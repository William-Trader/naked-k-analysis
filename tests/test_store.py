import os
import tempfile
import time
import unittest

from beagle import store


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "t.db")
        store.init(self.db)

    def test_event_alert_dedup(self):
        eid = store.add_event(self.db, {
            "ts": 1, "symbol": "BTCUSDT", "kind": "price_shock",
            "severity": "P1", "direction": "up", "price": 100.0, "payload": {},
        })
        aid = store.add_alert(self.db, eid, "P1", "test", 60_000)
        self.assertEqual(store.pending_alerts(self.db)[0]["id"], aid)
        now = int(time.time() * 1000)
        self.assertTrue(store.recent_alert_exists(self.db, "BTCUSDT", "price_shock", "up", now))
        store.mark_sent(self.db, aid)
        self.assertEqual(store.pending_alerts(self.db), [])

    def test_state_roundtrip(self):
        store.set_state(self.db, "BTCUSDT", "down")
        self.assertEqual(store.get_state(self.db, "BTCUSDT"), "down")
        store.set_state(self.db, "BTCUSDT", "up")
        self.assertEqual(store.get_state(self.db, "BTCUSDT"), "up")

    def test_status(self):
        s = store.status(self.db)
        self.assertEqual(s["events"], 0)
        self.assertEqual(s["pending"], 0)


if __name__ == "__main__":
    unittest.main()
