# Atome LM v2 — SuperESP (release notes)

**v2.0 — applied edge-AI layer on the Atome ternary engine.** Ships in this repo
under `superesp/`; it imports `atome_llm.core` and uses `c_engine/upstream/atome.c`,
so it lives alongside the engine it runs on.

## What's in it
- **11 applied on-device heads + an OS dispatcher** (classification): agri, voice,
  motion, sound-scene, anomaly, air, os-telemetry, power/NILM, occupancy, wearable,
  water, forecast. Plus a **regression** head.
- **Universal ESP32 installer** — auto-detects the chip, flashes prebuilt firmware
  for esp32 / s2 / s3 / c3 / c6 / h2 (Xtensa + RISC-V). No ESP-IDF needed by the user.
- **Live-sensor agriculture firmware** (soil ADC + DHT22 + relay).
- **Make-your-own loop**: logger firmware → `superesp log` → `train --csv` → `report` → `flashplan`.
- **Trust**: Ed25519 attestation, load-time FNV integrity check, tamper-evident audit log,
  and a signed **model-zoo** (`zoo build/list/pull/publish` with sha256 + signature verify).
- **CLI**: `superesp list / train / report / log / new / doctor / targets / setup / flashplan / zoo`.

## Verified (honest)
- **On real silicon (ESP32-WROOM-32): 12/12 applications PASS**, ~27 KB state, 265 KB free heap.
- Bit-exact Python↔C parity (~1e-6); 6/6 targets build; SuperESP tests 34/34; Atome 146/146 (no regression).
- Held-out: working heads ~0.94 mean. **Voice KWS = 0.625** (banded tokenization) — modest and
  at the ternary-architecture ceiling; reported honestly, not inflated.
- **9 heads ship on physics-grounded SYNTHETIC data, clearly labelled.** Swap any for your real
  data via `train --csv --name <head>`. Only esp32/WROOM is silicon-tested; other 5 are build+QEMU-verified.

## Not a moat (stated plainly)
Production-grade open kit, all Apache-2.0 — every piece is copyable. The durable advantage is
off-keyboard: being provably first, a regulated-vertical certification, or adoption on the zoo.

## Reserved (commercial, not in this release)
Services (bring-up, attestation/cert, partnership, domain-tuning, hardening, white-label),
the signing-key authority, the hosted zoo + OTA, and the certification program. See
[atomelm.com/services](https://atomelm.com/services.html).
