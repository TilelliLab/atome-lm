[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · **Deutsch** · [日本語](README.ja.md) <!-- i18n-switcher -->

# SuperESP — angewandtes Atome-LM für das ESP32-Edge

SuperESP verwandelt das winzige ternäre (1,58-Bit) Atome-Modell in eine Suite
**angewandter Streaming-Klassifizierer**, die auf einem Mikrocontroller laufen, *statt*
Text zu generieren, plus eine **"OS"-Laufzeit auf dem Gerät**, die alle Sensoren des
ESP32 ausliest und an den richtigen Kopf (head) verteilt.

Es realisiert PIVOT #1 des Atome-Burggraben-(moat)-Reviews vom 2026-06-13: der
`atome_classify`-Kopf existierte in der C-Engine, war aber **nie trainiert worden**. SuperESP
trainiert ihn — für 7 echte Edge-Aufgaben — und verdrahtet Delta-Inferenz (Energie),
Abstention (Ablehnung-bei-Unsicherheit) und kryptografische Attestierung (Auditierbarkeit).

## Die 11 Köpfe (ein gemeinsamer Engine-Build; jeder Kopf = ein anderer ATOMECL01-Blob)
| Kopf | Aufgabe | Daten |
|---|---|---|
| SuperESP-Agri | Boden/Klima → bewässern/Frost/Schädling/gesund/Fehler | SYNTH (agronomisch) |
| SuperESP-Voice | I2S-Mikrofon → Farm-Sprachbefehle (on/off/stop/go) | ECHT (Speech Commands) |
| SuperESP-Motion | IMU → Aktivität/Geste/Sturz | ECHT (UCI HAR) |
| SuperESP-Sound-Scene | Umgebungsaudio → akustisches Ereignis | SYNTH (synth. Audio) |
| SuperESP-Anomaly | Vibration → Maschinengesundheit | SYNTH (Physik) |
| SuperESP-Air | Gas+Klima → Luftqualität/Leck | SYNTH (Physik) |
| SuperESP-OS | fusionierte ESP32-Telemetrie → Gerätezustand + Verteilung | SYNTH (Chip-Telemetrie) |
| SuperESP-Power | Stromzangen-Energie/NILM → Lasttyp | SYNTH (Physik) |
| SuperESP-Occupancy | PIR+CO2+Schall → Raumbelegung | SYNTH (Physik) |
| SuperESP-Wearable | PPG+IMU → Herz-/Aktivitätszustand (nicht medizinisch) | SYNTH (Physik) |
| SuperESP-Water | Durchfluss+Druck+Feuchte → Leck/Überflutung | SYNTH (Physik) |

## Geschwindigkeit
- **Ternärer Kernel:** verzweigungsfreies 4-Trits/Byte-Matvec → **Klassifizierung 306 µs → 87 µs (3,5×)**, ~11.400/s
  auf dem Host (-O3). Kommt der gesamten Atome-Engine zugute (classify + generate + ESP32). Bit-Genauigkeit
  bleibt erhalten (Parität max. |Δ| 8,3e-7); alle 146 bestehenden Tests bestehen.
- **Änderungs-gegatetes Streaming** (`framework/streaming.py`): auf einem korrelierten, stets aktiven Strom nur dann
  das Modell erneut laufen lassen, wenn die Eingabe über einen Feuerungs-Schwellwert driftet; sonst die zwischengespeicherte
  Entscheidung wiederverwenden (bit-identisch zum Ausführen jedes Frames). Die Sprungrate ist der Gewinn (≈98 % auf einem statischen Strom).
- **Delta-Inferenz** (`framework/delta.py`): 4–11× weniger Matvec-Operationen auf korrelierten Strömen.
- Tok/s/RAM auf ESP32-Silizium **NICHT GEMESSEN** (kein Board); es wird erwartet, dass sich die Host-Speedups übertragen.

Für zurückgehaltene Genauigkeit, Abstention-AURC, Delta-Inferenz-Speedup und das
ECHT/SYNTH-Label pro Kopf siehe `HONEST_RESULTS.md` / `artifacts/RESULTS.json`.

## Wie es funktioniert
- **Tokenizer** (`framework/tokenize.py`): jeder Sensor-/Merkmalsframe wird linear
  zu einer Byte-Sequenz (≤32) quantisiert — sodass die bestehende Atome-Engine mit
  256-Byte-Vokabular unverändert läuft. Die Quantisierungskonstanten werden nur auf TRAIN gefittet (leckfrei).
- **Modell** (`framework/model.py`): die bestehende `AtomeLM`-Basis + ein ternärer
  Klassifizierungskopf über dem Final-Norm-Hidden des letzten Tokens — genau das, was das
  C-`atome_classify` berechnet. **Bit-genaue Python↔C-Parität** (max. |Δ| ~7e-7).
- **Abstention** (`framework/abstain.py`): ablehnen, wenn die Top1-Top2-Softmax-Marge
  niedrig ist; berichtet als Risiko-Coverage-Kurve + AURC vs. Orakel/Zufall.
- **Delta-Inferenz** (`framework/delta.py`): Integrate-and-Fire-Delta-Matvec für
  korrelierte Sensorströme — der gemessene Energie-Proxy aus dem
  delta_inference-Experiment, pro Kopf angewandt.
- **Attestierung** (`attest/sign.py`): Ed25519-signierte Quittung, die sha256(blob)
  + Metadaten bindet, sodass ein Deployer beweisen kann, dass DIESER exakte Kopf lief. Manipulationssicher (tamper-evident).
- **Laufzeit** (`runtime/dispatcher.py`): leitet einen Frame nach Modalität an seinen Kopf,
  führt den OS-Kopf auf fusionierter Telemetrie aus, wirft Last unter Fehlerzuständen ab. C-Spiegel:
  `c_engine/superesp/superesp_os.c`. Firmware-Skelett: `superesp/firmware/`.

## Installation
```
pip install -e .              # core (torch + numpy); run the CLI as: python3 -m superesp.cli <cmd>
pip install -e ".[superesp]"  # + cryptography/scipy/pyserial/esptool (attestation, audio, flashing)
```

## Jedes ESP32 flashen (kein ESP-IDF nötig — vorkompiliert für esp32/s2/s3/c3/c6/h2)
```
bash superesp/esp32/install.sh    # auto-detects the chip, flashes the matching
                                  # prebuilt firmware, runs all heads, writes a report
```

## Erstelle deinen EIGENEN Klassifizierer in Minuten (keine ML-Kenntnisse — die log→train→flash-Schleife)
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
**Die 9 SYNTH-Köpfe sind nur Standardwerte — vollständig austauschbar.** Trainiere unter einem
eingebauten Namen mit deinen eigenen Daten, um ihn durch ein reales Modell zu ersetzen:
`python3 -m superesp.cli train --csv my_field.csv --name agri` überschreibt den Blob des synthetischen `agri`-Kopfes.
Nichts ist hartcodiert; jeder Kopf ist "auf Daten trainieren → einen Blob exportieren".

## Reproduzieren / bring deine eigenen Daten mit
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
Jeder mit einer CSV seiner eigenen ESP32-Sensorfenster erhält einen bit-genauen, attestierbaren
Klassifizierer auf dem Gerät — ohne ML-Setup. Dies ist das offene/auditierbare Gegenstück zu einer
kommerziellen TinyML-Pipeline.

## Ehrlicher Umfang / Burggraben (moat)
Die einzelnen Köpfe sind echte angewandte Edge-KI (ein Schritt / ein Produkt), **keine Burggräben** —
TinyML-KWS/Geste/Anomalie sind überfüllt (TFLite-Micro, Edge Impulse). Der einzige
verteidigungsfähige Winkel ist die Kombination **ultrawinziges Ternär + bit-genau auditierbar +
kryptografisch attestiert + Delta-effizient** als ein einheitliches
OS auf dem Gerät. Das ist eine First-Mover-/Integrations-Wette, kein Sandbox-Burggraben. Köpfe,
die auf SYNTH-Daten trainiert sind, sind Physik-artige Platzhalter, als solche gekennzeichnet — keine
Feldeinsatz-Behauptungen. Durchsatz/RAM auf Silizium sind **NICHT GEMESSEN** (kein Board).
```
```
