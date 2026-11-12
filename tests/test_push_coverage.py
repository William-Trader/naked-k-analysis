# -----------------------------------------------------------------
# tests/test_push_coverage.py - full lifecycle notification coverage
# (c) 2026 William-Trader (https://github.com/William-Trader)
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# -----------------------------------------------------------------
"""Every trade/state transition must reach exactly ONE QQ group."""
from __future__ import annotations

import os
import tempfile
import unittest

from beagle import engine, push, store


def _payload(direction="long", structure="up", regime="transition",
             mtf="aligned_up"):
    return {
        "symbol": "BTCUSDT", "interval_order": ["15m", "4h"],
        "intervals": {"4h": {"structure": {"state": structure},
                             "regime": {"regime": regime}}},
        "combined": {"direction": direction}, "mtf": {"label": mtf},
        "last_price": 100000.0,
    }


def _settings():
    s = engine._sanitise(dict(engine.DEFAULTS))
    s["push_severity"] = sorted(engine.PUSH_EVENTS)
    s["push_state_change"] = True
    s["state_change_cooldown_min"] = 60
    s["push_dedupe_min"] = 0
    return s


class SingleGroup(unittest.TestCase):
    def test_accepts_one_group(self):
        self.assertEqual(push._single_target("group:abc123"), "group:abc123")

    def test_rejects_multiple_groups(self):
        for bad in ("group:a, group:b", "group:a;group:b", "group:a group:b",
                    "group:a\ngroup:b"):
            with self.assertRaises(ValueError):
                push._single_target(bad)

    def test_resolve_target_is_single(self):
        cfg = {"qq_target": "group:only-one"}
        self.assertEqual(push.resolve_target(cfg, "/tmp/x.db"), "group:only-one")
        with self.assertRaises(ValueError):
            push.resolve_target({"qq_target": "group:a, group:b"}, "/tmp/x.db")

    def test_push_outbox_reports_invalid_target(self):
        res = push.push_outbox("/tmp/nonexistent.db",
                               {"qq_target": "group:a, group:b"})
        self.assertEqual(res[0]["status"], "invalid_target")


class SeverityCoverage(unittest.TestCase):
    def test_all_lifecycle_events_survive_sanitise(self):
        s = engine._sanitise(dict(engine.DEFAULTS))
        s["push_severity"] = sorted(engine.PUSH_EVENTS)
        out = engine._sanitise(s)
        self.assertEqual(set(out["push_severity"]), engine.PUSH_EVENTS)

    def test_defaults_cover_core_transitions(self):
        for ev in ("triggered", "confirmed", "tp1", "tp2", "stopped",
                   "invalidated", "expired", "state_change"):
            self.assertIn(ev, engine.DEFAULTS["push_severity"])

    def test_state_change_switch_persists(self):
        s = engine._sanitise(dict(engine.DEFAULTS))
        s["push_state_change"] = False
        self.assertFalse(engine._sanitise(s)["push_state_change"])
        s["push_state_change"] = "yes"
        self.assertTrue(engine._sanitise(s)["push_state_change"])


class MarketStateNotifications(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = self.tmp.name
        store.init(self.db)
        engine._LAST_MARKET_SIG.clear()

    def tearDown(self):
        engine._LAST_MARKET_SIG.clear()
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.db + suffix)
            except OSError:
                pass

    def _outbox(self):
        c = store.connect(self.db)
        try:
            return [dict(r) for r in c.execute("SELECT * FROM outbox ORDER BY id")]
        finally:
            c.close()

    def test_first_run_records_baseline_without_pushing(self):
        changes = engine.notify_market_state("BTCUSDT", _payload(),
                                            _settings(), self.db)
        self.assertEqual(changes, [])
        self.assertEqual(len(self._outbox()), 0)
        self.assertIsNotNone(store.latest_market_state(self.db, "BTCUSDT"))

    def test_switch_pushes_one_urgent_message(self):
        s = _settings()
        engine.notify_market_state("BTCUSDT", _payload(), s, self.db)
        changes = engine.notify_market_state(
            "BTCUSDT", _payload(direction="short", structure="down",
                                regime="range", mtf="aligned_down"), s, self.db)
        self.assertEqual(len(changes), 4)
        rows = self._outbox()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["urgent"], 1)
        self.assertEqual(rows[0]["channel"], "qq")
        self.assertIn("市场状态切换", rows[0]["text"])
        self.assertIn("不构成投资建议", rows[0]["text"])
        self.assertLess(rows[0]["plan_event_id"], 0)  # distinct from plan events

    def test_unchanged_state_does_not_push(self):
        s = _settings()
        engine.notify_market_state("BTCUSDT", _payload(), s, self.db)
        for _ in range(3):
            self.assertEqual(
                engine.notify_market_state("BTCUSDT", _payload(), s, self.db), [])
        self.assertEqual(len(self._outbox()), 0)

    def test_cooldown_suppresses_identical_switch_replay(self):
        s = _settings()
        engine.notify_market_state("BTCUSDT", _payload(), s, self.db)
        alt = _payload(direction="short")
        engine.notify_market_state("BTCUSDT", alt, s, self.db)
        engine.notify_market_state("BTCUSDT", _payload(), s, self.db)
        engine._LAST_MARKET_SIG.clear()  # simulate process restart
        engine.notify_market_state("BTCUSDT", alt, s, self.db)
        self.assertEqual(len(self._outbox()), 2)  # forward + back, no replay

    def test_restart_does_not_replay_last_switch(self):
        s = _settings()
        engine.notify_market_state("BTCUSDT", _payload(), s, self.db)
        alt = _payload(direction="short")
        engine.notify_market_state("BTCUSDT", alt, s, self.db)
        before = len(self._outbox())
        engine._LAST_MARKET_SIG.clear()  # restart
        self.assertEqual(
            engine.notify_market_state("BTCUSDT", alt, s, self.db), [])
        self.assertEqual(len(self._outbox()), before)

    def test_disabled_by_setting(self):
        s = _settings()
        s["push_state_change"] = False
        engine.notify_market_state("BTCUSDT", _payload(), s, self.db)
        self.assertEqual(
            engine.notify_market_state("BTCUSDT", _payload("short"), s, self.db), [])
        self.assertEqual(len(self._outbox()), 0)


if __name__ == "__main__":
    unittest.main()
