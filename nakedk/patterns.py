"""Rule-based Al Brooks pattern candidates with quality scoring and arbitration.

Every detector returns:
{type, label, direction, index, price, quality, note, target?, stop?, neckline?}

detect() finds candidates; arbitrate() resolves contradictions using the
market context (bull/bear/range), position and quality. The primary and
secondary patterns are the only ones a trader should act on.
"""
from __future__ import annotations

BASE = {
    "DB": 60, "DT": 60, "HS": 65, "IHS": 65,
    "WEDGE_TOP": 60, "WEDGE_BOTTOM": 60,
    "H2": 58, "L2": 58, "H1": 52, "L1": 52,
    "TRI_ASC": 50, "TRI_DESC": 50, "TRI_SYM": 50,
    "FINAL_FLAG_BULL": 50, "FINAL_FLAG_BEAR": 50, "FLAG": 45,
    "BO_PB_BULL": 55, "BO_PB_BEAR": 55, "EMA20_PB": 50,
    "MTR": 55, "CUP": 50, "CLIMAX": 55, "TR": 45,
}
REVERSAL = {"DB", "DT", "HS", "IHS", "WEDGE_TOP", "WEDGE_BOTTOM", "CUP", "CLIMAX"}
TREND = {"H1", "H2", "L1", "L2", "BO_PB_BULL", "BO_PB_BEAR", "EMA20_PB"}


def _f(x):
    return float(x)


def swings(ks, w=2, keep=8):
    hs, ls = [], []
    for i in range(w, len(ks) - w):
        if _f(ks[i][2]) == max(_f(x[2]) for x in ks[i - w:i + w + 1]):
            hs.append((i, _f(ks[i][2])))
        if _f(ks[i][3]) == min(_f(x[3]) for x in ks[i - w:i + w + 1]):
            ls.append((i, _f(ks[i][3])))
    return hs[-keep:], ls[-keep:]


def _hi(ks, a, b):
    return max(_f(x[2]) for x in ks[a:b + 1]) if a <= b else None


def _lo(ks, a, b):
    return min(_f(x[3]) for x in ks[a:b + 1]) if a <= b else None


def _atr(ks, n=14):
    trs = []
    for i in range(1, len(ks)):
        trs.append(max(_f(ks[i][2]) - _f(ks[i][3]),
                       abs(_f(ks[i][2]) - _f(ks[i - 1][4])),
                       abs(_f(ks[i][3]) - _f(ks[i - 1][4]))))
    if not trs:
        return 0.0
    return sum(trs[-n:]) / min(len(trs), n)


def _context(f):
    if f["ema20"] > f["ema50"] and f["price"] > f["ema20"]:
        return "bull"
    if f["ema20"] < f["ema50"] and f["price"] < f["ema20"]:
        return "bear"
    return "range"


def _fit(p, ctx, f):
    d = p["direction"]
    pos = f.get("pos20", 0.5)
    if ctx == "bull":
        if d == "bullish":
            return 1.0
        if d == "bearish":
            return 0.3 if pos > 0.7 else 0.1
        return 0.5
    if ctx == "bear":
        if d == "bearish":
            return 1.0
        if d == "bullish":
            return 0.3 if pos < 0.3 else 0.1
        return 0.5
    if d == "neutral":
        return 1.0
    if d == "bullish":
        return 0.8 if pos < 0.35 else 0.3
    if d == "bearish":
        return 0.8 if pos > 0.65 else 0.3
    return 0.5


def _score(p, f, ks, atr):
    q = BASE.get(p["type"], 50)
    vz = f.get("vol_z") or 0.0
    if vz >= 1.5:
        q += 12
    elif vz >= 0.5:
        q += 8
    elif vz < 0:
        q -= 5
    pos = f.get("pos20", 0.5)
    if p["type"] in REVERSAL:
        q += 10 if (pos < 0.3 or pos > 0.7) else -5
    if p["type"] in TREND:
        q += 5 if 0.3 <= pos <= 0.7 else -10
    # signal bar quality (last 2 bars)
    last = ks[-1]
    rng = _f(last[2]) - _f(last[3])
    body = abs(_f(last[4]) - _f(last[1]))
    upper = _f(last[2]) - max(_f(last[1]), _f(last[4]))
    lower = min(_f(last[1]), _f(last[4])) - _f(last[3])
    sb = 0
    if rng > 0:
        if body / rng > 0.6:
            sb += 4
        if (_f(last[4]) - _f(last[1])) * (1 if p["direction"] == "bullish" else -1) > 0:
            sb += 3
        if upper < rng * 0.25 or lower < rng * 0.25:
            sb += 2
        if len(ks) >= 2:
            prev = ks[-2]
            if (_f(last[4]) - _f(last[1])) * (_f(prev[4]) - _f(prev[1])) > 0:
                sb += 1
    q += sb
    p["signal_bar"] = sb
    if p.get("target") and p.get("stop"):
        risk = abs(p["price"] - p["stop"])
        reward = abs(p["target"] - p["price"])
        if risk > 0:
            rr = reward / risk
            p["rr"] = round(rr, 2)
            if rr >= 2:
                q += 10
            elif rr >= 1.5:
                q += 6
            elif rr < 1:
                q -= 10
    p["quality"] = max(0, min(100, round(q)))
    return p


def detect(ks, f):
    p = _f(f["price"])
    atr = _atr(ks) or p * 0.01
    hs, ls = swings(ks)
    pats = []

    def add(t, label, d, idx, price, note="", **extra):
        pats.append({"type": t, "label": label, "direction": d,
                     "index": idx, "price": price, "note": note, **extra})

    if len(ls) >= 2:
        a, b = ls[-2], ls[-1]
        if abs(a[1] - b[1]) / p < 0.008 and p > max(a[1], b[1]):
            neck = _hi(ks, a[0], b[0])
            low = min(a[1], b[1])
            add("DB", "双底候选", "bullish", b[0], b[1],
                "两低点接近，颈线突破确认", neckline=neck,
                target=neck + (neck - low), stop=low - 0.2 * atr)
    if len(hs) >= 2:
        a, b = hs[-2], hs[-1]
        if abs(a[1] - b[1]) / p < 0.008 and p < min(a[1], b[1]):
            neck = _lo(ks, a[0], b[0])
            high = max(a[1], b[1])
            add("DT", "双顶候选", "bearish", b[0], b[1],
                "两高点接近，颈线跌破确认", neckline=neck,
                target=neck - (high - neck), stop=high + 0.2 * atr)
    if f["ema20"] > f["ema50"] and p > f["ema20"]:
        if len(ls) >= 2 and ls[-1][1] > ls[-2][1]:
            add("H2", "H2 回调", "bullish", ls[-1][0], ls[-1][1],
                "上升结构中的第二次更高低点")
        elif len(ls) >= 1:
            add("H1", "H1 回调", "bullish", ls[-1][0], ls[-1][1],
                "上升结构中的第一次回调")
    if f["ema20"] < f["ema50"] and p < f["ema20"]:
        if len(hs) >= 2 and hs[-1][1] < hs[-2][1]:
            add("L2", "L2 反弹", "bearish", hs[-1][0], hs[-1][1],
                "下降结构中的第二次更低高点")
        elif len(hs) >= 1:
            add("L1", "L1 反弹", "bearish", hs[-1][0], hs[-1][1],
                "下降结构中的第一次反弹")
    if len(hs) >= 3 and len(ls) >= 3:
        h3, l3 = hs[-3:], ls[-3:]
        if h3[-1][1] > h3[-2][1] > h3[-3][1] and l3[-1][1] > l3[-2][1] > l3[-3][1]:
            add("WEDGE_TOP", "上升楔形", "bearish", h3[-1][0], h3[-1][1],
                "三推上升，动能收敛")
        if h3[-1][1] < h3[-2][1] < h3[-3][1] and l3[-1][1] < l3[-2][1] < l3[-3][1]:
            add("WEDGE_BOTTOM", "下降楔形", "bullish", l3[-1][0], l3[-1][1],
                "三推下降，动能收敛")
    if len(hs) >= 3 and len(ls) >= 3:
        h3, l3 = hs[-3:], ls[-3:]
        hi_flat = max(x[1] for x in h3) - min(x[1] for x in h3) < atr * 0.8
        lo_flat = max(x[1] for x in l3) - min(x[1] for x in l3) < atr * 0.8
        hi_down = h3[-1][1] < h3[-3][1]
        lo_up = l3[-1][1] > l3[-3][1]
        if hi_flat and lo_up:
            add("TRI_ASC", "上升三角形", "bullish", len(ks) - 1, p, "高点走平、低点抬高")
        if hi_down and lo_flat:
            add("TRI_DESC", "下降三角形", "bearish", len(ks) - 1, p, "高点降低、低点走平")
        if hi_down and lo_up:
            add("TRI_SYM", "对称三角形", "neutral", len(ks) - 1, p, "高低点同时收敛")
    if len(hs) >= 3:
        a, b, c = hs[-3], hs[-2], hs[-1]
        if b[1] > a[1] and b[1] > c[1] and abs(a[1] - c[1]) / p < 0.02:
            neck = min(_lo(ks, a[0], b[0]), _lo(ks, b[0], c[0]))
            add("HS", "头肩顶候选", "bearish", c[0], c[1],
                "中间头高于两肩，颈线跌破确认", neckline=neck,
                target=neck - (b[1] - neck), stop=max(a[1], c[1]) + 0.2 * atr)
    if len(ls) >= 3:
        a, b, c = ls[-3], ls[-2], ls[-1]
        if b[1] < a[1] and b[1] < c[1] and abs(a[1] - c[1]) / p < 0.02:
            neck = max(_hi(ks, a[0], b[0]), _hi(ks, b[0], c[0]))
            add("IHS", "头肩底候选", "bullish", c[0], c[1],
                "中间底低于两肩，颈线突破确认", neckline=neck,
                target=neck + (neck - b[1]), stop=min(a[1], c[1]) - 0.2 * atr)
    if len(ks) >= 30:
        last = ks[-10:]
        rng = max(_f(x[2]) for x in last) - min(_f(x[3]) for x in last)
        if rng < atr * 1.2:
            prior = _f(ks[-11][4]) - _f(ks[-30][4])
            if prior > atr * 2:
                add("FINAL_FLAG_BULL", "最终牛旗候选", "bearish", len(ks) - 1, p,
                    "上升后紧旗，突破失败易反转")
            elif prior < -atr * 2:
                add("FINAL_FLAG_BEAR", "最终熊旗候选", "bullish", len(ks) - 1, p,
                    "下跌后紧旗，突破失败易反转")
            else:
                add("FLAG", "旗形整理", "neutral", len(ks) - 1, p, "窄幅整理，等突破")
    if len(ks) >= 25:
        hi20 = max(_f(x[2]) for x in ks[-25:-5])
        if _f(ks[-5][4]) > hi20 and p <= hi20 * 1.005:
            add("BO_PB_BULL", "突破回踩", "bullish", len(ks) - 1, p, "突破20根高点后回踩")
        lo20 = min(_f(x[3]) for x in ks[-25:-5])
        if _f(ks[-5][4]) < lo20 and p >= lo20 * 0.995:
            add("BO_PB_BEAR", "突破回踩", "bearish", len(ks) - 1, p, "跌破20根低点后反抽")
    if len(ks) >= 3:
        e = f["ema20"]
        lo3 = min(_f(x[3]) for x in ks[-3:])
        hi3 = max(_f(x[2]) for x in ks[-3:])
        if f["ema20"] > f["ema50"] and lo3 <= e <= hi3 and p > e:
            add("EMA20_PB", "EMA20 回踩", "bullish", len(ks) - 1, p, "强趋势回踩EMA20后收回")
        if f["ema20"] < f["ema50"] and lo3 <= e <= hi3 and p < e:
            add("EMA20_PB", "EMA20 反抽", "bearish", len(ks) - 1, p, "弱趋势反抽EMA20后回落")
    if f["ema20"] > f["ema50"] and len(hs) >= 2 and hs[-1][1] < hs[-2][1] and p < f["ema20"]:
        add("MTR", "MTR 空头候选", "bearish", hs[-1][0], hs[-1][1],
            "上升趋势出现更低高点并跌破EMA20")
    if f["ema20"] < f["ema50"] and len(ls) >= 2 and ls[-1][1] > ls[-2][1] and p > f["ema20"]:
        add("MTR", "MTR 多头候选", "bullish", ls[-1][0], ls[-1][1],
            "下降趋势出现更高低点并站上EMA20")
    if len(ls) >= 3 and len(hs) >= 2:
        a, b, c = ls[-3:]
        if b[1] < a[1] and b[1] < c[1] and abs(a[1] - c[1]) / p < 0.03 and p > c[1]:
            add("CUP", "杯柄候选", "bullish", c[0], c[1], "U形底 + 右侧小回调，突破杯口确认")
    if len(ks) >= 15:
        last = ks[-1]
        rng = _f(last[2]) - _f(last[3])
        avg = sum(float(x[5]) for x in ks[-15:-1]) / 14
        if rng > atr * 2 and avg and float(last[5]) / avg > 2.5:
            d = "bearish" if _f(last[4]) >= _f(last[1]) else "bullish"
            add("CLIMAX", "高潮K", d, len(ks) - 1, _f(last[4]), "超大实体 + 放量，趋势末端")
    if len(ks) >= 20:
        last20 = ks[-20:]
        rng = max(_f(x[2]) for x in last20) - min(_f(x[3]) for x in last20)
        if rng < atr * 2.5 and (f.get("adx14") or 0) < 25:
            add("TR", "交易区间", "neutral", len(ks) - 1, p, "20根重叠，等突破确认")

    pats = [_score(x, f, ks, atr) for x in pats]
    return pats


def arbitrate(pats, f):
    ctx = _context(f)
    for x in pats:
        x["context"] = ctx
        x["fit"] = round(_fit(x, ctx, f), 2)
        x["score"] = x["quality"] * (0.5 + 0.5 * x["fit"])
        mtf = f.get("mtf_alignment")
        if mtf is not None and x.get("direction") in ("bullish", "bearish"):
            conflict = ((mtf >= 2 and x["direction"] == "bearish")
                        or (mtf <= -2 and x["direction"] == "bullish"))
            aligned = ((mtf >= 2 and x["direction"] == "bullish")
                       or (mtf <= -2 and x["direction"] == "bearish"))
            if conflict:
                x["score"] *= 0.55
                x["mtf"] = "conflict"
            elif aligned:
                x["score"] *= 1.15
                x["mtf"] = "aligned"
            else:
                x["mtf"] = "neutral"
        mults = f.get("adapt_mult")
        if isinstance(mults, dict):
            am = float(mults.get(x.get("type"), 1.0))
            if am != 1.0:
                x["score"] *= am
                x["adapt"] = am
        x["score"] = round(x["score"], 1)
    pats.sort(key=lambda x: x["score"], reverse=True)
    primary = pats[0] if pats else None
    secondary = None
    if primary:
        for x in pats[1:]:
            if x["direction"] != primary["direction"] or x["type"] != primary["type"]:
                secondary = x
                break
    for x in pats:
        x["role"] = "primary" if x is primary else ("secondary" if x is secondary else "suppressed")
    return {"context": ctx, "primary": primary, "secondary": secondary, "patterns": pats}
