#!/usr/bin/env python3
"""scripts/measure_ram.py — peak SRAM usage of the Atome firmware.

Builds the cortex-m3-ram firmware with a tiny model baked in, runs it
on QEMU, parses the painted-stack high-water + .bss size, combines with
arm-none-eabi-size's .text + .data + .bss numbers, and reports total
RAM (bss + stack) + total flash (text + data) + the on-chip model blob.

Goal of the test: prove the inference path fits in well under 16 KB of
SRAM, which is the cap for the smallest Cortex-M0+ targets (e.g. nRF51,
ATSAMD21, original Pi Pico has 264 KB so this is a comfort check there).
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
RAM_DIR = ROOT / "c_engine" / "targets" / "cortex-m3-ram"
sys.path.insert(0, str(ROOT / "scripts"))


CONFIGS = {
    # Smallest plausible config — proves the engine fits the 8 KB-SRAM tier.
    "nano":    dict(vocab_size=32,  d_model=16, n_layers=2,
                    d_head=8,  top_k=4, kernel_size=5, max_seq=32),
    # Test default — what most CI tests build against.
    "tiny":    dict(vocab_size=32,  d_model=16, n_layers=2,
                    d_head=8,  top_k=4, kernel_size=5, max_seq=32),
    # Byte-tokenizer minimum (V=256) — first config that prints English.
    "byte_small": dict(vocab_size=256, d_model=32, n_layers=2,
                       d_head=8,  top_k=4, kernel_size=5, max_seq=32),
    # Trained tinystories checkpoint — what we actually run on QEMU today.
    "tinystories": dict(vocab_size=256, d_model=64, n_layers=4,
                        d_head=16, top_k=4, kernel_size=5, max_seq=64),
    # Stretch config — what a 1M-param scale-up would look like.
    "mid":     dict(vocab_size=256, d_model=128, n_layers=4,
                    d_head=32, top_k=4, kernel_size=5, max_seq=64),
    # The actual trained 944K-param model (atome_1m_v1) at TinyStories quality.
    "prod_1m": dict(vocab_size=256, d_model=256, n_layers=8,
                    d_head=64, top_k=4, kernel_size=5, max_seq=64),
}

# Common MCU classes — RAM / Flash budgets in bytes.
MCU_TARGETS = [
    # name,                    sram,        flash,      core,      notes
    ("STM32F103 (Blue Pill)",  20  * 1024,  128 * 1024, "M3",      "$2-4"),
    ("RP2040 (Pico)",          264 * 1024,  2 * 1024**2, "M0+",    "$4"),
    ("STM32F411 (Nucleo)",     128 * 1024,  512 * 1024, "M4F",     "$15"),
    ("STM32F7",                512 * 1024,  2 * 1024**2, "M7",     "$15-30"),
    ("ESP32-S3",               512 * 1024,  4 * 1024**2, "LX7",    "$5-10"),
]


def _max_seq(cfg: dict) -> int:
    return cfg.get("max_seq", 32)


def _check() -> None:
    missing = [t for t in ("arm-none-eabi-gcc", "arm-none-eabi-size",
                            "qemu-system-arm", "xxd")
               if shutil.which(t) is None]
    if missing:
        print(f"missing: {', '.join(missing)}", file=sys.stderr)
        raise SystemExit(2)


def _bake(atome_bin: Path, out: Path) -> None:
    proc = subprocess.run(
        ["xxd", "-i", "-n", "model_atome", str(atome_bin)],
        capture_output=True, text=True, check=True,
    )
    out.write_text(proc.stdout)


def _defines(cfg: dict) -> list[str]:
    return [
        f"-DATOME_D_MODEL={cfg['d_model']}",
        f"-DATOME_MAX_SEQ={_max_seq(cfg)}",
        f"-DATOME_N_LAYERS={cfg['n_layers']}",
        f"-DATOME_N_PATHWAYS=3",
        f"-DATOME_VOCAB_SIZE={cfg['vocab_size']}",
        f"-DATOME_D_HEAD={cfg['d_head']}",
        f"-DATOME_KERNEL_SIZE={cfg['kernel_size']}",
        f"-DATOME_TOP_K={cfg['top_k']}",
    ]


def _build(defines: list[str]) -> tuple[Path, dict]:
    for fn in ("startup.o", "firmware.o", "atome.o",
               "firmware.elf", "firmware.map"):
        (RAM_DIR / fn).unlink(missing_ok=True)
    proc = subprocess.run(
        ["make", "-C", str(RAM_DIR),
         f"ATOME_DEFINES={' '.join(defines)}",
         "firmware.elf"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout); sys.stderr.write(proc.stderr)
        raise SystemExit("ram firmware build failed")
    print(proc.stdout, end="")
    elf = RAM_DIR / "firmware.elf"

    # Parse `arm-none-eabi-size` output for static numbers.
    size_proc = subprocess.run(
        ["arm-none-eabi-size", str(elf)],
        capture_output=True, text=True, check=True,
    )
    last = size_proc.stdout.strip().splitlines()[-1].split()
    static = {"text": int(last[0]), "data": int(last[1]), "bss": int(last[2])}
    return elf, static


def _run(elf: Path) -> str:
    proc = subprocess.run(
        ["qemu-system-arm", "-M", "mps2-an385", "-nographic",
         "-semihosting", "-kernel", str(elf)],
        capture_output=True, text=True, timeout=30,
    )
    return proc.stdout


def _parse(out: str) -> dict:
    for line in out.splitlines():
        if line.startswith("ATOME-RAM"):
            kv: dict = {}
            for tok in line.split()[1:]:
                k, v = tok.split("=", 1)
                kv[k] = int(v)
            return kv
    raise SystemExit(f"no ATOME-RAM line in QEMU output:\n{out}")


def measure_one(name: str, cfg: dict) -> dict:
    import export_to_atome as ex
    from atome_llm.core.atome_lm import AtomeLM

    torch.manual_seed(0)
    model_cfg = {k: v for k, v in cfg.items() if k != "max_seq"}
    model = AtomeLM(**model_cfg).eval()

    work = Path(tempfile.mkdtemp(prefix=f"atome_ram_{name}_"))
    try:
        atome_bin = work / "model.atome"
        ex.export_model(model, atome_bin, verbose=False)
        _bake(atome_bin, RAM_DIR / "model_data.h")
        model_bytes = atome_bin.stat().st_size

        elf, static = _build(_defines(cfg))
        out = _run(elf)
        runtime = _parse(out)
        return {
            "name": name, "config": cfg,
            "text": static["text"], "data": static["data"],
            "bss": runtime["bss"], "stack_used": runtime["stack_used"],
            "model_bytes": model_bytes,
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _flash_bytes(r: dict) -> int:
    return r["text"] + r["data"] + r["model_bytes"]


def _peak_ram(r: dict) -> int:
    return r["bss"] + r["stack_used"]


def _fmt_kb(b: int) -> str:
    return f"{b / 1024:.1f} KB"


def _emit_markdown(rows: list[dict], path: Path) -> None:
    lines: list[str] = []
    lines.append("# Atome — RAM / Flash fit table\n")
    lines.append("Generated by `python3 scripts/measure_ram.py --markdown`. "
                 "Numbers come from a real Cortex-M3 build "
                 "(`c_engine/targets/cortex-m3-ram`) under QEMU MPS2-AN385: "
                 "`.text + .data + model.atome` for flash, and "
                 "`.bss + measured stack high-water` for RAM.\n")

    lines.append("## Per-config sizes\n")
    lines.append("| Config | d_model | layers | max_seq | Flash | RAM (.bss) | Stack | Peak RAM |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        c = r["config"]
        lines.append(
            f"| `{r['name']}` | {c['d_model']} | {c['n_layers']} | "
            f"{_max_seq(c)} | {_fmt_kb(_flash_bytes(r))} | "
            f"{_fmt_kb(r['bss'])} | {r['stack_used']} B | "
            f"{_fmt_kb(_peak_ram(r))} |"
        )
    lines.append("")

    lines.append("## Fits-on-MCU matrix\n")
    lines.append("`✓` = fits, `✗` = exceeds RAM or flash, "
                 "`✗R` = RAM-bound, `✗F` = flash-bound.\n")
    head = "| Config | " + " | ".join(name for name, *_ in MCU_TARGETS) + " |"
    sep = "|---|" + "|".join([":---:"] * len(MCU_TARGETS)) + "|"
    lines.append(head)
    lines.append(sep)
    for r in rows:
        cells: list[str] = [f"`{r['name']}`"]
        peak = _peak_ram(r)
        flash = _flash_bytes(r)
        for _, sram, fl, _core, _price in MCU_TARGETS:
            ram_ok = peak <= sram
            flash_ok = flash <= fl
            if ram_ok and flash_ok:
                cells.append("✓")
            elif not ram_ok and not flash_ok:
                cells.append("✗")
            elif not ram_ok:
                cells.append("✗R")
            else:
                cells.append("✗F")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## MCU reference\n")
    lines.append("| MCU | SRAM | Flash | Core | Approx price |")
    lines.append("|---|---:|---:|---|---|")
    for name, sram, fl, core, price in MCU_TARGETS:
        lines.append(f"| {name} | {_fmt_kb(sram)} | "
                     f"{fl // 1024} KB | {core} | {price} |")
    lines.append("")

    path.write_text("\n".join(lines))
    print(f"\nwrote {path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="+", default=list(CONFIGS.keys()))
    ap.add_argument("--markdown", type=Path, default=None,
                    help="emit a fits-on-MCU table to this path "
                         "(e.g. c_engine/RAM_TABLE.md)")
    args = ap.parse_args()

    _check()

    rows: list[dict] = []
    for name in args.configs:
        if name not in CONFIGS:
            print(f"!! unknown config '{name}'"); continue
        print(f"\n--- measuring '{name}' ---")
        rows.append(measure_one(name, CONFIGS[name]))

    print("\n" + "=" * 88)
    print(f"  {'config':<12} {'d_model':>8} {'layers':>7} {'max_seq':>8} "
          f"{'flash':>10} {'.bss':>10} {'stack':>8} {'peak RAM':>10}")
    print("  " + "-" * 84)
    for r in rows:
        c = r["config"]
        print(f"  {r['name']:<12} {c['d_model']:>8} {c['n_layers']:>7} "
              f"{_max_seq(c):>8} "
              f"{_flash_bytes(r)/1024:>7.1f} KB "
              f"{r['bss']/1024:>7.1f} KB "
              f"{r['stack_used']:>6} B "
              f"{_peak_ram(r)/1024:>7.1f} KB")

    print("\nFits-on-MCU summary:")
    for r in rows:
        peak = _peak_ram(r)
        flash = _flash_bytes(r)
        fitting = [name for name, sram, fl, *_ in MCU_TARGETS
                   if peak <= sram and flash <= fl]
        verdict = (", ".join(n.split(" ")[0] for n in fitting)
                   if fitting else "(none — too large for any tracked MCU)")
        print(f"  {r['name']:<12}  fits: {verdict}")

    if args.markdown is not None:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        _emit_markdown(rows, args.markdown)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
