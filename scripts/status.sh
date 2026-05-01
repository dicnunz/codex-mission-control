#!/bin/zsh
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
LABEL="${CODEX_RELAY_LABEL:-com.codexrelay.agent}"
PYTHON="${CODEX_RELAY_PYTHON:-/usr/bin/python3}"
RUNTIME="$HOME/Library/Application Support/CodexRelay"
STATE_DIR="$RUNTIME/state"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
EXPECTED_PROGRAM="/usr/bin/python3"
TAIL_LINES="${CODEX_RELAY_STATUS_TAIL_LINES:-40}"
SHOW_LOGS=1
exit_status=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-tail)
      SHOW_LOGS=0
      ;;
    --tail)
      if [[ $# -lt 2 ]]; then
        printf "Missing line count for --tail\n" >&2
        exit 64
      fi
      shift
      TAIL_LINES="$1"
      ;;
    --help|-h)
      printf "Usage: %s [--tail lines|--no-tail]\n" "$0"
      exit 0
      ;;
    *)
      printf "Unknown option: %s\n" "$1" >&2
      exit 64
      ;;
  esac
  shift
done

if ! [[ "$TAIL_LINES" == <-> ]]; then
  TAIL_LINES=40
fi

fail_status() {
  printf "%s\n" "$1"
  exit_status=1
}

printf "label=%s\n" "$LABEL"
printf "repo=%s\n" "$ROOT"
printf "runtime=%s\n" "$RUNTIME"
printf "state_dir=%s\n" "$STATE_DIR"
printf "self_check_repo=\"%s\" \"%s\" --check-config\n" "$PYTHON" "$ROOT/codex_relay.py"
printf "self_check_runtime=\"%s\" \"%s\" --check-config\n" "$PYTHON" "$RUNTIME/codex_relay.py"
echo

if output="$(launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null)"; then
  printf "%s\n" "$output" | sed -n '1,45p'
  if printf "%s\n" "$output" | grep -Eq "state = running|pid = [1-9][0-9]*"; then
    printf "launch_state=running\n"
  else
    fail_status "launch_state=loaded_not_running"
  fi
else
  fail_status "launch_state=not_loaded"
fi
echo

if disabled_output="$(launchctl print-disabled "gui/$(id -u)" 2>/dev/null)"; then
  if printf "%s\n" "$disabled_output" | grep -Fq "\"$LABEL\" => true"; then
    fail_status "launch_disabled=true; run launchctl enable gui/$(id -u)/$LABEL"
  else
    printf "launch_disabled=false\n"
  fi
else
  printf "launch_disabled=unknown\n"
fi

if [[ -f "$PLIST" ]]; then
  printf "plist=%s\n" "$PLIST"
  if grep -Fq "<string>$EXPECTED_PROGRAM</string>" "$PLIST" && grep -Fq "<string>$RUNTIME/codex_relay.py</string>" "$PLIST"; then
    printf "plist_program=expected\n"
  else
    fail_status "plist_program=unexpected; run ./scripts/install_launch_agent.sh"
  fi
else
  fail_status "plist missing: $PLIST"
fi

if [[ -x "$RUNTIME/codex_relay.py" ]]; then
  if [[ ! -x "$PYTHON" ]]; then
    fail_status "python missing: $PYTHON"
  elif ! "$PYTHON" "$RUNTIME/codex_relay.py" --check-config; then
    exit_status=1
  fi
  if [[ -f "$ROOT/codex_relay.py" ]]; then
    if cmp -s "$ROOT/codex_relay.py" "$RUNTIME/codex_relay.py"; then
      printf "runtime_script=matches_repo\n"
    else
      fail_status "runtime_script=differs_from_repo; run ./scripts/install_launch_agent.sh"
    fi
  fi
else
  fail_status "runtime script missing: $RUNTIME/codex_relay.py"
fi

if [[ "$SHOW_LOGS" == "1" ]]; then
  for log_file in "$STATE_DIR/launchd.err" "$STATE_DIR/launchd.out"; do
    if [[ -s "$log_file" ]]; then
      printf "\n== tail -%s %s ==\n" "$TAIL_LINES" "$log_file"
      tail -n "$TAIL_LINES" "$log_file"
    elif [[ -e "$log_file" ]]; then
      printf "\n%s is empty\n" "$log_file"
    else
      printf "\n%s is missing\n" "$log_file"
    fi
  done
fi

if [[ "$exit_status" -ne 0 ]]; then
  printf "\nremediation:\n"
  printf "- reinstall or restart: ./scripts/install_launch_agent.sh\n"
  printf "- full doctor: ./scripts/doctor.sh\n"
  printf "- larger log tail: ./scripts/status.sh --tail 120\n"
fi

exit "$exit_status"
