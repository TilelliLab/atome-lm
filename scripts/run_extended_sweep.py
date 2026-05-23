#!/usr/bin/env python3
"""scripts/run_extended_sweep.py — multi-seed sweep across architecture variants.

Trains:
  - atome_60k_ternary (full 3-pathway, 1.58 bits/wt, the headline model)
  - atome_60k_power3  (full 3-pathway, 7-level ~2.81 bits/wt)
  - atome_no_local    (drop conv, train state+sparse)
  - atome_no_state    (drop SSM, train conv+sparse)
  - atome_no_sparse   (drop attention, train conv+state)
  - vanilla_60k_fp32  (param-fair vanilla GPT)
  - vanilla_6k_fp32   (flash-fair vanilla GPT)

Each variant trains for `--steps` on identical TinyStories data, then
held-out bits-per-byte is reported. With `--seeds N`, each variant is
trained N times with different RNG seeds for variance estimation.

Output: a JSON file with per-run records (config, bpb, ppl, train time)
plus a summary table grouped by variant with median + min + max bpb.

Usage:
    python scripts/run_extended_sweep.py \\
        --train data/tinystories.txt --steps 3000 --seeds 3 \\
        --output extended_results.json
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from statistics import median

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


def train(model, train_chunks, steps, batch_size, lr) -> float:
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    model.train()
    last_loss = float("nan")
    for _ in range(steps):
        idx = torch.randint(0, train_chunks.size(0), (batch_size,))
        batch = train_chunks[idx]
        loss = model.loss(batch[:, :-1], batch[:, 1:])
        opt.zero_grad()
        loss.backward()
        opt.step()
        last_loss = loss.item()
    return last_loss


@torch.no_grad()
def eval_bpb(model, eval_chunks, vocab_size: int, batch_size: int = 8) -> float:
    model.eval()
    total_nats, total_predicted = 0.0, 0
    for i in range(0, eval_chunks.size(0), batch_size):
        batch = eval_chunks[i:i + batch_size]
        logits = model(batch[:, :-1])
        targets = batch[:, 1:]
        loss = F.cross_entropy(logits.reshape(-1, vocab_size),
                               targets.reshape(-1), reduction="sum").item()
        total_nats += loss
        total_predicted += targets.numel()
    return (total_nats / total_predicted) / math.log(2)


def disk_bytes(model, kind: str) -> int:
    n = sum(p.numel() for p in model.parameters())
    if kind == "atome_ternary":
        return int(n / 4) + 256                # 4 trits/byte + scales/norms
    if kind == "atome_power3":
        return int(n * 3 / 8) + 256            # 3 bits/weight + scales/norms
    return n * 4                                # FP32


VARIANTS = {
    "atome_60k_ternary": {
        "kind": "atome_ternary",
        "factory": lambda seq: AtomeLM(d_model=64, n_layers=4, d_head=16, top_k=4),
    },
    "atome_60k_power3": {
        "kind": "atome_power3",
        "factory": lambda seq: AtomeLM(d_model=64, n_layers=4, d_head=16, top_k=4,
                                       quantizer="power3"),
    },
    "atome_no_local": {
        "kind": "atome_ternary",
        "factory": lambda seq: AtomeLM(d_model=64, n_layers=4, d_head=16, top_k=4,
                                       disable_pathways=("local",)),
    },
    "atome_no_state": {
        "kind": "atome_ternary",
        "factory": lambda seq: AtomeLM(d_model=64, n_layers=4, d_head=16, top_k=4,
                                       disable_pathways=("state",)),
    },
    "atome_no_sparse": {
        "kind": "atome_ternary",
        "factory": lambda seq: AtomeLM(d_model=64, n_layers=4, d_head=16, top_k=4,
                                       disable_pathways=("sparse",)),
    },
    "vanilla_60k_fp32": {
        "kind": "vanilla_fp32",
        "factory": lambda seq: VanillaTransformer(d_model=44, n_layers=3,
                                                   n_heads=4, d_ff=44, max_seq=seq),
    },
    "vanilla_6k_fp32": {
        "kind": "vanilla_fp32",
        "factory": lambda seq: VanillaTransformer(d_model=8, n_layers=2,
                                                   n_heads=4, d_ff=24, max_seq=seq),
    },
}


def run_one(name: str, seed: int, train_chunks, eval_chunks, args) -> dict:
    print(f"\n=== {name}  seed={seed} ===")
    spec = VARIANTS[name]
    torch.manual_seed(seed)
    model = spec["factory"](args.seq_len)
    n_params = sum(p.numel() for p in model.parameters())
    disk = disk_bytes(model, spec["kind"])
    print(f"  params: {n_params:,}  disk: {disk:,} B ({disk/1024:.1f} KB)")
    t0 = time.time()
    last_loss = train(model, train_chunks, args.steps, args.batch_size, args.lr)
    train_s = time.time() - t0
    bpb = eval_bpb(model, eval_chunks, vocab_size=256)
    print(f"  train: {train_s:.0f}s  final_loss: {last_loss:.4f}  "
          f"bpb: {bpb:.4f}  ppl: {2**bpb:.2f}")
    return {
        "name": name, "seed": seed, "kind": spec["kind"],
        "params": n_params, "disk_bytes": disk,
        "train_seconds": round(train_s, 1),
        "final_loss": round(last_loss, 4),
        "bpb": round(bpb, 4), "perplexity": round(2 ** bpb, 3),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=Path, required=True)
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--seq-len", type=int, default=64)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS.keys()))
    ap.add_argument("--output", type=Path, default=Path("extended_results.json"))
    args = ap.parse_args()

    train_chunks, eval_chunks = load_data(args.train, args.seq_len)
    print(f"data: {train_chunks.size(0):,} train / {eval_chunks.size(0):,} eval "
          f"chunks of {args.seq_len}")

    results: list[dict] = []
    for name in args.variants:
        if name not in VARIANTS:
            print(f"!! unknown variant: {name}")
            continue
        for seed in range(args.seeds):
            results.append(run_one(name, seed, train_chunks, eval_chunks, args))

    summary: dict[str, dict] = {}
    for name in args.variants:
        runs = [r for r in results if r["name"] == name]
        if not runs:
            continue
        bpbs = [r["bpb"] for r in runs]
        summary[name] = {
            "n_runs": len(runs),
            "kind": runs[0]["kind"],
            "params": runs[0]["params"],
            "disk_bytes": runs[0]["disk_bytes"],
            "disk_kb": round(runs[0]["disk_bytes"] / 1024, 2),
            "bpb_median": round(median(bpbs), 4),
            "bpb_min": round(min(bpbs), 4),
            "bpb_max": round(max(bpbs), 4),
            "ppl_median": round(2 ** median(bpbs), 3),
        }

    out = {
        "config": {
            "data": str(args.train), "steps": args.steps,
            "seq_len": args.seq_len, "batch_size": args.batch_size,
            "lr": args.lr, "seeds": args.seeds,
            "torch_threads": torch.get_num_threads(),
        },
        "results": results,
        "summary": summary,
    }
    args.output.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {args.output}")

    # Pretty table
    print("\n" + "=" * 96)
    print(f"{'variant':<24} {'params':>10} {'disk':>10} {'bpb median':>12} "
          f"{'bpb range':>16} {'ppl median':>12}")
    print("-" * 96)
    for name, s in summary.items():
        rng = f"[{s['bpb_min']:.3f}, {s['bpb_max']:.3f}]"
        print(f"{name:<24} {s['params']:>10,} {s['disk_kb']:>8.1f} KB "
              f"{s['bpb_median']:>11.4f}  {rng:>16}  {s['ppl_median']:>11.2f}")


if __name__ == "__main__":
    main()
