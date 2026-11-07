# -----------------------------------------------------------------
# scripts/llm_check.py - naked-k-analysis LLM config check
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-F5B11130
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
"""LLM configuration / connectivity check (never prints the key)."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nakedk import llm


def main() -> int:
    st = llm.status()
    print(json.dumps({"status": st}, ensure_ascii=False, indent=2))
    if "--ping" not in sys.argv:
        print("\n加 --ping 做一次真实请求（会消耗少量 token）。")
        return 0 if st.get("enabled") else 2
    if not st.get("enabled"):
        print("\n未启用，未发送请求。补齐上面的 reason 后重试。")
        return 2
    res = llm.probe()
    print(json.dumps({"probe": res}, ensure_ascii=False, indent=2))
    return 0 if res.get("content") else 1


if __name__ == "__main__":
    raise SystemExit(main())
