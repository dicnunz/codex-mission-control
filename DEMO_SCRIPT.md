# Demo Script

Goal: show Codex Relay as a real phone remote for a Mac, not a chatbot gimmick.

The hook is:

```text
I left my Mac open on my desk and controlled Codex from bed.
```

## Shot List

1. Mac open on desk, Codex signed in.
2. Phone opens Telegram bot.
3. Send `/status`.
4. Send `/tools`.
5. Send:

```text
/new demo
/cd Documents
tell me the three most recent files here and what they look like they are for
```

6. Show the Mac doing local work and Telegram getting the answer.
7. End on the README install command.

## 30-Second Voiceover

```text
I wanted Codex on my phone, but not as a watered-down chatbot.

So I made Codex Relay.

My Mac stays open at home. I text this Telegram bot. It runs the real Codex CLI locally with gpt-5.5, my files, my repos, and Computer Use.

Here I ask for the tool check. It sees Telegram and Atlas. Then I switch threads and ask it to work in a folder.

There is no hosted middleman. It is just Telegram to a LaunchAgent to Codex on my Mac.
```

## Caption

I made Codex Relay: a private Telegram remote for Codex on your Mac.

Leave the laptop open. Text your bot. Codex runs locally with your files, repos, apps, plugins, and Computer Use.

No hosted middleman. No fake agent shell. Just Telegram -> Codex CLI -> your Mac.

## Pinned Reply

```text
GitHub: https://github.com/dicnunz/codex-relay

Install:
git clone https://github.com/dicnunz/codex-relay.git
cd codex-relay
./scripts/install.sh
```
