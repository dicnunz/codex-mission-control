#!/bin/zsh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
LABEL="${CODEX_RELAY_LABEL:-com.codexrelay.agent}"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PYTHON="/usr/bin/python3"
RUNTIME="$HOME/Library/Application Support/CodexRelay"
STATE_DIR="$RUNTIME/state"
WORKDIR="$HOME"

fail_install() {
  printf "fail: %s\n" "$1" >&2
  printf "diagnostics: ./scripts/status.sh --tail 120\n" >&2
  printf "retry from a logged-in macOS Terminal as this user; do not use sudo for this user LaunchAgent.\n" >&2
  exit "${2:-1}"
}

warn_install() {
  printf "warn: %s\n" "$1" >&2
}

launchctl_optional() {
  local description="$1"
  shift
  local output
  output="$(mktemp -t codex-relay-launchctl.XXXXXX)"
  if "$@" >"$output" 2>&1; then
    rm -f "$output"
    return 0
  fi
  warn_install "$description failed; continuing because the service may not exist yet"
  sed -n '1,20p' "$output" >&2
  rm -f "$output"
  return 0
}

launchctl_required() {
  local description="$1"
  shift
  local output rc
  output="$(mktemp -t codex-relay-launchctl.XXXXXX)"
  if "$@" >"$output" 2>&1; then
    cat "$output"
    rm -f "$output"
    return 0
  fi
  rc=$?
  printf "launchctl output:\n" >&2
  sed -n '1,80p' "$output" >&2
  rm -f "$output"
  fail_install "$description failed with exit $rc"
}

if [ ! -f "$ROOT/.env" ]; then
  echo "Missing $ROOT/.env. Copy .env.example to .env and fill it first." >&2
  exit 2
fi

"$PYTHON" "$ROOT/codex_relay.py" --check-config >/dev/null || fail_install "repo config check failed" 2

mkdir -p "$HOME/Library/LaunchAgents" "$RUNTIME" "$STATE_DIR" || fail_install "could not create LaunchAgent runtime directories"
chmod 700 "$RUNTIME" "$STATE_DIR" || fail_install "could not make runtime directories private"
umask 077
: > "$STATE_DIR/launchd.out" || fail_install "could not create launch stdout log"
: > "$STATE_DIR/launchd.err" || fail_install "could not create launch stderr log"
chmod 600 "$STATE_DIR/launchd.out" "$STATE_DIR/launchd.err" || fail_install "could not make launch logs private"

install -m 700 "$ROOT/codex_relay.py" "$RUNTIME/codex_relay.py" || fail_install "could not install runtime script"

if ! "$PYTHON" - <<PY
from pathlib import Path
root = Path("$ROOT")
runtime = Path("$RUNTIME")
state_dir = Path("$STATE_DIR")
workdir = Path("$WORKDIR")
source = root / ".env"
target = runtime / ".env"
lines = source.read_text().splitlines()
updates = {
    "CODEX_RELAY_REPO_DIR": str(root),
    "CODEX_TELEGRAM_STATE_DIR": str(state_dir),
}
thinking_mode = ""
for line in lines:
    if line.startswith("CODEX_TELEGRAM_THINKING_MODE="):
        thinking_mode = line.split("=", 1)[1].strip()
        break
if not thinking_mode:
    for line in lines:
        if line.startswith("CODEX_TELEGRAM_REASONING_EFFORT="):
            thinking_mode = line.split("=", 1)[1].strip()
            break
updates["CODEX_TELEGRAM_THINKING_MODE"] = thinking_mode or "xhigh"
max_images = ""
for line in lines:
    if line.startswith("CODEX_TELEGRAM_MAX_IMAGES_PER_MESSAGE="):
        max_images = line.split("=", 1)[1].strip()
        break
updates["CODEX_TELEGRAM_MAX_IMAGES_PER_MESSAGE"] = max_images or "10"
defaults = {
    "CODEX_RELAY_GEMINI_ENABLED": "true",
    "CODEX_RELAY_GEMINI_MODEL": "gemini-3.1-flash-lite-preview",
    "CODEX_RELAY_GEMINI_MAX_OUTPUT_TOKENS": "4096",
    "CODEX_RELAY_GEMINI_NATURAL_COMMANDS": "true",
    "CODEX_RELAY_GEMINI_POLISH": "true",
    "CODEX_RELAY_GEMINI_TIMEOUT_SECONDS": "20",
    "CODEX_RELAY_GEMINI_ERROR_NOTICES": "true",
    "CODEX_RELAY_RECOVERY_TIMEOUT_SECONDS": "1200",
    "CODEX_RELAY_TERMINAL_BUFFER_CHARS": "20000",
    "CODEX_RELAY_TERMINAL_READ_LIMIT": "4000",
    "CODEX_RELAY_ALLOW_SENSITIVE_FILE_TRANSFER": "false",
    "CODEX_TELEGRAM_POLL_TIMEOUT_SECONDS": "25",
    "CODEX_TELEGRAM_POLL_HTTP_TIMEOUT_SECONDS": "60",
    "CODEX_TELEGRAM_MAX_FILE_BYTES": "20971520",
}
for key, fallback in defaults.items():
    value = ""
    for line in lines:
        if line.startswith(key + "="):
            value = line.split("=", 1)[1].strip()
            break
    updates[key] = value or fallback
has_workdir = any(
    line.startswith("CODEX_TELEGRAM_WORKDIR=")
    and line.split("=", 1)[1].strip()
    for line in lines
)
if not has_workdir:
    updates["CODEX_TELEGRAM_WORKDIR"] = str(workdir)
out = []
seen = set()
for line in lines:
    replaced = False
    for key, value in updates.items():
        if line.startswith(key + "="):
            out.append(key + "=" + value)
            seen.add(key)
            replaced = True
            break
    if not replaced:
        out.append(line)
for key, value in updates.items():
    if key not in seen:
        out.append(key + "=" + value)
target.write_text("\\n".join(out) + "\\n")
target.chmod(0o600)
PY
then
  fail_install "could not write runtime .env" 2
fi

if ! cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>$RUNTIME/codex_relay.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$RUNTIME</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>Umask</key>
  <integer>63</integer>
  <key>StandardOutPath</key>
  <string>$STATE_DIR/launchd.out</string>
  <key>StandardErrorPath</key>
  <string>$STATE_DIR/launchd.err</string>
</dict>
</plist>
PLIST
then
  fail_install "could not write LaunchAgent plist"
fi

chmod 600 "$PLIST" || fail_install "could not make LaunchAgent plist private"
plutil -lint "$PLIST" >/dev/null || fail_install "LaunchAgent plist is invalid"
"$PYTHON" "$RUNTIME/codex_relay.py" --check-config >/dev/null || fail_install "runtime config check failed" 2

launchctl_optional "launchctl bootout" launchctl bootout "gui/$(id -u)" "$PLIST"
launchctl_required "launchctl enable" launchctl enable "gui/$(id -u)/$LABEL"
launchctl_required "launchctl bootstrap" launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl_required "launchctl kickstart" launchctl kickstart -k "gui/$(id -u)/$LABEL"
launchctl_required "launchctl print" launchctl print "gui/$(id -u)/$LABEL"
