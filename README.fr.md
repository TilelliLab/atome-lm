[English](README.md) · **Français** · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# Atome LM

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20518644.svg)](https://doi.org/10.5281/zenodo.20518644)
[![tests](https://github.com/TilelliLab/atome-lm/actions/workflows/test.yml/badge.svg)](https://github.com/TilelliLab/atome-lm/actions/workflows/test.yml)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Model-FFB020)](https://huggingface.co/TilelliLab/atome-lm)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

> Une implémentation de référence d'un modèle de langage minuscule à pondérations
> ternaires et routage, doté d'un moteur d'inférence Python ↔ C99 exact au bit près,
> dimensionné pour les budgets de RAM de la classe microcontrôleur.

Modèle de langage de 60 K paramètres par défaut, combinant trois idées connues en un
seul kit ouvert : des poids ternaires (d'après [BitNet b1.58](https://arxiv.org/abs/2402.17764)),
un bloc hybride SSM + attention parcimonieuse + convolution locale routé par jeton
(d'après [Hymba](https://arxiv.org/abs/2411.13676) et
[MossNet](https://arxiv.org/abs/2510.26182)),
et un tokeniseur d'octets à échelle ultra-réduite
(d'après [Guertler 2024](https://arxiv.org/abs/2405.14159)).
**La contribution, c'est l'intégration, pas l'architecture** : un chemin complet
entraînement → export ternaire → empaquetage en base 3 → inférence C99, avec une parité
Python ↔ C exacte au bit près, garantie par les tests.

**Liens rapides :**
- 📄 Présentation de l'architecture : [`PAPER.md`](PAPER.fr.md)
- 🔬 Résultats honnêtes, y compris le renversement à 944 K : [`HONEST_RESULTS.md`](HONEST_RESULTS.fr.md)
- 🌐 Démo en direct dans le navigateur (sans installation) : [atomelm.com/demo.html](https://atomelm.com/demo.html)
- 🏠 Page d'accueil du projet : [atomelm.com](https://atomelm.com)

**Récupérer le kit :** code d'entraînement, moteur C, benchmarks, article, et poids
entraînés — tout est dans ce dépôt, publié sous
[licence Apache 2.0](LICENSE). Entraînez votre propre point de contrôle avec
`scripts/train_demo.py` en ~30 min sur un CPU, ou exécutez immédiatement le point de
contrôle 944 K fourni.

**État MCU :** la parité QEMU ARM (Cortex-M3, MPS2-AN385) passe jusqu'à l'epsilon FP32,
et une **démo reproductible sur silicium réel** exécute le point de contrôle 944 K sur un
**ESP32-WROOM-32** physique — texte cohérent, entièrement hors ligne, ~1 tok/s — voir
[`hardware/esp32-wroom32/`](hardware/esp32-wroom32/) (binaire précompilé + journal série +
flash en une commande). Cette démo est une simple preuve d'exécution ; la **mise en
production** — l'Atome Secure Boot Pack (blobs `.atome` signés, drapeaux dev/prod,
secure-boot par plateforme, attestation), le durcissement par plateforme — nous la vendons
en tant qu'intégration sur [atomelm.com](https://atomelm.com).

**Les poids sont inclus** dans `checkpoints/` :

- `atome_944k.bin` (271 Ko) — le blob empaqueté du moteur C (format `ATOME01`),
  chargeable directement par le moteur d'inférence.
- `atome_1m_v1.pt` (3,7 Mo) — le point de contrôle source PyTorch qui l'a produit ;
  à utiliser pour affiner (fine-tune) ou ré-exporter avec d'autres `#define`.
- `vanilla_1m_v1.pt` (3,7 Mo) — la référence GPT vanilla FP32 utilisée pour
  le renversement A/B à 944 K dans [`HONEST_RESULTS.md`](HONEST_RESULTS.fr.md) ;
  livrée pour que vous puissiez reproduire la comparaison de bout en bout.

Le point de contrôle 944 K est un artefact de démonstration pour la recherche, pas un
produit : il est étroit, parfois incohérent, et entraîné sur un unique corpus. Il est là
pour rendre l'architecture *exécutable*, pas pour fixer un niveau de qualité. Sa
reproduction coûte ~1 à 2 $ de CPU/GPU avec le code d'entraînement inclus ; rien dans ce
kit ne constitue une barrière à la reproduction.

---

## Résultat reproductible, régime étroit

Sur TinyStories, 3000 pas, une seule graine : à nombre de paramètres fixé, le bloc
routé-ternaire d'Atome atteint **6,31 ppl contre 8,12** pour une référence GPT-FP32
vanilla (−22 %) ; à budget de flash fixé, **6,31 contre 13,10** (−52 %). L'empreinte
disque est 16× plus petite à paramètres égaux (15,1 Ko contre 237,5 Ko).

**Le résultat s'inverse à 944 K paramètres**, où la référence vanilla FP32 l'emporte
d'environ 11 %. Le pari d'Atome porte délibérément sur le régime sous-1M, de classe MCU ;
au-delà, le plafond de capacité du ternaire comble l'écart puis le dépasse. Reproduction
complète dans [`FRONTIER.md`](FRONTIER.fr.md), lecture honnête complète incluant le
renversement dans [`HONEST_RESULTS.md`](HONEST_RESULTS.fr.md).

## Pourquoi

Les LLM de datacenter supposent la RAM d'un datacenter. Un microcontrôleur à 2 $ coincé
sur un mur dans un capteur distant, une aide auditive, un jouet à piles ou un thermostat
n'en dispose pas. Atome LM est la partie « conception du modèle » de cette contrainte :

- **Poids ternaires** (`{-α, 0, +α}` par tenseur, style BitNet b1.58). Aucune
  multiplication flottante dans le matmul à l'inférence.
- **Bloc à 3 voies** (convolution locale depthwise, SSM diagonal, attention parcimonieuse
  top-k) mélangées par un routeur souple par jeton. Conçu pour correspondre exactement à la
  structure du moteur C99 Atome, de sorte que les points de contrôle entraînés s'exportent
  vers la flash et s'exécutent avec une **parité exacte au bit près** entre Python et C.
- **Tokeniseur d'octets.** Aucune table BPE à livrer.
- **Entropie du routeur comme signal de calibration.** L'entropie de la distribution du
  routeur par jeton est observable gratuitement à chaque position. À l'échelle par défaut du
  moteur Atome-LLM (60 K paramètres) sur un unique corpus étroit, le signal est exposé mais
  sa calibration en tant qu'estimateur d'incertitude à cette échelle n'a pas été mesurée ici.
  Nous avons *préliminairement* observé (dans un modèle plus grand de 3 M paramètres **ne
  faisant pas partie de cette publication**) que l'entropie suit les entrées hors domaine et
  corrèle avec la perte par jeton — rapporté ici comme une observation non encore publique,
  avec des mesures à venir dans une prochaine publication.

## Ce que c'est et ce que ce n'est pas

- **Ce que c'est :** le côté entraînement Python et l'architecture d'un LM ternaire qui
  tourne sur du matériel à quelques centimes.
- **Ce que ce n'est pas :** un agent conversationnel généraliste. Dans la configuration par
  défaut du moteur (`d_model=64`, `n_layers=4`), le modèle fait environ 60 K paramètres et
  s'exporte vers environ 20 Ko de flash. Entraînez-le étroit — un seul domaine (Q&R de
  systèmes embarqués, aide en ligne de commande, une seule FAQ) — et il parle couramment
  dans ce périmètre. L'élargir à cette taille produit une sortie incohérente ; c'est le
  reflet de la capacité, pas de l'architecture. Pour plus de marge, augmentez `d_model` et
  `n_layers` (par ex. `d_model=128, n_layers=6` ≈ 600 K paramètres, ~150 Ko empaquetés) et
  ré-exportez avec les `#define` correspondants.

## Installation

```bash
./install.sh          # CPU-only venv + dependencies + environment check
```

Ou manuellement : `pip install -e .` (Python ≥ 3.10, PyTorch ≥ 2.0). Nouveau ici ?
[`QUICKSTART.md`](QUICKSTART.fr.md) est le chemin de 60 secondes du clone à un modèle
prêt pour microcontrôleur.

## Démarrage rapide

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

## Entraîner une petite démo

```bash
python scripts/train_demo.py --data path/to/text.txt --steps 1000 \
    --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt
```

Un `build_corpus.py` intégré récupère quelques sources sous licence permissive
(`tinystories`, `esp-idf`, `mcu-wikipedia`) pour un entraînement rapide de test :

```bash
python scripts/build_corpus.py --source tinystories --max-bytes 500000 \
    --output data/tinystories.txt
```

## Essayer un point de contrôle

```bash
python scripts/demo.py --checkpoint checkpoints/atome_demo.pt
# or, with no checkpoint, sanity-check the plumbing:
python scripts/demo.py --random --temperature 0.8 --top-p 0.9
```

Le REPL affiche la continuation et les barres d'entropie du routeur par couche au-dessus
de l'invite — le signal de métacognition exposé gratuitement.

## Échantillonnage

`AtomeLM.generate(...)` utilise par défaut l'argmax glouton (correspondant à
`atome_predict_next` du moteur C). Les arguments optionnels `temperature`, `top_p`, `top_k`
et `generator=` activent l'échantillonnage nucleus / top-k avec une reproductibilité par
graine.

## Benchmark

```bash
python scripts/benchmark.py            # tiny / default / large
```

Latence CPU forward + generate sur trois configurations représentatives. Utile comme
contrôle de non-régression après des changements d'architecture ; ce n'est pas un chiffre
MCU.

## Exporter vers un microcontrôleur

```bash
python scripts/export_to_atome.py \
    --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome \
    --header
```

Cela produit un binaire plat `.atome` que vous pouvez `#include` depuis C et charger avec
`atome_load(...)` du [moteur C99 Atome](c_engine/). En configuration par défaut, le binaire
fait bien moins de 100 Ko — il tient à l'aise sur ESP32-S3, STM32F4, RP2040, nRF52840,
ESP32-C3.

## Architecture

```
x → LayerNorm → ┬─→ Local  (depthwise causal conv k=5)        ─→┐
                ├─→ State  (diagonal SSM, O(L))                 ─→ Σ → +x
                └─→ Sparse (top-k attention, O(L·k))            ─→┘
                        ↑              ↑
                        │              router weights r ∈ Δ per token
                        └──────────────┘
```

Trois voies. Trois biais inductifs différents. Un routeur partagé par jeton qui apprend
quelle voie convient le mieux à chaque position. L'entropie par jeton du routeur est exposée
comme un signal d'incertitude gratuit à chaque position et à chaque couche.

L'histoire complète de l'architecture est dans [`PAPER.md`](PAPER.fr.md).

## Tests

```bash
pytest -q
```

## Licence

Licence Apache 2.0 — voir [`LICENSE`](LICENSE) et [`NOTICE`](NOTICE).

Le kit est entièrement ouvert : utilisez-le, modifiez-le, redistribuez-le et livrez-le dans
des produits commerciaux sans frais par siège ni par appareil. La concession de brevets
Apache 2.0 couvre l'architecture routée-ternaire à 3 voies telle que publiée ici.

Les points de contrôle publiés dans `checkpoints/` (atome_944k.bin, atome_1m_v1.pt,
vanilla_1m_v1.pt) sont eux aussi sous Apache 2.0. Ce sont des artefacts de
référence / recherche, pas des produits. L'intégration commerciale — bring-up silicium,
l'Atome Secure Boot Pack (blobs `.atome` signés, drapeaux dev/prod, secure-boot par
plateforme, attestation), le durcissement par plateforme, l'affinage sur domaine
personnalisé du plus grand modèle interne V2 — est disponible sur
[atomelm.com](https://atomelm.com).

## Citation

```bibtex
@software{atome_llm_2026,
  title  = {Atome LM: a tiny ternary language model for microcontroller deployment},
  author = {Atome LM contributors},
  year   = {2026},
  note   = {Apache 2.0, https://atomelm.com},
}
```
