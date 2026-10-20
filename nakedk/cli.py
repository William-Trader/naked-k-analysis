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


def cmd_signal(args) -> int:
    rows = []
    for symbol in args.symbols:
        _, features = summarise(symbol)
        s = stance(features)
        line = signal_line(symbol, s)
        rows.append({"symbol": symbol, **s, "signal": line})
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
        if folds > 1:
            rows.append(walk_forward(symbol, days=args.days, folds=folds,
                                     horizon=args.horizon, cost_bps=args.cost_bps))
        else:
            rows.append(run(symbol, days=args.days, horizon=args.horizon,
                            cost_bps=args.cost_bps))
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
    p_signal.set_defaults(func=cmd_signal)

    p_score = sub.add_parser("score", help="score a JSONL signal ledger against real prices")
    p_score.add_argument("ledger")
    p_score.set_defaults(func=cmd_score)

    p_bt = sub.add_parser("backtest", help="walk-forward backtest of the deterministic engine")
    p_bt.add_argument("symbols", nargs="+")
    p_bt.add_argument("--days", type=int, default=365)
    p_bt.add_argument("--horizon", type=int, default=1, help="exit horizon in 4h bars")
    p_bt.add_argument("--folds", type=int, default=1, help="split into N out-of-sample folds")
    p_bt.add_argument("--cost-bps", type=float, default=10.0,
                      help="round-trip fees+slippage in basis points")
    p_bt.set_defaults(func=cmd_backtest)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
