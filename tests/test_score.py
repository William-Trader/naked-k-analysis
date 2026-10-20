import unittest

from nakedk.score import summarise


class TestScoreSummary(unittest.TestCase):
    def test_hit_rate_and_average(self):
        rows = [
            {"direction": "long", "hit": True, "signed_ret": 1.0, "confidence": 60},
            {"direction": "long", "hit": True, "signed_ret": 0.5, "confidence": 60},
            {"direction": "short", "hit": False, "signed_ret": 0.8, "confidence": 55},
        ]
        s = summarise(rows)
        self.assertEqual(s["n"], 3)
        self.assertEqual(s["directional"], 3)
        self.assertAlmostEqual(s["hit_rate"], 66.7)
        self.assertEqual(s["by_direction"]["long"]["n"], 2)
        self.assertAlmostEqual(s["by_direction"]["long"]["hit_rate"], 100.0)
        self.assertAlmostEqual(s["by_direction"]["short"]["hit_rate"], 0.0)
        self.assertIn("60-64", s["calibration"])

    def test_neutral_is_excluded_from_hit_rate(self):
        s = summarise([{"direction": "neutral", "hit": None, "signed_ret": 0.0, "confidence": 50}])
        self.assertEqual(s["directional"], 0)
        self.assertIsNone(s["hit_rate"])


if __name__ == "__main__":
    unittest.main()
