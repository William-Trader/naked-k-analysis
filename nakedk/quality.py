"""Data quality gates: refuse to analyse on broken data."""
from __future__ import annotations


def gates(ks, interval_ms: int, now_ms: int, source_prices=None) -> dict:
    issues = []
    if not ks:
        return {"ok": False, "issues": ["empty"]}
    gaps = 0
    for a, b in zip(ks, ks[1:]):
        if int(b[0]) - int(a[0]) > 1.5 * interval_ms:
            gaps += 1
    if gaps:
        issues.append(f"gap={gaps}")
    age = now_ms - int(ks[-1][0])
    if age > 1.5 * interval_ms:
        issues.append(f"stale={round(age / interval_ms, 1)}x")
    if source_prices:
        vals = [float(v) for v in source_prices if v]
        if len(vals) > 1:
            mid = sum(vals) / len(vals)
            if mid and (max(vals) - min(vals)) / mid > 0.003:
                issues.append("source_diff")
    return {"ok": not issues, "issues": issues}
