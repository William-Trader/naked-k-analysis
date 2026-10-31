"""Zero-dependency dashboard server for naked-k-analysis."""
from __future__ import annotations

import gzip
import json
import os
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

# Allow `python3 dashboard/server.py` from the repo root (or any cwd):
# the repo root must be importable so `nakedk` / `beagle` resolve.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
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
from nakedk.params import load as load_params, save as save_params

DB = os.environ.get("BEAGLE_DB", "/opt/naked-k-analysis/beagle.db")
KB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge")
DRAWINGS = os.path.join(os.path.dirname(__file__), "..", "drawings.json")
PATTERN_DB = os.environ.get("NK_PATTERN_DB", os.path.join(os.path.dirname(__file__), "..", "patterns.db"))
TOKEN = os.environ.get("NK_DASH_TOKEN", "")
CACHE_TTL = 60          # serve exactly this fresh window
STALE_TTL = 900         # after that, serve stale while refreshing in background
SYMBOLS = ("BTCUSDT", "ETHUSDT")
CACHE_DIR = os.environ.get("NK_CACHE_DIR") or os.path.join(_REPO_ROOT, "state")
_cache = {}
_lock = threading.Lock()
_build_locks = {}
_refreshing = set()
_exec = ThreadPoolExecutor(max_workers=16, thread_name_prefix="nk-fetch")


def _cache_path(interval):
    return os.path.join(CACHE_DIR, "overview_%s.json" % interval)


def _load_disk_cache():
    """Warm the in-memory cache from the last payload so a restart is instant."""
    for interval in VALID:
        try:
            with open(_cache_path(interval), encoding="utf-8") as fh:
                obj = json.load(fh)
            if isinstance(obj, dict) and obj.get("data") and obj.get("ts"):
                _cache[interval] = {"ts": int(obj["ts"]), "data": obj["data"]}
        except Exception:
            pass


def _save_disk_cache(interval, out):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        p = _cache_path(interval)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"ts": int(time.time() * 1000), "data": out},
                      fh, ensure_ascii=False)
        os.replace(tmp, p)
    except Exception:
        pass


def _interval_lock(interval):
    with _lock:
        return _build_locks.setdefault(interval, threading.Lock())


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


def _refresh_async(interval):
    """Refresh one interval in the background without blocking readers."""
    with _lock:
        if interval in _refreshing:
            return
        _refreshing.add(interval)

    def run():
        try:
            _build_now(interval)
        except Exception:
            pass
        finally:
            with _lock:
                _refreshing.discard(interval)

    threading.Thread(target=run, name="nk-refresh-" + interval, daemon=True).start()


def _prefetch(interval):
    """Fetch every network resource for all symbols concurrently.

    Includes the three MTF timeframes, so `mtf_alignment` never blocks on a
    sequential 1d/4h/1h fetch chain (the dominant cold-build cost on slow links).
    """
    tf_limits = {"1d": 120, "4h": 200, "1h": 200}
    futs = {}
    for sym in SYMBOLS:
        futs[(sym, "ticker")] = _exec.submit(ticker, sym)
        futs[(sym, "klines")] = _exec.submit(klines, sym, interval, 200)
        futs[(sym, "day")] = _exec.submit(klines, sym, "1d", 5)
        for tf, lim in tf_limits.items():
            futs[(sym, "mtf_" + tf)] = _exec.submit(klines, sym, tf, lim)
    bundle = {}
    for sym in SYMBOLS:
        t = futs[(sym, "ticker")].result()
        ks = futs[(sym, "klines")].result()
        try:
            day = futs[(sym, "day")].result()
        except Exception:
            day = []
        ks_cache = {(sym, interval): ks}
        for tf in tf_limits:
            try:
                ks_cache[(sym, tf)] = futs[(sym, "mtf_" + tf)].result()
            except Exception:
                pass

        def _klines(symbol, tf, limit, _cache=ks_cache):
            return _cache.get((symbol, tf)) or klines(symbol, tf, limit)

        try:
            mtf = mtf_alignment(sym, klines_fn=_klines)
        except Exception:
            mtf = {"by_tf": {"1d": 0, "4h": 0, "1h": 0}, "alignment": 0, "label": "unknown"}
        bundle[sym] = (t, ks, mtf, day)
    return bundle


def build(interval="4h"):
    """Return the dashboard payload, using a fresh cache or stale-while-revalidate."""
    if interval not in VALID:
        interval = "4h"
    now = int(time.time() * 1000)
    c = _cache.get(interval)
    if c:
        age = (now - c["ts"]) / 1000.0
        if age < CACHE_TTL:
            return c["data"]
        if age < STALE_TTL:
            _refresh_async(interval)
            return c["data"]
    return _build_now(interval)


def _build_now(interval):
    """Build the payload once per interval (single-flight); network in parallel."""
    if interval not in VALID:
        interval = "4h"
    with _interval_lock(interval):
        now = int(time.time() * 1000)
        c = _cache.get(interval)
        if c and now - c["ts"] < CACHE_TTL * 1000:
            return c["data"]
        return _build_uncached(interval, now)


def _build_uncached(interval, now):
    params = load_params()
    out = {"as_of": now, "interval": interval, "symbols": {},
           "events": [], "alerts": [], "params": params}
    bundle = _prefetch(interval)
    for sym in SYMBOLS:
        t, ks, mtf, day = bundle[sym]
        k_closed = closed_bars(ks, interval)
        f = features_from_klines(k_closed)
        f["mtf_alignment"] = mtf["alignment"]
        st = stance(f, params)
        ts = trend_score(f, params)
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
        sess = session_levels(closed_bars(day, "1d"))
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
    out["elapsed_ms"] = int((time.time() * 1000) - now)
    _cache[interval] = {"ts": int(time.time() * 1000), "data": out}
    _save_disk_cache(interval, out)
    return out


def _knowledge(file: str):
    """List knowledge modules, or return one module's raw markdown."""
    if file:
        name = os.path.basename(file)
        if not name.endswith(".md"):
            return {"error": "bad file"}
        p = os.path.join(KB_DIR, name)
        try:
            with open(p, encoding="utf-8") as fh:
                return {"file": name, "content": fh.read()}
        except Exception as e:
            return {"error": str(e)[:200]}
    items = []
    try:
        for name in sorted(os.listdir(KB_DIR)):
            if name.endswith(".md"):
                p = os.path.join(KB_DIR, name)
                with open(p, encoding="utf-8") as fh:
                    head = fh.readline().strip().lstrip("#").strip()
                items.append({"file": name, "title": head,
                              "bytes": os.path.getsize(p)})
    except Exception as e:
        return {"error": str(e)[:200]}
    return {"modules": items}


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
        if urlparse(self.path).path == "/api/params":
            self._send(json.dumps(load_params(), ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")
            return
        if urlparse(self.path).path == "/api/knowledge":
            self._send(json.dumps(_knowledge((q.get("file") or [""])[0]),
                                   ensure_ascii=False).encode("utf-8"),
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
        # serve static assets (vendor JS) if present, else the SPA shell
        req_path = urlparse(self.path).path
        if req_path.startswith("/vendor/") or req_path.endswith((".js", ".css", ".png", ".svg", ".ico", ".map")):
            rel = req_path.lstrip("/")
            fp = os.path.join(os.path.dirname(__file__), rel)
            if os.path.isfile(fp):
                ctype = "text/javascript; charset=utf-8" if rel.endswith(".js") else \
                        "text/css; charset=utf-8" if rel.endswith(".css") else \
                        "application/octet-stream"
                with open(fp, "rb") as fh:
                    self._send(fh.read(), ctype)
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
        path = urlparse(self.path).path
        if path not in ("/api/drawings", "/api/params"):
            self.send_response(404)
            self.end_headers()
            return
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n).decode("utf-8")
        try:
            body = json.loads(raw)
            if path == "/api/params":
                self._send(json.dumps(save_params(body), ensure_ascii=False).encode("utf-8"),
                           "application/json; charset=utf-8")
            else:
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
    _load_disk_cache()

    def _warm():
        # Pre-build so the first browser hit is instant instead of waiting
        # for a cold 4h payload (~tens of seconds on slow links).
        for interval in ("4h", "1h", "1d"):
            try:
                _build_now(interval)
            except Exception:
                pass

    threading.Thread(target=_warm, name="nk-warm", daemon=True).start()
    print(f"naked-k dashboard on :{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
