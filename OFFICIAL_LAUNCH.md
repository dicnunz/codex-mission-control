# Official Launch Payload

## Primary X Post

```text
I left my Mac open on my desk and controlled Codex from Telegram.

So I built Codex Relay.

Text your bot. Your Mac runs the real Codex CLI locally with files, repos, apps, Computer Use, and subagents.

Private. Local. gpt-5.5. LaunchAgent. Named threads.

GitHub: https://github.com/dicnunz/codex-relay
```

Attach: `assets/codex-relay-demo.mp4`

## First Reply

```text
Install:

git clone https://github.com/dicnunz/codex-relay.git
cd codex-relay
./scripts/install.sh

Then DM your bot:
/alive
/tools
/try
```

## GitHub Publish Commands

```bash
gh repo create dicnunz/codex-relay --public --source=. --remote=origin --push
gh repo edit dicnunz/codex-relay --description "Run Codex on your Mac from Telegram." --homepage ""
gh repo edit dicnunz/codex-relay --add-topic codex --add-topic telegram-bot --add-topic macos --add-topic computer-use --add-topic agents --add-topic openai --add-topic launchagent
```

## Final Preflight Already Passed

- Local relay running.
- `./scripts/doctor.sh` passed.
- Telegram `/alive`, `/capabilities`, `/try` passed.
- Telegram repo task passed.
- Telegram subagent task passed.
- Demo MP4 valid at 1280x720.
- Release zip contains no `.env`, token screenshot, runtime state, pycache, or `.DS_Store`.
