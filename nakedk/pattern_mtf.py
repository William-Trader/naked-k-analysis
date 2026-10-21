"""Multi-timeframe pattern confluence: 1d context vs 4h trigger."""
from __future__ import annotations


def confluence(h4, d1, regime=None):
    if not h4:
        return {"align": "none", "score": 0, "h4_dir": None, "d1_dir": None}
    d4 = h4.get("direction")
    d1d = (d1 or {}).get("direction")
    align, score = "none", 0
    if d4 in ("bullish", "bearish") and d1d in ("bullish", "bearish"):
        if d1d == d4:
            align, score = "same", 2
        else:
            align, score = "conflict", -1
    if regime in ("up", "down") and d4 in ("bullish", "bearish"):
        want = "bullish" if regime == "up" else "bearish"
        score += 1 if d4 == want else -1
    return {"align": align, "score": max(-2, min(3, score)),
            "h4_dir": d4, "d1_dir": d1d}


def apply(primary, conf):
    if not primary or not conf:
        return primary
    s = conf.get("score") or 0
    if s:
        primary["score"] = round(primary["score"] * (1 + 0.08 * s), 1)
        primary["mtf_confluence"] = s
    return primary
