[English](README.md) · [Français](README.fr.md) · **Español** · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# Atome LLM en la Raspberry Pi Pico (RP2040)

Receta de principio a fin para poner en marcha un modelo de lenguaje ternario de 60 K parámetros
en un microcontrolador de 4 $ y reportar los tokens-por-segundo por serie.

## Qué necesitas

- Una Raspberry Pi Pico (cualquier placa RP2040; Pico, Pico W, Pico 2, clones).
- Un cable USB (Micro-USB para la Pico original, USB-C para la Pico 2).
- Cadena de herramientas: `arm-none-eabi-gcc`, `cmake`, `make`, `git`.
- Disco: ~500 MB para el Pico SDK + ~50 MB para la compilación.

## Configuración única

```bash
sudo apt install gcc-arm-none-eabi cmake make build-essential libstdc++-arm-none-eabi-newlib

git clone --depth 1 https://github.com/raspberrypi/pico-sdk
export PICO_SDK_PATH=$PWD/pico-sdk
git -C "$PICO_SDK_PATH" submodule update --init
```

## Compilar el firmware

Desde la raíz del proyecto:

```bash
# 1. Train (or download) a checkpoint, then export to .atome:
python scripts/train_demo.py --data data/tinystories.txt --steps 800 \
    --output checkpoints/atome_demo.pt
python scripts/export_to_atome.py --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome

# 2. Bake the binary into a C array:
cd c_engine/targets/rp2040
xxd -i -n model_atome ../../../checkpoints/atome_demo.atome > model_data.h

# 3. Build:
mkdir -p build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j
```

Ahora deberías tener `build/atome_pico.uf2` (~200 KB).

## Flashear la placa

1. Mantén pulsado el botón **BOOTSEL** de la Pico mientras la conectas al USB.
2. Suelta; la placa se monta como un disco USB llamado **RPI-RP2**.
3. Arrastra y suelta `atome_pico.uf2` en el disco. La Pico se reinicia
   automáticamente cuando termina la copia.

## Leer la salida

Abre un terminal serie a **115 200 8N1** (`minicom -D /dev/ttyACM0 -b 115200`,
o cualquier app serie del host). Deberías ver:

```
ATOME-PICO-START prompt_len=4 new_tokens=16 max_seq=32
TOK 0 117 us=42120
TOK 1  98 us=43755
TOK 2 215 us=43818
...
ATOME-PICO-END total_us=698540 tokens=16
```

Cada línea `TOK N B us=...` es un byte generado y la latencia por paso
en microsegundos, medida por el temporizador hardware del RP2040 (sin reloj del host
involucrado). Con los valores por defecto del motor (60,8 K parámetros, 4 capas,
`max_seq=32`) en un RP2040 de serie a 125 MHz, espera aproximadamente **15-25
tokens/seg** con el bucle de generación de referencia del lado Python y aproximadamente
**40-60 tokens/seg** si cambias a la ruta C de SSM en streaming (véase el Bug A
en el README del proyecto — esa corrección está condicionada a la aprobación del usuario).

## Medir la potencia

Cablea una resistencia shunt de 1 Ω en la línea `VBUS` de la Pico, muestrea con un
multímetro aislado por USB o un Joulescope. Los julios-por-token son la integral de la
potencia sobre el tiempo entre dos líneas `TOK` consecutivas. Un consumo
activo típico del RP2040 es ~30 mA a 3,3 V → 100 mW — a 25 tok/s eso es
**4 mJ por token**.

## Solución de problemas

- **Sin dispositivo serie.** El Pico SDK expone tanto USB CDC como UART. Si
  no ves `/dev/ttyACM0`, comprueba `dmesg | tail` en busca de una línea de
  enumeración USB; si está ahí pero el dispositivo falta, tu usuario
  puede no estar en el grupo `dialout` / `tty`.
- **`atome_load` falla.** La causa más común es un desajuste de config
  entre el checkpoint entrenado y los defines del lado Pico. Recompila
  con `cmake -DATOME_D_MODEL=... -DATOME_N_LAYERS=...` que coincidan con
  la config de tu checkpoint (véase la salida del script de exportación).
- **Sin flash.** La config por defecto cabe muy por debajo de 200 KB. Si
  aumentaste `d_model` o `n_layers`, el blob .atome puede exceder los 2 MB de
  flash. Reduce el tamaño del modelo, o mueve el blob a una tarjeta SD externa
  (aún no soportado por este firmware).
