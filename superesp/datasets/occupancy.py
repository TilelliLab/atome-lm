"""superesp.datasets.occupancy — SuperESP-Occupancy: SYNTH smart-room sensing.

Very common ESP32 smart-home build (PIR + environment) for thermostats / lights:
classify room occupancy from fused sensors:
    empty     — no motion, baseline CO2/sound
    occupied  — some motion, rising CO2, moderate sound
    crowded   — high motion, high CO2, loud

Features (time-major, 6 steps x 4 = 24): [pir_rate, co2_ppm, sound_dB, temp_rise].
SYNTH physics-style stand-in; labeled.
"""
from __future__ import annotations

import numpy as np
from superesp.datasets import Dataset, make_splits

CLASS_NAMES = ["empty", "occupied", "crowded"]
CHANNELS = ["pir_rate", "co2_ppm", "sound_dB", "temp_rise"]
T = 6


def _window(rng, kind):
    if kind == "empty":
        pir = np.abs(rng.normal(0.0, 0.05, T)); co2 = 420 + rng.normal(0, 15, T)
        snd = rng.uniform(30, 38, T); tr = rng.normal(0, 0.2, T)
    elif kind == "occupied":
        pir = rng.uniform(0.2, 0.5, T) + rng.normal(0, 0.05, T)
        co2 = np.linspace(rng.uniform(500, 650), rng.uniform(700, 900), T) + rng.normal(0, 20, T)
        snd = rng.uniform(40, 55, T); tr = np.linspace(0.1, rng.uniform(0.5, 1.0), T)
    elif kind == "crowded":
        pir = rng.uniform(0.7, 1.0, T) + rng.normal(0, 0.05, T)
        co2 = np.linspace(rng.uniform(900, 1100), rng.uniform(1400, 2000), T) + rng.normal(0, 40, T)
        snd = rng.uniform(58, 75, T); tr = np.linspace(0.5, rng.uniform(1.5, 3.0), T)
    return np.stack([pir, co2, snd, tr], axis=1)


def load(n_per_class: int = 700, seed: int = 0, noise_frac: float = 0.80) -> Dataset:
    rng = np.random.default_rng(seed)
    X, y = [], []
    for ci, k in enumerate(CLASS_NAMES):
        for _ in range(n_per_class):
            X.append(_window(rng, k).reshape(-1)); y.append(ci)
    X = np.asarray(X)
    X = X + rng.normal(0, 1, X.shape) * X.std(0, keepdims=True) * noise_frac
    return make_splits("occupancy", "SYNTH", CLASS_NAMES, X, np.asarray(y), seed=seed,
                       description="PIR+CO2+sound room occupancy, 6-step x 4",
                       stream_shape=(T, 4))
