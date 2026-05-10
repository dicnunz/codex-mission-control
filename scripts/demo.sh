#!/bin/zsh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$ROOT"

printf "Codex Mission Control local demo\n"
printf "No Telegram token needed. This proves the hub, lane lock, packet, and phone flow.\n\n"

PYTHONPATH="$ROOT" python3 "$ROOT/scripts/smoke_test.py"
printf "ok: local Mission Control + Relay logic\n\n"

demo_hub="$(mktemp -d)"
trap 'rm -rf "$demo_hub"' EXIT
"$ROOT/cmc" --hub "$demo_hub" init >/dev/null
"$ROOT/cmc" --hub "$demo_hub" discover "$ROOT" >/dev/null
"$ROOT/cmc" --hub "$demo_hub" claim BROWSER DEMO "show lane locking" >/dev/null

printf "Mac > cmc status\n"
"$ROOT/cmc" --hub "$demo_hub" status
printf "\n"

printf "Mac > cmc claim BROWSER OTHER \"second chat\"\n"
if "$ROOT/cmc" --hub "$demo_hub" claim BROWSER OTHER "second chat" >/tmp/cmc-demo-double-claim.out 2>&1; then
  printf "expected second claim to fail\n" >&2
  exit 1
fi
cat /tmp/cmc-demo-double-claim.out
rm -f /tmp/cmc-demo-double-claim.out
printf "\n"

printf "Mac > cmc packet\n"
"$ROOT/cmc" --hub "$demo_hub" packet --mission DEMO --action "send public reply" --target "x.com thread" --object "exact reply text" --proof "proof/screenshot.png" --risk "public post" --why "user approved packet" --stop "after one reply"
printf "\n"

printf "Mac > cmc lanes\n"
"$ROOT/cmc" --hub "$demo_hub" lanes
printf "\n"

"$ROOT/cmc" --hub "$demo_hub" release BROWSER DEMO >/dev/null

printf "Telegram > /mission status\n"
printf "Codex Mission Control status comes back from the Mac.\n\n"

printf "Telegram > /policy\n"
printf "Allowed local Mac work; stops before public, account, payment, delete, or confirmation-sensitive actions.\n\n"

printf "Telegram > /screenshot\n"
printf "Mac screenshot returned to Telegram.\n\n"

printf "Sample Telegram > /health after install\n"
printf "health: token set; allowlist configured; Codex CLI found\n\n"

printf "Telegram > /tools\n"
printf "Working: job 8f31c2a0\n"
printf "Codex checks the local toolbelt and reports exact blockers.\n\n"

printf "Telegram > send a screenshot and ask what changed\n"
printf "Working: job 34bd91aa; attachments: 1 image\n"
printf "Codex receives the private image path with --image and replies back to Telegram.\n\n"

printf "Try the real bot after install:\n"
printf "./scripts/install.sh\n"
printf "\n"

printf "If this maps your workflow:\n"
printf "Run the route checker: https://dicnunz.github.io/codex-operator-sprint/workflow-route-checker.html\n"
printf "Buy the \$149 written mini-audit: https://nicdunz.gumroad.com/l/agent-workflow-mini-audit\n"
printf "Buy the \$750 workflow audit: https://nicdunz.gumroad.com/l/agent-workflow-audit\n"
