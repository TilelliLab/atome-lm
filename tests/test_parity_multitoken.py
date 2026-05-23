"""tests/test_parity_multitoken.py — multi-token Python↔C parity.

The single-forward parity test (`test_parity_with_c.py`) only checks the
last position of one predict_next call. This test extends the parity
contract across N generation steps: Python's `model.generate(prompt, N)`
and C's `atome_generate(prompt, ..., N)` must produce the same N tokens.

If the C engine's SSM hidden-state persistence-across-calls semantics
differs from Python's "fresh forward each call" semantics, this test
exposes it.

If gcc or the upstream atome C source is unavailable, the test is
skipped with a clear reason — it never silently passes.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parent.parent
ATOME_C_DIR = ROOT / "c_engine" / "upstream"
PARITY_C_DIR = ROOT / "tests" / "c_parity"
PARITY_C_FILE = PARITY_C_DIR / "parity_multitoken.c"

sys.path.insert(0, str(ROOT / "scripts"))


# Match the single-forward test's config so build cache (if any) is shared.
CONFIG = dict(
    vocab_size=32,
    d_model=16,
    n_layers=2,
    d_head=8,
    top_k=4,
    kernel_size=5,
)
MAX_SEQ = 32  # multi-token needs more headroom than single-forward's 8
N_GENERATE = 12  # generate this many continuation tokens
PROMPT = [10, 20, 5, 17]


def _gcc_available() -> bool:
    return shutil.which("gcc") is not None


def _atome_c_available() -> bool:
    return (ATOME_C_DIR / "atome.c").exists() and (ATOME_C_DIR / "atome.h").exists()


def _build_harness(tmp_path: Path) -> Path:
    out = tmp_path / "parity_multi"
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


def _run_c_harness(binary: Path, atome_path: Path,
                   prompt: list[int], n_generate: int) -> list[int]:
    proc = subprocess.run(
        [str(binary), str(atome_path),
         " ".join(str(t) for t in prompt), str(n_generate)],
        capture_output=True, text=True, check=True,
    )
    return [int(line) for line in proc.stdout.strip().splitlines()]


@pytest.mark.skipif(not _gcc_available(), reason="gcc not available")
@pytest.mark.skipif(not _atome_c_available(),
                    reason=f"upstream Atome C engine not at {ATOME_C_DIR}")
def test_python_c_generate_match(tmp_path: Path):
    """Multi-token autoregressive parity. Python's reference generate vs
    the C engine's atome_generate must produce identical token sequences.
    Random-init weights — exposes systematic divergences, not training-induced ones.
    """
    import export_to_atome as ex
    from atome_llm.core.atome_lm import AtomeLM

    torch.manual_seed(42)
    model = AtomeLM(**CONFIG)
    model.eval()

    atome_bin = tmp_path / "model.atome"
    ex.export_model(model, atome_bin, verbose=False)

    harness = _build_harness(tmp_path)
    c_tokens = _run_c_harness(harness, atome_bin, PROMPT, N_GENERATE)

    with torch.no_grad():
        prompt_tensor = torch.tensor([PROMPT], dtype=torch.long)
        py_full = model.generate(prompt_tensor, n_new_tokens=N_GENERATE,
                                 max_seq=MAX_SEQ)
        py_tokens = py_full[0, len(PROMPT):].tolist()

    print(f"\nPrompt:        {PROMPT}")
    print(f"Python tokens: {py_tokens}")
    print(f"C tokens:      {c_tokens}")

    # Identify first divergence step, if any.
    first_div = None
    for i, (p, c) in enumerate(zip(py_tokens, c_tokens)):
        if p != c:
            first_div = i
            break

    assert len(c_tokens) == len(py_tokens) == N_GENERATE, (
        f"length mismatch: C produced {len(c_tokens)}, Py produced {len(py_tokens)}"
    )
    assert py_tokens == c_tokens, (
        f"multi-token divergence first at step {first_div} "
        f"(Py={py_tokens[first_div]}, C={c_tokens[first_div]}). "
        f"Full Py: {py_tokens}\nFull C:  {c_tokens}"
    )


@pytest.mark.skipif(not _gcc_available(), reason="gcc not available")
@pytest.mark.skipif(not _atome_c_available(),
                    reason=f"upstream Atome C engine not at {ATOME_C_DIR}")
def test_python_c_generate_match_short_prompt(tmp_path: Path):
    """Single-token prompt. Documents the SSM-accumulation divergence."""
    import export_to_atome as ex
    from atome_llm.core.atome_lm import AtomeLM

    torch.manual_seed(7)
    model = AtomeLM(**CONFIG)
    model.eval()

    atome_bin = tmp_path / "model.atome"
    ex.export_model(model, atome_bin, verbose=False)

    harness = _build_harness(tmp_path)

    short_prompt = [3]
    short_n = 8
    c_tokens = _run_c_harness(harness, atome_bin, short_prompt, short_n)

    with torch.no_grad():
        prompt_tensor = torch.tensor([short_prompt], dtype=torch.long)
        py_full = model.generate(prompt_tensor, n_new_tokens=short_n,
                                 max_seq=MAX_SEQ)
        py_tokens = py_full[0, len(short_prompt):].tolist()

    assert py_tokens == c_tokens, (
        f"short-prompt divergence:\nPy: {py_tokens}\nC:  {c_tokens}"
    )
