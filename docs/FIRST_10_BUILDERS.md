# First 10 Builders

Goal: find the first install blocker, not collect compliments.

## Ask

Try Codex Mission Control on a Mac with Codex installed. Report the first thing that is confusing, broken, slow, or surprising.

## Install

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

## What To Report

- Mac model and macOS version
- Codex app or CLI state before install
- exact first blocker
- expected result
- short redacted output if useful

Do not paste bot tokens, `.env`, private screenshots, personal files, raw Codex transcripts, auth files, or unredacted logs.

Feedback form:

```text
https://github.com/dicnunz/codex-mission-control/issues/new?template=install-feedback.yml
```

## Paid Async Audit

If you want the workflow mapped instead of only reporting an install blocker,
use the paid setup audit template:

```text
https://github.com/dicnunz/codex-mission-control/issues/new?template=paid-setup-audit.yml
```

Mini audit:

```text
https://nicdunz.gumroad.com/l/agent-workflow-mini-audit
```

Full workflow audit:

```text
https://nicdunz.gumroad.com/l/agent-workflow-audit
```

Use redacted files and public repo links only. Do not paste tokens, secrets,
private transcripts, auth files, or personal data. No call required.
