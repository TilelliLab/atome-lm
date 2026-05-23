"""atome_llm.distill — knowledge distillation from a teacher LM into Atome.

The teacher gets to be any byte-tokenized callable that returns next-byte
log-probabilities. Cached teacher logits land on disk as a numpy memmap
so distillation training is decoupled from any API call: write the cache
once with whatever provider is available, then iterate cheaply.

The student is an `AtomeLM`. The training objective is a convex blend of
the standard token cross-entropy and KL(student || teacher) over the
full vocabulary.

This file is the pure mechanism; the teacher provider is pluggable so
the student-training step never depends on a network or an API key. Two
trivial providers ship: a `RandomTeacher` for tests and a
`UniformTeacher` for sanity checks. Real teachers live in user code.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import torch
from torch import Tensor
from torch.nn import functional as F

from atome_llm.core.atome_lm import AtomeLM
from atome_llm.tokenize import ByteTokenizer


VOCAB_SIZE = 256


# ────────────────────── teacher providers ────────────────────── #


class RandomTeacher:
    """Returns uniformly random logits — for plumbing tests only."""
    def __init__(self, seed: int = 0):
        self._rng = np.random.default_rng(seed)

    def logits_for(self, byte_ids: np.ndarray) -> np.ndarray:
        L = byte_ids.shape[0]
        return self._rng.standard_normal((L, VOCAB_SIZE)).astype(np.float32)


class UniformTeacher:
    """Returns equal logits over the vocabulary — distill target is uniform."""
    def logits_for(self, byte_ids: np.ndarray) -> np.ndarray:
        return np.zeros((byte_ids.shape[0], VOCAB_SIZE), dtype=np.float32)


# ────────────────────── cache file format ───────────────────── #


@dataclass(frozen=True)
class CacheHeader:
    n_chunks: int
    seq_len: int
    vocab_size: int


def write_teacher_cache(
    cache_path: Path,
    chunks: np.ndarray,
    teacher: Callable[[np.ndarray], np.ndarray] | object,
) -> CacheHeader:
    """Compute teacher logits for every chunk and write a flat float32 cache.

    Layout:
        magic ("ATOMETC1") · n_chunks (u32) · seq_len (u32) · vocab_size (u32)
        · chunks (u8 × n_chunks × seq_len)
        · logits (f32 × n_chunks × seq_len × vocab_size)

    The student-side reader memmaps the logits region, so a 1 GB cache
    is OK on a laptop without loading it into RAM.
    """
    if chunks.ndim != 2:
        raise ValueError(f"chunks must be (n_chunks, seq_len); got {chunks.shape}")
    n_chunks, seq_len = chunks.shape
    if not hasattr(teacher, "logits_for"):
        raise TypeError("teacher must have .logits_for(byte_ids) → (L, V) ndarray")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("wb") as f:
        f.write(b"ATOMETC1")
        f.write(np.array([n_chunks, seq_len, VOCAB_SIZE], dtype=np.uint32).tobytes())
        f.write(chunks.astype(np.uint8).tobytes())
        for c in chunks:
            tlogits = teacher.logits_for(c)
            if tlogits.shape != (seq_len, VOCAB_SIZE):
                raise ValueError(
                    f"teacher returned {tlogits.shape}, expected ({seq_len},{VOCAB_SIZE})"
                )
            f.write(tlogits.astype(np.float32).tobytes())
    return CacheHeader(n_chunks=n_chunks, seq_len=seq_len, vocab_size=VOCAB_SIZE)


def read_teacher_cache(cache_path: Path
                       ) -> tuple[CacheHeader, np.memmap, np.memmap]:
    """Memmap the cache. Returns (header, chunks_view, logits_view)."""
    buf = cache_path.read_bytes()[:8]
    if buf != b"ATOMETC1":
        raise ValueError(f"bad magic: {buf!r}")
    header_arr = np.frombuffer(
        cache_path.read_bytes()[8:8 + 12], dtype=np.uint32
    )
    n_chunks, seq_len, vocab = (int(x) for x in header_arr)
    h = CacheHeader(n_chunks=n_chunks, seq_len=seq_len, vocab_size=vocab)

    off_chunks = 20
    chunks_n = n_chunks * seq_len
    chunks = np.memmap(cache_path, dtype=np.uint8, mode="r",
                       offset=off_chunks, shape=(n_chunks, seq_len))
    off_logits = off_chunks + chunks_n
    logits = np.memmap(cache_path, dtype=np.float32, mode="r",
                       offset=off_logits, shape=(n_chunks, seq_len, vocab))
    return h, chunks, logits


# ────────────────────── distill loss ────────────────────── #


def distill_loss(
    student_logits: Tensor,
    teacher_logits: Tensor,
    targets: Tensor,
    *,
    alpha: float = 0.5,
    temperature: float = 2.0,
) -> Tensor:
    """Convex blend of CE on hard targets and KL(student || teacher) on soft.

    `alpha=0` is pure soft (KL only); `alpha=1` is pure hard (CE only).
    Standard distillation defaults: alpha=0.5, temperature=2.

    `student_logits` and `teacher_logits` are (B, L, V); `targets` is
    (B, L) integer. KL is computed at temperature T and rescaled by T².
    """
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha must be in [0, 1], got {alpha}")
    if temperature <= 0:
        raise ValueError(f"temperature must be > 0, got {temperature}")

    B, L, V = student_logits.shape
    ce = F.cross_entropy(student_logits.reshape(-1, V), targets.reshape(-1))

    s = F.log_softmax(student_logits / temperature, dim=-1)
    t = F.softmax(teacher_logits / temperature, dim=-1)
    kl = F.kl_div(s, t, reduction="batchmean") * (temperature ** 2)

    return alpha * ce + (1.0 - alpha) * kl


# ────────────────────── distill loop ────────────────────── #


def distill_train(
    student: AtomeLM,
    cache_path: Path,
    *,
    steps: int = 3000,
    batch_size: int = 16,
    lr: float = 3e-4,
    alpha: float = 0.5,
    temperature: float = 2.0,
    log_every: int = 200,
) -> list[float]:
    """Train `student` on cached teacher logits + hard targets.

    Returns the list of step losses. Plain AdamW; identical optimizer and
    schedule to `train_demo.py`. Re-uses the same byte tokenizer and
    sequence layout.
    """
    h, chunks, logits = read_teacher_cache(cache_path)
    if h.vocab_size != student.vocab_size:
        raise ValueError(
            f"vocab mismatch: cache {h.vocab_size}, student {student.vocab_size}"
        )

    chunks_t = torch.from_numpy(np.asarray(chunks, dtype=np.int64))
    opt = torch.optim.AdamW(student.parameters(), lr=lr)
    student.train()

    losses: list[float] = []
    for step in range(steps):
        idx = torch.randint(0, chunks_t.size(0), (batch_size,))
        batch_ids = chunks_t[idx]
        batch_t_logits = torch.from_numpy(np.asarray(logits[idx]))
        ids_in = batch_ids[:, :-1]
        targets = batch_ids[:, 1:]
        teacher_in = batch_t_logits[:, :-1, :]

        student_logits = student(ids_in)
        loss = distill_loss(
            student_logits, teacher_in, targets,
            alpha=alpha, temperature=temperature,
        )
        opt.zero_grad()
        loss.backward()
        opt.step()
        losses.append(loss.item())
        if step % log_every == 0:
            print(f"distill step {step:5d}  loss {loss.item():.4f}")
    return losses


def chunks_from_text(text: str, seq_len: int) -> np.ndarray:
    """Convenience helper: byte-encode text and return non-overlapping chunks."""
    ids = ByteTokenizer().encode(text).numpy().astype(np.uint8)
    n_full = ids.size // seq_len
    return ids[: n_full * seq_len].reshape(n_full, seq_len)
