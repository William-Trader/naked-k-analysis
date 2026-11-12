"""SQLite state for events, alerts, signals and outcomes.

Every write opens a short-lived connection and closes it explicitly:
sqlite3 context managers commit but do not close, which leaks
connections and eventually raises "database is locked".
"""
from __future__ import annotations

import json
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  kind TEXT NOT NULL,
  severity TEXT NOT NULL,
  direction TEXT,
  price REAL,
  payload TEXT,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_symbol_ts ON events(symbol, ts);

CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id INTEGER UNIQUE,
  severity TEXT NOT NULL,
  text TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  cooldown_until INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  sent_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_key ON alerts(severity, created_at);

CREATE TABLE IF NOT EXISTS signals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  direction TEXT NOT NULL,
  confidence INTEGER,
  entry REAL, stop REAL, target REAL,
  horizon_h INTEGER DEFAULT 4,
  source TEXT
);

CREATE TABLE IF NOT EXISTS outcomes (
  signal_id INTEGER NOT NULL,
  horizon_h INTEGER NOT NULL,
  ts INTEGER NOT NULL,
  price REAL,
  ret_pct REAL,
  hit INTEGER,
  PRIMARY KEY (signal_id, horizon_h)
);

CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  detail TEXT
);

CREATE TABLE IF NOT EXISTS health (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  heartbeat INTEGER NOT NULL,
  last_event_ts INTEGER,
  queue_depth INTEGER,
  errors INTEGER
);

CREATE TABLE IF NOT EXISTS plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  interval TEXT NOT NULL,
  side TEXT NOT NULL,
  setup TEXT,
  status TEXT NOT NULL,
  trigger REAL,
  stop REAL,
  target1 REAL,
  target2 REAL,
  ttl_at INTEGER,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  confirmed_at INTEGER,
  closed_at INTEGER,
  outcome TEXT,
  pnl_pct REAL,
  data TEXT
);
CREATE INDEX IF NOT EXISTS idx_plans_symbol ON plans(symbol, status);
CREATE INDEX IF NOT EXISTS idx_plans_created ON plans(created_at);

CREATE TABLE IF NOT EXISTS plan_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id INTEGER NOT NULL,
  symbol TEXT,
  type TEXT NOT NULL,
  price REAL,
  ts INTEGER NOT NULL,
  payload TEXT,
  idempotency_key TEXT UNIQUE,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plan_events_plan ON plan_events(plan_id, id);

CREATE TABLE IF NOT EXISTS outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_event_id INTEGER NOT NULL,
  channel TEXT NOT NULL,
  text TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  sent_at INTEGER,
  UNIQUE(plan_event_id, channel)
);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox(status, id);

CREATE TABLE IF NOT EXISTS market_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  kind TEXT NOT NULL,
  old_value TEXT,
  new_value TEXT,
  detail TEXT,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_market_events_symbol_ts ON market_events(symbol, ts);

CREATE TABLE IF NOT EXISTS state (
  symbol TEXT PRIMARY KEY,
  state TEXT,
  updated_at INTEGER
);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    # WAL lets the HTTP thread read while the engine writes; busy_timeout
    # replaces the old "database is locked" errors that were swallowed by
    # bare `except: pass` in the loops.
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass
    return conn


def init(path: str) -> None:
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(alerts)").fetchall()]
        for col, ddl in (
            ("attempts", "ALTER TABLE alerts ADD COLUMN attempts INTEGER DEFAULT 0"),
            ("last_error", "ALTER TABLE alerts ADD COLUMN last_error TEXT"),
            ("next_attempt_at", "ALTER TABLE alerts ADD COLUMN next_attempt_at INTEGER DEFAULT 0"),
        ):
            if col not in cols:
                conn.execute(ddl)
        ocols = [r[1] for r in conn.execute("PRAGMA table_info(outcomes)").fetchall()]
        for col, ddl in (
            ("mfe_pct", "ALTER TABLE outcomes ADD COLUMN mfe_pct REAL"),
            ("mae_pct", "ALTER TABLE outcomes ADD COLUMN mae_pct REAL"),
            ("first_touch", "ALTER TABLE outcomes ADD COLUMN first_touch TEXT"),
        ):
            if col not in ocols:
                conn.execute(ddl)
        scols = [r[1] for r in conn.execute("PRAGMA table_info(signals)").fetchall()]
        for col, ddl in (
            ("setup", "ALTER TABLE signals ADD COLUMN setup TEXT"),
            ("regime", "ALTER TABLE signals ADD COLUMN regime TEXT"),
            ("mtf_alignment", "ALTER TABLE signals ADD COLUMN mtf_alignment INTEGER"),
            ("plan_id", "ALTER TABLE signals ADD COLUMN plan_id INTEGER"),
        ):
            if col not in scols:
                conn.execute(ddl)
        bcols = [r[1] for r in conn.execute("PRAGMA table_info(outbox)").fetchall()]
        for col, ddl in (
            ("last_error", "ALTER TABLE outbox ADD COLUMN last_error TEXT"),
            ("next_attempt_at", "ALTER TABLE outbox ADD COLUMN next_attempt_at INTEGER DEFAULT 0"),
            ("urgent", "ALTER TABLE outbox ADD COLUMN urgent INTEGER DEFAULT 0"),
        ):
            if col not in bcols:
                conn.execute(ddl)
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_signals_plan "
                     "ON signals(plan_id) WHERE plan_id IS NOT NULL")
        conn.commit()
    finally:
        conn.close()


def _now() -> int:
    return int(time.time() * 1000)


def recent_alert_exists(path: str, symbol: str, kind: str, direction: str | None, now: int) -> bool:
    conn = connect(path)
    try:
        row = conn.execute(
            "SELECT 1 FROM alerts a JOIN events e ON e.id = a.event_id "
            "WHERE e.symbol = ? AND e.kind = ? AND IFNULL(e.direction,'') = IFNULL(?,'') "
            "AND a.cooldown_until > ? LIMIT 1",
            (symbol, kind, direction, now),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def add_event(path: str, event: dict) -> int:
    conn = connect(path)
    try:
        cur = conn.execute(
            "INSERT INTO events (ts, symbol, kind, severity, direction, price, payload, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (event["ts"], event["symbol"], event["kind"], event["severity"],
             event.get("direction"), event.get("price"),
             json.dumps(event.get("payload", {}), ensure_ascii=False), _now()),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def add_alert(path: str, event_id: int, severity: str, text: str, cooldown_ms: int) -> int:
    now = _now()
    conn = connect(path)
    try:
        cur = conn.execute(
            "INSERT INTO alerts (event_id, severity, text, status, cooldown_until, created_at) "
            "VALUES (?,?,?,'pending',?,?)",
            (event_id, severity, text, now + cooldown_ms, now),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def pending_alerts(path: str, limit: int = 20) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE status = 'pending' "
            "AND (next_attempt_at IS NULL OR next_attempt_at <= ?) ORDER BY id ASC LIMIT ?",
            (_now(), limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_sent(path: str, alert_id: int) -> None:
    conn = connect(path)
    try:
        conn.execute("UPDATE alerts SET status='sent', sent_at=? WHERE id=?", (_now(), alert_id))
        conn.commit()
    finally:
        conn.close()


def fail_alert(path: str, alert_id: int, err: str, max_attempts: int = 5) -> dict:
    now = _now()
    conn = connect(path)
    try:
        row = conn.execute("SELECT attempts FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        attempts = ((row["attempts"] or 0) if row else 0) + 1
        status = "failed" if attempts >= max_attempts else "pending"
        next_at = now + min(2 ** attempts, 60) * 60_000
        conn.execute(
            "UPDATE alerts SET attempts = ?, last_error = ?, status = ?, next_attempt_at = ? WHERE id = ?",
            (attempts, err[:500], status, next_at, alert_id),
        )
        conn.commit()
        return {"attempts": attempts, "status": status, "next_attempt_at": next_at}
    finally:
        conn.close()


def add_signal(path: str, rec: dict) -> int:
    conn = connect(path)
    try:
        cur = conn.execute(
            "INSERT INTO signals (ts, symbol, direction, confidence, entry, stop, target, "
            "horizon_h, source, setup, regime, mtf_alignment) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (int(rec.get("ts") or _now()), rec.get("symbol"), rec.get("direction"),
             rec.get("confidence"), rec.get("entry"), rec.get("stop"),
             rec.get("target"), int(rec.get("horizon_h") or 4), rec.get("source"),
             rec.get("setup"), rec.get("regime"), rec.get("mtf_alignment")),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def add_outcome(path: str, signal_id: int, horizon: int, ts: int, price,
                ret_pct, hit, mfe=None, mae=None, first_touch=None) -> None:
    conn = connect(path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO outcomes "
            "(signal_id, horizon_h, ts, price, ret_pct, hit, mfe_pct, mae_pct, first_touch) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (signal_id, horizon, ts, price, ret_pct, hit, mfe, mae, first_touch),
        )
        conn.commit()
    finally:
        conn.close()


def mark_status(path: str, alert_id: int, status: str) -> None:
    conn = connect(path)
    try:
        conn.execute("UPDATE alerts SET status = ? WHERE id = ?", (status, alert_id))
        conn.commit()
    finally:
        conn.close()


def mark_stale(path: str, alert_id: int) -> None:
    conn = connect(path)
    try:
        conn.execute("UPDATE alerts SET status = 'stale', last_error = 'stale_alert' WHERE id = ?",
                     (alert_id,))
        conn.commit()
    finally:
        conn.close()


def last_signal_ts(path: str, symbol: str):
    conn = connect(path)
    try:
        row = conn.execute(
            "SELECT MAX(ts) FROM signals WHERE symbol = ?", (symbol,)
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else None
    finally:
        conn.close()


def count_alerts_since(path: str, since_ms: int) -> int:
    conn = connect(path)
    try:
        row = conn.execute("SELECT COUNT(*) AS n FROM alerts WHERE created_at >= ?", (since_ms,)).fetchone()
        return int(row["n"])
    finally:
        conn.close()


def record_run(path: str, kind: str, status: str, detail: str = "") -> None:
    conn = connect(path)
    try:
        conn.execute("INSERT INTO runs (ts, kind, status, detail) VALUES (?,?,?,?)",
                     (_now(), kind, status, detail))
        conn.commit()
    finally:
        conn.close()


def heartbeat(path: str, last_event_ts: int | None = None, queue_depth: int = 0, errors: int = 0) -> None:
    conn = connect(path)
    try:
        conn.execute(
            "INSERT INTO health (ts, heartbeat, last_event_ts, queue_depth, errors) VALUES (?,?,?,?,?)",
            (_now(), 1, last_event_ts, queue_depth, errors),
        )
        conn.commit()
    finally:
        conn.close()


def get_state(path: str, symbol: str) -> str | None:
    conn = connect(path)
    try:
        row = conn.execute("SELECT state FROM state WHERE symbol = ?", (symbol,)).fetchone()
        return None if row is None else row["state"]
    finally:
        conn.close()


def set_state(path: str, symbol: str, state: str) -> None:
    conn = connect(path)
    try:
        conn.execute(
            "INSERT INTO state (symbol, state, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(symbol) DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at",
            (symbol, state, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def status(path: str) -> dict:
    conn = connect(path)
    try:
        def one(sql, args=()):
            row = conn.execute(sql, args).fetchone()
            return None if row is None else dict(row)
        return {
            "events": one("SELECT COUNT(*) AS n FROM events")["n"],
            "alerts": one("SELECT COUNT(*) AS n FROM alerts")["n"],
            "pending": one("SELECT COUNT(*) AS n FROM alerts WHERE status='pending'")["n"],
            "signals": one("SELECT COUNT(*) AS n FROM signals")["n"],
            "last_health": one("SELECT * FROM health ORDER BY id DESC LIMIT 1"),
            "last_event": one("SELECT * FROM events ORDER BY id DESC LIMIT 1"),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# plan lifecycle persistence
# ---------------------------------------------------------------------------

ACTIVE_STATUSES = ("armed", "triggered", "confirmed", "managing")


def save_plan(path: str, plan: dict) -> dict:
    """Insert or update one plan; returns the stored plan with id."""
    import json as _json
    plan = dict(plan or {})
    now = _now()
    payload = _json.dumps(plan, ensure_ascii=False, default=str)
    conn = connect(path)
    try:
        pid = plan.get("id")
        if pid:
            conn.execute(
                "UPDATE plans SET status=?, trigger=?, stop=?, target1=?, target2=?, "
                "ttl_at=?, updated_at=?, confirmed_at=?, closed_at=?, outcome=?, "
                "pnl_pct=?, data=? WHERE id=?",
                (plan.get("status"), plan.get("trigger"), plan.get("stop"),
                 plan.get("target1"), plan.get("target2"), plan.get("ttl_at"),
                 now, plan.get("confirmed_at"), plan.get("closed_at"),
                 plan.get("outcome"), plan.get("pnl_pct"), payload, pid))
        else:
            cur = conn.execute(
                "INSERT INTO plans(symbol,interval,side,setup,status,trigger,stop,"
                "target1,target2,ttl_at,created_at,updated_at,confirmed_at,"
                "closed_at,outcome,pnl_pct,data) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (plan.get("symbol"), plan.get("interval"), plan.get("side"),
                 plan.get("setup"), plan.get("status"), plan.get("trigger"),
                 plan.get("stop"), plan.get("target1"), plan.get("target2"),
                 plan.get("ttl_at"), plan.get("created_at") or now, now,
                 plan.get("confirmed_at"), plan.get("closed_at"),
                 plan.get("outcome"), plan.get("pnl_pct"), payload))
            pid = cur.lastrowid
        conn.commit()
        plan["id"] = pid
        return plan
    finally:
        conn.close()


def _plan_row(row) -> dict:
    import json as _json
    d = dict(row)
    try:
        data = _json.loads(d.pop("data") or "{}")
    except Exception:
        data = {}
    data.update({k: v for k, v in d.items() if v is not None})
    return data


def get_plan(path: str, plan_id: int):
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM plans WHERE id=?", (plan_id,)).fetchone()
        return _plan_row(row) if row else None
    finally:
        conn.close()


def active_plan(path: str, symbol: str, interval: str | None = None):
    conn = connect(path)
    try:
        if interval:
            row = conn.execute(
                "SELECT * FROM plans WHERE symbol=? AND interval=? AND status IN "
                "('armed','triggered','confirmed','managing') ORDER BY id DESC LIMIT 1",
                (symbol, interval)).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM plans WHERE symbol=? AND status IN "
                "('armed','triggered','confirmed','managing') ORDER BY id DESC LIMIT 1",
                (symbol,)).fetchone()
        return _plan_row(row) if row else None
    finally:
        conn.close()


def open_plans(path: str, symbol: str | None = None):
    conn = connect(path)
    try:
        sql = ("SELECT * FROM plans WHERE status IN "
               "('armed','triggered','confirmed','managing')")
        args = ()
        if symbol:
            sql += " AND symbol=?"
            args = (symbol,)
        sql += " ORDER BY id DESC"
        return [_plan_row(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def list_plans(path: str, symbol: str | None = None, limit: int = 40):
    conn = connect(path)
    try:
        sql = "SELECT * FROM plans"
        args = []
        if symbol:
            sql += " WHERE symbol=?"
            args.append(symbol)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        return [_plan_row(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def add_plan_event(path: str, plan: dict, event: dict, key: str):
    """Append one transition; returns event id or None when idempotent-skipped."""
    import json as _json
    conn = connect(path)
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO plan_events(plan_id,symbol,type,price,ts,payload,"
            "idempotency_key,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (plan.get("id"), plan.get("symbol"), event.get("type"),
             event.get("price"), event.get("ts"), _json.dumps(event, ensure_ascii=False),
             key, _now()))
        conn.commit()
        return cur.lastrowid if cur.rowcount else None
    finally:
        conn.close()


def plan_events(path: str, plan_id: int | None = None, limit: int = 60):
    import json as _json
    conn = connect(path)
    try:
        if plan_id:
            rows = conn.execute(
                "SELECT * FROM plan_events WHERE plan_id=? ORDER BY id DESC LIMIT ?",
                (plan_id, limit)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM plan_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["event"] = _json.loads(d.pop("payload") or "{}")
            except Exception:
                d["event"] = {}
            out.append(d)
        return out
    finally:
        conn.close()


def plan_stats(path: str, symbol: str | None = None) -> dict:
    conn = connect(path)
    try:
        where, args = "", ()
        if symbol:
            where, args = " WHERE symbol=?", (symbol,)
        total = conn.execute("SELECT COUNT(*) c FROM plans" + where, args).fetchone()["c"]
        closed = conn.execute(
            "SELECT COUNT(*) c FROM plans" + where +
            (" AND" if where else " WHERE") + " closed_at IS NOT NULL", args).fetchone()["c"]
        rows = conn.execute(
            "SELECT outcome, COUNT(*) c, AVG(pnl_pct) p FROM plans" + where +
            " GROUP BY outcome", args).fetchall()
        by_out = {r["outcome"] or "open": {"n": r["c"],
                                           "avg_pnl": round(r["p"], 3) if r["p"] is not None else None}
                  for r in rows}
        return {"total": total, "closed": closed, "by_outcome": by_out}
    finally:
        conn.close()


def outbox_add(path: str, plan_event_id: int, channel: str, text: str,
               dedupe_min: int = 0, urgent: int = 0):
    """Insert a pending message; optionally suppress identical text recently sent.

    plan_event_id uniqueness prevents replay of the *same* event. Content
    dedupe is the second guard: plan churn can create a new plan id with the
    exact same invalidation text every few minutes.
    """
    conn = connect(path)
    try:
        if dedupe_min and dedupe_min > 0:
            since = _now() - int(dedupe_min) * 60_000
            row = conn.execute(
                "SELECT id FROM outbox WHERE channel=? AND text=? AND created_at>=? "
                "AND status IN ('pending','sent') LIMIT 1",
                (channel, text, since)).fetchone()
            if row:
                return None
        cur = conn.execute(
            "INSERT OR IGNORE INTO outbox(plan_event_id,channel,text,status,attempts,"
            "created_at,urgent) VALUES(?,?,?,'pending',0,?,?)",
            (plan_event_id, channel, text, _now(), int(bool(urgent))))
        conn.commit()
        return cur.lastrowid if cur.rowcount else None
    finally:
        conn.close()


def recent_void_plan(path: str, symbol: str, side: str | None, since_ms: int):
    """Latest voided plan inside the re-arm cooldown.

    Pass side=None for symbol-level cooling. Side-scoped lookups allowed a
    direction flip (long void -> short candidate) to bypass the cooldown.
    """
    conn = connect(path)
    try:
        sql = ("SELECT id,setup,updated_at,outcome FROM plans WHERE symbol=? "
               "AND status='void' AND updated_at>=? ")
        args = [symbol, since_ms]
        if side is not None:
            sql += "AND side=? "
            args.append(side)
        row = conn.execute(sql + "ORDER BY id DESC LIMIT 1", args).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def outbox_pending(path: str, limit: int = 20):
    conn = connect(path)
    try:
        # Order by retry time so a skipped head-of-line row cannot starve the
        # rest of the queue for its whole 30min lifetime.
        return [dict(r) for r in conn.execute(
            "SELECT * FROM outbox WHERE status='pending' "
            "AND (next_attempt_at IS NULL OR next_attempt_at<=?) "
            "ORDER BY COALESCE(NULLIF(next_attempt_at,0), created_at), id LIMIT ?",
            (_now(), limit)).fetchall()]
    finally:
        conn.close()


def outbox_mark(path: str, oid: int, status: str, err: str = "",
                next_attempt_at: int | None = None):
    conn = connect(path)
    try:
        conn.execute(
            "UPDATE outbox SET status=?, attempts=attempts+1, sent_at=?, "
            "last_error=?, next_attempt_at=? WHERE id=?",
            (status, _now() if status == "sent" else None, str(err or "")[:300],
             int(next_attempt_at or 0), oid))
        conn.commit()
    finally:
        conn.close()


def record_plan_signal(path: str, plan: dict) -> int | None:
    """Bridge the plan ledger into the signals/outcomes scoring chain.

    Before 2.2.0 plans and signals lived in two different SQLite files, so
    the weekly review/calibration had zero samples from the actual plans.
    Idempotent via the partial unique index on signals(plan_id).
    """
    pid = plan.get("id")
    if not pid or plan.get("status") not in ("closed", "void"):
        return None
    snap = plan.get("snapshot") or {}
    conn = connect(path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO signals "
            "(ts,symbol,direction,confidence,entry,stop,target,horizon_h,source,"
            " setup,regime,mtf_alignment,plan_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (int(plan.get("created_at") or _now()), plan.get("symbol"),
             plan.get("side"), int(float(plan.get("confidence") or 50)),
             plan.get("trigger"), plan.get("stop"), plan.get("target1"), 4,
             "plan", plan.get("setup"),
             ((snap.get("structure") or {}).get("state")),
             ((snap.get("mtf") or {}).get("alignment")), pid))
        conn.commit()
        row = conn.execute("SELECT id FROM signals WHERE plan_id=?", (pid,)).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def add_market_event(path: str, symbol: str, kind: str, old_value: str,
                     new_value: str, ts: int, detail: str = "") -> int | None:
    """Append a market state transition (trend / structure / regime / MTF)."""
    conn = connect(path)
    try:
        cur = conn.execute(
            "INSERT INTO market_events (ts,symbol,kind,old_value,new_value,detail,"
            "created_at) VALUES (?,?,?,?,?,?,?)",
            (int(ts), symbol, kind, str(old_value)[:400], str(new_value)[:400],
             str(detail)[:500], _now()))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def recent_market_event(path: str, symbol: str, kind: str, old_value: str,
                        new_value: str, since_ms: int) -> bool:
    conn = connect(path)
    try:
        return conn.execute(
            "SELECT 1 FROM market_events WHERE symbol=? AND kind=? AND "
            "old_value=? AND new_value=? AND created_at>=? LIMIT 1",
            (symbol, kind, str(old_value)[:400], str(new_value)[:400],
             since_ms)).fetchone() is not None
    finally:
        conn.close()


def latest_market_state(path: str, symbol: str) -> str | None:
    """Last recorded state signature, so a restart does not re-notify."""
    conn = connect(path)
    try:
        row = conn.execute(
            "SELECT new_value FROM market_events WHERE symbol=? ORDER BY id DESC "
            "LIMIT 1", (symbol,)).fetchone()
        return row["new_value"] if row else None
    finally:
        conn.close()
