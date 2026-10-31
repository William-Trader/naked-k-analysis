#!/usr/bin/env bash
# -----------------------------------------------------------------
# bootstrap-local.sh - naked-k-analysis local workstation deploy
# (c) 2026 William-Trader
# WM: NKA-LOCALB00T
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Removing this mark violates the license.
# -----------------------------------------------------------------
# Deploy to a local computer (macOS / Linux) WITHOUT sudo or systemd.
# Starts the dashboard and the 5-minute event monitor in the foreground,
# or installs a launchd (macOS) / cron (Linux) entry to keep them running.
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/naked-k-analysis}"
PY="${PYTHON:-python3}"

echo "[1/5] Python check"
"$PY" -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"'

echo "[2/5] Copy files to $APP_DIR"
mkdir -p "$APP_DIR"
rsync -a --exclude .git --exclude __pycache__ --exclude beagle.db --exclude .beagle.env ./ "$APP_DIR/"

echo "[3/5] Unit tests"
(cd "$APP_DIR" && "$PY" -m unittest discover -s tests)

echo "[4/5] Config"
if [ ! -f "$APP_DIR/.beagle.env" ]; then
  cp "$APP_DIR/config/beagle.env.example" "$APP_DIR/.beagle.env"
fi
chmod 600 "$APP_DIR/.beagle.env"
# Default the local config to crypto majors only (realtime universe).
if [ ! -f "$APP_DIR/config/beagle.json" ]; then
  cp "$APP_DIR/config/beagle.json" "$APP_DIR/config/beagle.json"
fi

echo "[5/5] Run locally"
if command -v launchctl >/dev/null 2>&1 && [ "$(uname -s)" = "Darwin" ]; then
  bash "$APP_DIR/scripts/local_launchd_install.sh" "$APP_DIR" "$PY"
  echo "macOS: launchd agents installed. Start them with:"
  echo "  launchctl load ~/Library/LaunchAgents/com.william.nakedk-dashboard.plist"
  echo "  launchctl load ~/Library/LaunchAgents/com.william.beagle-monitor.plist"
else
  echo "Linux workstation: run the services in tmux or via cron:"
  echo "  cd $APP_DIR && PYTHONPATH=. PORT=8080 $PY dashboard/server.py"
  echo "  cd $APP_DIR && PYTHONPATH=. BEAGLE_CONFIG=config/beagle.json $PY -m beagle monitor --config config/beagle.json"
  echo "  (cron every 5 min) $PY -m beagle push --send"
fi

cat <<EOF
Done (local). Quick commands:
  fetch XAU:      cd $APP_DIR && PYTHONPATH=. $PY -m nakedk fetch XAU SPX
  signal XAU:     cd $APP_DIR && PYTHONPATH=. $PY -m nakedk signal XAU SPX
  backtest XAU:   cd $APP_DIR && PYTHONPATH=. $PY -m nakedk backtest XAU --days 365 --folds 8
  dashboard:      cd $APP_DIR && PYTHONPATH=. PORT=8080 $PY dashboard/server.py
Note: XAU / US indices / futures are the analysis source base (Yahoo public data);
realtime 1m/5m monitoring stays on the crypto majors (BTC / ETH).
EOF
