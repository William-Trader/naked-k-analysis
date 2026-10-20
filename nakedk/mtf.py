"""Multi-timeframe alignment across 1d / 4h / 1h."""
from __future__ import annotations

from .bars import closed_bars
from .features import ema


def tf_sign(ks) -> int:
    """+1 aligned up, -1 aligned down, 0 no clear alignment."""
    if not ks or len(ks) < 60:
        return 0
    closes = [float(k[4]) for k in ks]
    e20 = ema(closes[-120:], 20)
    e50 = ema(closes, 50)
    if e20 is None or e50 is None:
        return 0
    price = closes[-1]
    if price > e20 > e50:
        return 1
    if price < e20 < e50:
        return -1
    return 0


def alignment(symbol: str, klines_fn=None, now_ms=None) -> dict:
    if klines_fn is None:
        from .fetch import klines as klines_fn
    by = {}
    for tf, limit in (("1d", 120), ("4h", 200), ("1h", 200)):
        try:
            by[tf] = tf_sign(closed_bars(klines_fn(symbol, tf, limit), tf, now_ms))
        except Exception:
            by[tf] = 0
    total = sum(by.values())
    if total >= 2:
        label = "aligned_up"
    elif total <= -2:
        label = "aligned_down"
    elif total == 0:
        label = "neutral"
    else:
        label = "mixed"
    return {"by_tf": by, "alignment": total, "label": label}

