#!/usr/bin/env python3
"""Fast local checks that do not touch Telegram or Codex."""

from __future__ import annotations

import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import codex_relay as relay


def assert_true(value: object, message: str) -> None:
    if not value:
        raise SystemExit(message)


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
    assert_true(relay.extract_session_id("Session ID: 12345678-1234-1234-1234-123456789abc"), "expected session id")

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "private.bin"
        relay.write_private_bytes(target, b"ok")
        assert_true(target.read_bytes() == b"ok", "expected private byte write")
        assert_true(oct(target.stat().st_mode & 0o777) == "0o600", "expected private file mode")

    print("ok: smoke tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
