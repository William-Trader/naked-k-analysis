"""Family-level quality calibration (bounded, auditable)."""
from __future__ import annotations

import json
import os


def load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        out = {}
        for k, v in (raw.get("multipliers") or {}).items():
            try:
                out[k] = max(0.85, min(1.15, float(v)))
            except (TypeError, ValueError):
                continue
        return out
    except Exception:
        return {}


def save(path: str, multipliers: dict, source_n: int = 0) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"multipliers": multipliers, "source_n": source_n}, fh,
                  ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)
