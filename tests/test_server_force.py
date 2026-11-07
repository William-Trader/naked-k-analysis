"""Dashboard force-refresh must bypass the symbol cache."""
from __future__ import annotations

import time
import unittest
from unittest import mock

import dashboard.server as server


class ForceRefreshTest(unittest.TestCase):
    def tearDown(self):
        server._cache.pop("TESTSYM", None)

    def test_force_rebuilds_instead_of_returning_cache(self):
        server._cache["TESTSYM"] = {"ts": int(time.time() * 1000),
                                    "data": {"cached": True}}
        with mock.patch.object(server, "_build", return_value={"fresh": True}) as build:
            out = server._payload("TESTSYM", force=True)
        self.assertEqual(out, {"fresh": True})
        build.assert_called_once()
        self.assertTrue(build.call_args.kwargs.get("force"))

    def test_non_force_uses_fresh_cache(self):
        server._cache["TESTSYM"] = {"ts": int(time.time() * 1000),
                                    "data": {"cached": True}}
        with mock.patch.object(server, "_build") as build:
            out = server._payload("TESTSYM", force=False)
        self.assertEqual(out, {"cached": True})
        build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
