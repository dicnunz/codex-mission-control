# Codex Sessions

[![ci](https://github.com/dicnunz/codex-sessions/actions/workflows/ci.yml/badge.svg)](https://github.com/dicnunz/codex-sessions/actions/workflows/ci.yml)

Coordinate local Codex sessions with project discovery, cooperative filesystem locks, and an optional Telegram remote.

[Example dashboard](https://dicnunz.github.io/demos/mission-control/) (synthetic data) · [44-second demo](assets/codex-mission-control-demo.mp4)

## Install

Requires macOS, the Codex Mac app installed and signed in, and `python3`.

```sh
git clone https://github.com/dicnunz/codex-sessions.git
cd codex-sessions
./scripts/install.sh
```

The installer creates `~/Codex Mission Control`, indexes projects with symlinks, and links `cmc` into `~/.local/bin` when possible. Project folders stay in place. Use `./cmc` from the checkout if `~/.local/bin` is outside your `PATH`.

```sh
cmc status
cmc lanes
cmc dashboard
```

To try the coordination loop without installing or configuring Telegram, run `./scripts/demo.sh` from the checkout. See [INSTALL.md](INSTALL.md) for setup, runtime paths, and Relay removal.

## Use

`cmc discover` searches `~/Developer`, `~/Projects`, `~/Documents/Codex`, and the current directory. To select a root:

```sh
cmc discover /path/to/project
cmc discover --include-defaults /extra/root
```

Each discovered project has a mission entry and an outbox in the hub. `cmc merge` collects the outboxes. `cmc packet --help` lists the fields for an approval packet.

Project instructions are opt-in: `cmc adopt` previews the `AGENTS.md` additions; `cmc adopt --write` applies them and backs up existing files. The installer skips adoption unless you choose to write or set `CMC_ADOPT_AGENTS=yes`.

### Shared resources

Sessions claim lanes before using shared resources such as the browser, email, or GitHub:

```sh
cmc claim BROWSER SESSION_A "using the browser"
cmc claim BROWSER SESSION_B "using the browser"
# held: BROWSER
cmc release BROWSER SESSION_A
```

Claims and releases are serialized per lane. The default lease is 1,800 seconds; `--ttl 0` holds it until its owner releases it. Reclamation uses the existing owner's timeout.

Use a unique owner per session. Check that previous work has stopped before reclaiming an expired lease: expiry cannot stop a running session. Locks require cooperation from every session and grant no permissions. Use the same updated CLI on a local macOS or Linux filesystem; network filesystems and mixed CLI versions are unsupported.

### Dashboard

`cmc dashboard` writes and opens `<hub>/_ops/dashboard.html`, a private snapshot of missions, claims, and outboxes. Run the command again to refresh its data.

To generate a snapshot for another hub without opening it:

```sh
cmc --hub /path/to/hub dashboard --no-open
```

### Telegram

With a bot token from `@BotFather`, install the optional Mission Control Relay:

```sh
./cmc relay install
```

Send `/mission status`, `/mission lanes`, or `/mission projects` to inspect the hub; `/tools` lists available commands. Messages and image captions go to local Codex through your Mac. Access is restricted to the configured Telegram user/chat allowlist. Keep the bot token private.

Relay requires the Mac to run. It preserves login, MFA, usage-limit, and confirmation requirements.

## Development

```sh
./scripts/qa.sh
```

QA runs syntax checks, unit tests, coordination tests, the demo, and a fresh-clone check. The core CLI, dashboard, and lane tests support Linux; the installer, LaunchAgent, menu bar, and `scripts/doctor.sh` require macOS. QA reports platform skips on Linux.

Update with `./scripts/update.sh`. For installation failures, see the [feedback guide](docs/INSTALL_FEEDBACK.md).

Unofficial project, unaffiliated with OpenAI or Telegram.
