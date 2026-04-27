# Codex Relay

[![ci](https://github.com/dicnunz/codex-relay/actions/workflows/ci.yml/badge.svg)](https://github.com/dicnunz/codex-relay/actions/workflows/ci.yml)

**Text your Mac. Codex works.**

A Telegram DM becomes a local Codex run on your Mac. The phone is the remote. The Mac keeps the files, tools, apps, sandbox, and account context. When Codex finishes, the answer comes back to Telegram.

No web dashboard. No hosted relay account. No screen mirror.

<p align="center">
  <a href="assets/codex-relay-demo.mp4">
    <img src="assets/codex-relay-demo-poster.png" alt="Codex Relay demo poster" width="100%">
  </a>
</p>

**Watch first:** [52-second demo](assets/codex-relay-demo.mp4) · [Install](#install) · [Try it and report the first blocker](docs/builder-feedback.md) · [Security](#security)

> Unofficial project. Not affiliated with OpenAI or Telegram.

## The Product

```text
Telegram DM -> LaunchAgent -> Codex CLI -> your Mac -> Telegram reply
```

Use it when a task belongs on your Mac but you are not at the keyboard:

- ask Codex to inspect a repo while you are away
- send a screenshot and ask what changed
- run a small doc, test, or fix pass in a known folder
- request the current Mac screen with `/screenshot`
- check jobs, health, policy, and recent run receipts from your phone

Codex Relay does not mirror the visible Codex desktop chat UI. It calls your local Codex CLI with your configured model, workdir, sandbox, approval mode, and optional image attachment.

## Install

Requirements:

- macOS
- Codex Mac app installed and signed in
- Telegram account
- dedicated Telegram bot token from `@BotFather`
- Python 3 available as `python3`

```bash
git clone https://github.com/dicnunz/codex-relay.git
cd codex-relay
./scripts/install.sh
```

The installer verifies the bot token, gives you a one-time `/start` code, allow-lists your private Telegram DM, installs the LaunchAgent, and runs `doctor.sh`.

If token verification fails with `CERTIFICATE_VERIFY_FAILED`, rerun after fixing Python's CA bundle:

```bash
open "/Applications/Python 3.x/Install Certificates.command"
```

Codex Relay also retries Telegram HTTPS calls with the active Python CA path, `certifi` when installed, and common macOS/Homebrew CA bundles. On managed networks that use HTTPS inspection, set `CODEX_RELAY_CA_FILE=/path/to/your-ca.pem` in `.env` instead of disabling TLS verification.

Then DM your bot:

```text
/alive
/health
/policy
/screenshot
/tools
/latency
send a screenshot and ask what changed
```

Optional Mac control surface:

```bash
./scripts/menu_bar.sh
```

That opens a small native menu-bar controller for status, doctor, restart, update, and copying first-run Telegram commands.

## Demo Without Secrets

Run the no-token path from a clean checkout:

```bash
./scripts/demo.sh
./scripts/fresh_clone_test.sh
```

The demo proves the repo can run its smoke path without a Telegram token, local `.env`, or private runtime state. Regenerate the sanitized launch video with:

```bash
./scripts/record_demo.sh
```

<p align="center">
  <img src="assets/demo-transcript.svg" alt="Codex Relay Telegram transcript" width="760">
</p>

## What You Can Send

```text
/alive        live route, model, folder, uptime
/status       current thread and runtime config
/health       fast local bridge checks, no Codex run
/policy      safety boundary and allowed surface
/screenshot   send the Mac screen back to Telegram
/latency      last Codex run timing and timeout
/jobs         running jobs and last run
/cancel id    stop a running job
/history      recent run receipts, no prompt/response logs
/automations  inspect Codex automations through Codex
/tools        quick Codex tool probe
/try          useful first prompts
/new name     new Codex thread
/use name     switch threads
/list         list threads
/where        show active folder
/cd path      set active folder
/home         set folder to ~
/brief        terse replies for this thread
/verbose      detailed replies for this thread
/update       show local update command
/reset        clear the current Codex session
/ping         bridge check
```

Normal messages go to the active thread. Captions on Telegram images become the prompt; image files are saved privately and attached to Codex.

## Try It

I am looking for 10 real Mac/Codex users to try the first install path and report the first blocker.

Open the feedback form after a real attempt:

```text
https://github.com/dicnunz/codex-relay/issues/new?template=install-feedback.yml
```

The ask is simple: install it, run `/alive`, `/health`, `/policy`, `/screenshot`, try one safe local task, and report what was confusing or broken. Do not paste bot tokens, `.env`, private screenshots, personal files, raw Codex transcripts, or unredacted logs.

## What It Is Not

| It is | It is not |
| --- | --- |
| A private Telegram remote for local Codex on your Mac | An official OpenAI app |
| A macOS LaunchAgent that calls the Codex app CLI | A hosted agent platform |
| A way to send tasks, images, repo work, and local Mac requests from your phone | A VNC screen mirror |
| A small local bridge with allow-listed Telegram access | A bypass for logins, MFA, limits, or confirmations |

## Verify

```bash
python3 -m py_compile codex_relay.py scripts/configure.py
python3 scripts/smoke_test.py
./scripts/demo.sh
./scripts/fresh_clone_test.sh
```

After real install:

```bash
./scripts/doctor.sh
./scripts/status.sh
./scripts/status_ui.sh
```

`doctor.sh` checks the Mac environment, Codex CLI, local config, LaunchAgent, runtime copy, Python syntax, and smoke tests. `status_ui.sh` opens a private local status page generated from `status.sh`.

Runtime files:

```text
~/Library/Application Support/CodexRelay
~/Library/LaunchAgents/com.codexrelay.agent.plist
```

Update later with:

```bash
./scripts/update.sh
```

Stop the LaunchAgent with:

```bash
./scripts/uninstall.sh
```

Runtime files remain under `~/Library/Application Support/CodexRelay` unless you remove them separately.

## Security

Codex Relay is intentionally powerful. If you expose your Telegram bot, you are exposing a path to Codex on your Mac.

- Use a dedicated bot and keep the token private.
- `.env` is private and gitignored.
- Runtime config is copied with `0600` permissions.
- Only the allow-listed Telegram user/chat can run Codex.
- Group chats are disabled unless `CODEX_TELEGRAM_ALLOW_GROUP_CHATS=true`.
- Images are stored in the private runtime state directory and pruned by retention settings.
- `/policy` shows the same boundary inside Telegram.
- High-risk actions can still hit Codex, OpenAI, macOS, browser, or site confirmations.
- It cannot bypass logins, MFA, macOS privacy prompts, site safety barriers, account limits, or mandatory confirmations.

Use it only with a Telegram account and Mac you trust.

## Honest Limits

- It uses your normal Codex/OpenAI account limits.
- Telegram and Codex/OpenAI are still in the path; this only avoids adding another hosted relay server.
- It waits for Codex to finish before sending the final answer.
- A `/ping` is immediate; real repo, browser, image, test-running, and desktop/app-control tasks can take tens of seconds or minutes.
- Computer Use and plugin behavior depend on what your local Codex runtime exposes.
- The bot is only as capable as the Codex install on that Mac.

Codex is already useful on a Mac. Codex Relay makes it reachable from the chat app already on your phone.
