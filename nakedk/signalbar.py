"""Direction-aware signal-bar quality: six weighted dimensions."""
from __future__ import annotations


def _band(v, lo, hi):
    if v <= lo:
        return 0.0
    if v >= hi:
        return 1.0
    return (v - lo) / (hi - lo)


def score(bar: dict, prev, direction: str, pos20=None) -> dict:
    """0-100 signal-bar score plus the missing pieces, not a boolean."""
    if not bar or direction not in ("long", "short"):
        return {"score": 0, "parts": {}, "missing": ["no bar or direction"]}
    parts, missing = {}, []
    cp = bar.get("close_pos", 0.5)
    br = bar.get("body_ratio", 0.0)
    if direction == "long":
        parts["close_pos"] = 25 * _band(cp, 0.45, 0.80)
        parts["tail"] = 15 * (1 - _band(bar.get("lower_tail", 0.0), 0.15, 0.45))
        want = "trend_bull"
    else:
        parts["close_pos"] = 25 * _band(1 - cp, 0.45, 0.80)
        parts["tail"] = 15 * (1 - _band(bar.get("upper_tail", 0.0), 0.15, 0.45))
        want = "trend_bear"
    parts["body"] = 20 * _band(br, 0.30, 0.65)
    ctx = 0.0
    if prev:
        same_dir = (prev.get("c", 0) > prev.get("o", 0)) == (direction == "long")
        if prev.get("type") == want:
            ctx = 15.0
        elif same_dir and (prev.get("body_ratio") or 0) >= 0.5:
            ctx = 10.0
        elif prev.get("type") in ("doji", "inside"):
            ctx = 5.0
    parts["context"] = ctx
    if pos20 is None:
        parts["location"] = 7.0
    else:
        parts["location"] = 15 * _band(abs(pos20 - 0.5) * 2, 0.25, 0.85)
    parts["volume"] = 10 * _band(bar.get("vol_z") or 0.0, 0.5, 2.5)
    if direction == "long" and cp < 0.5:
        missing.append("收盘位置低于中点")
    if direction == "short" and cp > 0.5:
        missing.append("收盘位置高于中点")
    if br < 0.35:
        missing.append("实体过小")
    if prev and prev.get("type") != want and (prev.get("body_ratio") or 0) < 0.4:
        missing.append("前一根无跟随")
    total = sum(parts.values())
    return {
        "score": int(round(max(0.0, min(100.0, total)))),
        "parts": {k: round(v, 1) for k, v in parts.items()},
        "missing": missing,
    }

