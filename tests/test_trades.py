import unittest
from unittest.mock import patch

from nakedk import trades as T


class TestTrades(unittest.TestCase):
    def test_book_imbalance(self):
        fake = {"bids": [["100", "10"], ["99.6", "5"]],
                "asks": [["101", "4"], ["102", "20"]]}
        with patch.object(T, "_get", return_value=fake):
            out = T.book("BTCUSDT")
        self.assertAlmostEqual(out["bid_q"], 15.0)
        self.assertAlmostEqual(out["ask_q"], 4.0)
        self.assertEqual(out["imbalance"], round(11 / 19, 3))

    def test_trades_delta(self):
        rows = [{"p": "100", "q": "1", "m": False},
                {"p": "100", "q": "2", "m": True}]
        with patch.object(T, "_get", return_value=rows):
            out = T.trades("BTCUSDT")
        self.assertAlmostEqual(out["delta"], round((100 - 200) / 300, 3))
        self.assertEqual(out["n"], 2)


if __name__ == "__main__":
    unittest.main()
