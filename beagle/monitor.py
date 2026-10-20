"""Market monitor: snapshot -> features -> events -> state."""
from __future__ import annotations

import json
import sys
import time

from nakedk.features import features_from_klines
from nakedk.fetch import get_json

from . import store
from .detect import alert_text, detect_events


def funding_rate(symbol: str) -> float | None:
    try:
        base = symbol.replace("USDT", "")
        data = get_json_gate(f"/api/v4/futures/usdt/funding_rate?contract={base}_USDT")
        return float(data.get("r"))
    except Exception:
        return None


def get_json_gate(path: str):
    import urllib.request
    url = "https://api.gateio.ws" + path
    req = urllib.request.Request(url, headers={"User-Agent": "beagle/1.0"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode())


def snapshot(symbol: str) -> dict:
    k4 = get_json(f"/api/v3/klines?symbol={symbol}&interval=4h&limit=200")
    k1m = get_json(f"/api/v3/klines?symbol={symbol}&interval=1m&limit=60")
    features = features_from_klines(k4)
    closes = [float(r[4]) for r in k1m]
    vols = [float(r[5]) for r in k1m]
    vol_z = 0.0
    if len(vols) >= 20:
        base = vols[-20:-1]
        mu = sum(base) / len(base)
        sd = (sum((v - mu) ** 2 for v in base) / len(base)) ** 0.5 or 1.0
        vol_z = (vols[-1] - mu) / sd
    return {
        "features": features,
        "close_1m": closes[-1] if closes else None,
        "prev_close_1m": closes[-2] if len(closes) > 1 else None,
        "vol_z_1m": vol_z,
        "funding": funding_rate(symbol),
    }


def run_once(cfg: dict, db_path: str) -> list[dict]:
    store.init(db_path)
    out = []
    now = int(time.time() * 1000)
    hourly = store.count_alerts_since(db_path, now - 3600_000)
    daily = store.count_alerts_since(db_path, now - 86_400_000)
    if hourly >= cfg["rate_limit_per_hour"] or daily >= cfg["rate_limit_per_day"]:
        store.record_run(db_path, "once", "rate_limited",
                         f"hourly={hourly} daily={daily}")
        return out

    for symbol in cfg["symbols"]:
        try:
            snap = snapshot(symbol)
        except Exception as e:
            store.record_run(db_path, "once", "fetch_error", f"{symbol}: {e}")
            continue
        prev_state = store.get_state(db_path, symbol)
        events = detect_events(
            symbol, snap["features"], snap["close_1m"], snap["prev_close_1m"],
            snap["vol_z_1m"], snap["funding"], prev_state, cfg,
        )
        store.set_state(db_path, symbol, snap["features"].get("trend"))
        for ev in events:
            if ev["severity"] != "P0" and ev.get("quality", 50) < cfg.get("thresholds", {}).get("min_quality", 40):
                continue
            if store.recent_alert_exists(db_path, ev["symbol"], ev["kind"],
                                         ev["direction"], now):
                continue
            event_id = store.add_event(db_path, ev)
            cooldown = cfg["cooldown_min"].get(ev["severity"], 120) * 60_000
            store.add_alert(db_path, event_id, ev["severity"], alert_text(ev), cooldown)
            out.append(ev)

    store.heartbeat(db_path, queue_depth=store.status(db_path)["pending"])
    store.record_run(db_path, "once", "ok", f"events={len(out)}")
    return out


def monitor(cfg: dict, db_path: str) -> None:
    store.init(db_path)
    interval = int(cfg.get("poll_seconds", 60))
    while True:
        try:
            run_once(cfg, db_path)
        except Exception as e:
            store.record_run(db_path, "monitor", "error", str(e))
        time.sleep(interval)
