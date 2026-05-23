"""Atome LLM core primitives — ternary quantizer, ternary linear / conv,
diagonal SSM, sparse attention, the per-token router, and the
3-pathway MCU block + LM."""

from atome_llm.core.atome_lm import AtomeLM
from atome_llm.core.mcu_block import MCUBlock, PATHWAY_NAMES
from atome_llm.core.router import Router
from atome_llm.core.sparse_attention import SparseCausalAttention
from atome_llm.core.ssm import DiagonalSSM
from atome_llm.core.ternary import absmean_scale, ternarize, ternary_signs
from atome_llm.core.ternary_conv import TernaryCausalConv1d
from atome_llm.core.ternary_embedding import TernaryEmbedding
from atome_llm.core.ternary_linear import TernaryLinear

__all__ = [
    "AtomeLM",
    "MCUBlock",
    "PATHWAY_NAMES",
    "Router",
    "SparseCausalAttention",
    "DiagonalSSM",
    "absmean_scale",
    "ternarize",
    "ternary_signs",
    "TernaryCausalConv1d",
    "TernaryEmbedding",
    "TernaryLinear",
]
