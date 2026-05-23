"""atome_llm.core.ssm — diagonal state-space model.

State pathway. One scalar recurrence per channel:

    h_t[c] = a[c] · h_{t-1}[c] + b[c] · x_t[c]
    y_t[c] = c[c] · h_t[c]

Three learnable per-channel vectors: a_raw (decay; effective a = tanh(a_raw)),
b (input gain), c_out (output scale).

Training uses the convolutional unrolling so a single F.conv1d gives the
whole sequence in one shot. Inference uses the recurrent step — what the
C engine actually runs token-by-token, with constant per-channel hidden
state. A few hundred FP32 scalars live here; the bulk of the parameters
remain ternary in the surrounding linears and conv.
"""
from __future__ import annotations

import math

import torch
from torch import Tensor, nn
from torch.nn import functional as F


class DiagonalSSM(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        self.channels = channels
        # tanh(1.5) ≈ 0.905 → long-ish initial memory
        self.a_raw = nn.Parameter(torch.full((channels,), 1.5))
        self.b = nn.Parameter(torch.randn(channels) * (1.0 / math.sqrt(channels)))
        self.c_out = nn.Parameter(torch.randn(channels) * (1.0 / math.sqrt(channels)))

    def forward(self, x: Tensor) -> Tensor:
        if x.dim() != 3:
            raise ValueError(f"expected (B, L, C), got shape {tuple(x.shape)}")
        B, L, C = x.shape
        if C != self.channels:
            raise ValueError(f"channel mismatch: {self.channels} vs {C}")

        a = torch.tanh(self.a_raw)
        i = torch.arange(L - 1, -1, -1, device=x.device, dtype=x.dtype)
        powers = a.unsqueeze(-1) ** i.unsqueeze(0)
        kernel = (self.c_out * self.b).unsqueeze(-1) * powers
        kernel = kernel.unsqueeze(1)

        x_ = x.transpose(1, 2)
        x_ = F.pad(x_, (L - 1, 0))
        y = F.conv1d(x_, kernel, groups=C)
        return y.transpose(1, 2)

    @torch.no_grad()
    def infer(self, x: Tensor) -> Tensor:
        """Recurrent step-by-step — what the MCU runs at inference."""
        if x.dim() != 3:
            raise ValueError(f"expected (B, L, C), got shape {tuple(x.shape)}")
        B, L, C = x.shape
        a = torch.tanh(self.a_raw)
        h = torch.zeros(B, C, dtype=x.dtype, device=x.device)
        ys = []
        for t in range(L):
            h = a * h + self.b * x[:, t]
            ys.append(self.c_out * h)
        return torch.stack(ys, dim=1)
