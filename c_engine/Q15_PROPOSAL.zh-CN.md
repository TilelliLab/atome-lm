[English](Q15_PROPOSAL.md) · [Français](Q15_PROPOSAL.fr.md) · [Español](Q15_PROPOSAL.es.md) · **简体中文** · [Deutsch](Q15_PROPOSAL.de.md) · [日本語](Q15_PROPOSAL.ja.md) <!-- i18n-switcher -->

# Q15 激活路径 — 设计提案（未实现）

## 它为何存在

在 5 月 10 日的模拟器会话中，我们最初怀疑 ARM 软浮点与主机 x86 之间的浮点运算顺序
导致了多 token 漂移。经检查，真正的原因是一个逻辑 bug——`atome_predict_next`
从不重置 `state->ssm_h`，因此上一次调用的 SSM 状态污染了后续的
前向传播。该 bug 现已修复（`atome.c:294-300`），
且 48/48 个 QEMU token 与 Python 相符。

但 Q15 仍值得为**性能与能耗**而做，而非
为正确性。本文件冻结该设计，以便下一次会话能冷启动
接手。

## Q15 带来什么（最佳估计，尚未测量）

| 收益 | 量级 | 为何 |
|---|---|---|
| M0 / M3 上的计算加速 | ~5-10× | 无 FPU；整数乘加在 ARM v7-M 上是单周期 |
| M4F / M7 上的计算加速 | ~1.5-2× | 已有 FPU；收益来自 SIMD（`__SADD16`、`SMLAD`） |
| BSS 缩减 | ~40-50% | 激活张量减半（fp32 → int16） |
| 每 token 功耗 | ~3-5× 更低 | 随周期数缩放 |
| 跨主机确定性 | 完全 | 整数运算消除舍入顺序的歧义 |

## Q15 不带来什么

- 更小的 `.atome` blob——权重已经是三元（每个约 0.5 bit）。
  激活存在于 RAM，而非闪存。
- 更好的模型质量——推理时的量化是有损的；预期
  困惑度会略微上升（若经校准可能 <5 %；需测量）。

## 设计

### 编译期开关

添加 `ATOME_DTYPE`，选择 `f32`（今天，默认）或 `q15`（新增）。
当该标志缺失时，现有测试 / 固件不变。

```c
#ifndef ATOME_DTYPE_Q15
#define ATOME_DTYPE_Q15 0
#endif

#if ATOME_DTYPE_Q15
typedef int16_t  atome_act_t;
typedef int32_t  atome_acc_t;
#else
typedef float    atome_act_t;
typedef float    atome_acc_t;
#endif
```

### 什么保持浮点

- LayerNorm（sqrt + 除法——存在 Q15-LayerNorm，但会增加 200 LOC）
- Softmax（exp——同上）
- 单个注意力缩放 `1.0 / sqrtf(d_h)`
- 最终 logits（使 argmax 无歧义）

这些占周期的 <2 %。在边界处往返转换为 Q15。

### 什么变成 Q15

- 所有三元 matvec（`atome_ternary_matvec`）
- 因果卷积（`atome_causal_conv`）
- SSM 前向（需谨慎——`tanh(a)` 和 `b * x` 需要定点处理）
- 注意力点积（Q.K）
- 注意力加权和（sum_i p_i * V_i）

### 逐张量缩放跟踪

每个 Q15 张量携带一个隐式移位。维护一个小的、逐步的
`atome_q15_state_t`，保存当前缩放并即时更新：

```c
typedef struct {
    int x_shift;        /* current activation shift (Q15-pos) */
    int normed_shift;
    int path_local_shift;
    int path_ssm_shift;
    int path_attn_shift;
} atome_q15_state_t;
```

校准脚本（Python 侧）：让几千个提示词通过浮点模型，
记录每层的最大绝对激活，设定移位
使得 99.9 百分位落入 [-32768, 32767]。

### 测试计划

1. 新的 `tests/test_q15_parity.py`：浮点参考 vs Q15 前向。
   容差：在 d=64 时，对 >95 % 的提示词 top-1 logit 必须相符，
   逐 token 余弦相似度 >0.98。
2. 新的 `c_engine/targets/cortex-m3-q15/` 目标。固件报告
   每 token 周期数；预期在相同配置下比 `cortex-m3-gen` 快 5-10×。
3. 向 `RAM_TABLE.md` 添加一行 `q15`。预期：tinystories 配置从
   104 KB 峰值降至约 55 KB 峰值。F103 Blue Pill（2-4 美元）对训练好的
   模型变得可达。

## 预估工作量

| 阶段 | 工作量 | 风险 |
|---|---|---|
| 校准（Python）+ 缩放导出 | 半天 | 低 |
| `atome.c` 的 Q15 路径（骨架 + matvec + conv） | 1 天 | 低 |
| SSM Q15（tanh 表 + 缩放乘加） | 半天 | 中——需数值上的谨慎 |
| 注意力 Q15（Q·K、softmax 输入缩放） | 半天 | 中 |
| 测试 + 固件目标 | 半天 | 低 |
| 校准调优 + 基准 | 半天 | 低 |
| **总计** | **~3-4 天** | — |

## 何时重启

在以下之后：
1. 1M 参数检查点（`TRAIN_1M_RUNBOOK.md`）落地，且我们有一个
   值得为速度/功耗优化的真实模型。
2. 在 Nucleo-F411RE 上的真实硅片验证确认今天的 QEMU
   数字是有预测力的。
3. 有用户想在 F103 Blue Pill（2-4 美元）上运行 Atome——它是当前
   在训练模型配置下被 RAM 阻挡的最便宜档位。

这是一块干净、界定清晰、自洽的工作。当上述条件之一
达成时接手它。
