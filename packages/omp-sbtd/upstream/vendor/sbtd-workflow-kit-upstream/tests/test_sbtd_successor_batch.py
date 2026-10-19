from __future__ import annotations

import base64
import contextlib
import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import onboard_arguments
import onboard_contracts as contracts
import sbtd_migration_plan
from onboard_contracts import ContractError, canonical_json_bytes
from sbtd_graft_deployment import load_deployment_context
from sbtd_migration import apply_migration
from sbtd_migration_files import read_file, snapshot
from sbtd_migration_plan import plan_migration, validate_legacy_inputs

from tests.test_sbtd_migration_apply import legacy_project

_TEST_APPROVAL_KEY = None
_TEST_KEY_PATCH = None
_TOOL_VERSIONS = {"onboard": "fixture", "graft": "0.18.0"}


def setUpModule():
    global _TEST_APPROVAL_KEY, _TEST_KEY_PATCH
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    _TEST_APPROVAL_KEY = Ed25519PrivateKey.generate()
    _TEST_KEY_PATCH = mock.patch(
        "sbtd_migration_plan._routing_approval_public_key",
        return_value=_TEST_APPROVAL_KEY.public_key(),
    )
    _TEST_KEY_PATCH.start()


def tearDownModule():
    if _TEST_KEY_PATCH is not None:
        _TEST_KEY_PATCH.stop()


def _sign_existing_approval(path):
    document = json.loads(path.read_bytes())
    payload = contracts.canonical_json_bytes(
        {"schema_version": document["schema_version"], "items": document["items"]}
    )
    document["signature"] = base64.b64encode(
        _TEST_APPROVAL_KEY.sign(payload)
    ).decode("ascii")
    path.write_bytes(json.dumps(document).encode("utf-8"))
    return path


def _reader(reference):
    return read_file(Path(reference["path"]), reference["state"])


def _apply_environment(home):
    return {
        "HOME": str(home),
        "USERPROFILE": str(home),
        "CODEX_HOME": str(home / ".codex"),
        "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
    }


def _completed_batch(base, pins=None):
    """Plan and apply one deployment-less batch with an approved replacement."""
    project = legacy_project(base, "project")
    home, vault, evidence = (base / name for name in ("home", "vault", "evidence"))
    for path in (home, vault, evidence):
        path.mkdir(mode=0o700, exist_ok=True)
    live = home / ".codex" / "AGENTS.md"
    live.parent.mkdir(parents=True)
    live.write_bytes(b"custom trellis routing\n")
    pause = (SCRIPTS.parents[0] / "assets" / "migration-paused-agents.txt").read_bytes()
    candidate = vault / "routing-candidate.md"
    candidate.write_bytes(pause + b"\napproved replacement\n")
    approval = vault / "routing-approvals.json"
    approval.write_bytes(
        json.dumps(
            {
                "schema_version": 1,
                "items": [
                    {
                        "role": "codex-global",
                        "target_path": str(live),
                        "before": snapshot(live),
                        "candidate_ref": {
                            "path": str(candidate),
                            "state": snapshot(candidate),
                        },
                        "basis": "fixture custodian approval",
                    }
                ],
            }
        ).encode("utf-8")
    )
    _sign_existing_approval(approval)
    environment = _apply_environment(home)
    pin_patch = (
        mock.patch.object(
            sbtd_migration_plan, "_ownership_pins", return_value=pins
        )
        if pins is not None
        else contextlib.nullcontext()
    )
    with mock.patch.dict(os.environ, environment), pin_patch:
        manifest = plan_migration(
            [project],
            vault,
            "fixture",
            None,
            tool_versions=dict(_TOOL_VERSIONS),
            routing_approvals=approval,
        )
        manifest_path = evidence / "manifest.json"
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        with mock.patch(
            "sbtd_migration.runtime_versions", return_value=dict(_TOOL_VERSIONS)
        ):
            applied, code = apply_migration(
                manifest_path, confirmed=True, routing_approvals=approval
            )
    if code != 0:
        raise AssertionError(f"fixture apply failed: {applied}")
    receipt = applied["migration"]["apply_receipt"]
    receipt_path = evidence / ("apply-" + receipt["apply_id"] + ".json")
    return {
        "project": project,
        "home": home,
        "vault": vault,
        "evidence": evidence,
        "live": live,
        "approval": approval,
        "environment": environment,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "receipt": receipt,
        "receipt_path": receipt_path,
    }


def _plan_successor_batch(batch):
    with mock.patch.dict(os.environ, batch["environment"]):
        return plan_migration(
            [batch["project"]],
            batch["vault"],
            "fixture",
            None,
            tool_versions=dict(_TOOL_VERSIONS),
            deployment_mode="init",
            successor_manifest=batch["manifest_path"],
            successor_apply_receipt=batch["receipt_path"],
        )


class SuccessorBatchTests(unittest.TestCase):
    def test_successor_plan_apply_and_deployment_context(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            batch = _completed_batch(base)
            post_apply_approval = batch["vault"] / "successor-approvals.json"
            candidate = batch["vault"] / "routing-candidate.md"
            post_apply_approval.write_bytes(
                json.dumps(
                    {
                        "schema_version": 1,
                        "items": [
                            {
                                "role": "codex-global",
                                "target_path": str(batch["live"]),
                                "before": snapshot(batch["live"]),
                                "candidate_ref": {
                                    "path": str(candidate),
                                    "state": snapshot(candidate),
                                },
                                "basis": "fixture successor custodian approval",
                            }
                        ],
                    }
                ).encode("utf-8")
            )
            _sign_existing_approval(post_apply_approval)
            with (
                mock.patch.dict(os.environ, batch["environment"]),
                self.assertRaises(ContractError) as replan,
            ):
                plan_migration(
                    [batch["project"]],
                    batch["vault"],
                    "fixture",
                    None,
                    tool_versions=dict(_TOOL_VERSIONS),
                    routing_approvals=post_apply_approval,
                )
            self.assertEqual(replan.exception.code, "ownership-conflict")
            untouched = snapshot(base)
            successor = _plan_successor_batch(batch)
            with mock.patch.dict(os.environ, batch["environment"]):
                validate_legacy_inputs(successor, _reader)
            self.assertEqual(snapshot(base), untouched)
            payload = successor["payload"]
            binding = payload["successor"]
            self.assertEqual(binding["manifest_id"], batch["manifest"]["manifest_id"])
            self.assertEqual(
                binding["apply_id"], batch["receipt"]["apply_id"]
            )
            self.assertTrue(binding["apply_results"])
            self.assertEqual(payload["deployment"]["mode"], "init")
            self.assertEqual(payload["publication_decisions"], {
                "schema_version": 1,
                "items": [],
            })
            self.assertIsNone(payload["routing_approvals"])
            project = payload["projects"][0]
            cleanups = [
                operation
                for operation in project["private_operations"]
                if operation["phase"] == "cleanup"
            ]
            self.assertEqual(len(cleanups), 1)
            resource = contracts.resource_id("markdown", str(batch["live"]))
            template = next(
                operation
                for operation in payload["shared_operations"]
                if operation["target"] == str(batch["live"])
            )
            self.assertEqual(
                template["before_requirement"],
                {"kind": "phase-after", "phase": "apply", "resource_id": resource},
            )

            manifest_path = batch["evidence"] / "successor-manifest.json"
            manifest_path.write_bytes(canonical_json_bytes(successor))
            with (
                mock.patch.dict(os.environ, batch["environment"]),
                mock.patch(
                    "sbtd_migration.runtime_versions",
                    return_value=dict(_TOOL_VERSIONS),
                ),
            ):
                applied, code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
                self.assertEqual(code, 0, applied)
                self.assertEqual(applied["status"], "applied")
                receipt = applied["migration"]["apply_receipt"]
                self.assertIsNone(receipt["payload"]["previous_receipt_id"])
                self.assertTrue(
                    (
                        batch["vault"] / successor["manifest_id"] / "originals"
                    ).is_dir()
                )
                context = load_deployment_context(
                    manifest_path,
                    batch["evidence"] / ("apply-" + receipt["apply_id"] + ".json"),
                    batch["evidence"] / "deployment.json",
                    previous_path=None,
                    mode="init",
                    roots=[batch["project"]],
                    hooks_authorized=False,
                )
            self.assertEqual(
                context.expected_before[resource], snapshot(batch["live"])
            )

    def test_successor_rejects_incomplete_predecessor_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            batch = _completed_batch(base)
            document = json.loads(batch["receipt_path"].read_bytes())
            payload = document["payload"]
            payload["status"] = "failed"
            for project in payload["projects"]:
                project["status"] = "failed"
                project["reason"] = "synthetic failure"
                project["nextStep"] = "synthetic next step"
            failed = contracts.seal_document("apply_receipt", payload)
            failed_path = batch["evidence"] / "failed-receipt.json"
            failed_path.write_bytes(canonical_json_bytes(failed))
            with (
                mock.patch.dict(os.environ, batch["environment"]),
                self.assertRaises(ContractError) as error,
            ):
                plan_migration(
                    [batch["project"]],
                    batch["vault"],
                    "fixture",
                    None,
                    tool_versions=dict(_TOOL_VERSIONS),
                    deployment_mode="init",
                    successor_manifest=batch["manifest_path"],
                    successor_apply_receipt=failed_path,
                )
            self.assertEqual(error.exception.code, "binding-violation")

    def test_successor_rejects_a_batch_that_already_declares_deployment(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = legacy_project(base, "project")
            home, vault, evidence = (base / name for name in ("home", "vault", "evidence"))
            for path in (home, vault, evidence):
                path.mkdir(mode=0o700)
            environment = _apply_environment(home)
            with mock.patch.dict(os.environ, environment):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture",
                    None,
                    tool_versions=dict(_TOOL_VERSIONS),
                    deployment_mode="init",
                )
                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(manifest))
                with mock.patch(
                    "sbtd_migration.runtime_versions",
                    return_value=dict(_TOOL_VERSIONS),
                ):
                    applied, code = apply_migration(
                        manifest_path, confirmed=True, no_routing_approvals=True
                    )
                self.assertEqual(code, 0, applied)
                receipt = applied["migration"]["apply_receipt"]
                with self.assertRaises(ContractError) as error:
                    plan_migration(
                        [project],
                        vault,
                        "fixture",
                        None,
                        tool_versions=dict(_TOOL_VERSIONS),
                        deployment_mode="init",
                        successor_manifest=manifest_path,
                        successor_apply_receipt=evidence
                        / ("apply-" + receipt["apply_id"] + ".json"),
                    )
            self.assertEqual(error.exception.code, "successor-conflict")

    def test_successor_rejects_drifted_completed_outcome(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            batch = _completed_batch(base)
            batch["live"].write_bytes(batch["live"].read_bytes() + b"tampered\n")
            with (
                mock.patch.dict(os.environ, batch["environment"]),
                self.assertRaises(ContractError) as error,
            ):
                _plan_successor_batch(batch)
            self.assertEqual(error.exception.code, "state-conflict")

    def test_tampered_successor_manifest_fails_closed_set_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            batch = _completed_batch(base)
            successor = _plan_successor_batch(batch)
            payload = successor["payload"]
            payload["projects"][0]["private_operations"] = [
                operation
                for operation in payload["projects"][0]["private_operations"]
                if operation["phase"] == "deploy"
            ]
            resealed = contracts.seal_document("manifest", payload)
            with self.assertRaises(ContractError) as error:
                validate_legacy_inputs(resealed, _reader)
            self.assertEqual(error.exception.code, "semantic-violation")

            document = json.loads(canonical_json_bytes(successor))
            document["payload"]["successor"]["apply_results"] = []
            with self.assertRaises(ContractError):
                contracts.validate_document(document, "manifest")


class SuccessorPredecessorVerificationTests(unittest.TestCase):
    def test_resealed_embedded_results_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            batch = _completed_batch(base)
            successor = _plan_successor_batch(batch)
            batch["live"].write_bytes(batch["live"].read_bytes() + b"tampered\n")
            payload = successor["payload"]
            resource = contracts.resource_id("markdown", str(batch["live"]))
            for result in payload["successor"]["apply_results"]:
                if result["resource_id"] == resource:
                    result["after"] = snapshot(batch["live"])
            resealed = contracts.seal_document("manifest", payload)
            with (
                mock.patch.dict(os.environ, batch["environment"]),
                self.assertRaises(ContractError) as error,
            ):
                validate_legacy_inputs(resealed, _reader)
            self.assertEqual(error.exception.code, "binding-violation")

    def test_dropped_shared_cleanup_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            skill = base / "home/.agent/skills/trellis-workflow"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("---\nname: trellis-workflow\n---\nlegacy skill\n")
            pins = sbtd_migration_plan._ownership_pins()
            pins["skills"] = {"trellis-workflow": snapshot(skill)}
            batch = _completed_batch(base, pins=pins)
            retired = [
                operation
                for operation in batch["manifest"]["payload"]["shared_operations"]
                if operation["phase"] == "cleanup"
            ]
            assert len(retired) == 1, batch["manifest"]["payload"]["shared_operations"]
            with mock.patch.object(
                sbtd_migration_plan, "_ownership_pins", return_value=pins
            ):
                successor = _plan_successor_batch(batch)
                payload = successor["payload"]
                self.assertEqual(
                    [
                        operation
                        for operation in payload["shared_operations"]
                        if operation["phase"] == "cleanup"
                    ],
                    retired,
                )
                payload["shared_operations"] = [
                    operation
                    for operation in payload["shared_operations"]
                    if operation["phase"] != "cleanup"
                ]
                for project in payload["projects"]:
                    project["shared_operation_ids"] = sorted(
                        operation["operation_id"]
                        for operation in payload["shared_operations"]
                        if project["root"] in operation["dependent_projects"]
                    )
                resealed = contracts.seal_document("manifest", payload)
                with (
                    mock.patch.dict(os.environ, batch["environment"]),
                    self.assertRaises(ContractError) as error,
                ):
                    validate_legacy_inputs(resealed, _reader)
                self.assertEqual(error.exception.code, "semantic-violation")

    def test_recreated_predecessor_outcome_drift_blocks_every_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            batch = _completed_batch(base)
            successor = _plan_successor_batch(batch)
            regenerated = batch["project"] / ".codex/agents/trellis-implement.toml"
            regenerated.write_bytes(b'name = "trellis-implement"\n')
            with (
                mock.patch.dict(os.environ, batch["environment"]),
                self.assertRaises(ContractError) as error,
            ):
                validate_legacy_inputs(successor, _reader)
            self.assertEqual(error.exception.code, "state-conflict")

    def test_successor_inherits_predecessor_retention(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            import sbtd_migration

            custom_retention = copy.deepcopy(sbtd_migration._RETENTION)
            custom_retention["normal_observation_days"] = 30
            with mock.patch.object(
                sbtd_migration, "_RETENTION", custom_retention
            ):
                batch = _completed_batch(base)
            successor = _plan_successor_batch(batch)
            self.assertEqual(
                successor["payload"]["retention"], custom_retention
            )

    def test_successor_rejects_unapplied_ignore_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = legacy_project(base, "project")
            (project / ".trellis/.developer").unlink()
            home, vault, evidence = (base / name for name in ("home", "vault", "evidence"))
            for path in (home, vault, evidence):
                path.mkdir(mode=0o700)
            environment = _apply_environment(home)
            with mock.patch.dict(os.environ, environment):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture",
                    None,
                    tool_versions=dict(_TOOL_VERSIONS),
                )
                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(manifest))
                with mock.patch(
                    "sbtd_migration.runtime_versions",
                    return_value=dict(_TOOL_VERSIONS),
                ):
                    applied, code = apply_migration(
                        manifest_path, confirmed=True, no_routing_approvals=True
                    )
                self.assertEqual(code, 0, applied)
                receipt = applied["migration"]["apply_receipt"]
                with self.assertRaises(ContractError) as error:
                    plan_migration(
                        [project],
                        vault,
                        "fixture",
                        None,
                        tool_versions=dict(_TOOL_VERSIONS),
                        deployment_mode="init",
                        successor_manifest=manifest_path,
                        successor_apply_receipt=evidence
                        / ("apply-" + receipt["apply_id"] + ".json"),
                    )
            self.assertEqual(error.exception.code, "successor-conflict")

    def test_successor_of_successor_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            batch = _completed_batch(base)
            successor = _plan_successor_batch(batch)
            manifest_path = batch["evidence"] / "successor-manifest.json"
            manifest_path.write_bytes(canonical_json_bytes(successor))
            with (
                mock.patch.dict(os.environ, batch["environment"]),
                mock.patch(
                    "sbtd_migration.runtime_versions",
                    return_value=dict(_TOOL_VERSIONS),
                ),
            ):
                applied, code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
                self.assertEqual(code, 0, applied)
                receipt = applied["migration"]["apply_receipt"]
                with self.assertRaises(ContractError) as error:
                    plan_migration(
                        [batch["project"]],
                        batch["vault"],
                        "fixture",
                        None,
                        tool_versions=dict(_TOOL_VERSIONS),
                        deployment_mode="init",
                        successor_manifest=manifest_path,
                        successor_apply_receipt=batch["evidence"]
                        / ("apply-" + receipt["apply_id"] + ".json"),
                    )
            self.assertEqual(error.exception.code, "successor-conflict")

    def test_successor_rejects_batch_identity_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            batch = _completed_batch(base)
            other_project = legacy_project(base, "other")
            other_vault = base / "other-vault"
            other_vault.mkdir(mode=0o700)
            cases = [
                (
                    [batch["project"], other_project],
                    batch["vault"],
                    "fixture",
                    "scope-conflict",
                ),
                ([batch["project"]], other_vault, "fixture", "scope-conflict"),
                ([batch["project"]], batch["vault"], "intruder", "approval-conflict"),
            ]
            for roots, vault, custodian, code in cases:
                with (
                    self.subTest(custodian=custodian, vault=vault.name),
                    mock.patch.dict(os.environ, batch["environment"]),
                    self.assertRaises(ContractError) as error,
                ):
                    plan_migration(
                        roots,
                        vault,
                        custodian,
                        None,
                        tool_versions=dict(_TOOL_VERSIONS),
                        deployment_mode="init",
                        successor_manifest=batch["manifest_path"],
                        successor_apply_receipt=batch["receipt_path"],
                    )
                self.assertEqual(error.exception.code, code)

    def test_successor_rejects_drifted_carried_cleanup_target(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            batch = _completed_batch(base)
            (batch["project"] / ".trellis/workspace/dev01/new-file.md").write_text(
                "post-apply change\n"
            )
            with (
                mock.patch.dict(os.environ, batch["environment"]),
                self.assertRaises(ContractError) as error,
            ):
                _plan_successor_batch(batch)
            self.assertEqual(error.exception.code, "state-conflict")

    def test_successor_rejects_non_canonical_input_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            batch = _completed_batch(base)
            for manifest_value, receipt_value in (
                ("relative/manifest.json", str(batch["receipt_path"])),
                (
                    str(batch["evidence"] / ".." / "manifest.json"),
                    str(batch["receipt_path"]),
                ),
                (str(batch["manifest_path"]), "relative/apply.json"),
            ):
                with (
                    self.subTest(manifest=manifest_value),
                    mock.patch.dict(os.environ, batch["environment"]),
                    self.assertRaises(ContractError) as error,
                ):
                    plan_migration(
                        [batch["project"]],
                        batch["vault"],
                        "fixture",
                        None,
                        tool_versions=dict(_TOOL_VERSIONS),
                        deployment_mode="init",
                        successor_manifest=manifest_value,
                        successor_apply_receipt=receipt_value,
                    )
                self.assertEqual(error.exception.code, "invalid-argument")

    def test_non_state_carried_cleanup_fails_with_structured_error(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            batch = _completed_batch(base)
            manifest = json.loads(batch["manifest_path"].read_bytes())
            receipt = json.loads(batch["receipt_path"].read_bytes())
            payload = manifest["payload"]
            project = payload["projects"][0]
            legacy_ref = project["sources"][0]
            resource = contracts.resource_id("directory", legacy_ref["path"])
            fake_operation = {
                "operation_id": contracts.operation_id(
                    "apply", resource, "whole-resource"
                ),
                "phase": "apply",
                "resource_id": resource,
                "owner_kind": "directory",
                "target": legacy_ref["path"],
                "selector": "whole-resource",
                "change": {
                    "kind": "copy-directory",
                    "source_ref": dict(legacy_ref),
                },
                "ownership": {
                    "kind": "template-source",
                    "reference": dict(legacy_ref),
                },
                "before_requirement": {
                    "kind": "state",
                    "state": dict(legacy_ref["state"]),
                },
                "dependent_projects": [project["root"]],
            }
            project["private_operations"].insert(0, fake_operation)
            for operation in project["private_operations"]:
                if operation["phase"] == "cleanup":
                    operation["before_requirement"] = {
                        "kind": "phase-after",
                        "phase": "apply",
                        "resource_id": resource,
                    }
            forged_manifest = contracts.seal_document("manifest", payload)
            receipt["payload"]["manifest_id"] = forged_manifest["manifest_id"]
            import shutil

            backup_copy = batch["vault"] / "forged-original-backup"
            shutil.copytree(legacy_ref["path"], backup_copy)
            receipt["payload"]["projects"][0]["private_results"].append(
                {
                    "phase": "apply",
                    "resource_id": resource,
                    "operation_ids": [fake_operation["operation_id"]],
                    "dependent_projects": [project["root"]],
                    "status": "succeeded",
                    "backup_ref": {
                        "path": str(backup_copy),
                        "state": snapshot(backup_copy),
                    },
                    "before": dict(legacy_ref["state"]),
                    "after": dict(legacy_ref["state"]),
                    "error": None,
                }
            )
            forged_receipt = contracts.seal_document("apply_receipt", receipt["payload"])
            forged_manifest_path = batch["evidence"] / "forged-manifest.json"
            forged_manifest_path.write_bytes(canonical_json_bytes(forged_manifest))
            forged_receipt_path = batch["evidence"] / "forged-receipt.json"
            forged_receipt_path.write_bytes(canonical_json_bytes(forged_receipt))
            with (
                mock.patch.dict(os.environ, batch["environment"]),
                self.assertRaises(ContractError) as error,
            ):
                plan_migration(
                    [batch["project"]],
                    batch["vault"],
                    "fixture",
                    None,
                    tool_versions=dict(_TOOL_VERSIONS),
                    deployment_mode="init",
                    successor_manifest=forged_manifest_path,
                    successor_apply_receipt=forged_receipt_path,
                )
            self.assertEqual(error.exception.code, "semantic-violation")

    def test_resealed_inherited_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            batch = _completed_batch(base)
            successor = _plan_successor_batch(batch)
            variants = []
            altered_vault = json.loads(canonical_json_bytes(successor))
            altered_vault["payload"]["backup_root"] = str(batch["evidence"])
            variants.append(altered_vault)
            altered_custodian = json.loads(canonical_json_bytes(successor))
            altered_custodian["payload"]["custodian"] = "intruder"
            variants.append(altered_custodian)
            altered_retention = json.loads(canonical_json_bytes(successor))
            altered_retention["payload"]["retention"] = copy.deepcopy(
                altered_retention["payload"]["retention"]
            )
            altered_retention["payload"]["retention"]["normal_observation_days"] = 30
            variants.append(altered_retention)
            for index, variant in enumerate(variants):
                with (
                    self.subTest(variant=index),
                    mock.patch.dict(os.environ, batch["environment"]),
                    self.assertRaises(ContractError) as error,
                ):
                    validate_legacy_inputs(
                        contracts.seal_document("manifest", variant["payload"]),
                        _reader,
                    )
                self.assertEqual(error.exception.code, "semantic-violation")
            altered_publication = json.loads(canonical_json_bytes(successor))
            altered_publication["payload"]["publication_decisions"] = {
                "schema_version": 1,
                "items": ["not-empty"],
            }
            with (
                mock.patch.dict(os.environ, batch["environment"]),
                self.assertRaises(ContractError),
            ):
                validate_legacy_inputs(
                    contracts.seal_document(
                        "manifest", altered_publication["payload"]
                    ),
                    _reader,
                )

    def test_resealed_pause_operation_is_refused_at_apply_anchor(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            batch = _completed_batch(base)
            successor = _plan_successor_batch(batch)
            pause_asset = SCRIPTS.parents[0] / "assets" / "migration-paused-agents.txt"
            pause_reference = {
                "path": str(pause_asset),
                "state": snapshot(pause_asset),
            }
            legacy_global = b"# Legacy global routing\nUse trellis-workflow.\n"
            router_dir = batch["home"] / "elsewhere"
            router_dir.mkdir(parents=True)
            router = router_dir / "AGENTS.md"
            router.write_bytes(legacy_global)
            fixture_pins = sbtd_migration_plan._ownership_pins()
            fixture_pins["agents"] = hashlib.sha256(legacy_global).hexdigest()
            pinned = {"type": "file", "checksum": fixture_pins["agents"]}
            payload = successor["payload"]
            root = payload["projects"][0]["root"]
            resource = contracts.resource_id("markdown", str(router))
            pause_operation = {
                "operation_id": contracts.operation_id(
                    "apply", resource, "pause-legacy-routing"
                ),
                "phase": "apply",
                "resource_id": resource,
                "owner_kind": "markdown",
                "target": str(router),
                "selector": "pause-legacy-routing",
                "change": {
                    "kind": "ensure-file-block",
                    "source_ref": pause_reference,
                },
                "ownership": {
                    "kind": "template-source",
                    "reference": {"path": str(router), "state": pinned},
                },
                "before_requirement": {"kind": "state", "state": pinned},
                "dependent_projects": [root],
            }
            payload["shared_operations"].append(pause_operation)
            payload["shared_roots"].append(
                {
                    "kind": "omp-home",
                    "path": str(router_dir),
                    "dependent_projects": [root],
                }
            )
            for project in payload["projects"]:
                project["shared_operation_ids"] = sorted(
                    operation["operation_id"]
                    for operation in payload["shared_operations"]
                    if project["root"] in operation["dependent_projects"]
                )
            resealed = contracts.seal_document("manifest", payload)
            manifest_path = batch["evidence"] / "pause-carried-manifest.json"
            manifest_path.write_bytes(canonical_json_bytes(resealed))
            with (
                mock.patch.dict(os.environ, batch["environment"]),
                mock.patch.object(
                    sbtd_migration_plan, "_ownership_pins", return_value=fixture_pins
                ),
                mock.patch(
                    "sbtd_migration.runtime_versions",
                    return_value=dict(_TOOL_VERSIONS),
                ),
                self.assertRaises(ContractError) as error,
            ):
                apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
            self.assertEqual(error.exception.code, "approval-conflict")


class SuccessorCliTests(unittest.TestCase):
    def _argv(self, *extra):
        return [
            "migration",
            "--phase",
            "plan",
            "--projects-root",
            "/repo/one",
            "--backup-root",
            "/private/backup",
            "--custodian",
            "release-owner",
            *extra,
        ]

    def test_successor_pair_parses_with_deployment_mode(self):
        args = onboard_arguments.parse_workflow_args(
            self._argv(
                "--successor-manifest",
                "/private/manifest.json",
                "--successor-apply-receipt",
                "/private/apply.json",
                "--deployment-mode",
                "init",
            )
        )
        self.assertEqual(args.successor_manifest, "/private/manifest.json")
        self.assertEqual(args.successor_apply_receipt, "/private/apply.json")
        self.assertEqual(args.deployment_mode, "init")

    def test_successor_options_are_rejected_in_invalid_combinations(self):
        import contextlib
        import io

        def assert_error(argv):
            stderr = io.StringIO()
            with (
                contextlib.redirect_stderr(stderr),
                self.assertRaises(SystemExit) as caught,
            ):
                onboard_arguments.parse_workflow_args(argv)
            self.assertEqual(caught.exception.code, 2, stderr.getvalue())

        assert_error(self._argv("--successor-manifest", "/private/manifest.json"))
        assert_error(
            self._argv(
                "--successor-manifest",
                "/private/manifest.json",
                "--successor-apply-receipt",
                "/private/apply.json",
            )
        )
        assert_error(
            self._argv(
                "--successor-manifest",
                "/private/manifest.json",
                "--successor-apply-receipt",
                "/private/apply.json",
                "--deployment-mode",
                "init",
                "--publication-decisions",
                "/private/decisions.json",
            )
        )
        assert_error(
            self._argv(
                "--successor-manifest",
                "/private/manifest.json",
                "--successor-apply-receipt",
                "/private/apply.json",
                "--deployment-mode",
                "init",
                "--routing-approvals",
                "/private/routing.json",
            )
        )
        with self.assertRaises(SystemExit):
            onboard_arguments.parse_workflow_args(
                [
                    "migration",
                    "--phase",
                    "apply",
                    "--manifest",
                    "/private/manifest.json",
                    "--successor-manifest",
                    "/private/manifest.json",
                    "--yes",
                ]
            )


if __name__ == "__main__":
    unittest.main()
