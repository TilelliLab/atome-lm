# delta-inference experiment — host build + QEMU cortex-m3 build

CC      ?= cc
CFLAGS  := -std=c99 -O2 -Wall -Wextra -Werror

QEMU_HARNESS := ../../../security/emulation/cortex-m3-secure
ARM_CC  := arm-none-eabi-gcc
ARM_FLAGS := -std=c99 -Os -Wall -Wextra -mcpu=cortex-m3 -mthumb \
             -ffreestanding --specs=rdimon.specs -DDM_QEMU \
             -Wl,--defsym=__end__=_end \
             -I$(QEMU_HARNESS)

.PHONY: all host qemu run run-qemu real clean

all: host

host: bench
	@echo ">> host build OK"

bench: bench.c delta_matvec.c delta_matvec.h
	$(CC) $(CFLAGS) -o $@ bench.c delta_matvec.c -lm

run: bench
	./bench

# cortex-m3 firmware: same bench.c + delta_matvec.c, semihosted printf,
# DWT cycle counter. Reuses the security emulation startup + linker.
qemu: bench_m3.elf
	@echo ">> QEMU firmware built: bench_m3.elf"

bench_m3.elf: bench.c delta_matvec.c delta_matvec.h
	@if ! command -v $(ARM_CC) >/dev/null 2>&1; then \
	  echo "INSTALL: apt-get install -y gcc-arm-none-eabi qemu-system-arm"; \
	  exit 0; fi
	$(ARM_CC) $(ARM_FLAGS) -T$(QEMU_HARNESS)/linker.ld \
	  -o $@ $(QEMU_HARNESS)/startup.s bench.c delta_matvec.c -lm

run-qemu: bench_m3.elf
	@if ! command -v qemu-system-arm >/dev/null 2>&1; then \
	  echo "INSTALL: apt-get install -y qemu-system-arm"; exit 0; fi
	qemu-system-arm -M mps2-an385 -nographic -semihosting \
	  -kernel bench_m3.elf

# cross-check the C primitive on real captured traces
real: bench_real
	@if [ ! -f traces/wv_block0.tern ]; then \
	  echo ">> capturing real traces first"; python3 capture_real.py; fi
	./bench_real

bench_real: bench_real.c delta_matvec.c delta_matvec.h
	$(CC) $(CFLAGS) -o $@ bench_real.c delta_matvec.c -lm

clean:
	rm -f bench bench_m3.elf bench_real *.o
