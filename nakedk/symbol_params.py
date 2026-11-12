# -----------------------------------------------------------------
# nakedk/symbol_params.py - naked-k-analysis per-instrument parameter library
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-48F37A82
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
# -*- coding: utf-8 -*-
"""Per-instrument price-action parameters.

Every symbol gets its own parameter set. The library is a single JSON file
(state/symbol_profiles.json by default) so it is inspectable, diffable and
easy to back up. Symbol values override the global defaults in
nakedk.params; absent keys fall back to the measured global behaviour.

A profile also carries provenance (source: manual / llm / default), a version
counter and a short history so an automatic LLM tuning step can always be
traced and rolled back.
"""
from __future__ import annotations

import copy
import json
import os
import threading
import time

from . import params as global_params

_PATH = os.environ.get("NK_SYMBOL_PROFILES", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "state", "symbol_profiles.json"))

# hard bounds: any automated (LLM) proposal outside these is rejected
BOUNDS = {
    "stance_adx_trend": (12.0, 35.0),
    "stance_pos_short": (0.15, 0.45),
    "stance_pos_long": (0.55, 0.85),
    "stance_stop_atr": (0.8, 3.0),
    "stance_target_atr": (1.5, 6.0),
    "stance_overlap_max": (0.45, 0.90),
    "stance_min_vol_z": (-1.0, 1.5),
    "trend_adx_trend": (12.0, 35.0),
    "trend_label_up": (54.0, 70.0),
    "trend_label_down": (30.0, 46.0),
    "signalbar_min_quality": (25, 65),
    "plan_min_confidence": (45.0, 68.0),
    "plan_min_rr": (1.2, 3.0),
    "plan_ttl_h": (4, 48),
    "plan_risk_pct": (0.1, 2.0),
    "plan_min_confluence": (30.0, 80.0),
    # Previously unbounded: any numeric value (negative / 1e9) could be
    # persisted for these keys and silently disable the plan engine.
    "plan_trigger_max_atr": (0.2, 5.0),
    "plan_confirm_bars": (1, 12),
    "plan_max_open": (1, 8),
    "trend_label_strong_up": (50.0, 95.0),
    "trend_label_strong_down": (5.0, 50.0),
}

# extra plan-level keys are not part of nakedk.params.DEFAULTS
PLAN_DEFAULTS = {
    "plan_min_confidence": 52.0,
    "plan_min_rr": 1.5,
    "plan_ttl_h": 12,
    "plan_trigger_max_atr": 1.5,
    "plan_confirm_bars": 3,
    "plan_max_open": 2,
    "plan_risk_pct": 0.5,
    "plan_min_confluence": 40.0,
}

_LOCK = threading.RLock()


def _read(path=None) -> dict:
    p = path or _PATH
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write(data: dict, path=None):
    p = path or _PATH
    try:
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, p)
    except Exception:
        pass


def defaults() -> dict:
    """Global defaults plus plan-level defaults (one merged dictionary)."""
    d = dict(global_params.DEFAULTS)
    d.update(PLAN_DEFAULTS)
    return d


def get(symbol: str, path=None) -> dict:
    """Merged effective params for one symbol."""
    base = defaults()
    with _LOCK:
        prof = _read(path).get(_norm(symbol)) or {}
    over = prof.get("params") or {}
    for k, v in over.items():
        if k in base and isinstance(v, (int, float)) and not isinstance(v, bool):
            if k in BOUNDS:
                lo, hi = BOUNDS[k]
                v = max(lo, min(hi, float(v)))
            base[k] = v
    return base


def profile(symbol: str, path=None) -> dict:
    with _LOCK:
        prof = copy.deepcopy(_read(path).get(_norm(symbol)) or {})
    prof.setdefault("symbol", _norm(symbol))
    prof.setdefault("params", {})
    prof.setdefault("version", 0)
    prof.setdefault("source", "default")
    prof.setdefault("updated_at", None)
    prof.setdefault("history", [])
    prof["effective"] = get(symbol, path)
    return prof


def all_profiles() -> dict:
    with _LOCK:
        raw = _read()
    out = {}
    for sym in raw:
        out[sym] = profile(sym)
    return out


def save(symbol: str, patch: dict, source: str = "manual", note: str = "",
         path=None) -> dict:
    """Merge a patch into a symbol profile.

    Only known keys are written and every numeric value is clamped to BOUNDS.
    The previous effective values are appended to history (max 20 entries),
    which makes an automated change reversible.
    """
    sym = _norm(symbol)
    clean = {}
    for k, v in (patch or {}).items():
        if k not in defaults():
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        if k in BOUNDS:
            lo, hi = BOUNDS[k]
            v = max(lo, min(hi, float(v)))
            if isinstance(defaults()[k], int):
                v = int(round(v))
        clean[k] = v
    with _LOCK:
        data = _read(path)
        prof = data.get(sym) or {}
        hist = list(prof.get("history") or [])
        if clean:
            hist.append({
                "at": int(time.time() * 1000),
                "source": source,
                "note": note[:200],
                "before": prof.get("params") or {},
                "patch": clean,
            })
        merged = dict(prof.get("params") or {})
        merged.update(clean)
        data[sym] = {
            "symbol": sym,
            "params": merged,
            "version": int(prof.get("version") or 0) + (1 if clean else 0),
            "source": source,
            "note": note[:200],
            "updated_at": int(time.time() * 1000),
            "history": hist[-20:],
        }
        _write(data, path)
    return profile(sym)


def revert(symbol: str, version: int | None = None, path=None) -> dict:
    """Restore the effective params from a history entry (default: latest)."""
    sym = _norm(symbol)
    with _LOCK:
        data = _read(path)
        prof = data.get(sym) or {}
        hist = list(prof.get("history") or [])
        if not hist:
            return profile(sym)
        entry = hist[-1] if version is None else next(
            (h for h in reversed(hist) if h.get("at") == version), hist[-1])
        data[sym] = {
            "symbol": sym,
            "params": dict(entry.get("before") or {}),
            "version": int(prof.get("version") or 0) + 1,
            "source": "revert",
            "note": "reverted",
            "updated_at": int(time.time() * 1000),
            "history": hist,
        }
        _write(data, path)
    return profile(sym)


def validate_patch(patch: dict) -> list:
    """Return human-readable validation errors for an automated proposal."""
    errs = []
    for k, v in (patch or {}).items():
        if k not in defaults():
            errs.append(f"unknown key {k}")
            continue
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            errs.append(f"{k}: not numeric")
            continue
        if k in BOUNDS:
            lo, hi = BOUNDS[k]
            if not (lo <= float(v) <= hi):
                errs.append(f"{k}: {v} outside [{lo}, {hi}]")
    return errs


def _norm(symbol: str) -> str:
    return (symbol or "").strip().upper()
