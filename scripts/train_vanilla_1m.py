#!/usr/bin/env python3
"""scripts/train_vanilla_1m.py — param-fair vanilla-FP32 GPT baseline.

Exact mirror of scripts/train_atome_1m.py except the model class is
VanillaTransformer (FP32, standard causal self-attention + GELU FFN).
Used as the A/B baseline for atome_1m_v1.pt.

Param-fair config defaults (d=152, L=3, d_ff=608, n_heads=4) land at
~950,608 params, +0.63% off atome_1m_v1's 944,640. Same data path, same
seq_len, batch_size, accum_steps, optimizer, LR schedule, BF16, seed.
The val slice is identical because load_corpus seeds randperm with 0.

Recipe (same as Recipe B in TRAIN_1M_RUNBOOK.md):
  python scripts/train_vanilla_1m.py \
      --data data/tinystories_full.txt \
      --output checkpoints/vanilla_1m_v1.pt \
      --steps 30000 --seq-len 256 --batch-size 64 --accum-steps 4 \
      --lr 3e-4 --min-lr 3e-5 --warmup 1000 --weight-decay 0.1 \
      --bf16 --eval-every 1000 --seed 0
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

from atome_llm.baselines.vanilla_transformer import VanillaTransformer  # noqa: E402
from atome_llm.tokenize import ByteTokenizer  # noqa: E402


def load_corpus(path: Path, seq_len: int, val_frac: float = 0.1
                ) -> tuple[torch.Tensor, torch.Tensor]:
    """Identical to train_atome_1m.load_corpus — same seed → same val slice."""
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
def eval_loss(model: VanillaTransformer, val_ids: torch.Tensor, batch_size: int,
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
                    default=Path("checkpoints/vanilla_1m.pt"))
    ap.add_argument("--steps", type=int, default=30000)
    ap.add_argument("--seq-len", type=int, default=256)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--accum-steps", type=int, default=4)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--min-lr", type=float, default=3e-5)
    ap.add_argument("--warmup", type=int, default=1000)
    ap.add_argument("--weight-decay", type=float, default=0.1)
    # Param-fair vanilla config — ~950K params vs atome_1m_v1's 944K (+0.63%).
    ap.add_argument("--d-model", type=int, default=152)
    ap.add_argument("--n-layers", type=int, default=3)
    ap.add_argument("--n-heads", type=int, default=4)
    ap.add_argument("--d-ff", type=int, default=608)
    ap.add_argument("--max-seq", type=int, default=256)
    ap.add_argument("--bf16", action="store_true")
    ap.add_argument("--eval-every", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device: {device}")

    train_ids, val_ids = load_corpus(args.data, args.seq_len)

    model = VanillaTransformer(
        vocab_size=256,
        d_model=args.d_model,
        n_layers=args.n_layers,
        n_heads=args.n_heads,
        d_ff=args.d_ff,
        max_seq=args.max_seq,
    ).to(device)
    n_params = model.parameter_count()
    print(f"params: {n_params:,}  config: d={args.d_model} L={args.n_layers} "
          f"n_heads={args.n_heads} d_ff={args.d_ff} max_seq={args.max_seq}")

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
            ppl = math.exp(min(val, 20))
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

    final_val = eval_loss(model, val_ids, args.batch_size, device)
    print(f"\nfinal val loss {final_val:.4f}  ppl {math.exp(min(final_val, 20)):.2f}")
    print(f"best val loss  {best_val:.4f}")
    log_path = args.output.with_suffix(".train.json")
    log_path.write_text(json.dumps({
        "params": n_params,
        "args": vars(args) | {"data": str(args.data), "output": str(args.output)},
        "log": log, "final_val": final_val, "best_val": best_val,
    }, indent=2, default=str))
    print(f"wrote {log_path}")


if __name__ == "__main__":
    main()
