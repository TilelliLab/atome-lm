"""atome_llm.core.router — per-token soft router with ternary weights.

A `TernaryLinear(d_model, n_pathways)` followed by softmax over the
pathway axis. Per-token distribution; the surrounding block uses it to
mix pathway outputs and (at inference) to skip pathways with low maximum
weight across the batch.

The router's per-token entropy is the metacognition signal: high entropy
on out-of-domain inputs, low on in-domain. No uncertainty-specific
training required — it's a property of the routing structure.
"""
from __future__ import annotations

import torch
from torch import Tensor, nn

from atome_llm.core.ternary_linear import TernaryLinear


class Router(nn.Module):
    def __init__(self, d_model: int, n_pathways: int,
                 quantizer: str = "ternary") -> None:
        super().__init__()
        self.d_model = d_model
        self.n_pathways = n_pathways
        self.proj = TernaryLinear(d_model, n_pathways, quantizer=quantizer)

    def forward(self, x: Tensor) -> Tensor:
        """x: (B, L, d_model) → router weights (B, L, n_pathways), softmax-normalized."""
        return torch.softmax(self.proj(x), dim=-1)

    @torch.no_grad()
    def entropy(self, x: Tensor) -> Tensor:
        """Per-token entropy in nats. Shape (B, L)."""
        r = self.forward(x).clamp_min(1e-12)
        return -(r * r.log()).sum(dim=-1)
