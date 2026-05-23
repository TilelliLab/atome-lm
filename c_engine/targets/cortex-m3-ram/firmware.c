/*
 * firmware.c — Cortex-M3 RAM-watermark firmware for the Atome engine.
 *
 * Boots, paints the entire .heap+stack region with a known pattern,
 * runs one full forward + a short generation, then walks the painted
 * region to find the highest stack-pointer ever used. Reports:
 *
 *   ATOME-RAM bss=X heap_high=Y stack_high=Z total=BSS+STACK
 *
 * The Python harness combines these with the engine's static .text size
 * to confirm "fits in 16 KB SRAM" claims for Cortex-M0+ class targets.
 *
 * Note on QEMU vs real silicon: the linker script uses a 4 MB RAM
 * region for QEMU compatibility. We measure the high-water on the
 * *actual* used part, not on the whole region, so the number is honest
 * even though the linker-set limit is not.
 */

#include "atome.h"
#include "model_data.h"

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

extern uint32_t _ebss;       /* end of .bss, start of heap */
extern uint32_t _estack;     /* top of stack (linker-defined) */
extern uint32_t _sbss;       /* start of .bss (linker-defined) */

#define PAINT_PATTERN 0xA5A5A5A5u
#define PAINT_WORDS   8192u   /* 32 KB paint window — way more than we use */

static atome_model_t g_model;
static atome_state_t g_state;
static int g_tokens[ATOME_MAX_SEQ];

void _init(void) {}
void _fini(void) {}

/* Returns highest-address word above `from` whose value still equals
 * PAINT_PATTERN. We only paint a window of size PAINT_WORDS so that the
 * walk can't run forever on large RAM regions. */
static uint32_t* find_high_water(uint32_t* from, uint32_t* limit) {
    uint32_t* p = from;
    while (p < limit && *p == PAINT_PATTERN) ++p;
    return p;
}

int main(void) {
    /* Step 1. The stack grows DOWN from _estack. Paint a window of size
     * PAINT_WORDS just below the current SP: that is the band the stack
     * is about to walk into. We paint below SP-32 to avoid overwriting
     * the live activation record we are sitting in.
     *
     * paint_hi is the high (toward _estack) edge of the paint;
     * paint_lo is the low edge. After main() does its work, the stack
     * will have descended from paint_hi toward paint_lo by some amount;
     * the lowest word still equal to PAINT_PATTERN is the high-water. */
    uint32_t sp_at_paint;
    __asm volatile ("mov %0, sp" : "=r"(sp_at_paint));
    uint32_t* paint_hi = (uint32_t*)((sp_at_paint - 64) & ~3u);
    uint32_t* paint_lo = paint_hi - PAINT_WORDS;
    if ((uint32_t)paint_lo < (uint32_t)&_ebss) paint_lo = (uint32_t*)&_ebss;
    for (uint32_t* p = paint_lo; p < paint_hi; ++p) *p = PAINT_PATTERN;

    /* Step 2. Run the engine: full prompt forward + a few generation
     * steps. This is the path whose stack high-water we want to measure. */
    if (atome_load(&g_model, model_atome, model_atome_len) != 0) {
        printf("ERROR: atome_load failed\n");
        return 1;
    }
    atome_init(&g_state);

    static const int kPrompt[6] = {10, 20, 5, 17, 0, 25};
    for (int i = 0; i < 6; ++i) g_tokens[i] = kPrompt[i];
    int n = 6;
    for (int s = 0; s < 4; ++s) {
        if (n >= ATOME_MAX_SEQ) break;
        int next = atome_predict_next(&g_model, &g_state, g_tokens, n);
        g_tokens[n++] = next;
    }

    /* Step 3. Walk DOWN from paint_hi looking for the first word the
     * stack overwrote. Stack used = _estack - that_word. */
    uint32_t* p = paint_hi;
    while (p > paint_lo && *(p - 1) != PAINT_PATTERN) --p;
    uint32_t low_water_addr = (uint32_t)p;
    uint32_t stack_used = (uint32_t)&_estack - low_water_addr;

    uint32_t bss_size = (uint32_t)&_ebss - (uint32_t)&_sbss;

    printf("ATOME-RAM bss=%u stack_used=%u total_bss_plus_stack=%u\n",
           (unsigned)bss_size, (unsigned)stack_used,
           (unsigned)(bss_size + stack_used));
    return 0;
}
