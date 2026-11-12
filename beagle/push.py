"""Push pending beagle alerts through OpenClaw's qqbot channel."""
from __future__ import annotations

import os
import shutil
import shlex
import subprocess
import time

from . import store


def cli_path() -> str:
    """Resolve the OpenClaw CLI even when systemd PATH is minimal."""
    env = os.environ.get("BEAGLE_OPENCLAW_CLI")
    if env and os.path.exists(env):
        return env
    found = shutil.which("openclaw")
    if found:
        return found
    for cand in ("/home/ubuntu/.npm-global/bin/openclaw",
                 "/usr/local/bin/openclaw",
                 "/opt/homebrew/bin/openclaw"):
        if os.path.exists(cand):
            return cand
    return "openclaw"


def load_env_file(path: str) -> None:
    """Load KEY=VALUE lines (systemd EnvironmentFile equivalent)."""
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
    except FileNotFoundError:
        return
    except Exception:
        return


def _single_target(value) -> str:
    """Hard guarantee: every message goes to exactly ONE configured group."""
    v = str(value or "").strip()
    if not v:
        return ""
    if any(c in v for c in (",", ";", "\n", "\r", " ", "\t")):
        raise ValueError("qq_target must be a single group id, got %r" % v)
    return v


def resolve_target(cfg: dict, db_path: str):
    target = (cfg or {}).get("qq_target") or os.environ.get("BEAGLE_QQ_TARGET")
    if not target:
        path = os.environ.get("BEAGLE_ENV_FILE") or os.path.join(
            os.path.dirname(db_path) or ".", ".beagle.env")
        load_env_file(path)
        target = os.environ.get("BEAGLE_QQ_TARGET")
    return _single_target(target)


def transport_host(cfg: dict | None) -> str:
    return str((cfg or {}).get("push_ssh") or os.environ.get("BEAGLE_PUSH_SSH") or "").strip()


def _run_send(args: list, cfg: dict | None):
    """Send through this gateway, or through a configured SSH gateway.

    A remote host is used when the local gateway has no qqbot channel but
    another machine (e.g. the old qsp box) already has one configured. The
    message is passed as a single quoted argv, never interpolated into a
    shell string on the local side.
    """
    host = transport_host(cfg)
    if host:
        remote = "openclaw " + " ".join(shlex.quote(a) for a in args)
        cmd = ["ssh", "-T", "-o", "BatchMode=yes", "-o",
               "StrictHostKeyChecking=no", host, remote]
    else:
        cmd = [cli_path()] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=90)


def is_stale(created_at, now_ms: int, max_age_min: int) -> bool:
    if not max_age_min or not created_at:
        return False
    return (now_ms - int(created_at)) > max_age_min * 60_000


_FOOTER_CACHE: dict = {}


def _symbol_from_text(text: str):
    first = (text or "").splitlines()[0] if text else ""
    base = first.split(" · ")[0].strip()
    if base and base.isalnum() and 2 <= len(base) <= 10:
        return base + "USDT"
    return None


def _with_data_footer(alert):
    text = alert.get("text") or ""
    if "多源：" in text:
        return text
    sym = _symbol_from_text(text)
    if not sym:
        return text
    if sym not in _FOOTER_CACHE:
        try:
            from nakedk.sources import aggregate
            _FOOTER_CACHE[sym] = aggregate(sym)
        except Exception:
            _FOOTER_CACHE[sym] = {}
    d = _FOOTER_CACHE.get(sym) or {}
    if not d:
        return text
    warn = "（多源不一致，注意）" if (d.get("n", 0) < 3 or d.get("max_dev_pct", 0) > 0.5) else ""
    line = (f"多源：{d['n']}源加权 · 偏差{d['max_dev_pct']}%"
            f" · 置信{d['confidence']}{warn}")
    if "\n数据：" in text:
        return text.replace("\n数据：", "\n" + line + "\n数据：", 1)
    return text + "\n" + line


def _quiet(hour: int, cfg: dict) -> bool:
    q0, q1 = cfg.get("quiet_hours", [23, 8])
    return (hour >= q0 or hour < q1) if q0 > q1 else (q0 <= hour < q1)


def push_pending(cfg: dict, db_path: str, dry_run: bool = False, limit: int = 20):
    target = resolve_target(cfg, db_path)
    alerts = store.pending_alerts(db_path, limit)
    results = []
    now_ms = int(time.time() * 1000)
    max_age = int(cfg.get("max_alert_age_min", 30) or 0)
    for a in alerts:
        if is_stale(a.get("created_at"), now_ms, max_age):
            store.mark_stale(db_path, a["id"])
            results.append({"id": a["id"], "status": "stale_skip",
                            "age_min": round((now_ms - int(a["created_at"])) / 60_000, 1)})
            continue
        if a["severity"] == "P2":
            # Deferred, not terminal: p2_deferred was never picked up again by
            # pending_alerts(), so every P2 alert was silently lost forever.
            store.fail_alert(db_path, a["id"], "p2_deferred", cfg.get("max_push_attempts", 5))
            results.append({"id": a["id"], "status": "p2_deferred"})
            continue
        if _quiet(time.localtime().tm_hour, cfg) and a["severity"] != "P0":
            results.append({"id": a["id"], "status": "quiet_skip"})
            continue
        if dry_run:
            results.append({"id": a["id"], "status": "dry", "severity": a["severity"], "text": a["text"]})
            continue
        if not target:
            results.append({"id": a["id"], "status": "no_target"})
            continue
        text = _with_data_footer(a)
        args = ["message", "send", "--channel", "qqbot",
                "--target", target, "--message", text]
        try:
            p = _run_send(args, cfg)
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


def push_outbox(db_path: str, cfg: dict | None = None, dry_run: bool = False,
                limit: int = 20):
    """Drain plan-transition messages (outbox) to the configured QQ target.

    Plan text is composed once when the transition is recorded, so delivery
    retries can never re-derive different numbers. Quiet hours skip (and keep
    pending) everything except P0, which maps to stop / invalidation.
    """
    cfg = cfg or {}
    try:
        target = resolve_target(cfg, db_path)
    except ValueError as e:
        return [{"status": "invalid_target", "error": str(e)}]
    out = []
    now_hour = time.localtime().tm_hour
    now_ms = int(time.time() * 1000)
    max_age = int((cfg or {}).get("max_alert_age_min", 30) or 0) * 60_000
    max_attempts = int(cfg.get("max_push_attempts", 5) or 5)
    for row in store.outbox_pending(db_path, limit):
        oid = row["id"]
        if dry_run:
            out.append({"id": oid, "status": "dry", "text": row.get("text", "")[:120]})
            continue
        # Explicit urgent flag (set by state switches / triggers / errors)
        # plus the legacy keyword fallback for older outbox rows.
        urgent = bool(row.get("urgent")) or any(
            k in (row.get("text") or "")
            for k in ("止损离场", "结构失效", "计划超时"))
        # Quiet hours must defer, not destroy. The old code checked staleness
        # BEFORE the quiet gate, so messages born at 23:00 died at 23:30 and
        # the same 20 pending rows blocked the queue as head-of-line.
        if _quiet(now_hour, cfg) and not urgent:
            store.outbox_mark(db_path, oid, "pending", "quiet_hours",
                              next_attempt_at=now_ms + 5 * 60_000)
            out.append({"id": oid, "status": "quiet_skip"})
            continue
        if max_age and row.get("created_at") and \
                now_ms - int(row["created_at"]) > max_age and not urgent:
            store.outbox_mark(db_path, oid, "stale", "expired after quiet hours")
            out.append({"id": oid, "status": "stale_skip"})
            continue
        if not target:
            store.outbox_mark(db_path, oid, "pending", "no_target",
                              next_attempt_at=now_ms + 60_000)
            out.append({"id": oid, "status": "no_target"})
            continue
        args = ["message", "send", "--channel", "qqbot",
                "--target", target, "--message", row["text"]]
        err, rc = "", 0
        try:
            p = _run_send(args, cfg)
            rc = p.returncode
            err = (p.stderr or p.stdout or "")[:200] if rc else ""
        except Exception as e:
            rc, err = -1, str(e)[:200]
        if rc == 0:
            store.outbox_mark(db_path, oid, "sent")
            out.append({"id": oid, "status": "sent"})
            continue
        attempts = int(row.get("attempts") or 0) + 1
        if attempts >= max_attempts:
            # Genuinely terminal, but now with the reason persisted.
            store.outbox_mark(db_path, oid, "failed", err)
            new_status = "failed"
        else:
            # One transient exception used to permanently kill the message:
            # outbox_pending() only selects status='pending'.
            backoff = min(300_000, 15_000 * (2 ** min(attempts, 5)))
            store.outbox_mark(db_path, oid, "pending", err,
                              next_attempt_at=now_ms + backoff)
            new_status = "pending"
        out.append({"id": oid, "status": new_status, "attempts": attempts,
                    "err": err})
    return out
