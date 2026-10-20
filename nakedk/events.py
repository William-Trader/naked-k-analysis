"""Failed breakouts and follow-through: the two core Brooks confirmations."""
from __future__ import annotations


def failed_break(ks, atr_value, lookback: int = 20, confirm_bars: int = 3):
    """A break that closes back inside the range: trapped traders, high-value reversal."""
    n = len(ks)
    if n < lookback + 2 or not atr_value:
        return None
    highs = [float(k[2]) for k in ks]
    lows = [float(k[3]) for k in ks]
    closes = [float(k[4]) for k in ks]
    lo = max(lookback - 1, n - 41)
    for j in range(n - 2, lo, -1):
        prior_hi = max(highs[j - lookback:j])
        prior_lo = min(lows[j - lookback:j])
        rng = highs[j] - lows[j]
        if rng <= 0:
            continue
        up_wick = (highs[j] - max(float(ks[j][1]), closes[j])) / rng
        if closes[j] > prior_hi + 0.2 * atr_value and up_wick >= 0.5:
            for k in range(1, confirm_bars + 1):
                if j + k < n and closes[j + k] < prior_hi:
                    return {"kind": "failed_break_up", "level": round(prior_hi, 2),
                            "bars_since": n - 1 - j}
        down_wick = (min(float(ks[j][1]), closes[j]) - lows[j]) / rng
        if closes[j] < prior_lo - 0.2 * atr_value and down_wick >= 0.5:
            for k in range(1, confirm_bars + 1):
                if j + k < n and closes[j + k] > prior_lo:
                    return {"kind": "failed_break_down", "level": round(prior_lo, 2),
                            "bars_since": n - 1 - j}
    return None


def follow_through(ks, direction: str):
    """Did the latest closed bar follow the prior one in the trade direction?"""
    if len(ks) < 2 or direction not in ("long", "short"):
        return None
    prev, last = ks[-2], ks[-1]
    rng = float(last[2]) - float(last[3])
    if rng <= 0:
        return None
    close_pos = (float(last[4]) - float(last[3])) / rng
    if direction == "long":
        ok = float(last[4]) > float(prev[2]) and close_pos >= 0.6
    else:
        ok = float(last[4]) < float(prev[3]) and close_pos <= 0.4
    return {"ok": bool(ok), "close_pos": round(close_pos, 2)}
