[English](REPRODUCE.md) · [Français](REPRODUCE.fr.md) · [Español](REPRODUCE.es.md) · [简体中文](REPRODUCE.zh-CN.md) · [Deutsch](REPRODUCE.de.md) · **日本語** <!-- i18n-switcher -->

# Atome LM — 再現ガイド

`FRONTIER.md` と `HONEST_RESULTS.md` のすべての数値は、本ファイル内の
コマンドまでたどれます。特記なき限り CPU のみ。予算の数字は
RunPod / Vast A100/A6000 の価格を想定します。

## セットアップ（3 分）

```bash
pip install -e .
pytest -q                                # 146/146 should pass
```

## 60K A/B スイープ（約 30 分 CPU、0 ドル）

FRONTIER.md のパラメータ公平（Atome 22 % > vanilla）とフラッシュ公平
（Atome 52 % > vanilla）の表を再現します。

```bash
PYTHONPATH=. python3 scripts/build_corpus.py --source tinystories \
    --max-bytes 500000 --output data/tinystories.txt

PYTHONPATH=. python3 scripts/run_ab_sweep.py \
    --train data/tinystories.txt --steps 3000 \
    --output ab_results.json

python3 -c "import json; r=json.load(open('ab_results.json')); \
    [print(f\"{m}: ppl={d['val_ppl']:.2f}\") for m,d in r.items()]"
```

## 944K Atome 単一シード（約 0.40 ドル、RunPod A40 約 4h）

val_loss 1.0545 / ppl 2.87 を生成した ckpt。

前提条件——完全な TinyStories コーパスをビルドする（一度きり、約 5 分）：

```bash
PYTHONPATH=. python3 scripts/build_corpus.py --source tinystories \
    --output data/tinystories_full.txt
```

そして学習：

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

1000 ステップごとに `checkpoints/atome_1m_v1.train.json` へログします。

## 944K Vanilla ベースライン（約 0.55 ドル、Vast A100 約 2.5h）

val_loss 0.9337 / ppl 2.54 を生成した ckpt——60K の要点を
ひっくり返した結果です。

```bash
PYTHONPATH=. python3 scripts/train_vanilla_1m.py \
    --data data/tinystories_full.txt \
    --output checkpoints/vanilla_1m_v1.pt \
    --steps 30000 --seq-len 256 --batch-size 64 --accum-steps 4 \
    --lr 3e-4 --min-lr 3e-5 --warmup 1000 --weight-decay 0.1 \
    --d-model 152 --n-layers 3 --n-heads 4 --d-ff 608 \
    --bf16 --eval-every 1000 --seed 0
```

`d_model=152 d_ff=608` は atome の `d_model=256
n_layers=8` にパラメータ一致します（950,608 パラメータ、atome の 944,640 に対し +0.63 %）。

## MCU へのエクスポート（60K デモ）

```bash
python3 scripts/train_demo.py --data data/tinystories.txt --steps 1000 \
    --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt

python3 scripts/export_to_atome.py \
    --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome \
    --header

ls -la checkpoints/atome_demo.atome    # ~20 KB
```

`atome_demo.atome.h` を C プロジェクトに入れ、`c_engine/` の C エンジンから
`atome_load_from_const(...)` を呼び出してください。

## QEMU Cortex-M3 一致テスト（約 5 分）

```bash
pytest tests/test_qemu_parity.py -v
```

`qemu-system-arm` と `arm-none-eabi-gcc` が必要です。`c_engine/targets/cortex-m3/` の
ファームウェアをビルドし、微小なモデルを読み込み、QEMU で単一の forward を
実行し、logits を Python 参照とビット単位で厳密に比較します。

## C エンジンを単独で実行する

```bash
cd c_engine/upstream
gcc -O2 -o atome_cli atome.c
echo "Once upon a time" | ./atome_cli ../../checkpoints/atome_demo.atome
```

## CPU forward のベンチマーク

```bash
python3 scripts/benchmark.py
```

3 つの代表的な構成での tokens/sec を出力します。これは MCU の数値では
**ありません**——それにはファームウェアを書き込み、実シリコンで測定してください。

## テスト

```bash
pytest -q                                # all 146
pytest tests/test_power3.py -v           # 16 power-3 tests
pytest tests/test_vanilla_baseline.py    # 10 baseline sanity tests
pytest tests/test_parity_with_c.py       # bit-exact Python↔C parity
```
