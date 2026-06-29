"""Change-gated streaming: decisions stay exact; correlated streams skip frames."""
import numpy as np

from superesp.datasets import agri
from superesp.framework.train import train_head
from superesp.framework.streaming import StreamingClassifier


def _model_and_ds():
    ds = agri.load(n_per_class=150, seed=0)
    res = train_head(ds.n_classes, ds.train_ids, ds.train_labels,
                     ds.val_ids, ds.val_labels, epochs=12, seed=0)
    return res.model, ds


def test_gate_emits_exact_decisions():
    model, ds = _model_and_ds()
    sc = StreamingClassifier(model, ds.tokenizer, ds.class_names, fire_threshold=0.05)
    # feed distinct frames; whenever the gate COMPUTES, it must equal direct classify
    for i in range(40):
        frame = ds.test_X[i]
        label, conf, margin, computed = sc.push(frame)
        if computed:
            direct = sc._classify(frame)
            assert label == (direct[0])


def test_identical_stream_skips_almost_all():
    model, ds = _model_and_ds()
    sc = StreamingClassifier(model, ds.tokenizer, ds.class_names, fire_threshold=0.05)
    frame = ds.test_X[0]
    for _ in range(100):
        sc.push(frame)  # identical frame every time
    # first frame computes, the rest are served from cache
    assert sc.stats.computed == 1
    assert sc.stats.skip_rate > 0.98


def test_slow_stream_saves_compute():
    model, ds = _model_and_ds()
    sc = StreamingClassifier(model, ds.tokenizer, ds.class_names, fire_threshold=0.05)
    # slowly drifting stream between two real frames
    a, b = ds.test_X[0], ds.test_X[1]
    for t in np.linspace(0, 1, 100):
        sc.push((1 - t) * a + t * b)
    # a slow ramp should skip a meaningful fraction
    assert sc.stats.skip_rate > 0.3
    assert sc.stats.speedup > 1.4
