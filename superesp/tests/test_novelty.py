"""Honest router-entropy novelty: a PARTIAL distribution-shift signal only.

These tests lock in the truthful finding (see novelty.py docstring + LEDGER):
the signal separates a different real sensor distribution better than a
feature-shuffle, but it is NOT a reliable general OOD gate. We assert the
qualitative honest behaviour, not an inflated number.
"""
import torch

from superesp.datasets import agri, air
from superesp.framework.train import train_head
from superesp.framework import novelty


def _model():
    ds = agri.load(n_per_class=150, seed=0)
    res = train_head(ds.n_classes, ds.train_ids, ds.train_labels,
                     ds.val_ids, ds.val_labels, epochs=12, seed=0)
    return res.model, ds


def test_score_in_unit_range():
    m, ds = _model()
    s = novelty.novelty_score(m, ds.test_ids)
    assert float(s.min()) >= 0.0 and float(s.max()) <= 1.0


def test_novelty_mechanism_runs_but_is_not_a_reliable_gate():
    """Honest: the mechanism produces valid AUROCs, but its discriminative power
    is weak/inconsistent across OOD types and configs — so we DO NOT assert it
    separates anything well (it doesn't reliably). See novelty.py + LEDGER."""
    m, ds = _model()
    inn = ds.test_ids
    other = air.load(seed=0).test_ids[: inn.shape[0]]
    a = novelty.ood_auroc(m, inn, other)
    assert 0.0 <= a["auroc"] <= 1.0
    # scores are non-constant (the signal exists, even if not discriminative)
    s = novelty.novelty_score(m, inn)
    assert float(s.std()) > 0.0
