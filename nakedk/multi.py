# -----------------------------------------------------------------
# nakedk/multi.py - naked-k-analysis multi-interval combination
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-6B8E951C
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
# -*- coding: utf-8 -*-
"""Combine interval-level reads into one tradable opinion.

Default profile: 4h (context / bias) + 15m (execution / timing).
The combination is deliberately conservative:

* agreement raises confidence, conflict caps it;
* a neutral context interval cannot be outvoted by a fast interval into an
  aggressive call - the fast interval only sets timing;
* every output carries the per-interval inputs so the UI can show the split
  instead of hiding it behind one number.
"""
from __future__ import annotations

WEIGHTS = {"1d": 0.20, "4h": 0.55, "15m": 0.30, "1h": 0.25, "30m": 0.20}

CN = {"long": "偏多", "short": "偏空", "neutral": "中性"}


def _sign(d):
    return 1 if d == "long" else (-1 if d == "short" else 0)


def combine(analyses: dict, mode: str = "multi") -> dict:
    """analyses: {interval: {"stance": {...}, "trend": {...}, ...}}"""
    analyses = analyses or {}
    rows = []
    for interval, a in sorted(analyses.items()):
        st = (a or {}).get("stance") or {}
        d = st.get("direction") or "neutral"
        w = WEIGHTS.get(interval, 0.25)
        rows.append({
            "interval": interval,
            "direction": d,
            "direction_cn": CN.get(d, d),
            "confidence": st.get("confidence"),
            "grade": st.get("grade"),
            "score": (a or {}).get("trend", {}).get("score"),
            "structure": ((a or {}).get("structure") or {}).get("state"),
            "weight": w,
        })
    if not rows:
        return {"direction": "neutral", "direction_cn": "中性", "confidence": 0,
                "grade": "—", "agreement": "no_data", "conflict": False,
                "reasons": ["无可用周期分析"], "intervals": [], "score": 0.0}

    if mode == "single" or len(rows) == 1:
        r = rows[0]
        return {
            "direction": r["direction"],
            "direction_cn": r["direction_cn"],
            "confidence": r.get("confidence") or 50,
            "grade": r.get("grade") or "C",
            "agreement": "single",
            "conflict": False,
            "reasons": [f"单周期模式：{r['interval']} {r['direction_cn']}"],
            "intervals": rows,
            "score": _sign(r["direction"]) * ((r.get("confidence") or 50) - 50) / 20.0,
        }

    total_w = sum(r["weight"] for r in rows) or 1.0
    score = 0.0
    for r in rows:
        conf = float(r.get("confidence") or 50)
        strength = max(0.2, (conf - 35.0) / 30.0)  # 35..65 -> 0.2..1.0
        score += r["weight"] / total_w * _sign(r["direction"]) * strength

    directions = {r["direction"] for r in rows if r["direction"] != "neutral"}
    conflict = len(directions) > 1
    direction = "long" if score > 0.12 else ("short" if score < -0.12 else "neutral")
    if conflict:
        direction = "neutral"

    base = 50.0 + min(18.0, abs(score) * 30.0)
    if conflict:
        base = min(base, 55.0)
    # explicit high-timeframe veto: 4h opposite the fast read = no trade
    ctx = analyses.get("4h") or analyses.get("1d") or {}
    ctx_dir = ((ctx.get("stance") or {}).get("direction") or "neutral")
    if direction != "neutral" and ctx_dir not in ("neutral", direction):
        direction = "neutral"
        base = min(base, 50.0)
    if direction == "neutral":
        agreement = "conflict" if conflict else "no_edge"
    elif conflict:
        agreement = "conflict"
    else:
        agreement = "aligned"
    confidence = int(max(35, min(68, round(base))))
    grade = "A" if confidence >= 60 else ("B" if confidence >= 52 else "C")
    reasons = []
    for r in rows:
        reasons.append("%s %s 置信%s · 结构%s" % (
            r["interval"], r["direction_cn"], r.get("confidence") or "—",
            r.get("structure") or "—"))
    if conflict:
        reasons.append("周期方向冲突：只做观察，不追单")
    if direction == "neutral" and not conflict:
        reasons.append("无方向优势：等待结构确认")

    return {
        "direction": direction,
        "direction_cn": CN.get(direction, direction),
        "confidence": confidence,
        "grade": grade,
        "agreement": agreement,
        "conflict": conflict,
        "score": round(score, 3),
        "reasons": reasons,
        "intervals": rows,
    }
