"""atome_llm.core.trit_packing — base-3 packing of ternary weights.

Atome's stock export format stores ternary weights at 4 trits/byte
(2 bits/trit). That wastes 1 of every 4 codepoints — a 25 % overhead
versus the information-theoretic floor of log2(3) ≈ 1.585 bits/trit.

Base-3 packing puts 5 trits in 1 byte (3⁵ = 243 < 256), reaching
1.6 bits/trit — within 1 % of the floor and 20 % smaller than the stock
format. Encoding is

    byte = t0 + 3 · t1 + 9 · t2 + 27 · t3 + 81 · t4

where each `tk ∈ {0, 1, 2}` is the offset trit (raw `{-1, 0, +1}` shifted
by +1).

Decoding pulls the trits back out with five base-3 divisions.

This module is the Python reference. A C decoder lives next to it
(`c_engine/upstream/trit_packing.c`) and is bit-exact against this one.
"""
from __future__ import annotations

import numpy as np


TRITS_PER_BYTE = 5
"""Maximum ternary digits that fit losslessly in one byte (3^5 = 243)."""


def pack_trits(trits: np.ndarray) -> tuple[bytes, int]:
    """Pack a 1-D int8 array of `{-1, 0, +1}` into base-3 bytes.

    Returns
    -------
    (packed_bytes, n_trits) — `n_trits` is the original length, needed at
    decode time to know whether the last byte has padding trits to drop.
    """
    if trits.ndim != 1:
        raise ValueError(f"expected 1-D trits, got shape {trits.shape}")
    if trits.dtype.kind not in {"i", "u"}:
        raise ValueError(f"expected integer trits, got dtype {trits.dtype}")
    if trits.size > 0:
        lo, hi = int(trits.min()), int(trits.max())
        if lo < -1 or hi > 1:
            raise ValueError(f"trits out of range: min={lo} max={hi}")

    n = trits.size
    pad = (-n) % TRITS_PER_BYTE
    if pad:
        trits = np.concatenate([trits, np.zeros(pad, dtype=trits.dtype)])
    shifted = trits.astype(np.uint8) + 1            # {-1,0,+1} → {0,1,2}
    grouped = shifted.reshape(-1, TRITS_PER_BYTE)
    weights = np.array([1, 3, 9, 27, 81], dtype=np.uint16)
    packed = (grouped * weights).sum(axis=1).astype(np.uint8)
    return packed.tobytes(), n


def unpack_trits(packed: bytes, n_trits: int) -> np.ndarray:
    """Reverse of `pack_trits`. Returns int8 trits in `{-1, 0, +1}`."""
    if n_trits < 0:
        raise ValueError(f"n_trits must be >= 0, got {n_trits}")
    n_bytes_needed = (n_trits + TRITS_PER_BYTE - 1) // TRITS_PER_BYTE
    if len(packed) < n_bytes_needed:
        raise ValueError(
            f"need at least {n_bytes_needed} bytes for {n_trits} trits, "
            f"got {len(packed)}"
        )
    arr = np.frombuffer(packed[:n_bytes_needed], dtype=np.uint8)
    out = np.zeros(arr.size * TRITS_PER_BYTE, dtype=np.int8)
    a = arr.astype(np.int16)
    for k in range(TRITS_PER_BYTE):
        out[k::TRITS_PER_BYTE] = (a % 3).astype(np.int8) - 1
        a //= 3
    return out[:n_trits]


def packed_size(n_trits: int) -> int:
    """Bytes needed to pack `n_trits` ternary values."""
    if n_trits < 0:
        raise ValueError(f"n_trits must be >= 0, got {n_trits}")
    return (n_trits + TRITS_PER_BYTE - 1) // TRITS_PER_BYTE
