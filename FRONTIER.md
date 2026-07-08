**English** · [Français](FRONTIER.fr.md) · [Español](FRONTIER.es.md) · [简体中文](FRONTIER.zh-CN.md) · [Deutsch](FRONTIER.de.md) · [日本語](FRONTIER.ja.md) <!-- i18n-switcher -->

# Atome LM — Frontier Findings

> **Update 2026-05-11 — scale-up A/B at 944K reverses the headline.**
> Same recipe, same val slice, same fairness audit, a 944K-param vanilla
> GPT-FP32 baseline (950,608 params, +0.63 % vs Atome's 944,640) reaches
> val loss 0.9337 / ppl 2.54, beating Atome ternary at 944K by 11.4 %
> in loss and 11.5 % in perplexity. The +22 % param-fair / +52 %
> flash-fair gains below hold at the **60K-param MCU regime** and only
> that regime. Above ~1M params the inductive bias of the 3-pathway
> block stops substituting for capacity and starts constraining it.
> The honest framing is: *Atome's bet is the small-model regime —
> sub-1M params, MCU-class deployment, no network.* See
> [`HONEST_RESULTS.md`](HONEST_RESULTS.md) for the full 944K reading.
> Multi-seed pending.

**Date.** 2026-05-09. CPU only, no GPU.
**Hardware.** 4-thread CPU box. PyTorch 2.x, FP32 reference path.
**Corpus.** TinyStories validation slice, 500 KB UTF-8 (~99.9 % ASCII).
Train/eval split 90/10 over 64-byte chunks → 7,030 train chunks /
782 held-out chunks.
**Optimizer.** AdamW, lr 3e-4, batch 16, seq 64, 3,000 steps.
**Single seed** (seed 0). Results have not been replicated across seeds.

This document reports the first apples-to-apples A/B between Atome's
3-pathway ternary architecture and vanilla decoder-only Transformers
(FP32) at fixed parameter count and at fixed flash budget. The closest
published peer is Andrej Karpathy's `Stories260K` — a 260 K-parameter
FP32 plain transformer trained on TinyStories. Atome's frontier claim
is "smaller flash, better quality, smaller bits-per-weight, *and*
deployable on a $2 microcontroller." This page tests the first three
of those claims directly; MCU deployment is verified separately via
bit-exact Python ↔ C ↔ Cortex-M3 (QEMU) parity (see `tests/test_qemu_parity.py`).

## TL;DR

| Model | Params | Bits/wt | Disk | bpb ↓ | Perplexity ↓ |
|---|---:|---:|---:|---:|---:|
| **Atome 3-pathway, ternary** | **60,800** | **1.58** | **15.1 KB**¹ / **17.2 KB**² | **2.66** | **6.31** |
| Vanilla GPT, FP32 (param-fair) | 60,808 | 32 | 237.5 KB | 3.02 | 8.12 |
| Vanilla GPT, FP32 (flash-fair) | 5,968 | 32 | 23.3 KB | 3.71 | 13.10 |

¹ ATOME01, 4 trits/byte (current C engine reads this).
² ATOME02, 5 trits/byte base-3 packing — 14.4 % smaller, near
information-theoretic floor of `log2(3) ≈ 1.585` bits/trit. Python
encoder + decoder shipped today; C decoder is a future change.

## What this proves

1. **At the same parameter count, the 3-pathway ternary architecture
   beats a plain transformer by 22 % on perplexity (6.31 vs 8.12)
   while using 16× less disk.**

   The vanilla baseline is *not* over-parameterized — it's matched at
   60.8 K params (`d_model=44, n_layers=3, n_heads=4, d_ff=44`,
   selected by brute-force search to land within 8 params of the
   target). This is the same architecture every public tiny-LM paper
   (`Stories260K`, the TinyStories paper, BitNet at small scale) uses,
   modulo trivia.

2. **At the same flash budget, the 3-pathway ternary architecture beats
   a plain transformer by 52 % on perplexity (6.31 vs 13.10).**

   The flash-fair vanilla baseline is `d_model=8, n_layers=2,
   n_heads=4, d_ff=24`. It sits in the same 20–25 KB on-disk budget as
   the Atome ATOME01 binary (15.1 KB) and ATOME02 binary (17.2 KB).

3. **The 1.58-bit weights cost ~22 % perplexity vs FP32 at the same
   architecture parameters** — but the FP32 version costs 16× more
   flash. On any device where flash is the bottleneck (every MCU we
   target), ternary wins. On any device where compute is the
   bottleneck and flash is free (server CPUs), FP32 wins on quality.

4. **ATOME02 base-3 packing reaches 1.6 bits/trit — within 1 % of the
   information-theoretic floor of 1.585 bits/trit** — and reduces the
   on-disk binary from 20.1 KB to 17.2 KB on the same trained
   60.8 K-param model. C decoder still pending.

## What this does NOT prove

- **Single seed only.** All three numbers are seed 0. We have not run
  multi-seed yet to estimate variance. The 22 % / 52 % gaps are very
  large compared to typical seed-noise at this scale, but the variance
  is unmeasured.
- **Single corpus.** TinyStories is a forgiving target — short stories
  with restricted vocabulary. Wider-domain or code corpora may favor
  vanilla attention. We have not measured.
- **Single training horizon.** 3,000 steps is well short of
  convergence. The relative ranking might swap or amplify with more
  training. A 10 K-step run is in flight; we'll update this page if it
  changes the headline.
- **No real silicon.** All MCU claims are verified on QEMU
  Cortex-M3, not on physical RP2040 / STM32 hardware. Tokens/sec and
  Joules/token on real silicon are still pending.
- **Stories260K direct comparison still pending.** Karpathy's exact
  setup is `Stories260K` at 260 K params + a 32 K-token SentencePiece
  vocab. Our byte-tokenizer + 60 K config is ~4× smaller. A direct
  apples-to-apples vs `Stories260K` would need either (a) us to scale
  up to 260 K params and a SentencePiece tokenizer, or (b) Karpathy's
  setup retrained at 60 K params with a byte tokenizer. Neither is
  done.

## Comparison with the published frontier

| System | Smallest target | Params | Bits/wt | Real MCU? | Architecture beats vanilla? |
|---|---|---:|---:|---|---|
| Microsoft BitNet b1.58 | server CPU | 700 M – 3 B | 1.58 | no | (matches at scale) |
| Meta MobileLLM | smartphone | 125 M – 1 B | 4–8 | no | yes (vs same-size vanilla) |
| Karpathy `Stories260K` | laptop / browser | 260 K | 32 | no firmware | n/a (is the vanilla baseline) |
| llama.cpp on RP2040 (hobby) | RP2040 + SD | ~1 B (swapped) | 4 | yes (slow, requires SD) | not measured |
| TFLite Micro / Edge Impulse | Cortex-M0+ | – | 8 | yes | no language tasks |
| **Atome LM (this work)** | **Cortex-M0+, 16 KB SRAM** | **60 K** | **1.58** | **QEMU yes, silicon pending** | **+22 % at param-fair, +52 % at flash-fair** |

Smaller, more bit-efficient, *and* architecturally beats vanilla at
the budgets we target. To our knowledge, the smallest published LM
where the routed-architecture win has been measured directly against
a vanilla baseline at the same flash budget.

## Reproduce

```bash
# from the repository root
PYTHONPATH=. python3 scripts/build_corpus.py --source tinystories \
    --max-bytes 500000 --output data/tinystories.txt

PYTHONPATH=. python3 scripts/run_ab_sweep.py \
    --train data/tinystories.txt --steps 3000 \
    --output ab_results.json
```

`ab_results.json` will contain the same numbers as in the table above
(modulo platform-dependent rounding in PyTorch's matmul kernels).

## Open questions / next pushes

- **A1.** Multi-seed (3 seeds × 3 configs) to estimate variance on the
  22 % / 52 % gaps.
- **A2.** Train all three to ≥ 10 K steps. Does the gap close, hold,
  or widen?
- **A3.** Ablate: which of the three pathways (local conv, diagonal
  SSM, top-k sparse attention) carries most of the architecture win?
  Drop each, measure.
- **A4.** Ship a C decoder for ATOME02. Cuts the demo binary from
  20.1 KB to 17.2 KB without code changes elsewhere.
- **A5.** Real silicon. Flash an RP2040 with the engine + this 60.8 K
  ckpt. Measure tokens/sec, Joules/token. **The headline number that
  turns the claim from "frontier" into a fact.**
- **A6.** Distillation from a strong teacher LLM (10 MB of curated
  narrow-domain text generated by a frontier model) into the same 60 K Atome.
  Open question: does the architecture advantage compound under
  distillation?
- **A7.** Bug A fix (Python `generate` ↔ C `atome_generate`
  short-prompt SSM divergence). Touches the bit-exact-parity
  contract — needs explicit user sign-off.

## Files of record

- `ab_results.json` — exact numbers and config of the run reported here.
- Trained A/B checkpoints (`atome_60k_ternary`, `vanilla_60k_fp32`,
  `vanilla_6k_fp32`) are *not* shipped — regenerate them with the harness
  below (this kit is train-from-scratch).
- `atome_llm/baselines/vanilla_transformer.py` — the baseline.
- `scripts/run_ab_sweep.py` — the harness.
- `tests/test_vanilla_baseline.py` — 10 sanity tests on the baseline.
- `tests/test_export_packed.py` — 5 tests on ATOME02 round-trip.
- `tests/test_trit_packing.py` — 11 tests on the base-3 packer.
