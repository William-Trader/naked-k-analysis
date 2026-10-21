"""Zero-dependency dashboard server for naked-k-analysis."""
from __future__ import annotations

import gzip
import json
import os
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from nakedk.fetch import klines, ticker
from nakedk.features import features_from_klines
from nakedk.patterns import arbitrate, detect as detect_patterns
from nakedk.pattern_tracker import states as pattern_states, track as track_patterns
from nakedk.signals import stance
from nakedk.trend import trend_score
from nakedk.bars import profile_series, closed_bars
from nakedk.structure import structure as structure_of
from nakedk.mtf import alignment as mtf_alignment
from nakedk.volume import vpoc
from nakedk.location import atr_distance, edge_zone, session_levels
from nakedk.signalbar import score as signalbar_score
from nakedk.regime import arbitrate as arbitrate_regime

DB = os.environ.get("BEAGLE_DB", "/opt/naked-k-analysis/beagle.db")
DRAWINGS = os.path.join(os.path.dirname(__file__), "..", "drawings.json")
PATTERN_DB = os.environ.get("NK_PATTERN_DB", os.path.join(os.path.dirname(__file__), "..", "patterns.db"))
TOKEN = os.environ.get("NK_DASH_TOKEN", "")
CACHE_TTL = 60
_cache = {}
_lock = threading.Lock()


def load_drawings():
    try:
        with open(DRAWINGS, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_drawings(symbol, lines):
    with _lock:
        data = load_drawings()
        data[symbol] = lines
        tmp = DRAWINGS + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.replace(tmp, DRAWINGS)
VALID = ("1h", "4h", "1d")


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


def structure_label(hs, ls):
    sh = [p for _, p in hs]
    sl = [p for _, p in ls]
    hh = len(sh) >= 2 and sh[-1] > sh[-2]
    hl = len(sl) >= 2 and sl[-1] > sl[-2]
    lh = len(sh) >= 2 and sh[-1] < sh[-2]
    ll = len(sl) >= 2 and sl[-1] < sl[-2]
    if hh and hl:
        return "HH/HL 多头结构"
    if lh and ll:
        return "LH/LL 空头结构"
    return "重叠/区间"


def build(interval="4h"):
    if interval not in VALID:
        interval = "4h"
    now = int(time.time() * 1000)
    c = _cache.get(interval)
    if c and now - c["ts"] < CACHE_TTL * 1000:
        return c["data"]
    out = {"as_of": now, "interval": interval, "symbols": {},
           "events": [], "alerts": []}
    for sym in ("BTCUSDT", "ETHUSDT"):
        t = ticker(sym)
        ks = klines(sym, interval, 200)
        k_closed = closed_bars(ks, interval)
        f = features_from_klines(k_closed)
        try:
            mtf = mtf_alignment(sym)
        except Exception:
            mtf = {"by_tf": {"1d": 0, "4h": 0, "1h": 0}, "alignment": 0, "label": "unknown"}
        f["mtf_alignment"] = mtf["alignment"]
        st = stance(f)
        ts = trend_score(f)
        closes = [float(r[4]) for r in ks]
        e20 = ema_series(closes, 20)
        e50 = ema_series(closes, 50)
        candles = [{"t": r[0], "o": float(r[1]), "h": float(r[2]),
                    "l": float(r[3]), "c": float(r[4]), "v": float(r[5])}
                   for r in ks]
        marks = f.get("swing_marks") or {}
        hs = [(m["i"], m["p"]) for m in marks.get("highs", [])]
        ls = [(m["i"], m["p"]) for m in marks.get("lows", [])]
        arb = arbitrate(detect_patterns(k_closed, f), f)
        try:
            track_patterns(sym, arb["patterns"], PATTERN_DB, f["price"])
        except Exception:
            pass
        profiles = profile_series(k_closed)
        bar_profile = profiles[-1] if profiles else {}
        prev_bar = profiles[-2] if len(profiles) > 1 else None
        struct_v2 = structure_of(k_closed)
        vp = vpoc(k_closed)
        sess = session_levels(closed_bars(klines(sym, "1d", 5), "1d"))
        lv = struct_v2.get("levels", {})
        loc = {
            "edge": edge_zone(f.get("pos20")),
            "to_swing_hi": atr_distance(f["price"], lv.get("swing_high"), struct_v2.get("atr")),
            "to_swing_lo": atr_distance(f["price"], lv.get("swing_low"), struct_v2.get("atr")),
            "prev_day": sess,
        }
        _pdir = ("long" if (arb["primary"] or {}).get("direction") == "bullish"
                 else "short" if (arb["primary"] or {}).get("direction") == "bearish" else None)
        sb = signalbar_score(bar_profile, prev_bar, _pdir, f.get("pos20")) if _pdir else {}
        reg = arbitrate_regime(struct_v2.get("state"),
                               (mtf.get("by_state") or {}).get("1d"),
                               mtf.get("alignment"), f.get("adx14"),
                               f.get("adx_slope"), f.get("overlap"))
        out["symbols"][sym] = {
            "regime": reg,
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
            "data_ts": candles[-1]["t"] if candles else None,
            "source": "binance",
            "patterns": arb["patterns"],
            "primary_pattern": arb["primary"],
            "secondary_pattern": arb["secondary"],
            "pattern_context": arb["context"],
            "pattern_states": pattern_states(sym, PATTERN_DB, 8),
            "structure": structure_label(hs, ls),
            "structure_v2": struct_v2,
            "bar": bar_profile,
            "mtf": mtf,
            "volume_profile": vp,
            "location": loc,
            "signalbar": sb,
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
    _cache[interval] = {"ts": now, "data": out}
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, ctype):
        gz = (len(body) > 1024
              and "gzip" in (self.headers.get("Accept-Encoding") or ""))
        if gz:
            body = gzip.compress(body, 6)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        if gz:
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self, q):
        if not TOKEN:
            return True
        if self.headers.get("Authorization", "") == "Bearer " + TOKEN:
            return True
        return (q.get("token") or [""])[0] == TOKEN

    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        if not self._authorized(q):
            self.send_response(401)
            self.send_header("WWW-Authenticate", "Bearer")
            self.end_headers()
            self.wfile.write(b"unauthorized")
            return
        if urlparse(self.path).path == "/api/drawings":
            sym = (q.get("symbol") or [""])[0]
            self._send(json.dumps(load_drawings().get(sym, []), ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")
            return
        if urlparse(self.path).path == "/api/review":
            try:
                from beagle.review import build as build_review
                ap = os.environ.get("NK_ADAPTIVE") or os.path.join(
                    os.path.dirname(DB), "state", "adaptive.json")
                self._send(json.dumps(build_review(DB, ap), ensure_ascii=False).encode("utf-8"),
                           "application/json; charset=utf-8")
            except Exception as e:
                self._send(json.dumps({"error": str(e)[:200]}).encode("utf-8"),
                           "application/json; charset=utf-8", 500)
            return
        if urlparse(self.path).path == "/api/adaptive":
            try:
                from beagle import adaptive
                ap = os.environ.get("NK_ADAPTIVE") or os.path.join(
                    os.path.dirname(DB), "state", "adaptive.json")
                self._send(json.dumps(adaptive.load(ap), ensure_ascii=False).encode("utf-8"),
                           "application/json; charset=utf-8")
            except Exception as e:
                self._send(json.dumps({"error": str(e)[:200]}).encode("utf-8"),
                           "application/json; charset=utf-8", 500)
            return
        if urlparse(self.path).path == "/api/calibration":
            try:
                from nakedk.calibration import table_from_db
                db = os.environ.get("NK_CALIB_DB") or os.path.join(
                    os.path.dirname(__file__), "..", "beagle.db")
                self._send(json.dumps(table_from_db(db), ensure_ascii=False).encode("utf-8"),
                           "application/json; charset=utf-8")
            except Exception as e:
                self._send(json.dumps({"error": str(e)[:200]}).encode("utf-8"),
                           "application/json; charset=utf-8", 500)
            return
        if urlparse(self.path).path.startswith("/api/overview"):
            interval = (q.get("interval") or ["4h"])[0]
            self._send(json.dumps(build(interval), ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")
            return
        path = os.path.join(os.path.dirname(__file__), "index.html")
        with open(path, "rb") as fh:
            self._send(fh.read(), "text/html; charset=utf-8")

    def do_POST(self):
        q = parse_qs(urlparse(self.path).query)
        if not self._authorized(q):
            self.send_response(401)
            self.send_header("WWW-Authenticate", "Bearer")
            self.end_headers()
            self.wfile.write(b"unauthorized")
            return
        if urlparse(self.path).path != "/api/drawings":
            self.send_response(404)
            self.end_headers()
            return
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n).decode("utf-8")
        try:
            body = json.loads(raw)
            save_drawings(body["symbol"], body.get("lines", []))
            self._send(b'{"ok":true}', "application/json")
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"naked-k dashboard on :{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
