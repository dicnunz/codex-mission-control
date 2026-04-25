#!/usr/bin/env python3
"""Fast local checks that do not touch Telegram or Codex."""

from __future__ import annotations

import tempfile
import os
import sys
import threading
import json
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import codex_relay as relay


def assert_true(value: object, message: str) -> None:
    if not value:
        raise SystemExit(message)


class FakeTelegram(relay.TelegramAPI):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def call(self, method: str, params: Optional[dict[str, object]] = None) -> dict[str, object]:
        self.calls.append((method, params or {}))
        return {"ok": True, "result": {}}


def main() -> int:
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
    os.environ.pop("CODEX_TELEGRAM_ALLOW_GROUP_CHATS", None)

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
    assert_true("reasoning effort: xhigh" in status, "expected default xhigh reasoning status")
    assert_true("running jobs: 0" in status, "expected running job count")
    assert_true("last run: ok; 1.2s; 1 image" in status, "expected last-run latency status")

    job = relay.RelayJob(123, "main", 2)
    relay.register_job(job)
    try:
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
                "reasoning_effort": "xhigh",
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

        fake_codex = Path(tmp) / "fake-codex"
        fake_codex.write_text(
            "#!/bin/sh\n"
            "out=''\n"
            "found_reasoning=0\n"
            "while [ \"$#\" -gt 0 ]; do\n"
            "  if [ \"$1\" = '--output-last-message' ]; then shift; out=\"$1\"; fi\n"
            "  if [ \"$1\" = 'model_reasoning_effort=\"xhigh\"' ]; then found_reasoning=1; fi\n"
            "  shift || true\n"
            "done\n"
            "if [ \"$found_reasoning\" != 1 ]; then echo 'missing reasoning effort' >&2; exit 7; fi\n"
            "printf 'fake answer\\n' > \"$out\"\n"
            "printf 'session id: 12345678-1234-1234-1234-123456789abc\\n' >&2\n"
        )
        fake_codex.chmod(0o700)
        old_codex_bin = os.environ.get("CODEX_BIN")
        old_reasoning = os.environ.get("CODEX_TELEGRAM_REASONING_EFFORT")
        os.environ["CODEX_BIN"] = str(fake_codex)
        os.environ["CODEX_TELEGRAM_REASONING_EFFORT"] = "xhigh"
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
        assert_true(stats["last_reasoning_effort"] == "xhigh", "expected reasoning stats")

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


if __name__ == "__main__":
    raise SystemExit(main())
