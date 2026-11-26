#!/usr/bin/env bash
# Run ECM Launcher from source (no build). Needs python3 with tkinter + venv.
cd "$(dirname "$(readlink -f "$0")")"
[ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt; }
exec .venv/bin/python main.py
