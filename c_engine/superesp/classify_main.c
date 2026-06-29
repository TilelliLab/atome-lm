/*
 * classify_main.c — SuperESP classifier parity harness.
 *
 * Loads an exported ATOMECL01 blob via atome_classifier_load, runs
 * atome_classify on a fixed byte-token sequence, and prints the class
 * logits to stdout (one float per line). Mirrors c_parity/parity_main.c
 * but for the classification head.
 *
 * Compile-time #defines MUST match the SuperESP shared config the blob
 * was exported with (superesp/framework/config.py: SHARED).
 *
 * Usage:
 *   gcc -O2 -std=c99 -DATOME_D_MODEL=... ... -I<atome.h dir> \
 *       classify_main.c <atome.c> -lm -o classify
 *   ./classify head.atomecl "12 200 5 17"
 */

#ifndef ATOME_D_MODEL
#define ATOME_D_MODEL    32
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
#define ATOME_VOCAB_SIZE 256
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
#ifndef ATOME_MAX_CLASSES
#define ATOME_MAX_CLASSES 16
#endif

#include "atome.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static atome_classifier_t g_clf;
static atome_state_t g_state;
static unsigned char g_blob[1 << 20];

int main(int argc, char** argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: %s head.atomecl \"tok1 tok2 ...\"\n", argv[0]);
        return 2;
    }
    FILE* f = fopen(argv[1], "rb");
    if (!f) { fprintf(stderr, "cannot open %s\n", argv[1]); return 2; }
    size_t n = fread(g_blob, 1, sizeof(g_blob), f);
    fclose(f);

    int rc = atome_classifier_load(&g_clf, g_blob, n);
    if (rc != 0) { fprintf(stderr, "atome_classifier_load failed rc=%d\n", rc); return 2; }

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
    float class_logits[ATOME_MAX_CLASSES];
    int cls = atome_classify(&g_clf, &g_state, tokens, n_tokens, class_logits);

    /* line 0: predicted class index; then one logit per line */
    printf("%d\n", cls);
    for (int i = 0; i < g_clf.n_classes; ++i) printf("%.9g\n", class_logits[i]);
    return 0;
}
