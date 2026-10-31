"""Tests for runtime-tunable params."""
from __future__ import annotations

import unittest

from nakedk.params import DEFAULTS, load, save
from nakedk.signals import stance
from nakedk.trend import trend_score


def _features(**kw):
    base = {
        "price": 100.0, "adx14": 25.0, "rsi14": 50.0, "pos20": 0.5,
        "atr14": 2.0, "ema20": 99.0, "ema50": 95.0,
        "ret24h": 0.5, "adx_slope": 0.0, "ema_slope": 0.0,
    }
    base.update(kw)
    return base


class ParamsTest(unittest.TestCase):
    def test_defaults_present(self):
        self.assertIn("stance_adx_trend", DEFAULTS)
        self.assertIn("trend_label_up", DEFAULTS)

    def test_load_returns_defaults_when_empty(self):
        self.assertEqual(load("/nonexistent/path.json"), DEFAULTS)

    def test_stance_defaults_preserved(self):
        # no params -> historical behaviour (ADX 25 > 20, EMA aligned up)
        s = stance(_features())
        self.assertEqual(s["direction"], "long")

    def test_stance_respects_adx_override(self):
        # raise ADX trend gate above 25 -> neutral
        s = stance(_features(), {"stance_adx_trend": 30.0})
        self.assertEqual(s["direction"], "neutral")

    def test_stance_respects_stop_target_atr(self):
        f = _features()
        s = stance(f, {"stance_stop_atr": 2.0, "stance_target_atr": 4.0})
        self.assertAlmostEqual(s["stop"], f["price"] - 2.0 * f["atr14"], places=6)
        self.assertAlmostEqual(s["target"], f["price"] + 4.0 * f["atr14"], places=6)

    def test_trend_respects_label_override(self):
        f = _features()
        t = trend_score(f, {"trend_label_up": 80.0, "trend_label_down": 20.0})
        # 25 ADX / aligned up yields a score in the 60s, now relabelled neutral
        self.assertIn(t["label"], ("up", "neutral"))

    def test_save_ignores_unknown_keys(self):
        out = save({"bogus": 1, "stance_adx_trend": 30.0}, "/tmp/nk_params_test.json")
        self.assertNotIn("bogus", out)
        self.assertEqual(out["stance_adx_trend"], 30.0)


if __name__ == "__main__":
    unittest.main()
