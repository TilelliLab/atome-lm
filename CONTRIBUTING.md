# Contributing to Atome LM

Thanks for considering a contribution. This is a small, focused project — a tiny ternary language model + a C99 inference engine that talks to it bit-exactly. Read `PROJECT_CONTENT.md` first; it covers what you must not break.

## Quick start

```bash
git clone https://github.com/TilelliLab/atome-lm
cd atome-lm
./install.sh
. .venv/bin/activate
pytest -q        # expect: 146 passed (or 145 + 1 skipped without qemu-system-arm)
```

## Reporting bugs

Open an issue on GitHub with:

- what you ran (exact command)
- what you expected
- what happened (full error, not paraphrased)
- your platform: OS, Python version, and `python -c "import torch; print(torch.__version__)"`

If you hit a parity failure (Python forward ≠ C forward), please attach the failing seed and any checkpoint you trained — these are the highest-priority bugs.

## Submitting a pull request

1. Fork the repo and create a branch off `main`.
2. Make your change.
3. Run the full test suite — every PR must keep `pytest -q` green.
4. If your change touches `atome_llm/core/`, `c_engine/upstream/`, or the export format, **specifically confirm** these tests still pass:
   - `tests/test_parity_with_c.py` — single-forward Python ↔ C parity
   - `tests/test_parity_multitoken.py` — multi-token Python ↔ C parity
   - `tests/test_export_format.py` — binary format + header generation
5. Open the PR. CI will rerun the suite on Python 3.10 / 3.11 / 3.12.

## Scope of acceptable changes

Welcome:

- Bug fixes
- New test coverage (especially fuzz cases on the C parser and edge inputs to `atome_predict_next` / `atome_generate`)
- Performance improvements that preserve bit-exact parity
- Documentation fixes and clarifications
- New MCU target boards under `c_engine/targets/`, *as long as they don't change the upstream engine*
- New baselines under `atome_llm/baselines/` for honest A/B comparison

Out of scope, please don't open PRs for these:

- Adding heap allocation, dynamic memory, or libc dependencies to `c_engine/upstream/`
- Adding "shouldn't happen" fallbacks to deterministic code paths
- Bundling new tokenizers (BPE / sentencepiece) — the byte tokenizer is a load-bearing design choice for MCU flash budget
- Changes that break Python ↔ C parity, even if they improve a benchmark
- New features that promote code from `c_engine/experiments/` into `c_engine/upstream/` without full parity + bounds-check coverage

## Coding standards

- Python: keep it simple, no helper layers, no decorators-for-style. Match the existing voice — small functions, no premature abstraction, comments only when the *why* is non-obvious.
- C: C99 only, no GNU extensions, no libc beyond `<string.h>` / `<math.h>` / `<stdint.h>`. Static buffers sized by compile-time `ATOME_*` macros. Bounds-check all public API inputs.

## Security

If you find a security issue (anything that lets a malicious checkpoint or `.atome` blob compromise a host running the engine), please email **hello@atomelm.com** instead of filing a public issue. We'll coordinate disclosure.

## License

By submitting a contribution you agree it will be released under the Apache License 2.0 (the project license — see `LICENSE`).
