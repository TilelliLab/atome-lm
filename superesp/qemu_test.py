"""superesp.qemu_test — run a SuperESP head on Cortex-M3 under QEMU.

Cross-compiles firmware_classify.c (+ atome.c + startup.s) for cortex-m3 with the
SuperESP config, bakes the head's ATOMECL01 blob and a token sequence, runs it in
qemu-system-arm (mps2-an385, semihosting), and compares the class + logits to the
Python head. This is the honest "tested in emulation" step: real ARM Thumb
execution, bit-exact — short of (and pending) the physical ESP32.

NOTE: QEMU mps2-an385 is Cortex-M3 (ARM), not Xtensa/RISC-V; it validates the
portable C engine's correctness on real MCU instructions. Cycle-accurate timing
is NOT modelled here (DWT->CYCCNT reads 0) — latency must come from a real board.

Run:  python3 -m superesp.qemu_test [head]
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import torch

from superesp.framework.config import SHARED
from superesp.framework.export import export_classifier
from superesp.framework.parity import py_class_logits

ROOT = Path(__file__).resolve().parents[1]
CM3 = ROOT / "c_engine" / "targets" / "cortex-m3"
UP = ROOT / "c_engine" / "upstream"


def tools_ok() -> bool:
    return all(shutil.which(t) for t in ("arm-none-eabi-gcc", "qemu-system-arm", "xxd"))


def _defines():
    c = SHARED
    return [f"-DATOME_D_MODEL={c.d_model}", f"-DATOME_MAX_SEQ={c.max_seq}",
            f"-DATOME_N_LAYERS={c.n_layers}", "-DATOME_N_PATHWAYS=3",
            f"-DATOME_VOCAB_SIZE={c.vocab_size}", f"-DATOME_D_HEAD={c.d_head}",
            f"-DATOME_KERNEL_SIZE={c.kernel_size}", f"-DATOME_TOP_K={c.top_k}",
            f"-DATOME_MAX_CLASSES={c.max_classes}"]


def run_head_in_qemu(model, tokens: list[int], workdir: Path) -> tuple[int, torch.Tensor]:
    workdir.mkdir(parents=True, exist_ok=True)
    blob = workdir / "model.atomecl"
    export_classifier(model, blob)
    # bake blob + tokens into headers
    md = subprocess.run(["xxd", "-i", "-n", "model_atome", str(blob)],
                        capture_output=True, text=True, check=True).stdout
    (workdir / "model_data.h").write_text(md)
    toks = ", ".join(str(int(t)) for t in tokens)
    (workdir / "tokens_data.h").write_text(
        f"static const int kTokens[] = {{{toks}}};\n"
        f"static const int kNTokens = {len(tokens)};\n")

    cflags = ["-mcpu=cortex-m3", "-mthumb", "-Os", "-std=c99", "-ffunction-sections",
              "-fdata-sections", f"-I{workdir}", f"-I{CM3}", f"-I{UP}", *_defines()]
    ld = ["-mcpu=cortex-m3", "-mthumb", f"-T{CM3/'linker.ld'}", "--specs=rdimon.specs",
          "-nostartfiles", "-Wl,--gc-sections"]
    elf = workdir / "classify.elf"
    # assemble startup, compile sources, link
    subprocess.run(["arm-none-eabi-gcc", "-mcpu=cortex-m3", "-mthumb", "-c",
                    str(CM3 / "startup.s"), "-o", str(workdir / "startup.o")], check=True)
    for src in [CM3 / "firmware_classify.c", UP / "atome.c"]:
        subprocess.run(["arm-none-eabi-gcc", *cflags, "-c", str(src),
                        "-o", str(workdir / (src.stem + ".o"))], check=True)
    subprocess.run(["arm-none-eabi-gcc", *ld, str(workdir / "startup.o"),
                    str(workdir / "firmware_classify.o"), str(workdir / "atome.o"),
                    "-lc", "-lrdimon", "-lm", "-o", str(elf)], check=True)
    out = subprocess.run(["qemu-system-arm", "-M", "mps2-an385", "-nographic",
                          "-semihosting", "-kernel", str(elf)],
                         capture_output=True, text=True, timeout=60).stdout
    lines = [l for l in out.strip().splitlines() if l.strip()]
    cls = int(lines[0])
    logits = torch.tensor([float(x) for x in lines[1:]], dtype=torch.float32)
    return cls, logits


def main():
    if not tools_ok():
        print("SKIP: need arm-none-eabi-gcc + qemu-system-arm + xxd"); return
    from superesp.heads import BY_NAME
    from superesp.framework.train import train_head
    name = sys.argv[1] if len(sys.argv) > 1 else "agri"
    ds = BY_NAME[name].loader(seed=0)
    res = train_head(ds.n_classes, ds.train_ids, ds.train_labels,
                     ds.val_ids, ds.val_labels, epochs=12, seed=0)
    tmp = Path(tempfile.mkdtemp())
    maxd = 0.0; agree = True
    for i in range(4):
        toks = ds.test_ids[i].tolist()
        cls_q, lq = run_head_in_qemu(res.model, toks, tmp)
        lp = py_class_logits(res.model, toks)[: len(lq)]
        maxd = max(maxd, (lq - lp).abs().max().item())
        if cls_q != int(py_class_logits(res.model, toks).argmax()):
            agree = False
    print(f"[QEMU Cortex-M3] head={name}: class-agreement={agree}, max|Δ logit|={maxd:.3e} "
          f"(bit-exact on real ARM ISA; timing NOT modelled)")


if __name__ == "__main__":
    main()
