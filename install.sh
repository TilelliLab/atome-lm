#!/usr/bin/env bash
# Atome LM — one-shot environment setup.
#
# Creates a local virtualenv, installs CPU-only PyTorch + Atome LM and its
# test dependencies, then runs check_env.py. No GPU, no CUDA, no cloud.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

echo "==> Atome LM install (CPU-only)"
"$PYTHON" --version

if [ ! -d .venv ]; then
  echo "==> Creating virtualenv at .venv"
  "$PYTHON" -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate

python -m pip install --upgrade pip --quiet

echo "==> Installing CPU-only PyTorch (no GPU required)"
pip install --quiet torch --index-url https://download.pytorch.org/whl/cpu

echo "==> Installing Atome LM + test dependencies"
pip install --quiet -e ".[dev]"

echo "==> Verifying environment"
python check_env.py

echo
echo "Done. Activate the environment with:"
echo "    . .venv/bin/activate"
echo "Then see QUICKSTART.md  (or run: pytest -q)"
