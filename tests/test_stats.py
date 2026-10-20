import unittest

from nakedk.stats import MIN_N, bucket, summarize, wilson


class TestStats(unittest.TestCase):
    def test_wilson_bounds(self):
        lo, hi = wilson(0, 10)
        self.assertEqual(lo, 0.0)
        self.assertLess(hi, 35)
        lo2, hi2 = wilson(10, 10)
        self.assertGreater(lo2, 65)

    def test_summarize_reliable(self):
        rows = [{"hit": 1, "ret_pct": 1.0}] * (MIN_N - 1)
        self.assertFalse(summarize(rows)["reliable"])
        rows.append({"hit": 0, "ret_pct": -1.0})
        s = summarize(rows)
        self.assertTrue(s["reliable"])
        self.assertEqual(s["n"], MIN_N)

    def test_bucket_groups(self):
        rows = [{"setup": "L1", "hit": 1}, {"setup": "L1", "hit": 0}, {"setup": "DB", "hit": 1}]
        out = bucket(rows, lambda r: r["setup"])
        self.assertEqual(out["L1"]["n"], 2)
        self.assertEqual(out["L1"]["hit_rate"], 50.0)


if __name__ == "__main__":
    unittest.main()
