[English](HONEST_RESULTS.md) · **Français** · [Español](HONEST_RESULTS.es.md) · [简体中文](HONEST_RESULTS.zh-CN.md) · [Deutsch](HONEST_RESULTS.de.md) · [日本語](HONEST_RESULTS.ja.md) <!-- i18n-switcher -->

# SuperESP — Résultats honnêtes

> Généré par `make_results_doc.py` depuis `artifacts/RESULTS.json`. Chaque nombre provient d'une tranche de TEST tenue à l'écart. RÉEL = jeu de données public réel ; SYNTH = substitut de style physique (étiqueté, pas une affirmation de terrain).

## Tableau 1 — précision tenue à l'écart par tête + abstention + delta

| tête | données | classes | params | acc TEST | AURC abst. (oracle/aléa) | couv@≤5 % risque | blob o | delta@0.05 |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| SuperESP-Agri | SYNTH | 5 | 20512 | 0.976 | 0.0015 (0.0003/0.0244) | 1.00 | 6633 | 8.41x/err0.0179 |
| SuperESP-Voice | RÉEL | 4 | 20480 | 0.625 | 0.7297 (0.3700/0.7250) | 0.00 | 6625 | N/A (tabulaire) |
| SuperESP-Motion | RÉEL | 6 | 20544 | 0.811 | 0.0644 (0.0191/0.1891) | 0.53 | 6641 | N/A (tabulaire) |
| SuperESP-Sound-Scene | SYNTH | 4 | 20480 | 0.975 | 0.0064 (0.0003/0.0250) | 1.00 | 6625 | N/A (tabulaire) |
| SuperESP-Anomaly | SYNTH | 4 | 20480 | 0.937 | 0.0290 (0.0020/0.0633) | 0.96 | 6625 | 4.19x/err0.0161 |
| SuperESP-Air | SYNTH | 4 | 20480 | 0.978 | 0.0000 (0.0000/0.0000) | 1.00 | 6625 | 6.77x/err0.01 |
| SuperESP-OS | SYNTH | 5 | 20512 | 0.987 | 0.0007 (0.0001/0.0133) | 1.00 | 6633 | 4.27x/err0.0106 |
| SuperESP-Power | SYNTH | 4 | 20480 | 0.981 | 0.0007 (0.0002/0.0194) | 1.00 | 6625 | 8.28x/err0.0142 |
| SuperESP-Occupancy | SYNTH | 3 | 20448 | 0.984 | 0.0008 (0.0001/0.0159) | 1.00 | 6617 | 8.15x/err0.0127 |
| SuperESP-Wearable | SYNTH | 4 | 20480 | 0.983 | 0.0005 (0.0001/0.0167) | 1.00 | 6625 | 8.4x/err0.0098 |
| SuperESP-Water | SYNTH | 4 | 20480 | 0.989 | 0.0001 (0.0001/0.0111) | 1.00 | 6625 | 8.53x/err0.0114 |
| SuperESP-Forecast | SYNTH | 4 | 20480 | 0.831 | 0.0554 (0.0152/0.1690) | 0.59 | 6625 | 9.19x/err0.0151 |

**Précision moyenne tenue à l'écart sur 12 têtes : 0,921** (min 0,625, max 0,989).

## Tableau 2 — parité Python↔C (exacte au bit près)

- max |Δ logit| sur les têtes testées : **1.430511474609375e-06** (tolérance 1e-3) ; accord d'argmax : True.

## Tableau 3 — attestation

- 12/12 blobs de tête signés Ed25519 et vérifiés ; altération (blob/métadonnées/signature) rejetée (voir tests/test_attest.py).

## Ce qui n'est PAS mesuré

- Les tok/s sur silicium, le point haut de RAM, la capture ADC/I2S en direct — pas d'ESP32 physique dans la machine de build. Le firmware est un squelette de compilation seule.

- Les têtes SYNTH sont des substituts de style physique, pas des déploiements de terrain.

## Verdict de douve (moat)

- Les têtes individuelles sont une vraie ÉTAPE / un produit appliqué, **pas des douves** (le TinyML est encombré). Angle défendable = OS unifié ternaire-minuscule + auditable au bit près + attesté + efficace en delta (pari de premier arrivé/intégration).
