"""Deterministic event detectors (no LLM).

Each detector returns a normalised event dict:
{ts, symbol, kind, severity, direction, price, quality, payload}
"""
from __future__ import annotations

import time


def _ev(ts, symbol, kind, severity, direction, price, quality=50, **payload):
    return {
        "ts": ts, "symbol": symbol, "kind": kind, "severity": severity,
        "direction": direction, "price": price, "quality": quality,
        "payload": payload,
    }


def detect_events(symbol, features, close_1m, prev_close_1m, vol_z_1m,
                  vol_ratio_1m=None, funding=None, prev_state=None, cfg=None):
    cfg = cfg or {}
    th = cfg.get("thresholds", {})
    ts = int(time.time() * 1000)
    events = []
    atr = features.get("atr14") or 0.0
    price = features.get("price") or close_1m or 0.0
    move_pct = 0.0

    if prev_close_1m:
        move = close_1m - prev_close_1m
        move_pct = move / prev_close_1m * 100.0
        ratio = (abs(move) / atr) if atr else 0.0
        direction = "up" if move > 0 else "down"
        pct_shock = th.get("price_shock_pct", 0.5)
        pct_ext = th.get("extreme_pct", 1.5)
        if ratio >= th.get("extreme_shock_atr", 2.0) or abs(move_pct) >= pct_ext:
            events.append(_ev(ts, symbol, "price_shock_extreme", "P0", direction, close_1m,
                              quality=min(100, 70 + ratio * 10),
                              move_pct=move_pct, atr_ratio=ratio))
        elif ratio >= th.get("price_shock_atr", 0.8) or abs(move_pct) >= pct_shock:
            events.append(_ev(ts, symbol, "price_shock", "P1", direction, close_1m,
                              quality=min(100, 40 + ratio * 30 + max(0, vol_z_1m or 0) * 5),
                              move_pct=move_pct, atr_ratio=ratio))

    min_z = th.get("vol_z", 5.0)
    min_ratio = th.get("vol_ratio", 3.0)
    if (vol_z_1m is not None and vol_z_1m >= min_z
            and (vol_ratio_1m or 0.0) >= min_ratio):
        sev = "P1" if (vol_ratio_1m or 0.0) >= th.get("vol_ratio_p1", 5.0) else "P2"
        events.append(_ev(ts, symbol, "volume_spike", sev, None, close_1m,
                          quality=min(100, 35 + vol_z_1m * 10 + abs(move_pct) * 20),
                          vol_z=vol_z_1m, vol_ratio=round(float(vol_ratio_1m), 2),
                          move_pct=move_pct))

    lo, hi = features.get("r20_lo"), features.get("r20_hi")
    if lo and hi and close_1m:
        if close_1m > hi and (vol_z_1m or 0) >= th.get("breakout_vol_z", 1.0):
            events.append(_ev(ts, symbol, "range_break", "P1", "up", close_1m,
                              quality=min(100, 40 + (vol_z_1m or 0) * 15 + abs(move_pct) * 10),
                              r20_lo=lo, r20_hi=hi, vol_z=vol_z_1m))
        elif close_1m < lo and (vol_z_1m or 0) >= th.get("breakout_vol_z", 1.0):
            events.append(_ev(ts, symbol, "range_break", "P1", "down", close_1m,
                              quality=min(100, 40 + (vol_z_1m or 0) * 15 + abs(move_pct) * 10),
                              r20_lo=lo, r20_hi=hi, vol_z=vol_z_1m))

    state = features.get("trend")
    if prev_state and state and prev_state != state:
        events.append(_ev(ts, symbol, "state_shift", "P2", None, price, quality=50,
                          prev_state=prev_state, state=state,
                          adx=features.get("adx14"), pos20=features.get("pos20")))

    if funding is not None and abs(funding) >= 0.001:
        events.append(_ev(ts, symbol, "funding_extreme", "P2",
                          "long_crowded" if funding > 0 else "short_crowded",
                          price, quality=min(100, 40 + abs(funding) * 10000),
                          funding=funding))

    return events


_SEV_CN = {"P0": "需要立刻看", "P1": "值得留意", "P2": "仅供观察"}
_KIND_CN = {
    "price_shock_extreme": "极端价格冲击",
    "price_shock": "价格冲击",
    "volume_spike": "量能异常",
    "range_break": "区间突破",
    "state_shift": "结构切换",
    "funding_extreme": "资金费率极端",
}


def alert_text(event: dict) -> str:
    """Human-readable one-line alert for QQ / external channels."""
    p = event.get("payload", {})
    sym = (event.get("symbol") or "").replace("USDT", "")
    sev = event.get("severity", "")
    kind = event.get("kind", "")
    head = f"[{sev}·{_SEV_CN.get(sev, sev)}] {sym} · {_KIND_CN.get(kind, kind)}"
    bits = []
    if p.get("move_pct") is not None:
        bits.append(f"{p['move_pct']:+.2f}%")
    if p.get("atr_ratio") is not None:
        bits.append(f"{p['atr_ratio']:.1f}×ATR")
    if p.get("vol_z") is not None:
        bits.append(f"量 {p['vol_z']:.1f}σ")
    if p.get("prev_state") and p.get("state"):
        bits.append(f"{p['prev_state']}→{p['state']}")
    if p.get("funding") is not None:
        bits.append(f"资金费 {p['funding'] * 100:+.3f}%")
    price = event.get("price")
    if price:
        bits.append(f"price={price:.2f}")
    return head + (" · " + " · ".join(bits) if bits else "")
