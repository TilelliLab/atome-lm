[English](README.md) · [Français](README.fr.md) · **Español** · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# SuperESP — Atome-LM aplicado para el edge ESP32

SuperESP convierte el modelo Atome ternario minúsculo (1,58 bit) en una suite de
**clasificadores de flujo aplicados** que corren en un microcontrolador *en lugar de*
generar texto, más un runtime **«OS» en el dispositivo** que lee todos los sensores del
ESP32 y despacha a la cabeza correcta.

Realiza el PIVOTE #1 de la revisión de foso (moat) de Atome del 2026-06-13: la cabeza
`atome_classify` existía en el motor C pero **nunca se había entrenado**. SuperESP la
entrena — para 7 tareas edge reales — y cablea inferencia delta (energía), abstención
(rechazar-cuando-inseguro) y atestación criptográfica (auditabilidad).

## Las 11 cabezas (una única compilación de motor compartida; cada cabeza = un blob ATOMECL01 distinto)
| cabeza | tarea | datos |
|---|---|---|
| SuperESP-Agri | suelo/clima → regar/helada/plaga/sano/fallo | SYNTH (agronómico) |
| SuperESP-Voice | micro I2S → comandos de voz de granja (on/off/stop/go) | REAL (Speech Commands) |
| SuperESP-Motion | IMU → actividad/gesto/caída | REAL (UCI HAR) |
| SuperESP-Sound-Scene | audio ambiente → evento acústico | SYNTH (audio sintético) |
| SuperESP-Anomaly | vibración → salud de la máquina | SYNTH (física) |
| SuperESP-Air | gas+clima → calidad del aire/fuga | SYNTH (física) |
| SuperESP-OS | telemetría ESP32 fusionada → estado del dispositivo + despacho | SYNTH (telemetría del chip) |
| SuperESP-Power | energía pinza amperimétrica/NILM → tipo de carga | SYNTH (física) |
| SuperESP-Occupancy | PIR+CO2+sonido → ocupación de la sala | SYNTH (física) |
| SuperESP-Wearable | PPG+IMU → estado cardíaco/actividad (no médico) | SYNTH (física) |
| SuperESP-Water | caudal+presión+humedad → fuga/inundación | SYNTH (física) |

## Velocidad
- **Kernel ternario:** matvec 4-trits/byte sin ramificación → **clasificación 306 µs → 87 µs (3,5×)**, ~11.400/s
  en host (-O3). Beneficia a todo el motor Atome (classify + generate + ESP32). Exactitud al bit
  preservada (paridad máx |Δ| 8,3e-7); los 146 tests existentes pasan.
- **Streaming con umbral de cambio** (`framework/streaming.py`): en un flujo correlacionado siempre activo, solo
  reejecutar el modelo cuando la entrada deriva más allá de un umbral de disparo; si no, reutilizar la decisión
  en caché (bit-idéntica a ejecutar cada trama). La tasa de salto es la ganancia (≈98 % en un flujo estático).
- **Inferencia delta** (`framework/delta.py`): 4-11× menos operaciones matvec en flujos correlacionados.
- Los tok/s/RAM en silicio ESP32 están **NO MEDIDOS** (sin placa); se espera que las aceleraciones del host se trasladen.

Véase `HONEST_RESULTS.md` / `artifacts/RESULTS.json` para la precisión apartada,
el AURC de abstención, la aceleración de inferencia delta, y la etiqueta REAL/SYNTH por cabeza.

## Cómo funciona
- **Tokenizador** (`framework/tokenize.py`): cada trama de sensor/característica se cuantiza
  linealmente a una secuencia de bytes (≤32) — de modo que el motor Atome existente de vocabulario
  de 256 bytes corre sin cambios. Las constantes de cuantización se ajustan solo con TRAIN (sin fugas).
- **Modelo** (`framework/model.py`): la base `AtomeLM` existente + una cabeza de
  clasificación ternaria sobre el oculto final-norm del último token — exactamente lo que
  el C `atome_classify` calcula. **Paridad Python↔C exacta al bit** (máx |Δ| ~7e-7).
- **Abstención** (`framework/abstain.py`): rechazar cuando el margen softmax top1-top2
  es bajo; reportado como una curva riesgo-cobertura + AURC vs oráculo/aleatorio.
- **Inferencia delta** (`framework/delta.py`): matvec delta integra-y-dispara para
  flujos de sensores correlacionados — el proxy de energía medido del experimento
  delta_inference, aplicado por cabeza.
- **Atestación** (`attest/sign.py`): recibo firmado Ed25519 que liga sha256(blob)
  + metadatos, para que un desplegador pueda probar que ESTA cabeza exacta se ejecutó. A prueba de manipulaciones (tamper-evident).
- **Runtime** (`runtime/dispatcher.py`): enruta una trama a su cabeza por modalidad,
  ejecuta la cabeza OS sobre la telemetría fusionada, descarga carga bajo estados de fallo. Espejo C:
  `c_engine/superesp/superesp_os.c`. Esqueleto de firmware: `superesp/firmware/`.

## Instalación
```
pip install -e .              # core (torch + numpy); run the CLI as: python3 -m superesp.cli <cmd>
pip install -e ".[superesp]"  # + cryptography/scipy/pyserial/esptool (attestation, audio, flashing)
```

## Flashear cualquier ESP32 (sin necesidad de ESP-IDF — precompilado para esp32/s2/s3/c3/c6/h2)
```
bash superesp/esp32/install.sh    # auto-detects the chip, flashes the matching
                                  # prebuilt firmware, runs all heads, writes a report
```

## Haz tu PROPIO clasificador en minutos (sin habilidad ML — el bucle log→entrenar→flashear)
```
# 1. flash the data-logger, then record YOUR sensor in each state:
python3 -m superesp.cli log --label dry --out field.csv   # leave probe in dry soil
python3 -m superesp.cli log --label wet --out field.csv   # ...then wet soil
# 2. train + see how good it is + deploy:
python3 -m superesp.cli train --csv field.csv --name myfarm
python3 -m superesp.cli report myfarm                     # confusion matrix + abstention (md + html)
python3 -m superesp.cli flashplan myfarm
# (or start from a blank template:)  python3 -m superesp.cli new myfarm --features 30
```
**Las 9 cabezas SYNTH son solo valores por defecto — totalmente intercambiables.** Entrena bajo un nombre
integrado con tus propios datos para reemplazarla por un modelo del mundo real:
`python3 -m superesp.cli train --csv my_field.csv --name agri` sobrescribe el blob de la cabeza sintética `agri`.
Nada está hardcodeado; cada cabeza es «entrenar con datos → exportar un blob».

## Reproducir / trae tus propios datos
```
python3 -m superesp.cli list                      # the 11 built-in heads
python3 -m superesp.cli train agri                # train+eval+export one built-in head
# YOUR sensor: rows = up to 32 features + a label column
python3 -m superesp.cli train --csv my.csv --label-col state --name mysensor
python3 -m superesp.cli flashplan mysensor        # how to bake the blob into firmware
# or everything at once:
python3 -m superesp.train_all && python3 -m superesp.attest_all
python3 -m pytest superesp/tests                  # framework, parity(gcc), attest, dispatch, streaming, csv, novelty
```
Cualquiera con un CSV de sus propias ventanas de sensor ESP32 obtiene un clasificador en el dispositivo
exacto al bit y atestable — sin configuración ML. Este es el análogo abierto/auditable de un
pipeline TinyML comercial.

## Alcance honesto / foso (moat)
Las cabezas individuales son edge-AI aplicado real (un PASO / un producto), **no fosos** —
KWS/gesto/anomalía de TinyML están saturados (TFLite-Micro, Edge Impulse). El único
ángulo defendible es la combinación **ternario ultra-minúsculo + auditable al bit +
atestado criptográficamente + eficiente en delta** como un OS
unificado en el dispositivo. Es una apuesta de primer-actor/integración, no un foso de laboratorio. Las cabezas
entrenadas con datos SYNTH son sustitutos de estilo físico, etiquetados como tales — no
afirmaciones de despliegue en campo. El rendimiento/RAM en silicio están **NO MEDIDOS** (sin placa).
```
```
