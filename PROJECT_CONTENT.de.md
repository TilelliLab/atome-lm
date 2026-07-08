[English](PROJECT_CONTENT.md) · [Français](PROJECT_CONTENT.fr.md) · [Español](PROJECT_CONTENT.es.md) · [简体中文](PROJECT_CONTENT.zh-CN.md) · **Deutsch** · [日本語](PROJECT_CONTENT.ja.md) <!-- i18n-switcher -->

# PROJECT_CONTENT.md — Projekt-Orientierung

Lies dies zuerst. Eine ~5-minütige Orientierung für alle (Mensch oder Agent), die zur Codebasis kommen. Sie bewahrt dich davor, tragende Invarianten zu brechen, die diesem Kit wichtig sind.

---

## Kurzfassung (TL;DR)

**Atome LM** ist ein ternäres Sprachmodell mit ~60K Parametern + eine C99-Inferenz-Engine, die es auf Bare-Metal-Mikrocontrollern (RP2040, ESP32-C3, Cortex-M0) ausführt. Der Python-Trainingsstack und die C-Engine sind so entworfen, dass sie **bit-genau identische** Forward-Passes erzeugen — diese Parität ist der ganze Sinn des Projekts.

- Lizenz: Apache 2.0
- Tests: `pytest -q` → erwarte **146 passed, 0 skipped** (1 skip, falls `qemu-system-arm` fehlt)
- Drei trainierte Checkpoints werden in `checkpoints/` ausgeliefert: `atome_944k.bin` (271 KB gepackter C-Engine-Blob — das 944K-Parameter-Demo-Modell im `ATOME01`-Format), `atome_1m_v1.pt` (die PyTorch-Quelle, die ihn erzeugt hat) und `vanilla_1m_v1.pt` (die FP32-Vanilla-GPT-Baseline für das HONEST_RESULTS-A/B). Alles *andere*, das auf `*.pt`/`*.atome*`/`*.bin` passt, wird von git ignoriert. Um stattdessen von Grund auf zu trainieren, nutze `scripts/train_demo.py` (~30 Min. CPU).

## Warum es existiert

Die meisten "winzigen LMs" sind große LMs, die komprimiert wurden. Atome wird von Anfang an durch MCU-Einschränkungen geformt: RAM ist die bindende Kostengröße, ternäre Gewichte eliminieren Gleitkomma-Multiplikationen, drei Pfade (Local-Conv + diagonales SSM + Sparse-Top-k-Attention) ersetzen einen tiefen Transformer-Stack, ein weicher Router pro Token mischt sie, und der Byte-Tokenizer vermeidet das Ausliefern eines Vokabulars. Die interessante Behauptung sind nicht die Primitive (alles Stand der Technik — BitNet, Mamba, Top-k-Attention) — es ist die *Kombination, die Deployment-Geschichte und die ehrliche Evaluierung*, die zeigt, wo dies gewinnt (60K) und wo es verliert (944K). Die C-Engine ist Zero-Heap, statische Puffer, deterministischer Speicherbedarf.

## Was ein Agent NICHT brechen darf

Dies sind tragende Invarianten. Prüfe jede Änderung gegen sie, bevor du "fertig" meldest.

1. **Bit-genaue Python-↔-C-Parität.** Die Single-Forward-Parität ist das ganze Produkt. Tests: `tests/test_parity_with_c.py`, `tests/test_parity_multitoken.py`. Wenn du den Modellcode, das Exportformat oder die C-Kernel änderst, führe sie aus und bestätige, dass sie weiterhin bestehen.
2. **Null Heap-Allokation in der C-Engine.** `c_engine/upstream/atome.c` nutzt nur statische Puffer, die durch Kompilierzeit-`ATOME_*`-Makros dimensioniert sind. Führe hier niemals `malloc`/`calloc`/`free` ein. Arrays auf dem Stack sind in Ordnung.
3. **`weights_only=True` bei jedem `torch.load`.** Alle Kit-Checkpoints sind `{"config": dict, "state_dict": dict}` — reine Tensoren + Primitive. Laden mit `weights_only=False` ist RCE bei einer bösartigen .pt-Datei. Regressiere das nicht.
4. **Keine hartcodierten Modellkonstanten im Exporter.** `scripts/export_to_atome.py` liest `top_k` (und die gesamte Konfiguration) aus dem Checkpoint und schreibt den echten Wert in den C-Header. Hartcodiere keine Konstanten — es gibt einen Regressionstest in `tests/test_export_format.py`, der das abfängt.
5. **Grenzprüfungen in `atome_predict_next` und `atome_generate`.** Beide lehnen `n_tokens < 1`, `prompt_len < 1` und NULL-Zeiger vor jeder Indexierung/jedem memcpy ab. Entferne sie nicht — `state->x[n_tokens - 1]` ist ohne sie undefiniertes Verhalten (UB).
6. **Nur die drei veröffentlichten Checkpoints werden ausgeliefert.** `checkpoints/atome_944k.bin`, `checkpoints/atome_1m_v1.pt` und `checkpoints/vanilla_1m_v1.pt` werden getrackt und in `.gitignore` auf die Whitelist gesetzt. Jedes *neue* `*.pt`/`*.atome*`/`*.bin`-Artefakt wird standardmäßig von git ignoriert — füge der öffentlichen Veröffentlichung keine weiteren Checkpoints hinzu, ohne einen expliziten Whitelist-Eintrag und einen Grund.
7. **Ehrlichkeit bei Benchmarks.** `HONEST_RESULTS.md` dokumentiert *sowohl* Siege (~22 % bessere Perplexität als Vanilla FP32 bei 60K Parametern, 52 % besser bei gleichem Flash-Budget) *als auch* Niederlagen (Vanilla gewinnt um ~11 % im 944K-Maßstab). Lasse die Niederlagen nicht stillschweigend fallen, damit die Kernaussagen besser klingen.

## Dateikarte

```
atome-llm-kit/
├── README.md              ← user-facing intro
├── PAPER.md               ← architecture writeup
├── HONEST_RESULTS.md      ← what works, what doesn't, costs
├── FRONTIER.md            ← what's still being explored
├── QUICKSTART.md          ← 30-min train + export walkthrough
├── REPRODUCE.md           ← how to reproduce the headline benchmarks
├── LICENSE / NOTICE       ← Apache 2.0 + attribution
│
├── atome_llm/             ← Python package
│   ├── core/
│   │   ├── atome_lm.py       — main model
│   │   ├── mcu_block.py      — 3-pathway block
│   │   ├── router.py         — per-token soft router
│   │   ├── ssm.py            — diagonal SSM
│   │   ├── sparse_attention.py — top-k attention
│   │   └── ternary*.py       — ternary weight modules
│   ├── tokenize.py         — byte tokenizer (no BPE)
│   └── baselines/          — vanilla FP32 transformer for A/B
│
├── c_engine/upstream/     ← The C99 inference engine
│   ├── atome.c               — implementation (~600 lines, zero heap)
│   └── atome.h               — public API + compile-time macros
│
├── scripts/
│   ├── train_demo.py         — quick training (~30 min CPU)
│   ├── export_to_atome.py    — checkpoint → .atome binary + C header
│   ├── demo.py               — interactive REPL
│   ├── evaluate.py           — bits-per-byte eval
│   └── run_ab_sweep.py       — 60K param-fair / flash-fair A/B
│
└── tests/                 ← 146 tests, all expected to pass
    ├── test_parity_with_c.py        — single-forward Python ↔ C
    ├── test_parity_multitoken.py    — multi-token Python ↔ C
    ├── test_qemu_parity.py          — host C ↔ QEMU ARM (skips if QEMU missing)
    ├── test_export_format.py        — binary format + header generation
    └── test_*.py                    — model shape, router, SSM, ternary, etc.
```

## Überprüfe deine Arbeit

```bash
# from repo root, after install.sh has run once
. .venv/bin/activate
pytest -q       # expect: 146 passed (or 145 + 1 skipped if no qemu-system-arm)
```

Das ist das einzige Signal, das zählt, bevor man "fertig" erklärt. Wenn du irgendetwas in `atome_llm/core/` oder `c_engine/upstream/` änderst, überspringe diesen Schritt nicht.

## Häufige Wege, auf denen Agenten hier scheitern

- **Die C-Engine als Boilerplate behandeln.** Ist sie nicht — jede Zeile ist durch RAM/Flash dimensioniert. Füge keine Allokationen hinzu, füge keine libc-Abhängigkeiten hinzu, füge kein `printf` hinzu. Der ganze Sinn ist, dass dies auf einem 2-Dollar-Chip mit Kilobytes RAM läuft.
- **Versuchen, Parameterzahlen oder Benchmark-Zahlen in den Docs zu "verbessern", ohne den Sweep neu auszuführen.** Die Zahlen 60K / 944K / 22 % / 52 % / -11 % in `HONEST_RESULTS.md` sind an konkrete reproduzierbare Läufe gebunden. Wenn du nicht reproduzieren kannst, editiere nicht.
- **ML-artige Fallbacks hinzufügen ("if state is None, do X").** Die Laufzeit ist deterministisch — jeder Codepfad wird durchlaufen. Es gibt keine "sollte nicht passieren"-Zweige.
- **Den Byte-Tokenizer verallgemeinern.** Er sind absichtlich rohe Bytes. BPE oder sentencepiece hinzuzufügen würde eine Vokabeltabelle ausliefern (Kilobytes an Flash) und das Design zunichtemachen.
- **Experimentelle Ideen mit einbündeln.** `c_engine/experiments/delta_inference/` ist explizit experimentell — nicht auf dem unterstützten Pfad, nicht paritätsgetestet. Befördere Experimente nicht ohne Paritäts- + Grenzprüfungs-Abdeckung nach `c_engine/upstream/`.
- **Die Paritätstests anfassen, "um sie zum Bestehen zu bringen".** Wenn Paritätstests fehlschlagen, ist der *Code* falsch, nicht der Test. Finde die Python/C-Divergenz — es ist fast immer ein Off-by-One in der Conv-Kernel-Orientierung, der SSM-State-Initialisierung oder eine veraltete hartcodierte Konstante.

## Was offen ist vs. was nicht

| Offen (dieses Repo, Apache 2.0)                     | Nicht offen (kommerziell)                     |
|-----------------------------------------------------|-----------------------------------------------|
| Architektur, Trainingscode, C-Engine                | Silizium-Inbetriebnahme (plattformspez. Integration) |
| Trainierte 944K-Gewichte (`checkpoints/atome_944k.bin`) | Atome Secure Boot Pack (signierte `.atome`-Blobs) |
| PyTorch-Quelle `atome_1m_v1.pt` + Vanilla-Baseline  | Plattformspez. Härtung + Attestierungs-Flows  |
| Exportformat + Paritätstests                        | Größeres internes V2-Modell (3M Params, gemischte Domäne) |
| Beispieldaten, A/B-Sweep-Harness                    | Individuelles Feintuning + kundenspez. Integration |
| Alle Docs (PAPER, HONEST_RESULTS usw.)              | Marketing / Live-Demo-Site auf atomelm.com    |

Die Architektur ist bewusst öffentlich und die Trainingskosten betragen ~1–2 $ — eine Lizenz-als-Burggraben-Strategie hätte nie funktioniert, und Gewichte-als-Burggraben wäre dünn gewesen. Der eigentliche verteidigungsfähige Wert liegt in der Integrationsarbeit pro Deployment, der Sicherheitshärtung und dem größeren V2-Modell, das proprietär bleibt — nichts davon liegt in diesem Repo.

## Falls du tiefer graben musst

- Architektur-Begründung: `PAPER.md`
- Was gemessen ist, was nicht, was was gekostet hat: `HONEST_RESULTS.md`
- Was noch erforscht wird: `FRONTIER.md`
- Wie man die Kernzahlen reproduziert: `REPRODUCE.md`
- Wie man von null zu einem trainierten-und-exportierten Modell kommt: `QUICKSTART.md`
