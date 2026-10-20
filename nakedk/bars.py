"""Per-bar structural encoding: body, tails, close position, bar type."""
from __future__ import annotations

import time

INTERVAL_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000,
               "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}


def _f(x):
    return float(x)


def closed_bars(ks, interval: str = "4h", now_ms=None):
    """Drop the still-forming bar: signals must use closed candles only."""
    if not ks:
        return []
    step = INTERVAL_MS.get(interval)
    if not step:
        return list(ks)
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    out = [k for k in ks if int(k[0]) + step <= now]
    return out or list(ks)


def _atr(highs, lows, closes, n: int = 14) -> float:
    trs = []
    for i in range(1, len(closes)):
        trs.append(max(highs[i] - lows[i],
                       abs(highs[i] - closes[i - 1]),
                       abs(lows[i] - closes[i - 1])))
    if not trs:
        return 1.0
    tail = trs[-n:]
    return sum(tail) / len(tail) or 1.0


def _classify(p, prev) -> str:
    rng_atr = p.get("range_atr") or 0.0
    vz = p.get("vol_z") or 0.0
    br = p["body_ratio"]
    cp = p["close_pos"]
    if rng_atr >= 2.0 and vz >= 2.0:
        return "climax"
    if prev and p["h"] > prev["h"] and p["l"] < prev["l"]:
        return "outside"
    if prev and p["h"] < prev["h"] and p["l"] > prev["l"]:
        return "inside"
    if br <= 0.25:
        return "doji"
    if br >= 0.6 and abs(cp - 0.5) >= 0.2:
        return "trend_bull" if p["c"] > p["o"] else "trend_bear"
    if p["lower_tail"] >= 2 * br and cp <= 0.3:
        return "reversal_bull"
    if p["upper_tail"] >= 2 * br and cp >= 0.7:
        return "reversal_bear"
    return "normal"


def _base(k, prev, atr, vol_z) -> dict:
    o, h, l, c, v = _f(k[1]), _f(k[2]), _f(k[3]), _f(k[4]), _f(k[5])
    rng = h - l
    body = abs(c - o)
    br = body / rng if rng > 0 else 0.0
    cp = (c - l) / rng if rng > 0 else 0.5
    upper = (h - max(o, c)) / rng if rng > 0 else 0.0
    lower = (min(o, c) - l) / rng if rng > 0 else 0.0
    overlap = 0.0
    if prev and rng > 0:
        overlap = max(0.0, min(h, prev["h"]) - max(l, prev["l"])) / rng
    p = {
        "ts": int(k[0]), "o": o, "h": h, "l": l, "c": c, "v": v,
        "range": rng, "body": body,
        "body_ratio": round(br, 3), "close_pos": round(cp, 3),
        "upper_tail": round(upper, 3), "lower_tail": round(lower, 3),
        "range_atr": round(rng / atr, 2) if atr else None,
        "body_atr": round(body / atr, 2) if atr else None,
        "overlap_prev": round(overlap, 3),
        "gap": round(o - prev["c"], 4) if prev else 0.0,
        "vol_z": round(vol_z, 2),
    }
    p["type"] = _classify(p, prev)
    clarity = (40 * br + 40 * abs(cp - 0.5) * 2
               + 20 * min(1.0, (p["range_atr"] or 1.0) / 1.5))
    p["quality"] = int(max(0, min(100, round(clarity))))
    return p


def profile_series(ks, atr=None) -> list:
    """Return one profile dict per bar (oldest first)."""
    if not ks:
        return []
    highs = [_f(k[2]) for k in ks]
    lows = [_f(k[3]) for k in ks]
    closes = [_f(k[4]) for k in ks]
    vols = [_f(k[5]) for k in ks]
    if atr is None:
        atr = _atr(highs, lows, closes)
    out = []
    for i, k in enumerate(ks):
        prev = out[-1] if out else None
        window = vols[max(0, i - 42):i] or vols[:1]
        mu = sum(window) / len(window)
        sd = (sum((x - mu) ** 2 for x in window) / len(window)) ** 0.5 or 1.0
        out.append(_base(k, prev, atr, (vols[i] - mu) / sd))
    return out


def last_profile(ks, atr=None) -> dict:
    rows = profile_series(ks, atr)
    return rows[-1] if rows else {}

