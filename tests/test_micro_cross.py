import unittest

from nakedk.cross import analyse as cross_analyse, correlation
from nakedk.micro import analyse as micro_analyse
from nakedk.volstruct import analyse as vol_analyse


def K(c, h=None, l=None):
    h = h if h is not None else c + 1
    l = l if l is not None else c - 1
    return [0, str(c), str(h), str(l), str(c), "100"]


class TestCross(unittest.TestCase):
    def test_correlation_identical(self):
        a = [0.01, -0.02, 0.03, 0.0, 0.01, -0.01, 0.02, 0.01, -0.03, 0.02, 0.0]
        self.assertAlmostEqual(correlation(a, a), 1.0, places=6)

    def test_analyse_keys(self):
        ks = [K(100 + i) for i in range(40)]
        out = cross_analyse(ks, ks, ks)
        self.assertIn("corr_30d", out)
        self.assertIn("relative_strength", out)


class TestVolStruct(unittest.TestCase):
    def test_percentile_bounds(self):
        closes = [100 + i * 0.1 for i in range(80)]
        highs = [c + 1 for c in closes]
        lows = [c - 1 for c in closes]
        out = vol_analyse(highs, lows, closes)
        self.assertGreaterEqual(out["atr_percentile"], 0)
        self.assertLessEqual(out["atr_percentile"], 100)
        self.assertIn(out["state"], ("expansion", "contraction", "normal"))


class TestMicro(unittest.TestCase):
    def test_uptrend(self):
        ks = [K(100 + i * 0.5) for i in range(80)]
        out = micro_analyse(ks, ks)
        self.assertEqual(out["sign5m"], 1)
        self.assertIn(out["state5m"], ("up", "down", "range", "transition"))


if __name__ == "__main__":
    unittest.main()
