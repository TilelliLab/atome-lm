"""Framework smoke tests on the fast synthetic agri head (no slow real data)."""
import numpy as np
import torch

from superesp.datasets import agri
from superesp.framework.model import SuperESPHead
from superesp.framework.tokenize import FeatureTokenizer
from superesp.framework.train import train_head, evaluate
from superesp.framework import abstain, delta


def _small_ds():
    return agri.load(n_per_class=120, seed=0)


def test_tokenizer_range_and_leakfree():
    X = np.random.RandomState(0).randn(50, 10) * 5
    tok = FeatureTokenizer.fit(X)
    t = tok.transform(X)
    assert t.dtype == torch.int64
    assert int(t.min()) >= 0 and int(t.max()) <= 255
    # values outside fitted range clamp, never overflow the byte vocab
    big = tok.transform(X * 100)
    assert int(big.max()) <= 255 and int(big.min()) >= 0


def test_model_forward_shape():
    m = SuperESPHead(n_classes=5)
    ids = torch.randint(0, 256, (4, 12))
    out = m.forward(ids)
    assert out.shape == (4, 5)
    assert m.parameter_count() < 25000  # stays tiny


def test_train_eval_held_out():
    ds = _small_ds()
    res = train_head(ds.n_classes, ds.train_ids, ds.train_labels,
                     ds.val_ids, ds.val_labels, epochs=15, seed=0)
    ev = evaluate(res.model, ds.test_ids, ds.test_labels)
    # synthetic agri is learnable; require clearly-better-than-chance on HELD-OUT
    assert ev["test_acc"] > 0.6
    assert ev["n_test"] == ds.test_ids.shape[0]


def test_abstain_beats_random_and_brackets_oracle():
    ds = _small_ds()
    res = train_head(ds.n_classes, ds.train_ids, ds.train_labels,
                     ds.val_ids, ds.val_labels, epochs=15, seed=0)
    ev = evaluate(res.model, ds.test_ids, ds.test_labels)
    rc = abstain.risk_coverage(ev["probs"], ev["labels"])
    assert rc["oracle_aurc"] <= rc["aurc"] <= rc["random_aurc"] + 1e-9


def test_delta_speedup_and_bounded_error():
    W = (np.random.RandomState(1).randn(32, 32))
    W[np.abs(W) < 0.4] = 0.0  # ~ternary sparsity
    # correlated stream: slow drift
    base = np.cumsum(np.random.RandomState(2).randn(100, 32) * 0.01, axis=0)
    r = delta.delta_matvec_stream(W, base, threshold=0.05)
    assert r["iter_speedup"] > 1.0
    assert r["max_abs_error"] <= 0.05 * 32 + 1e-6  # bounded by thr * row width
