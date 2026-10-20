import os
import tempfile
import unittest

from beagle.score import excursions


def K(o, h, l, c):
    return [0, str(o), str(h), str(l), str(c), "1"]


class TestExcursions(unittest.TestCase):
    def test_long(self):
        ks = [K(100, 101, 99, 100), K(100, 106, 98, 104), K(104, 108, 95, 107)]
        mfe, mae = excursions(ks, 0, 2, "long")
        self.assertEqual(mfe, 8.0)
        self.assertEqual(mae, -5.0)

    def test_short(self):
        ks = [K(100, 101, 99, 100), K(100, 104, 97, 98), K(98, 99, 92, 93)]
        mfe, mae = excursions(ks, 0, 2, "short")
        self.assertEqual(mfe, 8.0)
        self.assertEqual(mae, -4.0)

    def test_neutral(self):
        ks = [K(100, 101, 99, 100), K(100, 101, 99, 100)]
        self.assertEqual(excursions(ks, 0, 1, "neutral"), (None, None))


if __name__ == "__main__":
    unittest.main()
