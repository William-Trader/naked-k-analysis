"""Engine plan construction from an analysis payload (no network)."""
from __future__ import annotations

import unittest

from beagle import engine
from beagle.engine import build_plan


def payload(direction="long", conf=62):
    return {
        "symbol": "BTCUSDT", "price": 100.0,
        "interval_order": ["4h", "15m"],
        "combined": {"direction": direction, "confidence": conf, "grade": "A",
                     "agreement": "aligned", "reasons": ["test"]},
        "mtf": {"alignment": 2, "label": "aligned_up"},
        "intervals": {
            "4h": {
                "interval": "4h", "price": 100.0,
                "features": {"atr": 2.0, "ema20": 99.0},
                "stance": {"direction": direction, "confidence": conf,
                           "target": 108.0, "stop": 95.0, "reasons": ["trend"]},
                "structure": {"state": "up", "levels": {"swing_low": 97.0}},
                "primary_pattern": {"type": "H2", "target": 109.0},
            }
        },
    }


class BuildPlanTest(unittest.TestCase):
    def test_long_plan_has_valid_geometry(self):
        params = {"plan_min_confidence": 52, "plan_min_rr": 1.5,
                  "plan_ttl_h": 12, "plan_trigger_max_atr": 1.5,
                  "stance_stop_atr": 1.5, "stance_target_atr": 3.0}
        p = build_plan("BTCUSDT", payload(), params, {})
        self.assertIsNotNone(p)
        self.assertEqual(p["side"], "long")
        self.assertLess(p["stop"], p["trigger"])
        self.assertGreater(p["target1"], p["trigger"])
        self.assertGreaterEqual(p["rr"], 1.5)
        self.assertEqual(p["status"], "armed")

    def test_neutral_returns_none(self):
        params = {"plan_min_confidence": 52}
        self.assertIsNone(build_plan("BTCUSDT", payload("neutral"), params, {}))

    def test_low_confidence_returns_none(self):
        params = {"plan_min_confidence": 52}
        self.assertIsNone(build_plan("BTCUSDT", payload(conf=45), params, {}))


if __name__ == "__main__":
    unittest.main()


class AdviceTest(unittest.TestCase):
    def plan(self):
        return {
            "symbol": "BTCUSDT", "interval": "4h", "side": "long",
            "status": "confirmed", "trigger": 75600, "stop": 74900,
            "target1": 76900, "target2": 77800, "rr": 2.1, "atr": 900,
            "confidence": 58, "grade": "B",
            "snapshot": {"reasons": ["EMA20 > EMA50"]},
        }

    def test_confirmed_advice_is_actionable(self):
        a = engine.plan_advice(self.plan(), {"type": "confirmed", "price": 75650},
                               {"name": "BTC/USDT", "price": 75650})
        self.assertIn("可轻仓做多", a["action"])
        self.assertIn("操作：", "\n".join(a["lines"]))
        self.assertIn("BTC/USDT", a["headline"])

    def test_far_from_trigger_does_not_chase(self):
        a = engine.plan_advice(self.plan(), {"type": "confirmed", "price": 77000},
                               {"name": "BTC/USDT", "price": 77000})
        self.assertIn("不追", a["action"])

    def test_tp1_and_stop_language(self):
        tp1 = engine.plan_advice(self.plan(), {"type": "tp1", "price": 76900},
                                 {"name": "BTC/USDT"})
        self.assertIn("减仓 50%", tp1["action"])
        stop = engine.plan_advice(self.plan(), {"type": "stopped", "price": 74890},
                                  {"name": "BTC/USDT"})
        self.assertIn("离场", stop["action"])

    def test_plan_text_is_short_and_readable(self):
        txt = engine._plan_text(self.plan(), {"type": "confirmed", "price": 75650},
                                {"name": "BTC/USDT", "price": 75650,
                                 "source": "Binance", "data_ts": 1_794_000_000_000})
        self.assertLessEqual(len(txt), 700)
        self.assertIn("操作：", txt)
        self.assertIn("非投资建议", txt)


class TargetTest(unittest.TestCase):
    def test_settings_target_wins(self):
        from beagle import push
        self.assertEqual(push.resolve_target({"qq_target": "12345"}, "x.db"),
                         "12345")


if __name__ == "__main__":
    unittest.main()
