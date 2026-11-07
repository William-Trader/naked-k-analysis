"""Engine plan construction from an analysis payload (no network)."""
from __future__ import annotations

import unittest

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
