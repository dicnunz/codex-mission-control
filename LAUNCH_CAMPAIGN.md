# Codex Relay Launch Campaign

Main link:

```text
https://github.com/dicnunz/codex-relay#readme
```

The launch posture is simple: Codex Relay is a clean local Mac remote for Codex, not a hosted agent platform and not a VNC replacement.

Do not imply OpenAI or Telegram affiliation. Do not use fake autonomy language. Stop before every public X submit action and ask final confirmation.

## Wave 1: Main Thread

Post:

- Main launch copy from `LAUNCH.md`.
- Attach `assets/codex-relay-demo.mp4` if using the explainer video, or real sanitized Telegram footage when available.

Immediate replies:

- Install reply from `LAUNCH.md`.
- VNC/PWA reply from `LAUNCH.md`.
- Latency reply from `LAUNCH.md`.
- Safety reply from `LAUNCH.md`.

Pin the main post only after traction starts.

## Wave 2: Proof

Post one real use case and keep it plain:

```text
This is the workflow:

Mac open on desk.
Me somewhere else.
Telegram DM in.
Local Codex run.
Telegram reply out.

https://github.com/dicnunz/codex-relay#readme
```

Use proof surfaces people can trust:

- `assets/codex-relay-demo.mp4`
- `/screenshot` from the bot
- `/health`
- `/latency`
- a Telegram image prompt with a visible reply

Reply into relevant Codex-phone conversations with the casual iOS reply from `LAUNCH.md`.

## Wave 3: Visuals

Use generated visuals as supporting posts, not as the main proof:

- `assets/promo/promo-hero.png`
- `assets/promo/promo-flow.png`
- `assets/promo/promo-no-vnc.png`
- `assets/promo/promo-install.png`
- `assets/promo/promo-proof.png`
- `assets/promo/promo-what-it-is.png`

Captions live in `assets/promo/README.md`.

If one generated visual clearly outperforms `assets/social-card.png`, consider replacing the GitHub social preview after a separate visual check.

## Browser Posting Checklist

Before X:

- `./scripts/doctor.sh` passes.
- `./scripts/fresh_clone_test.sh` passes.
- Latest GitHub CI is green.
- Browser Use opens `https://github.com/dicnunz/codex-relay#readme` and the README is visible.
- `assets/codex-relay-demo.mp4` is 1280x720 and readable immediately.
- Promo images are legible at feed size.

On X:

1. Open `https://x.com/home`.
2. Confirm the logged-in account is `@nicdunz`.
3. Draft the post or reply.
4. Attach only the intended public project asset.
5. Stop before the final `Post` or `Reply` click.
6. Ask action-time confirmation for that exact public action.
7. Record posted URLs only after they exist.
