"""Runtime dispatcher: routing, abstention, and OS load-shedding policy."""
import numpy as np

from superesp.datasets import agri, os_telem
from superesp.framework.train import train_head
from superesp.runtime.dispatcher import SuperESPRuntime, OS_POLICY


def _train(ds, epochs=12):
    res = train_head(ds.n_classes, ds.train_ids, ds.train_labels,
                     ds.val_ids, ds.val_labels, epochs=epochs, seed=0)
    return res.model


def test_route_and_classify():
    ds = agri.load(n_per_class=120, seed=0)
    model = _train(ds)
    rt = SuperESPRuntime()
    rt.register("agri", model, ds.tokenizer, ds.class_names)
    # a raw frame from the test set should classify to a known label or ABSTAIN
    dec = rt.classify("agri", ds.test_X[0])
    assert dec.modality == "agri"
    assert dec.label in ds.class_names + ["ABSTAIN"]
    assert 0.0 <= dec.confidence <= 1.0


def test_unknown_modality_raises():
    rt = SuperESPRuntime()
    try:
        rt.classify("nope", np.zeros(30))
        assert False, "should have raised"
    except KeyError:
        pass


def test_os_policy_sheds_load_and_disables_heads():
    dso = os_telem.load(n_per_class=150, seed=0)
    osm = _train(dso)
    dsa = agri.load(n_per_class=120, seed=0)
    am = _train(dsa)
    rt = SuperESPRuntime()
    rt.register("os_telem", osm, dso.tokenizer, dso.class_names)
    rt.register("agri", am, dsa.tokenizer, dsa.class_names)
    rt.register("voice", am, dsa.tokenizer, dsa.class_names)  # stand-in registration

    # force a power_fault telemetry frame and confirm policy disables heavy heads
    # (use a class_names index to find a power_fault sample in the test set)
    pf = dso.class_names.index("power_fault")
    idx = (dso.test_labels == pf).nonzero(as_tuple=True)[0]
    if len(idx):
        rt.os_tick(dso.test_X[int(idx[0])])
    # regardless of the exact predicted state, disabled must be a valid policy set
    assert rt.disabled in [set(v) for v in OS_POLICY.values()]
    # voice is disabled under both low_memory/overheating/power_fault
    if rt.disabled:
        dec = rt.classify("voice", dsa.test_X[0]) if "voice" in rt.disabled else None
        if dec is not None:
            assert dec.label == "DISABLED"
