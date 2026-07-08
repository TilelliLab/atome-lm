[English](REPRODUCE.md) · [Français](REPRODUCE.fr.md) · **Español** · [简体中文](REPRODUCE.zh-CN.md) · [Deutsch](REPRODUCE.de.md) · [日本語](REPRODUCE.ja.md) <!-- i18n-switcher -->

# Atome LM — Guía de reproducción

Cada número de `FRONTIER.md` y `HONEST_RESULTS.md` remonta a un
comando de este archivo. Solo CPU salvo indicación; las cifras de presupuesto asumen
precios de RunPod / Vast A100/A6000.

## Configuración (3 min)

```bash
pip install -e .
pytest -q                                # 146/146 should pass
```

## Barrido A/B 60K (~30 min CPU, 0 $)

Reproduce las tablas params-justo (Atome 22 % > vanilla) y flash-justo
(Atome 52 % > vanilla) de FRONTIER.md.

```bash
PYTHONPATH=. python3 scripts/build_corpus.py --source tinystories \
    --max-bytes 500000 --output data/tinystories.txt

PYTHONPATH=. python3 scripts/run_ab_sweep.py \
    --train data/tinystories.txt --steps 3000 \
    --output ab_results.json

python3 -c "import json; r=json.load(open('ab_results.json')); \
    [print(f\"{m}: ppl={d['val_ppl']:.2f}\") for m,d in r.items()]"
```

## Atome 944K semilla única (~0,40 $, RunPod A40 ~4h)

El ckpt que produjo val_loss 1,0545 / ppl 2,87.

Prerrequisito — construir el corpus TinyStories completo (una vez, ~5 min):

```bash
PYTHONPATH=. python3 scripts/build_corpus.py --source tinystories \
    --output data/tinystories_full.txt
```

Luego entrenar:

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

Registra cada 1000 pasos en `checkpoints/atome_1m_v1.train.json`.

## Referencia vanilla 944K (~0,55 $, Vast A100 ~2,5h)

El ckpt que produjo val_loss 0,9337 / ppl 2,54 — el resultado que
volteó el titular de 60K.

```bash
PYTHONPATH=. python3 scripts/train_vanilla_1m.py \
    --data data/tinystories_full.txt \
    --output checkpoints/vanilla_1m_v1.pt \
    --steps 30000 --seq-len 256 --batch-size 64 --accum-steps 4 \
    --lr 3e-4 --min-lr 3e-5 --warmup 1000 --weight-decay 0.1 \
    --d-model 152 --n-layers 3 --n-heads 4 --d-ff 608 \
    --bf16 --eval-every 1000 --seed 0
```

`d_model=152 d_ff=608` está emparejado en parámetros a `d_model=256
n_layers=8` de atome (950.608 params, +0,63 % vs los 944.640 de atome).

## Exportar a MCU (demo 60K)

```bash
python3 scripts/train_demo.py --data data/tinystories.txt --steps 1000 \
    --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt

python3 scripts/export_to_atome.py \
    --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome \
    --header

ls -la checkpoints/atome_demo.atome    # ~20 KB
```

Deja `atome_demo.atome.h` en tu proyecto C y llama a
`atome_load_from_const(...)` desde el motor C de `c_engine/`.

## Test de paridad QEMU Cortex-M3 (~5 min)

```bash
pytest tests/test_qemu_parity.py -v
```

Requiere `qemu-system-arm` y `arm-none-eabi-gcc`. Construye el
firmware en `c_engine/targets/cortex-m3/`, carga un modelo minúsculo,
ejecuta un solo forward en QEMU, y compara los logits al bit
contra la referencia de Python.

## Ejecutar el motor C de forma independiente

```bash
cd c_engine/upstream
gcc -O2 -o atome_cli atome.c
echo "Once upon a time" | ./atome_cli ../../checkpoints/atome_demo.atome
```

## Benchmark forward de CPU

```bash
python3 scripts/benchmark.py
```

Imprime tokens/seg en tres configuraciones representativas. **No** es un
número MCU — para eso, flashea el firmware y mide en silicio real.

## Tests

```bash
pytest -q                                # all 146
pytest tests/test_power3.py -v           # 16 power-3 tests
pytest tests/test_vanilla_baseline.py    # 10 baseline sanity tests
pytest tests/test_parity_with_c.py       # bit-exact Python↔C parity
```
