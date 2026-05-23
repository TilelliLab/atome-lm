"""tests/test_ssm.py — DiagonalSSM shape, conv vs recurrent agreement."""
from __future__ import annotations

import torch

from atome_llm.core.ssm import DiagonalSSM


def test_shape_preserved():
    ssm = DiagonalSSM(channels=8)
    x = torch.randn(2, 10, 8)
    y = ssm(x)
    assert y.shape == (2, 10, 8)


def test_forward_and_infer_agree_numerically():
    """The convolutional unrolling and the recurrent step must produce the
    same sequence — they're two evaluations of the same linear recurrence."""
    ssm = DiagonalSSM(channels=4)
    x = torch.randn(1, 8, 4)
    with torch.no_grad():
        a = ssm(x)
    b = ssm.infer(x)
    assert torch.allclose(a, b, atol=1e-5)


def test_gradient_flows_to_all_three_params():
    ssm = DiagonalSSM(channels=4)
    x = torch.randn(1, 6, 4, requires_grad=True)
    ssm(x).sum().backward()
    for name in ("a_raw", "b", "c_out"):
        p = getattr(ssm, name)
        assert p.grad is not None and torch.any(p.grad != 0), f"no grad for {name}"
