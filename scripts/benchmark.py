#!/usr/bin/env python3
"""scripts/benchmark.py — CPU forward / generate latency for AtomeLM.

Measures end-to-end Python latency at a few representative configs.
Useful as a regression check after architecture changes and as a
human-readable counterpart to `scripts/budget.py`'s flash/RAM table.

NOT a fair MCU number: the Python implementation runs on PyTorch FP32
with autograd machinery still around. The C engine is what runs on the
chip; this benchmark is for the training / development side.

Usage:
    python scripts/benchmark.py
    python scripts/benchmark.py --configs default 600k --seq 32
"""
from __future__ import annotations

import argparse
import statistics
import time

import torch

from atome_llm.core.atome_lm import AtomeLM


CONFIGS: dict[str, dict] = {
    "tiny":    dict(d_model=32, n_layers=2, d_head=8,  top_k=4),
    "default": dict(d_model=64, n_layers=4, d_head=16, top_k=4),
    "large":   dict(d_model=128, n_layers=6, d_head=32, top_k=4),
}


def time_block(fn, n_iter: int) -> tuple[float, float]:
    """Return (median_ms, stdev_ms) over `n_iter` calls."""
    samples: list[float] = []
    for _ in range(n_iter):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    median = statistics.median(samples)
    stdev = statistics.stdev(samples) if len(samples) > 1 else 0.0
    return median, stdev


def bench_one(name: str, cfg: dict, seq: int, n_new: int, n_iter: int,
              warmup: int) -> dict:
    torch.manual_seed(0)
    model = AtomeLM(vocab_size=256, **cfg).eval()
    params = model.parameter_count()

    ids_full = torch.randint(0, 256, (1, seq), dtype=torch.long)
    ids_short = torch.tensor([[1]], dtype=torch.long)

    # Warmup
    for _ in range(warmup):
        with torch.no_grad():
            model(ids_full)

    fwd_med, fwd_std = time_block(
        lambda: model(ids_full), n_iter
    )
    gen_med, gen_std = time_block(
        lambda: model.generate(
            ids_short, n_new_tokens=n_new, max_seq=seq, temperature=0.0
        ),
        n_iter,
    )

    tps = (n_new / gen_med) * 1000 if gen_med > 0 else float("nan")

    return {
        "name": name,
        "params": params,
        "d_model": cfg["d_model"],
        "n_layers": cfg["n_layers"],
        "fwd_ms": fwd_med,
        "fwd_std": fwd_std,
        "gen_ms": gen_med,
        "gen_std": gen_std,
        "tok_per_s": tps,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="+", default=["tiny", "default", "large"])
    ap.add_argument("--seq", type=int, default=32,
                    help="prompt length for the forward benchmark")
    ap.add_argument("--n-new", type=int, default=16,
                    help="tokens to generate for the generate benchmark")
    ap.add_argument("--iter", type=int, default=10)
    ap.add_argument("--warmup", type=int, default=2)
    args = ap.parse_args()

    print(f"# AtomeLM CPU benchmark  ({torch.get_num_threads()} threads)\n")
    print(
        f"{'config':<10} {'params':>10} {'d_model':>8} {'layers':>7} "
        f"{'fwd ms (B=1, L=' + str(args.seq) + ')':>22} "
        f"{'gen ms (' + str(args.n_new) + ' tok)':>20} "
        f"{'tok/s':>10}"
    )
    print("-" * 90)

    rows = []
    for name in args.configs:
        if name not in CONFIGS:
            print(f"!! unknown config '{name}' (have: {list(CONFIGS)})")
            continue
        row = bench_one(
            name, CONFIGS[name], args.seq, args.n_new, args.iter, args.warmup
        )
        rows.append(row)
        print(
            f"{row['name']:<10} {row['params']:>10,} "
            f"{row['d_model']:>8} {row['n_layers']:>7} "
            f"{row['fwd_ms']:>16.2f} ± {row['fwd_std']:>4.2f}    "
            f"{row['gen_ms']:>10.2f} ± {row['gen_std']:>4.2f}   "
            f"{row['tok_per_s']:>9.1f}"
        )


if __name__ == "__main__":
    main()
