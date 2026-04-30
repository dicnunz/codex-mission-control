# Codex Mission Control

Updated: {{UPDATED_AT}}

This is the local command room for Codex work on this Mac.

## Prime Rule

Run projects as missions, not loose chats. Local work can move quickly. Shared surfaces need lane checks and exact approval packets.

Read `CODEX_OPERATING_SPEC.md` at wakeup. It is the behavior contract: outcome first, minimal but sufficient context, explicit tool use, narrow edits, targeted validation, compact final report.

## Source Of Truth

- Hub: `{{HUB}}`
- Missions: `{{HUB}}/missions`
- Ops: `{{HUB}}/_ops`
- Outboxes: `{{HUB}}/_ops/CONSOLE_OUTBOX`

## Coordinator

`FLIGHT` owns shared dashboard merges, lane hygiene, approval stack cleanup, and stale-state checks.

Mission consoles own their own project folders. They write global updates to their outbox and do not rewrite shared files unless explicitly assigned as `FLIGHT`.

## Default Mission Loop

1. Name the concrete outcome.
2. Read only the files needed to ground it.
3. Claim a lane before shared-surface work.
4. Execute one narrow local change or produce one exact approval packet.
5. Verify with the closest targeted check.
6. Report only changed, verified, blocked.
