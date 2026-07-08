[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · **简体中文** · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# Atome LLM — 内置（vendored）C 引擎

本目录包含在微控制器和主机上运行 Atome LLM 检查点的 C99 推理引擎。项目的 Python 侧（`atome_llm/`）负责训练和导出；这里的 C 侧负责加载导出的 `.atome` 二进制并在设备上运行前向传播。

## 布局

```
c_engine/
├── README.md                  this file
├── upstream/
│   ├── atome.h                public API + compile-time #defines
│   └── atome.c                implementation (~570 lines, zero-heap, integer-arithmetic forward)
└── targets/
    └── cortex-m3/             ARM Cortex-M3 firmware that runs in QEMU MPS2-AN385
        ├── firmware.c
        ├── startup.s
        ├── linker.ld
        └── Makefile
```

## 它从何而来

`upstream/` 中的文件是截至 2026-05-03 的一份内部 C 引擎源的内置（vendored）副本。内置（而非子模块或符号链接）是刻意的：atome-llm 应当是分发单元。要拉入 upstream 的改动，请重新复制这些文件并重新运行一致性测试套件（`pytest tests/test_parity_with_c.py tests/test_qemu_parity.py`）。

与逐字 upstream 的一处小差异：`atome.h` 中的一个注释被改名为"Atome block"（它此前指的是前身名称）。没有功能性改动——注释不编译。

## 为主机编译（x86-64）

最简单的路径——由 `tests/test_parity_with_c.py` 使用：

```bash
gcc -O2 -std=c99 -DATOME_D_MODEL=16 -DATOME_N_LAYERS=2 ... \
    -I c_engine/upstream parity_main.c c_engine/upstream/atome.c -lm
```

## 为 ARM Cortex-M 编译

两层：

1. **仅编译的健全性检查**，跨多个 Cortex-M 变体——`python scripts/cross_compile.py` 产生一张尺寸表（逐架构的 `text/data/bss`）。它能捕捉可移植性回归，并给出真实的目标端二进制尺寸数字。
2. **完整固件**，面向 QEMU MPS2-AN385——`make -C c_engine/targets/cortex-m3` 产生一个能在 `qemu-system-arm` 下带半主机（semihosting）运行的 `.elf`。端到端的 Python ↔ Cortex-M3 一致性测试位于 `tests/test_qemu_parity.py`。

## 架构说明

C 引擎假定：
- 逐张量三元缩放（每张权重矩阵一个 FP32）
- 嵌入布局 `(vocab, d_model)`——参见 `atome_llm/core/ternary_embedding.py` 了解为何这很重要
- 无逐行缩放、无多 bank 权重、无位置嵌入
- `atome_block_t` 仅为 `local_conv`、`ssm`、`attn` 和 `router` 拥有固定缓冲区——无宽卷积、无稠密 FFN、无检索通路

这些约束是承重的。添加一条新通路需要一并更新 `atome.h`、C 核、`.atome` 二进制格式**以及** Python 的 `MCUBlock`。
