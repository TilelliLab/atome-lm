[English](PROJECT_CONTENT.md) · [Français](PROJECT_CONTENT.fr.md) · **Español** · [简体中文](PROJECT_CONTENT.zh-CN.md) · [Deutsch](PROJECT_CONTENT.de.md) · [日本語](PROJECT_CONTENT.ja.md) <!-- i18n-switcher -->

# PROJECT_CONTENT.md — Orientación del proyecto

Léelo primero. Una orientación de ~5 minutos para cualquiera (humano o agente) que llegue a la base de código. Te evita romper los invariantes portantes a los que este kit da importancia.

---

## En resumen (TL;DR)

**Atome LM** es un modelo de lenguaje ternario de ~60 K parámetros + un motor de inferencia C99 que lo ejecuta en microcontroladores bare-metal (RP2040, ESP32-C3, Cortex-M0). La pila de entrenamiento en Python y el motor C están diseñados para producir pasadas forward **idénticas al bit** — esa paridad es todo el sentido del proyecto.

- Licencia: Apache 2.0
- Tests: `pytest -q` → espera **146 passed, 0 skipped** (1 skip si falta `qemu-system-arm`)
- Se envían tres checkpoints entrenados en `checkpoints/`: `atome_944k.bin` (blob empaquetado del motor C de 271 KB — el modelo de demo de 944K parámetros en formato `ATOME01`), `atome_1m_v1.pt` (la fuente PyTorch que lo produjo) y `vanilla_1m_v1.pt` (la referencia GPT vanilla FP32 usada para el A/B de HONEST_RESULTS). Cualquier *otro* archivo que coincida con `*.pt`/`*.atome*`/`*.bin` está ignorado por git. Para entrenar desde cero en su lugar, usa `scripts/train_demo.py` (~30 min CPU).

## Por qué existe

La mayoría de los «LM minúsculos» son LM grandes que han sido comprimidos. Atome está moldeado desde el principio por las restricciones de MCU: la RAM es el coste vinculante, los pesos ternarios eliminan las multiplicaciones en coma flotante, tres vías (conv local + SSM diagonal + atención dispersa top-k) reemplazan una pila transformer profunda, un enrutador suave por token las mezcla, y el tokenizador de bytes evita enviar un vocabulario. La afirmación interesante no son las primitivas (todo estado del arte — BitNet, Mamba, atención top-k) — es la *combinación, la historia de despliegue y la evaluación honesta* que muestra dónde esto gana (60K) y dónde pierde (944K). El motor C es sin heap (zero-heap), con búferes estáticos, huella de memoria determinista.

## Lo que un agente NO DEBE romper

Son invariantes portantes. Verifica cualquier cambio contra ellos antes de declarar hecho.

1. **Paridad exacta al bit Python ↔ C.** La paridad de forward único es todo el producto. Tests: `tests/test_parity_with_c.py`, `tests/test_parity_multitoken.py`. Si cambias el código del modelo, el formato de exportación o los kernels C, ejecútalos y confirma que siguen pasando.
2. **Cero asignación de heap en el motor C.** `c_engine/upstream/atome.c` usa solo búferes estáticos dimensionados por macros `ATOME_*` en tiempo de compilación. Nunca introduzcas `malloc`/`calloc`/`free` aquí. Los arrays en pila están bien.
3. **`weights_only=True` en cada `torch.load`.** Todos los checkpoints del kit son `{"config": dict, "state_dict": dict}` — tensores puros + primitivas. Cargar con `weights_only=False` es RCE en un archivo .pt malicioso. No regreses en esto.
4. **Ninguna constante de modelo hardcodeada en el exportador.** `scripts/export_to_atome.py` lee `top_k` (y toda la config) desde el checkpoint y escribe el valor real en la cabecera C. No hardcodees constantes — hay un test de regresión en `tests/test_export_format.py` que lo detectará.
5. **Comprobaciones de límites en `atome_predict_next` y `atome_generate`.** Ambos rechazan `n_tokens < 1`, `prompt_len < 1` y punteros NULL antes de cualquier indexación/memcpy. No los quites — `state->x[n_tokens - 1]` es comportamiento indefinido (UB) sin ellos.
6. **Solo se envían los tres checkpoints publicados.** `checkpoints/atome_944k.bin`, `checkpoints/atome_1m_v1.pt` y `checkpoints/vanilla_1m_v1.pt` están rastreados y en lista blanca en `.gitignore`. Cualquier *nuevo* artefacto `*.pt`/`*.atome*`/`*.bin` está ignorado por git por defecto — no añadas más checkpoints a la publicación pública sin una entrada explícita en la lista blanca y una razón.
7. **Honestidad en los benchmarks.** `HONEST_RESULTS.md` documenta *tanto* las victorias (~22 % mejor perplejidad que vanilla FP32 en 60K params, 52 % mejor a igual presupuesto de flash) *como* las derrotas (vanilla gana por ~11 % a escala 944K). No dejes caer silenciosamente las derrotas para que los titulares suenen mejor.

## Mapa de archivos

```
atome-llm-kit/
├── README.md              ← user-facing intro
├── PAPER.md               ← architecture writeup
├── HONEST_RESULTS.md      ← what works, what doesn't, costs
├── FRONTIER.md            ← what's still being explored
├── QUICKSTART.md          ← 30-min train + export walkthrough
├── REPRODUCE.md           ← how to reproduce the headline benchmarks
├── LICENSE / NOTICE       ← Apache 2.0 + attribution
│
├── atome_llm/             ← Python package
│   ├── core/
│   │   ├── atome_lm.py       — main model
│   │   ├── mcu_block.py      — 3-pathway block
│   │   ├── router.py         — per-token soft router
│   │   ├── ssm.py            — diagonal SSM
│   │   ├── sparse_attention.py — top-k attention
│   │   └── ternary*.py       — ternary weight modules
│   ├── tokenize.py         — byte tokenizer (no BPE)
│   └── baselines/          — vanilla FP32 transformer for A/B
│
├── c_engine/upstream/     ← The C99 inference engine
│   ├── atome.c               — implementation (~600 lines, zero heap)
│   └── atome.h               — public API + compile-time macros
│
├── scripts/
│   ├── train_demo.py         — quick training (~30 min CPU)
│   ├── export_to_atome.py    — checkpoint → .atome binary + C header
│   ├── demo.py               — interactive REPL
│   ├── evaluate.py           — bits-per-byte eval
│   └── run_ab_sweep.py       — 60K param-fair / flash-fair A/B
│
└── tests/                 ← 146 tests, all expected to pass
    ├── test_parity_with_c.py        — single-forward Python ↔ C
    ├── test_parity_multitoken.py    — multi-token Python ↔ C
    ├── test_qemu_parity.py          — host C ↔ QEMU ARM (skips if QEMU missing)
    ├── test_export_format.py        — binary format + header generation
    └── test_*.py                    — model shape, router, SSM, ternary, etc.
```

## Verifica tu trabajo

```bash
# from repo root, after install.sh has run once
. .venv/bin/activate
pytest -q       # expect: 146 passed (or 145 + 1 skipped if no qemu-system-arm)
```

Esa es la única señal que importa antes de declarar hecho. Si cambias algo en `atome_llm/core/` o `c_engine/upstream/`, no te saltes este paso.

## Formas frecuentes en que los agentes se equivocan aquí

- **Tratar el motor C como código de relleno.** No lo es — cada línea está dimensionada por la RAM/flash. No añadas asignaciones, no añadas dependencias de libc, no añadas `printf`. Todo el sentido es que esto corra en un chip de 2 $ con kilobytes de RAM.
- **Intentar «mejorar» los conteos de parámetros o los números de benchmark en los docs sin reejecutar el barrido.** Los números 60K / 944K / 22 % / 52 % / -11 % en `HONEST_RESULTS.md` están ligados a ejecuciones reproducibles concretas. Si no puedes reproducir, no edites.
- **Añadir fallbacks estilo ML («if state is None, do X»).** El runtime es determinista — cada ruta de código se ejercita. No hay ramas «no debería pasar».
- **Generalizar el tokenizador de bytes.** Son bytes crudos intencionadamente. Añadir BPE o sentencepiece enviaría una tabla de vocabulario (kilobytes de flash) y frustraría el diseño.
- **Empaquetar ideas experimentales.** `c_engine/experiments/delta_inference/` es explícitamente experimental — no está en la ruta soportada, no está probado para paridad. No promuevas experimentos a `c_engine/upstream/` sin cobertura de paridad + comprobación de límites.
- **Tocar los tests de paridad «para hacerlos pasar».** Si los tests de paridad fallan, el que está mal es el *código*, no el test. Encuentra la divergencia Python/C — casi siempre es un desfase de uno en la orientación del kernel de conv, la inicialización del estado SSM, o una constante obsoleta hardcodeada.

## Qué está abierto vs qué no

| Abierto (este repo, Apache 2.0)                     | No abierto (comercial)                        |
|-----------------------------------------------------|-----------------------------------------------|
| Arquitectura, código de entrenamiento, motor C      | Puesta en marcha de silicio (integración por plataforma) |
| Pesos entrenados 944K (`checkpoints/atome_944k.bin`)| Atome Secure Boot Pack (blobs `.atome` firmados) |
| Fuente PyTorch `atome_1m_v1.pt` + referencia vanilla| Endurecimiento por plataforma + flujos de atestación |
| Formato de exportación + tests de paridad           | Mayor modelo interno V2 (3M params, multidominio) |
| Datos de ejemplo, arnés de barrido A/B              | Afinado personalizado + integración por cliente |
| Toda la doc (PAPER, HONEST_RESULTS, etc.)           | Marketing / sitio de demo en vivo en atomelm.com |

La arquitectura es pública por diseño y el coste de entrenamiento es de ~1-2 $ — una estrategia de licencia-como-foso nunca iba a funcionar, y pesos-como-foso habría sido fino. El verdadero valor defendible es el trabajo de integración por despliegue, el endurecimiento de seguridad y el mayor modelo V2 mantenido propietario — nada de lo cual está en este repo.

## Si necesitas profundizar más

- Justificación de la arquitectura: `PAPER.md`
- Qué se mide, qué no, qué costó qué: `HONEST_RESULTS.md`
- Qué se sigue explorando: `FRONTIER.md`
- Cómo reproducir los números destacados: `REPRODUCE.md`
- Cómo pasar de cero a un modelo entrenado-y-exportado: `QUICKSTART.md`
