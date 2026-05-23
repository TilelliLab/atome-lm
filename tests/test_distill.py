"""tests/test_distill.py — cache round-trip + KL+CE blend + smoke train."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch

from atome_llm.core.atome_lm import AtomeLM
from atome_llm.distill import (
    RandomTeacher,
    UniformTeacher,
    chunks_from_text,
    distill_loss,
    distill_train,
    read_teacher_cache,
    write_teacher_cache,
)


def test_cache_round_trip(tmp_path: Path):
    rng = np.random.default_rng(0)
    chunks = rng.integers(0, 256, size=(8, 16)).astype(np.uint8)
    cache = tmp_path / "x.cache"
    teacher = RandomTeacher(seed=42)
    write_teacher_cache(cache, chunks, teacher)
    h, chunks_back, logits = read_teacher_cache(cache)
    assert h.n_chunks == 8 and h.seq_len == 16 and h.vocab_size == 256
    assert np.array_equal(np.asarray(chunks_back), chunks)
    assert logits.shape == (8, 16, 256)
    assert logits.dtype == np.float32


def test_distill_loss_pure_ce_equals_cross_entropy():
    """alpha=1 should match plain F.cross_entropy."""
    torch.manual_seed(0)
    s = torch.randn(2, 4, 32)
    t = torch.randn(2, 4, 32)
    y = torch.randint(0, 32, (2, 4))
    L_distill = distill_loss(s, t, y, alpha=1.0, temperature=1.0)
    from torch.nn import functional as F
    L_ce = F.cross_entropy(s.reshape(-1, 32), y.reshape(-1))
    assert torch.allclose(L_distill, L_ce, atol=1e-6)


def test_distill_loss_zero_kl_when_teacher_equals_student():
    """If teacher_logits == student_logits, KL term is 0."""
    torch.manual_seed(0)
    s = torch.randn(2, 4, 32)
    y = torch.randint(0, 32, (2, 4))
    from torch.nn import functional as F
    ce_only = F.cross_entropy(s.reshape(-1, 32), y.reshape(-1))
    blended = distill_loss(s, s, y, alpha=0.5, temperature=2.0)
    assert torch.allclose(blended, 0.5 * ce_only, atol=1e-5)


def test_distill_loss_invalid_args():
    s = torch.randn(1, 2, 8); t = torch.randn(1, 2, 8); y = torch.zeros(1, 2, dtype=torch.long)
    with pytest.raises(ValueError):
        distill_loss(s, t, y, alpha=-0.1)
    with pytest.raises(ValueError):
        distill_loss(s, t, y, alpha=1.5)
    with pytest.raises(ValueError):
        distill_loss(s, t, y, alpha=0.5, temperature=0)


def test_smoke_distill_train(tmp_path: Path):
    torch.manual_seed(0)
    chunks = chunks_from_text("hello world " * 200, seq_len=32)
    cache = tmp_path / "smoke.cache"
    write_teacher_cache(cache, chunks, UniformTeacher())
    student = AtomeLM(vocab_size=256, d_model=16, n_layers=2, d_head=8, top_k=4)
    losses = distill_train(student, cache, steps=20, batch_size=4,
                           alpha=0.5, temperature=2.0, log_every=999)
    assert all(np.isfinite(l) for l in losses)
    assert losses[-1] < losses[0] + 1.0  # not exploding


def test_uniform_teacher_shape():
    out = UniformTeacher().logits_for(np.array([1, 2, 3], dtype=np.uint8))
    assert out.shape == (3, 256)
    assert (out == 0).all()


def test_chunks_from_text_drops_partial():
    chunks = chunks_from_text("abcdefghij", seq_len=4)  # 10 bytes → 2 chunks of 4
    assert chunks.shape == (2, 4)
    assert chunks.dtype == np.uint8


def test_cache_rejects_wrong_magic(tmp_path: Path):
    bad = tmp_path / "bad.cache"
    bad.write_bytes(b"NOTATOMETC" + b"\x00" * 60)
    with pytest.raises(ValueError):
        read_teacher_cache(bad)
