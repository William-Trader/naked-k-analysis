import math
import unittest

from nakedk.features import (adx, atr, ema, pct_change, range_position,
                             rsi, swing_points, volume_z)


class TestFeatures(unittest.TestCase):
    def test_ema_constant_series(self):
        self.assertAlmostEqual(ema([5.0] * 200, 20), 5.0)

    def test_ema_reacts_to_jump(self):
        self.assertGreater(ema([1.0] * 50 + [2.0], 10), 1.0)

    def test_rsi_rising_is_100(self):
        self.assertAlmostEqual(rsi(list(range(1, 60)), 14), 100.0)

    def test_rsi_falling_is_0(self):
        self.assertAlmostEqual(rsi(list(range(60, 1, -1)), 14), 0.0)

    def test_atr_constant_range(self):
        highs = [10.0] * 60
        lows = [9.0] * 60
        closes = [9.5] * 60
        self.assertAlmostEqual(atr(highs, lows, closes, 14), 1.0)

    def test_range_position(self):
        lo, hi, pos = range_position([10, 20, 30], [0, 5, 10], [15, 25, 20], 3)
        self.assertEqual((lo, hi), (0.0, 30.0))
        self.assertAlmostEqual(pos, 20.0 / 30.0)

    def test_volume_z(self):
        vols = [100.0 + (i % 7) for i in range(41)] + [200.0]
        self.assertGreater(volume_z(vols, 42), 3.0)

    def test_pct_change(self):
        self.assertAlmostEqual(pct_change([100, 110], 1), 10.0)

    def test_swing_points(self):
        highs = [1, 2, 3, 2, 1, 2, 4, 2, 1]
        lows = [0, 1, 2, 1, 0, 1, 3, 1, 0]
        sh, sl = swing_points(highs, lows, window=1, keep=2)
        self.assertIn(3.0, sh)
        self.assertIn(4.0, sh)


if __name__ == "__main__":
    unittest.main()
