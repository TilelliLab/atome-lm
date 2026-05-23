"""tests/test_vanilla_baseline.py — sanity tests on the vanilla baseline.

Pretty unsurprising: forward shape, loss differentiable, generate works,
parameter_count matches what you'd expect.
"""
from __future__ import annotations

import pytest
import torch

from atome_llm.baselines.vanilla_transformer import (
    VanillaTransformer,
    matched_param_config,
)


def test_forward_shape():
    m = VanillaTransformer(d_model=32, n_layers=2, n_heads=4, max_seq=16)
    ids = torch.randint(0, 256, (2, 8))
    logits = m(ids)
    assert logits.shape == (2, 8, 256)


def test_loss_finite_and_differentiable():
    m = VanillaTransformer(d_model=32, n_layers=2, n_heads=4, max_seq=16)
    ids = torch.randint(0, 256, (1, 8))
    loss = m.loss(ids[:, :-1], ids[:, 1:])
    assert torch.isfinite(loss)
    loss.backward()
    saw_grad = any(
        p.grad is not None and torch.isfinite(p.grad).all() and p.grad.abs().sum() > 0
        for p in m.parameters()
    )
    assert saw_grad


def test_max_seq_enforced():
    m = VanillaTransformer(d_model=32, n_layers=1, n_heads=4, max_seq=8)
    with pytest.raises(ValueError):
        m(torch.randint(0, 256, (1, 16)))


def test_generate_greedy_default():
    m = VanillaTransformer(d_model=32, n_layers=1, n_heads=4, max_seq=16).eval()
    prompt = torch.tensor([[1, 2, 3]], dtype=torch.long)
    out = m.generate(prompt, n_new_tokens=5)
    assert out.shape == (1, 8)


def test_generate_sampled_in_vocab():
    m = VanillaTransformer(d_model=32, n_layers=1, n_heads=4, max_seq=16).eval()
    prompt = torch.tensor([[1, 2, 3]], dtype=torch.long)
    g = torch.Generator().manual_seed(0)
    out = m.generate(prompt, n_new_tokens=20, temperature=1.0, generator=g)
    assert out.min().item() >= 0
    assert out.max().item() < 256


def test_parameter_count_grows_with_layers():
    m1 = VanillaTransformer(d_model=32, n_layers=1, n_heads=4, max_seq=16)
    m2 = VanillaTransformer(d_model=32, n_layers=4, n_heads=4, max_seq=16)
    assert m2.parameter_count() > m1.parameter_count()


def test_matched_param_config_lands_near_target():
    """Search for a 60K-param config — the err should be small (< 5K)."""
    cfg = matched_param_config(target_params=60_000, max_seq=64)
    assert abs(cfg["params"] - 60_000) < 5_000


def test_matched_param_config_lands_near_small_target():
    """Search for a 6K-param config (flash-fair vs ternary 60K)."""
    cfg = matched_param_config(target_params=6_000, max_seq=64)
    assert abs(cfg["params"] - 6_000) < 1_000


def test_invalid_d_model_n_heads():
    with pytest.raises(ValueError):
        VanillaTransformer(d_model=33, n_heads=4)


def test_config_dict_round_trips():
    m = VanillaTransformer(d_model=32, n_layers=2, n_heads=4, d_ff=128, max_seq=32)
    cfg = m.config
    m2 = VanillaTransformer(
        vocab_size=cfg["vocab_size"],
        d_model=cfg["d_model"],
        n_layers=cfg["n_layers"],
        n_heads=cfg["n_heads"],
        d_ff=cfg["d_ff"],
        max_seq=cfg["max_seq"],
    )
    assert m.parameter_count() == m2.parameter_count()
