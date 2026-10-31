# -----------------------------------------------------------------
# nakedk/markets.py - naked-k-analysis multi-market source base
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-2D9520FF
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
# -*- coding: utf-8 -*-
"""Multi-market source base: crypto (Binance) + metals / US indices / futures
(Yahoo Finance public chart API).

Realtime monitoring stays on the crypto majors (BTC / ETH). Everything else is
an *analysis source base*: the same engine (features, structure, patterns,
signals, backtest) runs on XAU, US equity indices and futures without change,
because every source normalises to the Binance kline shape

    [openTime_ms, open, high, low, close, volume, ...]

Nothing here is a hard dependency: if a source is unreachable the caller's
existing try/except paths degrade exactly as they do for crypto.
"""
from __future__ import annotations

from .http import get_json

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"

# friendly symbol -> (provider, provider ticker, market kind)
# - crypto majors are the realtime universe (Binance public data)
# - metals / indices / futures are the analysis source base (Yahoo public data)
UNIVERSE = {
    # crypto majors (realtime)
    "BTCUSDT": ("binance", "BTCUSDT", "crypto"),
    "ETHUSDT": ("binance", "ETHUSDT", "crypto"),
    "SOLUSDT": ("binance", "SOLUSDT", "crypto"),
    "BNBUSDT": ("binance", "BNBUSDT", "crypto"),
    "XRPUSDT": ("binance", "XRPUSDT", "crypto"),
    # precious metals
    "XAU": ("yahoo", "GC=F", "metal"),    # gold futures
    "XAG": ("yahoo", "SI=F", "metal"),    # silver futures
    "PLAT": ("yahoo", "PL=F", "metal"),   # platinum futures
    # US equity indices
    "SPX": ("yahoo", "^GSPC", "index"),   # S&P 500
    "NDX": ("yahoo", "^IXIC", "index"),   # Nasdaq Composite
    "DJI": ("yahoo", "^DJI", "index"),    # Dow Jones Industrial
    "RUT": ("yahoo", "^RUT", "index"),    # Russell 2000
    # futures (optional source base)
    "ES": ("yahoo", "ES=F", "future"),    # S&P 500 E-mini
    "NQ": ("yahoo", "NQ=F", "future"),    # Nasdaq-100 E-mini
    "YM": ("yahoo", "YM=F", "future"),    # Dow E-mini
    "CL": ("yahoo", "CL=F", "future"),    # WTI crude oil
    "GC": ("yahoo", "GC=F", "future"),    # gold (alias)
}

# approximate bars per 24h window per interval (futures ~23h, indices ~6.5h)
_BARS_PER_DAY = {"1m": 1440, "5m": 288, "15m": 96, "30m": 48,
                 "1h": 24, "4h": 6, "1d": 1}


def resolve(symbol: str):
    """Return (provider, ticker, kind); unknown symbols default to Binance."""
    return UNIVERSE.get(symbol, ("binance", symbol, "crypto"))


def _range_for(interval: str, limit: int) -> str:
    """Pick a Yahoo 'range' token that yields at least 'limit' bars."""
    bpd = _BARS_PER_DAY.get(interval, 24)
    days_needed = max(1.0, limit / bpd)
    if days_needed <= 5:
        return "5d"
    if days_needed <= 30:
        return "1mo"
    if days_needed <= 90:
        return "3mo"
    if days_needed <= 180:
        return "6mo"
    if days_needed <= 365:
        return "1y"
    if days_needed <= 730:
        return "2y"
    if days_needed <= 1825:
        return "5y"
    return "max"


def normalize_chart(timestamps, quote, limit=None):
    """Pure normaliser: Yahoo chart arrays -> Binance kline rows.

    Drops bars with a None close (Yahoo marks the in-progress bar this way) and
    coerces missing open/high/low to the close. Returns [] on empty/invalid.
    """
    ts = timestamps or []
    o = quote.get("open") or []
    h = quote.get("high") or []
    lo = quote.get("low") or []
    c = quote.get("close") or []
    v = quote.get("volume") or []
    n = min(len(ts), len(c))
    out = []
    for i in range(n):
        if c[i] is None:
            continue
        close = float(c[i])
        out.append([
            int(ts[i]) * 1000,
            float(o[i]) if o[i] is not None else close,
            float(h[i]) if h[i] is not None else close,
            float(lo[i]) if lo[i] is not None else close,
            close,
            float(v[i]) if v[i] is not None else 0.0,
        ])
    if limit:
        out = out[-limit:]
    return out


def _chart(ticker: str, interval: str, range_: str) -> dict:
    url = f"{YAHOO_CHART.format(ticker=ticker)}?interval={interval}&range={range_}"
    return get_json(url, timeout=15)


def yahoo_klines(ticker: str, interval: str = "4h", limit: int = 200):
    """Fetch Yahoo OHLCV normalised to Binance kline rows."""
    rng = _range_for(interval, limit)
    d = _chart(ticker, interval, rng)
    res = (d.get("chart") or {}).get("result") or []
    if not res:
        return []
    res = res[0]
    quote = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    return normalize_chart(res.get("timestamp"), quote, limit=limit)


def yahoo_ticker(ticker: str) -> dict:
    """24h-ish summary derived from chart meta (Yahoo quote API returns 401)."""
    d = _chart(ticker, "1d", "5d")
    res = (d.get("chart") or {}).get("result") or []
    if not res:
        return {}
    meta = res[0].get("meta") or {}
    price = meta.get("regularMarketPrice")
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    if price is None:
        rows = normalize_chart(
            res[0].get("timestamp"),
            ((res[0].get("indicators") or {}).get("quote") or [{}])[0])
        if rows:
            price = rows[-1][4]
    chg = None
    if price and prev:
        chg = (price - prev) / prev * 100.0
    return {
        "symbol": meta.get("symbol") or ticker,
        "lastPrice": str(price if price is not None else 0),
        "priceChangePercent": str(chg) if chg is not None else "0",
        "highPrice": str(meta.get("regularMarketDayHigh") or price or 0),
        "lowPrice": str(meta.get("regularMarketDayLow") or price or 0),
        "volume": str(meta.get("regularMarketVolume") or 0),
        "quoteVolume": "0",
    }
