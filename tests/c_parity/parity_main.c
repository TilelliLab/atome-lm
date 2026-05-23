/*
 * parity_main.c — minimal harness that loads an exported .atome binary,
 * runs the C engine's predict_next on a fixed token sequence, and
 * prints all logits to stdout (one float per line, decimal).
 *
 * Compile-time #defines below MUST match the Python AtomeLM config the
 * binary was exported with. The Python parity test sets these by
 * generating this file's compile flags before invoking gcc.
 *
 * Usage:
 *   gcc -O2 -std=c99 -lm -DATOME_D_MODEL=... ... -o parity \\
 *       parity_main.c <path-to-atome.c> -I<path-to-atome.h-dir>
 *   ./parity model.atome  "10 20 30 5"
 */

#ifndef ATOME_D_MODEL
#define ATOME_D_MODEL    16
#endif
#ifndef ATOME_MAX_SEQ
#define ATOME_MAX_SEQ    8
#endif
#ifndef ATOME_N_LAYERS
#define ATOME_N_LAYERS   2
#endif
#ifndef ATOME_N_PATHWAYS
#define ATOME_N_PATHWAYS 3
#endif
#ifndef ATOME_VOCAB_SIZE
#define ATOME_VOCAB_SIZE 32
#endif
#ifndef ATOME_D_HEAD
#define ATOME_D_HEAD     8
#endif
#ifndef ATOME_KERNEL_SIZE
#define ATOME_KERNEL_SIZE 5
#endif
#ifndef ATOME_TOP_K
#define ATOME_TOP_K      4
#endif

#include "atome.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static atome_model_t g_model;
static atome_state_t g_state;

static unsigned char g_blob[1 << 20]; /* up to 1 MB; tests stay tiny */

int main(int argc, char** argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: %s model.atome \"tok1 tok2 ...\"\n", argv[0]);
        return 2;
    }

    FILE* f = fopen(argv[1], "rb");
    if (!f) { fprintf(stderr, "cannot open %s\n", argv[1]); return 2; }
    size_t n = fread(g_blob, 1, sizeof(g_blob), f);
    fclose(f);

    if (atome_load(&g_model, g_blob, n) != 0) {
        fprintf(stderr, "atome_load failed\n");
        return 2;
    }

    int tokens[ATOME_MAX_SEQ];
    int n_tokens = 0;
    char* p = argv[2];
    while (*p && n_tokens < ATOME_MAX_SEQ) {
        char* end;
        long v = strtol(p, &end, 10);
        if (end == p) break;
        tokens[n_tokens++] = (int)v;
        p = end;
    }

    atome_init(&g_state);
    (void)atome_predict_next(&g_model, &g_state, tokens, n_tokens);

    const float* logits = atome_get_logits(&g_state);
    for (int i = 0; i < ATOME_VOCAB_SIZE; ++i) {
        printf("%.9g\n", logits[i]);
    }
    return 0;
}
