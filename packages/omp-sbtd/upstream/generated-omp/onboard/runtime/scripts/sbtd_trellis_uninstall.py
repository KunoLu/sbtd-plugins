"""Sealed prepare/execute wrapper for the vendor Trellis uninstaller.

``prepare_trellis_uninstall`` is a read-only planner: it proves the project
root is safe, binds the ``tl`` executable to its installed
``@mindfoldhq/trellis`` package (failing closed on any unsupported planner
version), replays the vendor's own pure planning modules
(``pruneOrphanManifestKeys`` with ``persist: false`` and
``buildManagedRemovalPlan`` with ``strictPaths: true``) through a Node import
that never writes, and corroborates the result against the vendor's genuine
``tl uninstall --dry-run`` output. The returned document is a JSON-safe
exact footprint: every file deletion, every structured-config scrub
(including the AGENTS.md Trellis marker block), the single ``.trellis``
tree removal and every conditional empty-directory prune carries a verified
``before`` state and an ``expected_after`` state. A missing tool, an
unsupported planner version or a missing vendor manifest seals an
``unavailable`` document instead of raising; integrity failures still raise.

``execute_trellis_uninstall`` revalidates the sealed scope (root, tool
binding, planner replay equality and every ``before`` state), preserves a
private backup of every potential vendor mutation, and only then invokes
the absolute vendor binary ``tl uninstall -y`` with the project root as its
working directory. The module never deletes ``.trellis`` itself and never
executes a command taken from the plan. Child PATH is bound to the
verified Node executable for both dry-run and uninstall; ``NODE_OPTIONS``
and ``NODE_PATH`` are stripped alongside the vendor safeguard bypass
variables (``TRELLIS_ALLOW_HOMEDIR`` /
``TRELLIS_ALLOW_DIRTY_UNINSTALL``), so the vendor guards stay armed.

A vendor failure is measured, never narrated: per-resource ``after`` states
are re-snapshotted and compared with ``expected_after`` so a partial run is
reported as ``partial`` with exactly which resources changed, instead of
claiming the project was left intact. Raw vendor stdout/stderr is never
copied into public errors or outcomes; it lands, ANSI-stripped and bounded,
only in the private outcome evidence document beside the backups. All
contract violations raise :class:`onboard_contracts.ContractError`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

import onboard_contracts as contracts
from sbtd_migration_files import (
    backup_reference,
    read_file,
    require_private_directory,
    save_document,
    snapshot,
)

TRELLIS_PACKAGE_NAME = "@mindfoldhq/trellis"
SUPPORTED_TRELLIS_VERSIONS = ("0.6.17",)
TRELLIS_DIR = ".trellis"
PREPARED_KIND = "trellis-uninstall-prepare"

_ABSENT = {"type": "absent", "checksum": None}
_STATE_TYPES = ("absent", "file", "directory")
_HEX = frozenset("0123456789abcdef")
_BYPASS_VARS = ("TRELLIS_ALLOW_HOMEDIR", "TRELLIS_ALLOW_DIRTY_UNINSTALL")
_PLANNER_MODULES = (
    "dist/commands/uninstall.js",
    "dist/configurators/index.js",
    "dist/utils/managed-removal.js",
    "dist/utils/manifest-prune.js",
    "dist/utils/template-hash.js",
)
_PLANNER_TIMEOUT = 60
_VENDOR_TIMEOUT = 120
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_DELETED_HEADER = re.compile(r"^Will be deleted \((\d+) entries\):", re.MULTILINE)
_MODIFIED_HEADER = re.compile(r"^Will be modified \((\d+) files\):", re.MULTILINE)
_MISSING_HEADER = re.compile(r"\((\d+) manifest entries already missing", re.MULTILINE)
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")

# Pure read-only replay of the vendor planner: loadHashes ->
# getConfiguredPlatforms -> pruneOrphanManifestKeys(persist: false) ->
# buildManagedRemovalPlan(strictPaths: true), plus a pure simulation of the
# vendor's conditional empty-directory pruning so expected_after states are
# exact. The script only reads the filesystem and prints one JSON document.
_PLANNER_SOURCE = r"""
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [pkgRoot, cwd] = process.argv.slice(1);
const url = (rel) => pathToFileURL(path.join(pkgRoot, rel)).href;
const { loadHashes } = await import(url("dist/utils/template-hash.js"));
const config = await import(url("dist/configurators/index.js"));
const { pruneOrphanManifestKeys } = await import(url("dist/utils/manifest-prune.js"));
const { buildManagedRemovalPlan } = await import(url("dist/utils/managed-removal.js"));

const out = (obj) => { process.stdout.write(JSON.stringify(obj)); };
const hashes = loadHashes(cwd);
if (Object.keys(hashes).length === 0) { out({ status: "no-manifest" }); process.exit(0); }
const platforms = [...config.getConfiguredPlatforms(cwd)];
const { pruned, hashes: kept } =
    pruneOrphanManifestKeys(cwd, platforms, hashes, { persist: false });
let plan;
try {
    plan = buildManagedRemovalPlan(cwd, kept, { strictPaths: true });
} catch (error) {
    out({ status: "plan-error", message: String((error && error.message) || error) });
    process.exit(0);
}

const gone = new Set();
const goneDirs = new Set();
for (const d of plan.deletions) if (!d.missing) gone.add(d.posixPath);
if (plan.removeTrellisDir) {
    const walk = (rel) => {
        let entries;
        try { entries = fs.readdirSync(path.join(cwd, rel), { withFileTypes: true }); }
        catch { return; }
        for (const e of entries) {
            const child = `${rel}/${e.name}`;
            if (e.isDirectory()) walk(child);
            else gone.add(child);
        }
        goneDirs.add(rel);
    };
    walk(".trellis");
}

const candidates = new Set();
const dirname = (p) => path.posix.dirname(p);
for (const d of plan.deletions) {
    if (d.missing) continue;
    let dir = dirname(d.posixPath);
    while (dir !== "." && dir !== "" &&
           config.isManagedPath(dir) && !config.isManagedRootDir(dir)) {
        candidates.add(dir);
        dir = dirname(dir);
    }
}
for (const managed of config.ALL_MANAGED_DIRS) {
    if (managed === ".trellis") continue;
    candidates.add(managed);
    let dir = dirname(managed);
    while (dir !== "." && dir !== "") { candidates.add(dir); dir = dirname(dir); }
}

const sorted = [...candidates].sort((a, b) => b.split("/").length - a.split("/").length);
const prunable = new Set();
for (const dir of sorted) {
    if (goneDirs.has(dir)) { prunable.add(dir); continue; }
    const abs = path.join(cwd, ...dir.split("/"));
    let stat;
    try { stat = fs.lstatSync(abs); } catch { continue; }
    if (!stat.isDirectory() || stat.isSymbolicLink()) continue;
    let entries;
    try { entries = fs.readdirSync(abs, { withFileTypes: true }); } catch { continue; }
    let empty = true;
    for (const e of entries) {
        const child = `${dir}/${e.name}`;
        if (e.isDirectory()) {
            if (!prunable.has(child) && !goneDirs.has(child)) { empty = false; break; }
        } else if (!gone.has(child)) { empty = false; break; }
    }
    if (empty) { prunable.add(dir); goneDirs.add(dir); }
}

out({
    status: "ok",
    pruned_keys: pruned,
    platforms,
    deletions: plan.deletions.map((d) => ({ path: d.posixPath, missing: d.missing })),
    modifications: plan.modifications.map((m) => ({
        path: m.posixPath, reason: m.reason, content: m.result.content,
    })),
    remove_trellis_dir: plan.removeTrellisDir === true,
    pruned_dirs: [...prunable]
        .filter((d) => d !== ".trellis" && !d.startsWith(".trellis/"))
        .sort(),
});
"""


def _fail(code: str, message: str, *, exit_code: int = 2) -> NoReturn:
    raise contracts.ContractError(code, message, exit_code=exit_code)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="microseconds")


def _digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(contracts.canonical_json_bytes(payload)).hexdigest()


def _scrubbed_environ(environ: Mapping[str, str]) -> dict[str, str]:
    excluded = (*_BYPASS_VARS, "NODE_OPTIONS", "NODE_PATH")
    return {key: value for key, value in environ.items() if key not in excluded}


def _default_which(environ: Mapping[str, str]) -> Callable[[str], str | None]:
    """Executable lookup bound to the caller-provided environment's PATH."""
    search_path = environ.get("PATH", "")

    def lookup(name: str) -> str | None:
        return shutil.which(name, path=search_path)

    return lookup


def _bound_vendor_environ(
    environ: Mapping[str, str], tool: Mapping[str, Any]
) -> dict[str, str]:
    """Keep the vendor shebang on the exact Node binary sealed in the plan."""
    child = _scrubbed_environ(environ)
    node = _resolve_executable(tool["node"], "Node.js")
    previous_path = child.get("PATH", "")
    child["PATH"] = str(node.parent) + (
        os.pathsep + previous_path if previous_path else ""
    )
    selected = shutil.which("node", path=child["PATH"])
    if selected is None or _resolve_executable(selected, "Node.js") != node:
        _fail("tool-binding", "the vendor CLI cannot use its bound Node.js runtime")
    return child


# ---------------------------------------------------------------------------
# Root and scope validation
# ---------------------------------------------------------------------------


def _checked_root(root: object, environ: Mapping[str, str]) -> Path:
    if isinstance(root, str):
        if not root.strip():
            _fail("invalid-argument", "the project root must not be empty")
        candidate = Path(root)
    elif isinstance(root, Path):
        candidate = root
    else:
        _fail("invalid-argument", "the project root must be a path")
    if not candidate.is_absolute() or ".." in candidate.parts:
        _fail("unsafe-path", "the project root must be a canonical absolute path")
    if candidate.is_symlink() or not candidate.is_dir():
        _fail("invalid-root", "the project root is not a real directory")
    try:
        resolved = candidate.resolve()
    except OSError:
        _fail("invalid-root", "the project root cannot be resolved")
    if resolved != candidate:
        _fail("invalid-root", "the project root must not resolve through links")
    if resolved.parent == resolved:
        _fail("invalid-root", "the filesystem root is not a valid uninstall target")
    for variable in ("HOME", "USERPROFILE"):
        raw_home = environ.get(variable)
        if not raw_home:
            continue
        try:
            home = Path(raw_home).resolve()
        except OSError:
            continue
        if home == resolved:
            _fail(
                "home-root-refused",
                "refusing to uninstall in the user home directory",
            )
    return resolved


def _checked_relative(value: object) -> str:
    """Mirror the vendor's strict managed-path validation, lexically."""
    if not isinstance(value, str):
        _fail("plan-unsafe", "the vendor plan carries a non-string path")
    if (
        not value
        or "\\" in value
        or value.startswith("/")
        or _DRIVE_PREFIX.match(value)
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        _fail("plan-unsafe", "the vendor plan carries an invalid managed path")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        _fail("plan-unsafe", "the vendor plan carries an invalid managed path")
    segments = value.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        _fail("plan-unsafe", "the vendor plan carries an invalid managed path")
    return value


def _join_root(root: Path, relative: str) -> Path:
    target = root.joinpath(*relative.split("/"))
    if target == root or not target.is_relative_to(root):
        _fail("plan-unsafe", "the vendor plan escapes the project root")
    return target


def _checked_state(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("invalid-document", "a resource state must be a mapping")
    if set(value) != {"type", "checksum"}:
        _fail("invalid-document", "a resource state must carry type and checksum")
    kind = value["type"]
    checksum = value["checksum"]
    if kind not in _STATE_TYPES:
        _fail("invalid-document", "a resource state type is not supported")
    if kind == "absent":
        if checksum is not None:
            _fail("invalid-document", "an absent state cannot carry a checksum")
    elif not (
        isinstance(checksum, str) and len(checksum) == 64 and _HEX.issuperset(checksum)
    ):
        _fail("invalid-document", "a resource checksum is not a SHA-256 digest")
    return {"type": kind, "checksum": checksum}


# ---------------------------------------------------------------------------
# Executable and package binding
# ---------------------------------------------------------------------------


def _bind_package(resolved_cli: Path) -> dict[str, Any]:
    if resolved_cli.name != "trellis.js" or resolved_cli.parent.name != "bin":
        _fail(
            "tool-binding",
            "the Trellis CLI does not resolve into its package bin directory",
        )
    package_root = resolved_cli.parent.parent
    try:
        document = json.loads((package_root / "package.json").read_bytes())
    except (OSError, UnicodeDecodeError, ValueError):
        _fail("tool-binding", "the Trellis package manifest cannot be read")
    if not isinstance(document, dict) or document.get("name") != TRELLIS_PACKAGE_NAME:
        _fail("tool-binding", "the Trellis CLI is not bound to its expected package")
    version = document.get("version")
    if version not in SUPPORTED_TRELLIS_VERSIONS:
        raise contracts.ContractError(
            "tool-version-unsupported",
            "the installed Trellis planner version is not supported",
            details={"package_root": str(package_root), "package_version": version},
        )
    sealed_files: dict[str, dict[str, Any]] = {}
    for relative in ("bin/trellis.js", "package.json", *_PLANNER_MODULES):
        state = snapshot(package_root / relative)
        if state["type"] != "file":
            _fail("tool-binding", "the Trellis package files are incomplete")
        sealed_files[relative] = state
    return {
        "package_root": str(package_root),
        "package_version": version,
        "package_files": sealed_files,
    }


def _resolve_executable(found: object, description: str) -> Path:
    if not found:
        _fail("tool-unavailable", f"the {description} executable is not installed")
    path = Path(found) if isinstance(found, str) else found
    if not isinstance(path, Path) or not path.is_absolute():
        _fail("tool-binding", f"the {description} executable path is not absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        _fail("tool-binding", f"the {description} executable cannot be resolved")
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        _fail("tool-binding", f"the {description} executable is not runnable")
    return resolved


def _bind_tool(which: Callable[[str], str | None]) -> dict[str, Any]:
    requested: str | None = None
    found: str | None = None
    for name in ("tl", "trellis"):
        found = which(name)
        if found:
            requested = name
            break
    if requested is None or found is None:
        _fail("tool-unavailable", "the Trellis CLI (tl) is not installed")
    resolved = _resolve_executable(found, "Trellis CLI")
    binding = _bind_package(resolved)
    node = _resolve_executable(which("node"), "Node.js")
    return {
        "requested": requested,
        "path": str(resolved),
        "node": str(node),
        "package_root": binding["package_root"],
        "package_name": TRELLIS_PACKAGE_NAME,
        "package_version": binding["package_version"],
        "package_files": binding["package_files"],
    }


def _recheck_tool(recorded: object) -> dict[str, Any]:
    """Re-prove the sealed binding points at the same supported package."""
    if not isinstance(recorded, Mapping):
        _fail("invalid-document", "the prepared tool binding is missing")
    path = recorded.get("path")
    if not isinstance(path, str) or not path:
        _fail("invalid-document", "the prepared tool binding has no path")
    resolved = _resolve_executable(path, "Trellis CLI")
    if str(resolved) != path:
        _fail("scope-conflict", "the Trellis CLI binding changed after preparation")
    binding = _bind_package(resolved)
    for key in (
        "requested",
        "node",
        "package_root",
        "package_name",
        "package_version",
        "package_files",
    ):
        if recorded.get(key) is None:
            _fail("invalid-document", "the prepared tool binding is incomplete")
    if recorded["package_name"] != TRELLIS_PACKAGE_NAME:
        _fail("invalid-document", "the prepared tool binding names another package")
    if (
        binding["package_root"] != recorded["package_root"]
        or binding["package_version"] != recorded["package_version"]
    ):
        _fail("scope-conflict", "the Trellis package changed after preparation")
    if binding["package_files"] != recorded["package_files"]:
        _fail("scope-conflict", "the Trellis package files changed after preparation")
    node = _resolve_executable(recorded["node"], "Node.js")
    if str(node) != recorded["node"]:
        _fail("scope-conflict", "the Node.js binding changed after preparation")
    return {
        "requested": recorded["requested"],
        "path": path,
        "node": str(node),
        "package_root": binding["package_root"],
        "package_name": TRELLIS_PACKAGE_NAME,
        "package_version": binding["package_version"],
        "package_files": binding["package_files"],
    }


# ---------------------------------------------------------------------------
# Vendor planner replay and dry-run evidence
# ---------------------------------------------------------------------------


def _run_subprocess(
    runner: Callable[..., Any],
    command: Sequence[str],
    root: Path,
    *,
    timeout: int,
    environ: Mapping[str, str],
) -> Any:
    try:
        return runner(
            list(command),
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_scrubbed_environ(environ),
        )
    except (OSError, subprocess.TimeoutExpired):
        _fail("vendor-run-failed", "a vendor read-only probe could not complete")


def _run_planner(
    root: Path,
    tool: Mapping[str, str],
    runner: Callable[..., Any],
    environ: Mapping[str, str],
) -> dict[str, Any]:
    command = [
        tool["node"],
        "--input-type=module",
        "-e",
        _PLANNER_SOURCE,
        tool["package_root"],
        str(root),
    ]
    completed = _run_subprocess(
        runner, command, root, timeout=_PLANNER_TIMEOUT, environ=environ
    )
    if completed.returncode != 0:
        _fail("planner-failed", "the vendor planner replay did not complete")
    try:
        document = json.loads(completed.stdout)
    except (TypeError, ValueError):
        _fail("planner-failed", "the vendor planner replay returned no plan")
    if not isinstance(document, dict):
        _fail("planner-failed", "the vendor planner replay returned no plan")
    status = document.get("status")
    if status == "no-manifest":
        _fail(
            "manifest-missing",
            "the .trellis manifest is missing; Trellis-owned files cannot be proven",
        )
    if status == "plan-error":
        _fail("plan-unsafe", "the vendor planner rejected its own managed paths")
    if status != "ok":
        _fail("planner-failed", "the vendor planner replay returned no plan")
    return _checked_plan(document)


def _checked_plan(document: Mapping[str, Any]) -> dict[str, Any]:
    def string_list(key: str) -> list[str]:
        value = document.get(key)
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            _fail(
                "planner-failed", "the vendor planner replay returned a malformed plan"
            )
        return list(value)

    deletions: list[dict[str, Any]] = []
    raw_deletions = document.get("deletions")
    if not isinstance(raw_deletions, list):
        _fail("planner-failed", "the vendor planner replay returned a malformed plan")
    for entry in raw_deletions:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("path"), str)
            or not isinstance(entry.get("missing"), bool)
        ):
            _fail(
                "planner-failed", "the vendor planner replay returned a malformed plan"
            )
        deletions.append(
            {"path": _checked_relative(entry["path"]), "missing": entry["missing"]}
        )
    modifications: list[dict[str, Any]] = []
    raw_modifications = document.get("modifications")
    if not isinstance(raw_modifications, list):
        _fail("planner-failed", "the vendor planner replay returned a malformed plan")
    for entry in raw_modifications:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("path"), str)
            or not isinstance(entry.get("reason"), str)
            or not isinstance(entry.get("content"), str)
        ):
            _fail(
                "planner-failed", "the vendor planner replay returned a malformed plan"
            )
        modifications.append(
            {
                "path": _checked_relative(entry["path"]),
                "reason": entry["reason"],
                "content": entry["content"],
            }
        )
    if document.get("remove_trellis_dir") is not True:
        _fail(
            "planner-failed", "the vendor planner replay keeps the .trellis directory"
        )
    return {
        "deletions": deletions,
        "modifications": modifications,
        "pruned_keys": [_checked_relative(v) for v in string_list("pruned_keys")],
        "platforms": string_list("platforms"),
        "pruned_dirs": [_checked_relative(v) for v in string_list("pruned_dirs")],
        "remove_trellis_dir": True,
    }


def _dry_run_evidence(
    root: Path,
    tool: Mapping[str, str],
    runner: Callable[..., Any],
    plan: Mapping[str, Any],
    *,
    environ: Mapping[str, str],
) -> dict[str, Any]:
    command = [tool["path"], "uninstall", "--dry-run"]
    completed = _run_subprocess(
        runner,
        command,
        root,
        timeout=_VENDOR_TIMEOUT,
        environ=_bound_vendor_environ(environ, tool),
    )
    if completed.returncode != 0:
        _fail("vendor-dry-run-failed", "the vendor dry run refused the uninstall plan")
    output = _ANSI.sub("", f"{completed.stdout}\n{completed.stderr}")
    deleted = _DELETED_HEADER.search(output)
    if deleted is None:
        _fail("plan-evidence-mismatch", "the vendor dry run output cannot be verified")
    expected_modifications = len(plan["modifications"])
    modified = _MODIFIED_HEADER.search(output)
    if modified is None:
        # tl 0.6.17 omits the "Will be modified" section when it is empty.
        if expected_modifications != 0:
            _fail(
                "plan-evidence-mismatch",
                "the vendor dry run output cannot be verified",
            )
        modified_files = 0
    else:
        modified_files = int(modified.group(1))
    missing = _MISSING_HEADER.search(output)
    deleted_entries = int(deleted.group(1))
    missing_entries = int(missing.group(1)) if missing else 0
    present_deletions = sum(1 for item in plan["deletions"] if not item["missing"])
    skipped = sum(1 for item in plan["deletions"] if item["missing"])
    expected_deleted = present_deletions + 1  # the .trellis/ tree line
    if (
        deleted_entries != expected_deleted
        or modified_files != expected_modifications
        or missing_entries != skipped
    ):
        _fail(
            "plan-evidence-mismatch",
            "the vendor dry run disagrees with the planner replay",
        )
    return {
        "command": command,
        "exit": completed.returncode,
        "deleted_entries": deleted_entries,
        "modified_files": modified_files,
        "missing_entries": missing_entries,
        "matches_planner": True,
    }


# ---------------------------------------------------------------------------
# Footprint construction
# ---------------------------------------------------------------------------


def _file_checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _resources(
    root: Path, plan: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    resources: list[dict[str, Any]] = []
    skipped: list[str] = []
    seen: set[str] = set()

    def add(
        kind: str, relative: str, expected_after: Mapping[str, Any], reason=None
    ) -> None:
        if relative in seen:
            _fail("plan-unsafe", "the vendor plan repeats a managed path")
        seen.add(relative)
        target = _join_root(root, relative)
        before = snapshot(target)
        if before["type"] == "absent":
            _fail("plan-unsafe", "the vendor plan mutates an absent path")
        resource = {
            "resource_id": f"trellis-{len(resources):03d}",
            "kind": kind,
            "path": str(target),
            "relative": relative,
            "before": before,
            "expected_after": dict(expected_after),
        }
        if reason is not None:
            resource["reason"] = reason
        resources.append(resource)

    for deletion in plan["deletions"]:
        relative = deletion["path"]
        if relative == TRELLIS_DIR or relative.startswith(f"{TRELLIS_DIR}/"):
            continue  # covered by the single vendor-trellis-dir tree resource
        if deletion["missing"]:
            skipped.append(relative)
            continue
        add("vendor-delete", relative, _ABSENT)
    for modification in plan["modifications"]:
        expected = {"type": "file", "checksum": _file_checksum(modification["content"])}
        add(
            "vendor-scrub",
            modification["path"],
            expected,
            reason=modification["reason"],
        )
        if resources[-1]["before"]["type"] != "file":
            _fail("plan-unsafe", "the vendor plan scrubs a non-regular file")
    if plan["remove_trellis_dir"]:
        add("vendor-trellis-dir", TRELLIS_DIR, _ABSENT)
        if resources[-1]["before"]["type"] != "directory":
            _fail("plan-unsafe", "the .trellis path is not a real directory")
    for relative in plan["pruned_dirs"]:
        if relative == TRELLIS_DIR or relative.startswith(f"{TRELLIS_DIR}/"):
            continue
        add("vendor-prune-dir", relative, _ABSENT)
        if resources[-1]["before"]["type"] != "directory":
            _fail("plan-unsafe", "the vendor plan prunes a non-directory path")
    return resources, skipped


def _scope_fingerprint(
    resources: Sequence[Mapping[str, Any]], skipped: Sequence[str]
) -> dict[str, Any]:
    return {
        "resources": [
            {
                "relative": resource["relative"],
                "kind": resource["kind"],
                "expected_after": resource["expected_after"],
            }
            for resource in resources
        ],
        "skipped_missing": list(skipped),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def prepare_trellis_uninstall(
    root: str | Path,
    *,
    environ: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """Seal the exact vendor uninstall footprint for one project root.

    Read-only: the planner replays the vendor's pure modules with
    ``persist: false`` and the dry run never writes. Every resource carries
    its verified ``before`` and ``expected_after`` states; the whole
    ``.trellis`` tree is exactly one ``vendor-trellis-dir`` entry. The
    payload ``status`` is ``ready`` (vendor bound and plan sealed),
    ``absent`` (no ``.trellis`` — nothing to uninstall) or ``unavailable``
    (vendor CLI missing, unsupported planner version or missing manifest;
    ``reason`` and ``unavailable_code`` carry the sanitized evidence).
    Raises :class:`onboard_contracts.ContractError` for an unsafe root, an
    untrustworthy tool binding, an unsafe plan, or any disagreement between
    the planner replay and the vendor dry run.
    """
    environment = os.environ if environ is None else environ
    lookup = _default_which(environment) if which is None else which
    checked = _checked_root(root, environment)
    trellis_state = snapshot(checked / TRELLIS_DIR)

    def sealed(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "kind": PREPARED_KIND,
            "prepared_id": _digest(payload),
            "payload": payload,
        }

    if trellis_state["type"] == "absent":
        return sealed(
            {
                "root": str(checked),
                "prepared_at": _now(),
                "status": "absent",
                "tool": None,
                "planner": None,
                "evidence": None,
                "resources": [],
                "skipped_missing": [],
                "pruned_keys": [],
                "platforms": [],
            }
        )
    if trellis_state["type"] != "directory":
        _fail("unsafe-path", "the project .trellis path is not a real directory")
    tool: dict[str, Any] | None = None
    unavailable: tuple[str, str] | None = None
    try:
        tool = _bind_tool(lookup)
    except contracts.ContractError as error:
        if error.code not in ("tool-unavailable", "tool-version-unsupported"):
            raise
        unavailable = (error.code, error.message)
        if error.details:
            tool = dict(error.details)
    plan: dict[str, Any] | None = None
    if unavailable is None:
        if tool is None:
            _fail("tool-unavailable", "the vendor runtime binding is unavailable")
        try:
            plan = _run_planner(checked, tool, runner, environment)
        except contracts.ContractError as error:
            if error.code != "manifest-missing":
                raise
            unavailable = (error.code, error.message)
    if unavailable is not None:
        return sealed(
            {
                "root": str(checked),
                "prepared_at": _now(),
                "status": "unavailable",
                "reason": unavailable[1],
                "unavailable_code": unavailable[0],
                "tool": tool,
                "planner": None,
                "evidence": None,
                "resources": [],
                "skipped_missing": [],
                "pruned_keys": [],
                "platforms": [],
            }
        )
    if tool is None or plan is None:
        _fail("plan-evidence-mismatch", "the vendor preparation is incomplete")
    resources, skipped = _resources(checked, plan)
    evidence = {
        "dry_run": _dry_run_evidence(checked, tool, runner, plan, environ=environment)
    }
    return sealed(
        {
            "root": str(checked),
            "prepared_at": _now(),
            "status": "ready",
            "tool": tool,
            "planner": {
                "source": "node-import",
                "strict_paths": True,
                "prune_persist": False,
            },
            "evidence": evidence,
            "resources": resources,
            "skipped_missing": skipped,
            "pruned_keys": plan["pruned_keys"],
            "platforms": plan["platforms"],
            "scope": _scope_fingerprint(resources, skipped),
        }
    )


def _bound_resource_path(root: Path, resource: Mapping[str, Any]) -> Path:
    target = _join_root(root, _checked_relative(resource.get("relative")))
    if resource.get("path") != str(target):
        _fail(
            "invalid-document",
            "a prepared resource path does not match its project-relative path",
        )
    return target


def _checked_prepared(prepared: object) -> dict[str, Any]:
    if not isinstance(prepared, Mapping):
        _fail("invalid-argument", "the prepared uninstall document must be a mapping")
    if prepared.get("schema_version") != 1 or prepared.get("kind") != PREPARED_KIND:
        _fail(
            "invalid-document",
            "the prepared uninstall document has an unsupported shape",
        )
    payload = prepared.get("payload")
    prepared_id = prepared.get("prepared_id")
    if not isinstance(payload, Mapping) or not isinstance(prepared_id, str):
        _fail("invalid-document", "the prepared uninstall document is incomplete")
    if _digest(payload) != prepared_id:
        _fail(
            "binding-violation",
            "the prepared uninstall document does not match its identifier",
        )
    status = payload.get("status")
    if status not in ("ready", "absent", "unavailable") or not isinstance(
        payload.get("root"), str
    ):
        _fail("invalid-document", "the prepared uninstall document is incomplete")
    resources = payload.get("resources")
    skipped = payload.get("skipped_missing")
    if not isinstance(resources, list) or not isinstance(skipped, list):
        _fail("invalid-document", "the prepared uninstall document is incomplete")
    seen: set[str] = set()
    for resource in resources:
        if not isinstance(resource, Mapping):
            _fail("invalid-document", "a prepared resource has an unsupported shape")
        kind = resource.get("kind")
        if kind not in (
            "vendor-delete",
            "vendor-scrub",
            "vendor-trellis-dir",
            "vendor-prune-dir",
        ):
            _fail("invalid-document", "a prepared resource kind is not supported")
        relative = resource.get("relative")
        path = resource.get("path")
        if not isinstance(relative, str) or not isinstance(path, str):
            _fail("invalid-document", "a prepared resource is missing its paths")
        if not isinstance(resource.get("resource_id"), str):
            _fail("invalid-document", "a prepared resource is missing its identifier")
        if relative in seen:
            _fail("invalid-document", "a prepared resource is repeated")
        seen.add(relative)
        _bound_resource_path(Path(payload["root"]), resource)
        _checked_state(resource.get("before"))
        _checked_state(resource.get("expected_after"))
    if status in ("absent", "unavailable"):
        return dict(prepared)
    tool = payload.get("tool")
    evidence = payload.get("evidence")
    scope = payload.get("scope")
    if not isinstance(tool, Mapping) or not isinstance(evidence, Mapping):
        _fail("invalid-document", "the prepared uninstall document is incomplete")
    if scope != _scope_fingerprint(resources, skipped):
        _fail("invalid-document", "the prepared uninstall scope is inconsistent")
    return dict(prepared)


def _private_subdirectory(parent: Path, name: str) -> Path:
    target = parent / name
    try:
        os.mkdir(target, 0o700)
    except FileExistsError:
        pass
    except OSError:
        _fail("write-failed", "the backup directory cannot be created", exit_code=3)
    return require_private_directory(target)


def _measure(
    resource: Mapping[str, Any], backup: dict[str, Any], path: Path
) -> dict[str, Any]:
    record = {
        "resource_id": resource["resource_id"],
        "kind": resource["kind"],
        "path": str(path),
        "relative": resource["relative"],
        "before": resource["before"],
        "backup_ref": backup,
    }
    try:
        after = snapshot(path)
    except contracts.ContractError:
        record["after"] = None
        record["status"] = "unknown"
        return record
    record["after"] = after
    if after == resource["expected_after"]:
        record["status"] = (
            "scrubbed" if resource["kind"] == "vendor-scrub" else "removed"
        )
    elif after == resource["before"]:
        record["status"] = "unchanged"
    else:
        record["status"] = "unexpected"
    return record


_OUTPUT_LIMIT = 4000


def _sanitize_output(value: object) -> str | None:
    """Bound vendor output for the private evidence record; never public."""
    if not isinstance(value, str):
        return None
    text = _ANSI.sub("", value)
    if len(text) > _OUTPUT_LIMIT:
        text = f"{text[:_OUTPUT_LIMIT]}\u2026"
    return text


def _save_evidence(directory: Path, document: Mapping[str, Any]) -> dict[str, Any]:
    """Persist the private outcome evidence once; identical retries reuse it.

    The file name is content-addressed so a retried execution with a
    different measured outcome gets its own immutable document instead of
    colliding with the first attempt's evidence.
    """
    payload = contracts.canonical_json_bytes(document)
    checksum = hashlib.sha256(payload).hexdigest()
    target = directory / f"outcome-{checksum[:16]}.json"
    if os.path.lexists(target):
        if read_file(target) == payload:
            return {
                "path": str(target),
                "state": {"type": "file", "checksum": checksum},
            }
        _fail(
            "state-conflict",
            "the vendor outcome evidence already exists with different content",
            exit_code=3,
        )
    return save_document(target, document, private_root=directory)


def execute_trellis_uninstall(
    root: str | Path,
    prepared: Mapping[str, Any],
    backup_root: str | Path,
    *,
    environ: Mapping[str, str] | None = None,
    runner: Callable[..., Any] = subprocess.run,
    before_execute: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Back up every prepared resource, then run the vendor uninstaller.

    Revalidates the sealed document, the root, the tool/package binding and
    every ``before`` state; a fresh planner replay must reproduce the sealed
    scope exactly. An ``unavailable`` prepared document is refused before
    anything runs; an ``absent`` one is a verified no-op. Only after every
    potential vendor mutation is preserved inside ``backup_root`` — and every
    ``skipped_missing`` path is re-proven absent — does the
    absolute ``tl uninstall -y`` run with the project root as its working
    when nothing changed, ``partial`` when any resource mutated) — never
    raised and never claimed harmless. The full outcome, including
    ANSI-stripped bounded vendor stdout/stderr, is persisted once as the
    private content-addressed outcome evidence document beside the backups.
    """
    environment = os.environ if environ is None else environ
    checked = _checked_root(root, environment)
    document = _checked_prepared(prepared)
    payload = document["payload"]
    if payload["root"] != str(checked):
        _fail("scope-conflict", "the prepared uninstall belongs to a different root")
    prepared_id = document["prepared_id"]
    resources: list[Mapping[str, Any]] = payload["resources"]
    resource_paths = [_bound_resource_path(checked, resource) for resource in resources]
    outcome: dict[str, Any] = {
        "status": None,
        "root": str(checked),
        "prepared_id": prepared_id,
        "command": None,
        "exit": None,
        "results": [],
        "errors": [],
        "backups": {"root": None, "refs": []},
        "evidence_ref": None,
    }
    if payload["status"] == "unavailable":
        _fail(
            "vendor-unavailable",
            "the prepared uninstall recorded no usable vendor uninstaller",
        )
    if payload["status"] == "absent":
        if snapshot(checked / TRELLIS_DIR) != _ABSENT:
            _fail("state-conflict", "the project changed after preparation")
        outcome["status"] = "removed"
        return outcome
    tool = _recheck_tool(payload["tool"])
    replay = _run_planner(checked, tool, runner, environment)
    replay_resources, replay_skipped = _resources(checked, replay)
    replay_paths = [
        _bound_resource_path(checked, resource) for resource in replay_resources
    ]
    if (
        _scope_fingerprint(replay_resources, replay_skipped) != payload["scope"]
        or replay_paths != resource_paths
    ):
        _fail("scope-conflict", "the vendor plan changed after preparation")
    for resource, path in zip(resources, resource_paths):
        if snapshot(path) != resource["before"]:
            _fail(
                "state-conflict",
                f"a prepared uninstall resource changed after preparation: "
                f"{resource['relative']}",
            )
    vault = require_private_directory(Path(backup_root))
    if vault.is_relative_to(checked) or checked.is_relative_to(vault):
        _fail("scope-violation", "the backup root must not overlap the project root")
    backup_dir = _private_subdirectory(vault, prepared_id)
    backups_dir = _private_subdirectory(backup_dir, "resources")
    backup_refs: list[dict[str, Any]] = []
    for index, (resource, path) in enumerate(zip(resources, resource_paths)):
        reference = backup_reference(
            {"path": str(path), "state": resource["before"]},
            backups_dir / f"{index:03d}",
            private_root=vault,
        )
        backup_refs.append(reference)
    if _checked_root(checked, environment) != checked:
        _fail("scope-conflict", "the project root changed during backup")
    for resource, path in zip(resources, resource_paths):
        if snapshot(path) != resource["before"]:
            _fail(
                "state-conflict",
                "a prepared uninstall resource changed during backup",
            )
    for relative in payload["skipped_missing"]:
        target = _join_root(checked, _checked_relative(relative))
        if snapshot(target) != _ABSENT:
            _fail(
                "state-conflict",
                "a manifest path recorded as missing reappeared during backup: "
                f"{relative}",
            )
    command = [tool["path"], "uninstall", "-y"]
    outcome["command"] = command
    outcome["backups"] = {"root": str(backup_dir), "refs": backup_refs}
    exit_code: int | None = None
    start_error: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    if before_execute is not None:
        before_execute()
    try:
        completed = runner(
            command,
            cwd=str(checked),
            capture_output=True,
            text=True,
            timeout=_VENDOR_TIMEOUT,
            env=_bound_vendor_environ(environment, tool),
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except (OSError, subprocess.TimeoutExpired):
        start_error = "the vendor uninstall could not complete"
    outcome["exit"] = exit_code
    results = [
        _measure(resource, backup_refs[index], path)
        for index, (resource, path) in enumerate(zip(resources, resource_paths))
    ]
    outcome["results"] = results
    matched = sum(record["status"] in ("removed", "scrubbed") for record in results)
    changed = sum(
        record["status"] in ("removed", "scrubbed", "unexpected") for record in results
    )
    unknown = sum(record["status"] == "unknown" for record in results)
    errors: list[str] = []
    if start_error is not None:
        errors.append(f"vendor-run-failed: {start_error}")
    elif exit_code != 0:
        errors.append(
            f"vendor-refused: the vendor uninstall exited {exit_code}; "
            "per-resource after states are measured in results"
        )
    if unknown:
        errors.append(
            "measurement-failed: a resource state could not be re-measured "
            "after the vendor run"
        )
    if matched == len(results) and exit_code == 0:
        outcome["status"] = "removed"
    elif changed == 0 and unknown == 0:
        outcome["status"] = "failed"
    else:
        outcome["status"] = "partial"
    if outcome["status"] != "removed" and not errors:
        errors.append(
            "vendor-verification: the vendor uninstall completed but the "
            "measured state differs from the sealed plan"
        )
    outcome["errors"] = errors
    evidence = {
        "kind": "trellis-uninstall-outcome",
        "root": str(checked),
        "prepared_id": prepared_id,
        "command": command,
        "exit": exit_code,
        "status": outcome["status"],
        "stdout": _sanitize_output(stdout),
        "stderr": _sanitize_output(stderr),
        "results": results,
        "errors": errors,
        "finished_at": _now(),
    }
    try:
        outcome["evidence_ref"] = _save_evidence(backup_dir, evidence)
    except contracts.ContractError:
        outcome["status"] = "partial"
        outcome["errors"].append(
            "evidence-failed: the private vendor outcome evidence could not be preserved"
        )
    return outcome


__all__ = [
    "PREPARED_KIND",
    "SUPPORTED_TRELLIS_VERSIONS",
    "TRELLIS_PACKAGE_NAME",
    "execute_trellis_uninstall",
    "prepare_trellis_uninstall",
]
