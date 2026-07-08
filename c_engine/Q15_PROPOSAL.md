**English** · [Français](Q15_PROPOSAL.fr.md) · [Español](Q15_PROPOSAL.es.md) · [简体中文](Q15_PROPOSAL.zh-CN.md) · [Deutsch](Q15_PROPOSAL.de.md) · [日本語](Q15_PROPOSAL.ja.md) <!-- i18n-switcher -->

# Q15-activations path — design proposal (NOT implemented)

## Why this exists

In the May 10 emulator session we initially suspected float-op-order
between ARM softfloat and host x86 was causing multi-token drift. On
inspection, the actual cause was a logic bug — `atome_predict_next`
never reset `state->ssm_h`, so prior-call SSM state polluted later
forward passes. That bug is now fixed (`atome.c:294-300`) and 48/48
QEMU tokens match Python.

But Q15 is still worth doing for **performance and energy**, not
correctness. This file freezes the design so the next session can pick
it up cold.

## What Q15 buys (best estimates, not measured yet)

| Win | Magnitude | Why |
|---|---|---|
| Compute speedup on M0 / M3 | ~5-10× | No FPU; integer multiply-accumulate is a single cycle on ARM v7-M |
| Compute speedup on M4F / M7 | ~1.5-2× | Already has FPU; gain is from SIMD (`__SADD16`, `SMLAD`) |
| BSS reduction | ~40-50% | Activation tensors halve (fp32 → int16) |
| Power per token | ~3-5× lower | Scales with cycles |
| Determinism across hosts | full | Integer arithmetic eliminates rounding-order ambiguity |

## What Q15 does NOT buy

- Smaller `.atome` blob — weights are already ternary (~0.5 bit each).
  Activations live in RAM, not flash.
- Better model quality — quantization at inference is lossy; expect
  perplexity to rise slightly (likely <5% if calibrated; needs measurement).

## Design

### Compile-time switch

Add `ATOME_DTYPE` selecting `f32` (today, default) or `q15` (new).
Existing tests / firmware unchanged when flag is absent.

```c
#ifndef ATOME_DTYPE_Q15
#define ATOME_DTYPE_Q15 0
#endif

#if ATOME_DTYPE_Q15
typedef int16_t  atome_act_t;
typedef int32_t  atome_acc_t;
#else
typedef float    atome_act_t;
typedef float    atome_acc_t;
#endif
```

### What stays float

- LayerNorm (sqrt + division — Q15-LayerNorm exists but adds 200 LOC)
- Softmax (exp — same)
- The single `1.0 / sqrtf(d_h)` attention scale
- Final logits (so argmax is unambiguous)

These are <2% of cycles. Convert to/from Q15 at the boundary.

### What becomes Q15

- All ternary matvecs (`atome_ternary_matvec`)
- Causal conv (`atome_causal_conv`)
- SSM forward (with care — `tanh(a)` and `b * x` need fixed-point handling)
- Attention dot product (Q.K)
- Attention weighted sum (sum_i p_i * V_i)

### Per-tensor scale tracking

Each Q15 tensor carries an implicit shift. Maintain a small per-step
`atome_q15_state_t` with the current scales and update on the fly:

```c
typedef struct {
    int x_shift;        /* current activation shift (Q15-pos) */
    int normed_shift;
    int path_local_shift;
    int path_ssm_shift;
    int path_attn_shift;
} atome_q15_state_t;
```

Calibration script (Python-side): run a few thousand prompts through
the float model, record max absolute activation per layer, set shift
so that 99.9th percentile fits in [-32768, 32767].

### Test plan

1. New `tests/test_q15_parity.py`: float reference vs Q15 forward.
   Tolerance: top-1 logit must match for >95% of prompts at d=64,
   per-token cosine similarity >0.98.
2. New `c_engine/targets/cortex-m3-q15/` target. Firmware reports
   per-token cycles; expect 5-10× faster than `cortex-m3-gen` at
   identical config.
3. Add `q15` row to `RAM_TABLE.md`. Expected: tinystories config drops
   from 104 KB peak → ~55 KB peak. F103 Blue Pill ($2-4) becomes
   reachable for the trained model.

## Estimated effort

| Phase | Effort | Risk |
|---|---|---|
| Calibration (Python) + scales export | half day | low |
| `atome.c` Q15 path (skeleton + matvec + conv) | 1 day | low |
| SSM Q15 (tanh table + scaled multiply-add) | half day | medium — numeric care |
| Attention Q15 (Q·K, softmax-input scaling) | half day | medium |
| Tests + firmware target | half day | low |
| Calibration tuning + benchmarks | half day | low |
| **Total** | **~3-4 days** | — |

## When to revisit

After:
1. The 1M-param checkpoint (`TRAIN_1M_RUNBOOK.md`) lands and we have a
   real model worth optimizing for speed/power.
2. Real-silicon validation on Nucleo-F411RE confirms today's QEMU
   numbers are predictive.
3. A user wants to run Atome on F103 Blue Pill ($2-4) — the cheapest
   tier currently blocked by RAM at the trained-model config.

This is a clean, scoped, self-contained piece of work. Pick it up when
one of the above conditions hits.
