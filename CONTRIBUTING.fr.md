[English](CONTRIBUTING.md) · **Français** · [Español](CONTRIBUTING.es.md) · [简体中文](CONTRIBUTING.zh-CN.md) · [Deutsch](CONTRIBUTING.de.md) · [日本語](CONTRIBUTING.ja.md) <!-- i18n-switcher -->

# Contribuer à Atome LM

Merci d'envisager une contribution. Ceci est un petit projet ciblé — un modèle de langage ternaire minuscule + un moteur d'inférence C99 qui lui parle au bit près. Lisez d'abord `PROJECT_CONTENT.md` ; il couvre ce que vous ne devez pas casser.

## Démarrage rapide

```bash
git clone https://github.com/TilelliLab/atome-lm
cd atome-lm
./install.sh
. .venv/bin/activate
pytest -q        # expect: 146 passed (or 145 + 1 skipped without qemu-system-arm)
```

## Signaler des bugs

Ouvrez une issue sur GitHub avec :

- ce que vous avez exécuté (commande exacte)
- ce que vous attendiez
- ce qui s'est passé (erreur complète, non paraphrasée)
- votre plateforme : OS, version de Python, et `python -c "import torch; print(torch.__version__)"`

Si vous rencontrez un échec de parité (forward Python ≠ forward C), veuillez joindre la graine défaillante et tout point de contrôle que vous avez entraîné — ce sont les bugs de plus haute priorité.

## Soumettre une pull request

1. Forkez le dépôt et créez une branche depuis `main`.
2. Faites votre changement.
3. Exécutez toute la suite de tests — chaque PR doit garder `pytest -q` au vert.
4. Si votre changement touche `atome_llm/core/`, `c_engine/upstream/` ou le format d'export, **confirmez spécifiquement** que ces tests passent toujours :
   - `tests/test_parity_with_c.py` — parité forward-unique Python ↔ C
   - `tests/test_parity_multitoken.py` — parité multi-jetons Python ↔ C
   - `tests/test_export_format.py` — format binaire + génération d'en-tête
5. Ouvrez la PR. La CI relancera la suite sur Python 3.10 / 3.11 / 3.12.

## Périmètre des changements acceptables

Bienvenus :

- Corrections de bugs
- Nouvelle couverture de tests (surtout des cas de fuzz sur le parseur C et des entrées limites vers `atome_predict_next` / `atome_generate`)
- Améliorations de performance qui préservent la parité exacte au bit près
- Corrections et clarifications de documentation
- Nouvelles cartes cibles MCU sous `c_engine/targets/`, *tant qu'elles ne changent pas le moteur upstream*
- Nouvelles références sous `atome_llm/baselines/` pour une comparaison A/B honnête

Hors périmètre, merci de ne pas ouvrir de PR pour ceci :

- Ajouter de l'allocation de tas, de la mémoire dynamique ou des dépendances libc à `c_engine/upstream/`
- Ajouter des replis (fallbacks) « ne devrait pas arriver » à des chemins de code déterministes
- Empaqueter de nouveaux tokeniseurs (BPE / sentencepiece) — le tokeniseur d'octets est un choix de conception porteur pour le budget de flash MCU
- Des changements qui cassent la parité Python ↔ C, même s'ils améliorent un benchmark
- De nouvelles fonctionnalités qui promeuvent du code de `c_engine/experiments/` vers `c_engine/upstream/` sans couverture complète de parité + vérification de bornes

## Standards de codage

- Python : gardez ça simple, pas de couches d'aide, pas de décorateurs-pour-le-style. Collez à la voix existante — petites fonctions, pas d'abstraction prématurée, des commentaires seulement quand le *pourquoi* n'est pas évident.
- C : C99 seulement, pas d'extensions GNU, pas de libc au-delà de `<string.h>` / `<math.h>` / `<stdint.h>`. Tampons statiques dimensionnés par des macros `ATOME_*` à la compilation. Vérifiez les bornes de toutes les entrées de l'API publique.

## Sécurité

Si vous trouvez un problème de sécurité (quoi que ce soit qui permette à un point de contrôle ou blob `.atome` malveillant de compromettre un hôte exécutant le moteur), veuillez envoyer un e-mail à **hello@atomelm.com** au lieu d'ouvrir une issue publique. Nous coordonnerons la divulgation.

## Licence

En soumettant une contribution, vous acceptez qu'elle soit publiée sous la licence Apache 2.0 (la licence du projet — voir `LICENSE`).
