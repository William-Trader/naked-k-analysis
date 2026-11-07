"""Multi-interval combination tests."""
from __future__ import annotations

import unittest

from nakedk.multi import combine


def iv(direction, conf=56, structure="up"):
    return {"stance": {"direction": direction, "confidence": conf, "grade": "B"},
            "trend": {"score": 60}, "structure": {"state": structure}}


class CombineTest(unittest.TestCase):
    def test_aligned_long_raises_confidence(self):
        c = combine({"4h": iv("long", 58), "15m": iv("long", 56)})
        self.assertEqual(c["direction"], "long")
        self.assertEqual(c["agreement"], "aligned")
        self.assertGreaterEqual(c["confidence"], 52)

    def test_conflict_caps_and_neutralises(self):
        c = combine({"4h": iv("long", 58), "15m": iv("short", 58)})
        self.assertEqual(c["direction"], "neutral")
        self.assertEqual(c["agreement"], "conflict")
        self.assertLessEqual(c["confidence"], 55)

    def test_high_timeframe_veto(self):
        c = combine({"4h": iv("short", 60, "down"), "15m": iv("long", 62, "up")})
        self.assertEqual(c["direction"], "neutral")
        self.assertTrue(c["conflict"])

    def test_single_mode(self):
        c = combine({"4h": iv("short", 54, "down")}, mode="single")
        self.assertEqual(c["direction"], "short")
        self.assertEqual(c["agreement"], "single")

    def test_empty(self):
        c = combine({})
        self.assertEqual(c["direction"], "neutral")
        self.assertEqual(c["intervals"], [])


if __name__ == "__main__":
    unittest.main()
