from __future__ import annotations

import copy
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import nullcontext, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard" / "scripts"
TESTS = Path(__file__).resolve().parent
for import_path in (str(SCRIPTS), str(TESTS)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from onboard_contracts import ContractError, seal_document
from sbtd_migration_files import save_document
from sbtd_recovery import apply_recovery, plan_recovery, run_recovery
from test_sbtd_migration_cleanup import VerifiedMigration
from test_sbtd_migration_verify import _tree_bytes


class RestoredMigration:
    def __init__(self, base: Path) -> None:
        self.base = base
        self.fixture = VerifiedMigration(base)
        self.fixture.build()
        self.cleaned, self.cleanup_code = self.fixture.cleanup(
            confirm_cleanup=self.fixture.verification["verification_id"]
        )
        if self.cleanup_code != 0:
            raise AssertionError(f"cleanup failed: {self.cleaned}")
        self.cleanup_receipt = self.cleaned["migration"]["cleanup_receipt"]
        self.cleanup_path = self.fixture.evidence / (
            f"cleanup-{self.cleanup_receipt['cleanup_id']}.json"
        )
        self.plan_path = self.fixture.evidence / "recovery-plan.json"

    @property
    def root(self) -> Path:
        return self.fixture.root

    @property
    def evidence(self) -> Path:
        return self.fixture.evidence

    def plan(self, *, include_cleanup: bool = True):
        envelope, code = plan_recovery(
            self.fixture.manifest_path,
            apply_receipt_path=self.fixture.apply_path,
            deployment_evidence_path=self.fixture.deployment_path,
            cleanup_receipt_path=self.cleanup_path if include_cleanup else None,
        )
        if code not in (0, 2):
            raise AssertionError(f"recovery plan failed: {envelope}")
        return envelope["recovery"]["plan"]

    def save_plan(self, plan: dict[str, Any]) -> Path:
        save_document(self.plan_path, plan, private_root=self.evidence)
        return self.plan_path


class RecoveryPlanTests(unittest.TestCase):
    def build(self, base: Path) -> RestoredMigration:
        return RestoredMigration(base)

    def test_recovery_plan_restores_the_cleaned_legacy_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            plan = fixture.plan()
            self.assertEqual(plan["payload"]["status"], "planned")
            self.assertEqual(plan["payload"]["target"], "pre-apply")
            targets = {
                resource["resource_id"]: resource["target"]
                for resource in plan["payload"]["resources"]
            }
            cleanup_steps = [
                step
                for step in plan["payload"]["steps"]
                if step["phase"] == "cleanup"
                and targets[step["resource_id"]].endswith("/.trellis")
            ]
            self.assertEqual(len(cleanup_steps), 1)
            step = cleanup_steps[0]
            self.assertEqual(step["expected_current"]["type"], "absent")
            self.assertEqual(step["restore_to"]["type"], "directory")
            self.assertIsNotNone(step["backup_ref"])

            apply_steps = [
                step for step in plan["payload"]["steps"] if step["phase"] == "apply"
            ]
            self.assertTrue(apply_steps)
            self.assertEqual(
                Path(targets[apply_steps[0]["resource_id"]]).name,
                ".gitignore",
            )

    def test_recovery_plan_is_blocked_when_current_state_drifts(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            retained = fixture.root / ".gitignore"
            retained.write_text(retained.read_text() + "\nuser edit after cleanup\n")
            plan = fixture.plan()
            self.assertEqual(plan["payload"]["status"], "blocked")
            self.assertTrue(plan["payload"]["conflicts"])
            self.assertEqual(plan["payload"]["steps"], [])

    def test_recovery_plan_is_blocked_by_an_unknown_stage_write(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            payload = copy.deepcopy(fixture.cleanup_receipt["payload"])
            payload["status"] = "failed"
            payload["projects"][0]["status"] = "failed"
            payload["projects"][0]["private_results"][0]["status"] = "failed"
            payload["projects"][0]["reason"] = "unknown write"
            payload["projects"][0]["nextStep"] = "Inspect the retained evidence."
            payload["projects"][0]["private_results"][0]["after"] = None
            payload["projects"][0]["private_results"][0]["error"] = "unknown write"
            unknown = contracts_path = fixture.evidence / "cleanup-unknown.json"
            save_document(
                contracts_path,
                seal_document("cleanup_receipt", payload),
                private_root=fixture.evidence,
            )
            envelope, code = plan_recovery(
                fixture.fixture.manifest_path,
                apply_receipt_path=fixture.fixture.apply_path,
                deployment_evidence_path=fixture.fixture.deployment_path,
                cleanup_receipt_path=unknown,
            )
            self.assertEqual(code, 2, envelope)
            plan = envelope["recovery"]["plan"]
            self.assertEqual(plan["payload"]["status"], "blocked")
            self.assertTrue(plan["payload"]["conflicts"])

    def test_recovery_plan_rejects_projects_outside_the_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            with self.assertRaises(ContractError) as raised:
                plan_recovery(
                    fixture.fixture.manifest_path,
                    apply_receipt_path=fixture.fixture.apply_path,
                    deployment_evidence_path=fixture.fixture.deployment_path,
                    cleanup_receipt_path=fixture.cleanup_path,
                    projects_root=str(fixture.base / "outside"),
                )
            self.assertEqual(raised.exception.exit_code, 2)

    def test_recovery_plan_is_blocked_when_cleanup_evidence_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            plan = fixture.plan(include_cleanup=False)
            self.assertEqual(plan["payload"]["status"], "blocked")
            self.assertTrue(plan["payload"]["conflicts"])
            self.assertEqual(plan["payload"]["steps"], [])


    def test_shared_skill_recovery_requires_full_dependent_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            fixture = VerifiedMigration(base, names=("one", "two"))
            skill = fixture.home / ".agent/skills/trellis-workflow"
            (skill / "SKILL.md").parent.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\nname: trellis-workflow\n---\n# another 1.0.x release\n"
            )
            fixture.build()
            cleaned, code = fixture.cleanup(
                confirm_cleanup=fixture.verification["verification_id"]
            )
            self.assertEqual(code, 0, cleaned)
            cleanup = fixture.evidence / (
                f"cleanup-{cleaned['migration']['cleanup_receipt']['cleanup_id']}.json"
            )
            before = _tree_bytes(base)
            blocked, blocked_code = plan_recovery(
                fixture.manifest_path,
                apply_receipt_path=fixture.apply_path,
                deployment_evidence_path=fixture.deployment_path,
                cleanup_receipt_path=cleanup,
                projects_root=str(fixture.roots[0]),
            )
            self.assertEqual(blocked_code, 2, blocked)
            self.assertEqual(blocked["recovery"]["plan"]["payload"]["steps"], [])
            self.assertEqual(_tree_bytes(base), before)
            planned, planned_code = plan_recovery(
                fixture.manifest_path,
                apply_receipt_path=fixture.apply_path,
                deployment_evidence_path=fixture.deployment_path,
                cleanup_receipt_path=cleanup,
            )
            resources = planned["recovery"]["plan"]["payload"]["resources"]
            shared = next(resource for resource in resources if resource["target"] == str(skill))
            self.assertEqual(shared["dependent_projects"], sorted(map(str, fixture.roots)))
            self.assertEqual(
                len(
                    [
                        step
                        for step in planned["recovery"]["plan"]["payload"]["steps"]
                        if step["resource_id"] == shared["resource_id"]
                    ]
                ),
                1,
            )

class RecoveryApplyTests(unittest.TestCase):
    def build(self, base: Path) -> RestoredMigration:
        fixture = RestoredMigration(base)
        fixture.save_plan(fixture.plan())
        return fixture

    def test_recovery_requires_the_current_plan_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            before = _tree_bytes(fixture.base)
            with self.assertRaises(ContractError) as raised:
                apply_recovery(fixture.plan_path)
            self.assertEqual(raised.exception.exit_code, 2)
            self.assertEqual(_tree_bytes(fixture.base), before)
            self.assertFalse((fixture.root / ".trellis").exists())

    def test_recovery_restores_the_cleaned_tree_and_saves_a_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            plan = json.loads(fixture.plan_path.read_text())
            envelope, code = apply_recovery(
                fixture.plan_path,
                confirm_recovery=plan["plan_id"],
            )
            self.assertEqual(code, 0, envelope)
            self.assertEqual(envelope["status"], "restored")
            self.assertTrue((fixture.root / ".trellis/.developer").is_file())
            receipt = envelope["recovery"]["receipt"]
            self.assertEqual(receipt["payload"]["status"], "restored")
            self.assertEqual(
                receipt["payload"]["completed_step_ids"],
                sorted(step["step_id"] for step in plan["payload"]["steps"]),
            )
            self.assertEqual(receipt["payload"]["pending_step_ids"], [])
            self.assertEqual(receipt["payload"]["runtime_readiness"], "not-verified")
            receipt_path = fixture.evidence / f"recovery-{receipt['receipt_id']}.json"
            self.assertTrue(receipt_path.is_file())
            protection = receipt["payload"]["results"][0]["protection_ref"]
            self.assertIsNone(protection)

    def test_recovery_refuses_current_drift_without_restoring(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            plan = json.loads(fixture.plan_path.read_text())
            foreign = fixture.root / ".trellis" / "foreign.txt"
            foreign.parent.mkdir()
            foreign.write_text("user-created after cleanup\n")
            before = _tree_bytes(fixture.base)
            with self.assertRaises(ContractError) as raised:
                apply_recovery(
                    fixture.plan_path,
                    confirm_recovery=plan["plan_id"],
                )
            self.assertEqual(raised.exception.exit_code, 2)
            self.assertEqual(_tree_bytes(fixture.base), before)
            self.assertEqual(
                [
                    path
                    for path in fixture.evidence.glob("recovery-*.json")
                    if path.name != "recovery-plan.json"
                ],
                [],
            )

    def test_recovery_retry_resumes_a_failed_step_and_then_already_completes(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            plan = json.loads(fixture.plan_path.read_text())
            refusal = ContractError(
                "state-conflict", "injected restore refusal", exit_code=2
            )
            with mock.patch("sbtd_recovery.install_reference", side_effect=refusal):
                first, first_code = apply_recovery(
                    fixture.plan_path,
                    confirm_recovery=plan["plan_id"],
                )
            self.assertEqual(first_code, 5, first)
            first_receipt = first["recovery"]["receipt"]
            first_path = (
                fixture.evidence / f"recovery-{first_receipt['receipt_id']}.json"
            )
            self.assertTrue(first_path.is_file())
            self.assertFalse((fixture.root / ".trellis").exists())

            second, second_code = apply_recovery(
                fixture.plan_path,
                previous_receipt_path=first_path,
                confirm_recovery=plan["plan_id"],
            )
            self.assertEqual(second_code, 0, second)
            self.assertEqual(second["status"], "restored")
            self.assertTrue((fixture.root / ".trellis").is_dir())
            self.assertEqual(
                second["recovery"]["receipt"]["payload"]["previous_receipt_id"],
                first_receipt["receipt_id"],
            )

            third, third_code = apply_recovery(
                fixture.plan_path,
                previous_receipt_path=(
                    fixture.evidence
                    / f"recovery-{second['recovery']['receipt']['receipt_id']}.json"
                ),
                confirm_recovery=plan["plan_id"],
            )
            self.assertEqual(third_code, 0, third)
            self.assertEqual(third["status"], "already-complete")

    def test_recovery_retry_requires_the_prior_protection_object(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            plan = json.loads(fixture.plan_path.read_text())
            import sbtd_recovery
            from sbtd_migration_files import install_reference as real_install

            def refuse_gitignore_restore(
                source, target, expected, *, scope, backup_ref=None
            ):
                if Path(target).name == ".gitignore":
                    raise ContractError(
                        "write-failed", "injected restore failure", exit_code=5
                    )
                return real_install(
                    source, target, expected, scope=scope, backup_ref=backup_ref
                )

            with mock.patch.object(
                sbtd_recovery, "install_reference", side_effect=refuse_gitignore_restore
            ):
                first, first_code = apply_recovery(
                    fixture.plan_path,
                    confirm_recovery=plan["plan_id"],
                )
            self.assertEqual(first_code, 5, first)
            first_receipt = first["recovery"]["receipt"]
            protection = next(
                result["protection_ref"]
                for result in first_receipt["payload"]["results"]
                if result["protection_ref"] is not None
            )
            Path(protection["path"]).unlink()
            first_path = (
                fixture.evidence / f"recovery-{first_receipt['receipt_id']}.json"
            )
            with self.assertRaises(ContractError) as raised:
                apply_recovery(
                    fixture.plan_path,
                    previous_receipt_path=first_path,
                    confirm_recovery=plan["plan_id"],
                )
            self.assertEqual(raised.exception.exit_code, 3)

    def test_recovery_receipt_save_failure_is_failed_and_honest(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            plan = json.loads(fixture.plan_path.read_text())
            with mock.patch(
                "sbtd_recovery.save_document",
                side_effect=ContractError(
                    "write-failed", "cannot save recovery receipt", exit_code=5
                ),
            ):
                envelope, code = apply_recovery(
                    fixture.plan_path,
                    confirm_recovery=plan["plan_id"],
                )
            self.assertEqual(code, 5, envelope)
            self.assertEqual(envelope["status"], "failed")
            self.assertEqual(
                envelope["reason"], "cumulative evidence persistence failed"
            )
            self.assertEqual(
                [
                    path
                    for path in fixture.evidence.glob("recovery-*.json")
                    if path.name != "recovery-plan.json"
                ],
                [],
            )

    def test_recovery_requires_the_plan_beside_the_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            plan = json.loads(fixture.plan_path.read_text())
            other = fixture.base / "other"
            other.mkdir(mode=0o700)
            other_plan = other / "recovery-plan.json"
            save_document(other_plan, plan, private_root=other)
            before = _tree_bytes(fixture.base)
            with self.assertRaises(ContractError) as raised:
                apply_recovery(other_plan, confirm_recovery=plan["plan_id"])
            self.assertEqual(raised.exception.exit_code, 2)
            self.assertEqual(_tree_bytes(fixture.base), before)


    def test_same_resource_keeps_only_the_latest_succeeded_inverse_step(self):
        from sbtd_recovery import _latest_succeeded_step_ids

        steps = [
            {"step_id": "cleanup-step", "resource_id": "same"},
            {"step_id": "deploy-step", "resource_id": "same"},
            {"step_id": "apply-step", "resource_id": "same"},
            {"step_id": "other-step", "resource_id": "other"},
        ]
        previous = {
            "cleanup-step": {"status": "succeeded", "after": {"type": "file"}},
            "deploy-step": {"status": "succeeded", "after": {"type": "absent"}},
            "apply-step": {"status": "failed", "after": {"type": "absent"}},
            "other-step": {"status": "succeeded", "after": {"type": "file"}},
        }
        self.assertEqual(
            _latest_succeeded_step_ids(steps, previous),
            {"deploy-step", "other-step"},
        )

    def test_multi_phase_retry_checks_only_the_latest_restored_state(self):
        from onboard_contracts import (
            operation_id,
            recovery_step_id,
            resource_id,
            seal_document,
        )
        from sbtd_migration_files import snapshot

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            evidence = base / "evidence"
            evidence.mkdir(mode=0o700)
            project = base / "project"
            project.mkdir()
            target = base / "live.txt"
            target.write_bytes(b"pre-apply\n")
            applied_backup = evidence / "backup-applied.txt"
            applied_backup.write_bytes(b"post-apply\n")
            original_backup = evidence / "backup-original.txt"
            original_backup.write_bytes(b"pre-apply\n")
            manifest_path = evidence / "manifest.json"
            apply_path = evidence / "apply.json"
            cleanup_path = evidence / "cleanup.json"
            for path in (manifest_path, apply_path, cleanup_path):
                path.write_bytes(b"{}\n")
            rid = resource_id("file", str(target))
            manifest_id = "ab" * 32
            cleanup_step = recovery_step_id(manifest_id, "cleanup", rid)
            apply_step = recovery_step_id(manifest_id, "apply", rid)
            cleanup_op = operation_id("cleanup", rid, "whole-resource")
            apply_op = operation_id("apply", rid, "name")
            applied = snapshot(applied_backup)
            original = snapshot(target)
            evidence_ref = {
                "manifest": {
                    "path": str(manifest_path),
                    "state": snapshot(manifest_path),
                },
                "apply_receipt": {
                    "path": str(apply_path),
                    "state": snapshot(apply_path),
                },
                "deployment_evidence": None,
                "cleanup_receipt": {
                    "path": str(cleanup_path),
                    "state": snapshot(cleanup_path),
                },
            }
            plan = seal_document(
                "recovery_plan",
                {
                    "manifest_id": manifest_id,
                    "status": "planned",
                    "projects": [
                        {"root": str(project), "source_ref": None, "head": None}
                    ],
                    "shared_operation_ids": [],
                    "input_evidence": evidence_ref,
                    "resources": [
                        {
                            "resource_id": rid,
                            "owner_kind": "file",
                            "target": str(target),
                            "operation_ids": sorted([cleanup_op, apply_op]),
                            "dependent_projects": [str(project)],
                            "state": {"type": "absent", "checksum": None},
                        }
                    ],
                    "steps": [
                        {
                            "step_id": cleanup_step,
                            "phase": "cleanup",
                            "resource_id": rid,
                            "operation_ids": [cleanup_op],
                            "dependent_projects": [str(project)],
                            "depends_on": [],
                            "backup_ref": {
                                "path": str(applied_backup),
                                "state": applied,
                            },
                            "expected_current": {"type": "absent", "checksum": None},
                            "restore_to": applied,
                        },
                        {
                            "step_id": apply_step,
                            "phase": "apply",
                            "resource_id": rid,
                            "operation_ids": [apply_op],
                            "dependent_projects": [str(project)],
                            "depends_on": [cleanup_step],
                            "backup_ref": {
                                "path": str(original_backup),
                                "state": original,
                            },
                            "expected_current": applied,
                            "restore_to": original,
                        },
                    ],
                    "conflicts": [],
                    "risks": [],
                    "target": "pre-apply",
                    "created_at": "2026-09-27T07:00:00+00:00",
                },
            )
            receipt = seal_document(
                "recovery_receipt",
                {
                    "plan_id": plan["plan_id"],
                    "manifest_id": manifest_id,
                    "previous_receipt_id": None,
                    "input_evidence": evidence_ref,
                    "status": "restored",
                    "projects": [
                        {
                            "root": str(project),
                            "source_ref": None,
                            "head": None,
                            "status": "restored",
                            "reason": "",
                            "nextStep": "",
                        }
                    ],
                    "results": [
                        {
                            "step_id": cleanup_step,
                            "resource_id": rid,
                            "phase": "cleanup",
                            "operation_ids": [cleanup_op],
                            "dependent_projects": [str(project)],
                            "status": "succeeded",
                            "protection_ref": None,
                            "before": {"type": "absent", "checksum": None},
                            "after": applied,
                            "error": None,
                        },
                        {
                            "step_id": apply_step,
                            "resource_id": rid,
                            "phase": "apply",
                            "operation_ids": [apply_op],
                            "dependent_projects": [str(project)],
                            "status": "succeeded",
                            "protection_ref": {
                                "path": str(applied_backup),
                                "state": applied,
                            },
                            "before": applied,
                            "after": original,
                            "error": None,
                        },
                    ],
                    "shared_results": [],
                    "completed_step_ids": sorted([cleanup_step, apply_step]),
                    "pending_step_ids": [],
                    "reason": "",
                    "started_at": "2026-09-27T07:01:00+00:00",
                    "finished_at": "2026-09-27T07:02:00+00:00",
                    "runtime_readiness": "not-verified",
                    "report_refs": [],
                },
            )
            plan_path = evidence / "recovery-plan.json"
            receipt_path = evidence / f"recovery-{receipt['receipt_id']}.json"
            save_document(plan_path, plan, private_root=evidence)
            save_document(receipt_path, receipt, private_root=evidence)
            loaded_manifest = {
                "manifest_id": manifest_id,
                "payload": {
                    "backup_root": str(evidence),
                    "projects": [
                        {
                            "sources": [],
                            "private_operations": [
                                {"resource_id": rid, "target": str(target)}
                            ],
                        }
                    ],
                    "shared_operations": [],
                },
            }

            def load_reference(reference, kind):
                if kind == "manifest":
                    return loaded_manifest, b"{}\n"
                return {
                    "payload": {"projects": [], "shared_results": []}
                }, b"{}\n"

            before = target.read_bytes()
            with (
                mock.patch(
                    "sbtd_recovery._document_from_reference",
                    side_effect=load_reference,
                ),
                mock.patch("sbtd_recovery.contracts.validate_declared_bindings"),
                mock.patch("sbtd_recovery._validate_context"),
                mock.patch("sbtd_recovery.contracts.validate_cumulative"),
            ):
                continued, code = apply_recovery(
                    plan_path,
                    previous_receipt_path=receipt_path,
                    confirm_recovery=plan["plan_id"],
                )
            self.assertEqual(code, 0, continued)
            self.assertEqual(continued["status"], "already-complete")
            self.assertEqual(target.read_bytes(), before)
            self.assertNotEqual(snapshot(target), applied)

    def test_bound_multi_phase_continuation_uses_real_recovery_gates(self):
        self._assert_bound_multi_phase_continuation(predecessor=False)

    def test_predecessor_deployment_recovery_uses_latest_bound_stage(self):
        self._assert_bound_multi_phase_continuation(predecessor=True)

    def test_predecessor_failed_deployment_recovers_known_writes_not_retries(self):
        self._assert_bound_multi_phase_continuation(
            predecessor=True, failed_deploy=True
        )

    def _install_lineage_fixture(self, base, predecessor, successor):
        import base64

        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        key = Ed25519PrivateKey.generate()
        public = base / "lineage.pub"
        public.write_bytes(
            key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        )
        pair = {
            "schema_version": 1,
            "purpose": "runtime-lineage",
            "predecessor": predecessor,
            "successor": successor,
        }
        signed = json.dumps(pair, sort_keys=True, separators=(",", ":")).encode()
        pair["signature"] = base64.b64encode(key.sign(signed)).decode()
        document = base / "lineage.json"
        document.write_text(json.dumps(pair))
        for name, path in (
            ("_LINEAGE_PUBLIC_KEY", public),
            ("_LINEAGE_DOCUMENT", document),
        ):
            patch = mock.patch(f"sbtd_migration.{name}", path)
            patch.start()
            self.addCleanup(patch.stop)

    def _assert_bound_multi_phase_continuation(
        self, *, predecessor: bool, failed_deploy: bool = False
    ):
        import os

        import test_sbtd_migration_plan as routing_tests
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )
        from sbtd_graft_deployment import (
            execute_migration_deployment,
            load_deployment_context,
            write_file,
        )
        from sbtd_migration import (
            apply_migration,
            runtime_versions,
        )
        from sbtd_migration_files import snapshot
        from sbtd_migration_plan import plan_migration
        from test_sbtd_migration_apply import legacy_project
        from test_sbtd_migration_plan import (
            _routing_approval,
            _sign_existing_approval,
        )

        successor_versions = runtime_versions()
        planned_versions = successor_versions
        if predecessor:
            planned_versions = {
                **planned_versions,
                "onboard": "runtime-sha256:" + "a" * 64,
            }
        key = Ed25519PrivateKey.generate()
        previous_key = routing_tests._TEST_APPROVAL_KEY
        routing_tests._TEST_APPROVAL_KEY = key
        self.addCleanup(
            setattr, routing_tests, "_TEST_APPROVAL_KEY", previous_key
        )
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            if predecessor:
                # Verify real signatures against this interpreter's identity;
                # no assumption that CI matches the live operational pairing.
                self._install_lineage_fixture(
                    base, planned_versions["onboard"], successor_versions["onboard"]
                )
            project = legacy_project(base, "project")
            home, vault, evidence = (
                base / name for name in ("home", "vault", "evidence")
            )
            for path in (home, vault, evidence):
                path.mkdir(mode=0o700)
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(home / ".codex"),
                "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
            }
            live = project / "AGENTS.md"
            pause = (
                Path(__file__).resolve().parents[1]
                / "sbtd-workflow-onboard/assets/migration-paused-agents.txt"
            ).read_bytes()
            candidate = vault / "routing-candidate.md"
            candidate.write_bytes(pause + b"\napproved replacement\n")
            approval = vault / "routing-approvals.json"
            with mock.patch(
                "sbtd_migration_plan._routing_approval_public_key",
                return_value=key.public_key(),
            ):
                _routing_approval(approval, "demo-project", live, candidate)
                _sign_existing_approval(approval, key)
                with mock.patch.dict(os.environ, environment):
                    manifest = plan_migration(
                        [project],
                        vault,
                        "fixture",
                        None,
                        tool_versions=planned_versions,
                        deployment_mode="init-projects",
                        routing_approvals=approval,
                    )
            approval_patch = mock.patch(
                "sbtd_migration_plan._routing_approval_public_key",
                return_value=key.public_key(),
            )
            approval_patch.start()
            self.addCleanup(approval_patch.stop)
            phases = {}
            for operation in manifest["payload"]["projects"][0]["private_operations"]:
                phases.setdefault(operation["resource_id"], set()).add(
                    operation["phase"]
                )
            shared = [
                resource_id
                for resource_id, seen in phases.items()
                if seen >= {"apply", "deploy"}
            ]
            self.assertEqual(len(shared), 1)
            manifest_path = evidence / "manifest.json"
            from onboard_contracts import canonical_json_bytes

            manifest_path.write_bytes(canonical_json_bytes(manifest))
            # Only the old producer's identity is simulated. Successor gates,
            # signatures, stage binding and recovery execute without bypasses.
            old_producer = (
                mock.patch(
                    "sbtd_migration.runtime_versions", return_value=planned_versions
                )
                if predecessor
                else nullcontext()
            )
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch(
                    "sbtd_migration_plan._routing_approval_public_key",
                    return_value=key.public_key(),
                ),
                old_producer,
            ):
                applied, apply_code = apply_migration(
                    manifest_path,
                    confirmed=True,
                    routing_approvals=approval,
                )
            self.assertEqual(apply_code, 0, applied)
            receipt = applied["migration"]["apply_receipt"]
            apply_path = evidence / f"apply-{receipt['apply_id']}.json"
            deployment_path = evidence / "deployment.json"
            context = load_deployment_context(
                manifest_path,
                apply_path,
                deployment_path,
                previous_path=None,
                mode="init-projects",
                roots=[project],
                hooks_authorized=False,
            )

            def write_graph(root, _runtime):
                (root / "graft").mkdir()
                (root / "graft/fixture").write_bytes(b"synthetic native output")

            runtime = {
                "node": "/fixture/node",
                "cli": "/fixture/cli.js",
                "python": "/fixture/python",
            }

            def fail_after_route_write(target, *args, **kwargs):
                write_file(target, *args, **kwargs)
                if target == live:
                    raise OSError("injected failure after the route was written")

            with (
                mock.patch(
                    "sbtd_graft_deployment.verified_runtime", return_value=runtime
                ),
                mock.patch(
                    "sbtd_graft_deployment.build_project_graph",
                    side_effect=write_graph,
                ),
                mock.patch(
                    "sbtd_graft_deployment.run_project_smoke", return_value=[]
                ),
                (
                    mock.patch(
                        "sbtd_graft_deployment.write_file",
                        side_effect=fail_after_route_write,
                    )
                    if failed_deploy
                    else nullcontext()
                ),
            ):
                deployed, deploy_code = execute_migration_deployment(context)
            self.assertIn(deploy_code, (5,) if failed_deploy else (0, 3), deployed)
            self.assertTrue(deployment_path.is_file())
            if predecessor:
                deployed_bytes = live.read_bytes()
                retry_arguments = {
                    "previous_path": deployment_path,
                    "mode": "init-projects",
                    "roots": [project],
                    "hooks_authorized": False,
                }
                if failed_deploy:
                    with self.assertRaises(ContractError) as partial_retry:
                        load_deployment_context(
                            manifest_path, apply_path,
                            evidence / "deployment-retry.json", **retry_arguments
                        )
                    self.assertEqual(partial_retry.exception.code, "state-conflict")
                    stage = json.loads(deployment_path.read_text())
                    route_result = next(
                        result
                        for result in stage["payload"]["projects"][0]["private_results"]
                        if result["resource_id"] == shared[0]
                    )
                    self.assertEqual(route_result["status"], "failed")
                    self.assertNotEqual(route_result["before"], route_result["after"])
                    backup_path = Path(route_result["backup_ref"]["path"])
                    backup_bytes = backup_path.read_bytes()
                    backup_path.write_bytes(b"damaged retained original\n")
                    with self.assertRaises(ContractError) as damaged:
                        plan_recovery(
                            manifest_path, apply_receipt_path=apply_path,
                            deployment_evidence_path=deployment_path,
                        )
                    self.assertEqual(damaged.exception.code, "original-unavailable")
                    self.assertEqual(live.read_bytes(), deployed_bytes)
                    backup_path.write_bytes(backup_bytes)
                    for defect in ("missing-backup", "unknown-after", "wrong-apply"):
                        with self.subTest(defect=defect):
                            invalid = copy.deepcopy(stage["payload"])
                            invalid_result = next(
                                result
                                for result in invalid["projects"][0]["private_results"]
                                if result["resource_id"] == shared[0]
                            )
                            if defect == "missing-backup":
                                invalid_result["backup_ref"] = None
                            elif defect == "unknown-after":
                                invalid_result["after"] = None
                            else:
                                invalid["apply_id"] = "0" * 64
                            invalid_path = evidence / f"{defect}.json"
                            save_document(
                                invalid_path,
                                seal_document("deployment_evidence", invalid),
                                private_root=evidence,
                            )
                            if defect == "missing-backup":
                                blocked, blocked_code = plan_recovery(
                                    manifest_path, apply_receipt_path=apply_path,
                                    deployment_evidence_path=invalid_path,
                                )
                                self.assertEqual(blocked_code, 2, blocked)
                                self.assertEqual(blocked["status"], "blocked")
                            else:
                                with self.assertRaises(ContractError):
                                    plan_recovery(
                                        manifest_path, apply_receipt_path=apply_path,
                                        deployment_evidence_path=invalid_path,
                                    )
                            self.assertEqual(live.read_bytes(), deployed_bytes)
                else:
                    retry_context = load_deployment_context(
                        manifest_path, apply_path,
                        evidence / "deployment-retry.json", **retry_arguments
                    )
                    self.assertEqual(
                        retry_context.expected_before[shared[0]], snapshot(live)
                    )
                self.assertEqual(live.read_bytes(), deployed_bytes)
                with self.assertRaises(ContractError) as missing_stage:
                    plan_recovery(manifest_path, apply_receipt_path=apply_path)
                self.assertEqual(missing_stage.exception.code, "lineage-conflict")
                live.write_bytes(b"operator changed this route\n")
                with self.assertRaises(ContractError) as drift:
                    plan_recovery(
                        manifest_path,
                        apply_receipt_path=apply_path,
                        deployment_evidence_path=deployment_path,
                    )
                self.assertEqual(drift.exception.code, "lineage-conflict")
                self.assertEqual(live.read_bytes(), b"operator changed this route\n")
                live.write_bytes(deployed_bytes)
            planned, plan_code = plan_recovery(
                manifest_path,
                apply_receipt_path=apply_path,
                deployment_evidence_path=deployment_path,
            )
            self.assertEqual(plan_code, 0, planned)
            plan = planned["recovery"]["plan"]
            paired = [
                step
                for step in plan["payload"]["steps"]
                if step["resource_id"] == shared[0]
            ]
            self.assertEqual([step["phase"] for step in paired], ["deploy", "apply"])
            self.assertNotEqual(paired[0]["restore_to"], paired[1]["restore_to"])
            plan_path = evidence / "recovery-plan.json"
            save_document(plan_path, plan, private_root=evidence)
            restored, recovery_code = apply_recovery(
                plan_path, confirm_recovery=plan["plan_id"]
            )
            self.assertEqual(recovery_code, 0, restored)
            first = restored["recovery"]["receipt"]
            first_path = evidence / f"recovery-{first['receipt_id']}.json"
            succeeded = [
                result["step_id"]
                for result in first["payload"]["results"]
                if result["resource_id"] == shared[0]
                and result["status"] == "succeeded"
            ]
            self.assertEqual(len(succeeded), 2)
            after_restore = live.read_bytes()
            continued, continued_code = apply_recovery(
                plan_path,
                previous_receipt_path=first_path,
                confirm_recovery=plan["plan_id"],
            )
            self.assertEqual(continued_code, 0, continued)
            self.assertEqual(continued["status"], "already-complete")
            self.assertEqual(live.read_bytes(), after_restore)


    def test_predecessor_recovery_can_continue_from_a_partial_receipt(self):
        from onboard_contracts import canonical_json_bytes
        from sbtd_migration import apply_migration, runtime_versions
        from sbtd_migration_files import snapshot
        from sbtd_migration_plan import plan_migration
        from test_sbtd_migration_apply import legacy_project

        predecessor = "runtime-sha256:" + "a" * 64
        current = runtime_versions()
        graft = current["graft"]
        sealed = {"onboard": predecessor, "graft": graft}
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            self._install_lineage_fixture(base, predecessor, current["onboard"])
            project = legacy_project(base, "project")
            home, vault, evidence = (base / name for name in ("home", "vault", "evidence"))
            for path in (home, vault, evidence):
                path.mkdir(mode=0o700)
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(home / ".codex"),
                "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
            }
            with mock.patch.dict(os.environ, environment):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture",
                    None,
                    tool_versions=sealed,
                )
            manifest_path = evidence / "manifest.json"
            manifest_path.write_bytes(canonical_json_bytes(manifest))
            with mock.patch.dict(os.environ, environment), mock.patch(
                "sbtd_migration.runtime_versions", return_value=sealed
            ):
                applied, apply_code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
            self.assertEqual(apply_code, 0, applied)
            receipt = applied["migration"]["apply_receipt"]
            apply_path = evidence / f"apply-{receipt['apply_id']}.json"
            self.assertTrue(apply_path.is_file())
            planned, plan_code = plan_recovery(
                manifest_path, apply_receipt_path=apply_path
            )
            self.assertEqual(plan_code, 0, planned)
            plan = planned["recovery"]["plan"]
            steps = plan["payload"]["steps"]
            self.assertGreaterEqual(len(steps), 2)
            plan_path = evidence / "recovery-plan.json"
            save_document(plan_path, plan, private_root=evidence)
            import sbtd_recovery

            real_execute = sbtd_recovery._execute_step

            def stop_after_first(manifest_doc, operation, path, step):
                if stop_after_first.calls:
                    current = snapshot(Path(operation["target"]))
                    return {
                        "step_id": step["step_id"],
                        "resource_id": step["resource_id"],
                        "phase": step["phase"],
                        "operation_ids": list(step["operation_ids"]),
                        "dependent_projects": list(step["dependent_projects"]),
                        "status": "failed",
                        "protection_ref": None,
                        "before": current,
                        "after": current,
                        "error": "state-conflict",
                    }
                stop_after_first.calls += 1
                return real_execute(manifest_doc, operation, path, step)

            stop_after_first.calls = 0
            with mock.patch.object(
                sbtd_recovery, "_execute_step", side_effect=stop_after_first
            ):
                first, first_code = apply_recovery(
                    plan_path, confirm_recovery=plan["plan_id"]
                )
            self.assertEqual(first_code, 5, first)
            first_receipt = first["recovery"]["receipt"]
            succeeded = [
                result
                for result in first_receipt["payload"]["results"]
                if result["status"] == "succeeded"
            ]
            self.assertEqual(len(succeeded), 1)
            operations = [
                operation
                for project in manifest["payload"]["projects"]
                for operation in project["private_operations"]
            ] + list(manifest["payload"]["shared_operations"])
            restored_target = Path(
                next(
                    operation["target"]
                    for operation in operations
                    if operation["resource_id"] == succeeded[0]["resource_id"]
                )
            )
            self.assertEqual(snapshot(restored_target), succeeded[0]["after"])
            self.assertNotEqual(snapshot(restored_target), succeeded[0]["before"])
            first_path = evidence / f"recovery-{first_receipt['receipt_id']}.json"
            before_continue = _tree_bytes(base)
            unlisted = {
                "onboard": "runtime-sha256:unlisted-successor",
                "graft": graft,
            }
            with (
                mock.patch("sbtd_migration.runtime_versions", return_value=unlisted),
                self.assertRaises(ContractError) as rejected,
            ):
                apply_recovery(
                    plan_path,
                    previous_receipt_path=first_path,
                    confirm_recovery=plan["plan_id"],
                )
            self.assertEqual(rejected.exception.code, "version-conflict")
            self.assertEqual(_tree_bytes(base), before_continue)
            official = (base / "lineage.json").read_bytes()
            outside = Path(tempfile.mkdtemp(dir=str(base.parent)))
            tampered = outside / "bad-lineage.json"
            payload = json.loads(official)
            payload["signature"] = "A" * len(payload["signature"])
            tampered.write_text(json.dumps(payload), encoding="utf-8")
            with (
                mock.patch("sbtd_migration._LINEAGE_DOCUMENT", tampered),
                self.assertRaises(ContractError) as bad_signature,
            ):
                apply_recovery(
                    plan_path,
                    previous_receipt_path=first_path,
                    confirm_recovery=plan["plan_id"],
                )
            self.assertEqual(bad_signature.exception.code, "version-conflict")
            self.assertEqual(_tree_bytes(base), before_continue)
            continued, continued_code = apply_recovery(
                plan_path,
                previous_receipt_path=first_path,
                confirm_recovery=plan["plan_id"],
            )
            self.assertEqual(continued_code, 0, continued)
            self.assertEqual(continued["status"], "restored")
            self.assertEqual(
                continued["recovery"]["receipt"]["payload"]["pending_step_ids"],
                [],
            )
            self.assertEqual(snapshot(restored_target), succeeded[0]["after"])




class RecoveryCliTests(unittest.TestCase):
    def test_run_recovery_dispatches_the_apply_phase(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            envelope = {
                "mode": "recovery",
                "phase": "apply",
                "status": "blocked",
                "manifest_id": "0" * 64,
                "plan_id": "1" * 64,
                "receipt_id": None,
                "projects": [],
                "reason": "confirmation required",
                "nextStep": "Confirm the current plan_id.",
                "recovery": {},
            }
            args = SimpleNamespace(
                phase="apply",
                plan=str(base / "plan.json"),
                recovery_receipt=None,
                confirm_recovery="1" * 64,
                json=False,
            )
            with mock.patch(
                "sbtd_recovery.apply_recovery", return_value=(envelope, 2)
            ) as apply:
                code = run_recovery(args)
            self.assertEqual(code, 2)
            apply.assert_called_once_with(
                base / "plan.json",
                previous_receipt_path=None,
                confirm_recovery="1" * 64,
            )

    def test_run_recovery_validates_the_rejection_json_envelope(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            args = SimpleNamespace(
                phase="plan",
                manifest=str(base / "manifest.json"),
                apply_receipt=None,
                deployment_evidence=None,
                cleanup_receipt=None,
                projects_root=None,
                json=True,
            )
            output = io.StringIO()
            with (
                mock.patch(
                    "sbtd_recovery.plan_recovery",
                    side_effect=ContractError(
                        "original-unavailable", "bound evidence missing", exit_code=3
                    ),
                ),
                redirect_stdout(output),
            ):
                code = run_recovery(args)
            self.assertEqual(code, 3)
            response = json.loads(output.getvalue())
            self.assertEqual(response["phase"], "plan")
            self.assertEqual(response["status"], "failed")
            self.assertEqual(response["recovery"], {})
            self.assertEqual(list(base.iterdir()), [])

    def test_run_recovery_dispatches_the_plan_phase(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            envelope = {
                "mode": "recovery",
                "phase": "plan",
                "status": "blocked",
                "manifest_id": "0" * 64,
                "plan_id": None,
                "receipt_id": None,
                "projects": [],
                "reason": "closure missing",
                "nextStep": "Select the full shared dependency closure.",
                "recovery": {},
            }
            args = SimpleNamespace(
                phase="plan",
                manifest=str(base / "manifest.json"),
                apply_receipt=None,
                deployment_evidence=None,
                cleanup_receipt=None,
                projects_root=None,
                json=True,
            )
            output = io.StringIO()
            with (
                mock.patch(
                    "sbtd_recovery.plan_recovery", return_value=(envelope, 2)
                ) as plan,
                redirect_stdout(output),
            ):
                code = run_recovery(args)
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output.getvalue())["phase"], "plan")
            plan.assert_called_once_with(
                base / "manifest.json",
                apply_receipt_path=None,
                deployment_evidence_path=None,
                cleanup_receipt_path=None,
                projects_root=None,
            )


if __name__ == "__main__":
    unittest.main()
