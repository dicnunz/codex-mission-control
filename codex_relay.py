#!/usr/bin/env python3
"""Codex Relay: private Telegram control for local Codex on macOS."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
STATE_DIR_DEFAULT = ROOT / ".codex-relay-state"
TELEGRAM_LIMIT = 4096
DEFAULT_THREAD = "main"
SESSION_RE = re.compile(r"session id:\s*([0-9a-fA-F-]{36})")
THREAD_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,39}$")


def load_dotenv(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        os.environ[key] = value


def private_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def write_private_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(text)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        raise SystemExit(f"{name} must be an integer")


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def default_workdir() -> str:
    raw = os.environ.get("CODEX_TELEGRAM_WORKDIR", "").strip()
    return str(Path(raw or str(Path.home())).expanduser())


def parse_id_set(*names: str) -> set[int]:
    values: set[int] = set()
    for name in names:
        raw = os.environ.get(name, "")
        for chunk in raw.replace(",", " ").split():
            try:
                values.add(int(chunk))
            except ValueError:
                raise SystemExit(f"{name} contains a non-numeric id: {chunk!r}")
    return values


class TelegramAPI:
    def __init__(self, token: str) -> None:
        self.base = f"https://api.telegram.org/bot{token}/"

    def call(self, method: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        data = urllib.parse.urlencode(params or {}).encode()
        request = urllib.request.Request(self.base + method, data=data, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=70) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")[:600]
            raise RuntimeError(f"Telegram HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Telegram network error: {exc.reason}") from exc
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API error: {payload}")
        return payload

    def send_message(
        self, chat_id: int, text: str, reply_to_message_id: Optional[int] = None
    ) -> None:
        chunks = split_for_telegram(text)
        for chunk in chunks:
            params: dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": "true",
            }
            if reply_to_message_id is not None:
                params["reply_to_message_id"] = reply_to_message_id
            self.call("sendMessage", params)
            reply_to_message_id = None

    def send_chat_action(self, chat_id: int, action: str = "typing") -> None:
        self.call("sendChatAction", {"chat_id": chat_id, "action": action})

    def get_updates(self, offset: Optional[int]) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"timeout": 50, "allowed_updates": json.dumps(["message"])}
        if offset is not None:
            params["offset"] = offset
        return self.call("getUpdates", params).get("result", [])


def split_for_telegram(text: str) -> list[str]:
    if not text:
        return ["(empty response)"]
    limit = TELEGRAM_LIMIT - 200
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = remaining.rfind(" ", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


class TypingPulse:
    def __init__(self, api: TelegramAPI, chat_id: int) -> None:
        self.api = api
        self.chat_id = chat_id
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> "TypingPulse":
        self.thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.stop.set()
        self.thread.join(timeout=1)

    def _run(self) -> None:
        while not self.stop.is_set():
            try:
                self.api.send_chat_action(self.chat_id)
            except Exception:
                pass
            self.stop.wait(4)


def state_dir() -> Path:
    return private_dir(Path(os.environ.get("CODEX_TELEGRAM_STATE_DIR", STATE_DIR_DEFAULT)))


def read_offset(path: Path) -> Optional[int]:
    try:
        return int(path.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def read_threads(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"active_by_chat": {}, "threads_by_chat": {}}
    data.setdefault("active_by_chat", {})
    data.setdefault("threads_by_chat", {})
    return data


def write_threads(path: Path, data: dict[str, Any]) -> None:
    write_private_text(path, json.dumps(data, indent=2, sort_keys=True))


def chat_threads(data: dict[str, Any], chat_id: int) -> dict[str, dict[str, Any]]:
    chats = data.setdefault("threads_by_chat", {})
    return chats.setdefault(str(chat_id), {})


def active_thread_name(data: dict[str, Any], chat_id: int) -> str:
    return data.setdefault("active_by_chat", {}).get(str(chat_id), DEFAULT_THREAD)


def set_active_thread(data: dict[str, Any], chat_id: int, name: str) -> None:
    data.setdefault("active_by_chat", {})[str(chat_id)] = name


def normalize_thread_name(raw: str) -> str:
    name = raw.strip().lower().replace(" ", "-")
    if not name:
        raise ValueError("Give it a name, like `/new school`.")
    if not THREAD_RE.fullmatch(name):
        raise ValueError("Use 1-40 letters, numbers, dots, dashes, or underscores.")
    return name


def ensure_thread(data: dict[str, Any], chat_id: int, name: str) -> dict[str, Any]:
    threads = chat_threads(data, chat_id)
    thread = threads.get(name)
    if thread is None:
        thread = {
            "name": name,
            "session_id": "",
            "workdir": default_workdir(),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        threads[name] = thread
    thread.setdefault("workdir", default_workdir())
    return thread


def resolve_workdir(raw: str, current: str) -> Path:
    value = raw.strip()
    if not value:
        raise ValueError("Give me a folder, like `/cd Projects/my-repo`.")
    if value == ".":
        path = Path(current)
    elif value.startswith("/") or value.startswith("~"):
        path = Path(value).expanduser()
    else:
        path = Path.home() / value
    path = path.resolve()
    if not path.exists():
        raise ValueError(f"Folder does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"Not a folder: {path}")
    return path


def authorized(
    user_id: Optional[int],
    chat_id: int,
    allowed_users: set[int],
    allowed_chats: set[int],
) -> bool:
    if allowed_users and user_id in allowed_users:
        return True
    if allowed_chats and chat_id in allowed_chats:
        return True
    return False


def relay_user_name() -> str:
    return os.environ.get("CODEX_RELAY_USER_NAME", "the user").strip() or "the user"


def codex_prompt(message_text: str, thread_name: str) -> str:
    user_name = relay_user_name()
    return f"""You are Codex replying to {user_name} through a private Telegram bot.

Act like the Codex Mac app remote-controlled from {user_name}'s phone.
Use the live Mac state and the available Codex plugins/tools when useful, including Computer Use, Browser Use, apps/connectors, image generation, and subagents if the runtime exposes them.
{user_name} has explicitly allowed Atlas/browser/computer-use control for Telegram tasks. For browser tasks, prefer Atlas or Browser Use when appropriate.
Read live state first. Act directly. Keep replies terse and concrete.
Do not reveal secrets, tokens, auth files, private logs, session transcripts, or personal content.
If a requested action is blocked by credentials, permissions, network, macOS privacy, tool availability, or mandatory safety confirmation, state the exact blocker and the next human-only step.
This Telegram chat is mapped to the Codex thread named `{thread_name}`.

{user_name}:
{message_text}
"""


def base_codex_command(codex_path: str, model: str, approval: str, sandbox: str) -> list[str]:
    command = [
        codex_path,
        "exec",
        "-c",
        f'sandbox_mode="{sandbox}"',
        "-c",
        f'approval_policy="{approval}"',
    ]
    if model:
        command.extend(["--model", model])
    command.append("--skip-git-repo-check")
    return command


def extract_session_id(output: str) -> str:
    match = SESSION_RE.search(output)
    return match.group(1) if match else ""


def run_codex(message_text: str, thread: dict[str, Any]) -> tuple[str, str]:
    workdir = Path(str(thread.get("workdir") or default_workdir())).expanduser()
    if not workdir.exists():
        return (f"Blocked: CODEX_TELEGRAM_WORKDIR does not exist: {workdir}", "")

    codex_bin = os.environ.get("CODEX_BIN", "codex")
    codex_path = shutil.which(codex_bin)
    if codex_path is None:
        return (f"Blocked: could not find Codex CLI: {codex_bin}", "")

    sandbox = os.environ.get("CODEX_TELEGRAM_SANDBOX", "danger-full-access")
    model = os.environ.get("CODEX_TELEGRAM_MODEL", "gpt-5.5").strip()
    approval = os.environ.get("CODEX_TELEGRAM_APPROVAL", "never")
    timeout = env_int("CODEX_TELEGRAM_TIMEOUT_SECONDS", 240)
    thread_name = str(thread.get("name") or DEFAULT_THREAD)
    session_id = str(thread.get("session_id") or "")
    command = base_codex_command(codex_path, model, approval, sandbox)

    with tempfile.NamedTemporaryFile(prefix="codex-telegram-", delete=False) as handle:
        output_path = Path(handle.name)
    if session_id:
        command[1:2] = ["exec", "resume"]
        command.extend(["--output-last-message", str(output_path), session_id, "-"])
    else:
        command.extend(["--output-last-message", str(output_path), "-"])

    try:
        completed = subprocess.run(
            command,
            input=codex_prompt(message_text, thread_name),
            text=True,
            cwd=workdir,
            capture_output=True,
            timeout=timeout,
        )
        if output_path.exists():
            answer = output_path.read_text(errors="replace").strip()
        else:
            answer = ""
    except subprocess.TimeoutExpired:
        return (f"Blocked: Codex timed out after {timeout} seconds.", session_id)
    finally:
        try:
            output_path.unlink()
        except OSError:
            pass

    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()[:1200]
        if stderr:
            return (f"Codex failed with exit {completed.returncode}:\n{stderr}", session_id)
        return (f"Codex failed with exit {completed.returncode}.", session_id)

    combined_output = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
    new_session_id = extract_session_id(combined_output) or session_id
    return (answer or "(Codex returned an empty final message.)", new_session_id)


def command_help() -> str:
    return "\n".join(
        [
            "Commands:",
            "/ping - check the bridge",
            "/new name - start a fresh Codex thread",
            "/use name - switch threads",
            "/list - show threads",
            "/where - show current thread and folder",
            "/cd path - set this thread's folder",
            "/status - show runtime state",
            "/tools - probe Codex tool access",
            "/reset - restart the current thread",
            "",
            "Normal messages go to the active thread.",
        ]
    )


def status_text(thread: dict[str, Any]) -> str:
    session_status = "started" if thread.get("session_id") else "new"
    return "\n".join(
        [
            f"thread: {thread.get('name', DEFAULT_THREAD)} ({session_status})",
            f"folder: {thread.get('workdir', default_workdir())}",
            f"model: {os.environ.get('CODEX_TELEGRAM_MODEL', 'gpt-5.5')}",
            f"sandbox: {os.environ.get('CODEX_TELEGRAM_SANDBOX', 'danger-full-access')}",
            f"approval: {os.environ.get('CODEX_TELEGRAM_APPROVAL', 'never')}",
        ]
    )


def handle_message(
    api: TelegramAPI,
    message: dict[str, Any],
    allowed_users: set[int],
    allowed_chats: set[int],
    threads_path: Path,
) -> None:
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    chat_id = int(chat["id"])
    user_id = sender.get("id")
    if user_id is not None:
        user_id = int(user_id)
    message_id = message.get("message_id")
    text = (message.get("text") or "").strip()

    enrollment_mode = not allowed_users and not allowed_chats
    if enrollment_mode:
        api.send_message(
            chat_id,
            "Enrollment mode. I will not run Codex yet.\n"
            f"Telegram user ID: {user_id}\n"
            f"Telegram chat ID: {chat_id}\n\n"
            "Paste the user ID into TELEGRAM_ALLOWED_USER_ID in .env and restart me.",
            message_id,
        )
        return

    if not authorized(user_id, chat_id, allowed_users, allowed_chats):
        api.send_message(chat_id, "Not authorized.", message_id)
        return

    if not text:
        api.send_message(chat_id, "Send text for now.", message_id)
        return

    command, _, arg = text.partition(" ")
    command = command.lower()

    if command == "/ping":
        api.send_message(chat_id, "online", message_id)
        return
    if command == "/id":
        api.send_message(chat_id, f"Telegram user ID: {user_id}\nTelegram chat ID: {chat_id}", message_id)
        return
    if command in {"/help", "/start"}:
        api.send_message(chat_id, command_help(), message_id)
        return

    data = read_threads(threads_path)
    active_missing = str(chat_id) not in data.setdefault("active_by_chat", {})
    active_name = active_thread_name(data, chat_id)
    ensure_thread(data, chat_id, active_name)
    set_active_thread(data, chat_id, active_name)
    if active_missing:
        write_threads(threads_path, data)

    if command == "/new":
        try:
            name = normalize_thread_name(arg)
        except ValueError as exc:
            api.send_message(chat_id, str(exc), message_id)
            return
        thread = ensure_thread(data, chat_id, name)
        thread["session_id"] = ""
        thread["updated_at"] = now_iso()
        set_active_thread(data, chat_id, name)
        write_threads(threads_path, data)
        api.send_message(chat_id, f"New thread: {name}", message_id)
        return

    if command in {"/use", "/switch"}:
        try:
            name = normalize_thread_name(arg)
        except ValueError as exc:
            api.send_message(chat_id, str(exc), message_id)
            return
        threads = chat_threads(data, chat_id)
        if name not in threads:
            api.send_message(chat_id, f"No thread named `{name}`. Use `/new {name}`.", message_id)
            return
        set_active_thread(data, chat_id, name)
        write_threads(threads_path, data)
        api.send_message(chat_id, f"Using thread: {name}", message_id)
        return

    if command in {"/list", "/threads"}:
        threads = chat_threads(data, chat_id)
        names = sorted(threads) or [DEFAULT_THREAD]
        lines = []
        for name in names:
            marker = "*" if name == active_name else "-"
            thread = threads.get(name, {})
            started = "started" if thread.get("session_id") else "new"
            folder = Path(str(thread.get("workdir", default_workdir()))).name or str(thread.get("workdir"))
            lines.append(f"{marker} {name} ({started}) {folder}")
        api.send_message(chat_id, "\n".join(lines), message_id)
        return

    if command == "/where":
        thread = ensure_thread(data, chat_id, active_name)
        status = "started" if thread.get("session_id") else "new"
        api.send_message(chat_id, f"{active_name} ({status})\n{thread.get('workdir')}", message_id)
        return

    if command in {"/cd", "/repo"}:
        thread = ensure_thread(data, chat_id, active_name)
        try:
            path = resolve_workdir(arg, str(thread.get("workdir") or default_workdir()))
        except ValueError as exc:
            api.send_message(chat_id, str(exc), message_id)
            return
        thread["workdir"] = str(path)
        thread["updated_at"] = now_iso()
        write_threads(threads_path, data)
        api.send_message(chat_id, f"Folder set:\n{path}", message_id)
        return

    if command == "/home":
        thread = ensure_thread(data, chat_id, active_name)
        path = Path.home()
        thread["workdir"] = str(path)
        thread["updated_at"] = now_iso()
        write_threads(threads_path, data)
        api.send_message(chat_id, f"Folder set:\n{path}", message_id)
        return

    if command == "/status":
        thread = ensure_thread(data, chat_id, active_name)
        api.send_message(chat_id, status_text(thread), message_id)
        return

    if command == "/tools":
        probe = {
            "name": "tool-probe",
            "session_id": "",
            "workdir": default_workdir(),
        }
        with TypingPulse(api, chat_id):
            answer, _session_id = run_codex(
                "Use Computer Use to list running apps. Reply with a terse toolbelt status: Computer Use ok/not ok, Telegram running/not, ChatGPT Atlas running/not.",
                probe,
            )
        api.send_message(chat_id, answer, message_id)
        return

    if command == "/reset":
        thread = ensure_thread(data, chat_id, active_name)
        thread["session_id"] = ""
        thread["updated_at"] = now_iso()
        write_threads(threads_path, data)
        api.send_message(chat_id, f"Reset thread: {active_name}", message_id)
        return

    if text.startswith("/"):
        api.send_message(chat_id, "Unknown command. Use /help.", message_id)
        return

    api.send_chat_action(chat_id)
    thread = ensure_thread(data, chat_id, active_name)
    with TypingPulse(api, chat_id):
        answer, session_id = run_codex(text, thread)
    if session_id:
        thread["session_id"] = session_id
    thread["updated_at"] = now_iso()
    write_threads(threads_path, data)
    api.send_message(chat_id, answer, message_id)


def check_config() -> int:
    load_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    allowed_users = parse_id_set("TELEGRAM_ALLOWED_USER_ID", "TELEGRAM_ALLOWED_USER_IDS")
    allowed_chats = parse_id_set("TELEGRAM_ALLOWED_CHAT_ID", "TELEGRAM_ALLOWED_CHAT_IDS")
    workdir = Path(os.environ.get("CODEX_TELEGRAM_WORKDIR", str(ROOT))).expanduser()
    codex_bin = os.environ.get("CODEX_BIN", "codex")
    print(f"TELEGRAM_BOT_TOKEN={'set' if token else 'missing'}")
    print(f"allowed_user_ids={len(allowed_users)}")
    print(f"allowed_chat_ids={len(allowed_chats)}")
    print(f"workdir={workdir} exists={workdir.exists()}")
    print(f"codex={shutil.which(codex_bin) or 'missing'}")
    print(f"sandbox={os.environ.get('CODEX_TELEGRAM_SANDBOX', 'danger-full-access')}")
    print(f"model={os.environ.get('CODEX_TELEGRAM_MODEL', 'gpt-5.5')}")
    print(f"approval={os.environ.get('CODEX_TELEGRAM_APPROVAL', 'never')}")
    if not token:
        return 2
    if not workdir.exists() or shutil.which(codex_bin) is None:
        return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a private Telegram-to-Codex bridge.")
    parser.add_argument("--check-config", action="store_true", help="Validate config without polling Telegram.")
    args = parser.parse_args()

    load_dotenv()
    if args.check_config:
        return check_config()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("Missing TELEGRAM_BOT_TOKEN. Get one from @BotFather, put it in .env, then rerun.", file=sys.stderr)
        return 2

    allowed_users = parse_id_set("TELEGRAM_ALLOWED_USER_ID", "TELEGRAM_ALLOWED_USER_IDS")
    allowed_chats = parse_id_set("TELEGRAM_ALLOWED_CHAT_ID", "TELEGRAM_ALLOWED_CHAT_IDS")
    directory = state_dir()
    offset_path = directory / "offset"
    threads_path = directory / "threads.json"
    api = TelegramAPI(token)

    print("Codex Relay running.")
    if not allowed_users and not allowed_chats:
        print("Enrollment mode: messages will only return Telegram ids.")

    offset = read_offset(offset_path)
    while True:
        try:
            for update in api.get_updates(offset):
                update_id = int(update["update_id"])
                offset = update_id + 1
                write_private_text(offset_path, str(offset))
                message = update.get("message")
                if message:
                    handle_message(api, message, allowed_users, allowed_chats, threads_path)
        except KeyboardInterrupt:
            print("Stopping.")
            return 0
        except Exception as exc:
            print(f"Bridge error: {exc}", file=sys.stderr)
            time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())
