# Atome LLM on PicoRV32 / Tang Nano 9K

Bare-metal port of the C99 ternary inference engine
(`c_engine/upstream/atome.c`) to the PicoRV32 RISC-V soft-core on a
Tang Nano 9K FPGA (`nano`/`tiny` config: d_model=16, 2 layers,
max_seq=32). Boots, links, and loads a real model on real hardware —
see [`hardware/tangnano9k/`](../../../hardware/tangnano9k/) for the
synthesized bitstream project and captured UART evidence; this
directory is the cross-compile target that produces `firmware.bin`.

> **Status: blocked on an upstream bug, not a target bug.** This port
> found and fixed two real target-side hardware bugs (NULL-pointer
> aliasing at address 0, `rv32imc` silently breaking above ~8 KB — both
> below), plus a **third bug that lives in `c_engine/upstream/atome.c`
> itself** (misaligned float-pointer reads in `atome_load()`'s binary
> parser) that this target cannot fix without touching upstream code,
> which is out of scope for a target directory per `CONTRIBUTING.md`.
> See "A third bug — this one is upstream, not ours" below. Firmware
> boots, UART works, the model loads — but real inference currently
> hangs on this exact hardware once it reaches the first `LayerNorm`.
> This needs an upstream fix before a real parity run is possible here.

## Hardware basis

The UART platform layer, PicoRV32 toolchain conventions, and Gowin EDA
flow are taken as a **read-only reference** from the
FreeRTOS-TetriSaraj project's `top_uart_hello.v` / `build.tcl` (plain
UART-only top, no HDMI/FreeRTOS). That project is not modified; this
directory contains its own `linker.ld`/`start.s`/`uart.c` adapted from
it, and `hardware/tangnano9k/firmware/` holds copies (not references)
of the Verilog/constraints/build script needed to synthesize.

Actual memory map, read from the instantiated RTL (not assumed):

| Region | RTL parameter | Size | Base |
|---|---|---|---|
| Flash / progmem | `progmem.v`: `MEM_SIZE_BITS` (auto, power-of-two-sized per build) | up to 32 KB | `0x00100000` |
| Data RAM | `picosoc_noflash.v`: `MEM_WORDS = 4096` | 16 KB | `0x00000000` |

`FreeRTOS-TetriSaraj/2.sw/main.lds` declares a 32 KB RAM region
(`LENGTH = 0x8000`) — that does not match what `picosoc_noflash.v`
actually instantiates (`4*MEM_WORDS = 0x4000` = 16 KB). The linker
script there is stale; the RTL is the source of truth. `linker.ld` in
this directory uses the RTL numbers, not a copy of `main.lds`.

`progmem.py` (the flash-baking script) does not hardcode 32 KB either:
it sizes `MEM_SIZE_BITS` to the smallest power-of-two word depth that
holds the given `firmware.bin`, so a ~17 KB firmware synthesizes a 32
KB-capable progmem block (`MEM_SIZE_BITS=13`, since 17 KB needs more
than the 16 KB a 12-bit depth gives), not a fixed one. 32 KB is this
target's *budget ceiling*, not a hard hardware constant — see
`linker.ld` for why the ceiling itself is trustworthy (RTL-derived).

## Faza 0 measurement — the plan's original verdict was wrong

`PICORV32_TANGNANO9K_PLAN.md` (repo root) originally concluded flash
would *not* fit even the smallest config, based on
`c_engine/RAM_TABLE.md`'s Cortex-M3 number (41.9 KB flash for `nano`).
Building the actual firmware for this target and measuring it
directly overturned that:

| Build | march | .text | .data+.bss | Flash used / 32 KB | RAM used / 16 KB |
|---|---|---:|---:|---:|---:|
| naive (`-lc -lm -lgcc`) | rv32im | 25260 | 17636 | 81 % | **107 % — overflows by 1252 B** |
| naive (`-lc -lm -lgcc`) | rv32imc | 18052 | 17636 | 58 % | **107 % — overflows by 1252 B** |
| this target (no `-lc`, `--gc-sections`) | rv32im | 17512 | 14452 | 53 % | 88 % |
| this target (no `-lc`, `--gc-sections`) | rv32imc | 13100 | 14452 | 40 % | 88 % |

Reproduce with `make check-budget` (default `MARCH=rv32im`, see Faza 5
below for why).

What actually happened:

1. **The Cortex-M3 41.9 KB number is not representative.** It's built
   with `-lc -lrdimon -lm` (full newlib + semihosting), which this
   bare-metal UART target never needed. RISC-V code density (even
   plain `rv32im`) turned out smaller than that ARM Thumb number once
   the semihosting/libc weight is removed.
2. **`-lc` is what actually threatens the RAM budget, not the engine.**
   Linking newlib's `-lc` pulls in its reentrancy struct, stdio `FILE`
   table, and malloc arena (`_impure_data`, `__sf`, `__malloc_av_`,
   ...) even though nothing here calls `malloc`, `fopen`, or `printf`.
   That alone overflowed the 16 KB RAM region by exactly 1252 bytes —
   confirmed by the linker (`region 'RAM' overflowed by 1252 bytes`).
   [`libc_stubs.c`](libc_stubs.c) replaces it with ~15 lines
   (`memcpy`/`memset`/`memcmp`/`errno`); `-lm -lgcc` are still linked
   normally.
3. **Float-without-FPU cost is real but affordable.** `atome.c` calls
   `sqrtf` (LayerNorm), `expf` (softmax), and `tanhf` (SSM gate) — the
   plan only anticipated `sqrtf`. Measured cost: libgcc's
   add/sub/mul/div/compare softfloat routines are ~5.0 KB; the three
   libm calls (plus `__ieee754_expf`'s internal `expm1f` and
   `sqrtf`'s CLZ table) add ~2.6 KB more. That's ~7.6 KB total — a real
   tax, but it fits, so no hand-written `sqrtf`/`expf`/`tanhf`
   replacements were needed.
4. **`-fno-builtin` (which the plan's draft `CFLAGS` included) breaks
   the build outright.** `atome.c` uses `memcpy`/`memset`/`memcmp`
   itself; with `-fno-builtin -nostdlib` and no libc, those are
   undefined at link time. This target's `CFLAGS` (see `Makefile`)
   drops `-fno-builtin` and supplies the three functions itself.
5. **The model blob must be `const` or it silently costs RAM.**
   `cortex-m3-ram` and `rp2040`'s `model_data.h` are baked with
   `xxd -i`, which emits a plain (non-`const`) `unsigned char[]`. A
   non-`const` global can't be proven read-only across translation
   units, so the compiler places it in `.data`: flash *and* a RAM
   copy. `c_engine/RAM_TABLE.md`'s "RAM (.bss)" column only counts
   `.bss`, so that RAM cost isn't visible there. `tools/bin2c.py` here
   emits `const` instead, which this target's `linker.ld` maps
   `.rodata` into the flash-only region — confirmed with `nm` showing
   `model_atome` at a flash-range address, zero RAM cost.

RAM is the binding constraint at 88% (14452 / 16384 B), all from
`atome_state_t` + `atome_model_t` + the token buffer — the engine
itself, not any library overhead. Flash has real headroom (53% used
even at `rv32im`), so **Faza 1 (BSRAM resynthesis to grow progmem) is
not needed** for the `nano`/`tiny` config.

## Faza 5 (real hardware) — a second plan decision was also wrong: use `rv32im`, not `rv32imc`

Flashed to a real Tang Nano 9K (see `hardware/tangnano9k/` for the
full synthesis/flash/capture setup). Captured, working boot output:

```
atome-picorv32 boot
prompt: 0A 14 05 11 00 19
generated: FF FF FF FF FF FF FF FF
done
```

(`0A 14 05 11 00 19` = the hardcoded prompt `{10,20,5,17,0,25}` in hex
— correct. The 8 generated `FF` tokens are expected noise: no trained
`nano`/`tiny` checkpoint exists, see below, so this is running
structurally-valid but untrained random weights.)

Getting here found a real, reproducible hardware bug: **`rv32imc`
(the plan's design decision — compressed ISA for code density) boots
fine at small firmware sizes but silently produces zero UART output
once progmem grows past roughly 8 KB, on this exact
`progmem.v`/`picosoc_noflash.v` pair.** Confirmed by bisection on real
hardware, not simulation:

- A ~13 KB firmware with **trivial logic** (a const padding array, no
  atome/libm/libgcc at all) — 0 bytes over UART at `rv32imc`, prints
  fine at `rv32im`, same byte size, same everything else.
  `FreeRTOS-TetriSaraj`'s own already-proven `hello.c` (988 B, small
  enough to stay under the failure threshold either way) and this
  target's own `uart.c`/`start.s` (proven separately via a small
  "smoke test" firmware) both ruled out the UART driver, `start.s`,
  the synthesis pipeline, and the host-side capture as the cause.
  `-Wl,--gc-sections` and an explicit `ENTRY(start)`/`KEEP()` were
  also ruled out (tested with and without; no change).
- `FreeRTOS-TetriSaraj`'s own milestone doc
  (`0.doc/milestone_5_freertos_boot.md`) has a *working* 32 KB-class
  firmware (17260 B) on this same `progmem.v`/`build.tcl` pipeline —
  built at `rv32im`. That's the tell: big firmware works at `rv32im`,
  fails at `rv32imc`; small firmware works at either. The likely
  mechanism is PicoRV32's `COMPRESSED_ISA` fetch (which can issue two
  back-to-back word reads to reconstruct an instruction straddling a
  word boundary) interacting badly with `progmem.v`'s fixed
  single-cycle-latency word-only read port once enough addresses get
  exercised to hit the case — not confirmed at the Verilog level, just
  empirically bisected on real silicon.

**Net effect:** this target's `Makefile` now defaults to `MARCH=rv32im`
(not `rv32imc`, reversing the plan's design decision 2.3). Flash usage
at `rv32im` is 17512 B / 32768 B = 53%, still comfortable. Do not
switch back to `rv32imc` without re-verifying on real hardware — the
synthesis and `make check-budget` both pass silently either way; only
the real UART output reveals the bug.

## A second target-side bug — NULL-pointer aliasing at address 0

The very first real-checkpoint hardware run (a fixed-seed, non-placeholder
model, see "A third bug" below for how that checkpoint was made) produced
`generated: FF FF FF FF FF FF FF FF` — 8 tokens of `0xFF`, which is out
of range for `ATOME_VOCAB_SIZE=32` (valid tokens are 0–31). Debug
firmware printing the raw 32-bit return value of `atome_predict_next()`
confirmed it was exactly `0xFFFFFFFF`, i.e. `-1` — the function's own
early-exit guard, `if (!model || !state || !tokens || n_tokens < 1)
return -1;`, firing on every single call despite valid arguments.

Root cause: `linker.ld`'s `RAM (xrw): ORIGIN = 0x00000000` — this
platform's data RAM starts at address 0, unlike almost every other
target (embedded or otherwise), where address 0 is unmapped/reserved
and therefore a safe sentinel for "no pointer here." `riscv-none-elf-nm`
confirmed `g_tokens` (the first global in this target's `.bss`) linked
to exactly `0x00000000`. `atome_predict_next(&g_model, &g_state,
g_tokens, n)` passes `g_tokens` as `tokens`; the perfectly ordinary,
valid, non-NULL pointer to it evaluates as `0`, so `!tokens` is true —
a completely standard defensive NULL check, entirely reasonable on
every platform except this one, silently misfiring.

**Fix (`linker.ld`):** reserve the first word of RAM before `.data`/`.bss`
begin, so no C symbol can ever link to address `0x0` again:

```
.reserved_zero_page (NOLOAD) : { . = . + 4; } >RAM
```

Confirmed with `nm` after the fix: `g_tokens` now links to `0x00000004`.
This is also the reason the very first captured evidence
(`hardware/tangnano9k/evidence/serial_boot_log_tangnano9k.txt`, the
`FF FF FF FF FF FF FF FF` run) is captioned there as "expected noise
from untrained weights" — that caption was written *before* this bug
was found and is **wrong**; the real explanation is this NULL-pointer
alias, not decoded random weights. Left uncorrected in that file
(evidence logs are a record of what was captured and believed at the
time) with a pointer added to this section.

## A third bug — this one is upstream, not ours

Fixing the NULL-pointer bug (below) let real inference actually start
running for the first time. It then hung on real hardware. Bisected
with a temporary, instrumented, local copy of `atome.c` (not committed,
not the real upstream file) that added UART checkpoints at every stage
of `atome_predict_next()` / `atome_block_forward()` / `atome_layer_norm()`.
Root cause, confirmed by printing the actual pointer values on real
hardware:

```
gamma_addr=0x001042DB
beta_addr=0x0010431B
```

Neither address is 4-byte aligned (`0xDB mod 4 = 3`, `0x1B mod 4 = 3`).
`atome_layer_norm()` dereferences `params->gamma[i]` as a `const
float*` — an unaligned 32-bit load. PicoRV32 defaults to
`CATCH_MISALIGN = 1` (confirmed in `picorv32.v`): a misaligned load
either raises a bus-error IRQ (not configured on this minimal
UART-only top — there's no timer/bus-error handler wired up) or, with
IRQs off, drops straight into `cpu_state_trap`, a terminal state the
core never leaves. Either way: silent, total hang, no crash message,
no UART output — indistinguishable from "very slow" until you
instrument the code and watch it stop dead at one exact line.

**Where the misalignment actually comes from — it's arithmetic, not
bad luck.** The `ATOME01` magic string is 7 bytes. `7 mod 4 = 3`.
Every packed-ternary section this specific `nano` config produces
happens to be a whole multiple of 4 bytes (its dimensions are all
powers of two), so nothing after the magic ever re-aligns the byte
cursor `atome_load()` walks forward — the entire rest of the file
stays offset by a constant 3 bytes from a 4-byte boundary. The first
`float*` field after the embedding table (`block[0].norm.gamma`) lands
at byte offset `7 + (4 + 128) = 139`, and `139 mod 4 = 3`. That matches
the measured address exactly. Every `gamma`/`beta`/`a`/`b`/`c_out`
pointer in the file inherits the same 3-byte skew.

**Why this was never caught before:** x86 (native test suite) and
ARMv7-M (Cortex-M3, `cortex-m3-ram` target) both do unaligned 32-bit
loads transparently in hardware — no trap, no penalty worth noticing.
QEMU-based tests likely don't model the trap either. PicoRV32, run on
real silicon with its default (and RV32I-spec-legal) `CATCH_MISALIGN`
behavior, is the first target in this repo that actually enforces
alignment — and it does, immediately, on the very first `LayerNorm`
call of the very first model this port tried loading.

**This is a bug in the `ATOME01` binary format / `atome_load()`
parser** (`c_engine/upstream/`), not in this target's glue code —
fixing it (e.g. padding the magic to 8 bytes, or rounding each
`read_*()` cursor up to 4-byte alignment before the next section)
means changing the shared engine, which `CONTRIBUTING.md` reserves for
upstream, not board-target PRs. This target's own code has no
misaligned access anywhere — the bug is entirely inside the one
`atome_predict_next()` call into upstream code. Filed upstream (see the
repo's issue tracker); this target's firmware will produce real,
verifiable inference output as soon as that lands, with zero changes
needed here.

**Fully reproducible without hardware**, for whoever picks up the
upstream fix: `nano_seed42.atome` in this directory (`torch.manual_seed(42)`,
the exact `AtomeLM(vocab_size=32, d_model=16, n_layers=2, d_head=8,
top_k=4, kernel_size=5)` config `tests/test_parity_with_c.py` already
uses) reproduces the same misalignment on any strict-alignment target,
and the expected correct output is already known: native-host build of
this exact engine + this exact blob generates `[6, 10, 18, 10, 18, 10,
10, 1]` for the prompt `{10, 20, 5, 17, 0, 25}`, bit-exact with the
Python reference (regenerate both via
`python scripts/gen_nano_checkpoint.py`).

## What's measured now, and what's still open

**Stack high-water mark — measured directly on real hardware**, not
inferred. `firmware_ramcheck.elf` (same stack-painting technique as
`cortex-m3-ram/firmware.c`: paint RAM below the live stack pointer with
`0xA5A5A5A5`, run the identical load/init/6-token-prompt/8-generation
workload as `firmware.c`, walk down to find the lowest word the stack
touched) was built, flashed, and read back over UART:

```
bss=0x00003874 stack_used=0x00000130 total=0x000039A4 ram_budget=0x00004000
```

`bss=14452 B` (matches `firmware.elf`'s `.bss` exactly), `stack_used=304
B` (~2x the Cortex-M3 figure of 144 B for the same workload — plausible
given RV32's calling convention spilling more callee-saved registers
through the same call chain), `total=14756/16384 B = 90.1%`, **margin =
1628 B (9.9%) free**. Tight, but real and positive. Full writeup:
[`hardware/tangnano9k/evidence/serial_ramcheck_log_tangnano9k.txt`](../../../hardware/tangnano9k/evidence/serial_ramcheck_log_tangnano9k.txt).
Caveat: this is one specific run (6-token prompt, 8 generation steps) —
not a proven worst case across all inputs / all `ATOME_MAX_SEQ` lengths.

Reproduce: `make firmware_ramcheck.elf firmware_ramcheck.bin`, bake into
`progmem.v` the same way as `firmware.bin` (see `hardware/tangnano9k/`).

- **A real (fixed-seed) checkpoint now exists**: `nano_seed42.atome`
  (1399 B, `torch.manual_seed(42)`, generated by
  `scripts/gen_nano_checkpoint.py`), exported with the repo's own
  `scripts/export_to_atome.py` — not the structurally-valid-but-random
  `tools/gen_placeholder_model.py` blob `make` still defaults to for
  quick build/size checks. Native-host build confirmed this checkpoint
  bit-exact against the Python reference (`[6, 10, 18, 10, 18, 10, 10,
  1]` for prompt `{10, 20, 5, 17, 0, 25}`). **It does not yet run to
  completion on this target's real hardware** — see "A third bug"
  above; the earlier claim in this file that the placeholder blob was
  "verified to load and run without crashing on real hardware" predates
  that discovery and was true only in the narrow sense that the
  NULL-pointer bug (previous section) made every call return instantly
  before reaching any real computation, placeholder or not. Use
  `make MODEL_ATOME=nano_seed42.atome` to build with it; re-flash and
  compare against the Python reference once the upstream alignment fix
  lands.

## Build

```bash
cd c_engine/targets/picorv32-tangnano9k
make                 # bakes a placeholder model, builds firmware.elf, MARCH=rv32im by default
make check-budget    # explicit pass/fail against the real 32 KB / 16 KB budget
make firmware.bin    # raw binary for FreeRTOS-TetriSaraj's progmem.py (see hardware/tangnano9k/)
```

Requires a RISC-V bare-metal GCC on `PATH` as `riscv-none-elf-gcc` (or
override `CROSS=`) — this was built and tested against the xPack
`riscv-none-elf-gcc` 15.2.0 toolchain. `xxd` is intentionally not
required; `tools/bin2c.py` does the same job in pure Python.

For the full synthesize/flash/capture flow on real hardware, see
[`hardware/tangnano9k/README.md`](../../../hardware/tangnano9k/README.md).

## Files

| File | Purpose |
|---|---|
| `linker.ld` | Real 32 KB flash @ `0x00100000` / 16 KB RAM @ `0x0` memory map; `ENTRY(start)` + `KEEP(*(.text.start))` so `--gc-sections` can't strip the reset vector; `.reserved_zero_page` reserves RAM's first word so no symbol can link to address `0x0` (see "A second target-side bug" above) |
| `start.s` | Reset entry, `.data`/`.bss` init, adapted from `FreeRTOS-TetriSaraj/2.sw/start.s` (IRQ/benchmark scaffolding dropped — this is a single-shot loop, no timer IRQs) |
| `uart.c` / `uart.h` | `uart_init`/`uart_putchar`/`uart_print`/`uart_print_hex`, adapted from `FreeRTOS-TetriSaraj/2.sw/uart.c`. `uart_init()` sets the clock divider (234, for 27 MHz / 115200 baud) — the original `uart.c` this was adapted from didn't set it, relying on the caller; this target's `firmware.c` calls it first thing, confirmed necessary on real hardware (simpleuart.v's own reset default divider is 562, which is ~48 KBd, not 115200) |
| `libc_stubs.c` | Hand-written `memcpy`/`memset`/`memcmp`/`errno` — see Faza 0 point 2 above |
| `firmware.c` | `atome_load` → `atome_init` → prompt + generate loop → UART print, modeled on `cortex-m3-ram/firmware.c` |
| `firmware_ramcheck.c` | Stack-painting variant for real RAM high-water measurement — see "What's measured now" above |
| `nano_seed42.atome` | Real (fixed-seed, not placeholder) `nano` checkpoint, generated by `scripts/gen_nano_checkpoint.py`, bit-exact against Python natively; the checkpoint this port's real hardware runs use |
| `tools/gen_placeholder_model.py` | Structurally valid but randomly-weighted `.atome` blob for build/size/boot testing |
| `tools/bin2c.py` | `const`-correct binary→C-array baker (replaces `xxd -i`) |
| `tools/check_budget.py` | Compares a built ELF against the real 32 KB / 16 KB budget |

## Next steps

- **Blocked on upstream**: report the `atome_load()` misalignment bug
  (see "A third bug" above) against `TilelliLab/atome-lm`; once fixed
  there, this target needs no further changes to produce a real,
  verifiable parity run — `nano_seed42.atome` and
  `scripts/gen_nano_checkpoint.py` already exist for exactly that.
- Faza 6: PR following `CONTRIBUTING.md`, with the hardware evidence
  in `hardware/tangnano9k/evidence/`.
