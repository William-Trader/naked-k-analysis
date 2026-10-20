"""Configuration loading for the beagle monitor."""
from __future__ import annotations

import json
import os

DEFAULTS = {
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "db_path": "beagle.db",
    "poll_seconds": 60,
    "cooldown_min": {"P0": 60, "P1": 120, "P2": 360},
    "quiet_hours": [23, 8],
    "rate_limit_per_hour": 6,
    "rate_limit_per_day": 20,
    "max_push_attempts": 5,
    "thresholds": {
        "price_shock_atr": 0.8,
        "price_shock_pct": 0.5,
        "extreme_shock_atr": 2.0,
        "extreme_pct": 1.5,
        "extreme_pct_1h": 3.0,
        "vol_z": 3.0,
        "breakout_vol_z": 1.0,
        "min_quality": 40,
    },
}


def load(path: str | None = None) -> dict:
    cfg = json.loads(json.dumps(DEFAULTS))
    if path is None:
        path = os.environ.get("BEAGLE_CONFIG", "config/beagle.json")
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            user = json.load(fh)
        _deep_update(cfg, user)
    return cfg


def _deep_update(base: dict, extra: dict) -> None:
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
