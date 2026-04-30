#!/bin/zsh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
SOURCE="${1:-$ROOT}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

printf "Fresh clone test\n"
printf "source: %s\n" "$SOURCE"

copied_worktree=0
if [[ "$SOURCE" == "$ROOT" && -n "$(git -C "$ROOT" status --short)" ]]; then
  printf "mode: current working tree copy\n"
  copied_worktree=1
  mkdir -p "$TMP/codex-mission-control"
  git -C "$ROOT" ls-files -co --exclude-standard -z | while IFS= read -r -d '' file_path; do
    [[ -e "$ROOT/$file_path" ]] || continue
    mkdir -p "$TMP/codex-mission-control/$(dirname "$file_path")"
    cp -p "$ROOT/$file_path" "$TMP/codex-mission-control/$file_path"
  done
else
  printf "mode: git clone\n"
  git clone --quiet "$SOURCE" "$TMP/codex-mission-control"
fi

cd "$TMP/codex-mission-control"

python3 -m py_compile mission_control.py codex_relay.py scripts/configure.py scripts/smoke_test.py
PYTHONPATH="$PWD" python3 scripts/smoke_test.py
./cmc --hub "$TMP/hub" init >/dev/null
./cmc --hub "$TMP/hub" discover "$PWD" >/dev/null
./cmc --hub "$TMP/hub" status >/dev/null
./cmc --hub "$TMP/hub" doctor >/dev/null
CODEX_MISSION_CONTROL_HOME="$TMP/hub" ./cmc dashboard --no-open >/dev/null
./cmc --hub "$TMP/hub" instructions >/dev/null
./cmc --hub "$TMP/hub" adopt >/dev/null
./cmc --hub "$TMP/hub" claim BROWSER TEST "fresh clone" >/dev/null
if ./cmc --hub "$TMP/hub" claim BROWSER OTHER "fresh clone" >/dev/null 2>&1; then
  printf "expected second BROWSER claim to fail\n" >&2
  exit 1
fi
./cmc --hub "$TMP/hub" release BROWSER TEST >/dev/null
./cmc --hub "$TMP/hub" packet --mission TEST --action inspect --target repo --object readme --proof proof.txt --risk none --why demo --stop done >/dev/null
CODEX_MISSION_CONTROL_HOME="$TMP/hub" ./scripts/status_ui.sh --no-open >/dev/null
./scripts/demo.sh
if [[ "$copied_worktree" == "0" ]]; then
  HOME="$TMP/home-update" \
  CODEX_MISSION_CONTROL_HOME="$TMP/home-update/Codex Mission Control" \
  PATH="$TMP/bin:$PATH" \
  ./scripts/update.sh >/dev/null
fi
if command -v swiftc >/dev/null 2>&1; then
  ./scripts/build_menu_bar.sh >/dev/null
fi

ISO_HOME="$TMP/home"
FAKE_BIN="$TMP/bin"
mkdir -p "$ISO_HOME"
mkdir -p "$FAKE_BIN"
cat > "$FAKE_BIN/codex" <<'SH'
#!/bin/sh
printf 'fake codex for installer preflight\n'
SH
chmod 700 "$FAKE_BIN/codex"
HOME="$ISO_HOME" \
PATH="$FAKE_BIN:$PATH" \
CODEX_RELAY_LABEL="com.codexrelay.fresh.$RANDOM" \
CODEX_MISSION_CONTROL_HOME="$ISO_HOME/Codex Mission Control" \
CMC_ADOPT_AGENTS=yes \
CMC_INSTALL_RELAY=no \
./scripts/install.sh >/dev/null
"$ISO_HOME/.local/bin/cmc" --version >/dev/null
"$ISO_HOME/.local/bin/cmc" --hub "$ISO_HOME/Codex Mission Control" doctor >/dev/null
HOME="$ISO_HOME" CODEX_MISSION_CONTROL_HOME="$ISO_HOME/Codex Mission Control" ./scripts/status_ui.sh --no-open >/dev/null

printf "ok: fresh clone works without Telegram secrets\n"
