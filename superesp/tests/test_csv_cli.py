"""Bring-your-own-CSV custom head: load -> train -> export round-trips."""
import csv
import tempfile
from pathlib import Path

import numpy as np

from superesp.datasets import agri
from superesp.datasets.csv_head import load_csv
from superesp.framework.train import train_head, evaluate
from superesp.framework.export import export_classifier


def _write_csv(path):
    ds = agri.load(n_per_class=120, seed=3)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([f"f{i}" for i in range(ds.test_X.shape[1])] + ["label"])
        for row, lab in zip(ds.test_X, ds.test_labels.tolist()):
            w.writerow(list(row) + [ds.class_names[lab]])


def test_csv_head_trains_and_exports():
    tmp = Path(tempfile.mkdtemp())
    csv_path = tmp / "sensor.csv"
    _write_csv(csv_path)
    ds = load_csv(csv_path, label_col="label", name="sensor")
    assert ds.source == "REAL" and ds.n_classes >= 2
    assert ds.train_ids.shape[1] <= 32
    res = train_head(ds.n_classes, ds.train_ids, ds.train_labels,
                     ds.val_ids, ds.val_labels, epochs=10, seed=0)
    ev = evaluate(res.model, ds.test_ids, ds.test_labels)
    assert 0.0 <= ev["test_acc"] <= 1.0  # pipeline runs end to end
    blob = tmp / "sensor.atomecl"
    st = export_classifier(res.model, blob)
    assert st["total_bytes"] > 0 and blob.exists()


def test_csv_rejects_too_many_features():
    tmp = Path(tempfile.mkdtemp())
    p = tmp / "wide.csv"
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([f"f{i}" for i in range(40)] + ["label"])  # 40 > MAX_SEQ 32
        w.writerow([0.0] * 40 + ["a"]); w.writerow([1.0] * 40 + ["b"])
    try:
        load_csv(p, label_col="label")
        assert False, "should reject >MAX_SEQ features"
    except ValueError:
        pass
