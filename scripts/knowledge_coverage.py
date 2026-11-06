# -----------------------------------------------------------------
# scripts/knowledge_coverage.py - naked-k-analysis knowledge coverage audit
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-389AFEB5
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
# -*- coding: utf-8 -*-
"""Audit that the distilled knowledge base covers every taught topic.

Each topic lists alternative keyword sets; a topic counts as covered when at
least one hit exists in a knowledge/*.md module for every required group.
Pure stdlib, read-only, exits 1 when a topic is missing so CI fails.

Usage:
    python3 scripts/knowledge_coverage.py [--json]
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = os.path.join(ROOT, "knowledge")

# topic -> list of keyword groups; every group needs one hit.
TOPICS = {
    "市场结构/四支柱": [["四支柱", "四根底层支柱", "支柱", "market structure"], ["always", "Always-In"]],
    "市场周期": [["市场周期"], ["突破", "通道"], ["交易区间", "TR"]],
    "趋势": [["趋势"], ["更高高点", "HH", "higher high"]],
    "通道/微通道": [["通道"], ["微通道", "micro channel", "窄通道"]],
    "交易区间": [["交易区间", "TR"], ["区间边缘", "区间中部", "边缘"]],
    "突破": [["突破"], ["跟进", "follow-through"]],
    "失败突破/陷阱": [["失败突破", "假突破"], ["陷阱"]],
    "回调与数K": [["回调"], ["H1", "H2", "L1", "L2", "数K"]],
    "信号K/入场K": [["信号K"], ["入场K", "信号棒", "signal bar"]],
    "反转": [["反转"], ["MTR", "主要趋势反转"]],
    "楔形": [["楔形", "wedge"]],
    "三角形": [["三角形", "triangle"]],
    "双顶双底": [["双顶", "DT"], ["双底", "DB"]],
    "头肩": [["头肩", "head and shoulders", "HS"]],
    "圆弧顶底": [["圆弧", "rounded"]],
    "高潮": [["高潮", "climax"]],
    "最终旗形": [["最终旗形", "final flag"]],
    "测量移动": [["测量移动", "measured move", "MM"]],
    "支撑阻力/关键位": [["支撑", "阻力"], ["关键位", "磁吸", "前高", "前低"]],
    "订单流/量价": [["订单流", "order flow"], ["量能", "volume", "vol_z"]],
    "筹码/主力": [["筹码", "吸筹", "派发"], ["扫单", "吸收", "stop run"]],
    "多周期/时间框架": [["多周期", "时间框架"], ["1d", "4h", "1h"]],
    "开盘/时段/缺口": [["开盘"], ["时段", "session"], ["缺口", "gap"]],
    "止损/实际风险": [["止损"], ["实际风险", "滑点", "成本"]],
    "头寸规模/组合风险": [["头寸"], ["0.25%", "0.5%", "风险预算"], ["相关", "组合"]],
    "交易者方程/概率": [["交易者方程", "trader equation"], ["概率", "胜率"]],
    "证据/回测方法": [["回测", "walk-forward"], ["Wilson", "样本"], ["成本", "12bp"]],
    "执行/心理": [["执行", "纪律"], ["情绪", "心理"], ["连亏", "亏损"]],
    "输出模板/评审": [["输出模板", "模板"], ["评审", "rubric", "评分"]],
    "术语映射": [["术语"], ["映射", "taxonomy", "引擎"]],
}

MIN_MODULES = 20


def load_modules() -> dict:
    out = {}
    for name in sorted(os.listdir(KB)):
        if name.endswith(".md") and name != "README.md":
            with open(os.path.join(KB, name), encoding="utf-8") as fh:
                out[name] = fh.read()
    return out


def audit() -> dict:
    mods = load_modules()
    blob = "\n".join(mods.values()).lower()
    rows = []
    for topic, groups in TOPICS.items():
        hits = []
        for group in groups:
            found = [k for k in group if k.lower() in blob]
            hits.append(found[0] if found else None)
        rows.append({
            "topic": topic,
            "covered": all(hits),
            "matched": hits,
        })
    missing = [r["topic"] for r in rows if not r["covered"]]
    return {
        "modules": len(mods),
        "min_modules": MIN_MODULES,
        "topics": len(rows),
        "covered": len(rows) - len(missing),
        "coverage_pct": round((len(rows) - len(missing)) / len(rows) * 100, 1),
        "missing": missing,
        "rows": rows,
    }


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    res = audit()
    if "--json" in argv:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        for r in res["rows"]:
            flag = "OK " if r["covered"] else "GAP"
            print(f"{flag} {r['topic']:22s} {r['matched']}")
        print(f"\nmodules={res['modules']} topics={res['topics']} "
              f"coverage={res['coverage_pct']}%")
        if res["missing"]:
            print("MISSING: " + ", ".join(res["missing"]))
    ok = not res["missing"] and res["modules"] >= MIN_MODULES
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
