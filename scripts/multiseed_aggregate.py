#!/usr/bin/env python3
"""Aggregate multi-seed training-log JSONs into a single results JSON.

Reads the *.train.json produced by train_atome_1m.py and train_vanilla_1m.py
for each seed, computes mean / sd / Welch's t-test, and emits a single
JSON document the FRONTIER.md update block can quote directly.

Usage:
    python scripts/multiseed_aggregate.py \\
        --atome checkpoints/atome_1m_seed{1,2,3}/atome_1m_v1.train.json \\
        --vanilla checkpoints/vanilla_1m_seed{1,2,3}/vanilla_1m_v1.train.json \\
        --out 944k_multiseed.json
"""
from __future__ import annotations
import argparse, json, math, statistics, sys
from pathlib import Path


def best_val_loss(log_path: Path) -> float:
    with log_path.open() as f:
        data = json.load(f)
    return min(rec["val_loss"] for rec in data["val_history"])


def welch_t(a: list[float], b: list[float]) -> tuple[float, float]:
    ma, mb = statistics.mean(a), statistics.mean(b)
    va, vb = statistics.variance(a), statistics.variance(b)
    na, nb = len(a), len(b)
    se = math.sqrt(va / na + vb / nb)
    t = (ma - mb) / se if se > 0 else float("inf")
    df = (va / na + vb / nb) ** 2 / (
        (va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1)
    )
    return t, df


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--atome",   nargs="+", required=True, type=Path)
    ap.add_argument("--vanilla", nargs="+", required=True, type=Path)
    ap.add_argument("--out",     type=Path, required=True)
    args = ap.parse_args()

    atome   = [best_val_loss(p) for p in args.atome]
    vanilla = [best_val_loss(p) for p in args.vanilla]

    def stats(xs):
        return {
            "n":    len(xs),
            "mean": statistics.mean(xs),
            "sd":   statistics.stdev(xs) if len(xs) > 1 else 0.0,
            "ppl":  [math.exp(x) for x in xs],
            "ppl_mean": math.exp(statistics.mean(xs)),
            "values":   xs,
        }

    t, df = welch_t(atome, vanilla)
    out = {
        "atome":   stats(atome),
        "vanilla": stats(vanilla),
        "gap_pct_loss": (statistics.mean(atome) - statistics.mean(vanilla))
                         / statistics.mean(vanilla) * 100,
        "welch_t": t,
        "welch_df": df,
    }
    args.out.write_text(json.dumps(out, indent=2))
    print(f"atome   mean {out['atome']['mean']:.4f} ± {out['atome']['sd']:.4f}  "
          f"(ppl {out['atome']['ppl_mean']:.3f})")
    print(f"vanilla mean {out['vanilla']['mean']:.4f} ± {out['vanilla']['sd']:.4f}  "
          f"(ppl {out['vanilla']['ppl_mean']:.3f})")
    print(f"gap     {out['gap_pct_loss']:+.2f} %  (Welch t = {t:.2f}, df = {df:.1f})")
    print(f"wrote   {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
