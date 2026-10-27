import unittest
from unittest.mock import patch

from nakedk import sources


def row(name, price, vol):
    return {"source": name, "price": price, "quote_vol": vol}


class TestCombine(unittest.TestCase):
    def test_outlier_is_ignored(self):
        rows = [row("a", 100.0, 40.0), row("b", 100.05, 30.0),
                row("c", 105.0, 20.0), row("d", 100.02, 10.0)]
        out = sources.combine(rows)
        self.assertLess(abs(out["weighted"] - 100.03), 0.05)
        self.assertEqual(out["confidence"], "low")

    def test_single_source_cap(self):
        rows = [row("a", 100.0, 900.0), row("b", 100.2, 50.0),
                row("c", 100.1, 50.0)]
        out = sources.combine(rows)
        top = max(r["weight"] for r in out["sources"])
        self.assertLessEqual(top, sources.MAX_SHARE + 1e-6)

    def test_confidence_high(self):
        rows = [row("a", 100.0, 45.0), row("b", 100.01, 22.0),
                row("c", 99.99, 12.0), row("d", 100.02, 12.0),
                row("e", 100.0, 9.0)]
        out = sources.combine(rows)
        self.assertEqual(out["n"], 5)
        self.assertEqual(out["confidence"], "high")
        self.assertGreaterEqual(out["effective_n"], 3.0)

    def test_empty(self):
        self.assertEqual(sources.combine([]), {})


class TestAggregate(unittest.TestCase):
    def test_weights_by_volume(self):
        rows = [row("binance", 100.0, 300.0), row("gate", 101.0, 100.0)]

        def fake_a(symbol):
            return rows[0]

        def fake_b(symbol):
            return rows[1]

        with patch.object(sources, "SOURCES", (fake_a, fake_b)):
            out = sources.aggregate("BTCUSDT")
        self.assertEqual(out["n"], 2)
        self.assertAlmostEqual(out["weighted"], 100.4, places=2)
        self.assertAlmostEqual(max(r["weight"] for r in out["sources"]), 0.6, places=2)

    def test_unreachable_skipped(self):
        def boom(symbol):
            raise RuntimeError("blocked")

        with patch.object(sources, "SOURCES", (boom, lambda s: row("gate", 100.0, 1.0))):
            out = sources.aggregate("ETHUSDT")
        self.assertEqual(out["n"], 1)


if __name__ == "__main__":
    unittest.main()
