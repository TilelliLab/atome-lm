# Delta-Inference Experiment — Results

**Date:** 2026-05-19
**Question:** Can Atome skip recomputation the way the eye doesn't re-render a static
wall? Measure full-recompute vs temporal-delta ternary matvec.

## Setup

- Ternary matrix 256×256 (mirrors the 944K Atome model's `d_model`), ~1/3 zeros
- 256-step input stream, three input regimes
- `out_new = out_old + W @ (x_new - x_prev)` — exact at threshold 0
- Selective `x_prev` update: only propagated channels update, so each channel's
  pending error is bounded by `threshold` at all times — this is integrate-and-fire
- Energy proxy: `iters` = inner-loop trips (each trip unpacks a trit + branches,
  ~1 cycle on an MCU regardless of whether it MACs). Deterministic and exact.

## Results (host, per-path cycles measured separately)

| Regime | threshold | iter speedup | cycle speedup | max error |
|---|---|---|---|---|
| **Sensor stream** | 0.000 | 1.00× | 1.04× | 0.00001 |
| (correlated input) | 0.005 | **17.52×** | 15.66× | 0.00715 |
| | 0.020 | **51.24×** | 42.96× | 0.01845 |
| | 0.050 | **59.67×** | 49.07× | 0.03455 |
| **Token embeddings** | 0.000 | 1.00× | 1.04× | 0.00001 |
| (uncorrelated / LM gen) | 0.005 | 1.01× | 1.05× | 0.00072 |
| **Hidden-state proxy** | 0.000 | 3.30× | 3.25× | 0.00001 |
| (~30% channels move) | 0.005 | 3.39× | 3.34× | 0.00171 |
| | 0.020 | 3.68× | 3.59× | 0.01163 |

QEMU Cortex-M3 (`mps2-an385`): `iters` are **bit-identical** to host
(16,711,680 / 954,112 / 326,144 / …) — the energy proxy reproduces exactly on the
target ISA. The on-target DWT cycle counter reads 0 because QEMU's `mps2-an385`
does not model `DWT->CYCCNT`; real-silicon cycle numbers need a Cortex-M3 dev
board or a cycle-accurate model. The host wall-clock already confirms `iters`
tracks real cycles (15.66× cycle vs 17.52× iter — the gap is loop/call overhead).

## Findings

1. **The win is real and large — but only for correlated input.** A sensor-style
   stream at threshold 0.005 runs **17.5× fewer operations** for a worst-case
   output error of 0.007 (the weights have scale 0.05, so this is ~0.7% of a
   typical logit). At threshold 0.02 it is **51×**. For an MCU device that is a
   thermostat, an accelerometer gesture detector, or an audio keyword spotter,
   this is a direct 17–51× cut in inference energy.

2. **No free lunch for token-LM generation — confirmed.** Scenario B holds at
   1.0×. Consecutive byte embeddings are uncorrelated; there is no "static wall"
   to skip. This is the honest result and it matches the prediction. Delta
   inference is an *input-modality* optimization, not a universal one.

3. **Mid-network hidden states sit in between (~3.3×).** Even with no threshold,
   a residual stream where ~30% of channels move per step gives 3.3× for free
   (exact, error 1e-5) because 70% of the matvec is genuinely redundant. This is
   the most interesting number: it suggests delta inference helps *within* the
   network even when the token input doesn't, especially for the SSM pathway
   whose state evolves slowly.

4. **The threshold is literally a firing threshold.** Because `x_prev` updates
   only for propagated channels, a channel with sub-threshold drift integrates
   silently until it crosses the bar, fires once, and resets. Error is bounded by
   `threshold` with no accumulation and no periodic "saccade" refresh required.
   The energy/accuracy tradeoff is a single knob.

## Honest limitations

- The 256×256 synthetic matrix is representative but not a trained Atome weight
  set — real weight sparsity structure may shift the constants (not the trend).
- Only the matvec is delta-ised. LayerNorm/SSM/attention are nonlinear; a full
  integration needs delta-aware (or periodically-refreshed) variants of those.
- "iters" is a faithful energy proxy for the matvec inner loop but ignores
  memory-traffic energy, which on a real MCU can dominate — the *real* speedup on
  silicon could be higher (less data movement) or lower (worse cache behaviour
  from the col-major delta access pattern). Needs a dev-board measurement.
- Token-regime result (1.0×) is the honest ceiling: do not pitch delta inference
  as an LM-generation speedup. Pitch it for streaming-sensor classifiers.

## Recommendation

Wire delta inference as an **opt-in mode for streaming-classifier deployments**
(Atome's `atome_classify` path on sensor input), not the generative path. The
SSM pathway is the natural place to extend it next — its state is the slowest-
moving signal in the network. Pair the threshold with the L11 state-norm monitor
(from the security stack) as the drift watchdog. Expected envelope: **15–50×
inference-energy reduction** for thermostat/audio/gesture-class devices, at a
tunable, bounded accuracy cost.

## Reproduce

```bash
cd c_engine/experiments/delta_inference
make run        # host (synthetic)
make run-qemu   # cortex-m3 under QEMU (iters bit-identical to host)
make real       # validation on the real 944K weights (see below)
```

---

# Extension: validation on the real 944K Atome model

The synthetic experiment above used a random matrix. This section runs the
delta path against `checkpoints/atome_1m_v1.pt` (the real trained 944K model,
val_loss 1.0545) on a real 196-byte TinyStories passage.

`capture_real.py` hooks every block, captures the real post-norm input and
each pathway output, and measures per-signal delta redundancy. `bench_real.c`
then runs the **C** `dm_matvec_delta` over the real captured streams using the
model's **real ternarized attention Wv**, and confirms the C primitive
reproduces the numpy prediction.

## Per-pathway delta-matvec speedup (real weights, 8-block average)

| Signal a matvec consumes | thr 0.0 | thr 0.02 | thr 0.05 | thr 0.10 |
|---|---|---|---|---|
| post-norm input `h` | 1.00× | 1.05× | 1.11× | 1.17× |
| conv pathway output | 1.01× | 1.06× | 1.12× | 1.22× |
| **SSM pathway output** | 1.00× | **4.06×** | **12.27×** | **45.16×** |
| attention pathway output | 1.02× | 1.07× | 1.15× | 1.27× |

## C primitive cross-check (block 0, real Wv 256×256, scale 0.0412)

| matvec | thr 0.0 | thr 0.02 | thr 0.05 | thr 0.10 |
|---|---|---|---|---|
| `Wv @ h` (numpy predict) | 1.03× | 1.26× | 1.53× | 1.61× |
| `Wv @ h` (**C measured**) | 1.03× | 1.26× | 1.53× | 1.61× |
| `Wv @ ssm_out` (numpy predict) | 1.00× | 3.12× | 8.60× | 33.64× |
| `Wv @ ssm_out` (**C measured**) | 1.00× | 3.12× | 8.60× | 33.64× |

The C delta primitive and the numpy reference agree **exactly** on real
trained weights and real activations. Max per-channel error stays ≤ threshold
(measured 0.10000 at thr 0.10) — the integrate-and-fire bound holds on real data.

## Findings — and one honest negative

1. **The SSM pathway output is the delta sweet spot, by a wide margin.** On
   real weights it is 4–45× delta-compressible; every other signal in the
   block is 1.0–1.3×. A matvec fed by the SSM output does 12× less work at
   threshold 0.05 for ~5% per-channel error.

2. **The SSM itself cannot be delta-compressed — and that's fine.** It is a
   per-channel recurrence `h_t = a·h_{t-1} + b·x_t`; every step depends on the
   last, so no step can be skipped. But it is already O(channels), not the
   bottleneck. Its role in delta inference is as the *slow-signal generator*:
   it is a per-channel low-pass filter, so its output is the most
   position-correlated signal in the network — which is exactly what makes the
   matvec downstream of it delta-friendly. The earlier RESULTS recommendation
   ("extend delta to the SSM") was half-right: extend it to the matvec that
   *consumes* the SSM, not the SSM recurrence itself.

3. **Honest negative: post-norm `h`, conv out, and attention out are NOT
   delta-friendly (~1.0–1.3×).** LayerNorm renormalizes every position so `h`
   shifts on nearly every channel; conv and attention outputs genuinely change
   position-to-position. Delta inference on the attention Wq/Wk/Wv projections
   (which consume `h`) buys almost nothing. Do not deploy it there.

4. **Later blocks are more delta-friendly than block 0** (45× 8-block average
   vs 33× at block 0, thr 0.10) — the SSM state warms up with depth, so the
   slow-signal property strengthens deeper in the network.

## Refined recommendation

Deploy delta inference on **the matvec layers that consume the SSM pathway
output**, not on the attention projections and not on the SSM recurrence
itself. On the real 944K model that is a measured **8–12× compute reduction**
at threshold 0.05 (≈5% per-channel error, bounded), rising to 33–45× at
threshold 0.10. Pair the threshold with the L11 state-norm monitor as the
drift watchdog.

## Quality cost — measured (2026-05-20, `quality_real.py`)

The earlier draft withheld the energy number because the *quality* cost of the
thresholding error was unmeasured. It is now measured. Delta inference on a
matvec consuming signal S is equivalent to feeding the exact matvec an
integrate-and-fire-thresholded S; so we threshold each block's SSM output,
run the rest of the real 944K model exactly, and measure cross-entropy.

| threshold | SSM-path speedup | Δ perplexity |
|---|---|---|
| 0.00 | 1.0× | +0.00% (exact — sanity check) |
| 0.02 | 4.1× | −0.46% (within noise) |
| **0.05** | **12.6×** | **+0.57%** |
| 0.10 | 49× | +5.6% |
| 0.20 | 320× | +11.5% (breaks) |

**The claim survives.** At threshold 0.05 the SSM pathway gives a real
**12.6× iteration-count reduction for +0.57% perplexity** on the trained
model — a shippable tradeoff. At 0.10 it is aggressive (49× / +5.6%); at 0.20
it breaks. This also refutes the worry that the SSM output is "near-constant
and contributes nothing": if it contributed nothing, staling it would be free
at every threshold — instead 0.20 costs +11.5%, so the SSM output genuinely
matters and the model genuinely tolerates *bounded* staleness.

## Remaining honest caveat

The quality number above is **prefill-position cross-entropy**, not
autoregressive generation. The SSM low-pass property should carry to
generation (it is a recurrent filter), but a generation-step measurement has
not been run. State the 12.6×/+0.57% number with that caveat attached.

## Reproduce (real-weights extension)

```bash
cd c_engine/experiments/delta_inference
python3 capture_real.py   # loads the real 944K ckpt, writes traces/
make real                 # C primitive cross-check on the real traces
```
