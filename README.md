# Codex Relay

Run Codex on your Mac from Telegram.

<p align="center">
  <img src="assets/social-card.svg" alt="Codex Relay: Telegram to Codex CLI to your Mac" width="100%">
</p>

Codex Relay is a private phone remote for the Codex Mac app runtime. DM your Telegram bot and your Mac runs a real local `codex exec` session with your files, repos, apps, plugins, and Computer Use access.

No hosted middleman. No fake agent shell. Telegram -> Codex CLI -> your Mac.

> Unofficial project. Not affiliated with OpenAI or Telegram.

## 10-Second Demo

Leave your Mac open and awake. From your phone:

```text
/tools
go on Atlas and check what assignments are due
```

Codex works locally on the Mac and replies in Telegram.

<p align="center">
  <img src="assets/demo-transcript.svg" alt="Example Telegram transcript controlling Codex Relay" width="760">
</p>

## What You Get

- `gpt-5.5` by default through the Codex Mac app CLI.
- Private Telegram bot allow-listed to your Telegram user.
- Persistent named threads: `/new`, `/use`, `/list`.
- Per-thread folders: `/cd`, `/where`, `/home`.
- macOS LaunchAgent, so it stays alive after setup.
- Tool probe for Computer Use and app visibility.
- Local `.env`; no cloud relay or extra agent account.

## Install

Requirements:

- macOS
- Codex Mac app installed and signed in
- Telegram account

```bash
git clone https://github.com/dicnunz/codex-relay.git
cd codex-relay
./scripts/install.sh
```

The installer handles the Mac side. The only human credential step is creating a Telegram bot with `@BotFather` and pasting the token.

Setup flow:

1. Detect the Codex Mac app CLI.
2. Ask for your Telegram bot token.
3. Verify the bot with Telegram.
4. Wait for you to send `/start` to the bot.
5. Allow-list that Telegram user.
6. Install and start the LaunchAgent.

Then DM the bot:

```text
/status
/tools
```

If anything feels off:

```bash
./scripts/doctor.sh
```

## Commands

Normal messages go to the active Codex thread.

```text
/new name     start a fresh Codex thread
/use name     switch threads
/list         show threads
/where        show current thread and folder
/cd path      set this thread's folder
/home         set this thread to your home folder
/status       show runtime state
/tools        test Computer Use/tool access
/reset        restart the current thread
/ping         check the bridge
```

## Run It Through Codex

Paste this into the Codex Mac app after cloning:

```text
Set up this repo for me. Run ./scripts/install.sh, help me create the Telegram bot token if needed, then verify /status and /tools.
```

## Manage It

```bash
./scripts/doctor.sh
./scripts/status.sh
./scripts/uninstall.sh
```

Runtime files:

```text
~/Library/Application Support/CodexRelay
~/Library/LaunchAgents/com.codexrelay.agent.plist
```

## Safety

Codex Relay is intentionally powerful: Telegram messages can make Codex act on your Mac.

- `.env` is private and gitignored.
- The installer copies config into a `0600` runtime file.
- Only your allow-listed Telegram user can run Codex.
- Default sandbox: `danger-full-access`.
- Default approval policy: `never`.
- High-risk actions can still hit OpenAI/Codex safety confirmations.
- macOS privacy prompts still apply.

Use it only with a Telegram account and Mac you trust.

## Honest Limits

- It uses your normal Codex/OpenAI account limits.
- It does not mirror the visible Codex desktop chat UI.
- It cannot bypass site logins, macOS privacy, or mandatory confirmations.
- Computer Use and plugin access depend on what your local Codex runtime exposes.

## Why Not A Generic Agent Platform

Codex Relay is deliberately narrow. It does one thing: make Telegram feel like a remote control for the Codex runtime already on your Mac.

That narrowness is the point. It is easy to inspect, easy to stop, and easy to explain in one video.
