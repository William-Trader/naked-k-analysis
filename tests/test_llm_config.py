"""LLM configuration tests (no network, no real key)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

from nakedk import llm


def missing_key():
    return os.path.join(tempfile.mkdtemp(prefix="nk-nokey-"), "missing.key")


def write_cfg(cfg):
    d = tempfile.mkdtemp(prefix="nk-llm-")
    p = os.path.join(d, "llm.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)
    return p


class SettingsTest(unittest.TestCase):
    def test_example_file_is_valid_and_has_no_key(self):
        p = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "config", "llm.example.json")
        with open(p, encoding="utf-8") as fh:
            cfg = json.load(fh)
        self.assertIn("base", cfg)
        self.assertIn("model", cfg)
        self.assertNotIn("api_key", cfg)
        self.assertTrue(cfg.get("api_key_env"))

    def test_cloud_without_key_is_disabled(self):
        p = write_cfg({"base": "https://api.deepseek.com/v1",
                       "model": "deepseek-chat",
                       "api_key_env": "DEEPSEEK_API_KEY",
                       "require_key": True})
        env = {"NK_LLM_KEY": "", "DEEPSEEK_API_KEY": "",
               "NK_LLM_BASE": "", "NK_LLM_MODEL": ""}
        with mock.patch.dict(os.environ, env, clear=False):
            s = llm._settings(path=p, key_file=missing_key())
        self.assertFalse(s["enabled"])
        self.assertIn("DEEPSEEK_API_KEY", s["reason"])
        self.assertEqual(s["model"], "deepseek-chat")

    def test_key_enables_cloud(self):
        p = write_cfg({"base": "https://api.deepseek.com/v1",
                       "model": "deepseek-chat",
                       "api_key_env": "DEEPSEEK_API_KEY",
                       "require_key": True})
        env = {"NK_LLM_KEY": "", "DEEPSEEK_API_KEY": "test-key",
               "NK_LLM_BASE": "", "NK_LLM_MODEL": ""}
        with mock.patch.dict(os.environ, env, clear=False):
            s = llm._settings(path=p, key_file=missing_key())
        self.assertTrue(s["enabled"])
        self.assertEqual(s["key"], "test-key")

    def test_local_endpoint_needs_no_key(self):
        p = write_cfg({"base": "http://127.0.0.1:11434/v1",
                       "model": "qwen2.5:7b",
                       "api_key_env": "",
                       "require_key": False})
        env = {"NK_LLM_KEY": "", "NK_LLM_BASE": "", "NK_LLM_MODEL": ""}
        with mock.patch.dict(os.environ, env, clear=False):
            s = llm._settings(path=p, key_file=missing_key())
        self.assertTrue(s["enabled"])
        self.assertTrue(s["local"])

    def test_env_overrides_file(self):
        p = write_cfg({"base": "https://api.deepseek.com/v1",
                       "model": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY",
                       "require_key": True})
        env = {"NK_LLM_KEY": "k", "NK_LLM_BASE": "https://example.com/v1",
               "NK_LLM_MODEL": "custom-model"}
        with mock.patch.dict(os.environ, env, clear=False):
            s = llm._settings(path=p, key_file=missing_key())
        self.assertEqual(s["base"], "https://example.com/v1")
        self.assertEqual(s["model"], "custom-model")
        self.assertTrue(s["enabled"])

    def test_save_and_clear_key_file(self):
        d = tempfile.mkdtemp(prefix="nk-key-")
        key_path = os.path.join(d, "llm.key")
        cfg = write_cfg({"base": "https://api.deepseek.com/v1",
                         "model": "deepseek-chat",
                         "api_key_env": "DEEPSEEK_API_KEY",
                         "require_key": True})
        res = llm.save_key("test-key", path=key_path)
        self.assertTrue(res["ok"])
        self.assertEqual(os.stat(key_path).st_mode & 0o777, 0o600)
        env = {"NK_LLM_KEY": "", "DEEPSEEK_API_KEY": "",
               "NK_LLM_BASE": "", "NK_LLM_MODEL": ""}
        with mock.patch.dict(os.environ, env, clear=False):
            s = llm._settings(path=cfg, key_file=key_path)
        self.assertTrue(s["enabled"])
        self.assertEqual(s["key_source"], "file")
        llm.clear_key(path=key_path)
        self.assertFalse(os.path.exists(key_path))

    def test_status_never_returns_key(self):
        p = write_cfg({"base": "https://api.deepseek.com/v1",
                       "model": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY",
                       "require_key": True})
        env = {"NK_LLM_KEY": "", "DEEPSEEK_API_KEY": "", "NK_LLM_BASE": "",
               "NK_LLM_MODEL": "", "NK_LLM_KEY_FILE": missing_key()}
        with mock.patch.dict(os.environ, env, clear=False):
            st = llm.status()
        self.assertNotIn("key", st)
        self.assertIn("config_path", st)


if __name__ == "__main__":
    unittest.main()
