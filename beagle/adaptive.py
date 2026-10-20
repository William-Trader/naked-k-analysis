"""Bounded, audited self-adjustment of per-setup confidence multipliers.

Guardrails: deterministic, minimum sample, max step per review, hard
bounds, and quarantine after consecutive degrading reviews.
"""
from __future__ import annotations

import json
import os
import time

MIN_N = 30
MAX_STEP = 0.08
LO = 0.70
HI = 1.30
QUARANTINE_STREAK = 2


def load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {"version": 1, "updated_at": 0, "multipliers": {}, "streaks": {}, "log": []}


def save(path: str, table: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(table, fh, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)


def multiplier(table: dict, setup: str) -> float:
    return float((table or {}).get("multipliers", {}).get(setup, 1.0))


def _clamp(x, lo=LO, hi=HI):
    return max(lo, min(hi, x))


def update(table: dict, by_setup: dict, base_rate: float,
           min_n: int = MIN_N, max_step: float = MAX_STEP, now=None) -> dict:
    now = int(now if now is not None else time.time() * 1000)
    mults = table.setdefault("multipliers", {})
    streaks = table.setdefault("streaks", {})
    log = table.setdefault("log", [])
    for setup, st in by_setup.items():
        n = st.get("n", 0)
        old = float(mults.get(setup, 1.0))
        if n < min_n or st.get("hit_rate") is None:
            continue
        hit = st["hit_rate"] / 100.0
        edge = hit - base_rate
        target = _clamp(1.0 + 1.8 * edge)
        new = round(old + max(-max_step, min(max_step, target - old)), 4)
        streaks[setup] = streaks.get(setup, 0) + 1 if edge < -0.10 else 0
        reason = "edge"
        if streaks.get(setup, 0) >= QUARANTINE_STREAK:
            new = LO
            reason = "quarantine"
        new = round(_clamp(new), 4)
        mults[setup] = new
        if new != old:
            log.append({"ts": now, "setup": setup, "n": n,
                        "hit_rate": st["hit_rate"], "edge": round(edge, 3),
                        "old": old, "new": new, "reason": reason})
    table["updated_at"] = now
    table["version"] = int(table.get("version", 1)) + 1
    return table

