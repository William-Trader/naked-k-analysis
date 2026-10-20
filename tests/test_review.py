import os
import tempfile
import unittest

from beagle import adaptive, review, store


class TestReview(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, "b.db")
        self.ad = os.path.join(self.dir, "state", "adaptive.json")
        store.init(self.db)
        for i in range(60):
            sid = store.add_signal(self.db, {
                "ts": 1000 + i, "symbol": "BTCUSDT", "direction": "long",
                "confidence": 60, "entry": 100, "horizon_h": 1,
                "source": "engine_backfill", "setup": "L1", "regime": "up",
                "mtf_alignment": -2,
            })
            store.add_outcome(self.db, sid, 1, 2000 + i, 101, 1.0, 1, 1.5, -0.5, None)

    def test_build_buckets(self):
        rep = review.build(self.db)
        self.assertEqual(rep["n_total"], 60)
        self.assertEqual(rep["by_setup"]["L1"]["n"], 60)
        self.assertEqual(rep["by_setup"]["L1"]["hit_rate"], 100.0)
        self.assertTrue(rep["by_setup"]["L1"]["reliable"])

    def test_apply_writes_adaptive(self):
        rep = review.build(self.db, self.ad, apply=True)
        self.assertTrue(os.path.exists(self.ad))
        table = adaptive.load(self.ad)
        self.assertIn("L1", table["multipliers"])
        self.assertTrue(rep["adaptive"]["multipliers"])

    def test_render_text(self):
        text = review.render(review.build(self.db))
        self.assertIn("反馈闭环复盘", text)
        self.assertIn("L1", text)


if __name__ == "__main__":
    unittest.main()
