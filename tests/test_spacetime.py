# -----------------------------------------------------------------
# tests/test_spacetime.py - adaptive spacetime engine
# (c) 2026 William-Trader (https://github.com/William-Trader)
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# -----------------------------------------------------------------
"""No-look-ahead, scale adaptivity and explainability of the 2.3.0 engine."""
from __future__ import annotations

import os
import unittest
from unittest import mock

from nakedk import spacetime

H = 3600_000


def _bars(n: int, step: int, *, slope: float = 0.1, wobble: float = 0.0):
    rows = []
    for i in range(n):
        c = 100.0 + i * slope + (wobble if i % 2 else 0.0)
        rows.append([i * step, c, c + 1.0, c - 1.0, c, 1.0])
    return rows


class SpacetimeState(unittest.TestCase):
    def setUp(self):
        self.ks4 = _bars(120, 4 * H, slope=0.4)
        self.ks1 = _bars(480, H, slope=0.1)

    def test_state_is_complete_and_explainable(self):
        st = spacetime.build_state(self.ks4, self.ks1, 100)
        self.assertTrue(st["complete"])
        self.assertIn("主导尺度", spacetime.describe(st))
        self.assertIn("state_id", st)
        self.assertIn(1, st["scale_scores"])
        self.assertIn(24, st["scale_scores"])

    def test_no_lookahead_past_bar_close(self):
        idx = 100
        cutoff = int(self.ks4[idx][0]) + 4 * H
        future = _bars(1, H)
        future[0][0] = cutoff + H
        future[0][1] = future[0][2] = future[0][3] = future[0][4] = 99999.0
        a = spacetime.build_state(self.ks4, self.ks1, idx)
        b = spacetime.build_state(self.ks4, self.ks1 + future, idx)
        self.assertEqual(a, b)

    def test_short_scale_wobble_reduces_its_efficiency(self):
        ks1 = _bars(480, H, slope=0.5, wobble=10.0)
        st = spacetime.build_state(_bars(120, 4 * H, slope=2.0),
                                   ks1, 100)
        # Alternating 10-point wobble destroys the 1h path efficiency while
        # 2h+ aggregation cancels it out.
        self.assertGreater(st["scale_scores"][2], st["scale_scores"][1])

    def test_insufficient_history_fails_closed(self):
        st = spacetime.build_state(self.ks4[:5], self.ks1[:5], 4)
        self.assertFalse(st["complete"])
        ok, why = spacetime.admit(st, "long")
        self.assertFalse(ok)
        self.assertTrue(why)


class AdmissionRules(unittest.TestCase):
    def _state(self, **kw):
        base = {"complete": True, "dominant_scale_h": 4, "regime": "trend",
                "velocity": 0.5, "acceleration": 0.1,
                "position": 0.5, "position_bucket": "mid",
                "level_touch_weight": 1.0, "session": "asia",
                "state_id": "4h|trend|mid|asia", "scale_scores": {1: 0.2,
                                                                  24: 0.6}}
        base.update(kw)
        return base

    def test_trend_requires_velocity_agreement(self):
        ok, why = spacetime.admit(self._state(velocity=-0.5), "long")
        self.assertFalse(ok)
        self.assertIn("逆", why)

    def test_trend_follows_long_dominant_scale(self):
        # v1 wrongly rejected a dominant scale longer than the horizon.
        ok, why = spacetime.admit(self._state(dominant_scale_h=24), "long")
        self.assertTrue(ok)
        self.assertIn("v2", why)

    def test_extreme_velocity_rejected(self):
        ok, _ = spacetime.admit(self._state(velocity=4.0), "long")
        self.assertFalse(ok)

    def test_range_mid_requires_agreement(self):
        ok, _ = spacetime.admit(
            self._state(regime="range", velocity=-0.3, acceleration=-0.2),
            "long")
        self.assertFalse(ok)
        ok2, _ = spacetime.admit(
            self._state(regime="range", velocity=0.3, acceleration=0.2),
            "long")
        self.assertTrue(ok2)

    def test_every_decision_has_a_reason(self):
        for direction in ("long", "short", "neutral"):
            ok, why = spacetime.admit(self._state(), direction)
            self.assertIsInstance(ok, bool)
            self.assertTrue(why)


class OptionalByDefault(unittest.TestCase):
    def test_disabled_by_default(self):
        with mock.patch.dict(os.environ, {"NK_SPACETIME": ""}):
            self.assertFalse(spacetime.enabled())

    def test_enabled_explicitly(self):
        with mock.patch.dict(os.environ, {"NK_SPACETIME": "1"}):
            self.assertTrue(spacetime.enabled())


if __name__ == "__main__":
    unittest.main()
