"""Plan persistence + trigger-loop integration (temp SQLite, no network)."""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from beagle import engine, store
from nakedk import plans


def make_plan():
    p = plans.build("BTCUSDT", "4h", "long", price=100.0, atr=2.0,
                    trigger=99.0, stop=96.0, target1=106.0, target2=109.0,
                    setup="H2", confidence=60, grade="A", ttl_h=12)
    return p


class StoreLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="nk-store-")
        self.db = os.path.join(self.tmp, "beagle.db")
        store.init(self.db)

    def test_save_active_and_events_idempotent(self):
        p = store.save_plan(self.db, make_plan())
        self.assertIsNotNone(p["id"])
        active = store.active_plan(self.db, "BTCUSDT")
        self.assertEqual(active["id"], p["id"])
        ev = {"type": "triggered", "price": 99.0, "ts": 1_700_000_000_000,
              "to_status": "triggered"}
        first = store.add_plan_event(self.db, p, ev, plans.event_key(p, ev))
        second = store.add_plan_event(self.db, p, ev, plans.event_key(p, ev))
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(len(store.plan_events(self.db, p["id"])), 1)

    def test_outbox_dedupes(self):
        p = store.save_plan(self.db, make_plan())
        a = store.outbox_add(self.db, 1, "qq", "hello")
        b = store.outbox_add(self.db, 1, "qq", "hello again")
        self.assertIsNotNone(a)
        self.assertIsNone(b)
        pending = store.outbox_pending(self.db)
        self.assertEqual(len(pending), 1)
        store.outbox_mark(self.db, pending[0]["id"], "sent")
        self.assertEqual(store.outbox_pending(self.db), [])

    def test_tick_moves_armed_to_triggered(self):
        p = store.save_plan(self.db, make_plan())
        settings = {"auto_trigger": True, "auto_push": False,
                    "push_severity": []}
        with mock.patch.object(engine, "last_price", return_value=98.9), \
                mock.patch.object(engine, "refresh_plan", return_value=p):
            events = engine.tick(settings, self.db)
        self.assertTrue(any(e.get("type") == "triggered" for e in events))
        active = store.active_plan(self.db, "BTCUSDT")
        self.assertEqual(active["status"], "triggered")
        self.assertIsNotNone(active.get("triggered_at"))

    def test_tick_respects_auto_trigger_off(self):
        store.save_plan(self.db, make_plan())
        with mock.patch.object(engine, "last_price", return_value=98.9):
            self.assertEqual(engine.tick({"auto_trigger": False}, self.db), [])
        self.assertEqual(store.active_plan(self.db, "BTCUSDT")["status"], "armed")


if __name__ == "__main__":
    unittest.main()
