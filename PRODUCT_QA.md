# Product QA

## Quality Bar

Codex Relay should feel like useful Mac infrastructure, not a novelty bot.

The product is ready to show only when these are true:

- The LaunchAgent is running.
- The installed runtime script matches the repo.
- `./scripts/doctor.sh` passes.
- The configured Codex app CLI can run the selected model.
- Telegram images are saved privately and attached to Codex.
- `/screenshot` returns the current Mac screen to Telegram without routing through Codex.
- `/policy` returns the allowed surface and confirmation boundaries.
- The demo video is readable in the first three seconds and shows Telegram -> LaunchAgent -> Codex CLI -> Mac.
- The README explains latency as real Codex runtime, not instant chat latency.
- `./scripts/fresh_clone_test.sh` passes from a clean checkout.
- macOS CI runs syntax, smoke, and local demo checks.
- `./scripts/status_ui.sh` opens a private local status page.
- `./scripts/menu_bar.sh` builds and opens the native macOS menu-bar controller.
- Local latency probe on 2026-04-25: trivial configured Codex CLI request returned in about 4.8-6.3 seconds before Telegram delivery.
- The README explains power and risk without hype.
- Public copy says unofficial and local-first.
- Public copy explains the wedge against VNC and PWA/app-server setups without dunking on them.

## Verified Locally

- LaunchAgent loaded: `com.codexrelay.agent`.
- Runtime script matches the repo copy.
- `./scripts/doctor.sh` passes.
- Local image check works through `/Applications/Codex.app/Contents/Resources/codex`.
- Real Telegram image round trip works: Telegram photo + caption -> private attachment save -> Codex `--image` -> Telegram reply.
- Generated demo is 1280x720 H.264.
- Fresh clone test passes without Telegram secrets.
- Status UI renders from the live `status.sh` output.
- Native menu-bar app builds from Swift source.

## Public Proof Points

- Local LaunchAgent, not a hosted relay account.
- Local Codex app CLI, not a separate agent backend.
- Default model, thinking mode, and speed tier are explicit in `.env.example`.
- Telegram bot is allow-listed to one configured user/chat.
- Runtime state lives under `~/Library/Application Support/CodexRelay`.
- Runtime jobs expose `/jobs`, `/cancel`, and `/history` without logging prompts or responses.
- Verification path is `./scripts/doctor.sh` plus `./scripts/status.sh`.
- Clean-checkout path is `./scripts/fresh_clone_test.sh`.
- Native Mac control surface is `./scripts/menu_bar.sh`.

## Latency QA

Expected behavior:

- `/ping`, `/alive`, `/health`, `/policy`, `/status`, `/where`, and thread commands should return quickly because they do not call Codex.
- `/jobs`, `/cancel`, and `/history` should respond while a long Codex task is running.
- Normal prompts show Telegram typing while Codex is running.
- Normal prompts use the configured model, thinking mode, and speed tier.
- `/screenshot` is a bridge command, not a Codex model call.
- Final replies arrive only after the Codex CLI run finishes.
- Longer waits are normal for image analysis, browser or desktop/app-control work, repo edits, tests, package installs, or prompts that require tool calls.
- A task that exceeds `CODEX_TELEGRAM_TIMEOUT_SECONDS` stops with a timeout message.
- `/history` stores only safe run receipts: status, latency, thread, job id, image count, folder basename, thinking mode, and speed tier.

Public answer:

```text
It is not instant chat. Telegram is just the remote; the Mac still starts the local Codex CLI, uses whatever local tools are available, and then sends the final reply back. Simple checks can be quick, but real repo/browser/image tasks often take tens of seconds or minutes. The default timeout is 10 minutes.
```

## Current Human-Only Checks

- Posting to X is public. Do it only after the final post text, demo video, and GitHub repo are ready.
- Do not push or publish from an automated pass unless explicitly requested.

## Launch Bar

Public launch should include:

1. Clean demo video.
2. Plain one-post explanation.
3. GitHub link.
4. Install reply.
5. Latency reply ready.
6. No exaggerated claims.
7. Clear unofficial/OpenAI non-affiliation language.
