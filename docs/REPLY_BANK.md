# Reply Bank

Use these for public replies after launch. Keep replies specific, short, and tied to the repo.

## What is this?

```text
local traffic control for people running multiple Codex chats at once

projects become missions
shared surfaces get lane locks
risky public/account actions become approval packets
Telegram is optional
```

## Why not just use one chat?

```text
one chat is fine for simple work

this is for people running several Codex threads across different projects where the shared browser, inbox, repo, desktop, social, or payment/account surface becomes the bottleneck
```

## Is this an agent framework?

```text
not really

it is a local coordination layer around Codex work on a Mac:

symlinks
markdown ops files
lane locks
approval packets
LaunchAgent Relay if you want phone control
```

## Is Telegram required?

```text
no

the hub is the product
Telegram Relay is just the optional phone remote

the core demo works without Telegram secrets:

./scripts/demo.sh
```

## Is it safe?

```text
it is local-only and intentionally boring

but Relay should be treated like SSH into your Mac through Telegram

allow-list your private chat, keep the bot token private, and do not use it to bypass confirmations/logins/MFA
```

## Does it move my projects?

```text
no

projects stay where they are
Mission Control creates a local hub and symlink index under:

~/Codex Mission Control
```

## Does it write to my repos?

```text
install is preview-first

cmc adopt shows the AGENTS.md blocks it would add
cmc adopt --write applies them with backups
```

## Why not hosted?

```text
because the shared surfaces are on your Mac:

browser sessions
desktop apps
local repos
private inbox/account state

the useful boundary here is local coordination, not another hosted dashboard
```

## Windows/Linux?

```text
macOS-first right now because it leans on Codex for Mac and LaunchAgent for the optional Relay

the lane/approval/hub idea is portable, but this release is Mac-only
```

## What feedback do you want?

```text
the first blocker

what was confusing, broken, slow, or surprising during install or first use

not a feature wishlist yet
```

## Someone asks for a demo

```text
44-second demo:

https://github.com/dicnunz/codex-mission-control/blob/main/assets/codex-mission-control-demo.mp4

local no-token demo:

git clone https://github.com/dicnunz/codex-mission-control.git
cd codex-mission-control
./scripts/demo.sh
```
