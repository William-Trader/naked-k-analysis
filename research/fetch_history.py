# -----------------------------------------------------------------
# research/fetch_history.py - naked-k-analysis reproducible research data
# (c) 2026 William-Trader (https://github.com/William-Trader)
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# -----------------------------------------------------------------
"""Fetch and freeze OHLCV history so every backtest is byte-for-byte reproducible.

Data source: Binance public market-data mirror (no API key required).
Only the first six kline fields are kept: [open_ms, open, high, low, close, vol].

Usage:
    PYTHONPATH=. python3 research/fetch_history.py            # fetch if missing
    PYTHONPATH=. python3 research/fetch_history.py --force    # refresh snapshot

The snapshot is committed as gzip-compressed JSON. Research scripts MUST read
the frozen snapshot, never the live API, so a result can be re-run months later
and produce identical numbers. `manifest.json` records sha256 of each payload.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "research", "data")
BASE = os.environ.get("NK_MARKET_BASE", "https://data-api.binance.vision")
SYMBOLS = ("BTCUSDT", "ETHUSDT")
INTERVALS = ("4h", "1h")
DAYS = 730
BAR_MS = {"4h": 4 * 3600_000, "1h": 3600_000}
UA = {"User-Agent": "naked-k-analysis/research (reproducible backtest)"}


def _get(url: str, timeout: int = 20, retries: int = 3):
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # network / rate limit / transient 5xx
            last = e
            if i < retries:
                time.sleep(1.5 * (2 ** i))
    raise last


def fetch(symbol: str, interval: str, days: int = DAYS):
    end = int(time.time() * 1000)
    start = end - days * 86_400_000
    step = BAR_MS[interval]
    out, cursor, seen = [], start, set()
    while cursor < end:
        rows = _get(
            f"{BASE}/api/v3/klines?symbol={symbol}&interval={interval}"
            f"&startTime={cursor}&limit=1000"
        )
        if not rows:
            break
        fresh = 0
        for r in rows:
            t = int(r[0])
            if t in seen:
                continue
            seen.add(t)
            # keep only closed bars; never let a forming bar into research data
            if t + step > end:
                continue
            out.append([t, float(r[1]), float(r[2]), float(r[3]),
                        float(r[4]), float(r[5])])
            fresh += 1
        nxt = int(rows[-1][0]) + step
        if nxt <= cursor or fresh == 0 or len(rows) < 1000:
            break
        cursor = nxt
        if len(out) > days * (86_400_000 // step) + 10:  # hard loop guard
            break
    out.sort(key=lambda x: x[0])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--days", type=int, default=DAYS)
    args = ap.parse_args()
    os.makedirs(DATA_DIR, exist_ok=True)
    manifest = {"base": BASE, "days": args.days,
                "generated_at": int(time.time() * 1000), "files": {}}
    for sym in SYMBOLS:
        for iv in INTERVALS:
            path = os.path.join(DATA_DIR, f"{sym}_{iv}.json.gz")
            if os.path.exists(path) and not args.force:
                raw = open(path, "rb").read()
                print(f"cached {sym} {iv}: {len(raw)} bytes")
            else:
                rows = fetch(sym, iv, args.days)
                payload = json.dumps({"symbol": sym, "interval": iv,
                                      "columns": ["t", "o", "h", "l", "c", "v"],
                                      "rows": rows}, separators=(",", ":")).encode()
                raw = gzip.compress(payload, compresslevel=9, mtime=0)
                with open(path, "wb") as f:
                    f.write(raw)
                print(f"fetched {sym} {iv}: {len(rows)} bars, {len(raw)} bytes gz")
            manifest["files"][os.path.basename(path)] = {
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "rows": len(json.loads(gzip.decompress(raw))["rows"]),
            }
    with open(os.path.join(DATA_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    print("manifest written:", os.path.join(DATA_DIR, "manifest.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
