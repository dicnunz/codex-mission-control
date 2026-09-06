#!/usr/bin/env python3
"""Lane regressions on real temporary hubs; no Relay or user state access."""

from __future__ import annotations

import json
import multiprocessing
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mission_control as mc


def lane_worker(hub, owner, action, started, done, results, paused=None, resume=None):
    """Pause after a real metadata read to expose the former check/delete race."""
    original_read = mc.read_lock_meta

    def read_and_pause(path):
        value = original_read(path)
        if paused is not None:
            paused.set()
            if not resume.wait(10):
                raise TimeoutError("test did not resume metadata reader")
        return value

    try:
        started.set()
        with patch.object(mc, "read_lock_meta", read_and_pause):
            if action == "release":
                result = mc.release_lane(Path(hub), "BROWSER", owner)
            else:
                result = mc.claim_lane(Path(hub), "BROWSER", owner, "test", ttl=1800)
        results.put((owner, result))
    except Exception as exc:
        results.put((owner, (-1, repr(exc))))
    finally:
        done.set()


class LaneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.hub = Path(self.temp.name) / "hub"
        mc.init_hub(self.hub)
        self.path = mc.lock_root(self.hub) / "BROWSER"
        self.ctx = multiprocessing.get_context("spawn")

    def seed(self, ttl=1800, age=60):
        self.assertEqual(mc.claim_lane(self.hub, "BROWSER", "OLD", "test", ttl)[0], 0)
        meta = mc.read_lock_meta(self.path)
        meta["created_epoch"] = time.time() - age
        (self.path / "lock.json").write_text(json.dumps(meta))

    def test_contender_cannot_shorten_current_lease(self):
        self.seed(ttl=3600)
        code, _ = mc.claim_lane(self.hub, "BROWSER", "NEW", "test", ttl=1)
        self.assertEqual(code, 1)
        self.assertEqual(mc.read_lock_meta(self.path)["owner"], "OLD")

    def test_expired_lease_uses_current_owners_timeout(self):
        self.seed(ttl=1)
        code, _ = mc.claim_lane(self.hub, "BROWSER", "NEW", "test", ttl=3600)
        self.assertEqual(code, 0)
        self.assertEqual(mc.read_lock_meta(self.path)["owner"], "NEW")

    def test_zero_ttl_does_not_expire(self):
        self.seed(ttl=0)
        self.assertEqual(mc.claim_lane(self.hub, "BROWSER", "NEW", "test", ttl=1)[0], 1)

    def test_invalid_metadata_remains_held(self):
        self.seed()
        (self.path / "lock.json").write_text('{"ttl_seconds": "bad", "owner": "OLD"}')
        self.assertFalse(mc.lock_meta_is_stale(mc.read_lock_meta(self.path)))
        self.assertEqual(mc.claim_lane(self.hub, "BROWSER", "NEW", "test")[0], 1)

    def test_missing_metadata_is_not_reported_as_clear_or_released(self):
        self.path.mkdir(parents=True)
        self.assertIn("BROWSER: held", mc.lanes_text(self.hub))
        self.assertEqual(mc.release_lane(self.hub, "BROWSER", "ANYONE")[0], 1)
        self.assertTrue(self.path.exists())

    def test_invalid_claim_does_not_create_a_lock(self):
        for owner, ttl in [("  ", 1800), ("NEW", -1)]:
            with self.subTest(owner=owner, ttl=ttl), self.assertRaises(ValueError):
                mc.claim_lane(self.hub, "BROWSER", owner, "test", ttl)
        self.assertFalse(self.path.exists())

    def racing_operations(self, first_action):
        self.seed(ttl=1, age=3600)
        paused, resume = self.ctx.Event(), self.ctx.Event()
        started_a, done_a = self.ctx.Event(), self.ctx.Event()
        started_b, done_b = self.ctx.Event(), self.ctx.Event()
        results = self.ctx.Queue()
        owner_a = "OLD" if first_action == "release" else "FIRST"
        first = self.ctx.Process(target=lane_worker, args=(
            str(self.hub), owner_a, first_action, started_a, done_a, results, paused, resume,
        ))
        second = self.ctx.Process(target=lane_worker, args=(
            str(self.hub), "SECOND", "claim", started_b, done_b, results,
        ))
        try:
            first.start()
            self.assertTrue(paused.wait(10), "first operation never read the lock")
            second.start()
            self.assertTrue(started_b.wait(10), "second process never started")
            # The other process must not finish inside the first transaction.
            # Events control the race; this bounded wait only checks exclusion.
            finished_while_paused = done_b.wait(0.25)
            resume.set()
            first.join(10)
            second.join(10)
            self.assertFalse(first.is_alive() or second.is_alive(), "lane operation hung")
            outcomes = dict(results.get(timeout=2) for _ in range(2))
            self.assertFalse(finished_while_paused, f"overlapping lane transactions: {outcomes}")
            return outcomes
        finally:
            resume.set()
            for process in (first, second):
                if process.pid:
                    if process.is_alive():
                        process.terminate()
                    process.join(5)
            results.close()

    def test_two_stale_claimants_cannot_both_acquire(self):
        outcomes = self.racing_operations("claim")
        self.assertEqual(outcomes["FIRST"][0], 0)
        self.assertEqual(outcomes["SECOND"][0], 1)
        self.assertEqual(mc.read_lock_meta(self.path)["owner"], "FIRST")

    def test_release_cannot_delete_a_replacement_claim(self):
        outcomes = self.racing_operations("release")
        self.assertEqual(outcomes["OLD"][0], 0)
        self.assertEqual(outcomes["SECOND"][0], 0)
        self.assertEqual(mc.read_lock_meta(self.path)["owner"], "SECOND")

    def test_process_exit_does_not_strand_the_transaction_guard(self):
        self.seed(ttl=1, age=3600)
        paused, resume = self.ctx.Event(), self.ctx.Event()
        started, finished = self.ctx.Event(), self.ctx.Event()
        results = self.ctx.Queue()
        process = self.ctx.Process(target=lane_worker, args=(
            str(self.hub), "FIRST", "claim", started, finished,
            results, paused, resume,
        ))
        try:
            process.start()
            self.assertTrue(paused.wait(10))
            process.terminate()
            process.join(5)
            # Use another process with a deadline so a stranded guard fails
            # clearly instead of hanging the test runner.
            done = self.ctx.Event()
            next_started = self.ctx.Event()
            next_process = self.ctx.Process(target=lane_worker, args=(
                str(self.hub), "SECOND", "claim", next_started, done, results,
            ))
            next_process.start()
            try:
                self.assertTrue(done.wait(10), "exited process stranded the guard")
                self.assertEqual(results.get(timeout=2)[1][0], 0)
                self.assertEqual(mc.read_lock_meta(self.path)["owner"], "SECOND")
            finally:
                if next_process.is_alive():
                    next_process.terminate()
                next_process.join(5)
        finally:
            if process.is_alive():
                process.terminate()
            process.join(5)
            results.close()


if __name__ == "__main__":
    unittest.main()
