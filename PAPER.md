**English** · [Français](PAPER.fr.md) · [Español](PAPER.es.md) · [简体中文](PAPER.zh-CN.md) · [Deutsch](PAPER.de.md) · [日本語](PAPER.ja.md) <!-- i18n-switcher -->

# Atome LM — architecture for microcontroller-native ternary language models

## 1. Motivation

The smallest language models that "actually talk" sit, today, in the 100 M–1 B parameter range. Every one of those models requires more RAM and more memory bandwidth than a $2 microcontroller can offer. The architecture choices in those models — full attention, dense FFNs, multi-bank MoE, retrieval-augmented pathways — are choices made under the assumption that RAM is cheap. Atome LM starts from the opposite assumption: RAM is the constraint that dominates every other consideration.

The result is a deliberately narrow architecture, designed end-to-end for compatibility with a fixed-shape C99 inference engine that runs on chips with kilobytes — not megabytes — of working RAM.

## 2. Constraints from the engine

The Atome C99 engine's `atome_block_t` struct is fixed at:

```
norm        : LayerNorm
local_conv  : depthwise causal conv, ternary kernel
ssm         : diagonal SSM (per-channel a, b, c_out, FP32)
attn        : top-k causal attention, ternary Q/K/V
router      : ternary linear → softmax over 3 pathways
```

Static buffers exist for each of those three pathway outputs and for the SSM hidden state and the attention KV cache. There is no buffer for a wide-conv, no buffer for a dense FFN, no provision for multi-bank weights, no per-row scale in the ternary kernel. Trying to train a wider architecture and "fit it later" would either require regenerating the C struct (breaking the bit-exact-parity contract this project rests on) or shipping un-supported pathways that get silently dropped at inference.

Atome LM therefore matches the engine exactly: three pathways, per-tensor scale, byte tokenizer, no positional embedding, sequence length capped by `ATOME_MAX_SEQ` at compile time.

## 3. The block

```
x → LayerNorm → ┬─→ Local   (depthwise causal conv, k=5)        ─→┐
                ├─→ State   (diagonal SSM, O(L))                  ─→ Σ → +x
                └─→ Sparse  (top-k attention, O(L·k))             ─→┘
                        ↑              ↑
                        │              router weights r ∈ Δ per token
                        └──────────────┘
```

Three structurally-different operations:

| # | Name   | Operation               | Job                          |
|---|--------|-------------------------|------------------------------|
| 1 | Local  | Depthwise conv k=5      | Bigrams, word boundaries     |
| 2 | State  | Diagonal SSM            | Long-range topic carry       |
| 3 | Sparse | Top-k attention         | Coreference, exact recall    |

The router is a `TernaryLinear(d_model, 3)` followed by softmax. It produces a 3-way distribution per token; the block output is the residual plus the convex combination of the pathway outputs under that distribution.

### 3.1 Router entropy as a calibration signal

The per-token router distribution carries an uncertainty signal:

```
H(r_t) = − Σ_i r_t,i · log r_t,i,    bounded in [0, log 3] for 3 pathways
```

High entropy means the router could not decide which compute primitive was most appropriate for the position. The signal is structural — it requires no uncertainty-specific training and no extra parameters. At the Atome-LLM engine-default scale (60 K parameters, single narrow corpus) the signal is exposed but its calibration as an uncertainty estimator at this scale is not evaluated here. In a larger 3 M-parameter model **not included in this release**, we have *preliminarily* observed router entropy tracking out-of-domain inputs and correlating with per-token loss; we report this only as a **not-yet-reproducible observation** and intend to publish the supporting measurements in a future release. Measuring it (e.g. expected calibration error between router entropy and per-token loss) is a separate exercise.

`MCUBlock.router_entropy(x)` returns the per-token entropy in nats. `AtomeLM.router_entropies(ids)` returns per-layer per-token entropy as a list of `(B, L)` tensors. The C engine's `atome_state_t` exposes the per-token router weights array `router_w[ATOME_MAX_SEQ][ATOME_N_PATHWAYS]` — entropy is a sum/log over that.

## 4. Size and shape budget

At the engine's default `#define`s (`d_model=64`, `n_layers=4`, `d_head=16`, `vocab=256`, `kernel=5`):

- Embedding: 256 × 64 = 16,384 trits
- Per block: norm (256 FP32) + conv (64 × 5 trits) + SSM (3 × 64 FP32) + Wq/Wk/Wv (16 × 64 + 16 × 64 + 64 × 64 trits) + router (3 × 64 trits)
- Final norm: 128 FP32
- Unembed: 64 × 256 trits

Packed at 2 bits per trit, the binary is on the order of 30–60 KB depending on configuration. Comfortably below 100 KB for typical defaults, well below the 1 MB flash of a low-end STM32, and orders of magnitude smaller than the 8 MB available on an ESP32-S3.

RAM use at inference is dominated by the static buffers in `atome_state_t`: `x`, `normed`, three pathway-output scratch arrays, an SSM hidden-state array per layer, the KV caches, the router weights buffer, the logits buffer. At defaults this totals a few KB.

## 5. What is not in this release

- No multi-bank weight MoE (the engine does not support it; would break bit-exact parity).
- No per-row ternary scale (same reason).
- No positional embedding. The Local conv and the SSM hidden state encode position implicitly within the engine's compile-time sequence window.
- No retrieval pathway, no episodic-memory pathway. Both require off-chip storage or large RAM scratch arrays incompatible with the target hardware.

These are deliberate omissions, not gaps. They are the cost of running on hardware where RAM is the binding constraint.

## 6. Limitations

- **Scale.** The default configuration is roughly 60 K parameters (`d_model=64`, `n_layers=4`). Train this narrow on a focused corpus and it speaks fluently in scope; train it wide and it will not be coherent. That is a reflection of capacity, not architecture. For more headroom raise `d_model` and `n_layers` — e.g. `d_model=128`, `n_layers=6` is roughly 600 K parameters.
- **Sequence length.** Capped by `ATOME_MAX_SEQ` at engine compile time (default 32). For longer-form generation, generate token-by-token by passing the growing prefix to `atome_predict_next` — the engine re-derives the SSM hidden state from the full prefix each call, which keeps Python ↔ C parity deterministic.
- **Tokenization.** Byte-level. UTF-8 multi-byte sequences cost multiple positions. Not ideal for non-Latin scripts at the engine's default `MAX_SEQ`; consider raising `ATOME_MAX_SEQ` and re-exporting if your target script has a high mean bytes-per-character.

## References

- Ma et al., 2024. *The Era of 1-bit LLMs: All Large Language Models are in 1.58 Bits.* arXiv:2402.17764.
- Wang et al., 2023. *BitNet: Scaling 1-bit Transformers for Large Language Models.* arXiv:2310.11453.
- Gu and Dao, 2023. *Mamba: Linear-Time Sequence Modeling with Selective State Spaces.* arXiv:2312.00752.
