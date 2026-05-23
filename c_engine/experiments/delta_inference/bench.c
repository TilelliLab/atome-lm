/*
 * bench.c — delta-inference energy experiment for Atome LM
 *
 * Measures full-recompute vs temporal-delta ternary matvec across three
 * input regimes, sweeping the firing threshold. Reports:
 *   - iters : inner-loop trips (deterministic, exact, the cycles/energy proxy)
 *   - macs  : add/sub actually performed
 *   - err   : max abs deviation of delta output vs an exact full recompute
 *   - cycles: wall-clock (host) or DWT CYCCNT (QEMU cortex-m3) — confirms iters
 *
 * `iters` is identical on host and target by construction (same C, same data),
 * so it is the headline number; cycles only confirm it tracks real hardware.
 *
 * Build:  make            (host)
 *         make qemu       (cortex-m3 firmware, run under qemu-system-arm)
 */
#include "delta_matvec.h"
#include <stdio.h>
#include <math.h>

#define D_MODEL 256          /* mirrors the 944K Atome model's d_model */
#define N_STEPS 256          /* tokens / frames in the stream */

/* ---- deterministic LCG so results are bit-reproducible ---- */
static uint32_t g_rng = 0x1234567u;
static uint32_t lcg(void) { g_rng = g_rng * 1664525u + 1013904223u; return g_rng; }
static float frand(void) { return (float)(lcg() >> 8) / (float)(1u << 24); } /* [0,1) */
static float frand_sym(void) { return 2.0f * frand() - 1.0f; }              /* [-1,1) */

/* ---- cycle counter ---- */
#if defined(DM_QEMU)
/* ARMv7-M DWT cycle counter */
#define DWT_CYCCNT (*(volatile uint32_t*)0xE0001004u)
#define DWT_CTRL   (*(volatile uint32_t*)0xE0001000u)
#define DEMCR      (*(volatile uint32_t*)0xE000EDFCu)
static void cyc_init(void) { DEMCR |= (1u << 24); DWT_CYCCNT = 0; DWT_CTRL |= 1u; }
static uint32_t cyc_now(void) { return DWT_CYCCNT; }
#else
#include <time.h>
static void cyc_init(void) {}
static uint32_t cyc_now(void) { return (uint32_t)clock(); }
#endif

/* ---- packed ternary weight matrix (rows x cols), ~1/3 zeros ---- */
static uint8_t g_packed[(D_MODEL * D_MODEL + 3) / 4];
static dm_ternary_t make_weights(void) {
    int n = D_MODEL * D_MODEL;
    for (int k = 0; k < n; ++k) {
        uint32_t r = lcg() % 3u;            /* 0,1,2 -> 0,+1,-1 */
        uint8_t code = (r == 0u) ? 0u : (r == 1u ? 1u : 3u);
        int b = k >> 2, s = (k & 3) << 1;
        g_packed[b] = (uint8_t)((g_packed[b] & ~(3u << s)) | (code << s));
    }
    dm_ternary_t W; W.packed = g_packed; W.scale = 0.05f;
    W.rows = D_MODEL; W.cols = D_MODEL;
    return W;
}

/* ---- input stream generators ---- */
/* A: sensor stream — every channel jitters by tiny noise, a few carry real
 *    signal. This is the thermostat/accelerometer/audio-frame regime. */
static void step_sensor(float* x) {
    for (int i = 0; i < D_MODEL; ++i) x[i] += 0.002f * frand_sym();   /* noise floor */
    for (int s = 0; s < 5; ++s) x[lcg() % D_MODEL] += 0.30f * frand_sym(); /* signal */
}
/* B: token embeddings — each step is a fresh, uncorrelated row. The
 *    LM-generation regime: there is no "static wall" to skip. */
static void step_token(float* x) {
    for (int i = 0; i < D_MODEL; ++i) x[i] = frand_sym();
}
/* C: hidden-state proxy — ~30% of channels move meaningfully each step.
 *    Stands in for a mid-network residual evolving across positions. */
static void step_hidden(float* x) {
    for (int i = 0; i < D_MODEL; ++i)
        if ((lcg() & 1023u) < 307u) x[i] += 0.20f * frand_sym();
}

typedef void (*stepfn)(float*);

static void run_scenario(const char* name, dm_ternary_t W, stepfn step,
                         float threshold) {
    float x[D_MODEL], x_prev[D_MODEL], out_delta[D_MODEL], out_ref[D_MODEL];

    for (int i = 0; i < D_MODEL; ++i) x[i] = frand_sym();
    for (int i = 0; i < D_MODEL; ++i) x_prev[i] = x[i];

    /* seed: one full recompute for both the delta path and the reference */
    dm_matvec_full(&W, x, out_delta);
    dm_matvec_full(&W, x, out_ref);

    long it_full = 0, mc_full = 0, it_delta = 0, mc_delta = 0;
    float max_err = 0.0f;
    uint32_t cyc_full = 0, cyc_delta = 0;  /* per-path, measured separately */

    for (int t = 1; t < N_STEPS; ++t) {
        step(x);
        /* reference: what a full recompute would produce this step */
        uint32_t a = cyc_now();
        dm_cost_t cf = dm_matvec_full(&W, x, out_ref);
        cyc_full += cyc_now() - a;
        it_full += cf.iters; mc_full += cf.macs;
        /* delta update in place — timed on its own so the cycle number is
         * the real per-path cost, not confounded by the reference recompute */
        uint32_t b = cyc_now();
        dm_cost_t cd = dm_matvec_delta(&W, x, x_prev, out_delta, threshold);
        cyc_delta += cyc_now() - b;
        it_delta += cd.iters; mc_delta += cd.macs;
        for (int j = 0; j < D_MODEL; ++j) {
            float e = fabsf(out_delta[j] - out_ref[j]);
            if (e > max_err) max_err = e;
        }
    }

    double speedup = (it_delta > 0) ? (double)it_full / (double)it_delta
                                    : (double)it_full;
    double cyc_sp = (cyc_delta > 0) ? (double)cyc_full / (double)cyc_delta
                                    : (double)cyc_full;
    printf("  %-16s thr=%.4f | iters f=%9ld d=%9ld sp=%6.2fx | "
           "cyc f=%8u d=%8u sp=%6.2fx | max_err=%.5f\n",
           name, (double)threshold, it_full, it_delta, speedup,
           (unsigned)cyc_full, (unsigned)cyc_delta, cyc_sp, (double)max_err);
}

int main(void) {
    cyc_init();
    dm_ternary_t W = make_weights();

    printf("=== Atome LM delta-inference experiment ===\n");
    printf("d_model=%d  steps=%d  ternary matrix %dx%d (~1/3 zeros)\n",
           D_MODEL, N_STEPS, D_MODEL, D_MODEL);
    printf("iters = inner-loop trips = energy proxy; full path always recomputes.\n\n");

    printf("[A] SENSOR STREAM  (correlated input — thermostat/audio/accel)\n");
    float thrs[] = {0.0f, 0.005f, 0.02f, 0.05f};
    for (int k = 0; k < 4; ++k) { g_rng = 0x1234567u; make_weights();
        run_scenario("sensor", W, step_sensor, thrs[k]); }

    printf("\n[B] TOKEN EMBEDDINGS  (uncorrelated — LM generation)\n");
    for (int k = 0; k < 2; ++k) { g_rng = 0x1234567u; make_weights();
        run_scenario("token", W, step_token, thrs[k]); }

    printf("\n[C] HIDDEN-STATE PROXY  (~30%% channels move/step)\n");
    for (int k = 0; k < 3; ++k) { g_rng = 0x1234567u; make_weights();
        run_scenario("hidden", W, step_hidden, thrs[k]); }

    printf("\nReading: speedup>1 means delta wins. err is bounded by the\n");
    printf("threshold by construction (selective x_prev update = integrate-\n");
    printf("and-fire). Token regime shows ~1x — honest: no free lunch there.\n");
    return 0;
}
