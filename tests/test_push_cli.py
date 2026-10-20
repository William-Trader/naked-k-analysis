import os
import unittest
from unittest.mock import patch

from beagle.push import cli_path


class TestCliPath(unittest.TestCase):
    def test_env_override(self):
        with patch.dict(os.environ, {"BEAGLE_OPENCLAW_CLI": "/bin/sh"}):
            self.assertEqual(cli_path(), "/bin/sh")

    def test_falls_back_to_name(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BEAGLE_OPENCLAW_CLI", None)
            self.assertIsInstance(cli_path(), str)


if __name__ == "__main__":
    unittest.main()
