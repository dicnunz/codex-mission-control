#!/usr/bin/env python3
"""Codex Relay: private Telegram control for local Codex on macOS."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pty
import re
import signal
import select
import shlex
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable, Optional


ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
STATE_DIR_DEFAULT = ROOT / ".codex-relay-state"
TELEGRAM_LIMIT = 4096
DEFAULT_THREAD = "main"
TOOL_PROBE_THREAD = "tool-probe"
DEFAULT_TIMEOUT_SECONDS = 600
DEFAULT_TELEGRAM_POLL_TIMEOUT_SECONDS = 25
DEFAULT_TELEGRAM_POLL_HTTP_TIMEOUT_SECONDS = 60
DEFAULT_MAX_IMAGE_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_FILE_BYTES = 20 * 1024 * 1024
DEFAULT_IMAGE_RETENTION_DAYS = 7
DEFAULT_MEDIA_GROUP_GRACE_SECONDS = 1.2
DEFAULT_TERMINAL_READ_LIMIT = 4000
MAX_IMAGES_PER_MESSAGE = 10
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
DEFAULT_GEMINI_TIMEOUT_SECONDS = 20
DEFAULT_GEMINI_MAX_OUTPUT_TOKENS = 4096
DEFAULT_PROGRESS_INTERVAL_SECONDS = 20
MAX_PROGRESS_LINES = 6
MAX_PENDING_REQUESTS = 8
MAX_PENDING_PROMPT_CHARS = 6000
DEFAULT_REASONING_EFFORT = "xhigh"
REASONING_EFFORTS = {"low", "medium", "high", "xhigh"}
THINKING_MODE_ALIASES = {
    "default": "default",
    "env": "default",
    "fast": "low",
    "low": "low",
    "medium": "medium",
    "normal": "medium",
    "standard": "medium",
    "high": "high",
    "deep": "high",
    "x-high": "xhigh",
    "xhigh": "xhigh",
    "extra": "xhigh",
    "extra-high": "xhigh",
    "max": "xhigh",
    "maximum": "xhigh",
}
DEFAULT_REPLY_STYLE = "normal"
REPLY_STYLES = {"brief", "normal", "verbose"}
SESSION_RE = re.compile(r"session id:\s*([0-9a-fA-F-]{36})", re.IGNORECASE)
THREAD_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,39}$")
GEMINI_ACTIONS = {
    "none",
    "queue_request",
    "remove_pending_request",
    "remove_pending_images",
    "replace_pending_request",
    "prioritize_pending_request",
    "set_thinking_mode",
    "set_workdir",
    "new_thread",
    "use_thread",
    "reset_thread",
    "run_codex",
    "show_activity",
    "show_status",
    "show_queue",
    "show_help",
    "terminal_open",
    "terminal_read",
    "terminal_send",
    "terminal_kill",
    "send_file",
}
GEMINI_SENSITIVE_TERMS = {
    ".env",
    "api key",
    "apikey",
    "authorization:",
    "bearer ",
    "gemini_api_key",
    "openai_api_key",
    "password",
    "private key",
    "secret",
    "ssh key",
    "telegram_bot_token",
    "token",
    "x-goog-api-key",
}
GEMINI_SECRET_VALUE_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{20,}|[0-9]{8,10}:[A-Za-z0-9_-]{30,})"
)
GEMINI_API_KEY_RE = re.compile(r"\b(AIza[0-9A-Za-z_-]{20,})\b")
STARTED_AT = time.time()
THREADS_LOCK = threading.Lock()
SHUTDOWN_EVENT = threading.Event()
WORKERS_LOCK = threading.Lock()
WORKERS: list[threading.Thread] = []
TERMINALS_LOCK = threading.Lock()
TERMINALS: dict[str, "TerminalSession"] = {}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif"}
IMAGE_SUFFIX_BY_MIME = {
    "image/gif": ".gif",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
CA_FILE_KEYS = ("CODEX_RELAY_CA_FILE", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE")
COMMON_CA_FILES = (
    "/etc/ssl/cert.pem",
    "/opt/homebrew/etc/openssl@3/cert.pem",
    "/opt/homebrew/etc/ca-certificates/cert.pem",
    "/usr/local/etc/openssl@3/cert.pem",
    "/usr/local/etc/ca-certificates/cert.pem",
)


class TelegramTLSCertificateError(RuntimeError):
    """Raised when Python cannot verify Telegram's HTTPS certificate."""


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


def write_private_bytes(path: Path, content: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(content)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def update_private_env_file(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text().splitlines() if path.exists() else [
        "# Codex Relay private config. Do not commit this file."
    ]
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            out.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")
    write_private_text(path, "\n".join(out).rstrip() + "\n")


def read_private_bytes(path: Path) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        raise SystemExit(f"{name} must be an integer")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise SystemExit(f"{name} must be true or false")


def env_choice(name: str, default: str, allowed: set[str]) -> str:
    value = os.environ.get(name, "").strip().lower() or default
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise SystemExit(f"{name} must be one of: {choices}")
    return value


def normalize_thinking_mode(raw: str, allow_default: bool = False) -> str:
    value = raw.strip().lower().replace("_", "-")
    mode = THINKING_MODE_ALIASES.get(value, value)
    if allow_default and mode == "default":
        return mode
    if mode in REASONING_EFFORTS:
        return mode
    choices = ", ".join(sorted(REASONING_EFFORTS))
    if allow_default:
        choices += ", default"
    raise ValueError(f"Thinking mode must be one of: {choices}")


def thinking_mode_default() -> str:
    raw = (
        os.environ.get("CODEX_TELEGRAM_THINKING_MODE", "").strip()
        or os.environ.get("CODEX_TELEGRAM_REASONING_EFFORT", "").strip()
        or DEFAULT_REASONING_EFFORT
    )
    try:
        return normalize_thinking_mode(raw)
    except ValueError:
        raise SystemExit("CODEX_TELEGRAM_THINKING_MODE must be one of: low, medium, high, xhigh")


def thread_thinking_mode(thread: dict[str, Any]) -> str:
    raw = str(thread.get("thinking_mode") or thread.get("reasoning_effort") or "").strip()
    if not raw:
        return thinking_mode_default()
    try:
        return normalize_thinking_mode(raw)
    except ValueError:
        return thinking_mode_default()


def thinking_mode_source(thread: dict[str, Any]) -> str:
    return "thread" if str(thread.get("thinking_mode") or thread.get("reasoning_effort") or "").strip() else "config"


def thinking_mode_status(thread: dict[str, Any]) -> str:
    return f"{thread_thinking_mode(thread)} ({thinking_mode_source(thread)})"


def set_thinking_mode_text(thread: dict[str, Any], raw: str) -> str:
    mode = normalize_thinking_mode(raw, allow_default=True)
    if mode == "default":
        thread.pop("thinking_mode", None)
        thread.pop("reasoning_effort", None)
        thread["updated_at"] = now_iso()
        return f"Thinking mode: {thinking_mode_default()} (config default)"
    thread["thinking_mode"] = mode
    thread.pop("reasoning_effort", None)
    thread["updated_at"] = now_iso()
    return f"Thinking mode: {mode}"


def thinking_mode_help_text(thread: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Thinking mode: {thinking_mode_status(thread)}",
            "Use: /think low|medium|high|xhigh|default",
            "Applies to the next Codex job in this thread.",
        ]
    )


def reply_style_default() -> str:
    return env_choice("CODEX_TELEGRAM_REPLY_STYLE", DEFAULT_REPLY_STYLE, REPLY_STYLES)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def duration_text(seconds: float) -> str:
    seconds = max(0, int(seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts[:2])


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


def candidate_ca_files() -> list[Path]:
    candidates: list[str] = []
    for key in CA_FILE_KEYS:
        value = os.environ.get(key, "").strip()
        if value:
            candidates.append(value)

    paths = ssl.get_default_verify_paths()
    candidates.extend([paths.cafile or "", paths.openssl_cafile or ""])

    try:
        import certifi  # type: ignore[import-not-found]

        candidates.append(certifi.where())
    except Exception:
        pass

    candidates.extend(COMMON_CA_FILES)

    seen: set[Path] = set()
    usable: list[Path] = []
    for raw in candidates:
        if not raw:
            continue
        path = Path(raw).expanduser()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        usable.append(path)
    return usable


def is_certificate_error(exc: BaseException) -> bool:
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, ssl.SSLError):
        return True
    return "CERTIFICATE_VERIFY_FAILED" in str(reason)


def python_org_certificate_command() -> str:
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    command = Path(f"/Applications/Python {version}/Install Certificates.command")
    if command.exists():
        return f'open "{command}"'
    return 'open "/Applications/Python 3.x/Install Certificates.command"'


def certificate_error_message(exc: BaseException, tried: list[Path]) -> str:
    tried_text = ", ".join(str(path) for path in tried) or "none found"
    return (
        "Could not verify Telegram's HTTPS certificate.\n"
        f"Original error: {getattr(exc, 'reason', exc)}\n"
        f"Tried CA bundles: {tried_text}\n\n"
        "Fix one of these, then rerun ./scripts/install.sh:\n"
        f"- python.org macOS Python: run {python_org_certificate_command()}\n"
        "- Homebrew/system Python: make sure /etc/ssl/cert.pem or Homebrew ca-certificates exists.\n"
        "- Corporate or security proxy: set CODEX_RELAY_CA_FILE=/path/to/your-ca.pem in .env.\n\n"
        "Do not bypass TLS verification for a bot token."
    )


def telegram_timeout_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "timed out" in text or "timeout" in text or "read operation timed out" in text


def telegram_urlopen(request: urllib.request.Request, timeout: int):
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.URLError as exc:
        if not is_certificate_error(exc):
            raise
        first_error: BaseException = exc

    tried: list[Path] = []
    for ca_file in candidate_ca_files():
        tried.append(ca_file)
        try:
            context = ssl.create_default_context(cafile=str(ca_file))
            return urllib.request.urlopen(request, timeout=timeout, context=context)
        except urllib.error.URLError as exc:
            if not is_certificate_error(exc):
                raise
            first_error = exc
        except ssl.SSLError as exc:
            first_error = exc

    raise TelegramTLSCertificateError(certificate_error_message(first_error, tried)) from first_error


class TelegramAPI:
    def __init__(self, token: str) -> None:
        self.token = token
        self.base = f"https://api.telegram.org/bot{token}/"

    def call(
        self,
        method: str,
        params: Optional[dict[str, Any]] = None,
        timeout: int = 70,
    ) -> dict[str, Any]:
        data = urllib.parse.urlencode(params or {}).encode()
        request = urllib.request.Request(self.base + method, data=data, method="POST")
        try:
            with telegram_urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")[:600]
            raise RuntimeError(f"Telegram HTTP {exc.code}: {body}") from exc
        except TelegramTLSCertificateError as exc:
            raise RuntimeError(str(exc)) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Telegram network error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError(f"Telegram request timed out: {exc}") from exc
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API error: {payload}")
        return payload

    def send_message(
        self, chat_id: int, text: str, reply_to_message_id: Optional[int] = None
    ) -> Optional[int]:
        chunks = split_for_telegram(text)
        threaded_replies = env_bool("CODEX_TELEGRAM_REPLY_TO_MESSAGES", False)
        first_message_id: Optional[int] = None
        for chunk in chunks:
            params: dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": "true",
            }
            if threaded_replies and reply_to_message_id is not None:
                params["reply_to_message_id"] = reply_to_message_id
            payload = self.call("sendMessage", params)
            message_id = int_or_none((payload.get("result") or {}).get("message_id"))
            if first_message_id is None:
                first_message_id = message_id
            reply_to_message_id = None
        return first_message_id

    def edit_message(self, chat_id: int, message_id: int, text: str) -> None:
        chunk = split_for_telegram(text)[0]
        self.call(
            "editMessageText",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": chunk,
                "disable_web_page_preview": "true",
            },
        )

    def send_chat_action(self, chat_id: int, action: str = "typing") -> None:
        self.call("sendChatAction", {"chat_id": chat_id, "action": action})

    def delete_message(self, chat_id: int, message_id: int) -> None:
        self.call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

    def send_photo(
        self,
        chat_id: int,
        path: Path,
        caption: str = "",
        reply_to_message_id: Optional[int] = None,
    ) -> None:
        boundary = "codexrelay-" + uuid.uuid4().hex
        fields: dict[str, str] = {
            "chat_id": str(chat_id),
        }
        if caption:
            fields["caption"] = caption
        if env_bool("CODEX_TELEGRAM_REPLY_TO_MESSAGES", False) and reply_to_message_id is not None:
            fields["reply_to_message_id"] = str(reply_to_message_id)

        body = bytearray()
        for key, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
            body.extend(value.encode())
            body.extend(b"\r\n")
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="photo"; filename="{path.name}"\r\n'.encode()
        )
        body.extend(b"Content-Type: image/jpeg\r\n\r\n")
        body.extend(read_private_bytes(path))
        body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode())

        request = urllib.request.Request(
            self.base + "sendPhoto",
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        try:
            with telegram_urlopen(request, timeout=70) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode(errors="replace")[:600]
            raise RuntimeError(f"Telegram HTTP {exc.code}: {body_text}") from exc
        except TelegramTLSCertificateError as exc:
            raise RuntimeError(str(exc)) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Telegram network error: {exc.reason}") from exc
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API error: {payload}")

    def send_document(
        self,
        chat_id: int,
        path: Path,
        caption: str = "",
        reply_to_message_id: Optional[int] = None,
    ) -> None:
        boundary = "codexrelay-" + uuid.uuid4().hex
        fields: dict[str, str] = {
            "chat_id": str(chat_id),
        }
        if caption:
            fields["caption"] = caption
        if env_bool("CODEX_TELEGRAM_REPLY_TO_MESSAGES", False) and reply_to_message_id is not None:
            fields["reply_to_message_id"] = str(reply_to_message_id)

        body = bytearray()
        for key, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
            body.extend(value.encode())
            body.extend(b"\r\n")
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="document"; filename="{path.name}"\r\n'.encode()
        )
        body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
        with open(path, "rb") as handle:
            body.extend(handle.read())
        body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode())

        request = urllib.request.Request(
            self.base + "sendDocument",
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        try:
            with telegram_urlopen(request, timeout=70) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode(errors="replace")[:600]
            raise RuntimeError(f"Telegram HTTP {exc.code}: {body_text}") from exc
        except TelegramTLSCertificateError as exc:
            raise RuntimeError(str(exc)) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Telegram network error: {exc.reason}") from exc
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API error: {payload}")

    def get_updates(self, offset: Optional[int]) -> list[dict[str, Any]]:
        poll_timeout = max(1, env_int("CODEX_TELEGRAM_POLL_TIMEOUT_SECONDS", DEFAULT_TELEGRAM_POLL_TIMEOUT_SECONDS))
        http_timeout = max(
            poll_timeout + 10,
            env_int("CODEX_TELEGRAM_POLL_HTTP_TIMEOUT_SECONDS", DEFAULT_TELEGRAM_POLL_HTTP_TIMEOUT_SECONDS),
        )
        params: dict[str, Any] = {"timeout": poll_timeout, "allowed_updates": json.dumps(["message"])}
        if offset is not None:
            params["offset"] = offset
        try:
            return self.call("getUpdates", params, timeout=http_timeout).get("result", [])
        except RuntimeError as exc:
            if telegram_timeout_error(exc):
                return []
            raise

    def get_file(self, file_id: str) -> dict[str, Any]:
        return self.call("getFile", {"file_id": file_id}).get("result", {})

    def download_file(self, file_path: str, max_bytes: Optional[int] = None) -> bytes:
        quoted_path = urllib.parse.quote(file_path, safe="/")
        request = urllib.request.Request(
            f"https://api.telegram.org/file/bot{self.token}/{quoted_path}",
            method="GET",
        )
        try:
            with telegram_urlopen(request, timeout=70) as response:
                announced = response.headers.get("Content-Length")
                if max_bytes is not None and announced:
                    try:
                        if int(announced) > max_bytes:
                            raise RuntimeError(
                                f"Telegram file is too large ({announced} bytes; limit {max_bytes})"
                            )
                    except ValueError:
                        pass
                chunks = bytearray()
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    chunks.extend(chunk)
                    if max_bytes is not None and len(chunks) > max_bytes:
                        raise RuntimeError(
                            f"Telegram file is too large ({len(chunks)} bytes; limit {max_bytes})"
                        )
                return bytes(chunks)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")[:600]
            raise RuntimeError(f"Telegram file download HTTP {exc.code}: {body}") from exc
        except TelegramTLSCertificateError as exc:
            raise RuntimeError(str(exc)) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Telegram file download error: {exc.reason}") from exc


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
    def __init__(self, api: TelegramAPI, chat_id: int, action: str = "typing") -> None:
        self.api = api
        self.chat_id = chat_id
        self.action = action
        self.interval = max(1, env_int("CODEX_TELEGRAM_TYPING_INTERVAL_SECONDS", 4))
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
                self.api.send_chat_action(self.chat_id, self.action)
            except Exception:
                pass
            self.stop.wait(self.interval)


class RelayJob:
    def __init__(self, chat_id: int, thread_name: str, image_count: int, request_text: str = "") -> None:
        self.id = uuid.uuid4().hex[:8]
        self.chat_id = chat_id
        self.thread_name = thread_name
        self.image_count = image_count
        self.request_preview = prompt_preview(request_text, 140) if request_text else ""
        self.started_at = now_iso()
        self.started_monotonic = time.monotonic()
        self.cancel_event = threading.Event()
        self.process: Optional[subprocess.Popen[str]] = None
        self.status_message_id: Optional[int] = None
        self.lock = threading.Lock()
        self.phase = "queued"
        self.progress_lines: list[str] = []
        self.progress_revision = 0

    def set_process(self, process: subprocess.Popen[str]) -> None:
        with self.lock:
            self.process = process
            self.phase = "codex running"
            self.progress_revision += 1

    def set_status_message(self, message_id: Optional[int]) -> None:
        with self.lock:
            self.status_message_id = message_id

    def add_progress(self, line: str) -> None:
        clean = sanitize_progress_line(line)
        if not clean:
            return
        with self.lock:
            if self.progress_lines and self.progress_lines[-1] == clean:
                return
            self.progress_lines.append(clean)
            self.progress_lines = self.progress_lines[-MAX_PROGRESS_LINES:]
            self.phase = "codex active"
            self.progress_revision += 1

    def progress_snapshot(self) -> tuple[str, int, list[str], Optional[int]]:
        with self.lock:
            return self.phase, self.progress_revision, list(self.progress_lines), self.status_message_id

    def cancel(self) -> None:
        self.cancel_event.set()
        with self.lock:
            process = self.process
        if process is not None:
            signal_process(process, signal.SIGTERM)

    def elapsed(self) -> str:
        return duration_text(time.monotonic() - self.started_monotonic)


JOBS_LOCK = threading.Lock()
ACTIVE_JOBS: dict[str, RelayJob] = {}
SHUTDOWN_CANCEL_STARTED = threading.Event()


def register_job(job: RelayJob) -> None:
    with JOBS_LOCK:
        ACTIVE_JOBS[job.id] = job


def finish_job(job: RelayJob) -> None:
    with JOBS_LOCK:
        ACTIVE_JOBS.pop(job.id, None)


def jobs_for_chat(chat_id: int) -> list[RelayJob]:
    with JOBS_LOCK:
        return [job for job in ACTIVE_JOBS.values() if job.chat_id == chat_id]


def jobs_for_thread(chat_id: int, thread_name: str) -> list[RelayJob]:
    return [job for job in jobs_for_chat(chat_id) if job.thread_name == thread_name]


def find_job(chat_id: int, job_id: str) -> Optional[RelayJob]:
    with JOBS_LOCK:
        job = ACTIVE_JOBS.get(job_id)
    if job and job.chat_id == chat_id:
        return job
    return None


def ansi_stripped(value: str) -> str:
    return re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", value)


def sanitize_progress_line(line: str) -> str:
    clean = ansi_stripped(line).replace("\r", " ").strip()
    clean = re.sub(r"\s+", " ", clean)
    clean = clean.replace("✓", "ok").replace("✔", "ok").replace("✗", "failed")
    if not clean:
        return ""
    lowered = clean.lower()
    if "session id:" in lowered:
        return ""
    if not gemini_allows_text(clean):
        return ""
    if len(clean) > 220:
        clean = clean[:217].rstrip() + "..."
    return clean


def progress_line_displayable(line: str) -> bool:
    clean = line.strip()
    if not clean:
        return False
    clean = re.sub(r"^[-*>\s]+", "", clean).strip()
    if re.match(r"^[?]{1,3}\s+", clean):
        return False
    words = re.findall(r"[A-Za-z0-9_./:-]+", clean)
    if len(words) <= 1 and len(clean) < 18:
        return False
    return True


def progress_interval_seconds() -> int:
    return max(5, env_int("CODEX_TELEGRAM_PROGRESS_INTERVAL_SECONDS", DEFAULT_PROGRESS_INTERVAL_SECONDS))


def progress_enabled(thread: dict[str, Any]) -> bool:
    return str(thread.get("progress_updates") or "").lower() in {"1", "true", "yes", "on"}


def set_progress_updates_text(thread: dict[str, Any], enabled: bool) -> str:
    thread["progress_updates"] = "true" if enabled else "false"
    thread["updated_at"] = now_iso()
    if enabled:
        return f"Live job updates: on ({progress_interval_seconds()}s minimum interval)"
    return "Live job updates: off"


def job_progress_text(job: RelayJob, force_detail: bool = False) -> str:
    phase, _revision, lines, _message_id = job.progress_snapshot()
    text = [f"Working: job {job.id}", f"thread: {job.thread_name}"]
    if job.request_preview:
        text.append(f"request: {job.request_preview}")
    text.extend([f"status: {phase}", f"elapsed: {job.elapsed()}"])
    if job.image_count:
        image_label = "image" if job.image_count == 1 else "images"
        text.append(f"attachments: {job.image_count} {image_label}")
    useful_lines = [line for line in lines if progress_line_displayable(line)]
    if useful_lines:
        shown = useful_lines if force_detail else useful_lines[-3:]
        text.append("progress:")
        text.extend(f"- {line}" for line in shown)
    else:
        text.append("progress: Codex is running; no useful status line yet.")
    text.append("check: /jobs")
    text.append(f"stop: /cancel {job.id}")
    return "\n".join(text)


class ProgressPulse:
    def __init__(self, api: TelegramAPI, chat_id: int, job: RelayJob, enabled: bool) -> None:
        self.api = api
        self.chat_id = chat_id
        self.job = job
        self.enabled = enabled
        self.interval = progress_interval_seconds()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> "ProgressPulse":
        if self.enabled:
            self.thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.stop.set()
        if self.enabled:
            self.thread.join(timeout=1)

    def _run(self) -> None:
        last_revision = -1
        last_sent = 0.0
        while not self.stop.wait(1):
            _phase, revision, lines, message_id = self.job.progress_snapshot()
            if message_id is None or revision == last_revision or not lines:
                continue
            now = time.monotonic()
            if now - last_sent < self.interval:
                continue
            try:
                self.api.edit_message(self.chat_id, message_id, job_progress_text(self.job))
                last_revision = revision
                last_sent = now
            except Exception:
                pass


TERMINAL_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,31}$")


def terminal_buffer_chars() -> int:
    return max(2000, env_int("CODEX_RELAY_TERMINAL_BUFFER_CHARS", 20000))


def terminal_read_limit() -> int:
    return max(500, env_int("CODEX_RELAY_TERMINAL_READ_LIMIT", DEFAULT_TERMINAL_READ_LIMIT))


def normalize_terminal_name(raw: str) -> str:
    name = (raw.strip() or "main").lower()
    if not TERMINAL_NAME_RE.fullmatch(name):
        raise ValueError("Terminal name must be 1-32 letters, numbers, dots, dashes, or underscores.")
    return name


def terminal_key(chat_id: int, name: str) -> str:
    return f"{chat_id}:{name}"


def terminal_output_clean(text: str) -> str:
    clean = ansi_stripped(text).replace("\r\n", "\n").replace("\r", "\n")
    clean = re.sub(r"\n{4,}", "\n\n\n", clean)
    return clean


class TerminalSession:
    def __init__(self, chat_id: int, name: str, cwd: Path, command: str = "") -> None:
        self.chat_id = chat_id
        self.name = name
        self.cwd = cwd
        self.command = command
        self.id = uuid.uuid4().hex[:8]
        self.started_at = now_iso()
        self.started_monotonic = time.monotonic()
        self.lock = threading.Lock()
        self.output = ""
        self.master_fd = -1
        self.process: Optional[subprocess.Popen[str]] = None
        self.reader: Optional[threading.Thread] = None

    def start(self) -> None:
        shell = os.environ.get("SHELL", "/bin/zsh") or "/bin/zsh"
        if self.command:
            argv = [shell, "-lc", self.command]
        else:
            argv = [shell, "-l"]
        master_fd, slave_fd = pty.openpty()
        env = os.environ.copy()
        env.setdefault("TERM", "xterm-256color")
        env["CODEX_RELAY_TERMINAL"] = "1"
        try:
            process = subprocess.Popen(
                argv,
                cwd=self.cwd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                text=False,
                close_fds=True,
                start_new_session=True,
                env=env,
            )
        finally:
            os.close(slave_fd)
        self.master_fd = master_fd
        self.process = process
        os.set_blocking(self.master_fd, False)
        self.reader = threading.Thread(target=self._read_loop, name=f"codex-relay-terminal-{self.name}", daemon=True)
        self.reader.start()

    def _append_output(self, chunk: str) -> None:
        if not chunk:
            return
        with self.lock:
            self.output += chunk
            max_chars = terminal_buffer_chars()
            if len(self.output) > max_chars:
                self.output = self.output[-max_chars:]

    def _read_loop(self) -> None:
        while True:
            process = self.process
            if process is None:
                return
            try:
                ready, _write, _error = select.select([self.master_fd], [], [], 0.2)
                if ready:
                    try:
                        data = os.read(self.master_fd, 4096)
                    except BlockingIOError:
                        data = b""
                    except OSError:
                        data = b""
                    if data:
                        self._append_output(data.decode(errors="replace"))
                if process.poll() is not None:
                    try:
                        while True:
                            data = os.read(self.master_fd, 4096)
                            if not data:
                                break
                            self._append_output(data.decode(errors="replace"))
                    except OSError:
                        pass
                    return
            except Exception:
                return

    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def elapsed(self) -> str:
        return duration_text(time.monotonic() - self.started_monotonic)

    def read(self, limit: Optional[int] = None) -> str:
        with self.lock:
            text = self.output
        text = terminal_output_clean(text)
        max_chars = limit or terminal_read_limit()
        if len(text) > max_chars:
            text = "(tail)\n" + text[-max_chars:].lstrip()
        return text.strip() or "(no terminal output yet)"

    def send(self, text: str, newline: bool = False) -> None:
        if not self.alive():
            raise RuntimeError(f"Terminal `{self.name}` is not running.")
        payload = text + ("\n" if newline else "")
        os.write(self.master_fd, payload.encode())

    def kill(self) -> None:
        process = self.process
        if process is not None and process.poll() is None:
            signal_process(process, signal.SIGTERM)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                signal_process(process, signal.SIGKILL)
        if self.master_fd >= 0:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = -1


def terminal_get(chat_id: int, name: str) -> Optional[TerminalSession]:
    with TERMINALS_LOCK:
        session = TERMINALS.get(terminal_key(chat_id, name))
        if session and not session.alive():
            TERMINALS.pop(terminal_key(chat_id, name), None)
        return session if session and session.alive() else None


def terminal_list(chat_id: int) -> list[TerminalSession]:
    with TERMINALS_LOCK:
        sessions = [session for session in TERMINALS.values() if session.chat_id == chat_id and session.alive()]
        stale = [key for key, session in TERMINALS.items() if session.chat_id == chat_id and not session.alive()]
        for key in stale:
            TERMINALS.pop(key, None)
        return sorted(sessions, key=lambda session: session.started_at)


def terminal_open(chat_id: int, name: str, cwd: Path, command: str = "") -> TerminalSession:
    name = normalize_terminal_name(name)
    existing = terminal_get(chat_id, name)
    if existing:
        raise ValueError(f"Terminal `{name}` is already running.")
    session = TerminalSession(chat_id, name, cwd, command)
    session.start()
    with TERMINALS_LOCK:
        TERMINALS[terminal_key(chat_id, name)] = session
    return session


def terminal_kill(chat_id: int, selector: str) -> list[str]:
    target = (selector.strip() or "main").lower()
    killed: list[str] = []
    with TERMINALS_LOCK:
        if target in {"all", "clear"}:
            sessions = [session for session in TERMINALS.values() if session.chat_id == chat_id]
        else:
            name = normalize_terminal_name(target)
            session = TERMINALS.get(terminal_key(chat_id, name))
            sessions = [session] if session else []
    for session in sessions:
        session.kill()
        killed.append(session.name)
        with TERMINALS_LOCK:
            TERMINALS.pop(terminal_key(chat_id, session.name), None)
    return killed


def parse_terminal_open_arg(arg: str) -> tuple[str, str]:
    value = arg.strip()
    if not value:
        return "main", ""
    if " -- " in value:
        left, command = value.split(" -- ", 1)
        return normalize_terminal_name(left or "main"), command.strip()
    parts = shlex.split(value)
    if len(parts) == 1 and TERMINAL_NAME_RE.fullmatch(parts[0]):
        return normalize_terminal_name(parts[0]), ""
    return "main", value


def parse_terminal_target_and_text(chat_id: int, arg: str) -> tuple[str, str]:
    value = arg.strip()
    if not value:
        raise ValueError("Give me text to send to the terminal.")
    parts = value.split(None, 1)
    if len(parts) == 2:
        candidate = parts[0].strip()
        if terminal_get(chat_id, candidate):
            return normalize_terminal_name(candidate), parts[1]
    return "main", value


def terminal_help_text() -> str:
    return "\n".join(
        [
            "Terminal commands:",
            "/terminal open - start a main login shell",
            "/terminal open name - start a named shell",
            "/terminal open name -- command - start a named command",
            "/terminal list - list running terminals",
            "/terminal read [name] - show recent output",
            "/terminal send [name] text - type without Enter",
            "/terminal enter [name] text - type and press Enter",
            "/terminal kill [name|all] - stop terminals",
            "Alias: /term",
        ]
    )


def terminal_list_text(chat_id: int) -> str:
    sessions = terminal_list(chat_id)
    if not sessions:
        return "terminals: none"
    lines = ["terminals:"]
    for session in sessions:
        cmd = f"; command: {session.command}" if session.command else ""
        lines.append(f"- {session.name}: running {session.elapsed()}; cwd: {session.cwd}{cmd}")
    return "\n".join(lines)


def terminal_command_text(chat_id: int, thread: dict[str, Any], arg: str) -> str:
    subcommand, _space, rest = arg.strip().partition(" ")
    subcommand = subcommand.lower()
    if not subcommand or subcommand in {"help", "?"}:
        return terminal_help_text()
    if subcommand in {"list", "ls"}:
        return terminal_list_text(chat_id)
    if subcommand in {"open", "new", "start"}:
        name, command = parse_terminal_open_arg(rest)
        cwd = Path(str(thread.get("workdir") or default_workdir())).expanduser()
        if not cwd.exists() or not cwd.is_dir():
            raise ValueError(f"Current thread folder is not usable: {cwd}")
        session = terminal_open(chat_id, name, cwd, command)
        time.sleep(0.2)
        output = session.read(1000)
        return f"Terminal `{session.name}` started in {cwd}.\n\n{output}"
    if subcommand in {"read", "tail", "show"}:
        name = normalize_terminal_name(rest or "main")
        session = terminal_get(chat_id, name)
        if not session:
            return f"No running terminal: {name}"
        return f"Terminal `{name}` output:\n\n{session.read()}"
    if subcommand in {"send", "type", "write"}:
        name, text = parse_terminal_target_and_text(chat_id, rest)
        session = terminal_get(chat_id, name)
        if not session:
            return f"No running terminal: {name}"
        session.send(text, newline=False)
        return f"Sent to terminal `{name}`."
    if subcommand in {"enter", "line", "input"}:
        name, text = parse_terminal_target_and_text(chat_id, rest)
        session = terminal_get(chat_id, name)
        if not session:
            return f"No running terminal: {name}"
        session.send(text, newline=True)
        time.sleep(0.2)
        return f"Sent Enter to terminal `{name}`.\n\n{session.read(1200)}"
    if subcommand in {"kill", "stop", "close"}:
        killed = terminal_kill(chat_id, rest)
        if not killed:
            return "No matching terminal to kill."
        return "Killed terminal: " + ", ".join(killed)
    raise ValueError("Unknown terminal command. Use /terminal help.")


def pending_item_image_paths(item: dict[str, Any]) -> list[str]:
    raw_paths = item.get("image_paths") or []
    if not isinstance(raw_paths, list):
        return []
    paths: list[str] = []
    for raw in raw_paths:
        value = str(raw or "").strip()
        if value:
            paths.append(value)
    return paths[: max_images_per_message()]


def pending_requests(thread: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items = thread.get("pending_requests") or []
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, Any]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        prompt = str(raw.get("prompt") or "").strip()
        if not prompt:
            continue
        request_id = str(raw.get("id") or uuid.uuid4().hex[:8])[:16]
        image_paths = pending_item_image_paths(raw)
        items.append(
            {
                "id": request_id,
                "prompt": prompt[:MAX_PENDING_PROMPT_CHARS],
                "image_paths": image_paths,
                "image_count": len(image_paths),
                "created_at": str(raw.get("created_at") or now_iso()),
                "updated_at": str(raw.get("updated_at") or raw.get("created_at") or now_iso()),
            }
        )
    return items[:MAX_PENDING_REQUESTS]


def save_pending_requests(thread: dict[str, Any], items: list[dict[str, Any]]) -> None:
    thread["pending_requests"] = items[:MAX_PENDING_REQUESTS]
    thread["updated_at"] = now_iso()


def prompt_preview(prompt: str, limit: int = 90) -> str:
    clean = re.sub(r"\s+", " ", prompt).strip()
    if len(clean) > limit:
        clean = clean[: limit - 3].rstrip() + "..."
    return clean


def normalize_pending_image_paths(image_paths: Optional[list[Path]]) -> list[str]:
    if not image_paths:
        return []
    paths: list[str] = []
    for path in image_paths[: max_images_per_message()]:
        paths.append(str(path))
    return paths


def queue_pending_request(
    thread: dict[str, Any],
    prompt: str,
    image_paths: Optional[list[Path]] = None,
) -> dict[str, Any]:
    clean = prompt.strip()[:MAX_PENDING_PROMPT_CHARS]
    if not clean:
        raise ValueError("Give me a request to queue.")
    items = pending_requests(thread)
    if len(items) >= MAX_PENDING_REQUESTS:
        raise ValueError(f"Pending queue is full ({MAX_PENDING_REQUESTS}).")
    stored_images = normalize_pending_image_paths(image_paths)
    item = {
        "id": uuid.uuid4().hex[:8],
        "prompt": clean,
        "image_paths": stored_images,
        "image_count": len(stored_images),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    items.append(item)
    save_pending_requests(thread, items)
    return item


def pending_selector(value: str) -> str:
    return (value.strip().lower() or "latest").replace("#", "")


def safe_unlink_pending_image(raw_path: str) -> bool:
    try:
        root = attachments_dir().resolve()
        path = Path(raw_path).expanduser().resolve()
        if root not in path.parents:
            return False
        if path.is_file():
            path.unlink()
            return True
    except OSError:
        return False
    return False


def delete_pending_item_images(item: dict[str, Any]) -> int:
    deleted = 0
    for raw_path in pending_item_image_paths(item):
        if safe_unlink_pending_image(raw_path):
            deleted += 1
    return deleted


def replace_pending_request(thread: dict[str, Any], selector: str, prompt: str) -> dict[str, Any]:
    clean = prompt.strip()[:MAX_PENDING_PROMPT_CHARS]
    if not clean:
        raise ValueError("Give me replacement text for the pending request.")
    items = pending_requests(thread)
    if not items:
        raise ValueError("No pending requests to modify.")
    target = pending_selector(selector)
    index = len(items) - 1 if target in {"latest", "last"} else -1
    if index == -1:
        for idx, item in enumerate(items):
            if item["id"].lower().startswith(target):
                index = idx
                break
    if index == -1:
        raise ValueError(f"No pending request matches: {selector}")
    items[index]["prompt"] = clean
    items[index]["updated_at"] = now_iso()
    save_pending_requests(thread, items)
    return items[index]


def remove_pending_images(thread: dict[str, Any], selector: str = "latest") -> tuple[list[dict[str, Any]], int]:
    items = pending_requests(thread)
    if not items:
        return [], 0
    target = pending_selector(selector)
    indexes: list[int] = []
    if target in {"all", "clear"}:
        indexes = list(range(len(items)))
    elif target in {"latest", "last"}:
        indexes = [len(items) - 1]
    else:
        for idx, item in enumerate(items):
            if item["id"].lower().startswith(target):
                indexes = [idx]
                break
    if not indexes:
        return [], 0
    changed: list[dict[str, Any]] = []
    deleted = 0
    for index in indexes:
        item = items[index]
        if pending_item_image_paths(item):
            deleted += delete_pending_item_images(item)
            item["image_paths"] = []
            item["image_count"] = 0
            item["updated_at"] = now_iso()
            changed.append(item)
    save_pending_requests(thread, items)
    return changed, deleted


def prioritize_pending_request(thread: dict[str, Any], selector: str = "latest") -> dict[str, Any]:
    items = pending_requests(thread)
    if not items:
        raise ValueError("No pending requests to reorder.")
    target = pending_selector(selector)
    index = len(items) - 1 if target in {"latest", "last"} else -1
    if index == -1:
        for idx, item in enumerate(items):
            if item["id"].lower().startswith(target):
                index = idx
                break
    if index == -1:
        raise ValueError(f"No pending request matches: {selector}")
    item = items.pop(index)
    items.insert(0, item)
    item["updated_at"] = now_iso()
    save_pending_requests(thread, items)
    return item


def remove_pending_request(thread: dict[str, Any], selector: str = "latest") -> list[dict[str, Any]]:
    items = pending_requests(thread)
    if not items:
        return []
    target = pending_selector(selector)
    if target in {"all", "clear"}:
        removed = items
        for item in removed:
            delete_pending_item_images(item)
        save_pending_requests(thread, [])
        return removed
    index = len(items) - 1 if target in {"latest", "last"} else -1
    if index == -1:
        for idx, item in enumerate(items):
            if item["id"].lower().startswith(target):
                index = idx
                break
    if index == -1:
        return []
    removed = [items.pop(index)]
    for item in removed:
        delete_pending_item_images(item)
    save_pending_requests(thread, items)
    return removed


def pop_next_pending_request(thread: dict[str, Any]) -> Optional[dict[str, Any]]:
    items = pending_requests(thread)
    if not items:
        return None
    item = items.pop(0)
    save_pending_requests(thread, items)
    return item


def pending_paths_for_codex(item: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for raw_path in pending_item_image_paths(item):
        path = Path(raw_path).expanduser()
        if path.is_file():
            paths.append(path)
    return paths[: max_images_per_message()]


def pending_queue_text(thread: dict[str, Any]) -> str:
    items = pending_requests(thread)
    if not items:
        return "pending: none"
    lines = ["pending:"]
    for item in items:
        image_count = int_or_none(item.get("image_count")) or 0
        image_note = ""
        if image_count:
            image_label = "image" if image_count == 1 else "images"
            image_note = f"; {image_count} {image_label}"
        lines.append(f"- {item['id']}: {prompt_preview(item['prompt'])}{image_note}")
    return "\n".join(lines)


def cancel_all_jobs() -> None:
    with JOBS_LOCK:
        jobs = list(ACTIVE_JOBS.values())
    for job in jobs:
        job.cancel()
    with TERMINALS_LOCK:
        sessions = list(TERMINALS.values())
        TERMINALS.clear()
    for session in sessions:
        session.kill()


def cancel_all_jobs_async() -> None:
    if SHUTDOWN_CANCEL_STARTED.is_set():
        return
    SHUTDOWN_CANCEL_STARTED.set()
    worker = threading.Thread(target=cancel_all_jobs, name="codex-relay-shutdown-cancel", daemon=True)
    worker.start()


def register_worker(worker: threading.Thread) -> None:
    with WORKERS_LOCK:
        WORKERS.append(worker)


def cleanup_workers() -> None:
    with WORKERS_LOCK:
        WORKERS[:] = [worker for worker in WORKERS if worker.is_alive()]


def join_workers(timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while True:
        cleanup_workers()
        with WORKERS_LOCK:
            workers = list(WORKERS)
        if not workers:
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        workers[0].join(timeout=min(1.0, remaining))


def request_shutdown(_signum: int, _frame: object) -> None:
    SHUTDOWN_EVENT.set()
    cancel_all_jobs_async()


def state_dir() -> Path:
    return private_dir(Path(os.environ.get("CODEX_TELEGRAM_STATE_DIR", STATE_DIR_DEFAULT)))


def attachments_dir() -> Path:
    return private_dir(state_dir() / "attachments")


def captures_dir() -> Path:
    return private_dir(state_dir() / "captures")


def history_path() -> Path:
    return state_dir() / "events.jsonl"


def int_or_none(value: object) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def image_suffix(file_name: str = "", mime_type: str = "", file_path: str = "") -> str:
    for raw in (file_name, file_path):
        suffix = Path(raw or "").suffix.lower()
        if suffix in IMAGE_SUFFIXES:
            return ".jpg" if suffix == ".jpeg" else suffix
    mime = (mime_type or "").split(";", 1)[0].strip().lower()
    return IMAGE_SUFFIX_BY_MIME.get(mime, ".jpg")


def max_images_per_message() -> int:
    return max(1, env_int("CODEX_TELEGRAM_MAX_IMAGES_PER_MESSAGE", MAX_IMAGES_PER_MESSAGE))


def image_attachment_specs(message: dict[str, Any]) -> list[dict[str, Any]]:
    grouped = message.get("_relay_media_group_messages")
    if isinstance(grouped, list):
        grouped_specs: list[dict[str, Any]] = []
        for item in grouped:
            if isinstance(item, dict):
                single = dict(item)
                single.pop("_relay_media_group_messages", None)
                grouped_specs.extend(image_attachment_specs(single))
            if len(grouped_specs) >= max_images_per_message():
                break
        return grouped_specs[: max_images_per_message()]

    specs: list[dict[str, Any]] = []
    photos = message.get("photo") or []
    if isinstance(photos, list) and photos:
        photo = max(
            photos,
            key=lambda item: (
                int_or_none(item.get("file_size")) or 0,
                (int_or_none(item.get("width")) or 0) * (int_or_none(item.get("height")) or 0),
            ),
        )
        if photo.get("file_id"):
            specs.append(
                {
                    "file_id": str(photo["file_id"]),
                    "file_size": int_or_none(photo.get("file_size")),
                    "file_name": "telegram-photo.jpg",
                    "mime_type": "image/jpeg",
                }
            )

    document = message.get("document") or {}
    if isinstance(document, dict) and document.get("file_id"):
        file_name = str(document.get("file_name") or "")
        mime_type = str(document.get("mime_type") or "")
        if mime_type.startswith("image/") or Path(file_name).suffix.lower() in IMAGE_SUFFIXES:
            specs.append(
                {
                    "file_id": str(document["file_id"]),
                    "file_size": int_or_none(document.get("file_size")),
                    "file_name": file_name,
                    "mime_type": mime_type,
                }
            )

    return specs[: max_images_per_message()]


def media_group_key(message: dict[str, Any]) -> Optional[tuple[int, str]]:
    media_group_id = str(message.get("media_group_id") or "").strip()
    if not media_group_id or not image_attachment_specs(message):
        return None
    chat = message.get("chat") or {}
    chat_id = int_or_none(chat.get("id"))
    if chat_id is None:
        return None
    return chat_id, media_group_id


def merge_media_group_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    if not messages:
        return {}
    merged = dict(messages[0])
    merged["_relay_media_group_messages"] = list(messages)
    for item in messages:
        text = str(item.get("caption") or item.get("text") or "").strip()
        if text:
            merged["caption"] = text
            merged["text"] = text
            break
    return merged


def prune_attachment_cache(root: Path) -> None:
    retention_days = env_int("CODEX_TELEGRAM_IMAGE_RETENTION_DAYS", DEFAULT_IMAGE_RETENTION_DAYS)
    if retention_days < 0 or not root.exists():
        return
    cutoff = time.time() - retention_days * 86400
    for path in sorted(root.rglob("*"), reverse=True):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        except OSError:
            pass


def download_telegram_images(api: TelegramAPI, message: dict[str, Any]) -> list[Path]:
    specs = image_attachment_specs(message)
    if not specs:
        return []

    root = attachments_dir()
    prune_attachment_cache(root)
    max_bytes = env_int("CODEX_TELEGRAM_MAX_IMAGE_BYTES", DEFAULT_MAX_IMAGE_BYTES)
    if max_bytes <= 0:
        raise RuntimeError("CODEX_TELEGRAM_MAX_IMAGE_BYTES must be positive")

    saved: list[Path] = []
    dated_dir = private_dir(root / dt.datetime.now().strftime("%Y%m%d"))
    message_id = str(message.get("message_id") or int(time.time()))
    stamp = dt.datetime.now().strftime("%H%M%S")

    for index, spec in enumerate(specs, start=1):
        announced_size = int_or_none(spec.get("file_size"))
        if announced_size and announced_size > max_bytes:
            raise RuntimeError(
                f"image is too large ({announced_size} bytes; limit {max_bytes})"
            )

        file_info = api.get_file(str(spec["file_id"]))
        file_path = str(file_info.get("file_path") or "")
        if not file_path:
            raise RuntimeError("Telegram did not return a file path for the image")

        reported_size = int_or_none(file_info.get("file_size")) or announced_size
        if reported_size and reported_size > max_bytes:
            raise RuntimeError(
                f"image is too large ({reported_size} bytes; limit {max_bytes})"
            )

        content = api.download_file(file_path, max_bytes=max_bytes)

        suffix = image_suffix(
            str(spec.get("file_name") or ""),
            str(spec.get("mime_type") or ""),
            file_path,
        )
        target = dated_dir / f"telegram-{stamp}-{message_id}-{index}{suffix}"
        write_private_bytes(target, content)
        saved.append(target)

    return saved


def capture_screenshot() -> Path:
    if sys.platform != "darwin":
        raise RuntimeError("screenshots are macOS-only")
    if not shutil.which("screencapture"):
        raise RuntimeError("screencapture command is missing")
    root = captures_dir()
    prune_attachment_cache(root)
    target = root / f"screenshot-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.jpg"
    try:
        subprocess.run(
            ["screencapture", "-x", "-t", "jpg", str(target)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()
        raise RuntimeError(detail or "screencapture failed") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("screencapture timed out") from exc
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError("screencapture produced no image")
    os.chmod(target, 0o600)
    return target


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


def append_history_event(event: dict[str, Any]) -> None:
    allowed = {
        "at",
        "chat_id",
        "thread",
        "status",
        "latency_seconds",
        "image_count",
        "reasoning_effort",
        "exit_code",
        "job_id",
        "folder",
    }
    safe_event = {key: event[key] for key in allowed if key in event and event[key] is not None}
    path = history_path()
    line = json.dumps(safe_event, sort_keys=True) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a") as handle:
        handle.write(line)
    os.chmod(path, 0o600)


def read_history(limit: int = 8) -> list[dict[str, Any]]:
    path = history_path()
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return []
    events: list[dict[str, Any]] = []
    for line in lines[-max(1, limit) :]:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def chat_threads(data: dict[str, Any], chat_id: int) -> dict[str, dict[str, Any]]:
    chats = data.setdefault("threads_by_chat", {})
    return chats.setdefault(str(chat_id), {})


def active_thread_name(data: dict[str, Any], chat_id: int) -> str:
    return data.setdefault("active_by_chat", {}).get(str(chat_id), DEFAULT_THREAD)


def set_active_thread(data: dict[str, Any], chat_id: int, name: str) -> None:
    data.setdefault("active_by_chat", {})[str(chat_id)] = name


def active_state(threads_path: Path, chat_id: int) -> tuple[dict[str, Any], str, dict[str, Any]]:
    data = read_threads(threads_path)
    active_missing = str(chat_id) not in data.setdefault("active_by_chat", {})
    active_name = active_thread_name(data, chat_id)
    thread = ensure_thread(data, chat_id, active_name)
    set_active_thread(data, chat_id, active_name)
    if active_missing:
        write_threads(threads_path, data)
    return data, active_name, thread


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
    thread.setdefault("reply_style", reply_style_default())
    return thread


def resolve_workdir(raw: str, current: str) -> Path:
    value = raw.strip()
    if not value:
        raise ValueError("Give me a folder, like `/cd Projects/my-repo`.")
    if value == ".":
        path = Path(current)
    elif value.startswith("~"):
        path = Path(value).expanduser()
    elif value.startswith("/"):
        path = Path(value)
        if not path.exists() and (value == "/code" or value.startswith("/code/")):
            path = Path.home() / value.lstrip("/")
    else:
        path = Path.home() / value
    path = path.resolve()
    if not path.exists():
        raise ValueError(f"Folder does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"Not a folder: {path}")
    return path


def path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def max_file_transfer_bytes() -> int:
    return max(1, env_int("CODEX_TELEGRAM_MAX_FILE_BYTES", DEFAULT_MAX_FILE_BYTES))


def allow_sensitive_file_transfer() -> bool:
    return env_bool("CODEX_RELAY_ALLOW_SENSITIVE_FILE_TRANSFER", False)


def resolve_transfer_file(raw: str, current_workdir: str) -> Path:
    value = raw.strip()
    if not value:
        raise ValueError("Give me a file path, like `/file README.md`.")
    if value.startswith("~"):
        path = Path(value).expanduser()
    elif value.startswith("/"):
        path = Path(value)
    else:
        path = Path(current_workdir).expanduser() / value
    path = path.resolve()
    if not path.exists():
        raise ValueError(f"File does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Not a file: {path}")
    size = path.stat().st_size
    max_bytes = max_file_transfer_bytes()
    if size > max_bytes:
        raise ValueError(f"File is too large ({size} bytes; limit {max_bytes}).")
    return path


def transfer_file_blocker(path: Path) -> str:
    if allow_sensitive_file_transfer():
        return ""
    lower_parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    sensitive_names = {
        ".env",
        ".netrc",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "known_hosts",
    }
    sensitive_substrings = ("token", "secret", "password", "private-key", "private_key", "credential")
    if name in sensitive_names or any(term in name for term in sensitive_substrings):
        return "blocked sensitive-looking file name"
    if ".ssh" in lower_parts or ".gnupg" in lower_parts:
        return "blocked credential directory"
    try:
        if path_is_within(path, state_dir()):
            return "blocked relay runtime state"
    except Exception:
        pass
    return ""


def send_file_to_telegram(
    api: TelegramAPI,
    chat_id: int,
    thread: dict[str, Any],
    raw_path: str,
    reply_to_message_id: Optional[int] = None,
) -> str:
    path = resolve_transfer_file(raw_path, str(thread.get("workdir") or default_workdir()))
    blocker = transfer_file_blocker(path)
    if blocker:
        raise ValueError(f"Blocked: {blocker}. Set CODEX_RELAY_ALLOW_SENSITIVE_FILE_TRANSFER=true only if you accept the risk.")
    api.send_document(chat_id, path, f"File: {path.name}", reply_to_message_id)
    return f"Sent file: {path}"


def authorized(
    user_id: Optional[int],
    chat_id: int,
    chat_type: str,
    allowed_users: set[int],
    allowed_chats: set[int],
) -> bool:
    if chat_type != "private" and not env_bool("CODEX_TELEGRAM_ALLOW_GROUP_CHATS", False):
        return False
    if chat_type != "private":
        if not allowed_users or not allowed_chats:
            return False
        return user_id in allowed_users and chat_id in allowed_chats
    if allowed_users and allowed_chats:
        return user_id in allowed_users and chat_id in allowed_chats
    if allowed_users:
        return user_id in allowed_users
    if allowed_chats:
        return chat_id in allowed_chats
    return False


def gemini_api_key() -> str:
    return (
        os.environ.get("CODEX_RELAY_GEMINI_API_KEY", "").strip()
        or os.environ.get("GEMINI_API_KEY", "").strip()
    )


def gemini_configured() -> bool:
    return bool(gemini_api_key())


def gemini_enabled() -> bool:
    if not gemini_configured():
        return False
    return env_bool("CODEX_RELAY_GEMINI_ENABLED", True)


def gemini_natural_commands_enabled() -> bool:
    return gemini_enabled() and env_bool("CODEX_RELAY_GEMINI_NATURAL_COMMANDS", True)


def gemini_polish_enabled() -> bool:
    return gemini_enabled() and env_bool("CODEX_RELAY_GEMINI_POLISH", True)


def gemini_model() -> str:
    return os.environ.get("CODEX_RELAY_GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL


def gemini_allows_text(*values: str) -> bool:
    combined = "\n".join(value for value in values if value)
    if not combined.strip():
        return True
    lowered = combined.lower()
    if any(term in lowered for term in GEMINI_SENSITIVE_TERMS):
        return False
    return GEMINI_SECRET_VALUE_RE.search(combined) is None


def gemini_timeout() -> int:
    return max(1, env_int("CODEX_RELAY_GEMINI_TIMEOUT_SECONDS", DEFAULT_GEMINI_TIMEOUT_SECONDS))


def gemini_max_output_tokens() -> int:
    return max(256, env_int("CODEX_RELAY_GEMINI_MAX_OUTPUT_TOKENS", DEFAULT_GEMINI_MAX_OUTPUT_TOKENS))


def gemini_response_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")
    parts = ((candidates[0].get("content") or {}).get("parts") or [])
    text_parts = [str(part.get("text") or "") for part in parts if part.get("text")]
    text = "".join(text_parts).strip()
    if not text:
        raise RuntimeError("Gemini returned no text")
    return text


def gemini_generate(prompt: str, response_schema: Optional[dict[str, Any]] = None) -> str:
    key = gemini_api_key()
    if not key:
        raise RuntimeError("Gemini API key is not configured")
    model = gemini_model()
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + urllib.parse.quote(model, safe="")
        + ":generateContent"
    )
    generation_config: dict[str, Any] = {
        "temperature": 0.2,
        "maxOutputTokens": gemini_max_output_tokens(),
    }
    if response_schema is not None:
        generation_config.update(
            {
                "responseMimeType": "application/json",
                "responseJsonSchema": response_schema,
            }
        )
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": generation_config,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": key,
        },
        method="POST",
    )
    try:
        with telegram_urlopen(request, timeout=gemini_timeout()) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Gemini HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini network error: {exc.reason}") from exc
    return gemini_response_text(payload)


GEMINI_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "reply": {
            "type": "string",
            "description": "Short optional note to send before any Codex job starts.",
        },
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": sorted(GEMINI_ACTIONS),
                        "description": "The relay action to run.",
                    },
                    "value": {
                        "type": "string",
                        "description": "Thread name, folder path, thinking mode, pending id, terminal name, file path, latest/all, or empty string, depending on action type.",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Prompt to send to Codex, queued request text, terminal command/input, or replacement text.",
                    },
                },
                "required": ["type"],
            },
        },
    },
    "required": ["actions"],
}


def gemini_plan_prompt(
    text: str,
    active_name: str,
    thread: dict[str, Any],
    threads: dict[str, dict[str, Any]],
) -> str:
    thread_lines = []
    for name in sorted(threads)[:20]:
        item = threads[name]
        status = "started" if item.get("session_id") else "new"
        thread_lines.append(f"- {name}: {status}; folder={item.get('workdir') or default_workdir()}")
    thread_text = "\n".join(thread_lines) or "- main: new"
    return f"""You are Codex Relay's mobile control planner.

Translate a private Telegram message into safe relay actions. The relay controls Codex locally; Codex does all repo/file/test/security work. You only choose relay actions.

Current active thread: {active_name}
Current folder: {thread.get('workdir') or default_workdir()}
Current thinking mode: {thinking_mode_status(thread)}
Pending requests:
{pending_queue_text(thread)}
Known threads:
{thread_text}

Allowed actions:
- queue_request: add a Codex request to the active thread's pending queue. Use when the current thread is busy or the user asks to do something after the current job.
- replace_pending_request: replace a pending request. Value is a pending id or latest; prompt is the new request text.
- remove_pending_request: remove a pending request. Value is a pending id, latest, or all. Use latest for "never mind" when the user does not specify.
- remove_pending_images: remove saved images from a pending request but keep its text. Value is a pending id, latest, or all. Use this when the user says the photos/images are bad, wrong, or should be ignored.
- prioritize_pending_request: move a pending request to the front of the queue. Value is a pending id or latest. Use this when the user says to do something next, first, before the others, or bump it up.
- show_queue: show pending requests.
- show_activity: summarize running jobs, pending requests, and recent safe history without starting Codex.
- terminal_open: open a persistent PTY terminal. Value is terminal name or empty for main. Prompt is an optional shell command to run.
- terminal_read: read recent terminal output. Value is terminal name or empty for main.
- terminal_send: send input to a terminal and press Enter. Value is terminal name or empty for main. Prompt is the input text.
- terminal_kill: stop a terminal. Value is terminal name, all, or empty for main.
- send_file: send a local file back to Telegram. Value is a file path relative to the active folder or absolute path.
- set_thinking_mode: set the active thread's Codex thinking mode. Value must be low, medium, high, xhigh, or default.
- set_workdir: set the active thread folder. For user shorthand like /code/name or code/name, return code/name or ~/code/name, not the filesystem root /code unless they clearly mean an absolute path.
- new_thread: create and switch to a named thread.
- use_thread: switch to an existing named thread.
- reset_thread: clear the current Codex session id.
- run_codex: start a Codex job with a clear prompt. Use this for audits, edits, summaries, research in a repo, diagnostics, and normal work.
- show_status: show current relay status.
- show_help: show relay command help.
- none: use only when the message is not actionable.

Rules:
- Return JSON only.
- Prefer one set_workdir followed by one run_codex for messages like "set my dir to X and run Y".
- Prefer one set_thinking_mode followed by one run_codex for messages like "switch to high thinking and run tests".
- If the user says "never mind", "forget that", or cancels a pending idea without a job id, use remove_pending_request rather than run_codex.
- If the user says only the photos/images are no good, use remove_pending_images rather than removing the whole pending request.
- If the user changes "that pending request", use replace_pending_request with value latest.
- If the user changes the order, use prioritize_pending_request instead of rewriting the request.
- If the user asks "what is going on", "what are you doing", "where are we", or asks for a summary while Codex is running, use show_activity.
- Use terminal actions only for explicit terminal/session/CLI login work, and prefer terminal_open before terminal_send if no terminal is running.
- Use send_file only when the user explicitly asks to fetch, send, download, or transfer a local file.
- Do not invent unsupported slash commands.
- Do not request or expose secrets, tokens, raw logs, auth files, or private transcripts.
- If the user asks for destructive, public, payment, account, medical, legal, or financial actions, still send the request to Codex as run_codex and let Codex stop at the confirmation boundary.
- Keep run_codex prompts direct and complete enough for Codex to execute.

Telegram message:
{text}
"""


def validate_gemini_plan(raw: Any, original_text: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"reply": "", "actions": []}
    actions: list[dict[str, str]] = []
    for item in raw.get("actions") or []:
        if not isinstance(item, dict):
            continue
        action_type = str(item.get("type") or "").strip()
        if action_type not in GEMINI_ACTIONS or action_type == "none":
            continue
        action = {
            "type": action_type,
            "value": str(item.get("value") or "").strip()[:500],
            "prompt": str(item.get("prompt") or "").strip()[:6000],
        }
        if action_type == "run_codex" and not action["prompt"]:
            action["prompt"] = original_text
        actions.append(action)
        if len(actions) >= 6:
            break
    return {"reply": str(raw.get("reply") or "").strip()[:1000], "actions": actions}


def gemini_plan_for_message(
    text: str,
    active_name: str,
    thread: dict[str, Any],
    threads: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    prompt = gemini_plan_prompt(text, active_name, thread, threads)
    response_text = gemini_generate(prompt, GEMINI_PLAN_SCHEMA)
    return validate_gemini_plan(json.loads(response_text), text)


def gemini_polish_answer(prompt_text: str, answer: str, thread: dict[str, Any]) -> str:
    if not gemini_polish_enabled() or not answer.strip():
        return answer
    if not gemini_allows_text(prompt_text, answer):
        return answer
    prompt = f"""Rewrite this Codex Relay reply for a private Telegram chat.

Goal: make it more human, readable, and easy to act on from a phone.

Rules:
- Preserve every factual claim, command, path, file name, warning, blocker, and verification result.
- Do not add new facts or pretend extra work happened.
- Do not reveal or request secrets.
- Use enough detail to make the phone reply useful. Do not over-compress changed files, commands, warnings, blockers, or verification.
- Use short paragraphs or bullets when they improve scanability.

Original user request:
{prompt_text}

Active folder:
{thread.get('workdir') or default_workdir()}

Thinking mode:
{thread_thinking_mode(thread)}

Codex reply:
{answer}
"""
    try:
        polished = gemini_generate(prompt).strip()
    except Exception:
        return answer
    return polished or answer


def execute_gemini_plan(
    api: TelegramAPI,
    chat_id: int,
    message_id: Optional[int],
    threads_path: Path,
    plan: dict[str, Any],
    original_text: str,
) -> bool:
    actions = plan.get("actions") or []
    if not actions:
        return False
    notes: list[str] = []
    for action in actions:
        action_type = action.get("type")
        value = str(action.get("value") or "").strip()
        if action_type == "show_help":
            api.send_message(chat_id, command_help(), message_id)
            return True
        if action_type == "show_status":
            with THREADS_LOCK:
                _data, _active_name, thread = active_state(threads_path, chat_id)
            api.send_message(chat_id, status_text(thread, chat_id), message_id)
            return True
        if action_type == "show_queue":
            with THREADS_LOCK:
                _data, _active_name, thread = active_state(threads_path, chat_id)
            api.send_message(chat_id, pending_queue_text(thread), message_id)
            return True
        if action_type == "show_activity":
            with THREADS_LOCK:
                _data, _active_name, thread = active_state(threads_path, chat_id)
            api.send_message(chat_id, activity_text(chat_id, thread), message_id)
            return True
        if action_type == "queue_request":
            prompt = str(action.get("prompt") or "").strip() or original_text
            try:
                with THREADS_LOCK:
                    data, _active_name, thread = active_state(threads_path, chat_id)
                    item = queue_pending_request(thread, prompt)
                    write_threads(threads_path, data)
            except ValueError as exc:
                api.send_message(chat_id, str(exc), message_id)
                return True
            notes.append(f"Queued request {item['id']}: {prompt_preview(item['prompt'])}")
            continue
        if action_type == "replace_pending_request":
            prompt = str(action.get("prompt") or "").strip() or original_text
            try:
                with THREADS_LOCK:
                    data, _active_name, thread = active_state(threads_path, chat_id)
                    item = replace_pending_request(thread, value, prompt)
                    write_threads(threads_path, data)
            except ValueError as exc:
                api.send_message(chat_id, str(exc), message_id)
                return True
            notes.append(f"Updated pending request {item['id']}: {prompt_preview(item['prompt'])}")
            continue
        if action_type == "remove_pending_request":
            with THREADS_LOCK:
                data, _active_name, thread = active_state(threads_path, chat_id)
                removed = remove_pending_request(thread, value)
                write_threads(threads_path, data)
            if removed:
                notes.append(
                    "Removed pending: "
                    + ", ".join(f"{item['id']} ({prompt_preview(item['prompt'], 48)})" for item in removed)
                )
            else:
                notes.append("No pending request matched.")
            continue
        if action_type == "remove_pending_images":
            with THREADS_LOCK:
                data, _active_name, thread = active_state(threads_path, chat_id)
                changed, deleted = remove_pending_images(thread, value)
                write_threads(threads_path, data)
            if changed:
                image_label = "image" if deleted == 1 else "images"
                notes.append(
                    f"Removed {deleted} saved {image_label} from pending: "
                    + ", ".join(item["id"] for item in changed)
                )
            else:
                notes.append("No pending images matched.")
            continue
        if action_type == "prioritize_pending_request":
            try:
                with THREADS_LOCK:
                    data, _active_name, thread = active_state(threads_path, chat_id)
                    item = prioritize_pending_request(thread, value)
                    write_threads(threads_path, data)
            except ValueError as exc:
                api.send_message(chat_id, str(exc), message_id)
                return True
            notes.append(f"Next up: {item['id']}: {prompt_preview(item['prompt'])}")
            continue
        if action_type == "terminal_open":
            with THREADS_LOCK:
                _data, _active_name, thread = active_state(threads_path, chat_id)
            try:
                name = normalize_terminal_name(value or "main")
                cwd = Path(str(thread.get("workdir") or default_workdir())).expanduser()
                session = terminal_open(chat_id, name, cwd, str(action.get("prompt") or "").strip())
            except (RuntimeError, ValueError, OSError) as exc:
                api.send_message(chat_id, str(exc), message_id)
                return True
            time.sleep(0.2)
            notes.append(f"Terminal `{session.name}` started.\n{session.read(800)}")
            continue
        if action_type == "terminal_read":
            name = normalize_terminal_name(value or "main")
            session = terminal_get(chat_id, name)
            if not session:
                api.send_message(chat_id, f"No running terminal: {name}", message_id)
                return True
            notes.append(f"Terminal `{name}` output:\n{session.read()}")
            continue
        if action_type == "terminal_send":
            name = normalize_terminal_name(value or "main")
            text = str(action.get("prompt") or "").strip()
            if not text:
                api.send_message(chat_id, "Give me terminal input to send.", message_id)
                return True
            session = terminal_get(chat_id, name)
            if not session:
                api.send_message(chat_id, f"No running terminal: {name}", message_id)
                return True
            try:
                session.send(text, newline=True)
            except RuntimeError as exc:
                api.send_message(chat_id, str(exc), message_id)
                return True
            time.sleep(0.2)
            notes.append(f"Sent input to terminal `{name}`.\n{session.read(1000)}")
            continue
        if action_type == "terminal_kill":
            try:
                killed = terminal_kill(chat_id, value or "main")
            except ValueError as exc:
                api.send_message(chat_id, str(exc), message_id)
                return True
            notes.append("Killed terminal: " + ", ".join(killed) if killed else "No matching terminal to kill.")
            continue
        if action_type == "send_file":
            raw_path = value or str(action.get("prompt") or "").strip()
            try:
                with THREADS_LOCK:
                    _data, _active_name, thread = active_state(threads_path, chat_id)
                note = send_file_to_telegram(api, chat_id, thread, raw_path, message_id)
            except (RuntimeError, ValueError) as exc:
                api.send_message(chat_id, str(exc), message_id)
                return True
            notes.append(note)
            continue
        if action_type == "new_thread":
            try:
                name = normalize_thread_name(value)
            except ValueError as exc:
                api.send_message(chat_id, str(exc), message_id)
                return True
            with THREADS_LOCK:
                data, _active_name, _thread = active_state(threads_path, chat_id)
                thread = ensure_thread(data, chat_id, name)
                thread["session_id"] = ""
                thread["updated_at"] = now_iso()
                set_active_thread(data, chat_id, name)
                write_threads(threads_path, data)
            notes.append(f"New thread: {name}")
            continue
        if action_type == "use_thread":
            try:
                name = normalize_thread_name(value)
            except ValueError as exc:
                api.send_message(chat_id, str(exc), message_id)
                return True
            with THREADS_LOCK:
                data, _active_name, _thread = active_state(threads_path, chat_id)
                threads = chat_threads(data, chat_id)
                if name not in threads:
                    api.send_message(chat_id, f"No thread named `{name}`. Use `/new {name}`.", message_id)
                    return True
                set_active_thread(data, chat_id, name)
                write_threads(threads_path, data)
            notes.append(f"Using thread: {name}")
            continue
        if action_type == "reset_thread":
            with THREADS_LOCK:
                data, active_name, thread = active_state(threads_path, chat_id)
            busy = busy_thread_message(chat_id, active_name)
            if busy:
                api.send_message(chat_id, busy, message_id)
                return True
            with THREADS_LOCK:
                data, active_name, thread = active_state(threads_path, chat_id)
                thread["session_id"] = ""
                thread["updated_at"] = now_iso()
                write_threads(threads_path, data)
            notes.append(f"Reset thread: {active_name}")
            continue
        if action_type == "set_thinking_mode":
            try:
                mode_note = ""
                with THREADS_LOCK:
                    data, _active_name, thread = active_state(threads_path, chat_id)
                    mode_note = set_thinking_mode_text(thread, value)
                    write_threads(threads_path, data)
            except ValueError as exc:
                api.send_message(chat_id, str(exc), message_id)
                return True
            notes.append(mode_note)
            continue
        if action_type == "set_workdir":
            with THREADS_LOCK:
                data, active_name, thread = active_state(threads_path, chat_id)
                current_workdir = str(thread.get("workdir") or default_workdir())
            busy = busy_thread_message(chat_id, active_name)
            if busy:
                api.send_message(chat_id, busy, message_id)
                return True
            try:
                path = resolve_workdir(value, current_workdir)
            except ValueError as exc:
                api.send_message(chat_id, str(exc), message_id)
                return True
            with THREADS_LOCK:
                data, active_name, thread = active_state(threads_path, chat_id)
                thread["workdir"] = str(path)
                thread["updated_at"] = now_iso()
                write_threads(threads_path, data)
            notes.append(f"Folder set:\n{path}")
            continue
        if action_type == "run_codex":
            prompt = str(action.get("prompt") or "").strip() or original_text
            with THREADS_LOCK:
                _data, active_name, thread = active_state(threads_path, chat_id)
            busy = busy_thread_message(chat_id, active_name)
            if busy:
                try:
                    with THREADS_LOCK:
                        data, active_name, thread = active_state(threads_path, chat_id)
                        item = queue_pending_request(thread, prompt)
                        write_threads(threads_path, data)
                except ValueError as exc:
                    api.send_message(chat_id, f"{busy}\n{exc}", message_id)
                    return True
                preface = "\n\n".join(notes + ([plan.get("reply", "").strip()] if plan.get("reply") else []))
                queued = f"Queued request {item['id']} until thread `{active_name}` is clear: {prompt_preview(item['prompt'])}"
                api.send_message(chat_id, "\n\n".join(part for part in [preface, queued] if part), message_id)
                return True
            preface = "\n\n".join(notes + ([plan.get("reply", "").strip()] if plan.get("reply") else []))
            if preface:
                api.send_message(chat_id, preface, message_id)
            start_background_job(
                api,
                chat_id,
                threads_path,
                active_name,
                thread,
                prompt,
                reply_to_message_id=message_id,
            )
            return True
    if notes or plan.get("reply"):
        api.send_message(chat_id, "\n\n".join(notes + ([plan.get("reply", "").strip()] if plan.get("reply") else [])), message_id)
        return True
    return False


def relay_user_name() -> str:
    return os.environ.get("CODEX_RELAY_USER_NAME", "the user").strip() or "the user"


def relay_assistant_name() -> str:
    return os.environ.get("CODEX_RELAY_ASSISTANT_NAME", "Codex").strip() or "Codex"


def relay_assistant_personality() -> str:
    return os.environ.get("CODEX_RELAY_ASSISTANT_PERSONALITY", "").strip()


def style_instruction(reply_style: str) -> str:
    if reply_style == "verbose":
        return (
            "Reply with enough detail to be useful for debugging or handoff. "
            "Use concise structure, include verification, and avoid filler."
        )
    if reply_style == "normal":
        return (
            "Reply with a compact but complete update. Include what changed, what was verified, "
            "and any blocker or next step. Use bullets when they improve scanability."
        )
    return (
        "Reply in the fewest words that still answer the task, but do not reduce useful status "
        "to fragments. Prefer concrete status, changed files, verification, and the next "
        "human-only boundary."
    )


def codex_prompt(
    message_text: str,
    thread_name: str,
    image_paths: Optional[list[Path]] = None,
    reply_style: Optional[str] = None,
    thinking_mode: Optional[str] = None,
) -> str:
    user_name = relay_user_name()
    assistant_name = relay_assistant_name()
    personality = relay_assistant_personality()
    personality_note = (
        f"\n{assistant_name}'s personality: {personality}\n" if personality else ""
    )
    style = reply_style if reply_style in REPLY_STYLES else reply_style_default()
    mode = thinking_mode or thinking_mode_default()
    image_paths = image_paths or []
    image_note = ""
    if image_paths:
        image_label = "image" if len(image_paths) == 1 else "images"
        image_lines = "\n".join(f"- {path}" for path in image_paths)
        image_note = (
            f"\nTelegram sent {len(image_paths)} {image_label}. "
            "They are attached to this Codex prompt and saved privately at:\n"
            f"{image_lines}\n"
            "Use them only for this Telegram task; do not reveal private paths unless needed.\n"
        )
    return f"""You are {assistant_name}, a terse Mac-side Codex remote replying to {user_name} through a private Telegram bot.

Act like the Codex Mac app remote-controlled from {user_name}'s phone.
Use the live Mac state and the available Codex plugins/tools when useful, including Computer Use, Browser Use, apps/connectors, image generation, and subagents if the runtime exposes them.
{user_name} has explicitly allowed local app, browser, and computer-use control for Telegram tasks when the runtime exposes those tools.
Read live state first. Act directly. Keep replies terse and concrete.
Default voice: Mac-side operator, not generic chatbot. Say what changed, what you verified, and the next human-only boundary if there is one.
Reply style: {style}. {style_instruction(style)}
Current Codex thinking mode: {mode}.
Do not reveal secrets, tokens, auth files, private logs, session transcripts, or personal content.
If a requested action is blocked by credentials, permissions, network, macOS privacy, tool availability, or mandatory safety confirmation, state the exact blocker and the next human-only step.
This Telegram chat is mapped to the Codex thread named `{thread_name}`.
{personality_note}
{image_note}

{user_name}:
{message_text}
"""


def base_codex_command(
    codex_path: str,
    model: str,
    approval: str,
    sandbox: str,
    reasoning_effort: str,
) -> list[str]:
    command = [
        codex_path,
        "exec",
        "-c",
        f'sandbox_mode="{sandbox}"',
        "-c",
        f'approval_policy="{approval}"',
        "-c",
        f'model_reasoning_effort="{reasoning_effort}"',
    ]
    if model:
        command.extend(["--model", model])
    command.append("--skip-git-repo-check")
    return command


def extract_session_id(output: str) -> str:
    match = SESSION_RE.search(output)
    return match.group(1) if match else ""


def child_pids(pid: int) -> list[int]:
    try:
        result = subprocess.run(
            ["pgrep", "-P", str(pid)],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
    except Exception:
        return []
    children = [int(line) for line in result.stdout.splitlines() if line.strip().isdigit()]
    descendants: list[int] = []
    for child in children:
        descendants.append(child)
        descendants.extend(child_pids(child))
    return descendants


def signal_pid_group(pid: int, sig: signal.Signals) -> None:
    if pid <= 0 or pid == os.getpid():
        return
    try:
        pgid = os.getpgid(pid)
    except OSError:
        pgid = 0
    if pgid > 0 and pgid != os.getpgrp():
        try:
            os.killpg(pgid, sig)
            return
        except OSError:
            pass
    try:
        os.kill(pid, sig)
    except OSError:
        pass


def signal_process(process: subprocess.Popen[str], sig: signal.Signals) -> None:
    if process.poll() is None:
        descendants = child_pids(process.pid)
        for pid in reversed(descendants):
            signal_pid_group(pid, sig)
        signal_pid_group(process.pid, sig)


def stop_process(process: subprocess.Popen[str]) -> tuple[str, str]:
    signal_process(process, signal.SIGTERM)
    try:
        return process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        signal_process(process, signal.SIGKILL)
        return process.communicate()


def run_codex(
    message_text: str,
    thread: dict[str, Any],
    image_paths: Optional[list[Path]] = None,
    cancel_event: Optional[threading.Event] = None,
    process_callback: Optional[Callable[[subprocess.Popen[str]], None]] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> tuple[str, str, dict[str, Any]]:
    session_id = str(thread.get("session_id") or "")
    image_count = len(image_paths or [])
    reasoning_effort = thread_thinking_mode(thread)
    started_at = now_iso()
    started = time.monotonic()

    def finish(
        answer: str,
        new_session_id: str,
        status: str,
        exit_code: Optional[int] = None,
    ) -> tuple[str, str, dict[str, Any]]:
        stats: dict[str, Any] = {
            "last_run_at": started_at,
            "last_latency_seconds": round(time.monotonic() - started, 1),
            "last_status": status,
            "last_image_count": image_count,
            "last_reasoning_effort": reasoning_effort,
        }
        if exit_code is not None:
            stats["last_exit_code"] = exit_code
        return answer, new_session_id, stats

    workdir = Path(str(thread.get("workdir") or default_workdir())).expanduser()
    if not workdir.exists():
        return finish(
            f"Blocked: CODEX_TELEGRAM_WORKDIR does not exist: {workdir}",
            session_id,
            "blocked",
        )

    codex_bin = os.environ.get("CODEX_BIN", "codex")
    codex_path = shutil.which(codex_bin)
    if codex_path is None:
        return finish(f"Blocked: could not find Codex CLI: {codex_bin}", session_id, "blocked")

    sandbox = os.environ.get("CODEX_TELEGRAM_SANDBOX", "danger-full-access")
    model = os.environ.get("CODEX_TELEGRAM_MODEL", "gpt-5.5").strip()
    approval = os.environ.get("CODEX_TELEGRAM_APPROVAL", "never")
    timeout = env_int("CODEX_TELEGRAM_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    thread_name = str(thread.get("name") or DEFAULT_THREAD)
    command = base_codex_command(codex_path, model, approval, sandbox, reasoning_effort)
    for image_path in image_paths or []:
        command.extend(["--image", str(image_path)])

    with tempfile.NamedTemporaryFile(prefix="codex-telegram-", delete=False) as handle:
        output_path = Path(handle.name)
    if session_id:
        command[1:2] = ["exec", "resume"]
        command.extend(["--output-last-message", str(output_path), session_id, "-"])
    else:
        command.extend(["--output-last-message", str(output_path), "-"])

    process: Optional[subprocess.Popen[str]] = None
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    returncode: Optional[int] = None
    prompt = codex_prompt(
        message_text,
        thread_name,
        image_paths,
        str(thread.get("reply_style") or reply_style_default()),
        reasoning_effort,
    )

    def reader(stream: Any, chunks: list[str]) -> None:
        try:
            for line in iter(stream.readline, ""):
                chunks.append(line)
                if progress_callback:
                    progress_callback(line)
        except Exception:
            pass
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def stop_streaming_process(target: subprocess.Popen[str]) -> None:
        signal_process(target, signal.SIGTERM)
        deadline = time.monotonic() + 5
        while target.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        if target.poll() is None:
            signal_process(target, signal.SIGKILL)

    readers: list[threading.Thread] = []
    try:
        process = subprocess.Popen(
            command,
            cwd=workdir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        if process_callback:
            process_callback(process)
        if process.stdout is not None:
            readers.append(threading.Thread(target=reader, args=(process.stdout, stdout_parts), daemon=True))
        if process.stderr is not None:
            readers.append(threading.Thread(target=reader, args=(process.stderr, stderr_parts), daemon=True))
        for item in readers:
            item.start()
        if process.stdin is not None:
            try:
                process.stdin.write(prompt)
                process.stdin.close()
            except BrokenPipeError:
                pass
        deadline = time.monotonic() + timeout
        while True:
            returncode = process.poll()
            if returncode is not None:
                break
            if cancel_event and cancel_event.is_set():
                stop_streaming_process(process)
                return finish(
                    "Canceled: job stopped before Codex replied.",
                    session_id,
                    "canceled",
                )
            if time.monotonic() >= deadline:
                stop_streaming_process(process)
                return finish(
                    f"Blocked: Codex timed out after {timeout} seconds. "
                    "The task was stopped before it could reply.",
                    session_id,
                    "timeout",
                )
            time.sleep(0.1)
        for item in readers:
            item.join(timeout=1)
        if output_path.exists():
            answer = output_path.read_text(errors="replace").strip()
        else:
            answer = ""
    except OSError as exc:
        return finish(f"Blocked: could not start Codex CLI: {exc}", session_id, "blocked")
    finally:
        try:
            output_path.unlink()
        except OSError:
            pass

    stdout = "".join(stdout_parts)
    stderr = "".join(stderr_parts)
    combined_output = "\n".join(part for part in [stdout, stderr] if part)

    if cancel_event and cancel_event.is_set():
        return finish("Canceled: job stopped before Codex replied.", session_id, "canceled")

    if returncode != 0:
        return finish(
            codex_failure_message(returncode, combined_output),
            session_id,
            "failed",
            returncode,
        )

    new_session_id = extract_session_id(combined_output) or session_id
    return finish(answer or "(Codex returned an empty final message.)", new_session_id, "ok", 0)


def command_help() -> str:
    return "\n".join(
        [
            "Commands:",
            "/ping - check the bridge",
            "/health - fast local bridge checks",
            "/jobs - show running and last run",
            "/activity - summarize running jobs, pending requests, and recent safe history",
            "/queue [text] - show or add a pending request",
            "/queue next id - move a pending request to the front",
            "/forget [id|latest|all] - remove pending request",
            "/forgetphotos [id|latest|all] - remove saved images from pending requests",
            "/watch - edit the job status message with live Codex progress",
            "/unwatch - stop live job status edits",
            "/history - show recent run receipts",
            "/cancel [job] - stop a running job",
            "/recover [restart] - run local self-recovery through scripts/recover.sh",
            "/terminal help - persistent interactive terminal sessions",
            "/file path - send a local file back to Telegram",
            "/automations - inspect Codex automations through Codex",
            "/new name - start a fresh Codex thread",
            "/use name - switch threads",
            "/list - show threads",
            "/where - show current thread and folder",
            "/cd path - set this thread's folder",
            "/think mode - set thinking mode: low, medium, high, xhigh, or default",
            "/status - show runtime state",
            "/policy - show safety boundaries",
            "/screenshot - send the Mac screen back to Telegram",
            "/latency - show last run timing and timeout",
            "/alive - show the Mac-side remote status",
            "/brief - terse replies for this thread",
            "/verbose - detailed replies for this thread",
            "/update - show local update command",
            "/capabilities - show what this remote can do",
            "/gemini [key|on|off] - configure optional mobile assist",
            "/try - show good first prompts",
            "/tools - probe Codex tool access",
            "/reset - restart the current thread",
            "",
            "Normal messages and images go to the active thread.",
        ]
    )


def launchagent_running() -> Optional[bool]:
    if sys.platform != "darwin":
        return None
    label = os.environ.get("CODEX_RELAY_LABEL", "com.codexrelay.agent")
    try:
        result = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
            stdout=subprocess.PIPE,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return False
    return "state = running" in result.stdout or re.search(r"pid = [1-9][0-9]*", result.stdout) is not None


def health_text() -> str:
    token = bool(os.environ.get("TELEGRAM_BOT_TOKEN", "").strip())
    allowed_users = parse_id_set("TELEGRAM_ALLOWED_USER_ID", "TELEGRAM_ALLOWED_USER_IDS")
    allowed_chats = parse_id_set("TELEGRAM_ALLOWED_CHAT_ID", "TELEGRAM_ALLOWED_CHAT_IDS")
    workdir = Path(os.environ.get("CODEX_TELEGRAM_WORKDIR", default_workdir())).expanduser()
    codex_bin = os.environ.get("CODEX_BIN", "codex")
    launchagent = launchagent_running()
    checks = [
        ("telegram token", token, "set", "missing"),
        ("allowlist", bool(allowed_users or allowed_chats), "configured", "missing"),
        ("codex cli", shutil.which(codex_bin) is not None, "found", "missing"),
        ("workdir", workdir.exists() and workdir.is_dir(), str(workdir), f"missing: {workdir}"),
        (
            "launchagent",
            launchagent is not False,
            "running" if launchagent else "unknown",
            "not running",
        ),
        ("reply style", True, reply_style_default(), ""),
        (
            "gemini",
            True,
            f"enabled; {gemini_model()}" if gemini_enabled() else "disabled",
            "",
        ),
        (
            "model",
            True,
            os.environ.get("CODEX_TELEGRAM_MODEL", "gpt-5.5"),
            "",
        ),
        (
            "thinking mode",
            True,
            thinking_mode_default(),
            "",
        ),
    ]
    lines = ["health:"]
    for label, ok, good, bad in checks:
        status = "ok" if ok else "warn"
        value = good if ok else bad
        lines.append(f"- {label}: {status} ({value})")
    lines.append("deep check: /tools")
    return "\n".join(lines)


def status_text(thread: dict[str, Any], chat_id: Optional[int] = None) -> str:
    session_status = "started" if thread.get("session_id") else "new"
    running = jobs_for_chat(chat_id) if chat_id is not None else []
    lines = [
        f"thread: {thread.get('name', DEFAULT_THREAD)} ({session_status})",
        f"folder: {thread.get('workdir', default_workdir())}",
        f"model: {os.environ.get('CODEX_TELEGRAM_MODEL', 'gpt-5.5')}",
        f"thinking mode: {thinking_mode_status(thread)}",
        f"reply style: {thread.get('reply_style') or reply_style_default()}",
        f"sandbox: {os.environ.get('CODEX_TELEGRAM_SANDBOX', 'danger-full-access')}",
        f"approval: {os.environ.get('CODEX_TELEGRAM_APPROVAL', 'never')}",
        f"timeout: {env_int('CODEX_TELEGRAM_TIMEOUT_SECONDS', DEFAULT_TIMEOUT_SECONDS)}s",
        f"reply threading: {'enabled' if env_bool('CODEX_TELEGRAM_REPLY_TO_MESSAGES', False) else 'disabled'}",
        f"group chats: {'enabled' if env_bool('CODEX_TELEGRAM_ALLOW_GROUP_CHATS', False) else 'disabled'}",
        f"typing interval: {max(1, env_int('CODEX_TELEGRAM_TYPING_INTERVAL_SECONDS', 4))}s",
        f"live job updates: {'on' if progress_enabled(thread) else 'off'}",
        f"telegram images: enabled; max {max_images_per_message()}",
        f"file transfer max: {max_file_transfer_bytes()} bytes",
        f"gemini assist: {'enabled' if gemini_enabled() else 'disabled'}",
        f"terminals: {len(terminal_list(chat_id)) if chat_id is not None else 0}",
        f"running jobs: {len(running)}",
        f"pending requests: {len(pending_requests(thread))}",
    ]
    lines.extend(last_run_lines(thread))
    if running:
        lines.append("send /jobs for elapsed time or /cancel job-id")
    return "\n".join(lines)


def alive_text(thread: dict[str, Any]) -> str:
    session_status = "started" if thread.get("session_id") else "new"
    return "\n".join(
        [
            "Codex Relay is live.",
            f"uptime: {duration_text(time.time() - STARTED_AT)}",
            f"thread: {thread.get('name', DEFAULT_THREAD)} ({session_status})",
            f"folder: {thread.get('workdir', default_workdir())}",
            f"model: {os.environ.get('CODEX_TELEGRAM_MODEL', 'gpt-5.5')}",
            f"thinking: {thinking_mode_status(thread)}",
            f"style: {thread.get('reply_style') or reply_style_default()}",
            "remote: Telegram -> LaunchAgent -> Codex CLI -> this Mac",
            "next: send /tools, /try, or a normal task.",
        ]
    )


def last_run_lines(thread: dict[str, Any]) -> list[str]:
    latency = thread.get("last_latency_seconds")
    status = str(thread.get("last_status") or "")
    if latency is None and not status:
        return ["last run: none"]
    pieces = [status or "unknown"]
    if latency is not None:
        pieces.append(f"{latency}s")
    image_count = int_or_none(thread.get("last_image_count"))
    if image_count:
        image_label = "image" if image_count == 1 else "images"
        pieces.append(f"{image_count} {image_label}")
    if thread.get("last_reasoning_effort"):
        pieces.append(str(thread["last_reasoning_effort"]))
    lines = [f"last run: {'; '.join(pieces)}"]
    if thread.get("last_run_at"):
        lines.append(f"last run at: {thread['last_run_at']}")
    return lines


def job_line(job: RelayJob) -> str:
    image_count = job.image_count
    image_note = ""
    if image_count:
        image_label = "image" if image_count == 1 else "images"
        image_note = f"; {image_count} {image_label}"
    phase, _revision, lines, _message_id = job.progress_snapshot()
    useful_lines = [line for line in lines if progress_line_displayable(line)]
    latest = f"; progress: {useful_lines[-1]}" if useful_lines else ""
    request = f"; request: {job.request_preview}" if job.request_preview else ""
    return f"{job.id}: {job.thread_name}; {phase}; running {job.elapsed()}{image_note}{request}{latest}"


def jobs_text(chat_id: int, thread: dict[str, Any]) -> str:
    running = jobs_for_chat(chat_id)
    lines = ["running jobs:"]
    if running:
        for job in sorted(running, key=lambda item: item.started_at):
            lines.append(f"- {job_line(job)}")
        lines.append("cancel: /cancel job-id")
        lines.append(f"live updates: {'on' if progress_enabled(thread) else 'off'}")
    else:
        lines.append("- none")
    pending_count = len(pending_requests(thread))
    if pending_count:
        lines.append(f"pending: {pending_count}")
    lines.extend(last_run_lines(thread))
    return "\n".join(lines)


def busy_thread_message(chat_id: int, thread_name: str) -> str:
    running = jobs_for_thread(chat_id, thread_name)
    if not running:
        return ""
    lines = [f"Thread `{thread_name}` is busy."]
    lines.extend(f"- {job_line(job)}" for job in running)
    lines.append("Wait for it, or cancel with /cancel job-id.")
    return "\n".join(lines)


def latency_text(thread: dict[str, Any]) -> str:
    lines = [
        "latency:",
        "- /ping, /alive, /status: immediate bridge replies",
        "- Codex tasks: local Codex runtime + tool work + Telegram delivery",
        f"- timeout: {env_int('CODEX_TELEGRAM_TIMEOUT_SECONDS', DEFAULT_TIMEOUT_SECONDS)}s",
    ]
    lines.extend(last_run_lines(thread))
    return "\n".join(lines)


def set_reply_style_text(thread: dict[str, Any], style: str) -> str:
    thread["reply_style"] = style
    thread["updated_at"] = now_iso()
    if style == "verbose":
        return "Reply style: verbose"
    return "Reply style: brief"


def history_text(chat_id: int) -> str:
    events = [event for event in read_history(12) if event.get("chat_id") == chat_id]
    if not events:
        return "history: none"
    lines = ["history:"]
    for event in events[-8:]:
        pieces = [
            str(event.get("status", "unknown")),
            str(event.get("thread", DEFAULT_THREAD)),
        ]
        if event.get("latency_seconds") is not None:
            pieces.append(f"{event['latency_seconds']}s")
        if event.get("image_count"):
            image_count = int_or_none(event.get("image_count")) or 0
            image_label = "image" if image_count == 1 else "images"
            pieces.append(f"{image_count} {image_label}")
        if event.get("folder"):
            pieces.append(str(event["folder"]))
        lines.append("- " + "; ".join(pieces))
    return "\n".join(lines)


def concise_external_error(service: str, exc: BaseException) -> str:
    detail = str(exc).strip()
    lowered = detail.lower()
    gateway_terms = ("gateway", "502", "503", "504", "unavailable", "timed out", "timeout")
    if any(term in lowered for term in gateway_terms):
        return f"{service} gateway looks down or unreachable right now."
    if "network" in lowered or "connection" in lowered:
        return f"{service} network call failed."
    if "429" in lowered or "rate" in lowered:
        return f"{service} is rate limited right now."
    if not detail:
        return f"{service} failed without a readable error."
    clean = sanitize_progress_line(detail)
    if not clean:
        return f"{service} failed. I hid the raw error because it may contain private details."
    return f"{service} failed: {clean[:240]}"


def codex_failure_message(returncode: int, output: str) -> str:
    lowered = output.lower()
    if any(term in lowered for term in ("gateway", "bad gateway", "502", "503", "504", "service unavailable")):
        return (
            "Codex gateway error: Telegram is reachable, but the local Codex CLI could not reach "
            "its backend. Wait a bit and retry. If local relay health also looks wrong, send /recover."
        )
    if any(term in lowered for term in ("network", "connection reset", "connection refused", "timed out", "timeout")):
        return (
            "Codex network error: Telegram is reachable, but the local Codex CLI could not complete "
            "its backend connection. Check the Mac network or retry. For local relay diagnostics, send /recover."
        )
    if any(term in lowered for term in ("rate limit", "429", "quota")):
        return "Codex rate limit or quota error. The relay is alive; retry after the account limit clears."
    return f"Codex failed with exit {returncode}. Run local diagnostics with ./scripts/doctor.sh or send /recover."


def activity_snapshot_text(chat_id: int, thread: dict[str, Any]) -> str:
    running = jobs_for_chat(chat_id)
    lines = [
        "activity:",
        f"thread: {thread.get('name', DEFAULT_THREAD)}",
        f"folder: {thread.get('workdir', default_workdir())}",
        f"thinking: {thinking_mode_status(thread)}",
    ]
    if running:
        lines.append("running:")
        for job in sorted(running, key=lambda item: item.started_at):
            lines.append(f"- {job_line(job)}")
    else:
        lines.append("running: none")
    sessions = terminal_list(chat_id)
    if sessions:
        lines.append("terminals:")
        for session in sessions:
            lines.append(f"- {session.name}: running {session.elapsed()}; cwd={session.cwd}")
    else:
        lines.append("terminals: none")
    pending = pending_queue_text(thread)
    lines.append(pending)
    history = history_text(chat_id)
    if history != "history: none":
        lines.append(history)
    lines.extend(last_run_lines(thread))
    return "\n".join(lines)


def activity_text(chat_id: int, thread: dict[str, Any]) -> str:
    snapshot = activity_snapshot_text(chat_id, thread)
    if not gemini_enabled() or not gemini_allows_text(snapshot):
        return snapshot
    prompt = f"""Summarize this Codex Relay activity for a private Telegram user.

Rules:
- Do not add facts.
- Do not ask for secrets.
- Keep it short and useful on a phone.
- Say whether Codex is currently running, what is queued, and what the safest next command is.

Relay activity:
{snapshot}
"""
    try:
        summary = gemini_generate(prompt).strip()
    except Exception as exc:
        return snapshot + "\n\n" + concise_external_error("Gemini", exc)
    return summary or snapshot


def job_ack_text(job: RelayJob) -> str:
    lines = [
        f"I'm on it: job {job.id}",
        f"thread: {job.thread_name}",
    ]
    if job.request_preview:
        lines.append(f"request: {job.request_preview}")
    lines.append("status: running")
    if job.image_count:
        image_label = "image" if job.image_count == 1 else "images"
        lines.append(f"attachments: {job.image_count} {image_label}")
    lines.append("check: /jobs")
    lines.append("live updates: /watch")
    lines.append(f"stop: /cancel {job.id}")
    return "\n".join(lines)


def cancel_text(chat_id: int, arg: str) -> str:
    job_id = arg.strip()
    if job_id:
        job = find_job(chat_id, job_id)
        if not job:
            return f"No running job: {job_id}"
        job.cancel()
        return f"Cancel requested: {job.id}"

    running = jobs_for_chat(chat_id)
    if not running:
        return "No running jobs."
    if len(running) > 1:
        return "Multiple jobs running. Use /cancel job-id."
    running[0].cancel()
    return f"Cancel requested: {running[0].id}"


def recovery_timeout_seconds() -> int:
    return max(60, env_int("CODEX_RELAY_RECOVERY_TIMEOUT_SECONDS", 1200))


def relay_repo_dir() -> Path:
    raw = os.environ.get("CODEX_RELAY_REPO_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    runtime_parent = ROOT.parent
    if (runtime_parent / "codex_relay.py").exists() and (runtime_parent / "scripts").exists():
        return runtime_parent.resolve()
    return ROOT


def relay_env_update_paths() -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    candidates = [ENV_PATH]
    repo_env = relay_repo_dir() / ".env"
    if repo_env != ENV_PATH and repo_env.exists():
        candidates.append(repo_env)
    for path in candidates:
        resolved = path.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        paths.append(resolved)
    return paths


def persist_relay_env_updates(updates: dict[str, str]) -> None:
    for path in relay_env_update_paths():
        update_private_env_file(path, updates)
    for key, value in updates.items():
        os.environ[key] = value


def valid_gemini_api_key(value: str) -> bool:
    candidate = value.strip()
    if not candidate or any(ch.isspace() for ch in candidate):
        return False
    if len(candidate) > 256:
        return False
    return GEMINI_API_KEY_RE.fullmatch(candidate) is not None


def extract_gemini_api_key(value: str) -> str:
    match = GEMINI_API_KEY_RE.search(value)
    if match:
        return match.group(1)
    candidate = value.strip()
    if valid_gemini_api_key(candidate):
        return candidate
    return ""


def delete_secret_message(api: TelegramAPI, chat_id: int, message_id: Optional[int]) -> None:
    if message_id is None:
        return
    try:
        api.delete_message(chat_id, int(message_id))
    except Exception:
        pass


def set_gemini_assist(
    api_key: Optional[str] = None,
    enabled: Optional[bool] = None,
    force_mobile_defaults: bool = False,
) -> None:
    updates: dict[str, str] = {}
    if api_key is not None:
        updates["CODEX_RELAY_GEMINI_API_KEY"] = api_key
    if enabled is not None:
        updates["CODEX_RELAY_GEMINI_ENABLED"] = "true" if enabled else "false"
    if force_mobile_defaults:
        updates["CODEX_RELAY_GEMINI_NATURAL_COMMANDS"] = "true"
        updates["CODEX_RELAY_GEMINI_POLISH"] = "true"
    if updates:
        persist_relay_env_updates(updates)


def gemini_status_text() -> str:
    lines = [
        "Gemini assist:",
        f"- status: {'enabled' if gemini_enabled() else 'disabled'}",
        f"- model: {gemini_model()}",
        f"- max output tokens: {gemini_max_output_tokens()}",
        f"- natural commands: {'enabled' if gemini_natural_commands_enabled() else 'disabled'}",
        f"- polish: {'enabled' if gemini_polish_enabled() else 'disabled'}",
    ]
    if gemini_configured():
        lines.append("- key: configured")
        lines.append("- controls: /gemini on, /gemini off, /gemini clear")
    else:
        lines.append("- setup: /gemini key YOUR_GEMINI_API_KEY")
    lines.append("- reload: immediate; no Mac-side restart needed")
    return "\n".join(lines)


def gemini_command_text(
    api: TelegramAPI,
    chat_id: int,
    message_id: Optional[int],
    arg: str,
) -> str:
    raw = arg.strip()
    if not raw or raw.lower() in {"status", "help"}:
        return gemini_status_text()

    command, _, rest = raw.partition(" ")
    action = command.lower()

    if valid_gemini_api_key(raw):
        action = "key"
        rest = raw

    if action in {"key", "set", "setup"}:
        api_key = extract_gemini_api_key(rest)
        if not api_key:
            return "Usage: /gemini key YOUR_GEMINI_API_KEY"
        set_gemini_assist(api_key, True, True)
        delete_secret_message(api, chat_id, message_id)
        return "Gemini assist enabled. Key saved privately and loaded in this running relay."

    if action in {"on", "enable"}:
        api_key = extract_gemini_api_key(rest)
        if api_key:
            set_gemini_assist(api_key, True, True)
            delete_secret_message(api, chat_id, message_id)
            return "Gemini assist enabled. Key saved privately and loaded in this running relay."
        if not gemini_configured():
            return "Missing Gemini API key. Send /gemini key YOUR_GEMINI_API_KEY."
        set_gemini_assist(enabled=True, force_mobile_defaults=True)
        return "Gemini assist enabled and reloaded."

    if action in {"off", "disable"}:
        set_gemini_assist(enabled=False)
        return "Gemini assist disabled."

    if action in {"clear", "remove", "forget"}:
        set_gemini_assist("", False)
        return "Gemini assist key cleared and disabled."

    return "Unknown Gemini command. Use /gemini, /gemini key YOUR_GEMINI_API_KEY, /gemini on, or /gemini off."


def recovery_script_path() -> Path:
    raw = os.environ.get("CODEX_RELAY_RECOVERY_SCRIPT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    repo_script = relay_repo_dir() / "scripts" / "recover.sh"
    if repo_script.exists():
        return repo_script
    return ROOT / "scripts" / "recover.sh"


def sanitize_shell_output(output: str, limit: int = 3600) -> str:
    safe_lines: list[str] = []
    for line in output.splitlines():
        clean = sanitize_progress_line(line)
        if clean:
            safe_lines.append(clean)
    text = "\n".join(safe_lines).strip()
    if not text:
        return "(no safe output)"
    if len(text) > limit:
        text = text[-limit:].lstrip()
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        text = "(tail)\n" + text
    return text


def run_recovery_command(job: RelayJob, arg: str) -> tuple[str, int]:
    script = recovery_script_path()
    if not script.exists():
        return f"Recovery script missing: {script}", 127
    command = ["/bin/zsh", str(script)]
    if arg.strip():
        command.extend(arg.strip().split())
    env = os.environ.copy()
    env.setdefault("CODEX_RELAY_REPO_DIR", str(relay_repo_dir()))
    timeout = recovery_timeout_seconds()
    started = time.monotonic()
    output_parts: list[str] = []
    try:
        process = subprocess.Popen(
            command,
            cwd=relay_repo_dir(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            start_new_session=True,
        )
    except OSError as exc:
        return f"Could not start recovery script: {exc}", 126
    job.set_process(process)

    def reader() -> None:
        if process.stdout is None:
            return
        try:
            for line in iter(process.stdout.readline, ""):
                output_parts.append(line)
                job.add_progress(line)
        except Exception:
            pass
        finally:
            try:
                process.stdout.close()
            except Exception:
                pass

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()
    while process.poll() is None:
        if job.cancel_event.is_set():
            signal_process(process, signal.SIGTERM)
            return "Canceled: recovery stopped before it finished.", 130
        if time.monotonic() - started >= timeout:
            signal_process(process, signal.SIGTERM)
            return f"Recovery timed out after {timeout} seconds.", 124
        time.sleep(0.1)
    reader_thread.join(timeout=1)
    return sanitize_shell_output("".join(output_parts)), int(process.returncode or 0)


def run_recovery_worker(
    api: TelegramAPI,
    chat_id: int,
    job: RelayJob,
    arg: str,
) -> None:
    try:
        with TypingPulse(api, chat_id), ProgressPulse(api, chat_id, job, True):
            output, exit_code = run_recovery_command(job, arg)
        if exit_code == 0:
            api.send_message(chat_id, "Recovery finished.\n\n" + output)
        else:
            api.send_message(chat_id, f"Recovery failed with exit {exit_code}.\n\n{output}")
    except Exception as exc:
        api.send_message(chat_id, "Recovery failed: " + concise_external_error("local recovery", exc))
    finally:
        finish_job(job)
        cleanup_workers()


def start_recovery_job(
    api: TelegramAPI,
    chat_id: int,
    arg: str,
    reply_to_message_id: Optional[int] = None,
) -> None:
    running = jobs_for_thread(chat_id, "recovery")
    if running:
        api.send_message(chat_id, "Recovery is already running.\n" + "\n".join(job_line(job) for job in running), reply_to_message_id)
        return
    job = RelayJob(chat_id, "recovery", 0, f"/recover {arg}".strip())
    job.set_status_message(api.send_message(chat_id, job_ack_text(job), reply_to_message_id))
    register_job(job)
    worker = threading.Thread(
        target=run_recovery_worker,
        args=(api, chat_id, job, arg),
        daemon=False,
    )
    register_worker(worker)
    try:
        worker.start()
    except Exception:
        finish_job(job)
        cleanup_workers()
        raise


def history_event_from_stats(
    chat_id: int,
    thread_name: str,
    thread: dict[str, Any],
    job: RelayJob,
    stats: dict[str, Any],
) -> dict[str, Any]:
    folder = Path(str(thread.get("workdir") or default_workdir())).expanduser()
    return {
        "at": now_iso(),
        "chat_id": chat_id,
        "thread": thread_name,
        "status": stats.get("last_status"),
        "latency_seconds": stats.get("last_latency_seconds"),
        "image_count": stats.get("last_image_count"),
        "reasoning_effort": stats.get("last_reasoning_effort"),
        "exit_code": stats.get("last_exit_code"),
        "job_id": job.id,
        "folder": folder.name or str(folder),
    }


def record_run_stats(thread: dict[str, Any], stats: dict[str, Any]) -> None:
    for key in [
        "last_run_at",
        "last_latency_seconds",
        "last_status",
        "last_exit_code",
        "last_image_count",
        "last_reasoning_effort",
    ]:
        if key in stats:
            thread[key] = stats[key]


def run_job_worker(
    api: TelegramAPI,
    chat_id: int,
    threads_path: Path,
    thread_name: str,
    prompt_text: str,
    thread_snapshot: dict[str, Any],
    image_paths: list[Path],
    job: RelayJob,
    persist_thread_state: bool = True,
    record_history: bool = True,
) -> None:
    try:
        with TypingPulse(api, chat_id), ProgressPulse(api, chat_id, job, progress_enabled(thread_snapshot)):
            answer, session_id, stats = run_codex(
                prompt_text,
                thread_snapshot,
                image_paths,
                job.cancel_event,
                job.set_process,
                job.add_progress,
            )
        if persist_thread_state:
            with THREADS_LOCK:
                data = read_threads(threads_path)
                thread = ensure_thread(data, chat_id, thread_name)
                if session_id:
                    thread["session_id"] = session_id
                record_run_stats(thread, stats)
                thread["updated_at"] = now_iso()
                write_threads(threads_path, data)
        else:
            thread = dict(thread_snapshot)
        if record_history:
            append_history_event(
                history_event_from_stats(chat_id, thread_name, thread, job, stats)
            )
        if stats.get("last_status") == "ok":
            answer = gemini_polish_answer(prompt_text, answer, thread)
        api.send_message(chat_id, answer)
    except Exception as exc:
        append_history_event(
            {
                "at": now_iso(),
                "chat_id": chat_id,
                "thread": thread_name,
                "status": "relay-failed",
                "job_id": job.id,
                "folder": Path(str(thread_snapshot.get("workdir") or default_workdir())).name,
            }
        )
        api.send_message(chat_id, f"Relay job failed: {exc}")
    finally:
        finish_job(job)
        cleanup_workers()
        if persist_thread_state:
            start_next_pending_job(api, chat_id, threads_path, thread_name)


def start_background_job(
    api: TelegramAPI,
    chat_id: int,
    threads_path: Path,
    thread_name: str,
    thread: dict[str, Any],
    prompt_text: str,
    image_paths: Optional[list[Path]] = None,
    reply_to_message_id: Optional[int] = None,
    persist_thread_state: bool = True,
    record_history: bool = True,
) -> None:
    image_paths = image_paths or []
    running_thread_jobs = jobs_for_thread(chat_id, thread_name)
    if running_thread_jobs:
        api.send_message(
            chat_id,
            "Already working on this thread.\n"
            + "\n".join(job_line(job) for job in running_thread_jobs),
            reply_to_message_id,
        )
        return
    job = RelayJob(chat_id, thread_name, len(image_paths), prompt_text)
    try:
        job.set_status_message(api.send_message(chat_id, job_ack_text(job), reply_to_message_id))
    except Exception:
        finish_job(job)
        raise
    register_job(job)
    worker = threading.Thread(
        target=run_job_worker,
        args=(
            api,
            chat_id,
            threads_path,
            thread_name,
            prompt_text,
            dict(thread),
            image_paths,
            job,
            persist_thread_state,
            record_history,
        ),
        daemon=False,
    )
    register_worker(worker)
    try:
        worker.start()
    except Exception:
        finish_job(job)
        cleanup_workers()
        raise


def start_next_pending_job(
    api: TelegramAPI,
    chat_id: int,
    threads_path: Path,
    thread_name: str,
) -> None:
    if jobs_for_thread(chat_id, thread_name):
        return
    with THREADS_LOCK:
        data = read_threads(threads_path)
        thread = ensure_thread(data, chat_id, thread_name)
        item = pop_next_pending_request(thread)
        if item is None:
            return
        thread["updated_at"] = now_iso()
        write_threads(threads_path, data)
        thread_snapshot = dict(thread)
    try:
        image_paths = pending_paths_for_codex(item)
        image_count = len(image_paths)
        image_note = ""
        if image_count:
            image_label = "image" if image_count == 1 else "images"
            image_note = f" with {image_count} {image_label}"
        api.send_message(chat_id, f"Starting queued request {item['id']}{image_note}: {prompt_preview(item['prompt'])}")
        start_background_job(
            api,
            chat_id,
            threads_path,
            thread_name,
            thread_snapshot,
            item["prompt"],
            image_paths,
        )
    except Exception:
        pass


def capabilities_text() -> str:
    return "\n".join(
        [
            "Codex Relay can:",
            "- run Codex on this Mac from Telegram",
            "- keep named Codex threads with separate folders",
            "- inspect and edit local repos/files",
            "- run tests, scripts, git, and shell commands",
            "- read Telegram photo and image-document attachments",
            "- send a current Mac screenshot back to Telegram with /screenshot",
            "- send local files back to Telegram with /file",
            "- keep persistent interactive terminal sessions with /terminal",
            "- use Computer Use, Browser Use, apps/connectors, images, and subagents when your Codex runtime exposes them",
            "- inspect Codex automations with /automations",
            "- operate local app/browser sessions when macOS permissions and logins allow it",
            "- draft public messages, commits, and posts, then stop at the confirmation boundary",
            "",
            "It cannot bypass logins, MFA, macOS privacy prompts, Codex limits, or mandatory safety confirmations.",
        ]
    )


def policy_text() -> str:
    return "\n".join(
        [
            "Policy:",
            "- allowed: local repo/file/test/shell work inside your configured Codex sandbox",
            "- allowed: Telegram images, /screenshot, /file, /terminal, named threads, local status, and automations inspection",
            "- stops before: public posts, messages to people, account/security changes, payments, purchases, deletes, or medical/legal/financial submissions",
            "- cannot bypass: logins, MFA, CAPTCHAs, macOS privacy prompts, site safety barriers, Codex/OpenAI limits, or required confirmations",
            "- bot access: only the allow-listed Telegram user/chat can run tasks",
        ]
    )


def try_text() -> str:
    return "\n".join(
        [
            "Good first prompts:",
            "1. /screenshot",
            "2. /new school",
            "   check the app or browser state I already have open and summarize the next action",
            "3. /new repo",
            "   /cd Projects/my-repo",
            "   read this repo and make the README more impressive without pushing",
            "4. send a screenshot/photo and ask what I should do next",
            "5. use available local tools to tell me what apps are open and what looks unfinished",
            "6. /terminal open setup -- gh auth login",
            "   /terminal read setup",
            "7. /file README.md",
        ]
    )


def update_text() -> str:
    return "\n".join(
        [
            "Update on the Mac:",
            "cd path/to/codex-relay",
            "./scripts/update.sh",
            "",
            "That pulls latest, reinstalls the LaunchAgent, and runs doctor.",
        ]
    )


def builtin_natural_control(
    api: TelegramAPI,
    chat_id: int,
    message_id: Optional[int],
    threads_path: Path,
    text: str,
    prefix: str = "",
) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return False
    gemini_key = extract_gemini_api_key(text)
    if gemini_key:
        set_gemini_assist(gemini_key, True, True)
        delete_secret_message(api, chat_id, message_id)
        reply = "Gemini assist enabled. Key saved privately and loaded in this running relay."
        api.send_message(chat_id, "\n\n".join(part for part in [prefix, reply] if part), None)
        return True
    if any(phrase in lowered for phrase in ("what's going on", "what is going on", "what are you doing", "where are we")):
        with THREADS_LOCK:
            _data, _active_name, thread = active_state(threads_path, chat_id)
        reply = activity_snapshot_text(chat_id, thread)
        api.send_message(chat_id, "\n\n".join(part for part in [prefix, reply] if part), message_id)
        return True

    mode_match = re.search(r"\b(low|medium|normal|high|deep|xhigh|x-high|extra-high|default)\b", lowered)
    if mode_match and any(word in lowered for word in ("think", "thinking", "reasoning")):
        try:
            with THREADS_LOCK:
                data, _active_name, thread = active_state(threads_path, chat_id)
                reply = set_thinking_mode_text(thread, mode_match.group(1))
                write_threads(threads_path, data)
        except ValueError as exc:
            api.send_message(chat_id, "\n\n".join(part for part in [prefix, str(exc)] if part), message_id)
            return True
        api.send_message(chat_id, "\n\n".join(part for part in [prefix, reply] if part), message_id)
        return True

    forget_words = ("never mind", "nevermind", "forget that", "drop that", "ignore that")
    if any(phrase in lowered for phrase in forget_words):
        with THREADS_LOCK:
            data, _active_name, thread = active_state(threads_path, chat_id)
            if any(word in lowered for word in ("photo", "photos", "image", "images", "pic", "pics")):
                changed, deleted = remove_pending_images(thread, "latest")
                write_threads(threads_path, data)
                if changed:
                    image_label = "image" if deleted == 1 else "images"
                    reply = f"Removed {deleted} saved {image_label} from pending: " + ", ".join(item["id"] for item in changed)
                else:
                    reply = "No pending images matched."
            else:
                removed = remove_pending_request(thread, "latest")
                write_threads(threads_path, data)
                reply = "Removed pending: " + ", ".join(item["id"] for item in removed) if removed else "No pending request matched."
        api.send_message(chat_id, "\n\n".join(part for part in [prefix, reply] if part), message_id)
        return True

    return False


def handle_message(
    api: TelegramAPI,
    message: dict[str, Any],
    allowed_users: set[int],
    allowed_chats: set[int],
    threads_path: Path,
) -> None:
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    chat_id = int_or_none(chat.get("id"))
    if chat_id is None:
        return
    chat_type = str(chat.get("type") or "private")
    user_id = sender.get("id")
    if user_id is not None:
        user_id = int_or_none(user_id)
    message_id = message.get("message_id")
    text = (message.get("text") or message.get("caption") or "").strip()
    image_specs = image_attachment_specs(message)

    allow_group_chats = env_bool("CODEX_TELEGRAM_ALLOW_GROUP_CHATS", False)
    if chat_type != "private" and not allow_group_chats:
        return

    enrollment_mode = not allowed_users and not allowed_chats
    if enrollment_mode:
        if chat_type != "private":
            return
        api.send_message(
            chat_id,
            "Enrollment mode. I will not run Codex yet.\n"
            f"Telegram user ID: {user_id}\n"
            f"Telegram chat ID: {chat_id}\n\n"
            "Paste the user ID into TELEGRAM_ALLOWED_USER_ID in .env and restart me.",
            message_id,
        )
        return

    if not authorized(user_id, chat_id, chat_type, allowed_users, allowed_chats):
        if env_bool("CODEX_TELEGRAM_REPLY_UNAUTHORIZED", False):
            api.send_message(chat_id, "Not authorized.", message_id)
        return

    if not text and not image_specs:
        return

    command, _, arg = text.partition(" ")
    command = command.lower()

    if command == "/ping":
        api.send_message(chat_id, "online", message_id)
        return
    if command == "/health":
        api.send_message(chat_id, health_text(), message_id)
        return
    if command == "/id":
        api.send_message(chat_id, f"Telegram user ID: {user_id}\nTelegram chat ID: {chat_id}", message_id)
        return
    if command in {"/help", "/start"}:
        api.send_message(chat_id, command_help(), message_id)
        return

    with THREADS_LOCK:
        data, active_name, _active_thread = active_state(threads_path, chat_id)

    if command == "/new":
        try:
            name = normalize_thread_name(arg)
        except ValueError as exc:
            api.send_message(chat_id, str(exc), message_id)
            return
        with THREADS_LOCK:
            data, _active_name, _active_thread = active_state(threads_path, chat_id)
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
        with THREADS_LOCK:
            data, _active_name, _active_thread = active_state(threads_path, chat_id)
            threads = chat_threads(data, chat_id)
            if name not in threads:
                api.send_message(chat_id, f"No thread named `{name}`. Use `/new {name}`.", message_id)
                return
            set_active_thread(data, chat_id, name)
            write_threads(threads_path, data)
        api.send_message(chat_id, f"Using thread: {name}", message_id)
        return

    if command in {"/list", "/threads"}:
        with THREADS_LOCK:
            data, active_name, _active_thread = active_state(threads_path, chat_id)
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
        with THREADS_LOCK:
            _data, active_name, thread = active_state(threads_path, chat_id)
        status = "started" if thread.get("session_id") else "new"
        api.send_message(chat_id, f"{active_name} ({status})\n{thread.get('workdir')}", message_id)
        return

    if command in {"/cd", "/repo"}:
        with THREADS_LOCK:
            data, active_name, thread = active_state(threads_path, chat_id)
            current_workdir = str(thread.get("workdir") or default_workdir())
        busy = busy_thread_message(chat_id, active_name)
        if busy:
            api.send_message(chat_id, busy, message_id)
            return
        try:
            path = resolve_workdir(arg, current_workdir)
        except ValueError as exc:
            api.send_message(chat_id, str(exc), message_id)
            return
        with THREADS_LOCK:
            data, active_name, thread = active_state(threads_path, chat_id)
            thread["workdir"] = str(path)
            thread["updated_at"] = now_iso()
            write_threads(threads_path, data)
        api.send_message(chat_id, f"Folder set:\n{path}", message_id)
        return

    if command == "/home":
        path = Path.home()
        with THREADS_LOCK:
            data, active_name, thread = active_state(threads_path, chat_id)
        busy = busy_thread_message(chat_id, active_name)
        if busy:
            api.send_message(chat_id, busy, message_id)
            return
        with THREADS_LOCK:
            data, active_name, thread = active_state(threads_path, chat_id)
            thread["workdir"] = str(path)
            thread["updated_at"] = now_iso()
            write_threads(threads_path, data)
        api.send_message(chat_id, f"Folder set:\n{path}", message_id)
        return

    if command == "/status":
        with THREADS_LOCK:
            _data, _active_name, thread = active_state(threads_path, chat_id)
        api.send_message(chat_id, status_text(thread, chat_id), message_id)
        return

    if command in {"/activity", "/now", "/what"}:
        with THREADS_LOCK:
            _data, _active_name, thread = active_state(threads_path, chat_id)
        api.send_message(chat_id, activity_text(chat_id, thread), message_id)
        return

    if command == "/latency":
        with THREADS_LOCK:
            _data, _active_name, thread = active_state(threads_path, chat_id)
        api.send_message(chat_id, latency_text(thread), message_id)
        return

    if command in {"/brief", "/terse"}:
        with THREADS_LOCK:
            data, _active_name, thread = active_state(threads_path, chat_id)
            reply = set_reply_style_text(thread, "brief")
            write_threads(threads_path, data)
        api.send_message(chat_id, reply, message_id)
        return

    if command == "/verbose":
        with THREADS_LOCK:
            data, _active_name, thread = active_state(threads_path, chat_id)
            reply = set_reply_style_text(thread, "verbose")
            write_threads(threads_path, data)
        api.send_message(chat_id, reply, message_id)
        return

    if command in {"/think", "/thinking", "/reasoning"}:
        with THREADS_LOCK:
            data, _active_name, thread = active_state(threads_path, chat_id)
            if not arg.strip():
                reply = thinking_mode_help_text(thread)
            else:
                try:
                    reply = set_thinking_mode_text(thread, arg)
                except ValueError as exc:
                    api.send_message(chat_id, str(exc), message_id)
                    return
                write_threads(threads_path, data)
        api.send_message(chat_id, reply, message_id)
        return

    if command in {"/watch", "/subscribe"}:
        with THREADS_LOCK:
            data, _active_name, thread = active_state(threads_path, chat_id)
            reply = set_progress_updates_text(thread, True)
            write_threads(threads_path, data)
        api.send_message(chat_id, reply, message_id)
        return

    if command in {"/unwatch", "/unsubscribe"}:
        with THREADS_LOCK:
            data, _active_name, thread = active_state(threads_path, chat_id)
            reply = set_progress_updates_text(thread, False)
            write_threads(threads_path, data)
        api.send_message(chat_id, reply, message_id)
        return

    if command in {"/queue", "/pending"}:
        queue_arg = arg.strip()
        if not queue_arg:
            with THREADS_LOCK:
                _data, _active_name, thread = active_state(threads_path, chat_id)
            api.send_message(chat_id, pending_queue_text(thread), message_id)
            return
        if queue_arg.lower().startswith("next "):
            selector = queue_arg[5:].strip() or "latest"
            try:
                with THREADS_LOCK:
                    data, _active_name, thread = active_state(threads_path, chat_id)
                    item = prioritize_pending_request(thread, selector)
                    write_threads(threads_path, data)
            except ValueError as exc:
                api.send_message(chat_id, str(exc), message_id)
                return
            api.send_message(chat_id, f"Next up: {item['id']}: {prompt_preview(item['prompt'])}", message_id)
            return
        try:
            with THREADS_LOCK:
                data, _active_name, thread = active_state(threads_path, chat_id)
                item = queue_pending_request(thread, queue_arg)
                write_threads(threads_path, data)
        except ValueError as exc:
            api.send_message(chat_id, str(exc), message_id)
            return
        api.send_message(chat_id, f"Queued request {item['id']}: {prompt_preview(item['prompt'])}", message_id)
        return

    if command in {"/forget", "/dequeue"}:
        with THREADS_LOCK:
            data, _active_name, thread = active_state(threads_path, chat_id)
            removed = remove_pending_request(thread, arg)
            write_threads(threads_path, data)
        if removed:
            reply = "Removed pending: " + ", ".join(item["id"] for item in removed)
        else:
            reply = "No pending request matched."
        api.send_message(chat_id, reply, message_id)
        return

    if command in {"/forgetphotos", "/dropimages", "/dropphotos"}:
        with THREADS_LOCK:
            data, _active_name, thread = active_state(threads_path, chat_id)
            changed, deleted = remove_pending_images(thread, arg)
            write_threads(threads_path, data)
        if changed:
            image_label = "image" if deleted == 1 else "images"
            reply = f"Removed {deleted} saved {image_label} from pending: " + ", ".join(item["id"] for item in changed)
        else:
            reply = "No pending images matched."
        api.send_message(chat_id, reply, message_id)
        return

    if command in {"/jobs", "/job"}:
        with THREADS_LOCK:
            _data, _active_name, thread = active_state(threads_path, chat_id)
        api.send_message(chat_id, jobs_text(chat_id, thread), message_id)
        return

    if command == "/history":
        api.send_message(chat_id, history_text(chat_id), message_id)
        return

    if command == "/cancel":
        api.send_message(chat_id, cancel_text(chat_id, arg), message_id)
        return

    if command == "/alive":
        with THREADS_LOCK:
            _data, _active_name, thread = active_state(threads_path, chat_id)
        api.send_message(chat_id, alive_text(thread), message_id)
        return

    if command in {"/capabilities", "/caps"}:
        api.send_message(chat_id, capabilities_text(), message_id)
        return

    if command == "/policy":
        api.send_message(chat_id, policy_text(), message_id)
        return

    if command in {"/terminal", "/term"}:
        with THREADS_LOCK:
            _data, _active_name, thread = active_state(threads_path, chat_id)
        try:
            reply = terminal_command_text(chat_id, thread, arg)
        except (RuntimeError, ValueError, OSError) as exc:
            reply = str(exc)
        api.send_message(chat_id, reply, message_id)
        return

    if command in {"/file", "/fetch", "/sendfile"}:
        with THREADS_LOCK:
            _data, _active_name, thread = active_state(threads_path, chat_id)
        try:
            note = send_file_to_telegram(api, chat_id, thread, arg, message_id)
        except (RuntimeError, ValueError) as exc:
            api.send_message(chat_id, str(exc), message_id)
            return
        api.send_message(chat_id, note, message_id)
        return

    if command in {"/screenshot", "/screen"}:
        try:
            with TypingPulse(api, chat_id, "upload_photo"):
                screenshot = capture_screenshot()
                api.send_photo(chat_id, screenshot, "Mac screenshot", message_id)
        except RuntimeError as exc:
            api.send_message(chat_id, f"Blocked: screenshot failed: {exc}", message_id)
        return

    if command in {"/try", "/demo"}:
        api.send_message(chat_id, try_text(), message_id)
        return

    if command in {"/gemini", "/assistant"}:
        reply = gemini_command_text(api, chat_id, message_id, arg)
        api.send_message(chat_id, reply, None if "key saved privately" in reply.lower() else message_id)
        return

    if command == "/update":
        api.send_message(chat_id, update_text(), message_id)
        return

    if command in {"/recover", "/selfheal", "/repair"}:
        start_recovery_job(api, chat_id, arg, message_id)
        return

    if command in {"/automations", "/automation"}:
        with THREADS_LOCK:
            _data, active_name, thread = active_state(threads_path, chat_id)
        prompt_text = (
            "Inspect this Mac's Codex automations from live local state. "
            "Do not print secrets, raw logs, session transcripts, auth files, or private message content. "
            "Summarize active and paused automations, what each does, and what I can safely command from Telegram. "
            "Keep it terse and include exact blockers only."
        )
        start_background_job(
            api,
            chat_id,
            threads_path,
            active_name,
            thread,
            prompt_text,
            reply_to_message_id=message_id,
        )
        return

    if command == "/tools":
        with THREADS_LOCK:
            _data, _active_name, thread = active_state(threads_path, chat_id)
        probe_thread = dict(thread)
        probe_thread["session_id"] = ""
        start_background_job(
            api,
            chat_id,
            threads_path,
            TOOL_PROBE_THREAD,
            probe_thread,
            "Check the local Codex toolbelt without reading secrets or private logs. Reply with terse status for available desktop/app/browser/image/subagent tools and exact blockers.",
            reply_to_message_id=message_id,
            persist_thread_state=False,
        )
        return

    if command == "/reset":
        with THREADS_LOCK:
            data, active_name, thread = active_state(threads_path, chat_id)
        busy = busy_thread_message(chat_id, active_name)
        if busy:
            api.send_message(chat_id, busy, message_id)
            return
        with THREADS_LOCK:
            data, active_name, thread = active_state(threads_path, chat_id)
            thread["session_id"] = ""
            thread["updated_at"] = now_iso()
            write_threads(threads_path, data)
        api.send_message(chat_id, f"Reset thread: {active_name}", message_id)
        return

    if text.startswith("/"):
        api.send_message(chat_id, "Unknown command. Use /help.", message_id)
        return

    if not image_specs and builtin_natural_control(api, chat_id, message_id, threads_path, text):
        return

    if gemini_natural_commands_enabled() and not image_specs and gemini_allows_text(text):
        try:
            with THREADS_LOCK:
                _data, active_name, thread = active_state(threads_path, chat_id)
                threads = dict(chat_threads(_data, chat_id))
            plan = gemini_plan_for_message(text, active_name, thread, threads)
            if execute_gemini_plan(api, chat_id, message_id, threads_path, plan, text):
                return
        except Exception as exc:
            if env_bool("CODEX_RELAY_GEMINI_ERROR_NOTICES", True):
                api.send_message(
                    chat_id,
                    concise_external_error("Gemini assist", exc) + "\nContinuing with the normal Codex path.",
                    message_id,
                )

    with THREADS_LOCK:
        _data, active_name, thread = active_state(threads_path, chat_id)
    image_paths: list[Path] = []
    if image_specs:
        try:
            with TypingPulse(api, chat_id, "upload_photo"):
                image_paths = download_telegram_images(api, message)
        except RuntimeError as exc:
            api.send_message(chat_id, f"Blocked: could not read Telegram image: {exc}", message_id)
            return
    prompt_text = text or (
        "Inspect the attached Telegram image and answer directly. "
        "Do not mention file paths."
    )
    busy = busy_thread_message(chat_id, active_name)
    if busy:
        try:
            with THREADS_LOCK:
                data, active_name, thread = active_state(threads_path, chat_id)
                item = queue_pending_request(thread, prompt_text, image_paths)
                write_threads(threads_path, data)
        except ValueError as exc:
            api.send_message(chat_id, f"{busy}\n{exc}", message_id)
            return
        image_count = len(image_paths)
        image_note = ""
        if image_count:
            image_label = "image" if image_count == 1 else "images"
            image_note = f" with {image_count} {image_label}"
        api.send_message(
            chat_id,
            f"Queued request {item['id']}{image_note} until thread `{active_name}` is clear: {prompt_preview(item['prompt'])}",
            message_id,
        )
        return
    start_background_job(
        api,
        chat_id,
        threads_path,
        active_name,
        thread,
        prompt_text,
        image_paths,
        message_id,
    )


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
    print(f"thinking_mode={thinking_mode_default()}")
    print(f"reasoning_effort={thinking_mode_default()}")
    print(f"reply_style={reply_style_default()}")
    print(f"gemini_enabled={gemini_enabled()}")
    print(f"gemini_model={gemini_model()}")
    print(f"gemini_max_output_tokens={gemini_max_output_tokens()}")
    print(f"gemini_natural_commands={gemini_natural_commands_enabled()}")
    print(f"gemini_polish={gemini_polish_enabled()}")
    print(f"approval={os.environ.get('CODEX_TELEGRAM_APPROVAL', 'never')}")
    print(f"timeout_seconds={env_int('CODEX_TELEGRAM_TIMEOUT_SECONDS', DEFAULT_TIMEOUT_SECONDS)}")
    print(f"reply_threading={env_bool('CODEX_TELEGRAM_REPLY_TO_MESSAGES', False)}")
    print(f"reply_unauthorized={env_bool('CODEX_TELEGRAM_REPLY_UNAUTHORIZED', False)}")
    print(f"allow_group_chats={env_bool('CODEX_TELEGRAM_ALLOW_GROUP_CHATS', False)}")
    print(f"typing_interval_seconds={max(1, env_int('CODEX_TELEGRAM_TYPING_INTERVAL_SECONDS', 4))}")
    print(f"poll_timeout_seconds={max(1, env_int('CODEX_TELEGRAM_POLL_TIMEOUT_SECONDS', DEFAULT_TELEGRAM_POLL_TIMEOUT_SECONDS))}")
    print(f"poll_http_timeout_seconds={max(env_int('CODEX_TELEGRAM_POLL_TIMEOUT_SECONDS', DEFAULT_TELEGRAM_POLL_TIMEOUT_SECONDS) + 10, env_int('CODEX_TELEGRAM_POLL_HTTP_TIMEOUT_SECONDS', DEFAULT_TELEGRAM_POLL_HTTP_TIMEOUT_SECONDS))}")
    print(f"max_images_per_message={max_images_per_message()}")
    print(f"max_file_bytes={max_file_transfer_bytes()}")
    print(f"terminal_buffer_chars={terminal_buffer_chars()}")
    print(f"recovery_script={recovery_script_path()}")
    print(f"telegram_images={'enabled'}")
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
    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    print("Codex Relay running.")
    if not allowed_users and not allowed_chats:
        print("Enrollment mode: messages will only return Telegram ids.")

    offset = read_offset(offset_path)
    pending_media_groups: dict[tuple[int, str], tuple[float, list[dict[str, Any]]]] = {}
    while not SHUTDOWN_EVENT.is_set():
        try:
            standalone_messages: list[dict[str, Any]] = []
            for update in api.get_updates(offset):
                if SHUTDOWN_EVENT.is_set():
                    break
                update_id = int(update["update_id"])
                offset = update_id + 1
                write_private_text(offset_path, str(offset))
                message = update.get("message")
                if message:
                    group_key = media_group_key(message)
                    if group_key:
                        _seen_at, messages = pending_media_groups.get(group_key, (0.0, []))
                        messages.append(message)
                        pending_media_groups[group_key] = (time.monotonic(), messages)
                    else:
                        standalone_messages.append(message)
            for message in standalone_messages:
                handle_message(api, message, allowed_users, allowed_chats, threads_path)
            now = time.monotonic()
            ready_keys = [
                key
                for key, (seen_at, _messages) in pending_media_groups.items()
                if now - seen_at >= DEFAULT_MEDIA_GROUP_GRACE_SECONDS
            ]
            for key in ready_keys:
                _seen_at, messages = pending_media_groups.pop(key)
                handle_message(
                    api,
                    merge_media_group_messages(messages),
                    allowed_users,
                    allowed_chats,
                    threads_path,
                )
        except KeyboardInterrupt:
            print("Stopping.")
            SHUTDOWN_EVENT.set()
            cancel_all_jobs()
            join_workers()
            return 0
        except Exception as exc:
            print(f"Relay error: {exc}", file=sys.stderr)
            time.sleep(5)
    cancel_all_jobs()
    join_workers()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
