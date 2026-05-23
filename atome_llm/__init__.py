"""Atome LLM — a tiny ternary language model designed for the Atome C99
microcontroller inference engine.

Three pathways (local conv + diagonal SSM + sparse attention) mixed by a
per-token soft router. Architecture chosen for bit-exact parity with the
Atome C99 engine (zero-heap, integer-arithmetic forward pass on
microcontrollers from ESP32 to STM32 to RP2040).

Released under the Apache License 2.0; see the LICENSE file.
"""

__version__ = "0.3.0"
