import os
import tempfile
import unittest
from unittest.mock import patch

from beagle.push import load_env_file, resolve_target


class TestPushEnv(unittest.TestCase):
    def test_load_env_file(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, ".beagle.env")
        with open(p, "w") as fh:
            fh.write("BEAGLE_QQ_TARGET='group:abc'\n# comment\nOTHER=1\n")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BEAGLE_QQ_TARGET", None)
            load_env_file(p)
            self.assertEqual(os.environ.get("BEAGLE_QQ_TARGET"), "group:abc")

    def test_resolve_prefers_env(self):
        with patch.dict(os.environ, {"BEAGLE_QQ_TARGET": "group:xyz"}):
            self.assertEqual(resolve_target({}, "/tmp/none.db"), "group:xyz")

    def test_missing_file_is_silent(self):
        load_env_file("/nonexistent/.beagle.env")


if __name__ == "__main__":
    unittest.main()
