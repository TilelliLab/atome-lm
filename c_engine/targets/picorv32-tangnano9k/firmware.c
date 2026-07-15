/*
 * firmware.c — boots the Atome engine on bare-metal PicoRV32, runs a
 * short prompt + generation loop, and prints the predicted token ids
 * over UART. Modeled on c_engine/targets/cortex-m3-ram/firmware.c's
 * load -> init -> predict loop, with semihosting printf swapped for
 * uart_print/uart_print_hex.
 */
#include "atome.h"
#include "model_data.h"
#include "uart.h"

static atome_model_t g_model;
static atome_state_t g_state;
static int g_tokens[ATOME_MAX_SEQ];

int main(void) {
    uart_init();
    uart_print("atome-picorv32 boot\n");

    if (atome_load(&g_model, model_atome, model_atome_len) != 0) {
        uart_print("ERROR: atome_load failed\n");
        return 1;
    }
    atome_init(&g_state);

    static const int kPrompt[6] = {10, 20, 5, 17, 0, 25};
    int n = 6;
    for (int i = 0; i < n; ++i) g_tokens[i] = kPrompt[i];

    uart_print("prompt:");
    for (int i = 0; i < n; ++i) {
        uart_putchar(' ');
        uart_print_hex((unsigned)g_tokens[i], 2);
    }
    uart_print("\ngenerated:");

    for (int s = 0; s < 8 && n < ATOME_MAX_SEQ; ++s) {
        int next = atome_predict_next(&g_model, &g_state, g_tokens, n);
        g_tokens[n++] = next;
        uart_putchar(' ');
        uart_print_hex((unsigned)next, 2);
    }
    uart_print("\ndone\n");
    return 0;
}
