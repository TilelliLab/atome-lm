"""superesp.datasets.csv_head — bring-your-own-CSV custom head.

The usefulness/reproducibility lever: a user logs their OWN ESP32 sensor windows
to a CSV (one row = one window of <= MAX_SEQ features + a label column) and gets
a trained, bit-exact, attestable ATOMECL01 head with NO ML expertise. This is
the open, auditable equivalent of an Edge-Impulse classifier.

CSV format:
    feat_0,feat_1,...,feat_k,<label_col>
    0.12,  0.98, ..., 3.4,   irrigate
    ...
Any non-label column is a feature (k+1 features, must be <= MAX_SEQ). The label
column holds class names (strings or ints); classes are inferred from the data.
"""
from __future__ import annotations

import csv as _csv
from pathlib import Path

import numpy as np

from superesp.datasets import Dataset, make_splits
from superesp.framework.config import MAX_SEQ, MAX_CLASSES


def load_csv(path, label_col: str = "label", seed: int = 0,
             name: str | None = None) -> Dataset:
    path = Path(path)
    rows, labels = [], []
    with path.open() as f:
        reader = _csv.DictReader(f)
        if label_col not in reader.fieldnames:
            raise ValueError(f"label column {label_col!r} not in {reader.fieldnames}")
        feat_cols = [c for c in reader.fieldnames if c != label_col]
        if not feat_cols:
            raise ValueError("no feature columns found")
        if len(feat_cols) > MAX_SEQ:
            raise ValueError(f"{len(feat_cols)} features > MAX_SEQ={MAX_SEQ}; "
                             "aggregate/downsample the window first")
        for r in reader:
            rows.append([float(r[c]) for c in feat_cols])
            labels.append(r[label_col])
    if not rows:
        raise ValueError("empty CSV")

    X = np.asarray(rows, dtype=np.float64)
    classes = sorted(set(labels), key=lambda s: (str(s)))
    if len(classes) > MAX_CLASSES:
        raise ValueError(f"{len(classes)} classes > MAX_CLASSES={MAX_CLASSES}")
    if len(classes) < 2:
        raise ValueError("need >= 2 classes")
    cls_idx = {c: i for i, c in enumerate(classes)}
    y = np.asarray([cls_idx[l] for l in labels], dtype=np.int64)

    return make_splits(name or path.stem, "REAL", [str(c) for c in classes],
                       X, y, seed=seed,
                       description=f"user CSV {path.name}: {X.shape[1]} feats, {len(classes)} classes")
