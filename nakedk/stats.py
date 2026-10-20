"""Outcome statistics: Wilson intervals, sample gating, bucketed expectancy."""
from __future__ import annotations

import math

MIN_N = 30


def wilson(hits: int, n: int, z: float = 1.96):
    if n <= 0:
        return (0.0, 0.0)
    p = hits / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(max(0.0, center - half) * 100, 1),
            round(min(1.0, center + half) * 100, 1))


def eff_n(n: int, rho: float = 0.5) -> float:
    """Overlapping horizons inflate n; shrink it conservatively."""
    return max(1.0, n / (1.0 + 2.0 * rho))


def binom_p(hits: int, n: int) -> float:
    """Two-sided p-value vs a 50% coin, normal approximation."""
    if n <= 0:
        return 1.0
    z = abs(hits / n - 0.5) / math.sqrt(0.25 / n)
    return 2.0 * (1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2.0))))


def bh_significant(pvals, alpha: float = 0.1) -> list:
    """Benjamini-Hochberg: which setups survive multiple testing."""
    m = len(pvals)
    if not m:
        return []
    ordered = sorted(pvals, key=lambda x: x[1])
    passed = []
    for i, (key, p) in enumerate(ordered, start=1):
        if p <= i * alpha / m:
            passed.append(key)
    return passed


def summarize(rows) -> dict:
    n = len(rows)
    if not n:
        return {"n": 0, "hit_rate": None, "wilson": [None, None],
                "expectancy": None, "mfe": None, "mae": None,
                "reliable": False}
    hits = sum(1 for r in rows if r.get("hit"))
    rets = [float(r["ret_pct"]) for r in rows if r.get("ret_pct") is not None]
    mfes = [float(r["mfe_pct"]) for r in rows if r.get("mfe_pct") is not None]
    maes = [float(r["mae_pct"]) for r in rows if r.get("mae_pct") is not None]
    return {
        "n": n,
        "n_eff": round(eff_n(n), 1),
        "hit_rate": round(100 * hits / n, 1),
        "wilson": list(wilson(hits, n)),
        "expectancy": round(sum(rets) / len(rets), 3) if rets else None,
        "mfe": round(sum(mfes) / len(mfes), 2) if mfes else None,
        "mae": round(sum(maes) / len(maes), 2) if maes else None,
        "reliable": eff_n(n) >= MIN_N,
    }


def bucket(rows, keyfn) -> dict:
    groups = {}
    for r in rows:
        key = keyfn(r) or "unknown"
        groups.setdefault(str(key), []).append(r)
    return {k: summarize(v) for k, v in sorted(groups.items())}

