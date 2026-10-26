import unittest

from nakedk.policy import allow, note


class TestPolicy(unittest.TestCase):
    def test_block_losers(self):
        self.assertFalse(allow("down", "short"))
        self.assertFalse(allow("up", "short"))
        self.assertFalse(allow("range", "long"))

    def test_allow_winners(self):
        self.assertTrue(allow("transition", "long"))
        self.assertTrue(allow("range", "short"))
        self.assertTrue(allow("down", "long"))

    def test_none(self):
        self.assertTrue(allow(None, None))

    def test_note(self):
        self.assertLess(note("down", "short"), 0)
        self.assertGreater(note("range", "short"), 0)


if __name__ == "__main__":
    unittest.main()
