import os
import tempfile
import unittest

from nakedk.pattern_calibration import load, save
from nakedk.patterns import _stage


class TestCalibration(unittest.TestCase):
    def test_bounds_and_roundtrip(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "q.json")
        save(p, {"DB": 1.4, "DT": 0.5}, 10)
        out = load(p)
        self.assertEqual(out["DB"], 1.15)
        self.assertEqual(out["DT"], 0.85)

    def test_missing_file(self):
        self.assertEqual(load("/nonexistent/q.json"), {})


class TestStage(unittest.TestCase):
    def test_stages(self):
        base = {"direction": "bullish", "neckline": 100.0, "target": 110.0}
        self.assertEqual(_stage(base, 99.7, 1.0), "forming")
        self.assertEqual(_stage(base, 101, 1.0), "breakout")
        self.assertEqual(_stage(base, 111, 1.0), "target")
        ks = [[0, "100", "101", "99", "99", "1"],
              [1, "100", "102", "99", "101", "1"]]
        self.assertEqual(_stage({**base, "index": 0}, 98.0, 1.0, ks), "failed")


if __name__ == "__main__":
    unittest.main()
