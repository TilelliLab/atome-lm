/*
 * bench_real.c — cross-check the C delta-matvec primitive on REAL traces.
 *
 * Loads activation streams captured from the real 944K Atome model
 * (capture_real.py) plus the model's real ternarized attention Wv, then runs
 * dm_matvec_full vs dm_matvec_delta over the real sequence. Confirms the C
 * primitive reproduces the speedup capture_real.py predicted in numpy.
 *
 * Host-only (reads files). Build: make real
 */
#include "delta_matvec.h"
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

#define D_MODEL 256

static float* load_f32(const char* path, int* n_rows) {
    FILE* f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "missing %s — run capture_real.py first\n", path); exit(1); }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    *n_rows = (int)(sz / (D_MODEL * (long)sizeof(float)));
    float* buf = malloc((size_t)sz);
    if (fread(buf, 1, (size_t)sz, f) != (size_t)sz) { fprintf(stderr, "short read\n"); exit(1); }
    fclose(f);
    return buf;
}

static uint8_t* load_wv(const char* path, dm_ternary_t* W) {
    FILE* f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "missing %s\n", path); exit(1); }
    int32_t rows, cols; float scale;
    if (fread(&rows, 4, 1, f) != 1 || fread(&cols, 4, 1, f) != 1 ||
        fread(&scale, 4, 1, f) != 1) { fprintf(stderr, "bad header\n"); exit(1); }
    long packed_len = ((long)rows * cols + 3) / 4;
    uint8_t* packed = malloc((size_t)packed_len);
    if (fread(packed, 1, (size_t)packed_len, f) != (size_t)packed_len) {
        fprintf(stderr, "short weight read\n"); exit(1);
    }
    fclose(f);
    W->packed = packed; W->scale = scale; W->rows = rows; W->cols = cols;
    return packed;
}

static void run(const char* name, const dm_ternary_t* W,
                const float* stream, int L, float threshold) {
    float x_prev[D_MODEL], out_delta[D_MODEL], out_ref[D_MODEL];
    for (int i = 0; i < D_MODEL; ++i) x_prev[i] = stream[i];
    dm_matvec_full(W, stream, out_delta);

    long it_full = 0, it_delta = 0;
    float max_err = 0.0f;
    for (int t = 1; t < L; ++t) {
        const float* x = stream + (long)t * D_MODEL;
        dm_cost_t cf = dm_matvec_full(W, x, out_ref);
        dm_cost_t cd = dm_matvec_delta(W, x, x_prev, out_delta, threshold);
        it_full += cf.iters; it_delta += cd.iters;
        for (int j = 0; j < W->rows; ++j) {
            float e = fabsf(out_delta[j] - out_ref[j]);
            if (e > max_err) max_err = e;
        }
    }
    double sp = (it_delta > 0) ? (double)it_full / (double)it_delta : 0.0;
    printf("  %-22s thr=%.2f | speedup=%7.2fx | max_err=%.5f\n",
           name, (double)threshold, sp, (double)max_err);
}

int main(void) {
    dm_ternary_t W;
    uint8_t* packed = load_wv("traces/wv_block0.tern", &W);
    int Lh, Ls;
    float* h   = load_f32("traces/h_block0.f32", &Lh);
    float* ssm = load_f32("traces/ssm_block0.f32", &Ls);

    printf("=== C delta-matvec on REAL 944K Atome traces ===\n");
    printf("real attention Wv: %dx%d, scale=%.5f | sequence: %d positions\n\n",
           W.rows, W.cols, (double)W.scale, Lh);
    printf("Each row: a real Wv matvec consuming a real captured signal.\n\n");

    float thrs[] = {0.0f, 0.02f, 0.05f, 0.10f};
    printf("[post-norm input h] — feeds attention Wq/Wk/Wv\n");
    for (int k = 0; k < 4; ++k) run("Wv @ h", &W, h, Lh, thrs[k]);
    printf("\n[SSM pathway output] — the slow signal\n");
    for (int k = 0; k < 4; ++k) run("Wv @ ssm_out", &W, ssm, Ls, thrs[k]);

    printf("\nCross-check: these speedups must match capture_real.py's numpy\n");
    printf("prediction (speedup_h / speedup_ssm in traces/manifest.json).\n");

    free(packed); free(h); free(ssm);
    return 0;
}
