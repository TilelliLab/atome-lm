"""superesp.datasets.water — SuperESP-Water: SYNTH leak/flood detection.

Common ESP32 safety build (flow meter + pressure + moisture). Classify the
plumbing state:
    no_flow      — valve closed, dry
    normal_use   — intermittent flow at stable pressure
    leak         — small persistent flow + slow pressure drop + rising moisture
    burst        — high flow + sharp pressure drop + fast moisture rise

Features (time-major, 8 steps x 4 = 32): [flow_lpm, pressure_bar, moisture, vibration].
SYNTH physics-style stand-in; labeled.
"""
from __future__ import annotations

import numpy as np
from superesp.datasets import Dataset, make_splits

CLASS_NAMES = ["no_flow", "normal_use", "leak", "burst"]
CHANNELS = ["flow_lpm", "pressure_bar", "moisture", "vibration"]
T = 8


def _window(rng, kind):
    if kind == "no_flow":
        flow = np.abs(rng.normal(0.0, 0.05, T)); pr = rng.uniform(2.8, 3.2, T)
        mo = rng.uniform(0.05, 0.15, T); vib = np.abs(rng.normal(0.02, 0.02, T))
    elif kind == "normal_use":
        flow = np.maximum(0, rng.uniform(4, 10) * (rng.random(T) > 0.3)) + rng.normal(0, 0.3, T)
        pr = rng.uniform(2.6, 3.0, T) + rng.normal(0, 0.1, T)
        mo = rng.uniform(0.05, 0.2, T); vib = rng.uniform(0.1, 0.4, T)
    elif kind == "leak":
        flow = rng.uniform(0.3, 1.2, T) + rng.normal(0, 0.1, T)  # small persistent
        pr = np.linspace(rng.uniform(2.8, 3.0), rng.uniform(2.3, 2.6), T) + rng.normal(0, 0.05, T)
        mo = np.linspace(0.2, rng.uniform(0.6, 0.9), T); vib = rng.uniform(0.05, 0.2, T)
    elif kind == "burst":
        flow = np.linspace(rng.uniform(12, 18), rng.uniform(20, 30), T) + rng.normal(0, 0.5, T)
        pr = np.linspace(rng.uniform(2.8, 3.0), rng.uniform(0.8, 1.5), T)
        mo = np.linspace(0.3, rng.uniform(0.9, 1.0), T); vib = rng.uniform(0.5, 1.2, T)
    return np.stack([flow, pr, mo, vib], axis=1)


def load(n_per_class: int = 600, seed: int = 0, noise_frac: float = 0.30) -> Dataset:
    rng = np.random.default_rng(seed)
    X, y = [], []
    for ci, k in enumerate(CLASS_NAMES):
        for _ in range(n_per_class):
            X.append(_window(rng, k).reshape(-1)); y.append(ci)
    X = np.asarray(X)
    X = X + rng.normal(0, 1, X.shape) * X.std(0, keepdims=True) * noise_frac
    return make_splits("water", "SYNTH", CLASS_NAMES, X, np.asarray(y), seed=seed,
                       description="flow+pressure+moisture leak/flood, 8-step x 4",
                       stream_shape=(T, 4))
