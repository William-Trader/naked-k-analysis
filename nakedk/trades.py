"""Real order flow: aggregated trades and book snapshot (not kline proxies)."""
from __future__ import annotations

import json
from urllib.request import Request, urlopen

BASE = "https://data-api.binance.vision"


def _get(path: str, timeout: int = 10):
    req = Request(BASE + path, headers={"User-Agent": "naked-k-analysis/2.0"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def sweeps(rows, atr_value):
    """Consecutive same-side taker flow that moves price in under a minute."""
    if len(rows) < 10 or not atr_value:
        return []
    quotes = [float(r["p"]) * float(r["q"]) for r in rows]
    avg = sum(quotes) / len(quotes) or 1.0
    out, i = [], 0
    while i < len(rows) - 4:
        side = not rows[i].get("m")
        j, quote, t0 = i, 0.0, int(rows[i]["T"])
        while j < len(rows) and (not rows[j].get("m")) == side \
                and int(rows[j]["T"]) - t0 <= 60_000:
            quote += quotes[j]
            j += 1
        if j - i >= 5 and quote >= 3 * avg:
            move = abs(float(rows[j - 1]["p"]) - float(rows[i]["p"]))
            if move >= 0.3 * atr_value:
                out.append({"side": "buy" if side else "sell", "trades": j - i,
                            "quote": round(quote, 0),
                            "move_atr": round(move / atr_value, 2)})
        i = max(j, i + 1)
    return out


def absorption(rows, atr_value, bar_range):
    """One price absorbs most of the flow while the bar barely moves."""
    if not rows or not atr_value or not bar_range:
        return None
    if bar_range >= 0.5 * atr_value:
        return None
    buckets, total = {}, 0.0
    for r in rows:
        q = float(r["p"]) * float(r["q"])
        total += q
        p = round(float(r["p"]), 2)
        buckets[p] = buckets.get(p, 0.0) + q
    if not total:
        return None
    top_price, top_quote = max(buckets.items(), key=lambda kv: kv[1])
    share = top_quote / total
    if share < 0.4:
        return None
    count = sum(1 for r in rows if round(float(r["p"]), 2) == top_price)
    return {"count": count, "quote": round(top_quote, 0),
            "price": top_price, "share": round(share, 2)}


def trades(symbol: str, limit: int = 1000, atr_value=None, bar_range=None) -> dict:
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
        "sweeps": sweeps(rows, atr_value),
        "absorb": absorption(rows, atr_value, bar_range),
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
