# -----------------------------------------------------------------
# nakedk/http.py - naked-k-analysis core price-action engine
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-F913E3A2
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
# -*- coding: utf-8 -*-
"""共享 HTTP 助手：JSON GET，带指数退避 + 抖动重试（stdlib only）。

覆盖评审缺口 #1：429（限频）/ 418（IP 风控）/ 5xx / 超时 / 网络抖动 都做
退避重试；其余 4xx（400/404 等参数错误）立即抛出；尊重 Retry-After。
"""
from __future__ import annotations

import json
import os
import random
import ssl
import time
import urllib.error
import urllib.request

UA = {"User-Agent": "naked-k-analysis/2.1"}
RETRYABLE_HTTP = {429, 418}

# Common system CA bundles. Some Python installs ship an incomplete bundled
# cert.pem (e.g. the python.org macOS framework build); falling back to the
# OS trust store keeps HTTPS working on those hosts without any new dependency.
_SYSTEM_CA_PATHS = (
    "/etc/ssl/cert.pem",                          # macOS (Homebrew/LibreSSL)
    "/etc/ssl/certs/ca-certificates.crt",          # Debian / Ubuntu
    "/etc/pki/tls/certs/ca-bundle.crt",            # RHEL / CentOS
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
)


def _ssl_context():
    """Return an SSL context that works even when the bundled CA is broken."""
    for cafile in _SYSTEM_CA_PATHS:
        if os.path.exists(cafile):
            try:
                return ssl.create_default_context(cafile=cafile)
            except Exception:
                continue
    try:
        return ssl.create_default_context()
    except Exception:
        return None


def _retry_after(err) -> float | None:
    """从 HTTPError 头里取 Retry-After（秒）；取不到返回 None。"""
    try:
        headers = getattr(err, "headers", None)
        ra = headers.get("Retry-After") if headers else None
        if ra and str(ra).strip():
            return float(ra)
    except Exception:
        pass
    return None


def get_json(url, timeout=15, max_retries=3, proxy=None):
    """GET + 解析 JSON；对瞬时错误退避重试，4xx 立即抛出。

    proxy: 可选 HTTP 代理地址（如 http://127.0.0.1:7890），仅在需要时走代理。
    """
    last = None
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url, headers=UA)
        ctx = _ssl_context()
        opener = None
        if proxy:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
                urllib.request.HTTPSHandler(context=ctx))
        try:
            if opener:
                with opener.open(req, timeout=timeout) as r:
                    return json.loads(r.read().decode())
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = e
            if e.code in RETRYABLE_HTTP or e.code >= 500:
                ra = _retry_after(e)
                wait = ra if ra is not None else (2.0 ** attempt)
            else:
                raise
        except (urllib.error.URLError, OSError) as e:
            last = e
            wait = 2.0 ** attempt
        if attempt < max_retries:
            time.sleep(wait + random.uniform(0, 0.5))
    raise last
