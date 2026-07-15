#!/usr/bin/env python3
"""tools/bin2c.py — bake a binary file into a C array, `const`-correct.

xxd -i (what cortex-m3-ram/rp2040 use to build model_data.h) emits a
plain `unsigned char foo[]`, not `const`. For those Cortex-M/RP2040
targets that puts the whole model blob in .data, meaning it gets
copied into RAM at boot -- wasted RAM the RAM_TABLE.md numbers don't
even account for (they only count .bss). Emitting `const` here instead
puts the array in .rodata, which this target's linker.ld maps into
FLASH only: the model blob costs progmem, not RAM. Confirmed in Faza 0
by checking `nm` output places it at a FLASH-range address.

Usage: bin2c.py <input-bin> <c-array-name> > model_data.h
"""
import sys


def main() -> int:
    path, name = sys.argv[1], sys.argv[2]
    data = open(path, "rb").read()

    out = [f"const unsigned char {name}[] = {{"]
    for i in range(0, len(data), 12):
        row = data[i:i + 12]
        out.append("  " + ", ".join(f"0x{b:02x}" for b in row) + ",")
    out.append("};")
    out.append(f"const unsigned int {name}_len = {len(data)};")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
