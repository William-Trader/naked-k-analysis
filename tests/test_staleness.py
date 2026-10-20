import unittest

from beagle.push import is_stale


class TestStaleness(unittest.TestCase):
    def test_fresh(self):
        self.assertFalse(is_stale(1_000_000, 1_000_000 + 60_000, 30))

    def test_stale(self):
        self.assertTrue(is_stale(1_000_000, 1_000_000 + 31 * 60_000, 30))

    def test_disabled(self):
        self.assertFalse(is_stale(1_000_000, 9_999_999_999, 0))

    def test_missing_created(self):
        self.assertFalse(is_stale(None, 9_999_999_999, 30))


if __name__ == "__main__":
    unittest.main()
