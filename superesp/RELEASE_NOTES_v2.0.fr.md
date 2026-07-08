[English](RELEASE_NOTES_v2.0.md) · **Français** · [Español](RELEASE_NOTES_v2.0.es.md) · [简体中文](RELEASE_NOTES_v2.0.zh-CN.md) · [Deutsch](RELEASE_NOTES_v2.0.de.md) · [日本語](RELEASE_NOTES_v2.0.ja.md) <!-- i18n-switcher -->

# Atome LM v2 — SuperESP (notes de version)

**v2.0 — couche edge-AI appliquée sur le moteur ternaire Atome.** Livrée dans ce dépôt
sous `superesp/` ; elle importe `atome_llm.core` et utilise `c_engine/upstream/atome.c`,
donc elle vit aux côtés du moteur sur lequel elle tourne.

## Ce qu'elle contient
- **11 têtes appliquées sur appareil + un dispatcher OS** (classification) : agri, voice,
  motion, sound-scene, anomaly, air, os-telemetry, power/NILM, occupancy, wearable,
  water, forecast. Plus une tête de **régression**.
- **Installateur ESP32 universel** — auto-détecte la puce, flashe le firmware précompilé
  pour esp32 / s2 / s3 / c3 / c6 / h2 (Xtensa + RISC-V). Pas besoin d'ESP-IDF pour l'utilisateur.
- **Firmware agriculture à capteurs en direct** (ADC sol + DHT22 + relais).
- **Boucle « fabriquez le vôtre »** : firmware logger → `superesp log` → `train --csv` → `report` → `flashplan`.
- **Confiance** : attestation Ed25519, contrôle d'intégrité FNV au chargement, journal d'audit inviolable,
  et un **model-zoo** signé (`zoo build/list/pull/publish` avec vérification sha256 + signature).
- **CLI** : `superesp list / train / report / log / new / doctor / targets / setup / flashplan / zoo`.

## Vérifié (honnête)
- **Sur silicium réel (ESP32-WROOM-32) : 12/12 applications PASSENT**, ~27 Ko d'état, 265 Ko de tas libre.
- Parité Python↔C exacte au bit près (~1e-6) ; 6/6 cibles se compilent ; tests SuperESP 34/34 ; Atome 146/146 (pas de régression).
- Tenu à l'écart : les têtes fonctionnelles ~0,94 en moyenne. **Voice KWS = 0,625** (tokenisation en bandes) — modeste et
  au plafond de l'architecture ternaire ; rapporté honnêtement, non gonflé.
- **9 têtes livrées sur des données SYNTHÉTIQUES fondées sur la physique, clairement étiquetées.** Remplacez-en n'importe laquelle par vos vraies
  données via `train --csv --name <head>`. Seul esp32/WROOM est testé sur silicium ; les 5 autres sont vérifiés en compilation+QEMU.

## Pas une douve (moat) (dit clairement)
Kit ouvert de qualité production, tout en Apache-2.0 — chaque pièce est copiable. L'avantage durable est
hors-clavier : être prouvablement premier, une certification de verticale réglementée, ou l'adoption sur le zoo.

## Réservé (commercial, pas dans cette version)
Services (bring-up, attestation/certification, partenariat, affinage de domaine, durcissement, marque blanche),
l'autorité de clé de signature, le zoo hébergé + OTA, et le programme de certification. Voir
[atomelm.com/services](https://atomelm.com/services.html).
