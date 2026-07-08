[English](PAPER.md) · **Français** · [Español](PAPER.es.md) · [简体中文](PAPER.zh-CN.md) · [Deutsch](PAPER.de.md) · [日本語](PAPER.ja.md) <!-- i18n-switcher -->

# Atome LM — architecture pour modèles de langage ternaires natifs microcontrôleur

## 1. Motivation

Les plus petits modèles de langage qui « parlent vraiment » se situent, aujourd'hui, dans la fourchette de 100 M à 1 Md de paramètres. Chacun de ces modèles réclame plus de RAM et plus de bande passante mémoire qu'un microcontrôleur à 2 $ ne peut en offrir. Les choix d'architecture de ces modèles — attention complète, FFN denses, MoE multi-bancs, voies augmentées par récupération (retrieval) — sont des choix faits sous l'hypothèse que la RAM est bon marché. Atome LM part de l'hypothèse inverse : la RAM est la contrainte qui domine toutes les autres.

Il en résulte une architecture délibérément étroite, conçue de bout en bout pour être compatible avec un moteur d'inférence C99 à forme fixe qui tourne sur des puces disposant de kilo-octets — et non de méga-octets — de RAM de travail.

## 2. Contraintes issues du moteur

La structure `atome_block_t` du moteur C99 Atome est figée ainsi :

```
norm        : LayerNorm
local_conv  : depthwise causal conv, ternary kernel
ssm         : diagonal SSM (per-channel a, b, c_out, FP32)
attn        : top-k causal attention, ternary Q/K/V
router      : ternary linear → softmax over 3 pathways
```

Des tampons statiques existent pour chacune de ces trois sorties de voie, ainsi que pour l'état caché du SSM et le cache KV de l'attention. Il n'y a pas de tampon pour une convolution large, pas de tampon pour un FFN dense, aucune prévision pour des poids multi-bancs, aucune échelle par ligne dans le noyau ternaire. Tenter d'entraîner une architecture plus large et de la « faire rentrer plus tard » exigerait soit de régénérer la structure C (rompant le contrat de parité exacte au bit près sur lequel repose ce projet), soit de livrer des voies non prises en charge qui seraient silencieusement abandonnées à l'inférence.

Atome LM correspond donc exactement au moteur : trois voies, échelle par tenseur, tokeniseur d'octets, aucun plongement positionnel, longueur de séquence plafonnée par `ATOME_MAX_SEQ` à la compilation.

## 3. Le bloc

```
x → LayerNorm → ┬─→ Local   (depthwise causal conv, k=5)        ─→┐
                ├─→ State   (diagonal SSM, O(L))                  ─→ Σ → +x
                └─→ Sparse  (top-k attention, O(L·k))             ─→┘
                        ↑              ↑
                        │              router weights r ∈ Δ per token
                        └──────────────┘
```

Trois opérations structurellement différentes :

| # | Nom    | Opération               | Rôle                          |
|---|--------|-------------------------|------------------------------|
| 1 | Local  | Conv depthwise k=5      | Bigrammes, frontières de mots |
| 2 | State  | SSM diagonal            | Report de thème longue portée |
| 3 | Sparse | Attention top-k         | Coréférence, rappel exact     |

Le routeur est un `TernaryLinear(d_model, 3)` suivi d'un softmax. Il produit une distribution à 3 voies par jeton ; la sortie du bloc est le résidu plus la combinaison convexe des sorties de voie sous cette distribution.

### 3.1 L'entropie du routeur comme signal de calibration

La distribution du routeur par jeton porte un signal d'incertitude :

```
H(r_t) = − Σ_i r_t,i · log r_t,i,    bounded in [0, log 3] for 3 pathways
```

Une entropie élevée signifie que le routeur n'a pas pu décider quelle primitive de calcul convenait le mieux à la position. Le signal est structurel — il ne requiert aucun entraînement spécifique à l'incertitude et aucun paramètre supplémentaire. À l'échelle par défaut du moteur Atome-LLM (60 K paramètres, corpus unique et étroit), le signal est exposé mais sa calibration en tant qu'estimateur d'incertitude à cette échelle n'est pas évaluée ici. Dans un modèle plus grand de 3 M paramètres **non inclus dans cette publication**, nous avons *préliminairement* observé l'entropie du routeur suivre les entrées hors domaine et corréler avec la perte par jeton ; nous ne rapportons cela que comme une **observation non encore reproductible**, et nous comptons publier les mesures à l'appui dans une prochaine version. La mesurer (par ex. l'erreur de calibration attendue entre l'entropie du routeur et la perte par jeton) est un exercice distinct.

`MCUBlock.router_entropy(x)` renvoie l'entropie par jeton en nats. `AtomeLM.router_entropies(ids)` renvoie l'entropie par couche et par jeton sous forme d'une liste de tenseurs `(B, L)`. La structure `atome_state_t` du moteur C expose le tableau des poids du routeur par jeton `router_w[ATOME_MAX_SEQ][ATOME_N_PATHWAYS]` — l'entropie est une somme/log sur celui-ci.

## 4. Budget de taille et de forme

Aux `#define` par défaut du moteur (`d_model=64`, `n_layers=4`, `d_head=16`, `vocab=256`, `kernel=5`) :

- Plongement : 256 × 64 = 16 384 trits
- Par bloc : norm (256 FP32) + conv (64 × 5 trits) + SSM (3 × 64 FP32) + Wq/Wk/Wv (16 × 64 + 16 × 64 + 64 × 64 trits) + routeur (3 × 64 trits)
- Norm finale : 128 FP32
- Dé-plongement (unembed) : 64 × 256 trits

Empaqueté à 2 bits par trit, le binaire est de l'ordre de 30 à 60 Ko selon la configuration. Confortablement en dessous de 100 Ko pour les valeurs par défaut typiques, bien en dessous du 1 Mo de flash d'un STM32 d'entrée de gamme, et de plusieurs ordres de grandeur plus petit que les 8 Mo disponibles sur un ESP32-S3.

L'usage de RAM à l'inférence est dominé par les tampons statiques de `atome_state_t` : `x`, `normed`, trois tableaux de travail pour les sorties de voie, un tableau d'état caché de SSM par couche, les caches KV, le tampon des poids du routeur, le tampon des logits. Aux valeurs par défaut, cela totalise quelques Ko.

## 5. Ce qui n'est pas dans cette publication

- Pas de MoE à poids multi-bancs (le moteur ne le prend pas en charge ; cela romprait la parité exacte au bit près).
- Pas d'échelle ternaire par ligne (même raison).
- Pas de plongement positionnel. La conv locale et l'état caché du SSM encodent la position implicitement à l'intérieur de la fenêtre de séquence fixée à la compilation du moteur.
- Pas de voie de récupération, pas de voie de mémoire épisodique. Toutes deux exigent un stockage hors puce ou de grands tableaux de travail en RAM incompatibles avec le matériel cible.

Ce sont des omissions délibérées, pas des lacunes. Elles sont le prix à payer pour tourner sur du matériel où la RAM est la contrainte contraignante.

## 6. Limites

- **Échelle.** La configuration par défaut fait environ 60 K paramètres (`d_model=64`, `n_layers=4`). Entraînez-la étroit sur un corpus focalisé et elle parle couramment dans le périmètre ; entraînez-la large et elle ne sera pas cohérente. C'est le reflet de la capacité, pas de l'architecture. Pour plus de marge, augmentez `d_model` et `n_layers` — par ex. `d_model=128`, `n_layers=6` fait environ 600 K paramètres.
- **Longueur de séquence.** Plafonnée par `ATOME_MAX_SEQ` à la compilation du moteur (32 par défaut). Pour une génération plus longue, générez jeton par jeton en passant le préfixe grandissant à `atome_predict_next` — le moteur redérive l'état caché du SSM à partir du préfixe complet à chaque appel, ce qui maintient la parité Python ↔ C déterministe.
- **Tokenisation.** Au niveau de l'octet. Les séquences UTF-8 multi-octets coûtent plusieurs positions. Pas idéal pour les écritures non latines à la valeur par défaut `MAX_SEQ` du moteur ; envisagez d'augmenter `ATOME_MAX_SEQ` et de ré-exporter si votre écriture cible a un nombre moyen élevé d'octets par caractère.

## Références

- Ma et al., 2024. *The Era of 1-bit LLMs: All Large Language Models are in 1.58 Bits.* arXiv:2402.17764.
- Wang et al., 2023. *BitNet: Scaling 1-bit Transformers for Large Language Models.* arXiv:2310.11453.
- Gu and Dao, 2023. *Mamba: Linear-Time Sequence Modeling with Selective State Spaces.* arXiv:2312.00752.
