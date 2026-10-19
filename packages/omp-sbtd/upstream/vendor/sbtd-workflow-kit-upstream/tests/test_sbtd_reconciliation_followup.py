"""Followup lifecycle over a genuine reconciled predecessor chain.

The fixture first builds a real original -> successor codex deployment ->
verified cleanup predecessor (labeled smoke-only native doubles; 合成夹具，
不证明真实 host 部署。), then reseals deployment evidence with typed
current-state reconciliation provenance plus the verification/cleanup pair
bound over it. That is the genuine reconciled+verified+cleaned predecessor a
followup must consume: planning and every later consumer accept it while the
cited missing historical receipt stays absent, fail closed the moment that
path reappears, and never rewrite predecessor history. The centralized
immutable-stage iterator also keeps the absent missing path protected
against descendant evidence output.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import onboard_contracts as contracts
import sbtd_migration as migration
from onboard_contracts import ContractError, canonical_json_bytes
from sbtd_migration import _protected_followup_ancestry, apply_migration
from sbtd_migration_files import save_document, snapshot

from tests.test_sbtd_followup_batch import FollowupMigration, assert_proof_intact

ABSENT = {"type": "absent", "checksum": None}
FORGED = b"forged historical receipt\n"


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _reconciled_predecessor(
    fixture: FollowupMigration, *, observer: str | None = None,
    observer_lineage: dict | None = None,
) -> Path:
    """Reseal the completed predecessor with current-state provenance.

    Manifest and apply receipt stay byte-identical; deployment evidence gains
    the typed reconciliation record citing their exact raw bytes and one
    absent historical receipt path, and verification (current-state
    acceptance basis) and cleanup are resealed over the new deployment
    identity. Returns the cited missing path, still absent.
    """
    manifest_raw = fixture.manifest_path.read_bytes()
    apply_raw = fixture.apply_path.read_bytes()
    missing_path = fixture.evidence / "interrupted-deployment.json"
    metadata = {
        "kind": "current-state",
        "historical_execution": "unknown",
        "manifest_ref": {
            "path": str(fixture.manifest_path),
            "state": {"type": "file", "checksum": _digest(manifest_raw)},
        },
        "apply_receipt_ref": {
            "path": str(fixture.apply_path),
            "state": {"type": "file", "checksum": _digest(apply_raw)},
        },
        "missing_deployment_evidence": {
            "path": str(missing_path),
            "state": dict(ABSENT),
        },
        "runtime_versions": dict(fixture.manifest["payload"]["tool_versions"]),
    }
    if observer is not None:
        metadata["runtime_versions"]["onboard"] = observer
    if observer_lineage is not None:
        metadata["observer_lineage"] = copy.deepcopy(observer_lineage)
    deployment_payload = copy.deepcopy(fixture.deployment["payload"])
    deployment_payload["reconciliation"] = metadata
    deployment = contracts.seal_document("deployment_evidence", deployment_payload)
    deployment_digest = _digest(canonical_json_bytes(deployment))
    verification_payload = copy.deepcopy(fixture.verification["payload"])
    verification_payload["deployment_evidence_hash"] = deployment_digest
    verification_payload["acceptance_basis"] = "current-state"
    verification = contracts.seal_document("verification", verification_payload)
    cleanup_payload = copy.deepcopy(fixture.cleanup_receipt["payload"])
    cleanup_payload["verification_id"] = verification["verification_id"]
    cleanup_payload["deployment_evidence_hash"] = deployment_digest
    cleanup = contracts.seal_document("cleanup_receipt", cleanup_payload)
    fixture.deployment_path = fixture.evidence / "reconciled-deployment.json"
    fixture.verification_path = fixture.evidence / "reconciled-verification.json"
    fixture.cleanup_path = fixture.evidence / "reconciled-cleanup.json"
    save_document(fixture.deployment_path, deployment, private_root=fixture.evidence)
    save_document(
        fixture.verification_path, verification, private_root=fixture.evidence
    )
    save_document(fixture.cleanup_path, cleanup, private_root=fixture.evidence)
    fixture.deployment = deployment
    fixture.verification = verification
    fixture.cleanup_receipt = cleanup
    return missing_path


def _signed_lineage(directory: Path, predecessor: str, successor: str):
    """Real signature under an isolated test trust key, never a mocked verifier."""
    key = Ed25519PrivateKey.generate()
    public_path = directory / "lineage.pub"
    public_path.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    signed = migration._lineage_signed_bytes(predecessor, successor)
    document = json.loads(signed)
    document["signature"] = base64.b64encode(key.sign(signed)).decode("ascii")
    pair_path = directory / "lineage.json"
    pair_path.write_bytes(canonical_json_bytes(document))
    return public_path, pair_path


def _apply_followup_at(fixture: FollowupMigration, followup: dict, directory: Path):
    """Apply a followup manifest stored inside ``directory`` (private scope)."""
    manifest_path = directory / "followup-manifest.json"
    manifest_path.write_bytes(canonical_json_bytes(followup))
    with mock.patch.dict(os.environ, fixture.environment):
        applied, code = apply_migration(
            manifest_path, confirmed=True, no_routing_approvals=True
        )
    assert code == 0, applied
    receipt = applied["migration"]["apply_receipt"]
    apply_path = directory / ("apply-" + receipt["apply_id"] + ".json")
    assert apply_path.is_file()
    return manifest_path, apply_path


class ReconciledPredecessorFollowupTests(unittest.TestCase):
    def test_reconciled_predecessor_plans_and_consumes_while_missing_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            missing_path = _reconciled_predecessor(fixture)
            self.assertEqual(snapshot(missing_path), ABSENT)
            followup = fixture.plan_followup()
            # The centralized immutable-stage iterator keeps the cited missing
            # historical path inside the protected followup ancestry even
            # though the object itself stays absent.
            protected = _protected_followup_ancestry(followup)
            self.assertIn((missing_path, False), protected)
            # The whole followup chain consumes the genuine reconciled (and
            # cleaned) predecessor without revalidating its superseded live
            # after-states.
            artifacts = fixture.complete_followup(followup)
            self.assertEqual(
                artifacts["cleanup_receipt"]["payload"]["status"], "cleaned"
            )
            self.assertEqual(snapshot(missing_path), ABSENT)

    def test_followup_plan_rechecks_provenance_after_sealing(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            _reconciled_predecessor(fixture)
            proof = fixture.predecessor_proof()
            original = fixture.manifest_path.read_bytes()
            real_seal = contracts.seal_document

            def drift_after_seal(kind, payload):
                document = real_seal(kind, payload)
                if kind == "manifest" and payload.get("followup") is not None:
                    fixture.manifest_path.write_bytes(original + b"\n")
                return document

            with (
                mock.patch.object(contracts, "seal_document", side_effect=drift_after_seal),
                self.assertRaises(ContractError) as failure,
            ):
                fixture.plan_followup()
            self.assertEqual(failure.exception.code, "state-conflict")
            self.assertEqual(fixture.manifest_path.read_bytes(), original + b"\n")
            assert_proof_intact(
                self, {path: raw for path, raw in proof.items() if path != str(fixture.manifest_path)}
            )

    def test_followup_apply_rechecks_ancestor_provenance_before_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            missing = _reconciled_predecessor(fixture)
            followup = fixture.plan_followup()
            real_seal = contracts.seal_document
            before = {path: snapshot(path) for path in (fixture.root, fixture.home, fixture.vault)}

            def reveal_history_after_seal(kind, payload):
                document = real_seal(kind, payload)
                if kind == "apply_receipt" and payload["manifest_id"] == followup["manifest_id"]:
                    missing.write_bytes(FORGED)
                return document

            with (
                mock.patch.object(contracts, "seal_document", side_effect=reveal_history_after_seal),
                self.assertRaises(ContractError) as failure,
            ):
                fixture.apply_followup(followup)
            self.assertEqual(failure.exception.code, "state-conflict")
            self.assertEqual(missing.read_bytes(), FORGED)
            self.assertFalse(list(fixture.followup_evidence.glob("apply-*.json")))
            self.assertEqual({path: snapshot(path) for path in before}, before)

    def test_followup_deploy_preserves_results_when_ancestor_provenance_drifts(self):
        import sbtd_graft_deployment as deployment

        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            missing = _reconciled_predecessor(fixture)
            followup = fixture.plan_followup()
            manifest_path, apply_path = _apply_followup_at(
                fixture, followup, fixture.followup_evidence
            )
            real_assemble = deployment._assemble_deployment_evidence

            def reveal_history_after_assembly(*args, **kwargs):
                document = real_assemble(*args, **kwargs)
                missing.write_bytes(FORGED)
                return document

            with mock.patch.object(
                deployment, "_assemble_deployment_evidence",
                side_effect=reveal_history_after_assembly,
            ):
                result, code, output_path = fixture.deploy_followup(manifest_path, apply_path)
            self.assertEqual(code, 5, result)
            self.assertEqual(result["status"], "failed")
            self.assertIsNone(result["deploymentEvidence"])
            self.assertFalse(output_path.exists())
            operations = {
                operation["resource_id"]: operation
                for operation in migration._operations(followup)
                if operation["phase"] == "deploy"
            }
            results = {row["resource_id"]: row for row in result["operationResults"]}
            self.assertEqual(set(results), set(operations))
            for resource_id, row in results.items():
                self.assertEqual(row["status"], "succeeded")
                self.assertEqual(snapshot(Path(operations[resource_id]["target"])), row["after"])
            self.assertEqual(missing.read_bytes(), FORGED)

    def test_followup_planning_fails_closed_when_missing_history_reappears(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            missing_path = _reconciled_predecessor(fixture)
            proof = fixture.predecessor_proof()
            missing_path.write_bytes(FORGED)
            with self.assertRaises(ContractError) as error:
                fixture.plan_followup()
            self.assertEqual(error.exception.code, "state-conflict")
            # Fail closed without altering the reappeared file or any history.
            self.assertEqual(missing_path.read_bytes(), FORGED)
            assert_proof_intact(self, proof)

    def test_followup_consumption_fails_closed_when_missing_history_reappears(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            missing_path = _reconciled_predecessor(fixture)
            followup = fixture.plan_followup()
            manifest_path, apply_path = _apply_followup_at(
                fixture, followup, fixture.followup_evidence
            )
            proof = fixture.predecessor_proof()
            home_before = snapshot(fixture.home)
            root_before = snapshot(fixture.root)
            missing_path.write_bytes(FORGED)
            output_path = fixture.followup_evidence / "deployment.json"
            with self.assertRaises(ContractError) as error:
                fixture.execute_deployment(manifest_path, apply_path, output_path)
            self.assertEqual(error.exception.code, "state-conflict")
            self.assertFalse(output_path.exists())
            self.assertEqual(missing_path.read_bytes(), FORGED)
            self.assertEqual(snapshot(fixture.home), home_before)
            self.assertEqual(snapshot(fixture.root), root_before)
            assert_proof_intact(self, proof)

    def test_followup_output_cannot_claim_the_missing_historical_path(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            missing_path = _reconciled_predecessor(fixture)
            followup = fixture.plan_followup()
            # Storing the followup manifest beside the predecessor evidence
            # places the cited missing path inside the permitted output
            # scope; the apply stage itself is legitimate and must succeed.
            manifest_path, apply_path = _apply_followup_at(
                fixture, followup, fixture.evidence
            )
            proof = fixture.predecessor_proof()
            home_before = snapshot(fixture.home)
            root_before = snapshot(fixture.root)
            with self.assertRaises(ContractError) as error:
                fixture.execute_deployment(manifest_path, apply_path, missing_path)
            self.assertEqual(error.exception.code, "private-scope")
            self.assertIn("protected predecessor object", str(error.exception))
            # The rejection happened before any write: the historical path
            # stays absent, targets are untouched, and every predecessor
            # proof keeps its exact bytes.
            self.assertEqual(snapshot(missing_path), ABSENT)
            self.assertEqual(snapshot(fixture.home), home_before)
            self.assertEqual(snapshot(fixture.root), root_before)
            assert_proof_intact(self, proof)

    def test_signed_successor_observer_survives_historical_followup(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            fixture = FollowupMigration(base)
            fixture.build()
            predecessor = fixture.manifest["payload"]["tool_versions"]["onboard"]
            observer = "runtime-sha256:" + "a" * 64
            self.assertNotEqual(predecessor, observer)
            _reconciled_predecessor(fixture, observer=observer)
            public_path, pair_path = _signed_lineage(base, predecessor, observer)
            proof = fixture.predecessor_proof()
            with (
                mock.patch.object(migration, "_LINEAGE_PUBLIC_KEY", public_path),
                mock.patch.object(migration, "_LINEAGE_DOCUMENT", pair_path),
            ):
                # The old observer differs from this consumer; historical
                # provenance must not be compared to its current runtime.
                followup = fixture.plan_followup()
                artifacts = fixture.complete_followup(followup)
            self.assertEqual(artifacts["cleanup_receipt"]["payload"]["status"], "cleaned")
            assert_proof_intact(self, proof)

    def test_rotated_lineage_preserves_historical_followup_chain(self):
        from tests import test_sbtd_followup_batch as followup_tests
        from tests.test_sbtd_reconciliation_lineage import _installed, _LineageAuthority

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            fixture = FollowupMigration(base)
            fixture.build()
            sealed = fixture.manifest["payload"]["tool_versions"]
            observer = "runtime-sha256:" + "a" * 64
            current = {**sealed, "onboard": "runtime-sha256:" + "c" * 64}
            authority = _LineageAuthority(base)
            original_pair = authority.install(sealed["onboard"], observer)
            _reconciled_predecessor(
                fixture, observer=observer, observer_lineage=original_pair
            )
            proof = fixture.predecessor_proof()
            authority.install(observer, current["onboard"])
            with (
                _installed(authority),
                mock.patch.object(followup_tests, "runtime_versions", return_value=current),
                mock.patch.object(migration, "runtime_versions", return_value=current),
            ):
                followup = fixture.plan_followup()
                artifacts = fixture.complete_followup(followup)
            self.assertEqual(artifacts["cleanup_receipt"]["payload"]["status"], "cleaned")
            assert_proof_intact(self, proof)

    def test_historical_observer_requires_valid_forward_lineage(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            fixture = FollowupMigration(base)
            fixture.build()
            predecessor = fixture.manifest["payload"]["tool_versions"]["onboard"]
            observer = "runtime-sha256:" + "a" * 64
            unrelated = "runtime-sha256:" + "b" * 64
            _reconciled_predecessor(fixture, observer=observer)
            proof = fixture.predecessor_proof()
            for variant in ("reverse", "unrelated", "invalid-signature", "missing"):
                with self.subTest(variant=variant):
                    first, second = predecessor, observer
                    if variant == "reverse":
                        first, second = observer, predecessor
                    elif variant == "unrelated":
                        second = unrelated
                    public_path, pair_path = _signed_lineage(base, first, second)
                    if variant == "invalid-signature":
                        pair = json.loads(pair_path.read_bytes())
                        pair["signature"] = base64.b64encode(bytes(64)).decode("ascii")
                        pair_path.write_bytes(canonical_json_bytes(pair))
                    elif variant == "missing":
                        pair_path.unlink()
                    with (
                        mock.patch.object(migration, "_LINEAGE_PUBLIC_KEY", public_path),
                        mock.patch.object(migration, "_LINEAGE_DOCUMENT", pair_path),
                        self.assertRaises(ContractError) as failure,
                    ):
                        fixture.plan_followup()
                    self.assertEqual(failure.exception.code, "version-conflict")
                    assert_proof_intact(self, proof)

    def test_executed_predecessor_ancestry_has_no_missing_path(self):
        # Regular-path compatibility: without reconciliation provenance the
        # ancestry is exactly the pre-existing document/input/backup set.
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            followup = fixture.plan_followup()
            protected = _protected_followup_ancestry(followup)
            self.assertNotIn(
                (fixture.evidence / "interrupted-deployment.json", False), protected
            )


if __name__ == "__main__":
    unittest.main()
