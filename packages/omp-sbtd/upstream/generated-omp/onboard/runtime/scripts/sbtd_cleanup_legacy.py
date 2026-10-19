"""Confirmed, project-scoped legacy cleanup with private plans and backups.

These documents have their own schema version; they are not migration contract
objects. A digest binds the displayed plan, never substitutes for scope/identity
validation. Plan writes only its private evidence, not cleanup targets.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

import onboard_contracts as contracts
from sbtd_cleanup_targets import (
    RETIRED_SKILL_NAMES,
    detect_mcp_targets,
    detect_project_targets,
    detect_skill_targets,
    remove_json_server_key,
    remove_marker_blocks,
    remove_toml_server_table,
    strict_json_object,
)
from sbtd_migration_files import (
    backup_reference,
    read_file,
    remove_reference,
    require_private_directory,
    save_document,
    snapshot,
    write_file,
)
from sbtd_project import TaskDataError


def _fail(code: str, message: str) -> NoReturn:
    raise contracts.ContractError(code, message, exit_code=2)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="microseconds")


def _digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(contracts.canonical_json_bytes(payload)).hexdigest()


def _safe_path(path: Path) -> Path:
    if not path.is_absolute() or path != path.resolve():
        _fail("invalid-path", "cleanup paths must be absolute canonical paths")
    if any(part.is_symlink() for part in (path, *path.parents)):
        _fail("invalid-path", "cleanup paths must not follow symlinks")
    return path


def _roots(roots: Sequence[Path], vault: Path, home: Path) -> list[Path]:
    result: list[Path] = []
    for root in roots:
        _safe_path(root)
        if not root.is_dir() or root in {home, Path(root.anchor)}:
            _fail("scope-conflict", "select a project, not HOME or a filesystem root")
        if root.is_relative_to(vault) or vault.is_relative_to(root):
            _fail(
                "scope-conflict", "backup directory must be outside selected projects"
            )
        if any(
            root.is_relative_to(other) or other.is_relative_to(root) for other in result
        ):
            _fail(
                "scope-conflict",
                "cleanup project roots must be distinct and non-nested",
            )
        result.append(root)
    if not result:
        _fail("scope-conflict", "cleanup requires explicitly selected project roots")
    return result


def _all_candidates(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    payload = plan["payload"]
    candidates = [
        item for project in payload["projects"] for item in project["candidates"]
    ]
    for kind in ("skills", "mcp"):
        candidates.extend(payload["shared"][kind]["candidates"])
    return candidates


def _check_candidate_paths(plan: Mapping[str, Any], vault: Path) -> None:
    seen: list[Path] = []
    for candidate in _all_candidates(plan):
        path = _safe_path(Path(candidate["path"]))
        if path.is_relative_to(vault) or vault.is_relative_to(path):
            _fail("scope-conflict", "backup directory overlaps a cleanup target")
        if any(
            path.is_relative_to(other) or other.is_relative_to(path) for other in seen
        ):
            _fail("scope-conflict", "cleanup targets must be distinct and non-nested")
        seen.append(path)


def _blocked(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for group in [*payload["projects"], *payload["shared"].values()]
        for item in group["blocked"]
    ]


def _seal_candidates(detected: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidates": [
            dict(item, before=snapshot(Path(item["path"])))
            for item in detected["candidates"]
        ],
        "blocked": detected["blocked"],
    }


def plan_cleanup_legacy(
    roots: Sequence[Path],
    backup_root: Path,
    *,
    skills_root: Path,
    environ: Mapping[str, str],
) -> tuple[dict[str, Any], int]:
    vault = require_private_directory(_safe_path(backup_root))
    home = Path(
        environ.get("HOME") or environ.get("USERPROFILE") or Path.home()
    ).resolve()
    selected = _roots(roots, vault, home)
    _safe_path(skills_root)
    projects = []
    for root in selected:
        detected = detect_project_targets(root)
        ready = []
        for candidate in detected["candidates"]:
            if candidate["kind"] == "trellis-uninstall":
                from sbtd_trellis_uninstall import prepare_trellis_uninstall

                try:
                    candidate["trellis"] = prepare_trellis_uninstall(
                        root, environ=environ
                    )
                    if candidate["trellis"]["payload"]["status"] != "ready":
                        detected["blocked"].append(
                            {
                                "path": candidate["path"],
                                "kind": candidate["kind"],
                                "reason": candidate["trellis"]["payload"].get(
                                    "unavailable_code", "uninstall-unavailable"
                                ),
                            }
                        )
                        continue
                except (contracts.ContractError, OSError, ValueError) as error:
                    detected["blocked"].append(
                        {
                            "path": candidate["path"],
                            "kind": candidate["kind"],
                            "reason": getattr(error, "code", "uninstall-unavailable"),
                        }
                    )
                    continue
            ready.append(candidate)
        detected["candidates"] = ready
        projects.append(dict(_seal_candidates(detected), root=str(root)))
    payload = {
        "created_at": _now(),
        "backup_root": str(vault),
        "home": str(home),
        "skills_root": str(skills_root),
        "projects": projects,
        "shared": {
            "skills": _seal_candidates(
                detect_skill_targets(skills_root, retired=RETIRED_SKILL_NAMES)
            ),
            "mcp": _seal_candidates(detect_mcp_targets(environ=environ)),
        },
    }
    plan = {"schema_version": 1, "payload": payload, "plan_id": _digest(payload)}
    _check_candidate_paths(plan, vault)
    status = (
        "blocked"
        if _blocked(payload)
        else ("planned" if _all_candidates(plan) else "nothing-to-clean")
    )
    destination = vault / f"cleanup-legacy-plan-{plan['plan_id']}.json"
    save_document(destination, plan, private_root=vault)
    return {
        "mode": "cleanup-legacy",
        "phase": "plan",
        "status": status,
        "plan_id": plan["plan_id"],
        "projects": [{"root": str(root), "status": status} for root in selected],
        "cleanup_legacy": {"plan": plan, "plan_path": str(destination)},
    }, 2 if status == "blocked" else 0


def _read_document(path: Path, id_key: str) -> dict[str, Any]:
    _safe_path(path)
    require_private_directory(path.parent)
    document = strict_json_object(read_file(path))
    if (
        type(document.get("schema_version")) is not int
        or document["schema_version"] != 1
        or set(document) != {"schema_version", "payload", id_key}
    ):
        _fail("invalid-document", "unsupported cleanup document")
    if not isinstance(document["payload"], dict) or document[id_key] != _digest(
        document["payload"]
    ):
        _fail(
            "binding-violation",
            "cleanup document content does not match its identifier",
        )
    return document


def _render(candidate: Mapping[str, Any], raw: bytes) -> bytes:
    if candidate["kind"] == "marker-blocks":
        return remove_marker_blocks(raw)
    if candidate["kind"] != "mcp-server-remove":
        _fail("unsupported-operation", "candidate is not a supported file edit")
    remove = (
        remove_toml_server_table
        if candidate["format"] == "toml"
        else remove_json_server_key
    )
    for key in candidate["keys"]:
        raw = remove(raw, key)
    return raw


def _goal(candidate: Mapping[str, Any], backup: Mapping[str, Any]) -> dict[str, Any]:
    if candidate["kind"] in {
        "directory-remove",
        "skill-directory",
        "trellis-uninstall",
    }:
        return {"type": "absent", "checksum": None}
    raw = read_file(Path(backup["path"]), backup["state"])
    return {
        "type": "file",
        "checksum": hashlib.sha256(_render(candidate, raw)).hexdigest(),
    }


def _validate_scope(
    plan: Mapping[str, Any],
    done: Mapping[str, Any],
    progressed: Mapping[str, Any],
    environ: Mapping[str, str],
) -> None:
    payload = plan["payload"]
    vault = require_private_directory(Path(payload["backup_root"]))
    home = Path(
        environ.get("HOME") or environ.get("USERPROFILE") or Path.home()
    ).resolve()
    if str(home) != payload["home"]:
        _fail("scope-conflict", "cleanup HOME changed since the plan")
    _roots([Path(p["root"]) for p in payload["projects"]], vault, home)
    # The confirmed plan owns this selection; ambient settings cannot redirect it.
    skills_root = _safe_path(Path(payload["skills_root"]))
    if _blocked(payload):
        _fail(
            "blocked-target", "resolve blocked cleanup targets and generate a new plan"
        )
    _check_candidate_paths(plan, vault)

    def compare(sealed, detected):
        if detected["blocked"]:
            _fail("blocked-target", "current target inspection is blocked")
        remaining = {
            item["path"]: {
                k: v for k, v in item.items() if k not in {"before", "trellis"}
            }
            for item in sealed
            if item["path"] not in done and item["path"] not in progressed
        }
        # A receipt-proven vendor transition fully explains why a pending
        # candidate no longer matches its sealed detection; every other path
        # keeps the exact sealed comparison, and the pending path is still
        # held to its recorded transition state below.
        if remaining != {
            item["path"]: item
            for item in detected["candidates"]
            if item["path"] not in progressed
        }:
            _fail(
                "scope-conflict",
                "cleanup candidates differ from current scoped detection",
            )

    for project in payload["projects"]:
        root = Path(project["root"])
        expected = {
            "trellis-uninstall": root / ".trellis",
            "directory-remove": root / ".gitnexus",
            "marker-blocks": root / "AGENTS.md",
        }
        for item in project["candidates"]:
            if expected.get(item["kind"]) != Path(item["path"]) or (
                item["kind"] == "trellis-uninstall" and item["root"] != str(root)
            ):
                _fail(
                    "scope-conflict", "project cleanup path or operation is not allowed"
                )
        compare(project["candidates"], detect_project_targets(root))
    for item in payload["shared"]["skills"]["candidates"]:
        if (
            item["kind"] != "skill-directory"
            or item["name"] not in RETIRED_SKILL_NAMES
            or Path(item["path"]) != skills_root / item["name"]
        ):
            _fail("scope-conflict", "unknown shared Skill deletion")
    compare(
        payload["shared"]["skills"]["candidates"],
        detect_skill_targets(skills_root, retired=RETIRED_SKILL_NAMES),
    )
    compare(payload["shared"]["mcp"]["candidates"], detect_mcp_targets(environ=environ))
    for candidate in _all_candidates(plan):
        current = snapshot(Path(candidate["path"]))
        # Pending targets sit at their sealed before-state, or exactly at the
        # expected_after a successful vendor transition recorded for them.
        allowed = done.get(candidate["path"])
        if allowed is None:
            advance = progressed.get(candidate["path"])
            allowed = (
                advance["expected_current"]
                if advance is not None
                else candidate["before"]
            )
        if current != allowed:
            _fail(
                "state-conflict", "cleanup target changed after plan or prior receipt"
            )


def _vendor_transitions(
    candidate: Mapping[str, Any], row: Mapping[str, Any], vault: Path
) -> dict[str, dict[str, Any]]:
    """Per-path effects of a succeeded vendor uninstall, bound to the plan.
    The receipt's vendor outcome proves a transition only when it is bound to
    the plan's sealed prepared resources: identical roots and prepared
    identity, a successful zero vendor exit, exact per-resource identity
    (resource id, kind, relative path, derived successful status) and
    ``before``/``expected_after`` states, an immutable original backup inside
    the private vault for every resource, and no unlisted, duplicated or
    omitted path or resource identifier.
    """
    outcome = row.get("vendor")
    prepared = candidate["trellis"]
    payload = prepared["payload"]
    if (
        not isinstance(outcome, Mapping)
        or outcome.get("status") != "removed"
        or type(outcome.get("exit")) is not int
        or outcome.get("exit") != 0
        or outcome.get("prepared_id") != prepared.get("prepared_id")
        or prepared.get("prepared_id") != _digest(payload)
        or outcome.get("root") != payload["root"]
        or payload["root"] != candidate["root"]
    ):
        _fail("binding-violation", "receipt vendor outcome is not bound to the plan")
    if not isinstance(outcome.get("results"), list):
        _fail("binding-violation", "receipt vendor results must be a list")
    resources = {}
    resource_ids = set()
    for resource in payload["resources"]:
        if not isinstance(resource, Mapping):
            _fail("binding-violation", "a prepared vendor resource is malformed")
        if (
            resource.get("path") in resources
            or resource.get("resource_id") in resource_ids
        ):
            _fail(
                "binding-violation",
                "prepared vendor resources repeat a path or identifier",
            )
        resources[resource.get("path")] = resource
        resource_ids.add(resource.get("resource_id"))
    transitions: dict[str, dict[str, Any]] = {}
    seen_ids = set()
    for result in outcome["results"]:
        if not isinstance(result, Mapping):
            _fail("binding-violation", "a receipt vendor result is malformed")
        path = result.get("path")
        resource = resources.get(path)
        if resource is None or path in transitions:
            _fail(
                "binding-violation",
                "receipt vendor outcome lists an unbound or repeated path",
            )
        expected_after = resource.get("expected_after")
        if not isinstance(expected_after, Mapping):
            _fail("binding-violation", "a prepared vendor resource is malformed")
        successful = "removed" if expected_after.get("type") == "absent" else "scrubbed"
        if (
            result.get("resource_id") != resource.get("resource_id")
            or result.get("resource_id") in seen_ids
            or result.get("kind") != resource.get("kind")
            or result.get("relative") != resource.get("relative")
            or result.get("status") != successful
            or result.get("before") != resource["before"]
            or result.get("after") != expected_after
        ):
            _fail(
                "binding-violation",
                "receipt vendor result differs from the prepared transition",
            )
        seen_ids.add(result["resource_id"])
        backup = result.get("backup_ref")
        if not backup:
            _fail("binding-violation", "receipt vendor result keeps no original")
        backup_path = _safe_path(Path(backup["path"]))
        if (
            not backup_path.is_relative_to(vault)
            or backup.get("state") != resource["before"]
            or snapshot(backup_path) != resource["before"]
        ):
            _fail("backup-conflict", "vendor backup is unavailable or changed")
        transitions[path] = {
            "before": resource["before"],
            "expected_current": result["after"],
            "backup_ref": backup,
        }
    if len(transitions) != len(resources):
        _fail("binding-violation", "receipt vendor outcome omits a prepared path")
    return transitions


def _previous_receipt(path: Path | None, plan: Mapping[str, Any], vault: Path):
    if path is None:
        return None, {}, {}
    previous = _read_document(path, "receipt_id")
    if previous["payload"]["plan_id"] != plan["plan_id"]:
        _fail("binding-violation", "cleanup receipt belongs to a different plan")
    candidates = {item["path"]: item for item in _all_candidates(plan)}
    done = {}
    progressed: dict[str, dict[str, Any]] = {}
    for row in previous["payload"]["results"]:
        candidate = candidates.get(row["path"])
        if (
            candidate is None
            or row["kind"] != candidate["kind"]
            or row["before"] != candidate["before"]
        ):
            _fail("binding-violation", "receipt contains an unbound cleanup result")
        backup = row["backup_ref"]
        if backup:
            backup_path = _safe_path(Path(backup["path"]))
            if (
                not backup_path.is_relative_to(vault)
                or snapshot(backup_path) != candidate["before"]
            ):
                _fail("backup-conflict", "receipt backup is unavailable or changed")
        if row["status"] == "succeeded":
            if not backup or row["after"] != _goal(candidate, backup):
                _fail(
                    "binding-violation",
                    "receipt success does not prove the intended result",
                )
            done[row["path"]] = row["after"]
            progressed.pop(row["path"], None)
            if candidate["kind"] == "trellis-uninstall":
                for resource_path, transition in _vendor_transitions(
                    candidate, row, vault
                ).items():
                    if resource_path == row["path"] or resource_path in done:
                        continue
                    other = candidates.get(resource_path)
                    if other is None:
                        # Not a cleanup candidate: only the recorded vendor
                        # transition may explain its current state.
                        if (
                            snapshot(_safe_path(Path(resource_path)))
                            != transition["expected_current"]
                        ):
                            _fail(
                                "state-conflict",
                                "vendor-cleaned path changed after the receipt",
                            )
                        continue
                    if transition["before"] != other["before"]:
                        _fail(
                            "binding-violation",
                            "vendor transition does not match the sealed candidate",
                        )
                    progressed[resource_path] = transition
        else:
            advance = progressed.get(row["path"])
            allowed = (
                advance["expected_current"] if advance is not None else row["before"]
            )
            if row["after"] != allowed:
                _fail(
                    "partial-cleanup",
                    "partial cleanup requires reconciliation before retry",
                )
        vendor = row.get("vendor")
        if vendor is None or row["status"] == "succeeded":
            continue
        if (
            not isinstance(vendor, Mapping)
            or not isinstance(vendor.get("results"), list)
            or any(not isinstance(resource, Mapping) for resource in vendor["results"])
        ):
            _fail("binding-violation", "failed vendor evidence is malformed")
        if vendor["status"] == "partial" or any(
            resource["after"] != resource["before"] for resource in vendor["results"]
        ):
            _fail(
                "partial-cleanup",
                "vendor side effects require reconciliation before retry",
            )
    return previous, done, progressed


def _rejection(phase: str, reason: str, code: int = 2):
    return {
        "mode": "cleanup-legacy",
        "phase": phase,
        "status": "blocked" if code == 2 else "failed",
        "plan_id": None,
        "projects": [],
        "reason": reason,
        "nextStep": "Preserve backups; reconcile the failure before retrying.",
        "cleanup_legacy": {},
    }, code


def apply_cleanup_legacy(
    plan_path: Path,
    *,
    confirm_cleanup: str | None,
    cleanup_receipt_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], int]:
    environ = dict(os.environ) if environ is None else environ
    try:
        plan = _read_document(plan_path, "plan_id")
        vault = require_private_directory(plan_path.parent)
        if str(vault) != plan["payload"]["backup_root"]:
            _fail(
                "scope-conflict",
                "plan moved from its declared private evidence directory",
            )
        if confirm_cleanup != plan["plan_id"]:
            _fail("confirmation-required", "confirm this plan_id before cleanup")
        previous, done, progressed = _previous_receipt(
            cleanup_receipt_path, plan, vault
        )
        _validate_scope(plan, done, progressed, environ)
    except (
        contracts.ContractError,
        TaskDataError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
    ):
        return _rejection(
            "apply",
            "cleanup confirmation, scope, identity or evidence validation failed",
        )
    from sbtd_migration import _prepare_backup_parent

    candidates = _all_candidates(plan)
    results = (
        {row["path"]: row for row in previous["payload"]["results"]} if previous else {}
    )
    started = _now()
    status = "cleaned"
    backups: dict[str, dict[str, Any]] = {}
    # Preserve every original before the vendor can edit another candidate (AGENTS).
    try:
        for index, item in enumerate(candidates):
            if item["path"] in done:
                continue
            advance = progressed.get(item["path"])
            if advance is not None:
                # The original is already preserved by the succeeded vendor
                # run; reuse that immutable backup instead of demanding the
                # target still match its sealed before-state.
                backups[item["path"]] = advance["backup_ref"]
                continue
            destination = vault / plan["plan_id"] / "cleanup" / f"{index:03d}"
            _prepare_backup_parent(destination, vault)
            backups[item["path"]] = backup_reference(
                {"path": item["path"], "state": item["before"]},
                destination,
                private_root=vault,
            )
    except (contracts.ContractError, TaskDataError, OSError):
        return _rejection(
            "apply", "backup preservation failed; no cleanup execution started", 3
        )
    current_states = {
        item["path"]: (
            progressed[item["path"]]["expected_current"]
            if item["path"] in progressed
            else item["before"]
        )
        for item in candidates
    }
    for index, item in enumerate(candidates):
        if item["path"] in done:
            continue
        path = Path(item["path"])
        row = {
            "resource_id": f"cleanup-{index:03d}",
            "kind": item["kind"],
            "path": str(path),
            "status": "failed",
            "before": item["before"],
            "after": None,
            "backup_ref": backups[str(path)],
        }
        try:
            if snapshot(path) != current_states[str(path)]:
                _fail("state-conflict", "target changed during cleanup")
            if item["kind"] == "trellis-uninstall":
                from sbtd_trellis_uninstall import execute_trellis_uninstall

                outcome = execute_trellis_uninstall(
                    Path(item["root"]), item["trellis"], vault, environ=environ
                )
                row["vendor"] = outcome
                for resource in outcome["results"]:
                    if resource["path"] in current_states:
                        current_states[resource["path"]] = resource["after"]
                if outcome["status"] != "removed":
                    _fail("uninstall-failed", "vendor uninstall did not complete")
            elif item["kind"] in {"directory-remove", "skill-directory"}:
                remove_reference(path, current_states[str(path)], scope=path.parent)
            else:
                # Render from the preserved original backup: a target the
                # vendor legitimately removed (expected absent) is recreated
                # by this write with the fully rendered content.
                original = read_file(Path(backups[str(path)]["path"]), item["before"])
                write_file(
                    path,
                    _render(item, original),
                    current_states[str(path)],
                    scope=path.parent,
                )
            row["after"] = snapshot(path)
            if row["after"] != _goal(item, backups[str(path)]):
                _fail(
                    "post-state-conflict",
                    "cleanup result differs from the intended state",
                )
            row["status"] = "succeeded"
        except (contracts.ContractError, TaskDataError, OSError, ValueError) as error:
            row["error"] = getattr(error, "code", "operation-failed")
            try:
                row["after"] = snapshot(path)
            except (contracts.ContractError, OSError):
                row["after"] = None
            status = "failed"
        results[str(path)] = row
        if status == "failed":
            break
    payload = {
        "plan_id": plan["plan_id"],
        "started_at": started,
        "finished_at": _now(),
        "status": status,
        "results": list(results.values()),
    }
    receipt = {"schema_version": 1, "receipt_id": _digest(payload), "payload": payload}
    destination = vault / f"cleanup-legacy-receipt-{receipt['receipt_id']}.json"
    try:
        save_document(destination, receipt, private_root=vault)
    except (contracts.ContractError, TaskDataError, OSError):
        return _rejection(
            "apply",
            "cleanup may have written targets; receipt persistence failed; preserve the private backup directory",
            3,
        )
    return {
        "mode": "cleanup-legacy",
        "phase": "apply",
        "status": status,
        "plan_id": plan["plan_id"],
        "projects": [
            {"root": p["root"], "status": status} for p in plan["payload"]["projects"]
        ],
        "cleanup_legacy": {"receipt": receipt, "receipt_path": str(destination)},
    }, 0 if status == "cleaned" else 3


def _argument_path(value: str) -> Path:
    if not value.strip():
        _fail("invalid-path", "cleanup path must not be empty")
    return _safe_path(Path(value).expanduser())


def run_cleanup_legacy(args: Any) -> int:
    try:
        if args.phase == "plan":
            from onboard import resolve_global_skills_dir

            roots = [
                _argument_path(value.strip()) for value in args.projects_root.split(",")
            ]
            skills_root, _source = resolve_global_skills_dir(args.global_skills_dir)
            envelope, code = plan_cleanup_legacy(
                roots,
                _argument_path(args.backup_root),
                skills_root=skills_root,
                environ=dict(os.environ),
            )
        else:
            envelope, code = apply_cleanup_legacy(
                _argument_path(args.plan),
                confirm_cleanup=args.confirm_cleanup,
                cleanup_receipt_path=_argument_path(args.cleanup_receipt)
                if args.cleanup_receipt
                else None,
                environ=dict(os.environ),
            )
    except (
        contracts.ContractError,
        TaskDataError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        ImportError,
    ):
        envelope, code = _rejection(
            args.phase,
            "cleanup scope, dependencies or private evidence could not be validated",
        )
    if args.json:
        # Standalone cleanup envelope, not a migration-schema document.
        print(contracts.canonical_json_bytes(envelope).decode("utf-8"))
    else:
        print(f"Cleanup legacy {args.phase}: {envelope['status']}")
        print(
            envelope.get(
                "reason",
                "Inspect private --json output before confirming any deletion.",
            )
        )
    return code
