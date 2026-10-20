"""Validate a price-action briefing and check number provenance."""
from __future__ import annotations

import json
import re
import sys

REQUIRED = {
    "always_in": ("Always-In", "缺少 Always-In"),
    "setup": ("Setup", "缺少 Setup"),
    "rr": ("R:R", "缺少 R:R"),
    "trigger": ("触发", "缺少触发"),
    "invalidation": ("失效", "缺少失效"),
    "target": ("目标", "缺少目标"),
    "disclaimer": ("非投资建议", "缺少免责声明"),
}


def validate_brief(text: str) -> dict:
    checks = {}
    for key, (needle, msg) in REQUIRED.items():
        ok = needle.lower() in text.lower()
        checks[key] = {"ok": ok, "note": "" if ok else msg}
    for sym in ("BTC", "ETH"):
        ok = bool(re.search(r"SIGNAL\|" + sym + r"\|", text, re.I))
        checks["signal_" + sym.lower()] = {"ok": ok, "note": "" if ok else "缺少 SIGNAL|" + sym + "|"}
    return {"ok": all(c["ok"] for c in checks.values()), "checks": checks}


def _numbers(text: str):
    out = []
    for raw in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
        try:
            out.append(float(raw.replace(",", "")))
        except ValueError:
            pass
    return out


def check_numbers(text: str, source: str, tol: float = 0.02) -> dict:
    src = _numbers(source)
    suspects = []
    for n in _numbers(text):
        if n < 100:
            continue
        if not any(abs(n - s) <= max(0.5, abs(s) * tol) for s in src):
            suspects.append(n)
    return {"ok": not suspects, "suspects": suspects[:20]}


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print("usage: python3 -m nakedk.validate <brief.txt> [source.txt]")
        return 2
    text = open(argv[0], encoding="utf-8").read()
    result = {"brief": validate_brief(text)}
    if len(argv) > 1:
        source = open(argv[1], encoding="utf-8").read()
        result["numbers"] = check_numbers(text, source)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["brief"]["ok"] and result.get("numbers", {}).get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
