[English](REPRODUCE.md) · **Français** · [Español](REPRODUCE.es.md) · [简体中文](REPRODUCE.zh-CN.md) · [Deutsch](REPRODUCE.de.md) · [日本語](REPRODUCE.ja.md) <!-- i18n-switcher -->

# Atome LM — Guide de reproduction

Chaque nombre de `FRONTIER.md` et `HONEST_RESULTS.md` remonte à une
commande de ce fichier. CPU seulement sauf indication contraire ; les chiffres de budget supposent
la tarification RunPod / Vast A100/A6000.

## Installation (3 min)

```bash
pip install -e .
pytest -q                                # 146/146 should pass
```

## Balayage A/B 60K (~30 min CPU, 0 $)

Reproduit les tableaux params-équit. (Atome 22 % > vanilla) et flash-équit.
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

## Atome 944K graine unique (~0,40 $, RunPod A40 ~4h)

Le ckpt qui a produit val_loss 1,0545 / ppl 2,87.

Prérequis — construire le corpus TinyStories complet (une seule fois, ~5 min) :

```bash
PYTHONPATH=. python3 scripts/build_corpus.py --source tinystories \
    --output data/tinystories_full.txt
```

Puis entraîner :

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

Journalise tous les 1000 pas dans `checkpoints/atome_1m_v1.train.json`.

## Référence vanilla 944K (~0,55 $, Vast A100 ~2,5h)

Le ckpt qui a produit val_loss 0,9337 / ppl 2,54 — le résultat qui
a fait basculer le titre 60K.

```bash
PYTHONPATH=. python3 scripts/train_vanilla_1m.py \
    --data data/tinystories_full.txt \
    --output checkpoints/vanilla_1m_v1.pt \
    --steps 30000 --seq-len 256 --batch-size 64 --accum-steps 4 \
    --lr 3e-4 --min-lr 3e-5 --warmup 1000 --weight-decay 0.1 \
    --d-model 152 --n-layers 3 --n-heads 4 --d-ff 608 \
    --bf16 --eval-every 1000 --seed 0
```

`d_model=152 d_ff=608` est apparié en paramètres à `d_model=256
n_layers=8` d'atome (950 608 params, +0,63 % vs les 944 640 d'atome).

## Exporter vers MCU (démo 60K)

```bash
python3 scripts/train_demo.py --data data/tinystories.txt --steps 1000 \
    --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt

python3 scripts/export_to_atome.py \
    --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome \
    --header

ls -la checkpoints/atome_demo.atome    # ~20 KB
```

Déposez `atome_demo.atome.h` dans votre projet C et appelez
`atome_load_from_const(...)` depuis le moteur C de `c_engine/`.

## Test de parité QEMU Cortex-M3 (~5 min)

```bash
pytest tests/test_qemu_parity.py -v
```

Nécessite `qemu-system-arm` et `arm-none-eabi-gcc`. Construit le
firmware dans `c_engine/targets/cortex-m3/`, charge un modèle minuscule,
exécute un forward unique dans QEMU, et compare les logits au bit près
avec la référence Python.

## Exécuter le moteur C en autonome

```bash
cd c_engine/upstream
gcc -O2 -o atome_cli atome.c
echo "Once upon a time" | ./atome_cli ../../checkpoints/atome_demo.atome
```

## Benchmark forward CPU

```bash
python3 scripts/benchmark.py
```

Affiche les jetons/sec sur trois configurations représentatives. Ce n'est **pas** un
nombre MCU — pour cela, flashez le firmware et mesurez sur silicium réel.

## Tests

```bash
pytest -q                                # all 146
pytest tests/test_power3.py -v           # 16 power-3 tests
pytest tests/test_vanilla_baseline.py    # 10 baseline sanity tests
pytest tests/test_parity_with_c.py       # bit-exact Python↔C parity
```
