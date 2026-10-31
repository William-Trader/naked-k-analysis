# -----------------------------------------------------------------
# nakedk/score.py - naked-k-analysis core price-action engine
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-C43C0A6E
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
"""Outcome scoring for emitted signals.

Ledger records are JSONL objects:
  {"ts": "2026-10-20T09:00:00Z", "symbol": "BTCUSDT",
   "direction": "long|short|neutral", "confidence": 60, "horizon_h": 4}
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime
from urllib.request import Request, urlopen

BASE = "https://data-api.binance.vision"


def _ms(ts) -> int:
    if isinstance(ts, (int, float)):
        return int(ts)
    return int(datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp() * 1000)


def klines_1h(symbol: str, start_ms: int, end_ms: int):
    url = (f"{BASE}/api/v3/klines?symbol={symbol}&interval=1h"
           f"&startTime={start_ms}&endTime={end_ms}&limit=1000")
    req = Request(url, headers={"User-Agent": "naked-k-analysis/2.0"})
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def klines_1m(symbol: str, start_ms: int, end_ms: int, max_bars: int = 2000):
    """1m bars for intrabar ordering (stop vs target)."""
    out, cursor = [], start_ms
    while cursor < end_ms and len(out) < max_bars:
        url = (f"{BASE}/api/v3/klines?symbol={symbol}&interval=1m"
               f"&startTime={cursor}&endTime={end_ms}&limit=1000")
        req = Request(url, headers={"User-Agent": "naked-k-analysis/2.0"})
        with urlopen(req, timeout=20) as r:
            rows = json.loads(r.read().decode())
        if not rows:
            break
        out.extend(rows)
        cursor = rows[-1][0] + 60_000
        if len(rows) < 1000:
            break
    return out[:max_bars]


def _index_at(ks, ts: int):
    for i, k in enumerate(ks):
        if k[0] <= ts < k[0] + 3600_000:
            return i
    return None


def evaluate(record: dict) -> dict | None:
    ts = _ms(record["ts"])
    symbol = record["symbol"]
    horizon = int(record.get("horizon_h", 4))
    direction = record.get("direction", "neutral")
    ks = klines_1h(symbol, ts - 2 * 3600_000, ts + (horizon + 2) * 3600_000)
    i = _index_at(ks, ts)
    if i is None or i + horizon >= len(ks):
        return None
    entry = float(ks[i][4])
    exit_ = float(ks[i + horizon][4])
    raw = (exit_ / entry - 1.0) * 100.0
    signed = raw if direction == "long" else (-raw if direction == "short" else 0.0)
    hit = None
    if direction in ("long", "short"):
        hit = (raw > 0) if direction == "long" else (raw < 0)
    return {
        "ts": record["ts"], "symbol": symbol, "direction": direction,
        "confidence": record.get("confidence"), "horizon_h": horizon,
        "entry": entry, "exit": exit_, "raw_ret": raw,
        "signed_ret": signed, "hit": hit,
    }


def summarise(rows: list[dict]) -> dict:
    directional = [r for r in rows if r["direction"] in ("long", "short")]
    hits = [r for r in directional if r["hit"]]
    by_dir = {}
    for d in ("long", "short"):
        sub = [r for r in directional if r["direction"] == d]
        by_dir[d] = {
            "n": len(sub),
            "hit_rate": round(100 * sum(1 for r in sub if r["hit"]) / len(sub), 1) if sub else None,
            "avg_ret": round(statistics.mean(r["signed_ret"] for r in sub), 3) if sub else None,
        }
    buckets = {}
    for lo in (50, 55, 60, 65):
        sub = [r for r in directional if (r.get("confidence") or 0) // 5 * 5 == lo]
        if sub:
            buckets[f"{lo}-{lo + 4}"] = {
                "n": len(sub),
                "hit_rate": round(100 * sum(1 for r in sub if r["hit"]) / len(sub), 1),
            }
    return {
        "n": len(rows), "directional": len(directional),
        "hit_rate": round(100 * len(hits) / len(directional), 1) if directional else None,
        "avg_signed_ret": round(statistics.mean(r["signed_ret"] for r in directional), 3) if directional else None,
        "by_direction": by_dir, "calibration": buckets,
    }


def load_ledger(path: str) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out
