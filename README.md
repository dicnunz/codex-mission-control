# Codex Relay

Text your Mac's Codex from Telegram. Local. No VNC. No hosted relay.

<p align="center">
  <img src="assets/social-card.svg" alt="Codex Relay: Telegram remote for Codex on your Mac" width="100%">
</p>

Text your bot from your phone. A LaunchAgent on your Mac runs the local Codex app CLI, waits for the run to finish, and sends the final answer back to Telegram.

That is the product: Telegram is the remote, Codex is the engine, and your Mac is the machine doing the work.

Use this when VNC is the wrong shape and a PWA/app-server setup is more surface area than you want: no tiny desktop, no Cloudflare Access, no web app server to maintain. You text the task; the Mac does the work.

> Unofficial project. Not affiliated with OpenAI or Telegram.

## Quickstart

```bash
gh repo clone dicnunz/codex-relay
cd codex-relay
./scripts/install.sh
```

The only manual credential step is creating a bot with `@BotFather` and pasting its token. The token stays in your local `.env`.

Then DM your bot:

```text
/alive
/tools
/latency
send a screenshot and ask what changed
```

## Demo

[Watch the demo](assets/codex-relay-demo.mp4)

<p align="center">
  <img src="assets/codex-relay-demo-poster.png" alt="Codex Relay demo poster" width="760">
</p>

```text
/alive
/tools
/jobs
send a screenshot and ask what changed
/cd Projects/my-repo
make this repo launch-ready without pushing
```

The demo is meant to make one thing obvious: Telegram is only the remote. The real work happens on the Mac through your installed Codex CLI, in the folder and sandbox you configured.

<p align="center">
  <img src="assets/demo-transcript.svg" alt="Codex Relay Telegram transcript" width="760">
</p>

## What It Is

| It is | It is not |
| --- | --- |
| A private Telegram remote for local Codex on your Mac | An official OpenAI app |
| A macOS LaunchAgent that calls the Codex app CLI | A hosted agent platform |
| A way to send tasks, images, repo work, and local Mac requests from your phone | A VNC screen mirror |
| A small local bridge with allow-listed Telegram access | A bypass for logins, MFA, limits, or confirmations |

## Why Use It

Codex Relay is useful when a task is worth handing to the Mac even though you are not at the keyboard:

- Check a repo while you are away from the laptop.
- Send a screenshot and ask what changed.
- Run a small fix, test, or doc pass in a known folder.
- Ask Codex to inspect local files, apps, or browser state when your Codex runtime exposes those tools.
- Check Codex automations from your phone with `/automations`.

It is not instant chat. A `/ping` is immediate, but a normal request waits for Codex CLI startup, `gpt-5.5` with `xhigh` reasoning, local tool work, and Telegram delivery. Small text tasks can feel quick; image, browser, Computer Use, repo, or test-running tasks can take tens of seconds or minutes. The default task timeout is 600 seconds.

## What It Does

- `gpt-5.5` with `xhigh` reasoning by default through the Codex app CLI.
- Private Telegram bot allow-listed to your Telegram user.
- Background jobs with `/jobs`, `/cancel`, and `/history`.
- Latency and mode controls with `/latency`, `/brief`, and `/verbose`.
- Named Codex threads: `/new`, `/use`, `/list`, `/reset`.
- Per-thread folders: `/cd`, `/where`, `/home`.
- Telegram photos and image documents passed to Codex with `--image`.
- `/automations` shortcut for a guardrailed Codex automation inspection.
- Mac-side files, repos, shell, images, and whatever tools your local Codex runtime exposes.
- macOS LaunchAgent so the relay stays running after setup.
- Local config only. No hosted relay account.

## Architecture

```text
Telegram DM -> local LaunchAgent -> Codex app CLI -> your Mac -> Telegram reply
```

The relay does not mirror the visible Codex desktop chat UI. It invokes your local Codex CLI with the configured model, workdir, sandbox, approval mode, and optional image attachment.

## Install Details

Requirements:

- macOS
- Codex Mac app installed and signed in
- Telegram account
- A Telegram bot token from `@BotFather`

The installer:

1. Finds the Codex app CLI.
2. Asks for your Telegram bot token.
3. Verifies the bot with Telegram.
4. Waits for you to send `/start`.
5. Allow-lists your Telegram user.
6. Installs and starts the LaunchAgent.
7. Runs `doctor.sh` so setup failures are caught immediately.

After install, DM your bot:

```text
/alive
/tools
/latency
/new repo
/cd Projects/my-repo
read this repo and tell me the next best fix
```

## Commands

```text
/alive        live route, model, folder, uptime
/status       current thread and runtime config
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

## Message Style

By default, Codex Relay sends clean Telegram messages instead of explicit reply bubbles quoting your last message. Turn threaded replies back on only if you want that chat style:

```env
CODEX_TELEGRAM_REPLY_TO_MESSAGES=true
```

Normal messages use `CODEX_TELEGRAM_MODEL=gpt-5.5` and `CODEX_TELEGRAM_REASONING_EFFORT=xhigh`. Change that env var only if you intentionally want a different reasoning profile.

`/status` shows the active reasoning setting, last run status, and latency after Codex replies.

Use `/brief` for phone-friendly answers and `/verbose` when you want debugging detail or a handoff summary. The setting is stored per thread.

## Verify

```bash
./scripts/doctor.sh
./scripts/status.sh
./scripts/demo.sh
```

`doctor.sh` checks the Mac environment, Codex CLI, local config, LaunchAgent, runtime copy, Python syntax, and smoke tests.

Runtime files:

```text
~/Library/Application Support/CodexRelay
~/Library/LaunchAgents/com.codexrelay.agent.plist
```

Update later with:

```bash
./scripts/update.sh
```

## Safety

Codex Relay is intentionally powerful. If you expose your Telegram bot, you are exposing a path to Codex on your Mac.

- `.env` is private and gitignored.
- Runtime config is copied with `0600` permissions.
- Only the allow-listed Telegram user/chat can run Codex.
- Group chats are disabled unless `CODEX_TELEGRAM_ALLOW_GROUP_CHATS=true`.
- Images are stored in the private runtime state directory and pruned by retention settings.
- High-risk actions can still hit Codex/OpenAI/macOS confirmations.
- It cannot bypass logins, MFA, macOS privacy prompts, site safety barriers, account limits, or mandatory confirmations.

Use it only with a Telegram account and Mac you trust.

## Honest Limits

- It uses your normal Codex/OpenAI account limits.
- It does not mirror the visible Codex desktop chat UI.
- It waits for Codex to finish before sending the final answer.
- It is not a generic agent platform.
- Computer Use and plugin behavior depend on what your local Codex runtime exposes.
- The bot will feel as capable as the Codex install on that Mac, not more.
- It is not an official OpenAI project.

## Why This Exists

Codex is already useful on a Mac. Codex Relay just makes it reachable from the chat app already on your phone.

Small surface. Local runtime. Real Codex.
