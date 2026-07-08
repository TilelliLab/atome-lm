[English](Q15_PROPOSAL.md) · **Français** · [Español](Q15_PROPOSAL.es.md) · [简体中文](Q15_PROPOSAL.zh-CN.md) · [Deutsch](Q15_PROPOSAL.de.md) · [日本語](Q15_PROPOSAL.ja.md) <!-- i18n-switcher -->

# Chemin d'activations Q15 — proposition de conception (NON implémentée)

## Pourquoi cela existe

Lors de la session d'émulateur du 10 mai, nous avons d'abord soupçonné que l'ordre
des opérations flottantes entre le softfloat ARM et le x86 hôte causait la dérive
multi-jetons. À l'examen, la cause réelle était un bug logique — `atome_predict_next`
ne réinitialisait jamais `state->ssm_h`, si bien que l'état SSM d'un appel précédent
polluait les passes forward ultérieures. Ce bug est maintenant corrigé (`atome.c:294-300`)
et 48/48 jetons QEMU correspondent à Python.

Mais Q15 vaut toujours la peine pour la **performance et l'énergie**, pas pour la
correction. Ce fichier fige la conception pour que la prochaine session puisse la
reprendre à froid.

## Ce que Q15 apporte (meilleures estimations, pas encore mesurées)

| Gain | Ampleur | Pourquoi |
|---|---|---|
| Accélération de calcul sur M0 / M3 | ~5-10× | Pas de FPU ; le multiply-accumulate entier est un cycle unique sur ARM v7-M |
| Accélération de calcul sur M4F / M7 | ~1.5-2× | A déjà un FPU ; le gain vient du SIMD (`__SADD16`, `SMLAD`) |
| Réduction du BSS | ~40-50% | Les tenseurs d'activation sont divisés par deux (fp32 → int16) |
| Puissance par jeton | ~3-5× plus bas | Évolue avec les cycles |
| Déterminisme entre hôtes | complet | L'arithmétique entière élimine l'ambiguïté de l'ordre d'arrondi |

## Ce que Q15 n'apporte PAS

- Un blob `.atome` plus petit — les poids sont déjà ternaires (~0,5 bit chacun).
  Les activations vivent en RAM, pas en flash.
- Une meilleure qualité de modèle — la quantification à l'inférence est avec perte ; attendez-vous
  à ce que la perplexité monte légèrement (probablement <5 % si calibrée ; nécessite mesure).

## Conception

### Interrupteur à la compilation

Ajouter `ATOME_DTYPE` sélectionnant `f32` (aujourd'hui, par défaut) ou `q15` (nouveau).
Les tests / firmware existants restent inchangés quand le drapeau est absent.

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

### Ce qui reste flottant

- LayerNorm (sqrt + division — un Q15-LayerNorm existe mais ajoute 200 LOC)
- Softmax (exp — idem)
- L'unique échelle d'attention `1.0 / sqrtf(d_h)`
- Les logits finaux (pour que l'argmax soit sans ambiguïté)

Ceux-ci représentent <2 % des cycles. Convertir vers/depuis Q15 à la frontière.

### Ce qui devient Q15

- Tous les matvecs ternaires (`atome_ternary_matvec`)
- La conv causale (`atome_causal_conv`)
- Le forward SSM (avec soin — `tanh(a)` et `b * x` nécessitent un traitement en virgule fixe)
- Le produit scalaire d'attention (Q.K)
- La somme pondérée d'attention (sum_i p_i * V_i)

### Suivi de l'échelle par tenseur

Chaque tenseur Q15 porte un décalage implicite. Maintenez un petit
`atome_q15_state_t` par pas avec les échelles courantes et mettez-le à jour à la volée :

```c
typedef struct {
    int x_shift;        /* current activation shift (Q15-pos) */
    int normed_shift;
    int path_local_shift;
    int path_ssm_shift;
    int path_attn_shift;
} atome_q15_state_t;
```

Script de calibration (côté Python) : faites passer quelques milliers d'invites dans le
modèle flottant, enregistrez l'activation absolue max par couche, réglez le décalage
pour que le 99,9e percentile tienne dans [-32768, 32767].

### Plan de test

1. Nouveau `tests/test_q15_parity.py` : référence flottante vs forward Q15.
   Tolérance : le logit top-1 doit correspondre pour >95 % des invites à d=64,
   similarité cosinus par jeton >0,98.
2. Nouvelle cible `c_engine/targets/cortex-m3-q15/`. Le firmware rapporte
   les cycles par jeton ; attendez-vous à 5-10× plus rapide que `cortex-m3-gen` à
   config identique.
3. Ajouter une ligne `q15` à `RAM_TABLE.md`. Attendu : la config tinystories tombe
   de 104 Ko de pic → ~55 Ko de pic. La F103 Blue Pill (2-4 $) devient
   atteignable pour le modèle entraîné.

## Effort estimé

| Phase | Effort | Risque |
|---|---|---|
| Calibration (Python) + export des échelles | demi-journée | faible |
| Chemin Q15 de `atome.c` (squelette + matvec + conv) | 1 jour | faible |
| SSM Q15 (table tanh + multiply-add mis à l'échelle) | demi-journée | moyen — soin numérique |
| Attention Q15 (Q·K, mise à l'échelle de l'entrée softmax) | demi-journée | moyen |
| Tests + cible firmware | demi-journée | faible |
| Réglage de la calibration + benchmarks | demi-journée | faible |
| **Total** | **~3-4 jours** | — |

## Quand y revenir

Après :
1. L'arrivée du point de contrôle à 1M params (`TRAIN_1M_RUNBOOK.md`) et nous avons un
   vrai modèle qui vaut la peine d'être optimisé en vitesse/puissance.
2. La validation sur silicium réel sur Nucleo-F411RE confirme que les chiffres QEMU
   d'aujourd'hui sont prédictifs.
3. Un utilisateur veut exécuter Atome sur F103 Blue Pill (2-4 $) — le palier
   le moins cher actuellement bloqué par la RAM à la config du modèle entraîné.

C'est un travail propre, cadré et autonome. Reprenez-le quand
l'une des conditions ci-dessus se réalise.
