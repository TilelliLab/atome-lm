#!/usr/bin/env python3
"""scripts/inspect_atome.py — read an exported .atome binary and print
its structure section by section.

Walks the same byte format `export_to_atome.py` writes:

    "ATOME01"                                 (7 bytes magic)
    embed:   scale(f32) + packed trits        (vocab * d_model trits)
    per block (n_layers):
        norm:   gamma(f32 * d) + beta(f32 * d)
        conv:   scale(f32) + packed trits     (d * kernel_size trits)
        ssm:    a_raw(f32*d) + b(f32*d) + c_out(f32*d)
        Wq:     scale(f32) + packed trits     (d_head * d_model trits)
        Wk:     scale(f32) + packed trits     (d_head * d_model trits)
        Wv:     scale(f32) + packed trits     (d_model * d_model trits)
        router: scale(f32) + packed trits     (3 * d_model trits)
    final_norm: gamma(f32 * d) + beta(f32 * d)
    unembed: scale(f32) + packed trits        (vocab * d_model trits)

Because the binary itself doesn't carry config in a header, the
inspector requires the user to supply --d-model / --n-layers / --d-head /
--kernel-size / --vocab so it knows what to expect. It then verifies
that the byte counts add up exactly to the file size; mismatches surface
as offset errors.

Usage:
    python scripts/inspect_atome.py model.atome \\
        --d-model 64 --n-layers 4 --d-head 16

For brevity the inspector also accepts --from-checkpoint to read the
config straight from a saved .pt file's stored config dict, removing the
need to type the shape parameters.
"""
from __future__ import annotations

import argparse
import statistics
import struct
from pathlib import Path


MAGIC = b"ATOME01"


def packed_bytes_for_n_trits(n: int) -> int:
    return (n + 3) // 4


def read_norm(data: bytes, cursor: int, d: int) -> tuple[int, dict]:
    gamma = struct.unpack_from(f"<{d}f", data, cursor)
    cursor += 4 * d
    beta = struct.unpack_from(f"<{d}f", data, cursor)
    cursor += 4 * d
    return cursor, {
        "gamma_mean": statistics.mean(gamma),
        "gamma_stdev": statistics.pstdev(gamma),
        "beta_mean": statistics.mean(beta),
        "beta_stdev": statistics.pstdev(beta),
    }


def read_ternary(data: bytes, cursor: int, rows: int, cols: int) -> tuple[int, dict]:
    scale = struct.unpack_from("<f", data, cursor)[0]
    cursor += 4
    n_trits = rows * cols
    n_bytes = packed_bytes_for_n_trits(n_trits)
    packed = data[cursor:cursor + n_bytes]
    cursor += n_bytes

    pos = neg = zer = 0
    for i in range(n_trits):
        bits = (packed[i >> 2] >> ((i & 3) << 1)) & 0x03
        if bits == 0x01:
            pos += 1
        elif bits == 0x03:
            neg += 1
        else:
            zer += 1

    return cursor, {
        "scale": scale,
        "rows": rows,
        "cols": cols,
        "n_trits": n_trits,
        "n_bytes": n_bytes,
        "frac_pos": pos / n_trits if n_trits else 0,
        "frac_neg": neg / n_trits if n_trits else 0,
        "frac_zero": zer / n_trits if n_trits else 0,
    }


def read_ssm(data: bytes, cursor: int, d: int) -> tuple[int, dict]:
    a = struct.unpack_from(f"<{d}f", data, cursor)
    cursor += 4 * d
    b = struct.unpack_from(f"<{d}f", data, cursor)
    cursor += 4 * d
    c = struct.unpack_from(f"<{d}f", data, cursor)
    cursor += 4 * d
    return cursor, {
        "a_raw_mean": statistics.mean(a),
        "b_mean": statistics.mean(b),
        "c_out_mean": statistics.mean(c),
    }


def fmt_ternary(name: str, info: dict, indent: int = 4) -> str:
    pad = " " * indent
    return (
        f"{pad}{name:<10} scale={info['scale']:>10.6f}  "
        f"shape=({info['rows']}, {info['cols']})  "
        f"trits={info['n_trits']:,}  bytes={info['n_bytes']:,}  "
        f"+{info['frac_pos']:.1%} / -{info['frac_neg']:.1%} / 0={info['frac_zero']:.1%}"
    )


def fmt_norm(name: str, info: dict, indent: int = 4) -> str:
    pad = " " * indent
    return (
        f"{pad}{name:<10} γ μ={info['gamma_mean']:>+8.4f} σ={info['gamma_stdev']:>8.4f}  "
        f"β μ={info['beta_mean']:>+8.4f} σ={info['beta_stdev']:>8.4f}"
    )


def fmt_ssm(name: str, info: dict, indent: int = 4) -> str:
    pad = " " * indent
    return (
        f"{pad}{name:<10} a_raw μ={info['a_raw_mean']:>+8.4f}  "
        f"b μ={info['b_mean']:>+8.4f}  c_out μ={info['c_out_mean']:>+8.4f}"
    )


def inspect(path: Path, vocab: int, d: int, n_layers: int, dh: int, ks: int) -> None:
    data = path.read_bytes()
    print(f"file:        {path}")
    print(f"size:        {len(data):,} bytes ({len(data) / 1024:.1f} KB)")

    if not data.startswith(MAGIC):
        raise SystemExit(f"magic mismatch: expected {MAGIC!r}, got {data[:7]!r}")
    print(f"magic:       {MAGIC!r}")
    cursor = len(MAGIC)

    print(f"\nshape:       d_model={d}  n_layers={n_layers}  d_head={dh}  "
          f"kernel_size={ks}  vocab={vocab}\n")

    cursor, embed = read_ternary(data, cursor, vocab, d)
    print("embedding")
    print(fmt_ternary("embed", embed))

    for layer_idx in range(n_layers):
        print(f"\nblock {layer_idx}")
        cursor, norm = read_norm(data, cursor, d)
        print(fmt_norm("norm", norm))
        cursor, conv = read_ternary(data, cursor, d, ks)
        print(fmt_ternary("conv", conv))
        cursor, ssm = read_ssm(data, cursor, d)
        print(fmt_ssm("ssm", ssm))
        cursor, wq = read_ternary(data, cursor, dh, d)
        print(fmt_ternary("Wq", wq))
        cursor, wk = read_ternary(data, cursor, dh, d)
        print(fmt_ternary("Wk", wk))
        cursor, wv = read_ternary(data, cursor, d, d)
        print(fmt_ternary("Wv", wv))
        cursor, rt = read_ternary(data, cursor, 3, d)
        print(fmt_ternary("router", rt))

    print("\nfinal")
    cursor, fn = read_norm(data, cursor, d)
    print(fmt_norm("final_norm", fn))
    cursor, ue = read_ternary(data, cursor, vocab, d)
    print(fmt_ternary("unembed", ue))

    leftover = len(data) - cursor
    print(f"\noffset reached: {cursor:,} / {len(data):,}  (leftover: {leftover})")
    if leftover != 0:
        raise SystemExit(
            f"format mismatch: {leftover} bytes left over after parsing — "
            f"check that --d-model/--n-layers/--d-head/--vocab match the export"
        )
    print("OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path, help=".atome binary file")
    ap.add_argument("--from-checkpoint", type=Path, default=None,
                    help="Read shape parameters from a .pt checkpoint's config dict")
    ap.add_argument("--d-model", type=int, default=64)
    ap.add_argument("--n-layers", type=int, default=4)
    ap.add_argument("--d-head", type=int, default=16)
    ap.add_argument("--kernel-size", type=int, default=5)
    ap.add_argument("--vocab", type=int, default=256)
    args = ap.parse_args()

    if args.from_checkpoint is not None:
        import torch  # local import keeps inspector usable without torch otherwise
        state = torch.load(args.from_checkpoint, map_location="cpu")
        cfg = state["config"]
        args.d_model = cfg["d_model"]
        args.n_layers = cfg["n_layers"]
        args.d_head = cfg["d_head"]
        args.kernel_size = cfg["kernel_size"]
        args.vocab = cfg["vocab_size"]

    inspect(args.path, args.vocab, args.d_model, args.n_layers,
            args.d_head, args.kernel_size)


if __name__ == "__main__":
    main()
