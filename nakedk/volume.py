"""Volume-price context: VPOC/value area, effort-vs-result, divergence."""
from __future__ import annotations


def vpoc(ks, buckets: int = 24) -> dict:
    """Approximate volume profile from OHLCV bars."""
    if not ks:
        return {}
    highs = [float(k[2]) for k in ks]
    lows = [float(k[3]) for k in ks]
    closes = [float(k[4]) for k in ks]
    vols = [float(k[5]) for k in ks]
    lo, hi = min(lows), max(highs)
    if hi <= lo:
        return {}
    step = (hi - lo) / buckets
    acc = [0.0] * buckets
    for h, l, c, v in zip(highs, lows, closes, vols):
        typical = (h + l + c) / 3.0
        idx = min(buckets - 1, max(0, int((typical - lo) / step)))
        acc[idx] += v
    total = sum(acc) or 1.0
    poc_i = max(range(buckets), key=lambda i: acc[i])
    order = sorted(range(buckets), key=lambda i: acc[i], reverse=True)
    chosen, cum = [], 0.0
    for i in order:
        chosen.append(i)
        cum += acc[i]
        if cum / total >= 0.70:
            break
    return {
        "poc": round(lo + step * (poc_i + 0.5), 2),
        "value_area": [round(lo + step * min(chosen), 2),
                       round(lo + step * (max(chosen) + 1), 2)],
        "hvn": [round(lo + step * (i + 0.5), 2) for i in order[:3]],
        "buckets": buckets,
    }


def effort_result(bar: dict) -> str:
    if not bar:
        return "unknown"
    vz = bar.get("vol_z") or 0.0
    br = bar.get("body_ratio") or 0.0
    ra = bar.get("range_atr") or 0.0
    if vz >= 2 and br <= 0.3:
        return "absorption"
    if vz >= 2 and br >= 0.6:
        return "expansion"
    if vz <= 0.8 and ra >= 1.5:
        return "thin_move"
    if vz <= -1 and br >= 0.6:
        return "low_volume_drift"
    return "normal"


def divergence(bars, lookback: int = 20):
    """Price makes a new extreme without matching volume."""
    if not bars or len(bars) < lookback + 2:
        return None
    last = bars[-1]
    window = bars[-lookback - 1:-1]
    max_high = max(b["h"] for b in window)
    min_low = min(b["l"] for b in window)
    if last["h"] > max_high:
        ref = max(window, key=lambda b: b["h"])
        if (last.get("vol_z") or 0) < (ref.get("vol_z") or 0) - 0.5:
            return "bearish"
    if last["l"] < min_low:
        ref = min(window, key=lambda b: b["l"])
        if (last.get("vol_z") or 0) < (ref.get("vol_z") or 0) - 0.5:
            return "bullish"
    return None

