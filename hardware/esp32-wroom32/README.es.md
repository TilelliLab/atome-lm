[English](README.md) · [Français](README.fr.md) · **Español** · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# Atome en silicio real — ESP32-WROOM-32

El checkpoint Atome **944K** incluido corriendo en un **ESP32-WROOM-32 físico**
(ESP32-D0WD-V3, 4 MB de flash, **sin PSRAM**), generando texto coherente **totalmente
sin conexión** a **~1,0 tok/s** (núcleo 240 MHz, flash 80 MHz). Este es el propio `c_engine`
del repo — el mismo motor que pasa los tests unitarios del host y el test de paridad QEMU
Cortex-M3 — ahora verificado en hardware real.

> **Alcance honesto.** Este es un artefacto de *prueba de ejecución + reproducibilidad*, no
> una victoria de benchmark ni un foso (moat). ~1 tok/s para un LM sub-1M en un MCU es terreno conocido
> (cf. `llama2.c`-en-MCU, TinyML). No se ha ejecutado ningún enfrentamiento en el mismo chip contra una
> alternativa — eso es trabajo futuro, no una afirmación aquí. El rendimiento está limitado por el flash
> (~270 KB de pesos ternarios leídos de la flash SPI por token).

Salida medida (`evidence/serial_boot_log_esp32_wroom32.txt`):

```
config : d=256 layers=8 head=64 seq=24  state=159 KB   (cpu 240 MHz, flash 80 MHz)
Once    ->  upon a time, there
The dog ->  was so excited.
A girl  ->  was so happy to h
average: 1.0 tok/s
```

## Verifícalo tú mismo en ~2 minutos (sin necesidad de ESP-IDF)
Consigue el `atome_esp32_merged.bin` precompilado desde la Release de GitHub, luego:
```bash
pip install esptool pyserial
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460800 write_flash 0x0 atome_esp32_merged.bin
python3 -m serial.tools.miniterm /dev/ttyUSB0 115200      # press the board's EN button
```
Comprueba primero el binario contra `SHA256SUMS` en la Release.

## Compilar desde el código fuente
Necesita ESP-IDF v5.3. `atome.sh` envuelve detectar → compilar → flashear → monitorizar y puede flashear
con el simple `esptool` (sin IDF en el host de flasheo):
```bash
./atome.sh detect                 # identify the board
. ~/esp-idf/export.sh
TARGET=esp32 ./atome.sh build wroom
TARGET=esp32 ./atome.sh flash
./atome.sh monitor
```

## Perfiles de compilación (el motor se dimensiona en tiempo de compilación → un binario = un modelo)
| perfil | salida | RAM de estado | placa |
|---------|--------|-----------|-------|
| `full`  | coherente, contexto completo (seq=128)  | ~811 KB | PSRAM (S3 …R8 / WROVER) |
| `wroom` | coherente, contexto corto (seq=24)  | ~159 KB | cualquier ESP32, SRAM interna |
| `toy`   | degenerado (checkpoint de 20 KB)     | ~103 KB | cualquier ESP32 |

El estado 944K escala con el contexto, no con la calidad; el mayor bloque de DRAM
contiguo de un ESP32 clásico es ~168 KB (369 KB libres pero fragmentados), así que `wroom`
(seq=24 → 159 KB) es el perfil sin PSRAM. Una placa con PSRAM ejecuta `full`.

## Notas
- `firmware/main/atome.{c,h}` son copias vendorizadas de [`c_engine/upstream/atome.{c,h}`](../../c_engine/upstream/) (Apache-2.0), de modo que este ejemplo compila de forma independiente.
- `firmware/main/model_full.atome` son exactamente los mismos bytes que [`checkpoints/atome_944k.bin`](../../checkpoints/) (md5 `b588e45f…`); `atome.sh build` copia el checkpoint elegido a `model.atome` para incrustarlo.
- `build/` y `model.atome` son generados e ignorados por git.
