"""Tests for the conditional edge module (order-flow/funding/OI conditions)."""
from __future__ import annotations

import unittest

from nakedk.conditional import (classify_flow, classify_funding, classify_oi,
                                conditions, build_flow_prob)


class ClassifyFlowTest(unittest.TestCase):
    def test_bearish_divergence(self):
        self.assertEqual(classify_flow(1.0, -0.3), "bearish")

    def test_bullish_divergence(self):
        self.assertEqual(classify_flow(-1.0, 0.3), "bullish")

    def test_none(self):
        self.assertEqual(classify_flow(0.1, 0.0), "none")


class ClassifyFundingTest(unittest.TestCase):
    def test_extreme_long(self):
        self.assertEqual(classify_funding(0.15), "extreme_long")

    def test_extreme_short(self):
        self.assertEqual(classify_funding(-0.2), "extreme_short")

    def test_neutral_and_unknown(self):
        self.assertEqual(classify_funding(0.05), "neutral")
        self.assertEqual(classify_funding(None), "unknown")


class ClassifyOiTest(unittest.TestCase):
    def test_short_covering(self):
        self.assertEqual(classify_oi(1.0, -2.0), "short_covering")

    def test_new_shorts(self):
        self.assertEqual(classify_oi(-1.0, 2.0), "new_shorts")

    def test_unknown(self):
        self.assertEqual(classify_oi(0.0, None), "unknown")


class ConditionsTest(unittest.TestCase):
    def test_combines_three(self):
        c = conditions({"price": 1.0},
                       {"price_chg": 1.0, "cum_delta": -0.3},
                       {"funding_rate": 0.15, "oi_change_24h": -2.0})
        self.assertEqual(c, {"flow": "bearish", "funding": "extreme_long",
                             "oi": "short_covering"})

    def test_empty_inputs(self):
        c = conditions({"price": 1.0})
        self.assertEqual(c, {"flow": "none", "funding": "unknown",
                             "oi": "unknown"})


class BuildFlowProbTest(unittest.TestCase):
    def _ks(self, n=120, trend=0.01):
        out = []
        price = 100.0
        for i in range(n):
            o = price
            c = price + trend
            h = max(o, c) + 0.2
            lo = min(o, c) - 0.2
            v = 100.0 + i
            out.append([i * 1000, o, h, lo, c, v, 0, 0, 0, v / 2])
            price = c
        return out

    def test_builds_table(self):
        table = build_flow_prob(self._ks(), horizon=1, warmup=20, lookback=100)
        self.assertIsInstance(table, dict)
        # every bucket carries a wilson interval
        for row in table.values():
            self.assertIn("wilson_up", row)
            self.assertIn("p_up", row)

    def test_empty_on_tiny_sample(self):
        self.assertEqual(build_flow_prob(self._ks(5)), {})


if __name__ == "__main__":
    unittest.main()
