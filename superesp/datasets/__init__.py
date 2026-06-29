"""superesp.datasets — real loaders + physically-grounded synthetic generators.

Each module exposes `load() -> Dataset`. Splitting + tokenizer fitting is
centralized here so every head follows the same leak-free protocol: tokenizer
is fit on TRAIN only; val selects the checkpoint; TEST is reported.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch

from superesp.framework.tokenize import FeatureTokenizer


@dataclass
class Dataset:
    name: str
    source: str  # "REAL" or "SYNTH" — stated in every results table
    class_names: list[str]
    train_ids: torch.Tensor
    train_labels: torch.Tensor
    val_ids: torch.Tensor
    val_labels: torch.Tensor
    test_ids: torch.Tensor
    test_labels: torch.Tensor
    tokenizer: FeatureTokenizer
    # Raw (untokenized) test windows kept for the delta-inference simulator,
    # which needs the continuous stream, not the byte tokens.
    test_X: np.ndarray
    description: str = ""
    # (T, C) layout for time-series heads whose features are a real temporal
    # stream — lets the delta-inference probe feed a *correlated* stream.
    # None for tabular heads (motion HAR / MFCC), where delta does not apply.
    stream_shape: tuple | None = None

    @property
    def n_classes(self) -> int:
        return len(self.class_names)


def make_splits(
    name: str,
    source: str,
    class_names: list[str],
    X: np.ndarray,
    y: np.ndarray,
    *,
    seed: int = 0,
    fracs: tuple[float, float, float] = (0.7, 0.15, 0.15),
    description: str = "",
    stream_shape: tuple | None = None,
    tokenizer_mode: str = "global",
) -> Dataset:
    """Stratified train/val/test split, tokenizer fit on TRAIN only."""
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.int64)
    rng = np.random.default_rng(seed)

    tr_idx, va_idx, te_idx = [], [], []
    for c in np.unique(y):
        idx = np.where(y == c)[0]
        rng.shuffle(idx)
        n = len(idx)
        n_tr = int(round(fracs[0] * n))
        n_va = int(round(fracs[1] * n))
        tr_idx += idx[:n_tr].tolist()
        va_idx += idx[n_tr : n_tr + n_va].tolist()
        te_idx += idx[n_tr + n_va :].tolist()
    rng.shuffle(tr_idx)
    rng.shuffle(va_idx)
    rng.shuffle(te_idx)

    tok = FeatureTokenizer.fit(X[tr_idx], mode=tokenizer_mode)  # TRAIN ONLY
    return Dataset(
        name=name,
        source=source,
        class_names=class_names,
        train_ids=tok.transform(X[tr_idx]),
        train_labels=torch.from_numpy(y[tr_idx]),
        val_ids=tok.transform(X[va_idx]),
        val_labels=torch.from_numpy(y[va_idx]),
        test_ids=tok.transform(X[te_idx]),
        test_labels=torch.from_numpy(y[te_idx]),
        tokenizer=tok,
        test_X=X[te_idx],
        description=description,
        stream_shape=stream_shape,
    )
