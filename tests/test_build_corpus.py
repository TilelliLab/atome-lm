"""tests/test_build_corpus.py — unit tests for the cleaning pipeline.

Pure logic tests using inline strings — the actual fetch path is
exercised manually via `python scripts/build_corpus.py --source ...`,
not in pytest, because the network is not always available and would
produce flaky tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_corpus import (  # type: ignore
    ascii_fraction,
    cap_bytes,
    clean_pipeline,
    deduplicate_paragraphs,
    filter_nonprintable,
    normalize_whitespace,
    strip_html,
)


def test_strip_html_drops_script_and_style():
    html = """<html><head><style>body{color:red}</style></head>
    <body><script>alert(1)</script><p>Hello world</p></body></html>"""
    text = strip_html(html)
    assert "Hello world" in text
    assert "alert" not in text
    assert "color:red" not in text


def test_strip_html_preserves_paragraph_structure():
    html = "<p>One</p><p>Two</p><p>Three</p>"
    text = strip_html(html)
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    assert "One" in paragraphs
    assert "Two" in paragraphs
    assert "Three" in paragraphs


def test_normalize_whitespace_collapses_runs():
    text = "hello   world\n\n\n\nnext"
    out = normalize_whitespace(text)
    assert "hello world" in out
    assert "\n\n\n" not in out


def test_filter_nonprintable_drops_control_bytes_keeps_tabs_newlines():
    text = "hello\x00\x01world\twith\ntab"
    out = filter_nonprintable(text)
    assert "\x00" not in out
    assert "\x01" not in out
    assert "\t" in out
    assert "\n" in out
    assert "world" in out


def test_deduplicate_paragraphs_collapses_repeats():
    text = "Para A\n\nPara B\n\nPara A\n\nPara A\n\nPara C"
    out = deduplicate_paragraphs(text)
    paragraphs = [p.strip() for p in out.split("\n\n") if p.strip()]
    assert sorted(paragraphs) == sorted(["Para A", "Para B", "Para C"])


def test_dedup_is_case_insensitive():
    text = "Hello World\n\nhello world\n\nHELLO WORLD"
    out = deduplicate_paragraphs(text)
    paragraphs = [p.strip() for p in out.split("\n\n") if p.strip()]
    assert len(paragraphs) == 1


def test_cap_bytes_respects_limit():
    text = "x" * 1000
    out = cap_bytes(text, max_bytes=500)
    assert len(out.encode("utf-8")) <= 500


def test_cap_bytes_does_not_split_utf8():
    """Multibyte chars must not be cut mid-codepoint."""
    text = "é" * 100  # each é is 2 bytes in UTF-8
    out = cap_bytes(text, max_bytes=51)
    # Should round down to 50 bytes (25 valid codepoints)
    enc = out.encode("utf-8")
    assert len(enc) <= 51
    out.encode("utf-8").decode("utf-8")  # round-trip must succeed


def test_ascii_fraction_pure_ascii_is_1():
    assert ascii_fraction("abcdef") == 1.0


def test_ascii_fraction_pure_multibyte_is_below_1():
    f = ascii_fraction("éééé")  # 8 bytes total, 0 ASCII
    assert f == 0.0


def test_ascii_fraction_mixed():
    f = ascii_fraction("abcé")  # 5 bytes total, 3 ASCII
    assert 0.5 < f < 0.7


def test_clean_pipeline_html_input_end_to_end():
    html = ("<html><body>"
            "<p>Section A.</p>"
            "<p>Section B.</p>"
            "<p>Section A.</p>"  # duplicate, should be dropped
            "<script>x</script>"
            "</body></html>")
    text, stats = clean_pipeline([html], max_bytes=10_000)
    assert "Section A." in text
    assert "Section B." in text
    assert "x" not in text
    assert stats["paragraphs"] == 2
    assert stats["ascii_fraction"] > 0.95
    assert stats["out_bytes"] > 0
    assert stats["raw_bytes"] >= len(html)


def test_clean_pipeline_plain_text_input():
    raw = "First paragraph.\n\nSecond paragraph.\n\nFirst paragraph.\n"
    text, stats = clean_pipeline([raw], max_bytes=10_000)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    assert sorted(paragraphs) == sorted(["First paragraph.", "Second paragraph."])
    assert stats["paragraphs"] == 2
