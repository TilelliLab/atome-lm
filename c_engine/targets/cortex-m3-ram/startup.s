/*
 * startup.s — minimal Cortex-M3 vector table + reset handler for
 * QEMU MPS2-AN385.
 *
 * Sets the initial stack pointer (top of RAM, defined by the linker
 * script) and entry point (Reset_Handler), then defaults every other
 * exception/IRQ to Default_Handler (an infinite loop — this is a test
 * firmware, not a production image).
 */

    .syntax unified
    .cpu cortex-m3
    .thumb

    .section .vectors,"a",%progbits
    .align 2
    .global g_pfnVectors

g_pfnVectors:
    .word _estack                  /* 0  Initial Stack Pointer */
    .word Reset_Handler            /* 1  Reset */
    .word Default_Handler          /* 2  NMI */
    .word Default_Handler          /* 3  HardFault */
    .word Default_Handler          /* 4  MemManage */
    .word Default_Handler          /* 5  BusFault */
    .word Default_Handler          /* 6  UsageFault */
    .word 0                        /* 7-10 reserved */
    .word 0
    .word 0
    .word 0
    .word Default_Handler          /* 11 SVCall */
    .word Default_Handler          /* 12 DebugMon */
    .word 0                        /* 13 reserved */
    .word Default_Handler          /* 14 PendSV */
    .word Default_Handler          /* 15 SysTick */
    /* External IRQs 0..47 — all default for test firmware */
    .rept 48
    .word Default_Handler
    .endr

    .section .text
    .thumb_func
    .global Reset_Handler
Reset_Handler:
    /* Copy .data from flash to RAM */
    ldr  r0, =_sidata
    ldr  r1, =_sdata
    ldr  r2, =_edata
1:  cmp  r1, r2
    ittt lt
    ldrlt r3, [r0], #4
    strlt r3, [r1], #4
    blt  1b

    /* Zero .bss */
    ldr  r0, =_sbss
    ldr  r1, =_ebss
    movs r2, #0
2:  cmp  r0, r1
    itt  lt
    strlt r2, [r0]
    addlt r0, r0, #4
    blt  2b

    /* Initialize newlib semihosting (provides stdin/stdout/stderr backed
       by host-side semihosting), then run C++ static constructors / init
       array, then main(), then exit() with main's return value. */
    bl   initialise_monitor_handles
    bl   __libc_init_array
    bl   main
    bl   exit

    /* Should not reach here. */
3:  b    3b

    .thumb_func
    .global Default_Handler
Default_Handler:
    b    Default_Handler

    .end
