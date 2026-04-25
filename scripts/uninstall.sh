#!/bin/zsh
set -eu

LABEL="${CODEX_RELAY_LABEL:-com.codexrelay.agent}"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
echo "Stopped Codex Relay. Runtime files remain in ~/Library/Application Support/CodexRelay."
