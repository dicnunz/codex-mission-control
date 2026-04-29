#!/bin/zsh
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"

printf "Codex Relay installer\n"
printf "1. preflight local Mac requirements\n"
printf "2. verify Codex + Telegram bot token\n"
printf "3. allow-list your private Telegram DM\n"
printf "4. install the macOS LaunchAgent\n"
printf "5. run local health checks\n\n"

[[ "$(uname -s)" == "Darwin" ]] || {
  printf "Codex Relay is macOS-first because it installs a LaunchAgent.\n" >&2
  exit 1
}

command -v python3 >/dev/null 2>&1 || {
  printf "python3 is required.\n" >&2
  exit 1
}

if [[ -x "/Applications/Codex.app/Contents/Resources/codex" ]]; then
  printf "ok: Codex app CLI found\n"
elif command -v codex >/dev/null 2>&1; then
  printf "warn: using PATH codex; Codex app CLI not found at /Applications/Codex.app\n"
else
  printf "Codex CLI not found. Install and open the Codex Mac app first.\n" >&2
  exit 1
fi

printf "ok: macOS + python3 preflight\n\n"

python3 "$ROOT/scripts/configure.py"
printf "\nRunning doctor...\n"
"$ROOT/scripts/doctor.sh"

printf "\nDone. DM your bot:\n"
printf "/alive\n/health\n/policy\n/screenshot\n/tools\n/latency\n"
printf "\nOptional Gemini mobile harness powered by Flash 3.1 Lite:\n"
printf "/gemini key YOUR_GEMINI_API_KEY\n"
printf "\nOptional Mac control surface:\n./scripts/menu_bar.sh\n"
printf "\nLocal status page:\n./scripts/status_ui.sh\n"
