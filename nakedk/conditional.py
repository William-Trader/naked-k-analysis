# -----------------------------------------------------------------
# nakedk/conditional.py - naked-k-analysis conditional edge
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-09E59DB8
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
# -*- coding: utf-8 -*-
"""Conditional edge: order-flow / funding / OI as *conditions*, not forecasts.

The state machine (structure, trend, regime) describes *where price is*; it
does not predict direction (docs/OPTIMIZE.md, BACKTEST.md). Order-flow, funding
and OI are the next honest dimension: instead of a hard directional switch,
report the condition and its empirical historical hit rate, with the same
Wilson-interval + min-sample discipline as analogs.py.

Three pure parts (all testable without network):
  1. classify_flow      — bullish/bearish divergence from price vs cumulative
                          taker delta (computed from OHLCV, so it is backtestable).
  2. classify_funding   — funding crowding (needs funding history; realtime only).
  3. classify_oi        — OI divergence (realtime only).

The empirical part builds a next-bar probability table bucketed by flow
divergence, because that is the only order-flow signal reconstructable from
kline history alone.
"""
from __future__ import annotations

import math


def classify_flow(price_chg: float, cum_delta: float) -> str:
    """bullish / bearish / none from price move vs cumulative taker delta."""
    if price_chg > 0.5 and cum_delta < 0:
        return "bearish"     # price up on net selling -> distribution
    if price_chg < -0.5 and cum_delta > 0:
        return "bullish"     # price down on net buying -> absorption
    return "none"


def classify_funding(rate: float | None, threshold: float = 0.1) -> str:
    """Funding crowding. threshold in % (0.1 = 0.1% per 8h)."""
    if rate is None:
        return "unknown"
    if rate >= threshold:
        return "extreme_long"
    if rate <= -threshold:
        return "extreme_short"
    return "neutral"


def classify_oi(price_chg: float, oi_chg: float | None) -> str:
    """OI divergence: price up + OI down = short-covering (weak), etc."""
    if oi_chg is None:
        return "unknown"
    if price_chg > 0.5 and oi_chg < -1.0:
        return "short_covering"
    if price_chg < -0.5 and oi_chg < -1.0:
        return "long_unwind"
    if price_chg > 0.5 and oi_chg > 1.0:
        return "new_longs"
    if price_chg < -0.5 and oi_chg > 1.0:
        return "new_shorts"
    return "neutral"


def conditions(f: dict, flow: dict | None = None,
               derivs: dict | None = None) -> dict:
    """Combine flow/funding/OI into a condition tag for the analysis chain."""
    flow = flow or {}
    derivs = derivs or {}
    fl = classify_flow(flow.get("price_chg", 0.0), flow.get("cum_delta", 0.0))
    fu = classify_funding(derivs.get("funding_rate"))
    oi = classify_oi(flow.get("price_chg", 0.0), derivs.get("oi_change_24h"))
    return {"flow": fl, "funding": fu, "oi": oi}


def _wilson(k, n, z=1.96):
    if n == 0:
        return [0.0, 100.0]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, 100 * (c - h)), 1), round(min(1.0, 100 * (c + h)), 1)]


def build_flow_prob(ks, horizon: int = 1, warmup: int = 60, lookback: int = 300):
    """Empirical next-bar direction bucketed by order-flow divergence.

    Reconstructs per-bar cumulative delta from OHLCV (flow.analyse) and labels
    the next bar's move. Returns {divergence: {n, p_up, p_down, wilson_up}}.
    Only the OHLCV-reconstructable signal is included; funding/OI need their
    own history feed and are deliberately excluded.
    """
    from .features import features_from_klines
    from .flow import analyse as flow_analyse
    table = {}
    start = max(warmup, len(ks) - lookback)
    for i in range(start, len(ks) - horizon):
        window = ks[:i + 1][-60:]
        if len(window) < 20:
            continue
        fl = flow_analyse(window)
        if not fl:
            continue
        cond = fl.get("divergence", "none")
        raw = (float(ks[i + horizon][4]) / float(ks[i][4]) - 1.0) * 100.0
        d = "up" if raw > 0.1 else ("down" if raw < -0.1 else "flat")
        row = table.setdefault(cond, {"n": 0, "up": 0, "down": 0, "flat": 0})
        row["n"] += 1
        row[d] += 1
    for row in table.values():
        n = row["n"]
        row["p_up"] = round(100.0 * row["up"] / n, 1) if n else None
        row["p_down"] = round(100.0 * row["down"] / n, 1) if n else None
        row["wilson_up"] = _wilson(row["up"], n)
        row["wilson_down"] = _wilson(row["down"], n)
    return table
