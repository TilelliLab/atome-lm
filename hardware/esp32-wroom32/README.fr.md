[English](README.md) · **Français** · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# Atome sur silicium réel — ESP32-WROOM-32

Le point de contrôle Atome **944K** fourni tournant sur un **ESP32-WROOM-32 physique**
(ESP32-D0WD-V3, 4 Mo de flash, **sans PSRAM**), générant un texte cohérent **entièrement
hors ligne** à **~1,0 tok/s** (cœur 240 MHz, flash 80 MHz). C'est le propre `c_engine`
du dépôt — le même moteur qui passe les tests unitaires hôte et le test de parité QEMU
Cortex-M3 — maintenant vérifié sur du matériel réel.

> **Périmètre honnête.** Ceci est un artefact de *preuve d'exécution + reproductibilité*, pas
> une victoire de benchmark ni une douve (moat). ~1 tok/s pour un LM sous-1M sur un MCU est un terrain connu
> (cf. `llama2.c`-sur-MCU, TinyML). Aucun face-à-face sur la même puce contre une alternative
> n'a été exécuté — c'est un travail futur, pas une affirmation ici. Le débit est limité par le flash
> (~270 Ko de poids ternaires lus depuis la flash SPI par jeton).

Sortie mesurée (`evidence/serial_boot_log_esp32_wroom32.txt`) :

```
config : d=256 layers=8 head=64 seq=24  state=159 KB   (cpu 240 MHz, flash 80 MHz)
Once    ->  upon a time, there
The dog ->  was so excited.
A girl  ->  was so happy to h
average: 1.0 tok/s
```

## Vérifiez-le vous-même en ~2 minutes (pas besoin d'ESP-IDF)
Récupérez le `atome_esp32_merged.bin` précompilé depuis la Release GitHub, puis :
```bash
pip install esptool pyserial
esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460800 write_flash 0x0 atome_esp32_merged.bin
python3 -m serial.tools.miniterm /dev/ttyUSB0 115200      # press the board's EN button
```
Vérifiez d'abord le binaire contre `SHA256SUMS` dans la Release.

## Compiler depuis les sources
Nécessite ESP-IDF v5.3. `atome.sh` enrobe détecter → compiler → flasher → superviser et peut flasher
avec le simple `esptool` (pas d'IDF sur l'hôte de flashage) :
```bash
./atome.sh detect                 # identify the board
. ~/esp-idf/export.sh
TARGET=esp32 ./atome.sh build wroom
TARGET=esp32 ./atome.sh flash
./atome.sh monitor
```

## Profils de compilation (le moteur est dimensionné à la compilation → un binaire = un modèle)
| profil | sortie | RAM d'état | carte |
|---------|--------|-----------|-------|
| `full`  | cohérent, contexte complet (seq=128)  | ~811 KB | PSRAM (S3 …R8 / WROVER) |
| `wroom` | cohérent, contexte court (seq=24)  | ~159 KB | tout ESP32, SRAM interne |
| `toy`   | dégénéré (point de contrôle 20 KB)     | ~103 KB | tout ESP32 |

L'état 944K évolue avec le contexte, pas avec la qualité ; le plus grand bloc DRAM
contigu d'un ESP32 classique est ~168 Ko (369 Ko libres mais fragmentés), donc `wroom`
(seq=24 → 159 Ko) est le profil sans PSRAM. Une carte avec PSRAM exécute `full`.

## Notes
- `firmware/main/atome.{c,h}` sont des copies vendorisées de [`c_engine/upstream/atome.{c,h}`](../../c_engine/upstream/) (Apache-2.0), pour que cet exemple se compile en autonome.
- `firmware/main/model_full.atome` correspond exactement aux mêmes octets que [`checkpoints/atome_944k.bin`](../../checkpoints/) (md5 `b588e45f…`) ; `atome.sh build` copie le point de contrôle choisi vers `model.atome` pour l'embarquer.
- `build/` et `model.atome` sont générés et ignorés par git.
