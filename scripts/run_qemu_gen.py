#!/usr/bin/env python3
"""scripts/run_qemu_gen.py — multi-token generation on emulated Cortex-M3.

Builds the cortex-m3-gen firmware, bakes a small AtomeLM into it, runs
on QEMU MPS2-AN385, parses the streamed token stream + DWT cycle count,
and reports estimated tokens/sec at a representative MCU clock.

This is the closest-to-real-silicon test that runs on a laptop. Real
RP2040 / STM32F4 numbers will land lower (no semihosting overhead, fewer
host-side context switches) but the same firmware drops onto those
boards with only the linker script + startup changing.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parent.parent
GEN_DIR = ROOT / "c_engine" / "targets" / "cortex-m3-gen"
sys.path.insert(0, str(ROOT / "scripts"))


CONFIG = dict(vocab_size=32, d_model=16, n_layers=2,
              d_head=8, top_k=4, kernel_size=5)
MAX_SEQ = 32
PROMPT = [10, 20, 5, 17]
N_NEW = 8


def _check_tools() -> None:
    missing = [t for t in ("arm-none-eabi-gcc", "qemu-system-arm", "xxd")
               if shutil.which(t) is None]
    if missing:
        print(f"error: missing tools: {', '.join(missing)}", file=sys.stderr)
        raise SystemExit(2)


def _bake(atome_path: Path, header_path: Path) -> None:
    proc = subprocess.run(
        ["xxd", "-i", "-n", "model_atome", str(atome_path)],
        capture_output=True, text=True, check=True,
    )
    header_path.write_text(proc.stdout)


def _defines(cfg: dict) -> list[str]:
    return [
        f"-DATOME_D_MODEL={cfg['d_model']}",
        f"-DATOME_MAX_SEQ={MAX_SEQ}",
        f"-DATOME_N_LAYERS={cfg['n_layers']}",
        f"-DATOME_N_PATHWAYS=3",
        f"-DATOME_VOCAB_SIZE={cfg['vocab_size']}",
        f"-DATOME_D_HEAD={cfg['d_head']}",
        f"-DATOME_KERNEL_SIZE={cfg['kernel_size']}",
        f"-DATOME_TOP_K={cfg['top_k']}",
        f"-DDEMO_PROMPT_LEN={len(PROMPT)}",
        f"-DDEMO_NEW_TOKENS={N_NEW}",
    ]


def _build(defines: list[str]) -> Path:
    for fn in ("startup.o", "firmware.o", "atome.o",
               "firmware.elf", "firmware.map"):
        (GEN_DIR / fn).unlink(missing_ok=True)
    proc = subprocess.run(
        ["make", "-C", str(GEN_DIR),
         f"ATOME_DEFINES={' '.join(defines)}",
         "firmware.elf"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout); sys.stderr.write(proc.stderr)
        raise SystemExit("gen firmware build failed")
    print(proc.stdout, end="")
    return GEN_DIR / "firmware.elf"


def _run(elf: Path, timeout_s: float = 60.0) -> str:
    proc = subprocess.run(
        ["qemu-system-arm", "-M", "mps2-an385", "-nographic",
         "-semihosting", "-kernel", str(elf)],
        capture_output=True, text=True, timeout=timeout_s,
    )
    return proc.stdout


def _parse(out: str) -> tuple[list[int], int]:
    tokens: list[int] = []
    cycles = -1
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("TOK "):
            parts = line.split()
            tokens.append(int(parts[2]))
        elif line.startswith("ATOME-GEN-END"):
            for kv in line.split():
                if kv.startswith("total_cycles="):
                    cycles = int(kv.split("=", 1)[1])
    return tokens, cycles


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mcu-clock-mhz", type=float, default=125.0,
                    help="reference MCU clock for tokens/sec estimate (RP2040=125)")
    ap.add_argument("--keep-tmp", action="store_true")
    args = ap.parse_args()

    _check_tools()
    import export_to_atome as ex
    from atome_llm.core.atome_lm import AtomeLM

    torch.manual_seed(42)
    model = AtomeLM(**CONFIG)
    model.eval()

    work = Path(tempfile.mkdtemp(prefix="atome_qgen_"))
    try:
        atome_bin = work / "model.atome"
        ex.export_model(model, atome_bin, verbose=False)
        _bake(atome_bin, GEN_DIR / "model_data.h")
        elf = _build(_defines(CONFIG))
        out = _run(elf)
        tokens, cycles = _parse(out)

        # Reference Python generation
        with torch.no_grad():
            py_full = model.generate(
                torch.tensor([PROMPT], dtype=torch.long),
                n_new_tokens=N_NEW, max_seq=MAX_SEQ,
            )
            py_tokens = py_full[0, len(PROMPT):].tolist()

        print(f"\nC tokens:  {tokens}")
        print(f"Py tokens: {py_tokens}")

        match = tokens == py_tokens
        per_token_cycles = cycles / max(1, len(tokens)) if cycles > 0 else 0
        per_token_us = per_token_cycles / args.mcu_clock_mhz
        tok_per_s = (1e6 / per_token_us) if per_token_us > 0 else 0

        print(f"\nDWT cycles total:        {cycles:,}")
        print(f"DWT cycles per token:    {per_token_cycles:,.0f}")
        print(f"At {args.mcu_clock_mhz:.0f} MHz: {per_token_us:.0f} µs / token "
              f"→ {tok_per_s:.1f} tokens/sec")

        if match:
            print("\nPASS — token-by-token match between QEMU C and Python.")
            return 0
        print("\nFAIL — divergence between C and Python tokens.")
        return 1
    finally:
        if not args.keep_tmp:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
