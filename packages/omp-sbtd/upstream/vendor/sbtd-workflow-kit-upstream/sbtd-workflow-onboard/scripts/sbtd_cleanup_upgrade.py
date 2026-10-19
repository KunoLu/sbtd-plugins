"""Cleanup-time trust continuation from one native Onboard self-upgrade hop.

Internal adapter for the legacy migration cleanup path. When an explicitly
approved native Onboard upgrade replaced exactly the canonical installed
Onboard package, its sealed plan and complete receipt prove which package
ran before the hop. ``validate_cleanup_upgrade`` re-proves that hop against
live filesystem state and returns an immutable :class:`CleanupUpgradeContext`
pinning every evidence reference, so the caller can bind cleanup receipts to
the upgrade provenance and re-check the same pins immediately before its
first mutation and again before receipt publication.

Trust model, matching the upgrade engine:

- The private backup vault is operator-controlled trusted history, not an
  unforgeable journal. Every document is digest-bound (``plan_id`` and
  ``receipt_id`` are SHA-256 over the canonical payload), the vault must
  still prove private, and every recorded state is re-measured live.
- This module never imports, executes or shells out to the historical
  package. The previous package is only hashed (semantic payload digest and
  mechanical snapshot); no public key, interpreter or dependency trust is
  derived here — the consumer owns the historical pairing/observer checks
  and the frozen runtime fingerprint inputs.
- There is no trust-key or bypass input: the only authority accepted is one
  complete, direct, native replacement of the canonical package, evidenced
  end to end.

A hop qualifies only when all of the following hold; anything else fails
closed with ``ContractError``:

1. The plan and receipt are strict native documents whose digest-bound
   identities validate; the receipt belongs to the plan, names the same
   package baseline, is complete and records no failure, and covers exactly
   the sealed resources.
2. Both documents are the canonical immutable vault files
   (``upgrade-plan-<plan_id>.json`` / ``upgrade-receipt-<receipt_id>.json``)
   inside the still-private sealed backup root. Each is pinned to the exact
   bytes that were parsed (one nofollow read, hashed and strict-parsed),
   and the same pins are rechecked before the context is returned — a
   mutation during validation fails instead of binding unparsed bytes.
3. The plan seals exactly one writable resource: a ``replace`` of the
   canonical ``skill:sbtd-workflow-onboard`` package; every other sealed
   resource is keep/preserve and its receipt row proves it stayed inert
   (``kept`` for keep, ``preserved`` for preserve, never mutated).
4. The sealed replacement target is literally the supplied current package
   path (canonical, no link components), disjoint from the vault.
5. The installed package still matches the successful outcome: its live
   semantic payload state equals the receipt ``after``, the sealed
   ``desired`` state and the sealed baseline source state — the source
   baseline is the same trusted package that is now installed.
6. The original package survives intact: the receipt's ``backup_ref`` is
   the batch's native vault copy, its recorded mechanical state matches the
   receipt ``mechanical_before``, and the backup still matches both that
   mechanical state and the semantic ``before`` state.
7. The batch ran through the staged, digest-bound isolated executor whose
   recorded package state equals the sealed baseline source state.

``revalidate_cleanup_upgrade`` (also ``context.revalidate()``)
re-measures every pinned reference: vault privacy, both document files
byte-identical, the current package payload state, and the backup's
mechanical and payload states. Any drift raises; it never weakens.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from onboard_contracts import ContractError, canonical_json_bytes
from sbtd_migration_files import (
    _canonical,
    read_file,
    require_private_directory,
    snapshot,
)
from sbtd_upgrade import (
    _COMPLETED_TOKENS,
    _WRITABLE,
    _check_decisions,
    _payload_state,
    _strict_loads,
    _validate_plan,
    _validate_upgrade_receipt,
)
from sbtd_upgrade_paths import path_contains, paths_overlap

__all__ = [
    "PROVENANCE_SCHEMA",
    "CleanupUpgradeContext",
    "revalidate_cleanup_upgrade",
    "validate_cleanup_upgrade",
]

PROVENANCE_SCHEMA = "cleanup-upgrade-provenance"

_ONBOARD_ID = "skill:sbtd-workflow-onboard"
_INERT_DECISIONS = ("keep", "preserve")
_ROW_BINDING_KEYS = ("kind", "target", "decision", "before", "desired")


def _fail(code: str, message: str, *, exit_code: int = 2) -> NoReturn:
    raise ContractError(code, message, exit_code=exit_code)


@dataclass(frozen=True)
class CleanupUpgradeContext:
    """Immutable pinned proof of one native Onboard package replacement hop.

    ``provenance`` is a JSON-safe document the cleanup receipt can cite
    verbatim. Its ``current_package`` state is the semantic payload digest
    (stable under interpreter cache churn, equal to the receipt ``after``);
    ``previous_package`` carries the mechanical vault-backup state (equal to
    the receipt ``backup_ref`` state) plus ``previous_payload_state``, the
    semantic digest equal to the receipt ``before``.
    """

    plan_id: str
    receipt_id: str
    baseline_id: str
    resource_id: str
    backup_root: Path
    current_package: Path
    previous_package: Path
    provenance: dict[str, Any]

    def revalidate(self) -> "CleanupUpgradeContext":
        """Re-measure every pinned reference before mutations or publication."""
        return revalidate_cleanup_upgrade(self)


def _pinned_document(path: Path, what: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Strictly parsed document pinned to the exact bytes that were parsed.

    One nofollow read is hashed and parsed, so the pin and the document can
    never diverge; the pin is rechecked before the context is returned and
    again on revalidation, never resnapshot-accepted as new evidence.
    """
    canonical = _canonical(Path(path))
    state = snapshot(canonical)
    if state["type"] != "file":
        _fail("invalid-document", f"{what} is not a regular file")
    raw = read_file(canonical, state)
    document = _strict_loads(raw)
    if raw != canonical_json_bytes(document):
        _fail("invalid-json", f"{what} is not the canonical native document")
    return document, {"path": str(canonical), "state": state}


def _require_canonical_vault_document(
    vault: Path, pin: Mapping[str, Any], name: str, what: str
) -> None:
    """The supplied document must be the native digest-named vault file."""
    if pin["path"] != str(vault / name):
        _fail("upgrade-hop-binding", f"{what} is not the canonical vault document")


def _require_unchanged(pin: Mapping[str, Any]) -> None:
    """Recheck a pinned document ref; never accept a fresh state in its place."""
    if snapshot(Path(pin["path"])) != pin["state"]:
        _fail("evidence-mismatch", "the upgrade evidence changed during validation")


def _check_executor(receipt_payload: Mapping[str, Any], source_state: Mapping[str, Any]) -> None:
    executor = receipt_payload.get("executor")
    if not isinstance(executor, Mapping):
        _fail("invalid-document", "the upgrade receipt executor is malformed")
    if executor.get("isolated") is not True:
        _fail(
            "upgrade-hop-binding",
            "the upgrade batch was not executed by the isolated staged executor",
        )
    if executor.get("package_state") != dict(source_state):
        _fail(
            "upgrade-hop-binding",
            "the upgrade executor package differs from the sealed baseline source",
        )


def _select_replacement(resources: list[dict[str, Any]]) -> dict[str, Any]:
    """Exactly one writable resource: the canonical Onboard package replace."""
    writable = [resource for resource in resources if resource["decision"] in _WRITABLE]
    if len(writable) != 1:
        _fail(
            "upgrade-hop-scope",
            "the upgrade batch must replace exactly the canonical Onboard package",
        )
    replacement = writable[0]
    if replacement["kind"] != "skill" or replacement["decision"] != "replace":
        _fail(
            "upgrade-hop-scope",
            "the upgrade batch write is not a package replacement",
        )
    if replacement["id"] != f"{_ONBOARD_ID}@{replacement['target']}":
        _fail(
            "upgrade-hop-scope",
            "the replaced resource is not the canonical Onboard package",
        )
    if (
        replacement["before"]["type"] != "directory"
        or replacement["desired"]["type"] != "directory"
    ):
        _fail(
            "upgrade-hop-scope",
            "the replaced package states must describe complete directories",
        )
    for resource in resources:
        if resource["decision"] in _WRITABLE:
            continue
        if resource["decision"] not in _INERT_DECISIONS:
            _fail(
                "upgrade-hop-scope",
                "the upgrade batch seals a non-conforming resource decision",
            )
    return replacement


def _check_rows(
    replacement: Mapping[str, Any],
    resources: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """The receipt must cover exactly the sealed set and mutate only the hop."""
    plan_by_id = {resource["id"]: resource for resource in resources}
    row_by_id = {row["id"]: row for row in rows}
    if set(row_by_id) != set(plan_by_id):
        _fail(
            "upgrade-hop-incomplete",
            "the upgrade receipt does not cover exactly the sealed resources",
        )
    row = row_by_id[replacement["id"]]
    if row["result"] not in _COMPLETED_TOKENS or row["mutated"] is not True:
        _fail(
            "upgrade-hop-incomplete",
            "the package replacement did not complete in this receipt",
        )
    for key in _ROW_BINDING_KEYS:
        if row[key] != replacement[key]:
            _fail(
                "upgrade-hop-binding",
                "the replacement receipt row contradicts the sealed plan",
            )
    if row["after"] != replacement["desired"]:
        _fail(
            "upgrade-hop-binding",
            "the replacement outcome differs from the sealed desired state",
        )
    if row["backup_ref"] is None:
        _fail(
            "upgrade-hop-incomplete",
            "the package replacement preserved no original backup",
        )
    if row["mechanical_after"] is None:
        _fail(
            "upgrade-hop-incomplete",
            "the package replacement recorded no measured after state",
        )
    for other in rows:
        if other["id"] == row["id"]:
            continue
        sealed = plan_by_id[other["id"]]
        for key in _ROW_BINDING_KEYS:
            if other[key] != sealed[key]:
                _fail(
                    "upgrade-hop-binding",
                    "a receipt row contradicts the sealed plan",
                )
        expected_inert = "kept" if sealed["decision"] == "keep" else "preserved"
        if (
            other["result"] != expected_inert
            or other["mutated"] is not False
            or other["backup_ref"] is not None
            or other["after"] != other["before"]
        ):
            _fail(
                "upgrade-hop-scope",
                "the upgrade batch mutated an unrelated resource",
            )
    return row


def validate_cleanup_upgrade(
    plan_path: Path,
    receipt_path: Path,
    *,
    current_package: Path,
) -> CleanupUpgradeContext:
    """Prove one complete direct-hop native upgrade of the current package.

    ``plan_path`` and ``receipt_path`` must be the canonical immutable
    documents inside the sealed private backup root; ``current_package`` is
    the installed canonical Onboard package now running. On success returns
    an immutable context whose ``previous_package`` is the intact original
    backup of the replaced package. Raises ``ContractError`` on any
    incomplete, wrong, unsafe or drifted evidence.
    """
    plan_document, plan_pin = _pinned_document(plan_path, "the upgrade plan")
    plan_id, plan_payload = _validate_plan(plan_document)
    if plan_payload["status"] != "planned":
        _fail(
            "upgrade-hop-incomplete",
            "the sealed upgrade plan is not an executable planned batch",
        )
    _check_decisions(plan_payload)

    receipt_document, receipt_pin = _pinned_document(
        receipt_path, "the upgrade receipt"
    )
    receipt_id, receipt_payload = _validate_upgrade_receipt(receipt_document)
    if receipt_payload["plan_id"] != plan_id:
        _fail(
            "upgrade-hop-binding",
            "the upgrade receipt belongs to a different plan",
        )
    if receipt_payload.get("baseline_id") != plan_payload["baseline"]["baseline_id"]:
        _fail(
            "upgrade-hop-binding",
            "the upgrade receipt names a different package baseline",
        )
    if receipt_payload["status"] != "complete":
        _fail(
            "upgrade-hop-incomplete",
            "the upgrade receipt is not a complete batch",
        )
    if receipt_payload["failure"] is not None:
        _fail(
            "upgrade-hop-incomplete",
            "the upgrade receipt records a batch failure",
        )
    if receipt_payload["backup_root"] != plan_payload["backup_root"]:
        _fail(
            "upgrade-hop-binding",
            "the upgrade receipt names a different private backup root",
        )
    _check_executor(receipt_payload, plan_payload["baseline"]["source"]["state"])

    vault = require_private_directory(Path(plan_payload["backup_root"]))
    _require_canonical_vault_document(
        vault, plan_pin, f"upgrade-plan-{plan_id}.json", "the upgrade plan"
    )
    _require_canonical_vault_document(
        vault, receipt_pin, f"upgrade-receipt-{receipt_id}.json", "the upgrade receipt"
    )

    replacement = _select_replacement(plan_payload["resources"])
    row = _check_rows(replacement, plan_payload["resources"], receipt_payload["resources"])

    current = _canonical(Path(current_package))
    if str(current) != replacement["target"]:
        _fail(
            "upgrade-hop-binding",
            "the current package is not the sealed replacement target",
        )
    if paths_overlap(current, vault):
        _fail(
            "backup-root-overlap",
            "the current package overlaps the private backup root",
        )

    source_state = plan_payload["baseline"]["source"]["state"]
    desired = replacement["desired"]
    if desired != source_state:
        _fail(
            "upgrade-hop-binding",
            "the sealed package source differs from the replacement goal",
        )
    backup_ref = row["backup_ref"]
    previous = _canonical(Path(backup_ref["path"]))
    expected_backup = (
        vault
        / "originals"
        / plan_id[:16]
        / hashlib.sha256(replacement["id"].encode("utf-8")).hexdigest()[:32]
    )
    if previous == vault or not path_contains(previous, vault):
        _fail(
            "upgrade-hop-binding",
            "the original backup is not contained in the private vault",
        )
    if previous != expected_backup:
        _fail(
            "upgrade-hop-binding",
            "the original backup is not the batch's native vault copy",
        )
    if paths_overlap(previous, current):
        _fail(
            "upgrade-hop-binding",
            "the original backup overlaps the current package",
        )
    if row["mechanical_before"] != backup_ref["state"]:
        _fail(
            "upgrade-hop-binding",
            "the original backup does not match the recorded pre-write state",
        )

    current_state = _payload_state(current)
    if current_state != desired or current_state != row["after"]:
        _fail(
            "upgrade-hop-drift",
            "the installed package no longer matches the upgrade outcome",
        )
    previous_mechanical = snapshot(previous)
    if previous_mechanical != backup_ref["state"]:
        _fail(
            "preservation-failed",
            "the original package backup changed since the upgrade",
            exit_code=3,
        )
    previous_payload = _payload_state(previous)
    if previous_payload != row["before"]:
        _fail(
            "preservation-failed",
            "the original package backup payload differs from the replaced state",
            exit_code=3,
        )

    # Last gate: the parsed evidence bytes must still be the pinned bytes.
    _require_unchanged(plan_pin)
    _require_unchanged(receipt_pin)

    provenance = {
        "schema": PROVENANCE_SCHEMA,
        "schema_version": 1,
        "plan_id": plan_id,
        "receipt_id": receipt_id,
        "baseline_id": plan_payload["baseline"]["baseline_id"],
        "resource_id": replacement["id"],
        "backup_root": str(vault),
        "plan_ref": plan_pin,
        "receipt_ref": receipt_pin,
        "current_package": {"path": str(current), "state": current_state},
        "previous_package": {"path": str(previous), "state": previous_mechanical},
        "previous_payload_state": previous_payload,
    }
    return CleanupUpgradeContext(
        plan_id=plan_id,
        receipt_id=receipt_id,
        baseline_id=plan_payload["baseline"]["baseline_id"],
        resource_id=replacement["id"],
        backup_root=vault,
        current_package=current,
        previous_package=previous,
        provenance=provenance,
    )


def revalidate_cleanup_upgrade(context: CleanupUpgradeContext) -> CleanupUpgradeContext:
    """Re-measure every pinned reference; raise on any drift, never weaken.

    Intended for immediately before the cleanup's first mutation and again
    before receipt publication, so late drift of the vault documents, the
    installed package or the original backup still fails closed.
    """
    if not isinstance(context, CleanupUpgradeContext):
        _fail("invalid-argument", "revalidation requires a cleanup upgrade context")
    provenance = context.provenance
    vault = require_private_directory(Path(provenance["backup_root"]))
    for key in ("plan_ref", "receipt_ref"):
        reference = provenance[key]
        path = _canonical(Path(reference["path"]))
        if snapshot(path) != reference["state"]:
            _fail(
                "evidence-mismatch",
                "the upgrade evidence changed since validation",
            )
    current = _canonical(Path(provenance["current_package"]["path"]))
    if current != context.current_package:
        _fail(
            "upgrade-hop-binding",
            "the context current package is inconsistent with its provenance",
        )
    if _payload_state(current) != provenance["current_package"]["state"]:
        _fail(
            "upgrade-hop-drift",
            "the installed package drifted since validation",
        )
    previous = _canonical(Path(provenance["previous_package"]["path"]))
    if (
        previous != context.previous_package
        or previous == vault
        or not path_contains(previous, vault)
        or paths_overlap(previous, current)
        or paths_overlap(current, vault)
    ):
        _fail(
            "upgrade-hop-binding",
            "the context package paths are inconsistent with their provenance",
        )
    if snapshot(previous) != provenance["previous_package"]["state"]:
        _fail(
            "preservation-failed",
            "the original package backup changed since validation",
            exit_code=3,
        )
    if _payload_state(previous) != provenance["previous_payload_state"]:
        _fail(
            "preservation-failed",
            "the original package backup payload changed since validation",
            exit_code=3,
        )
    return CleanupUpgradeContext(
        plan_id=context.plan_id,
        receipt_id=context.receipt_id,
        baseline_id=context.baseline_id,
        resource_id=context.resource_id,
        backup_root=vault,
        current_package=current,
        previous_package=previous,
        provenance=context.provenance,
    )
