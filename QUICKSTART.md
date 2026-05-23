# Atome LM — Quick Start

The 60-second path from clone to a trained, microcontroller-ready model.
For the full story see [README.md](README.md) and [REPRODUCE.md](REPRODUCE.md).

## 1. Install (CPU-only, no GPU)

```bash
./install.sh
. .venv/bin/activate
```

`install.sh` creates a local `.venv`, installs CPU-only PyTorch and Atome
LM, and runs `check_env.py`. Re-run `python check_env.py` any time to
re-verify the environment.

## 2. Train a tiny demo model

A ~256 KB sample of the permissively-licensed TinyStories corpus ships in
`data/sample.txt`, so this runs offline:

```bash
python scripts/train_demo.py --data data/sample.txt --steps 1000 \
    --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt
```

For a larger corpus, fetch one with the bundled builder:

```bash
python scripts/build_corpus.py --source tinystories \
    --max-bytes 500000 --output data/tinystories.txt
```

## 3. Talk to it

```bash
python scripts/demo.py --checkpoint checkpoints/atome_demo.pt
```

The REPL prints the continuation plus per-layer router-entropy bars — the
free per-token uncertainty signal.

## 4. Export to a microcontroller

```bash
python scripts/export_to_atome.py \
    --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome --header
```

At default config the `.atome` binary is well under 100 KB. Drop the
generated `.h` into a C project and load it with the engine in
`c_engine/`.

## 5. Run the tests

```bash
pytest -q
```

The QEMU Cortex-M3 parity tests need `qemu-system-arm`, `arm-none-eabi-gcc`,
and `xxd` on `PATH`; they are **skipped** (not failed) when the toolchain
is absent.

---

**Trained weights are bundled** in `checkpoints/` — `atome_944k.bin`
(packed C-engine blob), `atome_1m_v1.pt` (PyTorch source), and
`vanilla_1m_v1.pt` (FP32 baseline for the 944 K reversal A/B in
[HONEST_RESULTS.md](HONEST_RESULTS.md)). If you want to run the model
without training first:

```bash
python scripts/demo.py --checkpoint checkpoints/atome_1m_v1.pt
```

If you want to train your own from scratch, follow the
`scripts/train_demo.py` flow above — it produces a 60 K-parameter model
in ~30 min on a CPU.
