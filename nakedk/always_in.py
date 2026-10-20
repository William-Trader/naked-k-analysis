"""Always-In state machine with hysteresis, persisted in SQLite."""
from __future__ import annotations

import sqlite3
import time

BAR_MS = 14_400_000


def init(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ai_state ("
            "symbol TEXT PRIMARY KEY, state TEXT, since_ts INTEGER, reason TEXT)"
        )
        conn.commit()
    finally:
        conn.close()


def load(path: str, symbol: str):
    conn = sqlite3.connect(path)
    try:
        row = conn.execute(
            "SELECT state, since_ts, reason FROM ai_state WHERE symbol = ?", (symbol,)
        ).fetchone()
        return row
    finally:
        conn.close()


def save(path: str, symbol: str, state: str, since_ts: int, reason: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT INTO ai_state (symbol, state, since_ts, reason) VALUES (?,?,?,?) "
            "ON CONFLICT(symbol) DO UPDATE SET state=excluded.state, "
            "since_ts=excluded.since_ts, reason=excluded.reason",
            (symbol, state, since_ts, reason),
        )
        conn.commit()
    finally:
        conn.close()


def next_state(prev, bos_kind, follow_ok, close, ema20, bars_since, min_hold=3):
    if prev != "neutral" and bars_since < min_hold:
        return prev, "hold_min"
    if bos_kind == "bullish" and follow_ok and ema20 and close > ema20:
        return "long", "bos_up"
    if bos_kind == "bearish" and follow_ok and ema20 and close < ema20:
        return "short", "bos_down"
    return prev, "hold"


def update(path, symbol, bos_kind, follow_ok, close, ema20, bar_ts, min_hold=3):
    init(path)
    row = load(path, symbol)
    prev = row[0] if row else "neutral"
    since = int(row[1]) if row and row[1] else bar_ts
    bars_since = max(0, (int(bar_ts) - since) // BAR_MS)
    new, reason = next_state(prev, bos_kind, follow_ok, close, ema20,
                             bars_since, min_hold)
    if new != prev:
        since = int(bar_ts)
        save(path, symbol, new, since, reason)
    return {"state": new, "prev": prev, "since_ts": since,
            "bars_since": bars_since, "reason": reason, "changed": new != prev}
