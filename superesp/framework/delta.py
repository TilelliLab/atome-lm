"""superesp.framework.delta — delta-inference energy proxy for streaming heads.

Ports the measured result from c_engine/experiments/delta_inference/RESULTS.md:
for a *correlated* sensor stream, a ternary matvec can be computed
incrementally as  out_new = out_old + W @ (x_new - x_prev), updating x_prev
only for channels whose drift crosses a firing threshold (integrate-and-fire).
The energy proxy is the inner-loop iteration count (each trip ~1 MCU cycle).

This simulator runs the EXACT integrate-and-fire delta over a real stream of
input vectors and reports the iteration-count speedup vs full recompute, plus
the max output error (bounded by threshold * row-L1 of W). It is the honest,
deterministic energy proxy — not a wall-clock claim.
"""
from __future__ import annotations

import numpy as np


def delta_matvec_stream(W: np.ndarray, stream: np.ndarray, threshold: float) -> dict:
    """W: (out, in) weights. stream: (T, in) input vectors over time.

    Returns iteration counts for full vs delta and the max abs output error
    vs exact full recompute.
    """
    W = np.asarray(W, dtype=np.float64)
    stream = np.asarray(stream, dtype=np.float64)
    T, n_in = stream.shape
    out_dim = W.shape[0]
    assert W.shape[1] == n_in

    nz_cols_per_row = np.count_nonzero(W, axis=1)  # for delta iter accounting
    full_iters = 0
    delta_iters = 0
    max_err = 0.0

    x_prev = np.zeros(n_in)
    out = np.zeros(out_dim)
    out_exact = np.zeros(out_dim)
    first = True
    for t in range(T):
        x = stream[t]
        # Full recompute cost: every (out,in) trit is visited.
        full_iters += out_dim * n_in
        out_exact = W @ x

        if first:
            out = W @ x
            x_prev = x.copy()
            delta_iters += out_dim * n_in  # first frame is a full compute
            first = False
        else:
            dx = x - x_prev
            fire = np.abs(dx) >= threshold  # channels that cross the bar
            # delta cost ~ (#fired input channels) * out_dim trit visits
            delta_iters += int(fire.sum()) * out_dim
            if fire.any():
                out = out + W[:, fire] @ dx[fire]
                x_prev = x_prev.copy()
                x_prev[fire] = x[fire]  # integrate-and-fire: only fired channels update
        max_err = max(max_err, float(np.max(np.abs(out - out_exact))))

    speedup = full_iters / max(delta_iters, 1)
    return {
        "full_iters": full_iters,
        "delta_iters": delta_iters,
        "iter_speedup": speedup,
        "max_abs_error": max_err,
        "threshold": threshold,
        "T": T,
        "mean_nz_cols_per_row": float(nz_cols_per_row.mean()),
    }
