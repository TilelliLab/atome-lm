[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · **Deutsch** · [日本語](README.ja.md) <!-- i18n-switcher -->

# SuperESP-Firmware-Skelett (ESP32 / ESP-IDF)

> **Status: NUR-BUILD-Skelett — NICHT GEFLASHT, NICHT auf Silizium GEMESSEN.**
> Diese Box hat kein physisches ESP32 und keine ESP-IDF-Toolchain. Die Firmware unten
> ist die echte Struktur (sie nutzt die eingebettete (vendored) `atome.c`/`atome.h`-Engine und
> die trainierten ATOMECL01-Kopf-Blobs erneut), aber Tok/s auf dem Board, RAM-Hochwassermarke und
> Live-ADC/I2S-Erfassung werden **hier nicht gemessen**. Der C-Dispatcher auf der Host-Seite
> `c_engine/superesp/superesp_os.c` *wird* kompiliert und getestet (siehe superesp-Tests).

## Was es tut (die "OS"-Idee)
Beim Booten:
1. Liest die eigene Telemetrie des ESP32 — `esp_get_free_heap_size()`, interner Temperatur-
   sensor, Wi-Fi-RSSI, ADC-Kanäle, Hall, Touch — in den **OS-Fusionsframe**.
2. Quantisiert diesen Frame zu Bytes (unter Nutzung der pro Merkmal aus `os_telem.tok.json`
   gebackenen `vmin/vmax`) und führt `atome_classify` mit dem **OS-Kopf** aus, um einen
   Gerätezustand zu erhalten (normal / low_memory / overheating / wifi_degraded / power_fault).
3. Wendet die Lastabwurf-Richtlinie an (z. B. deaktiviert die Audio-Köpfe bei
   Überhitzung), liest dann den aktiven Sensor (ADC für agri, I2S-Mikrofon für voice)
   und verteilt diesen Frame an seinen Kopf — mit Abstention bei Unsicherheit.

So läuft Atome als Geräte-Supervisor, nicht als Textgenerator. Alle 7 Köpfe teilen sich
einen Engine-Build (dieselbe geteilte Konfig); jeder Kopf ist ein anderer eingebetteter Blob.

## Zum Bauen (auf einer Maschine mit ESP-IDF + einem Board)
```
idf.py set-target esp32
idf.py build            # compile-time config in main/CMakeLists.txt
idf.py -p /dev/ttyUSB0 flash monitor
```
Die Kompilierzeit-Defines (d_model=32, n_layers=2, ...) MÜSSEN mit der geteilten
SuperESP-Konfig (superesp/framework/config.py) übereinstimmen, mit der die Blobs exportiert wurden.
