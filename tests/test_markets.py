"""Tests for the multi-market source base (markets.py)."""
from __future__ import annotations

import unittest

from nakedk.markets import resolve, normalize_chart, _range_for, UNIVERSE


class ResolveTest(unittest.TestCase):
    def test_crypto_majors_default_to_binance(self):
        self.assertEqual(resolve("BTCUSDT"), ("binance", "BTCUSDT", "crypto"))
        self.assertEqual(resolve("ETHUSDT"), ("binance", "ETHUSDT", "crypto"))

    def test_unknown_symbol_defaults_to_binance(self):
        self.assertEqual(resolve("DOGEUSDT"), ("binance", "DOGEUSDT", "crypto"))

    def test_metals_indices_futures_route_to_yahoo(self):
        self.assertEqual(resolve("XAU"), ("yahoo", "GC=F", "metal"))
        self.assertEqual(resolve("SPX"), ("yahoo", "^GSPC", "index"))
        self.assertEqual(resolve("NDX"), ("yahoo", "^IXIC", "index"))
        self.assertEqual(resolve("ES"), ("yahoo", "ES=F", "future"))
        self.assertEqual(resolve("CL"), ("yahoo", "CL=F", "future"))

    def test_universe_has_required_markets(self):
        for s in ("XAU", "SPX", "NDX", "DJI", "ES", "NQ", "CL"):
            self.assertIn(s, UNIVERSE)


class RangeForTest(unittest.TestCase):
    def test_small_limit_uses_short_range(self):
        self.assertEqual(_range_for("4h", 10), "5d")
        self.assertEqual(_range_for("1d", 5), "5d")

    def test_4h_200_is_3mo(self):
        self.assertEqual(_range_for("4h", 200), "3mo")

    def test_daily_160_is_6mo(self):
        self.assertEqual(_range_for("1d", 160), "6mo")

    def test_daily_365_is_1y(self):
        self.assertEqual(_range_for("1d", 365), "1y")

    def test_daily_2000_is_max(self):
        self.assertEqual(_range_for("1d", 2000), "max")


class NormalizeChartTest(unittest.TestCase):
    def test_drops_none_close(self):
        rows = normalize_chart(
            [1000, 2000, 3000],
            {"open": [10, 20, None], "high": [11, 21, None],
             "low": [9, 19, None], "close": [10.5, 20.5, None],
             "volume": [5, 5, 5]})
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], [1000000, 10.0, 11.0, 9.0, 10.5, 5.0])

    def test_coerces_missing_ohl_to_close(self):
        rows = normalize_chart([1000], {"open": [None], "high": [None],
                                        "low": [None], "close": [42.0],
                                        "volume": [None]})
        self.assertEqual(rows, [[1000000, 42.0, 42.0, 42.0, 42.0, 0.0]])

    def test_empty_returns_empty(self):
        self.assertEqual(normalize_chart(None, {}), [])
        self.assertEqual(normalize_chart([], {}), [])

    def test_limit_slices_tail(self):
        ts = list(range(1000, 1010))
        q = {"open": [1.0]*10, "high": [1.0]*10, "low": [1.0]*10,
             "close": [1.0]*10, "volume": [0.0]*10}
        rows = normalize_chart(ts, q, limit=3)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0][0], 1007000)


if __name__ == "__main__":
    unittest.main()
