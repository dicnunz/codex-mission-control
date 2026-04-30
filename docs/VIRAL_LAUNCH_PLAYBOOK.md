# Viral Launch Playbook

Goal: make the right small audience feel the pain immediately and try the install.

This is not a broad productivity pitch. The wedge is:

```text
multiple Codex chats are useful until they touch the same browser, inbox, repo, desktop, social account, or payment surface
```

## Launch Order

1. Ship the hardened README/install changes.
2. Update GitHub issue #1 so the tester ask points at `codex-mission-control`.
3. Park PR #5 publicly so the repo looks focused.
4. Post on X with the demo video.
5. Reply with the lane-lock proof, local-only boundary, Telegram boundary, and first-blocker ask.
6. Send the repo to 10 specific Codex-heavy builders by DM or small community replies.
7. Post a follow-up after the first 3 real install reports: what broke, what changed, what still needs testers.
8. Only then post to Hacker News / Reddit / broader builder channels.

## Message Rules

- Lead with the collision, not the architecture.
- Show terminal proof before generated visuals.
- Say Telegram is optional.
- Say local-only and no hosted account.
- Ask for the first blocker, not general feedback.
- Do not claim official OpenAI affiliation.
- Do not claim zero setup.
- Do not imply it bypasses logins, MFA, site limits, confirmations, or account safety.

## X Primary Post

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

Attach `assets/codex-mission-control-demo.mp4`.

## X Replies

```text
the core loop is intentionally boring:

cmc discover
cmc claim BROWSER FLIGHT "using the browser"
cmc claim BROWSER OTHER "also using the browser"

second claim gets blocked

that is the point: Codex chats stop colliding on shared surfaces
```

```text
it does not move projects
it does not run a hosted dashboard
it does not create another account

the hub is local:

~/Codex Mission Control

projects stay where they are
```

```text
Telegram is optional

Mission Control is the hub
Relay is just the phone remote:

Telegram -> LaunchAgent -> Codex CLI -> local hub
```

```text
if you try it, i want the first blocker

not a review
not a feature request pile

the first confusing, broken, slow, or surprising part of install

github issue template is in the repo
```

## Hacker News

Title:

```text
Show HN: Codex Mission Control - local traffic control for multiple Codex chats
```

Body:

```text
I built a local Mac tool for people running several Codex chats at once.

The problem it solves is collisions: two chats touching the same browser session, inbox, GitHub repo, desktop, social account, or payment/account surface.

It creates a local hub, discovers projects as missions, adds lane locks for shared surfaces, generates approval packets for risky actions, and optionally exposes a private Telegram remote.

It is local-only. No hosted account. Projects stay where they are.

Demo:
https://github.com/dicnunz/codex-mission-control/blob/main/assets/codex-mission-control-demo.mp4

Repo:
https://github.com/dicnunz/codex-mission-control

I am looking for the first install blocker from Mac/Codex users who actually run multiple chats.
```

## Reddit / Builder Communities

Use only where self-promotion is allowed.

```text
I built Codex Mission Control, a local Mac tool for people running multiple Codex chats at once.

It is not a hosted agent service. It is traffic control:

- projects become missions
- browser/GitHub/email/social/payment/desktop get lane locks
- risky public/account actions become approval packets
- optional Telegram bot lets you control the local hub from your phone

The core demo does not need Telegram:

git clone https://github.com/dicnunz/codex-mission-control.git
cd codex-mission-control
./scripts/demo.sh

Looking for the first blocker from Codex-heavy Mac users.
```

## LinkedIn

```text
I built Codex Mission Control, a local Mac tool for coordinating multiple Codex chats across real projects.

The interesting problem is not memory. It is shared surfaces.

If several agent runs can touch the same browser, inbox, repo, desktop, social account, or payment/account surface, they need traffic control.

Codex Mission Control creates local mission workspaces, lane locks, outboxes, approval packets, and an optional private Telegram remote.

It is mac-first, local-only, and does not move your projects or create a hosted account.

Repo:
https://github.com/dicnunz/codex-mission-control
```

## Direct DM

```text
i built a small local Mac tool for the exact problem of running multiple Codex chats at once without them stepping on the same browser/repo/inbox/account surface

repo: https://github.com/dicnunz/codex-mission-control

if you have 5 minutes, the useful thing would be running:

git clone https://github.com/dicnunz/codex-mission-control.git
cd codex-mission-control
./scripts/install.sh

and telling me the first confusing/broken thing
```

## Follow-Up After First Installs

```text
early Codex Mission Control install feedback:

1. [blocker/fix]
2. [blocker/fix]
3. [blocker/fix]

the core idea is still holding:

multiple Codex chats need traffic control when they share browser, repo, inbox, desktop, social, or payment/account surfaces

still looking for Mac/Codex users to break the install
```

## What To Do If It Gets Attention

- Reply to technical questions with exact commands, not theory.
- Use `docs/REPLY_BANK.md` for common objections.
- Ask users to open install-feedback issues.
- Fix install blockers immediately.
- Do not add new feature branches during launch unless they remove install friction.
- Do not merge the Gemini/queue/terminal PR until the core install path has enough proof.
