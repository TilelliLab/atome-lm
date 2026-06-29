"""Python<->C bit-exact parity for a trained SuperESP classifier head.

Skipped (never silently passed) if gcc or the upstream Atome C engine is absent.
"""
import tempfile
from pathlib import Path

import pytest
import torch

from superesp.datasets import agri
from superesp.framework.train import train_head
from superesp.framework.export import export_classifier
from superesp.framework import parity


@pytest.mark.skipif(not parity.gcc_available(), reason="gcc not available")
@pytest.mark.skipif(not parity.atome_c_available(), reason="upstream atome.c absent")
def test_classifier_python_c_parity():
    ds = agri.load(n_per_class=120, seed=0)
    res = train_head(ds.n_classes, ds.train_ids, ds.train_labels,
                     ds.val_ids, ds.val_labels, epochs=10, seed=0)
    model = res.model

    tmp = Path(tempfile.mkdtemp())
    blob = tmp / "agri.atomecl"
    export_classifier(model, blob)
    binary = parity.build_harness(tmp)

    max_diff = 0.0
    for i in range(6):
        toks = ds.test_ids[i].tolist()
        cls_c, logits_c = parity.run_harness(binary, blob, toks)
        logits_py = parity.py_class_logits(model, toks)
        max_diff = max(max_diff, (logits_c - logits_py).abs().max().item())
        # the on-device decision MUST match the Python decision
        assert cls_c == int(logits_py.argmax())
    # bit-exact within float associativity tolerance (project bound ~3.7e-7)
    assert max_diff < 1e-3, f"logits diverged: max|Δ|={max_diff}"
