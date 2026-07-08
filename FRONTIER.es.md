[English](FRONTIER.md) · [Français](FRONTIER.fr.md) · **Español** · [简体中文](FRONTIER.zh-CN.md) · [Deutsch](FRONTIER.de.md) · [日本語](FRONTIER.ja.md) <!-- i18n-switcher -->

# Atome LM — Hallazgos de frontera

> **Actualización 2026-05-11 — el A/B de escalado en 944K invierte el titular.**
> Misma receta, misma porción de validación, misma auditoría de equidad, una referencia
> GPT-FP32 vanilla de 944K params (950.608 params, +0,63 % vs los 944.640 de Atome) alcanza
> pérdida de validación 0,9337 / ppl 2,54, ganando al Atome ternario en 944K por un 11,4 %
> en pérdida y un 11,5 % en perplejidad. Las ganancias +22 % params-justo / +52 %
> flash-justo de más abajo se sostienen en el **régimen MCU de 60K params** y solo
> en ese régimen. Por encima de ~1M params, el sesgo inductivo del bloque
> de 3 vías deja de sustituir a la capacidad y empieza a restringirla.
> El encuadre honesto es: *la apuesta de Atome es el régimen de modelo-pequeño —
> sub-1M params, despliegue de clase MCU, sin red.* Véase
> [`HONEST_RESULTS.md`](HONEST_RESULTS.es.md) para la lectura completa del 944K.
> Multisemilla pendiente.

**Fecha.** 2026-05-09. Solo CPU, sin GPU.
**Hardware.** Máquina CPU de 4 hilos. PyTorch 2.x, ruta de referencia FP32.
**Corpus.** Porción de validación de TinyStories, 500 KB UTF-8 (~99,9 % ASCII).
División entrenamiento/eval 90/10 sobre fragmentos de 64 bytes → 7.030 fragmentos de entrenamiento /
782 fragmentos apartados (held-out).
**Optimizador.** AdamW, lr 3e-4, batch 16, seq 64, 3.000 pasos.
**Semilla única** (semilla 0). Los resultados no se han replicado en varias semillas.

Este documento informa el primer A/B manzanas-con-manzanas entre la arquitectura
ternaria de 3 vías de Atome y los Transformers decodificador-solo vanilla
(FP32) a igual número de parámetros y a igual presupuesto de flash. El par
publicado más cercano es el `Stories260K` de Andrej Karpathy — un transformer
simple FP32 de 260 K parámetros entrenado sobre TinyStories. La afirmación de frontera
de Atome es «menos flash, mejor calidad, menos bits por peso, *y*
desplegable en un microcontrolador de 2 $». Esta página prueba las tres primeras
de esas afirmaciones directamente; el despliegue MCU se verifica por separado vía
paridad exacta al bit Python ↔ C ↔ Cortex-M3 (QEMU) (véase `tests/test_qemu_parity.py`).

## En resumen (TL;DR)

| Modelo | Params | Bits/peso | Disco | bpb ↓ | Perplejidad ↓ |
|---|---:|---:|---:|---:|---:|
| **Atome 3 vías, ternario** | **60,800** | **1.58** | **15.1 KB**¹ / **17.2 KB**² | **2.66** | **6.31** |
| GPT vanilla, FP32 (params justo) | 60,808 | 32 | 237.5 KB | 3.02 | 8.12 |
| GPT vanilla, FP32 (flash justo) | 5,968 | 32 | 23.3 KB | 3.71 | 13.10 |

¹ ATOME01, 4 trits/byte (el motor C actual lee este formato).
² ATOME02, empaquetado base 3 a 5 trits/byte — 14,4 % más pequeño, cerca del
piso teórico de la información de `log2(3) ≈ 1,585` bits/trit. Codificador +
decodificador Python enviados hoy; el decodificador C es un cambio futuro.

## Qué demuestra esto

1. **A igual número de parámetros, la arquitectura ternaria de 3 vías
   gana a un transformer simple por un 22 % en perplejidad (6,31 vs 8,12)
   usando 16× menos disco.**

   La referencia vanilla *no* está sobreparametrizada — está emparejada a
   60,8 K params (`d_model=44, n_layers=3, n_heads=4, d_ff=44`,
   seleccionados por búsqueda exhaustiva para caer a menos de 8 params del
   objetivo). Es la misma arquitectura que usa todo artículo público de LM minúsculo
   (`Stories260K`, el artículo de TinyStories, BitNet a pequeña escala),
   salvo trivialidades.

2. **A igual presupuesto de flash, la arquitectura ternaria de 3 vías gana
   a un transformer simple por un 52 % en perplejidad (6,31 vs 13,10).**

   La referencia vanilla flash-justa es `d_model=8, n_layers=2,
   n_heads=4, d_ff=24`. Ocupa el mismo presupuesto de 20-25 KB en disco que
   el binario Atome ATOME01 (15,1 KB) y ATOME02 (17,2 KB).

3. **Los pesos de 1,58 bit cuestan ~22 % de perplejidad vs FP32 a los mismos
   parámetros de arquitectura** — pero la versión FP32 cuesta 16× más
   flash. En cualquier dispositivo donde el flash sea el cuello de botella (cada MCU que
   apuntamos), el ternario gana. En cualquier dispositivo donde el cómputo sea el
   cuello de botella y el flash sea gratis (CPU de servidor), FP32 gana en calidad.

4. **El empaquetado base 3 ATOME02 alcanza 1,6 bit/trit — a menos del 1 % del
   piso teórico de la información de 1,585 bit/trit** — y reduce el
   binario en disco de 20,1 KB a 17,2 KB en el mismo modelo entrenado de
   60,8 K params. Decodificador C aún pendiente.

## Qué NO demuestra esto

- **Solo semilla única.** Los tres números son de la semilla 0. No hemos ejecutado
  multisemilla para estimar la varianza. Las brechas del 22 % / 52 % son muy
  grandes comparadas con el ruido de semilla típico a esta escala, pero la varianza
  no está medida.
- **Corpus único.** TinyStories es un objetivo indulgente — historias cortas
  con vocabulario restringido. Corpus de dominio más amplio o de código podrían favorecer
  la atención vanilla. No lo hemos medido.
- **Horizonte de entrenamiento único.** 3.000 pasos está muy lejos de la
  convergencia. El ranking relativo podría invertirse o amplificarse con más
  entrenamiento. Una ejecución de 10 K pasos está en marcha; actualizaremos esta página si
  cambia el titular.
- **Sin silicio real.** Todas las afirmaciones MCU están verificadas en QEMU
  Cortex-M3, no en hardware físico RP2040 / STM32. Los tokens/seg y
  los julios/token en silicio real siguen pendientes.
- **Comparación directa con Stories260K aún pendiente.** La configuración exacta de Karpathy
  es `Stories260K` a 260 K params + un vocabulario SentencePiece de 32 K tokens. Nuestro
  tokenizador de bytes + config 60 K es ~4× más pequeño. Un verdadero
  manzanas-con-manzanas vs `Stories260K` necesitaría o bien (a) que escalemos
  a 260 K params y un tokenizador SentencePiece, o bien (b) la configuración de
  Karpathy reentrenada a 60 K params con un tokenizador de bytes. Ninguna está
  hecha.

## Comparación con la frontera publicada

| Sistema | Objetivo más pequeño | Params | Bits/peso | ¿MCU real? | ¿La arquitectura gana a vanilla? |
|---|---|---:|---:|---|---|
| Microsoft BitNet b1.58 | CPU de servidor | 700 M – 3 B | 1.58 | no | (empata a escala) |
| Meta MobileLLM | smartphone | 125 M – 1 B | 4–8 | no | sí (vs vanilla del mismo tamaño) |
| Karpathy `Stories260K` | portátil / navegador | 260 K | 32 | sin firmware | n/a (es la referencia vanilla) |
| llama.cpp en RP2040 (afición) | RP2040 + SD | ~1 B (con swap) | 4 | sí (lento, requiere SD) | no medido |
| TFLite Micro / Edge Impulse | Cortex-M0+ | – | 8 | sí | sin tareas de lenguaje |
| **Atome LM (este trabajo)** | **Cortex-M0+, 16 KB SRAM** | **60 K** | **1.58** | **QEMU sí, silicio pendiente** | **+22 % en params-justo, +52 % en flash-justo** |

Más pequeño, más eficiente en bits, *y* gana arquitectónicamente a vanilla en los
presupuestos que apuntamos. Que sepamos, el LM publicado más pequeño
donde la victoria de la arquitectura enrutada se ha medido directamente contra
una referencia vanilla al mismo presupuesto de flash.

## Reproducir

```bash
# from the repository root
PYTHONPATH=. python3 scripts/build_corpus.py --source tinystories \
    --max-bytes 500000 --output data/tinystories.txt

PYTHONPATH=. python3 scripts/run_ab_sweep.py \
    --train data/tinystories.txt --steps 3000 \
    --output ab_results.json
```

`ab_results.json` contendrá los mismos números que la tabla de arriba
(salvo redondeo dependiente de la plataforma en los kernels matmul de PyTorch).

## Preguntas abiertas / próximos empujes

- **A1.** Multisemilla (3 semillas × 3 configs) para estimar la varianza en las
  brechas del 22 % / 52 %.
- **A2.** Entrenar los tres a ≥ 10 K pasos. ¿Se cierra la brecha, se sostiene,
  o se ensancha?
- **A3.** Ablación: ¿cuál de las tres vías (conv local, SSM
  diagonal, atención dispersa top-k) carga con la mayor parte de la victoria de arquitectura?
  Quita cada una, mide.
- **A4.** Enviar un decodificador C para ATOME02. Recorta el binario de demo de
  20,1 KB a 17,2 KB sin cambios de código en otro sitio.
- **A5.** Silicio real. Flashear un RP2040 con el motor + este ckpt de 60,8 K.
  Medir tokens/seg, julios/token. **El número destacado que
  convierte la afirmación de «frontera» en un hecho.**
- **A6.** Destilación desde un fuerte LLM profesor (10 MB de texto de dominio
  estrecho curado, generado por un modelo de vanguardia) en el mismo Atome 60 K.
  Pregunta abierta: ¿se compone la ventaja de arquitectura bajo la
  destilación?
- **A7.** Corrección del Bug A (divergencia SSM con prompt corto entre `generate` de Python
  ↔ `atome_generate` de C). Toca el contrato de paridad exacta al bit
  — necesita aprobación explícita del usuario.

## Archivos de registro

- `ab_results.json` — números y config exactos de la ejecución reportada aquí.
- Los checkpoints A/B entrenados (`atome_60k_ternary`, `vanilla_60k_fp32`,
  `vanilla_6k_fp32`) *no* se envían — regénéralos con el arnés
  de abajo (este kit se entrena desde cero).
- `atome_llm/baselines/vanilla_transformer.py` — la referencia.
- `scripts/run_ab_sweep.py` — el arnés.
- `tests/test_vanilla_baseline.py` — 10 tests de cordura sobre la referencia.
- `tests/test_export_packed.py` — 5 tests sobre el ida-y-vuelta ATOME02.
- `tests/test_trit_packing.py` — 11 tests sobre el empaquetador base 3.
