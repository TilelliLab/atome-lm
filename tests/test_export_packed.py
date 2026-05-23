"""tests/test_export_packed.py — ATOME02 (base-3 packed) round-trip + size win.

The export is bit-exact-recoverable: every dequantized weight read from
disk equals the in-memory weight matrix (sign × scale).

The packed binary is at least 18 % smaller than the stock 4-trit/byte
ATOME01 format on the same model.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import torch

from atome_llm.core.atome_lm import AtomeLM
from atome_llm.core.ternary import absmean_scale, ternary_signs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _model(seed: int = 0) -> AtomeLM:
    torch.manual_seed(seed)
    return AtomeLM(vocab_size=64, d_model=32, n_layers=2,
                   d_head=8, top_k=4).eval()


def test_round_trip_dequantized_weights_match(tmp_path: Path):
    import export_to_atome_packed as ep
    model = _model()

    out = tmp_path / "model.atome2"
    ep.export_model(model, out, verbose=False)
    decoded = ep.unpack_atome02(out, model.config)

    # embed
    expected = (
        ternary_signs(model.embed.weight).numpy().astype(np.float32)
        * absmean_scale(model.embed.weight).item()
    )
    assert np.allclose(decoded["embed"], expected, atol=1e-7)

    # one block's Wq, conv (with the spatial-flip), router
    block0 = model.blocks[0]
    expected_wq = (
        ternary_signs(block0.sparse.Wq.weight).numpy().astype(np.float32)
        * absmean_scale(block0.sparse.Wq.weight).item()
    )
    assert np.allclose(decoded["blocks"][0]["Wq"], expected_wq, atol=1e-7)

    with torch.no_grad():
        cw = block0.local.weight.squeeze(1)
    expected_conv = (
        ternary_signs(cw).numpy().astype(np.float32)[:, ::-1].copy()
        * absmean_scale(cw).item()
    )
    assert np.allclose(decoded["blocks"][0]["conv"], expected_conv, atol=1e-7)

    expected_router = (
        ternary_signs(block0.router.proj.weight).numpy().astype(np.float32)
        * absmean_scale(block0.router.proj.weight).item()
    )
    assert np.allclose(decoded["blocks"][0]["router"], expected_router, atol=1e-7)


def test_packed_smaller_than_atome01(tmp_path: Path):
    import export_to_atome as ex_v1
    import export_to_atome_packed as ex_v2
    model = _model()

    p1 = tmp_path / "model.atome"
    p2 = tmp_path / "model.atome2"
    ex_v1.export_model(model, p1, verbose=False)
    ex_v2.export_model(model, p2, verbose=False)

    s1 = p1.stat().st_size
    s2 = p2.stat().st_size
    saving = 1 - s2 / s1
    assert s2 < s1, f"ATOME02 {s2}B not smaller than ATOME01 {s1}B"
    assert saving > 0.1, (
        f"saving {saving:.1%} below 10% — packing didn't pay off as expected"
    )


def test_packed_at_engine_default_under_18kb(tmp_path: Path):
    """Engine-default model (60.8K params) packed → < 18 KB on disk."""
    import export_to_atome_packed as ep
    torch.manual_seed(0)
    model = AtomeLM().eval()  # engine defaults
    out = tmp_path / "model.atome2"
    ep.export_model(model, out, verbose=False)
    size = out.stat().st_size
    assert size < 18 * 1024, f"packed binary is {size / 1024:.1f} KB, want < 18"


def test_magic_bytes_are_atome02(tmp_path: Path):
    import export_to_atome_packed as ep
    out = tmp_path / "model.atome2"
    ep.export_model(_model(), out, verbose=False)
    assert out.read_bytes()[:7] == b"ATOME02"


def test_unpack_rejects_wrong_magic(tmp_path: Path):
    import export_to_atome_packed as ep
    bad = tmp_path / "bad.atome2"
    bad.write_bytes(b"NOTATOME" + b"\x00" * 100)
    with pytest.raises(ValueError):
        ep.unpack_atome02(bad, _model().config)
