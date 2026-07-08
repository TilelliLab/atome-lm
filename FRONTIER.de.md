[English](FRONTIER.md) · [Français](FRONTIER.fr.md) · [Español](FRONTIER.es.md) · [简体中文](FRONTIER.zh-CN.md) · **Deutsch** · [日本語](FRONTIER.ja.md) <!-- i18n-switcher -->

# Atome LM — Frontier-Befunde

> **Update 2026-05-11 — das Hochskalierungs-A/B bei 944K kehrt die Kernaussage um.**
> Gleiches Rezept, gleicher Validierungs-Slice, gleiches Fairness-Audit, eine 944K-Parameter-
> Vanilla-GPT-FP32-Baseline (950.608 Parameter, +0,63 % vs. Atomes 944.640) erreicht
> Validierungsverlust 0,9337 / ppl 2,54 und schlägt Atome-Ternär bei 944K um 11,4 %
> beim Verlust und 11,5 % bei der Perplexität. Die Gewinne +22 % Param-fair / +52 %
> Flash-fair weiter unten gelten im **60K-Parameter-MCU-Regime** und nur in
> diesem Regime. Über ~1M Parameter hinaus hört die induktive Verzerrung des
> 3-Pfad-Blocks auf, Kapazität zu ersetzen, und beginnt, sie zu beschränken.
> Die ehrliche Einordnung lautet: *Atomes Wette ist das Kleinmodell-Regime —
> Sub-1M-Parameter, Deployment der MCU-Klasse, ohne Netzwerk.* Siehe
> [`HONEST_RESULTS.md`](HONEST_RESULTS.de.md) für die vollständige 944K-Lesart.
> Multi-Seed ausstehend.

**Datum.** 2026-05-09. Nur CPU, keine GPU.
**Hardware.** 4-Thread-CPU-Box. PyTorch 2.x, FP32-Referenzpfad.
**Korpus.** TinyStories-Validierungs-Slice, 500 KB UTF-8 (~99,9 % ASCII).
Train/Eval-Split 90/10 über 64-Byte-Chunks → 7.030 Train-Chunks /
782 zurückgehaltene (held-out) Chunks.
**Optimierer.** AdamW, lr 3e-4, batch 16, seq 64, 3.000 Schritte.
**Einzelner Seed** (Seed 0). Die Ergebnisse wurden nicht über Seeds hinweg repliziert.

Dieses Dokument berichtet das erste Äpfel-mit-Äpfel-A/B zwischen Atomes
ternärer 3-Pfad-Architektur und Vanilla-Decoder-only-Transformern
(FP32) bei fester Parameterzahl und festem Flash-Budget. Der nächste
veröffentlichte Peer ist Andrej Karpathys `Stories260K` — ein einfacher
FP32-Transformer mit 260 K Parametern, trainiert auf TinyStories. Atomes Frontier-
Behauptung lautet "weniger Flash, bessere Qualität, weniger Bits pro Gewicht, *und*
einsetzbar auf einem 2-Dollar-Mikrocontroller". Diese Seite prüft die ersten drei
dieser Behauptungen direkt; das MCU-Deployment wird separat über
bit-genaue Python-↔-C-↔-Cortex-M3-(QEMU)-Parität verifiziert (siehe `tests/test_qemu_parity.py`).

## Kurzfassung (TL;DR)

| Modell | Params | Bits/Gew | Disk | bpb ↓ | Perplexität ↓ |
|---|---:|---:|---:|---:|---:|
| **Atome 3 Pfade, ternär** | **60,800** | **1.58** | **15.1 KB**¹ / **17.2 KB**² | **2.66** | **6.31** |
| Vanilla GPT, FP32 (Param-fair) | 60,808 | 32 | 237.5 KB | 3.02 | 8.12 |
| Vanilla GPT, FP32 (Flash-fair) | 5,968 | 32 | 23.3 KB | 3.71 | 13.10 |

¹ ATOME01, 4 Trits/Byte (die aktuelle C-Engine liest dies).
² ATOME02, Basis-3-Packung mit 5 Trits/Byte — 14,4 % kleiner, nahe der
informationstheoretischen Untergrenze von `log2(3) ≈ 1,585` Bits/Trit. Python-
Encoder + Decoder heute ausgeliefert; der C-Decoder ist eine künftige Änderung.

## Was dies beweist

1. **Bei gleicher Parameterzahl schlägt die ternäre 3-Pfad-Architektur
   einen einfachen Transformer um 22 % bei der Perplexität (6,31 vs. 8,12)
   und nutzt dabei 16× weniger Disk.**

   Die Vanilla-Baseline ist *nicht* überparametrisiert — sie ist auf
   60,8 K Params abgestimmt (`d_model=44, n_layers=3, n_heads=4, d_ff=44`,
   per Brute-Force-Suche ausgewählt, um innerhalb von 8 Params am Ziel
   zu landen). Das ist dieselbe Architektur, die jedes öffentliche Tiny-LM-Paper
   (`Stories260K`, das TinyStories-Paper, BitNet im kleinen Maßstab) verwendet,
   Trivialitäten ausgenommen.

2. **Bei gleichem Flash-Budget schlägt die ternäre 3-Pfad-Architektur
   einen einfachen Transformer um 52 % bei der Perplexität (6,31 vs. 13,10).**

   Die Flash-faire Vanilla-Baseline ist `d_model=8, n_layers=2,
   n_heads=4, d_ff=24`. Sie sitzt im selben 20–25 KB-Disk-Budget wie
   das Atome-ATOME01-Binary (15,1 KB) und das ATOME02-Binary (17,2 KB).

3. **Die 1,58-Bit-Gewichte kosten ~22 % Perplexität vs. FP32 bei denselben
   Architekturparametern** — aber die FP32-Version kostet 16× mehr
   Flash. Auf jedem Gerät, bei dem Flash der Engpass ist (jeder MCU, den
   wir anvisieren), gewinnt Ternär. Auf jedem Gerät, bei dem Rechenleistung der
   Engpass ist und Flash frei ist (Server-CPUs), gewinnt FP32 bei der Qualität.

4. **Die ATOME02-Basis-3-Packung erreicht 1,6 Bit/Trit — innerhalb von 1 % der
   informationstheoretischen Untergrenze von 1,585 Bit/Trit** — und reduziert das
   Disk-Binary von 20,1 KB auf 17,2 KB beim selben trainierten
   60,8 K-Parameter-Modell. C-Decoder noch ausstehend.

## Was dies NICHT beweist

- **Nur einzelner Seed.** Alle drei Zahlen sind Seed 0. Wir haben noch kein
  Multi-Seed ausgeführt, um die Varianz zu schätzen. Die Lücken von 22 % / 52 % sind
  sehr groß im Vergleich zum typischen Seed-Rauschen in diesem Maßstab, aber die Varianz
  ist ungemessen.
- **Einzelner Korpus.** TinyStories ist ein nachsichtiges Ziel — kurze Geschichten
  mit eingeschränktem Vokabular. Breitere Domänen- oder Code-Korpora könnten
  Vanilla-Attention begünstigen. Wir haben es nicht gemessen.
- **Einzelner Trainingshorizont.** 3.000 Schritte liegen weit unterhalb der
  Konvergenz. Die relative Rangfolge könnte sich mit mehr Training
  vertauschen oder verstärken. Ein 10 K-Schritt-Lauf läuft; wir aktualisieren diese Seite, falls er
  die Kernaussage ändert.
- **Kein echtes Silizium.** Alle MCU-Aussagen sind auf QEMU
  Cortex-M3 verifiziert, nicht auf physischer RP2040- / STM32-Hardware. Tokens/Sek. und
  Joule/Token auf echtem Silizium stehen noch aus.
- **Direkter Stories260K-Vergleich noch ausstehend.** Karpathys exaktes
  Setup ist `Stories260K` bei 260 K Params + ein 32 K-Token-SentencePiece-
  Vokabular. Unser Byte-Tokenizer + 60 K-Konfig ist ~4× kleiner. Ein echtes
  Äpfel-mit-Äpfel vs. `Stories260K` bräuchte entweder (a) dass wir
  auf 260 K Params und einen SentencePiece-Tokenizer hochskalieren, oder (b) Karpathys
  Setup, neu trainiert bei 60 K Params mit einem Byte-Tokenizer. Keines ist
  erledigt.

## Vergleich mit der veröffentlichten Frontier

| System | Kleinstes Ziel | Params | Bits/Gew | Echter MCU? | Schlägt Architektur Vanilla? |
|---|---|---:|---:|---|---|
| Microsoft BitNet b1.58 | Server-CPU | 700 M – 3 B | 1.58 | nein | (gleichauf im Maßstab) |
| Meta MobileLLM | Smartphone | 125 M – 1 B | 4–8 | nein | ja (vs. Vanilla gleicher Größe) |
| Karpathy `Stories260K` | Laptop / Browser | 260 K | 32 | keine Firmware | k.A. (ist die Vanilla-Baseline) |
| llama.cpp auf RP2040 (Hobby) | RP2040 + SD | ~1 B (ausgelagert) | 4 | ja (langsam, braucht SD) | nicht gemessen |
| TFLite Micro / Edge Impulse | Cortex-M0+ | – | 8 | ja | keine Sprachaufgaben |
| **Atome LM (diese Arbeit)** | **Cortex-M0+, 16 KB SRAM** | **60 K** | **1.58** | **QEMU ja, Silizium ausstehend** | **+22 % bei Param-fair, +52 % bei Flash-fair** |

Kleiner, bit-effizienter *und* schlägt Vanilla architektonisch bei den
Budgets, die wir anvisieren. Nach unserem Wissen das kleinste veröffentlichte LM,
bei dem der Sieg der gerouteten Architektur direkt gegen
eine Vanilla-Baseline bei gleichem Flash-Budget gemessen wurde.

## Reproduzieren

```bash
# from the repository root
PYTHONPATH=. python3 scripts/build_corpus.py --source tinystories \
    --max-bytes 500000 --output data/tinystories.txt

PYTHONPATH=. python3 scripts/run_ab_sweep.py \
    --train data/tinystories.txt --steps 3000 \
    --output ab_results.json
```

`ab_results.json` wird dieselben Zahlen enthalten wie in der Tabelle oben
(bis auf plattformabhängige Rundung in PyTorchs Matmul-Kerneln).

## Offene Fragen / nächste Vorstöße

- **A1.** Multi-Seed (3 Seeds × 3 Konfigs), um die Varianz bei den
  Lücken von 22 % / 52 % zu schätzen.
- **A2.** Alle drei auf ≥ 10 K Schritte trainieren. Schließt sich die Lücke, hält sie,
  oder weitet sie sich?
- **A3.** Ablation: welcher der drei Pfade (Local-Conv, diagonales
  SSM, Sparse-Top-k-Attention) trägt den größten Teil des Architektur-Siegs?
  Lasse jeden weg, miss.
- **A4.** Einen C-Decoder für ATOME02 ausliefern. Kürzt das Demo-Binary von
  20,1 KB auf 17,2 KB ohne Codeänderungen anderswo.
- **A5.** Echtes Silizium. Einen RP2040 mit der Engine + diesem 60,8 K-ckpt flashen.
  Tokens/Sek., Joule/Token messen. **Die Kernzahl, die
  die Behauptung von "Frontier" in ein Fakt verwandelt.**
- **A6.** Distillation von einem starken LLM-Lehrer (10 MB kuratierten
  engdomänen Textes, generiert von einem Frontier-Modell) in dasselbe 60 K-Atome.
  Offene Frage: verstärkt sich der Architekturvorteil unter der
  Distillation?
- **A7.** Bug-A-Fix (Python `generate` ↔ C `atome_generate`
  Kurz-Prompt-SSM-Divergenz). Berührt den Vertrag der bit-genauen
  Parität — braucht die ausdrückliche Zustimmung des Nutzers.

## Belegdateien

- `ab_results.json` — exakte Zahlen und Konfig des hier berichteten Laufs.
- Trainierte A/B-Checkpoints (`atome_60k_ternary`, `vanilla_60k_fp32`,
  `vanilla_6k_fp32`) werden *nicht* ausgeliefert — regeneriere sie mit dem Harness
  unten (dieses Kit trainiert von Grund auf).
- `atome_llm/baselines/vanilla_transformer.py` — die Baseline.
- `scripts/run_ab_sweep.py` — der Harness.
- `tests/test_vanilla_baseline.py` — 10 Sanity-Tests auf der Baseline.
- `tests/test_export_packed.py` — 5 Tests zum ATOME02-Roundtrip.
- `tests/test_trit_packing.py` — 11 Tests zum Basis-3-Packer.
