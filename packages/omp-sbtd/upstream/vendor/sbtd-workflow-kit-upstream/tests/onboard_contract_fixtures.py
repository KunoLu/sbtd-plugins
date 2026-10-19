"""Valid onboard-contract fixture family builders shared by tests and Main.

``build_fixture_family()`` returns one coherent, fully bound document family
(publication decisions, manifest, apply receipt, deployment evidence,
verification, cleanup receipt, recovery plan/receipt and both envelope kinds)
built through the real ``onboard_contracts`` public API, so every document is
schema-valid, semantically consistent and canonically sealed.

Main can serialize the family for installed-copy smoke testing:

    python3 tests/onboard_contract_fixtures.py <output-dir>

Each ``<kind>.json`` file is written as exact canonical bytes (no trailing
newline), so the file bytes double as ``raw_documents`` values for
``validate_declared_bindings`` (e.g. the verification payload's
``deployment_evidence_hash`` is the SHA-256 of ``deployment_evidence.json``).
Fixtures prove contract structure and declared bindings only; they are not
migration, deployment, recovery or host proof.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
_MODULE_PATH = ROOT / "sbtd-workflow-onboard" / "scripts" / "onboard_contracts.py"
_spec = importlib.util.spec_from_file_location("onboard_contracts", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
contracts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(contracts)

ALPHA = "/private/work/alpha"
BETA = "/private/work/beta"
BOTH = [ALPHA, BETA]
BACKUP_ROOT = "/private/backup"
EVIDENCE_DIR = "/private/migration"

T0 = "2026-09-18T01:00:00Z"
T1 = "2026-09-18T02:00:00Z"
T2 = "2026-09-18T02:05:00Z"
T3 = "2026-09-18T03:00:00Z"
T4 = "2026-09-18T03:05:00Z"
T5 = "2026-09-18T04:00:00Z"
T6 = "2026-09-18T04:05:00Z"
T7 = "2026-09-18T05:00:00Z"
T8 = "2026-09-18T05:05:00Z"
T9 = "2026-09-18T06:00:00Z"


def digest_number(number: int) -> str:
    return format(number, "064x")


def file_state(number: int) -> dict[str, Any]:
    return {"type": "file", "checksum": digest_number(number)}


def directory_state(number: int) -> dict[str, Any]:
    return {"type": "directory", "checksum": digest_number(number)}


ABSENT = {"type": "absent", "checksum": None}

# resource key -> (owner_kind, target, phases, dependent roots)
RESOURCES = {
    "r1": (
        "json",
        "/private/work/alpha/.codex/config.json",
        ("apply", "deploy", "cleanup"),
        [ALPHA],
    ),
    "r2": (
        "directory",
        "/private/work/alpha/.sbtd/skills/sbtd-task",
        ("apply", "cleanup"),
        [ALPHA],
    ),
    "r3": (
        "toml",
        "/private/work/beta/.codex/config.toml",
        ("apply", "deploy", "cleanup"),
        [BETA],
    ),
    "s1": (
        "toml",
        "/private/home/.codex/config.toml",
        ("apply", "deploy", "cleanup"),
        BOTH,
    ),
    "r4": (
        "markdown",
        "/private/work/alpha/docs/spec/notes.md",
        ("apply",),
        [ALPHA],
    ),
}

# state digest numbers per resource: orig / after-apply / after-deploy.
# "absent" marks a stage where the resource genuinely does not exist (r4 has no
# pre-apply original); None marks a phase the resource does not declare at all.
STATE_NUMBERS: dict[str, tuple[int | Literal["absent"], int, int | None]] = {
    "r1": (11, 12, 13),
    "r2": (21, 22, None),
    "r3": (31, 32, 33),
    "s1": (41, 42, 43),
    "r4": ("absent", 82, None),
}


def resource_state(key: str, stage: str) -> dict[str, Any]:
    """Return a state for an orig/apply/deploy stage recorded for this resource."""
    orig, after_apply, after_deploy = STATE_NUMBERS[key]
    number = {"orig": orig, "apply": after_apply, "deploy": after_deploy}[stage]
    if number is None:
        raise ValueError("fixture resource has no state for the requested stage")
    if number == "absent":
        return dict(ABSENT)
    if RESOURCES[key][0] == "directory":
        return directory_state(number)
    return file_state(number)


def resource_id_of(key: str) -> str:
    owner_kind, target, _, _ = RESOURCES[key]
    return contracts.resource_id(owner_kind, target)


def backup_ref_of(key: str, stage: str) -> dict[str, Any]:
    return {
        "path": f"{BACKUP_ROOT}/{key}-{stage}",
        "state": resource_state(key, stage),
    }


def _file_ref(path: str, number: int) -> dict[str, Any]:
    return {"path": path, "state": file_state(number)}


# Approved shared-notes publication candidate; also the exact r4 apply copy
# source and template-source ownership reference so both always correspond.
PUBLICATION_CANDIDATE = _file_ref("/private/candidates/notes.md", 82)

# Original shared-notes file later approved for publication; the same ref is
# listed in the alpha project's initial sources and in publication sources.
PUBLICATION_ORIGINAL = _file_ref("/private/work/alpha/docs/notes.md", 81)


def initial_source_ref(key: str) -> dict[str, Any]:
    """Plan-time snapshot of a resource's pre-apply original (project.sources)."""
    return {"path": RESOURCES[key][1], "state": resource_state(key, "orig")}


def build_operation(key: str, phase: str) -> dict[str, Any]:
    owner_kind, target, _, dependents = RESOURCES[key]
    rid = resource_id_of(key)
    if phase == "apply":
        # Copy sources are prepared whole candidates whose state is exactly the
        # recorded after-apply state, so a successful copy binds to the source.
        if owner_kind == "directory":
            change = {
                "kind": "copy-directory",
                "source_ref": {
                    "path": "/private/source/r2-apply-candidate",
                    "state": resource_state(key, "apply"),
                },
            }
            ownership = {
                "kind": "skill-identity",
                "reference": {
                    "path": "/private/source/sbtd-task",
                    "state": directory_state(71),
                },
                "name": "sbtd-task",
            }
            selector = "whole-resource"
        elif owner_kind == "markdown":
            change = {
                "kind": "copy-file",
                "source_ref": copy.deepcopy(PUBLICATION_CANDIDATE),
            }
            ownership = {
                "kind": "template-source",
                "reference": copy.deepcopy(PUBLICATION_CANDIDATE),
            }
            selector = "whole-resource"
        else:
            change = {
                "kind": "copy-file",
                "source_ref": {
                    "path": f"/private/source/{key}-apply-candidate",
                    "state": resource_state(key, "apply"),
                },
            }
            ownership = {
                "kind": "config-entry",
                "reference": _file_ref("/private/source/base-config", 72),
                "key_path": ["sbtd"],
            }
            selector = "sbtd.managed"
        before = {"kind": "state", "state": resource_state(key, "orig")}
    elif phase == "deploy":
        change = {
            "kind": "ensure-file-block",
            "source_ref": _file_ref("/private/source/managed-block", 73),
        }
        ownership = {
            "kind": "managed-marker",
            "reference": _file_ref("/private/source/managed-block", 73),
            "marker": "sbtd-managed",
        }
        before = {"kind": "phase-after", "phase": "apply", "resource_id": rid}
        selector = "sbtd.block"
    else:
        change = {"kind": "remove"}
        if owner_kind == "directory":
            ownership = {
                "kind": "skill-identity",
                "reference": {
                    "path": "/private/source/sbtd-task",
                    "state": directory_state(71),
                },
                "name": "sbtd-task",
            }
        else:
            ownership = {
                "kind": "config-entry",
                "reference": _file_ref("/private/source/base-config", 72),
                "key_path": ["sbtd"],
            }
        earlier = "deploy" if "deploy" in RESOURCES[key][2] else "apply"
        before = {"kind": "phase-after", "phase": earlier, "resource_id": rid}
        selector = "whole-resource" if owner_kind == "directory" else "sbtd.managed"
    return {
        "operation_id": contracts.operation_id(phase, rid, selector),
        "phase": phase,
        "resource_id": rid,
        "owner_kind": owner_kind,
        "target": target,
        "selector": selector,
        "change": change,
        "ownership": ownership,
        "before_requirement": before,
        "dependent_projects": sorted(dependents),
    }


def operations_of(key: str) -> dict[str, dict[str, Any]]:
    return {phase: build_operation(key, phase) for phase in RESOURCES[key][2]}


def build_publication_items() -> list[dict[str, Any]]:
    share_sources = [copy.deepcopy(PUBLICATION_ORIGINAL)]
    share_candidate = copy.deepcopy(PUBLICATION_CANDIDATE)
    local_sources = [_file_ref("/private/work/alpha/cache/local.bin", 83)]
    return [
        {
            "item_id": "shared-notes",
            "sources": share_sources,
            "target_path": f"{ALPHA}/docs/spec/notes.md",
            "required": True,
            "decision": "share",
            "candidate_ref": share_candidate,
            "approval": {
                "basis": "custodian reviewed the redacted candidate",
                "scope": {
                    "sources": copy.deepcopy(share_sources),
                    "target_path": f"{ALPHA}/docs/spec/notes.md",
                    "decision": "share",
                    "candidate_ref": copy.deepcopy(share_candidate),
                },
            },
        },
        {
            "item_id": "local-cache",
            "sources": local_sources,
            "target_path": None,
            "required": False,
            "decision": "private-only",
            "candidate_ref": None,
            "approval": {
                "basis": "optional local-only cache stays private",
                "scope": {
                    "sources": copy.deepcopy(local_sources),
                    "target_path": None,
                    "decision": "private-only",
                    "candidate_ref": None,
                },
            },
        },
    ]


def build_publication_decisions() -> dict[str, Any]:
    return {"schema_version": 1, "items": build_publication_items()}


def build_manifest_payload() -> dict[str, Any]:
    r1_ops = operations_of("r1")
    r2_ops = operations_of("r2")
    r3_ops = operations_of("r3")
    s1_ops = operations_of("s1")
    shared_ids = sorted(operation["operation_id"] for operation in s1_ops.values())
    r4_ops = operations_of("r4")
    return {
        "projects": [
            {
                "root": ALPHA,
                "source_ref": None,
                "head": None,
                "platforms": ["codex"],
                "sources": [
                    initial_source_ref("r1"),
                    initial_source_ref("r2"),
                    copy.deepcopy(PUBLICATION_ORIGINAL),
                ],
                "private_operations": [
                    r1_ops["apply"],
                    r1_ops["deploy"],
                    r1_ops["cleanup"],
                    r2_ops["apply"],
                    r2_ops["cleanup"],
                    r4_ops["apply"],
                ],
                "shared_operation_ids": list(shared_ids),
            },
            {
                "root": BETA,
                "source_ref": None,
                "head": None,
                "platforms": ["codex"],
                "sources": [initial_source_ref("r3")],
                "private_operations": [
                    r3_ops["apply"],
                    r3_ops["deploy"],
                    r3_ops["cleanup"],
                ],
                "shared_operation_ids": list(shared_ids),
            },
        ],
        "shared_roots": [
            {
                "kind": "codex-home",
                "path": "/private/home/.codex",
                "dependent_projects": list(BOTH),
            }
        ],
        "shared_operations": [s1_ops["apply"], s1_ops["deploy"], s1_ops["cleanup"]],
        "publication_decisions": build_publication_decisions(),
        "routing_approvals": None,
        "custodian": "release-custodian",
        "backup_root": BACKUP_ROOT,
        "created_at": T0,
        "retention": {
            "normal_observation_days": 14,
            "normal_disposal_gates": [
                "observation-complete",
                "final-acceptance",
                "stable-release",
                "recovery-window-closed",
            ],
            "termination_disposal_gates": [
                "explicit-termination",
                "recovery-or-no-recovery-confirmed",
                "custodian-review",
            ],
            "disposal_authorization": "separate-manual-confirmation",
        },
        "tool_versions": {"onboard": "2.0.0", "graft": "1.0.0"},
        "deployment": {"mode": "init", "platform": "codex", "inputs": []},
    }


def build_manifest() -> dict[str, Any]:
    return contracts.seal_document("manifest", build_manifest_payload())


def build_resource_result(
    key: str, phase: str, status: str = "succeeded", error: str | None = None
) -> dict[str, Any]:
    operation = operations_of(key)[phase]
    before_stage = {"apply": "orig", "deploy": "apply", "cleanup": "deploy"}[phase]
    if phase == "cleanup" and "deploy" not in RESOURCES[key][2]:
        before_stage = "apply"
    after_stage = {"apply": "apply", "deploy": "deploy", "cleanup": "cleanup"}[phase]
    before = resource_state(key, before_stage)
    after = ABSENT if after_stage == "cleanup" else resource_state(key, after_stage)
    if status == "succeeded":
        backup = (
            None if before["type"] == "absent" else backup_ref_of(key, before_stage)
        )
        error_text = None
    else:
        backup = None
        before = None
        after = None
        error_text = error or "recorded stage failure"
    return {
        "phase": phase,
        "resource_id": operation["resource_id"],
        "operation_ids": [operation["operation_id"]],
        "dependent_projects": sorted(RESOURCES[key][3]),
        "status": status,
        "backup_ref": backup,
        "before": before,
        "after": after,
        "error": error_text,
    }


def _stage_project(
    root: str,
    status: str,
    keys: list[str],
    phase: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    shared_op = operations_of("s1")[phase]
    project = {
        "root": root,
        "source_ref": None,
        "head": None,
        "status": status,
        "reason": "",
        "nextStep": "",
        "private_results": [build_resource_result(key, phase) for key in keys],
        "shared_operation_ids": [shared_op["operation_id"]],
    }
    if extra:
        project.update(extra)
    return project


def build_apply_receipt_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "manifest_id": manifest["manifest_id"],
        "previous_receipt_id": None,
        "status": "applied",
        "projects": [
            _stage_project(ALPHA, "applied", ["r1", "r2", "r4"], "apply"),
            _stage_project(BETA, "applied", ["r3"], "apply"),
        ],
        "shared_results": [build_resource_result("s1", "apply")],
        "started_at": T1,
        "finished_at": T2,
    }


def build_apply_receipt(manifest: dict[str, Any]) -> dict[str, Any]:
    return contracts.seal_document(
        "apply_receipt", build_apply_receipt_payload(manifest)
    )


def build_deployment_evidence_payload(
    manifest: dict[str, Any], apply_receipt: dict[str, Any]
) -> dict[str, Any]:
    return {
        "manifest_id": manifest["manifest_id"],
        "apply_id": apply_receipt["apply_id"],
        "previous_deployment_id": None,
        "status": "succeeded",
        "projects": [
            _stage_project(
                ALPHA,
                "succeeded",
                ["r1"],
                "deploy",
                {"report_refs": [_file_ref(f"{EVIDENCE_DIR}/alpha-smoke.json", 101)]},
            ),
            _stage_project(
                BETA,
                "succeeded",
                ["r3"],
                "deploy",
                {"report_refs": [_file_ref(f"{EVIDENCE_DIR}/beta-smoke.json", 102)]},
            ),
        ],
        "shared_results": [build_resource_result("s1", "deploy")],
        "started_at": T3,
        "finished_at": T4,
    }


def build_deployment_evidence(
    manifest: dict[str, Any], apply_receipt: dict[str, Any]
) -> dict[str, Any]:
    return contracts.seal_document(
        "deployment_evidence",
        build_deployment_evidence_payload(manifest, apply_receipt),
    )


def raw_bytes_of(document: dict[str, Any]) -> bytes:
    return contracts.canonical_json_bytes(document)


def raw_digest_of(document: dict[str, Any]) -> str:
    return hashlib.sha256(raw_bytes_of(document)).hexdigest()


def build_cleanup_candidate(key: str, observed_stage: str) -> dict[str, Any]:
    operation = operations_of(key)["cleanup"]
    return {
        "resource_id": operation["resource_id"],
        "operation_ids": [operation["operation_id"]],
        "target": operation["target"],
        "state": resource_state(key, observed_stage),
        "dependent_projects": sorted(RESOURCES[key][3]),
    }


def retained_asset_of(key: str) -> dict[str, Any]:
    """Object ref for a published asset retained through verification/cleanup."""
    return {"path": RESOURCES[key][1], "state": resource_state(key, "apply")}


def build_verification_payload(
    manifest: dict[str, Any],
    apply_receipt: dict[str, Any],
    deployment_evidence: dict[str, Any],
) -> dict[str, Any]:
    def verified_project(
        root: str, keys: list[str], stages: list[str], retained: list[str]
    ) -> dict[str, Any]:
        return {
            "root": root,
            "source_ref": None,
            "head": None,
            "status": "verified",
            "reason": "",
            "nextStep": "",
            "retained_assets": [retained_asset_of(key) for key in retained],
            "cleanup_candidates": [
                build_cleanup_candidate(key, stage) for key, stage in zip(keys, stages)
            ],
        }

    return {
        "manifest_id": manifest["manifest_id"],
        "apply_id": apply_receipt["apply_id"],
        "deployment_evidence_hash": raw_digest_of(deployment_evidence),
        "status": "verified",
        "projects": [
            verified_project(ALPHA, ["r1", "r2"], ["deploy", "apply"], ["r4"]),
            verified_project(BETA, ["r3"], ["deploy"], []),
        ],
        "shared_cleanup_candidates": [build_cleanup_candidate("s1", "deploy")],
        "verified_at": T5,
    }


def build_verification(
    manifest: dict[str, Any],
    apply_receipt: dict[str, Any],
    deployment_evidence: dict[str, Any],
) -> dict[str, Any]:
    return contracts.seal_document(
        "verification",
        build_verification_payload(manifest, apply_receipt, deployment_evidence),
    )


def build_cleanup_receipt_payload(
    manifest: dict[str, Any],
    apply_receipt: dict[str, Any],
    deployment_evidence: dict[str, Any],
    verification: dict[str, Any],
) -> dict[str, Any]:
    return {
        "manifest_id": manifest["manifest_id"],
        "verification_id": verification["verification_id"],
        "apply_id": apply_receipt["apply_id"],
        "deployment_evidence_hash": raw_digest_of(deployment_evidence),
        "previous_receipt_id": None,
        "status": "cleaned",
        "projects": [
            _stage_project(
                ALPHA,
                "cleaned",
                ["r1", "r2"],
                "cleanup",
                {"retained_assets": [retained_asset_of("r4")]},
            ),
            _stage_project(BETA, "cleaned", ["r3"], "cleanup", {"retained_assets": []}),
        ],
        "shared_results": [build_resource_result("s1", "cleanup")],
        "retained_assets": [retained_asset_of("r4")],
        "started_at": T6,
        "finished_at": T7,
    }


def build_cleanup_receipt(
    manifest: dict[str, Any],
    apply_receipt: dict[str, Any],
    deployment_evidence: dict[str, Any],
    verification: dict[str, Any],
) -> dict[str, Any]:
    return contracts.seal_document(
        "cleanup_receipt",
        build_cleanup_receipt_payload(
            manifest, apply_receipt, deployment_evidence, verification
        ),
    )


def build_input_evidence(
    manifest: dict[str, Any],
    apply_receipt: dict[str, Any],
    deployment_evidence: dict[str, Any],
    cleanup_receipt: dict[str, Any],
) -> dict[str, Any]:
    def ref(name: str, document: dict[str, Any]) -> dict[str, Any]:
        return {
            "path": f"{EVIDENCE_DIR}/{name}.json",
            "state": {"type": "file", "checksum": raw_digest_of(document)},
        }

    return {
        "manifest": ref("manifest", manifest),
        "apply_receipt": ref("apply_receipt", apply_receipt),
        "deployment_evidence": ref("deployment_evidence", deployment_evidence),
        "cleanup_receipt": ref("cleanup_receipt", cleanup_receipt),
    }


def build_recovery_step(
    key: str, phase: str, manifest_id: str, depends_on: list[str]
) -> dict[str, Any]:
    operation = operations_of(key)[phase]
    phases = RESOURCES[key][2]
    if phase == "cleanup":
        inverse_before = dict(ABSENT)
        restore_stage = "deploy" if "deploy" in phases else "apply"
    elif phase == "deploy":
        inverse_before = resource_state(key, "deploy")
        restore_stage = "apply"
    else:
        inverse_before = resource_state(key, "apply")
        restore_stage = "orig"
    inverse_after = resource_state(key, restore_stage)
    if inverse_after["type"] == "absent":
        backup = None
    else:
        backup = backup_ref_of(key, restore_stage)
    return {
        "step_id": contracts.recovery_step_id(
            manifest_id, phase, operation["resource_id"]
        ),
        "phase": phase,
        "resource_id": operation["resource_id"],
        "operation_ids": [operation["operation_id"]],
        "dependent_projects": sorted(RESOURCES[key][3]),
        "depends_on": depends_on,
        "backup_ref": backup,
        "expected_current": inverse_before,
        "restore_to": inverse_after,
    }


def build_recovery_steps(manifest_id: str) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    previous_inverse: dict[str, str] = {}
    for phase in ("cleanup", "deploy", "apply"):
        for key in RESOURCES:
            if phase not in RESOURCES[key][2]:
                continue
            depends = [previous_inverse[key]] if key in previous_inverse else []
            step = build_recovery_step(key, phase, manifest_id, depends)
            previous_inverse[key] = step["step_id"]
            steps.append(step)
    return steps


def _plan_snapshot_state(key: str) -> dict[str, Any]:
    """Observed resource state when recovery is planned, after its last phase."""
    phases = RESOURCES[key][2]
    if "cleanup" in phases:
        return dict(ABSENT)
    return resource_state(key, "deploy" if "deploy" in phases else "apply")


def build_recovery_plan_payload(
    manifest: dict[str, Any],
    apply_receipt: dict[str, Any],
    deployment_evidence: dict[str, Any],
    cleanup_receipt: dict[str, Any],
) -> dict[str, Any]:
    manifest_id = manifest["manifest_id"]
    shared_ids = sorted(
        operation["operation_id"] for operation in operations_of("s1").values()
    )
    return {
        "manifest_id": manifest_id,
        "status": "planned",
        "projects": [
            {"root": ALPHA, "source_ref": None, "head": None},
            {"root": BETA, "source_ref": None, "head": None},
        ],
        "shared_operation_ids": shared_ids,
        "input_evidence": build_input_evidence(
            manifest, apply_receipt, deployment_evidence, cleanup_receipt
        ),
        "resources": [
            {
                "resource_id": resource_id_of(key),
                "owner_kind": RESOURCES[key][0],
                "target": RESOURCES[key][1],
                "operation_ids": sorted(
                    operation["operation_id"]
                    for operation in operations_of(key).values()
                ),
                "dependent_projects": sorted(RESOURCES[key][3]),
                "state": _plan_snapshot_state(key),
            }
            for key in RESOURCES
        ],
        "steps": build_recovery_steps(manifest_id),
        "conflicts": [],
        "risks": [],
        "target": "pre-apply",
        "created_at": T8,
    }


def build_recovery_plan(
    manifest: dict[str, Any],
    apply_receipt: dict[str, Any],
    deployment_evidence: dict[str, Any],
    cleanup_receipt: dict[str, Any],
) -> dict[str, Any]:
    return contracts.seal_document(
        "recovery_plan",
        build_recovery_plan_payload(
            manifest, apply_receipt, deployment_evidence, cleanup_receipt
        ),
    )


def build_recovery_step_result(step: dict[str, Any], key: str) -> dict[str, Any]:
    before = step["expected_current"]
    after = step["restore_to"]
    if before["type"] == "absent":
        protection = None
    else:
        protection = {
            "path": f"{EVIDENCE_DIR}/protection/{key}-{step['phase']}",
            "state": copy.deepcopy(before),
        }
    return {
        "step_id": step["step_id"],
        "resource_id": step["resource_id"],
        "phase": step["phase"],
        "operation_ids": list(step["operation_ids"]),
        "dependent_projects": list(step["dependent_projects"]),
        "status": "succeeded",
        "protection_ref": protection,
        "before": copy.deepcopy(before),
        "after": copy.deepcopy(after),
        "error": None,
    }


def build_recovery_receipt_payload(
    manifest: dict[str, Any],
    apply_receipt: dict[str, Any],
    deployment_evidence: dict[str, Any],
    cleanup_receipt: dict[str, Any],
    recovery_plan: dict[str, Any],
) -> dict[str, Any]:
    steps = recovery_plan["payload"]["steps"]
    key_by_resource = {resource_id_of(key): key for key in RESOURCES}
    results = [
        build_recovery_step_result(step, key_by_resource[step["resource_id"]])
        for step in steps
    ]
    shared_steps = sorted(
        step["step_id"] for step in steps if step["resource_id"] == resource_id_of("s1")
    )
    return {
        "plan_id": recovery_plan["plan_id"],
        "manifest_id": manifest["manifest_id"],
        "previous_receipt_id": None,
        "input_evidence": build_input_evidence(
            manifest, apply_receipt, deployment_evidence, cleanup_receipt
        ),
        "status": "restored",
        "projects": [
            {
                "root": ALPHA,
                "source_ref": None,
                "head": None,
                "status": "restored",
                "reason": "",
                "nextStep": "",
            },
            {
                "root": BETA,
                "source_ref": None,
                "head": None,
                "status": "restored",
                "reason": "",
                "nextStep": "",
            },
        ],
        "results": results,
        "shared_results": [
            {
                "resource_id": resource_id_of("s1"),
                "dependent_projects": list(BOTH),
                "step_ids": shared_steps,
            }
        ],
        "completed_step_ids": sorted(step["step_id"] for step in steps),
        "pending_step_ids": [],
        "reason": "",
        "started_at": T8,
        "finished_at": T9,
        "runtime_readiness": "not-verified",
        "report_refs": [],
    }


def build_recovery_receipt(
    manifest: dict[str, Any],
    apply_receipt: dict[str, Any],
    deployment_evidence: dict[str, Any],
    cleanup_receipt: dict[str, Any],
    recovery_plan: dict[str, Any],
) -> dict[str, Any]:
    return contracts.seal_document(
        "recovery_receipt",
        build_recovery_receipt_payload(
            manifest, apply_receipt, deployment_evidence, cleanup_receipt, recovery_plan
        ),
    )


def envelope_projects(status: str) -> list[dict[str, Any]]:
    return [
        {"root": ALPHA, "status": status, "reason": "", "nextStep": ""},
        {"root": BETA, "status": status, "reason": "", "nextStep": ""},
    ]


def build_fixture_family() -> dict[str, Any]:
    """One coherent family: every document sealed and cross-bound by construction."""
    manifest = build_manifest()
    apply_receipt = build_apply_receipt(manifest)
    deployment = build_deployment_evidence(manifest, apply_receipt)
    verification = build_verification(manifest, apply_receipt, deployment)
    cleanup = build_cleanup_receipt(manifest, apply_receipt, deployment, verification)
    plan = build_recovery_plan(manifest, apply_receipt, deployment, cleanup)
    receipt = build_recovery_receipt(manifest, apply_receipt, deployment, cleanup, plan)
    manifest_id = manifest["manifest_id"]
    return {
        "publication_decisions": build_publication_decisions(),
        "manifest": manifest,
        "apply_receipt": apply_receipt,
        "deployment_evidence": deployment,
        "verification": verification,
        "cleanup_receipt": cleanup,
        "recovery_plan": plan,
        "recovery_receipt": receipt,
        "migration_envelope_plan": contracts.make_envelope(
            "migration",
            "plan",
            "planned",
            envelope_projects("planned"),
            "",
            "",
            artifact=manifest,
            identifiers={"manifest_id": manifest_id},
        ),
        "migration_envelope_apply": contracts.make_envelope(
            "migration",
            "apply",
            "applied",
            envelope_projects("applied"),
            "",
            "",
            artifact=apply_receipt,
            identifiers={"manifest_id": manifest_id},
        ),
        "migration_envelope_verify": contracts.make_envelope(
            "migration",
            "verify",
            "verified",
            envelope_projects("verified"),
            "",
            "",
            artifact=verification,
            identifiers={
                "manifest_id": manifest_id,
                "verification_id": verification["verification_id"],
            },
        ),
        "migration_envelope_cleanup": contracts.make_envelope(
            "migration",
            "cleanup",
            "cleaned",
            envelope_projects("cleaned"),
            "",
            "",
            artifact=cleanup,
            identifiers={
                "manifest_id": manifest_id,
                "verification_id": verification["verification_id"],
            },
        ),
        "recovery_envelope_plan": contracts.make_envelope(
            "recovery",
            "plan",
            "planned",
            envelope_projects("planned"),
            "",
            "",
            artifact=plan,
            identifiers={"manifest_id": manifest_id, "plan_id": plan["plan_id"]},
        ),
        "recovery_envelope_apply": contracts.make_envelope(
            "recovery",
            "apply",
            "restored",
            envelope_projects("restored"),
            "",
            "",
            artifact=receipt,
            identifiers={
                "manifest_id": manifest_id,
                "plan_id": plan["plan_id"],
                "receipt_id": receipt["receipt_id"],
            },
        ),
    }


def fixture_raw_documents(family: dict[str, Any]) -> dict[str, bytes]:
    """Raw file bytes for the evidence slots validate_declared_bindings checks."""
    return {
        kind: raw_bytes_of(family[kind])
        for kind in (
            "manifest",
            "apply_receipt",
            "deployment_evidence",
            "cleanup_receipt",
        )
    }


def write_fixture_family(directory: Path) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for name, document in build_fixture_family().items():
        path = directory / f"{name}.json"
        path.write_bytes(raw_bytes_of(document))
        written[name] = path
    return written


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: onboard_contract_fixtures.py <output-dir>", file=sys.stderr)
        return 2
    written = write_fixture_family(Path(argv[1]))
    for name, path in sorted(written.items()):
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
