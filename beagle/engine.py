# -----------------------------------------------------------------
# beagle/engine.py - naked-k-analysis automated analysis + trigger engine
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-08D00909
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
# -*- coding: utf-8 -*-
"""Automation loop: analyse -> arm a plan -> watch price -> confirm -> push.

Runtime split
-------------
analysis  every N minutes (or on demand): recompute features, refresh plans
trigger   every ~20s: compare the last price with open plans only (no features)
push      drain the outbox after each transition

The trigger loop never recomputes features. When price reaches a trigger the
engine immediately runs one full analysis of that symbol and applies the
confirmation gate (structure / MTF / regime / volume). That "re-think on
arrival" is deliberate: a price touch alone is not a trade.
"""
from __future__ import annotations

import json
import os
import threading
import time

from nakedk import analysis, llm, plans as planlib, symbol_params
from nakedk.fetch import klines
from nakedk.markets import meta

from . import push, store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.environ.get("NK_SETTINGS", os.path.join(ROOT, "state", "settings.json"))
TUNE_PATH = os.environ.get("NK_LLM_TUNE", os.path.join(ROOT, "state", "llm_tune.json"))
DB_PATH = os.environ.get("BEAGLE_DB", os.path.join(ROOT, "beagle.db"))
_LOCK = threading.RLock()

DEFAULTS = {
    "active_symbols": ["BTCUSDT", "ETHUSDT"],
    "max_symbols": 6,
    "mode": "multi",                 # multi | single
    "intervals": ["15m", "4h"],
    "single_interval": "4h",
    "auto_analyze": True,
    "auto_trigger": True,
    "auto_push": False,              # QQ delivery is opt-in
    "push_armed": False,             # also push newly armed plans
    "qq_target": "",                 # optional per-settings target
    "push_ssh": "",                  # send through a remote qqbot gateway
    "plan_rearm_cooldown_min": 240,  # no same-side re-arm after a void
    "push_dedupe_min": 240,          # suppress identical push text
    "quiet_hours": [23, 8],
    "llm_annotate": True,
    "llm_autotune": False,
    "analysis_ttl_min": 30,
    "trigger_seconds": 20,
    "max_open_plans": 2,
    "level_proximity_atr": 0.35,
    "push_severity": ["confirmed", "tp1", "tp2", "stopped", "invalidated"],
}

_LAST_ANALYSIS = {}
_LAST_PAYLOAD = {}


# ---------------------------------------------------------------------------
# settings
# ---------------------------------------------------------------------------

def load_settings(path=None) -> dict:
    p = path or SETTINGS_PATH
    s = json.loads(json.dumps(DEFAULTS))
    try:
        with open(p, encoding="utf-8") as fh:
            user = json.load(fh)
        if isinstance(user, dict):
            for k, v in user.items():
                if k in s:
                    s[k] = v
    except Exception:
        pass
    return _sanitise(s)


def save_settings(patch: dict, path=None) -> dict:
    p = path or SETTINGS_PATH
    with _LOCK:
        s = load_settings(p)
        for k, v in (patch or {}).items():
            if k in DEFAULTS:
                s[k] = v
        s = _sanitise(s)
        try:
            os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(s, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, p)
        except Exception:
            pass
        return s


def _sanitise(s: dict) -> dict:
    syms = [str(x).strip().upper() for x in (s.get("active_symbols") or [])
            if str(x).strip()]
    syms = list(dict.fromkeys(syms))
    mx = max(1, min(24, int(s.get("max_symbols") or 6)))
    s["max_symbols"] = mx
    s["active_symbols"] = syms[:mx]
    ivs = [x for x in (s.get("intervals") or []) if x in ("1d", "4h", "1h", "30m", "15m")]
    if not ivs:
        ivs = ["4h", "15m"]
    s["mode"] = "single" if s.get("mode") == "single" else "multi"
    s["intervals"] = ivs if s["mode"] == "multi" else [s.get("single_interval") or "4h"]
    s["single_interval"] = s.get("single_interval") or "4h"
    s["analysis_ttl_min"] = max(2, min(240, int(s.get("analysis_ttl_min") or 30)))
    s["trigger_seconds"] = max(5, min(300, int(s.get("trigger_seconds") or 20)))
    s["max_open_plans"] = max(1, min(8, int(s.get("max_open_plans") or 2)))
    s["qq_target"] = str(s.get("qq_target") or "").strip()[:200]
    s["push_ssh"] = str(s.get("push_ssh") or "").strip()[:120]
    s["plan_rearm_cooldown_min"] = max(0, min(1440, int(s.get("plan_rearm_cooldown_min") or 240)))
    s["push_dedupe_min"] = max(0, min(1440, int(s.get("push_dedupe_min") or 240)))
    qh = s.get("quiet_hours") or [23, 8]
    if isinstance(qh, list) and len(qh) == 2:
        s["quiet_hours"] = [int(qh[0]) % 24, int(qh[1]) % 24]
    else:
        s["quiet_hours"] = [23, 8]
    s["push_armed"] = bool(s.get("push_armed"))
    return s


def intervals_for(s: dict) -> list:
    if s.get("mode") == "single":
        return [s.get("single_interval") or "4h"]
    return list(s.get("intervals") or ["4h", "15m"])


# ---------------------------------------------------------------------------
# plan construction from analysis
# ---------------------------------------------------------------------------

def _choose_trigger(side: str, primary: dict, price: float, atr: float,
                    max_atr: float) -> tuple:
    """Pick a pullback level; fall back to market when no level is near."""
    f = primary.get("features") or {}
    st = primary.get("structure") or {}
    levels = st.get("levels") or {}
    cands = []
    if f.get("ema20"):
        cands.append(float(f["ema20"]))
    if side == "long":
        sw = levels.get("swing_low")
        if sw:
            cands.append(float(sw) + 0.15 * atr)
    else:
        sw = levels.get("swing_high")
        if sw:
            cands.append(float(sw) - 0.15 * atr)
    is_long = side == "long"
    valid = []
    for c in cands:
        dist = (price - c) if is_long else (c - price)
        if 0.05 * atr <= dist <= max_atr * atr:
            valid.append(c)
    if not valid:
        # no pullback level nearby: wait for a small pullback instead of
        # arming at market and triggering on the very next tick
        trig = price - 0.15 * atr if is_long else price + 0.15 * atr
        return round(trig, 6), ("below" if is_long else "above")
    trig = max(valid) if is_long else min(valid)
    return round(trig, 6), planlib.trigger_mode(price, trig)


def _confluence(side: str, combined: dict, primary: dict, payload: dict,
                rr: float | None) -> tuple:
    score, parts = 40, []
    if combined.get("agreement") == "aligned":
        score += 15; parts.append("多周期共振")
    pstate = (primary.get("structure") or {}).get("state")
    if (side == "long" and pstate == "up") or (side == "short" and pstate == "down"):
        score += 15; parts.append("主周期结构同向")
    other = None
    for tf, iv in (payload.get("intervals") or {}).items():
        if tf != (primary.get("interval") or "4h"):
            other = iv
            break
    odir = ((other or {}).get("stance") or {}).get("direction")
    if odir == side:
        score += 10; parts.append("次周期同向")
    elif odir in ("long", "short"):
        score -= 10; parts.append("次周期反向")
    pat = primary.get("primary_pattern") or {}
    if (side == "long" and pat.get("direction") == "bullish") or        (side == "short" and pat.get("direction") == "bearish"):
        score += 10; parts.append("形态同向")
    if rr and rr >= 2.0:
        score += 5; parts.append("R:R≥2")
    return max(0, min(100, score)), parts


def build_plan(symbol: str, payload: dict, params: dict, settings: dict,
               now_ms: int | None = None):
    """Derive an armed plan from a finished analysis payload."""
    combined = payload.get("combined") or {}
    side = combined.get("direction")
    if side not in ("long", "short"):
        return None
    if (combined.get("confidence") or 0) < float(params.get("plan_min_confidence", 52)):
        return None
    primary = (payload.get("intervals") or {}).get("4h") or \
        (payload.get("intervals") or {}).get((payload.get("interval_order") or ["4h"])[0]) or {}
    price = primary.get("price") or payload.get("price")
    atr = ((primary.get("features") or {}).get("atr"))
    st = primary.get("stance") or {}
    if not price or not atr or not st.get("target"):
        return None
    max_atr = float(params.get("plan_trigger_max_atr", 1.5))
    trigger, mode = _choose_trigger(side, primary, float(price), float(atr), max_atr)
    stop_atr = float(params.get("stance_stop_atr", 1.5))
    target_atr = float(params.get("stance_target_atr", 3.0))
    swing = (primary.get("structure") or {}).get("levels") or {}
    if side == "long":
        stop = trigger - stop_atr * atr
        sl = swing.get("swing_low")
        if sl and float(sl) < trigger and (trigger - float(sl)) < 2.2 * atr:
            stop = min(stop, float(sl) - 0.1 * atr)
        target1 = trigger + target_atr * atr
        target2 = trigger + 2 * target_atr * atr
        if st.get("target") and float(st["target"]) > target1:
            target1 = float(st["target"])
    else:
        stop = trigger + stop_atr * atr
        sh = swing.get("swing_high")
        if sh and float(sh) > trigger and (float(sh) - trigger) < 2.2 * atr:
            stop = max(stop, float(sh) + 0.1 * atr)
        target1 = trigger - target_atr * atr
        target2 = trigger - 2 * target_atr * atr
        if st.get("target") and float(st["target"]) < target1:
            target1 = float(st["target"])
    pat = primary.get("primary_pattern") or {}
    if pat.get("target") and ((side == "long" and pat["target"] > price)
                              or (side == "short" and pat["target"] < price)):
        target1 = float(pat["target"])
    setup = (pat.get("type") or "structure")
    snap = {
        "combined": combined,
        "mtf": payload.get("mtf"),
        "structure": primary.get("structure"),
        "features": primary.get("features"),
        "primary_pattern": pat,
        "reasons": st.get("reasons") or [],
    }
    invalidation = ("4h 收盘跌破 %.4f" % stop) if side == "long" else \
                   ("4h 收盘突破 %.4f" % stop)
    p = planlib.build(
        symbol, primary.get("interval") or "4h", side,
        price=float(price), atr=float(atr), trigger=trigger, stop=stop,
        target1=target1, target2=target2, setup=setup,
        confidence=combined.get("confidence") or 50,
        grade=combined.get("grade") or "C", snapshot=snap,
        ttl_h=float(params.get("plan_ttl_h", 12)),
        params_version=int(payload.get("params_version") or 0),
        invalidation=invalidation, now_ms=now_ms,
        min_rr=float(params.get("plan_min_rr", 1.5)))
    if not p:
        return None
    score, parts = _confluence(side, combined, primary, payload, p.get("rr"))
    if score < float(params.get("plan_min_confluence", 40)):
        return None
    p["confluence"] = score
    p["confluence_parts"] = parts
    risk = float(params.get("plan_risk_pct", 0.5))
    stop_pct = abs(float(trigger) - float(stop)) / float(trigger) * 100 if trigger else 0
    p["risk_pct"] = risk
    p["notional_pct"] = round(min(100.0, risk / stop_pct * 100), 1) if stop_pct else None
    return p


def _fp(x, nd=4):
    if x is None:
        return "—"
    v = float(x)
    if abs(v) >= 1000:
        return "{:,.2f}".format(v)
    if abs(v) >= 10:
        return "%.2f" % v
    if abs(v) >= 1:
        return "%.3f" % v
    return "%.4f" % v


def _side_cn(side):
    return "做多" if side == "long" else ("做空" if side == "short" else "观望")


def plan_advice(plan: dict, event: dict | None = None,
                payload: dict | None = None) -> dict:
    """Simple, actionable Chinese advice. Deterministic; no invented numbers."""
    plan = plan or {}
    event = event or {}
    payload = payload or {}
    typ = event.get("type") or {
        "armed": "armed", "triggered": "triggered", "confirmed": "confirmed",
        "managing": "tp1", "closed": "tp2", "void": "invalidated",
    }.get(plan.get("status"), "armed")
    side = plan.get("side")
    side_cn = _side_cn(side)
    price = event.get("price")
    if price is None:
        price = payload.get("price") or plan.get("entry_ref")
    trig = plan.get("trigger")
    stop = plan.get("stop")
    t1 = plan.get("target1")
    t2 = plan.get("target2")
    atr = float(plan.get("atr") or 0)
    raw_sym = payload.get("name") or plan.get("symbol") or ""
    sym = raw_sym if "/" in raw_sym else (
        raw_sym.replace("USDT", "/USDT") if raw_sym.endswith("USDT") else raw_sym)
    headline = "%s · %s · %s" % (sym, plan.get("interval") or "", side_cn)
    status_cn = {
        "armed": "计划待触发", "triggered": "已到触发区，复核中",
        "confirmed": "触发确认", "tp1": "目标一达成",
        "tp2": "目标二达成", "stopped": "止损离场",
        "invalidated": "结构失效", "void": "计划作废",
        "expired": "计划超时",
    }.get(typ) or {
        "armed": "计划待触发", "triggered": "已到触发区，复核中",
        "confirmed": "触发确认", "managing": "持仓管理",
        "closed": "计划结束", "void": "计划作废",
    }.get(plan.get("status"), plan.get("status") or typ)

    action = ""
    if typ in ("armed", "triggered"):
        action = "等价格到 %s 再执行；未到不追。" % _fp(trig)
        if typ == "triggered":
            action = "已到触发区，正在重新分析；确认前不进场。"
    elif typ == "confirmed":
        if side == "long":
            if price is None or float(price) <= float(trig):
                action = "等回踩到 %s 附近再做多，止损 %s。" % (
                    _fp(trig), _fp(stop))
            elif atr and (float(price) - float(trig)) > 0.45 * atr:
                action = "现价离触发价已远，不追；等回踩 %s 再考虑。" % _fp(trig)
            else:
                action = "现价 %s 附近可轻仓做多，止损 %s。" % (
                    _fp(price), _fp(stop))
        elif side == "short":
            if price is None or float(price) >= float(trig):
                action = "等反抽到 %s 附近再做空，止损 %s。" % (
                    _fp(trig), _fp(stop))
            elif atr and (float(trig) - float(price)) > 0.45 * atr:
                action = "现价离触发价已远，不追；等反抽 %s 再考虑。" % _fp(trig)
            else:
                action = "现价 %s 附近可轻仓做空，止损 %s。" % (
                    _fp(price), _fp(stop))
    elif typ == "tp1":
        action = f"目标1 已到：减仓 50%，止损上移到 {_fp(trig)}（保本），剩余看目标2。"
    elif typ == "tp2":
        action = "目标2 已到：剩余仓位了结，不恋战。"
    elif typ == "stopped":
        action = "止损 %s 已触发：离场，不补仓；等下一次结构。" % _fp(stop)
    elif typ in ("invalidated", "void"):
        action = "结构失效：取消计划，不追单。"
    elif typ == "expired":
        action = "计划超时：取消，不补单。"
    else:
        action = "按计划执行；未触发不进场。"

    rr = plan.get("rr")
    risk = "单笔风险 %s%%" % (plan.get("risk_pct") or 0.5)
    if plan.get("notional_pct") is not None:
        risk += " · 名义 %s%%" % plan["notional_pct"]
    if rr:
        risk += " · R:R %s" % rr
    reasons = ((plan.get("snapshot") or {}).get("reasons") or [])[:2]
    mtf = (payload.get("mtf") or {}).get("label")
    basis_parts = [str(x) for x in reasons if x]
    if mtf:
        basis_parts.append("MTF %s" % mtf)
    basis = " · ".join(basis_parts[:3]) or "结构 + 周期确认"
    data_ts = payload.get("data_ts")
    data_line = payload.get("source") or "—"
    if data_ts:
        data_line += " · " + time.strftime("%m-%d %H:%M", time.localtime(data_ts / 1000))
    lines = [headline, "状态：" + status_cn, "操作：" + action]
    if trig is not None and stop is not None:
        tgt = " / ".join(x for x in (_fp(t1), _fp(t2) if t2 else "") if x)
        lines.append("触发 %s ｜ 止损 %s ｜ 目标 %s" % (_fp(trig), _fp(stop), tgt or "—"))
    lines += ["依据：" + basis, "风控：" + risk,
              "数据：" + data_line + " · 非投资建议"]
    return {"headline": headline, "status_cn": status_cn, "action": action,
            "risk": risk, "basis": basis, "lines": lines}


def _plan_text(plan: dict, event: dict, payload: dict | None = None) -> str:
    adv = plan_advice(plan, event, payload)
    text = "\n".join(adv["lines"])
    return text if len(text) <= 700 else text[:699] + "…"



# ---------------------------------------------------------------------------
# analysis + plan refresh
# ---------------------------------------------------------------------------

def analyze_symbol(symbol: str, settings: dict | None = None, db_path: str = DB_PATH,
                   force_plan: bool = True) -> dict:
    s = settings or load_settings()
    ivs = intervals_for(s)
    prof = symbol_params.profile(symbol)
    params = symbol_params.get(symbol)
    payload = analysis.analyze_symbol(symbol, ivs, params, prof.get("version") or 0)
    _LAST_ANALYSIS[symbol] = int(time.time() * 1000)
    _LAST_PAYLOAD[symbol] = payload
    if not force_plan:
        payload["plan"] = store.active_plan(db_path, symbol)
        return payload

    active = store.active_plan(db_path, symbol)
    cand = build_plan(symbol, payload, params, s)
    now = int(time.time() * 1000)
    if cand and not active:
        cooldown = int(s.get("plan_rearm_cooldown_min") or 240) * 60_000
        if cooldown and store.recent_void_plan(db_path, symbol, cand["side"], now - cooldown):
            cand = None
    plan = active
    if cand:
        if active and active.get("status") in ("armed",) and \
                active.get("side") == cand.get("side"):
            # refresh levels in place, keep the same lifecycle
            for k in ("trigger", "trigger_mode", "stop", "target1", "target2",
                      "confidence", "grade", "rr", "invalidation", "ttl_at",
                      "snapshot", "atr", "setup"):
                active[k] = cand.get(k)
            active["updated_at"] = now
            active["version"] = int(active.get("version") or 1) + 1
            plan = store.save_plan(db_path, active)
        elif not active:
            plan = store.save_plan(db_path, cand)
            ev = {"type": "armed", "price": cand.get("entry_ref"),
                  "ts": now, "plan_id": plan["id"], "symbol": symbol,
                  "side": cand["side"], "to_status": "armed"}
            eid = store.add_plan_event(db_path, plan, ev,
                                       planlib.event_key(plan, ev))
            if eid and (s.get("push_armed") or "armed" in (s.get("push_severity") or [])):
                store.outbox_add(db_path, eid, "qq", _plan_text(plan, ev, payload), dedupe_min=int(s.get("push_dedupe_min") or 0))
        else:
            plan = active
    elif active and active.get("status") == "armed":
        combined = payload.get("combined") or {}
        if combined.get("direction") not in (None, "neutral", active.get("side")):
            ev = {"type": "invalidated", "price": payload.get("price"),
                  "ts": now, "reason": "分析方向翻转", "to_status": "void",
                  "outcome": "invalidated"}
            plan = planlib.apply(active, ev)
            plan = store.save_plan(db_path, plan)
            eid = store.add_plan_event(db_path, plan, ev, planlib.event_key(plan, ev))
            if eid:
                store.outbox_add(db_path, eid, "qq", _plan_text(plan, ev, payload), dedupe_min=int(s.get("push_dedupe_min") or 0))
    if plan:
        described = planlib.describe(plan)
        ev_type = {"armed": "armed", "triggered": "triggered",
                   "confirmed": "confirmed", "managing": "tp1"}.get(
            plan.get("status"), "armed")
        described["advice"] = plan_advice(plan, {"type": ev_type}, payload)
        payload["plan"] = described
    else:
        payload["plan"] = None
    payload["params"] = params
    payload["params_profile"] = {"version": prof.get("version") or 0,
                                 "source": prof.get("source") or "default"}
    return payload


def _confirm_payload(symbol: str, settings: dict, db_path: str) -> dict:
    """Full re-analysis used by the confirmation gate."""
    prof = symbol_params.profile(symbol)
    params = symbol_params.get(symbol)
    return analysis.analyze_symbol(symbol, intervals_for(settings), params,
                                   prof.get("version") or 0)


def _ctx_from(payload: dict, plan: dict) -> dict:
    primary = (payload.get("intervals") or {}).get(plan.get("interval") or "4h") or {}
    f = primary.get("features") or {}
    return {
        "structure_direction": (primary.get("structure") or {}).get("state"),
        "htf_direction": ((payload.get("intervals") or {}).get("1d") or {}).get(
            "structure", {}).get("state"),
        "mtf_alignment": (payload.get("mtf") or {}).get("alignment"),
        "regime": (primary.get("regime") or {}).get("regime")
        or (primary.get("regime") or {}).get("state"),
        "vol_z": f.get("vol_z"),
        "overlap": f.get("overlap"),
    }


def refresh_plan(symbol: str, settings: dict | None = None,
                 db_path: str = DB_PATH) -> dict | None:
    """Re-analysis + confirmation for a plan already in `triggered`."""
    s = settings or load_settings()
    plan = store.active_plan(db_path, symbol)
    if not plan or plan.get("status") != "triggered":
        return plan
    payload = _confirm_payload(symbol, s, db_path)
    dec = planlib.confirm(plan, _ctx_from(payload, plan))
    now = int(time.time() * 1000)
    if dec["ok"]:
        ev = {"type": "confirmed", "price": payload.get("price"), "ts": now,
              "to_status": "confirmed", "reason": "上下文确认"}
        plan = planlib.apply(plan, ev)
        plan = store.save_plan(db_path, plan)
        eid = store.add_plan_event(db_path, plan, ev, planlib.event_key(plan, ev))
        if eid and "confirmed" in (s.get("push_severity") or []):
            store.outbox_add(db_path, eid, "qq", _plan_text(plan, ev, payload), dedupe_min=int(s.get("push_dedupe_min") or 0))
    else:
        ev = {"type": "invalidated", "price": payload.get("price"), "ts": now,
              "to_status": "void", "outcome": "invalidated",
              "reason": "；".join(dec["reasons"])[:180]}
        plan = planlib.apply(plan, ev)
        plan = store.save_plan(db_path, plan)
        eid = store.add_plan_event(db_path, plan, ev, planlib.event_key(plan, ev))
        if eid and "invalidated" in (s.get("push_severity") or []):
            store.outbox_add(db_path, eid, "qq", _plan_text(plan, ev, payload), dedupe_min=int(s.get("push_dedupe_min") or 0))
    return plan


# ---------------------------------------------------------------------------
# trigger loop
# ---------------------------------------------------------------------------

def last_price(symbol: str) -> float | None:
    """Last traded price with one cheap request (2 bars)."""
    try:
        rows = klines(symbol, "15m", 3)
        return float(rows[-1][4]) if rows else None
    except Exception:
        return None


def tick(settings: dict | None = None, db_path: str = DB_PATH) -> list:
    s = settings or load_settings()
    if not s.get("auto_trigger"):
        return []
    events = []
    open_plans = store.open_plans(db_path)
    if not open_plans:
        return events
    prices = {}
    for plan in open_plans:
        sym = plan.get("symbol")
        if sym not in prices:
            prices[sym] = last_price(sym)
        price = prices.get(sym)
        if price is None:
            continue
        ev = planlib.evaluate(plan, price)
        if not ev:
            continue
        ev["plan_id"] = plan.get("id")
        if ev["type"] == "triggered":
            updated = planlib.apply(plan, ev)
            updated = store.save_plan(db_path, updated)
            eid = store.add_plan_event(db_path, updated, ev,
                                       planlib.event_key(updated, ev))
            events.append(ev)
            # "think on arrival": full re-analysis + confirmation gate
            try:
                confirm_plan = refresh_plan(sym, s, db_path)
                if confirm_plan:
                    events.append({"type": "confirm_result",
                                   "status": confirm_plan.get("status"),
                                   "plan_id": confirm_plan.get("id")})
            except Exception as e:
                events.append({"type": "confirm_error", "error": str(e)[:160]})
        else:
            updated = planlib.apply(plan, ev)
            updated = store.save_plan(db_path, updated)
            eid = store.add_plan_event(db_path, updated, ev,
                                       planlib.event_key(updated, ev))
            events.append(ev)
            push_type = {"tp2": "tp2", "tp1": "tp1", "stopped": "stopped",
                         "expired": "expired", "invalidated": "invalidated",
                         "void": "invalidated"}.get(ev["type"], ev["type"])
            if eid and push_type in (s.get("push_severity") or []):
                store.outbox_add(db_path, eid, "qq", _plan_text(updated, ev), dedupe_min=int(s.get("push_dedupe_min") or 0))
    if events and s.get("auto_push"):
        try:
            push.push_outbox(db_path, s)
        except Exception:
            pass
    return events


def level_watch(settings: dict | None = None, db_path: str = DB_PATH,
                cooldown_ms: int = 300_000) -> list:
    """Re-analyse when price arrives at a level that matters.

    This is the "到达价位自动进行下一次分析" rule. It only fires when the last
    price is within (level_proximity_atr x ATR) of a support / resistance,
    pattern neckline or measured target, with a per-symbol cooldown so a
    slow trend cannot turn into a request storm.
    """
    s = settings or load_settings()
    if not s.get("auto_analyze"):
        return []
    now = int(time.time() * 1000)
    fired = []
    prox = float(s.get("level_proximity_atr") or 0.35)
    for sym in s.get("active_symbols") or []:
        p = _LAST_PAYLOAD.get(sym)
        if not p or now - _LAST_ANALYSIS.get(sym, 0) < cooldown_ms:
            continue
        price = p.get("price")
        primary = (p.get("intervals") or {}).get("4h") or next(
            iter((p.get("intervals") or {}).values()), None)
        if not price or not primary:
            continue
        f = primary.get("features") or {}
        atr = float(f.get("atr") or 0)
        if not atr:
            continue
        levels = []
        ann = primary.get("annotations") or {}
        for grp in (ann.get("levels") or {}).values():
            for x in grp or []:
                if x.get("price"):
                    levels.append(float(x["price"]))
        for pat in ann.get("patterns") or []:
            for ln in pat.get("lines") or []:
                if ln.get("price"):
                    levels.append(float(ln["price"]))
        if not levels:
            continue
        near = [x for x in levels if abs(x - float(price)) <= prox * atr]
        if not near:
            continue
        try:
            analyze_symbol(sym, s, db_path)
            fired.append({"symbol": sym, "price": price,
                          "level": min(near, key=lambda x: abs(x - float(price)))})
        except Exception:
            continue
    return fired


def analysis_loop(settings: dict | None = None, db_path: str = DB_PATH):
    s = settings or load_settings()
    now = int(time.time() * 1000)
    ttl = int(s.get("analysis_ttl_min") or 30) * 60_000
    for sym in s.get("active_symbols") or []:
        if now - _LAST_ANALYSIS.get(sym, 0) >= ttl:
            try:
                analyze_symbol(sym, s, db_path)
            except Exception:
                continue


def maybe_autotune(settings: dict | None = None, db_path: str = DB_PATH):
    """LLM parameter proposal, only with enough closed samples and hard bounds."""
    s = settings or load_settings()
    if not s.get("llm_autotune") or not llm.status().get("enabled"):
        return []
    applied = []
    state = _read_json(TUNE_PATH)
    for sym in s.get("active_symbols") or []:
        stats = store.plan_stats(db_path, sym)
        if (stats.get("total") or 0) < 20 or (stats.get("closed") or 0) < 10:
            continue
        if time.time() * 1000 - int(state.get(sym) or 0) < 24 * 3600_000:
            continue
        prof = symbol_params.profile(sym)
        payload = {
            "symbol": sym,
            "current_params": {k: prof["effective"].get(k) for k in symbol_params.BOUNDS},
            "stats": stats,
            "recent_events": store.plan_events(db_path, None, 40),
        }
        res = llm.propose_params(payload, symbol_params.BOUNDS, symbol_params.BOUNDS)
        patch = res.get("patch") or {}
        errs = symbol_params.validate_patch(patch)
        if not patch or errs or len(patch) > 2:
            state[sym] = int(time.time() * 1000)
            _write_json(TUNE_PATH, state)
            continue
        symbol_params.save(sym, patch, source="llm",
                           note=(res.get("rationale") or "")[:180])
        state[sym] = int(time.time() * 1000)
        _write_json(TUNE_PATH, state)
        applied.append({"symbol": sym, "patch": patch,
                        "rationale": res.get("rationale")})
    return applied


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json(path, data):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass


def run_forever(db_path: str = DB_PATH, stop_event: threading.Event | None = None):
    """Standalone worker (python -m beagle.engine)."""
    store.init(db_path)
    last_analysis = 0
    while not (stop_event and stop_event.is_set()):
        s = load_settings()
        try:
            if time.time() * 1000 - last_analysis > 60_000:
                analysis_loop(s, db_path)
                level_watch(s, db_path)
                maybe_autotune(s, db_path)
                last_analysis = int(time.time() * 1000)
            tick(s, db_path)
            if s.get("auto_push"):
                push.push_outbox(db_path, s)
        except Exception:
            pass
        time.sleep(int(s.get("trigger_seconds") or 20))


if __name__ == "__main__":
    store.init(DB_PATH)
    run_forever(DB_PATH)
