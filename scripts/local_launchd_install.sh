#!/usr/bin/env bash
# WM: NKA-LAUNCHD00
# SPDX-License-Identifier: LicenseRef-NKA-Personal-1.0
# Install launchd agents for the local macOS deploy.
set -euo pipefail

APP_DIR="${1:?usage: local_launchd_install.sh <app_dir> <python>}"
PY="${2:-python3}"
AGENTS_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$AGENTS_DIR"

cat > "$AGENTS_DIR/com.william.nakedk-dashboard.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.william.nakedk-dashboard</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>dashboard/server.py</string>
  </array>
  <key>WorkingDirectory</key><string>$APP_DIR</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PORT</key><string>8080</string>
    <key>PYTHONPATH</key><string>$APP_DIR</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict>
</plist>
PLIST

cat > "$AGENTS_DIR/com.william.beagle-monitor.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.william.beagle-monitor</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>-m</string>
    <string>beagle</string>
    <string>monitor</string>
    <string>--config</string>
    <string>config/beagle.json</string>
  </array>
  <key>WorkingDirectory</key><string>$APP_DIR</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key><string>$APP_DIR</string>
    <key>BEAGLE_CONFIG</key><string>$APP_DIR/config/beagle.json</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StartInterval</key><integer>60</integer>
</dict>
</plist>
PLIST

echo "Installed launchd agents to $AGENTS_DIR"
echo "Enable with:  launchctl load ~/Library/LaunchAgents/com.william.nakedk-dashboard.plist"
echo "              launchctl load ~/Library/LaunchAgents/com.william.beagle-monitor.plist"
