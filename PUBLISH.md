# Publish Plan

This is the exact public launch path.

## GitHub

```bash
gh repo create dicnunz/codex-relay --public --source=. --remote=origin --push
```

Then in the GitHub repo settings:

- Set description: `Run Codex on your Mac from Telegram.`
- Add topics: `codex`, `telegram-bot`, `macos`, `computer-use`, `agents`, `openai`, `launchagent`
- Add social preview: `assets/social-card.svg`
- Pin the repo.

## X Launch

Use `assets/codex-relay-demo.mp4` as the video.

Use the primary post from `LAUNCH_POSTS.md`, then immediately reply with:

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

## Human-Only Boundary

Posting on X is public. Do it only after the demo video, repo, and post text are final.
