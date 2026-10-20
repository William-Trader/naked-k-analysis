import os
import tempfile
import unittest

from nakedk.pattern_tracker import states, track


class TestPatternTracker(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "p.db")

    def test_lifecycle(self):
        p = {"type": "DB", "direction": "bullish", "price": 100.0, "neckline": 105.0,
             "target": 115.0, "stop": 95.0, "quality": 70, "score": 70.0,
             "context": "range", "note": ""}
        track("BTCUSDT", [p], self.db, last_price=100, now=1)
        self.assertEqual(states("BTCUSDT", self.db)[0]["status"], "forming")
        track("BTCUSDT", [p], self.db, last_price=106, now=2)
        self.assertEqual(states("BTCUSDT", self.db)[0]["status"], "confirmed")
        track("BTCUSDT", [p], self.db, last_price=116, now=3)
        self.assertEqual(states("BTCUSDT", self.db)[0]["status"], "target_hit")

    def test_invalidation(self):
        p = {"type": "DT", "direction": "bearish", "price": 100.0, "neckline": 95.0,
             "target": 85.0, "stop": 105.0, "quality": 60, "score": 60.0,
             "context": "bear", "note": ""}
        track("ETHUSDT", [p], self.db, last_price=100, now=1)
        track("ETHUSDT", [p], self.db, last_price=106, now=2)
        self.assertEqual(states("ETHUSDT", self.db)[0]["status"], "invalidated")


if __name__ == "__main__":
    unittest.main()
