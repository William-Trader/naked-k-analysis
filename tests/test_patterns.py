import unittest

from nakedk.patterns import arbitrate, detect


def feat(**over):
    base = {"price": 100.0, "ema20": 99.0, "ema50": 98.0, "adx14": 30.0,
            "rsi14": 50.0, "atr14": 2.0, "vol_z": 0.0, "pos20": 0.5}
    base.update(over)
    return base


def bars(prices):
    # build OHLC rows: [openTime, open, high, low, close, volume, closeTime]
    out = []
    for i, c in enumerate(prices):
        o = prices[i - 1] if i else c
        h = max(o, c) + 0.5
        l = min(o, c) - 0.5
        out.append([i * 3600000, o, h, l, c, 100.0, (i + 1) * 3600000 - 1])
    return out


class TestPatterns(unittest.TestCase):
    def test_detect_returns_list(self):
        ks = bars([100 + i * 0.2 for i in range(60)])
        pats = detect(ks, feat())
        self.assertIsInstance(pats, list)

    def test_arbitrate_picks_primary(self):
        ks = bars([100 + i * 0.2 for i in range(60)])
        pats = detect(ks, feat())
        arb = arbitrate(pats, feat())
        self.assertIn("context", arb)
        self.assertIn("patterns", arb)
        if arb["primary"]:
            self.assertEqual(arb["primary"]["role"], "primary")

    def test_quality_in_range(self):
        ks = bars([100 + i * 0.2 for i in range(60)])
        for p in detect(ks, feat()):
            self.assertGreaterEqual(p["quality"], 0)
            self.assertLessEqual(p["quality"], 100)


if __name__ == "__main__":
    unittest.main()
