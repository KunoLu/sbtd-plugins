"""Onboard upgrade alignment engine: sealed plans, guarded apply, verify, recovery.

This module owns the upgrade core. ``sbtd_upgrade_inventory`` builds the
payload baseline and skill/AGENTS resources, ``sbtd_upgrade_hosts`` builds,
renders and verifies host (MCP/shell) resources, and ``sbtd_upgrade_cli``
owns the public CLI envelope. Everything here returns JSON-safe
dictionaries; refusals raise the existing sanitized ``ContractError``.

Two digest families are kept strictly separate:

- Semantic (payload) states come only from the inventory module's
  ``payload_directory_state`` / ``payload_file_state`` helpers. They are
  stable under cache churn and seal plans, receipts, intents and recovery
  expectations; they decide drift, alignment and retry reconciliation.
- Mechanical states are fresh ``sbtd_migration_files.snapshot`` results
  taken immediately before each primitive call and passed as ``expected``
  to ``backup_reference`` / ``install_reference`` / ``write_file`` /
  ``remove_reference``. The two families are never compared to each other.

Security semantics, by design:

- A plan seals the baseline, the canonical scope (normalized once through
  the inventory provider's strict ``normalize_scope``: checked absolute
  paths with their literal spelling, canonical host platforms such as
  oh-my-pi -> omp), the private backup
  root and every resource identity. The ``plan_id`` binds one confirmation
  to that sealed set; it is not authentication and never authorizes
  arbitrary paths.
- Apply re-derives resource identities from the sealed scope and the
  current validated sources. A self-consistent plan whose resources were
  edited and re-hashed (paths, desired content, source pins) is rejected
  as plan-stale; the sealed skill/AGENTS decision must also match the
  documented classification/decision rule, so flipping a preserve into a
  replace requires editing the user's own scope decisions, which the
  confirmation binds.
- Every mutation batch runs in an isolated subprocess executed from a
  complete staged copy of the current package inside the private vault.
  The staged copy is digest-bound to the sealed baseline source state, so
  the running package may itself be an upgrade target without ever
  lazy-importing a mixed old/new module set. Host rendering keeps its
  anchor at the real package root; rendered configuration never points
  into the vault.
- The whole resource set is preflighted (overlap, vault disjointness,
  live before-states, complete original backups) before the first write.
  Each write is preceded by an immutable persisted intent and followed by
  a measured after-state and an immutable cumulative receipt. Original
  backups are never destroyed by the engine.
- Retry skips only resources whose live state matches the prior receipt's
  recorded after-state. An interruption between a write and its receipt
  is reconciled from the persisted intent and the measured live state,
  never claimed unwritten; unknown live state is rejected.
- Recovery covers only resources this batch actually changed, re-seals
  the current after-state, requires its own confirmation, refuses live
  drift (unknown changes are never overwritten) and restores backups
  without deleting them.
- A failure escaping the mutation region (intent/receipt persistence or an
  isolated executor crash) is re-raised with ``details["batch"]`` binding
  the plan or recovery identity, the private backup root, the latest
  trusted checkpoint receipt path and the measured-or-unknown mutation
  state. The bound checkpoint is recovery evidence, never the failed
  attempt's success; pre-write validation failures carry no batch evidence
  and keep the plain pre-write blocked surface.
- Verify is read-only: managed skill/AGENTS payload state is measured
  semantically against the sealed desired states, while MCP/shell disk,
  runtime, host and legacy evidence comes from ``verify_hosts`` as a
  separate dimension — a user adding unrelated configuration after the
  upgrade stays aligned, ownership drift still fails. A preserve
  exception always prevents a complete-aligned result, and without an
  explicit probe no host loading is claimed.

No cross-domain atomic transaction is claimed: resources are written one
at a time with per-resource receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn

from onboard_contracts import ContractError, canonical_json_bytes
from sbtd_cleanup_targets import strict_json_object
from sbtd_migration_files import (
    _canonical,
    _lstat,
    backup_reference,
    directory_snapshot,
    install_reference,
    read_file,
    remove_reference,
    require_private_directory,
    save_document,
    snapshot,
    write_file,
)
from sbtd_upgrade_paths import paths_overlap

__all__ = [
    "apply_recovery",
    "apply_upgrade",
    "plan_recovery",
    "plan_upgrade",
    "prepare_probe_link_authorization",
    "save_plan",
    "verify_upgrade",
]

PLAN_SCHEMA = "upgrade-plan"
RECEIPT_SCHEMA = "upgrade-receipt"
VERIFICATION_SCHEMA = "upgrade-verification"
RECOVERY_PLAN_SCHEMA = "upgrade-recovery-plan"
RECOVERY_RECEIPT_SCHEMA = "upgrade-recovery-receipt"

_HEX = frozenset("0123456789abcdef")
_ABSENT = {"type": "absent", "checksum": None}
_STATE_TYPES = ("absent", "file", "directory")
_RESOURCE_KINDS = ("skill", "agents", "mcp", "shell")
_CLASSIFICATIONS = (
    "missing",
    "current",
    "known-old",
    "unknown-drift",
    "identity-conflict",
)
_DECISIONS = ("install", "keep", "replace", "preserve", "blocked")
_WRITABLE = ("install", "replace")
_RESULT_TOKENS = (
    "succeeded",
    "reconciled",
    "skipped-complete",
    "kept",
    "preserved",
    "failed",
    "pending",
)
_STEP_RESULT_TOKENS = (
    "succeeded",
    "reconciled",
    "skipped-complete",
    "failed",
    "pending",
)
_COMPLETED_TOKENS = ("succeeded", "reconciled", "skipped-complete")


def _fail(code: str, message: str, *, exit_code: int = 2) -> NoReturn:
    raise ContractError(code, message, exit_code=exit_code)


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _bytes_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# ---------------------------------------------------------------------------
# Strict document decoding and validation
# ---------------------------------------------------------------------------


def _strict_loads(raw: bytes) -> dict[str, Any]:
    try:
        return strict_json_object(raw)
    except (UnicodeDecodeError, TypeError, ValueError) as error:
        raise ContractError(
            "invalid-json", "document is not a strict finite JSON object"
        ) from error


def _load_document_file(path: Path) -> dict[str, Any]:
    state = snapshot(path)
    if state["type"] != "file":
        _fail("invalid-document", "referenced document is not a regular file")
    return _strict_loads(read_file(path, state))


def _expect_mapping(value: Any, what: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("invalid-document", f"{what} must be a JSON object")
    return dict(value)


def _expect_hex(value: Any, what: str) -> str:
    if not (
        isinstance(value, str) and len(value) == 64 and _HEX.issuperset(value)
    ):
        _fail(
            "invalid-document", f"{what} must be a lowercase SHA-256 hex digest"
        )
    return value


def _expect_state(value: Any, what: str) -> dict[str, Any]:
    state = _expect_mapping(value, what)
    if set(state) != {"type", "checksum"}:
        _fail("invalid-document", f"{what} must carry exactly type and checksum")
    kind = state["type"]
    checksum = state["checksum"]
    if kind not in _STATE_TYPES:
        _fail(
            "invalid-document",
            f"{what} state type is not absent, file or directory",
        )
    if kind == "absent":
        if checksum is not None:
            _fail(
                "invalid-document", f"{what} absent state cannot carry a checksum"
            )
    else:
        _expect_hex(checksum, f"{what} checksum")
    return {"type": kind, "checksum": checksum}


def _expect_abs_path(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(
            "invalid-document",
            f"{what} must be a non-empty absolute path string",
        )
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        _fail("unsafe-path", f"{what} must be a canonical absolute path")
    return str(path)




def _expect_reference(value: Any, what: str) -> dict[str, Any]:
    reference = _expect_mapping(value, what)
    if set(reference) != {"path", "state"}:
        _fail("invalid-document", f"{what} must carry exactly path and state")
    path = _expect_abs_path(reference["path"], f"{what} path")
    state = _expect_state(reference["state"], f"{what} state")
    if state["type"] == "absent":
        _fail(
            "invalid-document", f"{what} state must describe a present object"
        )
    return {"path": path, "state": state}


def _validate_baseline(value: Any) -> dict[str, Any]:
    baseline = _expect_mapping(value, "baseline")
    if not isinstance(baseline.get("baseline_id"), str) or not baseline["baseline_id"]:
        _fail("invalid-inventory", "baseline must carry a non-empty baseline_id")
    source = _expect_mapping(baseline.get("source"), "baseline.source")
    source_path = _expect_abs_path(source.get("path"), "baseline.source.path")
    source_state = _expect_state(source.get("state"), "baseline.source.state")
    if source_state["type"] != "directory":
        _fail("invalid-inventory", "baseline source must be a directory state")
    return {**baseline, "source": {"path": source_path, "state": source_state}}


def _validate_source(value: Any, what: str) -> dict[str, Any]:
    """Resource source: absolute path string or a {"path","state"} reference."""
    if isinstance(value, str):
        return {"path": _expect_abs_path(value, what), "state": None}
    reference = _expect_mapping(value, what)
    if set(reference) - {"path", "state"} or "path" not in reference:
        _fail("invalid-inventory", f"{what} must carry path and optional state")
    path = _expect_abs_path(reference["path"], f"{what} path")
    state = reference.get("state")
    if state is not None:
        state = _expect_state(state, f"{what} state")
        if state["type"] == "absent":
            _fail("invalid-inventory", f"{what} state must describe a payload")
    return {"path": path, "state": state}


def _validate_resource(value: Any, what: str) -> dict[str, Any]:
    resource = _expect_mapping(value, what)
    required = {
        "id",
        "kind",
        "target",
        "source",
        "before",
        "desired",
        "classification",
        "decision",
        "details",
    }
    if required - set(resource):
        _fail("invalid-inventory", f"{what} is missing required resource fields")
    if not isinstance(resource["id"], str) or not resource["id"]:
        _fail("invalid-inventory", f"{what} id must be a non-empty string")
    if resource["kind"] not in _RESOURCE_KINDS:
        _fail("invalid-inventory", f"{what} kind is not a known resource kind")
    target = _expect_abs_path(resource["target"], f"{what} target")
    source = _validate_source(resource["source"], f"{what} source")
    before = _expect_state(resource["before"], f"{what} before")
    desired = resource["desired"]
    if desired is not None:
        desired = _expect_state(desired, f"{what} desired")
        if desired["type"] == "absent":
            _fail(
                "invalid-inventory",
                f"{what} desired state must describe a payload",
            )
    if resource["classification"] not in _CLASSIFICATIONS:
        _fail("invalid-inventory", f"{what} classification is not recognized")
    decision = resource["decision"]
    if decision not in _DECISIONS:
        _fail("invalid-inventory", f"{what} decision is not recognized")
    if not isinstance(resource["details"], Mapping):
        _fail("invalid-inventory", f"{what} details must be an object")
    if decision in _WRITABLE and desired is None:
        _fail(
            "invalid-inventory",
            f"{what} a writable decision requires a desired state",
        )
    if decision in ("keep",) and desired is None:
        _fail(
            "invalid-inventory",
            f"{what} a kept resource requires a desired state",
        )
    if decision == "install" and before["type"] != "absent":
        _fail("invalid-inventory", f"{what} install requires an absent before-state")
    if decision == "replace" and before["type"] == "absent":
        _fail(
            "invalid-inventory", f"{what} replace requires a present before-state"
        )
    return {
        **resource,
        "target": target,
        "source": source,
        "before": before,
        "desired": desired,
        "details": dict(resource["details"]),
    }


def _expected_decision(
    classification: str, decisions: Mapping[str, Any], target: str
) -> str:
    """Documented skill/AGENTS classification/decision rule.

    Mirrors the inventory module: missing installs (an explicit preserve is
    honored); current keeps; known-old and unknown-drift follow the sealed
    scope decision and block without one; identity-conflict blocks and may
    only be preserved, never approved as replace. Host resources derive
    their decisions in the host module from the same sealed scope.
    """
    choice = decisions.get(target)
    if classification == "missing":
        return "preserve" if choice == "preserve" else "install"
    if classification == "current":
        return "keep"
    if classification == "identity-conflict":
        return "preserve" if choice == "preserve" else "blocked"
    if choice == "replace":
        return "replace"
    if choice == "preserve":
        return "preserve"
    return "blocked"


def _scope_decisions(scope: Mapping[str, Any]) -> dict[str, str]:
    raw = scope.get("decisions", {})
    if not isinstance(raw, Mapping):
        _fail("invalid-scope", "scope decisions must be an object keyed by target")
    decisions: dict[str, str] = {}
    for key, value in raw.items():
        target = _expect_abs_path(key, "scope decision target")
        if value not in ("replace", "preserve"):
            _fail("invalid-scope", "scope decision must be replace or preserve")
        decisions[target] = value
    return decisions


def _validate_scope(value: Any) -> dict[str, Any]:
    scope = _expect_mapping(value, "scope")
    if type(scope.get("schema_version")) is not int or scope["schema_version"] != 1:
        _fail("invalid-scope", "scope schema_version must be 1")
    _scope_decisions(scope)
    return scope

def _canonical_scope(scope: Mapping[str, Any]) -> dict[str, Any]:
    """Canonical provider-normalized scope sealed by every plan.

    The inventory provider's strict ``normalize_scope`` owns the single
    normalization rule (resolved paths, canonical host platforms such as
    oh-my-pi -> omp); the engine re-validates the JSON-safe result so the
    sealed scope, derived resources and later verification all agree.
    """
    normalize = getattr(_inventory_module(), "normalize_scope", None)
    if normalize is None:
        _fail(
            "inventory-unavailable",
            "the upgrade inventory module does not expose scope normalization",
        )
    return _validate_scope(_strict_loads(canonical_json_bytes(normalize(scope))))


def _validate_plan(plan: Any) -> tuple[str, dict[str, Any]]:
    document = _expect_mapping(plan, "plan")
    if type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        _fail("invalid-document", "plan schema_version must be 1")
    plan_id = _expect_hex(document.get("plan_id"), "plan_id")
    payload = _expect_mapping(document.get("payload"), "plan payload")
    if payload.get("plan_schema") != PLAN_SCHEMA:
        _fail("invalid-document", "document is not an upgrade plan")
    if _digest(payload) != plan_id:
        _fail(
            "plan-id-mismatch",
            "plan id does not match the canonical payload digest",
            exit_code=3,
        )
    _validate_baseline(payload.get("baseline"))
    _validate_scope(payload.get("scope"))
    _expect_abs_path(payload.get("backup_root"), "plan backup_root")
    if payload.get("status") not in ("planned", "blocked"):
        _fail("invalid-document", "plan status is not planned or blocked")
    resources = payload.get("resources")
    if not isinstance(resources, list) or not resources:
        _fail("invalid-document", "plan must seal at least one resource")
    for index, resource in enumerate(resources):
        _validate_resource(resource, f"plan resource {index}")
    if not isinstance(payload.get("domains"), list):
        _fail("invalid-document", "plan domains must be a list")
    return plan_id, payload


def _validate_receipt(
    receipt: Any, *, schema: str, id_key: str, list_key: str
) -> tuple[str, dict[str, Any]]:
    document = _expect_mapping(receipt, "receipt")
    if type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        _fail("invalid-document", "receipt schema_version must be 1")
    receipt_id = _expect_hex(document.get(id_key), id_key)
    payload = _expect_mapping(document.get("payload"), "receipt payload")
    if payload.get("receipt_schema") != schema:
        _fail("invalid-document", "receipt schema does not match its phase")
    if _digest(payload) != receipt_id:
        _fail(
            "receipt-id-mismatch",
            "receipt id does not match the canonical payload digest",
            exit_code=3,
        )
    previous = payload.get("previous_receipt_id")
    if previous is not None:
        _expect_hex(previous, "previous_receipt_id")
    sequence = payload.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
        _fail(
            "invalid-document", "receipt sequence must be a non-negative integer"
        )
    if payload.get("status") not in ("complete", "partial", "failed"):
        _fail(
            "invalid-document",
            "receipt status is not complete, partial or failed",
        )
    if not isinstance(payload.get(list_key), list):
        _fail("invalid-document", "receipt results must be a list")
    _expect_abs_path(payload.get("backup_root"), "receipt backup_root")
    return receipt_id, payload


def _validate_upgrade_receipt(receipt: Any) -> tuple[str, dict[str, Any]]:
    receipt_id, payload = _validate_receipt(
        receipt, schema=RECEIPT_SCHEMA, id_key="receipt_id", list_key="resources"
    )
    _expect_hex(payload.get("plan_id"), "receipt plan_id")
    seen: set[str] = set()
    for row in payload["resources"]:
        if not isinstance(row, Mapping) or not isinstance(row.get("id"), str):
            _fail("invalid-document", "a receipt resource row is malformed")
        if row["id"] in seen:
            _fail("invalid-document", "receipt resource ids must be unique")
        seen.add(row["id"])
        _expect_abs_path(row.get("target"), "receipt resource target")
        for key in ("before", "mechanical_before"):
            _expect_state(row.get(key), f"receipt resource {key}")
        for key in ("after", "desired", "mechanical_after"):
            if row.get(key) is not None:
                _expect_state(row[key], f"receipt resource {key}")
        if row.get("result") not in _RESULT_TOKENS:
            _fail("invalid-document", "a receipt resource result is unrecognized")
        if "mutated" not in row or (row["mutated"] is not None and type(row["mutated"]) is not bool):
            _fail("invalid-document", "receipt mutation attribution must be boolean or unknown")
        if row.get("backup_ref") is not None:
            _expect_reference(row["backup_ref"], "receipt resource backup")
    return receipt_id, payload


def _validate_recovery_receipt(receipt: Any) -> tuple[str, dict[str, Any]]:
    receipt_id, payload = _validate_receipt(
        receipt,
        schema=RECOVERY_RECEIPT_SCHEMA,
        id_key="recovery_receipt_id",
        list_key="steps",
    )
    _expect_hex(payload.get("recovery_id"), "receipt recovery_id")
    return receipt_id, payload


def _validate_step(step: Any, what: str) -> dict[str, Any]:
    row = _expect_mapping(step, what)
    _expect_hex(row.get("step_id"), f"{what} step_id")
    if not isinstance(row.get("resource_id"), str) or not row["resource_id"]:
        _fail(
            "invalid-document", f"{what} resource_id must be a non-empty string"
        )
    _expect_abs_path(row.get("target"), f"{what} target")
    if row.get("action") not in ("restore", "remove"):
        _fail("invalid-document", f"{what} action is not restore or remove")
    expected = _expect_state(row.get("expected_current"), f"{what} expected_current")
    _expect_state(row.get("expected_mechanical"), f"{what} expected_mechanical")
    restore_state = row.get("restore_state")
    if restore_state is not None:
        _expect_state(restore_state, f"{what} restore_state")
    backup_ref = row.get("backup_ref")
    if backup_ref is not None:
        _expect_reference(backup_ref, f"{what} backup_ref")
    if row.get("status") not in ("actionable", "blocked"):
        _fail(
            "invalid-document", f"{what} status is not actionable or blocked"
        )
    parents = row.get("created_parents", [])
    if not isinstance(parents, list):
        _fail("invalid-document", f"{what} created_parents must be a list")
    for parent in parents:
        _expect_abs_path(parent, f"{what} created parent")
        if Path(parent) not in Path(row["target"]).parents or Path(parent).parent == Path(parent):
            _fail("unsafe-path", "a recovery parent lies outside the resource ancestry")
    if row.get("action") == "restore" and restore_state is None:
        _fail("invalid-document", f"{what} restore needs a restore state")
    if expected["type"] == "absent" and row.get("action") != "restore":
        _fail(
            "invalid-document",
            f"{what} expected_current must describe the batch outcome",
        )
    return row


def _validate_recovery_plan(plan: Any) -> tuple[str, dict[str, Any]]:
    document = _expect_mapping(plan, "recovery plan")
    if type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        _fail("invalid-document", "recovery plan schema_version must be 1")
    recovery_id = _expect_hex(document.get("recovery_id"), "recovery_id")
    payload = _expect_mapping(document.get("payload"), "recovery plan payload")
    if payload.get("recovery_schema") != RECOVERY_PLAN_SCHEMA:
        _fail("invalid-document", "document is not an upgrade recovery plan")
    if _digest(payload) != recovery_id:
        _fail(
            "plan-id-mismatch",
            "recovery id does not match the canonical payload digest",
            exit_code=3,
        )
    _expect_hex(payload.get("plan_id"), "recovery plan plan_id")
    _expect_hex(payload.get("receipt_id"), "recovery plan receipt_id")
    _expect_abs_path(payload.get("backup_root"), "recovery plan backup_root")
    if payload.get("status") not in ("planned", "blocked"):
        _fail("invalid-document", "recovery plan status is not planned or blocked")
    steps = payload.get("steps")
    if not isinstance(steps, list):
        _fail("invalid-document", "recovery plan steps must be a list")
    for index, step in enumerate(steps):
        _validate_step(step, f"recovery step {index}")
    return recovery_id, payload


# ---------------------------------------------------------------------------
# Lazy provider modules (also the test seam: sys.modules injection)
# ---------------------------------------------------------------------------


def _inventory_module() -> Any:
    try:
        return importlib.import_module("sbtd_upgrade_inventory")
    except ImportError as error:
        raise ContractError(
            "inventory-unavailable",
            "the upgrade inventory module is not importable",
        ) from error


def _hosts_module() -> Any:
    try:
        return importlib.import_module("sbtd_upgrade_hosts")
    except ImportError as error:
        raise ContractError(
            "hosts-unavailable", "the upgrade hosts module is not importable"
        ) from error


def _payload_state(path: Path) -> dict[str, Any]:
    """Semantic state via the inventory payload digest; never snapshot()."""
    probe = snapshot(path)
    if probe["type"] == "absent":
        return dict(_ABSENT)
    inventory = _inventory_module()
    if probe["type"] == "directory":
        state = inventory.payload_directory_state(path)
        expected = "directory"
    else:
        state = inventory.payload_file_state(path)
        expected = "file"
    result = _expect_state(state, "payload state")
    if result["type"] != expected:
        _fail("invalid-inventory", "payload state type disagrees with the target")
    return result


def _derive_resources(
    scope: Mapping[str, Any], package_root: Path | None, *, host_package_root: Path | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]], list[Any]]:
    inventory = _inventory_module().build_inventory(scope, package_root=package_root)
    result = _expect_mapping(inventory, "inventory result")
    baseline = _validate_baseline(result.get("baseline"))
    raw_resources = result.get("resources")
    if not isinstance(raw_resources, list):
        _fail("invalid-inventory", "inventory resources must be a list")
    domains = result.get("domains")
    if not isinstance(domains, list):
        _fail("invalid-inventory", "inventory domains must be a list")
    host_root = host_package_root if host_package_root is not None else package_root
    host_resources = (
        _hosts_module().build_host_resources(scope, package_root=host_root)
        if scope.get("hosts") or scope.get("shell_profiles") else []
    )
    if not isinstance(host_resources, list):
        _fail("invalid-inventory", "host resources must be a list")
    resources = [
        _validate_resource(resource, f"inventory resource {index}")
        for index, resource in enumerate(raw_resources)
    ] + [
        _validate_resource(resource, f"host resource {index}")
        for index, resource in enumerate(host_resources)
    ]
    if not resources:
        _fail("invalid-scope", "the scope selects no resources")
    return baseline, resources, domains


# ---------------------------------------------------------------------------
# Overlap preflight and identity comparison
# ---------------------------------------------------------------------------


def _preflight_set(resources: list[dict[str, Any]], vault: Path) -> None:
    targets = [Path(resource["target"]) for resource in resources]
    ids: set[str] = set()
    for index, target in enumerate(targets):
        resource_id = resources[index]["id"]
        if resource_id in ids:
            _fail("resource-overlap", "two resources share one stable id")
        ids.add(resource_id)
        for other in targets[index + 1 :]:
            if paths_overlap(target, other):
                _fail(
                    "resource-overlap",
                    "upgrade targets must never be equal or nested",
                )
        if paths_overlap(target, vault):
            _fail(
                "backup-root-overlap",
                "the private backup root and an upgrade target overlap",
            )
    for resource in resources:
        source = Path(resource["source"]["path"])
        if paths_overlap(source, vault):
            _fail(
                "backup-root-overlap",
                "the private backup root and an upgrade source overlap",
            )


def _source_identity(resource: Mapping[str, Any], package_path: str) -> dict[str, Any]:
    source = resource["source"]
    if resource["kind"] in ("mcp", "shell"):
        return {"path": source["path"], "state": source["state"]}
    try:
        relative: str | None = (
            Path(source["path"]).relative_to(Path(package_path)).as_posix()
        )
    except ValueError:
        relative = None
    return {
        "path": relative if relative is not None else source["path"],
        "state": source["state"],
    }


def _relative_package_path(path: str, package_path: str) -> str:
    """Normalize package-internal pins without changing durable target paths."""
    try:
        return Path(path).relative_to(Path(package_path)).as_posix()
    except ValueError:
        return path



def _identity_view(resource: Mapping[str, Any], package_path: str) -> dict[str, Any]:
    """Batch-invariant identity: what is installed where from which payload."""
    view = {
        "id": resource["id"],
        "kind": resource["kind"],
        "target": resource["target"],
        "source": _source_identity(resource, package_path),
        "desired": resource["desired"],
    }
    for extra in ("host", "profile"):
        if extra in resource:
            view[extra] = resource[extra]
    details = resource["details"]
    view["bindings"] = {
        key: details[key] for key in ("package_root", "runtime", "launcher_source", "onboard_payload_digest", "shell", "bin", "command_identity", "runtime_cli_targets")
        if key in details
    }
    if isinstance(view["bindings"].get("launcher_source"), Mapping):
        launcher_source = view["bindings"]["launcher_source"]
        view["bindings"]["launcher_source"] = {
            **launcher_source,
            "path": _relative_package_path(launcher_source["path"], package_path),
        }
    if isinstance(view["bindings"].get("package_root"), str):
        view["bindings"]["package_root"] = "."
    if "launcher" in details:
        launcher = details["launcher"]
        view["bindings"]["launcher"] = {
            key: launcher[key] for key in ("path", "desired") if key in launcher
        }
    if "effective_inputs" in details:
        view["bindings"]["effective_inputs"] = [
            dependency for dependency in details["effective_inputs"]
            if dependency["path"] != resource["target"]
        ]
    return view


def _check_plan_fresh(
    sealed: list[dict[str, Any]],
    recomputed: list[dict[str, Any]],
    sealed_baseline: Mapping[str, Any],
    fresh_baseline: Mapping[str, Any],
) -> None:
    if sealed_baseline["baseline_id"] != fresh_baseline["baseline_id"]:
        _fail(
            "plan-stale", "the package baseline changed since the plan was sealed"
        )
    if sealed_baseline["source"]["state"] != fresh_baseline["source"]["state"]:
        _fail(
            "plan-stale", "the package source changed since the plan was sealed"
        )
    sealed_map = {resource["id"]: resource for resource in sealed}
    fresh_map = {resource["id"]: resource for resource in recomputed}
    if set(sealed_map) != set(fresh_map):
        _fail(
            "plan-stale", "the derived resource set differs from the sealed plan"
        )
    sealed_package = sealed_baseline["source"]["path"]
    fresh_package = fresh_baseline["source"]["path"]
    for resource_id, sealed_resource in sealed_map.items():
        if _identity_view(sealed_resource, sealed_package) != _identity_view(
            fresh_map[resource_id], fresh_package
        ):
            _fail(
                "plan-stale",
                "a sealed resource identity differs from a fresh derivation",
            )


def _check_decisions(payload: Mapping[str, Any]) -> None:
    decisions = _scope_decisions(payload["scope"])
    for resource in payload["resources"]:
        expected = _expected_decision(
            resource["classification"], decisions, resource["target"]
        )
        if resource["kind"] in ("mcp", "shell"):
            if resource["classification"] == "missing":
                expected = "install"
            elif resource["classification"] == "identity-conflict":
                expected = "blocked"
        if resource["decision"] in _WRITABLE and resource["before"] == resource["desired"]:
            _fail("plan-inconsistent", "a semantically current resource cannot be approved as a write")
        if resource["decision"] != expected:
            _fail(
                "plan-inconsistent",
                "a sealed decision contradicts the documented decision rule",
            )
    if payload["status"] == "blocked" or any(
        resource["decision"] == "blocked" for resource in payload["resources"]
    ):
        _fail(
            "blocked-resource",
            "the plan seals blocked resources; resolve the scope decisions first",
        )


# ---------------------------------------------------------------------------
# Vault layout and immutable document persistence
# ---------------------------------------------------------------------------


def _ensure_private_subdir(vault: Path, name: str) -> Path:
    return require_private_directory(vault / name, create=True)


def _save_once(
    path: Path, document: Mapping[str, Any], vault: Path
) -> dict[str, Any]:
    """Immutable save; an existing identical document is reused, never rewritten."""
    state = snapshot(path)
    if state["type"] == "absent":
        return save_document(path, document, private_root=vault)
    existing = read_file(path, state)
    if existing != canonical_json_bytes(document):
        _fail(
            "state-conflict",
            "an immutable vault document already holds different content",
        )
    return {"path": str(path), "state": state}


def _receipt_document(payload: Mapping[str, Any], id_key: str) -> dict[str, Any]:
    receipt_id = _digest(payload)
    prefix = "upgrade-receipt" if id_key == "receipt_id" else "upgrade-recovery-receipt"
    return {
        "schema_version": 1,
        "receipt_path": str(Path(payload["backup_root"]) / f"{prefix}-{receipt_id}.json"),
        "status": payload["status"],
        id_key: receipt_id,
        "payload": dict(payload),
    }


def _scan_documents(vault: Path, prefix: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if not vault.is_dir():
        return found
    for entry in sorted(vault.iterdir()):
        if not entry.name.startswith(prefix) or not entry.name.endswith(".json"):
            continue
        found.append(_load_document_file(Path(entry)))
    return found


def _scan_intents(
    vault: Path, prefix: str, id_field: str
) -> dict[str, dict[str, Any]]:
    intents_dir = vault / "intents"
    intents: dict[str, dict[str, Any]] = {}
    if not intents_dir.is_dir():
        return intents
    for entry in sorted(intents_dir.iterdir()):
        if not entry.name.startswith(prefix) or not entry.name.endswith(".json"):
            continue
        document = _load_document_file(Path(entry))
        payload = document.get("payload")
        if not isinstance(payload, Mapping) or not isinstance(
            payload.get(id_field), str
        ):
            _fail("corrupt-evidence", "a vault intent document is malformed")
        intents[payload[id_field]] = dict(payload)
    return intents


def _latest_receipt(
    vault: Path,
    prefix: str,
    plan_field: str,
    plan_id: str,
    passed: dict[str, Any] | None,
    validator: Any,
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for document in _scan_documents(vault, prefix):
        _receipt_id, payload = validator(document)
        if payload.get(plan_field) == plan_id:
            candidates.append(document)
    if passed is not None:
        candidates.append(passed)
    if not candidates:
        return None

    def rank(document: dict[str, Any]) -> tuple[int, int, int]:
        payload = document["payload"]
        rows = payload.get("resources", payload.get("steps", []))
        terminal = sum(
            1
            for row in rows
            if isinstance(row, Mapping) and row.get("result") != "pending"
        )
        return payload["sequence"], len(rows), terminal

    return max(candidates, key=rank)


# ---------------------------------------------------------------------------
# Post-mutation failure evidence (bound to the sealed batch identity)
# ---------------------------------------------------------------------------


def _latest_checkpoint(
    vault: Path, *, phase: str, plan_id: str | None, recovery_id: str | None
) -> dict[str, Any] | None:
    """Latest persisted checkpoint receipt reference for the batch, if any."""
    batch_id = recovery_id if phase == "recovery" else plan_id
    if batch_id is None:
        return None
    try:
        if phase == "recovery":
            document = _latest_receipt(
                vault,
                "upgrade-recovery-receipt-",
                "recovery_id",
                batch_id,
                None,
                _validate_recovery_receipt,
            )
            id_key, prefix = "recovery_receipt_id", "upgrade-recovery-receipt-"
        else:
            document = _latest_receipt(
                vault,
                "upgrade-receipt-",
                "plan_id",
                batch_id,
                None,
                _validate_upgrade_receipt,
            )
            id_key, prefix = "receipt_id", "upgrade-receipt-"
    except (ContractError, OSError):
        return None
    if document is None:
        return None
    receipt_id = document[id_key]
    return {
        "receipt_id": receipt_id,
        "path": str(vault / f"{prefix}{receipt_id}.json"),
        "status": document["payload"]["status"],
    }


def _batch_evidence(
    vault: Path,
    *,
    phase: str,
    plan_id: str | None,
    recovery_id: str | None,
    intent_prefix: str,
    id_field: str,
) -> dict[str, Any] | None:
    """Measured/unknown mutation evidence bound to persisted batch intents.

    Returns ``None`` when no intent and no checkpoint was ever persisted:
    the failure is pre-mutation and keeps the plain pre-write surface.
    """
    identity: dict[str, Any] = {}
    if plan_id is not None:
        identity["plan_id"] = plan_id
    if recovery_id is not None:
        identity["recovery_id"] = recovery_id
    try:
        intents = _scan_intents(vault, intent_prefix, id_field)
    except (ContractError, OSError):
        # A failed evidence scan must never mask the original halt.
        intents = None
    checkpoint = _latest_checkpoint(
        vault, phase=phase, plan_id=plan_id, recovery_id=recovery_id
    )
    if intents is None:
        return {
            "phase": phase,
            **identity,
            "backup_root": str(vault),
            "checkpoint": checkpoint,
            "mutation": {"state": "unknown", "resources": []},
        }
    if not intents and checkpoint is None:
        return None
    resources: list[dict[str, Any]] = []
    measured = True
    for key in sorted(intents):
        target = intents[key].get("target")
        after = _measured(target) if isinstance(target, str) else None
        if after is None:
            measured = False
        resources.append(
            {
                "id": key,
                "target": target if isinstance(target, str) else "",
                "after": after,
            }
        )
    return {
        "phase": phase,
        **identity,
        "backup_root": str(vault),
        "checkpoint": checkpoint,
        "mutation": {
            "state": "measured" if measured else "unknown",
            "resources": resources,
        },
    }


def _batch_halt(
    error: BaseException,
    vault: Path,
    *,
    phase: str,
    plan_id: str | None,
    recovery_id: str | None,
    intent_prefix: str,
    id_field: str,
) -> ContractError:
    """Post-mutation halt carrying batch evidence; pre-mutation stays plain."""
    batch = _batch_evidence(
        vault,
        phase=phase,
        plan_id=plan_id,
        recovery_id=recovery_id,
        intent_prefix=intent_prefix,
        id_field=id_field,
    )
    if batch is None:
        if isinstance(error, ContractError):
            return error
        return ContractError(
            "write-failed", "the batch failed before any mutation was persisted"
        )
    details: dict[str, Any] = {}
    if isinstance(error, ContractError):
        code, message = error.code, error.message
        if isinstance(error.details, Mapping):
            details.update(error.details)
    else:
        code, message = (
            "write-failed",
            "a post-mutation persistence failure interrupted the batch",
        )
    details["batch"] = batch
    return ContractError(code, message, exit_code=3, details=details)


def _isolated_batch_evidence(
    error: ContractError,
    vault: Path,
    *,
    phase: str,
    plan_id: str | None,
    recovery_id: str | None,
    intent_prefix: str,
    id_field: str,
) -> ContractError:
    """Bind batch evidence to an isolated executor crash; forward the rest."""
    if isinstance(error.details, Mapping) and "batch" in error.details:
        return error
    if error.code != "self-upgrade-failed":
        return error
    return _batch_halt(
        error,
        vault,
        phase=phase,
        plan_id=plan_id,
        recovery_id=recovery_id,
        intent_prefix=intent_prefix,
        id_field=id_field,
    )


# ---------------------------------------------------------------------------
# Self-upgrade staging and isolated execution
# ---------------------------------------------------------------------------


def _trusted_package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _purge_stage_caches(staged: Path) -> None:
    cache_names = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
    for directory, children, files in os.walk(staged, topdown=True, followlinks=False):
        parent = Path(directory)
        for name in list(children):
            if name in cache_names:
                target = parent / name
                remove_reference(target, snapshot(target), scope=staged)
                children.remove(name)
        for name in files:
            if name.endswith((".pyc", ".pyo")):
                target = parent / name
                remove_reference(target, snapshot(target), scope=staged)


def _stage_self_package(
    baseline: Mapping[str, Any], vault: Path, *, package: Path | None = None
) -> dict[str, Any]:
    """Complete validated copy of the current package inside the private vault.

    The sealed baseline source state binds execution:
    the live package and the staged copy must both match the recorded
    payload digest, so a source package changed since planning fails before
    anything runs. The staged directory name keys on that digest, which is
    stable under cache churn, so retries reuse the verified copy.
    """
    source = baseline["source"]
    package = _trusted_package_root() if package is None else package
    if snapshot(package)["type"] == "absent":
        _fail(
            "plan-stale",
            "the package source is missing since the plan was sealed",
        )
    if _payload_state(package) != source["state"]:
        _fail(
            "plan-stale", "the package source changed since the plan was sealed"
        )
    stage_root = _ensure_private_subdir(vault, "self")
    destination = stage_root / f"package-{source['state']['checksum']}"
    existing = snapshot(destination)
    reference: dict[str, Any]
    if existing["type"] == "absent":
        reference = backup_reference(
            {"path": str(package), "state": snapshot(package)},
            destination,
            private_root=vault,
        )
    else:
        reference = {"path": str(destination), "state": existing}
    staged = Path(reference["path"])
    _purge_stage_caches(staged)
    if _payload_state(staged) != source["state"]:
        _fail(
            "self-stage-conflict",
            "the staged package copy fails the baseline digest binding",
            exit_code=3,
        )
    runner = staged / "scripts" / "sbtd_upgrade.py"
    if snapshot(runner)["type"] != "file":
        _fail(
            "self-stage-invalid",
            "the staged package does not contain the upgrade runner",
            exit_code=3,
        )
    return {"path": str(staged), "state": snapshot(staged), "runner": runner}


def _scrubbed_env() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if key
        not in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONINSPECT")
    }


def _run_isolated(runner: Path, argv: list[str]) -> dict[str, Any]:
    bootstrap = (
        "import pathlib,runpy,sys;"
        "runner=sys.argv.pop(1);"
        "sys.path.insert(0,str(pathlib.Path(runner).parent));"
        "sys.argv[0]=runner;"
        "runpy.run_path(runner,run_name='__main__')"
    )
    command = [sys.executable, "-I", "-B", "-c", bootstrap, str(runner), *argv]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_scrubbed_env(),
            check=False,
        )
    except OSError:
        _fail(
            "self-upgrade-failed",
            "the isolated upgrade executor could not be started",
            exit_code=3,
        )
    output = completed.stdout.strip()
    document: Any = None
    if output:
        try:
            document = _strict_loads(output.encode("utf-8"))
        except ContractError:
            document = None
    if completed.returncode == 0:
        if not isinstance(document, dict) or "payload" not in document:
            _fail(
                "self-upgrade-failed",
                "the isolated upgrade executor returned no usable document",
                exit_code=3,
            )
        return document
    if isinstance(document, dict) and isinstance(document.get("error"), Mapping):
        error = document["error"]
        code = error.get("code")
        message = error.get("message")
        exit_code = error.get("exit_code")
        details = error.get("details")
        if (
            isinstance(code, str)
            and isinstance(message, str)
            and exit_code in (2, 3)
        ):
            raise ContractError(
                code,
                message,
                exit_code=exit_code,
                details=dict(details) if isinstance(details, Mapping) else None,
            )
    _fail(
        "self-upgrade-failed",
        "the isolated upgrade executor failed without a contract error",
        exit_code=3,
    )


# ---------------------------------------------------------------------------
# Parent directory creation (recorded for recovery)
# ---------------------------------------------------------------------------


def _missing_parents(target: Path) -> list[str]:
    """Parent-chain preflight: lstat/nofollow each component, never a tree scan.

    Only the target's own ancestry is inspected: unselected siblings are
    never read, while a linked, reparse or non-directory parent component
    is still refused.
    """
    parent = _canonical(target.parent)
    missing: list[str] = []
    current = parent
    while True:
        info = _lstat(current)
        if info is not None:
            break
        missing.append(str(current))
        if current.parent == current:
            break
        current = current.parent
    info = _lstat(current)
    if info is None or not stat.S_ISDIR(info.st_mode):
        _fail("unsafe-path", "an upgrade target parent is not a real directory")
    return list(reversed(missing))


def _ensure_parent_directories(target: Path) -> list[str]:
    """Create missing target parents top-down; returns the created directories."""
    created: list[str] = []
    for name in _missing_parents(target):
        try:
            os.mkdir(name, 0o755)
        except FileExistsError:
            continue
        except OSError:
            for cleanup in reversed(created):
                try:
                    os.rmdir(cleanup)
                except OSError:
                    pass
            _fail("write-failed", "an upgrade target parent cannot be created")
        created.append(name)
    return created


# ---------------------------------------------------------------------------
# plan_upgrade
# ---------------------------------------------------------------------------


def _require_isolated_dependencies() -> None:
    """Planning and execution must use the same isolated dependency environment."""
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-c",
             "import yaml, jsonschema, markdown_it, tomlkit, cryptography"],
            env=_scrubbed_env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        _fail("isolated-dependencies-unavailable", "prepare the declared dependencies in an isolated-capable interpreter")
    if result.returncode != 0:
        _fail("isolated-dependencies-unavailable", "prepare the declared dependencies in an isolated-capable interpreter")


def plan_upgrade(
    scope: Mapping[str, Any],
    backup_root: str | Path,
    *,
    package_root: str | Path | None = None,
) -> dict[str, Any]:
    """Read-only sealed upgrade plan. Writes nothing; the vault stays untouched."""
    sealed_scope = _canonical_scope(
        _validate_scope(_strict_loads(canonical_json_bytes(scope)))
    )
    vault = require_private_directory(Path(backup_root))
    _require_isolated_dependencies()
    root = None if package_root is None else Path(package_root)
    baseline, resources, domains = _derive_resources(sealed_scope, root)
    if paths_overlap(vault, Path(baseline["source"]["path"])):
        _fail("backup-root-overlap", "the backup root overlaps the package")
    _preflight_set(resources, vault)
    blocked = sorted(
        resource["id"] for resource in resources if resource["decision"] == "blocked"
    )
    payload = {
        "plan_schema": PLAN_SCHEMA,
        "status": "blocked" if blocked else "planned",
        "baseline": baseline,
        "scope": sealed_scope,
        "backup_root": str(vault),
        "resources": resources,
        "domains": domains,
        "blocked_resources": blocked,
    }
    return {"schema_version": 1, "plan_id": _digest(payload), "payload": payload}


def save_plan(
    plan: Mapping[str, Any],
    destination: str | Path,
    *,
    private_root: str | Path | None = None,
) -> dict[str, Any]:
    """Persist a sealed plan as a new immutable document inside the vault."""
    _plan_id, payload = _validate_plan(plan)
    root = (
        Path(private_root)
        if private_root is not None
        else Path(payload["backup_root"])
    )
    return save_document(Path(destination), plan, private_root=root)


def prepare_probe_link_authorization(
    plan: Mapping[str, Any],
    *,
    host_id: str,
    skill_path: str,
    target_path: str,
) -> dict[str, Any]:
    """Seal a precise linked-Skill probe authorization bound to this plan.

    The operator's explicit physical ``target_path`` is the required initial
    target access; nothing is written and no other target is read. See
    ``sbtd_probe_links`` for the exact binding and revalidation rules.
    """
    plan_id, payload = _validate_plan(plan)
    from sbtd_probe_links import prepare_link_authorization

    return prepare_link_authorization(
        plan_id=plan_id,
        hosts=payload["scope"].get("hosts") or [],
        host_id=host_id,
        skill_path=skill_path,
        target_path=target_path,
    )


# ---------------------------------------------------------------------------
# apply_upgrade
# ---------------------------------------------------------------------------


def _require_confirmation(confirmed: str | None, expected: str) -> None:
    if confirmed is None:
        _fail(
            "confirmation-required",
            "the phase requires an explicit confirmation of the sealed plan id",
        )
    if not isinstance(confirmed, str) or confirmed != expected:
        _fail(
            "confirmation-mismatch",
            "the confirmation does not match the sealed plan id",
        )


def apply_upgrade(
    plan: Mapping[str, Any],
    *,
    confirmed: str | None,
    receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Guarded apply via the staged, digest-bound isolated executor."""
    plan_id, payload = _validate_plan(plan)
    _require_confirmation(confirmed, plan_id)
    _require_isolated_dependencies()
    trusted = _trusted_package_root()
    if _payload_state(trusted) != payload["baseline"]["source"]["state"]:
        _fail("source-stale", "the running trusted package does not match the sealed baseline")
    vault = require_private_directory(Path(payload["backup_root"]))
    if paths_overlap(vault, trusted):
        _fail("backup-root-overlap", "the backup root overlaps the trusted package")
    baseline, recomputed, _domains = _derive_resources(
        payload["scope"], trusted, host_package_root=trusted
    )
    _check_plan_fresh(payload["resources"], recomputed, payload["baseline"], baseline)
    _preflight_set(payload["resources"], vault)
    _check_decisions(payload)
    previous: dict[str, Any] | None = None
    if receipt is not None:
        _validate_upgrade_receipt(receipt)
        _require_saved(vault / f"upgrade-receipt-{receipt['receipt_id']}.json", receipt)
        previous = dict(receipt)
    stage = _upgrade_execution_stage(plan, vault)
    plan_ref = _save_once(vault / f"upgrade-plan-{plan_id}.json", plan, vault)
    argv = [
        "--internal-apply",
        "--plan-id",
        plan_id,
        "--plan-file",
        plan_ref["path"],
    ]
    if previous is not None:
        previous_id = previous["receipt_id"]
        receipt_ref = _save_once(
            vault / f"upgrade-receipt-{previous_id}.json", previous, vault
        )
        argv += ["--receipt-file", receipt_ref["path"]]
    try:
        document = _run_isolated(stage["runner"], argv)
    except ContractError as error:
        raise _isolated_batch_evidence(
            error,
            vault,
            phase="upgrade",
            plan_id=plan_id,
            recovery_id=None,
            intent_prefix=f"intent-{plan_id[:16]}-",
            id_field="resource_id",
        ) from error
    _validate_upgrade_receipt(document)
    if document["payload"]["plan_id"] != plan_id:
        _fail(
            "self-upgrade-failed",
            "the isolated executor returned a receipt for a different plan",
            exit_code=3,
        )
    return document


def _upgrade_execution_stage(plan: Mapping[str, Any], vault: Path) -> dict[str, Any]:
    baseline = plan["payload"]["baseline"]
    if _payload_state(_trusted_package_root()) != baseline["source"]["state"]:
        _fail("source-stale", "the current trusted package changed; an old vault stage cannot authorize execution")
    return _stage_self_package(baseline, vault, package=_trusted_package_root())


def _apply_upgrade_local(
    plan: Mapping[str, Any],
    *,
    confirmed: str | None,
    receipt: Mapping[str, Any] | None,
    package_root: Path | None,
    executor_isolated: bool = False,
) -> dict[str, Any]:
    """In-process apply body; runs only inside the isolated staged executor."""
    plan_id, payload = _validate_plan(plan)
    _require_confirmation(confirmed, plan_id)
    _check_decisions(payload)
    vault = require_private_directory(Path(payload["backup_root"]))
    if receipt is not None:
        _validate_upgrade_receipt(receipt)
        _require_saved(vault / f"upgrade-receipt-{receipt['receipt_id']}.json", receipt)
        if receipt["payload"]["plan_id"] != plan_id:  # type: ignore[index]
            _fail("receipt-mismatch", "the receipt belongs to a different plan")
    inventory_root = _trusted_package_root() if executor_isolated else package_root
    baseline, recomputed, _domains = _derive_resources(
        payload["scope"], inventory_root, host_package_root=inventory_root
    )
    _check_plan_fresh(payload["resources"], recomputed, payload["baseline"], baseline)
    _preflight_set(payload["resources"], vault)
    _save_once(vault / f"upgrade-plan-{plan_id}.json", plan, vault)

    previous = _latest_receipt(
        vault,
        "upgrade-receipt-",
        "plan_id",
        plan_id,
        dict(receipt) if receipt is not None else None,
        _validate_upgrade_receipt,
    )
    prior_results: dict[str, dict[str, Any]] = {}
    previous_id: str | None = None
    sequence = 0
    if previous is not None:
        previous_id = previous["receipt_id"]
        sequence = previous["payload"]["sequence"] + 1
        for row in previous["payload"]["resources"]:
            if isinstance(row, Mapping) and isinstance(row.get("id"), str):
                prior_results[row["id"]] = dict(row)
    intents = _scan_intents(vault, f"intent-{plan_id[:16]}-", "resource_id")

    actions: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for resource in payload["resources"]:
        fresh = next(row for row in recomputed if row["id"] == resource["id"])
        continued = (
            prior_results.get(resource["id"], {}).get("result") in _COMPLETED_TOKENS
            or (previous is not None and resource["id"] in intents)
        )
        if not continued:
            if resource["before"] != fresh["before"]:
                _fail("state-conflict", "an initial target changed since planning")
            if any(resource[key] != fresh[key] for key in ("classification", "decision")):
                _fail("plan-stale", "initial consent differs from a fresh derivation")
        action = _reconcile_resource(
            resource, prior_results.get(resource["id"]), intents
        )
        if action["verb"] == "write":
            action["mechanical_before"] = snapshot(Path(resource["target"]))
            _missing_parents(Path(resource["target"]))
            action["created_parents"] = []
            actions.append(action)
        else:
            results.append(action["row"])

    write_ids = {action["resource"]["id"] for action in actions}
    for consumer in recomputed:
        if consumer["kind"] != "mcp" or consumer["id"] not in write_ids:
            continue
        digest = consumer["details"].get("onboard_payload_digest")
        if digest is None:
            continue
        root = Path(consumer["host"].get("onboard_root") or Path(consumer["details"]["launcher"]["path"]).parent.parent)
        goal = {"type": "directory", "checksum": digest}
        provider = next((row for row in recomputed if row["kind"] == "skill" and row["target"] == str(root)), None)
        if provider is not None and provider["id"] in write_ids:
            current_or_scheduled = provider["desired"] == goal
        else:
            current_or_scheduled = _payload_state(root) == goal
        if not current_or_scheduled:
            _fail("launcher-dependency-conflict", "align the selected Onboard installation before writing MCP")
    for consumer in recomputed:
        if consumer["kind"] == "shell" and consumer["id"] in write_ids:
            identity = consumer["details"]["command_identity"]
            command_paths = {identity["path"], identity.get("resolved")}
            if identity.get("shim") is not None:
                command_paths.add(identity["shim"]["target"])
            for command_path in command_paths - {None}:
                for action in actions:
                    if action["resource"]["id"] != consumer["id"] and paths_overlap(
                        Path(command_path), Path(action["resource"]["target"]),
                    ):
                        _fail(
                            "shell-dependency-conflict",
                            "align the selected shell command first, then re-plan its profile",
                        )
        for dependency in consumer["details"].get("effective_inputs", []):
            path = Path(_expect_abs_path(dependency["path"], "host dependency"))
            expected = _expect_state(dependency["state"], "host dependency state")
            if snapshot(path) != expected:
                _fail("state-conflict", "an inherited configuration source changed")
            for action in actions:
                provider = Path(action["resource"]["target"])
                if action["resource"]["id"] != consumer["id"] and paths_overlap(path, provider):
                    _fail(
                        "inherited-dependency-conflict",
                        "align the provider domain first, then re-plan the consumer against its measured state",
                    )
    # Preflight complete: take every original backup before the first write.
    intents_dir = _ensure_private_subdir(vault, "intents")
    originals_dir = _ensure_private_subdir(vault, "originals")
    batch_dir = originals_dir / plan_id[:16]
    if actions:
        require_private_directory(batch_dir, create=True)
    for action in actions:
        resource = action["resource"]
        backup_ref: dict[str, Any] | None = None
        if resource["before"]["type"] != "absent":
            backup_name = hashlib.sha256(
                resource["id"].encode("utf-8")
            ).hexdigest()[:32]
            backup_ref = backup_reference(
                {
                    "path": resource["target"],
                    "state": action["mechanical_before"],
                },
                batch_dir / backup_name,
                private_root=vault,
            )
        action["backup_ref"] = backup_ref

    recomputed_by_id = {resource["id"]: resource for resource in recomputed}
    executor = {
        "isolated": executor_isolated,
        "runner": str(Path(__file__).resolve()),
        "package_state": baseline["source"]["state"],
    }
    for action in actions:
        _record_result(results, _result_row(
            action["resource"], "pending", None, action["backup_ref"], action["created_parents"],
        ))
    try:
        initial_payload = _receipt_payload(
            plan_id, payload, vault, previous_id, sequence, results, None, executor
        )
        initial = _receipt_document(initial_payload, "receipt_id")
        _save_once(vault / f"upgrade-receipt-{initial['receipt_id']}.json", initial, vault)
        failure: dict[str, Any] | None = None
        stopped = False
        document: dict[str, Any] | None = None
        for action in actions:
            resource = action["resource"]
            if stopped:
                continue
            intent = {
                "intent_schema": "upgrade-write-intent",
                "plan_id": plan_id,
                "resource_id": resource["id"],
                "target": resource["target"],
                "before": resource["before"],
                "desired": resource["desired"],
                "backup_ref": action["backup_ref"],
                "mechanical_desired": (
                    snapshot(
                        Path(recomputed_by_id[resource["id"]]["source"]["path"])
                    )
                    if resource["kind"] in ("skill", "agents") else resource["desired"]
                ),
                "mechanical_before": action["mechanical_before"],
                "created_parents": action["created_parents"],
            }
            action["mechanical_desired"] = intent["mechanical_desired"]
            _save_once(
                intents_dir / f"intent-{plan_id[:16]}-{_digest(resource['id'])[:32]}.json",
                {"schema_version": 1, "payload": intent},
                vault,
            )
            try:
                created_parents = _ensure_parent_directories(Path(resource["target"]))
                action["created_parents"] = created_parents
                _write_resource(
                    resource,
                    recomputed_by_id[resource["id"]],
                    action["backup_ref"],
                    inventory_root,
                    action["mechanical_before"],
                    action,
                )
                after = _payload_state(Path(resource["target"]))
            except ContractError as error:
                _record_result(results,
                    _result_row(
                        resource,
                        "failed",
                        _measured(resource["target"]),
                        action["backup_ref"],
                        action["created_parents"],
                        reason=error.code,
                    )
                )
                failure = {"resource_id": resource["id"], "code": error.code}
                retained = getattr(error, "retained_refs", None)
                if retained:
                    failure["retained_refs"] = retained
                stopped = True
            except OSError:
                _record_result(results,
                    _result_row(
                        resource,
                        "failed",
                        _measured(resource["target"]),
                        action["backup_ref"],
                        action["created_parents"],
                        reason="write-failed",
                    )
                )
                failure = {"resource_id": resource["id"], "code": "write-failed"}
                stopped = True
            else:
                if after != resource["desired"]:
                    _record_result(results,
                        _result_row(
                            resource,
                            "failed",
                            after,
                            action["backup_ref"],
                            action["created_parents"],
                            reason="after-mismatch",
                        )
                    )
                    failure = {"resource_id": resource["id"], "code": "after-mismatch"}
                    stopped = True
                else:
                    _record_result(results,
                        _result_row(
                            resource,
                            "succeeded",
                            after,
                            action["backup_ref"],
                            action["created_parents"],
                        )
                    )
            row = next(row for row in results if row["id"] == resource["id"])
            if row["result"] == "failed":
                no_commit = not action.get("mutation_started") or row["reason"] in (
                    "state-conflict", "plan-stale", "render-drift", "invalid-inventory",
                )
                if no_commit or row["mechanical_after"] == action["mechanical_before"]:
                    row["mutated"] = False
                elif row["mechanical_after"] == intent["mechanical_desired"]:
                    row["mutated"] = True
                else:
                    row["mutated"] = None
            receipt_payload = _receipt_payload(
                plan_id, payload, vault, previous_id, sequence, results, failure, executor
            )
            document = _receipt_document(receipt_payload, "receipt_id")
            _save_once(
                vault / f"upgrade-receipt-{document['receipt_id']}.json", document, vault
            )

        receipt_payload = _receipt_payload(
            plan_id, payload, vault, previous_id, sequence, results, failure, executor
        )
        document = _receipt_document(receipt_payload, "receipt_id")
        _save_once(
            vault / f"upgrade-receipt-{document['receipt_id']}.json", document, vault
        )
    except (ContractError, OSError) as error:
        raise _batch_halt(
            error,
            vault,
            phase="upgrade",
            plan_id=plan_id,
            recovery_id=None,
            intent_prefix=f"intent-{plan_id[:16]}-",
            id_field="resource_id",
        ) from error
    return document


def _record_result(rows: list[dict[str, Any]], row: dict[str, Any]) -> None:
    key = "id" if "id" in row else "step_id"
    for index, previous in enumerate(rows):
        if previous[key] == row[key]:
            rows[index] = row
            return
    rows.append(row)


def _receipt_payload(
    plan_id: str,
    plan_payload: Mapping[str, Any],
    vault: Path,
    previous_id: str | None,
    sequence: int,
    results: list[dict[str, Any]],
    failure: dict[str, Any] | None,
    executor: Mapping[str, Any],
) -> dict[str, Any]:
    failed = any(row["result"] == "failed" for row in results)
    succeeded = any(row["result"] in _COMPLETED_TOKENS for row in results)
    if failed and succeeded:
        status = "partial"
    elif failed:
        status = "failed"
    elif any(row["result"] == "pending" for row in results):
        status = "partial"
    else:
        status = "complete"
    return {
        "receipt_schema": RECEIPT_SCHEMA,
        "plan_id": plan_id,
        "baseline_id": plan_payload["baseline"]["baseline_id"],
        "backup_root": str(vault),
        "previous_receipt_id": previous_id,
        "sequence": sequence,
        "status": status,
        "executor": dict(executor),
        "resources": list(results),
        "failure": failure,
    }


def _measured(target: str) -> dict[str, Any] | None:
    try:
        return _payload_state(Path(target))
    except (ContractError, OSError):
        return None


def _mechanical_measured(target: str) -> dict[str, Any] | None:
    try:
        return snapshot(Path(target))
    except (ContractError, OSError):
        return None


def _result_row(
    resource: Mapping[str, Any],
    result: str,
    after: dict[str, Any] | None,
    backup_ref: dict[str, Any] | None,
    created_parents: list[str] | None,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    if result not in _RESULT_TOKENS:
        _fail("invalid-argument", "unknown resource result token")
    return {
        "id": resource["id"],
        "kind": resource["kind"],
        "target": resource["target"],
        "decision": resource["decision"],
        "result": result,
        "before": resource["before"],
        "desired": resource["desired"],
        "after": after,
        "mechanical_after": _mechanical_measured(resource["target"]) if after is not None else None,
        "mechanical_before": backup_ref["state"] if backup_ref is not None else dict(_ABSENT),
        "backup_ref": backup_ref,
        "created_parents": list(created_parents or []),
        "reason": reason,
        "mutated": result in _COMPLETED_TOKENS,
    }


def _reconcile_resource(
    resource: dict[str, Any],
    prior: dict[str, Any] | None,
    intents: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    """Decide write/skip/keep per resource, or reject unknown live state."""
    live = _payload_state(Path(resource["target"]))
    mechanical = snapshot(Path(resource["target"]))
    decision = resource["decision"]
    if decision in ("keep", "preserve"):
        if live != resource["before"]:
            _fail("state-conflict", "a kept or preserved target changed since planning")
        token = "kept" if decision == "keep" else "preserved"
        return {
            "verb": "record",
            "row": _result_row(resource, token, live, None, None),
        }
    if prior is not None and prior.get("result") in _COMPLETED_TOKENS:
        backup = prior.get("backup_ref")
        if backup is not None and snapshot(Path(backup["path"])) != backup["state"]:
            _fail("preservation-failed", "an original backup changed before retry", exit_code=3)
        semantic_retry = resource["kind"] in ("skill", "agents")
        if live == resource["desired"] == prior.get("after") and (
            semantic_retry or mechanical == prior.get("mechanical_after")
        ):
            # Never adopt cache churn as batch-owned recovery content.
            return {"verb": "record", "row": {**prior, "result": "skipped-complete"}}
        _fail(
            "state-conflict",
            "a completed resource no longer matches its receipt outcome",
        )
    if (
        prior is not None and prior.get("result") != "pending"
        and prior.get("mutated") is False and live != resource["before"]
    ):
        _fail("state-conflict", "a proven unwritten target changed outside this batch")
    intent = intents.get(resource["id"])
    if intent is not None:
        if intent.get("before") != resource["before"] or intent.get(
            "desired"
        ) != resource["desired"]:
            _fail("corrupt-evidence", "a vault intent contradicts the sealed plan")
        if live == resource["desired"]:
            if mechanical != intent.get("mechanical_desired"):
                _fail("state-conflict", "an interrupted target contains unmeasured changes")
            backup_ref = intent.get("backup_ref")
            if backup_ref is not None and (
                snapshot(Path(backup_ref["path"])) != backup_ref["state"]
            ):
                _fail(
                    "preservation-failed",
                    "an original backup no longer matches its recorded state",
                    exit_code=3,
                )
            return {
                "verb": "record",
                "row": _result_row(resource, "reconciled", live, backup_ref, intent.get("created_parents", [])),
            }
        if live != resource["before"]:
            _fail(
                "state-conflict",
                "an interrupted write left an unknown live state; reconcile manually",
            )
        return {"verb": "write", "resource": resource}
    if live != resource["before"]:
        _fail(
            "state-conflict",
            "an upgrade target changed since the plan was sealed",
        )
    return {"verb": "write", "resource": resource}


def _write_resource(
    sealed: Mapping[str, Any],
    fresh: Mapping[str, Any],
    backup_ref: dict[str, Any] | None,
    package_root: Path | None,
    expected: Mapping[str, Any],
    mutation: dict[str, Any],
) -> None:
    target = Path(sealed["target"])
    scope = target.parent
    if _payload_state(target) != sealed["before"] or snapshot(target) != expected:
        _fail("state-conflict", "a target changed immediately before its write")
    if sealed["kind"] in ("mcp", "shell"):
        content = _hosts_module().render_resource(fresh, package_root=package_root)
        if not isinstance(content, (bytes, bytearray)):
            _fail("invalid-inventory", "rendered host content must be bytes")
        if _bytes_digest(bytes(content)) != sealed["desired"]["checksum"]:
            _fail(
                "render-drift",
                "freshly rendered host content differs from the sealed desired state",
            )
        mutation["mutation_started"] = True
        write_file(
            target, bytes(content), expected, scope=scope
        )
        return
    source_path = Path(fresh["source"]["path"])
    if _payload_state(source_path) != sealed["desired"]:
        _fail(
            "plan-stale",
            "a payload source changed since the plan was sealed",
        )
    mutation["mutation_started"] = True
    install_reference(
        {"path": str(source_path), "state": mutation["mechanical_desired"]},
        target,
        expected,
        scope=scope,
        backup_ref=backup_ref,
    )


# ---------------------------------------------------------------------------
# verify_upgrade
# ---------------------------------------------------------------------------


def _validate_link_authorizations(
    link_authorizations: Sequence[Mapping[str, Any]] | None,
    *,
    plan_id: str,
    payload: Mapping[str, Any],
    probe: bool,
) -> list[dict[str, Any]] | None:
    """Bind precise linked-Skill authorizations to this plan before any probe."""
    if link_authorizations is None:
        return None
    if not probe:
        _fail(
            "invalid-argument",
            "link authorizations are only meaningful for an explicit probe verification",
        )
    if isinstance(link_authorizations, (str, bytes)) or not isinstance(
        link_authorizations, Sequence
    ):
        _fail("invalid-argument", "link authorizations must be a sequence of documents")
    from sbtd_probe_links import validate_link_authorization

    hosts = payload["scope"].get("hosts") or []
    sealed = []
    for document in link_authorizations:
        sealed_payload = validate_link_authorization(document, plan_id=plan_id, hosts=hosts)
        sealed.append(
            {
                "authorization_id": document["authorization_id"],
                "payload": sealed_payload,
            }
        )
    seen: set[tuple[str, str]] = set()
    for item in sealed:
        key = (item["payload"]["host_id"], os.path.normpath(item["payload"]["skill_path"]))
        if key in seen:
            _fail(
                "authorization-conflict",
                "duplicate link authorizations for one host and Skill path",
            )
        seen.add(key)
    return sealed


def verify_upgrade(
    plan: Mapping[str, Any],
    *,
    receipt: Mapping[str, Any] | None = None,
    probe: bool = False,
    link_authorizations: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Read-only verification: managed payload state plus separate host evidence."""
    plan_id, payload = _validate_plan(plan)
    vault = require_private_directory(Path(payload["backup_root"]))
    stored = vault / f"upgrade-plan-{plan_id}.json"
    if snapshot(stored)["type"] == "file":
        _require_saved(stored, plan)
    else:
        fresh_baseline, fresh_resources, _domains = _derive_resources(payload["scope"], None)
        sealed_files = [row for row in payload["resources"] if row["kind"] in ("skill", "agents")]
        fresh_files = [row for row in fresh_resources if row["kind"] in ("skill", "agents")]
        _check_plan_fresh(sealed_files, fresh_files, payload["baseline"], fresh_baseline)
    receipt_rows: dict[str, dict[str, Any]] = {}
    receipt_id: str | None = None
    if receipt is not None:
        receipt_id, receipt_payload = _validate_upgrade_receipt(receipt)
        if receipt_payload["plan_id"] != plan_id:
            _fail("receipt-mismatch", "the receipt belongs to a different plan")
        for row in receipt_payload["resources"]:
            if isinstance(row, Mapping) and isinstance(row.get("id"), str):
                receipt_rows[row["id"]] = dict(row)
    if not isinstance(probe, bool):
        _fail("invalid-argument", "probe must be a boolean")
    sealed_links = _validate_link_authorizations(
        link_authorizations, plan_id=plan_id, payload=payload, probe=probe
    )
    hosts_report = _hosts_module().verify_hosts(
        payload["scope"], package_root=None, probe=probe, link_authorizations=sealed_links
    )
    if not isinstance(hosts_report, Mapping):
        _fail("invalid-inventory", "host verification must return an object")

    resources: list[dict[str, Any]] = []
    exceptions: list[str] = []
    drifted = False
    blocked = False
    if probe:
        normalize_platform = getattr(
            _inventory_module(), "normalize_host_platform", None
        )
        if normalize_platform is None:
            _fail(
                "inventory-unavailable",
                "the upgrade inventory module does not expose platform normalization",
            )
        required_hosts = {
            host["id"] for host in payload["scope"].get("hosts", [])
            if normalize_platform(host["platform"]) in ("codex", "omp")
        }
        reported_hosts = {
            row.get("id") for row in hosts_report.get("hosts", []) if isinstance(row, Mapping)
        }
        required_profiles = {
            str(Path(profile["path"])) for profile in payload["scope"].get("shell_profiles", [])
        }
        reported_profiles = {
            str(Path(row["path"])) for row in hosts_report.get("shell_profiles", [])
            if isinstance(row, Mapping) and isinstance(row.get("path"), str)
        }
        blocked = bool(required_hosts - reported_hosts or required_profiles - reported_profiles)
        blocked = blocked or any(
            row.get("id") in required_hosts and row.get("applicability", "supported") != "supported"
            for row in hosts_report.get("hosts", []) if isinstance(row, Mapping)
        )
    for resource in payload["resources"]:
        row = _verify_resource(resource, receipt_rows.get(resource["id"]))
        resources.append(row)
        if row["result"] == "preserved":
            exceptions.append(row["id"])
        elif row["result"] in ("drift", "missing"):
            drifted = True
        elif row["result"] == "blocked":
            blocked = True
    host_verdict, host_exceptions = _host_verdict(hosts_report, probe=probe)
    if host_verdict == "blocked":
        blocked = True
    elif host_verdict == "drift":
        drifted = True
    for resource_id in host_exceptions:
        if resource_id not in exceptions:
            exceptions.append(resource_id)

    if blocked:
        status = "blocked"
    elif drifted:
        status = "drift"
    elif exceptions:
        status = "exceptions"
    else:
        status = "aligned"
    verification_payload = {
        "verification_schema": VERIFICATION_SCHEMA,
        "plan_id": plan_id,
        "receipt_id": receipt_id,
        "baseline_id": payload["baseline"]["baseline_id"],
        "status": status,
        "probe": probe,
        "resources": resources,
        "exceptions": exceptions,
        "domains": payload["domains"],
        "hosts": dict(hosts_report),
    }
    return {
        "schema_version": 1,
        "status": status,
        "verification_id": _digest(verification_payload),
        "payload": verification_payload,
    }


def _verify_resource(
    resource: Mapping[str, Any], receipt_row: dict[str, Any] | None
) -> dict[str, Any]:
    base = {
        "id": resource["id"],
        "kind": resource["kind"],
        "target": resource["target"],
        "classification": resource["classification"],
        "decision": resource["decision"],
        "desired": resource["desired"],
    }
    if resource["decision"] == "blocked":
        return {
            **base,
            "measured": _measured(resource["target"]),
            "result": "blocked",
            "reason": "decision-blocked",
        }
    if resource["kind"] in ("mcp", "shell"):
        # Host configuration is semantically compared by verify_hosts; the
        # whole-file digest is recorded but never alone decides alignment,
        # so unrelated user additions after the upgrade stay aligned.
        return {
            **base,
            "measured": _measured(resource["target"]),
            "result": "preserved" if resource["decision"] == "preserve" else "host-managed",
            "reason": None,
        }
    try:
        measured = _payload_state(Path(resource["target"]))
    except ContractError as error:
        return {
            **base,
            "measured": None,
            "result": "blocked",
            "reason": error.code,
        }
    result: str
    reason: str | None = None
    if resource["decision"] == "preserve":
        result = "preserved"
    elif measured == resource["desired"]:
        result = "aligned"
    elif measured["type"] == "absent":
        result = "missing"
    else:
        result = "drift"
        if measured == resource["before"]:
            reason = "not-applied"
    if (
        receipt_row is not None
        and receipt_row.get("result") in _COMPLETED_TOKENS
        and measured != receipt_row.get("after")
    ):
        result = "drift"
        reason = "receipt-outcome-diverged"
    return {**base, "measured": measured, "result": result, "reason": reason}


def _host_verdict(
    report: Mapping[str, Any], *, probe: bool = False
) -> tuple[str | None, list[str]]:
    """Readonly alignment is disk-only; explicitly requested probes must finish."""
    blocked = False
    failed = False
    exceptions: list[str] = []

    def status(value: Any) -> str | None:
        token = value.get("status") if isinstance(value, Mapping) else value
        return token if isinstance(token, str) else None

    for collection in ("hosts", "shell_profiles"):
        rows = report.get(collection, [])
        for entry in rows:
            if not isinstance(entry, Mapping):
                blocked = True
                continue
            disk_record = entry.get("disk")
            disk = status(disk_record)
            decision = disk_record.get("decision") if isinstance(disk_record, Mapping) else entry.get("decision")
            if disk == "blocked":
                blocked = True
            elif disk in ("drifted", "missing"):
                if decision == "preserve":
                    identifier = entry.get("id", entry.get("path"))
                    if isinstance(identifier, str):
                        exceptions.append(identifier)
                else:
                    failed = True
            if entry.get("applicability") == "unsupported":
                continue
            required: list[str | None] = []
            if collection == "hosts":
                required.append(status(entry.get("runtime")))
            host = entry.get("host")
            checks = host.get("checks") if isinstance(host, Mapping) else None
            if isinstance(checks, Mapping):
                keys = ("binding", "protocol", "host_load", "skills") if collection == "hosts" else ("command_resolution",)
                required.extend(status(checks.get(key)) for key in keys)
            else:
                required.append(status(host))
            if "failed" in required:
                failed = True
            elif probe and any(token != "verified" for token in required):
                blocked = True
            # live_reload and legacy are separate, nonrequested dimensions.
    # Blocked evidence always outranks drift: one blocked domain must never
    # be hidden by another domain's drift, and per-domain rows stay intact.
    return ("blocked" if blocked else "drift" if failed else None), exceptions


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------


def _require_saved(path: Path, document: Mapping[str, Any]) -> None:
    if canonical_json_bytes(_load_document_file(path)) != canonical_json_bytes(document):
        _fail("evidence-mismatch", "a document differs from the immutable vault evidence")


def _cacheless_mechanical_state(path: Path) -> dict[str, Any]:
    state = snapshot(path)
    if state["type"] != "directory":
        return state
    _state, entries = directory_snapshot(path)
    caches = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
    payload_entries = [
        entry for entry in entries
        if not any(part in caches for part in Path(entry["path"]).parts)
        and not (entry["type"] == "file" and entry["path"].endswith((".pyc", ".pyo")))
    ]
    return {"type": "directory", "checksum": _digest(payload_entries)}


def _authorize_recovery_evidence(
    plan: Mapping[str, Any], receipt: Mapping[str, Any], vault: Path
) -> None:
    """Writable JSON is evidence, never authority: rederive trusted goals first."""
    payload = plan["payload"]
    trusted = _trusted_package_root()
    source = Path(payload["baseline"]["source"]["path"])
    isolated = trusted.parent == vault / "self"
    if not isolated and _payload_state(trusted) != payload["baseline"]["source"]["state"]:
        _fail("source-stale", "recovery source is not an equivalent running trusted package")
    baseline, fresh, _domains = _derive_resources(
        payload["scope"], trusted, host_package_root=trusted
    )
    if baseline["baseline_id"] != payload["baseline"]["baseline_id"] or baseline["source"]["state"] != payload["baseline"]["source"]["state"]:
        _fail("source-stale", "the trusted recovery package no longer matches the batch baseline")
    expected = {row["id"]: row for row in fresh}
    sealed = {row["id"]: row for row in payload["resources"]}
    if set(expected) != set(sealed):
        _fail("plan-stale", "recovery resource identities do not derive from the trusted catalog")
    _check_decisions(payload)
    for identifier, resource in sealed.items():
        actual = _identity_view(resource, str(source))
        derived = _identity_view(expected[identifier], baseline["source"]["path"])
        if resource["kind"] in ("mcp", "shell"):
            # Bind managed intent independently from unrelated live file bytes.
            actual["desired"] = derived["desired"] = None
            actual["managed_goal"] = resource["details"].get("managed_digest")
            derived["managed_goal"] = expected[identifier]["details"].get("managed_digest")
        if actual != derived:
            _fail("plan-stale", "recovery content or source pins do not derive from the trusted package")
    intents = _scan_intents(vault, f"intent-{plan['plan_id'][:16]}-", "resource_id")
    checkpoints = _scan_documents(vault, "upgrade-receipt-")
    initial_rows: set[str] = set()
    for document in checkpoints:
        _identifier, checkpoint = _validate_upgrade_receipt(document)
        if checkpoint["plan_id"] == plan["plan_id"]:
            for item in checkpoint["resources"]:
                if item["result"] == "pending" and item["after"] is None:
                    initial_rows.add(_digest([
                        item["id"], item["before"], item["desired"], item.get("backup_ref"),
                    ]))
    for row in receipt["payload"]["resources"]:
        if row.get("mutated") is False and row.get("result") != "pending":
            continue
        resource = sealed.get(row["id"])
        intent = intents.get(row["id"])
        if resource is None or resource["decision"] not in _WRITABLE:
            _fail("receipt-mismatch", "recovery row has no permitted catalog write")
        if intent is None:
            if row["result"] == "pending":
                continue
            _fail("intent-missing", "recovery requires the bound write intent")
        if intent.get("plan_id") != plan["plan_id"] or intent.get("resource_id") != row["id"] or any(
            intent.get(key) != resource.get(key) for key in ("target", "before", "desired")
        ):
            _fail("intent-mismatch", "recovery intent contradicts the canonical write")
        canonical_goal = (
            _cacheless_mechanical_state(Path(expected[row["id"]]["source"]["path"]))
            if resource["kind"] in ("skill", "agents") else resource["desired"]
        )
        if intent.get("mechanical_desired") != canonical_goal:
            _fail("intent-mismatch", "intent goal does not match trusted payload bytes")
        if row.get("mutated") is True and (
            row.get("after") != resource["desired"]
            or row.get("mechanical_after") != canonical_goal
        ):
            _fail("receipt-mismatch", "a completed write does not match its intended canonical goal")
        initial = _digest([
            row["id"], resource["before"], resource["desired"], intent.get("backup_ref"),
        ]) in initial_rows
        if not initial:
            _fail("checkpoint-missing", "recovery requires a bound pre-write checkpoint")
        backup = intent.get("backup_ref")
        if resource["before"]["type"] != "absent":
            name = hashlib.sha256(row["id"].encode("utf-8")).hexdigest()[:32]
            if backup is None or Path(backup["path"]) != vault / "originals" / plan["plan_id"][:16] / name:
                _fail("preservation-failed", "recovery original has no authorized backup", exit_code=3)
            if snapshot(Path(backup["path"])) != backup["state"] or _payload_state(Path(backup["path"])) != resource["before"]:
                _fail("preservation-failed", "recovery backup differs from the original pre-state", exit_code=3)
        if row.get("backup_ref") != backup or intent.get("mechanical_before") != row.get("mechanical_before"):
            _fail("receipt-mismatch", "receipt preservation evidence differs from its intent")


def _check_recovery_binding(recovery_plan: Mapping[str, Any]) -> None:
    payload = recovery_plan["payload"]
    original = payload.get("upgrade_plan")
    receipt = payload.get("upgrade_receipt")
    if not isinstance(original, Mapping) or not isinstance(receipt, Mapping):
        _fail("evidence-missing", "recovery requires its bound upgrade evidence")
    expected = _plan_recovery(
        original, receipt,
        observed_ids={step["resource_id"] for step in payload["steps"]},
    )["payload"]
    vault = Path(payload["backup_root"])
    recovery_id = recovery_plan["recovery_id"]
    previous = _latest_receipt(
        vault, "upgrade-recovery-receipt-", "recovery_id", recovery_id,
        None, _validate_recovery_receipt,
    )
    outcomes = {
        row["step_id"]: row for row in previous["payload"]["steps"]
    } if previous is not None else {}
    intents = _scan_intents(vault, f"rintent-{recovery_id[:16]}-", "step_id")
    for step in expected["steps"]:
        # A blocked attribution or missing backup is never a retry exception.
        if step["reason"] != "live-drift":
            continue
        measured = snapshot(Path(step["target"]))
        goal = dict(_ABSENT) if step["action"] == "remove" else step["backup_ref"]["state"]
        prior = outcomes.get(step["step_id"])
        intent = intents.get(step["step_id"])
        if intent is not None and any(
            intent.get(key) != step.get(key)
            for key in ("target", "action", "expected_current", "restore_state")
        ):
            _fail("intent-mismatch", "recovery continuation intent contradicts its step")
        receipt_proof = (
            prior is not None and prior["result"] in _COMPLETED_TOKENS
            and prior.get("mechanical_after") == measured == goal
        )
        intent_proof = intent is not None and (
            measured == goal or (step["action"] == "restore" and measured["type"] == "absent")
        )
        if receipt_proof or intent_proof:
            step["status"] = "actionable"
            step["reason"] = None
    expected["status"] = "blocked" if any(step["status"] == "blocked" for step in expected["steps"]) else "planned"
    if payload != expected:
        _fail("plan-stale", "recovery effects or eligibility differ from the trusted evidence")


def plan_recovery(
    plan: Mapping[str, Any], receipt: Mapping[str, Any]
) -> dict[str, Any]:
    """Read-only recovery plan over measured writes, including interrupted intents."""
    _require_isolated_dependencies()
    return _plan_recovery(plan, receipt)


def _recovery_rows(
    plan: Mapping[str, Any], receipt: Mapping[str, Any], observed_ids: set[str] | None
) -> list[dict[str, Any]]:
    payload = plan["payload"]
    vault = Path(payload["backup_root"])
    intents = _scan_intents(vault, f"intent-{plan['plan_id'][:16]}-", "resource_id")
    resources = {resource["id"]: resource for resource in payload["resources"]}
    latest = _latest_receipt(
        vault, "upgrade-receipt-", "plan_id", plan["plan_id"],
        dict(receipt), _validate_upgrade_receipt,
    )
    latest_rows = {
        row["id"]: row for row in latest["payload"]["resources"]
    } if latest is not None else {}
    rows: list[dict[str, Any]] = []
    for original in receipt["payload"]["resources"]:
        row = dict(original)
        intent = intents.get(row["id"])
        later = latest_rows.get(row["id"])
        if (
            row["result"] == "pending" and later is not None
            and later["result"] != "pending" and later.get("mutated") is False
        ):
            rows.append(dict(later))
            continue
        if row["result"] == "pending" and intent is not None:
            resource = resources.get(row["id"])
            if resource is None or any(
                intent.get(key) != resource.get(key) for key in ("target", "before", "desired")
            ) or intent.get("plan_id") != plan["plan_id"]:
                _fail("corrupt-evidence", "an interruption intent leaves the sealed resource set")
            measured = snapshot(Path(row["target"]))
            observed = measured == intent["mechanical_desired"]
            if observed or (observed_ids is not None and row["id"] in observed_ids):
                row.update({
                    "result": "reconciled", "after": resource["desired"],
                    "mutated": True,
                    "mechanical_after": intent["mechanical_desired"],
                    "mechanical_before": intent["mechanical_before"],
                    "backup_ref": intent["backup_ref"],
                    "created_parents": intent.get("created_parents", []),
                })
            elif measured != intent["mechanical_before"]:
                row.update({
                    "result": "failed", "after": _measured(row["target"]),
                    "mutated": None, "mechanical_after": measured,
                    "mechanical_before": intent["mechanical_before"],
                    "backup_ref": intent["backup_ref"],
                    "created_parents": intent.get("created_parents", []),
                    "reason": "unattributed-outcome",
                })
        rows.append(row)
    return rows


def _plan_recovery(
    plan: Mapping[str, Any], receipt: Mapping[str, Any], *, observed_ids: set[str] | None = None
) -> dict[str, Any]:
    plan_id, plan_payload = _validate_plan(plan)
    receipt_id, receipt_payload = _validate_upgrade_receipt(receipt)
    if receipt_payload["plan_id"] != plan_id:
        _fail("receipt-mismatch", "the receipt belongs to a different plan")
    vault = require_private_directory(Path(plan_payload["backup_root"]))
    _require_saved(vault / f"upgrade-plan-{plan_id}.json", plan)
    _require_saved(vault / f"upgrade-receipt-{receipt_id}.json", receipt)
    _authorize_recovery_evidence(plan, receipt, vault)
    allowed = {resource["id"]: resource for resource in plan_payload["resources"]}
    steps: list[dict[str, Any]] = []
    blocked = False
    for row in _recovery_rows(plan, receipt, observed_ids):
        if not isinstance(row, Mapping):
            _fail("corrupt-evidence", "a receipt resource row is malformed")
        if row.get("result") not in ("succeeded", "reconciled", "skipped-complete", "failed"):
            continue
        if row.get("mutated") is False:
            continue
        if row.get("after") is None or row.get("mechanical_after") is None:
            _fail("unmeasured-outcome", "recovery cannot authorize an unmeasured resource outcome")
        if row.get("mechanical_after") == row.get("mechanical_before"):
            continue
        resource = allowed.get(row.get("id"))
        if resource is None or any(
            row.get(key) != resource.get(key) for key in ("kind", "target", "before", "desired", "decision")
        ):
            _fail("receipt-mismatch", "a receipt row is outside the sealed resource set")
        resource_id = row["id"]
        target = row["target"]
        live = _payload_state(Path(target))
        step_id = _digest(["upgrade-recovery-step", plan_id, receipt_id, resource_id])
        base = {
            "step_id": step_id,
            "resource_id": resource_id,
            "kind": row["kind"],
            "target": target,
            "expected_current": row["after"],
            "created_parents": list(row.get("created_parents", [])),
            "expected_mechanical": row["mechanical_after"],
        }
        was_present = row["before"]["type"] != "absent"
        if row.get("mutated") is not True:
            steps.append({
                **base, "action": "restore" if was_present else "remove",
                "restore_state": row["before"] if was_present else None,
                "backup_ref": row.get("backup_ref"), "status": "blocked",
                "reason": "unattributed-outcome",
            })
            blocked = True
            continue
        if live != row["after"] or snapshot(Path(target)) != row["mechanical_after"]:
            steps.append(
                {
                    **base,
                    "action": "restore" if was_present else "remove",
                    "restore_state": row["before"] if was_present else None,
                    "backup_ref": row.get("backup_ref"),
                    "status": "blocked",
                    "reason": "live-drift",
                }
            )
            blocked = True
            continue
        if not was_present:
            steps.append(
                {
                    **base,
                    "action": "remove",
                    "restore_state": None,
                    "backup_ref": None,
                    "status": "actionable",
                    "reason": None,
                }
            )
            continue
        backup_ref = row.get("backup_ref")
        if backup_ref is not None:
            backup_name = hashlib.sha256(resource_id.encode("utf-8")).hexdigest()[:32]
            if Path(backup_ref["path"]) != vault / "originals" / plan_id[:16] / backup_name:
                _fail("receipt-mismatch", "an original backup has an unauthorized path")
        if backup_ref is None or (
            snapshot(Path(backup_ref["path"])) != backup_ref["state"]
        ):
            steps.append(
                {
                    **base,
                    "action": "restore",
                    "restore_state": row["before"],
                    "backup_ref": backup_ref,
                    "status": "blocked",
                    "reason": "backup-missing",
                }
            )
            blocked = True
            continue
        steps.append(
            {
                **base,
                "action": "restore",
                "restore_state": row["before"],
                "backup_ref": backup_ref,
                "status": "actionable",
                "reason": None,
            }
        )
    payload = {
        "recovery_schema": RECOVERY_PLAN_SCHEMA,
        "plan_id": plan_id,
        "receipt_id": receipt_id,
        "backup_root": str(vault),
        "status": "blocked" if blocked else "planned",
        "steps": steps,
        "upgrade_plan": dict(plan),
        "upgrade_receipt": dict(receipt),
    }
    return {"schema_version": 1, "recovery_id": _digest(payload), "payload": payload}


def apply_recovery(
    recovery_plan: Mapping[str, Any],
    *,
    confirmed: str | None,
    receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Guarded recovery via the staged, digest-bound isolated executor."""
    recovery_id, payload = _validate_recovery_plan(recovery_plan)
    _require_confirmation(confirmed, recovery_id)
    _require_isolated_dependencies()
    if payload["status"] != "planned" or any(
        step["status"] != "actionable" for step in payload["steps"]
    ):
        _fail(
            "blocked-recovery-step",
            "the recovery plan seals blocked steps; reconcile and re-plan first",
        )
    vault = require_private_directory(Path(payload["backup_root"]))
    _check_recovery_binding(recovery_plan)
    previous: dict[str, Any] | None = None
    if receipt is not None:
        _validate_recovery_receipt(receipt)
        _require_saved(vault / f"upgrade-recovery-receipt-{receipt['recovery_receipt_id']}.json", receipt)
        previous = dict(receipt)
    stage = _stage_self_package(
        _recovery_executor_baseline(), vault
    )
    plan_ref = _save_once(
        vault / f"upgrade-recovery-plan-{recovery_id}.json", recovery_plan, vault
    )
    argv = [
        "--internal-apply-recovery",
        "--recovery-id",
        recovery_id,
        "--plan-file",
        plan_ref["path"],
    ]
    if previous is not None:
        previous_id = previous["recovery_receipt_id"]
        receipt_ref = _save_once(
            vault / f"upgrade-recovery-receipt-{previous_id}.json", previous, vault
        )
        argv += ["--receipt-file", receipt_ref["path"]]
    try:
        document = _run_isolated(stage["runner"], argv)
    except ContractError as error:
        raise _isolated_batch_evidence(
            error,
            vault,
            phase="recovery",
            plan_id=payload["plan_id"],
            recovery_id=recovery_id,
            intent_prefix=f"rintent-{recovery_id[:16]}-",
            id_field="step_id",
        ) from error
    _validate_recovery_receipt(document)
    if document["payload"]["recovery_id"] != recovery_id:
        _fail(
            "self-upgrade-failed",
            "the isolated executor returned a receipt for a different plan",
            exit_code=3,
        )
    return document


def _recovery_executor_baseline() -> dict[str, Any]:
    """Current running package as the recovery executor source.

    Recovery binds the sealed upgrade batch, not a package baseline; the
    staged executor copy is still a complete verified private copy.
    """
    package = _trusted_package_root()
    return {
        "baseline_id": "recovery-executor",
        "source": {"path": str(package), "state": _payload_state(package)},
    }


def _apply_recovery_local(
    recovery_plan: Mapping[str, Any],
    *,
    confirmed: str | None,
    receipt: Mapping[str, Any] | None,
    package_root: Path | None,
    executor_isolated: bool = False,
) -> dict[str, Any]:
    recovery_id, payload = _validate_recovery_plan(recovery_plan)
    _require_confirmation(confirmed, recovery_id)
    if payload["status"] != "planned" or any(
        step["status"] != "actionable" for step in payload["steps"]
    ):
        _fail(
            "blocked-recovery-step",
            "the recovery plan seals blocked steps; reconcile and re-plan first",
        )
    vault = require_private_directory(Path(payload["backup_root"]))
    _check_recovery_binding(recovery_plan)
    if receipt is not None:
        _validate_recovery_receipt(receipt)
        _require_saved(vault / f"upgrade-recovery-receipt-{receipt['recovery_receipt_id']}.json", receipt)
        if receipt["payload"]["recovery_id"] != recovery_id:  # type: ignore[index]
            _fail(
                "receipt-mismatch",
                "the receipt belongs to a different recovery plan",
            )

    previous = _latest_receipt(
        vault,
        "upgrade-recovery-receipt-",
        "recovery_id",
        recovery_id,
        dict(receipt) if receipt is not None else None,
        _validate_recovery_receipt,
    )
    prior_steps: dict[str, dict[str, Any]] = {}
    previous_id: str | None = None
    sequence = 0
    if previous is not None:
        previous_id = previous["recovery_receipt_id"]
        sequence = previous["payload"]["sequence"] + 1
        for row in previous["payload"]["steps"]:
            if isinstance(row, Mapping) and isinstance(row.get("step_id"), str):
                prior_steps[row["step_id"]] = dict(row)
    intents = _scan_intents(vault, f"rintent-{recovery_id[:16]}-", "step_id")

    actions: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for step in payload["steps"]:
        action = _reconcile_step(step, prior_steps.get(step["step_id"]), intents)
        if action["verb"] == "write":
            action["mechanical_before"] = snapshot(Path(step["target"]))
            actions.append(action)
        else:
            results.append(action["row"])

    intents_dir = _ensure_private_subdir(vault, "intents")
    executor = {
        "isolated": executor_isolated,
        "runner": str(Path(__file__).resolve()),
        "package_state": None,
    }
    for action in actions:
        _record_result(results, _step_row(action["step"], "pending", None))
    try:
        initial_payload = _recovery_receipt_payload(
            recovery_id, payload, vault, previous_id, sequence, results, None, executor
        )
        initial = _receipt_document(initial_payload, "recovery_receipt_id")
        _save_once(
            vault / f"upgrade-recovery-receipt-{initial['recovery_receipt_id']}.json", initial, vault
        )
        failure: dict[str, Any] | None = None
        stopped = False
        document: dict[str, Any] | None = None
        for action in actions:
            step = action["step"]
            if stopped:
                continue
            intent = {
                "intent_schema": "upgrade-recovery-intent",
                "recovery_id": recovery_id,
                "step_id": step["step_id"],
                "target": step["target"],
                "action": step["action"],
                "expected_current": step["expected_current"],
                "restore_state": step["restore_state"],
            }
            _save_once(
                intents_dir / f"rintent-{recovery_id[:16]}-{step['step_id'][:32]}.json",
                {"schema_version": 1, "payload": intent},
                vault,
            )
            try:
                _execute_step(step, action["mechanical_before"])
                after = _payload_state(Path(step["target"]))
            except ContractError as error:
                _record_result(results,
                    _step_row(step, "failed", _measured(step["target"]), reason=error.code)
                )
                failure = {"step_id": step["step_id"], "code": error.code}
                retained = getattr(error, "retained_refs", None)
                if retained:
                    failure["retained_refs"] = retained
                stopped = True
            except OSError:
                _record_result(results,
                    _step_row(
                        step, "failed", _measured(step["target"]), reason="write-failed"
                    )
                )
                failure = {"step_id": step["step_id"], "code": "write-failed"}
                stopped = True
            else:
                expected_after = (
                    dict(_ABSENT) if step["action"] == "remove" else step["restore_state"]
                )
                if after != expected_after:
                    _record_result(results, _step_row(step, "failed", after, reason="after-mismatch"))
                    failure = {"step_id": step["step_id"], "code": "after-mismatch"}
                    stopped = True
                else:
                    _record_result(results, _step_row(step, "succeeded", after))
            receipt_payload = _recovery_receipt_payload(
                recovery_id,
                payload,
                vault,
                previous_id,
                sequence,
                results,
                failure,
                executor,
            )
            document = _receipt_document(receipt_payload, "recovery_receipt_id")
            _save_once(
                vault / f"upgrade-recovery-receipt-{document['recovery_receipt_id']}.json",
                document,
                vault,
            )

        receipt_payload = _recovery_receipt_payload(
            recovery_id, payload, vault, previous_id, sequence, results, failure, executor
        )
        document = _receipt_document(receipt_payload, "recovery_receipt_id")
        _save_once(
            vault / f"upgrade-recovery-receipt-{document['recovery_receipt_id']}.json",
            document,
            vault,
        )
    except (ContractError, OSError) as error:
        raise _batch_halt(
            error,
            vault,
            phase="recovery",
            plan_id=payload["plan_id"],
            recovery_id=recovery_id,
            intent_prefix=f"rintent-{recovery_id[:16]}-",
            id_field="step_id",
        ) from error
    return document


def _recovery_receipt_payload(
    recovery_id: str,
    plan_payload: Mapping[str, Any],
    vault: Path,
    previous_id: str | None,
    sequence: int,
    results: list[dict[str, Any]],
    failure: dict[str, Any] | None,
    executor: Mapping[str, Any],
) -> dict[str, Any]:
    failed = any(row["result"] == "failed" for row in results)
    succeeded = any(row["result"] in _COMPLETED_TOKENS for row in results)
    if failed and succeeded:
        status = "partial"
    elif failed:
        status = "failed"
    elif any(row["result"] == "pending" for row in results):
        status = "partial"
    else:
        status = "complete"
    return {
        "receipt_schema": RECOVERY_RECEIPT_SCHEMA,
        "recovery_id": recovery_id,
        "plan_id": plan_payload["plan_id"],
        "upgrade_receipt_id": plan_payload["receipt_id"],
        "backup_root": str(vault),
        "previous_receipt_id": previous_id,
        "sequence": sequence,
        "status": status,
        "executor": dict(executor),
        "steps": list(results),
        "failure": failure,
    }


def _step_row(
    step: Mapping[str, Any],
    result: str,
    after: dict[str, Any] | None,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    if result not in _STEP_RESULT_TOKENS:
        _fail("invalid-argument", "unknown step result token")
    return {
        "step_id": step["step_id"],
        "resource_id": step["resource_id"],
        "action": step["action"],
        "target": step["target"],
        "result": result,
        "expected_current": step["expected_current"],
        "restore_state": step["restore_state"],
        "after": after,
        "mechanical_after": _mechanical_measured(step["target"]) if after is not None else None,
        "reason": reason,
    }


def _reconcile_step(
    step: dict[str, Any],
    prior: dict[str, Any] | None,
    intents: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    live = _payload_state(Path(step["target"]))
    mechanical = snapshot(Path(step["target"]))
    expected_after = (
        dict(_ABSENT) if step["action"] == "remove" else step["restore_state"]
    )
    if prior is not None and prior.get("result") in _COMPLETED_TOKENS:
        if live == expected_after and mechanical == prior.get("mechanical_after"):
            return {"verb": "record", "row": _step_row(step, "skipped-complete", live)}
        _fail(
            "state-conflict",
            "a completed recovery step no longer matches its receipt outcome",
        )
    intent = intents.get(step["step_id"])
    if intent is not None:
        if step["action"] == "restore" and live["type"] == "absent":
            return {"verb": "write", "step": step}
        if live == expected_after and (
            mechanical == (dict(_ABSENT) if step["action"] == "remove" else step["backup_ref"]["state"])
        ):
            return {"verb": "record", "row": _step_row(step, "reconciled", live)}
        if live != step["expected_current"] or mechanical != step["expected_mechanical"]:
            _fail(
                "state-conflict",
                "an interrupted recovery left an unknown live state; reconcile manually",
            )
        return {"verb": "write", "step": step}
    if live != step["expected_current"] or mechanical != step["expected_mechanical"]:
        _fail(
            "state-conflict",
            "a recovery target changed since the recovery plan was sealed",
        )
    if live == expected_after and step["action"] == "restore":
        return {"verb": "record", "row": _step_row(step, "succeeded", live)}
    return {"verb": "write", "step": step}


def _execute_step(step: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    target = Path(step["target"])
    scope = target.parent
    if snapshot(target) != expected:
        _fail("state-conflict", "a recovery target changed immediately before its write")
    if step["action"] == "remove":
        remove_reference(target, expected, scope=scope)
        return
    backup_ref = step["backup_ref"]
    if backup_ref is None:
        _fail(
            "preservation-failed",
            "a restore step has no original backup",
            exit_code=3,
        )
    if snapshot(Path(backup_ref["path"])) != backup_ref["state"]:
        _fail(
            "preservation-failed",
            "an original backup no longer matches its recorded state",
            exit_code=3,
        )
    if step["restore_state"]["type"] == "file":
        install_reference(backup_ref, target, expected, scope=scope)
        return
    if expected["type"] != "absent":
        remove_reference(target, expected, scope=scope)
    install_reference(backup_ref, target, dict(_ABSENT), scope=scope)


# ---------------------------------------------------------------------------
# Internal isolated executor dispatch (private argv; never a public CLI)
# ---------------------------------------------------------------------------


def _internal_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sbtd_upgrade",
        description="private isolated upgrade executor; not a public interface",
    )
    phase = parser.add_mutually_exclusive_group(required=True)
    phase.add_argument("--internal-apply", action="store_true")
    phase.add_argument("--internal-apply-recovery", action="store_true")
    parser.add_argument("--plan-id")
    parser.add_argument("--recovery-id")
    parser.add_argument("--plan-file", required=True)
    parser.add_argument("--receipt-file")
    args = parser.parse_args(argv)
    try:
        plan = _load_document_file(Path(args.plan_file))
        receipt = (
            _load_document_file(Path(args.receipt_file))
            if args.receipt_file
            else None
        )
        if args.internal_apply:
            _plan_id, plan_payload = _validate_plan(plan)
            package_root = Path(plan_payload["baseline"]["source"]["path"])
            staged = _trusted_package_root()
            vault = require_private_directory(Path(plan_payload["backup_root"]))
            if staged.parent != vault / "self" or _payload_state(staged) != plan_payload["baseline"]["source"]["state"]:
                _fail("source-untrusted", "the internal executor is not a validated vault stage")
            document = _apply_upgrade_local(
                plan,
                confirmed=args.plan_id,
                receipt=receipt,
                package_root=package_root,
                executor_isolated=True,
            )
        else:
            document = _apply_recovery_local(
                plan,
                confirmed=args.recovery_id,
                receipt=receipt,
                package_root=None,
                executor_isolated=True,
            )
    except ContractError as error:
        exit_code = error.exit_code if error.exit_code in (2, 3) else 2
        surface: dict[str, Any] = {
            "code": error.code,
            "message": error.message,
            "exit_code": exit_code,
        }
        if isinstance(error.details, Mapping):
            surface["details"] = dict(error.details)
        _emit_internal({"error": surface})
        return exit_code
    _emit_internal(document)
    return 0


def _emit_internal(document: Mapping[str, Any]) -> None:
    payload = json.dumps(document, ensure_ascii=False, allow_nan=False) + "\n"
    sys.stdout.buffer.write(payload.encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    raise SystemExit(_internal_main())
