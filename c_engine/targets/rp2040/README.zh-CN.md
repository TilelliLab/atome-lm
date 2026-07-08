[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · **简体中文** · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# 在 Raspberry Pi Pico (RP2040) 上运行 Atome LLM

让一个 60 K 参数的三元语言模型在一个 4 美元的微控制器上运行、
并通过串口报告每秒 token 数的端到端配方。

## 你需要什么

- 一块 Raspberry Pi Pico（任意 RP2040 板；Pico、Pico W、Pico 2、克隆板）。
- 一根 USB 线（原版 Pico 用 Micro-USB，Pico 2 用 USB-C）。
- 工具链：`arm-none-eabi-gcc`、`cmake`、`make`、`git`。
- 磁盘：Pico SDK 约 500 MB + 构建约 50 MB。

## 一次性设置

```bash
sudo apt install gcc-arm-none-eabi cmake make build-essential libstdc++-arm-none-eabi-newlib

git clone --depth 1 https://github.com/raspberrypi/pico-sdk
export PICO_SDK_PATH=$PWD/pico-sdk
git -C "$PICO_SDK_PATH" submodule update --init
```

## 构建固件

从项目根目录：

```bash
# 1. Train (or download) a checkpoint, then export to .atome:
python scripts/train_demo.py --data data/tinystories.txt --steps 800 \
    --output checkpoints/atome_demo.pt
python scripts/export_to_atome.py --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome

# 2. Bake the binary into a C array:
cd c_engine/targets/rp2040
xxd -i -n model_atome ../../../checkpoints/atome_demo.atome > model_data.h

# 3. Build:
mkdir -p build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j
```

现在你应当有 `build/atome_pico.uf2`（约 200 KB）。

## 烧录板子

1. 在把 Pico 插入 USB 时按住其上的 **BOOTSEL** 按钮。
2. 松开；板子会挂载为一个名为 **RPI-RP2** 的 USB 驱动器。
3. 把 `atome_pico.uf2` 拖放到该驱动器上。复制完成后 Pico 会
   自动重启。

## 读取输出

用 **115 200 8N1** 打开一个串口终端（`minicom -D /dev/ttyACM0 -b 115200`，
或任意主机串口应用）。你应当会看到：

```
ATOME-PICO-START prompt_len=4 new_tokens=16 max_seq=32
TOK 0 117 us=42120
TOK 1  98 us=43755
TOK 2 215 us=43818
...
ATOME-PICO-END total_us=698540 tokens=16
```

每一行 `TOK N B us=...` 是一个生成的字节以及以微秒计的逐步延迟，
由 RP2040 硬件定时器测量（不涉及主机时钟）。在引擎默认值下
（60.8 K 参数、4 层、`max_seq=32`），在标准 125 MHz RP2040 上，
配合 Python 侧的参考生成循环，预期约 **15–25 tokens/sec**，
若切换到流式 SSM 的 C 路径则约 **40–60 tokens/sec**（见项目 README
中的 Bug A——该修复以用户签字同意为前提）。

## 测量功耗

在 Pico 的 `VBUS` 线上串一个 1 Ω 分流电阻，用 USB 隔离的
万用表或 Joulescope 采样。每 token 焦耳数是功率在两条连续
`TOK` 行之间时间上的积分。典型的 RP2040 有源电流约 30 mA @ 3.3 V
→ 100 mW——在 25 tok/s 下即 **每 token 4 mJ**。

## 故障排查

- **没有串口设备。** Pico SDK 同时暴露 USB CDC 和 UART。如果
  你看不到 `/dev/ttyACM0`，请检查 `dmesg | tail` 中的 USB
  枚举行；如果它在那里但设备缺失，你的用户
  可能不在 `dialout` / `tty` 组中。
- **`atome_load` 失败。** 最常见的原因是训练好的检查点与 Pico
  侧的定义之间配置不匹配。请用与你检查点配置相匹配的
  `cmake -DATOME_D_MODEL=... -DATOME_N_LAYERS=...` 重新构建
  （见导出脚本的打印输出）。
- **闪存不足。** 默认配置远低于 200 KB。如果你
  提高了 `d_model` 或 `n_layers`，`.atome` blob 可能会超过 2 MB
  闪存。请减小模型尺寸，或把 blob 移到外部 SD 卡
  （本固件尚不支持）。
