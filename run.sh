#!/bin/sh
cd "$(dirname "$0")" || exit 1
if [ ! -d .venv ]; then
  python3 -m venv .venv || { echo "Python 3.10+ is required"; exit 1; }
  .venv/bin/python -m pip install --quiet . || exit 1
fi
exec .venv/bin/python -m markmark
