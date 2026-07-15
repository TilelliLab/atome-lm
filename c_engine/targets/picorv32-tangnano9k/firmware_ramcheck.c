/*
 * firmware_ramcheck.c — stack high-water mark measurement for the
 * PicoRV32/Tang Nano 9K target, same technique as
 * c_engine/targets/cortex-m3-ram/firmware.c: paint a window below the
 * current SP with a known pattern, run the exact same load/init/predict
 * workload as firmware.c, then walk down from the paint's high edge to
 * find the lowest word the stack actually touched.
 *
 * RAM budget (see linker.ld): 16 KB total, 0x0000..0x4000. _estack sits
 * at the top (0x4000); PicoRV32 sets sp = STACKADDR on reset, mirrored by
 * start.s. This paints the region between _ebss (end of .bss/globals,
 * i.e. atome_state_t + atome_model_t + token buffer) and the stack's
 * current position, then reports how far the stack actually descended
 * into it during a real 6-token-prompt + 8-token-generation run.
 */
#include "atome.h"
#include "model_data.h"
#include "uart.h"

extern uint32_t _ebss;
extern uint32_t _sbss;
extern uint32_t _estack;

#define PAINT_PATTERN 0xA5A5A5A5u

static atome_model_t g_model;
static atome_state_t g_state;
static int g_tokens[ATOME_MAX_SEQ];

int main(void) {
    uart_init();
    uart_print("atome-picorv32 ramcheck\n");

    /* Paint everything between end-of-bss and (current SP - 64 words
     * safety margin, so we don't paint over our own live activation
     * record). Whatever the stack doesn't touch during the run below
     * still reads back as the paint pattern afterward. */
    uint32_t sp_at_paint;
    __asm__ volatile ("mv %0, sp" : "=r"(sp_at_paint));
    uint32_t *paint_hi = (uint32_t *)((sp_at_paint - 256u) & ~3u);
    uint32_t *paint_lo = (uint32_t *)&_ebss;
    for (uint32_t *p = paint_lo; p < paint_hi; ++p) *p = PAINT_PATTERN;

    if (atome_load(&g_model, model_atome, model_atome_len) != 0) {
        uart_print("ERROR: atome_load failed\n");
        return 1;
    }
    atome_init(&g_state);

    static const int kPrompt[6] = {10, 20, 5, 17, 0, 25};
    int n = 6;
    for (int i = 0; i < n; ++i) g_tokens[i] = kPrompt[i];
    for (int s = 0; s < 8 && n < ATOME_MAX_SEQ; ++s) {
        int next = atome_predict_next(&g_model, &g_state, g_tokens, n);
        g_tokens[n++] = next;
    }

    /* Walk down from paint_hi: the first word (from the top) that no
     * longer equals the pattern marks where the stack's lowest excursion
     * stopped. Everything below that, down to paint_lo, was never
     * touched by the stack during this run. */
    uint32_t *p = paint_hi;
    while (p > paint_lo && *(p - 1) != PAINT_PATTERN) --p;
    uint32_t low_water_addr = (uint32_t)p;
    uint32_t stack_used = (uint32_t)&_estack - low_water_addr;
    uint32_t bss_size = (uint32_t)&_ebss - (uint32_t)&_sbss;
    uint32_t ram_total = (uint32_t)&_estack; /* RAM starts at 0x0 */

    uart_print("bss=0x");
    uart_print_hex(bss_size, 8);
    uart_print(" stack_used=0x");
    uart_print_hex(stack_used, 8);
    uart_print(" total=0x");
    uart_print_hex(bss_size + stack_used, 8);
    uart_print(" ram_budget=0x");
    uart_print_hex(ram_total, 8);
    uart_print("\ndone\n");
    return 0;
}
