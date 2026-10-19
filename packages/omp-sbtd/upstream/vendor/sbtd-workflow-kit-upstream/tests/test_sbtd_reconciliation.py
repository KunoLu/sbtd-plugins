"""Current-state reconciliation lifecycle; native graph/report boundaries are fixtures."""
from __future__ import annotations

# ruff: noqa: I001 -- approved fixture imports bootstrap the local script path.

import contextlib
import dataclasses
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import test_sbtd_approved_agents_deployment as approved
from tests.test_sbtd_followup_batch import (
    _failed_copy,
    _focused_installation_templates,
    _synthetic_smoke,
)
from tests.test_sbtd_migration_cleanup import _fake_vendor_adapter
from tests.test_sbtd_migration_verify import _tree_bytes

import onboard_contracts as contracts
from sbtd_graft_deployment import load_deployment_context, save_deployment_evidence
from sbtd_migration_files import save_document, snapshot
from sbtd_reconciliation import reconcile_deployment
from sbtd_recovery import apply_recovery, plan_recovery
from sbtd_migration_verify import verify_migration


def setUpModule():
    approved.setUpModule()


def tearDownModule():
    approved.tearDownModule()


class CurrentStateReconciliationTests(unittest.TestCase):
    def test_missing_receipt_current_state_is_verified_without_redeployment(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = approved._SignedBatch(Path(directory).resolve())
            manifest = batch.plan(deployment_mode="init")
            manifest_path = batch.write_manifest(manifest, "manifest.json")
            _applied, apply_path = batch.apply(
                manifest_path, routing_approvals=batch.approval
            )
            missing_path = batch.evidence / "interrupted-deployment.json"
            deployed, code = batch.execute(manifest_path, apply_path, missing_path)
            self.assertEqual(code, 0, deployed)
            missing_path.unlink()
            project_before = _tree_bytes(batch.root)
            home_before = _tree_bytes(batch.home)
            originals_before = _tree_bytes(batch.vault)
            manifest_before = manifest_path.read_bytes()
            apply_before = apply_path.read_bytes()
            output_path = batch.evidence / "current-state-evidence.json"

            with mock.patch.dict(os.environ, batch.environment):
                with self.assertRaises(contracts.ContractError):
                    verify_migration(manifest_path, apply_path, missing_path)

                from sbtd_reconciliation import reconcile_deployment

                with (
                    mock.patch(
                        "sbtd_graft_deployment.verified_runtime",
                        return_value=dict(approved._RUNTIME),
                    ),
                    mock.patch(
                        "sbtd_graft_deployment.run_project_smoke",
                        side_effect=_synthetic_smoke(manifest),
                    ),
                    mock.patch(
                        "sbtd_graft_deployment.build_project_graph",
                        side_effect=AssertionError("reconciliation must not rebuild"),
                    ),
                    mock.patch(
                        "sbtd_graft_deployment.execute_resource",
                        side_effect=AssertionError("reconciliation must not deploy"),
                    ),
                ):
                    result = reconcile_deployment(
                        manifest_path,
                        apply_path,
                        missing_path,
                        output_path,
                        confirmed=True,
                    )

                self.assertEqual(result["path"], str(output_path))
                evidence = json.loads(output_path.read_bytes())
                self.assertEqual(
                    evidence["payload"]["reconciliation"]["historical_execution"],
                    "unknown",
                )
                self.assertEqual(
                    evidence["payload"]["reconciliation"]["kind"], "current-state"
                )
                verified, verify_code = verify_migration(
                    manifest_path, apply_path, output_path
                )

            self.assertEqual(verify_code, 0, verified)
            self.assertEqual(verified["status"], "verified")
            self.assertEqual(
                verified["migration"]["verification"]["payload"]["acceptance_basis"],
                "current-state",
            )
            self.assertFalse(missing_path.exists())
            self.assertEqual(_tree_bytes(batch.root), project_before)
            self.assertEqual(_tree_bytes(batch.home), home_before)
            self.assertEqual(_tree_bytes(batch.vault), originals_before)
            self.assertEqual(manifest_path.read_bytes(), manifest_before)
            self.assertEqual(apply_path.read_bytes(), apply_before)


def _native_doubles(manifest, *, smoke=None):
    """Contract-backed doubles for the native external boundaries only.

    Deployment writers stay hard-blocked: reconciliation must never rebuild a
    graph or execute a resource while observing current state.
    """
    return (
        mock.patch(
            "sbtd_graft_deployment.verified_runtime",
            return_value=dict(approved._RUNTIME),
        ),
        mock.patch(
            "sbtd_graft_deployment.run_project_smoke",
            side_effect=(
                _synthetic_smoke(manifest) if smoke is None else smoke
            ),
        ),
        mock.patch(
            "sbtd_graft_deployment.build_project_graph",
            side_effect=AssertionError("reconciliation must not rebuild"),
        ),
        mock.patch(
            "sbtd_graft_deployment.execute_resource",
            side_effect=AssertionError("reconciliation must not deploy"),
        ),
    )


def _interrupted_deployment(case):
    """One genuinely deployed batch whose historical receipt is then lost."""
    directory = tempfile.TemporaryDirectory()
    case.addCleanup(directory.cleanup)
    batch = approved._SignedBatch(Path(directory.name).resolve())
    manifest = batch.plan(deployment_mode="init")
    manifest_path = batch.write_manifest(manifest, "manifest.json")
    _receipt, apply_path = batch.apply(
        manifest_path, routing_approvals=batch.approval
    )
    missing_path = batch.evidence / "interrupted-deployment.json"
    deployed, code = batch.execute(manifest_path, apply_path, missing_path)
    case.assertEqual(code, 0, deployed)
    missing_path.unlink()
    return batch, manifest, manifest_path, apply_path, missing_path


def _reconcile(batch, manifest, manifest_path, apply_path, missing_path, output_path, *, smoke=None):
    patches = _native_doubles(manifest, smoke=smoke)
    with (
        mock.patch.dict(os.environ, batch.environment),
        patches[0],
        patches[1],
        patches[2],
        patches[3],
    ):
        return reconcile_deployment(
            manifest_path,
            apply_path,
            missing_path,
            output_path,
            confirmed=True,
        )


def _failed_run_smoke(manifest):
    """Smoke double whose native check genuinely fails (exit 1), truthfully reported."""
    passing = _synthetic_smoke(manifest)

    def smoke(project, runtime, evidence_dir):
        refs = passing(project, runtime, evidence_dir)
        raw_path, envelope_path, summary_path = (
            Path(reference["path"]) for reference in refs
        )
        raw = json.loads(raw_path.read_bytes())
        raw["exitCode"] = 1
        raw["processExitCode"] = 1
        raw_path.write_text(json.dumps(raw), encoding="utf-8")
        envelope = json.loads(envelope_path.read_bytes())
        envelope["reports"][0]["status"] = "failed"
        envelope["reports"][0]["sha256"] = hashlib.sha256(
            raw_path.read_bytes()
        ).hexdigest()
        envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
        return [
            {"path": str(path), "state": snapshot(path)}
            for path in (raw_path, envelope_path, summary_path)
        ]

    return smoke


def _stage_results(document_path):
    """Resource results of one stage document, indexed by resource_id."""
    document = json.loads(document_path.read_bytes())
    results = [
        result
        for project in document["payload"]["projects"]
        for result in project["private_results"]
    ] + list(document["payload"]["shared_results"])
    return {result["resource_id"]: result for result in results}


def _apply_only_operation(manifest):
    """One declared apply resource with no deploy observation of its own."""
    payload = manifest["payload"]
    operations = [
        operation
        for project in payload["projects"]
        for operation in project["private_operations"]
    ] + list(payload["shared_operations"])
    deployed = {
        operation["resource_id"] for operation in operations if operation["phase"] == "deploy"
    }
    apply_only = sorted(
        (
            operation
            for operation in operations
            if operation["phase"] == "apply" and operation["resource_id"] not in deployed
        ),
        key=lambda operation: operation["target"],
    )
    if not apply_only:
        raise AssertionError("fixture must declare an apply-only resource")
    return apply_only[0]


def _drift_target(target, after):
    """Mutate one receipt-proven target away from its recorded after-state."""
    if after["type"] == "absent":
        target.write_bytes(b"resurrected receipt-proven absence\n")
    elif after["type"] == "file":
        with open(target, "ab") as handle:
            handle.write(b"\nreceipt outcome drift\n")
    else:
        (target / "receipt-outcome-drift.marker").write_bytes(b"drift\n")


def _reseal_deployment_evidence(document_path, mutate):
    """Mutate one deployment evidence payload in place, then honestly reseal it.

    The seal is recomputed from the mutated payload, so the result is a
    schema-valid, self-consistent document whose provenance claims are false.
    """
    document = json.loads(document_path.read_bytes())
    mutate(document["payload"])
    resealed = contracts.seal_document("deployment_evidence", document["payload"])
    document_path.write_bytes(contracts.canonical_json_bytes(resealed))
    return resealed


def _drift_cited_copy(copied, change, damaged):
    """Idempotently apply the concurrent cited-source change under test."""
    if change == "modify":
        copied.write_bytes(damaged)
    else:
        copied.unlink(missing_ok=True)


def _reconciled_batch_citing_copied_inputs(case):
    """One reconciled batch whose evidence cites intact private input copies.

    The reseal is honest: each copy holds the exact genuine input bytes, so
    the cited refs satisfy both the byte binding and the live provenance gate
    while consumer argv still names the original documents. Mutating a copy
    afterwards therefore exercises only the cited-source recheck — it cannot
    invalidate the argv spelling or the already-bound raw documents before
    the initial gate.
    """
    batch, manifest, manifest_path, apply_path, missing_path = (
        _interrupted_deployment(case)
    )
    output_path = batch.evidence / "current-state-evidence.json"
    _reconcile(batch, manifest, manifest_path, apply_path, missing_path, output_path)
    copies = {}
    for ref_key, source in (
        ("manifest_ref", manifest_path),
        ("apply_receipt_ref", apply_path),
    ):
        copied = batch.evidence / f"cited-{ref_key}.json"
        copied.write_bytes(source.read_bytes())
        copies[ref_key] = copied

    def cite_copies(payload):
        for ref_key, copied in copies.items():
            payload["reconciliation"][ref_key]["path"] = str(copied)

    _reseal_deployment_evidence(output_path, cite_copies)
    return batch, manifest_path, apply_path, missing_path, output_path, copies


def _verified_batch_citing_copied_inputs(case):
    """Reconciled-and-verified copied-input batch, ready for real cleanup."""
    batch, manifest_path, apply_path, missing_path, output_path, copies = (
        _reconciled_batch_citing_copied_inputs(case)
    )
    with mock.patch.dict(os.environ, batch.environment):
        verified, verify_code = verify_migration(
            manifest_path, apply_path, output_path
        )
        case.assertEqual(verify_code, 0, verified)
        case.assertEqual(verified["status"], "verified")
        verification = verified["migration"]["verification"]
        verification_path = batch.evidence / "verification.json"
        save_document(verification_path, verification, private_root=batch.evidence)
    return (
        batch,
        manifest_path,
        apply_path,
        missing_path,
        output_path,
        copies,
        verification,
        verification_path,
    )


class CurrentStateReconciliationLifecycleTests(unittest.TestCase):
    def setUp(self):
        # Provenance/retry invariants never depend on the full skill catalog.
        _focused_installation_templates(self)

    def test_reconcile_then_cumulative_retry_preserves_current_state_provenance(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        result = _reconcile(
            batch, manifest, manifest_path, apply_path, missing_path, output_path
        )
        evidence = result["evidence"]

        # An ordinary cumulative deployment retry after reconciliation must
        # carry the reconciliation provenance forward unchanged: provenance is
        # immutable and can never be laundered back to an executed origin.
        retry_path = batch.evidence / "deployment-retry.json"
        retried, retry_code = batch.execute(
            manifest_path,
            apply_path,
            retry_path,
            previous_path=output_path,
            rebuild_graph=False,
        )
        self.assertEqual(retry_code, 0, retried)
        retry_evidence = json.loads(retry_path.read_bytes())
        self.assertEqual(
            retry_evidence["payload"]["reconciliation"],
            evidence["payload"]["reconciliation"],
        )
        self.assertEqual(
            retry_evidence["payload"]["previous_deployment_id"],
            evidence["deployment_id"],
        )
        with mock.patch.dict(os.environ, batch.environment):
            verified, verify_code = verify_migration(
                manifest_path, apply_path, retry_path
            )
        self.assertEqual(verify_code, 0, verified)
        self.assertEqual(
            verified["migration"]["verification"]["payload"]["acceptance_basis"],
            "current-state",
        )
        self.assertFalse(missing_path.exists())

    def test_historical_receipt_reappearance_fails_verification(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        _reconcile(batch, manifest, manifest_path, apply_path, missing_path, output_path)
        evidence_before = output_path.read_bytes()
        appeared = b'{"late_historical_evidence": true}\n'
        missing_path.write_bytes(appeared)
        try:
            with (
                mock.patch.dict(os.environ, batch.environment),
                self.assertRaises(contracts.ContractError) as rejected,
            ):
                verify_migration(manifest_path, apply_path, output_path)
            self.assertEqual(rejected.exception.code, "state-conflict")
            self.assertEqual(missing_path.read_bytes(), appeared)
            self.assertEqual(output_path.read_bytes(), evidence_before)
        finally:
            missing_path.unlink()

    def test_reconciled_evidence_supports_recovery_and_cleanup_planning(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        _reconcile(batch, manifest, manifest_path, apply_path, missing_path, output_path)

        with mock.patch.dict(os.environ, batch.environment):
            # Recovery planning consumes the genuine reconciled record: every
            # inverse step chains from the derived results and their retained
            # originals, not from a mock echo.
            planned, plan_code = plan_recovery(
                manifest_path,
                apply_receipt_path=apply_path,
                deployment_evidence_path=output_path,
            )
            self.assertEqual(plan_code, 0, planned)
            plan = planned["recovery"]["plan"]
            self.assertTrue(plan["plan_id"])

            verified, verify_code = verify_migration(
                manifest_path, apply_path, output_path
            )
        self.assertEqual(verify_code, 0, verified)
        verification = verified["migration"]["verification"]["payload"]
        self.assertEqual(verification["acceptance_basis"], "current-state")
        # Cleanup planning consumption: candidates are derived from the
        # reconciled evidence after-states and the live tree.
        self.assertIn("shared_cleanup_candidates", verification)
        for project in verification["projects"]:
            self.assertIn("cleanup_candidates", project)

    def test_cli_reconcile_roundtrip_emits_envelope_and_verifies(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        project_before = _tree_bytes(batch.root)
        originals_before = _tree_bytes(batch.vault)

        import onboard

        argv = [
            "onboard",
            "migration",
            "--phase",
            "reconcile",
            "--manifest",
            str(manifest_path),
            "--apply-receipt",
            str(apply_path),
            "--missing-deployment-evidence",
            str(missing_path),
            "--deployment-evidence-out",
            str(output_path),
            "--yes",
            "--json",
        ]
        patches = _native_doubles(manifest)
        with (
            mock.patch.dict(os.environ, batch.environment),
            mock.patch.object(sys, "argv", argv),
            patches[0],
            patches[1],
            patches[2],
            patches[3],
        ):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = onboard.main()
        self.assertEqual(code, 0, buffer.getvalue())
        envelope = json.loads(buffer.getvalue())
        self.assertEqual(envelope["mode"], "migration")
        self.assertEqual(envelope["phase"], "reconcile")
        self.assertEqual(envelope["status"], "reconciled")
        self.assertEqual(envelope["manifest_id"], manifest["manifest_id"])
        self.assertIsNone(envelope["verification_id"])
        self.assertTrue(envelope["projects"])
        self.assertEqual(
            {project["status"] for project in envelope["projects"]}, {"reconciled"}
        )
        self.assertEqual(
            envelope["migration"]["deployment_evidence_path"], str(output_path)
        )
        evidence = envelope["migration"]["deployment_evidence"]
        self.assertEqual(
            evidence["payload"]["reconciliation"],
            {
                "kind": "current-state",
                "historical_execution": "unknown",
                "manifest_ref": {
                    "path": str(manifest_path),
                    "state": snapshot(manifest_path),
                },
                "apply_receipt_ref": {
                    "path": str(apply_path),
                    "state": snapshot(apply_path),
                },
                "missing_deployment_evidence": {
                    "path": str(missing_path),
                    "state": {"type": "absent", "checksum": None},
                },
                "runtime_versions": evidence["payload"]["reconciliation"][
                    "runtime_versions"
                ],
            },
        )
        self.assertEqual(
            evidence["payload"]["reconciliation"]["runtime_versions"]["graft"],
            manifest["payload"]["tool_versions"]["graft"],
        )
        self.assertEqual(evidence, json.loads(output_path.read_bytes()))

        with mock.patch.dict(os.environ, batch.environment):
            verified, verify_code = verify_migration(
                manifest_path, apply_path, output_path
            )
        self.assertEqual(verify_code, 0, verified)
        self.assertEqual(
            verified["migration"]["verification"]["payload"]["acceptance_basis"],
            "current-state",
        )
        self.assertFalse(missing_path.exists())
        self.assertEqual(_tree_bytes(batch.root), project_before)
        self.assertEqual(_tree_bytes(batch.vault), originals_before)

    def test_repeated_reconciliation_to_a_new_path_is_idempotent(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        first_path = batch.evidence / "current-state-evidence.json"
        first = _reconcile(
            batch, manifest, manifest_path, apply_path, missing_path, first_path
        )
        # The same output is never overwritten; a fresh path observes the same
        # unchanged current state into an equivalent new record.
        with self.assertRaises(contracts.ContractError) as collision:
            _reconcile(
                batch, manifest, manifest_path, apply_path, missing_path, first_path
            )
        self.assertEqual(collision.exception.code, "state-conflict")

        second_path = batch.evidence / "current-state-evidence-2.json"
        second = _reconcile(
            batch, manifest, manifest_path, apply_path, missing_path, second_path
        )
        self.assertEqual(
            second["evidence"]["payload"]["reconciliation"],
            first["evidence"]["payload"]["reconciliation"],
        )
        with mock.patch.dict(os.environ, batch.environment):
            verified, verify_code = verify_migration(
                manifest_path, apply_path, second_path
            )
        self.assertEqual(verify_code, 0, verified)
        self.assertFalse(missing_path.exists())


class CurrentStateReconciliationRefusalTests(unittest.TestCase):
    def setUp(self):
        # Refusal drift targets are file-level fixture objects, not skill dirs.
        _focused_installation_templates(self)

    def test_missing_consent_blocks_before_any_write_or_smoke(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        evidence_before = _tree_bytes(batch.evidence)
        patches = _native_doubles(manifest)
        with (
            mock.patch.dict(os.environ, batch.environment),
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            self.assertRaises(contracts.ContractError) as failure,
        ):
            reconcile_deployment(manifest_path, apply_path, missing_path, output_path)
        self.assertEqual(failure.exception.code, "confirmation-required")
        self.assertFalse(output_path.exists())
        self.assertFalse(missing_path.exists())
        self.assertEqual(_tree_bytes(batch.evidence), evidence_before)

    def test_existing_historical_receipt_stays_authoritative(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        batch = approved._SignedBatch(Path(directory.name).resolve())
        manifest = batch.plan(deployment_mode="init")
        manifest_path = batch.write_manifest(manifest, "manifest.json")
        _receipt, apply_path = batch.apply(
            manifest_path, routing_approvals=batch.approval
        )
        historical_path = batch.evidence / "interrupted-deployment.json"
        deployed, code = batch.execute(manifest_path, apply_path, historical_path)
        self.assertEqual(code, 0, deployed)
        historical_before = historical_path.read_bytes()
        output_path = batch.evidence / "current-state-evidence.json"
        evidence_before = _tree_bytes(batch.evidence)

        with self.assertRaises(contracts.ContractError) as failure:
            _reconcile(
                batch,
                manifest,
                manifest_path,
                apply_path,
                historical_path,
                output_path,
            )
        self.assertEqual(failure.exception.code, "state-conflict")
        self.assertEqual(historical_path.read_bytes(), historical_before)
        self.assertFalse(output_path.exists())
        self.assertEqual(_tree_bytes(batch.evidence), evidence_before)

    def test_unsafe_and_colliding_paths_reject_before_writes(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"

        # Output must be absolute, physical, new, private and disjoint from
        # every declared/protected object; all rejections precede any write.
        cases = {
            "output equals missing": (missing_path, missing_path),
            "output aliases absent missing by case": (
                missing_path, missing_path.with_name(missing_path.name.upper()),
            ),
            "output aliases absent missing by Unicode": (
                batch.evidence / "caf\u00e9.json",
                batch.evidence / "cafe\u0301.json",
            ),
            "output equals manifest": (missing_path, manifest_path),
            "output outside private dir": (
                missing_path,
                batch.base / "outside.json",
            ),
            "relative output": (missing_path, Path("relative-current-state.json")),
            "relative missing": (Path("relative-missing.json"), output_path),
            "missing equals apply receipt": (apply_path, output_path),
        }
        for name, (missing, output) in cases.items():
            with self.subTest(case=name):
                evidence_before = _tree_bytes(batch.evidence)
                manifest_before = manifest_path.read_bytes()
                with self.assertRaises(contracts.ContractError) as failure:
                    _reconcile(
                        batch, manifest, manifest_path, apply_path, missing, output
                    )
                self.assertEqual(failure.exception.code, "private-scope")
                # No write or smoke happened; every input is byte-identical.
                self.assertEqual(_tree_bytes(batch.evidence), evidence_before)
                self.assertEqual(manifest_path.read_bytes(), manifest_before)
                self.assertFalse(missing_path.exists())
                self.assertFalse(output_path.exists())

        # An already-existing output is preserved, never overwritten.
        output_path.write_bytes(b"pre-existing private content\n")
        evidence_before = _tree_bytes(batch.evidence)
        with self.assertRaises(contracts.ContractError) as failure:
            _reconcile(
                batch,
                manifest,
                manifest_path,
                apply_path,
                missing_path,
                output_path,
            )
        self.assertEqual(failure.exception.code, "state-conflict")
        self.assertEqual(output_path.read_bytes(), b"pre-existing private content\n")
        self.assertEqual(_tree_bytes(batch.evidence), evidence_before)

    def test_tampered_deployed_target_fails_closed_without_repairs(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        tampered = batch.agents.read_bytes() + b"\ntampered after deployment\n"
        batch.agents.write_bytes(tampered)

        with self.assertRaises(contracts.ContractError) as failure:
            _reconcile(
                batch,
                manifest,
                manifest_path,
                apply_path,
                missing_path,
                output_path,
            )
        self.assertEqual(failure.exception.code, "state-conflict")
        # No evidence, no repair, no historical fabrication.
        self.assertFalse(output_path.exists())
        self.assertFalse(missing_path.exists())
        self.assertEqual(batch.agents.read_bytes(), tampered)

    def test_missing_retained_original_fails_closed(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        resource = contracts.resource_id("markdown", str(batch.agents))
        backup = (
            batch.vault / manifest["manifest_id"] / "deploy" / resource
        )
        self.assertTrue(backup.exists())
        backup_bytes = backup.read_bytes()
        backup.unlink()
        vault_after_unlink = _tree_bytes(batch.vault)

        with self.assertRaises(contracts.ContractError) as failure:
            _reconcile(
                batch,
                manifest,
                manifest_path,
                apply_path,
                missing_path,
                output_path,
            )
        self.assertEqual(failure.exception.code, "original-unavailable")
        self.assertFalse(output_path.exists())
        self.assertFalse(missing_path.exists())
        self.assertEqual(_tree_bytes(batch.vault), vault_after_unlink)
        self.assertNotEqual(batch.agents.read_bytes(), backup_bytes)

    def test_altered_manifest_bytes_fail_binding(self):
        batch, _manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        forged = json.loads(manifest_path.read_bytes())
        forged["payload"]["custodian"] = "forged-custodian"
        forged_path = batch.evidence / "manifest-forged.json"
        forged_path.write_bytes(
            contracts.canonical_json_bytes(
                contracts.seal_document("manifest", forged["payload"])
            )
        )

        with self.assertRaises(contracts.ContractError) as failure:
            _reconcile(
                batch,
                forged,
                forged_path,
                apply_path,
                missing_path,
                output_path,
            )
        self.assertEqual(failure.exception.code, "binding-violation")
        self.assertFalse(output_path.exists())
        self.assertFalse(missing_path.exists())

    def test_incomplete_apply_receipt_is_rejected(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        failed_apply = batch.evidence / "apply-failed.json"
        _failed_copy(apply_path, "apply_receipt", failed_apply)

        with self.assertRaises(contracts.ContractError) as failure:
            _reconcile(
                batch,
                manifest,
                manifest_path,
                failed_apply,
                missing_path,
                output_path,
            )
        self.assertEqual(failure.exception.code, "binding-violation")
        self.assertFalse(output_path.exists())
        self.assertFalse(missing_path.exists())

    def test_tampered_approved_candidate_is_rejected(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        projected = batch.agents.read_bytes()
        batch.candidate.write_bytes(
            approved._PAUSE_ASSET.read_bytes() + b"\ntampered after approval\n"
        )

        with self.assertRaises(contracts.ContractError):
            _reconcile(
                batch,
                manifest,
                manifest_path,
                apply_path,
                missing_path,
                output_path,
            )
        self.assertFalse(output_path.exists())
        self.assertFalse(missing_path.exists())
        self.assertEqual(batch.agents.read_bytes(), projected)

    def test_failed_fresh_smoke_leaves_artifacts_but_no_evidence(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        evidence_before = set(os.listdir(batch.evidence))

        with self.assertRaises(contracts.ContractError) as failure:
            _reconcile(
                batch,
                manifest,
                manifest_path,
                apply_path,
                missing_path,
                output_path,
                smoke=_failed_run_smoke(manifest),
            )
        self.assertEqual(failure.exception.code, "report-acceptance")
        self.assertFalse(output_path.exists())
        self.assertFalse(missing_path.exists())
        # Truthful fresh smoke artifacts may remain; accepted evidence may not.
        created = set(os.listdir(batch.evidence)) - evidence_before
        self.assertTrue(
            any(name.startswith("api-report-graft-smoke-") for name in created)
        )

    def test_uncompleted_fresh_smoke_records_no_evidence(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        evidence_before = _tree_bytes(batch.evidence)

        def raising_smoke(project, runtime, evidence_dir):
            raise RuntimeError("synthetic native check crash")

        with self.assertRaises(contracts.ContractError) as failure:
            _reconcile(
                batch,
                manifest,
                manifest_path,
                apply_path,
                missing_path,
                output_path,
                smoke=raising_smoke,
            )
        self.assertEqual(failure.exception.code, "report-unavailable")
        self.assertFalse(output_path.exists())
        self.assertFalse(missing_path.exists())
        self.assertEqual(_tree_bytes(batch.evidence), evidence_before)

    def test_smoke_that_mutates_a_target_fails_closed(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        passing = _synthetic_smoke(manifest)
        projected = batch.agents.read_bytes()

        def mutating_smoke(project, runtime, evidence_dir):
            refs = passing(project, runtime, evidence_dir)
            with open(batch.agents, "ab") as handle:
                handle.write(b"\nsmoke mutation\n")
            return refs

        with self.assertRaises(contracts.ContractError) as failure:
            _reconcile(
                batch,
                manifest,
                manifest_path,
                apply_path,
                missing_path,
                output_path,
                smoke=mutating_smoke,
            )
        self.assertEqual(failure.exception.code, "state-conflict")
        self.assertFalse(output_path.exists())
        self.assertFalse(missing_path.exists())
        # The mutation is preserved as evidence of the unsafe check; nothing
        # is silently repaired.
        self.assertEqual(
            batch.agents.read_bytes(), projected + b"\nsmoke mutation\n"
        )

    def test_output_race_is_rejected_without_overwriting(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        passing = _synthetic_smoke(manifest)
        raced = b"raced private content\n"

        def racing_smoke(project, runtime, evidence_dir):
            refs = passing(project, runtime, evidence_dir)
            output_path.write_bytes(raced)
            return refs

        with self.assertRaises(contracts.ContractError) as failure:
            _reconcile(
                batch,
                manifest,
                manifest_path,
                apply_path,
                missing_path,
                output_path,
                smoke=racing_smoke,
            )
        self.assertEqual(failure.exception.code, "state-conflict")
        self.assertEqual(output_path.read_bytes(), raced)
        self.assertFalse(missing_path.exists())

    def test_tampered_reconciled_evidence_fails_verification(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        _reconcile(batch, manifest, manifest_path, apply_path, missing_path, output_path)

        document = json.loads(output_path.read_bytes())
        document["payload"]["reconciliation"]["kind"] = "executed"
        output_path.write_bytes(json.dumps(document).encode("utf-8"))
        with (
            mock.patch.dict(os.environ, batch.environment),
            self.assertRaises(contracts.ContractError),
        ):
            verify_migration(manifest_path, apply_path, output_path)

    def test_apply_only_target_drift_fails_before_any_smoke(self):
        # Every successful apply target without a fresh deploy observation is
        # compared with its receipt after-state before smoke runs, regardless
        # of runtime version equality.
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        operation = _apply_only_operation(manifest)
        target = Path(operation["target"])
        after = _stage_results(apply_path)[operation["resource_id"]]["after"]
        self.assertEqual(snapshot(target), after)
        _drift_target(target, after)
        drifted = snapshot(target)
        evidence_before = _tree_bytes(batch.evidence)

        with self.assertRaises(contracts.ContractError) as failure:
            _reconcile(
                batch,
                manifest,
                manifest_path,
                apply_path,
                missing_path,
                output_path,
            )
        self.assertEqual(failure.exception.code, "state-conflict")
        self.assertFalse(output_path.exists())
        self.assertFalse(missing_path.exists())
        # The refusal precedes any fresh smoke: no report artifacts appear and
        # the drifted target is preserved, never repaired.
        self.assertEqual(_tree_bytes(batch.evidence), evidence_before)
        self.assertEqual(snapshot(target), drifted)

    def test_smoke_mutating_apply_only_target_fails_closed(self):
        # The same receipt-outcome gate runs again after the native check
        # window, so a smoke that mutates an apply-only target invalidates the
        # observation instead of being published.
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        operation = _apply_only_operation(manifest)
        target = Path(operation["target"])
        after = _stage_results(apply_path)[operation["resource_id"]]["after"]
        passing = _synthetic_smoke(manifest)

        def mutating_smoke(project, runtime, evidence_dir):
            refs = passing(project, runtime, evidence_dir)
            _drift_target(target, after)
            return refs

        with self.assertRaises(contracts.ContractError) as failure:
            _reconcile(
                batch,
                manifest,
                manifest_path,
                apply_path,
                missing_path,
                output_path,
                smoke=mutating_smoke,
            )
        self.assertEqual(failure.exception.code, "state-conflict")
        self.assertFalse(output_path.exists())
        self.assertFalse(missing_path.exists())
        # The mutation is preserved as evidence of the unsafe check.
        self.assertNotEqual(snapshot(target), after)

    def test_retry_output_cannot_claim_reconciled_missing_path(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        _reconcile(batch, manifest, manifest_path, apply_path, missing_path, output_path)

        # A cumulative retry whose proposed output IS the cited missing
        # historical receipt path is refused at preflight, before any write
        # or smoke.
        with (
            mock.patch.dict(os.environ, batch.environment),
            self.assertRaises(contracts.ContractError) as failure,
        ):
            load_deployment_context(
                manifest_path,
                apply_path,
                missing_path,
                previous_path=output_path,
                mode="init",
                roots=[batch.root],
                hooks_authorized=False,
            )
        self.assertEqual(failure.exception.code, "private-scope")
        self.assertFalse(missing_path.exists())

        # The save path refuses the same collision even when the output is
        # swapped onto the missing path after a clean preflight.
        retry_path = batch.evidence / "deployment-retry.json"
        with mock.patch.dict(os.environ, batch.environment):
            context = load_deployment_context(
                manifest_path,
                apply_path,
                retry_path,
                previous_path=output_path,
                mode="init",
                roots=[batch.root],
                hooks_authorized=False,
            )
        swapped = dataclasses.replace(context, output_path=missing_path)
        carried = _stage_results(output_path)
        with self.assertRaises(contracts.ContractError) as failure:
            save_deployment_evidence(swapped, carried, {}, failed_smokes=set())
        self.assertEqual(failure.exception.code, "private-scope")
        self.assertFalse(missing_path.exists())
        self.assertFalse(retry_path.exists())

    def test_smoke_cannot_create_an_absent_original_slot(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        graph = next(
            op for project in manifest["payload"]["projects"]
            for op in project["private_operations"]
            if op["change"]["kind"] == "build-graft"
        )
        backup = (
            Path(manifest["payload"]["backup_root"]) / manifest["manifest_id"]
            / "deploy" / graph["resource_id"]
        )
        self.assertFalse(backup.exists())
        passing = _synthetic_smoke(manifest)

        def mutating_smoke(project, runtime, evidence_dir):
            refs = passing(project, runtime, evidence_dir)
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(b"unexpected original")
            return refs

        with self.assertRaises(contracts.ContractError) as failure:
            _reconcile(
                batch, manifest, manifest_path, apply_path, missing_path,
                output_path, smoke=mutating_smoke,
            )
        self.assertEqual(failure.exception.code, "state-conflict")
        self.assertEqual(backup.read_bytes(), b"unexpected original")
        self.assertFalse(output_path.exists())
        self.assertFalse(missing_path.exists())

    def test_retry_smoke_cannot_recreate_the_missing_historical_receipt(self):
        from sbtd_graft_deployment import execute_migration_deployment

        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        _reconcile(batch, manifest, manifest_path, apply_path, missing_path, output_path)
        retry_path = batch.evidence / "deployment-retry.json"
        passing = _synthetic_smoke(manifest)

        def late_receipt(project, runtime, evidence_dir):
            refs = passing(project, runtime, evidence_dir)
            missing_path.write_bytes(b"late historical receipt")
            return refs

        with mock.patch.dict(os.environ, batch.environment):
            context = load_deployment_context(
                manifest_path, apply_path, retry_path, previous_path=output_path,
                mode="init", roots=[batch.root], hooks_authorized=False,
            )
            with (
                mock.patch("sbtd_graft_deployment.verified_runtime",
                           return_value=dict(approved._RUNTIME)),
                mock.patch("sbtd_graft_deployment.run_project_smoke",
                           side_effect=late_receipt),
            ):
                result, code = execute_migration_deployment(context)
        self.assertNotEqual(code, 0, result)
        self.assertFalse(retry_path.exists())
        self.assertEqual(missing_path.read_bytes(), b"late historical receipt")

    def test_deployment_drift_after_context_validation_prevents_publication(self):
        import sbtd_migration

        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        before = batch.agents.read_bytes()
        late_content = before + b"\nConcurrent operator change after validation.\n"
        validate_context = sbtd_migration._validate_context

        def change_after_real_validation(*args, **kwargs):
            result = validate_context(*args, **kwargs)
            batch.agents.write_bytes(late_content)
            return result

        with (
            mock.patch(
                "sbtd_migration._validate_context",
                side_effect=change_after_real_validation,
            ),
            self.assertRaises(contracts.ContractError) as failure,
        ):
            _reconcile(
                batch, manifest, manifest_path, apply_path, missing_path, output_path
            )
        self.assertEqual(failure.exception.code, "state-conflict")
        self.assertEqual(batch.agents.read_bytes(), late_content)
        self.assertFalse(output_path.exists())
        self.assertFalse(missing_path.exists())

    def test_report_drift_after_context_validation_prevents_publication(self):
        import sbtd_migration

        damaged_bytes = b"Concurrent report replacement.\n"

        for change in ("modify", "delete"):
            with self.subTest(change=change):
                batch, manifest, manifest_path, apply_path, missing_path = (
                    _interrupted_deployment(self)
                )
                output_path = batch.evidence / "current-state-evidence.json"
                validate_context = sbtd_migration._validate_context
                changed_report = []

                def change_after_real_validation(
                    *args, change=change, validate=validate_context,
                    changed=changed_report, **kwargs
                ):
                    result = validate(*args, **kwargs)
                    reference = kwargs["deployment"]["payload"]["projects"][0]["report_refs"][0]
                    report = Path(reference["path"])
                    if change == "modify":
                        report.write_bytes(damaged_bytes)
                    else:
                        report.unlink()
                    changed.append(report)
                    return result

                with (
                    mock.patch(
                        "sbtd_migration._validate_context",
                        side_effect=change_after_real_validation,
                    ),
                    self.assertRaises(contracts.ContractError) as failure,
                ):
                    _reconcile(
                        batch, manifest, manifest_path, apply_path, missing_path, output_path
                    )
                self.assertEqual(failure.exception.code, "state-conflict")
                if change == "modify":
                    self.assertEqual(changed_report[0].read_bytes(), damaged_bytes)
                else:
                    self.assertFalse(changed_report[0].exists())
                self.assertFalse(output_path.exists())
                self.assertFalse(missing_path.exists())


class CurrentStateProvenanceBindingTests(unittest.TestCase):
    """Public verify must reject resealed evidence carrying false provenance.

    Regression coverage for the deferred RC1 findings RC1-P2-PROVENANCE-PATH
    and RC1-P2-OBSERVER-RUNTIME: a resealed record whose cited input path no
    longer resolves to the recorded bytes, or whose observer Onboard runtime
    fingerprint was swapped for another format-valid value, must not verify.
    """

    def setUp(self):
        # Provenance binding covers cited input documents, not skill dirs.
        _focused_installation_templates(self)

    def test_equivalent_existing_source_references_still_verify(self):
        # Provenance binds safe objects and exact bytes, not the caller's argv
        # spelling: intact copies remain valid cited sources.
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        _reconcile(batch, manifest, manifest_path, apply_path, missing_path, output_path)
        copies = {}
        for ref_key, source in (
            ("manifest_ref", manifest_path), ("apply_receipt_ref", apply_path)
        ):
            copied = batch.evidence / f"preserved-{ref_key}.json"
            copied.write_bytes(source.read_bytes())
            copies[ref_key] = copied

        def cite_copies(payload):
            for ref_key, copied in copies.items():
                payload["reconciliation"][ref_key]["path"] = str(copied)

        _reseal_deployment_evidence(output_path, cite_copies)

        with mock.patch.dict(os.environ, batch.environment):
            verified, verify_code = verify_migration(
                manifest_path, apply_path, output_path
            )
        self.assertEqual(verify_code, 0, verified)
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(
            verified["migration"]["verification"]["payload"]["acceptance_basis"],
            "current-state",
        )
        self.assertFalse(missing_path.exists())

    def test_signed_successor_can_reconcile_and_verify_predecessor(self):
        import sbtd_migration as migration
        from tests.test_sbtd_reconciliation_followup import _signed_lineage

        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        sealed = manifest["payload"]["tool_versions"]
        observer = {**sealed, "onboard": "runtime-sha256:" + "a" * 64}
        self.assertNotEqual(observer, sealed)
        public_path, pair_path = _signed_lineage(
            batch.evidence, sealed["onboard"], observer["onboard"]
        )
        output_path = batch.evidence / "successor-observation.json"
        with (
            mock.patch.object(migration, "_LINEAGE_PUBLIC_KEY", public_path),
            mock.patch.object(migration, "_LINEAGE_DOCUMENT", pair_path),
            mock.patch.object(migration, "runtime_versions", return_value=observer),
            mock.patch.dict(os.environ, batch.environment),
        ):
            _reconcile(batch, manifest, manifest_path, apply_path, missing_path, output_path)
            verified, code = verify_migration(manifest_path, apply_path, output_path)
        self.assertEqual(code, 0, verified)
        self.assertEqual(verified["status"], "verified")
        evidence = json.loads(output_path.read_bytes())
        self.assertEqual(evidence["payload"]["reconciliation"]["runtime_versions"], observer)
        self.assertEqual(
            verified["migration"]["verification"]["payload"]["acceptance_basis"],
            "current-state",
        )

    def test_forged_manifest_ref_path_fails_verification(self):
        self._assert_forged_ref_path_rejected("manifest_ref")

    def test_forged_apply_receipt_ref_path_fails_verification(self):
        self._assert_forged_ref_path_rejected("apply_receipt_ref")

    def _assert_forged_ref_path_rejected(self, ref_key):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        _reconcile(batch, manifest, manifest_path, apply_path, missing_path, output_path)
        genuine = manifest_path if ref_key == "manifest_ref" else apply_path
        wrong_bytes = batch.evidence / f"decoy-{ref_key}.json"
        wrong_bytes.write_bytes(b'{"decoy": true}\n')
        linked = batch.evidence / f"linked-{ref_key}.json"
        linked.symlink_to(genuine)
        manifest_before = manifest_path.read_bytes()
        apply_before = apply_path.read_bytes()

        for name, forged_path in (
            ("nonexistent path", batch.evidence / f"absent-{ref_key}.json"),
            ("existing bytes of another object", wrong_bytes),
            ("existing directory", batch.evidence),
            ("symlink to the genuine input", linked),
        ):
            with self.subTest(ref=ref_key, case=name):
                # Only the cited path changes; the recorded state still
                # describes the genuine input bytes, exactly the reseal
                # forgery the finding demonstrates.
                _reseal_deployment_evidence(
                    output_path,
                    lambda payload, key=ref_key, path=forged_path: payload[
                        "reconciliation"
                    ][key].update({"path": str(path)}),
                )
                forged = output_path.read_bytes()
                evidence_before = _tree_bytes(batch.evidence)
                with (
                    mock.patch.dict(os.environ, batch.environment),
                    self.assertRaises(contracts.ContractError),
                ):
                    verify_migration(manifest_path, apply_path, output_path)
                # Rejection is read-only: forged evidence stays as submitted,
                # inputs are untouched, and nothing is written anywhere.
                self.assertEqual(output_path.read_bytes(), forged)
                self.assertEqual(_tree_bytes(batch.evidence), evidence_before)
                self.assertEqual(manifest_path.read_bytes(), manifest_before)
                self.assertEqual(apply_path.read_bytes(), apply_before)
                self.assertFalse(missing_path.exists())

    def test_foreign_observer_runtime_fails_verification(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        _reconcile(batch, manifest, manifest_path, apply_path, missing_path, output_path)

        # Same-runtime baseline: the genuine record verifies before forgery.
        with mock.patch.dict(os.environ, batch.environment):
            verified, verify_code = verify_migration(
                manifest_path, apply_path, output_path
            )
        self.assertEqual(verify_code, 0, verified)
        self.assertEqual(verified["status"], "verified")

        runtime = json.loads(output_path.read_bytes())["payload"]["reconciliation"][
            "runtime_versions"
        ]
        foreign = "runtime-sha256:" + hashlib.sha256(
            b"foreign observer runtime\n"
        ).hexdigest()
        self.assertNotEqual(foreign, runtime["onboard"])

        # Swap only the observer Onboard fingerprint for another format-valid
        # value; the pinned Graft version and every input stay genuine.
        _reseal_deployment_evidence(
            output_path,
            lambda payload: payload["reconciliation"]["runtime_versions"].update(
                {"onboard": foreign}
            ),
        )
        forged = output_path.read_bytes()
        manifest_before = manifest_path.read_bytes()
        apply_before = apply_path.read_bytes()
        with (
            mock.patch.dict(os.environ, batch.environment),
            self.assertRaises(contracts.ContractError),
        ):
            verify_migration(manifest_path, apply_path, output_path)
        self.assertEqual(output_path.read_bytes(), forged)
        self.assertEqual(manifest_path.read_bytes(), manifest_before)
        self.assertEqual(apply_path.read_bytes(), apply_before)
        self.assertFalse(missing_path.exists())


class CurrentStateProvenanceRecheckTests(unittest.TestCase):
    """Late cited-source drift must defeat acceptance at every consumer.

    Regression coverage for finding 4236584341 (P1): the cited manifest/apply
    source copies can change or vanish AFTER the initial provenance gate,
    while the consumer is still inspecting reports and targets. Verify must
    recheck the cited sources immediately before returning; cleanup must
    recheck after the full preflight (before the first resource write) and
    again after receipt contract processing (before publication). Every case
    drives the real consumer with a call-real-first wrapper on one internal
    seam: the genuine validator runs to completion, then the drift lands.
    Nothing mocks a success path, the provenance guard, or a saved receipt.

    Cited inputs are intact private COPIES (honestly resealed, exactly as the
    still-verify binding test allows), so late drift invalidates only the
    cited-source recheck — never the argv spelling or the raw input documents
    already bound at the initial gate.

    Recovery follows the same discipline (discussion_r4237001536): apply must
    recheck after the full preflight, before the first step write, and again
    after result processing, before publication — a stale recheck there still
    persists every genuinely measured step outcome, completed id and
    protection object in a non-success cumulative receipt, never reporting
    restored/already-complete. The read-only recovery plan and reconcile
    consumers recheck once more before any accepted artifact is returned or
    saved, and a reappearing historical receipt is stale provenance too.
    """

    def setUp(self):
        # Cited-source recheck invariants bind private document copies; every
        # drift subcase and real consumer call stays exactly as declared.
        _focused_installation_templates(self)

    def test_verify_rechecks_cited_sources_after_report_inspection(self):
        import sbtd_migration_verify as verify_module

        damaged = b'{"late cited source drift": true}\n'
        real_reports = verify_module.validate_deployment_reports
        for ref_key in ("manifest_ref", "apply_receipt_ref"):
            for change in ("modify", "delete"):
                with self.subTest(ref=ref_key, change=change):
                    (
                        batch,
                        manifest_path,
                        apply_path,
                        missing_path,
                        output_path,
                        copies,
                    ) = _reconciled_batch_citing_copied_inputs(self)
                    cited = copies[ref_key]
                    manifest_before = manifest_path.read_bytes()
                    apply_before = apply_path.read_bytes()
                    evidence_before = output_path.read_bytes()
                    names_before = set(os.listdir(batch.evidence))

                    def drift_after_real_reports(*args, cited=cited, change=change, **kwargs):
                        # The real report validator genuinely accepts first;
                        # only then does the cited source copy drift.
                        result = real_reports(*args, **kwargs)
                        _drift_cited_copy(cited, change, damaged)
                        return result

                    with (
                        mock.patch.dict(os.environ, batch.environment),
                        mock.patch.object(
                            verify_module,
                            "validate_deployment_reports",
                            side_effect=drift_after_real_reports,
                        ),
                        self.assertRaises(contracts.ContractError) as failure,
                    ):
                        verify_migration(manifest_path, apply_path, output_path)
                    self.assertEqual(failure.exception.code, "state-conflict")
                    # No verified envelope exists; the late drift is preserved
                    # exactly as the concurrent change left it, no input is
                    # repaired or rewritten, and verify stays read-only.
                    if change == "modify":
                        self.assertEqual(cited.read_bytes(), damaged)
                        self.assertEqual(
                            set(os.listdir(batch.evidence)), names_before
                        )
                    else:
                        self.assertFalse(cited.exists())
                        self.assertEqual(
                            set(os.listdir(batch.evidence)),
                            names_before - {cited.name},
                        )
                    self.assertEqual(manifest_path.read_bytes(), manifest_before)
                    self.assertEqual(apply_path.read_bytes(), apply_before)
                    self.assertEqual(output_path.read_bytes(), evidence_before)
                    self.assertFalse(missing_path.exists())

    def test_cleanup_rechecks_cited_sources_after_preflight_before_any_write(self):
        import sbtd_migration as migration

        damaged = b'{"late cited source drift": true}\n'
        real_groups = migration._groups
        real_cleanup_resource = migration._cleanup_resource
        for ref_key, change in (
            ("manifest_ref", "modify"),
            ("apply_receipt_ref", "delete"),
        ):
            with self.subTest(ref=ref_key, change=change):
                (
                    batch,
                    manifest_path,
                    apply_path,
                    missing_path,
                    output_path,
                    copies,
                    verification,
                    verification_path,
                ) = _verified_batch_citing_copied_inputs(self)
                cited = copies[ref_key]
                root_before = _tree_bytes(batch.root)
                vault_before = _tree_bytes(batch.vault)
                names_before = set(os.listdir(batch.evidence))
                writes = []

                def drift_after_real_groups(manifest_document, phase, *, cited=cited, change=change):
                    # Real preflight grouping completes; the cited source copy
                    # drifts only afterwards, still inside the preflight
                    # window that follows the initial provenance gate.
                    groups = real_groups(manifest_document, phase)
                    if phase == "cleanup":
                        _drift_cited_copy(cited, change, damaged)
                    return groups

                def recording_cleanup_resource(*args, writes=writes, **kwargs):
                    writes.append(args)
                    return real_cleanup_resource(*args, **kwargs)

                with (
                    mock.patch.dict(os.environ, batch.environment),
                    _fake_vendor_adapter(),
                    mock.patch.object(
                        migration, "_groups", side_effect=drift_after_real_groups
                    ),
                    mock.patch.object(
                        migration,
                        "_cleanup_resource",
                        side_effect=recording_cleanup_resource,
                    ),
                    self.assertRaises(contracts.ContractError) as failure,
                ):
                    migration.cleanup_migration(
                        manifest_path,
                        apply_path,
                        output_path,
                        verification_path,
                        confirm_cleanup=verification["verification_id"],
                    )
                self.assertEqual(failure.exception.code, "state-conflict")
                # The refusal lands after the full genuine preflight yet
                # before the first resource write: no target, backup or
                # receipt is touched, and the drifted copy is preserved.
                self.assertEqual(writes, [])
                self.assertEqual(_tree_bytes(batch.root), root_before)
                self.assertEqual(_tree_bytes(batch.vault), vault_before)
                self.assertEqual(list(batch.evidence.glob("cleanup-*.json")), [])
                if change == "modify":
                    self.assertEqual(cited.read_bytes(), damaged)
                    self.assertEqual(set(os.listdir(batch.evidence)), names_before)
                else:
                    self.assertFalse(cited.exists())
                    self.assertEqual(
                        set(os.listdir(batch.evidence)), names_before - {cited.name}
                    )
                self.assertFalse(missing_path.exists())

    def test_cleanup_recheck_failure_preserves_measured_results(self):
        import sbtd_migration as migration

        damaged = b'{"late cited source drift": true}\n'
        real_cleanup_projects = migration._cleanup_projects
        for ref_key, change in (
            ("manifest_ref", "modify"),
            ("apply_receipt_ref", "delete"),
        ):
            with self.subTest(ref=ref_key, change=change):
                (
                    batch,
                    manifest_path,
                    apply_path,
                    missing_path,
                    output_path,
                    copies,
                    verification,
                    verification_path,
                ) = _verified_batch_citing_copied_inputs(self)
                cited = copies[ref_key]
                legacy_tree = batch.root / ".trellis"
                self.assertTrue(legacy_tree.is_dir())
                manifest_before = manifest_path.read_bytes()
                apply_before = apply_path.read_bytes()
                evidence_before = output_path.read_bytes()

                def drift_after_real_projects(*args, cited=cited, change=change, **kwargs):
                    # Real cleanup already measured every resource outcome;
                    # the cited source copy drifts only afterwards, before
                    # the receipt is published.
                    projects = real_cleanup_projects(*args, **kwargs)
                    _drift_cited_copy(cited, change, damaged)
                    return projects

                with (
                    mock.patch.dict(os.environ, batch.environment),
                    _fake_vendor_adapter(),
                    mock.patch.object(
                        migration,
                        "_cleanup_projects",
                        side_effect=drift_after_real_projects,
                    ),
                ):
                    envelope, code = migration.cleanup_migration(
                        manifest_path,
                        apply_path,
                        output_path,
                        verification_path,
                        confirm_cleanup=verification["verification_id"],
                    )
                # The resources were genuinely cleaned, then the final
                # provenance recheck failed: the batch can never claim
                # cleaned/already-complete, and the measured results are
                # retained in a truthful blocked/failed cumulative receipt.
                self.assertNotEqual(code, 0, envelope)
                self.assertNotIn(
                    envelope["status"], ("cleaned", "already-complete")
                )
                self.assertIn(envelope["status"], ("blocked", "failed"))
                receipt = envelope["migration"]["cleanup_receipt"]
                self.assertIn(receipt["payload"]["status"], ("blocked", "failed"))
                for project in receipt["payload"]["projects"]:
                    self.assertIn(project["status"], ("blocked", "failed"))
                saved = list(batch.evidence.glob("cleanup-*.json"))
                self.assertEqual(len(saved), 1)
                saved_receipt = json.loads(saved[0].read_bytes())
                self.assertEqual(saved_receipt["cleanup_id"], receipt["cleanup_id"])
                results = _stage_results(saved[0])
                succeeded = [
                    result
                    for result in results.values()
                    if result["status"] == "succeeded"
                ]
                self.assertTrue(succeeded)
                self.assertIn(
                    {"type": "absent", "checksum": None},
                    [result["after"] for result in succeeded],
                )
                for result in succeeded:
                    if result["backup_ref"] is not None:
                        self.assertTrue(Path(result["backup_ref"]["path"]).exists())
                # Real cleanup is neither rolled back nor repaired, and the
                # drifted copy is preserved exactly as the concurrent change
                # left it; every genuine input stays byte-identical.
                self.assertFalse(legacy_tree.exists())
                if change == "modify":
                    self.assertEqual(cited.read_bytes(), damaged)
                else:
                    self.assertFalse(cited.exists())
                self.assertEqual(manifest_path.read_bytes(), manifest_before)
                self.assertEqual(apply_path.read_bytes(), apply_before)
                self.assertEqual(output_path.read_bytes(), evidence_before)
                self.assertFalse(missing_path.exists())

    def test_reconciled_recovery_roundtrip_restores_pre_apply_state(self):
        # Control: cited copies intact and the historical receipt still
        # absent, so the guarded path still genuinely restores pre-apply.
        (
            batch,
            manifest_path,
            apply_path,
            missing_path,
            output_path,
            copies,
        ) = _reconciled_batch_citing_copied_inputs(self)
        with mock.patch.dict(os.environ, batch.environment):
            planned, plan_code = plan_recovery(
                manifest_path,
                apply_receipt_path=apply_path,
                deployment_evidence_path=output_path,
            )
        self.assertEqual(plan_code, 0, planned)
        plan = planned["recovery"]["plan"]
        steps = plan["payload"]["steps"]
        self.assertTrue(steps)
        plan_path = batch.evidence / "recovery-plan.json"
        save_document(plan_path, plan, private_root=batch.evidence)

        with mock.patch.dict(os.environ, batch.environment):
            restored, recovery_code = apply_recovery(
                plan_path, confirm_recovery=plan["plan_id"]
            )
        self.assertEqual(recovery_code, 0, restored)
        self.assertEqual(restored["status"], "restored")
        receipt = restored["recovery"]["receipt"]
        self.assertEqual(receipt["payload"]["status"], "restored")
        self.assertEqual(
            receipt["payload"]["completed_step_ids"],
            sorted(step["step_id"] for step in steps),
        )
        self.assertEqual(receipt["payload"]["pending_step_ids"], [])
        self.assertEqual(batch.agents.read_bytes(), batch.foreign)
        saved = [
            path
            for path in batch.evidence.glob("recovery-*.json")
            if path != plan_path
        ]
        self.assertEqual(len(saved), 1)
        self.assertEqual(
            json.loads(saved[0].read_bytes())["receipt_id"],
            receipt["receipt_id"],
        )
        self.assertEqual(
            copies["manifest_ref"].read_bytes(), manifest_path.read_bytes()
        )
        self.assertEqual(
            copies["apply_receipt_ref"].read_bytes(), apply_path.read_bytes()
        )
        self.assertFalse(missing_path.exists())

    def test_recovery_rechecks_provenance_after_preflight_before_any_write(self):
        import sbtd_recovery

        damaged = b'{"late cited source drift": true}\n'
        reappeared = b'{"late_historical_evidence": true}\n'
        real_validate_context = sbtd_recovery._validate_context
        real_execute_step = sbtd_recovery._execute_step
        for ref_key, change in (
            ("manifest_ref", "modify"),
            ("manifest_ref", "delete"),
            ("apply_receipt_ref", "modify"),
            ("apply_receipt_ref", "delete"),
            ("missing_deployment_evidence", "reappear"),
        ):
            with self.subTest(ref=ref_key, change=change):
                (
                    batch,
                    manifest_path,
                    apply_path,
                    missing_path,
                    output_path,
                    copies,
                ) = _reconciled_batch_citing_copied_inputs(self)
                cited = copies.get(ref_key)
                with mock.patch.dict(os.environ, batch.environment):
                    planned, plan_code = plan_recovery(
                        manifest_path,
                        apply_receipt_path=apply_path,
                        deployment_evidence_path=output_path,
                    )
                self.assertEqual(plan_code, 0, planned)
                plan = planned["recovery"]["plan"]
                plan_path = batch.evidence / "recovery-plan.json"
                save_document(plan_path, plan, private_root=batch.evidence)
                root_before = _tree_bytes(batch.root)
                home_before = _tree_bytes(batch.home)
                vault_before = _tree_bytes(batch.vault)
                manifest_before = manifest_path.read_bytes()
                apply_before = apply_path.read_bytes()
                evidence_before = output_path.read_bytes()
                names_before = set(os.listdir(batch.evidence))
                writes = []

                def drift_after_real_validation(
                    *args, cited=cited, change=change, missing=missing_path, **kwargs
                ):
                    # The real full-context preflight genuinely accepts first;
                    # the cited source copy drifts, or the historical receipt
                    # reappears, only afterwards — inside the window before
                    # the first recovery write.
                    result = real_validate_context(*args, **kwargs)
                    if change == "reappear":
                        missing.write_bytes(reappeared)
                    else:
                        _drift_cited_copy(cited, change, damaged)
                    return result

                def recording_execute_step(*args, writes=writes, **kwargs):
                    writes.append(args)
                    return real_execute_step(*args, **kwargs)

                with (
                    mock.patch.dict(os.environ, batch.environment),
                    mock.patch.object(
                        sbtd_recovery,
                        "_validate_context",
                        side_effect=drift_after_real_validation,
                    ),
                    mock.patch.object(
                        sbtd_recovery,
                        "_execute_step",
                        side_effect=recording_execute_step,
                    ),
                    self.assertRaises(contracts.ContractError) as failure,
                ):
                    apply_recovery(plan_path, confirm_recovery=plan["plan_id"])
                self.assertEqual(failure.exception.code, "state-conflict")
                # The refusal lands after the full genuine preflight yet
                # before the first recovery write: no step ran, no target,
                # backup, protection object or receipt is touched, and the
                # concurrent change is preserved exactly as it landed.
                self.assertEqual(writes, [])
                self.assertEqual(_tree_bytes(batch.root), root_before)
                self.assertEqual(_tree_bytes(batch.home), home_before)
                self.assertEqual(_tree_bytes(batch.vault), vault_before)
                if change == "modify":
                    self.assertEqual(cited.read_bytes(), damaged)
                    self.assertEqual(set(os.listdir(batch.evidence)), names_before)
                elif change == "delete":
                    self.assertFalse(cited.exists())
                    self.assertEqual(
                        set(os.listdir(batch.evidence)),
                        names_before - {cited.name},
                    )
                else:
                    self.assertEqual(missing_path.read_bytes(), reappeared)
                    self.assertEqual(
                        set(os.listdir(batch.evidence)),
                        names_before | {missing_path.name},
                    )
                self.assertEqual(manifest_path.read_bytes(), manifest_before)
                self.assertEqual(apply_path.read_bytes(), apply_before)
                self.assertEqual(output_path.read_bytes(), evidence_before)

    def test_recovery_recheck_failure_preserves_measured_results(self):
        import sbtd_recovery

        damaged = b'{"late cited source drift": true}\n'
        reappeared = b'{"late_historical_evidence": true}\n'
        real_projects = sbtd_recovery._recovery_projects
        for ref_key, change in (
            ("manifest_ref", "modify"),
            ("manifest_ref", "delete"),
            ("apply_receipt_ref", "modify"),
            ("apply_receipt_ref", "delete"),
            ("missing_deployment_evidence", "reappear"),
        ):
            with self.subTest(ref=ref_key, change=change):
                (
                    batch,
                    manifest_path,
                    apply_path,
                    missing_path,
                    output_path,
                    copies,
                ) = _reconciled_batch_citing_copied_inputs(self)
                cited = copies.get(ref_key)
                with mock.patch.dict(os.environ, batch.environment):
                    planned, plan_code = plan_recovery(
                        manifest_path,
                        apply_receipt_path=apply_path,
                        deployment_evidence_path=output_path,
                    )
                self.assertEqual(plan_code, 0, planned)
                plan = planned["recovery"]["plan"]
                steps = plan["payload"]["steps"]
                self.assertTrue(steps)
                plan_path = batch.evidence / "recovery-plan.json"
                save_document(plan_path, plan, private_root=batch.evidence)
                manifest_before = manifest_path.read_bytes()
                apply_before = apply_path.read_bytes()
                evidence_before = output_path.read_bytes()

                def drift_after_real_projects(
                    *args, cited=cited, change=change, missing=missing_path, **kwargs
                ):
                    # Real recovery already executed and measured every step
                    # outcome; the cited source copy drifts, or the historical
                    # receipt reappears, only afterwards — before publication.
                    projects = real_projects(*args, **kwargs)
                    if change == "reappear":
                        missing.write_bytes(reappeared)
                    else:
                        _drift_cited_copy(cited, change, damaged)
                    return projects

                with (
                    mock.patch.dict(os.environ, batch.environment),
                    mock.patch.object(
                        sbtd_recovery,
                        "_recovery_projects",
                        side_effect=drift_after_real_projects,
                    ),
                ):
                    envelope, code = apply_recovery(
                        plan_path, confirm_recovery=plan["plan_id"]
                    )
                # Every step genuinely restored, then the final provenance
                # recheck failed: the batch can never claim restored or
                # already-complete, and the measured results are retained in
                # a truthful blocked/failed cumulative receipt.
                self.assertNotEqual(code, 0, envelope)
                self.assertNotIn(
                    envelope["status"], ("restored", "already-complete")
                )
                self.assertIn(envelope["status"], ("blocked", "failed"))
                receipt = envelope["recovery"]["receipt"]
                self.assertIn(receipt["payload"]["status"], ("blocked", "failed"))
                for project in receipt["payload"]["projects"]:
                    self.assertIn(project["status"], ("blocked", "failed"))
                saved = [
                    path
                    for path in batch.evidence.glob("recovery-*.json")
                    if path != plan_path
                ]
                self.assertEqual(len(saved), 1)
                saved_receipt = json.loads(saved[0].read_bytes())
                self.assertEqual(saved_receipt["receipt_id"], receipt["receipt_id"])
                completed = receipt["payload"]["completed_step_ids"]
                self.assertEqual(
                    completed, sorted(step["step_id"] for step in steps)
                )
                self.assertEqual(receipt["payload"]["pending_step_ids"], [])
                restore_to = {step["step_id"]: step["restore_to"] for step in steps}
                targets = {
                    resource["resource_id"]: resource["target"]
                    for resource in plan["payload"]["resources"]
                }
                results = {
                    result["step_id"]: result
                    for result in receipt["payload"]["results"]
                }
                self.assertEqual(sorted(results), completed)
                protections = []
                for step_id in completed:
                    result = results[step_id]
                    self.assertEqual(result["status"], "succeeded")
                    self.assertEqual(result["after"], restore_to[step_id])
                    if result["protection_ref"] is not None:
                        protections.append(result["protection_ref"])
                # A later inverse step may supersede an earlier after-state
                # for the same resource. Only the final planned state is live.
                final_states = {
                    step["resource_id"]: step["restore_to"] for step in steps
                }
                for resource_id, expected in final_states.items():
                    self.assertEqual(snapshot(Path(targets[resource_id])), expected)
                self.assertTrue(protections)
                for protection in protections:
                    self.assertEqual(
                        snapshot(Path(protection["path"])), protection["state"]
                    )
                # The restoration is neither rolled back nor repaired, and the
                # concurrent change is preserved exactly as it landed; every
                # genuine input stays byte-identical.
                self.assertEqual(batch.agents.read_bytes(), batch.foreign)
                if change == "modify":
                    self.assertEqual(cited.read_bytes(), damaged)
                elif change == "delete":
                    self.assertFalse(cited.exists())
                else:
                    self.assertEqual(missing_path.read_bytes(), reappeared)
                self.assertEqual(manifest_path.read_bytes(), manifest_before)
                self.assertEqual(apply_path.read_bytes(), apply_before)
                self.assertEqual(output_path.read_bytes(), evidence_before)

    def test_recovery_plan_rechecks_cited_sources_before_accepted_return(self):
        import sbtd_recovery

        damaged = b'{"late cited source drift": true}\n'
        real_validate_context = sbtd_recovery._validate_context
        for ref_key, change in (
            ("manifest_ref", "modify"),
            ("apply_receipt_ref", "delete"),
        ):
            with self.subTest(ref=ref_key, change=change):
                (
                    batch,
                    manifest_path,
                    apply_path,
                    missing_path,
                    output_path,
                    copies,
                ) = _reconciled_batch_citing_copied_inputs(self)
                cited = copies[ref_key]
                names_before = set(os.listdir(batch.evidence))
                manifest_before = manifest_path.read_bytes()
                apply_before = apply_path.read_bytes()

                def drift_after_real_validation(
                    *args, cited=cited, change=change, **kwargs
                ):
                    # The real context validation genuinely accepts first;
                    # the cited source copy drifts only afterwards, inside
                    # the read-only planning window.
                    result = real_validate_context(*args, **kwargs)
                    _drift_cited_copy(cited, change, damaged)
                    return result

                with (
                    mock.patch.dict(os.environ, batch.environment),
                    mock.patch.object(
                        sbtd_recovery,
                        "_validate_context",
                        side_effect=drift_after_real_validation,
                    ),
                    self.assertRaises(contracts.ContractError) as failure,
                ):
                    plan_recovery(
                        manifest_path,
                        apply_receipt_path=apply_path,
                        deployment_evidence_path=output_path,
                    )
                self.assertEqual(failure.exception.code, "state-conflict")
                # Planning stays read-only: no accepted plan envelope, no new
                # private object, genuine inputs byte-identical, and the
                # drifted copy is preserved as the concurrent change left it.
                if change == "modify":
                    self.assertEqual(cited.read_bytes(), damaged)
                    self.assertEqual(set(os.listdir(batch.evidence)), names_before)
                else:
                    self.assertFalse(cited.exists())
                    self.assertEqual(
                        set(os.listdir(batch.evidence)),
                        names_before - {cited.name},
                    )
                self.assertEqual(manifest_path.read_bytes(), manifest_before)
                self.assertEqual(apply_path.read_bytes(), apply_before)
                self.assertFalse(missing_path.exists())

    def test_reconcile_rechecks_cited_manifest_bytes_before_save(self):
        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        manifest_before = manifest_path.read_bytes()
        apply_before = apply_path.read_bytes()
        damaged = manifest_before + b'\n{"late cited source drift": true}\n'
        real_validate_result = contracts.validate_deployment_result

        def drift_after_real_result(*args, **kwargs):
            # The real result validator genuinely accepts first; the cited
            # manifest bytes drift only afterwards — after every earlier
            # input guard and before the single evidence write.
            result = real_validate_result(*args, **kwargs)
            manifest_path.write_bytes(damaged)
            return result

        patches = _native_doubles(manifest)
        with (
            mock.patch.dict(os.environ, batch.environment),
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            mock.patch.object(
                contracts,
                "validate_deployment_result",
                side_effect=drift_after_real_result,
            ),
            self.assertRaises(contracts.ContractError) as failure,
        ):
            reconcile_deployment(
                manifest_path,
                apply_path,
                missing_path,
                output_path,
                confirmed=True,
            )
        self.assertEqual(failure.exception.code, "state-conflict")
        # No accepted evidence exists; the late drift is preserved exactly as
        # the concurrent change left it and the apply receipt is untouched.
        self.assertFalse(output_path.exists())
        self.assertFalse(missing_path.exists())
        self.assertEqual(manifest_path.read_bytes(), damaged)
        self.assertEqual(apply_path.read_bytes(), apply_before)


class CurrentStateFinalSnapshotTests(unittest.TestCase):
    def setUp(self):
        # Late-artifact drift targets are the project file, its file backup
        # and the project report; none is a sibling skill directory.
        _focused_installation_templates(self)

    def test_reconcile_rechecks_artifacts_after_provenance_validation(self):
        for artifact in ("target", "original", "report"):
            with self.subTest(artifact=artifact):
                self._assert_late_artifact_rejected("reconcile", artifact)

    def test_verify_rechecks_artifacts_after_provenance_validation(self):
        for artifact in ("target", "original", "report"):
            with self.subTest(artifact=artifact):
                self._assert_late_artifact_rejected("verify", artifact)

    def _assert_late_artifact_rejected(self, consumer, artifact):
        import sbtd_migration as migration

        batch, manifest, manifest_path, apply_path, missing_path = (
            _interrupted_deployment(self)
        )
        output_path = batch.evidence / "current-state-evidence.json"
        if consumer == "verify":
            _reconcile(batch, manifest, manifest_path, apply_path, missing_path, output_path)
        input_bytes = {path: path.read_bytes() for path in (manifest_path, apply_path)}
        evidence_bytes = output_path.read_bytes() if output_path.exists() else None
        real_context = migration._validate_context
        real_provenance = migration._require_reconciliation_provenance
        context_complete = False
        changed = None

        def complete_real_context(*args, **kwargs):
            nonlocal context_complete
            result = real_context(*args, **kwargs)
            context_complete = True
            return result

        def drift_after_real_provenance(manifest_document, deployment_document, **kwargs):
            nonlocal changed
            references = real_provenance(manifest_document, deployment_document, **kwargs)
            if context_complete and changed is None:
                if artifact == "target":
                    path = batch.agents
                elif artifact == "original":
                    reference = next(
                        row["backup_ref"]
                        for row in migration._result_index(deployment_document).values()
                        if row["backup_ref"] is not None
                        and row["backup_ref"]["state"]["type"] == "file"
                    )
                    path = Path(reference["path"])
                else:
                    path = Path(deployment_document["payload"]["projects"][0]["report_refs"][0]["path"])
                damaged = path.read_bytes() + b"\nconcurrent artifact drift\n"
                path.write_bytes(damaged)
                changed = path, damaged
            return references

        with (
            mock.patch.dict(os.environ, batch.environment),
            mock.patch.object(migration, "_validate_context", side_effect=complete_real_context),
            mock.patch.object(
                migration, "_require_reconciliation_provenance",
                side_effect=drift_after_real_provenance,
            ),
            self.assertRaises(contracts.ContractError),
        ):
            if consumer == "reconcile":
                _reconcile(batch, manifest, manifest_path, apply_path, missing_path, output_path)
            else:
                verify_migration(manifest_path, apply_path, output_path)
        self.assertIsNotNone(changed)
        path, damaged = changed
        self.assertEqual(path.read_bytes(), damaged)
        self.assertEqual({path: path.read_bytes() for path in input_bytes}, input_bytes)
        if evidence_bytes is None:
            self.assertFalse(output_path.exists())
        else:
            self.assertEqual(output_path.read_bytes(), evidence_bytes)
        self.assertFalse(missing_path.exists())


class CurrentStateRetrySnapshotTests(unittest.TestCase):
    def setUp(self):
        # The retry result set mirrors the same manifest's evidence on both
        # sides of the equality, so catalog size never enters the invariant.
        _focused_installation_templates(self)

    def test_retry_rechecks_artifacts_after_provenance_validation(self):
        import sbtd_graft_deployment as deployment
        import sbtd_migration as migration

        for artifact in ("target", "original", "report"):
            with self.subTest(artifact=artifact):
                batch, manifest, manifest_path, apply_path, missing_path = (
                    _interrupted_deployment(self)
                )
                previous_path = batch.evidence / "current-state-evidence.json"
                _reconcile(batch, manifest, manifest_path, apply_path, missing_path, previous_path)
                previous_bytes = previous_path.read_bytes()
                output_path = batch.evidence / "retry.json"
                real_assemble = deployment._assemble_deployment_evidence
                real_provenance = migration._require_reconciliation_provenance
                stage = {"assembled": False}
                changed = []

                def after_assembly(*args, stage=stage, real_assemble=real_assemble, **kwargs):
                    document = real_assemble(*args, **kwargs)
                    stage["assembled"] = True
                    return document

                def after_provenance(
                    manifest_document, evidence, *, artifact=artifact,
                    changed=changed, agents=batch.agents, stage=stage,
                    real_provenance=real_provenance, **kwargs,
                ):
                    references = real_provenance(manifest_document, evidence, **kwargs)
                    if stage["assembled"] and not changed:
                        if artifact == "target":
                            path = agents
                        elif artifact == "original":
                            path = Path(next(
                                row["backup_ref"]["path"]
                                for row in migration._result_index(evidence).values()
                                if row["backup_ref"] is not None
                                and row["backup_ref"]["state"]["type"] == "file"
                            ))
                        else:
                            path = Path(evidence["payload"]["projects"][0]["report_refs"][0]["path"])
                        damaged = path.read_bytes() + b"\nlate retry drift\n"
                        path.write_bytes(damaged)
                        changed.append((path, damaged))
                    return references

                with (
                    mock.patch.object(deployment, "_assemble_deployment_evidence", side_effect=after_assembly),
                    mock.patch.object(migration, "_require_reconciliation_provenance", side_effect=after_provenance),
                ):
                    result, code = batch.execute(
                        manifest_path, apply_path, output_path,
                        previous_path=previous_path, rebuild_graph=False,
                    )
                self.assertEqual(code, 5, result)
                self.assertEqual(result["status"], "failed")
                self.assertIsNone(result["deploymentEvidence"])
                self.assertFalse(output_path.exists())
                self.assertEqual(previous_path.read_bytes(), previous_bytes)
                self.assertEqual(len(changed), 1)
                path, damaged = changed[0]
                self.assertEqual(path.read_bytes(), damaged)
                self.assertEqual(
                    {row["resource_id"] for row in result["operationResults"]},
                    set(migration._result_index(json.loads(previous_bytes))),
                )


if __name__ == "__main__":
    unittest.main()
