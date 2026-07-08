[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · **Deutsch** · [日本語](README.ja.md) <!-- i18n-switcher -->

# Atome auf echtem Silizium — ESP32-WROOM-32

Der mitgelieferte **944K**-Atome-Checkpoint läuft auf einem **physischen ESP32-WROOM-32**
(ESP32-D0WD-V3, 4 MB Flash, **kein PSRAM**) und generiert kohärenten Text **vollständig
offline** mit **~1,0 Tok/s** (240-MHz-Kern, 80-MHz-Flash). Dies ist die eigene `c_engine`
des Repos — dieselbe Engine, die die Host-Unit-Tests und den QEMU-Cortex-M3-Paritätstest
besteht — jetzt auf echter Hardware verifiziert.

> **Ehrlicher Umfang.** Dies ist ein *Ausführungsbeweis- + Reproduzierbarkeits*-Artefakt, kein
> Benchmark-Sieg und kein Burggraben (moat). ~1 Tok/s für ein Sub-1M-LM auf einem MCU ist bekanntes Terrain
> (vgl. `llama2.c`-on-MCU, TinyML). Es wurde kein Direktvergleich auf demselben Chip gegen eine
> Alternative durchgeführt — das ist künftige Arbeit, keine Aussage hier. Der Durchsatz ist flash-gebunden
> (~270 KB ternäre Gewichte, pro Token aus dem SPI-Flash gelesen).

Gemessene Ausgabe (`evidence/serial_boot_log_esp32_wroom32.txt`):

```
config : d=256 layers=8 head=64 seq=24  state=159 KB   (cpu 240 MHz, flash 80 MHz)
Once    ->  upon a time, there
The dog ->  was so excited.
A girl  ->  was so happy to h
average: 1.0 tok/s
```

## Verifiziere es selbst in ~2 Minuten (kein ESP-IDF nötig)
Hol dir das vorkompilierte `atome_esp32_merged.bin` aus dem GitHub-Release, dann:
```bash
pip install esptool pyserial
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460800 write_flash 0x0 atome_esp32_merged.bin
python3 -m serial.tools.miniterm /dev/ttyUSB0 115200      # press the board's EN button
```
Prüfe das Binary zuerst gegen `SHA256SUMS` im Release.

## Aus dem Quellcode bauen
Benötigt ESP-IDF v5.3. `atome.sh` umschließt erkennen → bauen → flashen → überwachen und kann mit
schlichtem `esptool` flashen (kein IDF auf dem Flash-Host):
```bash
./atome.sh detect                 # identify the board
. ~/esp-idf/export.sh
TARGET=esp32 ./atome.sh build wroom
TARGET=esp32 ./atome.sh flash
./atome.sh monitor
```

## Build-Profile (die Engine wird zur Kompilierzeit dimensioniert → ein Binary = ein Modell)
| Profil | Ausgabe | State-RAM | Board |
|---------|--------|-----------|-------|
| `full`  | kohärent, voller Kontext (seq=128)  | ~811 KB | PSRAM (S3 …R8 / WROVER) |
| `wroom` | kohärent, kurzer Kontext (seq=24)  | ~159 KB | jedes ESP32, internes SRAM |
| `toy`   | degeneriert (20-KB-Checkpoint)     | ~103 KB | jedes ESP32 |

Der 944K-State skaliert mit dem Kontext, nicht mit der Qualität; der größte zusammenhängende
DRAM-Block eines klassischen ESP32 ist ~168 KB (369 KB frei, aber fragmentiert), also ist `wroom`
(seq=24 → 159 KB) das Profil ohne PSRAM. Ein Board mit PSRAM führt `full` aus.

## Hinweise
- `firmware/main/atome.{c,h}` sind eingebettete (vendored) Kopien von [`c_engine/upstream/atome.{c,h}`](../../c_engine/upstream/) (Apache-2.0), sodass dieses Beispiel eigenständig baut.
- `firmware/main/model_full.atome` sind exakt dieselben Bytes wie [`checkpoints/atome_944k.bin`](../../checkpoints/) (md5 `b588e45f…`); `atome.sh build` kopiert den gewählten Checkpoint nach `model.atome` zum Einbetten.
- `build/` und `model.atome` werden generiert und von git ignoriert.
