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

[[ "$(uname -s)" == "Darwin" ]] && ok "macOS detected" || fail "Codex Mission Control is macOS-first"

if [[ -x "/Applications/Codex.app/Contents/Resources/codex" ]]; then
  ok "Codex app CLI found"
elif command -v codex >/dev/null 2>&1; then
  warn "using PATH codex; Codex app CLI not found at /Applications/Codex.app"
else
  fail "Codex CLI not found"
fi

"$ROOT/cmc" doctor >/dev/null
ok "Mission Control doctor works"

if [[ -f "$ROOT/.env" ]]; then
  ok "repo .env exists"
  "$ROOT/codex_relay.py" --check-config
elif [[ -f "$RUNTIME/.env" ]]; then
  ok "runtime .env exists"
  (cd "$RUNTIME" && "$RUNTIME/codex_relay.py" --check-config)
else
  warn ".env missing; Mission Control Relay is not installed"
fi

launch_state="$(launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null || true)"
if [[ -n "$launch_state" ]] && printf "%s\n" "$launch_state" | grep -Eq "state = running|pid = [1-9][0-9]*"; then
  ok "LaunchAgent is running"
else
  warn "LaunchAgent is not running; install Relay with ./cmc relay install"
fi

[[ -f "$PLIST" ]] && ok "plist exists" || warn "plist missing; Relay not installed"
[[ -f "$RUNTIME/codex_relay.py" ]] && ok "runtime script exists" || warn "runtime script missing; Relay not installed"
[[ -f "$RUNTIME/mission_control.py" ]] && ok "runtime Mission Control module exists" || warn "runtime Mission Control module missing; Relay not installed"
[[ -d "$RUNTIME/templates/mission-control" ]] && ok "runtime templates exist" || warn "runtime templates missing; Relay not installed"
if [[ -f "$RUNTIME/codex_relay.py" ]]; then
  cmp -s "$ROOT/codex_relay.py" "$RUNTIME/codex_relay.py" && ok "runtime script matches repo" || fail "runtime script differs; run ./scripts/install_launch_agent.sh"
fi
if [[ -f "$RUNTIME/mission_control.py" ]]; then
  cmp -s "$ROOT/mission_control.py" "$RUNTIME/mission_control.py" && ok "runtime Mission Control module matches repo" || fail "runtime Mission Control module differs; run ./scripts/install_launch_agent.sh"
fi

shot="$(mktemp -t codex-relay-screen.XXXXXX.jpg)"
if screencapture -x -t jpg "$shot" >/dev/null 2>&1 && [[ -s "$shot" ]]; then
  ok "screenshot permission works"
else
  warn "screenshot permission blocked; allow Screen Recording for Terminal/Codex in System Settings"
fi
rm -f "$shot"

python3 -m py_compile "$ROOT/mission_control.py" "$ROOT/codex_relay.py" "$ROOT/scripts/configure.py"
ok "python syntax"

PYTHONPATH="$ROOT" python3 "$ROOT/scripts/smoke_test.py"
