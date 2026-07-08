[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · **Deutsch** · [日本語](README.ja.md) <!-- i18n-switcher -->

# Atome LLM — eingebettete (vendored) C-Engine

Dieses Verzeichnis enthält die C99-Inferenz-Engine, die Atome-LLM-Checkpoints auf Mikrocontrollern und auf dem Host ausführt. Die Python-Seite des Projekts (`atome_llm/`) trainiert und exportiert; die C-Seite hier lädt das exportierte `.atome`-Binary und führt den Forward-Pass auf dem Gerät aus.

## Aufbau

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

## Woher dies stammt

Die Dateien in `upstream/` sind eingebettete (vendored) Kopien einer internen C-Engine-Quelle mit Stand 2026-05-03. Das Vendoring (statt Submodul oder Symlink) ist beabsichtigt: atome-llm soll die Verteilungseinheit sein. Um Upstream-Änderungen einzuziehen, kopiere die Dateien erneut und führe die Paritätstest-Suite erneut aus (`pytest tests/test_parity_with_c.py tests/test_qemu_parity.py`).

Ein kleiner Unterschied zum wortgetreuen Upstream: ein einzelner Kommentar in `atome.h` wurde in "Atome block" umbenannt (er hatte auf den Vorgängernamen verwiesen). Keine funktionale Änderung — Kommentare kompilieren nicht.

## Für den Host kompilieren (x86-64)

Der einfachste Pfad — verwendet von `tests/test_parity_with_c.py`:

```bash
gcc -O2 -std=c99 -DATOME_D_MODEL=16 -DATOME_N_LAYERS=2 ... \
    -I c_engine/upstream parity_main.c c_engine/upstream/atome.c -lm
```

## Für ARM Cortex-M kompilieren

Zwei Schichten:

1. **Reine Kompilierungs-Sanity-Prüfung** über mehrere Cortex-M-Varianten — `python scripts/cross_compile.py` erzeugt eine Größentabelle (`text/data/bss` pro Architektur). Fängt Portabilitätsregressionen ab und liefert echte Binärgrößenzahlen auf dem Ziel.
2. **Vollständige Firmware** für QEMU MPS2-AN385 — `make -C c_engine/targets/cortex-m3` erzeugt ein `.elf`, das unter `qemu-system-arm` mit Semihosting läuft. Der Ende-zu-Ende-Python-↔-Cortex-M3-Paritätstest liegt in `tests/test_qemu_parity.py`.

## Architektur-Hinweise

Die C-Engine nimmt an:
- Ternäre Skalierung pro Tensor (ein einzelnes FP32 pro Gewichtsmatrix)
- Embedding-Layout `(vocab, d_model)` — siehe `atome_llm/core/ternary_embedding.py`, warum das wichtig ist
- Keine Skalierung pro Zeile, keine Multi-Bank-Gewichte, kein Positions-Embedding
- `atome_block_t` hat feste Puffer nur für `local_conv`, `ssm`, `attn` und `router` — keine breite Conv, kein dichtes FFN, kein Retrieval-Pfad

Diese Einschränkungen sind tragend. Das Hinzufügen eines neuen Pfades erfordert, `atome.h`, die C-Kernel, das `.atome`-Binärformat **und** das Python-`MCUBlock` gemeinsam zu aktualisieren.
