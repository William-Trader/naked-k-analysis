"""Funding rate / open-interest context (Binance USD-M futures, public).

Every call degrades to None on failure: derivatives context is a bonus,
never a hard dependency for the 4h briefing.
"""
from __future__ import annotations

import json
from urllib.request import Request, urlopen

FAPI = "https://fapi.binance.com"


def _get(path: str, timeout: int = 10):
    req = Request(FAPI + path, headers={"User-Agent": "naked-k-analysis/2.0"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def funding_rate(symbol: str):
    try:
        return float(_get(f"/fapi/v1/premiumIndex?symbol={symbol}")["lastFundingRate"])
    except Exception:
        return None


def open_interest(symbol: str):
    try:
        return float(_get(f"/fapi/v1/openInterest?symbol={symbol}")["openInterest"])
    except Exception:
        return None


def oi_change(symbol: str, hours: int = 24):
    """Percent change in open interest over the window (1h buckets)."""
    try:
        rows = _get(f"/futures/data/openInterestHist?symbol={symbol}&period=1h&limit={hours + 1}")
        if len(rows) < 2:
            return None
        first = float(rows[0]["sumOpenInterest"])
        last = float(rows[-1]["sumOpenInterest"])
        return None if first == 0 else (last / first - 1.0) * 100.0
    except Exception:
        return None


def derivatives(symbol: str) -> dict:
    return {
        "funding_rate": funding_rate(symbol),
        "open_interest": open_interest(symbol),
        "oi_change_24h": oi_change(symbol),
    }

