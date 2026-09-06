# Install Feedback

Use this guide to report a problem during installation or first use. Start with the first step that is confusing, broken, slow, or surprising.

## Install

Check the [installation requirements](../INSTALL.md#requirements), then run:

```bash
git clone https://github.com/dicnunz/codex-mission-control.git
cd codex-mission-control
./scripts/install.sh
```

Then run:

```bash
cmc status
cmc doctor
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

[Open the install feedback form](https://github.com/dicnunz/codex-mission-control/issues/new?template=install-feedback.yml).
