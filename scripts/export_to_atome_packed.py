#!/usr/bin/env python3
"""scripts/export_to_atome_packed.py — write a base-3 packed `ATOME02` binary.

**Experimental.** The C engine in `c_engine/upstream/` does not yet decode
ATOME02; this script produces research artifacts only. For an MCU-deployable
blob today, use `scripts/export_to_atome.py` (ATOME01). See `FRONTIER.md`
for the ATOME02 / ATOMEP3 status.

Identical wire layout to `export_to_atome.py` (ATOME01) except every
"packed trits" payload is laid out as

    n_trits (uint32)        # original trit count, drives padding
    packed bytes            # ceil(n_trits / 5) bytes, base-3 packed

The 5 trits/byte packing is 1.6 bits/trit — within 1 % of the
information-theoretic floor `log2(3) ≈ 1.585`, and 20 % smaller than
ATOME01's 2 bits/trit.

The C engine does NOT yet read this format — that's intentional. ATOME02
is the canonical "smallest binary" we ship. The current C decoder reads
ATOME01; a future C-side refactor will add ATOME02 support and we'll
deprecate ATOME01 then.

The unpacker `unpack_atome02()` here returns a dict of dequantized
NumPy tensors so unit tests and any future C decoder can verify
parity.

Usage:
    python scripts/export_to_atome_packed.py \\
        --checkpoint checkpoints/atome_demo.pt \\
        --output checkpoints/atome_demo.atome2
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atome_llm.core.atome_lm import AtomeLM
from atome_llm.core.ternary import absmean_scale, ternary_signs
from atome_llm.core.trit_packing import pack_trits, packed_size, unpack_trits


MAGIC = b"ATOME02"


def _write_packed_ternary(f, trits: np.ndarray, scale: float) -> int:
    """scale (f32) | packed bytes (5 trits/byte). Shape is implicit at the read site."""
    flat = trits.flatten().astype(np.int8)
    packed, _ = pack_trits(flat)
    payload = struct.pack("<f", scale) + packed
    f.write(payload)
    return len(payload)


def write_ternary(f, weight: torch.nn.Parameter) -> int:
    with torch.no_grad():
        trits = ternary_signs(weight).numpy()
        scale = absmean_scale(weight).item()
    return _write_packed_ternary(f, trits, scale)


def write_conv(f, conv_module) -> int:
    with torch.no_grad():
        w = conv_module.weight.squeeze(1)
        trits = ternary_signs(w).numpy()[:, ::-1].copy()
        scale = absmean_scale(w).item()
    return _write_packed_ternary(f, trits, scale)


def write_norm(f, norm: torch.nn.LayerNorm) -> int:
    gamma = norm.weight.detach().numpy().astype(np.float32)
    beta = norm.bias.detach().numpy().astype(np.float32)
    payload = gamma.tobytes() + beta.tobytes()
    f.write(payload)
    return len(payload)


def write_ssm(f, ssm) -> int:
    a = ssm.a_raw.detach().numpy().astype(np.float32)
    b = ssm.b.detach().numpy().astype(np.float32)
    c = ssm.c_out.detach().numpy().astype(np.float32)
    payload = a.tobytes() + b.tobytes() + c.tobytes()
    f.write(payload)
    return len(payload)


def export_model(model: AtomeLM, output: Path, verbose: bool = True) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with output.open("wb") as f:
        f.write(MAGIC); total += len(MAGIC)
        total += write_ternary(f, model.embed.weight)
        for i, block in enumerate(model.blocks):
            if verbose:
                print(f"  block {i}")
            total += write_norm(f, block.norm)
            total += write_conv(f, block.local)
            total += write_ssm(f, block.state)
            total += write_ternary(f, block.sparse.Wq.weight)
            total += write_ternary(f, block.sparse.Wk.weight)
            total += write_ternary(f, block.sparse.Wv.weight)
            total += write_ternary(f, block.router.proj.weight)
        total += write_norm(f, model.final_norm)
        total += write_ternary(f, model.unembed.weight)
    if verbose:
        print(f"exported {total} bytes ({total / 1024:.1f} KB) → {output}")
    return {"total_bytes": total, "format": "ATOME02"}


def _read_ternary_payload(buf: bytes, off: int, shape: tuple
                          ) -> tuple[np.ndarray, int]:
    """Read scale (f32) | packed bytes; shape is implicit, drives n_trits."""
    scale = struct.unpack_from("<f", buf, off)[0]; off += 4
    n_trits = int(np.prod(shape))
    nb = packed_size(n_trits)
    trits = unpack_trits(buf[off:off + nb], n_trits); off += nb
    return trits.reshape(shape).astype(np.float32) * scale, off


def unpack_atome02(path: Path, model_config: dict) -> dict:
    """Read a packed binary and return dequantized weight tensors as numpy.

    Used by tests + future C decoder to verify the file is bit-exact-
    equivalent to the in-memory model.
    """
    buf = path.read_bytes()
    if buf[:7] != MAGIC:
        raise ValueError(f"bad magic: {buf[:7]!r}")
    off = 7
    d = model_config["d_model"]
    V = model_config["vocab_size"]
    dh = model_config["d_head"]
    ks = model_config["kernel_size"]
    n_layers = model_config["n_layers"]
    out: dict = {"blocks": []}

    out["embed"], off = _read_ternary_payload(buf, off, (V, d))
    for _ in range(n_layers):
        block: dict = {}
        gamma = np.frombuffer(buf, dtype=np.float32, count=d, offset=off); off += d * 4
        beta = np.frombuffer(buf, dtype=np.float32, count=d, offset=off); off += d * 4
        block["norm_gamma"] = gamma.copy()
        block["norm_beta"] = beta.copy()
        block["conv"], off = _read_ternary_payload(buf, off, (d, ks))
        a = np.frombuffer(buf, dtype=np.float32, count=d, offset=off); off += d * 4
        b = np.frombuffer(buf, dtype=np.float32, count=d, offset=off); off += d * 4
        c = np.frombuffer(buf, dtype=np.float32, count=d, offset=off); off += d * 4
        block["ssm"] = {"a_raw": a.copy(), "b": b.copy(), "c_out": c.copy()}
        block["Wq"], off = _read_ternary_payload(buf, off, (dh, d))
        block["Wk"], off = _read_ternary_payload(buf, off, (dh, d))
        block["Wv"], off = _read_ternary_payload(buf, off, (d, d))
        block["router"], off = _read_ternary_payload(buf, off, (3, d))
        out["blocks"].append(block)
    fn_g = np.frombuffer(buf, dtype=np.float32, count=d, offset=off); off += d * 4
    fn_b = np.frombuffer(buf, dtype=np.float32, count=d, offset=off); off += d * 4
    out["final_norm_gamma"] = fn_g.copy()
    out["final_norm_beta"] = fn_b.copy()
    out["unembed"], off = _read_ternary_payload(buf, off, (V, d))
    if off != len(buf):
        raise ValueError(f"trailing data: off={off}, len={len(buf)}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    state = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    cfg = state["config"]
    model = AtomeLM(**{
        k: cfg[k] for k in
        ("vocab_size", "d_model", "n_layers", "d_head", "top_k", "kernel_size")
    })
    model.load_state_dict(state["state_dict"])
    model.eval()
    export_model(model, args.output)


if __name__ == "__main__":
    main()
