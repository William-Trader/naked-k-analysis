import unittest

from nakedk.bars import closed_bars, profile_series


def K(ts, o, h, l, c, v=100.0):
    return [ts, str(o), str(h), str(l), str(c), str(v)]


class TestBars(unittest.TestCase):
    def test_close_position_and_body(self):
        ks = [K(0, 100, 110, 98, 108), K(1, 108, 112, 107, 111)]
        rows = profile_series(ks)
        last = rows[-1]
        self.assertAlmostEqual(last["body_ratio"], round(3 / 5, 3))
        self.assertAlmostEqual(last["close_pos"], round(4 / 5, 3))

    def test_doji_and_trend_types(self):
        ks = [K(0, 100, 110, 98, 100.2), K(0, 100, 120, 99, 119)]
        rows = profile_series(ks)
        self.assertEqual(rows[0]["type"], "doji")
        self.assertEqual(rows[1]["type"], "trend_bull")

    def test_inside_outside(self):
        ks = [K(0, 100, 110, 90, 105), K(0, 102, 108, 95, 104),
              K(0, 103, 112, 94, 111)]
        rows = profile_series(ks)
        self.assertEqual(rows[1]["type"], "inside")
        self.assertEqual(rows[2]["type"], "outside")

    def test_closed_bars_drops_forming(self):
        ks = [K(0, 1, 2, 0.5, 1.5), K(14_400_000, 1, 2, 0.5, 1.6)]
        self.assertEqual(len(closed_bars(ks, "4h", now_ms=14_400_000 + 10)), 1)
        self.assertEqual(len(closed_bars(ks, "4h", now_ms=28_800_000)), 2)


if __name__ == "__main__":
    unittest.main()
