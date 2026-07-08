[English](agri.md) · **Français** · [Español](agri.es.md) · [简体中文](agri.zh-CN.md) · [Deutsch](agri.de.md) · [日本語](agri.ja.md) <!-- i18n-switcher -->

# Rapport de tête SuperESP — agri

Précision de TEST tenue à l'écart : **0.953** (n=450)  •  AURC d'abstention **0.0053** (oracle 0.0011, aléatoire 0.0467)

## Matrice de confusion (lignes = vrai, colonnes = prédit)

| vrai \\ préd | healthy | needs_irrigate | frost_risk | pest_favorable | sensor_fault |
|---|---|---|---|---|---|
| healthy | **87** | 0 | 0 | 0 | 3 |
| needs_irrigate | 0 | **90** | 0 | 0 | 0 |
| frost_risk | 0 | 0 | **90** | 0 | 0 |
| pest_favorable | 0 | 0 | 0 | **90** | 0 |
| sensor_fault | 17 | 1 | 0 | 0 | **72** |

## Rappel par classe
- healthy : 0.967 (87/90)
- needs_irrigate : 1.000 (90/90)
- frost_risk : 1.000 (90/90)
- pest_favorable : 1.000 (90/90)
- sensor_fault : 0.800 (72/90)

## Risque vs couverture (s'abstenir sur les entrées à faible marge)
| couverture | risque |
|---|---|
| 0.50 | 0.000 |
| 0.70 | 0.006 |
| 0.90 | 0.017 |
| 1.00 | 0.047 |
