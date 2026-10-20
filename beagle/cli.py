"""Command line interface: python -m beagle [once|monitor|status|push|score]."""
from __future__ import annotations

import argparse
import json
import sys

from . import config, store
from .monitor import monitor, run_once
from .score import score_pending, summary


def _cfg(path):
    return config.load(path)


def cmd_once(args):
    cfg = _cfg(args.config)
    events = run_once(cfg, cfg["db_path"])
    print(json.dumps(events, ensure_ascii=False, indent=2))
    return 0


def cmd_monitor(args):
    cfg = _cfg(args.config)
    monitor(cfg, cfg["db_path"])
    return 0


def cmd_status(args):
    cfg = _cfg(args.config)
    store.init(cfg["db_path"])
    print(json.dumps(store.status(cfg["db_path"]), ensure_ascii=False, indent=2))
    return 0


def cmd_push(args):
    cfg = _cfg(args.config)
    store.init(cfg["db_path"])
    alerts = store.pending_alerts(cfg["db_path"], args.limit)
    if args.mark_sent:
        for a in alerts:
            store.mark_sent(cfg["db_path"], a["id"])
    print(json.dumps(alerts, ensure_ascii=False, indent=2))
    return 0


def cmd_score(args):
    cfg = _cfg(args.config)
    store.init(cfg["db_path"])
    n = score_pending(cfg["db_path"])
    print(json.dumps({"scored": n, **summary(cfg["db_path"])}, ensure_ascii=False, indent=2))
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="beagle", description="Beagle market monitor")
    sub = p.add_subparsers(dest="command", required=True)
    for name, func in (("once", cmd_once), ("monitor", cmd_monitor),
                       ("status", cmd_status), ("score", cmd_score)):
        s = sub.add_parser(name)
        s.add_argument("--config")
        s.set_defaults(func=func)
    p_push = sub.add_parser("push")
    p_push.add_argument("--config")
    p_push.add_argument("--limit", type=int, default=20)
    p_push.add_argument("--mark-sent", action="store_true")
    p_push.set_defaults(func=cmd_push)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
