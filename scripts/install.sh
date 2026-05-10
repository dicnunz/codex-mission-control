#!/bin/zsh
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"

printf "Codex Mission Control installer\n"
printf "1. preflight local Mac requirements\n"
printf "2. initialize the local Mission Control hub\n"
printf "3. discover existing projects as missions\n"
printf "4. expose the cmc command in ~/.local/bin when possible\n"
printf "5. optionally preview/install project AGENTS.md blocks\n"
printf "6. optionally install Mission Control Relay for Telegram\n"
printf "7. run local health checks\n\n"

[[ "$(uname -s)" == "Darwin" ]] || {
  printf "Codex Mission Control is macOS-first in this release.\n" >&2
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

printf "Initializing Mission Control...\n"
"$ROOT/cmc" init
printf "\nDiscovering projects...\n"
"$ROOT/cmc" discover
printf "\nMission Control status...\n"
"$ROOT/cmc" status

LOCAL_BIN="$HOME/.local/bin"
if [[ -d "$LOCAL_BIN" || -w "$HOME" ]]; then
  mkdir -p "$LOCAL_BIN"
  ln -sf "$ROOT/cmc" "$LOCAL_BIN/cmc"
  printf "\nok: linked cmc at %s\n" "$LOCAL_BIN/cmc"
  case ":$PATH:" in
    *":$LOCAL_BIN:"*) ;;
    *) printf "note: add %s to PATH to run cmc without ./cmc\n" "$LOCAL_BIN" ;;
  esac
fi

adopt_agents="${CMC_ADOPT_AGENTS:-}"
if [[ -z "$adopt_agents" && -t 0 ]]; then
  printf "\nPreview Mission Control AGENTS.md blocks now. Write them into discovered projects? [y/N] "
  read -r adopt_agents
  [[ -n "$adopt_agents" ]] || adopt_agents="no"
elif [[ -z "$adopt_agents" ]]; then
  adopt_agents="no"
fi

case "${adopt_agents:l}" in
  y|yes|1|true)
    "$ROOT/cmc" adopt --write
    ;;
  *)
    printf "\nProject AGENTS.md adoption skipped. Preview the exact changes with:\n"
    printf "  ./cmc adopt\n"
    printf "Apply later with backups using:\n"
    printf "  ./cmc adopt --write\n"
    ;;
esac

install_relay="${CMC_INSTALL_RELAY:-}"
if [[ -z "$install_relay" && -t 0 ]]; then
  printf "\nInstall Mission Control Relay for Telegram now? [y/N] "
  read -r install_relay
fi

case "${install_relay:l}" in
  y|yes|1|true)
    python3 "$ROOT/scripts/configure.py"
    ;;
  *)
    printf "\nRelay skipped. Install later with:\n"
    printf "./cmc relay install\n"
    ;;
esac

printf "\nRunning final checks...\n"
doctor_log="$(mktemp)"
if "$ROOT/scripts/doctor.sh" >"$doctor_log" 2>&1; then
  printf "ok: doctor passed\n"
else
  cat "$doctor_log"
  rm -f "$doctor_log"
  exit 1
fi
rm -f "$doctor_log"

if [[ -t 1 && "${CMC_OPEN_DASHBOARD:-yes}" != "no" ]]; then
  dashboard_path="$("$ROOT/scripts/status_ui.sh")"
  printf "ok: opened dashboard at %s\n" "$dashboard_path"
else
  dashboard_path="$("$ROOT/scripts/status_ui.sh" --no-open)"
fi

printf "\nMission Control is ready.\n"
printf "Dashboard: %s\n" "$dashboard_path"
printf "\nUse next:\n"
printf "  cmc status\n"
printf "  cmc lanes\n"
printf "  cmc packet\n"
printf "  cmc dashboard\n"
printf "  cmc support  # optional self-serve browser/operator kit\n"
printf "\nTelegram after Relay install:\n"
printf "  /mission status\n"
printf "  /mission lanes\n"
printf "  /mission packet\n"
printf "  /mission health\n"
printf "\nOptional browser/operator kit: https://nicdunz.gumroad.com/l/agent-browser-operator-os\n"
