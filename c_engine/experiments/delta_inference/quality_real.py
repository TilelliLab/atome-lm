#!/usr/bin/env python3
"""
quality_real.py — TEST 3: the downstream-quality cost of delta inference.

The delta experiment measured ENERGY (iteration count). The critic's fair hit:
nobody measured what the thresholding ERROR does to model OUTPUT quality. This
script measures exactly that, on the real 944K model.

Method: delta inference on a matvec that consumes signal S is *equivalent* to
feeding the exact matvec an integrate-and-fire-thresholded version of S (the
consumer sees the last propagated value for un-fired channels). So we hook each
block's diagonal-SSM output, replace it with its thresholded reconstruction,
run the rest of the model exactly, and measure cross-entropy loss vs the
untouched model. Sweep threshold → honest energy/quality tradeoff curve.
"""
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from atome_llm.core.atome_lm import AtomeLM  # noqa: E402

CKPT = ROOT / "checkpoints" / "atome_1m_v1.pt"
THRESHOLDS = [0.0, 0.02, 0.05, 0.10, 0.20]

# Held-out TinyStories-style text — NOT the capture_real.py passage.
TEXT = (
    "Tom had a small red kite. He took it to the park on a windy day. "
    "The kite went up high into the blue sky. Tom was very happy and "
    "laughed. Then the wind stopped and the kite came down slowly. "
    "Tom picked it up and ran home to show his mom the pretty kite."
)


def load_model():
    ckpt = torch.load(CKPT, map_location="cpu", weights_only=True)
    cfg = ckpt["config"]
    m = AtomeLM(vocab_size=cfg.get("vocab_size", 256), d_model=cfg["d_model"],
                n_layers=cfg["n_layers"], d_head=cfg["d_head"], top_k=cfg["top_k"],
                kernel_size=cfg.get("kernel_size", 5))
    m.load_state_dict(ckpt["state_dict"])
    m.eval()
    return m


def integrate_and_fire(sig: np.ndarray, threshold: float) -> np.ndarray:
    """sig: (L, C). Return the signal a delta consumer actually sees: each
    channel holds its last propagated value until it next crosses threshold.
    Identical bookkeeping to the C dm_matvec_delta primitive."""
    L, C = sig.shape
    out = sig.copy()
    x_prev = sig[0].copy()
    for t in range(1, L):
        d = sig[t] - x_prev
        fire = np.abs(d) > threshold
        x_prev[fire] = sig[t][fire]
        out[t] = x_prev          # un-fired channels keep the stale value
    return out


def loss_at(model, ids, threshold):
    """Cross-entropy with each block's SSM output integrate-and-fire-thresholded."""
    handles = []
    if threshold > 0.0:
        def mk(_li):
            def hook(_m, _i, out):
                arr = out.detach()[0].float().numpy()         # (L, C)
                approx = integrate_and_fire(arr, threshold)
                return torch.from_numpy(approx).unsqueeze(0).to(out.dtype)
            return hook
        for li, blk in enumerate(model.blocks):
            handles.append(blk.state.register_forward_hook(mk(li)))
    try:
        with torch.no_grad():
            logits = model(ids)                                # (1, L, V)
            tgt = ids[0, 1:]
            lg = logits[0, :-1]
            loss = F.cross_entropy(lg, tgt)
    finally:
        for h in handles:
            h.remove()
    return float(loss)


def main():
    model = load_model()
    ids = torch.tensor([[b for b in TEXT.encode("utf-8")]], dtype=torch.long)

    # Energy side: per-threshold SSM-pathway speedup, measured the same way as
    # capture_real.py (mean channels that fire → d_model / mean_fired).
    caps = {}
    hs = []
    for li, blk in enumerate(model.blocks):
        def mk(name):
            def h(_m, _i, o): caps[name] = o.detach()[0].float().numpy()
            return h
        hs.append(blk.state.register_forward_hook(mk(f"L{li}.ssm")))
    with torch.no_grad():
        model(ids)
    for h in hs:
        h.remove()
    d_model = caps["L0.ssm"].shape[1]

    def speedup(thr):
        sps = []
        for li in range(len(model.blocks)):
            sig = caps[f"L{li}.ssm"]
            L = sig.shape[0]
            x_prev = sig[0].copy()
            fired = []
            for t in range(1, L):
                d = sig[t] - x_prev
                f = np.abs(d) > thr
                fired.append(int(f.sum()))
                x_prev[f] = sig[t][f]
            sps.append(d_model / max(np.mean(fired), 1e-6))
        return float(np.mean(sps))

    base = loss_at(model, ids, 0.0)
    base_ppl = float(np.exp(base))

    print("=== TEST 3 — delta-inference quality cost (real 944K model) ===")
    print(f"checkpoint val_loss=1.0545 | test text {ids.shape[1]} bytes")
    print(f"baseline (exact): loss={base:.4f}  ppl={base_ppl:.3f}\n")
    print("  threshold | SSM-path speedup | loss   | Δloss   | ppl     | Δppl%")
    print("  " + "-" * 64)
    rows = []
    for thr in THRESHOLDS:
        sp = speedup(thr)
        loss = loss_at(model, ids, thr)
        ppl = float(np.exp(loss))
        dloss = loss - base
        dppl = 100.0 * (ppl - base_ppl) / base_ppl
        rows.append((thr, sp, loss, dloss, ppl, dppl))
        print(f"  {thr:8.2f}  | {sp:13.2f}x  | {loss:.4f} | {dloss:+.4f} | "
              f"{ppl:7.3f} | {dppl:+6.2f}%")

    print("\nHonest reading:")
    print("  threshold 0.0 must show Δloss≈0 (delta is exact there).")
    print("  The real question: at the threshold where speedup is large, is")
    print("  Δloss small enough to ship? If ppl blows up, the energy number")
    print("  is a dead end and must be reported as such.")
    return rows


if __name__ == "__main__":
    main()
