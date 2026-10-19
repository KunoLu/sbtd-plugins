from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sbtd-workflow-onboard/scripts"))

from sbtd_handoff import HandoffPolicy, HandoffStore
from sbtd_project import TaskDataError, open_regular_file
from sbtd_task_state import TaskStateError, TaskStore


class HandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="sbtd-handoff-test-")
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

    def test_manual_handoff_respects_readonly_and_does_not_clear_auto_optouts(
        self,
    ) -> None:
        tasks = TaskStore(self.root)
        tasks.create(
            "parent/child", mode="lite", body="Synthetic task.\n", confirmed=True
        )
        policy = HandoffPolicy(task_opt_out=True, session_opt_out=True)
        content = {
            "goal": "Continue synthetic work",
            "decisions": ["keep scope"],
            "completed": ["baseline checked"],
            "remaining": ["verify change"],
            "changed_files": [],
            "verification": ["synthetic smoke only"],
            "next_action": "Read the selected task",
            "do_not_repeat": ["do not change user environment"],
            "limitations": "No host session proof",
        }
        handoffs = HandoffStore(tasks)
        skipped = handoffs.save(
            "parent/child",
            content=content,
            trigger="pause",
            policy=policy,
            confirmed=True,
            redaction_confirmed=True,
        )
        self.assertEqual(skipped.status, "suppressed")
        self.assertFalse((self.root / "docs/handoffs").exists())
        readonly = HandoffStore(TaskStore(self.root, read_only=True)).save(
            "parent/child",
            content=content,
            trigger="manual",
            policy=policy,
            confirmed=True,
            redaction_confirmed=True,
        )
        self.assertEqual(readonly.status, "conversation-only")
        self.assertFalse((self.root / "docs/handoffs").exists())
        saved = handoffs.save(
            "parent/child",
            content=content,
            trigger="manual",
            policy=policy,
            confirmed=True,
            redaction_confirmed=True,
        )
        self.assertEqual(saved.status, "saved")
        self.assertTrue(saved.persisted)
        self.assertTrue(policy.task_opt_out and policy.session_opt_out)
        assert saved.path is not None
        loaded = handoffs.load(saved.path)
        self.assertEqual(loaded["task_id"], "parent/child")
        self.assertEqual(loaded["workflow_mode"], "lite")
        self.assertEqual(
            loaded["policy"], {"task_opt_out": True, "session_opt_out": True}
        )

    def _git(self, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(self.root), *arguments],
            env=self.env,
            capture_output=True,
            check=True,
            text=True,
        )

    def _commit(self, message: str = "synthetic commit") -> str:
        self._git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--allow-empty",
            "-m",
            message,
        )
        return self._git("rev-parse", "HEAD").stdout.strip()

    @staticmethod
    def _content(**overrides) -> dict:
        content = {
            "goal": "Continue synthetic work",
            "decisions": ["keep scope"],
            "completed": ["baseline checked"],
            "remaining": ["verify change"],
            "changed_files": [],
            "verification": ["synthetic smoke only"],
            "next_action": "Read the selected task",
            "do_not_repeat": ["do not change user environment"],
            "limitations": "No host session proof",
        }
        content.update(overrides)
        return content

    @staticmethod
    def _make_task(root: Path, task_id: str = "task") -> TaskStore:
        tasks = TaskStore(root)
        tasks.create(task_id, mode="lite", body="Synthetic task.\n", confirmed=True)
        return tasks

    def _save(self, handoffs: HandoffStore, task_id: str = "task", **overrides):
        arguments = {
            "content": self._content(),
            "trigger": "manual",
            "policy": HandoffPolicy(),
            "confirmed": True,
            "redaction_confirmed": True,
        }
        arguments.update(overrides)
        return handoffs.save(task_id, **arguments)

    def _age_snapshot(self, relative: str, days: int) -> str:
        source = self.root / relative
        text = source.read_text(encoding="utf-8")
        moment = datetime.now().astimezone() - timedelta(days=days)
        aged = re.sub(
            r"(?m)^created_at: .*$", f"created_at: '{moment.isoformat()}'", text
        )
        self.assertNotEqual(aged, text)
        target = source.with_name(moment.strftime("%Y_%m_%d") + source.name[10:])
        source.unlink()
        target.write_text(aged, encoding="utf-8")
        return "docs/handoffs/" + target.name

    def _handoff_files(self) -> list:
        base = self.root / "docs/handoffs"
        return sorted(entry.name for entry in base.iterdir()) if base.exists() else []

    def test_automatic_trigger_allowlist_saves_and_non_events_suppress(self) -> None:
        tasks = self._make_task(self.root)
        handoffs = HandoffStore(tasks)
        for non_event in ("checking", "call-count", ""):
            suppressed = self._save(handoffs, trigger=non_event)
            self.assertEqual(suppressed.status, "suppressed")
            self.assertFalse(suppressed.persisted)
        self.assertFalse((self.root / "docs/handoffs").exists())
        saved = self._save(handoffs, trigger="pause")
        self.assertEqual(saved.status, "saved")
        self.assertEqual(len(self._handoff_files()), 1)

    def test_session_optout_alone_suppresses_automatic_but_not_manual_save(
        self,
    ) -> None:
        tasks = self._make_task(self.root)
        handoffs = HandoffStore(tasks)
        policy = HandoffPolicy(session_opt_out=True)
        suppressed = self._save(handoffs, trigger="context-switch", policy=policy)
        self.assertEqual(suppressed.status, "suppressed")
        self.assertIn("session", suppressed.reason)
        self.assertFalse((self.root / "docs/handoffs").exists())
        saved = self._save(handoffs, trigger="manual", policy=policy)
        self.assertEqual(saved.status, "saved")
        self.assertFalse(policy.task_opt_out)
        self.assertTrue(policy.session_opt_out)

    def test_unconfirmed_save_reports_planned_snapshot_without_writing(self) -> None:
        tasks = self._make_task(self.root)
        planned = self._save(HandoffStore(tasks), confirmed=False)
        self.assertEqual(planned.status, "pending-confirmation")
        self.assertFalse(planned.persisted)
        self.assertIsNotNone(planned.snapshot)
        self.assertEqual(planned.snapshot["task_id"], "task")
        self.assertEqual(planned.snapshot["workflow_mode"], "lite")
        self.assertFalse((self.root / "docs/handoffs").exists())

    def test_writable_save_requires_explicit_redaction_confirmation(self) -> None:
        tasks = self._make_task(self.root)
        result = self._save(HandoffStore(tasks), redaction_confirmed=False)
        self.assertEqual(result.status, "needs-redaction")
        self.assertFalse(result.persisted)
        self.assertFalse((self.root / "docs/handoffs").exists())

    def test_unchanged_snapshot_is_not_rewritten_same_day_or_across_days(self) -> None:
        tasks = self._make_task(self.root)
        handoffs = HandoffStore(tasks)
        saved = self._save(handoffs)
        self.assertEqual(saved.status, "saved")
        first_bytes = (self.root / saved.path).read_bytes()
        again = self._save(handoffs)
        self.assertEqual(again.status, "unchanged")
        self.assertTrue(again.persisted)
        self.assertEqual(again.path, saved.path)
        self.assertEqual((self.root / saved.path).read_bytes(), first_bytes)
        aged_path = self._age_snapshot(saved.path, days=3)
        aged_bytes = (self.root / aged_path).read_bytes()
        across_days = self._save(handoffs)
        self.assertEqual(across_days.status, "unchanged")
        self.assertEqual(across_days.path, aged_path)
        self.assertEqual(self._handoff_files(), [Path(aged_path).name])
        self.assertEqual((self.root / aged_path).read_bytes(), aged_bytes)
        changed = self._save(
            handoffs, content=self._content(remaining=["verify change", "run smoke"])
        )
        self.assertEqual(changed.status, "saved")
        self.assertNotEqual(changed.path, aged_path)
        self.assertEqual(len(self._handoff_files()), 2)
        reminders = handoffs.reminders()
        self.assertEqual([entry["path"] for entry in reminders], [changed.path])

    def test_changed_task_context_rewrites_the_snapshot(self) -> None:
        tasks = self._make_task(self.root)
        handoffs = HandoffStore(tasks)
        saved = self._save(handoffs)
        self.assertEqual(saved.status, "saved")
        self.assertIsNone(handoffs.load(saved.path)["head"])
        tasks.transition(
            "task",
            "in-progress",
            reason="work started",
            evidence="synthetic transition",
            confirmed=True,
        )
        status_changed = self._save(handoffs)
        self.assertEqual(status_changed.status, "saved")
        self.assertEqual(status_changed.path, saved.path)
        self.assertEqual(handoffs.load(saved.path)["task_status"], "in-progress")
        head = self._commit()
        head_changed = self._save(handoffs)
        self.assertEqual(head_changed.status, "saved")
        self.assertEqual(handoffs.load(saved.path)["head"], head)
        tasks.set_mode("task", "strict", note="user chose strict", confirmed=True)
        mode_changed = self._save(handoffs)
        self.assertEqual(mode_changed.status, "saved")
        loaded = handoffs.load(saved.path)
        self.assertEqual(loaded["workflow_mode"], "strict")
        self.assertEqual(loaded["mode_note"], "user chose strict")

    def test_branch_mismatch_and_detached_head_reject_writes(self) -> None:
        tasks = self._make_task(self.root)
        handoffs = HandoffStore(tasks)
        head = self._commit()
        self._git("checkout", "-b", "other")
        conflict = self._save(handoffs)
        self.assertEqual(conflict.status, "branch-conflict")
        self.assertFalse(conflict.persisted)
        self.assertIsNone(conflict.path)
        self.assertFalse((self.root / "docs/handoffs").exists())
        self._git("checkout", "main")
        self._git("checkout", "--detach", "main")
        self.assertEqual(TaskStore(self.root).current_binding(), "detached:" + head)
        detached = self._save(HandoffStore(TaskStore(self.root)))
        self.assertEqual(detached.status, "branch-conflict")
        self.assertFalse((self.root / "docs/handoffs").exists())
        self._git("checkout", "main")
        saved = self._save(HandoffStore(TaskStore(self.root)))
        self.assertEqual(saved.status, "saved")
        self.assertEqual(handoffs.load(saved.path)["branch"], "main")
        self.assertEqual(handoffs.load(saved.path)["head"], head)

    def test_unborn_head_is_recorded_as_explicit_unknown(self) -> None:
        tasks = self._make_task(self.root)
        handoffs = HandoffStore(tasks)
        saved = self._save(handoffs)
        self.assertEqual(saved.status, "saved")
        loaded = handoffs.load(saved.path)
        self.assertEqual(loaded["branch"], "main")
        self.assertIsNone(loaded["head"])
        self.assertEqual(loaded["task_status"], "planned")

    def test_missing_protection_blocks_save_until_narrow_protect(self) -> None:
        (self.root / ".gitignore").write_text("/.sbtd/\n", encoding="utf-8")
        tasks = self._make_task(self.root)
        handoffs = HandoffStore(tasks)
        blocked = self._save(handoffs)
        self.assertEqual(blocked.status, "unprotected")
        self.assertFalse(blocked.persisted)
        self.assertFalse((self.root / "docs/handoffs").exists())
        with self.assertRaises(TaskStateError):
            handoffs.protect()
        self.assertTrue(handoffs.protect(confirmed=True))
        self.assertEqual(
            (self.root / ".gitignore").read_text(encoding="utf-8"),
            "/.sbtd/\n/docs/handoffs/\n",
        )
        saved = self._save(handoffs)
        self.assertEqual(saved.status, "saved")
        self.assertFalse(handoffs.protect(confirmed=True))

    def test_protect_does_not_hide_unknown_existing_data(self) -> None:
        (self.root / ".gitignore").write_text("/.sbtd/\n", encoding="utf-8")
        tasks = self._make_task(self.root)
        handoffs = HandoffStore(tasks)
        target = self.root / "docs/handoffs"
        target.mkdir(parents=True)
        (target / "existing.md").write_text("user data\n", encoding="utf-8")
        with self.assertRaises(TaskStateError):
            handoffs.protect(confirmed=True)
        self.assertEqual(
            (target / "existing.md").read_text(encoding="utf-8"), "user data\n"
        )
        self.assertEqual(
            (self.root / ".gitignore").read_text(encoding="utf-8"), "/.sbtd/\n"
        )
        blocked = self._save(handoffs)
        self.assertEqual(blocked.status, "unprotected")

    def test_tracked_handoff_directory_is_a_hard_conflict(self) -> None:
        tasks = self._make_task(self.root)
        handoffs = HandoffStore(tasks)
        target = self.root / "docs/handoffs"
        target.mkdir(parents=True)
        (target / "tracked.md").write_text("tracked\n", encoding="utf-8")
        self._git("add", "-f", "docs/handoffs/tracked.md")
        self._commit()
        with self.assertRaises(TaskStateError):
            self._save(handoffs)
        with self.assertRaises(TaskStateError):
            handoffs.protect(confirmed=True)

    def test_malformed_existing_snapshot_is_rejected_and_never_overwritten(
        self,
    ) -> None:
        tasks = self._make_task(self.root)
        handoffs = HandoffStore(tasks)
        saved = self._save(handoffs)
        target = self.root / saved.path
        target.write_text("not a handoff snapshot\n", encoding="utf-8")
        with self.assertRaises(TaskStateError):
            handoffs.load(saved.path)
        with self.assertRaises(TaskStateError):
            self._save(handoffs, content=self._content(remaining=["something else"]))
        self.assertEqual(target.read_text(encoding="utf-8"), "not a handoff snapshot\n")
        self.assertEqual(handoffs.reminders(), ())

    def test_load_rejects_foreign_root_filename_mismatch_and_bad_paths(self) -> None:
        tasks = self._make_task(self.root)
        handoffs = HandoffStore(tasks)
        saved = self._save(handoffs)
        original = (self.root / saved.path).read_text(encoding="utf-8")
        foreign_path = self._age_snapshot(saved.path, days=1)
        foreign = re.sub(
            r"(?m)^project_root: .*$",
            "project_root: /elsewhere",
            (self.root / foreign_path).read_text(encoding="utf-8"),
        )
        (self.root / foreign_path).write_text(foreign, encoding="utf-8")
        with self.assertRaises(TaskStateError):
            handoffs.load(foreign_path)
        mismatched = re.sub(r"(?m)^task_id: .*$", "task_id: other", original)
        (self.root / saved.path).write_text(mismatched, encoding="utf-8")
        with self.assertRaises(TaskStateError):
            handoffs.load(saved.path)
        for bad_path in (
            ".sbtd/active-task.json",
            "docs/handoffs",
            "docs/handoffs/../active-task.json",
            "docs/handoffs/2026_01_01-deadbeef.md",
        ):
            with self.assertRaises(TaskStateError):
                handoffs.load(bad_path)

    def test_reminders_filter_window_status_branch_and_root(self) -> None:
        tasks = self._make_task(self.root, "recent")
        handoffs = HandoffStore(tasks)
        recent = self._save(handoffs, "recent")
        tasks = self._make_task(self.root, "finished")
        done_snapshot = self._save(handoffs, "finished")
        for status, reason in (
            ("in-progress", "work started"),
            ("checking", "verifying"),
            ("done", "accepted"),
        ):
            tasks.transition(
                "finished",
                status,
                reason=reason,
                evidence="synthetic transition",
                confirmed=True,
            )
        self._make_task(self.root, "old")
        old = self._save(handoffs, "old")
        old_path = self._age_snapshot(old.path, days=8)
        foreign = re.sub(
            r"(?m)^project_root: .*$",
            "project_root: /elsewhere",
            (self.root / recent.path).read_text(encoding="utf-8"),
        )
        foreign_name = (datetime.now().astimezone() - timedelta(days=1)).strftime(
            "%Y_%m_%d"
        ) + Path(recent.path).name[10:]
        (self.root / "docs/handoffs" / foreign_name).write_text(
            foreign, encoding="utf-8"
        )
        reminders = handoffs.reminders()
        self.assertEqual([entry["task_id"] for entry in reminders], ["recent"])
        self.assertEqual(reminders[0]["path"], recent.path)
        self.assertEqual(handoffs.load(old_path)["task_id"], "old")
        self.assertTrue((self.root / done_snapshot.path).exists())
        self.assertEqual(
            handoffs.reminders(now=datetime.now().astimezone() + timedelta(days=8)), ()
        )
        self._commit()
        self._git("checkout", "-b", "other")
        self.assertEqual(HandoffStore(TaskStore(self.root)).reminders(), ())
        self._git("checkout", "main")
        self.assertEqual(
            [
                entry["task_id"]
                for entry in HandoffStore(TaskStore(self.root)).reminders()
            ],
            ["recent"],
        )

    def test_cancelled_tasks_get_no_unfinished_work_reminder(self) -> None:
        tasks = self._make_task(self.root)
        handoffs = HandoffStore(tasks)
        saved = self._save(handoffs)
        tasks.transition(
            "task",
            "cancelled",
            reason="scope withdrawn",
            evidence="decision",
            confirmed=True,
        )
        self.assertEqual(handoffs.reminders(), ())
        self.assertEqual(handoffs.load(saved.path)["task_id"], "task")
        cancelled = self._save(handoffs)
        self.assertEqual(cancelled.status, "saved")
        assert cancelled.snapshot is not None
        self.assertEqual(cancelled.snapshot["task_status"], "cancelled")
        self.assertEqual(handoffs.reminders(), ())

    def test_readonly_store_still_loads_and_lists_reminders(self) -> None:
        tasks = self._make_task(self.root)
        saved = self._save(HandoffStore(tasks))
        readonly = HandoffStore(TaskStore(self.root, read_only=True))
        self.assertEqual(readonly.load(saved.path)["task_id"], "task")
        self.assertEqual([entry["task_id"] for entry in readonly.reminders()], ["task"])

    def test_full_logical_id_prevents_basename_collisions(self) -> None:
        tasks = TaskStore(self.root)
        for parent in ("a", "b"):
            tasks.create(
                parent, mode="lite", body="Synthetic parent.\n", confirmed=True
            )
            tasks.create(
                f"{parent}/child",
                mode="lite",
                body="Synthetic child.\n",
                parent=parent,
                confirmed=True,
            )
        handoffs = HandoffStore(tasks)
        first = self._save(handoffs, "a/child")
        second = self._save(handoffs, "b/child")
        self.assertEqual(first.status, "saved")
        self.assertEqual(second.status, "saved")
        self.assertNotEqual(first.path, second.path)
        self.assertNotIn("child", Path(first.path).name)
        self.assertEqual(handoffs.load(first.path)["task_id"], "a/child")
        self.assertEqual(handoffs.load(second.path)["task_id"], "b/child")

    def test_unknown_files_in_handoffs_directory_are_left_alone(self) -> None:
        tasks = self._make_task(self.root)
        handoffs = HandoffStore(tasks)
        saved = self._save(handoffs)
        junk = {
            "notes.txt": "plain notes\n",
            "random.md": "not a snapshot\n",
            "2099_01_01-ff.md": "garbage\n",
        }
        for name, text in junk.items():
            (self.root / "docs/handoffs" / name).write_text(text, encoding="utf-8")
        unchanged = self._save(handoffs)
        self.assertEqual(unchanged.status, "unchanged")
        self.assertEqual([entry["task_id"] for entry in handoffs.reminders()], ["task"])
        for name, text in junk.items():
            self.assertEqual(
                (self.root / "docs/handoffs" / name).read_text(encoding="utf-8"), text
            )
        self.assertTrue((self.root / saved.path).exists())

    def test_handoff_flow_writes_nothing_under_home(self) -> None:
        fake_home = Path(self.temporary.name).resolve() / "fake-home"
        fake_home.mkdir()
        with patch.dict(os.environ, {"HOME": str(fake_home)}):
            tasks = self._make_task(self.root)
            handoffs = HandoffStore(tasks)
            saved = self._save(handoffs)
            self.assertEqual(saved.status, "saved")
            handoffs.load(saved.path)
            handoffs.reminders()
        self.assertEqual(list(fake_home.iterdir()), [])

    def test_non_git_project_uses_explicit_final_root_ignore(self) -> None:
        root = Path(self.temporary.name).resolve() / "nogit"
        root.mkdir()
        (root / ".gitignore").write_text("/.sbtd/\n", encoding="utf-8")
        tasks = self._make_task(root)
        handoffs = HandoffStore(tasks)
        self.assertTrue(handoffs.protect(confirmed=True))
        self.assertEqual(
            (root / ".gitignore").read_text(encoding="utf-8"),
            "/docs/handoffs/\n/.sbtd/\n",
        )
        self.assertFalse(handoffs.protect(confirmed=True))
        saved = handoffs.save(
            "task",
            content=self._content(),
            trigger="manual",
            policy=HandoffPolicy(),
            confirmed=True,
            redaction_confirmed=True,
        )
        self.assertEqual(saved.status, "saved")
        assert saved.path is not None
        loaded = handoffs.load(saved.path)
        self.assertIsNone(loaded["branch"])
        self.assertIsNone(loaded["head"])
        self.assertEqual([entry["task_id"] for entry in handoffs.reminders()], ["task"])
        tasks.transition(
            "task",
            "in-progress",
            reason="work started",
            evidence="synthetic transition",
            confirmed=True,
        )
        self.assertEqual(
            tasks.inspect("task").document.frontmatter["status"], "in-progress"
        )

    def test_newest_snapshot_wins_when_context_returns_to_an_older_value(self) -> None:
        tasks = self._make_task(self.root)
        handoffs = HandoffStore(tasks)
        first = self._save(handoffs, content=self._content(goal="context A"))
        self.assertEqual(first.status, "saved")
        self._age_snapshot(first.path, days=2)
        middle = self._save(handoffs, content=self._content(goal="context B"))
        self.assertEqual(middle.status, "saved")
        self._age_snapshot(middle.path, days=1)
        latest = self._save(handoffs, content=self._content(goal="context A"))
        self.assertEqual(latest.status, "saved")
        reminders = handoffs.reminders()
        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0]["path"], latest.path)
        self.assertEqual(reminders[0]["content"]["goal"], "context A")

    def test_non_git_protection_uses_the_last_relevant_rule(self) -> None:
        root = Path(self.temporary.name).resolve() / "nogit-rule-order"
        root.mkdir()
        (root / ".gitignore").write_text(
            "/docs/handoffs/\n!/docs/handoffs/\n/.sbtd/\n", encoding="utf-8"
        )
        tasks = self._make_task(root)
        handoffs = HandoffStore(tasks)
        self.assertTrue(handoffs.protect(confirmed=True))
        self.assertEqual(
            (root / ".gitignore").read_text(encoding="utf-8"),
            "/docs/handoffs/\n!/docs/handoffs/\n/docs/handoffs/\n/.sbtd/\n",
        )
        self.assertEqual(
            self._save(handoffs).status,
            "saved",
        )

    def test_non_git_leading_space_rule_does_not_claim_protection(self) -> None:
        root = Path(self.temporary.name).resolve() / "nogit-leading-space"
        root.mkdir()
        (root / ".gitignore").write_text(
            " /docs/handoffs/\n/.sbtd/\n", encoding="utf-8"
        )
        handoffs = HandoffStore(self._make_task(root))
        self.assertEqual(self._save(handoffs).status, "unprotected")

    def test_long_legal_task_id_uses_a_bounded_handoff_filename(self) -> None:
        task_id = "a" * 121
        tasks = self._make_task(self.root, task_id)
        saved = self._save(HandoffStore(tasks), task_id)
        self.assertEqual(saved.status, "saved")
        assert saved.path is not None
        self.assertLessEqual(len(Path(saved.path).name.encode("utf-8")), 255)
        self.assertEqual(HandoffStore(tasks).load(saved.path)["task_id"], task_id)

    def test_existing_reversible_hex_handoff_name_remains_loadable(self) -> None:
        task_id = "legacy/name"
        handoffs = HandoffStore(self._make_task(self.root, task_id))
        saved = self._save(handoffs, task_id)
        assert saved.path is not None
        original = self.root / saved.path
        legacy_name = (
            original.name[:11] + task_id.encode("utf-8").hex() + original.suffix
        )
        legacy = original.with_name(legacy_name)
        original.rename(legacy)
        self.assertEqual(
            handoffs.load(f"docs/handoffs/{legacy.name}")["task_id"], task_id
        )

    def test_future_snapshot_is_not_a_recent_unfinished_reminder(self) -> None:
        tasks = self._make_task(self.root)
        handoffs = HandoffStore(tasks)
        saved = self._save(handoffs)
        future = self._age_snapshot(saved.path, days=-1)
        self.assertEqual(handoffs.load(future)["task_id"], "task")
        self.assertEqual(handoffs.reminders(), ())

    def test_reminder_requires_the_actual_task_binding_to_match(self) -> None:
        tasks = self._make_task(self.root)
        handoffs = HandoffStore(tasks)
        saved = self._save(handoffs)
        task = tasks.inspect("task")
        changed = task.document.updated({"branch": "another-worktree"})
        (self.root / task.task_path).write_text(changed.text, encoding="utf-8")
        self.assertEqual(handoffs.load(saved.path)["branch"], "main")
        self.assertEqual(handoffs.reminders(), ())

    def test_user_change_after_ownership_read_is_not_authorized_by_a_second_read(
        self,
    ) -> None:
        tasks = self._make_task(self.root)
        handoffs = HandoffStore(tasks)
        saved = self._save(handoffs)
        target = self.root / saved.path
        user_change = b"User replaced this file after the ownership check.\n"
        reads = 0

        @contextmanager
        def change_after_ownership(path, label):
            nonlocal reads
            with open_regular_file(path, label) as handle:
                yield handle
            if path == target:
                reads += 1
                if reads == 2:
                    target.write_bytes(user_change)

        with (
            patch("sbtd_handoff.open_regular_file", side_effect=change_after_ownership),
            self.assertRaises(TaskDataError),
        ):
            self._save(
                handoffs, content=self._content(remaining=["new actual context"])
            )
        self.assertEqual(target.read_bytes(), user_change)


if __name__ == "__main__":
    unittest.main()
