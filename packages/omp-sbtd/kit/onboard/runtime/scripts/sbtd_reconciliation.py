"""Current-state reconciliation for an interrupted migration deployment.

A confirmed migration batch can reach a state where the deployment writes and
native smoke checks genuinely completed but the cumulative deployment evidence
was never saved (interrupted process, lost buffer, crashed writer). The
historical deploy execution can no longer be proven: no receipt exists and its
exit code is unknowable. This module records exactly what CAN be proven — a
fresh, fully revalidated observation of the current state — as new, explicitly
typed deployment evidence at a new path.

Truthfulness contract (no historical fabrication):

* ``payload.reconciliation.kind`` is ``"current-state"`` and
  ``historical_execution`` is ``"unknown"``. With this metadata present, a
  ``succeeded`` status means the current postconditions were observed and
  accepted NOW; it never claims the original deployment process was observed
  to exit 0, and no new target writes occurred while reconciling.
* Every resource result is derived, never caller-supplied: ``before`` is the
  sealed phase requirement, proven by the exact retained original at the
  deterministic deploy backup path (or by planned absence, which must not
  have invented a backup); ``after`` is the freshly measured current state,
  proven equal to the deterministic declared outcome (re-rendered
  configuration, exact canonical copy source, or a validated native graph).
* The evidence window (``started_at``/``finished_at``) covers only this
  observation: fresh native smoke reports are produced inside it and no
  historical timestamps or exit codes are guessed.
* Writes are limited to fresh private smoke reports and the single new
  evidence document. The missing historical path is never written. Any failed
  check fails closed: truthful fresh smoke artifacts may remain, but no
  accepted evidence is persisted.

This producer never calls deployment writers (execute_resource,
execute_migration_deployment, build_project_graph, apply_migration, recovery
or cleanup paths) and never reseals the manifest or changes versions/pins.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

import onboard_contracts as contracts
import sbtd_graft_deployment as deployment
from sbtd_migration_files import (
    read_file,
    require_private_directory,
    save_document,
    snapshot,
)

_ABSENT = {"type": "absent", "checksum": None}
_HOST_CONFIG_SELECTORS = {"graft-mcp", "graft-hooks", "graft-omp-mcp"}


def _fail(code: str, message: str, exit_code: int = 2) -> NoReturn:
    raise contracts.ContractError(code, message, exit_code=exit_code)


def _check_candidate_path(
    label: str,
    candidate: Path,
    *,
    private: Path,
    reserved: Sequence[Path],
    protected: Sequence[tuple[Path, bool]],
) -> None:
    """One evidence path: new, private, physical, disjoint from all managed state."""
    if (
        not candidate.is_absolute()
        or candidate.resolve() != candidate
        or candidate == private
        or not candidate.is_relative_to(private)
    ):
        _fail(
            "private-scope",
            f"the {label} evidence path must be a new physical path inside the manifest directory",
        )
    require_private_directory(candidate.parent)
    for path in reserved:
        if contracts._publication_paths_overlap(str(candidate), str(path)):
            _fail(
                "private-scope",
                f"the {label} evidence path overlaps a declared or protected object",
            )
    for protected_path, is_directory in protected:
        if contracts._publication_paths_overlap(str(candidate), str(protected_path)):
            _fail(
                "private-scope",
                f"the {label} evidence path overlaps a protected predecessor object",
            )


def _require_original_state(backup_path: Path, expected: Mapping[str, Any]) -> None:
    if snapshot(backup_path) != expected:
        _fail(
            "state-conflict" if expected["type"] == "absent" else "original-unavailable",
            "a retained deployment original or an absent original slot changed",
            2 if expected["type"] == "absent" else 3,
        )


def _observe_resource(
    operation: Mapping[str, Any],
    *,
    expected: Mapping[str, Any],
    backup_path: Path,
    bindings: Sequence[Mapping[str, Any]],
    install_template: bool,
    approved_body: bytes | None,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Derive one truthful result from the retained original and live state.

    Nothing is written. A non-absent sealed before-state must still exist as
    the exact deterministic original below the private vault; an absent
    before-state must not have invented one. The current target bytes must
    equal the deterministic declared outcome of the sealed operation.
    """
    target = Path(operation["target"])
    _require_original_state(backup_path, expected)
    backup_ref = (
        None if expected["type"] == "absent"
        else {"path": str(backup_path), "state": dict(expected)}
    )
    kind = operation["change"]["kind"]
    if (
        kind in {"build-graft", "configure-graft"}
        and operation["change"]["source_ref"] != policy
    ):
        _fail(
            "ownership-conflict",
            "the deployment policy does not match this runtime",
        )
    if kind == "configure-graft":
        # The exact retained original bytes are the render base, never live
        # bytes; a directory before-state cannot render and fails closed.
        before_bytes = (
            b"" if expected["type"] == "absent" else read_file(backup_path, expected)
        )
        # Live size describes the post-state here, not whether the original
        # was absent; the OMP renderer must not treat an empty file as absence.
        if (
            operation["selector"] == "graft-omp-mcp"
            and expected["type"] == "file"
            and not before_bytes
        ):
            _fail("invalid-json", "the active OMP MCP configuration is not strict JSON")
        candidate = deployment.render_configuration(
            operation,
            before_bytes,
            bindings,
            install_template=install_template,
            approved_body=approved_body,
        )
        # A no-op candidate leaves the sealed before-state as the declared
        # outcome: an inherited user-wide equivalent intentionally keeps an
        # absent target absent. Only a changed candidate writes file bytes.
        expected_after = (
            dict(expected)
            if candidate == before_bytes
            else {
                "type": "file",
                "checksum": hashlib.sha256(candidate).hexdigest(),
            }
        )
        current = snapshot(target)
        if current != expected_after:
            _fail(
                "state-conflict",
                "the current resource state is not the declared deployment outcome",
            )
        after = current
    elif kind in {"copy-file", "copy-directory"}:
        source = operation["change"]["source_ref"]
        if snapshot(Path(source["path"])) != source["state"]:
            _fail(
                "state-conflict",
                "a canonical installation source changed after planning",
            )
        current = snapshot(target)
        if current != source["state"]:
            _fail(
                "state-conflict",
                "the current resource state is not the declared deployment outcome",
            )
        after = current
    elif kind == "build-graft":
        current = snapshot(target)
        if current["type"] != "directory":
            _fail(
                "state-conflict",
                "the declared native graph is missing or not an ordinary directory",
            )
        after = current
    else:
        _fail("unsupported-operation", "the deployment operation is not supported")
    return {
        "phase": "deploy",
        "resource_id": operation["resource_id"],
        "operation_ids": [operation["operation_id"]],
        "dependent_projects": list(operation["dependent_projects"]),
        "status": "succeeded",
        "backup_ref": backup_ref,
        "before": dict(expected),
        "after": after,
        "error": None,
    }


def _require_apply_outcomes(
    operations: Sequence[Mapping[str, Any]],
    applied_results: Mapping[str, Any],
    observed: Mapping[str, Mapping[str, Any]],
) -> None:
    """Apply-only drift gate: receipt outcomes must still hold live.

    Every successful apply target not superseded by a fresh deploy
    observation is compared with its receipt after-state, regardless of
    runtime version equality; deploy-observed resources are proven by their
    own current-state observation instead. Runs before smoke and again
    before publication so a mutating native check fails closed.
    """
    for operation in operations:
        if operation.get("phase") != "apply":
            continue
        resource_id = operation["resource_id"]
        if resource_id in observed:
            continue
        result = applied_results.get(resource_id)
        if (
            result is None
            or result.get("status") != "succeeded"
            or result.get("after") is None
        ):
            _fail(
                "state-conflict",
                "a declared apply resource lacks a complete successful receipt outcome",
            )
        if snapshot(Path(operation["target"])) != result["after"]:
            _fail(
                "state-conflict",
                "an applied resource no longer matches its receipt outcome",
            )


def reconcile_deployment(
    manifest_path: Path,
    apply_path: Path,
    missing_path: Path,
    output_path: Path,
    *,
    confirmed: bool = False,
) -> dict[str, Any]:
    """Record a fresh current-state observation as new typed deploy evidence.

    Requires explicit confirmation, the genuine original manifest bytes, a
    complete successful apply receipt, a truly absent historical deployment
    receipt, and a new non-overwriting output path inside the original
    manifest private directory. Returns the ordinary deployment result
    ``{"path": str, "evidence": document}``; the evidence carries
    ``payload.reconciliation`` current-state provenance. Every refusal raises
    a sanitized ContractError before any accepted evidence exists.
    """
    from sbtd_migration import (
        _check_reference,
        _check_source_backups,
        _check_stage_backups,
        _operations,
        _private_document,
        _protected_followup_ancestry,
        _require_reconciliation_provenance,
        _result_index,
        _source_backup_paths,
        _validate_context,
        _verified_runtime_lineage,
        runtime_versions,
    )

    if not confirmed:
        _fail(
            "confirmation-required",
            "current-state reconciliation requires its own explicit confirmation",
        )
    manifest_path = Path(manifest_path)
    apply_path = Path(apply_path)
    missing_path = Path(missing_path)
    output_path = Path(output_path)
    if contracts._publication_paths_overlap(str(missing_path), str(output_path)):
        _fail(
            "private-scope",
            "the new evidence path must be distinct from the missing historical path",
        )
    manifest, manifest_raw = _private_document(manifest_path, "manifest")
    applied, apply_raw = _private_document(apply_path, "apply_receipt")
    contracts.validate_declared_bindings(
        manifest,
        {"apply_receipt": applied},
        {"manifest": manifest_raw, "apply_receipt": apply_raw},
    )
    contracts._bind_success_gate(applied, {"applied", "already-complete"})
    started_at = datetime.now(timezone.utc).isoformat()
    if contracts._parse_timestamp(
        applied["payload"]["finished_at"]
    ) > contracts._parse_timestamp(started_at):
        _fail(
            "state-conflict",
            "the reconciliation clock predates its completed input evidence",
        )
    private = require_private_directory(manifest_path.parent)
    payload = manifest["payload"]
    declaration = payload["deployment"]
    operations = [
        operation
        for project in payload["projects"]
        for operation in project["private_operations"]
        if operation["phase"] == "deploy"
    ] + [
        operation
        for operation in payload["shared_operations"]
        if operation["phase"] == "deploy"
    ]
    if declaration is None or not operations:
        _fail(
            "missing-deployment-plan",
            "this manifest contains no declared deployment operations",
        )
    vault = Path(payload["backup_root"])
    applied_results = _result_index(applied)
    reserved = [manifest_path, apply_path]
    reserved.extend(Path(operation["target"]) for operation in _operations(manifest))
    reserved.extend(_source_backup_paths(manifest).values())
    # Every sealed manifest input is reserved, including absent OMP
    # configuration inputs: new evidence may never equal or contain one.
    reserved.extend(
        Path(reference["path"])
        for reference in contracts._manifest_input_references(payload)
    )
    reserved.extend(
        Path(result["backup_ref"]["path"])
        for result in applied_results.values()
        if result["backup_ref"] is not None
    )
    reserved.extend(
        vault / manifest["manifest_id"] / "deploy" / operation["resource_id"]
        for operation in operations
    )
    protected = _protected_followup_ancestry(manifest)
    for label, candidate in (("missing historical", missing_path), ("output", output_path)):
        _check_candidate_path(
            label, candidate, private=private, reserved=reserved, protected=protected
        )
    if snapshot(missing_path) != _ABSENT:
        _fail(
            "state-conflict",
            "the historical deployment receipt is not absent; reconciliation would duplicate it",
        )
    if snapshot(output_path) != _ABSENT:
        _fail("state-conflict", "the reconciliation evidence target already exists")

    runtime = deployment.verified_runtime()
    policy = deployment.policy_reference()
    from sbtd_graft_entry import validate_build_scope

    roots = [Path(project["root"]) for project in payload["projects"]]
    for root in roots:
        validate_build_scope(root)
    from onboard import resolve_global_skills_dir

    full_installation = any(
        operation["selector"] in _HOST_CONFIG_SELECTORS
        for operation in payload["shared_operations"]
    )
    launcher_package = (
        resolve_global_skills_dir()[0] / "sbtd-workflow-onboard"
        if full_installation
        else deployment._PACKAGE
    )
    bindings = deployment.launch_bindings(
        roots, runtime, package_root=launcher_package
    )
    launcher_state = snapshot(deployment._PACKAGE)
    if any(operation["selector"] in _HOST_CONFIG_SELECTORS for operation in operations):
        installed_package = Path(bindings[0]["launcher"]).parents[1]
        if snapshot(installed_package) != launcher_state:
            _fail(
                "runtime-unavailable",
                "the canonical installed launcher is missing or has drifted",
            )

    from sbtd_migration_plan import approved_agents_provenance

    # Signature-approved project routing keeps its exact approved body; the
    # re-proved manifest chain authorizes preservation, never live bytes.
    _origin, approved_bodies = approved_agents_provenance(manifest)
    install_template = payload.get("followup") is None
    resolution = contracts.resolution_stage_results(
        payload, {"apply": applied_results}
    )
    _check_source_backups(manifest)
    results: dict[str, Mapping[str, Any]] = {}
    expected_before: dict[str, Mapping[str, Any]] = {}
    for operation in operations:
        expected = contracts._expected_before(
            operation["before_requirement"], resolution
        )
        if expected is None:
            _fail(
                "state-conflict",
                "a declared deployment resource has no proven before requirement",
            )
        expected_before[operation["resource_id"]] = expected
        results[operation["resource_id"]] = _observe_resource(
            operation,
            expected=expected,
            backup_path=vault
            / manifest["manifest_id"]
            / "deploy"
            / operation["resource_id"],
            bindings=bindings,
            install_template=install_template,
            approved_body=approved_bodies.get(operation["target"]),
            policy=policy,
        )

    # Closed OMP input paths: any drift since sealing must chain through
    # receipt-proven apply/deploy outcomes, never through silent live edits.
    if declaration["platform"] == "omp":
        from onboard import user_home
        from sbtd_omp_sources import discover_omp_sources

        discovered = discover_omp_sources(roots, home=user_home(), environ=os.environ)
        if declaration["inputs"] != discovered["inputs"]:
            deployment._require_proven_input_changes(
                payload,
                declaration["inputs"],
                discovered["inputs"],
                {"apply": applied_results, "deploy": results},
            )

    # Apply-only drift gate before smoke: successful apply targets without a
    # fresh deploy observation must still match their receipt after-states.
    _require_apply_outcomes(_operations(manifest), applied_results, results)

    # Fresh real native smoke per project inside this observation window; a
    # failed or incomplete check leaves its truthful artifacts but no evidence.
    reports: dict[str, Sequence[Mapping[str, Any]]] = {}
    for root in roots:
        try:
            reports[str(root)] = deployment.run_project_smoke(
                root, runtime, manifest_path.parent
            )
        except (contracts.ContractError, OSError, RuntimeError, ValueError):
            _fail(
                "report-unavailable",
                "a fresh native graph check did not complete; no evidence was recorded",
                3,
            )

    # The native check is expected to be read-only. Re-validate every observed
    # target, retained original and source before trusting the fresh window.
    for operation in operations:
        result = results[operation["resource_id"]]
        if snapshot(Path(operation["target"])) != result["after"]:
            _fail(
                "state-conflict",
                "the native check mutated an observed deployment resource",
            )
        _require_original_state(
            vault / manifest["manifest_id"] / "deploy" / operation["resource_id"],
            expected_before[operation["resource_id"]],
        )
    _check_source_backups(manifest)

    reconciliation = {
        "kind": "current-state",
        "historical_execution": "unknown",
        "manifest_ref": {"path": str(manifest_path), "state": snapshot(manifest_path)},
        "apply_receipt_ref": {"path": str(apply_path), "state": snapshot(apply_path)},
        "missing_deployment_evidence": {
            "path": str(missing_path),
            "state": snapshot(missing_path),
        },
        "runtime_versions": runtime_versions(),
    }
    if reconciliation["runtime_versions"]["onboard"] != payload["tool_versions"]["onboard"]:
        reconciliation["observer_lineage"] = _verified_runtime_lineage()
    context = deployment.DeploymentContext(
        manifest_path=manifest_path,
        output_path=output_path,
        manifest=manifest,
        applied=applied,
        previous=None,
        started_at=started_at,
        expected_before=expected_before,
        manifest_raw=manifest_raw,
        apply_raw=apply_raw,
    )
    evidence = deployment._assemble_deployment_evidence(
        context, results, reports, failed_smokes=set(), reconciliation=reconciliation
    )
    if evidence["payload"]["status"] != "succeeded":
        _fail(
            "report-acceptance",
            "the current state did not pass deployment acceptance; no evidence was recorded",
            3,
        )

    # Revalidate the complete context against the assembled, provenance-marked
    # evidence: runtime lineage, revisions, physical aliases, input references
    # and retained backups, all through the ordinary validators.
    _validate_context(manifest_path, manifest, previous=applied, deployment=evidence)

    # Validate the proposed result before the single write: a reconciled
    # record never claims its own cited missing historical path, and no
    # invalid deployment result is ever persisted.
    deployment._require_output_clear_of_missing(output_path, evidence["payload"])
    result = contracts.validate_deployment_result(
        {"path": str(output_path), "evidence": evidence}
    )
    provenance = _require_reconciliation_provenance(manifest, evidence)
    for project in payload["projects"]:
        no_touch = project.get("agents_no_touch")
        if no_touch is not None:
            provenance += (no_touch["target"], no_touch["template"])
    # Final snapshot-only pass: no lineage parsing after observed artifacts.
    _check_source_backups(manifest)
    _check_stage_backups({"apply": applied_results, "deploy": _result_index(evidence)})
    # Apply-only drift gate before publication: the native check window must
    # not have mutated any receipt-proven apply target either.
    _require_apply_outcomes(_operations(manifest), applied_results, results)
    for operation in operations:
        if snapshot(Path(operation["target"])) != results[operation["resource_id"]]["after"]:
            _fail(
                "state-conflict",
                "a deployment resource changed before evidence publication",
            )
        _require_original_state(
            vault / manifest["manifest_id"] / "deploy" / operation["resource_id"],
            expected_before[operation["resource_id"]],
        )
    for project in evidence["payload"]["projects"]:
        for reference in project["report_refs"]:
            if snapshot(Path(reference["path"])) != reference["state"]:
                _fail(
                    "state-conflict",
                    "a fresh report changed before evidence publication",
                )
    for reference in provenance:
        _check_reference(reference)
    if snapshot(output_path) != _ABSENT:
        _fail(
            "state-conflict",
            "the reconciliation evidence target appeared before publication",
        )
    save_document(output_path, evidence, private_root=manifest_path.parent)
    return result
