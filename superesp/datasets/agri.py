"""superesp.datasets.agri — SuperESP-Agri: physically-grounded SYNTHETIC.

A 6-hour window of 5 farm sensors (time-major), 30 features total (<= MAX_SEQ):
    channels = [soil_moisture %, air_temp C, humidity %, soil_temp C, leaf_wetness 0-1]
    window   = 6 timesteps, flattened time-major: [t0_c0..t0_c4, t1_c0.. ...]

Classes (rule-labeled from agronomic conditions, then Gaussian-noised so the
task is non-trivial — not linearly separable):
    0 healthy        — comfortable, stable
    1 needs_irrigate — soil moisture declining + hot + dry air
    2 frost_risk     — air temp falling toward/below 0 C
    3 pest_favorable — warm + very humid + leaf wetness (fungal/pest window)
    4 sensor_fault   — a channel stuck at an out-of-range extreme

SYNTH, not a field deployment claim. The point is a real, trainable, held-out
streaming-classification task that exercises the conv+SSM pathways and the
delta-inference stream, with reproducible physics-style class structure.
"""
from __future__ import annotations

import numpy as np

from superesp.datasets import Dataset, make_splits

CLASS_NAMES = ["healthy", "needs_irrigate", "frost_risk", "pest_favorable", "sensor_fault"]
CHANNELS = ["soil_moisture", "air_temp", "humidity", "soil_temp", "leaf_wetness"]
T = 6  # timesteps
C = 5  # channels


def _window(rng, kind: str) -> np.ndarray:
    """Return (T, C) physical window for a class, with noise."""
    t = np.arange(T)
    sm = np.full(T, 50.0)   # soil moisture %
    at = np.full(T, 22.0)   # air temp C
    hu = np.full(T, 60.0)   # humidity %
    st = np.full(T, 19.0)   # soil temp C
    lw = np.full(T, 0.1)    # leaf wetness

    if kind == "healthy":
        sm += rng.normal(0, 4, T) + rng.uniform(-8, 8)
        at += rng.normal(0, 1.5, T) + rng.uniform(-3, 3)
        hu += rng.normal(0, 5, T) + rng.uniform(-8, 8)
        st += rng.normal(0, 1.2, T)
        lw = np.clip(lw + rng.normal(0, 0.05, T), 0, 1)
    elif kind == "needs_irrigate":
        sm = np.linspace(rng.uniform(32, 40), rng.uniform(10, 20), T) + rng.normal(0, 2, T)
        at = np.linspace(rng.uniform(27, 30), rng.uniform(33, 37), T) + rng.normal(0, 1, T)
        hu = np.linspace(rng.uniform(38, 45), rng.uniform(22, 30), T) + rng.normal(0, 3, T)
        st += rng.normal(2, 1.0, T)
        lw = np.clip(rng.normal(0.05, 0.03, T), 0, 1)
    elif kind == "frost_risk":
        at = np.linspace(rng.uniform(6, 9), rng.uniform(-3, 1), T) + rng.normal(0, 0.7, T)
        st = np.linspace(rng.uniform(8, 11), rng.uniform(0, 3), T) + rng.normal(0, 0.7, T)
        hu += rng.normal(15, 5, T)
        sm += rng.normal(0, 3, T)
        lw = np.clip(lw + rng.normal(0.1, 0.05, T), 0, 1)
    elif kind == "pest_favorable":
        hu = np.linspace(rng.uniform(82, 88), rng.uniform(90, 96), T) + rng.normal(0, 2, T)
        lw = np.clip(np.linspace(0.6, 0.9, T) + rng.normal(0, 0.05, T), 0, 1)
        at += rng.normal(4, 1.0, T)  # warm + humid
        sm += rng.normal(0, 3, T)
        st += rng.normal(2, 1.0, T)
    elif kind == "sensor_fault":
        # one channel stuck at an out-of-range extreme; rest noisy-normal
        sm += rng.normal(0, 4, T); at += rng.normal(0, 1.5, T)
        hu += rng.normal(0, 5, T); st += rng.normal(0, 1.2, T)
        lw = np.clip(lw + rng.normal(0, 0.05, T), 0, 1)
        ch = rng.integers(0, C)
        extreme = {0: rng.uniform(-20, -5), 1: rng.uniform(80, 95),
                   2: rng.uniform(-30, -10), 3: rng.uniform(80, 95),
                   4: rng.uniform(3, 6)}[ch]
        [sm, at, hu, st, lw][ch][:] = extreme + rng.normal(0, 0.3, T)
    else:
        raise ValueError(kind)
    return np.stack([sm, at, hu, st, lw], axis=1)  # (T, C)


def load(n_per_class: int = 600, seed: int = 0) -> Dataset:
    rng = np.random.default_rng(seed)
    X, y = [], []
    for ci, kind in enumerate(CLASS_NAMES):
        for _ in range(n_per_class):
            w = _window(rng, kind)               # (T, C)
            X.append(w.reshape(-1))               # time-major flatten -> (T*C,)
            y.append(ci)
    X = np.asarray(X)  # (N, 30)
    y = np.asarray(y)
    return make_splits(
        "agri", "SYNTH", CLASS_NAMES, X, y, seed=seed,
        description="6h x 5-sensor farm window, agronomic rule labels + noise",
        stream_shape=(T, C),
    )
