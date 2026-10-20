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

DB = os.environ.get("BEAGLE_DB", "/opt/naked-k-analysis/beagle-app/beagle.db")
CACHE_TTL = 60
_cache = {"ts": 0, "data": None}


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
            "closes": [float(r[4]) for r in k4[-60:]],
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
