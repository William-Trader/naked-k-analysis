"""Funding rate / open-interest context.

Binance USD-M futures (fapi) is blocked from the production host, so
Gate.io is the primary source and Binance is only a fallback. Every
call degrades to None: derivatives context is a bonus, never a hard
dependency for the 4h briefing.
"""
from __future__ import annotations

import json
from urllib.request import Request, urlopen

FAPI = "https://fapi.binance.com"
GATE = "https://api.gateio.ws/api/v4"


def _get(base: str, path: str, timeout: int = 6):
    req = Request(base + path, headers={"User-Agent": "naked-k-analysis/2.0"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def gate_contract(symbol: str) -> str:
    base = symbol[:-4] if symbol.endswith("USDT") else symbol
    return base + "_USDT"


def _from_gate(symbol: str) -> dict:
    contract = gate_contract(symbol)
    d = _get(GATE, f"/futures/usdt/contracts/{contract}")
    funding = float(d.get("funding_rate")) if d.get("funding_rate") not in (None, "") else None
    oi = float(d.get("open_interest")) if d.get("open_interest") not in (None, "") else None
    oi_chg = None
    try:
        rows = _get(GATE, f"/futures/usdt/contract_stats?contract={contract}&interval=1h&limit=25")
        if len(rows) >= 1:
            first = float(rows[0]["open_interest"])
            last = float(rows[-1]["open_interest"])
            if oi is None:
                oi = last
            if len(rows) >= 2 and first:
                oi_chg = (last / first - 1.0) * 100.0
    except Exception:
        pass
    return {"funding_rate": funding, "open_interest": oi,
            "oi_change_24h": oi_chg, "source": "gate"}


def _from_binance(symbol: str) -> dict:
    funding = float(_get(FAPI, f"/fapi/v1/premiumIndex?symbol={symbol}", 4)["lastFundingRate"])
    oi = None
    try:
        oi = float(_get(FAPI, f"/fapi/v1/openInterest?symbol={symbol}", 4)["openInterest"])
    except Exception:
        pass
    return {"funding_rate": funding, "open_interest": oi,
            "oi_change_24h": None, "source": "binance"}


def funding_rate(symbol: str):
    return derivatives(symbol).get("funding_rate")


def open_interest(symbol: str):
    return derivatives(symbol).get("open_interest")


def oi_change(symbol: str, hours: int = 24):
    return derivatives(symbol).get("oi_change_24h")


def derivatives(symbol: str) -> dict:
    """Try Gate first (reachable from production), then Binance."""
    for fn in (_from_gate, _from_binance):
        try:
            out = fn(symbol)
            if out.get("funding_rate") is not None or out.get("open_interest") is not None:
                return out
        except Exception:
            continue
    return {"funding_rate": None, "open_interest": None,
            "oi_change_24h": None, "source": "none"}
