"""Multi-exchange free-source price aggregation, weighted by 24h quote volume.

Reachability on the production host (2026-10-27):
  binance, gate  -> direct
  okx, kucoin, bitget -> via W1 mihomo tunnel at 127.0.0.1:17890
  bybit -> 403 even through the proxy (regional block); kept but skipped fast
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from urllib.request import Request, urlopen

UA = {"User-Agent": "naked-k-analysis/2.0"}
PROXY = os.environ.get("NK_PROXY") or "http://127.0.0.1:17890"
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


def _blocked(name: str) -> bool:
    t = _BLOCKED.get(name)
    return bool(t and time.time() - t < BLOCK_TTL)


def _mark(name: str) -> None:
    _BLOCKED[name] = time.time()
    try:
        os.makedirs(os.path.dirname(_CACHE_FILE) or ".", exist_ok=True)
        with open(_CACHE_FILE, "w", encoding="utf-8") as fh:
            json.dump(_BLOCKED, fh)
    except Exception:
        pass


def _get(url: str, timeout: int = 6, proxy: bool = False):
    req = Request(url, headers=UA)
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
        with opener.open(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _base(symbol: str) -> str:
    return symbol[:-4] if symbol.endswith("USDT") else symbol


def _binance(symbol: str) -> dict:
    d = _get(f"https://data-api.binance.vision/api/v3/ticker/24hr?symbol={symbol}")
    return {"source": "binance", "price": float(d["lastPrice"]),
            "quote_vol": float(d["quoteVolume"])}


def _gate(symbol: str) -> dict:
    d = _get(f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={_base(symbol)}_USDT")
    row = d[0] if isinstance(d, list) else d
    return {"source": "gate", "price": float(row["last"]),
            "quote_vol": float(row.get("quote_volume") or 0.0)}


def _okx(symbol: str) -> dict:
    d = _get(f"https://www.okx.com/api/v5/market/ticker?instId={_base(symbol)}-USDT",
             timeout=6, proxy=True)
    row = d["data"][0]
    return {"source": "okx", "price": float(row["last"]),
            "quote_vol": float(row.get("volCcy24h") or 0.0)}


def _kucoin(symbol: str) -> dict:
    d = _get(f"https://api.kucoin.com/api/v1/market/stats?symbol={_base(symbol)}-USDT",
             timeout=6, proxy=True)
    row = d["data"]
    return {"source": "kucoin", "price": float(row["last"]),
            "quote_vol": float(row.get("volValue") or 0.0)}


def _bitget(symbol: str) -> dict:
    d = _get(f"https://api.bitget.com/api/v2/spot/market/tickers?symbol={symbol}",
             timeout=6, proxy=True)
    row = d["data"][0]
    return {"source": "bitget", "price": float(row["lastPr"]),
            "quote_vol": float(row.get("quoteVolume") or row.get("usdtVolume") or 0.0)}


def _bybit(symbol: str) -> dict:
    d = _get(f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}",
             timeout=3, proxy=True)
    row = d["result"]["list"][0]
    return {"source": "bybit", "price": float(row["lastPrice"]),
            "quote_vol": float(row.get("turnover24h") or 0.0)}


SOURCES = (_binance, _gate, _okx, _kucoin, _bitget)


def aggregate(symbol: str) -> dict:
    """Weighted price across reachable sources; blocked venues skipped for 30 min."""
    rows = []
    for fn in SOURCES:
        name = fn.__name__.lstrip("_")
        if _blocked(name):
            continue
        try:
            r = fn(symbol)
            if r["price"] > 0:
                rows.append(r)
        except urllib.error.HTTPError:
            continue
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
