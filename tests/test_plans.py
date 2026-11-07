"""Plan lifecycle state machine tests (pure, no network)."""
from __future__ import annotations

import unittest

from nakedk import plans


def make_plan(**over):
    p = plans.build(
        "BTCUSDT", "4h", "long", price=100.0, atr=2.0,
        trigger=99.0, stop=96.0, target1=106.0, target2=109.0,
        setup="H2", confidence=58, grade="B", now_ms=1_700_000_000_000,
        ttl_h=12, min_rr=1.5)
    assert p is not None
    p["id"] = 7
    p.update(over)
    return p


class BuildTest(unittest.TestCase):
    def test_long_geometry(self):
        p = make_plan()
        self.assertEqual(p["side"], "long")
        self.assertEqual(p["trigger_mode"], "below")
        self.assertEqual(p["status"], "armed")
        self.assertAlmostEqual(p["rr"], 2.33)

    def test_rejects_bad_rr_and_inverted_levels(self):
        self.assertIsNone(plans.build(
            "X", "4h", "long", price=100, atr=1, trigger=100,
            stop=98, target1=100.5, min_rr=1.5))
        self.assertIsNone(plans.build(
            "X", "4h", "long", price=100, atr=1, trigger=100,
            stop=101, target1=110))

    def test_short_geometry(self):
        p = plans.build("X", "4h", "short", price=100, atr=2, trigger=101,
                        stop=104, target1=95, min_rr=1.5)
        self.assertIsNotNone(p)
        self.assertEqual(p["trigger_mode"], "above")


class EvaluateTest(unittest.TestCase):
    def test_armed_triggers_on_pullback(self):
        p = make_plan()
        ev = plans.evaluate(p, 99.0, 1_700_000_100_000)
        self.assertEqual(ev["type"], "triggered")
        self.assertEqual(ev["to_status"], "triggered")

    def test_armed_does_not_trigger_far_away(self):
        self.assertIsNone(plans.evaluate(make_plan(), 103.0, 1_700_000_100_000))

    def test_triggered_void_on_stop(self):
        p = plans.apply(make_plan(), {
            "type": "triggered", "ts": 1_700_000_100_000, "to_status": "triggered"})
        ev = plans.evaluate(p, 95.9, 1_700_000_200_000)
        self.assertEqual(ev["type"], "void")
        self.assertEqual(ev["reason"], "stopped_before_confirm")

    def test_confirmed_tp1_moves_stop_to_breakeven(self):
        p = plans.apply(make_plan(), {
            "type": "triggered", "ts": 1_700_000_100_000, "to_status": "triggered"})
        p = plans.apply(p, {"type": "confirmed", "ts": 1_700_000_200_000,
                            "to_status": "confirmed"})
        ev = plans.evaluate(p, 106.2, 1_700_000_300_000)
        self.assertEqual(ev["type"], "tp1")
        p2 = plans.apply(p, ev)
        self.assertEqual(p2["status"], "managing")
        self.assertEqual(p2["stop"], p["trigger"])
        self.assertTrue(p2["breakeven"])

    def test_target2_closes(self):
        p = make_plan(status="confirmed")
        ev = plans.evaluate(p, 109.5, 1_700_000_400_000)
        self.assertEqual(ev["type"], "tp2")
        p2 = plans.apply(p, ev)
        self.assertEqual(p2["status"], "closed")
        self.assertEqual(p2["outcome"], "target2")
        self.assertGreater(p2["pnl_pct"], 0)

    def test_expiry(self):
        p = make_plan(ttl_at=1_700_000_000_500)
        ev = plans.evaluate(p, 100.0, 1_700_000_001_000)
        self.assertEqual(ev["type"], "expired")
        self.assertEqual(ev["to_status"], "void")


class ConfirmTest(unittest.TestCase):
    def test_blocks_opposite_structure(self):
        d = plans.confirm(make_plan(), {"structure_direction": "down"})
        self.assertFalse(d["ok"])
        self.assertTrue(d["reasons"])

    def test_allows_clean_context(self):
        d = plans.confirm(make_plan(), {
            "structure_direction": "up", "htf_direction": "up",
            "mtf_alignment": 3, "regime": "transition", "vol_z": 1.2, "overlap": 0.3})
        self.assertTrue(d["ok"])

    def test_blocks_overlap(self):
        d = plans.confirm(make_plan(), {"overlap": 0.8})
        self.assertFalse(d["ok"])


class KeyTest(unittest.TestCase):
    def test_idempotency_key_is_stable_per_minute(self):
        p = make_plan()
        a = plans.event_key(p, {"type": "triggered", "ts": 1_700_000_100_000})
        b = plans.event_key(p, {"type": "triggered", "ts": 1_700_000_100_900})
        c = plans.event_key(p, {"type": "triggered", "ts": 1_700_000_160_000})
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)


if __name__ == "__main__":
    unittest.main()
