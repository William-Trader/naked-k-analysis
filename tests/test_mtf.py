import unittest

from nakedk.mtf import alignment, tf_sign


def K(o, c):
    return [0, str(o), str(max(o, c) + 1), str(min(o, c) - 1), str(c), "100"]


class TestMtf(unittest.TestCase):
    def test_up_and_down(self):
        up = [K(100 + i, 101 + i) for i in range(80)]
        down = [K(200 - i, 199 - i) for i in range(80)]
        self.assertEqual(tf_sign(up), 1)
        self.assertEqual(tf_sign(down), -1)

    def test_alignment_sums(self):
        up = [K(100 + i, 101 + i) for i in range(80)]
        down = [K(200 - i, 199 - i) for i in range(80)]
        def fake(symbol, tf, limit):
            return up if tf in ("1d", "4h") else down
        out = alignment("BTCUSDT", klines_fn=fake, now_ms=0)
        self.assertEqual(out["alignment"], 1)
        self.assertEqual(out["label"], "mixed")


if __name__ == "__main__":
    unittest.main()
