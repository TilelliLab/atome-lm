"""superesp.targets — ESP32-family capability matrix + fit analysis.

SuperESP heads share one tiny config: ~27 KB SRAM state (atome_state_t) + ~6.6 KB
flash per head (weights). The C99 engine has NO architecture-specific code, so it
runs on both Xtensa (ESP32/S2/S3) and RISC-V (C3/C6/H2) cores unchanged. Because
27 KB fits even the smallest ESP32 variant (≥320 KB SRAM) with >10× headroom,
ONE build profile covers the whole family — only the IDF target differs.
"""
from __future__ import annotations

from dataclasses import dataclass

# Measured for the shared config (gcc sizeof on host).
STATE_RAM_B = 27424
HEAD_FLASH_B = 6633


@dataclass(frozen=True)
class Target:
    name: str
    arch: str          # xtensa-lx6 / lx7 / riscv32
    cores: int
    sram_kb: int
    psram: str         # "optional" / "none"
    radios: str
    idf_target: str    # idf.py set-target <x>


# Mainline ESP32 family (datasheet SRAM figures).
TARGETS = [
    Target("ESP32",     "xtensa-lx6", 2, 520, "optional", "Wi-Fi+BT",      "esp32"),
    Target("ESP32-S2",  "xtensa-lx7", 1, 320, "optional", "Wi-Fi",         "esp32s2"),
    Target("ESP32-S3",  "xtensa-lx7", 2, 512, "optional", "Wi-Fi+BLE",     "esp32s3"),
    Target("ESP32-C3",  "riscv32",    1, 400, "none",     "Wi-Fi+BLE",     "esp32c3"),
    Target("ESP32-C6",  "riscv32",    1, 512, "none",     "Wi-Fi6+BLE+154","esp32c6"),
    Target("ESP32-H2",  "riscv32",    1, 320, "none",     "BLE+802.15.4",  "esp32h2"),
]


def fits(t: Target) -> dict:
    """Does a SuperESP head fit this target? (state in SRAM, weights in flash)."""
    margin = (t.sram_kb * 1024) / STATE_RAM_B
    return {"name": t.name, "arch": t.arch, "sram_kb": t.sram_kb,
            "fits": STATE_RAM_B < t.sram_kb * 1024,
            "sram_headroom_x": round(margin, 1), "idf_target": t.idf_target}


def report() -> list:
    return [fits(t) for t in TARGETS]
