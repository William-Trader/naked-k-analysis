#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/naked-k-analysis}"
PY="${PYTHON:-python3}"

echo "[1/6] Python check"
"$PY" -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"'

echo "[2/6] Copy files to $APP_DIR"
sudo mkdir -p "$APP_DIR"
sudo rsync -a --delete-excluded --exclude .git --exclude __pycache__ --exclude beagle.db --exclude .beagle.env ./ "$APP_DIR/"

echo "[3/6] Unit tests"
(cd "$APP_DIR" && "$PY" -m unittest discover -s tests)

echo "[4/6] Environment template"
if [ ! -f "$APP_DIR/.beagle.env" ]; then
  cp "$APP_DIR/config/beagle.env.example" "$APP_DIR/.beagle.env"
fi
chmod 600 "$APP_DIR/.beagle.env"

echo "[5/6] systemd units"
sudo cp "$APP_DIR"/deploy/beagle-monitor.service "$APP_DIR"/deploy/beagle-push.service "$APP_DIR"/deploy/beagle-push.timer "$APP_DIR"/deploy/nakedk-dashboard.service /etc/systemd/system/
sudo sed -i "s#/opt/naked-k-analysis#$APP_DIR#g" /etc/systemd/system/beagle-monitor.service /etc/systemd/system/beagle-push.service /etc/systemd/system/nakedk-dashboard.service
sudo systemctl daemon-reload

echo "[6/6] Enable services"
sudo systemctl enable --now beagle-monitor beagle-push.timer nakedk-dashboard

cat <<EOF
Done.
Next:
1. Edit $APP_DIR/.beagle.env  -> BEAGLE_QQ_TARGET=group:<openid>
2. Copy $APP_DIR/config/openclaw.example.json to ~/.openclaw/openclaw.json and fill appId/clientSecret
3. sudo systemctl restart beagle-push
4. Dashboard: http://<host>:8080/
5. Chat route: append the price-action section from AGENT-SETUP.md to AGENTS.md
EOF
