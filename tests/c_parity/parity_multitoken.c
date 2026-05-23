/*
 * parity_multitoken.c — multi-token parity harness.
 *
 * Loads an exported .atome binary, runs atome_generate on a prompt to
 * produce N continuation tokens, prints them one per line. The Python
 * side does the equivalent model.generate(prompt, n_new_tokens=N) and
 * compares.
 *
 * The single-forward harness (parity_main.c) only checks the LAST
 * position of one predict_next call. This harness exposes any
 * divergence in the multi-step inference loop — particularly any bug
 * where the SSM hidden state's persistence-across-calls semantics
 * differ between Python and C.
 *
 * Usage:
 *   ./parity_multi model.atome "10 20 30 5" 16
 */

#ifndef ATOME_D_MODEL
#define ATOME_D_MODEL    16
#endif
#ifndef ATOME_MAX_SEQ
#define ATOME_MAX_SEQ    32
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
static unsigned char g_blob[1 << 20];

int main(int argc, char** argv) {
    if (argc < 4) {
        fprintf(stderr, "usage: %s model.atome \"tok1 tok2 ...\" n_generate\n", argv[0]);
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

    int prompt[ATOME_MAX_SEQ];
    int prompt_len = 0;
    char* p = argv[2];
    while (*p && prompt_len < ATOME_MAX_SEQ) {
        char* end;
        long v = strtol(p, &end, 10);
        if (end == p) break;
        prompt[prompt_len++] = (int)v;
        p = end;
    }

    int n_generate = atoi(argv[3]);
    if (n_generate < 1 || n_generate > ATOME_MAX_SEQ - prompt_len) {
        fprintf(stderr, "bad n_generate %d (max %d)\n",
                n_generate, ATOME_MAX_SEQ - prompt_len);
        return 2;
    }

    atome_init(&g_state);

    int out[ATOME_MAX_SEQ];
    int got = atome_generate(&g_model, &g_state, prompt, prompt_len,
                              out, n_generate);

    for (int i = 0; i < got; ++i) {
        printf("%d\n", out[i]);
    }
    return 0;
}
