"""Read-only migration verification and deployment report acceptance.

Boundary (docs/prd/sbtd-workflow-v2-migration-runtime.md, main PRD 10.2/11):

- ``verify_migration`` consumes the explicit private manifest, apply receipt
  and deployment evidence with the strict codec, proves document IDs, raw
  bindings, closure and complete predecessor success before observing
  anything, then checks actual resources against their last completed phase
  states, every retained original backup, the private source originals, the
  approved publication projections and the declared cleanup candidates. It
  never writes projects, HOME or the vault, never deploys, runs no smoke and
  performs no receipt discovery; the sealed verification is returned inside
  the read-only envelope for the authorized caller to store privately. When
  the bound deployment evidence carries current-state reconciliation
  provenance, the verification payload exposes
  ``acceptance_basis = "current-state"``; ordinary executed-origin evidence
  keeps the historical shape with no marker.
- ``validate_deployment_reports`` re-validates the native validation-evidence
  v1/v2 envelopes and their raw runner reports for one supplied deployment
  project record. The caller owns actual project Git and filesystem truth;
  this helper only checks the supplied scope facts against readable,
  checksum-matching report references bound to the current deployment
  attempt. A passing native envelope alone is not acceptance: the current
  attempt window, the raw API smoke exit status, the project root/ref/HEAD
  binding, the verified environment and the non-mock mode are all checked.
  Non-API reports remain non-acceptance-bearing but must be v2 typed reports
  with a passed locator-bound case; v1/untyped auxiliary formats are rejected
  rather than parsed generically. JSON shape or hash equality is never
  execution or host authenticity proof, and fixture-based checks never prove
  a real deployment happened.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

import onboard_contracts as contracts
import sbtd_migration as migration
from sbtd_migration_files import read_file, snapshot
from sbtd_project import _reject_json_duplicates

__all__ = ["validate_deployment_reports", "verify_migration"]

_PACKAGE = Path(__file__).resolve().parents[1]
_EVIDENCE_VALIDATOR = (
    _PACKAGE
    / "templates"
    / "skills"
    / "project-validation"
    / "scripts"
    / "validate_validation_evidence.py"
)

# Genuine, non-mock runner modes from the unchanged native evidence schema;
# contract-backed/app-mocked/blocked/not-needed runs cannot prove acceptance.
_GENUINE_MODES = frozenset({"full-stack", "smoke-only", "backend-only"})

_PROJECT_OUTCOME = {
    "verified": ("", ""),
    "failed": (
        "actual resources or bound deployment reports differ from the proven migration state",
        "Inspect the private evidence, reconcile or repeat deployment, then repeat verification; do not clean up.",
    ),
    "blocked": (
        "not every required state could be observed",
        "Restore access to the declared evidence and repeat verification before cleanup.",
    ),
}
_VERIFY_OUTCOME = {
    "verified": (
        "",
        "Review the recorded cleanup candidates and confirm cleanup explicitly with this verification_id.",
    ),
    "failed": (
        "not every project passed migration acceptance",
        "Inspect the private per-project evidence; preserve originals and do not clean up.",
    ),
    "blocked": (
        "verification could not observe every required state",
        "Resolve the observation gap and repeat verification before cleanup.",
    ),
}
_VERIFY_EXIT = {"verified": 0, "blocked": 2, "failed": 3}


def _fail(code: str, message: str, exit_code: int = 2) -> NoReturn:
    raise contracts.ContractError(code, message, exit_code=exit_code)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="microseconds")


def _evidence_validator() -> Any:
    """Lazy self-contained load of the unchanged native evidence validator."""
    try:
        spec = importlib.util.spec_from_file_location(
            "validate_validation_evidence", _EVIDENCE_VALIDATOR
        )
        if spec is None or spec.loader is None:
            raise ImportError
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except (ImportError, OSError):
        _fail(
            "validator-unavailable",
            "the native validation-evidence validator is unavailable",
        )


def _reject_report_constant(literal: str) -> NoReturn:
    raise ValueError


def _decode_report(content: bytes) -> Any:
    """Lenient JSON for report bytes; strict UTF-8, no duplicate keys/non-finite."""
    try:
        text = bytes(content).decode("utf-8", errors="strict")
        return json.loads(
            text,
            object_pairs_hook=_reject_json_duplicates,
            parse_constant=_reject_report_constant,
        )
    except (ValueError, RecursionError, UnicodeError, contracts.ContractError):
        return None


def _attempt_time(container: Mapping[str, Any], key: str) -> Any:
    try:
        parsed = contracts._parse_timestamp(container[key])
        timestamp, _fraction = parsed
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("timestamp must carry an explicit UTC offset")
        return parsed
    except (KeyError, TypeError, ValueError, AttributeError):
        _fail("unexpected-type", "deployment scope fields are missing or invalid")


def _report_path(root: Path, recorded: Any) -> Path:
    if not isinstance(recorded, str) or not recorded:
        _fail("unexpected-type", "deployment report paths are missing or invalid")
    candidate = Path(recorded)
    return candidate if candidate.is_absolute() else root / candidate


def _bound_reports(project_record: Mapping[str, Any]) -> dict[str, bytes]:
    """Actual nofollow bytes of every declared report ref, checksum-bound."""
    refs = project_record.get("report_refs")
    if not isinstance(refs, list):
        _fail("unexpected-type", "deployment report references are missing or invalid")
    bound: dict[str, bytes] = {}
    for reference in refs:
        if (
            not isinstance(reference, Mapping)
            or not isinstance(reference.get("path"), str)
            or not isinstance(reference.get("state"), Mapping)
        ):
            _fail(
                "unexpected-type",
                "deployment report references are missing or invalid",
            )
        try:
            bound[reference["path"]] = read_file(
                Path(reference["path"]), reference.get("state")
            )
        except contracts.ContractError:
            _fail(
                "report-unavailable",
                "a bound deployment report is unavailable or changed",
                3,
            )
    return bound


def _accept_raw_smoke(
    content: bytes,
    report: Mapping[str, Any],
    envelope: Mapping[str, Any],
    *,
    started: Any,
    finished: Any,
    root: Path,
    source_ref: Any,
    head: Any,
) -> None:
    """Raw API runner JSON: real exit, current attempt, exact scope, non-mock."""
    value = _decode_report(content)
    if not isinstance(value, dict):
        _fail("report-acceptance", "an API smoke raw report is not a JSON object", 3)
    exit_code = value.get("exitCode")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int) or exit_code != 0:
        _fail("report-acceptance", "an API smoke raw run did not exit cleanly", 3)
    if value.get("timedOut") is not False:
        _fail("report-acceptance", "an API smoke raw run timed out", 3)
    command = value.get("command")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(item, str) and item for item in command)
    ):
        _fail(
            "report-acceptance",
            "an API smoke raw run lacks its executed command",
            3,
        )
    if not isinstance(value.get("stdout"), str) or not isinstance(
        value.get("stderr"), str
    ):
        _fail(
            "report-acceptance",
            "an API smoke raw run lacks its captured output",
            3,
        )
    process_exit = value.get("processExitCode")
    if "processExitCode" in value and (
        isinstance(process_exit, bool)
        or not isinstance(process_exit, int)
        or process_exit != 0
    ):
        _fail(
            "report-acceptance",
            "an API smoke raw run process exit contradicts its clean exit",
            3,
        )
    raw_started = _attempt_time(value, "startedAt")
    raw_finished = _attempt_time(value, "finishedAt")
    if raw_started > raw_finished or raw_started < started or raw_finished > finished:
        _fail(
            "report-acceptance",
            "an API smoke raw run is outside the current deployment attempt",
            3,
        )
    if value.get("projectRoot") != str(root):
        _fail("report-acceptance", "an API smoke raw run is bound to another root", 3)
    if value.get("sourceRef") != source_ref or value.get("sourceCommit") != head:
        _fail(
            "report-acceptance",
            "an API smoke raw run is bound to another revision",
            3,
        )
    if (
        value.get("environmentAlignment") != "verified"
        or value.get("mockStrategy") != "none"
        or value.get("e2eMode") != report["mode"]
    ):
        _fail(
            "report-acceptance",
            "an API smoke raw run is not a verified non-mock smoke",
            3,
        )
    repository = envelope["repository"]
    provenance = {
        "repositoryKey": repository.get("repositoryKey"),
        "sourceRef": repository.get("sourceRef"),
        "sourceCommit": repository.get("sourceCommit"),
        "worktreeState": repository.get("worktreeState"),
        "sourceRevision": envelope.get("sourceRevision"),
        "evidenceSource": envelope.get("evidenceSource"),
        "trigger": envelope.get("trigger"),
        "environmentAlignment": envelope.get("environmentAlignment"),
        "evidencePublication": envelope.get("evidencePublication"),
        "e2eMode": envelope.get("e2eMode"),
        "mockStrategy": envelope.get("mockStrategy"),
    }
    if any(value.get(key) != expected for key, expected in provenance.items()):
        _fail(
            "report-acceptance",
            "an API smoke raw run is not bound to the enclosing envelope",
            3,
        )


def _accept_auxiliary_report(
    content: bytes,
    report: Mapping[str, Any],
    envelope: Mapping[str, Any],
    validator: Any,
) -> None:
    """Require a v2 typed report and locator-bound passing case, not a smoke."""
    if envelope.get("schemaVersion") != 2:
        _fail(
            "report-acceptance",
            "an auxiliary deployment report has no typed format contract",
            3,
        )
    report_format = report.get("reportFormat")
    if report_format not in {"junit-xml-v1", "playwright-json-v1"}:
        _fail(
            "report-acceptance",
            "an auxiliary deployment report does not declare a supported typed format",
            3,
        )
    report_sha = report["sha256"].lower()
    links = [
        link
        for link in envelope["scenarioLinks"]
        if link["reportSha256"].lower() == report_sha
    ]
    if not links:
        _fail(
            "report-acceptance",
            "an auxiliary deployment report has no source locator provenance",
            3,
        )
    try:
        cases = (
            validator.parse_junit(content)
            if report_format == "junit-xml-v1"
            else validator.parse_playwright(content)
        )
        locators = {
            locator["sourceLocatorDigest"]: locator
            for locator in envelope["sourceLocators"]
        }
        for link in links:
            locator = locators[link["sourceLocatorDigest"]]
            if any(
                locator.get(key) != envelope["repository"].get(key)
                for key in ("repositoryKey", "sourceRef")
            ):
                _fail(
                    "report-acceptance",
                    "an auxiliary source locator belongs to another repository or revision",
                    3,
                )
            matched = (
                validator.match_junit(cases, link["testCaseSelector"])
                if report_format == "junit-xml-v1"
                else validator.match_playwright(cases, link["testCaseSelector"])
            )
            if len(matched) != 1 or matched[0]["outcome"] != "passed":
                _fail(
                    "report-acceptance",
                    "an auxiliary deployment report does not prove its passed case",
                    3,
                )
            if validator.unique_binding(matched[0]) != validator.source_locator_digest(
                locator
            ):
                _fail(
                    "report-acceptance",
                    "an auxiliary deployment report is bound to another source locator",
                    3,
                )
    except (KeyError, TypeError, validator.EvidenceError):
        _fail(
            "report-acceptance",
            "an auxiliary deployment report failed typed content or provenance validation",
            3,
        )


def _accept_report(
    report: Any,
    envelope: Mapping[str, Any],
    validator: Any,
    *,
    started: Any,
    finished: Any,
    root: Path,
    source_ref: Any,
    head: Any,
    bound: Mapping[str, bytes],
) -> bool:
    """One native report entry; returns True for a genuine API smoke."""
    if not isinstance(report, Mapping):
        _fail("unexpected-type", "deployment report entries are missing or invalid")
    if report.get("status") != "passed":
        _fail(
            "report-acceptance",
            "a deployment report did not pass its declared run",
            3,
        )

    content = bound.get(str(_report_path(root, report.get("path"))))
    if content is None:
        _fail(
            "report-acceptance",
            "a deployment report is not one of the declared bound references",
            3,
        )
    sha256 = report.get("sha256")
    if (
        not isinstance(sha256, str)
        or hashlib.sha256(content).hexdigest() != sha256.lower()
    ):
        _fail("report-acceptance", "a deployment report digest does not match", 3)
    summary_path = str(_report_path(root, report.get("summaryMd")))
    if bound.get(summary_path) is None:
        _fail(
            "report-unavailable",
            "a deployment report summary is not a declared bound reference",
            3,
        )

    if report.get("testType") != "api":
        _accept_auxiliary_report(content, report, envelope, validator)
        return False
    if report.get("mode") not in _GENUINE_MODES:
        _fail(
            "report-acceptance",
            "an API deployment report did not pass a genuine non-mock run",
            3,
        )
    _accept_raw_smoke(
        content,
        report,
        envelope,
        started=started,
        finished=finished,
        root=root,
        source_ref=source_ref,
        head=head,
    )
    return True


def _accept_envelope(
    validator: Any,
    envelope: Mapping[str, Any],
    *,
    started: Any,
    finished: Any,
    root: Path,
    source_ref: Any,
    head: Any,
    bound: Mapping[str, bytes],
) -> bool:
    """Native v1/v2 validation plus current-attempt scope acceptance."""
    try:
        if envelope["schemaVersion"] == 1:
            validator.validate_v1(envelope)
        else:
            validator.validate_v2(envelope, root)
    except validator.EvidenceError as error:
        if error.code == "VALIDATOR_UNAVAILABLE":
            _fail(
                "validator-unavailable",
                "the native validation-evidence validator dependency is unavailable",
            )
        _fail("report-acceptance", "native deployment evidence failed validation", 3)
    created = _attempt_time(envelope, "createdAt")
    if created < started or created > finished:
        _fail(
            "report-acceptance",
            "native deployment evidence is outside the current deployment attempt",
            3,
        )
    if (
        envelope.get("environmentAlignment") != "verified"
        or envelope.get("mockStrategy") != "none"
        or envelope.get("e2eMode") not in _GENUINE_MODES
    ):
        _fail(
            "report-acceptance",
            "deployment evidence is not environment-verified non-mock smoke",
            3,
        )
    repository = envelope.get("repository")
    if not isinstance(repository, Mapping):
        _fail("unexpected-type", "deployment evidence repository is missing")
    commit = repository.get("sourceCommit")
    if (
        repository.get("sourceRef") != source_ref
        or (commit.lower() if isinstance(commit, str) else None) != head
    ):
        _fail(
            "report-acceptance",
            "deployment evidence is bound to another revision",
            3,
        )
    api_smoke = False
    for report in envelope["reports"]:
        api_smoke |= _accept_report(
            report,
            envelope,
            validator,
            started=started,
            finished=finished,
            root=root,
            source_ref=source_ref,
            head=head,
            bound=bound,
        )
    return api_smoke


def validate_deployment_reports(
    deployment_payload: Mapping[str, Any],
    project_record: Mapping[str, Any],
    *,
    epoch_started: Any = None,
) -> None:
    """Re-validate one project's bound deployment reports against the attempt.

    ``deployment_payload`` supplies the current attempt window; ``project_record``
    supplies the declared root/source_ref/head scope and report_refs. A first
    attempt must produce every report inside its exact window; a cumulative
    retry (non-null ``previous_deployment_id``) may retain earlier reports
    within the same bound apply epoch, so the caller passes that epoch's lower
    bound (the bound apply receipt's finished_at) separately as
    ``epoch_started`` while the deployment bytes stay immutable. Every
    reference must still be the exact recorded file, at least one native
    validation-evidence v1/v2 envelope must pass its own unchanged schema
    validation, and at least one genuine non-mock API smoke raw run must be
    bound to this root, revision and window. Sanitized ContractError only.
    """
    if not isinstance(deployment_payload, Mapping) or not isinstance(
        project_record, Mapping
    ):
        _fail(
            "unexpected-type", "deployment payload and project record must be mappings"
        )
    started = _attempt_time(deployment_payload, "started_at")
    finished = _attempt_time(deployment_payload, "finished_at")
    if started > finished:
        _fail("unexpected-type", "the deployment attempt window is invalid")
    if deployment_payload.get("previous_deployment_id") is not None:
        if not isinstance(epoch_started, str):
            _fail("unexpected-type", "the bound apply epoch is missing or invalid")
        started = _attempt_time({"epoch_started": epoch_started}, "epoch_started")
        if started > finished:
            _fail("unexpected-type", "the bound apply epoch is invalid")
    try:
        root = Path(project_record["root"])
        source_ref = project_record["source_ref"]
        head = project_record["head"]
    except (KeyError, TypeError):
        _fail("unexpected-type", "deployment scope fields are missing or invalid")
    # Native schemas keep their required string ref. These explicit labels
    # represent branchlessness, not invented branch names; outer refs stay null.
    if source_ref is None:
        source_ref = "HEAD" if head is not None else "non-git"
    bound = _bound_reports(project_record)
    validator = _evidence_validator()
    envelopes = [
        value
        for value in (_decode_report(content) for content in bound.values())
        if isinstance(value, dict)
        and value.get("schemaVersion") in (1, 2)
        and isinstance(value.get("reports"), list)
    ]
    if not envelopes:
        _fail(
            "report-unavailable",
            "no native validation-evidence envelope is bound to this project",
            3,
        )
    api_smoke = False
    for envelope in envelopes:
        api_smoke |= _accept_envelope(
            validator,
            envelope,
            started=started,
            finished=finished,
            root=root,
            source_ref=source_ref,
            head=head,
            bound=bound,
        )
    if not api_smoke:
        _fail(
            "report-acceptance",
            "no genuine API smoke report is bound to this project",
            3,
        )

def _check_approved_routing(manifest: Mapping[str, Any]) -> None:
    """Reopen each approved candidate; drift is a conflict, not success.

    A target this batch deployed through its declared ``graft-agents``
    operation must equal the rendered approved projection — the re-proved
    approved body plus exactly the managed fence. Only then is the shared
    provenance resolver consulted (a successor batch is followed to its
    revalidated predecessor origin). A current-manifest approved target
    without a deployment keeps the raw paused-candidate comparison and its
    drift failure unchanged; an ancestor batch's other approved targets
    (e.g. global routing) are legitimately superseded by this batch's
    declared deployment, and their outcomes stay pinned by the stage
    receipts and retained-resource checks instead.
    """
    rendered = {
        operation["target"]
        for operation in migration._operations(manifest)
        if operation["phase"] == "deploy" and operation["selector"] == "graft-agents"
    }
    if rendered:
        from sbtd_codex_wiring import project_agents_candidate
        from sbtd_migration_plan import approved_agents_provenance

        origin, bodies = approved_agents_provenance(manifest)
    else:
        origin, bodies = manifest, {}
    for operation in migration._operations(origin):
        if operation["selector"] != "approved-routing-replacement":
            continue
        target = operation["target"]
        if target in rendered:
            body = bodies.get(target)
            expected = (
                None
                if body is None
                else {
                    "type": "file",
                    "checksum": hashlib.sha256(
                        project_agents_candidate(body)
                    ).hexdigest(),
                }
            )
        elif origin is manifest:
            candidate = operation["change"]["source_ref"]
            expected = snapshot(Path(candidate["path"]))
        else:
            continue
        if expected is None or snapshot(Path(target)) != expected:
            migration._fail(
                "approved-routing-drift",
                "an approved routing file no longer matches its candidate",
            )



def verify_migration(
    manifest_path: Path,
    apply_receipt_path: Path,
    deployment_evidence_path: Path,
) -> tuple[dict[str, Any], int]:
    """Read-only acceptance of one migrated batch; returns (envelope, exit_code).

    Hard input, binding, stale-context or preservation violations raise a
    sanitized ContractError (2 = input/conflict, 3 = digest/preservation).
    Per-project acceptance outcomes are recorded independently in a sealed
    verification bound to the manifest, the apply receipt and the deployment
    evidence raw bytes; nothing is written and no receipt is discovered.
    """
    manifest_path = Path(manifest_path)
    manifest, manifest_raw = migration._private_document(manifest_path, "manifest")
    apply_document, apply_raw = migration._private_document(
        Path(apply_receipt_path), "apply_receipt"
    )
    deployment, deployment_raw = migration._private_document(
        Path(deployment_evidence_path), "deployment_evidence"
    )
    documents = {"apply_receipt": apply_document, "deployment_evidence": deployment}
    raw_documents = {
        "manifest": manifest_raw,
        "apply_receipt": apply_raw,
        "deployment_evidence": deployment_raw,
    }
    contracts.validate_declared_bindings(manifest, documents, raw_documents)
    contracts._bind_success_gate(deployment, {"succeeded"})
    migration._validate_context(
        manifest_path, manifest, previous=apply_document, deployment=deployment
    )
    migration._check_source_backups(manifest)
    stage_results = {
        "apply": migration._result_index(apply_document),
        "deploy": migration._result_index(deployment),
    }
    migration._check_stage_backups(stage_results)
    _check_approved_routing(manifest)

    epoch_started = None
    if deployment["payload"].get("previous_deployment_id") is not None:
        epoch_started = apply_document["payload"]["finished_at"]

    payload = manifest["payload"]
    track_freshness = (
        deployment["payload"].get("reconciliation") is not None
        or payload.get("followup") is not None
    )
    observed_states: dict[str, Mapping[str, Any]] = {}
    private, shared, dependents, identity = contracts._declared_resources(payload)
    publications = {
        item["target_path"]: item["candidate_ref"]["state"]
        for item in payload["publication_decisions"]["items"]
        if item["decision"] != "private-only"
    }
    requirements = {
        (operation["phase"], operation["resource_id"]): operation["before_requirement"]
        for operation in migration._operations(manifest)
    }

    failed_roots: set[str] = set()
    blocked_roots: set[str] = set()
    for project in deployment["payload"]["projects"]:
        try:
            validate_deployment_reports(
                deployment["payload"], project, epoch_started=epoch_started
            )
        except contracts.ContractError as error:
            if error.code == "validator-unavailable":
                raise
            failed_roots.add(project["root"])
        except OSError:
            failed_roots.add(project["root"])

    cleanup_dependents: dict[str, set[str]] = {}
    for operation in payload["shared_operations"]:
        if operation["phase"] == "cleanup":
            cleanup_dependents.setdefault(operation["resource_id"], set()).update(
                operation["dependent_projects"]
            )
    shared_candidates: list[dict[str, Any]] = []
    for rid in sorted(shared, key=lambda item: identity[item][1]):
        phases = shared[rid]
        if "cleanup" not in phases:
            continue
        owner_kind, target = identity[rid]
        expected_type = "directory" if owner_kind == "directory" else "file"
        try:
            state = snapshot(Path(target))
            expected = contracts._expected_before(
                requirements[("cleanup", rid)], stage_results
            )
        except (contracts.ContractError, OSError, RuntimeError):
            blocked_roots.update(cleanup_dependents[rid])
            continue
        if track_freshness:
            observed_states[target] = state
        shared_candidates.append(
            {
                "resource_id": rid,
                "operation_ids": sorted(phases["cleanup"]),
                "target": target,
                "state": state,
                "dependent_projects": sorted(cleanup_dependents[rid]),
            }
        )
        if state["type"] not in {"absent", expected_type} or (
            expected is not None and state != expected
        ):
            failed_roots.update(cleanup_dependents[rid])

    projects: list[dict[str, Any]] = []
    for manifest_project in payload["projects"]:
        root = manifest_project["root"]
        drift = root in failed_roots
        blocked = root in blocked_roots
        retained_assets: list[dict[str, Any]] = []
        cleanup_candidates: list[dict[str, Any]] = []
        retained_resources = {
            rid: phases
            for rid, phases in private.get(root, {}).items()
            if "cleanup" not in phases or identity[rid][1] in publications
        }
        retained_resources.update(
            {
                rid: phases
                for rid, phases in shared.items()
                if root in dependents.get(rid, set())
                and ("cleanup" not in phases or identity[rid][1] in publications)
            }
        )
        for rid in sorted(retained_resources, key=lambda item: identity[item][1]):
            phases = retained_resources[rid]
            owner_kind, target = identity[rid]
            expected_type = "directory" if owner_kind == "directory" else "file"
            try:
                state = snapshot(Path(target))
            except (contracts.ContractError, OSError, RuntimeError):
                blocked = True
                continue
            if track_freshness:
                observed_states[target] = state
            if state["type"] != "absent":
                retained_assets.append({"path": target, "state": state})
            if state["type"] not in {"absent", expected_type}:
                drift = True
                continue
            if target in publications and state != publications[target]:
                drift = True
                continue
            completed = [phase for phase in phases if phase != "cleanup"]
            if completed:
                last_phase = max(completed, key=contracts._PHASE_ORDER.__getitem__)
                if last_phase in stage_results:
                    result = stage_results[last_phase].get(rid)
                    if (
                        result is None
                        or result["status"] != "succeeded"
                        or result["after"] != state
                    ):
                        drift = True
        declared_cleanup = {
            rid: phases["cleanup"]
            for rid, phases in private.get(root, {}).items()
            if "cleanup" in phases
        }
        for rid in sorted(declared_cleanup, key=lambda item: identity[item][1]):
            owner_kind, target = identity[rid]
            expected_type = "directory" if owner_kind == "directory" else "file"
            try:
                state = snapshot(Path(target))
                expected = contracts._expected_before(
                    requirements[("cleanup", rid)], stage_results
                )
            except (contracts.ContractError, OSError, RuntimeError):
                blocked = True
                continue
            if track_freshness:
                observed_states[target] = state
            cleanup_candidates.append(
                {
                    "resource_id": rid,
                    "operation_ids": sorted(declared_cleanup[rid]),
                    "target": target,
                    "state": state,
                    "dependent_projects": [root],
                }
            )
            if state["type"] not in {"absent", expected_type} or (
                expected is not None and state != expected
            ):
                drift = True
        status = "failed" if drift else "blocked" if blocked else "verified"
        reason, next_step = _PROJECT_OUTCOME[status]
        projects.append(
            {
                "root": root,
                "source_ref": manifest_project["source_ref"],
                "head": manifest_project["head"],
                "status": status,
                "reason": reason,
                "nextStep": next_step,
                "retained_assets": retained_assets,
                "cleanup_candidates": cleanup_candidates,
            }
        )

    status = contracts._aggregate(
        [project["status"] for project in projects],
        ("failed", "blocked"),
        "verified",
        None,
    )
    verification_payload: dict[str, Any] = {
        "manifest_id": manifest["manifest_id"],
        "apply_id": apply_document["apply_id"],
        "deployment_evidence_hash": hashlib.sha256(
            bytes(deployment_raw)
        ).hexdigest(),
        "status": status,
        "projects": projects,
        "shared_cleanup_candidates": shared_candidates,
        "verified_at": _now(),
    }
    if deployment["payload"].get("reconciliation") is not None:
        # The bound evidence is a provenance-marked current-state observation
        # of an interrupted deployment, not an executed-origin receipt; expose
        # that acceptance basis explicitly so downstream consumers and the
        # contract binding cannot mistake it for observed historical success.
        verification_payload["acceptance_basis"] = "current-state"
    verification = contracts.seal_document("verification", verification_payload)
    contracts.validate_declared_bindings(
        manifest, {**documents, "verification": verification}, raw_documents
    )
    reason, next_step = _VERIFY_OUTCOME[status]
    envelope = contracts.make_envelope(
        "migration",
        "verify",
        status,
        migration._summary_projects(verification),
        reason,
        next_step,
        verification,
        {
            "manifest_id": manifest["manifest_id"],
            "verification_id": verification["verification_id"],
        },
    )
    provenance = migration._require_reconciliation_provenance(manifest, deployment)
    if status == "verified" and track_freshness:
        for project in payload["projects"]:
            no_touch = project.get("agents_no_touch")
            if no_touch is not None:
                provenance += (no_touch["target"], no_touch["template"])
        # Refresh the same observed states, including absent resources, after
        # all semantic/lineage work. Previously failed outcomes stay unchanged.
        migration._check_source_backups(manifest)
        migration._check_stage_backups(stage_results)
        for target, state in observed_states.items():
            migration._check_reference({"path": target, "state": state})
        for project in deployment["payload"]["projects"]:
            for reference in project["report_refs"]:
                migration._check_reference(reference)
    for reference in provenance:
        migration._check_reference(reference)
    return envelope, _VERIFY_EXIT[status]
