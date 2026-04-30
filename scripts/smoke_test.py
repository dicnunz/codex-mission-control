#!/usr/bin/env python3
"""Fast local checks that do not touch Telegram or Codex."""

from __future__ import annotations

import tempfile
import os
import sys
import threading
import json
import time
import importlib.util
import contextlib
import io
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import codex_relay as relay
import mission_control

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
ENV_EXACT = {"CODEX_BIN"}
TEST_ENV = {
    "CODEX_TELEGRAM_MODEL": "",
    "CODEX_TELEGRAM_REASONING_EFFORT": "high",
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
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        hub = tmp_path / "hub"
        project = tmp_path / "sample-app"
        project.mkdir()
        (project / ".git").mkdir()
        (project / "README.md").write_text("# Sample App\n")
        weak = tmp_path / "notes-only"
        weak.mkdir()
        (weak / "README.md").write_text("# Notes\n")
        old_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            assert_true(not mission_control.likely_project(weak), "expected README-only folder to be ignored")
            init_text = mission_control.init_hub(hub)
            assert_true("Mission Control initialized" in init_text, "expected hub init")
            assert_true((hub / "_ops" / "COMMAND_CENTER.md").exists(), "expected command center template")
            assert_true((hub / "_ops" / "CODEX_OPERATING_SPEC.md").exists(), "expected Codex operating spec")
            discover_text = mission_control.discover_projects(hub, [str(project)], include_defaults=False)
            assert_true("added: 1" in discover_text, "expected one discovered project")
            missions = mission_control.load_missions(hub)
            assert_true(len(missions) == 1, "expected one mission")
            link = Path(missions[0]["link"])
            assert_true(link.exists() or link.is_symlink(), "expected mission index link")
            code, text = mission_control.claim_lane(hub, "BROWSER", "TEST", "smoke")
            assert_true(code == 0 and "acquired" in text, "expected lane claim")
            code, text = mission_control.claim_lane(hub, "BROWSER", "OTHER", "smoke")
            assert_true(code == 1 and "held" in text, "expected double claim block")
            status = mission_control.status_text(hub)
            assert_true("missions: 1" in status, "expected status mission count")
            assert_true("locks: 1 held" in status, "expected status lock count")
            lock_file = hub / "_ops" / ".surface_locks" / "BROWSER" / "lock.json"
            lock_meta = json.loads(lock_file.read_text())
            lock_meta["created_epoch"] = time.time() - 9999
            lock_file.write_text(json.dumps(lock_meta))
            stale_status = mission_control.status_text(hub)
            assert_true("1 stale" in stale_status and "[stale]" in stale_status, "expected stale lock status")
            stale_lanes = mission_control.lanes_text(hub)
            assert_true("BROWSER: held" in stale_lanes and "[stale]" in stale_lanes, "expected stale lane status")
            stale_doctor = mission_control.doctor_text(hub)
            assert_true("stale lock: BROWSER" in stale_doctor, "expected doctor stale lock detail")
            packet = mission_control.packet_text("TEST", "post", "x.com", "hello", "proof.png", "public", "now", "stop after post")
            assert_true("Exact action: post" in packet and "Stop condition" in packet, "expected complete packet")
            instructions = mission_control.instructions_text(hub)
            assert_true("Codex Operating Overlay" in instructions, "expected optimized instructions")
            doctor = mission_control.doctor_text(hub)
            assert_true("ops files: ok" in doctor, "expected doctor ok")
            old_runtime_dir = os.environ.get("CODEX_RELAY_RUNTIME_DIR")
            old_relay_label = os.environ.get("CODEX_RELAY_LABEL")
            runtime = tmp_path / "runtime"
            runtime.mkdir()
            (runtime / "codex_relay.py").write_text("# relay\n")
            (runtime / ".env").write_text("TELEGRAM_BOT_TOKEN=fake\n")
            os.environ["CODEX_RELAY_RUNTIME_DIR"] = str(runtime)
            os.environ["CODEX_RELAY_LABEL"] = "com.codexrelay.test-missing"
            try:
                relay_state = mission_control.relay_state()
                assert_true(relay_state.startswith("installed,"), "expected runtime Relay install detection")
            finally:
                if old_runtime_dir is None:
                    os.environ.pop("CODEX_RELAY_RUNTIME_DIR", None)
                else:
                    os.environ["CODEX_RELAY_RUNTIME_DIR"] = old_runtime_dir
                if old_relay_label is None:
                    os.environ.pop("CODEX_RELAY_LABEL", None)
                else:
                    os.environ["CODEX_RELAY_LABEL"] = old_relay_label
            adopt_preview = mission_control.adopt_agents(hub)
            assert_true("would create" in adopt_preview, "expected dry-run adoption")
            adopt_write = mission_control.adopt_agents(hub, write=True)
            assert_true("wrote" in adopt_write, "expected adoption write")
            agents_text = (project / "AGENTS.md").read_text()
            assert_true("codex-mission-control:start" in agents_text, "expected managed agents block")
            merge = mission_control.merge_outboxes(hub)
            assert_true("merged outboxes: 1" in merge, "expected outbox merge")
            assert_true("Outbox" in (hub / "_ops" / "GLOBAL_DASHBOARD.md").read_text(), "expected dashboard merge")
            assert_true((project / "README.md").read_text() == "# Sample App\n", "expected merge not to touch mission files")
            old_hub_env = os.environ.get("CODEX_MISSION_CONTROL_HOME")
            os.environ["CODEX_MISSION_CONTROL_HOME"] = str(hub)
            try:
                assert_true("missions: 1" in relay.mission_command_text("status"), "expected relay mission status")
                assert_true("Codex Mission Control doctor" in relay.mission_command_text("doctor"), "expected relay mission doctor")
                assert_true("Codex Mission Control doctor" in relay.mission_command_text("health"), "expected relay mission health")
                assert_true("BROWSER" in relay.mission_command_text("lanes"), "expected relay mission lanes")
                assert_true("sample-app" in relay.mission_command_text("projects"), "expected relay mission projects")
            finally:
                if old_hub_env is None:
                    os.environ.pop("CODEX_MISSION_CONTROL_HOME", None)
                else:
                    os.environ["CODEX_MISSION_CONTROL_HOME"] = old_hub_env
        finally:
            os.chdir(old_cwd)

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
    assert_true("reasoning effort: high" in status, "expected default high reasoning status")
    assert_true("speed: standard" in status, "expected default standard speed status")
    assert_true("running jobs: 0" in status, "expected running job count")
    assert_true("last run: ok; 1.2s; 1 image" in status, "expected last-run latency status")
    health = relay.health_text()
    assert_true("health:" in health, "expected health output")
    assert_true("deep check: /tools" in health, "expected health to point at deep check")

    old_urlopen = relay.urllib.request.urlopen
    try:
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

    job = relay.RelayJob(123, "main", 2)
    relay.register_job(job)
    try:
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
        os.environ["CODEX_BIN"] = str(fake_codex)
        os.environ["CODEX_TELEGRAM_REASONING_EFFORT"] = "high"
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
        assert_true(answer == "fake answer", "expected fake Codex answer")
        assert_true(session_id.endswith("123456789abc"), "expected captured session id")
        assert_true(stats["last_status"] == "ok", "expected ok run status")
        assert_true("last_latency_seconds" in stats, "expected latency stats")
        assert_true(stats["last_reasoning_effort"] == "high", "expected reasoning stats")
        assert_true(stats["last_speed"] == "standard", "expected speed stats")

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

        stale_resume_codex = Path(tmp) / "stale-resume-codex"
        stale_resume_codex.write_text(
            "#!/bin/sh\n"
            "out=''\n"
            "resume=0\n"
            "for arg in \"$@\"; do\n"
            "  if [ \"$arg\" = '--output-last-message' ]; then next_out=1; continue; fi\n"
            "  if [ \"${next_out:-0}\" = 1 ]; then out=\"$arg\"; next_out=0; fi\n"
            "  if [ \"$arg\" = 'resume' ]; then resume=1; fi\n"
            "done\n"
            "if [ \"$resume\" = 1 ]; then\n"
            "  echo 'Error: thread/resume failed: no rollout found for thread id old-session' >&2\n"
            "  exit 1\n"
            "fi\n"
            "printf 'recovered answer\\n' > \"$out\"\n"
            "printf 'session id: 87654321-4321-4321-4321-cba987654321\\n' >&2\n"
        )
        stale_resume_codex.chmod(0o700)
        os.environ["CODEX_BIN"] = str(stale_resume_codex)
        try:
            answer, session_id, stats = relay.run_codex(
                "recover",
                {"workdir": tmp, "name": "main", "session_id": "old-session"},
            )
        finally:
            if old_codex_bin is None:
                os.environ.pop("CODEX_BIN", None)
            else:
                os.environ["CODEX_BIN"] = old_codex_bin
        assert_true(answer == "recovered answer", "expected stale resume recovery")
        assert_true(session_id.endswith("cba987654321"), "expected fresh session id")
        assert_true(stats["last_status"] == "ok", "expected recovered ok status")

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
