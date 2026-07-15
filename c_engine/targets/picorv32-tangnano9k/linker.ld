/*
 * linker.ld — PicoRV32 / Tang Nano 9K memory map.
 *
 * These numbers come from the instantiated RTL, not from
 * FreeRTOS-TetriSaraj's 2.sw/main.lds (which declares a 32 KB RAM
 * region that does not match what picosoc_noflash.v actually
 * instantiates — see README.md for the discrepancy).
 *
 *   progmem.v:            MEM_SIZE_BITS = 13  -> 8192 words -> 32 KB
 *   picosoc_noflash.v:    MEM_WORDS     = 4096 -> 16 KB
 *   picosoc_noflash.v:    PROGADDR_RESET = 0x00100000
 */
MEMORY
{
    FLASH (rx) : ORIGIN = 0x00100000, LENGTH = 0x8000  /* 32 KB progmem */
    RAM (xrw)  : ORIGIN = 0x00000000, LENGTH = 0x4000  /* 16 KB data RAM */
}

/*
 * ENTRY(start) + KEEP(*(.text.start)) below: defensive, not the fix for
 * anything observed. Without an explicit ENTRY, `-Wl,--gc-sections` has
 * no C-visible reachability root pointing at `start` (only the PicoRV32
 * reset vector fetching PROGADDR_RESET does, invisible to the linker).
 * In practice GNU ld's implicit fallback entry (first byte of .text)
 * already happened to keep it here -- verified on real hardware with
 * and without --gc-sections, both worked once the real bug (below) was
 * fixed. Kept explicit anyway since relying on the implicit fallback is
 * fragile if the section layout ever changes.
 *
 * The actual bug that cost real hardware debugging time: this target
 * was originally built with `-march=rv32imc`. That silently produces
 * zero UART output once progmem grows past ~8 KB on this exact
 * progmem.v/picosoc_noflash.v pair -- confirmed by flashing a padded,
 * logically-trivial firmware (no atome.c/libm/libgcc at all) at the
 * same byte size: works at rv32im, mute at rv32imc. See
 * c_engine/targets/picorv32-tangnano9k/README.md and
 * hardware/tangnano9k/README.md for the full bisection. Fix was in the
 * Makefile (MARCH=rv32im), not here, but if you're reading this because
 * UART went mute again after a size change, check MARCH first.
 */
ENTRY(start)

SECTIONS {
    /*
     * Real bug found via hardware debugging (see README.md "A second
     * real bug..."): RAM starts at address 0x00000000 on this platform
     * (unlike most targets, where address 0 is unmapped/reserved). A
     * global (g_tokens) linked to sit at exactly that address makes
     * atome.c's defensive `if (!tokens) return -1;` NULL-pointer check
     * misfire on a perfectly valid pointer -- atome_predict_next()
     * returned -1 on every call, silently, with no crash. Reserving
     * the first word of RAM guarantees no C symbol ever lands on
     * address 0 again.
     */
    .reserved_zero_page (NOLOAD) : {
        . = . + 4;
    } >RAM


    .text : {
        . = ALIGN(4);
        KEEP(*(.text.start))
        *(.text)
        *(.text*)
        *(.rodata)
        *(.rodata*)
        *(.srodata)
        *(.srodata*)
        . = ALIGN(4);
        _etext = .;
        _sidata = _etext;
    } >FLASH

    .data : AT (_sidata) {
        . = ALIGN(4);
        _sdata = .;
        *(.data)
        *(.data*)
        *(.sdata)
        *(.sdata*)
        . = ALIGN(4);
        _edata = .;
    } >RAM

    .bss : {
        . = ALIGN(4);
        _sbss = .;
        *(.bss)
        *(.bss*)
        *(.sbss)
        *(.sbss*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
        PROVIDE(end = .);
    } >RAM

    . = ALIGN(4);
    _heap_start = .;
    _estack = ORIGIN(RAM) + LENGTH(RAM);  /* PicoRV32 sets sp = STACKADDR on reset; start.s mirrors it */
}
