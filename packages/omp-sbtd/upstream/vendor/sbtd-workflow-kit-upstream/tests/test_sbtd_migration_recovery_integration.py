from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard" / "scripts"
TESTS = Path(__file__).resolve().parent
for import_path in (str(SCRIPTS), str(TESTS)):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from onboard_contracts import ContractError
from sbtd_migration_files import save_document
from sbtd_recovery import apply_recovery, plan_recovery
from test_sbtd_migration_cleanup import VerifiedMigration
from test_sbtd_migration_verify import _tree_bytes


class ProducerCleanupRecoveryIntegrationTests(unittest.TestCase):
    def build(self, base: Path) -> VerifiedMigration:
        fixture = VerifiedMigration(base)
        fixture.build()
        return fixture

    def test_full_producer_verify_cleanup_recovery_chain_retains_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            vault_before = _tree_bytes(fixture.vault)
            evidence_before = _tree_bytes(fixture.evidence)

            cleaned, cleanup_code = fixture.cleanup(
                confirm_cleanup=fixture.verification["verification_id"]
            )
            self.assertEqual(cleanup_code, 0, cleaned)
            self.assertFalse((fixture.root / ".trellis").exists())
            cleanup_receipt = cleaned["migration"]["cleanup_receipt"]
            cleanup_result = cleanup_receipt["payload"]["projects"][0]["private_results"][0]
            backup_ref = cleanup_result["backup_ref"]
            self.assertIsNotNone(backup_ref)
            self.assertTrue(Path(backup_ref["path"]).exists())
            after_cleanup = _tree_bytes(fixture.vault)
            self.assertEqual(
                {path: after_cleanup[path] for path in vault_before},
                vault_before,
                "cleanup must retain every original backup",
            )

            planned, plan_code = plan_recovery(
                fixture.manifest_path,
                apply_receipt_path=fixture.apply_path,
                deployment_evidence_path=fixture.deployment_path,
                cleanup_receipt_path=(
                    fixture.evidence / f"cleanup-{cleanup_receipt['cleanup_id']}.json"
                ),
            )
            self.assertEqual(plan_code, 0, planned)
            plan = planned["recovery"]["plan"]
            plan_path = fixture.evidence / "recovery-plan.json"
            save_document(
                plan_path,
                plan,
                private_root=fixture.evidence,
            )
            restored, recovery_code = apply_recovery(
                plan_path,
                confirm_recovery=plan["plan_id"],
            )
            self.assertEqual(recovery_code, 0, restored)
            self.assertEqual(restored["status"], "restored")
            self.assertTrue((fixture.root / ".trellis/.developer").is_file())
            recovery_receipt = restored["recovery"]["receipt"]
            self.assertEqual(recovery_receipt["payload"]["plan_id"], plan["plan_id"])
            after_recovery = _tree_bytes(fixture.vault)
            self.assertEqual(
                {path: after_recovery[path] for path in vault_before},
                vault_before,
                "recovery success must not delete original backups",
            )
            self.assertTrue(
                (fixture.evidence / f"cleanup-{cleanup_receipt['cleanup_id']}.json").is_file()
            )
            self.assertTrue(
                (
                    fixture.evidence / f"recovery-{recovery_receipt['receipt_id']}.json"
                ).is_file()
            )
            self.assertNotEqual(_tree_bytes(fixture.evidence), evidence_before)

    def test_partial_continuation_and_missing_evidence_refuse_without_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.build(Path(directory).resolve())
            vault_before = _tree_bytes(fixture.vault)
            refusal = ContractError(
                "state-conflict", "injected cleanup refusal", exit_code=2
            )

            def refuse_vendor(*_args):
                raise refusal

            failed, failed_code = fixture.cleanup(
                vendor_execute=refuse_vendor,
                confirm_cleanup=fixture.verification["verification_id"],
            )
            self.assertEqual(failed_code, 5, failed)
            self.assertTrue((fixture.root / ".trellis").is_dir())
            self.assertEqual(_tree_bytes(fixture.vault), vault_before)
            failed_receipt = failed["migration"]["cleanup_receipt"]
            failed_path = fixture.evidence / f"cleanup-{failed_receipt['cleanup_id']}.json"
            self.assertTrue(failed_path.is_file())

            resumed, resumed_code = fixture.cleanup(
                previous_receipt_path=failed_path,
                confirm_cleanup=fixture.verification["verification_id"],
            )
            self.assertEqual(resumed_code, 0, resumed)
            self.assertFalse((fixture.root / ".trellis").exists())
            after_resume = _tree_bytes(fixture.vault)
            self.assertEqual(
                {path: after_resume[path] for path in vault_before},
                vault_before,
            )
            cleanup_receipt = resumed["migration"]["cleanup_receipt"]
            cleanup_path = fixture.evidence / f"cleanup-{cleanup_receipt['cleanup_id']}.json"

            evidence_before = _tree_bytes(fixture.evidence)
            blocked, blocked_code = plan_recovery(
                fixture.manifest_path,
                apply_receipt_path=fixture.apply_path,
                deployment_evidence_path=fixture.deployment_path,
                cleanup_receipt_path=None,
            )
            self.assertEqual(blocked_code, 2, blocked)
            self.assertEqual(blocked["recovery"]["plan"]["payload"]["status"], "blocked")
            self.assertEqual(
                _tree_bytes(fixture.evidence),
                evidence_before,
                "evidence-insufficient recovery planning must be read-only",
            )
            self.assertFalse((fixture.root / ".trellis").exists())
            self.assertEqual(
                list(fixture.evidence.glob("recovery-*.json")),
                [],
                "blocked recovery must not create a receipt or claim done",
            )

            planned, plan_code = plan_recovery(
                fixture.manifest_path,
                apply_receipt_path=fixture.apply_path,
                deployment_evidence_path=fixture.deployment_path,
                cleanup_receipt_path=cleanup_path,
            )
            self.assertEqual(plan_code, 0, planned)
            plan = planned["recovery"]["plan"]
            plan_path = fixture.evidence / "recovery-plan.json"
            save_document(
                plan_path,
                plan,
                private_root=fixture.evidence,
            )
            restored, recovery_code = apply_recovery(
                plan_path,
                confirm_recovery=plan["plan_id"],
            )
            self.assertEqual(recovery_code, 0, restored)
            self.assertTrue((fixture.root / ".trellis").is_dir())
            after_recovery = _tree_bytes(fixture.vault)
            self.assertEqual(
                {path: after_recovery[path] for path in vault_before},
                vault_before,
            )


if __name__ == "__main__":
    unittest.main()
