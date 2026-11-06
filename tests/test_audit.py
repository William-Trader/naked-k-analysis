import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _load(name, relpath):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, relpath))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


audit = _load("accuracy_audit", "scripts/accuracy_audit.py")
coverage = _load("knowledge_coverage", "scripts/knowledge_coverage.py")


class TestAccuracyAudit(unittest.TestCase):
    def test_wilson_bounds(self):
        self.assertAlmostEqual(audit.wilson(0, 10), 0.0, places=6)
        lo = audit.wilson(5, 10)
        self.assertLess(lo, 0.5)
        self.assertGreater(lo, 0.2)

    def test_summarize_counts_and_hits(self):
        rows = [
            {"i": 60, "net": 1.0},
            {"i": 61, "net": -1.0},
            {"i": 62, "net": 0.5},
            {"i": 63, "net": -0.5},
        ]
        res = audit.summarize(rows)
        self.assertEqual(res["n"], 4)
        self.assertAlmostEqual(res["hit_rate"], 50.0)
        self.assertAlmostEqual(res["avg_net_pct"], 0.0)
        self.assertEqual(len(res["folds"]), 3)

    def test_folds_use_bar_index_not_count(self):
        # Regression: folds were computed from row counts while 'i' was a bar
        # index, so every fold came back None.
        rows = [{"i": 60 + k, "net": 0.1} for k in range(9)]
        res = audit.summarize(rows)
        self.assertTrue(all(f is not None for f in res["folds"]))

    def test_empty_filter_returns_none(self):
        self.assertIsNone(audit.summarize([], None))


class TestKnowledgeCoverage(unittest.TestCase):
    def test_covers_every_topic(self):
        res = coverage.audit()
        self.assertEqual(res["missing"], [])
        self.assertEqual(res["coverage_pct"], 100.0)
        self.assertGreaterEqual(res["modules"], coverage.MIN_MODULES)

    def test_new_modules_are_indexed(self):
        readme = os.path.join(ROOT, "knowledge", "README.md")
        with open(readme, encoding="utf-8") as fh:
            text = fh.read()
        for name in ("15-position-sizing-and-portfolio.md",
                     "16-multi-timeframe-confluence.md",
                     "17-failed-breakouts-and-traps.md",
                     "18-session-open-and-gaps.md",
                     "19-evidence-and-backtest-method.md",
                     "20-execution-and-psychology.md"):
            self.assertIn(name, text)


if __name__ == "__main__":
    unittest.main()
