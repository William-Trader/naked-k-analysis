import os
import tempfile
import unittest

from nakedk import always_in as ai
from nakedk.legs import decompose, exhaustion, maturity
from nakedk.quality import gates
from nakedk.trades import absorption, sweeps


class TestAlwaysIn(unittest.TestCase):
    def test_min_hold_blocks_flip(self):
        state, reason = ai.next_state("short", "bullish", True, 110, 100, 1)
        self.assertEqual(state, "short")
        self.assertEqual(reason, "hold_min")

    def test_flip_on_bos_and_follow(self):
        state, reason = ai.next_state("short", "bullish", True, 110, 100, 5)
        self.assertEqual(state, "long")
        self.assertEqual(reason, "bos_up")

    def test_persist_roundtrip(self):
        path = os.path.join(tempfile.mkdtemp(), "ai.db")
        out = ai.update(path, "BTCUSDT", "bullish", True, 110, 100, 1_000_000)
        self.assertEqual(out["state"], "long")
        again = ai.update(path, "BTCUSDT", "bearish", True, 90, 100, 1_000_000 + 4 * 14_400_000)
        self.assertEqual(again["state"], "short")


class TestLegs(unittest.TestCase):
    def test_maturity_and_exhaustion(self):
        legs = [{"dir": "up", "delta_atr": 3.0}, {"dir": "up", "delta_atr": 1.0}]
        self.assertEqual(maturity(legs), 2)
        self.assertTrue(exhaustion(legs))

    def test_empty(self):
        self.assertEqual(maturity([]), 0)
        self.assertFalse(exhaustion([]))


class TestQuality(unittest.TestCase):
    def test_gap_and_stale(self):
        ks = [[0, "1", "1", "1", "1", "1"], [2 * 14_400_000, "1", "1", "1", "1", "1"]]
        out = gates(ks, 14_400_000, 2 * 14_400_000 + 1000)
        self.assertFalse(out["ok"])
        self.assertTrue(any("gap" in x for x in out["issues"]))

    def test_clean(self):
        ks = [[i * 14_400_000, "1", "1", "1", "1", "1"] for i in range(5)]
        out = gates(ks, 14_400_000, 4 * 14_400_000 + 1000)
        self.assertTrue(out["ok"])


class TestSweeps(unittest.TestCase):
    def _rows(self, n, side_buy=True, price=100.0, qty=1.0, step=1000):
        return [{"p": str(price), "q": str(qty), "m": not side_buy,
                 "T": i * step} for i in range(n)]

    def test_sweep_detected(self):
        rows = self._rows(10, True, 100.0, 2.0, 500)
        rows[-1]["p"] = "101"
        out = sweeps(rows, atr_value=1.0)
        self.assertTrue(out)
        self.assertEqual(out[0]["side"], "buy")

    def test_absorption(self):
        rows = self._rows(6, True, 100.0, 10.0, 1000)
        self.assertIsNotNone(absorption(rows, 1.0, 0.2))


if __name__ == "__main__":
    unittest.main()
