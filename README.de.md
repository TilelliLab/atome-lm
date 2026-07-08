[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · **Deutsch** · [日本語](README.ja.md) <!-- i18n-switcher -->

# Atome LM

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20518644.svg)](https://doi.org/10.5281/zenodo.20518644)
[![tests](https://github.com/TilelliLab/atome-lm/actions/workflows/test.yml/badge.svg)](https://github.com/TilelliLab/atome-lm/actions/workflows/test.yml)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Model-FFB020)](https://huggingface.co/TilelliLab/atome-lm)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

> Eine Referenzimplementierung eines gerouteten ternären, winzigen Sprachmodells mit
> einer bit-genauen Python-↔-C99-Inferenz-Engine, dimensioniert für RAM-Budgets der
> Mikrocontroller-Klasse.

Sprachmodell mit standardmäßig 60K Parametern, das drei bekannte Ideen zu einem
offenen Kit vereint: ternäre Gewichte (nach [BitNet b1.58](https://arxiv.org/abs/2402.17764)),
ein pro Token geroutetes hybrides SSM- + Sparse-Attention- + Local-Conv-Block
(nach [Hymba](https://arxiv.org/abs/2411.13676) und
[MossNet](https://arxiv.org/abs/2510.26182)),
sowie ein Byte-Tokenizer im ultrakleinen Maßstab
(nach [Guertler 2024](https://arxiv.org/abs/2405.14159)).
**Der Beitrag ist die Integration, nicht die Architektur**: ein vollständiger Pfad von
Training → ternärem Export → Basis-3-Packung → C99-Inferenz, mit bit-genauer
Python-↔-C-Parität, die durch Tests erzwungen wird.

**Schnelllinks:**
- 📄 Architektur-Beschreibung: [`PAPER.md`](PAPER.de.md)
- 🔬 Ehrliche Ergebnisse, inklusive der Umkehrung bei 944 K: [`HONEST_RESULTS.md`](HONEST_RESULTS.de.md)
- 🌐 Live-Demo im Browser (ohne Installation): [atomelm.com/demo.html](https://atomelm.com/demo.html)
- 🏠 Projekt-Startseite: [atomelm.com](https://atomelm.com)

**Hol dir das Kit:** Trainingscode, C-Engine, Benchmarks, Paper und trainierte
Gewichte — alles in diesem Repository, veröffentlicht unter der
[Apache-2.0-Lizenz](LICENSE). Trainiere deinen eigenen Checkpoint mit
`scripts/train_demo.py` in ~30 Min. auf einer CPU, oder führe den mitgelieferten
944 K-Checkpoint sofort aus.

**MCU-Status:** Die QEMU-ARM-Parität (Cortex-M3, MPS2-AN385) besteht bis zum
FP32-Epsilon, und eine reproduzierbare **Demo auf echtem Silizium** lässt den 944 K-Checkpoint
auf einem physischen **ESP32-WROOM-32** laufen — kohärenter Text, vollständig offline,
~1 Tok/s — siehe [`hardware/esp32-wroom32/`](hardware/esp32-wroom32/) (vorkompiliertes
Binary + serielles Log + Flashen mit einem Befehl). Diese Demo ist ein reiner
Ausführungsbeweis; die **Produktivierung** — das Atome Secure Boot Pack (signierte
`.atome`-Blobs, Dev/Prod-Flags, plattformspezifisches Secure-Boot, Attestierung), die
plattformspezifische Härtung — verkaufen wir als Integration auf
[atomelm.com](https://atomelm.com).

**Die Gewichte sind enthalten** in `checkpoints/`:

- `atome_944k.bin` (271 KB) — der gepackte C-Engine-Blob (`ATOME01`-Format),
  direkt von der Inferenz-Engine ladbar.
- `atome_1m_v1.pt` (3,7 MB) — der PyTorch-Quell-Checkpoint, der ihn erzeugt hat;
  nutze ihn zum Feintunen oder zum Re-Export mit anderen `#define`s.
- `vanilla_1m_v1.pt` (3,7 MB) — die FP32-Vanilla-GPT-Baseline, die für die
  944K-A/B-Umkehrung in [`HONEST_RESULTS.md`](HONEST_RESULTS.de.md) verwendet wurde;
  mitgeliefert, damit du den Vergleich Ende-zu-Ende reproduzieren kannst.

Der 944K-Checkpoint ist ein Forschungs-Demo-Artefakt, kein Produkt: er ist eng,
manchmal inkohärent und auf einem einzigen Korpus trainiert. Er ist hier,
um die Architektur *lauffähig* zu machen, nicht um eine Qualitätslatte zu setzen. Die
Reproduktion kostet ~1–2 $ an CPU/GPU mit dem enthaltenen Trainingscode; nichts in diesem
Kit ist eine Reproduktionsbarriere.

---

## Reproduzierbares Ergebnis, enges Regime

Auf TinyStories, 3000 Schritte, einzelner Seed: bei fester Parameterzahl erreicht Atomes
geroutet-ternärer Block **6,31 ppl vs. 8,12** für eine Vanilla-GPT-FP32-Baseline (−22 %);
bei festem Flash-Budget **6,31 vs. 13,10** (−52 %). Der Speicherplatz ist bei
Parameter-Gleichheit 16× kleiner (15,1 KB vs. 237,5 KB).

**Das Ergebnis kehrt sich bei 944 K Parametern um**, wo die Vanilla-FP32-Baseline um ~11 %
gewinnt. Atomes Wette liegt bewusst im Sub-1M-Regime der MCU-Klasse; darüber schließt die
Kapazitätsgrenze des Ternären die Lücke und überholt sie. Vollständige Reproduktion in
[`FRONTIER.md`](FRONTIER.de.md), vollständige ehrliche Lesart einschließlich der Umkehrung
in [`HONEST_RESULTS.md`](HONEST_RESULTS.de.md).

## Warum

Rechenzentrums-LLMs setzen Rechenzentrums-RAM voraus. Ein 2-Dollar-Mikrocontroller, der an einer Wand in einem entlegenen Sensor, einem Hörgerät, einem batteriebetriebenen Spielzeug oder einem Thermostat klebt, hat ihn nicht. Atome LM ist das Modelldesign-Ende dieser Einschränkung:

- **Ternäre Gewichte** (`{-α, 0, +α}` pro Tensor, BitNet-b1.58-Stil). Keine Gleitkomma-Multiplikationen im Matmul bei der Inferenz.
- **3-Pfad-Block** (depthwise Local-Conv, diagonales SSM, Top-k-Sparse-Attention), gemischt von einem weichen Router pro Token. So entworfen, dass er exakt der Struct der Atome-C99-Engine entspricht, sodass trainierte Checkpoints in den Flash exportiert werden und mit **bit-genauer Parität** zwischen Python und C laufen.
- **Byte-Tokenizer.** Keine BPE-Tabelle, die ausgeliefert werden muss.
- **Router-Entropie als Kalibrierungssignal.** Die Entropie der Router-Verteilung pro Token ist an jeder Position kostenlos beobachtbar. Im Engine-Standardmaßstab von Atome-LLM mit 60 K Parametern auf einem einzigen engen Korpus ist das Signal offengelegt, aber seine Kalibrierung als Unsicherheitsschätzer in diesem Maßstab wurde hier nicht gemessen. Wir haben *vorläufig* beobachtet (in einem größeren 3 M-Parameter-Modell, das **nicht Teil dieser Veröffentlichung ist**), dass die Entropie Eingaben außerhalb der Domäne verfolgt und mit dem Verlust pro Token korreliert — hier als noch nicht öffentliche Beobachtung berichtet, mit Messungen, die in einer künftigen Veröffentlichung folgen.

## Was es ist und was nicht

- **Ist:** die Python-Trainingsseite und die Architektur für ein ternäres LM, das auf Cent-Klasse-Hardware läuft.
- **Ist nicht:** ein Allzweck-Chatbot. In der Engine-Standardkonfiguration (`d_model=64`, `n_layers=4`) hat das Modell rund 60 K Parameter und exportiert zu etwa 20 KB Flash. Trainiere es eng — eine einzige Domäne (Embedded-System-Q&A, Kommandozeilenhilfe, ein einzelnes FAQ) — und es spricht flüssig innerhalb dieses Rahmens. In die Breite zu gehen erzeugt bei dieser Größe inkohärente Ausgaben; das spiegelt die Kapazität wider, nicht die Architektur. Für mehr Spielraum erhöhe `d_model` und `n_layers` (z. B. `d_model=128, n_layers=6` ≈ 600 K Parameter, ~150 KB gepackt) und re-exportiere mit den passenden `#define`s.

## Installation

```bash
./install.sh          # CPU-only venv + dependencies + environment check
```

Oder manuell: `pip install -e .` (Python ≥ 3.10, PyTorch ≥ 2.0). Neu hier?
[`QUICKSTART.md`](QUICKSTART.de.md) ist der 60-Sekunden-Pfad vom Klon zu einem
Mikrocontroller-fertigen Modell.

## Schnellstart

```python
import torch
from atome_llm.core.atome_lm import AtomeLM

# Defaults match the Atome C99 engine's compile-time #defines:
#   d_model=64, n_layers=4, d_head=16, top_k=4, kernel=5, vocab=256.
model = AtomeLM()
print(f"params: {model.parameter_count():,}")

ids = torch.randint(0, 256, (1, 32))
logits = model(ids)                     # (1, 32, 256)
loss = model.loss(ids[:, :-1], ids[:, 1:])

# Per-layer per-token uncertainty signal — no extra training:
ent_per_layer = model.router_entropies(ids)   # list of (B, L) tensors
```

## Eine winzige Demo trainieren

```bash
python scripts/train_demo.py --data path/to/text.txt --steps 1000 \
    --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt
```

Ein eingebautes `build_corpus.py` holt ein paar freizügig lizenzierte Quellen
(`tinystories`, `esp-idf`, `mcu-wikipedia`) für ein Smoke-Training:

```bash
python scripts/build_corpus.py --source tinystories --max-bytes 500000 \
    --output data/tinystories.txt
```

## Einen Checkpoint ausprobieren

```bash
python scripts/demo.py --checkpoint checkpoints/atome_demo.pt
# or, with no checkpoint, sanity-check the plumbing:
python scripts/demo.py --random --temperature 0.8 --top-p 0.9
```

Die REPL gibt die Fortsetzung und die Router-Entropie-Balken pro Schicht über dem
Prompt aus — das Metakognitionssignal, das kostenlos offengelegt wird.

## Sampling

`AtomeLM.generate(...)` verwendet standardmäßig gieriges Argmax (passend zum
`atome_predict_next` der C-Engine). Optionale Argumente `temperature`, `top_p`, `top_k`
und `generator=` aktivieren Nucleus-/Top-k-Sampling mit seed-basierter Reproduzierbarkeit.

## Benchmark

```bash
python scripts/benchmark.py            # tiny / default / large
```

CPU-Forward- + Generate-Latenz bei drei repräsentativen Konfigurationen. Nützlich als
Regressionsprüfung nach Architekturänderungen; keine MCU-Zahl.

## Export auf einen Mikrocontroller

```bash
python scripts/export_to_atome.py \
    --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome \
    --header
```

Dies erzeugt ein flaches `.atome`-Binary, das du aus C heraus `#include`en und mit
`atome_load(...)` aus der [Atome-C99-Engine](c_engine/) laden kannst. In der
Standardkonfiguration liegt das Binary deutlich unter 100 KB — passt bequem auf ESP32-S3,
STM32F4, RP2040, nRF52840, ESP32-C3.

## Architektur

```
x → LayerNorm → ┬─→ Local  (depthwise causal conv k=5)        ─→┐
                ├─→ State  (diagonal SSM, O(L))                 ─→ Σ → +x
                └─→ Sparse (top-k attention, O(L·k))            ─→┘
                        ↑              ↑
                        │              router weights r ∈ Δ per token
                        └──────────────┘
```

Drei Pfade. Drei verschiedene induktive Verzerrungen (inductive biases). Ein gemeinsamer Router pro Token, der lernt, welcher Pfad für jede Position am geeignetsten ist. Die Entropie pro Token des Routers wird auf jeder Schicht als kostenloses Unsicherheitssignal pro Position offengelegt.

Die vollständige Architektur-Geschichte steht in [`PAPER.md`](PAPER.de.md).

## Tests

```bash
pytest -q
```

## Lizenz

Apache License 2.0 — siehe [`LICENSE`](LICENSE) und [`NOTICE`](NOTICE).

Das Kit ist vollständig offen: nutze, modifiziere, verteile es weiter und liefere es in kommerziellen Produkten aus, ohne Gebühren pro Sitzplatz oder pro Gerät. Die Apache-2.0-Patentgewährung deckt die 3-Pfad-Geroutet-Ternär-Architektur ab, wie sie hier veröffentlicht ist.

Die veröffentlichten Checkpoints in `checkpoints/` (atome_944k.bin, atome_1m_v1.pt, vanilla_1m_v1.pt) stehen ebenfalls unter Apache-2.0. Sie sind Referenz-/Forschungsartefakte, keine Produkte. Kommerzielle Integration — Silizium-Inbetriebnahme, das Atome Secure Boot Pack (signierte `.atome`-Blobs, Dev/Prod-Flags, plattformspezifisches Secure-Boot, Attestierung), plattformspezifische Härtung, domänenspezifisches Feintuning des größeren internen V2-Modells — ist auf [atomelm.com](https://atomelm.com) erhältlich.

## Zitation

```bibtex
@software{atome_llm_2026,
  title  = {Atome LM: a tiny ternary language model for microcontroller deployment},
  author = {Atome LM contributors},
  year   = {2026},
  note   = {Apache 2.0, https://atomelm.com},
}
```
