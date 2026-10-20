import unittest

from nakedk.flow import analyse, classify, delta_series


def K(v, buy, c=100.0, h=101.0, l=99.0, o=100.0):
    return [0, str(o), str(h), str(l), str(c), str(v), "0", "0", "1", str(buy)]


class TestFlow(unittest.TestCase):
    def test_delta_series(self):
        ks = [K(100, 70), K(100, 50)]
        self.assertAlmostEqual(delta_series(ks)[0], 0.4, places=6)
        self.assertAlmostEqual(delta_series(ks)[1], 0.0, places=6)

    def test_analyse_divergence(self):
        ks = [K(100, 50, c=100 + i) for i in range(10)] + [K(100, 30, c=110)]
        out = analyse(ks, lookback=10)
        self.assertLess(out["cum_delta"], 0)
        self.assertEqual(out["divergence"], "bearish")

    def test_classify_absorption(self):
        bar = {"vol_z": 2.0, "body_ratio": 0.2, "range_atr": 0.9}
        self.assertEqual(classify(bar, 0.2), "absorption_buy")
        self.assertEqual(classify(bar, -0.2), "absorption_sell")

    def test_classify_sweep(self):
        bar = {"vol_z": 0.5, "body_ratio": 0.7, "range_atr": 1.5}
        self.assertEqual(classify(bar, 0.5), "sweep_buy")


if __name__ == "__main__":
    unittest.main()
