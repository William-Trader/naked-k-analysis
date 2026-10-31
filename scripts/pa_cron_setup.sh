#!/bin/bash
# -----------------------------------------------------------------
# scripts/pa_cron_setup.sh - naked-k-analysis core price-action data/deploy logic
# (c) 2026 William-Trader (https://github.com/William-Trader)
# WM: NKA-98995EAC
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
set -e
MSG="$(cat /home/user/pa_agent_msg.txt)"
openclaw cron add "pa-btc-eth-4h" \
  --cron "5 0,4,8,12,16,20 * * *" \
  --tz "Asia/Shanghai" \
  --agent main \
  --session isolated \
  --message "$MSG" \
  --announce \
  --channel qqbot \
  --to "group:REPLACE_WITH_QQ_GROUP_OPENID" \
  --timeout-seconds 300 \
  --display-name "价格行为简报-BTC/ETH-每4小时" \
  --description "BTC/ETH 价格行为简报推送到 QQ 群"
