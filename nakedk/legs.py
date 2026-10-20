"""Leg decomposition and trend maturity (Brooks: legs, not bars)."""
from __future__ import annotations

from .structure import zigzag


def decompose(highs, lows, atr_value, mult: float = 0.5) -> list:
    if not atr_value or len(highs) < 10:
        return []
    piv = zigzag(highs, lows, atr_value, mult)
    out = []
    for a, b in zip(piv, piv[1:]):
        delta = b["p"] - a["p"]
        out.append({
            "from_i": a["i"], "to_i": b["i"],
            "from_p": a["p"], "to_p": b["p"],
            "dir": "up" if delta > 0 else "down",
            "delta_atr": round(delta / atr_value, 2),
            "bars": b["i"] - a["i"],
        })
    return out


def maturity(legs: list) -> int:
    if not legs:
        return 0
    d = legs[-1]["dir"]
    count = 0
    for leg in reversed(legs):
        if leg["dir"] == d:
            count += 1
        else:
            break
    return count


def exhaustion(legs: list, ratio: float = 0.7) -> bool:
    if not legs:
        return False
    same = [l for l in legs if l["dir"] == legs[-1]["dir"]]
    if len(same) < 2:
        return False
    return abs(same[-1]["delta_atr"]) < ratio * abs(same[-2]["delta_atr"])
