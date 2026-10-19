"""Public contract tests for current-state reconciliation provenance.

Covers the provenance-marked deployment evidence contract and the migration
reconcile envelope: closed metadata shape and constants, exact raw manifest /
apply input binding, anti-laundering of provenance and of the verification
acceptance basis across bound chains and cumulative retries, time/status/path
semantics, and backwards compatibility for ordinary historical documents.
Native graph/report/runtime boundaries are out of scope here; these tests
exercise the public contract API only.
"""
from __future__ import annotations

import copy
import unittest

from tests import onboard_contract_fixtures as fixtures

contracts = fixtures.contracts
ContractError = contracts.ContractError

MANIFEST_PATH = f"{fixtures.EVIDENCE_DIR}/manifest.json"
APPLY_PATH = f"{fixtures.EVIDENCE_DIR}/apply_receipt.json"
MISSING_PATH = f"{fixtures.EVIDENCE_DIR}/interrupted-deployment.json"
OUTPUT_PATH = f"{fixtures.EVIDENCE_DIR}/current-state-evidence.json"
ONBOARD_SHA = f"runtime-sha256:{fixtures.digest_number(900)}"
GRAFT_PIN = "1.0.0"


def reseal(kind: str, document: dict, mutate) -> dict:
    payload = copy.deepcopy(document["payload"])
    mutate(payload)
    return contracts.seal_document(kind, payload)


def reconciliation_metadata(manifest: dict, apply_receipt: dict) -> dict:
    return {
        "kind": "current-state",
        "historical_execution": "unknown",
        "manifest_ref": {
            "path": MANIFEST_PATH,
            "state": {"type": "file", "checksum": fixtures.raw_digest_of(manifest)},
        },
        "apply_receipt_ref": {
            "path": APPLY_PATH,
            "state": {
                "type": "file",
                "checksum": fixtures.raw_digest_of(apply_receipt),
            },
        },
        "missing_deployment_evidence": {
            "path": MISSING_PATH,
            "state": dict(fixtures.ABSENT),
        },
        "runtime_versions": {"onboard": ONBOARD_SHA, "graft": GRAFT_PIN},
    }


def reconciled_evidence(manifest: dict, apply_receipt: dict) -> dict:
    payload = fixtures.build_deployment_evidence_payload(manifest, apply_receipt)
    payload["reconciliation"] = reconciliation_metadata(manifest, apply_receipt)
    return contracts.seal_document("deployment_evidence", payload)


def raw_map(manifest: dict, apply_receipt: dict, evidence: dict | None = None) -> dict:
    raw = {
        "manifest": fixtures.raw_bytes_of(manifest),
        "apply_receipt": fixtures.raw_bytes_of(apply_receipt),
    }
    if evidence is not None:
        raw["deployment_evidence"] = fixtures.raw_bytes_of(evidence)
    return raw


def verification_over(
    manifest: dict, apply_receipt: dict, evidence: dict, *, marked: bool
) -> dict:
    payload = fixtures.build_verification_payload(manifest, apply_receipt, evidence)
    if marked:
        payload["acceptance_basis"] = "current-state"
    return contracts.seal_document("verification", payload)


def reconcile_envelope(manifest: dict, evidence: dict, output_path: str) -> dict:
    return {
        "mode": "migration",
        "phase": "reconcile",
        "status": "reconciled",
        "manifest_id": manifest["manifest_id"],
        "verification_id": None,
        "projects": fixtures.envelope_projects("reconciled"),
        "reason": "",
        "nextStep": "",
        "migration": {
            "deployment_evidence": evidence,
            "deployment_evidence_path": output_path,
        },
    }


class ReconciledCase(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = fixtures.build_manifest()
        self.apply_receipt = fixtures.build_apply_receipt(self.manifest)
        self.evidence = reconciled_evidence(self.manifest, self.apply_receipt)
        self.raw = raw_map(self.manifest, self.apply_receipt, self.evidence)


class ReconciliationShapeTests(ReconciledCase):
    def test_current_state_evidence_is_accepted_with_unknown_history(self):
        validated = contracts.validate_document(self.evidence, "deployment_evidence")
        reconciliation = validated["payload"]["reconciliation"]
        self.assertEqual(reconciliation["kind"], "current-state")
        self.assertEqual(reconciliation["historical_execution"], "unknown")
        self.assertEqual(validated["deployment_id"], self.evidence["deployment_id"])

    def test_provenance_kind_cannot_claim_execution(self):
        with self.assertRaises(ContractError):
            reseal(
                "deployment_evidence",
                self.evidence,
                lambda payload: payload["reconciliation"].update(kind="executed"),
            )

    def test_provenance_cannot_fabricate_historical_execution(self):
        for forged in ("exit0", "succeeded", "observed"):
            with self.subTest(forged=forged), self.assertRaises(ContractError):
                reseal(
                    "deployment_evidence",
                    self.evidence,
                    lambda payload, forged=forged: payload["reconciliation"].update(
                        historical_execution=forged
                    ),
                )

    def test_provenance_is_closed_to_extra_historical_claims(self):
        for key, value in (
            ("exit_code", 0),
            ("original_started_at", fixtures.T1),
            ("interrupted", True),
        ):
            with self.subTest(key=key), self.assertRaises(ContractError):
                reseal(
                    "deployment_evidence",
                    self.evidence,
                    lambda payload, key=key, value=value: payload["reconciliation"].update(
                        {key: value}
                    ),
                )

    def test_provenance_requires_complete_refs_and_versions(self):
        for missing in (
            "manifest_ref",
            "apply_receipt_ref",
            "missing_deployment_evidence",
            "runtime_versions",
        ):
            with self.subTest(missing=missing), self.assertRaises(ContractError):
                reseal(
                    "deployment_evidence",
                    self.evidence,
                    lambda payload, missing=missing: payload["reconciliation"].pop(missing),
                )

    def test_missing_evidence_must_record_exact_absence(self):
        for state in (
            fixtures.file_state(42),
            {"type": "absent", "checksum": fixtures.digest_number(42)},
            {"type": "directory", "checksum": fixtures.digest_number(42)},
        ):
            with self.subTest(state=state["type"]), self.assertRaises(ContractError):
                reseal(
                    "deployment_evidence",
                    self.evidence,
                    lambda payload, state=state: payload["reconciliation"].update(
                        missing_deployment_evidence={
                            "path": MISSING_PATH,
                            "state": state,
                        }
                    ),
                )

    def test_provenance_refs_must_be_files(self):
        with self.assertRaises(ContractError):
            reseal(
                "deployment_evidence",
                self.evidence,
                lambda payload: payload["reconciliation"].update(
                    manifest_ref={
                        "path": MANIFEST_PATH,
                        "state": fixtures.directory_state(42),
                    }
                ),
            )

    def test_provenance_paths_must_be_normalized_absolute(self):
        for bad in ("private/migration/manifest.json", f"{MANIFEST_PATH}/../x.json"):
            with self.subTest(bad=bad), self.assertRaises(ContractError):
                reseal(
                    "deployment_evidence",
                    self.evidence,
                    lambda payload, bad=bad: payload["reconciliation"].update(
                        manifest_ref={
                            "path": bad,
                            "state": {
                                "type": "file",
                                "checksum": fixtures.raw_digest_of(self.manifest),
                            },
                        }
                    ),
                )

    def test_provenance_paths_must_be_distinct(self):
        for slot in ("apply_receipt_ref", "missing_deployment_evidence"):
            with self.subTest(slot=slot):
                def collide(payload, slot=slot):
                    metadata = payload["reconciliation"]
                    if slot == "apply_receipt_ref":
                        metadata["apply_receipt_ref"] = {
                            "path": MANIFEST_PATH,
                            "state": metadata["apply_receipt_ref"]["state"],
                        }
                    else:
                        metadata["missing_deployment_evidence"] = {
                            "path": MANIFEST_PATH,
                            "state": dict(fixtures.ABSENT),
                        }

                with self.assertRaises(ContractError):
                    reseal("deployment_evidence", self.evidence, collide)

    def test_runtime_versions_shape_is_closed(self):
        versions = (
            {"onboard": "2.0.0", "graft": GRAFT_PIN},
            {"onboard": fixtures.digest_number(900), "graft": GRAFT_PIN},
            {"onboard": ONBOARD_SHA, "graft": "  "},
            {"onboard": ONBOARD_SHA, "graft": GRAFT_PIN, "python": "3.12"},
        )
        for mutated in versions:
            with self.subTest(mutated=sorted(mutated)), self.assertRaises(ContractError):
                reseal(
                    "deployment_evidence",
                    self.evidence,
                    lambda payload, mutated=mutated: payload["reconciliation"].update(
                        runtime_versions=mutated
                    ),
                )

    def test_ordinary_evidence_without_provenance_remains_valid(self):
        ordinary = fixtures.build_deployment_evidence(self.manifest, self.apply_receipt)
        validated = contracts.validate_document(ordinary, "deployment_evidence")
        self.assertNotIn("reconciliation", validated["payload"])


class ReconciliationBindingTests(ReconciledCase):
    def bind(self, documents, raw):
        return contracts.validate_declared_bindings(self.manifest, documents, raw)

    def test_reconciled_chain_binds_exact_raw_inputs(self):
        supplied = self.bind(
            {
                "apply_receipt": self.apply_receipt,
                "deployment_evidence": self.evidence,
            },
            self.raw,
        )
        self.assertEqual(
            supplied["deployment_evidence"]["payload"]["reconciliation"]["kind"],
            "current-state",
        )

    def test_reconciliation_cannot_change_the_sealed_runtime_pin(self):
        forged = reseal(
            "deployment_evidence",
            self.evidence,
            lambda payload: payload["reconciliation"]["runtime_versions"].update(
                graft="9.9.9"
            ),
        )
        with self.assertRaises(ContractError):
            self.bind(
                {
                    "apply_receipt": self.apply_receipt,
                    "deployment_evidence": forged,
                },
                raw_map(self.manifest, self.apply_receipt),
            )

    def test_reconciled_binding_requires_raw_manifest_bytes(self):
        raw = {key: value for key, value in self.raw.items() if key != "manifest"}
        with self.assertRaises(ContractError):
            self.bind(
                {
                    "apply_receipt": self.apply_receipt,
                    "deployment_evidence": self.evidence,
                },
                raw,
            )

    def test_reconciled_binding_requires_raw_apply_bytes(self):
        raw = {key: value for key, value in self.raw.items() if key != "apply_receipt"}
        with self.assertRaises(ContractError):
            self.bind(
                {
                    "apply_receipt": self.apply_receipt,
                    "deployment_evidence": self.evidence,
                },
                raw,
            )

    def test_reconciled_binding_rejects_corrupted_input_digest(self):
        def corrupt(payload):
            payload["reconciliation"]["manifest_ref"]["state"]["checksum"] = (
                fixtures.digest_number(999)
            )

        forged = reseal("deployment_evidence", self.evidence, corrupt)
        contracts.validate_document(forged, "deployment_evidence")
        with self.assertRaises(ContractError):
            self.bind(
                {
                    "apply_receipt": self.apply_receipt,
                    "deployment_evidence": forged,
                },
                raw_map(self.manifest, self.apply_receipt),
            )

    def test_reconciled_binding_rejects_swapped_input_digests(self):
        def swap(payload):
            metadata = payload["reconciliation"]
            metadata["manifest_ref"]["state"]["checksum"] = fixtures.raw_digest_of(
                self.apply_receipt
            )
            metadata["apply_receipt_ref"]["state"]["checksum"] = fixtures.raw_digest_of(
                self.manifest
            )

        forged = reseal("deployment_evidence", self.evidence, swap)
        with self.assertRaises(ContractError):
            self.bind(
                {
                    "apply_receipt": self.apply_receipt,
                    "deployment_evidence": forged,
                },
                raw_map(self.manifest, self.apply_receipt),
            )

    def test_reconciled_verification_binds_current_state_basis(self):
        verification = verification_over(
            self.manifest, self.apply_receipt, self.evidence, marked=True
        )
        supplied = self.bind(
            {
                "apply_receipt": self.apply_receipt,
                "deployment_evidence": self.evidence,
                "verification": verification,
            },
            self.raw,
        )
        self.assertEqual(
            supplied["verification"]["payload"]["acceptance_basis"], "current-state"
        )
        self.assertEqual(
            supplied["deployment_evidence"]["payload"]["reconciliation"][
                "historical_execution"
            ],
            "unknown",
        )

    def test_reconciled_evidence_requires_current_state_marker(self):
        verification = verification_over(
            self.manifest, self.apply_receipt, self.evidence, marked=False
        )
        with self.assertRaises(ContractError):
            self.bind(
                {
                    "apply_receipt": self.apply_receipt,
                    "deployment_evidence": self.evidence,
                    "verification": verification,
                },
                self.raw,
            )

    def test_current_state_marker_rejects_ordinary_evidence(self):
        ordinary = fixtures.build_deployment_evidence(self.manifest, self.apply_receipt)
        verification = verification_over(
            self.manifest, self.apply_receipt, ordinary, marked=True
        )
        raw = raw_map(self.manifest, self.apply_receipt, ordinary)
        with self.assertRaises(ContractError):
            self.bind(
                {
                    "apply_receipt": self.apply_receipt,
                    "deployment_evidence": ordinary,
                    "verification": verification,
                },
                raw,
            )

    def test_current_state_marker_requires_bound_evidence(self):
        verification = verification_over(
            self.manifest, self.apply_receipt, self.evidence, marked=True
        )
        with self.assertRaises(ContractError):
            self.bind(
                {
                    "apply_receipt": self.apply_receipt,
                    "verification": verification,
                },
                raw_map(self.manifest, self.apply_receipt),
            )

    def test_acceptance_basis_rejects_unknown_values(self):
        payload = fixtures.build_verification_payload(
            self.manifest, self.apply_receipt, self.evidence
        )
        payload["acceptance_basis"] = "executed"
        with self.assertRaises(ContractError):
            contracts.seal_document("verification", payload)

    def test_full_chain_consumes_reconciled_evidence_coherently(self):
        verification = verification_over(
            self.manifest, self.apply_receipt, self.evidence, marked=True
        )
        cleanup = fixtures.build_cleanup_receipt(
            self.manifest, self.apply_receipt, self.evidence, verification
        )
        plan = fixtures.build_recovery_plan(
            self.manifest, self.apply_receipt, self.evidence, cleanup
        )
        receipt = fixtures.build_recovery_receipt(
            self.manifest, self.apply_receipt, self.evidence, cleanup, plan
        )
        raw = raw_map(self.manifest, self.apply_receipt, self.evidence)
        raw["cleanup_receipt"] = fixtures.raw_bytes_of(cleanup)
        supplied = self.bind(
            {
                "apply_receipt": self.apply_receipt,
                "deployment_evidence": self.evidence,
                "verification": verification,
                "cleanup_receipt": cleanup,
                "recovery_plan": plan,
                "recovery_receipt": receipt,
            },
            raw,
        )
        self.assertEqual(supplied["recovery_plan"]["payload"]["status"], "planned")
        self.assertEqual(
            supplied["recovery_receipt"]["payload"]["input_evidence"][
                "deployment_evidence"
            ]["state"]["checksum"],
            fixtures.raw_digest_of(self.evidence),
        )


class ReconciliationRetryTests(ReconciledCase):
    def retry(self, previous, mutate=None):
        def apply_retry(payload):
            payload["previous_deployment_id"] = previous["deployment_id"]
            payload["started_at"] = fixtures.T5
            payload["finished_at"] = fixtures.T6
            if mutate is not None:
                mutate(payload)

        return reseal("deployment_evidence", previous, apply_retry)

    def test_first_run_reconciled_evidence_starts_a_chain(self):
        validated = contracts.validate_cumulative(
            None, self.evidence, "deployment_evidence"
        )
        self.assertIsNone(validated["payload"]["previous_deployment_id"])

    def test_retry_preserving_provenance_is_accepted(self):
        attempt = self.retry(self.evidence)
        validated = contracts.validate_cumulative(
            self.evidence, attempt, "deployment_evidence"
        )
        self.assertEqual(
            validated["payload"]["reconciliation"],
            self.evidence["payload"]["reconciliation"],
        )

    def test_retry_cannot_strip_provenance(self):
        attempt = self.retry(
            self.evidence, lambda payload: payload.pop("reconciliation")
        )
        with self.assertRaises(ContractError):
            contracts.validate_cumulative(
                self.evidence, attempt, "deployment_evidence"
            )

    def test_retry_cannot_add_provenance(self):
        ordinary = fixtures.build_deployment_evidence(self.manifest, self.apply_receipt)
        attempt = self.retry(
            ordinary,
            lambda payload: payload.update(
                reconciliation=reconciliation_metadata(self.manifest, self.apply_receipt)
            ),
        )
        with self.assertRaises(ContractError):
            contracts.validate_cumulative(ordinary, attempt, "deployment_evidence")

    def test_retry_cannot_rewrite_provenance(self):
        mutations = (
            lambda metadata: metadata["runtime_versions"].update(graft="9.9.9"),
            lambda metadata: metadata.update(
                missing_deployment_evidence={
                    "path": f"{fixtures.EVIDENCE_DIR}/other-missing.json",
                    "state": dict(fixtures.ABSENT),
                }
            ),
            lambda metadata: metadata["manifest_ref"].update(
                path=f"{fixtures.EVIDENCE_DIR}/other-manifest.json"
            ),
        )
        for mutate_metadata in mutations:
            with self.subTest(mutate=mutate_metadata):
                attempt = self.retry(
                    self.evidence,
                    lambda payload, mutate=mutate_metadata: mutate(payload["reconciliation"]),
                )
                with self.assertRaises(ContractError):
                    contracts.validate_cumulative(
                        self.evidence, attempt, "deployment_evidence"
                    )

    def test_retry_cannot_predate_previous_observation(self):
        attempt = reseal(
            "deployment_evidence",
            self.evidence,
            lambda payload: payload.update(
                previous_deployment_id=self.evidence["deployment_id"],
                started_at=fixtures.T1,
                finished_at=fixtures.T3,
            ),
        )
        with self.assertRaises(ContractError):
            contracts.validate_cumulative(
                self.evidence, attempt, "deployment_evidence"
            )

    def test_ordinary_retry_chain_is_unchanged(self):
        ordinary = fixtures.build_deployment_evidence(self.manifest, self.apply_receipt)
        attempt = self.retry(ordinary)
        validated = contracts.validate_cumulative(
            ordinary, attempt, "deployment_evidence"
        )
        self.assertNotIn("reconciliation", validated["payload"])


class ReconcileEnvelopeTests(ReconciledCase):
    def test_reconcile_envelope_binds_evidence_and_output_path(self):
        envelope = reconcile_envelope(self.manifest, self.evidence, OUTPUT_PATH)
        validated = contracts.validate_document(envelope, "migration_envelope")
        self.assertEqual(validated["status"], "reconciled")
        self.assertIsNone(validated["verification_id"])
        self.assertEqual(
            validated["migration"]["deployment_evidence"]["deployment_id"],
            self.evidence["deployment_id"],
        )

    def test_make_envelope_supports_the_reconcile_phase(self):
        envelope = contracts.make_envelope(
            "migration",
            "reconcile",
            "reconciled",
            fixtures.envelope_projects("reconciled"),
            "",
            "",
            artifact={
                "deployment_evidence": self.evidence,
                "deployment_evidence_path": OUTPUT_PATH,
            },
            identifiers={"manifest_id": self.manifest["manifest_id"]},
        )
        self.assertEqual(envelope["phase"], "reconcile")
        self.assertIsNone(envelope["verification_id"])
        self.assertEqual(
            envelope["migration"]["deployment_evidence_path"], OUTPUT_PATH
        )

    def test_reconciled_envelope_requires_typed_provenance(self):
        ordinary = fixtures.build_deployment_evidence(self.manifest, self.apply_receipt)
        envelope = reconcile_envelope(self.manifest, ordinary, OUTPUT_PATH)
        with self.assertRaises(ContractError):
            contracts.validate_document(envelope, "migration_envelope")

    def test_reconcile_envelope_cannot_hold_a_verification_identity(self):
        envelope = reconcile_envelope(self.manifest, self.evidence, OUTPUT_PATH)
        envelope["verification_id"] = fixtures.digest_number(1)
        with self.assertRaises(ContractError):
            contracts.validate_document(envelope, "migration_envelope")

    def test_reconcile_output_path_must_be_distinct_from_cited_inputs(self):
        for collision in (MISSING_PATH, MANIFEST_PATH, APPLY_PATH):
            with self.subTest(collision=collision):
                envelope = reconcile_envelope(self.manifest, self.evidence, collision)
                with self.assertRaises(ContractError):
                    contracts.validate_document(envelope, "migration_envelope")

    def test_reconcile_envelope_rejects_foreign_project_status(self):
        envelope = reconcile_envelope(self.manifest, self.evidence, OUTPUT_PATH)
        envelope["projects"] = fixtures.envelope_projects("applied")
        with self.assertRaises(ContractError):
            contracts.validate_document(envelope, "migration_envelope")

    def test_reconcile_status_variants_are_closed(self):
        for status in ("verified", "applied", "cleaned"):
            with self.subTest(status=status):
                envelope = reconcile_envelope(self.manifest, self.evidence, OUTPUT_PATH)
                envelope["status"] = status
                if status != "verified":
                    envelope["projects"] = fixtures.envelope_projects(status)
                with self.assertRaises(ContractError):
                    contracts.validate_document(envelope, "migration_envelope")

    def test_reconciled_envelope_requires_the_evidence_artifact(self):
        envelope = reconcile_envelope(self.manifest, self.evidence, OUTPUT_PATH)
        envelope["migration"] = {}
        with self.assertRaises(ContractError):
            contracts.validate_document(envelope, "migration_envelope")

    def test_blocked_reconcile_envelope_carries_no_artifact(self):
        envelope = {
            "mode": "migration",
            "phase": "reconcile",
            "status": "blocked",
            "manifest_id": self.manifest["manifest_id"],
            "verification_id": None,
            "projects": [
                {
                    "root": fixtures.ALPHA,
                    "status": "blocked",
                    "reason": "reconciliation was not consented",
                    "nextStep": "Re-run reconcile with explicit consent.",
                },
                {
                    "root": fixtures.BETA,
                    "status": "blocked",
                    "reason": "reconciliation was not consented",
                    "nextStep": "Re-run reconcile with explicit consent.",
                },
            ],
            "reason": "current-state reconciliation requires explicit consent",
            "nextStep": "Re-run the reconcile phase with --yes to accept writes.",
            "migration": {},
        }
        validated = contracts.validate_document(envelope, "migration_envelope")
        self.assertEqual(validated["status"], "blocked")
        self.assertEqual(validated["migration"], {})


class ReconciliationSemanticsTests(ReconciledCase):
    def test_observation_window_must_be_ordered(self):
        with self.assertRaises(ContractError):
            reseal(
                "deployment_evidence",
                self.evidence,
                lambda payload: payload.update(
                    started_at=fixtures.T4, finished_at=fixtures.T3
                ),
            )

    def test_status_still_aggregates_project_outcomes(self):
        def degrade(payload):
            payload["projects"][0].update(
                status="blocked",
                reason="smoke observation was inconclusive",
                nextStep="Re-run the observation before accepting.",
            )

        with self.assertRaises(ContractError):
            reseal("deployment_evidence", self.evidence, degrade)

    def test_ordinary_family_still_binds_end_to_end(self):
        family = fixtures.build_fixture_family()
        supplied = contracts.validate_declared_bindings(
            family["manifest"],
            {
                kind: family[kind]
                for kind in (
                    "apply_receipt",
                    "deployment_evidence",
                    "verification",
                    "cleanup_receipt",
                    "recovery_plan",
                    "recovery_receipt",
                )
            },
            fixtures.fixture_raw_documents(family),
        )
        self.assertNotIn(
            "acceptance_basis", supplied["verification"]["payload"]
        )
        self.assertNotIn(
            "reconciliation", supplied["deployment_evidence"]["payload"]
        )


class ReconciliationImmutableReferenceTests(ReconciledCase):
    """The cited missing historical snapshot joins immutable stage references.

    Only the missing snapshot is reserved (the manifest/apply input refs are
    not stage-produced artifacts); ordinary historical evidence keeps the
    exact pre-reconciliation reference set, so a path that a reconciled
    record cites stays usable by ordinary execution evidence.
    """

    def immutable_paths(self, evidence: dict) -> set:
        return {
            reference["path"]
            for reference in contracts._immutable_stage_references(
                evidence["payload"]
            )
        }

    def test_stage_references_include_only_the_missing_snapshot(self):
        paths = self.immutable_paths(self.evidence)
        self.assertIn(MISSING_PATH, paths)
        self.assertNotIn(MANIFEST_PATH, paths)
        self.assertNotIn(APPLY_PATH, paths)

    def test_ordinary_evidence_reference_set_gains_nothing(self):
        ordinary = fixtures.build_deployment_evidence(self.manifest, self.apply_receipt)
        difference = self.immutable_paths(self.evidence) - self.immutable_paths(ordinary)
        self.assertEqual(difference, {MISSING_PATH})

    def test_result_path_distinct_from_missing_path_is_accepted(self):
        result = {"path": OUTPUT_PATH, "evidence": self.evidence}
        self.assertIs(contracts.validate_deployment_result(result), result)

    def test_result_path_cannot_be_the_cited_missing_path(self):
        result = {"path": MISSING_PATH, "evidence": self.evidence}
        with self.assertRaises(ContractError) as error:
            contracts.validate_deployment_result(result)
        self.assertEqual(error.exception.code, "semantic-violation")

    def test_result_path_cannot_nest_below_the_cited_missing_path(self):
        result = {"path": f"{MISSING_PATH}/nested.json", "evidence": self.evidence}
        with self.assertRaises(ContractError) as error:
            contracts.validate_deployment_result(result)
        self.assertEqual(error.exception.code, "semantic-violation")

    def test_result_path_cannot_contain_the_cited_missing_path(self):
        def relocate(payload):
            payload["reconciliation"]["missing_deployment_evidence"] = {
                "path": f"{fixtures.EVIDENCE_DIR}/missing-slot/historical.json",
                "state": dict(fixtures.ABSENT),
            }

        evidence = reseal("deployment_evidence", self.evidence, relocate)
        result = {"path": f"{fixtures.EVIDENCE_DIR}/missing-slot", "evidence": evidence}
        with self.assertRaises(ContractError) as error:
            contracts.validate_deployment_result(result)
        self.assertEqual(error.exception.code, "semantic-violation")

    def test_ordinary_evidence_may_use_a_path_a_reconciled_record_cites(self):
        ordinary = fixtures.build_deployment_evidence(self.manifest, self.apply_receipt)
        result = {"path": MISSING_PATH, "evidence": ordinary}
        self.assertIs(contracts.validate_deployment_result(result), result)

    def test_retry_output_still_cannot_be_the_cited_missing_path(self):
        attempt = reseal(
            "deployment_evidence",
            self.evidence,
            lambda payload: payload.update(
                previous_deployment_id=self.evidence["deployment_id"],
                started_at=fixtures.T5,
                finished_at=fixtures.T6,
            ),
        )
        contracts.validate_cumulative(self.evidence, attempt, "deployment_evidence")
        result = {"path": MISSING_PATH, "evidence": attempt}
        with self.assertRaises(ContractError) as error:
            contracts.validate_deployment_result(result)
        self.assertEqual(error.exception.code, "semantic-violation")

    def test_recovery_binding_reserves_the_cited_missing_path(self):
        verification = verification_over(
            self.manifest, self.apply_receipt, self.evidence, marked=True
        )
        cleanup = fixtures.build_cleanup_receipt(
            self.manifest, self.apply_receipt, self.evidence, verification
        )
        base_plan = fixtures.build_recovery_plan(
            self.manifest, self.apply_receipt, self.evidence, cleanup
        )

        def usurp(payload):
            payload["input_evidence"]["deployment_evidence"]["path"] = MISSING_PATH

        plan = reseal("recovery_plan", base_plan, usurp)
        base_receipt = fixtures.build_recovery_receipt(
            self.manifest, self.apply_receipt, self.evidence, cleanup, plan
        )
        receipt = reseal("recovery_receipt", base_receipt, usurp)
        raw = raw_map(self.manifest, self.apply_receipt, self.evidence)
        raw["cleanup_receipt"] = fixtures.raw_bytes_of(cleanup)
        with self.assertRaises(ContractError) as error:
            contracts.validate_declared_bindings(
                self.manifest,
                {
                    "apply_receipt": self.apply_receipt,
                    "deployment_evidence": self.evidence,
                    "verification": verification,
                    "cleanup_receipt": cleanup,
                    "recovery_plan": plan,
                    "recovery_receipt": receipt,
                },
                raw,
            )
        self.assertEqual(error.exception.code, "binding-violation")


if __name__ == "__main__":
    unittest.main()
