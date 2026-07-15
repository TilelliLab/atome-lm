#ifndef ATOME_PICORV32_UART_H
#define ATOME_PICORV32_UART_H

void uart_init(void);
void uart_putchar(char c);
void uart_print(const char *p);
void uart_print_hex(unsigned int val, int digits);

#endif
