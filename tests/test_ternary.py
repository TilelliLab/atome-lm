"""tests/test_ternary.py — quantizer + STE primitives."""
from __future__ import annotations

import torch

from atome_llm.core.ternary import (
    EPS,
    absmean_scale,
    ternarize,
    ternary_signs,
    ternary_values,
)


def test_absmean_scale_is_mean_abs_for_nonzero():
    w = torch.tensor([[-2.0, 1.0], [0.5, -1.5]])
    assert torch.allclose(absmean_scale(w), torch.tensor((2.0 + 1.0 + 0.5 + 1.5) / 4))


def test_absmean_scale_clamped_for_all_zero():
    """Float32 representation of EPS rounds slightly under the literal value;
    accept the clamped value if it is within an ULP of EPS."""
    w = torch.zeros(3, 4)
    assert absmean_scale(w).item() >= EPS - 1e-7


def test_ternarize_values_in_three_clusters():
    torch.manual_seed(0)
    w = torch.randn(64, 64) * 0.5
    out = ternarize(w)
    alpha = absmean_scale(w).item()
    unique = torch.unique(out.detach().round(decimals=4))
    assert unique.numel() <= 3
    for v in unique.tolist():
        assert abs(abs(v) - alpha) < 1e-4 or abs(v) < 1e-4


def test_ternarize_ste_gradient_is_identity():
    w = torch.randn(8, 8, requires_grad=True)
    ternarize(w).sum().backward()
    assert torch.allclose(w.grad, torch.ones_like(w))


def test_ternary_signs_int8_in_minus_one_zero_one():
    w = torch.randn(32, 32)
    s = ternary_signs(w)
    assert s.dtype == torch.int8
    assert torch.all((s == -1) | (s == 0) | (s == 1))


def test_ternary_values_consistent_with_ternarize_forward():
    w = torch.randn(16, 16)
    a = ternary_values(w)
    b = ternarize(w).detach()
    assert torch.allclose(a, b, atol=1e-6)
