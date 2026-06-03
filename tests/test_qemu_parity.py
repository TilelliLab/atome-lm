"""tests/test_qemu_parity.py — end-to-end Python ↔ ARM Cortex-M3 firmware parity.

Builds the engine with arm-none-eabi-gcc, runs it on a QEMU MPS2-AN385
emulated Cortex-M3 with semihosting, captures the logits printed via
newlib's printf, and compares them to the Python AtomeLM forward pass.

Skipped (not failed) when arm-none-eabi-gcc, qemu-system-arm, or xxd
are not on PATH — the host parity test (`test_parity_with_c.py`) still
covers the Python ↔ x86-64-C invariant in that case.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _have_tool(name: str) -> bool:
    return shutil.which(name) is not None


def _arm_can_build() -> bool:
    """True only if arm-none-eabi-gcc can actually find its C library headers.
    The gcc-arm-none-eabi package ships the compiler but not newlib; without
    libnewlib-arm-none-eabi a simple `#include <stdio.h>` fails to compile, so
    checking for the binary alone is not enough — verify a real build works."""
    if not _have_tool("arm-none-eabi-gcc"):
        return False
    try:
        r = subprocess.run(
            ["arm-none-eabi-gcc", "-fsyntax-only", "-x", "c", "-"],
            input=b"#include <stdio.h>\n",
            capture_output=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


@pytest.mark.skipif(not _arm_can_build(),
                    reason="arm-none-eabi-gcc + newlib (libnewlib-arm-none-eabi) not available")
@pytest.mark.skipif(not _have_tool("qemu-system-arm"),
                    reason="qemu-system-arm not installed")
@pytest.mark.skipif(not _have_tool("xxd"), reason="xxd not installed")
def test_qemu_cortex_m3_logits_match_python(tmp_path: Path):
    """Build firmware, run on QEMU, compare logits to Python."""
    import run_qemu as rq

    import export_to_atome as ex
    from atome_llm.core.atome_lm import AtomeLM

    torch.manual_seed(42)
    model = AtomeLM(**rq.CONFIG)
    model.eval()

    atome_bin = tmp_path / "model.atome"
    ex.export_model(model, atome_bin, verbose=False)

    header = rq.CM3_DIR / "model_data.h"
    rq._bake_model_data_h(atome_bin, header)

    try:
        elf = rq._build_firmware(rq._atome_defines(rq.CONFIG))
        out = rq._run_qemu(elf, timeout_s=60.0)
    finally:
        # Don't leak generated artifacts into the source tree
        subprocess.run(["make", "-C", str(rq.CM3_DIR), "clean"],
                       capture_output=True)

    c_logits = rq._parse_logits(out, rq.CONFIG["vocab_size"])

    with torch.no_grad():
        ids = torch.tensor([rq.TOKENS], dtype=torch.long)
        py_logits = model(ids)[0, -1, :]

    abs_diff = (c_logits - py_logits).abs()
    max_d = abs_diff.max().item()
    print(f"\nCortex-M3 vs Python: max |Δ| = {max_d:.4g}, "
          f"argmax C={c_logits.argmax().item()} "
          f"Py={py_logits.argmax().item()}")

    assert torch.allclose(c_logits, py_logits, atol=1e-3, rtol=1e-3), (
        f"divergence beyond tolerance: max |Δ|={max_d:.4g}"
    )
    assert c_logits.argmax().item() == py_logits.argmax().item()
