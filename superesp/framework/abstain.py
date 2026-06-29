"""superesp.framework.abstain — refuse-when-unsure for edge classifiers.

Concept ported from our LLM-reliability stack (Reasoner / Athar / Yaz): instead
of always emitting the argmax class, the head ABSTAINS when its confidence is
low. On an always-on sensor device this is the difference between a useful
alarm and a false-alarm generator. The signal is the softmax margin
(top1 - top2 probability); abstain when margin < threshold.

We report the risk-coverage curve and AURC (area under the risk-coverage curve)
on the HELD-OUT test split: lower AURC = the confidence signal ranks errors well.
An oracle (perfect confidence) and a random baseline bracket it.
"""
from __future__ import annotations

import numpy as np
import torch
from torch import Tensor


def margins(probs: Tensor) -> Tensor:
    """top1 - top2 softmax probability, per sample. (N,)."""
    top2 = probs.topk(2, dim=-1).values
    return (top2[:, 0] - top2[:, 1]).clamp(min=0.0)


def decide(probs: Tensor, threshold: float) -> Tensor:
    """Returns predicted class, or -1 (ABSTAIN) where margin < threshold."""
    pred = probs.argmax(dim=-1)
    m = margins(probs)
    return torch.where(m >= threshold, pred, torch.full_like(pred, -1))


def risk_coverage(probs: Tensor, labels: Tensor) -> dict:
    """Risk-coverage curve sorted by confidence (margin), + AURC.

    coverage = fraction of samples we answer; risk = error rate among answered.
    """
    m = margins(probs).numpy()
    pred = probs.argmax(dim=-1).numpy()
    correct = (pred == labels.numpy()).astype(np.float64)
    order = np.argsort(-m)  # most confident first
    correct_sorted = correct[order]
    n = len(correct_sorted)
    cum_correct = np.cumsum(correct_sorted)
    k = np.arange(1, n + 1)
    coverage = k / n
    risk = 1.0 - cum_correct / k
    aurc = float(np.trapz(risk, coverage))  # area under risk-coverage curve

    # Oracle: rank all correct first -> minimal achievable AURC for this acc.
    oc = np.sort(correct)[::-1]
    oracle_risk = 1.0 - np.cumsum(oc) / k
    oracle_aurc = float(np.trapz(oracle_risk, coverage))
    base_acc = float(correct.mean())
    return {
        "aurc": aurc,
        "oracle_aurc": oracle_aurc,
        "random_aurc": float(1.0 - base_acc),  # flat risk = error rate
        "base_acc": base_acc,
        "coverage": coverage.tolist(),
        "risk": risk.tolist(),
    }


def coverage_at_risk(probs: Tensor, labels: Tensor, max_risk: float) -> float:
    """Largest coverage achievable while keeping risk <= max_risk."""
    rc = risk_coverage(probs, labels)
    cov = np.asarray(rc["coverage"])
    risk = np.asarray(rc["risk"])
    ok = risk <= max_risk
    return float(cov[ok].max()) if ok.any() else 0.0
