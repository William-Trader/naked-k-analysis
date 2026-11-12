#!/usr/bin/env bash
# 生产 101 部署：文件级覆盖同步。
# 路径以 deploy/INVENTORY.md 为唯一权威清单；生产目录不是 git 仓库。
# 同步为纯覆盖（不使用 --delete / --delete-excluded），绝不删除目标端独有文件。
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/apps/nakedk-dashboard}"
PY="${PYTHON:-python3}"

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) echo "usage: $0 [--dry-run]"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

# dry-run：只打印将要执行的写命令，不产生任何副作用
run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '[dry-run] '
    printf '%q ' "$@"
    printf '\n'
  else
    "$@"
  fi
}

RSYNC_EXCLUDES=(
  --exclude '.git/'
  --exclude '__pycache__/'
  --exclude '*.pyc'
  --exclude 'state/'
  --exclude '*.db'
  --exclude '*.key'
  --exclude '.env*'
  --exclude '.beagle.env'
  --exclude 'config/*.local.json'
)
RSYNC_FLAGS=(-a)
if [ "$DRY_RUN" -eq 1 ]; then
  RSYNC_FLAGS+=(--dry-run)
fi

echo "[1/6] Python check"
"$PY" -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"'

echo "[2/6] Sync files to $APP_DIR (see deploy/INVENTORY.md)"
run sudo mkdir -p "$APP_DIR"

# 覆盖前备份目标 beagle.db（带时间戳）；仅真实执行且文件已存在时。
# rsync 已排除 *.db，这里仍保留一道发布前安全网，防手工/后续步骤误覆盖。
TARGET_DB="$APP_DIR/beagle.db"
if [ -f "$TARGET_DB" ]; then
  BACKUP="$TARGET_DB.bak-$(date +%Y%m%d-%H%M%S)"
  echo "backup: $TARGET_DB -> $BACKUP"
  run sudo cp -p "$TARGET_DB" "$BACKUP"
fi

# 纯覆盖同步：不加 --delete / --delete-excluded，目标端独有文件一律保留
run sudo rsync "${RSYNC_FLAGS[@]}" "${RSYNC_EXCLUDES[@]}" ./ "$APP_DIR/"

echo "[3/6] Unit tests"
if [ "$DRY_RUN" -eq 0 ]; then
  (cd "$APP_DIR" && "$PY" -m unittest discover -s tests)
else
  echo "[dry-run] skip unit tests"
fi

echo "[4/6] Environment template"
if [ "$DRY_RUN" -eq 0 ]; then
  if [ ! -f "$APP_DIR/.beagle.env" ]; then
    run sudo cp "$APP_DIR/config/beagle.env.example" "$APP_DIR/.beagle.env"
  fi
  run sudo chmod 600 "$APP_DIR/.beagle.env"
else
  echo "[dry-run] skip .beagle.env provisioning"
fi

echo "[5/6] systemd units"
run sudo cp "$APP_DIR"/deploy/*.service "$APP_DIR"/deploy/*.timer /etc/systemd/system/
# 模板内已是生产权威绝对路径（deploy/INVENTORY.md）。默认 APP_DIR 下 sed 为 no-op；
# 若通过 APP_DIR 部署到其它目录，则把主链路路径一并改写，保持可定制。
run sudo sed -i "s#/opt/apps/nakedk-dashboard#$APP_DIR#g" \
  /etc/systemd/system/nakedk-dashboard.service \
  /etc/systemd/system/beagle-record.service \
  /etc/systemd/system/beagle-score.service \
  /etc/systemd/system/beagle-review.service
run sudo systemctl daemon-reload

echo "[6/6] Enable services (beagle-monitor / beagle-push.timer 2.1.1 起停用，不 enable)"
run sudo systemctl enable --now nakedk-dashboard

cat <<EOF
Done.
Next (paths per deploy/INVENTORY.md):
1. Dashboard PORT=8081, default bind 127.0.0.1; for external access set NK_DASH_HOST + NK_DASH_TOKEN.
2. Edit $APP_DIR/.beagle.env  -> BEAGLE_QQ_TARGET=group:<openid>
3. Copy $APP_DIR/config/openclaw.example.json to ~/.openclaw/openclaw.json and fill appId/clientSecret
4. Dashboard: http://127.0.0.1:8081/
5. Chat route: append the price-action section from AGENT-SETUP.md to AGENTS.md
EOF
