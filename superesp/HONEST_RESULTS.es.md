[English](HONEST_RESULTS.md) · [Français](HONEST_RESULTS.fr.md) · **Español** · [简体中文](HONEST_RESULTS.zh-CN.md) · [Deutsch](HONEST_RESULTS.de.md) · [日本語](HONEST_RESULTS.ja.md) <!-- i18n-switcher -->

# SuperESP — Resultados honestos

> Generado por `make_results_doc.py` desde `artifacts/RESULTS.json`. Cada número proviene de una porción de TEST apartada. REAL = conjunto de datos público real; SYNTH = sustituto de estilo físico (etiquetado, no una afirmación de campo).

## Tabla 1 — precisión apartada por cabeza + abstención + delta

| cabeza | datos | clases | params | acc TEST | AURC abst. (oráculo/aleat) | cob@≤5 % riesgo | blob B | delta@0.05 |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| SuperESP-Agri | SYNTH | 5 | 20512 | 0.976 | 0.0015 (0.0003/0.0244) | 1.00 | 6633 | 8.41x/err0.0179 |
| SuperESP-Voice | REAL | 4 | 20480 | 0.625 | 0.7297 (0.3700/0.7250) | 0.00 | 6625 | N/A (tabular) |
| SuperESP-Motion | REAL | 6 | 20544 | 0.811 | 0.0644 (0.0191/0.1891) | 0.53 | 6641 | N/A (tabular) |
| SuperESP-Sound-Scene | SYNTH | 4 | 20480 | 0.975 | 0.0064 (0.0003/0.0250) | 1.00 | 6625 | N/A (tabular) |
| SuperESP-Anomaly | SYNTH | 4 | 20480 | 0.937 | 0.0290 (0.0020/0.0633) | 0.96 | 6625 | 4.19x/err0.0161 |
| SuperESP-Air | SYNTH | 4 | 20480 | 0.978 | 0.0000 (0.0000/0.0000) | 1.00 | 6625 | 6.77x/err0.01 |
| SuperESP-OS | SYNTH | 5 | 20512 | 0.987 | 0.0007 (0.0001/0.0133) | 1.00 | 6633 | 4.27x/err0.0106 |
| SuperESP-Power | SYNTH | 4 | 20480 | 0.981 | 0.0007 (0.0002/0.0194) | 1.00 | 6625 | 8.28x/err0.0142 |
| SuperESP-Occupancy | SYNTH | 3 | 20448 | 0.984 | 0.0008 (0.0001/0.0159) | 1.00 | 6617 | 8.15x/err0.0127 |
| SuperESP-Wearable | SYNTH | 4 | 20480 | 0.983 | 0.0005 (0.0001/0.0167) | 1.00 | 6625 | 8.4x/err0.0098 |
| SuperESP-Water | SYNTH | 4 | 20480 | 0.989 | 0.0001 (0.0001/0.0111) | 1.00 | 6625 | 8.53x/err0.0114 |
| SuperESP-Forecast | SYNTH | 4 | 20480 | 0.831 | 0.0554 (0.0152/0.1690) | 0.59 | 6625 | 9.19x/err0.0151 |

**Precisión media apartada en 12 cabezas: 0,921** (mín 0,625, máx 0,989).

## Tabla 2 — paridad Python↔C (exacta al bit)

- máx |Δ logit| en las cabezas probadas: **1.430511474609375e-06** (tolerancia 1e-3); acuerdo de argmax: True.

## Tabla 3 — atestación

- 12/12 blobs de cabeza firmados con Ed25519 y verificados; manipulación (blob/metadatos/firma) rechazada (véase tests/test_attest.py).

## Qué NO se mide

- Los tok/s en silicio, la marca alta de RAM, la captura ADC/I2S en vivo — sin ESP32 físico en la máquina de compilación. El firmware es un esqueleto de solo-compilación.

- Las cabezas SYNTH son sustitutos de estilo físico, no despliegues de campo.

## Veredicto de foso (moat)

- Las cabezas individuales son un PASO real / un producto aplicado, **no fosos** (TinyML está saturado). Ángulo defendible = OS unificado ternario-minúsculo + auditable al bit + atestado + eficiente en delta (apuesta de primer-actor/integración).
