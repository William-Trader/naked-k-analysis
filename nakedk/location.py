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


def plan_from_context(price, direction, struct, atr, rr_min: float = 1.5,
                      risk_pct: float = 0.5, ttl_h: int = 8):
    """Executable plan with one source of truth; nearest valid target wins."""
    if direction not in ("bullish", "bearish") or not price or not atr:
        return None
    lv = (struct or {}).get("levels", {})
    side = "long" if direction == "bullish" else "short"
    if side == "long":
        struct_stop = lv.get("swing_low")
        stop = (struct_stop if struct_stop and price - struct_stop <= 2.0 * atr
                else price - 1.5 * atr)
        stop = min(stop, price - 0.8 * atr)
        risk = price - stop
        candidates = []
        if lv.get("swing_high") and lv["swing_high"] > price:
            candidates.append(("structure", float(lv["swing_high"])))
        candidates += [("atr_2.5r", price + 2.5 * risk), ("atr_3r", price + 3.0 * risk)]
    else:
        struct_stop = lv.get("swing_high")
        stop = (struct_stop if struct_stop and struct_stop - price <= 2.0 * atr
                else price + 1.5 * atr)
        stop = max(stop, price + 0.8 * atr)
        risk = stop - price
        candidates = []
        if lv.get("swing_low") and lv["swing_low"] < price:
            candidates.append(("structure", float(lv["swing_low"])))
        candidates += [("atr_2.5r", price - 2.5 * risk), ("atr_3r", price - 3.0 * risk)]
    if risk <= 0:
        return None
    best = None
    for basis, target in candidates:
        dist = (target - price) if side == "long" else (price - target)
        if dist <= 0:
            continue
        rr = dist / risk
        if rr < rr_min:
            continue
        if best is None or rr < best[0]:
            best = (rr, basis, target)
    if best is None:
        return None
    rr, basis, target = best
    stop_pct = risk / price * 100.0
    notional = min(200.0, risk_pct / stop_pct * 100.0) if stop_pct else 0.0
    return {"side": side, "entry": round(price, 2), "stop": round(stop, 2),
            "target": round(target, 2), "rr": round(rr, 2), "basis": basis,
            "stop_pct": round(stop_pct, 2), "risk_pct": risk_pct,
            "notional_pct": round(notional, 1), "ttl_h": ttl_h,
            "invalidate": "4h收盘" + ("<" if side == "long" else ">") + f" {round(stop, 2)}"}


def measured_move(pattern_height: float, breakout_level: float, direction: str):
    if not pattern_height or not breakout_level:
        return None
    if direction == "long":
        return round(breakout_level + pattern_height, 2)
    if direction == "short":
        return round(breakout_level - pattern_height, 2)
    return None

