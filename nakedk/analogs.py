"""Empirical next-bar direction probabilities by regime/ADX/position."""
from __future__ import annotations

import math

from .features import features_from_klines


def _wilson(k, n, z=1.96):
    if n == 0:
        return [0.0, 100.0]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, 100 * (c - h)), 1), round(min(1.0, 100 * (c + h)), 1)]


def bucket(f):
    adx = f.get("adx14") or 0.0
    pos = f.get("pos20")
    pos = 0.5 if pos is None else pos
    if f["ema20"] > f["ema50"] and f["price"] > f["ema20"]:
        regime = "up"
    elif f["ema20"] < f["ema50"] and f["price"] < f["ema20"]:
        regime = "down"
    else:
        regime = "range"
    a = "low" if adx < 20 else ("mid" if adx < 30 else "high")
    p = "low" if pos < 0.3 else ("high" if pos > 0.7 else "mid")
    return regime + "|" + a + "|" + p


def build(ks, horizon: int = 1, warmup: int = 60, lookback: int = 300):
    table = {}
    start = max(warmup, len(ks) - lookback)
    for i in range(start, len(ks) - horizon):
        try:
            f = features_from_klines(ks[:i + 1][-200:])
        except ValueError:
            continue
        if not f.get("adx14"):
            continue
        key = bucket(f)
        raw = (float(ks[i + horizon][4]) / float(ks[i][4]) - 1.0) * 100.0
        d = "up" if raw > 0.1 else ("down" if raw < -0.1 else "flat")
        row = table.setdefault(key, {"n": 0, "up": 0, "down": 0, "flat": 0})
        row["n"] += 1
        row[d] += 1
    for row in table.values():
        n = row["n"]
        row["p_up"] = round(100.0 * row["up"] / n, 1) if n else None
        row["p_down"] = round(100.0 * row["down"] / n, 1) if n else None
        row["p_flat"] = round(100.0 * row["flat"] / n, 1) if n else None
        row["wilson_up"] = _wilson(row["up"], n)
    return table
