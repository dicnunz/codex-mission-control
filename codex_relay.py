#!/usr/bin/env python3
"""Codex Relay: private Telegram control for local Codex on macOS."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import signal
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
DEFAULT_MAX_IMAGE_BYTES = 20 * 1024 * 1024
DEFAULT_IMAGE_RETENTION_DAYS = 7
MAX_IMAGES_PER_MESSAGE = 4
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
DEFAULT_GEMINI_TIMEOUT_SECONDS = 20
DEFAULT_REASONING_EFFORT = "xhigh"
REASONING_EFFORTS = {"low", "medium", "high", "xhigh"}
DEFAULT_REPLY_STYLE = "brief"
REPLY_STYLES = {"brief", "verbose"}
SESSION_RE = re.compile(r"session id:\s*([0-9a-fA-F-]{36})", re.IGNORECASE)
THREAD_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,39}$")
GEMINI_ACTIONS = {
    "none",
    "set_workdir",
    "new_thread",
    "use_thread",
    "reset_thread",
    "run_codex",
    "show_status",
    "show_help",
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
STARTED_AT = time.time()
THREADS_LOCK = threading.Lock()
SHUTDOWN_EVENT = threading.Event()
WORKERS_LOCK = threading.Lock()
WORKERS: list[threading.Thread] = []
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

    def call(self, method: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        data = urllib.parse.urlencode(params or {}).encode()
        request = urllib.request.Request(self.base + method, data=data, method="POST")
        try:
            with telegram_urlopen(request, timeout=70) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")[:600]
            raise RuntimeError(f"Telegram HTTP {exc.code}: {body}") from exc
        except TelegramTLSCertificateError as exc:
            raise RuntimeError(str(exc)) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Telegram network error: {exc.reason}") from exc
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API error: {payload}")
        return payload

    def send_message(
        self, chat_id: int, text: str, reply_to_message_id: Optional[int] = None
    ) -> None:
        chunks = split_for_telegram(text)
        threaded_replies = env_bool("CODEX_TELEGRAM_REPLY_TO_MESSAGES", False)
        for chunk in chunks:
            params: dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": "true",
            }
            if threaded_replies and reply_to_message_id is not None:
                params["reply_to_message_id"] = reply_to_message_id
            self.call("sendMessage", params)
            reply_to_message_id = None

    def send_chat_action(self, chat_id: int, action: str = "typing") -> None:
        self.call("sendChatAction", {"chat_id": chat_id, "action": action})

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

    def get_updates(self, offset: Optional[int]) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"timeout": 50, "allowed_updates": json.dumps(["message"])}
        if offset is not None:
            params["offset"] = offset
        return self.call("getUpdates", params).get("result", [])

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
    def __init__(self, chat_id: int, thread_name: str, image_count: int) -> None:
        self.id = uuid.uuid4().hex[:8]
        self.chat_id = chat_id
        self.thread_name = thread_name
        self.image_count = image_count
        self.started_at = now_iso()
        self.started_monotonic = time.monotonic()
        self.cancel_event = threading.Event()
        self.process: Optional[subprocess.Popen[str]] = None
        self.lock = threading.Lock()

    def set_process(self, process: subprocess.Popen[str]) -> None:
        with self.lock:
            self.process = process

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


def cancel_all_jobs() -> None:
    with JOBS_LOCK:
        jobs = list(ACTIVE_JOBS.values())
    for job in jobs:
        job.cancel()


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


def image_attachment_specs(message: dict[str, Any]) -> list[dict[str, Any]]:
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

    return specs[:MAX_IMAGES_PER_MESSAGE]


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
    generation_config: dict[str, Any] = {"temperature": 0.2}
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
                        "description": "Thread name, folder path, or empty string, depending on action type.",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Prompt to send to Codex for run_codex actions.",
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
Known threads:
{thread_text}

Allowed actions:
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
        if len(actions) >= 4:
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
- Keep it concise. Use short paragraphs or bullets only when they improve scanability.

Original user request:
{prompt_text}

Active folder:
{thread.get('workdir') or default_workdir()}

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
                api.send_message(chat_id, busy, message_id)
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
    return (
        "Reply in the fewest words that still answer the task. "
        "Prefer concrete status, changed files, verification, and the next human-only boundary."
    )


def codex_prompt(
    message_text: str,
    thread_name: str,
    image_paths: Optional[list[Path]] = None,
    reply_style: Optional[str] = None,
) -> str:
    user_name = relay_user_name()
    assistant_name = relay_assistant_name()
    personality = relay_assistant_personality()
    personality_note = (
        f"\n{assistant_name}'s personality: {personality}\n" if personality else ""
    )
    style = reply_style if reply_style in REPLY_STYLES else reply_style_default()
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
) -> tuple[str, str, dict[str, Any]]:
    session_id = str(thread.get("session_id") or "")
    image_count = len(image_paths or [])
    reasoning_effort = env_choice(
        "CODEX_TELEGRAM_REASONING_EFFORT",
        DEFAULT_REASONING_EFFORT,
        REASONING_EFFORTS,
    )
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
    stdout = ""
    stderr = ""
    returncode: Optional[int] = None
    prompt = codex_prompt(
        message_text,
        thread_name,
        image_paths,
        str(thread.get("reply_style") or reply_style_default()),
    )
    input_text: Optional[str] = prompt

    try:
        process = subprocess.Popen(
            command,
            cwd=workdir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        if process_callback:
            process_callback(process)
        deadline = time.monotonic() + timeout
        while True:
            if cancel_event and cancel_event.is_set():
                stop_process(process)
                return finish(
                    "Canceled: job stopped before Codex replied.",
                    session_id,
                    "canceled",
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                stop_process(process)
                return finish(
                    f"Blocked: Codex timed out after {timeout} seconds. "
                    "The task was stopped before it could reply.",
                    session_id,
                    "timeout",
                )
            try:
                stdout, stderr = process.communicate(
                    input=input_text,
                    timeout=min(0.5, remaining),
                )
                returncode = process.returncode
                break
            except subprocess.TimeoutExpired:
                input_text = None
                continue
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

    if cancel_event and cancel_event.is_set():
        return finish("Canceled: job stopped before Codex replied.", session_id, "canceled")

    if returncode != 0:
        return finish(
            f"Codex failed with exit {returncode}. Run local diagnostics with ./scripts/doctor.sh.",
            session_id,
            "failed",
            returncode,
        )

    combined_output = "\n".join(part for part in [stdout, stderr] if part)
    new_session_id = extract_session_id(combined_output) or session_id
    return finish(answer or "(Codex returned an empty final message.)", new_session_id, "ok", 0)


def command_help() -> str:
    return "\n".join(
        [
            "Commands:",
            "/ping - check the bridge",
            "/health - fast local bridge checks",
            "/jobs - show running and last run",
            "/history - show recent run receipts",
            "/cancel [job] - stop a running job",
            "/automations - inspect Codex automations through Codex",
            "/new name - start a fresh Codex thread",
            "/use name - switch threads",
            "/list - show threads",
            "/where - show current thread and folder",
            "/cd path - set this thread's folder",
            "/status - show runtime state",
            "/policy - show safety boundaries",
            "/screenshot - send the Mac screen back to Telegram",
            "/latency - show last run timing and timeout",
            "/alive - show the Mac-side remote status",
            "/brief - terse replies for this thread",
            "/verbose - detailed replies for this thread",
            "/update - show local update command",
            "/capabilities - show what this remote can do",
            "/gemini - show optional Gemini assist status",
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
            f"{os.environ.get('CODEX_TELEGRAM_MODEL', 'gpt-5.5')} / "
            f"{env_choice('CODEX_TELEGRAM_REASONING_EFFORT', DEFAULT_REASONING_EFFORT, REASONING_EFFORTS)}",
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
        f"reasoning effort: {env_choice('CODEX_TELEGRAM_REASONING_EFFORT', DEFAULT_REASONING_EFFORT, REASONING_EFFORTS)}",
        f"reply style: {thread.get('reply_style') or reply_style_default()}",
        f"sandbox: {os.environ.get('CODEX_TELEGRAM_SANDBOX', 'danger-full-access')}",
        f"approval: {os.environ.get('CODEX_TELEGRAM_APPROVAL', 'never')}",
        f"timeout: {env_int('CODEX_TELEGRAM_TIMEOUT_SECONDS', DEFAULT_TIMEOUT_SECONDS)}s",
        f"reply threading: {'enabled' if env_bool('CODEX_TELEGRAM_REPLY_TO_MESSAGES', False) else 'disabled'}",
        f"group chats: {'enabled' if env_bool('CODEX_TELEGRAM_ALLOW_GROUP_CHATS', False) else 'disabled'}",
        f"typing interval: {max(1, env_int('CODEX_TELEGRAM_TYPING_INTERVAL_SECONDS', 4))}s",
        "telegram images: enabled",
        f"gemini assist: {'enabled' if gemini_enabled() else 'disabled'}",
        f"running jobs: {len(running)}",
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
            f"reasoning: {env_choice('CODEX_TELEGRAM_REASONING_EFFORT', DEFAULT_REASONING_EFFORT, REASONING_EFFORTS)}",
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
    return f"{job.id}: {job.thread_name}; running {job.elapsed()}{image_note}"


def jobs_text(chat_id: int, thread: dict[str, Any]) -> str:
    running = jobs_for_chat(chat_id)
    lines = ["running jobs:"]
    if running:
        lines.extend(f"- {job_line(job)}" for job in sorted(running, key=lambda item: item.started_at))
        lines.append("cancel: /cancel job-id")
    else:
        lines.append("- none")
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


def job_ack_text(job: RelayJob) -> str:
    lines = [
        f"Working: job {job.id}",
        f"thread: {job.thread_name}",
        "status: running",
    ]
    if job.image_count:
        image_label = "image" if job.image_count == 1 else "images"
        lines.append(f"attachments: {job.image_count} {image_label}")
    lines.append(f"check: /jobs")
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
        with TypingPulse(api, chat_id):
            answer, session_id, stats = run_codex(
                prompt_text,
                thread_snapshot,
                image_paths,
                job.cancel_event,
                job.set_process,
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
    job = RelayJob(chat_id, thread_name, len(image_paths))
    try:
        api.send_message(chat_id, job_ack_text(job), reply_to_message_id)
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
            "- allowed: Telegram images, /screenshot, named threads, local status, and automations inspection",
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
        lines = [
            "Gemini assist:",
            f"- status: {'enabled' if gemini_enabled() else 'disabled'}",
            f"- model: {gemini_model()}",
            f"- natural commands: {'enabled' if gemini_natural_commands_enabled() else 'disabled'}",
            f"- polish: {'enabled' if gemini_polish_enabled() else 'disabled'}",
        ]
        if not gemini_configured():
            lines.append("- setup: add CODEX_RELAY_GEMINI_API_KEY to .env and run ./scripts/install_launch_agent.sh")
        api.send_message(chat_id, "\n".join(lines), message_id)
        return

    if command == "/update":
        api.send_message(chat_id, update_text(), message_id)
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

    if gemini_natural_commands_enabled() and not image_specs and gemini_allows_text(text):
        try:
            with THREADS_LOCK:
                _data, active_name, thread = active_state(threads_path, chat_id)
                threads = dict(chat_threads(_data, chat_id))
            plan = gemini_plan_for_message(text, active_name, thread, threads)
            if execute_gemini_plan(api, chat_id, message_id, threads_path, plan, text):
                return
        except Exception:
            pass

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
    print(f"reasoning_effort={env_choice('CODEX_TELEGRAM_REASONING_EFFORT', DEFAULT_REASONING_EFFORT, REASONING_EFFORTS)}")
    print(f"reply_style={reply_style_default()}")
    print(f"gemini_enabled={gemini_enabled()}")
    print(f"gemini_model={gemini_model()}")
    print(f"gemini_natural_commands={gemini_natural_commands_enabled()}")
    print(f"gemini_polish={gemini_polish_enabled()}")
    print(f"approval={os.environ.get('CODEX_TELEGRAM_APPROVAL', 'never')}")
    print(f"timeout_seconds={env_int('CODEX_TELEGRAM_TIMEOUT_SECONDS', DEFAULT_TIMEOUT_SECONDS)}")
    print(f"reply_threading={env_bool('CODEX_TELEGRAM_REPLY_TO_MESSAGES', False)}")
    print(f"reply_unauthorized={env_bool('CODEX_TELEGRAM_REPLY_UNAUTHORIZED', False)}")
    print(f"allow_group_chats={env_bool('CODEX_TELEGRAM_ALLOW_GROUP_CHATS', False)}")
    print(f"typing_interval_seconds={max(1, env_int('CODEX_TELEGRAM_TYPING_INTERVAL_SECONDS', 4))}")
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
    while not SHUTDOWN_EVENT.is_set():
        try:
            for update in api.get_updates(offset):
                if SHUTDOWN_EVENT.is_set():
                    break
                update_id = int(update["update_id"])
                offset = update_id + 1
                write_private_text(offset_path, str(offset))
                message = update.get("message")
                if message:
                    handle_message(api, message, allowed_users, allowed_chats, threads_path)
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
