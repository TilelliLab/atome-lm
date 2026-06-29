"""superesp.framework.parity — compile + run the C classifier harness.

Builds c_engine/superesp/classify_main.c against the upstream atome.c with
compile-time defines matching the SuperESP SHARED config, runs it on a byte
token sequence, and returns the C class logits + predicted class. Used by the
parity tests to prove the trained head produces the same decision on-device.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import torch

from superesp.framework.config import SHARED, MAX_CLASSES

_REPO = Path(__file__).resolve().parents[2]
_ATOME_C_DIR = _REPO / "c_engine" / "upstream"
_HARNESS = _REPO / "c_engine" / "superesp" / "classify_main.c"


def gcc_available() -> bool:
    return shutil.which("gcc") is not None


def atome_c_available() -> bool:
    return (_ATOME_C_DIR / "atome.c").exists() and (_ATOME_C_DIR / "atome.h").exists()


def build_harness(out_dir: Path, config=SHARED) -> Path:
    out = Path(out_dir) / "superesp_classify"
    defines = [
        f"-DATOME_D_MODEL={config.d_model}",
        f"-DATOME_MAX_SEQ={config.max_seq}",
        f"-DATOME_N_LAYERS={config.n_layers}",
        "-DATOME_N_PATHWAYS=3",
        f"-DATOME_VOCAB_SIZE={config.vocab_size}",
        f"-DATOME_D_HEAD={config.d_head}",
        f"-DATOME_KERNEL_SIZE={config.kernel_size}",
        f"-DATOME_TOP_K={config.top_k}",
        f"-DATOME_MAX_CLASSES={config.max_classes}",
    ]
    cmd = [
        "gcc", "-O2", "-std=c99", f"-I{_ATOME_C_DIR}", *defines,
        str(_HARNESS), str(_ATOME_C_DIR / "atome.c"), "-lm", "-o", str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"gcc failed:\n{proc.stderr}")
    return out


def run_harness(binary: Path, blob: Path, tokens: list[int]) -> tuple[int, torch.Tensor]:
    proc = subprocess.run(
        [str(binary), str(blob), " ".join(str(int(t)) for t in tokens)],
        capture_output=True, text=True, check=True,
    )
    lines = proc.stdout.strip().splitlines()
    cls = int(lines[0])
    logits = torch.tensor([float(x) for x in lines[1:]], dtype=torch.float32)
    return cls, logits


def py_class_logits(model, tokens: list[int]) -> torch.Tensor:
    model.eval()
    with torch.no_grad():
        ids = torch.tensor([list(tokens)], dtype=torch.long)
        return model.forward(ids)[0]
