/*
 * linker.ld — Cortex-M3 memory map for QEMU MPS2-AN385.
 *
 * MPS2-AN385 memory (per QEMU docs): the boot region is RAM aliased
 * to 0x00000000 at startup; SSRAM2 lives at 0x28000000. We treat the
 * whole 0x00000000+ region as flash-equivalent (loaded by `-kernel`)
 * and use SSRAM2 for the data + heap + stack region.
 *
 * The model blob is large-ish (tens of KB at default config), so we
 * size FLASH to 4 MB to leave room for arbitrary configs without
 * editing this file.
 */

ENTRY(Reset_Handler)

/* QEMU MPS2-AN385 memory map:
 *   0x00000000  Code SSRAM, 4 MB     (loaded by `qemu -kernel`)
 *   0x20000000  Internal SRAM, 16 KB (Cortex-M3 TCM, too small for our stack)
 *   0x21000000  ZBT SSRAM1, 4 MB     (this is the data RAM we use)
 *   0x28000000  ZBT SSRAM2, 4 MB     (unused here)
 */
MEMORY
{
    FLASH (rx)  : ORIGIN = 0x00000000, LENGTH = 4M
    RAM   (rwx) : ORIGIN = 0x21000000, LENGTH = 4M
}

_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
    .vectors :
    {
        KEEP(*(.vectors))
    } > FLASH

    .text :
    {
        *(.text*)
        *(.rodata*)
        *(.glue_7)
        *(.glue_7t)
        *(.eh_frame)
        KEEP(*(.init))
        KEEP(*(.fini))
        . = ALIGN(4);
        _etext = .;
    } > FLASH

    .ARM.extab : { *(.ARM.extab* .gnu.linkonce.armextab.*) } > FLASH
    .ARM : {
        __exidx_start = .;
        *(.ARM.exidx*)
        __exidx_end = .;
    } > FLASH

    .preinit_array :
    {
        PROVIDE_HIDDEN (__preinit_array_start = .);
        KEEP(*(.preinit_array*))
        PROVIDE_HIDDEN (__preinit_array_end = .);
    } > FLASH

    .init_array :
    {
        PROVIDE_HIDDEN (__init_array_start = .);
        KEEP(*(SORT(.init_array.*)))
        KEEP(*(.init_array*))
        PROVIDE_HIDDEN (__init_array_end = .);
    } > FLASH

    .fini_array :
    {
        PROVIDE_HIDDEN (__fini_array_start = .);
        KEEP(*(SORT(.fini_array.*)))
        KEEP(*(.fini_array*))
        PROVIDE_HIDDEN (__fini_array_end = .);
    } > FLASH

    _sidata = LOADADDR(.data);
    .data :
    {
        . = ALIGN(4);
        _sdata = .;
        *(.data*)
        . = ALIGN(4);
        _edata = .;
    } > RAM AT > FLASH

    .bss :
    {
        . = ALIGN(4);
        _sbss = .;
        __bss_start__ = _sbss;
        *(.bss*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
        __bss_end__ = _ebss;
    } > RAM

    /* Heap grows up from end of bss; stack grows down from _estack */
    .heap :
    {
        . = ALIGN(8);
        _heap_start = .;
        end = .;
        _end = .;
    } > RAM

    /DISCARD/ :
    {
        *(.ARM.attributes)
    }
}
