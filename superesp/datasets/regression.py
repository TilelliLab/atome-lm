"""superesp.datasets.regression — SYNTH continuous-target task (regression).

Demonstrates Atome heads predicting a NUMBER, not a class. Scenario: estimate
"hours until irrigation needed" from a 6-step window of 4 farm sensors
    [soil_moisture %, air_temp C, humidity %, ET0 (evapotranspiration mm/h)].
Physics-style target: hours ≈ (moisture - dry_threshold) / drying_rate, where
drying_rate rises with temp+ET0 and falls with humidity, plus noise.

Returns tokenized features (leak-free, tokenizer fit on TRAIN) + NORMALIZED
float targets, with (target_mean, target_std) for de-normalization to hours.
SYNTH, labeled — not a field claim.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch

from superesp.framework.tokenize import FeatureTokenizer

T, C = 6, 4
DRY_THRESHOLD = 20.0  # % soil moisture at which irrigation is needed


@dataclass
class RegressionDataset:
    name: str
    source: str
    train_ids: torch.Tensor
    train_y: torch.Tensor      # normalized
    val_ids: torch.Tensor
    val_y: torch.Tensor
    test_ids: torch.Tensor
    test_y: torch.Tensor        # normalized
    test_y_real: np.ndarray     # original units (hours)
    tokenizer: FeatureTokenizer
    target_mean: float
    target_std: float
    units: str = "hours"


def _sample(rng):
    moisture = rng.uniform(22, 60)
    temp = rng.uniform(12, 38)
    humidity = rng.uniform(20, 90)
    et0 = rng.uniform(0.05, 0.6)
    # window: moisture slowly drops; other channels noisy-steady
    drying_rate = 0.15 * (1 + 0.06 * (temp - 20) + 4.0 * et0 - 0.01 * (humidity - 50))
    drying_rate = max(drying_rate, 0.02)
    m = moisture - drying_rate * np.arange(T) + rng.normal(0, 0.5, T)
    win = np.stack([m,
                    temp + rng.normal(0, 1.0, T),
                    humidity + rng.normal(0, 3.0, T),
                    et0 + rng.normal(0, 0.03, T)], axis=1)
    hours = max((moisture - DRY_THRESHOLD) / drying_rate, 0.0) + rng.normal(0, 2.0)
    hours = max(hours, 0.0)
    return win.reshape(-1), hours


def load(n: int = 3000, seed: int = 0):
    rng = np.random.default_rng(seed)
    X = np.zeros((n, T * C)); y = np.zeros(n)
    for i in range(n):
        X[i], y[i] = _sample(rng)
    idx = rng.permutation(n)
    ntr, nva = int(0.7 * n), int(0.15 * n)
    tr, va, te = idx[:ntr], idx[ntr:ntr + nva], idx[ntr + nva:]
    tok = FeatureTokenizer.fit(X[tr])
    mu, sd = y[tr].mean(), y[tr].std() + 1e-9
    norm = lambda a: torch.from_numpy(((a - mu) / sd)).float()
    return RegressionDataset(
        "irrigation_hours", "SYNTH",
        tok.transform(X[tr]), norm(y[tr]),
        tok.transform(X[va]), norm(y[va]),
        tok.transform(X[te]), norm(y[te]),
        y[te], tok, float(mu), float(sd),
    )
