"""Multi-ESP32 fit: a SuperESP head fits every mainline variant with headroom."""
from superesp import targets


def test_all_variants_fit_with_headroom():
    rep = targets.report()
    assert len(rep) >= 6  # ESP32, S2, S3, C3, C6, H2
    for r in rep:
        assert r["fits"] is True
        assert r["sram_headroom_x"] > 5.0   # comfortable margin everywhere


def test_footprint_is_tiny():
    # state in SRAM well under the smallest variant's RAM; weights tiny in flash
    assert targets.STATE_RAM_B < 64 * 1024
    assert targets.HEAD_FLASH_B < 32 * 1024


def test_covers_both_isas():
    arches = {r["arch"] for r in targets.report()}
    assert any("xtensa" in a for a in arches) and any("riscv" in a for a in arches)
