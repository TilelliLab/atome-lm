"""superesp.framework.tokenize — quantize feature frames to byte tokens.

Everything in SuperESP reduces to a sequence of byte tokens (0..255, length
<= MAX_SEQ) so the existing Atome byte-vocab engine runs unchanged. A "frame"
is a feature vector of length n_features <= MAX_SEQ; each feature is linearly
quantized to one byte using per-feature min/max fitted on the TRAIN split only
(no test leakage).

Two modes:
- "global"  : each feature -> a byte in 0..255 (full resolution). Best for
              sensor/threshold tasks where the value pattern is what matters.
- "banded"  : each feature -> a byte in its OWN sub-range [i*B, i*B+B-1],
              B=256//n_features. This encodes FEATURE IDENTITY into the token so
              the shared embedding can't collide value `v` of feature i with the
              same value of feature j. Costs resolution (B levels/feature) but is
              what makes correlated-feature tasks (MFCC keyword spotting) learnable
              on the byte-vocab engine — measured voice 0.39->0.59. The engine is
              unchanged either way (still byte tokens), so bit-exact C parity holds.

The fitted (vmin, vmax) + mode are the exact constants an MCU firmware would bake
in to reproduce the same tokens, so they are saved alongside each head.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import torch

from superesp.framework.config import MAX_SEQ


@dataclass
class FeatureTokenizer:
    vmin: np.ndarray  # (n_features,)
    vmax: np.ndarray  # (n_features,)
    mode: str = "global"          # "global" | "banded"

    @classmethod
    def fit(cls, X: np.ndarray, mode: str = "global") -> "FeatureTokenizer":
        """Fit per-feature min/max on TRAIN data only. X: (n, n_features)."""
        X = np.asarray(X, dtype=np.float64)
        if X.ndim != 2:
            raise ValueError(f"expected 2D (n, n_features), got {X.shape}")
        if X.shape[1] > MAX_SEQ:
            raise ValueError(
                f"n_features={X.shape[1]} exceeds MAX_SEQ={MAX_SEQ}; "
                "downsample/aggregate the window first"
            )
        if mode not in ("global", "banded"):
            raise ValueError(f"mode must be global|banded, got {mode!r}")
        vmin = X.min(axis=0)
        vmax = X.max(axis=0)
        # Guard against zero-range features (constant column -> all mid-gray).
        flat = vmax - vmin < 1e-12
        vmax = np.where(flat, vmin + 1.0, vmax)
        return cls(vmin=vmin, vmax=vmax, mode=mode)

    def transform(self, X: np.ndarray) -> torch.Tensor:
        """X: (n, n_features) float -> (n, n_features) int64 byte tokens."""
        X = np.asarray(X, dtype=np.float64)
        norm = np.clip((X - self.vmin) / (self.vmax - self.vmin), 0.0, 1.0)
        if self.mode == "banded":
            nfeat = X.shape[1]
            B = max(256 // nfeat, 2)
            idx = np.arange(nfeat)[None, :]
            toks = idx * B + np.round(norm * (B - 1)).astype(np.int64)
            return torch.from_numpy(np.clip(toks, 0, 255).astype(np.int64))
        toks = np.round(norm * 255.0).astype(np.int64)
        return torch.from_numpy(toks)

    def to_dict(self) -> dict:
        return {"vmin": self.vmin.tolist(), "vmax": self.vmax.tolist(), "mode": self.mode}

    @classmethod
    def from_dict(cls, d: dict) -> "FeatureTokenizer":
        return cls(vmin=np.asarray(d["vmin"]), vmax=np.asarray(d["vmax"]),
                   mode=d.get("mode", "global"))
