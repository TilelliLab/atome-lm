"""tests/test_ternary_linear.py — TernaryLinear shape, forward, gradient, infer parity."""
from __future__ import annotations

import torch

from atome_llm.core.ternary_linear import TernaryLinear


def test_forward_shape():
    layer = TernaryLinear(in_features=16, out_features=8)
    x = torch.randn(2, 5, 16)
    y = layer(x)
    assert y.shape == (2, 5, 8)


def test_gradient_flows_to_shadow_weight():
    layer = TernaryLinear(8, 4)
    x = torch.randn(1, 8)
    layer(x).sum().backward()
    assert layer.weight.grad is not None
    assert torch.any(layer.weight.grad != 0)


def test_infer_matches_forward_within_ste_tolerance():
    """Inference path uses int8 trits + scalar alpha; forward uses STE-shimmed
    ternarized weight. Numerically equal up to floating-point noise."""
    layer = TernaryLinear(8, 4)
    x = torch.randn(2, 8)
    with torch.no_grad():
        a = layer(x)
    b = layer.infer(x)
    assert torch.allclose(a, b, atol=1e-5)


def test_trits_and_scale_shape():
    layer = TernaryLinear(16, 8)
    assert layer.trits().shape == (8, 16)
    assert layer.trits().dtype == torch.int8
    assert layer.scale().dim() == 0
