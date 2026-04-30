#!/usr/bin/env python3
"""Interactive Mission Control Relay setup."""

from __future__ import annotations

import json
import getpass
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def private_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(text)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    return values


def save_env(values: dict[str, str]) -> None:
    ordered = [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_ALLOWED_USER_ID",
        "TELEGRAM_ALLOWED_CHAT_ID",
        "CODEX_RELAY_USER_NAME",
        "CODEX_RELAY_ASSISTANT_NAME",
        "CODEX_RELAY_ASSISTANT_PERSONALITY",
        "CODEX_MISSION_CONTROL_HOME",
        "CODEX_TELEGRAM_WORKDIR",
        "CODEX_BIN",
        "CODEX_TELEGRAM_SANDBOX",
        "CODEX_TELEGRAM_MODEL",
        "CODEX_TELEGRAM_REASONING_EFFORT",
        "CODEX_TELEGRAM_SPEED",
        "CODEX_TELEGRAM_REPLY_STYLE",
        "CODEX_TELEGRAM_APPROVAL",
        "CODEX_TELEGRAM_TIMEOUT_SECONDS",
        "CODEX_TELEGRAM_REPLY_TO_MESSAGES",
        "CODEX_TELEGRAM_REPLY_UNAUTHORIZED",
        "CODEX_TELEGRAM_ALLOW_GROUP_CHATS",
        "CODEX_TELEGRAM_TYPING_INTERVAL_SECONDS",
        "CODEX_TELEGRAM_MAX_IMAGE_BYTES",
        "CODEX_TELEGRAM_IMAGE_RETENTION_DAYS",
    ]
    lines = ["# Codex Mission Control private config. Do not commit this file."]
    for key in ordered:
        if key in values:
            lines.append(f"{key}={values[key]}")
    for key in sorted(set(values) - set(ordered)):
        lines.append(f"{key}={values[key]}")
    private_write(ENV_PATH, "\n".join(lines) + "\n")


def telegram_call(token: str, method: str, params: Optional[dict[str, str]] = None) -> dict:
    data = urllib.parse.urlencode(params or {}).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=data,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError:
        raise
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Telegram request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("Telegram request timed out") from exc
    if not payload.get("ok"):
        raise RuntimeError(str(payload))
    return payload


def detect_codex() -> str:
    candidates = [
        "/Applications/Codex.app/Contents/Resources/codex",
        shutil.which("codex") or "",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists() and os.access(candidate, os.X_OK):
            return candidate
    raise SystemExit("Could not find Codex. Install/open the Codex Mac app first.")


def prompt_token(existing: str) -> str:
    if existing:
        return existing
    print("Create a Telegram bot with @BotFather, then paste its token here.")
    token = getpass.getpass("Bot token: ").strip()
    if not token:
        raise SystemExit("No token provided.")
    return token


def latest_update_offset(token: str) -> Optional[int]:
    updates = telegram_call(
        token,
        "getUpdates",
        {"timeout": "0", "allowed_updates": json.dumps(["message"])},
    ).get("result", [])
    update_ids = [int(update["update_id"]) for update in updates if "update_id" in update]
    if not update_ids:
        return None
    return max(update_ids) + 1


def enrollment_match(update: dict, nonce: str) -> Optional[tuple[str, str]]:
    message = update.get("message") or {}
    text = str(message.get("text") or "").strip()
    sender = message.get("from") or {}
    chat = message.get("chat") or {}
    if chat.get("type") != "private" or not sender.get("id"):
        return None
    if text != f"/start {nonce}":
        return None
    return str(sender["id"]), str(chat.get("id") or sender["id"])


def wait_for_start(
    token: str,
    username: str,
    existing_user: str,
    existing_chat: str = "",
) -> tuple[str, str]:
    if existing_user:
        return existing_user, existing_chat or existing_user
    nonce = "codex-" + secrets.token_hex(3)
    deep_link = f"https://t.me/{username}?start={nonce}" if username else ""
    try:
        offset = latest_update_offset(token)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Telegram rejected the token: HTTP {exc.code}") from exc
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print("Authorize only your private Telegram DM.")
    if deep_link:
        print(f"Open {deep_link}")
    print(f"Send exactly: /start {nonce}")
    print("Waiting up to 90 seconds...")
    deadline = time.time() + 90
    while time.time() < deadline:
        params = {"timeout": "5", "allowed_updates": json.dumps(["message"])}
        if offset is not None:
            params["offset"] = str(offset)
        try:
            updates = telegram_call(token, "getUpdates", params).get("result", [])
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"Telegram rejected the token: HTTP {exc.code}") from exc
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc
        for update in updates:
            offset = int(update["update_id"]) + 1
            match = enrollment_match(update, nonce)
            if match:
                return match
        time.sleep(1)
    raise SystemExit("Timed out waiting for the exact /start code. Run scripts/configure.py again.")


def main() -> int:
    values = load_env()
    codex_bin = values.get("CODEX_BIN") or detect_codex()
    token = prompt_token(values.get("TELEGRAM_BOT_TOKEN", ""))
    try:
        bot = telegram_call(token, "getMe")["result"]
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Telegram rejected the token: HTTP {exc.code}") from exc
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    username = bot.get("username") or ""
    user_id, chat_id = wait_for_start(
        token,
        username,
        values.get("TELEGRAM_ALLOWED_USER_ID", ""),
        values.get("TELEGRAM_ALLOWED_CHAT_ID", ""),
    )
    values.update(
        {
            "TELEGRAM_BOT_TOKEN": token,
            "TELEGRAM_ALLOWED_USER_ID": user_id,
            "TELEGRAM_ALLOWED_CHAT_ID": chat_id,
            "CODEX_MISSION_CONTROL_HOME": values.get("CODEX_MISSION_CONTROL_HOME") or str(Path.home() / "Codex Mission Control"),
            "CODEX_TELEGRAM_WORKDIR": values.get("CODEX_TELEGRAM_WORKDIR") or str(Path.home()),
            "CODEX_RELAY_ASSISTANT_NAME": values.get("CODEX_RELAY_ASSISTANT_NAME") or "Codex",
            "CODEX_RELAY_ASSISTANT_PERSONALITY": values.get("CODEX_RELAY_ASSISTANT_PERSONALITY") or "",
            "CODEX_BIN": codex_bin,
            "CODEX_TELEGRAM_SANDBOX": values.get("CODEX_TELEGRAM_SANDBOX") or "danger-full-access",
            "CODEX_TELEGRAM_MODEL": values.get("CODEX_TELEGRAM_MODEL") or "",
            "CODEX_TELEGRAM_REASONING_EFFORT": values.get("CODEX_TELEGRAM_REASONING_EFFORT") or "high",
            "CODEX_TELEGRAM_SPEED": values.get("CODEX_TELEGRAM_SPEED") or "standard",
            "CODEX_TELEGRAM_REPLY_STYLE": values.get("CODEX_TELEGRAM_REPLY_STYLE") or "brief",
            "CODEX_TELEGRAM_APPROVAL": values.get("CODEX_TELEGRAM_APPROVAL") or "never",
            "CODEX_TELEGRAM_TIMEOUT_SECONDS": values.get("CODEX_TELEGRAM_TIMEOUT_SECONDS") or "600",
            "CODEX_TELEGRAM_REPLY_TO_MESSAGES": values.get("CODEX_TELEGRAM_REPLY_TO_MESSAGES") or "false",
            "CODEX_TELEGRAM_REPLY_UNAUTHORIZED": values.get("CODEX_TELEGRAM_REPLY_UNAUTHORIZED") or "false",
            "CODEX_TELEGRAM_ALLOW_GROUP_CHATS": values.get("CODEX_TELEGRAM_ALLOW_GROUP_CHATS") or "false",
            "CODEX_TELEGRAM_TYPING_INTERVAL_SECONDS": values.get("CODEX_TELEGRAM_TYPING_INTERVAL_SECONDS") or "4",
            "CODEX_TELEGRAM_MAX_IMAGE_BYTES": values.get("CODEX_TELEGRAM_MAX_IMAGE_BYTES") or "20971520",
            "CODEX_TELEGRAM_IMAGE_RETENTION_DAYS": values.get("CODEX_TELEGRAM_IMAGE_RETENTION_DAYS") or "7",
        }
    )
    save_env(values)
    subprocess.run([str(ROOT / "scripts/install_launch_agent.sh")], check=True)
    print()
    print(f"Mission Control Relay is running. DM @{username} /mission status to verify.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
