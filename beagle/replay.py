"""Historical replay for event calibration (read-only, no pushes)."""
from __future__ import annotations

import bisect
import time

from nakedk.features import features_from_klines
from nakedk.fetch import get_json

from .detect import detect_events

STEP = {"1m": 60_000, "5m": 300_000, "4h": 4 * 3600_000}


def fetch(symbol: str, interval: str, start_ms: int, end_ms: int):
    out, cur = [], start_ms
    step = STEP[interval]
    while cur < end_ms:
        rows = get_json(
            f"/api/v3/klines?symbol={symbol}&interval={interval}"
            f"&startTime={cur}&endTime={end_ms}&limit=1000"
        )
        if not rows:
            break
        out.extend(rows)
        cur = rows[-1][0] + step
        if len(rows) < 1000:
            break
    return out


def replay(symbol: str, days: float = 1.0, cfg: dict | None = None) -> list[dict]:
    cfg = cfg or {}
    end = int(time.time() * 1000)
    start = end - int(days * 86_400_000)
    m1 = fetch(symbol, "1m", start, end)
    h4 = fetch(symbol, "4h", start - 20 * 86_400_000, end)

    timeline = []
    for i in range(60, len(h4)):
        try:
            timeline.append((h4[i][0], features_from_klines(h4[: i + 1][-200:])))
        except Exception:
            timeline.append((h4[i][0], None))
    opens = [t for t, _ in timeline]

    events = []
    for i in range(60, len(m1)):
        ts = m1[i][0]
        k = bisect.bisect_right(opens, ts - 4 * 3600_000) - 1
        if k < 0 or timeline[k][1] is None:
            continue
        f = timeline[k][1]
        window = m1[max(0, i - 20): i + 1]
        vols = [float(r[5]) for r in window]
        vol_z = 0.0
        if len(vols) > 2:
            base = vols[:-1]
            mu = sum(base) / len(base)
            sd = (sum((v - mu) ** 2 for v in base) / len(base)) ** 0.5 or 1.0
            vol_z = (vols[-1] - mu) / sd
        evs = detect_events(
            symbol, f, float(m1[i][4]), float(m1[i - 1][4]), vol_z, None, None, cfg
        )
        for e in evs:
            e["ts"] = ts
        events.extend(evs)
    return events


def summarise(events: list[dict], cooldown_min: dict | None = None) -> dict:
    cooldown_min = cooldown_min or {"P0": 60, "P1": 120, "P2": 360}
    by_kind, by_sev = {}, {}
    kept = []
    last = {}
    for e in sorted(events, key=lambda x: x["ts"]):
        key = (e["symbol"], e["kind"], e.get("direction"))
        cd = cooldown_min.get(e["severity"], 120) * 60_000
        if key in last and e["ts"] - last[key] < cd:
            continue
        last[key] = e["ts"]
        kept.append(e)
        by_kind[e["kind"]] = by_kind.get(e["kind"], 0) + 1
        by_sev[e["severity"]] = by_sev.get(e["severity"], 0) + 1
    return {
        "raw_events": len(events),
        "after_cooldown": len(kept),
        "by_kind": by_kind,
        "by_severity": by_sev,
        "sample": kept[:5],
    }
