# -----------------------------------------------------------------
# nakedk/analysis.py - naked-k-analysis per-symbol orchestration
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-D97BF60A
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
# -*- coding: utf-8 -*-
"""One symbol -> multi-interval, chart-ready analysis payload.

This module is the single analysis path used by the dashboard, the trigger
engine and the CLI. It deliberately returns plain JSON-serialisable dicts:

    {symbol, price, intervals:{4h:{...},15m:{...}}, combined:{...}, mtf:{...}}

Per-interval work reuses the deterministic engine (features -> stance ->
patterns -> structure -> annotations). Nothing here talks to an LLM and
nothing here pushes; those are separate layers.
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor

from . import annotations, multi, symbol_params
from .bars import closed_bars, profile_series
from .features import features_from_klines, ema
from .fetch import klines
from .location import session_levels
from .markets import meta, resolve
from .params import load as load_params
from .pattern_tracker import states as pattern_states, track as track_patterns
from .patterns import arbitrate, detect as detect_patterns
from .regime import arbitrate as arbitrate_regime
from .signalbar import score as signalbar_score
from .signals import stance
from .structure import structure as structure_of
from .trend import trend_score

DEFAULT_INTERVALS = ("4h", "15m")
LIMITS = {"1m": 300, "5m": 300, "15m": 320, "30m": 300,
          "1h": 260, "4h": 240, "1d": 180}
_TF_SIGN = ("1d", "4h", "15m")
_EXEC = ThreadPoolExecutor(max_workers=6, thread_name_prefix="nk-analysis")


def _sign(ks):
    """+1 / -1 / 0 from price vs EMA20/EMA50 (same rule as nakedk.mtf)."""
    if not ks or len(ks) < 60:
        return 0
    closes = [float(k[4]) for k in ks]
    e20 = ema(closes[-120:], 20)
    e50 = ema(closes, 50)
    price = closes[-1]
    if price > e20 > e50:
        return 1
    if price < e20 < e50:
        return -1
    return 0


def _label(total):
    if total >= 2:
        return "aligned_up"
    if total <= -2:
        return "aligned_down"
    if total == 0:
        return "neutral"
    return "mixed"


def _candles(ks):
    return [{"t": int(k[0]), "o": float(k[1]), "h": float(k[2]),
             "l": float(k[3]), "c": float(k[4]), "v": float(k[5])}
            for k in ks]


def _ema_series(closes, n):
    if not closes:
        return []
    k = 2.0 / (n + 1.0)
    e = float(closes[0])
    out = []
    for v in closes:
        e = float(v) * k + e * (1.0 - k)
        out.append(round(e, 6))
    return out


def _pattern_states(symbol):
    try:
        import os
        from .pattern_tracker import states as ps
        db = os.environ.get("NK_PATTERN_DB") or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "patterns.db")
        return ps(symbol, db, 8)
    except Exception:
        return []


def analyze_interval(symbol: str, interval: str, ks_raw, params: dict,
                     mtf: dict | None = None, day_ks=None) -> dict:
    ks = closed_bars(ks_raw, interval)
    if len(ks) < 60:
        raise ValueError("need >=60 closed bars for %s %s" % (symbol, interval))
    f = features_from_klines(ks, interval)
    if mtf:
        f["mtf_alignment"] = mtf.get("alignment")
        f["mtf_label"] = mtf.get("label")
    st = stance(f, params)
    tr = trend_score(f, params)
    pats = arbitrate(detect_patterns(ks, f), f)
    struct = structure_of(ks)
    try:
        reg = arbitrate_regime(
            struct.get("state"),
            ((mtf or {}).get("by_state") or {}).get("1d"),
            (mtf or {}).get("alignment"), f.get("adx14"),
            f.get("adx_slope"), f.get("overlap"))
    except Exception:
        reg = {}
    prof = profile_series(ks)
    bar = prof[-1] if prof else {}
    prev = prof[-2] if len(prof) > 1 else None
    pdir = ("long" if (pats.get("primary") or {}).get("direction") == "bullish"
            else "short" if (pats.get("primary") or {}).get("direction") == "bearish"
            else None)
    try:
        sb = signalbar_score(bar, prev, pdir, f.get("pos20")) if pdir else {}
    except Exception:
        sb = {}
    try:
        import os
        db = os.environ.get("NK_PATTERN_DB") or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "patterns.db")
        track_patterns(symbol, pats.get("patterns") or [], db, f["price"])
    except Exception:
        pass
    overlays = annotations.build(ks, f, pats.get("patterns") or [], struct, interval)
    closes = [float(k[4]) for k in ks]
    session = {}
    try:
        session = session_levels(closed_bars(day_ks or [], "1d"))
    except Exception:
        session = {}
    return {
        "interval": interval,
        "candles": _candles(ks),
        "ema20_series": _ema_series(closes, 20),
        "ema50_series": _ema_series(closes, 50),
        "price": round(f["price"], 6),
        "features": {
            "adx": _num(f, "adx14", 0.0, 2),
            "adx_slope": f.get("adx_slope"),
            "rsi": _num(f, "rsi14", 50.0, 2),
            "atr": _num(f, "atr14", 0.0, 6),
            "atr_pct": _num(f, "atr_pct", 0.0, 3),
            "vol_z": _num(f, "vol_z", 0.0, 2),
            "pos20": _num(f, "pos20", 0.5, 3),
            "r20_lo": f.get("r20_lo"), "r20_hi": f.get("r20_hi"),
            "overlap": f.get("overlap"),
            "ret24h": _num(f, "ret24h", 0.0, 3),
            "ret72h": _num(f, "ret72h", 0.0, 3),
            "ema20": f.get("ema20"), "ema50": f.get("ema50"),
        },
        "stance": st,
        "trend": tr,
        "structure": struct,
        "regime": reg,
        "patterns": (pats.get("patterns") or [])[:8],
        "primary_pattern": pats.get("primary"),
        "secondary_pattern": pats.get("secondary"),
        "pattern_context": pats.get("context"),
        "pattern_states": _pattern_states(symbol),
        "bar": bar,
        "signalbar": sb,
        "annotations": overlays,
        "session": session,
        "source": resolve(symbol)[0],
        "data_ts": int(ks[-1][0]),
        "bars": len(ks),
    }


def _num(f: dict, key: str, default=0.0, nd=None):
    """Preserve real zero/None semantics instead of `or default`."""
    v = f.get(key)
    if v is None:
        v = default
    return round(v, nd) if nd is not None else v


_BARS_PER_DAY = {"1d": 1, "4h": 6, "1h": 24, "30m": 48, "15m": 96,
                 "5m": 288, "1m": 1440}


def _summary_24h(ks, price, interval: str = "15m"):
    if not ks:
        return {"change24h": 0.0, "high24h": price, "low24h": price}
    # 96 bars is exactly 24h only for 15m; on 4h it silently meant 16 days.
    bars = _BARS_PER_DAY.get(interval, 96)
    recent = ks[-min(len(ks), bars):]
    hi = max(float(k[2]) for k in recent)
    lo = min(float(k[3]) for k in recent)
    ref = float(recent[0][1]) if recent else price
    chg = (price - ref) / ref * 100.0 if ref else 0.0
    return {"change24h": round(chg, 3), "high24h": hi, "low24h": lo}


def analyze_symbol(symbol: str, intervals=None, params: dict | None = None,
                   params_version: int = 0) -> dict:
    """Fetch and analyse one symbol across the requested intervals."""
    symbol = (symbol or "").strip().upper()
    ivs = list(intervals or DEFAULT_INTERVALS)
    ivs = [x for x in ivs if x in LIMITS]
    if not ivs:
        ivs = list(DEFAULT_INTERVALS)
    p = params or symbol_params.get(symbol) or load_params()
    now = int(time.time() * 1000)

    # one parallel fetch phase: requested intervals + 1d context
    need = list(dict.fromkeys(ivs + ["1d"]))
    futs = {tf: _EXEC.submit(klines, symbol, tf, LIMITS.get(tf, 240))
            for tf in need}
    raw, errors = {}, {}
    for tf, fut in futs.items():
        try:
            raw[tf] = closed_bars(fut.result(), tf)
        except Exception as e:
            errors[tf] = str(e)[:160]
    if not any(raw.get(tf) for tf in ivs):
        raise RuntimeError("data unavailable: " + "; ".join(
            f"{k}: {v}" for k, v in errors.items()) or "no bars")

    # Execution price: last (possibly still forming) 15m bar close. This is
    # the same feed engine.last_price() uses, so arming and triggering share
    # one price basis instead of 4h-close vs 15m-last.
    last_price = None
    for tf in ("15m",) + tuple(ivs):
        if tf not in futs:
            continue
        try:
            rows = futs[tf].result()
            if rows:
                last_price = float(rows[-1][4])
                break
        except Exception:
            continue
    # 1d context is fetched for MTF but was never exposed on the payload,
    # which made the high-timeframe confirmation veto permanently None.
    context_1d = {}
    if raw.get("1d"):
        try:
            context_1d = {"state": structure_of(raw["1d"]).get("state")}
        except Exception:
            context_1d = {}
        context_1d["bars"] = len(raw["1d"])

    # Optional adaptive spacetime state (2.3.0). Purely descriptive: it never
    # gates a plan. Off by default => zero extra network request.
    spacetime_payload = None
    if os.environ.get("NK_SPACETIME", "").strip().lower() in (
            "1", "true", "yes", "on"):
        try:
            from . import spacetime
            bars4 = raw.get("4h") or []
            rows1h = futs["1h"].result() if "1h" in futs else \
                klines(symbol, "1h", 260)
            if len(bars4) > 20:
                st = spacetime.build_state(bars4, rows1h, len(bars4) - 1)
                spacetime_payload = {"state": st,
                                     "explain": spacetime.describe(st),
                                     "rules": spacetime.RULE_VERSION}
        except Exception as e:
            spacetime_payload = {"error": str(e)[:160]}

    signs, states = {}, {}
    for tf in _TF_SIGN:
        if raw.get(tf):
            signs[tf] = _sign(raw[tf])
            try:
                states[tf] = structure_of(raw[tf]).get("state")
            except Exception:
                states[tf] = None
        else:
            signs[tf] = 0
            states[tf] = None
    total = sum(signs.values())
    mtf = {"by_tf": signs, "by_state": states, "alignment": total,
           "label": _label(total)}

    out_ivs = {}
    for tf in ivs:
        try:
            out_ivs[tf] = analyze_interval(symbol, tf, raw.get(tf) or [],
                                           p, mtf, raw.get("1d"))
        except Exception as e:
            out_ivs[tf] = {"interval": tf, "error": str(e)[:200],
                           "candles": [], "stance": {"direction": "neutral"},
                           "annotations": {"patterns": [], "levels": {}}}
    combined = multi.combine(out_ivs, mode="multi" if len(ivs) > 1 else "single")
    primary = out_ivs.get("4h") or out_ivs.get(ivs[0]) or {}
    price = primary.get("price") or 0.0
    m = meta(symbol)
    _summ_tf = "15m" if raw.get("15m") else ivs[0]
    summ = _summary_24h(raw.get(_summ_tf) or [], price, _summ_tf)
    provider = resolve(symbol)[0]
    return {
        "symbol": symbol,
        "name": m.get("name") or symbol,
        "market": m.get("market") or "crypto",
        "provider": provider,
        "source": {"binance": "Binance", "yahoo": "Yahoo Finance",
                   "sina": "新浪财经"}.get(provider, provider),
        "price": price,
        "last_price": last_price,
        "context_1d": context_1d,
        "spacetime": spacetime_payload,
        "change24h": summ["change24h"],
        "high24h": summ["high24h"],
        "low24h": summ["low24h"],
        "intervals": out_ivs,
        "interval_order": ivs,
        "combined": combined,
        "mtf": mtf,
        "params_version": params_version,
        "errors": errors,
        "as_of": now,
        "data_ts": max((v.get("data_ts") or 0) for v in out_ivs.values()) or None,
    }
