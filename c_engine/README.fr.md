[English](README.md) · **Français** · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# Atome LLM — moteur C vendorisé

Ce répertoire contient le moteur d'inférence C99 qui exécute les points de contrôle Atome LLM sur microcontrôleurs et sur l'hôte. Le côté Python du projet (`atome_llm/`) entraîne et exporte ; le côté C ici charge le binaire `.atome` exporté et exécute la passe forward sur l'appareil.

## Disposition

```
c_engine/
├── README.md                  this file
├── upstream/
│   ├── atome.h                public API + compile-time #defines
│   └── atome.c                implementation (~570 lines, zero-heap, integer-arithmetic forward)
└── targets/
    └── cortex-m3/             ARM Cortex-M3 firmware that runs in QEMU MPS2-AN385
        ├── firmware.c
        ├── startup.s
        ├── linker.ld
        └── Makefile
```

## D'où cela vient

Les fichiers de `upstream/` sont des copies vendorisées d'une source interne de moteur C datée du 2026-05-03. La vendorisation (plutôt que le sous-module ou le lien symbolique) est intentionnelle : atome-llm doit être l'unité de distribution. Pour intégrer les changements upstream, recopiez les fichiers et relancez la suite de tests de parité (`pytest tests/test_parity_with_c.py tests/test_qemu_parity.py`).

Un petit écart par rapport à l'upstream littéral : un unique commentaire dans `atome.h` a été renommé « Atome block » (il faisait référence au nom précédent). Aucun changement fonctionnel — les commentaires ne se compilent pas.

## Compiler pour l'hôte (x86-64)

Le chemin le plus simple — utilisé par `tests/test_parity_with_c.py` :

```bash
gcc -O2 -std=c99 -DATOME_D_MODEL=16 -DATOME_N_LAYERS=2 ... \
    -I c_engine/upstream parity_main.c c_engine/upstream/atome.c -lm
```

## Compiler pour ARM Cortex-M

Deux couches :

1. **Vérification de compilation seule** sur plusieurs variantes Cortex-M — `python scripts/cross_compile.py` produit un tableau de tailles (`text/data/bss` par architecture). Détecte les régressions de portabilité et donne de vrais chiffres de taille de binaire sur cible.
2. **Firmware complet** pour QEMU MPS2-AN385 — `make -C c_engine/targets/cortex-m3` produit un `.elf` qui tourne sous `qemu-system-arm` avec semihosting. Le test de parité de bout en bout Python ↔ Cortex-M3 se trouve dans `tests/test_qemu_parity.py`.

## Notes d'architecture

Le moteur C suppose :
- Une échelle ternaire par tenseur (un seul FP32 par matrice de poids)
- Une disposition de plongement `(vocab, d_model)` — voir `atome_llm/core/ternary_embedding.py` pour comprendre pourquoi cela compte
- Pas d'échelle par ligne, pas de poids multi-bancs, pas de plongement positionnel
- `atome_block_t` n'a des tampons fixes que pour `local_conv`, `ssm`, `attn` et `router` — pas de conv large, pas de FFN dense, pas de voie de récupération

Ces contraintes sont porteuses. Ajouter une nouvelle voie exige de mettre à jour `atome.h`, les noyaux C, le format binaire `.atome` **et** le `MCUBlock` Python ensemble.
