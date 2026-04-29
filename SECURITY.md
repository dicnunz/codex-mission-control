# Security

Codex Mission Control is intentionally powerful because it organizes local Codex work around your real Mac, real files, and real logged-in tools.

Treat Mission Control Relay like SSH into your Mac through Telegram.

![Local-only Mission Control boundary](assets/visuals/local-only.png)

## Local State

- Mission hub: `~/Codex Mission Control`
- Relay runtime: `~/Library/Application Support/CodexRelay`
- LaunchAgent: `~/Library/LaunchAgents/com.codexrelay.agent.plist`
- Private config: `.env`, written with `0600` permissions

The product is local-only. There is no hosted Mission Control account, sync backend, or web dashboard.

Project discovery does not move files. `cmc adopt` is a dry run by default; `cmc adopt --write` is the only command that writes Mission Control instruction blocks into discovered project `AGENTS.md` files. Existing `AGENTS.md` files are backed up before changes.

## Approval Boundary

Mission Control is built around a hard line:

- local inspection, drafts, tests, and repo work can proceed inside the configured Codex sandbox
- shared surfaces should use lane locks first
- public posts, emails, DMs, account changes, payments, purchases, deletes, applications, uploads, and sensitive submissions require exact approval packets

An approval packet must name the mission, action, target, exact text/change/object, evidence checked, risks, why now, proof path, and stop condition.

## Telegram Relay

Relay uses a dedicated Telegram bot and an allow-listed private Telegram user/chat.

Keep the bot token private. Do not paste `.env`, raw logs, screenshots with secrets, auth files, or private transcripts into issues.

Relay cannot bypass:

- logins
- MFA
- CAPTCHAs
- macOS privacy prompts
- site safety barriers
- Codex/OpenAI limits
- required confirmations

## Shared Surfaces

The default lanes are:

```text
BROWSER
GITHUB
EMAIL
PUBLIC_SOCIAL
COMMERCE
DESKTOP
GLOBAL_WRITE
```

Lane locks prevent accidental collisions. They are not a permission system. The user and the local Codex sandbox are still the real boundary.

## Reporting Issues

Include:

- macOS version
- Codex CLI version
- `./cmc status`
- `./scripts/doctor.sh` output with secrets removed
- exact command that failed

Do not include bot tokens, `.env`, private screenshots, raw Telegram updates, auth files, or personal data.
