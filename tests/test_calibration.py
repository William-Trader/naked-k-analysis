import os
import tempfile
import unittest

from nakedk import calibration as cal


class TestCalibration(unittest.TestCase):
    def test_bucket_keys(self):
        self.assertEqual(cal.bucket_key(42), "0-44")
        self.assertEqual(cal.bucket_key(57), "55-59")
        self.assertEqual(cal.bucket_key(64), "60-64")
        self.assertEqual(cal.bucket_key(99), "70+")

    def test_shrink_small_sample(self):
        samples = [(57, 1)] * 2 + [(50, 0)] * 2
        table = cal.fit(samples)
        b = table["buckets"]["55-59"]
        self.assertEqual(b["n"], 2)
        self.assertLess(b["p"], 1.0)
        self.assertGreater(b["p"], 0.4)

    def test_small_bucket_not_applied(self):
        table = cal.fit([(57, 1)] * 5)
        conf, meta = cal.calibrate(57, table, min_n=20)
        self.assertEqual(conf, 57)
        self.assertFalse(meta["applied"])

    def test_large_bucket_applied_and_capped(self):
        table = cal.fit([(57, 1)] * 60 + [(57, 0)] * 20)
        conf, meta = cal.calibrate(57, table, min_n=20)
        self.assertTrue(meta["applied"])
        self.assertGreaterEqual(conf, 35)
        self.assertLessEqual(conf, 65)

    def test_missing_db_is_empty(self):
        self.assertEqual(cal.load_samples("/nonexistent/x.db"), [])
        table = cal.table_from_db("/nonexistent/x.db")
        self.assertEqual(table["n"], 0)


if __name__ == "__main__":
    unittest.main()
