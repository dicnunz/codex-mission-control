# Publish Plan

This is the exact public launch path. Do not run the publish commands unless the repo is intentionally ready to go public.

## GitHub

If `origin` already points at `dicnunz/codex-relay`:

```bash
git status --short
git add -A
git commit -m "Prepare public Codex Relay launch"
git push -u origin main
gh repo edit dicnunz/codex-relay --visibility public
```

If the repo does not exist yet:

```bash
gh repo create dicnunz/codex-relay --public --source=. --remote=origin --push
```

Then in the GitHub repo settings:

- Set description: `Private Telegram remote for Codex on your Mac.`
- Add topics: `codex`, `codex-cli`, `telegram-bot`, `macos`, `launchagent`, `local-first`, `openai`
- Upload custom social preview: `assets/social-card.png` (1280x640)
- Pin the repo.

Before publishing:

```bash
python3 -m py_compile codex_relay.py scripts/configure.py
./scripts/doctor.sh
./scripts/status.sh
./scripts/fresh_clone_test.sh
./scripts/record_demo.sh
```

## X Launch

Use `assets/codex-relay-demo.mp4` only if you label it as an explainer. For launch, prefer real sanitized Telegram footage showing one repo task from prompt to final reply.

Use the main post from `LAUNCH.md`, then immediately reply with:

```text
Install:

git clone https://github.com/dicnunz/codex-relay.git
cd codex-relay
./scripts/install.sh

Then DM your bot:
/alive
/screenshot
/tools
/latency
/jobs
/automations
send a screenshot and ask what changed
```

Use the latency reply from `LAUNCH.md` if anyone asks why it is not instant.

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
- Social preview: `assets/social-card.png`
- README transcript: `assets/demo-transcript.svg`
- Local status page: `./scripts/status_ui.sh`

Before posting, make sure the first frame still shows the complete flow: Telegram -> LaunchAgent -> Codex CLI -> Mac.

Best demo shape:

1. Phone sends a real repo task.
2. Telegram shows a job receipt.
3. Mac visibly runs local Codex.
4. Telegram receives the final answer.
5. Run `/screenshot` and `/health` as proof.
6. End on the repo quickstart, not a marketing slide.

Second-post angle:

```text
Codex Relay is now the cleaner version of the idea:

Telegram DM -> local LaunchAgent -> Codex CLI on your Mac -> Telegram reply.

Images, jobs/cancel/history, brief/verbose modes, latency/status, macOS CI, fresh-clone test, and a tiny local status page.

github.com/dicnunz/codex-relay
```

## Human-Only Boundary

Posting on X is public. Do it only after the demo video, repo, and post text are final.

Pushing the GitHub repo public is also public. Do not push from a cleanup or docs-polish pass unless that was explicitly requested.
