[English](PROJECT_CONTENT.md) · **Français** · [Español](PROJECT_CONTENT.es.md) · [简体中文](PROJECT_CONTENT.zh-CN.md) · [Deutsch](PROJECT_CONTENT.de.md) · [日本語](PROJECT_CONTENT.ja.md) <!-- i18n-switcher -->

# PROJECT_CONTENT.md — Orientation du projet

À lire en premier. Une orientation d'environ 5 minutes pour quiconque (humain ou agent) arrive sur la base de code. Vous évite de casser les invariants porteurs auxquels ce kit tient.

---

## En bref (TL;DR)

**Atome LM** est un modèle de langage ternaire d'environ 60 K paramètres + un moteur d'inférence C99 qui l'exécute sur des microcontrôleurs bare-metal (RP2040, ESP32-C3, Cortex-M0). La pile d'entraînement Python et le moteur C sont conçus pour produire des passes forward **identiques au bit près** — cette parité est toute la raison d'être du projet.

- Licence : Apache 2.0
- Tests : `pytest -q` → attendez **146 passed, 0 skipped** (1 skip si `qemu-system-arm` est absent)
- Trois points de contrôle entraînés sont livrés dans `checkpoints/` : `atome_944k.bin` (blob empaqueté du moteur C de 271 Ko — le modèle de démo à 944K paramètres au format `ATOME01`), `atome_1m_v1.pt` (la source PyTorch qui l'a produit) et `vanilla_1m_v1.pt` (la référence GPT vanilla FP32 utilisée pour l'A/B de HONEST_RESULTS). Tout *autre* fichier correspondant à `*.pt`/`*.atome*`/`*.bin` est ignoré par git. Pour entraîner depuis zéro à la place, utilisez `scripts/train_demo.py` (~30 min CPU).

## Pourquoi ça existe

La plupart des « petits LM » sont de gros LM qui ont été compressés. Atome est façonné dès le départ par les contraintes MCU : la RAM est le coût contraignant, les poids ternaires suppriment les multiplications flottantes, trois voies (conv locale + SSM diagonal + attention parcimonieuse top-k) remplacent une pile transformer profonde, un routeur souple par jeton les mélange, et le tokeniseur d'octets évite de livrer un vocabulaire. L'affirmation intéressante n'est pas les primitives (toutes de l'état de l'art — BitNet, Mamba, attention top-k) — c'est la *combinaison, l'histoire de déploiement et l'évaluation honnête* montrant où cela gagne (60K) et où cela perd (944K). Le moteur C est sans tas (zero-heap), à tampons statiques, empreinte mémoire déterministe.

## Ce qu'un agent ne DOIT PAS casser

Ce sont des invariants porteurs. Vérifiez tout changement par rapport à eux avant de déclarer terminé.

1. **Parité exacte au bit près Python ↔ C.** La parité forward-unique est tout le produit. Tests : `tests/test_parity_with_c.py`, `tests/test_parity_multitoken.py`. Si vous changez le code du modèle, le format d'export ou les noyaux C, exécutez-les et confirmez qu'ils passent toujours.
2. **Zéro allocation de tas dans le moteur C.** `c_engine/upstream/atome.c` n'utilise que des tampons statiques dimensionnés par des macros `ATOME_*` à la compilation. N'introduisez jamais `malloc`/`calloc`/`free` ici. Les tableaux sur la pile sont acceptables.
3. **`weights_only=True` sur chaque `torch.load`.** Tous les points de contrôle du kit sont `{"config": dict, "state_dict": dict}` — des tenseurs purs + primitives. Charger avec `weights_only=False` est une RCE sur un fichier .pt malveillant. Ne régressez pas là-dessus.
4. **Aucune constante de modèle en dur dans l'exporteur.** `scripts/export_to_atome.py` lit `top_k` (et toute la config) depuis le point de contrôle et écrit la vraie valeur dans l'en-tête C. Ne codez pas de constantes en dur — il y a un test de non-régression dans `tests/test_export_format.py` qui le détectera.
5. **Vérifications de bornes dans `atome_predict_next` et `atome_generate`.** Les deux rejettent `n_tokens < 1`, `prompt_len < 1` et les pointeurs NULL avant toute indexation/memcpy. Ne les retirez pas — `state->x[n_tokens - 1]` est un comportement indéfini (UB) sans elles.
6. **Seuls les trois points de contrôle publiés sont livrés.** `checkpoints/atome_944k.bin`, `checkpoints/atome_1m_v1.pt` et `checkpoints/vanilla_1m_v1.pt` sont suivis et mis en liste blanche dans `.gitignore`. Tout *nouvel* artefact `*.pt`/`*.atome*`/`*.bin` est ignoré par git par défaut — n'ajoutez pas d'autres points de contrôle à la publication publique sans une entrée de liste blanche explicite et une raison.
7. **Honnêteté dans les benchmarks.** `HONEST_RESULTS.md` documente *à la fois* les victoires (~22 % de perplexité en mieux que vanilla FP32 à 60K params, 52 % en mieux à budget de flash égal) *et* les défaites (vanilla gagne d'environ 11 % à l'échelle 944K). Ne laissez pas discrètement tomber les défaites pour que les titres sonnent mieux.

## Carte des fichiers

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

## Vérifiez votre travail

```bash
# from repo root, after install.sh has run once
. .venv/bin/activate
pytest -q       # expect: 146 passed (or 145 + 1 skipped if no qemu-system-arm)
```

C'est le seul signal qui compte avant de déclarer terminé. Si vous changez quoi que ce soit dans `atome_llm/core/` ou `c_engine/upstream/`, ne sautez pas cette étape.

## Erreurs fréquentes des agents ici

- **Traiter le moteur C comme du remplissage.** Ce n'en est pas — chaque ligne est dimensionnée par la RAM/flash. N'ajoutez pas d'allocations, n'ajoutez pas de dépendances libc, n'ajoutez pas de `printf`. Tout l'intérêt est que cela tourne sur une puce à 2 $ avec des kilo-octets de RAM.
- **Essayer d'« améliorer » les nombres de paramètres ou de benchmark dans les docs sans relancer le balayage.** Les nombres 60K / 944K / 22 % / 52 % / -11 % dans `HONEST_RESULTS.md` sont liés à des runs reproductibles précis. Si vous ne pouvez pas reproduire, ne modifiez pas.
- **Ajouter des replis (fallbacks) de style ML (« if state is None, do X »).** Le runtime est déterministe — chaque chemin de code est exercé. Il n'y a pas de branches « ne devrait pas arriver ».
- **Généraliser le tokeniseur d'octets.** Il s'agit d'octets bruts intentionnellement. Ajouter BPE ou sentencepiece livrerait une table de vocabulaire (des kilo-octets de flash) et irait à l'encontre de la conception.
- **Empaqueter des idées expérimentales.** `c_engine/experiments/delta_inference/` est explicitement expérimental — pas sur le chemin pris en charge, pas testé pour la parité. Ne promouvez pas d'expériences dans `c_engine/upstream/` sans couverture de parité + vérification de bornes.
- **Toucher aux tests de parité « pour les faire passer ».** Si les tests de parité échouent, c'est le *code* qui est faux, pas le test. Trouvez la divergence Python/C — c'est presque toujours un décalage d'un cran dans l'orientation du noyau de conv, l'initialisation de l'état SSM, ou une constante périmée codée en dur.

## Ce qui est ouvert vs ce qui ne l'est pas

| Ouvert (ce dépôt, Apache 2.0)                       | Non ouvert (commercial)                        |
|-----------------------------------------------------|-----------------------------------------------|
| Architecture, code d'entraînement, moteur C         | Bring-up silicium (intégration par plateforme) |
| Poids entraînés 944K (`checkpoints/atome_944k.bin`) | Atome Secure Boot Pack (blobs `.atome` signés) |
| Source PyTorch `atome_1m_v1.pt` + référence vanilla | Durcissement par plateforme + flux d'attestation |
| Format d'export + tests de parité                   | Plus grand modèle interne V2 (3M params, multi-domaine) |
| Données d'exemple, harnais de balayage A/B          | Affinage personnalisé + intégration par client |
| Toute la doc (PAPER, HONEST_RESULTS, etc.)          | Marketing / site de démo en direct sur atomelm.com |

L'architecture est publique par conception et le coût d'entraînement est de ~1 à 2 $ — une stratégie licence-comme-douve n'allait jamais marcher, et poids-comme-douve aurait été mince. La vraie valeur défendable, c'est le travail d'intégration par déploiement, le durcissement de sécurité et le plus grand modèle V2 gardé propriétaire — dont rien ne se trouve dans ce dépôt.

## Si vous devez creuser davantage

- Justification de l'architecture : `PAPER.md`
- Ce qui est mesuré, ce qui ne l'est pas, ce qui a coûté quoi : `HONEST_RESULTS.md`
- Ce qui est encore en exploration : `FRONTIER.md`
- Comment reproduire les chiffres phares : `REPRODUCE.md`
- Comment passer de zéro à un modèle entraîné-et-exporté : `QUICKSTART.md`
