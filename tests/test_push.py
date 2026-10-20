import os
import tempfile
import unittest

from beagle import store


class TestPushOutbox(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "b.db")
        store.init(self.db)
        eid = store.add_event(self.db, {"ts": 1, "symbol": "BTCUSDT", "kind": "price_shock",
                                         "severity": "P1", "direction": "up", "price": 100, "payload": {}})
        self.aid = store.add_alert(self.db, eid, "P1", "test", 0)

    def _row(self):
        conn = store.connect(self.db)
        try:
            return dict(conn.execute("SELECT * FROM alerts WHERE id=?", (self.aid,)).fetchone())
        finally:
            conn.close()

    def test_retry_then_dead(self):
        for i in range(4):
            info = store.fail_alert(self.db, self.aid, "boom", max_attempts=5)
            self.assertEqual(info["status"], "pending")
        info = store.fail_alert(self.db, self.aid, "boom", max_attempts=5)
        self.assertEqual(info["status"], "failed")
        row = self._row()
        self.assertEqual(row["attempts"], 5)
        self.assertEqual(row["status"], "failed")
        self.assertIn("boom", row["last_error"])


if __name__ == "__main__":
    unittest.main()
