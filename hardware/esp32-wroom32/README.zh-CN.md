[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · **简体中文** · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# 真实硅片上的 Atome — ESP32-WROOM-32

随附的 **944K** Atome 检查点运行在一块**物理 ESP32-WROOM-32**
（ESP32-D0WD-V3，4 MB 闪存，**无 PSRAM**）上，**完全离线**生成连贯文本，
速度约 **1.0 tok/s**（240 MHz 内核，80 MHz 闪存）。这就是本仓库自己的
`c_engine`——同一个通过主机单元测试和 QEMU Cortex-M3 一致性测试的引擎
——现在在真实硬件上得到验证。

> **诚实范围。** 这是一个*执行证明 + 可复现性*产物，而非
> 基准胜利或护城河（moat）。sub-1M LM 在 MCU 上约 1 tok/s 是已知领域
> （参见 `llama2.c`-on-MCU、TinyML）。尚未运行任何同芯片的、与替代方案的
> 正面对比——那是未来工作，而非此处的主张。吞吐量受闪存限制
> （每 token 从 SPI 闪存读取约 270 KB 三元权重）。

实测输出（`evidence/serial_boot_log_esp32_wroom32.txt`）：

```
config : d=256 layers=8 head=64 seq=24  state=159 KB   (cpu 240 MHz, flash 80 MHz)
Once    ->  upon a time, there
The dog ->  was so excited.
A girl  ->  was so happy to h
average: 1.0 tok/s
```

## 约 2 分钟内自行验证（无需 ESP-IDF）
从 GitHub Release 获取预编译的 `atome_esp32_merged.bin`，然后：
```bash
pip install esptool pyserial
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460800 write_flash 0x0 atome_esp32_merged.bin
python3 -m serial.tools.miniterm /dev/ttyUSB0 115200      # press the board's EN button
```
请先对照 Release 中的 `SHA256SUMS` 核对该二进制。

## 从源码构建
需要 ESP-IDF v5.3。`atome.sh` 封装了 检测 → 构建 → 烧录 → 监视，并可用普通
`esptool` 烧录（烧录主机上无需 IDF）：
```bash
./atome.sh detect                 # identify the board
. ~/esp-idf/export.sh
TARGET=esp32 ./atome.sh build wroom
TARGET=esp32 ./atome.sh flash
./atome.sh monitor
```

## 构建配置（引擎在编译期定尺寸 → 一个二进制 = 一个模型）
| 配置 | 输出 | 状态 RAM | 板子 |
|---------|--------|-----------|-------|
| `full`  | 连贯，完整上下文（seq=128）  | ~811 KB | PSRAM（S3 …R8 / WROVER） |
| `wroom` | 连贯，短上下文（seq=24）  | ~159 KB | 任意 ESP32，内部 SRAM |
| `toy`   | 退化（20 KB 检查点）     | ~103 KB | 任意 ESP32 |

944K 状态随上下文缩放，而非随质量缩放；经典 ESP32 最大的连续
DRAM 块约 168 KB（369 KB 空闲但碎片化），因此 `wroom`
（seq=24 → 159 KB）是无 PSRAM 的配置。带 PSRAM 的板子运行 `full`。

## 说明
- `firmware/main/atome.{c,h}` 是 [`c_engine/upstream/atome.{c,h}`](../../c_engine/upstream/)（Apache-2.0）的内置（vendored）副本，因此这个示例可独立构建。
- `firmware/main/model_full.atome` 与 [`checkpoints/atome_944k.bin`](../../checkpoints/) 是完全相同的字节（md5 `b588e45f…`）；`atome.sh build` 会把所选检查点复制到 `model.atome` 以供嵌入。
- `build/` 和 `model.atome` 是生成的，并被 git 忽略。
