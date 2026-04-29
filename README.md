# Codex Mission Control

[![ci](https://github.com/dicnunz/codex-mission-control/actions/workflows/ci.yml/badge.svg)](https://github.com/dicnunz/codex-mission-control/actions/workflows/ci.yml)

**Codex Mission Control gives Codex a control room for your Mac.**

It finds your projects, creates mission workspaces, locks shared surfaces, keeps approval gates, and lets you text it from your phone.

Unofficial project. Not affiliated with OpenAI or Telegram.

![Codex Mission Control control-room hero](assets/visuals/hero-control-room.png)

## What It Does

```text
projects -> missions -> lane locks -> approval packets -> optional Telegram remote
```

It creates:

- a local hub at `~/Codex Mission Control`
- a non-destructive `missions/` symlink index to your real projects
- a private local dashboard for missions, lanes, Relay health, and copyable commands
- lane locks for browser, GitHub, email, public social, commerce, desktop, and global writes
- mission outboxes for handoffs
- approval packets for risky actions
- an optional Telegram remote: **Mission Control Relay**

It does not move your projects, run a hosted dashboard, or create another account.

## Why It Exists

Multiple Codex chats can all be useful and still wreck each other if they touch the same browser, inbox, GitHub repo, desktop, social account, or payment surface.

Mission Control makes those collisions visible:

```bash
cmc claim BROWSER FLIGHT "using the browser"
cmc claim BROWSER OTHER "also using the browser"
# held: BROWSER
```

That is the product: projects become missions, shared surfaces get lanes, and risky actions become approval packets before anything leaves your Mac.

## Install

Requirements:

- macOS
- Codex Mac app installed and signed in
- Python 3 available as `python3`
- optional: Telegram bot token from `@BotFather` if you want phone control

```bash
git clone https://github.com/dicnunz/codex-mission-control.git
cd codex-mission-control
./scripts/install.sh
```

The installer initializes the hub, discovers projects under `~/Developer`, `~/Projects`, `~/Documents/Codex`, and the current folder, offers backed-up `AGENTS.md` mission blocks, then runs health checks.

It also links `cmc` into `~/.local/bin` when possible. If that folder is not on your `PATH`, use `./cmc` from the repo.

The last installer screen gives you the dashboard path and the three commands that matter first:

```bash
cmc status
cmc lanes
cmc packet
```

Install the phone remote during setup or later:

```bash
./cmc relay install
```

## Local Commands

```bash
./cmc init
./cmc discover
./cmc status
./cmc doctor
./cmc lanes
./cmc projects
./cmc instructions
./cmc adopt
./cmc adopt --write
./cmc claim BROWSER FLIGHT "using the browser"
./cmc release BROWSER FLIGHT
./cmc packet --mission APP --action "send reply" --target "email thread" --object "exact text" --proof "proof/email.png" --risk "outreach" --why "warm inbound" --stop "after one send"
./cmc merge
./scripts/status_ui.sh
```

Discovery is deliberately boring: `cmc discover` scans the standard Mac roots; `cmc discover /path/to/project` scans only that path; `cmc discover --include-defaults /extra/root` scans both. It creates symlinks in the hub and per-mission outboxes. Your real folders stay where they are.

`cmc adopt` previews the `AGENTS.md` blocks Mission Control would add to discovered projects. `cmc adopt --write` applies them with backups when an `AGENTS.md` already exists. The interactive installer defaults to applying them because that is what makes the hub useful immediately; non-interactive installs skip unless `CMC_ADOPT_AGENTS=yes` is set.

## Relay Commands

Mission Control Relay is the optional Telegram remote pointed at the hub:

```text
/mission status
/mission lanes
/mission projects
/mission packet
/mission health
/mission doctor
/mission instructions
/alive
/health
/policy
/screenshot
/tools
/jobs
/cd path
```

Normal Telegram messages still go to local Codex through your Mac. Image captions still attach the image to Codex. Relay remains allow-listed to your private Telegram user/chat.

## Demo

```bash
./scripts/demo.sh
```

The demo proves the core loop without Telegram secrets: initialize a temp hub, discover a mission, claim a browser lane, show the blocked second claim, generate an approval packet, and print the phone flow.

Fresh clone check:

```bash
./scripts/fresh_clone_test.sh
```

## What It Is Not

| It is | It is not |
| --- | --- |
| Local traffic control for Codex work on your Mac | An official OpenAI product |
| A mission hub over your existing project folders | A hosted agent service |
| A lane and approval system for shared surfaces | A way to bypass logins, MFA, limits, or confirmations |
| A Telegram remote for the hub | A VNC screen mirror |

## Verify

```bash
python3 -m py_compile mission_control.py codex_relay.py scripts/configure.py
PYTHONPATH=. python3 scripts/smoke_test.py
./cmc doctor
./scripts/demo.sh
./scripts/fresh_clone_test.sh
./scripts/doctor.sh
./scripts/qa.sh
```

Runtime files:

```text
~/Codex Mission Control
~/Library/Application Support/CodexRelay
~/Library/LaunchAgents/com.codexrelay.agent.plist
```

Update later with:

```bash
./scripts/update.sh
```

Stop Relay with:

```bash
./scripts/uninstall.sh
```

Mission Control is the hub. Relay is the remote.
