**English** · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# Atome LM

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20518644.svg)](https://doi.org/10.5281/zenodo.20518644)
[![tests](https://github.com/TilelliLab/atome-lm/actions/workflows/test.yml/badge.svg)](https://github.com/TilelliLab/atome-lm/actions/workflows/test.yml)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Model-FFB020)](https://huggingface.co/TilelliLab/atome-lm)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

> A reference implementation of a routed-ternary tiny language model with a
> bit-exact Python ↔ C99 inference engine, sized for microcontroller-class RAM
> budgets.

60K-default-parameter LM combining three known ideas into one open kit:
ternary weights (after [BitNet b1.58](https://arxiv.org/abs/2402.17764)),
a hybrid SSM + sparse-attention + local-conv block routed per token
(after [Hymba](https://arxiv.org/abs/2411.13676) and
[MossNet](https://arxiv.org/abs/2510.26182)),
and a byte tokenizer at super-tiny scale
(after [Guertler 2024](https://arxiv.org/abs/2405.14159)).
**The contribution is integration, not architecture**: a complete train →
ternary export → base-3 packing → C99 inference path, with bit-exact
Python ↔ C parity enforced by tests.

**Quick links:**
- 📄 Architecture writeup: [`PAPER.md`](PAPER.md)
- 🔬 Honest results, including the 944 K reversal: [`HONEST_RESULTS.md`](HONEST_RESULTS.md)
- 🌐 Live in-browser demo (no install): [atomelm.com/demo.html](https://atomelm.com/demo.html)
- 🏠 Project home: [atomelm.com](https://atomelm.com)

**Get the kit:** training code, C engine, benchmarks, paper, and trained
weights — all in this repository, released under the
[Apache 2.0 License](LICENSE). Train your own checkpoint with
`scripts/train_demo.py` in ~30 min on a CPU, or run the bundled 944 K
checkpoint immediately.

**MCU status:** QEMU ARM (Cortex-M3, MPS2-AN385) parity passes to FP32
epsilon, and a reproducible **real-silicon demo** runs the 944 K checkpoint on a
physical **ESP32-WROOM-32** — coherent text, fully offline, ~1 tok/s — see
[`hardware/esp32-wroom32/`](hardware/esp32-wroom32/) (prebuilt binary + serial
log + one-command flash). That demo is a bare proof-of-execution; **productized
bring-up** — the Atome Secure Boot Pack (signed `.atome` blobs, dev/prod flags,
per-platform secure-boot, attestation), per-platform hardening — we sell as
integration at [atomelm.com](https://atomelm.com).

**Weights are included** in `checkpoints/`:

- `atome_944k.bin` (271 KB) — the packed C-engine blob (`ATOME01` format),
  loadable directly by the inference engine.
- `atome_1m_v1.pt` (3.7 MB) — the PyTorch source checkpoint that produced
  it; use this to fine-tune or to re-export at different `#define`s.
- `vanilla_1m_v1.pt` (3.7 MB) — the FP32 vanilla GPT baseline used for
  the 944K A/B reversal in [`HONEST_RESULTS.md`](HONEST_RESULTS.md);
  shipped so you can reproduce the comparison end-to-end.

The 944K checkpoint is a research-demo artifact, not a product: it is
narrow, sometimes incoherent, and trained on a single corpus. It is here
to make the architecture *runnable*, not to set a quality bar. Reproduction
is ~$1–2 of CPU/GPU using the included training code; nothing in this kit
is a reproduction barrier.

---

## Reproducible result, narrow regime

On TinyStories, 3000 steps, single seed: at fixed parameter count Atome's
routed-ternary block reaches **6.31 ppl vs 8.12** for a vanilla GPT-FP32
baseline (−22 %); at fixed flash budget **6.31 vs 13.10** (−52 %). Disk
footprint is 16× smaller at param-match (15.1 KB vs 237.5 KB).

**The result reverses at 944 K parameters**, where the vanilla FP32 baseline
wins by ~11 %. Atome's bet is deliberately the sub-1M, MCU-class regime;
above it ternary's capacity ceiling closes the gap and overruns it. Full
reproduction in [`FRONTIER.md`](FRONTIER.md), full honest reading including
the reversal in [`HONEST_RESULTS.md`](HONEST_RESULTS.md).

## Why

Datacenter LLMs assume datacenter RAM. A $2 microcontroller stuck on a wall in a remote sensor, a hearing aid, a battery-powered toy, or a thermostat doesn't have it. Atome LM is the model design end of that constraint:

- **Ternary weights** (`{-α, 0, +α}` per tensor, BitNet b1.58 style). No float multiplies in the matmul at inference.
- **3-pathway block** (local depthwise conv, diagonal SSM, top-k sparse attention) mixed by a per-token soft router. Designed to match the Atome C99 engine struct exactly so trained checkpoints export to flash and run with **bit-exact parity** between Python and C.
- **Byte tokenizer.** No BPE table to ship.
- **Router entropy as a calibration signal.** The per-token router distribution's entropy is observable for free at every position. At Atome-LLM's engine-default 60 K-parameter scale on a single narrow corpus the signal is exposed but its calibration as an uncertainty estimator at that scale has not been measured here. We have *preliminarily* observed (in a larger 3 M-parameter model **not part of this release**) that entropy tracks out-of-domain inputs and correlates with per-token loss — reported here as a not-yet-public observation, with measurements to follow in a future release.

## What this is and isn't

- **Is:** the Python training side and architecture for a ternary LM that runs on cents-class hardware.
- **Isn't:** a general-purpose chatbot. At engine-default config (`d_model=64`, `n_layers=4`) the model is roughly 60 K parameters and exports to about 20 KB of flash. Train it narrow — a single domain (embedded-system Q&A, command-line help, a single FAQ) — and it speaks fluently inside that scope. Going wide at this size produces incoherent output; that is a reflection of capacity, not of the architecture. For more headroom, raise `d_model` and `n_layers` (e.g. `d_model=128, n_layers=6` ≈ 600 K parameters, ~150 KB packed) and re-export with the matching `#define`s.

## Install

```bash
./install.sh          # CPU-only venv + dependencies + environment check
```

Or manually: `pip install -e .` (Python ≥ 3.10, PyTorch ≥ 2.0). New here?
[`QUICKSTART.md`](QUICKSTART.md) is the 60-second path from clone to a
microcontroller-ready model.

## Quick start

```python
import torch
from atome_llm.core.atome_lm import AtomeLM

# Defaults match the Atome C99 engine's compile-time #defines:
#   d_model=64, n_layers=4, d_head=16, top_k=4, kernel=5, vocab=256.
model = AtomeLM()
print(f"params: {model.parameter_count():,}")

ids = torch.randint(0, 256, (1, 32))
logits = model(ids)                     # (1, 32, 256)
loss = model.loss(ids[:, :-1], ids[:, 1:])

# Per-layer per-token uncertainty signal — no extra training:
ent_per_layer = model.router_entropies(ids)   # list of (B, L) tensors
```

## Train a tiny demo

```bash
python scripts/train_demo.py --data path/to/text.txt --steps 1000 \
    --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt
```

A built-in `build_corpus.py` fetches a few permissively-licensed sources
(`tinystories`, `esp-idf`, `mcu-wikipedia`) for smoke training:

```bash
python scripts/build_corpus.py --source tinystories --max-bytes 500000 \
    --output data/tinystories.txt
```

## Try a checkpoint

```bash
python scripts/demo.py --checkpoint checkpoints/atome_demo.pt
# or, with no checkpoint, sanity-check the plumbing:
python scripts/demo.py --random --temperature 0.8 --top-p 0.9
```

The REPL prints the continuation and per-layer router-entropy bars over
the prompt — the metacognition signal that's exposed for free.

## Sampling

`AtomeLM.generate(...)` defaults to greedy argmax (matching the C
engine's `atome_predict_next`). Optional `temperature`, `top_p`, `top_k`,
and `generator=` arguments enable nucleus / top-k sampling with seeded
reproducibility.

## Benchmark

```bash
python scripts/benchmark.py            # tiny / default / large
```

CPU forward + generate latency at three representative configs. Useful
as a regression check after architecture changes; not an MCU number.

## Export to a microcontroller

```bash
python scripts/export_to_atome.py \
    --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome \
    --header
```

This produces a `.atome` flat binary you can `#include` from C and load with `atome_load(...)` from the [Atome C99 engine](c_engine/). At default config the binary is well under 100 KB — fits comfortably on ESP32-S3, STM32F4, RP2040, nRF52840, ESP32-C3.

## Architecture

```
x → LayerNorm → ┬─→ Local  (depthwise causal conv k=5)        ─→┐
                ├─→ State  (diagonal SSM, O(L))                 ─→ Σ → +x
                └─→ Sparse (top-k attention, O(L·k))            ─→┘
                        ↑              ↑
                        │              router weights r ∈ Δ per token
                        └──────────────┘
```

Three pathways. Three different inductive biases. One shared per-token router that learns which pathway is most appropriate for each position. The router's per-token entropy is exposed as a free per-position uncertainty signal at every layer.

The full architecture story is in [`PAPER.md`](PAPER.md).

## Tests

```bash
pytest -q
```

## License

Apache License 2.0 — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

The kit is fully open: use, modify, redistribute, and ship in commercial products without per-seat or per-device fees. The Apache 2.0 patent grant covers the 3-pathway routed-ternary architecture as released here.

The released checkpoints in `checkpoints/` (atome_944k.bin, atome_1m_v1.pt, vanilla_1m_v1.pt) are likewise Apache-2.0. They are reference / research artifacts, not products. Commercial integration — silicon bring-up, the Atome Secure Boot Pack (signed `.atome` blobs, dev/prod flags, per-platform secure-boot, attestation), per-platform hardening, custom-domain fine-tuning of the larger internal V2 model — is available at [atomelm.com](https://atomelm.com).

## Citation

```bibtex
@software{atome_llm_2026,
  title  = {Atome LM: a tiny ternary language model for microcontroller deployment},
  author = {Atome LM contributors},
  year   = {2026},
  note   = {Apache 2.0, https://atomelm.com},
}
```
