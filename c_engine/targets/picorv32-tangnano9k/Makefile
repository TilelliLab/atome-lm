# Makefile — PicoRV32 / Tang Nano 9K firmware for Atome LLM.
#
# HW reference (read-only, not vendored): FreeRTOS-TetriSaraj's
# 1.hw/src/ip.cpu/{progmem.v,picosoc_noflash.v} and top_uart_hello.v /
# build.tcl. This target ships its own linker.ld/start.s/uart.c
# adapted from that project; nothing there is modified.
#
# Budget (from the instantiated RTL, see linker.ld):
#   FLASH (progmem) : 32 KB @ 0x00100000
#   RAM (data)       : 16 KB @ 0x00000000
#
# Faza 0 measurement (see README.md) found that linking newlib's -lc
# pulls in enough reentrancy/stdio/malloc bss to overflow the 16 KB
# RAM budget by itself. This Makefile links only -lm -lgcc and
# supplies libc_stubs.c (memcpy/memset/memcmp/errno) instead of -lc.
#
# Faza 5 (real Tang Nano 9K hardware) found that `rv32imc` -- the
# plan's original choice, for the code-density win -- silently fails
# on real silicon once progmem grows past ~8 KB: confirmed on hardware
# that a padded, logically-trivial firmware boots and prints fine at
# rv32im and produces zero UART bytes at rv32imc for the exact same
# byte size, with everything else (toolchain, bitstream, flash, host
# capture) held identical. Root cause not fully bottomed out (likely a
# PicoRV32 COMPRESSED_ISA vs. this progmem.v's single-cycle word-only
# read timing interaction that only shows up once enough addresses are
# exercised), but the fix is proven: MARCH=rv32im. Do not switch this
# back to rv32imc without re-verifying on real hardware first.

CROSS    ?= riscv-none-elf-
CC       := $(CROSS)gcc
SIZE     := $(CROSS)size
OBJCOPY  := $(CROSS)objcopy

UPSTREAM := ../../upstream

MARCH ?= rv32im
MABI  ?= ilp32

# nano/tiny config -- smallest official atome-lm config, see
# c_engine/RAM_TABLE.md. Override on the command line to try others,
# but re-run Faza 0's size check (`make check-budget`) before trusting
# a bigger config fits.
ATOME_DEFINES ?= \
    -DATOME_D_MODEL=16 \
    -DATOME_MAX_SEQ=32 \
    -DATOME_N_LAYERS=2 \
    -DATOME_N_PATHWAYS=3 \
    -DATOME_VOCAB_SIZE=32 \
    -DATOME_D_HEAD=8 \
    -DATOME_KERNEL_SIZE=5 \
    -DATOME_TOP_K=4

CFLAGS := -march=$(MARCH) -mabi=$(MABI) -Os -std=c99 \
          -ffreestanding -nostdlib -nostartfiles \
          -Wall -Wextra -ffunction-sections -fdata-sections \
          -I. -I$(UPSTREAM) $(ATOME_DEFINES)

ASFLAGS := -march=$(MARCH) -mabi=$(MABI)

LDFLAGS := -march=$(MARCH) -mabi=$(MABI) \
           -nostdlib -nostartfiles \
           -T linker.ld \
           -Wl,--gc-sections \
           -Wl,-Map=firmware.map

LIBS := -lm -lgcc

OBJ := start.o firmware.o atome.o uart.o libc_stubs.o
RAMCHECK_OBJ := start.o firmware_ramcheck.o atome.o uart.o libc_stubs.o
DEBUG_OBJ := start.o firmware_debug.o atome.o uart.o libc_stubs.o

# No real nano/tiny checkpoint ships in this repo (measure_ram.py
# generates a random-init one on the fly for the same reason). Default
# to the structurally-valid placeholder for build/size testing; pass
# MODEL_ATOME=path/to/real.atome for an actual trained model.
MODEL_ATOME ?= placeholder.atome

all: firmware.elf

firmware.elf: $(OBJ) linker.ld
	$(CC) $(LDFLAGS) $(OBJ) $(LIBS) -o $@
	$(SIZE) $@

# Raw binary for progmem.py (FreeRTOS-TetriSaraj/progmem.py <firmware.bin>
# <out-progmem.v>) -- baking into the bitstream is Faza 5, needs the Gowin
# toolchain and is not done by this Makefile.
firmware.bin: firmware.elf
	$(OBJCOPY) -O binary $< $@

# Stack high-water measurement firmware (see README "What's still
# unmeasured"): paints unused RAM, runs the same load/predict workload as
# firmware.elf, reports how deep the stack actually went, over UART.
firmware_ramcheck.elf: $(RAMCHECK_OBJ) linker.ld
	$(CC) $(LDFLAGS) $(RAMCHECK_OBJ) $(LIBS) -o $@
	$(SIZE) $@

firmware_ramcheck.bin: firmware_ramcheck.elf
	$(OBJCOPY) -O binary $< $@

firmware_ramcheck.o: firmware_ramcheck.c model_data.h $(UPSTREAM)/atome.h uart.h
	$(CC) $(CFLAGS) -c $< -o $@

firmware_debug.elf: $(DEBUG_OBJ) linker.ld
	$(CC) $(LDFLAGS) $(DEBUG_OBJ) $(LIBS) -o $@
	$(SIZE) $@

firmware_debug.bin: firmware_debug.elf
	$(OBJCOPY) -O binary $< $@

firmware_debug.o: firmware_debug.c model_data.h $(UPSTREAM)/atome.h uart.h
	$(CC) $(CFLAGS) -c $< -o $@

check-budget: firmware.elf
	@python3 tools/check_budget.py $(SIZE) firmware.elf

placeholder.atome:
	python3 tools/gen_placeholder_model.py --config nano -o $@

model_data.h: $(MODEL_ATOME)
	python3 tools/bin2c.py $(MODEL_ATOME) model_atome > $@

start.o: start.s
	$(CC) $(ASFLAGS) -c $< -o $@

firmware.o: firmware.c model_data.h $(UPSTREAM)/atome.h uart.h
	$(CC) $(CFLAGS) -c $< -o $@

atome.o: $(UPSTREAM)/atome.c $(UPSTREAM)/atome.h
	$(CC) $(CFLAGS) -c $< -o $@

uart.o: uart.c uart.h
	$(CC) $(CFLAGS) -c $< -o $@

libc_stubs.o: libc_stubs.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJ) $(RAMCHECK_OBJ) firmware.elf firmware.bin firmware_ramcheck.elf \
	      firmware_ramcheck.bin firmware.map model_data.h placeholder.atome

.PHONY: all clean check-budget
