# -----------------------------------------------------------------
# nakedk/knowledge.py - naked-k-analysis knowledge search + rubric
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-KNOWL0001
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
# -*- coding: utf-8 -*-
"""Knowledge base search + briefing rubric auto-scorer (stdlib only).

Two capabilities:
  1. search(query) — full-text search over the knowledge/*.md modules,
     ranked by term frequency; returns file / line / snippet so every claim
     is citable.
  2. score_briefing(text) — score a briefing against the 12-dimension
     practitioner rubric (knowledge/09-review-rubric.md), 0-5 each, total 60.
     It checks for *presence* of the required elements, not whether the call
     was right (that is the trader review, which is human).
"""
from __future__ import annotations

import os
import re

_KB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                       "knowledge")

# 12 rubric dimensions -> keyword signals. Each dimension scores:
#   5 = strong marker, 3 = weak marker, 0 = absent.
_RUBRIC = [
    ("高周期上下文", ["高周期", "日线", "1d", "daily"], ["周线", "4h 与日"]),
    ("市场周期阶段", ["突破", "紧通道", "宽通道", "通道", "TR", "区间整理"],
     ["趋势", "区间", "过渡"]),
    ("Always-In", ["always", "Always-In", "强K", "反转三步"], ["方向"]),
    ("位置", ["pos20", "前高", "前低", "VWAP"], ["位置", "边缘"]),
    ("Setup 命名", ["H1", "H2", "L1", "L2", "DB", "DT", "楔形", "MTR",
                   "头肩", "BLSHS", "旗形", "最终旗形"], ["Setup", "setup"]),
    ("信号K质量", ["收盘", "实体", "影线", "跟随"], ["信号K", "K线"]),
    ("触发价", ["触发"], []),
    ("失效价", ["失效"], []),
    ("目标/MM", ["目标", "测量移动", "MM"], []),
    ("R:R", ["R:R", "R:R"], []),
    ("主力/订单流", ["吸筹", "派发", "扫单", "背离", "资金费率", "订单流",
                    "量能", "缩量"], ["主力"]),
    ("反方情景", ["反方", "备选", "否则", "反之", "失效条件", "概率区间"],
                 ["概率"]),
]


def knowledge_dir() -> str:
    return _KB_DIR


def search(query: str, limit: int = 8):
    """Full-text search over knowledge/*.md, ranked by term frequency.

    Returns a list of {file, line, snippet, score}. Case-insensitive; splits
    the query into words and scores a file by how many distinct words it
    matches, then returns matching lines with the most hits first.
    """
    words = [w for w in re.split(r"[\s,，。;；]+", query.lower()) if w]
    if not words:
        return []
    results = []
    for name in sorted(os.listdir(_KB_DIR)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(_KB_DIR, name)
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except Exception:
            continue
        distinct = 0
        for w in words:
            if any(w in ln.lower() for ln in lines):
                distinct += 1
        if not distinct:
            continue
        # collect matching lines
        hits = []
        for ln in lines:
            n = sum(1 for w in words if w in ln.lower())
            if n:
                hits.append((n, ln))
        hits.sort(key=lambda x: -x[0])
        results.append({
            "file": name,
            "score": distinct,
            "top": [{"line": ln} for _n, ln in hits[:2]],
        })
    results.sort(key=lambda r: -r["score"])
    return results[:limit]


def score_briefing(text: str) -> dict:
    """Score a briefing against the 12-dimension rubric.

    Returns {total, dimensions: [{name, score}], verdict}. Presence-based:
    it measures completeness, not correctness.
    """
    t = (text or "").lower()
    dims = []
    total = 0
    for name, strong, weak in _RUBRIC:
        if any(s.lower() in t for s in strong):
            score = 5
        elif any(s.lower() in t for s in weak):
            score = 3
        else:
            score = 0
        dims.append({"name": name, "score": score})
        total += score
    verdict = ("practitioner-grade" if total >= 50
               else "adequate" if total >= 40 else "rework")
    return {"total": total, "dimensions": dims, "verdict": verdict}
