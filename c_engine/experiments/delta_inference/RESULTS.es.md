[English](RESULTS.md) · [Français](RESULTS.fr.md) · **Español** · [简体中文](RESULTS.zh-CN.md) · [Deutsch](RESULTS.de.md) · [日本語](RESULTS.ja.md) <!-- i18n-switcher -->

# Experimento de inferencia delta — Resultados

**Fecha:** 2026-05-19
**Pregunta:** ¿Puede Atome evitar el recálculo como el ojo no re-renderiza una pared
estática? Medir el recálculo completo vs el matvec ternario con delta temporal.

## Montaje

- Matriz ternaria 256×256 (refleja el `d_model` del modelo Atome 944K), ~1/3 de ceros
- Flujo de entrada de 256 pasos, tres regímenes de entrada
- `out_new = out_old + W @ (x_new - x_prev)` — exacto en el umbral 0
- Actualización selectiva de `x_prev`: solo los canales propagados se actualizan, de modo que
  el error pendiente de cada canal está acotado por `threshold` en todo momento — esto es integra-y-dispara
- Proxy de energía: `iters` = pasadas por el bucle interno (cada pasada desempaqueta un trit + ramifica,
  ~1 ciclo en un MCU, haga o no un MAC). Determinista y exacto.

## Resultados (host, ciclos por ruta medidos por separado)

| Régimen | umbral | acel. iter | acel. ciclos | error máx |
|---|---|---|---|---|
| **Flujo de sensor** | 0.000 | 1.00× | 1.04× | 0.00001 |
| (entrada correlacionada) | 0.005 | **17.52×** | 15.66× | 0.00715 |
| | 0.020 | **51.24×** | 42.96× | 0.01845 |
| | 0.050 | **59.67×** | 49.07× | 0.03455 |
| **Embeddings de tokens** | 0.000 | 1.00× | 1.04× | 0.00001 |
| (no correlacionado / generación LM) | 0.005 | 1.01× | 1.05× | 0.00072 |
| **Proxy de estado oculto** | 0.000 | 3.30× | 3.25× | 0.00001 |
| (~30 % de los canales se mueven) | 0.005 | 3.39× | 3.34× | 0.00171 |
| | 0.020 | 3.68× | 3.59× | 0.01163 |

QEMU Cortex-M3 (`mps2-an385`): los `iters` son **bit-idénticos** al host
(16.711.680 / 954.112 / 326.144 / …) — el proxy de energía se reproduce exactamente en la
ISA objetivo. El contador de ciclos DWT en el objetivo lee 0 porque el `mps2-an385` de QEMU
no modela `DWT->CYCCNT`; los números de ciclos en silicio real necesitan una placa de
desarrollo Cortex-M3 o un modelo exacto al ciclo. El reloj de pared del host ya confirma
que los `iters` siguen los ciclos reales (15,66× ciclo vs 17,52× iter — la brecha es la sobrecarga
de bucle/llamada).

## Hallazgos

1. **La ganancia es real y grande — pero solo para entrada correlacionada.** Un flujo
   de estilo sensor en el umbral 0,005 ejecuta **17,5× menos operaciones** para un error de
   salida en el peor caso de 0,007 (los pesos tienen escala 0,05, así que esto es ~0,7 % de un
   logit típico). En el umbral 0,02 es **51×**. Para un dispositivo MCU que es un
   termostato, un detector de gestos por acelerómetro, o un localizador de palabras clave
   de audio, esto es un recorte directo de 17-51× en la energía de inferencia.

2. **Sin almuerzo gratis para la generación LM por tokens — confirmado.** El escenario B se mantiene en
   1,0×. Los embeddings de bytes consecutivos no están correlacionados; no hay «pared
   estática» que saltar. Este es el resultado honesto y coincide con la predicción. La inferencia
   delta es una optimización *de modalidad de entrada*, no universal.

3. **Los estados ocultos de en medio de la red quedan entre ambos (~3,3×).** Incluso sin umbral,
   un flujo residual donde ~30 % de los canales se mueven por paso da 3,3× gratis
   (exacto, error 1e-5) porque el 70 % del matvec es genuinamente redundante. Este es
   el número más interesante: sugiere que la inferencia delta ayuda *dentro* de la
   red incluso cuando la entrada por tokens no lo hace, especialmente para la vía SSM
   cuyo estado evoluciona lentamente.

4. **El umbral es literalmente un umbral de disparo.** Como `x_prev` solo se actualiza
   para los canales propagados, un canal con deriva por debajo del umbral integra
   silenciosamente hasta que cruza la barra, dispara una vez, y se reinicia. El error está acotado por
   `threshold` sin acumulación y sin refresco «sacádico» periódico
   requerido. El compromiso energía/precisión es una única perilla.

## Limitaciones honestas

- La matriz sintética 256×256 es representativa pero no un conjunto de pesos Atome
  entrenado real — la estructura real de dispersión de los pesos puede desplazar las constantes (no
  la tendencia).
- Solo el matvec está «delta-izado». LayerNorm/SSM/atención son no lineales; una
  integración completa necesita variantes delta-conscientes (o refrescadas periódicamente) de ellas.
- «iters» es un proxy de energía fiel para el bucle interno del matvec pero ignora
  la energía del tráfico de memoria, que en un MCU real puede dominar — la aceleración *real* en
  silicio podría ser mayor (menos movimiento de datos) o menor (peor comportamiento de caché
  por el patrón de acceso delta en columna-mayor). Necesita una medición en placa de desarrollo.
- El resultado en régimen de token (1,0×) es el techo honesto: no presentar la inferencia delta
  como una aceleración de generación LM. Preséntala para clasificadores de flujo de sensores.

## Recomendación

Cablea la inferencia delta como un **modo opcional para despliegues de clasificadores de flujo**
(la ruta `atome_classify` de Atome sobre entrada de sensor), no la ruta generativa. La
vía SSM es el lugar natural para extenderlo a continuación — su estado es la señal más lenta
de la red. Empareja el umbral con el monitor de norma de estado L11
(de la pila de seguridad) como perro guardián de la deriva. Envolvente esperada: **15-50×
de reducción de energía de inferencia** para dispositivos de clase termostato/audio/gesto, a un
coste de precisión acotado y ajustable.

## Reproducir

```bash
cd c_engine/experiments/delta_inference
make run        # host (synthetic)
make run-qemu   # cortex-m3 under QEMU (iters bit-identical to host)
make real       # validation on the real 944K weights (see below)
```

---

# Extensión: validación en el modelo Atome 944K real

El experimento sintético de arriba usaba una matriz aleatoria. Esta sección ejecuta la
ruta delta contra `checkpoints/atome_1m_v1.pt` (el modelo 944K entrenado real,
val_loss 1,0545) sobre un pasaje TinyStories real de 196 bytes.

`capture_real.py` engancha cada bloque, captura la entrada post-norm real y
cada salida de vía, y mide la redundancia delta por señal. `bench_real.c`
ejecuta entonces el `dm_matvec_delta` **C** sobre los flujos reales capturados usando el
**Wv de atención ternarizado real** del modelo, y confirma que la primitiva C
reproduce la predicción de numpy.

## Aceleración delta-matvec por vía (pesos reales, promedio de 8 bloques)

| Señal que consume un matvec | umbral 0.0 | umbral 0.02 | umbral 0.05 | umbral 0.10 |
|---|---|---|---|---|
| entrada post-norm `h` | 1.00× | 1.05× | 1.11× | 1.17× |
| salida de la vía conv | 1.01× | 1.06× | 1.12× | 1.22× |
| **salida de la vía SSM** | 1.00× | **4.06×** | **12.27×** | **45.16×** |
| salida de la vía atención | 1.02× | 1.07× | 1.15× | 1.27× |

## Verificación cruzada de la primitiva C (bloque 0, Wv real 256×256, escala 0.0412)

| matvec | umbral 0.0 | umbral 0.02 | umbral 0.05 | umbral 0.10 |
|---|---|---|---|---|
| `Wv @ h` (predicción numpy) | 1.03× | 1.26× | 1.53× | 1.61× |
| `Wv @ h` (**C medido**) | 1.03× | 1.26× | 1.53× | 1.61× |
| `Wv @ ssm_out` (predicción numpy) | 1.00× | 3.12× | 8.60× | 33.64× |
| `Wv @ ssm_out` (**C medido**) | 1.00× | 3.12× | 8.60× | 33.64× |

La primitiva delta de C y la referencia de numpy concuerdan **exactamente** en pesos
entrenados reales y activaciones reales. El error máximo por canal se mantiene ≤ umbral
(medido 0,10000 en el umbral 0,10) — el límite integra-y-dispara se sostiene en datos reales.

## Hallazgos — y un negativo honesto

1. **La salida de la vía SSM es el punto dulce del delta, con diferencia.** En
   pesos reales es 4-45× delta-comprimible; cualquier otra señal del
   bloque es 1,0-1,3×. Un matvec alimentado por la salida SSM hace 12× menos trabajo en el
   umbral 0,05 para ~5 % de error por canal.

2. **El SSM en sí no puede delta-comprimirse — y está bien.** Es una
   recurrencia por canal `h_t = a·h_{t-1} + b·x_t`; cada paso depende del
   anterior, así que ningún paso puede saltarse. Pero ya es O(canales), no el
   cuello de botella. Su papel en la inferencia delta es el de *generador de señal lenta*:
   es un filtro paso-bajo por canal, así que su salida es la señal más
   correlacionada en posición de la red — que es exactamente lo que hace que el
   matvec aguas abajo sea delta-amigable. La recomendación previa de RESULTS
   («extender el delta al SSM») era medio acierto: extiéndelo al matvec que
   *consume* el SSM, no a la recurrencia SSM en sí.

3. **Negativo honesto: `h` post-norm, salida conv y salida atención NO son
   delta-amigables (~1,0-1,3×).** LayerNorm renormaliza cada posición de modo que `h`
   se desplaza en casi todos los canales; las salidas conv y atención cambian genuinamente
   de posición a posición. La inferencia delta sobre las proyecciones Wq/Wk/Wv de atención
   (que consumen `h`) casi no aporta nada. No la despliegues ahí.

4. **Los bloques más profundos son más delta-amigables que el bloque 0** (45× promedio de 8 bloques
   vs 33× en el bloque 0, umbral 0,10) — el estado SSM se calienta con la profundidad, de modo que la
   propiedad de señal lenta se refuerza más profundo en la red.

## Recomendación refinada

Despliega la inferencia delta en **las capas matvec que consumen la salida de la vía
SSM**, no en las proyecciones de atención ni en la recurrencia SSM
en sí. En el modelo 944K real eso es una **reducción de cómputo medida de 8-12×**
en el umbral 0,05 (≈5 % de error por canal, acotado), subiendo a 33-45× en el
umbral 0,10. Empareja el umbral con el monitor de norma de estado L11 como perro guardián de
la deriva.

## Coste de calidad — medido (2026-05-20, `quality_real.py`)

El borrador anterior retenía el número de energía porque el coste de *calidad* del
error de umbralización no estaba medido. Ahora sí lo está. La inferencia delta sobre un
matvec que consume una señal S equivale a alimentar el matvec exacto con una
S umbralizada por integra-y-dispara; así que umbralizamos la salida SSM de cada bloque,
ejecutamos el resto del modelo 944K real exactamente, y medimos la entropía cruzada.

| umbral | acel. vía SSM | Δ perplejidad |
|---|---|---|
| 0.00 | 1.0× | +0.00% (exacto — comprobación de cordura) |
| 0.02 | 4.1× | −0.46% (dentro del ruido) |
| **0.05** | **12.6×** | **+0.57%** |
| 0.10 | 49× | +5.6% |
| 0.20 | 320× | +11.5% (se rompe) |

**La afirmación sobrevive.** En el umbral 0,05 la vía SSM da una verdadera
**reducción de 12,6× en el conteo de iteraciones por +0,57 % de perplejidad** sobre el modelo
entrenado — un compromiso enviable. En 0,10 es agresivo (49× / +5,6 %); en 0,20
se rompe. Esto también refuta la preocupación de que la salida SSM sea «casi constante
y no aporte nada»: si no aportara nada, dejarla obsoleta sería gratis
en cualquier umbral — en cambio 0,20 cuesta +11,5 %, así que la salida SSM importa genuinamente
y el modelo tolera genuinamente una obsolescencia *acotada*.

## Salvedad honesta restante

El número de calidad de arriba es **entropía cruzada en posición de prellenado (prefill)**, no
generación autorregresiva. La propiedad paso-bajo del SSM debería trasladarse a la
generación (es un filtro recurrente), pero una medición en paso de generación no
se ha ejecutado. Enuncia el número 12,6×/+0,57 % con esa salvedad adjunta.

## Reproducir (extensión de pesos reales)

```bash
cd c_engine/experiments/delta_inference
python3 capture_real.py   # loads the real 944K ckpt, writes traces/
make real                 # C primitive cross-check on the real traces
```
