[English](HONEST_RESULTS.md) · [Français](HONEST_RESULTS.fr.md) · **Español** · [简体中文](HONEST_RESULTS.zh-CN.md) · [Deutsch](HONEST_RESULTS.de.md) · [日本語](HONEST_RESULTS.ja.md) <!-- i18n-switcher -->

# Atome LM — Dosier de resultados honestos

> Una página, sin marketing. Qué medimos, en qué hardware, con qué
> semilla. Dónde ganamos a vanilla, dónde no, dónde aún no lo sabemos.

**Última actualización.** 2026-05-13. Compilado desde `checkpoints/*.train.json`
y `ab_results.json` (que son los artefactos reales de las ejecuciones — ábrelos).

---

## Tabla 1 — Los números, tal como se midieron

| Config | Params | Bits/peso | Pérdida ↓ | PPL ↓ | Disco | Estado |
|---|---:|---:|---:|---:|---:|---|
| **Régimen 60K (objetivo MCU)** | | | | | | |
| Atome ternario 3 vías | 60,800 | 1.58 | 1.84 | 6.31 | 15.1 KB¹ | ✅ medido |
| GPT vanilla FP32 (params justo) | 60,808 | 32 | 2.09 | 8.12 | 237.5 KB | ✅ medido |
| GPT vanilla FP32 (flash justo) | 5,968 | 32 | 2.57 | 13.10 | 23.3 KB | ✅ medido |
| **Régimen 944K (escalado A/B)** | | | | | | |
| Atome ternario 3 vías | 944,640 | 1.58 | **1.0545** | 2.87 | 184 KB¹ | ✅ medido |
| GPT vanilla FP32 (params justo) | 950,608 | 32 | **0.9337** | 2.54 | 3.7 MB | ✅ medido |
| Atome 3 vías, power3 (por tensor) | 944,640 | 2.81 | TBD | TBD | ~325 KB est | ⏳ lanzador listo |
| Atome 3 vías, power3 (α por fila) | 944,640 | 2.81² | TBD | TBD | ~330 KB est | ⏳ lanzador listo |

¹ ATOME01, empaquetado 4 trits/byte.  
² La porción por tensor es de 2,81 bits/peso; la α por fila añade un FP16 por fila
de salida (sobrecarga % despreciable en 944K).

**Titulares, sin edulcorar:**

- En el objetivo MCU de 60K, la arquitectura ternaria de 3 vías gana a vanilla
  FP32 por un **22 % en perplejidad a igual número de parámetros** y por un **52 % a
  igual presupuesto de flash**.
- En 944K, el ternario simple **pierde frente a vanilla FP32 por un 11,4 % en pérdida de
  validación / 11,5 % en perplejidad**. Misma receta, misma porción de validación, misma semilla.
- La reversión en 944K es el hallazgo honesto más importante de este kit.
  Dice: el sesgo inductivo de 3 vías sustituye a la capacidad a
  escala pequeña y la restringe a escala mayor. La apuesta de Atome es el
  régimen de modelo-pequeño / MCU — no «el ternario minúsculo gana a todos».

## Tabla 2 — De qué está condicionado el resultado 944K

| Variable | Valor |
|---|---|
| Corpus | TinyStories completo (`train.txt + valid.txt` concatenados, ~1,7 GB en bruto) |
| Pasos | 30,000 |
| Longitud de secuencia | 256 |
| Batch × acum | 64 × 4 |
| Optimizador | AdamW, lr=3e-4 → 3e-5 coseno, warmup=1000, weight_decay=0.1 |
| Precisión | BF16 autocast |
| Semilla | 0 (semilla única; multisemilla pendiente) |
| Hardware | RunPod A100/A6000 (atome) — vast A100 (vanilla, 2026-05-11) |

## Tabla 3 — Lo que NO hemos medido

| Pregunta | Por qué importa | Coste de resolver |
|---|---|---|
| Varianza multisemilla en 944K | Una sola semilla no es un hallazgo | ~2 $ vast (3 semillas × atome + vanilla) |
| Punto de cruce | ¿Dónde exactamente empieza a perder el de 3 vías? | ~8 $ vast (barrido 100K / 300K / 600K / 1.5M) |
| Power-of-3 cierra la brecha en 944K | Si sí: el titular de reversión de pérdida se voltea | ~6 $ vast (el lanzador de este kit) |
| RAM de inferencia en punto fijo Q15 | El objetivo de RAM del RP2040 se falló en 944K (pico 411 KB) | ~3 días de ingeniería |
| Rendimiento en silicio real | Todas las afirmaciones MCU son de QEMU; convierte «frontera» en «hecho» | 0 $ (RP2040 en el escritorio) + ~1 día |
| Destilación desde un profesor vanilla | Los alumnos ternarios a menudo cierran el 80 %+ de la brecha con el profesor flotante | ~1-2 $ vast |
| Corpus de dominio más amplio | TinyStories favorece los modelos de patrón local | ~4 $ vast |

## Tabla 4 — Qué es sólido vs qué es portante-pero-fino

**Sólido (no cambiar sin razón fuerte):**

- 146/146 tests en verde en HEAD (16 de ellos específicos de power3).
- Paridad exacta al bit Python ↔ C ↔ Cortex-M3 (QEMU) para un solo forward
  (`tests/test_parity_with_c.py`, `tests/c_parity/parity_main.c`).
- Artefactos atome_1m_v1.pt + vanilla_1m_v1.pt entrenados en disco, ambos
  con registros de entrenamiento completos en `checkpoints/*.train.json` (ábrelos — la pérdida
  de cada paso está registrada).
- A/B 60K params-justo / flash-justo reproducible en ~30 min de CPU
  (`scripts/run_ab_sweep.py`).

**Portante pero fino:**

- Todos los números destacados son de semilla única.
- La generación C multitoken tenía antes un bug de divergencia del estado
  SSM (Bug A). Corregido tanto en Python como en el motor C: `atome_predict_next`
  reinicia el estado oculto del SSM y lo rederiva desde el prefijo completo de tokens
  en cada llamada (`c_engine/upstream/atome.c`). La paridad Python↔C multitoken
  está cubierta por `tests/test_parity_multitoken.py`; la paridad de forward único
  sigue siendo exacta al bit vía `tests/test_parity_with_c.py`.
- La demo RP2040 supera actualmente los 264 KB de SRAM en 944K — la afirmación MCU
  depende del régimen, y el lanzador de este kit está probando si
  power3 estrecha el presupuesto de parámetros lo suficiente para traer 944K de vuelta al alcance
  (no lo hace por sí solo; necesita Q15 o un estado oculto más pequeño).

## Tabla 5 — Coste de cada medición hecha hasta la fecha

| Trabajo | Fecha | Coste | Resultado en disco |
|---|---|---:|---|
| Barrido A/B 60K | 2026-05-09 | 0 $ (CPU) | `ab_results.json` |
| Atome 944K | 2026-05-10 | ~0,40 $ (RunPod A40) | `atome_1m_v1.pt` |
| Vanilla 944K | 2026-05-11 | ~0,55 $ (Vast A100) | `vanilla_1m_v1.pt` |
| Cableado Power-3 + tests + prueba CPU | 2026-05-12/13 | 0 $ (CPU) | `atome_llm/core/power3.py` + 6 nuevos tests |
| **Total gastado hasta ahora** | | **< 1,00 $** | — |
| Pendiente: A/B 944K con power3 + power3_pr | — | ~3,60-6,40 $ tope 8 $ | lanzador en `scripts/` |

## Archivos de registro

Los checkpoints 944K entrenados y sus registros de entrenamiento se envían con el kit, de modo que
cada número reportado es auditable paso a paso *y* reevaluable directamente:

- `checkpoints/atome_944k.bin` — blob empaquetado del motor C (formato ATOME01).
- `checkpoints/atome_1m_v1.pt` — fuente PyTorch del Atome 944K.
- `checkpoints/vanilla_1m_v1.pt` — referencia vanilla FP32 944K (para la
  reversión A/B de arriba).
- `checkpoints/atome_1m_v1.train.json` — registro de entrenamiento cada 1000 pasos.
- `checkpoints/vanilla_1m_v1.train.json` — lo mismo para la referencia vanilla.
- `ab_results.json` — fila de resultado A/B 60K exacta.
- `FRONTIER.md` — descripción de la frontera con divulgación completa del 944K.
- `PAPER.md` — descripción de la arquitectura.
- `tests/` — 146 tests en verde.

El barrido 60K en sí (`checkpoints/ab_sweep/`) **no** se envía — fueron
24 ejecuciones de entrenamiento desechables. Reproducir el barrido lleva ~20 minutos
de CPU con los `scripts/` incluidos.
