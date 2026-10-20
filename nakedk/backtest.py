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
fixed horizon. No parameter fitting, no look-ahead.
"""
from __future__ import annotations

import math
import time

from .features import features_from_klines
from .fetch import get_json
from .signals import stance

BAR_MS = {"1h": 3600_000, "4h": 4 * 3600_000}


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


def _max_drawdown(equity: list[float]) -> float:
    peak, mdd = equity[0] if equity else 1.0, 0.0
    for v in equity:
        peak = max(peak, v)
        if peak:
            mdd = min(mdd, v / peak - 1.0)
    return mdd * 100.0


def _sharpe(returns: list[float]) -> float | None:
    if len(returns) < 3:
        return None
    mu = sum(returns) / len(returns)
    sd = math.sqrt(sum((r - mu) ** 2 for r in returns) / len(returns))
    return None if sd == 0 else mu / sd


def run(symbol: str, days: int = 365, horizon: int = 1, warmup: int = 60) -> dict:
    ks = fetch_history(symbol, "4h", days)
    trades = []
    for i in range(warmup, len(ks) - horizon):
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
        signed = raw if s["direction"] == "long" else -raw
        trades.append({
            "ts": ks[i][0], "direction": s["direction"],
            "confidence": s["confidence"], "raw_ret": raw, "signed_ret": signed,
            "hit": raw > 0 if s["direction"] == "long" else raw < 0,
        })

    equity, value = [], 1.0
    for t in trades:
        value *= 1.0 + t["signed_ret"] / 100.0
        equity.append(value)

    def stats(sub):
        if not sub:
            return {"n": 0, "hit_rate": None, "avg_ret": None}
        return {
            "n": len(sub),
            "hit_rate": round(100.0 * sum(1 for t in sub if t["hit"]) / len(sub), 1),
            "avg_ret": round(sum(t["signed_ret"] for t in sub) / len(sub), 3),
        }

    directional = trades
    return {
        "symbol": symbol,
        "days": days,
        "bars": len(ks),
        "trades": len(directional),
        "trade_fraction": round(100.0 * len(directional) / max(1, len(ks) - warmup), 1),
        "hit_rate": round(100.0 * sum(1 for t in directional if t["hit"]) / len(directional), 1) if directional else None,
        "avg_ret": round(sum(t["signed_ret"] for t in directional) / len(directional), 3) if directional else None,
        "cum_return": round((equity[-1] - 1.0) * 100.0, 2) if equity else None,
        "max_drawdown": round(_max_drawdown(equity), 2) if equity else None,
        "sharpe_per_trade": round(_sharpe([t["signed_ret"] for t in directional]), 3) if directional else None,
        "long": stats([t for t in directional if t["direction"] == "long"]),
        "short": stats([t for t in directional if t["direction"] == "short"]),
    }
