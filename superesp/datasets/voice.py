"""superesp.datasets.voice — SuperESP-Voice: keyword spotting (KWS).

Tries REAL data first (Google Speech Commands test set, downloaded to
superesp/.data/speech_test.tar.gz) and falls back to physics-style SYNTH tones
if the corpus is absent. The Dataset's `source` field records which actually
loaded ("REAL" vs "SYNTH"), so results tables never mislabel.

Front-end: MFCC (8 coeffs x 4 frames = 32) — the same the ESP32 I2S mic path
would run. Keywords are farm-relevant commands.
"""
from __future__ import annotations

import io
import tarfile
from pathlib import Path

import numpy as np

from superesp.framework.audio import mfcc_features
from superesp.datasets import Dataset, make_splits

KEYWORDS = ["on", "off", "stop", "go"]   # farm commands
SR = 16000
N_MFCC, N_FRAMES = 8, 4
_TARBALL = Path(__file__).resolve().parents[1] / ".data" / "speech_test.tar.gz"


def _load_real(max_per_class: int, seed: int):
    """Return (X, y, names) from the Speech Commands tarball, or None."""
    if not _TARBALL.exists():
        return None
    try:
        from scipy.io import wavfile
    except Exception:
        return None
    rng = np.random.default_rng(seed)
    X, y = [], []
    got = {i: 0 for i in range(len(KEYWORDS))}
    with tarfile.open(_TARBALL, "r:gz") as tf:
        members = [m for m in tf.getmembers() if m.isfile() and m.name.endswith(".wav")]
        rng.shuffle(members)
        for m in members:
            parts = m.name.strip("./").split("/")
            if len(parts) < 2:
                continue
            label = parts[0]
            if label not in KEYWORDS:
                continue
            ci = KEYWORDS.index(label)
            if got[ci] >= max_per_class:
                continue
            f = tf.extractfile(m)
            if f is None:
                continue
            try:
                sr, wave = wavfile.read(io.BytesIO(f.read()))
            except Exception:
                continue
            wave = wave.astype(np.float64)
            X.append(mfcc_features(wave, sr, n_mfcc=N_MFCC, n_frames=N_FRAMES))
            y.append(ci)
            got[ci] += 1
            if all(v >= max_per_class for v in got.values()):
                break
    if len(X) < len(KEYWORDS) * 20:  # too few real samples -> not usable
        return None
    return np.asarray(X), np.asarray(y), KEYWORDS


def _synth_word(rng, ci: int) -> np.ndarray:
    """Distinct synthetic 'word' waveforms (NOT real speech) per keyword index."""
    n = int(SR * 0.7)
    t = np.arange(n) / SR
    f0 = [120, 150, 100, 180][ci]
    # different formant/syllable patterns per word
    x = np.zeros(n)
    harmonics = [(1, 1.0), (2, 0.6), (3, 0.4)] if ci % 2 == 0 else [(1, 1.0), (3, 0.7), (5, 0.4)]
    for h, a in harmonics:
        x += a * np.sin(2 * np.pi * f0 * h * t + rng.uniform(0, 6))
    syl = [3, 5, 2, 7][ci]
    x *= (0.5 + 0.5 * np.sin(2 * np.pi * syl * t))
    return 0.3 * x + rng.normal(0, 0.02, n)


def _load_synth(n_per_class: int, seed: int):
    rng = np.random.default_rng(seed)
    X, y = [], []
    for ci in range(len(KEYWORDS)):
        for _ in range(n_per_class):
            X.append(mfcc_features(_synth_word(rng, ci), SR, n_mfcc=N_MFCC, n_frames=N_FRAMES))
            y.append(ci)
    return np.asarray(X), np.asarray(y), KEYWORDS


_CACHE = Path(__file__).resolve().parents[1] / ".data" / "voice_real_cache.npz"


def load(max_per_class: int = 200, seed: int = 0) -> Dataset:
    # Cache real MFCC features (tar scan is slow) so repeated runs are fast.
    # The test-set has a limited, fixed number of clips per word, so we just
    # reuse whatever the cache captured (capping per-class if a smaller run asks).
    if _CACHE.exists():
        z = np.load(_CACHE, allow_pickle=True)
        X, y = z["X"], z["y"]
        if max_per_class < int(z["max_per_class"]):
            keep = np.concatenate([
                np.where(y == c)[0][:max_per_class] for c in np.unique(y)
            ])
            X, y = X[keep], y[keep]
        return make_splits("voice", "REAL", list(z["names"]), X, y, seed=seed,
                           description="Google Speech Commands KWS, MFCC 8x4 (cached)",
                           tokenizer_mode="banded")
    real = _load_real(max_per_class, seed)
    if real is not None:
        X, y, names = real
        np.savez(_CACHE, X=X, y=y, names=np.array(names), max_per_class=max_per_class)
        return make_splits("voice", "REAL", names, X, y, seed=seed,
                           description="Google Speech Commands KWS, MFCC 8x4",
                           tokenizer_mode="banded")
    X, y, names = _load_synth(max_per_class, seed)
    return make_splits("voice", "SYNTH", names, X, y, seed=seed,
                       description="SYNTH keyword tones (real corpus absent), MFCC 8x4",
                       tokenizer_mode="banded")
