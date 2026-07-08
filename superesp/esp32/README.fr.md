[English](README.md) · **Français** · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# Batterie de tests d'applications ESP32 SuperESP

Testez **les 12 applications SuperESP sur un vrai ESP32 en une seule commande**, puis obtenez un
rapport par application (réussite/échec, classe sur appareil vs attendue, tas libre, bugs).

> La carte sur laquelle nous avons testé en premier : **ESP32-WROOM-32** (ESP32-D0WD-V3, 4 Mo de flash, sans
> PSRAM, /dev/ttyUSB0 @ 115200). L'état de SuperESP est ~27 Ko (vs les 159 Ko du LM 944K),
> il tient donc avec une immense marge — voir `superesp/cli.py targets`.

## Une seule commande (sur VOTRE machine, carte branchée)
```bash
. ~/esp-idf/export.sh           # once per shell (install: superesp/cli.py setup)
./superesp/esp32/run_battery.sh # doctor→detect→build→flash→capture→grade→report
# env overrides: PORT=/dev/ttyUSB0 TARGET=esp32 CAPTURE_S=60
```
Sortie : `superesp/esp32/reports/REPORT.md` + `report.json` + les `serial_*.log` bruts.

## Ce qu'elle fait
1. **gen_battery.py** cuit les 12 blobs de tête + un vecteur de test chacun + la
   **classe attendue en or côté hôte-C** dans `battery_data.h` (+ `golden.json`).
2. **battery_main.c** (une seule source, se compile pour QEMU *et* ESP-IDF) charge chaque
   tête, classifie son vecteur, et affiche
   `HEAD <name> CLASS <got> EXPECT <want> PASS|FAIL HEAP <kb>`.
3. **parse_report.py** note le journal série contre l'or → rapport par application,
   honnêtement étiqueté **silicium réel** (HEAP présent) vs **QEMU/émulation**.

## Déjà validé en émulation (ce dépôt, sans carte)
Le firmware exact a été exécuté dans `qemu-system-arm` (Cortex-M3, vrai ARM Thumb) :
**12/12 applications PASSENT, au bit près** (`python3 -m superesp.qemu_test <head>` pour
des têtes uniques). La logique est donc prouvée avant que vous ne flashiez — l'exécution sur carte convertit
« émulé-correct » en « silicium-correct » et ajoute de vrais nombres de tas/timing.

## Si quelque chose échoue
La section **Bugs / erreurs** du rapport capture : les têtes manquantes (série
tronquée / n'a pas tourné), les `LOAD_FAIL` (problème de flash/blob), les décalages de classe, et
les crashs suspectés (`Guru Meditation` / panique sans `BATTERY DONE`). Collez
`reports/REPORT.md` en réponse et je diagnostiquerai.
