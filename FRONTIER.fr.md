[English](FRONTIER.md) · **Français** · [Español](FRONTIER.es.md) · [简体中文](FRONTIER.zh-CN.md) · [Deutsch](FRONTIER.de.md) · [日本語](FRONTIER.ja.md) <!-- i18n-switcher -->

# Atome LM — Résultats de frontière

> **Mise à jour 2026-05-11 — l'A/B de montée en échelle à 944K renverse le titre.**
> Même recette, même tranche de validation, même audit d'équité, une référence GPT-FP32
> vanilla de 944K params (950 608 params, +0,63 % vs les 944 640 d'Atome) atteint
> une perte de validation de 0,9337 / ppl 2,54, battant l'Atome ternaire à 944K de 11,4 %
> en perte et de 11,5 % en perplexité. Les gains +22 % params-équit. / +52 %
> flash-équit. ci-dessous tiennent au **régime MCU 60K params** et à
> ce régime seulement. Au-delà de ~1M params, le biais inductif du bloc
> à 3 voies cesse de se substituer à la capacité et commence à la contraindre.
> Le cadrage honnête est : *le pari d'Atome, c'est le régime petit-modèle —
> sous-1M params, déploiement de classe MCU, sans réseau.* Voir
> [`HONEST_RESULTS.md`](HONEST_RESULTS.fr.md) pour la lecture complète du 944K.
> Multi-graines en attente.

**Date.** 2026-05-09. CPU seulement, pas de GPU.
**Matériel.** Machine CPU 4 threads. PyTorch 2.x, chemin de référence FP32.
**Corpus.** Tranche de validation TinyStories, 500 Ko UTF-8 (~99,9 % ASCII).
Split entraînement/éval 90/10 sur des morceaux de 64 octets → 7 030 morceaux d'entraînement /
782 morceaux tenus à l'écart (held-out).
**Optimiseur.** AdamW, lr 3e-4, batch 16, seq 64, 3 000 pas.
**Graine unique** (graine 0). Les résultats n'ont pas été répliqués sur plusieurs graines.

Ce document rapporte le premier A/B pommes-à-pommes entre l'architecture
ternaire à 3 voies d'Atome et les Transformers décodeur-seul vanilla
(FP32) à nombre de paramètres fixé et à budget de flash fixé. Le pair
publié le plus proche est le `Stories260K` d'Andrej Karpathy — un transformer
simple FP32 de 260 K paramètres entraîné sur TinyStories. L'affirmation de frontière
d'Atome est « moins de flash, meilleure qualité, moins de bits par poids, *et*
déployable sur un microcontrôleur à 2 $ ». Cette page teste les trois premières
de ces affirmations directement ; le déploiement MCU est vérifié séparément via
la parité exacte au bit près Python ↔ C ↔ Cortex-M3 (QEMU) (voir `tests/test_qemu_parity.py`).

## En bref (TL;DR)

| Modèle | Params | Bits/pds | Disque | bpb ↓ | Perplexité ↓ |
|---|---:|---:|---:|---:|---:|
| **Atome 3 voies, ternaire** | **60,800** | **1.58** | **15.1 KB**¹ / **17.2 KB**² | **2.66** | **6.31** |
| GPT vanilla, FP32 (params équit.) | 60,808 | 32 | 237.5 KB | 3.02 | 8.12 |
| GPT vanilla, FP32 (flash équit.) | 5,968 | 32 | 23.3 KB | 3.71 | 13.10 |

¹ ATOME01, 4 trits/octet (le moteur C actuel lit ce format).
² ATOME02, empaquetage base 3 à 5 trits/octet — 14,4 % plus petit, proche du
plancher théorique de l'information de `log2(3) ≈ 1,585` bits/trit. Encodeur +
décodeur Python livrés aujourd'hui ; le décodeur C est un changement futur.

## Ce que cela prouve

1. **À nombre de paramètres égal, l'architecture ternaire à 3 voies
   bat un transformer simple de 22 % en perplexité (6,31 vs 8,12)
   tout en utilisant 16× moins de disque.**

   La référence vanilla n'est *pas* sur-paramétrée — elle est appariée à
   60,8 K params (`d_model=44, n_layers=3, n_heads=4, d_ff=44`,
   sélectionnés par recherche exhaustive pour tomber à moins de 8 params de la
   cible). C'est la même architecture que tout article public de petit LM
   (`Stories260K`, l'article TinyStories, BitNet à petite échelle) utilise,
   aux détails près.

2. **À budget de flash égal, l'architecture ternaire à 3 voies bat
   un transformer simple de 52 % en perplexité (6,31 vs 13,10).**

   La référence vanilla flash-équitable est `d_model=8, n_layers=2,
   n_heads=4, d_ff=24`. Elle occupe le même budget disque de 20-25 Ko que
   le binaire Atome ATOME01 (15,1 Ko) et ATOME02 (17,2 Ko).

3. **Les poids 1,58 bit coûtent ~22 % de perplexité vs FP32 aux mêmes
   paramètres d'architecture** — mais la version FP32 coûte 16× plus de
   flash. Sur tout appareil où le flash est le goulot d'étranglement (chaque MCU que
   nous ciblons), le ternaire gagne. Sur tout appareil où le calcul est le
   goulot d'étranglement et le flash est gratuit (CPU serveurs), le FP32 gagne en qualité.

4. **L'empaquetage base 3 ATOME02 atteint 1,6 bit/trit — à moins de 1 % du
   plancher théorique de l'information de 1,585 bit/trit** — et réduit le
   binaire sur disque de 20,1 Ko à 17,2 Ko sur le même modèle entraîné de
   60,8 K params. Décodeur C encore en attente.

## Ce que cela ne prouve PAS

- **Graine unique seulement.** Les trois nombres sont sur la graine 0. Nous n'avons pas exécuté
  de multi-graines pour estimer la variance. Les écarts de 22 % / 52 % sont très
  grands comparés au bruit de graine typique à cette échelle, mais la variance
  n'est pas mesurée.
- **Corpus unique.** TinyStories est une cible indulgente — de courtes histoires
  au vocabulaire restreint. Des corpus à domaine plus large ou de code pourraient favoriser
  l'attention vanilla. Nous n'avons pas mesuré.
- **Horizon d'entraînement unique.** 3 000 pas, c'est bien en deçà de la
  convergence. Le classement relatif pourrait s'inverser ou s'amplifier avec plus
  d'entraînement. Un run de 10 K pas est en cours ; nous mettrons cette page à jour si cela
  change le titre.
- **Pas de vrai silicium.** Toutes les affirmations MCU sont vérifiées sur QEMU
  Cortex-M3, pas sur du matériel physique RP2040 / STM32. Les jetons/sec et
  les Joules/jeton sur silicium réel sont encore en attente.
- **Comparaison directe Stories260K encore en attente.** La configuration exacte de Karpathy
  est `Stories260K` à 260 K params + un vocabulaire SentencePiece de 32 K jetons. Notre
  tokeniseur d'octets + config 60 K est ~4× plus petit. Un vrai
  pommes-à-pommes vs `Stories260K` nécessiterait soit (a) de monter
  à 260 K params et un tokeniseur SentencePiece, soit (b) la configuration de
  Karpathy réentraînée à 60 K params avec un tokeniseur d'octets. Ni l'un ni l'autre n'est
  fait.

## Comparaison avec la frontière publiée

| Système | Plus petite cible | Params | Bits/pds | Vrai MCU ? | L'archi bat-elle vanilla ? |
|---|---|---:|---:|---|---|
| Microsoft BitNet b1.58 | CPU serveur | 700 M – 3 B | 1.58 | non | (à égalité à l'échelle) |
| Meta MobileLLM | smartphone | 125 M – 1 B | 4–8 | non | oui (vs vanilla de même taille) |
| Karpathy `Stories260K` | portable / navigateur | 260 K | 32 | pas de firmware | s/o (est la référence vanilla) |
| llama.cpp sur RP2040 (hobby) | RP2040 + SD | ~1 B (swappé) | 4 | oui (lent, requiert SD) | non mesuré |
| TFLite Micro / Edge Impulse | Cortex-M0+ | – | 8 | oui | pas de tâches langagières |
| **Atome LM (ce travail)** | **Cortex-M0+, 16 Ko SRAM** | **60 K** | **1.58** | **QEMU oui, silicium en attente** | **+22 % à params-équit., +52 % à flash-équit.** |

Plus petit, plus efficace en bits, *et* bat architecturalement vanilla aux
budgets que nous ciblons. À notre connaissance, le plus petit LM publié
où la victoire d'architecture routée a été mesurée directement contre
une référence vanilla au même budget de flash.

## Reproduire

```bash
# from the repository root
PYTHONPATH=. python3 scripts/build_corpus.py --source tinystories \
    --max-bytes 500000 --output data/tinystories.txt

PYTHONPATH=. python3 scripts/run_ab_sweep.py \
    --train data/tinystories.txt --steps 3000 \
    --output ab_results.json
```

`ab_results.json` contiendra les mêmes nombres que dans le tableau ci-dessus
(aux arrondis dépendants de la plateforme près dans les noyaux matmul de PyTorch).

## Questions ouvertes / prochaines poussées

- **A1.** Multi-graines (3 graines × 3 configs) pour estimer la variance sur les
  écarts de 22 % / 52 %.
- **A2.** Entraîner les trois à ≥ 10 K pas. L'écart se referme-t-il, tient-il,
  ou s'élargit-il ?
- **A3.** Ablation : laquelle des trois voies (conv locale, SSM
  diagonal, attention parcimonieuse top-k) porte la plus grande part de la victoire d'architecture ?
  Retirez chacune, mesurez.
- **A4.** Livrer un décodeur C pour ATOME02. Réduit le binaire de démo de
  20,1 Ko à 17,2 Ko sans changement de code ailleurs.
- **A5.** Vrai silicium. Flasher un RP2040 avec le moteur + ce ckpt de 60,8 K.
  Mesurer les jetons/sec, les Joules/jeton. **Le chiffre phare qui
  transforme l'affirmation de « frontière » en fait.**
- **A6.** Distillation depuis un fort LLM enseignant (10 Mo de texte de domaine
  étroit soigneusement produit par un modèle de pointe) dans le même Atome 60 K.
  Question ouverte : l'avantage d'architecture se compose-t-il sous la
  distillation ?
- **A7.** Correctif du Bug A (divergence SSM à prompt court entre `generate` Python
  ↔ `atome_generate` C). Touche le contrat de parité exacte au bit près
  — nécessite l'accord explicite de l'utilisateur.

## Fichiers de référence

- `ab_results.json` — nombres et config exacts du run rapporté ici.
- Les points de contrôle A/B entraînés (`atome_60k_ternary`, `vanilla_60k_fp32`,
  `vanilla_6k_fp32`) ne sont *pas* livrés — régénérez-les avec le harnais
  ci-dessous (ce kit s'entraîne depuis zéro).
- `atome_llm/baselines/vanilla_transformer.py` — la référence.
- `scripts/run_ab_sweep.py` — le harnais.
- `tests/test_vanilla_baseline.py` — 10 tests de cohérence sur la référence.
- `tests/test_export_packed.py` — 5 tests sur l'aller-retour ATOME02.
- `tests/test_trit_packing.py` — 11 tests sur l'empaqueteur base 3.
