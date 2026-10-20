import unittest

from nakedk.signalbar import score


def bar(**kw):
    base = {"close_pos": 0.85, "body_ratio": 0.7, "lower_tail": 0.05,
            "upper_tail": 0.25, "vol_z": 2.0, "o": 100, "c": 108, "type": "trend_bull"}
    base.update(kw)
    return base


class TestSignalBar(unittest.TestCase):
    def test_strong_bull_scores_high(self):
        s = score(bar(), bar(), "long", pos20=0.2)
        self.assertGreaterEqual(s["score"], 60)
        self.assertEqual(s["missing"], [])

    def test_weak_bar_has_missing(self):
        s = score(bar(close_pos=0.3, body_ratio=0.1, lower_tail=0.5), None, "long")
        self.assertLess(s["score"], 40)
        self.assertTrue(s["missing"])

    def test_direction_asymmetry(self):
        b = bar(close_pos=0.9, upper_tail=0.05, lower_tail=0.3)
        long_s = score(b, bar(), "long", 0.2)["score"]
        short_s = score(b, bar(), "short", 0.8)["score"]
        self.assertGreater(long_s, short_s)

    def test_empty(self):
        self.assertEqual(score({}, None, "long")["score"], 0)


if __name__ == "__main__":
    unittest.main()
