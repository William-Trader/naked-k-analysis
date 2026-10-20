import unittest

from nakedk.volume import divergence, effort_result, vpoc


class TestVolume(unittest.TestCase):
    def test_vpoc_within_range(self):
        ks = [[i, "100", "102", "98", "101", "1000"] for i in range(10)]
        out = vpoc(ks, buckets=5)
        self.assertGreaterEqual(out["poc"], 98)
        self.assertLessEqual(out["poc"], 102)
        lo, hi = out["value_area"]
        self.assertLess(lo, hi)

    def test_effort_result(self):
        self.assertEqual(effort_result({"vol_z": 3, "body_ratio": 0.2, "range_atr": 1}), "absorption")
        self.assertEqual(effort_result({"vol_z": 3, "body_ratio": 0.8, "range_atr": 1}), "expansion")

    def test_divergence_needs_history(self):
        self.assertIsNone(divergence([], 20))


if __name__ == "__main__":
    unittest.main()
