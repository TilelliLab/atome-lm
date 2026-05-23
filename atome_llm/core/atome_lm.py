"""atome_llm.core.atome_lm — byte-level LM stacking the MCU block.

Token embedding (no positional embedding, to match the C engine's binary
format which exports only the token table). The model relies on the
Local conv and the SSM's hidden state to handle position implicitly —
the C engine's static buffers are sized for sequences up to
`ATOME_MAX_SEQ` (default 32) so absolute position is rarely informative
beyond what the convolution and recurrence already provide.

For sequences longer than the C engine's compile-time max, generate
token-by-token: the SSM carries state across calls.
"""
from __future__ import annotations

import torch
from torch import Tensor, nn
from torch.nn import functional as F

from atome_llm.core.mcu_block import MCUBlock
from atome_llm.core.ternary_embedding import TernaryEmbedding
from atome_llm.core.ternary_linear import TernaryLinear


class AtomeLM(nn.Module):
    """Byte-level Atome language model.

    Parameters
    ----------
    vocab_size : int, default 256
        Byte vocabulary.
    d_model : int, default 64
        Residual stream width. Defaults match `atome.h`.
    n_layers : int, default 4
        Number of MCU blocks.
    d_head : int, default 16
        Per-block sparse-attention head dim.
    top_k : int, default 4
        Per-block sparse-attention top-k.
    kernel_size : int, default 5
        Per-block Local conv kernel.
    """

    def __init__(
        self,
        vocab_size: int = 256,
        d_model: int = 64,
        n_layers: int = 4,
        d_head: int = 16,
        top_k: int = 4,
        kernel_size: int = 5,
        quantizer: str = "ternary",
        disable_pathways: tuple[str, ...] = (),
    ) -> None:
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.n_layers = n_layers
        self.d_head = d_head
        self.top_k = top_k
        self.kernel_size = kernel_size
        self.quantizer = quantizer
        self.disable_pathways = tuple(disable_pathways)

        # Index-style ternary embedding — weight shape (vocab, d_model)
        # to match the C engine's tok * d + i lookup. TernaryLinear would
        # store (d_model, vocab), which the engine reads as garbage.
        self.embed = TernaryEmbedding(vocab_size, d_model, quantizer=quantizer)
        self.blocks = nn.ModuleList(
            [
                MCUBlock(
                    d_model=d_model,
                    d_head=d_head,
                    kernel_size=kernel_size,
                    top_k=top_k,
                    quantizer=quantizer,
                    disable_pathways=self.disable_pathways,
                )
                for _ in range(n_layers)
            ]
        )
        self.final_norm = nn.LayerNorm(d_model)
        self.unembed = TernaryLinear(d_model, vocab_size, quantizer=quantizer)

    @property
    def config(self) -> dict:
        """Configuration dict matching the C engine's compile-time defines."""
        return {
            "vocab_size": self.vocab_size,
            "d_model": self.d_model,
            "n_layers": self.n_layers,
            "d_head": self.d_head,
            "top_k": self.top_k,
            "kernel_size": self.kernel_size,
            "n_pathways": 3,
        }

    def forward(self, ids: Tensor) -> Tensor:
        """ids: (B, L) int64. Returns logits (B, L, vocab)."""
        if ids.dim() != 2:
            raise ValueError(f"expected (B, L), got shape {tuple(ids.shape)}")
        x = self.embed(ids)
        for block in self.blocks:
            x = block(x)
        x = self.final_norm(x)
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
        max_seq: int = 32,
        temperature: float = 0.0,
        top_p: float = 1.0,
        top_k: int | None = None,
        generator: torch.Generator | None = None,
    ) -> Tensor:
        """Continuation. Trims context to `max_seq` (the engine's window).

        Default `temperature=0.0` is greedy argmax — preserves bit-exact
        parity with the C engine's `atome_predict_next` and keeps the
        existing parity tests valid. Set `temperature > 0` for sampling.

        Parameters
        ----------
        ids : (B, L) int64 prompt.
        n_new_tokens : number of tokens to append.
        max_seq : context window the engine compiled with.
        temperature : 0 = argmax. >0 scales logits before softmax.
        top_p : nucleus probability mass. 1.0 = no truncation.
        top_k : optional top-k truncation (applied before top_p).
        generator : optional torch.Generator for reproducibility.

        On a real MCU you would not re-run the full window each step; you
        would keep the SSM state across calls. This Python `generate` is
        the simple reference implementation.
        """
        if temperature < 0:
            raise ValueError(f"temperature must be >= 0, got {temperature}")
        if not 0.0 < top_p <= 1.0:
            raise ValueError(f"top_p must be in (0, 1], got {top_p}")
        if top_k is not None and top_k < 1:
            raise ValueError(f"top_k must be >= 1 if set, got {top_k}")

        was_training = self.training
        self.eval()
        try:
            for _ in range(n_new_tokens):
                ids_in = ids[:, -max_seq:]
                logits = self.forward(ids_in)[:, -1, :]
                next_id = self._sample_next(
                    logits, temperature, top_p, top_k, generator
                )
                ids = torch.cat([ids, next_id], dim=1)
            return ids
        finally:
            if was_training:
                self.train()

    @staticmethod
    def _sample_next(
        logits: Tensor,
        temperature: float,
        top_p: float,
        top_k: int | None,
        generator: torch.Generator | None,
    ) -> Tensor:
        if temperature == 0.0:
            return logits.argmax(dim=-1, keepdim=True)

        scaled = logits / temperature
        if top_k is not None and top_k < scaled.size(-1):
            kth = scaled.topk(top_k, dim=-1).values[..., -1:]
            scaled = torch.where(
                scaled < kth, torch.full_like(scaled, float("-inf")), scaled
            )
        if top_p < 1.0:
            sorted_logits, sorted_idx = scaled.sort(dim=-1, descending=True)
            sorted_probs = torch.softmax(sorted_logits, dim=-1)
            cum = sorted_probs.cumsum(dim=-1)
            mask = cum - sorted_probs > top_p
            sorted_logits = sorted_logits.masked_fill(mask, float("-inf"))
            scaled = torch.full_like(scaled, float("-inf")).scatter(
                -1, sorted_idx, sorted_logits
            )

        probs = torch.softmax(scaled, dim=-1)
        return torch.multinomial(probs, num_samples=1, generator=generator)

    @torch.no_grad()
    def router_entropies(self, ids: Tensor) -> list[Tensor]:
        """Per-layer per-token router entropy. List of (B, L) tensors."""
        x = self.embed(ids)
        out = []
        for block in self.blocks:
            out.append(block.router_entropy(x))
            x = block(x)
        return out

    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters())
