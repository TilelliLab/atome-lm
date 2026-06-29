"""Tamper-evident decision audit log + runtime integration."""
import numpy as np

from superesp.datasets import agri
from superesp.framework.train import train_head
from superesp.framework.audit import AuditLog
from superesp.runtime.dispatcher import SuperESPRuntime


def test_chain_verifies_and_detects_tamper():
    log = AuditLog()
    for i in range(8):
        log.append(modality="agri", model_sha256="abc123" * 8,
                   tokens=[i, i + 1, i + 2], label="healthy", margin=0.4)
    ok, bad = log.verify()
    assert ok and bad == -1
    # tamper with a past decision's label
    log.entries[3]["label"] = "irrigate"
    ok, bad = log.verify()
    assert not ok and bad == 3


def test_reorder_detected():
    log = AuditLog()
    for i in range(5):
        log.append(modality="m", model_sha256="x" * 64, tokens=[i], label="a", margin=0.5)
    log.entries[1], log.entries[2] = log.entries[2], log.entries[1]
    ok, _ = log.verify()
    assert not ok


def test_runtime_logs_decisions_and_event_gate_skips():
    ds = agri.load(n_per_class=120, seed=0)
    res = train_head(ds.n_classes, ds.train_ids, ds.train_labels,
                     ds.val_ids, ds.val_labels, epochs=10, seed=0)
    rt = SuperESPRuntime(audit=AuditLog(), fire_threshold=0.05)
    rt.register("agri", res.model, ds.tokenizer, ds.class_names, model_sha256="d" * 64)
    frame = ds.test_X[0]
    rt.classify("agri", frame)          # computes + logs
    rt.classify("agri", frame)          # identical -> event-gate reuses, NO new log entry
    assert len(rt.audit.entries) == 1
    # a frame perturbed well beyond the fire threshold MUST trigger a compute+log
    span = ds.tokenizer.vmax - ds.tokenizer.vmin
    rt.classify("agri", frame + span)   # +100% of range on every feature
    assert len(rt.audit.entries) == 2
    ok, _ = rt.audit.verify()
    assert ok
