**English** · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# Atome LLM — vendored C engine

This directory contains the C99 inference engine that runs Atome LLM checkpoints on microcontrollers and on the host. The Python side of the project (`atome_llm/`) trains and exports; the C side here loads the exported `.atome` binary and runs the forward pass on-device.

## Layout

```
c_engine/
├── README.md                  this file
├── upstream/
│   ├── atome.h                public API + compile-time #defines
│   └── atome.c                implementation (~570 lines, zero-heap, integer-arithmetic forward)
└── targets/
    └── cortex-m3/             ARM Cortex-M3 firmware that runs in QEMU MPS2-AN385
        ├── firmware.c
        ├── startup.s
        ├── linker.ld
        └── Makefile
```

## Where this came from

The files in `upstream/` are vendored copies of an internal C engine source as of 2026-05-03. Vendoring (rather than submoduling or symlinking) is intentional: atome-llm should be the unit of distribution. To pull in upstream changes, re-copy the files and re-run the parity test suite (`pytest tests/test_parity_with_c.py tests/test_qemu_parity.py`).

One small delta from the verbatim upstream: a single comment in `atome.h` was renamed to "Atome block" (it had referred to the predecessor name). No functional change — comments don't compile.

## Building for the host (x86-64)

The simplest path — used by `tests/test_parity_with_c.py`:

```bash
gcc -O2 -std=c99 -DATOME_D_MODEL=16 -DATOME_N_LAYERS=2 ... \
    -I c_engine/upstream parity_main.c c_engine/upstream/atome.c -lm
```

## Building for ARM Cortex-M

Two layers:

1. **Compile-only sanity check** across multiple Cortex-M variants — `python scripts/cross_compile.py` produces a size table (`text/data/bss` per architecture). Catches portability regressions and gives real on-target binary size numbers.
2. **Full firmware** for QEMU MPS2-AN385 — `make -C c_engine/targets/cortex-m3` produces a `.elf` that runs under `qemu-system-arm` with semihosting. End-to-end Python ↔ Cortex-M3 parity test lives at `tests/test_qemu_parity.py`.

## Architecture notes

The C engine assumes:
- Per-tensor ternary scale (single FP32 per weight matrix)
- Embedding layout `(vocab, d_model)` — see `atome_llm/core/ternary_embedding.py` for why this matters
- No per-row scale, no multi-bank weights, no positional embedding
- `atome_block_t` has fixed buffers for `local_conv`, `ssm`, `attn`, and `router` only — no wide conv, no dense FFN, no retrieval pathway

These constraints are load-bearing. Adding a new pathway requires updating `atome.h`, the C kernels, the `.atome` binary format, **and** the Python `MCUBlock` together.
