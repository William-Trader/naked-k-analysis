"""Per-instrument parameter library tests (isolated temp store)."""
from __future__ import annotations

import os
import tempfile
import unittest

from nakedk import symbol_params


class ProfileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="nk-params-")
        self.path = os.path.join(self.tmp, "profiles.json")

    def test_default_effective_matches_global(self):
        p = symbol_params.get("BTCUSDT")
        self.assertIn("stance_adx_trend", p)
        self.assertIn("plan_min_rr", p)

    def test_save_merges_and_clamps(self):
        symbol_params.save("BTCUSDT", {
            "stance_adx_trend": 999,       # clamped to 35
            "stance_stop_atr": 2.0,
            "unknown_key": 1,
        }, source="manual", path=self.path)
        p = symbol_params.get("BTCUSDT", path=self.path)
        self.assertEqual(p["stance_adx_trend"], 35.0)
        self.assertEqual(p["stance_stop_atr"], 2.0)
        prof = symbol_params.profile("BTCUSDT", path=self.path)
        self.assertEqual(prof["version"], 1)
        self.assertEqual(prof["source"], "manual")
        self.assertNotIn("unknown_key", prof["params"])

    def test_validate_patch(self):
        errs = symbol_params.validate_patch({"stance_stop_atr": 99, "nope": 1})
        self.assertEqual(len(errs), 2)

    def test_revert(self):
        symbol_params.save("BTCUSDT", {"stance_stop_atr": 2.2}, path=self.path)
        symbol_params.revert("BTCUSDT")
        p = symbol_params.get("BTCUSDT")
        self.assertAlmostEqual(p["stance_stop_atr"], 1.5)


class PlanDefaultsTest(unittest.TestCase):
    def test_plan_defaults_present(self):
        d = symbol_params.defaults()
        for k in ("plan_min_confidence", "plan_min_rr", "plan_ttl_h",
                  "plan_trigger_max_atr"):
            self.assertIn(k, d)


if __name__ == "__main__":
    unittest.main()
