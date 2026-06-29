"""superesp.datasets.wearable — SuperESP-Wearable: SYNTH PPG heart/activity.

Common ESP32 wearable build (MAX30102 PPG + IMU). Classify physiological state
from a window of derived features:
    rest      — low HR, high HRV, no motion
    active    — elevated HR, lower HRV, motion present
    exercise  — high HR, low HRV, strong motion
    irregular — erratic HR/HRV at low motion (arrhythmia-like flag, NOT a medical claim)

Features (time-major, 6 steps x 4 = 24): [hr_bpm, hrv_ms, accel_rms, perfusion].
SYNTH physics-style stand-in; NOT a medical device. Labeled.
"""
from __future__ import annotations

import numpy as np
from superesp.datasets import Dataset, make_splits

CLASS_NAMES = ["rest", "active", "exercise", "irregular"]
CHANNELS = ["hr_bpm", "hrv_ms", "accel_rms", "perfusion"]
T = 6


def _window(rng, kind):
    if kind == "rest":
        hr = rng.uniform(55, 70) + rng.normal(0, 2, T); hrv = rng.uniform(45, 75, T)
        acc = np.abs(rng.normal(0.02, 0.02, T)); perf = rng.uniform(0.8, 1.0, T)
    elif kind == "active":
        hr = rng.uniform(85, 110) + rng.normal(0, 3, T); hrv = rng.uniform(20, 40, T)
        acc = rng.uniform(0.3, 0.7, T); perf = rng.uniform(0.6, 0.9, T)
    elif kind == "exercise":
        hr = rng.uniform(130, 170) + rng.normal(0, 4, T); hrv = rng.uniform(8, 20, T)
        acc = rng.uniform(0.8, 1.5, T); perf = rng.uniform(0.5, 0.8, T)
    elif kind == "irregular":
        hr = rng.uniform(60, 100) + rng.normal(0, 18, T)  # erratic
        hrv = rng.uniform(90, 160, T) + rng.normal(0, 20, T)  # abnormally high variability
        acc = np.abs(rng.normal(0.05, 0.04, T)); perf = rng.uniform(0.5, 0.95, T)
    return np.stack([hr, hrv, acc, perf], axis=1)


def load(n_per_class: int = 600, seed: int = 0, noise_frac: float = 0.30) -> Dataset:
    rng = np.random.default_rng(seed)
    X, y = [], []
    for ci, k in enumerate(CLASS_NAMES):
        for _ in range(n_per_class):
            X.append(_window(rng, k).reshape(-1)); y.append(ci)
    X = np.asarray(X)
    X = X + rng.normal(0, 1, X.shape) * X.std(0, keepdims=True) * noise_frac
    return make_splits("wearable", "SYNTH", CLASS_NAMES, X, np.asarray(y), seed=seed,
                       description="PPG+IMU heart/activity state, 6-step x 4 (not medical)",
                       stream_shape=(T, 4))
