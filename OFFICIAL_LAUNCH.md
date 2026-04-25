# Official Launch Payload

## Primary X Post

```text
I built a Telegram remote for Codex on your Mac.

Text the bot. Your Mac runs the real Codex CLI locally and replies back.

No hosted relay. No new agent platform.

https://github.com/dicnunz/codex-relay
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
send a screenshot and ask what broke
```

## Preflight

```bash
./scripts/doctor.sh
ffprobe -v error -show_entries format=duration,size assets/codex-relay-demo.mp4
git status --short --branch
```

## Public Repo

```text
https://github.com/dicnunz/codex-relay
```
