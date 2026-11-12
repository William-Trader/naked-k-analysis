#!/usr/bin/env bash
# Install the price-action skill into the server-side OpenClaw home.
set -euo pipefail
APP_DIR="${APP_DIR:-/home/ubuntu/nakedk-dashboard}"
OC_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
SRC="$APP_DIR/skills/price-action-analyst/SKILL.md"
DEST_DIR="$OC_HOME/skills/price-action-analyst"

if [ ! -f "$SRC" ]; then
  echo "missing $SRC" >&2; exit 1
fi
mkdir -p "$DEST_DIR"
cp -f "$SRC" "$DEST_DIR/SKILL.md"

AG_DIR="$OC_HOME/workspace"
AG="$AG_DIR/AGENTS.md"
# 幂等：以段落标题作为固定字符串标记，已存在则不再追加。
# 同时确保 workspace/AGENTS.md 存在——原逻辑以 [ -f "$AG" ] 为前提，
# 文件不存在时会静默跳过，导致指针段落永远丢失。
MARKER="## 价格行为系统"
mkdir -p "$AG_DIR"
if [ ! -f "$AG" ]; then
  : > "$AG"
fi
if ! grep -qF "$MARKER" "$AG"; then
  {
    echo ""
    echo "## 价格行为系统"
    echo "- 处理任何行情/价格行为请求前，先读 skill price-action-analyst。"
    echo "- 数据入口：python3 $APP_DIR/pa_fetch.py BTCUSDT ETHUSDT"
    echo "- 输出必须遵循一屏九行结构 + 结尾 SIGNAL 两行。"
  } >> "$AG"
fi

echo "skill installed: $DEST_DIR/SKILL.md"
echo "agents pointer: $AG"
echo "next: openclaw cron list --json  # then update the 4h job prompt to v13"
