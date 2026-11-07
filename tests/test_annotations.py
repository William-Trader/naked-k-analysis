"""Chart annotation geometry tests (pure, synthetic bars)."""
from __future__ import annotations

import json
import unittest

from nakedk.annotations import build


def bars(n=160, start=100.0, drift=0.25, amp=1.2):
    out = []
    t = 1_700_000_000
    p = start
    for i in range(n):
        o = p
        c = p + drift + (amp if i % 7 == 0 else -amp * 0.6)
        h = max(o, c) + 0.5
        l = min(o, c) - 0.5
        out.append([int((t + i * 14400) * 1000), o, h, l, c, 100 + i % 9])
        p = c
    return out


class AnnotationTest(unittest.TestCase):
    def test_build_returns_serialisable_geometry(self):
        ks = bars()
        f = {"price": ks[-1][4], "atr14": 2.0}
        out = build(ks, f, [], {"state": "up", "bos": None}, "4h")
        self.assertIn("levels", out)
        self.assertIn("pivots", out)
        self.assertGreater(len(out["pivots"]), 3)
        json.dumps(out)  # must not contain non-serialisable objects
        for p in out["pivots"]:
            self.assertIsNotNone(p["t"])
        for z in out["zones"]:
            self.assertLess(z["bottom"], z["top"])

    def test_pattern_geometry_has_finite_points(self):
        ks = bars()
        f = {"price": ks[-1][4], "atr14": 2.0}
        pats = [{"type": "DB", "label": "双底候选", "direction": "bullish",
                 "index": len(ks) - 6, "price": ks[-6][3], "quality": 70,
                 "neckline": ks[-6][4] + 3, "target": ks[-6][4] + 8,
                 "stop": ks[-6][3] - 1}]
        out = build(ks, f, pats, {"state": "range"}, "4h")
        self.assertEqual(len(out["patterns"]), 1)
        p = out["patterns"][0]
        self.assertGreaterEqual(len(p["points"]), 3)
        self.assertTrue(all(x["t"] is not None and x["p"] is not None for x in p["points"]))
        self.assertTrue(any(ln["kind"] == "neckline" for ln in p["lines"]))

    def test_empty_safe(self):
        out = build([], {}, [], {}, "4h")
        self.assertEqual(out["pivots"], [])


if __name__ == "__main__":
    unittest.main()
