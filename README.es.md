[English](README.md) · [Français](README.fr.md) · **Español** · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# Atome LM

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20518644.svg)](https://doi.org/10.5281/zenodo.20518644)
[![tests](https://github.com/TilelliLab/atome-lm/actions/workflows/test.yml/badge.svg)](https://github.com/TilelliLab/atome-lm/actions/workflows/test.yml)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Model-FFB020)](https://huggingface.co/TilelliLab/atome-lm)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

> Una implementación de referencia de un modelo de lenguaje minúsculo ternario con
> enrutamiento, con un motor de inferencia Python ↔ C99 exacto al bit, dimensionado
> para presupuestos de RAM de clase microcontrolador.

Modelo de lenguaje de 60 K parámetros por defecto, que combina tres ideas conocidas en un
único kit abierto: pesos ternarios (siguiendo [BitNet b1.58](https://arxiv.org/abs/2402.17764)),
un bloque híbrido SSM + atención dispersa + convolución local enrutado por token
(siguiendo [Hymba](https://arxiv.org/abs/2411.13676) y
[MossNet](https://arxiv.org/abs/2510.26182)),
y un tokenizador de bytes a escala ultra-reducida
(siguiendo [Guertler 2024](https://arxiv.org/abs/2405.14159)).
**La contribución es la integración, no la arquitectura**: una ruta completa de
entrenamiento → exportación ternaria → empaquetado en base 3 → inferencia C99, con paridad
Python ↔ C exacta al bit garantizada por los tests.

**Enlaces rápidos:**
- 📄 Descripción de la arquitectura: [`PAPER.md`](PAPER.es.md)
- 🔬 Resultados honestos, incluida la reversión en 944 K: [`HONEST_RESULTS.md`](HONEST_RESULTS.es.md)
- 🌐 Demo en vivo en el navegador (sin instalación): [atomelm.com/demo.html](https://atomelm.com/demo.html)
- 🏠 Página del proyecto: [atomelm.com](https://atomelm.com)

**Consigue el kit:** código de entrenamiento, motor C, benchmarks, artículo y pesos
entrenados: todo está en este repositorio, publicado bajo la
[Licencia Apache 2.0](LICENSE). Entrena tu propio checkpoint con
`scripts/train_demo.py` en ~30 min en una CPU, o ejecuta de inmediato el checkpoint
944 K incluido.

**Estado MCU:** la paridad QEMU ARM (Cortex-M3, MPS2-AN385) pasa hasta el epsilon FP32,
y una **demo reproducible en silicio real** ejecuta el checkpoint 944 K en un
**ESP32-WROOM-32** físico — texto coherente, totalmente sin conexión, ~1 tok/s — véase
[`hardware/esp32-wroom32/`](hardware/esp32-wroom32/) (binario precompilado + registro serie
+ flasheo con un solo comando). Esa demo es una simple prueba de ejecución; la **puesta en
producción** — el Atome Secure Boot Pack (blobs `.atome` firmados, flags dev/prod,
secure-boot por plataforma, atestación), el endurecimiento por plataforma — la vendemos
como integración en [atomelm.com](https://atomelm.com).

**Los pesos están incluidos** en `checkpoints/`:

- `atome_944k.bin` (271 KB) — el blob empaquetado del motor C (formato `ATOME01`),
  cargable directamente por el motor de inferencia.
- `atome_1m_v1.pt` (3,7 MB) — el checkpoint fuente de PyTorch que lo produjo;
  úsalo para afinar (fine-tune) o reexportar con otros `#define`.
- `vanilla_1m_v1.pt` (3,7 MB) — la referencia GPT vanilla FP32 usada para
  la reversión A/B en 944 K en [`HONEST_RESULTS.md`](HONEST_RESULTS.es.md);
  se incluye para que puedas reproducir la comparación de principio a fin.

El checkpoint 944 K es un artefacto de demostración para investigación, no un producto: es
estrecho, a veces incoherente, y entrenado sobre un único corpus. Está aquí
para hacer la arquitectura *ejecutable*, no para fijar un listón de calidad. Su reproducción
cuesta ~1-2 $ de CPU/GPU con el código de entrenamiento incluido; nada en este kit
constituye una barrera de reproducción.

---

## Resultado reproducible, régimen estrecho

En TinyStories, 3000 pasos, una sola semilla: a igual número de parámetros, el bloque
ternario-enrutado de Atome alcanza **6,31 ppl frente a 8,12** para una referencia GPT-FP32
vanilla (−22 %); a igual presupuesto de flash **6,31 frente a 13,10** (−52 %). La huella
en disco es 16× menor a igual número de parámetros (15,1 KB frente a 237,5 KB).

**El resultado se invierte en 944 K parámetros**, donde la referencia vanilla FP32 gana
por ~11 %. La apuesta de Atome es deliberadamente el régimen sub-1M, de clase MCU;
por encima, el techo de capacidad del ternario cierra la brecha y la supera. Reproducción
completa en [`FRONTIER.md`](FRONTIER.es.md), lectura honesta completa incluida la
reversión en [`HONEST_RESULTS.md`](HONEST_RESULTS.es.md).

## Por qué

Los LLM de centro de datos asumen la RAM de un centro de datos. Un microcontrolador de 2 $ pegado a una pared en un sensor remoto, un audífono, un juguete a pilas o un termostato no la tiene. Atome LM es el extremo de «diseño del modelo» de esa restricción:

- **Pesos ternarios** (`{-α, 0, +α}` por tensor, estilo BitNet b1.58). Ninguna multiplicación en coma flotante en el matmul durante la inferencia.
- **Bloque de 3 vías** (convolución local depthwise, SSM diagonal, atención dispersa top-k) mezcladas por un enrutador suave por token. Diseñado para coincidir exactamente con la estructura del motor C99 de Atome, de modo que los checkpoints entrenados se exportan a flash y se ejecutan con **paridad exacta al bit** entre Python y C.
- **Tokenizador de bytes.** Ninguna tabla BPE que enviar.
- **Entropía del enrutador como señal de calibración.** La entropía de la distribución del enrutador por token es observable gratis en cada posición. A la escala por defecto del motor Atome-LLM de 60 K parámetros sobre un único corpus estrecho, la señal está expuesta pero su calibración como estimador de incertidumbre a esa escala no se ha medido aquí. Hemos observado *preliminarmente* (en un modelo mayor de 3 M parámetros **que no forma parte de esta publicación**) que la entropía sigue las entradas fuera de dominio y correlaciona con la pérdida por token — se informa aquí como una observación aún no pública, con mediciones por venir en una publicación futura.

## Qué es y qué no es

- **Es:** el lado de entrenamiento en Python y la arquitectura de un LM ternario que corre en hardware de céntimos.
- **No es:** un chatbot de propósito general. Con la configuración por defecto del motor (`d_model=64`, `n_layers=4`) el modelo tiene unos 60 K parámetros y se exporta a unos 20 KB de flash. Entrénalo estrecho — un único dominio (preguntas y respuestas de sistemas embebidos, ayuda de línea de comandos, un único FAQ) — y habla con fluidez dentro de ese ámbito. Ampliarlo a este tamaño produce salida incoherente; eso es un reflejo de la capacidad, no de la arquitectura. Para más margen, aumenta `d_model` y `n_layers` (p. ej. `d_model=128, n_layers=6` ≈ 600 K parámetros, ~150 KB empaquetados) y reexporta con los `#define` correspondientes.

## Instalación

```bash
./install.sh          # CPU-only venv + dependencies + environment check
```

O manualmente: `pip install -e .` (Python ≥ 3.10, PyTorch ≥ 2.0). ¿Nuevo aquí?
[`QUICKSTART.md`](QUICKSTART.es.md) es la ruta de 60 segundos del clon a un modelo
listo para microcontrolador.

## Inicio rápido

```python
import torch
from atome_llm.core.atome_lm import AtomeLM

# Defaults match the Atome C99 engine's compile-time #defines:
#   d_model=64, n_layers=4, d_head=16, top_k=4, kernel=5, vocab=256.
model = AtomeLM()
print(f"params: {model.parameter_count():,}")

ids = torch.randint(0, 256, (1, 32))
logits = model(ids)                     # (1, 32, 256)
loss = model.loss(ids[:, :-1], ids[:, 1:])

# Per-layer per-token uncertainty signal — no extra training:
ent_per_layer = model.router_entropies(ids)   # list of (B, L) tensors
```

## Entrenar una demo minúscula

```bash
python scripts/train_demo.py --data path/to/text.txt --steps 1000 \
    --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt
```

Un `build_corpus.py` integrado descarga unas cuantas fuentes con licencia permisiva
(`tinystories`, `esp-idf`, `mcu-wikipedia`) para un entrenamiento rápido de prueba:

```bash
python scripts/build_corpus.py --source tinystories --max-bytes 500000 \
    --output data/tinystories.txt
```

## Probar un checkpoint

```bash
python scripts/demo.py --checkpoint checkpoints/atome_demo.pt
# or, with no checkpoint, sanity-check the plumbing:
python scripts/demo.py --random --temperature 0.8 --top-p 0.9
```

El REPL imprime la continuación y las barras de entropía del enrutador por capa sobre
el prompt — la señal de metacognición expuesta gratis.

## Muestreo

`AtomeLM.generate(...)` usa por defecto el argmax voraz (que coincide con
`atome_predict_next` del motor C). Los argumentos opcionales `temperature`, `top_p`, `top_k`
y `generator=` habilitan el muestreo nucleus / top-k con reproducibilidad por semilla.

## Benchmark

```bash
python scripts/benchmark.py            # tiny / default / large
```

Latencia CPU de forward + generate en tres configuraciones representativas. Útil como
comprobación de regresión tras cambios de arquitectura; no es un número MCU.

## Exportar a un microcontrolador

```bash
python scripts/export_to_atome.py \
    --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome \
    --header
```

Esto produce un binario plano `.atome` que puedes `#include` desde C y cargar con
`atome_load(...)` del [motor C99 de Atome](c_engine/). Con la configuración por defecto, el
binario está muy por debajo de 100 KB — cabe cómodamente en ESP32-S3, STM32F4, RP2040,
nRF52840, ESP32-C3.

## Arquitectura

```
x → LayerNorm → ┬─→ Local  (depthwise causal conv k=5)        ─→┐
                ├─→ State  (diagonal SSM, O(L))                 ─→ Σ → +x
                └─→ Sparse (top-k attention, O(L·k))            ─→┘
                        ↑              ↑
                        │              router weights r ∈ Δ per token
                        └──────────────┘
```

Tres vías. Tres sesgos inductivos distintos. Un enrutador compartido por token que aprende
qué vía es la más apropiada para cada posición. La entropía por token del enrutador se expone
como una señal de incertidumbre gratuita en cada posición y en cada capa.

La historia completa de la arquitectura está en [`PAPER.md`](PAPER.es.md).

## Tests

```bash
pytest -q
```

## Licencia

Licencia Apache 2.0 — véase [`LICENSE`](LICENSE) y [`NOTICE`](NOTICE).

El kit es totalmente abierto: úsalo, modifícalo, redistribúyelo y envíalo en productos
comerciales sin tarifas por puesto ni por dispositivo. La concesión de patentes de Apache 2.0
cubre la arquitectura ternaria-enrutada de 3 vías tal como se publica aquí.

Los checkpoints publicados en `checkpoints/` (atome_944k.bin, atome_1m_v1.pt,
vanilla_1m_v1.pt) también son Apache-2.0. Son artefactos de referencia / investigación,
no productos. La integración comercial — puesta en marcha de silicio, el Atome Secure Boot
Pack (blobs `.atome` firmados, flags dev/prod, secure-boot por plataforma, atestación), el
endurecimiento por plataforma, el afinado en dominios personalizados del mayor modelo interno
V2 — está disponible en [atomelm.com](https://atomelm.com).

## Cita

```bibtex
@software{atome_llm_2026,
  title  = {Atome LM: a tiny ternary language model for microcontroller deployment},
  author = {Atome LM contributors},
  year   = {2026},
  note   = {Apache 2.0, https://atomelm.com},
}
```
