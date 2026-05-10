#!/bin/zsh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$ROOT"

printf "Codex Mission Control QA\n"

zsh -n scripts/*.sh
python3 -m py_compile mission_control.py codex_relay.py scripts/configure.py scripts/smoke_test.py
PYTHONPATH="$ROOT" python3 scripts/smoke_test.py

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
./cmc support > "$tmp/support.out"
grep -q 'https://nicdunz.gumroad.com/l/smrimu' "$tmp/support.out"
grep -q 'https://nicdunz.gumroad.com/l/agent-operator-starter-bundle' "$tmp/support.out"
grep -q 'https://nicdunz.gumroad.com/l/agent-browser-operator-os' "$tmp/support.out"
test -s .github/ISSUE_TEMPLATE/paid-setup-audit.yml
grep -q 'https://nicdunz.gumroad.com/l/agent-workflow-mini-audit' .github/ISSUE_TEMPLATE/paid-setup-audit.yml
grep -q 'https://nicdunz.gumroad.com/l/agent-workflow-audit' .github/ISSUE_TEMPLATE/paid-setup-audit.yml
grep -q 'https://nicdunz.gumroad.com/l/agent-browser-operator-os' README.md
grep -q 'https://nicdunz.gumroad.com/l/agent-browser-operator-os' .github/FUNDING.yml

hub="$tmp/hub"
proj_root="$tmp/projects"
one="$proj_root/repo-one"
two="$proj_root/repo-two"
notes="$proj_root/notes-only"
mkdir -p "$one/.git" "$two/.git" "$notes"
printf '# One\n' > "$one/README.md"
printf '# Two\n' > "$two/README.md"
printf '# Notes\n' > "$notes/README.md"

./cmc --hub "$hub" init >/dev/null
./cmc --hub "$hub" discover "$proj_root" > "$tmp/discover1.out"
./cmc --hub "$hub" discover "$proj_root" > "$tmp/discover2.out"
grep -q 'added: 2' "$tmp/discover1.out"
grep -q 'added: 0' "$tmp/discover2.out"
test -L "$hub/missions/RO-repo-one"
test -L "$hub/missions/RT-repo-two"
test ! -e "$hub/missions/NO-notes-only"

./cmc --hub "$hub" adopt --write >/dev/null
grep -q 'Codex Mission Contract' "$one/AGENTS.md"
./cmc --hub "$hub" adopt > "$tmp/adopt.out"
grep -q 'changed: 0' "$tmp/adopt.out"

./cmc --hub "$hub" claim BROWSER TEST edge >/dev/null
if ./cmc --hub "$hub" claim BROWSER OTHER edge > "$tmp/double.out" 2>&1; then
  printf "expected second BROWSER claim to fail\n" >&2
  exit 1
fi
grep -q 'held: BROWSER' "$tmp/double.out"
if ./cmc --hub "$hub" release BROWSER OTHER > "$tmp/release_bad.out" 2>&1; then
  printf "expected wrong-owner release to fail\n" >&2
  exit 1
fi
grep -q 'not owner' "$tmp/release_bad.out"

python3 - "$hub" <<'PY'
import json
import pathlib
import sys
import time

path = pathlib.Path(sys.argv[1]) / "_ops/.surface_locks/BROWSER/lock.json"
data = json.loads(path.read_text())
data["created_epoch"] = time.time() - 99999
path.write_text(json.dumps(data))
PY
./cmc --hub "$hub" status > "$tmp/status_stale.out"
grep -q '1 stale' "$tmp/status_stale.out"
./cmc --hub "$hub" claim BROWSER OTHER replacement > "$tmp/reclaim.out"
grep -q 'acquired: BROWSER by OTHER' "$tmp/reclaim.out"
./cmc --hub "$hub" release BROWSER OTHER >/dev/null

if ./cmc --hub "$hub" claim FAKE TEST edge > "$tmp/invalid.out" 2>&1; then
  printf "expected invalid lane to fail\n" >&2
  exit 1
fi
grep -q 'invalid lane' "$tmp/invalid.out"

./cmc --hub "$hub" packet --mission QA --action action --target target --object object --proof proof --risk risk --why reason --stop stop > "$tmp/packet.out"
grep -q 'Exact action: action' "$tmp/packet.out"
grep -q 'Target: target' "$tmp/packet.out"
grep -q 'Proof after execution: proof' "$tmp/packet.out"
grep -q 'Stop condition: stop' "$tmp/packet.out"

readme_before="$(cat "$one/README.md")"
./cmc --hub "$hub" merge > "$tmp/merge.out"
test "$(cat "$one/README.md")" = "$readme_before"
grep -q 'merged outboxes: 2' "$tmp/merge.out"

rm -f "$hub/_ops/GO_NO_GO.md"
./cmc --hub "$hub" status > "$tmp/status_missing.out"
grep -q 'missing GO_NO_GO.md' "$tmp/status_missing.out"

CODEX_MISSION_CONTROL_HOME="$hub" ./scripts/status_ui.sh --no-open > "$tmp/dashboard.out"
dashboard_path="$(cat "$tmp/dashboard.out")"
test -s "$dashboard_path"
CODEX_MISSION_CONTROL_HOME="$hub" ./cmc dashboard --no-open >/dev/null
grep -q 'Mission Control' "$dashboard_path"
grep -q 'Lanes' "$dashboard_path"
grep -q 'Approval packet' "$dashboard_path"
grep -q 'Copy command' "$dashboard_path"
grep -q 'https://nicdunz.gumroad.com/l/smrimu' "$dashboard_path"
grep -q 'https://nicdunz.gumroad.com/l/agent-operator-starter-bundle' "$dashboard_path"
grep -q 'https://nicdunz.gumroad.com/l/agent-browser-operator-os' "$dashboard_path"
grep -q 'Support Mission Control' "$dashboard_path"

for visual in \
  assets/visuals/hero-control-room.png \
  assets/visuals/origin-lanes.png \
  assets/visuals/project-discovery.png \
  assets/visuals/lane-lock.png \
  assets/visuals/approval-packet.png \
  assets/visuals/phone-remote.png \
  assets/visuals/local-only.png \
  assets/visuals/dashboard-instrument.png \
  assets/visuals/mission-control-icon.png; do
  test -s "$visual"
done

./scripts/demo.sh
./scripts/demo.sh > "$tmp/demo.out"
grep -q 'https://dicnunz.github.io/codex-operator-sprint/workflow-route-checker.html' "$tmp/demo.out"
grep -q 'https://nicdunz.gumroad.com/l/agent-browser-operator-os' "$tmp/demo.out"
grep -q 'https://nicdunz.gumroad.com/l/agent-workflow-mini-audit' "$tmp/demo.out"
grep -q 'https://nicdunz.gumroad.com/l/agent-workflow-audit' "$tmp/demo.out"
./scripts/fresh_clone_test.sh

if command -v swiftc >/dev/null 2>&1; then
  ./scripts/build_menu_bar.sh >/dev/null
fi

if command -v ffprobe >/dev/null 2>&1; then
  test "$(sips -g pixelWidth -g pixelHeight assets/social-card.png | awk '/pixelWidth/ {w=$2} /pixelHeight/ {h=$2} END {print w "x" h}')" = "1280x640"
  test "$(ffprobe -v error -show_entries stream=width,height -of csv=p=0:s=x assets/codex-mission-control-demo.mp4 | head -n1)" = "1280x720"
  test "$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 assets/codex-mission-control-demo.mp4)" = "44.000000"
fi

printf "ok: qa\n"
