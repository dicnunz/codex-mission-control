#!/bin/zsh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
LABEL="${CODEX_RELAY_LABEL:-com.codexrelay.agent}"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PYTHON="/usr/bin/python3"
RUNTIME="$HOME/Library/Application Support/CodexRelay"
STATE_DIR="$RUNTIME/state"
WORKDIR="$HOME"

if [ ! -f "$ROOT/.env" ]; then
  echo "Missing $ROOT/.env. Copy .env.example to .env and fill it first." >&2
  exit 2
fi

mkdir -p "$HOME/Library/LaunchAgents" "$RUNTIME" "$STATE_DIR"
chmod 700 "$RUNTIME" "$STATE_DIR"
umask 077

install -m 700 "$ROOT/codex_relay.py" "$RUNTIME/codex_relay.py"

python3 - <<PY
from pathlib import Path
root = Path("$ROOT")
runtime = Path("$RUNTIME")
state_dir = Path("$STATE_DIR")
workdir = Path("$WORKDIR")
source = root / ".env"
target = runtime / ".env"
lines = source.read_text().splitlines()
updates = {
    "CODEX_TELEGRAM_STATE_DIR": str(state_dir),
}
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

cat > "$PLIST" <<PLIST
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
  <key>StandardOutPath</key>
  <string>$STATE_DIR/launchd.out</string>
  <key>StandardErrorPath</key>
  <string>$STATE_DIR/launchd.err</string>
</dict>
</plist>
PLIST

chmod 600 "$PLIST"

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/$LABEL"
launchctl print "gui/$(id -u)/$LABEL" | sed -n '1,40p'
