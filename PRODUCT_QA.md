# Product QA

## Quality Bar

Codex Relay should feel like a clean Mac remote, not a novelty bot.

The product is ready to show only when these are true:

- The LaunchAgent is running.
- The installed runtime script matches the repo.
- `./scripts/doctor.sh` passes.
- The configured Codex app CLI can run `gpt-5.5`.
- Telegram images are saved privately and attached to Codex.
- The demo video is readable in the first three seconds.
- The README explains power and risk without hype.

## Verified Locally

- LaunchAgent loaded: `com.codexrelay.agent`.
- Runtime script matches the repo copy.
- `./scripts/doctor.sh` passes.
- Local `gpt-5.5` image check works through `/Applications/Codex.app/Contents/Resources/codex`.
- Real Telegram image round trip works: Telegram photo + caption -> private attachment save -> Codex `--image` -> Telegram reply.
- Generated demo is 1280x720 H.264.

## Current Human-Only Checks

- Repost to X only after the final post text is confirmed.

## Launch Bar

Public launch should include:

1. Clean demo video.
2. Plain one-post explanation.
3. GitHub link.
4. Install reply.
5. No exaggerated claims.
