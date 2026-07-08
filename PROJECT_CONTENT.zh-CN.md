[English](PROJECT_CONTENT.md) · [Français](PROJECT_CONTENT.fr.md) · [Español](PROJECT_CONTENT.es.md) · **简体中文** · [Deutsch](PROJECT_CONTENT.de.md) · [日本語](PROJECT_CONTENT.ja.md) <!-- i18n-switcher -->

# PROJECT_CONTENT.md — 项目导览

先读这个。为任何来到本代码库的人（人类或智能体）准备的约 5 分钟导览。能让你避免破坏本套件所看重的承重不变量。

---

## 一句话概览（TL;DR）

**Atome LM** 是一个约 60K 参数的三元语言模型 + 一个在裸机微控制器（RP2040、ESP32-C3、Cortex-M0）上运行它的 C99 推理引擎。Python 训练栈与 C 引擎被设计为产生**逐位完全一致**的前向传播——这份一致性正是本项目的全部要点。

- 许可证：Apache 2.0
- 测试：`pytest -q` → 预期 **146 passed, 0 skipped**（若缺少 `qemu-system-arm` 则 1 skip）
- 三个训练好的检查点随 `checkpoints/` 出货：`atome_944k.bin`（271 KB 的打包 C 引擎 blob——`ATOME01` 格式的 944K 参数演示模型）、`atome_1m_v1.pt`（生成它的 PyTorch 源）以及 `vanilla_1m_v1.pt`（用于 HONEST_RESULTS A/B 的 FP32 vanilla GPT 基线）。任何*其他*匹配 `*.pt`/`*.atome*`/`*.bin` 的文件都被 git 忽略。若想从零训练，请用 `scripts/train_demo.py`（约 30 分钟 CPU）。

## 它为何存在

大多数"微型 LM"都是被压缩过的大型 LM。Atome 从一开始就由 MCU 约束塑造：RAM 是约束性成本，三元权重消灭浮点乘法，三条通路（局部卷积 + 对角 SSM + 稀疏 top-k 注意力）取代一叠深层 transformer，一个逐 token 的软路由器混合它们，字节分词器避免出货词表。有意思的主张不是这些原语（全是既有成果——BitNet、Mamba、top-k 注意力）——而是那种*组合、部署故事以及诚实评估*，展示它在哪里胜出（60K）、在哪里落败（944K）。C 引擎是零堆、静态缓冲、确定性内存占用。

## 智能体绝不能破坏的东西

这些是承重不变量。在报告完成前请对照它们检查任何改动。

1. **Python ↔ C 逐位精确一致性。** 单次前向的一致性就是整个产品。测试：`tests/test_parity_with_c.py`、`tests/test_parity_multitoken.py`。若你改动了模型代码、导出格式或 C 核，请运行它们并确认它们仍然通过。
2. **C 引擎中零堆分配。** `c_engine/upstream/atome.c` 只使用由编译期 `ATOME_*` 宏定尺寸的静态缓冲区。切勿在此引入 `malloc`/`calloc`/`free`。栈上数组没问题。
3. **每一次 `torch.load` 都用 `weights_only=True`。** 套件所有检查点都是 `{"config": dict, "state_dict": dict}`——纯张量 + 原语。用 `weights_only=False` 加载一个恶意 .pt 文件即为 RCE。别退化这一点。
4. **导出器中没有硬编码的模型常量。** `scripts/export_to_atome.py` 从检查点读取 `top_k`（以及所有其他配置）并把真实值写入 C 头。别硬编码常量——`tests/test_export_format.py` 中有一个回归测试会抓到它。
5. **`atome_predict_next` 和 `atome_generate` 中的边界检查。** 二者都会在任何索引/memcpy 之前拒绝 `n_tokens < 1`、`prompt_len < 1` 和 NULL 指针。别移除它们——没有它们，`state->x[n_tokens - 1]` 是未定义行为（UB）。
6. **只出货这三个已发布的检查点。** `checkpoints/atome_944k.bin`、`checkpoints/atome_1m_v1.pt` 和 `checkpoints/vanilla_1m_v1.pt` 被跟踪并在 `.gitignore` 中列入白名单。任何*新*的 `*.pt`/`*.atome*`/`*.bin` 产物默认被 git 忽略——不要在没有明确的白名单条目和理由的情况下向公开发布中添加更多检查点。
7. **基准测试中的诚实。** `HONEST_RESULTS.md` *同时*记录胜利（在 60K 参数下困惑度比 vanilla FP32 好约 22 %，在相同闪存预算下好 52 %）*和*失败（在 944K 规模下 vanilla 以约 11 % 胜出）。别为了让标题更好听而悄悄丢掉失败。

## 文件地图

```
atome-llm-kit/
├── README.md              ← user-facing intro
├── PAPER.md               ← architecture writeup
├── HONEST_RESULTS.md      ← what works, what doesn't, costs
├── FRONTIER.md            ← what's still being explored
├── QUICKSTART.md          ← 30-min train + export walkthrough
├── REPRODUCE.md           ← how to reproduce the headline benchmarks
├── LICENSE / NOTICE       ← Apache 2.0 + attribution
│
├── atome_llm/             ← Python package
│   ├── core/
│   │   ├── atome_lm.py       — main model
│   │   ├── mcu_block.py      — 3-pathway block
│   │   ├── router.py         — per-token soft router
│   │   ├── ssm.py            — diagonal SSM
│   │   ├── sparse_attention.py — top-k attention
│   │   └── ternary*.py       — ternary weight modules
│   ├── tokenize.py         — byte tokenizer (no BPE)
│   └── baselines/          — vanilla FP32 transformer for A/B
│
├── c_engine/upstream/     ← The C99 inference engine
│   ├── atome.c               — implementation (~600 lines, zero heap)
│   └── atome.h               — public API + compile-time macros
│
├── scripts/
│   ├── train_demo.py         — quick training (~30 min CPU)
│   ├── export_to_atome.py    — checkpoint → .atome binary + C header
│   ├── demo.py               — interactive REPL
│   ├── evaluate.py           — bits-per-byte eval
│   └── run_ab_sweep.py       — 60K param-fair / flash-fair A/B
│
└── tests/                 ← 146 tests, all expected to pass
    ├── test_parity_with_c.py        — single-forward Python ↔ C
    ├── test_parity_multitoken.py    — multi-token Python ↔ C
    ├── test_qemu_parity.py          — host C ↔ QEMU ARM (skips if QEMU missing)
    ├── test_export_format.py        — binary format + header generation
    └── test_*.py                    — model shape, router, SSM, ternary, etc.
```

## 验证你的工作

```bash
# from repo root, after install.sh has run once
. .venv/bin/activate
pytest -q       # expect: 146 passed (or 145 + 1 skipped if no qemu-system-arm)
```

那是在宣布完成之前唯一重要的信号。如果你改动了 `atome_llm/core/` 或 `c_engine/upstream/` 中的任何东西，别跳过这一步。

## 智能体在这里常见的出错方式

- **把 C 引擎当成样板代码。** 它不是——每一行都由 RAM/闪存定尺寸。别添加分配，别添加 libc 依赖，别添加 `printf`。全部要点就是它能在一个只有几千字节 RAM 的 2 美元芯片上运行。
- **试图在不重新运行扫描的情况下"改进"文档中的参数量或基准数字。** `HONEST_RESULTS.md` 中的 60K / 944K / 22 % / 52 % / -11 % 数字都绑定到具体的可复现运行。若你无法复现，就别编辑。
- **添加 ML 风格的回退（"if state is None, do X"）。** 运行时是确定的——每条代码路径都会被走到。没有"不应发生"的分支。
- **泛化字节分词器。** 它有意是原始字节。添加 BPE 或 sentencepiece 会出货一个词表（几千字节闪存）并破坏该设计。
- **打包实验性想法。** `c_engine/experiments/delta_inference/` 明确是实验性的——不在受支持的路径上，不经一致性测试。别在没有一致性 + 边界检查覆盖的情况下把实验提升到 `c_engine/upstream/`。
- **为了"让它们通过"而改动一致性测试。** 如果一致性测试失败，错的是*代码*，不是测试。找出 Python/C 的分歧——它几乎总是卷积核方向上的差一、SSM 状态初始化、或一个陈旧的硬编码常量。

## 什么是开放的、什么不是

| 开放（本仓库，Apache 2.0）                          | 非开放（商业）                                 |
|-----------------------------------------------------|-----------------------------------------------|
| 架构、训练代码、C 引擎                              | 硅片落地（逐平台集成）                          |
| 944K 训练权重（`checkpoints/atome_944k.bin`）       | Atome Secure Boot Pack（签名的 `.atome` blob） |
| PyTorch 源 `atome_1m_v1.pt` + vanilla 基线          | 逐平台加固 + 认证流程                           |
| 导出格式 + 一致性测试                               | 更大的内部 V2 模型（3M 参数，混合领域）         |
| 示例数据、A/B 扫描测试装置                          | 自定义微调 + 逐客户集成                         |
| 所有文档（PAPER、HONEST_RESULTS 等）                | atomelm.com 上的营销 / 实时演示站点            |

架构在设计上是公开的，且训练成本为 ~1–2 美元——"许可证即护城河"的策略从来不会奏效，而"权重即护城河"本会很单薄。真正可防御的价值在于逐部署的集成工作、安全加固以及保持专有的更大的 V2 模型——这些都不在本仓库中。

## 若你需要深入挖掘

- 架构原理：`PAPER.md`
- 测了什么、没测什么、各项成本：`HONEST_RESULTS.md`
- 仍在探索什么：`FRONTIER.md`
- 如何复现要点数字：`REPRODUCE.md`
- 如何从零到一个训练并导出好的模型：`QUICKSTART.md`
