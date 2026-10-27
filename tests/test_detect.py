import unittest

from beagle.detect import alert_text, detect_events


def feat(**over):
    base = {"price": 1000.0, "atr14": 100.0, "r20_lo": 900.0,
            "r20_hi": 1050.0, "trend": "down", "adx14": 30.0, "pos20": 0.4}
    base.update(over)
    return base


class TestDetect(unittest.TestCase):
    def test_price_shock_p1(self):
        ev = detect_events("BTCUSDT", feat(), 1005.0, 1000.0, 0.0)
        kinds = [e["kind"] for e in ev]
        self.assertIn("price_shock", kinds)
        self.assertEqual(next(e for e in ev if e["kind"] == "price_shock")["severity"], "P1")

    def test_extreme_shock_p0(self):
        ev = detect_events("BTCUSDT", feat(), 1020.0, 1000.0, 0.0)
        self.assertIn("price_shock_extreme", [e["kind"] for e in ev])

    def test_volume_spike(self):
        ev = detect_events("BTCUSDT", feat(), 1000.0, 1000.0, 6.0, vol_ratio_1m=4.0)
        self.assertIn("volume_spike", [e["kind"] for e in ev])

    def test_volume_requires_ratio(self):
        ev = detect_events("BTCUSDT", feat(), 1000.0, 1000.0, 10.0, vol_ratio_1m=1.5)
        self.assertNotIn("volume_spike", [e["kind"] for e in ev])

    def test_volume_p2_between(self):
        ev = detect_events("BTCUSDT", feat(), 1000.0, 1000.0, 6.0, vol_ratio_1m=3.5)
        v = [e for e in ev if e["kind"] == "volume_spike"][0]
        self.assertEqual(v["severity"], "P2")

    def test_volume_p1_high(self):
        ev = detect_events("BTCUSDT", feat(), 1000.0, 1000.0, 8.0, vol_ratio_1m=6.0)
        v = [e for e in ev if e["kind"] == "volume_spike"][0]
        self.assertEqual(v["severity"], "P1")

    def test_range_break_up(self):
        ev = detect_events("BTCUSDT", feat(), 1100.0, 1090.0, 1.5)
        self.assertIn("range_break", [e["kind"] for e in ev])

    def test_no_break_without_volume(self):
        ev = detect_events("BTCUSDT", feat(), 1100.0, 1090.0, 0.2)
        self.assertNotIn("range_break", [e["kind"] for e in ev])

    def test_state_shift(self):
        ev = detect_events("BTCUSDT", feat(trend="down"), 1000.0, 1000.0, 0.0, prev_state="up")
        self.assertIn("state_shift", [e["kind"] for e in ev])

    def test_funding_extreme(self):
        ev = detect_events("BTCUSDT", feat(), 1000.0, 1000.0, 0.0, funding=0.002)
        self.assertIn("funding_extreme", [e["kind"] for e in ev])

    def test_alert_text_contains_price(self):
        ev = detect_events("BTCUSDT", feat(), 1090.0, 1000.0, 0.0)[0]
        self.assertIn("BTCUSDT", alert_text(ev))
        self.assertIn("price=", alert_text(ev))


if __name__ == "__main__":
    unittest.main()
