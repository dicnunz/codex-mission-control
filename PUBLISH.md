# Publish Plan

This is the exact public launch path. Do not run the publish commands unless the repo is intentionally ready to go public.

## GitHub

Only run this when you are ready to publish the repo publicly:

```bash
gh repo create dicnunz/codex-relay --public --source=. --remote=origin --push
```

Then in the GitHub repo settings:

- Set description: `Private Telegram remote for Codex on your Mac.`
- Add topics: `codex`, `telegram-bot`, `macos`, `computer-use`, `agents`, `openai`, `launchagent`
- Add social preview: `assets/social-card.svg`
- Pin the repo.

Before publishing:

```bash
python3 -m py_compile codex_relay.py scripts/configure.py
./scripts/doctor.sh
./scripts/status.sh
```

## X Launch

Use `assets/codex-relay-demo.mp4` as the video.

Use the primary post from `LAUNCH_POSTS.md`, then immediately reply with:

```text
Install:

gh repo clone dicnunz/codex-relay
cd codex-relay
./scripts/install.sh

Then DM your bot:
/alive
/tools
/latency
/jobs
/automations
send a screenshot and ask what changed
```

Use the latency reply from `LAUNCH_POSTS.md` if anyone asks why it is not instant.

Do not describe it as an always-on autonomous agent. The clean claim is:

```text
Telegram is the remote. Codex runs locally on the Mac. The reply comes back when Codex finishes.
```

If asked about affiliation:

```text
Unofficial project. Not affiliated with OpenAI or Telegram. It uses your installed Codex app CLI and your normal account limits.
```

If the conversation is about VNC, PWA, or app-server setups:

```text
Those can work. Codex Relay is the smaller shape when you want task-level Codex control from the phone: Telegram DM -> local LaunchAgent -> Codex app CLI -> Telegram reply. No tiny desktop, no Cloudflare Access, no app server to maintain.
```

## Demo Assets

- Video: `assets/codex-relay-demo.mp4`
- Poster: `assets/codex-relay-demo-poster.png`
- Social preview: `assets/social-card.svg`
- README transcript: `assets/demo-transcript.svg`

Before posting, make sure the first frame still shows the complete flow: Telegram -> LaunchAgent -> Codex CLI -> Mac.

Best demo shape:

1. Phone sends `/tools`.
2. Telegram shows a real job receipt.
3. Mac visibly runs local Codex.
4. Telegram receives the final answer.
5. End on the repo quickstart, not a marketing slide.

## Human-Only Boundary

Posting on X is public. Do it only after the demo video, repo, and post text are final.

Pushing the GitHub repo public is also public. Do not push from a cleanup or docs-polish pass unless that was explicitly requested.
