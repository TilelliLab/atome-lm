"""tests/test_tokenize.py — ByteTokenizer round-trip and shape."""
from __future__ import annotations

import torch

from atome_llm.tokenize import ByteTokenizer


def test_round_trip_ascii():
    tok = ByteTokenizer()
    s = "hello world"
    ids = tok.encode(s)
    assert ids.dtype == torch.long
    assert ids.shape == (len(s.encode("utf-8")),)
    assert tok.decode(ids) == s


def test_round_trip_utf8_multibyte():
    tok = ByteTokenizer()
    s = "café · 日本語 · 🚀"
    ids = tok.encode(s)
    assert tok.decode(ids) == s


def test_invalid_byte_replaced():
    tok = ByteTokenizer()
    ids = torch.tensor([0xFF, 0xFE, 0xFD], dtype=torch.long)
    decoded = tok.decode(ids)
    assert "�" in decoded
