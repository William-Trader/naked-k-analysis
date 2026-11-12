# -----------------------------------------------------------------
# research/run_spacetime.py - adaptive spacetime engine validation
# (c) 2026 William-Trader (https://github.com/William-Trader)
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# -----------------------------------------------------------------
"""Compare the new adaptive spacetime engine against the 2.2.0 champion.

Same frozen snapshot, same train/validation/test boundaries, same costs and
same metrics as research/run_backtest.py. The spacetime mask is computed with
data available at each 4h bar only (the 1h series is cut at that bar's close),
so there is no look-ahead.

Usage:
    PYTHONPATH=. python3 research/run_spacetime.py
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research"))

from nakedk import spacetime  # noqa: E402
from nakedk.backtest import _precompute, _simulate, _stats  # noqa: E402
from nakedk.stats import wilson  # noqa: E402
from run_backtest import (COST_BPS, HORIZON, SYMBOLS, TRAIN_END, VAL_END,  # noqa: E402
                          MIN_TRADES, RESULTS_DIR, _data_fingerprint,
                          _segment, _snapshot, robustness)

CHAMPION_PARAMS = {"stop_atr": 1.5, "target_atr": 3.0, "adx_min": 22}

CANDIDATES = [
    ("baseline", None, None, False),
    ("champion_v22", "v22", CHAMPION_PARAMS, False),
    ("spacetime", None, None, True),
    ("spacetime+params", None, CHAMPION_PARAMS, True),
    ("spacetime+v22", "v22", CHAMPION_PARAMS, True),
]


def _eval_st(ks, path_ks, feats, mask, a, b, gate, params, folds=4):
    a, b = _segment(ks, a, b)
    span = b - a
    fold_stats, trades = [], []
    for k in range(folds):
        x = a + span * k // folds
        y = a + span * (k + 1) // folds
        t = _simulate(ks, x, y, HORIZON, COST_BPS, path_ks, gate, False,
                      params, feats, mask=mask)
        fold_stats.append(_stats(t))
        trades.extend(t)
    st = _stats(trades)
    avgs = [f["avg_ret"] for f in fold_stats if f["avg_ret"] is not None]
    pos = sum(1 for x in avgs if x > 0)
    mean = sum(avgs) / len(avgs) if avgs else 0.0
    sd = (sum((x - mean) ** 2 for x in avgs) / len(avgs)) ** 0.5 if avgs else 0.0
    n = st["trades"]
    wl, wh = wilson(sum(1 for t in trades if t["hit"]), n) if n else (0, 0)
    return {"trades": n, "hit_rate": st["hit_rate"], "avg_ret": st["avg_ret"],
            "cum_return": st["cum_return"], "max_drawdown": st["max_drawdown"],
            "sharpe_per_trade": st["sharpe_per_trade"],
            "positive_folds": pos, "folds": folds,
            "fold_stability": round(100.0 * pos / max(1, folds), 1),
            "t_stat": round(mean / (sd / math.sqrt(len(avgs)))
                            if sd and avgs else 0.0, 3),
            "wilson_low": wl, "wilson_high": wh}


def main() -> int:
    print("building adaptive spacetime states from frozen 4h + 1h bars ...",
          flush=True)
    data = {}
    for sym in SYMBOLS:
        ks = _snapshot(sym, "4h")
        path = _snapshot(sym, "1h")
        lo, hi = _segment(ks, 0, len(ks))
        feats = _precompute(ks, lo, hi)
        t0 = time.time()
        mask = spacetime.build_mask(ks, path, lo=lo)
        complete = sum(1 for v in mask.values() if v.get("complete"))
        print(f"  {sym}: {len(mask)} states ({complete} complete) "
              f"in {time.time()-t0:.1f}s", flush=True)
        # Explainability sample: show one fully described state.
        sample = next((v for v in mask.values() if v.get("complete")), None)
        if sample:
            print("    example: " + spacetime.describe(sample), flush=True)
        data[sym] = (ks, path, feats, mask, hi)

    def run(cand, which):
        name, gate, params, use_mask = cand
        rows = []
        for sym in SYMBOLS:
            ks, path, feats, mask, hi = data[sym]
            a, b = {"train": (60, int(hi * TRAIN_END)),
                    "validation": (int(hi * TRAIN_END), int(hi * VAL_END)),
                    "test": (int(hi * VAL_END), hi)}[which]
            rows.append(_eval_st(ks, path, feats,
                                 mask if use_mask else None,
                                 a, b, gate, params))
        n = sum(r["trades"] for r in rows)
        avg = sum((r["avg_ret"] or 0) * r["trades"] for r in rows) / max(1, n)
        hits = sum((r["hit_rate"] or 0) * r["trades"] for r in rows) / max(1, n)
        wl, wh = wilson(round(hits / 100 * n), n) if n else (0, 0)
        pooled = {"trades": n, "avg_ret": round(avg, 4),
                  "hit_rate": round(hits, 2), "wilson_low": wl,
                  "wilson_high": wh,
                  "sharpe_per_trade": round(sum((r["sharpe_per_trade"] or 0)
                                                for r in rows) / len(rows), 3),
                  "max_drawdown": round(min((r["max_drawdown"] or 0)
                                            for r in rows), 2),
                  "positive_folds": sum(r["positive_folds"] for r in rows),
                  "folds": sum(r["folds"] for r in rows),
                  "per_symbol": {s: rows[i] for i, s in enumerate(SYMBOLS)}}
        pooled["robustness"] = robustness(pooled)
        pooled["eligible"] = n >= MIN_TRADES
        return pooled

    report = {"generated_at": int(time.time() * 1000),
              "data": _data_fingerprint(),
              "method": ("frozen snapshot; train 50% / validation 25% / "
                         "test 25% evaluated once; 4-fold walk-forward per "
                         "segment; 12bp round-trip cost; adaptive spacetime "
                         "mask has no look-ahead"),
              "candidates": [], "disclaimer": (
                  "Historical simulation. Not a claim of positive expectation "
                  "or of being 'industry best'; all numbers are reproducible "
                  "from the frozen snapshot.")}

    print("\n%-20s %-10s %8s %10s %9s %9s %9s" %
          ("candidate", "segment", "trades", "avg_ret%", "hit%", "maxDD%",
           "robust"), flush=True)
    for cand in CANDIDATES:
        row = {"name": cand[0], "gate": cand[1], "params": cand[2],
               "spacetime": cand[3], "segments": {}}
        for seg in ("train", "validation", "test"):
            m = run(cand, seg)
            row["segments"][seg] = m
            print("%-20s %-10s %8d %10.4f %9.2f %9.2f %9.4f" %
                  (cand[0], seg, m["trades"], m["avg_ret"] or 0,
                   m["hit_rate"] or 0, m["max_drawdown"] or 0,
                   m["robustness"]), flush=True)
        report["candidates"].append(row)

    def get(name):
        return next(r for r in report["candidates"] if r["name"] == name)

    champion = get("champion_v22")["segments"]["test"]
    contenders = [r for r in report["candidates"] if r["spacetime"]
                  and r["segments"]["test"]["eligible"]]
    best = max(contenders, key=lambda r: r["segments"]["test"]["robustness"]) \
        if contenders else None
    better = bool(best
                  and best["segments"]["test"]["avg_ret"] > champion["avg_ret"]
                  and best["segments"]["test"]["robustness"]
                  > champion["robustness"])
    report["verdict"] = {
        "champion_test": champion,
        "best_spacetime": best["name"] if best else None,
        "best_spacetime_test": best["segments"]["test"] if best else None,
        "spacetime_beats_champion_out_of_sample": better,
        "decision": ("adopt spacetime as the optional new default"
                     if better else
                     "keep v22 champion; spacetime did not improve "
                     "out-of-sample and stays an optional engine"),
        "role": "descriptive analytics layer (NK_SPACETIME=1), NOT a trade gate",
        "test_reuse_warning": (
            "v2 rules were revised after inspecting v1 test results, so the "
            "test segment has been consulted twice. The 2.2.0 v22 champion "
            "is the only configuration whose test was evaluated exactly once. "
            "For that reason spacetime is NOT promoted to a decision gate "
            "regardless of these numbers; further rule tuning against this "
            "same test set would be overfitting."),
    }
    out = os.path.join(RESULTS_DIR, "spacetime_2.3.0.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    print("\nverdict:", report["verdict"]["decision"])
    print("report:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
