"""Cross-asset context: BTC/ETH correlation and relative strength."""
from __future__ import annotations

from .features import ema


def _returns(closes):
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))
            if closes[i - 1]]


def correlation(a, b) -> float | None:
    n = min(len(a), len(b))
    if n < 10:
        return None
    a, b = a[-n:], b[-n:]
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if not va or not vb:
        return None
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    return round(cov / (va ** 0.5 * vb ** 0.5), 3)


def analyse(btc_daily, eth_daily, ethbtc_daily=None) -> dict:
    def closes(ks):
        return [float(k[4]) for k in ks]
    cb, ce = closes(btc_daily), closes(eth_daily)
    n = min(len(cb), len(ce), 31)
    if n < 11:
        return {}
    corr = correlation(_returns(cb[-n:]), _returns(ce[-n:]))
    btc_ret = (cb[-1] / cb[-n] - 1.0) * 100.0
    eth_ret = (ce[-1] / ce[-n] - 1.0) * 100.0
    out = {"corr_30d": corr, "btc_30d": round(btc_ret, 2),
           "eth_30d": round(eth_ret, 2),
           "relative_strength": round(eth_ret - btc_ret, 2)}
    if ethbtc_daily and len(ethbtc_daily) >= 60:
        c = closes(ethbtc_daily)
        e20, e50 = ema(c[-120:], 20), ema(c, 50)
        if e20 and e50:
            out["ethbtc_trend"] = ("up" if c[-1] > e20 > e50
                                   else "down" if c[-1] < e20 < e50 else "mixed")
    return out

