"""Multi-exchange free-source price aggregation, weighted by 24h quote volume."""
from __future__ import annotations

import json
import os
import time
from urllib.request import Request, urlopen

UA = {"User-Agent": "naked-k-analysis/2.0"}
BLOCK_TTL = 1800
_CACHE_FILE = os.environ.get("NK_BLOCK_FILE") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "state", "blocked_sources.json")


def _load_blocked():
    try:
        with open(_CACHE_FILE, encoding="utf-8") as fh:
            d = json.load(fh)
        now = time.time()
        return {k: v for k, v in d.items() if now - float(v) < BLOCK_TTL}
    except Exception:
        return {}


_BLOCKED = _load_blocked()


def _mark(name: str) -> None:
    _BLOCKED[name] = time.time()
    try:
        os.makedirs(os.path.dirname(_CACHE_FILE) or ".", exist_ok=True)
        with open(_CACHE_FILE, "w", encoding="utf-8") as fh:
            json.dump(_BLOCKED, fh)
    except Exception:
        pass


def _blocked(name: str) -> bool:
    t = _BLOCKED.get(name)
    return bool(t and time.time() - t < BLOCK_TTL)


def _get(url: str, timeout: int = 6):
    with urlopen(Request(url, headers=UA), timeout=timeout) as r:
        return json.loads(r.read().decode())


def _binance(symbol: str) -> dict:
    d = _get(f"https://data-api.binance.vision/api/v3/ticker/24hr?symbol={symbol}")
    return {"source": "binance", "price": float(d["lastPrice"]),
            "quote_vol": float(d["quoteVolume"])}


def _gate(symbol: str) -> dict:
    base = symbol[:-4] if symbol.endswith("USDT") else symbol
    d = _get(f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={base}_USDT")
    row = d[0] if isinstance(d, list) else d
    return {"source": "gate", "price": float(row["last"]),
            "quote_vol": float(row.get("quote_volume") or 0.0)}


def _bybit(symbol: str) -> dict:
    d = _get(f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}",
             timeout=2)
    row = d["result"]["list"][0]
    return {"source": "bybit", "price": float(row["lastPrice"]),
            "quote_vol": float(row.get("turnover24h") or 0.0)}


def _okx(symbol: str) -> dict:
    base = symbol[:-4] if symbol.endswith("USDT") else symbol
    d = _get(f"https://www.okx.com/api/v5/market/ticker?instId={base}-USDT", timeout=2)
    row = d["data"][0]
    return {"source": "okx", "price": float(row["last"]),
            "quote_vol": float(row.get("volCcy24h") or 0.0)}


SOURCES = (_binance, _gate, _bybit, _okx)


def aggregate(symbol: str) -> dict:
    """Weighted price across reachable sources; skips blocked venues for 30 min."""
    rows = []
    for fn in SOURCES:
        name = fn.__name__.lstrip("_")
        if _blocked(name):
            continue
        try:
            r = fn(symbol)
            if r["price"] > 0:
                rows.append(r)
        except Exception:
            _mark(name)
            continue
    if not rows:
        return {}
    total = sum(r["quote_vol"] for r in rows) or 1.0
    for r in rows:
        r["share"] = round(r["quote_vol"] / total, 3)
    weighted = sum(r["price"] * r["quote_vol"] for r in rows) / total
    prices = sorted(r["price"] for r in rows)
    med = prices[len(prices) // 2]
    dev = max(abs(r["price"] / med - 1.0) for r in rows) * 100.0
    return {"n": len(rows), "weighted": round(weighted, 2), "median": round(med, 2),
            "max_dev_pct": round(dev, 3), "sources": rows}
