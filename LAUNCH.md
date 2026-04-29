# Launch

Main link:

```text
https://github.com/dicnunz/codex-mission-control
```

## Positioning

Product sentence:

```text
Codex Mission Control gives Codex a control room for your Mac.
```

Origin line:

```text
I kept running multiple Codex chats at once, and they started stepping on the same browser and account surfaces. This is the traffic-control layer.
```

GitHub description:

```text
Codex Mission Control gives Codex a control room for your Mac.
```

## First X Post

```text
i kept running a bunch of codex chats at once and they started stepping on each other

two would try to use the same browser, inbox, github repo, desktop, or account surface at the same time

so i turned the setup into a small product:

Codex Mission Control

it gives Codex a control room for your Mac

it finds your projects, turns them into missions, locks shared surfaces, keeps approval packets, and lets you text the whole thing from Telegram

local-only
mac-first
no hosted account

github.com/dicnunz/codex-mission-control
```

Attach `assets/social-card.png` or the 45-second demo video.

## Follow-Ups

Why it exists:

```text
the hard part is not just memory

it is shared surfaces

browser, email, github, desktop, payments, social accounts

if multiple codex runs can touch them, they need traffic control
```

Install:

```text
install is:

git clone https://github.com/dicnunz/codex-mission-control.git
cd codex-mission-control
./scripts/install.sh

it sets up the local hub first
telegram is optional
projects stay where they are
```

Relay:

```text
Mission Control Relay is just the phone remote

Telegram -> LaunchAgent -> Codex CLI -> local Mission Control hub

the hub is the product
the phone is the remote
```

Safety:

```text
it is intentionally boring

symlinks
markdown ops files
lane locks
approval packets
LaunchAgent relay

no hosted account
no login/MFA/confirmation bypass
```

## Demo Script

Keep it under 45 seconds:

```text
1. Fresh clone.
2. Run ./scripts/install.sh.
3. Show cmc discover finding one existing project.
4. Claim BROWSER with FLIGHT.
5. Try a second BROWSER claim and show held: BROWSER.
6. Open the local dashboard.
7. Run cmc packet.
8. Show Telegram /mission status.
```

No theory. No architecture talk. Prove the collision layer.

## Visual Order

Post order:

```text
1. assets/social-card.png
2. assets/codex-mission-control-demo.mp4
3. assets/visuals/origin-lanes.png
4. assets/visuals/lane-lock.png
5. assets/visuals/approval-packet.png
6. assets/visuals/phone-remote.png
```

Carousel order:

```text
1. assets/visuals/origin-lanes.png
2. assets/visuals/project-discovery.png
3. assets/visuals/lane-lock.png
4. assets/visuals/approval-packet.png
5. assets/visuals/phone-remote.png
6. assets/visuals/local-only.png
```

Generated visuals carry mood and shape. Terminal, dashboard, and Telegram footage carry proof.

## Audience

For:

- Codex users running several chats or projects at once
- people who use Codex against real local repos
- people who want Telegram as a private remote
- people who need approval gates before public/account/payment actions

Not for:

- users who run one simple Codex chat at a time
- people who want a hosted agent service
- people who want browser/VNC screen control
- people trying to bypass logins, MFA, account limits, or confirmations

## Do Not Claim

- official OpenAI product
- zero setup
- hosted agent service
- unlimited model usage
- bypasses confirmations, logins, MFA, CAPTCHAs, macOS privacy, or account limits
- replaces VNC or remote desktop
