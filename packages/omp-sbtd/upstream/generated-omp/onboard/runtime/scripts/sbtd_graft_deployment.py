"""Shared host deployment resources and fixed-policy native graph generation.

The public installer owns confirmation and dispatch. This module owns only the
selected Codex or OMP deployment resources; migration data/apply/cleanup are
separate stages.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

import onboard_contracts as contracts
from graft_runtime import GRAFT_PINNED_VERSION, _locate_package, check_graft
from sbtd_migration import _LEGACY_TREE, _prepare_target_parents, _project_revision
from sbtd_migration_files import (
    _canonical,
    _lstat,
    backup_reference,
    install_reference,
    read_file,
    require_private_directory,
    save_document,
    snapshot,
    write_file,
)

_PACKAGE = Path(__file__).resolve().parents[1]
_ABSENT = {"type": "absent", "checksum": None}
_SAFE_OPTS = {"global": False, "mcp": False, "hooks": False, "statusline": False}


def _fail(code: str, message: str, exit_code: int = 2) -> NoReturn:
    raise contracts.ContractError(code, message, exit_code=exit_code)


def policy_reference() -> dict[str, Any]:
    reference = {
        "path": str(contracts.GRAFT_BUILD_POLICY_PATH),
        "state": {"type": "file", "checksum": contracts.GRAFT_BUILD_POLICY_SHA256},
    }
    read_file(Path(reference["path"]), reference["state"])
    return reference


def _operation(
    target: Path,
    owner_kind: str,
    selector: str,
    kind: str,
    dependents: Sequence[str],
    earlier: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    resource = contracts.resource_id(owner_kind, str(target))
    prior = [operation for operation in earlier if operation["target"] == str(target)]
    if prior and any(operation["owner_kind"] != owner_kind for operation in prior):
        _fail(
            "ownership-conflict", "deployment cannot change a physical resource owner"
        )
    requirement = (
        {"kind": "phase-after", "phase": "apply", "resource_id": resource}
        if prior
        else {"kind": "state", "state": snapshot(target)}
    )
    policy = policy_reference()
    return {
        "phase": "deploy",
        "resource_id": resource,
        "operation_id": contracts.operation_id("deploy", resource, selector),
        "owner_kind": owner_kind,
        "target": str(target),
        "selector": selector,
        "change": {"kind": kind, "source_ref": policy},
        "ownership": {"kind": "template-source", "reference": policy},
        "before_requirement": requirement,
        "dependent_projects": sorted(dependents),
    }


def deployment_operations(
    projects: Sequence[Mapping[str, Any]],
    *,
    codex_home: Path | None = None,
    omp_home: Path | None = None,
    platform: str = "codex",
    hooks_authorized: bool = False,
    shared_operations: Sequence[Mapping[str, Any]] = (),
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Read-only declarations; no package execution or authorization inference."""
    if platform not in {"codex", "omp"}:
        _fail(
            "invalid-argument", "the deployment platform must be explicitly supported"
        )
    private: dict[str, list[dict[str, Any]]] = {}
    roots = sorted(project["root"] for project in projects)
    for project in projects:
        root = Path(project["root"])
        prior = project["private_operations"]
        operations: list[dict[str, Any]] = []
        if project.get("agents_no_touch") is None:
            operations.append(
                _operation(
                    root / "AGENTS.md",
                    "markdown",
                    "graft-agents",
                    "configure-graft",
                    [str(root)],
                    prior,
                )
            )
        # A sealed no-touch proof preserves the exact aligned AGENTS.md, so
        # no fence is appended; the graph build is independent capability
        # and stays declared either way.
        operations.append(
            _operation(
                root / "graft",
                "directory",
                "whole-resource",
                "build-graft",
                [str(root)],
                prior,
            )
        )
        private[str(root)] = operations
    shared = []
    if platform == "codex" and codex_home is not None:
        shared.append(
            _operation(
                codex_home / "config.toml",
                "toml",
                "graft-mcp",
                "configure-graft",
                roots,
                shared_operations,
            )
        )
        if hooks_authorized:
            shared.append(
                _operation(
                    codex_home / "hooks.json",
                    "json",
                    "graft-hooks",
                    "configure-graft",
                    roots,
                    shared_operations,
                )
            )
    elif platform == "omp":
        if hooks_authorized:
            _fail("scope-conflict", "OMP deployment does not include Codex hooks")
        if omp_home is not None:
            shared.append(
                _operation(
                    omp_home / "mcp.json",
                    "json",
                    "graft-omp-mcp",
                    "configure-graft",
                    roots,
                    shared_operations,
                )
            )
    elif hooks_authorized:
        _fail("scope-conflict", "project-only deployment cannot authorize global hooks")
    return private, shared


def _validate_selected_root_batch(roots: Sequence[Path]) -> None:
    """Reject nested selected roots before any runtime probe or deployment write."""
    ordered = sorted(roots)
    for index, root in enumerate(ordered):
        for other in ordered[index + 1 :]:
            if root.samefile(other):
                _fail(
                    "scope-conflict",
                    "selected Graft roots must not identify the same physical repository",
                )
            if root.is_relative_to(other) or other.is_relative_to(root):
                _fail(
                    "scope-conflict",
                    "selected Graft roots must not overlap or contain another selected root",
                )


def verified_runtime() -> dict[str, str]:
    """Resolve the existing verified installation; never install or upgrade."""
    from sbtd_graft_entry import validate_runtime

    found = check_graft()
    node = found.get("node")
    if (
        found.get("status") != "available"
        or not isinstance(node, dict)
        or not node.get("compatible")
    ):
        _fail(
            "runtime-unavailable",
            "the pinned native Graft installation must be available before deployment",
        )
    executable = found.get("path")
    located = _locate_package(str(executable)) if executable else None
    if located is None or located[1] != GRAFT_PINNED_VERSION:
        _fail(
            "runtime-unavailable", "the selected Graft executable identity is unproven"
        )
    node_path = Path(str(node["path"])).resolve(strict=True)
    cli = located[0] / "dist/cli.js"
    validate_runtime(node_path, cli)
    return {
        "node": str(node_path),
        "cli": str(cli),
        "python": str(Path(sys.executable).absolute()),
    }


def launch_bindings(
    roots: Sequence[Path], runtime: Mapping[str, str], *, package_root: Path
) -> list[dict[str, str]]:
    binding = {
        "node": runtime["node"],
        "cli": runtime["cli"],
        "python": runtime["python"],
        "launcher": str(package_root / "scripts/sbtd_graft_entry.py"),
    }
    return [{**binding, "root": str(root)} for root in roots] or [binding]


def _run_native(
    root: Path, runtime: Mapping[str, str], arguments: Sequence[str]
) -> subprocess.CompletedProcess[str]:
    from sbtd_graft_entry import (
        _seed_update_cache,
        managed_environment,
        validate_build_scope,
    )

    validate_build_scope(root)
    with tempfile.TemporaryDirectory(prefix="sbtd-graft-native-") as directory:
        home = Path(directory).resolve()
        environment = managed_environment(root, home)
        _seed_update_cache(home)
        try:
            return subprocess.run(
                [runtime["node"], runtime["cli"], *arguments],
                cwd=root,
                env=environment,
                text=True,
                capture_output=True,
                timeout=900,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            _fail(
                "native-operation-failed",
                "the fixed Graft operation did not complete",
                5,
            )


def build_project_graph(root: Path, runtime: Mapping[str, str]) -> dict[str, Any]:
    """Explicit generation only; no live native init or auto-reconciliation."""
    from sbtd_graft_entry import (
        validate_build_scope,
        validate_project,
        validate_runtime,
    )

    policy_reference()
    validate_runtime(Path(runtime["node"]), Path(runtime["cli"]))
    _project_revision(root)
    validate_build_scope(root)
    graph = root / "graft"
    if snapshot(graph)["type"] not in {"absent", "directory"}:
        _fail("ownership-conflict", "the graph target is not an ordinary directory")
    stamp_path = graph / ".cache/wiring-stamp.json"
    _prepare_target_parents(stamp_path, root)
    before = snapshot(stamp_path)
    stamp = {
        "version": GRAFT_PINNED_VERSION,
        "hosts": ["agents"],
        "opts": dict(_SAFE_OPTS),
        "at": datetime.now(timezone.utc).isoformat(),
    }
    write_file(stamp_path, contracts.canonical_json_bytes(stamp), before, scope=root)
    completed = _run_native(
        root, runtime, ["build", ".", "--no-gitignore", "--no-ignore"]
    )
    if completed.returncode != 0:
        _fail("native-operation-failed", "the fixed Graft graph build failed", 5)
    validate_project(root)
    return {
        "state": snapshot(graph),
        "command": [
            runtime["node"],
            runtime["cli"],
            "build",
            ".",
            "--no-gitignore",
            "--no-ignore",
        ],
        "exitCode": completed.returncode,
    }


def render_configuration(
    operation: Mapping[str, Any],
    before: bytes,
    bindings: Sequence[Mapping[str, Any]],
    *,
    install_template: bool = False,
    retire_legacy: bool = False,
    approved_body: bytes | None = None,
) -> bytes:
    from sbtd_codex_wiring import (
        codex_hooks_candidate,
        codex_mcp_candidate,
        project_agents_candidate,
    )

    selector = operation["selector"]
    if selector == "graft-agents":
        if approved_body is not None:
            # The migration manifest chain proves this exact approved body;
            # deployment adds or refreshes only the managed fence around it.
            return project_agents_candidate(approved_body)
        if install_template:
            from onboard import PROJECT_AGENTS_TEMPLATE

            # This operation carries explicit replacement authorization, so
            # obsolete malformed bytes must not block adding the managed fence.
            before = read_file(PROJECT_AGENTS_TEMPLATE)
        return project_agents_candidate(before)
    if selector == "graft-mcp":
        return codex_mcp_candidate(before, bindings, retire_legacy=retire_legacy)
    if selector == "graft-omp-mcp":
        from onboard import user_home
        from sbtd_omp_sources import discover_omp_sources
        from sbtd_omp_wiring import analyze_omp_configuration, omp_mcp_candidate

        target = Path(operation["target"])
        roots = [Path(binding["root"]) for binding in bindings if "root" in binding]
        discovered = discover_omp_sources(roots, home=user_home(), environ=os.environ)
        if discovered["target"] != str(target):
            _fail("scope-conflict", "the OMP resource leaves the active profile")
        if (
            not before
            and target.exists()
            and target.stat().st_size == 0
        ):
            # A present but empty active document is invalid JSON, exactly as
            # the live analysis has always enforced; only genuine absence
            # renders from an empty document.
            _fail("invalid-json", "the active OMP MCP configuration is not strict JSON")
        analysis = analyze_omp_configuration(
            target,
            bindings,
            discovered["sources"],
            disabled_extensions=discovered["disabled_extensions"],
            retire_legacy=retire_legacy,
            active_bytes=before,
        )
        return omp_mcp_candidate(before, analysis)
    if selector == "graft-hooks":
        return codex_hooks_candidate(before, bindings, authorized=True)
    _fail("unsupported-operation", "the deployment selector is not supported")


def execute_resource(
    operation: Mapping[str, Any],
    *,
    expected: Mapping[str, Any],
    root: Path,
    private_root: Path,
    backup_path: Path,
    bindings: Sequence[Mapping[str, Any]],
    runtime: Mapping[str, str],
    launcher_state: Mapping[str, Any],
    install_template: bool = False,
    retire_legacy: bool = False,
    approved_body: bytes | None = None,
) -> dict[str, Any]:
    """One observed resource result; caller persists cumulative stage evidence."""
    result: dict[str, Any] = {
        "phase": "deploy",
        "resource_id": operation["resource_id"],
        "operation_ids": [operation["operation_id"]],
        "dependent_projects": list(operation["dependent_projects"]),
        "status": "blocked",
        "backup_ref": None,
        "before": None,
        "after": None,
        "error": "resource execution has not begun",
    }
    target = Path(operation["target"])
    started = False
    try:
        before = snapshot(target)
        result.update(before=before, after=before)
        if before != expected:
            _fail("state-conflict", "the deployment resource changed before execution")
        kind = operation["change"]["kind"]
        if (
            kind in {"build-graft", "configure-graft"}
            and operation["change"]["source_ref"] != policy_reference()
        ):
            _fail(
                "ownership-conflict",
                "the deployment policy does not match this runtime",
            )
        candidate = None
        before_bytes = b""
        if operation["change"]["kind"] == "configure-graft":
            before_bytes = (
                b"" if before["type"] == "absent" else read_file(target, before)
            )
            candidate = render_configuration(
                operation,
                before_bytes,
                bindings,
                install_template=install_template,
                retire_legacy=retire_legacy,
                approved_body=approved_body,
            )
        if operation["selector"] in {"graft-mcp", "graft-hooks", "graft-omp-mcp"}:
            installed_package = Path(bindings[0]["launcher"]).parents[1]
            if snapshot(installed_package) != launcher_state:
                _fail(
                    "runtime-unavailable",
                    "the canonical installed launcher is missing or has drifted",
                )
        root_info = _lstat(_canonical(root))
        if root_info is None:
            root.mkdir(parents=True, mode=0o700)
        elif not stat.S_ISDIR(root_info.st_mode):
            _fail("unsafe-path", "the deployment write scope is not a real directory")
        if private_root.is_relative_to(root):
            _prepare_target_parents(private_root, root)
            require_private_directory(private_root, create=True)
        if before["type"] != "absent":
            require_private_directory(private_root)
            _prepare_target_parents(backup_path, private_root)
            result["backup_ref"] = backup_reference(
                {"path": str(target), "state": before},
                backup_path,
                private_root=private_root,
            )
        if snapshot(target) != before:
            _fail(
                "state-conflict",
                "the deployment resource changed while retaining its original",
            )
        started = True
        if candidate is not None:
            if candidate != before_bytes:
                _prepare_target_parents(target, root)
                write_file(target, candidate, before, scope=root)
        elif operation["change"]["kind"] == "build-graft":
            build_project_graph(root, runtime)
        elif kind in {"copy-file", "copy-directory"}:
            _prepare_target_parents(target, root)
            install_reference(
                operation["change"]["source_ref"],
                target,
                before,
                scope=root,
                backup_ref=result.get("backup_ref"),
            )
        else:
            _fail("unsupported-operation", "the deployment operation is not supported")
        result.update(status="succeeded", after=snapshot(target), error=None)
    except (contracts.ContractError, OSError, RuntimeError):
        result["status"] = "failed" if started else "blocked"
        result["error"] = (
            "deployment resource execution failed"
            if started
            else "deployment resource precondition failed"
        )
        try:
            result["after"] = snapshot(target)
        except (contracts.ContractError, OSError, RuntimeError):
            result["after"] = None
    return result


def _omp_agents_template_target(
    platform: str, omp_home: Path | None
) -> Path | None:
    """The OMP global rules target an OMP init deployment implicitly creates.

    The installer catalog includes the OMP global AGENTS.md only when the OMP
    root already exists; an OMP deployment itself creates that root with its
    MCP write. Naming the target explicitly keeps the canonical set identical
    at plan time and at every later re-derivation.
    """
    if platform != "omp" or omp_home is None:
        return None
    from onboard import detect_omp_root, omp_global_agents_path, user_home

    if detect_omp_root() is not None:
        return None
    root = (user_home() / ".omp").resolve()
    try:
        omp_home.resolve().relative_to(root)
    except (OSError, ValueError, RuntimeError):
        return None
    return omp_global_agents_path(root)


def _installation_templates(
    roots: Sequence[str], *, omp_agents_target: Path | None = None
) -> list[Any]:
    """Reuse the installer's canonical source/target selection, not a second catalog."""
    from argparse import Namespace

    from onboard import build_operations

    arguments = Namespace(
        projects_root=",".join(roots),
        skip_project_agents=False,
        global_agents_path=None,
        global_skills_dir=None,
    )
    project_targets = {
        str(Path(root) / name) for root in roots for name in ("AGENTS.md", ".gitignore")
    }
    selected = [
        operation
        for operation in build_operations("init", arguments)
        if str(operation.target) not in project_targets and not operation.same_location
    ]
    if omp_agents_target is not None and all(
        operation.target != omp_agents_target for operation in selected
    ):
        from onboard import GLOBAL_AGENTS_TEMPLATE, Operation

        selected.append(
            Operation(
                "omp global AGENTS.md", GLOBAL_AGENTS_TEMPLATE, omp_agents_target, "file"
            )
        )
    return selected


def attach_deployment(
    payload: dict[str, Any],
    *,
    project_only: bool,
    hooks_authorized: bool,
    platform: str = "codex",
    successor_pauses: Mapping[str, str] | None = None,
    followup_deployed: Mapping[str, Any] | None = None,
) -> None:
    """Declare every write before the migration manifest is sealed."""
    from onboard import (
        default_codex_home,
        detect_omp_root,
        resolve_global_skills_dir,
        user_home,
    )
    from sbtd_migration_plan import _ignore_operation

    if platform not in {"codex", "omp"}:
        _fail(
            "invalid-argument", "the deployment platform must be explicitly supported"
        )
    if platform != "codex" and hooks_authorized:
        _fail("scope-conflict", "OMP deployment does not include Codex hooks")
    roots = sorted(project["root"] for project in payload["projects"])
    if project_only and payload["shared_operations"]:
        _fail(
            "scope-conflict",
            "project-only deployment cannot consume a shared-HOME batch",
        )
    codex_home = None if project_only else default_codex_home()
    discovery = None
    omp_home = None
    if platform == "omp" and not project_only:
        from sbtd_omp_sources import discover_omp_sources

        discovery = discover_omp_sources(
            [Path(root) for root in roots], home=user_home(), environ=os.environ
        )
        omp_home = Path(discovery["agent_dir"])
    omp_agents_target = _omp_agents_template_target(platform, omp_home)
    private, shared = deployment_operations(
        payload["projects"],
        codex_home=codex_home if platform == "codex" else None,
        omp_home=omp_home,
        platform=platform,
        hooks_authorized=hooks_authorized,
        shared_operations=payload["shared_operations"],
    )
    payload["deployment"] = {
        "mode": "init-projects" if project_only else "init",
        "platform": platform,
        "inputs": list(discovery["inputs"]) if discovery is not None else [],
    }
    for project in payload["projects"]:
        if not any(
            operation["owner_kind"] == "gitignore"
            for operation in project["private_operations"]
        ):
            protection = _ignore_operation(Path(project["root"]))
            if protection is not None:
                project["private_operations"].insert(0, protection)
        project["private_operations"].extend(private[project["root"]])
    if codex_home is not None:
        if not any(
            record["path"] == str(codex_home) for record in payload["shared_roots"]
        ):
            payload["shared_roots"].append(
                {
                    "kind": "codex-home",
                    "path": str(codex_home),
                    "dependent_projects": roots,
                }
            )
        omp_root = detect_omp_root()
        if platform == "codex":
            if omp_root is not None and not any(
                record["path"] == str(omp_root) for record in payload["shared_roots"]
            ):
                payload["shared_roots"].append(
                    {
                        "kind": "omp-home",
                        "path": str(omp_root),
                        "dependent_projects": roots,
                    }
                )
        elif omp_home is not None:
            effective_omp_root = (
                omp_root
                if omp_root is not None
                else (
                    omp_agents_target.parent.parent
                    if omp_agents_target is not None
                    else None
                )
            )
            if effective_omp_root is not None and not any(
                record["path"] == str(effective_omp_root)
                for record in payload["shared_roots"]
            ):
                payload["shared_roots"].append(
                    {
                        "kind": "omp-home",
                        "path": str(effective_omp_root),
                        "dependent_projects": roots,
                    }
                )
            if not any(
                omp_home.is_relative_to(Path(record["path"]))
                for record in payload["shared_roots"]
            ):
                payload["shared_roots"].append(
                    {
                        "kind": "omp-home",
                        "path": str(omp_home),
                        "dependent_projects": roots,
                    }
                )
        obsolete_skills_roots = [
            record
            for record in payload["shared_roots"]
            if record["kind"] == "skills"
            and any(
                Path(record["path"]).is_relative_to(Path(scope["path"]))
                and scope["dependent_projects"] == record["dependent_projects"]
                for scope in payload["shared_roots"]
                if scope["kind"] in {"codex-home", "omp-home"}
            )
        ]
        if any(
            record["dependent_projects"] != roots for record in obsolete_skills_roots
        ):
            _fail(
                "scope-conflict",
                "an existing skills root has different project dependencies",
            )
        if obsolete_skills_roots:
            for record in obsolete_skills_roots:
                strict_covering = [
                    scope
                    for scope in payload["shared_roots"]
                    if scope["kind"] in {"codex-home", "omp-home"}
                    and scope["dependent_projects"] == record["dependent_projects"]
                    and scope["path"] != record["path"]
                    and Path(record["path"]).is_relative_to(Path(scope["path"]))
                ]
                if len(strict_covering) == 1:
                    # The absorbed Skills root survives as sealed logical
                    # metadata on its covering home root; an already-sealed
                    # location keeps authority over a re-resolution.
                    strict_covering[0].setdefault("skills_root", record["path"])
            payload["shared_roots"] = [
                record
                for record in payload["shared_roots"]
                if record not in obsolete_skills_roots
            ]
        skills_root, _source = resolve_global_skills_dir()
        covering_skills = [
            record
            for record in payload["shared_roots"]
            if Path(skills_root).is_relative_to(Path(record["path"]))
            and record["dependent_projects"] == roots
        ]
        if not covering_skills:
            payload["shared_roots"].append(
                {
                    "kind": "skills",
                    "path": str(skills_root),
                    "dependent_projects": roots,
                }
            )
        earlier_by_target = {
            operation["target"]: operation
            for operation in payload["shared_operations"]
            if operation["phase"] == "apply"
            and operation["selector"] == "pause-legacy-routing"
        }
        for selected in _installation_templates(
            roots, omp_agents_target=omp_agents_target
        ):
            target = selected.target
            source = {"path": str(selected.source), "state": snapshot(selected.source)}
            before = snapshot(target)
            earlier = earlier_by_target.get(str(target))
            paused_predecessor = (
                None if successor_pauses is None else successor_pauses.get(str(target))
            )
            directory = selected.kind == "dir"
            owner_kind = "directory" if directory else "markdown"
            selector = "whole-resource" if directory else "global-rules"
            resource = contracts.resource_id(owner_kind, str(target))
            followup_after = (
                None if followup_deployed is None else followup_deployed.get(resource)
            )
            if earlier is None and paused_predecessor is None:
                if followup_after is not None:
                    # A followup batch replaces only what its proven
                    # predecessor deployment owns, from that exact outcome.
                    if before != followup_after:
                        _fail(
                            "state-conflict",
                            "a completed batch outcome no longer matches the "
                            "current state",
                        )
                elif before not in (_ABSENT, source["state"]):
                    _fail(
                        "ownership-conflict",
                        "an installation target has unrecognized customized content",
                    )
            if earlier is not None:
                requirement = {
                    "kind": "phase-after",
                    "phase": "apply",
                    "resource_id": resource,
                }
            elif paused_predecessor is not None:
                if paused_predecessor != resource:
                    _fail(
                        "ownership-conflict",
                        "a paused predecessor does not own the installation target",
                    )
                requirement = {
                    "kind": "phase-after",
                    "phase": "apply",
                    "resource_id": resource,
                }
            else:
                requirement = {"kind": "state", "state": before}
            shared.append(
                {
                    "phase": "deploy",
                    "resource_id": resource,
                    "operation_id": contracts.operation_id(
                        "deploy", resource, selector
                    ),
                    "owner_kind": owner_kind,
                    "target": str(target),
                    "selector": selector,
                    "change": {
                        "kind": "copy-directory" if directory else "copy-file",
                        "source_ref": source,
                    },
                    "ownership": {"kind": "template-source", "reference": source},
                    "before_requirement": requirement,
                    "dependent_projects": roots,
                }
            )
    payload["shared_operations"].extend(shared)
    payload["shared_roots"].sort(key=lambda record: record["path"])
    for project in payload["projects"]:
        project["shared_operation_ids"] = sorted(
            operation["operation_id"]
            for operation in payload["shared_operations"]
            if project["root"] in operation["dependent_projects"]
        )


def _declared_operations(
    payload: Mapping[str, Any],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {
        (operation["phase"], operation["resource_id"]): operation
        for operation in (
            *(
                operation
                for project in payload["projects"]
                for operation in project["private_operations"]
            ),
            *payload["shared_operations"],
        )
    }


def _proven_input_outcome(
    operations: Mapping[tuple[str, str], Mapping[str, Any]],
    stage_results: Mapping[str, Mapping[str, Any]] | None,
    path: str,
    sealed_state: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    """Chain one sealed input through its bound successful stage outcomes.

    Returns the receipt-proven outcome once at least one bound stage result
    claims the input path, or None when no bound stage touches it. A claimed
    input with a broken chain (duplicate, failed, partial or untracked
    outcome, mutated retained original) keeps the exact drift rejection.
    """
    proven = sealed_state
    bound = False
    for phase in ("apply", "deploy", "cleanup"):
        matched = []
        for resource_id, result in ((stage_results or {}).get(phase) or {}).items():
            operation = operations.get((phase, resource_id))
            if operation is not None and operation["target"] == path:
                matched.append(result)
        if not matched:
            continue
        bound = True
        result = matched[0]
        backup = result["backup_ref"]
        if (
            len(matched) != 1
            or result["status"] != "succeeded"
            or result["before"] != proven
            or result["after"] is None
            or (
                proven["type"] != "absent"
                and (
                    backup is None
                    or snapshot(Path(backup["path"])) != backup["state"]
                )
            )
        ):
            _fail(
                "state-conflict",
                "the sealed OMP configuration sources have drifted",
            )
        proven = result["after"]
    return proven if bound else None


def _require_proven_input_changes(
    payload: Mapping[str, Any],
    sealed: Sequence[Mapping[str, Any]],
    discovered: Sequence[Mapping[str, Any]],
    stage_results: Mapping[str, Mapping[str, Any]] | None,
) -> None:
    """Recognize only input changes proven by bound successful stage results.

    Between planning and deployment a bound stage may legitimately change a
    sealed configuration input; an approved apply removal is the known case.
    Every differing input must chain from its sealed state through succeeded
    receipt outcomes to the live state, with the retained original still
    intact. The input path set itself is closed: new or vanished paths,
    unbound or partial outcomes and mutated originals keep the drift
    rejection.
    """
    sealed_states = {entry["path"]: entry["state"] for entry in sealed}
    live_states = {entry["path"]: entry["state"] for entry in discovered}
    if not stage_results or sealed_states.keys() != live_states.keys():
        _fail("state-conflict", "the sealed OMP configuration sources have drifted")
    operations = _declared_operations(payload)
    for path, sealed_state in sealed_states.items():
        if sealed_state == live_states[path]:
            continue
        if _proven_input_outcome(operations, stage_results, path, sealed_state) != (
            live_states[path]
        ):
            _fail(
                "state-conflict",
                "the sealed OMP configuration sources have drifted",
            )


def _cleanup_safe_input_drift(
    payload: Mapping[str, Any],
    sealed: Sequence[Mapping[str, Any]],
    discovered: Sequence[Mapping[str, Any]],
    stage_results: Mapping[str, Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Recognize only drift provably irrelevant to the cleanup phase.

    Cleanup never redeploys, so a sealed deployment-discovery input whose
    bytes changed since planning need not block legacy retirement — but only
    when the input is deterministically proven to take no part in this
    cleanup. This is never a lexical-disjointness waiver; an input is
    ignored only after every cleanup dependency is shown independent of it:

    - Tool and host choice: cleanup executes only the characterized
      retirement kinds below. A project legacy tree is retired exclusively
      by ``sbtd_trellis_uninstall``: its planner/executor never imports or
      consults OMP runtime configuration, binds an absolute
      ``@mindfoldhq/trellis`` CLI of a supported version plus the verified
      Node executable on a scrubbed child environment, never runs a command
      taken from the plan, and confines every vendor effect to the selected
      project root through the validated relative-path adapter
      (``_join_root`` rejects anything escaping the root) and the sealed
      footprint gate. Global skill retirement writes exactly its validated
      operation target via ``remove_reference`` after preserving the
      verified original. No OMP input byte selects or steers either path.
    - Scope and ownership: every declared operation target (which also
      covers every retained asset, including the MCP write target), the
      exact selected project roots, the private backup vault and every
      ownership/source reference an operation binds are sealed in the
      payload and re-validated by the caller; a drifted input must not
      overlap any of them in either direction, so it cannot be a cleanup
      target, a retained asset, a backup or recovery input, or an
      ownership anchor. The input path set stays closed: new or vanished
      paths change the discovery scope and keep the rejection.
    - Vendor footprint: for each pending characterized ``.trellis``
      retirement the *actual current* vendor footprint is derived with the
      same read-only ``prepare_trellis_uninstall`` planner the executor
      uses, and every resource path it carries is protected exactly — a
      drifted input the vendor would delete, scrub or prune out from under
      is influencing and keeps the rejection, while unrelated project-level
      settings outside the real footprint stay accepted. A retirement
      already proven cleaned by a bound succeeded result whose target is
      still absent runs no vendor plan, so it contributes no footprint; an
      unavailable vendor produces no effects and is reported blocked by the
      executor instead. Project roots themselves stay protected only by
      exact identity: the vendor footprint, not coarse root descent,
      decides which project-local paths participate.
    - Plan, backup and recovery: the cleanup plan derives from the sealed
      operations and the bound verification candidates, backups and stage
      receipts — never from deployment-discovery inputs; receipt-proven
      input changes keep their historical chained acceptance here.
    - Live binding checks stay live: the active profile, target and agent
      directory are still re-derived from the current environment and the
      MCP resource must still match them; only byte equality of the proven
      irrelevant inputs is not re-run.

    Acceptance is limited to inputs whose sealed and live states are both
    ordinary files or genuine absence; a forged non-file sealed state or
    any unknown type keeps the exact historical drift rejection, and live
    links, specials and directories already fail inside source discovery,
    so no state transition becomes a generic waiver. Anything unproven
    keeps that rejection. Returns the ignored deployment-only input
    entries, sorted by path.
    """
    sealed_states = {entry["path"]: entry["state"] for entry in sealed}
    live_states = {entry["path"]: entry["state"] for entry in discovered}
    if sealed_states.keys() != live_states.keys():
        _fail("state-conflict", "the sealed OMP configuration sources have drifted")
    declared = [
        operation
        for project in payload["projects"]
        for operation in project["private_operations"]
    ] + list(payload["shared_operations"])
    operations = _declared_operations(payload)
    roots = [Path(project["root"]) for project in payload["projects"]]
    protected = [Path(operation["target"]) for operation in declared]
    protected.append(Path(payload["backup_root"]))
    for operation in declared:
        for field in (
            operation["ownership"].get("reference"),
            operation["change"].get("source_ref"),
        ):
            if isinstance(field, Mapping) and isinstance(field.get("path"), str):
                protected.append(Path(field["path"]))
    retirements: list[tuple[Mapping[str, Any], Path]] = []
    for operation in declared:
        if operation["phase"] != "cleanup":
            continue
        if (
            operation["change"] != {"kind": "remove"}
            or operation["owner_kind"] != "directory"
            or operation["selector"] != "whole-resource"
        ):
            _fail(
                "scope-conflict",
                "the cleanup dependency scope carries an unknown target kind",
            )
        target = Path(operation["target"])
        if target.name == _LEGACY_TREE and target.parent in roots:
            retirements.append((operation, target))
    if retirements:
        from sbtd_trellis_uninstall import prepare_trellis_uninstall

        cleanup_results = (stage_results or {}).get("cleanup") or {}
        for operation, target in retirements:
            prior = cleanup_results.get(operation["resource_id"])
            if (
                prior is not None
                and prior["status"] == "succeeded"
                and prior["after"] == _ABSENT
                and snapshot(target) == _ABSENT
            ):
                # Proven already cleaned: the retry runs no vendor plan for
                # this tree, so it contributes no footprint to protect.
                continue
            prepared = prepare_trellis_uninstall(target.parent)
            plan = prepared["payload"]
            if plan["status"] != "ready":
                # An unavailable vendor mutates nothing; the executor
                # reports the blocked retirement instead of validating it.
                continue
            protected.extend(Path(resource["path"]) for resource in plan["resources"])
    ignored: list[dict[str, Any]] = []
    for path in sorted(sealed_states):
        sealed_state = sealed_states[path]
        live_state = live_states[path]
        if sealed_state == live_state:
            continue
        proven = _proven_input_outcome(operations, stage_results, path, sealed_state)
        if proven is not None:
            if proven != live_state:
                _fail(
                    "state-conflict",
                    "the sealed OMP configuration sources have drifted",
                )
            continue
        if (
            sealed_state["type"] not in {"file", "absent"}
            or live_state["type"] not in {"file", "absent"}
        ):
            _fail(
                "state-conflict",
                "the sealed OMP configuration sources have drifted",
            )
        candidate = Path(path)
        if any(candidate == root for root in roots) or any(
            candidate.is_relative_to(scope) or scope.is_relative_to(candidate)
            for scope in protected
        ):
            _fail(
                "state-conflict",
                "the sealed OMP configuration sources have drifted",
            )
        ignored.append(
            {"path": path, "sealed_state": sealed_state, "live_state": live_state}
        )
    return ignored


def validate_deployment_declarations(
    payload: Mapping[str, Any],
    *,
    followup_deployed: Mapping[str, Any] | None = None,
    stage_results: Mapping[str, Mapping[str, Any]] | None = None,
    cleanup_only: bool = False,
) -> list[dict[str, Any]] | None:
    """Re-derive the closed deploy write set without trusting a resealed list.

    With ``cleanup_only`` the caller is the migration cleanup phase, which
    never redeploys: every structural, ownership and live host-binding check
    below still runs, but sealed OMP discovery inputs that drifted may be
    accepted by ``_cleanup_safe_input_drift`` only when provably irrelevant
    to the cleanup scope. The ignored deployment-only input entries are
    then returned, sorted by path; every other caller keeps the historical
    proven-change rule and a None return.
    """
    from onboard import default_codex_home

    ignored: list[dict[str, Any]] = []
    roots = sorted(project["root"] for project in payload["projects"])
    successor = payload.get("successor")
    successor_embedded = (
        {}
        if successor is None
        else {result["resource_id"]: result for result in successor["apply_results"]}
    )
    followup_owned = (
        {}
        if payload.get("followup") is None or followup_deployed is None
        else followup_deployed
    )
    all_deploy = [
        operation
        for project in payload["projects"]
        for operation in project["private_operations"]
        if operation["phase"] == "deploy"
    ] + [
        operation
        for operation in payload["shared_operations"]
        if operation["phase"] == "deploy"
    ]
    shared_deploy = [
        operation
        for operation in payload["shared_operations"]
        if operation["phase"] == "deploy"
    ]
    declaration = payload["deployment"]
    if not all_deploy:
        if declaration is not None:
            _fail(
                "semantic-violation",
                "a deployment declaration requires declared deployment operations",
            )
        return ignored if cleanup_only else None
    if declaration is None:
        _fail(
            "semantic-violation",
            "deployment operations require an explicit deployment declaration",
        )
    expected_mode = "init" if shared_deploy else "init-projects"
    if declaration["mode"] != expected_mode:
        _fail("scope-conflict", "the deployment mode does not match its operation set")
    platform = declaration["platform"]
    if platform not in {"codex", "omp"}:
        _fail(
            "invalid-argument", "the deployment platform must be explicitly supported"
        )
    if platform == "codex" and declaration["inputs"]:
        _fail(
            "scope-conflict",
            "the sealed deployment does not match the Codex producer",
        )
    for project in payload["projects"]:
        expected = {
            (str(Path(project["root"]) / "graft"), "build-graft", "whole-resource"),
        }
        if project.get("agents_no_touch") is None:
            expected.add(
                (
                    str(Path(project["root"]) / "AGENTS.md"),
                    "configure-graft",
                    "graft-agents",
                )
            )
        actual = {
            (operation["target"], operation["change"]["kind"], operation["selector"])
            for operation in project["private_operations"]
            if operation["phase"] == "deploy"
        }
        if actual != expected:
            _fail(
                "semantic-violation",
                "the complete private deployment set is missing or altered",
            )
    for operation in all_deploy:
        if (
            operation["change"]["kind"] in {"build-graft", "configure-graft"}
            and operation["change"]["source_ref"] != policy_reference()
        ):
            _fail("ownership-conflict", "a generated deployment policy was altered")
    shared = [
        operation
        for operation in payload["shared_operations"]
        if operation["phase"] == "deploy"
    ]
    if not shared:
        if payload["shared_operations"]:
            _fail(
                "scope-conflict",
                "shared legacy operations require their declared deployment",
            )
        return ignored if cleanup_only else None
    if any(operation["dependent_projects"] != roots for operation in shared):
        _fail(
            "scope-conflict", "shared deployment requires the complete selected batch"
        )
    if platform == "codex":
        if any(operation["selector"] == "graft-omp-mcp" for operation in all_deploy):
            _fail("scope-conflict", "Codex deployment cannot declare OMP resources")
        mcp = [
            operation for operation in shared if operation["selector"] == "graft-mcp"
        ]
        if len(mcp) != 1:
            _fail(
                "semantic-violation",
                "shared Codex deployment requires one complete MCP resource",
            )
        active_home = default_codex_home()
        codex_roots = [
            record
            for record in payload["shared_roots"]
            if record["kind"] == "codex-home"
        ]
        if len(codex_roots) != 1 or codex_roots[0]["path"] != str(active_home):
            _fail(
                "scope-conflict", "deployment must bind the current active Codex HOME"
            )
        expected_mcp = active_home / "config.toml"
        if mcp[0]["target"] != str(expected_mcp):
            _fail(
                "scope-conflict",
                "the MCP resource leaves the current active Codex HOME",
            )
        hooks = [
            operation for operation in shared if operation["selector"] == "graft-hooks"
        ]
        if len(hooks) > 1 or any(
            operation["target"] != str(active_home / "hooks.json")
            for operation in hooks
        ):
            _fail(
                "scope-conflict",
                "the hook resource leaves the current active Codex HOME",
            )
    else:
        from onboard import user_home
        from sbtd_omp_sources import discover_omp_sources

        if any(
            operation["selector"] in {"graft-mcp", "graft-hooks"}
            for operation in shared
        ):
            _fail("scope-conflict", "OMP deployment cannot declare Codex resources")
        mcp = [
            operation
            for operation in shared
            if operation["selector"] == "graft-omp-mcp"
        ]
        if len(mcp) != 1:
            _fail(
                "semantic-violation",
                "shared OMP deployment requires one complete MCP resource",
            )
        discovered = discover_omp_sources(
            [Path(root) for root in roots], home=user_home(), environ=os.environ
        )
        if declaration["inputs"] != discovered["inputs"]:
            if cleanup_only:
                ignored = _cleanup_safe_input_drift(
                    payload,
                    declaration["inputs"],
                    discovered["inputs"],
                    stage_results,
                )
            else:
                _require_proven_input_changes(
                    payload,
                    declaration["inputs"],
                    discovered["inputs"],
                    stage_results,
                )
        if mcp[0]["target"] != discovered["target"]:
            _fail("scope-conflict", "the MCP resource leaves the active OMP profile")
    omp_agents_target = _omp_agents_template_target(
        platform,
        Path(discovered["agent_dir"]) if platform == "omp" else None,
    )
    templates = {
        str(operation.target): operation
        for operation in _installation_templates(
            roots, omp_agents_target=omp_agents_target
        )
    }
    copied = {
        operation["target"]: operation
        for operation in shared
        if operation["change"]["kind"] != "configure-graft"
    }
    if set(copied) != set(templates):
        _fail(
            "semantic-violation",
            "the complete canonical installation deployment set was changed",
        )
    for target, operation in copied.items():
        selected = templates[target]
        directory = selected.kind == "dir"
        source = {"path": str(selected.source), "state": snapshot(selected.source)}
        if (
            operation["change"]
            != {
                "kind": "copy-directory" if directory else "copy-file",
                "source_ref": source,
            }
            or operation["selector"]
            != ("whole-resource" if directory else "global-rules")
            or operation["ownership"]
            != {"kind": "template-source", "reference": source}
        ):
            _fail(
                "ownership-conflict",
                "an installation deployment source is not canonical",
            )
        paused = [
            earlier
            for earlier in payload["shared_operations"]
            if earlier["phase"] == "apply"
            and earlier["target"] == target
            and earlier["selector"] == "pause-legacy-routing"
        ]
        requirement = operation["before_requirement"]
        expected = {
            "kind": "phase-after",
            "phase": "apply",
            "resource_id": operation["resource_id"],
        }
        if paused:
            if len(paused) != 1 or requirement != expected:
                _fail(
                    "ownership-conflict",
                    "global routing must follow its exact paused predecessor",
                )
        elif successor_embedded.get(operation["resource_id"]) is not None:
            if requirement != expected:
                _fail(
                    "ownership-conflict",
                    "global routing must follow its exact paused predecessor",
                )
        elif followup_owned.get(operation["resource_id"]) is not None:
            # A followup batch replaces a predecessor-owned target only from
            # that exact proven deployment outcome, sealed as concrete state.
            if requirement != {
                "kind": "state",
                "state": followup_owned[operation["resource_id"]],
            }:
                _fail(
                    "ownership-conflict",
                    "a followup replacement must start from the exact "
                    "predecessor deployment outcome",
                )
        elif requirement["kind"] != "state" or requirement["state"] not in (
            _ABSENT,
            source["state"],
        ):
            _fail(
                "ownership-conflict",
                "an installation target has unrecognized customized content",
            )
    return ignored if cleanup_only else None


@dataclass(frozen=True)
class DeploymentContext:
    manifest_path: Path
    output_path: Path
    manifest: dict[str, Any]
    applied: dict[str, Any]
    previous: dict[str, Any] | None
    started_at: str
    expected_before: dict[str, Mapping[str, Any]]
    manifest_raw: bytes
    apply_raw: bytes


def _require_output_clear_of_missing(
    output_path: Path, payload: Mapping[str, Any]
) -> None:
    """Keep new evidence off a reconciled record's missing historical path.

    Reconciled deployment evidence cites the historical receipt it observed
    absent; that path stays reserved for the truthful record, so no later
    evidence output may equal it or overlap it in either direction.
    """
    reconciliation = payload.get("reconciliation")
    if reconciliation is None:
        return
    missing = Path(reconciliation["missing_deployment_evidence"]["path"])
    if contracts._publication_paths_overlap(str(output_path), str(missing)):
        _fail(
            "private-scope",
            "deployment evidence must not overlap the cited missing historical receipt",
        )


def load_deployment_context(
    manifest_path: Path,
    apply_path: Path,
    output_path: Path,
    *,
    previous_path: Path | None,
    mode: str,
    roots: Sequence[Path],
    hooks_authorized: bool,
) -> DeploymentContext:
    """All context and actual-state checks precede every deployment write."""
    from sbtd_migration import (
        _check_source_backups,
        _private_document,
        _protected_followup_ancestry,
        _result_index,
        _validate_context,
    )

    if mode not in {"init", "init-projects"}:
        _fail(
            "scope-conflict",
            "migration deployment is supported only by init and init-projects",
        )
    manifest, manifest_raw = _private_document(manifest_path, "manifest")
    applied, apply_raw = _private_document(apply_path, "apply_receipt")
    previous = None
    documents = {"apply_receipt": applied}
    raw_documents = {"manifest": manifest_raw, "apply_receipt": apply_raw}
    if previous_path is not None:
        previous, previous_raw = _private_document(previous_path, "deployment_evidence")
        documents["deployment_evidence"] = previous
        raw_documents["deployment_evidence"] = previous_raw
    contracts.validate_declared_bindings(manifest, documents, raw_documents)
    contracts._bind_success_gate(applied, {"applied", "already-complete"})
    started_at = datetime.now(timezone.utc).isoformat()
    if any(
        contracts._parse_timestamp(document["payload"]["finished_at"])
        > contracts._parse_timestamp(started_at)
        for document in documents.values()
    ):
        _fail(
            "state-conflict",
            "the deployment clock predates its completed input evidence",
        )
    private = require_private_directory(manifest_path.parent)
    if (
        not output_path.is_absolute()
        or output_path.resolve() != output_path
        or output_path == private
        or not output_path.is_relative_to(private)
        or output_path in {manifest_path, apply_path, previous_path}
    ):
        _fail(
            "private-scope",
            "deployment evidence requires a new path inside the manifest directory",
        )
    require_private_directory(output_path.parent)
    if snapshot(output_path) != _ABSENT:
        _fail("state-conflict", "the deployment evidence target already exists")
    for protected_path, is_directory in _protected_followup_ancestry(manifest):
        if contracts._publication_paths_overlap(str(output_path), str(protected_path)):
            _fail(
                "private-scope",
                "deployment evidence must not overlap a protected predecessor object",
            )
    if previous is not None:
        _require_output_clear_of_missing(output_path, previous["payload"])
    declared_roots = {project["root"] for project in manifest["payload"]["projects"]}
    if {str(root) for root in roots} != declared_roots or len(roots) != len(
        declared_roots
    ):
        _fail(
            "scope-conflict",
            "deployment roots must exactly match the confirmed migration batch",
        )
    operations = [
        operation
        for project in manifest["payload"]["projects"]
        for operation in project["private_operations"]
        if operation["phase"] == "deploy"
    ] + [
        operation
        for operation in manifest["payload"]["shared_operations"]
        if operation["phase"] == "deploy"
    ]
    if not operations:
        _fail(
            "missing-deployment-plan",
            "this manifest contains no declared deployment operations",
        )
    if mode == "init-projects" and manifest["payload"]["shared_operations"]:
        _fail(
            "scope-conflict",
            "project-only deployment cannot execute shared-HOME operations",
        )
    declaration = manifest["payload"]["deployment"]
    if declaration is None or declaration["mode"] != mode:
        _fail("scope-conflict", "the init entry must match the sealed deployment scope")
    full_deployment = any(
        operation["selector"] in {"graft-mcp", "graft-omp-mcp"}
        for operation in operations
    )
    if full_deployment != (mode == "init"):
        _fail("scope-conflict", "the init entry must match the sealed deployment scope")
    planned_hooks = any(
        operation["selector"] == "graft-hooks" for operation in operations
    )
    if declaration["platform"] != "codex" and hooks_authorized:
        _fail("scope-conflict", "OMP deployment does not include Codex hooks")
    if planned_hooks != hooks_authorized:
        _fail(
            "authorization-conflict",
            "hook authorization must exactly match the displayed deployment plan",
        )
    _validate_context(manifest_path, manifest, previous=applied, deployment=previous)
    _check_source_backups(manifest)
    from sbtd_graft_entry import validate_build_scope

    for root in roots:
        validate_build_scope(root)
    applied_results, prior_results = _result_index(applied), _result_index(previous)
    resolution = contracts.resolution_stage_results(
        manifest["payload"], {"apply": applied_results}
    )
    expected_before: dict[str, Mapping[str, Any]] = {}
    for operation in operations:
        result = prior_results.get(operation["resource_id"])
        if result is not None and result["status"] == "succeeded":
            expected = result["after"]
        else:
            expected = contracts._expected_before(
                operation["before_requirement"], resolution
            )
            if result is not None and (
                result["before"] is None
                or result["after"] != result["before"]
                or result["before"] != expected
            ):
                _fail(
                    "state-conflict",
                    "a partially written resource needs explicit recovery",
                )
        if expected is None or snapshot(Path(operation["target"])) != expected:
            _fail("state-conflict", "a declared deployment resource has drifted")
        expected_before[operation["resource_id"]] = expected
        if result is not None and result["backup_ref"] is not None:
            reference = result["backup_ref"]
            if snapshot(Path(reference["path"])) != reference["state"]:
                _fail(
                    "original-unavailable",
                    "a prior deployment original is unavailable",
                    3,
                )
    return DeploymentContext(
        manifest_path,
        output_path,
        manifest,
        applied,
        previous,
        started_at,
        expected_before,
        manifest_raw,
        apply_raw,
    )


def _assemble_deployment_evidence(
    context: DeploymentContext,
    results: Mapping[str, Mapping[str, Any]],
    reports: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    failed_smokes: set[str],
    reconciliation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble and fully validate one cumulative evidence document, unsaved.

    This is the pure assembly/validation portion of save_deployment_evidence:
    same project statuses, same payload, same seals and binding checks, but no
    filesystem write. Reconciliation provenance is immutable through a retry
    chain: a fresh current-state record supplies its metadata exactly once, a
    retry of an already reconciled record carries the identical metadata
    forward, and the two can never disagree or silently appear/disappear.
    When reconciliation provenance is present, the raw manifest/apply bytes
    are bound explicitly so the metadata can never point at other inputs.
    """
    from sbtd_migration_verify import validate_deployment_reports

    prior_reconciliation = (
        None
        if context.previous is None
        else context.previous["payload"].get("reconciliation")
    )
    if (
        reconciliation is not None
        and prior_reconciliation is not None
        and reconciliation != prior_reconciliation
    ):
        _fail(
            "provenance-conflict",
            "reconciliation provenance cannot change across a deployment retry",
        )
    effective_reconciliation = (
        reconciliation if reconciliation is not None else prior_reconciliation
    )
    manifest = context.manifest
    projects: list[dict[str, Any]] = []
    shared_operations = [
        operation
        for operation in manifest["payload"]["shared_operations"]
        if operation["phase"] == "deploy"
    ]
    finished = datetime.now(timezone.utc).isoformat()
    window = {
        "started_at": context.started_at,
        "finished_at": finished,
        "previous_deployment_id": context.previous["deployment_id"]
        if context.previous
        else None,
    }
    for declared in manifest["payload"]["projects"]:
        root = declared["root"]
        private_operations = [
            operation
            for operation in declared["private_operations"]
            if operation["phase"] == "deploy"
        ]
        required = private_operations + [
            operation
            for operation in shared_operations
            if root in operation["dependent_projects"]
        ]
        resource_ids = {operation["resource_id"] for operation in required}
        statuses = {
            results[resource]["status"]
            for resource in resource_ids
            if resource in results
        }
        complete = resource_ids <= results.keys() and statuses <= {"succeeded"}
        status = (
            "failed"
            if "failed" in statuses or root in failed_smokes
            else ("blocked" if not complete else "not-verified")
        )
        private_ids = {operation["resource_id"] for operation in private_operations}
        project = {
            "root": root,
            "source_ref": declared["source_ref"],
            "head": declared["head"],
            "status": status,
            "reason": "deployment or smoke is incomplete",
            "nextStep": "Preserve private evidence and resolve the recorded failure before retrying.",
            "private_results": [
                dict(results[rid]) for rid in sorted(private_ids) if rid in results
            ],
            "shared_operation_ids": sorted(
                operation["operation_id"]
                for operation in shared_operations
                if root in operation["dependent_projects"]
                and operation["resource_id"] in results
            ),
            "report_refs": list(reports.get(root, ())),
        }
        if complete and project["report_refs"] and root not in failed_smokes:
            try:
                validate_deployment_reports(
                    window,
                    project,
                    epoch_started=context.applied["payload"]["finished_at"]
                    if context.previous
                    else None,
                )
            except contracts.ContractError:
                project.update(
                    status="failed",
                    reason="the actual deployment reports did not pass acceptance",
                )
            else:
                project.update(status="succeeded", reason="", nextStep="")
        projects.append(project)
    shared_ids = {operation["resource_id"] for operation in shared_operations}
    payload = {
        "manifest_id": manifest["manifest_id"],
        "apply_id": context.applied["apply_id"],
        **window,
        "projects": projects,
        "shared_results": [
            dict(results[rid]) for rid in sorted(shared_ids) if rid in results
        ],
        "status": contracts._aggregate(
            [project["status"] for project in projects],
            ("failed", "blocked", "not-verified"),
            "succeeded",
            None,
        ),
    }
    if effective_reconciliation is not None:
        payload["reconciliation"] = copy.deepcopy(dict(effective_reconciliation))
    evidence = contracts.seal_document("deployment_evidence", payload)
    contracts.validate_cumulative(context.previous, evidence, "deployment_evidence")
    if effective_reconciliation is not None:
        contracts.validate_declared_bindings(
            manifest,
            {"apply_receipt": context.applied, "deployment_evidence": evidence},
            {"manifest": context.manifest_raw, "apply_receipt": context.apply_raw},
        )
    else:
        contracts.validate_declared_bindings(
            manifest,
            {"apply_receipt": context.applied, "deployment_evidence": evidence},
        )
    return evidence


def save_deployment_evidence(
    context: DeploymentContext,
    results: Mapping[str, Mapping[str, Any]],
    reports: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    failed_smokes: set[str],
) -> dict[str, Any]:
    """Seal one observed cumulative deployment, preserving all prior successes.

    The proposed result is fully validated before the single write: a retry
    of reconciled evidence can never claim its cited missing historical
    path, and no invalid result is ever persisted.
    """
    evidence = _assemble_deployment_evidence(
        context, results, reports, failed_smokes=failed_smokes
    )
    _require_output_clear_of_missing(context.output_path, evidence["payload"])
    result = contracts.validate_deployment_result(
        {"path": str(context.output_path), "evidence": evidence}
    )
    from sbtd_migration import (
        _check_reference,
        _check_source_backups,
        _check_stage_backups,
        _operations,
        _require_reconciliation_provenance,
        _result_index,
    )

    provenance = _require_reconciliation_provenance(context.manifest, evidence)
    if provenance:
        for project in context.manifest["payload"]["projects"]:
            no_touch = project.get("agents_no_touch")
            if no_touch is not None:
                provenance += (no_touch["target"], no_touch["template"])
        _check_source_backups(context.manifest)
        _check_stage_backups({"apply": _result_index(context.applied), "deploy": results})
        for operation in _operations(context.manifest):
            if operation["phase"] != "deploy":
                continue
            observed = results.get(operation["resource_id"])
            if observed is None or observed["status"] != "succeeded":
                continue
            _check_reference({"path": operation["target"], "state": observed["after"]})
        for project in evidence["payload"]["projects"]:
            for reference in project["report_refs"]:
                _check_reference(reference)
        for reference in provenance:
            _check_reference(reference)
    save_document(
        context.output_path, evidence, private_root=context.manifest_path.parent
    )
    return result


def run_project_smoke(
    root: Path, runtime: Mapping[str, str], evidence_dir: Path
) -> list[dict[str, Any]]:
    """Real fixed local CLI check; report status never comes from a plan."""
    from sbtd_graft_entry import validate_project, validate_runtime

    validate_runtime(Path(runtime["node"]), Path(runtime["cli"]))
    validate_project(root)
    started = datetime.now(timezone.utc)
    completed = _run_native(root, runtime, ["check", ".", "--json"])
    finished = datetime.now(timezone.utc)
    source_ref, head = _project_revision(root)
    native_ref = (
        source_ref
        if source_ref is not None
        else ("HEAD" if head is not None else "non-git")
    )
    worktree = "dirty" if head is not None else "unknown"
    revision = "dirty" if head is not None else "unknown"
    stem = (
        "api-report-graft-smoke-"
        + hashlib.sha256(str(root).encode()).hexdigest()[:16]
        + "-"
        + started.strftime("%Y_%m_%d-%H_%M_%S-%f")
    )
    report_path = evidence_dir / (stem + ".json")
    summary_path = evidence_dir / (stem + ".md")
    envelope_path = evidence_dir / (stem + ".evidence.json")
    raw = {
        "repositoryKey": hashlib.sha256(str(root).encode()).hexdigest(),
        "projectRoot": str(root),
        "sourceRef": native_ref,
        "sourceCommit": head,
        "worktreeState": worktree,
        "sourceRevision": revision,
        "evidenceSource": "developer-local",
        "trigger": "manual",
        "environmentAlignment": "verified",
        "evidencePublication": "local-only",
        "e2eMode": "smoke-only",
        "mockStrategy": "none",
        "startedAt": started.isoformat(),
        "finishedAt": finished.isoformat(),
        "command": [runtime["node"], runtime["cli"], "check", ".", "--json"],
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "exitCode": completed.returncode,
        "processExitCode": completed.returncode,
        "timedOut": False,
    }
    require_private_directory(evidence_dir)
    raw_ref = save_document(report_path, raw, private_root=evidence_dir)
    summary = (
        "# Graft 结构图部署 smoke\n\n"
        "- 实际执行固定本地 Graft check，读取所选项目；不调用LLM/cloud。\n"
        f"- 运行退出码：{completed.returncode}；模式smoke-only；非full-stack或模型行为证明。\n"
        "- 原始命令、时间、项目/ref/OID、stdout/stderr见同stem私有JSON。\n"
        "- 无HTTP endpoint；URI覆盖not-needed。此记录不替代真实host事件验证。\n"
    )
    write_file(summary_path, summary.encode(), _ABSENT, scope=evidence_dir)
    envelope = {
        "schemaVersion": 1,
        "runId": stem,
        "createdAt": finished.isoformat(),
        "evidenceSource": "developer-local",
        "trigger": "manual",
        "repository": {
            "repositoryKey": raw["repositoryKey"],
            "sourceRef": native_ref,
            "sourceCommit": head,
            "worktreeState": worktree,
        },
        "sourceRevision": revision,
        "environmentAlignment": "verified",
        "e2eMode": "smoke-only",
        "mockStrategy": "none",
        "featureSources": [],
        "reports": [
            {
                "testType": "api",
                "path": str(report_path),
                "summaryMd": str(summary_path),
                "sha256": raw_ref["state"]["checksum"],
                "status": "passed" if completed.returncode == 0 else "failed",
                "mode": "smoke-only",
            }
        ],
        "evidencePublication": "local-only",
        "secretsRedacted": True,
    }
    envelope_ref = save_document(envelope_path, envelope, private_root=evidence_dir)
    return [
        raw_ref,
        envelope_ref,
        {"path": str(summary_path), "state": snapshot(summary_path)},
    ]


def execute_migration_deployment(
    context: DeploymentContext,
) -> tuple[dict[str, Any], int]:
    """Execute only the sealed deploy closure and save truthful cumulative results."""
    from onboard import resolve_global_skills_dir
    from sbtd_migration import _result_index

    manifest = context.manifest
    runtime = verified_runtime()
    projects = manifest["payload"]["projects"]
    roots = [Path(project["root"]) for project in projects]
    full_installation = any(
        operation["selector"] in {"graft-mcp", "graft-omp-mcp"}
        for operation in manifest["payload"]["shared_operations"]
    )
    launcher_package = (
        resolve_global_skills_dir()[0] / "sbtd-workflow-onboard"
        if full_installation
        else _PACKAGE
    )
    bindings = launch_bindings(roots, runtime, package_root=launcher_package)
    launcher_state = snapshot(_PACKAGE)
    operations = [
        operation
        for project in projects
        for operation in project["private_operations"]
        if operation["phase"] == "deploy"
    ] + [
        operation
        for operation in manifest["payload"]["shared_operations"]
        if operation["phase"] == "deploy"
    ]
    # Active host configuration must never precede its installed launcher.
    operations.sort(
        key=lambda operation: (
            operation["selector"] in {"graft-mcp", "graft-hooks", "graft-omp-mcp"}
        )
    )
    prior = _result_index(context.previous)
    results = {resource: dict(value) for resource, value in prior.items()}
    scopes = {
        operation["resource_id"]: Path(project["root"])
        for project in projects
        for operation in project["private_operations"]
        if operation["phase"] == "deploy"
    }
    for operation in manifest["payload"]["shared_operations"]:
        if operation["phase"] != "deploy":
            continue
        candidates = [
            Path(record["path"])
            for record in manifest["payload"]["shared_roots"]
            if Path(operation["target"]).is_relative_to(Path(record["path"]))
        ]
        if len(candidates) != 1:
            _fail(
                "scope-conflict",
                "a shared deployment target has no unique approved root",
            )
        scopes[operation["resource_id"]] = candidates[0]
    # A followup batch merges the managed fence into the live bytes its
    # outcome gate just proved, keeping fence-outside user text; earlier
    # batch kinds keep the explicit template-replacement authorization.
    install_template = manifest["payload"].get("followup") is None
    from sbtd_migration_plan import approved_agents_provenance

    # Signature-approved project routing keeps its exact approved body: the
    # re-proved manifest chain (origin signature, sealed target and
    # candidate states), never the live bytes or a name prefix, authorizes
    # preservation. Targets without provenance keep the explicit template
    # replacement or followup merge behavior. The same per-target base feeds
    # the preflight render and the executing render below.
    _origin, approved_bodies = approved_agents_provenance(manifest)
    # Render every config against the currently expected bytes before the first
    # mutation; malformed/foreign ownership cannot fail after another write.
    for operation in operations:
        if operation["change"]["kind"] != "configure-graft":
            continue
        state = snapshot(Path(operation["target"]))
        render_configuration(
            operation,
            b""
            if state["type"] == "absent"
            else read_file(Path(operation["target"]), state),
            bindings,
            install_template=install_template,
            approved_body=approved_bodies.get(operation["target"]),
        )
    vault = Path(manifest["payload"]["backup_root"])
    stopped = False
    for operation in operations:
        resource = operation["resource_id"]
        old = prior.get(resource)
        if old is not None and old["status"] == "succeeded":
            continue
        if stopped:
            break
        scope = scopes[resource]
        backup_path = vault / manifest["manifest_id"] / "deploy" / resource
        expected = context.expected_before[resource]
        result = execute_resource(
            operation,
            expected=expected,
            root=scope,
            private_root=vault,
            backup_path=backup_path,
            bindings=bindings,
            runtime=runtime,
            install_template=install_template,
            launcher_state=launcher_state,
            approved_body=approved_bodies.get(operation["target"]),
        )
        if old is not None and old["backup_ref"] is not None:
            result["backup_ref"] = old["backup_ref"]
        results[resource] = result
        stopped = result["status"] != "succeeded"
    reports: dict[str, Sequence[Mapping[str, Any]]] = {
        project["root"]: list(project["report_refs"])
        for project in (
            context.previous["payload"]["projects"] if context.previous else ()
        )
    }
    failed_smokes: set[str] = set()
    if not stopped:
        for root in roots:
            try:
                reports[str(root)] = run_project_smoke(
                    root, runtime, context.manifest_path.parent
                )
            except (contracts.ContractError, OSError, RuntimeError, ValueError):
                failed_smokes.add(str(root))
        # Native check is expected to be read-only. Any unexpected resource
        # mutation invalidates completion instead of rewriting the receipt proof.
        for operation in operations:
            result = results.get(operation["resource_id"])
            if result is None or result["status"] != "succeeded":
                continue
            try:
                unchanged = snapshot(Path(operation["target"])) == result["after"]
            except (contracts.ContractError, OSError, RuntimeError, ValueError):
                unchanged = False
            if not unchanged:
                failed_smokes.update(operation["dependent_projects"])
    try:
        production = save_deployment_evidence(
            context, results, reports, failed_smokes=failed_smokes
        )
    except (contracts.ContractError, OSError, RuntimeError, ValueError):
        return {
            "status": "failed",
            "deploymentEvidence": None,
            "reason": "deployment evidence could not be safely saved; observed writes are retained",
            "operationResults": list(results.values()),
            "nextStep": "Preserve originals and inspect observed results; do not infer a usable receipt.",
        }, 5
    status = production["evidence"]["payload"]["status"]
    return {
        "status": status,
        "deploymentEvidence": production,
        "projects": production["evidence"]["payload"]["projects"],
        "operationResults": list(results.values()),
    }, {"succeeded": 0, "not-verified": 3, "blocked": 2, "failed": 5}[status]


def run_migration_init(mode: str, args: Any) -> int:
    """Dedicated existing-init context, before unrelated installer side effects."""
    from onboard import (
        default_codex_home,
        expand_path,
        resolve_global_skills_dir,
        resolve_project_roots,
    )
    from sbtd_migration import _argument_path

    payload: dict[str, Any] = {"mode": mode, "deploymentEvidence": None}
    try:
        if (
            getattr(args, "graft_retire_legacy", False)
            or getattr(args, "graft_legacy_bindings", None)
        ):
            _fail(
                "scope-conflict",
                "legacy MCP retirement requires a new explicit installation plan, not a sealed historical deployment",
            )
        if mode != "init-projects" and getattr(args, "no_mcp", False):
            _fail(
                "scope-conflict",
                "sealed deployment cannot omit its declared host wiring",
            )
        if not args.yes:
            _fail(
                "confirmation-required",
                "migration deployment requires its own explicit confirmation",
            )
        selected_platform = getattr(args, "platform", None)
        if selected_platform == "oh-my-pi":
            selected_platform = "omp"
        if selected_platform not in {None, "codex", "omp"}:
            _fail(
                "scope-conflict",
                "this deployment context supports only its declared host",
            )
        if getattr(args, "developer", None) is not None:
            _fail(
                "scope-conflict",
                "deployment cannot create an undeclared developer identity",
            )
        if getattr(args, "skip_project_agents", False):
            _fail(
                "scope-conflict",
                "deployment cannot omit a declared project instruction resource",
            )
        canonical_scopes = {
            "global_agents_path": default_codex_home() / "AGENTS.md",
            "global_skills_dir": resolve_global_skills_dir()[0],
        }
        for name, expected in canonical_scopes.items():
            provided = getattr(args, name, None)
            if provided is not None and (
                mode == "init-projects" or expand_path(provided) != expected
            ):
                _fail(
                    "scope-conflict",
                    "installation scope options must match the sealed deployment batch",
                )
        context = load_deployment_context(
            _argument_path(args.migration_manifest),
            _argument_path(args.migration_apply_receipt),
            _argument_path(args.deployment_evidence_out),
            previous_path=_argument_path(args.previous_deployment_evidence)
            if args.previous_deployment_evidence
            else None,
            mode=mode,
            roots=resolve_project_roots(args),
            hooks_authorized=bool(getattr(args, "graft_hooks", False)),
        )
        if (
            selected_platform is not None
            and selected_platform
            != context.manifest["payload"]["deployment"]["platform"]
        ):
            _fail(
                "scope-conflict",
                "the selected host must match the sealed deployment manifest",
            )
        production, code = execute_migration_deployment(context)
        payload.update(production)
    except contracts.ContractError as error:
        code = error.exit_code
        payload.update(
            status="blocked" if code == 2 else "failed",
            reason=str(error),
            nextStep="Resolve the migration precondition without modifying preserved originals.",
        )
    except (OSError, RuntimeError, ValueError, ImportError):
        code = 5
        payload.update(
            status="failed",
            reason="the installed deployment runtime could not safely complete",
            nextStep="Preserve originals and inspect the private execution evidence.",
        )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, allow_nan=False))
    else:
        print("Host deployment: " + str(payload["status"]))
        print(
            "Detailed artifacts remain private; use --json only with authorized private storage."
        )
    return code


def _legacy_binding_input(
    value: str, roots: Sequence[Path]
) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    """Read an explicit private old-runtime contract, never infer its approval."""
    path = _canonical(Path(value).expanduser().absolute())
    require_private_directory(path.parent)
    state = snapshot(path)
    document = contracts._decode_strict(read_file(path, state))
    if (
        not isinstance(document, dict)
        or set(document) != {"schema_version", "bindings"}
        or type(document["schema_version"]) is not int
        or document["schema_version"] != 1
        or not isinstance(document["bindings"], list)
        or not document["bindings"]
    ):
        _fail("invalid-argument", "legacy bindings require a version 1 private binding contract")
    selected = {str(root) for root in roots}
    approved: dict[str, dict[str, str]] = {}
    for binding in document["bindings"]:
        if (
            not isinstance(binding, dict)
            or set(binding) != {"root", "python", "node", "cli", "launcher"}
            or any(not isinstance(item, str) or not os.path.isabs(item) for item in binding.values())
            or binding["root"] not in selected
            or binding["root"] in approved
        ):
            _fail("scope-conflict", "legacy bindings must uniquely name selected roots and absolute runtime paths")
        approved[binding["root"]] = {
            key: item for key, item in binding.items() if key != "root"
        }
    return approved, {"path": str(path), "state": state}


def legacy_bindings_unchanged(plan: Mapping[str, Any]) -> bool:
    """Recheck approval at each mutation boundary, not just when planning."""
    reference = plan.get("legacyBindingsInput")
    if reference is None:
        return True
    try:
        return snapshot(Path(reference["path"])) == reference["state"]
    except (contracts.ContractError, OSError, RuntimeError):
        return False


def plan_normal_wiring(
    mode: str, args: Any, *, installation_targets: Sequence[Path] = ()
) -> dict[str, Any]:
    """Read-only installation feasibility for the selected host/template scope."""
    from onboard import (
        default_codex_home,
        external_skill_target_is_valid,
        resolve_project_roots,
        scoped_skills_root,
        user_home,
    )
    from sbtd_graft_entry import validate_build_scope

    roots = resolve_project_roots(args)
    authorized = bool(getattr(args, "graft_hooks", False))
    retire_legacy = bool(getattr(args, "graft_retire_legacy", False))
    legacy_input = getattr(args, "graft_legacy_bindings", None)
    no_mcp = bool(getattr(args, "no_mcp", False))
    if no_mcp and (authorized or retire_legacy or legacy_input):
        return {
            "status": "blocked",
            "reason": "--no-mcp cannot authorize global hooks or legacy MCP retirement",
        }
    if legacy_input and not retire_legacy:
        return {
            "status": "blocked",
            "reason": "legacy bindings require explicit --graft-retire-legacy authorization",
        }
    selected = getattr(args, "platform", None)
    platform = "omp" if selected in {"omp", "oh-my-pi"} else selected
    if platform not in {"codex", "omp"}:
        if authorized or retire_legacy:
            return {
                "status": "blocked",
                "reason": "Graft configuration changes require an explicitly selected supported host",
            }
        return {"status": "skipped", "reason": "Graft host wiring was not selected"}
    if no_mcp and not roots:
        return {"status": "skipped", "reason": "MCP configuration was explicitly disabled"}
    if authorized and not roots:
        return {
            "status": "blocked",
            "reason": "hook authorization requires an explicitly selected Codex project batch",
        }
    if retire_legacy and not roots:
        return {
            "status": "blocked",
            "reason": "legacy retirement requires the exact formerly bound project roots",
        }
    if mode == "init-projects" and (authorized or retire_legacy):
        return {
            "status": "blocked",
            "reason": "project-only setup cannot change global hooks or retire global MCP entries",
        }
    if platform != "codex" and authorized:
        return {
            "status": "blocked",
            "reason": "OMP wiring does not include Codex hooks",
        }
    try:
        _validate_selected_root_batch(roots)
        try:
            runtime = verified_runtime()
        except contracts.ContractError as error:
            if error.code != "runtime-unavailable" or authorized or retire_legacy:
                raise
            return {
                "status": "not-available",
                "reason": str(error),
                "nextStep": "Continue with source/LSP; install the pinned Graft only after separate confirmation.",
                "hooks": "not-installed",
            }
        records = []
        for root in roots:
            _project_revision(root)
            validate_build_scope(root)
            if snapshot(root / "graft")["type"] not in {"absent", "directory"}:
                _fail(
                    "ownership-conflict",
                    "the selected graph path has another owner type",
                )
            records.append(
                {"root": str(root), "platforms": [platform], "private_operations": []}
            )
        codex_home = None
        omp_home = None
        discovered = None
        if mode != "init-projects" and not no_mcp:
            if platform == "codex":
                codex_home = default_codex_home()
            else:
                from sbtd_omp_sources import discover_omp_sources

                discovered = discover_omp_sources(
                    roots, home=user_home(), environ=os.environ
                )
                omp_home = Path(discovered["agent_dir"])
        private, shared = deployment_operations(
            records,
            codex_home=codex_home,
            omp_home=omp_home,
            platform=platform,
            hooks_authorized=authorized,
        )
        host_home = codex_home if codex_home is not None else omp_home
        launcher_package = (
            scoped_skills_root(args) / "sbtd-workflow-onboard"
            if host_home is not None
            else _PACKAGE
        )
        launcher_state = snapshot(_PACKAGE)
        if (
            host_home is not None
            and mode != "reset"
            and external_skill_target_is_valid(
                launcher_package.parent, launcher_package.name
            )
            and snapshot(launcher_package) != launcher_state
        ):
            _fail(
                "runtime-unavailable",
                "the retained installed Onboard differs; explicitly reset it before installing new wiring",
            )
        bindings: list[dict[str, Any]] = list(
            launch_bindings(roots, runtime, package_root=launcher_package)
        )
        legacy_reference = None
        if legacy_input:
            legacy_bindings, legacy_reference = _legacy_binding_input(legacy_input, roots)
            approval_path = Path(legacy_reference["path"])
            # Full init/reset also replaces global Skills before wiring begins.
            # Reject the complete selected skills root, including external targets.
            targets = [scoped_skills_root(args), *installation_targets]
            for target in targets:
                target = _canonical(target)
                if approval_path == target or target in approval_path.parents:
                    _fail("scope-conflict", "legacy bindings must be outside every installation write target")
            for binding in bindings:
                if binding.get("root") in legacy_bindings:
                    binding["legacy"] = legacy_bindings[binding["root"]]
        for operation in [
            item for group in private.values() for item in group
        ] + shared:
            if legacy_reference is not None:
                approval_path = Path(legacy_reference["path"])
                target = Path(operation["target"])
                if approval_path == target or target in approval_path.parents:
                    _fail("scope-conflict", "legacy bindings must be outside deployment write targets")
            if operation["change"]["kind"] != "configure-graft":
                continue
            state = snapshot(Path(operation["target"]))
            render_configuration(
                operation,
                b""
                if state["type"] == "absent"
                else read_file(Path(operation["target"]), state),
                bindings,
                install_template=not bool(getattr(args, "skip_project_agents", False)),
                retire_legacy=retire_legacy,
                # Normal wiring has no migration manifest chain, so no target
                # can carry signature-approved AGENTS provenance.
                approved_body=None,
            )
        moment = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        backup_scopes = roots + ([host_home] if host_home is not None else [])
        return {
            "status": "planned",
            "reason": "",
            "roots": [str(root) for root in roots],
            "codexHome": str(codex_home) if codex_home is not None else None,
            "ompHome": str(omp_home) if omp_home is not None else None,
            "deploymentPlatform": platform,
            "ompInputs": list(discovered["inputs"]) if discovered is not None else [],
            "hooksAuthorized": authorized,
            "retireLegacy": retire_legacy,
            "legacyBindingsInput": legacy_reference,
            "runtime": runtime,
            "privateOperations": private,
            "sharedOperations": shared,
            "bindings": bindings,
            "launcherPackage": str(launcher_package),
            "launcherPackageState": launcher_state,
            "backupRoots": {
                str(scope): str(scope / ".sbtd" / "installation-originals" / moment)
                for scope in backup_scopes
            },
        }
    except contracts.ContractError as error:
        return {"status": "blocked", "reason": str(error)}
    except (OSError, RuntimeError, ValueError, ImportError):
        return {
            "status": "blocked",
            "reason": "the selected host wiring could not be safely planned",
        }


def execute_normal_wiring(
    plan: Mapping[str, Any], *, template_written: bool
) -> tuple[dict[str, Any], int]:
    """Run only the previously planned wiring after existing template writes."""
    from onboard import PROJECT_AGENTS_TEMPLATE

    if plan["status"] in {"skipped", "not-available"}:
        return dict(plan), 0
    if plan["status"] != "planned":
        return dict(plan), 2
    try:
        launcher_current = snapshot(Path(plan["launcherPackage"]))
    except (contracts.ContractError, OSError, RuntimeError):
        launcher_current = None
    if launcher_current != plan["launcherPackageState"]:
        return {
            "status": "blocked",
            "reason": "the canonical installed launcher was not verified",
            "operationResults": [],
        }, 2
    operations = [
        operation for group in plan["privateOperations"].values() for operation in group
    ] + list(plan["sharedOperations"])
    roots = [Path(root) for root in plan["roots"]]
    results: dict[str, dict[str, Any]] = {}
    scope_by_resource = {
        operation["resource_id"]: Path(root)
        for root, group in plan["privateOperations"].items()
        for operation in group
    }
    host_home = plan.get("codexHome") or plan.get("ompHome")
    if host_home is not None:
        scope_by_resource.update(
            {
                operation["resource_id"]: Path(host_home)
                for operation in plan["sharedOperations"]
            }
        )
    if not legacy_bindings_unchanged(plan):
        return {
            "status": "blocked",
            "reason": "the approved legacy bindings changed since the displayed plan",
            "operationResults": [],
        }, 2
    for reference in plan.get("ompInputs", []):
        if snapshot(Path(reference["path"])) != reference["state"]:
            return {
                "status": "blocked",
                "reason": "an OMP configuration source changed since its displayed plan",
                "operationResults": [],
            }, 2
    for operation in operations:
        scope = scope_by_resource[operation["resource_id"]]
        expected = operation["before_requirement"]["state"]
        if operation["selector"] == "graft-agents" and template_written:
            expected = snapshot(PROJECT_AGENTS_TEMPLATE)
        if snapshot(Path(operation["target"])) != expected:
            return {
                "status": "blocked",
                "reason": "a wiring resource changed since its displayed plan",
                "operationResults": [],
            }, 2
    for operation in operations:
        if not legacy_bindings_unchanged(plan):
            return {
                "status": "blocked",
                "reason": "the approved legacy bindings changed before resource execution",
                "operationResults": list(results.values()),
            }, 2
        resource = operation["resource_id"]
        scope = scope_by_resource[resource]
        private = Path(plan["backupRoots"][str(scope)])
        expected = operation["before_requirement"]["state"]
        if operation["selector"] == "graft-agents" and template_written:
            expected = snapshot(PROJECT_AGENTS_TEMPLATE)
        result = execute_resource(
            operation,
            expected=expected,
            root=scope,
            private_root=private,
            backup_path=private / resource,
            bindings=plan["bindings"],
            runtime=plan["runtime"],
            launcher_state=plan["launcherPackageState"],
            retire_legacy=bool(plan.get("retireLegacy", False)),
            approved_body=None,
        )
        results[resource] = result
        if result["status"] != "succeeded":
            break
    projects = []
    for root in roots:
        required = [
            operation
            for operation in operations
            if str(root) in operation["dependent_projects"]
        ]
        complete = all(
            results.get(operation["resource_id"], {}).get("status") == "succeeded"
            for operation in required
        )
        projects.append(
            {
                "projectRoot": str(root),
                "status": "success" if complete else "failed",
                "reason": ""
                if complete
                else "not every declared wiring resource completed",
                "nextStep": ""
                if complete
                else "Preserve installation originals and inspect the failed wiring.",
            }
        )
    status = (
        "success"
        if len(results) == len(operations)
        and all(result["status"] == "succeeded" for result in results.values())
        and all(project["status"] == "success" for project in projects)
        else "failed"
    )
    return {
        "status": status,
        "projects": projects,
        "operationResults": list(results.values()),
        "hooks": "configured-needs-host-trust"
        if plan["hooksAuthorized"]
        else "not-installed",
        "validationScope": (
            "selected-files-and-native-graph; host-event-acceptance-separate"
            if roots
            else "shared-host-definition-only; project-query-not-verified"
        ),
    }, 0 if status == "success" else 5
