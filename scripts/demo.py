#!/usr/bin/env python3
"""scripts/demo.py — interactive Atome LLM REPL.

Loads a checkpoint (or random-init model with --random) and reads a
prompt at a time. For each prompt:

  - prints the model's continuation (greedy by default; sampling with
    --temperature/--top-p/--top-k),
  - prints per-layer router-entropy bars over the prompt — the
    metacognition signal exposed for free at every position.

Usage
-----
    python scripts/demo.py --checkpoint checkpoints/atome_1m_v1.pt
    python scripts/demo.py --random                    # random-init,
                                                       # for plumbing checks
    python scripts/demo.py --random --temperature 1.0 --top-p 0.9

Type 'quit' / 'exit' / Ctrl-D to leave.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import torch

from atome_llm.core.atome_lm import AtomeLM
from atome_llm.core.mcu_block import PATHWAY_NAMES
from atome_llm.tokenize import ByteTokenizer


BAR_CHARS = " ▁▂▃▄▅▆▇█"


def bar(value: float, vmax: float, width: int = 20) -> str:
    if vmax <= 0:
        return " " * width
    frac = max(0.0, min(1.0, value / vmax))
    full = int(frac * width)
    rem = (frac * width) - full
    sub = BAR_CHARS[int(rem * (len(BAR_CHARS) - 1))]
    return "█" * full + sub + " " * max(0, width - full - 1)


def load_model(checkpoint: Path | None, random: bool) -> AtomeLM:
    if random:
        torch.manual_seed(0)
        return AtomeLM().eval()
    if checkpoint is None or not checkpoint.exists():
        raise SystemExit(
            f"checkpoint not found: {checkpoint}. "
            "Pass --random for a plumbing check."
        )
    blob = torch.load(checkpoint, map_location="cpu", weights_only=True)
    cfg = blob.get("config", {})
    model = AtomeLM(
        vocab_size=cfg.get("vocab_size", 256),
        d_model=cfg.get("d_model", 64),
        n_layers=cfg.get("n_layers", 4),
        d_head=cfg.get("d_head", 16),
        top_k=cfg.get("top_k", 4),
        kernel_size=cfg.get("kernel_size", 5),
    )
    model.load_state_dict(blob["state_dict"])
    return model.eval()


def show_router_entropies(model: AtomeLM, ids: torch.Tensor, tok: ByteTokenizer) -> None:
    bound = math.log(model.blocks[0].router.n_pathways)
    ents = model.router_entropies(ids)  # list[(B, L)]
    text = tok.decode(ids[0]).replace("\n", "\\n")
    head = f"  router entropy (max {bound:.2f} nats):"
    print(head)
    for layer, e in enumerate(ents):
        e0 = e[0]
        ent_mean = e0.mean().item()
        ent_max = e0.max().item()
        print(
            f"    L{layer}  μ={ent_mean:.3f}  max={ent_max:.3f}  "
            f"|{bar(ent_mean, bound)}|"
        )


def show_pathway_mix(model: AtomeLM, ids: torch.Tensor) -> None:
    """Average router weight per pathway across the prompt."""
    with torch.no_grad():
        x = model.embed(ids)
        for layer, block in enumerate(model.blocks):
            r = block.router_weights(x)            # (B, L, 3)
            avg = r[0].mean(dim=0).tolist()        # (3,)
            mix = "  ".join(
                f"{name} {p * 100:5.1f}%" for name, p in zip(PATHWAY_NAMES, avg)
            )
            print(f"    L{layer}  pathway mix: {mix}")
            x = block(x)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", type=Path, default=None)
    ap.add_argument("--random", action="store_true",
                    help="use a random-init model (smoke test)")
    ap.add_argument("--n-tokens", type=int, default=64,
                    help="how many bytes to generate per prompt")
    ap.add_argument("--max-seq", type=int, default=32,
                    help="must match the C engine's compile-time ATOME_MAX_SEQ")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--top-p", type=float, default=1.0)
    ap.add_argument("--top-k", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--no-router", action="store_true",
                    help="skip per-layer router-entropy display")
    args = ap.parse_args()

    model = load_model(args.checkpoint, args.random)
    tok = ByteTokenizer()
    gen = torch.Generator().manual_seed(args.seed) if args.seed is not None else None

    print(
        f"Atome LLM REPL  •  {model.parameter_count():,} params  "
        f"•  d_model={model.d_model}  n_layers={model.n_layers}"
    )
    print("Type a prompt, then Enter. 'quit' to leave.\n")

    while True:
        try:
            prompt = input("> ").rstrip("\n")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if prompt.strip().lower() in {"quit", "exit"}:
            break
        if not prompt:
            continue

        ids = tok.encode(prompt).unsqueeze(0)
        out = model.generate(
            ids,
            n_new_tokens=args.n_tokens,
            max_seq=args.max_seq,
            temperature=args.temperature,
            top_p=args.top_p,
            top_k=args.top_k,
            generator=gen,
        )
        cont = tok.decode(out[0, ids.size(1):])
        print(f"\n{prompt}{cont}\n")
        if not args.no_router:
            show_router_entropies(model, ids, tok)
            show_pathway_mix(model, ids)
            print()


if __name__ == "__main__":
    sys.exit(main())
