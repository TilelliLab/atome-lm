[English](RESULTS.md) · [Français](RESULTS.fr.md) · [Español](RESULTS.es.md) · [简体中文](RESULTS.zh-CN.md) · **Deutsch** · [日本語](RESULTS.ja.md) <!-- i18n-switcher -->

# Delta-Inferenz-Experiment — Ergebnisse

**Datum:** 2026-05-19
**Frage:** Kann Atome die Neuberechnung überspringen, so wie das Auge eine statische
Wand nicht neu rendert? Vollständige Neuberechnung vs. temporales Delta-Ternär-Matvec messen.

## Aufbau

- Ternäre 256×256-Matrix (spiegelt das `d_model` des 944K-Atome-Modells), ~1/3 Nullen
- 256-Schritt-Eingabestrom, drei Eingaberegime
- `out_new = out_old + W @ (x_new - x_prev)` — exakt bei Schwellwert 0
- Selektives `x_prev`-Update: nur propagierte Kanäle aktualisieren, sodass der
  ausstehende Fehler jedes Kanals jederzeit durch `threshold` begrenzt ist — das ist Integrate-and-Fire
- Energie-Proxy: `iters` = Durchläufe der inneren Schleife (jeder Durchlauf entpackt ein Trit + verzweigt,
  ~1 Zyklus auf einem MCU, egal ob er ein MAC macht). Deterministisch und exakt.

## Ergebnisse (Host, Zyklen pro Pfad separat gemessen)

| Regime | Schwellwert | iter-Speedup | Zyklus-Speedup | max. Fehler |
|---|---|---|---|---|
| **Sensorstrom** | 0.000 | 1.00× | 1.04× | 0.00001 |
| (korrelierte Eingabe) | 0.005 | **17.52×** | 15.66× | 0.00715 |
| | 0.020 | **51.24×** | 42.96× | 0.01845 |
| | 0.050 | **59.67×** | 49.07× | 0.03455 |
| **Token-Embeddings** | 0.000 | 1.00× | 1.04× | 0.00001 |
| (unkorreliert / LM-Generierung) | 0.005 | 1.01× | 1.05× | 0.00072 |
| **Hidden-State-Proxy** | 0.000 | 3.30× | 3.25× | 0.00001 |
| (~30 % der Kanäle bewegen sich) | 0.005 | 3.39× | 3.34× | 0.00171 |
| | 0.020 | 3.68× | 3.59× | 0.01163 |

QEMU Cortex-M3 (`mps2-an385`): die `iters` sind **bit-identisch** zum Host
(16.711.680 / 954.112 / 326.144 / …) — der Energie-Proxy reproduziert exakt auf der
Ziel-ISA. Der DWT-Zykluszähler auf dem Ziel liest 0, weil QEMUs `mps2-an385`
`DWT->CYCCNT` nicht modelliert; Zyklenzahlen auf echtem Silizium brauchen ein Cortex-M3-
Dev-Board oder ein zyklen-genaues Modell. Die Host-Wanduhr bestätigt bereits, dass die
`iters` echte Zyklen verfolgen (15,66× Zyklus vs. 17,52× iter — die Lücke ist der Schleifen-/Aufruf-Overhead).

## Befunde

1. **Der Gewinn ist real und groß — aber nur für korrelierte Eingabe.** Ein Strom
   im Sensorstil bei Schwellwert 0,005 läuft mit **17,5× weniger Operationen** bei einem
   Worst-Case-Ausgabefehler von 0,007 (die Gewichte haben Skala 0,05, das sind also ~0,7 % eines
   typischen Logits). Bei Schwellwert 0,02 ist es **51×**. Für ein MCU-Gerät, das ein
   Thermostat, ein Beschleunigungssensor-Gestenerkenner oder ein Audio-Keyword-Spotter ist,
   ist das eine direkte 17–51×-Kürzung der Inferenzenergie.

2. **Kein Freibier für die Token-LM-Generierung — bestätigt.** Szenario B hält bei
   1,0×. Aufeinanderfolgende Byte-Embeddings sind unkorreliert; es gibt keine "statische Wand"
   zum Überspringen. Das ist das ehrliche Ergebnis und es passt zur Vorhersage. Delta-
   Inferenz ist eine Optimierung *der Eingabemodalität*, keine universelle.

3. **Mittlere Netzwerk-Hidden-States liegen dazwischen (~3,3×).** Selbst ohne Schwellwert
   gibt ein Residualstrom, bei dem ~30 % der Kanäle sich pro Schritt bewegen, 3,3× gratis
   (exakt, Fehler 1e-5), weil 70 % des Matvec echt redundant sind. Das ist
   die interessanteste Zahl: sie legt nahe, dass Delta-Inferenz *innerhalb* des
   Netzwerks hilft, selbst wenn die Token-Eingabe es nicht tut, besonders für den SSM-Pfad,
   dessen Zustand sich langsam entwickelt.

4. **Der Schwellwert ist buchstäblich ein Feuerungs-Schwellwert.** Weil `x_prev` sich nur
   für propagierte Kanäle aktualisiert, integriert ein Kanal mit Unter-Schwellwert-Drift
   still, bis er die Schranke überschreitet, einmal feuert und zurücksetzt. Der Fehler ist durch
   `threshold` begrenzt, ohne Akkumulation und ohne periodisches "Sakkaden"-Refresh
   erforderlich. Der Energie-/Genauigkeits-Trade-off ist ein einzelner Regler.

## Ehrliche Einschränkungen

- Die synthetische 256×256-Matrix ist repräsentativ, aber kein trainiertes Atome-Gewichts-
  Set — die echte Gewichts-Sparsity-Struktur könnte die Konstanten verschieben (nicht
  den Trend).
- Nur das Matvec ist "delta-isiert". LayerNorm/SSM/Attention sind nichtlinear; eine
  vollständige Integration braucht delta-bewusste (oder periodisch aufgefrischte) Varianten davon.
- "iters" ist ein treuer Energie-Proxy für die innere Matvec-Schleife, ignoriert aber die
  Speicherverkehr-Energie, die auf einem echten MCU dominieren kann — der *echte* Speedup auf
  Silizium könnte höher sein (weniger Datenbewegung) oder niedriger (schlechteres Cache-
  Verhalten durch das spaltenweise Delta-Zugriffsmuster). Braucht eine Dev-Board-Messung.
- Das Token-Regime-Ergebnis (1,0×) ist die ehrliche Obergrenze: Delta-Inferenz nicht als
  LM-Generierungs-Speedup verkaufen. Verkaufe sie für Streaming-Sensor-Klassifizierer.

## Empfehlung

Verdrahte Delta-Inferenz als **Opt-in-Modus für Streaming-Klassifizierer-Deployments**
(Atomes `atome_classify`-Pfad bei Sensoreingabe), nicht den generativen Pfad. Der
SSM-Pfad ist der natürliche Ort, ihn als Nächstes zu erweitern — sein Zustand ist das langsamste
Signal im Netzwerk. Kopple den Schwellwert mit dem L11-State-Norm-Monitor
(aus dem Sicherheits-Stack) als Drift-Watchdog. Erwartete Bandbreite: **15–50×
Inferenzenergie-Reduktion** für Geräte der Thermostat-/Audio-/Gesten-Klasse, zu einem
regelbaren, begrenzten Genauigkeitskosten.

## Reproduzieren

```bash
cd c_engine/experiments/delta_inference
make run        # host (synthetic)
make run-qemu   # cortex-m3 under QEMU (iters bit-identical to host)
make real       # validation on the real 944K weights (see below)
```

---

# Erweiterung: Validierung auf dem echten 944K-Atome-Modell

Das synthetische Experiment oben nutzte eine Zufallsmatrix. Dieser Abschnitt lässt den
Delta-Pfad gegen `checkpoints/atome_1m_v1.pt` (das echte trainierte 944K-Modell,
val_loss 1,0545) auf einer echten 196-Byte-TinyStories-Passage laufen.

`capture_real.py` hakt jeden Block ein, erfasst die echte Post-Norm-Eingabe und
jede Pfad-Ausgabe und misst die Delta-Redundanz pro Signal. `bench_real.c`
lässt dann das **C**-`dm_matvec_delta` über die echten erfassten Ströme laufen, unter Nutzung
des **echten ternarisierten Attention-Wv** des Modells, und bestätigt, dass das C-Primitiv
die numpy-Vorhersage reproduziert.

## Delta-Matvec-Speedup pro Pfad (echte Gewichte, 8-Block-Durchschnitt)

| Signal, das ein Matvec konsumiert | Schw. 0.0 | Schw. 0.02 | Schw. 0.05 | Schw. 0.10 |
|---|---|---|---|---|
| Post-Norm-Eingabe `h` | 1.00× | 1.05× | 1.11× | 1.17× |
| Conv-Pfad-Ausgabe | 1.01× | 1.06× | 1.12× | 1.22× |
| **SSM-Pfad-Ausgabe** | 1.00× | **4.06×** | **12.27×** | **45.16×** |
| Attention-Pfad-Ausgabe | 1.02× | 1.07× | 1.15× | 1.27× |

## C-Primitiv-Gegenprüfung (Block 0, echtes Wv 256×256, Skala 0.0412)

| matvec | Schw. 0.0 | Schw. 0.02 | Schw. 0.05 | Schw. 0.10 |
|---|---|---|---|---|
| `Wv @ h` (numpy-Vorhersage) | 1.03× | 1.26× | 1.53× | 1.61× |
| `Wv @ h` (**C gemessen**) | 1.03× | 1.26× | 1.53× | 1.61× |
| `Wv @ ssm_out` (numpy-Vorhersage) | 1.00× | 3.12× | 8.60× | 33.64× |
| `Wv @ ssm_out` (**C gemessen**) | 1.00× | 3.12× | 8.60× | 33.64× |

Das C-Delta-Primitiv und die numpy-Referenz stimmen bei echten trainierten Gewichten
und echten Aktivierungen **exakt** überein. Der maximale Fehler pro Kanal bleibt ≤ Schwellwert
(gemessen 0,10000 bei Schw. 0,10) — die Integrate-and-Fire-Schranke hält auf echten Daten.

## Befunde — und ein ehrliches Negativergebnis

1. **Die SSM-Pfad-Ausgabe ist der Delta-Sweet-Spot, mit großem Abstand.** Auf
   echten Gewichten ist sie 4–45× delta-komprimierbar; jedes andere Signal im
   Block ist 1,0–1,3×. Ein von der SSM-Ausgabe gespeistes Matvec leistet 12× weniger Arbeit bei
   Schwellwert 0,05 für ~5 % Fehler pro Kanal.

2. **Das SSM selbst kann nicht delta-komprimiert werden — und das ist in Ordnung.** Es ist eine
   Rekurrenz pro Kanal `h_t = a·h_{t-1} + b·x_t`; jeder Schritt hängt vom
   letzten ab, also kann kein Schritt übersprungen werden. Aber es ist bereits O(Kanäle), nicht der
   Engpass. Seine Rolle in der Delta-Inferenz ist die des *Langsam-Signal-Generators*:
   es ist ein Tiefpassfilter pro Kanal, also ist seine Ausgabe das positions-
   korrelierteste Signal im Netzwerk — was genau das ist, was das
   nachgelagerte Matvec delta-freundlich macht. Die frühere RESULTS-Empfehlung
   ("Delta auf das SSM erweitern") war halb richtig: erweitere es auf das Matvec, das
   das SSM *konsumiert*, nicht auf die SSM-Rekurrenz selbst.

3. **Ehrliches Negativergebnis: Post-Norm-`h`, Conv-Ausgabe und Attention-Ausgabe sind NICHT
   delta-freundlich (~1,0–1,3×).** LayerNorm renormalisiert jede Position, sodass `h`
   sich auf fast jedem Kanal verschiebt; Conv- und Attention-Ausgaben ändern sich echt
   von Position zu Position. Delta-Inferenz auf den Attention-Wq/Wk/Wv-Projektionen
   (die `h` konsumieren) bringt fast nichts. Setze sie dort nicht ein.

4. **Tiefere Blöcke sind delta-freundlicher als Block 0** (45× 8-Block-Durchschnitt
   vs. 33× bei Block 0, Schw. 0,10) — der SSM-Zustand wärmt sich mit der Tiefe auf, sodass die
   Langsam-Signal-Eigenschaft tiefer im Netzwerk stärker wird.

## Verfeinerte Empfehlung

Setze Delta-Inferenz auf **den Matvec-Schichten ein, die die SSM-Pfad-Ausgabe
konsumieren**, nicht auf den Attention-Projektionen und nicht auf der SSM-Rekurrenz
selbst. Auf dem echten 944K-Modell ist das eine **gemessene 8–12×-Rechenreduktion**
bei Schwellwert 0,05 (≈5 % Fehler pro Kanal, begrenzt), steigend auf 33–45× bei
Schwellwert 0,10. Kopple den Schwellwert mit dem L11-State-Norm-Monitor als Drift-
Watchdog.

## Qualitätskosten — gemessen (2026-05-20, `quality_real.py`)

Der frühere Entwurf hielt die Energiezahl zurück, weil die *Qualitäts*-Kosten des
Schwellwert-Fehlers ungemessen waren. Sie sind jetzt gemessen. Delta-Inferenz auf einem
Matvec, das ein Signal S konsumiert, ist äquivalent dazu, dem exakten Matvec ein
integrate-and-fire-schwellwert-behandeltes S zuzuführen; also behandeln wir die SSM-Ausgabe
jedes Blocks mit Schwellwert, lassen den Rest des echten 944K-Modells exakt laufen und
messen die Kreuzentropie.

| Schwellwert | SSM-Pfad-Speedup | Δ Perplexität |
|---|---|---|
| 0.00 | 1.0× | +0.00% (exakt — Sanity-Check) |
| 0.02 | 4.1× | −0.46% (innerhalb des Rauschens) |
| **0.05** | **12.6×** | **+0.57%** |
| 0.10 | 49× | +5.6% |
| 0.20 | 320× | +11.5% (bricht) |

**Die Behauptung überlebt.** Bei Schwellwert 0,05 liefert der SSM-Pfad eine echte
**12,6×-Reduktion der Iterationszahl für +0,57 % Perplexität** auf dem trainierten
Modell — ein auslieferbarer Trade-off. Bei 0,10 ist es aggressiv (49× / +5,6 %); bei 0,20
bricht es. Das widerlegt auch die Sorge, die SSM-Ausgabe sei "nahezu konstant
und trage nichts bei": trüge sie nichts bei, wäre ihr Veralten bei jedem Schwellwert
gratis — stattdessen kostet 0,20 +11,5 %, also ist die SSM-Ausgabe echt wichtig
und das Modell toleriert echt ein *begrenztes* Veralten.

## Verbleibende ehrliche Einschränkung

Die Qualitätszahl oben ist **Kreuzentropie an der Prefill-Position (prefill)**, nicht
autoregressive Generierung. Die SSM-Tiefpass-Eigenschaft sollte sich auf die
Generierung übertragen (es ist ein rekurrenter Filter), aber eine Messung im Generierungs-
Schritt wurde nicht durchgeführt. Nenne die 12,6×/+0,57 %-Zahl mit dieser Einschränkung.

## Reproduzieren (Erweiterung mit echten Gewichten)

```bash
cd c_engine/experiments/delta_inference
python3 capture_real.py   # loads the real 944K ckpt, writes traces/
make real                 # C primitive cross-check on the real traces
```
