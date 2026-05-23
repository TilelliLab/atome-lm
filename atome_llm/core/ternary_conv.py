"""atome_llm.core.ternary_conv — depthwise causal 1-D conv, ternary kernel.

Local pathway. Each input channel is convolved with its own kernel
(depthwise; no cross-channel mixing). Causal via left-pad k-1.

Weight shape: (channels, 1, kernel_size). The C engine consumes the
flat (channels * kernel_size) trit array; export flips the spatial axis
because PyTorch conv1d is cross-correlation with weight[c,0,K-1] at the
current position, while the C kernel writes weight[c,0] at the current
position.
"""
from __future__ import annotations

import torch
from torch import Tensor, nn
from torch.nn import functional as F

from atome_llm.core.power3 import power3_quantize
from atome_llm.core.ternary import absmean_scale, ternarize, ternary_signs


# power3_pr (per-row) is a Linear-only variant — depthwise conv weights are
# (channels, 1, K), one row per channel by construction, so per-tensor power3
# is the natural fit here. Accept the name and route to power3 to keep the
# AtomeLM quantizer string single-valued across the model.
_QUANTIZERS = {
    "ternary": ternarize,
    "power3": power3_quantize,
    "power3_pr": power3_quantize,
}


class TernaryCausalConv1d(nn.Module):
    def __init__(self, channels: int, kernel_size: int = 5,
                 quantizer: str = "ternary") -> None:
        super().__init__()
        if quantizer not in _QUANTIZERS:
            raise ValueError(f"quantizer must be one of {list(_QUANTIZERS)}")
        self.channels = channels
        self.kernel_size = kernel_size
        self.quantizer = quantizer
        self._quant_fn = _QUANTIZERS[quantizer]
        w = torch.randn(channels, 1, kernel_size) * (1.0 / kernel_size ** 0.5)
        self.weight = nn.Parameter(w)

    def forward(self, x: Tensor) -> Tensor:
        if x.dim() != 3:
            raise ValueError(f"expected (B, L, C), got shape {tuple(x.shape)}")
        if x.shape[-1] != self.channels:
            raise ValueError(
                f"channel mismatch: module has {self.channels}, input has {x.shape[-1]}"
            )
        x_ = x.transpose(1, 2)
        x_ = F.pad(x_, (self.kernel_size - 1, 0))
        y = F.conv1d(x_, self._quant_fn(self.weight), groups=self.channels)
        return y.transpose(1, 2)

    @torch.no_grad()
    def trits(self) -> Tensor:
        return ternary_signs(self.weight)

    @torch.no_grad()
    def scale(self) -> Tensor:
        return absmean_scale(self.weight)

    @torch.no_grad()
    def infer(self, x: Tensor) -> Tensor:
        x_ = x.transpose(1, 2)
        x_ = F.pad(x_, (self.kernel_size - 1, 0))
        trits = self.trits().to(x.dtype)
        y = self.scale() * F.conv1d(x_, trits, groups=self.channels)
        return y.transpose(1, 2)
