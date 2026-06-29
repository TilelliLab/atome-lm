"""superesp.datasets.power — SuperESP-Power: SYNTH energy/NILM monitoring.

One of the most common ESP32 builds: a CT-clamp energy monitor. From a window
of electrical features, classify which kind of load is running (the core of
non-intrusive load monitoring / NILM):
    off          — near-zero current
    resistive    — heater/kettle: high steady current, power factor ~1, low THD
    motor        — fridge/pump: inductive (low PF), startup surge, some harmonics
    electronic   — TV/PC/LED: lower current, poor PF, high THD (switching supply)

Features (time-major, 6 steps x 4 = 24): [I_rms(A), power_factor, THD, crest_factor].
SYNTH physics-style stand-in (real build → CT clamp + emonlib); labeled.
"""
from __future__ import annotations

import numpy as np
from superesp.datasets import Dataset, make_splits

CLASS_NAMES = ["off", "resistive", "motor", "electronic"]
CHANNELS = ["I_rms", "power_factor", "THD", "crest_factor"]
T = 6


def _window(rng, kind):
    if kind == "off":
        I = np.abs(rng.normal(0.02, 0.02, T)); pf = rng.uniform(0, 0.3, T)
        thd = rng.uniform(0, 0.1, T); cf = rng.uniform(1.0, 1.6, T)
    elif kind == "resistive":
        I = rng.uniform(6, 14) + rng.normal(0, 0.3, T); pf = rng.uniform(0.97, 1.0, T)
        thd = rng.uniform(0.02, 0.08, T); cf = rng.uniform(1.38, 1.45, T)
    elif kind == "motor":
        base = rng.uniform(2, 5); I = np.full(T, base) + rng.normal(0, 0.2, T)
        I[0] += rng.uniform(6, 12)  # startup inrush
        pf = rng.uniform(0.5, 0.75, T); thd = rng.uniform(0.08, 0.2, T)
        cf = rng.uniform(1.5, 2.2, T)
    elif kind == "electronic":
        I = rng.uniform(0.3, 2.0) + rng.normal(0, 0.1, T); pf = rng.uniform(0.55, 0.8, T)
        thd = rng.uniform(0.25, 0.6, T); cf = rng.uniform(2.0, 3.5, T)
    return np.stack([I, pf, thd, cf], axis=1)


def load(n_per_class: int = 600, seed: int = 0, noise_frac: float = 0.55) -> Dataset:
    rng = np.random.default_rng(seed)
    X, y = [], []
    for ci, k in enumerate(CLASS_NAMES):
        for _ in range(n_per_class):
            X.append(_window(rng, k).reshape(-1)); y.append(ci)
    X = np.asarray(X)
    X = X + rng.normal(0, 1, X.shape) * X.std(0, keepdims=True) * noise_frac
    return make_splits("power", "SYNTH", CLASS_NAMES, X, np.asarray(y), seed=seed,
                       description="CT-clamp NILM: 6-step x 4 electrical features",
                       stream_shape=(T, 4))
