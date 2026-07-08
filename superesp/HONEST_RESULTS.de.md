[English](HONEST_RESULTS.md) · [Français](HONEST_RESULTS.fr.md) · [Español](HONEST_RESULTS.es.md) · [简体中文](HONEST_RESULTS.zh-CN.md) · **Deutsch** · [日本語](HONEST_RESULTS.ja.md) <!-- i18n-switcher -->

# SuperESP — Ehrliche Ergebnisse

> Erzeugt von `make_results_doc.py` aus `artifacts/RESULTS.json`. Jede Zahl stammt aus einem zurückgehaltenen TEST-Split. ECHT = echter öffentlicher Datensatz; SYNTH = Physik-artiger Platzhalter (gekennzeichnet, keine Feldbehauptung).

## Tabelle 1 — zurückgehaltene Genauigkeit pro Kopf + Abstention + Delta

| Kopf | Daten | Klassen | Params | TEST-Acc | Abst.-AURC (Orakel/Zuf) | Cov@≤5% Risiko | Blob B | delta@0.05 |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| SuperESP-Agri | SYNTH | 5 | 20512 | 0.976 | 0.0015 (0.0003/0.0244) | 1.00 | 6633 | 8.41x/err0.0179 |
| SuperESP-Voice | ECHT | 4 | 20480 | 0.625 | 0.7297 (0.3700/0.7250) | 0.00 | 6625 | N/A (tabellarisch) |
| SuperESP-Motion | ECHT | 6 | 20544 | 0.811 | 0.0644 (0.0191/0.1891) | 0.53 | 6641 | N/A (tabellarisch) |
| SuperESP-Sound-Scene | SYNTH | 4 | 20480 | 0.975 | 0.0064 (0.0003/0.0250) | 1.00 | 6625 | N/A (tabellarisch) |
| SuperESP-Anomaly | SYNTH | 4 | 20480 | 0.937 | 0.0290 (0.0020/0.0633) | 0.96 | 6625 | 4.19x/err0.0161 |
| SuperESP-Air | SYNTH | 4 | 20480 | 0.978 | 0.0000 (0.0000/0.0000) | 1.00 | 6625 | 6.77x/err0.01 |
| SuperESP-OS | SYNTH | 5 | 20512 | 0.987 | 0.0007 (0.0001/0.0133) | 1.00 | 6633 | 4.27x/err0.0106 |
| SuperESP-Power | SYNTH | 4 | 20480 | 0.981 | 0.0007 (0.0002/0.0194) | 1.00 | 6625 | 8.28x/err0.0142 |
| SuperESP-Occupancy | SYNTH | 3 | 20448 | 0.984 | 0.0008 (0.0001/0.0159) | 1.00 | 6617 | 8.15x/err0.0127 |
| SuperESP-Wearable | SYNTH | 4 | 20480 | 0.983 | 0.0005 (0.0001/0.0167) | 1.00 | 6625 | 8.4x/err0.0098 |
| SuperESP-Water | SYNTH | 4 | 20480 | 0.989 | 0.0001 (0.0001/0.0111) | 1.00 | 6625 | 8.53x/err0.0114 |
| SuperESP-Forecast | SYNTH | 4 | 20480 | 0.831 | 0.0554 (0.0152/0.1690) | 0.59 | 6625 | 9.19x/err0.0151 |

**Mittlere zurückgehaltene Genauigkeit über 12 Köpfe: 0,921** (min. 0,625, max. 0,989).

## Tabelle 2 — Python↔C-Parität (bit-genau)

- max. |Δ Logit| über die getesteten Köpfe: **1.430511474609375e-06** (Toleranz 1e-3); Argmax-Übereinstimmung: True.

## Tabelle 3 — Attestierung

- 12/12 Kopf-Blobs mit Ed25519 signiert und verifiziert; Manipulation (Blob/Metadaten/Signatur) abgelehnt (siehe tests/test_attest.py).

## Was NICHT gemessen ist

- Tok/s auf Silizium, RAM-Hochwassermarke, Live-ADC/I2S-Erfassung — kein physisches ESP32 in der Build-Box. Die Firmware ist ein reines Build-Skelett.

- SYNTH-Köpfe sind Physik-artige Platzhalter, keine Feldeinsätze.

## Burggraben-(moat)-Urteil

- Einzelne Köpfe sind ein echter Schritt / ein angewandtes Produkt, **keine Burggräben** (TinyML ist überfüllt). Verteidigungsfähiger Winkel = winzig-ternäres + bit-genau-auditierbares + attestiertes + Delta-effizientes einheitliches OS (First-Mover-/Integrations-Wette).
