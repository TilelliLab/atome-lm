[English](README.md) · [Français](README.fr.md) · **Español** · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# Batería de tests de aplicaciones ESP32 de SuperESP

Prueba **las 12 aplicaciones SuperESP en un ESP32 real con un solo comando**, luego obtén un
informe por aplicación (pasa/falla, clase en el dispositivo vs esperada, heap libre, bugs).

> La placa en la que probamos primero: **ESP32-WROOM-32** (ESP32-D0WD-V3, 4 MB de flash, sin
> PSRAM, /dev/ttyUSB0 @ 115200). El estado de SuperESP es ~27 KB (vs los 159 KB del LM 944K),
> así que cabe con muchísimo margen — véase `superesp/cli.py targets`.

## Un solo comando (en TU máquina, con la placa conectada)
```bash
. ~/esp-idf/export.sh           # once per shell (install: superesp/cli.py setup)
./superesp/esp32/run_battery.sh # doctor→detect→build→flash→capture→grade→report
# env overrides: PORT=/dev/ttyUSB0 TARGET=esp32 CAPTURE_S=60
```
Salida: `superesp/esp32/reports/REPORT.md` + `report.json` + los `serial_*.log` en bruto.

## Qué hace
1. **gen_battery.py** hornea los 12 blobs de cabeza + un vector de prueba cada uno + la
   **clase de oro esperada del host-C** en `battery_data.h` (+ `golden.json`).
2. **battery_main.c** (una sola fuente, compila para QEMU *y* ESP-IDF) carga cada
   cabeza, clasifica su vector, e imprime
   `HEAD <name> CLASS <got> EXPECT <want> PASS|FAIL HEAP <kb>`.
3. **parse_report.py** califica el registro serie contra el oro → informe por aplicación,
   honestamente etiquetado **silicio real** (HEAP presente) vs **QEMU/emulación**.

## Ya validado en emulación (este repo, sin placa)
El firmware exacto se ejecutó en `qemu-system-arm` (Cortex-M3, ARM Thumb real):
**12/12 aplicaciones PASAN, al bit** (`python3 -m superesp.qemu_test <head>` para
cabezas individuales). Así que la lógica está probada antes de que flashees — la ejecución en la placa convierte
«emulado-correcto» en «silicio-correcto» y añade números reales de heap/tiempo.

## Si algo falla
La sección **Bugs / errors** del informe captura: cabezas faltantes (serie
truncada / no se ejecutó), `LOAD_FAIL` (problema de flash/blob), desajustes de clase, y
cuelgues sospechados (`Guru Meditation` / panic sin `BATTERY DONE`). Pega
`reports/REPORT.md` en respuesta y lo diagnosticaré.
