from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sbtd-workflow-onboard" / "scripts"))

from sbtd_task_state import TaskSnapshot, TaskStateError, TaskStore


class TaskStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="sbtd-task-state-test-")
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
        (self.root / ".gitignore").write_text("/.sbtd/\n", encoding="utf-8")

    def _case_variant_transfer_records(
        self,
        source: TaskSnapshot,
        source_directory: str,
        variant_directory: str,
    ) -> tuple[TaskSnapshot, ...]:
        variant = self.root / variant_directory
        if not variant.exists():
            (self.root / source_directory).rename(variant)
        suffix = source.task_path.removeprefix(source_directory + "/")
        return (TaskSnapshot(f"{variant_directory}/{suffix}", source.document),)

    def test_default_creation_is_persisted_and_selected_without_identity(self) -> None:
        store = TaskStore(self.root)
        created = store.create(
            "fix-parser", body="# Fix parser\n\nKeep narrow scope.\n", confirmed=True
        )
        resumed = TaskStore(self.root).inspect()
        self.assertEqual(resumed.task_path, ".sbtd/tasks/fix-parser/task.md")
        self.assertEqual(resumed.document.text, created.document.text)
        self.assertEqual(resumed.document.frontmatter["id"], "fix-parser")
        self.assertEqual(resumed.document.frontmatter["workflow_mode"], "default")
        self.assertEqual(resumed.document.frontmatter["mode_source"], "default")
        self.assertEqual(resumed.document.frontmatter["status"], "planned")
        self.assertEqual(resumed.document.frontmatter["branch"], "main")
        self.assertIsNotNone(resumed.document.frontmatter["created_at"])
        self.assertEqual(resumed.document.events, ())
        self.assertIn("Keep narrow scope.", resumed.document.text)

    def test_partial_ignore_protection_never_authorizes_local_writes(self) -> None:
        for protected in (
            "/.sbtd/active-task.json",
            "/.sbtd/tasks/",
            "/.sbtd/*\n!/.sbtd/tasks/\n/.sbtd/tasks/*\n!/.sbtd/tasks/unprotected-task/",
        ):
            with self.subTest(protected=protected):
                ignore = self.root / ".gitignore"
                ignore.write_text(protected + "\n", encoding="utf-8")
                before = ignore.read_bytes()
                with self.assertRaises(TaskStateError):
                    TaskStore(self.root).create(
                        "unprotected-task", body="Task\n", confirmed=True
                    )
                self.assertFalse((self.root / ".sbtd").exists())
                self.assertEqual(ignore.read_bytes(), before)

    def test_blocked_recovery_survives_repeat_reason_mode_change_and_new_store(
        self,
    ) -> None:
        store = TaskStore(self.root)
        store.create(
            "recover-check", body="Acceptance is still pending.\n", confirmed=True
        )
        store.transition(
            "recover-check",
            "in-progress",
            reason="started",
            evidence="scope agreed",
            confirmed=True,
        )
        store.transition(
            "recover-check",
            "checking",
            reason="implemented",
            evidence="candidate exists",
            confirmed=True,
        )
        store.transition(
            "recover-check",
            "blocked",
            reason="waiting on access",
            evidence="permission missing",
            confirmed=True,
        )
        store.transition(
            "recover-check",
            "blocked",
            reason="still waiting",
            evidence="same permission missing",
            confirmed=True,
        )
        store.set_mode(
            "recover-check", "lite", note="user chose a shorter process", confirmed=True
        )

        resumed = TaskStore(self.root).resume(
            "recover-check",
            reason="access granted",
            evidence="permission confirmed",
            confirmed=True,
        )
        self.assertEqual(resumed.document.frontmatter["status"], "checking")
        self.assertEqual(resumed.document.frontmatter["workflow_mode"], "lite")
        self.assertEqual(resumed.document.frontmatter["mode_source"], "user")
        self.assertIsNone(resumed.document.frontmatter.get("blocked_reason"))
        self.assertEqual(
            [(event["from"], event["to"]) for event in resumed.document.events],
            [
                ("planned", "in-progress"),
                ("in-progress", "checking"),
                ("checking", "blocked"),
                ("blocked", "checking"),
            ],
        )
        self.assertIn("Acceptance is still pending.", resumed.document.text)

    def test_unknown_block_history_requires_a_real_choice_and_reason(self) -> None:
        store = TaskStore(self.root)
        selected = store.create(
            "legacy-block", body="Historical evidence is unavailable.\n", confirmed=True
        )
        legacy = selected.document.updated(
            {"status": "blocked", "blocked_reason": "legacy blocker"}
        )
        path = self.root / selected.task_path
        path.write_text(legacy.text, encoding="utf-8")
        before = path.read_bytes()
        with self.assertRaises(TaskStateError):
            store.resume(
                "legacy-block",
                reason="permission granted",
                evidence="user confirmation",
                confirmed=True,
            )
        self.assertEqual(path.read_bytes(), before)
        with self.assertRaises(TaskStateError):
            store.resume(
                "legacy-block",
                target="planned",
                reason=" ",
                evidence="user confirmation",
                confirmed=True,
            )
        self.assertEqual(path.read_bytes(), before)

        resumed = store.resume(
            "legacy-block",
            target="planned",
            reason="user chose planned because the prior phase is unknown",
            evidence="explicit recovery choice",
            confirmed=True,
        )
        self.assertEqual(resumed.document.frontmatter["status"], "planned")
        self.assertEqual(
            [(event["from"], event["to"]) for event in resumed.document.events],
            [("blocked", "planned")],
        )
        self.assertIn("Historical evidence is unavailable.", resumed.document.text)
        after = path.read_bytes()
        store.resume(
            "legacy-block",
            target="planned",
            reason="same choice",
            evidence="same confirmation",
            confirmed=True,
        )
        self.assertEqual(path.read_bytes(), after)

    def test_non_git_first_write_requires_only_narrow_protection_authorization(
        self,
    ) -> None:
        shutil.rmtree(self.root / ".git")
        (self.root / ".gitignore").unlink()
        store = TaskStore(self.root)
        with self.assertRaises(TaskStateError):
            store.create("local-note", body="A non-Git task.\n", confirmed=True)
        self.assertEqual(list(self.root.iterdir()), [])
        with self.assertRaises(TaskStateError):
            store.protect_local_state()
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertTrue(store.protect_local_state(confirmed=True))
        self.assertEqual((self.root / ".gitignore").read_text(), "/.sbtd/\n")
        self.assertFalse((self.root / ".sbtd").exists())
        created = store.create("local-note", body="A non-Git task.\n", confirmed=True)
        self.assertIsNone(created.document.frontmatter["branch"])
        self.assertEqual(TaskStore(self.root).inspect().task_path, created.task_path)
        self.assertFalse((self.root / ".git").exists())

    def test_array_shaped_pointer_is_not_reinterpreted_and_overwritten(self) -> None:
        store = TaskStore(self.root)
        first = store.create("first", body="First task\n", confirmed=True)
        pointer = self.root / ".sbtd/active-task.json"
        malformed = json.dumps(
            [
                ["schema_version", 1],
                ["task_id", "first"],
                ["task_path", first.task_path],
            ]
        ).encode("utf-8")
        pointer.write_bytes(malformed)
        with self.assertRaises(TaskStateError):
            store.create("second", body="Second task\n", confirmed=True)
        self.assertEqual(pointer.read_bytes(), malformed)
        self.assertFalse((self.root / ".sbtd/tasks/second").exists())

    def test_reopening_child_preserves_completion_and_reopens_done_ancestors(
        self,
    ) -> None:
        store = TaskStore(self.root)
        store.create("parent", body="Parent acceptance.\n", confirmed=True)
        store.create(
            "child", body="Child acceptance.\n", parent="parent", confirmed=True
        )
        completed = {}
        for task_id in ("child", "parent"):
            for status in ("in-progress", "checking", "done"):
                snapshot = store.transition(
                    task_id,
                    status,
                    reason="actual task progress",
                    evidence="recorded acceptance",
                    confirmed=True,
                )
            completed[task_id] = snapshot.document.frontmatter["completed_at"]

        reopened = store.reopen(
            "child",
            reason="new acceptance gap",
            evidence="reproduction confirmed",
            confirmed=True,
        )
        self.assertEqual(reopened.document.frontmatter["status"], "planned")
        for task_id in ("parent", "child"):
            current = TaskStore(self.root).inspect(task_id)
            self.assertEqual(current.document.frontmatter["status"], "planned")
            self.assertIsNone(current.document.frontmatter["completed_at"])
            self.assertEqual(
                [
                    event["at"]
                    for event in current.document.events
                    if event["to"] == "done"
                ],
                [completed[task_id]],
            )
            self.assertEqual(
                (
                    current.document.events[-1]["from"],
                    current.document.events[-1]["to"],
                ),
                ("done", "planned"),
            )
        before_retry = (self.root / reopened.task_path).read_bytes()
        store.reopen(
            "child", reason="same gap", evidence="same reproduction", confirmed=True
        )
        self.assertEqual((self.root / reopened.task_path).read_bytes(), before_retry)

    def test_parent_cannot_enter_integration_with_unfinished_descendants(self) -> None:
        store = TaskStore(self.root)
        parent = store.create("parent", body="Parent\n", confirmed=True)
        store.create("child", body="Child\n", parent="parent", confirmed=True)
        store.transition(
            "parent",
            "in-progress",
            reason="summarizing children",
            evidence="child task exists",
            confirmed=True,
        )
        before = (self.root / parent.task_path).read_bytes()
        with self.assertRaises(TaskStateError):
            store.transition(
                "parent",
                "checking",
                reason="premature integration",
                evidence="child is not finished",
                confirmed=True,
            )
        self.assertEqual((self.root / parent.task_path).read_bytes(), before)

    def test_cancellation_is_terminal_keeps_completion_empty_and_never_cascades(
        self,
    ) -> None:
        store = TaskStore(self.root)
        store.create("parent", body="Parent\n", confirmed=True)
        child = store.create(
            "child", body="Child\n", parent="parent", confirmed=True
        )
        for status in ("in-progress", "checking", "done"):
            store.transition(
                "child", status, reason="progress", evidence="accepted", confirmed=True
            )
        store.transition(
            "parent",
            "in-progress",
            reason="summarizing children",
            evidence="child task exists",
            confirmed=True,
        )
        child_before = (self.root / child.task_path).read_bytes()

        cancelled = store.transition(
            "parent",
            "cancelled",
            reason="scope withdrawn",
            evidence="sponsor decision recorded",
            confirmed=True,
        )
        self.assertEqual(cancelled.document.frontmatter["status"], "cancelled")
        self.assertIsNone(cancelled.document.frontmatter["completed_at"])
        self.assertEqual(
            (
                cancelled.document.events[-1]["from"],
                cancelled.document.events[-1]["to"],
            ),
            ("in-progress", "cancelled"),
        )
        self.assertEqual((self.root / child.task_path).read_bytes(), child_before)
        self.assertEqual(
            store.inspect("child").document.frontmatter["status"], "done"
        )
        for target in ("planned", "in-progress", "checking", "done", "blocked"):
            with self.subTest(target=target), self.assertRaises(TaskStateError):
                store.transition(
                    "parent",
                    target,
                    reason="no longer applicable",
                    evidence="terminal record",
                    confirmed=True,
                )
        before_retry = (self.root / cancelled.task_path).read_bytes()
        repeated = store.transition(
            "parent",
            "cancelled",
            reason="same withdrawal",
            evidence="same decision",
            confirmed=True,
        )
        self.assertEqual(repeated.document.text, cancelled.document.text)
        self.assertEqual((self.root / cancelled.task_path).read_bytes(), before_retry)

    def test_cancelling_planned_checking_and_blocked_records_no_completion(
        self,
    ) -> None:
        store = TaskStore(self.root)
        for source, path in (
            ("planned", ()),
            ("checking", ("in-progress", "checking")),
            ("blocked", ("in-progress", "blocked")),
        ):
            task_id = f"cancel-from-{source}"
            with self.subTest(source=source):
                store.create(task_id, body=f"Cancel from {source}.\n", confirmed=True)
                for status in path:
                    store.transition(
                        task_id,
                        status,
                        reason="recorded progress",
                        evidence="recorded evidence",
                        confirmed=True,
                    )
                cancelled = store.transition(
                    task_id,
                    "cancelled",
                    reason="scope withdrawn",
                    evidence="decision record",
                    confirmed=True,
                )
                frontmatter = cancelled.document.frontmatter
                self.assertEqual(frontmatter["status"], "cancelled")
                self.assertIsNone(frontmatter["completed_at"])
                self.assertIsNone(frontmatter.get("blocked_reason"))
                self.assertEqual(
                    (
                        cancelled.document.events[-1]["from"],
                        cancelled.document.events[-1]["to"],
                    ),
                    (source, "cancelled"),
                )

    def test_completed_tasks_cannot_be_cancelled_silently(self) -> None:
        store = TaskStore(self.root)
        original = store.create("finished", body="Done work.\n", confirmed=True)
        for status in ("in-progress", "checking", "done"):
            store.transition(
                "finished",
                status,
                reason="progress",
                evidence="accepted",
                confirmed=True,
            )
        before = (self.root / original.task_path).read_bytes()
        with self.assertRaises(TaskStateError):
            store.transition(
                "finished",
                "cancelled",
                reason="late withdrawal",
                evidence="decision",
                confirmed=True,
            )
        self.assertEqual((self.root / original.task_path).read_bytes(), before)
        self.assertEqual(
            store.inspect("finished").document.frontmatter["status"], "done"
        )

    def test_unfinished_descendants_guard_cancellation_and_cancelled_counts_terminal(
        self,
    ) -> None:
        store = TaskStore(self.root)
        parent = store.create("parent", body="Parent\n", confirmed=True)
        store.create("child", body="Child\n", parent="parent", confirmed=True)
        store.transition(
            "parent",
            "in-progress",
            reason="summarizing children",
            evidence="child task exists",
            confirmed=True,
        )
        before = (self.root / parent.task_path).read_bytes()
        with self.assertRaises(TaskStateError):
            store.transition(
                "parent",
                "cancelled",
                reason="premature withdrawal",
                evidence="child is not finished",
                confirmed=True,
            )
        with self.assertRaises(TaskStateError):
            store.select("parent", confirmed=True)
        self.assertEqual((self.root / parent.task_path).read_bytes(), before)

        store.transition(
            "child",
            "cancelled",
            reason="child scope withdrawn",
            evidence="decision",
            confirmed=True,
        )
        cancelled = store.transition(
            "parent",
            "cancelled",
            reason="parent scope withdrawn",
            evidence="decision",
            confirmed=True,
        )
        self.assertEqual(cancelled.document.frontmatter["status"], "cancelled")

        store.create("integration", body="Parent\n", confirmed=True)
        store.create(
            "integration-child",
            body="Child\n",
            parent="integration",
            confirmed=True,
        )
        store.transition(
            "integration-child",
            "cancelled",
            reason="child scope withdrawn",
            evidence="decision",
            confirmed=True,
        )
        selected = store.select("integration", confirmed=True)
        self.assertEqual(selected.task_path, ".sbtd/tasks/integration/task.md")
        for status in ("in-progress", "checking", "done"):
            snapshot = store.transition(
                "integration",
                status,
                reason="progress",
                evidence="accepted",
                confirmed=True,
            )
        self.assertEqual(snapshot.document.frontmatter["status"], "done")
        self.assertIsNotNone(snapshot.document.frontmatter["completed_at"])

    def test_new_child_under_cancelled_ancestor_requires_explicit_reopen(self) -> None:
        store = TaskStore(self.root)
        store.create("parent", body="Parent\n", confirmed=True)
        store.transition(
            "parent",
            "cancelled",
            reason="scope withdrawn",
            evidence="decision",
            confirmed=True,
        )
        with self.assertRaises(TaskStateError):
            store.create("child", body="Child\n", parent="parent", confirmed=True)
        self.assertFalse((self.root / ".sbtd/tasks/child").exists())
        store.reopen(
            "parent",
            reason="scope restored",
            evidence="user request",
            confirmed=True,
        )
        child = store.create("child", body="Child\n", parent="parent", confirmed=True)
        self.assertEqual(child.document.frontmatter["parent"], "parent")

    def test_reopening_cancelled_preserves_cancellation_and_reopens_terminal_ancestors(
        self,
    ) -> None:
        store = TaskStore(self.root)
        store.create("parent", body="Parent\n", confirmed=True)
        store.create("child", body="Child\n", parent="parent", confirmed=True)
        for task_id in ("child", "parent"):
            store.transition(
                task_id,
                "cancelled",
                reason="scope withdrawn",
                evidence="decision",
                confirmed=True,
            )

        reopened = store.reopen(
            "child",
            reason="scope restored",
            evidence="user request",
            confirmed=True,
        )
        self.assertEqual(reopened.document.frontmatter["status"], "planned")
        for task_id in ("parent", "child"):
            current = TaskStore(self.root).inspect(task_id)
            self.assertEqual(current.document.frontmatter["status"], "planned")
            self.assertIsNone(current.document.frontmatter["completed_at"])
            cancellations = [
                event
                for event in current.document.events
                if event["to"] == "cancelled" and event["from"] != "cancelled"
            ]
            self.assertEqual(len(cancellations), 1)
            self.assertEqual(
                (
                    current.document.events[-1]["from"],
                    current.document.events[-1]["to"],
                ),
                ("cancelled", "planned"),
            )
        before_retry = (self.root / reopened.task_path).read_bytes()
        store.reopen(
            "child",
            reason="same restoration",
            evidence="same request",
            confirmed=True,
        )
        self.assertEqual((self.root / reopened.task_path).read_bytes(), before_retry)

    def test_reopen_does_not_infer_cancellation_time_from_updated_at(self) -> None:
        store = TaskStore(self.root)
        selected = store.create(
            "legacy-cancelled", body="Historical cancellation without an event.\n",
            confirmed=True,
        )
        legacy = selected.document.updated(
            {"status": "cancelled", "created_at": None, "completed_at": None}
        )
        (self.root / selected.task_path).write_text(legacy.text, encoding="utf-8")

        reopened = store.reopen(
            "legacy-cancelled",
            reason="operator explicitly restores the scope",
            evidence="reopening request",
            confirmed=True,
        )

        self.assertEqual(reopened.document.frontmatter["status"], "planned")
        self.assertIsNone(reopened.document.frontmatter["completed_at"])
        preserved = reopened.document.events[0]
        self.assertEqual((preserved["from"], preserved["to"]), ("unknown", "cancelled"))
        self.assertEqual(preserved["at"], "unknown")

    def test_resume_does_not_treat_blocked_cancellation_as_recovery(self):
        store = TaskStore(self.root)
        store.create("cancelled-block", body="Task\n", confirmed=True)
        for status in ("blocked", "cancelled"):
            selected = store.transition(
                "cancelled-block", status, reason="operator decision",
                evidence="recorded request", confirmed=True,
            )
        path = self.root / selected.task_path
        before = path.read_bytes()
        with self.assertRaises(TaskStateError):
            store.resume(
                "cancelled-block", reason="retry", evidence="operator request",
                confirmed=True,
            )
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(store.inspect("cancelled-block").document.frontmatter["status"], "cancelled")

    def test_cancelled_block_can_reopen_and_block_again_without_stale_phase(self):
        store = TaskStore(self.root)
        store.create("repeat-block", body="Task\n", confirmed=True)
        for status in ("blocked", "cancelled"):
            store.transition(
                "repeat-block", status, reason="first cycle",
                evidence="operator decision", confirmed=True,
            )
        store.reopen(
            "repeat-block", reason="new scope", evidence="operator request",
            confirmed=True,
        )
        for status in ("in-progress", "blocked"):
            store.transition(
                "repeat-block", status, reason="second cycle",
                evidence="new blocker", confirmed=True,
            )
        resumed = store.resume(
            "repeat-block", reason="second blocker resolved",
            evidence="resolution", confirmed=True,
        )
        self.assertEqual(resumed.document.frontmatter["status"], "in-progress")
        self.assertIsNone(resumed.document.frontmatter["blocked_reason"])

    def test_archiving_cancelled_parent_checks_children_in_other_directories(self):
        store = TaskStore(self.root)
        parent = store.create("parent", body="Parent\n", confirmed=True)
        store.create("separate-child", body="Child\n", parent="parent", confirmed=True)
        store.transition(
            "separate-child", "blocked", reason="waiting",
            evidence="legacy child fact", confirmed=True,
        )
        historical = parent.document.updated(
            {"status": "cancelled", "created_at": None, "updated_at": None},
            event={
                "at": "unknown", "from": "unknown", "to": "cancelled",
                "reason": "legacy cancellation fact", "evidence": "legacy task.json status",
            },
        )
        parent_path = self.root / parent.task_path
        parent_path.write_text(historical.text, encoding="utf-8")
        before = parent_path.read_bytes()
        for confirmed in (False, True):
            with self.subTest(confirmed=confirmed), self.assertRaises(TaskStateError):
                store.archive(
                    "parent", reason="retain history", evidence="operator request",
                    confirmed=confirmed,
                )
            self.assertEqual(parent_path.read_bytes(), before)
            self.assertEqual(store.inspect("parent").task_path, parent.task_path)
            self.assertEqual(
                store.inspect("separate-child").document.frontmatter["status"], "blocked"
            )

    def test_historical_unknown_block_fact_recovers_only_through_explicit_choice(
        self,
    ) -> None:
        store = TaskStore(self.root)
        selected = store.create(
            "legacy-block-fact", body="Historical blocked record.\n", confirmed=True
        )
        legacy = selected.document.updated(
            {
                "status": "blocked",
                "blocked_reason": "legacy blocker",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
            },
            event={
                "at": "unknown",
                "from": "unknown",
                "to": "blocked",
                "reason": "legacy blocked fact",
                "evidence": "legacy task.json status",
            },
        )
        path = self.root / selected.task_path
        path.write_text(legacy.text, encoding="utf-8")
        before = path.read_bytes()
        with self.assertRaises(TaskStateError):
            store.resume(
                "legacy-block-fact",
                reason="access restored",
                evidence="user confirmation",
                confirmed=True,
            )
        with self.assertRaises(TaskStateError):
            store.transition(
                "legacy-block-fact",
                "in-progress",
                reason="skip recovery",
                evidence="not permitted",
                confirmed=True,
            )
        self.assertEqual(path.read_bytes(), before)

        store.set_mode(
            "legacy-block-fact",
            "lite",
            note="user chose a shorter process",
            confirmed=True,
        )
        resumed = store.resume(
            "legacy-block-fact",
            target="in-progress",
            reason="user chose in-progress because the prior phase is unknown",
            evidence="explicit recovery choice",
            confirmed=True,
        )
        self.assertEqual(resumed.document.frontmatter["status"], "in-progress")
        self.assertIsNone(resumed.document.frontmatter.get("blocked_reason"))
        self.assertEqual(
            [(event["from"], event["to"]) for event in resumed.document.events],
            [("unknown", "blocked"), ("blocked", "in-progress")],
        )
        self.assertEqual(resumed.document.events[0]["at"], "unknown")
        progressed = store.transition(
            "legacy-block-fact",
            "checking",
            reason="implemented",
            evidence="candidate exists",
            confirmed=True,
        )
        self.assertEqual(progressed.document.frontmatter["status"], "checking")

    def test_partial_ancestor_reopen_reports_written_prefix_and_retries_once(
        self,
    ) -> None:
        store = TaskStore(self.root)
        parent = store.create("parent", body="Parent\n", confirmed=True)
        child = store.create("child", body="Child\n", parent="parent", confirmed=True)
        for task_id in ("child", "parent"):
            for status in ("in-progress", "checking", "done"):
                store.transition(
                    task_id,
                    status,
                    reason="progress",
                    evidence="acceptance",
                    confirmed=True,
                )
        child_path = self.root / child.task_path
        child_before = child_path.read_bytes()
        real_replace = os.replace

        def fail_child(source, target):
            if Path(target) == child_path:
                raise PermissionError("synthetic child write failure")
            return real_replace(source, target)

        with (
            mock.patch("sbtd_task_state.os.replace", side_effect=fail_child),
            self.assertRaises(TaskStateError) as failure,
        ):
            store.reopen(
                "child", reason="new gap", evidence="reproduction", confirmed=True
            )
        self.assertEqual(failure.exception.completed_steps, (parent.task_path,))
        self.assertEqual(child_path.read_bytes(), child_before)
        parent_before_retry = (self.root / parent.task_path).read_bytes()
        self.assertEqual(
            store.inspect("parent").document.frontmatter["status"], "planned"
        )
        recovered = store.reopen(
            "child", reason="new gap", evidence="reproduction", confirmed=True
        )
        self.assertEqual(recovered.document.frontmatter["status"], "planned")
        self.assertEqual(
            (self.root / parent.task_path).read_bytes(), parent_before_retry
        )

    def test_promotion_preserves_mode_and_requires_separate_original_retirement(
        self,
    ) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "share-me", body="Approved shared task scope.\n", confirmed=True
        )
        original_dir = (self.root / original.task_path).parent
        (original_dir / "notes.bin").write_bytes(b"\x00unchanged attachment\xff")
        index = self.root / "ai/tasks/index.md"
        index.parent.mkdir(parents=True)
        index.write_text(
            "# Team notes\n\nPreserve this introduction.\n", encoding="utf-8"
        )
        before = (original_dir / "task.md").read_bytes()

        prepared = store.promote("share-me", confirmed=True)
        self.assertEqual(prepared.status, "retirement-required")
        self.assertEqual(prepared.task.task_path, "ai/tasks/share-me/task.md")
        self.assertEqual(prepared.task.document.frontmatter["workflow_mode"], "default")
        self.assertEqual((original_dir / "task.md").read_bytes(), before)
        with self.assertRaises(TaskStateError):
            store.transition(
                "share-me",
                "in-progress",
                reason="not yet reconciled",
                evidence="two records remain",
                confirmed=True,
            )

        promoted = store.promote("share-me", confirmed=True, retire_source=True)
        self.assertEqual(promoted.status, "promoted")
        self.assertFalse(original_dir.exists())
        assert promoted.retained_original is not None
        retained = self.root / promoted.retained_original
        self.assertEqual((retained / "task.md").read_bytes(), before)
        self.assertEqual(
            (retained / "notes.bin").read_bytes(), b"\x00unchanged attachment\xff"
        )
        self.assertEqual(
            (self.root / "ai/tasks/share-me/notes.bin").read_bytes(),
            b"\x00unchanged attachment\xff",
        )
        self.assertEqual(store.inspect().task_path, "ai/tasks/share-me/task.md")
        self.assertIn("Preserve this introduction.", index.read_text())
        self.assertIn("(share-me/task.md)", index.read_text())

    def test_promotion_does_not_infer_nested_task_ownership(self) -> None:
        store = TaskStore(self.root)
        parent = store.create("foo", body="One task.\n", confirmed=True)
        nested = store.create(
            "foo/bar", body="A separate logical task.\n", confirmed=True
        )
        pointer = self.root / ".sbtd/active-task.json"
        before = {
            path: (self.root / path).read_bytes()
            for path in (parent.task_path, nested.task_path, ".sbtd/active-task.json")
        }
        with self.assertRaises(TaskStateError):
            store.promote("foo", confirmed=True)
        self.assertFalse((self.root / "ai").exists())
        for path, content in before.items():
            self.assertEqual((self.root / path).read_bytes(), content)
        store.promote("foo", include_tasks=("foo/bar",), confirmed=True)
        promoted = store.promote(
            "foo", include_tasks=("foo/bar",), confirmed=True, retire_source=True
        )
        self.assertEqual(promoted.status, "promoted")
        self.assertEqual(
            json.loads(pointer.read_text())["task_path"], "ai/tasks/foo/bar/task.md"
        )
        self.assertEqual(store.inspect("foo/bar").document.frontmatter["id"], "foo/bar")

    def test_original_retirement_cannot_be_preapproved_before_target_preparation(
        self,
    ) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "two-gates", body="Review the prepared target first.\n", confirmed=True
        )
        before = (self.root / original.task_path).read_bytes()
        with self.assertRaises(TaskStateError):
            store.promote("two-gates", confirmed=True, retire_source=True)
        self.assertEqual((self.root / original.task_path).read_bytes(), before)
        self.assertFalse((self.root / "ai").exists())

    def test_unclosed_body_fence_cannot_hide_a_persisted_status_event(self) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "open-fence", body="```text\nUnfinished user example.\n", confirmed=True
        )
        path = self.root / original.task_path
        before = path.read_bytes()
        from sbtd_project import TaskDataError

        with self.assertRaises(TaskDataError):
            store.transition(
                "open-fence",
                "in-progress",
                reason="start work",
                evidence="approved scope",
                confirmed=True,
            )
        self.assertEqual(path.read_bytes(), before)

    def test_markdown_examples_are_not_authoritative_task_history(self) -> None:
        table = (
            "## 状态事件\n"
            "| at | from | to | reason | evidence |\n"
            "|---|---|---|---|---|\n"
            "| 2026-01-01T00:00:00Z | planned | planned | example only | sample |\n"
        )
        examples = [
            "".join("    " + line for line in table.splitlines(keepends=True)),
            "```text\n```not-a-closer\n" + table + "```\n",
            "<!--\n" + table + "-->\n",
        ]
        for index, body in enumerate(examples):
            with self.subTest(example=index):
                store = TaskStore(self.root)
                task_id = f"example-{index}"
                original = store.create(task_id, body=body, confirmed=True)
                self.assertEqual(original.document.events, ())
                changed = store.transition(
                    task_id,
                    "in-progress",
                    reason="real work",
                    evidence="approved",
                    confirmed=True,
                )
                self.assertEqual(
                    [(event["from"], event["to"]) for event in changed.document.events],
                    [("planned", "in-progress")],
                )
                self.assertIn(body, changed.document.text)

    def test_optional_outer_table_pipes_do_not_truncate_recovery_history(self) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "pipe-history", body="Preserve all recorded transitions.\n", confirmed=True
        )
        legacy = original.document.updated(
            {
                "status": "blocked",
                "blocked_reason": "second block",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:03:00Z",
            }
        )
        history = (
            "\n## 状态事件\n\n"
            "| at | from | to | reason | evidence |\n"
            "|---|---|---|---|---|\n"
            "| 2026-01-01T00:00:00Z | planned | blocked | first block | old record |\n"
            "2026-01-01T00:01:00Z | blocked | checking | explicit old recovery | old choice\n"
            "| 2026-01-01T00:02:00Z | checking | blocked | second block | new dependency |\n"
        )
        (self.root / original.task_path).write_text(
            legacy.text + history, encoding="utf-8"
        )
        before = (self.root / original.task_path).read_bytes()
        with self.assertRaises(TaskStateError):
            store.resume(
                "pipe-history",
                reason="dependency resolved",
                evidence="confirmed",
                confirmed=True,
            )
        self.assertEqual((self.root / original.task_path).read_bytes(), before)
        recovered = store.resume(
            "pipe-history",
            target="checking",
            reason="user chose checking after reviewing the conflicting history",
            evidence="confirmed",
            confirmed=True,
        )
        self.assertEqual(recovered.document.frontmatter["status"], "checking")
        self.assertEqual(
            [(event["from"], event["to"]) for event in recovered.document.events],
            [
                ("planned", "blocked"),
                ("blocked", "checking"),
                ("checking", "blocked"),
                ("blocked", "checking"),
            ],
        )

    def test_shared_archive_preserves_completion_and_uses_its_original_quarter(
        self,
    ) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "archive-me",
            mode="lite",
            body="Keep the completed acceptance evidence.\n",
            confirmed=True,
        )
        completed_at = "2026-03-31T23:59:00+08:00"
        historical = original.document.updated(
            {
                "created_at": "2026-01-01T00:00:00+08:00",
                "updated_at": completed_at,
                "completed_at": completed_at,
                "status": "done",
            },
            event={
                "at": completed_at,
                "from": "unknown",
                "to": "done",
                "reason": "known historical completion",
                "evidence": "accepted legacy fixture",
            },
        )
        original_path = self.root / original.task_path
        original_path.write_text(historical.text, encoding="utf-8")
        (original_path.parent / "attachment.bin").write_bytes(b"keep-all-attachments")
        prepared = store.archive(
            "archive-me",
            reason="user requested archive",
            evidence="archive approved",
            confirmed=True,
        )
        self.assertEqual(prepared.status, "retirement-required")
        self.assertEqual(
            prepared.task.task_path, "ai/tasks/archive/2026-Q1/archive-me/task.md"
        )
        archived = store.archive(
            "archive-me",
            reason="user requested archive",
            evidence="archive approved",
            confirmed=True,
            retire_source=True,
        )
        self.assertEqual(archived.status, "archived")
        self.assertEqual(
            archived.task.document.frontmatter["completed_at"], completed_at
        )
        self.assertEqual(
            [(event["from"], event["to"]) for event in archived.task.document.events],
            [("unknown", "done"), ("done", "done")],
        )
        self.assertIn(original.task_path, archived.task.document.events[-1]["reason"])
        self.assertIn(
            archived.task.task_path, archived.task.document.events[-1]["reason"]
        )
        self.assertFalse(original_path.parent.exists())
        self.assertEqual(store.inspect().task_path, archived.task.task_path)
        self.assertEqual(
            (self.root / archived.task.task_path)
            .parent.joinpath("attachment.bin")
            .read_bytes(),
            b"keep-all-attachments",
        )
        before_retry = (self.root / archived.task.task_path).read_bytes()
        repeated = store.archive(
            "archive-me",
            reason="user requested archive",
            evidence="archive approved",
            confirmed=True,
            retire_source=True,
        )
        self.assertEqual(repeated.status, "already-archived")
        self.assertEqual(
            (self.root / archived.task.task_path).read_bytes(), before_retry
        )

    def test_cancelled_archive_uses_the_proven_cancellation_quarter(self) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "cancelled-shared",
            mode="lite",
            body="Keep the cancelled scope record.\n",
            confirmed=True,
        )
        cancelled_at = "2026-03-31T23:59:00+08:00"
        historical = original.document.updated(
            {
                "created_at": "2026-01-01T00:00:00+08:00",
                "updated_at": cancelled_at,
                "status": "cancelled",
            },
            event={
                "at": cancelled_at,
                "from": "unknown",
                "to": "cancelled",
                "reason": "known historical cancellation",
                "evidence": "accepted legacy fixture",
            },
        )
        original_path = self.root / original.task_path
        original_path.write_text(historical.text, encoding="utf-8")
        prepared = store.archive(
            "cancelled-shared",
            reason="user requested archive",
            evidence="archive approved",
            confirmed=True,
        )
        self.assertEqual(prepared.status, "retirement-required")
        self.assertEqual(
            prepared.task.task_path,
            "ai/tasks/archive/2026-Q1/cancelled-shared/task.md",
        )
        archived = store.archive(
            "cancelled-shared",
            reason="user requested archive",
            evidence="archive approved",
            confirmed=True,
            retire_source=True,
        )
        self.assertEqual(archived.status, "archived")
        self.assertIsNone(archived.task.document.frontmatter["completed_at"])
        self.assertEqual(
            [
                (event["from"], event["to"])
                for event in archived.task.document.events
            ],
            [("unknown", "cancelled"), ("cancelled", "cancelled")],
        )
        self.assertFalse(original_path.parent.exists())
        self.assertEqual(store.inspect().task_path, archived.task.task_path)
        before_retry = (self.root / archived.task.task_path).read_bytes()
        repeated = store.archive(
            "cancelled-shared",
            reason="user requested archive",
            evidence="archive approved",
            confirmed=True,
            retire_source=True,
        )
        self.assertEqual(repeated.status, "already-archived")
        self.assertEqual(
            (self.root / archived.task.task_path).read_bytes(), before_retry
        )

    def test_migrated_undated_cancellation_archives_under_undated_idempotently(
        self,
    ) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "undated-cancelled",
            mode="lite",
            body="Migrated cancelled record.\n",
            confirmed=True,
        )
        historical = original.document.updated(
            {
                "workflow_mode": None,
                "mode_source": "migration-unknown",
                "created_at": None,
                "updated_at": None,
                "status": "cancelled",
            },
            event={
                "at": "unknown",
                "from": "unknown",
                "to": "cancelled",
                "reason": "legacy cancellation fact",
                "evidence": "legacy task.json status",
            },
        )
        (self.root / original.task_path).write_text(historical.text, encoding="utf-8")
        prepared = store.archive(
            "undated-cancelled",
            reason="archive",
            evidence="old source",
            confirmed=True,
        )
        self.assertEqual(
            prepared.task.task_path,
            "ai/tasks/archive/undated/undated-cancelled/task.md",
        )
        archived = store.archive(
            "undated-cancelled",
            reason="archive",
            evidence="old source",
            confirmed=True,
            retire_source=True,
        )
        self.assertEqual(archived.status, "archived")
        frontmatter = archived.task.document.frontmatter
        self.assertIsNone(frontmatter["completed_at"])
        self.assertIsNone(frontmatter["workflow_mode"])
        events = archived.task.document.events
        self.assertEqual(
            (events[0]["from"], events[0]["to"], events[0]["at"]),
            ("unknown", "cancelled", "unknown"),
        )
        self.assertEqual(
            [(event["from"], event["to"]) for event in events],
            [("unknown", "cancelled"), ("cancelled", "cancelled")],
        )
        self.assertNotEqual(events[-1]["at"], "unknown")
        before_retry = (self.root / archived.task.task_path).read_bytes()
        repeated = store.archive(
            "undated-cancelled",
            reason="archive",
            evidence="old source",
            confirmed=True,
            retire_source=True,
        )
        self.assertEqual(repeated.status, "already-archived")
        self.assertEqual(
            (self.root / archived.task.task_path).read_bytes(), before_retry
        )

    def test_explicit_selection_changes_only_the_minimal_bookmark(self) -> None:
        store = TaskStore(self.root)
        first = store.create("first-choice", body="First\n", confirmed=True)
        second = store.create(
            "second-choice", mode="lite", body="Second\n", confirmed=True
        )
        originals = {
            item.task_path: (self.root / item.task_path).read_bytes()
            for item in (first, second)
        }
        selected = store.select("first-choice", confirmed=True)
        self.assertEqual(selected.task_path, first.task_path)
        self.assertEqual(TaskStore(self.root).inspect().task_path, first.task_path)
        self.assertEqual(
            json.loads((self.root / ".sbtd/active-task.json").read_text()),
            {
                "schema_version": 1,
                "task_id": "first-choice",
                "task_path": first.task_path,
            },
        )
        for path, content in originals.items():
            self.assertEqual((self.root / path).read_bytes(), content)
        before = (self.root / ".sbtd/active-task.json").read_bytes()
        with self.assertRaises(TaskStateError):
            TaskStore(self.root, read_only=True).select("second-choice", confirmed=True)
        self.assertEqual((self.root / ".sbtd/active-task.json").read_bytes(), before)

    def test_shared_creation_updates_navigation_without_replacing_user_content(
        self,
    ) -> None:
        index = self.root / "ai/tasks/index.md"
        index.parent.mkdir(parents=True)
        introduction = b"# Team notes\n\nKeep these notes unchanged.\n"
        index.write_bytes(introduction)
        created = TaskStore(self.root).create(
            "shared", mode="lite", body="Shared task\n", confirmed=True
        )
        self.assertEqual(created.task_path, "ai/tasks/shared/task.md")
        self.assertTrue(index.read_bytes().startswith(introduction))
        self.assertIn("(shared/task.md)", index.read_text())

    def test_creation_retry_finishes_a_failed_bookmark_without_recreating_the_task(
        self,
    ) -> None:
        store = TaskStore(self.root)
        real_link = os.link

        def fail_bookmark(source, target, *args, **kwargs):
            if Path(target).name == "active-task.json":
                raise PermissionError("synthetic bookmark failure")
            return real_link(source, target, *args, **kwargs)

        with (
            mock.patch("sbtd_task_state.os.link", side_effect=fail_bookmark),
            self.assertRaises(TaskStateError) as failure,
        ):
            store.create(
                "retry-create",
                mode="lite",
                body="Keep the original creation.\n",
                confirmed=True,
            )
        task_path = "ai/tasks/retry-create/task.md"
        self.assertEqual(
            failure.exception.completed_steps, (task_path, "ai/tasks/index.md")
        )
        before = (self.root / task_path).read_bytes()
        index_before = (self.root / "ai/tasks/index.md").read_bytes()
        resumed = TaskStore(self.root).create(
            "retry-create",
            mode="lite",
            body="Keep the original creation.\n",
            confirmed=True,
        )
        self.assertEqual(resumed.task_path, task_path)
        self.assertEqual((self.root / task_path).read_bytes(), before)
        self.assertEqual((self.root / "ai/tasks/index.md").read_bytes(), index_before)
        self.assertEqual(TaskStore(self.root).inspect().task_path, task_path)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO fixture")
    def test_nonregular_pointer_is_rejected_without_blocking_or_writing(self) -> None:
        pointer = self.root / ".sbtd/active-task.json"
        pointer.parent.mkdir()
        os.mkfifo(pointer)
        code = (
            "import sys\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from sbtd_task_state import TaskStore, TaskStateError\n"
            "try:\n"
            "    TaskStore(Path(sys.argv[2])).create('blocked-fifo', body='Task', confirmed=True)\n"
            "except TaskStateError:\n"
            "    raise SystemExit(2)\n"
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                code,
                str(ROOT / "sbtd-workflow-onboard/scripts"),
                str(self.root),
            ],
            env=self.env,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertTrue(pointer.is_fifo())
        self.assertFalse((self.root / ".sbtd/tasks").exists())

    def test_unknown_date_local_archive_stays_private_and_passes_inspection(
        self,
    ) -> None:
        from sbtd_project import inspect_project_state

        store = TaskStore(self.root)
        original = store.create(
            "local-history",
            body="Unknown historical completion date.\n",
            confirmed=True,
        )
        historical = original.document.updated(
            {
                "status": "done",
                "created_at": None,
                "updated_at": None,
                "completed_at": None,
            },
            event={
                "at": "unknown",
                "from": "unknown",
                "to": "done",
                "reason": "historical completed record with unknown date",
                "evidence": "legacy source; earlier evidence not-recorded",
            },
        )
        (self.root / original.task_path).write_text(historical.text, encoding="utf-8")
        store.archive(
            "local-history",
            reason="archive privately",
            evidence="user confirmation",
            confirmed=True,
        )
        archived = store.archive(
            "local-history",
            reason="archive privately",
            evidence="user confirmation",
            confirmed=True,
            retire_source=True,
        )
        self.assertEqual(
            archived.task.task_path, ".sbtd/tasks/archive/undated/local-history/task.md"
        )
        self.assertIsNone(archived.task.document.frontmatter["completed_at"])
        self.assertEqual(archived.task.document.events[0]["at"], "unknown")
        self.assertFalse((self.root / "ai").exists())
        inspection = inspect_project_state(self.root)
        self.assertEqual(inspection["status"], "success", inspection)
        active = inspection["activeTask"]
        assert active is not None
        self.assertEqual(active["id"], "local-history")

    def test_promotion_failures_preserve_originals_and_resume_each_persisted_prefix(
        self,
    ) -> None:
        for failure_point in ("copy", "index", "bookmark", "retirement"):
            with self.subTest(failure_point=failure_point):
                self._assert_promotion_failure_recovers(failure_point)

    def _assert_promotion_failure_recovers(self, failure_point: str) -> None:
        store = TaskStore(self.root)
        task_id = "failure-" + failure_point
        original = store.create(task_id, body="Approved transfer.\n", confirmed=True)
        source = (self.root / original.task_path).parent
        (source / "proof.bin").write_bytes(b"unchanged proof")
        before = (source / "task.md").read_bytes()
        target = self.root / "ai/tasks" / task_id
        index = self.root / "ai/tasks/index.md"
        bookmark = self.root / ".sbtd/active-task.json"
        if failure_point == "retirement":
            store.promote(task_id, confirmed=True)
        real_copytree, real_link = shutil.copytree, os.link
        real_replace, real_rename = os.replace, os.rename

        def copytree(source_path, target_path, *args, **kwargs):
            if failure_point == "copy":
                Path(target_path).mkdir()
                (Path(target_path) / "partial").write_bytes(b"owned temporary data")
                raise OSError("synthetic copy failure")
            return real_copytree(source_path, target_path, *args, **kwargs)

        def write_failure(native, source_path, target_path, *args, **kwargs):
            blocked = index if failure_point == "index" else bookmark
            if failure_point in ("index", "bookmark") and Path(target_path) == blocked:
                raise PermissionError("synthetic metadata failure")
            return native(source_path, target_path, *args, **kwargs)

        def rename(source_path, target_path):
            if failure_point == "retirement" and Path(source_path) == source:
                raise PermissionError("synthetic retirement failure")
            return real_rename(source_path, target_path)

        with (
            mock.patch("sbtd_task_state.shutil.copytree", side_effect=copytree),
            mock.patch(
                "sbtd_task_state.os.link",
                side_effect=lambda *args, **kwargs: write_failure(
                    real_link, *args, **kwargs
                ),
            ),
            mock.patch(
                "sbtd_task_state.os.replace",
                side_effect=lambda *args, **kwargs: write_failure(
                    real_replace, *args, **kwargs
                ),
            ),
            mock.patch("sbtd_task_state.os.rename", side_effect=rename),
            self.assertRaises(TaskStateError) as failed,
        ):
            store.promote(
                task_id,
                confirmed=True,
                retire_source=failure_point == "retirement",
            )
        expected_steps = {
            "copy": (),
            "index": (f"ai/tasks/{task_id}",),
            "bookmark": (f"ai/tasks/{task_id}", "ai/tasks/index.md"),
            "retirement": (),
        }
        self.assertEqual(
            failed.exception.completed_steps, expected_steps[failure_point]
        )
        self.assertEqual((source / "task.md").read_bytes(), before)
        self.assertEqual((source / "proof.bin").read_bytes(), b"unchanged proof")
        self.assertEqual(target.exists(), failure_point != "copy")
        expected_active = (
            f"ai/tasks/{task_id}/task.md"
            if failure_point == "retirement"
            else original.task_path
        )
        self.assertEqual(json.loads(bookmark.read_text())["task_path"], expected_active)

        retry = TaskStore(self.root)
        retry.promote(task_id, confirmed=True)
        finished = retry.promote(task_id, confirmed=True, retire_source=True)
        self.assertEqual(finished.status, "promoted")
        self.assertFalse(source.exists())
        self.assertEqual((target / "proof.bin").read_bytes(), b"unchanged proof")
        self.assertEqual(
            TaskStore(self.root).inspect().task_path,
            f"ai/tasks/{task_id}/task.md",
        )

    def test_retirement_preserves_user_changes_even_with_equal_size_and_mtime(
        self,
    ) -> None:
        for changed_side in ("source", "target"):
            with self.subTest(changed_side=changed_side):
                store = TaskStore(self.root)
                task_id = "changed-" + changed_side
                original = store.create(task_id, body="AAA\n", confirmed=True)
                prepared = store.promote(task_id, confirmed=True)
                source = self.root / original.task_path
                target = self.root / prepared.task.task_path
                changed = source if changed_side == "source" else target
                original_bytes = changed.read_bytes()
                metadata = changed.stat()
                changed.write_bytes(original_bytes.replace(b"AAA", b"BBB"))
                os.utime(changed, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
                source_before, target_before = source.read_bytes(), target.read_bytes()
                bookmark_before = (self.root / ".sbtd/active-task.json").read_bytes()
                with self.assertRaises(TaskStateError):
                    TaskStore(self.root).promote(
                        task_id, confirmed=True, retire_source=True
                    )
                self.assertEqual(source.read_bytes(), source_before)
                self.assertEqual(target.read_bytes(), target_before)
                self.assertEqual(
                    (self.root / ".sbtd/active-task.json").read_bytes(), bookmark_before
                )
                changed.write_bytes(original_bytes)
                os.utime(changed, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
                store.promote(task_id, confirmed=True, retire_source=True)

    def test_branch_changes_block_writes_without_rebinding_the_task(self) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "branch-bound", body="Stay on the recorded branch.\n", confirmed=True
        )
        path = self.root / original.task_path
        before = path.read_bytes()
        subprocess.run(
            ["git", "-C", str(self.root), "switch", "--orphan", "different"],
            env=self.env,
            capture_output=True,
            check=True,
        )
        with self.assertRaises(TaskStateError):
            store.transition(
                "branch-bound",
                "in-progress",
                reason="wrong worktree",
                evidence="not authorized",
                confirmed=True,
            )
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(
            store.inspect("branch-bound").document.frontmatter["branch"], "main"
        )

    def test_parent_and_duplicate_identity_conflicts_never_create_a_replacement(
        self,
    ) -> None:
        store = TaskStore(self.root)
        original = store.create("existing", body="Keep this record.\n", confirmed=True)
        pointer = self.root / ".sbtd/active-task.json"
        before = pointer.read_bytes()
        for task_id, parent in (
            ("missing-parent", "absent"),
            ("self-cycle", "self-cycle"),
        ):
            with self.subTest(task_id=task_id):
                with self.assertRaises(TaskStateError):
                    store.create(
                        task_id, body="Invalid graph\n", parent=parent, confirmed=True
                    )
                self.assertFalse((self.root / ".sbtd/tasks" / task_id).exists())
        duplicate = self.root / "ai/tasks/duplicate-location"
        shutil.copytree((self.root / original.task_path).parent, duplicate)
        original_bytes = (self.root / original.task_path).read_bytes()
        with self.assertRaises(TaskStateError):
            store.create(
                "replacement", body="Must not hide the conflict\n", confirmed=True
            )
        self.assertFalse((self.root / ".sbtd/tasks/replacement").exists())
        self.assertEqual((self.root / original.task_path).read_bytes(), original_bytes)
        self.assertEqual((duplicate / "task.md").read_bytes(), original_bytes)
        self.assertEqual(pointer.read_bytes(), before)

    def test_state_symlink_never_redirects_a_write_outside_the_project(self) -> None:
        outside = self.root.parent / "outside"
        outside.mkdir()
        marker = outside / "keep.bin"
        marker.write_bytes(b"outside data")
        (self.root / ".sbtd").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(TaskStateError):
            TaskStore(self.root).create(
                "escape", body="Do not follow the link.\n", confirmed=True
            )
        self.assertEqual(marker.read_bytes(), b"outside data")
        self.assertEqual({path.name for path in outside.iterdir()}, {"keep.bin"})

    def test_changed_content_during_preparation_is_not_force_overwritten(self) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "concurrent-edit", body="Original note.\n", confirmed=True
        )
        path = self.root / original.task_path
        user_version = path.read_bytes() + b"\nNew user content.\n"
        real_mkstemp = tempfile.mkstemp

        def change_after_preparation_starts(*args, **kwargs):
            descriptor, temporary = real_mkstemp(*args, **kwargs)
            path.write_bytes(user_version)
            return descriptor, temporary

        with (
            mock.patch(
                "sbtd_task_state.tempfile.mkstemp",
                side_effect=change_after_preparation_starts,
            ),
            self.assertRaises(TaskStateError),
        ):
            store.transition(
                "concurrent-edit",
                "in-progress",
                reason="start",
                evidence="approved",
                confirmed=True,
            )
        self.assertEqual(path.read_bytes(), user_version)
        self.assertEqual(
            store.inspect("concurrent-edit").document.frontmatter["status"], "planned"
        )
        self.assertEqual(list(path.parent.glob(".sbtd-write-*")), [])

    def test_unknown_legacy_mode_requires_an_explicit_choice_before_progress(
        self,
    ) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "unknown-mode", body="Preserve the unresolved old choice.\n", confirmed=True
        )
        unresolved = original.document.updated(
            {
                "workflow_mode": None,
                "mode_source": "migration-unknown",
                "mode_note": "old mode cannot be established",
            }
        )
        path = self.root / original.task_path
        path.write_text(unresolved.text, encoding="utf-8")
        before = path.read_bytes()
        with self.assertRaises(TaskStateError):
            store.transition(
                "unknown-mode",
                "in-progress",
                reason="no choice yet",
                evidence="not authorized",
                confirmed=True,
            )
        self.assertEqual(path.read_bytes(), before)
        store.set_mode(
            "unknown-mode",
            "default",
            note="user explicitly chose default",
            confirmed=True,
        )
        started = store.transition(
            "unknown-mode",
            "in-progress",
            reason="choice recorded",
            evidence="user confirmation",
            confirmed=True,
        )
        self.assertEqual(started.document.frontmatter["workflow_mode"], "default")
        self.assertEqual(started.document.frontmatter["mode_source"], "user")

    def test_selective_metadata_ignores_do_not_prove_the_private_tree_is_protected(
        self,
    ) -> None:
        ignore = self.root / ".gitignore"
        ignore.write_text(
            "/.sbtd/active-task.json\n"
            "/.sbtd/tasks/**/task.md\n"
            "/.sbtd/task-transfer-candidates/**/task.md\n"
            "/.sbtd/task-originals/**/task.md\n",
            encoding="utf-8",
        )
        before = ignore.read_bytes()
        with self.assertRaises(TaskStateError):
            TaskStore(self.root).create(
                "private-tree",
                body="Attachments must stay private too.\n",
                confirmed=True,
            )
        self.assertFalse((self.root / ".sbtd").exists())
        self.assertEqual(ignore.read_bytes(), before)

    def test_legacy_completion_archives_and_reopens_without_reordering_history(
        self,
    ) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "legacy-no-event",
            mode="lite",
            body="Preserve the historical completion.\n",
            confirmed=True,
        )
        historical = original.document.updated(
            {
                "status": "done",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-02-01T00:00:00Z",
                "completed_at": "2026-02-01T00:00:00Z",
            }
        )
        (self.root / original.task_path).write_text(historical.text, encoding="utf-8")
        store.archive(
            "legacy-no-event",
            reason="archive old work",
            evidence="old record",
            confirmed=True,
        )
        store.archive(
            "legacy-no-event",
            reason="archive old work",
            evidence="old record",
            confirmed=True,
            retire_source=True,
        )
        store.reopen(
            "legacy-no-event",
            reason="new scope",
            evidence="user request",
            confirmed=True,
        )
        started = store.transition(
            "legacy-no-event",
            "in-progress",
            reason="start reopened work",
            evidence="scope approved",
            confirmed=True,
        )
        self.assertEqual(started.document.frontmatter["status"], "in-progress")
        events = started.document.events
        self.assertEqual(
            (events[0]["from"], events[0]["to"], events[0]["at"]),
            ("unknown", "done", "2026-02-01T00:00:00Z"),
        )
        self.assertEqual(
            [(event["from"], event["to"]) for event in events[1:]],
            [("done", "done"), ("done", "planned"), ("planned", "in-progress")],
        )

    def test_multiple_tables_in_state_section_cannot_silently_hide_history(
        self,
    ) -> None:
        from sbtd_project import TaskDataError

        store = TaskStore(self.root)
        original = store.create(
            "split-history", body="Retain both historical tables.\n", confirmed=True
        )
        blocked = original.document.updated(
            {
                "status": "blocked",
                "blocked_reason": "legacy blocker",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:05:00Z",
            }
        )
        header = "| at | from | to | reason | evidence |\n|---|---|---|---|---|\n"
        text = (
            blocked.text
            + "\n## 状态事件\n\n"
            + header
            + "| 2026-01-01T00:00:00Z | planned | blocked | first | old |\n"
            + "\nHistorical continuation:\n\n"
            + header
            + "| 2026-01-01T00:01:00Z | blocked | planned | release | old |\n"
            + "| 2026-01-01T00:02:00Z | planned | in-progress | start | old |\n"
            + "| 2026-01-01T00:03:00Z | in-progress | blocked | second | old |\n"
        )
        path = self.root / original.task_path
        path.write_text(text, encoding="utf-8")
        before = path.read_bytes()
        with self.assertRaises(TaskDataError):
            store.resume(
                "split-history",
                reason="resolved",
                evidence="user confirmed",
                confirmed=True,
            )
        self.assertEqual(path.read_bytes(), before)

    def test_undated_completion_is_preserved_before_archive_and_reopen_events(
        self,
    ) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "undated-no-event", body="Historical source.\n", confirmed=True
        )
        historical = original.document.updated(
            {
                "status": "done",
                "created_at": None,
                "updated_at": None,
                "completed_at": None,
            }
        )
        (self.root / original.task_path).write_text(historical.text, encoding="utf-8")
        store.archive(
            "undated-no-event", reason="archive", evidence="old source", confirmed=True
        )
        store.archive(
            "undated-no-event",
            reason="archive",
            evidence="old source",
            confirmed=True,
            retire_source=True,
        )
        store.reopen(
            "undated-no-event",
            reason="new work",
            evidence="user request",
            confirmed=True,
        )
        started = store.transition(
            "undated-no-event",
            "in-progress",
            reason="start",
            evidence="approved",
            confirmed=True,
        )
        self.assertEqual(started.document.events[0]["at"], "unknown")
        self.assertEqual(
            [(event["from"], event["to"]) for event in started.document.events],
            [
                ("unknown", "done"),
                ("done", "done"),
                ("done", "planned"),
                ("planned", "in-progress"),
            ],
        )

    def test_local_archive_does_not_publish_to_a_selectively_unprotected_target(
        self,
    ) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "private-archive", body="Keep every attachment private.\n", confirmed=True
        )
        for status in ("in-progress", "checking", "done"):
            store.transition(
                "private-archive",
                status,
                reason="progress",
                evidence="accepted",
                confirmed=True,
            )
        source = (self.root / original.task_path).parent
        (source / "private.bin").write_bytes(b"private synthetic attachment")
        before = (source / "task.md").read_bytes()
        ignore = self.root / ".gitignore"
        ignore.write_text(
            "/.sbtd/active-task.json\n/.sbtd/tasks/private-archive/\n"
            "/.sbtd/task-transfer-candidates/\n/.sbtd/task-originals/\n",
            encoding="utf-8",
        )
        with self.assertRaises(TaskStateError):
            store.archive(
                "private-archive", reason="archive", evidence="approved", confirmed=True
            )
        self.assertFalse((self.root / ".sbtd/tasks/archive").exists())
        self.assertEqual((source / "task.md").read_bytes(), before)
        self.assertEqual(
            (source / "private.bin").read_bytes(), b"private synthetic attachment"
        )


    def test_new_child_under_completed_ancestor_requires_explicit_reopen(self) -> None:
        store = TaskStore(self.root)
        parent = store.create("parent", body="Parent\n", confirmed=True)
        for status in ("in-progress", "checking", "done"):
            store.transition(
                "parent", status, reason="progress", evidence="accepted", confirmed=True
            )
        parent_before = (self.root / parent.task_path).read_bytes()
        pointer = (self.root / ".sbtd/active-task.json").read_bytes()
        with self.assertRaises(TaskStateError):
            store.create(
                "child", parent="parent", body="Child\n", confirmed=True
            )
        self.assertFalse((self.root / ".sbtd/tasks/child").exists())
        self.assertEqual((self.root / parent.task_path).read_bytes(), parent_before)
        self.assertEqual((self.root / ".sbtd/active-task.json").read_bytes(), pointer)

    def test_promotion_rejects_shared_index_subtree_before_writing(self) -> None:
        store = TaskStore(self.root)
        source = store.create(
            "index.md/child", body="Must not create an index directory.\n", confirmed=True
        )
        with self.assertRaises(TaskStateError):
            store.promote("index.md/child", confirmed=True)
        self.assertTrue((self.root / source.task_path).exists())
        self.assertFalse((self.root / "ai").exists())

    def test_archive_rejects_source_target_ancestry_before_writing(self) -> None:
        task_id = "archive"
        store = TaskStore(self.root)
        source = store.create(
            task_id, body="Archive namespace source.\n", shared=True, confirmed=True
        )
        for status in ("in-progress", "checking", "done"):
            store.transition(
                task_id, status, reason="progress", evidence="accepted", confirmed=True
            )
        before = (self.root / source.task_path).read_bytes()
        with self.assertRaises(TaskStateError):
            store.archive(task_id, reason="archive", evidence="approved", confirmed=True)
        self.assertEqual((self.root / source.task_path).read_bytes(), before)

    def test_promotion_rejects_case_variant_shared_index_subtree_before_writing(
        self,
    ) -> None:
        store = TaskStore(self.root)
        source = store.create(
            "index.md/child", body="Must not create an index directory.\n", confirmed=True
        )
        records = self._case_variant_transfer_records(
            source, ".sbtd/tasks/index.md", ".sbtd/tasks/Index.md"
        )
        variant_path = self.root / records[0].task_path
        before = variant_path.read_bytes()
        with (
            mock.patch.object(store, "_records", return_value=iter(records)),
            self.assertRaises(TaskStateError),
        ):
            store.promote("index.md/child", confirmed=True)
        self.assertEqual(variant_path.read_bytes(), before)
        self.assertFalse((self.root / "ai").exists())

    def test_archive_rejects_case_variant_source_target_ancestry_before_writing(
        self,
    ) -> None:
        store = TaskStore(self.root)
        source = store.create(
            "archive", body="Archive namespace source.\n", shared=True, confirmed=True
        )
        for status in ("in-progress", "checking", "done"):
            store.transition(
                "archive", status, reason="progress", evidence="accepted", confirmed=True
            )
        records = self._case_variant_transfer_records(
            source, "ai/tasks/archive", "ai/tasks/Archive"
        )
        variant_path = self.root / records[0].task_path
        before = variant_path.read_bytes()
        with (
            mock.patch.object(store, "_records", return_value=iter(records)),
            self.assertRaises(TaskStateError),
        ):
            store.archive("archive", reason="archive", evidence="approved", confirmed=True)
        self.assertEqual(variant_path.read_bytes(), before)

    def test_uninspectable_task_subtree_aborts_create_without_writing(self) -> None:
        store = TaskStore(self.root)
        existing = store.create("existing", body="Keep this task.\n", confirmed=True)
        original_walk = os.walk

        def unreadable_walk(path, *args, **kwargs):
            if Path(path) == self.root / ".sbtd/tasks":
                kwargs["onerror"](PermissionError("synthetic unreadable subtree"))
            return original_walk(path, *args, **kwargs)

        with (
            mock.patch("sbtd_task_state.os.walk", side_effect=unreadable_walk),
            self.assertRaises(TaskStateError),
        ):
            store.create("new", body="Must not be created.\n", confirmed=True)
        self.assertTrue((self.root / existing.task_path).exists())
        self.assertFalse((self.root / ".sbtd/tasks/new").exists())

    def test_reopen_rejects_unknown_mode_on_done_ancestor_without_writing(self) -> None:
        store = TaskStore(self.root)
        parent = store.create("parent", body="Parent\n", confirmed=True)
        child = store.create("child", parent="parent", body="Child\n", confirmed=True)
        for task_id in ("child", "parent"):
            for status in ("in-progress", "checking", "done"):
                store.transition(
                    task_id, status, reason="progress", evidence="accepted", confirmed=True
                )
        parent_path = self.root / parent.task_path
        unknown = store.inspect("parent").document.updated(
            {
                "workflow_mode": None,
                "mode_source": "migration-unknown",
                "mode_note": "legacy mode is unknown",
            }
        )
        parent_path.write_text(unknown.text, encoding="utf-8")
        before = {
            parent_path: parent_path.read_bytes(),
            self.root / child.task_path: (self.root / child.task_path).read_bytes(),
        }
        with self.assertRaises(TaskStateError):
            store.reopen(
                "child", reason="new gap", evidence="reproduced", confirmed=True
            )
        self.assertEqual(
            {path: path.read_bytes() for path in before}, before
        )

    def test_reopen_skips_unknown_mode_planned_ancestor_that_stays_untouched(
        self,
    ) -> None:
        store = TaskStore(self.root)
        parent = store.create("parent", body="Parent\n", confirmed=True)
        store.create("child", parent="parent", body="Child\n", confirmed=True)
        for status in ("in-progress", "checking", "done"):
            store.transition(
                "child", status, reason="progress", evidence="accepted", confirmed=True
            )
        parent_path = self.root / parent.task_path
        unknown = store.inspect("parent").document.updated(
            {
                "workflow_mode": None,
                "mode_source": "migration-unknown",
                "mode_note": "legacy mode is unknown",
            }
        )
        parent_path.write_text(unknown.text, encoding="utf-8")
        parent_before = parent_path.read_bytes()

        reopened = store.reopen(
            "child", reason="new gap", evidence="reproduced", confirmed=True
        )

        self.assertEqual(reopened.document.frontmatter["status"], "planned")
        self.assertEqual(parent_path.read_bytes(), parent_before)

    def test_create_rejects_history_that_conflicts_with_planned_frontmatter(self) -> None:
        body = """## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| unknown | unknown | done | old completion | legacy |
"""
        with self.assertRaises(TaskStateError):
            TaskStore(self.root).create("conflict", body=body, confirmed=True)
        self.assertFalse((self.root / ".sbtd/tasks/conflict").exists())

    def test_future_event_with_null_updated_at_blocks_transition(self) -> None:
        store = TaskStore(self.root)
        snapshot = store.create("future-event", body="Task\n", confirmed=True)
        future = "2999-01-01T00:00:00Z"
        changed = snapshot.document.updated(
            {"updated_at": None},
            event={
                "at": future,
                "from": "planned",
                "to": "planned",
                "reason": "historical note",
                "evidence": "preserved",
            },
        )
        path = self.root / snapshot.task_path
        path.write_text(changed.text, encoding="utf-8")
        before = path.read_bytes()
        with self.assertRaises(TaskStateError):
            store.transition(
                "future-event",
                "in-progress",
                reason="start",
                evidence="approved",
                confirmed=True,
            )
        self.assertEqual(path.read_bytes(), before)

    def test_transfer_reports_published_target_when_candidate_cleanup_fails(self) -> None:
        store = TaskStore(self.root)
        store.create("cleanup-failure", body="Task\n", confirmed=True)
        target = "ai/tasks/cleanup-failure"
        with (
            mock.patch(
                "sbtd_task_state.shutil.rmtree",
                side_effect=PermissionError("synthetic cleanup failure"),
            ),
            self.assertRaises(TaskStateError) as failure,
        ):
            store.promote("cleanup-failure", confirmed=True)
        self.assertEqual(failure.exception.completed_steps, (target,))
        self.assertTrue((self.root / target / "task.md").exists())

    def test_taskstore_normalizes_malformed_task_errors_at_its_boundary(self) -> None:
        store = TaskStore(self.root)
        created = store.create("malformed", body="Task\n", confirmed=True)
        path = self.root / created.task_path
        path.write_text("---\nid: [\n---\n", encoding="utf-8")
        with self.assertRaises(TaskStateError):
            store.inspect("malformed")

    def test_non_git_leading_space_ignore_rule_does_not_protect_state(self) -> None:
        shutil.rmtree(self.root / ".git")
        (self.root / ".gitignore").write_text(" /.sbtd/\n", encoding="utf-8")
        with self.assertRaises(TaskStateError):
            TaskStore(self.root).create(
                "unprotected", body="Task\n", confirmed=True
            )
        self.assertFalse((self.root / ".sbtd").exists())

    def test_git_root_with_trailing_space_keeps_its_binding(self) -> None:
        spaced = self.root.parent / "project "
        self.root.rename(spaced)
        self.root = spaced
        store = TaskStore(self.root)
        self.assertEqual(store.current_binding(), "main")
        self.assertEqual(
            store.create("space-root", body="Task\n", confirmed=True).task_path,
            ".sbtd/tasks/space-root/task.md",
        )

if __name__ == "__main__":
    unittest.main()
