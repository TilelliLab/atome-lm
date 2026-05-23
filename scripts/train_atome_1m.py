#!/usr/bin/env python3
"""scripts/train_atome_1m.py — production-leaning trainer for ~1M-param Atome.

Trains a wider/deeper AtomeLM than `train_demo.py` to actually produce
coherent English continuations on TinyStories. Reaches ~944K params at
the default config (d=256, L=8, d_head=64) — borderline-runnable on
RP2040 / STM32F411 (see RAM_TABLE.md, `mid` row), and the natural
follow-up to the 60K tinystories checkpoint.

What this script does that `train_demo.py` does not:
  - Larger default config (1M-class)
  - 90/10 train/val split with periodic val perplexity
  - Cosine LR schedule with warmup
  - Mixed-precision (--bf16) when CUDA is present
  - Gradient accumulation (effective batch = batch * accum_steps)
  - Save best-val checkpoint, not last
  - Write a `.train.json` log next to the checkpoint

NOT included (deliberately):
  - Distributed training — the model is too small for it to matter
  - Custom scheduler beyond cosine — the model is too small for it to matter
  - HuggingFace integration — bytes are bytes, no tokenizer needed

Recommended GPU recipe (do NOT launch from this assistant — present plan first):
  pod:    RunPod A6000 ($0.39-0.79/hr) or A4000 ($0.19/hr)
  corpus: TinyStories ~370M token dump (~370 MB) or local 500KB sample
  config: d=256, L=8, d_head=64, seq_len=256
  steps:  100k @ batch=64 with accum=4 → 51M samples
  budget: ~30-90 min wall on A6000 → ~$0.20-1.00 GPU
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atome_llm.core.atome_lm import AtomeLM  # noqa: E402
from atome_llm.tokenize import ByteTokenizer  # noqa: E402


def load_corpus(path: Path, seq_len: int, val_frac: float = 0.1) -> tuple[torch.Tensor, torch.Tensor]:
    text = path.read_text(encoding="utf-8", errors="replace")
    tok = ByteTokenizer()
    ids = tok.encode(text)
    n_chunks = ids.numel() // seq_len
    chunks = ids[: n_chunks * seq_len].view(n_chunks, seq_len)
    n_val = max(1, int(n_chunks * val_frac))
    perm = torch.randperm(n_chunks, generator=torch.Generator().manual_seed(0))
    val_ids = chunks[perm[:n_val]]
    train_ids = chunks[perm[n_val:]]
    print(f"corpus: {path.name}  {len(text):,} chars  →  "
          f"{train_ids.size(0):,} train / {val_ids.size(0):,} val "
          f"chunks of length {seq_len}")
    return train_ids, val_ids


def lr_at(step: int, total: int, peak_lr: float, warmup: int, min_lr: float) -> float:
    if step < warmup:
        return peak_lr * (step + 1) / max(1, warmup)
    progress = (step - warmup) / max(1, total - warmup)
    progress = min(1.0, max(0.0, progress))
    cosine = 0.5 * (1.0 + math.cos(math.pi * progress))
    return min_lr + (peak_lr - min_lr) * cosine


@torch.no_grad()
def eval_loss(model: AtomeLM, val_ids: torch.Tensor, batch_size: int,
              device: torch.device, max_batches: int = 64) -> float:
    model.eval()
    losses: list[float] = []
    n = val_ids.size(0)
    for i in range(min(max_batches, max(1, n // batch_size))):
        idx = slice(i * batch_size, (i + 1) * batch_size)
        chunk = val_ids[idx].to(device)
        if chunk.size(0) == 0:
            break
        ids, targets = chunk[:, :-1], chunk[:, 1:]
        loss = model.loss(ids, targets)
        losses.append(loss.item())
    model.train()
    return sum(losses) / max(1, len(losses))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data/tinystories.txt"))
    ap.add_argument("--output", type=Path,
                    default=Path("checkpoints/atome_1m.pt"))
    ap.add_argument("--steps", type=int, default=20000)
    ap.add_argument("--seq-len", type=int, default=128)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--accum-steps", type=int, default=1,
                    help="effective batch = batch * accum_steps")
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--min-lr", type=float, default=3e-5)
    ap.add_argument("--warmup", type=int, default=500)
    ap.add_argument("--weight-decay", type=float, default=0.1)
    # Architecture — defaults aim at ~944K params (`mid` config in RAM_TABLE.md)
    ap.add_argument("--d-model", type=int, default=256)
    ap.add_argument("--n-layers", type=int, default=8)
    ap.add_argument("--d-head", type=int, default=64)
    ap.add_argument("--top-k", type=int, default=4)
    ap.add_argument("--quantizer", type=str, default="ternary",
                    choices=["ternary", "power3", "power3_pr"],
                    help="weight quantizer for all TernaryLinear/Conv. "
                         "power3 = {0, ±1, ±3, ±9}×α (2.81 bits/wt). "
                         "power3_pr = per-output-row alpha — closes 33%% of "
                         "the FP32→ternary gap in prior internal evidence. "
                         "Research-only; does not export to MCU C engine.")
    # Misc
    ap.add_argument("--bf16", action="store_true",
                    help="bfloat16 autocast on CUDA (no-op on CPU)")
    ap.add_argument("--eval-every", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device}")

    train_ids, val_ids = load_corpus(args.data, args.seq_len)

    model = AtomeLM(
        vocab_size=256,
        d_model=args.d_model,
        n_layers=args.n_layers,
        d_head=args.d_head,
        top_k=args.top_k,
        quantizer=args.quantizer,
    ).to(device)
    n_params = model.parameter_count()
    print(f"params: {n_params:,}  config: d={args.d_model} L={args.n_layers} "
          f"d_head={args.d_head} top_k={args.top_k} quantizer={args.quantizer}")

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr,
                            weight_decay=args.weight_decay,
                            betas=(0.9, 0.95))

    use_bf16 = args.bf16 and device.type == "cuda"
    autocast_ctx = torch.autocast(device_type="cuda", dtype=torch.bfloat16) \
        if use_bf16 else torch.autocast(device_type="cpu", enabled=False)

    log: list[dict] = []
    best_val = float("inf")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    model.train()
    t0 = time.time()
    opt.zero_grad()
    n_train = train_ids.size(0)

    for step in range(args.steps):
        cur_lr = lr_at(step, args.steps, args.lr, args.warmup, args.min_lr)
        for pg in opt.param_groups:
            pg["lr"] = cur_lr

        # Gradient accumulation
        accum_loss = 0.0
        for _ in range(args.accum_steps):
            idx = torch.randint(0, n_train, (args.batch_size,))
            chunk = train_ids[idx].to(device)
            ids, targets = chunk[:, :-1], chunk[:, 1:]
            with autocast_ctx:
                loss = model.loss(ids, targets) / args.accum_steps
            loss.backward()
            accum_loss += loss.item()

        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        opt.zero_grad()

        if step % 50 == 0:
            elapsed = time.time() - t0
            print(f"step {step:6d}/{args.steps}  "
                  f"loss {accum_loss:.4f}  lr {cur_lr:.1e}  "
                  f"({elapsed:.0f}s)")

        if step > 0 and step % args.eval_every == 0:
            val = eval_loss(model, val_ids, args.batch_size, device)
            ppl = math.exp(min(val, 20))  # clamp to avoid overflow on early steps
            print(f"  >> val loss {val:.4f}  ppl {ppl:.2f}")
            log.append({"step": step, "train_loss": accum_loss,
                        "val_loss": val, "val_ppl": ppl, "lr": cur_lr})
            if val < best_val:
                best_val = val
                torch.save(
                    {"state_dict": model.state_dict(),
                     "config": model.config,
                     "step": step, "val_loss": val},
                    args.output,
                )
                print(f"  >> saved best to {args.output} (val {val:.4f})")

    # Final eval + log dump
    final_val = eval_loss(model, val_ids, args.batch_size, device)
    print(f"\nfinal val loss {final_val:.4f}  ppl {math.exp(min(final_val, 20)):.2f}")
    print(f"best val loss  {best_val:.4f}")
    log_path = args.output.with_suffix(".train.json")
    log_path.write_text(json.dumps({
        "params": n_params, "args": vars(args) | {"data": str(args.data),
                                                   "output": str(args.output)},
        "log": log, "final_val": final_val, "best_val": best_val,
    }, indent=2, default=str))
    print(f"wrote {log_path}")


if __name__ == "__main__":
    main()
