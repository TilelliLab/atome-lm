#!/usr/bin/env python3
"""Atome LM environment check.

Verifies the Python version, dependencies, package import, and a tiny
forward + loss pass. Exits non-zero on the first hard failure, so it can
gate CI or a fresh install. Run any time: `python check_env.py`.
"""
import sys


def _fail(msg: str) -> None:
    print(f"  FAIL  {msg}")
    sys.exit(1)


def main() -> None:
    print("Atome LM environment check")
    print("-" * 44)

    if sys.version_info < (3, 10):
        _fail(f"Python >= 3.10 required, found {sys.version.split()[0]}")
    print(f"  OK    Python {sys.version.split()[0]}")

    try:
        import torch
    except ImportError:
        _fail("PyTorch not installed — run ./install.sh")
    print(f"  OK    torch {torch.__version__}")

    try:
        import numpy
    except ImportError:
        _fail("numpy not installed — run ./install.sh")
    print(f"  OK    numpy {numpy.__version__}")

    try:
        from atome_llm.core.atome_lm import AtomeLM
    except ImportError as e:
        _fail(f"cannot import atome_llm ({e}) — run: pip install -e .")
    print("  OK    atome_llm imports")

    try:
        model = AtomeLM()
        n_params = model.parameter_count()
        ids = torch.randint(0, 256, (1, 32))
        logits = model(ids)
        assert logits.shape == (1, 32, 256), f"bad logits shape {tuple(logits.shape)}"
        loss = model.loss(ids[:, :-1], ids[:, 1:])
        assert torch.isfinite(loss), "loss is not finite"
    except Exception as e:  # noqa: BLE001 — surface any failure to the user
        _fail(f"forward pass failed: {e}")
    print(f"  OK    forward pass — {n_params:,} params, loss {float(loss):.3f}")

    print("-" * 44)
    print("All checks passed. See QUICKSTART.md to train and export a model.")


if __name__ == "__main__":
    main()
