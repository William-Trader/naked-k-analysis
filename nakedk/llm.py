# -----------------------------------------------------------------
# nakedk/llm.py - naked-k-analysis LLM adapter (stdlib only)
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-3CB98FE9
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
# -*- coding: utf-8 -*-
"""Optional LLM layer: chart commentary and guarded parameter proposals.

Configuration (highest priority first)
--------------------------------------
1. environment: NK_LLM_BASE / NK_LLM_MODEL / NK_LLM_KEY
2. JSON file: NK_LLM_CONFIG, else config/llm.local.json
3. built-in defaults (OpenAI-compatible endpoint)

The JSON file never needs to contain a key: point ``api_key_env`` at the
environment variable that holds it. A localhost endpoint (Ollama / vLLM)
does not require a key at all.

Design rules
------------
* No third-party SDK: plain OpenAI-compatible /chat/completions with urllib.
* No key = disabled, not broken. Every caller gets {"enabled": false}.
* The LLM never computes prices. It receives the deterministic engine output
  and may only (a) write commentary, (b) propose parameter deltas inside the
  hard bounds enforced by nakedk.symbol_params.
* Every response is cached by payload hash so a dashboard refresh does not
  spend tokens twice.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
CONFIG_PATH = os.environ.get("NK_LLM_CONFIG") or os.path.join(
    ROOT, "config", "llm.local.json")
CACHE_PATH = os.environ.get("NK_LLM_CACHE", os.path.join(
    ROOT, "state", "llm_cache.json"))
KEY_PATH = os.environ.get("NK_LLM_KEY_FILE", os.path.join(
    ROOT, "state", "llm.key"))
_LOCK = threading.RLock()

ANNOTATE_SYSTEM = (
    "你是价格行为（Al Brooks 体系）交易分析助手。只根据给定 JSON 事实写结论，"
    "不得编造价位或数据。输出严格 JSON，不要 Markdown 代码围栏。字段："
    "summary(一句话结论), bias(偏多/偏空/中性), key_levels(数组,最多4个"
    "{price,role}), scenario(触发后怎么走), invalidation(什么情况下判断失效),"
    "warnings(数组,最多3条), confidence_note(为何不是高置信)。"
)

TUNE_SYSTEM = (
    "你是量化参数审计员。输入包含某标的的当前参数、近期计划统计与允许范围。"
    "只能在允许键内提出小幅调整（单次不超过范围的15%），目标是减少亏损交易，"
    "不是提高交易数量。样本不足(计划<20或已结束<10)时必须返回空 patch。"
    "输出严格 JSON：{patch:{key:value},rationale:string,sample_note:string}。"
    "禁止输出范围外的键或非数字值。"
)


def _key_ok(key: str) -> bool:
    """Accept only a single ASCII token; reject pasted UI text / Chinese / newlines."""
    return bool(key) and key.isascii() and not any(c.isspace() for c in key) and len(key) >= 8


def _read_config(path=None):
    p = path or os.environ.get("NK_LLM_CONFIG") or CONFIG_PATH
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        return (data if isinstance(data, dict) else {}), p
    except Exception:
        return {}, p


def _file_key(path=None) -> str:
    p = path or os.environ.get("NK_LLM_KEY_FILE") or KEY_PATH
    try:
        with open(p, encoding="utf-8") as fh:
            return (fh.read() or "").strip()
    except Exception:
        return ""


def _settings(path=None, key_file=None) -> dict:
    """Resolve effective settings without ever exposing the key."""
    cfg, config_path = _read_config(path)
    base = (os.environ.get("NK_LLM_BASE") or cfg.get("base") or DEFAULT_BASE).rstrip("/")
    model = os.environ.get("NK_LLM_MODEL") or cfg.get("model") or DEFAULT_MODEL
    key_env = (cfg.get("api_key_env") or "NK_LLM_KEY").strip()
    key = os.environ.get("NK_LLM_KEY") or ""
    key_source = "env" if key else None
    if not key and key_env:
        key = os.environ.get(key_env) or ""
        key_source = "env" if key else None
    if not key:
        key = _file_key(key_file)
        key_source = "file" if key else None
    if not key and cfg.get("api_key"):
        key = str(cfg.get("api_key") or "")
        key_source = "config" if key else None
    key_invalid = bool(key) and not _key_ok(key)
    if key_invalid:
        key = ""
        key_source = "invalid"
    local = base.startswith(("http://127.0.0.1", "http://localhost",
                             "http://[::1]", "http://0.0.0.0"))
    require_key = bool(cfg.get("require_key", not local))
    configured_on = cfg.get("enabled", True) is not False
    enabled = configured_on and (bool(key) or not require_key)
    reason = None
    if not configured_on:
        reason = "配置中 enabled=false"
    elif key_invalid:
        reason = "API Key 格式错误：只允许 ASCII 字符，不要带空格、换行或中文"
    elif require_key and not key:
        reason = "缺少环境变量 %s（或 NK_LLM_KEY）" % (key_env or "NK_LLM_KEY")
    return {
        "enabled": enabled,
        "base": base,
        "model": model,
        "key": key,
        "key_valid": bool(key) and _key_ok(key),
        "key_invalid": key_invalid,
        "key_source": key_source,
        "key_env": key_env,
        "key_file": key_file or os.environ.get("NK_LLM_KEY_FILE") or KEY_PATH,
        "requires_key": require_key,
        "local": local,
        "config_path": config_path,
        "config_exists": os.path.exists(config_path),
        "timeout": int(cfg.get("timeout") or 45),
        "reason": reason,
    }


def status() -> dict:
    s = _settings()
    return {
        "enabled": bool(s["enabled"]),
        "model": s["model"] if s["enabled"] else None,
        "base": s["base"] if s["enabled"] else None,
        "features": ["chart_commentary", "guarded_param_tuning"]
        if s["enabled"] else [],
        "reason": s["reason"],
        "config_path": s["config_path"],
        "config_exists": s["config_exists"],
        "key_env": s["key_env"],
        "key_source": s["key_source"],
        "key_configured": bool(s["key_valid"]),
        "key_invalid": s["key_invalid"],
        "key_file": s["key_file"],
        "requires_key": s["requires_key"],
        "local": s["local"],
    }


def save_key(key: str, path=None) -> dict:
    """Store a key in a 0600 local file. Never return or log the value."""
    key = (key or "").strip()
    if not key:
        return {"ok": False, "error": "empty_key"}
    if not _key_ok(key):
        return {"ok": False, "error": "API Key 格式错误：只允许 ASCII 字符，不要带空格、换行或中文"}
    p = path or os.environ.get("NK_LLM_KEY_FILE") or KEY_PATH
    try:
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        tmp = p + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(key + "\n")
        os.replace(tmp, p)
        try:
            os.chmod(p, 0o600)
        except Exception:
            pass
        return {"ok": True, "status": status()}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def clear_key(path=None) -> dict:
    p = path or os.environ.get("NK_LLM_KEY_FILE") or KEY_PATH
    try:
        if os.path.exists(p):
            os.remove(p)
        return {"ok": True, "status": status()}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _post(url, payload, headers, timeout):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def chat(messages, max_tokens=700, temperature=0.2, timeout=None):
    s = _settings()
    if not s["enabled"]:
        return {"enabled": False, "error": "llm_disabled", "reason": s["reason"]}
    headers = {}
    if s["key"]:
        headers["Authorization"] = "Bearer " + s["key"]
    payload = {"model": s["model"], "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens}
    try:
        data = _post(s["base"] + "/chat/completions", payload, headers,
                     timeout or s["timeout"])
        content = (((data.get("choices") or [{}])[0].get("message") or {})
                   .get("content") or "")
        return {"enabled": True, "content": content,
                "model": data.get("model") or s["model"],
                "usage": data.get("usage") or {}}
    except Exception as e:
        return {"enabled": True, "error": str(e)[:300]}


def _json_block(text):
    if not text:
        return None
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r"\{.*\}", t, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


def _cache_key(kind, payload):
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return kind + ":" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def _cache_get(key):
    with _LOCK:
        try:
            with open(CACHE_PATH, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            return None
    item = data.get(key)
    if not item:
        return None
    if time.time() * 1000 - int(item.get("at") or 0) > 6 * 3600_000:
        return None
    return item.get("value")


def _cache_put(key, value):
    with _LOCK:
        try:
            with open(CACHE_PATH, encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
        data[key] = {"at": int(time.time() * 1000), "value": value}
        if len(data) > 120:
            for k in list(data)[:30]:
                data.pop(k, None)
        try:
            os.makedirs(os.path.dirname(CACHE_PATH) or ".", exist_ok=True)
            tmp = CACHE_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False)
            os.replace(tmp, CACHE_PATH)
        except Exception:
            pass


def annotate(payload, use_cache=True):
    """LLM commentary for one symbol/interval. Never raises."""
    s = _settings()
    if not s["enabled"]:
        return {"enabled": False, "reason": s["reason"], "error": "llm_disabled"}
    key = _cache_key("annotate", payload)
    if use_cache:
        hit = _cache_get(key)
        if hit:
            return {"enabled": True, "cached": True, **hit}
    res = chat([{"role": "system", "content": ANNOTATE_SYSTEM},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False,
                                                       default=str)}])
    if not res.get("enabled") or res.get("error"):
        return {"enabled": True, "error": res.get("error", "llm_error")}
    obj = _json_block(res.get("content"))
    if not isinstance(obj, dict):
        return {"enabled": True, "error": "llm_bad_json",
                "raw": (res.get("content") or "")[:400]}
    out = {
        "summary": str(obj.get("summary") or "")[:300],
        "bias": str(obj.get("bias") or "")[:16],
        "key_levels": obj.get("key_levels")[:4] if isinstance(obj.get("key_levels"), list) else [],
        "scenario": str(obj.get("scenario") or "")[:400],
        "invalidation": str(obj.get("invalidation") or "")[:300],
        "warnings": obj.get("warnings")[:3] if isinstance(obj.get("warnings"), list) else [],
        "confidence_note": str(obj.get("confidence_note") or "")[:240],
        "model": res.get("model"),
    }
    _cache_put(key, out)
    return {"enabled": True, "cached": False, **out}


def propose_params(payload, allowed: dict, bounds: dict, use_cache=False):
    """Ask for a small, bounded parameter patch. Caller still validates."""
    s = _settings()
    if not s["enabled"]:
        return {"enabled": False, "reason": s["reason"], "error": "llm_disabled"}
    key = _cache_key("tune", payload)
    if use_cache:
        hit = _cache_get(key)
        if hit:
            return {"enabled": True, "cached": True, **hit}
    send = dict(payload)
    send["allowed_keys"] = sorted(allowed.keys())
    send["bounds"] = {k: list(v) for k, v in (bounds or {}).items()}
    res = chat([{"role": "system", "content": TUNE_SYSTEM},
                {"role": "user", "content": json.dumps(send, ensure_ascii=False,
                                                       default=str)}],
               max_tokens=700, temperature=0.1)
    if not res.get("enabled") or res.get("error"):
        return {"enabled": True, "error": res.get("error", "llm_error")}
    obj = _json_block(res.get("content")) or {}
    patch = obj.get("patch") if isinstance(obj.get("patch"), dict) else {}
    clean = {}
    for k, v in patch.items():
        if k in allowed and isinstance(v, (int, float)) and not isinstance(v, bool):
            clean[k] = v
    out = {
        "patch": clean,
        "rationale": str(obj.get("rationale") or "")[:500],
        "sample_note": str(obj.get("sample_note") or "")[:200],
        "model": res.get("model"),
    }
    _cache_put(key, out)
    return {"enabled": True, "cached": False, **out}


def probe():
    """One cheap round-trip used by scripts/llm_check.py."""
    return chat([{"role": "user", "content": "只回复 OK"}], max_tokens=8,
                temperature=0)
