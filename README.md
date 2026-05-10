# Codex Mission Control

[![ci](https://github.com/dicnunz/codex-mission-control/actions/workflows/ci.yml/badge.svg)](https://github.com/dicnunz/codex-mission-control/actions/workflows/ci.yml)

**Stop running Codex like loose chats. Give it local traffic control.**

Codex Mission Control is for Mac users running several Codex chats against real projects, browsers, inboxes, repos, and account surfaces.

It finds your projects, turns them into missions, locks shared surfaces, keeps approval gates, and lets you text the whole setup from your phone.

Unofficial project. Not affiliated with OpenAI or Telegram.

![Codex Mission Control launch card](assets/social-card.png)

## The Problem

One Codex chat is simple. Several useful Codex chats can collide:

- two chats use the same browser session,
- one edits a repo while another tries to push it,
- one drafts an email while another touches the inbox,
- one reaches a public, payment, or account surface without the rest of the work knowing.

Mission Control makes that coordination explicit with projects, lanes, outboxes, and approval packets.

## Quick Demo

```bash
git clone https://github.com/dicnunz/codex-mission-control.git
cd codex-mission-control
./scripts/demo.sh
```

No Telegram token needed. The demo proves the core loop: discover a project, claim the browser lane, block a second browser claim, generate an approval packet, and print the phone flow.

Watch the 44-second demo: [assets/codex-mission-control-demo.mp4](assets/codex-mission-control-demo.mp4)

If Mission Control saves you time and you want the smallest paid support path, buy the $5 Codex run receipt: <https://nicdunz.gumroad.com/l/smrimu>.

For broader self-serve templates around browser-agent lanes, public-action gates, proof ledgers, and handoffs, the Agent Operator Starter Bundle is here: <https://nicdunz.gumroad.com/l/agent-operator-starter-bundle>.

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

## Why It Works

Multiple Codex chats can all be useful and still wreck each other if they touch the same browser, inbox, GitHub repo, desktop, social account, or payment surface.

Mission Control makes those collisions visible:

```bash
cmc claim BROWSER FLIGHT "using the browser"
cmc claim BROWSER OTHER "also using the browser"
# held: BROWSER
```

That is the product: projects become missions, shared surfaces get lanes, and risky actions become approval packets before anything leaves your Mac.

## Who It Is For

- Codex-heavy Mac users with multiple active projects
- people who run several Codex chats at once
- builders who want local coordination without a hosted agent service
- users who want a private Telegram remote for their Mac-side Codex setup
- anyone who needs public/account/payment actions to stop at exact approval

Not for people running one simple Codex chat at a time.

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

Full install notes: [INSTALL.md](INSTALL.md).

The installer initializes the hub, discovers projects under `~/Developer`, `~/Projects`, `~/Documents/Codex`, and the current folder, offers backed-up `AGENTS.md` mission blocks, then runs health checks.

By default, setup does not rewrite your projects. `cmc adopt` previews the `AGENTS.md` blocks Mission Control would add; `cmc adopt --write` applies them with backups.

It also links `cmc` into `~/.local/bin` when possible. If that folder is not on your `PATH`, use `./cmc` from the repo.

The last installer screen gives you the dashboard path and the three commands that matter first:

```bash
cmc status
cmc lanes
cmc packet
cmc dashboard
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
./cmc dashboard
./scripts/status_ui.sh
```

Discovery is deliberately boring: `cmc discover` scans the standard Mac roots; `cmc discover /path/to/project` scans only that path; `cmc discover --include-defaults /extra/root` scans both. It creates symlinks in the hub and per-mission outboxes. Your real folders stay where they are.

`cmc adopt` previews the `AGENTS.md` blocks Mission Control would add to discovered projects. `cmc adopt --write` applies them with backups when an `AGENTS.md` already exists. The installer defaults to preview-only unless `CMC_ADOPT_AGENTS=yes` is set.

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

## Local Demo

```bash
./scripts/demo.sh
```

The demo proves the core loop without Telegram secrets: initialize a temp hub, discover a mission, claim a browser lane, show the blocked second claim, generate an approval packet, and print the phone flow.

Fresh clone check:

```bash
./scripts/fresh_clone_test.sh
```

First-builder feedback script: [docs/FIRST_10_BUILDERS.md](docs/FIRST_10_BUILDERS.md).

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

The Relay runtime path keeps the original `CodexRelay` name for upgrade compatibility.

Update later with:

```bash
./scripts/update.sh
```

Stop Relay with:

```bash
./scripts/uninstall.sh
```

Mission Control is the hub. Relay is the remote.
