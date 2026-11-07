"""Remote qqbot transport tests (no network)."""
from __future__ import annotations

import unittest
from unittest import mock

from beagle import push


class RemoteTransportTest(unittest.TestCase):
    def test_ssh_command_quotes_message(self):
        seen = {}

        class P:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake(cmd, **kw):
            seen["cmd"] = cmd
            return P()

        with mock.patch.object(push.subprocess, "run", fake):
            p = push._run_send(
                ["message", "send", "--channel", "qqbot",
                 "--target", "group:abc", "--message", "BTC 4h 做多"],
                {"push_ssh": "qsp"})
        self.assertEqual(p.returncode, 0)
        cmd = seen["cmd"]
        self.assertEqual(cmd[:2], ["ssh", "-T"])
        self.assertIn("qsp", cmd)
        self.assertIn("openclaw message send", cmd[-1])
        self.assertIn("'BTC 4h 做多'", cmd[-1])

    def test_local_when_no_ssh(self):
        seen = {}

        class P:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake(cmd, **kw):
            seen["cmd"] = cmd
            return P()

        with mock.patch.object(push.subprocess, "run", fake):
            push._run_send(["message", "send"], {})
        self.assertNotEqual(seen["cmd"][0], "ssh")


if __name__ == "__main__":
    unittest.main()
