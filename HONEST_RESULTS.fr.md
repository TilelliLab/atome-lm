[English](HONEST_RESULTS.md) · **Français** · [Español](HONEST_RESULTS.es.md) · [简体中文](HONEST_RESULTS.zh-CN.md) · [Deutsch](HONEST_RESULTS.de.md) · [日本語](HONEST_RESULTS.ja.md) <!-- i18n-switcher -->

# Atome LM — Dossier de résultats honnêtes

> Une page, sans marketing. Ce que nous avons mesuré, sur quel matériel, avec quelle
> graine. Où nous battons vanilla, où non, où nous ne savons pas encore.

**Dernière mise à jour.** 2026-05-13. Compilé depuis `checkpoints/*.train.json`
et `ab_results.json` (qui sont les artefacts réels des runs — ouvrez-les).

---

## Tableau 1 — Les chiffres, tels que mesurés

| Config | Params | Bits/pds | Perte ↓ | PPL ↓ | Disque | Statut |
|---|---:|---:|---:|---:|---:|---|
| **Régime 60K (cible MCU)** | | | | | | |
| Atome ternaire 3 voies | 60,800 | 1.58 | 1.84 | 6.31 | 15.1 KB¹ | ✅ mesuré |
| GPT vanilla FP32 (params équit.) | 60,808 | 32 | 2.09 | 8.12 | 237.5 KB | ✅ mesuré |
| GPT vanilla FP32 (flash équit.) | 5,968 | 32 | 2.57 | 13.10 | 23.3 KB | ✅ mesuré |
| **Régime 944K (montée en échelle A/B)** | | | | | | |
| Atome ternaire 3 voies | 944,640 | 1.58 | **1.0545** | 2.87 | 184 KB¹ | ✅ mesuré |
| GPT vanilla FP32 (params équit.) | 950,608 | 32 | **0.9337** | 2.54 | 3.7 MB | ✅ mesuré |
| Atome 3 voies, power3 (par tenseur) | 944,640 | 2.81 | TBD | TBD | ~325 KB est | ⏳ lanceur prêt |
| Atome 3 voies, power3 (α par ligne) | 944,640 | 2.81² | TBD | TBD | ~330 KB est | ⏳ lanceur prêt |

¹ ATOME01, empaquetage 4 trits/octet.  
² La portion par tenseur fait 2,81 bits/pds ; l'α par ligne ajoute un FP16 par ligne
de sortie (surcoût % négligeable à 944K).

**Points saillants, non aseptisés :**

- À la cible MCU 60K, l'architecture ternaire à 3 voies bat le vanilla
  FP32 de **22 % en perplexité à nombre de paramètres égal** et de **52 % à
  budget de flash égal**.
- À 944K, le ternaire simple **perd face au vanilla FP32 de 11,4 % en perte de
  validation / 11,5 % en perplexité**. Même recette, même tranche de validation, même graine.
- Le renversement à 944K est la conclusion honnête la plus importante de ce kit.
  Il dit : le biais inductif à 3 voies se substitue à la capacité à
  petite échelle et la contraint à plus grande échelle. Le pari d'Atome, c'est le
  régime petit-modèle / MCU — pas « le petit ternaire bat tout le monde ».

## Tableau 2 — Ce qui conditionne le résultat 944K

| Variable | Valeur |
|---|---|
| Corpus | TinyStories complet (`train.txt + valid.txt` concaténés, ~1,7 Go brut) |
| Pas | 30,000 |
| Longueur de séquence | 256 |
| Batch × accum | 64 × 4 |
| Optimiseur | AdamW, lr=3e-4 → 3e-5 cosinus, warmup=1000, weight_decay=0.1 |
| Précision | BF16 autocast |
| Graine | 0 (graine unique ; multi-graines en attente) |
| Matériel | RunPod A100/A6000 (atome) — vast A100 (vanilla, 2026-05-11) |

## Tableau 3 — Ce que nous n'avons PAS mesuré

| Question | Pourquoi c'est important | Coût pour résoudre |
|---|---|---|
| Variance multi-graines à 944K | Une graine unique n'est pas une conclusion | ~2 $ vast (3 graines × atome + vanilla) |
| Point de croisement | Où exactement le 3 voies commence-t-il à perdre ? | ~8 $ vast (balayage 100K / 300K / 600K / 1.5M) |
| Power-of-3 comble l'écart à 944K | Si oui : le titre du renversement de perte bascule | ~6 $ vast (le lanceur de ce kit) |
| RAM d'inférence en virgule fixe Q15 | La cible RAM du RP2040 a été manquée à 944K (pic 411 Ko) | ~3 jours d'ingénierie |
| Débit sur silicium réel | Toutes les affirmations MCU sont sous QEMU ; transforme « frontière » en « fait » | 0 $ (RP2040 sur le bureau) + ~1 jour |
| Distillation depuis un enseignant vanilla | Les élèves ternaires comblent souvent 80 %+ de l'écart avec l'enseignant flottant | ~1 à 2 $ vast |
| Corpus à domaine plus large | TinyStories favorise les modèles à motifs locaux | ~4 $ vast |

## Tableau 4 — Ce qui est solide vs ce qui est porteur-mais-mince

**Solide (ne pas changer sans forte raison) :**

- 146/146 tests au vert au HEAD (dont 16 spécifiques à power3).
- Parité exacte au bit près Python ↔ C ↔ Cortex-M3 (QEMU) pour un forward unique
  (`tests/test_parity_with_c.py`, `tests/c_parity/parity_main.c`).
- Artefacts atome_1m_v1.pt + vanilla_1m_v1.pt entraînés sur disque, tous deux
  avec des journaux d'entraînement complets dans `checkpoints/*.train.json` (ouvrez-les — la perte
  de chaque pas est enregistrée).
- A/B 60K params-équit. / flash-équit. reproductible en ~30 min CPU
  (`scripts/run_ab_sweep.py`).

**Porteur mais mince :**

- Tous les chiffres phares sont sur graine unique.
- La génération C multi-jetons souffrait auparavant d'un bug de divergence de l'état
  SSM (Bug A). Corrigé à la fois en Python et dans le moteur C : `atome_predict_next`
  réinitialise l'état caché du SSM et le redérive depuis le préfixe complet de jetons
  à chaque appel (`c_engine/upstream/atome.c`). La parité Python↔C multi-jetons
  est couverte par `tests/test_parity_multitoken.py` ; la parité forward-unique
  reste exacte au bit près via `tests/test_parity_with_c.py`.
- La démo RP2040 dépasse actuellement 264 Ko de SRAM à 944K — l'affirmation MCU
  dépend du régime, et le lanceur de ce kit teste si
  power3 réduit assez le budget de paramètres pour ramener 944K dans le périmètre
  (il ne le fait pas à lui seul ; nécessite Q15 ou un état caché plus petit).

## Tableau 5 — Coût de chaque mesure effectuée à ce jour

| Travail | Date | Coût | Résultat sur disque |
|---|---|---:|---|
| Balayage A/B 60K | 2026-05-09 | 0 $ (CPU) | `ab_results.json` |
| Atome 944K | 2026-05-10 | ~0,40 $ (RunPod A40) | `atome_1m_v1.pt` |
| Vanilla 944K | 2026-05-11 | ~0,55 $ (Vast A100) | `vanilla_1m_v1.pt` |
| Câblage Power-3 + tests + test CPU | 2026-05-12/13 | 0 $ (CPU) | `atome_llm/core/power3.py` + 6 nouveaux tests |
| **Total dépensé à ce jour** | | **< 1,00 $** | — |
| En attente : A/B 944K avec power3 + power3_pr | — | ~3,60–6,40 $ plafond 8 $ | lanceur dans `scripts/` |

## Fichiers de référence

Les points de contrôle 944K entraînés et leurs journaux d'entraînement sont livrés avec le kit, de sorte que
chaque chiffre rapporté est auditable pas à pas *et* réévaluable directement :

- `checkpoints/atome_944k.bin` — blob empaqueté du moteur C (format ATOME01).
- `checkpoints/atome_1m_v1.pt` — source PyTorch de l'Atome 944K.
- `checkpoints/vanilla_1m_v1.pt` — référence vanilla FP32 944K (pour le
  renversement A/B ci-dessus).
- `checkpoints/atome_1m_v1.train.json` — journal d'entraînement tous les 1000 pas.
- `checkpoints/vanilla_1m_v1.train.json` — idem pour la référence vanilla.
- `ab_results.json` — ligne de résultat A/B 60K exacte.
- `FRONTIER.md` — présentation de la frontière avec divulgation complète du 944K.
- `PAPER.md` — présentation de l'architecture.
- `tests/` — 146 tests au vert.

Le balayage 60K lui-même (`checkpoints/ab_sweep/`) n'est **pas** livré — c'était
24 runs d'entraînement jetables. Reproduire le balayage prend ~20 minutes
de CPU avec les `scripts/` inclus.
