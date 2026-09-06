#!/usr/bin/env python3
"""Generated-page contracts: real hub data, safe commands, and isolated output."""

from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mission_control as mc


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.commands = []
        self.text = []
        self.tags = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        attrs = dict(attrs)
        if "data-copy" in attrs:
            self.commands.append(attrs["data-copy"])

    def handle_data(self, text):
        self.text.append(text)


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.hub = Path(self.temp.name) / "hub with 'quotes'"
        isolated_relay = patch.dict(os.environ, {
            "CODEX_RELAY_RUNTIME_DIR": str(Path(self.temp.name) / "relay"),
            "CODEX_RELAY_LABEL": f"com.codexrelay.dashboard-test-{os.getpid()}",
        })
        isolated_relay.start()
        self.addCleanup(isolated_relay.stop)
        mc.init_hub(self.hub)

    def render(self):
        with patch.object(mc.subprocess, "call", side_effect=AssertionError(
            "no-open dashboard must not invoke Relay status scripts"
        )):
            self.assertEqual(mc.dashboard_open(self.hub, no_open=True), 0)
        path = self.hub / "_ops" / "dashboard.html"
        self.assertTrue(path.exists(), "dashboard must live in the selected hub")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        return Page(path.read_text())

    def test_commands_target_selected_hub_and_preserve_full_owner(self):
        # macOS temporary paths traverse /var -> /private/var. Exercise the
        # same alias on every platform so command targeting checks identity.
        alias = Path(self.temp.name) / "hub-link"
        alias.symlink_to(self.hub, target_is_directory=True)
        self.hub = alias
        owner = 'Design chat; "review"'
        mc.claim_lane(self.hub, "BROWSER", owner, "review <script>draft</script>")
        page = self.render()
        commands = [shlex.split(command) for command in page.commands]
        release = next(command for command in commands if "release" in command)
        self.assertEqual(release[-3:], ["release", "BROWSER", owner])
        for command in commands:
            if Path(command[0]).name == "cmc":
                self.assertEqual(command[1:3], ["--hub", str(self.hub.resolve())])
        self.assertIn(owner, "".join(page.text))
        self.assertEqual(page.tags.count("script"), 1, "hub text must not become executable markup")

    def test_stale_and_unknown_lanes_are_visible_and_all_missions_are_rendered(self):
        mc.claim_lane(self.hub, "BROWSER", "OLD", "handoff", ttl=1)
        path = mc.lock_root(self.hub) / "BROWSER" / "lock.json"
        meta = json.loads(path.read_text())
        meta["created_epoch"] = 1
        path.write_text(json.dumps(meta))
        (mc.lock_root(self.hub) / "GITHUB").mkdir()
        mc.save_missions(self.hub, [
            {"call_sign": f"P{i}", "name": f"project-{i}", "path": f"/local/project-{i}"}
            for i in range(12)
        ])
        page = self.render()
        text = " ".join(page.text)
        for expected in ("Stale", "Unknown owner", "project-11", "snapshot"):
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
