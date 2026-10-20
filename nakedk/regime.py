"""Regime arbitration: one answer instead of four definitions."""
from __future__ import annotations


def _norm(state):
    return state if state in ("up", "down", "range", "transition") else None


def arbitrate(state4h, state1d, mtf_alignment, adx=None, adx_slope=None, overlap=None):
    """Precedence: 1d structure > 4h structure > EMA alignment."""
    s1, s4 = _norm(state1d), _norm(state4h)
    notes = []
    if s1 and s4 and s1 == s4 and s1 in ("up", "down"):
        regime, conf = s1, 70.0
        if adx and adx >= 25:
            conf += 10
        if adx_slope and adx_slope > 2:
            conf += 5
        elif adx_slope and adx_slope < -2:
            conf -= 10
            notes.append("ADX 走弱")
    elif s1 and s4 and {s1, s4} == {"up", "down"}:
        regime, conf = "transition", 40.0
        notes.append(f"1d={s1} 与 4h={s4} 相反")
    elif s4 in ("up", "down"):
        regime, conf = s4, 55.0
        notes.append("仅 4h 结构确认")
    elif s1 in ("up", "down", "range"):
        regime, conf = s1, 50.0
        notes.append("以 1d 结构为准")
    else:
        regime = "range" if (overlap is not None and overlap > 0.55) else "transition"
        conf = 45.0
        notes.append("无结构确认")
    if overlap is not None and overlap > 0.6 and regime in ("up", "down"):
        conf -= 10
        notes.append("K线重叠高，趋势不干净")
    if adx is not None and adx < 20:
        conf = min(conf, 45.0)
        notes.append("ADX<20")
    conflict = bool(s1 and s4 and {s1, s4} == {"up", "down"})
    if not conflict and mtf_alignment is not None:
        if (regime == "down" and mtf_alignment >= 2) or (regime == "up" and mtf_alignment <= -2):
            conflict = True
            notes.append("MTF 与结构冲突")
    return {"regime": regime, "confidence": round(max(0.0, min(100.0, conf)), 1),
            "conflict": conflict, "notes": notes}
