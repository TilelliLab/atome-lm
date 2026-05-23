#!/usr/bin/env python3
"""scripts/run_ab_sweep.py — Atome vs vanilla-FP32 head-to-head.

Trains three models on the same data with the same step budget, then
evaluates each on a held-out slice and writes results to JSON.

The three:
  - atome_60k_ternary    : 60.8 K params, 1.58 bits/wt → ~12 KB weights
                            packed, ~20 KB .atome binary on disk.
  - vanilla_60k_fp32     : 60.8 K params, 32 bits/wt → ~243 KB FP32.
                            *Param-fair* — same parameter count, ~20× more bits.
  - vanilla_6k_fp32      : 6.0 K params, 32 bits/wt → ~24 KB FP32.
                            *Flash-fair* — same approximate flash budget as
                            our packed ternary binary.

The headline finding we want is: at fixed flash budget on a $2 MCU,
Atome wins on bpb. At fixed param count, vanilla wins (because it has
~20× more bits).

Usage:
    python scripts/run_ab_sweep.py \\
        --train data/tinystories.txt --steps 3000 \\
        --output ab_results.json
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import torch
from torch.nn import functional as F

from atome_llm.baselines.vanilla_transformer import VanillaTransformer
from atome_llm.core.atome_lm import AtomeLM
from atome_llm.tokenize import ByteTokenizer


def load_data(path: Path, seq_len: int, train_frac: float = 0.9
              ) -> tuple[torch.Tensor, torch.Tensor]:
    text = path.read_text(encoding="utf-8", errors="replace")
    ids = ByteTokenizer().encode(text)
    n_full = ids.numel() // seq_len
    chunks = ids[: n_full * seq_len].view(n_full, seq_len)
    n_train = int(n_full * train_frac)
    return chunks[:n_train], chunks[n_train:]


def train(model: torch.nn.Module, train_chunks: torch.Tensor, steps: int,
          batch_size: int, lr: float) -> list[float]:
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    model.train()
    losses: list[float] = []
    t0 = time.time()
    for step in range(steps):
        idx = torch.randint(0, train_chunks.size(0), (batch_size,))
        batch = train_chunks[idx]
        loss = model.loss(batch[:, :-1], batch[:, 1:])
        opt.zero_grad()
        loss.backward()
        opt.step()
        losses.append(loss.item())
        if step % 200 == 0 or step == steps - 1:
            print(f"    step {step:5d}  loss {loss.item():.4f}  "
                  f"({time.time() - t0:.0f}s)")
    return losses


@torch.no_grad()
def eval_bpb(model: torch.nn.Module, eval_chunks: torch.Tensor,
             vocab_size: int, batch_size: int = 8) -> float:
    model.eval()
    total_nats = 0.0
    total_predicted = 0
    for i in range(0, eval_chunks.size(0), batch_size):
        batch = eval_chunks[i:i + batch_size]
        logits = model(batch[:, :-1])
        targets = batch[:, 1:]
        loss_nats = F.cross_entropy(
            logits.reshape(-1, vocab_size),
            targets.reshape(-1),
            reduction="sum",
        ).item()
        total_nats += loss_nats
        total_predicted += targets.numel()
    bits_per_nat = 1.0 / math.log(2)
    return (total_nats / total_predicted) * bits_per_nat


def disk_size_bytes(model: torch.nn.Module, kind: str) -> int:
    """Approximate on-disk size after the natural quantization for that arch."""
    n_params = sum(p.numel() for p in model.parameters())
    if kind == "atome_ternary":
        # 4 trits/byte packed (current ATOME01 format); scales + norms add a few %.
        return int(n_params / 4) + 256  # ~256 B for headers + scales (rough)
    return n_params * 4  # FP32


def run_one(name: str, model_factory, kind: str,
            train_chunks: torch.Tensor, eval_chunks: torch.Tensor,
            steps: int, batch_size: int, lr: float,
            ckpt_dir: Path) -> dict:
    print(f"\n=== {name} ===")
    torch.manual_seed(0)
    model = model_factory()
    n_params = sum(p.numel() for p in model.parameters())
    disk = disk_size_bytes(model, kind)
    print(f"  params: {n_params:,}  approx disk: {disk:,} B "
          f"({disk / 1024:.1f} KB)")

    t0 = time.time()
    losses = train(model, train_chunks, steps, batch_size, lr)
    train_s = time.time() - t0

    bpb = eval_bpb(model, eval_chunks, vocab_size=256)
    print(f"  train time: {train_s:.0f}s  bpb: {bpb:.4f}  ppl: {2 ** bpb:.2f}")

    ckpt_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = ckpt_dir / f"{name}.pt"
    torch.save(
        {"state_dict": model.state_dict(), "config": model.config, "kind": kind},
        ckpt_path,
    )

    return {
        "name": name,
        "kind": kind,
        "params": n_params,
        "approx_disk_bytes": disk,
        "approx_disk_kb": round(disk / 1024, 2),
        "steps": steps,
        "train_seconds": round(train_s, 1),
        "final_loss": round(losses[-1], 4),
        "bpb": round(bpb, 4),
        "perplexity": round(2 ** bpb, 3),
        "ckpt": str(ckpt_path),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=Path, required=True)
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--seq-len", type=int, default=64)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--output", type=Path, default=Path("ab_results.json"))
    ap.add_argument("--ckpt-dir", type=Path, default=Path("checkpoints/ab_sweep"))
    ap.add_argument("--skip", nargs="*", default=[],
                    help="model names to skip (e.g. atome_60k_ternary)")
    args = ap.parse_args()

    train_chunks, eval_chunks = load_data(args.train, args.seq_len)
    print(f"data: {train_chunks.size(0):,} train / {eval_chunks.size(0):,} eval "
          f"chunks of {args.seq_len}")

    runs = [
        ("atome_60k_ternary", "atome_ternary",
         lambda: AtomeLM(d_model=64, n_layers=4, d_head=16, top_k=4)),
        ("vanilla_60k_fp32", "vanilla_fp32",
         lambda: VanillaTransformer(d_model=44, n_layers=3, n_heads=4,
                                    d_ff=44, max_seq=args.seq_len)),
        ("vanilla_6k_fp32", "vanilla_fp32",
         lambda: VanillaTransformer(d_model=8, n_layers=2, n_heads=4,
                                    d_ff=24, max_seq=args.seq_len)),
    ]

    results = []
    for name, kind, fac in runs:
        if name in args.skip:
            print(f"\n=== {name} (SKIPPED) ===")
            continue
        results.append(run_one(
            name, fac, kind, train_chunks, eval_chunks,
            args.steps, args.batch_size, args.lr, args.ckpt_dir,
        ))

    out = {
        "config": {
            "data": str(args.train),
            "steps": args.steps,
            "seq_len": args.seq_len,
            "batch_size": args.batch_size,
            "lr": args.lr,
            "torch_threads": torch.get_num_threads(),
        },
        "results": results,
    }
    args.output.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {args.output}")

    # Pretty table
    print("\n" + "=" * 88)
    print(f"{'name':<24} {'kind':<16} {'params':>10} {'disk':>10} "
          f"{'bpb':>8} {'ppl':>10}")
    print("-" * 88)
    for r in results:
        print(f"{r['name']:<24} {r['kind']:<16} "
              f"{r['params']:>10,} {r['approx_disk_kb']:>8.1f} KB "
              f"{r['bpb']:>8.4f} {r['perplexity']:>10.2f}")


if __name__ == "__main__":
    main()
