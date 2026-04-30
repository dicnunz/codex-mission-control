# Launch Packet

Canonical launch plan: [docs/VIRAL_LAUNCH_PLAYBOOK.md](docs/VIRAL_LAUNCH_PLAYBOOK.md).
Public reply bank: [docs/REPLY_BANK.md](docs/REPLY_BANK.md).

## Primary Post

```text
i kept running a bunch of Codex chats at once and they started stepping on each other

same browser
same repo
same inbox
same account surfaces

so i built a local traffic-control layer:

Codex Mission Control

missions
lane locks
approval packets
optional Telegram remote

mac-first
local-only
no hosted account

github.com/dicnunz/codex-mission-control

looking for 10 Codex-heavy Mac users to try the install and tell me the first blocker
```

Attach `assets/codex-mission-control-demo.mp4` first. If video upload fails, attach `assets/social-card.png`.

## Reply 1

```text
the core loop is intentionally boring:

cmc discover
cmc claim BROWSER FLIGHT "using the browser"
cmc claim BROWSER OTHER "also using the browser"

second claim gets blocked

that is the point: Codex chats stop colliding on shared surfaces
```

## Reply 2

```text
it does not move projects
it does not run a hosted dashboard
it does not create another account

the hub is local:

~/Codex Mission Control

projects stay where they are
```

## Reply 3

```text
Telegram is optional

Mission Control is the hub
Relay is just the phone remote:

Telegram -> LaunchAgent -> Codex CLI -> local hub
```

## Reply 4

```text
if you try it, i want the first blocker

not a review
not a feature request pile

the first confusing, broken, slow, or surprising part of install

github issue template is in the repo
```

## Approval Packet: X Post

- Mission: CMC
- Exact action: publish primary X post
- Target: Nic's X account
- Exact text/change/object: use `Primary Post` above exactly
- Evidence checked: repo URL, README, CI status, local QA, launch packet
- Risk flags: public post, reputational claim
- Why now: request first 10 real builder installs
- Proof after execution: screenshot or X URL
- Stop condition: after one post and no extra replies unless separately approved

## Approval Packet: X Reply Thread

- Mission: CMC
- Exact action: publish four replies under the primary X post
- Target: the primary CMC launch post
- Exact text/change/object: use Reply 1 through Reply 4 above exactly
- Evidence checked: primary post live and attached asset rendered
- Risk flags: public replies, reputational claims
- Why now: explain install/use/safety boundaries
- Proof after execution: screenshot or X URL for each reply
- Stop condition: after four replies

## Approval Packet: GitHub Issue Cleanup

- Mission: CMC
- Exact action: update issue #1 body and title to use `codex-mission-control` URLs and current commands
- Target: `dicnunz/codex-mission-control` issue #1
- Exact text/change/object:
  - Title: `Install feedback wanted: first 10 builders`
  - Body:

````text
I am looking for 10 real Mac/Codex users to try the Codex Mission Control install path and report the first blocker.

Start here:

```bash
git clone https://github.com/dicnunz/codex-mission-control.git
cd codex-mission-control
./scripts/install.sh
```

Then run:

```bash
cmc status
cmc lanes
cmc packet
cmc dashboard
```

Optional Telegram path:

```bash
./cmc relay install
```

Then DM the bot:

```text
/mission status
/mission lanes
/mission packet
/health
/policy
```

Try one safe local task, then report what was confusing, broken, slow, or surprising.

Do not paste bot tokens, `.env`, private screenshots, personal files, raw Codex transcripts, auth files, or unredacted logs.

Feedback form: https://github.com/dicnunz/codex-mission-control/issues/new?template=install-feedback.yml

Builder script: https://github.com/dicnunz/codex-mission-control/blob/main/docs/FIRST_10_BUILDERS.md

Demo: https://github.com/dicnunz/codex-mission-control/blob/main/assets/codex-mission-control-demo.mp4
````
- Evidence checked: issue #1 still references old repo name
- Risk flags: public GitHub issue edit
- Why now: remove launch confusion before recruiting testers
- Proof after execution: issue URL
- Stop condition: after one issue edit

## Approval Packet: Publish Launch-Hardening Changes

- Mission: CMC
- Exact action: create a branch, commit the local launch-hardening changes, push it, and open a draft PR
- Target: `dicnunz/codex-mission-control`
- Exact text/change/object:
  - Branch: `codex/launch-hardening`
  - Commit message: `Harden Mission Control launch surface`
  - PR title: `Harden Mission Control launch surface`
  - PR body:

```text
## Summary
- makes first-run setup more trust-preserving by defaulting AGENTS.md adoption to preview-first
- adds `cmc dashboard`
- removes model-specific defaults and public GPT-5.5 wording
- adds install, first-builder, viral launch, reply-bank, and launch-packet docs
- refreshes the demo video asset after copy updates

## Verification
- `python3 -m py_compile mission_control.py codex_relay.py scripts/configure.py scripts/smoke_test.py`
- `PYTHONPATH=. python3 scripts/smoke_test.py`
- `./scripts/qa.sh`
- `./scripts/fresh_clone_test.sh`
- `git diff --check`
- asset dimension/duration checks
```
- Evidence checked: local QA passed and worktree contains only launch-hardening changes
- Risk flags: public GitHub push/PR
- Why now: make the repo ready before public launch traffic
- Proof after execution: pushed branch URL and PR URL
- Stop condition: after one draft PR; do not merge without separate exact approval

## Approval Packet: GitHub Repo Metadata

- Mission: CMC
- Exact action: update public GitHub repository description and topics
- Target: `dicnunz/codex-mission-control`
- Exact text/change/object:
  - Description: `Local traffic control for multiple Codex chats on your Mac.`
  - Topics: `codex`, `codex-cli`, `macos`, `local-first`, `automation`, `telegram-bot`, `launchagent`, `agent-ops`, `approval-gates`, `remote-control`
- Evidence checked: current repo description is less direct than the launch hook
- Risk flags: public repo metadata change
- Why now: improve link preview and GitHub search clarity before public posts
- Proof after execution: repository URL screenshot or `gh repo view` output
- Stop condition: after metadata update only

## Approval Packet: Tagged Release

- Mission: CMC
- Exact action: create a GitHub release after launch-hardening changes are merged
- Target: `dicnunz/codex-mission-control`
- Exact text/change/object:
  - Tag: `v0.2.1`
  - Title: `Codex Mission Control v0.2.1`
  - Notes:

```text
Launch-hardening release.

- safer preview-first installer behavior for project AGENTS.md adoption
- `cmc dashboard`
- model-neutral Relay defaults and mission wording
- install, first-builder, viral launch, reply-bank, and launch-packet docs
- refreshed 44-second demo asset
```
- Evidence checked: launch-hardening PR merged and CI green
- Risk flags: public GitHub release
- Why now: give launch traffic a stable version marker
- Proof after execution: release URL
- Stop condition: after one release

## Approval Packet: Draft PR Park

- Mission: CMC
- Exact action: comment on draft PR #5 that it is parked until core install feedback lands
- Target: `dicnunz/codex-mission-control` PR #5
- Exact text/change/object: `Parking this until the core Mission Control install path has more real-user feedback. The Gemini/queue/terminal/file-transfer scope is useful, but it widens the product before the current lane/approval/Relay core has enough installs.`
- Evidence checked: PR #5 is open draft and widens scope
- Risk flags: public GitHub PR comment
- Why now: keep launch scope tight
- Proof after execution: PR comment URL
- Stop condition: after one comment, no close/merge unless separately approved

## Approval Packet: Hacker News

- Mission: CMC
- Exact action: submit a Show HN post
- Target: Hacker News
- Exact text/change/object:
  - Title: `Show HN: Codex Mission Control - local traffic control for multiple Codex chats`
  - URL: `https://github.com/dicnunz/codex-mission-control`
  - Optional first comment: use the Hacker News body in `docs/VIRAL_LAUNCH_PLAYBOOK.md`
- Evidence checked: repo README, install docs, demo asset, local QA
- Risk flags: public post, reputational claim, community self-promotion norms
- Why now: broaden reach after X/GitHub tester ask is live
- Proof after execution: HN item URL
- Stop condition: after one submission and one optional first comment

## Approval Packet: Reddit / Builder Community

- Mission: CMC
- Exact action: post the Reddit / Builder Communities copy
- Target: one self-promotion-appropriate community selected live before posting
- Exact text/change/object: use the Reddit / Builder Communities copy in `docs/VIRAL_LAUNCH_PLAYBOOK.md`
- Evidence checked: community rules allow the post, repo link works, install docs current
- Risk flags: public post, possible self-promotion removal
- Why now: reach Codex-heavy builders outside X
- Proof after execution: post URL or screenshot
- Stop condition: after one post only

## Approval Packet: Direct Builder DM

- Mission: CMC
- Exact action: send the direct DM copy to one specific Codex-heavy builder
- Target: one named recipient selected by Nic
- Exact text/change/object: use the Direct DM copy in `docs/VIRAL_LAUNCH_PLAYBOOK.md`
- Evidence checked: recipient is relevant and not a cold spam blast
- Risk flags: outreach DM
- Why now: get first install blockers from real target users
- Proof after execution: sent-message screenshot or URL
- Stop condition: after one DM; repeat only with a new exact recipient approval
