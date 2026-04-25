# Launch

Use this as the canonical public copy. Keep claims plain: unofficial, local-first, and no extra hosted relay server.

## Main Post

```text
I built Codex Relay.

I can text my Mac from Telegram.

I send: "make this repo launch-ready without pushing."
My Mac runs local Codex, does the work, and replies when it finishes.

Telegram DM -> LaunchAgent -> Codex CLI -> Mac -> Telegram reply.

No VNC. No extra hosted relay server.

https://github.com/dicnunz/codex-relay#readme
```

Attach: `assets/codex-relay-demo.mp4`

## Install Reply

```text
Install:

git clone https://github.com/dicnunz/codex-relay.git
cd codex-relay
./scripts/install.sh

Then DM your bot:
/alive
/health
/policy
/screenshot
/tools
/latency
/jobs
/automations
send a screenshot and ask what changed

Unofficial. Local-first. Uses your normal Codex/OpenAI account.
```

## Short Reply

```text
It is a small Mac relay: Telegram DM in, local LaunchAgent runs Codex CLI, Telegram reply out. It does not host your tasks or pretend to be the official Codex app UI.
```

## Latency Reply

```text
Same latency as a local Codex run, plus Telegram. Bridge/status commands are quick; real repo, browser, image, and tool tasks usually take tens of seconds or more.
```

## VNC/PWA Reply

```text
Yeah, VNC/PWA/app-server can work.

I wanted the smaller shape: text the task, let the Mac run local Codex, get the final reply back.

No tiny desktop. No hosted relay to maintain.
```

## Safety Reply

```text
The important boundary is the allowlist plus `/policy`. Only the configured Telegram user/chat can call Codex, the bot token/config stay local, and the bot says where it stops before public, account, payment, delete, or confirmation-sensitive actions.
```

## Casual iOS Reply

```text
I wanted this too, so I made a local version:

Telegram DM -> LaunchAgent -> Codex CLI on your Mac -> Telegram reply.

Not official, not VNC, not hosted. Just a small remote for the Mac you already use.

github.com/dicnunz/codex-relay#readme
```

## Promo Captions

```text
I made the missing phone remote for Codex on my Mac.
```

```text
The whole thing is just this small local loop.
```

```text
I did not want a tiny desktop on my phone. I wanted task-level control.
```

```text
Install is basically clone, run, DM your bot.
```

```text
This is for the "my Mac is on my desk and I'm not" workflow.
```

```text
The distinction matters.
```

## Checklist

- Use the generated video only if you label it as an explainer. For launch, prefer real sanitized Telegram footage showing one repo task from prompt to final reply.
- Keep the post plain. No "AGI", "always-on agent", "instant", or fake autonomy language.
- Reply with install commands.
- Keep the latency reply nearby.
- Say plainly that it is unofficial and local-first.
- Do not imply OpenAI affiliation.
- Stop before every public X submit action and ask final confirmation.
