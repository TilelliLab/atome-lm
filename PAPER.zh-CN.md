[English](PAPER.md) · [Français](PAPER.fr.md) · [Español](PAPER.es.md) · **简体中文** · [Deutsch](PAPER.de.md) · [日本語](PAPER.ja.md) <!-- i18n-switcher -->

# Atome LM — 面向微控制器原生三元语言模型的架构

## 1. 动机

如今能"真正开口说话"的最小语言模型，参数量落在 100 M–1 B 的范围。这些模型无一例外都需要比 2 美元微控制器所能提供的更多的 RAM 和更高的内存带宽。这些模型的架构选择——完整注意力、稠密 FFN、多 bank MoE、检索增强通路——都是在"RAM 便宜"这一假设下做出的。Atome LM 从相反的假设出发：RAM 是压倒其他一切考量的约束。

其结果是一个刻意设计得很窄的架构，端到端地为与一个固定形状的 C99 推理引擎兼容而设计——该引擎运行在只有千字节（而非兆字节）工作 RAM 的芯片上。

## 2. 来自引擎的约束

Atome C99 引擎的 `atome_block_t` 结构体被固定为：

```
norm        : LayerNorm
local_conv  : depthwise causal conv, ternary kernel
ssm         : diagonal SSM (per-channel a, b, c_out, FP32)
attn        : top-k causal attention, ternary Q/K/V
router      : ternary linear → softmax over 3 pathways
```

为这三条通路的每一条输出、以及为 SSM 隐藏状态和注意力 KV 缓存，都存在静态缓冲区。没有宽卷积的缓冲区，没有稠密 FFN 的缓冲区，没有为多 bank 权重的预留，三元核中没有逐行缩放。试图训练一个更宽的架构再"事后塞进去"，要么需要重新生成 C 结构体（打破本项目赖以立身的逐位精确一致性契约），要么会出货一些在推理时被悄悄丢弃的、不受支持的通路。

因此 Atome LM 与引擎完全对应：三条通路、逐张量缩放、字节分词器、无位置嵌入、序列长度在编译期由 `ATOME_MAX_SEQ` 封顶。

## 3. 块

```
x → LayerNorm → ┬─→ Local   (depthwise causal conv, k=5)        ─→┐
                ├─→ State   (diagonal SSM, O(L))                  ─→ Σ → +x
                └─→ Sparse  (top-k attention, O(L·k))             ─→┘
                        ↑              ↑
                        │              router weights r ∈ Δ per token
                        └──────────────┘
```

三种结构上不同的运算：

| # | 名称   | 运算                     | 作用                          |
|---|--------|-------------------------|------------------------------|
| 1 | Local  | 深度可分卷积 k=5         | 二元组、词边界                |
| 2 | State  | 对角 SSM                 | 长程主题携带                  |
| 3 | Sparse | Top-k 注意力             | 指代消解、精确回忆            |

路由器是一个 `TernaryLinear(d_model, 3)`，其后接 softmax。它为每个 token 产生一个 3 路分布；块的输出是残差加上在该分布下各通路输出的凸组合。

### 3.1 将路由器熵作为校准信号

每 token 的路由器分布携带一个不确定性信号：

```
H(r_t) = − Σ_i r_t,i · log r_t,i,    bounded in [0, log 3] for 3 pathways
```

高熵意味着路由器无法决定哪个计算原语对该位置最合适。该信号是结构性的——它不需要任何针对不确定性的专门训练，也不需要额外参数。在 Atome-LLM 引擎默认规模（60 K 参数、单一狭窄语料）下，该信号是暴露出来的，但其在此规模下作为不确定性估计器的校准并未在此评估。在一个**不包含在本次发布中**的更大的 3 M 参数模型里，我们*初步*观察到路由器熵会跟踪域外输入并与每 token 损失相关；我们仅将其作为一项**尚不可复现的观察**报告，并打算在未来版本中发布支撑性测量。对其进行测量（例如路由器熵与每 token 损失之间的期望校准误差）是另一项单独的工作。

`MCUBlock.router_entropy(x)` 以 nats 为单位返回每 token 的熵。`AtomeLM.router_entropies(ids)` 以 `(B, L)` 张量列表的形式返回逐层、逐 token 的熵。C 引擎的 `atome_state_t` 暴露了逐 token 路由器权重数组 `router_w[ATOME_MAX_SEQ][ATOME_N_PATHWAYS]`——熵是在其上的一个求和/取对数。

## 4. 尺寸与形状预算

在引擎默认的 `#define`（`d_model=64`、`n_layers=4`、`d_head=16`、`vocab=256`、`kernel=5`）下：

- 嵌入：256 × 64 = 16,384 个 trit
- 每块：norm（256 FP32）+ conv（64 × 5 个 trit）+ SSM（3 × 64 FP32）+ Wq/Wk/Wv（16 × 64 + 16 × 64 + 64 × 64 个 trit）+ 路由器（3 × 64 个 trit）
- 最终 norm：128 FP32
- 反嵌入（unembed）：64 × 256 个 trit

以每 trit 2 bit 打包，二进制视配置约在 30–60 KB 量级。对于典型默认值舒适地低于 100 KB，远低于低端 STM32 的 1 MB 闪存，且比 ESP32-S3 上可用的 8 MB 小若干个数量级。

推理时的 RAM 使用由 `atome_state_t` 中的静态缓冲区主导：`x`、`normed`、三个通路输出暂存数组、每层一个 SSM 隐藏状态数组、KV 缓存、路由器权重缓冲区、logits 缓冲区。在默认值下这总计几 KB。

## 5. 本次发布中不包含的内容

- 无多 bank 权重 MoE（引擎不支持它；会打破逐位精确的一致性）。
- 无逐行三元缩放（同样的原因）。
- 无位置嵌入。局部卷积和 SSM 隐藏状态在引擎编译期的序列窗口内隐式地编码位置。
- 无检索通路，无情景记忆通路。二者都需要片外存储或与目标硬件不兼容的大型 RAM 暂存数组。

这些是刻意的省略，而非缺口。它们是在 RAM 为约束性瓶颈的硬件上运行所付出的代价。

## 6. 局限

- **规模。** 默认配置约 60 K 参数（`d_model=64`、`n_layers=4`）。在聚焦的语料上把它训练得很窄，它就能在范围内流利表达；把它训练得很宽，它就不会连贯。这反映的是容量，而非架构。若需更多余量，请提高 `d_model` 与 `n_layers`——例如 `d_model=128`、`n_layers=6` 约为 600 K 参数。
- **序列长度。** 在引擎编译期由 `ATOME_MAX_SEQ` 封顶（默认 32）。对于更长篇的生成，请逐 token 生成，将不断增长的前缀传给 `atome_predict_next`——引擎在每次调用时从完整前缀重新推导 SSM 隐藏状态，从而保持 Python ↔ C 一致性是确定的。
- **分词。** 字节级。UTF-8 多字节序列会占用多个位置。在引擎默认 `MAX_SEQ` 下对非拉丁文字并不理想；如果你的目标文字每字符平均字节数较高，可考虑提高 `ATOME_MAX_SEQ` 并重新导出。

## 参考文献

- Ma et al., 2024. *The Era of 1-bit LLMs: All Large Language Models are in 1.58 Bits.* arXiv:2402.17764.
- Wang et al., 2023. *BitNet: Scaling 1-bit Transformers for Large Language Models.* arXiv:2310.11453.
- Gu and Dao, 2023. *Mamba: Linear-Time Sequence Modeling with Selective State Spaces.* arXiv:2312.00752.
