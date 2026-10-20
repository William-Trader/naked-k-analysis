"""Outcome scoring for stored signals (4h default)."""
from __future__ import annotations

from nakedk.score import klines_1h

from .store import connect


def _index_at(ks, ts: int):
    for i, k in enumerate(ks):
        if k[0] <= ts < k[0] + 3600_000:
            return i
    return None


def score_pending(db_path: str) -> int:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT s.* FROM signals s LEFT JOIN outcomes o "
            "ON o.signal_id = s.id AND o.horizon_h = s.horizon_h "
            "WHERE o.signal_id IS NULL"
        ).fetchall()
        scored = 0
        for r in rows:
            ts = int(r["ts"])
            horizon = int(r["horizon_h"] or 4)
            try:
                ks = klines_1h(r["symbol"], ts - 2 * 3600_000,
                               ts + (horizon + 2) * 3600_000)
            except Exception:
                continue
            i = _index_at(ks, ts)
            if i is None or i + horizon >= len(ks):
                continue
            entry = float(ks[i][4])
            exit_ = float(ks[i + horizon][4])
            ret = (exit_ / entry - 1.0) * 100.0
            hit = None
            if r["direction"] == "long":
                hit = 1 if ret > 0 else 0
            elif r["direction"] == "short":
                hit = 1 if ret < 0 else 0
            conn.execute(
                "INSERT OR REPLACE INTO outcomes (signal_id, horizon_h, ts, price, ret_pct, hit) "
                "VALUES (?,?,?,?,?,?)",
                (r["id"], horizon, ts, exit_, ret, hit),
            )
            scored += 1
        conn.commit()
        return scored
    finally:
        conn.close()


def summary(db_path: str) -> dict:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT s.direction, s.confidence, o.ret_pct, o.hit FROM outcomes o "
            "JOIN signals s ON s.id = o.signal_id"
        ).fetchall()
        directional = [r for r in rows if r["direction"] in ("long", "short")]
        hits = [r for r in directional if r["hit"]]
        by_dir = {}
        for d in ("long", "short"):
            sub = [r for r in directional if r["direction"] == d]
            by_dir[d] = {
                "n": len(sub),
                "hit_rate": round(100 * sum(1 for r in sub if r["hit"]) / len(sub), 1) if sub else None,
                "avg_ret": round(sum(r["ret_pct"] for r in sub) / len(sub), 3) if sub else None,
            }
        buckets = {}
        for lo in (50, 55, 60, 65):
            sub = [r for r in directional if (r["confidence"] or 0) // 5 * 5 == lo]
            if sub:
                buckets[f"{lo}-{lo + 4}"] = {
                    "n": len(sub),
                    "hit_rate": round(100 * sum(1 for r in sub if r["hit"]) / len(sub), 1),
                }
        return {
            "n": len(rows),
            "directional": len(directional),
            "hit_rate": round(100 * len(hits) / len(directional), 1) if directional else None,
            "by_direction": by_dir,
            "calibration": buckets,
        }
    finally:
        conn.close()
