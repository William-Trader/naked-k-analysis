# -----------------------------------------------------------------
# nakedk/annotations.py - naked-k-analysis chart annotation geometry
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-3DC589D6
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
# -*- coding: utf-8 -*-
"""Turn engine output into drawable geometry.

The frontend renders candles with Lightweight Charts and paints this payload
on a transparent canvas overlay (boxes, channels, polygons, labels). Keeping
the geometry server-side means the chart, the right-hand panel and the alert
text all describe the same structure.

Coordinate contract: every point is {"t": unix_seconds, "p": price}.
"""
from __future__ import annotations

from .structure import label as label_pivots, zigzag

MAX_PATTERNS = 5


def _f(x):
    return float(x)


def _t(ks, i):
    if i is None or i < 0 or i >= len(ks):
        return None
    return int(ks[i][0]) // 1000


def _pt(ks, i, p):
    t = _t(ks, i)
    if t is None or p is None:
        return None
    return {"t": t, "p": round(_f(p), 6)}


def _atr(ks, n=14):
    if len(ks) < 3:
        return 1.0
    highs = [_f(k[2]) for k in ks]
    lows = [_f(k[3]) for k in ks]
    closes = [_f(k[4]) for k in ks]
    trs = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]),
               abs(lows[i] - closes[i - 1])) for i in range(1, len(ks))]
    tail = trs[-n:]
    return (sum(tail) / len(tail)) if tail and sum(tail) else 1.0


def _cluster(points, atr, kind, price, keep=6):
    """Cluster pivots into horizontal levels (touches + recency = strength)."""
    if not points:
        return []
    pts = sorted(points, key=lambda x: x["p"])
    groups, cur = [], [pts[0]]
    for p in pts[1:]:
        if abs(p["p"] - cur[-1]["p"]) <= 0.35 * atr:
            cur.append(p)
        else:
            groups.append(cur)
            cur = [p]
    groups.append(cur)
    n = max(1, len(points))
    out = []
    for g in groups:
        avg = sum(x["p"] for x in g) / len(g)
        last = max(g, key=lambda x: x["i"])
        touches = len(g)
        recency = max(0.0, 1.0 - (n - last["i"]) / max(n, 1))
        strength = min(5, max(1, touches + (1 if recency > 0.75 else 0)))
        out.append({
            "kind": kind,
            "price": round(avg, 6),
            "touches": touches,
            "strength": strength,
            "last_t": None,  # filled by build() after pivots carry t
            "distance_pct": round((avg - price) / price * 100, 3) if price else None,
        })
    out.sort(key=lambda x: (x["strength"], x["touches"]), reverse=True)
    return out[:keep]


def _fit_line(points):
    """Least-squares y = a + b*x on pivot points (x = bar index)."""
    n = len(points)
    if n < 3:
        return None
    xs = [p["i"] for p in points]
    ys = [p["p"] for p in points]
    mx = sum(xs) / n
    my = sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den <= 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    a = my - b * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    return {"a": a, "b": b, "r2": r2}


def _channels(ks, pivots, atr, extend=18):
    highs = [p for p in pivots if p["kind"] == "H"][-4:]
    lows = [p for p in pivots if p["kind"] == "L"][-4:]
    out = []
    last_i = len(ks) - 1
    for group, kind, label in ((highs, "channel_upper", "通道上轨"),
                               (lows, "channel_lower", "通道下轨")):
        fit = _fit_line(group)
        if not fit or fit["r2"] < 0.45:
            continue
        i0, i1 = group[0]["i"], last_i + extend
        out.append({
            "kind": kind,
            "label": label,
            "r2": round(fit["r2"], 2),
            "points": [
                {"t": _t(ks, i0), "p": round(fit["a"] + fit["b"] * i0, 6)},
                {"t": _t(ks, last_i), "p": round(fit["a"] + fit["b"] * last_i, 6)},
            ],
            "extend_to": {"t": _t(ks, last_i), "p": round(fit["a"] + fit["b"] * i1, 6)},
            "slope_atr": round(fit["b"] / atr, 4) if atr else None,
        })
    return out


def _zones(ks, pivots, atr, struct):
    out = []
    if not pivots:
        return out
    n = len(ks)
    last_l = next((p for p in reversed(pivots) if p["kind"] == "L"), None)
    last_h = next((p for p in reversed(pivots) if p["kind"] == "H"), None)
    if last_l and n - last_l["i"] <= 80:
        out.append({
            "kind": "demand",
            "label": "需求区",
            "top": round(last_l["p"] + 0.55 * atr, 6),
            "bottom": round(last_l["p"] - 0.20 * atr, 6),
            "from_t": _t(ks, last_l["i"]),
            "strength": 3,
        })
    if last_h and n - last_h["i"] <= 80:
        out.append({
            "kind": "supply",
            "label": "供给区",
            "top": round(last_h["p"] + 0.20 * atr, 6),
            "bottom": round(last_h["p"] - 0.55 * atr, 6),
            "from_t": _t(ks, last_h["i"]),
            "strength": 3,
        })
    bos = (struct or {}).get("bos") or {}
    bi = bos.get("i")
    if isinstance(bi, int) and 2 <= bi < n:
        base = ks[max(0, bi - 3):bi]
        if base:
            out.append({
                "kind": "breakout_base",
                "label": "突破基座",
                "top": round(max(_f(k[2]) for k in base), 6),
                "bottom": round(min(_f(k[3]) for k in base), 6),
                "from_t": _t(ks, max(0, bi - 3)),
                "strength": 2 if bos.get("kind") == "bullish" else 2,
            })
    return out


def _pattern_geometry(ks, pat, pivots, atr):
    """Build polygon / neckline / target lines for one detected pattern."""
    typ = pat.get("type")
    i = pat.get("index")
    if i is None or i >= len(ks):
        return None
    highs = [p for p in pivots if p["kind"] == "H"]
    lows = [p for p in pivots if p["kind"] == "L"]
    geo = {"points": [], "lines": [], "box": None, "marker": None}
    last_t = _t(ks, len(ks) - 1)

    def add_line(kind, p, label, t0=None, dashed=True, strength=2):
        geo["lines"].append({
            "kind": kind, "label": label,
            "from_t": t0 or _t(ks, max(0, len(ks) - 40)),
            "to_t": last_t, "price": round(_f(p), 6),
            "dashed": dashed, "strength": strength,
        })

    if typ == "DB" and len(lows) >= 2:
        a, b = lows[-2], lows[-1]
        neck = pat.get("neckline")
        geo["points"] = [{"t": _t(ks, a["i"]), "p": a["p"]},
                         {"t": _t(ks, b["i"]), "p": b["p"]},
                         {"t": _t(ks, b["i"]), "p": neck or b["p"]},
                         {"t": _t(ks, a["i"]), "p": neck or b["p"]}]
        if neck:
            add_line("neckline", neck, "颈线")
        if pat.get("target"):
            add_line("target", pat["target"], "量度目标", dashed=False, strength=3)
    elif typ == "DT" and len(highs) >= 2:
        a, b = highs[-2], highs[-1]
        neck = pat.get("neckline")
        geo["points"] = [{"t": _t(ks, a["i"]), "p": a["p"]},
                         {"t": _t(ks, b["i"]), "p": b["p"]},
                         {"t": _t(ks, b["i"]), "p": neck or b["p"]},
                         {"t": _t(ks, a["i"]), "p": neck or b["p"]}]
        if neck:
            add_line("neckline", neck, "颈线")
        if pat.get("target"):
            add_line("target", pat["target"], "量度目标", dashed=False, strength=3)
    elif typ in ("HS", "IHS") and len(highs) >= 3 and len(lows) >= 3:
        if typ == "HS":
            a, b, c = highs[-3], highs[-2], highs[-1]
            mids = [p for p in lows if a["i"] < p["i"] < c["i"]]
        else:
            a, b, c = lows[-3], lows[-2], lows[-1]
            mids = [p for p in highs if a["i"] < p["i"] < c["i"]]
        neck = pat.get("neckline")
        left_neck = mids[0]["p"] if mids else neck
        right_neck = mids[-1]["p"] if mids else neck
        geo["points"] = [{"t": _t(ks, a["i"]), "p": a["p"]},
                         {"t": _t(ks, mids[0]["i"]) if mids else _t(ks, a["i"]),
                          "p": left_neck},
                         {"t": _t(ks, b["i"]), "p": b["p"]},
                         {"t": _t(ks, mids[-1]["i"]) if mids else _t(ks, c["i"]),
                          "p": right_neck},
                         {"t": _t(ks, c["i"]), "p": c["p"]}]
        if neck:
            add_line("neckline", neck, "颈线")
        if pat.get("target"):
            add_line("target", pat["target"], "量度目标", dashed=False, strength=3)
    elif typ in ("TRI_ASC", "TRI_DESC", "TRI_SYM", "WEDGE_TOP", "WEDGE_BOTTOM"):
        h3, l3 = highs[-3:], lows[-3:]
        if len(h3) == 3 and len(l3) == 3:
            pts = [{"t": _t(ks, p["i"]), "p": p["p"]} for p in h3]
            pts += [{"t": _t(ks, p["i"]), "p": p["p"]} for p in reversed(l3)]
            geo["points"] = pts
            add_line("trend", h3[0]["p"], "上边界", t0=_t(ks, h3[0]["i"]))
            add_line("trend", l3[0]["p"], "下边界", t0=_t(ks, l3[0]["i"]))
    elif typ in ("FLAG", "FINAL_FLAG_BULL", "FINAL_FLAG_BEAR", "TR", "CUP"):
        w = min(24, len(ks))
        seg = ks[-w:]
        top = max(_f(k[2]) for k in seg)
        bot = min(_f(k[3]) for k in seg)
        geo["box"] = {"top": round(top, 6), "bottom": round(bot, 6),
                      "from_t": _t(ks, len(ks) - w), "to_t": last_t}
        if pat.get("target"):
            add_line("target", pat["target"], "量度目标", dashed=False, strength=3)
    elif typ in ("BO_PB_BULL", "BO_PB_BEAR"):
        p = pat.get("price")
        if p:
            geo["box"] = {"top": round(_f(p) + 0.3 * atr, 6),
                          "bottom": round(_f(p) - 0.3 * atr, 6),
                          "from_t": _t(ks, max(0, i - 12)), "to_t": last_t}
    geo["marker"] = {
        "t": _t(ks, i), "p": pat.get("price") or _f(ks[i][4]),
        "side": "above" if (pat.get("direction") == "bearish") else "below",
        "label": pat.get("label") or typ,
        "direction": pat.get("direction"),
        "quality": pat.get("quality"),
    }
    return geo


def build(ks, f, patterns, struct, primary_interval="4h"):
    """Return the full annotation payload for one interval."""
    if not ks:
        return {"pivots": [], "levels": {}, "zones": [], "channels": [],
                "patterns": [], "markers": [], "meta": {}}
    atr = _atr(ks, 14)
    highs = [_f(k[2]) for k in ks]
    lows = [_f(k[3]) for k in ks]
    raw = zigzag(highs, lows, atr, mult=0.45)
    labeled = label_pivots(raw)
    pivots = []
    for p in labeled:
        t = _t(ks, p["i"])
        pivots.append({"i": p["i"], "t": t, "p": round(p["p"], 6),
                       "kind": p["kind"], "label": p.get("label")})
    price = f.get("price") or _f(ks[-1][4])
    hi_pts = [p for p in pivots if p["kind"] == "H"]
    lo_pts = [p for p in pivots if p["kind"] == "L"]
    supports = _cluster(lo_pts, atr, "support", price)
    resistances = _cluster(hi_pts, atr, "resistance", price)
    for s in supports + resistances:
        s["last_t"] = next((p["t"] for p in reversed(pivots)
                            if abs(p["p"] - s["price"]) <= 0.35 * atr), None)

    out_pats = []
    allp = sorted(patterns or [], key=lambda x: (x.get("quality") or 0), reverse=True)
    for pat in allp[:MAX_PATTERNS]:
        geo = _pattern_geometry(ks, pat, pivots, atr)
        if not geo:
            continue
        out_pats.append({
            "id": "%s-%s-%s" % (pat.get("type"), pat.get("index"), pat.get("label")),
            "type": pat.get("type"),
            "label": pat.get("label"),
            "direction": pat.get("direction"),
            "quality": pat.get("quality"),
            "stage": pat.get("stage"),
            "note": pat.get("note"),
            "target": pat.get("target"),
            "stop": pat.get("stop"),
            "points": [p for p in geo["points"] if p["t"] is not None],
            "lines": [ln for ln in geo["lines"] if ln["from_t"] is not None],
            "box": geo["box"],
            "marker": geo["marker"],
        })

    markers = []
    for p in pivots[-14:]:
        if p["label"] in ("HH", "HL", "LH", "LL"):
            markers.append({"t": p["t"], "p": p["p"],
                            "side": "above" if p["kind"] == "H" else "below",
                            "kind": "pivot", "label": p["label"]})
    for p in out_pats:
        m = p.get("marker")
        if m and m.get("t"):
            markers.append({"t": m["t"], "p": m["p"], "side": m["side"],
                            "kind": "pattern", "label": p["label"],
                            "direction": p["direction"]})
    markers.sort(key=lambda x: x["t"])

    return {
        "pivots": pivots,
        "zigzag": [{"t": p["t"], "p": p["p"]} for p in pivots],
        "levels": {"supports": supports, "resistances": resistances},
        "zones": _zones(ks, pivots, atr, struct),
        "channels": _channels(ks, pivots, atr),
        "patterns": out_pats,
        "markers": markers,
        "meta": {
            "interval": primary_interval,
            "atr": round(atr, 6),
            "pivots": len(pivots),
            "pattern_count": len(out_pats),
        },
    }
