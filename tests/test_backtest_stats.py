import unittest

from nakedk.backtest import _stats


class TestBacktestStats(unittest.TestCase):
    def test_constant_returns_no_sharpe(self):
        trades = [{"signed_ret": 0.0, "hit": False, "direction": "long",
                   "hit_stop": False} for _ in range(5)]
        out = _stats(trades)
        self.assertIsNone(out["sharpe_per_trade"])
        self.assertEqual(out["trades"], 5)

    def test_varied_returns_have_sharpe(self):
        trades = [{"signed_ret": r, "hit": r > 0, "direction": "long",
                   "hit_stop": False} for r in (0.5, -0.2, 0.3, -0.1, 0.4)]
        self.assertIsNotNone(_stats(trades)["sharpe_per_trade"])


if __name__ == "__main__":
    unittest.main()
