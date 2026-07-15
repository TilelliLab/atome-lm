#!/usr/bin/env python3
"""tools/gen_placeholder_model.py — structurally-valid ATOME01 blob with
random weights, for build/size testing when no real checkpoint is
available (this repo has no trained nano/tiny checkpoint; scripts/
measure_ram.py generates its own random-init model on the fly for the
same reason).

This is NOT a usable model. atome_load() will parse it successfully
and atome_predict_next() will run without crashing, but the output is
noise (random float bit patterns as gamma/beta/scale, may include NaN/
Inf). It exists to test that the firmware boots, links, and fits the
32 KB / 16 KB budget -- not to test inference quality.

For a real model: run scripts/export_to_atome.py on an AtomeLM
checkpoint (needs torch) with the matching nano/tiny config, and pass
that .atome file via `make MODEL_ATOME=path/to/model.atome`.

Byte layout mirrors atome_load()/read_ternary()/read_norm()/
read_conv()/read_ssm() in c_engine/upstream/atome.c exactly:

    "ATOME01"
    embed:   scale(f32) + packed trits (vocab * d_model)
    per block (n_layers):
        norm:   gamma(f32 * d) + beta(f32 * d)
        conv:   scale(f32) + packed trits (d * kernel_size)
        ssm:    a(f32 * d) + b(f32 * d) + c_out(f32 * d)
        Wq:     scale(f32) + packed trits (d_head * d)
        Wk:     scale(f32) + packed trits (d_head * d)
        Wv:     scale(f32) + packed trits (d * d)
        router: scale(f32) + packed trits (n_pathways * d)
    final_norm: gamma(f32 * d) + beta(f32 * d)
    unembed: scale(f32) + packed trits (vocab * d_model)
"""
from __future__ import annotations

import argparse
import random
import struct
import sys

CONFIGS = {
    "nano": dict(vocab_size=32, d_model=16, n_layers=2, d_head=8,
                 kernel_size=5, n_pathways=3),
    "tiny": dict(vocab_size=32, d_model=16, n_layers=2, d_head=8,
                 kernel_size=5, n_pathways=3),
}


def packed_trits(n_trits: int, rng: random.Random) -> bytes:
    n_bytes = (n_trits + 3) // 4
    return bytes(rng.randint(0, 255) for _ in range(n_bytes))


def rand_f32(rng: random.Random, n: int) -> bytes:
    # Small, finite values -- keeps LayerNorm/softmax from immediately
    # blowing up to NaN, even though the weights are meaningless.
    return b"".join(struct.pack("<f", rng.uniform(-1.0, 1.0)) for _ in range(n))


def build(cfg: dict, seed: int) -> bytes:
    rng = random.Random(seed)
    d = cfg["d_model"]
    v = cfg["vocab_size"]
    dh = cfg["d_head"]
    ks = cfg["kernel_size"]
    npw = cfg["n_pathways"]

    out = bytearray(b"ATOME01")

    def ternary(rows: int, cols: int) -> None:
        out.extend(struct.pack("<f", rng.uniform(0.5, 1.5)))  # scale
        out.extend(packed_trits(rows * cols, rng))

    def norm(dim: int) -> None:
        out.extend(rand_f32(rng, dim))  # gamma
        out.extend(rand_f32(rng, dim))  # beta

    ternary(v, d)  # embed

    for _ in range(cfg["n_layers"]):
        norm(d)  # block norm
        out.extend(struct.pack("<f", rng.uniform(0.5, 1.5)))  # conv scale
        out.extend(packed_trits(d * ks, rng))  # conv packed
        out.extend(rand_f32(rng, d))  # ssm a
        out.extend(rand_f32(rng, d))  # ssm b
        out.extend(rand_f32(rng, d))  # ssm c_out
        ternary(dh, d)  # Wq
        ternary(dh, d)  # Wk
        ternary(d, d)   # Wv
        ternary(npw, d)  # router

    norm(d)  # final_norm
    ternary(v, d)  # unembed

    return bytes(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", choices=sorted(CONFIGS), default="nano")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    blob = build(CONFIGS[args.config], args.seed)
    with open(args.output, "wb") as f:
        f.write(blob)
    print(f"wrote {args.output}: {len(blob)} bytes "
          f"({len(blob) / 1024:.2f} KB), config={args.config} "
          f"-- PLACEHOLDER WEIGHTS, not a trained model", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
