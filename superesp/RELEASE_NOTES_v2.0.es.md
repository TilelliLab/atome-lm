[English](RELEASE_NOTES_v2.0.md) · [Français](RELEASE_NOTES_v2.0.fr.md) · **Español** · [简体中文](RELEASE_NOTES_v2.0.zh-CN.md) · [Deutsch](RELEASE_NOTES_v2.0.de.md) · [日本語](RELEASE_NOTES_v2.0.ja.md) <!-- i18n-switcher -->

# Atome LM v2 — SuperESP (notas de versión)

**v2.0 — capa de edge-AI aplicado sobre el motor ternario de Atome.** Se envía en este repo
bajo `superesp/`; importa `atome_llm.core` y usa `c_engine/upstream/atome.c`,
así que vive junto al motor sobre el que corre.

## Qué contiene
- **11 cabezas aplicadas en el dispositivo + un despachador OS** (clasificación): agri, voice,
  motion, sound-scene, anomaly, air, os-telemetry, power/NILM, occupancy, wearable,
  water, forecast. Más una cabeza de **regresión**.
- **Instalador ESP32 universal** — autodetecta el chip, flashea firmware precompilado
  para esp32 / s2 / s3 / c3 / c6 / h2 (Xtensa + RISC-V). El usuario no necesita ESP-IDF.
- **Firmware de agricultura con sensores en vivo** (ADC de suelo + DHT22 + relé).
- **Bucle «haz el tuyo»**: firmware logger → `superesp log` → `train --csv` → `report` → `flashplan`.
- **Confianza**: atestación Ed25519, comprobación de integridad FNV en carga, registro de auditoría a prueba de manipulaciones,
  y un **model-zoo** firmado (`zoo build/list/pull/publish` con verificación de sha256 + firma).
- **CLI**: `superesp list / train / report / log / new / doctor / targets / setup / flashplan / zoo`.

## Verificado (honesto)
- **En silicio real (ESP32-WROOM-32): 12/12 aplicaciones PASAN**, ~27 KB de estado, 265 KB de heap libre.
- Paridad Python↔C exacta al bit (~1e-6); 6/6 objetivos compilan; tests SuperESP 34/34; Atome 146/146 (sin regresión).
- Apartado: las cabezas funcionales ~0,94 de media. **Voice KWS = 0,625** (tokenización en bandas) — modesto y
  en el techo de la arquitectura ternaria; reportado honestamente, no inflado.
- **9 cabezas se envían con datos SINTÉTICOS fundados en la física, claramente etiquetados.** Reemplaza cualquiera por tus datos
  reales vía `train --csv --name <head>`. Solo esp32/WROOM está probado en silicio; los otros 5 están verificados por compilación+QEMU.

## No es un foso (moat) (dicho llanamente)
Kit abierto de grado producción, todo Apache-2.0 — cada pieza es copiable. La ventaja durable está
fuera del teclado: ser demostrablemente el primero, una certificación de vertical regulada, o la adopción en el zoo.

## Reservado (comercial, no en esta versión)
Servicios (puesta en marcha, atestación/certificación, alianza, afinado de dominio, endurecimiento, marca blanca),
la autoridad de clave de firma, el zoo alojado + OTA, y el programa de certificación. Véase
[atomelm.com/services](https://atomelm.com/services.html).
