[English](RELEASE_NOTES_v2.0.md) · [Français](RELEASE_NOTES_v2.0.fr.md) · [Español](RELEASE_NOTES_v2.0.es.md) · [简体中文](RELEASE_NOTES_v2.0.zh-CN.md) · **Deutsch** · [日本語](RELEASE_NOTES_v2.0.ja.md) <!-- i18n-switcher -->

# Atome LM v2 — SuperESP (Release Notes)

**v2.0 — angewandte Edge-KI-Schicht auf der ternären Atome-Engine.** Wird in diesem Repo
unter `superesp/` ausgeliefert; sie importiert `atome_llm.core` und nutzt `c_engine/upstream/atome.c`,
also lebt sie neben der Engine, auf der sie läuft.

## Was drin ist
- **11 angewandte Köpfe auf dem Gerät + ein OS-Dispatcher** (Klassifizierung): agri, voice,
  motion, sound-scene, anomaly, air, os-telemetry, power/NILM, occupancy, wearable,
  water, forecast. Plus ein **Regressions**-Kopf.
- **Universeller ESP32-Installer** — erkennt den Chip automatisch, flasht vorkompilierte Firmware
  für esp32 / s2 / s3 / c3 / c6 / h2 (Xtensa + RISC-V). Kein ESP-IDF beim Nutzer nötig.
- **Live-Sensor-Landwirtschafts-Firmware** (Boden-ADC + DHT22 + Relais).
- **Mach-deinen-eigenen-Schleife**: Logger-Firmware → `superesp log` → `train --csv` → `report` → `flashplan`.
- **Vertrauen**: Ed25519-Attestierung, FNV-Integritätsprüfung beim Laden, manipulationssicheres Audit-Log,
  und ein signierter **Model-Zoo** (`zoo build/list/pull/publish` mit sha256- + Signaturprüfung).
- **CLI**: `superesp list / train / report / log / new / doctor / targets / setup / flashplan / zoo`.

## Verifiziert (ehrlich)
- **Auf echtem Silizium (ESP32-WROOM-32): 12/12 Anwendungen BESTEHEN**, ~27 KB State, 265 KB freier Heap.
- Bit-genaue Python↔C-Parität (~1e-6); 6/6 Targets bauen; SuperESP-Tests 34/34; Atome 146/146 (keine Regression).
- Zurückgehalten: funktionierende Köpfe ~0,94 im Mittel. **Voice KWS = 0,625** (Banded-Tokenisierung) — bescheiden und
  an der Obergrenze der ternären Architektur; ehrlich berichtet, nicht aufgebläht.
- **9 Köpfe werden mit physikalisch fundierten SYNTHETISCHEN Daten ausgeliefert, klar gekennzeichnet.** Ersetze einen beliebigen durch deine
  echten Daten über `train --csv --name <head>`. Nur esp32/WROOM ist silizium-getestet; die anderen 5 sind Build+QEMU-verifiziert.

## Kein Burggraben (moat) (klar gesagt)
Produktionsreifes offenes Kit, alles Apache-2.0 — jedes Teil ist kopierbar. Der dauerhafte Vorteil liegt
abseits der Tastatur: nachweislich Erster zu sein, eine Zertifizierung in einer regulierten Vertikale, oder die Adoption im Zoo.

## Reserviert (kommerziell, nicht in diesem Release)
Dienste (Inbetriebnahme, Attestierung/Zertifizierung, Partnerschaft, Domänen-Tuning, Härtung, White-Label),
die Signierschlüssel-Autorität, der gehostete Zoo + OTA und das Zertifizierungsprogramm. Siehe
[atomelm.com/services](https://atomelm.com/services.html).
