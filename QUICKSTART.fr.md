[English](QUICKSTART.md) · **Français** · [Español](QUICKSTART.es.md) · [简体中文](QUICKSTART.zh-CN.md) · [Deutsch](QUICKSTART.de.md) · [日本語](QUICKSTART.ja.md) <!-- i18n-switcher -->

# Atome LM — Démarrage rapide

Le chemin de 60 secondes du clone à un modèle entraîné, prêt pour microcontrôleur.
Pour l'histoire complète, voir [README.md](README.fr.md) et [REPRODUCE.md](REPRODUCE.fr.md).

## 1. Installer (CPU seulement, pas de GPU)

```bash
./install.sh
. .venv/bin/activate
```

`install.sh` crée un `.venv` local, installe PyTorch CPU-only et Atome
LM, et exécute `check_env.py`. Relancez `python check_env.py` à tout moment pour
revérifier l'environnement.

## 2. Entraîner un petit modèle de démo

Un échantillon d'environ 256 Ko du corpus TinyStories sous licence permissive est livré dans
`data/sample.txt`, de sorte que ceci tourne hors ligne :

```bash
python scripts/train_demo.py --data data/sample.txt --steps 1000 \
    --d-model 64 --n-layers 4 --output checkpoints/atome_demo.pt
```

Pour un corpus plus grand, récupérez-en un avec le constructeur fourni :

```bash
python scripts/build_corpus.py --source tinystories \
    --max-bytes 500000 --output data/tinystories.txt
```

## 3. Lui parler

```bash
python scripts/demo.py --checkpoint checkpoints/atome_demo.pt
```

Le REPL affiche la continuation plus les barres d'entropie du routeur par couche — le
signal d'incertitude par jeton exposé gratuitement.

## 4. Exporter vers un microcontrôleur

```bash
python scripts/export_to_atome.py \
    --checkpoint checkpoints/atome_demo.pt \
    --output checkpoints/atome_demo.atome --header
```

En configuration par défaut, le binaire `.atome` fait bien moins de 100 Ko. Déposez le
`.h` généré dans un projet C et chargez-le avec le moteur de
`c_engine/`.

## 5. Lancer les tests

```bash
pytest -q
```

Les tests de parité QEMU Cortex-M3 nécessitent `qemu-system-arm`, `arm-none-eabi-gcc`
et `xxd` dans le `PATH` ; ils sont **ignorés** (skipped, pas en échec) lorsque la chaîne
d'outils est absente.

---

**Les poids entraînés sont fournis** dans `checkpoints/` — `atome_944k.bin`
(blob empaqueté du moteur C), `atome_1m_v1.pt` (source PyTorch) et
`vanilla_1m_v1.pt` (référence FP32 pour l'A/B du renversement à 944 K dans
[HONEST_RESULTS.md](HONEST_RESULTS.fr.md)). Si vous voulez exécuter le modèle
sans entraîner d'abord :

```bash
python scripts/demo.py --checkpoint checkpoints/atome_1m_v1.pt
```

Si vous voulez entraîner le vôtre depuis zéro, suivez le
flux `scripts/train_demo.py` ci-dessus — il produit un modèle de 60 K paramètres
en ~30 min sur un CPU.
