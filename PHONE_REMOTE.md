# Phone Remote Runbook

Keep the Mac open, awake, online, and signed into Codex. Then talk to the Telegram bot like a terse Codex remote.

## Prompts That Fit

```text
go on Atlas and check what assignments are due
open my portfolio repo and tell me the next best fix
use Computer Use to check if Atlas is running
make this folder easier to understand
generate a cover image for this idea and send me the file path
send a screenshot/photo and ask what changed or what to do next
```

## Thread Flow

```text
/alive
/tools
/try

/new school
/cd Documents
check what class files look important this week

/new portfolio
/cd Projects/my-repo
make the README feel pinned-worthy
```

## Runtime

- Service: `~/Library/LaunchAgents/com.codexrelay.agent.plist`
- Runtime dir: `~/Library/Application Support/CodexRelay`
- Status: `./scripts/status.sh`
- Stop: `./scripts/uninstall.sh`

## Limits

This is a local Codex runtime, not a visible Codex Mac app thread. It can use the same signed-in Codex CLI/plugin setup, but it does not mirror the desktop chat UI.

Telegram photos and image documents are saved in the private runtime state directory and attached to the next Codex prompt.
