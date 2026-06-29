"""superesp.framework.model — SuperESPHead: Atome base + ternary classifier head.

Wraps the existing `AtomeLM` (embedding + MCU blocks + final norm + unembed)
and adds a ternary classification head over the LAST token's final-norm hidden
state — exactly what the C `atome_classify` computes
(`c_engine/upstream/atome.c`: it runs the base forward, takes
`state->x[n_tokens-1]` after `final_norm`, then `head @ hidden`).

The base `unembed` is kept (so the exported blob matches the ATOMECL01 layout,
which the C loader reads then skips) but is unused for classification.
"""
from __future__ import annotations

import torch
from torch import Tensor, nn

from atome_llm.core.atome_lm import AtomeLM
from atome_llm.core.ternary_linear import TernaryLinear

from superesp.framework.config import SuperESPConfig, SHARED


class SuperESPHead(nn.Module):
    """Tiny ternary head over the frozen-able Atome backbone.

    task="classify" -> n_classes logits + cross-entropy (argmax decision).
    task="regress"  -> n_classes continuous outputs + MSE (the C engine returns
                       these raw via class_logits; firmware de-scales them).
    Both export to the SAME ATOMECL01 format (n_classes = output count).
    """

    def __init__(self, n_classes: int, config: SuperESPConfig = SHARED,
                 task: str = "classify") -> None:
        super().__init__()
        if not (0 < n_classes <= config.max_classes):
            raise ValueError(
                f"n_classes must be in 1..{config.max_classes}, got {n_classes}"
            )
        if task not in ("classify", "regress"):
            raise ValueError(f"task must be classify|regress, got {task!r}")
        self.config = config
        self.n_classes = n_classes
        self.task = task
        self.base = AtomeLM(**config.atome_kwargs())
        # Head: (n_classes, d_model) weight via nn.Linear convention, matches
        # the C engine's `read_ternary(&clf->head, n_classes, d)` + matvec.
        self.head = TernaryLinear(config.d_model, n_classes)

    def _last_hidden(self, ids: Tensor) -> Tensor:
        """Final-norm hidden state of the LAST token. (B, d_model)."""
        if ids.dim() != 2:
            raise ValueError(f"expected (B, L), got {tuple(ids.shape)}")
        x = self.base.embed(ids)
        for block in self.base.blocks:
            x = block(x)
        x = self.base.final_norm(x)
        return x[:, -1, :]

    def forward(self, ids: Tensor) -> Tensor:
        """ids: (B, L) int64 byte tokens. Returns class logits (B, n_classes)."""
        return self.head(self._last_hidden(ids))

    def loss(self, ids: Tensor, labels: Tensor) -> Tensor:
        out = self.forward(ids)
        if self.task == "regress":
            target = labels.float()
            if target.dim() == 1:
                target = target.unsqueeze(-1)
            return nn.functional.mse_loss(out, target)
        return nn.functional.cross_entropy(out, labels)

    @torch.no_grad()
    def predict(self, ids: Tensor) -> tuple[Tensor, Tensor]:
        """Classify: (class_idx (B,), softmax_probs (B, n_classes))."""
        self.eval()
        logits = self.forward(ids)
        probs = torch.softmax(logits, dim=-1)
        return probs.argmax(dim=-1), probs

    @torch.no_grad()
    def predict_value(self, ids: Tensor) -> Tensor:
        """Regress: raw continuous outputs (B, n_classes) in normalized space."""
        self.eval()
        return self.forward(ids)

    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters())
