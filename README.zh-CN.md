[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · **简体中文** · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# Atome LM

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20518644.svg)](https://doi.org/10.5281/zenodo.20518644)
[![tests](https://github.com/TilelliLab/atome-lm/actions/workflows/test.yml/badge.svg)](https://github.com/TilelliLab/atome-lm/actions/workflows/test.yml)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Model-FFB020)](https://huggingface.co/TilelliLab/atome-lm)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

> 一个带路由的三元微型语言模型的参考实现，配有逐位精确的 Python ↔ C99
> 推理引擎，为微控制器级别的 RAM 预算量身定制。

默认 60K 参数的语言模型，将三个已知思想融合到一个开放套件中：
三元权重（沿用 [BitNet b1.58](https://arxiv.org/abs/2402.17764)），
按 token 路由的混合 SSM + 稀疏注意力 + 局部卷积块
（沿用 [Hymba](https://arxiv.org/abs/2411.13676) 与
[MossNet](https://arxiv.org/abs/2510.26182)），
以及超微规模下的字节分词器
（沿用 [Guertler 2024](https://arxiv.org/abs/2405.14159)）。
**贡献在于集成，而非架构**：一条完整的
训练 → 三元导出 → 三进制打包 → C99 推理路径，并由测试强制保证
Python ↔ C 逐位精确的一致性。

**快速链接：**
- 📄 架构说明：[`PAPER.md`](PAPER.zh-CN.md)
- 🔬 诚实的结果，包括 944 K 处的反转：[`HONEST_RESULTS.md`](HONEST_RESULTS.zh-CN.md)
- 🌐 浏览器内实时演示（无需安装）：[atomelm.com/demo.html](https://atomelm.com/demo.html)
- 🏠 项目主页：[atomelm.com](https://atomelm.com)

**获取套件：** 训练代码、C 引擎、基准测试、论文以及训练好的权重——全部都在本仓库中，
以 [Apache 2.0 许可证](LICENSE) 发布。用
`scripts/train_demo.py` 在 CPU 上约 30 分钟即可训练你自己的检查点，或立即运行随附的
944 K 检查点。

**MCU 状态：** QEMU ARM（Cortex-M3，MPS2-AN385）的一致性通过到 FP32
epsilon 级别，并且一个可复现的**真实硅片演示**在物理 **ESP32-WROOM-32** 上运行 944 K 检查点
——连贯的文本、完全离线、约 1 tok/s——见
[`hardware/esp32-wroom32/`](hardware/esp32-wroom32/)（预编译二进制 + 串口日志 +
一条命令烧录）。该演示只是一个执行证明；**产品化落地**——Atome Secure Boot
Pack（签名的 `.atome` blob、dev/prod 标志、逐平台 secure-boot、认证）、逐平台加固——
我们作为集成服务在 [atomelm.com](https://atomelm.com) 上出售。

**权重已包含**在 `checkpoints/` 中：

- `atome_944k.bin`（271 KB）——打包后的 C 引擎 blob（`ATOME01` 格式），
  可由推理引擎直接加载。
- `atome_1m_v1.pt`（3.7 MB）——生成它的 PyTorch 源检查点；
  用它来微调（fine-tune）或以不同的 `#define` 重新导出。
- `vanilla_1m_v1.pt`（3.7 MB）——用于 [`HONEST_RESULTS.md`](HONEST_RESULTS.zh-CN.md) 中
  944K A/B 反转的 FP32 vanilla GPT 基线；
  随附提供，便于你端到端复现该对比。

944K 检查点是一个研究演示用的产物，而非产品：它很窄、有时不连贯，且仅在单一语料上训练。
它的存在是为了让架构*可运行*，而非设立质量标杆。使用随附训练代码复现它约需
~1–2 美元的 CPU/GPU；本套件中没有任何东西构成复现障碍。

---

## 可复现结果，狭窄区间

在 TinyStories 上，3000 步，单一随机种子：在固定参数量下，Atome 的
三元路由块达到 **6.31 ppl，而 vanilla GPT-FP32 基线为 8.12**（−22 %）；在固定闪存
预算下 **6.31 对 13.10**（−52 %）。在参数匹配时，磁盘占用小 16×（15.1 KB 对 237.5 KB）。

**该结果在 944 K 参数处反转**，此时 vanilla FP32 基线以约 11 % 胜出。Atome 的赌注刻意押在
sub-1M、MCU 级别的区间；超过它之后，三元的容量上限先弥合差距、随后反超。完整复现见
[`FRONTIER.md`](FRONTIER.zh-CN.md)，包括该反转在内的完整诚实解读见
[`HONEST_RESULTS.md`](HONEST_RESULTS.zh-CN.md)。

## 为什么

数据中心的 LLM 假定拥有数据中心的 RAM。一个卡在远程传感器墙上、助听器、电池供电玩具或恒温器里的 2 美元微控制器并没有那么多 RAM。Atome LM 就是这一约束下"模型设计"这一端的产物：

- **三元权重**（每张量 `{-α, 0, +α}`，BitNet b1.58 风格）。推理时矩阵乘法中没有浮点乘法。
- **3 通路块**（局部深度可分卷积、对角 SSM、top-k 稀疏注意力），由每 token 的软路由器混合。其设计与 Atome C99 引擎的结构体完全对应，使得训练好的检查点导出到闪存后，能在 Python 与 C 之间以**逐位精确的一致性**运行。
- **字节分词器。** 无需附带 BPE 词表。
- **将路由器熵作为校准信号。** 每 token 路由器分布的熵在每个位置都可免费观测。在 Atome-LLM 引擎默认的 60 K 参数规模、单一狭窄语料上，该信号是暴露出来的，但其在该规模下作为不确定性估计器的校准尚未在此测量。我们*初步*观察到（在一个**不属于本次发布**的更大的 3 M 参数模型中）该熵会跟踪域外输入并与每 token 损失相关——此处仅作为一项尚未公开的观察报告，测量将在未来发布中给出。

## 它是什么、不是什么

- **是：** 一个能在几美分级硬件上运行的三元 LM 的 Python 训练侧与架构。
- **不是：** 一个通用聊天机器人。在引擎默认配置（`d_model=64`、`n_layers=4`）下，模型约 60 K 参数，导出后约 20 KB 闪存。把它训练得很窄——单一领域（嵌入式系统问答、命令行帮助、单个 FAQ）——它就能在该范围内流利表达。在此尺寸下追求广度会产生不连贯的输出；这反映的是容量，而非架构。若需更多余量，请提高 `d_model` 与 `n_layers`（例如 `d_model=128, n_layers=6` ≈ 600 K 参数，打包后约 150 KB），并用相应的 `#define` 重新导出。

## 安装

```bash
./install.sh          # CPU-only venv + dependencies + environment check
```

或手动：`pip install -e .`（Python ≥ 3.10，PyTorch ≥ 2.0）。第一次来？
[`QUICKSTART.md`](QUICKSTART.zh-CN.md) 是从克隆到一个可用于微控制器的模型的 60 秒路径。

## 快速开始

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

## 训练一个微型演示

```bash
python scripts/train_demo.py --data path/to/text.txt --steps 1000 \
    --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt
```

内置的 `build_corpus.py` 会抓取几个宽松许可的来源
（`tinystories`、`esp-idf`、`mcu-wikipedia`）用于冒烟训练：

```bash
python scripts/build_corpus.py --source tinystories --max-bytes 500000 \
    --output data/tinystories.txt
```

## 试用一个检查点

```bash
python scripts/demo.py --checkpoint checkpoints/atome_demo.pt
# or, with no checkpoint, sanity-check the plumbing:
python scripts/demo.py --random --temperature 0.8 --top-p 0.9
```

该 REPL 会在提示词之上打印续写内容以及逐层的路由器熵条——那是免费暴露出来的元认知信号。

## 采样

`AtomeLM.generate(...)` 默认使用贪心 argmax（与 C 引擎的
`atome_predict_next` 相匹配）。可选的 `temperature`、`top_p`、`top_k`
以及 `generator=` 参数可启用带随机种子可复现性的 nucleus / top-k 采样。

## 基准测试

```bash
python scripts/benchmark.py            # tiny / default / large
```

三种代表性配置下的 CPU 前向 + 生成延迟。适合作为架构改动后的回归检查；不是 MCU 数字。

## 导出到微控制器

```bash
python scripts/export_to_atome.py \
    --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome \
    --header
```

这会产生一个扁平的 `.atome` 二进制，你可以从 C 中 `#include` 并用
[Atome C99 引擎](c_engine/) 的 `atome_load(...)` 加载。在默认配置下该二进制远小于
100 KB——能舒适地放进 ESP32-S3、STM32F4、RP2040、nRF52840、ESP32-C3。

## 架构

```
x → LayerNorm → ┬─→ Local  (depthwise causal conv k=5)        ─→┐
                ├─→ State  (diagonal SSM, O(L))                 ─→ Σ → +x
                └─→ Sparse (top-k attention, O(L·k))            ─→┘
                        ↑              ↑
                        │              router weights r ∈ Δ per token
                        └──────────────┘
```

三条通路。三种不同的归纳偏置。一个共享的、逐 token 的路由器，学习对每个位置哪条通路最合适。路由器的逐 token 熵在每一层被作为免费的逐位置不确定性信号暴露出来。

完整的架构故事见 [`PAPER.md`](PAPER.zh-CN.md)。

## 测试

```bash
pytest -q
```

## 许可证

Apache License 2.0——见 [`LICENSE`](LICENSE) 与 [`NOTICE`](NOTICE)。

本套件完全开放：可用于、修改、再分发，并在商业产品中出货，无需按席位或按设备付费。Apache 2.0 的专利授予涵盖此处发布的 3 通路三元路由架构。

`checkpoints/` 中已发布的检查点（atome_944k.bin、atome_1m_v1.pt、vanilla_1m_v1.pt）同样是 Apache-2.0。它们是参考 / 研究产物，而非产品。商业集成——硅片落地、Atome Secure Boot Pack（签名的 `.atome` blob、dev/prod 标志、逐平台 secure-boot、认证）、逐平台加固、对更大的内部 V2 模型的自定义领域微调——可在 [atomelm.com](https://atomelm.com) 获得。

## 引用

```bibtex
@software{atome_llm_2026,
  title  = {Atome LM: a tiny ternary language model for microcontroller deployment},
  author = {Atome LM contributors},
  year   = {2026},
  note   = {Apache 2.0, https://atomelm.com},
}
```
