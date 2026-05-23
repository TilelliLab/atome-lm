#!/usr/bin/env python3
"""scripts/evaluate.py — held-out bits-per-character for an Atome LM checkpoint.

Reads a UTF-8 text file, byte-encodes it, slides over it in non-overlapping
chunks of `--seq-len`, and computes the mean cross-entropy loss in bits per
predicted byte. Pure-CPU, no gradients.

Useful as a numeric quality signal for trained checkpoints — easier to
read than raw cross-entropy because it's directly interpretable as
"how many bits per character of the test set the model needs."

Usage:
    python scripts/evaluate.py \\
        --checkpoint checkpoints/atome_1m_v1.pt \\
        --data data/sample.txt \\
        --max-bytes 100000
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import torch
from torch.nn import functional as F

from atome_llm.core.atome_lm import AtomeLM
from atome_llm.tokenize import ByteTokenizer


def load_model(path: Path) -> AtomeLM:
    blob = torch.load(path, map_location="cpu", weights_only=True)
    cfg = blob.get("config", {})
    model = AtomeLM(
        vocab_size=cfg.get("vocab_size", 256),
        d_model=cfg.get("d_model", 64),
        n_layers=cfg.get("n_layers", 4),
        d_head=cfg.get("d_head", 16),
        top_k=cfg.get("top_k", 4),
        kernel_size=cfg.get("kernel_size", 5),
    )
    model.load_state_dict(blob["state_dict"])
    return model.eval()


@torch.no_grad()
def bits_per_byte(model: AtomeLM, ids: torch.Tensor, seq_len: int,
                  batch_size: int = 8) -> tuple[float, int]:
    """Returns (bpb, n_bytes_predicted)."""
    n_full = ids.numel() // seq_len
    if n_full == 0:
        raise ValueError(f"data ({ids.numel()} bytes) shorter than seq_len {seq_len}")
    chunks = ids[: n_full * seq_len].view(n_full, seq_len)
    total_loss_nats = 0.0
    total_predicted = 0
    for i in range(0, n_full, batch_size):
        batch = chunks[i: i + batch_size]
        logits = model(batch[:, :-1])             # (B, L-1, V)
        targets = batch[:, 1:]                    # (B, L-1)
        loss_nats = F.cross_entropy(
            logits.reshape(-1, model.vocab_size),
            targets.reshape(-1),
            reduction="sum",
        ).item()
        total_loss_nats += loss_nats
        total_predicted += targets.numel()
    bits_per_nat = 1.0 / math.log(2)
    bpb = (total_loss_nats / total_predicted) * bits_per_nat
    return bpb, total_predicted


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--max-bytes", type=int, default=200_000)
    ap.add_argument("--seq-len", type=int, default=128)
    ap.add_argument("--batch-size", type=int, default=8)
    args = ap.parse_args()

    model = load_model(args.checkpoint)
    text = args.data.read_text(encoding="utf-8", errors="replace")[: args.max_bytes]
    ids = ByteTokenizer().encode(text)

    bpb, n_pred = bits_per_byte(model, ids, args.seq_len, args.batch_size)
    print(
        f"checkpoint:  {args.checkpoint}\n"
        f"data:        {args.data}\n"
        f"params:      {model.parameter_count():,}\n"
        f"predicted:   {n_pred:,} bytes  (seq_len={args.seq_len})\n"
        f"bits/byte:   {bpb:.4f}\n"
        f"perplexity:  {2 ** bpb:.3f}\n"
        f"baseline (uniform 256): 8.0000 bpb / 256 ppl\n"
    )


if __name__ == "__main__":
    main()
