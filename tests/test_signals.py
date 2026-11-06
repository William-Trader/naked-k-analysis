import unittest

from nakedk.signals import signal_line, stance


def feat(**over):
    base = {
        "price": 100.0, "ema20": 99.0, "ema50": 98.0,
        "adx14": 30.0, "rsi14": 50.0, "atr14": 2.0, "atr_pct": 2.0,
        "vol_z": 0.0, "pos20": 0.5, "pos40": 0.5,
    }
    base.update(over)
    return base


class TestSignals(unittest.TestCase):
    def test_adx_below_20_forces_neutral(self):
        s = stance(feat(adx14=15.0))
        self.assertEqual(s["direction"], "neutral")

    def test_no_short_at_range_low(self):
        s = stance(feat(pos20=0.10, rsi14=50.0, price=97.0, ema20=99.0))
        self.assertEqual(s["direction"], "neutral")
        self.assertTrue(any("disabled" in r for r in s["reasons"]))

    def test_mean_reversion_long_at_range_low(self):
        s = stance(feat(pos20=0.10, rsi14=35.0, price=101.0, ema20=99.0))
        self.assertEqual(s["direction"], "long")
        self.assertLessEqual(s["confidence"], 56)

    def test_no_long_at_range_high(self):
        s = stance(feat(pos20=0.90, rsi14=50.0, price=101.0, ema20=99.0))
        self.assertEqual(s["direction"], "neutral")

    def test_mean_reversion_short_at_range_high(self):
        s = stance(feat(pos20=0.90, rsi14=65.0, price=97.0, ema20=99.0))
        self.assertEqual(s["direction"], "short")

    def test_bear_trend_emits_short_with_calibrated_grade(self):
        s = stance(feat(ema20=98.0, ema50=99.0, price=97.0, adx14=30.0))
        self.assertEqual(s["direction"], "short")
        # 2026-11-06 audit: fixed 60/64 confidence was not monotone with
        # outcomes (conf>=62 scored below baseline), so it is now a capped
        # quality grade rather than a fake probability.
        self.assertGreaterEqual(s["confidence"], 35)
        self.assertLessEqual(s["confidence"], 60)
        self.assertIn(s["grade"], ("A", "B", "C"))
        self.assertTrue(s["evidence"])
        self.assertIsNotNone(s["stop"])
        self.assertIsNotNone(s["target"])

    def test_high_overlap_vetoes_signal(self):
        # Worst measured bucket: overlap >= 0.70 -> 31.6% / 25.9% hit.
        s = stance(feat(overlap=0.75))
        self.assertEqual(s["direction"], "neutral")
        self.assertTrue(any("overlap" in r for r in s["reasons"]))

    def test_missing_volume_confirmation_vetoes_trend_entry(self):
        s = stance(feat(vol_z=-1.2))
        self.assertEqual(s["direction"], "neutral")
        self.assertTrue(any("volume confirmation" in r for r in s["reasons"]))

    def test_quality_grade_rewards_trending_volume(self):
        good = stance(feat(adx14=22.0, overlap=0.50, vol_z=1.0))
        plain = stance(feat(adx14=22.0, overlap=0.60, vol_z=0.0))
        self.assertGreater(good["confidence"], plain["confidence"])
        self.assertEqual(good["grade"], "A")

    def test_signal_line_is_machine_readable(self):
        s = stance(feat(ema20=98.0, ema50=99.0, price=97.0, adx14=30.0))
        line = signal_line("BTCUSDT", s)
        self.assertTrue(line.startswith("SIGNAL|BTC|short|4h|"))
        self.assertIn("entry=", line)


if __name__ == "__main__":
    unittest.main()
