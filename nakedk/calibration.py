"""Confidence calibration from realised signal outcomes.

The stance engine emits a prior confidence. This module measures what
actually happened for each confidence bucket and shrinks the estimate
toward the base rate so small samples cannot inflate confidence.
"""
from __future__ import annotations

import os
import sqlite3
import time

BUCKETS = ((0, 45), (45, 55), (55, 60), (60, 65), (65, 70), (70, 101))
PRIOR = 0.5
PRIOR_N = 20
MIN_N = 20
CONF_CAP = (35, 65)
_CACHE: dict = {}


def bucket_key(conf: int) -> str:
    c = int(conf)
    for lo, hi in BUCKETS:
        if lo <= c < hi:
            return f"{lo}-{hi - 1}" if hi <= 100 else f"{lo}+"
    return "0-44"


def load_samples(db_path: str) -> list:
    """Return [(confidence, hit)] from scored, non-neutral signals."""
    if not db_path or not os.path.exists(db_path):
        return []
    uri = "file:" + os.path.abspath(db_path) + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error:
        return []
    try:
        rows = conn.execute(
            "SELECT s.confidence, o.hit FROM signals s "
            "JOIN outcomes o ON o.signal_id = s.id "
            "WHERE o.hit IS NOT NULL AND s.direction != 'neutral'"
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    out = []
    for c, h in rows:
        if h is None:
            continue
        out.append((int(c if c is not None else 50), int(h)))
    return out


def fit(samples, prior: float = PRIOR, strength: int = PRIOR_N) -> dict:
    """Shrink each bucket hit rate toward the sample base rate."""
    total = len(samples)
    hits = sum(h for _, h in samples)
    base = (hits + prior * strength) / (total + strength) if total else prior
    buckets = {}
    for lo, hi in BUCKETS:
        key = bucket_key(lo)
        sub = [h for c, h in samples if lo <= c < hi]
        n = len(sub)
        sh = sum(sub)
        p = (sh + base * strength) / (n + strength)
        buckets[key] = {
            "n": n,
            "hit_rate": round(100.0 * sh / n, 1) if n else None,
            "p": round(p, 4),
        }
    return {
        "n": total,
        "hits": hits,
        "base_rate": round(100.0 * base, 1),
        "buckets": buckets,
        "prior_strength": strength,
        "fitted_at": int(time.time() * 1000),
    }


def table_from_db(db_path: str, ttl_ms: int = 300_000) -> dict:
    """Fit and cache the calibration table for a database path."""
    now = int(time.time() * 1000)
    hit = _CACHE.get(db_path)
    if hit and now - hit['fitted_at'] < ttl_ms:
        return hit
    table = fit(load_samples(db_path))
    table["db"] = db_path
    _CACHE[db_path] = table
    return table


def calibrate(conf, table, min_n: int = MIN_N, cap=CONF_CAP) -> tuple:
    """Return (calibrated_conf, bucket_meta). Small samples keep the prior."""
    raw = int(round(float(conf if conf is not None else 50)))
    key = bucket_key(raw)
    b = (table or {}).get("buckets", {}).get(key, {})
    n = b.get("n", 0)
    if n < min_n:
        return raw, {"bucket": key, "n": n, "applied": False,
                     "p": b.get("p"), "hit_rate": b.get("hit_rate")}
    lo, hi = cap
    adjusted = int(round(100.0 * float(b["p"])))
    return max(lo, min(hi, adjusted)), {"bucket": key, "n": n, "applied": True,
                                        "p": b.get("p"), "hit_rate": b.get("hit_rate")}

