"""tests/test_export_format.py — export_to_atome binary format sanity.

Runs the export script's `export_model` against a tiny AtomeLM, then
parses the resulting bytes directly to verify the magic header, the
per-block layout, and the trailing final-norm + unembed sections. We
don't test bit-exact parity with the C engine here (that lives in the
Atome project's `test_e2e.py`); this only checks the Python side
produces the binary format the engine expects.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest
import torch

from atome_llm.core.atome_lm import AtomeLM

# Adding scripts/ to sys.path so we can import the export module by name.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import export_to_atome as ex  # type: ignore  (script in scripts/ dir)


def packed_bytes_for_n_trits(n: int) -> int:
    return (n + 3) // 4


def test_pack_trits_round_trip_zero_one_minus_one():
    import numpy as np
    trits = np.array([0, 1, -1, 0, 1, -1, 0, 1], dtype=np.int8)
    packed = ex.pack_trits(trits)
    # 8 trits × 2 bits = 16 bits = 2 bytes
    assert len(packed) == 2
    # Byte 0: trit0=0(00,bits0-1) | trit1=01(bits2-3) | trit2=11(bits4-5) | trit3=00(bits6-7)
    #         = 0x00 | (0x01<<2) | (0x03<<4) | 0x00 = 0x34
    assert packed[0] == 0x34
    # Byte 1: trit4=01 | trit5=11(<<2) | trit6=00(<<4) | trit7=01(<<6)
    #         = 0x01 | 0x0C | 0x00 | 0x40 = 0x4D
    assert packed[1] == 0x4D


def test_export_roundtrips_magic_and_sizes(tmp_path: Path):
    """Construct a small model, export it, then parse the resulting bytes
    and check the magic, the per-block byte counts, and the trailing
    final-norm + unembed section."""
    torch.manual_seed(0)
    model = AtomeLM(vocab_size=32, d_model=16, n_layers=2, d_head=8,
                    top_k=4, kernel_size=5)

    out = tmp_path / "tiny.atome"
    stats = ex.export_model(model, out, verbose=False)

    data = out.read_bytes()
    assert data[:7] == b"ATOME01"
    cursor = 7

    cfg = model.config
    d, V, dh, ks = cfg["d_model"], cfg["vocab_size"], cfg["d_head"], cfg["kernel_size"]

    # embed: scale(f32) + packed trits (V × d)
    cursor += 4 + packed_bytes_for_n_trits(V * d)

    for _ in range(cfg["n_layers"]):
        # norm: gamma + beta (each f32 × d)
        cursor += 4 * d * 2
        # conv: scale + packed (d × ks)
        cursor += 4 + packed_bytes_for_n_trits(d * ks)
        # ssm: a + b + c_out (each f32 × d)
        cursor += 4 * d * 3
        # Wq, Wk: scale + packed (dh × d)
        for _wqk in range(2):
            cursor += 4 + packed_bytes_for_n_trits(dh * d)
        # Wv: scale + packed (d × d)
        cursor += 4 + packed_bytes_for_n_trits(d * d)
        # router: scale + packed (3 × d)
        cursor += 4 + packed_bytes_for_n_trits(3 * d)

    # final_norm + unembed
    cursor += 4 * d * 2
    cursor += 4 + packed_bytes_for_n_trits(V * d)

    assert cursor == len(data) == stats["total_bytes"]


def test_exported_scale_matches_layer_scale(tmp_path: Path):
    """The first 4 bytes after the magic encode the embedding's per-tensor
    scale alpha. It should match `model.embed.scale()` exactly."""
    torch.manual_seed(0)
    model = AtomeLM(vocab_size=32, d_model=16, n_layers=1, d_head=8, top_k=4)
    out = tmp_path / "tiny.atome"
    ex.export_model(model, out, verbose=False)
    data = out.read_bytes()
    encoded_scale = struct.unpack_from("<f", data, 7)[0]
    expected = model.embed.scale().item()
    assert abs(encoded_scale - expected) < 1e-6


def test_export_for_default_config_is_under_100kb(tmp_path: Path):
    """Sanity-check the headline claim: at engine defaults, the binary is
    well under 100 KB and fits comfortably on small MCUs."""
    model = AtomeLM()  # engine defaults
    out = tmp_path / "default.atome"
    stats = ex.export_model(model, out, verbose=False)
    assert stats["total_bytes"] < 100 * 1024


def test_generate_c_header(tmp_path: Path):
    stats = {
        "d_model": 64, "vocab_size": 256, "n_layers": 4,
        "d_head": 16, "kernel_size": 5, "n_pathways": 3,
        "top_k": 4,
    }
    out = tmp_path / "config.h"
    ex.generate_c_header(stats, out)
    text = out.read_text()
    assert "#define ATOME_D_MODEL    64" in text
    assert "#define ATOME_N_LAYERS   4" in text
    assert "#define ATOME_N_PATHWAYS 3" in text
    assert "#define ATOME_TOP_K      4" in text

    # Custom top_k must propagate (regression guard against the old
    # hardcoded `#define ATOME_TOP_K 4`).
    stats["top_k"] = 8
    ex.generate_c_header(stats, out)
    assert "#define ATOME_TOP_K      8" in out.read_text()
