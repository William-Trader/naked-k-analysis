import unittest
from unittest.mock import patch

from nakedk import sources


def fake(name, price, vol):
    return {"source": name, "price": price, "quote_vol": vol}


class TestSources(unittest.TestCase):
    def test_weighted_price_and_shares(self):
        rows = [fake("binance", 100.0, 300.0), fake("gate", 101.0, 100.0)]
        with patch.object(sources, "SOURCES", (
                lambda s: rows[0], lambda s: rows[1])):
            out = sources.aggregate("BTCUSDT")
        self.assertEqual(out["n"], 2)
        self.assertAlmostEqual(out["weighted"], 100.25, places=2)
        self.assertAlmostEqual(out["sources"][0]["share"], 0.75, places=3)
        self.assertAlmostEqual(out["sources"][1]["share"], 0.25, places=3)

    def test_unreachable_source_is_skipped(self):
        def boom(symbol):
            raise RuntimeError("blocked")

        with patch.object(sources, "SOURCES", (boom, lambda s: fake("gate", 100.0, 1.0))):
            out = sources.aggregate("ETHUSDT")
        self.assertEqual(out["n"], 1)
        self.assertEqual(out["sources"][0]["source"], "gate")

    def test_empty(self):
        with patch.object(sources, "SOURCES", ()):
            self.assertEqual(sources.aggregate("BTCUSDT"), {})


if __name__ == "__main__":
    unittest.main()
