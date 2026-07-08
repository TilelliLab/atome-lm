[English](QUICKSTART.md) · [Français](QUICKSTART.fr.md) · [Español](QUICKSTART.es.md) · **简体中文** · [Deutsch](QUICKSTART.de.md) · [日本語](QUICKSTART.ja.md) <!-- i18n-switcher -->

# Atome LM — 快速开始

从克隆到一个训练好、可用于微控制器的模型的 60 秒路径。
完整故事见 [README.md](README.zh-CN.md) 和 [REPRODUCE.md](REPRODUCE.zh-CN.md)。

## 1. 安装（仅 CPU，无 GPU）

```bash
./install.sh
. .venv/bin/activate
```

`install.sh` 会创建一个本地 `.venv`，安装仅 CPU 版 PyTorch 和 Atome
LM，并运行 `check_env.py`。随时重新运行 `python check_env.py` 即可
重新验证环境。

## 2. 训练一个微型演示模型

一份约 256 KB、宽松许可的 TinyStories 语料样本随附在
`data/sample.txt` 中，因此这一步可离线运行：

```bash
python scripts/train_demo.py --data data/sample.txt --steps 1000 \
    --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt
```

若需更大的语料，用随附的构建器抓取一个：

```bash
python scripts/build_corpus.py --source tinystories \
    --max-bytes 500000 --output data/tinystories.txt
```

## 3. 与它对话

```bash
python scripts/demo.py --checkpoint checkpoints/atome_demo.pt
```

该 REPL 会打印续写内容以及逐层的路由器熵条——那个免费的逐 token 不确定性信号。

## 4. 导出到微控制器

```bash
python scripts/export_to_atome.py \
    --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome --header
```

在默认配置下，`.atome` 二进制远小于 100 KB。把生成的
`.h` 放进一个 C 项目，并用 `c_engine/` 中的引擎加载它。

## 5. 运行测试

```bash
pytest -q
```

QEMU Cortex-M3 一致性测试需要 `qemu-system-arm`、`arm-none-eabi-gcc`
和 `xxd` 在 `PATH` 中；当工具链缺失时它们会被**跳过**（skipped，而非失败）。

---

**训练好的权重已随附**在 `checkpoints/` 中——`atome_944k.bin`
（打包的 C 引擎 blob）、`atome_1m_v1.pt`（PyTorch 源）和
`vanilla_1m_v1.pt`（用于 [HONEST_RESULTS.md](HONEST_RESULTS.zh-CN.md) 中 944 K
反转 A/B 的 FP32 基线）。若你想在不先训练的情况下运行模型：

```bash
python scripts/demo.py --checkpoint checkpoints/atome_1m_v1.pt
```

若你想从零训练自己的模型，请遵循上面的
`scripts/train_demo.py` 流程——它能在 CPU 上约 30 分钟内产生一个
60 K 参数的模型。
