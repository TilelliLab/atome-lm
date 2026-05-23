"""atome_llm.core.mcu_block — the Atome MCU Block.

Three pathways mixed by a per-token soft router. Architecture chosen to
match the Atome C99 engine's `atome_block_t` struct exactly:

    x → LayerNorm → ┬─→ Local  (depthwise causal conv k=5)        ─→┐
                    ├─→ State  (diagonal SSM, O(L))                 ─→ Σ → +x
                    └─→ Sparse (top-k attention, O(L·k))            ─→┘
                            ↑              ↑
                            │              router weights r ∈ Δ per token
                            └──────────────┘

Three pathways (not four, not five): the C engine has fixed-size static
buffers for Local, State, and Sparse only. Adding a Wide conv or a
Dense FFN would require C-side struct changes and break bit-exact
parity. This is a deliberate constraint, not a missing feature.

The router still gives the metacognition signal. With three pathways,
maximum entropy is `log(3) ≈ 1.099` nats; high entropy means the model
cannot decide which compute primitive to favor for a given position —
empirically, this correlates with out-of-domain inputs.
"""
from __future__ import annotations

import torch
from torch import Tensor, nn

from atome_llm.core.router import Router
from atome_llm.core.sparse_attention import SparseCausalAttention
from atome_llm.core.ssm import DiagonalSSM
from atome_llm.core.ternary_conv import TernaryCausalConv1d


PATHWAY_NAMES = ("local", "state", "sparse")


class MCUBlock(nn.Module):
    """One Atome MCU block: three parallel pathways + per-token router.

    Parameters
    ----------
    d_model : int
        Channel / embedding dimension.
    d_head : int, default 16
        Head dimension for the Sparse pathway.
    kernel_size : int, default 5
        Local conv kernel length.
    top_k : int, default 4
        Sparse attention top-k.
    skip_threshold : float, default 0.05
        At inference, skip a pathway if its maximum router weight (over
        the batch and sequence) is below this. Training always computes
        every pathway.
    """

    def __init__(
        self,
        d_model: int,
        d_head: int = 16,
        kernel_size: int = 5,
        top_k: int = 4,
        skip_threshold: float = 0.05,
        quantizer: str = "ternary",
        disable_pathways: tuple[str, ...] = (),
    ) -> None:
        super().__init__()
        self.d_model = d_model
        self.skip_threshold = skip_threshold
        self.quantizer = quantizer
        for name in disable_pathways:
            if name not in PATHWAY_NAMES:
                raise ValueError(
                    f"unknown pathway {name!r}; valid: {PATHWAY_NAMES}"
                )
        self.disabled = tuple(disable_pathways)

        self.norm = nn.LayerNorm(d_model)
        self.local = TernaryCausalConv1d(d_model, kernel_size=kernel_size,
                                          quantizer=quantizer)
        self.state = DiagonalSSM(d_model)
        self.sparse = SparseCausalAttention(d_model, d_head=d_head, top_k=top_k,
                                             quantizer=quantizer)
        n_active = 3 - len(self.disabled)
        if n_active < 1:
            raise ValueError("at least one pathway must remain active")
        self.router = Router(d_model, n_pathways=n_active, quantizer=quantizer)

    def _pathways(self) -> list[tuple[str, nn.Module]]:
        all_pw = [("local", self.local), ("state", self.state), ("sparse", self.sparse)]
        return [(n, m) for n, m in all_pw if n not in self.disabled]

    def forward(self, x: Tensor) -> Tensor:
        h = self.norm(x)
        active = self._pathways()
        r = self.router(h)
        outputs = [mod(h) for _, mod in active]
        mixed = sum(r[..., i:i + 1] * outputs[i] for i in range(len(active)))
        return x + mixed

    @torch.no_grad()
    def infer(self, x: Tensor) -> Tensor:
        """Inference forward with dynamic per-batch pathway skip."""
        h = self.norm(x)
        active = self._pathways()
        r = self.router(h)
        r_max = r.amax(dim=(0, 1))
        y = torch.zeros_like(x)
        for i, (_, mod) in enumerate(active):
            if r_max[i].item() >= self.skip_threshold:
                step = mod.infer(h) if hasattr(mod, "infer") else mod(h)
                y = y + r[..., i:i + 1] * step
        return x + y

    @torch.no_grad()
    def router_weights(self, x: Tensor) -> Tensor:
        """Per-token router distribution. Shape (B, L, 3)."""
        return self.router(self.norm(x))

    @torch.no_grad()
    def router_entropy(self, x: Tensor) -> Tensor:
        """Per-token router entropy in nats. Shape (B, L). Bounded by log(3)."""
        return self.router.entropy(self.norm(x))
