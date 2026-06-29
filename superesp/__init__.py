"""SuperESP — applied Atome-LM prototypes for the ESP32 / Cortex-M edge.

A suite of tiny ternary (1.58-bit) streaming classifiers that run *instead of*
text generation: agritech, voice/keyword command, motion, sound-scene, anomaly,
air-quality, and an on-device "OS" runtime that reads all the ESP32's sensors
and dispatches to the right head.

Built additively on top of the existing Atome LM engine (atome_llm.core +
c_engine). Realizes PIVOT #1 of the 2026-06-13 moat review: the `atome_classify`
head existed in C but was never trained.

Honest scope: the individual heads are real applied edge-AI (a STEP / product),
not moats — TinyML KWS/gesture/anomaly are crowded. The only defensible angle is
the ultra-tiny ternary + bit-exact-auditable + cryptographically-attested +
delta-efficient *combination* as a unified on-device OS. See superesp/LEDGER.md.
"""

__version__ = "0.1.0"
