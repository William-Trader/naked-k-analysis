"""Order-flow proxies from OHLCV: taker delta, cumulative delta, sweeps."""
from __future__ import annotations


def delta_series(ks) -> list:
    """Per-bar (buy - sell) / volume using Binance taker-buy field."""
    out = []
    for k in ks:
        v = float(k[5])
        b = float(k[9]) if len(k) > 9 else v / 2.0
        out.append((2.0 * b - v) / v if v else 0.0)
    return out


def analyse(ks, lookback: int = 20) -> dict:
    if len(ks) < 5:
        return {}
    d = delta_series(ks)
    n = min(lookback, len(ks))
    vols = [float(k[5]) for k in ks[-n:]]
    buys = [float(k[9]) if len(k) > 9 else float(k[5]) / 2.0 for k in ks[-n:]]
    total = sum(vols) or 1.0
    cum = sum(2.0 * b - v for b, v in zip(buys, vols)) / total
    price_chg = (float(ks[-1][4]) / float(ks[-n][4]) - 1.0) * 100.0
    divergence = "none"
    if price_chg > 0.5 and cum < 0:
        divergence = "bearish"
    elif price_chg < -0.5 and cum > 0:
        divergence = "bullish"
    return {
        "delta": round(d[-1], 3),
        "cum_delta": round(cum, 3),
        "price_chg": round(price_chg, 2),
        "divergence": divergence,
    }


def classify(bar: dict, delta: float) -> str:
    """Absorption vs sweep from bar shape plus delta."""
    if not bar:
        return "none"
    vz = bar.get("vol_z") or 0.0
    br = bar.get("body_ratio") or 0.0
    ra = bar.get("range_atr") or 0.0
    if vz >= 1.5 and br <= 0.35 and abs(delta) >= 0.15:
        return "absorption_buy" if delta > 0 else "absorption_sell"
    if abs(delta) >= 0.35 and ra >= 1.2:
        return "sweep_buy" if delta > 0 else "sweep_sell"
    return "none"

