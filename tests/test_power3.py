"""tests/test_power3.py — Power-of-3 quantizer + AtomeLM with quantizer="power3"."""
from __future__ import annotations

import pytest
import torch

from atome_llm.core.atome_lm import AtomeLM
from atome_llm.core.power3 import (
    power3_codes,
    power3_codes_per_row,
    power3_quantize,
    power3_quantize_per_row,
    power3_round,
)
from atome_llm.core.ternary import absmean_scale_per_row


def test_power3_round_levels():
    """Boundaries: |w|<0.5 → 0; |w|<2 → 1; |w|<6 → 3; else → 9."""
    w = torch.tensor([0.0, 0.4, 0.5, 1.0, 1.99, 2.0, 5.99, 6.0, 9.0, 100.0])
    expected = torch.tensor([0.0, 0.0, 1.0, 1.0, 1.0, 3.0, 3.0, 9.0, 9.0, 9.0])
    assert torch.allclose(power3_round(w), expected)
    assert torch.allclose(power3_round(-w), -expected)


def test_power3_codes_in_set():
    rng = torch.Generator().manual_seed(0)
    w = torch.randn(64, 32, generator=rng)
    codes = power3_codes(w)
    allowed = {-9, -3, -1, 0, 1, 3, 9}
    unique = set(codes.unique().tolist())
    assert unique.issubset(allowed), f"got codes outside set: {unique - allowed}"


def test_power3_quantize_passes_gradient():
    w = torch.randn(8, 8, requires_grad=True)
    y = power3_quantize(w).sum()
    y.backward()
    assert w.grad is not None
    assert torch.isfinite(w.grad).all()
    assert w.grad.abs().sum() > 0


def test_power3_atome_lm_forward_and_backward():
    """An AtomeLM with quantizer='power3' trains end-to-end."""
    torch.manual_seed(0)
    m = AtomeLM(vocab_size=32, d_model=16, n_layers=2, d_head=8, top_k=4,
                quantizer="power3")
    ids = torch.randint(0, 32, (2, 8))
    loss = m.loss(ids[:, :-1], ids[:, 1:])
    assert torch.isfinite(loss)
    loss.backward()
    saw_grad = any(
        p.grad is not None and torch.isfinite(p.grad).all() and p.grad.abs().sum() > 0
        for p in m.parameters()
    )
    assert saw_grad


def test_power3_quantizer_propagates_to_all_layers():
    """quantizer='power3' must reach embed, conv, sparse Q/K/V, router, unembed."""
    m = AtomeLM(vocab_size=32, d_model=16, n_layers=1, d_head=8, top_k=4,
                quantizer="power3")
    assert m.embed.quantizer == "power3"
    assert m.unembed.quantizer == "power3"
    block = m.blocks[0]
    assert block.local.quantizer == "power3"
    assert block.sparse.Wq.quantizer == "power3"
    assert block.sparse.Wk.quantizer == "power3"
    assert block.sparse.Wv.quantizer == "power3"
    assert block.router.proj.quantizer == "power3"


def test_invalid_quantizer_raises():
    with pytest.raises(ValueError):
        AtomeLM(vocab_size=32, d_model=16, n_layers=1, quantizer="binary")


def test_power3_default_unchanged():
    """Default quantizer is 'ternary' — backwards compatible."""
    m = AtomeLM(vocab_size=32, d_model=16, n_layers=1)
    assert m.embed.quantizer == "ternary"
    assert m.unembed.quantizer == "ternary"


def test_power3_per_row_alpha_shape():
    """absmean_scale_per_row returns (out, 1) so it broadcasts row-wise."""
    torch.manual_seed(0)
    w = torch.randn(8, 16)
    a = absmean_scale_per_row(w)
    assert a.shape == (8, 1)
    assert (a > 0).all()


def test_power3_per_row_uses_distinct_scales():
    """Per-row alpha gives each output row its own dynamic range."""
    torch.manual_seed(0)
    # Build a weight with very different per-row magnitudes.
    w = torch.cat([torch.randn(4, 16) * 0.1, torch.randn(4, 16) * 5.0], dim=0)
    a = absmean_scale_per_row(w)
    assert a.flatten()[:4].max() < a.flatten()[4:].min(), \
        "per-row alpha should differ when row magnitudes differ"


def test_power3_per_row_codes_in_set():
    rng = torch.Generator().manual_seed(0)
    w = torch.randn(32, 16, generator=rng) * 2.0
    codes = power3_codes_per_row(w)
    allowed = {-9, -3, -1, 0, 1, 3, 9}
    unique = set(codes.unique().tolist())
    assert unique.issubset(allowed)


def test_power3_per_row_passes_gradient():
    w = torch.randn(8, 8, requires_grad=True)
    y = power3_quantize_per_row(w).sum()
    y.backward()
    assert w.grad is not None and torch.isfinite(w.grad).all()


def test_power3_pr_atome_lm_forward_and_backward():
    """An AtomeLM with quantizer='power3_pr' trains end-to-end."""
    torch.manual_seed(0)
    m = AtomeLM(vocab_size=32, d_model=16, n_layers=2, d_head=8, top_k=4,
                quantizer="power3_pr")
    ids = torch.randint(0, 32, (2, 8))
    loss = m.loss(ids[:, :-1], ids[:, 1:])
    assert torch.isfinite(loss)
    loss.backward()


def test_power3_pr_routes_conv_to_per_tensor():
    """Conv weights are (channels, 1, K) — depthwise — so per-row gracefully
    falls back to per-tensor power3 inside conv. Linear+embed stay per-row.
    """
    m = AtomeLM(vocab_size=32, d_model=16, n_layers=1, d_head=8, top_k=4,
                quantizer="power3_pr")
    assert m.embed.quantizer == "power3_pr"
    assert m.blocks[0].local.quantizer == "power3_pr"
    # All linears in the block should be in power3_pr too:
    assert m.blocks[0].sparse.Wq.quantizer == "power3_pr"


def test_power3_more_unique_levels_than_ternary():
    """Same weight matrix quantized two ways should yield more unique levels under power3."""
    torch.manual_seed(0)
    w = torch.randn(64, 64) * 2.0  # wide enough to use all power3 levels
    # Ternary: 3 levels {-α, 0, +α}
    from atome_llm.core.ternary import ternary_signs
    n_ternary = ternary_signs(w).unique().numel()
    # Power3: up to 7 levels {-9, -3, -1, 0, 1, 3, 9}
    n_power3 = power3_codes(w).unique().numel()
    assert n_ternary <= 3
    assert n_power3 > n_ternary
