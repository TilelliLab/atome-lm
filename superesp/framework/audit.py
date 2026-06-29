"""superesp.framework.audit — tamper-evident on-device decision log (flight recorder).

The auditable-edge wedge made concrete: the device keeps a hash-chained log of
EVERY decision it made, each entry binding the exact model that produced it
(attested blob sha256), a hash of the input, the predicted label, and the
confidence margin. Anyone can later replay the chain and prove the device's
decision history was not altered, reordered, or produced by a different model —
something no mainstream TinyML runtime offers.

Chain: entry_hash[i] = sha256(prev_hash || canonical(record[i])). Tampering with
any record, its order, or the bound model hash breaks the chain at that point.
This is a lightweight RFC-6962-style append-only log sized for an MCU (each entry
is ~100 bytes; verification needs only sha256). C-mirror is a ~40-LOC sha256 +
running hash in flash/NVS.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

GENESIS = "0" * 64


def _canonical(d: dict) -> bytes:
    return json.dumps(d, sort_keys=True, separators=(",", ":")).encode()


def _input_hash(tokens) -> str:
    return hashlib.sha256(bytes(int(t) & 0xFF for t in tokens)).hexdigest()[:16]


@dataclass
class AuditLog:
    entries: list = field(default_factory=list)

    @property
    def head_hash(self) -> str:
        return self.entries[-1]["entry_hash"] if self.entries else GENESIS

    def append(self, *, modality: str, model_sha256: str, tokens,
               label: str, margin: float) -> dict:
        prev = self.head_hash
        record = {
            "seq": len(self.entries),
            "prev": prev,
            "modality": modality,
            "model": model_sha256[:16],     # binds WHICH attested head decided
            "input": _input_hash(tokens),
            "label": label,
            "margin": round(float(margin), 4),
        }
        entry_hash = hashlib.sha256(prev.encode() + _canonical(record)).hexdigest()
        record["entry_hash"] = entry_hash
        self.entries.append(record)
        return record

    def verify(self) -> tuple[bool, int]:
        """Replay the chain. Returns (ok, first_bad_index or -1)."""
        prev = GENESIS
        for i, rec in enumerate(self.entries):
            body = {k: rec[k] for k in rec if k != "entry_hash"}
            if rec["prev"] != prev:
                return False, i
            expect = hashlib.sha256(prev.encode() + _canonical(body)).hexdigest()
            if expect != rec["entry_hash"]:
                return False, i
            prev = rec["entry_hash"]
        return True, -1

    def to_json(self) -> str:
        return json.dumps(self.entries, indent=2)
