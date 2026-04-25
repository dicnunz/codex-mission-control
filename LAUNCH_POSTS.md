# Launch Posts

## X Short

I built Codex Relay.

It lets me text Codex from Telegram and have my Mac do the work locally.

Mac open on desk. Me on phone. Telegram -> Codex CLI -> Computer Use/apps/files/repos.

Private, local, `gpt-5.5`, LaunchAgent, named threads.

GitHub: https://github.com/YOUR_USERNAME/codex-relay

## X Thread

I made my Mac feel remotely alive from Telegram.

Codex Relay is a private phone remote for Codex on macOS.

Leave the laptop open, DM your bot, and Codex runs locally with your files, repos, apps, plugins, and Computer Use.

It is not a hosted service or wrapper around another agent framework.

The flow is:

Telegram -> local LaunchAgent -> Codex CLI -> your Mac

It supports named threads, per-thread folders, `/status`, `/tools`, and `gpt-5.5` by default.

The setup script detects Codex, asks for a BotFather token, waits for your `/start`, allow-lists your Telegram user, and installs the background agent.

GitHub: https://github.com/YOUR_USERNAME/codex-relay
