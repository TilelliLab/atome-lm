**English** · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# SuperESP ESP32 application test battery

Test **all 12 SuperESP applications on a real ESP32 in one command**, then get a
per-application report (pass/fail, on-device class vs expected, free heap, bugs).

> The board we first tested on: **ESP32-WROOM-32** (ESP32-D0WD-V3, 4 MB flash, no
> PSRAM, /dev/ttyUSB0 @ 115200). SuperESP's state is ~27 KB (vs the 944K LM's
> 159 KB), so it fits with huge headroom — see `superesp/cli.py targets`.

## One command (on YOUR machine, board plugged in)
```bash
. ~/esp-idf/export.sh           # once per shell (install: superesp/cli.py setup)
./superesp/esp32/run_battery.sh # doctor→detect→build→flash→capture→grade→report
# env overrides: PORT=/dev/ttyUSB0 TARGET=esp32 CAPTURE_S=60
```
Output: `superesp/esp32/reports/REPORT.md` + `report.json` + the raw `serial_*.log`.

## What it does
1. **gen_battery.py** bakes all 12 head blobs + a test vector each + the
   **host-C golden expected class** into `battery_data.h` (+ `golden.json`).
2. **battery_main.c** (one source, compiles for QEMU *and* ESP-IDF) loads each
   head, classifies its vector, and prints
   `HEAD <name> CLASS <got> EXPECT <want> PASS|FAIL HEAP <kb>`.
3. **parse_report.py** grades the serial log against golden → per-app report,
   honestly labeled **real silicon** (HEAP present) vs **QEMU/emulation**.

## Already validated in emulation (this repo, no board)
The exact firmware was run in `qemu-system-arm` (Cortex-M3, real ARM Thumb):
**12/12 applications PASS, bit-exact** (`python3 -m superesp.qemu_test <head>` for
single heads). So the logic is proven before you flash — the board run converts
"emulated-correct" into "silicon-correct" and adds real heap/timing numbers.

## If something fails
The report's **Bugs / errors** section captures: missing heads (serial
truncated / didn't run), `LOAD_FAIL` (flash/blob issue), class mismatches, and
suspected crashes (`Guru Meditation` / panic without `BATTERY DONE`). Paste
`reports/REPORT.md` back and I'll diagnose.
