"""superesp.framework.editable — add/remove classes ON-DEVICE, no retraining.

Most TinyML classifiers are frozen at flash time: teaching the device a new
gesture/command/state means re-collecting data, retraining, and re-flashing.
SuperESP can be EDITABLE: freeze the trained Atome backbone as a feature
extractor (its final-norm last-hidden state), and represent each class as a
PROTOTYPE centroid in that feature space. Adding a class = average a few example
feature vectors and store the centroid (a d_model float vector). Removing a
class = delete its centroid. Classification = nearest centroid + a margin-based
abstention. No weight updates, no re-flash — the only state that changes is a
tiny table of centroids (which can live in NVS/flash and be edited at runtime).

This is the on-device-editable, auditable edge classifier: every centroid is an
inspectable vector, and add/remove is a logged, reversible operation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import torch
from torch import Tensor

from superesp.framework.model import SuperESPHead


@dataclass
class PrototypeHead:
    backbone: SuperESPHead                 # weights used ONLY as a feature extractor
    centroids: dict = field(default_factory=dict)   # name -> (d_model,) tensor
    _order: list = field(default_factory=list)

    @torch.no_grad()
    def features(self, ids: Tensor) -> Tensor:
        self.backbone.eval()
        return self.backbone._last_hidden(ids)        # (B, d_model)

    @torch.no_grad()
    def add_class(self, name: str, support_ids: Tensor) -> None:
        """Create/replace a class prototype from a few labelled examples."""
        f = self.features(support_ids)                # (k, d)
        self.centroids[name] = f.mean(dim=0)
        if name not in self._order:
            self._order.append(name)

    def remove_class(self, name: str) -> None:
        self.centroids.pop(name, None)
        if name in self._order:
            self._order.remove(name)

    @torch.no_grad()
    def classify(self, ids: Tensor, abstain_margin: float = 0.10):
        """Nearest-centroid classify with margin abstention.
        Returns (labels list, margins (B,)). label is None where abstained."""
        if not self._order:
            raise RuntimeError("no classes registered")
        f = self.features(ids)                         # (B, d)
        C = torch.stack([self.centroids[n] for n in self._order], dim=0)  # (K, d)
        # negative squared L2 as similarity -> softmax for a calibrated margin
        d2 = ((f[:, None, :] - C[None, :, :]) ** 2).sum(-1)   # (B, K)
        probs = torch.softmax(-d2, dim=-1)
        top2 = probs.topk(min(2, probs.shape[1]), dim=-1)
        idx = top2.indices[:, 0]
        margin = (top2.values[:, 0] - top2.values[:, 1]) if probs.shape[1] > 1 \
                 else torch.ones(f.shape[0])
        labels = [self._order[int(i)] if m >= abstain_margin else None
                  for i, m in zip(idx.tolist(), margin.tolist())]
        return labels, margin

    @torch.no_grad()
    def accuracy(self, ids: Tensor, label_names: list) -> float:
        labels, _ = self.classify(ids, abstain_margin=0.0)  # force a decision
        return float(np.mean([p == t for p, t in zip(labels, label_names)]))
