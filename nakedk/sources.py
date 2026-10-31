"""Multi-exchange price aggregation with robust, liquidity-weighted estimation.

Weight design:
  w_i = liquidity_share_i * quality_i
  quality: 1.0 within 0.3% of median, 0.25 within 1%, 0 beyond 1%
  cap: no single source above 60% of total weight (redistribute twice)
Outputs: weighted price, median, max deviation, effective source count,
confidence label and per-source weights — all auditable.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from urllib.request import Request, urlopen

UA = {"User-Agent": "naked-k-analysis/2.0"}
PROXY = os.environ.get("NK_PROXY") or "http://127.0.0.1:7890"
BLOCK_TTL = 1800
MAX_SHARE = 0.60
DEV_BAND = 0.003
HARD_DEV = 0.010
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
    from .http import get_json as _http_get_json
    return _http_get_json(url, timeout=timeout, max_retries=2,
                          proxy=PROXY if proxy else None)


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


SOURCES = (_binance, _gate, _okx, _kucoin, _bitget)


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def combine(rows, max_share: float = MAX_SHARE) -> dict:
    """Pure weighting step: no IO, fully testable."""
    rows = [dict(r) for r in rows if r.get("price") and r["price"] > 0]
    if not rows:
        return {}
    total_vol = sum(float(r.get("quote_vol") or 0.0) for r in rows)
    if total_vol <= 0:
        total_vol = float(len(rows))
        for r in rows:
            r["quote_vol"] = 1.0
    med = _median([r["price"] for r in rows])
    for r in rows:
        dev = abs(r["price"] / med - 1.0)
        r["dev_pct"] = round(dev * 100.0, 4)
        if dev > HARD_DEV:
            q = 0.0
        elif dev > DEV_BAND:
            q = 0.25
        else:
            q = 1.0
        r["quality"] = q
        r["liq_share"] = round(float(r["quote_vol"]) / total_vol, 4)
        r["w"] = r["liq_share"] * q
    W = sum(r["w"] for r in rows)
    if W <= 0:
        for r in rows:
            r["w"] = r["liq_share"] if r["liq_share"] > 0 else 0.0
        W = sum(r["w"] for r in rows) or 1.0
    for _ in range(2):
        over = [r for r in rows if r["w"] / W > max_share]
        if not over:
            break
        cap = max_share * W
        excess = sum(r["w"] - cap for r in over)
        for r in over:
            r["w"] = cap
        rest = [r for r in rows if r not in over]
        rest_sum = sum(r["w"] for r in rest)
        if rest_sum > 0:
            for r in rest:
                r["w"] += excess * r["w"] / rest_sum
        W = sum(r["w"] for r in rows) or 1.0
    weighted = sum(r["price"] * r["w"] for r in rows) / W
    for r in rows:
        r["weight"] = round(r["w"] / W, 4)
    sw = sum(r["weight"] ** 2 for r in rows)
    eff_n = round((1.0 / sw) if sw else 0.0, 2)
    top_share = max(r["weight"] for r in rows)
    max_dev = max(r["dev_pct"] for r in rows)
    if len(rows) >= 4 and max_dev <= 0.15 and top_share <= MAX_SHARE + 1e-6:
        conf = "high"
    elif len(rows) >= 3 and max_dev <= 0.50:
        conf = "medium"
    else:
        conf = "low"
    return {
        "n": len(rows),
        "weighted": round(weighted, 4),
        "median": round(med, 4),
        "max_dev_pct": round(max_dev, 4),
        "effective_n": eff_n,
        "top_share": round(top_share, 4),
        "confidence": conf,
        "sources": rows,
    }


def aggregate(symbol: str) -> dict:
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
    return combine(rows)
