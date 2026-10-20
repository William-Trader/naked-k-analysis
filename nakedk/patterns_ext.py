"""Extended Brooks patterns: flags, micro doubles, iii, OBR, climax."""
from __future__ import annotations


def _f(x):
    return float(x)


def _atr(ks, n=14):
    trs = []
    for i in range(1, len(ks)):
        trs.append(max(_f(ks[i][2]) - _f(ks[i][3]),
                       abs(_f(ks[i][2]) - _f(ks[i - 1][4])),
                       abs(_f(ks[i][3]) - _f(ks[i - 1][4]))))
    if not trs:
        return 0.0
    return sum(trs[-n:]) / min(len(trs), n)


def _bar(ks, i):
    k = ks[i]
    return {"o": _f(k[1]), "h": _f(k[2]), "l": _f(k[3]), "c": _f(k[4]), "v": _f(k[5])}


def _rng(b):
    return b["h"] - b["l"]


def _close_pos(b):
    r = _rng(b)
    return 0.5 if r <= 0 else (b["c"] - b["l"]) / r


def _inside(a, b):
    return b["h"] < a["h"] and b["l"] > a["l"]


def _outside(a, b):
    return b["h"] > a["h"] and b["l"] < a["l"]


def extra_patterns(ks, f):
    if len(ks) < 30:
        return []
    atr = _atr(ks) or f.get("atr14") or 0.0
    if not atr:
        return []
    n = len(ks)
    price = f.get("price") or _bar(ks, n - 1)["c"]
    b1, b2, b3, b4 = (_bar(ks, n - 1), _bar(ks, n - 2),
                      _bar(ks, n - 3), _bar(ks, n - 4))
    out = []

    # Micro double bottom / top: two-bar reversal at an extreme.
    if abs(b1["l"] - b2["l"]) <= 0.25 * atr and _close_pos(b1) >= 0.6:
        low = min(b1["l"], b2["l"])
        out.append({"type": "MICRO_DB", "label": "微型双底", "direction": "bullish",
                    "index": n - 1, "price": low,
                    "note": "两根K线低点接近，收盘在区间上半部",
                    "stop": low - 0.3 * atr, "target": price + 2 * (price - low),
                    "height": price - low, "symmetry": 1.0})
    if abs(b1["h"] - b2["h"]) <= 0.25 * atr and _close_pos(b1) <= 0.4:
        high = max(b1["h"], b2["h"])
        out.append({"type": "MICRO_DT", "label": "微型双顶", "direction": "bearish",
                    "index": n - 1, "price": high,
                    "note": "两根K线高点接近，收盘在区间下半部",
                    "stop": high + 0.3 * atr, "target": price - 2 * (high - price),
                    "height": high - price, "symmetry": 1.0})

    # iii: three consecutive inside bars.
    if _inside(b4, b3) and _inside(b3, b2) and _inside(b2, b1):
        out.append({"type": "III", "label": "三内包（iii）", "direction": "neutral",
                    "index": n - 1, "price": price,
                    "note": "连续三根内包，突破方向待定",
                    "height": _rng(b4), "symmetry": 1.0})

    # Outside bar reversal: engulf then close beyond the prior bar.
    if _outside(b2, b1):
        if b1["c"] > b2["h"]:
            out.append({"type": "OBR_BULL", "label": "外包反转（多）",
                        "direction": "bullish", "index": n - 1, "price": b1["c"],
                        "note": "外包K线收在前高之上", "stop": b1["l"],
                        "target": b1["c"] + (b1["c"] - b1["l"]),
                        "height": b1["c"] - b1["l"], "symmetry": 1.0})
        elif b1["c"] < b2["l"]:
            out.append({"type": "OBR_BEAR", "label": "外包反转（空）",
                        "direction": "bearish", "index": n - 1, "price": b1["c"],
                        "note": "外包K线收在前低之下", "stop": b1["h"],
                        "target": b1["c"] - (b1["h"] - b1["c"]),
                        "height": b1["h"] - b1["c"], "symmetry": 1.0})

    # Climax reversal: 2x ATR range with volume, closing against the extreme.
    vz = f.get("vol_z") or 0.0
    if _rng(b1) >= 2 * atr and vz >= 2:
        cp = _close_pos(b1)
        if cp <= 0.3:
            out.append({"type": "CLIMAX_BULL", "label": "抛售高潮反转",
                        "direction": "bullish", "index": n - 1, "price": b1["l"],
                        "note": "放量长下影，收盘回到上半部", "stop": b1["l"] - 0.3 * atr,
                        "height": _rng(b1), "symmetry": 1.0})
        elif cp >= 0.7:
            out.append({"type": "CLIMAX_BEAR", "label": "买入高潮反转",
                        "direction": "bearish", "index": n - 1, "price": b1["h"],
                        "note": "放量长上影，收盘回到下半部", "stop": b1["h"] + 0.3 * atr,
                        "height": _rng(b1), "symmetry": 1.0})

    # Flag: impulse >= 2.5 ATR, then a tight, shallow pullback.
    window = [_bar(ks, i) for i in range(max(0, n - 12), n)]
    closes = [b["c"] for b in window]
    hi, lo = max(closes), min(closes)
    if hi - lo >= 2.5 * atr and len(window) >= 8:
        up = closes[-1] >= closes[0]
        pb = window[-4:]
        pb_range = max(b["h"] for b in pb) - min(b["l"] for b in pb)
        if pb_range <= 1.2 * atr:
            if up:
                retr = (hi - min(b["l"] for b in pb)) / max(hi - lo, 1e-9)
                if retr <= 0.5:
                    out.append({"type": "FLAG_BULL", "label": "牛旗",
                                "direction": "bullish", "index": n - 1, "price": price,
                                "note": "急涨后窄幅回调，未破一半",
                                "stop": min(b["l"] for b in pb),
                                "target": hi + (hi - lo),
                                "height": hi - lo, "symmetry": round(1 - retr, 2)})
            else:
                retr = (max(b["h"] for b in pb) - lo) / max(hi - lo, 1e-9)
                if retr <= 0.5:
                    out.append({"type": "FLAG_BEAR", "label": "熊旗",
                                "direction": "bearish", "index": n - 1, "price": price,
                                "note": "急跌后窄幅反弹，未收复一半",
                                "stop": max(b["h"] for b in pb),
                                "target": lo - (hi - lo),
                                "height": hi - lo, "symmetry": round(1 - retr, 2)})
    # Measured move: two equal legs in the same direction.
    try:
        from .structure import zigzag
        highs = [_f(k[2]) for k in ks]
        lows = [_f(k[3]) for k in ks]
        piv = zigzag(highs, lows, atr, 0.5)
        if len(piv) >= 4:
            a, b, c, d = piv[-4], piv[-3], piv[-2], piv[-1]
            if a["kind"] == "L" and b["kind"] == "H" and c["kind"] == "L" and d["kind"] == "H":
                leg1, leg2 = b["p"] - a["p"], d["p"] - c["p"]
                if leg1 > 0 and leg2 > 0 and abs(leg2 - leg1) / leg1 <= 0.25 and d["p"] > b["p"]:
                    out.append({"type": "MM_UP", "label": "测量移动（上）",
                                "direction": "bullish", "index": d["i"], "price": d["p"],
                                "note": "两段等长上涨，第二段完成",
                                "stop": c["p"] - 0.3 * atr, "target": d["p"] + leg2,
                                "height": leg2, "symmetry": round(1 - abs(leg2 - leg1) / leg1, 2)})
            elif a["kind"] == "H" and b["kind"] == "L" and c["kind"] == "H" and d["kind"] == "L":
                leg1, leg2 = a["p"] - b["p"], c["p"] - d["p"]
                if leg1 > 0 and leg2 > 0 and abs(leg2 - leg1) / leg1 <= 0.25 and d["p"] < b["p"]:
                    out.append({"type": "MM_DOWN", "label": "测量移动（下）",
                                "direction": "bearish", "index": d["i"], "price": d["p"],
                                "note": "两段等长下跌，第二段完成",
                                "stop": c["p"] + 0.3 * atr, "target": d["p"] - leg2,
                                "height": leg2, "symmetry": round(1 - abs(leg2 - leg1) / leg1, 2)})
    except Exception:
        pass

    # Final flag: a tight flag at the end of a mature trend.
    try:
        from .legs import decompose, maturity
        legs = decompose([_f(k[2]) for k in ks], [_f(k[3]) for k in ks], atr)
        if maturity(legs) >= 3:
            for p in list(out):
                if p["type"] == "FLAG_BULL":
                    out.append({**p, "type": "FINAL_FLAG_BULL", "label": "最终旗形（多）",
                                "direction": "neutral",
                                "note": "趋势末段旗形：突破后更容易失败"})
                elif p["type"] == "FLAG_BEAR":
                    out.append({**p, "type": "FINAL_FLAG_BEAR", "label": "最终旗形（空）",
                                "direction": "neutral",
                                "note": "趋势末段旗形：破位后更容易失败"})
    except Exception:
        pass

    return out
