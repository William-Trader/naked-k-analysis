import unittest

from nakedk.analogs import bucket, bucket_regime, build


def K(c, h=None, l=None):
    h = h if h is not None else c + 1
    l = l if l is not None else c - 1
    return [0, str(c), str(h), str(l), str(c), "100"]


class TestAnalogs(unittest.TestCase):
    def test_bucket_keys(self):
        f = {"ema20": 101, "ema50": 100, "price": 102, "adx14": 25, "pos20": 0.5}
        self.assertEqual(bucket(f), "up|mid|mid")
        self.assertEqual(bucket_regime(f), "up")

    def test_build_returns_counts(self):
        ks = [K(100 + i * 0.5) for i in range(90)]
        table = build(ks, horizon=1, lookback=60)
        self.assertTrue(table)
        row = next(iter(table.values()))
        self.assertGreater(row["n"], 0)
        self.assertIn("wilson_up", row)


if __name__ == "__main__":
    unittest.main()
