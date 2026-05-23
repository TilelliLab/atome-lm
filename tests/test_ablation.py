"""tests/test_ablation.py — disabling a pathway must not break training."""
from __future__ import annotations

import pytest
import torch

from atome_llm.core.atome_lm import AtomeLM
from atome_llm.core.mcu_block import PATHWAY_NAMES


@pytest.mark.parametrize("disable", [("local",), ("state",), ("sparse",),
                                     ("local", "state"), ("state", "sparse")])
def test_ablated_model_trains(disable):
    torch.manual_seed(0)
    m = AtomeLM(vocab_size=32, d_model=16, n_layers=2, d_head=8, top_k=4,
                disable_pathways=disable)
    ids = torch.randint(0, 32, (2, 8))
    loss = m.loss(ids[:, :-1], ids[:, 1:])
    loss.backward()
    assert torch.isfinite(loss)
    assert any(p.grad is not None and p.grad.abs().sum() > 0 for p in m.parameters())


def test_router_size_matches_active_pathways():
    m = AtomeLM(vocab_size=32, d_model=16, n_layers=1,
                disable_pathways=("local",))
    assert m.blocks[0].router.n_pathways == 2

    m2 = AtomeLM(vocab_size=32, d_model=16, n_layers=1,
                 disable_pathways=("local", "state"))
    assert m2.blocks[0].router.n_pathways == 1


def test_disable_unknown_pathway_raises():
    with pytest.raises(ValueError):
        AtomeLM(vocab_size=32, d_model=16, n_layers=1,
                disable_pathways=("ffn",))


def test_disable_all_pathways_raises():
    with pytest.raises(ValueError):
        AtomeLM(vocab_size=32, d_model=16, n_layers=1,
                disable_pathways=PATHWAY_NAMES)


def test_param_count_drops_with_disabled_pathway():
    full = AtomeLM(vocab_size=32, d_model=16, n_layers=2)
    no_sparse = AtomeLM(vocab_size=32, d_model=16, n_layers=2,
                        disable_pathways=("sparse",))
    assert no_sparse.parameter_count() < full.parameter_count()
