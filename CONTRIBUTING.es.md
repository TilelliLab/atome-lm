[English](CONTRIBUTING.md) · [Français](CONTRIBUTING.fr.md) · **Español** · [简体中文](CONTRIBUTING.zh-CN.md) · [Deutsch](CONTRIBUTING.de.md) · [日本語](CONTRIBUTING.ja.md) <!-- i18n-switcher -->

# Contribuir a Atome LM

Gracias por considerar una contribución. Este es un proyecto pequeño y enfocado — un modelo de lenguaje ternario minúsculo + un motor de inferencia C99 que le habla al bit. Lee primero `PROJECT_CONTENT.md`; cubre lo que no debes romper.

## Inicio rápido

```bash
git clone https://github.com/TilelliLab/atome-lm
cd atome-lm
./install.sh
. .venv/bin/activate
pytest -q        # expect: 146 passed (or 145 + 1 skipped without qemu-system-arm)
```

## Reportar bugs

Abre una issue en GitHub con:

- qué ejecutaste (comando exacto)
- qué esperabas
- qué pasó (error completo, no parafraseado)
- tu plataforma: SO, versión de Python, y `python -c "import torch; print(torch.__version__)"`

Si te topas con un fallo de paridad (forward de Python ≠ forward de C), por favor adjunta la semilla que falla y cualquier checkpoint que hayas entrenado — estos son los bugs de máxima prioridad.

## Enviar una pull request

1. Haz fork del repo y crea una rama desde `main`.
2. Haz tu cambio.
3. Ejecuta la suite completa de tests — cada PR debe mantener `pytest -q` en verde.
4. Si tu cambio toca `atome_llm/core/`, `c_engine/upstream/` o el formato de exportación, **confirma específicamente** que estos tests siguen pasando:
   - `tests/test_parity_with_c.py` — paridad forward-único Python ↔ C
   - `tests/test_parity_multitoken.py` — paridad multitoken Python ↔ C
   - `tests/test_export_format.py` — formato binario + generación de cabecera
5. Abre la PR. La CI reejecutará la suite en Python 3.10 / 3.11 / 3.12.

## Alcance de los cambios aceptables

Bienvenidos:

- Correcciones de bugs
- Nueva cobertura de tests (especialmente casos de fuzz sobre el parser C y entradas límite a `atome_predict_next` / `atome_generate`)
- Mejoras de rendimiento que preserven la paridad exacta al bit
- Correcciones y aclaraciones de documentación
- Nuevas placas objetivo MCU bajo `c_engine/targets/`, *siempre que no cambien el motor upstream*
- Nuevas referencias bajo `atome_llm/baselines/` para una comparación A/B honesta

Fuera de alcance, por favor no abras PR para esto:

- Añadir asignación de heap, memoria dinámica o dependencias de libc a `c_engine/upstream/`
- Añadir fallbacks «no debería pasar» a rutas de código deterministas
- Empaquetar nuevos tokenizadores (BPE / sentencepiece) — el tokenizador de bytes es una decisión de diseño portante para el presupuesto de flash de MCU
- Cambios que rompan la paridad Python ↔ C, aunque mejoren un benchmark
- Nuevas funciones que promuevan código de `c_engine/experiments/` a `c_engine/upstream/` sin cobertura completa de paridad + comprobación de límites

## Estándares de código

- Python: mantenlo simple, sin capas de ayuda, sin decoradores-por-estilo. Ajústate a la voz existente — funciones pequeñas, sin abstracción prematura, comentarios solo cuando el *porqué* no es obvio.
- C: solo C99, sin extensiones GNU, sin libc más allá de `<string.h>` / `<math.h>` / `<stdint.h>`. Búferes estáticos dimensionados por macros `ATOME_*` en tiempo de compilación. Comprueba los límites de todas las entradas de la API pública.

## Seguridad

Si encuentras un problema de seguridad (cualquier cosa que permita que un checkpoint o blob `.atome` malicioso comprometa un host que ejecuta el motor), por favor envía un correo a **hello@atomelm.com** en lugar de abrir una issue pública. Coordinaremos la divulgación.

## Licencia

Al enviar una contribución aceptas que se publique bajo la Licencia Apache 2.0 (la licencia del proyecto — véase `LICENSE`).
