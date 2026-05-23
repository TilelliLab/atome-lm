#!/usr/bin/env python3
"""
capture_real.py — validate delta inference on the real 944K Atome model.

Loads checkpoints/atome_1m_v1.pt, runs a real TinyStories-style text through
it, and measures — per block, per pathway — how position-to-position
correlated each signal is. The delta-matvec speedup of a layer that consumes
a signal is d_model / (mean channels that change beyond threshold), using the
exact integrate-and-fire semantics of the C primitive (selective x_prev
update, so per-channel error stays <= threshold).

Also dumps real traces for the C cross-check (bench_real.c):
  traces/h_block0.f32        — post-norm residual stream feeding the pathways
  traces/ssm_block0.f32      — DiagonalSSM pathway output (the slow signal)
  traces/wv_block0.tern      — real ternarized attention Wv (256x256), packed

Honest finding up front: the SSM itself is a per-channel recurrence
(h_t = a*h_{t-1} + b*x_t) — every step depends on the last, so it cannot be
delta-skipped. Its value to delta inference is indirect: it emits the
slowest-changing signal in the block, which makes the matvec DOWNSTREAM of it
the most delta-friendly. This script measures exactly that.
"""
import json
import struct
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from atome_llm.core.atome_lm import AtomeLM           # noqa: E402
from atome_llm.core.ternary import absmean_scale, ternary_signs  # noqa: E402

CKPT = ROOT / "checkpoints" / "atome_1m_v1.pt"
OUT = Path(__file__).resolve().parent / "traces"
OUT.mkdir(exist_ok=True)

THRESHOLDS = [0.0, 0.02, 0.05, 0.10]

# A real TinyStories-style passage — the model's training distribution.
TEXT = (
    "Once upon a time, there was a little girl named Lily. She loved to "
    "play in the garden with her dog. One sunny day, they found a shiny "
    "red ball under the big tree and played all afternoon together."
)


def load_model():
    ckpt = torch.load(CKPT, map_location="cpu", weights_only=False)
    cfg = ckpt["config"]
    model = AtomeLM(
        vocab_size=cfg.get("vocab_size", 256),
        d_model=cfg["d_model"],
        n_layers=cfg["n_layers"],
        d_head=cfg["d_head"],
        top_k=cfg["top_k"],
        kernel_size=cfg.get("kernel_size", 5),
    )
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    return model, cfg


def delta_redundancy(sig: np.ndarray, threshold: float):
    """sig: (L, C). Replicates dm_matvec_delta's integrate-and-fire bookkeeping
    and returns (mean changed channels per step, max pending |error|)."""
    L, C = sig.shape
    x_prev = sig[0].copy()
    changed = []
    max_pending = 0.0
    for t in range(1, L):
        d = sig[t] - x_prev
        fire = np.abs(d) > threshold
        changed.append(int(fire.sum()))
        max_pending = max(max_pending, float(np.abs(d[~fire]).max() if (~fire).any() else 0.0))
        x_prev[fire] = sig[t][fire]  # selective update — bounds error by threshold
    return float(np.mean(changed)), max_pending


def main():
    torch.manual_seed(0)
    model, cfg = load_model()
    d_model, n_layers = cfg["d_model"], cfg["n_layers"]

    ids = torch.tensor([[b for b in TEXT.encode("utf-8")]], dtype=torch.long)
    L = ids.shape[1]

    # Hook the post-norm input (h) and each pathway output, per block.
    caps = {}

    def hook(name):
        def fn(_m, _i, out):
            caps[name] = out.detach()[0].float().numpy()  # (L, C)
        return fn

    handles = []
    for li, blk in enumerate(model.blocks):
        handles.append(blk.norm.register_forward_hook(hook(f"L{li}.h")))
        handles.append(blk.local.register_forward_hook(hook(f"L{li}.conv")))
        handles.append(blk.state.register_forward_hook(hook(f"L{li}.ssm")))
        handles.append(blk.sparse.register_forward_hook(hook(f"L{li}.attn")))

    with torch.no_grad():
        model(ids)
    for h in handles:
        h.remove()

    print("=== Delta inference on REAL 944K Atome weights ===")
    print(f"checkpoint: {CKPT.name}  val_loss=1.0545  d_model={d_model} "
          f"n_layers={n_layers}")
    print(f'input: {L} real bytes of TinyStories text\n')
    print("Per-signal delta-matvec speedup (= d_model / mean changed channels).")
    print("A matvec consuming this signal would run this much less work.\n")

    # Aggregate across blocks for each signal kind.
    kinds = ["h", "conv", "ssm", "attn"]
    summary = {k: {t: [] for t in THRESHOLDS} for k in kinds}
    for li in range(n_layers):
        for k in kinds:
            sig = caps[f"L{li}.{k}"]
            for t in THRESHOLDS:
                mc, _ = delta_redundancy(sig, t)
                summary[k][t].append(d_model / max(mc, 1e-6))

    label = {"h": "post-norm input h", "conv": "conv pathway out",
             "ssm": "SSM pathway out", "attn": "attention pathway out"}
    hdr = "  signal               " + "".join(f"  thr={t:<6}" for t in THRESHOLDS)
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for k in kinds:
        row = f"  {label[k]:<20}"
        for t in THRESHOLDS:
            row += f"  {np.mean(summary[k][t]):8.2f}x"
        print(row)

    # Error bound check at the largest threshold.
    print()
    worst = 0.0
    for li in range(n_layers):
        for k in kinds:
            _, mp = delta_redundancy(caps[f"L{li}.{k}"], THRESHOLDS[-1])
            worst = max(worst, mp)
    print(f"max pending per-channel error at thr={THRESHOLDS[-1]}: {worst:.5f} "
          f"(<= threshold by construction — integrate-and-fire)")

    # Block-0-specific prediction — what bench_real.c (which uses only the
    # block-0 traces) must reproduce. Kept separate from the 8-block average
    # above so the C cross-check is apples-to-apples.
    print("\nblock-0 prediction (cross-check target for bench_real.c):")
    blk0 = {}
    for k in ("h", "ssm"):
        sig = caps[f"L0.{k}"]
        blk0[k] = {}
        line = f"  L0.{k:<4}"
        for t in THRESHOLDS:
            mc, _ = delta_redundancy(sig, t)
            sp = d_model / max(mc, 1e-6)
            blk0[k][str(t)] = sp
            line += f"  thr={t}:{sp:7.2f}x"
        print(line)

    # ---- dump real traces for the C cross-check (block 0) ----
    h0 = caps["L0.h"].astype(np.float32)
    ssm0 = caps["L0.ssm"].astype(np.float32)
    (OUT / "h_block0.f32").write_bytes(h0.tobytes())
    (OUT / "ssm_block0.f32").write_bytes(ssm0.tobytes())

    # real attention Wv (256x256), ternarized exactly as the engine does, packed
    # 4 trits/byte (00=0 01=+1 11=-1).
    wv = model.blocks[0].sparse.Wv.weight.detach()
    scale = float(absmean_scale(wv))
    signs = ternary_signs(wv).numpy().astype(np.int8)  # {-1,0,+1}, shape (256,256)
    rows, cols = signs.shape
    flat = signs.reshape(-1)
    packed = bytearray((flat.size + 3) // 4)
    for idx, s in enumerate(flat):
        code = 1 if s == 1 else (3 if s == -1 else 0)
        packed[idx >> 2] |= code << ((idx & 3) * 2)
    with open(OUT / "wv_block0.tern", "wb") as f:
        f.write(struct.pack("<iif", rows, cols, scale))
        f.write(bytes(packed))

    manifest = {
        "checkpoint": CKPT.name, "d_model": d_model, "n_layers": n_layers,
        "seq_len": L, "wv_scale": scale, "wv_shape": [rows, cols],
        "traces": {
            "h_block0.f32": [L, d_model],
            "ssm_block0.f32": [L, d_model],
            "wv_block0.tern": "int32 rows, int32 cols, float32 scale, packed trits",
        },
        "thresholds": THRESHOLDS,
        "speedup_h": {str(t): float(np.mean(summary["h"][t])) for t in THRESHOLDS},
        "speedup_ssm": {str(t): float(np.mean(summary["ssm"][t])) for t in THRESHOLDS},
        "speedup_conv": {str(t): float(np.mean(summary["conv"][t])) for t in THRESHOLDS},
        "speedup_attn": {str(t): float(np.mean(summary["attn"][t])) for t in THRESHOLDS},
        "block0_h": blk0["h"],
        "block0_ssm": blk0["ssm"],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\ntraces + manifest written to {OUT}/")
    print("next: `make real` cross-checks the C delta primitive on these traces.")


if __name__ == "__main__":
    main()
