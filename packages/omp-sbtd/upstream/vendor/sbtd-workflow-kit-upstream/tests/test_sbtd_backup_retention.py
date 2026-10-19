from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from onboard_contracts import ContractError
from sbtd_backup_retention import (
    DESTRUCTION_AUTHORIZATION_FIELD,
    REQUIRED_DESTRUCTION_AUTHORIZATION_FIELDS,
    record_destruction_authorization,
    validate_destruction_authorization,
)


class DestructionAuthorizationTests(unittest.TestCase):
    def record(self) -> dict[str, str]:
        return {
            "custodian": "fixture-custodian",
            "candidate_ownership": "private publication candidates 1-3",
            "exact_scope": "vault/backups/manifest-123/*",
            "authorization": "independent destruction approval 2026-09-20T21:00:00Z",
            "confirmed_at": "2026-09-20T21:00:01Z",
        }

    def prepare(self, base: Path) -> tuple[Path, Path, Path]:
        private = base / "private"
        private.mkdir(mode=0o700)
        backup = private / "backup.json"
        backup.write_text("original backup\n")
        report = private / "migration-report.json"
        report.write_text(json.dumps({"existing": "migration report"}) + "\n")
        return private, backup, report

    def test_every_missing_authorization_field_blocks_without_changing_records(self):
        with tempfile.TemporaryDirectory() as directory:
            private, backup, report = self.prepare(Path(directory).resolve())
            report_before = report.read_bytes()
            for field in REQUIRED_DESTRUCTION_AUTHORIZATION_FIELDS:
                with self.subTest(field=field):
                    record = self.record()
                    record[field] = ""
                    with self.assertRaises(ContractError) as raised:
                        validate_destruction_authorization(record)
                    self.assertEqual(raised.exception.exit_code, 2)
                    with self.assertRaises(ContractError):
                        record_destruction_authorization(
                            report, record, private_root=private
                        )
                    self.assertEqual(backup.read_bytes(), b"original backup\n")
                    self.assertEqual(report.read_bytes(), report_before)

    def test_invalid_confirmation_time_blocks_without_changing_records(self):
        with tempfile.TemporaryDirectory() as directory:
            private, backup, report = self.prepare(Path(directory).resolve())
            report_before = report.read_bytes()
            record = self.record()
            record["confirmed_at"] = "not-a-time"
            with self.assertRaises(ContractError) as raised:
                record_destruction_authorization(report, record, private_root=private)
            self.assertEqual(raised.exception.exit_code, 2)
            self.assertEqual(backup.read_bytes(), b"original backup\n")
            self.assertEqual(report.read_bytes(), report_before)

    def test_missing_existing_record_is_blocked_and_never_created(self):
        with tempfile.TemporaryDirectory() as directory:
            private, backup, _ = self.prepare(Path(directory).resolve())
            missing = private / "new-authorization.json"
            with self.assertRaises(ContractError) as raised:
                record_destruction_authorization(
                    missing, self.record(), private_root=private
                )
            self.assertEqual(raised.exception.exit_code, 2)
            self.assertFalse(missing.exists())
            self.assertEqual(backup.read_bytes(), b"original backup\n")

    def test_closed_publication_decisions_cannot_gain_new_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            private, backup, _ = self.prepare(Path(directory).resolve())
            decisions = private / "publication-decisions.json"
            decisions.write_text(json.dumps({"schema_version": 1, "items": []}) + "\n")
            before = decisions.read_bytes()
            with self.assertRaises(ContractError) as raised:
                record_destruction_authorization(
                    decisions, self.record(), private_root=private
                )
            self.assertEqual(raised.exception.exit_code, 2)
            self.assertEqual(decisions.read_bytes(), before)
            self.assertEqual(backup.read_bytes(), b"original backup\n")

    def test_update_and_reread_success_preserves_the_existing_report_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            private, backup, report = self.prepare(Path(directory).resolve())
            record = self.record()
            saved = record_destruction_authorization(report, record, private_root=private)
            updated = json.loads(report.read_text())
            self.assertEqual(updated["existing"], "migration report")
            self.assertEqual(updated[DESTRUCTION_AUTHORIZATION_FIELD], record)
            self.assertEqual(saved["authorization"], record)
            self.assertEqual(backup.read_bytes(), b"original backup\n")

    def test_write_failure_blocks_without_changing_the_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            private, backup, report = self.prepare(Path(directory).resolve())
            report_before = report.read_bytes()
            with mock.patch(
                "sbtd_backup_retention.write_file",
                side_effect=ContractError(
                    "write-failed", "cannot update authorization record", exit_code=5
                ),
            ):
                with self.assertRaises(ContractError) as raised:
                    record_destruction_authorization(
                        report, self.record(), private_root=private
                    )
            self.assertEqual(raised.exception.exit_code, 5)
            self.assertEqual(report.read_bytes(), report_before)
            self.assertEqual(backup.read_bytes(), b"original backup\n")

    def test_readback_mismatch_blocks_and_does_not_claim_done(self):
        with tempfile.TemporaryDirectory() as directory:
            private, backup, report = self.prepare(Path(directory).resolve())
            original_reads = []

            def tampered_read(path, expected=None):
                current = Path(path).read_bytes()
                original_reads.append(current)
                if len(original_reads) == 1:
                    return current
                return b'{"tampered": true}'

            with mock.patch("sbtd_backup_retention.read_file", side_effect=tampered_read):
                with self.assertRaises(ContractError) as raised:
                    record_destruction_authorization(
                        report, self.record(), private_root=private
                    )
            self.assertEqual(raised.exception.exit_code, 3)
            self.assertEqual(backup.read_bytes(), b"original backup\n")
            self.assertNotEqual(json.loads(report.read_text()), {"tampered": True})


if __name__ == "__main__":
    unittest.main()
