# Codex Mission Control

[![ci](https://github.com/dicnunz/codex-mission-control/actions/workflows/ci.yml/badge.svg)](https://github.com/dicnunz/codex-mission-control/actions/workflows/ci.yml)

**Stop running Codex like loose chats. Give it a control room.**

Give Codex a mission control room for your Mac. It finds your projects, creates mission workspaces, locks shared surfaces, keeps approval gates, and lets you text it from your phone.

Unofficial project. Not affiliated with OpenAI or Telegram.

![Codex Mission Control control-room hero](assets/visuals/hero-control-room.png)

## The Product

```text
existing projects -> Mission Control hub -> lanes + outboxes + approvals -> optional Telegram remote
```

Codex Mission Control is local Mac infrastructure for people who run more than one Codex thread or project at once.

It creates:

- a local hub at `~/Codex Mission Control`
- a private local dashboard for missions, lanes, Relay health, and copyable commands
- a non-destructive `missions/` symlink index to your real projects
- shared-surface lanes for browser, GitHub, email, public social, commerce, desktop, and global writes
- mission outboxes for handoffs
- exact approval packet templates
- an optional Telegram remote called **Mission Control Relay**

It does not move your projects. It does not run a hosted dashboard. It does not create another account.

## Why It Exists

The failure mode is simple: multiple Codex chats can all be useful and still wreck each other if they touch the same browser, inbox, GitHub repo, desktop, social account, or payment surface.

Mission Control makes those collisions visible:

```bash
cmc claim BROWSER FLIGHT "using the browser"
cmc claim BROWSER OTHER "also using the browser"
# held: BROWSER
```

That is the product: projects become missions, shared surfaces get lanes, and risky actions become exact approval packets before anything leaves your Mac.

![Projects become missions](assets/visuals/project-discovery.png)

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

The installer initializes Mission Control, discovers projects under `~/Developer`, `~/Projects`, `~/Documents/Codex`, and the current folder, offers to install backed-up `AGENTS.md` mission blocks, then runs local health checks.

It also links `cmc` into `~/.local/bin` when possible. If that folder is not on your `PATH`, use `./cmc` from the repo.

The last installer screen is the product: the local dashboard path plus the three commands that matter first:

```bash
cmc status
cmc lanes
cmc packet
```

![First local dashboard visual](assets/visuals/dashboard-instrument.png)

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

The generated instructions follow OpenAI's prompt guidance shape: clear role and objective, explicit instructions, compact reasoning steps, tool boundaries, validation, and a short output contract.

## Relay Commands

Mission Control Relay keeps the old Telegram remote idea, now pointed at the hub:

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

![Mission Control Relay phone remote](assets/visuals/phone-remote.png)

## Visual Model

The product is deliberately visual but not decorative: one hub, real project folders, shared-surface traffic, exact approval packets, and a clear local boundary.

![Shared-surface lane lock](assets/visuals/lane-lock.png)

![Go/no-go approval packet](assets/visuals/approval-packet.png)

![Local-only boundary](assets/visuals/local-only.png)

## Demo

```bash
./scripts/demo.sh
```

The demo proves the no-token path: initialize a temp hub, discover this repo as a mission, claim a browser lane, show status, run smoke tests, and print the phone flow.

Fresh clone check:

```bash
./scripts/fresh_clone_test.sh
```

## What It Is Not

| It is | It is not |
| --- | --- |
| Local traffic control for Codex work on your Mac | An official OpenAI product |
| A mission hub over your existing project folders | A hosted agent platform |
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
