"""atome_llm.core.ternary — BitNet b1.58 style ternary weights with STE.

Per-tensor AbsMean rescaling. The forward pass sees ternarized values in
{-alpha, 0, +alpha}; the backward pass uses the straight-through
estimator (gradients flow through the round/clamp as identity into a
FP32 shadow weight).

The C engine consumes per-tensor ternary weights only. Per-row scale is
intentionally absent here — it would require C-side changes and break
the bit-exact-parity contract this project rests on.
"""
from __future__ import annotations

import torch
from torch import Tensor


EPS = 1e-5


def absmean_scale(w: Tensor) -> Tensor:
    """Per-tensor scalar alpha = mean(|W|), clamped away from zero."""
    return w.abs().mean().clamp(min=EPS)


def absmean_scale_per_row(w: Tensor) -> Tensor:
    """Per-output-row alpha for a 2-D weight matrix (out, in).

    Returns shape (out, 1) so the result broadcasts against w. Each row
    gets its own dynamic range — research-side only; the MCU C engine
    consumes per-tensor scales. Used at >MCU scale where the gain
    justifies storing one extra float per output channel.
    """
    if w.dim() != 2:
        raise ValueError(f"absmean_scale_per_row expects 2-D weight, got shape {tuple(w.shape)}")
    return w.abs().mean(dim=1, keepdim=True).clamp(min=EPS)


def ternarize(w: Tensor) -> Tensor:
    """Ternarize w to values in {-alpha, 0, +alpha} with STE.

    Forward:  round(w / alpha).clamp(-1, 1) * alpha
    Backward: identity to w (straight-through)
    """
    alpha = absmean_scale(w)
    w_q = torch.round(w / alpha).clamp_(-1.0, 1.0) * alpha
    return w + (w_q - w).detach()


def ternary_values(w: Tensor) -> Tensor:
    """Ternarized tensor as a plain (no-grad) tensor — for inspection / export."""
    with torch.no_grad():
        alpha = absmean_scale(w)
        return torch.round(w / alpha).clamp_(-1.0, 1.0) * alpha


def ternary_signs(w: Tensor) -> Tensor:
    """Just the {-1, 0, +1} trits as int8, without the scale.

    Storage form for export. The C engine packs four trits per byte
    using encoding 00=0, 01=+1, 11=-1.
    """
    with torch.no_grad():
        alpha = absmean_scale(w)
        return torch.round(w / alpha).clamp_(-1.0, 1.0).to(torch.int8)
