# Atome LM — Reproduction Guide

Every number on `FRONTIER.md` and `HONEST_RESULTS.md` traces back to a
command in this file. CPU only unless noted; budget figures assume
RunPod / Vast A100/A6000 pricing.

## Setup (3 min)

```bash
pip install -e .
pytest -q                                # 146/146 should pass
```

## 60K A/B sweep (~30 min CPU, $0)

Reproduces the param-fair (Atome 22% > vanilla) and flash-fair
(Atome 52% > vanilla) tables in FRONTIER.md.

```bash
PYTHONPATH=. python3 scripts/build_corpus.py --source tinystories \
    --max-bytes 500000 --output data/tinystories.txt

PYTHONPATH=. python3 scripts/run_ab_sweep.py \
    --train data/tinystories.txt --steps 3000 \
    --output ab_results.json

python3 -c "import json; r=json.load(open('ab_results.json')); \
    [print(f\"{m}: ppl={d['val_ppl']:.2f}\") for m,d in r.items()]"
```

## 944K Atome single-seed (~$0.40, RunPod A40 ~4h)

The ckpt that produced val_loss 1.0545 / ppl 2.87.

Prerequisite — build the full TinyStories corpus (one-shot, ~5 min):

```bash
PYTHONPATH=. python3 scripts/build_corpus.py --source tinystories \
    --output data/tinystories_full.txt
```

Then train:

```bash
# On the GPU pod:
PYTHONPATH=. python3 scripts/train_atome_1m.py \
    --data data/tinystories_full.txt \
    --output checkpoints/atome_1m_v1.pt \
    --steps 30000 --seq-len 256 --batch-size 64 --accum-steps 4 \
    --lr 3e-4 --min-lr 3e-5 --warmup 1000 --weight-decay 0.1 \
    --d-model 256 --n-layers 8 --d-head 64 --top-k 4 \
    --bf16 --eval-every 1000 --seed 0
```

Logs every 1000 steps to `checkpoints/atome_1m_v1.train.json`.

## 944K Vanilla baseline (~$0.55, Vast A100 ~2.5h)

The ckpt that produced val_loss 0.9337 / ppl 2.54 — the result that
flipped the 60K headline.

```bash
PYTHONPATH=. python3 scripts/train_vanilla_1m.py \
    --data data/tinystories_full.txt \
    --output checkpoints/vanilla_1m_v1.pt \
    --steps 30000 --seq-len 256 --batch-size 64 --accum-steps 4 \
    --lr 3e-4 --min-lr 3e-5 --warmup 1000 --weight-decay 0.1 \
    --d-model 152 --n-layers 3 --n-heads 4 --d-ff 608 \
    --bf16 --eval-every 1000 --seed 0
```

`d_model=152 d_ff=608` is param-matched to atome's `d_model=256
n_layers=8` (950,608 params, +0.63% vs atome's 944,640).

## Export to MCU (60K demo)

```bash
python3 scripts/train_demo.py --data data/tinystories.txt --steps 1000 \
    --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt

python3 scripts/export_to_atome.py \
    --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome \
    --header

ls -la checkpoints/atome_demo.atome    # ~20 KB
```

Drop `atome_demo.atome.h` into your C project and call
`atome_load_from_const(...)` from the C engine in `c_engine/`.

## QEMU Cortex-M3 parity test (~5 min)

```bash
pytest tests/test_qemu_parity.py -v
```

Requires `qemu-system-arm` and `arm-none-eabi-gcc`. Builds the
firmware in `c_engine/targets/cortex-m3/`, loads a tiny model,
runs a single forward in QEMU, and compares logits bit-exact
against the Python reference.

## Run the C engine standalone

```bash
cd c_engine/upstream
gcc -O2 -o atome_cli atome.c
echo "Once upon a time" | ./atome_cli ../../checkpoints/atome_demo.atome
```

## Benchmark CPU forward

```bash
python3 scripts/benchmark.py
```

Prints tokens/sec at three representative configs. **Not** an MCU
number — for that, flash the firmware and measure on real silicon.

## Tests

```bash
pytest -q                                # all 146
pytest tests/test_power3.py -v           # 16 power-3 tests
pytest tests/test_vanilla_baseline.py    # 10 baseline sanity tests
pytest tests/test_parity_with_c.py       # bit-exact Python↔C parity
```
