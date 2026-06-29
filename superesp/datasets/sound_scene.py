"""superesp.datasets.sound_scene — SuperESP-Sound-Scene: SYNTH acoustic events.

Ambient acoustic event detection (distinct from keyword spotting): the device
listens for environmental sounds, not words. Synthesized waveforms per class,
turned into MFCC features (same front-end as Voice):
    quiet       — low broadband noise
    alarm       — periodic beep tone (square-ish, ~2-4 kHz on/off)
    glass_break — sharp broadband burst + HF ring decay
    speech_like — formant-structured buzz (voiced sound, not a specific word)

SYNTH — physics-style stand-in. A real build would train on ESC-50 / UrbanSound.
"""
from __future__ import annotations

import numpy as np

from superesp.framework.audio import mfcc_features
from superesp.datasets import Dataset, make_splits

CLASS_NAMES = ["quiet", "alarm", "glass_break", "speech_like"]
SR = 16000
DUR = 0.5
N_MFCC = 8
N_FRAMES = 4  # 8*4 = 32


def _wave(rng, kind: str) -> np.ndarray:
    n = int(SR * DUR)
    t = np.arange(n) / SR
    if kind == "quiet":
        x = rng.normal(0, 0.02, n)
    elif kind == "alarm":
        f = rng.uniform(2000, 3500)
        beep = np.sign(np.sin(2 * np.pi * f * t))
        gate = (np.sin(2 * np.pi * rng.uniform(4, 8) * t) > 0).astype(float)
        x = 0.5 * beep * gate + rng.normal(0, 0.02, n)
    elif kind == "glass_break":
        x = rng.normal(0, 0.03, n)
        burst = rng.integers(0, n // 3)
        env = np.exp(-np.maximum(t - burst / SR, 0) * rng.uniform(15, 35))
        ring = np.sin(2 * np.pi * rng.uniform(3000, 6000) * t)
        x += 1.2 * env * ring
    elif kind == "speech_like":
        f0 = rng.uniform(100, 160)
        x = np.zeros(n)
        for h, amp in [(1, 1.0), (2, 0.5), (3, 0.7), (4, 0.3), (5, 0.4)]:
            x += amp * np.sin(2 * np.pi * f0 * h * t + rng.uniform(0, 6))
        x *= (0.5 + 0.5 * np.sin(2 * np.pi * rng.uniform(3, 6) * t))  # syllable envelope
        x = 0.3 * x + rng.normal(0, 0.02, n)
    return x


def load(n_per_class: int = 400, seed: int = 0) -> Dataset:
    rng = np.random.default_rng(seed)
    X, y = [], []
    for ci, kind in enumerate(CLASS_NAMES):
        for _ in range(n_per_class):
            feats = mfcc_features(_wave(rng, kind), SR, n_mfcc=N_MFCC, n_frames=N_FRAMES)
            X.append(feats)
            y.append(ci)
    return make_splits("sound_scene", "SYNTH", CLASS_NAMES, np.asarray(X), np.asarray(y),
                       seed=seed, description="synth acoustic-event MFCC (8 mfcc x 4 frames)")
