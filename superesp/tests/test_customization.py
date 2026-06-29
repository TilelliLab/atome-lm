"""Easy-customization loop: log-parse, new-template round-trip, report rendering."""
import csv
import tempfile
from pathlib import Path

import numpy as np

from superesp.cli import parse_logger_lines, _append_csv
from superesp.datasets.csv_head import load_csv
from superesp.datasets import agri
from superesp.framework.train import train_head, evaluate
from superesp.framework import abstain, report


def test_logger_line_parsing():
    lines = [
        "SUPERESP LOGGER (agri 6x5 frame).\n",
        "CSV_HEADER,t0_soil,t0_airT,t0_hum\n",
        "CSV,40.0,22.5,60.0\n",
        "noise line\n",
        "CSV,38.0,23.0,58.0\n",
    ]
    header, rows = parse_logger_lines(lines)
    assert header == ["t0_soil", "t0_airT", "t0_hum"]
    assert rows == [["40.0", "22.5", "60.0"], ["38.0", "23.0", "58.0"]]
    # max_frames stops early
    _, r2 = parse_logger_lines(lines, max_frames=1)
    assert len(r2) == 1


def test_log_csv_roundtrips_into_training():
    """Simulated capture -> labeled CSV (2 classes) -> load_csv -> trains."""
    tmp = Path(tempfile.mkdtemp())
    out = tmp / "field.csv"
    rng = np.random.default_rng(0)
    for label, base in [("healthy", 50.0), ("needs_irrigate", 15.0)]:
        rows = [[f"{base + rng.normal(0, 3):.3f}" for _ in range(6)] for _ in range(40)]
        hdr = [f"f{i}" for i in range(6)]
        _append_csv(out, hdr, rows, label)
    ds = load_csv(out, label_col="label", name="field")
    assert ds.source == "REAL" and ds.n_classes == 2
    res = train_head(ds.n_classes, ds.train_ids, ds.train_labels,
                     ds.val_ids, ds.val_labels, epochs=8, seed=0)
    ev = evaluate(res.model, ds.test_ids, ds.test_labels)
    assert ev["test_acc"] > 0.7   # two well-separated classes are learnable


def test_report_confusion_sums_and_files():
    ds = agri.load(n_per_class=120, seed=0)
    res = train_head(ds.n_classes, ds.train_ids, ds.train_labels,
                     ds.val_ids, ds.val_labels, epochs=10, seed=0)
    ev = evaluate(res.model, ds.test_ids, ds.test_labels)
    rc = abstain.risk_coverage(ev["probs"], ev["labels"])
    tmp = Path(tempfile.mkdtemp())
    paths = report.write_report("agri", ds.class_names, ev, rc, tmp)
    # confusion matrix totals == n_test; files written
    assert sum(sum(r) for r in ev["confusion"]) == ev["n_test"]
    assert 0.0 <= rc["aurc"] <= 1.0
    assert Path(paths["md"]).exists() and Path(paths["html"]).exists()
