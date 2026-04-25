#!/bin/zsh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
LABEL="${CODEX_RELAY_LABEL:-com.codexrelay.agent}"
RUNTIME="$HOME/Library/Application Support/CodexRelay"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

ok() { printf "ok: %s\n" "$1"; }
warn() { printf "warn: %s\n" "$1"; }
fail() { printf "fail: %s\n" "$1"; exit 1; }

cd "$ROOT"

[[ "$(uname -s)" == "Darwin" ]] && ok "macOS detected" || fail "Codex Relay is macOS-first"

if [[ -x "/Applications/Codex.app/Contents/Resources/codex" ]]; then
  ok "Codex app CLI found"
elif command -v codex >/dev/null 2>&1; then
  warn "using PATH codex; Codex app CLI not found at /Applications/Codex.app"
else
  fail "Codex CLI not found"
fi

[[ -f "$ROOT/.env" ]] && ok ".env exists" || warn ".env missing; run ./scripts/install.sh"

if [[ -f "$ROOT/.env" ]]; then
  "$ROOT/codex_relay.py" --check-config
fi

if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  ok "LaunchAgent is loaded"
else
  warn "LaunchAgent is not loaded"
fi

[[ -f "$PLIST" ]] && ok "plist exists" || warn "plist missing"
[[ -f "$RUNTIME/codex_relay.py" ]] && ok "runtime script exists" || warn "runtime script missing"
if [[ -f "$RUNTIME/codex_relay.py" ]]; then
  cmp -s "$ROOT/codex_relay.py" "$RUNTIME/codex_relay.py" && ok "runtime script matches repo" || warn "runtime script differs; run ./scripts/install_launch_agent.sh"
fi

python3 -m py_compile "$ROOT/codex_relay.py" "$ROOT/scripts/configure.py"
ok "python syntax"

PYTHONPATH="$ROOT" python3 "$ROOT/scripts/smoke_test.py"
