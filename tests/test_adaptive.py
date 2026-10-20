import unittest

from beagle import adaptive


def st(n, hit):
    return {"n": n, "hit_rate": hit, "reliable": n >= 30}


class TestAdaptive(unittest.TestCase):
    def test_no_change_below_min_n(self):
        table = {"version": 1, "multipliers": {}, "streaks": {}, "log": []}
        out = adaptive.update(table, {"L1": st(10, 90)}, 0.5)
        self.assertEqual(out["multipliers"], {})

    def test_step_is_bounded(self):
        table = {"version": 1, "multipliers": {"L1": 1.0}, "streaks": {}, "log": []}
        out = adaptive.update(table, {"L1": st(100, 90)}, 0.5)
        self.assertAlmostEqual(out["multipliers"]["L1"], 1.08)
        self.assertEqual(len(out["log"]), 1)

    def test_hard_bounds(self):
        table = {"version": 1, "multipliers": {"L1": 1.29}, "streaks": {}, "log": []}
        for _ in range(10):
            table = adaptive.update(table, {"L1": st(100, 99)}, 0.5)
        self.assertLessEqual(table["multipliers"]["L1"], adaptive.HI)

    def test_quarantine_after_two_bad_reviews(self):
        table = {"version": 1, "multipliers": {"DB": 1.0}, "streaks": {}, "log": []}
        table = adaptive.update(table, {"DB": st(100, 30)}, 0.5)
        self.assertGreater(table["multipliers"]["DB"], adaptive.LO)
        table = adaptive.update(table, {"DB": st(100, 30)}, 0.5)
        self.assertEqual(table["multipliers"]["DB"], adaptive.LO)


if __name__ == "__main__":
    unittest.main()
