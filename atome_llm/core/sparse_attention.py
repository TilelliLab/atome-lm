"""atome_llm.core.sparse_attention — top-k causal attention with ternary Q/K/V.

Single-head, causal, sparse. Each query attends to its top-k highest-
scoring past positions only; the rest contribute zero after softmax over
the masked-and-sparsified score matrix.

Sized so the C engine's static buffers fit comfortably on small MCUs:
ATOME_TOP_K=4 by default, ATOME_MAX_SEQ=32, ATOME_D_HEAD=16. KV cache is
proportional to seq_len × d_head and seq_len × d_model — a few KB at the
defaults, fine for ESP32-class targets.
"""
from __future__ import annotations

import math

import torch
from torch import Tensor, nn

from atome_llm.core.ternary_linear import TernaryLinear


class SparseCausalAttention(nn.Module):
    def __init__(self, d_model: int, d_head: int = 16, top_k: int = 4,
                 quantizer: str = "ternary") -> None:
        super().__init__()
        self.d_model = d_model
        self.d_head = d_head
        self.top_k = top_k
        self.Wq = TernaryLinear(d_model, d_head, quantizer=quantizer)
        self.Wk = TernaryLinear(d_model, d_head, quantizer=quantizer)
        self.Wv = TernaryLinear(d_model, d_model, quantizer=quantizer)

    def forward(self, x: Tensor) -> Tensor:
        if x.dim() != 3:
            raise ValueError(f"expected (B, L, D), got shape {tuple(x.shape)}")
        B, L, D = x.shape
        if D != self.d_model:
            raise ValueError(f"d_model mismatch: {self.d_model} vs {D}")

        q = self.Wq(x)
        k = self.Wk(x)
        v = self.Wv(x)

        scale = 1.0 / math.sqrt(self.d_head)
        scores = (q @ k.transpose(-1, -2)) * scale

        causal = torch.ones(L, L, dtype=torch.bool, device=x.device).triu(1)
        scores = scores.masked_fill(causal, float("-inf"))

        k_eff = min(self.top_k, L)
        topk_vals, topk_idx = scores.topk(k_eff, dim=-1)

        sparse_scores = torch.full_like(scores, float("-inf"))
        sparse_scores.scatter_(-1, topk_idx, topk_vals)

        attn = torch.softmax(sparse_scores, dim=-1)
        attn = torch.nan_to_num(attn, nan=0.0)
        return attn @ v
