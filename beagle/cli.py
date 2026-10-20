"""Command line interface: python -m beagle [once|monitor|status|push|score]."""
from __future__ import annotations

import argparse
import json
import os
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
    if args.send or args.dry_run:
        from .push import push_pending
        print(json.dumps(push_pending(cfg, cfg["db_path"], dry_run=args.dry_run,
                                      limit=args.limit), ensure_ascii=False, indent=2))
        return 0
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


def apply_corr_gate(candidates, corr, threshold: float = 0.8):
    """BTC/ETH with high correlation count as one risk; drop the weaker one."""
    btc = next((c for c in candidates if c["symbol"] == "BTCUSDT"), None)
    eth = next((c for c in candidates if c["symbol"] == "ETHUSDT"), None)
    if not btc or not eth or btc["direction"] != eth["direction"]:
        return candidates, None
    if corr is None or corr <= threshold:
        return candidates, None
    drop = min(btc, eth, key=lambda c: c.get("confidence") or 0)
    kept = btc if drop is eth else eth
    return ([c for c in candidates if c is not drop],
            {"dropped": drop["symbol"], "kept": kept["symbol"], "corr": corr})


def cmd_record(args):
    """Record the current closed-bar stance once per 4h bar (live loop input)."""
    from nakedk.bars import closed_bars
    from nakedk.features import features_from_klines
    from nakedk.fetch import klines
    from nakedk.mtf import alignment as mtf_alignment
    from nakedk.patterns import arbitrate, detect as detect_patterns
    from nakedk.signals import stance
    from nakedk.structure import structure as structure_of

    cfg = _cfg(args.config)
    store.init(cfg["db_path"])
    out = []
    candidates = []
    for symbol in (args.symbols or cfg["symbols"]):
        try:
            ks = closed_bars(klines(symbol, "4h", 200), "4h")
            bar_ts = int(ks[-1][0])
            last = store.last_signal_ts(cfg["db_path"], symbol)
            if last is not None and last >= bar_ts:
                out.append({"symbol": symbol, "status": "duplicate"})
                continue
            f = features_from_klines(ks)
            s = stance(f)
            if s["direction"] not in ("long", "short"):
                out.append({"symbol": symbol, "status": "neutral"})
                continue
            arb = arbitrate(detect_patterns(ks, f), f)
            stc = structure_of(ks)
            try:
                mtf = mtf_alignment(symbol)["alignment"]
            except Exception:
                mtf = None
            candidates.append({
                "symbol": symbol, "ts": bar_ts, "direction": s["direction"],
                "confidence": s.get("confidence"),
                "entry": s.get("entry") or f["price"],
                "stop": s.get("stop"), "target": s.get("target"),
                "setup": (arb.get("primary") or {}).get("type") or "NONE",
                "regime": stc.get("state"), "mtf": mtf,
            })
        except Exception as e:
            out.append({"symbol": symbol, "status": "error", "error": str(e)[:120]})

    corr = None
    try:
        from nakedk.cross import correlation
        b = [float(k[4]) for k in closed_bars(klines("BTCUSDT", "1d", 40), "1d")]
        e = [float(k[4]) for k in closed_bars(klines("ETHUSDT", "1d", 40), "1d")]
        rb = [b[i] / b[i - 1] - 1 for i in range(1, len(b)) if b[i - 1]]
        re = [e[i] / e[i - 1] - 1 for i in range(1, len(e)) if e[i - 1]]
        corr = correlation(rb, re)
    except Exception:
        corr = None
    candidates, gate = apply_corr_gate(candidates, corr)
    if gate:
        out.append({"status": "corr_suppressed", **gate})

    for c in candidates:
        try:
            sid = store.add_signal(cfg["db_path"], {
                "ts": c["ts"], "symbol": c["symbol"], "direction": c["direction"],
                "confidence": c["confidence"], "entry": c["entry"],
                "stop": c["stop"], "target": c["target"], "horizon_h": 4,
                "source": "live", "setup": c["setup"], "regime": c["regime"],
                "mtf_alignment": c["mtf"],
            })
            out.append({"symbol": c["symbol"], "status": "recorded", "id": sid,
                        "direction": c["direction"], "setup": c["setup"],
                        "mtf": c["mtf"], "regime": c["regime"], "corr": corr})
        except Exception as e:
            out.append({"symbol": c["symbol"], "status": "error", "error": str(e)[:120]})
    print(json.dumps(out, ensure_ascii=False))
    return 0


def cmd_review(args):
    from .review import build, render
    cfg = _cfg(args.config)
    store.init(cfg["db_path"])
    path = cfg.get("adaptive_path") or os.path.join(
        os.path.dirname(cfg["db_path"]) or ".", "state", "adaptive.json")
    report = build(cfg["db_path"], path, apply=args.apply)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report))
    return 0


def cmd_backfill(args):
    """Generate labelled historical signals so the loop has data on day one."""
    from nakedk.bars import closed_bars
    from nakedk.features import features_from_klines
    from nakedk.fetch import klines
    from nakedk.patterns import arbitrate, detect as detect_patterns
    from nakedk.signals import stance
    from nakedk.structure import structure as structure_of

    cfg = _cfg(args.config)
    store.init(cfg["db_path"])
    inserted = 0
    for symbol in (args.symbols or cfg["symbols"]):
        ks = closed_bars(klines(symbol, "4h", min(1000, args.days * 6 + 80)), "4h")
        for i in range(60, len(ks) - 1):
            window = ks[: i + 1][-200:]
            try:
                f = features_from_klines(window)
            except ValueError:
                continue
            s = stance(f)
            if s["direction"] not in ("long", "short"):
                continue
            arb = arbitrate(detect_patterns(window, f), f)
            stc = structure_of(window)
            sid = store.add_signal(cfg["db_path"], {
                "ts": int(ks[i][0]), "symbol": symbol,
                "direction": s["direction"], "confidence": s.get("confidence"),
                "entry": float(ks[i][4]), "stop": s.get("stop"),
                "target": s.get("target"), "horizon_h": 1,
                "source": "engine_backfill",
                "setup": (arb.get("primary") or {}).get("type") or "NONE",
                "regime": stc.get("state"), "mtf_alignment": None,
            })
            entry = float(ks[i][4])
            nxt = ks[i + 1]
            exit_ = float(nxt[4])
            ret = (exit_ / entry - 1.0) * 100.0
            hit = int(ret > 0) if s["direction"] == "long" else int(ret < 0)
            hi, lo = float(nxt[2]), float(nxt[3])
            mfe = ((hi - entry) if s["direction"] == "long" else (entry - lo)) / entry * 100.0
            mae = ((lo - entry) if s["direction"] == "long" else (entry - hi)) / entry * 100.0
            store.add_outcome(cfg["db_path"], sid, 1, int(nxt[0]), exit_,
                              round(ret, 3), hit, round(mfe, 3), round(mae, 3), None)
            inserted += 1
    print(json.dumps({"inserted": inserted}, ensure_ascii=False))
    return 0


def cmd_replay(args):
    from .replay import replay, summarise
    cfg = _cfg(args.config)
    all_events = []
    for symbol in (args.symbols or cfg["symbols"]):
        all_events.extend(replay(symbol, args.days, cfg))
    print(json.dumps({
        "symbols": args.symbols or cfg["symbols"],
        "days": args.days,
        **summarise(all_events, cfg.get("cooldown_min")),
    }, ensure_ascii=False, indent=2))
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="beagle", description="Beagle market monitor")
    sub = p.add_subparsers(dest="command", required=True)
    for name, func in (("once", cmd_once), ("monitor", cmd_monitor),
                       ("status", cmd_status), ("score", cmd_score)):
        s = sub.add_parser(name)
        s.add_argument("--config")
        s.set_defaults(func=func)
    p_replay = sub.add_parser("replay")
    p_replay.add_argument("--config")
    p_replay.add_argument("--days", type=float, default=1.0)
    p_replay.add_argument("--symbols", nargs="*")
    p_replay.set_defaults(func=cmd_replay)

    p_push = sub.add_parser("push")
    p_push.add_argument("--config")
    p_push.add_argument("--limit", type=int, default=20)
    p_push.add_argument("--mark-sent", action="store_true")
    p_push.add_argument("--send", action="store_true")
    p_push.add_argument("--dry-run", action="store_true")
    p_push.set_defaults(func=cmd_push)
    p_record = sub.add_parser("record")
    p_record.add_argument("--config")
    p_record.add_argument("--symbols", nargs="*")
    p_record.set_defaults(func=cmd_record)

    p_review = sub.add_parser("review")
    p_review.add_argument("--config")
    p_review.add_argument("--apply", action="store_true")
    p_review.add_argument("--json", action="store_true")
    p_review.set_defaults(func=cmd_review)

    p_back = sub.add_parser("backfill")
    p_back.add_argument("--config")
    p_back.add_argument("--days", type=int, default=120)
    p_back.add_argument("--symbols", nargs="*")
    p_back.set_defaults(func=cmd_backfill)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
