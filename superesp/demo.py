"""superesp.demo — end-to-end SuperESP demo on the REAL on-device path.

Verifies each head's signed attestation, then drives the compiled C OS
dispatcher (c_engine/superesp/superesp_os.c) on real tokenized sensor frames:
  - a NORMAL telemetry tick -> agri sensor classified;
  - a POWER_FAULT telemetry tick -> policy sheds load, voice head DISABLED,
    agri still runs.
No retraining needed — it loads the shipped ATOMECL01 blobs the same way the
firmware would. Run:  python3 -m superesp.demo
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from superesp.framework.config import SHARED
from superesp.framework.tokenize import FeatureTokenizer
from superesp.attest import sign
from superesp.datasets import os_telem, agri

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "superesp" / "artifacts"


def _build_dispatcher(tmp: Path) -> Path:
    out = tmp / "superesp_os"
    c = SHARED
    defines = [
        f"-DATOME_D_MODEL={c.d_model}", f"-DATOME_N_LAYERS={c.n_layers}",
        f"-DATOME_D_HEAD={c.d_head}", f"-DATOME_MAX_SEQ={c.max_seq}",
        f"-DATOME_TOP_K={c.top_k}", f"-DATOME_KERNEL_SIZE={c.kernel_size}",
        f"-DATOME_VOCAB_SIZE={c.vocab_size}", f"-DATOME_MAX_CLASSES={c.max_classes}",
        "-DATOME_N_PATHWAYS=3",
    ]
    cmd = ["gcc", "-O2", "-std=c99", f"-I{ROOT/'c_engine'/'upstream'}", *defines,
           str(ROOT / "c_engine" / "superesp" / "superesp_os.c"),
           str(ROOT / "c_engine" / "upstream" / "atome.c"), "-lm", "-o", str(out)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out


def _toks(tok: FeatureTokenizer, frame: np.ndarray) -> str:
    return " ".join(map(str, tok.transform(frame[None, :])[0].tolist()))


def main() -> None:
    print("=== SuperESP demo — on-device path (C engine, shipped blobs) ===\n")

    # 1. attestation
    print("1) Verifying head attestations (Ed25519):")
    for name in ["os_telem", "agri", "voice"]:
        att = json.loads((ART / f"{name}.att.json").read_text())
        ok, reason = sign.verify(ART / f"{name}.atomecl", att)
        print(f"   {name:9s}: {'VERIFIED' if ok else 'FAIL '+reason}")

    # 2. tokenizers + real frames
    otok = FeatureTokenizer.from_dict(json.loads((ART / "os_telem.tok.json").read_text()))
    atok = FeatureTokenizer.from_dict(json.loads((ART / "agri.tok.json").read_text()))
    dso = os_telem.load(seed=2)
    dsa = agri.load(seed=2)
    normal_i = int((dso.test_labels == dso.class_names.index("normal")).nonzero(as_tuple=True)[0][0])
    fault_i = int((dso.test_labels == dso.class_names.index("power_fault")).nonzero(as_tuple=True)[0][0])
    ag_toks = _toks(atok, dsa.test_X[0])

    tmp = Path(tempfile.mkdtemp())
    disp = _build_dispatcher(tmp)

    def run(os_frame_i, modality, blob):
        os_toks = _toks(otok, dso.test_X[os_frame_i])
        o = subprocess.run([str(disp), str(ART / "os_telem.atomecl"), modality,
                            str(ART / f"{blob}.atomecl"), os_toks, ag_toks],
                           capture_output=True, text=True)
        return o.stdout.strip()

    print("\n2) NORMAL telemetry tick + agri sensor:")
    for line in run(normal_i, "agri", "agri").splitlines():
        print("   " + line)
    print("\n3) POWER_FAULT telemetry tick + voice request (should be shed):")
    for line in run(fault_i, "voice", "voice").splitlines():
        print("   " + line)
    print("\n4) POWER_FAULT telemetry tick + agri sensor (still runs):")
    for line in run(fault_i, "agri", "agri").splitlines():
        print("   " + line)
    print("\nSuperESP: Atome runs as the device supervisor (classify, not generate).")


if __name__ == "__main__":
    main()
