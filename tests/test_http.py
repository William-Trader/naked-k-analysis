# -*- coding: utf-8 -*-
"""nakedk/http.py 单元测试：退避重试 / 4xx 不重试 / 耗尽抛错。"""
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError

from nakedk.http import get_json


def _good():
    g = mock.MagicMock()
    g.__enter__ = mock.MagicMock(return_value=g)
    g.read.return_value = b'{"ok": true}'
    return g


class TestHttpRetry(unittest.TestCase):
    @mock.patch("nakedk.http.urllib.request.urlopen")
    @mock.patch("nakedk.http.time.sleep")
    def test_success_first_try(self, _s, u):
        u.return_value = _good()
        self.assertEqual(get_json("http://x/", max_retries=2), {"ok": True})
        self.assertEqual(u.call_count, 1)

    @mock.patch("nakedk.http.urllib.request.urlopen")
    @mock.patch("nakedk.http.time.sleep")
    def test_429_retries_then_succeeds(self, _s, u):
        err = HTTPError("http://x", 429, "Too Many Requests", {}, None)
        u.side_effect = [err, err, _good()]
        self.assertEqual(get_json("http://x/", max_retries=3), {"ok": True})
        self.assertEqual(u.call_count, 3)

    @mock.patch("nakedk.http.urllib.request.urlopen")
    @mock.patch("nakedk.http.time.sleep")
    def test_5xx_retries(self, _s, u):
        err = HTTPError("http://x", 502, "Bad Gateway", {}, None)
        u.side_effect = [err, _good()]
        self.assertEqual(get_json("http://x/", max_retries=2), {"ok": True})

    @mock.patch("nakedk.http.urllib.request.urlopen")
    def test_4xx_raises_immediately(self, u):
        u.side_effect = HTTPError("http://x", 400, "Bad Request", {}, None)
        with self.assertRaises(HTTPError):
            get_json("http://x/", max_retries=3)
        self.assertEqual(u.call_count, 1)

    @mock.patch("nakedk.http.urllib.request.urlopen")
    @mock.patch("nakedk.http.time.sleep")
    def test_timeout_then_success(self, _s, u):
        u.side_effect = [URLError("timed out"), _good()]
        self.assertEqual(get_json("http://x/", max_retries=2), {"ok": True})

    @mock.patch("nakedk.http.urllib.request.urlopen")
    @mock.patch("nakedk.http.time.sleep")
    def test_exhausted_raises_last(self, _s, u):
        u.side_effect = HTTPError("http://x", 429, "Too Many Requests", {}, None)
        with self.assertRaises(HTTPError):
            get_json("http://x/", max_retries=2)
        self.assertEqual(u.call_count, 3)


if __name__ == "__main__":
    unittest.main()
