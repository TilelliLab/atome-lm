"""tests/test_router.py — Router shape, simplex property, entropy bound."""
from __future__ import annotations

import math

import torch

from atome_llm.core.router import Router


def test_router_output_shape():
    r = Router(d_model=32, n_pathways=3)
    x = torch.randn(2, 12, 32)
    out = r(x)
    assert out.shape == (2, 12, 3)


def test_router_output_is_a_simplex():
    r = Router(d_model=32, n_pathways=3)
    x = torch.randn(2, 12, 32)
    out = r(x)
    assert torch.all(out >= 0)
    sums = out.sum(dim=-1)
    assert torch.allclose(sums, torch.ones_like(sums), atol=1e-5)


def test_router_entropy_in_valid_range():
    r = Router(d_model=32, n_pathways=3)
    x = torch.randn(2, 12, 32)
    h = r.entropy(x)
    assert h.shape == (2, 12)
    assert torch.all(h >= -1e-6)
    assert torch.all(h <= math.log(3) + 1e-6)


def test_router_gradient_flows():
    """Use a non-degenerate loss — `softmax(...).sum()` over the last
    axis is identically 1 and has zero gradient, so we square first."""
    r = Router(d_model=16, n_pathways=3)
    x = torch.randn(1, 4, 16)
    (r(x) ** 2).sum().backward()
    assert r.proj.weight.grad is not None
    assert torch.any(r.proj.weight.grad != 0)
