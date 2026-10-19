from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sbtd-workflow-onboard/scripts"))

from sbtd_task_routing import RouteRequest, TaskRouter
from sbtd_task_state import TaskStore


class TaskRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="sbtd-route-test-")
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

    def test_readonly_explicit_mode_does_not_replace_persisted_continuation_mode(
        self,
    ) -> None:
        store = TaskStore(self.root)
        task = store.create(
            "same-task", mode="lite", body="Keep this scope.\n", confirmed=True
        )
        before = (self.root / task.task_path).read_bytes()
        readonly = TaskRouter(store).route(
            RouteRequest(
                intent="continue",
                task_id="same-task",
                explicit_mode="strict",
                read_only=True,
            )
        )
        self.assertEqual(readonly.status, "ready")
        self.assertEqual(readonly.mode, "strict")
        self.assertFalse(readonly.persisted)
        self.assertEqual((self.root / task.task_path).read_bytes(), before)
        continued = TaskRouter(store).route(
            RouteRequest(intent="continue", task_id="same-task")
        )
        self.assertEqual(continued.status, "ready")
        self.assertEqual(continued.mode, "lite")
        self.assertTrue(continued.persisted)
        question = TaskRouter(store).route(RouteRequest(intent="question"))
        self.assertEqual(question.mode, "default")
        self.assertFalse(question.persisted)

    def test_ambiguous_continuation_asks_for_task_before_mode(self) -> None:
        store = TaskStore(self.root)
        first = store.create("first", mode="lite", body="First\n", confirmed=True)
        second = store.create("second", mode="strict", body="Second\n", confirmed=True)
        (self.root / ".sbtd/active-task.json").unlink()
        decision = TaskRouter(store).route(RouteRequest(intent="continue"))
        self.assertEqual(decision.status, "needs-task-choice")
        self.assertIsNone(decision.mode)
        self.assertEqual(set(decision.candidates), {"first", "second"})
        chosen = TaskRouter(store).route(
            RouteRequest(intent="continue", task_id="first")
        )
        self.assertEqual(chosen.mode, "lite")
        assert chosen.task is not None
        self.assertEqual(chosen.task.task_path, first.task_path)
        self.assertFalse((self.root / ".sbtd/active-task.json").exists())
        self.assertTrue((self.root / second.task_path).is_file())

    def test_recommendation_pauses_and_a_refusal_survives_a_new_router(self) -> None:
        from sbtd_task_routing import ModeRecommendation

        store = TaskStore(self.root)
        original = store.create(
            "choice", mode="lite", body="Keep explicit delivery.\n", confirmed=True
        )
        recommendation = ModeRecommendation(
            "strict", "new cross-service risk", "risk-A"
        )
        before = (self.root / original.task_path).read_bytes()
        prompted = TaskRouter(store).route(
            RouteRequest(
                intent="continue", task_id="choice", recommendation=recommendation
            )
        )
        self.assertEqual(prompted.status, "needs-mode-decision")
        self.assertEqual(prompted.mode, "lite")
        self.assertEqual((self.root / original.task_path).read_bytes(), before)
        kept = TaskRouter(store).route(
            RouteRequest(
                intent="continue",
                task_id="choice",
                recommendation=recommendation,
                recommendation_response="keep",
                refusal_reason="user prefers lite",
                confirmed=True,
            )
        )
        self.assertEqual(kept.mode, "lite")
        self.assertTrue(kept.persisted)
        repeated = TaskRouter(store).route(
            RouteRequest(
                intent="continue", task_id="choice", recommendation=recommendation
            )
        )
        self.assertEqual(repeated.status, "ready")
        self.assertEqual(repeated.mode, "lite")
        changed_risk = TaskRouter(store).route(
            RouteRequest(
                intent="continue",
                task_id="choice",
                recommendation=ModeRecommendation(
                    "strict", "new destructive scope", "risk-B"
                ),
            )
        )
        self.assertEqual(changed_risk.status, "needs-mode-decision")

    def test_accepting_a_previously_kept_recommendation_clears_its_refusal(
        self,
    ) -> None:
        from sbtd_task_routing import ModeRecommendation

        store = TaskStore(self.root)
        store.create("reconsider", mode="lite", body="Task\n", confirmed=True)
        recommendation = ModeRecommendation("strict", "new risk", "risk-1")
        kept = TaskRouter(store).route(
            RouteRequest(
                intent="continue",
                task_id="reconsider",
                recommendation=recommendation,
                recommendation_response="keep",
                refusal_reason="retain lite",
                confirmed=True,
            )
        )
        self.assertEqual(kept.status, "ready")
        accepted = TaskRouter(store).route(
            RouteRequest(
                intent="continue",
                task_id="reconsider",
                recommendation=recommendation,
                recommendation_response="accept",
                confirmed=True,
            )
        )
        self.assertEqual(accepted.status, "ready")
        self.assertEqual(accepted.mode, "strict")
        changed = TaskRouter(store).route(
            RouteRequest(
                intent="continue",
                task_id="reconsider",
                explicit_mode="lite",
                confirmed=True,
            )
        )
        self.assertEqual(changed.status, "ready")
        prompted = TaskRouter(store).route(
            RouteRequest(
                intent="continue", task_id="reconsider", recommendation=recommendation
            )
        )
        self.assertEqual(prompted.status, "needs-mode-decision")

    def test_replayed_keep_decision_needs_no_persistence_confirmation(self) -> None:
        from sbtd_task_routing import ModeRecommendation

        store = TaskStore(self.root)
        task = store.create("keep-replay", mode="lite", body="Task\n", confirmed=True)
        recommendation = ModeRecommendation("strict", "new risk", "risk-1")
        saved = TaskRouter(store).route(
            RouteRequest(
                intent="continue",
                task_id="keep-replay",
                recommendation=recommendation,
                recommendation_response="keep",
                refusal_reason="retain lite",
                confirmed=True,
            )
        )
        self.assertEqual(saved.status, "ready")
        before = (self.root / task.task_path).read_bytes()
        replayed = TaskRouter(store).route(
            RouteRequest(
                intent="continue",
                task_id="keep-replay",
                recommendation=recommendation,
                recommendation_response="keep",
                refusal_reason="retain lite",
            )
        )
        self.assertEqual(replayed.status, "ready")
        self.assertTrue(replayed.persisted)
        self.assertEqual((self.root / task.task_path).read_bytes(), before)


    def test_failed_mode_save_keeps_session_choice_without_claiming_recovery(
        self,
    ) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "save-failure", mode="lite", body="Keep the task.\n", confirmed=True
        )
        path = self.root / original.task_path
        before = path.read_bytes()
        router = TaskRouter(store)
        with mock.patch(
            "sbtd_task_state.os.replace",
            side_effect=PermissionError("synthetic readonly file"),
        ):
            failed = router.route(
                RouteRequest(
                    intent="continue",
                    task_id="save-failure",
                    explicit_mode="strict",
                    confirmed=True,
                )
            )
        self.assertEqual(failed.status, "persistence-failed")
        self.assertEqual(failed.mode, "strict")
        self.assertFalse(failed.persisted)
        self.assertEqual(path.read_bytes(), before)
        continued = router.route(
            RouteRequest(intent="continue", task_id="save-failure", read_only=True)
        )
        self.assertEqual(continued.mode, "strict")
        self.assertFalse(continued.persisted)
        restarted = TaskRouter(store).route(
            RouteRequest(intent="continue", task_id="save-failure")
        )
        self.assertEqual(restarted.mode, "lite")

    def test_branch_choice_precedes_persistence_but_readonly_can_inspect(self) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "branch-choice", mode="lite", body="Keep branch binding.\n", confirmed=True
        )
        before = (self.root / original.task_path).read_bytes()
        subprocess.run(
            ["git", "-C", str(self.root), "switch", "--orphan", "other"],
            env=self.env,
            capture_output=True,
            check=True,
        )
        blocked = TaskRouter(store).route(
            RouteRequest(
                intent="continue",
                task_id="branch-choice",
                explicit_mode="strict",
                confirmed=True,
            )
        )
        self.assertEqual(blocked.status, "needs-branch-choice")
        self.assertFalse(blocked.persisted)
        self.assertEqual((self.root / original.task_path).read_bytes(), before)
        inspected = TaskRouter(store).route(
            RouteRequest(intent="continue", task_id="branch-choice", read_only=True)
        )
        self.assertEqual(inspected.status, "ready")
        self.assertEqual(inspected.mode, "lite")
        self.assertEqual((self.root / original.task_path).read_bytes(), before)

    def test_unknown_legacy_mode_is_not_a_new_task_default(self) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "unknown", body="Legacy mode unknown.\n", confirmed=True
        )
        legacy = original.document.updated(
            {
                "workflow_mode": None,
                "mode_source": "migration-unknown",
                "mode_note": "no original choice",
            }
        )
        path = self.root / original.task_path
        path.write_text(legacy.text, encoding="utf-8")
        decision = TaskRouter(store).route(
            RouteRequest(intent="continue", task_id="unknown")
        )
        self.assertEqual(decision.status, "needs-mode-choice")
        self.assertIsNone(decision.mode)
        self.assertEqual(path.read_text(), legacy.text)

    def test_downgrade_requires_acceptance_and_never_moves_shared_history(self) -> None:
        from sbtd_task_routing import ModeRecommendation

        store = TaskStore(self.root)
        original = store.create(
            "shared-mode",
            mode="strict",
            body="Shared historical content.\n",
            confirmed=True,
        )
        proposal = ModeRecommendation(
            "lite", "scope is a verified small change", "small-change"
        )
        pending = TaskRouter(store).route(
            RouteRequest(
                intent="continue", task_id="shared-mode", recommendation=proposal
            )
        )
        self.assertEqual(pending.status, "needs-mode-decision")
        self.assertEqual(pending.mode, "strict")
        accepted = TaskRouter(store).route(
            RouteRequest(
                intent="continue",
                task_id="shared-mode",
                recommendation=proposal,
                recommendation_response="accept",
                confirmed=True,
            )
        )
        self.assertEqual(accepted.mode, "lite")
        self.assertTrue(accepted.persisted)
        assert accepted.task is not None
        self.assertEqual(accepted.task.task_path, original.task_path)
        self.assertIn("Shared historical content.", accepted.task.document.text)

    def test_explicit_new_mode_is_saved_with_user_source(self) -> None:
        decision = TaskRouter(TaskStore(self.root)).route(
            RouteRequest(
                intent="new",
                task_id="new-default",
                explicit_mode="default",
                body="Explicit default choice.\n",
                confirmed=True,
            )
        )
        self.assertEqual(decision.status, "ready")
        assert decision.task is not None
        self.assertEqual(decision.task.document.frontmatter["mode_source"], "user")
        independent = TaskRouter(TaskStore(self.root)).route(
            RouteRequest(
                intent="new",
                task_id="independent",
                body="New task, not inherited.\n",
                confirmed=True,
            )
        )
        self.assertEqual(independent.mode, "default")
        assert independent.task is not None
        self.assertEqual(
            independent.task.document.frontmatter["mode_source"], "default"
        )

    def test_newer_task_choice_invalidates_an_unpersisted_session_snapshot(
        self,
    ) -> None:
        store = TaskStore(self.root)
        store.create("fresh-choice", mode="lite", body="Task\n", confirmed=True)
        router = TaskRouter(store)
        pending = router.route(
            RouteRequest(
                intent="continue",
                task_id="fresh-choice",
                explicit_mode="strict",
                read_only=True,
            )
        )
        self.assertEqual(pending.mode, "strict")
        store.set_mode(
            "fresh-choice", "default", note="newer actual user choice", confirmed=True
        )
        resumed = router.route(RouteRequest(intent="continue", task_id="fresh-choice"))
        self.assertEqual(resumed.mode, "default")
        self.assertTrue(resumed.persisted)

    def test_malformed_active_pointer_is_not_replaced_by_latest_task(self) -> None:
        store = TaskStore(self.root)
        first = store.create("older", mode="lite", body="First\n", confirmed=True)
        store.create("newer", mode="strict", body="Second\n", confirmed=True)
        pointer = self.root / ".sbtd/active-task.json"
        pointer.write_bytes(b'{"schema_version":1,"task_id":"broken"}')
        before = pointer.read_bytes()
        result = TaskRouter(store).route(
            RouteRequest(intent="continue", confirmed=True)
        )
        self.assertEqual(result.status, "blocked")
        self.assertIsNone(result.mode)
        self.assertEqual(pointer.read_bytes(), before)
        explicit = TaskRouter(store).route(
            RouteRequest(intent="continue", task_id="older", read_only=True)
        )
        self.assertEqual(explicit.mode, "lite")
        assert explicit.task is not None
        self.assertEqual(explicit.task.task_path, first.task_path)

    def test_explicit_session_choice_survives_separate_branch_rebinding(self) -> None:
        store = TaskStore(self.root)
        task = store.create(
            "branch-mode",
            mode="lite",
            body="Mode and branch are separate choices.\n",
            confirmed=True,
        )
        subprocess.run(
            ["git", "-C", str(self.root), "switch", "--orphan", "other"],
            env=self.env,
            capture_output=True,
            check=True,
        )
        router = TaskRouter(store)
        pending = router.route(
            RouteRequest(
                intent="continue",
                task_id="branch-mode",
                explicit_mode="strict",
                confirmed=True,
            )
        )
        self.assertEqual(pending.status, "needs-branch-choice")
        self.assertEqual(pending.mode, "strict")
        self.assertEqual(
            store.inspect("branch-mode").document.frontmatter["workflow_mode"], "lite"
        )
        store.rebind(
            "branch-mode",
            expected_branch="main",
            reason="user selected this checkout",
            evidence="explicit choice",
            confirmed=True,
        )
        continued = router.route(
            RouteRequest(intent="continue", task_id="branch-mode", confirmed=True)
        )
        self.assertEqual(continued.mode, "strict")
        self.assertTrue(continued.persisted)
        assert continued.task is not None
        self.assertEqual(continued.task.task_path, task.task_path)

    def test_explicit_mode_survives_pending_recommendation_then_keep(self) -> None:
        from sbtd_task_routing import ModeRecommendation

        store = TaskStore(self.root)
        store.create(
            "explicit-pending", mode="lite", body="Keep scope.\n", confirmed=True
        )
        router = TaskRouter(store)
        recommendation = ModeRecommendation("strict", "documented risk", "risk")
        pending = router.route(
            RouteRequest(
                intent="continue",
                task_id="explicit-pending",
                explicit_mode="default",
                recommendation=recommendation,
            )
        )
        self.assertEqual(pending.status, "needs-mode-decision")
        kept = router.route(
            RouteRequest(
                intent="continue",
                task_id="explicit-pending",
                recommendation=recommendation,
                recommendation_response="keep",
                refusal_reason="keep my explicit default",
                confirmed=True,
            )
        )
        self.assertEqual(kept.mode, "default")
        self.assertEqual(
            store.inspect("explicit-pending").document.frontmatter["workflow_mode"],
            "default",
        )

    def test_accepted_recommendation_survives_branch_choice(self) -> None:
        from sbtd_task_routing import ModeRecommendation

        store = TaskStore(self.root)
        store.create(
            "accepted-branch", mode="lite", body="Keep scope.\n", confirmed=True
        )
        subprocess.run(
            ["git", "-C", str(self.root), "switch", "--orphan", "other"],
            env=self.env,
            capture_output=True,
            check=True,
        )
        router = TaskRouter(store)
        pending = router.route(
            RouteRequest(
                intent="continue",
                task_id="accepted-branch",
                recommendation=ModeRecommendation("strict", "accepted risk", "risk"),
                recommendation_response="accept",
                confirmed=True,
            )
        )
        self.assertEqual(pending.status, "needs-branch-choice")
        self.assertEqual(pending.mode, "strict")
        store.rebind(
            "accepted-branch",
            expected_branch="main",
            reason="explicit branch choice",
            evidence="confirmed",
            confirmed=True,
        )
        resumed = router.route(
            RouteRequest(intent="continue", task_id="accepted-branch", confirmed=True)
        )
        self.assertEqual(resumed.mode, "strict")
        self.assertTrue(resumed.persisted)

    def test_uncreated_task_keeps_explicit_mode_until_authorized_retry(self) -> None:
        router = TaskRouter(TaskStore(self.root))
        pending = router.route(
            RouteRequest(
                intent="new",
                task_id="not-created",
                explicit_mode="strict",
                body="Task\n",
            )
        )
        self.assertEqual(pending.status, "needs-persistence-confirmation")
        self.assertFalse((self.root / "ai/tasks/not-created").exists())
        created = router.route(
            RouteRequest(
                intent="new", task_id="not-created", body="Task\n", confirmed=True
            )
        )
        self.assertEqual(created.mode, "strict")
        assert created.task is not None
        self.assertEqual(created.task.document.frontmatter["mode_source"], "user")

    def test_missing_yaml_reports_unsaved_choice_instead_of_escaping(self) -> None:
        router = TaskRouter(TaskStore(self.root))
        with mock.patch.dict(sys.modules, {"yaml": None}):
            failed = router.route(
                RouteRequest(
                    intent="new",
                    task_id="missing-yaml",
                    explicit_mode="strict",
                    body="Task\n",
                    confirmed=True,
                )
            )
        self.assertEqual(failed.status, "persistence-failed")
        self.assertEqual(failed.mode, "strict")
        self.assertFalse(failed.persisted)
        self.assertFalse((self.root / "ai").exists())
        resumed = router.route(
            RouteRequest(
                intent="new", task_id="missing-yaml", body="Task\n", confirmed=True
            )
        )
        self.assertEqual(resumed.mode, "strict")
        self.assertTrue(resumed.persisted)

    def test_refusal_survives_branch_choice_without_reprompting(self) -> None:
        from sbtd_task_routing import ModeRecommendation

        store = TaskStore(self.root)
        store.create("keep-branch", mode="lite", body="Task\n", confirmed=True)
        subprocess.run(
            ["git", "-C", str(self.root), "switch", "--orphan", "other"],
            env=self.env,
            capture_output=True,
            check=True,
        )
        recommendation = ModeRecommendation("strict", "same risk", "same-risk")
        router = TaskRouter(store)
        pending = router.route(
            RouteRequest(
                intent="continue",
                task_id="keep-branch",
                recommendation=recommendation,
                recommendation_response="keep",
                refusal_reason="retain lite",
                confirmed=True,
            )
        )
        self.assertEqual(pending.status, "needs-branch-choice")
        store.rebind(
            "keep-branch",
            expected_branch="main",
            reason="explicit branch choice",
            evidence="approved",
            confirmed=True,
        )
        resumed = router.route(
            RouteRequest(
                intent="continue",
                task_id="keep-branch",
                recommendation=recommendation,
                confirmed=True,
            )
        )
        self.assertEqual(resumed.status, "ready")
        self.assertEqual(resumed.mode, "lite")
        self.assertTrue(resumed.persisted)
        repeated = TaskRouter(store).route(
            RouteRequest(
                intent="continue", task_id="keep-branch", recommendation=recommendation
            )
        )
        self.assertEqual(repeated.status, "ready")

    def test_new_task_without_an_id_asks_for_that_choice_before_confirmation(
        self,
    ) -> None:
        decision = TaskRouter(TaskStore(self.root)).route(
            RouteRequest(intent="new", explicit_mode="strict", body="Task\n")
        )
        self.assertEqual(decision.status, "needs-task-choice")
        self.assertFalse(decision.persisted)
        self.assertFalse((self.root / ".sbtd").exists())

    def test_mode_note_with_decision_prefix_is_valid_free_text(self) -> None:
        store = TaskStore(self.root)
        task = store.create(
            "prefix-note",
            mode="lite",
            mode_note="SBTD mode decisions: ordinary user explanation",
            body="Task\n",
            confirmed=True,
        )
        decision = TaskRouter(store).route(
            RouteRequest(intent="continue", task_id="prefix-note")
        )
        self.assertEqual(decision.status, "ready")
        self.assertEqual(decision.mode, "lite")
        self.assertEqual(
            store.inspect("prefix-note").document.frontmatter["mode_note"],
            task.document.frontmatter["mode_note"],
        )

    def test_accepted_recommendation_persists_its_reason_and_risk(self) -> None:
        from sbtd_task_routing import ModeRecommendation

        store = TaskStore(self.root)
        store.create("accept-note", mode="lite", body="Task\n", confirmed=True)
        decision = TaskRouter(store).route(
            RouteRequest(
                intent="continue",
                task_id="accept-note",
                recommendation=ModeRecommendation(
                    "strict", "cross-service mutation", "risk-42"
                ),
                recommendation_response="accept",
                confirmed=True,
            )
        )
        self.assertEqual(decision.status, "ready")
        persisted_note = store.inspect("accept-note").document.frontmatter["mode_note"]
        self.assertIn("cross-service mutation", persisted_note)
        self.assertIn("risk-42", persisted_note)

    def test_identical_explicit_user_choice_does_not_reconfirm_or_rewrite(self) -> None:
        store = TaskStore(self.root)
        task = store.create(
            "same-choice",
            mode="lite",
            mode_note="user kept lite",
            body="Task\n",
            confirmed=True,
        )
        before = (self.root / task.task_path).read_bytes()
        decision = TaskRouter(store).route(
            RouteRequest(
                intent="continue",
                task_id="same-choice",
                explicit_mode="lite",
                mode_note="user kept lite",
            )
        )
        self.assertEqual(decision.status, "ready")
        self.assertTrue(decision.persisted)
        self.assertEqual((self.root / task.task_path).read_bytes(), before)

    def test_partial_new_task_creation_retries_with_the_original_explicit_mode(
        self,
    ) -> None:
        store = TaskStore(self.root)
        router = TaskRouter(store)
        real_link = os.link

        def fail_pointer(source, target, *args, **kwargs):
            if Path(target).name == "active-task.json":
                raise PermissionError("synthetic pointer failure")
            return real_link(source, target, *args, **kwargs)

        with mock.patch("sbtd_task_state.os.link", side_effect=fail_pointer):
            failed = router.route(
                RouteRequest(
                    intent="new",
                    task_id="partial-mode",
                    explicit_mode="strict",
                    body="Original task.\n",
                    confirmed=True,
                )
            )
        self.assertEqual(failed.status, "persistence-failed")
        original = (self.root / "ai/tasks/partial-mode/task.md").read_bytes()
        self.assertFalse((self.root / ".sbtd/active-task.json").exists())
        resumed = router.route(
            RouteRequest(
                intent="new",
                task_id="partial-mode",
                body="Original task.\n",
                confirmed=True,
            )
        )
        self.assertEqual(resumed.status, "ready")
        self.assertEqual(resumed.mode, "strict")
        self.assertTrue(resumed.persisted)
        self.assertEqual(
            (self.root / "ai/tasks/partial-mode/task.md").read_bytes(), original
        )
        self.assertEqual(
            store.inspect().document.frontmatter["workflow_mode"], "strict"
        )

    def test_continuing_a_cancelled_task_keeps_its_recorded_choice(self) -> None:
        store = TaskStore(self.root)
        original = store.create(
            "withdrawn", mode="lite", body="Cancelled scope.\n", confirmed=True
        )
        store.transition(
            "withdrawn",
            "cancelled",
            reason="scope withdrawn",
            evidence="decision",
            confirmed=True,
        )
        before = (self.root / original.task_path).read_bytes()
        decision = TaskRouter(store).route(
            RouteRequest(intent="continue", task_id="withdrawn")
        )
        self.assertEqual(decision.status, "ready")
        self.assertEqual(decision.mode, "lite")
        self.assertTrue(decision.persisted)
        assert decision.task is not None
        self.assertEqual(decision.task.document.frontmatter["status"], "cancelled")
        self.assertEqual((self.root / original.task_path).read_bytes(), before)
        changed = TaskRouter(store).route(
            RouteRequest(
                intent="continue",
                task_id="withdrawn",
                explicit_mode="strict",
                mode_note="user now wants strict review",
                confirmed=True,
            )
        )
        self.assertEqual(changed.status, "ready")
        self.assertTrue(changed.persisted)
        persisted = store.inspect("withdrawn").document.frontmatter
        self.assertEqual(persisted["workflow_mode"], "strict")
        self.assertEqual(persisted["status"], "cancelled")
        self.assertIsNone(persisted["completed_at"])


if __name__ == "__main__":
    unittest.main()
