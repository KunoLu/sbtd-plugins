"""Catalog-driven fixed baseline and selected-scope inventory for Onboard upgrades.

This module is the single source of truth for what an upgrade *is*: it loads
the package catalog, validates the pinned stable External Skill set (origin,
licenses and recomputed tree digests), pins the implementation and declared
runtime constraints, and inventories every explicitly selected target against
that fixed baseline. Nothing here is derived from hardcoded Skill lists or
counts; the catalog and stable manifest drive every resource.

Contract (shared with ``sbtd_upgrade`` and ``sbtd_upgrade_hosts``):

``build_inventory(scope, *, package_root=None) -> dict`` returns exactly
``{"baseline", "resources", "domains"}`` and never writes, creates or probes
anything. Only scope-supplied paths and the package itself are inspected;
unselected HOME locations are never discovered.

``normalize_scope(scope) -> dict`` is the same strict validator exposed for
the engine to seal into plans: a JSON-safe, idempotent canonical scope with
physical alias dedup of existing skills roots (proven device/inode identity,
never a blanket casefold), alias-canonical decision keys and one canonical
host platform spelling from ``normalize_host_platform`` (``oh-my-pi`` is
``omp``). Targets nested in the source package — including the exact
same-location installed copy — are supported and classified by content.

* ``baseline.schema_version`` is 1. ``baseline.baseline_id`` is
  ``"sha256:<hex>"`` over the canonical JSON of the catalog summary, stable
  provenance, runtime constraints and known-old evidence pins. It depends on
  content only: install absolute paths, mtimes and the running environment
  never enter it. ``baseline.source`` is ``{"path", "state"}`` for the
  package root; the state checksum is the payload digest below.
* ``resources[]`` carry ``id`` (``"<catalog_id>@<target>"``, the stable
  target identity), ``kind`` (``skill``/``agents``), absolute ``target``,
  ``source`` reference ``{"path", "state"}`` inside the package root,
  ``before``/``desired`` states, ``classification``
  (missing/current/known-old/unknown-drift/identity-conflict), ``decision``
  (install/keep/replace/preserve/blocked) and ``details`` with relative
  POSIX names and digests only — never file content.
* ``domains[]`` explain every selected skills root, AGENTS target, host and
  shell profile, including shared-root attribution and duplicate Onboard
  copies.

Directory checksums everywhere in this module are *payload* digests: the
same construction as ``onboard.external_tree_sha256``, with portable
relative POSIX path ordering and streamed file contents, excluding the declared
generated caches (``__pycache__``/``.pytest_cache``/``.ruff_cache``/
``.mypy_cache`` directories and ``*.pyc``/``*.pyo`` files) and rejecting any
link, reparse point or special entry. They are not the complete-scan
``sbtd_migration_files.snapshot`` digests and must not be fed to the
migration mutation primitives as expected states; the engine snapshots live
targets itself for write mechanics and deep-compares these resources for
plan staleness.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NoReturn

from onboard_contracts import ContractError, canonical_json_bytes
from sbtd_project import TaskDataError, open_regular_file
from sbtd_upgrade_paths import path_contains

__all__ = [
    "BASELINE_SCHEMA_VERSION",
    "build_inventory",
    "normalize_host_platform",
    "normalize_scope",
    "payload_directory_state",
    "payload_file_state",
]

BASELINE_SCHEMA_VERSION = 1

_CACHE_DIRS = frozenset({"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"})
_CACHE_SUFFIXES = frozenset({".pyc", ".pyo"})
_CHUNK = 1024 * 1024
_HEX64 = re.compile(r"[0-9a-f]{64}")
_ENTRY_ID = re.compile(r"(agent|project|skill):[a-z0-9][a-z0-9-]*")
_ABS_PREFIX = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/])")
_PARENT_SEGMENT = re.compile(r"(^|[\\/])\.\.([\\/]|$)")
_ABSENT: dict[str, Any] = {"type": "absent", "checksum": None}

_SCOPE_KEYS = frozenset(
    {"schema_version", "skills_roots", "agents_targets", "hosts", "shell_profiles", "decisions"}
)
_HOST_KEYS = frozenset(
    {"id", "platform", "config_home", "config", "skills_roots", "runtime", "project_roots"}
)
_RUNTIME_KEYS = frozenset({"python", "node", "cli"})
_HOST_OPTIONAL_KEYS = frozenset({"executable", "onboard_root"})
_SHELL_KEYS = frozenset({"path", "shell", "bin"})
_SHELL_NAMES = frozenset({"bash", "zsh", "powershell"})
_DECISION_VALUES = frozenset({"replace", "preserve"})

_HOST_PLATFORM_ALIASES = {"oh-my-pi": "omp"}

_AGENT_TEMPLATE_ID = "agent:codex-global"
_SELF_ENTRY_ID = "skill:sbtd-workflow-onboard"
_ONBOARD_TARGET_ROLE = "skill:sbtd-workflow-onboard"
_STABLE_ROOT = "assets/external-skills/stable"
_STABLE_MANIFEST = f"{_STABLE_ROOT}/MANIFEST.json"
_OWNERSHIP_ASSET = "assets/migration-legacy-ownership.json"
_OWNERSHIP_AGENTS_FIELD = "global_agents_sha256"


def _fail(code: str, message: str) -> NoReturn:
    raise ContractError(code, message, exit_code=2)


# ---------------------------------------------------------------------------
# Canonical paths and safe reads (sbtd_migration_files semantics)
# ---------------------------------------------------------------------------


def _is_reparse(info: os.stat_result) -> bool:
    return bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _lstat(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        _fail("read-failed", "an inventory path cannot be inspected")


def _canonical(path: Path) -> Path:
    """Reject relative paths, ``..`` segments and any link/reparse component."""
    if not path.is_absolute() or ".." in path.parts:
        _fail("unsafe-path", "inventory paths must be absolute without '..' segments")
    current = Path(path.anchor)
    for index, part in enumerate(path.parts[1:]):
        current = current / part
        info = _lstat(current)
        if info is None:
            continue
        if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
            _fail(
                "unsafe-path",
                "inventory paths do not follow symbolic links or junctions",
            )
        if index < len(path.parts) - 2 and not stat.S_ISDIR(info.st_mode):
            _fail("unsafe-path", "an inventory path parent is not a directory")
    return path


def _resolved(value: object, field: str) -> Path:
    """One checked absolute path: link components rejected, spelling kept.

    No ``resolve()`` after the literal walk: re-following here would reopen
    link traversal behind the no-follow preflight and silently rewrite the
    user's spelling that physical alias dedup and decision binding rely on.
    """
    if isinstance(value, str) and not value:
        _fail("invalid-config", f"{field} must be a non-empty absolute path string")
    if not isinstance(value, (str, os.PathLike)):
        _fail("invalid-config", f"{field} must be a non-empty absolute path string")
    return _canonical(Path(value))


def _norm(path: Path) -> str:
    """Checked spelling key; filesystem equivalence requires physical evidence."""
    return str(path)



def _canonical_child(root: Path, relative: str) -> Path:
    """One package-internal path proven link-free on every literal component.

    ``open_regular_file`` protects only the final component, so any path the
    package itself opens (catalog, manifest, licenses, sources) must first be
    walked literally; a symlinked ``stable`` or ``templates`` directory is
    rejected before a single byte is read through it.
    """
    candidate = _canonical(root / relative)
    if not path_contains(candidate, root):
        _fail("source-untrusted", "a package path escapes its root")
    return candidate


def _read_bytes(path: Path, label: str) -> bytes:
    try:
        with open_regular_file(path, label) as handle:
            return handle.read()
    except TaskDataError:
        _fail("read-failed", f"{label} cannot be read safely")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with open_regular_file(path, "inventory file") as handle:
            while chunk := handle.read(_CHUNK):
                digest.update(chunk)
    except TaskDataError:
        _fail("read-failed", "an inventory file cannot be read safely")
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Payload trees: complete file comparison with declared-cache exclusion
# ---------------------------------------------------------------------------


def _list_children(directory: Path) -> list[os.DirEntry[str]]:
    try:
        with os.scandir(directory) as listing:
            children = list(listing)
    except OSError:
        _fail("read-failed", "a directory cannot be listed")
    children.sort(key=lambda entry: os.fsencode(entry.name))
    return children


def _collect_payload_files(root: Path) -> list[str]:
    """Relative POSIX paths of payload files, sorted in portable POSIX order.

    Declared cache directories are excluded from the digest but are still
    traversed: a link, junction or special entry anywhere in the selected
    tree (including inside ``__pycache__``) rejects the tree as unsafe.
    """
    files: list[str] = []

    def walk(directory: Path, prefix: str, collect: bool) -> None:
        for child in _list_children(directory):
            name = child.name
            relative = name if not prefix else f"{prefix}/{name}"
            try:
                info = child.stat(follow_symlinks=False)
            except OSError:
                _fail("read-failed", "a directory entry cannot be inspected")
            if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
                _fail(
                    "unsafe-path",
                    "a payload tree contains a link, junction or special entry",
                )
            if stat.S_ISDIR(info.st_mode):
                walk(Path(child.path), relative, collect and name not in _CACHE_DIRS)
            elif stat.S_ISREG(info.st_mode):
                if collect and Path(name).suffix not in _CACHE_SUFFIXES:
                    files.append(relative)
            else:
                _fail(
                    "unsafe-path",
                    "a payload tree contains a link, junction or special entry",
                )

    try:
        walk(root, "", True)
    except RecursionError:
        _fail("unsafe-path", "a payload tree is deeper than the traversal limit")
    # Plain relative POSIX order: identical to onboard.external_tree_sha256's
    # string-keyed order on every operating system, so the fixed baseline
    # digests stay valid on Windows too.
    files.sort()
    return files


def _payload_scan(root: Path) -> tuple[str, dict[str, str]]:
    """(tree digest, per-file digests) for one payload root.

    The tree digest matches ``onboard.external_tree_sha256`` on POSIX:
    sorted length-prefixed relative POSIX paths and contents, declared
    caches excluded. Files stream into both digests in one pass; the
    opened file's own size frames the content, and any change mid-read
    fails instead of hashing a torn file. Per-file digests back the
    missing/changed/extra difference lists and never include content.
    """
    digest = hashlib.sha256()
    hashes: dict[str, str] = {}
    for relative in _collect_payload_files(root):
        encoded = relative.encode("utf-8")
        per_file = hashlib.sha256()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        try:
            with open_regular_file(root / Path(relative), "payload file") as handle:
                before_info = os.fstat(handle.fileno())
                size = before_info.st_size
                digest.update(size.to_bytes(8, "big"))
                counted = 0
                while chunk := handle.read(_CHUNK):
                    counted += len(chunk)
                    if counted > size:
                        _fail("read-failed", "a payload file changed while it was read")
                    digest.update(chunk)
                    per_file.update(chunk)
                after_info = os.fstat(handle.fileno())
                if (
                    before_info.st_size != after_info.st_size
                    or before_info.st_mtime_ns != after_info.st_mtime_ns
                    or before_info.st_ctime_ns != after_info.st_ctime_ns
                ):
                    _fail("read-failed", "a payload file changed while it was read")
        except TaskDataError:
            _fail("read-failed", "a payload file cannot be read safely")
        if counted != size:
            _fail("read-failed", "a payload file changed while it was read")
        hashes[relative] = per_file.hexdigest()
    return digest.hexdigest(), hashes


class _PayloadCache:
    """One inventory run's scans; a shared root or same-location source is read once."""

    def __init__(self) -> None:
        self._scans: dict[str, tuple[str, dict[str, str]]] = {}

    def scan(self, root: Path) -> tuple[str, dict[str, str]]:
        key = _norm(root)
        if key not in self._scans:
            info = _lstat(root)
            if info is None or not stat.S_ISDIR(info.st_mode):
                _fail("invalid-argument", "a payload root is not a regular directory")
            self._scans[key] = _payload_scan(root)
        return self._scans[key]

    def state(self, root: Path) -> dict[str, Any]:
        return {"type": "directory", "checksum": self.scan(root)[0]}

    def file_map(self, root: Path) -> dict[str, str]:
        return self.scan(root)[1]


def payload_directory_state(path: Path) -> dict[str, Any]:
    """Payload state for one present regular directory (engine re-verification)."""
    target = _canonical(Path(path))
    info = _lstat(target)
    if info is None:
        _fail("invalid-argument", "payload directory is absent")
    if stat.S_ISLNK(info.st_mode) or _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
        _fail("unsafe-path", "payload directory is a link or not a directory")
    return {"type": "directory", "checksum": _payload_scan(target)[0]}


def payload_file_state(path: Path) -> dict[str, Any]:
    """Payload state for one present regular file (engine re-verification)."""
    target = _canonical(Path(path))
    info = _lstat(target)
    if info is None:
        _fail("invalid-argument", "payload file is absent")
    if stat.S_ISLNK(info.st_mode) or _is_reparse(info) or not stat.S_ISREG(info.st_mode):
        _fail("unsafe-path", "payload file is a link or not a regular file")
    return {"type": "file", "checksum": _file_sha256(target)}


# ---------------------------------------------------------------------------
# Package sources: catalog, stable manifest, runtime constraints, evidence
# ---------------------------------------------------------------------------


def _frontmatter_name(path: Path) -> str | None:
    """Read only a bounded YAML header; never materialize the Markdown body.

    Missing, oversized, unterminated or ambiguous headers prove no identity.
    The shared safe YAML loader rejects duplicate keys, unsafe tags and cycles;
    parse failures never disclose file text.
    """
    from sbtd_project import _load_safe_yaml

    limit = 64 * 1024
    try:
        with open_regular_file(path, "Skill identity") as handle:
            first = handle.readline(limit + 1)
            if len(first) > limit or first.strip() != b"---":
                return None
            remaining = limit - len(first)
            header: list[bytes] = []
            while remaining > 0:
                line = handle.readline(remaining + 1)
                if not line or len(line) > remaining:
                    return None
                remaining -= len(line)
                if line.strip() == b"---":
                    break
                header.append(line)
            else:
                return None
    except TaskDataError:
        _fail("read-failed", "a Skill identity cannot be read safely")
    try:
        metadata = _load_safe_yaml(b"".join(header).decode("utf-8"), "Skill identity")
    except (TaskDataError, UnicodeDecodeError):
        return None
    name = metadata.get("name") if isinstance(metadata, dict) else None
    return name if isinstance(name, str) and name else None


def _catalog_contracts() -> dict[str, tuple[str, frozenset[str]]]:
    from onboard import CATALOG_KIND_CONTRACTS

    return CATALOG_KIND_CONTRACTS

def _valid_repository_url(value: object) -> bool:
    from onboard import valid_https_repository_url

    return valid_https_repository_url(value)


def _json_document(raw: bytes, label: str) -> Any:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        _fail("source-untrusted", f"{label} is not valid JSON")


def _validate_relative(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        _fail("source-untrusted", f"{field} must be a non-empty relative path")
    if _ABS_PREFIX.match(value) or _PARENT_SEGMENT.search(value) or Path(value).is_absolute():
        _fail("source-untrusted", f"{field} must stay inside its declared root")
    return value


def _resolve_local_source(package_root: Path, value: object, entry_id: str) -> Path:
    relative = _validate_relative(value, f"catalog source for {entry_id}")
    source = _canonical_child(package_root, relative)
    if _lstat(source) is None:
        _fail("source-untrusted", f"catalog source is missing for {entry_id}")
    return source


def _load_catalog(package_root: Path) -> list[dict[str, Any]]:
    raw = _read_bytes(_canonical_child(package_root, "catalog.json"), "the Onboard catalog")
    catalog = _json_document(raw, "the Onboard catalog")
    if not isinstance(catalog, dict):
        _fail("source-untrusted", "the Onboard catalog must be a JSON object")
    if (
        type(catalog.get("schemaVersion")) is not int
        or catalog.get("schemaVersion") != 1
        or catalog.get("name") != "sbtd-workflow-onboard"
    ):
        _fail("source-untrusted", "the Onboard catalog identity or schema is invalid")
    entries = catalog.get("entries")
    if not isinstance(entries, list) or not entries:
        _fail("source-untrusted", "the Onboard catalog must contain entries")
    contracts = _catalog_contracts()
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"id", "kind", "source", "targetRole"}:
            _fail("source-untrusted", "a catalog entry has invalid fields")
        entry_id = entry["id"]
        kind = entry["kind"]
        if not isinstance(entry_id, str) or _ENTRY_ID.fullmatch(entry_id) is None or entry_id in seen:
            _fail("source-untrusted", "a catalog entry id is invalid or duplicated")
        contract = contracts.get(str(kind))
        if contract is None:
            _fail("source-untrusted", f"a catalog entry kind is invalid for {entry_id}")
        prefix, roles = contract
        target_role = entry["targetRole"]
        if not entry_id.startswith(prefix) or not isinstance(target_role, str) or target_role not in roles:
            _fail("source-untrusted", f"a catalog entry role is invalid for {entry_id}")
        source = entry["source"]
        if kind == "external-skill":
            if not isinstance(source, dict) or set(source) != {"repo", "subpath", "aliases"}:
                _fail("source-untrusted", f"an external catalog source is invalid for {entry_id}")
            repo = source["repo"]
            if not _valid_repository_url(repo):
                _fail("source-untrusted", f"an external catalog repo is invalid for {entry_id}")
            _validate_relative(source.get("subpath"), f"external subpath for {entry_id}")
            aliases = source["aliases"]
            if (
                not isinstance(aliases, list)
                or not aliases
                or any(not isinstance(alias, str) or not alias for alias in aliases)
                or len(aliases) != len(set(aliases))
            ):
                _fail("source-untrusted", f"external catalog aliases are invalid for {entry_id}")
        else:
            resolved = _resolve_local_source(package_root, source, entry_id)
            if entry_id == _SELF_ENTRY_ID and _norm(resolved) != _norm(package_root):
                _fail("source-untrusted", "the Onboard self source must be the complete package root")
            info = _lstat(resolved)
            assert info is not None  # _resolve_local_source rejects absence
            if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
                _fail("unsafe-path", f"catalog source is a link for {entry_id}")
            if kind in {"agent-template", "project-template"}:
                if not stat.S_ISREG(info.st_mode):
                    _fail("source-untrusted", f"catalog template source must be a file for {entry_id}")
            else:
                if not stat.S_ISDIR(info.st_mode):
                    _fail("source-untrusted", f"catalog skill source must be a directory for {entry_id}")
                expected_name = entry_id.removeprefix("skill:")
                skill_md = resolved / "SKILL.md"
                md_info = _lstat(skill_md)
                if md_info is None or not stat.S_ISREG(md_info.st_mode):
                    _fail("source-untrusted", f"bundled skill source lacks SKILL.md for {entry_id}")
                actual_name = _frontmatter_name(skill_md)
                if actual_name != expected_name:
                    _fail(
                        "source-untrusted",
                        f"bundled skill frontmatter does not match {entry_id}",
                    )
        seen.add(entry_id)
        normalized.append(
            {"id": entry_id, "kind": str(kind), "source": source, "targetRole": target_role}
        )
    # A damaged catalog that drops these entries would leave installed managed
    # content unexamined while everything else reports aligned.
    if not any(
        entry["id"] == _SELF_ENTRY_ID
        and entry["kind"] == "bundled-skill"
        and entry["targetRole"] == _ONBOARD_TARGET_ROLE
        for entry in normalized
    ):
        _fail("source-untrusted", "the catalog lacks the Onboard self Skill entry")
    if not any(
        entry["id"] == _AGENT_TEMPLATE_ID
        and entry["kind"] == "agent-template"
        and entry["targetRole"] == "codex-global-agents"
        for entry in normalized
    ):
        _fail("source-untrusted", "the catalog lacks the global AGENTS template entry")
    return normalized

def _load_stable_manifest(
    package_root: Path,
    external: Mapping[str, Mapping[str, Any]],
    cache: _PayloadCache,
) -> dict[str, Any]:
    """Validate stable origin/licenses/digests and return the pinned summary."""
    stable_root = _canonical_child(package_root, _STABLE_ROOT)
    raw = _read_bytes(
        _canonical_child(package_root, _STABLE_MANIFEST),
        "the stable External Skills manifest",
    )
    manifest = _json_document(raw, "the stable External Skills manifest")
    if (
        not isinstance(manifest, dict)
        or type(manifest.get("schemaVersion")) is not int
        or manifest.get("schemaVersion") != 1
    ):
        _fail("source-untrusted", "the stable manifest schema is invalid")
    stable_set = manifest.get("stableSet")
    promoted_at = manifest.get("promotedAt")
    if not isinstance(stable_set, str) or not stable_set or not isinstance(promoted_at, str) or not promoted_at:
        _fail("source-untrusted", "the stable manifest identity is invalid")
    repositories = manifest.get("repositories")
    skills = manifest.get("skills")
    if not isinstance(repositories, dict) or not isinstance(skills, dict):
        _fail("source-untrusted", "the stable manifest must hold repositories and skills")
    if set(skills) != set(external):
        _fail("source-untrusted", "the stable manifest does not match the catalog external set")

    repo_summaries: dict[str, Any] = {}
    for repository_id, repository in repositories.items():
        if not isinstance(repository_id, str) or not repository_id or not isinstance(repository, dict):
            _fail("source-untrusted", "stable repository metadata is invalid")
        url = repository.get("url")
        revision = repository.get("revision")
        license_name = repository.get("license")
        license_files = repository.get("licenseFiles")
        if not _valid_repository_url(url):
            _fail("source-untrusted", "a stable repository url is invalid")
        if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
            _fail("source-untrusted", "a stable repository revision is invalid")
        if not isinstance(license_name, str) or not license_name:
            _fail("source-untrusted", "a stable repository license is invalid")
        if not isinstance(license_files, list) or not license_files:
            _fail("source-untrusted", "a stable repository has no license files")
        license_summary: list[dict[str, str]] = []
        for license_entry in license_files:
            if not isinstance(license_entry, dict) or set(license_entry) != {"source", "stablePath"}:
                _fail("source-untrusted", "a stable license entry is invalid")
            _validate_relative(license_entry["source"], "a license source path")
            stable_path = _validate_relative(license_entry["stablePath"], "a license stable path")
            license_path = _canonical_child(stable_root, stable_path)
            info = _lstat(license_path)
            if info is None or not stat.S_ISREG(info.st_mode):
                _fail("source-untrusted", "a stable license file is missing or not regular")
            license_summary.append(
                {"path": stable_path, "sha256": _file_sha256(license_path)}
            )
        license_summary.sort(key=lambda item: item["path"])
        repo_summaries[repository_id] = {
            "url": url,
            "revision": revision,
            "license": license_name,
            "license_files": license_summary,
        }

    skills_root = stable_root / "skills"
    skill_summaries: dict[str, Any] = {}
    for name in sorted(skills):
        skill = skills[name]
        if not isinstance(skill, dict):
            _fail("source-untrusted", "stable Skill metadata is invalid")
        repository_id = skill.get("repository")
        if not isinstance(repository_id, str):
            _fail("source-untrusted", f"the stable repository id is invalid for {name}")
        repository = repositories.get(repository_id)
        if not isinstance(repository, dict):
            _fail("source-untrusted", f"the stable repository is invalid for {name}")
        source_subpath = skill.get("sourceSubpath")
        stable_path = skill.get("stablePath")
        tree_sha = skill.get("treeSha256")
        catalog_source = external[name]["source"]
        if repository["url"] != catalog_source["repo"]:
            _fail("source-untrusted", f"the stable repository does not match the catalog for {name}")
        if source_subpath != catalog_source["subpath"]:
            _fail("source-untrusted", f"the stable provenance does not match the catalog for {name}")
        _validate_relative(stable_path, f"stablePath for {name}")
        source = _canonical_child(stable_root, str(stable_path))
        if _norm(source.parent) != _norm(skills_root):
            _fail("source-untrusted", f"stablePath for {name} must be a direct child of skills/")
        info = _lstat(source)
        if info is None or not stat.S_ISDIR(info.st_mode):
            _fail("source-untrusted", f"a stable Skill source is not a regular directory for {name}")
        if not isinstance(tree_sha, str) or _HEX64.fullmatch(tree_sha) is None:
            _fail("source-untrusted", f"the stable tree digest is invalid for {name}")
        actual = cache.state(source)["checksum"]
        if actual != tree_sha:
            _fail(
                "source-untrusted",
                f"the stable Skill payload does not match its pinned digest for {name}",
            )
        skill_md = source / "SKILL.md"
        md_info = _lstat(skill_md)
        if md_info is None or not stat.S_ISREG(md_info.st_mode):
            _fail("source-untrusted", f"a stable Skill lacks a regular SKILL.md for {name}")
        if _frontmatter_name(skill_md) != name:
            _fail("source-untrusted", f"a stable Skill frontmatter does not match {name}")
        skill_summaries[name] = {
            "stable_path": str(stable_path),
            "tree_sha256": tree_sha,
            "repository": repository_id,
            "revision": repository["revision"],
            "repo": repository["url"],
            "source_subpath": source_subpath,
        }

    return {
        "stable_set": stable_set,
        "promoted_at": promoted_at,
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "repositories": repo_summaries,
        "skills": skill_summaries,
    }


def _runtime_constraints(package_root: Path) -> dict[str, Any]:
    """Declared dependency constraints plus the implementation source digests."""
    pinned: dict[str, str] = {}
    for relative in ("requirements.txt", "catalog.schema.json", "onboard-contracts.schema.json"):
        candidate = _canonical_child(package_root, relative)
        info = _lstat(candidate)
        if info is None or not stat.S_ISREG(info.st_mode):
            _fail("source-untrusted", f"the declared runtime constraint {relative} is missing")
        pinned[relative] = _file_sha256(candidate)
    scripts = _canonical_child(package_root, "scripts")
    info = _lstat(scripts)
    if info is None or not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        _fail("source-untrusted", "the package scripts directory is invalid")
    implementation: dict[str, str] = {}
    for child in _list_children(scripts):
        if Path(child.name).suffix != ".py":
            continue
        try:
            child_info = child.stat(follow_symlinks=False)
        except OSError:
            _fail("read-failed", "an implementation file cannot be inspected")
        if stat.S_ISLNK(child_info.st_mode) or _is_reparse(child_info):
            _fail("unsafe-path", "an implementation file is a link or reparse entry")
        if not stat.S_ISREG(child_info.st_mode):
            continue
        implementation[f"scripts/{child.name}"] = _file_sha256(Path(child.path))
    if not implementation:
        _fail("source-untrusted", "the package has no implementation files")
    return {
        "requirements_sha256": pinned["requirements.txt"],
        "catalog_schema_sha256": pinned["catalog.schema.json"],
        "onboard_contracts_schema_sha256": pinned["onboard-contracts.schema.json"],
        "implementation": implementation,
    }


def _ownership_agents_pin(package_root: Path) -> tuple[str, str]:
    """(asset digest, pinned legacy global AGENTS digest) — known-old evidence."""
    raw = _read_bytes(_canonical_child(package_root, _OWNERSHIP_ASSET), "the legacy ownership pins")
    document = _json_document(raw, "the legacy ownership pins")
    if (
        not isinstance(document, dict)
        or type(document.get("schema_version")) is not int
        or document.get("schema_version") != 1
    ):
        _fail("source-untrusted", "the legacy ownership pins are malformed")
    agents = document.get(_OWNERSHIP_AGENTS_FIELD)
    if not isinstance(agents, str) or _HEX64.fullmatch(agents) is None:
        _fail("source-untrusted", "the legacy ownership pins are malformed")
    return hashlib.sha256(raw).hexdigest(), agents


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------


def _build_baseline(
    package_root: Path, cache: _PayloadCache
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], str]:
    entries = _load_catalog(package_root)
    external = {
        entry["id"].removeprefix("skill:"): entry
        for entry in entries
        if entry["kind"] == "external-skill"
    }
    stable = _load_stable_manifest(package_root, external, cache)

    catalog_summary: list[dict[str, Any]] = []
    for entry in entries:
        kind = entry["kind"]
        if kind == "external-skill":
            name = entry["id"].removeprefix("skill:")
            pin = stable["skills"][name]
            source_summary: dict[str, Any] = {
                "repo": entry["source"]["repo"],
                "subpath": entry["source"]["subpath"],
                "aliases": list(entry["source"]["aliases"]),
                "stable_path": pin["stable_path"],
                "tree_sha256": pin["tree_sha256"],
            }
        else:
            relative = str(entry["source"])
            resolved = _resolve_local_source(package_root, entry["source"], entry["id"])
            info = _lstat(resolved)
            assert info is not None
            if stat.S_ISREG(info.st_mode):
                source_summary = {"path": relative, "sha256": _file_sha256(resolved)}
            else:
                digest, files = cache.scan(resolved)
                source_summary = {
                    "path": relative,
                    "tree_sha256": digest,
                    "file_count": len(files),
                }
        catalog_summary.append(
            {
                "id": entry["id"],
                "kind": kind,
                "targetRole": entry["targetRole"],
                "source": source_summary,
            }
        )

    runtime = _runtime_constraints(package_root)
    ownership_sha, agents_pin = _ownership_agents_pin(package_root)
    identity_document = {
        "catalog": catalog_summary,
        "stable": stable,
        "runtime": runtime,
        "evidence": {"ownership_sha256": ownership_sha},
    }
    baseline_id = "sha256:" + hashlib.sha256(canonical_json_bytes(identity_document)).hexdigest()
    baseline = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "baseline_id": baseline_id,
        "source": {"path": str(package_root), "state": cache.state(package_root)},
        "catalog": {
            "sha256": _file_sha256(_canonical_child(package_root, "catalog.json")),
            "entries": catalog_summary,
        },
        "stable": stable,
        "runtime": runtime,
        "evidence": {"ownership_sha256": ownership_sha},
    }
    return baseline, entries, stable, agents_pin


# ---------------------------------------------------------------------------
# Scope validation
# ---------------------------------------------------------------------------


def _path_list(value: object, field: str) -> list[Path]:
    if not isinstance(value, list):
        _fail("invalid-config", f"{field} must be an array of absolute paths")
    resolved: list[Path] = []
    seen: set[str] = set()
    for item in value:
        candidate = _resolved(item, field)
        key = _norm(candidate)
        if key not in seen:
            seen.add(key)
            resolved.append(candidate)
    return resolved


def normalize_host_platform(value: object) -> str:
    """One canonical host platform spelling; ``oh-my-pi`` is ``omp``.

    Strict: anything but a non-empty string is rejected. Every other
    declared platform passes through unchanged so the hosts layer keeps
    classifying it (unsupported platforms are reported, never rewritten).
    """
    if not isinstance(value, str) or not value:
        _fail("invalid-config", "a host platform must be a non-empty string")
    return _HOST_PLATFORM_ALIASES.get(value, value)


def _physical_key(path: Path) -> tuple[int, int] | None:
    """Proven physical identity (device, inode) of one existing entry.

    ``None`` when identity cannot be proven — an absent path or a zero
    inode — because distinct paths are never merged on suspicion.
    """
    info = _lstat(path)
    if info is None or not info.st_ino:
        return None
    return (info.st_dev, info.st_ino)


def _canonical_target(
    target: Path, root_identities: Mapping[tuple[int, int], Path]
) -> Path:
    """Rewrite ``target`` through the canonical spelling of any aliased root.

    The nearest existing ancestor decides, so absent child targets under the
    same physical root bind exactly like present ones; paths with no proven
    aliased ancestor keep their spelling untouched.
    """
    if not root_identities:
        return target
    for ancestor in (target, *target.parents):
        key = _physical_key(ancestor)
        canonical = root_identities.get(key) if key is not None else None
        if canonical is not None:
            return canonical.joinpath(*target.parts[len(ancestor.parts):])
    return target


def _canonical_skill_child(target: Path, root_norms: frozenset[str]) -> Path:
    """Fold a direct skill-child alias onto its lowercase catalog spelling.

    Only when physical identity proves both spellings name the same existing
    directory: case-insensitive aliases then bind the canonical resource
    target (and the sealed decision keeps the stable catalog spelling, so a
    later retry against an absent target still binds). Genuinely distinct
    case-sensitive children keep their spelling and stay unselected. Never
    fold anything beyond this one proven child component.
    """
    lowered = target.name.lower()
    if lowered == target.name or _norm(target.parent) not in root_norms:
        return target
    candidate = target.parent / lowered
    info = _lstat(target)
    if info is None or not stat.S_ISDIR(info.st_mode) or not info.st_ino:
        return target
    if (info.st_dev, info.st_ino) == _physical_key(candidate):
        return candidate
    return target

def _validate_hosts(
    value: object,
    top_roots: list[Path],
    root_identities: Mapping[tuple[int, int], Path],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        _fail("invalid-config", "hosts must be an array of host objects")
    top = {_norm(root) for root in top_roots}
    hosts: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in value:
        if (
            not isinstance(item, dict)
            or not _HOST_KEYS.issubset(set(item))
            or set(item) - (_HOST_KEYS | _HOST_OPTIONAL_KEYS)
        ):
            _fail("invalid-config", "a host entry carries undeclared keys")
        host_id = item["id"]
        if not isinstance(host_id, str) or not host_id or host_id in seen_ids:
            _fail("invalid-config", "a host id is invalid or duplicated")
        seen_ids.add(host_id)
        platform = normalize_host_platform(item["platform"])
        config_home = _canonical_target(
            _resolved(item["config_home"], f"host {host_id} config_home"), root_identities
        )
        home_info = _lstat(config_home)
        if home_info is not None and not stat.S_ISDIR(home_info.st_mode):
            _fail("invalid-config", f"host {host_id} config_home is not a directory")
        config = _canonical_target(
            _resolved(item["config"], f"host {host_id} config"), root_identities
        )
        if _norm(config) == _norm(config_home) or not path_contains(config, config_home):
            _fail("unsafe-path", f"host {host_id} config must stay inside its config_home")
        if home_info is not None and home_info.st_ino:
            config = _canonical_target(
                config, {(home_info.st_dev, home_info.st_ino): config_home},
            )
        runtime = item["runtime"]
        if not isinstance(runtime, dict) or set(runtime) != _RUNTIME_KEYS:
            _fail("invalid-config", f"host {host_id} runtime must declare python, node and cli")
        for constraint in runtime.values():
            if constraint is not None and (not isinstance(constraint, str) or not constraint):
                _fail("invalid-config", f"host {host_id} runtime values must be strings or null")
        # Aliases of one physical root collapse to a single canonical root
        # before the installation-binding rules below count them.
        host_roots: list[Path] = []
        seen_roots: set[str] = set()
        for root in (
            _canonical_target(candidate, root_identities)
            for candidate in _path_list(item["skills_roots"], f"host {host_id} skills_roots")
        ):
            key = _norm(root)
            if key not in seen_roots:
                seen_roots.add(key)
                host_roots.append(root)
        for root in host_roots:
            if _norm(root) not in top:
                _fail(
                    "invalid-config",
                    f"host {host_id} skills_roots must also be selected top-level",
                )
        onboard_value = item.get("onboard_root")
        onboard_root = (
            _canonical_target(
                _resolved(onboard_value, f"host {host_id} onboard_root"), root_identities
            )
            if onboard_value is not None else None
        )
        if onboard_root is None and len(host_roots) == 1:
            onboard_root = host_roots[0] / _SELF_ENTRY_ID.removeprefix("skill:")
        if onboard_root is None and platform in {"codex", "omp"}:
            _fail("scope-conflict", f"host {host_id} requires one unambiguous Onboard installation")
        if onboard_root is not None:
            onboard_root = _canonical_skill_child(
                onboard_root, frozenset(_norm(root) for root in host_roots)
            )
        if onboard_root is not None and host_roots and not any(
            _norm(onboard_root) == _norm(root / _SELF_ENTRY_ID.removeprefix("skill:"))
            for root in host_roots
        ):
            _fail("unsafe-path", f"host {host_id} onboard_root must name a selected Onboard installation")
        project_roots = [
            _canonical_target(root, root_identities)
            for root in _path_list(item["project_roots"], f"host {host_id} project_roots")
        ]
        # Optional probe-only host CLI binary: absolute-string shape is the
        # entire contract here; sbtd_upgrade_hosts resolves/executes it (or
        # the platform default) exclusively inside verify_hosts(probe=True).
        executable = item.get("executable")
        if executable is not None and (
            not isinstance(executable, str)
            or not executable
            or not Path(executable).is_absolute()
        ):
            _fail("invalid-config", f"host {host_id} executable must be absolute or null")
        hosts.append(
            {
                "id": host_id,
                "platform": platform,
                "config_home": config_home,
                "config": config,
                "skills_roots": host_roots,
                "runtime": {key: runtime[key] for key in sorted(runtime)},
                "project_roots": project_roots,
                "executable": executable,
                "onboard_root": onboard_root,
            }
        )
    return hosts


def _validate_shells(
    value: object, root_identities: Mapping[tuple[int, int], Path]
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        _fail("invalid-config", "shell_profiles must be an array of profile objects")
    profiles: list[dict[str, Any]] = []
    seen: dict[str, tuple[str, str]] = {}
    for item in value:
        if not isinstance(item, dict) or set(item) != _SHELL_KEYS:
            _fail("invalid-config", "a shell profile must carry exactly path, shell and bin")
        path = _canonical_target(
            _resolved(item["path"], "a shell profile path"), root_identities
        )
        info = _lstat(path)
        if info is not None and not stat.S_ISREG(info.st_mode):
            _fail("invalid-config", "a shell profile path is not a regular file")
        if not isinstance(item["shell"], str) or item["shell"] not in _SHELL_NAMES:
            _fail("invalid-config", "a shell profile must name bash, zsh or powershell")
        bin_dir = _canonical_target(
            _resolved(item["bin"], "a shell profile bin"), root_identities
        )
        bin_info = _lstat(bin_dir)
        if bin_info is not None and not stat.S_ISDIR(bin_info.st_mode):
            _fail("invalid-config", "a shell profile bin is not a directory")
        key = _norm(path)
        declaration = (item["shell"], _norm(bin_dir))
        if key in seen:
            if seen[key] != declaration:
                _fail("invalid-config", "duplicate shell profiles declare conflicting selections")
            continue
        seen[key] = declaration
        profiles.append({"path": path, "shell": item["shell"], "bin": bin_dir})
    return profiles


def _validate_scope(scope: object) -> dict[str, Any]:
    if not isinstance(scope, Mapping):
        _fail("invalid-config", "the upgrade scope must be a JSON object")
    unknown = set(scope) - _SCOPE_KEYS
    if unknown:
        _fail("invalid-config", "the upgrade scope carries unknown keys")
    if type(scope.get("schema_version")) is not int or scope.get("schema_version") != 1:
        _fail("invalid-config", "the upgrade scope schema_version must be 1")

    listed_roots = _path_list(scope.get("skills_roots", []), "skills_roots")
    for root in listed_roots:
        info = _lstat(root)
        if info is not None and not stat.S_ISDIR(info.st_mode):
            _fail("invalid-config", "a selected skills root is not a directory")
    # Spellings proven to name the same existing directory (case-folding
    # volumes, bind mounts) collapse to the first spelling; genuinely
    # distinct case-sensitive roots keep their separate identities.
    root_identities: dict[tuple[int, int], Path] = {}
    skills_roots: list[Path] = []
    for root in listed_roots:
        key = _physical_key(root)
        if key is not None:
            if key in root_identities:
                continue
            root_identities[key] = root
        skills_roots.append(root)
    for index, root in enumerate(skills_roots):
        for other in skills_roots[index + 1 :]:
            if path_contains(root, other) or path_contains(other, root):
                _fail("unsafe-path", "selected skills roots overlap")

    agents_targets = [
        _canonical_target(target, root_identities)
        for target in _path_list(scope.get("agents_targets", []), "agents_targets")
    ]
    for index, target in enumerate(agents_targets):
        for other in agents_targets[index + 1 :]:
            if path_contains(target, other) or path_contains(other, target):
                _fail("unsafe-path", "selected AGENTS targets overlap")
    for target in agents_targets:
        for root in skills_roots:
            if path_contains(target, root) or path_contains(root, target):
                _fail("unsafe-path", "an AGENTS target overlaps a selected skills root")
        info = _lstat(target)
        if info is not None and not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            _fail("unsafe-path", "an AGENTS target is a special file")

    hosts = _validate_hosts(scope.get("hosts", []), skills_roots, root_identities)
    shell_profiles = _validate_shells(scope.get("shell_profiles", []), root_identities)

    root_norms = frozenset(_norm(root) for root in skills_roots)
    non_skill_targets = {str(target) for target in agents_targets}
    non_skill_targets.update(str(host["config"]) for host in hosts)
    non_skill_targets.update(str(profile["path"]) for profile in shell_profiles)
    decision_identities = dict(root_identities)
    for host in hosts:
        home_key = _physical_key(host["config_home"])
        if home_key is not None:
            decision_identities.setdefault(home_key, host["config_home"])
    for selected in sorted(non_skill_targets):
        key = _physical_key(Path(selected))
        if key is not None:
            decision_identities.setdefault(key, Path(selected))

    raw_decisions = scope.get("decisions", {})
    decisions: dict[str, str] = {}
    if not isinstance(raw_decisions, Mapping):
        _fail("invalid-config", "decisions must be an object keyed by absolute targets")
    for raw_target, raw_value in raw_decisions.items():
        target = _resolved(raw_target, "a decision target")
        if str(target) not in non_skill_targets:
            target = _canonical_target(target, decision_identities)
        if str(target) not in non_skill_targets:
            target = _canonical_skill_child(target, root_norms)
        if not isinstance(raw_value, str) or raw_value not in _DECISION_VALUES:
            _fail("invalid-config", "a decision must be replace or preserve")
        key = str(target)
        previous = decisions.get(key)
        if previous is not None:
            if previous != raw_value:
                _fail(
                    "decision-conflict",
                    "aliased spellings of one target carry conflicting decisions",
                )
            continue
        decisions[key] = raw_value

    if not (skills_roots or agents_targets or hosts or shell_profiles):
        _fail("invalid-config", "the upgrade scope selects no resources")

    return {
        "skills_roots": skills_roots,
        "agents_targets": agents_targets,
        "hosts": hosts,
        "shell_profiles": shell_profiles,
        "decisions": decisions,
    }


def _seal_scope(validated: Mapping[str, Any]) -> dict[str, Any]:
    """JSON-safe canonical scope: every path stringified, nothing re-read."""
    return {
        "schema_version": 1,  # the scope schema required by _validate_scope
        "skills_roots": [str(root) for root in validated["skills_roots"]],
        "agents_targets": [str(target) for target in validated["agents_targets"]],
        "hosts": [
            {
                "id": host["id"],
                "platform": host["platform"],
                "config_home": str(host["config_home"]),
                "config": str(host["config"]),
                "skills_roots": [str(root) for root in host["skills_roots"]],
                "runtime": dict(host["runtime"]),
                "project_roots": [str(root) for root in host["project_roots"]],
                "executable": host["executable"],
                "onboard_root": str(host["onboard_root"])
                if host["onboard_root"] is not None else None,
            }
            for host in validated["hosts"]
        ],
        "shell_profiles": [
            {
                "path": str(profile["path"]),
                "shell": profile["shell"],
                "bin": str(profile["bin"]),
            }
            for profile in validated["shell_profiles"]
        ],
        "decisions": dict(validated["decisions"]),
    }


def _scope_paths(sealed: Mapping[str, Any]) -> dict[str, Any]:
    """Path view of a sealed canonical scope for the resource builders."""
    return {
        "skills_roots": [Path(value) for value in sealed["skills_roots"]],
        "agents_targets": [Path(value) for value in sealed["agents_targets"]],
        "hosts": [
            {
                **host,
                "config_home": Path(host["config_home"]),
                "config": Path(host["config"]),
                "skills_roots": [Path(value) for value in host["skills_roots"]],
                "project_roots": [Path(value) for value in host["project_roots"]],
                "onboard_root": Path(host["onboard_root"])
                if host["onboard_root"] is not None else None,
            }
            for host in sealed["hosts"]
        ],
        "shell_profiles": [
            {**profile, "path": Path(profile["path"]), "bin": Path(profile["bin"])}
            for profile in sealed["shell_profiles"]
        ],
        "decisions": dict(sealed["decisions"]),
    }


def normalize_scope(scope: object) -> dict[str, Any]:
    """Strictly validate and canonically normalize one upgrade scope.

    This is the validator the engine seals into plans before deriving
    resources: absolute link-free paths, physical alias dedup of existing
    skills roots, alias-canonical decision keys and the shared host platform
    spelling (``normalize_host_platform``). The result is JSON-safe and
    idempotent: ``normalize_scope(normalize_scope(scope))`` is identical.
    """
    return _seal_scope(_validate_scope(scope))


# ---------------------------------------------------------------------------
# Classification and decisions
# ---------------------------------------------------------------------------


def _target_identity_error(target: Path, expected_name: str) -> dict[str, Any] | None:
    """None only when the drifted target still proves its managed identity."""
    skill_md = target / "SKILL.md"
    info = _lstat(skill_md)
    if info is None:
        return {"kind": "skill-md-missing", "expected": expected_name, "actual_sha256": None}
    if stat.S_ISLNK(info.st_mode) or _is_reparse(info) or not stat.S_ISREG(info.st_mode):
        _fail("unsafe-path", "a target SKILL.md is a link or not a regular file")
    actual = _frontmatter_name(skill_md)
    if actual != expected_name:
        return {
            "kind": "frontmatter-mismatch",
            "expected": expected_name,
            "actual_sha256": hashlib.sha256(actual.encode("utf-8")).hexdigest()
            if actual is not None else None,
        }
    return None


def _diff_details(
    desired_files: Mapping[str, str], before_files: Mapping[str, str]
) -> dict[str, Any]:
    missing = sorted(path for path in desired_files if path not in before_files)
    changed = [
        {"path": path, "before_sha256": before_files[path], "desired_sha256": desired_files[path]}
        for path in sorted(desired_files)
        if path in before_files and before_files[path] != desired_files[path]
    ]
    extra = [
        {"path": path, "sha256": before_files[path]}
        for path in sorted(before_files)
        if path not in desired_files
    ]
    details: dict[str, Any] = {}
    if missing:
        details["missing"] = missing
    if changed:
        details["changed"] = changed
    if extra:
        details["extra"] = extra
    return details


def _resolve_decision(
    classification: str,
    target_key: str,
    decisions: Mapping[str, str],
    details: dict[str, Any],
) -> str:
    chosen = decisions.get(target_key)
    if classification == "missing":
        return "preserve" if chosen == "preserve" else "install"
    if classification == "current":
        return "keep"
    if classification == "identity-conflict":
        if chosen == "replace":
            _fail(
                "decision-conflict",
                "an identity or path conflict cannot be approved as replace",
            )
        return "preserve" if chosen == "preserve" else "blocked"
    # known-old / unknown-drift: existing managed content requires an explicit call.
    if chosen is None:
        details["decision_required"] = True
        return "blocked"
    return chosen


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


def _skill_resources(
    scope: Mapping[str, Any],
    entries: list[dict[str, Any]],
    stable: Mapping[str, Any],
    package_root: Path,
    cache: _PayloadCache,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    skills = [entry for entry in entries if entry["kind"] in {"bundled-skill", "external-skill"}]
    decisions = scope["decisions"]
    resources: list[dict[str, Any]] = []
    onboard_targets: dict[str, str] = {}
    for root in scope["skills_roots"]:
        for entry in skills:
            name = entry["id"].removeprefix("skill:")
            target = root / name
            if entry["kind"] == "external-skill":
                source = _canonical_child(
                    package_root, f"{_STABLE_ROOT}/{stable['skills'][name]['stable_path']}"
                )
            else:
                source = _resolve_local_source(package_root, entry["source"], entry["id"])
            source_state = cache.state(source)
            desired = dict(source_state)
            desired_files = cache.file_map(source)

            info = _lstat(target)
            details: dict[str, Any] = {}
            if info is None:
                before: dict[str, Any] = dict(_ABSENT)
                classification = "missing"
            elif stat.S_ISLNK(info.st_mode) or _is_reparse(info) or not (
                stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)
            ):
                _fail("unsafe-path", "a skill target is a link, junction or special entry")
            elif not stat.S_ISDIR(info.st_mode):
                before = {"type": "file", "checksum": _file_sha256(target)}
                classification = "identity-conflict"
                details["identity"] = {
                    "kind": "type-conflict",
                    "expected": "directory",
                    "actual": "file",
                }
            else:
                before = cache.state(target)
                if before["checksum"] == desired["checksum"]:
                    classification = "current"
                else:
                    identity_error = _target_identity_error(target, name)
                    if identity_error is not None:
                        classification = "identity-conflict"
                        details["identity"] = identity_error
                    else:
                        classification = "unknown-drift"
                        details.update(
                            _diff_details(desired_files, cache.file_map(target))
                        )

            decision = _resolve_decision(classification, str(target), decisions, details)
            resources.append(
                {
                    "id": f"{entry['id']}@{target}",
                    "kind": "skill",
                    "target": str(target),
                    "source": {"path": str(source), "state": source_state},
                    "before": before,
                    "desired": desired,
                    "classification": classification,
                    "decision": decision,
                    "details": details,
                }
            )
            if entry["targetRole"] == _ONBOARD_TARGET_ROLE:
                onboard_targets[_norm(root)] = str(target)
    return resources, onboard_targets


def _agents_resources(
    scope: Mapping[str, Any],
    entries: list[dict[str, Any]],
    package_root: Path,
    agents_pin: str,
) -> list[dict[str, Any]]:
    template = next((entry for entry in entries if entry["id"] == _AGENT_TEMPLATE_ID), None)
    if template is None:
        _fail("source-untrusted", "the catalog lacks the global AGENTS template")
    source = _resolve_local_source(package_root, template["source"], template["id"])
    desired_checksum = _file_sha256(source)
    desired = {"type": "file", "checksum": desired_checksum}
    decisions = scope["decisions"]
    resources: list[dict[str, Any]] = []
    for target in scope["agents_targets"]:
        info = _lstat(target)
        details: dict[str, Any] = {}
        if info is None:
            before = dict(_ABSENT)
            classification = "missing"
        elif stat.S_ISLNK(info.st_mode) or _is_reparse(info):
            _fail("unsafe-path", "an AGENTS target is a link or junction")
        elif stat.S_ISDIR(info.st_mode):
            before = {"type": "directory", "checksum": _payload_scan(target)[0]}
            classification = "identity-conflict"
            details["identity"] = {
                "kind": "type-conflict",
                "expected": "file",
                "actual": "directory",
            }
        elif stat.S_ISREG(info.st_mode):
            checksum = _file_sha256(target)
            before = {"type": "file", "checksum": checksum}
            if checksum == desired_checksum:
                classification = "current"
            elif checksum == agents_pin:
                classification = "known-old"
                details["evidence"] = {
                    "kind": "legacy-ownership-pin",
                    "asset": _OWNERSHIP_ASSET,
                    "field": _OWNERSHIP_AGENTS_FIELD,
                }
            else:
                classification = "unknown-drift"
                details["changed"] = [
                    {
                        "path": target.name,
                        "before_sha256": checksum,
                        "desired_sha256": desired_checksum,
                    }
                ]
        else:
            _fail("unsafe-path", "an AGENTS target is a special file")
        decision = _resolve_decision(classification, str(target), decisions, details)
        resources.append(
            {
                "id": f"{_AGENT_TEMPLATE_ID}@{target}",
                "kind": "agents",
                "target": str(target),
                "source": {"path": str(source), "state": dict(desired)},
                "before": before,
                "desired": dict(desired),
                "classification": classification,
                "decision": decision,
                "details": details,
            }
        )
    return resources


# ---------------------------------------------------------------------------
# Domains
# ---------------------------------------------------------------------------


def _build_domains(
    scope: Mapping[str, Any],
    resources: list[dict[str, Any]],
    onboard_targets: Mapping[str, str],
    package_root: Path,
) -> list[dict[str, Any]]:
    by_target: dict[str, list[str]] = {}
    for resource in resources:
        by_target.setdefault(resource["target"], []).append(resource["id"])

    host_by_root: dict[str, list[str]] = {}
    for host in scope["hosts"]:
        for root in host["skills_roots"]:
            host_by_root.setdefault(_norm(root), []).append(host["id"])

    duplicates = sorted(onboard_targets.values())
    package_key = _norm(package_root)
    domains: list[dict[str, Any]] = []
    for root in scope["skills_roots"]:
        selected_by = ["skills_roots"]
        selected_by.extend(f"host:{host_id}" for host_id in sorted(host_by_root.get(_norm(root), [])))
        onboard_target = onboard_targets.get(_norm(root))
        onboard_copy = None
        if onboard_target is not None:
            onboard_copy = {
                "target": onboard_target,
                "resource_id": by_target[onboard_target][0],
                "is_source": _norm(Path(onboard_target)) == package_key,
                "duplicates": duplicates,
            }
        domains.append(
            {
                "id": f"skills:{root}",
                "kind": "skills",
                "path": str(root),
                "selected_by": selected_by,
                "resources": sorted(
                    resource["id"]
                    for resource in resources
                    if path_contains(Path(resource["target"]), root)
                ),
                "onboard_copy": onboard_copy,
            }
        )
    for target in scope["agents_targets"]:
        domains.append(
            {
                "id": f"agents:{target}",
                "kind": "agents",
                "path": str(target),
                "template": _AGENT_TEMPLATE_ID,
                "resources": sorted(by_target[str(target)]),
            }
        )
    for host in scope["hosts"]:
        domains.append(
            {
                "id": f"host:{host['id']}",
                "kind": "host",
                "host": host["id"],
                "platform": host["platform"],
                "config_home": str(host["config_home"]),
                "config": str(host["config"]),
                "skills_roots": [str(root) for root in host["skills_roots"]],
                "project_roots": [str(root) for root in host["project_roots"]],
                "runtime": host["runtime"],
                "executable": host["executable"],
                "onboard_root": str(host["onboard_root"])
                if host["onboard_root"] is not None else None,
            }
        )
    for profile in scope["shell_profiles"]:
        domains.append(
            {
                "id": f"shell:{profile['path']}",
                "kind": "shell",
                "path": str(profile["path"]),
                "shell": profile["shell"],
                "bin": str(profile["bin"]),
            }
        )
    domains.sort(key=lambda domain: domain["id"])
    return domains


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def build_inventory(scope: object, *, package_root: Path | str | None = None) -> dict[str, Any]:
    """Inventory every selected target against the fixed catalog baseline.

    Read-only: no writes, no cache or directory creation, no host probes and
    no HOME discovery beyond the supplied roots. The same scope, package and
    live disk always produce byte-identical output.
    """
    if package_root is None:
        root = Path(__file__).resolve().parents[1]
        _canonical(root)
    else:
        root = _resolved(package_root, "package_root")
    info = _lstat(root)
    if info is None or not stat.S_ISDIR(info.st_mode):
        _fail("invalid-config", "the package root is not a directory")

    validated = _scope_paths(normalize_scope(scope))
    cache = _PayloadCache()
    baseline, entries, stable, agents_pin = _build_baseline(root, cache)

    skill_resources, onboard_targets = _skill_resources(validated, entries, stable, root, cache)
    agents_resources = _agents_resources(validated, entries, root, agents_pin)
    resources = sorted(
        [*skill_resources, *agents_resources], key=lambda resource: resource["target"]
    )

    selected_targets = {resource["target"] for resource in resources}
    # mcp/shell resources are owned by sbtd_upgrade_hosts; their selected
    # targets legitimately appear in decisions and pass through for it.
    selected_targets.update(str(host["config"]) for host in validated["hosts"])
    selected_targets.update(str(profile["path"]) for profile in validated["shell_profiles"])
    for decision_target in validated["decisions"]:
        if decision_target not in selected_targets:
            _fail("decision-conflict", "a decision targets an unselected resource")

    domains = _build_domains(validated, resources, onboard_targets, root)
    return {"baseline": baseline, "resources": resources, "domains": domains}
