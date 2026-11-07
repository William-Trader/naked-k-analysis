# -----------------------------------------------------------------
# nakedk/llm.py - naked-k-analysis LLM adapter (stdlib only)
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-3CB98FE9
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
# -*- coding: utf-8 -*-
"""Optional LLM layer: chart commentary and guarded parameter proposals.

Design rules
------------
* No third-party SDK: a plain OpenAI-compatible /chat/completions call with
  urllib. Works with OpenAI, DeepSeek, Moonshot, vLLM, Ollama gateways.
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

BASE = os.environ.get("NK_LLM_BASE", "https://api.openai.com/v1").rstrip("/")
KEY = os.environ.get("NK_LLM_KEY") or os.environ.get("OPENAI_API_KEY") or ""
MODEL = os.environ.get("NK_LLM_MODEL", "gpt-4o-mini")
CACHE_PATH = os.environ.get("NK_LLM_CACHE", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "state", "llm_cache.json"))
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


def status() -> dict:
    return {
        "enabled": bool(KEY),
        "model": MODEL if KEY else None,
        "base": BASE if KEY else None,
        "features": ["chart_commentary", "guarded_param_tuning"] if KEY else [],
        "reason": None if KEY else "未配置 NK_LLM_KEY（设置环境变量后启用）",
    }


def _post(url, payload, headers, timeout):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def chat(messages, max_tokens=700, temperature=0.2, timeout=45):
    if not KEY:
        return {"enabled": False, "error": "llm_disabled"}
    payload = {"model": MODEL, "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens}
    try:
        data = _post(BASE + "/chat/completions", payload,
                     {"Authorization": "Bearer " + KEY}, timeout)
        content = (((data.get("choices") or [{}])[0].get("message") or {})
                   .get("content") or "")
        return {"enabled": True, "content": content,
                "model": data.get("model") or MODEL,
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
    if not KEY:
        return {"enabled": False, "reason": "llm_disabled"}
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
    if not KEY:
        return {"enabled": False, "reason": "llm_disabled"}
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
