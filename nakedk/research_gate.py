# -----------------------------------------------------------------
# nakedk/research_gate.py - evidence-backed optional admission filter
# (c) 2026 William-Trader (https://github.com/William-Trader)
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# -----------------------------------------------------------------
"""Optional admission filter derived from the frozen 2.2.0 research run.

Disabled by default so existing deployments keep their exact behaviour.
Enable with NK_RESEARCH_GATE=1 after reading:

    research/results/backtest_2.2.0.json     (train/validation/test split)
    research/results/verification_2.2.0.json (11/12 perturbation scenarios)

Evidence summary (BTCUSDT + ETHUSDT, 730 frozen days, 4h bars, 12bp cost,
test segment evaluated once):
    baseline       169 trades  avg -0.0125%  hit 46.72%  maxDD -12.33%
    v22 + params    51 trades  avg +0.1162%  hit 56.88%  maxDD  -5.11%

This is a historical simulation, NOT a claim of positive expectation. The
filter is a *subtractive* gate: it can only remove plans, never create one.
"""
from __future__ import annotations

import os

# Mirrors `v22` in nakedk.backtest._passes_gate plus the selected params.
ADX_MIN = 22
OVERLAP_MAX = 0.65
VOL_Z_MIN = -0.5
ADX_SLOPE_MIN = -1.0

EVIDENCE = {
    "backtest": "research/results/backtest_2.2.0.json",
    "verification": "research/results/verification_2.2.0.json",
    "selected": {"gate": "v22", "stop_atr": 1.5, "target_atr": 3.0,
                 "adx_min": ADX_MIN},
}


def enabled() -> bool:
    return os.environ.get("NK_RESEARCH_GATE", "").strip().lower() in (
        "1", "true", "yes", "on")


def admit(primary: dict) -> tuple[bool, str]:
    """Return (allowed, reason). Applied to the primary (4h) analysis block."""
    if not enabled():
        return True, ""
    f = primary.get("features") or {}
    adx = f.get("adx", f.get("adx14"))
    if adx is None or float(adx) < ADX_MIN:
        return False, "research_gate: ADX 低于 %s" % ADX_MIN
    if float(f.get("adx_slope") or 0) < ADX_SLOPE_MIN:
        return False, "research_gate: ADX 斜率走弱"
    if float(f.get("overlap") or 0) >= OVERLAP_MAX:
        return False, "research_gate: K 线重叠过高"
    if float(f.get("vol_z") or 0) < VOL_Z_MIN:
        return False, "research_gate: 量能不确认"
    return True, ""
