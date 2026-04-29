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

configured_codex=""
if [[ -f "$ROOT/.env" ]]; then
  configured_codex="$(sed -n 's/^CODEX_BIN=//p' "$ROOT/.env" | head -n 1)"
  configured_codex="${configured_codex#\"}"
  configured_codex="${configured_codex%\"}"
  configured_codex="${configured_codex#\'}"
  configured_codex="${configured_codex%\'}"
fi

if [[ -n "$configured_codex" && -x "$configured_codex" ]]; then
  ok "configured Codex CLI found"
elif [[ -x "/Applications/Codex.app/Contents/Resources/codex" ]]; then
  ok "Codex app CLI found"
elif command -v codex >/dev/null 2>&1; then
  warn "using PATH codex; Codex app CLI not found at /Applications/Codex.app"
else
  fail "Codex CLI not found"
fi

[[ -f "$ROOT/.env" ]] && ok ".env exists" || fail ".env missing; run ./scripts/install.sh"

if [[ -f "$ROOT/.env" ]]; then
  "$ROOT/codex_relay.py" --check-config
fi

launch_state="$(launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null || true)"
if [[ -n "$launch_state" ]] && printf "%s\n" "$launch_state" | grep -Eq "state = running|pid = [1-9][0-9]*"; then
  ok "LaunchAgent is running"
else
  fail "LaunchAgent is not running"
fi

[[ -f "$PLIST" ]] && ok "plist exists" || fail "plist missing"
[[ -f "$RUNTIME/codex_relay.py" ]] && ok "runtime script exists" || fail "runtime script missing"
if [[ -f "$RUNTIME/codex_relay.py" ]]; then
  cmp -s "$ROOT/codex_relay.py" "$RUNTIME/codex_relay.py" && ok "runtime script matches repo" || fail "runtime script differs; run ./scripts/install_launch_agent.sh"
fi

python3 -m py_compile "$ROOT/codex_relay.py" "$ROOT/scripts/configure.py"
ok "python syntax"

PYTHONPATH="$ROOT" python3 "$ROOT/scripts/smoke_test.py"
