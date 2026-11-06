# -----------------------------------------------------------------
# scripts/accuracy_audit.py - naked-k-analysis accuracy audit
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-2B092075
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
# -*- coding: utf-8 -*-
"""Reproducible accuracy audit for the deterministic stance engine.

Unlike `nakedk backtest` (which simulates stops/targets), this audit answers
one narrow question: when the engine says long/short on a 4h bar, what
happened over the next N bars after realistic cost? It reports the number
that matters (average net return) next to the hit rate and a Wilson lower
bound, split by the conditions that produced the trade, plus per-third
consistency so a single lucky stretch cannot masquerade as an edge.

Usage:
    PYTHONPATH=. python3 scripts/accuracy_audit.py [SYMBOL ...] \
        [--days 150] [--cost-bps 12] [--json]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from nakedk.backtest import fetch_history          # noqa: E402
from nakedk.features import features_from_klines  # noqa: E402
from nakedk.signals import stance                 # noqa: E402

BUCKETS = {
    "adx": ((0, 20), (20, 25), (25, 30), (30, 100)),
    "overlap": ((0, 0.55), (0.55, 0.65), (0.65, 0.70), (0.70, 1.01)),
    "vol_z": ((-99, 0), (0, 0.5), (0.5, 1.5), (1.5, 99)),
    "pos20": ((0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 1.01)),
}


def wilson(k: int, n: int, z: float = 1.96) -> float:
    if n <= 0:
        return 0.0
    p = k / n
    den = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - margin) / den


def collect(symbol: str, days: int, horizon: int, cost_pct: float):
    ks = fetch_history(symbol, "4h", days)
    rows = []
    for i in range(60, len(ks) - horizon):
        try:
            f = features_from_klines(ks[: i + 1][-200:])
        except ValueError:
            continue
        s = stance(f)
        if s["direction"] not in ("long", "short"):
            continue
        entry, exit_ = float(ks[i][4]), float(ks[i + horizon][4])
        if not entry:
            continue
        raw = (exit_ / entry - 1.0) * 100.0
        net = (raw if s["direction"] == "long" else -raw) - cost_pct
        rows.append({
            "i": i, "dir": s["direction"], "conf": s["confidence"],
            "net": net,
            "adx": f.get("adx14"), "overlap": f.get("overlap"),
            "vol_z": f.get("vol_z"), "pos20": f.get("pos20"),
        })
    return rows


def summarize(rows, filt=None) -> dict | None:
    sub = [r for r in rows if filt is None or filt(r)]
    n = len(sub)
    if not n:
        return None
    nets = [r["net"] for r in sub]
    hits = sum(1 for x in nets if x > 0)
    lo_i = min(r["i"] for r in rows)
    hi_i = max(r["i"] for r in rows) + 1
    third = max(1, (hi_i - lo_i) // 3)
    folds = []
    for j in range(3):
        a, b = lo_i + j * third, lo_i + (j + 1) * third
        part = [r["net"] for r in sub
                if a <= r["i"] < (b if j < 2 else hi_i)]
        folds.append(round(sum(part) / len(part), 3) if part else None)
    return {
        "n": n,
        "hit_rate": round(hits / n * 100, 1),
        "wilson_lb": round(wilson(hits, n) * 100, 1),
        "avg_net_pct": round(sum(nets) / n, 3),
        "folds": folds,
    }


def audit_symbol(symbol, days, horizon, cost_bps):
    rows = collect(symbol, days, horizon, cost_bps / 100.0)
    out = {"symbol": symbol, "days": days, "horizon": horizon,
           "cost_bps": cost_bps, "trades": len(rows),
           "overall": summarize(rows),
           "by_direction": {d: summarize(rows, lambda r, d=d: r["dir"] == d)
                            for d in ("long", "short")},
           "buckets": {}}
    for key, bands in BUCKETS.items():
        out["buckets"][key] = {}
        for lo, hi in bands:
            label = f"{lo}-{hi}"
            out["buckets"][key][label] = summarize(
                rows, lambda r, k=key, lo=lo, hi=hi:
                r[k] is not None and lo <= r[k] < hi)
    return out


def print_symbol(res):
    o = res["overall"]
    print(f"\n== {res['symbol']}  {res['days']}d  4h x{res['horizon']}  "
          f"{res['cost_bps']}bp  n={res['trades']}")
    if not o:
        print("   no directional signals")
        return
    print(f"   overall hit={o['hit_rate']:.1f}%  WilsonLB={o['wilson_lb']:.1f}%"
          f"  avg_net={o['avg_net_pct']:+.3f}%  folds={o['folds']}")
    for d, v in res["by_direction"].items():
        if v:
            print(f"   {d:5s} hit={v['hit_rate']:.1f}% avg={v['avg_net_pct']:+.3f}%"
                  f" n={v['n']}")
    for key, bands in res["buckets"].items():
        for label, v in bands.items():
            if v:
                print(f"   {key:8s} {label:12s} n={v['n']:3d} "
                      f"hit={v['hit_rate']:5.1f}% avg={v['avg_net_pct']:+.3f}% "
                      f"folds={v['folds']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="stance accuracy audit")
    ap.add_argument("symbols", nargs="*", default=["BTCUSDT", "ETHUSDT"])
    ap.add_argument("--days", type=int, default=150)
    ap.add_argument("--horizon", type=int, default=1)
    ap.add_argument("--cost-bps", type=float, default=12.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    results = [audit_symbol(s, args.days, args.horizon, args.cost_bps)
               for s in (args.symbols or ["BTCUSDT", "ETHUSDT"])]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print_symbol(r)
        print("\nNOTE: in-sample audit. Positive average net is not a promise "
              "of future returns; check folds and Wilson bound.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
