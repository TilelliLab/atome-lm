[English](PAPER.md) · [Français](PAPER.fr.md) · [Español](PAPER.es.md) · [简体中文](PAPER.zh-CN.md) · **Deutsch** · [日本語](PAPER.ja.md) <!-- i18n-switcher -->

# Atome LM — Architektur für mikrocontroller-native ternäre Sprachmodelle

## 1. Motivation

Die kleinsten Sprachmodelle, die "wirklich sprechen", liegen heute im Bereich von 100 M–1 B Parametern. Jedes dieser Modelle benötigt mehr RAM und mehr Speicherbandbreite, als ein 2-Dollar-Mikrocontroller bieten kann. Die Architekturentscheidungen dieser Modelle — volle Attention, dichte FFNs, Multi-Bank-MoE, retrieval-augmentierte Pfade — sind Entscheidungen unter der Annahme, dass RAM billig ist. Atome LM geht von der gegenteiligen Annahme aus: RAM ist die Einschränkung, die jede andere Erwägung dominiert.

Das Ergebnis ist eine bewusst enge Architektur, die Ende-zu-Ende für die Kompatibilität mit einer C99-Inferenz-Engine mit fester Form entworfen wurde, die auf Chips mit Kilobytes — nicht Megabytes — an Arbeits-RAM läuft.

## 2. Einschränkungen durch die Engine

Die `atome_block_t`-Struct der Atome-C99-Engine ist festgelegt auf:

```
norm        : LayerNorm
local_conv  : depthwise causal conv, ternary kernel
ssm         : diagonal SSM (per-channel a, b, c_out, FP32)
attn        : top-k causal attention, ternary Q/K/V
router      : ternary linear → softmax over 3 pathways
```

Für jede dieser drei Pfad-Ausgaben sowie für den SSM-Hidden-State und den Attention-KV-Cache existieren statische Puffer. Es gibt keinen Puffer für eine breite Conv, keinen Puffer für ein dichtes FFN, keine Vorkehrung für Multi-Bank-Gewichte, keine Skalierung pro Zeile im ternären Kernel. Der Versuch, eine breitere Architektur zu trainieren und sie "später hineinzupassen", würde entweder erfordern, die C-Struct neu zu generieren (was den Vertrag der bit-genauen Parität bricht, auf dem dieses Projekt ruht), oder nicht unterstützte Pfade auszuliefern, die bei der Inferenz stillschweigend verworfen werden.

Atome LM entspricht daher exakt der Engine: drei Pfade, Skalierung pro Tensor, Byte-Tokenizer, kein Positions-Embedding, Sequenzlänge zur Kompilierzeit durch `ATOME_MAX_SEQ` gedeckelt.

## 3. Der Block

```
x → LayerNorm → ┬─→ Local   (depthwise causal conv, k=5)        ─→┐
                ├─→ State   (diagonal SSM, O(L))                  ─→ Σ → +x
                └─→ Sparse  (top-k attention, O(L·k))             ─→┘
                        ↑              ↑
                        │              router weights r ∈ Δ per token
                        └──────────────┘
```

Drei strukturell unterschiedliche Operationen:

| # | Name   | Operation               | Aufgabe                       |
|---|--------|-------------------------|------------------------------|
| 1 | Local  | Depthwise-Conv k=5      | Bigramme, Wortgrenzen         |
| 2 | State  | Diagonales SSM          | Themen-Übertrag über weite Distanz |
| 3 | Sparse | Top-k-Attention         | Koreferenz, exakter Abruf     |

Der Router ist ein `TernaryLinear(d_model, 3)`, gefolgt von Softmax. Er erzeugt eine 3-Wege-Verteilung pro Token; die Block-Ausgabe ist das Residuum plus die konvexe Kombination der Pfad-Ausgaben unter dieser Verteilung.

### 3.1 Router-Entropie als Kalibrierungssignal

Die Router-Verteilung pro Token trägt ein Unsicherheitssignal:

```
H(r_t) = − Σ_i r_t,i · log r_t,i,    bounded in [0, log 3] for 3 pathways
```

Hohe Entropie bedeutet, dass der Router nicht entscheiden konnte, welches Rechen-Primitiv für die Position am geeignetsten war. Das Signal ist strukturell — es erfordert kein unsicherheitsspezifisches Training und keine zusätzlichen Parameter. Im Engine-Standardmaßstab von Atome-LLM (60 K Parameter, einzelner enger Korpus) ist das Signal offengelegt, aber seine Kalibrierung als Unsicherheitsschätzer in diesem Maßstab wird hier nicht evaluiert. In einem größeren 3 M-Parameter-Modell, das **nicht in dieser Veröffentlichung enthalten ist**, haben wir *vorläufig* beobachtet, dass die Router-Entropie Eingaben außerhalb der Domäne verfolgt und mit dem Verlust pro Token korreliert; wir berichten dies nur als **noch nicht reproduzierbare Beobachtung** und beabsichtigen, die stützenden Messungen in einer künftigen Version zu veröffentlichen. Sie zu messen (z. B. der erwartete Kalibrierungsfehler zwischen Router-Entropie und Verlust pro Token) ist eine separate Übung.

`MCUBlock.router_entropy(x)` gibt die Entropie pro Token in Nats zurück. `AtomeLM.router_entropies(ids)` gibt die Entropie pro Schicht und pro Token als Liste von `(B, L)`-Tensoren zurück. Die `atome_state_t`-Struct der C-Engine legt das Router-Gewichts-Array pro Token `router_w[ATOME_MAX_SEQ][ATOME_N_PATHWAYS]` offen — die Entropie ist eine Summe/Log darüber.

## 4. Größen- und Formbudget

Bei den Standard-`#define`s der Engine (`d_model=64`, `n_layers=4`, `d_head=16`, `vocab=256`, `kernel=5`):

- Embedding: 256 × 64 = 16.384 Trits
- Pro Block: norm (256 FP32) + conv (64 × 5 Trits) + SSM (3 × 64 FP32) + Wq/Wk/Wv (16 × 64 + 16 × 64 + 64 × 64 Trits) + Router (3 × 64 Trits)
- Finale Norm: 128 FP32
- Unembed: 64 × 256 Trits

Mit 2 Bit pro Trit gepackt, liegt das Binary je nach Konfiguration in der Größenordnung von 30–60 KB. Bequem unter 100 KB für typische Standardwerte, weit unter dem 1 MB Flash eines Low-End-STM32 und um Größenordnungen kleiner als die 8 MB, die auf einem ESP32-S3 verfügbar sind.

Die RAM-Nutzung bei der Inferenz wird von den statischen Puffern in `atome_state_t` dominiert: `x`, `normed`, drei Pfad-Ausgabe-Scratch-Arrays, ein SSM-Hidden-State-Array pro Schicht, die KV-Caches, der Router-Gewichts-Puffer, der Logits-Puffer. Bei den Standardwerten ergibt das insgesamt ein paar KB.

## 5. Was nicht in dieser Veröffentlichung enthalten ist

- Kein Multi-Bank-Gewichts-MoE (die Engine unterstützt es nicht; es würde die bit-genaue Parität brechen).
- Keine ternäre Skalierung pro Zeile (derselbe Grund).
- Kein Positions-Embedding. Die Local-Conv und der SSM-Hidden-State kodieren die Position implizit innerhalb des Kompilierzeit-Sequenzfensters der Engine.
- Kein Retrieval-Pfad, kein episodischer Gedächtnispfad. Beide erfordern Off-Chip-Speicher oder große RAM-Scratch-Arrays, die mit der Zielhardware inkompatibel sind.

Dies sind bewusste Auslassungen, keine Lücken. Sie sind der Preis dafür, auf Hardware zu laufen, bei der RAM die bindende Einschränkung ist.

## 6. Einschränkungen

- **Maßstab.** Die Standardkonfiguration hat rund 60 K Parameter (`d_model=64`, `n_layers=4`). Trainiere sie eng auf einem fokussierten Korpus, und sie spricht flüssig im Rahmen; trainiere sie breit, und sie wird nicht kohärent sein. Das spiegelt die Kapazität wider, nicht die Architektur. Für mehr Spielraum erhöhe `d_model` und `n_layers` — z. B. `d_model=128`, `n_layers=6` sind rund 600 K Parameter.
- **Sequenzlänge.** Zur Kompilierzeit der Engine durch `ATOME_MAX_SEQ` gedeckelt (Standard 32). Für längere Generierung generiere Token für Token, indem du das wachsende Präfix an `atome_predict_next` übergibst — die Engine leitet den SSM-Hidden-State bei jedem Aufruf aus dem vollständigen Präfix neu ab, was die Python-↔-C-Parität deterministisch hält.
- **Tokenisierung.** Auf Byte-Ebene. UTF-8-Mehrbyte-Sequenzen kosten mehrere Positionen. Bei der Standard-`MAX_SEQ` der Engine nicht ideal für nicht-lateinische Schriften; erwäge, `ATOME_MAX_SEQ` zu erhöhen und neu zu exportieren, falls deine Zielschrift einen hohen mittleren Byte-pro-Zeichen-Wert hat.

## Referenzen

- Ma et al., 2024. *The Era of 1-bit LLMs: All Large Language Models are in 1.58 Bits.* arXiv:2402.17764.
- Wang et al., 2023. *BitNet: Scaling 1-bit Transformers for Large Language Models.* arXiv:2310.11453.
- Gu and Dao, 2023. *Mamba: Linear-Time Sequence Modeling with Selective State Spaces.* arXiv:2312.00752.
