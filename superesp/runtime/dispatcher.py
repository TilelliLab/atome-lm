"""superesp.runtime.dispatcher — modality routing + abstention + OS policy.

A frame arrives tagged with its modality (which sensor produced it: "voice",
"motion", "agri", ...). The runtime knows the firmware reads each sensor on its
own bus, so routing is by modality tag (deterministic, no guessing) — the
on-device equivalent of Engram's "send this input to the head that owns it".
Each head then classifies with an abstention margin gate.

The OS head runs every tick on fused chip telemetry and emits both a device
state and a policy (which sensor heads to keep enabled), so a degraded device
sheds load — e.g. on `overheating` it disables the heavy audio heads.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import torch

from superesp.framework.tokenize import FeatureTokenizer
from superesp.framework import abstain
from superesp.framework.model import SuperESPHead


@dataclass
class RegisteredHead:
    model: SuperESPHead
    tokenizer: FeatureTokenizer
    class_names: list[str]
    model_sha256: str = ""          # for audit-log binding (which model decided)
    _last_frame: object = None      # event-driven wake state
    _last_dec: object = None


@dataclass
class Decision:
    modality: str
    label: str            # class name or "ABSTAIN"
    confidence: float     # top-1 softmax prob
    margin: float         # top1 - top2
    abstained: bool


# OS device-state -> sensor heads to DISABLE (shed load / avoid noise).
OS_POLICY = {
    "normal": set(),
    "low_memory": {"sound_scene", "voice"},      # audio heads are the heaviest
    "overheating": {"sound_scene", "voice"},
    "wifi_degraded": set(),                        # local sensing still fine
    "power_fault": {"sound_scene", "voice", "motion", "anomaly"},  # bare survival
}


@dataclass
class SuperESPRuntime:
    heads: dict[str, RegisteredHead] = field(default_factory=dict)
    abstain_threshold: float = 0.15
    os_modality: str = "os_telem"
    disabled: set = field(default_factory=set)
    audit: object = None            # optional AuditLog (tamper-evident flight recorder)
    fire_threshold: float = 0.0     # >0 enables event-driven wake (skip if input unchanged)

    def register(self, modality: str, model: SuperESPHead,
                 tokenizer: FeatureTokenizer, class_names: list[str],
                 model_sha256: str = "") -> None:
        self.heads[modality] = RegisteredHead(model, tokenizer, class_names, model_sha256)

    def classify(self, modality: str, raw_frame: np.ndarray) -> Decision:
        if modality not in self.heads:
            raise KeyError(f"no head registered for modality {modality!r}")
        if modality in self.disabled:
            return Decision(modality, "DISABLED", 0.0, 0.0, True)
        rh = self.heads[modality]
        frame = np.asarray(raw_frame, dtype=np.float64)
        ids = rh.tokenizer.transform(frame[None, :])

        # Event-driven wake: if the input barely moved since the last compute,
        # reuse the cached decision (no model run, no new log entry).
        if self.fire_threshold > 0 and rh._last_frame is not None:
            span = np.maximum(rh.tokenizer.vmax - rh.tokenizer.vmin, 1e-9)
            if np.max(np.abs(frame - rh._last_frame) / span) < self.fire_threshold:
                return rh._last_dec

        rh.model.eval()
        with torch.no_grad():
            probs = torch.softmax(rh.model.forward(ids), dim=-1)
        margin = abstain.margins(probs).item()
        top = int(probs.argmax(dim=-1).item())
        conf = float(probs[0, top].item())
        label = "ABSTAIN" if margin < self.abstain_threshold else rh.class_names[top]
        dec = Decision(modality, label, conf, margin, margin < self.abstain_threshold)

        rh._last_frame, rh._last_dec = frame, dec
        if self.audit is not None:
            self.audit.append(modality=modality, model_sha256=rh.model_sha256,
                              tokens=ids[0].tolist(), label=label, margin=margin)
        return dec

    def self_test(self, blob_dir) -> dict:
        """Boot-time integrity check: verify each head's signed attestation so a
        flash-corrupted or swapped model is caught before it decides anything."""
        import json
        from pathlib import Path
        from superesp.attest import sign
        blob_dir = Path(blob_dir)
        results = {}
        for modality in self.heads:
            att_p = blob_dir / f"{modality}.att.json"
            blob_p = blob_dir / f"{modality}.atomecl"
            if att_p.exists() and blob_p.exists():
                ok, reason = sign.verify(blob_p, json.loads(att_p.read_text()))
                results[modality] = ok
            else:
                results[modality] = None
        return results

    @staticmethod
    def fuse_intrusion(motion: Decision, sound: Decision) -> bool:
        """Cross-head fusion example: intrusion = aggressive motion AND a break/alarm
        sound, each above its own abstention bar. Two weak cues -> one strong alarm."""
        m_ok = (not motion.abstained) and motion.label in ("shake", "fall")
        s_ok = (not sound.abstained) and sound.label in ("glass_break", "alarm")
        return m_ok and s_ok

    def os_tick(self, telemetry_frame: np.ndarray) -> Decision:
        """Run the OS head on fused telemetry; update the load-shedding policy."""
        dec = self.classify(self.os_modality, telemetry_frame)
        state = dec.label if not dec.abstained else "normal"
        self.disabled = set(OS_POLICY.get(state, set()))
        return dec
