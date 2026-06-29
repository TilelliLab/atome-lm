"""superesp.train_all — train, evaluate (held-out), abstain, delta, export all 7 heads.

Writes one ATOMECL01 blob + a tokenizer json per head to superesp/artifacts/,
and a machine-readable superesp/artifacts/RESULTS.json. Every row records
REAL vs SYNTH data, TEST accuracy (held-out), abstention AURC vs oracle/random,
and the delta-inference iter-speedup with bounded error.

Run:  python3 -m superesp.train_all
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch
from atome_llm.core.ternary import ternary_signs, absmean_scale

from superesp.heads import HEADS
from superesp.framework.train import train_head, evaluate
from superesp.framework import abstain, delta
from superesp.framework.export import export_classifier

ART = Path(__file__).resolve().parent / "artifacts"


def _delta_probe(model, ds) -> dict:
    """Delta-inference iter-speedup on a CONTINUOUS correlated sensor stream.

    Only meaningful for time-series heads (ds.stream_shape = (T, C)): we unfold
    the test windows into one long (n*T, C) stream of consecutive timesteps —
    the always-on sensor signal — pad channels to d_model, and run the
    integrate-and-fire delta matvec through block-0 Wv. Tabular heads (HAR
    features / MFCC) have no temporal stream, so delta does not apply (N/A).
    """
    if ds.stream_shape is None:
        return {"applicable": False, "reason": "tabular head, no temporal stream"}
    T, C = ds.stream_shape
    w = model.base.blocks[0].sparse.Wv.weight
    Wv = (ternary_signs(w) * absmean_scale(w)).detach().numpy()
    d = model.config.d_model
    raw = ds.test_X[:80].reshape(-1, T, C).reshape(-1, C)  # (n*T, C) consecutive steps
    # standardize channels so the firing threshold is in a comparable scale
    mu, sd = raw.mean(0), raw.std(0) + 1e-9
    raw = (raw - mu) / sd
    streamd = np.zeros((raw.shape[0], d))
    streamd[:, : min(C, d)] = raw[:, : min(C, d)]
    out = {"applicable": True}
    for thr in (0.02, 0.05, 0.10):
        r = delta.delta_matvec_stream(Wv, streamd, thr)
        out[f"thr_{thr}"] = {"speedup": round(r["iter_speedup"], 2),
                             "max_err": round(r["max_abs_error"], 4)}
    return out


def run(epochs: int = 40, seed: int = 0, verbose: bool = True) -> dict:
    ART.mkdir(parents=True, exist_ok=True)
    rows = []
    for head in HEADS:
        t0 = time.time()
        ds = head.loader(seed=seed)
        res = train_head(ds.n_classes, ds.train_ids, ds.train_labels,
                         ds.val_ids, ds.val_labels, epochs=epochs, seed=seed)
        ev = evaluate(res.model, ds.test_ids, ds.test_labels)
        rc = abstain.risk_coverage(ev["probs"], ev["labels"])
        cov5 = abstain.coverage_at_risk(ev["probs"], ev["labels"], 0.05)
        dprobe = _delta_probe(res.model, ds)

        blob = ART / f"{head.name}.atomecl"
        st = export_classifier(res.model, blob)
        (ART / f"{head.name}.tok.json").write_text(json.dumps(ds.tokenizer.to_dict()))

        row = {
            "head": head.name, "title": head.title, "source": ds.source,
            "classes": ds.class_names, "n_classes": ds.n_classes,
            "n_features": int(ds.train_ids.shape[1]),
            "params": res.model.parameter_count(),
            "test_acc": round(ev["test_acc"], 4),
            "n_test": ev["n_test"],
            "abstain_aurc": round(rc["aurc"], 4),
            "oracle_aurc": round(rc["oracle_aurc"], 4),
            "random_aurc": round(rc["random_aurc"], 4),
            "coverage_at_5pct_risk": round(cov5, 3),
            "blob_bytes": st["total_bytes"],
            "delta": dprobe,
            "train_s": round(time.time() - t0, 1),
        }
        rows.append(row)
        if verbose:
            print(f"[{head.name:11s}] {ds.source:5s} acc={row['test_acc']:.3f} "
                  f"AURC={row['abstain_aurc']:.4f}(orac {row['oracle_aurc']:.4f}) "
                  f"cov@5%={row['coverage_at_5pct_risk']:.2f} "
                  f"bytes={st['total_bytes']} {row['train_s']}s")
    out = {"config": HEADS[0].loader.__module__ and "shared", "heads": rows}
    (ART / "RESULTS.json").write_text(json.dumps(rows, indent=2))
    return {"heads": rows}


if __name__ == "__main__":
    run()
