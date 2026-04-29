# Agent Notes

Keep this repo small, local-first, and dependency-light.

- Public promise: Codex Mission Control gives Codex a control room for your Mac.
- Main product: Mission Control hub and `cmc`.
- Extension: Mission Control Relay, the optional Telegram phone remote.
- Do not commit `.env`, bot tokens, runtime state, screenshots, private logs, or machine-local mission state.
- Do not add hosted services, accounts, sync backends, or speculative features.
- Prefer standard-library Python unless a dependency removes real complexity.
- Keep visuals as supporting product proof, not decoration. Generated visuals must come from the built-in ChatGPT image tool only, never an Image API script or API-key route.
- Do not claim this is an official OpenAI or Telegram project.
- After installer, CLI, dashboard, or Relay changes, run the closest relevant checks from `./scripts/qa.sh`, `./scripts/fresh_clone_test.sh`, `./scripts/doctor.sh`, and `./scripts/demo.sh`.
