import unittest

from nakedk.patterns_ext import extra_patterns


def K(o, h, l, c, v=100):
    return [0, str(o), str(h), str(l), str(c), str(v)]


def flat(n=30):
    return [K(100, 101, 99, 100) for _ in range(n)]


class TestExtendedPatterns(unittest.TestCase):
    def test_micro_double_bottom(self):
        ks = flat(28) + [K(101, 102, 100, 101.9), K(101, 102, 100, 101.8)]
        types = [p["type"] for p in extra_patterns(ks, {"price": 101.8})]
        self.assertIn("MICRO_DB", types)

    def test_iii(self):
        ks = flat(26) + [K(100, 105, 95, 100), K(100, 104, 96, 100),
                         K(100, 103, 97, 100), K(100, 102, 98, 100)]
        types = [p["type"] for p in extra_patterns(ks, {"price": 100})]
        self.assertIn("III", types)

    def test_outside_bar_reversal(self):
        ks = flat(28) + [K(100, 101, 99, 100), K(99, 102, 98, 101.5)]
        types = [p["type"] for p in extra_patterns(ks, {"price": 101.5})]
        self.assertIn("OBR_BULL", types)

    def test_no_pattern_on_flat(self):
        self.assertEqual(extra_patterns(flat(30), {"price": 100}), [])


if __name__ == "__main__":
    unittest.main()
