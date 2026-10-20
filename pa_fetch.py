#!/usr/bin/env python3
# -----------------------------------------------------------------
# pa_fetch.py - naked-k-analysis core price-action engine
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-FD2C1B22
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
"""Backwards-compatible entry point: python3 pa_fetch.py BTCUSDT ETHUSDT."""
import sys

from nakedk.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["fetch", *sys.argv[1:]]))
