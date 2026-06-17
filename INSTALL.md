# Install

Codex Mission Control is macOS-first and local-only.

## Requirements

- macOS
- Codex Mac app installed and signed in
- Python 3 available as `python3`
- optional: Telegram bot token from `@BotFather` for phone control

## Safe First Run

```bash
git clone https://github.com/dicnunz/codex-mission-control.git
cd codex-mission-control
./scripts/install.sh
```

The installer:

1. checks macOS, Python, and Codex CLI,
2. creates `~/Codex Mission Control`,
3. discovers projects under standard Mac folders,
4. links `cmc` into `~/.local/bin` when possible,
5. previews project `AGENTS.md` adoption unless you choose to write it,
6. optionally installs the Telegram Relay,
7. runs doctor and writes the local dashboard.

Mission Control does not move project folders. The hub stores symlinks, markdown ops files, lane locks, and outboxes.

## First-run Troubleshooting

### `python3 is required`

Confirm Python 3 is available before running the installer:

```bash
python3 --version
```

If that command fails, install Python 3 first and rerun `./scripts/install.sh`.

### `Codex CLI not found`

Open the Codex Mac app first and confirm it is installed and signed in. The installer checks for the Codex app CLI under `/Applications/Codex.app` and then falls back to a `codex` command on your `PATH`.

You can verify the PATH-based fallback with:

```bash
command -v codex
```

### `cmc: command not found`

The installer links `cmc` into `~/.local/bin` when possible. If that folder is not on your `PATH`, either run commands from the repo:

```bash
./cmc status
./cmc doctor
```

or add the local bin folder to your shell profile:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Dashboard does not open

Generate the dashboard path without opening the browser:

```bash
cmc dashboard --no-open
```

Then open the printed local HTML path manually.

### Unsure what to report

Run the smallest safe check set and paste only short, redacted output into the install feedback issue template:

```bash
cmc status
cmc doctor
cmc lanes
```

Do not paste bot tokens, `.env`, private screenshots, personal files, raw Codex transcripts, auth files, or unredacted logs.

## Project Instructions

Preview the exact project instruction blocks:

```bash
cmc adopt
```

Write them with backups:

```bash
cmc adopt --write
```

Existing `AGENTS.md` files are backed up as `AGENTS.md.cmc-backup-*`.

## Dashboard

```bash
cmc dashboard
```

The dashboard is a private local HTML file under `~/Library/Application Support/CodexRelay/state/`.

## Telegram Relay

Install later with:

```bash
./cmc relay install
```

Relay is a private Telegram bot pointed at your Mac:

```text
Telegram -> LaunchAgent -> Codex CLI -> Mission Control
```

Treat it like SSH into your Mac through Telegram. Keep the bot token private.

## Runtime Files

```text
~/Codex Mission Control
~/Library/Application Support/CodexRelay
~/Library/LaunchAgents/com.codexrelay.agent.plist
```

The `CodexRelay` runtime name is kept for upgrade compatibility.

## Verify

```bash
cmc status
cmc doctor
cmc lanes
./scripts/doctor.sh
```

## Uninstall Relay

```bash
./scripts/uninstall.sh
```

This removes the LaunchAgent plist. Runtime files remain so you can inspect or delete them manually.
