"""Feedback loop: scoreboard, bucket statistics and adaptive weights."""
from __future__ import annotations

import time

from nakedk.stats import bucket, summarize

from . import adaptive, store


def load_rows(db_path: str) -> list:
    conn = store.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT s.id, s.ts, s.symbol, s.direction, s.confidence, s.setup, s.regime, "
            "s.mtf_alignment, s.source, o.ret_pct, o.hit, o.mfe_pct, o.mae_pct, o.first_touch "
            "FROM signals s JOIN outcomes o ON o.signal_id = s.id "
            "WHERE s.direction IN ('long', 'short')"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _count_signals(db_path: str) -> int:
    conn = store.connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM signals WHERE direction IN ('long', 'short')"
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def _mtf_key(r):
    a = r.get("mtf_alignment")
    if a is None:
        return "unknown"
    if a >= 2:
        return "aligned_up"
    if a <= -2:
        return "aligned_down"
    return "mixed"


def build(db_path: str, adaptive_path: str | None = None, apply: bool = False) -> dict:
    rows = load_rows(db_path)
    live = [r for r in rows if (r.get("source") or "live") != "engine_backfill"]
    base = summarize(live) if live else summarize(rows)
    report = {
        "generated_at": int(time.time() * 1000),
        "n_total": len(rows),
        "n_pending": max(0, _count_signals(db_path) - len(rows)),
        "n_live": len(live),
        "base": base,
        "by_setup": bucket(rows, lambda r: r.get("setup") or "NONE"),
        "by_regime": bucket(rows, lambda r: r.get("regime") or "unknown"),
        "by_mtf": bucket(rows, _mtf_key),
        "by_confidence": bucket(rows, lambda r: str((int(r.get("confidence") or 50) // 5) * 5)),
    }
    report["reliable_setups"] = [k for k, v in report["by_setup"].items() if v["reliable"]]
    if adaptive_path:
        table = adaptive.load(adaptive_path)
        if apply and rows:
            base_rate = (base.get("hit_rate") or 50.0) / 100.0
            table = adaptive.update(table, report["by_setup"], base_rate)
            adaptive.save(adaptive_path, table)
        report["adaptive"] = {
            "updated_at": table.get("updated_at"),
            "version": table.get("version"),
            "multipliers": table.get("multipliers", {}),
            "recent_changes": table.get("log", [])[-5:],
        }
    return report


def render(report: dict) -> str:
    b = report.get("base", {})
    lines = [
        "===== 反馈闭环复盘 =====",
        f"样本: {report.get('n_total')} (live {report.get('n_live')}) | "
        f"命中率 {b.get('hit_rate')}% | Wilson {b.get('wilson')} | "
        f"期望 {b.get('expectancy')}% | MFE {b.get('mfe')} / MAE {b.get('mae')}",
        "",
        "--- 按形态 ---",
    ]
    for k, v in report.get("by_setup", {}).items():
        tag = "" if v["reliable"] else " (样本不足)"
        lines.append(f"{k}: n={v['n']} hit={v['hit_rate']}% "
                     f"wilson={v['wilson']} exp={v['expectancy']}{tag}")
    lines.append("")
    lines.append("--- 按结构状态 ---")
    for k, v in report.get("by_regime", {}).items():
        lines.append(f"{k}: n={v['n']} hit={v['hit_rate']}% exp={v['expectancy']}")
    lines.append("")
    lines.append("--- 按 MTF 对齐 ---")
    for k, v in report.get("by_mtf", {}).items():
        lines.append(f"{k}: n={v['n']} hit={v['hit_rate']}% exp={v['expectancy']}")
    ad = report.get("adaptive") or {}
    if ad:
        lines.append("")
        lines.append(f"--- 自适应权重 v{ad.get('version')} ---")
        mults = ad.get("multipliers") or {}
        lines.append("multipliers: " + (", ".join(f"{k}={v}" for k, v in mults.items()) or "none"))
        for ch in ad.get("recent_changes", []):
            lines.append(f"  {ch['setup']}: {ch['old']} -> {ch['new']} "
                         f"(n={ch['n']} hit={ch['hit_rate']}% {ch['reason']})")
    return "\n".join(lines)

