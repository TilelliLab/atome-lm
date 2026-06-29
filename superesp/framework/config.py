"""superesp.framework.config — one shared architecture for all 7 heads.

Every SuperESP head uses the SAME tiny Atome architecture (only the trained
weights and the number of classes differ). This lets the C engine compile
ONCE and run any head by loading a different ATOMECL01 blob.

The config is deliberately small so heads train in seconds on CPU and the
state buffers stay tiny on an MCU. d_model=32, n_layers=2 → ~20K base params.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


# Byte vocabulary — sensor/feature frames are quantized to bytes (0..255),
# so the engine's existing 256-entry embedding works unchanged.
VOCAB_SIZE = 256

# Hard cap from atome.h (ATOME_MAX_SEQ) and the classifier head (ATOME_MAX_CLASSES).
MAX_SEQ = 32
MAX_CLASSES = 16


@dataclass(frozen=True)
class SuperESPConfig:
    vocab_size: int = VOCAB_SIZE
    d_model: int = 32
    n_layers: int = 2
    d_head: int = 8
    top_k: int = 4
    kernel_size: int = 5
    max_seq: int = MAX_SEQ
    max_classes: int = MAX_CLASSES

    def atome_kwargs(self) -> dict:
        """kwargs for AtomeLM(...)."""
        return {
            "vocab_size": self.vocab_size,
            "d_model": self.d_model,
            "n_layers": self.n_layers,
            "d_head": self.d_head,
            "top_k": self.top_k,
            "kernel_size": self.kernel_size,
        }

    def as_dict(self) -> dict:
        return asdict(self)


# The single shared config instance every head and the C engine use.
SHARED = SuperESPConfig()
