#!/bin/zsh
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"

printf "Codex Relay installer\n"
printf "1. verify Codex + Telegram bot token\n"
printf "2. allow-list your Telegram DM\n"
printf "3. install the macOS LaunchAgent\n"
printf "4. run local health checks\n\n"

python3 "$ROOT/scripts/configure.py"
printf "\nRunning doctor...\n"
"$ROOT/scripts/doctor.sh"

printf "\nDone. DM your bot:\n"
printf "/alive\n/tools\n/latency\n"
