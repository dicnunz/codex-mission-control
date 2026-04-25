#!/bin/zsh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$ROOT"

printf "Codex Relay local demo\n"
printf "No Telegram token needed. This runs smoke tests and prints the intended phone flow.\n\n"

PYTHONPATH="$ROOT" python3 "$ROOT/scripts/smoke_test.py"
printf "ok: local relay logic\n\n"

printf "Telegram > /alive\n"
printf "Codex Relay is live.\n"
printf "remote: Telegram -> LaunchAgent -> Codex CLI -> this Mac\n\n"

printf "Telegram > /tools\n"
printf "Working: job 8f31c2a0\n"
printf "Computer Use ok; Telegram running; ChatGPT Atlas running\n\n"

printf "Telegram > send a screenshot and ask what changed\n"
printf "Working: job 34bd91aa; attachments: 1 image\n"
printf "Codex receives the private image path with --image and replies back to Telegram.\n\n"

printf "Try the real bot after install:\n"
printf "./scripts/install.sh\n"
