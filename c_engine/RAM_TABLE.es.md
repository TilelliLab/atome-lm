[English](RAM_TABLE.md) · [Français](RAM_TABLE.fr.md) · **Español** · [简体中文](RAM_TABLE.zh-CN.md) · [Deutsch](RAM_TABLE.de.md) · [日本語](RAM_TABLE.ja.md) <!-- i18n-switcher -->

# Atome — tabla de ajuste RAM / Flash

Generada por `python3 scripts/measure_ram.py --markdown`. Los números provienen de una compilación real Cortex-M3 (`c_engine/targets/cortex-m3-ram`) bajo QEMU MPS2-AN385: `.text + .data + model.atome` para flash, y `.bss + marca alta de pila medida` para RAM.

## Tamaños por configuración

| Config | d_model | capas | max_seq | Flash | RAM (.bss) | Pila | Pico RAM |
|---|---:|---:|---:|---:|---:|---:|---:|
| `nano` | 16 | 2 | 32 | 41.9 KB | 14.3 KB | 144 B | 14.5 KB |
| `tiny` | 16 | 2 | 32 | 41.9 KB | 14.3 KB | 144 B | 14.5 KB |
| `byte_small` | 32 | 2 | 32 | 52.1 KB | 27.3 KB | 156 B | 27.5 KB |
| `tinystories` | 64 | 4 | 64 | 79.4 KB | 103.9 KB | 164 B | 104.1 KB |
| `mid` | 128 | 4 | 64 | 143.4 KB | 205.0 KB | 164 B | 205.1 KB |
| `prod_1m` | 256 | 8 | 64 | 579.6 KB | 411.4 KB | 164 B | 411.6 KB |

## Matriz «cabe-en-MCU»

`✓` = cabe, `✗` = excede RAM o flash, `✗R` = limitado por RAM, `✗F` = limitado por flash.

| Config | STM32F103 (Blue Pill) | RP2040 (Pico) | STM32F411 (Nucleo) | STM32F7 | ESP32-S3 |
|---|:---:|:---:|:---:|:---:|:---:|
| `nano` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `tiny` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `byte_small` | ✗R | ✓ | ✓ | ✓ | ✓ |
| `tinystories` | ✗R | ✓ | ✓ | ✓ | ✓ |
| `mid` | ✗ | ✓ | ✗R | ✓ | ✓ |
| `prod_1m` | ✗ | ✗R | ✗ | ✓ | ✓ |

## Referencia de MCU

| MCU | SRAM | Flash | Núcleo | Precio aprox. |
|---|---:|---:|---|---|
| STM32F103 (Blue Pill) | 20.0 KB | 128 KB | M3 | $2-4 |
| RP2040 (Pico) | 264.0 KB | 2048 KB | M0+ | $4 |
| STM32F411 (Nucleo) | 128.0 KB | 512 KB | M4F | $15 |
| STM32F7 | 512.0 KB | 2048 KB | M7 | $15-30 |
| ESP32-S3 | 512.0 KB | 4096 KB | LX7 | $5-10 |
