"""superesp.framework.novelty — router-entropy novelty signal (PARTIAL, honest).

Atome's per-token router picks among 3 compute pathways; its entropy is a free
byproduct of the forward. HONEST MEASURED BEHAVIOUR (superesp tests + LEDGER):
it is a *partial* distribution-shift detector, NOT a general OOD guarantee:
  - other real sensor distribution: AUROC ~0.85  (works)
  - uniform-random input:           AUROC ~0.57  (weak)
  - feature-shuffle:                AUROC ~0.48  (chance)
  - all-zero / degenerate input:    AUROC ~0.09  (INVERTS — falsely confident!)
So do NOT rely on it as a safety OOD gate. The reliable "knows-when-unsure"
mechanism is the abstention margin (superesp/framework/abstain.py), which is
near-oracle on the working heads. Use novelty only as a supplementary
distribution-shift hint, fused with abstention.

novelty_score in [0,1]: mean router entropy across layers/positions / log(n_pathways).
"""
from __future__ import annotations

import math

import numpy as np
import torch
from torch import Tensor


def novelty_score(model, ids: Tensor) -> Tensor:
    """Per-sample novelty in [0,1] from mean router entropy. (B,)."""
    model.eval()
    with torch.no_grad():
        ents = model.base.router_entropies(ids)  # list of (B, L) per layer
    stacked = torch.stack(ents, dim=0)            # (n_layers, B, L)
    mean_ent = stacked.mean(dim=(0, 2))           # (B,)
    n_pathways = 3 - len(model.base.blocks[0].disabled)
    return (mean_ent / math.log(max(n_pathways, 2))).clamp(0, 1)


def ood_auroc(model, in_ids: Tensor, ood_ids: Tensor) -> dict:
    """How well novelty_score separates in-distribution from OOD inputs.

    AUROC of the score discriminating ood (positive) vs in-dist (negative).
    """
    s_in = novelty_score(model, in_ids).numpy()
    s_ood = novelty_score(model, ood_ids).numpy()
    scores = np.concatenate([s_in, s_ood])
    y = np.concatenate([np.zeros(len(s_in)), np.ones(len(s_ood))])
    # rank-based AUROC
    order = np.argsort(scores)
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, len(scores) + 1)
    n_pos, n_neg = y.sum(), (1 - y).sum()
    auroc = (ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return {"auroc": float(auroc),
            "mean_in": float(s_in.mean()), "mean_ood": float(s_ood.mean())}
