#!/bin/zsh
set -eu

LABEL="${CODEX_RELAY_LABEL:-com.codexrelay.agent}"
RUNTIME="$HOME/Library/Application Support/CodexRelay"

launchctl print "gui/$(id -u)/$LABEL" | sed -n '1,45p'
echo
"$RUNTIME/codex_relay.py" --check-config
