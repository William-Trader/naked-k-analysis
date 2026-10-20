"""Push pending beagle alerts through OpenClaw's qqbot channel."""
from __future__ import annotations

import os
import subprocess
import time

from . import store


def _quiet(hour: int, cfg: dict) -> bool:
    q0, q1 = cfg.get("quiet_hours", [23, 8])
    return (hour >= q0 or hour < q1) if q0 > q1 else (q0 <= hour < q1)


def push_pending(cfg: dict, db_path: str, dry_run: bool = False, limit: int = 20):
    target = os.environ.get("BEAGLE_QQ_TARGET")
    alerts = store.pending_alerts(db_path, limit)
    results = []
    for a in alerts:
        if _quiet(time.localtime().tm_hour, cfg) and a["severity"] != "P0":
            results.append({"id": a["id"], "status": "quiet_skip"})
            continue
        if dry_run:
            results.append({"id": a["id"], "status": "dry", "severity": a["severity"], "text": a["text"]})
            continue
        if not target:
            results.append({"id": a["id"], "status": "no_target"})
            continue
        cmd = ["openclaw", "message", "send", "--channel", "qqbot",
               "--target", target, "--message", a["text"]]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        except Exception as e:
            err = str(e)[:200]
            info = store.fail_alert(db_path, a["id"], err, cfg.get("max_push_attempts", 5))
            results.append({"id": a["id"], "status": info["status"],
                            "attempts": info["attempts"], "err": err})
            continue
        if p.returncode == 0:
            store.mark_sent(db_path, a["id"])
            results.append({"id": a["id"], "status": "sent"})
        else:
            err = (p.stderr or p.stdout)[:200]
            info = store.fail_alert(db_path, a["id"], err, cfg.get("max_push_attempts", 5))
            results.append({"id": a["id"], "status": info["status"],
                            "attempts": info["attempts"], "err": err})
    return results
