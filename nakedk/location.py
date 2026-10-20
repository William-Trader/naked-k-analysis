"""Location context: distance to levels in ATR units, session levels."""
from __future__ import annotations


def atr_distance(price: float, level, atr) -> float | None:
    if not level or not atr:
        return None
    return round(abs(price - level) / atr, 2)


def edge_zone(pos20) -> str:
    if pos20 is None:
        return "unknown"
    if pos20 < 0.15:
        return "low"
    if pos20 > 0.85:
        return "high"
    return "middle"


def session_levels(daily_ks_or_rows) -> dict:
    """Previous completed daily high/low from 1d klines."""
    rows = daily_ks_or_rows or []
    if len(rows) < 2:
        return {}
    prev = rows[-2]
    return {"prev_day_high": round(float(prev[2]), 2),
            "prev_day_low": round(float(prev[3]), 2),
            "prev_day_close": round(float(prev[4]), 2)}


def measured_move(pattern_height: float, breakout_level: float, direction: str):
    if not pattern_height or not breakout_level:
        return None
    if direction == "long":
        return round(breakout_level + pattern_height, 2)
    if direction == "short":
        return round(breakout_level - pattern_height, 2)
    return None

