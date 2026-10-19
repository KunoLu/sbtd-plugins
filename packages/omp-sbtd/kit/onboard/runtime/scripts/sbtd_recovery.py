"""Manifest-scoped recovery planning and execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn

import onboard_contracts as contracts
from sbtd_migration import (
    _argument_path,
    _check_source_backups,
    _check_stage_backups,
    _now,
    _operations,
    _prepare_backup_parent,
    _private_document,
    _require_reconciliation_provenance,
    _resource_scope,
    _result_index,
    _summary_projects,
    _validate_context,
)
from sbtd_migration_files import (
    RetainedObjectError,
    backup_reference,
    install_reference,
    read_file,
    remove_reference,
    save_document,
    snapshot,
)
from sbtd_project import TaskDataError

_STAGE_PHASES = ("apply", "deploy", "cleanup")
_INVERSE_PHASES = ("cleanup", "deploy", "apply")
_RECOVERY_EXIT = {"failed": 5, "blocked": 2}


def _fail(code: str, message: str, exit_code: int = 2) -> NoReturn:
    raise contracts.ContractError(code, message, exit_code=exit_code)


def _document_from_reference(
    reference: Mapping[str, Any], kind: str
) -> tuple[dict[str, Any], bytes]:
    raw = read_file(Path(reference["path"]), reference["state"])
    return contracts.load_document(raw, kind), raw


def _evidence_ref(path: Path) -> dict[str, Any]:
    return {"path": str(path), "state": snapshot(path)}


def _selected_roots(
    manifest: Mapping[str, Any], projects_root: str | None
) -> list[dict[str, Any]]:
    projects = manifest["payload"]["projects"]
    if projects_root is None:
        return list(projects)
    selected: list[Path] = []
    for value in projects_root.split(","):
        if not value.strip():
            _fail("invalid-path", "the selected project list contains an empty path")
        root = _argument_path(value.strip())
        if root not in selected:
            selected.append(root)
    selected_names = {str(root) for root in selected}
    known = {project["root"] for project in projects}
    if not selected_names <= known:
        _fail("scope-conflict", "recovery selects projects outside the manifest batch")
    return [project for project in projects if project["root"] in selected_names]


def _resource_maps(
    manifest: Mapping[str, Any],
) -> tuple[
    dict[str, set[str]], dict[str, tuple[str, str]], dict[str, list[Mapping[str, Any]]]
]:
    dependents: dict[str, set[str]] = {}
    identity: dict[str, tuple[str, str]] = {}
    operations: dict[str, list[Mapping[str, Any]]] = {}
    for operation in _operations(manifest):
        rid = operation["resource_id"]
        identity[rid] = (operation["owner_kind"], operation["target"])
        dependents.setdefault(rid, set()).update(operation["dependent_projects"])
        operations.setdefault(rid, []).append(operation)
    return dependents, identity, operations


def _initial_states(
    operations: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    initial: dict[str, Any] = {}
    for rid, group in operations.items():
        for operation in group:
            requirement = operation["before_requirement"]
            if requirement["kind"] == "state":
                initial.setdefault(rid, requirement["state"])
    return initial


def _resource_order(
    identity: Mapping[str, tuple[str, str]], resource_id: str
) -> tuple[bool, str]:
    owner_kind, target = identity[resource_id]
    return owner_kind != "gitignore", target


def _blocked_plan(
    manifest: Mapping[str, Any],
    projects: Sequence[Mapping[str, Any]],
    evidence: Mapping[str, Any],
    conflicts: Sequence[str],
) -> tuple[dict[str, Any], int]:
    payload = {
        "manifest_id": manifest["manifest_id"],
        "status": "blocked",
        "projects": [
            {
                "root": project["root"],
                "source_ref": project["source_ref"],
                "head": project["head"],
            }
            for project in projects
        ],
        "shared_operation_ids": [],
        "input_evidence": dict(evidence),
        "resources": [],
        "steps": [],
        "conflicts": list(conflicts),
        "risks": [],
        "target": "pre-apply",
        "created_at": _now(),
    }
    plan = contracts.seal_document("recovery_plan", payload)
    projects_summary = [
        {
            "root": project["root"],
            "status": "blocked",
            "reason": "; ".join(conflicts),
            "nextStep": "Select the complete authorized dependency closure and re-plan.",
        }
        for project in projects
    ]
    return (
        contracts.make_envelope(
            "recovery",
            "plan",
            "blocked",
            projects_summary,
            "; ".join(conflicts),
            "Select the complete authorized dependency closure and re-plan.",
            plan,
            {"manifest_id": manifest["manifest_id"], "plan_id": plan["plan_id"]},
        ),
        2,
    )


def plan_recovery(
    manifest_path: Path,
    *,
    apply_receipt_path: Path | None = None,
    deployment_evidence_path: Path | None = None,
    cleanup_receipt_path: Path | None = None,
    projects_root: str | None = None,
) -> tuple[dict[str, Any], int]:
    """Read-only recovery plan for one manifest scope; caller owns saving."""
    manifest_path = Path(manifest_path)
    manifest, manifest_raw = _private_document(manifest_path, "manifest")
    documents: dict[str, Any] = {}
    raw_documents = {"manifest": manifest_raw}
    input_paths = {
        "manifest": manifest_path,
        "apply_receipt": Path(apply_receipt_path)
        if apply_receipt_path is not None
        else None,
        "deployment_evidence": Path(deployment_evidence_path)
        if deployment_evidence_path is not None
        else None,
        "cleanup_receipt": Path(cleanup_receipt_path)
        if cleanup_receipt_path is not None
        else None,
    }
    for path, kind in (
        (apply_receipt_path, "apply_receipt"),
        (deployment_evidence_path, "deployment_evidence"),
        (cleanup_receipt_path, "cleanup_receipt"),
    ):
        if path is None:
            continue
        document, raw = _private_document(Path(path), kind)
        documents[kind] = document
        raw_documents[kind] = raw
    contracts.validate_declared_bindings(manifest, documents, raw_documents)
    projects = _selected_roots(manifest, projects_root)
    context_conflicts: list[str] = []
    try:
        _validate_context(
            manifest_path,
            manifest,
            previous=documents.get("apply_receipt"),
            deployment=documents.get("deployment_evidence"),
            cleanup=documents.get("cleanup_receipt"),
        )
    except contracts.ContractError as error:
        if error.code != "state-conflict":
            raise
        context_conflicts.append(
            "current resources differ from the supplied migration evidence chain"
        )
    stage_documents = {
        "apply": documents.get("apply_receipt"),
        "deploy": documents.get("deployment_evidence"),
        "cleanup": documents.get("cleanup_receipt"),
    }
    stage_results = {
        phase: _result_index(document)
        for phase, document in stage_documents.items()
        if document is not None
    }
    _check_stage_backups(stage_results)
    _check_source_backups(manifest)

    dependents, identity, operations = _resource_maps(manifest)
    initial = _initial_states(operations)
    selected = {project["root"] for project in projects}
    required = {rid for rid, roots in dependents.items() if roots & selected}
    closure_conflicts = [
        f"{identity[rid][1]} requires dependents outside the selected recovery scope"
        for rid in sorted(required, key=lambda item: _resource_order(identity, item))
        if not dependents[rid] <= selected
    ]
    input_evidence = {
        kind: _evidence_ref(path) if path is not None else None
        for kind, path in input_paths.items()
    }
    if closure_conflicts:
        return _blocked_plan(manifest, projects, input_evidence, closure_conflicts)

    latest = {rid: initial.get(rid) for rid in required}
    required_steps: set[tuple[str, str]] = set()
    conflicts: list[str] = list(context_conflicts)
    for phase in _STAGE_PHASES:
        for rid, result in stage_results.get(phase, {}).items():
            if rid not in required:
                continue
            before = result["before"]
            after = result["after"]
            if before is None or after is None:
                conflicts.append(
                    f"{identity[rid][1]} has an unknown {phase} write state"
                )
                continue
            latest[rid] = after
            if before == after:
                continue
            if before["type"] != "absent" and result["backup_ref"] is None:
                conflicts.append(
                    f"{identity[rid][1]} lacks its retained {phase} original backup"
                )
                continue
            required_steps.add((phase, rid))
    resources = []
    for rid in sorted(required, key=lambda item: _resource_order(identity, item)):
        owner_kind, target = identity[rid]
        current = snapshot(Path(target))
        if latest[rid] is not None and current != latest[rid]:
            conflicts.append(f"{target} differs from its latest proven state")
        resources.append(
            {
                "resource_id": rid,
                "owner_kind": owner_kind,
                "target": target,
                "operation_ids": sorted(
                    operation["operation_id"] for operation in operations[rid]
                ),
                "dependent_projects": sorted(dependents[rid]),
                "state": current,
            }
        )
    if conflicts:
        return _blocked_plan(manifest, projects, input_evidence, conflicts)

    steps: list[dict[str, Any]] = []
    previous_by_resource: dict[str, str] = {}
    shared_ids: set[str] = set()
    shared_resources = {
        operation["resource_id"]
        for operation in manifest["payload"]["shared_operations"]
    }
    for phase in _INVERSE_PHASES:
        for rid in sorted(required, key=lambda item: _resource_order(identity, item)):
            if (phase, rid) not in required_steps:
                continue
            result = stage_results[phase][rid]
            depends_on = (
                [previous_by_resource[rid]] if rid in previous_by_resource else []
            )
            step = {
                "step_id": contracts.recovery_step_id(
                    manifest["manifest_id"], phase, rid
                ),
                "phase": phase,
                "resource_id": rid,
                "operation_ids": sorted(result["operation_ids"]),
                "dependent_projects": sorted(result["dependent_projects"]),
                "depends_on": depends_on,
                "backup_ref": result["backup_ref"],
                "expected_current": result["after"],
                "restore_to": result["before"],
            }
            previous_by_resource[rid] = step["step_id"]
            if rid in shared_resources:
                shared_ids.update(step["operation_ids"])
            steps.append(step)
    payload = {
        "manifest_id": manifest["manifest_id"],
        "status": "planned",
        "projects": [
            {
                "root": project["root"],
                "source_ref": project["source_ref"],
                "head": project["head"],
            }
            for project in projects
        ],
        "shared_operation_ids": sorted(shared_ids),
        "input_evidence": input_evidence,
        "resources": resources,
        "steps": steps,
        "conflicts": [],
        "risks": [],
        "target": "pre-apply",
        "created_at": _now(),
    }
    plan = contracts.seal_document("recovery_plan", payload)
    contracts.validate_declared_bindings(
        manifest,
        {**documents, "recovery_plan": plan},
        raw_documents,
    )
    projects_summary = [
        {
            "root": project["root"],
            "status": "planned",
            "reason": "",
            "nextStep": "Confirm this exact recovery plan before applying it.",
        }
        for project in projects
    ]
    envelope = contracts.make_envelope(
        "recovery",
        "plan",
        "planned",
        projects_summary,
        "",
        "Save only the recovery plan object in an authorized private directory; plan made no writes.",
        plan,
        {"manifest_id": manifest["manifest_id"], "plan_id": plan["plan_id"]},
    )
    _require_reconciliation_provenance(manifest, documents.get("deployment_evidence"))
    return envelope, 0


def _protection_ref(
    plan_path: Path, step: Mapping[str, Any], before: Mapping[str, Any], target: Path
) -> Mapping[str, Any] | None:
    if before["type"] == "absent":
        return None
    destination = plan_path.parent / "protection" / step["step_id"]
    _prepare_backup_parent(destination, plan_path.parent)
    return backup_reference(
        {"path": str(target), "state": before},
        destination,
        private_root=plan_path.parent,
    )


def _execute_step(
    manifest: Mapping[str, Any],
    operation: Mapping[str, Any],
    plan_path: Path,
    step: Mapping[str, Any],
) -> dict[str, Any]:
    target = Path(operation["target"])
    before = snapshot(target)
    result = {
        "step_id": step["step_id"],
        "resource_id": step["resource_id"],
        "phase": step["phase"],
        "operation_ids": list(step["operation_ids"]),
        "dependent_projects": list(step["dependent_projects"]),
        "status": "failed",
        "protection_ref": None,
        "before": before,
        "after": before,
        "error": None,
    }
    try:
        if before != step["expected_current"]:
            _fail("state-conflict", "a recovery step target changed after planning")
        scope = _resource_scope(manifest, operation)
        protection = _protection_ref(plan_path, step, before, target)
        result["protection_ref"] = protection
        if step["restore_to"]["type"] == "absent":
            remove_reference(target, before, scope=scope)
        else:
            install_reference(
                step["backup_ref"],
                target,
                before,
                scope=scope,
                backup_ref=protection,
            )
        result["after"] = snapshot(target)
        if result["after"] != step["restore_to"]:
            _fail(
                "post-state-conflict",
                "the recovery step outcome is not its planned post-state",
            )
        result["status"] = "succeeded"
    except (contracts.ContractError, TaskDataError, OSError, RuntimeError) as error:
        try:
            result["after"] = snapshot(target)
        except (contracts.ContractError, TaskDataError, OSError, RuntimeError):
            result["after"] = None
        result["error"] = (
            error.code
            if isinstance(error, contracts.ContractError)
            else "operation-io-failed"
        )
        if isinstance(error, RetainedObjectError):
            result["error"] += "; retained=" + contracts.canonical_json_bytes(
                error.retained_refs
            ).decode("utf-8")
    return result


def _check_recovery_protections(receipt: Mapping[str, Any]) -> None:
    for result in receipt["payload"]["results"]:
        protection = result["protection_ref"]
        if (
            protection is not None
            and snapshot(Path(protection["path"])) != protection["state"]
        ):
            _fail(
                "original-unavailable",
                "a retained recovery protection object is incomplete or unavailable",
                3,
            )


def _recovery_projects(
    plan: Mapping[str, Any],
    results: Mapping[str, Mapping[str, Any]],
    previous: Mapping[str, Any] | None,
    global_error: str | None,
) -> list[dict[str, Any]]:
    previous_projects = (
        {project["root"]: project for project in previous["payload"]["projects"]}
        if previous is not None
        else {}
    )
    projects = []
    for project in plan["payload"]["projects"]:
        root = project["root"]
        relevant = [
            step
            for step in plan["payload"]["steps"]
            if root in step["dependent_projects"]
        ]
        statuses = {
            results[step["step_id"]]["status"]
            for step in relevant
            if step["step_id"] in results
        }
        complete = all(step["step_id"] in results for step in relevant)
        if "failed" in statuses:
            status = "failed"
        elif not complete or "blocked" in statuses:
            status = "blocked"
        else:
            old = previous_projects.get(root)
            status = (
                "already-complete"
                if old and old["status"] in {"restored", "already-complete"}
                else "restored"
            )
        projects.append(
            {
                "root": root,
                "source_ref": project["source_ref"],
                "head": project["head"],
                "status": status,
                "reason": "a declared recovery step failed"
                if status == "failed"
                else (global_error or "not every planned recovery step completed")
                if status == "blocked"
                else "",
                "nextStep": "Inspect the retained private receipt and resolve the failure before retrying."
                if status in {"failed", "blocked"}
                else "",
            }
        )
    return projects


def _latest_succeeded_step_ids(
    steps: Sequence[Mapping[str, Any]],
    previous_results: Mapping[str, Mapping[str, Any]],
) -> set[str]:
    """Plan order is cleanup, then deploy, then apply.

    An earlier inverse step's after is historical once a later step for the
    same resource has succeeded. Only that latest succeeded step is current.
    """
    latest: dict[str, str] = {}
    for step in steps:
        old = previous_results.get(step["step_id"])
        if old is not None and old["status"] == "succeeded":
            latest[step["resource_id"]] = step["step_id"]
    return set(latest.values())


def apply_recovery(
    plan_path: Path,
    *,
    previous_receipt_path: Path | None = None,
    confirm_recovery: str | None = None,
) -> tuple[dict[str, Any], int]:
    """Execute or continue one confirmed manifest-scoped recovery plan."""
    plan_path = Path(plan_path)
    plan, plan_raw = _private_document(plan_path, "recovery_plan")
    if confirm_recovery != plan["plan_id"]:
        _fail(
            "confirmation-required",
            "recovery apply requires this plan's explicit confirmation",
        )
    evidence = plan["payload"]["input_evidence"]
    manifest, manifest_raw = _document_from_reference(evidence["manifest"], "manifest")
    documents: dict[str, Any] = {"recovery_plan": plan}
    raw_documents = {
        "manifest": manifest_raw,
        "recovery_plan": plan_raw,
    }
    stage_documents: dict[str, Any] = {}
    for kind in ("apply_receipt", "deployment_evidence", "cleanup_receipt"):
        reference = evidence[kind]
        if reference is None:
            continue
        document, raw = _document_from_reference(reference, kind)
        documents[kind] = document
        raw_documents[kind] = raw
        stage_documents[kind] = document
    previous = None
    previous_raw = None
    if previous_receipt_path is not None:
        previous, previous_raw = _private_document(
            Path(previous_receipt_path), "recovery_receipt"
        )
        documents["recovery_receipt"] = previous
        raw_documents["recovery_receipt"] = previous_raw
        if contracts._parse_timestamp(
            previous["payload"]["finished_at"]
        ) > contracts._parse_timestamp(_now()):
            _fail(
                "future-evidence",
                "a previous receipt is later than the current operation",
            )
    contracts.validate_declared_bindings(manifest, documents, raw_documents)
    manifest_dir = Path(evidence["manifest"]["path"]).parent
    if plan_path.parent != manifest_dir:
        _fail(
            "scope-conflict",
            "the recovery plan must remain beside its manifest in the authorized private directory",
        )
    _validate_context(
        plan_path,
        manifest,
        previous=stage_documents.get("apply_receipt"),
        deployment=stage_documents.get("deployment_evidence"),
        cleanup=stage_documents.get("cleanup_receipt"),
        recovery=previous,
    )
    stage_results = {
        "apply": _result_index(stage_documents.get("apply_receipt")),
        "deploy": _result_index(stage_documents.get("deployment_evidence")),
        "cleanup": _result_index(stage_documents.get("cleanup_receipt")),
    }
    stage_results = {
        phase: results for phase, results in stage_results.items() if results
    }
    _check_stage_backups(stage_results)
    _check_source_backups(manifest)
    if previous is not None:
        _check_recovery_protections(previous)
    operations = {
        operation["resource_id"]: operation for operation in _operations(manifest)
    }
    previous_results = (
        {result["step_id"]: result for result in previous["payload"]["results"]}
        if previous is not None
        else {}
    )
    results: dict[str, Mapping[str, Any]] = {
        step_id: dict(result) for step_id, result in previous_results.items()
    }
    latest_succeeded = _latest_succeeded_step_ids(
        plan["payload"]["steps"], previous_results
    )

    for step in plan["payload"]["steps"]:
        old = previous_results.get(step["step_id"])
        if old is not None and old["status"] == "succeeded":
            if step["step_id"] not in latest_succeeded:
                continue
            if (
                old["after"] is None
                or snapshot(Path(operations[step["resource_id"]]["target"]))
                != old["after"]
            ):
                _fail(
                    "retry-conflict",
                    "a previously restored resource no longer matches its outcome",
                )
            continue
        if old is not None:
            if (old["error"] or "").startswith(
                ("foreign-content-conflict", "post-state-conflict")
            ):
                _fail(
                    "unsafe-retry",
                    "unapproved changed objects require explicit manual reconciliation",
                )
            if old["before"] is None or old["before"] != old["after"]:
                _fail(
                    "unsafe-retry",
                    "a partial or unknown recovery write requires manual reconciliation",
                )
    _require_reconciliation_provenance(
        manifest, stage_documents.get("deployment_evidence")
    )
    started = _now()
    global_error = None
    try:
        for step in plan["payload"]["steps"]:
            old = previous_results.get(step["step_id"])
            if old is not None and old["status"] == "succeeded":
                continue
            result = _execute_step(
                manifest,
                operations[step["resource_id"]],
                plan_path,
                step,
            )
            results[step["step_id"]] = result
            if result["status"] != "succeeded":
                global_error = "a recovery step failed; later steps were not attempted"
                break
    except (contracts.ContractError, TaskDataError, OSError, RuntimeError):
        global_error = "recovery step execution failed"
    projects = _recovery_projects(plan, results, previous, global_error)
    status = contracts._aggregate(
        [project["status"] for project in projects],
        ("failed", "blocked"),
        "restored",
        "already-complete",
    )
    completed = sorted(
        step_id
        for step_id, result in results.items()
        if result["status"] == "succeeded"
    )
    pending = sorted(
        step["step_id"]
        for step in plan["payload"]["steps"]
        if step["step_id"] not in completed
    )
    shared_results = []
    shared_resources = {
        operation["resource_id"]
        for operation in manifest["payload"]["shared_operations"]
    }
    for rid in sorted(shared_resources):
        step_ids = [
            step["step_id"]
            for step in plan["payload"]["steps"]
            if step["resource_id"] == rid and step["step_id"] in completed
        ]
        if not step_ids:
            continue
        shared_results.append(
            {
                "resource_id": rid,
                "dependent_projects": sorted(dependents_for(manifest, rid)),
                "step_ids": step_ids,
            }
        )
    payload = {
        "plan_id": plan["plan_id"],
        "manifest_id": manifest["manifest_id"],
        "previous_receipt_id": previous["receipt_id"] if previous is not None else None,
        "input_evidence": evidence,
        "status": status,
        "projects": projects,
        "results": [
            results[step["step_id"]]
            for step in plan["payload"]["steps"]
            if step["step_id"] in results
        ],
        "shared_results": shared_results,
        "completed_step_ids": completed,
        "pending_step_ids": pending,
        "reason": global_error or "",
        "started_at": started,
        "finished_at": _now(),
        "runtime_readiness": "not-verified",
        "report_refs": [],
    }

    def seal_receipt() -> dict[str, Any]:
        document = contracts.seal_document("recovery_receipt", payload)
        contracts.validate_cumulative(previous, document, "recovery_receipt")
        contracts.validate_declared_bindings(
            manifest,
            {key: value for key, value in documents.items() if key != "recovery_receipt"}
            | {"recovery_receipt": document},
            {kind: raw for kind, raw in raw_documents.items() if kind != "recovery_receipt"},
        )
        return document

    receipt = seal_receipt()
    try:
        _require_reconciliation_provenance(
            manifest, stage_documents.get("deployment_evidence")
        )
    except contracts.ContractError:
        # Restoration has already happened. Preserve completed steps and
        # protections, but do not accept a result against stale provenance.
        provenance_error = "reconciliation provenance changed before recovery receipt publication"
        global_error = (
            f"{global_error}; {provenance_error}" if global_error else provenance_error
        )
        for project in projects:
            if project["status"] in {"restored", "already-complete"}:
                project.update(
                    status="blocked",
                    reason=provenance_error,
                    nextStep="Preserve the measured results and resolve the cited source drift before retrying.",
                )
        status = contracts._aggregate(
            [project["status"] for project in projects],
            ("failed", "blocked"),
            "restored",
            "already-complete",
        )
        payload.update(status=status, reason=global_error, finished_at=_now())
        receipt = seal_receipt()
    destination = plan_path.parent / f"recovery-{receipt['receipt_id']}.json"
    try:
        save_document(destination, receipt, private_root=plan_path.parent)
    except (contracts.ContractError, TaskDataError, OSError, RuntimeError):
        summaries = []
        for project in projects:
            diagnostics = [
                result["error"]
                for result in results.values()
                if project["root"] in result["dependent_projects"] and result["error"]
            ]
            summaries.append(
                {
                    "root": project["root"],
                    "status": "failed",
                    "reason": "cumulative receipt could not be saved; "
                    + "; ".join(diagnostics),
                    "nextStep": "Preserve originals and all reported retained objects; do not claim automatic recovery.",
                }
            )
        return contracts.make_envelope(
            "recovery",
            "apply",
            "failed",
            summaries,
            "cumulative evidence persistence failed",
            "Inspect the declared private evidence directory and reconcile before proceeding.",
            identifiers={
                "manifest_id": manifest["manifest_id"],
                "plan_id": plan["plan_id"],
                "receipt_id": None,
            },
        ), 5
    envelope = contracts.make_envelope(
        "recovery",
        "apply",
        status,
        _summary_projects(receipt),
        global_error or "",
        f"Cumulative receipt saved privately at {destination}.",
        receipt,
        {
            "manifest_id": manifest["manifest_id"],
            "plan_id": plan["plan_id"],
            "receipt_id": receipt["receipt_id"],
        },
    )
    return envelope, _RECOVERY_EXIT.get(status, 0)


def dependents_for(manifest: Mapping[str, Any], resource_id: str) -> set[str]:
    return {
        root
        for operation in _operations(manifest)
        if operation["resource_id"] == resource_id
        for root in operation["dependent_projects"]
    }


def run_recovery(args: Any) -> int:
    """The live CLI projects private recovery envelopes, never private logs."""
    envelope: dict[str, Any]
    rejection: str | None = None
    try:
        if args.phase == "plan":
            envelope, code = plan_recovery(
                _argument_path(args.manifest),
                apply_receipt_path=_argument_path(args.apply_receipt)
                if args.apply_receipt
                else None,
                deployment_evidence_path=_argument_path(args.deployment_evidence)
                if args.deployment_evidence
                else None,
                cleanup_receipt_path=_argument_path(args.cleanup_receipt)
                if args.cleanup_receipt
                else None,
                projects_root=args.projects_root,
            )
        elif args.phase == "apply":
            envelope, code = apply_recovery(
                _argument_path(args.plan),
                previous_receipt_path=_argument_path(args.recovery_receipt)
                if args.recovery_receipt
                else None,
                confirm_recovery=args.confirm_recovery,
            )
        else:
            _fail(
                "unsupported-phase",
                "this recovery phase is not implemented by this entry point",
            )
    except contracts.ContractError as error:
        code = error.exit_code
        rejection = str(error)
    except ImportError:
        code = 2
        rejection = "the installed recovery runtime or its declared dependencies are unavailable"
    except (TaskDataError, OSError, RuntimeError, ValueError):
        code = 5
        rejection = "recovery could not safely finish its filesystem operation"
    if rejection is not None:
        envelope = {
            "mode": "recovery",
            "phase": args.phase,
            "status": "failed" if code in {3, 5} else "blocked",
            "manifest_id": None,
            "plan_id": None,
            "receipt_id": None,
            "projects": [],
            "reason": rejection,
            "nextStep": "Preserve originals and private evidence; resolve the failure before retrying.",
            "recovery": {},
        }
    if args.json:
        contracts.write_json_response(envelope)
    else:
        print(f"Recovery {args.phase}: {envelope['status']}")
        for number, project in enumerate(envelope["projects"], 1):
            print(f"Project {number}: {project['status']}")
        print(
            "Detailed references are private; use --json only with authorized private storage."
        )
    return code
