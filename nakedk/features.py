# -----------------------------------------------------------------
# nakedk/features.py - naked-k-analysis core price-action engine
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-05747093
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
"""Technical primitives for price-action analysis (stdlib only).

All functions operate on plain Python sequences so the package stays
dependency-free. Kline rows follow the Binance REST shape:
[openTime, open, high, low, close, volume, ...].
"""
from __future__ import annotations

import math
from typing import Sequence


def _f(x) -> float:
    return float(x)


def ema(values: Sequence[float], period: int) -> float:
    if not values:
        raise ValueError("ema: empty series")
    if period <= 0:
        raise ValueError("ema: period must be positive")
    k = 2.0 / (period + 1.0)
    out = _f(values[0])
    for v in values[1:]:
        out = _f(v) * k + out * (1.0 - k)
    return out


def rsi(closes: Sequence[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = _f(closes[i]) - _f(closes[i - 1])
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
    if al == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + ag / al)


def true_ranges(highs, lows, closes) -> list[float]:
    out = []
    for i in range(1, len(closes)):
        out.append(max(
            _f(highs[i]) - _f(lows[i]),
            abs(_f(highs[i]) - _f(closes[i - 1])),
            abs(_f(lows[i]) - _f(closes[i - 1])),
        ))
    return out


def atr(highs, lows, closes, period: int = 14) -> float | None:
    tr = true_ranges(highs, lows, closes)
    if len(tr) < period:
        return None
    value = sum(tr[:period]) / period
    for x in tr[period:]:
        value = (value * (period - 1) + x) / period
    return value


def adx(highs, lows, closes, period: int = 14) -> float | None:
    if len(closes) < period * 2 + 2:
        return None
    tr, pdm, ndm = [], [], []
    for i in range(1, len(closes)):
        up = _f(highs[i]) - _f(highs[i - 1])
        dn = _f(lows[i - 1]) - _f(lows[i])
        pdm.append(up if (up > dn and up > 0) else 0.0)
        ndm.append(dn if (dn > up and dn > 0) else 0.0)
        tr.append(max(
            _f(highs[i]) - _f(lows[i]),
            abs(_f(highs[i]) - _f(closes[i - 1])),
            abs(_f(lows[i]) - _f(closes[i - 1])),
        ))
    a = sum(tr[:period]) / period
    p = sum(pdm[:period]) / period
    m = sum(ndm[:period]) / period
    dxs = []
    for i in range(period, len(tr)):
        a = (a * (period - 1) + tr[i]) / period
        p = (p * (period - 1) + pdm[i]) / period
        m = (m * (period - 1) + ndm[i]) / period
        pdi = 100.0 * p / a if a else 0.0
        mdi = 100.0 * m / a if a else 0.0
        dxs.append(0.0 if (pdi + mdi) == 0 else 100.0 * abs(pdi - mdi) / (pdi + mdi))
    if not dxs:
        return None
    value = sum(dxs[:period]) / period if len(dxs) >= period else sum(dxs) / len(dxs)
    for d in dxs[period:]:
        value = (value * (period - 1) + d) / period
    return value


def volume_z(volumes: Sequence[float], lookback: int = 42) -> float:
    base = [_f(v) for v in volumes[-lookback:-1]]
    if len(base) < 3:
        return 0.0
    mu = sum(base) / len(base)
    sd = math.sqrt(sum((v - mu) ** 2 for v in base) / len(base))
    return 0.0 if sd == 0 else (_f(volumes[-1]) - mu) / sd


def swing_points(highs, lows, window: int = 2, keep: int = 3):
    sh, sl = [], []
    for i in range(window, len(highs) - window):
        if _f(highs[i]) == max(_f(x) for x in highs[i - window:i + window + 1]):
            sh.append(_f(highs[i]))
        if _f(lows[i]) == min(_f(x) for x in lows[i - window:i + window + 1]):
            sl.append(_f(lows[i]))
    return sh[-keep:], sl[-keep:]


def range_position(highs, lows, closes, lookback: int):
    hh = max(_f(x) for x in highs[-lookback:])
    ll = min(_f(x) for x in lows[-lookback:])
    c = _f(closes[-1])
    return ll, hh, (0.5 if hh == ll else (c - ll) / (hh - ll))


def pct_change(closes, bars: int) -> float:
    if len(closes) <= bars:
        return 0.0
    prev = _f(closes[-bars - 1])
    return 0.0 if prev == 0 else (_f(closes[-1]) / prev - 1.0) * 100.0


def features_from_klines(k4) -> dict:
    """Compute the 4h feature set from Binance kline rows."""
    if len(k4) < 60:
        raise ValueError("need at least 60 4h candles")
    highs = [_f(r[2]) for r in k4]
    lows = [_f(r[3]) for r in k4]
    closes = [_f(r[4]) for r in k4]
    vols = [_f(r[5]) for r in k4]
    price = closes[-1]
    e20 = ema(closes[-120:], 20)
    e50 = ema(closes[-160:] if len(closes) >= 160 else closes, 50)
    a = atr(highs, lows, closes, 14)
    ad = adx(highs, lows, closes, 14)
    r = rsi(closes, 14)
    lo20, hi20, p20 = range_position(highs, lows, closes, 20)
    lo40, hi40, p40 = range_position(highs, lows, closes, 40)
    sh, sl = swing_points(highs, lows)
    return {
        "price": price,
        "ema20": e20,
        "ema50": e50,
        "adx14": ad,
        "rsi14": r,
        "atr14": a,
        "atr_pct": (a / price * 100.0) if a and price else None,
        "vol_z": volume_z(vols),
        "r20_lo": lo20, "r20_hi": hi20, "pos20": p20,
        "r40_lo": lo40, "r40_hi": hi40, "pos40": p40,
        "swing_highs": sh, "swing_lows": sl,
        "ret4h": pct_change(closes, 1),
        "ret24h": pct_change(closes, 6),
        "ret72h": pct_change(closes, 18),
        "trend": ("up" if e20 > e50 and price > e20 else
                  "down" if e20 < e50 and price < e20 else "mixed"),
    }
