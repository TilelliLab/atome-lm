[English](Q15_PROPOSAL.md) · [Français](Q15_PROPOSAL.fr.md) · **Español** · [简体中文](Q15_PROPOSAL.zh-CN.md) · [Deutsch](Q15_PROPOSAL.de.md) · [日本語](Q15_PROPOSAL.ja.md) <!-- i18n-switcher -->

# Ruta de activaciones Q15 — propuesta de diseño (NO implementada)

## Por qué existe

En la sesión de emulador del 10 de mayo sospechamos al principio que el orden de las
operaciones en coma flotante entre el softfloat de ARM y el x86 del host causaba la deriva
multitoken. Al examinarlo, la causa real era un bug lógico — `atome_predict_next`
nunca reiniciaba `state->ssm_h`, de modo que el estado SSM de una llamada previa
contaminaba las pasadas forward posteriores. Ese bug ya está corregido (`atome.c:294-300`)
y 48/48 tokens de QEMU coinciden con Python.

Pero Q15 sigue mereciendo la pena por **rendimiento y energía**, no por
corrección. Este archivo congela el diseño para que la próxima sesión pueda
retomarlo en frío.

## Qué aporta Q15 (mejores estimaciones, aún no medidas)

| Ganancia | Magnitud | Por qué |
|---|---|---|
| Aceleración de cómputo en M0 / M3 | ~5-10× | Sin FPU; el multiplica-acumula entero es un único ciclo en ARM v7-M |
| Aceleración de cómputo en M4F / M7 | ~1.5-2× | Ya tiene FPU; la ganancia viene del SIMD (`__SADD16`, `SMLAD`) |
| Reducción de BSS | ~40-50% | Los tensores de activación se reducen a la mitad (fp32 → int16) |
| Potencia por token | ~3-5× menor | Escala con los ciclos |
| Determinismo entre hosts | completo | La aritmética entera elimina la ambigüedad del orden de redondeo |

## Qué NO aporta Q15

- Un blob `.atome` más pequeño — los pesos ya son ternarios (~0,5 bit cada uno).
  Las activaciones viven en RAM, no en flash.
- Mejor calidad de modelo — la cuantización en la inferencia tiene pérdidas; espera
  que la perplejidad suba ligeramente (probablemente <5 % si se calibra; necesita medición).

## Diseño

### Interruptor en tiempo de compilación

Añadir `ATOME_DTYPE` que seleccione `f32` (hoy, por defecto) o `q15` (nuevo).
Los tests / firmware existentes quedan sin cambios cuando el flag está ausente.

```c
#ifndef ATOME_DTYPE_Q15
#define ATOME_DTYPE_Q15 0
#endif

#if ATOME_DTYPE_Q15
typedef int16_t  atome_act_t;
typedef int32_t  atome_acc_t;
#else
typedef float    atome_act_t;
typedef float    atome_acc_t;
#endif
```

### Qué sigue en coma flotante

- LayerNorm (sqrt + división — existe un Q15-LayerNorm pero añade 200 LOC)
- Softmax (exp — lo mismo)
- La única escala de atención `1.0 / sqrtf(d_h)`
- Los logits finales (para que el argmax sea inequívoco)

Estos son <2 % de los ciclos. Convertir hacia/desde Q15 en la frontera.

### Qué pasa a ser Q15

- Todos los matvecs ternarios (`atome_ternary_matvec`)
- La conv causal (`atome_causal_conv`)
- El forward del SSM (con cuidado — `tanh(a)` y `b * x` necesitan manejo en punto fijo)
- El producto escalar de atención (Q.K)
- La suma ponderada de atención (sum_i p_i * V_i)

### Seguimiento de la escala por tensor

Cada tensor Q15 lleva un desplazamiento implícito. Mantén un pequeño
`atome_q15_state_t` por paso con las escalas actuales y actualízalo al vuelo:

```c
typedef struct {
    int x_shift;        /* current activation shift (Q15-pos) */
    int normed_shift;
    int path_local_shift;
    int path_ssm_shift;
    int path_attn_shift;
} atome_q15_state_t;
```

Script de calibración (lado Python): pasa unos miles de prompts por el
modelo flotante, registra la activación absoluta máxima por capa, ajusta el desplazamiento
para que el percentil 99,9 quepa en [-32768, 32767].

### Plan de pruebas

1. Nuevo `tests/test_q15_parity.py`: referencia flotante vs forward Q15.
   Tolerancia: el logit top-1 debe coincidir para >95 % de los prompts a d=64,
   similitud coseno por token >0,98.
2. Nuevo objetivo `c_engine/targets/cortex-m3-q15/`. El firmware reporta
   los ciclos por token; espera 5-10× más rápido que `cortex-m3-gen` con
   config idéntica.
3. Añadir una fila `q15` a `RAM_TABLE.md`. Esperado: la config tinystories baja
   de 104 KB de pico → ~55 KB de pico. La F103 Blue Pill (2-4 $) pasa a ser
   alcanzable para el modelo entrenado.

## Esfuerzo estimado

| Fase | Esfuerzo | Riesgo |
|---|---|---|
| Calibración (Python) + exportación de escalas | medio día | bajo |
| Ruta Q15 de `atome.c` (esqueleto + matvec + conv) | 1 día | bajo |
| SSM Q15 (tabla tanh + multiplica-suma escalado) | medio día | medio — cuidado numérico |
| Atención Q15 (Q·K, escalado de la entrada del softmax) | medio día | medio |
| Tests + objetivo de firmware | medio día | bajo |
| Ajuste de calibración + benchmarks | medio día | bajo |
| **Total** | **~3-4 días** | — |

## Cuándo retomarlo

Después de:
1. Que llegue el checkpoint de 1M params (`TRAIN_1M_RUNBOOK.md`) y tengamos un
   modelo real que merezca optimizarse en velocidad/potencia.
2. Que la validación en silicio real en Nucleo-F411RE confirme que los números de QEMU
   de hoy son predictivos.
3. Que un usuario quiera ejecutar Atome en F103 Blue Pill (2-4 $) — el escalón
   más barato actualmente bloqueado por la RAM en la config del modelo entrenado.

Es un trabajo limpio, acotado y autocontenido. Retómalo cuando
se dé una de las condiciones de arriba.
