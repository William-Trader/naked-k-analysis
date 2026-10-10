#!/bin/bash
# -----------------------------------------------------------------
# scripts/pa_run.sh - naked-k-analysis core price-action data/deploy logic
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-B3E5AC11
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
cd /home/user
openclaw agent --agent main --session-key agent:main:pa-report --message-file /home/user/pa_agent_msg.txt
