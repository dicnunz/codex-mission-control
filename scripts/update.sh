#!/bin/zsh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$ROOT"

printf "Updating Codex Mission Control...\n"
git pull --ff-only

"$ROOT/cmc" init >/dev/null
"$ROOT/cmc" discover >/dev/null
"$ROOT/cmc" doctor >/dev/null
dashboard_path="$("$ROOT/scripts/status_ui.sh" --no-open)"
printf "ok: Mission Control hub refreshed\n"
printf "dashboard: %s\n" "$dashboard_path"

if [[ -f "$ROOT/.env" ]]; then
  "$ROOT/scripts/install_launch_agent.sh" >/dev/null
  "$ROOT/scripts/doctor.sh"
  printf "ok: Mission Control Relay refreshed\n"
else
  printf "Relay not configured; skipped phone remote refresh.\n"
  printf "Install later with: ./cmc relay install\n"
fi

printf "\nOptional Mac control surface:\n./scripts/menu_bar.sh\n"
printf "Optional local status page:\n./scripts/status_ui.sh\n"
printf "Optional browser/operator kit:\n./cmc support\n"
printf "\nUpdated and running.\n"
