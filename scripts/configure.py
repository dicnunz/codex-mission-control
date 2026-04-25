#!/usr/bin/env python3
"""Interactive Codex Relay setup."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


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
        "CODEX_TELEGRAM_WORKDIR",
        "CODEX_BIN",
        "CODEX_TELEGRAM_SANDBOX",
        "CODEX_TELEGRAM_MODEL",
        "CODEX_TELEGRAM_APPROVAL",
        "CODEX_TELEGRAM_TIMEOUT_SECONDS",
        "CODEX_TELEGRAM_MAX_IMAGE_BYTES",
        "CODEX_TELEGRAM_IMAGE_RETENTION_DAYS",
    ]
    lines = ["# Codex Relay private config. Do not commit this file."]
    for key in ordered:
        if key in values:
            lines.append(f"{key}={values[key]}")
    for key in sorted(set(values) - set(ordered)):
        lines.append(f"{key}={values[key]}")
    private_write(ENV_PATH, "\n".join(lines) + "\n")


def telegram_call(token: str, method: str, params: dict[str, str] | None = None) -> dict:
    data = urllib.parse.urlencode(params or {}).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=data,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode())
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
    token = input("Bot token: ").strip()
    if not token:
        raise SystemExit("No token provided.")
    return token


def wait_for_start(token: str, username: str, existing_user: str) -> tuple[str, str]:
    if existing_user:
        return existing_user, existing_user
    print(f"Open https://t.me/{username} and send /start.")
    print("Waiting up to 90 seconds...")
    deadline = time.time() + 90
    offset = None
    while time.time() < deadline:
        params = {"timeout": "5", "allowed_updates": json.dumps(["message"])}
        if offset is not None:
            params["offset"] = str(offset)
        try:
            updates = telegram_call(token, "getUpdates", params).get("result", [])
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"Telegram rejected the token: HTTP {exc.code}") from exc
        for update in updates:
            offset = int(update["update_id"]) + 1
            message = update.get("message") or {}
            sender = message.get("from") or {}
            chat = message.get("chat") or {}
            if chat.get("type") == "private" and sender.get("id"):
                return str(sender["id"]), str(chat.get("id") or sender["id"])
        time.sleep(1)
    raise SystemExit("Timed out waiting for /start. Run scripts/configure.py again.")


def main() -> int:
    values = load_env()
    codex_bin = values.get("CODEX_BIN") or detect_codex()
    token = prompt_token(values.get("TELEGRAM_BOT_TOKEN", ""))
    try:
        bot = telegram_call(token, "getMe")["result"]
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Telegram rejected the token: HTTP {exc.code}") from exc
    username = bot.get("username") or ""
    user_id, chat_id = wait_for_start(token, username, values.get("TELEGRAM_ALLOWED_USER_ID", ""))
    values.update(
        {
            "TELEGRAM_BOT_TOKEN": token,
            "TELEGRAM_ALLOWED_USER_ID": user_id,
            "TELEGRAM_ALLOWED_CHAT_ID": chat_id,
            "CODEX_TELEGRAM_WORKDIR": values.get("CODEX_TELEGRAM_WORKDIR") or str(Path.home()),
            "CODEX_BIN": codex_bin,
            "CODEX_TELEGRAM_SANDBOX": values.get("CODEX_TELEGRAM_SANDBOX") or "danger-full-access",
            "CODEX_TELEGRAM_MODEL": values.get("CODEX_TELEGRAM_MODEL") or "gpt-5.5",
            "CODEX_TELEGRAM_APPROVAL": values.get("CODEX_TELEGRAM_APPROVAL") or "never",
            "CODEX_TELEGRAM_TIMEOUT_SECONDS": values.get("CODEX_TELEGRAM_TIMEOUT_SECONDS") or "600",
            "CODEX_TELEGRAM_MAX_IMAGE_BYTES": values.get("CODEX_TELEGRAM_MAX_IMAGE_BYTES") or "20971520",
            "CODEX_TELEGRAM_IMAGE_RETENTION_DAYS": values.get("CODEX_TELEGRAM_IMAGE_RETENTION_DAYS") or "7",
        }
    )
    save_env(values)
    subprocess.run([str(ROOT / "scripts/install_launch_agent.sh")], check=True)
    print()
    print(f"Codex Relay is running. DM @{username} /tools to verify.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
