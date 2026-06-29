"""superesp.framework.export — write a SuperESPHead to the ATOMECL01 blob.

Reuses the exact ternary/conv/norm/ssm serializers from
`scripts/export_to_atome.py` so the bytes are identical to what the C loader
`atome_classifier_load` (c_engine/upstream/atome.c) reads:

    "ATOMECL01"                  (9 bytes magic)
    n_classes                    (int32 little-endian)
    <ATOME01 body w/o magic>     embed, [blocks], final_norm, unembed
    head ternary                 (n_classes, d_model)
"""
from __future__ import annotations

import importlib.util
import struct
import sys
from pathlib import Path

def _find_export_script() -> Path | None:
    """Locate scripts/export_to_atome.py by walking up from this file.

    Works from a source checkout or an editable install (files stay in place).
    A non-editable wheel install has no scripts/ dir; in that case exporting a
    new blob needs a source checkout, so we defer a clear error to call time
    rather than crashing at import (read-only commands stay usable).
    """
    for base in Path(__file__).resolve().parents:
        cand = base / "scripts" / "export_to_atome.py"
        if cand.exists():
            sys.path.insert(0, str(base))
            return cand
    return None

_SCRIPT = _find_export_script()
if _SCRIPT is not None:
    _spec = importlib.util.spec_from_file_location("_atome_export", _SCRIPT)
    _exp = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_exp)
    write_ternary = _exp.write_ternary
    write_conv = _exp.write_conv
    write_norm = _exp.write_norm
    write_ssm = _exp.write_ssm
else:
    def _need_checkout(*_a, **_k):
        raise RuntimeError(
            "Exporting a blob needs the Atome source tree (scripts/export_to_atome.py).\n"
            "Install from a checkout:  git clone …/atome-lm && pip install -e .\n"
            "(A plain wheel install can run read-only commands but not train/export.)"
        )
    write_ternary = write_conv = write_norm = write_ssm = _need_checkout

MAGIC = b"ATOMECL01"


def export_classifier(model, output: Path) -> dict:
    """Write `model` (SuperESPHead) to `output` as an ATOMECL01 blob."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    base = model.base
    total = 0
    with output.open("wb") as f:
        f.write(MAGIC)
        total += len(MAGIC)
        f.write(struct.pack("<i", model.n_classes))
        total += 4
        # ATOME01 body without its own magic:
        total += write_ternary(f, base.embed.weight)
        for block in base.blocks:
            total += write_norm(f, block.norm)
            total += write_conv(f, block.local)
            total += write_ssm(f, block.state)
            total += write_ternary(f, block.sparse.Wq.weight)
            total += write_ternary(f, block.sparse.Wk.weight)
            total += write_ternary(f, block.sparse.Wv.weight)
            total += write_ternary(f, block.router.proj.weight)
        total += write_norm(f, base.final_norm)
        total += write_ternary(f, base.unembed.weight)
        # Classification head:
        total += write_ternary(f, model.head.weight)
    return {"total_bytes": total, "n_classes": model.n_classes}
