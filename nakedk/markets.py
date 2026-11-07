# -----------------------------------------------------------------
# nakedk/markets.py - naked-k-analysis multi-market source base
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-2D9520FF
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
# -*- coding: utf-8 -*-
"""Multi-market source base.

Providers
--------
binance  crypto spot / USDT pairs          (public data-api.binance.vision)
yahoo    metals, energy, US indices, CBOT  (public chart API, 4h aggregated)
sina     Chinese domestic futures           (public Sina futures JSONP API)

Every provider normalises to the Binance kline shape

    [openTime_ms, open, high, low, close, volume, ...]

so features / structure / patterns / plans run unchanged across markets.
Nothing here is a hard dependency: an unreachable source raises and the
caller degrades to "data unavailable" instead of inventing prices.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone

from .http import get_json, get_text

YAHOO_CHARTS = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
    "https://query2.finance.yahoo.com/v8/finance/chart/{ticker}",
)
SINA_FEWMIN = ("https://stock2.finance.sina.com.cn/futures/api/jsonp.php/"
               "var%20_{code}_{tf}=/InnerFuturesNewService.getFewMinLine"
               "?symbol={code}&type={tf}")
SINA_DAILY = ("https://stock2.finance.sina.com.cn/futures/api/jsonp.php/"
              "var%20_{code}=/InnerFuturesNewService.getDailyKLine?symbol={code}")
SINA_QUOTE = "https://hq.sinajs.cn/list=nf_{code}"
CST = timezone(timedelta(hours=8))

# friendly symbol -> (provider, provider ticker, market kind)
UNIVERSE = {
    # ---------------- crypto (realtime universe, Binance) ----------------
    "BTCUSDT": ("binance", "BTCUSDT", "crypto"),
    "ETHUSDT": ("binance", "ETHUSDT", "crypto"),
    "SOLUSDT": ("binance", "SOLUSDT", "crypto"),
    "BNBUSDT": ("binance", "BNBUSDT", "crypto"),
    "XRPUSDT": ("binance", "XRPUSDT", "crypto"),
    "DOGEUSDT": ("binance", "DOGEUSDT", "crypto"),
    "ADAUSDT": ("binance", "ADAUSDT", "crypto"),
    "AVAXUSDT": ("binance", "AVAXUSDT", "crypto"),
    "LINKUSDT": ("binance", "LINKUSDT", "crypto"),
    # ---------------- commodities (Yahoo global futures) ----------------
    "XAU": ("yahoo", "GC=F", "metal"),        # backward-compatible alias
    "XAG": ("yahoo", "SI=F", "metal"),        # backward-compatible alias
    "PLAT": ("yahoo", "PL=F", "metal"),       # backward-compatible alias
    "GC": ("yahoo", "GC=F", "commodity"),     # COMEX gold
    "SI": ("yahoo", "SI=F", "commodity"),     # COMEX silver
    "HG": ("yahoo", "HG=F", "commodity"),     # COMEX copper
    "PL": ("yahoo", "PL=F", "commodity"),     # platinum
    "CL": ("yahoo", "CL=F", "future"),      # WTI crude
    "BZ": ("yahoo", "BZ=F", "commodity"),     # Brent crude
    "NG": ("yahoo", "NG=F", "commodity"),     # natural gas
    "ZC": ("yahoo", "ZC=F", "commodity"),     # corn
    "ZS": ("yahoo", "ZS=F", "commodity"),     # soybeans
    "ZM": ("yahoo", "ZM=F", "commodity"),     # soybean meal
    "ZL": ("yahoo", "ZL=F", "commodity"),     # soybean oil
    "KC": ("yahoo", "KC=F", "commodity"),     # coffee
    "SB": ("yahoo", "SB=F", "commodity"),     # sugar
    "CT": ("yahoo", "CT=F", "commodity"),     # cotton
    # ---------------- US indices / futures ----------------
    "SPX": ("yahoo", "^GSPC", "index"),
    "NDX": ("yahoo", "^IXIC", "index"),
    "DJI": ("yahoo", "^DJI", "index"),
    "RUT": ("yahoo", "^RUT", "index"),
    "ES": ("yahoo", "ES=F", "future"),
    "NQ": ("yahoo", "NQ=F", "future"),
    "YM": ("yahoo", "YM=F", "future"),
    # ---------------- Chinese domestic futures (Sina) ----------------
    "RB0": ("sina", "RB0", "cn_future"),   # 螺纹钢主连
    "HC0": ("sina", "HC0", "cn_future"),   # 热卷主连
    "I0": ("sina", "I0", "cn_future"),     # 铁矿石主连
    "J0": ("sina", "J0", "cn_future"),     # 焦炭主连
    "JM0": ("sina", "JM0", "cn_future"),   # 焦煤主连
    "CU0": ("sina", "CU0", "cn_future"),   # 沪铜主连
    "AL0": ("sina", "AL0", "cn_future"),   # 沪铝主连
    "AU0": ("sina", "AU0", "cn_future"),   # 沪金主连
    "AG0": ("sina", "AG0", "cn_future"),   # 沪银主连
    "SC0": ("sina", "SC0", "cn_future"),   # 原油主连
    "MA0": ("sina", "MA0", "cn_future"),   # 甲醇主连
    "TA0": ("sina", "TA0", "cn_future"),   # PTA 主连
    "M0": ("sina", "M0", "cn_future"),     # 豆粕主连
    "Y0": ("sina", "Y0", "cn_future"),     # 豆油主连
    "P0": ("sina", "P0", "cn_future"),     # 棕榈油主连
    "CF0": ("sina", "CF0", "cn_future"),   # 棉花主连
    "SR0": ("sina", "SR0", "cn_future"),   # 白糖主连
    "FG0": ("sina", "FG0", "cn_future"),   # 玻璃主连
    "SA0": ("sina", "SA0", "cn_future"),   # 纯碱主连
    "RU0": ("sina", "RU0", "cn_future"),   # 橡胶主连
    "BU0": ("sina", "BU0", "cn_future"),   # 沥青主连
}

# display / routing metadata
META = {
    "BTCUSDT": {"name": "BTC/USDT", "market": "crypto", "default": True},
    "ETHUSDT": {"name": "ETH/USDT", "market": "crypto", "default": True},
    "SOLUSDT": {"name": "SOL/USDT", "market": "crypto"},
    "BNBUSDT": {"name": "BNB/USDT", "market": "crypto"},
    "XRPUSDT": {"name": "XRP/USDT", "market": "crypto"},
    "DOGEUSDT": {"name": "DOGE/USDT", "market": "crypto"},
    "ADAUSDT": {"name": "ADA/USDT", "market": "crypto"},
    "AVAXUSDT": {"name": "AVAX/USDT", "market": "crypto"},
    "LINKUSDT": {"name": "LINK/USDT", "market": "crypto"},
    "XAU": {"name": "黄金", "market": "commodity"},
    "XAG": {"name": "白银", "market": "commodity"},
    "PLAT": {"name": "铂金", "market": "commodity"},
    "GC": {"name": "COMEX 黄金", "market": "commodity"},
    "SI": {"name": "COMEX 白银", "market": "commodity"},
    "HG": {"name": "COMEX 铜", "market": "commodity"},
    "PL": {"name": "铂金", "market": "commodity"},
    "CL": {"name": "WTI 原油", "market": "commodity"},
    "BZ": {"name": "布伦特原油", "market": "commodity"},
    "NG": {"name": "天然气", "market": "commodity"},
    "ZC": {"name": "玉米", "market": "commodity"},
    "ZS": {"name": "大豆", "market": "commodity"},
    "ZM": {"name": "豆粕(美)", "market": "commodity"},
    "ZL": {"name": "豆油(美)", "market": "commodity"},
    "KC": {"name": "咖啡", "market": "commodity"},
    "SB": {"name": "原糖", "market": "commodity"},
    "CT": {"name": "棉花(美)", "market": "commodity"},
    "SPX": {"name": "标普 500", "market": "index"},
    "NDX": {"name": "纳斯达克", "market": "index"},
    "DJI": {"name": "道琼斯", "market": "index"},
    "RUT": {"name": "罗素 2000", "market": "index"},
    "ES": {"name": "标普 E-mini", "market": "future"},
    "NQ": {"name": "纳指 E-mini", "market": "future"},
    "YM": {"name": "道指 E-mini", "market": "future"},
    "RB0": {"name": "螺纹钢主连", "market": "cn_future"},
    "HC0": {"name": "热卷主连", "market": "cn_future"},
    "I0": {"name": "铁矿石主连", "market": "cn_future"},
    "J0": {"name": "焦炭主连", "market": "cn_future"},
    "JM0": {"name": "焦煤主连", "market": "cn_future"},
    "CU0": {"name": "沪铜主连", "market": "cn_future"},
    "AL0": {"name": "沪铝主连", "market": "cn_future"},
    "AU0": {"name": "沪金主连", "market": "cn_future"},
    "AG0": {"name": "沪银主连", "market": "cn_future"},
    "SC0": {"name": "原油主连", "market": "cn_future"},
    "MA0": {"name": "甲醇主连", "market": "cn_future"},
    "TA0": {"name": "PTA 主连", "market": "cn_future"},
    "M0": {"name": "豆粕主连", "market": "cn_future"},
    "Y0": {"name": "豆油主连", "market": "cn_future"},
    "P0": {"name": "棕榈油主连", "market": "cn_future"},
    "CF0": {"name": "棉花主连", "market": "cn_future"},
    "SR0": {"name": "白糖主连", "market": "cn_future"},
    "FG0": {"name": "玻璃主连", "market": "cn_future"},
    "SA0": {"name": "纯碱主连", "market": "cn_future"},
    "RU0": {"name": "橡胶主连", "market": "cn_future"},
    "BU0": {"name": "沥青主连", "market": "cn_future"},
}

MARKET_LABELS = {
    "crypto": "加密货币",
    "commodity": "大宗商品",
    "index": "全球指数",
    "future": "海外期货",
    "cn_future": "国内期货",
}

# approximate bars per 24h window per interval
_BARS_PER_DAY = {"1m": 1440, "5m": 288, "15m": 96, "30m": 48,
                 "1h": 24, "4h": 6, "1d": 1}

_SUPPORTED = {"binance": {"1m", "5m", "15m", "30m", "1h", "4h", "1d"},
              "yahoo": {"15m", "30m", "1h", "4h", "1d"},
              "sina": {"15m", "30m", "1h", "4h", "1d"}}


def resolve(symbol: str):
    """Return (provider, ticker, kind); unknown symbols default to Binance."""
    return UNIVERSE.get(symbol, ("binance", symbol, "crypto"))


def meta(symbol: str) -> dict:
    m = dict(META.get(symbol) or {"name": symbol, "market": "crypto"})
    m.setdefault("market", "crypto")
    return m


def universe() -> list:
    """Serialisable instrument catalogue for the settings panel."""
    out = []
    for sym, (provider, _tkr, kind) in UNIVERSE.items():
        m = meta(sym)
        out.append({
            "symbol": sym,
            "name": m["name"],
            "market": m["market"],
            "market_label": MARKET_LABELS.get(m["market"], m["market"]),
            "kind": kind,
            "provider": provider,
            "default": bool(m.get("default")),
            "intervals": sorted(_SUPPORTED.get(provider, {"4h", "15m"})),
        })
    return out


def supports(symbol: str, interval: str) -> bool:
    provider, _tkr, _kind = resolve(symbol)
    return interval in _SUPPORTED.get(provider, {"4h", "15m"})


def _range_for(interval: str, limit: int) -> str:
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


# ---------------------------------------------------------------------------
# pure helpers (tested without network)
# ---------------------------------------------------------------------------

def normalize_chart(timestamps, quote, limit=None):
    """Yahoo chart arrays -> Binance kline rows (drops unformed bars)."""
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
            float(o[i]) if i < len(o) and o[i] is not None else close,
            float(h[i]) if i < len(h) and h[i] is not None else close,
            float(lo[i]) if i < len(lo) and lo[i] is not None else close,
            close,
            float(v[i]) if i < len(v) and v[i] is not None else 0.0,
        ])
    if limit:
        out = out[-limit:]
    return out


def aggregate(rows, factor: int):
    """Aggregate closed rows by a fixed factor, breaking groups on session gaps.

    Used to turn 1h into 4h without a provider 4h endpoint. A gap larger than
    2x the nominal step starts a new bucket, so overnight / weekend breaks are
    never merged into one candle.
    """
    if not rows or factor <= 1:
        return list(rows or [])
    out = []
    bucket = []
    step = int(rows[1][0]) - int(rows[0][0]) if len(rows) > 1 else 0

    def flush():
        if not bucket:
            return
        out.append([
            int(bucket[0][0]),
            float(bucket[0][1]),
            max(float(x[2]) for x in bucket),
            min(float(x[3]) for x in bucket),
            float(bucket[-1][4]),
            sum(float(x[5]) for x in bucket),
        ])

    for r in rows:
        if bucket and step and int(r[0]) - int(bucket[-1][0]) > step * 1.6:
            flush()
            bucket = []
        bucket.append(r)
        if len(bucket) >= factor:
            flush()
            bucket = []
    flush()
    return out


def _jsonp_array(text: str):
    """Extract the first JSON array/object from a Sina JSONP payload."""
    if not text:
        return None
    m = re.search(r"=\s*\((\[.*\])\)\s*;?\s*$", text.strip(), re.S)
    if not m:
        m = re.search(r"\((\[.*\])\)", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def _cn_ts(s: str, daily: bool = False) -> int:
    s = (s or "").strip()
    for fmt, date_only in (("%Y-%m-%d %H:%M:%S", False),
                           ("%Y-%m-%d %H:%M", False),
                           ("%Y-%m-%d", True)):
        try:
            dt = datetime.strptime(s, fmt).replace(tzinfo=CST)
            if date_only:
                dt = dt.replace(hour=15, minute=0)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue
    return 0


def normalize_sina(items, daily: bool = False, limit=None):
    """Sina futures rows -> Binance kline rows."""
    out = []
    for it in items or []:
        try:
            ts = _cn_ts(it.get("d") or it.get("date"), daily)
            if not ts:
                continue
            o = float(it.get("o"))
            h = float(it.get("h"))
            l = float(it.get("l"))
            c = float(it.get("c") or it.get("p"))
            v = float(it.get("v") or 0)
            out.append([ts, o, h, l, c, v])
        except (TypeError, ValueError):
            continue
    out.sort(key=lambda r: r[0])
    if limit:
        out = out[-limit:]
    return out


# ---------------------------------------------------------------------------
# providers
# ---------------------------------------------------------------------------

def _chart(ticker: str, interval: str, range_: str) -> dict:
    last = None
    for host in YAHOO_CHARTS:
        url = f"{host.format(ticker=ticker)}?interval={interval}&range={range_}"
        try:
            return get_json(url, timeout=15)
        except Exception as e:  # 429 on query1 is common; try query2
            last = e
    raise last


def yahoo_klines(ticker: str, interval: str = "4h", limit: int = 200):
    """Yahoo OHLCV normalised to Binance kline rows. 4h is 1h aggregated."""
    if interval == "4h":
        need = max(120, limit * 4 + 8)
        d = _chart(ticker, "1h", _range_for("1h", need))
        res = (d.get("chart") or {}).get("result") or []
        if not res:
            return []
        res = res[0]
        quote = ((res.get("indicators") or {}).get("quote") or [{}])[0]
        rows = normalize_chart(res.get("timestamp"), quote, limit=need)
        return aggregate(rows, 4)[-limit:]
    d = _chart(ticker, interval, _range_for(interval, limit))
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
    meta_ = res[0].get("meta") or {}
    price = meta_.get("regularMarketPrice")
    prev = meta_.get("chartPreviousClose") or meta_.get("previousClose")
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
        "symbol": meta_.get("symbol") or ticker,
        "lastPrice": str(price if price is not None else 0),
        "priceChangePercent": str(chg) if chg is not None else "0",
        "highPrice": str(meta_.get("regularMarketDayHigh") or price or 0),
        "lowPrice": str(meta_.get("regularMarketDayLow") or price or 0),
        "volume": str(meta_.get("regularMarketVolume") or 0),
        "quoteVolume": "0",
    }


def sina_klines(ticker: str, interval: str = "15m", limit: int = 300):
    """Chinese domestic futures via Sina public JSONP endpoints.

    Supported natively: 15m / 30m / 1h / 1d. 4h = 1h aggregated 4x.
    """
    code = ticker.upper()
    if interval == "1d":
        text = get_text(SINA_DAILY.format(code=code), timeout=15,
                        encoding="gbk", referer="https://finance.sina.com.cn")
        items = _jsonp_array(text) or []
        return normalize_sina(items, daily=True, limit=limit)
    tf = {"15m": 15, "30m": 30, "1h": 60}.get(interval, 15)
    if interval == "4h":
        text = get_text(SINA_FEWMIN.format(code=code, tf=60), timeout=15,
                        encoding="gbk", referer="https://finance.sina.com.cn")
        items = _jsonp_array(text) or []
        rows = normalize_sina(items, limit=max(limit * 4 + 8, 200))
        return aggregate(rows, 4)[-limit:]
    text = get_text(SINA_FEWMIN.format(code=code, tf=tf), timeout=15,
                    encoding="gbk", referer="https://finance.sina.com.cn")
    items = _jsonp_array(text) or []
    return normalize_sina(items, limit=limit)


def sina_ticker(ticker: str) -> dict:
    """Derive a 24h summary from 15m bars (no fragile quote-string parsing)."""
    rows = sina_klines(ticker, "15m", limit=120)
    if not rows:
        return {}
    price = rows[-1][4]
    cutoff = int(time.time() * 1000) - 86_400_000
    day = [r for r in rows if int(r[0]) >= cutoff] or rows[-96:]
    prev = rows[0][1]
    hi = max(r[2] for r in day)
    lo = min(r[3] for r in day)
    vol = sum(r[5] for r in day)
    chg = (price - prev) / prev * 100 if prev else 0.0
    return {
        "symbol": ticker.upper(),
        "lastPrice": str(price),
        "priceChangePercent": str(round(chg, 4)),
        "highPrice": str(hi),
        "lowPrice": str(lo),
        "volume": str(vol),
        "quoteVolume": "0",
    }
