/*
 * delta_matvec.h — temporal-delta ternary matvec experiment
 *
 * The brain/eye don't re-process a static scene. This experiment tests the
 * same idea for Atome's hot path: instead of recomputing W @ x every step,
 * propagate only the CHANGE since the previous input:
 *
 *     out_new = out_old + W @ (x_new - x_prev)
 *
 * This is algebraically exact when threshold = 0. With threshold > 0, small
 * per-channel deltas are skipped — and because x_prev is updated ONLY for
 * propagated channels, each channel's pending error is bounded by `threshold`
 * at all times (it accumulates silently until it crosses the bar, then fires
 * once and resets). That is literally an integrate-and-fire neuron: the
 * threshold IS the firing threshold.
 *
 * Win is real for correlated input streams (sensors, audio frames, camera
 * pixels). It is NOT a free lunch for token-LM generation, where consecutive
 * byte embeddings are uncorrelated — the benchmark measures both honestly.
 *
 * Standalone (mirrors atome_ternary_t) so the experiment builds without the
 * full engine. Zero heap, C99.
 */
#ifndef DELTA_MATVEC_H
#define DELTA_MATVEC_H

#include <stdint.h>
#include <stddef.h>

typedef struct {
    const uint8_t* packed;  /* 4 trits/byte, 2 bits each: 00=0 01=+1 11=-1 */
    float scale;
    int rows;
    int cols;
} dm_ternary_t;

/* energy proxy: every inner-loop trip unpacks a trit + branches (~1 cycle
 * on an MCU whether or not it produces a MAC); `iters` is the honest
 * cycles-per-matvec proxy, `macs` is the subset that did add/sub. */
typedef struct {
    long iters;
    long macs;
} dm_cost_t;

static inline int8_t dm_trit(const uint8_t* p, int idx) {
    int b = idx >> 2;
    int s = (idx & 3) << 1;
    uint8_t v = (uint8_t)((p[b] >> s) & 3u);
    if (v == 1u) return 1;
    if (v == 3u) return -1;
    return 0;
}

/* Full recompute: out = scale * (W @ x). The existing Atome path. */
dm_cost_t dm_matvec_full(const dm_ternary_t* W, const float* x, float* out);

/*
 * Delta update. `out` holds the PREVIOUS output (pre-seeded by a full call);
 * updated in place. `x_prev` is the previous input and is updated in place —
 * but ONLY for channels actually propagated, which is what bounds the error.
 * Channels whose delta is <= threshold are skipped this step.
 */
dm_cost_t dm_matvec_delta(const dm_ternary_t* W, const float* x,
                          float* x_prev, float* out, float threshold);

#endif /* DELTA_MATVEC_H */
