"""atome_llm.core.ternary_linear — Linear layer with ternary weights.

Shadow FP32 parameter, ternarized on every forward pass via STE. Shape
convention matches torch.nn.Linear: weight is (out_features, in_features)
and forward is x @ W.t(). No bias — pre-LayerNorm absorbs that role.

Optional `quantizer="power3"` switches to {0, ±1, ±3, ±9} × α levels.
Default "ternary" preserves bit-exact parity with the C engine. Power-3
weights cannot currently be exported to ATOME01/02 — they need their own
on-disk format and a C-side decoder.
"""
from __future__ import annotations

import torch
from torch import Tensor, nn

from atome_llm.core.power3 import power3_quantize, power3_quantize_per_row
from atome_llm.core.ternary import absmean_scale, ternarize, ternary_signs


_QUANTIZERS = {
    "ternary": ternarize,
    "power3":  power3_quantize,
    # Per-row power-3: one alpha per output row. Research-only — does
    # not export to the C engine (MCU buffer has one scale per weight tensor).
    "power3_pr": power3_quantize_per_row,
}


class TernaryLinear(nn.Module):
    def __init__(self, in_features: int, out_features: int,
                 quantizer: str = "ternary") -> None:
        super().__init__()
        if quantizer not in _QUANTIZERS:
            raise ValueError(
                f"quantizer must be one of {list(_QUANTIZERS)}, got {quantizer!r}"
            )
        self.in_features = in_features
        self.out_features = out_features
        self.quantizer = quantizer
        self._quant_fn = _QUANTIZERS[quantizer]
        w = torch.randn(out_features, in_features) * (1.0 / in_features ** 0.5)
        self.weight = nn.Parameter(w)

    def forward(self, x: Tensor) -> Tensor:
        return x @ self._quant_fn(self.weight).t()

    @torch.no_grad()
    def trits(self) -> Tensor:
        return ternary_signs(self.weight)

    @torch.no_grad()
    def scale(self) -> Tensor:
        return absmean_scale(self.weight)

    @torch.no_grad()
    def infer(self, x: Tensor) -> Tensor:
        """Inference forward identical to the C kernel: y = alpha * (x @ trits.t())."""
        trits = self.trits().to(x.dtype)
        return self.scale() * (x @ trits.t())
