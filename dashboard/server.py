"""Zero-dependency API + static server for the price-action terminal.

Layers
------
dashboard/app/*.js   browser ES modules (no build step, no CDN)
nakedk/analysis.py   deterministic analysis payload
beagle/engine.py     automation: analyse -> plan -> trigger -> confirm
beagle/store.py      SQLite plans / plan_events / outbox
nakedk/llm.py        optional commentary + guarded parameter proposals

Endpoints are intentionally small JSON documents so the frontend can poll,
stream (SSE) or be replaced without touching the engine.
"""
from __future__ import annotations

import gzip
import json
import os
import queue
import sqlite3
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from beagle import engine, push, store
from nakedk import llm, symbol_params
from nakedk.markets import universe

DB = os.environ.get("BEAGLE_DB", os.path.join(_REPO_ROOT, "beagle.db"))
DASH = os.path.dirname(os.path.abspath(__file__))
TOKEN = os.environ.get("NK_DASH_TOKEN", "")
PORT = int(os.environ.get("PORT", "8080"))
CACHE_TTL = 45
STALE_TTL = 600

_cache = {}
_build_locks = {}
_refreshing = set()
_lock = threading.Lock()
_exec = ThreadPoolExecutor(max_workers=8, thread_name_prefix="nk-api")
_subs = []
_subs_lock = threading.Lock()

STATIC_TYPES = {
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json",
}


# ---------------------------------------------------------------------------
# cache + broadcast
# ---------------------------------------------------------------------------

def _build_lock(symbol):
    with _lock:
        return _build_locks.setdefault(symbol, threading.Lock())


def _broadcast(event, data):
    with _subs_lock:
        dead = []
        for q in _subs:
            try:
                q.put_nowait((event, data))
            except Exception:
                dead.append(q)
        for q in dead:
            try:
                _subs.remove(q)
            except ValueError:
                pass


def _payload(symbol, force=False):
    """Cached plan-aware payload; stale-while-revalidate."""
    now = int(time.time() * 1000)
    c = _cache.get(symbol)
    if c and not force:
        age = (now - c["ts"]) / 1000.0
        if age < CACHE_TTL:
            return c["data"]
        if age < STALE_TTL:
            _refresh(symbol)
            return c["data"]
    return _build(symbol, now)


def _refresh(symbol):
    with _lock:
        if symbol in _refreshing:
            return
        _refreshing.add(symbol)

    def run():
        try:
            _build(symbol, int(time.time() * 1000), force=True)
        except Exception:
            pass
        finally:
            with _lock:
                _refreshing.discard(symbol)

    threading.Thread(target=run, name="nk-refresh-" + symbol, daemon=True).start()


def _build(symbol, now=None, force=False):
    with _build_lock(symbol):
        now = now or int(time.time() * 1000)
        c = _cache.get(symbol)
        if c and not force and now - c["ts"] < CACHE_TTL * 1000:
            return c["data"]
        settings = engine.load_settings()
        try:
            data = engine.analyze_symbol(symbol, settings, DB)
        except Exception as e:
            data = {"symbol": symbol, "error": str(e)[:300],
                    "as_of": now, "intervals": {}, "combined": {},
                    "plan": None, "candles": []}
        data["server_ts"] = now
        data["history"] = _history(symbol)
        _cache[symbol] = {"ts": now, "data": data}
        _broadcast("symbol", {"symbol": symbol,
                              "price": data.get("price"),
                              "plan": data.get("plan"),
                              "combined": data.get("combined")})
        return data


def _history(symbol):
    try:
        return {"plans": store.list_plans(DB, symbol, 12),
                "events": store.plan_events(DB, None, 30)}
    except Exception:
        return {"plans": [], "events": []}


# ---------------------------------------------------------------------------
# API handlers
# ---------------------------------------------------------------------------

def api_health():
    try:
        store.init(DB)
        stats = store.plan_stats(DB)
        db_ok = True
    except Exception as e:
        stats = {"error": str(e)[:200]}
        db_ok = False
    s = engine.load_settings()
    return {
        "ok": db_ok,
        "service": "naked-k-price-action-terminal",
        "version": "2.0.0",
        "as_of": int(time.time() * 1000),
        "db": DB,
        "plans": stats,
        "active_symbols": s.get("active_symbols"),
        "mode": s.get("mode"),
        "intervals": engine.intervals_for(s),
        "auto_analyze": s.get("auto_analyze"),
        "auto_trigger": s.get("auto_trigger"),
        "auto_push": s.get("auto_push"),
        "llm": llm.status(),
        "cache": sorted(_cache.keys()),
    }


def api_universe():
    s = engine.load_settings()
    return {"universe": universe(), "settings": s,
            "markets": sorted({x["market"] for x in universe()})}


def api_overview(q):
    s = engine.load_settings()
    raw = (q.get("symbols") or [""])[0]
    syms = [x.strip().upper() for x in raw.split(",") if x.strip()] or \
        list(s.get("active_symbols") or ["BTCUSDT", "ETHUSDT"])
    syms = syms[: int(s.get("max_symbols") or 6)]
    ivs = [x for x in (q.get("intervals") or [""])[0].split(",") if x]
    if ivs:
        s = dict(s)
        s["intervals"] = ivs
        s["mode"] = "multi" if len(ivs) > 1 else "single"
        if len(ivs) == 1:
            s["single_interval"] = ivs[0]
    syms = list(dict.fromkeys(syms))
    futs = {sym: _exec.submit(_payload, sym) for sym in syms}
    out, errors = {}, {}
    for sym, fut in futs.items():
        try:
            out[sym] = fut.result()
        except Exception as e:
            errors[sym] = str(e)[:200]
    return {"as_of": int(time.time() * 1000), "settings": s,
            "symbols": out, "errors": errors}


def api_symbol(q):
    sym = (q.get("symbol") or [""])[0].strip().upper()
    if not sym:
        return {"error": "symbol required"}
    data = _payload(sym, force=(q.get("force") or ["0"])[0] in ("1", "true"))
    data["history"] = _history(sym)
    return data


def api_plans(q):
    sym = (q.get("symbol") or [""])[0].strip().upper() or None
    return {"open": store.open_plans(DB, sym),
            "history": store.list_plans(DB, sym, 30),
            "events": store.plan_events(DB, None, 50),
            "stats": store.plan_stats(DB, sym)}


def api_events(q):
    limit = int((q.get("limit") or ["40"])[0])
    return {"plan_events": store.plan_events(DB, None, min(200, limit)),
            "alerts": _legacy_alerts(limit)}


def _legacy_alerts(limit=8):
    try:
        conn = sqlite3.connect(DB, timeout=5)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(
            "SELECT severity,text,status,created_at FROM alerts "
            "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


def api_knowledge(q):
    kb_dir = os.path.join(_REPO_ROOT, "knowledge")
    name = (q.get("file") or [""])[0]
    if name:
        name = os.path.basename(name)
        if not name.endswith(".md"):
            return {"error": "bad file"}
        try:
            with open(os.path.join(kb_dir, name), encoding="utf-8") as fh:
                return {"file": name, "content": fh.read()}
        except Exception as e:
            return {"error": str(e)[:200]}
    items = []
    try:
        for n in sorted(os.listdir(kb_dir)):
            if n.endswith(".md"):
                p = os.path.join(kb_dir, n)
                with open(p, encoding="utf-8") as fh:
                    head = fh.readline().strip().lstrip("#").strip()
                items.append({"file": n, "title": head,
                              "bytes": os.path.getsize(p)})
    except Exception as e:
        return {"error": str(e)[:200]}
    return {"modules": items}


def api_llm_annotate(body):
    sym = (body.get("symbol") or "").strip().upper()
    if not sym:
        return {"error": "symbol required"}
    p = _payload(sym)
    slim = {
        "symbol": p.get("symbol"), "price": p.get("price"),
        "change24h": p.get("change24h"),
        "combined": p.get("combined"), "mtf": p.get("mtf"),
        "intervals": {
            tf: {
                "stance": v.get("stance"), "structure": {
                    "state": (v.get("structure") or {}).get("state"),
                    "bos": (v.get("structure") or {}).get("bos"),
                    "levels": (v.get("structure") or {}).get("levels")},
                "features": v.get("features"),
                "patterns": [{"type": x.get("type"), "label": x.get("label"),
                              "direction": x.get("direction"),
                              "quality": x.get("quality")}
                             for x in (v.get("patterns") or [])[:4]],
                "levels": (v.get("annotations") or {}).get("levels"),
            }
            for tf, v in (p.get("intervals") or {}).items()
        },
    }
    return llm.annotate(slim)


def api_llm_optimize(body):
    sym = (body.get("symbol") or "").strip().upper()
    if not sym:
        return {"error": "symbol required"}
    stats = store.plan_stats(DB, sym)
    prof = symbol_params.profile(sym)
    payload = {
        "symbol": sym,
        "current_params": {k: prof["effective"].get(k) for k in symbol_params.BOUNDS},
        "stats": stats,
        "recent_events": store.plan_events(DB, None, 40),
    }
    res = llm.propose_params(payload, symbol_params.BOUNDS, symbol_params.BOUNDS)
    res["validation"] = symbol_params.validate_patch(res.get("patch") or {})
    res["applied"] = False
    if body.get("apply") and res.get("patch") and not res["validation"]:
        res["profile"] = symbol_params.save(
            sym, res["patch"], source="llm",
            note=(res.get("rationale") or "manual LLM tune")[:180])
        res["applied"] = True
    return res


def api_settings(body=None):
    if body is None:
        return engine.load_settings()
    s = engine.save_settings(body)
    _broadcast("settings", s)
    return s


def api_symbol_params(q, body=None):
    if body is not None:
        sym = (body.get("symbol") or "").strip().upper()
        if not sym:
            return {"error": "symbol required"}
        if body.get("revert"):
            return {"profile": symbol_params.revert(sym)}
        return {"profile": symbol_params.save(
            sym, body.get("patch") or {}, source=body.get("source") or "manual",
            note=body.get("note") or "")}
    sym = (q.get("symbol") or [""])[0].strip().upper()
    if sym:
        return {"profile": symbol_params.profile(sym)}
    return {"defaults": symbol_params.defaults(),
            "bounds": symbol_params.BOUNDS,
            "profiles": symbol_params.all_profiles()}


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, fmt, *args):
        if os.environ.get("NK_VERBOSE"):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, body, ctype="application/json; charset=utf-8", status=200):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        gz = len(body) > 1200 and "gzip" in (self.headers.get("Accept-Encoding") or "")
        if gz:
            body = gzip.compress(body, 6)
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        if gz:
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def _authorized(self, q):
        if not TOKEN:
            return True
        if self.headers.get("Authorization", "") == "Bearer " + TOKEN:
            return True
        return (q.get("token") or [""])[0] == TOKEN

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            return json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        path = u.path
        if not self._authorized(q):
            self._send({"error": "unauthorized"}, status=401)
            return
        try:
            if path == "/api/health":
                return self._send(api_health())
            if path == "/api/universe":
                return self._send(api_universe())
            if path == "/api/overview":
                return self._send(api_overview(q))
            if path == "/api/symbol":
                return self._send(api_symbol(q))
            if path == "/api/plans":
                return self._send(api_plans(q))
            if path == "/api/events":
                return self._send(api_events(q))
            if path == "/api/settings":
                return self._send(api_settings())
            if path == "/api/symbol-params":
                return self._send(api_symbol_params(q))
            if path == "/api/llm/status":
                return self._send(llm.status())
            if path == "/api/knowledge":
                return self._send(api_knowledge(q))
            if path == "/api/stream":
                return self._stream(q)
            if path == "/api/params":
                from nakedk.params import load as load_params
                return self._send(load_params())
            if path == "/api/drawings":
                return self._send(self._drawings(q))
            # static files, then SPA fallback
            if self._static(path):
                return
            return self._send(self._index(), "text/html; charset=utf-8")
        except BrokenPipeError:
            pass
        except Exception as e:
            tb = traceback.format_exc(limit=4)
            self._send({"error": str(e)[:300], "trace": tb[-800:]}, status=500)

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if not self._authorized(q):
            return self._send({"error": "unauthorized"}, status=401)
        body = self._body()
        try:
            if u.path == "/api/settings":
                return self._send(api_settings(body))
            if u.path == "/api/symbol-params":
                return self._send(api_symbol_params(q, body))
            if u.path == "/api/llm/annotate":
                return self._send(api_llm_annotate(body))
            if u.path == "/api/llm/optimize":
                return self._send(api_llm_optimize(body))
            if u.path == "/api/plan/action":
                return self._send(self._plan_action(body))
            if u.path == "/api/analyze":
                sym = (body.get("symbol") or "").strip().upper()
                if not sym:
                    return self._send({"error": "symbol required"})
                return self._send(_payload(sym, force=True))
            return self._send({"error": "not found"}, status=404)
        except Exception as e:
            self._send({"error": str(e)[:300]}, status=500)

    def _plan_action(self, body):
        """Manual control: void an armed plan (user override only)."""
        pid = int(body.get("plan_id") or 0)
        plan = store.get_plan(DB, pid)
        if not plan:
            return {"error": "plan not found"}
        if body.get("action") == "void" and plan.get("status") in (
                "armed", "triggered", "confirmed", "managing"):
            ev = {"type": "void", "price": body.get("price"),
                  "ts": int(time.time() * 1000), "to_status": "void",
                  "outcome": "manual", "reason": "用户手动作废"}
            from nakedk.plans import apply as apply_plan, event_key
            plan = apply_plan(plan, ev)
            plan = store.save_plan(DB, plan)
            store.add_plan_event(DB, plan, ev, event_key(plan, ev))
        return {"plan": plan}

    def _drawings(self, q):
        path = os.path.join(_REPO_ROOT, "drawings.json")
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}

    def _static(self, path):
        if path == "/styles.css":
            rel = "styles.css"
        elif path.startswith("/app/") or path.startswith("/vendor/"):
            rel = path.lstrip("/")
        else:
            return False
        base = os.path.abspath(DASH)
        full = os.path.abspath(os.path.join(base, rel))
        if not full.startswith(base + os.sep) or not os.path.isfile(full):
            self._send({"error": "not found"}, status=404)
            return True
        ctype = STATIC_TYPES.get(os.path.splitext(full)[1], "application/octet-stream")
        try:
            with open(full, "rb") as fh:
                raw = fh.read()
        except Exception:
            self._send({"error": "read error"}, status=500)
            return True
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
        return True

    def _index(self):
        try:
            with open(os.path.join(DASH, "index.html"), encoding="utf-8") as fh:
                return fh.read()
        except Exception as e:
            return "<h1>dashboard/index.html missing</h1><pre>%s</pre>" % e

    def _stream(self, q):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        qq = queue.Queue(maxsize=80)
        with _subs_lock:
            _subs.append(qq)
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            self.wfile.write(("event: hello\ndata: %s\n\n" % json.dumps(
                {"as_of": int(time.time() * 1000)})).encode())
            self.wfile.flush()
            while True:
                try:
                    ev, data = qq.get(timeout=15)
                    chunk = "event: %s\ndata: %s\n\n" % (
                        ev, json.dumps(data, ensure_ascii=False, default=str))
                    self.wfile.write(chunk.encode())
                    self.wfile.flush()
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with _subs_lock:
                try:
                    _subs.remove(qq)
                except ValueError:
                    pass


# ---------------------------------------------------------------------------
# background automation
# ---------------------------------------------------------------------------

class EngineThread(threading.Thread):
    def __init__(self):
        super().__init__(name="nk-engine", daemon=True)
        self.stop_event = threading.Event()

    def run(self):
        try:
            store.init(DB)
        except Exception:
            pass
        last_analysis = 0
        while not self.stop_event.is_set():
            s = engine.load_settings()
            try:
                now = int(time.time() * 1000)
                if s.get("auto_analyze") and now - last_analysis > 120_000:
                    for sym in s.get("active_symbols") or []:
                        try:
                            _build(sym, force=True)
                        except Exception:
                            pass
                    last_analysis = now
                if s.get("auto_analyze"):
                    engine.level_watch(s, DB)
                if s.get("auto_trigger"):
                    events = engine.tick(s, DB)
                    for ev in events:
                        _broadcast("plan", ev)
                if s.get("auto_push"):
                    push.push_outbox(DB, s)
            except Exception:
                pass
            self.stop_event.wait(max(5, int(s.get("trigger_seconds") or 20)))


def main():
    store.init(DB)
    EngineThread().start()
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("price-action terminal on http://127.0.0.1:%d  db=%s" % (PORT, DB))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
