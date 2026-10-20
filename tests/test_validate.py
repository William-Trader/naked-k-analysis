import unittest

from nakedk.validate import check_numbers, validate_brief

GOOD = """Always-In = 空
Setup: L2 反弹
触发 81,200；失效 82,300；目标 80,684
R:R = 1.8:1
SIGNAL|BTC|short|4h|58|entry=81200|stop=82300|target=80684
SIGNAL|ETH|neutral|4h|55|entry=2400|stop=2430|target=2380
非投资建议"""

BAD = """BTC 可能上涨。
SIGNAL|BTC|long|4h|60|entry=1|stop=2|target=3"""


class TestValidate(unittest.TestCase):
    def test_good_brief(self):
        r = validate_brief(GOOD)
        self.assertTrue(r["ok"], r)

    def test_missing_always_in(self):
        r = validate_brief(BAD)
        self.assertFalse(r["ok"])
        self.assertFalse(r["checks"]["always_in"]["ok"])

    def test_number_provenance(self):
        src = "SIG|close=81200|stop=82300|target=80684"
        self.assertTrue(check_numbers("触发 81,200；失效 82,300", src)["ok"])
        self.assertFalse(check_numbers("触发 99,999", src)["ok"])


if __name__ == "__main__":
    unittest.main()
