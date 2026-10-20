"""Micro structure on lower timeframes (5m state, 1m impulse)."""
from __future__ import annotations

from .features import atr, ema
from .structure import structure


def analyse(ks5, ks1=None) -> dict:
    if not ks5 or len(ks5) < 60:
        return {}
    closes = [float(k[4]) for k in ks5]
    st = structure(ks5)
    e20 = ema(closes[-120:], 20)
    e50 = ema(closes, 50)
    sign = 1 if e20 and e50 and closes[-1] > e20 > e50 else (
        -1 if e20 and e50 and closes[-1] < e20 < e50 else 0)
    out = {"state5m": st.get("state"),
           "bos5m": (st.get("bos") or {}).get("kind"),
           "sign5m": sign}
    if ks1 and len(ks1) >= 20:
        c1 = [float(k[4]) for k in ks1]
        a1 = atr([float(k[2]) for k in ks1], [float(k[3]) for k in ks1], c1, 14)
        move = c1[-1] - c1[-6] if len(c1) >= 6 else 0.0
        out["impulse_1m"] = round(move / a1, 2) if a1 else 0.0
    return out

