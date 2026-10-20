# -----------------------------------------------------------------
# nakedk/cli.py - naked-k-analysis core price-action engine
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-65B91A8F
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
"""Command line interface for naked-k-analysis."""
from __future__ import annotations

import argparse
import json
import time

from .fetch import summarise
from .score import evaluate, load_ledger, summarise as score_summarise
from .signals import signal_line, stance


def cmd_fetch(args) -> int:
    for i, symbol in enumerate(args.symbols):
        text, _ = summarise(symbol)
        if i:
            print()
        print(text)
    print("\n# source: Binance public data (data-api.binance.vision)")
    return 0


def _record_signal(db_path, symbol, s, features):
    from beagle import store as bstore
    from .bars import closed_bars
    from .fetch import klines
    from .mtf import alignment as mtf_alignment
    from .patterns import arbitrate, detect as detect_patterns
    from .structure import structure as structure_of
    try:
        ks = closed_bars(klines(symbol, "4h", 200), "4h")
        arb = arbitrate(detect_patterns(ks, features), features)
        stc = structure_of(ks)
        try:
            mtf = mtf_alignment(symbol)["alignment"]
        except Exception:
            mtf = None
        bstore.init(db_path)
        return bstore.add_signal(db_path, {
            "ts": int(time.time() * 1000), "symbol": symbol,
            "direction": s.get("direction"), "confidence": s.get("confidence"),
            "entry": s.get("entry"), "stop": s.get("stop"),
            "target": s.get("target"), "horizon_h": 4, "source": "live",
            "setup": (arb.get("primary") or {}).get("type"),
            "regime": stc.get("state"), "mtf_alignment": mtf,
        })
    except Exception:
        return None


def cmd_signal(args) -> int:
    rows = []
    for symbol in args.symbols:
        _, features = summarise(symbol)
        s = stance(features)
        line = signal_line(symbol, s)
        rec = {"symbol": symbol, **s, "signal": line}
        if getattr(args, "record_db", None):
            rec["record_id"] = _record_signal(args.record_db, symbol, s, features)
        rows.append(rec)
        if not args.json:
            print(line)
            print("  " + "; ".join(s["reasons"]))
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def cmd_score(args) -> int:
    rows = []
    for record in load_ledger(args.ledger):
        result = evaluate(record)
        if result:
            rows.append(result)
    print(json.dumps(score_summarise(rows), ensure_ascii=False, indent=2))
    return 0


def cmd_backtest(args) -> int:
    from .backtest import run, walk_forward
    folds = getattr(args, "folds", 1) or 1
    rows = []
    for symbol in args.symbols:
        ib = not getattr(args, "no_intrabar", False)
        if folds > 1:
            rows.append(walk_forward(symbol, days=args.days, folds=folds,
                                     horizon=args.horizon, cost_bps=args.cost_bps,
                                     intrabar=ib, gate=args.gate,
                                     tag_setups=args.tag_setups))
        else:
            rows.append(run(symbol, days=args.days, horizon=args.horizon,
                            cost_bps=args.cost_bps, intrabar=ib, gate=args.gate,
                            tag_setups=args.tag_setups))
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nakedk",
        description="Zero-dependency price-action analysis, signals and outcome scoring.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="print the 4h feature summary for symbols")
    p_fetch.add_argument("symbols", nargs="+")
    p_fetch.set_defaults(func=cmd_fetch)

    p_signal = sub.add_parser("signal", help="emit deterministic SIGNAL lines")
    p_signal.add_argument("symbols", nargs="+")
    p_signal.add_argument("--json", action="store_true")
    p_signal.add_argument("--record-db", help="record signals into a beagle SQLite DB")
    p_signal.set_defaults(func=cmd_signal)

    p_score = sub.add_parser("score", help="score a JSONL signal ledger against real prices")
    p_score.add_argument("ledger")
    p_score.set_defaults(func=cmd_score)

    p_bt = sub.add_parser("backtest", help="walk-forward backtest of the deterministic engine")
    p_bt.add_argument("symbols", nargs="+")
    p_bt.add_argument("--days", type=int, default=365)
    p_bt.add_argument("--horizon", type=int, default=1, help="exit horizon in 4h bars")
    p_bt.add_argument("--folds", type=int, default=1, help="split into N out-of-sample folds")
    p_bt.add_argument("--cost-bps", type=float, default=12.0,
                      help="round-trip fees+slippage in basis points")
    p_bt.add_argument("--no-intrabar", action="store_true",
                      help="skip 1h path simulation (faster, less honest)")
    p_bt.add_argument("--tag-setups", action="store_true",
                      help="tag every trade with its primary pattern for attribution")
    p_bt.add_argument("--gate", choices=["none", "quality", "quality_soft"], default="none",
                      help="extra entry gate for iteration")
    p_bt.set_defaults(func=cmd_backtest)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
