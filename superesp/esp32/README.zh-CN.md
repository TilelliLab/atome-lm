[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · **简体中文** · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# SuperESP ESP32 应用测试套件

用一条命令在一块真实 ESP32 上**测试全部 12 个 SuperESP 应用**，随后获得一份
逐应用报告（通过/失败、设备端类别 vs 预期、空闲堆、bug）。

> 我们最初测试的板子：**ESP32-WROOM-32**（ESP32-D0WD-V3，4 MB 闪存，无
> PSRAM，/dev/ttyUSB0 @ 115200）。SuperESP 的状态约 27 KB（相较 944K LM 的
> 159 KB），因此装得下且余量巨大——见 `superesp/cli.py targets`。

## 一条命令（在你的机器上，板子已插好）
```bash
. ~/esp-idf/export.sh           # once per shell (install: superesp/cli.py setup)
./superesp/esp32/run_battery.sh # doctor→detect→build→flash→capture→grade→report
# env overrides: PORT=/dev/ttyUSB0 TARGET=esp32 CAPTURE_S=60
```
输出：`superesp/esp32/reports/REPORT.md` + `report.json` + 原始的 `serial_*.log`。

## 它做什么
1. **gen_battery.py** 把 12 个头 blob + 各自一个测试向量 + **主机-C 的黄金
   预期类别**烘焙进 `battery_data.h`（+ `golden.json`）。
2. **battery_main.c**（单一源文件，可为 QEMU *和* ESP-IDF 编译）加载每个
   头，对其向量分类，并打印
   `HEAD <name> CLASS <got> EXPECT <want> PASS|FAIL HEAP <kb>`。
3. **parse_report.py** 用黄金标准对串口日志评分 → 逐应用报告，
   如实标注为**真实硅片**（HEAP 存在）vs **QEMU/仿真**。

## 已在仿真中验证（本仓库，无板子）
确切的固件曾在 `qemu-system-arm`（Cortex-M3，真实 ARM Thumb）中运行：
**12/12 个应用通过，逐位精确**（单个头用 `python3 -m superesp.qemu_test <head>`）。
所以逻辑在你烧录之前就已证明——板上运行把"仿真-正确"转变为
"硅片-正确"，并加入真实的堆/时序数字。

## 如果有东西失败
报告的 **Bugs / errors** 部分会捕获：缺失的头（串口
被截断 / 未运行）、`LOAD_FAIL`（闪存/blob 问题）、类别不匹配，以及
疑似崩溃（`Guru Meditation` / 没有 `BATTERY DONE` 的 panic）。把
`reports/REPORT.md` 粘回来，我会诊断。
