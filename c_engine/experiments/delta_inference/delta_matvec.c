/*
 * delta_matvec.c — see delta_matvec.h
 */
#include "delta_matvec.h"
#include <math.h>

dm_cost_t dm_matvec_full(const dm_ternary_t* W, const float* x, float* out) {
    dm_cost_t c = {0, 0};
    for (int j = 0; j < W->rows; ++j) {
        float acc = 0.0f;
        const int base = j * W->cols;
        for (int i = 0; i < W->cols; ++i) {
            c.iters++;
            int8_t w = dm_trit(W->packed, base + i);
            if (w == 1)        { acc += x[i]; c.macs++; }
            else if (w == -1)  { acc -= x[i]; c.macs++; }
            /* w == 0: skip — ternary sparsity, ~1/3 of weights */
        }
        out[j] = acc * W->scale;
    }
    return c;
}

dm_cost_t dm_matvec_delta(const dm_ternary_t* W, const float* x,
                          float* x_prev, float* out, float threshold) {
    dm_cost_t c = {0, 0};
    for (int i = 0; i < W->cols; ++i) {
        float d = x[i] - x_prev[i];
        if (fabsf(d) <= threshold) continue;  /* below firing threshold */
        x_prev[i] = x[i];  /* selective update: keeps per-channel error <= threshold */
        /* Precompute the scaled delta ONCE per changed input so the inner
         * loop stays pure add/sub — preserves the zero-multiply-hot-path
         * property the architecture sells. */
        const float ds = d * W->scale;
        for (int j = 0; j < W->rows; ++j) {
            c.iters++;
            int8_t w = dm_trit(W->packed, j * W->cols + i);
            if (w == 1)        { out[j] += ds; c.macs++; }
            else if (w == -1)  { out[j] -= ds; c.macs++; }
        }
    }
    return c;
}
