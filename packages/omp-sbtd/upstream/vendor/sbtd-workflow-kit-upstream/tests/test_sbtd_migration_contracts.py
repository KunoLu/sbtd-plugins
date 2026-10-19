from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from tests import onboard_contract_fixtures as fixtures
from tests.onboard_contract_fixtures import build_manifest_payload, contracts


class MigrationIdentityContractTests(unittest.TestCase):
    def test_legacy_name_extraction_is_an_explicit_private_apply_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            source = {
                "path": str(root / ".trellis/.developer"),
                "state": {
                    "type": "file",
                    "checksum": hashlib.sha256(
                        b"name=dev01\ninitialized_at=2026-09-01T12:00:00\n"
                    ).hexdigest(),
                },
            }
            target = str(root / ".sbtd/developer")
            resource = contracts.resource_id("file", target)
            operation = {
                "operation_id": contracts.operation_id("apply", resource, "name"),
                "phase": "apply",
                "resource_id": resource,
                "owner_kind": "file",
                "target": target,
                "selector": "name",
                "change": {
                    "kind": "migrate-developer",
                    "source_ref": source,
                    "name": "dev01",
                },
                "ownership": {
                    "kind": "config-entry",
                    "reference": source,
                    "key_path": ["name"],
                },
                "before_requirement": {
                    "kind": "state",
                    "state": {"type": "absent", "checksum": None},
                },
                "dependent_projects": [str(root)],
            }
            payload = {
                "projects": [
                    {
                        "root": str(root),
                        "source_ref": None,
                        "head": None,
                        "platforms": ["codex"],
                        "sources": [source],
                        "private_operations": [operation],
                        "shared_operation_ids": [],
                    }
                ],
                "shared_roots": [],
                "shared_operations": [],
                "publication_decisions": {"schema_version": 1, "items": []},
                "routing_approvals": None,
                "custodian": "fixture",
                "backup_root": str(base / "vault"),
                "created_at": "2026-09-19T00:00:00Z",
                "retention": copy.deepcopy(build_manifest_payload()["retention"]),
                "tool_versions": {"onboard": "fixture", "graft": "0.18.0"},
                "deployment": None,
            }
            sealed = contracts.seal_document("manifest", payload)
            self.assertEqual(
                contracts.load_document(
                    contracts.canonical_json_bytes(sealed), "manifest"
                ),
                sealed,
            )


class MigrationRetainedContractTests(unittest.TestCase):
    def test_only_proven_absent_unpublished_resources_may_omit_retention(self):
        family = fixtures.build_fixture_family()
        target = fixtures.ALPHA + "/.codex/agents/trellis-implement.toml"
        resource = contracts.resource_id("file", target)
        operation_id = contracts.operation_id("apply", resource, "whole-resource")
        state = fixtures.file_state(42)
        operation = {
            "operation_id": operation_id,
            "phase": "apply",
            "resource_id": resource,
            "owner_kind": "file",
            "target": target,
            "selector": "whole-resource",
            "change": {"kind": "remove"},
            "ownership": {
                "kind": "template-source",
                "reference": {"path": target, "state": state},
            },
            "before_requirement": {"kind": "state", "state": state},
            "dependent_projects": [fixtures.ALPHA],
        }
        payload = copy.deepcopy(family["manifest"]["payload"])
        payload["projects"][0]["private_operations"].append(operation)
        manifest = contracts.seal_document("manifest", payload)

        def evidence(after):
            payload = copy.deepcopy(family["apply_receipt"]["payload"])
            payload["manifest_id"] = manifest["manifest_id"]
            payload["projects"][0]["private_results"].append(
                {
                    "phase": "apply",
                    "resource_id": resource,
                    "operation_ids": [operation_id],
                    "dependent_projects": [fixtures.ALPHA],
                    "status": "succeeded",
                    "backup_ref": {
                        "path": fixtures.BACKUP_ROOT + "/retired-route",
                        "state": state,
                    },
                    "before": state,
                    "after": after,
                    "error": None,
                }
            )
            applied = contracts.seal_document("apply_receipt", payload)
            payload = copy.deepcopy(family["deployment_evidence"]["payload"])
            payload.update(
                manifest_id=manifest["manifest_id"], apply_id=applied["apply_id"]
            )
            deployed = contracts.seal_document("deployment_evidence", payload)
            payload = copy.deepcopy(family["verification"]["payload"])
            payload.update(
                manifest_id=manifest["manifest_id"],
                apply_id=applied["apply_id"],
                deployment_evidence_hash=hashlib.sha256(
                    contracts.canonical_json_bytes(deployed)
                ).hexdigest(),
            )
            return {
                "apply_receipt": applied,
                "deployment_evidence": deployed,
                "verification": contracts.seal_document("verification", payload),
            }

        contracts.validate_declared_bindings(manifest, evidence(fixtures.ABSENT))
        with self.assertRaises(contracts.ContractError):
            contracts.validate_declared_bindings(manifest, evidence(state))


if __name__ == "__main__":
    unittest.main()
