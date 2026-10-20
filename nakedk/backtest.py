# -----------------------------------------------------------------
# nakedk/backtest.py - naked-k-analysis core price-action engine
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-45E4B101
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
"""Walk-forward backtest of the deterministic stance engine.

The backtest is intentionally simple and honest: at every 4h bar it
computes the same features the live bot uses, asks the same `stance`
engine for a direction, and measures the realised signed return at a
fixed horizon. No parameter fitting, no look-ahead. Costs (fees +
slippage) are deducted per trade so the result is not flattered.
"""
from __future__ import annotations

import math
import time

from .features import features_from_klines
from .fetch import get_json
from .signals import stance

BAR_MS = {"1h": 3600_000, "4h": 4 * 3600_000}
DEFAULT_COST_BPS = 10.0  # taker fee 4bp x2 + slippage ~1bp x2


def fetch_history(symbol: str, interval: str = "4h", days: int = 365):
    end = int(time.time() * 1000)
    start = end - days * 86_400_000
    out, cursor = [], start
    step = BAR_MS[interval]
    while cursor < end:
        rows = get_json(
            f"/api/v3/klines?symbol={symbol}&interval={interval}"
            f"&startTime={cursor}&limit=1000"
        )
        if not rows:
            break
        out.extend(rows)
        cursor = rows[-1][0] + step
        if len(rows) < 1000:
            break
    return out


def _max_drawdown(equity: list) -> float:
    peak, mdd = equity[0] if equity else 1.0, 0.0
    for v in equity:
        peak = max(peak, v)
        if peak:
            mdd = min(mdd, v / peak - 1.0)
    return mdd * 100.0


def _sharpe(returns: list):
    if len(returns) < 3:
        return None
    mu = sum(returns) / len(returns)
    sd = math.sqrt(sum((r - mu) ** 2 for r in returns) / len(returns))
    return None if sd == 0 else mu / sd


def _simulate(ks, lo: int, hi: int, horizon: int, cost_bps: float) -> list:
    trades = []
    for i in range(lo, hi):
        window = ks[: i + 1][-200:]
        try:
            f = features_from_klines(window)
        except ValueError:
            continue
        s = stance(f)
        if s["direction"] == "neutral":
            continue
        entry = float(ks[i][4])
        exit_ = float(ks[i + horizon][4])
        raw = (exit_ / entry - 1.0) * 100.0
        gross = raw if s["direction"] == "long" else -raw
        net = gross - cost_bps / 100.0
        trades.append({
            "ts": ks[i][0], "direction": s["direction"],
            "confidence": s["confidence"], "raw_ret": raw,
            "gross_ret": gross, "signed_ret": net,
            "hit": net > 0,
        })
    return trades


def _stats(trades: list) -> dict:
    equity, value = [], 1.0
    for t in trades:
        value *= 1.0 + t["signed_ret"] / 100.0
        equity.append(value)

    def sub_stats(sub):
        if not sub:
            return {"n": 0, "hit_rate": None, "avg_ret": None}
        return {
            "n": len(sub),
            "hit_rate": round(100.0 * sum(1 for t in sub if t["hit"]) / len(sub), 1),
            "avg_ret": round(sum(t["signed_ret"] for t in sub) / len(sub), 3),
        }

    return {
        "trades": len(trades),
        "hit_rate": (round(100.0 * sum(1 for t in trades if t["hit"]) / len(trades), 1)
                     if trades else None),
        "avg_ret": (round(sum(t["signed_ret"] for t in trades) / len(trades), 3)
                    if trades else None),
        "cum_return": round((equity[-1] - 1.0) * 100.0, 2) if equity else None,
        "max_drawdown": round(_max_drawdown(equity), 2) if equity else None,
        "sharpe_per_trade": (round(_sharpe([t["signed_ret"] for t in trades]), 3)
                             if trades else None),
        "long": sub_stats([t for t in trades if t["direction"] == "long"]),
        "short": sub_stats([t for t in trades if t["direction"] == "short"]),
    }


def run(symbol: str, days: int = 365, horizon: int = 1, warmup: int = 60,
        cost_bps: float = DEFAULT_COST_BPS) -> dict:
    ks = fetch_history(symbol, "4h", days)
    lo = min(warmup, max(0, len(ks) // 4))
    hi = max(lo, len(ks) - horizon)
    trades = _simulate(ks, lo, hi, horizon, cost_bps)
    out = {
        "symbol": symbol,
        "days": days,
        "bars": len(ks),
        "cost_bps": cost_bps,
        "trade_fraction": round(100.0 * len(trades) / max(1, hi - lo), 1),
    }
    out.update(_stats(trades))
    return out


def walk_forward(symbol: str, days: int = 365, folds: int = 4, horizon: int = 1,
                 warmup: int = 60, cost_bps: float = DEFAULT_COST_BPS) -> dict:
    """Split the sample into consecutive out-of-sample folds.

    Consistency across folds matters more than any single fold: a rule
    that only works in one regime is noise, not edge.
    """
    ks = fetch_history(symbol, "4h", days)
    lo = min(warmup, max(0, len(ks) // 4))
    hi = max(lo, len(ks) - horizon)
    span = hi - lo
    folds = max(2, min(int(folds), 8))
    results = []
    for k in range(folds):
        a = lo + span * k // folds
        b = lo + span * (k + 1) // folds
        trades = _simulate(ks, a, b, horizon, cost_bps)
        row = {"fold": k + 1, "bars": b - a}
        row.update(_stats(trades))
        results.append(row)
    positive = sum(1 for r in results if (r["avg_ret"] or 0) > 0)
    scored = [r["hit_rate"] for r in results if r["hit_rate"] is not None]
    return {
        "symbol": symbol,
        "days": days,
        "folds": folds,
        "horizon": horizon,
        "cost_bps": cost_bps,
        "bars": len(ks),
        "fold_results": results,
        "positive_folds": positive,
        "fold_stability": round(positive / len(results) * 100.0, 1),
        "hit_rate_spread": (round(max(scored) - min(scored), 1) if len(scored) > 1 else None),
        "mean_hit_rate": round(sum(scored) / len(scored), 1) if scored else None,
    }

