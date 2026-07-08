[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · **Deutsch** · [日本語](README.ja.md) <!-- i18n-switcher -->

# SuperESP-ESP32-Anwendungs-Testbatterie

Teste **alle 12 SuperESP-Anwendungen auf einem echten ESP32 mit einem Befehl** und erhalte dann einen
Bericht pro Anwendung (bestanden/durchgefallen, Klasse auf dem Gerät vs. erwartet, freier Heap, Bugs).

> Das Board, auf dem wir zuerst getestet haben: **ESP32-WROOM-32** (ESP32-D0WD-V3, 4 MB Flash, kein
> PSRAM, /dev/ttyUSB0 @ 115200). Der State von SuperESP ist ~27 KB (vs. den 159 KB des 944K-LM),
> passt also mit riesigem Spielraum — siehe `superesp/cli.py targets`.

## Ein Befehl (auf DEINER Maschine, Board eingesteckt)
```bash
. ~/esp-idf/export.sh           # once per shell (install: superesp/cli.py setup)
./superesp/esp32/run_battery.sh # doctor→detect→build→flash→capture→grade→report
# env overrides: PORT=/dev/ttyUSB0 TARGET=esp32 CAPTURE_S=60
```
Ausgabe: `superesp/esp32/reports/REPORT.md` + `report.json` + die rohen `serial_*.log`.

## Was es tut
1. **gen_battery.py** backt alle 12 Kopf-Blobs + je einen Testvektor + die
   **Host-C-Golden-Erwartungsklasse** in `battery_data.h` (+ `golden.json`).
2. **battery_main.c** (eine Quelle, kompiliert für QEMU *und* ESP-IDF) lädt jeden
   Kopf, klassifiziert seinen Vektor und gibt
   `HEAD <name> CLASS <got> EXPECT <want> PASS|FAIL HEAP <kb>` aus.
3. **parse_report.py** benotet das serielle Log gegen das Golden → Bericht pro Anwendung,
   ehrlich gekennzeichnet als **echtes Silizium** (HEAP vorhanden) vs. **QEMU/Emulation**.

## Bereits in der Emulation validiert (dieses Repo, kein Board)
Die exakte Firmware lief in `qemu-system-arm` (Cortex-M3, echtes ARM Thumb):
**12/12 Anwendungen BESTEHEN, bit-genau** (`python3 -m superesp.qemu_test <head>` für
einzelne Köpfe). Die Logik ist also bewiesen, bevor du flashst — der Board-Lauf verwandelt
"emuliert-korrekt" in "silizium-korrekt" und fügt echte Heap-/Timing-Zahlen hinzu.

## Falls etwas fehlschlägt
Der Abschnitt **Bugs / errors** des Berichts erfasst: fehlende Köpfe (seriell
abgeschnitten / lief nicht), `LOAD_FAIL` (Flash-/Blob-Problem), Klassen-Diskrepanzen und
vermutete Abstürze (`Guru Meditation` / Panic ohne `BATTERY DONE`). Füge
`reports/REPORT.md` als Antwort ein, und ich diagnostiziere.
