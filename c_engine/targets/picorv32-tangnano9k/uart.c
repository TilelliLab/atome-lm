/*
 * uart.c — adapted from FreeRTOS-TetriSaraj/2.sw/uart.c. Renamed
 * putchar/print/print_hex -> uart_* so they don't collide with libgcc's
 * expectations or a future libc pull-in.
 *
 * FreeRTOS-TetriSaraj/2.sw/uart.c (which this was adapted from) never
 * writes the clock-divider register, relying on whatever the caller
 * already set up. simpleuart.v resets cfg_divider to 562, which at the
 * 27 MHz clk_27 top_uart_hello.v feeds straight into the core (no PLL)
 * is ~48 KBd, not 115200 -- garbled output on a real terminal. 234 is
 * the divider FreeRTOS-TetriSaraj's own milestone doc
 * (0.doc/milestone_0_1_uart_hello.md) measured as correct for 27 MHz /
 * 115200 baud; uart_init() must run before any uart_print call.
 */
#include "uart.h"
#include <stdint.h>

#define reg_uart_clkdiv (*(volatile uint32_t*)0x02000004)
#define reg_uart_data (*(volatile uint32_t*)0x02000008)

void uart_init(void) {
    reg_uart_clkdiv = 234;
}

void uart_putchar(char c) {
    if (c == '\n') uart_putchar('\r');
    reg_uart_data = c;
}

void uart_print(const char *p) {
    while (*p) uart_putchar(*(p++));
}

void uart_print_hex(unsigned int val, int digits) {
    for (int i = (4 * digits) - 4; i >= 0; i -= 4)
        reg_uart_data = "0123456789ABCDEF"[(val >> i) % 16];
}
