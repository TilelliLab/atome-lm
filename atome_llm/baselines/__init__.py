"""Baselines for honest A/B comparison.

Atome's frontier claim is "at fixed flash budget on a $2 MCU, our 3-pathway
ternary architecture dominates plain transformers." That claim only stands
if a plain transformer trained at the same budget actually loses. These
baselines exist to make that comparison real, not vibes.
"""
from atome_llm.baselines.vanilla_transformer import VanillaTransformer

__all__ = ["VanillaTransformer"]
