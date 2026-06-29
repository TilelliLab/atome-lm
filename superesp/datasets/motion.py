"""superesp.datasets.motion — SuperESP-Motion: gesture/activity recognition.

Tries REAL data first (UCI HAR, downloaded to superesp/.data/har.zip) using a
32-feature slice of its 561 precomputed inertial features; falls back to SYNTH
accelerometer patterns. `source` records which loaded.

HAR classes: WALKING, WALKING_UPSTAIRS, WALKING_DOWNSTAIRS, SITTING, STANDING,
LAYING. Delta-inference sweet spot (correlated motion stream).
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np

from superesp.datasets import Dataset, make_splits
from superesp.framework.config import MAX_SEQ

_ZIP = Path(__file__).resolve().parents[1] / ".data" / "har.zip"
HAR_CLASSES = ["walking", "upstairs", "downstairs", "sitting", "standing", "laying"]
SYNTH_CLASSES = ["idle", "walk", "tap", "shake", "fall"]
N_FEAT = 30


def _read_har_txt(zf: zipfile.ZipFile, name: str) -> np.ndarray:
    with zf.open(name) as f:
        return np.loadtxt(f)


def _pick(names: list[str], leaf: str) -> str | None:
    """Match the canonical 'train/X_train.txt' style path, excluding the macOS
    resource forks (__MACOSX/._*) and Inertial-Signals files (body_*, total_*)."""
    cands = [
        n for n in names
        if n.endswith("/" + leaf)
        and "__MACOSX" not in n
        and "Inertial" not in n
    ]
    return cands[0] if cands else None


def _load_pair(zf, names):
    xtr, ytr = _pick(names, "X_train.txt"), _pick(names, "y_train.txt")
    xte, yte = _pick(names, "X_test.txt"), _pick(names, "y_test.txt")
    if not all([xtr, ytr, xte, yte]):
        return None
    Xtr = _read_har_txt(zf, xtr); ytr_ = _read_har_txt(zf, ytr)
    Xte = _read_har_txt(zf, xte); yte_ = _read_har_txt(zf, yte)
    return Xtr, ytr_, Xte, yte_


def _load_real(seed: int):
    if not _ZIP.exists():
        return None
    try:
        import io
        with zipfile.ZipFile(_ZIP) as outer:
            names = outer.namelist()
            pair = _load_pair(outer, names)
            if pair is None:
                inner = [n for n in names if n.endswith(".zip") and "__MACOSX" not in n]
                if not inner:
                    return None
                with outer.open(inner[0]) as fz:
                    with zipfile.ZipFile(io.BytesIO(fz.read())) as iz:
                        pair = _load_pair(iz, iz.namelist())
                        if pair is None:
                            return None
                        Xtr, ytr_, Xte, yte_ = pair
            else:
                Xtr, ytr_, Xte, yte_ = pair
        Xfull = np.vstack([Xtr, Xte])
        # Select the N_FEAT highest-VARIANCE of the 561 HAR features — the most
        # informative/active ones (vs the first-30 redundant tBodyAcc). Variance
        # is unsupervised (no labels), so this is a standard leak-free preprocessing.
        k = min(N_FEAT, MAX_SEQ)
        var = Xfull.var(axis=0)
        cols = np.sort(np.argsort(var)[::-1][:k])
        X = Xfull[:, cols]
        y = np.concatenate([ytr_, yte_]).astype(int) - 1  # labels 1..6 -> 0..5
        # HAR has 6 activity classes; guard against unexpected label ranges.
        if X.ndim != 2 or y.ndim != 1 or X.shape[0] != y.shape[0]:
            return None
        if y.min() < 0 or y.max() >= len(HAR_CLASSES):
            return None
        return X, y, HAR_CLASSES
    except Exception:
        return None


def _synth_window(rng, kind: str) -> np.ndarray:
    """(N_FEAT,) accel feature window."""
    t = np.linspace(0, 1, N_FEAT)
    if kind == "idle":
        x = rng.normal(0, 0.05, N_FEAT)
    elif kind == "walk":
        x = 0.6 * np.sin(2 * np.pi * 2 * t) + rng.normal(0, 0.1, N_FEAT)
    elif kind == "tap":
        x = rng.normal(0, 0.05, N_FEAT); p = rng.integers(2, N_FEAT - 2); x[p] += rng.uniform(2, 4)
    elif kind == "shake":
        x = 1.2 * np.sin(2 * np.pi * rng.uniform(6, 10) * t) + rng.normal(0, 0.2, N_FEAT)
    elif kind == "fall":
        x = rng.normal(0, 0.1, N_FEAT); p = rng.integers(3, N_FEAT - 6)
        x[p] += rng.uniform(3, 5); x[p + 1:p + 4] -= rng.uniform(1, 2)  # impact + freefall
    return x


def _load_synth(n_per_class: int, seed: int):
    rng = np.random.default_rng(seed)
    X, y = [], []
    for ci, kind in enumerate(SYNTH_CLASSES):
        for _ in range(n_per_class):
            X.append(_synth_window(rng, kind)); y.append(ci)
    return np.asarray(X), np.asarray(y), SYNTH_CLASSES


def load(n_per_class: int = 500, seed: int = 0) -> Dataset:
    real = _load_real(seed)
    if real is not None:
        X, y, names = real
        return make_splits("motion", "REAL", names, X, y, seed=seed,
                           description="UCI HAR, 30-feature inertial slice")
    X, y, names = _load_synth(n_per_class, seed)
    return make_splits("motion", "SYNTH", names, X, y, seed=seed,
                       description="SYNTH accelerometer gestures (UCI HAR absent)")
