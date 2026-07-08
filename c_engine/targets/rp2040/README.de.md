[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · **Deutsch** · [日本語](README.ja.md) <!-- i18n-switcher -->

# Atome LLM auf dem Raspberry Pi Pico (RP2040)

Ein Ende-zu-Ende-Rezept, um ein 60 K-Parameter-ternäres Sprachmodell auf einem
4-Dollar-Mikrocontroller zum Laufen zu bringen und Tokens-pro-Sekunde über seriell zu melden.

## Was du brauchst

- Ein Raspberry Pi Pico (jedes RP2040-Board; Pico, Pico W, Pico 2, Klone).
- Ein USB-Kabel (Micro-USB für den originalen Pico, USB-C für den Pico 2).
- Toolchain: `arm-none-eabi-gcc`, `cmake`, `make`, `git`.
- Disk: ~500 MB für das Pico SDK + ~50 MB für den Build.

## Einmalige Einrichtung

```bash
sudo apt install gcc-arm-none-eabi cmake make build-essential libstdc++-arm-none-eabi-newlib

git clone --depth 1 https://github.com/raspberrypi/pico-sdk
export PICO_SDK_PATH=$PWD/pico-sdk
git -C "$PICO_SDK_PATH" submodule update --init
```

## Die Firmware bauen

Aus dem Projekt-Root:

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

Du solltest nun `build/atome_pico.uf2` (~200 KB) haben.

## Das Board flashen

1. Halte den **BOOTSEL**-Knopf am Pico gedrückt, während du ihn in USB steckst.
2. Loslassen; das Board wird als USB-Laufwerk namens **RPI-RP2** gemountet.
3. Ziehe `atome_pico.uf2` per Drag-and-Drop auf das Laufwerk. Der Pico startet
   automatisch neu, wenn das Kopieren fertig ist.

## Die Ausgabe lesen

Öffne ein serielles Terminal mit **115 200 8N1** (`minicom -D /dev/ttyACM0 -b 115200`,
oder eine beliebige serielle Host-App). Du solltest sehen:

```
ATOME-PICO-START prompt_len=4 new_tokens=16 max_seq=32
TOK 0 117 us=42120
TOK 1  98 us=43755
TOK 2 215 us=43818
...
ATOME-PICO-END total_us=698540 tokens=16
```

Jede `TOK N B us=...`-Zeile ist ein generiertes Byte und die Latenz pro Schritt
in Mikrosekunden, gemessen vom RP2040-Hardware-Timer (keine Host-Uhr
beteiligt). Bei den Engine-Standardwerten (60,8 K Parameter, 4 Schichten,
`max_seq=32`) auf dem serienmäßigen 125-MHz-RP2040 erwarte grob **15–25
Tokens/Sek.** mit der Referenz-Generierungsschleife der Python-Seite und grob
**40–60 Tokens/Sek.**, wenn du auf den Streaming-SSM-C-Pfad umschaltest (siehe Bug A
im Projekt-README — dieser Fix ist an die Zustimmung des Nutzers gebunden).

## Leistung messen

Verdrahte einen 1-Ω-Shunt-Widerstand an der `VBUS`-Leitung des Pico, sample mit einem
USB-isolierten Multimeter oder einem Joulescope. Joule-pro-Token ist das Integral der
Leistung über die Zeit zwischen zwei aufeinanderfolgenden `TOK`-Zeilen. Eine typische
aktive RP2040-Stromaufnahme beträgt ~30 mA bei 3,3 V → 100 mW — bei 25 Tok/s sind das
**4 mJ pro Token**.

## Fehlerbehebung

- **Kein serielles Gerät.** Das Pico SDK legt sowohl USB CDC als auch UART offen. Falls
  du `/dev/ttyACM0` nicht siehst, prüfe `dmesg | tail` auf eine USB-
  Enumerierungszeile; falls sie da ist, das Gerät aber fehlt, ist dein Nutzer
  möglicherweise nicht in der Gruppe `dialout` / `tty`.
- **`atome_load` schlägt fehl.** Die häufigste Ursache ist eine Konfig-Diskrepanz
  zwischen dem trainierten Checkpoint und den Defines auf der Pico-Seite. Baue
  mit `cmake -DATOME_D_MODEL=... -DATOME_N_LAYERS=...` neu, passend zu
  deiner Checkpoint-Konfig (siehe die Ausgabe des Export-Skripts).
- **Kein Flash mehr.** Die Standardkonfig passt deutlich unter 200 KB. Falls du
  `d_model` oder `n_layers` erhöht hast, könnte der .atome-Blob die 2 MB
  Flash überschreiten. Verringere die Modellgröße, oder verschiebe den Blob auf eine externe SD-Karte
  (von dieser Firmware noch nicht unterstützt).
