#!/usr/bin/env python3
"""tools/check_budget.py — compare a built firmware.elf against the
real PicoRV32/Tang Nano 9K memory budget (see linker.ld / README.md),
not the inflated Cortex-M3 numbers in c_engine/RAM_TABLE.md.

Usage: check_budget.py <size-binary> <elf-path>
"""
import subprocess
import sys

FLASH_BUDGET = 0x8000  # 32 KB progmem
RAM_BUDGET = 0x4000    # 16 KB data RAM


def main() -> int:
    size_bin, elf = sys.argv[1], sys.argv[2]
    out = subprocess.run([size_bin, elf], capture_output=True, text=True,
                          check=True).stdout
    last = out.strip().splitlines()[-1].split()
    text, data, bss = int(last[0]), int(last[1]), int(last[2])

    flash = text + data
    ram = data + bss

    def line(label, used, budget):
        pct = 100.0 * used / budget
        status = "OK" if used <= budget else "OVER BUDGET"
        print(f"{label:6s} {used:6d} / {budget:6d} bytes "
              f"({pct:5.1f}%)  {status}")

    print(f"text={text} data={data} bss={bss}")
    line("flash", flash, FLASH_BUDGET)
    line("ram", ram, RAM_BUDGET)

    return 0 if flash <= FLASH_BUDGET and ram <= RAM_BUDGET else 1


if __name__ == "__main__":
    raise SystemExit(main())
