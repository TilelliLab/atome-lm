/*
 * main.c — Atome LLM generation demo for the Raspberry Pi Pico (RP2040).
 *
 * Boots the Pico SDK, brings up USB CDC + UART stdio, loads the
 * baked-in `.atome` model, runs DEMO_NEW_TOKENS rounds of
 * `atome_predict_next`, and streams each generated token over stdio
 * with the elapsed microseconds.
 *
 * Build with the Pico SDK (see CMakeLists.txt). Flash the resulting
 * .uf2 onto an RPI-RP2 device and open a serial terminal at 115200.
 */

#include "pico/stdlib.h"
#include "pico/time.h"
#include "atome.h"
#include "model_data.h"

#include <stdio.h>
#include <stdint.h>


static atome_model_t g_model;
static atome_state_t g_state;
static int g_tokens[ATOME_MAX_SEQ];

#ifndef DEMO_PROMPT_LEN
#define DEMO_PROMPT_LEN 4
#endif
#ifndef DEMO_NEW_TOKENS
#define DEMO_NEW_TOKENS 16
#endif


int main(void) {
    stdio_init_all();
    /* Give USB enumeration a moment before we start writing. */
    sleep_ms(2500);

    if (atome_load(&g_model, model_atome, model_atome_len) != 0) {
        printf("ERROR: atome_load failed\n");
        return 1;
    }
    atome_init(&g_state);

    static const int kPrompt[DEMO_PROMPT_LEN] = {10, 20, 5, 17};
    for (int i = 0; i < DEMO_PROMPT_LEN; ++i) g_tokens[i] = kPrompt[i];
    int n_tokens = DEMO_PROMPT_LEN;

    printf("ATOME-PICO-START prompt_len=%d new_tokens=%d max_seq=%d\n",
           DEMO_PROMPT_LEN, DEMO_NEW_TOKENS, ATOME_MAX_SEQ);

    absolute_time_t t0 = get_absolute_time();
    for (int step = 0; step < DEMO_NEW_TOKENS; ++step) {
        if (n_tokens >= ATOME_MAX_SEQ) {
            printf("WARN: hit ATOME_MAX_SEQ; stopping early\n");
            break;
        }
        absolute_time_t t_step0 = get_absolute_time();
        int next = atome_predict_next(&g_model, &g_state, g_tokens, n_tokens);
        absolute_time_t t_step1 = get_absolute_time();
        int64_t step_us = absolute_time_diff_us(t_step0, t_step1);

        g_tokens[n_tokens++] = next;
        printf("TOK %d %d us=%lld\n", step, next, step_us);
    }
    int64_t total_us = absolute_time_diff_us(t0, get_absolute_time());
    printf("ATOME-PICO-END total_us=%lld tokens=%d\n",
           total_us, DEMO_NEW_TOKENS);

    /* Idle forever so the serial output stays attached. */
    while (1) sleep_ms(1000);
    return 0;
}
