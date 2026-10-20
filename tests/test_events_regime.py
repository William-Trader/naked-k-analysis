import unittest

from nakedk.events import failed_break, follow_through
from nakedk.regime import arbitrate


def K(o, h, l, c):
    return [0, str(o), str(h), str(l), str(c), "100"]


class TestEvents(unittest.TestCase):
    def test_failed_break_up(self):
        ks = [K(100, 101, 99, 100) for _ in range(20)]
        ks.append(K(100, 106, 100, 103))     # break + long upper wick
        ks.append(K(103, 103, 100, 100.2))   # close back inside
        out = failed_break(ks, atr_value=1.0, lookback=20, confirm_bars=2)
        self.assertIsNotNone(out)
        self.assertEqual(out["kind"], "failed_break_up")

    def test_follow_through(self):
        ks = [K(100, 101, 99, 100), K(101, 103, 100.5, 102.8)]
        self.assertTrue(follow_through(ks, "long")["ok"])
        self.assertFalse(follow_through(ks, "short")["ok"])


class TestRegime(unittest.TestCase):
    def test_agree(self):
        out = arbitrate("up", "up", 2, adx=30, adx_slope=3, overlap=0.3)
        self.assertEqual(out["regime"], "up")
        self.assertFalse(out["conflict"])

    def test_conflict(self):
        out = arbitrate("up", "down", 2, adx=30, overlap=0.3)
        self.assertEqual(out["regime"], "transition")
        self.assertTrue(out["conflict"])

    def test_range_when_no_structure(self):
        out = arbitrate(None, None, 0, adx=15, overlap=0.7)
        self.assertEqual(out["regime"], "range")


if __name__ == "__main__":
    unittest.main()
