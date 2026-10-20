"""Volatility structure: ATR percentile, expansion/contraction, realised vol."""
from __future__ import annotations

import math


def _trs(highs, lows, closes):
    return [max(highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])) for i in range(1, len(closes))]


def analyse(highs, lows, closes, period: int = 14, bars_per_year: float = 2190) -> dict:
    if len(closes) < period + 5:
        return {}
    trs = _trs(highs, lows, closes)
    atrs = [sum(trs[i - period + 1:i + 1]) / period
            for i in range(period - 1, len(trs))]
    if not atrs:
        return {}
    last = atrs[-1]
    hist = atrs[:-1] or atrs
    pct = 100.0 * sum(1 for x in hist if x <= last) / len(hist)
    long_atr = sum(hist[-50:]) / len(hist[-50:]) if hist else last
    ratio = last / long_atr if long_atr else 1.0
    if ratio >= 1.25:
        state = "expansion"
    elif ratio <= 0.80:
        state = "contraction"
    else:
        state = "normal"
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))
            if closes[i - 1] > 0]
    tail = rets[-min(len(rets), 30):]
    mu = sum(tail) / len(tail) if tail else 0.0
    sd = (sum((r - mu) ** 2 for r in tail) / len(tail)) ** 0.5 if tail else 0.0
    rv = sd * math.sqrt(bars_per_year) * 100.0
    return {"atr_percentile": round(pct, 1), "ratio": round(ratio, 2),
            "state": state, "rv": round(rv, 1), "atr": round(last, 4)}

