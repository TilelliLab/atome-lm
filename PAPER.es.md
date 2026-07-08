[English](PAPER.md) · [Français](PAPER.fr.md) · **Español** · [简体中文](PAPER.zh-CN.md) · [Deutsch](PAPER.de.md) · [日本語](PAPER.ja.md) <!-- i18n-switcher -->

# Atome LM — arquitectura para modelos de lenguaje ternarios nativos de microcontrolador

## 1. Motivación

Los modelos de lenguaje más pequeños que «hablan de verdad» se sitúan hoy en el rango de 100 M a 1 B de parámetros. Cada uno de esos modelos exige más RAM y más ancho de banda de memoria de los que un microcontrolador de 2 $ puede ofrecer. Las decisiones de arquitectura de esos modelos — atención completa, FFN densas, MoE multibanco, vías aumentadas por recuperación (retrieval) — son decisiones tomadas bajo la suposición de que la RAM es barata. Atome LM parte de la suposición opuesta: la RAM es la restricción que domina cualquier otra consideración.

El resultado es una arquitectura deliberadamente estrecha, diseñada de principio a fin para ser compatible con un motor de inferencia C99 de forma fija que corre en chips con kilobytes — no megabytes — de RAM de trabajo.

## 2. Restricciones del motor

La estructura `atome_block_t` del motor C99 de Atome está fijada así:

```
norm        : LayerNorm
local_conv  : depthwise causal conv, ternary kernel
ssm         : diagonal SSM (per-channel a, b, c_out, FP32)
attn        : top-k causal attention, ternary Q/K/V
router      : ternary linear → softmax over 3 pathways
```

Existen búferes estáticos para cada una de esas tres salidas de vía, así como para el estado oculto del SSM y la caché KV de la atención. No hay búfer para una convolución ancha, no hay búfer para una FFN densa, ninguna previsión para pesos multibanco, ninguna escala por fila en el kernel ternario. Intentar entrenar una arquitectura más ancha y «encajarla luego» requeriría o bien regenerar la estructura C (rompiendo el contrato de paridad exacta al bit sobre el que se sustenta este proyecto), o bien enviar vías no soportadas que serían silenciosamente descartadas en la inferencia.

Por eso Atome LM coincide exactamente con el motor: tres vías, escala por tensor, tokenizador de bytes, sin embedding posicional, longitud de secuencia limitada por `ATOME_MAX_SEQ` en tiempo de compilación.

## 3. El bloque

```
x → LayerNorm → ┬─→ Local   (depthwise causal conv, k=5)        ─→┐
                ├─→ State   (diagonal SSM, O(L))                  ─→ Σ → +x
                └─→ Sparse  (top-k attention, O(L·k))             ─→┘
                        ↑              ↑
                        │              router weights r ∈ Δ per token
                        └──────────────┘
```

Tres operaciones estructuralmente distintas:

| # | Nombre | Operación               | Función                       |
|---|--------|-------------------------|------------------------------|
| 1 | Local  | Conv depthwise k=5      | Bigramas, fronteras de palabra |
| 2 | State  | SSM diagonal            | Acarreo de tema de largo alcance |
| 3 | Sparse | Atención top-k          | Correferencia, recuerdo exacto |

El enrutador es un `TernaryLinear(d_model, 3)` seguido de softmax. Produce una distribución de 3 vías por token; la salida del bloque es el residuo más la combinación convexa de las salidas de vía bajo esa distribución.

### 3.1 La entropía del enrutador como señal de calibración

La distribución del enrutador por token porta una señal de incertidumbre:

```
H(r_t) = − Σ_i r_t,i · log r_t,i,    bounded in [0, log 3] for 3 pathways
```

Una entropía alta significa que el enrutador no pudo decidir qué primitiva de cómputo era la más apropiada para la posición. La señal es estructural — no requiere ningún entrenamiento específico de incertidumbre ni parámetros adicionales. A la escala por defecto del motor Atome-LLM (60 K parámetros, corpus único y estrecho) la señal está expuesta pero su calibración como estimador de incertidumbre a esta escala no se evalúa aquí. En un modelo mayor de 3 M parámetros **no incluido en esta publicación**, hemos observado *preliminarmente* que la entropía del enrutador sigue las entradas fuera de dominio y correlaciona con la pérdida por token; lo informamos solo como una **observación aún no reproducible**, y tenemos la intención de publicar las mediciones de respaldo en una versión futura. Medirla (p. ej. el error de calibración esperado entre la entropía del enrutador y la pérdida por token) es un ejercicio aparte.

`MCUBlock.router_entropy(x)` devuelve la entropía por token en nats. `AtomeLM.router_entropies(ids)` devuelve la entropía por capa y por token como una lista de tensores `(B, L)`. La estructura `atome_state_t` del motor C expone el array de pesos del enrutador por token `router_w[ATOME_MAX_SEQ][ATOME_N_PATHWAYS]` — la entropía es una suma/log sobre él.

## 4. Presupuesto de tamaño y forma

Con los `#define` por defecto del motor (`d_model=64`, `n_layers=4`, `d_head=16`, `vocab=256`, `kernel=5`):

- Embedding: 256 × 64 = 16.384 trits
- Por bloque: norm (256 FP32) + conv (64 × 5 trits) + SSM (3 × 64 FP32) + Wq/Wk/Wv (16 × 64 + 16 × 64 + 64 × 64 trits) + enrutador (3 × 64 trits)
- Norm final: 128 FP32
- Des-embedding (unembed): 64 × 256 trits

Empaquetado a 2 bits por trit, el binario es del orden de 30-60 KB según la configuración. Cómodamente por debajo de 100 KB para los valores por defecto típicos, muy por debajo del 1 MB de flash de un STM32 de gama baja, y órdenes de magnitud más pequeño que los 8 MB disponibles en un ESP32-S3.

El uso de RAM en la inferencia está dominado por los búferes estáticos de `atome_state_t`: `x`, `normed`, tres arrays de trabajo para las salidas de vía, un array de estado oculto de SSM por capa, las cachés KV, el búfer de pesos del enrutador, el búfer de logits. Con los valores por defecto, esto totaliza unos pocos KB.

## 5. Qué no está en esta publicación

- No hay MoE de pesos multibanco (el motor no lo soporta; rompería la paridad exacta al bit).
- No hay escala ternaria por fila (misma razón).
- No hay embedding posicional. La conv local y el estado oculto del SSM codifican la posición implícitamente dentro de la ventana de secuencia fijada en tiempo de compilación del motor.
- No hay vía de recuperación, no hay vía de memoria episódica. Ambas requieren almacenamiento fuera del chip o grandes arrays de trabajo en RAM incompatibles con el hardware objetivo.

Son omisiones deliberadas, no lagunas. Son el precio de correr en hardware donde la RAM es la restricción vinculante.

## 6. Limitaciones

- **Escala.** La configuración por defecto es de unos 60 K parámetros (`d_model=64`, `n_layers=4`). Entrénala estrecha sobre un corpus enfocado y habla con fluidez en su ámbito; entrénala ancha y no será coherente. Eso es un reflejo de la capacidad, no de la arquitectura. Para más margen, aumenta `d_model` y `n_layers` — p. ej. `d_model=128`, `n_layers=6` es aproximadamente 600 K parámetros.
- **Longitud de secuencia.** Limitada por `ATOME_MAX_SEQ` en tiempo de compilación del motor (32 por defecto). Para generación de formato largo, genera token a token pasando el prefijo creciente a `atome_predict_next` — el motor rederiva el estado oculto del SSM a partir del prefijo completo en cada llamada, lo que mantiene la paridad Python ↔ C determinista.
- **Tokenización.** A nivel de byte. Las secuencias UTF-8 multibyte cuestan varias posiciones. No es ideal para escrituras no latinas con el valor por defecto `MAX_SEQ` del motor; considera aumentar `ATOME_MAX_SEQ` y reexportar si tu escritura objetivo tiene un alto promedio de bytes por carácter.

## Referencias

- Ma et al., 2024. *The Era of 1-bit LLMs: All Large Language Models are in 1.58 Bits.* arXiv:2402.17764.
- Wang et al., 2023. *BitNet: Scaling 1-bit Transformers for Large Language Models.* arXiv:2310.11453.
- Gu and Dao, 2023. *Mamba: Linear-Time Sequence Modeling with Selective State Spaces.* arXiv:2312.00752.
