"""atome_llm.core.power3 — Power-of-3 quantization {0, ±1, ±3, ±9} × alpha.

Drop-in extension of the ternary quantizer. Same per-tensor AbsMean
rescaling, same straight-through gradient — just a wider level set.

Why these levels:
  - Plain ternary {-1, 0, +1}: 1.58 bits/weight, ~20-30% behind FP16.
  - Power-of-3 {0, ±1, ±3, ±9}: ~2.81 bits/weight (7 levels = log2(7)),
    closes a measurable fraction of the ternary→FP gap.
  - Powers of 3 are special on integer hardware: ×3 = (x<<1)+x and
    ×9 = (x<<3)+x. Two adds per multiply; no float ALU needed.

The 7 levels are integer-codeable in 3 bits, so future on-disk packing
can store 8 weights / 3 bytes = 3.0 bits/weight (vs 4 weights / 1 byte =
2.0 bits/weight for ternary). Roughly +50% storage overhead for ~10-15%
quality recovery — useful when flash budget allows.

Per-tensor only — engine compatibility constraint (same reason as
`ternary.py`).
"""
from __future__ import annotations

import torch
from torch import Tensor

from atome_llm.core.ternary import absmean_scale, absmean_scale_per_row


# Integer levels and the midpoint boundaries between them.
# |w_scaled| >= 0.5 → level 1; >= 2.0 → level 3; >= 6.0 → level 9.
_BOUNDARIES = (0.5, 2.0, 6.0)


def power3_round(w_scaled: Tensor) -> Tensor:
    """Round |w_scaled| to the nearest level in {0, 1, 3, 9}, preserve sign."""
    sign = torch.sign(w_scaled)
    aw = w_scaled.abs()
    levels = torch.zeros_like(aw)
    levels = torch.where(aw >= _BOUNDARIES[0], torch.ones_like(aw), levels)
    levels = torch.where(aw >= _BOUNDARIES[1], torch.full_like(aw, 3.0), levels)
    levels = torch.where(aw >= _BOUNDARIES[2], torch.full_like(aw, 9.0), levels)
    return sign * levels


def power3_quantize(w: Tensor) -> Tensor:
    """Quantize w to {0, ±α, ±3α, ±9α} with straight-through gradient."""
    alpha = absmean_scale(w)
    w_q = power3_round(w / alpha) * alpha
    return w + (w_q - w).detach()


def power3_codes(w: Tensor) -> Tensor:
    """Inference-time export codes in {-9, -3, -1, 0, 1, 3, 9} as int8."""
    with torch.no_grad():
        alpha = absmean_scale(w)
        return power3_round(w / alpha).to(torch.int8)


# Per-output-row alpha. Prior internal evidence: pow3 alone matched plain
# ternary; pow3 + per-row was the best ternary-class result, closing ~33%
# of the FP32→ternary gap at a ~10M-param scale. Research-only — the MCU C
# engine has no buffer for per-row alphas.
def power3_quantize_per_row(w: Tensor) -> Tensor:
    """Per-row {0, ±α_r, ±3α_r, ±9α_r} with STE. 2-D weights only."""
    alpha = absmean_scale_per_row(w)
    w_q = power3_round(w / alpha) * alpha
    return w + (w_q - w).detach()


def power3_codes_per_row(w: Tensor) -> Tensor:
    """Per-row int8 codes in {-9, -3, -1, 0, 1, 3, 9}."""
    with torch.no_grad():
        alpha = absmean_scale_per_row(w)
        return power3_round(w / alpha).to(torch.int8)
