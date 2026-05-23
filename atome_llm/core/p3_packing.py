"""atome_llm.core.p3_packing — 3-bit packing for power-of-3 weights.

Power-of-3 weights take values in {-9, -3, -1, 0, 1, 3, 9} — 7 distinct
levels, fitting exactly in 3 bits. Eight weights pack into 3 bytes (24
bits), so on-disk cost is **3 bits per weight** vs ternary's 2 bits per
weight. Cost: +50 % storage. Benefit: ~2 % perplexity at 60 K params on
TinyStories (verified in the multi-seed sweep).

Code map:
    000 = 0
    001 = +1
    010 = -1
    011 = +3
    100 = -3
    101 = +9
    110 = -9
    111 = unused (sentinel — never written by encoder)
"""
from __future__ import annotations

import numpy as np


WEIGHTS_PER_GROUP = 8         # 8 codes × 3 bits = 24 bits = 3 bytes
BYTES_PER_GROUP   = 3
BITS_PER_CODE     = 3

_LEVEL_TO_CODE = {0: 0b000, 1: 0b001, -1: 0b010,
                  3: 0b011, -3: 0b100, 9: 0b101, -9: 0b110}
_CODE_TO_LEVEL = {v: k for k, v in _LEVEL_TO_CODE.items()}


def _validate_levels(arr: np.ndarray) -> None:
    if arr.size > 0:
        unique = np.unique(arr).tolist()
        for v in unique:
            if int(v) not in _LEVEL_TO_CODE:
                raise ValueError(
                    f"value {v} not in power-of-3 level set "
                    f"{sorted(_LEVEL_TO_CODE)}"
                )


def packed_size(n_weights: int) -> int:
    """Bytes needed to pack `n_weights` power-of-3 codes."""
    if n_weights < 0:
        raise ValueError(f"n_weights must be >= 0, got {n_weights}")
    n_groups = (n_weights + WEIGHTS_PER_GROUP - 1) // WEIGHTS_PER_GROUP
    return n_groups * BYTES_PER_GROUP


def pack_p3(codes: np.ndarray) -> tuple[bytes, int]:
    """Pack a 1-D int array of {-9, -3, -1, 0, 1, 3, 9} into 3-bit groups.

    Returns (packed_bytes, n_weights). The n_weights is required at decode
    time to drop trailing padding codes.
    """
    if codes.ndim != 1:
        raise ValueError(f"expected 1-D codes, got shape {codes.shape}")
    _validate_levels(codes)

    n = codes.size
    pad = (-n) % WEIGHTS_PER_GROUP
    flat = np.concatenate([codes, np.zeros(pad, dtype=codes.dtype)]).astype(np.int64)
    code_arr = np.array([_LEVEL_TO_CODE[int(v)] for v in flat], dtype=np.uint32)

    n_groups = code_arr.size // WEIGHTS_PER_GROUP
    out = bytearray(n_groups * BYTES_PER_GROUP)
    for g in range(n_groups):
        word = 0
        for i in range(WEIGHTS_PER_GROUP):
            word |= int(code_arr[g * WEIGHTS_PER_GROUP + i]) << (i * BITS_PER_CODE)
        # word now uses 24 bits; emit little-endian.
        out[g * 3 + 0] = word & 0xFF
        out[g * 3 + 1] = (word >> 8) & 0xFF
        out[g * 3 + 2] = (word >> 16) & 0xFF
    return bytes(out), n


def unpack_p3(packed: bytes, n_weights: int) -> np.ndarray:
    """Reverse of `pack_p3`. Returns int8 codes in the level set."""
    if n_weights < 0:
        raise ValueError(f"n_weights must be >= 0, got {n_weights}")
    nb = packed_size(n_weights)
    if len(packed) < nb:
        raise ValueError(
            f"need at least {nb} bytes for {n_weights} weights, got {len(packed)}"
        )
    n_groups = nb // BYTES_PER_GROUP
    out = np.zeros(n_groups * WEIGHTS_PER_GROUP, dtype=np.int8)
    for g in range(n_groups):
        word = (
            packed[g * 3 + 0]
            | (packed[g * 3 + 1] << 8)
            | (packed[g * 3 + 2] << 16)
        )
        for i in range(WEIGHTS_PER_GROUP):
            code = (word >> (i * BITS_PER_CODE)) & 0b111
            if code == 0b111:
                # Sentinel: encoder never produces this; treat as 0 for
                # robustness if a malformed file slips through.
                out[g * WEIGHTS_PER_GROUP + i] = 0
            else:
                out[g * WEIGHTS_PER_GROUP + i] = _CODE_TO_LEVEL[code]
    return out[:n_weights]
