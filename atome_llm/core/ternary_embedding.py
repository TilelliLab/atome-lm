"""atome_llm.core.ternary_embedding — index-style ternary embedding.

A token id maps to a row of a ternary (vocab, d_model) shadow matrix.
The forward path is a row-lookup, not a matmul — the C engine reads
the row at offset `tok * d_model` and multiplies by the per-tensor
scale, with no full one-hot matmul intermediate.

Shape is **(vocab, d_model)**, which is the row-major layout the
C engine expects when it does `embed.packed[tok * d + i]`. Using
TernaryLinear (which has shape `(out, in) = (d_model, vocab)`) would
silently produce a transposed binary that the engine reads as garbage.
"""
from __future__ import annotations

import torch
from torch import Tensor, nn

from atome_llm.core.power3 import power3_quantize, power3_quantize_per_row
from atome_llm.core.ternary import absmean_scale, ternarize, ternary_signs


# Embedding shadow weight is 2-D (vocab, d_model), so per-row alpha is
# valid here — one scale per token row. The C engine still expects
# per-tensor at export; power3_pr is research-only.
_QUANTIZERS = {
    "ternary": ternarize,
    "power3": power3_quantize,
    "power3_pr": power3_quantize_per_row,
}


class TernaryEmbedding(nn.Module):
    def __init__(self, vocab_size: int, d_model: int,
                 quantizer: str = "ternary") -> None:
        super().__init__()
        if quantizer not in _QUANTIZERS:
            raise ValueError(f"quantizer must be one of {list(_QUANTIZERS)}")
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.quantizer = quantizer
        self._quant_fn = _QUANTIZERS[quantizer]
        # Shadow weight in C-engine layout: (vocab, d_model).
        w = torch.randn(vocab_size, d_model) * (1.0 / d_model ** 0.5)
        self.weight = nn.Parameter(w)

    def forward(self, ids: Tensor) -> Tensor:
        """ids: (B, L) int64 → (B, L, d_model)."""
        if ids.dim() != 2:
            raise ValueError(f"expected (B, L) token ids, got shape {tuple(ids.shape)}")
        return self._quant_fn(self.weight)[ids]

    @torch.no_grad()
    def trits(self) -> Tensor:
        return ternary_signs(self.weight)

    @torch.no_grad()
    def scale(self) -> Tensor:
        return absmean_scale(self.weight)
