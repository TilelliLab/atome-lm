[English](REPRODUCE.md) · [Français](REPRODUCE.fr.md) · [Español](REPRODUCE.es.md) · [简体中文](REPRODUCE.zh-CN.md) · **Deutsch** · [日本語](REPRODUCE.ja.md) <!-- i18n-switcher -->

# Atome LM — Reproduktions-Leitfaden

Jede Zahl in `FRONTIER.md` und `HONEST_RESULTS.md` lässt sich auf einen
Befehl in dieser Datei zurückführen. Nur CPU, sofern nicht anders vermerkt; Budgetzahlen nehmen
RunPod-/Vast-A100/A6000-Preise an.

## Setup (3 Min.)

```bash
pip install -e .
pytest -q                                # 146/146 should pass
```

## 60K-A/B-Sweep (~30 Min. CPU, 0 $)

Reproduziert die Param-fair- (Atome 22 % > vanilla) und Flash-fair-
(Atome 52 % > vanilla) Tabellen in FRONTIER.md.

```bash
PYTHONPATH=. python3 scripts/build_corpus.py --source tinystories \
    --max-bytes 500000 --output data/tinystories.txt

PYTHONPATH=. python3 scripts/run_ab_sweep.py \
    --train data/tinystories.txt --steps 3000 \
    --output ab_results.json

python3 -c "import json; r=json.load(open('ab_results.json')); \
    [print(f\"{m}: ppl={d['val_ppl']:.2f}\") for m,d in r.items()]"
```

## 944K Atome, einzelner Seed (~0,40 $, RunPod A40 ~4h)

Der ckpt, der val_loss 1,0545 / ppl 2,87 erzeugt hat.

Voraussetzung — den vollständigen TinyStories-Korpus bauen (einmalig, ~5 Min.):

```bash
PYTHONPATH=. python3 scripts/build_corpus.py --source tinystories \
    --output data/tinystories_full.txt
```

Dann trainieren:

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

Loggt alle 1000 Schritte nach `checkpoints/atome_1m_v1.train.json`.

## 944K-Vanilla-Baseline (~0,55 $, Vast A100 ~2,5h)

Der ckpt, der val_loss 0,9337 / ppl 2,54 erzeugt hat — das Ergebnis, das
die 60K-Kernaussage kippte.

```bash
PYTHONPATH=. python3 scripts/train_vanilla_1m.py \
    --data data/tinystories_full.txt \
    --output checkpoints/vanilla_1m_v1.pt \
    --steps 30000 --seq-len 256 --batch-size 64 --accum-steps 4 \
    --lr 3e-4 --min-lr 3e-5 --warmup 1000 --weight-decay 0.1 \
    --d-model 152 --n-layers 3 --n-heads 4 --d-ff 608 \
    --bf16 --eval-every 1000 --seed 0
```

`d_model=152 d_ff=608` ist parametergleich zu atomes `d_model=256
n_layers=8` (950.608 Params, +0,63 % vs. atomes 944.640).

## Export auf MCU (60K-Demo)

```bash
python3 scripts/train_demo.py --data data/tinystories.txt --steps 1000 \
    --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt

python3 scripts/export_to_atome.py \
    --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome \
    --header

ls -la checkpoints/atome_demo.atome    # ~20 KB
```

Lege `atome_demo.atome.h` in dein C-Projekt und rufe
`atome_load_from_const(...)` aus der C-Engine in `c_engine/` auf.

## QEMU-Cortex-M3-Paritätstest (~5 Min.)

```bash
pytest tests/test_qemu_parity.py -v
```

Benötigt `qemu-system-arm` und `arm-none-eabi-gcc`. Baut die
Firmware in `c_engine/targets/cortex-m3/`, lädt ein winziges Modell,
führt einen einzelnen Forward in QEMU aus und vergleicht die Logits bit-genau
mit der Python-Referenz.

## Die C-Engine eigenständig ausführen

```bash
cd c_engine/upstream
gcc -O2 -o atome_cli atome.c
echo "Once upon a time" | ./atome_cli ../../checkpoints/atome_demo.atome
```

## CPU-Forward benchmarken

```bash
python3 scripts/benchmark.py
```

Gibt Tokens/Sek. bei drei repräsentativen Konfigurationen aus. **Keine**
MCU-Zahl — dafür flashe die Firmware und miss auf echtem Silizium.

## Tests

```bash
pytest -q                                # all 146
pytest tests/test_power3.py -v           # 16 power-3 tests
pytest tests/test_vanilla_baseline.py    # 10 baseline sanity tests
pytest tests/test_parity_with_c.py       # bit-exact Python↔C parity
```
