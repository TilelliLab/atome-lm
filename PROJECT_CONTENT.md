# PROJECT_CONTENT.md — Project orientation

Read this first. ~5 minute orientation for anyone (human or agent) coming to the codebase. Saves you from breaking load-bearing invariants this kit cares about.

---

## TL;DR

**Atome LM** is a ~60K-parameter ternary language model + a C99 inference engine that runs it on bare-metal microcontrollers (RP2040, ESP32-C3, Cortex-M0). The Python training stack and the C engine are designed to produce **bit-exact identical** forward passes — that parity is the project's whole point.

- License: Apache 2.0
- Tests: `pytest -q` → expect **146 passed, 0 skipped** (1 skip if `qemu-system-arm` is missing)
- No trained weights ship in this repo. Train your own with `scripts/train_demo.py` (~30 min CPU).

## Why this exists

Most "tiny LMs" are big LMs that have been compressed. Atome is shaped from the start by MCU constraints: RAM is the binding cost, ternary weights kill float multiplies, three pathways (local conv + diagonal SSM + sparse top-k attention) replace a deep transformer stack, a per-token soft router mixes them, and the byte tokenizer avoids shipping a vocab. The interesting claim is not the primitives (all prior art — BitNet, Mamba, top-k attention) — it's the *combination, the deployment story, and the honest evaluation* showing where this wins (60K) and where it loses (944K). The C engine is zero-heap, static buffers, deterministic memory footprint.

## What an agent must NOT break

These are load-bearing invariants. Verify any change against them before reporting done.

1. **Python ↔ C bit-exact parity.** Single-forward parity is the whole product. Tests: `tests/test_parity_with_c.py`, `tests/test_parity_multitoken.py`. If you change the model code, the export format, or the C kernels, run these and confirm they still pass.
2. **Zero heap allocation in the C engine.** `c_engine/upstream/atome.c` uses only static buffers sized by compile-time `ATOME_*` macros. Never introduce `malloc`/`calloc`/`free` here. Stack arrays are fine.
3. **`weights_only=True` on every `torch.load`.** All kit checkpoints are `{"config": dict, "state_dict": dict}` — pure tensors + primitives. Loading with `weights_only=False` is RCE on a malicious .pt file. Don't regress this.
4. **No hardcoded model constants in the exporter.** `scripts/export_to_atome.py` reads `top_k` (and all other config) from the checkpoint and writes the real value into the C header. Don't hardcode constants — there's a regression test in `tests/test_export_format.py` that will catch it.
5. **Bounds checks in `atome_predict_next` and `atome_generate`.** Both reject `n_tokens < 1`, `prompt_len < 1`, and NULL pointers before any indexing/memcpy. Don't remove these — `state->x[n_tokens - 1]` is UB without them.
6. **No trained weights in this repo.** Anything matching `*.pt`, `*.atome*`, `*.bin` is gitignored. The 944K-parameter "moat" weights live elsewhere and stay out of the public release.
7. **Honesty in benchmarks.** `HONEST_RESULTS.md` documents *both* wins (~22% better perplexity than vanilla FP32 at 60K params, 52% better at same flash budget) *and* losses (vanilla wins by ~11% at 944K scale). Don't quietly drop the losses to make headlines sound better.

## File map

```
atome-llm-kit/
├── README.md              ← user-facing intro
├── PAPER.md               ← architecture writeup
├── HONEST_RESULTS.md      ← what works, what doesn't, costs
├── FRONTIER.md            ← what's still being explored
├── QUICKSTART.md          ← 30-min train + export walkthrough
├── REPRODUCE.md           ← how to reproduce the headline benchmarks
├── LICENSE / NOTICE       ← Apache 2.0 + attribution
│
├── atome_llm/             ← Python package
│   ├── core/
│   │   ├── atome_lm.py       — main model
│   │   ├── mcu_block.py      — 3-pathway block
│   │   ├── router.py         — per-token soft router
│   │   ├── ssm.py            — diagonal SSM
│   │   ├── sparse_attention.py — top-k attention
│   │   └── ternary*.py       — ternary weight modules
│   ├── tokenize.py         — byte tokenizer (no BPE)
│   └── baselines/          — vanilla FP32 transformer for A/B
│
├── c_engine/upstream/     ← The C99 inference engine
│   ├── atome.c               — implementation (~600 lines, zero heap)
│   └── atome.h               — public API + compile-time macros
│
├── scripts/
│   ├── train_demo.py         — quick training (~30 min CPU)
│   ├── export_to_atome.py    — checkpoint → .atome binary + C header
│   ├── demo.py               — interactive REPL
│   ├── evaluate.py           — bits-per-byte eval
│   └── run_ab_sweep.py       — 60K param-fair / flash-fair A/B
│
└── tests/                 ← 146 tests, all expected to pass
    ├── test_parity_with_c.py        — single-forward Python ↔ C
    ├── test_parity_multitoken.py    — multi-token Python ↔ C
    ├── test_qemu_parity.py          — host C ↔ QEMU ARM (skips if QEMU missing)
    ├── test_export_format.py        — binary format + header generation
    └── test_*.py                    — model shape, router, SSM, ternary, etc.
```

## Verify your work

```bash
# from repo root, after install.sh has run once
. .venv/bin/activate
pytest -q       # expect: 146 passed (or 145 + 1 skipped if no qemu-system-arm)
```

That's the only signal that matters before declaring done. If you change anything in `atome_llm/core/` or `c_engine/upstream/`, do not skip this step.

## Common ways agents go wrong here

- **Treating the C engine as boilerplate.** It's not — every line is sized by RAM/flash. Don't add allocations, don't add libc dependencies, don't add `printf`. The whole point is that this runs on a $2 chip with kilobytes of RAM.
- **Trying to "improve" parameter counts or benchmark numbers in docs without rerunning the sweep.** The 60K / 944K / 22% / 52% / -11% numbers in `HONEST_RESULTS.md` are tied to specific reproducible runs. If you can't reproduce, don't edit.
- **Adding ML-style fallbacks ("if state is None, do X").** The runtime is deterministic — every code path is exercised. There are no "shouldn't happen" branches.
- **Generalizing the byte tokenizer.** It's intentionally raw bytes. Adding BPE or sentencepiece would ship a vocab table (kilobytes of flash) and defeat the design.
- **Bundling experimental ideas.** `c_engine/experiments/delta_inference/` is explicitly experimental — not on the supported path, not parity-tested. Don't promote experiments into `c_engine/upstream/` without parity + bounds-check coverage.
- **Touching the parity tests "to make them pass".** If parity tests fail, the *code* is wrong, not the test. Find the Python/C divergence — it's almost always an off-by-one in conv kernel orientation, SSM state init, or a stale hardcoded constant.

## What's open vs. what's not

| Open (this repo, Apache 2.0)                        | Not open (commercial)                         |
|-----------------------------------------------------|-----------------------------------------------|
| Architecture, training code, C engine               | Silicon bring-up (per-platform integration)   |
| 944K trained weights (`checkpoints/atome_944k.bin`) | Atome Secure Boot Pack (signed `.atome` blobs)|
| PyTorch source `atome_1m_v1.pt` + vanilla baseline  | Per-platform hardening + attestation flows    |
| Export format + parity tests                        | Larger internal V2 model (3M params, mixed-domain) |
| Sample data, A/B sweep harness                      | Custom fine-tuning + per-customer integration |
| All docs (PAPER, HONEST_RESULTS, etc.)              | Marketing / live-demo site at atomelm.com     |

The architecture is public by design and the training cost is ~$1–2 — a license-as-moat strategy was never going to work, and weights-as-moat would have been thin. The actual defensible value is the per-deployment integration work, the security hardening, and the larger V2 model kept proprietary — none of which sit in this repo.

## If you need to dig deeper

- Architecture rationale: `PAPER.md`
- What's measured, what's not, what cost what: `HONEST_RESULTS.md`
- What's still being explored: `FRONTIER.md`
- How to reproduce the headline numbers: `REPRODUCE.md`
- How to get from zero to a trained-and-exported model: `QUICKSTART.md`
