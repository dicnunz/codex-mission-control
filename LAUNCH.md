# Launch

Main link:

```text
https://github.com/dicnunz/codex-mission-control#readme
```

## Positioning

Codex Mission Control is the local control room for running Codex across real projects.

Tagline:

```text
Stop running Codex like loose chats. Give it a control room.
```

One-line pitch:

```text
One install gives Codex a local mission hub: project discovery, shared-surface locks, approval packets, a private local dashboard, outboxes, and an optional Telegram remote.
```

## Main Post

```text
i kept running a bunch of codex chats at once and they started stepping on each other

two would try to use the browser or same account surface at the same time, or one would stale-read another's state

so i turned the setup into a product:

Codex Mission Control

it finds your projects, creates mission workspaces, locks shared surfaces, keeps approval packets, and lets you text the whole thing from Telegram

local-only, mac-first, no hosted account

github.com/dicnunz/codex-mission-control
```

Attach the clearest demo asset available. Prefer real terminal + Telegram footage over generated visuals.

## Visual Stack

Use generated visuals as proof-shaping, not proof replacement.

Primary:

```text
assets/visuals/origin-lanes.png
assets/visuals/hero-control-room.png
assets/codex-mission-control-demo.mp4
```

Carousel:

```text
1. assets/visuals/origin-lanes.png
2. assets/visuals/project-discovery.png
3. assets/visuals/lane-lock.png
4. assets/visuals/approval-packet.png
5. assets/visuals/phone-remote.png
6. assets/visuals/local-only.png
```

Rule: generated plates carry mood and shape; terminal/dashboard/Telegram footage carries proof.

## Demo Script

Keep it under 45 seconds:

1. Fresh clone.
2. Run `./scripts/install.sh`.
3. Show `cmc discover` finding an existing project.
4. Show `cmc claim BROWSER FLIGHT "demo"` blocking a second claim.
5. Show the local dashboard.
6. Show `cmc packet`.
7. Show Telegram `/mission status`.

No theory. No architecture diagram as the main proof.

## Replies

Install:

```text
install is just:

git clone https://github.com/dicnunz/codex-mission-control.git
cd codex-mission-control
./scripts/install.sh

it sets up the local hub first
opens a private local dashboard
telegram is optional
project AGENTS.md adoption is offered during install, defaults yes interactively, and backs up existing files
```

Why:

```text
the problem is not "agents need memory"

the problem is shared surfaces

browser, email, github, desktop, payments, social accounts

if multiple codex runs can touch them, they need traffic control
```

Relay:

```text
Mission Control Relay is the phone remote inside Mission Control

Telegram -> LaunchAgent -> Codex CLI -> Mission Control hub

same local Mac, bigger operating system around it
```

Safety:

```text
it is local-only and intentionally boring

symlink index, markdown ops files, lane locks, approval packets, launchagent relay

no hosted account
no bypassing logins / MFA / confirmations
```

## Do Not Claim

- official OpenAI product
- zero setup
- hosted agent platform
- unlimited model usage
- bypasses confirmations, logins, MFA, CAPTCHAs, macOS privacy, or account limits
- replaces VNC or remote desktop
