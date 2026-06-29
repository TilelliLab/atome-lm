"""superesp.datasets.air — SuperESP-Air: SYNTH air-quality / leak detection.

A short window of 5 gas/climate sensors (time-major), 5 channels x 6 steps = 30:
    channels = [MQ2_gas, CO2_ppm, VOC_index, temp C, humidity %]
Classes:
    clean     — baseline indoor air
    co2_high  — rising CO2 (poor ventilation)
    gas_leak  — sharp MQ2 + VOC rise (combustible gas)
    smoke     — MQ2 + VOC + temp rise, humidity drop (smouldering)

SYNTH — physics-style stand-in; a real build would use MQ-series / SGP / SCD
sensors. Reproducible class structure with overlap + noise.
"""
from __future__ import annotations

import numpy as np

from superesp.datasets import Dataset, make_splits

CLASS_NAMES = ["clean", "co2_high", "gas_leak", "smoke"]
CHANNELS = ["MQ2_gas", "CO2_ppm", "VOC_index", "temp", "humidity"]
T = 6


def _window(rng, kind: str) -> np.ndarray:
    mq = np.full(T, 120.0); co2 = np.full(T, 450.0); voc = np.full(T, 80.0)
    temp = np.full(T, 22.0); hum = np.full(T, 45.0)
    if kind == "clean":
        mq += rng.normal(0, 8, T); co2 += rng.normal(0, 20, T); voc += rng.normal(0, 6, T)
        temp += rng.normal(0, 0.6, T); hum += rng.normal(0, 3, T)
    elif kind == "co2_high":
        co2 = np.linspace(rng.uniform(600, 800), rng.uniform(1200, 1800), T) + rng.normal(0, 30, T)
        mq += rng.normal(0, 8, T); voc += rng.normal(20, 8, T)
        temp += rng.normal(0.5, 0.5, T); hum += rng.normal(0, 3, T)
    elif kind == "gas_leak":
        mq = np.linspace(rng.uniform(180, 250), rng.uniform(500, 800), T) + rng.normal(0, 20, T)
        voc = np.linspace(rng.uniform(120, 160), rng.uniform(250, 400), T) + rng.normal(0, 15, T)
        co2 += rng.normal(0, 30, T); temp += rng.normal(0, 0.6, T); hum += rng.normal(0, 3, T)
    elif kind == "smoke":
        mq = np.linspace(rng.uniform(160, 220), rng.uniform(400, 650), T) + rng.normal(0, 20, T)
        voc = np.linspace(rng.uniform(140, 180), rng.uniform(300, 450), T) + rng.normal(0, 15, T)
        temp = np.linspace(rng.uniform(24, 28), rng.uniform(35, 50), T) + rng.normal(0, 1, T)
        hum = np.linspace(rng.uniform(40, 45), rng.uniform(20, 30), T) + rng.normal(0, 2, T)
        co2 += rng.normal(100, 30, T)
    return np.stack([mq, co2, voc, temp, hum], axis=1)


def load(n_per_class: int = 600, seed: int = 0, noise_frac: float = 0.70) -> Dataset:
    rng = np.random.default_rng(seed)
    X, y = [], []
    for ci, kind in enumerate(CLASS_NAMES):
        for _ in range(n_per_class):
            X.append(_window(rng, kind).reshape(-1))
            y.append(ci)
    X = np.asarray(X)
    # Realistic sensor-grade measurement noise so classes OVERLAP (the earlier
    # version was trivially separable -> 0.997, a red flag). Scaled per-feature.
    X = X + rng.normal(0, 1, X.shape) * X.std(0, keepdims=True) * noise_frac
    return make_splits("air", "SYNTH", CLASS_NAMES, X, np.asarray(y),
                       seed=seed, description="6-step x 5 gas/climate sensor window",
                       stream_shape=(T, 5))
