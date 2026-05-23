"""tests/test_ternary_embedding.py — TernaryEmbedding shape & C-engine layout.

The most important assertion here is the SHAPE: weight must be
(vocab, d_model), not (d_model, vocab). The C engine reads
`embed.packed[tok * d + i]` — only the (vocab, d_model) row-major
layout produces the right bytes.
"""
from __future__ import annotations

import torch

from atome_llm.core.ternary import absmean_scale, ternary_signs
from atome_llm.core.ternary_embedding import TernaryEmbedding


def test_weight_shape_is_vocab_d_model():
    """Load-bearing for C-engine compatibility. Do NOT change to (d_model, vocab)."""
    emb = TernaryEmbedding(vocab_size=128, d_model=32)
    assert emb.weight.shape == (128, 32)


def test_forward_indexes_correctly():
    emb = TernaryEmbedding(vocab_size=64, d_model=16)
    ids = torch.tensor([[3, 7, 7, 0]], dtype=torch.long)
    out = emb(ids)
    assert out.shape == (1, 4, 16)
    # The two id=7 positions should produce identical vectors
    assert torch.allclose(out[0, 1], out[0, 2])
    # id=3 must differ from id=0 with overwhelming probability
    assert not torch.allclose(out[0, 0], out[0, 3])


def test_gradient_flows_to_shadow_weight():
    emb = TernaryEmbedding(vocab_size=32, d_model=8)
    ids = torch.tensor([[1, 2, 3]], dtype=torch.long)
    emb(ids).sum().backward()
    assert emb.weight.grad is not None
    assert torch.any(emb.weight.grad != 0)


def test_trits_layout_matches_packing_order():
    """Bit-packing convention: the i-th flattened element of trits()
    encodes the trit at position i in the packed byte stream. With
    weight shape (vocab, d_model), index `tok * d_model + i` corresponds
    to weight[tok, i] — exactly the offset the C engine uses."""
    vocab, d = 17, 5
    emb = TernaryEmbedding(vocab_size=vocab, d_model=d)
    trits = emb.trits().numpy()
    flat = trits.flatten()
    assert flat.shape == (vocab * d,)
    for tok in range(vocab):
        for i in range(d):
            assert flat[tok * d + i] == trits[tok, i]


def test_scale_is_zero_dim_tensor():
    emb = TernaryEmbedding(vocab_size=32, d_model=8)
    s = emb.scale()
    assert s.dim() == 0
    assert s.item() > 0
