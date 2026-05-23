"""tests/test_parity_with_c.py — bit-exact parity between AtomeLM (Python)
and the Atome C99 engine.

This is the foundational invariant the whole project rests on: any
checkpoint trained in Python must produce the same logits when loaded
by the C engine on a microcontroller. If this test passes, the
Python↔C parity claim is real. If it fails, any number you measure
in Python is meaningless on-device.

How it works:
  1. Construct a tiny AtomeLM at a fixed config (kept small for build speed)
  2. Export to a temporary .atome binary
  3. Compile the C harness `c_parity/parity_main.c` against the upstream
     atome.c source, with compile-time defines matching the Python config
  4. Run the harness on a fixed token sequence; capture logits
  5. Run the Python forward on the same sequence; compare last-position logits
  6. Assert agreement within a numerical tolerance (associativity in
     summation gives some divergence, but it should be well under 1e-3)

If gcc or the upstream atome C source is unavailable, the test is
skipped with a clear reason — it never silently passes.
"""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest
import torch

# Path to the Atome C engine, vendored inside this repo so the parity
# test runs anywhere the repo is checked out — no external dependency.
ROOT = Path(__file__).resolve().parent.parent
ATOME_C_DIR = ROOT / "c_engine" / "upstream"
PARITY_C_DIR = ROOT / "tests" / "c_parity"
PARITY_C_FILE = PARITY_C_DIR / "parity_main.c"

sys.path.insert(0, str(ROOT / "scripts"))


# A small but non-trivial config — keeps gcc fast, exercises every path.
CONFIG = dict(
    vocab_size=32,
    d_model=16,
    n_layers=2,
    d_head=8,
    top_k=4,
    kernel_size=5,
)
MAX_SEQ = 8
TOKENS = [10, 20, 5, 17, 0, 25]  # any sequence with len <= MAX_SEQ


def _gcc_available() -> bool:
    return shutil.which("gcc") is not None


def _atome_c_available() -> bool:
    return (ATOME_C_DIR / "atome.c").exists() and (ATOME_C_DIR / "atome.h").exists()


def _build_harness(tmp_path: Path) -> Path:
    """Compile the C harness with defines matching CONFIG. Returns the binary path."""
    out = tmp_path / "parity"
    defines = [
        f"-DATOME_D_MODEL={CONFIG['d_model']}",
        f"-DATOME_MAX_SEQ={MAX_SEQ}",
        f"-DATOME_N_LAYERS={CONFIG['n_layers']}",
        f"-DATOME_N_PATHWAYS=3",
        f"-DATOME_VOCAB_SIZE={CONFIG['vocab_size']}",
        f"-DATOME_D_HEAD={CONFIG['d_head']}",
        f"-DATOME_KERNEL_SIZE={CONFIG['kernel_size']}",
        f"-DATOME_TOP_K={CONFIG['top_k']}",
    ]
    cmd = [
        "gcc", "-O2", "-std=c99",
        f"-I{ATOME_C_DIR}",
        *defines,
        str(PARITY_C_FILE),
        str(ATOME_C_DIR / "atome.c"),
        "-lm",
        "-o", str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"gcc failed:\n{proc.stderr}")
    return out


def _run_c_harness(binary: Path, atome_path: Path, tokens: list[int]) -> torch.Tensor:
    proc = subprocess.run(
        [str(binary), str(atome_path), " ".join(str(t) for t in tokens)],
        capture_output=True, text=True, check=True,
    )
    logits = [float(line) for line in proc.stdout.strip().splitlines()]
    return torch.tensor(logits, dtype=torch.float32)


@pytest.mark.skipif(not _gcc_available(), reason="gcc not available")
@pytest.mark.skipif(not _atome_c_available(),
                    reason=f"upstream Atome C engine not at {ATOME_C_DIR}")
def test_python_c_logits_match(tmp_path: Path):
    import export_to_atome as ex
    from atome_llm.core.atome_lm import AtomeLM

    torch.manual_seed(42)
    model = AtomeLM(**CONFIG)
    model.eval()

    atome_bin = tmp_path / "model.atome"
    ex.export_model(model, atome_bin, verbose=False)

    harness = _build_harness(tmp_path)
    c_logits = _run_c_harness(harness, atome_bin, TOKENS)
    assert c_logits.shape == (CONFIG["vocab_size"],)

    with torch.no_grad():
        ids = torch.tensor([TOKENS], dtype=torch.long)
        py_logits_all = model(ids)                      # (1, L, vocab)
        py_logits = py_logits_all[0, -1, :]             # last position only

    abs_diff = (c_logits - py_logits).abs()
    max_diff = abs_diff.max().item()
    mean_diff = abs_diff.mean().item()

    print(f"\nC vs Python logits (vocab={CONFIG['vocab_size']}, last position):")
    print(f"  max |Δ|  = {max_diff:.6g}")
    print(f"  mean |Δ| = {mean_diff:.6g}")
    print(f"  C argmax  = {c_logits.argmax().item()}")
    print(f"  Py argmax = {py_logits.argmax().item()}")

    assert torch.allclose(c_logits, py_logits, atol=1e-3, rtol=1e-3), (
        f"logits diverged beyond tolerance: max |Δ|={max_diff:.4g}"
    )


@pytest.mark.skipif(not _gcc_available(), reason="gcc not available")
@pytest.mark.skipif(not _atome_c_available(),
                    reason=f"upstream Atome C engine not at {ATOME_C_DIR}")
def test_python_c_argmax_agrees(tmp_path: Path):
    """Even if numerical diffs creep in, the next-token decision must agree."""
    import export_to_atome as ex
    from atome_llm.core.atome_lm import AtomeLM

    torch.manual_seed(7)
    model = AtomeLM(**CONFIG)
    model.eval()

    atome_bin = tmp_path / "model.atome"
    ex.export_model(model, atome_bin, verbose=False)
    harness = _build_harness(tmp_path)

    for seed_seq in ([1, 2, 3], [10, 11, 12, 13, 14], [29, 0, 17, 8]):
        c_logits = _run_c_harness(harness, atome_bin, seed_seq)
        with torch.no_grad():
            ids = torch.tensor([seed_seq], dtype=torch.long)
            py_logits = model(ids)[0, -1, :]
        assert c_logits.argmax().item() == py_logits.argmax().item(), (
            f"argmax disagreement on seed {seed_seq}: "
            f"C={c_logits.argmax().item()} Py={py_logits.argmax().item()}"
        )
