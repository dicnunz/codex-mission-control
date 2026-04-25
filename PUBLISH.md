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

Post the video first, not the repo link first.

Use the short post from `LAUNCH_POSTS.md`, then immediately reply with:

```text
GitHub: https://github.com/dicnunz/codex-relay

Install:
git clone https://github.com/dicnunz/codex-relay.git
cd codex-relay
./scripts/install.sh
```

## Human-Only Boundary

Publishing the repo and posting on X are public actions. Do them only when the demo video is ready.
