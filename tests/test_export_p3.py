"""tests/test_export_p3.py — ATOMEP3 round-trip + size comparison."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import torch

from atome_llm.core.atome_lm import AtomeLM
from atome_llm.core.power3 import power3_codes
from atome_llm.core.ternary import absmean_scale

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _model(seed: int = 0):
    torch.manual_seed(seed)
    return AtomeLM(vocab_size=64, d_model=32, n_layers=2,
                   d_head=8, top_k=4, quantizer="power3").eval()


def test_round_trip_dequantized(tmp_path: Path):
    import export_to_atome_p3 as ep
    model = _model()
    out = tmp_path / "m.atome3"
    ep.export_model(model, out, verbose=False)
    decoded = ep.unpack_atome_p3(out, {
        "vocab_size": 64, "d_model": 32, "n_layers": 2,
        "d_head": 8, "kernel_size": 5,
    })
    expected_embed = (
        power3_codes(model.embed.weight).numpy().astype(np.float32)
        * absmean_scale(model.embed.weight).item()
    )
    assert np.allclose(decoded["embed"], expected_embed, atol=1e-7)


def test_p3_smaller_than_int8_storage(tmp_path: Path):
    """The P3 binary should be far smaller than naive int8 storage at the
    same model size — in particular about 3 bits per weight."""
    import export_to_atome_p3 as ep
    model = _model()
    out = tmp_path / "m.atome3"
    ep.export_model(model, out, verbose=False)
    n_p3 = sum(p.numel() for n, p in model.named_parameters()
               if "weight" in n and ("embed" in n or "unembed" in n
                                     or "Wq" in n or "Wk" in n or "Wv" in n
                                     or "router" in n or "local" in n))
    int8_estimate = n_p3
    actual = out.stat().st_size
    assert actual < int8_estimate, (
        f"ATOMEP3 binary {actual} should be smaller than int8 storage {int8_estimate}"
    )


def test_magic_is_atome_p3(tmp_path: Path):
    import export_to_atome_p3 as ep
    out = tmp_path / "m.atome3"
    ep.export_model(_model(), out, verbose=False)
    assert out.read_bytes()[:7] == b"ATOMEP3"


def test_unpack_rejects_wrong_magic(tmp_path: Path):
    import export_to_atome_p3 as ep
    bad = tmp_path / "bad.atome3"
    bad.write_bytes(b"NOTATOME" + b"\x00" * 100)
    with pytest.raises(ValueError):
        ep.unpack_atome_p3(bad, {
            "vocab_size": 64, "d_model": 32, "n_layers": 2,
            "d_head": 8, "kernel_size": 5,
        })


def test_p3_size_between_atome01_and_int8(tmp_path: Path):
    """ATOMEP3 should be ~50% bigger than ATOME01 (ternary) on the same model
    — within a tolerance because of fixed FP32 overhead."""
    import export_to_atome as v1
    import export_to_atome_p3 as p3
    torch.manual_seed(0)
    # Use ternary-init model so v1 export is meaningful.
    ternary = AtomeLM(vocab_size=64, d_model=32, n_layers=2,
                      d_head=8, top_k=4).eval()
    p3_model = AtomeLM(vocab_size=64, d_model=32, n_layers=2,
                       d_head=8, top_k=4, quantizer="power3").eval()
    p3_model.load_state_dict(ternary.state_dict())  # same weights

    p1 = tmp_path / "m.atome"
    p2 = tmp_path / "m.atome3"
    v1.export_model(ternary, p1, verbose=False)
    p3.export_model(p3_model, p2, verbose=False)
    assert p2.stat().st_size > p1.stat().st_size      # P3 strictly bigger
    overhead = p2.stat().st_size / p1.stat().st_size - 1
    assert overhead < 1.0       # but not more than 2× the ternary size
