from __future__ import annotations

import base64
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "sbtd-workflow-onboard"
for entry in (PACKAGE / "scripts", ROOT / "tests"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import onboard
import sbtd_migration as migration
from onboard_arguments import parse_workflow_args
from onboard_contracts import ContractError, canonical_json_bytes, seal_document
from sbtd_migration_files import require_private_directory, snapshot
from sbtd_migration_verify import verify_migration
from sbtd_upgrade import apply_upgrade, plan_upgrade
from sbtd_upgrade_inventory import build_inventory
from test_sbtd_migration_cleanup import (
    VerifiedMigration,
    _fake_execute_trellis_uninstall,
    _fake_vendor_adapter,
)


class CleanupUpgradeIntegrationTests(unittest.TestCase):
    def _run_transition(self, *, reconciled: bool, late_drift: str | None = None) -> None:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        with tempfile.TemporaryDirectory(prefix="cleanup-upgrade-integration-") as raw:
            base = Path(raw).resolve()
            skills = base / "skills"
            skills.mkdir()
            installed = skills / "sbtd-workflow-onboard"
            shutil.copytree(
                PACKAGE, installed,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
            )
            # A genuinely different previous package, not a mocked version result.
            source = installed / "scripts" / "sbtd_graft_entry.py"
            source.write_bytes(source.read_bytes() + b"\n# previous installation\n")
            key = Ed25519PrivateKey.generate()
            public = installed / "assets" / "runtime-lineage.pub"
            public.write_bytes(key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
            pair = installed / "assets" / "runtime-lineage.json"
            fixture = VerifiedMigration(base)
            upgrade_vault = base / "upgrade-vault"
            require_private_directory(upgrade_vault, create=True)
            with (
                mock.patch.dict(os.environ, fixture.environment),
                mock.patch.object(migration, "_PACKAGE", installed),
                mock.patch.object(migration, "_LINEAGE_PUBLIC_KEY", public),
                mock.patch.object(migration, "_LINEAGE_DOCUMENT", pair),
                mock.patch.object(onboard, "PROJECT_AGENTS_TEMPLATE", installed / "templates/agents/AGENTS.project.md"),
                _fake_vendor_adapter(),
            ):
                fixture.build()
                if reconciled:
                    predecessor = fixture.manifest["payload"]["tool_versions"]["onboard"]
                    source.write_bytes(source.read_bytes() + b"\n# accepted observer successor\n")
                    observer_versions = migration.runtime_versions()
                    successor = observer_versions["onboard"]
                    proof = {
                        "schema_version": 1, "purpose": "runtime-lineage",
                        "predecessor": predecessor, "successor": successor,
                        "signature": base64.b64encode(key.sign(
                            migration._lineage_signed_bytes(predecessor, successor)
                        )).decode(),
                    }
                    pair.write_bytes(canonical_json_bytes(proof))
                    deployment = json.loads(fixture.deployment_path.read_bytes())
                    deployment["payload"]["reconciliation"] = {
                        "kind": "current-state", "historical_execution": "unknown",
                        "manifest_ref": {"path": str(fixture.manifest_path), "state": snapshot(fixture.manifest_path)},
                        "apply_receipt_ref": {"path": str(fixture.apply_path), "state": snapshot(fixture.apply_path)},
                        "missing_deployment_evidence": {"path": str(fixture.evidence / "missing-deployment.json"), "state": {"type": "absent", "checksum": None}},
                        "runtime_versions": observer_versions,
                        "observer_lineage": proof,
                    }
                    deployment = seal_document("deployment_evidence", deployment["payload"])
                    fixture.deployment_path.write_bytes(canonical_json_bytes(deployment))
                    verified, code = verify_migration(
                        fixture.manifest_path, fixture.apply_path, fixture.deployment_path
                    )
                    self.assertEqual(code, 0, verified)
                    fixture.verification = verified["migration"]["verification"]
                    fixture.verification_path.write_bytes(canonical_json_bytes(fixture.verification))

                scope = {
                    "schema_version": 1, "skills_roots": [str(skills)],
                    "agents_targets": [], "hosts": [], "shell_profiles": [],
                    "decisions": {str(installed): "replace"},
                }
                inventory = build_inventory(scope, package_root=PACKAGE)
                for resource in inventory["resources"]:
                    if resource["classification"] == "missing":
                        shutil.copytree(resource["source"]["path"], resource["target"])
                plan = plan_upgrade(scope, upgrade_vault, package_root=PACKAGE)
                receipt = apply_upgrade(plan, confirmed=plan["plan_id"])
                self.assertEqual(receipt["payload"]["status"], "complete")
                plan_path = upgrade_vault / f"upgrade-plan-{plan['plan_id']}.json"
                receipt_path = upgrade_vault / f"upgrade-receipt-{receipt['receipt_id']}.json"
                before = snapshot(fixture.root / ".trellis")
                arguments = (fixture.manifest_path, fixture.apply_path, fixture.deployment_path, fixture.verification_path)
                confirmation = fixture.verification["verification_id"]
                with self.assertRaises(ContractError):
                    migration.cleanup_migration(*arguments, confirm_cleanup=confirmation)
                self.assertEqual(snapshot(fixture.root / ".trellis"), before)

                if late_drift is not None:
                    if late_drift == "alias":
                        probe = base / "symlink-probe"
                        try:
                            probe.symlink_to(plan_path)
                        except (OSError, NotImplementedError):
                            self.skipTest("symlink creation unavailable")
                        probe.unlink()

                    def remove_then_drift(root, prepared, backup_root):
                        outcome = _fake_execute_trellis_uninstall(root, prepared, backup_root)
                        if late_drift == "alias":
                            plan_path.unlink()
                            plan_path.symlink_to(receipt_path)
                        else:
                            asset = next(
                                item for item in fixture.verification["payload"]["projects"][0]["retained_assets"]
                                if item["state"]["type"] == "file"
                            )
                            path = Path(asset["path"])
                            path.write_bytes(path.read_bytes() + b"\n# concurrent edit\n")
                        return outcome

                    with _fake_vendor_adapter(execute=remove_then_drift):
                        failed, code = migration.cleanup_migration(
                            *arguments, confirm_cleanup=confirmation,
                            upgrade_plan_path=plan_path, upgrade_receipt_path=receipt_path,
                        )
                    self.assertEqual(code, 2, failed)
                    self.assertFalse((fixture.root / ".trellis").exists())
                    recorded = failed["migration"]["cleanup_receipt"]
                    self.assertEqual(recorded["payload"]["status"], "blocked")
                    outcomes = recorded["payload"]["projects"][0]["private_results"]
                    self.assertEqual(outcomes[0]["status"], "succeeded")
                    self.assertEqual(outcomes[0]["after"]["type"], "absent")
                    self.assertTrue((fixture.evidence / f"cleanup-{recorded['cleanup_id']}.json").is_file())
                    return

                args = parse_workflow_args([
                    "migration", "--phase", "cleanup",
                    "--manifest", str(fixture.manifest_path),
                    "--apply-receipt", str(fixture.apply_path),
                    "--deployment-evidence", str(fixture.deployment_path),
                    "--verification", str(fixture.verification_path),
                    "--confirm-cleanup", confirmation,
                    "--upgrade-plan", str(plan_path),
                    "--upgrade-receipt", str(receipt_path),
                    "--json",
                ])
                output = io.StringIO()
                with redirect_stdout(output):
                    code = migration.run_migration(args)
                result = json.loads(output.getvalue())
                self.assertEqual(code, 0, result)
                self.assertFalse((fixture.root / ".trellis").exists())
                cleanup = result["migration"]["cleanup_receipt"]
                self.assertIn("upgrade_context", cleanup["payload"])
                previous_path = fixture.evidence / f"cleanup-{cleanup['cleanup_id']}.json"
                self.assertTrue(previous_path.is_file())
                # A retry cannot silently drop the trust source it used before.
                with self.assertRaises(ContractError):
                    migration.cleanup_migration(
                        *arguments, confirm_cleanup=confirmation,
                        previous_receipt_path=previous_path,
                    )
                retried, retry_code = migration.cleanup_migration(
                    *arguments, confirm_cleanup=confirmation,
                    previous_receipt_path=previous_path,
                    upgrade_plan_path=plan_path, upgrade_receipt_path=receipt_path,
                )
                self.assertEqual(retry_code, 0, retried)
                self.assertEqual(retried["status"], "already-complete")

    def test_completed_batch_exits_through_native_upgrade_without_new_signature(self) -> None:
        self._run_transition(reconciled=False)

    def test_reconciled_observer_uses_bound_previous_key_after_native_upgrade(self) -> None:
        self._run_transition(reconciled=True)

    def test_late_upgrade_alias_drift_preserves_measured_cleanup_receipt(self) -> None:
        self._run_transition(reconciled=False, late_drift="alias")

    def test_late_retained_asset_drift_cannot_publish_success(self) -> None:
        self._run_transition(reconciled=False, late_drift="retained")


if __name__ == "__main__":
    unittest.main()
