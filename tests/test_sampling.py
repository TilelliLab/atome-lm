"""tests/test_sampling.py — temperature / top-p / top-k sampling in generate.

Greedy default (`temperature=0`) must remain identical to the prior
argmax behaviour so the parity tests stay valid. Sampling paths must
respect the truncation rules and be reproducible under a torch Generator.
"""
from __future__ import annotations

import pytest
import torch

from atome_llm.core.atome_lm import AtomeLM


def _model(seed: int = 0) -> AtomeLM:
    torch.manual_seed(seed)
    return AtomeLM(vocab_size=32, d_model=16, n_layers=2, d_head=8, top_k=4)


def test_greedy_default_matches_argmax():
    model = _model()
    prompt = torch.tensor([[1, 2, 3]], dtype=torch.long)
    a = model.generate(prompt, n_new_tokens=5, max_seq=16)
    b = model.generate(prompt, n_new_tokens=5, max_seq=16, temperature=0.0)
    assert torch.equal(a, b)


def test_temperature_invalid_raises():
    model = _model()
    prompt = torch.tensor([[1]], dtype=torch.long)
    with pytest.raises(ValueError):
        model.generate(prompt, n_new_tokens=1, temperature=-0.1)


def test_top_p_invalid_raises():
    model = _model()
    prompt = torch.tensor([[1]], dtype=torch.long)
    with pytest.raises(ValueError):
        model.generate(prompt, n_new_tokens=1, temperature=1.0, top_p=0.0)
    with pytest.raises(ValueError):
        model.generate(prompt, n_new_tokens=1, temperature=1.0, top_p=1.1)


def test_top_k_invalid_raises():
    model = _model()
    prompt = torch.tensor([[1]], dtype=torch.long)
    with pytest.raises(ValueError):
        model.generate(prompt, n_new_tokens=1, temperature=1.0, top_k=0)


def test_sampling_with_seed_is_reproducible():
    model = _model()
    prompt = torch.tensor([[1, 2, 3]], dtype=torch.long)
    g1 = torch.Generator().manual_seed(123)
    g2 = torch.Generator().manual_seed(123)
    a = model.generate(prompt, n_new_tokens=8, temperature=1.0, generator=g1)
    b = model.generate(prompt, n_new_tokens=8, temperature=1.0, generator=g2)
    assert torch.equal(a, b)


def test_sampling_can_diverge_from_greedy():
    """A high-temperature sample must be able to differ from argmax.
    Tries a few seeds — only requires SOME divergence to exist."""
    model = _model(seed=42)
    prompt = torch.tensor([[1, 2, 3, 4]], dtype=torch.long)
    greedy = model.generate(prompt, n_new_tokens=12, temperature=0.0)
    diverged = False
    for s in range(10):
        g = torch.Generator().manual_seed(s)
        sampled = model.generate(
            prompt, n_new_tokens=12, temperature=2.0, generator=g
        )
        if not torch.equal(greedy, sampled):
            diverged = True
            break
    assert diverged, "high-temp sampling produced argmax for 10 seeds"


def test_top_k_one_equals_greedy():
    """top_k=1 with any temperature collapses to argmax."""
    model = _model()
    prompt = torch.tensor([[1, 2, 3]], dtype=torch.long)
    g = torch.Generator().manual_seed(0)
    greedy = model.generate(prompt, n_new_tokens=6, temperature=0.0)
    sampled = model.generate(
        prompt, n_new_tokens=6, temperature=1.5, top_k=1, generator=g
    )
    assert torch.equal(greedy, sampled)


def test_top_p_very_small_equals_greedy():
    """top_p just above 0 keeps only the argmax token in the nucleus."""
    model = _model()
    prompt = torch.tensor([[1, 2, 3]], dtype=torch.long)
    g = torch.Generator().manual_seed(0)
    greedy = model.generate(prompt, n_new_tokens=6, temperature=0.0)
    sampled = model.generate(
        prompt, n_new_tokens=6, temperature=1.0, top_p=1e-6, generator=g
    )
    assert torch.equal(greedy, sampled)


def test_sampled_tokens_in_vocab():
    model = _model()
    prompt = torch.tensor([[1, 2, 3]], dtype=torch.long)
    g = torch.Generator().manual_seed(0)
    out = model.generate(prompt, n_new_tokens=20, temperature=1.0, generator=g)
    assert out.min().item() >= 0
    assert out.max().item() < model.vocab_size
