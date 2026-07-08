[English](README.md) · [Français](README.fr.md) · **Español** · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# Esqueleto de firmware SuperESP (ESP32 / ESP-IDF)

> **Estado: esqueleto DE SOLO-COMPILACIÓN — NO FLASHEADO, NO MEDIDO en silicio.**
> Esta máquina no tiene un ESP32 físico ni la cadena de herramientas ESP-IDF. El firmware de abajo
> es la estructura real (reutiliza el motor `atome.c`/`atome.h` vendorizado y
> los blobs de cabeza ATOMECL01 entrenados), pero los tok/s en la placa, la marca alta de RAM y
> la captura ADC/I2S en vivo **no se miden aquí**. El despachador C del lado del host
> `c_engine/superesp/superesp_os.c` *sí* se compila y prueba (véase los tests de superesp).

## Qué hace (la idea del «OS»)
Al arrancar, el firmware:
1. Lee la propia telemetría del ESP32 — `esp_get_free_heap_size()`, sensor de temperatura
   interno, RSSI Wi-Fi, canales ADC, hall, touch — en la **trama OS fusionada**.
2. Cuantiza esa trama a bytes (usando los `vmin/vmax` por característica horneados desde
   `os_telem.tok.json`) y ejecuta `atome_classify` con la **cabeza OS** para obtener un
   estado del dispositivo (normal / low_memory / overheating / wifi_degraded / power_fault).
3. Aplica la política de descarga de carga (p. ej. deshabilita las cabezas de audio al
   sobrecalentarse), luego lee el sensor activo (ADC para agri, micro I2S para voice)
   y despacha esa trama a su cabeza — absteniéndose cuando hay incertidumbre.

Así Atome corre como el supervisor del dispositivo, no como un generador de texto. Las 7 cabezas comparten
una única compilación del motor (misma config compartida); cada cabeza es un blob incrustado distinto.

## Para compilar (en una máquina con ESP-IDF + una placa)
```
idf.py set-target esp32
idf.py build            # compile-time config in main/CMakeLists.txt
idf.py -p /dev/ttyUSB0 flash monitor
```
Los defines de compilación (d_model=32, n_layers=2, ...) DEBEN coincidir con la config
compartida de SuperESP (superesp/framework/config.py) con la que se exportaron los blobs.
