"""Zero-dependency dashboard server for naked-k-analysis."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from nakedk.fetch import klines, ticker
from nakedk.features import features_from_klines
from nakedk.signals import stance
from nakedk.trend import trend_score

DB = os.environ.get("BEAGLE_DB", "/opt/naked-k-analysis/beagle.db")
CACHE_TTL = 60
_cache = {"ts": 0, "data": None}


def ema_series(vals, n):
    if not vals:
        return []
    k = 2.0 / (n + 1)
    e = float(vals[0])
    out = []
    for v in vals:
        e = float(v) * k + e * (1 - k)
        out.append(e)
    return out


def local_swings(ks, w=2, keep=5):
    hs, ls = [], []
    for i in range(w, len(ks) - w):
        if float(ks[i][2]) == max(float(x[2]) for x in ks[i - w:i + w + 1]):
            hs.append((i, float(ks[i][2])))
        if float(ks[i][3]) == min(float(x[3]) for x in ks[i - w:i + w + 1]):
            ls.append((i, float(ks[i][3])))
    return hs[-keep:], ls[-keep:]


def detect_patterns(ks, f, hs, ls):
    pats = []
    p = f["price"]
    if len(ls) >= 2:
        a, b = ls[-2][1], ls[-1][1]
        if abs(a - b) / p < 0.0035 and p > max(a, b):
            pats.append({"type": "DB", "label": "双底候选", "price": min(a, b)})
    if len(hs) >= 2:
        a, b = hs[-2][1], hs[-1][1]
        if abs(a - b) / p < 0.0035 and p < min(a, b):
            pats.append({"type": "DT", "label": "双顶候选", "price": max(a, b)})
    if f["ema20"] > f["ema50"] and f["price"] > f["ema20"] and len(ls) >= 2 and ls[-1][1] > ls[-2][1]:
        pats.append({"type": "H2", "label": "H2 回调", "price": ls[-1][1]})
    if f["ema20"] < f["ema50"] and f["price"] < f["ema20"] and len(hs) >= 2 and hs[-1][1] < hs[-2][1]:
        pats.append({"type": "L2", "label": "L2 反弹", "price": hs[-1][1]})
    if len(hs) >= 3 and hs[-1][1] > hs[-2][1] > hs[-3][1]:
        pats.append({"type": "WEDGE_UP", "label": "上升楔形", "price": hs[-1][1]})
    if len(ls) >= 3 and ls[-1][1] < ls[-2][1] < ls[-3][1]:
        pats.append({"type": "WEDGE_DOWN", "label": "下降楔形", "price": ls[-1][1]})
    return pats


def structure_label(hs, ls):
    sh = [p for _, p in hs]
    sl = [p for _, p in ls]
    hh = len(sh) >= 2 and sh[-1] > sh[-2]
    hl = len(sl) >= 2 and sl[-1] > sl[-2]
    lh = len(sh) >= 2 and sh[-1] < sh[-2]
    ll = len(sl) >= 2 and sl[-1] < sl[-2]
    if hh and hl:
        return 'HH/HL 多头结构'
    if lh and ll:
        return 'LH/LL 空头结构'
    return '重叠/区间'


def build():
    now = int(time.time() * 1000)
    if _cache["data"] and now - _cache["ts"] < CACHE_TTL * 1000:
        return _cache["data"]
    out = {"as_of": now, "symbols": {}, "events": [], "alerts": []}
    for sym in ("BTCUSDT", "ETHUSDT"):
        t = ticker(sym)
        k4 = klines(sym, "4h", 200)
        f = features_from_klines(k4)
        st = stance(f)
        ts = trend_score(f)
        closes_all = [float(r[4]) for r in k4]
        e20 = ema_series(closes_all, 20)[-120:]
        e50 = ema_series(closes_all, 50)[-120:]
        candles = [{"t": r[0], "o": float(r[1]), "h": float(r[2]),
                    "l": float(r[3]), "c": float(r[4]), "v": float(r[5])}
                   for r in k4[-120:]]
        hs, ls = local_swings(k4[-120:])
        out["symbols"][sym] = {
            "price": f["price"],
            "change24h": float(t["priceChangePercent"]),
            "high24h": float(t["highPrice"]),
            "low24h": float(t["lowPrice"]),
            "ema20": f["ema20"], "ema50": f["ema50"],
            "adx": f["adx14"], "rsi": f["rsi14"], "atr_pct": f["atr_pct"],
            "vol_z": f["vol_z"], "pos20": f["pos20"],
            "r20_lo": f["r20_lo"], "r20_hi": f["r20_hi"],
            "swing_highs": f["swing_highs"], "swing_lows": f["swing_lows"],
            "trend": ts, "stance": st,
            "candles": candles,
            "ema20_series": e20,
            "ema50_series": e50,
            "swing_marks": {
                "highs": [{"i": i, "p": p} for i, p in hs],
                "lows": [{"i": i, "p": p} for i, p in ls],
            },
            "patterns": detect_patterns(k4[-120:], f, hs, ls),
            "structure": structure_label(hs, ls),
        }
    try:
        conn = sqlite3.connect(DB, timeout=5)
        conn.row_factory = sqlite3.Row
        out["events"] = [dict(r) for r in conn.execute(
            "SELECT ts,symbol,kind,severity,direction,price FROM events ORDER BY id DESC LIMIT 8"
        ).fetchall()]
        out["alerts"] = [dict(r) for r in conn.execute(
            "SELECT severity,text,status,created_at FROM alerts ORDER BY id DESC LIMIT 5"
        ).fetchall()]
        conn.close()
    except Exception as e:
        out["db_error"] = str(e)
    _cache.update(ts=now, data=out)
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/overview"):
            self._send(json.dumps(build(), ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")
            return
        path = os.path.join(os.path.dirname(__file__), "index.html")
        with open(path, "rb") as fh:
            self._send(fh.read(), "text/html; charset=utf-8")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"naked-k dashboard on :{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
