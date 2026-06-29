"""superesp.datasets.forecast — SuperESP-Forecast: SYNTH time-to-event.

Predict the FUTURE, not the present: from a window of a degrading machine's
sensors, classify how soon failure will occur — so the device acts BEFORE the
fault (the high-value safety pattern). A hidden degradation level rises at a
per-unit rate; failure when it crosses 1.0. The window shows current level +
recent slope (noisy). Label = bucket of steps-until-failure:
    safe     (> 30 steps)
    later    (15-30)
    soon     (5-15)
    imminent (< 5)

Features (time-major, 6 steps x 4 = 24): [level, slope, vib_rms, temp].
SYNTH physics-style stand-in; labeled.
"""
from __future__ import annotations

import numpy as np
from superesp.datasets import Dataset, make_splits

CLASS_NAMES = ["safe", "later", "soon", "imminent"]
T, C = 6, 4


def _sample(rng):
    rate = rng.uniform(0.005, 0.05)           # degradation per step
    level0 = rng.uniform(0.0, 0.95)           # current hidden damage
    steps_left = max((1.0 - level0) / rate, 0.0)
    # observed window: level rising at ~rate, vibration & temp grow with level
    t = np.arange(T)
    level = np.clip(level0 - rate * (T - 1 - t), 0, 1.2) + rng.normal(0, 0.01, T)
    slope = np.full(T, rate) + rng.normal(0, 0.003, T)
    vib = 0.2 + 1.5 * level + rng.normal(0, 0.08, T)
    temp = 40 + 30 * level + rng.normal(0, 1.5, T)
    win = np.stack([level, slope, vib, temp], axis=1).reshape(-1)
    if steps_left > 30:   c = 0
    elif steps_left > 15: c = 1
    elif steps_left > 5:  c = 2
    else:                 c = 3
    return win, c


def load(n_per_class: int = 700, seed: int = 0) -> Dataset:
    rng = np.random.default_rng(seed)
    # rejection-sample to balance buckets
    buckets = {i: [] for i in range(4)}
    target = n_per_class
    while any(len(v) < target for v in buckets.values()):
        win, c = _sample(rng)
        if len(buckets[c]) < target:
            buckets[c].append(win)
    X = np.vstack([np.array(buckets[c]) for c in range(4)])
    y = np.concatenate([np.full(target, c) for c in range(4)])
    return make_splits("forecast", "SYNTH", CLASS_NAMES, X, y, seed=seed,
                       description="time-to-failure bucket from degradation window",
                       stream_shape=(T, C))
