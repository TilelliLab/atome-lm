"""atome_llm.tokenize — byte tokenizer.

Raw UTF-8 bytes, vocab size 256. No BPE, no learned tokenizer. Matches
the C engine's expected `int tokens[]` array exactly.
"""
from __future__ import annotations

import torch
from torch import Tensor


class ByteTokenizer:
    vocab_size = 256

    def encode(self, text: str) -> Tensor:
        """Encode UTF-8 text to int64 ids. Shape: (len_in_bytes,)."""
        return torch.tensor(list(text.encode("utf-8")), dtype=torch.long)

    def decode(self, ids: Tensor) -> str:
        """Decode int ids back to UTF-8 text. Replaces invalid bytes."""
        if ids.dim() != 1:
            ids = ids.flatten()
        return bytes(int(b) for b in ids.tolist()).decode("utf-8", errors="replace")
