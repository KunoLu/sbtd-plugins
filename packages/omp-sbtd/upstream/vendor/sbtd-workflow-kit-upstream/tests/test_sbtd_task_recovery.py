from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sbtd-workflow-onboard/scripts"))

from sbtd_task_state import TaskStateError, TaskStore


class TaskRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="sbtd-recovery-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "project"
        self.root.mkdir()
        self.env = {
            **os.environ,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
        }
        subprocess.run(
            ["git", "init", "-b", "main", str(self.root)],
            env=self.env,
            capture_output=True,
            check=True,
        )
        (self.root / ".gitignore").write_text("/.sbtd/\n/docs/handoffs/\n")

    def test_explicit_rebinding_preserves_blocked_ingress_and_existing_mode(
        self,
    ) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "resume", mode="lite", body="Keep this task.\n", confirmed=True
        )
        store.transition(
            "resume", "in-progress", reason="start", evidence="scope", confirmed=True
        )
        blocked = store.transition(
            "resume",
            "blocked",
            reason="pause",
            evidence="missing access",
            confirmed=True,
        )
        subprocess.run(
            ["git", "-C", str(self.root), "switch", "--orphan", "replacement"],
            env=self.env,
            capture_output=True,
            check=True,
        )
        before = (self.root / original.task_path).read_bytes()
        with self.assertRaises(TaskStateError):
            store.rebind(
                "resume",
                expected_branch="main",
                reason="explicit worktree choice",
                evidence="user confirmation",
            )
        self.assertEqual((self.root / original.task_path).read_bytes(), before)
        rebound = store.rebind(
            "resume",
            expected_branch="main",
            reason="explicit worktree choice",
            evidence="user confirmation",
            confirmed=True,
        )
        self.assertEqual(rebound.document.frontmatter["branch"], "replacement")
        self.assertEqual(rebound.document.frontmatter["workflow_mode"], "lite")
        self.assertEqual(rebound.document.frontmatter["status"], "blocked")
        self.assertEqual(rebound.document.events[:-1], blocked.document.events)
        self.assertEqual(
            (rebound.document.events[-1]["from"], rebound.document.events[-1]["to"]),
            ("blocked", "blocked"),
        )
        resumed = TaskStore(self.root).resume(
            "resume", reason="access restored", evidence="confirmed", confirmed=True
        )
        self.assertEqual(resumed.document.frontmatter["status"], "in-progress")

    def test_explicit_rebinding_preserves_a_historical_unknown_block_fact(self) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "resume-fact", mode="lite", body="Keep this task.\n", confirmed=True
        )
        legacy = original.document.updated(
            {"status": "blocked", "blocked_reason": "legacy blocker"},
            event={
                "at": "unknown",
                "from": "unknown",
                "to": "blocked",
                "reason": "legacy blocked fact",
                "evidence": "legacy task.json status",
            },
        )
        (self.root / original.task_path).write_text(legacy.text, encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.root), "switch", "--orphan", "replacement"],
            env=self.env,
            capture_output=True,
            check=True,
        )
        rebound = store.rebind(
            "resume-fact",
            expected_branch="main",
            reason="explicit worktree choice",
            evidence="user confirmation",
            confirmed=True,
        )
        self.assertEqual(rebound.document.frontmatter["branch"], "replacement")
        self.assertEqual(rebound.document.frontmatter["workflow_mode"], "lite")
        self.assertEqual(rebound.document.frontmatter["status"], "blocked")
        self.assertEqual(rebound.document.events[:-1], legacy.events)
        self.assertEqual(
            (rebound.document.events[-1]["from"], rebound.document.events[-1]["to"]),
            ("blocked", "blocked"),
        )
        resumed = TaskStore(self.root).resume(
            "resume-fact",
            target="in-progress",
            reason="user chose in-progress because the prior phase is unknown",
            evidence="explicit recovery choice",
            confirmed=True,
        )
        self.assertEqual(resumed.document.frontmatter["status"], "in-progress")
        self.assertEqual(
            [(event["from"], event["to"]) for event in resumed.document.events],
            [("unknown", "blocked"), ("blocked", "blocked"), ("blocked", "in-progress")],
        )

    def test_non_first_unknown_block_event_still_fails_closed(self) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "conflicted-block", body="Conflicted history.\n", confirmed=True
        )
        store.transition(
            "conflicted-block",
            "in-progress",
            reason="start",
            evidence="scope",
            confirmed=True,
        )
        conflicted = store.inspect("conflicted-block").document.updated(
            {"status": "blocked", "blocked_reason": "legacy blocker"},
            event={
                "at": "unknown",
                "from": "unknown",
                "to": "blocked",
                "reason": "legacy blocked fact",
                "evidence": "legacy task.json status",
            },
        )
        path = self.root / original.task_path
        path.write_text(conflicted.text, encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.root), "switch", "--orphan", "replacement"],
            env=self.env,
            capture_output=True,
            check=True,
        )
        before = path.read_bytes()
        with self.assertRaises(TaskStateError):
            store.rebind(
                "conflicted-block",
                expected_branch="main",
                reason="explicit worktree choice",
                evidence="user confirmation",
                confirmed=True,
            )
        self.assertEqual(path.read_bytes(), before)

    def test_normal_commits_do_not_change_binding_but_detached_commits_do(self) -> None:
        def commit(label):
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.root),
                    "-c",
                    "user.name=Synthetic Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "--allow-empty",
                    "-m",
                    label,
                ],
                env=self.env,
                capture_output=True,
                check=True,
            )
            return subprocess.check_output(
                ["git", "-C", str(self.root), "rev-parse", "HEAD"],
                env=self.env,
                text=True,
            ).strip()

        first = commit("first fixture")
        store = TaskStore(self.root)
        original = store.create("named", body="Named branch task.\n", confirmed=True)
        second = commit("second fixture")
        self.assertNotEqual(first, second)
        self.assertEqual(store.current_binding(), "main")
        store.transition(
            "named",
            "in-progress",
            reason="same branch",
            evidence="normal commit",
            confirmed=True,
        )
        subprocess.run(
            ["git", "-C", str(self.root), "checkout", "--detach", first],
            env=self.env,
            capture_output=True,
            check=True,
        )
        detached = store.create("detached", body="Detached task.\n", confirmed=True)
        self.assertEqual(detached.document.frontmatter["branch"], "detached:" + first)
        subprocess.run(
            ["git", "-C", str(self.root), "checkout", "--detach", second],
            env=self.env,
            capture_output=True,
            check=True,
        )
        before = (self.root / detached.task_path).read_bytes()
        with self.assertRaises(TaskStateError):
            store.transition(
                "detached",
                "in-progress",
                reason="different detached head",
                evidence="not rebound",
                confirmed=True,
            )
        self.assertEqual((self.root / detached.task_path).read_bytes(), before)
        rebound = store.rebind(
            "detached",
            expected_branch="detached:" + first,
            reason="user chose this exact checkout",
            evidence="explicit choice",
            confirmed=True,
        )
        self.assertEqual(rebound.document.frontmatter["branch"], "detached:" + second)
        self.assertTrue((self.root / original.task_path).is_file())


if __name__ == "__main__":
    unittest.main()
