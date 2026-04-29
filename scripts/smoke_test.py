#!/usr/bin/env python3
"""Fast local checks that do not touch Telegram or Codex."""

from __future__ import annotations

import tempfile
import os
import ssl
import sys
import threading
import json
import time
import importlib.util
import contextlib
import io
import urllib.error
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import codex_relay as relay

CONFIGURE_SPEC = importlib.util.spec_from_file_location("configure", ROOT / "scripts" / "configure.py")
assert CONFIGURE_SPEC and CONFIGURE_SPEC.loader
configure = importlib.util.module_from_spec(CONFIGURE_SPEC)
CONFIGURE_SPEC.loader.exec_module(configure)


def assert_true(value: object, message: str) -> None:
    if not value:
        raise SystemExit(message)


class FakeTelegram(relay.TelegramAPI):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def call(self, method: str, params: Optional[dict[str, object]] = None) -> dict[str, object]:
        self.calls.append((method, params or {}))
        return {"ok": True, "result": {}}

    def send_photo(
        self,
        chat_id: int,
        path: Path,
        caption: str = "",
        reply_to_message_id: Optional[int] = None,
    ) -> None:
        self.calls.append(
            (
                "sendPhoto",
                {
                    "chat_id": chat_id,
                    "path": str(path),
                    "caption": caption,
                    "reply_to_message_id": reply_to_message_id,
                },
            )
        )

    def send_document(
        self,
        chat_id: int,
        path: Path,
        caption: str = "",
        reply_to_message_id: Optional[int] = None,
    ) -> None:
        self.calls.append(
            (
                "sendDocument",
                {
                    "chat_id": chat_id,
                    "path": str(path),
                    "caption": caption,
                    "reply_to_message_id": reply_to_message_id,
                },
            )
        )


class FakeResponse:
    def __init__(self, chunks: list[bytes], headers: Optional[dict[str, str]] = None) -> None:
        self.chunks = chunks
        self.headers = headers or {}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        pass

    def read(self, _size: int = -1) -> bytes:
        if not self.chunks:
            return b""
        return self.chunks.pop(0)


ENV_PREFIXES = ("CODEX_TELEGRAM_", "CODEX_RELAY_", "TELEGRAM_")
ENV_EXACT = {"CODEX_BIN", "GEMINI_API_KEY"}
TEST_ENV = {
    "CODEX_TELEGRAM_MODEL": "gpt-5.5",
    "CODEX_TELEGRAM_THINKING_MODE": "xhigh",
    "CODEX_TELEGRAM_REASONING_EFFORT": "xhigh",
    "CODEX_TELEGRAM_SPEED": "standard",
    "CODEX_TELEGRAM_REPLY_STYLE": "brief",
    "CODEX_TELEGRAM_TIMEOUT_SECONDS": "600",
}


@contextlib.contextmanager
def isolated_env() -> object:
    touched = {
        key
        for key in os.environ
        if key.startswith(ENV_PREFIXES) or key in ENV_EXACT
    } | set(TEST_ENV)
    old_values = {key: os.environ.get(key) for key in touched}
    for key in touched:
        os.environ.pop(key, None)
    os.environ.update(TEST_ENV)
    try:
        yield
    finally:
        for key in touched:
            os.environ.pop(key, None)
        for key, value in old_values.items():
            if value is not None:
                os.environ[key] = value


def run_tests() -> int:
    photo_message = {
        "message_id": 1,
        "caption": "can you see this?",
        "photo": [
            {"file_id": "small", "width": 320, "height": 240, "file_size": 1000},
            {"file_id": "large", "width": 1280, "height": 720, "file_size": 4000},
        ],
    }
    specs = relay.image_attachment_specs(photo_message)
    assert_true(len(specs) == 1, "expected one selected Telegram photo")
    assert_true(specs[0]["file_id"] == "large", "expected highest-resolution photo")

    document_message = {
        "message_id": 2,
        "document": {
            "file_id": "doc-image",
            "file_name": "screen.PNG",
            "mime_type": "application/octet-stream",
            "file_size": 2000,
        },
    }
    assert_true(relay.image_attachment_specs(document_message), "expected image document support")
    assert_true(relay.image_suffix("screen.PNG") == ".png", "expected png suffix")
    assert_true(relay.image_suffix("photo.jpeg") == ".jpg", "expected jpeg normalization")
    grouped = relay.merge_media_group_messages(
        [
            {
                "message_id": 3,
                "media_group_id": "album-1",
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 1},
                "photo": [{"file_id": "album-a", "width": 640, "height": 480, "file_size": 1000}],
            },
            {
                "message_id": 4,
                "media_group_id": "album-1",
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 1},
                "caption": "compare these",
                "photo": [{"file_id": "album-b", "width": 640, "height": 480, "file_size": 1000}],
            },
        ]
    )
    grouped_specs = relay.image_attachment_specs(grouped)
    assert_true(len(grouped_specs) == 2, "expected Telegram media group to preserve multiple images")
    assert_true(grouped.get("caption") == "compare these", "expected media group caption")
    assert_true(relay.media_group_key(grouped["_relay_media_group_messages"][0]) == (123, "album-1"), "expected media group key")
    os.environ["CODEX_TELEGRAM_MAX_IMAGES_PER_MESSAGE"] = "1"
    assert_true(len(relay.image_attachment_specs(grouped)) == 1, "expected configurable image cap")
    os.environ.pop("CODEX_TELEGRAM_MAX_IMAGES_PER_MESSAGE", None)

    prompt = relay.codex_prompt("what is in this image?", "main", [Path("/tmp/example.png")])
    assert_true("attached to this Codex prompt" in prompt, "expected image prompt note")
    assert_true("Reply style: brief" in prompt, "expected default brief reply style")
    verbose_prompt = relay.codex_prompt("explain", "main", reply_style="verbose")
    assert_true("Reply style: verbose" in verbose_prompt, "expected verbose reply style")
    assert_true(relay.extract_session_id("Session ID: 12345678-1234-1234-1234-123456789abc"), "expected session id")
    assert_true(relay.env_bool("MISSING_TEST_BOOL", True), "expected default bool support")
    assert_true(relay.authorized(1, 2, "private", {1}, {2}), "expected private allowlist match")
    assert_true(not relay.authorized(1, 2, "private", {1}, {3}), "expected both user and chat to match")
    assert_true(not relay.authorized(1, -100, "group", {1}, {-100}), "expected groups disabled by default")
    os.environ["CODEX_TELEGRAM_ALLOW_GROUP_CHATS"] = "true"
    assert_true(relay.authorized(1, -100, "group", {1}, {-100}), "expected explicit group opt-in")
    assert_true(not relay.authorized(1, -100, "group", {1}, set()), "expected groups to require chat allowlist")
    assert_true(not relay.authorized(1, -100, "group", set(), {-100}), "expected groups to require user allowlist")
    os.environ.pop("CODEX_TELEGRAM_ALLOW_GROUP_CHATS", None)

    assert_true(
        configure.enrollment_match(
            {
                "message": {
                    "text": "/start codex-abc123",
                    "from": {"id": 1},
                    "chat": {"id": 2, "type": "private"},
                }
            },
            "codex-abc123",
        )
        == ("1", "2"),
        "expected nonce enrollment match",
    )
    assert_true(
        configure.enrollment_match(
            {
                "message": {
                    "text": "/start",
                    "from": {"id": 1},
                    "chat": {"id": 2, "type": "private"},
                }
            },
            "codex-abc123",
        )
        is None,
        "expected stale /start to be ignored",
    )
    original_latest_offset = configure.latest_update_offset
    original_token_hex = configure.secrets.token_hex
    original_telegram_call = configure.telegram_call
    try:
        configure.latest_update_offset = lambda _token: 42
        configure.secrets.token_hex = lambda _n: "abc123"

        def fake_telegram_call(_token: str, _method: str, params: Optional[dict[str, str]] = None) -> dict[str, object]:
            assert_true(params and params.get("offset") == "42", "expected stale updates to be skipped")
            return {
                "result": [
                    {
                        "update_id": 42,
                        "message": {
                            "text": "/start",
                            "from": {"id": 9},
                            "chat": {"id": 9, "type": "private"},
                        },
                    },
                    {
                        "update_id": 43,
                        "message": {
                            "text": "/start codex-abc123",
                            "from": {"id": 10},
                            "chat": {"id": 10, "type": "private"},
                        },
                    },
                ]
            }

        configure.telegram_call = fake_telegram_call
        with contextlib.redirect_stdout(io.StringIO()):
            assert_true(
                configure.wait_for_start("token", "botname", "") == ("10", "10"),
                "expected wait_for_start to require nonce-bearing /start",
            )
    finally:
        configure.latest_update_offset = original_latest_offset
        configure.secrets.token_hex = original_token_hex
        configure.telegram_call = original_telegram_call

    old_configure_urlopen = configure.urllib.request.urlopen
    old_configure_context = configure.ssl.create_default_context
    old_configure_ca = os.environ.get("CODEX_RELAY_CA_FILE")
    try:
        with tempfile.NamedTemporaryFile() as ca_file:
            os.environ["CODEX_RELAY_CA_FILE"] = ca_file.name
            calls = []

            def fake_configure_urlopen(*_args: object, **kwargs: object) -> FakeResponse:
                calls.append(kwargs)
                if "context" not in kwargs:
                    raise urllib.error.URLError(
                        ssl.SSLError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
                    )
                return FakeResponse([b'{"ok": true, "result": {"username": "bot"}}'])

            configure.ssl.create_default_context = lambda cafile=None: ("context", cafile)
            configure.urllib.request.urlopen = fake_configure_urlopen
            payload = configure.telegram_call("token", "getMe")
            assert_true(payload["result"]["username"] == "bot", "expected configure CA fallback")
            assert_true(len(calls) == 2, "expected configure to retry TLS with CA bundle")
    finally:
        configure.urllib.request.urlopen = old_configure_urlopen
        configure.ssl.create_default_context = old_configure_context
        if old_configure_ca is None:
            os.environ.pop("CODEX_RELAY_CA_FILE", None)
        else:
            os.environ["CODEX_RELAY_CA_FILE"] = old_configure_ca

    fake_enroll = FakeTelegram()
    relay.handle_message(
        fake_enroll,
        {
            "message_id": 1,
            "chat": {"id": -100, "type": "group"},
            "from": {"id": 1},
            "text": "/start",
        },
        set(),
        set(),
        Path("/tmp/codex-relay-unused-threads.json"),
    )
    assert_true(not fake_enroll.calls, "expected group enrollment to stay silent by default")

    fake = FakeTelegram()
    os.environ.pop("CODEX_TELEGRAM_REPLY_TO_MESSAGES", None)
    fake.send_message(123, "plain", 999)
    assert_true("reply_to_message_id" not in fake.calls[-1][1], "expected reply threading off by default")
    os.environ["CODEX_TELEGRAM_REPLY_TO_MESSAGES"] = "true"
    fake.send_message(123, "threaded", 999)
    assert_true(fake.calls[-1][1].get("reply_to_message_id") == 999, "expected opt-in reply threading")
    os.environ.pop("CODEX_TELEGRAM_REPLY_TO_MESSAGES", None)

    timeout_api = relay.TelegramAPI("token")
    timeout_api.call = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("Telegram request timed out"))
    assert_true(timeout_api.get_updates(123) == [], "expected polling timeout to be non-fatal")

    thread = {
        "name": "main",
        "workdir": "/tmp",
        "last_status": "ok",
        "last_latency_seconds": 1.2,
        "last_image_count": 1,
        "last_run_at": "2026-04-25T00:00:00+00:00",
    }
    status = relay.status_text(thread)
    assert_true("reply threading: disabled" in status, "expected reply threading status")
    assert_true("reply style: brief" in status, "expected reply style status")
    assert_true("group chats: disabled" in status, "expected group chat status")
    assert_true("thinking mode: xhigh" in status, "expected default xhigh thinking status")
    assert_true("speed: standard" in status, "expected default standard speed status")
    assert_true("gemini assist: disabled" in status, "expected Gemini status")
    assert_true("running jobs: 0" in status, "expected running job count")
    assert_true("pending requests: 0" in status, "expected pending request count")
    assert_true("last run: ok; 1.2s; 1 image" in status, "expected last-run latency status")
    health = relay.health_text()
    assert_true("health:" in health, "expected health output")
    assert_true("deep check: /tools" in health, "expected health to point at deep check")

    old_urlopen = relay.urllib.request.urlopen
    old_context = relay.ssl.create_default_context
    try:
        with tempfile.NamedTemporaryFile() as ca_file:
            old_ca = os.environ.get("CODEX_RELAY_CA_FILE")
            try:
                os.environ["CODEX_RELAY_CA_FILE"] = ca_file.name
                calls = []

                def fake_relay_tls_urlopen(*_args: object, **kwargs: object) -> FakeResponse:
                    calls.append(kwargs)
                    if "context" not in kwargs:
                        raise urllib.error.URLError(
                            ssl.SSLError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
                        )
                    return FakeResponse([b'{"ok": true, "result": {"id": 1}}'])

                relay.ssl.create_default_context = lambda cafile=None: ("context", cafile)
                relay.urllib.request.urlopen = fake_relay_tls_urlopen
                assert_true(
                    relay.TelegramAPI("token").call("getMe")["result"]["id"] == 1,
                    "expected runtime CA fallback",
                )
                assert_true(len(calls) == 2, "expected runtime to retry TLS with CA bundle")
            finally:
                if old_ca is None:
                    os.environ.pop("CODEX_RELAY_CA_FILE", None)
                else:
                    os.environ["CODEX_RELAY_CA_FILE"] = old_ca

        relay.ssl.create_default_context = old_context
        relay.urllib.request.urlopen = lambda *_args, **_kwargs: FakeResponse([b"ok"])
        assert_true(relay.TelegramAPI("token").download_file("file.jpg", max_bytes=2) == b"ok", "expected bounded download")
        relay.urllib.request.urlopen = lambda *_args, **_kwargs: FakeResponse([b"abc"])
        try:
            relay.TelegramAPI("token").download_file("file.jpg", max_bytes=2)
        except RuntimeError as exc:
            assert_true("too large" in str(exc), "expected oversized streaming download failure")
        else:
            raise SystemExit("expected oversized streaming download failure")
        relay.urllib.request.urlopen = lambda *_args, **_kwargs: FakeResponse([b""], {"Content-Length": "3"})
        try:
            relay.TelegramAPI("token").download_file("file.jpg", max_bytes=2)
        except RuntimeError as exc:
            assert_true("too large" in str(exc), "expected oversized content-length failure")
        else:
            raise SystemExit("expected oversized content-length failure")
    finally:
        relay.urllib.request.urlopen = old_urlopen
        relay.ssl.create_default_context = old_context

    job = relay.RelayJob(123, "main", 2)
    relay.register_job(job)
    try:
        job.add_progress("?? LaunchAgent")
        job.add_progress("Running scripts/smoke_test.py")
        progress = relay.job_progress_text(job)
        assert_true("?? LaunchAgent" not in progress, "expected noisy Codex fragment hidden from progress")
        assert_true("Running scripts/smoke_test.py" in progress, "expected useful progress line")
        busy = relay.busy_thread_message(123, "main")
        assert_true("Thread `main` is busy." in busy, "expected busy thread message")
        jobs = relay.jobs_text(123, thread)
        assert_true(job.id in jobs, "expected running job in /jobs output")
        assert_true("2 images" in jobs, "expected image count in /jobs output")
        assert_true(f"stop: /cancel {job.id}" in relay.job_ack_text(job), "expected cancel affordance in ack")
        assert_true(relay.cancel_text(123, job.id) == f"Cancel requested: {job.id}", "expected cancel by id")
        assert_true(job.cancel_event.is_set(), "expected cancel event")
    finally:
        relay.finish_job(job)
    assert_true("- none" in relay.jobs_text(123, thread), "expected empty jobs output")
    assert_true("last run: ok; 1.2s; 1 image" in relay.latency_text(thread), "expected latency text")
    assert_true("./scripts/update.sh" in relay.update_text(), "expected update command text")

    with tempfile.TemporaryDirectory() as tmp:
        old_state_dir = os.environ.get("CODEX_TELEGRAM_STATE_DIR")
        os.environ["CODEX_TELEGRAM_STATE_DIR"] = str(Path(tmp) / "state")
        target = Path(tmp) / "private.bin"
        relay.write_private_bytes(target, b"ok")
        assert_true(target.read_bytes() == b"ok", "expected private byte write")
        assert_true(oct(target.stat().st_mode & 0o777) == "0o600", "expected private file mode")

        relay.append_history_event(
            {
                "at": "2026-04-25T00:00:00+00:00",
                "chat_id": 123,
                "thread": "main",
                "status": "ok",
                "latency_seconds": 2.3,
                "image_count": 1,
                "reasoning_effort": "high",
                "speed": "standard",
                "job_id": "abc12345",
                "folder": "repo",
                "prompt": "must not persist",
            }
        )
        events = relay.read_history()
        assert_true(events and events[0]["status"] == "ok", "expected history event")
        assert_true("prompt" not in json.dumps(events), "expected sanitized history")
        history = relay.history_text(123)
        assert_true("ok; main; 2.3s; 1 image; repo" in history, "expected history text")

        threads_path = Path(tmp) / "threads.json"
        fake_style = FakeTelegram()
        relay.handle_message(
            fake_style,
            {
                "message_id": 3,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 1},
                "text": "/verbose",
            },
            {1},
            {123},
            threads_path,
        )
        data = relay.read_threads(threads_path)
        assert_true(
            data["threads_by_chat"]["123"]["main"]["reply_style"] == "verbose",
            "expected /verbose to persist style",
        )
        relay.handle_message(
            fake_style,
            {
                "message_id": 4,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 1},
                "text": "/brief",
            },
            {1},
            {123},
            threads_path,
        )
        data = relay.read_threads(threads_path)
        assert_true(
            data["threads_by_chat"]["123"]["main"]["reply_style"] == "brief",
            "expected /brief to persist style",
        )
        relay.handle_message(
            fake_style,
            {
                "message_id": 4,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 1},
                "text": "/think high",
            },
            {1},
            {123},
            threads_path,
        )
        data = relay.read_threads(threads_path)
        assert_true(
            data["threads_by_chat"]["123"]["main"]["thinking_mode"] == "high",
            "expected /think to persist thread thinking mode",
        )
        assert_true("Thinking mode: high" in str(fake_style.calls[-1][1].get("text")), "expected /think reply")
        relay.handle_message(
            fake_style,
            {
                "message_id": 4,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 1},
                "text": "/think default",
            },
            {1},
            {123},
            threads_path,
        )
        data = relay.read_threads(threads_path)
        assert_true(
            "thinking_mode" not in data["threads_by_chat"]["123"]["main"],
            "expected /think default to clear thread override",
        )
        natural_project = Path(tmp) / "natural-project"
        natural_project.mkdir()
        original_gemini_plan_for_message = relay.gemini_plan_for_message
        original_start_background_job = relay.start_background_job
        old_gemini_key = os.environ.get("CODEX_RELAY_GEMINI_API_KEY")
        os.environ["CODEX_RELAY_GEMINI_API_KEY"] = "fake-gemini-key"
        natural_jobs = []

        def fake_gemini_plan_for_message(*_args: object) -> dict[str, object]:
            return {
                "actions": [
                    {"type": "set_thinking_mode", "value": "high"},
                    {"type": "set_workdir", "value": str(natural_project)},
                    {"type": "run_codex", "prompt": "Run a security audit."},
                ]
            }

        def fake_natural_start_background_job(*args: object, **kwargs: object) -> None:
            natural_jobs.append((args, kwargs))

        relay.gemini_plan_for_message = fake_gemini_plan_for_message
        relay.start_background_job = fake_natural_start_background_job
        try:
            relay.handle_message(
                fake_style,
                {
                    "message_id": 5,
                    "chat": {"id": 123, "type": "private"},
                    "from": {"id": 1},
                    "text": "set my dir to this project and run a security audit",
                },
                {1},
                {123},
                threads_path,
            )
        finally:
            relay.gemini_plan_for_message = original_gemini_plan_for_message
            relay.start_background_job = original_start_background_job
            if old_gemini_key is None:
                os.environ.pop("CODEX_RELAY_GEMINI_API_KEY", None)
            else:
                os.environ["CODEX_RELAY_GEMINI_API_KEY"] = old_gemini_key
        data = relay.read_threads(threads_path)
        assert_true(
            data["threads_by_chat"]["123"]["main"]["workdir"] == str(natural_project.resolve()),
            "expected Gemini natural command to update workdir",
        )
        assert_true(
            data["threads_by_chat"]["123"]["main"]["thinking_mode"] == "high",
            "expected Gemini natural command to update thinking mode",
        )
        assert_true(natural_jobs, "expected Gemini natural command to start Codex job")
        assert_true(natural_jobs[-1][0][5] == "Run a security audit.", "expected planned Codex prompt")

        queue_job = relay.RelayJob(123, "main", 0)
        relay.register_job(queue_job)
        original_gemini_plan_for_message = relay.gemini_plan_for_message
        old_gemini_key = os.environ.get("CODEX_RELAY_GEMINI_API_KEY")
        os.environ["CODEX_RELAY_GEMINI_API_KEY"] = "fake-gemini-key"

        def fake_queue_plan(*_args: object) -> dict[str, object]:
            return {"actions": [{"type": "run_codex", "prompt": "Queued audit."}]}

        relay.gemini_plan_for_message = fake_queue_plan
        try:
            relay.handle_message(
                fake_style,
                {
                    "message_id": 5,
                    "chat": {"id": 123, "type": "private"},
                    "from": {"id": 1},
                    "text": "run this after the current job",
                },
                {1},
                {123},
                threads_path,
            )
        finally:
            relay.gemini_plan_for_message = original_gemini_plan_for_message
            relay.finish_job(queue_job)
            if old_gemini_key is None:
                os.environ.pop("CODEX_RELAY_GEMINI_API_KEY", None)
            else:
                os.environ["CODEX_RELAY_GEMINI_API_KEY"] = old_gemini_key
        data = relay.read_threads(threads_path)
        pending = data["threads_by_chat"]["123"]["main"]["pending_requests"]
        assert_true(pending and pending[0]["prompt"] == "Queued audit.", "expected busy Gemini run to queue")

        original_gemini_plan_for_message = relay.gemini_plan_for_message
        old_gemini_key = os.environ.get("CODEX_RELAY_GEMINI_API_KEY")
        os.environ["CODEX_RELAY_GEMINI_API_KEY"] = "fake-gemini-key"

        def fake_replace_plan(*_args: object) -> dict[str, object]:
            return {
                "actions": [
                    {
                        "type": "replace_pending_request",
                        "value": "latest",
                        "prompt": "Run tests instead.",
                    }
                ]
            }

        relay.gemini_plan_for_message = fake_replace_plan
        try:
            relay.handle_message(
                fake_style,
                {
                    "message_id": 5,
                    "chat": {"id": 123, "type": "private"},
                    "from": {"id": 1},
                    "text": "change that pending request to run tests",
                },
                {1},
                {123},
                threads_path,
            )
        finally:
            relay.gemini_plan_for_message = original_gemini_plan_for_message
            if old_gemini_key is None:
                os.environ.pop("CODEX_RELAY_GEMINI_API_KEY", None)
            else:
                os.environ["CODEX_RELAY_GEMINI_API_KEY"] = old_gemini_key
        data = relay.read_threads(threads_path)
        pending = data["threads_by_chat"]["123"]["main"]["pending_requests"]
        assert_true(pending and pending[0]["prompt"] == "Run tests instead.", "expected Gemini to replace pending request")

        original_gemini_plan_for_message = relay.gemini_plan_for_message
        old_gemini_key = os.environ.get("CODEX_RELAY_GEMINI_API_KEY")
        os.environ["CODEX_RELAY_GEMINI_API_KEY"] = "fake-gemini-key"

        def fake_remove_plan(*_args: object) -> dict[str, object]:
            return {"actions": [{"type": "remove_pending_request", "value": "latest"}]}

        relay.gemini_plan_for_message = fake_remove_plan
        try:
            relay.handle_message(
                fake_style,
                {
                    "message_id": 5,
                    "chat": {"id": 123, "type": "private"},
                    "from": {"id": 1},
                    "text": "never mind",
                },
                {1},
                {123},
                threads_path,
            )
        finally:
            relay.gemini_plan_for_message = original_gemini_plan_for_message
            if old_gemini_key is None:
                os.environ.pop("CODEX_RELAY_GEMINI_API_KEY", None)
            else:
                os.environ["CODEX_RELAY_GEMINI_API_KEY"] = old_gemini_key
        data = relay.read_threads(threads_path)
        assert_true(
            not data["threads_by_chat"]["123"]["main"].get("pending_requests"),
            "expected Gemini never mind to clear pending request",
        )

        with relay.THREADS_LOCK:
            data = relay.read_threads(threads_path)
            thread = relay.ensure_thread(data, 123, "main")
            relay.queue_pending_request(thread, "Queued follow up.")
            relay.write_threads(threads_path, data)
        queued_starts = []
        original_start_background_job = relay.start_background_job
        relay.start_background_job = lambda *args, **kwargs: queued_starts.append((args, kwargs))
        try:
            relay.start_next_pending_job(fake_style, 123, threads_path, "main")
        finally:
            relay.start_background_job = original_start_background_job
        assert_true(queued_starts, "expected queued request to start after thread clears")
        assert_true(queued_starts[-1][0][5] == "Queued follow up.", "expected queued prompt to start")
        data = relay.read_threads(threads_path)
        assert_true(
            not data["threads_by_chat"]["123"]["main"].get("pending_requests"),
            "expected started queued request to be removed from queue",
        )

        attachment = relay.attachments_dir() / "queued-image.jpg"
        relay.write_private_bytes(attachment, b"fake-image")
        with relay.THREADS_LOCK:
            data = relay.read_threads(threads_path)
            thread = relay.ensure_thread(data, 123, "main")
            queued_image = relay.queue_pending_request(thread, "Queued image task.", [attachment])
            relay.write_threads(threads_path, data)
        assert_true(queued_image["image_count"] == 1, "expected queued request to retain image count")
        data = relay.read_threads(threads_path)
        thread = data["threads_by_chat"]["123"]["main"]
        assert_true("1 image" in relay.pending_queue_text(thread), "expected queue text to show image count")
        changed, deleted = relay.remove_pending_images(thread, queued_image["id"])
        assert_true(changed and deleted == 1, "expected pending image removal")
        assert_true(not attachment.exists(), "expected removed pending image file to be deleted")

        terminal_message_id = 30
        relay.handle_message(
            fake_style,
            {
                "message_id": terminal_message_id,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 1},
                "text": "/terminal open smoke -- printf ready; sleep 5",
            },
            {1},
            {123},
            threads_path,
        )
        assert_true("Terminal `smoke` started" in str(fake_style.calls[-1][1].get("text")), "expected terminal open reply")
        relay.handle_message(
            fake_style,
            {
                "message_id": terminal_message_id + 1,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 1},
                "text": "/terminal read smoke",
            },
            {1},
            {123},
            threads_path,
        )
        assert_true("ready" in str(fake_style.calls[-1][1].get("text")), "expected terminal read output")
        relay.handle_message(
            fake_style,
            {
                "message_id": terminal_message_id + 2,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 1},
                "text": "/terminal kill smoke",
            },
            {1},
            {123},
            threads_path,
        )
        assert_true("Killed terminal: smoke" in str(fake_style.calls[-1][1].get("text")), "expected terminal kill")

        fetch_file = natural_project / "fetch.txt"
        fetch_file.write_text("send me")
        relay.handle_message(
            fake_style,
            {
                "message_id": 34,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 1},
                "text": "/file fetch.txt",
            },
            {1},
            {123},
            threads_path,
        )
        assert_true(any(call[0] == "sendDocument" for call in fake_style.calls[-3:]), "expected /file to send document")

        dummy_recovery = Path(tmp) / "recover.sh"
        dummy_recovery.write_text("#!/bin/sh\necho recover-ok\n")
        dummy_recovery.chmod(0o700)
        old_recovery_script = os.environ.get("CODEX_RELAY_RECOVERY_SCRIPT")
        os.environ["CODEX_RELAY_RECOVERY_SCRIPT"] = str(dummy_recovery)
        try:
            recovery_job = relay.RelayJob(123, "recovery", 0)
            output, exit_code = relay.run_recovery_command(recovery_job, "")
        finally:
            if old_recovery_script is None:
                os.environ.pop("CODEX_RELAY_RECOVERY_SCRIPT", None)
            else:
                os.environ["CODEX_RELAY_RECOVERY_SCRIPT"] = old_recovery_script
        assert_true(exit_code == 0 and "recover-ok" in output, "expected recovery script runner")

        relay.handle_message(
            fake_style,
            {
                "message_id": 5,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 1},
                "text": "/health",
            },
            {1},
            {123},
            threads_path,
        )
        assert_true("health:" in str(fake_style.calls[-1][1].get("text")), "expected /health command")

        relay.handle_message(
            fake_style,
            {
                "message_id": 5,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 1},
                "text": "/gemini",
            },
            {1},
            {123},
            threads_path,
        )
        assert_true("/gemini key" in str(fake_style.calls[-1][1].get("text")), "expected Telegram Gemini setup hint")

        old_env_paths = relay.relay_env_update_paths
        old_gemini_values = {
            key: os.environ.get(key)
            for key in (
                "CODEX_RELAY_GEMINI_API_KEY",
                "CODEX_RELAY_GEMINI_ENABLED",
                "CODEX_RELAY_GEMINI_NATURAL_COMMANDS",
                "CODEX_RELAY_GEMINI_POLISH",
            )
        }
        gemini_env = Path(tmp) / "gemini.env"
        gemini_key = "AIzaSyDUMMYKEYDUMMYKEYDUMMYKEY123456789"
        relay.relay_env_update_paths = lambda: [gemini_env]
        try:
            relay.handle_message(
                fake_style,
                {
                    "message_id": 55,
                    "chat": {"id": 123, "type": "private"},
                    "from": {"id": 1},
                    "text": f"/gemini key {gemini_key}",
                },
                {1},
                {123},
                threads_path,
            )
            assert_true("CODEX_RELAY_GEMINI_API_KEY=" in gemini_env.read_text(), "expected Gemini key persistence")
            assert_true(os.environ.get("CODEX_RELAY_GEMINI_API_KEY") == gemini_key, "expected live Gemini env reload")
            assert_true(any(call[0] == "deleteMessage" for call in fake_style.calls[-3:]), "expected key message deletion attempt")
            assert_true(gemini_key not in str(fake_style.calls[-1][1].get("text")), "expected Gemini key hidden from reply")
        finally:
            relay.relay_env_update_paths = old_env_paths
            for key, value in old_gemini_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        relay.handle_message(
            fake_style,
            {
                "message_id": 6,
                "chat": {"id": 123, "type": "private"},
                "from": {"id": 1},
                "text": "/policy",
            },
            {1},
            {123},
            threads_path,
        )
        assert_true("Policy:" in str(fake_style.calls[-1][1].get("text")), "expected /policy command")

        original_capture_screenshot = relay.capture_screenshot
        screenshot_path = Path(tmp) / "screen.jpg"
        screenshot_path.write_bytes(b"fake-jpeg")
        relay.capture_screenshot = lambda: screenshot_path
        try:
            relay.handle_message(
                fake_style,
                {
                    "message_id": 7,
                    "chat": {"id": 123, "type": "private"},
                    "from": {"id": 1},
                    "text": "/screenshot",
                },
                {1},
                {123},
                threads_path,
            )
        finally:
            relay.capture_screenshot = original_capture_screenshot
        assert_true(fake_style.calls[-1][0] == "sendPhoto", "expected /screenshot to send a photo")

        def blocked_screenshot() -> Path:
            raise RuntimeError("could not create image from display")

        relay.capture_screenshot = blocked_screenshot
        try:
            relay.handle_message(
                fake_style,
                {
                    "message_id": 8,
                    "chat": {"id": 123, "type": "private"},
                    "from": {"id": 1},
                    "text": "/screenshot",
                },
                {1},
                {123},
                threads_path,
            )
        finally:
            relay.capture_screenshot = original_capture_screenshot
        blocked_text = str(fake_style.calls[-1][1].get("text"))
        assert_true("Screen Recording permission" in blocked_text, "expected screenshot permission guidance")

        background_calls = []
        original_start_background_job = relay.start_background_job

        def fake_start_background_job(*args: object, **kwargs: object) -> None:
            background_calls.append((args, kwargs))

        relay.start_background_job = fake_start_background_job
        try:
            relay.handle_message(
                fake_style,
                {
                    "message_id": 7,
                    "chat": {"id": 123, "type": "private"},
                    "from": {"id": 1},
                    "text": "/tools",
                },
                {1},
                {123},
                threads_path,
            )
        finally:
            relay.start_background_job = original_start_background_job
        assert_true(background_calls, "expected /tools to start a background job")
        args, kwargs = background_calls[-1]
        assert_true(args[3] == relay.TOOL_PROBE_THREAD, "expected isolated tool probe thread")
        assert_true(kwargs.get("persist_thread_state") is False, "expected /tools not to persist session")

        fake_codex = Path(tmp) / "fake-codex"
        fake_codex.write_text(
            "#!/bin/sh\n"
            "out=''\n"
            "found_reasoning=0\n"
            "found_speed=0\n"
            "while [ \"$#\" -gt 0 ]; do\n"
            "  if [ \"$1\" = '--output-last-message' ]; then shift; out=\"$1\"; fi\n"
            "  if [ \"$1\" = 'model_reasoning_effort=\"high\"' ]; then found_reasoning=1; fi\n"
            "  if [ \"$1\" = 'service_tier=\"standard\"' ]; then found_speed=1; fi\n"
            "  shift || true\n"
            "done\n"
            "if [ \"$found_reasoning\" != 1 ]; then echo 'missing reasoning effort' >&2; exit 7; fi\n"
            "if [ \"$found_speed\" != 1 ]; then echo 'missing speed tier' >&2; exit 8; fi\n"
            "printf 'fake answer\\n' > \"$out\"\n"
            "printf 'session id: 12345678-1234-1234-1234-123456789abc\\n' >&2\n"
        )
        fake_codex.chmod(0o700)
        old_codex_bin = os.environ.get("CODEX_BIN")
        old_reasoning = os.environ.get("CODEX_TELEGRAM_REASONING_EFFORT")
        old_thinking = os.environ.get("CODEX_TELEGRAM_THINKING_MODE")
        os.environ["CODEX_BIN"] = str(fake_codex)
        os.environ["CODEX_TELEGRAM_REASONING_EFFORT"] = "high"
        os.environ["CODEX_TELEGRAM_THINKING_MODE"] = "high"
        try:
            answer, session_id, stats = relay.run_codex("hello", {"workdir": tmp, "name": "main"})
        finally:
            if old_codex_bin is None:
                os.environ.pop("CODEX_BIN", None)
            else:
                os.environ["CODEX_BIN"] = old_codex_bin
            if old_reasoning is None:
                os.environ.pop("CODEX_TELEGRAM_REASONING_EFFORT", None)
            else:
                os.environ["CODEX_TELEGRAM_REASONING_EFFORT"] = old_reasoning
            if old_thinking is None:
                os.environ.pop("CODEX_TELEGRAM_THINKING_MODE", None)
            else:
                os.environ["CODEX_TELEGRAM_THINKING_MODE"] = old_thinking
        assert_true(answer == "fake answer", "expected fake Codex answer")
        assert_true(session_id.endswith("123456789abc"), "expected captured session id")
        assert_true(stats["last_status"] == "ok", "expected ok run status")
        assert_true("last_latency_seconds" in stats, "expected latency stats")
        assert_true(stats["last_reasoning_effort"] == "high", "expected reasoning stats")
        assert_true(stats["last_speed"] == "standard", "expected speed stats")

        high_codex = Path(tmp) / "high-codex"
        high_codex.write_text(
            "#!/bin/sh\n"
            "out=''\n"
            "found_reasoning=0\n"
            "while [ \"$#\" -gt 0 ]; do\n"
            "  if [ \"$1\" = '--output-last-message' ]; then shift; out=\"$1\"; fi\n"
            "  if [ \"$1\" = 'model_reasoning_effort=\"high\"' ]; then found_reasoning=1; fi\n"
            "  shift || true\n"
            "done\n"
            "if [ \"$found_reasoning\" != 1 ]; then echo 'missing high thinking mode' >&2; exit 7; fi\n"
            "printf 'high answer\\n' > \"$out\"\n"
        )
        high_codex.chmod(0o700)
        os.environ["CODEX_BIN"] = str(high_codex)
        try:
            answer, _session_id, stats = relay.run_codex(
                "hello",
                {"workdir": tmp, "name": "main", "thinking_mode": "high"},
            )
        finally:
            if old_codex_bin is None:
                os.environ.pop("CODEX_BIN", None)
            else:
                os.environ["CODEX_BIN"] = old_codex_bin
        assert_true(answer == "high answer", "expected thread thinking override to reach Codex")
        assert_true(stats["last_reasoning_effort"] == "high", "expected thinking override stats")

        failing_codex = Path(tmp) / "failing-codex"
        failing_codex.write_text(
            "#!/bin/sh\n"
            "echo 'SECRET_TOKEN_SHOULD_NOT_LEAK' >&2\n"
            "exit 9\n"
        )
        failing_codex.chmod(0o700)
        os.environ["CODEX_BIN"] = str(failing_codex)
        try:
            answer, _session_id, stats = relay.run_codex("fail", {"workdir": tmp, "name": "main"})
        finally:
            if old_codex_bin is None:
                os.environ.pop("CODEX_BIN", None)
            else:
                os.environ["CODEX_BIN"] = old_codex_bin
        assert_true("SECRET_TOKEN_SHOULD_NOT_LEAK" not in answer, "expected stderr redaction")
        assert_true("exit 9" in answer, "expected exit code in sanitized failure")
        assert_true(stats["last_status"] == "failed", "expected failed status")

        old_gemini_key = os.environ.get("CODEX_RELAY_GEMINI_API_KEY")
        original_gemini_generate = relay.gemini_generate
        original_telegram_urlopen = relay.telegram_urlopen
        os.environ["CODEX_RELAY_GEMINI_API_KEY"] = "fake-gemini-key"
        relay.gemini_generate = lambda *_args, **_kwargs: "Polished answer"
        try:
            assert_true(
                relay.gemini_polish_answer("prompt", "raw answer", {"workdir": tmp}) == "Polished answer",
                "expected Gemini answer polish",
            )
            assert_true(
                relay.gemini_polish_answer("prompt", "SECRET_TOKEN=value", {"workdir": tmp}) == "SECRET_TOKEN=value",
                "expected Gemini polish to skip sensitive text",
            )
            assert_true(not relay.gemini_allows_text("set OPENAI_API_KEY=sk-12345678901234567890"), "expected Gemini secret guard")
        finally:
            relay.gemini_generate = original_gemini_generate
        try:
            captured: dict[str, object] = {}

            def fake_gemini_urlopen(request: object, timeout: int) -> FakeResponse:
                captured["timeout"] = timeout
                captured["body"] = json.loads(getattr(request, "data").decode())
                return FakeResponse(
                    [
                        b'{"candidates":[{"content":{"parts":[{"text":"Gemini ok"}]}}]}'
                    ]
                )

            os.environ["CODEX_RELAY_GEMINI_MAX_OUTPUT_TOKENS"] = "4096"
            relay.telegram_urlopen = fake_gemini_urlopen
            assert_true(relay.gemini_generate("hello") == "Gemini ok", "expected fake Gemini output")
            body = captured["body"]
            assert_true(
                isinstance(body, dict)
                and body["generationConfig"]["maxOutputTokens"] == 4096,
                "expected Gemini max output tokens in generation config",
            )
        finally:
            relay.telegram_urlopen = original_telegram_urlopen
            os.environ.pop("CODEX_RELAY_GEMINI_MAX_OUTPUT_TOKENS", None)
            if old_gemini_key is None:
                os.environ.pop("CODEX_RELAY_GEMINI_API_KEY", None)
            else:
                os.environ["CODEX_RELAY_GEMINI_API_KEY"] = old_gemini_key

        slow_codex = Path(tmp) / "slow-codex"
        slow_codex.write_text(
            "#!/bin/sh\n"
            "sleep 30\n"
        )
        slow_codex.chmod(0o700)
        os.environ["CODEX_BIN"] = str(slow_codex)
        cancel_event = threading.Event()

        def cancel_after_start(_process: object) -> None:
            cancel_event.set()

        try:
            answer, _session_id, stats = relay.run_codex(
                "cancel me",
                {"workdir": tmp, "name": "main"},
                cancel_event=cancel_event,
                process_callback=cancel_after_start,
            )
        finally:
            if old_codex_bin is None:
                os.environ.pop("CODEX_BIN", None)
            else:
                os.environ["CODEX_BIN"] = old_codex_bin
        assert_true("Canceled:" in answer, "expected canceled answer")
        assert_true(stats["last_status"] == "canceled", "expected canceled status")

        child_pid_file = Path(tmp) / "child.pid"
        process_tree_codex = Path(tmp) / "process-tree-codex"
        process_tree_codex.write_text(
            "#!/usr/bin/python3\n"
            "import pathlib, subprocess\n"
            f"pidfile = pathlib.Path({str(child_pid_file)!r})\n"
            "child = subprocess.Popen(['sleep', '30'], start_new_session=True)\n"
            "pidfile.write_text(str(child.pid))\n"
            "child.wait()\n"
        )
        process_tree_codex.chmod(0o700)
        os.environ["CODEX_BIN"] = str(process_tree_codex)
        cancel_event = threading.Event()

        def cancel_after_child(_process: object) -> None:
            deadline = time.time() + 5
            while not child_pid_file.exists() and time.time() < deadline:
                time.sleep(0.05)
            cancel_event.set()

        try:
            answer, _session_id, stats = relay.run_codex(
                "cancel process tree",
                {"workdir": tmp, "name": "main"},
                cancel_event=cancel_event,
                process_callback=cancel_after_child,
            )
            child_pid = int(child_pid_file.read_text())
            time.sleep(0.1)
            try:
                os.kill(child_pid, 0)
            except OSError:
                child_alive = False
            else:
                child_alive = True
        finally:
            if old_codex_bin is None:
                os.environ.pop("CODEX_BIN", None)
            else:
                os.environ["CODEX_BIN"] = old_codex_bin
        assert_true("Canceled:" in answer, "expected process tree cancel answer")
        assert_true(stats["last_status"] == "canceled", "expected process tree canceled status")
        assert_true(not child_alive, "expected descendant process to be stopped")

        if old_state_dir is None:
            os.environ.pop("CODEX_TELEGRAM_STATE_DIR", None)
        else:
            os.environ["CODEX_TELEGRAM_STATE_DIR"] = old_state_dir

    print("ok: smoke tests")
    return 0


def main() -> int:
    with isolated_env():
        return run_tests()


if __name__ == "__main__":
    raise SystemExit(main())
