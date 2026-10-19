from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import shutil
import tempfile
import unittest
from contextlib import contextmanager, nullcontext, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard" / "scripts"
TESTS = Path(__file__).resolve().parent
for import_path in (str(SCRIPTS), str(TESTS)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)


from onboard_arguments import parse_workflow_args
from onboard_contracts import ContractError, canonical_json_bytes, seal_document
from sbtd_migration import apply_migration, run_migration, runtime_versions
from sbtd_migration_files import (
    backup_reference,
    require_private_directory,
    save_document,
    snapshot,
)
from sbtd_migration_plan import plan_migration
from sbtd_migration_verify import verify_migration
from test_sbtd_migration_apply import legacy_project
from test_sbtd_migration_verify import _file_ref, _tree_bytes


def _fake_prepare_trellis_uninstall(root: Path) -> dict[str, Any]:
    """Test-only vendor seam; production always uses the installed tl CLI."""
    target = Path(root) / ".trellis"
    before = snapshot(target)
    return {
        "schema_version": 1,
        "kind": "trellis-uninstall-prepare",
        "prepared_id": hashlib.sha256(str(target).encode()).hexdigest(),
        "payload": {
            "root": str(root),
            "status": "ready",
            "resources": [
                {
                    "kind": "vendor-trellis-dir",
                    "path": str(target),
                    "before": before,
                    "expected_after": {"type": "absent", "checksum": None},
                }
            ],
        },
    }


def _fake_execute_trellis_uninstall(
    root: Path, prepared: dict[str, Any], backup_root: Path
) -> dict[str, Any]:
    target = Path(root) / ".trellis"
    before = snapshot(target)
    private = Path(backup_root)
    backup_dir = require_private_directory(
        private / prepared["prepared_id"], create=True
    )
    backup_ref = backup_reference(
        {"path": str(target), "state": before},
        backup_dir / "trellis",
        private_root=private,
    )
    shutil.rmtree(target)  # Test double only; production never deletes .trellis.
    after = snapshot(target)
    return {
        "status": "removed",
        "exit": 0,
        "results": [
            {
                "path": str(target),
                "before": before,
                "after": after,
                "status": "removed",
                "backup_ref": backup_ref,
            }
        ],
        "errors": [],
    }


@contextmanager
def _fake_vendor_adapter(*, prepare=None, execute=None):
    def guarded_execute(root, prepared, backup_root, *, before_execute=None):
        if before_execute is not None:
            before_execute()
        return (execute or _fake_execute_trellis_uninstall)(root, prepared, backup_root)

    with (
        mock.patch(
            "sbtd_trellis_uninstall.prepare_trellis_uninstall",
            side_effect=prepare or _fake_prepare_trellis_uninstall,
        ),
        mock.patch(
            "sbtd_trellis_uninstall.execute_trellis_uninstall",
            side_effect=guarded_execute,
        ),
    ):
        yield


class VerifiedMigration:
    def __init__(self, base: Path, names: tuple[str, ...] = ("project",)) -> None:
        self.base = base
        self.roots = [legacy_project(base, name) for name in names]
        self.root = self.roots[0]
        self.home = base / "home"
        self.vault = base / "vault"
        self.evidence = base / "evidence"
        for path in (self.home, self.vault, self.evidence):
            require_private_directory(path, create=True)
        self.environment = {
            "HOME": str(self.home),
            "USERPROFILE": str(self.home),
            "CODEX_HOME": str(self.home / ".codex"),
            "AGENT_SKILLS_DIR": str(self.home / ".agent/skills"),
        }
        self.manifest: dict[str, Any] = {}
        self.manifest_path = self.evidence / "manifest.json"
        self.apply_path = self.evidence / "apply.json"
        self.deployment_path = self.evidence / "deployment.json"
        self.verification_path = self.evidence / "verification.json"
        self.verification: dict[str, Any] = {}

    def build(self) -> None:
        with mock.patch.dict(os.environ, self.environment):
            self.manifest = plan_migration(
                list(self.roots),
                self.vault,
                "fixture-custodian",
                None,
                tool_versions=runtime_versions(),
            )
            self.manifest_path.write_bytes(canonical_json_bytes(self.manifest))
            applied, apply_code = apply_migration(
                self.manifest_path, confirmed=True, no_routing_approvals=True
            )
            if apply_code != 0:
                raise AssertionError(f"apply failed: {applied}")
            apply_receipt = applied["migration"]["apply_receipt"]
            self.apply_path = next(
                path
                for path in self.evidence.glob("*.json")
                if json.loads(path.read_text()).get("apply_id")
                == apply_receipt["apply_id"]
            )

            moment = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            report_refs = {}
            for index, root in enumerate(self.roots):
                report_path = self.evidence / f"smoke-{index}.json"
                summary = self.evidence / f"smoke-{index}.md"
                summary.write_text("合成 cleanup 夹具；不证明真实 host 部署。\n", encoding="utf-8")
                raw = {
                    "repositoryKey": "fixture/project",
                    "projectRoot": str(root),
                    "sourceRef": "non-git",
                    "sourceCommit": None,
                    "worktreeState": "unknown",
                    "sourceRevision": "unknown",
                    "evidenceSource": "developer-local",
                    "trigger": "manual",
                    "environmentAlignment": "verified",
                    "evidencePublication": "local-only",
                    "e2eMode": "smoke-only",
                    "mockStrategy": "none",
                    "startedAt": moment,
                    "finishedAt": moment,
                    "command": ["fixture"],
                    "stdout": "synthetic contract data",
                    "stderr": "",
                    "exitCode": 0,
                    "timedOut": False,
                }
                report_path.write_text(json.dumps(raw))
                report = {
                    "testType": "api",
                    "path": str(report_path),
                    "summaryMd": str(summary),
                    "sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
                    "status": "passed",
                    "mode": "smoke-only",
                }
                envelope = {
                    "schemaVersion": 1,
                    "runId": f"fixture-smoke-{index}",
                    "createdAt": moment,
                    "evidenceSource": "developer-local",
                    "trigger": "manual",
                    "repository": {
                        "repositoryKey": "fixture/project",
                        "sourceRef": "non-git",
                        "sourceCommit": None,
                        "worktreeState": "unknown",
                    },
                    "sourceRevision": "unknown",
                    "environmentAlignment": "verified",
                    "e2eMode": "smoke-only",
                    "mockStrategy": "none",
                    "featureSources": [],
                    "reports": [report],
                    "evidencePublication": "local-only",
                    "secretsRedacted": True,
                }
                evidence_path = self.evidence / f"smoke-{index}.evidence.json"
                evidence_path.write_text(json.dumps(envelope))
                report_refs[root] = [
                    _file_ref(evidence_path),
                    _file_ref(report_path),
                    _file_ref(summary),
                ]
            deployment = seal_document(
                "deployment_evidence",
                {
                    "manifest_id": self.manifest["manifest_id"],
                    "apply_id": apply_receipt["apply_id"],
                    "previous_deployment_id": None,
                    "status": "succeeded",
                    "projects": [
                        {
                            "root": str(root),
                            "source_ref": None,
                            "head": None,
                            "status": "succeeded",
                            "reason": "",
                            "nextStep": "",
                            "private_results": [],
                            "shared_operation_ids": [],
                            "report_refs": report_refs[root],
                        }
                        for root in self.roots
                    ],
                    "shared_results": [],
                    "started_at": moment,
                    "finished_at": moment,
                },
            )
            save_document(
                self.deployment_path,
                deployment,
                private_root=self.evidence,
            )
            verified, verify_code = verify_migration(
                self.manifest_path,
                self.apply_path,
                self.deployment_path,
            )
            if verify_code != 0:
                raise AssertionError(f"verify failed: {verified}")
            self.verification = verified["migration"]["verification"]
            save_document(
                self.verification_path,
                self.verification,
                private_root=self.evidence,
            )

    def cleanup(
        self,
        *,
        fake_vendor: bool = True,
        vendor_prepare=None,
        vendor_execute=None,
        **kwargs: Any,
    ) -> tuple[dict[str, Any], int]:
        from sbtd_migration import cleanup_migration

        vendor = (
            _fake_vendor_adapter(prepare=vendor_prepare, execute=vendor_execute)
            if fake_vendor
            else nullcontext()
        )
        with vendor:
            return cleanup_migration(
                self.manifest_path,
                self.apply_path,
                self.deployment_path,
                self.verification_path,
                **kwargs,
            )


class CleanupMigrationTests(unittest.TestCase):
    def build(self, base: Path) -> VerifiedMigration:
        fixture = VerifiedMigration(base)
        fixture.build()
        return fixture

    def test_cleanup_requires_the_current_verification_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            before = _tree_bytes(fixture.base)
            with self.assertRaises(ContractError) as raised:
                fixture.cleanup()
            self.assertEqual(raised.exception.exit_code, 2)
            self.assertEqual(_tree_bytes(fixture.base), before)
            self.assertTrue((fixture.root / ".trellis").is_dir())

    def test_cleanup_rejects_a_stale_verification_id_without_deleting(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            with self.assertRaises(ContractError):
                fixture.cleanup(confirm_cleanup="0" * 64)
            self.assertTrue((fixture.root / ".trellis").is_dir())
            self.assertEqual(list(fixture.evidence.glob("cleanup-*.json")), [])

    def test_cleanup_with_a_failed_verification_deletes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            retained = next(
                asset
                for project in fixture.verification["payload"]["projects"]
                for asset in project["retained_assets"]
                if asset["state"]["type"] == "file"
                and asset["path"].endswith("/.sbtd/developer")
            )
            drifted = Path(retained["path"])
            drifted.write_bytes(drifted.read_bytes() + b"drift\n")
            failed, failed_code = verify_migration(
                fixture.manifest_path, fixture.apply_path, fixture.deployment_path
            )
            self.assertEqual(failed_code, 3, failed)
            self.assertEqual(failed["status"], "failed")
            failed_verification = failed["migration"]["verification"]
            fixture.verification_path = fixture.evidence / "verification-failed.json"
            save_document(
                fixture.verification_path,
                failed_verification,
                private_root=fixture.evidence,
            )
            before = _tree_bytes(fixture.base)
            with self.assertRaises(ContractError) as raised:
                fixture.cleanup(
                    confirm_cleanup=failed_verification["verification_id"]
                )
            self.assertEqual(raised.exception.exit_code, 2)
            self.assertEqual(_tree_bytes(fixture.base), before)
            self.assertTrue((fixture.root / ".trellis").is_dir())
            self.assertEqual(list(fixture.evidence.glob("cleanup-*.json")), [])

    def test_cleanup_removes_the_verified_legacy_tree_and_saves_a_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            envelope, code = fixture.cleanup(
                confirm_cleanup=fixture.verification["verification_id"]
            )
            self.assertEqual(code, 0, envelope)
            self.assertEqual(envelope["status"], "cleaned")
            self.assertFalse((fixture.root / ".trellis").exists())
            receipt = envelope["migration"]["cleanup_receipt"]
            self.assertEqual(receipt["payload"]["status"], "cleaned")
            self.assertEqual(
                receipt["payload"]["verification_id"],
                fixture.verification["verification_id"],
            )
            self.assertIsNone(receipt["payload"]["previous_receipt_id"])
            project = receipt["payload"]["projects"][0]
            self.assertEqual(project["status"], "cleaned")
            self.assertEqual(len(project["private_results"]), 1)
            result = project["private_results"][0]
            self.assertEqual(result["phase"], "cleanup")
            self.assertEqual(result["after"], {"type": "absent", "checksum": None})
            backup = result["backup_ref"]
            self.assertIsNotNone(backup)
            self.assertTrue(Path(backup["path"]).exists())
            receipt_path = fixture.evidence / f"cleanup-{receipt['cleanup_id']}.json"
            self.assertTrue(receipt_path.is_file())

    def test_a_candidate_changed_after_verification_is_blocked_without_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            changed = fixture.root / ".trellis/workspace/dev01/new-user-file.txt"
            changed.write_text("user data after verification\n")
            before = _tree_bytes(fixture.base)
            with self.assertRaises(ContractError):
                fixture.cleanup(confirm_cleanup=fixture.verification["verification_id"])
            self.assertEqual(_tree_bytes(fixture.base), before)
            self.assertEqual(list(fixture.evidence.glob("cleanup-*.json")), [])

    def test_a_retained_asset_changed_after_verification_blocks_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            retained = fixture.root / ".sbtd/developer"
            retained.write_text(retained.read_text() + "extra\n")
            before = _tree_bytes(fixture.base)
            with self.assertRaises(ContractError):
                fixture.cleanup(confirm_cleanup=fixture.verification["verification_id"])
            self.assertEqual(_tree_bytes(fixture.base), before)
            self.assertTrue((fixture.root / ".trellis").is_dir())
            self.assertEqual(list(fixture.evidence.glob("cleanup-*.json")), [])

    def test_a_successful_cleanup_retry_is_already_complete_and_cumulative(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            first, first_code = fixture.cleanup(
                confirm_cleanup=fixture.verification["verification_id"]
            )
            self.assertEqual(first_code, 0, first)
            first_receipt = first["migration"]["cleanup_receipt"]
            first_path = (
                fixture.evidence / f"cleanup-{first_receipt['cleanup_id']}.json"
            )

            second, second_code = fixture.cleanup(
                previous_receipt_path=first_path,
                confirm_cleanup=fixture.verification["verification_id"],
            )
            self.assertEqual(second_code, 0, second)
            self.assertEqual(second["status"], "already-complete")
            second_receipt = second["migration"]["cleanup_receipt"]
            self.assertEqual(
                second_receipt["payload"]["previous_receipt_id"],
                first_receipt["cleanup_id"],
            )
            self.assertTrue(
                (
                    fixture.evidence / f"cleanup-{second_receipt['cleanup_id']}.json"
                ).is_file()
            )

    def test_a_failed_cleanup_can_resume_from_its_cumulative_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            refusal = ContractError(
                "state-conflict", "injected cleanup refusal", exit_code=2
            )

            def refuse_vendor(*_args):
                raise refusal

            first, first_code = fixture.cleanup(
                vendor_execute=refuse_vendor,
                confirm_cleanup=fixture.verification["verification_id"],
            )
            self.assertEqual(first_code, 5, first)
            first_receipt = first["migration"]["cleanup_receipt"]
            self.assertEqual(first_receipt["payload"]["status"], "failed")
            first_result = first_receipt["payload"]["projects"][0]["private_results"][0]
            self.assertEqual(first_result["status"], "failed")
            self.assertEqual(first_result["before"], first_result["after"])
            self.assertTrue((fixture.root / ".trellis").is_dir())
            first_path = (
                fixture.evidence / f"cleanup-{first_receipt['cleanup_id']}.json"
            )
            self.assertTrue(first_path.is_file())
            second, second_code = fixture.cleanup(
                previous_receipt_path=first_path,
                confirm_cleanup=fixture.verification["verification_id"],
            )
            self.assertEqual(second_code, 0, second)
            self.assertEqual(second["status"], "cleaned")
            self.assertFalse((fixture.root / ".trellis").exists())
            self.assertEqual(
                second["migration"]["cleanup_receipt"]["payload"][
                    "previous_receipt_id"
                ],
                first_receipt["cleanup_id"],
            )

    def test_a_failed_cleanup_project_does_not_fail_an_unaffected_project(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = VerifiedMigration(Path(directory).resolve(), names=("one", "two"))
            fixture.build()
            def refuse_second_project(root, prepared, backup_root):
                if Path(root) == fixture.roots[1]:
                    raise ContractError(
                        "state-conflict",
                        "injected second-project refusal",
                        exit_code=2,
                    )
                return _fake_execute_trellis_uninstall(root, prepared, backup_root)

            envelope, code = fixture.cleanup(
                vendor_execute=refuse_second_project,
                confirm_cleanup=fixture.verification["verification_id"],
            )
            self.assertEqual(code, 5, envelope)
            receipt = envelope["migration"]["cleanup_receipt"]
            projects = {
                project["root"]: project for project in receipt["payload"]["projects"]
            }
            self.assertEqual(
                projects[str(fixture.roots[1])]["reason"],
                "a declared cleanup resource failed",
            )
            self.assertEqual(receipt["payload"]["status"], "failed")
            statuses = {
                project["root"]: project["status"]
                for project in receipt["payload"]["projects"]
            }
            self.assertEqual(statuses[str(fixture.roots[0])], "cleaned")
            self.assertEqual(statuses[str(fixture.roots[1])], "failed")
            self.assertFalse((fixture.roots[0] / ".trellis").exists())
            self.assertTrue((fixture.roots[1] / ".trellis").is_dir())

    def test_shared_1_0_x_skill_cleanup_runs_once_for_the_full_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = VerifiedMigration(Path(directory).resolve(), names=("one", "two"))
            skill = fixture.home / ".agent/skills/trellis-workflow"
            (skill / "SKILL.md").parent.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\nname: trellis-workflow\n---\n# 1.0.x customized release\n"
            )
            (skill / "release.txt").write_text("not the v1.0.15 bytes\n")
            import sbtd_migration_plan

            self.assertNotEqual(
                snapshot(skill),
                sbtd_migration_plan._ownership_pins()["skills"]["trellis-workflow"],
            )
            fixture.build()
            envelope, code = fixture.cleanup(
                confirm_cleanup=fixture.verification["verification_id"]
            )
            self.assertEqual(code, 0, envelope)
            receipt = envelope["migration"]["cleanup_receipt"]["payload"]
            self.assertEqual(len(receipt["shared_results"]), 1)
            shared = receipt["shared_results"][0]
            self.assertEqual(
                shared["dependent_projects"], sorted(map(str, fixture.roots))
            )
            self.assertFalse(skill.exists())
            for project in receipt["projects"]:
                self.assertEqual(
                    project["shared_operation_ids"], shared["operation_ids"]
                )

    def test_shared_skill_failure_marks_every_dependent_and_keeps_the_skill(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            fixture = VerifiedMigration(Path(directory).resolve(), names=("one", "two"))
            skill = fixture.home / ".agent/skills/trellis-workflow"
            (skill / "SKILL.md").parent.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\nname: trellis-workflow\n---\n# 1.0.x\n"
            )
            from sbtd_migration_files import remove_reference as real_remove

            fixture.build()

            def refuse_skill(path, expected, *, scope):
                if Path(path) == skill:
                    raise ContractError("state-conflict", "injected shared refusal")
                return real_remove(path, expected, scope=scope)

            with mock.patch(
                "sbtd_migration.remove_reference", side_effect=refuse_skill
            ):
                envelope, code = fixture.cleanup(
                    confirm_cleanup=fixture.verification["verification_id"]
                )
            self.assertEqual(code, 5, envelope)
            self.assertTrue(skill.is_dir())
            receipt = envelope["migration"]["cleanup_receipt"]["payload"]
            self.assertEqual(len(receipt["shared_results"]), 1)
            self.assertEqual(
                {project["status"] for project in receipt["projects"]}, {"failed"}
            )

    def test_resource_preservation_failure_keeps_exit_three(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            def fail_vendor(*_args):
                raise ContractError(
                    "checksum-mismatch", "synthetic readback failure", exit_code=3
                )

            response, code = fixture.cleanup(
                vendor_execute=fail_vendor,
                confirm_cleanup=fixture.verification["verification_id"],
            )
            self.assertEqual(code, 3, response)
            self.assertEqual(response["status"], "failed")
            self.assertTrue((fixture.roots[0] / ".trellis").is_dir())

    def test_vendor_unavailable_preserves_tree_and_skips_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            executed = mock.Mock()

            def unavailable(root):
                prepared = _fake_prepare_trellis_uninstall(root)
                prepared["payload"].update(
                    status="unavailable",
                    reason="the Trellis CLI is not installed",
                )
                return prepared

            envelope, code = fixture.cleanup(
                vendor_prepare=unavailable,
                vendor_execute=executed,
                confirm_cleanup=fixture.verification["verification_id"],
            )
            self.assertEqual(code, 5, envelope)
            self.assertTrue((fixture.root / ".trellis").is_dir())
            result = envelope["migration"]["cleanup_receipt"]["payload"][
                "projects"
            ][0]["private_results"][0]
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error"], "vendor-unavailable")
            self.assertIsNotNone(result["backup_ref"])
            executed.assert_not_called()

    def test_vendor_nonzero_preserves_tree_and_reports_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())

            def nonzero(root, _prepared, _backup_root):
                target = Path(root) / ".trellis"
                before = snapshot(target)
                return {
                    "status": "failed",
                    "exit": 7,
                    "results": [
                        {
                            "path": str(target),
                            "before": before,
                            "after": before,
                            "status": "unchanged",
                            "backup_ref": None,
                        }
                    ],
                    "errors": [
                        "vendor-refused: the vendor uninstall exited 7"
                    ],
                }

            envelope, code = fixture.cleanup(
                vendor_execute=nonzero,
                confirm_cleanup=fixture.verification["verification_id"],
            )
            self.assertEqual(code, 5, envelope)
            self.assertTrue((fixture.root / ".trellis").is_dir())
            result = envelope["migration"]["cleanup_receipt"]["payload"][
                "projects"
            ][0]["private_results"][0]
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error"], "vendor-uninstall-failed")
            self.assertEqual(result["before"], result["after"])
            self.assertIsNotNone(result["backup_ref"])

    def test_vendor_failure_links_private_outcome_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            evidence_refs = []

            def nonzero(root, _prepared, backup_root):
                target = Path(root) / ".trellis"
                before = snapshot(target)
                evidence_path = backup_root / "outcome.json"
                evidence_path.write_text('{"exit":7,"status":"failed"}')
                evidence = {"path": str(evidence_path), "state": snapshot(evidence_path)}
                resources = backup_root / "resources"
                resources.mkdir()
                preserved = resources / "000"
                shutil.copytree(target, preserved)
                backup = {"path": str(preserved), "state": snapshot(preserved)}
                evidence_refs.extend([evidence, backup])
                return {
                    "status": "failed",
                    "exit": 7,
                    "errors": ["vendor refused"],
                    "evidence_ref": evidence,
                    "results": [{
                        "path": str(target), "before": before, "after": before,
                        "status": "unchanged", "backup_ref": backup,
                    }],
                }

            envelope, code = fixture.cleanup(
                vendor_execute=nonzero,
                confirm_cleanup=fixture.verification["verification_id"],
            )
            self.assertEqual(code, 5, envelope)
            self.assertTrue((fixture.root / ".trellis").is_dir())
            result = envelope["migration"]["cleanup_receipt"]["payload"]["projects"][0]["private_results"][0]
            self.assertTrue(result["error"].startswith("vendor-uninstall-failed; retained="))
            retained = json.loads(result["error"].split("; retained=", 1)[1])
            self.assertEqual(retained, evidence_refs)
            self.assertEqual(len(retained), 2)
            self.assertTrue(retained[0]["path"].endswith("outcome.json"))
            self.assertTrue(retained[1]["path"].endswith("resources/000"))
            self.assertNotIn("evidence_ref", result)
            self.assertEqual(result["before"], result["after"])

    def test_vendor_external_partial_retains_outcome_and_original_references(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            agents = fixture.root / "AGENTS.md"
            original = agents.read_bytes()
            evidence_refs = []

            def partial(root, _prepared, backup_root):
                before = snapshot(agents)
                preserved = backup_root / "agents-original"
                preserved.write_bytes(original)
                backup = {"path": str(preserved), "state": snapshot(preserved)}
                agents.write_bytes(b"unexpected vendor mutation\n")
                evidence_path = backup_root / "vendor-outcome.json"
                evidence_path.write_text('{"exit":7,"status":"partial"}')
                evidence = {"path": str(evidence_path), "state": snapshot(evidence_path)}
                evidence_refs.extend([evidence, backup])
                tree = Path(root) / ".trellis"
                return {
                    "status": "partial", "exit": 7, "errors": ["vendor failed"],
                    "evidence_ref": evidence,
                    "results": [
                        {"path": str(tree), "before": snapshot(tree), "after": snapshot(tree), "backup_ref": None},
                        {"path": str(agents), "before": before, "after": snapshot(agents), "backup_ref": backup},
                    ],
                }

            envelope, code = fixture.cleanup(
                vendor_execute=partial,
                confirm_cleanup=fixture.verification["verification_id"],
            )
            self.assertEqual(code, 5, envelope)
            result = envelope["migration"]["cleanup_receipt"]["payload"]["projects"][0]["private_results"][0]
            self.assertEqual(result["status"], "failed")
            self.assertTrue(result["error"].startswith("post-state-conflict; retained="))
            self.assertEqual(json.loads(result["error"].split("; retained=", 1)[1]), evidence_refs)
            self.assertEqual(Path(evidence_refs[1]["path"]).read_bytes(), original)

    def test_unbound_vendor_footprint_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            foreign = fixture.root / "unrelated.txt"
            foreign.write_text("keep this user file\n")
            executed = mock.Mock()

            def broaden(root):
                prepared = _fake_prepare_trellis_uninstall(root)
                prepared["payload"]["resources"].append(
                    {
                        "kind": "vendor-delete",
                        "path": str(foreign),
                        "before": snapshot(foreign),
                        "expected_after": {"type": "absent", "checksum": None},
                    }
                )
                return prepared

            envelope, code = fixture.cleanup(
                vendor_prepare=broaden,
                vendor_execute=executed,
                confirm_cleanup=fixture.verification["verification_id"],
            )
            self.assertEqual(code, 5, envelope)
            self.assertEqual(foreign.read_text(), "keep this user file\n")
            self.assertTrue((fixture.root / ".trellis").is_dir())
            result = envelope["migration"]["cleanup_receipt"]["payload"][
                "projects"
            ][0]["private_results"][0]
            self.assertEqual(result["error"], "scope-conflict")
            executed.assert_not_called()

    def test_vendor_prune_with_foreign_empty_child_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            user_dir = fixture.root / ".codex/user-dir"
            user_dir.mkdir(parents=True)
            executed = mock.Mock()

            def broaden(root):
                prepared = _fake_prepare_trellis_uninstall(root)
                for relative in (".codex/agents", ".codex"):
                    path = Path(root) / relative
                    prepared["payload"]["resources"].append(
                        {
                            "kind": "vendor-prune-dir",
                            "path": str(path),
                            "before": snapshot(path),
                            "expected_after": {"type": "absent", "checksum": None},
                        }
                    )
                return prepared

            envelope, code = fixture.cleanup(
                vendor_prepare=broaden,
                vendor_execute=executed,
                confirm_cleanup=fixture.verification["verification_id"],
            )
            self.assertEqual(code, 5, envelope)
            self.assertTrue(user_dir.is_dir())
            self.assertTrue((fixture.root / ".trellis").is_dir())
            result = envelope["migration"]["cleanup_receipt"]["payload"][
                "projects"
            ][0]["private_results"][0]
            self.assertEqual(result["error"], "scope-conflict")
            executed.assert_not_called()

    def test_retry_reproves_removed_skill_identity_from_preserved_original(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = VerifiedMigration(Path(directory).resolve())
            skill = fixture.home / ".agent/skills/trellis-channel"
            (skill / "SKILL.md").parent.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\nname: trellis-channel\n---\n# different 1.0.x bytes\n"
            )
            fixture.build()
            first, code = fixture.cleanup(
                confirm_cleanup=fixture.verification["verification_id"]
            )
            self.assertEqual(code, 0, first)
            self.assertFalse(skill.exists())
            receipt = first["migration"]["cleanup_receipt"]
            receipt_path = fixture.evidence / f"cleanup-{receipt['cleanup_id']}.json"
            second, code = fixture.cleanup(
                previous_receipt_path=receipt_path,
                confirm_cleanup=fixture.verification["verification_id"],
            )
            self.assertEqual(code, 0, second)
            self.assertEqual(second["status"], "already-complete")


    def test_a_receipt_save_failure_is_failed_and_does_not_claim_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            with mock.patch(
                "sbtd_migration.save_document",
                side_effect=ContractError(
                    "write-failed", "cannot save receipt", exit_code=5
                ),
            ):
                envelope, code = fixture.cleanup(
                    confirm_cleanup=fixture.verification["verification_id"]
                )
            self.assertEqual(code, 5, envelope)
            self.assertEqual(envelope["status"], "failed")
            self.assertEqual(
                envelope["reason"], "cumulative evidence persistence failed"
            )
            self.assertEqual(list(fixture.evidence.glob("cleanup-*.json")), [])

    def test_cleanup_cli_emits_one_blocked_json_envelope_without_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            args = SimpleNamespace(
                phase="cleanup",
                manifest=str(fixture.manifest_path),
                apply_receipt=str(fixture.apply_path),
                deployment_evidence=str(fixture.deployment_path),
                verification=str(fixture.verification_path),
                cleanup_receipt=None,
                confirm_cleanup=None,
                json=True,
            )
            output = io.StringIO()
            with redirect_stdout(output):
                code = run_migration(args)
            self.assertEqual(code, 2)
            response = json.loads(output.getvalue())
            self.assertEqual(response["phase"], "cleanup")
            self.assertEqual(response["status"], "blocked")
            self.assertEqual(response["migration"], {})
            self.assertTrue((fixture.root / ".trellis").is_dir())

    def test_run_migration_dispatches_the_cleanup_phase(self):
        """Legacy CLI cleanup remains usable without any upgrade-hop options."""
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            args = parse_workflow_args([
                "migration", "--phase", "cleanup",
                "--manifest", str(fixture.manifest_path),
                "--apply-receipt", str(fixture.apply_path),
                "--deployment-evidence", str(fixture.deployment_path),
                "--verification", str(fixture.verification_path),
                "--confirm-cleanup", fixture.verification["verification_id"],
                "--json",
            ])
            output = io.StringIO()
            with (
                mock.patch.dict(os.environ, fixture.environment),
                _fake_vendor_adapter(),
                redirect_stdout(output),
            ):
                code = run_migration(args)
            response = json.loads(output.getvalue())
            self.assertEqual(code, 0, response)
            self.assertEqual(response["status"], "cleaned")
            self.assertFalse((fixture.root / ".trellis").exists())
            receipt = response["migration"]["cleanup_receipt"]
            self.assertNotIn("upgrade_context", receipt["payload"])



if __name__ == "__main__":
    unittest.main()
