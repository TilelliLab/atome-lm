#!/usr/bin/env python3
"""scripts/cross_compile.py — compile the vendored Atome C engine for
several ARM Cortex-M variants and print a size comparison table.

This is a portability + footprint check, not a runnable artifact. The
script invokes `arm-none-eabi-gcc -c` to produce a `.o` for each target
tuple, then runs `arm-none-eabi-size` to extract `.text` (code) and
`.data + .bss` (RAM) sections. No linking, no startup, no binary —
just "does the engine compile cleanly for that architecture and what
does it cost in flash?"

If `arm-none-eabi-gcc` is not on PATH, the script exits with a clear
error pointing at `apt install gcc-arm-none-eabi`.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Target:
    name: str
    cpu_flags: list[str]
    use: str


TARGETS = [
    Target("cortex-m0",   ["-mcpu=cortex-m0",   "-mthumb"],
           "nRF51 / RP2040 (M0+)"),
    Target("cortex-m3",   ["-mcpu=cortex-m3",   "-mthumb"],
           "STM32F1 / mps2-an385"),
    Target("cortex-m4",   ["-mcpu=cortex-m4",   "-mthumb",
                           "-mfloat-abi=soft"],
           "STM32F4 (no FPU)"),
    Target("cortex-m4f",  ["-mcpu=cortex-m4",   "-mthumb",
                           "-mfpu=fpv4-sp-d16", "-mfloat-abi=hard"],
           "STM32F4 / nRF52840"),
    Target("cortex-m7",   ["-mcpu=cortex-m7",   "-mthumb",
                           "-mfpu=fpv5-sp-d16", "-mfloat-abi=hard"],
           "STM32F7 / H7"),
]


# Compile-time ATOME_* defines for the size-measurement run. Match the
# realistic headline config so the numbers reflect a plausible deploy.
DEFAULT_DEFINES = {
    "ATOME_D_MODEL": 64,
    "ATOME_MAX_SEQ": 32,
    "ATOME_N_LAYERS": 4,
    "ATOME_N_PATHWAYS": 3,
    "ATOME_VOCAB_SIZE": 256,
    "ATOME_D_HEAD": 16,
    "ATOME_KERNEL_SIZE": 5,
    "ATOME_TOP_K": 4,
}


ROOT = Path(__file__).resolve().parent.parent
ATOME_C = ROOT / "c_engine" / "upstream" / "atome.c"
ATOME_INC = ROOT / "c_engine" / "upstream"


def parse_size_output(text: str) -> tuple[int, int, int]:
    """Parse the second line of `arm-none-eabi-size` output: text, data, bss."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    nums = lines[-1].split()
    return int(nums[0]), int(nums[1]), int(nums[2])


def compile_target(target: Target, defines: dict[str, int],
                   tmp: Path, opt: str = "-Os") -> tuple[int, int, int] | str:
    obj = tmp / f"{target.name}.o"
    cmd = [
        "arm-none-eabi-gcc", "-c", opt, "-std=c99",
        "-Wall", "-Wextra",
        f"-I{ATOME_INC}",
        *target.cpu_flags,
        *[f"-D{k}={v}" for k, v in defines.items()],
        str(ATOME_C),
        "-o", str(obj),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return f"COMPILE FAIL\n{proc.stderr}"

    proc = subprocess.run(["arm-none-eabi-size", str(obj)],
                          capture_output=True, text=True, check=True)
    return parse_size_output(proc.stdout)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--opt", default="-Os", choices=("-O0", "-O1", "-O2", "-O3", "-Os"))
    args = ap.parse_args()

    if shutil.which("arm-none-eabi-gcc") is None:
        print("error: arm-none-eabi-gcc not found on PATH",
              file=sys.stderr)
        print("  fix: apt install gcc-arm-none-eabi", file=sys.stderr)
        return 2
    if not ATOME_C.exists():
        print(f"error: missing {ATOME_C}", file=sys.stderr)
        return 2

    print(f"Compile-only size table for atome.c   (defines: "
          f"d={DEFAULT_DEFINES['ATOME_D_MODEL']}, layers="
          f"{DEFAULT_DEFINES['ATOME_N_LAYERS']}, opt={args.opt})\n")
    print(f"  {'target':<14} {'use':<22} {'.text':>8} {'.data':>6} {'.bss':>8}  "
          f"{'flash':>8} {'static-RAM':>10}")
    print(f"  {'-' * 14} {'-' * 22} {'-' * 8} {'-' * 6} {'-' * 8}  "
          f"{'-' * 8} {'-' * 10}")

    fail = False
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for t in TARGETS:
            res = compile_target(t, DEFAULT_DEFINES, tmp, opt=args.opt)
            if isinstance(res, str):
                print(f"  {t.name:<14} {t.use:<22}  {res}")
                fail = True
                continue
            text, data, bss = res
            flash = text + data
            ram = data + bss
            print(f"  {t.name:<14} {t.use:<22} "
                  f"{text:>8} {data:>6} {bss:>8}  "
                  f"{flash:>8} {ram:>10}")

    print("\nNote: these are the engine's contribution alone — startup, "
          "newlib, and the model blob are extra. Multiply RAM column by "
          "~3-5x for realistic firmware total.")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
