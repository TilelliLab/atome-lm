/*
 * firmware.c — Cortex-M3 test firmware for the Atome LLM C engine.
 *
 * Boots, loads a baked-in `.atome` model blob, runs predict_next on a
 * fixed token sequence, and prints all logits one-per-line via newlib
 * semihosting (which QEMU forwards to host stdout).
 *
 * Compile-time ATOME_* defines come from the Makefile.
 *
 * The model blob is provided by `model_data.h`, generated at build
 * time by `xxd -i model.atome > model_data.h`. The header defines
 *   unsigned char model_atome[];
 *   unsigned int  model_atome_len;
 * which match xxd's default symbols.
 */

#include "atome.h"
#include "model_data.h"

#include <stdio.h>
#include <stdlib.h>

/* Tokens the firmware will feed to predict_next. The Python harness
 * uses the same sequence so the comparison is deterministic. */
static const int kTokens[] = {10, 20, 5, 17, 0, 25};
static const int kNTokens = (int)(sizeof(kTokens) / sizeof(kTokens[0]));

static atome_model_t g_model;
static atome_state_t g_state;

/* Newlib's __libc_init_array / __libc_fini_array call these. We have no
   global C++ constructors and nothing to clean up, so they're empty. */
void _init(void) {}
void _fini(void) {}

int main(void) {
    if (atome_load(&g_model, model_atome, model_atome_len) != 0) {
        printf("ERROR: atome_load failed\n");
        return 1;
    }
    atome_init(&g_state);

    (void)atome_predict_next(&g_model, &g_state, kTokens, kNTokens);

    const float* logits = atome_get_logits(&g_state);
    for (int i = 0; i < ATOME_VOCAB_SIZE; ++i) {
        printf("%.9g\n", logits[i]);
    }
    return 0;
}
