"""tests/test_trit_packing.py — round-trip + size + boundary cases for base-3 packing."""
from __future__ import annotations

import numpy as np
import pytest

from atome_llm.core.trit_packing import (
    TRITS_PER_BYTE,
    pack_trits,
    packed_size,
    unpack_trits,
)


def test_round_trip_small():
    trits = np.array([-1, 0, 1, -1, 0, 1, 1, 0, -1, 1], dtype=np.int8)
    packed, n = pack_trits(trits)
    assert n == 10
    assert len(packed) == packed_size(10) == 2
    out = unpack_trits(packed, n)
    assert np.array_equal(out, trits)


def test_round_trip_random_large():
    rng = np.random.default_rng(0)
    trits = rng.integers(-1, 2, size=10_000).astype(np.int8)
    packed, n = pack_trits(trits)
    out = unpack_trits(packed, n)
    assert np.array_equal(out, trits)


def test_packing_size_matches_5_trits_per_byte():
    """5 trits → 1 byte, 6 trits → 2 bytes (1 byte of pad)."""
    assert packed_size(0) == 0
    assert packed_size(1) == 1
    assert packed_size(5) == 1
    assert packed_size(6) == 2
    assert packed_size(10) == 2
    assert packed_size(11) == 3
    assert packed_size(50) == 10


def test_size_advantage_vs_stock_format():
    """16,384 trits (one Atome embed weight): stock 4,096 B vs base-3 3,277 B = ~20% smaller."""
    n = 16_384
    stock_4_per_byte = (n + 3) // 4
    base3 = packed_size(n)
    assert stock_4_per_byte == 4_096
    assert base3 == 3_277
    saving = 1 - base3 / stock_4_per_byte
    assert 0.18 < saving < 0.22


def test_max_byte_value_in_range():
    """All-+1 trits should produce 2 + 3*2 + 9*2 + 27*2 + 81*2 = 242 (< 256)."""
    trits = np.full(5, 1, dtype=np.int8)
    packed, _ = pack_trits(trits)
    assert packed[0] == 2 + 6 + 18 + 54 + 162
    assert packed[0] == 242


def test_min_byte_value_in_range():
    """All-(-1) trits should produce 0 (since shifted to all-0)."""
    trits = np.full(5, -1, dtype=np.int8)
    packed, _ = pack_trits(trits)
    assert packed[0] == 0


def test_partial_last_byte_decodes_correctly():
    """7 trits, last byte holds 2 real trits + 3 padding zeros."""
    trits = np.array([-1, 0, 1, 1, -1, 0, 1], dtype=np.int8)
    packed, n = pack_trits(trits)
    out = unpack_trits(packed, n)
    assert np.array_equal(out, trits)


def test_pack_rejects_2d_input():
    with pytest.raises(ValueError):
        pack_trits(np.zeros((4, 4), dtype=np.int8))


def test_pack_rejects_out_of_range():
    with pytest.raises(ValueError):
        pack_trits(np.array([-2, 0, 1], dtype=np.int8))
    with pytest.raises(ValueError):
        pack_trits(np.array([-1, 0, 2], dtype=np.int8))


def test_unpack_rejects_short_buffer():
    """Asking for more trits than the buffer can hold should raise."""
    packed = b"\x00\x00"  # 2 bytes = up to 10 trits
    with pytest.raises(ValueError):
        unpack_trits(packed, 11)


def test_empty_round_trip():
    trits = np.array([], dtype=np.int8)
    packed, n = pack_trits(trits)
    assert n == 0
    assert packed == b""
    out = unpack_trits(packed, 0)
    assert out.size == 0
