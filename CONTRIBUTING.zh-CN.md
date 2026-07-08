[English](CONTRIBUTING.md) · [Français](CONTRIBUTING.fr.md) · [Español](CONTRIBUTING.es.md) · **简体中文** · [Deutsch](CONTRIBUTING.de.md) · [日本語](CONTRIBUTING.ja.md) <!-- i18n-switcher -->

# 为 Atome LM 做贡献

感谢你考虑做贡献。这是一个小而聚焦的项目——一个微型三元语言模型 + 一个与它逐位精确对话的 C99 推理引擎。请先读 `PROJECT_CONTENT.md`；它涵盖了你绝不能破坏的东西。

## 快速开始

```bash
git clone https://github.com/TilelliLab/atome-lm
cd atome-lm
./install.sh
. .venv/bin/activate
pytest -q        # expect: 146 passed (or 145 + 1 skipped without qemu-system-arm)
```

## 报告 bug

在 GitHub 上开一个 issue，并附上：

- 你运行了什么（确切命令）
- 你预期什么
- 发生了什么（完整错误，而非转述）
- 你的平台：操作系统、Python 版本，以及 `python -c "import torch; print(torch.__version__)"`

如果你遇到一致性失败（Python 前向 ≠ C 前向），请附上失败的随机种子以及你训练的任何检查点——这些是最高优先级的 bug。

## 提交 pull request

1. Fork 仓库并从 `main` 创建一个分支。
2. 做你的改动。
3. 运行完整测试套件——每个 PR 都必须保持 `pytest -q` 通过。
4. 如果你的改动触及 `atome_llm/core/`、`c_engine/upstream/` 或导出格式，请**特别确认**这些测试仍然通过：
   - `tests/test_parity_with_c.py` — 单次前向 Python ↔ C 一致性
   - `tests/test_parity_multitoken.py` — 多 token Python ↔ C 一致性
   - `tests/test_export_format.py` — 二进制格式 + 头生成
5. 开启 PR。CI 会在 Python 3.10 / 3.11 / 3.12 上重新运行套件。

## 可接受改动的范围

欢迎：

- Bug 修复
- 新的测试覆盖（尤其是对 C 解析器的模糊测试用例以及对 `atome_predict_next` / `atome_generate` 的边界输入）
- 保持逐位精确一致性的性能改进
- 文档修正与澄清
- `c_engine/targets/` 下新的 MCU 目标板，*只要它们不改动 upstream 引擎*
- `atome_llm/baselines/` 下用于诚实 A/B 对比的新基线

超出范围，请不要为这些开 PR：

- 向 `c_engine/upstream/` 添加堆分配、动态内存或 libc 依赖
- 向确定性代码路径添加"不应发生"的回退
- 打包新的分词器（BPE / sentencepiece）——字节分词器是面向 MCU 闪存预算的承重设计选择
- 破坏 Python ↔ C 一致性的改动，即便它改善了某个基准
- 在没有完整一致性 + 边界检查覆盖的情况下把代码从 `c_engine/experiments/` 提升到 `c_engine/upstream/` 的新功能

## 编码规范

- Python：保持简单，无辅助层，无为风格而设的装饰器。贴合既有风格——小函数、无过早抽象、只有当*为何*不显然时才写注释。
- C：仅 C99，无 GNU 扩展，除 `<string.h>` / `<math.h>` / `<stdint.h>` 外无 libc。由编译期 `ATOME_*` 宏定尺寸的静态缓冲区。对所有公共 API 输入做边界检查。

## 安全

如果你发现一个安全问题（任何能让恶意检查点或 `.atome` blob 危害运行引擎的主机的东西），请发邮件至 **hello@atomelm.com** 而非提交一个公开 issue。我们会协调披露。

## 许可证

提交贡献即表示你同意它将以 Apache License 2.0（项目许可证——见 `LICENSE`）发布。
