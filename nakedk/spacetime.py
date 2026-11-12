# -----------------------------------------------------------------
# nakedk/spacetime.py - adaptive multi-scale time/price-state engine
# (c) 2026 William-Trader (https://github.com/William-Trader)
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# -----------------------------------------------------------------
"""Spacetime analysis: replace hard-coded 15m+4h with an adaptive scale axis.

Motivation
----------
The legacy stack fixes two observation windows (15m execution / 4h bias) and
treats every bar as interchangeable in time. That conflates three different
questions: *which scale currently carries the trend*, *where price sits in the
structure*, and *how that structure has aged*. This module answers them
explicitly and produces a decision that can be explained bar by bar.

Time axis (adaptive scale)
    From the 1h base series we re-aggregate 1h / 2h / 4h / 8h / 1d and measure
    "information ratio" = |net displacement| / total path length per scale.
    The scale with the cleanest directional path is `dominant_scale`. No scale
    is privileged a priori; 15m is no longer assumed to be the execution frame.

Space axis (price structure)
    Structural range from rolling swing extremes; position inside it,
    displacement velocity / acceleration in ATR units, level age and
    exponentially decayed touch count. Together these describe *where* and
    *how fast*, not just "up or down".

State + decision
    A discrete state id (scale x trend/range x position bucket) plus a purely
    rule-based `admit()`. Rules are deliberately not fitted to returns: they
    encode the measurable hypotheses (trade with the dominant scale, fade only
    at range edges, require velocity/acceleration agreement). Every rejection
    carries a human-readable reason for the audit trail.

Compatibility
    Pure functions, stdlib only. Nothing here changes the existing pipeline
    unless `NK_SPACETIME=1` (production) or `mask=` (research) is supplied.
"""
from __future__ import annotations

import datetime as _dt
import math
import os

SCALES = (1, 2, 4, 8, 24)          # hours, aggregated from the 1h base
LOOKBACK_HOURS = 240               # 10 days of 1h bars per state
VELOCITY_BARS = 6
EFFICIENCY_TREND = 0.30   # v2: 24x1h path efficiency; 0.45 was too strict
HALF_LIFE_BARS = 24                # level touch decay (4h bars)


def enabled() -> bool:
    return os.environ.get("NK_SPACETIME", "").strip().lower() in (
        "1", "true", "yes", "on")


def _aggregate(rows, n: int):
    """Aggregate 1h [t,o,h,l,c,v] rows into n-hour bars (no look-ahead)."""
    out = []
    for i in range(0, len(rows) - n + 1, n):
        chunk = rows[i:i + n]
        out.append([int(chunk[0][0]), float(chunk[0][1]),
                    max(float(r[2]) for r in chunk),
                    min(float(r[3]) for r in chunk),
                    float(chunk[-1][4]),
                    sum(float(r[5]) for r in chunk)])
    return out


def _efficiency(bars) -> float:
    """Net displacement / total path length in [0,1]; 1 = perfectly clean trend."""
    if len(bars) < 3:
        return 0.0
    closes = [float(b[4]) for b in bars]
    path = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))
    net = abs(closes[-1] - closes[0])
    return net / path if path > 0 else 0.0


def _atr(rows, period: int = 14) -> float:
    if len(rows) < period + 1:
        return 0.0
    tr = []
    for i in range(1, len(rows)):
        h, l, pc = float(rows[i][2]), float(rows[i][3]), float(rows[i - 1][4])
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(tr[-period:]) / period


def _swing_range(bars4, window: int = 40):
    part = bars4[-window:] if len(bars4) >= window else bars4
    if not part:
        return 0.0, 0.0
    return (min(float(b[3]) for b in part),
            max(float(b[2]) for b in part))


def _level_touch(bars4, lo, hi, price, atr) -> tuple[int, float]:
    """Touch count and decayed weight for the nearest structural boundary."""
    if atr <= 0:
        return 0, 0.0
    tol = 0.25 * atr
    target = lo if abs(price - lo) <= abs(price - hi) else hi
    n, weight = 0, 0.0
    window = bars4[-120:]
    for j in range(len(window) - 1, -1, -1):
        b = window[j]
        if abs(float(b[3]) - target) <= tol or abs(float(b[2]) - target) <= tol:
            n += 1
            k = len(window) - 1 - j
            weight += 0.5 ** (k / max(1, HALF_LIFE_BARS))
    return n, round(weight, 3)


_TS_CACHE: dict = {}


def build_state(ks4, ks1, index: int, lookback_hours: int = LOOKBACK_HOURS) -> dict:
    """State for the 4h bar at `index`, using only data up to and including it.

    ks4 / ks1 are [t,o,h,l,c,v] rows sorted by t (ms). The 1h series is cut at
    the bar's close time so no future information leaks into the state.
    """
    import bisect
    t = int(ks4[index][0])
    cutoff = t + 4 * 3600_000
    upto4 = ks4[:index + 1]
    key = id(ks1)
    ts = _TS_CACHE.get(key)
    if ts is None or len(ts) != len(ks1):
        ts = [int(r[0]) for r in ks1]
        _TS_CACHE.clear()
        _TS_CACHE[key] = ts
    j = bisect.bisect_left(ts, cutoff)
    upto1 = ks1[:j][-max(lookback_hours, 24 * 8):]
    if len(upto1) < 48 or len(upto4) < 20:
        return {"complete": False, "t": t, "reason": "insufficient history"}
    price = float(upto4[-1][4])
    atr = _atr(upto4[-60:]) or 1e-9

    scale_scores = {}
    for n in SCALES:
        agg = _aggregate(upto1[-min(len(upto1), n * 30):], n)
        scale_scores[n] = round(_efficiency(agg), 4)
    dominant = max(scale_scores, key=lambda n: scale_scores[n])

    path = _efficiency(upto1[-24:])
    v_now = (float(upto1[-1][4]) - float(upto1[-VELOCITY_BARS][4])) / atr
    v_prev = (float(upto1[-VELOCITY_BARS][4]) -
              float(upto1[-2 * VELOCITY_BARS][4])) / atr
    lo, hi = _swing_range(upto4)
    span = hi - lo
    pos = (price - lo) / span if span > 0 else 0.5
    touches, touch_weight = _level_touch(upto4, lo, hi, price, atr)
    hour = _dt.datetime.fromtimestamp(t / 1000, _dt.timezone.utc).hour
    session = ("asia" if 0 <= hour < 8 else
               "europe" if 8 <= hour < 16 else "us")
    regime = "trend" if path >= EFFICIENCY_TREND else "range"
    pos_bucket = "low" if pos < 0.25 else "high" if pos > 0.75 else "mid"
    return {
        "complete": True, "t": t, "price": round(price, 6),
        "atr": round(atr, 6),
        "dominant_scale_h": dominant, "scale_scores": scale_scores,
        "path_efficiency": round(path, 4),
        "velocity": round(v_now, 4), "acceleration": round(v_now - v_prev, 4),
        "position": round(pos, 4), "position_bucket": pos_bucket,
        "swing_low": round(lo, 6), "swing_high": round(hi, 6),
        "level_touches": touches, "level_touch_weight": touch_weight,
        "session": session, "regime": regime,
        "state_id": "%dh|%s|%s|%s" % (dominant, regime, pos_bucket, session),
    }


RULE_VERSION = "v2"


def admit(state: dict, direction: str, horizon_h: int = 4) -> tuple[bool, str]:
    """Rule-based, explainable admission. Only removes; never invents a trade.

    v2 fixes a logical inversion in v1: a dominant scale LONGER than the
    holding horizon is evidence of a durable trend (follow it), whereas v1
    rejected it. Short dominant scales are the noisy case and now require
    structural-edge confirmation. v1 admitted only 4 training trades.
    """
    if not state or not state.get("complete"):
        return False, "时空状态样本不足"
    if direction not in ("long", "short"):
        return False, "无明确方向"
    dom = state["dominant_scale_h"]
    vel, acc = state["velocity"], state["acceleration"]
    trend_dir = 1 if vel > 0 else -1 if vel < 0 else 0
    want = 1 if direction == "long" else -1
    if abs(vel) > 3.0:
        return False, "速度 %.2f 过大，追高/杀跌风险" % vel
    if state["regime"] == "trend":
        if trend_dir and trend_dir != want:
            return False, "逆主导尺度方向（速度 %.2f）" % vel
        if acc * want < -1.5:
            return False, "加速度强反转（%.2f）" % acc
        if dom < horizon_h and state["position_bucket"] == "mid":
            # A short dominant scale is noisy: demand a structural edge.
            return False, "短尺度 %dh 主导且位于区间中部" % dom
    else:
        b = state["position_bucket"]
        if b == "mid":
            # Mid-range trades are allowed only with agreeing velocity AND
            # non-diverging acceleration (a nascent move, not a coin flip).
            if trend_dir != want:
                return False, "区间中部且速度不配合"
            if acc * want < 0:
                return False, "区间中部且加速度背离"
        else:
            if (direction == "long" and b != "low") or \
                    (direction == "short" and b != "high"):
                return False, "区间边缘与方向不匹配（%s）" % b
        if state["level_touch_weight"] < 0.25:
            return False, "关键位缺少时间加权验证"
    return True, "v2 主导尺度%dh·%s·位置%s·速度%.2f·加速度%.2f" % (
        dom, state["regime"], state["position_bucket"], vel, acc)


def describe(state: dict) -> str:
    """One-line Chinese explanation for the UI / audit log."""
    if not state or not state.get("complete"):
        return "时空状态不可用（历史不足）"
    return ("时空：主导尺度 %dh（各尺度效率 %s），%s，结构分位 %.2f，"
            "速度 %.2f ATR/6h，加速度 %.2f，关键位触碰 %d 次(衰减权重 %.2f)，%s 时段"
            % (state["dominant_scale_h"],
               "/".join("%dh=%.2f" % (k, v)
                        for k, v in sorted(state["scale_scores"].items())),
               state["regime"], state["position"], state["velocity"],
               state["acceleration"], state["level_touches"],
               state["level_touch_weight"], state["session"]))


def build_mask(ks4, ks1, lo: int = 60) -> dict:
    """Precompute one state per 4h bar index (research replay)."""
    out = {}
    for i in range(max(lo, 20), len(ks4)):
        out[int(ks4[i][0])] = build_state(ks4, ks1, i)
    return out
