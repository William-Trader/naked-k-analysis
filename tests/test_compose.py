import unittest

from beagle.compose import compose_event, compose_signal, plan, validate_message


class TestCompose(unittest.TestCase):
    def test_plan_rejects_low_rr(self):
        s = {"direction": "long", "entry": 100, "stop": 98, "target": 101}
        self.assertIsNone(plan(s, 100, 1.0))

    def test_plan_accepts_good_rr(self):
        s = {"direction": "long", "entry": 100, "stop": 98, "target": 105}
        p = plan(s, 100, 1.0)
        self.assertAlmostEqual(p["rr"], 2.5)
        self.assertLessEqual(p["notional_pct"], 200)

    def test_signal_card_contract(self):
        data = {
            "price": 81504.32, "direction": "short", "confidence": 62,
            "plan": {"side": "short", "entry": 81504.32, "stop": 82280.0,
                     "target": 79900.0, "rr": 2.1, "stop_pct": 0.95,
                     "risk_pct": 0.5, "notional_pct": 52.6, "ttl_h": 8,
                     "invalidate": "4h收盘> 82280"},
            "evidence": ["结构 down", "L1 反弹", "MTF -2"],
            "source": "Binance", "data_time": "2026-10-20 22:00",
        }
        text = compose_signal("BTCUSDT", data)
        self.assertIn("结论", text)
        self.assertIn("止损", text)
        self.assertIn("非投资建议", text)
        self.assertLessEqual(len(text), 900)
        self.assertTrue(validate_message(text)["ok"])

    def test_event_shape(self):
        ev = {"severity": "P1", "symbol": "BTCUSDT", "kind": "price_shock",
              "price": 81504, "payload": {"move_pct": 0.9, "atr_ratio": 1.2}}
        text = compose_event(ev)
        self.assertIn("值得留意", text)
        self.assertIn("现在怎么做", text)
        self.assertIn("非投资建议", text)
        self.assertLessEqual(len(text), 900)

    def test_event_p2_observation(self):
        ev = {"severity": "P2", "symbol": "BTCUSDT", "kind": "state_shift",
              "price": 81504, "payload": {"prev_state": "range", "state": "up"}}
        text = compose_event(ev)
        self.assertIn("仅供观察", text)
        self.assertIn("区间 → 上涨", text)
        self.assertIn("等第一次回踩", text)

    def test_range_break_plain(self):
        ev = {"severity": "P1", "symbol": "BTCUSDT", "kind": "range_break",
              "direction": "up", "price": 81350,
              "payload": {"r20_lo": 80900, "r20_hi": 81300, "vol_z": 1.8}}
        text = compose_event(ev)
        self.assertIn("80,900.00 - 81,300.00", text)
        self.assertIn("回踩", text)

    def test_volume_spike_plain(self):
        ev = {"severity": "P1", "symbol": "ETHUSDT", "kind": "volume_spike",
              "price": 3000, "payload": {"vol_z": 3.4}}
        text = compose_event(ev)
        self.assertIn("成交量突然放大", text)
        self.assertIn("别把放量当成方向", text)

    def test_validator_flags_table(self):
        self.assertFalse(validate_message("| a | b |\n结论 数据 非投资建议")["ok"])


if __name__ == "__main__":
    unittest.main()
