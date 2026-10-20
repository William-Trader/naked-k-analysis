"""Pattern lifecycle tracking in SQLite.

Status: forming -> confirmed -> target_hit / invalidated.
A pattern is matched to an existing row by symbol/type/direction and a
price within 0.5%.
"""
from __future__ import annotations

import os
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS pattern_state (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  type TEXT NOT NULL,
  direction TEXT NOT NULL,
  price REAL NOT NULL,
  first_seen INTEGER NOT NULL,
  last_seen INTEGER NOT NULL,
  status TEXT NOT NULL,
  quality INTEGER,
  score REAL,
  context TEXT,
  neckline REAL,
  target REAL,
  stop REAL,
  last_price REAL,
  note TEXT
);
CREATE INDEX IF NOT EXISTS idx_ps_symbol ON pattern_state(symbol, last_seen);
"""


def _conn(db):
    c = sqlite3.connect(db, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def init(db):
    if not db:
        return
    c = _conn(db)
    try:
        c.executescript(SCHEMA)
        c.commit()
    finally:
        c.close()


def _status(p, last_price):
    if not last_price:
        return "forming"
    target = p.get("target")
    stop = p.get("stop")
    neck = p.get("neckline")
    bull = p["direction"] == "bullish"
    bear = p["direction"] == "bearish"
    if bull:
        if target and last_price >= target:
            return "target_hit"
        if stop and last_price <= stop:
            return "invalidated"
        if neck and last_price >= neck:
            return "confirmed"
    if bear:
        if target and last_price <= target:
            return "target_hit"
        if stop and last_price >= stop:
            return "invalidated"
        if neck and last_price <= neck:
            return "confirmed"
    return "forming"


def track(symbol, patterns, db, last_price=None, now=None):
    if not db:
        return
    now = now or int(time.time() * 1000)
    init(db)
    c = _conn(db)
    try:
        for p in patterns:
            price = float(p["price"])
            status = _status(p, last_price)
            row = c.execute(
                "SELECT id, status FROM pattern_state WHERE symbol=? AND type=? AND direction=? "
                "AND ABS(price-?)/? < 0.005 ORDER BY id DESC LIMIT 1",
                (symbol, p["type"], p["direction"], price, price or 1),
            ).fetchone()
            if row:
                old = row["status"]
                if old in ("target_hit", "invalidated") and status == "forming":
                    status = old
                c.execute(
                    "UPDATE pattern_state SET last_seen=?, status=?, quality=?, score=?, context=?, "
                    "neckline=?, target=?, stop=?, last_price=?, note=? WHERE id=?",
                    (now, status, p.get("quality"), p.get("score"), p.get("context"),
                     p.get("neckline"), p.get("target"), p.get("stop"),
                     last_price, p.get("note", ""), row["id"]),
                )
            else:
                c.execute(
                    "INSERT INTO pattern_state (symbol,type,direction,price,first_seen,last_seen,"
                    "status,quality,score,context,neckline,target,stop,last_price,note) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (symbol, p["type"], p["direction"], price, now, now, status,
                     p.get("quality"), p.get("score"), p.get("context"),
                     p.get("neckline"), p.get("target"), p.get("stop"),
                     last_price, p.get("note", "")),
                )
        c.commit()
    finally:
        c.close()


def states(symbol, db, limit=12):
    if not db:
        return []
    init(db)
    c = _conn(db)
    try:
        rows = c.execute(
            "SELECT * FROM pattern_state WHERE symbol=? ORDER BY last_seen DESC LIMIT ?",
            (symbol, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()
