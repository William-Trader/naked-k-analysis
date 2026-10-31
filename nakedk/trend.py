"""Transparent trend score (0-100) and multi-timeframe alignment.

The score is descriptive, not predictive: it summarises EMA alignment,
ADX strength, range position and 24h momentum. It is intentionally
simple so a trader can audit every component.
"""
from __future__ import annotations


def _clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def trend_score(f: dict, params: dict | None = None) -> dict:
    p = params or {}
    adx_trend = p.get("trend_adx_trend", 20.0)
    up = p.get("trend_label_up", 60.0)
    down = p.get("trend_label_down", 40.0)
    sup = p.get("trend_label_strong_up", 75.0)
    sdown = p.get("trend_label_strong_down", 25.0)

    e20 = f.get("ema20")
    e50 = f.get("ema50")
    p = f.get("price")
    adx = f.get("adx14") or 0.0
    pos = f.get("pos20")
    ret24 = f.get("ret24h") or 0.0
    adx_slope = f.get("adx_slope") or 0.0
    ema_slope = f.get("ema_slope") or 0.0

    if e20 is None or e50 is None or p is None:
        return {"score": 50, "label": "neutral", "always_in": "neutral",
                "components": {"ema": 0, "adx": 0, "pos": 0, "mom": 0}}

    ema = 1.0 if (e20 > e50 and p > e20) else (-1.0 if (e20 < e50 and p < e20) else 0.0)
    strength = _clamp((adx - 15.0) / 25.0, 0.0, 1.0)  # 0 at 15, 1 at 40
    pos_s = (_clamp(pos if pos is not None else 0.5) - 0.5) * 2.0
    mom = _clamp(ret24 / 3.0, -1.0, 1.0)

    slope = 0.0
    if ema:
        slope += 5.0 if (ema > 0 and ema_slope > 0) or (ema < 0 and ema_slope < 0) else -5.0
    if adx_slope >= 2:
        slope += 3.0
    elif adx_slope <= -2:
        slope -= 3.0
    score = 50.0 + 20.0 * ema * strength + 10.0 * pos_s + 10.0 * mom + slope
    score = _clamp(score)
    if adx < adx_trend:
        score = 50.0 + (score - 50.0) * 0.4

    if score >= sup:
        label = "strong_up"
    elif score >= up:
        label = "up"
    elif score > down:
        label = "neutral"
    elif score > sdown:
        label = "down"
    else:
        label = "strong_down"

    always_in = "long" if score >= up else ("short" if score <= down else "neutral")
    return {
        "score": round(score, 1),
        "label": label,
        "always_in": always_in,
        "components": {
            "ema": round(ema, 2),
            "adx": round(strength, 2),
            "pos": round(pos_s, 2),
            "mom": round(mom, 2),
            "slope": round(slope, 1),
        },
    }
