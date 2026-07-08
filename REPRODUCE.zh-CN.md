[English](REPRODUCE.md) · [Français](REPRODUCE.fr.md) · [Español](REPRODUCE.es.md) · **简体中文** · [Deutsch](REPRODUCE.de.md) · [日本語](REPRODUCE.ja.md) <!-- i18n-switcher -->

# Atome LM — 复现指南

`FRONTIER.md` 和 `HONEST_RESULTS.md` 上的每一个数字都能追溯到
本文件中的一条命令。除非另有说明否则仅 CPU；预算数字假定
RunPod / Vast A100/A6000 的价格。

## 设置（3 分钟）

```bash
pip install -e .
pytest -q                                # 146/146 should pass
```

## 60K A/B 扫描（约 30 分钟 CPU，0 美元）

复现 FRONTIER.md 中的参数公平（Atome 22 % > vanilla）和闪存公平
（Atome 52 % > vanilla）表格。

```bash
PYTHONPATH=. python3 scripts/build_corpus.py --source tinystories \
    --max-bytes 500000 --output data/tinystories.txt

PYTHONPATH=. python3 scripts/run_ab_sweep.py \
    --train data/tinystories.txt --steps 3000 \
    --output ab_results.json

python3 -c "import json; r=json.load(open('ab_results.json')); \
    [print(f\"{m}: ppl={d['val_ppl']:.2f}\") for m,d in r.items()]"
```

## 944K Atome 单一种子（约 0.40 美元，RunPod A40 约 4h）

产生 val_loss 1.0545 / ppl 2.87 的那个 ckpt。

先决条件——构建完整的 TinyStories 语料（一次性，约 5 分钟）：

```bash
PYTHONPATH=. python3 scripts/build_corpus.py --source tinystories \
    --output data/tinystories_full.txt
```

然后训练：

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

每 1000 步记录到 `checkpoints/atome_1m_v1.train.json`。

## 944K Vanilla 基线（约 0.55 美元，Vast A100 约 2.5h）

产生 val_loss 0.9337 / ppl 2.54 的那个 ckpt——翻转了 60K 要点的
那个结果。

```bash
PYTHONPATH=. python3 scripts/train_vanilla_1m.py \
    --data data/tinystories_full.txt \
    --output checkpoints/vanilla_1m_v1.pt \
    --steps 30000 --seq-len 256 --batch-size 64 --accum-steps 4 \
    --lr 3e-4 --min-lr 3e-5 --warmup 1000 --weight-decay 0.1 \
    --d-model 152 --n-layers 3 --n-heads 4 --d-ff 608 \
    --bf16 --eval-every 1000 --seed 0
```

`d_model=152 d_ff=608` 在参数上与 atome 的 `d_model=256
n_layers=8` 匹配（950,608 参数，比 atome 的 944,640 多 +0.63 %）。

## 导出到 MCU（60K 演示）

```bash
python3 scripts/train_demo.py --data data/tinystories.txt --steps 1000 \
    --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt

python3 scripts/export_to_atome.py \
    --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome \
    --header

ls -la checkpoints/atome_demo.atome    # ~20 KB
```

把 `atome_demo.atome.h` 放进你的 C 项目，并从 `c_engine/` 的 C 引擎调用
`atome_load_from_const(...)`。

## QEMU Cortex-M3 一致性测试（约 5 分钟）

```bash
pytest tests/test_qemu_parity.py -v
```

需要 `qemu-system-arm` 和 `arm-none-eabi-gcc`。它会构建
`c_engine/targets/cortex-m3/` 中的固件，加载一个微型模型，
在 QEMU 中运行一次前向，并将 logits 与 Python 参考
逐位精确地对比。

## 独立运行 C 引擎

```bash
cd c_engine/upstream
gcc -O2 -o atome_cli atome.c
echo "Once upon a time" | ./atome_cli ../../checkpoints/atome_demo.atome
```

## 基准测试 CPU 前向

```bash
python3 scripts/benchmark.py
```

在三种代表性配置下打印 tokens/sec。这**不是**一个
MCU 数字——为此，请烧录固件并在真实硅片上测量。

## 测试

```bash
pytest -q                                # all 146
pytest tests/test_power3.py -v           # 16 power-3 tests
pytest tests/test_vanilla_baseline.py    # 10 baseline sanity tests
pytest tests/test_parity_with_c.py       # bit-exact Python↔C parity
```
