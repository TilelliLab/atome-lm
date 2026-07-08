**English** · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# SuperESP firmware skeleton (ESP32 / ESP-IDF)

> **Status: BUILD-ONLY skeleton — NOT FLASHED, NOT MEASURED on silicon.**
> This box has no physical ESP32 and no ESP-IDF toolchain. The firmware below
> is the real structure (it reuses the vendored `atome.c`/`atome.h` engine and
> the trained ATOMECL01 head blobs), but on-board tok/s, RAM high-water, and
> live ADC/I2S capture are **not measured here**. The host-side C dispatcher
> `c_engine/superesp/superesp_os.c` *is* compiled and tested (see superesp tests).

## What it does (the "OS" idea)
On boot the firmware:
1. Reads the ESP32's own telemetry — `esp_get_free_heap_size()`, internal temp
   sensor, Wi-Fi RSSI, ADC channels, hall, touch — into the **OS fused frame**.
2. Quantizes that frame to bytes (using the per-feature `vmin/vmax` baked from
   `os_telem.tok.json`) and runs `atome_classify` with the **OS head** to get a
   device state (normal / low_memory / overheating / wifi_degraded / power_fault).
3. Applies the load-shedding policy (e.g. disables the audio heads when
   overheating), then reads the active sensor (ADC for agri, I2S mic for voice)
   and dispatches that frame to its head — abstaining when unsure.

So Atome runs as the device supervisor, not a text generator. All 7 heads share
one engine build (same shared config); each head is a different embedded blob.

## To build (on a machine with ESP-IDF + a board)
```
idf.py set-target esp32
idf.py build            # compile-time config in main/CMakeLists.txt
idf.py -p /dev/ttyUSB0 flash monitor
```
The compile-time defines (d_model=32, n_layers=2, ...) MUST match the SuperESP
shared config (superesp/framework/config.py) the blobs were exported with.
