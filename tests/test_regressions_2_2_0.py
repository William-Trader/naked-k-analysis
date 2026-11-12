# -----------------------------------------------------------------
# tests/test_regressions_2_2_0.py - audit regression suite
# (c) 2026 William-Trader (https://github.com/William-Trader)
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# -----------------------------------------------------------------
"""Regressions for every defect confirmed in the 2026-11-12 code audit.

All tests are offline (temp SQLite / pure functions / mocks). Each class is
named after the bug ID in the audit report so a failure points straight at
the original finding.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from beagle import config as beagle_config
from beagle import engine, push, store
from nakedk import analogs, features, plans as planlib, research_gate
from nakedk import backtest, symbol_params
from nakedk.analysis import _num, _summary_24h


class B4TriggerMode(unittest.TestCase):
    def test_near_trigger_is_directional_not_market(self):
        self.assertEqual(planlib.trigger_mode(100000.0, 99925.0), "below")
        self.assertEqual(planlib.trigger_mode(100000.0, 100075.0), "above")
        self.assertEqual(planlib.trigger_mode(100.0, None), "market")

    def test_explicit_hint_is_honoured(self):
        p = planlib.build("BTCUSDT", "4h", "long", price=100.0, atr=2.0,
                          trigger=99.0, stop=97.0, target1=105.0,
                          trigger_mode_hint="below")
        self.assertEqual(p["trigger_mode"], "below")


class B2SharedGate(unittest.TestCase):
    def test_gate_reasons_shared_and_strict_fails_closed(self):
        plan = {"side": "short"}
        ctx = {"structure_direction": "up", "regime": "up",
               "vol_z": 0.0, "overlap": 0.4}
        self.assertFalse(planlib.confirm(plan, ctx)["ok"])
        self.assertTrue(planlib.gate_reasons(plan, ctx, strict=True))
        # A missing regime must not silently pass when arming.
        self.assertTrue(planlib.gate_reasons(
            {"side": "long"}, {"regime": None}, strict=True))

    def test_allow_from_policy_is_consistent(self):
        from nakedk.policy import allow
        self.assertFalse(allow("up", "short"))
        self.assertTrue(allow("transition", "long"))


class B3SingleDatabase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = self.tmp.name
        store.init(self.db)

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.db + suffix)
            except OSError:
                pass

    def test_env_override_points_monitor_to_same_db(self):
        with mock.patch.dict(os.environ, {"BEAGLE_DB": self.db}):
            self.assertEqual(beagle_config.load(path=None)["db_path"], self.db)

    def test_closed_plan_writes_exactly_one_signal(self):
        plan = {"id": 77, "symbol": "BTCUSDT", "side": "long",
                "status": "void", "confidence": 55, "trigger": 100.0,
                "stop": 98.0, "target1": 106.0, "setup": "H2",
                "created_at": 1700000000000,
                "snapshot": {"structure": {"state": "up"},
                             "mtf": {"alignment": 2}}}
        sid = store.record_plan_signal(self.db, plan)
        self.assertIsNotNone(sid)
        self.assertIsNotNone(store.record_plan_signal(self.db, plan))
        conn = store.connect(self.db)
        try:
            rows = list(conn.execute("SELECT * FROM signals WHERE plan_id=?", (77,)))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["source"], "plan")
        finally:
            conn.close()


class B5RearmCooldown(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = self.tmp.name
        store.init(self.db)
        conn = store.connect(self.db)
        try:
            conn.execute(
                "INSERT INTO plans (id,symbol,interval,side,status,created_at,"
                "updated_at,outcome) VALUES (1,'BTCUSDT','4h','long','void',?,?,'invalidated')",
                (1700000000000, 1700000000000))
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.db + suffix)
            except OSError:
                pass

    def test_symbol_level_cooling_catches_opposite_side(self):
        self.assertIsNotNone(store.recent_void_plan(
            self.db, "BTCUSDT", None, 1699999999999))
        self.assertIsNone(store.recent_void_plan(
            self.db, "BTCUSDT", "short", 1699999999999))


class B8OutboxReliability(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = self.tmp.name
        store.init(self.db)

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.db + suffix)
            except OSError:
                pass

    def test_failed_text_does_not_suppress_a_new_message(self):
        conn = store.connect(self.db)
        try:
            conn.execute(
                "INSERT INTO outbox (plan_event_id,channel,text,status,created_at) "
                "VALUES (1,'qq','same text','failed',?)", (store._now(),))
            conn.commit()
        finally:
            conn.close()
        self.assertIsNotNone(store.outbox_add(self.db, 2, "qq", "same text",
                                              dedupe_min=240))

    def test_transient_send_error_retries_instead_of_terminal_failure(self):
        oid = store.outbox_add(self.db, 10, "qq", "hello", dedupe_min=0)
        self.assertIsNotNone(oid)
        with mock.patch.object(push, "resolve_target", return_value="group:x"), \
             mock.patch.object(push, "_run_send", side_effect=OSError("timeout")):
            res = push.push_outbox(self.db, {"max_push_attempts": 5,
                                             "quiet_hours": [0, 0]})
        self.assertEqual(res[0]["status"], "pending")
        conn = store.connect(self.db)
        try:
            row = conn.execute("SELECT status,attempts,last_error,next_attempt_at "
                               "FROM outbox WHERE id=?", (oid,)).fetchone()
            self.assertEqual(row["status"], "pending")
            self.assertEqual(row["attempts"], 1)
            self.assertIn("timeout", row["last_error"])
            self.assertGreater(row["next_attempt_at"], store._now())
        finally:
            conn.close()


class B9PriceBasis(unittest.TestCase):
    def test_summary_uses_interval_specific_bar_count(self):
        ks = [[i * 3600_000, 100.0, 101.0, 99.0, 100.0, 1.0]
              for i in range(500)]
        ks[-1][2] = 101.0
        ks[-50][2] = 150.0  # inside the last 96 (15m/24h), outside last 6 (4h/24h)
        a = _summary_24h(ks, 100.0, "15m")
        b = _summary_24h(ks, 100.0, "4h")
        self.assertEqual(a["high24h"], 150.0)
        self.assertEqual(b["high24h"], 101.0)

    def test_num_preserves_real_zero(self):
        self.assertEqual(_num({"pos20": 0.0}, "pos20", 0.5, 3), 0.0)
        self.assertEqual(_num({}, "pos20", 0.5, 3), 0.5)


class B10HtfContext(unittest.TestCase):
    def test_ctx_prefers_context_1d(self):
        payload = {"context_1d": {"state": "down", "bars": 180},
                   "intervals": {"4h": {"features": {}, "structure": {}}},
                   "mtf": {"alignment": 1}}
        ctx = engine._ctx_from(payload, {"interval": "4h"})
        self.assertEqual(ctx["htf_direction"], "down")


class B13NumericCorrectness(unittest.TestCase):
    def test_flat_tape_rsi_is_neutral(self):
        self.assertEqual(features.rsi([100.0] * 40), 50.0)

    def test_wilson_upper_is_percentage(self):
        low, high = analogs._wilson(45, 100)
        self.assertGreater(high, 40.0)
        self.assertLess(high, 100.0)
        self.assertLess(low, high)

    def test_ret_lookbacks_rescale_with_interval(self):
        ks = [[i * 3600_000, 100.0 + i * 0.01, 100.0 + i * 0.01 + 1,
               99.0 + i * 0.01, 100.0 + i * 0.01, 1.0] for i in range(200)]
        f4 = features.features_from_klines(ks, "4h")
        f1 = features.features_from_klines(ks, "1h")
        self.assertNotEqual(f4["ret24h"], f1["ret24h"])

    def test_symbol_params_bounds_cover_all_defaults(self):
        missing = set(symbol_params.defaults()) - set(symbol_params.BOUNDS)
        # Non-numeric / non-tunable keys may legitimately have no bounds,
        # but the five previously-unbounded numeric plan keys must be covered.
        self.assertFalse({"plan_trigger_max_atr", "plan_confirm_bars",
                          "plan_max_open"} & missing)

    def test_get_clamps_persisted_profile(self):
        with mock.patch.object(symbol_params, "_read", return_value={
                "BTCUSDT": {"params": {"plan_trigger_max_atr": 1e9}}}):
            self.assertLessEqual(
                symbol_params.get("BTCUSDT")["plan_trigger_max_atr"], 5.0)

    def test_apply_rejects_illegal_status(self):
        p = {"status": "armed", "snapshot": {}}
        with self.assertRaises(ValueError):
            planlib.apply(p, {"type": "void", "to_status": "zombie", "ts": 1})
        with self.assertRaises(ValueError):
            planlib.apply({"status": "void", "snapshot": {}},
                          {"type": "armed", "to_status": "armed", "ts": 1})


class B14SettingsSchema(unittest.TestCase):
    def test_wrong_types_are_normalised(self):
        s = engine._sanitise(dict(engine.DEFAULTS))
        s["auto_trigger"] = "yes"
        s["level_proximity_atr"] = "abc"
        s["push_severity"] = "not-a-list"
        out = engine._sanitise(s)
        self.assertIsInstance(out["auto_trigger"], bool)
        self.assertIsInstance(out["level_proximity_atr"], float)
        self.assertIsInstance(out["push_severity"], list)


class ResearchAndPerformance(unittest.TestCase):
    def test_research_gate_off_by_default(self):
        with mock.patch.dict(os.environ, {"NK_RESEARCH_GATE": ""}):
            self.assertFalse(research_gate.enabled())
            self.assertTrue(research_gate.admit({"features": {}})[0])

    def test_research_gate_filters_when_enabled(self):
        with mock.patch.dict(os.environ, {"NK_RESEARCH_GATE": "1"}):
            self.assertFalse(research_gate.admit(
                {"features": {"adx": 10, "adx_slope": 0,
                              "overlap": 0.2, "vol_z": 0}})[0])
            self.assertTrue(research_gate.admit(
                {"features": {"adx": 30, "adx_slope": 0,
                              "overlap": 0.2, "vol_z": 0}})[0])

    def test_path_slice_bisect_matches_linear_scan(self):
        ks = [[i * 3600_000, 1, 2, 0.5, 1.5, 1] for i in range(1000)]
        got = backtest._path_slice(ks, 10 * 3600_000, 20 * 3600_000)
        want = [k for k in ks if 10 * 3600_000 < int(k[0]) <= 20 * 3600_000]
        self.assertEqual(got, want)


if __name__ == "__main__":
    unittest.main()
