**English** · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# Atome on real silicon — ESP32-WROOM-32

The bundled **944K** Atome checkpoint running on a **physical ESP32-WROOM-32**
(ESP32-D0WD-V3, 4 MB flash, **no PSRAM**), generating coherent text **fully
offline** at **~1.0 tok/s** (240 MHz core, 80 MHz flash). This is the repo's own
`c_engine` — the same engine that passes the host unit tests and the QEMU
Cortex-M3 parity test — now verified on real hardware.

> **Honest scope.** This is a *proof-of-execution + reproducibility* artifact, not
> a benchmark win or a moat. ~1 tok/s for a sub-1M LM on an MCU is known territory
> (cf. `llama2.c`-on-MCU, TinyML). No same-chip head-to-head against an alternative
> has been run — that's future work, not a claim here. Throughput is flash-bound
> (~270 KB of ternary weights read from SPI flash per token).

Measured output (`evidence/serial_boot_log_esp32_wroom32.txt`):

```
config : d=256 layers=8 head=64 seq=24  state=159 KB   (cpu 240 MHz, flash 80 MHz)
Once    ->  upon a time, there
The dog ->  was so excited.
A girl  ->  was so happy to h
average: 1.0 tok/s
```

## Verify it yourself in ~2 minutes (no ESP-IDF needed)
Grab the prebuilt `atome_esp32_merged.bin` from the GitHub Release, then:
```bash
pip install esptool pyserial
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460800 write_flash 0x0 atome_esp32_merged.bin
python3 -m serial.tools.miniterm /dev/ttyUSB0 115200      # press the board's EN button
```
Check the binary against `SHA256SUMS` in the Release first.

## Build from source
Needs ESP-IDF v5.3. `atome.sh` wraps detect → build → flash → monitor and can flash
with plain `esptool` (no IDF on the flashing host):
```bash
./atome.sh detect                 # identify the board
. ~/esp-idf/export.sh
TARGET=esp32 ./atome.sh build wroom
TARGET=esp32 ./atome.sh flash
./atome.sh monitor
```

## Build profiles (the engine is compile-time-sized → one binary = one model)
| profile | output | state RAM | board |
|---------|--------|-----------|-------|
| `full`  | coherent, full context (seq=128)  | ~811 KB | PSRAM (S3 …R8 / WROVER) |
| `wroom` | coherent, short context (seq=24)  | ~159 KB | any ESP32, internal SRAM |
| `toy`   | degenerate (20 KB checkpoint)     | ~103 KB | any ESP32 |

The 944K state scales with context, not quality; a classic ESP32's largest
contiguous DRAM block is ~168 KB (369 KB free but fragmented), so `wroom`
(seq=24 → 159 KB) is the no-PSRAM profile. A PSRAM board runs `full`.

## Notes
- `firmware/main/atome.{c,h}` are vendored copies of [`c_engine/upstream/atome.{c,h}`](../../c_engine/upstream/) (Apache-2.0), so this example builds standalone.
- `firmware/main/model_full.atome` is the same bytes as [`checkpoints/atome_944k.bin`](../../checkpoints/) (md5 `b588e45f…`); `atome.sh build` copies the chosen checkpoint to `model.atome` for embedding.
- `build/` and `model.atome` are generated and git-ignored.
