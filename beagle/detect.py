"""Deterministic event detectors (no LLM).

Each detector returns a normalised event dict:
{ts, symbol, kind, severity, direction, price, payload}
"""
from __future__ import annotations

import time


def _ev(ts, symbol, kind, severity, direction, price, **payload):
    return {
        "ts": ts, "symbol": symbol, "kind": kind, "severity": severity,
        "direction": direction, "price": price, "payload": payload,
    }


def detect_events(symbol, features, close_1m, prev_close_1m, vol_z_1m,
                  funding=None, prev_state=None, cfg=None):
    cfg = cfg or {}
    th = cfg.get("thresholds", {})
    ts = int(time.time() * 1000)
    events = []
    atr = features.get("atr14") or 0.0
    price = features.get("price") or close_1m or 0.0

    if atr and prev_close_1m:
        move = close_1m - prev_close_1m
        ratio = abs(move) / atr
        direction = "up" if move > 0 else "down"
        if ratio >= th.get("extreme_shock_atr", 2.0):
            events.append(_ev(ts, symbol, "price_shock_extreme", "P0", direction, close_1m,
                              move_pct=(move / prev_close_1m * 100), atr_ratio=ratio))
        elif ratio >= th.get("price_shock_atr", 0.8):
            events.append(_ev(ts, symbol, "price_shock", "P1", direction, close_1m,
                              move_pct=(move / prev_close_1m * 100), atr_ratio=ratio))

    if vol_z_1m is not None and vol_z_1m >= th.get("vol_z", 3.0):
        events.append(_ev(ts, symbol, "volume_spike", "P1", None, close_1m,
                          vol_z=vol_z_1m))

    lo, hi = features.get("r20_lo"), features.get("r20_hi")
    if lo and hi and close_1m:
        if close_1m > hi and (vol_z_1m or 0) >= th.get("breakout_vol_z", 1.0):
            events.append(_ev(ts, symbol, "range_break", "P1", "up", close_1m,
                              r20_lo=lo, r20_hi=hi, vol_z=vol_z_1m))
        elif close_1m < lo and (vol_z_1m or 0) >= th.get("breakout_vol_z", 1.0):
            events.append(_ev(ts, symbol, "range_break", "P1", "down", close_1m,
                              r20_lo=lo, r20_hi=hi, vol_z=vol_z_1m))

    state = features.get("trend")
    if prev_state and state and prev_state != state:
        events.append(_ev(ts, symbol, "state_shift", "P2", None, price,
                          prev_state=prev_state, state=state,
                          adx=features.get("adx14"), pos20=features.get("pos20")))

    if funding is not None and abs(funding) >= 0.001:
        events.append(_ev(ts, symbol, "funding_extreme", "P2",
                          "long_crowded" if funding > 0 else "short_crowded",
                          price, funding=funding))

    return events


def alert_text(event: dict) -> str:
    p = event.get("payload", {})
    head = f"[{event['severity']}] {event['symbol']} {event['kind']}"
    bits = []
    for k in ("move_pct", "atr_ratio", "vol_z", "funding", "prev_state", "state", "r20_lo", "r20_hi"):
        if p.get(k) is not None:
            v = p[k]
            bits.append(f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}")
    if event.get("price"):
        bits.append(f"price={event['price']:.2f}")
    return head + (" | " + " ".join(bits) if bits else "")
