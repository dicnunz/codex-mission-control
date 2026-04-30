# Codex Mission Control Launch Packet - 2026-04-30

## Current Live Context

- Repo: https://github.com/dicnunz/codex-mission-control
- Public repo state: 13 stars, 1 fork, PR #6 still draft.
- Pinned X post: 2,059 views, 11 likes, 3 reposts, 2 bookmarks, 1 reply.
- Existing pinned post angle works, but it explains too much. The better next post should lead with the failure mode and show proof.

## Required Launch Order

1. Push the local dashboard proof commit and asset.
2. Make PR #6 ready/mergeable or merge it to `main`.
3. Post the new X root post with the clean dashboard crop.
4. Immediately self-reply with the repo/install commands.
5. Reply to questions with exact commands from `docs/REPLY_BANK.md`.

Do not post before step 1. The screenshot should match what new users can install.

## Primary X Post

```text
i don't think the missing layer for heavy Codex use is another agent framework.

it's traffic control.

when a few Codex chats share one Mac, they share the same browser, repos, inbox, desktop, social accounts, and payment/account surfaces.

so i built Codex Mission Control:

local hub
lane locks
approval packets
optional Telegram remote

mac-first. local-only.

looking for Codex-heavy Mac users to run the install and tell me the first blocker.
```

Media:

```text
assets/cmc-dashboard-launch-crop.png
```

## Immediate Self-Reply

```text
repo/install:

https://github.com/dicnunz/codex-mission-control

git clone https://github.com/dicnunz/codex-mission-control.git
cd codex-mission-control
./scripts/demo.sh
./scripts/install.sh

the demo does not need Telegram.
Telegram is just the optional phone remote.
```

## First Replies To Use

If someone asks what it actually does:

```text
the useful bit is intentionally boring:

cmc claim BROWSER FLIGHT "using browser"
cmc claim BROWSER OTHER "also using browser"

the second one gets blocked.

same idea for github, email, public social, commerce, desktop, and global writes.
```

If someone asks about safety:

```text
local-only.

it does not move projects, create a hosted account, bypass logins, or bypass confirmations.

Relay should be treated like SSH into your Mac through Telegram, so it is optional and allow-listed.
```

If someone says they will try it:

```text
the useful feedback is the first blocker.

confusing, broken, slow, surprising, whatever.

open it here so i can fix install friction fast:
https://github.com/dicnunz/codex-mission-control/issues/1
```

## Approval Packet

- Account: @nicdunz
- Action: push launch proof to PR #6 if approved separately, then publish one root X post and one immediate self-reply
- Destination: https://x.com/nicdunz
- Final text: use `Primary X Post` and `Immediate Self-Reply` above exactly
- Media: `assets/cmc-dashboard-launch-crop.png` on the root post
- Source links: https://github.com/dicnunz/codex-mission-control, https://github.com/dicnunz/codex-mission-control/issues/1
- Risk notes: public posts; public repo promotion; do not claim official OpenAI/Telegram affiliation; do not imply bypassing confirmations/logins/MFA
- Approval phrase: `approve X launch @nicdunz CMC 2026-04-30`
