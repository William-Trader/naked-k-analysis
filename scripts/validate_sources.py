"""Monte Carlo validation of the multi-source weighting scheme."""
from __future__ import annotations

import random
import statistics

from nakedk.sources import combine

SHARES = [0.45, 0.22, 0.12, 0.12, 0.09]
NOISE = 0.0003
TRIALS = 2000


def build(truth, outlier=False, outlier_pct=0.03, outlier_idx=2):
    rows = []
    for i, share in enumerate(SHARES):
        price = truth * (1.0 + random.gauss(0.0, NOISE))
        if outlier and i == outlier_idx:
            price *= 1.0 + outlier_pct
        rows.append({"source": f"s{i}", "price": price,
                     "quote_vol": share * 1_000_000})
    return rows


def run(label, outlier=False, outlier_pct=0.03):
    naive_err, weighted_err, devs, confs = [], [], [], []
    for _ in range(TRIALS):
        truth = 100.0
        rows = build(truth, outlier, outlier_pct)
        naive = sum(r["price"] for r in rows) / len(rows)
        out = combine(rows)
        naive_err.append(abs(naive - truth) / truth * 1e4)
        weighted_err.append(abs(out["weighted"] - truth) / truth * 1e4)
        devs.append(out["max_dev_pct"])
        confs.append(out["confidence"])
    print(f"{label}:")
    print(f"  naive    MAE {statistics.mean(naive_err):6.2f} bps  max {max(naive_err):6.2f}")
    print(f"  weighted MAE {statistics.mean(weighted_err):6.2f} bps  max {max(weighted_err):6.2f}")
    print(f"  dev mean {statistics.mean(devs):.3f}%  conf {dict((c, confs.count(c)) for c in set(confs))}")


if __name__ == "__main__":
    random.seed(20261027)
    run("clean (no outliers)")
    run("one source +3% (12% liquidity)", outlier=True, outlier_pct=0.03)
    run("one source +1% (12% liquidity)", outlier=True, outlier_pct=0.01)
