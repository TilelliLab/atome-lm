[English](HONEST_RESULTS.md) · [Français](HONEST_RESULTS.fr.md) · [Español](HONEST_RESULTS.es.md) · [简体中文](HONEST_RESULTS.zh-CN.md) · **Deutsch** · [日本語](HONEST_RESULTS.ja.md) <!-- i18n-switcher -->

# Atome LM — Dossier ehrlicher Ergebnisse

> Eine Seite, kein Marketing. Was wir gemessen haben, auf welcher Hardware, mit welchem
> Seed. Wo wir Vanilla schlagen, wo nicht, wo wir es noch nicht wissen.

**Zuletzt aktualisiert.** 2026-05-13. Zusammengestellt aus `checkpoints/*.train.json`
und `ab_results.json` (das sind die tatsächlichen Lauf-Artefakte — öffne sie).

---

## Tabelle 1 — Die Zahlen, wie gemessen

| Konfig | Params | Bits/Gew | Verlust ↓ | PPL ↓ | Disk | Status |
|---|---:|---:|---:|---:|---:|---|
| **60K-Regime (MCU-Ziel)** | | | | | | |
| Atome ternär 3 Pfade | 60,800 | 1.58 | 1.84 | 6.31 | 15.1 KB¹ | ✅ gemessen |
| Vanilla GPT FP32 (Param-fair) | 60,808 | 32 | 2.09 | 8.12 | 237.5 KB | ✅ gemessen |
| Vanilla GPT FP32 (Flash-fair) | 5,968 | 32 | 2.57 | 13.10 | 23.3 KB | ✅ gemessen |
| **944K-Regime (Hochskalierung A/B)** | | | | | | |
| Atome ternär 3 Pfade | 944,640 | 1.58 | **1.0545** | 2.87 | 184 KB¹ | ✅ gemessen |
| Vanilla GPT FP32 (Param-fair) | 950,608 | 32 | **0.9337** | 2.54 | 3.7 MB | ✅ gemessen |
| Atome 3 Pfade, power3 (pro Tensor) | 944,640 | 2.81 | TBD | TBD | ~325 KB gesch. | ⏳ Launcher bereit |
| Atome 3 Pfade, power3 (α pro Zeile) | 944,640 | 2.81² | TBD | TBD | ~330 KB gesch. | ⏳ Launcher bereit |

¹ ATOME01, 4-Trits/Byte-Packung.  
² Der Anteil pro Tensor beträgt 2,81 Bits/Gew; das α pro Zeile fügt ein FP16 pro
Ausgabezeile hinzu (vernachlässigbarer %-Overhead bei 944K).

**Kernaussagen, unbereinigt:**

- Beim 60K-MCU-Ziel schlägt die ternäre 3-Pfad-Architektur Vanilla
  FP32 um **22 % bei der Perplexität bei gleicher Parameterzahl** und um **52 % bei
  gleichem Flash-Budget**.
- Bei 944K **verliert** reines Ternär gegen Vanilla FP32 um **11,4 % beim
  Validierungsverlust / 11,5 % bei der Perplexität**. Gleiches Rezept, gleicher Validierungs-Slice, gleicher Seed.
- Die Umkehrung bei 944K ist der wichtigste ehrliche Befund in diesem Kit.
  Er besagt: die induktive 3-Pfad-Verzerrung ersetzt Kapazität bei
  kleinem Maßstab und beschränkt sie bei größerem Maßstab. Atomes Wette ist das
  Kleinmodell-/MCU-Regime — nicht "winziges Ternär schlägt alles".

## Tabelle 2 — Wovon das 944K-Ergebnis abhängt

| Variable | Wert |
|---|---|
| Korpus | TinyStories vollständig (`train.txt + valid.txt` verkettet, ~1,7 GB roh) |
| Schritte | 30,000 |
| Sequenzlänge | 256 |
| Batch × Akkum | 64 × 4 |
| Optimierer | AdamW, lr=3e-4 → 3e-5 Kosinus, warmup=1000, weight_decay=0.1 |
| Präzision | BF16 autocast |
| Seed | 0 (einzelner Seed; Multi-Seed ausstehend) |
| Hardware | RunPod A100/A6000 (atome) — vast A100 (vanilla, 2026-05-11) |

## Tabelle 3 — Was wir NICHT gemessen haben

| Frage | Warum es wichtig ist | Kosten der Klärung |
|---|---|---|
| Multi-Seed-Varianz bei 944K | Ein einzelner Seed ist kein Befund | ~2 $ vast (3 Seeds × atome + vanilla) |
| Crossover-Punkt | Wo genau beginnt 3-Pfad zu verlieren? | ~8 $ vast (Sweep 100K / 300K / 600K / 1.5M) |
| Power-of-3 schließt die 944K-Lücke | Falls ja: die Kernaussage der Verlust-Umkehrung kippt | ~6 $ vast (der Launcher dieses Kits) |
| Q15-Festkomma-Inferenz-RAM | Das RP2040-RAM-Ziel wurde bei 944K verfehlt (Spitze 411 KB) | ~3 Tage Engineering |
| Durchsatz auf echtem Silizium | Alle MCU-Aussagen sind QEMU; macht aus "Frontier" ein "Fakt" | 0 $ (RP2040 liegt auf dem Schreibtisch) + ~1 Tag |
| Distillation von einem Vanilla-Lehrer | Ternäre Schüler schließen oft 80 %+ der Lücke zum Float-Lehrer | ~1–2 $ vast |
| Korpora mit breiterer Domäne | TinyStories begünstigt Modelle mit lokalem Muster | ~4 $ vast |

## Tabelle 4 — Was solide ist vs. was tragend-aber-dünn ist

**Solide (nicht ohne triftigen Grund ändern):**

- 146/146 Tests grün bei HEAD (16 davon power3-spezifisch).
- Bit-genaue Python-↔-C-↔-Cortex-M3-(QEMU)-Parität für einen einzelnen Forward
  (`tests/test_parity_with_c.py`, `tests/c_parity/parity_main.c`).
- Trainierte atome_1m_v1.pt- + vanilla_1m_v1.pt-Artefakte auf der Disk, beide
  mit vollständigen Trainingslogs in `checkpoints/*.train.json` (öffne sie — der Verlust
  jedes Schritts ist aufgezeichnet).
- 60K Param-fair / Flash-fair A/B reproduzierbar in ~30 Min. CPU
  (`scripts/run_ab_sweep.py`).

**Tragend, aber dünn:**

- Alle Kernzahlen sind Single-Seed.
- Die Multi-Token-C-Generierung hatte zuvor einen Bug mit SSM-State-Divergenz
  (Bug A). Behoben sowohl in Python als auch in der C-Engine: `atome_predict_next`
  setzt den SSM-Hidden-State zurück und leitet ihn bei jedem Aufruf aus dem vollständigen
  Token-Präfix neu ab (`c_engine/upstream/atome.c`). Multi-Token-
  Python↔C-Parität ist durch `tests/test_parity_multitoken.py` abgedeckt;
  die Single-Forward-Parität bleibt bit-genau über `tests/test_parity_with_c.py`.
- Die RP2040-Demo überschreitet derzeit 264 KB SRAM bei 944K — die MCU-Aussage
  ist regime-abhängig, und der Launcher in diesem Kit prüft, ob
  power3 das Parameterbudget genug einengt, um 944K wieder in Reichweite zu bringen
  (allein schafft er es nicht; braucht Q15 oder einen kleineren Hidden-State).

## Tabelle 5 — Kosten jeder bisher durchgeführten Messung

| Arbeit | Datum | Kosten | Ergebnis auf der Disk |
|---|---|---:|---|
| 60K A/B-Sweep | 2026-05-09 | 0 $ (CPU) | `ab_results.json` |
| 944K Atome | 2026-05-10 | ~0,40 $ (RunPod A40) | `atome_1m_v1.pt` |
| 944K Vanilla | 2026-05-11 | ~0,55 $ (Vast A100) | `vanilla_1m_v1.pt` |
| Power-3-Verdrahtung + Tests + CPU-Smoke | 2026-05-12/13 | 0 $ (CPU) | `atome_llm/core/power3.py` + 6 neue Tests |
| **Bisher insgesamt ausgegeben** | | **< 1,00 $** | — |
| Ausstehend: 944K A/B mit power3 + power3_pr | — | ~3,60–6,40 $ Deckel 8 $ | Launcher in `scripts/` |

## Belegdateien

Die trainierten 944K-Checkpoints und ihre Trainingslogs werden mit dem Kit ausgeliefert, sodass
jede berichtete Zahl Schritt für Schritt prüfbar *und* direkt neu evaluierbar ist:

- `checkpoints/atome_944k.bin` — gepackter C-Engine-Blob (ATOME01-Format).
- `checkpoints/atome_1m_v1.pt` — 944K-Atome-PyTorch-Quelle.
- `checkpoints/vanilla_1m_v1.pt` — 944K-Vanilla-FP32-Baseline (für die
  Umkehrung A/B oben).
- `checkpoints/atome_1m_v1.train.json` — Trainingslog alle 1000 Schritte.
- `checkpoints/vanilla_1m_v1.train.json` — dasselbe für die Vanilla-Baseline.
- `ab_results.json` — exakte 60K-A/B-Ergebniszeile.
- `FRONTIER.md` — Frontier-Beschreibung mit vollständiger 944K-Offenlegung.
- `PAPER.md` — Architektur-Beschreibung.
- `tests/` — 146 grüne Tests.

Der 60K-Sweep selbst (`checkpoints/ab_sweep/`) wird **nicht** ausgeliefert — das waren
24 wegwerfbare Trainingsläufe. Die Reproduktion des Sweeps dauert ~20 Minuten
CPU mit den enthaltenen `scripts/`.
