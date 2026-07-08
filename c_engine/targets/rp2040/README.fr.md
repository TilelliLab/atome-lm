[English](README.md) · **Français** · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# Atome LLM sur le Raspberry Pi Pico (RP2040)

Recette de bout en bout pour faire tourner un modèle de langage ternaire de 60 K paramètres
sur un microcontrôleur à 4 $ et rapporter les jetons-par-seconde sur la liaison série.

## Ce qu'il vous faut

- Un Raspberry Pi Pico (n'importe quelle carte RP2040 ; Pico, Pico W, Pico 2, clones).
- Un câble USB (Micro-USB pour le Pico d'origine, USB-C pour le Pico 2).
- Chaîne d'outils : `arm-none-eabi-gcc`, `cmake`, `make`, `git`.
- Disque : ~500 Mo pour le Pico SDK + ~50 Mo pour la compilation.

## Configuration ponctuelle

```bash
sudo apt install gcc-arm-none-eabi cmake make build-essential libstdc++-arm-none-eabi-newlib

git clone --depth 1 https://github.com/raspberrypi/pico-sdk
export PICO_SDK_PATH=$PWD/pico-sdk
git -C "$PICO_SDK_PATH" submodule update --init
```

## Compiler le firmware

Depuis la racine du projet :

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

Vous devriez maintenant avoir `build/atome_pico.uf2` (~200 Ko).

## Flasher la carte

1. Maintenez le bouton **BOOTSEL** du Pico en le branchant en USB.
2. Relâchez ; la carte se monte comme un disque USB nommé **RPI-RP2**.
3. Glissez-déposez `atome_pico.uf2` sur le disque. Le Pico redémarre
   automatiquement une fois la copie terminée.

## Lire la sortie

Ouvrez un terminal série à **115 200 8N1** (`minicom -D /dev/ttyACM0 -b 115200`,
ou n'importe quelle appli série hôte). Vous devriez voir :

```
ATOME-PICO-START prompt_len=4 new_tokens=16 max_seq=32
TOK 0 117 us=42120
TOK 1  98 us=43755
TOK 2 215 us=43818
...
ATOME-PICO-END total_us=698540 tokens=16
```

Chaque ligne `TOK N B us=...` est un octet généré et la latence par pas
en microsecondes, mesurée par le minuteur matériel du RP2040 (aucune horloge hôte
impliquée). Aux valeurs par défaut du moteur (60,8 K paramètres, 4 couches,
`max_seq=32`) sur un RP2040 de série à 125 MHz, attendez-vous à environ **15-25
jetons/sec** avec la boucle de génération de référence côté Python et environ
**40-60 jetons/sec** si vous passez au chemin C SSM en streaming (voir le Bug A
dans le README du projet — ce correctif est conditionné à l'accord de l'utilisateur).

## Mesurer la puissance

Câblez une résistance shunt de 1 Ω sur la ligne `VBUS` du Pico, échantillonnez avec un
multimètre isolé USB ou un Joulescope. Les Joules-par-jeton sont l'intégrale de la
puissance sur le temps entre deux lignes `TOK` consécutives. Un tirage
RP2040 actif typique est ~30 mA à 3,3 V → 100 mW — à 25 jetons/s c'est
**4 mJ par jeton**.

## Dépannage

- **Pas de périphérique série.** Le Pico SDK expose à la fois l'USB CDC et l'UART. Si
  vous ne voyez pas `/dev/ttyACM0`, vérifiez `dmesg | tail` pour une ligne
  d'énumération USB ; si elle est là mais que le périphérique manque, votre utilisateur
  n'est peut-être pas dans le groupe `dialout` / `tty`.
- **`atome_load` échoue.** La cause la plus fréquente est un décalage de config
  entre le point de contrôle entraîné et les defines côté Pico. Recompilez
  avec `cmake -DATOME_D_MODEL=... -DATOME_N_LAYERS=...` correspondant à
  la config de votre point de contrôle (voir l'affichage du script d'export).
- **Plus de flash.** La config par défaut tient bien en dessous de 200 Ko. Si vous
  avez augmenté `d_model` ou `n_layers`, le blob .atome peut dépasser les 2 Mo de
  flash. Réduisez la taille du modèle, ou déplacez le blob sur une carte SD externe
  (pas encore pris en charge par ce firmware).
