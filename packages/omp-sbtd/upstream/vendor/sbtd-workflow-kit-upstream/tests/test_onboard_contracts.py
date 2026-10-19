from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import onboard_contract_fixtures as fixtures

contracts = fixtures.contracts
ContractError = contracts.ContractError

ZERO_DIGEST = "0" * 64


def reseal(kind: str, document: dict, mutate) -> dict:
    payload = copy.deepcopy(document["payload"])
    mutate(payload)
    return contracts.seal_document(kind, payload)


def expect_error(
    testcase: unittest.TestCase, code: str, fn, *args, **kwargs
) -> ContractError:
    with testcase.assertRaises(ContractError) as raised:
        fn(*args, **kwargs)
    testcase.assertEqual(raised.exception.code, code)
    return raised.exception


class StrictDecodeTests(unittest.TestCase):
    def load(self, text, kind="publication_decisions"):
        return contracts.load_document(text, kind)

    def test_duplicate_keys_are_rejected(self) -> None:
        error = expect_error(
            self,
            "duplicate-key",
            self.load,
            '{"schema_version": 1, "schema_version": 1, "items": []}',
        )
        self.assertEqual(error.exit_code, 2)

    def test_nonfinite_numbers_are_rejected(self) -> None:
        for literal in ("NaN", "Infinity", "-Infinity", "1e999"):
            with self.subTest(literal=literal):
                expect_error(
                    self,
                    "non-finite-number",
                    self.load,
                    f'{{"schema_version": {literal}, "items": []}}',
                )

    def test_float_literals_are_wrong_type(self) -> None:
        expect_error(
            self,
            "unexpected-type",
            self.load,
            '{"schema_version": 1.0, "items": []}',
        )

    def test_boolean_is_not_an_integer(self) -> None:
        expect_error(
            self,
            "schema-violation",
            self.load,
            '{"schema_version": true, "items": []}',
        )

    def test_invalid_utf8_is_rejected(self) -> None:
        expect_error(
            self,
            "invalid-utf8",
            contracts.load_document,
            b'{"schema_version": 1, "items": [], "x": "\xff"}',
            "publication_decisions",
        )

    def test_unpaired_surrogate_escape_is_rejected(self) -> None:
        expect_error(
            self,
            "malformed-unicode",
            self.load,
            '{"schema_version": 1, "items": [], "x": "\\ud800"}',
        )

    def test_malformed_json_is_rejected(self) -> None:
        expect_error(self, "invalid-json", self.load, '{"schema_version": 1,]')

    def test_unknown_kind_is_rejected(self) -> None:
        expect_error(self, "unknown-kind", self.load, "{}", kind="Manifest")
        expect_error(
            self, "unknown-kind", contracts.validate_document, {}, "deployment_result"
        )

    def test_future_schema_version_is_rejected(self) -> None:
        expect_error(
            self, "schema-violation", self.load, '{"schema_version": 2, "items": []}'
        )


class CanonicalJsonTests(unittest.TestCase):
    def test_canonical_bytes_sort_keys_and_skip_ascii_escaping(self) -> None:
        value = {"b": "用户", "a": [1, True, None]}
        self.assertEqual(
            contracts.canonical_json_bytes(value),
            '{"a":[1,true,null],"b":"用户"}'.encode(),
        )

    def test_key_insertion_order_does_not_change_digest(self) -> None:
        first = {"x": 1, "y": {"z": 2, "w": 3}}
        second = {"y": {"w": 3, "z": 2}, "x": 1}
        self.assertEqual(
            contracts.canonical_json_bytes(first),
            contracts.canonical_json_bytes(second),
        )

    def test_nonfinite_values_cannot_be_serialized(self) -> None:
        expect_error(
            self, "non-json-value", contracts.canonical_json_bytes, float("inf")
        )
        expect_error(
            self, "non-json-value", contracts.canonical_json_bytes, {"x": float("nan")}
        )

    def test_resource_id_matches_independent_vector(self) -> None:
        expected = hashlib.sha256(b'["json","/a/b"]').hexdigest()
        self.assertEqual(contracts.resource_id("json", "/a/b"), expected)

    def test_operation_id_matches_independent_vector(self) -> None:
        rid = contracts.resource_id("toml", "/cfg/file.toml")
        expected = hashlib.sha256(
            f'["apply","{rid}","whole-resource"]'.encode()
        ).hexdigest()
        self.assertEqual(
            contracts.operation_id("apply", rid, "whole-resource"), expected
        )

    def test_recovery_step_id_matches_independent_vector(self) -> None:
        manifest_id = "a" * 64
        rid = contracts.resource_id("json", "/x")
        expected = hashlib.sha256(
            f'["recovery","{manifest_id}","cleanup","{rid}"]'.encode()
        ).hexdigest()
        self.assertEqual(
            contracts.recovery_step_id(manifest_id, "cleanup", rid), expected
        )

    def test_ids_are_stable_across_calls(self) -> None:
        self.assertEqual(
            contracts.resource_id("json", "/a/b"), contracts.resource_id("json", "/a/b")
        )
        self.assertNotEqual(
            contracts.resource_id("json", "/a/b"), contracts.resource_id("toml", "/a/b")
        )


class FormatBoundaryTests(unittest.TestCase):
    def manifest_with(self, mutate):
        payload = fixtures.build_manifest_payload()
        mutate(payload)
        return contracts.seal_document("manifest", payload)

    def test_timestamp_requires_timezone(self) -> None:
        def mutate(payload):
            payload["created_at"] = "2026-09-18T01:00:00"

        expect_error(self, "schema-violation", self.manifest_with, mutate)

    def test_timestamp_requires_a_real_calendar_date(self) -> None:
        def mutate(payload):
            payload["created_at"] = "2026-02-31T01:00:00Z"

        expect_error(self, "schema-violation", self.manifest_with, mutate)

    def test_timestamp_with_explicit_offset_is_accepted(self) -> None:
        def mutate(payload):
            payload["created_at"] = "2026-09-18T09:00:00+08:00"

        self.manifest_with(mutate)

    def test_paths_must_be_normalized_and_absolute(self) -> None:
        for bad in (
            "relative/path",
            "/private//backup",
            "/private/../x",
            "/private/backup/",
        ):
            with self.subTest(path=bad):

                def mutate(payload, bad=bad):
                    payload["backup_root"] = bad

                expect_error(self, "schema-violation", self.manifest_with, mutate)

    def test_uppercase_digest_is_rejected(self) -> None:
        def mutate(payload):
            payload["custodian"] = "custodian"
            payload["projects"][0]["shared_operation_ids"] = ["A" * 64]

        expect_error(self, "schema-violation", self.manifest_with, mutate)

    def test_unknown_keys_are_rejected(self) -> None:
        document = fixtures.build_manifest()
        document["payload"]["unexpected"] = True
        expect_error(
            self, "schema-violation", contracts.validate_document, document, "manifest"
        )

    def test_unknown_enum_is_rejected(self) -> None:
        def mutate(payload):
            payload["projects"][0]["platforms"] = ["trellis"]

        expect_error(self, "schema-violation", self.manifest_with, mutate)


class PublicationDecisionTests(unittest.TestCase):
    def decisions_with(self, mutate):
        items = fixtures.build_publication_items()
        mutate(items)
        return contracts.validate_document(
            {"schema_version": 1, "items": items}, "publication_decisions"
        )

    def test_valid_decisions_pass(self) -> None:
        self.decisions_with(lambda items: None)
        contracts.validate_document(
            {"schema_version": 1, "items": []}, "publication_decisions"
        )

    def test_approval_scope_drift_is_rejected(self) -> None:
        def mutate(items):
            items[0]["approval"]["scope"]["target_path"] = (
                "/private/home/shared/other.md"
            )

        expect_error(self, "semantic-violation", self.decisions_with, mutate)

    def test_approval_scope_must_keep_exact_structure(self) -> None:
        def mutate(items):
            items[0]["approval"]["scope"] = {"decision": "share"}

        expect_error(self, "schema-violation", self.decisions_with, mutate)

    def test_duplicate_item_id_is_rejected(self) -> None:
        def mutate(items):
            clone = copy.deepcopy(items[0])
            clone["target_path"] = "/private/home/shared/second.md"
            clone["approval"]["scope"]["target_path"] = "/private/home/shared/second.md"
            items.append(clone)

        expect_error(self, "semantic-violation", self.decisions_with, mutate)

    def test_duplicate_sources_within_one_item_are_rejected(self) -> None:
        def mutate(items):
            extra = copy.deepcopy(items[0]["sources"][0])
            items[0]["sources"].append(extra)
            items[0]["approval"]["scope"]["sources"].append(copy.deepcopy(extra))

        expect_error(self, "semantic-violation", self.decisions_with, mutate)

    def test_duplicate_targets_across_items_are_rejected(self) -> None:
        def mutate(items):
            clone = copy.deepcopy(items[0])
            clone["item_id"] = "second"
            items.append(clone)

        expect_error(self, "semantic-violation", self.decisions_with, mutate)

    def test_parent_child_target_overlap_is_rejected(self) -> None:
        def mutate(items):
            clone = copy.deepcopy(items[0])
            clone["item_id"] = "second"
            clone["target_path"] = str(Path(items[0]["target_path"]).parent)
            clone["approval"]["scope"]["target_path"] = clone["target_path"]
            items.append(clone)

        expect_error(self, "semantic-violation", self.decisions_with, mutate)

    def test_private_only_must_keep_null_target_and_candidate(self) -> None:
        def mutate(items):
            items[1]["candidate_ref"] = fixtures._file_ref("/private/candidates/x", 90)
            items[1]["approval"]["scope"]["candidate_ref"] = fixtures._file_ref(
                "/private/candidates/x", 90
            )

        expect_error(self, "schema-violation", self.decisions_with, mutate)


class PathAliasContainmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="sbtd-contract-paths-")
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def decisions_with_targets(self, first: Path, second: Path) -> dict:
        items = fixtures.build_publication_items()
        items[0]["target_path"] = str(first)
        items[0]["approval"]["scope"]["target_path"] = str(first)
        clone = copy.deepcopy(items[0])
        clone["item_id"] = "alias-target"
        clone["target_path"] = str(second)
        clone["approval"]["scope"]["target_path"] = str(second)
        items.append(clone)
        return {"schema_version": 1, "items": items}

    def test_public_contract_rejects_symlinked_parent_child_targets(self) -> None:
        real = self.root / "real"
        real.mkdir()
        alias = self.root / "alias"
        try:
            alias.symlink_to(real, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"symlinks are unavailable: {error}")

        payload = self.decisions_with_targets(
            real / "reports", alias / "reports" / "detail.json"
        )

        expect_error(
            self,
            "semantic-violation",
            contracts.validate_document,
            payload,
            "publication_decisions",
        )

    def test_public_contract_rejects_case_aliases_when_filesystem_identifies_them(
        self,
    ) -> None:
        lower = self.root / "case"
        upper = self.root / "CASE"
        lower.mkdir()
        if not upper.exists() or not os.path.samefile(lower, upper):
            self.skipTest("filesystem is case-sensitive")

        payload = self.decisions_with_targets(
            lower / "reports", upper / "reports" / "detail.json"
        )

        expect_error(
            self,
            "semantic-violation",
            contracts.validate_document,
            payload,
            "publication_decisions",
        )

    def test_public_contract_keeps_distinct_case_sensitive_targets_separate(
        self,
    ) -> None:
        lower = self.root / "case"
        upper = self.root / "CASE"
        lower.mkdir()
        if upper.exists() and os.path.samefile(lower, upper):
            self.skipTest("filesystem is case-insensitive")
        upper.mkdir()

        payload = self.decisions_with_targets(
            lower / "report.json", upper / "report.json"
        )

        contracts.validate_document(payload, "publication_decisions")

    def test_public_contract_rechecks_changed_hardlink_aliases(self) -> None:
        first = self.root / "first.md"
        second = self.root / "second.md"
        first.write_text("first")
        second.write_text("second")
        payload = self.decisions_with_targets(first, second)
        contracts.validate_document(payload, "publication_decisions")

        second.unlink()
        try:
            os.link(first, second)
        except OSError as error:
            self.skipTest(f"hardlinks are unavailable: {error}")
        expect_error(
            self, "semantic-violation", contracts.validate_document,
            payload, "publication_decisions",
        )

        second.unlink()
        second.write_text("separate again")
        contracts.validate_document(payload, "publication_decisions")


class ManifestSemanticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = fixtures.build_manifest()

    def test_valid_manifest_passes(self) -> None:
        contracts.validate_document(self.manifest, "manifest")

    def test_deployment_declaration_is_required_and_null_only_without_deploy(
        self,
    ) -> None:
        payload = fixtures.build_manifest_payload()
        payload.pop("deployment")
        with self.assertRaises(contracts.ContractError):
            contracts.seal_document("manifest", payload)
        for project in payload["projects"]:
            project["private_operations"] = [
                operation
                for operation in project["private_operations"]
                if operation["phase"] == "apply"
            ]
        payload["shared_operations"] = [
            operation
            for operation in payload["shared_operations"]
            if operation["phase"] == "apply"
        ]
        shared_ids = [
            operation["operation_id"] for operation in payload["shared_operations"]
        ]
        for project in payload["projects"]:
            project["shared_operation_ids"] = list(shared_ids)
        payload["deployment"] = None
        contracts.seal_document("manifest", payload)
        payload["deployment"] = {
            "mode": "init",
            "platform": "codex",
            "inputs": [],
        }
        with self.assertRaises(contracts.ContractError):
            contracts.seal_document("manifest", payload)

    def test_omp_deployment_binds_host_mode_and_readonly_inputs(self) -> None:
        payload = fixtures.build_manifest_payload()
        payload["deployment"] = {
            "mode": "init",
            "platform": "omp",
            "inputs": [
                {
                    "path": "/private/home/.codex/inherited.toml",
                    "state": fixtures.file_state(91),
                },
                {
                    "path": "/private/work/alpha/.omp/mcp.json",
                    "state": dict(fixtures.ABSENT),
                },
            ],
        }
        contracts.seal_document("manifest", payload)
        payload["deployment"]["inputs"].append(
            {
                "path": "/private/home/.codex/inherited.toml",
                "state": fixtures.file_state(92),
            }
        )
        with self.assertRaises(contracts.ContractError):
            contracts.seal_document("manifest", payload)

    def test_forged_manifest_id_is_rejected_with_exit_three(self) -> None:
        document = copy.deepcopy(self.manifest)
        document["manifest_id"] = ZERO_DIGEST
        error = expect_error(
            self, "id-mismatch", contracts.validate_document, document, "manifest"
        )
        self.assertEqual(error.exit_code, 3)

    def test_forged_operation_id_is_rejected(self) -> None:
        def mutate(payload):
            payload["projects"][0]["private_operations"][0]["operation_id"] = (
                ZERO_DIGEST
            )

        error = expect_error(
            self, "id-mismatch", reseal, "manifest", self.manifest, mutate
        )
        self.assertEqual(error.exit_code, 3)

    def test_forged_resource_id_is_rejected(self) -> None:
        def mutate(payload):
            payload["projects"][0]["private_operations"][0]["resource_id"] = ZERO_DIGEST

        expect_error(self, "id-mismatch", reseal, "manifest", self.manifest, mutate)

    def with_project_root(self, index, root):
        payload = copy.deepcopy(self.manifest["payload"])
        project = payload["projects"][index]
        old_root = project["root"]
        project["root"] = root
        for operation in project["private_operations"]:
            operation["dependent_projects"] = [root]
        for entry in [*payload["shared_operations"], *payload["shared_roots"]]:
            entry["dependent_projects"] = sorted(
                root if dependency == old_root else dependency
                for dependency in entry["dependent_projects"]
            )
        return payload

    def test_resource_cannot_have_two_private_owners(self) -> None:
        # Nested selected roots both contain r1; containment alone cannot reject it.
        payload = self.with_project_root(1, "/private/work")
        contracts.seal_document("manifest", copy.deepcopy(payload))
        operation = fixtures.build_operation("r1", "apply")
        operation["selector"] = "second-owner"
        operation["ownership"]["key_path"] = ["other"]
        operation["operation_id"] = contracts.operation_id(
            "apply", operation["resource_id"], operation["selector"]
        )
        operation["dependent_projects"] = [payload["projects"][1]["root"]]
        payload["projects"][1]["private_operations"].append(operation)
        expect_error(
            self, "semantic-violation", contracts.seal_document, "manifest", payload
        )

    def test_resource_cannot_be_both_private_and_shared(self) -> None:
        payload = self.with_project_root(0, "/private/home")
        payload["projects"][0]["private_operations"] = []
        payload["publication_decisions"]["items"] = []
        contracts.seal_document("manifest", copy.deepcopy(payload))
        operation = copy.deepcopy(payload["shared_operations"][0])
        operation["selector"] = "private-claim"
        operation["ownership"]["key_path"] = ["other"]
        operation["operation_id"] = contracts.operation_id(
            "apply", operation["resource_id"], operation["selector"]
        )
        operation["dependent_projects"] = [payload["projects"][0]["root"]]
        payload["projects"][0]["private_operations"].append(operation)
        expect_error(
            self, "semantic-violation", contracts.seal_document, "manifest", payload
        )

    def test_duplicate_operation_id_is_rejected(self) -> None:
        def mutate(payload):
            operation = copy.deepcopy(payload["projects"][1]["private_operations"][0])
            operation["dependent_projects"] = [fixtures.BETA]
            payload["projects"][1]["private_operations"].append(operation)

        expect_error(
            self, "semantic-violation", reseal, "manifest", self.manifest, mutate
        )

    def test_phase_after_must_reference_an_earlier_phase(self) -> None:
        def mutate(payload):
            operation = payload["projects"][0]["private_operations"][1]
            operation["before_requirement"] = {
                "kind": "phase-after",
                "phase": "deploy",
                "resource_id": operation["resource_id"],
            }

        expect_error(
            self, "semantic-violation", reseal, "manifest", self.manifest, mutate
        )

    def test_phase_after_must_reference_the_same_resource(self) -> None:
        def mutate(payload):
            operation = payload["projects"][0]["private_operations"][1]
            operation["before_requirement"] = {
                "kind": "phase-after",
                "phase": "apply",
                "resource_id": fixtures.resource_id_of("r2"),
            }

        expect_error(
            self, "semantic-violation", reseal, "manifest", self.manifest, mutate
        )

    def test_shared_reverse_dependency_set_must_match(self) -> None:
        def mutate(payload):
            s1_apply = fixtures.operations_of("s1")["apply"]["operation_id"]
            payload["projects"][1]["shared_operation_ids"] = [
                op_id
                for op_id in payload["projects"][1]["shared_operation_ids"]
                if op_id != s1_apply
            ]

        expect_error(
            self, "semantic-violation", reseal, "manifest", self.manifest, mutate
        )

    def test_unknown_shared_operation_reference_is_rejected(self) -> None:
        def mutate(payload):
            payload["projects"][0]["shared_operation_ids"].append(ZERO_DIGEST)

        expect_error(
            self, "semantic-violation", reseal, "manifest", self.manifest, mutate
        )

    def test_dependent_projects_must_be_sorted(self) -> None:
        def mutate(payload):
            payload["shared_operations"][0]["dependent_projects"] = [
                fixtures.BETA,
                fixtures.ALPHA,
            ]

        expect_error(
            self, "semantic-violation", reseal, "manifest", self.manifest, mutate
        )


class StageReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = fixtures.build_manifest()
        cls.apply_receipt = fixtures.build_apply_receipt(cls.manifest)
        cls.deployment = fixtures.build_deployment_evidence(
            cls.manifest, cls.apply_receipt
        )

    def test_valid_receipts_pass(self) -> None:
        contracts.validate_document(self.apply_receipt, "apply_receipt")
        contracts.validate_document(self.deployment, "deployment_evidence")

    def test_duplicate_phase_resource_result_is_rejected(self) -> None:
        def mutate(payload):
            payload["projects"][0]["private_results"].append(
                copy.deepcopy(payload["projects"][0]["private_results"][0])
            )

        expect_error(
            self,
            "semantic-violation",
            reseal,
            "apply_receipt",
            self.apply_receipt,
            mutate,
        )

    def test_absent_before_state_cannot_carry_a_backup(self) -> None:
        def mutate(payload):
            payload["projects"][0]["private_results"][0]["before"] = dict(
                fixtures.ABSENT
            )

        expect_error(
            self,
            "semantic-violation",
            reseal,
            "apply_receipt",
            self.apply_receipt,
            mutate,
        )

    def test_failed_result_requires_an_error(self) -> None:
        def mutate(payload):
            result = payload["projects"][0]["private_results"][0]
            result["status"] = "failed"
            result["error"] = None

        expect_error(
            self,
            "schema-violation",
            reseal,
            "apply_receipt",
            self.apply_receipt,
            mutate,
        )

    def test_temporal_order_is_enforced(self) -> None:
        def mutate(payload):
            payload["started_at"] = fixtures.T2
            payload["finished_at"] = fixtures.T1

        expect_error(
            self,
            "semantic-violation",
            reseal,
            "apply_receipt",
            self.apply_receipt,
            mutate,
        )

    def test_status_must_match_project_aggregation(self) -> None:
        def mutate(payload):
            payload["status"] = "already-complete"

        expect_error(
            self,
            "semantic-violation",
            reseal,
            "apply_receipt",
            self.apply_receipt,
            mutate,
        )

    def test_result_phase_must_match_the_receipt_stage(self) -> None:
        def mutate(payload):
            payload["projects"][0]["private_results"][0]["phase"] = "deploy"

        expect_error(
            self,
            "semantic-violation",
            reseal,
            "apply_receipt",
            self.apply_receipt,
            mutate,
        )

    def test_deployment_evidence_rejects_apply_phase_results(self) -> None:
        def mutate(payload):
            payload["projects"][0]["private_results"] = [
                fixtures.build_resource_result("r1", "apply")
            ]

        expect_error(
            self,
            "semantic-violation",
            reseal,
            "deployment_evidence",
            self.deployment,
            mutate,
        )


class RecoveryPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = fixtures.build_manifest()
        cls.apply_receipt = fixtures.build_apply_receipt(cls.manifest)
        cls.deployment = fixtures.build_deployment_evidence(
            cls.manifest, cls.apply_receipt
        )
        cls.verification = fixtures.build_verification(
            cls.manifest, cls.apply_receipt, cls.deployment
        )
        cls.cleanup = fixtures.build_cleanup_receipt(
            cls.manifest, cls.apply_receipt, cls.deployment, cls.verification
        )
        cls.plan = fixtures.build_recovery_plan(
            cls.manifest, cls.apply_receipt, cls.deployment, cls.cleanup
        )

    def test_valid_plan_passes(self) -> None:
        contracts.validate_document(self.plan, "recovery_plan")

    def test_blocked_plan_records_conflicts(self) -> None:
        def blocked(payload):
            payload["status"] = "blocked"
            payload["conflicts"] = ["shared closure is incomplete"]

        contracts.validate_document(
            reseal("recovery_plan", self.plan, blocked), "recovery_plan"
        )

        def no_conflicts(payload):
            payload["status"] = "blocked"

        expect_error(
            self, "semantic-violation", reseal, "recovery_plan", self.plan, no_conflicts
        )

    def test_steps_must_follow_inverse_phase_order(self) -> None:
        def mutate(payload):
            steps = payload["steps"]
            cleanup_index = next(
                i for i, s in enumerate(steps) if s["phase"] == "cleanup"
            )
            deploy_index = next(
                i for i, s in enumerate(steps) if s["phase"] == "deploy"
            )
            steps[cleanup_index], steps[deploy_index] = (
                steps[deploy_index],
                steps[cleanup_index],
            )

        expect_error(
            self, "semantic-violation", reseal, "recovery_plan", self.plan, mutate
        )

    def test_state_chain_must_hold_per_resource(self) -> None:
        def mutate(payload):
            for step in payload["steps"]:
                if step["phase"] == "deploy" and step[
                    "resource_id"
                ] == fixtures.resource_id_of("r1"):
                    step["expected_current"] = fixtures.file_state(99)

        expect_error(
            self, "semantic-violation", reseal, "recovery_plan", self.plan, mutate
        )

    def test_unknown_or_forward_dependencies_are_rejected(self) -> None:
        def unknown(payload):
            payload["steps"][0]["depends_on"] = [ZERO_DIGEST]

        expect_error(
            self, "semantic-violation", reseal, "recovery_plan", self.plan, unknown
        )

        def forward(payload):
            cleanup_step = payload["steps"][0]
            deploy_step = next(
                step
                for step in payload["steps"]
                if step["phase"] == "deploy"
                and step["resource_id"] == cleanup_step["resource_id"]
            )
            cleanup_step["depends_on"] = [deploy_step["step_id"]]

        expect_error(
            self, "semantic-violation", reseal, "recovery_plan", self.plan, forward
        )

    def test_shared_step_operations_must_be_listed(self) -> None:
        def mutate(payload):
            s1_apply = fixtures.operations_of("s1")["apply"]["operation_id"]
            payload["shared_operation_ids"] = [
                op_id for op_id in payload["shared_operation_ids"] if op_id != s1_apply
            ]

        expect_error(
            self, "semantic-violation", reseal, "recovery_plan", self.plan, mutate
        )

    def test_step_id_must_match_canonical_digest(self) -> None:
        def mutate(payload):
            payload["steps"][0]["step_id"] = ZERO_DIGEST

        error = expect_error(
            self, "id-mismatch", reseal, "recovery_plan", self.plan, mutate
        )
        self.assertEqual(error.exit_code, 3)


class RecoveryReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = fixtures.build_manifest()
        cls.apply_receipt = fixtures.build_apply_receipt(cls.manifest)
        cls.deployment = fixtures.build_deployment_evidence(
            cls.manifest, cls.apply_receipt
        )
        cls.verification = fixtures.build_verification(
            cls.manifest, cls.apply_receipt, cls.deployment
        )
        cls.cleanup = fixtures.build_cleanup_receipt(
            cls.manifest, cls.apply_receipt, cls.deployment, cls.verification
        )
        cls.plan = fixtures.build_recovery_plan(
            cls.manifest, cls.apply_receipt, cls.deployment, cls.cleanup
        )
        cls.receipt = fixtures.build_recovery_receipt(
            cls.manifest, cls.apply_receipt, cls.deployment, cls.cleanup, cls.plan
        )

    def test_valid_receipt_passes(self) -> None:
        contracts.validate_document(self.receipt, "recovery_receipt")

    def test_step_cannot_be_completed_and_pending(self) -> None:
        def mutate(payload):
            payload["pending_step_ids"] = [payload["completed_step_ids"][0]]

        expect_error(
            self, "semantic-violation", reseal, "recovery_receipt", self.receipt, mutate
        )

    def test_shared_results_must_group_multi_project_steps(self) -> None:
        def mutate(payload):
            payload["shared_results"] = []

        expect_error(
            self, "semantic-violation", reseal, "recovery_receipt", self.receipt, mutate
        )

    def test_completed_steps_need_succeeded_results(self) -> None:
        def mutate(payload):
            result = payload["results"][0]
            result["status"] = "failed"
            result["error"] = "write failed"

        expect_error(
            self, "semantic-violation", reseal, "recovery_receipt", self.receipt, mutate
        )

    def test_absent_before_state_cannot_carry_protection(self) -> None:
        def mutate(payload):
            result = payload["results"][0]
            result["protection_ref"] = {
                "path": "/private/migration/protection/x",
                "state": fixtures.file_state(77),
            }

        expect_error(
            self, "semantic-violation", reseal, "recovery_receipt", self.receipt, mutate
        )


class DeclaredBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.family = fixtures.build_fixture_family()

    def documents(self):
        return {
            kind: copy.deepcopy(self.family[kind])
            for kind in (
                "apply_receipt",
                "deployment_evidence",
                "verification",
                "cleanup_receipt",
                "recovery_plan",
                "recovery_receipt",
            )
        }

    def test_full_family_binds_with_raw_bytes(self) -> None:
        supplied = contracts.validate_declared_bindings(
            self.family["manifest"],
            self.documents(),
            fixtures.fixture_raw_documents(self.family),
        )
        self.assertEqual(set(supplied), set(self.documents()))

    def test_bindings_hold_without_raw_bytes(self) -> None:
        contracts.validate_declared_bindings(self.family["manifest"], self.documents())

    def test_absent_stage_documents_are_not_inferred(self) -> None:
        contracts.validate_declared_bindings(
            self.family["manifest"], {"apply_receipt": self.family["apply_receipt"]}
        )

    def test_tampered_raw_bytes_fail_closed(self) -> None:
        raw = fixtures.fixture_raw_documents(self.family)
        raw["deployment_evidence"] = b"{}"
        error = expect_error(
            self,
            "binding-violation",
            contracts.validate_declared_bindings,
            self.family["manifest"],
            self.documents(),
            raw,
        )
        self.assertEqual(error.exit_code, 3)

    def test_successful_stage_requires_complete_private_coverage(self) -> None:
        receipt = reseal(
            "apply_receipt",
            self.family["apply_receipt"],
            lambda payload: payload["projects"][0]["private_results"].pop(0),
        )
        expect_error(
            self,
            "binding-violation",
            contracts.validate_declared_bindings,
            self.family["manifest"],
            {"apply_receipt": receipt},
        )

    def test_partial_receipt_may_omit_unfinished_resources(self) -> None:
        def mutate(payload):
            payload["status"] = "failed"
            alpha = payload["projects"][0]
            alpha["status"] = "failed"
            alpha["reason"] = "shared dependency failed"
            alpha["nextStep"] = "resolve the shared failure and retry"
            alpha["private_results"] = [
                fixtures.build_resource_result("r1", "apply", "failed", "write failed")
            ]
            payload["projects"][1]["status"] = "failed"
            payload["projects"][1]["reason"] = "blocked by batch"
            payload["projects"][1]["nextStep"] = "retry after unblock"
            payload["projects"][1]["private_results"] = []
            payload["shared_results"] = [
                fixtures.build_resource_result("s1", "apply", "failed", "write failed")
            ]

        partial = reseal("apply_receipt", self.family["apply_receipt"], mutate)
        contracts.validate_declared_bindings(
            self.family["manifest"], {"apply_receipt": partial}
        )

    def test_result_operation_ids_must_match_the_declared_set(self) -> None:
        def add_second_apply_entry(payload):
            operation = fixtures.build_operation("r1", "apply")
            operation["selector"] = "second-entry"
            operation["ownership"]["key_path"] = ["other"]
            operation["operation_id"] = contracts.operation_id(
                "apply", operation["resource_id"], "second-entry"
            )
            payload["projects"][0]["private_operations"].append(operation)

        manifest = reseal("manifest", self.family["manifest"], add_second_apply_entry)
        receipt_payload = fixtures.build_apply_receipt_payload(manifest)
        receipt = contracts.seal_document("apply_receipt", receipt_payload)
        expect_error(
            self,
            "binding-violation",
            contracts.validate_declared_bindings,
            manifest,
            {"apply_receipt": receipt},
        )

    def test_cleanup_must_bind_the_current_verification(self) -> None:
        cleanup = reseal(
            "cleanup_receipt",
            self.family["cleanup_receipt"],
            lambda payload: payload.update({"verification_id": ZERO_DIGEST}),
        )
        expect_error(
            self,
            "binding-violation",
            contracts.validate_declared_bindings,
            self.family["manifest"],
            {
                "verification": self.family["verification"],
                "cleanup_receipt": cleanup,
            },
        )

    def test_recovery_receipt_must_match_the_plan(self) -> None:
        receipt = reseal(
            "recovery_receipt",
            self.family["recovery_receipt"],
            lambda payload: payload["results"][0].update(
                {"operation_ids": [ZERO_DIGEST]}
            ),
        )
        expect_error(
            self,
            "binding-violation",
            contracts.validate_declared_bindings,
            self.family["manifest"],
            {
                "apply_receipt": self.family["apply_receipt"],
                "deployment_evidence": self.family["deployment_evidence"],
                "cleanup_receipt": self.family["cleanup_receipt"],
                "recovery_plan": self.family["recovery_plan"],
                "recovery_receipt": receipt,
            },
        )

    def test_unknown_binding_kind_is_rejected(self) -> None:
        expect_error(
            self,
            "unknown-kind",
            contracts.validate_declared_bindings,
            self.family["manifest"],
            {"manifest": self.family["manifest"]},
        )

    def test_deployment_report_refs_cannot_be_parent_and_child(self) -> None:
        payload = fixtures.build_deployment_evidence_payload(
            self.family["manifest"], self.family["apply_receipt"]
        )
        payload["projects"][0]["report_refs"].append(
            {
                "path": f"{fixtures.EVIDENCE_DIR}/alpha-smoke.json/details.json",
                "state": fixtures.file_state(103),
            }
        )

        expect_error(
            self,
            "semantic-violation",
            contracts.seal_document,
            "deployment_evidence",
            payload,
        )

    def test_deployment_report_refs_cannot_nest_across_projects(self) -> None:
        payload = fixtures.build_deployment_evidence_payload(
            self.family["manifest"], self.family["apply_receipt"]
        )
        payload["projects"][0]["report_refs"] = [
            {
                "path": f"{fixtures.EVIDENCE_DIR}/reports/run.json",
                "state": fixtures.file_state(103),
            }
        ]
        payload["projects"][1]["report_refs"] = [
            {
                "path": f"{fixtures.EVIDENCE_DIR}/reports/run.json/details.json",
                "state": fixtures.file_state(104),
            }
        ]

        expect_error(
            self,
            "semantic-violation",
            contracts.seal_document,
            "deployment_evidence",
            payload,
        )

    def test_projects_may_share_one_state_consistent_report(self) -> None:
        payload = fixtures.build_deployment_evidence_payload(
            self.family["manifest"], self.family["apply_receipt"]
        )
        shared = {
            "path": f"{fixtures.EVIDENCE_DIR}/reports/batch.json",
            "state": fixtures.file_state(103),
        }
        for project in payload["projects"]:
            project["report_refs"] = [copy.deepcopy(shared)]
        document = contracts.seal_document("deployment_evidence", payload)
        self.assertEqual(
            document["payload"]["projects"][0]["report_refs"],
            document["payload"]["projects"][1]["report_refs"],
        )
        payload["projects"][1]["report_refs"][0]["state"] = fixtures.file_state(104)
        expect_error(
            self,
            "semantic-violation",
            contracts.seal_document,
            "deployment_evidence",
            payload,
        )

    def test_stage_report_refs_cannot_overlap_manifest_targets(self) -> None:
        payload = fixtures.build_deployment_evidence_payload(
            self.family["manifest"], self.family["apply_receipt"]
        )
        payload["projects"][0]["report_refs"] = [
            {
                "path": fixtures.RESOURCES["r1"][1],
                "state": fixtures.file_state(103),
            }
        ]
        deployment = contracts.seal_document("deployment_evidence", payload)

        expect_error(
            self,
            "binding-violation",
            contracts.validate_declared_bindings,
            self.family["manifest"],
            {"deployment_evidence": deployment},
        )

    def test_stage_report_refs_cannot_overlap_manifest_inputs(self) -> None:
        payload = fixtures.build_deployment_evidence_payload(
            self.family["manifest"], self.family["apply_receipt"]
        )
        payload["projects"][0]["report_refs"] = [
            {
                "path": f"{fixtures.PUBLICATION_ORIGINAL['path']}/report.json",
                "state": fixtures.file_state(103),
            }
        ]
        deployment = contracts.seal_document("deployment_evidence", payload)

        expect_error(
            self,
            "binding-violation",
            contracts.validate_declared_bindings,
            self.family["manifest"],
            {"deployment_evidence": deployment},
        )


class CumulativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = fixtures.build_manifest()
        cls.full_receipt = fixtures.build_apply_receipt(cls.manifest)

    def partial_receipt(self):
        def mutate(payload):
            payload["status"] = "failed"
            alpha = payload["projects"][0]
            alpha["status"] = "failed"
            alpha["reason"] = "r2 write failed"
            alpha["nextStep"] = "retry the failed resources"
            alpha["private_results"] = [
                fixtures.build_resource_result("r1", "apply"),
                fixtures.build_resource_result("r2", "apply", "failed", "write failed"),
            ]
            retryable = alpha["private_results"][1]
            retryable["before"] = fixtures.resource_state("r2", "orig")
            retryable["after"] = fixtures.resource_state("r2", "orig")
            retryable["backup_ref"] = fixtures.backup_ref_of("r2", "orig")

        return reseal("apply_receipt", self.full_receipt, mutate)

    def retry_receipt(self, previous):
        payload = fixtures.build_apply_receipt_payload(self.manifest)
        payload["previous_receipt_id"] = previous["apply_id"]
        finished = previous["payload"]["finished_at"]
        payload["started_at"] = finished
        payload["finished_at"] = finished
        return contracts.seal_document("apply_receipt", payload)

    def test_retry_preserving_previous_successes_passes(self) -> None:
        previous = self.partial_receipt()
        current = self.retry_receipt(previous)
        contracts.validate_cumulative(previous, current, "apply_receipt")

    def test_dropping_a_previous_success_is_rejected(self) -> None:
        previous = self.partial_receipt()
        current = reseal(
            "apply_receipt",
            self.retry_receipt(previous),
            lambda payload: payload["projects"][0]["private_results"].pop(0),
        )
        error = expect_error(
            self,
            "cumulative-violation",
            contracts.validate_cumulative,
            previous,
            current,
            "apply_receipt",
        )
        self.assertEqual(error.exit_code, 3)

    def test_original_backup_reference_must_survive(self) -> None:
        previous = self.partial_receipt()

        def mutate(payload):
            payload["projects"][0]["private_results"][0]["backup_ref"] = {
                "path": "/private/backup/replaced",
                "state": fixtures.file_state(11),
            }

        current = reseal("apply_receipt", self.retry_receipt(previous), mutate)
        expect_error(
            self,
            "cumulative-violation",
            contracts.validate_cumulative,
            previous,
            current,
            "apply_receipt",
        )

    def test_retry_must_reference_the_supplied_previous_receipt(self) -> None:
        previous = self.partial_receipt()
        current = self.retry_receipt(self.full_receipt)
        expect_error(
            self,
            "cumulative-violation",
            contracts.validate_cumulative,
            previous,
            current,
            "apply_receipt",
        )

    def test_first_run_must_declare_a_null_previous_reference(self) -> None:
        contracts.validate_cumulative(None, self.full_receipt, "apply_receipt")
        expect_error(
            self,
            "cumulative-violation",
            contracts.validate_cumulative,
            None,
            self.retry_receipt(self.full_receipt),
            "apply_receipt",
        )

    def test_recovery_receipt_retry_keeps_completed_steps(self) -> None:
        family = fixtures.build_fixture_family()
        receipt = family["recovery_receipt"]
        payload = copy.deepcopy(receipt["payload"])
        keep = sorted(
            step["step_id"] for step in family["recovery_plan"]["payload"]["steps"][:6]
        )
        payload["completed_step_ids"] = keep
        payload["pending_step_ids"] = [
            step_id
            for step_id in receipt["payload"]["completed_step_ids"]
            if step_id not in keep
        ]
        payload["results"] = [r for r in payload["results"] if r["step_id"] in keep]
        payload["shared_results"] = [
            {
                **shared,
                "step_ids": [s for s in shared["step_ids"] if s in keep],
            }
            for shared in payload["shared_results"]
        ]
        payload["shared_results"] = [
            s for s in payload["shared_results"] if s["step_ids"]
        ]
        payload["status"] = "failed"
        payload["reason"] = "later step failed"
        payload["runtime_readiness"] = "not-verified"
        payload["report_refs"] = []
        payload["projects"][0]["status"] = "failed"
        payload["projects"][0]["reason"] = "later step failed"
        payload["projects"][0]["nextStep"] = "retry the plan"
        payload["projects"][1]["status"] = "failed"
        payload["projects"][1]["reason"] = "later step failed"
        payload["projects"][1]["nextStep"] = "retry the plan"
        partial = contracts.seal_document("recovery_receipt", payload)

        retry_payload = copy.deepcopy(receipt["payload"])
        retry_payload["previous_receipt_id"] = partial["receipt_id"]
        retry_payload["started_at"] = partial["payload"]["finished_at"]
        retry_payload["finished_at"] = partial["payload"]["finished_at"]
        retry = contracts.seal_document("recovery_receipt", retry_payload)
        contracts.validate_cumulative(partial, retry, "recovery_receipt")

        retry_payload = copy.deepcopy(partial["payload"])
        retry_payload["previous_receipt_id"] = partial["receipt_id"]
        retry_payload["started_at"] = partial["payload"]["finished_at"]
        retry_payload["finished_at"] = partial["payload"]["finished_at"]
        lost_step = keep[0]
        retry_payload["completed_step_ids"].remove(lost_step)
        retry_payload["pending_step_ids"].append(lost_step)
        retry_payload["results"] = [
            result
            for result in retry_payload["results"]
            if result["step_id"] != lost_step
        ]
        retry_payload["shared_results"] = [
            {
                **shared,
                "step_ids": [
                    step_id for step_id in shared["step_ids"] if step_id != lost_step
                ],
            }
            for shared in retry_payload["shared_results"]
        ]
        retry_payload["shared_results"] = [
            shared for shared in retry_payload["shared_results"] if shared["step_ids"]
        ]
        broken = contracts.seal_document("recovery_receipt", retry_payload)
        expect_error(
            self,
            "cumulative-violation",
            contracts.validate_cumulative,
            partial,
            broken,
            "recovery_receipt",
        )


class EnvelopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.family = fixtures.build_fixture_family()

    def test_every_phase_envelope_in_the_family_is_valid(self) -> None:
        for name in (
            "migration_envelope_plan",
            "migration_envelope_apply",
            "migration_envelope_verify",
            "migration_envelope_cleanup",
        ):
            with self.subTest(name=name):
                contracts.validate_document(self.family[name], "migration_envelope")
        for name in ("recovery_envelope_plan", "recovery_envelope_apply"):
            with self.subTest(name=name):
                contracts.validate_document(self.family[name], "recovery_envelope")

    def test_blocked_envelope_has_honest_null_ids_and_empty_artifact(self) -> None:
        envelope = contracts.make_envelope(
            "migration",
            "plan",
            "blocked",
            [],
            "publication decisions failed validation",
            "fix the decisions file and rerun plan",
        )
        self.assertEqual(envelope["migration"], {})
        self.assertIsNone(envelope["manifest_id"])
        contracts.validate_document(envelope, "migration_envelope")

    def test_blocked_envelope_requires_an_explanation(self) -> None:
        expect_error(
            self,
            "semantic-violation",
            contracts.make_envelope,
            "migration",
            "plan",
            "blocked",
            [],
            "",
            "",
        )

    def test_envelope_ids_must_match_the_artifact(self) -> None:
        expect_error(
            self,
            "semantic-violation",
            contracts.make_envelope,
            "migration",
            "plan",
            "planned",
            fixtures.envelope_projects("planned"),
            "",
            "",
            artifact=self.family["manifest"],
            identifiers={"manifest_id": ZERO_DIGEST},
        )

    def test_envelope_scope_must_match_the_artifact(self) -> None:
        expect_error(
            self,
            "semantic-violation",
            contracts.make_envelope,
            "migration",
            "apply",
            "applied",
            [fixtures.envelope_projects("applied")[0]],
            "",
            "",
            artifact=self.family["apply_receipt"],
            identifiers={"manifest_id": self.family["manifest"]["manifest_id"]},
        )

    def test_project_status_must_fit_the_phase(self) -> None:
        expect_error(
            self,
            "semantic-violation",
            contracts.make_envelope,
            "migration",
            "plan",
            "planned",
            fixtures.envelope_projects("restored"),
            "",
            "",
            artifact=self.family["manifest"],
            identifiers={"manifest_id": self.family["manifest"]["manifest_id"]},
        )

    def test_unexpected_identifier_keys_are_rejected(self) -> None:
        expect_error(
            self,
            "unknown-kind",
            contracts.make_envelope,
            "migration",
            "plan",
            "blocked",
            [],
            "reason",
            "next",
            identifiers={"plan_id": ZERO_DIGEST},
        )


class DeploymentResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.family = fixtures.build_fixture_family()

    def test_null_result_is_accepted(self) -> None:
        self.assertIsNone(contracts.validate_deployment_result(None))

    def test_complete_result_is_accepted(self) -> None:
        result = {
            "path": "/private/migration/deployment_evidence.json",
            "evidence": self.family["deployment_evidence"],
        }
        self.assertIs(contracts.validate_deployment_result(result), result)

    def test_result_requires_path_and_valid_evidence(self) -> None:
        expect_error(
            self,
            "schema-violation",
            contracts.validate_deployment_result,
            {"evidence": self.family["deployment_evidence"]},
        )
        broken = copy.deepcopy(self.family["deployment_evidence"])
        broken["deployment_id"] = ZERO_DIGEST
        expect_error(
            self,
            "id-mismatch",
            contracts.validate_deployment_result,
            {"path": "/private/migration/e.json", "evidence": broken},
        )

    def test_result_path_cannot_overlap_an_embedded_report(self) -> None:
        report_path = self.family["deployment_evidence"]["payload"]["projects"][0][
            "report_refs"
        ][0]["path"]
        expect_error(
            self,
            "semantic-violation",
            contracts.validate_deployment_result,
            {"path": report_path, "evidence": self.family["deployment_evidence"]},
        )

    def test_result_path_cannot_overlap_an_embedded_backup(self) -> None:
        backup_path = self.family["deployment_evidence"]["payload"]["projects"][0][
            "private_results"
        ][0]["backup_ref"]["path"]
        expect_error(
            self,
            "semantic-violation",
            contracts.validate_deployment_result,
            {"path": backup_path, "evidence": self.family["deployment_evidence"]},
        )


class JsonWriterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.family = fixtures.build_fixture_family()

    def write(self, value) -> str:
        stream = io.StringIO()
        contracts.write_json_response(value, stream)
        return stream.getvalue()

    def test_writer_emits_exactly_one_json_root(self) -> None:
        envelope = self.family["migration_envelope_plan"]
        output = self.write(envelope)
        self.assertTrue(output.endswith("\n"))
        self.assertEqual(output.count("\n"), 1)
        self.assertEqual(json.loads(output), json.loads(json.dumps(envelope)))

    def test_writer_validates_fixed_envelopes(self) -> None:
        broken = copy.deepcopy(self.family["migration_envelope_plan"])
        broken["manifest_id"] = ZERO_DIGEST
        expect_error(self, "semantic-violation", self.write, broken)

    def test_retired_trellis_fields_are_refused_not_aliased(self) -> None:
        for field in ("trellis", "trellisInit", "trellisProjectSetup"):
            with self.subTest(field=field):
                expect_error(
                    self, "retired-field", self.write, {field: {"status": "success"}}
                )

    def test_pass_through_payloads_keep_their_fields_and_numbers(self) -> None:
        payload = {"sbtdInit": {"status": "success", "projects": 2, "ratio": 0.5}}
        output = self.write(payload)
        decoded = json.loads(output)
        self.assertEqual(set(decoded), {"sbtdInit"})
        self.assertEqual(decoded["sbtdInit"]["ratio"], 0.5)

    def test_writer_rejects_non_object_roots(self) -> None:
        expect_error(self, "unexpected-type", self.write, ["not", "an", "object"])


class ErrorSanitizationTests(unittest.TestCase):
    def test_schema_errors_do_not_echo_rejected_values(self) -> None:
        secret = "/private/secret-token-9f8e7d"
        items = fixtures.build_publication_items()
        items[0]["approval"]["basis"] = secret
        items[0]["approval"]["scope"]["decision"] = "invalid-decision"
        error = expect_error(
            self,
            "schema-violation",
            contracts.validate_document,
            {"schema_version": 1, "items": items},
            "publication_decisions",
        )
        self.assertNotIn(secret, str(error))
        self.assertNotIn("is not of type", str(error))
        self.assertNotIn("invalid-decision", str(error))

    def test_id_mismatch_does_not_leak_digests(self) -> None:
        document = fixtures.build_manifest()
        declared = document["manifest_id"]
        forged = copy.deepcopy(document)
        forged["manifest_id"] = ZERO_DIGEST
        error = expect_error(
            self, "id-mismatch", contracts.validate_document, forged, "manifest"
        )
        self.assertNotIn(declared, str(error))
        self.assertNotIn(ZERO_DIGEST, str(error))

    def test_binding_errors_do_not_leak_digests(self) -> None:
        family = fixtures.build_fixture_family()
        raw = fixtures.fixture_raw_documents(family)
        raw["deployment_evidence"] = b"{}"
        error = expect_error(
            self,
            "binding-violation",
            contracts.validate_declared_bindings,
            family["manifest"],
            {"verification": family["verification"]},
            raw,
        )
        self.assertNotIn(
            family["verification"]["payload"]["deployment_evidence_hash"], str(error)
        )


class ValidatorAvailabilityTests(unittest.TestCase):
    def test_missing_jsonschema_fails_closed_without_breaking_pure_functions(
        self,
    ) -> None:
        module_path = (
            ROOT / "sbtd-workflow-onboard" / "scripts" / "onboard_contracts.py"
        )
        script = (
            "import importlib.util, json\n"
            "assert importlib.util.find_spec('jsonschema') is None\n"
            f"spec = importlib.util.spec_from_file_location('isolated_contracts', {str(module_path)!r})\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(module)\n"
            "try:\n"
            "    module.validate_document({'schema_version': 1, 'items': []}, 'publication_decisions')\n"
            "except module.ContractError as error:\n"
            "    assert error.code == 'validator-unavailable' and error.exit_code == 2\n"
            "    print(json.dumps({'validator': error.code, 'canonical': module.canonical_json_bytes({'b': 2, 'a': 1}).decode()}))\n"
            "else:\n"
            "    raise AssertionError('missing dependency was accepted')\n"
        )
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-c", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {"validator": "validator-unavailable", "canonical": '{"a":1,"b":2}'},
        )


class FixtureRoundTripTests(unittest.TestCase):
    KIND_BY_FILE: ClassVar[dict[str, str]] = {
        "publication_decisions": "publication_decisions",
        "manifest": "manifest",
        "apply_receipt": "apply_receipt",
        "deployment_evidence": "deployment_evidence",
        "verification": "verification",
        "cleanup_receipt": "cleanup_receipt",
        "recovery_plan": "recovery_plan",
        "recovery_receipt": "recovery_receipt",
        "migration_envelope_plan": "migration_envelope",
        "migration_envelope_apply": "migration_envelope",
        "migration_envelope_verify": "migration_envelope",
        "migration_envelope_cleanup": "migration_envelope",
        "recovery_envelope_plan": "recovery_envelope",
        "recovery_envelope_apply": "recovery_envelope",
    }

    def test_serialized_family_round_trips_through_load_document(self) -> None:
        with tempfile.TemporaryDirectory(prefix="onboard-contract-fixtures-") as tmp:
            written = fixtures.write_fixture_family(Path(tmp))
            self.assertEqual(set(written), set(self.KIND_BY_FILE))
            loaded = {
                name: contracts.load_document(
                    path.read_bytes(), self.KIND_BY_FILE[name]
                )
                for name, path in written.items()
            }
            raw = {
                kind: written[kind].read_bytes()
                for kind in (
                    "manifest",
                    "apply_receipt",
                    "deployment_evidence",
                    "cleanup_receipt",
                )
            }
            contracts.validate_declared_bindings(
                loaded["manifest"],
                {
                    kind: loaded[kind]
                    for kind in (
                        "apply_receipt",
                        "deployment_evidence",
                        "verification",
                        "cleanup_receipt",
                        "recovery_plan",
                        "recovery_receipt",
                    )
                },
                raw,
            )
            # File bytes are exactly the canonical bytes used for raw bindings.
            evidence_hash = hashlib.sha256(
                written["deployment_evidence"].read_bytes()
            ).hexdigest()
            self.assertEqual(
                loaded["verification"]["payload"]["deployment_evidence_hash"],
                evidence_hash,
            )


class ExplicitInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.family = fixtures.build_fixture_family()

    def test_required_projection_cannot_be_private_only(self) -> None:
        document = fixtures.build_publication_decisions()
        document["items"][1]["required"] = True
        with self.assertRaises(ContractError):
            contracts.validate_document(document, "publication_decisions")

    def test_non_adjacent_ancestor_targets_are_rejected(self) -> None:
        seed = fixtures.build_publication_items()[0]
        items = []
        for index, target in enumerate(
            ("/shared/a", "/shared/a-other", "/shared/a/child")
        ):
            item = copy.deepcopy(seed)
            item["item_id"] = f"projection-{index}"
            item["target_path"] = target
            item["approval"]["scope"]["target_path"] = target
            items.append(item)
        with self.assertRaises(ContractError):
            contracts.validate_document(
                {"schema_version": 1, "items": items}, "publication_decisions"
            )

    def test_successful_result_requires_its_original_before_backup(self) -> None:
        for backup in (None, fixtures._file_ref("/private/backup/wrong", 999)):
            with self.subTest(backup_missing=backup is None):
                payload = copy.deepcopy(self.family["apply_receipt"]["payload"])
                payload["projects"][0]["private_results"][0]["backup_ref"] = backup
                with self.assertRaises(ContractError):
                    contracts.seal_document("apply_receipt", payload)

    def test_recovery_restore_requires_a_matching_backup(self) -> None:
        for backup in (None, fixtures._file_ref("/private/backup/wrong", 999)):
            with self.subTest(backup_missing=backup is None):
                payload = copy.deepcopy(self.family["recovery_plan"]["payload"])
                payload["steps"][0]["backup_ref"] = backup
                with self.assertRaises(ContractError):
                    contracts.seal_document("recovery_plan", payload)

    def test_phase_after_requires_a_declared_predecessor(self) -> None:
        payload = copy.deepcopy(self.family["manifest"]["payload"])
        resource = fixtures.resource_id_of("r1")
        payload["projects"][0]["private_operations"] = [
            operation
            for operation in payload["projects"][0]["private_operations"]
            if not (
                operation["resource_id"] == resource and operation["phase"] == "apply"
            )
        ]
        with self.assertRaises(ContractError):
            contracts.seal_document("manifest", payload)

    def test_same_target_cannot_claim_conflicting_owner_formats(self) -> None:
        payload = copy.deepcopy(self.family["manifest"]["payload"])
        operation = copy.deepcopy(payload["projects"][0]["private_operations"][0])
        operation["owner_kind"] = "toml"
        operation["resource_id"] = contracts.resource_id("toml", operation["target"])
        operation["operation_id"] = contracts.operation_id(
            operation["phase"], operation["resource_id"], operation["selector"]
        )
        payload["projects"][0]["private_operations"].append(operation)
        with self.assertRaises(ContractError):
            contracts.seal_document("manifest", payload)

    def test_private_operation_cannot_target_another_project(self) -> None:
        payload = copy.deepcopy(self.family["manifest"]["payload"])
        operation = copy.deepcopy(payload["projects"][0]["private_operations"][0])
        operation["target"] = fixtures.BETA + "/foreign.json"
        operation["resource_id"] = contracts.resource_id(
            operation["owner_kind"], operation["target"]
        )
        operation["operation_id"] = contracts.operation_id(
            operation["phase"], operation["resource_id"], operation["selector"]
        )
        payload["projects"][0]["private_operations"] = [operation]
        with self.assertRaises(ContractError):
            contracts.seal_document("manifest", payload)

    def test_backup_root_cannot_be_inside_a_selected_project(self) -> None:
        payload = copy.deepcopy(self.family["manifest"]["payload"])
        payload["backup_root"] = fixtures.ALPHA + "/.sbtd/backups"
        with self.assertRaises(ContractError):
            contracts.seal_document("manifest", payload)

    def test_recovery_snapshot_must_match_the_first_inverse_step(self) -> None:
        payload = copy.deepcopy(self.family["recovery_plan"]["payload"])
        payload["resources"][0]["state"] = fixtures.file_state(999)
        with self.assertRaises(ContractError):
            contracts.seal_document("recovery_plan", payload)

    def test_raw_bytes_cannot_describe_a_different_supplied_record(self) -> None:
        payload = copy.deepcopy(self.family["apply_receipt"]["payload"])
        payload["finished_at"] = fixtures.T9
        other = contracts.seal_document("apply_receipt", payload)
        self.assertNotEqual(other["apply_id"], self.family["apply_receipt"]["apply_id"])
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.family["manifest"],
                {"apply_receipt": self.family["apply_receipt"]},
                {"apply_receipt": contracts.canonical_json_bytes(other)},
            )

    def test_project_success_cannot_hide_a_failed_private_result(self) -> None:
        payload = copy.deepcopy(self.family["apply_receipt"]["payload"])
        result = payload["projects"][0]["private_results"][0]
        result["status"] = "failed"
        result["error"] = "write failed"
        with self.assertRaises(ContractError):
            contracts.seal_document("apply_receipt", payload)

    def test_unverified_deployment_still_requires_complete_operations(self) -> None:
        payload = copy.deepcopy(self.family["deployment_evidence"]["payload"])
        payload["status"] = "not-verified"
        for project in payload["projects"]:
            project["status"] = "not-verified"
            project["report_refs"] = []
        payload["projects"][0]["private_results"] = []
        document = contracts.seal_document("deployment_evidence", payload)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.family["manifest"], {"deployment_evidence": document}
            )

    def test_failed_attempt_cannot_replace_known_original_backup(self) -> None:
        payload = copy.deepcopy(self.family["apply_receipt"]["payload"])
        project = payload["projects"][0]
        result = project["private_results"][0]
        result["status"] = "failed"
        result["after"] = copy.deepcopy(result["before"])
        result["error"] = "write failed before target changed"
        project["status"] = "failed"
        project["reason"] = "private write failed"
        project["nextStep"] = "inspect and retry"
        payload["status"] = "failed"
        previous = contracts.seal_document("apply_receipt", payload)
        current_payload = copy.deepcopy(payload)
        current_payload["previous_receipt_id"] = previous["apply_id"]
        current_payload["started_at"] = previous["payload"]["finished_at"]
        current_payload["finished_at"] = previous["payload"]["finished_at"]
        changed = current_payload["projects"][0]["private_results"][0]
        changed["before"] = fixtures.file_state(999)
        changed["after"] = fixtures.file_state(999)
        changed["backup_ref"] = fixtures._file_ref("/private/backup/replaced", 999)
        current = contracts.seal_document("apply_receipt", current_payload)
        with self.assertRaises(ContractError):
            contracts.validate_cumulative(previous, current, "apply_receipt")

    def test_successful_deployment_cannot_omit_report_references(self) -> None:
        payload = copy.deepcopy(self.family["deployment_evidence"]["payload"])
        payload["projects"][0]["report_refs"] = []
        with self.assertRaises(ContractError):
            contracts.seal_document("deployment_evidence", payload)

    def test_single_dependent_shared_recovery_keeps_shared_ownership(self) -> None:
        manifest_payload = copy.deepcopy(self.family["manifest"]["payload"])
        for operation in manifest_payload["shared_operations"]:
            operation["dependent_projects"] = [fixtures.ALPHA]
        manifest_payload["projects"][1]["shared_operation_ids"] = []
        for shared_root in manifest_payload["shared_roots"]:
            shared_root["dependent_projects"] = [fixtures.ALPHA]
        manifest = contracts.seal_document("manifest", manifest_payload)
        shared_resource = fixtures.resource_id_of("s1")
        sources = {}
        for kind in ("apply_receipt", "deployment_evidence", "cleanup_receipt"):
            payload = copy.deepcopy(self.family[kind]["payload"])
            payload["manifest_id"] = manifest["manifest_id"]
            payload["shared_results"][0]["dependent_projects"] = [fixtures.ALPHA]
            payload["projects"][1]["shared_operation_ids"] = []
            if kind != "apply_receipt":
                payload["apply_id"] = sources["apply_receipt"]["apply_id"]
            if kind == "cleanup_receipt":
                verification_payload = fixtures.build_verification_payload(
                    manifest, sources["apply_receipt"], sources["deployment_evidence"]
                )
                verification_payload["shared_cleanup_candidates"][0][
                    "dependent_projects"
                ] = [fixtures.ALPHA]
                sources["verification"] = contracts.seal_document(
                    "verification", verification_payload
                )
                payload["verification_id"] = sources["verification"]["verification_id"]
                payload["deployment_evidence_hash"] = fixtures.raw_digest_of(
                    sources["deployment_evidence"]
                )
            sources[kind] = contracts.seal_document(kind, payload)

        plan_payload = copy.deepcopy(self.family["recovery_plan"]["payload"])
        plan_payload["manifest_id"] = manifest["manifest_id"]
        plan_payload["input_evidence"] = fixtures.build_input_evidence(
            manifest,
            sources["apply_receipt"],
            sources["deployment_evidence"],
            sources["cleanup_receipt"],
        )
        renamed_steps = {
            step["step_id"]: contracts.recovery_step_id(
                manifest["manifest_id"], step["phase"], step["resource_id"]
            )
            for step in plan_payload["steps"]
        }
        for resource in plan_payload["resources"]:
            if resource["resource_id"] == shared_resource:
                resource["dependent_projects"] = [fixtures.ALPHA]
        for step in plan_payload["steps"]:
            step["step_id"] = renamed_steps[step["step_id"]]
            step["depends_on"] = [renamed_steps[key] for key in step["depends_on"]]
            if step["resource_id"] == shared_resource:
                step["dependent_projects"] = [fixtures.ALPHA]
        plan = contracts.seal_document("recovery_plan", plan_payload)
        contracts.validate_declared_bindings(
            manifest, {**sources, "recovery_plan": plan}
        )

        missing_ownership = copy.deepcopy(plan_payload)
        missing_ownership["shared_operation_ids"] = []
        bad_plan = contracts.seal_document("recovery_plan", missing_ownership)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                manifest, {**sources, "recovery_plan": bad_plan}
            )

        receipt_payload = copy.deepcopy(self.family["recovery_receipt"]["payload"])
        receipt_payload["manifest_id"] = manifest["manifest_id"]
        receipt_payload["plan_id"] = plan["plan_id"]
        receipt_payload["input_evidence"] = copy.deepcopy(
            plan_payload["input_evidence"]
        )
        for result in receipt_payload["results"]:
            result["step_id"] = renamed_steps[result["step_id"]]
            if result["resource_id"] == shared_resource:
                result["dependent_projects"] = [fixtures.ALPHA]
        receipt_payload["completed_step_ids"] = [
            renamed_steps[key] for key in receipt_payload["completed_step_ids"]
        ]
        for shared in receipt_payload["shared_results"]:
            shared["dependent_projects"] = [fixtures.ALPHA]
            shared["step_ids"] = [renamed_steps[key] for key in shared["step_ids"]]
        receipt = contracts.seal_document(
            "recovery_receipt", copy.deepcopy(receipt_payload)
        )
        contracts.validate_declared_bindings(
            manifest, {**sources, "recovery_plan": plan, "recovery_receipt": receipt}
        )
        receipt_payload["shared_results"] = []
        bad_receipt = contracts.seal_document("recovery_receipt", receipt_payload)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                manifest,
                {**sources, "recovery_plan": plan, "recovery_receipt": bad_receipt},
            )

    def test_recovery_success_requires_preservation_completion_and_reports(
        self,
    ) -> None:
        missing_protection = copy.deepcopy(self.family["recovery_receipt"]["payload"])
        protected = next(
            result
            for result in missing_protection["results"]
            if result["before"]["type"] != "absent"
        )
        protected["protection_ref"] = None

        incomplete = copy.deepcopy(self.family["recovery_receipt"]["payload"])
        unexecuted = next(
            result
            for result in incomplete["results"]
            if result["dependent_projects"] == [fixtures.ALPHA]
        )
        incomplete["results"].remove(unexecuted)
        incomplete["completed_step_ids"].remove(unexecuted["step_id"])
        incomplete["pending_step_ids"].append(unexecuted["step_id"])

        no_reports = copy.deepcopy(self.family["recovery_receipt"]["payload"])
        no_reports["runtime_readiness"] = "verified"
        no_reports["report_refs"] = []
        for boundary, payload in (
            ("original protection", missing_protection),
            ("pending step", incomplete),
            ("runtime evidence", no_reports),
        ):
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.seal_document("recovery_receipt", payload)

    def test_envelope_cannot_mask_failed_artifact_or_project_status(self) -> None:
        payload = copy.deepcopy(self.family["apply_receipt"]["payload"])
        payload["status"] = "failed"
        payload["projects"][0].update(
            status="failed",
            reason="verification failed",
            nextStep="inspect the project",
        )
        failed = contracts.seal_document("apply_receipt", payload)
        successful_summaries = [
            {"root": project["root"], "status": "applied", "reason": "", "nextStep": ""}
            for project in payload["projects"]
        ]
        with self.assertRaises(ContractError):
            contracts.make_envelope(
                "migration",
                "apply",
                "applied",
                successful_summaries,
                "",
                "",
                artifact=failed,
                identifiers={"manifest_id": self.family["manifest"]["manifest_id"]},
            )

        failed_summary = [
            {
                "root": fixtures.ALPHA,
                "status": "failed",
                "reason": "source inspection failed",
                "nextStep": "repair the source",
            }
        ]
        with self.assertRaises(ContractError):
            contracts.make_envelope(
                "migration",
                "plan",
                "blocked",
                failed_summary,
                "waiting for source",
                "repair the source",
            )

    def test_manifest_preserves_embedded_publication_approval_and_scope(self) -> None:
        for boundary in ("approval drift", "foreign target", "in-project candidate"):
            payload = copy.deepcopy(self.family["manifest"]["payload"])
            item = payload["publication_decisions"]["items"][0]
            if boundary == "approval drift":
                item["approval"]["scope"]["decision"] = "redact"
            elif boundary == "foreign target":
                item["target_path"] = "/private/outside/published.md"
                item["approval"]["scope"]["target_path"] = item["target_path"]
            else:
                item["candidate_ref"]["path"] = fixtures.ALPHA + "/.sbtd/candidate.md"
                item["approval"]["scope"]["candidate_ref"] = copy.deepcopy(
                    item["candidate_ref"]
                )
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.seal_document("manifest", payload)

    def test_partial_stage_references_observed_results_and_preserves_project_truth(
        self,
    ) -> None:
        payload = copy.deepcopy(self.family["deployment_evidence"]["payload"])
        payload["status"] = "blocked"
        payload["shared_results"] = []
        for project in payload["projects"]:
            project.update(
                status="blocked",
                reason="required tool unavailable",
                nextStep="prepare the tool",
                private_results=[],
                shared_operation_ids=[],
                report_refs=[],
            )
        blocked = contracts.seal_document("deployment_evidence", payload)
        contracts.validate_declared_bindings(
            self.family["manifest"], {"deployment_evidence": blocked}
        )
        payload["projects"][0]["shared_operation_ids"] = [
            self.family["deployment_evidence"]["payload"]["projects"][0][
                "shared_operation_ids"
            ][0]
        ]
        dangling = contracts.seal_document("deployment_evidence", payload)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.family["manifest"], {"deployment_evidence": dangling}
            )

        mixed = copy.deepcopy(self.family["apply_receipt"]["payload"])
        mixed["status"] = "failed"
        mixed["projects"][1].update(
            status="failed",
            reason="private operation failed",
            nextStep="inspect the failure",
        )
        mixed["projects"][0]["private_results"] = []
        incomplete_success = contracts.seal_document("apply_receipt", mixed)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.family["manifest"], {"apply_receipt": incomplete_success}
            )

    def test_retry_cannot_switch_its_bound_stage_or_recovery_plan(self) -> None:
        for kind, id_key, previous_key, binding in (
            (
                "deployment_evidence",
                "deployment_id",
                "previous_deployment_id",
                "apply_id",
            ),
            ("cleanup_receipt", "cleanup_id", "previous_receipt_id", "verification_id"),
            ("recovery_receipt", "receipt_id", "previous_receipt_id", "plan_id"),
        ):
            previous = self.family[kind]
            payload = copy.deepcopy(previous["payload"])
            payload[previous_key] = previous[id_key]
            payload["started_at"] = previous["payload"]["finished_at"]
            payload["finished_at"] = previous["payload"]["finished_at"]
            payload[binding] = fixtures.digest_number(999)
            self.assertNotEqual(payload[binding], previous["payload"][binding])
            current = contracts.seal_document(kind, payload)
            with self.subTest(kind=kind), self.assertRaises(ContractError):
                contracts.validate_cumulative(previous, current, kind)

    def test_successful_recovery_result_must_match_the_planned_state(self) -> None:
        payload = copy.deepcopy(self.family["recovery_receipt"]["payload"])
        payload["results"][0]["after"] = fixtures.file_state(999)
        changed = contracts.seal_document("recovery_receipt", payload)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.family["manifest"],
                {
                    "apply_receipt": self.family["apply_receipt"],
                    "deployment_evidence": self.family["deployment_evidence"],
                    "cleanup_receipt": self.family["cleanup_receipt"],
                    "recovery_plan": self.family["recovery_plan"],
                    "recovery_receipt": changed,
                },
            )

    def test_recovery_result_step_reference_retains_its_stable_identity(self) -> None:
        payload = copy.deepcopy(self.family["recovery_receipt"]["payload"])
        result = next(
            result
            for result in payload["results"]
            if result["dependent_projects"] == [fixtures.ALPHA]
        )
        original = result["step_id"]
        result["step_id"] = fixtures.digest_number(999)
        payload["completed_step_ids"] = [
            result["step_id"] if key == original else key
            for key in payload["completed_step_ids"]
        ]
        with self.assertRaises(ContractError):
            contracts.seal_document("recovery_receipt", payload)


class IndependentReviewRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.family = fixtures.build_fixture_family()
        cls.manifest = cls.family["manifest"]
        cls.apply_receipt = cls.family["apply_receipt"]
        cls.deployment = cls.family["deployment_evidence"]
        cls.verification = cls.family["verification"]
        cls.cleanup = cls.family["cleanup_receipt"]
        cls.plan = cls.family["recovery_plan"]
        cls.receipt = cls.family["recovery_receipt"]

    def test_result_states_and_backups_must_match_declared_requirements(self) -> None:
        for kind in ("apply_receipt", "deployment_evidence", "cleanup_receipt"):
            payload = copy.deepcopy(self.family[kind]["payload"])
            result = payload["projects"][0]["private_results"][0]
            result["before"] = fixtures.file_state(999)
            result["backup_ref"] = copy.deepcopy(result["backup_ref"])
            result["backup_ref"]["state"] = copy.deepcopy(result["before"])
            document = contracts.seal_document(kind, payload)
            documents = {kind: document}
            if kind != "apply_receipt":
                documents["apply_receipt"] = self.apply_receipt
            if kind == "cleanup_receipt":
                documents["deployment_evidence"] = self.deployment
            with self.subTest(kind=kind), self.assertRaises(ContractError):
                contracts.validate_declared_bindings(self.manifest, documents)

    def test_partial_results_preserve_known_backup_and_protection_states(self) -> None:
        for unknown_before in (False, True):
            payload = copy.deepcopy(self.apply_receipt["payload"])
            project = payload["projects"][0]
            project.update(status="failed", reason="write failed", nextStep="inspect")
            payload["status"] = "failed"
            result = project["private_results"][0]
            result.update(status="failed", error="write failed")
            if unknown_before:
                result["before"] = None
            else:
                result["backup_ref"]["state"] = fixtures.file_state(999)
            with (
                self.subTest(unknown_before=unknown_before),
                self.assertRaises(ContractError),
            ):
                contracts.seal_document("apply_receipt", payload)

        payload = copy.deepcopy(self.receipt["payload"])
        result = next(
            result
            for result in payload["results"]
            if result["protection_ref"] is not None
        )
        result.update(status="failed", error="restore failed")
        result["protection_ref"]["state"] = fixtures.file_state(999)
        payload["completed_step_ids"].remove(result["step_id"])
        payload["pending_step_ids"].append(result["step_id"])
        payload["status"] = "failed"
        payload["reason"] = "restore failed"
        for project in payload["projects"]:
            project.update(status="failed", reason="restore failed", nextStep="inspect")
        with self.assertRaises(ContractError):
            contracts.seal_document("recovery_receipt", payload)

    def test_downstream_artifacts_require_successful_supplied_predecessors(
        self,
    ) -> None:
        for predecessor in (
            "apply_receipt",
            "deployment_evidence",
            "verification",
            "recovery_plan",
        ):
            payload = copy.deepcopy(self.family[predecessor]["payload"])
            payload["status"] = "blocked"
            if predecessor == "recovery_plan":
                payload["conflicts"] = ["resource state changed"]
            else:
                payload["projects"][0].update(
                    status="blocked", reason="waiting", nextStep="prepare"
                )
            failed = contracts.seal_document(predecessor, payload)
            if predecessor == "apply_receipt":
                downstream = fixtures.build_deployment_evidence(self.manifest, failed)
                documents = {predecessor: failed, "deployment_evidence": downstream}
            elif predecessor == "deployment_evidence":
                downstream = fixtures.build_verification(
                    self.manifest, self.apply_receipt, failed
                )
                documents = {predecessor: failed, "verification": downstream}
            elif predecessor == "verification":
                downstream = fixtures.build_cleanup_receipt(
                    self.manifest, self.apply_receipt, self.deployment, failed
                )
                documents = {predecessor: failed, "cleanup_receipt": downstream}
            else:
                receipt_payload = copy.deepcopy(self.receipt["payload"])
                receipt_payload["plan_id"] = failed["plan_id"]
                downstream = contracts.seal_document(
                    "recovery_receipt", receipt_payload
                )
                documents = {
                    "apply_receipt": self.apply_receipt,
                    "deployment_evidence": self.deployment,
                    "cleanup_receipt": self.cleanup,
                    predecessor: failed,
                    "recovery_receipt": downstream,
                }
            with (
                self.subTest(predecessor=predecessor),
                self.assertRaises(ContractError),
            ):
                contracts.validate_declared_bindings(self.manifest, documents)

    def test_recovery_steps_must_derive_from_supplied_stage_results(self) -> None:
        payload = copy.deepcopy(self.plan["payload"])
        payload["steps"][0]["expected_current"] = fixtures.file_state(999)
        payload["resources"][0]["state"] = copy.deepcopy(
            payload["steps"][0]["expected_current"]
        )
        plan = contracts.seal_document("recovery_plan", payload)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.manifest,
                {
                    "apply_receipt": self.apply_receipt,
                    "deployment_evidence": self.deployment,
                    "cleanup_receipt": self.cleanup,
                    "recovery_plan": plan,
                },
            )

    def test_failed_resource_cannot_be_downgraded_to_blocked_project(self) -> None:
        payload = copy.deepcopy(self.apply_receipt["payload"])
        result = payload["projects"][0]["private_results"][0]
        result["status"] = "failed"
        result["error"] = "private write failed"
        payload["projects"][0].update(
            status="blocked", reason="private write failed", nextStep="inspect"
        )
        payload["status"] = "blocked"
        with self.assertRaises(ContractError):
            contracts.seal_document("apply_receipt", payload)

    def test_shared_operations_require_an_unambiguous_shared_root(self) -> None:
        for boundary in (
            "absent root",
            "target outside",
            "ambiguous roots",
            "wrong closure",
        ):
            payload = copy.deepcopy(self.manifest["payload"])
            # Change only the root declaration; operation identities remain valid.
            if boundary == "absent root":
                payload["shared_roots"] = []
            elif boundary == "target outside":
                payload["shared_roots"][0]["path"] = "/private/other"
            elif boundary == "ambiguous roots":
                payload["shared_roots"].append(
                    {
                        "kind": "home",
                        "path": "/private/home",
                        "dependent_projects": list(fixtures.BOTH),
                    }
                )
            else:
                payload["shared_roots"][0]["dependent_projects"] = [fixtures.ALPHA]
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.seal_document("manifest", payload)

    def test_shared_root_logical_skills_root_stays_inside_its_root(self) -> None:
        for skills_root in (
            "/private/home/.codex/skills",
            "/private/home/.codex/nested/skills",
        ):
            payload = copy.deepcopy(self.manifest["payload"])
            payload["shared_roots"][0]["skills_root"] = skills_root
            with self.subTest(skills_root=skills_root):
                contracts.seal_document("manifest", payload)

    def test_shared_root_logical_skills_root_rejects_escape_or_self(self) -> None:
        for boundary, skills_root in (
            ("sibling", "/private/home/.codex-skills"),
            ("ancestor", "/private/home"),
            ("self", "/private/home/.codex"),
            ("relative", "skills"),
            ("unnormalized", "/private/home/.codex/../.codex/skills"),
        ):
            payload = copy.deepcopy(self.manifest["payload"])
            payload["shared_roots"][0]["skills_root"] = skills_root
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.seal_document("manifest", payload)

    def test_skills_kind_root_cannot_declare_a_logical_skills_root(self) -> None:
        payload = copy.deepcopy(self.manifest["payload"])
        payload["shared_roots"][0]["kind"] = "skills"
        payload["shared_roots"][0]["skills_root"] = "/private/home/.codex/skills"
        with self.assertRaises(ContractError):
            contracts.seal_document("manifest", payload)

    def test_shared_roots_reject_competing_logical_skills_roots(self) -> None:
        for boundary in ("standalone plus annotation", "two annotations"):
            payload = copy.deepcopy(self.manifest["payload"])
            payload["shared_roots"][0]["skills_root"] = "/private/home/.codex/user"
            if boundary == "standalone plus annotation":
                payload["shared_roots"].append(
                    {
                        "kind": "skills",
                        "path": "/private/home/.agent/skills",
                        "dependent_projects": list(fixtures.BOTH),
                    }
                )
            else:
                payload["shared_roots"].append(
                    {
                        "kind": "omp-home",
                        "path": "/private/home/.omp",
                        "skills_root": "/private/home/.omp/skills",
                        "dependent_projects": list(fixtures.BOTH),
                    }
                )
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.seal_document("manifest", payload)

    def test_matching_standalone_and_annotation_share_one_logical_root(self) -> None:
        payload = copy.deepcopy(self.manifest["payload"])
        payload["shared_roots"][0]["skills_root"] = "/private/home/.codex/skills"
        payload["shared_roots"].append(
            {
                "kind": "skills",
                "path": "/private/home/.codex/skills",
                "dependent_projects": list(fixtures.BOTH),
            }
        )
        contracts.seal_document("manifest", payload)

    def test_receipt_scope_and_project_outcomes_must_match_its_plan(self) -> None:
        for boundary in ("scope", "evidence", "project result"):
            payload = copy.deepcopy(self.receipt["payload"])
            if boundary == "scope":
                payload["projects"] = [payload["projects"][0]]
            elif boundary == "evidence":
                payload["input_evidence"]["manifest"]["path"] = (
                    "/private/other/manifest.json"
                )
            else:
                dependent = next(
                    result
                    for result in payload["results"]
                    if result["phase"] == "apply"
                    and result["dependent_projects"] == [fixtures.ALPHA]
                )
                dependent["status"] = "failed"
                dependent["error"] = "restore failed"
                payload["completed_step_ids"].remove(dependent["step_id"])
                payload["pending_step_ids"].append(dependent["step_id"])
                payload["status"] = "failed"
                payload["reason"] = "restore failed"
                payload["projects"][1].update(
                    status="failed", reason="restore failed", nextStep="inspect"
                )
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                receipt = contracts.seal_document("recovery_receipt", payload)
                contracts.validate_declared_bindings(
                    self.manifest,
                    {
                        "apply_receipt": self.apply_receipt,
                        "deployment_evidence": self.deployment,
                        "cleanup_receipt": self.cleanup,
                        "recovery_plan": self.plan,
                        "recovery_receipt": receipt,
                    },
                )

    def test_failed_project_records_require_explanatory_diagnostics(self) -> None:
        payload = copy.deepcopy(self.apply_receipt["payload"])
        project = payload["projects"][0]
        project.update(status="failed", reason="", nextStep="")
        result = project["private_results"][0]
        result["status"] = "failed"
        result["error"] = "write failed"
        payload["status"] = "failed"
        with self.assertRaises(ContractError):
            contracts.seal_document("apply_receipt", payload)

    def test_known_partial_write_remains_recoverable_but_noop_does_not(self) -> None:
        for outcome in ("failed", "blocked"):
            cleanup_payload = copy.deepcopy(self.cleanup["payload"])
            result = cleanup_payload["projects"][0]["private_results"][0]
            result.update(status=outcome, error="write did not finish")
            cleanup_payload["projects"][0].update(
                status=outcome, reason="write did not finish", nextStep="recover"
            )
            cleanup_payload["status"] = outcome
            cleanup = contracts.seal_document("cleanup_receipt", cleanup_payload)
            plan = fixtures.build_recovery_plan(
                self.manifest, self.apply_receipt, self.deployment, cleanup
            )
            documents = {
                "apply_receipt": self.apply_receipt,
                "deployment_evidence": self.deployment,
                "cleanup_receipt": cleanup,
                "recovery_plan": plan,
            }
            with self.subTest(outcome=outcome):
                self.assertEqual(
                    contracts.validate_declared_bindings(self.manifest, documents)[
                        "recovery_plan"
                    ],
                    plan,
                )

            result["after"] = copy.deepcopy(result["before"])
            cleanup = contracts.seal_document("cleanup_receipt", cleanup_payload)
            plan_payload = fixtures.build_recovery_plan_payload(
                self.manifest, self.apply_receipt, self.deployment, cleanup
            )
            plan_payload["steps"][0]["expected_current"] = copy.deepcopy(
                result["after"]
            )
            plan_payload["resources"][0]["state"] = copy.deepcopy(result["after"])
            with self.subTest(noop=outcome), self.assertRaises(ContractError):
                plan = contracts.seal_document("recovery_plan", plan_payload)
                documents.update(cleanup_receipt=cleanup, recovery_plan=plan)
                contracts.validate_declared_bindings(self.manifest, documents)

    def test_recovery_can_bind_only_the_proven_apply_stage(self) -> None:
        payload = copy.deepcopy(self.plan["payload"])
        payload["input_evidence"]["deployment_evidence"] = None
        payload["input_evidence"]["cleanup_receipt"] = None
        payload["steps"] = [
            step for step in payload["steps"] if step["phase"] == "apply"
        ]
        by_resource = {step["resource_id"]: step for step in payload["steps"]}
        for step in payload["steps"]:
            step["depends_on"] = []
        for resource in payload["resources"]:
            step = by_resource[resource["resource_id"]]
            resource["operation_ids"] = list(step["operation_ids"])
            resource["state"] = copy.deepcopy(step["expected_current"])
        payload["shared_operation_ids"] = list(
            by_resource[fixtures.resource_id_of("s1")]["operation_ids"]
        )
        plan = contracts.seal_document("recovery_plan", payload)
        self.assertEqual(
            contracts.validate_declared_bindings(
                self.manifest,
                {"apply_receipt": self.apply_receipt, "recovery_plan": plan},
            )["recovery_plan"],
            plan,
        )


class SecondReviewRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.family = fixtures.build_fixture_family()

    def test_cleanup_cannot_skip_a_declared_deployment(self) -> None:
        payload = copy.deepcopy(self.family["manifest"]["payload"])
        operation = next(
            op
            for op in payload["projects"][0]["private_operations"]
            if op["phase"] == "cleanup"
            and op["resource_id"] == fixtures.resource_id_of("r1")
        )
        operation["before_requirement"]["phase"] = "apply"
        with self.assertRaises(ContractError):
            contracts.seal_document("manifest", payload)

    def test_selectors_of_one_phase_resource_require_one_precondition(self) -> None:
        payload = copy.deepcopy(self.family["manifest"]["payload"])
        operation = copy.deepcopy(payload["projects"][0]["private_operations"][0])
        operation["selector"] = "another-entry"
        operation["ownership"]["key_path"] = ["other"]
        operation["operation_id"] = contracts.operation_id(
            operation["phase"], operation["resource_id"], operation["selector"]
        )
        operation["before_requirement"]["state"] = fixtures.file_state(999)
        payload["projects"][0]["private_operations"].append(operation)
        with self.assertRaises(ContractError):
            contracts.seal_document("manifest", payload)

    def test_completed_stages_cannot_switch_the_manifest_revision(self) -> None:
        manifest_payload = copy.deepcopy(self.family["manifest"]["payload"])
        manifest_payload["projects"][0].update(source_ref="main", head="a" * 40)
        manifest = contracts.seal_document("manifest", manifest_payload)
        for kind in (
            "apply_receipt",
            "deployment_evidence",
            "verification",
            "cleanup_receipt",
        ):
            payload = copy.deepcopy(self.family[kind]["payload"])
            payload["manifest_id"] = manifest["manifest_id"]
            if kind == "deployment_evidence":
                payload["status"] = "not-verified"
                payload["projects"][0]["status"] = "not-verified"
            payload["projects"][0].update(source_ref="main", head="a" * 40)
            document = contracts.seal_document(kind, payload)
            contracts.validate_declared_bindings(manifest, {kind: document})
            payload["projects"][0]["head"] = "b" * 40
            document = contracts.seal_document(kind, payload)
            with self.subTest(kind=kind), self.assertRaises(ContractError):
                contracts.validate_declared_bindings(manifest, {kind: document})
            payload["status"] = "failed"
            payload["projects"][0].update(
                status="failed", reason="revision changed", nextStep="replan"
            )
            failed = contracts.seal_document(kind, payload)
            contracts.validate_declared_bindings(manifest, {kind: failed})

    def test_verified_candidates_must_match_the_supplied_predecessor(self) -> None:
        for shared in (False, True):
            payload = copy.deepcopy(self.family["verification"]["payload"])
            candidates = (
                payload["shared_cleanup_candidates"]
                if shared
                else payload["projects"][0]["cleanup_candidates"]
            )
            candidates[0]["state"] = fixtures.file_state(999)
            document = contracts.seal_document("verification", payload)
            with self.subTest(shared=shared), self.assertRaises(ContractError):
                contracts.validate_declared_bindings(
                    self.family["manifest"],
                    {
                        "apply_receipt": self.family["apply_receipt"],
                        "deployment_evidence": self.family["deployment_evidence"],
                        "verification": document,
                    },
                )
            payload["status"] = "failed"
            affected = payload["projects"] if shared else payload["projects"][:1]
            for project in affected:
                project.update(
                    status="failed", reason="candidate changed", nextStep="inspect"
                )
            failed = contracts.seal_document("verification", payload)
            contracts.validate_declared_bindings(
                self.family["manifest"],
                {
                    "apply_receipt": self.family["apply_receipt"],
                    "deployment_evidence": self.family["deployment_evidence"],
                    "verification": failed,
                },
            )

    def test_verified_project_needs_candidates_in_a_failed_batch(self) -> None:
        for shared in (False, True):
            payload = copy.deepcopy(self.family["verification"]["payload"])
            payload["status"] = "failed"
            payload["projects"][1].update(
                status="failed", reason="verification failed", nextStep="inspect"
            )
            if shared:
                payload["shared_cleanup_candidates"] = []
            else:
                payload["projects"][0]["cleanup_candidates"] = []
            document = contracts.seal_document("verification", payload)
            with self.subTest(shared=shared), self.assertRaises(ContractError):
                contracts.validate_declared_bindings(
                    self.family["manifest"], {"verification": document}
                )

    def test_recovery_steps_require_supplied_nonnull_stage_evidence(self) -> None:
        with (
            self.subTest(boundary="missing document"),
            self.assertRaises(ContractError),
        ):
            contracts.validate_declared_bindings(
                self.family["manifest"],
                {
                    "apply_receipt": self.family["apply_receipt"],
                    "recovery_plan": self.family["recovery_plan"],
                },
            )
        payload = copy.deepcopy(self.family["recovery_plan"]["payload"])
        payload["input_evidence"]["cleanup_receipt"] = None
        with self.subTest(boundary="null evidence"), self.assertRaises(ContractError):
            plan = contracts.seal_document("recovery_plan", payload)
            contracts.validate_declared_bindings(
                self.family["manifest"],
                {
                    "apply_receipt": self.family["apply_receipt"],
                    "deployment_evidence": self.family["deployment_evidence"],
                    "cleanup_receipt": self.family["cleanup_receipt"],
                    "recovery_plan": plan,
                },
            )

    def test_equal_state_recovery_step_is_not_a_plan_action(self) -> None:
        payload = copy.deepcopy(self.family["recovery_plan"]["payload"])
        step = payload["steps"][0]
        step["expected_current"] = copy.deepcopy(step["restore_to"])
        payload["resources"][0]["state"] = copy.deepcopy(step["restore_to"])
        with self.assertRaises(ContractError):
            contracts.seal_document("recovery_plan", payload)

    def test_already_complete_requires_a_successful_previous_receipt(self) -> None:
        for kind, id_key in (
            ("apply_receipt", "apply_id"),
            ("cleanup_receipt", "cleanup_id"),
            ("recovery_receipt", "receipt_id"),
        ):
            payload = copy.deepcopy(self.family[kind]["payload"])
            payload["status"] = "already-complete"
            for project in payload["projects"]:
                project["status"] = "already-complete"
            with self.subTest(kind=kind), self.assertRaises(ContractError):
                document = contracts.seal_document(kind, payload)
                contracts.validate_cumulative(None, document, kind)
            payload["previous_receipt_id"] = self.family[kind][id_key]
            payload["started_at"] = self.family[kind]["payload"]["finished_at"]
            payload["finished_at"] = self.family[kind]["payload"]["finished_at"]
            retry = contracts.seal_document(kind, payload)
            self.assertEqual(
                contracts.validate_cumulative(self.family[kind], retry, kind), retry
            )
            failed_payload = copy.deepcopy(self.family[kind]["payload"])
            failed_payload["status"] = "failed"
            if kind == "recovery_receipt":
                failed_payload["reason"] = "phase check failed"
            for project in failed_payload["projects"]:
                project.update(
                    status="failed", reason="phase check failed", nextStep="inspect"
                )
            previous = contracts.seal_document(kind, failed_payload)
            payload["previous_receipt_id"] = previous[id_key]
            payload["started_at"] = previous["payload"]["finished_at"]
            payload["finished_at"] = previous["payload"]["finished_at"]
            retry = contracts.seal_document(kind, payload)
            with self.subTest(previous_failed=kind), self.assertRaises(ContractError):
                contracts.validate_cumulative(previous, retry, kind)

    def test_retry_cannot_discard_pending_steps_without_results(self) -> None:
        payload = copy.deepcopy(self.family["recovery_receipt"]["payload"])
        payload["pending_step_ids"] = list(payload["completed_step_ids"])
        payload["completed_step_ids"] = []
        payload["results"] = []
        payload["shared_results"] = []
        payload["status"] = "blocked"
        payload["reason"] = "no write attempted"
        for project in payload["projects"]:
            project.update(
                status="blocked", reason="no write attempted", nextStep="retry"
            )
        previous = contracts.seal_document("recovery_receipt", payload)
        payload = copy.deepcopy(previous["payload"])
        complete_payload = copy.deepcopy(self.family["recovery_receipt"]["payload"])
        complete_payload["previous_receipt_id"] = previous["receipt_id"]
        complete_payload["started_at"] = previous["payload"]["finished_at"]
        complete_payload["finished_at"] = previous["payload"]["finished_at"]
        complete = contracts.seal_document("recovery_receipt", complete_payload)
        contracts.validate_cumulative(previous, complete, "recovery_receipt")

        payload["previous_receipt_id"] = previous["receipt_id"]
        payload["started_at"] = previous["payload"]["finished_at"]
        payload["finished_at"] = previous["payload"]["finished_at"]
        payload["pending_step_ids"] = []
        payload["status"] = "restored"
        for project in payload["projects"]:
            project.update(status="restored", reason="", nextStep="")
        lost = contracts.seal_document("recovery_receipt", payload)
        with self.assertRaises(ContractError):
            contracts.validate_cumulative(previous, lost, "recovery_receipt")

    def test_success_envelope_preserves_artifact_completion_variant(self) -> None:
        for boundary in ("aggregate", "project"):
            envelope = copy.deepcopy(self.family["migration_envelope_apply"])
            if boundary == "aggregate":
                envelope["status"] = "already-complete"
            else:
                envelope["projects"][0]["status"] = "already-complete"
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.validate_document(envelope, "migration_envelope")

    def test_loaded_completion_record_requires_a_predecessor_identity(self) -> None:
        for kind, id_key in (
            ("apply_receipt", "apply_id"),
            ("cleanup_receipt", "cleanup_id"),
            ("recovery_receipt", "receipt_id"),
        ):
            document = copy.deepcopy(self.family[kind])
            document["payload"]["projects"][0]["status"] = "already-complete"
            document[id_key] = hashlib.sha256(
                contracts.canonical_json_bytes(document["payload"])
            ).hexdigest()
            with self.subTest(kind=kind), self.assertRaises(ContractError):
                contracts.load_document(contracts.canonical_json_bytes(document), kind)

    def test_retry_creates_first_backup_only_after_proven_unwritten_failure(
        self,
    ) -> None:
        for kind, id_key, reference_key in (
            ("apply_receipt", "apply_id", "backup_ref"),
            ("cleanup_receipt", "cleanup_id", "backup_ref"),
            ("recovery_receipt", "receipt_id", "protection_ref"),
        ):
            for observation in ("unchanged", "unknown", "changed"):
                payload = copy.deepcopy(self.family[kind]["payload"])
                if kind == "recovery_receipt":
                    result = next(
                        result
                        for result in payload["results"]
                        if result["phase"] == "apply"
                        and result["dependent_projects"] == [fixtures.ALPHA]
                    )
                    payload["completed_step_ids"].remove(result["step_id"])
                    payload["pending_step_ids"].append(result["step_id"])
                    payload["reason"] = "protection creation failed"
                else:
                    result = payload["projects"][0]["private_results"][0]
                result.update(status="failed", error="original copy failed")
                result[reference_key] = None
                if observation == "unchanged":
                    result["after"] = copy.deepcopy(result["before"])
                elif observation == "unknown":
                    result["after"] = None
                else:
                    result["after"] = fixtures.file_state(999)
                payload["status"] = "failed"
                payload["projects"][0].update(
                    status="failed", reason="original copy failed", nextStep="inspect"
                )
                previous = contracts.seal_document(kind, payload)
                retry_payload = copy.deepcopy(self.family[kind]["payload"])
                retry_payload["previous_receipt_id"] = previous[id_key]
                retry_payload["started_at"] = previous["payload"]["finished_at"]
                retry_payload["finished_at"] = previous["payload"]["finished_at"]
                retry = contracts.seal_document(kind, retry_payload)
                with self.subTest(kind=kind, observation=observation):
                    if observation == "unchanged":
                        self.assertEqual(
                            contracts.validate_cumulative(previous, retry, kind), retry
                        )
                    else:
                        with self.assertRaises(ContractError):
                            contracts.validate_cumulative(previous, retry, kind)

    def test_completed_recovery_step_cannot_skip_a_pending_dependency(self) -> None:
        payload = copy.deepcopy(self.family["recovery_receipt"]["payload"])
        missing = next(
            result["step_id"]
            for result in payload["results"]
            if result["phase"] == "deploy"
            and result["resource_id"] == fixtures.resource_id_of("r1")
        )
        payload["results"] = [
            result for result in payload["results"] if result["step_id"] != missing
        ]
        payload["completed_step_ids"].remove(missing)
        payload["pending_step_ids"].append(missing)
        payload["status"] = "failed"
        payload["reason"] = "dependency was not completed"
        payload["projects"][0].update(
            status="failed", reason="dependency was not completed", nextStep="inspect"
        )
        receipt = contracts.seal_document("recovery_receipt", payload)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.family["manifest"],
                {
                    "apply_receipt": self.family["apply_receipt"],
                    "deployment_evidence": self.family["deployment_evidence"],
                    "cleanup_receipt": self.family["cleanup_receipt"],
                    "recovery_plan": self.family["recovery_plan"],
                    "recovery_receipt": receipt,
                },
            )


class ThirdReviewRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.family = fixtures.build_fixture_family()
        cls.manifest = cls.family["manifest"]
        cls.apply_receipt = cls.family["apply_receipt"]
        cls.deployment = cls.family["deployment_evidence"]
        cls.verification = cls.family["verification"]
        cls.cleanup = cls.family["cleanup_receipt"]
        cls.plan = cls.family["recovery_plan"]
        cls.receipt = cls.family["recovery_receipt"]
        cls.r4 = fixtures.resource_id_of("r4")

    def bound_stages(self):
        return {
            "apply_receipt": self.apply_receipt,
            "deployment_evidence": self.deployment,
            "verification": self.verification,
            "cleanup_receipt": self.cleanup,
        }

    def apply_inverse_steps(self, exclude=()):
        steps = [
            copy.deepcopy(step)
            for step in self.plan["payload"]["steps"]
            if step["phase"] == "apply" and step["resource_id"] not in exclude
        ]
        for step in steps:
            step["depends_on"] = []
        return steps

    def apply_only_evidence(self, apply_document):
        evidence = fixtures.build_input_evidence(
            self.manifest, apply_document, self.deployment, self.cleanup
        )
        evidence["deployment_evidence"] = None
        evidence["cleanup_receipt"] = None
        return evidence

    def custom_plan(self, steps, input_evidence, extra_entries=()):
        payload = copy.deepcopy(self.plan["payload"])
        payload["steps"] = steps
        by_resource = {}
        for step in steps:
            by_resource.setdefault(step["resource_id"], []).append(step)
        resources = []
        for entry in payload["resources"]:
            group = by_resource.get(entry["resource_id"])
            if group is None:
                continue
            entry["operation_ids"] = sorted(
                op_id for step in group for op_id in step["operation_ids"]
            )
            entry["state"] = copy.deepcopy(group[0]["expected_current"])
            resources.append(entry)
        resources.extend(copy.deepcopy(list(extra_entries)))
        payload["resources"] = resources
        payload["shared_operation_ids"] = sorted(
            op_id
            for step in steps
            if step["resource_id"] == fixtures.resource_id_of("s1")
            for op_id in step["operation_ids"]
        )
        payload["input_evidence"] = input_evidence
        return payload

    def test_share_item_requires_a_matching_apply_operation(self) -> None:
        contracts.validate_declared_bindings(self.manifest, self.bound_stages())

        def r4_operation(payload):
            return next(
                op
                for op in payload["projects"][0]["private_operations"]
                if op["resource_id"] == self.r4
            )

        for boundary in ("missing operation", "source path", "source state", "target"):
            payload = copy.deepcopy(self.manifest["payload"])
            if boundary == "missing operation":
                payload["projects"][0]["private_operations"] = [
                    op
                    for op in payload["projects"][0]["private_operations"]
                    if op["resource_id"] != self.r4
                ]
            elif boundary == "source path":
                r4_operation(payload)["change"]["source_ref"]["path"] = (
                    "/private/candidates/other-notes.md"
                )
            elif boundary == "source state":
                r4_operation(payload)["change"]["source_ref"]["state"] = (
                    fixtures.file_state(999)
                )
            else:
                renamed = r4_operation(payload)
                renamed["target"] = fixtures.ALPHA + "/docs/spec/renamed-notes.md"
                renamed["resource_id"] = contracts.resource_id(
                    renamed["owner_kind"], renamed["target"]
                )
                renamed["operation_id"] = contracts.operation_id(
                    renamed["phase"], renamed["resource_id"], renamed["selector"]
                )
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.seal_document("manifest", payload)

    def test_succeeded_publication_result_must_match_the_candidate(self) -> None:
        contracts.validate_declared_bindings(
            self.manifest, {"apply_receipt": self.apply_receipt}
        )

        payload = copy.deepcopy(self.apply_receipt["payload"])
        forged = next(
            entry
            for entry in payload["projects"][0]["private_results"]
            if entry["resource_id"] == self.r4
        )
        forged["after"] = fixtures.file_state(999)
        receipt = contracts.seal_document("apply_receipt", payload)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.manifest, {"apply_receipt": receipt}
            )

    def test_recovery_plan_must_cover_every_proven_changed_selected_resource(
        self,
    ) -> None:
        r2 = fixtures.resource_id_of("r2")
        for boundary in ("omitted resource", "empty plan"):
            payload = copy.deepcopy(self.plan["payload"])
            if boundary == "omitted resource":
                payload["steps"] = [
                    step for step in payload["steps"] if step["resource_id"] != r2
                ]
                payload["resources"] = [
                    entry
                    for entry in payload["resources"]
                    if entry["resource_id"] != r2
                ]
            else:
                payload["steps"] = []
                payload["resources"] = []
                payload["shared_operation_ids"] = []
            plan = contracts.seal_document("recovery_plan", payload)
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.validate_declared_bindings(
                    self.manifest, {**self.bound_stages(), "recovery_plan": plan}
                )

    def test_cleanup_only_chain_stopping_short_of_pre_apply_is_rejected(
        self,
    ) -> None:
        steps = [
            copy.deepcopy(step)
            for step in self.plan["payload"]["steps"]
            if step["phase"] == "cleanup"
        ]
        payload = self.custom_plan(
            steps,
            fixtures.build_input_evidence(
                self.manifest, self.apply_receipt, self.deployment, self.cleanup
            ),
        )
        plan = contracts.seal_document("recovery_plan", payload)
        keep = {step["step_id"] for step in payload["steps"]}
        receipt_payload = copy.deepcopy(self.receipt["payload"])
        receipt_payload["plan_id"] = plan["plan_id"]
        receipt_payload["results"] = [
            result for result in receipt_payload["results"] if result["step_id"] in keep
        ]
        receipt_payload["completed_step_ids"] = sorted(keep)
        receipt_payload["pending_step_ids"] = []
        receipt_payload["shared_results"] = [
            {**shared, "step_ids": [s for s in shared["step_ids"] if s in keep]}
            for shared in receipt_payload["shared_results"]
        ]
        receipt_payload["shared_results"] = [
            shared for shared in receipt_payload["shared_results"] if shared["step_ids"]
        ]
        receipt = contracts.seal_document("recovery_receipt", receipt_payload)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.manifest,
                {
                    **self.bound_stages(),
                    "recovery_plan": plan,
                    "recovery_receipt": receipt,
                },
            )

    def test_proven_noop_resource_may_keep_a_no_action_initial_snapshot(
        self,
    ) -> None:
        r2 = fixtures.resource_id_of("r2")
        # A noop copy still binds its result to the declared source, so reseal
        # the manifest with a prepared candidate whose state equals the
        # recorded before/after state instead of contradicting the copy.
        manifest_payload = copy.deepcopy(self.manifest["payload"])
        r2_apply = next(
            op
            for op in manifest_payload["projects"][0]["private_operations"]
            if op["resource_id"] == r2 and op["phase"] == "apply"
        )
        r2_apply["change"]["source_ref"] = {
            "path": "/private/source/r2-noop-candidate",
            "state": fixtures.resource_state("r2", "orig"),
        }
        manifest = contracts.seal_document("manifest", manifest_payload)
        apply_payload = copy.deepcopy(self.apply_receipt["payload"])
        apply_payload["manifest_id"] = manifest["manifest_id"]
        noop = next(
            result
            for result in apply_payload["projects"][0]["private_results"]
            if result["resource_id"] == r2
        )
        noop["after"] = copy.deepcopy(noop["before"])
        apply_document = contracts.seal_document("apply_receipt", apply_payload)
        snapshot = copy.deepcopy(
            next(
                entry
                for entry in self.plan["payload"]["resources"]
                if entry["resource_id"] == r2
            )
        )
        snapshot["state"] = fixtures.resource_state("r2", "orig")
        steps = [
            fixtures.build_recovery_step(key, "apply", manifest["manifest_id"], [])
            for key in fixtures.RESOURCES
            if key != "r2" and "apply" in fixtures.RESOURCES[key][2]
        ]
        evidence = fixtures.build_input_evidence(
            manifest, apply_document, self.deployment, self.cleanup
        )
        evidence["deployment_evidence"] = None
        evidence["cleanup_receipt"] = None
        payload = self.custom_plan(steps, evidence, extra_entries=[snapshot])
        payload["manifest_id"] = manifest["manifest_id"]
        plan = contracts.seal_document("recovery_plan", payload)
        self.assertEqual(
            contracts.validate_declared_bindings(
                manifest,
                {"apply_receipt": apply_document, "recovery_plan": plan},
            )["recovery_plan"],
            plan,
        )

    def test_unknown_selected_write_blocks_the_plan(self) -> None:
        r2 = fixtures.resource_id_of("r2")
        apply_payload = copy.deepcopy(self.apply_receipt["payload"])
        alpha = apply_payload["projects"][0]
        unknown = next(
            result for result in alpha["private_results"] if result["resource_id"] == r2
        )
        unknown.update(status="failed", error="apply outcome is unknown")
        unknown["before"] = None
        unknown["after"] = None
        unknown["backup_ref"] = None
        alpha.update(
            status="failed",
            reason="apply outcome is unknown",
            nextStep="inspect the resource",
        )
        apply_payload["status"] = "failed"
        apply_document = contracts.seal_document("apply_receipt", apply_payload)
        snapshot = copy.deepcopy(
            next(
                entry
                for entry in self.plan["payload"]["resources"]
                if entry["resource_id"] == r2
            )
        )
        snapshot["state"] = fixtures.resource_state("r2", "orig")
        payload = self.custom_plan(
            self.apply_inverse_steps(exclude={r2}),
            self.apply_only_evidence(apply_document),
            extra_entries=[snapshot],
        )
        plan = contracts.seal_document("recovery_plan", payload)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.manifest,
                {"apply_receipt": apply_document, "recovery_plan": plan},
            )

    def test_successful_recovery_must_retain_the_planned_revision(self) -> None:
        plan_payload = copy.deepcopy(self.plan["payload"])
        plan_payload["projects"][0].update(source_ref="main", head="a" * 40)
        plan = contracts.seal_document("recovery_plan", plan_payload)
        documents = {**self.bound_stages(), "recovery_plan": plan}
        baseline = copy.deepcopy(self.receipt["payload"])
        baseline["plan_id"] = plan["plan_id"]
        baseline["projects"][0].update(source_ref="main", head="a" * 40)
        control = contracts.seal_document("recovery_receipt", copy.deepcopy(baseline))
        contracts.validate_declared_bindings(
            self.manifest, {**documents, "recovery_receipt": control}
        )
        for field, value in (("head", "b" * 40), ("source_ref", "other-branch")):
            payload = copy.deepcopy(baseline)
            payload["projects"][0][field] = value
            drifted = contracts.seal_document("recovery_receipt", payload)
            with self.subTest(field=field), self.assertRaises(ContractError):
                contracts.validate_declared_bindings(
                    self.manifest, {**documents, "recovery_receipt": drifted}
                )

        # A failed record may truthfully report the drift it observed.
        payload = copy.deepcopy(baseline)
        r1 = fixtures.resource_id_of("r1")
        failed = next(
            result
            for result in payload["results"]
            if result["phase"] == "apply" and result["resource_id"] == r1
        )
        failed.update(
            status="failed", error="restore failed", after=None, protection_ref=None
        )
        payload["completed_step_ids"].remove(failed["step_id"])
        payload["pending_step_ids"].append(failed["step_id"])
        payload["status"] = "failed"
        payload["reason"] = "restore failed"
        payload["projects"][0].update(
            status="failed",
            reason="restore failed",
            nextStep="inspect the restore",
            head="b" * 40,
        )
        honest = contracts.seal_document("recovery_receipt", payload)
        contracts.validate_declared_bindings(
            self.manifest, {**documents, "recovery_receipt": honest}
        )

    def test_operation_change_must_fit_the_owner_kind(self) -> None:
        contracts.validate_document(self.manifest, "manifest")
        cases = (
            (
                "json with copy-directory",
                fixtures.resource_id_of("r1"),
                {
                    "kind": "copy-directory",
                    "source_ref": {
                        "path": "/private/source/sbtd-task",
                        "state": fixtures.directory_state(71),
                    },
                },
            ),
            (
                "directory with copy-file",
                fixtures.resource_id_of("r2"),
                {
                    "kind": "copy-file",
                    "source_ref": fixtures._file_ref("/private/source/base-config", 72),
                },
            ),
            (
                "directory with ensure-file-block",
                fixtures.resource_id_of("r2"),
                {
                    "kind": "ensure-file-block",
                    "source_ref": fixtures._file_ref(
                        "/private/source/managed-block", 73
                    ),
                },
            ),
        )
        for boundary, rid, change in cases:
            payload = copy.deepcopy(self.manifest["payload"])
            operation = next(
                op
                for op in payload["projects"][0]["private_operations"]
                if op["resource_id"] == rid and op["phase"] == "apply"
            )
            operation["change"] = change
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.seal_document("manifest", payload)

    def test_empty_artifact_envelope_cannot_invent_generated_ids(self) -> None:
        manifest_id = self.manifest["manifest_id"]
        plan_id = self.plan["plan_id"]
        verification_id = self.verification["verification_id"]
        forged = "a" * 64
        negatives = (
            ("migration", "plan", {"manifest_id": forged}),
            (
                "migration",
                "verify",
                {"manifest_id": manifest_id, "verification_id": forged},
            ),
            ("recovery", "plan", {"manifest_id": manifest_id, "plan_id": forged}),
            (
                "recovery",
                "apply",
                {"manifest_id": manifest_id, "plan_id": plan_id, "receipt_id": forged},
            ),
        )
        for mode, phase, identifiers in negatives:
            with self.subTest(mode=mode, phase=phase), self.assertRaises(ContractError):
                contracts.make_envelope(
                    mode,
                    phase,
                    "blocked",
                    [],
                    "phase could not run",
                    "fix the inputs and retry",
                    identifiers=identifiers,
                )
        positives = (
            (
                "migration",
                "cleanup",
                {"manifest_id": manifest_id, "verification_id": verification_id},
            ),
            ("recovery", "plan", {"manifest_id": manifest_id, "plan_id": None}),
            (
                "recovery",
                "apply",
                {"manifest_id": manifest_id, "plan_id": plan_id, "receipt_id": None},
            ),
        )
        for mode, phase, identifiers in positives:
            with self.subTest(mode=mode, phase=phase, boundary="kept inputs"):
                contracts.make_envelope(
                    mode,
                    phase,
                    "blocked",
                    [],
                    "phase could not run",
                    "fix the inputs and retry",
                    identifiers=identifiers,
                )

    def test_recovery_receipt_rejects_duplicate_project_roots(self) -> None:
        payload = copy.deepcopy(self.receipt["payload"])
        payload["projects"].append(copy.deepcopy(payload["projects"][0]))
        with self.assertRaises(ContractError):
            contracts.seal_document("recovery_receipt", payload)

    def test_private_resource_cannot_repeat_across_projects(self) -> None:
        payload = copy.deepcopy(self.apply_receipt["payload"])
        duplicate = fixtures.build_resource_result("r1", "apply")
        duplicate["dependent_projects"] = [fixtures.BETA]
        payload["projects"][1]["private_results"].append(duplicate)
        with self.subTest(document="apply_receipt"), self.assertRaises(ContractError):
            contracts.seal_document("apply_receipt", payload)

        payload = copy.deepcopy(self.verification["payload"])
        duplicate = fixtures.build_cleanup_candidate("r1", "deploy")
        duplicate["dependent_projects"] = [fixtures.BETA]
        payload["projects"][1]["cleanup_candidates"].append(duplicate)
        with self.subTest(document="verification"), self.assertRaises(ContractError):
            contracts.seal_document("verification", payload)

    def test_successful_cleanup_must_carry_the_verified_retained_assets(
        self,
    ) -> None:
        contracts.validate_declared_bindings(self.manifest, self.bound_stages())

        for boundary in ("dropped", "changed"):
            payload = copy.deepcopy(self.cleanup["payload"])
            if boundary == "changed":
                payload["projects"][0]["retained_assets"][0]["state"] = (
                    fixtures.file_state(999)
                )
            else:
                payload["projects"][0]["retained_assets"] = []
            payload["retained_assets"] = copy.deepcopy(
                payload["projects"][0]["retained_assets"]
            )
            drifted = contracts.seal_document("cleanup_receipt", payload)
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.validate_declared_bindings(
                    self.manifest,
                    {**self.bound_stages(), "cleanup_receipt": drifted},
                )

        # Extra retained evidence on the verified side must be carried as well.
        verification_payload = copy.deepcopy(self.verification["payload"])
        verification_payload["projects"][0]["retained_assets"].append(
            {
                "path": fixtures.ALPHA + "/docs/spec/extra-notes.md",
                "state": fixtures.file_state(84),
            }
        )
        verification = contracts.seal_document("verification", verification_payload)
        cleanup_payload = copy.deepcopy(self.cleanup["payload"])
        cleanup_payload["verification_id"] = verification["verification_id"]
        cleanup = contracts.seal_document("cleanup_receipt", cleanup_payload)
        with (
            self.subTest(boundary="uncarried verified asset"),
            self.assertRaises(ContractError),
        ):
            contracts.validate_declared_bindings(
                self.manifest,
                {
                    "apply_receipt": self.apply_receipt,
                    "deployment_evidence": self.deployment,
                    "verification": verification,
                    "cleanup_receipt": cleanup,
                },
            )

        # A failed record may truthfully report the drift it observed.
        payload = copy.deepcopy(self.cleanup["payload"])
        payload["status"] = "failed"
        payload["retained_assets"] = []
        payload["projects"][0].update(
            status="failed",
            reason="cleanup verification drifted",
            nextStep="inspect the project",
            retained_assets=[],
        )
        honest = contracts.seal_document("cleanup_receipt", payload)
        contracts.validate_declared_bindings(
            self.manifest, {**self.bound_stages(), "cleanup_receipt": honest}
        )

    def test_bound_stages_must_follow_causal_time_order(self) -> None:
        cases = (
            (
                "apply_receipt",
                {"started_at": "2026-09-18T00:30:00Z"},
                ("apply_receipt",),
            ),
            (
                "deployment_evidence",
                {"started_at": fixtures.T1},
                ("apply_receipt", "deployment_evidence"),
            ),
            (
                "verification",
                {"verified_at": fixtures.T1},
                ("apply_receipt", "deployment_evidence", "verification"),
            ),
            (
                "cleanup_receipt",
                {"started_at": "2026-09-18T03:30:00Z"},
                (
                    "apply_receipt",
                    "deployment_evidence",
                    "verification",
                    "cleanup_receipt",
                ),
            ),
            (
                "recovery_plan",
                {"created_at": "2026-09-18T04:30:00Z"},
                (
                    "apply_receipt",
                    "deployment_evidence",
                    "cleanup_receipt",
                    "recovery_plan",
                ),
            ),
            (
                "recovery_receipt",
                {"started_at": "2026-09-18T05:00:00Z"},
                (
                    "apply_receipt",
                    "deployment_evidence",
                    "cleanup_receipt",
                    "recovery_plan",
                    "recovery_receipt",
                ),
            ),
        )
        for kind, changes, supplied in cases:
            payload = copy.deepcopy(self.family[kind]["payload"])
            payload.update(changes)
            document = contracts.seal_document(kind, payload)
            documents = {
                name: document if name == kind else self.family[name]
                for name in supplied
            }
            with self.subTest(kind=kind), self.assertRaises(ContractError):
                contracts.validate_declared_bindings(self.manifest, documents)

    def test_retry_must_not_predate_the_previous_attempt(self) -> None:
        for kind, id_key, previous_key in (
            ("apply_receipt", "apply_id", "previous_receipt_id"),
            ("deployment_evidence", "deployment_id", "previous_deployment_id"),
            ("cleanup_receipt", "cleanup_id", "previous_receipt_id"),
            ("recovery_receipt", "receipt_id", "previous_receipt_id"),
        ):
            previous = self.family[kind]
            finished = previous["payload"]["finished_at"]
            # Deliberately bad chronology: this retry reuses the first attempt's
            # execution window even though it links the finished predecessor.
            early_payload = copy.deepcopy(previous["payload"])
            early_payload[previous_key] = previous[id_key]
            early = contracts.seal_document(kind, early_payload)
            with (
                self.subTest(kind=kind, boundary="early retry"),
                self.assertRaises(ContractError),
            ):
                contracts.validate_cumulative(previous, early, kind)
            adjacent_payload = copy.deepcopy(previous["payload"])
            adjacent_payload[previous_key] = previous[id_key]
            adjacent_payload["started_at"] = finished
            adjacent_payload["finished_at"] = finished
            adjacent = contracts.seal_document(kind, adjacent_payload)
            with self.subTest(kind=kind, boundary="adjacent retry"):
                self.assertEqual(
                    contracts.validate_cumulative(previous, adjacent, kind), adjacent
                )

    def test_no_evidence_requires_complete_initial_snapshots(self) -> None:
        payload = copy.deepcopy(self.plan["payload"])
        payload["steps"] = []
        payload["shared_operation_ids"] = []
        for kind in ("apply_receipt", "deployment_evidence", "cleanup_receipt"):
            payload["input_evidence"][kind] = None
        initial = {
            op["resource_id"]: op["before_requirement"]["state"]
            for project in self.manifest["payload"]["projects"]
            for op in project["private_operations"]
            if op["before_requirement"]["kind"] == "state"
        }
        initial.update(
            {
                op["resource_id"]: op["before_requirement"]["state"]
                for op in self.manifest["payload"]["shared_operations"]
                if op["before_requirement"]["kind"] == "state"
            }
        )
        for resource in payload["resources"]:
            resource["state"] = copy.deepcopy(initial[resource["resource_id"]])
        plan = contracts.seal_document("recovery_plan", copy.deepcopy(payload))
        contracts.validate_declared_bindings(self.manifest, {"recovery_plan": plan})
        payload["resources"] = []
        missing = contracts.seal_document("recovery_plan", payload)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.manifest, {"recovery_plan": missing}
            )

    def test_later_stage_evidence_cannot_restore_only_an_intermediate_state(
        self,
    ) -> None:
        manifest_payload = copy.deepcopy(self.manifest["payload"])
        manifest_payload["projects"] = [manifest_payload["projects"][0]]
        project = manifest_payload["projects"][0]
        project["private_operations"] = list(fixtures.operations_of("r2").values())
        project["shared_operation_ids"] = []
        manifest_payload["shared_operations"] = []
        manifest_payload["shared_roots"] = []
        manifest_payload["deployment"] = None
        manifest_payload["publication_decisions"]["items"] = []
        manifest = contracts.seal_document("manifest", manifest_payload)

        cleanup_payload = copy.deepcopy(self.cleanup["payload"])
        cleanup_payload["manifest_id"] = manifest["manifest_id"]
        cleanup_payload["projects"] = [cleanup_payload["projects"][0]]
        cleanup_payload["projects"][0].update(
            private_results=[fixtures.build_resource_result("r2", "cleanup")],
            shared_operation_ids=[],
            retained_assets=[],
        )
        cleanup_payload["shared_results"] = []
        cleanup_payload["retained_assets"] = []
        cleanup = contracts.seal_document("cleanup_receipt", cleanup_payload)
        step = fixtures.build_recovery_step(
            "r2", "cleanup", manifest["manifest_id"], []
        )
        payload = self.custom_plan(
            [step],
            fixtures.build_input_evidence(
                manifest, self.apply_receipt, self.deployment, cleanup
            ),
        )
        payload["manifest_id"] = manifest["manifest_id"]
        payload["projects"] = [payload["projects"][0]]
        payload["input_evidence"]["apply_receipt"] = None
        payload["input_evidence"]["deployment_evidence"] = None
        plan = contracts.seal_document("recovery_plan", payload)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                manifest, {"cleanup_receipt": cleanup, "recovery_plan": plan}
            )


class FourthReviewRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.family = fixtures.build_fixture_family()
        cls.manifest = cls.family["manifest"]

    def stages(self):
        return {
            kind: self.family[kind]
            for kind in (
                "apply_receipt",
                "deployment_evidence",
                "verification",
                "cleanup_receipt",
            )
        }

    def retry(self, kind, previous):
        id_key = {
            "apply_receipt": "apply_id",
            "deployment_evidence": "deployment_id",
            "cleanup_receipt": "cleanup_id",
            "recovery_receipt": "receipt_id",
        }[kind]
        previous_key = (
            "previous_deployment_id"
            if kind == "deployment_evidence"
            else "previous_receipt_id"
        )
        payload = copy.deepcopy(self.family[kind]["payload"])
        payload[previous_key] = previous[id_key]
        payload["started_at"] = previous["payload"]["finished_at"]
        payload["finished_at"] = previous["payload"]["finished_at"]
        return contracts.seal_document(kind, payload)

    def test_canonical_json_refuses_non_string_keys_without_losing_finite_numbers(
        self,
    ) -> None:
        self.assertEqual(
            contracts.canonical_json_bytes({"value": 1.25}), b'{"value":1.25}'
        )
        for value in ({1: "x"}, {"nested": [{None: "x"}]}):
            with self.subTest(value=value), self.assertRaises(ContractError):
                contracts.canonical_json_bytes(value)

    def test_oversized_integer_uses_the_contract_error_boundary(self) -> None:
        limit = getattr(sys, "get_int_max_str_digits", lambda: 4300)()
        raw = '{"schema_version":' + "9" * max(limit + 1, 5000) + ',"items":[]}'
        with self.assertRaises(ContractError):
            contracts.load_document(raw, "publication_decisions")

    def test_resource_write_selectors_and_sources_must_be_compatible(self) -> None:
        for boundary in (
            "same entry",
            "ancestor entry",
            "whole resource",
            "different copy",
            "mixed changes",
        ):
            payload = copy.deepcopy(self.manifest["payload"])
            operation = copy.deepcopy(payload["projects"][0]["private_operations"][0])
            operation["selector"] = "another-selector"
            operation["ownership"]["key_path"] = ["other"]
            if boundary == "same entry":
                operation["ownership"]["key_path"] = ["sbtd"]
            elif boundary == "ancestor entry":
                operation["ownership"]["key_path"] = ["sbtd", "nested"]
            elif boundary == "whole resource":
                operation["selector"] = "whole-resource"
            elif boundary == "different copy":
                operation["change"]["source_ref"] = fixtures._file_ref(
                    "/private/source/other", 999
                )
            else:
                operation["change"] = {"kind": "remove"}
            operation["operation_id"] = contracts.operation_id(
                operation["phase"], operation["resource_id"], operation["selector"]
            )
            payload["projects"][0]["private_operations"].append(operation)
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.seal_document("manifest", payload)

        payload = copy.deepcopy(self.manifest["payload"])
        operation = copy.deepcopy(payload["projects"][0]["private_operations"][0])
        operation["selector"] = "disjoint-entry"
        operation["ownership"]["key_path"] = ["other"]
        operation["operation_id"] = contracts.operation_id(
            "apply", operation["resource_id"], operation["selector"]
        )
        payload["projects"][0]["private_operations"].append(operation)
        contracts.seal_document("manifest", payload)

    def test_successful_non_remove_results_leave_the_declared_resource_type(
        self,
    ) -> None:
        for kind, resource, after in (
            ("apply_receipt", "r1", fixtures.ABSENT),
            ("deployment_evidence", "r1", fixtures.ABSENT),
            ("apply_receipt", "r2", fixtures.file_state(999)),
        ):
            payload = copy.deepcopy(self.family[kind]["payload"])
            result = next(
                r
                for r in payload["projects"][0]["private_results"]
                if r["resource_id"] == fixtures.resource_id_of(resource)
            )
            result["after"] = copy.deepcopy(after)
            document = contracts.seal_document(kind, payload)
            with (
                self.subTest(kind=kind, resource=resource),
                self.assertRaises(ContractError),
            ):
                contracts.validate_declared_bindings(self.manifest, {kind: document})

    def test_original_backups_stay_in_the_declared_vault_without_conflicting_reuse(
        self,
    ) -> None:
        for path in (fixtures.ALPHA + "/original", "/private/home/.codex/original"):
            payload = copy.deepcopy(self.family["apply_receipt"]["payload"])
            payload["projects"][0]["private_results"][0]["backup_ref"]["path"] = path
            document = contracts.seal_document("apply_receipt", payload)
            with self.subTest(path=path), self.assertRaises(ContractError):
                contracts.validate_declared_bindings(
                    self.manifest, {"apply_receipt": document}
                )
        payload = copy.deepcopy(self.family["apply_receipt"]["payload"])
        alpha_backup = payload["projects"][0]["private_results"][0]["backup_ref"]
        payload["projects"][1]["private_results"][0]["backup_ref"]["path"] = (
            alpha_backup["path"]
        )
        document = contracts.seal_document("apply_receipt", payload)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.manifest, {"apply_receipt": document}
            )

    def test_blocked_runtime_and_failed_recovery_need_an_explanation(self) -> None:
        for boundary in ("runtime", "outcome"):
            payload = copy.deepcopy(self.family["recovery_receipt"]["payload"])
            if boundary == "runtime":
                payload["runtime_readiness"] = "blocked"
            else:
                payload["status"] = "failed"
                payload["projects"][0].update(
                    status="failed", reason="restore failed", nextStep="inspect"
                )
            payload["reason"] = ""
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.seal_document("recovery_receipt", payload)
            payload["reason"] = "required runtime or recovery step is unavailable"
            contracts.seal_document("recovery_receipt", payload)

    def test_known_partial_or_unknown_writes_cannot_advance_on_retry(self) -> None:
        for kind in (
            "apply_receipt",
            "deployment_evidence",
            "cleanup_receipt",
            "recovery_receipt",
        ):
            for outcome in ("changed", "unknown"):
                payload = copy.deepcopy(self.family[kind]["payload"])
                if kind == "recovery_receipt":
                    result = next(
                        r
                        for r in payload["results"]
                        if r["phase"] == "apply"
                        and r["resource_id"] == fixtures.resource_id_of("r1")
                    )
                    payload["completed_step_ids"].remove(result["step_id"])
                    payload["pending_step_ids"].append(result["step_id"])
                    payload["reason"] = "partial write needs recovery"
                else:
                    result = payload["projects"][0]["private_results"][0]
                result.update(status="failed", error="partial write")
                result["after"] = (
                    fixtures.file_state(999) if outcome == "changed" else None
                )
                payload["status"] = "failed"
                payload["projects"][0].update(
                    status="failed", reason="partial write", nextStep="recover"
                )
                previous = contracts.seal_document(kind, payload)
                with (
                    self.subTest(kind=kind, outcome=outcome),
                    self.assertRaises(ContractError),
                ):
                    contracts.validate_cumulative(
                        previous, self.retry(kind, previous), kind
                    )
                preserved_payload = copy.deepcopy(previous["payload"])
                previous_key = (
                    "previous_deployment_id"
                    if kind == "deployment_evidence"
                    else "previous_receipt_id"
                )
                id_key = {
                    "apply_receipt": "apply_id",
                    "deployment_evidence": "deployment_id",
                    "cleanup_receipt": "cleanup_id",
                    "recovery_receipt": "receipt_id",
                }[kind]
                preserved_payload[previous_key] = previous[id_key]
                preserved_payload["started_at"] = previous["payload"]["finished_at"]
                preserved_payload["finished_at"] = previous["payload"]["finished_at"]
                preserved = contracts.seal_document(kind, preserved_payload)
                self.assertEqual(
                    contracts.validate_cumulative(previous, preserved, kind), preserved
                )

    def test_carried_recovery_results_keep_operation_and_project_identity(self) -> None:
        for pending in (False, True):
            previous_payload = copy.deepcopy(self.family["recovery_receipt"]["payload"])
            if pending:
                result = next(
                    result
                    for result in previous_payload["results"]
                    if result["phase"] == "apply"
                    and result["resource_id"] == fixtures.resource_id_of("r1")
                )
                result.update(
                    status="failed",
                    after=copy.deepcopy(result["before"]),
                    error="write did not begin",
                )
                previous_payload["completed_step_ids"].remove(result["step_id"])
                previous_payload["pending_step_ids"].append(result["step_id"])
                previous_payload.update(status="failed", reason="write did not begin")
                previous_payload["projects"][0].update(
                    status="failed", reason="write did not begin", nextStep="retry"
                )
            previous = contracts.seal_document("recovery_receipt", previous_payload)
            control = self.retry("recovery_receipt", previous)
            contracts.validate_cumulative(previous, control, "recovery_receipt")
            for field, value in (
                ("operation_ids", [fixtures.digest_number(999)]),
                ("dependent_projects", [fixtures.BETA]),
            ):
                payload = copy.deepcopy(control["payload"])
                result = next(
                    result
                    for result in payload["results"]
                    if result["phase"] == "apply"
                    and result["resource_id"] == fixtures.resource_id_of("r1")
                )
                result[field] = value
                current = contracts.seal_document("recovery_receipt", payload)
                with (
                    self.subTest(pending=pending, field=field),
                    self.assertRaises(ContractError),
                ):
                    contracts.validate_cumulative(previous, current, "recovery_receipt")

    def test_verification_cannot_drop_or_forge_retained_non_cleanup_resources(
        self,
    ) -> None:
        for boundary in ("missing", "state"):
            payload = copy.deepcopy(self.family["verification"]["payload"])
            if boundary == "missing":
                payload["projects"][0]["retained_assets"] = []
            else:
                payload["projects"][0]["retained_assets"][0]["state"] = (
                    fixtures.file_state(999)
                )
            verification = contracts.seal_document("verification", payload)
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.validate_declared_bindings(
                    self.manifest,
                    {
                        "apply_receipt": self.family["apply_receipt"],
                        "deployment_evidence": self.family["deployment_evidence"],
                        "verification": verification,
                    },
                )

    def test_cleanup_batch_summary_is_the_union_of_project_observations(self) -> None:
        payload = copy.deepcopy(self.family["cleanup_receipt"]["payload"])
        payload["retained_assets"] = []
        with self.assertRaises(ContractError):
            cleanup = contracts.seal_document("cleanup_receipt", payload)
            contracts.validate_declared_bindings(
                self.manifest, {**self.stages(), "cleanup_receipt": cleanup}
            )
        payload = copy.deepcopy(self.family["cleanup_receipt"]["payload"])
        payload["status"] = "failed"
        payload["projects"][0].update(
            status="failed", reason="asset drift", nextStep="inspect"
        )
        payload["projects"][0]["retained_assets"][0]["state"] = fixtures.file_state(999)
        payload["retained_assets"] = copy.deepcopy(
            payload["projects"][0]["retained_assets"]
        )
        cleanup = contracts.seal_document("cleanup_receipt", payload)
        contracts.validate_declared_bindings(
            self.manifest, {**self.stages(), "cleanup_receipt": cleanup}
        )

    def test_recovery_snapshot_cannot_ignore_later_retained_observations(self) -> None:
        payload = copy.deepcopy(self.family["cleanup_receipt"]["payload"])
        payload["status"] = "failed"
        payload["projects"][0].update(
            status="failed", reason="asset changed", nextStep="inspect"
        )
        payload["projects"][0]["retained_assets"][0]["state"] = fixtures.file_state(999)
        payload["retained_assets"] = copy.deepcopy(
            payload["projects"][0]["retained_assets"]
        )
        cleanup = contracts.seal_document("cleanup_receipt", payload)
        plan_payload = copy.deepcopy(self.family["recovery_plan"]["payload"])
        plan_payload["input_evidence"] = fixtures.build_input_evidence(
            self.manifest,
            self.family["apply_receipt"],
            self.family["deployment_evidence"],
            cleanup,
        )
        plan = contracts.seal_document("recovery_plan", plan_payload)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.manifest,
                {**self.stages(), "cleanup_receipt": cleanup, "recovery_plan": plan},
            )


class FifthReviewRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.family = fixtures.build_fixture_family()
        cls.manifest = cls.family["manifest"]

    def stages(self):
        return {
            kind: self.family[kind]
            for kind in (
                "apply_receipt",
                "deployment_evidence",
                "verification",
                "cleanup_receipt",
            )
        }

    def test_repeated_deployment_digests_agree_without_raw_bytes(self) -> None:
        for kind in ("cleanup_receipt", "recovery_plan", "recovery_receipt"):
            payload = copy.deepcopy(self.family[kind]["payload"])
            if kind == "cleanup_receipt":
                payload["deployment_evidence_hash"] = fixtures.digest_number(999)
            else:
                payload["input_evidence"]["deployment_evidence"]["state"][
                    "checksum"
                ] = fixtures.digest_number(999)
            document = contracts.seal_document(kind, payload)
            with self.subTest(kind=kind), self.assertRaises(ContractError):
                contracts.validate_declared_bindings(
                    self.manifest, {**self.stages(), kind: document}
                )

    def test_failed_verification_candidates_override_older_recovery_snapshots(
        self,
    ) -> None:
        payload = copy.deepcopy(self.family["recovery_plan"]["payload"])
        payload["steps"] = [
            step for step in payload["steps"] if step["phase"] != "cleanup"
        ]
        kept = {step["step_id"] for step in payload["steps"]}
        groups = {}
        for step in payload["steps"]:
            step["depends_on"] = [item for item in step["depends_on"] if item in kept]
            groups.setdefault(step["resource_id"], []).append(step)
        for entry in payload["resources"]:
            group = groups[entry["resource_id"]]
            entry["state"] = copy.deepcopy(group[0]["expected_current"])
            entry["operation_ids"] = sorted(
                op for step in group for op in step["operation_ids"]
            )
        payload["shared_operation_ids"] = sorted(
            op
            for step in payload["steps"]
            if step["resource_id"] == fixtures.resource_id_of("s1")
            for op in step["operation_ids"]
        )
        payload["input_evidence"]["cleanup_receipt"] = None
        plan = contracts.seal_document("recovery_plan", payload)
        verification_payload = copy.deepcopy(self.family["verification"]["payload"])
        verification_payload["status"] = "failed"
        verification_payload["projects"][0].update(
            status="failed", reason="inspection failed", nextStep="inspect"
        )
        control = contracts.seal_document(
            "verification", copy.deepcopy(verification_payload)
        )
        documents = {
            "apply_receipt": self.family["apply_receipt"],
            "deployment_evidence": self.family["deployment_evidence"],
            "verification": control,
            "recovery_plan": plan,
        }
        contracts.validate_declared_bindings(self.manifest, documents)
        verification_payload["projects"][0]["cleanup_candidates"][0]["state"] = (
            fixtures.file_state(999)
        )
        documents["verification"] = contracts.seal_document(
            "verification", verification_payload
        )
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(self.manifest, documents)

    def test_grouped_shared_results_preserve_operation_level_project_routes(
        self,
    ) -> None:
        payload = copy.deepcopy(self.manifest["payload"])
        first = next(
            op for op in payload["shared_operations"] if op["phase"] == "apply"
        )
        second = copy.deepcopy(first)
        first["dependent_projects"] = [fixtures.ALPHA]
        second["dependent_projects"] = [fixtures.BETA]
        second["selector"] = "other-entry"
        second["ownership"]["key_path"] = ["other"]
        second["operation_id"] = contracts.operation_id(
            "apply", second["resource_id"], second["selector"]
        )
        payload["shared_operations"].append(second)
        payload["projects"][1]["shared_operation_ids"] = [
            op_id
            for op_id in payload["projects"][1]["shared_operation_ids"]
            if op_id != first["operation_id"]
        ] + [second["operation_id"]]
        manifest = contracts.seal_document("manifest", payload)
        receipt_payload = fixtures.build_apply_receipt_payload(manifest)
        receipt_payload["projects"][1]["shared_operation_ids"] = [
            second["operation_id"]
        ]
        receipt_payload["shared_results"][0]["operation_ids"].append(
            second["operation_id"]
        )
        receipt = contracts.seal_document(
            "apply_receipt", copy.deepcopy(receipt_payload)
        )
        contracts.validate_declared_bindings(manifest, {"apply_receipt": receipt})
        receipt_payload["status"] = "failed"
        for project in receipt_payload["projects"]:
            project.update(
                status="failed", reason="other step failed", nextStep="inspect"
            )
            project["shared_operation_ids"] = [
                first["operation_id"],
                second["operation_id"],
            ]
        wrong = contracts.seal_document("apply_receipt", receipt_payload)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(manifest, {"apply_receipt": wrong})

    def test_cleanup_cannot_target_a_candidate_or_its_container(self) -> None:
        candidate = self.manifest["payload"]["publication_decisions"]["items"][0][
            "candidate_ref"
        ]
        # The overlapping targets stay strictly below the appended shared root
        # so only the candidate-overlap guard can reject these manifests.
        for target, owner, state in (
            (candidate["path"], "file", candidate["state"]),
            (
                candidate["path"] + "/nested",
                "directory",
                fixtures.directory_state(901),
            ),
        ):
            payload = copy.deepcopy(self.manifest["payload"])
            rid = contracts.resource_id(owner, target)
            operation = {
                "operation_id": contracts.operation_id(
                    "cleanup", rid, "whole-resource"
                ),
                "phase": "cleanup",
                "resource_id": rid,
                "owner_kind": owner,
                "target": target,
                "selector": "whole-resource",
                "change": {"kind": "remove"},
                "ownership": {
                    "kind": "template-source",
                    "reference": copy.deepcopy(candidate),
                },
                "before_requirement": {"kind": "state", "state": copy.deepcopy(state)},
                "dependent_projects": list(fixtures.BOTH),
            }
            payload["shared_operations"].append(operation)
            for project in payload["projects"]:
                project["shared_operation_ids"].append(operation["operation_id"])
            payload["shared_roots"].append(
                {
                    "kind": "home",
                    "path": str(Path(candidate["path"]).parent),
                    "dependent_projects": list(fixtures.BOTH),
                }
            )
            with self.subTest(target=target), self.assertRaises(ContractError):
                contracts.seal_document("manifest", payload)

    def test_whole_resource_removal_cannot_claim_a_present_after_state(self) -> None:
        payload = copy.deepcopy(self.family["cleanup_receipt"]["payload"])
        result = next(
            r
            for r in payload["projects"][0]["private_results"]
            if r["resource_id"] == fixtures.resource_id_of("r2")
        )
        result["after"] = fixtures.resource_state("r2", "apply")
        cleanup = contracts.seal_document("cleanup_receipt", payload)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.manifest, {"cleanup_receipt": cleanup}
            )

    def test_shared_publication_paths_have_one_state_snapshot(self) -> None:
        for boundary in ("sources", "candidate_ref"):
            document = fixtures.build_publication_decisions()
            clone = copy.deepcopy(document["items"][0])
            clone["item_id"] = "another-projection"
            clone["target_path"] = fixtures.ALPHA + "/docs/spec/another.md"
            clone["approval"]["scope"]["target_path"] = clone["target_path"]
            document["items"].append(clone)
            contracts.validate_document(document, "publication_decisions")
            if boundary == "sources":
                clone["sources"][0]["state"] = fixtures.file_state(999)
            else:
                clone["candidate_ref"]["state"] = fixtures.file_state(999)
            clone["approval"]["scope"][boundary] = copy.deepcopy(clone[boundary])
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.validate_document(document, "publication_decisions")

    @unittest.skipIf(sys.platform == "win32", "POSIX normalization boundary")
    def test_posix_double_leading_slash_is_not_a_distinct_path(self) -> None:
        document = fixtures.build_publication_decisions()
        item = document["items"][0]
        item["sources"][0]["path"] = "/" + item["sources"][0]["path"]
        item["approval"]["scope"]["sources"] = copy.deepcopy(item["sources"])
        with self.assertRaises(ContractError):
            contracts.validate_document(document, "publication_decisions")

    def test_raw_evidence_requires_a_mapping_even_when_empty(self) -> None:
        for invalid in (
            [],
            b"x",
            [("manifest", contracts.canonical_json_bytes(self.manifest))],
        ):
            with (
                self.subTest(raw_type=type(invalid).__name__),
                self.assertRaises(ContractError),
            ):
                contracts.validate_declared_bindings(self.manifest, {}, invalid)


class SixthReviewRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.family = fixtures.build_fixture_family()
        cls.manifest = cls.family["manifest"]

    def test_concrete_before_state_matches_the_resource_category(self) -> None:
        for key, state in (
            ("r1", fixtures.directory_state(999)),
            ("r2", fixtures.file_state(999)),
        ):
            payload = copy.deepcopy(self.manifest["payload"])
            operation = next(
                op
                for op in payload["projects"][0]["private_operations"]
                if op["resource_id"] == fixtures.resource_id_of(key)
                and op["phase"] == "apply"
            )
            operation["before_requirement"]["state"] = state
            with self.subTest(resource=key), self.assertRaises(ContractError):
                contracts.seal_document("manifest", payload)

    def test_directory_operations_require_complete_ownership(self) -> None:
        for boundary in ("selector", "proof"):
            payload = copy.deepcopy(self.manifest["payload"])
            operation = next(
                op
                for op in payload["projects"][0]["private_operations"]
                if op["resource_id"] == fixtures.resource_id_of("r2")
                and op["phase"] == "cleanup"
            )
            if boundary == "selector":
                operation["selector"] = "child-entry"
                operation["operation_id"] = contracts.operation_id(
                    "cleanup", operation["resource_id"], operation["selector"]
                )
            else:
                operation["ownership"] = copy.deepcopy(
                    fixtures.build_operation("r1", "cleanup")["ownership"]
                )
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.seal_document("manifest", payload)

    def test_managed_parent_directory_cannot_overlap_another_resource(self) -> None:
        payload = copy.deepcopy(self.manifest["payload"])
        operation = fixtures.build_operation("r2", "apply")
        operation["target"] = str(Path(fixtures.RESOURCES["r1"][1]).parent)
        operation["resource_id"] = contracts.resource_id(
            "directory", operation["target"]
        )
        operation["operation_id"] = contracts.operation_id(
            "apply", operation["resource_id"], "whole-resource"
        )
        payload["projects"][0]["private_operations"].append(operation)
        with self.assertRaises(ContractError):
            contracts.seal_document("manifest", payload)

    def test_backup_objects_cannot_use_parent_child_paths(self) -> None:
        payload = copy.deepcopy(self.family["apply_receipt"]["payload"])
        payload["projects"][0]["private_results"][0]["backup_ref"]["path"] = (
            fixtures.BACKUP_ROOT + "/item"
        )
        payload["projects"][1]["private_results"][0]["backup_ref"]["path"] = (
            fixtures.BACKUP_ROOT + "/item/child"
        )
        receipt = contracts.seal_document("apply_receipt", payload)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.manifest, {"apply_receipt": receipt}
            )

    def test_envelope_identifiers_require_mapping_shape(self) -> None:
        for invalid in ([], "", b"x", [("manifest_id", None)]):
            with (
                self.subTest(kind=type(invalid).__name__),
                self.assertRaises(ContractError),
            ):
                contracts.make_envelope(
                    "migration",
                    "plan",
                    "blocked",
                    [],
                    "input unavailable",
                    "inspect",
                    identifiers=invalid,
                )

    def test_one_operation_cannot_belong_to_two_result_resources(self) -> None:
        for boundary in ("private", "shared"):
            payload = copy.deepcopy(self.family["apply_receipt"]["payload"])
            duplicate = list(
                payload["projects"][0]["private_results"][0]["operation_ids"]
            )
            if boundary == "private":
                payload["projects"][1]["private_results"][0]["operation_ids"] = (
                    duplicate
                )
            else:
                payload["shared_results"][0]["operation_ids"] = duplicate
                for project in payload["projects"]:
                    project["shared_operation_ids"] = list(duplicate)
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.seal_document("apply_receipt", payload)

    def test_cleanup_cannot_remove_an_approved_publication_target(self) -> None:
        payload = copy.deepcopy(self.manifest["payload"])
        operation = fixtures.build_operation("r4", "apply")
        operation.update(phase="cleanup", change={"kind": "remove"})
        operation["operation_id"] = contracts.operation_id(
            "cleanup", operation["resource_id"], operation["selector"]
        )
        operation["before_requirement"] = {
            "kind": "phase-after",
            "phase": "apply",
            "resource_id": operation["resource_id"],
        }
        payload["projects"][0]["private_operations"].append(operation)
        with self.assertRaises(ContractError):
            contracts.seal_document("manifest", payload)

    def test_downstream_apply_ids_agree_without_the_apply_document(self) -> None:
        verification_payload = copy.deepcopy(self.family["verification"]["payload"])
        verification_payload["apply_id"] = fixtures.digest_number(999)
        verification = contracts.seal_document("verification", verification_payload)
        with (
            self.subTest(boundary="deployment and verification"),
            self.assertRaises(ContractError),
        ):
            contracts.validate_declared_bindings(
                self.manifest,
                {
                    "deployment_evidence": self.family["deployment_evidence"],
                    "verification": verification,
                },
            )
        cleanup_payload = copy.deepcopy(self.family["cleanup_receipt"]["payload"])
        cleanup_payload.update(
            apply_id=verification_payload["apply_id"],
            verification_id=verification["verification_id"],
        )
        cleanup = contracts.seal_document("cleanup_receipt", cleanup_payload)
        with (
            self.subTest(boundary="full downstream chain"),
            self.assertRaises(ContractError),
        ):
            contracts.validate_declared_bindings(
                self.manifest,
                {
                    "deployment_evidence": self.family["deployment_evidence"],
                    "verification": verification,
                    "cleanup_receipt": cleanup,
                },
            )

    def test_shared_cleanup_candidates_use_only_cleanup_dependents(self) -> None:
        payload = copy.deepcopy(self.manifest["payload"])
        operation = next(
            op for op in payload["shared_operations"] if op["phase"] == "cleanup"
        )
        operation["dependent_projects"] = [fixtures.BETA]
        payload["projects"][0]["shared_operation_ids"] = [
            op_id
            for op_id in payload["projects"][0]["shared_operation_ids"]
            if op_id != operation["operation_id"]
        ]
        manifest = contracts.seal_document("manifest", payload)
        applied = fixtures.build_apply_receipt(manifest)
        deployed = fixtures.build_deployment_evidence(manifest, applied)
        verification_payload = fixtures.build_verification_payload(
            manifest, applied, deployed
        )
        verification_payload["shared_cleanup_candidates"][0]["dependent_projects"] = [
            fixtures.BETA
        ]
        control = contracts.seal_document(
            "verification", copy.deepcopy(verification_payload)
        )
        base = {"apply_receipt": applied, "deployment_evidence": deployed}
        with self.subTest(boundary="phase-specific closure"):
            contracts.validate_declared_bindings(
                manifest, {**base, "verification": control}
            )
        wrong_payload = copy.deepcopy(verification_payload)
        wrong_payload["shared_cleanup_candidates"][0]["dependent_projects"] = list(
            fixtures.BOTH
        )
        wrong = contracts.seal_document("verification", wrong_payload)
        with (
            self.subTest(boundary="unrelated phase dependency"),
            self.assertRaises(ContractError),
        ):
            contracts.validate_declared_bindings(
                manifest, {**base, "verification": wrong}
            )
        verification_payload["status"] = "failed"
        verification_payload["projects"][1].update(
            status="failed", reason="candidate unavailable", nextStep="inspect"
        )
        verification_payload["shared_cleanup_candidates"] = []
        partial = contracts.seal_document("verification", verification_payload)
        with self.subTest(boundary="independent verified project"):
            contracts.validate_declared_bindings(
                manifest, {**base, "verification": partial}
            )

    def test_recovery_protection_path_cannot_claim_two_original_states(self) -> None:
        payload = copy.deepcopy(self.family["recovery_receipt"]["payload"])
        protected = [
            result
            for result in payload["results"]
            if result["protection_ref"] is not None
        ]
        protected[1]["protection_ref"]["path"] = protected[0]["protection_ref"]["path"]
        with self.assertRaises(ContractError):
            contracts.seal_document("recovery_receipt", payload)


class SeventhReviewRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.family = fixtures.build_fixture_family()
        cls.manifest = cls.family["manifest"]
        cls.apply_receipt = cls.family["apply_receipt"]
        cls.deployment = cls.family["deployment_evidence"]
        cls.verification = cls.family["verification"]
        cls.cleanup = cls.family["cleanup_receipt"]
        cls.plan = cls.family["recovery_plan"]
        cls.receipt = cls.family["recovery_receipt"]

    def recovery_documents(self, receipt):
        return {
            "apply_receipt": self.apply_receipt,
            "deployment_evidence": self.deployment,
            "cleanup_receipt": self.cleanup,
            "recovery_plan": self.plan,
            "recovery_receipt": receipt,
        }

    def test_whole_resource_operations_require_complete_ownership(self) -> None:
        contracts.validate_document(self.manifest, "manifest")
        r1 = fixtures.resource_id_of("r1")
        for phase, proof in (
            ("apply", "config-entry"),
            ("deploy", "managed-marker"),
            ("cleanup", "config-entry"),
        ):
            payload = copy.deepcopy(self.manifest["payload"])
            operation = next(
                op
                for op in payload["projects"][0]["private_operations"]
                if op["resource_id"] == r1 and op["phase"] == phase
            )
            self.assertEqual(operation["ownership"]["kind"], proof)
            operation["selector"] = "whole-resource"
            operation["operation_id"] = contracts.operation_id(
                phase, operation["resource_id"], operation["selector"]
            )
            with self.subTest(phase=phase), self.assertRaises(ContractError):
                contracts.seal_document("manifest", payload)

    def test_successful_copy_result_must_match_the_declared_source(self) -> None:
        contracts.validate_declared_bindings(
            self.manifest, {"apply_receipt": self.apply_receipt}
        )
        for key, wrong_after in (
            ("r1", fixtures.file_state(999)),
            ("r2", fixtures.directory_state(999)),
            ("s1", fixtures.file_state(999)),
        ):
            payload = copy.deepcopy(self.apply_receipt["payload"])
            if key == "s1":
                result = payload["shared_results"][0]
            else:
                result = next(
                    entry
                    for entry in payload["projects"][0]["private_results"]
                    if entry["resource_id"] == fixtures.resource_id_of(key)
                )
            result["after"] = copy.deepcopy(wrong_after)
            receipt = contracts.seal_document("apply_receipt", payload)
            with self.subTest(resource=key), self.assertRaises(ContractError):
                contracts.validate_declared_bindings(
                    self.manifest, {"apply_receipt": receipt}
                )

    def test_cleanup_cannot_alter_retained_ancestors_or_descendants(self) -> None:
        r2_target = fixtures.RESOURCES["r2"][1]

        def family_with_retained(asset):
            # Omit verification so its earlier overlap guard cannot mask the
            # cleanup receipt's independently enforceable retention boundary.
            cleanup_payload = copy.deepcopy(self.cleanup["payload"])
            cleanup_payload["projects"][0]["retained_assets"].append(
                copy.deepcopy(asset)
            )
            cleanup_payload["retained_assets"].append(copy.deepcopy(asset))
            cleanup = contracts.seal_document("cleanup_receipt", cleanup_payload)
            return {
                "apply_receipt": self.apply_receipt,
                "deployment_evidence": self.deployment,
                "cleanup_receipt": cleanup,
            }

        contracts.validate_declared_bindings(
            self.manifest,
            family_with_retained(
                {
                    "path": fixtures.ALPHA + "/docs/spec/extra-notes.md",
                    "state": fixtures.file_state(84),
                }
            ),
        )
        for boundary, asset in (
            (
                "descendant",
                {"path": r2_target + "/keep.txt", "state": fixtures.file_state(85)},
            ),
            (
                "ancestor",
                {
                    "path": str(Path(r2_target).parent),
                    "state": fixtures.directory_state(86),
                },
            ),
        ):
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.validate_declared_bindings(
                    self.manifest, family_with_retained(asset)
                )

    def test_original_backups_cannot_overlap_publication_candidates(self) -> None:
        candidate_path = fixtures.BACKUP_ROOT + "/candidates/notes.md"
        manifest_payload = copy.deepcopy(self.manifest["payload"])
        item = manifest_payload["publication_decisions"]["items"][0]
        item["candidate_ref"]["path"] = candidate_path
        item["approval"]["scope"]["candidate_ref"]["path"] = candidate_path
        r4 = fixtures.resource_id_of("r4")
        for operation in manifest_payload["projects"][0]["private_operations"]:
            if operation["resource_id"] == r4:
                operation["change"]["source_ref"]["path"] = candidate_path
                operation["ownership"]["reference"]["path"] = candidate_path
        manifest = contracts.seal_document("manifest", manifest_payload)
        receipt_payload = fixtures.build_apply_receipt_payload(manifest)
        control = contracts.seal_document(
            "apply_receipt", copy.deepcopy(receipt_payload)
        )
        contracts.validate_declared_bindings(manifest, {"apply_receipt": control})
        r1 = fixtures.resource_id_of("r1")
        for boundary, backup_path in (
            ("equal", candidate_path),
            ("parent", str(Path(candidate_path).parent)),
        ):
            payload = copy.deepcopy(receipt_payload)
            result = next(
                entry
                for entry in payload["projects"][0]["private_results"]
                if entry["resource_id"] == r1
            )
            result["backup_ref"] = {
                "path": backup_path,
                "state": fixtures.resource_state("r1", "orig"),
            }
            receipt = contracts.seal_document("apply_receipt", payload)
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.validate_declared_bindings(
                    manifest, {"apply_receipt": receipt}
                )

    def test_successful_before_state_must_match_the_owner_category(self) -> None:
        # A later-phase receipt binds without its predecessor, so its recorded
        # before-state must still fit the declared resource owner.
        contracts.validate_declared_bindings(
            self.manifest, {"cleanup_receipt": self.cleanup}
        )
        payload = copy.deepcopy(self.cleanup["payload"])
        result = next(
            entry
            for entry in payload["projects"][0]["private_results"]
            if entry["resource_id"] == fixtures.resource_id_of("r1")
        )
        result["before"] = fixtures.directory_state(999)
        result["backup_ref"] = {
            "path": fixtures.BACKUP_ROOT + "/r1-deploy",
            "state": fixtures.directory_state(999),
        }
        cleanup = contracts.seal_document("cleanup_receipt", payload)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.manifest, {"cleanup_receipt": cleanup}
            )

    def test_cleanup_candidates_bind_each_operation_to_one_resource(self) -> None:
        contracts.validate_document(self.verification, "verification")
        payload = copy.deepcopy(self.verification["payload"])
        clone = copy.deepcopy(payload["shared_cleanup_candidates"][0])
        target = "/private/home/.codex/second-config.json"
        clone["resource_id"] = contracts.resource_id("json", target)
        clone["target"] = target
        clone["state"] = fixtures.file_state(55)
        payload["shared_cleanup_candidates"].append(clone)
        with self.assertRaises(ContractError):
            contracts.seal_document("verification", payload)

    def test_cleanup_candidates_bind_each_target_to_one_resource(self) -> None:
        contracts.validate_document(self.verification, "verification")
        payload = copy.deepcopy(self.verification["payload"])
        clone = copy.deepcopy(payload["projects"][0]["cleanup_candidates"][0])
        clone["resource_id"] = contracts.resource_id("toml", clone["target"])
        clone["operation_ids"] = [
            contracts.operation_id("cleanup", clone["resource_id"], "whole-resource")
        ]
        payload["shared_cleanup_candidates"].append(clone)
        with self.assertRaises(ContractError):
            contracts.seal_document("verification", payload)

    def test_manifest_project_sources_cannot_conflict(self) -> None:
        contracts.validate_document(self.manifest, "manifest")
        source = self.manifest["payload"]["projects"][0]["sources"][0]
        other = (
            fixtures.file_state
            if source["state"]["type"] == "directory"
            else fixtures.directory_state
        )
        for conflicting in (
            {
                "type": source["state"]["type"],
                "checksum": fixtures.digest_number(999),
            },
            other(999),
        ):
            payload = copy.deepcopy(self.manifest["payload"])
            payload["projects"][0]["sources"].append(
                {"path": source["path"], "state": conflicting}
            )
            with (
                self.subTest(conflicting=conflicting["type"]),
                self.assertRaises(ContractError),
            ):
                contracts.seal_document("manifest", payload)

    def test_private_targets_must_be_strictly_below_the_project_root(self) -> None:
        for target in (fixtures.BETA, fixtures.BETA + "/managed-dir"):
            payload = copy.deepcopy(self.manifest["payload"])
            rid = contracts.resource_id("directory", target)
            operation = {
                "operation_id": contracts.operation_id("apply", rid, "whole-resource"),
                "phase": "apply",
                "resource_id": rid,
                "owner_kind": "directory",
                "target": target,
                "selector": "whole-resource",
                "change": {
                    "kind": "copy-directory",
                    "source_ref": {
                        "path": "/private/source/beta-root-copy",
                        "state": fixtures.directory_state(91),
                    },
                },
                "ownership": {
                    "kind": "skill-identity",
                    "reference": {
                        "path": "/private/source/beta-root-copy",
                        "state": fixtures.directory_state(91),
                    },
                    "name": "beta-root-copy",
                },
                "before_requirement": {
                    "kind": "state",
                    "state": fixtures.directory_state(90),
                },
                "dependent_projects": [fixtures.BETA],
            }
            payload["projects"][1]["private_operations"] = [operation]
            with self.subTest(target=target):
                if target == fixtures.BETA:
                    with self.assertRaises(ContractError):
                        contracts.seal_document("manifest", payload)
                else:
                    contracts.seal_document("manifest", payload)

    def test_shared_targets_must_be_strictly_below_a_shared_root(self) -> None:
        root = self.manifest["payload"]["shared_roots"][0]["path"]
        for target in (root, root + "/managed-dir"):
            payload = copy.deepcopy(self.manifest["payload"])
            rid = contracts.resource_id("directory", target)
            operation = {
                "operation_id": contracts.operation_id("apply", rid, "whole-resource"),
                "phase": "apply",
                "resource_id": rid,
                "owner_kind": "directory",
                "target": target,
                "selector": "whole-resource",
                "change": {
                    "kind": "copy-directory",
                    "source_ref": {
                        "path": "/private/source/shared-root-copy",
                        "state": fixtures.directory_state(92),
                    },
                },
                "ownership": {
                    "kind": "skill-identity",
                    "reference": {
                        "path": "/private/source/shared-root-copy",
                        "state": fixtures.directory_state(92),
                    },
                    "name": "shared-root-copy",
                },
                "before_requirement": {
                    "kind": "state",
                    "state": fixtures.directory_state(40),
                },
                "dependent_projects": list(fixtures.BOTH),
            }
            payload["shared_operations"] = [operation]
            for project in payload["projects"]:
                project["shared_operation_ids"] = [operation["operation_id"]]
            with self.subTest(target=target):
                if target == root:
                    with self.assertRaises(ContractError):
                        contracts.seal_document("manifest", payload)
                else:
                    contracts.seal_document("manifest", payload)

    def test_recovery_steps_carry_phase_specific_dependents(self) -> None:
        s1 = fixtures.resource_id_of("s1")
        cleanup_op = fixtures.operations_of("s1")["cleanup"]["operation_id"]
        manifest_payload = copy.deepcopy(self.manifest["payload"])
        for operation in manifest_payload["shared_operations"]:
            if operation["phase"] == "cleanup":
                operation["dependent_projects"] = [fixtures.ALPHA]
        manifest_payload["projects"][1]["shared_operation_ids"] = [
            op_id
            for op_id in manifest_payload["projects"][1]["shared_operation_ids"]
            if op_id != cleanup_op
        ]
        manifest = contracts.seal_document("manifest", manifest_payload)
        applied = fixtures.build_apply_receipt(manifest)
        deployed = fixtures.build_deployment_evidence(manifest, applied)
        verification_payload = fixtures.build_verification_payload(
            manifest, applied, deployed
        )
        verification_payload["shared_cleanup_candidates"][0]["dependent_projects"] = [
            fixtures.ALPHA
        ]
        verification = contracts.seal_document("verification", verification_payload)
        cleanup_payload = fixtures.build_cleanup_receipt_payload(
            manifest, applied, deployed, verification
        )
        cleanup_payload["shared_results"][0]["dependent_projects"] = [fixtures.ALPHA]
        cleanup_payload["projects"][1]["shared_operation_ids"] = []
        cleanup = contracts.seal_document("cleanup_receipt", cleanup_payload)
        plan_payload = fixtures.build_recovery_plan_payload(
            manifest, applied, deployed, cleanup
        )

        def s1_cleanup_step(payload):
            return next(
                step
                for step in payload["steps"]
                if step["resource_id"] == s1 and step["phase"] == "cleanup"
            )

        # The step records only its own phase dependents; the resource entry
        # keeps the all-phase union.
        s1_cleanup_step(plan_payload)["dependent_projects"] = [fixtures.ALPHA]
        control = contracts.seal_document("recovery_plan", copy.deepcopy(plan_payload))
        documents = {
            "apply_receipt": applied,
            "deployment_evidence": deployed,
            "verification": verification,
            "cleanup_receipt": cleanup,
        }
        self.assertEqual(
            contracts.validate_declared_bindings(
                manifest, {**documents, "recovery_plan": control}
            )["recovery_plan"],
            control,
        )

        s1_cleanup_step(plan_payload)["dependent_projects"] = list(fixtures.BOTH)
        overstated = contracts.seal_document("recovery_plan", plan_payload)
        with (
            self.subTest(boundary="resource-wide step provenance"),
            self.assertRaises(ContractError),
        ):
            contracts.validate_declared_bindings(
                manifest, {**documents, "recovery_plan": overstated}
            )

        narrowed = copy.deepcopy(control["payload"])
        for entry in narrowed["resources"]:
            if entry["resource_id"] == s1:
                entry["dependent_projects"] = [fixtures.ALPHA]
        with (
            self.subTest(boundary="entry dropped the all-phase union"),
            self.assertRaises(ContractError),
        ):
            bad_entry = contracts.seal_document("recovery_plan", narrowed)
            contracts.validate_declared_bindings(
                manifest, {**documents, "recovery_plan": bad_entry}
            )

    def test_recovery_protection_cannot_overlap_plan_objects_or_candidates(
        self,
    ) -> None:
        def receipt_with_protection(path):
            payload = copy.deepcopy(self.receipt["payload"])
            result = next(
                entry
                for entry in payload["results"]
                if entry["phase"] == "apply"
                and entry["resource_id"] == fixtures.resource_id_of("r1")
            )
            result["protection_ref"]["path"] = path
            return contracts.seal_document("recovery_receipt", payload)

        planned_backup = next(
            step["backup_ref"]["path"]
            for step in self.plan["payload"]["steps"]
            if step["backup_ref"] is not None
        )
        for boundary, path in (
            ("planned backup", planned_backup),
            ("managed target", fixtures.RESOURCES["r4"][1]),
            (
                "input evidence",
                self.receipt["payload"]["input_evidence"]["manifest"]["path"],
            ),
        ):
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.validate_declared_bindings(
                    self.manifest,
                    self.recovery_documents(receipt_with_protection(path)),
                )

        # Standalone validation has no candidate inventory and cannot invent
        # one; the overlap is rejected once the manifest is supplied.
        candidate = fixtures.PUBLICATION_CANDIDATE["path"]
        receipt = receipt_with_protection(candidate)
        contracts.validate_document(receipt, "recovery_receipt")
        with (
            self.subTest(boundary="publication candidate"),
            self.assertRaises(ContractError),
        ):
            contracts.validate_declared_bindings(
                self.manifest, self.recovery_documents(receipt)
            )

    def test_no_phase_can_rewrite_an_approved_candidate(self) -> None:
        candidate = self.manifest["payload"]["publication_decisions"]["items"][0][
            "candidate_ref"
        ]
        candidate_path = candidate["path"]
        container = str(Path(candidate_path).parent)

        def operation(phase, owner, target, change, ownership, selector, before):
            rid = contracts.resource_id(owner, target)
            return {
                "operation_id": contracts.operation_id(phase, rid, selector),
                "phase": phase,
                "resource_id": rid,
                "owner_kind": owner,
                "target": target,
                "selector": selector,
                "change": change,
                "ownership": ownership,
                "before_requirement": {"kind": "state", "state": before},
                "dependent_projects": list(fixtures.BOTH),
            }

        apply_target = operation(
            "apply",
            "markdown",
            candidate_path,
            {
                "kind": "copy-file",
                "source_ref": fixtures._file_ref(
                    "/private/source/candidate-rewrite", 92
                ),
            },
            {
                "kind": "template-source",
                "reference": fixtures._file_ref(
                    "/private/source/candidate-rewrite", 92
                ),
            },
            "whole-resource",
            fixtures.file_state(93),
        )
        apply_child = operation(
            "apply",
            "directory",
            candidate_path + "/nested",
            {
                "kind": "copy-directory",
                "source_ref": {
                    "path": "/private/source/candidate-rewrite-dir",
                    "state": fixtures.directory_state(94),
                },
            },
            {
                "kind": "skill-identity",
                "reference": {
                    "path": "/private/source/candidate-rewrite-dir",
                    "state": fixtures.directory_state(94),
                },
                "name": "candidate-rewrite-dir",
            },
            "whole-resource",
            fixtures.directory_state(95),
        )
        deploy_target = operation(
            "deploy",
            "markdown",
            candidate_path,
            {
                "kind": "ensure-file-block",
                "source_ref": fixtures._file_ref("/private/source/managed-block", 73),
            },
            {
                "kind": "managed-marker",
                "reference": fixtures._file_ref("/private/source/managed-block", 73),
                "marker": "sbtd-managed",
            },
            "sbtd.block",
            fixtures.file_state(93),
        )
        for boundary, added in (
            ("apply target", apply_target),
            ("apply child", apply_child),
            ("deploy target", deploy_target),
        ):
            payload = copy.deepcopy(self.manifest["payload"])
            payload["shared_operations"].append(added)
            for project in payload["projects"]:
                project["shared_operation_ids"].append(added["operation_id"])
            payload["shared_roots"].append(
                {
                    "kind": "home",
                    "path": container,
                    "dependent_projects": list(fixtures.BOTH),
                }
            )
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.seal_document("manifest", payload)

    def test_input_evidence_paths_are_unique_across_kinds(self) -> None:
        manifest_ref = self.plan["payload"]["input_evidence"]["manifest"]
        for boundary in ("conflicting state", "identical ref"):
            payload = copy.deepcopy(self.plan["payload"])
            evidence = payload["input_evidence"]
            if boundary == "conflicting state":
                evidence["apply_receipt"]["path"] = manifest_ref["path"]
                raw = fixtures.fixture_raw_documents(self.family)
            else:
                evidence["apply_receipt"] = copy.deepcopy(manifest_ref)
                raw = fixtures.fixture_raw_documents(self.family)
                del raw["apply_receipt"]
            documents = {
                "apply_receipt": self.apply_receipt,
                "deployment_evidence": self.deployment,
                "cleanup_receipt": self.cleanup,
            }
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                plan = contracts.seal_document("recovery_plan", payload)
                contracts.validate_declared_bindings(
                    self.manifest, {**documents, "recovery_plan": plan}, raw
                )

    def test_report_paths_have_one_state_snapshot(self) -> None:
        payload = copy.deepcopy(self.deployment["payload"])
        beta_report = payload["projects"][1]["report_refs"][0]
        payload["projects"][0]["report_refs"].append(
            {"path": beta_report["path"], "state": fixtures.file_state(999)}
        )
        with (
            self.subTest(document="deployment_evidence"),
            self.assertRaises(ContractError),
        ):
            deployment = contracts.seal_document("deployment_evidence", payload)
            contracts.validate_declared_bindings(
                self.manifest, {"deployment_evidence": deployment}
            )

        payload = copy.deepcopy(self.receipt["payload"])
        payload["runtime_readiness"] = "verified"
        payload["report_refs"] = [
            {
                "path": fixtures.EVIDENCE_DIR + "/restore-smoke.json",
                "state": fixtures.file_state(201),
            },
            {
                "path": fixtures.EVIDENCE_DIR + "/restore-smoke.json",
                "state": fixtures.file_state(202),
            },
        ]
        with (
            self.subTest(document="recovery_receipt"),
            self.assertRaises(ContractError),
        ):
            receipt = contracts.seal_document("recovery_receipt", payload)
            contracts.validate_declared_bindings(
                self.manifest, self.recovery_documents(receipt)
            )

    def test_recovery_follows_supplied_verification_observations(self) -> None:
        plan_payload = copy.deepcopy(self.plan["payload"])
        plan_payload["steps"] = [
            step for step in plan_payload["steps"] if step["phase"] != "cleanup"
        ]
        kept = {step["step_id"] for step in plan_payload["steps"]}
        groups = {}
        for step in plan_payload["steps"]:
            step["depends_on"] = [
                dependency for dependency in step["depends_on"] if dependency in kept
            ]
            groups.setdefault(step["resource_id"], []).append(step)
        for entry in plan_payload["resources"]:
            group = groups[entry["resource_id"]]
            entry["state"] = copy.deepcopy(group[0]["expected_current"])
            entry["operation_ids"] = sorted(
                op_id for step in group for op_id in step["operation_ids"]
            )
        plan_payload["shared_operation_ids"] = sorted(
            op_id
            for step in plan_payload["steps"]
            if step["resource_id"] == fixtures.resource_id_of("s1")
            for op_id in step["operation_ids"]
        )
        plan_payload["input_evidence"]["cleanup_receipt"] = None
        verification_payload = copy.deepcopy(self.verification["payload"])
        verification_payload["status"] = "failed"
        verification_payload["projects"][0].update(
            status="failed", reason="inspection failed", nextStep="inspect"
        )
        verification_payload["verified_at"] = "2026-09-18T04:30:00Z"
        verification = contracts.seal_document("verification", verification_payload)
        documents = {
            "apply_receipt": self.apply_receipt,
            "deployment_evidence": self.deployment,
            "verification": verification,
        }
        plan_payload["created_at"] = "2026-09-18T04:35:00Z"
        control = contracts.seal_document("recovery_plan", copy.deepcopy(plan_payload))
        contracts.validate_declared_bindings(
            self.manifest, {**documents, "recovery_plan": control}
        )
        plan_payload["created_at"] = "2026-09-18T04:15:00Z"
        early = contracts.seal_document("recovery_plan", plan_payload)
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.manifest, {**documents, "recovery_plan": early}
            )

    def test_unwritten_failure_retry_cannot_advance_without_an_original(
        self,
    ) -> None:
        previous_payload = copy.deepcopy(self.apply_receipt["payload"])
        project = previous_payload["projects"][0]
        result = project["private_results"][0]
        result.update(status="failed", error="write did not begin", backup_ref=None)
        result["after"] = copy.deepcopy(result["before"])
        project.update(
            status="failed",
            reason="write did not begin",
            nextStep="retry the resource",
        )
        previous_payload["status"] = "failed"
        previous = contracts.seal_document("apply_receipt", previous_payload)

        def retry_payload():
            payload = copy.deepcopy(previous_payload)
            payload["previous_receipt_id"] = previous["apply_id"]
            payload["started_at"] = previous["payload"]["finished_at"]
            payload["finished_at"] = previous["payload"]["finished_at"]
            return payload

        control = contracts.seal_document("apply_receipt", retry_payload())
        contracts.validate_cumulative(previous, control, "apply_receipt")
        acquired = retry_payload()
        acquired_result = acquired["projects"][0]["private_results"][0]
        acquired_result["after"] = fixtures.file_state(999)
        acquired_result["backup_ref"] = fixtures.backup_ref_of("r1", "orig")
        contracts.validate_cumulative(
            previous,
            contracts.seal_document("apply_receipt", acquired),
            "apply_receipt",
        )
        for outcome in ("changed", "unknown"):
            attempt = retry_payload()
            attempt_result = attempt["projects"][0]["private_results"][0]
            attempt_result["after"] = (
                fixtures.file_state(999) if outcome == "changed" else None
            )
            current = contracts.seal_document("apply_receipt", attempt)
            with (
                self.subTest(kind="apply_receipt", outcome=outcome),
                self.assertRaises(ContractError),
            ):
                contracts.validate_cumulative(previous, current, "apply_receipt")

        previous_payload = copy.deepcopy(self.receipt["payload"])
        failed = next(
            entry
            for entry in previous_payload["results"]
            if entry["phase"] == "apply"
            and entry["resource_id"] == fixtures.resource_id_of("r1")
        )
        failed.update(
            status="failed", error="restore did not begin", protection_ref=None
        )
        failed["after"] = copy.deepcopy(failed["before"])
        previous_payload["completed_step_ids"].remove(failed["step_id"])
        previous_payload["pending_step_ids"].append(failed["step_id"])
        previous_payload["status"] = "failed"
        previous_payload["reason"] = "restore did not begin"
        previous_payload["projects"][0].update(
            status="failed",
            reason="restore did not begin",
            nextStep="retry the step",
        )
        previous = contracts.seal_document("recovery_receipt", previous_payload)

        def recovery_retry_payload():
            payload = copy.deepcopy(previous_payload)
            payload["previous_receipt_id"] = previous["receipt_id"]
            payload["started_at"] = previous["payload"]["finished_at"]
            payload["finished_at"] = previous["payload"]["finished_at"]
            return payload

        control = contracts.seal_document("recovery_receipt", recovery_retry_payload())
        contracts.validate_cumulative(previous, control, "recovery_receipt")
        for outcome in ("changed", "unknown"):
            attempt = recovery_retry_payload()
            attempt_result = next(
                entry
                for entry in attempt["results"]
                if entry["step_id"] == failed["step_id"]
            )
            attempt_result["after"] = (
                fixtures.file_state(999) if outcome == "changed" else None
            )
            current = contracts.seal_document("recovery_receipt", attempt)
            with (
                self.subTest(kind="recovery_receipt", outcome=outcome),
                self.assertRaises(ContractError),
            ):
                contracts.validate_cumulative(previous, current, "recovery_receipt")

    def test_recovery_operation_ids_bind_to_one_resource(self) -> None:
        r1_cleanup = fixtures.operations_of("r1")["cleanup"]["operation_id"]
        r3 = fixtures.resource_id_of("r3")
        r3_ops = fixtures.operations_of("r3")
        payload = copy.deepcopy(self.plan["payload"])
        for step in payload["steps"]:
            if step["phase"] == "cleanup" and step["resource_id"] == r3:
                step["operation_ids"] = [r1_cleanup]
        for entry in payload["resources"]:
            if entry["resource_id"] == r3:
                entry["operation_ids"] = sorted(
                    [
                        r3_ops["apply"]["operation_id"],
                        r3_ops["deploy"]["operation_id"],
                        r1_cleanup,
                    ]
                )
        with (
            self.subTest(document="recovery_plan"),
            self.assertRaises(ContractError),
        ):
            contracts.seal_document("recovery_plan", payload)

        payload = copy.deepcopy(self.receipt["payload"])
        for result in payload["results"]:
            if result["phase"] == "cleanup" and result["resource_id"] == r3:
                result["operation_ids"] = [r1_cleanup]
        with (
            self.subTest(document="recovery_receipt"),
            self.assertRaises(ContractError),
        ):
            contracts.seal_document("recovery_receipt", payload)

    def test_standalone_plan_resources_keep_canonical_ids_and_concrete_states(
        self,
    ) -> None:
        r4 = fixtures.resource_id_of("r4")
        for boundary in ("target", "owner_kind", "state type"):
            payload = copy.deepcopy(self.plan["payload"])
            entry = next(
                item for item in payload["resources"] if item["resource_id"] == r4
            )
            if boundary == "target":
                entry["target"] = fixtures.ALPHA + "/docs/spec/substituted.md"
            elif boundary == "owner_kind":
                entry["owner_kind"] = "toml"
            else:
                entry["state"] = fixtures.directory_state(82)
                step = next(
                    item for item in payload["steps"] if item["resource_id"] == r4
                )
                step["expected_current"] = fixtures.directory_state(82)
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.seal_document("recovery_plan", payload)


class EighthReviewRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.family = fixtures.build_fixture_family()

    def nested_project_payload(self):
        payload = copy.deepcopy(self.family["manifest"]["payload"])
        outer = str(Path(fixtures.ALPHA).parent)
        payload["projects"][0]["root"] = outer
        for operation in payload["projects"][0]["private_operations"]:
            operation["dependent_projects"] = [outer]
        for operation in payload["shared_operations"]:
            operation["dependent_projects"] = sorted([outer, fixtures.BETA])
        for shared_root in payload["shared_roots"]:
            shared_root["dependent_projects"] = sorted([outer, fixtures.BETA])
        return payload

    def move_publication(self, payload, target, project_index):
        operations = payload["projects"][0]["private_operations"]
        operation = next(
            op
            for op in operations
            if op["resource_id"] == fixtures.resource_id_of("r4")
        )
        operations.remove(operation)
        owner = payload["projects"][project_index]
        operation["target"] = target
        operation["resource_id"] = contracts.resource_id("markdown", target)
        operation["operation_id"] = contracts.operation_id(
            "apply", operation["resource_id"], operation["selector"]
        )
        operation["dependent_projects"] = [owner["root"]]
        owner["private_operations"].append(operation)
        item = payload["publication_decisions"]["items"][0]
        item["target_path"] = target
        item["approval"]["scope"]["target_path"] = target

    def test_shared_target_cannot_equal_a_nested_declared_root(self) -> None:
        payload = copy.deepcopy(self.family["manifest"]["payload"])
        inner = copy.deepcopy(payload["shared_roots"][0])
        target = inner["path"]
        outer = {
            "kind": "home",
            "path": str(Path(target).parent),
            "dependent_projects": list(fixtures.BOTH),
        }
        operation = copy.deepcopy(fixtures.operations_of("r2")["apply"])
        operation["target"] = target
        operation["resource_id"] = contracts.resource_id("directory", target)
        operation["operation_id"] = contracts.operation_id(
            "apply", operation["resource_id"], "whole-resource"
        )
        operation["dependent_projects"] = list(fixtures.BOTH)
        operation["ownership"] = {
            "kind": "template-source",
            "reference": copy.deepcopy(operation["change"]["source_ref"]),
        }
        payload["shared_operations"] = [operation]
        for project in payload["projects"]:
            project["shared_operation_ids"] = [operation["operation_id"]]
        payload["shared_roots"] = [outer]
        contracts.seal_document("manifest", copy.deepcopy(payload))
        payload["shared_roots"].append(inner)
        with self.assertRaises(ContractError):
            contracts.seal_document("manifest", payload)

    def test_manifest_snapshots_agree_across_reference_roles(self) -> None:
        base = self.family["manifest"]["payload"]
        for boundary in ("publication", "copy source", "ownership"):
            payload = copy.deepcopy(base)
            if boundary == "publication":
                path = payload["publication_decisions"]["items"][0]["sources"][0][
                    "path"
                ]
                reference = next(
                    ref
                    for ref in payload["projects"][0]["sources"]
                    if ref["path"] == path
                )
                reference["state"] = fixtures.file_state(999)
            else:
                operation = next(
                    op
                    for op in payload["projects"][0]["private_operations"]
                    if op["resource_id"] == fixtures.resource_id_of("r1")
                    and op["phase"] == "apply"
                )
                reference = (
                    operation["change"]["source_ref"]
                    if boundary == "copy source"
                    else operation["ownership"]["reference"]
                )
                reference["path"] = operation["target"]
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.seal_document("manifest", payload)
        # A source alias is not itself contradictory when it records the same
        # initial state. Later phase-after states are not initial observations.
        payload = copy.deepcopy(base)
        operation = next(
            op
            for op in payload["projects"][0]["private_operations"]
            if op["resource_id"] == fixtures.resource_id_of("r1")
            and op["phase"] == "apply"
        )
        operation["change"]["source_ref"] = {
            "path": operation["target"],
            "state": copy.deepcopy(operation["before_requirement"]["state"]),
        }
        contracts.seal_document("manifest", payload)

    def test_recursive_python_values_have_a_controlled_error(self) -> None:
        cycle = copy.deepcopy(self.family["manifest"])
        cycle["payload"]["recursive-value-sentinel"] = cycle
        deep = copy.deepcopy(self.family["manifest"])
        nested = []
        for _ in range(1500):
            nested = [nested]
        deep["payload"]["recursive-value-sentinel"] = nested
        for boundary, value in (("cycle", cycle), ("depth", deep)):
            with self.subTest(boundary=boundary):
                with self.assertRaises(ContractError) as caught:
                    contracts.validate_document(value, "manifest")
                self.assertNotIn("recursive-value-sentinel", str(caught.exception))

    def test_private_owner_is_the_most_specific_selected_project(self) -> None:
        payload = self.nested_project_payload()
        contracts.seal_document("manifest", copy.deepcopy(payload))
        target = fixtures.BETA + "/outer-write.md"
        self.move_publication(payload, target, 0)
        with self.assertRaises(ContractError):
            contracts.seal_document("manifest", payload)
        payload = self.nested_project_payload()
        self.move_publication(payload, target, 1)
        contracts.seal_document("manifest", payload)

    def test_publication_cannot_replace_a_nested_project_root(self) -> None:
        payload = self.nested_project_payload()
        # Remove unrelated descendant operations so their overlap check cannot
        # hide the root-boundary defect.
        payload["projects"][1]["private_operations"] = []
        payload["projects"][1]["sources"] = []
        self.move_publication(payload, fixtures.BETA, 0)
        with self.assertRaises(ContractError):
            contracts.seal_document("manifest", payload)

    def test_recovery_scope_covers_recorded_dependents(self) -> None:
        for kind in ("recovery_plan", "recovery_receipt"):
            payload = copy.deepcopy(self.family[kind]["payload"])
            payload["projects"] = payload["projects"][:1]
            with self.subTest(kind=kind), self.assertRaises(ContractError):
                contracts.seal_document(kind, payload)
        blocked = copy.deepcopy(self.family["recovery_plan"]["payload"])
        blocked["projects"] = blocked["projects"][:1]
        blocked["status"] = "blocked"
        blocked["conflicts"] = ["shared dependency authorization is incomplete"]
        contracts.seal_document("recovery_plan", blocked)

    def test_recovery_backups_do_not_overlap_input_evidence(self) -> None:
        base = self.family["recovery_plan"]["payload"]
        backup = next(
            step["backup_ref"]
            for step in base["steps"]
            if step["backup_ref"] is not None
            and step["backup_ref"]["state"]["type"] == "directory"
        )
        source_documents = {
            kind: self.family[kind]
            for kind in (
                "apply_receipt",
                "deployment_evidence",
                "verification",
                "cleanup_receipt",
            )
        }
        for boundary, evidence_path in (
            ("equal", backup["path"]),
            ("inside backup", backup["path"] + "/manifest.json"),
            ("contains backup", str(Path(backup["path"]).parent)),
        ):
            payload = copy.deepcopy(base)
            payload["input_evidence"]["manifest"]["path"] = evidence_path
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                plan = contracts.seal_document("recovery_plan", payload)
                contracts.validate_declared_bindings(
                    self.family["manifest"],
                    {**source_documents, "recovery_plan": plan},
                    fixtures.fixture_raw_documents(self.family),
                )

    def test_recovery_protection_preserves_supplied_sources_and_reports(self) -> None:
        paths = (
            fixtures.PUBLICATION_ORIGINAL["path"],
            fixtures.operations_of("r1")["apply"]["change"]["source_ref"]["path"],
            fixtures.operations_of("r2")["apply"]["ownership"]["reference"]["path"],
            fixtures.EVIDENCE_DIR + "/restore-smoke.json",
        )
        documents = {
            kind: self.family[kind]
            for kind in (
                "apply_receipt",
                "deployment_evidence",
                "verification",
                "cleanup_receipt",
                "recovery_plan",
            )
        }
        for path in paths:
            payload = copy.deepcopy(self.family["recovery_receipt"]["payload"])
            result = next(
                entry
                for entry in payload["results"]
                if entry["resource_id"] == fixtures.resource_id_of("r1")
                and entry["phase"] == "apply"
            )
            result["protection_ref"]["path"] = path
            if path == paths[-1]:
                payload["runtime_readiness"] = "verified"
                payload["report_refs"] = [
                    {"path": path, "state": fixtures.file_state(201)}
                ]
            with self.subTest(path=path), self.assertRaises(ContractError):
                receipt = contracts.seal_document("recovery_receipt", payload)
                contracts.validate_declared_bindings(
                    self.family["manifest"],
                    {**documents, "recovery_receipt": receipt},
                )

    def test_stage_backups_preserve_all_declared_copy_sources(self) -> None:
        payload = copy.deepcopy(self.family["manifest"]["payload"])
        source_path = fixtures.BACKUP_ROOT + "/prepared/copy"
        operation = next(
            op
            for op in payload["projects"][0]["private_operations"]
            if op["resource_id"] == fixtures.resource_id_of("r1")
            and op["phase"] == "apply"
        )
        operation["change"]["source_ref"]["path"] = source_path
        manifest = contracts.seal_document("manifest", payload)
        receipt_payload = fixtures.build_apply_receipt_payload(manifest)
        contracts.validate_declared_bindings(
            manifest,
            {
                "apply_receipt": contracts.seal_document(
                    "apply_receipt", copy.deepcopy(receipt_payload)
                )
            },
        )
        for boundary, backup_path in (
            ("equal", source_path),
            ("contains source", str(Path(source_path).parent)),
        ):
            payload = copy.deepcopy(receipt_payload)
            result = next(
                entry
                for entry in payload["projects"][0]["private_results"]
                if entry["resource_id"] == fixtures.resource_id_of("r1")
            )
            result["backup_ref"]["path"] = backup_path
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.validate_declared_bindings(
                    manifest,
                    {
                        "apply_receipt": contracts.seal_document(
                            "apply_receipt", payload
                        )
                    },
                )

    def test_backup_object_cannot_be_the_vault_root(self) -> None:
        payload = copy.deepcopy(self.family["apply_receipt"]["payload"])
        first = payload["projects"][0]["private_results"][0]
        for project in payload["projects"]:
            project.update(
                status="failed",
                reason="remaining writes were not attempted",
                nextStep="inspect",
            )
            project["private_results"] = []
            project["shared_operation_ids"] = []
        payload["projects"][0]["private_results"] = [first]
        payload["shared_results"] = []
        payload["status"] = "failed"
        control = contracts.seal_document("apply_receipt", copy.deepcopy(payload))
        contracts.validate_declared_bindings(
            self.family["manifest"], {"apply_receipt": control}
        )
        first["backup_ref"]["path"] = fixtures.BACKUP_ROOT
        with self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.family["manifest"],
                {"apply_receipt": contracts.seal_document("apply_receipt", payload)},
            )


class NinthReviewRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.family = fixtures.build_fixture_family()

    def documents(self, family):
        return {
            kind: family[kind]
            for kind in (
                "apply_receipt",
                "deployment_evidence",
                "verification",
                "cleanup_receipt",
                "recovery_plan",
                "recovery_receipt",
            )
        }

    def family_with_extra_retention(self):
        family = {
            key: self.family[key]
            for key in ("manifest", "apply_receipt", "deployment_evidence")
        }
        deployment_payload = copy.deepcopy(family["deployment_evidence"]["payload"])
        deployment_payload["projects"][0]["report_refs"][0]["path"] = (
            fixtures.EVIDENCE_DIR + "/native/alpha-smoke.json"
        )
        family["deployment_evidence"] = contracts.seal_document(
            "deployment_evidence", deployment_payload
        )
        asset = {
            "path": fixtures.EVIDENCE_DIR + "/retained-extra.txt",
            "state": fixtures.file_state(201),
        }
        payload = fixtures.build_verification_payload(
            family["manifest"], family["apply_receipt"], family["deployment_evidence"]
        )
        payload["projects"][0]["retained_assets"].append(copy.deepcopy(asset))
        verification = contracts.seal_document("verification", payload)
        payload = fixtures.build_cleanup_receipt_payload(
            family["manifest"],
            family["apply_receipt"],
            family["deployment_evidence"],
            verification,
        )
        payload["projects"][0]["retained_assets"].append(copy.deepcopy(asset))
        payload["retained_assets"].append(copy.deepcopy(asset))
        cleanup = contracts.seal_document("cleanup_receipt", payload)
        plan = fixtures.build_recovery_plan(
            family["manifest"],
            family["apply_receipt"],
            family["deployment_evidence"],
            cleanup,
        )
        receipt = fixtures.build_recovery_receipt(
            family["manifest"],
            family["apply_receipt"],
            family["deployment_evidence"],
            cleanup,
            plan,
        )
        family.update(
            verification=verification,
            cleanup_receipt=cleanup,
            recovery_plan=plan,
            recovery_receipt=receipt,
        )
        return family, asset

    def test_managed_directory_cannot_contain_a_declared_scope_root(self) -> None:
        for scope in ("shared", "private"):
            payload = copy.deepcopy(self.family["manifest"]["payload"])
            operation = copy.deepcopy(fixtures.operations_of("r2")["apply"])
            operation["before_requirement"] = {
                "kind": "state",
                "state": fixtures.directory_state(90),
            }
            if scope == "shared":
                parent = "/private/home"
                payload["shared_roots"] = [
                    {
                        "kind": "home",
                        "path": parent,
                        "dependent_projects": [fixtures.ALPHA],
                    },
                    {
                        "kind": "codex-home",
                        "path": parent + "/container/nested",
                        "dependent_projects": [fixtures.BETA],
                    },
                ]
                operation["dependent_projects"] = [fixtures.ALPHA]
                destination = payload["shared_operations"]
                destination.clear()
                payload["projects"][1]["shared_operation_ids"] = []
            else:
                parent = "/private/work"
                inner = parent + "/container/nested"
                payload["projects"][0]["root"] = parent
                payload["projects"][1].update(
                    root=inner,
                    private_operations=[],
                    sources=[],
                )
                for op in payload["projects"][0]["private_operations"]:
                    op["dependent_projects"] = [parent]
                for op in payload["shared_operations"]:
                    op["dependent_projects"] = sorted([parent, inner])
                payload["shared_roots"][0]["dependent_projects"] = sorted(
                    [parent, inner]
                )
                operation["dependent_projects"] = [parent]
                destination = payload["projects"][0]["private_operations"]
            for boundary, target in (
                ("unrelated", parent + "/unrelated"),
                ("contains root", parent + "/container"),
            ):
                operation["target"] = target
                operation["resource_id"] = contracts.resource_id("directory", target)
                operation["operation_id"] = contracts.operation_id(
                    "apply",
                    operation["resource_id"],
                    "whole-resource",
                )
                destination.append(operation)
                if scope == "shared":
                    payload["projects"][0]["shared_operation_ids"] = [
                        operation["operation_id"]
                    ]
                with self.subTest(scope=scope, boundary=boundary):
                    if boundary == "unrelated":
                        contracts.seal_document("manifest", copy.deepcopy(payload))
                    else:
                        with self.assertRaises(ContractError):
                            contracts.seal_document("manifest", payload)
                destination.pop()

    def test_verified_cleanup_candidates_do_not_overlap_retained_assets(self) -> None:
        base = self.family["verification"]["payload"]
        file_candidate = base["projects"][0]["cleanup_candidates"][0]
        directory_candidate = next(
            entry
            for entry in base["projects"][0]["cleanup_candidates"]
            if entry["state"]["type"] == "directory"
        )
        for boundary, asset in (
            (
                "equal",
                {
                    "path": file_candidate["target"],
                    "state": copy.deepcopy(file_candidate["state"]),
                },
            ),
            (
                "ancestor",
                {
                    "path": str(Path(file_candidate["target"]).parent),
                    "state": fixtures.directory_state(202),
                },
            ),
            (
                "descendant",
                {
                    "path": directory_candidate["target"] + "/keep.txt",
                    "state": fixtures.file_state(203),
                },
            ),
        ):
            payload = copy.deepcopy(base)
            payload["projects"][0]["retained_assets"].append(asset)
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.seal_document("verification", payload)
            payload["status"] = "failed"
            payload["projects"][0].update(
                status="failed",
                reason="retention conflicts with cleanup",
                nextStep="resolve the conflict",
            )
            contracts.seal_document("verification", payload)

    def test_deploy_cannot_rewrite_an_approved_publication_target(self) -> None:
        payload = copy.deepcopy(self.family["manifest"]["payload"])
        alpha = payload["projects"][0]
        apply_op = fixtures.operations_of("r4")["apply"]
        resource_id = apply_op["resource_id"]
        deploy = {
            "operation_id": contracts.operation_id(
                "deploy", resource_id, "whole-resource"
            ),
            "phase": "deploy",
            "resource_id": resource_id,
            "owner_kind": "markdown",
            "target": apply_op["target"],
            "selector": "whole-resource",
            "change": {
                "kind": "copy-file",
                "source_ref": fixtures._file_ref(
                    "/private/source/deploy-candidate", 83
                ),
            },
            "ownership": {
                "kind": "template-source",
                "reference": fixtures._file_ref("/private/source/deploy-candidate", 83),
            },
            "before_requirement": {
                "kind": "phase-after",
                "phase": "apply",
                "resource_id": resource_id,
            },
            "dependent_projects": [fixtures.ALPHA],
        }
        manifest = contracts.seal_document("manifest", copy.deepcopy(payload))
        apply_receipt = fixtures.build_apply_receipt(manifest)
        contracts.validate_declared_bindings(manifest, {"apply_receipt": apply_receipt})
        alpha["private_operations"].append(deploy)
        with self.assertRaises(ContractError):
            contracts.seal_document("manifest", payload)

    def test_private_operation_cannot_claim_a_shared_root_descendant(self) -> None:
        payload = copy.deepcopy(self.family["manifest"]["payload"])
        operation = copy.deepcopy(fixtures.operations_of("r1")["apply"])
        target = fixtures.ALPHA + "/.shared/settings.json"
        payload["shared_roots"] = [
            {
                "kind": "codex-home",
                "path": str(Path(target).parent),
                "dependent_projects": list(fixtures.BOTH),
            }
        ]
        operation["target"] = target
        operation["resource_id"] = contracts.resource_id("json", target)
        operation["operation_id"] = contracts.operation_id(
            "apply", operation["resource_id"], operation["selector"]
        )
        for project in payload["projects"]:
            project["shared_operation_ids"] = []
        payload["shared_operations"] = []
        contracts.seal_document("manifest", copy.deepcopy(payload))
        payload["projects"][0]["private_operations"].append(operation)
        with self.assertRaises(ContractError):
            contracts.seal_document("manifest", payload)
        payload["shared_roots"] = []
        contracts.seal_document("manifest", payload)
        payload["shared_roots"] = [
            {
                "kind": "home",
                "path": str(Path(fixtures.ALPHA).parent),
                "dependent_projects": list(fixtures.BOTH),
            }
        ]
        contracts.seal_document("manifest", payload)

    def test_verified_candidate_type_must_match_manifest_owner(self) -> None:
        manifest = self.family["manifest"]
        contracts.validate_declared_bindings(
            manifest, {"verification": self.family["verification"]}
        )
        for key in ("r1", "r2", "s1"):
            payload = copy.deepcopy(self.family["verification"]["payload"])
            candidates = (
                payload["shared_cleanup_candidates"]
                if key == "s1"
                else payload["projects"][0]["cleanup_candidates"]
            )
            candidate = next(
                entry
                for entry in candidates
                if entry["resource_id"] == fixtures.resource_id_of(key)
            )
            candidate["state"]["type"] = "file" if key == "r2" else "directory"
            with self.subTest(resource=key), self.assertRaises(ContractError):
                verification = contracts.seal_document("verification", payload)
                contracts.validate_declared_bindings(
                    manifest, {"verification": verification}
                )
            diagnostic = copy.deepcopy(payload)
            diagnostic["status"] = "failed"
            for project in diagnostic["projects"]:
                project.update(
                    status="failed", reason="observed type drift", nextStep="inspect"
                )
            contracts.validate_declared_bindings(
                manifest,
                {"verification": contracts.seal_document("verification", diagnostic)},
            )
            candidate["state"] = dict(fixtures.ABSENT)
            contracts.validate_declared_bindings(
                manifest,
                {"verification": contracts.seal_document("verification", payload)},
            )

    def test_shared_retention_blocks_any_verified_dependent(self) -> None:
        payload = copy.deepcopy(self.family["verification"]["payload"])
        payload["status"] = "failed"
        payload["projects"][0].update(
            status="failed", reason="inspection failed", nextStep="inspect"
        )
        sources = {
            "apply_receipt": self.family["apply_receipt"],
            "deployment_evidence": self.family["deployment_evidence"],
        }
        control = contracts.seal_document("verification", copy.deepcopy(payload))
        contracts.validate_declared_bindings(
            self.family["manifest"], {**sources, "verification": control}
        )
        candidate = payload["shared_cleanup_candidates"][0]
        payload["projects"][0]["retained_assets"].append(
            {"path": candidate["target"], "state": copy.deepcopy(candidate["state"])}
        )
        with self.assertRaises(ContractError):
            verification = contracts.seal_document("verification", payload)
            contracts.validate_declared_bindings(
                self.family["manifest"], {**sources, "verification": verification}
            )
        payload["projects"][1].update(
            status="failed", reason="shared retention conflict", nextStep="resolve"
        )
        diagnostic = contracts.seal_document("verification", payload)
        contracts.validate_declared_bindings(
            self.family["manifest"], {**sources, "verification": diagnostic}
        )

    def test_temporal_comparisons_preserve_submicrosecond_precision(self) -> None:
        early = "2026-09-18T03:00:00.0000001Z"
        late = "2026-09-18T03:00:00.0000002Z"
        payload = copy.deepcopy(self.family["apply_receipt"]["payload"])
        payload.update(started_at=late, finished_at=early)
        with self.subTest(boundary="within record"), self.assertRaises(ContractError):
            contracts.seal_document("apply_receipt", payload)
        payload["started_at"] = self.family["apply_receipt"]["payload"]["started_at"]
        payload["finished_at"] = late
        applied = contracts.seal_document("apply_receipt", payload)
        deployed_payload = copy.deepcopy(self.family["deployment_evidence"]["payload"])
        deployed_payload.update(apply_id=applied["apply_id"], started_at=early)
        deployed = contracts.seal_document("deployment_evidence", deployed_payload)
        with self.subTest(boundary="phase order"), self.assertRaises(ContractError):
            contracts.validate_declared_bindings(
                self.family["manifest"],
                {"apply_receipt": applied, "deployment_evidence": deployed},
            )
        retry = copy.deepcopy(payload)
        retry.update(
            previous_receipt_id=applied["apply_id"],
            started_at=early,
            finished_at="2026-09-18T03:05:00Z",
        )
        with self.subTest(boundary="retry order"), self.assertRaises(ContractError):
            contracts.validate_cumulative(
                applied,
                contracts.seal_document("apply_receipt", retry),
                "apply_receipt",
            )
        for finish in (
            "2026-09-18T04:00:00.1+01:00",
            "2026-09-18T04:00:00.100000001+01:00",
        ):
            payload.update(
                started_at="2026-09-18T03:00:00.100000000Z",
                finished_at=finish,
            )
            contracts.seal_document("apply_receipt", payload)

    def test_all_json_entry_points_control_recursive_values(self) -> None:
        deployment = {
            "path": fixtures.EVIDENCE_DIR + "/deployment.json",
            "evidence": self.family["deployment_evidence"],
        }
        contracts.validate_deployment_result(deployment)
        deployment["recursive-value-sentinel"] = deployment
        response = {"status": "success"}
        response["recursive-value-sentinel"] = response
        stream = io.StringIO()
        for boundary, action in (
            ("deployment", lambda: contracts.validate_deployment_result(deployment)),
            ("writer", lambda: contracts.write_json_response(response, stream)),
        ):
            with self.subTest(boundary=boundary):
                with self.assertRaises(ContractError) as caught:
                    action()
                self.assertNotIn("recursive-value-sentinel", str(caught.exception))
        self.assertEqual(stream.getvalue(), "")

    def test_standalone_recovery_objects_are_spatially_separate(self) -> None:
        base = self.family["recovery_plan"]["payload"]

        def move_resource(payload, key, target):
            old_id = fixtures.resource_id_of(key)
            entry = next(x for x in payload["resources"] if x["resource_id"] == old_id)
            entry["target"] = target
            entry["resource_id"] = contracts.resource_id(entry["owner_kind"], target)
            renamed_steps = {}
            for step in payload["steps"]:
                if step["resource_id"] == old_id:
                    old_step = step["step_id"]
                    step["resource_id"] = entry["resource_id"]
                    step["step_id"] = contracts.recovery_step_id(
                        payload["manifest_id"], step["phase"], entry["resource_id"]
                    )
                    renamed_steps[old_step] = step["step_id"]
            for step in payload["steps"]:
                step["depends_on"] = [
                    renamed_steps.get(dependency, dependency)
                    for dependency in step["depends_on"]
                ]

        for boundary in (
            "targets",
            "backup in backup",
            "backup in target",
            "evidence in target",
        ):
            payload = copy.deepcopy(base)
            if boundary == "targets":
                move_resource(payload, "r2", fixtures.ALPHA + "/restore-parent")
                move_resource(payload, "r1", fixtures.ALPHA + "/restore-parent/child")
            elif boundary == "evidence in target":
                payload["input_evidence"]["manifest"]["path"] = (
                    fixtures.RESOURCES["r2"][1] + "/manifest.json"
                )
            else:
                backup = next(
                    step["backup_ref"]
                    for step in payload["steps"]
                    if step["resource_id"] == fixtures.resource_id_of("r1")
                    and step["phase"] == "apply"
                )
                if boundary == "backup in backup":
                    parent = fixtures.backup_ref_of("r2", "orig")["path"]
                else:
                    parent = fixtures.RESOURCES["r2"][1]
                backup["path"] = parent + "/original"
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                contracts.seal_document("recovery_plan", payload)

    def test_recovery_reports_do_not_replace_recovery_objects(self) -> None:
        for boundary, path in (
            ("restored target", fixtures.RESOURCES["r4"][1]),
            ("manifest input", fixtures.PUBLICATION_ORIGINAL["path"]),
            (
                "evidence",
                self.family["recovery_plan"]["payload"]["input_evidence"]["manifest"][
                    "path"
                ],
            ),
            ("backup", fixtures.backup_ref_of("r1", "orig")["path"]),
            ("backup ancestor", fixtures.BACKUP_ROOT),
        ):
            payload = copy.deepcopy(self.family["recovery_receipt"]["payload"])
            payload.update(
                runtime_readiness="verified",
                report_refs=[{"path": path, "state": fixtures.file_state(204)}],
            )
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                receipt = contracts.seal_document("recovery_receipt", payload)
                contracts.validate_declared_bindings(
                    self.family["manifest"],
                    {**self.documents(self.family), "recovery_receipt": receipt},
                )

    def test_recovery_preserves_refs_nested_in_supplied_stages(self) -> None:
        family, asset = self.family_with_extra_retention()
        contracts.validate_declared_bindings(family["manifest"], self.documents(family))
        report = family["deployment_evidence"]["payload"]["projects"][0]["report_refs"][
            0
        ]
        for source in (report, asset):
            for output_kind in ("protection", "report"):
                payload = copy.deepcopy(family["recovery_receipt"]["payload"])
                if output_kind == "protection":
                    result = next(
                        entry
                        for entry in payload["results"]
                        if entry["protection_ref"] is not None
                    )
                    result["protection_ref"]["path"] = source["path"]
                else:
                    payload.update(
                        runtime_readiness="verified",
                        report_refs=[
                            {"path": source["path"], "state": fixtures.file_state(205)}
                        ],
                    )
                with (
                    self.subTest(source=source["path"], output=output_kind),
                    self.assertRaises(ContractError),
                ):
                    receipt = contracts.seal_document("recovery_receipt", payload)
                    contracts.validate_declared_bindings(
                        family["manifest"],
                        {**self.documents(family), "recovery_receipt": receipt},
                    )

    def test_evidence_file_paths_do_not_alias_their_declared_objects(self) -> None:
        family, asset = self.family_with_extra_retention()
        report_path = family["deployment_evidence"]["payload"]["projects"][0][
            "report_refs"
        ][0]["path"]
        for source_kind, path, blocked in (
            ("manifest", fixtures.PUBLICATION_CANDIDATE["path"], False),
            ("deployment_evidence", report_path, False),
            ("deployment_evidence", str(Path(report_path).parent), False),
            ("apply_receipt", fixtures.backup_ref_of("r1", "orig")["path"], True),
            ("cleanup_receipt", asset["path"], False),
        ):
            payload = copy.deepcopy(family["recovery_plan"]["payload"])
            if blocked:
                payload.update(
                    status="blocked",
                    conflicts=["evidence conflict"],
                    steps=[],
                    shared_operation_ids=[],
                )
            payload["input_evidence"][source_kind]["path"] = path
            documents = self.documents(family)
            del documents["recovery_receipt"]
            with (
                self.subTest(source=source_kind, path=path),
                self.assertRaises(ContractError),
            ):
                plan = contracts.seal_document("recovery_plan", payload)
                contracts.validate_declared_bindings(
                    family["manifest"],
                    {**documents, "recovery_plan": plan},
                    fixtures.fixture_raw_documents(family),
                )

    def test_evidence_cannot_alias_immutable_refs_from_other_stages(self) -> None:
        documents = {
            kind: self.family[kind]
            for kind in (
                "apply_receipt",
                "deployment_evidence",
                "verification",
                "cleanup_receipt",
            )
        }
        manifest = self.family["manifest"]
        raw = fixtures.fixture_raw_documents(self.family)
        report_path = documents["deployment_evidence"]["payload"]["projects"][0][
            "report_refs"
        ][0]["path"]
        backup_path = fixtures.backup_ref_of("r1", "orig")["path"]
        for boundary, slot, path in (
            ("report", "apply_receipt", report_path),
            ("other-stage backup", "deployment_evidence", backup_path),
        ):
            payload = copy.deepcopy(self.family["recovery_plan"]["payload"])
            if boundary == "other-stage backup":
                payload.update(
                    status="blocked",
                    conflicts=["evidence conflict"],
                    steps=[],
                    shared_operation_ids=[],
                )
            control = contracts.seal_document("recovery_plan", copy.deepcopy(payload))
            contracts.validate_declared_bindings(
                manifest, {**documents, "recovery_plan": control}, raw
            )
            payload["input_evidence"][slot]["path"] = path
            with self.subTest(boundary=boundary), self.assertRaises(ContractError):
                plan = contracts.seal_document("recovery_plan", payload)
                contracts.validate_declared_bindings(
                    manifest, {**documents, "recovery_plan": plan}, raw
                )
        deployment = copy.deepcopy(self.family["deployment_evidence"]["payload"])
        deployment["projects"][0]["report_refs"][0]["path"] = backup_path
        with (
            self.subTest(boundary="backup versus report"),
            self.assertRaises(ContractError),
        ):
            contracts.validate_declared_bindings(
                manifest,
                {
                    "apply_receipt": self.family["apply_receipt"],
                    "deployment_evidence": contracts.seal_document(
                        "deployment_evidence", deployment
                    ),
                },
            )


class EleventhReviewRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.family = fixtures.build_fixture_family()

    def linked_payload(self, previous, kind):
        payload = copy.deepcopy(previous["payload"])
        id_key, previous_key = (
            ("deployment_id", "previous_deployment_id")
            if kind == "deployment_evidence"
            else ("receipt_id", "previous_receipt_id")
        )
        payload[previous_key] = previous[id_key]
        payload["started_at"] = payload["finished_at"] = previous["payload"][
            "finished_at"
        ]
        return payload

    def test_shared_operation_cannot_intrude_into_a_more_specific_project(self) -> None:
        payload = copy.deepcopy(self.family["manifest"]["payload"])
        operation = copy.deepcopy(fixtures.operations_of("s1")["apply"])
        operation["dependent_projects"] = [fixtures.BETA]
        payload["shared_operations"] = [operation]
        payload["shared_roots"] = [
            {
                "kind": "home",
                "path": str(Path(fixtures.ALPHA).parent),
                "dependent_projects": list(fixtures.BOTH),
            }
        ]
        payload["projects"][0]["shared_operation_ids"] = []
        for boundary, target in (
            ("shared control", "/private/work/shared/settings.toml"),
            ("project intrusion", fixtures.ALPHA + "/.config/settings.toml"),
        ):
            operation["target"] = target
            operation["resource_id"] = contracts.resource_id("toml", target)
            operation["operation_id"] = contracts.operation_id(
                "apply", operation["resource_id"], operation["selector"]
            )
            payload["projects"][1]["shared_operation_ids"] = [operation["operation_id"]]
            with self.subTest(boundary=boundary):
                if boundary == "shared control":
                    contracts.seal_document("manifest", copy.deepcopy(payload))
                else:
                    with self.assertRaises(ContractError):
                        contracts.seal_document("manifest", payload)
        payload["shared_roots"][0]["path"] = fixtures.ALPHA + "/.config"
        contracts.seal_document("manifest", payload)

    def test_retry_reports_preserve_the_previous_file_snapshots(self) -> None:
        old_report = {
            "path": fixtures.BACKUP_ROOT + "/prior-report.json",
            "state": fixtures.file_state(211),
        }
        for kind in ("deployment_evidence", "recovery_receipt"):
            previous_payload = copy.deepcopy(self.family[kind]["payload"])
            if kind == "deployment_evidence":
                previous_payload["projects"][0]["report_refs"] = [
                    copy.deepcopy(old_report)
                ]
            else:
                previous_payload["report_refs"] = [copy.deepcopy(old_report)]
            previous = contracts.seal_document(kind, previous_payload)
            control = contracts.seal_document(kind, self.linked_payload(previous, kind))
            contracts.validate_cumulative(previous, control, kind)
            for boundary, path, state in (
                ("changed", old_report["path"], fixtures.file_state(212)),
                (
                    "ancestor",
                    str(Path(old_report["path"]).parent),
                    fixtures.file_state(213),
                ),
                (
                    "descendant",
                    old_report["path"] + "/details.json",
                    fixtures.file_state(214),
                ),
                (
                    "fresh disjoint",
                    fixtures.EVIDENCE_DIR + "/new-report.json",
                    fixtures.file_state(215),
                ),
            ):
                payload = self.linked_payload(previous, kind)
                holder = (
                    payload["projects"][0] if kind == "deployment_evidence" else payload
                )
                holder["report_refs"] = [{"path": path, "state": state}]
                current = contracts.seal_document(kind, payload)
                with self.subTest(kind=kind, boundary=boundary):
                    if boundary == "fresh disjoint":
                        contracts.validate_cumulative(previous, current, kind)
                    else:
                        with self.assertRaises(ContractError):
                            contracts.validate_cumulative(previous, current, kind)

    def test_new_retry_original_refs_cannot_repurpose_previous_reports(self) -> None:
        old_report = {
            "path": fixtures.BACKUP_ROOT + "/prior-report.json",
            "state": fixtures.file_state(211),
        }
        for kind in ("deployment_evidence", "recovery_receipt"):
            previous_payload = copy.deepcopy(self.family[kind]["payload"])
            previous_payload["status"] = "failed"
            if kind == "deployment_evidence":
                previous_payload["projects"][0]["report_refs"] = [
                    copy.deepcopy(old_report)
                ]
                previous_payload["projects"][1].update(
                    status="failed",
                    reason="resource not attempted",
                    nextStep="retry",
                    private_results=[],
                )
            else:
                leaf = next(
                    result
                    for result in previous_payload["results"]
                    if result["resource_id"] == fixtures.resource_id_of("r1")
                    and result["phase"] == "apply"
                )
                previous_payload["results"].remove(leaf)
                previous_payload["completed_step_ids"].remove(leaf["step_id"])
                previous_payload["pending_step_ids"].append(leaf["step_id"])
                previous_payload["projects"][0].update(
                    status="failed",
                    reason="restore not attempted",
                    nextStep="retry",
                )
                previous_payload["reason"] = "restore not attempted"
                previous_payload["report_refs"] = [copy.deepcopy(old_report)]
            previous = contracts.seal_document(kind, previous_payload)
            payload = copy.deepcopy(self.family[kind]["payload"])
            if kind == "deployment_evidence":
                payload["previous_deployment_id"] = previous["deployment_id"]
                holder = payload["projects"][0]
                new_original = payload["projects"][1]["private_results"][0][
                    "backup_ref"
                ]
            else:
                payload["previous_receipt_id"] = previous["receipt_id"]
                holder = payload
                new_original = next(
                    result["protection_ref"]
                    for result in payload["results"]
                    if result["resource_id"] == fixtures.resource_id_of("r1")
                    and result["phase"] == "apply"
                )
            payload["started_at"] = payload["finished_at"] = previous_payload[
                "finished_at"
            ]
            holder["report_refs"] = [
                {
                    "path": fixtures.EVIDENCE_DIR + "/fresh-retry.json",
                    "state": fixtures.file_state(216),
                }
            ]
            control = contracts.seal_document(kind, copy.deepcopy(payload))
            contracts.validate_cumulative(previous, control, kind)
            new_original["path"] = old_report["path"]
            current = contracts.seal_document(kind, payload)
            with self.subTest(kind=kind), self.assertRaises(ContractError):
                contracts.validate_cumulative(previous, current, kind)


if __name__ == "__main__":
    unittest.main()
