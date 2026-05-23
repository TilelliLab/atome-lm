# Atome LM — Honest Results Dossier

> One page, no marketing. What we measured, on what hardware, with what
> seed. Where we beat vanilla, where we don't, where we don't yet know.

**Last updated.** 2026-05-13. Compiled from `checkpoints/*.train.json`
and `ab_results.json` (which are the actual run artifacts — open them).

---

## Table 1 — The numbers, as measured

| Config | Params | Bits/wt | Loss ↓ | PPL ↓ | Disk | Status |
|---|---:|---:|---:|---:|---:|---|
| **60K regime (MCU target)** | | | | | | |
| Atome 3-pathway ternary | 60,800 | 1.58 | 1.84 | 6.31 | 15.1 KB¹ | ✅ measured |
| Vanilla GPT FP32 (param-fair) | 60,808 | 32 | 2.09 | 8.12 | 237.5 KB | ✅ measured |
| Vanilla GPT FP32 (flash-fair) | 5,968 | 32 | 2.57 | 13.10 | 23.3 KB | ✅ measured |
| **944K regime (scale-up A/B)** | | | | | | |
| Atome 3-pathway ternary | 944,640 | 1.58 | **1.0545** | 2.87 | 184 KB¹ | ✅ measured |
| Vanilla GPT FP32 (param-fair) | 950,608 | 32 | **0.9337** | 2.54 | 3.7 MB | ✅ measured |
| Atome 3-pathway, power3 (per-tensor) | 944,640 | 2.81 | TBD | TBD | ~325 KB est | ⏳ launcher ready |
| Atome 3-pathway, power3 (per-row α) | 944,640 | 2.81² | TBD | TBD | ~330 KB est | ⏳ launcher ready |

¹ ATOME01, 4 trits/byte packing.  
² Per-tensor portion is 2.81 bits/wt; per-row α adds one FP16 per output
row (negligible % overhead at 944K).

**Headlines, unsanitized:**

- At the 60K MCU target, the 3-pathway ternary architecture beats vanilla
  FP32 by **22% in perplexity at the same param count** and **52% at the
  same flash budget**.
- At 944K, plain ternary **loses to vanilla FP32 by 11.4% in val loss /
  11.5% in perplexity**. Same recipe, same val slice, same seed.
- The 944K reversal is the most important honest finding in this kit.
  It says: the 3-pathway inductive bias substitutes for capacity at
  small scale and constrains it at larger scale. Atome's bet is the
  small-model / MCU regime — not "tiny ternary beats everything."

## Table 2 — What the 944K result is conditioned on

| Variable | Value |
|---|---|
| Corpus | TinyStories full (`train.txt + valid.txt` concatenated, ~1.7 GB raw) |
| Steps | 30,000 |
| Sequence length | 256 |
| Batch × accum | 64 × 4 |
| Optimizer | AdamW, lr=3e-4 → 3e-5 cosine, warmup=1000, weight_decay=0.1 |
| Precision | BF16 autocast |
| Seed | 0 (single seed; multi-seed pending) |
| Hardware | RunPod A100/A6000 (atome) — vast A100 (vanilla, 2026-05-11) |

## Table 3 — What we have NOT measured

| Question | Why it matters | Cost to resolve |
|---|---|---|
| Multi-seed variance at 944K | Single seed isn't a finding | ~$2 vast (3 seeds × atome + vanilla) |
| Crossover point | Where exactly does 3-pathway start losing? | ~$8 vast (sweep 100K / 300K / 600K / 1.5M) |
| Power-of-3 closes the 944K gap | If yes: the loss-reversal headline flips | ~$6 vast (this kit's launcher) |
| Q15 fixed-point inference RAM | RP2040 RAM target was missed at 944K (411 KB peak) | ~3 days engineering |
| Real silicon throughput | All MCU claims are QEMU; turns "frontier" into "fact" | $0 (RP2040 sitting on desk) + ~1 day |
| Distillation from vanilla teacher | Ternary students often close 80%+ of float-teacher gap | ~$1–2 vast |
| Wider-domain corpora | TinyStories favors local-pattern models | ~$4 vast |

## Table 4 — What's solid vs what's load-bearing-but-thin

**Solid (don't change without strong reason):**

- 146/146 tests green at HEAD (16 of those are power3-specific).
- Bit-exact Python ↔ C ↔ Cortex-M3 (QEMU) parity for single forward
  (`tests/test_parity_with_c.py`, `tests/c_parity/parity_main.c`).
- Trained atome_1m_v1.pt + vanilla_1m_v1.pt artifacts on disk, both
  with full training logs in `checkpoints/*.train.json` (open them — every step's
  loss is recorded).
- 60K param-fair / flash-fair A/B reproducible in ~30 min CPU
  (`scripts/run_ab_sweep.py`).

**Load-bearing but thin:**

- All headline numbers are single-seed.
- Multi-token C generation previously had an SSM-state divergence bug
  (Bug A). Fixed in both Python and the C engine: `atome_predict_next`
  resets the SSM hidden state and re-derives it from the full token
  prefix on every call (`c_engine/upstream/atome.c`). Multi-token
  Python↔C parity is covered by `tests/test_parity_multitoken.py`;
  single-forward parity remains bit-exact via `tests/test_parity_with_c.py`.
- RP2040 demo currently exceeds 264 KB SRAM at 944K — the MCU claim
  is regime-dependent and the launcher in this kit is testing whether
  power3 narrows the param budget enough to bring 944K back into scope
  (it doesn't on its own; needs Q15 or smaller hidden state).

## Table 5 — Cost of every measurement done to date

| Work | Date | Cost | Result on disk |
|---|---|---:|---|
| 60K A/B sweep | 2026-05-09 | $0 (CPU) | `ab_results.json` |
| 944K Atome | 2026-05-10 | ~$0.40 (RunPod A40) | `atome_1m_v1.pt` |
| 944K Vanilla | 2026-05-11 | ~$0.55 (Vast A100) | `vanilla_1m_v1.pt` |
| Power-3 wiring + tests + CPU smoke | 2026-05-12/13 | $0 (CPU) | `atome_llm/core/power3.py` + 6 new tests |
| **Total spent so far** | | **< $1.00** | — |
| Pending: 944K A/B with power3 + power3_pr | — | ~$3.60–$6.40 cap $8 | launcher in `scripts/` |

## Files of record

The trained 944K checkpoints and their training logs ship with the kit, so
every reported number is auditable step-by-step *and* re-evaluable directly:

- `checkpoints/atome_944k.bin` — packed C-engine blob (ATOME01 format).
- `checkpoints/atome_1m_v1.pt` — 944K Atome PyTorch source.
- `checkpoints/vanilla_1m_v1.pt` — 944K vanilla FP32 baseline (for the
  reversal A/B above).
- `checkpoints/atome_1m_v1.train.json` — every-1000-step training log.
- `checkpoints/vanilla_1m_v1.train.json` — same for the vanilla baseline.
- `ab_results.json` — exact 60K A/B result row.
- `FRONTIER.md` — frontier writeup with full 944K disclosure.
- `PAPER.md` — architecture writeup.
- `tests/` — 146 green tests.

The 60K sweep itself (`checkpoints/ab_sweep/`) is **not** shipped — that
was 24 throwaway training runs. Reproducing the sweep takes ~20 minutes
of CPU using the included `scripts/`.
