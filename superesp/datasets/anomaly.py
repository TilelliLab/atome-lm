"""superesp.datasets.anomaly — SuperESP-Anomaly: SYNTH machine-health.

Vibration signal (accel) from a rotating machine, summarized as band-energy
features over a short window. Physically-grounded fault signatures:
    normal       — clean 1x rotation tone + small noise
    imbalance    — strong 1x rotation harmonic
    bearing_fault— high-frequency impact bursts (broadband HF energy)
    looseness    — sub-harmonics (0.5x) + raised noise floor

Features: 8 log band-energies x 4 sub-windows (time-major) = 32 (<= MAX_SEQ).
SYNTH — a real predictive-maintenance task would use accelerometer captures;
this is a physics-style stand-in with reproducible fault structure.
"""
from __future__ import annotations

import numpy as np

from superesp.datasets import Dataset, make_splits

CLASS_NAMES = ["normal", "imbalance", "bearing_fault", "looseness"]
SR = 4000          # Hz
DUR = 0.256        # s
F_ROT = 50.0       # Hz rotation (3000 rpm)
N_SUBWIN = 4
N_BANDS = 8


def _signal(rng, kind: str) -> np.ndarray:
    n = int(SR * DUR)
    t = np.arange(n) / SR
    x = 0.3 * np.sin(2 * np.pi * F_ROT * t)               # base 1x
    x += rng.normal(0, 0.05, n)                            # noise floor
    if kind == "normal":
        pass
    elif kind == "imbalance":
        x += rng.uniform(0.6, 1.0) * np.sin(2 * np.pi * F_ROT * t + rng.uniform(0, 6))
    elif kind == "bearing_fault":
        # periodic high-freq impacts
        impact = np.zeros(n)
        period = int(SR / rng.uniform(120, 180))
        for s in range(0, n, max(period, 1)):
            impact[s] = rng.uniform(1.5, 3.0)
        hf = np.sin(2 * np.pi * rng.uniform(900, 1400) * t)
        x += np.convolve(impact, hf[:64], mode="same") * 0.4
        x += rng.normal(0, 0.1, n)
    elif kind == "looseness":
        x += rng.uniform(0.4, 0.7) * np.sin(2 * np.pi * 0.5 * F_ROT * t)
        x += rng.normal(0, 0.15, n)
    return x


def _features(x: np.ndarray) -> np.ndarray:
    sub = np.array_split(x, N_SUBWIN)
    feats = []
    for s in sub:
        spec = np.abs(np.fft.rfft(s * np.hanning(len(s)))) ** 2
        bands = np.array_split(spec, N_BANDS)
        feats.append(np.log10([b.sum() + 1e-10 for b in bands]))
    return np.concatenate(feats)  # (N_SUBWIN*N_BANDS,) = 32


def load(n_per_class: int = 500, seed: int = 0, noise_frac: float = 0.35) -> Dataset:
    rng = np.random.default_rng(seed)
    X, y = [], []
    for ci, kind in enumerate(CLASS_NAMES):
        for _ in range(n_per_class):
            X.append(_features(_signal(rng, kind)))
            y.append(ci)
    X = np.asarray(X)
    X = X + rng.normal(0, 1, X.shape) * X.std(0, keepdims=True) * noise_frac
    return make_splits("anomaly", "SYNTH", CLASS_NAMES, X, np.asarray(y),
                       seed=seed, description="rotating-machine vibration band-energy",
                       stream_shape=(N_SUBWIN, N_BANDS))
