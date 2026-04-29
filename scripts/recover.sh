#!/bin/zsh
set -u

ROOT="${CODEX_RELAY_REPO_DIR:-$(cd "$(dirname "$0")/.." && pwd -P)}"
MODE="${1:-codex}"

cd "$ROOT" || exit 2

say() {
  printf "%s\n" "$1"
}

run_step() {
  say "==> $*"
  "$@"
}

say "Codex Relay recovery"
say "repo: $ROOT"
say "mode: $MODE"

run_step python3 -m py_compile "$ROOT/codex_relay.py" "$ROOT/scripts/configure.py" || exit $?
say "==> python3 $ROOT/scripts/smoke_test.py"
PYTHONPATH="$ROOT" python3 "$ROOT/scripts/smoke_test.py" || exit $?

if [[ "$MODE" == "restart" || "$MODE" == "reinstall" ]]; then
  run_step "$ROOT/scripts/install_launch_agent.sh" || exit $?
  run_step "$ROOT/scripts/status.sh" || true
  exit 0
fi

CODEX="${CODEX_BIN:-codex}"
if ! command -v "$CODEX" >/dev/null 2>&1 && [[ ! -x "$CODEX" ]]; then
  say "Codex CLI not found: $CODEX"
  say "Use /recover restart after fixing CODEX_BIN."
  exit 127
fi

MODEL="${CODEX_TELEGRAM_MODEL:-gpt-5.5}"
THINKING="${CODEX_TELEGRAM_THINKING_MODE:-${CODEX_TELEGRAM_REASONING_EFFORT:-high}}"
SANDBOX="${CODEX_TELEGRAM_SANDBOX:-danger-full-access}"

PROMPT="You are repairing the local codex-relay checkout.

Goal: make the Telegram relay healthy without exposing secrets.

Rules:
- Do not read, print, modify, or summarize .env values, bot tokens, private keys, runtime state, screenshots, or private logs.
- Do not commit or push.
- Inspect the code and scripts needed for relay startup, Telegram handling, queueing, terminal sessions, file transfer, recovery, and tests.
- Make the smallest safe fixes if anything is broken.
- Run: python3 -m py_compile codex_relay.py scripts/configure.py
- Run: PYTHONPATH=. python3 scripts/smoke_test.py
- If installer/startup changed, run ./scripts/doctor.sh and ./scripts/status.sh when safe.
- Finish with a terse summary of changed files and verification.
"

say "==> codex self-repair"
printf "%s" "$PROMPT" | "$CODEX" exec \
  -c "sandbox_mode=\"$SANDBOX\"" \
  -c 'approval_policy="never"' \
  -c "model_reasoning_effort=\"$THINKING\"" \
  --model "$MODEL" \
  --skip-git-repo-check \
  -
CODEX_EXIT=$?

say "==> post-check"
python3 -m py_compile "$ROOT/codex_relay.py" "$ROOT/scripts/configure.py" || exit $?
PYTHONPATH="$ROOT" python3 "$ROOT/scripts/smoke_test.py" || exit $?
"$ROOT/scripts/status.sh" || true

exit "$CODEX_EXIT"
