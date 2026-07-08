[English](FRONTIER.md) · [Français](FRONTIER.fr.md) · [Español](FRONTIER.es.md) · **简体中文** · [Deutsch](FRONTIER.de.md) · [日本語](FRONTIER.ja.md) <!-- i18n-switcher -->

# Atome LM — 前沿发现

> **更新 2026-05-11 — 944K 处的扩容 A/B 反转了要点。**
> 同样的配方、同样的验证切片、同样的公平性审计，一个 944K 参数的 vanilla
> GPT-FP32 基线（950,608 参数，比 Atome 的 944,640 多 +0.63 %）达到
> 验证损失 0.9337 / ppl 2.54，在 944K 处于损失上以 11.4 %、
> 于困惑度上以 11.5 % 胜过 Atome 三元。下面 +22 % 参数公平 / +52 %
> 闪存公平的收益仅在 **60K 参数 MCU 区间**成立，且仅在
> 那个区间。超过约 1M 参数后，3 通路块的归纳偏置
> 就不再替代容量，而开始约束它。
> 诚实的表述是：*Atome 的赌注是小模型区间——
> sub-1M 参数、MCU 级别部署、无网络。* 关于 944K 的完整解读见
> [`HONEST_RESULTS.md`](HONEST_RESULTS.zh-CN.md)。
> 多种子待办。

**日期。** 2026-05-09。仅 CPU，无 GPU。
**硬件。** 4 线程 CPU 机器。PyTorch 2.x，FP32 参考路径。
**语料。** TinyStories 验证切片，500 KB UTF-8（约 99.9 % ASCII）。
在 64 字节块上按 90/10 划分训练/评估 → 7,030 个训练块 /
782 个留出（held-out）块。
**优化器。** AdamW，lr 3e-4，batch 16，seq 64，3,000 步。
**单一种子**（种子 0）。结果未跨种子复制。

本文档报告了 Atome 的三元 3 通路架构与 vanilla 仅解码器 Transformer（FP32）之间，在固定参数量与固定闪存预算下的首次同类对比（apples-to-apples）A/B。最接近的已发表同类是 Andrej Karpathy 的 `Stories260K`——一个在 TinyStories 上训练的 260 K 参数 FP32 普通 transformer。Atome 的前沿主张是"更小的闪存、更好的质量、更少的每权重比特数，*并且*可部署在 2 美元的微控制器上"。本页直接检验其中前三项主张；MCU 部署通过逐位精确的 Python ↔ C ↔ Cortex-M3（QEMU）一致性单独验证（见 `tests/test_qemu_parity.py`）。

## 一句话概览（TL;DR）

| 模型 | 参数 | 位/权重 | 磁盘 | bpb ↓ | 困惑度 ↓ |
|---|---:|---:|---:|---:|---:|
| **Atome 3 通路，三元** | **60,800** | **1.58** | **15.1 KB**¹ / **17.2 KB**² | **2.66** | **6.31** |
| Vanilla GPT，FP32（参数公平） | 60,808 | 32 | 237.5 KB | 3.02 | 8.12 |
| Vanilla GPT，FP32（闪存公平） | 5,968 | 32 | 23.3 KB | 3.71 | 13.10 |

¹ ATOME01，4 trit/字节（当前 C 引擎读取此格式）。
² ATOME02，5 trit/字节的三进制打包——小 14.4 %，接近
`log2(3) ≈ 1.585` 位/trit 的信息论下界。Python
编码器 + 解码器今日出货；C 解码器是未来的改动。

## 这证明了什么

1. **在相同参数量下，三元 3 通路架构在困惑度上以 22 %（6.31 对 8.12）胜过普通 transformer，同时少用 16× 的磁盘。**

   vanilla 基线*并非*过参数化——它在 60.8 K 参数处匹配
   （`d_model=44, n_layers=3, n_heads=4, d_ff=44`，
   通过暴力搜索选出以落在目标 8 参数之内）。这与每一篇公开的
   微型 LM 论文（`Stories260K`、TinyStories 论文、小规模 BitNet）所用的
   是同一种架构，除去琐碎差异。

2. **在相同闪存预算下，三元 3 通路架构在困惑度上以 52 %（6.31 对 13.10）胜过普通 transformer。**

   闪存公平的 vanilla 基线是 `d_model=8, n_layers=2,
   n_heads=4, d_ff=24`。它与 Atome 的 ATOME01 二进制（15.1 KB）和
   ATOME02 二进制（17.2 KB）落在同一个 20–25 KB 的磁盘预算内。

3. **1.58 位权重在相同架构参数下相比 FP32 花费约 22 % 的困惑度**——但 FP32 版本花费 16× 的闪存。在任何以闪存为瓶颈的设备上（我们瞄准的每一个 MCU），三元胜出。在任何以计算为瓶颈、闪存免费的设备上（服务器 CPU），FP32 在质量上胜出。

4. **ATOME02 三进制打包达到 1.6 位/trit——距离 1.585 位/trit 的信息论下界不到 1 %**——并在同一个训练好的 60.8 K 参数模型上把磁盘二进制从 20.1 KB 降到 17.2 KB。C 解码器仍待办。

## 这没有证明什么

- **仅单一种子。** 三个数字都来自种子 0。我们尚未运行
  多种子以估计方差。相对于此规模下典型的种子噪声，22 % / 52 % 的
  差距非常大，但方差
  未经测量。
- **单一语料。** TinyStories 是一个宽容的目标——短篇故事
  且词汇受限。更广领域或代码语料可能偏向
  vanilla 注意力。我们尚未测量。
- **单一训练时长。** 3,000 步远未达到
  收敛。相对排名可能随着更多训练而
  互换或放大。一次 10 K 步的运行正在进行中；若它
  改变要点，我们会更新本页。
- **无真实硅片。** 所有 MCU 声明都在 QEMU
  Cortex-M3 上验证，而非物理 RP2040 / STM32 硬件。真实硅片上的
  tokens/sec 与每 token 焦耳数仍待办。
- **Stories260K 直接对比仍待办。** Karpathy 的确切
  设置是 `Stories260K`，260 K 参数 + 一个 32 K token 的 SentencePiece
  词表。我们的字节分词器 + 60 K 配置小约 4×。一次真正的
  与 `Stories260K` 的同类对比需要 (a) 我们扩容
  到 260 K 参数和一个 SentencePiece 分词器，或 (b) Karpathy 的
  设置在 60 K 参数下用字节分词器重新训练。二者
  均未完成。

## 与已发表前沿的对比

| 系统 | 最小目标 | 参数 | 位/权重 | 真实 MCU？ | 架构是否胜过 vanilla？ |
|---|---|---:|---:|---|---|
| Microsoft BitNet b1.58 | 服务器 CPU | 700 M – 3 B | 1.58 | 否 | （在规模上打平） |
| Meta MobileLLM | 智能手机 | 125 M – 1 B | 4–8 | 否 | 是（对比同尺寸 vanilla） |
| Karpathy `Stories260K` | 笔记本 / 浏览器 | 260 K | 32 | 无固件 | 不适用（就是 vanilla 基线） |
| RP2040 上的 llama.cpp（业余） | RP2040 + SD | ~1 B（换页） | 4 | 是（慢，需 SD） | 未测量 |
| TFLite Micro / Edge Impulse | Cortex-M0+ | – | 8 | 是 | 无语言任务 |
| **Atome LM（本工作）** | **Cortex-M0+，16 KB SRAM** | **60 K** | **1.58** | **QEMU 是，硅片待办** | **参数公平 +22 %，闪存公平 +52 %** |

更小、更节省比特，*并且*在我们瞄准的预算下架构上胜过 vanilla。据我们所知，这是路由架构胜利在相同闪存预算下相对 vanilla 基线被直接测量到的最小的已发表 LM。

## 复现

```bash
# from the repository root
PYTHONPATH=. python3 scripts/build_corpus.py --source tinystories \
    --max-bytes 500000 --output data/tinystories.txt

PYTHONPATH=. python3 scripts/run_ab_sweep.py \
    --train data/tinystories.txt --steps 3000 \
    --output ab_results.json
```

`ab_results.json` 将包含与上表相同的数字
（除 PyTorch 矩阵乘法核中依赖平台的舍入之外）。

## 开放问题 / 下一步推进

- **A1.** 多种子（3 种子 × 3 配置）以估计 22 % / 52 %
  差距上的方差。
- **A2.** 把三者都训练到 ≥ 10 K 步。差距会缩小、保持，
  还是扩大？
- **A3.** 消融：三条通路（局部卷积、对角
  SSM、top-k 稀疏注意力）中哪一条承载了架构胜利的大部分？
  逐一去掉，测量。
- **A4.** 为 ATOME02 出货一个 C 解码器。把演示二进制从
  20.1 KB 削到 17.2 KB，而无需在别处改动代码。
- **A5.** 真实硅片。用引擎 + 这个 60.8 K ckpt 烧录一块 RP2040。
  测量 tokens/sec、每 token 焦耳数。**那个把主张从"前沿"
  变成事实的要点数字。**
- **A6.** 从一个强大的 LLM 教师蒸馏（10 MB 由前沿模型生成的、
  精挑细选的窄领域文本）到同一个 60 K Atome。
  开放问题：架构优势在蒸馏下是否会
  叠加放大？
- **A7.** Bug A 修复（Python `generate` ↔ C `atome_generate`
  短提示 SSM 发散）。触及逐位精确一致性
  契约——需要用户明确签字同意。

## 存档文件

- `ab_results.json` — 此处报告的运行的精确数字与配置。
- 训练好的 A/B 检查点（`atome_60k_ternary`、`vanilla_60k_fp32`、
  `vanilla_6k_fp32`）*不*出货——用下面的测试装置重新生成它们
  （本套件从零训练）。
- `atome_llm/baselines/vanilla_transformer.py` — 基线。
- `scripts/run_ab_sweep.py` — 测试装置。
- `tests/test_vanilla_baseline.py` — 对基线的 10 个健全性测试。
- `tests/test_export_packed.py` — 对 ATOME02 往返的 5 个测试。
- `tests/test_trit_packing.py` — 对三进制打包器的 11 个测试。
