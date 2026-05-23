# Makefile — Cortex-M3 firmware for Atome LLM, runs on QEMU MPS2-AN385.
#
# Inputs:
#   - ../../upstream/atome.{c,h}    vendored C engine
#   - firmware.c                    boots the engine and prints logits
#   - startup.s                     vector table + reset handler
#   - linker.ld                     MPS2-AN385 memory map
#   - model_data.h                  baked-in .atome blob (generated at runtime)
#
# Output:
#   - firmware.elf                  loadable by `qemu-system-arm -kernel`
#
# The compile-time ATOME_* defines must match the Python AtomeLM config
# the model was exported from. The Python harness passes them in via
# `make ATOME_DEFINES="-DATOME_D_MODEL=16 -DATOME_N_LAYERS=2 ..."`.

CROSS    ?= arm-none-eabi-
CC       := $(CROSS)gcc
SIZE     := $(CROSS)size
OBJCOPY  := $(CROSS)objcopy

UPSTREAM := ../../upstream

ATOME_DEFINES ?= \
    -DATOME_D_MODEL=16 \
    -DATOME_MAX_SEQ=8 \
    -DATOME_N_LAYERS=2 \
    -DATOME_N_PATHWAYS=3 \
    -DATOME_VOCAB_SIZE=32 \
    -DATOME_D_HEAD=8 \
    -DATOME_KERNEL_SIZE=5 \
    -DATOME_TOP_K=4

CFLAGS := -mcpu=cortex-m3 -mthumb -Os -std=c99 \
          -Wall -Wextra -ffunction-sections -fdata-sections \
          -I. -I$(UPSTREAM) $(ATOME_DEFINES)

ASFLAGS := -mcpu=cortex-m3 -mthumb

# Use newlib + semihosting (rdimon) so printf reaches host stdout.
LDFLAGS := -mcpu=cortex-m3 -mthumb \
           -T linker.ld \
           --specs=rdimon.specs \
           -nostartfiles \
           -Wl,--gc-sections \
           -Wl,-Map=firmware.map

LIBS := -lc -lrdimon -lm

OBJ := startup.o firmware.o atome.o

all: firmware.elf

firmware.elf: $(OBJ) linker.ld
	$(CC) $(LDFLAGS) $(OBJ) $(LIBS) -o $@
	$(SIZE) $@

startup.o: startup.s
	$(CC) $(ASFLAGS) -c $< -o $@

firmware.o: firmware.c model_data.h $(UPSTREAM)/atome.h
	$(CC) $(CFLAGS) -c $< -o $@

atome.o: $(UPSTREAM)/atome.c $(UPSTREAM)/atome.h
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJ) firmware.elf firmware.map model_data.h

.PHONY: all clean
