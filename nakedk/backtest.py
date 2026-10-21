# -----------------------------------------------------------------
# nakedk/backtest.py - naked-k-analysis core price-action engine
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-45E4B101
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
"""Walk-forward backtest with intrabar path and realistic costs."""
from __future__ import annotations

import math
import time

from .features import features_from_klines
from .fetch import get_json
from .signals import stance

BAR_MS = {"1h": 3600_000, "4h": 4 * 3600_000}
DEFAULT_COST_BPS = 12.0


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


def _path_slice(path_ks, start_ts: int, end_ts: int):
    return [k for k in path_ks if start_ts < int(k[0]) <= end_ts]


def _passes_gate(f, s, gate):
    if not gate:
        return True
    if gate == "quality":
        adx = f.get("adx14") or 0.0
        slope = f.get("adx_slope") or 0.0
        overlap = f.get("overlap") or 0.0
        return adx >= 25 and slope >= 0 and overlap < 0.5
    if gate == "quality_soft":
        adx = f.get("adx14") or 0.0
        slope = f.get("adx_slope") or 0.0
        overlap = f.get("overlap") or 0.0
        return adx >= 20 and slope >= -1.0 and overlap < 0.65
    return True


def _simulate(ks, lo: int, hi: int, horizon: int, cost_bps: float, path_ks=None,
              gate=None, tag_setups: bool = False, params=None) -> list:
    trades = []
    for i in range(lo, hi):
        window = ks[: i + 1][-200:]
        try:
            f = features_from_klines(window)
        except ValueError:
            continue
        s = stance(f)
        if s["direction"] not in ("long", "short"):
            continue
        if not _passes_gate(f, s, gate):
            continue
        entry = float(ks[i][4])
        if params:
            atr = f.get("atr14") or 0.0
            if (f.get("adx14") or 0.0) < params.get("adx_min", 0):
                continue
            if atr:
                if s["direction"] == "long":
                    s["stop"] = entry - params.get("stop_atr", 1.5) * atr
                    s["target"] = entry + params.get("target_atr", 3.0) * atr
                else:
                    s["stop"] = entry + params.get("stop_atr", 1.5) * atr
                    s["target"] = entry - params.get("target_atr", 3.0) * atr
        setup = None
        if tag_setups:
            try:
                from .patterns import arbitrate, detect as detect_patterns
                arb = arbitrate(detect_patterns(window, f), f)
                setup = (arb.get("primary") or {}).get("type")
            except Exception:
                setup = None
        entry = float(ks[i][4])
        exit_ = float(ks[i + horizon][4])
        stop, target = s.get("stop"), s.get("target")
        gross = None
        hit_stop = hit_target = False
        if path_ks and stop and target:
            bars = _path_slice(path_ks, int(ks[i][0]),
                               int(ks[i + horizon][0]))
            for k in bars:
                high, low = float(k[2]), float(k[3])
                if s["direction"] == "long":
                    if low <= stop:
                        hit_stop = True
                        break
                    if high >= target:
                        hit_target = True
                        break
                else:
                    if high >= stop:
                        hit_stop = True
                        break
                    if low <= target:
                        hit_target = True
                        break
        if hit_stop:
            gross = (stop - entry) / entry * 100.0 if s["direction"] == "long" \
                else (entry - stop) / entry * 100.0
        elif hit_target:
            gross = (target - entry) / entry * 100.0 if s["direction"] == "long" \
                else (entry - target) / entry * 100.0
        else:
            raw = (exit_ / entry - 1.0) * 100.0
            gross = raw if s["direction"] == "long" else -raw
        net = gross - cost_bps / 100.0
        trades.append({
            "ts": ks[i][0], "direction": s["direction"],
            "confidence": s["confidence"], "gross_ret": round(gross, 3),
            "signed_ret": round(net, 3), "hit": net > 0,
            "hit_stop": hit_stop, "hit_target": hit_target,
            "setup": setup,
        })
    return trades


def _group_by(trades, key):
    out = {}
    for t in trades:
        out.setdefault(t.get(key) or "NONE", []).append(t)
    return out


DEFAULT_GRID = [{"stop_atr": s, "target_atr": t, "adx_min": a}
                for s in (1.0, 1.5, 2.0)
                for t in (2.0, 3.0, 4.0)
                for a in (18, 20, 22)]


def optimize(symbols, days: int = 365, folds: int = 8,
             cost_bps: float = DEFAULT_COST_BPS, grid=None,
             horizon: int = 1) -> list:
    """Walk-forward parameter search; ranks by fold consistency, not best fold."""
    grid = grid or DEFAULT_GRID
    data = {s: (fetch_history(s, "4h", days), fetch_history(s, "1h", days))
            for s in symbols}
    out = []
    for params in grid:
        rows = []
        for sym, (ks, path_ks) in data.items():
            lo = min(60, max(0, len(ks) // 4))
            hi = max(lo, len(ks) - horizon)
            span = hi - lo
            nf = max(2, min(int(folds), 12))
            for k in range(nf):
                a = lo + span * k // nf
                b = lo + span * (k + 1) // nf
                trades = _simulate(ks, a, b, horizon, cost_bps, path_ks,
                                   None, False, params)
                rows.append(_stats(trades))
        hits = [r["hit_rate"] for r in rows if r["hit_rate"] is not None]
        avgs = [r["avg_ret"] for r in rows if r["avg_ret"] is not None]
        mean_avg = sum(avgs) / len(avgs) if avgs else None
        sd = ((sum((x - mean_avg) ** 2 for x in avgs) / len(avgs)) ** 0.5
              if avgs and len(avgs) > 1 else 0.0)
        t_stat = (mean_avg / (sd / len(avgs) ** 0.5)) if sd and avgs else 0.0
        positive = sum(1 for x in avgs if x > 0)
        out.append({
            "params": params,
            "mean_hit": round(sum(hits) / len(hits), 1) if hits else None,
            "mean_avg": round(mean_avg, 3) if mean_avg is not None else None,
            "positive_folds": positive,
            "total_folds": len(avgs),
            "t_stat": round(t_stat, 2),
        })
    out.sort(key=lambda r: (r["positive_folds"], r["mean_avg"] or -9), reverse=True)
    return out


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

    sharpe = _sharpe([t["signed_ret"] for t in trades]) if trades else None
    return {
        "trades": len(trades),
        "hit_rate": (round(100.0 * sum(1 for t in trades if t["hit"]) / len(trades), 1)
                     if trades else None),
        "avg_ret": (round(sum(t["signed_ret"] for t in trades) / len(trades), 3)
                    if trades else None),
        "cum_return": round((equity[-1] - 1.0) * 100.0, 2) if equity else None,
        "max_drawdown": round(_max_drawdown(equity), 2) if equity else None,
        "sharpe_per_trade": round(sharpe, 3) if sharpe is not None else None,
        "stop_rate": (round(100.0 * sum(1 for t in trades if t["hit_stop"]) / len(trades), 1)
                      if trades else None),
        "long": sub_stats([t for t in trades if t["direction"] == "long"]),
        "short": sub_stats([t for t in trades if t["direction"] == "short"]),
        "by_setup": {k: sub_stats(v) for k, v in sorted(
            _group_by(trades, "setup").items()) if v},
    }


def run(symbol: str, days: int = 365, horizon: int = 1, warmup: int = 60,
        cost_bps: float = DEFAULT_COST_BPS, intrabar: bool = True, gate=None,
        tag_setups: bool = False) -> dict:
    ks = fetch_history(symbol, "4h", days)
    path_ks = fetch_history(symbol, "1h", days) if intrabar else None
    lo = min(warmup, max(0, len(ks) // 4))
    hi = max(lo, len(ks) - horizon)
    trades = _simulate(ks, lo, hi, horizon, cost_bps, path_ks, gate, tag_setups)
    out = {
        "symbol": symbol, "days": days, "bars": len(ks),
        "cost_bps": cost_bps, "intrabar": intrabar, "gate": gate,
        "trade_fraction": round(100.0 * len(trades) / max(1, hi - lo), 1),
    }
    out.update(_stats(trades))
    return out


def walk_forward(symbol: str, days: int = 365, folds: int = 4, horizon: int = 1,
                 warmup: int = 60, cost_bps: float = DEFAULT_COST_BPS,
                 intrabar: bool = True, gate=None, tag_setups: bool = False,
                 params=None) -> dict:
    ks = fetch_history(symbol, "4h", days)
    path_ks = fetch_history(symbol, "1h", days) if intrabar else None
    lo = min(warmup, max(0, len(ks) // 4))
    hi = max(lo, len(ks) - horizon)
    span = hi - lo
    folds = max(2, min(int(folds), 8))
    results = []
    for k in range(folds):
        a = lo + span * k // folds
        b = lo + span * (k + 1) // folds
        trades = _simulate(ks, a, b, horizon, cost_bps, path_ks, gate,
                           tag_setups, params)
        row = {"fold": k + 1, "bars": b - a}
        row.update(_stats(trades))
        results.append(row)
    positive = sum(1 for r in results if (r["avg_ret"] or 0) > 0)
    scored = [r["hit_rate"] for r in results if r["hit_rate"] is not None]
    return {
        "symbol": symbol, "days": days, "folds": folds, "horizon": horizon,
        "cost_bps": cost_bps, "intrabar": intrabar, "gate": gate, "bars": len(ks),
        "fold_results": results, "positive_folds": positive,
        "fold_stability": round(positive / len(results) * 100.0, 1),
        "hit_rate_spread": (round(max(scored) - min(scored), 1) if len(scored) > 1 else None),
        "mean_hit_rate": round(sum(scored) / len(scored), 1) if scored else None,
    }
