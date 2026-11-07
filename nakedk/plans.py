# -----------------------------------------------------------------
# nakedk/plans.py - naked-k-analysis plan lifecycle state machine
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-49345A05
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
# -*- coding: utf-8 -*-
"""Trade-plan lifecycle.

A plan is the only thing the UI and the push channel are allowed to quote.
It is created once from an analysis snapshot, then only *transitions*:

    armed -> triggered -> confirmed -> managing -> closed
      |          |            |
      +----------+------------+--> void (expired / invalidated)

Why a state machine instead of re-deriving a signal on every tick:

* the trigger loop never recomputes features, it only compares price to the
  stored trigger / stop / target (cheap, safe at 15s cadence);
* the same plan object feeds the chart, the right-hand panel and QQ, so the
  three can never disagree;
* every transition is an append-only event with an idempotency key, so a
  process restart cannot re-push the same alert.

The module is pure: evaluate()/apply() never touch IO. Persistence lives in
beagle.store, delivery in beagle.push.
"""
from __future__ import annotations

import time

STATUSES = ("armed", "triggered", "confirmed", "managing", "closed", "void")
SIDES = ("long", "short")

TYPE_CN = {
    "armed": "待触发",
    "triggered": "已到触发区",
    "confirmed": "确认",
    "managing": "持仓管理",
    "closed": "已结束",
    "void": "作废",
}

SIDE_CN = {"long": "做多", "short": "做空"}

ACTION_CN = {
    "triggered": "进入触发区",
    "confirmed": "触发确认",
    "tp1": "目标一达成",
    "tp2": "目标二达成",
    "stopped": "止损",
    "expired": "超时作废",
    "invalidated": "结构失效",
    "void": "计划作废",
    "armed": "计划建立",
}


def _r(x, nd=6):
    return None if x is None else round(float(x), nd)


def rr(plan: dict) -> float | None:
    entry = plan.get("trigger")
    stop = plan.get("stop")
    target = plan.get("target1")
    if entry is None or stop is None or target is None:
        return None
    risk = abs(float(entry) - float(stop))
    if risk <= 0:
        return None
    return round(abs(float(target) - float(entry)) / risk, 2)


def trigger_mode(price: float, trigger: float) -> str:
    """below = wait for a pullback; above = wait for a breakout."""
    if trigger is None or price is None:
        return "market"
    if abs(trigger - price) / max(price, 1e-9) < 0.0008:
        return "market"
    return "below" if trigger < price else "above"


def build(symbol: str, interval: str, side: str, *, price: float, atr: float,
          trigger: float, stop: float, target1: float, target2: float | None = None,
          setup: str = "", confidence: float = 50, grade: str = "C",
          snapshot: dict | None = None, ttl_h: float = 12,
          params_version: int = 0, invalidation: str = "",
          now_ms: int | None = None, min_rr: float = 1.5) -> dict | None:
    """Create a plan dict; return None when the geometry is not tradable."""
    if side not in SIDES or not price or not atr:
        return None
    if trigger is None or stop is None or target1 is None:
        return None
    if side == "long":
        if not (stop < trigger < target1):
            return None
    else:
        if not (target1 < trigger < stop):
            return None
    risk = abs(float(trigger) - float(stop))
    if risk <= 0 or risk / float(trigger) > 0.08:
        return None
    cand = {"trigger": trigger, "stop": stop, "target1": target1}
    ratio = rr(cand)
    if ratio is None or ratio < min_rr:
        return None
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    return {
        "symbol": symbol,
        "interval": interval,
        "side": side,
        "setup": setup or "price_action",
        "status": "armed",
        "trigger": _r(trigger),
        "trigger_mode": trigger_mode(float(price), float(trigger)),
        "stop": _r(stop),
        "target1": _r(target1),
        "target2": _r(target2),
        "entry_ref": _r(price),
        "atr": _r(atr),
        "rr": ratio,
        "confidence": round(float(confidence), 1),
        "grade": grade,
        "invalidation": invalidation,
        "ttl_at": now + int(ttl_h * 3_600_000),
        "created_at": now,
        "updated_at": now,
        "params_version": params_version,
        "snapshot": snapshot or {},
        "triggered_at": None,
        "confirmed_at": None,
        "closed_at": None,
        "outcome": None,
        "pnl_pct": None,
        "version": 1,
    }


def expiry_event(plan: dict, now_ms: int):
    if plan.get("status") not in ("armed", "triggered"):
        return None
    if plan.get("ttl_at") and now_ms >= int(plan["ttl_at"]):
        return _transition("expired", plan, plan.get("entry_ref"), now_ms,
                           reason="ttl", to_status="void")
    return None


def evaluate(plan: dict, price: float, now_ms: int | None = None):
    """Return zero or one transition for this price tick (pure)."""
    if not plan or price is None:
        return None
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    status = plan.get("status")

    exp = expiry_event(plan, now)
    if exp:
        return exp
    if status not in ("armed", "triggered", "confirmed", "managing"):
        return None

    p = float(price)
    if status == "armed":
        t = float(plan["trigger"])
        mode = plan.get("trigger_mode") or trigger_mode(plan.get("entry_ref") or t, t)
        hit = (mode == "below" and p <= t) or (mode == "above" and p >= t) \
            or mode == "market"
        if hit:
            return _transition("triggered", plan, p, now, to_status="triggered")
        return None

    if status == "triggered":
        stop = float(plan["stop"])
        side = plan["side"]
        if (side == "long" and p <= stop) or (side == "short" and p >= stop):
            return _transition("void", plan, p, now,
                               reason="stopped_before_confirm", to_status="void",
                               outcome="stopped")
        return None

    # confirmed / managing: manage the live position
    stop = float(plan["stop"])
    side = plan["side"]
    if (side == "long" and p <= stop) or (side == "short" and p >= stop):
        return _transition("stopped", plan, p, now, to_status="closed",
                           outcome="stopped")
    t2 = plan.get("target2")
    t1 = plan.get("target1")
    if t2 is not None and ((side == "long" and p >= float(t2))
                           or (side == "short" and p <= float(t2))):
        return _transition("tp2", plan, p, now, to_status="closed",
                           outcome="target2")
    if t1 is not None and status == "confirmed" and (
            (side == "long" and p >= float(t1))
            or (side == "short" and p <= float(t1))):
        return _transition("tp1", plan, p, now, to_status="managing",
                           outcome="tp1")
    return None


def confirm(plan: dict, ctx: dict) -> dict:
    """Confirmation gate used when price reaches the trigger.

    Only removes trades; never invents a reason to enter. Reuses the same
    measured context the deterministic engine already exposes (4h structure,
    MTF alignment, regime policy, volume confirmation).
    """
    reasons = []
    side = plan.get("side")
    ctx = ctx or {}
    struct_dir = ctx.get("structure_direction")
    h4 = ctx.get("htf_direction")
    mtf = ctx.get("mtf_alignment")
    regime = ctx.get("regime")
    vol_z = ctx.get("vol_z")
    overlap = ctx.get("overlap")

    if side == "long" and struct_dir == "down":
        reasons.append("4h 结构向下，逆势做多")
    if side == "short" and struct_dir == "up":
        reasons.append("4h 结构向上，逆势做空")
    if side == "long" and h4 == "down":
        reasons.append("高周期方向向下")
    if side == "short" and h4 == "up":
        reasons.append("高周期方向向上")
    if mtf is not None and side == "long" and mtf <= -2:
        reasons.append("多周期空头排列")
    if mtf is not None and side == "short" and mtf >= 2:
        reasons.append("多周期多头排列")
    if vol_z is not None and vol_z < -0.5:
        reasons.append("成交量不确认")
    if overlap is not None and overlap >= 0.70:
        reasons.append("K 线重叠过高，无结构")
    try:
        from .policy import allow
        if not allow(regime, side):
            reasons.append("实测门禁拒绝该状态/方向组合")
    except Exception:
        pass
    return {"ok": not reasons, "reasons": reasons}


def apply(plan: dict, event: dict) -> dict:
    """Return a copy of the plan with one transition applied."""
    out = dict(plan or {})
    out["snapshot"] = dict(out.get("snapshot") or {})
    typ = (event or {}).get("type")
    now = int((event or {}).get("ts") or time.time() * 1000)
    if event.get("to_status"):
        out["status"] = event["to_status"]
    out["updated_at"] = now
    out["version"] = int(out.get("version") or 1) + 1
    if typ == "triggered":
        out["triggered_at"] = now
    elif typ == "confirmed":
        out["confirmed_at"] = now
    elif typ == "tp1":
        # move stop to breakeven and let the runner work toward target2
        out["stop"] = out.get("trigger")
        out["breakeven"] = True
    elif typ in ("tp2", "stopped", "expired", "invalidated", "void"):
        out["closed_at"] = now
        out["outcome"] = event.get("outcome") or typ
        entry = out.get("trigger")
        price = event.get("price")
        if entry and price:
            move = (float(price) - float(entry)) / float(entry) * 100.0
            out["pnl_pct"] = round(move if out.get("side") == "long" else -move, 3)
    return out


def _transition(typ: str, plan: dict, price, ts: int, to_status=None,
                reason="", outcome=None) -> dict:
    return {
        "type": typ,
        "price": _r(price),
        "ts": int(ts),
        "to_status": to_status,
        "reason": reason,
        "outcome": outcome,
        "plan_id": plan.get("id"),
        "symbol": plan.get("symbol"),
        "side": plan.get("side"),
        "status_before": plan.get("status"),
    }


def event_key(plan: dict, event: dict, bucket_ms: int = 60_000) -> str:
    """Idempotency key: one transition per plan per type per time bucket."""
    pid = plan.get("id") or "%s:%s:%s" % (
        plan.get("symbol"), plan.get("interval"), plan.get("created_at"))
    b = int(event.get("ts") or 0) // max(1, bucket_ms)
    return "%s|%s|%s" % (pid, event.get("type"), b)


def describe(plan: dict) -> dict:
    """UI-ready labels (Chinese) derived from a plan."""
    if not plan:
        return {}
    out = dict(plan)
    out["status_cn"] = TYPE_CN.get(plan.get("status"), plan.get("status"))
    out["side_cn"] = SIDE_CN.get(plan.get("side"), plan.get("side"))
    out["rr"] = plan.get("rr") or rr(plan)
    out["risk_pct"] = (round(abs(plan["trigger"] - plan["stop"])
                             / plan["trigger"] * 100, 2)
                       if plan.get("trigger") and plan.get("stop") else None)
    return out
