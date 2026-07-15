/*
 * start.s — minimal PicoRV32 reset entry, adapted from
 * FreeRTOS-TetriSaraj/2.sw/start.s (IRQ/benchmark scaffolding dropped;
 * this firmware is a single-shot bare-metal inference loop, no timer
 * IRQs).
 *
 * PicoRV32 hardware-initializes sp = STACKADDR on reset (picorv32.v,
 * "if (~STACKADDR) reg_out <= STACKADDR"; picosoc_noflash.v sets
 * STACKADDR = 4*MEM_WORDS = 0x4000, matching _estack below exactly).
 * The explicit `la sp, _estack` here is redundant on real hardware but
 * kept so this boots the same way under a plain RV32 simulator that
 * doesn't model that reset behavior.
 */
.section .text.start, "ax"
.global start
start:
    la sp, _estack

    la a0, _sidata
    la a1, _sdata
    la a2, _edata
    bge a1, a2, end_init_data
loop_init_data:
    lw a3, 0(a0)
    sw a3, 0(a1)
    addi a0, a0, 4
    addi a1, a1, 4
    blt a1, a2, loop_init_data
end_init_data:

    la a0, _sbss
    la a1, _ebss
    bge a0, a1, end_init_bss
loop_init_bss:
    sw zero, 0(a0)
    addi a0, a0, 4
    blt a0, a1, loop_init_bss
end_init_bss:

    call main
loop:
    j loop
