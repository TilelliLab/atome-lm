"""atome_llm.baselines.vanilla_transformer — minimal GPT-style baseline.

A plain decoder-only Transformer with a byte tokenizer. FP32, full
softmax attention, learned positional embeddings, GELU FFN. This is the
reference architecture every public tiny-LM (Karpathy's `Stories260K`,
the TinyStories paper, BitNet at small scales) uses, modulo trivia.

Used purely as the A/B baseline for Atome's 3-pathway ternary block.
NOT shipped to any MCU — a 60 K-param FP32 model is ~240 KB of FP32
weights, far too big for the smallest targets.
"""
from __future__ import annotations

import math

import torch
from torch import Tensor, nn
from torch.nn import functional as F


class CausalSelfAttention(nn.Module):
    def __init__(self, d_model: int, n_heads: int, max_seq: int) -> None:
        super().__init__()
        if d_model % n_heads != 0:
            raise ValueError(f"d_model {d_model} not divisible by n_heads {n_heads}")
        self.n_heads = n_heads
        self.d_head = d_model // n_heads
        self.qkv = nn.Linear(d_model, 3 * d_model, bias=False)
        self.out = nn.Linear(d_model, d_model, bias=False)
        mask = torch.tril(torch.ones(max_seq, max_seq, dtype=torch.bool))
        self.register_buffer("mask", mask, persistent=False)

    def forward(self, x: Tensor) -> Tensor:
        B, L, D = x.shape
        qkv = self.qkv(x).reshape(B, L, 3, self.n_heads, self.d_head)
        q, k, v = qkv.unbind(dim=2)
        q = q.transpose(1, 2)  # (B, H, L, d_head)
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)
        scores = (q @ k.transpose(-2, -1)) / math.sqrt(self.d_head)
        scores = scores.masked_fill(~self.mask[:L, :L], float("-inf"))
        attn = scores.softmax(dim=-1)
        out = (attn @ v).transpose(1, 2).reshape(B, L, D)
        return self.out(out)


class FeedForward(nn.Module):
    def __init__(self, d_model: int, d_ff: int) -> None:
        super().__init__()
        self.up = nn.Linear(d_model, d_ff, bias=False)
        self.down = nn.Linear(d_ff, d_model, bias=False)

    def forward(self, x: Tensor) -> Tensor:
        return self.down(F.gelu(self.up(x)))


class Block(nn.Module):
    def __init__(self, d_model: int, n_heads: int, d_ff: int, max_seq: int) -> None:
        super().__init__()
        self.norm1 = nn.LayerNorm(d_model)
        self.attn = CausalSelfAttention(d_model, n_heads, max_seq)
        self.norm2 = nn.LayerNorm(d_model)
        self.ffn = FeedForward(d_model, d_ff)

    def forward(self, x: Tensor) -> Tensor:
        x = x + self.attn(self.norm1(x))
        x = x + self.ffn(self.norm2(x))
        return x


class VanillaTransformer(nn.Module):
    """Minimal GPT-style baseline matching AtomeLM's interface.

    Parameters
    ----------
    vocab_size : int, default 256
    d_model : int, default 64
    n_layers : int, default 4
    n_heads : int, default 4
    d_ff : int, default 4 * d_model
    max_seq : int, default 64

    Exposes the same `forward(ids) -> logits`, `loss(ids, targets)`,
    `generate(ids, n_new_tokens, ...)`, `parameter_count()` API as
    AtomeLM so the A/B trainer code is shared.
    """

    def __init__(
        self,
        vocab_size: int = 256,
        d_model: int = 64,
        n_layers: int = 4,
        n_heads: int = 4,
        d_ff: int | None = None,
        max_seq: int = 64,
    ) -> None:
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.n_layers = n_layers
        self.max_seq = max_seq
        d_ff = d_ff if d_ff is not None else 4 * d_model

        self.tok_embed = nn.Embedding(vocab_size, d_model)
        self.pos_embed = nn.Embedding(max_seq, d_model)
        self.blocks = nn.ModuleList(
            [Block(d_model, n_heads, d_ff, max_seq) for _ in range(n_layers)]
        )
        self.norm_final = nn.LayerNorm(d_model)
        self.unembed = nn.Linear(d_model, vocab_size, bias=False)

    @property
    def config(self) -> dict:
        return {
            "kind": "vanilla_transformer_fp32",
            "vocab_size": self.vocab_size,
            "d_model": self.d_model,
            "n_layers": self.n_layers,
            "n_heads": self.blocks[0].attn.n_heads,
            "d_ff": self.blocks[0].ffn.up.out_features,
            "max_seq": self.max_seq,
        }

    def forward(self, ids: Tensor) -> Tensor:
        if ids.dim() != 2:
            raise ValueError(f"expected (B, L), got {tuple(ids.shape)}")
        B, L = ids.shape
        if L > self.max_seq:
            raise ValueError(f"L={L} exceeds max_seq={self.max_seq}")
        pos = torch.arange(L, device=ids.device).unsqueeze(0).expand(B, L)
        x = self.tok_embed(ids) + self.pos_embed(pos)
        for block in self.blocks:
            x = block(x)
        x = self.norm_final(x)
        return self.unembed(x)

    def loss(self, ids: Tensor, targets: Tensor) -> Tensor:
        logits = self.forward(ids)
        return F.cross_entropy(
            logits.reshape(-1, self.vocab_size), targets.reshape(-1)
        )

    @torch.no_grad()
    def generate(
        self,
        ids: Tensor,
        n_new_tokens: int,
        max_seq: int | None = None,
        temperature: float = 0.0,
        top_p: float = 1.0,
        top_k: int | None = None,
        generator: torch.Generator | None = None,
    ) -> Tensor:
        max_seq = max_seq if max_seq is not None else self.max_seq
        was_training = self.training
        self.eval()
        try:
            for _ in range(n_new_tokens):
                ids_in = ids[:, -max_seq:]
                logits = self.forward(ids_in)[:, -1, :]
                if temperature == 0.0:
                    next_id = logits.argmax(dim=-1, keepdim=True)
                else:
                    scaled = logits / temperature
                    if top_k is not None and top_k < scaled.size(-1):
                        kth = scaled.topk(top_k, dim=-1).values[..., -1:]
                        scaled = torch.where(
                            scaled < kth,
                            torch.full_like(scaled, float("-inf")),
                            scaled,
                        )
                    if top_p < 1.0:
                        sl, si = scaled.sort(dim=-1, descending=True)
                        sp = torch.softmax(sl, dim=-1)
                        cum = sp.cumsum(dim=-1)
                        mask = cum - sp > top_p
                        sl = sl.masked_fill(mask, float("-inf"))
                        scaled = torch.full_like(scaled, float("-inf")).scatter(
                            -1, si, sl
                        )
                    probs = torch.softmax(scaled, dim=-1)
                    next_id = torch.multinomial(
                        probs, num_samples=1, generator=generator
                    )
                ids = torch.cat([ids, next_id], dim=1)
            return ids
        finally:
            if was_training:
                self.train()

    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters())


def matched_param_config(target_params: int, vocab_size: int = 256,
                         max_seq: int = 64, n_heads: int = 4,
                         min_d: int = 8, max_d: int = 256) -> dict:
    """Find a (d_model, n_layers, d_ff) that lands near `target_params`.

    Brute-force search — the model is tiny so this is cheap. Helps build
    fair-budget baselines without manual tuning.
    """
    best = None
    for d_model in range(max(min_d, n_heads), max_d + 1, n_heads):
        for n_layers in range(1, 8):
            for ff_mul in (1, 2, 3, 4):
                d_ff = ff_mul * d_model
                m = VanillaTransformer(
                    vocab_size=vocab_size, d_model=d_model,
                    n_layers=n_layers, n_heads=n_heads, d_ff=d_ff,
                    max_seq=max_seq,
                )
                p = m.parameter_count()
                err = abs(p - target_params)
                if best is None or err < best[0]:
                    best = (err, p, dict(
                        d_model=d_model, n_layers=n_layers,
                        n_heads=n_heads, d_ff=d_ff,
                    ))
    return {"params": best[1], "err": best[0], **best[2]}
