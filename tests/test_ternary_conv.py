"""tests/test_ternary_conv.py — TernaryCausalConv1d shape, causality, infer parity."""
from __future__ import annotations

import torch

from atome_llm.core.ternary_conv import TernaryCausalConv1d


def test_shape_preserved():
    conv = TernaryCausalConv1d(channels=8, kernel_size=5)
    x = torch.randn(2, 12, 8)
    y = conv(x)
    assert y.shape == (2, 12, 8)


def test_causality_no_future_leakage():
    """Changing a future position must not affect any past output."""
    conv = TernaryCausalConv1d(channels=4, kernel_size=3)
    x = torch.randn(1, 10, 4)
    y1 = conv(x.clone()).detach()
    x2 = x.clone()
    x2[0, 7:] = 99.0
    y2 = conv(x2).detach()
    assert torch.allclose(y1[0, :7], y2[0, :7], atol=1e-5)


def test_gradient_flows():
    conv = TernaryCausalConv1d(channels=4, kernel_size=3)
    x = torch.randn(1, 5, 4, requires_grad=True)
    conv(x).sum().backward()
    assert conv.weight.grad is not None
    assert torch.any(conv.weight.grad != 0)


def test_infer_matches_forward():
    conv = TernaryCausalConv1d(channels=4, kernel_size=3)
    x = torch.randn(1, 8, 4)
    with torch.no_grad():
        a = conv(x)
    b = conv.infer(x)
    assert torch.allclose(a, b, atol=1e-5)
