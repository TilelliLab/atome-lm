[English](HONEST_RESULTS.md) · [Français](HONEST_RESULTS.fr.md) · [Español](HONEST_RESULTS.es.md) · **简体中文** · [Deutsch](HONEST_RESULTS.de.md) · [日本語](HONEST_RESULTS.ja.md) <!-- i18n-switcher -->

# Atome LM — 诚实结果档案

> 一页纸，无营销话术。我们测了什么、在什么硬件上、用什么随机种子。
> 我们在哪里胜过 vanilla，在哪里没有，在哪里我们还不知道。

**最后更新。** 2026-05-13。汇编自 `checkpoints/*.train.json`
和 `ab_results.json`（它们是真实的运行产物——请打开它们）。

---

## 表 1 — 如实测得的数字

| 配置 | 参数 | 位/权重 | 损失 ↓ | PPL ↓ | 磁盘 | 状态 |
|---|---:|---:|---:|---:|---:|---|
| **60K 区间（MCU 目标）** | | | | | | |
| Atome 三元 3 通路 | 60,800 | 1.58 | 1.84 | 6.31 | 15.1 KB¹ | ✅ 已测 |
| Vanilla GPT FP32（参数公平） | 60,808 | 32 | 2.09 | 8.12 | 237.5 KB | ✅ 已测 |
| Vanilla GPT FP32（闪存公平） | 5,968 | 32 | 2.57 | 13.10 | 23.3 KB | ✅ 已测 |
| **944K 区间（扩容 A/B）** | | | | | | |
| Atome 三元 3 通路 | 944,640 | 1.58 | **1.0545** | 2.87 | 184 KB¹ | ✅ 已测 |
| Vanilla GPT FP32（参数公平） | 950,608 | 32 | **0.9337** | 2.54 | 3.7 MB | ✅ 已测 |
| Atome 3 通路，power3（逐张量） | 944,640 | 2.81 | TBD | TBD | ~325 KB 估 | ⏳ 启动器就绪 |
| Atome 3 通路，power3（逐行 α） | 944,640 | 2.81² | TBD | TBD | ~330 KB 估 | ⏳ 启动器就绪 |

¹ ATOME01，4 trit/字节打包。  
² 逐张量部分为 2.81 位/权重；逐行 α 每个输出行额外增加一个 FP16
（在 944K 时开销占比可忽略）。

**未加修饰的要点：**

- 在 60K 的 MCU 目标上，三元 3 通路架构在相同参数量下以**困惑度 22 %**、在相同闪存预算下以 **52 %** 胜过 vanilla FP32。
- 在 944K，纯三元**在验证损失上以 11.4 %、在困惑度上以 11.5 % 输给 vanilla FP32**。同样的配方、同样的验证切片、同样的随机种子。
- 944K 的反转是本套件中最重要的诚实发现。它表明：3 通路的归纳偏置在小规模下替代容量，而在较大规模下约束容量。Atome 的赌注是小模型 / MCU 区间——而非"微小三元胜过一切"。

## 表 2 — 944K 结果所依赖的条件

| 变量 | 值 |
|---|---|
| 语料 | TinyStories 全量（`train.txt + valid.txt` 拼接，原始约 1.7 GB） |
| 步数 | 30,000 |
| 序列长度 | 256 |
| Batch × 累积 | 64 × 4 |
| 优化器 | AdamW, lr=3e-4 → 3e-5 余弦, warmup=1000, weight_decay=0.1 |
| 精度 | BF16 autocast |
| 随机种子 | 0（单一种子；多种子待办） |
| 硬件 | RunPod A100/A6000（atome）— vast A100（vanilla，2026-05-11） |

## 表 3 — 我们尚未测量的内容

| 问题 | 为何重要 | 解决成本 |
|---|---|---|
| 944K 处的多种子方差 | 单一种子算不上一个发现 | ~2 美元 vast（3 种子 × atome + vanilla） |
| 交叉点 | 3 通路究竟从哪里开始落败？ | ~8 美元 vast（扫描 100K / 300K / 600K / 1.5M） |
| Power-of-3 在 944K 缩小差距 | 若是：损失反转的要点会翻转 | ~6 美元 vast（本套件的启动器） |
| Q15 定点推理 RAM | RP2040 的 RAM 目标在 944K 处未达标（峰值 411 KB） | ~3 天工程量 |
| 真实硅片吞吐量 | 所有 MCU 声明都是 QEMU；把"前沿"变成"事实" | 0 美元（桌上就有 RP2040）+ ~1 天 |
| 从 vanilla 教师蒸馏 | 三元学生常能弥补与浮点教师差距的 80 %+ | ~1–2 美元 vast |
| 更广领域语料 | TinyStories 偏向局部模式模型 | ~4 美元 vast |

## 表 4 — 哪些是稳固的，哪些是承重但单薄的

**稳固（无强理由不要改动）：**

- HEAD 处 146/146 测试通过（其中 16 个是 power3 专属）。
- 单次前向的 Python ↔ C ↔ Cortex-M3（QEMU）逐位精确一致性
  （`tests/test_parity_with_c.py`、`tests/c_parity/parity_main.c`）。
- 磁盘上有训练好的 atome_1m_v1.pt + vanilla_1m_v1.pt 产物，二者
  在 `checkpoints/*.train.json` 中都有完整训练日志（打开它们——每一步的
  损失都有记录）。
- 60K 参数公平 / 闪存公平 A/B 在约 30 分钟 CPU 内可复现
  （`scripts/run_ab_sweep.py`）。

**承重但单薄：**

- 所有要点数字都是单一种子。
- 多 token 的 C 生成此前存在一个 SSM 状态发散的 bug
  （Bug A）。已在 Python 和 C 引擎中修复：`atome_predict_next`
  在每次调用时重置 SSM 隐藏状态并从完整 token 前缀重新推导它
  （`c_engine/upstream/atome.c`）。多 token 的 Python↔C 一致性
  由 `tests/test_parity_multitoken.py` 覆盖；单次前向一致性
  仍通过 `tests/test_parity_with_c.py` 保持逐位精确。
- RP2040 演示目前在 944K 处超过 264 KB SRAM——MCU 声明
  依赖于区间，而本套件中的启动器正在测试
  power3 是否能把参数预算收窄到足以把 944K 拉回可行范围
  （单靠它做不到；需要 Q15 或更小的隐藏状态）。

## 表 5 — 迄今为止每项测量的成本

| 工作 | 日期 | 成本 | 磁盘上的结果 |
|---|---|---:|---|
| 60K A/B 扫描 | 2026-05-09 | 0 美元（CPU） | `ab_results.json` |
| 944K Atome | 2026-05-10 | ~0.40 美元（RunPod A40） | `atome_1m_v1.pt` |
| 944K Vanilla | 2026-05-11 | ~0.55 美元（Vast A100） | `vanilla_1m_v1.pt` |
| Power-3 接线 + 测试 + CPU 冒烟 | 2026-05-12/13 | 0 美元（CPU） | `atome_llm/core/power3.py` + 6 个新测试 |
| **迄今总花费** | | **< 1.00 美元** | — |
| 待办：带 power3 + power3_pr 的 944K A/B | — | ~3.60–6.40 美元 上限 8 美元 | `scripts/` 中的启动器 |

## 存档文件

训练好的 944K 检查点及其训练日志随套件一同出货，因此
每一个报告的数字都可逐步审计*并*可直接重新评估：

- `checkpoints/atome_944k.bin` — 打包后的 C 引擎 blob（ATOME01 格式）。
- `checkpoints/atome_1m_v1.pt` — 944K Atome 的 PyTorch 源。
- `checkpoints/vanilla_1m_v1.pt` — 944K vanilla FP32 基线（用于上面的
  反转 A/B）。
- `checkpoints/atome_1m_v1.train.json` — 每 1000 步的训练日志。
- `checkpoints/vanilla_1m_v1.train.json` — vanilla 基线的同类日志。
- `ab_results.json` — 精确的 60K A/B 结果行。
- `FRONTIER.md` — 带完整 944K 披露的前沿说明。
- `PAPER.md` — 架构说明。
- `tests/` — 146 个通过的测试。

60K 扫描本身（`checkpoints/ab_sweep/`）**不**出货——那是
24 次一次性的训练运行。复现该扫描约需 ~20 分钟
CPU，使用随附的 `scripts/`。
