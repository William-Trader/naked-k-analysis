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

CREATE TABLE IF NOT EXISTS state (
  symbol TEXT PRIMARY KEY,
  state TEXT,
  updated_at INTEGER
);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def init(path: str) -> None:
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
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
            "SELECT * FROM alerts WHERE status = 'pending' ORDER BY id ASC LIMIT ?", (limit,)
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
