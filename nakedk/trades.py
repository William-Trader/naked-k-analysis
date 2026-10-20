"""Real order flow: aggregated trades and book snapshot (not kline proxies)."""
from __future__ import annotations

import json
from urllib.request import Request, urlopen

BASE = "https://data-api.binance.vision"


def _get(path: str, timeout: int = 10):
    req = Request(BASE + path, headers={"User-Agent": "naked-k-analysis/2.0"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def trades(symbol: str, limit: int = 1000) -> dict:
    rows = _get(f"/api/v3/aggTrades?symbol={symbol}&limit={limit}")
    buy = sell = 0.0
    sizes = []
    for r in rows:
        quote = float(r["p"]) * float(r["q"])
        if r.get("m"):
            sell += quote
        else:
            buy += quote
        sizes.append(quote)
    total = buy + sell
    if not total:
        return {}
    sizes.sort()
    p99 = sizes[max(0, int(len(sizes) * 0.99) - 1)] if sizes else 0.0
    big = [s for s in sizes if s >= p99 and s > 0]
    return {
        "n": len(rows),
        "delta": round((buy - sell) / total, 3),
        "avg": round(total / len(rows), 2) if rows else 0.0,
        "max": round(max(sizes), 2) if sizes else 0.0,
        "p99": round(p99, 2),
        "big": len(big),
    }


def book(symbol: str, limit: int = 100, band: float = 0.01) -> dict:
    d = _get(f"/api/v3/depth?symbol={symbol}&limit={limit}")
    bids = [(float(p), float(q)) for p, q in d.get("bids", [])]
    asks = [(float(p), float(q)) for p, q in d.get("asks", [])]
    if not bids or not asks:
        return {}
    mid = (bids[0][0] + asks[0][0]) / 2.0
    lo, hi = mid * (1 - band), mid * (1 + band)
    bid_q = sum(q for p, q in bids if p >= lo)
    ask_q = sum(q for p, q in asks if p <= hi)
    total = bid_q + ask_q or 1.0
    return {
        "imbalance": round((bid_q - ask_q) / total, 3),
        "bid_q": round(bid_q, 0),
        "ask_q": round(ask_q, 0),
        "spread_bp": round((asks[0][0] - bids[0][0]) / mid * 10000, 2),
    }
