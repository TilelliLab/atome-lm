"""tests/test_atome_lm.py — AtomeLM forward, loss, generate, entropy, config."""
from __future__ import annotations

import math

import torch

from atome_llm.core.atome_lm import AtomeLM


def test_lm_forward_shape():
    m = AtomeLM(vocab_size=256, d_model=32, n_layers=2, d_head=8, top_k=4)
    ids = torch.randint(0, 256, (2, 16))
    logits = m(ids)
    assert logits.shape == (2, 16, 256)


def test_lm_loss_and_backward():
    m = AtomeLM(vocab_size=256, d_model=32, n_layers=2, d_head=8, top_k=4)
    ids = torch.randint(0, 256, (2, 16))
    loss = m.loss(ids[:, :-1], ids[:, 1:])
    assert loss.dim() == 0
    assert torch.isfinite(loss)
    loss.backward()


def test_lm_generate_extends_sequence():
    m = AtomeLM(vocab_size=256, d_model=32, n_layers=2, d_head=8, top_k=4)
    ids = torch.randint(0, 256, (1, 8))
    out = m.generate(ids, n_new_tokens=4, max_seq=16)
    assert out.shape == (1, 12)


def test_lm_router_entropies_per_layer():
    m = AtomeLM(vocab_size=256, d_model=32, n_layers=3, d_head=8, top_k=4)
    ids = torch.randint(0, 256, (2, 12))
    ents = m.router_entropies(ids)
    assert len(ents) == 3
    for e in ents:
        assert e.shape == (2, 12)
        assert torch.all(e >= -1e-6)
        assert torch.all(e <= math.log(3) + 1e-6)


def test_lm_config_dict_matches_engine_keys():
    m = AtomeLM(vocab_size=256, d_model=32, n_layers=2, d_head=8, top_k=4, kernel_size=5)
    cfg = m.config
    expected_keys = {"vocab_size", "d_model", "n_layers", "d_head", "top_k",
                     "kernel_size", "n_pathways"}
    assert set(cfg.keys()) == expected_keys
    assert cfg["n_pathways"] == 3


def test_lm_parameter_count_grows_with_layers():
    small = AtomeLM(d_model=32, n_layers=1, d_head=8, top_k=4).parameter_count()
    big = AtomeLM(d_model=32, n_layers=4, d_head=8, top_k=4).parameter_count()
    assert big > small
