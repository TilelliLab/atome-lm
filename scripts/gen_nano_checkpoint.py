#!/usr/bin/env python3
"""scripts/gen_nano_checkpoint.py — one-off: build the fixed-seed nano
config used by tests/test_parity_with_c.py, export it to .atome, and
print the Python-side expected autoregressive generation for the same
prompt the picorv32-tangnano9k firmware.c uses, so the real-hardware
output can be diffed against it.

Not a permanent repo script -- ad hoc for the PicoRV32/Tang Nano 9K
target's hardware parity check (see PICORV32_TANGNANO9K_PLAN.md).
"""
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from atome_llm.core.atome_lm import AtomeLM  # noqa: E402
import export_to_atome as ex  # noqa: E402

# Exactly tests/test_parity_with_c.py's CONFIG -- this is also exactly
# c_engine/targets/picorv32-tangnano9k/Makefile's ATOME_DEFINES (nano/tiny).
CONFIG = dict(
    vocab_size=32,
    d_model=16,
    n_layers=2,
    d_head=8,
    top_k=4,
    kernel_size=5,
)
PROMPT = [10, 20, 5, 17, 0, 25]  # matches firmware.c's kPrompt
N_GENERATE = 8  # matches firmware.c's generation loop bound

torch.manual_seed(42)
model = AtomeLM(**CONFIG)
model.eval()

out_path = ROOT / "c_engine" / "targets" / "picorv32-tangnano9k" / "nano_seed42.atome"
stats = ex.export_model(model, out_path, verbose=True)

tokens = list(PROMPT)
with torch.no_grad():
    for _ in range(N_GENERATE):
        ids = torch.tensor([tokens], dtype=torch.long)
        logits = model(ids)[0, -1, :]
        next_tok = int(logits.argmax().item())
        tokens.append(next_tok)

generated = tokens[len(PROMPT):]
print(f"prompt:    {PROMPT}")
print(f"generated: {generated}")
print(f"generated (hex, 2-digit, matches firmware.c uart_print_hex format):")
print(" ".join(f"{t:02X}" for t in generated))
print(f"exported: {out_path} ({stats['total_bytes']} bytes)")
