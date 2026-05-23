"""tests/test_mcu_block.py — MCUBlock shape, residual, router, infer skip."""
from __future__ import annotations

import math

import torch

from atome_llm.core.mcu_block import PATHWAY_NAMES, MCUBlock


def test_pathway_names_match_engine():
    assert PATHWAY_NAMES == ("local", "state", "sparse")


def test_block_shape_preserved():
    block = MCUBlock(d_model=32, d_head=8, top_k=4)
    x = torch.randn(2, 12, 32)
    y = block(x)
    assert y.shape == (2, 12, 32)


def test_block_gradient_flows():
    block = MCUBlock(d_model=32, d_head=8, top_k=4)
    x = torch.randn(1, 6, 32, requires_grad=True)
    block(x).sum().backward()
    assert x.grad is not None and torch.any(x.grad != 0)


def test_block_router_weights_per_token():
    block = MCUBlock(d_model=32, d_head=8, top_k=4)
    x = torch.randn(2, 12, 32)
    r = block.router_weights(x)
    assert r.shape == (2, 12, 3)
    sums = r.sum(dim=-1)
    assert torch.allclose(sums, torch.ones_like(sums), atol=1e-5)


def test_block_router_entropy_bounded_by_log3():
    block = MCUBlock(d_model=32, d_head=8, top_k=4)
    x = torch.randn(1, 8, 32)
    h = block.router_entropy(x)
    assert h.shape == (1, 8)
    assert torch.all(h <= math.log(3) + 1e-6)


def test_block_infer_with_high_threshold_is_identity():
    block = MCUBlock(d_model=32, d_head=8, top_k=4, skip_threshold=1.0 + 1e-3)
    block.eval()
    x = torch.randn(1, 6, 32)
    y = block.infer(x)
    assert torch.allclose(y, x)


def test_block_infer_default_threshold_active():
    torch.manual_seed(0)
    block = MCUBlock(d_model=32, d_head=8, top_k=4)
    block.eval()
    x = torch.randn(2, 8, 32)
    y = block.infer(x)
    assert not torch.allclose(y, x)
