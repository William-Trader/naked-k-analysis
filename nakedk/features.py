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
    """SMA-seeded EMA: deterministic regardless of how much history is passed."""
    if not values:
        raise ValueError("ema: empty series")
    if period <= 0:
        raise ValueError("ema: period must be positive")
    vals = [_f(v) for v in values]
    k = 2.0 / (period + 1.0)
    if len(vals) < period:
        out = vals[0]
        for v in vals[1:]:
            out = v * k + out * (1.0 - k)
        return out
    out = sum(vals[:period]) / period
    for v in vals[period:]:
        out = v * k + out * (1.0 - k)
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


def adx_series(highs, lows, closes, period: int = 14) -> list:
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
        return []
    out = []
    value = sum(dxs[:period]) / period if len(dxs) >= period else sum(dxs) / len(dxs)
    out.append(value)
    for d in dxs[period:]:
        value = (value * (period - 1) + d) / period
        out.append(value)
    return out


def adx(highs, lows, closes, period: int = 14):
    series = adx_series(highs, lows, closes, period)
    return series[-1] if series else None


def overlap_ratio(highs, lows, lookback: int = 20) -> float:
    """Average bar overlap: high overlap = range, low overlap = trend."""
    vals = []
    start = max(1, len(highs) - lookback)
    for i in range(start, len(highs)):
        rng = _f(highs[i]) - _f(lows[i])
        if rng <= 0:
            continue
        ov = min(_f(highs[i]), _f(highs[i - 1])) - max(_f(lows[i]), _f(lows[i - 1]))
        vals.append(max(0.0, ov) / rng)
    return sum(vals) / len(vals) if vals else 0.0


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def volume_z(volumes: Sequence[float], lookback: int = 42) -> float:
    """Robust z on log volume (median/MAD): heavy tails do not poison the baseline."""
    base = [math.log1p(max(0.0, _f(v))) for v in volumes[-lookback:-1]]
    if len(base) < 5:
        return 0.0
    med = _median(base)
    mad = _median([abs(x - med) for x in base])
    scale = 1.4826 * mad
    if scale == 0:
        mu = sum(base) / len(base)
        scale = math.sqrt(sum((x - mu) ** 2 for x in base) / len(base))
    if scale == 0:
        return 0.0
    return (math.log1p(max(0.0, _f(volumes[-1]))) - med) / scale


def swing_points(highs, lows, window: int = 2, keep: int = 3, atr_value=None):
    """ATR-thresholded swings, the same definition structure.py uses for plans."""
    if len(highs) < 5:
        return [], []
    if atr_value is None:
        atr_value = sum(_f(h) - _f(l) for h, l in zip(highs, lows)) / len(highs)
    try:
        from .structure import zigzag
        piv = zigzag([_f(x) for x in highs], [_f(x) for x in lows],
                     atr_value or 1.0, mult=0.5)
    except Exception:
        piv = []
    sh = [p["p"] for p in piv if p["kind"] == "H"][-keep:]
    sl = [p["p"] for p in piv if p["kind"] == "L"][-keep:]
    if not sh and not sl:
        sh = [_f(x) for x in highs[-keep:]]
        sl = [_f(x) for x in lows[-keep:]]
    return sh, sl


def swing_marks(highs, lows, atr_value=None, keep: int = 8):
    """Swing pivots with indices, so UI and PLAN share one source."""
    if len(highs) < 5:
        return {"highs": [], "lows": []}
    try:
        from .structure import zigzag
        piv = zigzag([_f(x) for x in highs], [_f(x) for x in lows],
                     atr_value or 1.0, mult=0.5)
    except Exception:
        piv = []
    hs = [{"i": p["i"], "p": p["p"]} for p in piv if p["kind"] == "H"][-keep:]
    ls = [{"i": p["i"], "p": p["p"]} for p in piv if p["kind"] == "L"][-keep:]
    return {"highs": hs, "lows": ls}


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
    e20 = ema(closes, 20)
    e50 = ema(closes, 50)
    a = atr(highs, lows, closes, 14)
    ad_series = adx_series(highs, lows, closes, 14)
    ad = ad_series[-1] if ad_series else None
    adx_slope = (ad_series[-1] - ad_series[-6]) if len(ad_series) >= 6 else 0.0
    e20_prev = ema(closes[:-5], 20) if len(closes) > 25 else e20
    ema_slope = ((e20 - e20_prev) / a) if (a and e20_prev) else 0.0
    r = rsi(closes, 14)
    lo20, hi20, p20 = range_position(highs, lows, closes, 20)
    lo40, hi40, p40 = range_position(highs, lows, closes, 40)
    sh, sl = swing_points(highs, lows, atr_value=a)
    marks = swing_marks(highs, lows, atr_value=a)
    return {
        "price": price,
        "ema20": e20,
        "ema50": e50,
        "adx14": ad,
        "adx_slope": round(adx_slope, 2),
        "ema_slope": round(ema_slope, 3),
        "overlap": round(overlap_ratio(highs, lows), 3),
        "rsi14": r,
        "atr14": a,
        "atr_pct": (a / price * 100.0) if a and price else None,
        "vol_z": volume_z(vols),
        "r20_lo": lo20, "r20_hi": hi20, "pos20": p20,
        "r40_lo": lo40, "r40_hi": hi40, "pos40": p40,
        "swing_highs": sh, "swing_lows": sl, "swing_marks": marks,
        "ret4h": pct_change(closes, 1),
        "ret24h": pct_change(closes, 6),
        "ret72h": pct_change(closes, 18),
        "trend": ("up" if e20 > e50 and price > e20 else
                  "down" if e20 < e50 and price < e20 else "mixed"),
    }
