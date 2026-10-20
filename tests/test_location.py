import unittest

from nakedk.location import atr_distance, edge_zone, measured_move, session_levels


class TestLocation(unittest.TestCase):
    def test_atr_distance(self):
        self.assertEqual(atr_distance(100, 110, 5), 2.0)
        self.assertIsNone(atr_distance(100, None, 5))

    def test_edge_zone(self):
        self.assertEqual(edge_zone(0.05), "low")
        self.assertEqual(edge_zone(0.5), "middle")
        self.assertEqual(edge_zone(0.95), "high")

    def test_session_levels(self):
        rows = [[0, "1", "2", "3", "1.5"],
                [1, "1.5", "9", "8", "8.5"],
                [2, "8.5", "9.5", "8.2", "9.1"]]
        s = session_levels(rows)
        self.assertEqual(s["prev_day_high"], 9)
        self.assertEqual(s["prev_day_low"], 8)

    def test_measured_move(self):
        self.assertEqual(measured_move(10, 100, "long"), 110)
        self.assertEqual(measured_move(10, 100, "short"), 90)


if __name__ == "__main__":
    unittest.main()
