import unittest

from beagle.cli import apply_corr_gate


def C(sym, d, conf):
    return {"symbol": sym, "direction": d, "confidence": conf}


class TestCorrGate(unittest.TestCase):
    def test_drops_weaker_on_high_corr(self):
        cands = [C("BTCUSDT", "short", 64), C("ETHUSDT", "short", 58)]
        kept, gate = apply_corr_gate(cands, 0.91)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["symbol"], "BTCUSDT")
        self.assertEqual(gate["dropped"], "ETHUSDT")

    def test_keeps_both_when_low_corr(self):
        cands = [C("BTCUSDT", "short", 64), C("ETHUSDT", "short", 58)]
        kept, gate = apply_corr_gate(cands, 0.5)
        self.assertEqual(len(kept), 2)
        self.assertIsNone(gate)

    def test_keeps_both_when_directions_differ(self):
        cands = [C("BTCUSDT", "short", 64), C("ETHUSDT", "long", 58)]
        kept, gate = apply_corr_gate(cands, 0.95)
        self.assertEqual(len(kept), 2)
        self.assertIsNone(gate)


if __name__ == "__main__":
    unittest.main()
