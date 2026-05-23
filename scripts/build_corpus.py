#!/usr/bin/env python3
"""scripts/build_corpus.py — fetch + clean + write a training corpus
for the byte-tokenizer Atome LLM.

Three built-in source modes plus a freeform `--source <url-or-path>`:

  --source tinystories
      Slice of TinyStories validation set (HuggingFace, MIT). Use for
      smoke-training the architecture: "does it learn anything at all?"

  --source esp-idf
      ESP-IDF documentation snippets (Apache-2.0). Permissive license,
      narrow embedded domain. The keeper for the "talking microcontroller"
      demo: when trained on this, the model speaks ESP32-shaped English.

  --source mcu-wikipedia
      Wikipedia articles on microcontrollers (CC-BY-SA). Broader narrative
      style than the API docs; useful as a complementary corpus or as a
      fallback when ESP-IDF docs are unreachable.

  --source <file-or-url>
      Read raw text from a local path or arbitrary HTTP(S) URL.

Cleaning: HTML strip → whitespace normalization → dedup-by-paragraph
(sha256) → non-printable filter → byte cap → write.

Reports input bytes, after-dedup bytes, paragraph count, ASCII fraction
(higher is better for the byte tokenizer — fewer tokens per character).

The script uses only Python stdlib (`urllib`, `html.parser`, `hashlib`)
to avoid pulling extra deps into the project.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


# Source URL lists. Kept short on purpose — the byte tokenizer + tiny
# model wants narrow domain coherence, not breadth.

TINYSTORIES_URLS = [
    # Validation slice: ~20 MB; we cap at --max-bytes anyway.
    "https://huggingface.co/datasets/roneneldan/TinyStories"
    "/resolve/main/TinyStoriesV2-GPT4-valid.txt",
]

ESP_IDF_URLS = [
    "https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/index.html",
    "https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/gpio.html",
    "https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/uart.html",
    "https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/adc.html",
    "https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/i2c.html",
    "https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/spi_master.html",
    "https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/timer.html",
    "https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/freertos.html",
]

MCU_WIKIPEDIA_URLS = [
    "https://en.wikipedia.org/wiki/Microcontroller",
    "https://en.wikipedia.org/wiki/ESP32",
    "https://en.wikipedia.org/wiki/Arduino",
    "https://en.wikipedia.org/wiki/STM32",
    "https://en.wikipedia.org/wiki/ARM_Cortex-M",
    "https://en.wikipedia.org/wiki/Raspberry_Pi_Pico",
    "https://en.wikipedia.org/wiki/Embedded_system",
    "https://en.wikipedia.org/wiki/Real-time_operating_system",
]


CACHE_DIR = Path(".corpus_cache")


# ----------------------------- fetch ----------------------------------- #

def _cache_path(url: str) -> Path:
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"{h}.bin"


def fetch(url: str, *, timeout: float = 30.0, use_cache: bool = True) -> bytes:
    """GET a URL, optionally cached on disk under .corpus_cache/."""
    cache = _cache_path(url)
    if use_cache and cache.exists():
        return cache.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": "atome-llm-corpus/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    if use_cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(data)
    return data


def fetch_text(source: str) -> str:
    """Read from local file or HTTP URL, decode as UTF-8 (replace errors)."""
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in ("http", "https"):
        return fetch(source).decode("utf-8", errors="replace")
    p = Path(source)
    if p.exists():
        return p.read_text(encoding="utf-8", errors="replace")
    raise SystemExit(f"source not found: {source}")


def fetch_text_tolerant(source: str) -> str | None:
    """Like fetch_text but returns None (with a stderr note) on HTTP errors,
    so a single 404 in a curated URL list doesn't crash the whole run."""
    try:
        return fetch_text(source)
    except Exception as e:
        print(f"  warn: skipping {source}: {e}", file=sys.stderr)
        return None


# ----------------------------- HTML strip ------------------------------ #

class _TextOnly(HTMLParser):
    """Stdlib HTMLParser that just collects visible text, dropping
    <script> and <style>. Naive but adequate for documentation pages."""

    SKIP = {"script", "style", "head", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._buf: list[str] = []
        self._depth_skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._depth_skip += 1
        elif self._depth_skip == 0 and tag in ("p", "br", "li", "h1", "h2", "h3", "h4", "div", "pre"):
            self._buf.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._depth_skip > 0:
            self._depth_skip -= 1
        elif self._depth_skip == 0 and tag in ("p", "li", "h1", "h2", "h3", "h4", "div", "pre"):
            self._buf.append("\n")

    def handle_data(self, data):
        if self._depth_skip == 0:
            self._buf.append(data)

    @property
    def text(self) -> str:
        return "".join(self._buf)


def strip_html(html: str) -> str:
    parser = _TextOnly()
    parser.feed(html)
    parser.close()
    return parser.text


# ----------------------------- clean ----------------------------------- #

_WS = re.compile(r"[ \t]+")
_NL = re.compile(r"\n{3,}")


def normalize_whitespace(text: str) -> str:
    text = _WS.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = _NL.sub("\n\n", text)
    return text.strip() + "\n"


def filter_nonprintable(text: str) -> str:
    """Drop control bytes except tab/newline. UTF-8 multibyte stays."""
    return "".join(c for c in text
                   if c in ("\n", "\t") or (ord(c) >= 0x20 and ord(c) != 0x7F))


def deduplicate_paragraphs(text: str) -> str:
    """Drop repeated paragraphs (sha256 over normalized form)."""
    seen: set[str] = set()
    out: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        key = hashlib.sha256(para.strip().lower().encode("utf-8")).hexdigest()
        if not para.strip() or key in seen:
            continue
        seen.add(key)
        out.append(para.strip())
    return "\n\n".join(out) + "\n"


def cap_bytes(text: str, max_bytes: int) -> str:
    """Truncate `text` to at most `max_bytes` UTF-8 bytes, never splitting
    a multibyte codepoint. Walks back one byte at a time until the prefix
    is a valid UTF-8 string — at most three iterations because UTF-8
    code units are at most 4 bytes."""
    enc = text.encode("utf-8")
    if len(enc) <= max_bytes:
        return text
    cut = enc[:max_bytes]
    while cut:
        try:
            return cut.decode("utf-8")
        except UnicodeDecodeError:
            cut = cut[:-1]
    return ""


def ascii_fraction(text: str) -> float:
    if not text:
        return 0.0
    enc = text.encode("utf-8", errors="replace")
    n_ascii = sum(1 for b in enc if b < 0x80)
    return n_ascii / len(enc)


# ----------------------------- pipeline -------------------------------- #

def clean_pipeline(raw_chunks: list[str], *, max_bytes: int) -> tuple[str, dict]:
    """Run the full clean pipeline over a list of raw text/HTML chunks.

    Returns (final_text, stats_dict).
    """
    raw_total = sum(len(c.encode("utf-8", errors="replace")) for c in raw_chunks)
    stripped = []
    for c in raw_chunks:
        if "<html" in c.lower() or "<body" in c.lower() or "<p>" in c.lower():
            stripped.append(strip_html(c))
        else:
            stripped.append(c)
    text = "\n\n".join(stripped)
    text = filter_nonprintable(text)
    text = normalize_whitespace(text)
    text = deduplicate_paragraphs(text)
    text = cap_bytes(text, max_bytes)
    text = normalize_whitespace(text)
    n_para = len([p for p in re.split(r"\n\s*\n", text) if p.strip()])
    stats = {
        "raw_bytes": raw_total,
        "out_bytes": len(text.encode("utf-8", errors="replace")),
        "paragraphs": n_para,
        "ascii_fraction": ascii_fraction(text),
    }
    return text, stats


def collect_source(source: str) -> list[str]:
    if source == "tinystories":
        return [c for c in (fetch_text_tolerant(u) for u in TINYSTORIES_URLS)
                if c is not None]
    if source == "esp-idf":
        return [c for c in (fetch_text_tolerant(u) for u in ESP_IDF_URLS)
                if c is not None]
    if source == "mcu-wikipedia":
        return [c for c in (fetch_text_tolerant(u) for u in MCU_WIKIPEDIA_URLS)
                if c is not None]
    return [fetch_text(source)]


# ----------------------------- CLI ------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", required=True,
                    help="tinystories | esp-idf | mcu-wikipedia | <file-or-url>")
    ap.add_argument("--max-bytes", type=int, default=1_000_000)
    ap.add_argument("--output", type=Path, default=Path("data/corpus.txt"))
    ap.add_argument("--no-cache", action="store_true",
                    help="skip the on-disk fetch cache")
    args = ap.parse_args()

    if args.no_cache:
        global fetch
        # Replace with non-caching version for this run
        original = fetch
        def fetch(url, *, timeout=30.0, use_cache=True):  # noqa: F811
            return original(url, timeout=timeout, use_cache=False)

    print(f"source: {args.source}")
    chunks = collect_source(args.source)
    print(f"fetched {len(chunks)} chunk(s)")

    text, stats = clean_pipeline(chunks, max_bytes=args.max_bytes)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")

    print(f"\nwrote {stats['out_bytes']:,} bytes / {stats['paragraphs']:,} "
          f"paragraphs → {args.output}")
    print(f"  raw input bytes:      {stats['raw_bytes']:,}")
    print(f"  after dedup + cap:    {stats['out_bytes']:,}")
    print(f"  ASCII fraction:       {stats['ascii_fraction']:.1%}  "
          f"(higher = fewer byte-tokens per character)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
