import unittest

from nakedk.backtest import _max_drawdown, _sharpe


class TestBacktestMetrics(unittest.TestCase):
    def test_max_drawdown(self):
        self.assertAlmostEqual(_max_drawdown([1.0, 1.2, 0.9, 1.1]), -25.0)

    def test_max_drawdown_monotonic(self):
        self.assertAlmostEqual(_max_drawdown([1.0, 1.1, 1.2]), 0.0)

    def test_sharpe_none_for_short_sample(self):
        self.assertIsNone(_sharpe([1.0, 2.0]))

    def test_sharpe_positive_for_consistent_returns(self):
        self.assertGreater(_sharpe([1.0, 1.2, 0.8, 1.1, 0.9]), 0.0)


if __name__ == "__main__":
    unittest.main()
