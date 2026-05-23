#!/usr/bin/env python3
"""scripts/export_to_atome_p3.py — write a power-of-3 ATOME-P3 binary.

**Experimental.** The C engine in `c_engine/upstream/` does not yet decode
ATOMEP3; this script produces research artifacts only. For an
MCU-deployable blob today, use `scripts/export_to_atome.py` (ATOME01).
See `FRONTIER.md` for the ATOMEP3 / ATOME02 status.

Identical wire layout to ATOME01 except every quantized payload stores
3-bit power-of-3 codes (3 bits / weight, 8 codes per 3 bytes), not
2-bit ternary trits (2 bits / trit, 4 trits per byte).

Header magic is "ATOMEP3" so a reader can dispatch by magic. The C
engine does NOT yet read this format — that's a separate change.

For comparison vs ATOME01 / ATOME02 on the same trained checkpoint,
this script also prints the size delta in bytes and percent.
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
from atome_llm.core.p3_packing import pack_p3, packed_size, unpack_p3
from atome_llm.core.power3 import power3_codes
from atome_llm.core.ternary import absmean_scale


MAGIC = b"ATOMEP3"


def _write_p3(f, weight: torch.Tensor) -> int:
    with torch.no_grad():
        codes = power3_codes(weight).numpy().flatten()
        scale = absmean_scale(weight).item()
    packed, _ = pack_p3(codes)
    payload = struct.pack("<f", scale) + packed
    f.write(payload)
    return len(payload)


def _write_p3_conv(f, conv_module) -> int:
    """Conv weight is (channels, 1, kernel_size); flip the spatial axis on export."""
    with torch.no_grad():
        w = conv_module.weight.squeeze(1)
        codes = power3_codes(w).numpy()[:, ::-1].copy().flatten()
        scale = absmean_scale(w).item()
    packed, _ = pack_p3(codes)
    payload = struct.pack("<f", scale) + packed
    f.write(payload)
    return len(payload)


def _write_norm(f, norm) -> int:
    gamma = norm.weight.detach().numpy().astype(np.float32)
    beta = norm.bias.detach().numpy().astype(np.float32)
    payload = gamma.tobytes() + beta.tobytes()
    f.write(payload)
    return len(payload)


def _write_ssm(f, ssm) -> int:
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
        total += _write_p3(f, model.embed.weight)
        for i, block in enumerate(model.blocks):
            if verbose:
                print(f"  block {i}")
            total += _write_norm(f, block.norm)
            total += _write_p3_conv(f, block.local)
            total += _write_ssm(f, block.state)
            total += _write_p3(f, block.sparse.Wq.weight)
            total += _write_p3(f, block.sparse.Wk.weight)
            total += _write_p3(f, block.sparse.Wv.weight)
            total += _write_p3(f, block.router.proj.weight)
        total += _write_norm(f, model.final_norm)
        total += _write_p3(f, model.unembed.weight)
    if verbose:
        print(f"exported {total} bytes ({total / 1024:.1f} KB) → {output}")
    return {"total_bytes": total, "format": "ATOMEP3"}


def _read_p3_payload(buf: bytes, off: int, shape: tuple
                     ) -> tuple[np.ndarray, int]:
    scale = struct.unpack_from("<f", buf, off)[0]; off += 4
    n = int(np.prod(shape))
    nb = packed_size(n)
    codes = unpack_p3(buf[off:off + nb], n); off += nb
    return codes.reshape(shape).astype(np.float32) * scale, off


def unpack_atome_p3(path: Path, model_config: dict) -> dict:
    """Read an ATOMEP3 binary, return dequantised tensors as numpy."""
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
    out["embed"], off = _read_p3_payload(buf, off, (V, d))
    for _ in range(n_layers):
        block: dict = {}
        block["norm_gamma"] = np.frombuffer(buf, dtype=np.float32, count=d, offset=off).copy(); off += d * 4
        block["norm_beta"]  = np.frombuffer(buf, dtype=np.float32, count=d, offset=off).copy(); off += d * 4
        block["conv"], off = _read_p3_payload(buf, off, (d, ks))
        block["ssm_a"] = np.frombuffer(buf, dtype=np.float32, count=d, offset=off).copy(); off += d * 4
        block["ssm_b"] = np.frombuffer(buf, dtype=np.float32, count=d, offset=off).copy(); off += d * 4
        block["ssm_c"] = np.frombuffer(buf, dtype=np.float32, count=d, offset=off).copy(); off += d * 4
        block["Wq"], off = _read_p3_payload(buf, off, (dh, d))
        block["Wk"], off = _read_p3_payload(buf, off, (dh, d))
        block["Wv"], off = _read_p3_payload(buf, off, (d, d))
        block["router"], off = _read_p3_payload(buf, off, (3, d))
        out["blocks"].append(block)
    out["final_norm_gamma"] = np.frombuffer(buf, dtype=np.float32, count=d, offset=off).copy(); off += d * 4
    out["final_norm_beta"]  = np.frombuffer(buf, dtype=np.float32, count=d, offset=off).copy(); off += d * 4
    out["unembed"], off = _read_p3_payload(buf, off, (V, d))
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
    quant = state.get("quantizer") or cfg.get("quantizer", "ternary")
    if quant != "power3":
        print(f"warning: checkpoint quantizer is '{quant}', not 'power3'. "
              "Exporting anyway, but the trained weights will be re-quantised "
              "into the power-3 level set on the fly — the resulting binary "
              "is not the same model the checkpoint represents.",
              file=sys.stderr)
    model = AtomeLM(
        vocab_size=cfg["vocab_size"], d_model=cfg["d_model"],
        n_layers=cfg["n_layers"], d_head=cfg["d_head"],
        top_k=cfg["top_k"], kernel_size=cfg["kernel_size"],
        quantizer="power3",
    )
    model.load_state_dict(state["state_dict"])
    model.eval()
    export_model(model, args.output)


if __name__ == "__main__":
    main()
