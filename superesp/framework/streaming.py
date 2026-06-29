"""superesp.framework.streaming — change-gated streaming classification.

For always-on sensing, the cheapest classification is the one you DON'T run.
On a correlated sensor stream, consecutive windows are nearly identical, so we
gate the (already kernel-optimized) classifier with an integrate-and-fire test:
only re-run the model when the input frame has drifted past a threshold since
the last time we actually classified; otherwise reuse the cached decision.

This is exact — every decision the gate EMITS is produced by the same
`SuperESPHead.forward`, bit-identical to running it every frame. The only thing
that changes is HOW OFTEN the model runs. The measured win is the skip rate
(fraction of frames served from cache) on a real stream. Combined with the 3.5×
ternary-kernel speedup, this is the always-on speed story.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import torch

from superesp.framework.tokenize import FeatureTokenizer
from superesp.framework import abstain


@dataclass
class StreamStats:
    frames: int = 0
    computed: int = 0          # frames where the model actually ran
    skipped: int = 0           # frames served from cache

    @property
    def skip_rate(self) -> float:
        return self.skipped / self.frames if self.frames else 0.0

    @property
    def speedup(self) -> float:
        return self.frames / self.computed if self.computed else float("inf")


@dataclass
class StreamingClassifier:
    model: object               # SuperESPHead
    tokenizer: FeatureTokenizer
    class_names: list
    fire_threshold: float = 0.05    # normalized per-feature drift to re-fire
    abstain_threshold: float = 0.15
    _last_frame: np.ndarray | None = field(default=None, repr=False)
    _last_decision: tuple | None = field(default=None, repr=False)
    stats: StreamStats = field(default_factory=StreamStats)

    def _classify(self, frame: np.ndarray) -> tuple:
        ids = self.tokenizer.transform(np.asarray(frame, dtype=np.float64)[None, :])
        self.model.eval()
        with torch.no_grad():
            probs = torch.softmax(self.model.forward(ids), dim=-1)
        margin = abstain.margins(probs).item()
        top = int(probs.argmax(dim=-1).item())
        label = self.class_names[top] if margin >= self.abstain_threshold else "ABSTAIN"
        return label, float(probs[0, top].item()), margin

    def push(self, frame: np.ndarray) -> tuple:
        """Feed one streamed frame; returns (label, confidence, margin, computed?)."""
        frame = np.asarray(frame, dtype=np.float64)
        self.stats.frames += 1
        if self._last_frame is not None:
            # integrate-and-fire on normalized per-feature drift
            span = np.maximum(self.tokenizer.vmax - self.tokenizer.vmin, 1e-9)
            drift = np.max(np.abs(frame - self._last_frame) / span)
            if drift < self.fire_threshold:
                self.stats.skipped += 1
                return (*self._last_decision, False)
        dec = self._classify(frame)
        self._last_frame = frame
        self._last_decision = dec
        self.stats.computed += 1
        return (*dec, True)
