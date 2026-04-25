# Demo Script

Goal: show a phone controlling real Codex on a Mac in seconds.

Generated assets:

```bash
./scripts/record_demo.sh
```

Outputs:

```text
assets/codex-relay-demo.mp4
assets/codex-relay-demo-poster.png
assets/social-card.svg
assets/demo-transcript.svg
```

## Story

```text
Text Codex from Telegram.
Your Mac runs the real Codex CLI locally.
Images, files, apps, shell, Computer Use, and subagents work when your local Codex runtime exposes them.
```

## Shot List

1. `/alive`: show the Mac route is live.
2. Screenshot/image prompt: show Telegram image support.
3. `/tools`: show Computer Use/tool probe.
4. Install frame: show the repo and one-command setup.

## Voiceover

```text
Codex Relay is a Telegram remote for Codex on your Mac.

You text the bot. A local LaunchAgent calls the Codex app CLI. Codex works on the Mac and replies back in Telegram.

It can take screenshots from Telegram, work in folders, run tools, and use whatever your local Codex install exposes.

No hosted relay. No new agent platform. Just your phone, your Mac, and Codex.
```
