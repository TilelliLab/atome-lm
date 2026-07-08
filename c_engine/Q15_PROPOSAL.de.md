[English](Q15_PROPOSAL.md) · [Français](Q15_PROPOSAL.fr.md) · [Español](Q15_PROPOSAL.es.md) · [简体中文](Q15_PROPOSAL.zh-CN.md) · **Deutsch** · [日本語](Q15_PROPOSAL.ja.md) <!-- i18n-switcher -->

# Q15-Aktivierungspfad — Design-Vorschlag (NICHT implementiert)

## Warum dies existiert

In der Emulator-Session am 10. Mai vermuteten wir zunächst, dass die Reihenfolge der
Gleitkomma-Operationen zwischen ARM-Softfloat und Host-x86 die Multi-Token-Drift
verursachte. Bei der Prüfung war die tatsächliche Ursache ein Logik-Bug — `atome_predict_next`
setzte `state->ssm_h` nie zurück, sodass der SSM-Zustand eines vorherigen Aufrufs spätere
Forward-Passes verunreinigte. Dieser Bug ist nun behoben (`atome.c:294-300`),
und 48/48 QEMU-Tokens stimmen mit Python überein.

Aber Q15 ist immer noch für **Performance und Energie** wert, nicht für die
Korrektheit. Diese Datei friert das Design ein, damit die nächste Session es kalt
aufgreifen kann.

## Was Q15 bringt (beste Schätzungen, noch nicht gemessen)

| Gewinn | Größenordnung | Warum |
|---|---|---|
| Rechenbeschleunigung auf M0 / M3 | ~5-10× | Kein FPU; Integer-Multiply-Accumulate ist ein einzelner Zyklus auf ARM v7-M |
| Rechenbeschleunigung auf M4F / M7 | ~1.5-2× | Hat bereits FPU; der Gewinn kommt von SIMD (`__SADD16`, `SMLAD`) |
| BSS-Reduktion | ~40-50% | Aktivierungstensoren halbieren sich (fp32 → int16) |
| Leistung pro Token | ~3-5× geringer | Skaliert mit den Zyklen |
| Determinismus über Hosts hinweg | vollständig | Integer-Arithmetik eliminiert die Mehrdeutigkeit der Rundungsreihenfolge |

## Was Q15 NICHT bringt

- Einen kleineren `.atome`-Blob — die Gewichte sind bereits ternär (~0,5 Bit je).
  Aktivierungen leben im RAM, nicht im Flash.
- Bessere Modellqualität — die Quantisierung bei der Inferenz ist verlustbehaftet; erwarte,
  dass die Perplexität leicht steigt (wahrscheinlich <5 %, falls kalibriert; braucht Messung).

## Design

### Kompilierzeit-Schalter

Füge `ATOME_DTYPE` hinzu, das `f32` (heute, Standard) oder `q15` (neu) auswählt.
Bestehende Tests / Firmware bleiben unverändert, wenn das Flag fehlt.

```c
#ifndef ATOME_DTYPE_Q15
#define ATOME_DTYPE_Q15 0
#endif

#if ATOME_DTYPE_Q15
typedef int16_t  atome_act_t;
typedef int32_t  atome_acc_t;
#else
typedef float    atome_act_t;
typedef float    atome_acc_t;
#endif
```

### Was Gleitkomma bleibt

- LayerNorm (sqrt + Division — ein Q15-LayerNorm existiert, fügt aber 200 LOC hinzu)
- Softmax (exp — dasselbe)
- Die einzelne Attention-Skalierung `1.0 / sqrtf(d_h)`
- Die finalen Logits (damit das Argmax eindeutig ist)

Diese machen <2 % der Zyklen aus. An der Grenze zu/von Q15 konvertieren.

### Was zu Q15 wird

- Alle ternären Matvecs (`atome_ternary_matvec`)
- Die kausale Conv (`atome_causal_conv`)
- Der SSM-Forward (mit Vorsicht — `tanh(a)` und `b * x` brauchen Festkomma-Behandlung)
- Das Attention-Skalarprodukt (Q.K)
- Die gewichtete Attention-Summe (sum_i p_i * V_i)

### Skalen-Tracking pro Tensor

Jeder Q15-Tensor trägt eine implizite Verschiebung. Halte ein kleines,
schrittweises `atome_q15_state_t` mit den aktuellen Skalen und aktualisiere es on the fly:

```c
typedef struct {
    int x_shift;        /* current activation shift (Q15-pos) */
    int normed_shift;
    int path_local_shift;
    int path_ssm_shift;
    int path_attn_shift;
} atome_q15_state_t;
```

Kalibrierungsskript (Python-Seite): lasse ein paar tausend Prompts durch das
Float-Modell laufen, zeichne die maximale absolute Aktivierung pro Schicht auf, setze die
Verschiebung so, dass das 99,9. Perzentil in [-32768, 32767] passt.

### Testplan

1. Neues `tests/test_q15_parity.py`: Float-Referenz vs. Q15-Forward.
   Toleranz: das Top-1-Logit muss für >95 % der Prompts bei d=64 übereinstimmen,
   Kosinus-Ähnlichkeit pro Token >0,98.
2. Neues `c_engine/targets/cortex-m3-q15/`-Target. Die Firmware berichtet
   Zyklen pro Token; erwarte 5-10× schneller als `cortex-m3-gen` bei
   identischer Konfig.
3. Füge eine `q15`-Zeile zu `RAM_TABLE.md` hinzu. Erwartet: die tinystories-Konfig fällt
   von 104 KB Spitze → ~55 KB Spitze. Das F103 Blue Pill (2-4 $) wird für das
   trainierte Modell erreichbar.

## Geschätzter Aufwand

| Phase | Aufwand | Risiko |
|---|---|---|
| Kalibrierung (Python) + Skalen-Export | halber Tag | niedrig |
| Q15-Pfad von `atome.c` (Skelett + matvec + conv) | 1 Tag | niedrig |
| SSM Q15 (tanh-Tabelle + skalierter Multiply-Add) | halber Tag | mittel — numerische Sorgfalt |
| Attention Q15 (Q·K, Softmax-Eingangsskalierung) | halber Tag | mittel |
| Tests + Firmware-Target | halber Tag | niedrig |
| Kalibrierungs-Tuning + Benchmarks | halber Tag | niedrig |
| **Gesamt** | **~3-4 Tage** | — |

## Wann erneut aufgreifen

Nach:
1. Dem Eintreffen des 1M-Parameter-Checkpoints (`TRAIN_1M_RUNBOOK.md`) und wir haben ein
   echtes Modell, das eine Optimierung auf Geschwindigkeit/Leistung wert ist.
2. Der Validierung auf echtem Silizium auf dem Nucleo-F411RE, die bestätigt, dass die
   heutigen QEMU-Zahlen prädiktiv sind.
3. Einem Nutzer, der Atome auf dem F103 Blue Pill (2-4 $) ausführen möchte — dem
   günstigsten Level, das derzeit durch RAM bei der Trainiert-Modell-Konfig blockiert ist.

Dies ist ein sauberes, abgegrenztes, in sich geschlossenes Arbeitspaket. Greife es auf, wenn
eine der obigen Bedingungen eintritt.
