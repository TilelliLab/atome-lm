"""On-device editable classes: add/remove works; few-shot transfer beats chance."""
import numpy as np
import torch

from superesp.datasets import agri
from superesp.framework.train import train_head
from superesp.framework.editable import PrototypeHead


def _backbone_excluding(ds, held):
    m = ds.train_labels != held
    vm = ds.val_labels != held
    res = train_head(ds.n_classes - 1, ds.train_ids[m], _relabel(ds.train_labels[m], held),
                     ds.val_ids[vm], _relabel(ds.val_labels[vm], held), epochs=12, seed=0)
    return res.model


def _relabel(labels, held):
    # compress labels >held by 1 so they are contiguous 0..n-2
    out = labels.clone()
    out[labels > held] -= 1
    return out


def test_add_remove_and_few_shot_beats_chance():
    ds = agri.load(n_per_class=150, seed=0)
    names = ds.class_names
    held = ds.n_classes - 1                      # last class never trained
    model = _backbone_excluding(ds, held)
    ph = PrototypeHead(backbone=model)

    rng = np.random.default_rng(0)
    for c in range(ds.n_classes):
        idx = (ds.train_labels == c).nonzero(as_tuple=True)[0].numpy()
        sup = ds.train_ids[rng.choice(idx, size=min(10, len(idx)), replace=False)]
        ph.add_class(names[c], sup)
    assert len(ph._order) == ds.n_classes

    # never-trained class recognized above chance from 10 examples
    m = ds.test_labels == held
    acc_new = ph.accuracy(ds.test_ids[m], [names[held]] * int(m.sum()))
    assert acc_new > 1.0 / ds.n_classes          # beats uniform chance

    # remove is reversible
    ph.remove_class(names[held])
    assert len(ph._order) == ds.n_classes - 1
