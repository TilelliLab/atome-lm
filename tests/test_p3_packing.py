"""tests/test_p3_packing.py — round-trip + sizes for power-of-3 packing."""
from __future__ import annotations

import numpy as np
import pytest

from atome_llm.core.p3_packing import (
    BITS_PER_CODE,
    WEIGHTS_PER_GROUP,
    pack_p3,
    packed_size,
    unpack_p3,
)


def test_round_trip_small():
    codes = np.array([-9, -3, -1, 0, 1, 3, 9, 1], dtype=np.int8)
    packed, n = pack_p3(codes)
    assert n == 8
    assert len(packed) == 3              # 8 codes × 3 bits = 3 bytes
    out = unpack_p3(packed, n)
    assert np.array_equal(out, codes)


def test_round_trip_large():
    rng = np.random.default_rng(0)
    levels = np.array([-9, -3, -1, 0, 1, 3, 9])
    codes = levels[rng.integers(0, 7, size=10_000)].astype(np.int8)
    packed, n = pack_p3(codes)
    assert len(packed) == packed_size(n)
    out = unpack_p3(packed, n)
    assert np.array_equal(out, codes)


def test_packing_size():
    """8 codes → 3 bytes; 9 codes → 6 bytes (one full + one partial group)."""
    assert packed_size(0) == 0
    assert packed_size(1) == 3
    assert packed_size(8) == 3
    assert packed_size(9) == 6
    assert packed_size(16) == 6
    assert packed_size(64) == 24


def test_size_advantage_over_int8():
    """Power-3 packed is 3 bits/weight vs int8 storage at 8 bits/weight."""
    n = 16_384
    int8_bytes = n
    p3_bytes = packed_size(n)
    saving = 1 - p3_bytes / int8_bytes
    assert p3_bytes == 6_144
    assert saving > 0.6      # ~62 % smaller than int8


def test_size_overhead_vs_ternary():
    """Power-3 takes ~50 % more space than 2-bit ternary; ATOME01 packing is 4 trits/byte."""
    n = 16_384
    ternary_bytes = (n + 3) // 4
    p3_bytes = packed_size(n)
    overhead = p3_bytes / ternary_bytes - 1
    assert 0.45 < overhead < 0.55


def test_pack_rejects_2d():
    with pytest.raises(ValueError):
        pack_p3(np.zeros((4, 4), dtype=np.int8))


def test_pack_rejects_invalid_level():
    with pytest.raises(ValueError):
        pack_p3(np.array([2], dtype=np.int8))      # 2 not in {-9,-3,-1,0,1,3,9}
    with pytest.raises(ValueError):
        pack_p3(np.array([-5], dtype=np.int8))


def test_unpack_rejects_short_buffer():
    packed = b"\x00\x00\x00"  # 3 bytes = 8 codes max
    with pytest.raises(ValueError):
        unpack_p3(packed, 9)


def test_constants_consistent():
    assert WEIGHTS_PER_GROUP * BITS_PER_CODE == 24


def test_empty_round_trip():
    packed, n = pack_p3(np.array([], dtype=np.int8))
    assert n == 0 and packed == b""
    assert unpack_p3(packed, 0).size == 0
