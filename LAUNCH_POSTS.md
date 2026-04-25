# Launch Posts

## Primary X Post

```text
I built Codex Relay.

Text your Mac's Codex from Telegram.

Telegram DM -> local LaunchAgent -> Codex CLI -> Telegram reply.

No VNC. No hosted relay. No PWA to maintain.

https://github.com/dicnunz/codex-relay
```

Attach: `assets/codex-relay-demo.mp4`

## Alternate Short

```text
Codex Relay turns Telegram into a phone remote for local Codex on your Mac.

Your phone sends the task.
Your Mac runs the local Codex CLI.
Telegram gets the final answer back.

https://github.com/dicnunz/codex-relay
```

## VNC Angle

```text
I got tired of the "remote into my Mac from my phone" shape.

I don't want a tiny desktop. I want to text Codex:
"check this repo"
"look at this screenshot"
"inspect my automations"
"stop before posting/pushing"

So I built Codex Relay.

Telegram in. Local Codex CLI on the Mac. Telegram out.
```

## App Server Angle

```text
The PWA + app server route works, but then you own a tiny product.

Codex Relay is the smaller shape:
Telegram bot
local LaunchAgent
Codex app CLI
allowlisted user

No hosted relay account. No Cloudflare Access. No phone terminal.
```

## Romain/Team Reply Draft

```text
This is exactly the gap I tried to make small: not VNC, not a phone terminal, not a PWA/app-server product to maintain.

Telegram DM -> local LaunchAgent -> Codex app CLI on the Mac -> Telegram reply.

It supports screenshots/images, named threads, jobs/cancel/history, latency/status checks, brief/verbose modes, and a guardrailed /automations inspection shortcut.

github.com/dicnunz/codex-relay
```

## First Reply

```text
Install:

gh repo clone dicnunz/codex-relay
cd codex-relay
./scripts/install.sh

Then DM your bot:
/alive
/tools
/latency
/jobs
/automations
send a screenshot and ask what changed

Unofficial. Local-first. Uses your normal Codex/OpenAI account.
```

## Latency Reply

Use this if someone asks "how fast is it?" or "why does it take a while?":

```text
It is not trying to be instant chat. Telegram is just the remote; the Mac still starts the local Codex CLI, uses whatever tools the local runtime exposes, and sends the final reply back. A trivial probe on my Mac was about 5-6s. Real repo/browser/image tasks can take tens of seconds or minutes.
```

Short version:

```text
Same latency as a local Codex run, plus Telegram. Trivial prompt was ~5s here; real tool work is usually tens of seconds or more.
```

## Comment Reply

Use this if someone asks what it actually is:

```text
It is a small Mac relay: Telegram DM in, local LaunchAgent runs Codex CLI, Telegram reply out. It does not host your tasks or pretend to be the official Codex app UI.
```

## Safety Reply

```text
The important boundary is the allowlist. Only the configured Telegram user/chat can call Codex, and the bot token/config stay local. Still, it is a path to Codex on your Mac, so use it only with a Telegram account and Mac you trust.
```

## Launch Checklist

- Use the generated demo video, not a raw UI accident.
- First frame must make the flow obvious: Telegram -> Codex CLI -> Mac.
- Keep the post plain. No "AGI", "always-on agent", "instant", or fake autonomy language.
- Reply with install commands.
- Keep the latency reply nearby.
- Pin the repo after posting.
- If asked, say plainly that it is unofficial and local-first.
- Do not imply OpenAI affiliation.
