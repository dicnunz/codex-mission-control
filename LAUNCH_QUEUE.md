# X Launch Queue

Use this order. Keep each post visually quiet and concrete.

Main link:

```text
https://github.com/dicnunz/codex-relay#readme
```

## 1. Main Post

Attach: `assets/codex-relay-demo.mp4`

```text
I wanted Codex from my phone without VNC, so I built a small local remote.

Telegram DM -> LaunchAgent -> Codex CLI on my Mac -> Telegram reply.

No hosted relay. No tiny desktop. The Mac does the work.

https://github.com/dicnunz/codex-relay#readme
```

## 2. Install Reply

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

Unofficial. Local-first. Uses your normal Codex/OpenAI account.
```

## 3. Proof Reply

Attach: `assets/promo/promo-flow.png`

```text
The whole loop is intentionally small:

Telegram DM -> local LaunchAgent -> Codex CLI -> your Mac -> Telegram reply.
```

## 4. Latency Reply

```text
Latency is basically a local Codex run plus Telegram.

Bridge/status commands are quick. Real repo, browser, image, and tool tasks usually take tens of seconds or more.
```

## 5. Safety Reply

```text
Boundary:

Only your configured Telegram user/chat can call it.
Token/config stay local.
/policy shows where it stops before public, account, payment, delete, or confirmation-sensitive actions.
```

## 6. VNC/PWA Reply

```text
VNC/PWA/app-server setups can work.

I wanted the smaller shape: text the task, let the Mac run local Codex, get the final answer back.

No tiny desktop. No web service to maintain.
```

## 7. Visual Followups

Use one per post, not all at once:

- `assets/promo/promo-hero.png`: `I made the missing phone remote for Codex on my Mac.`
- `assets/promo/promo-no-vnc.png`: `I did not want a tiny desktop on my phone. I wanted task-level control.`
- `assets/promo/promo-install.png`: `Install is basically clone, run, DM your bot.`
- `assets/promo/promo-proof.png`: `This is for the "my Mac is on my desk and I'm not" workflow.`
- `assets/promo/promo-what-it-is.png`: `The distinction matters.`

## Final Submit Rule

Draft and attach freely. Stop before each public `Post` or `Reply` click and ask final confirmation for that exact action.
