[English](agri.md) · [Français](agri.fr.md) · **Español** · [简体中文](agri.zh-CN.md) · [Deutsch](agri.de.md) · [日本語](agri.ja.md) <!-- i18n-switcher -->

# Informe de cabeza SuperESP — agri

Precisión de TEST apartada: **0.953** (n=450)  •  AURC de abstención **0.0053** (oráculo 0.0011, aleatorio 0.0467)

## Matriz de confusión (filas = verdadero, columnas = predicho)

| verd. \\ pred. | healthy | needs_irrigate | frost_risk | pest_favorable | sensor_fault |
|---|---|---|---|---|---|
| healthy | **87** | 0 | 0 | 0 | 3 |
| needs_irrigate | 0 | **90** | 0 | 0 | 0 |
| frost_risk | 0 | 0 | **90** | 0 | 0 |
| pest_favorable | 0 | 0 | 0 | **90** | 0 |
| sensor_fault | 17 | 1 | 0 | 0 | **72** |

## Recall por clase
- healthy: 0.967 (87/90)
- needs_irrigate: 1.000 (90/90)
- frost_risk: 1.000 (90/90)
- pest_favorable: 1.000 (90/90)
- sensor_fault: 0.800 (72/90)

## Riesgo vs cobertura (abstenerse en entradas de bajo margen)
| cobertura | riesgo |
|---|---|
| 0.50 | 0.000 |
| 0.70 | 0.006 |
| 0.90 | 0.017 |
| 1.00 | 0.047 |
