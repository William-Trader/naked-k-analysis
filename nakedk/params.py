# -----------------------------------------------------------------
# nakedk/params.py - naked-k-analysis runtime tuning parameters
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-1834A1A6
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
# -*- coding: utf-8 -*-
"""Runtime-tunable parameters for the deterministic engine.

The dashboard /api/params endpoint reads and writes a JSON file so a trader
can tune decision thresholds live without touching code. Every parameter has
a default that reproduces the historical behaviour exactly, so tests stay
green when params are absent.

Scope is deliberately the *decision* thresholds (stance, trend labels,
signal-bar floor), not feature computation (EMA periods etc.), which would
require recomputing features.
"""
from __future__ import annotations

import json
import os

DEFAULTS = {
    # stance (nakedk.signals.stance)
    "stance_adx_trend": 20.0,      # ADX below this -> no trend edge
    "stance_pos_short": 0.30,      # pos20 below this -> shorting disabled
    "stance_pos_long": 0.70,       # pos20 above this -> buying disabled
    "stance_stop_atr": 1.5,        # stop distance in ATR
    "stance_target_atr": 3.0,      # target distance in ATR
    # trend labels (nakedk.trend.trend_score)
    "trend_adx_trend": 20.0,       # ADX below this -> damp score toward 50
    "trend_label_up": 60.0,        # >= -> up / always_in long
    "trend_label_down": 40.0,      # <= -> down / always_in short
    "trend_label_strong_up": 75.0,
    "trend_label_strong_down": 25.0,
    # signal bar floor (nakedk.signalbar)
    "signalbar_min_quality": 40,
}

_PATH = os.environ.get("NK_PARAMS", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "state", "params.json"))


def load(path: str | None = None) -> dict:
    """Merge DEFAULTS with any persisted overrides."""
    params = dict(DEFAULTS)
    p = path or _PATH
    try:
        with open(p, encoding="utf-8") as fh:
            user = json.load(fh)
        if isinstance(user, dict):
            for k, v in user.items():
                if k in params and v is not None:
                    params[k] = v
    except Exception:
        pass
    return params


def save(params: dict, path: str | None = None) -> dict:
    """Persist only known keys (ignores unknown/garbage)."""
    clean = {k: v for k, v in (params or {}).items() if k in DEFAULTS}
    p = path or _PATH
    try:
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(clean, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return load(p)
