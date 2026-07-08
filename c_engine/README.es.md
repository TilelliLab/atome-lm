[English](README.md) · [Français](README.fr.md) · **Español** · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# Atome LLM — motor C vendorizado

Este directorio contiene el motor de inferencia C99 que ejecuta los checkpoints de Atome LLM en microcontroladores y en el host. El lado Python del proyecto (`atome_llm/`) entrena y exporta; el lado C de aquí carga el binario `.atome` exportado y ejecuta la pasada forward en el dispositivo.

## Estructura

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

## De dónde viene esto

Los archivos en `upstream/` son copias vendorizadas de una fuente interna del motor C con fecha del 2026-05-03. La vendorización (en lugar de submódulo o enlace simbólico) es intencionada: atome-llm debe ser la unidad de distribución. Para incorporar cambios de upstream, vuelve a copiar los archivos y reejecuta la suite de tests de paridad (`pytest tests/test_parity_with_c.py tests/test_qemu_parity.py`).

Una pequeña diferencia respecto al upstream literal: un único comentario en `atome.h` fue renombrado a «Atome block» (se refería al nombre anterior). Sin cambio funcional — los comentarios no compilan.

## Compilar para el host (x86-64)

La ruta más simple — usada por `tests/test_parity_with_c.py`:

```bash
gcc -O2 -std=c99 -DATOME_D_MODEL=16 -DATOME_N_LAYERS=2 ... \
    -I c_engine/upstream parity_main.c c_engine/upstream/atome.c -lm
```

## Compilar para ARM Cortex-M

Dos capas:

1. **Comprobación de solo-compilación** sobre varias variantes Cortex-M — `python scripts/cross_compile.py` produce una tabla de tamaños (`text/data/bss` por arquitectura). Detecta regresiones de portabilidad y da números reales de tamaño de binario en el objetivo.
2. **Firmware completo** para QEMU MPS2-AN385 — `make -C c_engine/targets/cortex-m3` produce un `.elf` que corre bajo `qemu-system-arm` con semihosting. El test de paridad de principio a fin Python ↔ Cortex-M3 vive en `tests/test_qemu_parity.py`.

## Notas de arquitectura

El motor C asume:
- Escala ternaria por tensor (un único FP32 por matriz de pesos)
- Disposición de embedding `(vocab, d_model)` — véase `atome_llm/core/ternary_embedding.py` para entender por qué esto importa
- Sin escala por fila, sin pesos multibanco, sin embedding posicional
- `atome_block_t` tiene búferes fijos solo para `local_conv`, `ssm`, `attn` y `router` — sin conv ancha, sin FFN densa, sin vía de recuperación

Estas restricciones son portantes. Añadir una nueva vía requiere actualizar `atome.h`, los kernels C, el formato binario `.atome` **y** el `MCUBlock` de Python juntos.
