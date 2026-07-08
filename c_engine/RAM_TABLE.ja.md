[English](RAM_TABLE.md) · [Français](RAM_TABLE.fr.md) · [Español](RAM_TABLE.es.md) · [简体中文](RAM_TABLE.zh-CN.md) · [Deutsch](RAM_TABLE.de.md) · **日本語** <!-- i18n-switcher -->

# Atome — RAM / フラッシュ適合表

`python3 scripts/measure_ram.py --markdown` により生成。数値は、QEMU MPS2-AN385 の下での実際の Cortex-M3 ビルド（`c_engine/targets/cortex-m3-ram`）から得られます：フラッシュは `.text + .data + model.atome`、RAM は `.bss + 実測のスタック高水位`。

## 構成ごとのサイズ

| 構成 | d_model | 層数 | max_seq | フラッシュ | RAM (.bss) | スタック | ピーク RAM |
|---|---:|---:|---:|---:|---:|---:|---:|
| `nano` | 16 | 2 | 32 | 41.9 KB | 14.3 KB | 144 B | 14.5 KB |
| `tiny` | 16 | 2 | 32 | 41.9 KB | 14.3 KB | 144 B | 14.5 KB |
| `byte_small` | 32 | 2 | 32 | 52.1 KB | 27.3 KB | 156 B | 27.5 KB |
| `tinystories` | 64 | 4 | 64 | 79.4 KB | 103.9 KB | 164 B | 104.1 KB |
| `mid` | 128 | 4 | 64 | 143.4 KB | 205.0 KB | 164 B | 205.1 KB |
| `prod_1m` | 256 | 8 | 64 | 579.6 KB | 411.4 KB | 164 B | 411.6 KB |

## 「MCU に収まるか」マトリクス

`✓` = 収まる、`✗` = RAM またはフラッシュを超過、`✗R` = RAM 制約、`✗F` = フラッシュ制約。

| 構成 | STM32F103 (Blue Pill) | RP2040 (Pico) | STM32F411 (Nucleo) | STM32F7 | ESP32-S3 |
|---|:---:|:---:|:---:|:---:|:---:|
| `nano` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `tiny` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `byte_small` | ✗R | ✓ | ✓ | ✓ | ✓ |
| `tinystories` | ✗R | ✓ | ✓ | ✓ | ✓ |
| `mid` | ✗ | ✓ | ✗R | ✓ | ✓ |
| `prod_1m` | ✗ | ✗R | ✗ | ✓ | ✓ |

## MCU リファレンス

| MCU | SRAM | フラッシュ | コア | おおよその価格 |
|---|---:|---:|---|---|
| STM32F103 (Blue Pill) | 20.0 KB | 128 KB | M3 | $2-4 |
| RP2040 (Pico) | 264.0 KB | 2048 KB | M0+ | $4 |
| STM32F411 (Nucleo) | 128.0 KB | 512 KB | M4F | $15 |
| STM32F7 | 512.0 KB | 2048 KB | M7 | $15-30 |
| ESP32-S3 | 512.0 KB | 4096 KB | LX7 | $5-10 |
