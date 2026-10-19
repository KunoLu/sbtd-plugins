"""Backup-retention authorization record helpers.

This module only validates and records the pre-destruction authorization
required before any manual backup destruction. It updates an existing private
preparation record or migration report in place and proves the reread. It does
not delete backups, create a new disposal record, register a CLI, or replace
the custodian's manual P3-04 procedure.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any, Mapping

from onboard_contracts import ContractError, _parse_timestamp, canonical_json_bytes
from sbtd_migration_files import (
    read_file,
    require_private_directory,
    snapshot,
    write_file,
)

__all__ = [
    "DESTRUCTION_AUTHORIZATION_FIELD",
    "REQUIRED_DESTRUCTION_AUTHORIZATION_FIELDS",
    "record_destruction_authorization",
    "validate_destruction_authorization",
]

DESTRUCTION_AUTHORIZATION_FIELD = "backup_destruction_authorization"
REQUIRED_DESTRUCTION_AUTHORIZATION_FIELDS = (
    "custodian",
    "candidate_ownership",
    "exact_scope",
    "authorization",
    "confirmed_at",
)
_PUBLICATION_DECISIONS_KEYS = {"schema_version", "items"}


def _fail(code: str, message: str, *, exit_code: int = 2) -> None:
    raise ContractError(code, message, exit_code=exit_code)


def validate_destruction_authorization(record: Mapping[str, Any]) -> None:
    """Require the five pre-destruction authorization facts to be present."""
    if not isinstance(record, Mapping):
        _fail("unexpected-type", "destruction authorization must be a mapping")
    missing = [
        name
        for name in REQUIRED_DESTRUCTION_AUTHORIZATION_FIELDS
        if not isinstance(record.get(name), str) or not record[name].strip()
    ]
    if missing:
        _fail(
            "confirmation-required",
            "destruction authorization is missing: " + ", ".join(missing),
        )
    try:
        _parse_timestamp(record["confirmed_at"])
    except (TypeError, ValueError):
        _fail("confirmation-required", "confirmed_at must be a real timestamp")


def _existing_private_record(path: Path, private_root: Path) -> tuple[Path, dict[str, Any]]:
    private = require_private_directory(private_root)
    candidate = path if path.is_absolute() else private / path
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        _fail("state-conflict", "authorization record must already exist")
    if not resolved.is_relative_to(private):
        _fail("state-conflict", "authorization record escapes the private root")
    try:
        metadata = resolved.lstat()
    except OSError:
        _fail("state-conflict", "authorization record cannot be inspected")
    if not stat.S_ISREG(metadata.st_mode):
        _fail("state-conflict", "authorization record must be a regular file")
    before = snapshot(resolved)
    try:
        current = json.loads(read_file(resolved, before).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("schema-violation", "authorization record must remain JSON")
    if not isinstance(current, dict):
        _fail("schema-violation", "authorization record must remain a JSON object")
    if _PUBLICATION_DECISIONS_KEYS <= set(current) and DESTRUCTION_AUTHORIZATION_FIELD not in current:
        _fail(
            "schema-violation",
            "closed publication-decisions records cannot gain new fields",
        )
    return resolved, {"before": before, "current": current}


def record_destruction_authorization(
    path: Path, record: Mapping[str, Any], *, private_root: Path
) -> dict[str, Any]:
    """Update an existing private record and reread it; never delete anything."""
    validate_destruction_authorization(record)
    resolved, state = _existing_private_record(path, private_root)
    updated = dict(state["current"])
    updated[DESTRUCTION_AUTHORIZATION_FIELD] = dict(record)
    payload = canonical_json_bytes(updated)
    write_file(resolved, payload, state["before"], scope=require_private_directory(private_root))
    readback_state = snapshot(resolved)
    try:
        readback = json.loads(read_file(resolved, readback_state).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail(
            "preservation-failed",
            "authorization record could not be reread after the update",
            exit_code=3,
        )
    if readback != updated:
        _fail(
            "preservation-failed",
            "authorization record readback does not match the update",
            exit_code=3,
        )
    return {
        "path": str(resolved),
        "state": readback_state,
        "authorization": readback[DESTRUCTION_AUTHORIZATION_FIELD],
    }
