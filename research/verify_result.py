# -----------------------------------------------------------------
# research/verify_result.py - out-of-sample robustness verification
# (c) 2026 William-Trader (https://github.com/William-Trader)
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# -----------------------------------------------------------------
"""Stress-test the candidate selected by run_backtest.py.

Selection used TRAIN/VALIDATION only. This script asks a different question:
does the chosen configuration still beat the baseline when we perturb costs,
symbols, time windows and its own parameters? A result that only survives the
exact configuration used to pick it is overfitting, not an improvement.

Usage:
    PYTHONPATH=. python3 research/verify_result.py
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from nakedk.backtest import _precompute, _simulate, _stats  # noqa: E402
from run_backtest import (COST_BPS, HORIZON, SYMBOLS, TRAIN_END, VAL_END,  # noqa: E402
                          _data_fingerprint, _eval, _segment, _snapshot,
                          robustness, RESULTS_DIR)


def _load_chosen():
    p = os.path.join(RESULTS_DIR, "backtest_2.2.0.json")
    with open(p, encoding="utf-8") as fh:
        r = json.load(fh)
    if not r.get("adoption", {}).get("adopt_as_new_default"):
        return None, r
    c = r["chosen"]
    return (c["name"], c["gate"], c["params"]), r


def main() -> int:
    chosen, report = _load_chosen()
    if chosen is None:
        print("no candidate was adopted; nothing to verify")
        return 0
    name, gate, params = chosen
    print(f"verifying {name} (gate={gate}, params={params})", flush=True)
    data = {}
    for sym in SYMBOLS:
        ks = _snapshot(sym, "4h")
        path = _snapshot(sym, "1h")
        lo, hi = _segment(ks, 0, len(ks))
        data[sym] = (ks, path, _precompute(ks, lo, hi), lo, hi)
    test_a, test_b = int(data[SYMBOLS[0]][4] * VAL_END), data[SYMBOLS[0]][4]

    def run(g, p, cost, syms, a, b, folds=2):
        rows = []
        for sym in syms:
            ks, path, feats, _, _ = data[sym]
            rows.append(_eval(ks, path, feats, a, b, g, p, folds=folds))
        n = sum(r["trades"] for r in rows)
        avg = sum((r["avg_ret"] or 0) * r["trades"] for r in rows) / max(1, n)
        hits = sum((r["hit_rate"] or 0) * r["trades"] for r in rows) / max(1, n)
        pooled = {"trades": n, "avg_ret": round(avg, 4),
                  "hit_rate": round(hits, 2),
                  "max_drawdown": round(min((r["max_drawdown"] or 0)
                                            for r in rows), 2),
                  "sharpe_per_trade": round(sum((r["sharpe_per_trade"] or 0)
                                                for r in rows) / len(rows), 3),
                  "positive_folds": sum(r["positive_folds"] for r in rows),
                  "folds": sum(r["folds"] for r in rows),
                  "wilson_low": round(min(r["wilson_low"] for r in rows), 2)}
        pooled["robustness"] = robustness(pooled)
        return pooled

    scenarios = []

    def add(label, **kw):
        cost = kw.pop("cost", COST_BPS)
        syms = kw.pop("syms", SYMBOLS)
        a, b = kw.pop("range", (test_a, test_b))
        p_override = kw.pop("params_override", params)
        # cost is applied by temporarily overriding the module constant used
        # by _eval (single-threaded research script, restored immediately).
        import run_backtest as rb
        old = rb.COST_BPS
        rb.COST_BPS = cost
        try:
            base = run(None, None, cost, syms, a, b)
            cand = run(gate, p_override, cost, syms, a, b)
        finally:
            rb.COST_BPS = old
        win = (cand["avg_ret"] > base["avg_ret"]
               and cand["robustness"] > base["robustness"])
        scenarios.append({"scenario": label, "cost_bps": cost,
                          "symbols": list(syms), "range": [a, b],
                          "baseline": base, "candidate": cand,
                          "candidate_wins": bool(win)})
        print(f"  {label:<34} base={base['avg_ret']:>7}% "
              f"cand={cand['avg_ret']:>7}% "
              f"dd {base['max_drawdown']}->{cand['max_drawdown']}  "
              f"{'WIN' if win else 'lose'}", flush=True)

    add("reference (12bp, 2 symbols)")
    for c in (16, 20, 25):
        add(f"cost {c}bp", cost=c)
    for s in SYMBOLS:
        add(f"{s} only", syms=(s,))
    mid = (test_a + test_b) // 2
    add("test first half", range=(test_a, mid))
    add("test second half", range=(mid, test_b))
    for a in (20, 24):
        p = dict(params); p["adx_min"] = a
        add(f"neighbour adx_min={a}", params_override=p)
    for s in (1.25, 1.75):
        p = dict(params); p["stop_atr"] = s
        add(f"neighbour stop_atr={s}", params_override=p)

    wins = sum(1 for x in scenarios if x["candidate_wins"])
    out = {
        "generated_at": int(time.time() * 1000),
        "data": _data_fingerprint(),
        "candidate": {"name": name, "gate": gate, "params": params},
        "scenarios": scenarios,
        "win_count": wins, "total": len(scenarios),
        "win_rate": round(100.0 * wins / len(scenarios), 1),
        "verdict": ("robust across perturbations" if wins >= len(scenarios) * 0.7
                    else "NOT robust: improvement is configuration-sensitive; "
                         "do not promote to production defaults"),
    }
    path = os.path.join(RESULTS_DIR, "verification_2.2.0.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"\nwins {wins}/{len(scenarios)} ({out['win_rate']}%) -> {out['verdict']}")
    print("report:", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
