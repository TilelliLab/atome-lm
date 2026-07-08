[English](README.md) · **Français** · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# SuperESP — Atome-LM appliqué pour l'edge ESP32

SuperESP transforme le modèle Atome ternaire minuscule (1,58 bit) en une suite de
**classifieurs de flux appliqués** qui tournent sur un microcontrôleur *au lieu de* la
génération de texte, plus un runtime **« OS » sur l'appareil** qui lit tous les capteurs de
l'ESP32 et route vers la bonne tête.

Il réalise le PIVOT #1 de la revue de douve (moat) Atome du 2026-06-13 : la tête
`atome_classify` existait dans le moteur C mais n'avait **jamais été entraînée**. SuperESP
l'entraîne — pour 7 tâches edge réelles — et câble l'inférence delta (énergie), l'abstention
(refuser-quand-incertain) et l'attestation cryptographique (auditabilité).

## Les 11 têtes (une seule compilation de moteur partagée ; chaque tête = un blob ATOMECL01 différent)
| tête | tâche | données |
|---|---|---|
| SuperESP-Agri | sol/climat → irriguer/gel/nuisible/sain/défaut | SYNTH (agronomique) |
| SuperESP-Voice | micro I2S → commandes vocales de ferme (on/off/stop/go) | RÉEL (Speech Commands) |
| SuperESP-Motion | IMU → activité/geste/chute | RÉEL (UCI HAR) |
| SuperESP-Sound-Scene | audio ambiant → événement acoustique | SYNTH (audio synthétique) |
| SuperESP-Anomaly | vibration → santé machine | SYNTH (physique) |
| SuperESP-Air | gaz+climat → qualité de l'air/fuite | SYNTH (physique) |
| SuperESP-OS | télémétrie ESP32 fusionnée → état de l'appareil + dispatch | SYNTH (télémétrie puce) |
| SuperESP-Power | énergie pince ampèremétrique/NILM → type de charge | SYNTH (physique) |
| SuperESP-Occupancy | PIR+CO2+son → occupation de la pièce | SYNTH (physique) |
| SuperESP-Wearable | PPG+IMU → état cardiaque/activité (non médical) | SYNTH (physique) |
| SuperESP-Water | débit+pression+humidité → fuite/inondation | SYNTH (physique) |

## Vitesse
- **Noyau ternaire :** matvec 4-trits/octet sans branchement → **classification 306 µs → 87 µs (3,5×)**, ~11 400/s
  sur hôte (-O3). Profite à tout le moteur Atome (classify + generate + ESP32). Exactitude au bit près
  préservée (parité max |Δ| 8,3e-7) ; les 146 tests existants passent.
- **Streaming à seuil de changement** (`framework/streaming.py`) : sur un flux corrélé toujours actif, ne
  ré-exécuter le modèle que quand l'entrée dérive au-delà d'un seuil de déclenchement ; sinon réutiliser la décision
  en cache (bit-identique à une exécution à chaque trame). Le taux de saut est le gain (≈98 % sur un flux statique).
- **Inférence delta** (`framework/delta.py`) : 4-11× moins d'opérations matvec sur les flux corrélés.
- Les tok/s/RAM sur silicium ESP32 sont **NON MESURÉS** (pas de carte) ; les accélérations hôte devraient se transmettre.

Voir `HONEST_RESULTS.md` / `artifacts/RESULTS.json` pour la précision tenue à l'écart,
l'AURC d'abstention, l'accélération d'inférence delta, et l'étiquette RÉEL/SYNTH par tête.

## Comment ça marche
- **Tokeniseur** (`framework/tokenize.py`) : chaque trame de capteur/caractéristique est linéairement
  quantifiée en une séquence d'octets (≤32) — de sorte que le moteur Atome existant à vocabulaire de 256 octets
  tourne inchangé. Les constantes de quantification sont ajustées sur le TRAIN uniquement (sans fuite).
- **Modèle** (`framework/model.py`) : la base `AtomeLM` existante + une tête de
  classification ternaire sur le caché final-norm du dernier jeton — exactement ce que le
  C `atome_classify` calcule. **Parité Python↔C exacte au bit près** (max |Δ| ~7e-7).
- **Abstention** (`framework/abstain.py`) : refuser quand la marge softmax top1-top2
  est faible ; rapporté comme une courbe risque-couverture + AURC vs oracle/aléatoire.
- **Inférence delta** (`framework/delta.py`) : matvec delta intègre-et-tire pour
  les flux de capteurs corrélés — le proxy d'énergie mesuré de l'expérience
  delta_inference, appliqué par tête.
- **Attestation** (`attest/sign.py`) : reçu signé Ed25519 liant sha256(blob)
  + métadonnées, pour qu'un déployeur puisse prouver que CETTE tête exacte a tourné. Inviolable (tamper-evident).
- **Runtime** (`runtime/dispatcher.py`) : route une trame vers sa tête par modalité,
  exécute la tête OS sur la télémétrie fusionnée, délestage sous états de défaut. Miroir C :
  `c_engine/superesp/superesp_os.c`. Squelette firmware : `superesp/firmware/`.

## Installation
```
pip install -e .              # core (torch + numpy); run the CLI as: python3 -m superesp.cli <cmd>
pip install -e ".[superesp]"  # + cryptography/scipy/pyserial/esptool (attestation, audio, flashing)
```

## Flasher n'importe quel ESP32 (pas besoin d'ESP-IDF — précompilé pour esp32/s2/s3/c3/c6/h2)
```
bash superesp/esp32/install.sh    # auto-detects the chip, flashes the matching
                                  # prebuilt firmware, runs all heads, writes a report
```

## Fabriquez votre PROPRE classifieur en quelques minutes (sans compétence ML — la boucle log→entraîner→flasher)
```
# 1. flash the data-logger, then record YOUR sensor in each state:
python3 -m superesp.cli log --label dry --out field.csv   # leave probe in dry soil
python3 -m superesp.cli log --label wet --out field.csv   # ...then wet soil
# 2. train + see how good it is + deploy:
python3 -m superesp.cli train --csv field.csv --name myfarm
python3 -m superesp.cli report myfarm                     # confusion matrix + abstention (md + html)
python3 -m superesp.cli flashplan myfarm
# (or start from a blank template:)  python3 -m superesp.cli new myfarm --features 30
```
**Les 9 têtes SYNTH ne sont que des valeurs par défaut — entièrement remplaçables.** Entraînez sous un nom
intégré avec vos propres données pour la remplacer par un modèle du monde réel :
`python3 -m superesp.cli train --csv my_field.csv --name agri` écrase le blob de la tête synthétique `agri`.
Rien n'est codé en dur ; chaque tête est « entraîner sur des données → exporter un blob ».

## Reproduire / apportez vos propres données
```
python3 -m superesp.cli list                      # the 11 built-in heads
python3 -m superesp.cli train agri                # train+eval+export one built-in head
# YOUR sensor: rows = up to 32 features + a label column
python3 -m superesp.cli train --csv my.csv --label-col state --name mysensor
python3 -m superesp.cli flashplan mysensor        # how to bake the blob into firmware
# or everything at once:
python3 -m superesp.train_all && python3 -m superesp.attest_all
python3 -m pytest superesp/tests                  # framework, parity(gcc), attest, dispatch, streaming, csv, novelty
```
Quiconque a un CSV de ses propres fenêtres de capteur ESP32 obtient un classifieur sur appareil
exact au bit près et attestable — sans configuration ML. C'est l'analogue ouvert/auditable d'un
pipeline TinyML commercial.

## Périmètre honnête / douve (moat)
Les têtes individuelles sont de l'edge-AI appliqué réel (une ÉTAPE / un produit), **pas des douves** —
les KWS/geste/anomalie TinyML sont encombrés (TFLite-Micro, Edge Impulse). Le seul
angle défendable est la combinaison **ternaire ultra-minuscule + auditable au bit près +
attestée cryptographiquement + efficace en delta** en tant qu'OS
unifié sur appareil. C'est un pari de premier arrivé/intégration, pas une douve de bac à sable. Les têtes
entraînées sur données SYNTH sont des substituts de style physique, étiquetés comme tels — pas des
affirmations de déploiement sur le terrain. Le débit/RAM sur silicium sont **NON MESURÉS** (pas de carte).
```
```
