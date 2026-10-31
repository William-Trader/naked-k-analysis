"""Tests for knowledge search + rubric auto-scorer."""
from __future__ import annotations

import unittest

from nakedk.knowledge import search, score_briefing, knowledge_dir


class SearchTest(unittest.TestCase):
    def test_dir_exists(self):
        import os
        self.assertTrue(os.path.isdir(knowledge_dir()))

    def test_search_finds_albrooks(self):
        results = search("Al Brooks", limit=20)
        self.assertTrue(results, "expected at least one hit for 'Al Brooks'")
        # top hit should be a markdown file in the knowledge dir
        self.assertTrue(results[0]["file"].endswith(".md"))

    def test_search_returns_snippets(self):
        results = search("market structure", limit=20)
        self.assertTrue(results)
        self.assertTrue(all("top" in r and r["top"] for r in results))

    def test_empty_query(self):
        self.assertEqual(search("   "), [])


class RubricTest(unittest.TestCase):
    def test_full_briefing_scores_high(self):
        text = ("高周期：日线偏空；市场周期：下跌后的区间整理；Always-In 偏空；"
                "pos20=0.36 位置区间下沿；Setup：H2 观察；信号K：收盘、实体、影线、跟随；"
                "触发：站上 81900；失效：跌破 80684；目标：82225 / 82940；"
                "R:R 1.8:1；主力：缩量、下影买回、无派发；反方情景：若放量跌破则转空；"
                "概率区间 40-60%")
        r = score_briefing(text)
        self.assertGreaterEqual(r["total"], 50)
        self.assertEqual(r["verdict"], "practitioner-grade")

    def test_empty_briefing_scores_zero(self):
        r = score_briefing("")
        self.assertEqual(r["total"], 0)
        self.assertEqual(r["verdict"], "rework")

    def test_partial_scores_adequate(self):
        text = ("日线方向；趋势；方向偏多；位置；Setup H2；触发；失效；目标；"
                "R:R；主力证据；概率区间")
        r = score_briefing(text)
        self.assertEqual(r["total"], 47)
        self.assertEqual(r["verdict"], "adequate")

    def test_dimension_count_is_12(self):
        r = score_briefing("")
        self.assertEqual(len(r["dimensions"]), 12)


if __name__ == "__main__":
    unittest.main()
