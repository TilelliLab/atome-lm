#!/usr/bin/env python3
"""scripts/train_demo.py — minimal Atome LM trainer.

Trains a tiny AtomeLM on a small text file. Useful as a smoke test that
the stack composes end-to-end. Not a serious training recipe — the
intended path is to train narrow on a focused corpus (embedded-systems
Q&A, command-line help, FAQs in a specific domain) so the resulting
checkpoint is coherent in scope and small enough to fit on a $2 MCU.

Usage:
    python scripts/train_demo.py --data path/to/text.txt --steps 1000 \\
        --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import torch

from atome_llm.core.atome_lm import AtomeLM
from atome_llm.tokenize import ByteTokenizer
from atome_llm.utils.runtime import ThermalGuard, polite_training


def load_data(path: Path, tokenizer: ByteTokenizer, seq_len: int) -> torch.Tensor:
    text = path.read_text(encoding="utf-8", errors="replace")
    print(f"data: {len(text):,} chars from {path}")
    ids = tokenizer.encode(text)
    n_chunks = ids.numel() // seq_len
    return ids[: n_chunks * seq_len].view(n_chunks, seq_len)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--steps", type=int, default=1000)
    ap.add_argument("--seq-len", type=int, default=32)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--d-model", type=int, default=64)
    ap.add_argument("--n-layers", type=int, default=4)
    ap.add_argument("--d-head", type=int, default=16)
    ap.add_argument("--top-k", type=int, default=4)
    ap.add_argument("--max-temp-c", type=float, default=80.0)
    ap.add_argument("--output", type=Path, default=Path("checkpoints/atome_demo.pt"))
    args = ap.parse_args()

    tok = ByteTokenizer()
    data = load_data(args.data, tok, args.seq_len)
    print(f"chunks: {data.size(0):,} of {args.seq_len}")

    model = AtomeLM(
        vocab_size=256,
        d_model=args.d_model,
        n_layers=args.n_layers,
        d_head=args.d_head,
        top_k=args.top_k,
    )
    print(f"params: {model.parameter_count():,}")

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    guard = ThermalGuard(max_temp_c=args.max_temp_c)

    model.train()
    t0 = time.time()
    for step in range(args.steps):
        idx = torch.randint(0, data.size(0), (args.batch_size,))
        chunk = data[idx]
        ids, targets = chunk[:, :-1], chunk[:, 1:]

        with polite_training(guard, backoff_s=1.0):
            loss = model.loss(ids, targets)
            opt.zero_grad()
            loss.backward()
            opt.step()

        if step % 50 == 0:
            elapsed = time.time() - t0
            print(f"step {step:5d}  loss {loss.item():.4f}  ({elapsed:.0f}s)")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {"state_dict": model.state_dict(), "config": model.config},
        args.output,
    )
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
