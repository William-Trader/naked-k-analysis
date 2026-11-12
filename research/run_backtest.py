# -----------------------------------------------------------------
# research/run_backtest.py - naked-k-analysis reproducible research harness
# (c) 2026 William-Trader (https://github.com/William-Trader)
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# -----------------------------------------------------------------
"""Walk-forward research harness on a FROZEN OHLCV snapshot.

Design rules (deliberate, do not "optimize" them away):

1. Three-way split: TRAIN (first 50%) selects, VALIDATION (50-75%) governs
   iteration / early stopping, TEST (last 25%) is reported ONCE and never
   used to pick anything. Choosing parameters on the test set is leakage.
2. The objective is risk-adjusted *stability*, not maximum return:
   positive-fold ratio, t-like consistency, drawdown and sample size all
   matter. A candidate with fewer than MIN_TRADES samples is disqualified.
3. Gates are the SAME rules the live 2.2.0 confirmation gate uses, so a
   research result is a statement about production logic, not a toy model.
4. Iteration stops when validation robustness stops improving for `patience`
   consecutive waves, or after `max_waves`. More search after that is
   overfitting, not progress.
5. Costs are charged on every trade (12bp round trip). No claim of positive
   expectation is made by this script; see the printed disclaimer.

Usage:
    PYTHONPATH=. python3 research/run_backtest.py
    PYTHONPATH=. python3 research/run_backtest.py --max-waves 2 --quick
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from nakedk.backtest import (DEFAULT_COST_BPS, _precompute, _simulate,  # noqa: E402
                             _stats)
from nakedk.stats import wilson  # noqa: E402

DATA_DIR = os.path.join(ROOT, "research", "data")
RESULTS_DIR = os.path.join(ROOT, "research", "results")
SYMBOLS = ("BTCUSDT", "ETHUSDT")
TRAIN_END, VAL_END = 0.50, 0.75
MIN_TRADES = 30
HORIZON = 1                      # one 4h bar
COST_BPS = DEFAULT_COST_BPS      # 12bp round trip
MAX_DD_CAP = 25.0                # % beyond which a candidate is disqualified


def _snapshot(symbol: str, interval: str):
    p = os.path.join(DATA_DIR, f"{symbol}_{interval}.json.gz")
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        return json.load(fh)["rows"]


def _data_fingerprint() -> dict:
    p = os.path.join(DATA_DIR, "manifest.json")
    with open(p, encoding="utf-8") as fh:
        m = json.load(fh)
    return {"days": m.get("days"), "base": m.get("base"),
            "sha256": hashlib.sha256(
                json.dumps(m["files"], sort_keys=True).encode()).hexdigest()[:16],
            "rows": {k: v["rows"] for k, v in m["files"].items()}}


def _segment(ks, a: int, b: int):
    return max(a, 60), max(a + 1, min(b, len(ks) - HORIZON - 1))


def _eval(ks, path_ks, feats, a: int, b: int, gate, params, folds: int = 4):
    a, b = _segment(ks, a, b)
    span = b - a
    fold_stats, trades = [], []
    for k in range(folds):
        x = a + span * k // folds
        y = a + span * (k + 1) // folds
        t = _simulate(ks, x, y, HORIZON, COST_BPS, path_ks, gate, False,
                      params, feats)
        fold_stats.append(_stats(t))
        trades.extend(t)
    st = _stats(trades)
    avgs = [f["avg_ret"] for f in fold_stats if f["avg_ret"] is not None]
    pos = sum(1 for x in avgs if x > 0)
    mean = sum(avgs) / len(avgs) if avgs else 0.0
    sd = (sum((x - mean) ** 2 for x in avgs) / len(avgs)) ** 0.5 if avgs else 0.0
    tstat = mean / (sd / math.sqrt(len(avgs))) if sd and avgs else 0.0
    n = st["trades"]
    hits = sum(1 for t in trades if t["hit"])
    wl, wh = wilson(hits, n) if n else (0.0, 0.0)
    return {
        "trades": n, "hit_rate": st["hit_rate"], "avg_ret": st["avg_ret"],
        "cum_return": st["cum_return"], "max_drawdown": st["max_drawdown"],
        "sharpe_per_trade": st["sharpe_per_trade"],
        "stop_rate": st["stop_rate"],
        "positive_folds": pos, "folds": folds,
        "fold_stability": round(100.0 * pos / max(1, folds), 1),
        "mean_fold_ret": round(mean, 4), "t_stat": round(tstat, 3),
        "wilson_low": wl, "wilson_high": wh,
    }


def robustness(m: dict) -> float:
    """Composite robustness score; penalties are continuous, not cliff-edged.

    A hard disqualification used to flatten every candidate to -1e9 on this
    dataset (a losing baseline accumulates >25% drawdown over 323 trades),
    which made ranking and early stopping meaningless. Penalties keep the
    ordering informative while still pushing toward small drawdowns and
    adequate sample sizes.
    """
    mdd = m["max_drawdown"] or 0.0
    stab = m["positive_folds"] / max(1, m["folds"])
    ret = math.tanh((m["avg_ret"] or 0.0) / 0.20)
    shp = math.tanh((m["sharpe_per_trade"] or 0.0) / 0.30)
    dd = max(0.0, 1.0 + mdd / MAX_DD_CAP)
    # Wilson lower bound rewards a hit rate that is statistically supported.
    hit = (m["wilson_low"] or 0.0) / 100.0
    score = (0.35 * stab + 0.25 * ret + 0.20 * shp
             + 0.10 * dd + 0.10 * hit)
    if m["trades"] < MIN_TRADES:
        score -= 0.5 * (1.0 - m["trades"] / max(1, MIN_TRADES))
    if mdd < -MAX_DD_CAP:
        score -= 0.5 * min(1.0, (abs(mdd) - MAX_DD_CAP) / MAX_DD_CAP)
    return round(score, 5)


def _candidates(quick: bool):
    gates = [("baseline", None), ("quality", "quality"),
             ("quality_soft", "quality_soft"), ("v22", "v22"),
             ("v22_strict", "v22_strict"), ("policy", "policy"),
             ("v22_policy", "v22_policy")]
    if quick:
        gates = gates[:4]
    wave1 = [(name, g, None) for name, g in gates]
    grids = [(1.5, 3.0, 20), (2.0, 3.0, 20), (1.5, 3.0, 22),
             (2.0, 4.0, 22), (1.0, 2.0, 25)]
    wave2 = [(f"v22_p{s}_{t}_{a}", "v22",
              {"stop_atr": s, "target_atr": t, "adx_min": a})
             for s, t, a in grids]
    wave3 = [(f"v22_policy_p{s}_{t}_{a}", "v22_policy",
              {"stop_atr": s, "target_atr": t, "adx_min": a})
             for s, t, a in grids[:3]]
    return [wave1, wave2, wave3]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-waves", type=int, default=3)
    ap.add_argument("--patience", type=int, default=1)
    ap.add_argument("--quick", action="store_true", help="smaller grid smoke run")
    ap.add_argument("--folds", type=int, default=4)
    args = ap.parse_args()

    os.makedirs(RESULTS_DIR, exist_ok=True)
    print("loading frozen snapshot ...", flush=True)
    data = {}
    for sym in SYMBOLS:
        ks = _snapshot(sym, "4h")
        path = _snapshot(sym, "1h")
        lo, hi = _segment(ks, 0, len(ks))
        t0 = time.time()
        feats = _precompute(ks, lo, hi)
        data[sym] = (ks, path, feats, lo, hi)
        print(f"  {sym}: {len(ks)} 4h bars, {len(path)} 1h bars, "
              f"{len(feats)} feature windows ({time.time()-t0:.1f}s)", flush=True)

    def run_segment(cand, which: str):
        name, gate, params = cand
        rows = []
        for sym, (ks, path, feats, lo, hi) in data.items():
            a, b = {"train": (lo, int(hi * TRAIN_END)),
                    "validation": (int(hi * TRAIN_END), int(hi * VAL_END)),
                    "test": (int(hi * VAL_END), hi)}[which]
            m = _eval(ks, path, feats, a, b, gate, params, args.folds)
            rows.append(m)
        # Pool both symbols into one decision: a result that only works on
        # BTC is not robust enough to ship.
        total = sum(r["trades"] for r in rows)
        avg = sum((r["avg_ret"] or 0) * r["trades"] for r in rows) / max(1, total)
        hits = sum((r["hit_rate"] or 0) * r["trades"] for r in rows) / max(1, total)
        wl, wh = wilson(round(hits / 100 * total), total) if total else (0, 0)
        pooled = {
            "trades": total, "avg_ret": round(avg, 4),
            "hit_rate": round(hits, 2), "wilson_low": wl, "wilson_high": wh,
            "sharpe_per_trade": round(sum((r["sharpe_per_trade"] or 0)
                                          for r in rows) / len(rows), 3),
            "max_drawdown": round(min((r["max_drawdown"] or 0) for r in rows), 2),
            "positive_folds": sum(r["positive_folds"] for r in rows),
            "folds": sum(r["folds"] for r in rows),
            "per_symbol": {s: rows[i] for i, s in enumerate(SYMBOLS)},
        }
        pooled["robustness"] = robustness(pooled)
        # Hard sample-size gate at the *selection* layer (separate from the
        # continuous penalty in robustness): a candidate with 6 validation
        # trades can post +1.9% by luck and must never win a wave.
        pooled["eligible"] = (pooled["trades"] >= MIN_TRADES)
        return pooled

    report = {
        "generated_at": int(time.time() * 1000),
        "data": _data_fingerprint(),
        "config": {"cost_bps": COST_BPS, "horizon_4h_bars": HORIZON,
                   "split": [TRAIN_END, VAL_END, 1.0], "folds": args.folds,
                   "min_trades": MIN_TRADES, "max_dd_cap_pct": MAX_DD_CAP,
                   "symbols": list(SYMBOLS)},
        "waves": [], "disclaimer": (
            "Historical simulation only. Costs are charged but liquidity, "
            "funding and execution risk are approximations. No claim of "
            "positive expectation or future performance is made."),
    }

    waves = _candidates(args.quick)[:args.max_waves]
    best, best_val, stale = None, -1e9, 0
    baseline_train = run_segment(("baseline", None, None), "train")
    print(f"baseline train: {baseline_train['trades']} trades, "
          f"avg {baseline_train['avg_ret']}% , hit {baseline_train['hit_rate']}%",
          flush=True)

    for wi, cands in enumerate(waves, 1):
        rows = []
        for cand in cands:
            tr = run_segment(cand, "train")
            va = run_segment(cand, "validation")
            rows.append({"name": cand[0], "gate": cand[1],
                         "params": cand[2], "train": tr, "validation": va})
            print(f"  wave{wi} {cand[0]:<24} train={tr['robustness']:.4f} "
                  f"val={va['robustness']:.4f} trades={tr['trades']}/"
                  f"{va['trades']} avg={va['avg_ret']}%", flush=True)
        eligible = [r for r in rows
                    if r["train"]["eligible"] and r["validation"]["eligible"]]
        excluded = [r["name"] for r in rows if r not in eligible]
        pool = eligible or rows
        pool.sort(key=lambda r: r["train"]["robustness"], reverse=True)
        winner = pool[0]
        improved = (winner["validation"]["eligible"]
                    and winner["validation"]["robustness"] > best_val + 1e-6)
        if improved:
            best, best_val = winner, winner["validation"]["robustness"]
            stale = 0
        else:
            stale += 1
        report["waves"].append({
            "wave": wi, "candidates": rows,
            "selected_on_train": winner["name"],
            "excluded_insufficient_sample": excluded,
            "validation_improved": improved,
            "best_validation_so_far": round(best_val, 5),
        })
        print(f"wave {wi} winner={winner['name']} improved={improved} "
              f"stale={stale}", flush=True)
        if stale > args.patience:
            print("early stop: validation robustness stopped improving; "
                  "further search would be overfitting.", flush=True)
            break

    if best is None:
        best = {"name": "baseline", "gate": None, "params": None}
    chosen = (best["name"], best["gate"], best["params"])
    # TEST is evaluated exactly once, after all decisions are frozen.
    base_test = run_segment(("baseline", None, None), "test")
    chosen_test = run_segment(chosen, "test")
    report["baseline"] = {"train": baseline_train, "test": base_test}
    report["chosen"] = {"name": chosen[0], "gate": chosen[1],
                        "params": chosen[2],
                        "validation": best.get("validation"),
                        "train": best.get("train"), "test": chosen_test}
    report["delta_test"] = {
        "avg_ret_pct_points": round((chosen_test["avg_ret"] or 0)
                                    - (base_test["avg_ret"] or 0), 4),
        "hit_rate_points": round((chosen_test["hit_rate"] or 0)
                                 - (base_test["hit_rate"] or 0), 2),
        "max_drawdown_points": round((chosen_test["max_drawdown"] or 0)
                                     - (base_test["max_drawdown"] or 0), 2),
        "trades_delta": chosen_test["trades"] - base_test["trades"],
    }

    # Adoption is an evidence decision, not a hope. A candidate is promoted
    # only if it beats the baseline on BOTH out-of-sample net return and the
    # composite robustness score with an adequate sample. Otherwise the
    # project keeps its existing defaults ("gates only remove trades").
    adopted = bool(
        chosen[0] != "baseline" and chosen_test["eligible"]
        and (chosen_test["avg_ret"] or 0) > (base_test["avg_ret"] or 0)
        and chosen_test["robustness"] > base_test["robustness"])
    report["adoption"] = {
        "adopt_as_new_default": adopted,
        "reason": ("out-of-sample return and robustness both improved with "
                   "adequate sample" if adopted else
                   "no candidate beat the baseline out-of-sample on both "
                   "return and robustness; keeping existing defaults is the "
                   "evidence-based choice (no positive expectation claimed)"),
        "test_baseline_robustness": base_test["robustness"],
        "test_chosen_robustness": chosen_test["robustness"],
    }

    out = os.path.join(RESULTS_DIR, "backtest_2.2.0.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    print("\n=== FINAL (TEST, evaluated once) ===")
    print(f"baseline : {base_test['trades']} trades, avg {base_test['avg_ret']}%, "
          f"hit {base_test['hit_rate']}%, mdd {base_test['max_drawdown']}%")
    print(f"chosen   : {chosen[0]} | {chosen_test['trades']} trades, "
          f"avg {chosen_test['avg_ret']}%, hit {chosen_test['hit_rate']}%, "
          f"mdd {chosen_test['max_drawdown']}%")
    print(f"delta    : {report['delta_test']}")
    print(f"adoption : {report['adoption']['adopt_as_new_default']} "
          f"- {report['adoption']['reason']}")
    print(f"report   : {out}")
    print("DISCLAIMER: " + report["disclaimer"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
