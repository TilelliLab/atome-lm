#!/usr/bin/env python3
"""scripts/budget.py — print flash + RAM estimates for an Atome LLM config
against a table of common microcontroller targets.

The flash estimate is the size of the exported `.atome` binary at the
given config (computed from the same byte counts the exporter writes).
The RAM estimate matches the static buffers in `atome_state_t` from
atome.h: input + normed + three pathway scratch arrays + per-layer SSM
state + KV cache + logits + router weights + attention scratch.

Both numbers are estimates; the actual binary size and `sizeof(atome_state_t)`
are exact. Use the flash number to decide whether your model fits the
target's program memory, and the RAM number to decide whether the
inference state fits in working RAM.

Usage:
    python scripts/budget.py
    python scripts/budget.py --d-model 128 --n-layers 6
    python scripts/budget.py --d-model 64 --n-layers 4 --max-seq 64
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass


F32_BYTES = 4
TRIT_BITS = 2
MAGIC_BYTES = 7  # "ATOME01"


@dataclass(frozen=True)
class MCU:
    name: str
    flash_kb: int
    ram_kb: int


# Working RAM, not flash. ESP32-S3 / nRF52840 etc. have lots of flash
# and we generally don't worry about flash on those; RAM is the binding
# constraint. The numbers below are typical conservative figures for the
# RAM available to a single application after the toolchain reserves
# stack and bootloader.
TARGETS = [
    MCU("ATtiny1614",       16,    2),
    MCU("ATmega328P",       32,    2),
    MCU("RP2040",         2048,  264),
    MCU("nRF52840",       1024,  256),
    MCU("STM32F4 (F411)",  512,  128),
    MCU("ESP32-C3",       4096,  400),
    MCU("ESP32-S3",       8192,  512),
]


def packed_bytes_for_n_trits(n: int) -> int:
    """4 trits per byte (2 bits each)."""
    return (n + 3) // 4


def ternary_block_bytes(rows: int, cols: int) -> int:
    return F32_BYTES + packed_bytes_for_n_trits(rows * cols)


def norm_block_bytes(d: int) -> int:
    return F32_BYTES * d * 2


def ssm_block_bytes(d: int) -> int:
    return F32_BYTES * d * 3


def block_flash_bytes(d: int, dh: int, ks: int) -> int:
    """One block: norm + conv + ssm + Wq + Wk + Wv + router."""
    total = 0
    total += norm_block_bytes(d)
    total += ternary_block_bytes(d, ks)              # depthwise conv: (d, ks)
    total += ssm_block_bytes(d)
    total += ternary_block_bytes(dh, d)              # Wq
    total += ternary_block_bytes(dh, d)              # Wk
    total += ternary_block_bytes(d, d)               # Wv
    total += ternary_block_bytes(3, d)               # router (3 pathways)
    return total


def model_flash_bytes(vocab: int, d: int, n_layers: int, dh: int, ks: int) -> int:
    """Total bytes the exported .atome binary occupies in flash."""
    total = MAGIC_BYTES
    total += ternary_block_bytes(vocab, d)           # embed
    total += n_layers * block_flash_bytes(d, dh, ks)
    total += norm_block_bytes(d)                     # final_norm
    total += ternary_block_bytes(vocab, d)           # unembed
    return total


def model_ram_bytes(d: int, n_layers: int, dh: int, max_seq: int, vocab: int) -> int:
    """Approximate sizeof(atome_state_t) for the given config.

    Mirrors the struct in atome.h:
        x[MAX_SEQ][D_MODEL]              float
        normed[MAX_SEQ][D_MODEL]         float
        path_local[MAX_SEQ][D_MODEL]     float
        path_ssm[MAX_SEQ][D_MODEL]       float
        path_attn[MAX_SEQ][D_MODEL]      float
        ssm_h[N_LAYERS][D_MODEL]         float
        logits[VOCAB_SIZE]               float
        router_w[MAX_SEQ][N_PATHWAYS]    float (n_pathways = 3)
        q[D_HEAD]                        float
        k_cache[MAX_SEQ][D_HEAD]         float
        v_cache[MAX_SEQ][D_MODEL]        float
        attn_scores[MAX_SEQ]             float
    """
    total = 0
    total += F32_BYTES * max_seq * d                 # x
    total += F32_BYTES * max_seq * d                 # normed
    total += F32_BYTES * max_seq * d * 3             # 3 pathway scratch
    total += F32_BYTES * n_layers * d                # SSM hidden state per layer
    total += F32_BYTES * vocab                       # logits
    total += F32_BYTES * max_seq * 3                 # router weights
    total += F32_BYTES * dh                          # q
    total += F32_BYTES * max_seq * dh                # k_cache
    total += F32_BYTES * max_seq * d                 # v_cache
    total += F32_BYTES * max_seq                     # attn scores
    return total


def fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.2f} MB"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--d-model", type=int, default=64)
    ap.add_argument("--n-layers", type=int, default=4)
    ap.add_argument("--d-head", type=int, default=16)
    ap.add_argument("--kernel-size", type=int, default=5)
    ap.add_argument("--max-seq", type=int, default=32)
    ap.add_argument("--vocab", type=int, default=256)
    args = ap.parse_args()

    flash = model_flash_bytes(args.vocab, args.d_model, args.n_layers,
                              args.d_head, args.kernel_size)
    ram = model_ram_bytes(args.d_model, args.n_layers, args.d_head,
                          args.max_seq, args.vocab)

    print(f"\nAtome LLM budget for d_model={args.d_model}, "
          f"n_layers={args.n_layers}, d_head={args.d_head}, "
          f"max_seq={args.max_seq}, vocab={args.vocab}")
    print("=" * 70)
    print(f"  Flash (binary):  {fmt_bytes(flash):>10}")
    print(f"  RAM (state):     {fmt_bytes(ram):>10}")
    print()

    print(f"  {'Target':<20} {'Flash':>10} {'RAM':>10}  Verdict")
    print(f"  {'-' * 20} {'-' * 10} {'-' * 10}  {'-' * 20}")
    for mcu in TARGETS:
        flash_avail = mcu.flash_kb * 1024
        ram_avail = mcu.ram_kb * 1024
        flash_ok = flash <= flash_avail
        ram_ok = ram <= ram_avail
        if flash_ok and ram_ok:
            verdict = "fits"
        elif not flash_ok and not ram_ok:
            verdict = "too big (flash + RAM)"
        elif not flash_ok:
            verdict = "too big (flash)"
        else:
            verdict = "too big (RAM)"
        print(f"  {mcu.name:<20} "
              f"{fmt_bytes(flash_avail):>10} {fmt_bytes(ram_avail):>10}  {verdict}")
    print()


if __name__ == "__main__":
    main()
