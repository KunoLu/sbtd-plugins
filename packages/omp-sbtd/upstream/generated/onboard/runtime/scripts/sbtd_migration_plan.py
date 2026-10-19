"""Read-only batch migration planning and repeatable legacy input validation.

Grounded in Trellis v0.6.17 (commit 833a5846d18ad7a5ccd8c41c876d89cc936f5fd9)
and the characterized Trellis v0.6.15 project data shape, plus the main PRD
sections 10.2/11 plus the P1-12 migration-runtime decisions:

- ``plan_migration`` is strictly read-only. It never creates the private
  vault, candidates, projects or HOME entries; it verifies the already
  authorized private preparation (exact publication decisions, existing
  share/redact candidates under the verified private vault, current source
  and target states) and seals a bound manifest. Missing, non-private,
  linked or otherwise unproven inputs block the plan with zero writes.
- No candidate is ever generated here and no scan result substitutes human
  approval. A legacy task is either an exact share/redact projection or an
  explicit private-only skip of its whole folder. Spec files are either
  exact share/redact projections or explicit private-only preservation.
  Lessons still require a share/redact projection. A skipped task is not
  published and does not require a handoff. Missing approval still blocks.
- Operations use only the existing contract change kinds. ``apply`` adds
  ignore protection before data writes, extracts the legacy developer name
  into the missing current identity, installs the approved candidates and
  stops managed old routing; it never deploys new wiring or runs smoke.
  ``cleanup`` only retires the legacy project tree and the identity-proven
  global ``trellis-workflow``/``trellis-channel`` Skill directories (any
  1.0.x version, never a fixed checksum pin); drifted or unknown global
  content is preserved untouched. No deployment producer targets are
  declared.
- ``validate_legacy_inputs`` repeats the complete legacy closure against a
  manifest with caller-supplied original bytes, so apply/verify revalidation
  stays sound after controlled rewrites or cleanup of the legacy sources.

Every failure is a sanitized ``ContractError`` naming the fixed rule, never
a rejected private value.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import re
import stat
import subprocess
from collections.abc import Callable, Collection, Mapping, Sequence
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn, cast
from urllib.parse import unquote, urlsplit

import onboard_contracts as contracts
from onboard_contracts import ContractError
from sbtd_identity import DeveloperStore
from sbtd_migration_files import (
    _canonical,
    _lstat,
    directory_snapshot,
    read_file,
    require_private_directory,
    snapshot,
)
from sbtd_migration_legacy import (
    read_legacy_identity,
    validate_projection_graph,
    validate_task_projection,
)
from sbtd_task_state import TERMINAL_STATUSES

__all__ = ["plan_migration", "validate_legacy_inputs"]

_PACKAGE = Path(__file__).resolve().parents[1]
_IGNORE_ASSET = _PACKAGE / "assets" / "migration-local-ignore.txt"
_PAUSE_ASSET = _PACKAGE / "assets" / "migration-paused-agents.txt"
_OWNERSHIP_ASSET = _PACKAGE / "assets" / "migration-legacy-ownership.json"

_ABSENT = {"type": "absent", "checksum": None}
_LEGACY_DIR = ".trellis"
_LEGACY_VERSIONS = frozenset({"0.6.15", "0.6.17"})
_TASK_JSON = "task.json"
_TASK_DOCUMENT = "task.md"
_TASK_SIDECAR = "legacy-task.json"
_DEVELOPER_NAME = ".developer"
_TEMPLATE_HASHES = ".template-hashes.json"
_VERSION_FILE = ".version"

# Known v0.6.15/v0.6.17 layout. Gitignore may hide incidental files outside this
# layout; those stay in the directory snapshot and are deleted with the tree.
# tasks, spec and lessons stay in the approval closure even when ignored.
# A path outside this layout that git does not ignore stops the plan.
_KNOWN_LEGACY_TOP = frozenset(
    {
        _DEVELOPER_NAME,
        _TEMPLATE_HASHES,
        _VERSION_FILE,
        "tasks",
        "spec",
        "lessons",
        "workspace",
        "workflow.md",
        ".gitignore",
        ".current-task",
        ".runtime",
        "config.yaml",
        "scripts",
        "agents",
    }
)
_MANDATORY_TOP = frozenset({"tasks", "spec", "lessons"})
_GENERATED_LEGACY_TOP = frozenset({"workflow.md", "config.yaml", "scripts", "agents"})
# v0.6.15 also recorded digests for these non-generated legacy paths. A
# recorded claim proves bytes only, never generated ownership: lessons keep
# their publication closure, runtime context its private approval, and junk
# stays on the fail-closed unknown-path rules.
_LEGACY_CLAIMED_USER_DATA = frozenset({"lessons", ".runtime", ".DS_Store"})
_UNSELECTED_PLATFORM_PREFIX = frozenset({".cursor", ".opencode", ".pi"})
_PLATFORM_PREFIX = {
    ".codex": "codex",
    ".agents": "codex",
    ".claude": "claude",
    ".kimi": "kimi",
    ".omp": "oh-my-pi",
}
_ROOT_OWNED_FILES = frozenset({"AGENTS.md"})
# Host-level shared configuration keeps its own pin rules; the exact
# official payload fallback below never authorizes these names.
_SHARED_CONFIG_NAMES = frozenset({"config.toml", "hooks.json", "settings.json"})
_TRELLIS_MARKER = "TRELLIS"

_HEX64 = re.compile(r"[0-9a-f]{64}")
_LESSON_MARKER = re.compile(r"<!-- lessons:[^>]*-->")
_LESSON_ID = re.compile(r"LESSON-\d{8}-[a-z0-9]+-[a-z0-9-]+")
# Obvious secret shapes only; approval, not scanning, is the privacy gate.
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
)

# (category root inside the legacy directory) -> shared document root.
_DOC_TARGETS = {"spec": ("docs", "spec"), "lessons": ("docs", "lessons")}
# Historical task documents (files below legacy tasks/ with no ancestor
# task.json) publish verbatim under this root, keeping their exact legacy
# relative path below tasks/ as an opaque directory hierarchy.
_HISTORY_DOC_TARGET = ("docs", "legacy-archive", "tasks")
# Trusted project-root template used to prove an already-aligned root
# AGENTS.md; patchable in tests like the other trusted payload assets.
_PROJECT_AGENTS_TEMPLATE = _PACKAGE / "templates" / "agents" / "AGENTS.project.md"

ReadOriginal = Callable[[Mapping[str, Any]], bytes]

ResolveOriginal = Callable[[Mapping[str, Any]], Mapping[str, Any]]
"""Resolve a sealed reference to its live or retained-backup location."""


def _fail(
    code: str,
    message: str,
    *,
    exit_code: int = 2,
    details: Mapping[str, Any] | None = None,
) -> NoReturn:
    raise ContractError(code, message, exit_code=exit_code, details=details)


# ---------------------------------------------------------------------------
# Paths, references and strict JSON
# ---------------------------------------------------------------------------


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("invalid-config", "a structured input repeats a key")
        result[key] = value
    return result


def _json_object(raw: bytes, label: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (ValueError, RecursionError, UnicodeError):
        _fail("invalid-config", f"{label} is not unambiguous JSON")


def _parts_relative(path: Path, root: Path) -> tuple[str, ...] | None:
    try:
        return path.relative_to(root).parts
    except ValueError:
        return None


def _check_safe_relative(value: str, label: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or "\\" in value:
        _fail("invalid-config", f"{label} is not a safe relative path")
    parts = PurePosixPath(value).parts
    if (
        not parts
        or PurePosixPath(value).is_absolute()
        or any(part in {"", ".", ".."} for part in parts)
    ):
        _fail("invalid-config", f"{label} is not a safe relative path")
    return parts


def _physical_root(value: Any) -> Path:
    if not isinstance(value, (str, os.PathLike)):
        _fail("invalid-argument", "project roots must be filesystem paths")
    root = Path(value)
    try:
        resolved = root.resolve(strict=True)
    except (OSError, RuntimeError):
        _fail("scope-conflict", "a selected project root cannot be resolved")
    if resolved != root or not root.is_dir():
        _fail(
            "scope-conflict",
            "a selected project is not its recorded physical root",
        )
    return root


def _reference(path: Path) -> dict[str, Any]:
    return {"path": str(path), "state": snapshot(path)}


def _present_file_reference(path: Path, label: str) -> dict[str, Any]:
    reference = _reference(path)
    if reference["state"]["type"] != "file":
        _fail("missing-input", f"{label} is unavailable")
    return reference


def _check_reference_current(reference: Mapping[str, Any], code: str) -> None:
    path = reference.get("path")
    state = reference.get("state")
    if not isinstance(path, str) or not isinstance(state, Mapping):
        _fail(code, "a bound reference is malformed")
    if snapshot(Path(path)) != dict(state):
        _fail(code, "a bound input no longer matches its recorded state")


def _lineage_probe(path: Path) -> str:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return "absent"
    except OSError:
        _fail("read-failed", "a target parent path cannot be inspected")
    if stat.S_ISLNK(info.st_mode):
        _fail("unsafe-path", "a target parent path is a link")
    if stat.S_ISDIR(info.st_mode):
        return "directory"
    if stat.S_ISREG(info.st_mode):
        return "file"
    _fail("unsafe-path", "a target parent path is a special entry")


def _omp_root_presence(path: Path) -> str:
    """Classify only the OMP root. Do not walk children or follow links."""
    checked = _canonical(path)
    info = _lstat(checked)
    if info is None:
        return "absent"
    if stat.S_ISDIR(info.st_mode):
        return "directory"
    if stat.S_ISREG(info.st_mode):
        return "file"
    _fail("unsafe-path", "path is a link or special file, not absent")


def _check_target_lineage(target: Path, root: Path) -> None:
    """Missing parents are fine (apply creates them); existing junk is not."""
    parent = target.parent
    while parent != root:
        if parent == parent.parent:
            _fail("scope-conflict", "a managed target escapes its project")
        if _lineage_probe(parent) == "file":
            _fail("target-conflict", "a target parent path is not a directory")
        parent = parent.parent


# ---------------------------------------------------------------------------
# Private vault, pinned ownership metadata and shared-text privacy gate
# ---------------------------------------------------------------------------


def _private_vault(value: Any) -> Path:
    if not isinstance(value, (str, os.PathLike)):
        _fail("invalid-argument", "the backup root must be a filesystem path")
    return require_private_directory(Path(value))


def _ownership_pins() -> dict[str, Any]:
    document = _json_object(read_file(_OWNERSHIP_ASSET), "the legacy ownership pins")
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        _fail("invalid-config", "the legacy ownership pins are malformed")
    agents = document.get("global_agents_sha256")
    if not isinstance(agents, str) or _HEX64.fullmatch(agents) is None:
        _fail("invalid-config", "the legacy ownership pins are malformed")
    skills = document.get("skills")
    if not isinstance(skills, dict):
        _fail("invalid-config", "the legacy ownership pins are malformed")
    pinned: dict[str, dict[str, Any]] = {}
    for name, pin in skills.items():
        if not isinstance(name, str) or not name or "/" in name or name in {".", ".."}:
            _fail("invalid-config", "the legacy ownership pins are malformed")
        if (
            not isinstance(pin, Mapping)
            or pin.get("type") != "directory"
            or not isinstance(pin.get("checksum"), str)
            or _HEX64.fullmatch(pin["checksum"]) is None
        ):
            _fail("invalid-config", "the legacy ownership pins are malformed")
        pinned[name] = {"type": "directory", "checksum": pin["checksum"]}
    configurations = document.get("project_config_templates")
    if not isinstance(configurations, dict) or not configurations:
        _fail("invalid-config", "the legacy configuration pins are malformed")
    for relative, digests in configurations.items():
        _check_safe_relative(relative, "a pinned configuration path")
        if (
            not isinstance(digests, list)
            or not digests
            or any(
                not isinstance(digest, str) or _HEX64.fullmatch(digest) is None
                for digest in digests
            )
        ):
            _fail("invalid-config", "the legacy configuration pins are malformed")
    return {
        "agents": agents,
        "skills": pinned,
        "project_configs": configurations,
        "official_payloads": _official_template_payloads(document),
    }


def _official_template_payloads(
    document: Mapping[str, Any],
) -> dict[str, tuple[str, ...]]:
    """Optional provenance-pinned exact official payload digests by path.

    Absent evidence disables fallback recognition entirely; malformed
    evidence fails closed.  A digest is authorized only for its exact
    recorded path with published provenance.
    """
    if "official_template_payloads" not in document:
        return {}
    field = document["official_template_payloads"]
    if not isinstance(field, Mapping):
        _fail("invalid-config", "the official template payload evidence is malformed")
    if (
        field.get("package") != "@mindfoldhq/trellis"
        or field.get("normalization") != "UTF-8, CRLF to LF only"
    ):
        _fail("invalid-config", "the official template payload evidence is malformed")
    releases = field.get("releases")
    if not isinstance(releases, Mapping) or not releases:
        _fail("invalid-config", "the official template payload evidence is malformed")
    for name, release in releases.items():
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(release, Mapping)
            or not isinstance(release.get("tarball"), str)
            or not release["tarball"]
            or not isinstance(release.get("integrity"), str)
            or not release["integrity"].startswith("sha512-")
        ):
            _fail(
                "invalid-config",
                "the official template payload evidence is malformed",
            )
    files = field.get("files")
    if not isinstance(files, Mapping) or not files:
        _fail("invalid-config", "the official template payload evidence is malformed")
    payloads: dict[str, tuple[str, ...]] = {}
    for relative, records in files.items():
        parts = _check_safe_relative(relative, "an official payload path")
        if not isinstance(records, list) or not records:
            _fail(
                "invalid-config",
                "the official template payload evidence is malformed",
            )
        digests: list[str] = []
        for record in records:
            if (
                not isinstance(record, Mapping)
                or not isinstance(record.get("sha256"), str)
                or _HEX64.fullmatch(record["sha256"]) is None
                or not isinstance(record.get("version"), str)
                or record["version"] not in releases
                or not isinstance(record.get("member"), str)
                or not isinstance(record.get("rendering"), str)
                or not record["rendering"]
            ):
                _fail(
                    "invalid-config",
                    "the official template payload evidence is malformed",
                )
            _check_safe_relative(record["member"], "an official payload member")
            digests.append(record["sha256"])
        payloads[PurePosixPath(*parts).as_posix()] = tuple(digests)
    return payloads


def _private_strings(vault: Path) -> tuple[str, ...]:
    from onboard import user_home

    values = {str(vault), str(user_home())}
    return tuple(sorted(value for value in values if len(value) > 3))


def _check_shared_text(
    data: bytes,
    *,
    private_strings: tuple[str, ...],
    private_digests: set[str],
    check_legacy_layout: bool = True,
    check_digests: bool = True,
) -> None:
    """Refuse obvious private path/hash/secret leaks in shared projections.

    Binary candidates cannot be inspected reliably; they ship only under
    their explicit approval and are never scanned-into-safety here. The
    sidecar records its legacy ``source_path`` and pins ``source_sha256``
    structurally (both validated by the projection contract), so only it
    skips the layout and digest substring scans.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return
    if check_legacy_layout and _LEGACY_DIR in text:
        _fail(
            "privacy-violation",
            "a shared projection still references the retired legacy layout",
        )
    for needle in private_strings:
        if needle in text:
            _fail("privacy-violation", "a shared projection leaks a private path")
    if check_digests:
        for digest in private_digests:
            if digest in text:
                _fail("privacy-violation", "a shared projection leaks a private digest")
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            _fail("privacy-violation", "a shared projection carries an obvious secret")


def _check_markdown_links(
    data: bytes, target: Path, root: Path, approved_targets: set[Path]
) -> None:
    try:
        from markdown_it import MarkdownIt
    except ImportError:
        _fail(
            "dependency-unavailable",
            "Markdown link validation requires the declared Markdown parser",
        )
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return
    parser = MarkdownIt("commonmark")
    safe_link = parser.validateLink
    # Parse unsafe destinations too so the migration gate can reject them;
    # this parser only inspects tokens and never renders or opens a link.
    cast(Any, parser).validateLink = lambda _url: True
    inline_tokens = (
        child for block in parser.parse(text) for child in (block.children or ())
    )
    for token in inline_tokens:
        if token.type not in {"link_open", "image"}:
            continue
        href = token.attrGet("href" if token.type == "link_open" else "src")
        if href is None:
            continue
        if not isinstance(href, str) or not safe_link(href):
            _fail(
                "target-conflict", "a shared Markdown link uses an unsafe destination"
            )
        if re.match(r"^[A-Za-z]:", unquote(href)):
            _fail("target-conflict", "a shared Markdown link cannot name a drive path")
        try:
            parsed = urlsplit(href)
        except ValueError:
            _fail(
                "target-conflict", "a shared Markdown link has an invalid destination"
            )
        if parsed.scheme == "file":
            _fail(
                "target-conflict", "a shared Markdown link cannot name a local file URL"
            )
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        path = unquote(parsed.path)
        if path.startswith("/") or "\\" in path:
            _fail("target-conflict", "a shared Markdown link is not project-relative")
        resolved = Path(os.path.normpath(target.parent / path))
        if not resolved.is_relative_to(root) or resolved not in approved_targets:
            _fail(
                "target-conflict",
                "a shared Markdown link does not resolve to an approved publication",
            )


def _check_lessons_preserved(source_raw: bytes, candidate_raw: bytes) -> None:
    try:
        source_text = source_raw.decode("utf-8")
        candidate_text = candidate_raw.decode("utf-8")
    except UnicodeDecodeError:
        _fail("privacy-unproven", "lessons content cannot be inspected safely")
    needed = set(_LESSON_MARKER.findall(source_text)) | set(
        _LESSON_ID.findall(source_text)
    )
    if any(token not in candidate_text for token in needed):
        _fail(
            "preservation-failure",
            "the approved projection dropped lesson markers or IDs",
        )


# ---------------------------------------------------------------------------
# Candidate byte access (candidates are never rewritten by later phases, so a
# verified state plus a safe read is the original approved bytes)
# ---------------------------------------------------------------------------


def _candidate_files(candidate: Mapping[str, Any]) -> set[str]:
    state, entries = directory_snapshot(Path(candidate["path"]))
    if state != candidate["state"]:
        _fail("state-conflict", "an approved candidate changed after approval")
    return {entry["path"] for entry in entries if entry["type"] == "file"}


def _candidate_bytes(candidate: Mapping[str, Any], member: str | None) -> bytes:
    state = candidate["state"]
    path = Path(candidate["path"])
    if state["type"] == "file":
        if member is not None:
            _fail("candidate-conflict", "a file candidate has no members")
        return read_file(path, state)
    if member is None:
        _fail("candidate-conflict", "a directory candidate needs a member name")
    parts = _check_safe_relative(member, "candidate member")
    if snapshot(path) != state:
        _fail("state-conflict", "an approved candidate changed after approval")
    return read_file(path.joinpath(*parts))


def _approved_target_files(
    closures: Mapping[
        tuple[str, ...], Sequence[tuple[Mapping[str, Any], list[tuple[str, ...]]]]
    ],
    documents: Sequence[tuple[str, Mapping[str, Any], list[tuple[str, ...]]]],
) -> set[Path]:
    targets: set[Path] = set()
    for records in closures.values():
        for item, _rels in records:
            if item["decision"] == "private-only":
                continue
            candidate = item["candidate_ref"]
            target = Path(item["target_path"])
            if candidate["state"]["type"] == "file":
                targets.add(target)
            else:
                targets.update(
                    target / member for member in _candidate_files(candidate)
                )
    for _category, item, _rels in documents:
        if item["decision"] == "private-only":
            continue
        candidate = item["candidate_ref"]
        target = Path(item["target_path"])
        if candidate["state"]["type"] == "file":
            targets.add(target)
        else:
            targets.update(target / member for member in _candidate_files(candidate))
    return targets


# ---------------------------------------------------------------------------
# Publication item classification and closure validation (shared by plan and
# validate; only the source-byte reader differs)
# ---------------------------------------------------------------------------


def _classify_project_items(
    root: Path, items: Sequence[Mapping[str, Any]]
) -> tuple[
    dict[tuple[str, ...], list[tuple[Mapping[str, Any], list[tuple[str, ...]]]]],
    list[tuple[str, Mapping[str, Any], list[tuple[str, ...]]]],
    list[Mapping[str, Any]],
]:
    primaries: dict[
        tuple[str, ...], list[tuple[Mapping[str, Any], list[tuple[str, ...]]]]
    ] = {}
    attachments: list[tuple[Mapping[str, Any], list[tuple[str, ...]]]] = []
    documents: list[tuple[str, Mapping[str, Any], list[tuple[str, ...]]]] = []
    optional: list[Mapping[str, Any]] = []
    handoff_root = root / "docs" / "handoffs"
    for item in items:
        rels: list[tuple[str, ...]] = []
        for reference in item["sources"]:
            rel = _parts_relative(Path(reference["path"]), root)
            if rel is None or len(rel) < 2 or rel[0] != _LEGACY_DIR:
                _fail(
                    "approval-conflict",
                    "a publication source is not legacy project data",
                )
            rels.append(rel)
        target = item["target_path"]
        if target is not None and Path(target).parent == handoff_root:
            if any(rel[1] not in {"workspace", ".runtime"} for rel in rels):
                _fail("approval-conflict", "handoff sources must be legacy context")
            optional.append(item)
            continue
        top = rels[0][1]
        if any(rel[1] != top for rel in rels):
            _fail("approval-conflict", "one publication item mixes legacy categories")
        if top == "tasks":
            task_sources = [rel for rel in rels if rel[-1] == _TASK_JSON]
            if task_sources:
                if len(task_sources) != 1:
                    _fail(
                        "approval-conflict",
                        "an item cannot bind several task sources",
                    )
                folder = task_sources[0][:-1]
                if len(folder) < 3:
                    _fail(
                        "approval-conflict",
                        "a legacy task source must live in its own folder",
                    )
                inside = (
                    len(rel) > len(folder) and rel[: len(folder)] == folder
                    for rel in rels
                )
                if not all(inside):
                    _fail(
                        "approval-conflict",
                        "a task item binds sources outside its task folder",
                    )
                if item["decision"] == "private-only":
                    if item["required"]:
                        _fail(
                            "approval-conflict",
                            "a private task skip must be explicitly optional",
                        )
                    optional.append(item)
                    continue
                candidate = item["candidate_ref"]
                if len(rels) != 1 and (
                    candidate is None or candidate["state"]["type"] != "directory"
                ):
                    _fail(
                        "approval-conflict",
                        "a file task projection binds exactly its task source",
                    )
                primaries.setdefault(folder, []).append(
                    (item, [rel[len(folder) :] for rel in rels])
                )
            else:
                attachments.append((item, rels))
        elif top in _DOC_TARGETS:
            if any(len(rel) < 3 for rel in rels):
                _fail(
                    "approval-conflict",
                    "a legacy document source must be a file below its category",
                )
            if top == "spec" and item["decision"] == "private-only":
                if item["required"]:
                    _fail(
                        "approval-conflict",
                        "private spec preservation must be explicitly optional",
                    )
                optional.append(item)
                continue
            documents.append((top, item, [rel[2:] for rel in rels]))
        else:
            if item["decision"] != "private-only":
                _fail(
                    "approval-conflict",
                    "generated or journal legacy data stays private-only",
                )
            optional.append(item)
    for item, rels in attachments:
        matches = [
            folder
            for folder in primaries
            if all(
                len(rel) > len(folder) and rel[: len(folder)] == folder for rel in rels
            )
        ]
        if item["decision"] == "private-only":
            if item["required"]:
                _fail(
                    "approval-conflict",
                    "a private task attachment must be explicitly optional",
                )
            if len(matches) == 0:
                _fail(
                    "approval-conflict",
                    "a historical task document cannot stay private-only",
                )
            optional.append(item)
            continue
        if len(matches) == 0:
            # No approved task closure claims these files: the item documents
            # one orphan legacy file verbatim as task history, keeping its
            # exact relative path below the shared legacy-archive root.
            candidate = item["candidate_ref"]
            if (
                len(rels) != 1
                or candidate is None
                or candidate["state"]["type"] != "file"
            ):
                _fail(
                    "approval-conflict",
                    "a historical task document binds exactly one legacy file",
                )
            documents.append(("tasks", item, [rels[0][2:]]))
            continue
        folder = max(matches, key=len)
        primaries[folder].append((item, [rel[len(folder) :] for rel in rels]))
    return primaries, documents, optional


def _check_task_target(root: Path, target: Path, projection: Any) -> None:
    tasks = root / "ai" / "tasks"
    if projection.archive_bucket is None:
        expected = tasks / projection.legacy_id
    else:
        expected = tasks / "archive" / projection.archive_bucket / projection.legacy_id
    if target != expected:
        _fail("target-conflict", "a migrated task must use its derived task location")


def _check_task_closure(
    root: Path,
    folder: tuple[str, ...],
    records: Sequence[tuple[Mapping[str, Any], list[tuple[str, ...]]]],
    read_source: ReadOriginal,
    private_strings: tuple[str, ...],
    approved_targets: set[Path],
) -> tuple[Any, str]:
    items = [record[0] for record in records]
    decisions = {item["decision"] for item in items}
    if len(decisions) != 1 or not decisions <= {"share", "redact"}:
        _fail(
            "approval-required",
            "a legacy task needs exactly one share or redact approval",
        )
    decision = next(iter(decisions))
    if any(not item["required"] for item in items):
        _fail("approval-required", "a legacy task projection cannot be optional")
    source_map: dict[str, Mapping[str, Any]] = {}
    for item, rels in records:
        for rel, reference in zip(rels, item["sources"]):
            source_map.setdefault(PurePosixPath(*rel).as_posix(), reference)
    directory_form = (
        len(records) == 1
        and records[0][0]["candidate_ref"]["state"]["type"] == "directory"
    )
    sibling_candidates: dict[str, bytes] = {}
    if directory_form:
        item = records[0][0]
        candidate = item["candidate_ref"]
        target = Path(item["target_path"])
        members = _candidate_files(candidate)
        expected = (set(source_map) - {_TASK_JSON}) | {_TASK_DOCUMENT, _TASK_SIDECAR}
        if members != expected:
            _fail(
                "candidate-conflict",
                "the approved task tree drops obligated projections or adds "
                "unknown members",
            )
        task_raw = _candidate_bytes(candidate, _TASK_DOCUMENT)
        sidecar_raw = _candidate_bytes(candidate, _TASK_SIDECAR)
        for rel in source_map:
            if rel != _TASK_JSON:
                sibling_candidates[rel] = _candidate_bytes(candidate, rel)
        form = "directory"
    else:
        document_records = [
            record
            for record in records
            if Path(record[0]["target_path"]).name == _TASK_DOCUMENT
        ]
        if len(document_records) != 1:
            _fail(
                "candidate-conflict",
                "a legacy task needs exactly one migrated task document",
            )
        document_item = document_records[0][0]
        target = Path(document_item["target_path"]).parent
        sidecar_records = [
            record
            for record in records
            if Path(record[0]["target_path"]).name == _TASK_SIDECAR
        ]
        if (
            len(sidecar_records) != 1
            or Path(sidecar_records[0][0]["target_path"]).parent != target
        ):
            _fail(
                "candidate-conflict",
                "a legacy task needs exactly one migrated sidecar next to its document",
            )
        sidecar_item = sidecar_records[0][0]
        primaries = [
            record
            for record in records
            if any(rel == (_TASK_JSON,) for rel in record[1])
        ]
        if {id(record[0]) for record in primaries} != {
            id(document_item),
            id(sidecar_item),
        }:
            _fail(
                "approval-conflict",
                "a task source is bound by exactly its document and sidecar "
                "projections",
            )
        task_raw = _candidate_bytes(document_item["candidate_ref"], None)
        sidecar_raw = _candidate_bytes(sidecar_item["candidate_ref"], None)
        for record_item, rels in records:
            if record_item in (document_item, sidecar_item):
                continue
            if (
                len(rels) != 1
                or record_item["candidate_ref"]["state"]["type"] != "file"
            ):
                _fail(
                    "approval-conflict",
                    "one approved attachment item per legacy file",
                )
            rel = PurePosixPath(*rels[0]).as_posix()
            if Path(record_item["target_path"]) != target.joinpath(*rels[0]):
                _fail(
                    "target-conflict",
                    "an approved attachment keeps its legacy name inside the "
                    "task directory",
                )
            sibling_candidates[rel] = _candidate_bytes(
                record_item["candidate_ref"], None
            )
        form = "file"
    source_raw = read_source(source_map[_TASK_JSON])
    source_path = PurePosixPath(*folder, _TASK_JSON).as_posix()
    projection = validate_task_projection(
        source_raw,
        task_raw,
        sidecar_raw,
        source_path=source_path,
        decision=decision,
    )
    _check_task_target(root, target, projection)
    sibling_sources = {
        rel: read_source(reference)
        for rel, reference in source_map.items()
        if rel != _TASK_JSON
    }
    digests = {hashlib.sha256(source_raw).hexdigest()}
    digests.update(hashlib.sha256(raw).hexdigest() for raw in sibling_sources.values())
    _check_shared_text(
        task_raw, private_strings=private_strings, private_digests=digests
    )
    _check_markdown_links(task_raw, target / _TASK_DOCUMENT, root, approved_targets)
    for relative, candidate_raw in sibling_candidates.items():
        if decision == "share" and candidate_raw != sibling_sources[relative]:
            _fail(
                "candidate-conflict", "a shared attachment must preserve source bytes"
            )
        _check_shared_text(
            candidate_raw, private_strings=private_strings, private_digests=digests
        )
        _check_markdown_links(candidate_raw, target / relative, root, approved_targets)
    _check_shared_text(
        sidecar_raw,
        private_strings=private_strings,
        private_digests=digests,
        check_legacy_layout=False,
        check_digests=False,
    )
    return projection, form


def _common_directory_prefix(paths: Sequence[tuple[str, ...]]) -> tuple[str, ...]:
    prefix = paths[0][:-1]
    for rel in paths[1:]:
        current = rel[:-1]
        index = 0
        while (
            index < len(prefix)
            and index < len(current)
            and prefix[index] == current[index]
        ):
            index += 1
        prefix = prefix[:index]
    return prefix


def _check_document_item(
    root: Path,
    category: str,
    item: Mapping[str, Any],
    rels: Sequence[tuple[str, ...]],
    read_source: ReadOriginal,
    private_strings: tuple[str, ...],
    approved_targets: set[Path],
) -> None:
    if item["decision"] not in {"share", "redact"} or not item["required"]:
        _fail(
            "approval-required",
            "legacy document projections cannot be omitted or optional",
        )
    candidate = item["candidate_ref"]
    target = Path(item["target_path"])
    root_parts = (
        _HISTORY_DOC_TARGET if category == "tasks" else _DOC_TARGETS[category]
    )
    documents_root = root.joinpath(*root_parts)
    pairs: list[tuple[str, bytes, bytes, Path]] = []
    if candidate["state"]["type"] == "file":
        if len(rels) != 1:
            _fail(
                "approval-conflict",
                "a file candidate projects exactly one legacy document",
            )
        if target != documents_root.joinpath(*rels[0]):
            _fail(
                "target-conflict",
                "a legacy document projection keeps its relative path",
            )
        pairs.append(
            (
                rels[0][-1],
                read_source(item["sources"][0]),
                _candidate_bytes(candidate, None),
                target,
            )
        )
    else:
        common = _common_directory_prefix(rels)
        if target != (documents_root.joinpath(*common) if common else documents_root):
            _fail(
                "target-conflict",
                "an approved document tree keeps its legacy relative position",
            )
        members = _candidate_files(candidate)
        expected = {PurePosixPath(*rel[len(common) :]).as_posix() for rel in rels}
        if members != expected:
            _fail(
                "candidate-conflict",
                "an approved document tree does not match its legacy sources",
            )
        for rel, reference in zip(rels, item["sources"]):
            member = PurePosixPath(*rel[len(common) :]).as_posix()
            pairs.append(
                (
                    member,
                    read_source(reference),
                    _candidate_bytes(candidate, member),
                    target / member,
                )
            )
    digests = {hashlib.sha256(source_raw).hexdigest() for _, source_raw, _, _ in pairs}
    for member, source_raw, candidate_raw, output in pairs:
        if item["decision"] == "share" and candidate_raw != source_raw:
            _fail("candidate-conflict", "a shared document must preserve source bytes")
        _check_shared_text(
            candidate_raw, private_strings=private_strings, private_digests=digests
        )
        _check_markdown_links(candidate_raw, output, root, approved_targets)
        if category == "lessons" and member.endswith(".md"):
            _check_lessons_preserved(source_raw, candidate_raw)


def _validate_project_closures(
    root: Path,
    closures: Mapping[
        tuple[str, ...], Sequence[tuple[Mapping[str, Any], list[tuple[str, ...]]]]
    ],
    documents: Sequence[tuple[str, Mapping[str, Any], list[tuple[str, ...]]]],
    read_source: ReadOriginal,
    private_strings: tuple[str, ...],
) -> tuple[dict[str, Any], dict[tuple[str, ...], str]]:
    """Validate one project's closures; return projections and task forms."""
    approved_targets = _approved_target_files(closures, documents)
    projections: dict[str, Any] = {}
    forms: dict[tuple[str, ...], str] = {}
    for folder, records in closures.items():
        projection, form = _check_task_closure(
            root, folder, records, read_source, private_strings, approved_targets
        )
        if projection.legacy_id in projections:
            _fail("graph-conflict", "legacy task identities must be unique")
        projections[projection.legacy_id] = projection
        forms[folder] = form
    validate_projection_graph(projections)
    for category, item, rels in documents:
        _check_document_item(
            root, category, item, rels, read_source, private_strings, approved_targets
        )
    return projections, forms


# ---------------------------------------------------------------------------
# Repeatable legacy input validation
# ---------------------------------------------------------------------------


def _assign_items(
    roots: Sequence[Path], items: Sequence[Mapping[str, Any]]
) -> dict[Path, list[Mapping[str, Any]]]:
    assigned: dict[Path, list[Mapping[str, Any]]] = {root: [] for root in roots}
    for item in items:
        covering = [
            root
            for root in roots
            if all(
                _parts_relative(Path(reference["path"]), root) is not None
                for reference in item["sources"]
            )
        ]
        if len(covering) != 1:
            _fail(
                "scope-conflict",
                "a publication item's sources do not belong to exactly one selected project",
            )
        root = covering[0]
        target = item["target_path"]
        if target is not None and _parts_relative(Path(target), root) is None:
            _fail("scope-conflict", "a publication target leaves its owning project")
        assigned[root].append(item)
    return assigned


def _validate_successor_project_operations(
    root: Path, project: Mapping[str, Any]
) -> None:
    """A successor project carries exactly its pending legacy retirement."""
    _check_agents_no_touch_untouched(project)
    sources = project["sources"]
    if (
        len(sources) != 1
        or Path(sources[0]["path"]) != root / _LEGACY_DIR
        or sources[0]["state"]["type"] != "directory"
    ):
        _fail("semantic-violation", "a project binds exactly its legacy tree")
    remaining = [
        operation
        for operation in project["private_operations"]
        if operation["phase"] != "deploy"
    ]
    if len(remaining) != 1 or remaining[0]["phase"] != "cleanup":
        _fail(
            "semantic-violation",
            "a successor project carries exactly its legacy retirement",
        )
    _check_cleanup_operation(root, remaining[0], sources[0])


def _verify_successor_predecessor(
    manifest: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """Re-verify a successor manifest against its real predecessor chain.

    The sealed object refs name the exact predecessor files by content hash.
    Both documents are re-loaded and fully re-validated, the embedded apply
    results must equal the real receipt's results, and the predecessor must
    be a deployment-less original batch. Read-only.
    """
    from sbtd_migration import _check_reference, _private_document, _result_index

    successor = manifest["payload"]["successor"]
    manifest_ref = successor["manifest_ref"]
    receipt_ref = successor["apply_receipt_ref"]
    _check_reference(manifest_ref)
    _check_reference(receipt_ref)
    prev_manifest, manifest_raw = _private_document(
        Path(manifest_ref["path"]), "manifest"
    )
    prev_receipt, apply_raw = _private_document(
        Path(receipt_ref["path"]), "apply_receipt"
    )
    if (
        prev_manifest["manifest_id"] != successor["manifest_id"]
        or prev_receipt["apply_id"] != successor["apply_id"]
    ):
        _fail(
            "binding-violation",
            "a successor binding does not match its referenced predecessor",
        )
    contracts.validate_declared_bindings(
        prev_manifest,
        {"apply_receipt": prev_receipt},
        {"manifest": manifest_raw, "apply_receipt": apply_raw},
    )
    contracts._bind_success_gate(prev_receipt, {"applied", "already-complete"})
    prev_payload = prev_manifest["payload"]
    if (
        prev_payload["deployment"] is not None
        or prev_payload.get("successor") is not None
    ):
        _fail(
            "successor-conflict",
            "a successor batch requires a deployment-less original batch",
        )
    recorded = _result_index(prev_receipt)
    embedded = {
        result["resource_id"]: result for result in successor["apply_results"]
    }
    if embedded != recorded:
        _fail(
            "binding-violation",
            "embedded predecessor results differ from the completed receipt",
        )
    return prev_manifest, prev_receipt

def _bind_followup_predecessor(
    prev_manifest: Mapping[str, Any],
    prev_apply: Mapping[str, Any],
    prev_deployment: Mapping[str, Any],
    prev_verification: Mapping[str, Any],
    prev_cleanup: Mapping[str, Any],
    raw_documents: Mapping[str, Any],
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Bind one fully completed Codex predecessor chain. Read-only.

    Document binding, success gates, retained backup availability and — for
    a reconciled predecessor — cited source objects, observer lineage and
    continued absence of its missing historical receipt are rechecked.
    Historical versions need not equal this runtime; template sources and
    superseded live after-states are never re-derived against it.
    Returns the successor ancestors (nearest first), each a bound
    (manifest, apply receipt) pair with its own backups proven retained.
    """
    contracts.validate_declared_bindings(
        prev_manifest,
        {
            "apply_receipt": prev_apply,
            "deployment_evidence": prev_deployment,
            "verification": prev_verification,
            "cleanup_receipt": prev_cleanup,
        },
        raw_documents,
    )
    contracts._bind_success_gate(prev_apply, {"applied", "already-complete"})
    contracts._bind_success_gate(prev_deployment, {"succeeded"})
    contracts._bind_success_gate(prev_verification, {"verified"})
    contracts._bind_success_gate(prev_cleanup, {"cleaned", "already-complete"})
    if prev_cleanup["payload"].get("upgrade_context") is not None:
        # Upgrade provenance is restricted to the cleanup invocation that
        # consumed the bound native upgrade evidence; no followup contract
        # re-proves it, so an upgrade-backed predecessor fails closed.
        _fail(
            "upgrade-lineage-conflict",
            "a followup batch cannot consume an upgrade-backed cleanup",
        )
    from sbtd_migration import (
        _check_source_backups,
        _check_stage_backups,
        _require_reconciliation_provenance,
        _result_index,
    )

    # Recheck provenance without revalidating live after-states that cleanup
    # or a later deployment may have superseded.
    _require_reconciliation_provenance(prev_manifest, prev_deployment)
    prev_payload = prev_manifest["payload"]
    if prev_payload["deployment"] is None:
        _fail(
            "followup-conflict",
            "a followup batch requires a completed batch with its deployment",
        )
    if prev_payload["deployment"]["platform"] != "codex":
        _fail(
            "followup-conflict",
            "a followup batch requires a Codex predecessor deployment",
        )
    if prev_payload.get("followup") is not None:
        _fail(
            "followup-conflict",
            "a followup batch cannot follow another followup batch",
        )
    _check_source_backups(prev_manifest)
    _check_stage_backups(
        {
            "apply": _result_index(prev_apply),
            "deploy": _result_index(prev_deployment),
            "cleanup": _result_index(prev_cleanup),
        }
    )
    ancestors: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    cursor = prev_manifest
    while cursor["payload"].get("successor") is not None:
        ancestor_manifest, ancestor_apply = _verify_successor_predecessor(cursor)
        # Ancestors of a completed batch are deployment-less originals, so
        # their source and apply backups are the only reachable artifacts.
        _check_source_backups(ancestor_manifest)
        _check_stage_backups({"apply": _result_index(ancestor_apply)})
        ancestors.append((ancestor_manifest, ancestor_apply))
        cursor = ancestor_manifest
    return ancestors


def _verify_followup_predecessor(
    manifest: Mapping[str, Any],
) -> tuple[
    Mapping[str, Any],
    Mapping[str, Any],
    Mapping[str, Any],
    Mapping[str, Any],
    Mapping[str, Any],
    list[tuple[Mapping[str, Any], Mapping[str, Any]]],
]:
    """Re-verify a followup manifest against its real predecessor chain.

    The sealed object refs name the exact predecessor files by content hash.
    All five documents are re-loaded and fully re-bound on every consumer.
    Read-only.
    """
    from sbtd_migration import _check_reference, _private_document

    followup = manifest["payload"]["followup"]
    slots = (
        ("manifest", followup["manifest_ref"], "manifest_id"),
        ("apply_receipt", followup["apply_receipt_ref"], "apply_id"),
        (
            "deployment_evidence",
            followup["deployment_evidence_ref"],
            "deployment_id",
        ),
        ("verification", followup["verification_ref"], "verification_id"),
        ("cleanup_receipt", followup["cleanup_receipt_ref"], "cleanup_id"),
    )
    documents: dict[str, Any] = {}
    raw_documents: dict[str, Any] = {}
    for kind, reference, id_key in slots:
        _check_reference(reference)
        document, raw = _private_document(Path(reference["path"]), kind)
        if document[id_key] != followup[id_key]:
            _fail(
                "binding-violation",
                "a followup binding does not match its referenced predecessor",
            )
        documents[kind] = document
        raw_documents[kind] = raw
    ancestors = _bind_followup_predecessor(
        documents["manifest"],
        documents["apply_receipt"],
        documents["deployment_evidence"],
        documents["verification"],
        documents["cleanup_receipt"],
        raw_documents,
    )
    return (
        documents["manifest"],
        documents["apply_receipt"],
        documents["deployment_evidence"],
        documents["verification"],
        documents["cleanup_receipt"],
        ancestors,
    )


def _followup_outcome_chain(
    prev_manifest: Mapping[str, Any],
    prev_apply: Mapping[str, Any],
    prev_deployment: Mapping[str, Any],
    prev_cleanup: Mapping[str, Any],
    ancestors: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
) -> list[tuple[Mapping[str, Any], dict[str, Mapping[str, Any]]]]:
    """Order the bound chain oldest to newest with per-phase result indexes."""
    from sbtd_migration import _result_index

    chain: list[tuple[Mapping[str, Any], dict[str, Mapping[str, Any]]]] = [
        (manifest, {"apply": _result_index(receipt)})
        for manifest, receipt in reversed(ancestors)
    ]
    chain.append(
        (
            prev_manifest,
            {
                "apply": _result_index(prev_apply),
                "deploy": _result_index(prev_deployment),
                "cleanup": _result_index(prev_cleanup),
            },
        )
    )
    return chain


def _check_configure_graft_outcome(
    operation: Mapping[str, Any], target: Path, anchors: Collection[str]
) -> dict[str, Any]:
    """Gate a completed configure-graft outcome by managed-section ownership.

    The host runtime legitimately extends these files outside the
    graft-owned section, so whole-file equality cannot gate them; the
    sealed chain never carries launch bindings, so ownership is proven by
    the managed argv/fence shapes instead of recomputed bytes. A missing
    or unparseable file, or any drift inside the managed section, fails
    closed; drift outside it does not block. Returns the live target state
    so followup before-requirements seal the current bytes. ``anchors``
    are the chain's deploy-phase directory outcomes still present on disk
    (retired cleanup targets never anchor); Codex launchers must live
    inside one.
    """
    selector = operation["selector"]
    roots = operation["dependent_projects"]
    state = snapshot(target)
    if state["type"] != "file":
        _fail(
            "state-conflict",
            "a completed batch outcome no longer matches the current state",
        )
    raw = read_file(target, state)
    if selector == "graft-omp-mcp":
        from sbtd_omp_wiring import verify_owned_omp_mcp_section

        verify_owned_omp_mcp_section(raw, roots)
    elif selector == "graft-mcp":
        from sbtd_codex_wiring import verify_owned_mcp_section

        verify_owned_mcp_section(raw, roots, anchors)
    elif selector == "graft-hooks":
        from sbtd_codex_wiring import verify_owned_hooks_section

        verify_owned_hooks_section(raw, roots, anchors)
    elif selector == "graft-agents":
        from sbtd_codex_wiring import verify_owned_agents_fence

        verify_owned_agents_fence(raw)
    else:
        _fail("state-conflict", "unknown Graft configuration selector")
    return state


def _check_followup_predecessor_outcomes(
    chain: Sequence[tuple[Mapping[str, Any], Mapping[str, Mapping[str, Any]]]],
    *,
    overwritten: Collection[str],
) -> dict[str, Any]:
    """Require current predecessor outcomes; exempt followup-overwritten targets.

    Every declared predecessor resource must be proven succeeded by its
    phase receipt. An ancestor operation whose phase receipt is unreachable
    is lawful only when a newer batch carries the same resource and phase;
    the carried copy then holds the proof. The latest proven after-state
    per target is the live expectation unless the followup batch
    legitimately rewrites that target, in which case the followup's own
    concrete before-requirement and receipts carry the proof. Directory
    and other whole-resource targets pin the recorded historical
    after-state; configure-graft targets prove their managed section and
    map the current live snapshot.
    """
    declared: list[tuple[int, Mapping[str, Any], bool]] = []
    latest: dict[
        str, tuple[tuple[int, int], Mapping[str, Any], Mapping[str, Any]]
    ] = {}
    for batch_index, (manifest, stage_results) in enumerate(chain):
        operations = [
            operation
            for project in manifest["payload"]["projects"]
            for operation in project["private_operations"]
        ] + list(manifest["payload"]["shared_operations"])
        for operation in operations:
            proven = False
            results = stage_results.get(operation["phase"])
            if results is not None:
                result = results.get(operation["resource_id"])
                if (
                    result is None
                    or result["status"] != "succeeded"
                    or result["after"] is None
                ):
                    _fail(
                        "followup-conflict",
                        "the completed batch receipts do not prove every declared "
                        "resource",
                    )
                proven = True
                key = (batch_index, contracts._PHASE_ORDER[operation["phase"]])
                current = latest.get(operation["target"])
                if current is None or key > current[0]:
                    latest[operation["target"]] = (key, result, operation)
            declared.append((batch_index, operation, proven))
    for batch_index, operation, proven in declared:
        if proven:
            continue
        carried = any(
            later_index > batch_index
            and later["resource_id"] == operation["resource_id"]
            and later["phase"] == operation["phase"]
            for later_index, later, _proven in declared
        )
        if not carried:
            _fail(
                "followup-conflict",
                "the completed batch history cannot prove every declared resource",
            )
    outcomes = {target: item[1]["after"] for target, item in latest.items()}
    # Anchors prove path containment only, so every live directory
    # deployment outcome qualifies — including trees the followup
    # overwrites, whose content stays pinned by the sealed
    # before-requirement and is re-measured before any write at execute.
    # Retired trees (cleanup removals, after absent) never anchor: their
    # paths no longer prove anything about the bytes that were deployed.
    anchors = [
        target
        for target, (_key, result, operation) in latest.items()
        if operation["phase"] == "deploy"
        and operation["change"]["kind"] != "remove"
        and operation["owner_kind"] == "directory"
        and result["after"]["type"] == "directory"
    ]
    configure: list[tuple[str, Mapping[str, Any]]] = []
    for target, (_key, result, operation) in latest.items():
        if operation["change"]["kind"] == "configure-graft":
            configure.append((target, operation))
            continue
        if target in overwritten:
            continue
        if snapshot(Path(target)) != result["after"]:
            _fail(
                "state-conflict",
                "a completed batch outcome no longer matches the current state",
            )
    for target, operation in configure:
        # Managed-section outcomes are proven even when the followup batch
        # rewrites the target, and the mapping carries the live state so the
        # followup's sealed before-requirement matches the current bytes.
        outcomes[target] = _check_configure_graft_outcome(
            operation, Path(target), anchors
        )
    return outcomes



def validate_legacy_inputs(
    manifest: Mapping[str, Any],
    read_original: ReadOriginal,
    resolve_original: ResolveOriginal | None = None,
    stage_results: Mapping[str, Mapping[str, Any]] | None = None,
    cleanup_only: bool = False,
) -> list[dict[str, Any]] | None:
    """Re-validate the complete legacy closure of a sealed manifest.

    The caller has already proven the bound references current or resolved
    their originals after controlled rewrites; ``read_original`` supplies
    those known original bytes. Candidates are re-read against their
    recorded state. Beyond the publication closures, every declared
    operation must match the closed set derivable from the bound legacy
    sources, the ownership metadata and the approved candidates: a re-sealed
    manifest with altered, invented or missing operations is rejected even
    when it is schema-valid. Nothing here writes or substitutes approval.
    ``stage_results`` carries the bound stage receipts' results (phase to
    resource outcome) so deployment revalidation can recognize a sealed
    configuration input change that a succeeded, intact-backed stage result
    already proves; without it the sealed inputs must match live discovery
    exactly.
    ``cleanup_only`` is set only by the migration cleanup phase, which never
    redeploys. Every check above is unchanged; only the deployment
    declaration's sealed OMP input byte equality may then recognize drift
    that is receipt-proven or deterministically irrelevant to the cleanup
    dependency scope, and the ignored deployment-only input entries are
    returned (sorted by path, each with its sealed and live state) so the
    cleanup receipt can report truthfully what this phase did not
    re-validate. Every other caller receives the historical None return.
    """
    payload = manifest["payload"]
    if payload.get("followup") is not None:
        from sbtd_migration import _result_index

        (
            prev_manifest,
            prev_apply,
            prev_deployment,
            _prev_verification,
            prev_cleanup,
            ancestors,
        ) = _verify_followup_predecessor(manifest)
        prev_payload = prev_manifest["payload"]
        deployment = payload["deployment"]
        if deployment["mode"] != "init" or deployment["platform"] != "omp":
            _fail(
                "semantic-violation",
                "a followup batch requires the full init OMP deployment",
            )
        followup_operations = [
            operation
            for project in payload["projects"]
            for operation in project["private_operations"]
        ] + list(payload["shared_operations"])
        if any(
            operation["selector"] == "graft-hooks" for operation in followup_operations
        ):
            _fail(
                "semantic-violation",
                "a followup batch does not authorize hooks",
            )
        if any(
            operation["before_requirement"]["kind"] != "state"
            for operation in followup_operations
        ):
            _fail(
                "semantic-violation",
                "a followup batch seals only concrete before-states",
            )
        followup_roots = sorted(project["root"] for project in payload["projects"])
        prev_by_root = {
            project["root"]: project for project in prev_payload["projects"]
        }
        if followup_roots != sorted(prev_by_root):
            _fail(
                "semantic-violation",
                "a followup batch alters the completed batch roots",
            )
        for field in ("backup_root", "custodian", "retention"):
            if payload[field] != prev_payload[field]:
                _fail(
                    "semantic-violation",
                    "a followup batch alters the inherited batch identity",
                )
        if payload["publication_decisions"] != {"schema_version": 1, "items": []}:
            _fail(
                "semantic-violation",
                "a followup batch alters the fixed publication record",
            )
        if payload["routing_approvals"] is not None:
            _fail(
                "semantic-violation",
                "a followup batch cannot bind routing approvals",
            )
        for project in payload["projects"]:
            _check_agents_no_touch_untouched(project)
            if (
                project["sources"]
                or project["platforms"] != prev_by_root[project["root"]]["platforms"]
                or project.get("agents_no_touch")
                != prev_by_root[project["root"]].get("agents_no_touch")
            ):
                _fail(
                    "semantic-violation",
                    "a followup batch alters an inherited project binding",
                )
            if any(
                operation["phase"] != "deploy"
                for operation in project["private_operations"]
            ):
                _fail(
                    "semantic-violation",
                    "a followup batch carries only deployment operations",
                )
        if any(
            operation["phase"] != "deploy" for operation in payload["shared_operations"]
        ):
            _fail(
                "semantic-violation",
                "a followup batch carries only deployment operations",
            )
        overwritten = {operation["target"] for operation in followup_operations}
        predecessor_states = _check_followup_predecessor_outcomes(
            _followup_outcome_chain(
                prev_manifest, prev_apply, prev_deployment, prev_cleanup, ancestors
            ),
            overwritten=overwritten,
        )
        for operation in followup_operations:
            target = operation["target"]
            if (
                target in predecessor_states
                and operation["before_requirement"]["state"] != predecessor_states[target]
            ):
                _fail(
                    "ownership-conflict",
                    "a followup before-state differs from its proven predecessor outcome",
                )
        _validate_shared_operations(payload, followup_roots, resolve_original)
        from sbtd_graft_deployment import validate_deployment_declarations

        ignored = validate_deployment_declarations(
            payload,
            followup_deployed={
                result["resource_id"]: result["after"]
                for result in _result_index(prev_deployment).values()
                if result["status"] == "succeeded" and result["after"] is not None
            },
            cleanup_only=cleanup_only,
        )
        _bind_approved_routing(
            payload, [Path(root) for root in followup_roots], bind_live=False
        )
        return ignored
    if payload.get("successor") is not None:
        prev_manifest, _prev_receipt = _verify_successor_predecessor(manifest)
        prev_payload = prev_manifest["payload"]
        successor_roots = sorted(project["root"] for project in payload["projects"])
        prev_by_root = {
            project["root"]: project for project in prev_payload["projects"]
        }
        if successor_roots != sorted(prev_by_root):
            _fail(
                "semantic-violation",
                "a successor batch alters the completed batch roots",
            )
        for field in ("backup_root", "custodian", "retention"):
            if payload[field] != prev_payload[field]:
                _fail(
                    "semantic-violation",
                    "a successor batch alters the inherited batch identity",
                )
        if payload["publication_decisions"] != {"schema_version": 1, "items": []}:
            _fail(
                "semantic-violation",
                "a successor batch alters the fixed publication record",
            )
        if payload["routing_approvals"] is not None:
            _fail(
                "semantic-violation",
                "a successor batch cannot bind routing approvals",
            )
        declared_rids = {
            operation["resource_id"]
            for project in payload["projects"]
            for operation in project["private_operations"]
        } | {
            operation["resource_id"] for operation in payload["shared_operations"]
        }
        prev_operations: dict[str, Mapping[str, Any]] = {}
        for project in payload["projects"]:
            root = Path(project["root"])
            _validate_successor_project_operations(root, project)
            prev_project = prev_by_root[project["root"]]
            if (
                project["sources"] != prev_project["sources"]
                or project["platforms"] != prev_project["platforms"]
                or project.get("agents_no_touch")
                != prev_project.get("agents_no_touch")
            ):
                _fail(
                    "semantic-violation",
                    "a successor batch alters an inherited project binding",
                )
            carried = [
                operation
                for operation in project["private_operations"]
                if operation["phase"] == "cleanup"
            ]
            expected = [
                operation
                for operation in prev_by_root[project["root"]]["private_operations"]
                if operation["phase"] == "cleanup"
            ]
            if carried != expected:
                _fail(
                    "semantic-violation",
                    "a successor batch alters the carried cleanup set",
                )
            original = project["sources"][0]
            inventory_root = Path(original["path"])
            if snapshot(inventory_root) != original["state"]:
                from sbtd_migration import _source_backup_paths

                require_private_directory(Path(payload["backup_root"]))
                inventory_root = _source_backup_paths(manifest)[original["path"]]
            if directory_snapshot(inventory_root)[0] != original["state"]:
                _fail(
                    "state-conflict", "the complete original inventory is unavailable"
                )
            for operation in prev_by_root[project["root"]]["private_operations"]:
                prev_operations[operation["resource_id"]] = operation
        carried_shared = sorted(
            (
                operation
                for operation in payload["shared_operations"]
                if operation["phase"] == "cleanup"
            ),
            key=lambda operation: operation["operation_id"],
        )
        expected_shared = sorted(
            (
                operation
                for operation in prev_payload["shared_operations"]
                if operation["phase"] == "cleanup"
            ),
            key=lambda operation: operation["operation_id"],
        )
        if carried_shared != expected_shared:
            _fail(
                "semantic-violation",
                "a successor batch alters the carried cleanup set",
            )
        for operation in prev_payload["shared_operations"]:
            prev_operations[operation["resource_id"]] = operation
        for result in payload["successor"]["apply_results"]:
            resource = result["resource_id"]
            if resource in declared_rids:
                continue
            operation = prev_operations.get(resource)
            if operation is None:
                _fail(
                    "semantic-violation",
                    "an embedded result owns an unknown predecessor resource",
                )
            if snapshot(Path(operation["target"])) != result["after"]:
                _fail(
                    "state-conflict",
                    "a completed batch outcome no longer matches the current state",
                )
        _validate_shared_operations(payload, successor_roots, resolve_original)
        from sbtd_graft_deployment import validate_deployment_declarations

        ignored = validate_deployment_declarations(payload, cleanup_only=cleanup_only)
        _bind_approved_routing(
            payload, [Path(root) for root in successor_roots], bind_live=False
        )
        return ignored
    items = payload["publication_decisions"]["items"]
    roots = [Path(project["root"]) for project in payload["projects"]]
    assigned = _assign_items(roots, items)
    private_strings = _private_strings(Path(payload["backup_root"]))
    for project in payload["projects"]:
        root = Path(project["root"])
        closures, documents, optional = _classify_project_items(root, assigned[root])
        projections, forms = _validate_project_closures(
            root, closures, documents, read_original, private_strings
        )
        original = project["sources"][0]
        inventory_root = Path(original["path"])
        if snapshot(inventory_root) != original["state"]:
            from sbtd_migration import _source_backup_paths

            require_private_directory(Path(payload["backup_root"]))
            inventory_root = _source_backup_paths(manifest)[original["path"]]
        state, entries = directory_snapshot(inventory_root)
        if state != original["state"]:
            _fail("state-conflict", "the complete original inventory is unavailable")
        # The sealed inventory proves the data version and the metadata bytes
        # for every later closure step, live or from the retained backup.
        version = _inventory_version(entries, inventory_root)
        metadata = next(
            (entry for entry in entries if entry["path"] == _TEMPLATE_HASHES), None
        )
        if metadata is None or metadata["type"] != "file":
            _fail("invalid-config", "the original ownership metadata is unavailable")
        hashes = _parse_template_hashes(
            _json_object(
                read_file(
                    inventory_root / _TEMPLATE_HASHES,
                    {"type": "file", "checksum": metadata["checksum"]},
                ),
                "the original ownership metadata",
            ),
            version,
        )
        metadata_reference = {
            "path": str(root / _LEGACY_DIR / _TEMPLATE_HASHES),
            "state": {"type": "file", "checksum": metadata["checksum"]},
        }
        _check_generated_legacy_bytes(root, inventory_root, entries, hashes)
        _validate_project_operations(
            root,
            project,
            assigned[root],
            read_original,
            metadata_reference,
            version,
        )
        _inventory_coverage(
            entries,
            closures,
            forms,
            documents,
            optional,
            root,
            hashes,
            inventory_root=inventory_root,
        )
        _check_context_handoffs(
            root,
            entries,
            closures,
            projections,
            assigned[root],
            read_original,
            project["source_ref"],
            project["head"],
        )
    _validate_shared_operations(
        payload, sorted(str(root) for root in roots), resolve_original
    )
    from sbtd_graft_deployment import validate_deployment_declarations

    ignored = validate_deployment_declarations(
        payload, stage_results=stage_results, cleanup_only=cleanup_only
    )
    _bind_approved_routing(payload, roots, bind_live=False)
    return ignored


# ---------------------------------------------------------------------------
# Operation-set legitimacy gate (shared by apply and verify consumers)
# ---------------------------------------------------------------------------


def _check_operation_common(operation: Mapping[str, Any], root: Path) -> None:
    if operation["dependent_projects"] != [str(root)]:
        _fail("semantic-violation", "a private operation binds foreign dependents")
    if _parts_relative(Path(operation["target"]), root) is None:
        _fail("semantic-violation", "a private operation leaves its project")
    requirement = operation["before_requirement"]
    if requirement["kind"] != "state":
        _fail("semantic-violation", "operations start from a concrete state")


def _check_identity_operation(
    root: Path, operation: Mapping[str, Any], read_original: ReadOriginal
) -> None:
    if (
        operation["phase"] != "apply"
        or operation["owner_kind"] != "file"
        or operation["selector"] != "name"
    ):
        _fail("semantic-violation", "developer extraction shape was altered")
    _check_operation_common(operation, root)
    if Path(operation["target"]) != root / ".sbtd" / "developer":
        _fail("semantic-violation", "developer extraction target was altered")
    if operation["before_requirement"] != _state_requirement(_ABSENT):
        _fail("semantic-violation", "developer extraction requires a missing target")
    change = operation["change"]
    source = change["source_ref"]
    if (
        Path(source["path"]) != root / _LEGACY_DIR / _DEVELOPER_NAME
        or source["state"]["type"] != "file"
    ):
        _fail("semantic-violation", "developer extraction source was altered")
    ownership = operation["ownership"]
    if (
        ownership["kind"] != "config-entry"
        or ownership["key_path"] != ["name"]
        or ownership["reference"] != source
    ):
        _fail("semantic-violation", "developer extraction ownership was altered")
    if read_legacy_identity(read_original(source)) != change["name"]:
        _fail(
            "identity-conflict",
            "the legacy identity no longer matches the approved operation",
        )


def _check_ignore_operation(
    root: Path, operation: Mapping[str, Any], read_original: ReadOriginal
) -> None:
    if (
        operation["phase"] != "apply"
        or operation["owner_kind"] != "gitignore"
        or operation["selector"] != "local-ignore"
    ):
        _fail("semantic-violation", "the ignore protection shape was altered")
    _check_operation_common(operation, root)
    if Path(operation["target"]) != root / ".gitignore":
        _fail("semantic-violation", "the ignore protection target was altered")
    asset = {"path": str(_IGNORE_ASSET), "state": snapshot(_IGNORE_ASSET)}
    if operation["change"] != {"kind": "ensure-file-block", "source_ref": asset}:
        _fail("semantic-violation", "the ignore protection content was altered")
    if operation["ownership"] != {"kind": "template-source", "reference": asset}:
        _fail("semantic-violation", "the ignore protection ownership was altered")
    from onboard import missing_file_lines

    before = operation["before_requirement"]
    if before["kind"] != "state" or before["state"]["type"] not in {"file", "absent"}:
        _fail(
            "semantic-violation", "ignore protection needs a fixed original file state"
        )
    original = (
        b""
        if before["state"]["type"] == "absent"
        else read_original({"path": operation["target"], "state": before["state"]})
    )
    try:
        needed = missing_file_lines(
            read_file(_IGNORE_ASSET, asset["state"]).decode("utf-8"),
            original.decode("utf-8"),
        )
    except UnicodeDecodeError:
        _fail("invalid-config", "managed ignore content is not UTF-8 text")
    if not needed:
        _fail(
            "semantic-violation", "ignore protection was already complete before apply"
        )


def _check_cleanup_operation(
    root: Path, operation: Mapping[str, Any], legacy_reference: Mapping[str, Any]
) -> None:
    if (
        operation["phase"] != "cleanup"
        or operation["owner_kind"] != "directory"
        or operation["selector"] != "whole-resource"
        or operation["change"] != {"kind": "remove"}
    ):
        _fail("semantic-violation", "the legacy retirement shape was altered")
    _check_operation_common(operation, root)
    if Path(operation["target"]) != root / _LEGACY_DIR:
        _fail("semantic-violation", "the legacy retirement target was altered")
    if operation["ownership"] != {
        "kind": "template-source",
        "reference": dict(legacy_reference),
    }:
        _fail("semantic-violation", "the legacy retirement ownership was altered")
    if operation["before_requirement"] != _state_requirement(legacy_reference["state"]):
        _fail("semantic-violation", "the legacy retirement before-state was altered")


def _check_platform_closure(
    root: Path,
    operations: list[Mapping[str, Any]],
    platforms: Sequence[str],
    read_original: ReadOriginal,
    metadata_reference: Mapping[str, Any],
    version: str,
    agents_no_touch: Any,
) -> None:
    """The remaining operations must be exactly the recorded platform files."""
    if not platforms:
        _require_no_host_roots(root)
    hashes_reference: Mapping[str, Any] | None = None
    file_targets: set[str] = set()
    marker_targets: set[str] = set()
    replacement_targets: set[str] = set()
    content_operations: list[Mapping[str, Any]] = []
    for operation in operations:
        if operation["selector"] == _ROUTING_SELECTOR:
            if operation["change"].get("kind") != "copy-file":
                _fail(
                    "semantic-violation",
                    "an approved routing replacement must copy its candidate",
                )
            replacement_targets.add(operation["target"])
            continue
        if operation["phase"] != "apply" or operation["change"] != {"kind": "remove"}:
            _fail("semantic-violation", "an unknown private operation was added")
        _check_operation_common(operation, root)
        if operation["before_requirement"]["state"]["type"] != "file":
            _fail("semantic-violation", "a platform operation before-state drifted")
        ownership = operation["ownership"]
        if ownership["kind"] == "template-source":
            if (
                operation["owner_kind"] != "file"
                or operation["selector"] != "whole-resource"
            ):
                _fail("semantic-violation", "a platform removal shape was altered")
            if hashes_reference is None:
                hashes_reference = ownership["reference"]
            elif ownership["reference"] != hashes_reference:
                _fail(
                    "semantic-violation",
                    "platform removals must bind the same ownership metadata",
                )
            file_targets.add(operation["target"])
        elif ownership["kind"] == "managed-marker":
            if (
                operation["owner_kind"] != "markdown"
                or operation["selector"] != "trellis-block"
                or ownership["marker"] != _TRELLIS_MARKER
            ):
                _fail("semantic-violation", "a marker removal shape was altered")
            if ownership["reference"] != {
                "path": operation["target"],
                "state": operation["before_requirement"]["state"],
            }:
                _fail("semantic-violation", "a marker removal ownership was altered")
            marker_targets.add(operation["target"])
        else:
            _fail("semantic-violation", "an unknown private ownership was added")
        content_operations.append(operation)
    if hashes_reference is None:
        # Marker-only or empty platform closures carry no template-source
        # operation; the sealed inventory still proves the metadata.
        hashes_reference = metadata_reference
    if Path(hashes_reference["path"]) != root / _LEGACY_DIR / _TEMPLATE_HASHES:
        _fail("semantic-violation", "the platform ownership reference was altered")
    hashes = _parse_template_hashes(
        _json_object(read_original(hashes_reference), "the legacy ownership metadata"),
        version,
    )
    agents_target = str(root / "AGENTS.md")
    if agents_target in replacement_targets:
        # An approved routing replacement owns the root document; a sealed
        # no-touch proof cannot coexist with it.
        derived_no_touch = None
    else:
        agents_before = next(
            (
                operation["before_requirement"]["state"]
                for operation in content_operations
                if operation["target"] == agents_target
            ),
            None,
        )
        derived_no_touch = _agents_no_touch(
            root, hashes, read_original, target_state=agents_before
        )
    if agents_no_touch != derived_no_touch:
        _fail(
            "semantic-violation",
            "the sealed AGENTS no-touch proof was altered",
        )
    expected_files: set[str] = set()
    expected_markers: set[str] = set()
    derived_platforms: set[str] = set()
    for relative in hashes:
        parts = PurePosixPath(relative).parts
        target = str(root.joinpath(*parts))
        if parts[0] == _LEGACY_DIR:
            continue
        if parts[0] in _UNSELECTED_PLATFORM_PREFIX:
            _fail(
                "scope-conflict",
                "unselected legacy host routing requires reconciliation",
            )
        if len(parts) > 1 and parts[0] in _PLATFORM_PREFIX:
            derived_platforms.add(_PLATFORM_PREFIX[parts[0]])
            expected_files.add(target)
        elif len(parts) == 1 and parts[0] in _ROOT_OWNED_FILES:
            expected_markers.add(target)
        else:
            _fail("unknown-content", "a recorded generated path cannot be classified")
    if marker_targets & replacement_targets:
        _fail(
            "approval-conflict",
            "an approved routing replacement cannot also delete the marker block",
        )
    covered_markers = marker_targets | (replacement_targets & expected_markers)
    if derived_no_touch is not None:
        covered_markers = covered_markers | (
            {derived_no_touch["target"]["path"]} & expected_markers
        )
    if file_targets != expected_files or covered_markers != expected_markers:
        _fail(
            "semantic-violation",
            "platform operations do not match the recorded ownership metadata",
        )
    if sorted(derived_platforms) != list(platforms):
        _fail("semantic-violation", "the declared platforms were altered")
    # Re-prove every content-bearing operation's before bytes from the live
    # path or the retained original: a coherently re-sealed manifest must not
    # let foreign bytes inherit recorded or official ownership.
    official = _ownership_pins()["official_payloads"]
    for operation in content_operations:
        parts = _parts_relative(Path(operation["target"]), root)
        if parts is None:
            continue
        relative = PurePosixPath(*parts).as_posix()
        recorded = hashes.get(relative)
        if recorded is None:
            continue
        raw = read_original(
            {
                "path": operation["target"],
                "state": operation["before_requirement"]["state"],
            }
        )
        digest = _normalized_text_digest(raw)
        if digest == recorded:
            continue
        if digest in _official_alternative_digests(official, relative, parts):
            continue
        _fail(
            "ownership-conflict",
            "generated content drifted; removal is not authorized",
        )


def _validate_project_operations(
    root: Path,
    project: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
    read_original: ReadOriginal,
    metadata_reference: Mapping[str, Any],
    version: str,
) -> None:
    _check_agents_no_touch_untouched(project)
    sources = project["sources"]
    if (
        len(sources) != 1
        or Path(sources[0]["path"]) != root / _LEGACY_DIR
        or sources[0]["state"]["type"] != "directory"
    ):
        _fail("semantic-violation", "a project binds exactly its legacy tree")
    deployment = [
        operation
        for operation in project["private_operations"]
        if operation["phase"] == "deploy"
    ]
    remaining = [
        operation
        for operation in project["private_operations"]
        if operation["phase"] != "deploy"
    ]
    expected_publications = [
        _publication_operation(root, item)
        for item in sorted(
            (item for item in items if item["decision"] != "private-only"),
            key=lambda item: item["target_path"],
        )
    ]
    for expected in expected_publications:
        if expected not in remaining:
            _fail(
                "semantic-violation",
                "a required publication operation is missing or altered",
            )
        remaining.remove(expected)
    identities = [
        operation
        for operation in remaining
        if operation["change"].get("kind") == "migrate-developer"
    ]
    if len(identities) > 1:
        _fail("semantic-violation", "developer extraction was duplicated")
    if identities:
        remaining.remove(identities[0])
        _check_identity_operation(root, identities[0], read_original)
    needs_protection = bool(expected_publications or identities or deployment)
    protection = [
        operation for operation in remaining if operation["owner_kind"] == "gitignore"
    ]
    if protection:
        if not needs_protection or len(protection) != 1:
            _fail("semantic-violation", "the ignore protection scope was altered")
        # Later phases see the applied file. Validate the frozen operation,
        # not whether its pre-apply change is still needed in today's file.
        _check_ignore_operation(root, protection[0], read_original)
        remaining.remove(protection[0])
    elif needs_protection and _ignore_operation(root) is not None:
        _fail("semantic-violation", "the required ignore protection is missing")
    cleanups = [operation for operation in remaining if operation["phase"] == "cleanup"]
    if len(cleanups) != 1:
        _fail(
            "semantic-violation",
            "the legacy tree retirement is missing or duplicated",
        )
    remaining.remove(cleanups[0])
    _check_cleanup_operation(root, cleanups[0], sources[0])
    _check_platform_closure(
        root,
        remaining,
        project["platforms"],
        read_original,
        metadata_reference,
        version,
        project.get("agents_no_touch"),
    )


_ROUTING_ROLES = frozenset({"codex-global", "omp-global", "demo-project"})
_ROUTING_SELECTOR = "approved-routing-replacement"
_ROUTING_APPROVAL_PUBLIC_KEY = _PACKAGE / "assets" / "routing-approval.pub"


def _routing_crypto():
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
        from cryptography.hazmat.primitives.serialization import (
            load_pem_private_key,
            load_pem_public_key,
        )
    except ImportError:
        _fail(
            "validator-unavailable",
            "prepare the installed Skill's declared requirements before migration",
        )
    return (
        InvalidSignature,
        Ed25519PrivateKey,
        Ed25519PublicKey,
        load_pem_private_key,
        load_pem_public_key,
    )


def _routing_approval_public_key():
    """The installed approval key. Callers cannot replace it with a path."""
    invalid, _private, public_type, _load_private, load_public = _routing_crypto()
    try:
        key = load_public(_ROUTING_APPROVAL_PUBLIC_KEY.read_bytes())
    except (OSError, ValueError, TypeError, invalid):
        _fail("runtime-unavailable", "the installed routing approval key is unusable")
    if not isinstance(key, public_type):
        _fail("runtime-unavailable", "the installed routing approval key is not Ed25519")
    return key


def _approval_signed_bytes(document: Mapping[str, Any]) -> bytes:
    return contracts.canonical_json_bytes(
        {"schema_version": document["schema_version"], "items": document["items"]}
    )


def _verify_routing_approval_signature(document: Mapping[str, Any]) -> None:
    invalid, _private, _public, _load_private, _load_public = _routing_crypto()
    signature = document.get("signature")
    if not isinstance(signature, str) or not signature:
        _fail("invalid-config", "the routing approval record has no signature")
    try:
        raw = base64.b64decode(signature, validate=True)
        _routing_approval_public_key().verify(raw, _approval_signed_bytes(document))
    except (invalid, ValueError, TypeError):
        _fail(
            "approval-conflict",
            "the routing approval signature does not match the installed key",
        )


def _sign_routing_approval(
    approval_path: Path, key_path: Path, vault: Path, roots: Sequence[Path]
) -> None:
    """Sign one existing approval file. No other path is written."""
    invalid, private_type, _public, load_private, _load_public = _routing_crypto()
    if (
        ".." in key_path.parts
        or not key_path.is_absolute()
        or key_path.is_symlink()
        or not key_path.is_file()
        or key_path.is_relative_to(vault)
        or any(
            key_path.is_relative_to(root) or root.is_relative_to(key_path) for root in roots
        )
    ):
        _fail(
            "private-scope",
            "the routing approval key must stay outside the vault and selected projects",
        )
    if not approval_path.is_relative_to(vault):
        _fail("private-scope", "routing approvals must live inside the private vault")
    require_private_directory(approval_path.parent)
    document = _json_object(read_file(approval_path), "the routing approval record")
    if not isinstance(document, dict) or "items" not in document:
        _fail("invalid-config", "the routing approval record is malformed")
    try:
        private = load_private(key_path.read_bytes(), password=None)
    except (OSError, ValueError, TypeError):
        _fail("invalid-argument", "the routing approval key is unusable")
    if not isinstance(private, private_type):
        _fail("invalid-argument", "the routing approval key is not Ed25519")
    document["signature"] = base64.b64encode(
        private.sign(_approval_signed_bytes(document))
    ).decode("ascii")
    try:
        _routing_approval_public_key().verify(
            base64.b64decode(document["signature"]), _approval_signed_bytes(document)
        )
    except (invalid, ValueError, TypeError):
        _fail(
            "approval-conflict",
            "the routing approval key does not match the installed public key",
        )
    approval_path.write_bytes(contracts.canonical_json_bytes(document))



def _load_routing_approvals(path: Any, vault: Path) -> list[dict[str, Any]]:
    """Load the private routing approval record. Plan never creates it."""
    if path is None:
        return []
    if not isinstance(path, (str, os.PathLike)):
        _fail("invalid-argument", "the routing approval path must be a path")
    approval_path = Path(path)
    if ".." in approval_path.parts or not approval_path.is_absolute():
        _fail("invalid-argument", "the routing approval path is not canonical")
    if not approval_path.is_relative_to(vault):
        _fail("private-scope", "routing approvals must live inside the private vault")
    require_private_directory(approval_path.parent)
    document = _json_object(read_file(approval_path), "the routing approval record")
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or set(document) != {"schema_version", "items", "signature"}
        or not isinstance(document["items"], list)
    ):
        _fail("invalid-config", "the routing approval record is malformed")
    _verify_routing_approval_signature(document)
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in document["items"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"role", "target_path", "before", "candidate_ref", "basis"}
            or item["role"] not in _ROUTING_ROLES
            or not isinstance(item["target_path"], str)
            or not isinstance(item["basis"], str)
            or not item["basis"].strip()
            or not isinstance(item["before"], dict)
            or not isinstance(item["candidate_ref"], dict)
        ):
            _fail("invalid-config", "a routing approval item is malformed")
        if item["target_path"] in seen:
            _fail("approval-conflict", "a routing target is approved more than once")
        seen.add(item["target_path"])
        items.append(item)
    return items


def _approved_routing_operations(
    items: Sequence[Mapping[str, Any]],
    roots: Sequence[Path],
    vault: Path,
    approval_path: Path,
    *,
    bind_live: bool = True,
) -> tuple[list[dict[str, Any]], dict[Path, list[dict[str, Any]]]]:
    """Bind each approved candidate to its live target. Mismatch blocks."""
    from onboard import default_codex_home, omp_global_agents_path, user_home

    pause = read_file(_PAUSE_ASSET)
    approval_ref = {"path": str(approval_path), "state": snapshot(approval_path)}
    shared: list[dict[str, Any]] = []
    private: dict[Path, list[dict[str, Any]]] = {root: [] for root in roots}
    dependents = sorted(str(root) for root in roots)
    for item in items:
        target = Path(item["target_path"])
        if (
            not target.is_absolute()
            or ".." in target.parts
            or target.name != "AGENTS.md"
            or target.is_relative_to(vault)
        ):
            _fail("approval-conflict", "a routing target is not a live AGENTS.md")
        role = item["role"]
        owner: Path | None = None
        if role == "codex-global":
            if target != default_codex_home() / "AGENTS.md":
                _fail(
                    "approval-conflict", "a codex routing approval names another file"
                )
        elif role == "omp-global":
            omp_home = user_home() / ".omp"
            if _omp_root_presence(omp_home) != "directory":
                _fail(
                    "ownership-conflict",
                    "the existing OMP root is not a safe directory",
                )
            if target != omp_global_agents_path(omp_home):
                _fail("approval-conflict", "an omp routing approval names another file")
        else:
            matches = [root for root in roots if target == root / "AGENTS.md"]
            if len(matches) != 1:
                _fail(
                    "approval-conflict",
                    "a project routing approval is outside the batch",
                )
            owner = matches[0]
        recorded = item["before"]
        if not isinstance(recorded, Mapping) or recorded.get("type") != "file":
            _fail("approval-conflict", "a routing approval does not bind a file")
        if bind_live:
            before = snapshot(target)
            if before != recorded:
                _fail(
                    "state-conflict", "a routing target no longer matches its approval"
                )
        else:
            before = dict(recorded)
        candidate = item["candidate_ref"]
        candidate_path = Path(candidate.get("path", ""))
        if (
            not candidate_path.is_absolute()
            or ".." in candidate_path.parts
            or not candidate_path.is_relative_to(vault)
            or snapshot(candidate_path) != candidate.get("state")
        ):
            _fail("state-conflict", "an approved routing candidate changed")
        raw = read_file(candidate_path, candidate["state"])
        if not raw.startswith(pause):
            _fail(
                "candidate-conflict",
                "an approved routing candidate lacks the pause block",
            )
        operation = _operation(
            "apply",
            "markdown",
            target,
            _ROUTING_SELECTOR,
            {"kind": "copy-file", "source_ref": copy.deepcopy(candidate)},
            {
                "kind": "approved-candidate",
                "reference": copy.deepcopy(candidate),
                "approval_ref": approval_ref,
                "role": role,
            },
            _state_requirement(before),
            dependents if owner is None else [str(owner)],
        )
        if owner is None:
            shared.append(operation)
        else:
            private[owner].append(operation)
    return shared, private


def _vault_file_ref(reference: Mapping[str, Any], vault: Path, message: str) -> Path:
    path = reference.get("path")
    if (
        not isinstance(path, str)
        or not Path(path).is_absolute()
        or ".." in Path(path).parts
        or not Path(path).is_relative_to(vault)
    ):
        _fail("private-scope", message)
    return Path(path)


def _routing_rows(
    payload: Mapping[str, Any],
) -> list[tuple[str, Path | None, Mapping[str, Any]]]:
    rows: list[tuple[str, Path | None, Mapping[str, Any]]] = []
    for operation in payload["shared_operations"]:
        if operation["selector"] == _ROUTING_SELECTOR:
            rows.append(("shared", None, operation))
    for project in payload["projects"]:
        root = Path(project["root"])
        for operation in project["private_operations"]:
            if operation["selector"] == _ROUTING_SELECTOR:
                rows.append(("private", root, operation))
    return rows


def _bind_approved_routing(
    payload: Mapping[str, Any], roots: Sequence[Path], *, bind_live: bool
) -> None:
    """Rebuild the approved set from the sealed approval ref and require a match.

    The ref lives on the payload, so dropping every routing operation cannot
    hide it. A missing, extra, or substituted operation is rejected. Role,
    target, and candidate changes fail the same comparison. The approval file
    and every declared candidate must stay inside the vault.
    """
    declared = _routing_rows(payload)
    approval = payload["routing_approvals"]
    if approval is None:
        if declared:
            _fail(
                "approval-conflict",
                "an approved routing replacement is not bound to its approval record",
            )
        return
    vault = Path(payload["backup_root"])
    approval_path = _vault_file_ref(
        approval,
        vault,
        "an approved routing record lives outside the private vault",
    )
    for _place, _root, operation in declared:
        ownership = operation["ownership"]
        candidate = operation["change"].get("source_ref")
        if not isinstance(ownership.get("approval_ref"), Mapping) or not isinstance(
            candidate, Mapping
        ):
            _fail(
                "approval-conflict",
                "an approved routing replacement is not bound to its approval record",
            )
        _vault_file_ref(
            ownership["approval_ref"],
            vault,
            "an approved routing record lives outside the private vault",
        )
        _vault_file_ref(
            candidate,
            vault,
            "an approved routing candidate lives outside the private vault",
        )
    if snapshot(approval_path) != approval["state"]:
        _fail("state-conflict", "the routing approval record changed")
    items = _load_routing_approvals(approval_path, vault)
    shared, private = _approved_routing_operations(
        items, roots, vault, approval_path, bind_live=bind_live
    )
    expected: list[tuple[str, Path | None, Mapping[str, Any]]] = [
        ("shared", None, operation) for operation in shared
    ]
    for root in roots:
        expected.extend(
            ("private", root, operation) for operation in private.get(root, [])
        )
    if [_routing_key(row) for row in declared] != [
        _routing_key(row) for row in expected
    ]:
        _fail(
            "approval-conflict",
            "an approved routing replacement does not match its approval record",
        )


def _routing_key(
    row: tuple[str, Path | None, Mapping[str, Any]],
) -> str:
    place, root, operation = row
    return contracts.canonical_json_bytes(
        {
            "place": place,
            "root": None if root is None else str(root),
            "operation": operation,
        }
    ).decode("utf-8")


def approved_agents_provenance(
    manifest: Mapping[str, Any],
) -> tuple[Mapping[str, Any], dict[str, bytes]]:
    """Re-proved signed AGENTS routing origin and approved project bodies.

    The origin is the manifest itself, or the re-verified deployment-less
    predecessor for a successor batch (``_verify_successor_predecessor``).
    The origin's complete signed routing set is rebuilt and bound exactly by
    ``_bind_approved_routing`` with ``bind_live=False``: the approval record,
    its signature, every target and every candidate state must still match
    the sealed operations, so preservation is authorized by the signed
    binding — never by a file name or live-byte prefix. Each returned body
    is the exact approved candidate bytes minus the native pause block and
    at most one immediately following formatting blank line, keyed by the
    sealed operation target. Only demo-project replacements carry project
    bodies; followup batches and batches without signed routing return an
    empty mapping (their deployments keep merging proven live bytes).
    """
    origin = manifest
    payload = manifest["payload"]
    if payload.get("followup") is not None:
        return origin, {}
    if payload.get("successor") is not None:
        origin, _receipt = _verify_successor_predecessor(manifest)
        payload = origin["payload"]
    if payload.get("routing_approvals") is None:
        return origin, {}
    roots = [Path(project["root"]) for project in payload["projects"]]
    _bind_approved_routing(payload, roots, bind_live=False)
    pause = read_file(_PAUSE_ASSET)
    bodies: dict[str, bytes] = {}
    for _place, _root, operation in _routing_rows(payload):
        if operation["ownership"].get("role") != "demo-project":
            continue
        candidate = operation["change"]["source_ref"]
        raw = read_file(Path(candidate["path"]), candidate["state"])
        if not raw.startswith(pause):
            _fail(
                "candidate-conflict",
                "an approved routing candidate lacks the pause block",
            )
        body = raw[len(pause) :]
        if body.startswith(b"\n"):
            body = body[1:]
        bodies[operation["target"]] = body
    return origin, bodies


def _check_skill_identity(
    operation: Mapping[str, Any], resolve_original: ResolveOriginal | None
) -> None:
    """Re-prove a sealed Skill retirement from the actual preserved original.

    The recorded directory state (never a version pin) binds the exact tree
    being retired; identity is read back from the live path while it matches
    or, after retirement, from the retained backup through the caller's
    resolver. An already-absent target leaves nothing to re-prove: the op is
    inert and its execution treats absence as a no-op.
    """
    ownership = operation["ownership"]
    reference = ownership["reference"]
    target = Path(reference["path"])
    live = snapshot(target)
    resolved: Path | None = None
    if live == reference["state"]:
        resolved = target
    elif resolve_original is not None:
        resolved = Path(resolve_original(reference)["path"])
    if resolved is None:
        if live["type"] == "absent":
            return
        _fail(
            "state-conflict",
            "a skill retirement target changed after planning",
        )
    from sbtd_cleanup_targets import skill_identity_error

    if skill_identity_error(resolved, ownership["name"]) is not None:
        _fail(
            "identity-conflict",
            "the sealed Skill retirement no longer proves its legacy identity",
        )


def _validate_shared_operations(
    payload: Mapping[str, Any],
    all_roots: list[str],
    resolve_original: ResolveOriginal | None = None,
) -> None:
    pins = _ownership_pins()
    pause_asset = {"path": str(_PAUSE_ASSET), "state": snapshot(_PAUSE_ASSET)}
    shared_roots = payload["shared_roots"]
    for record in shared_roots:
        if record["dependent_projects"] != all_roots:
            _fail("semantic-violation", "a shared root binds foreign dependents")
    for operation in payload["shared_operations"]:
        if operation["dependent_projects"] != all_roots:
            _fail("semantic-violation", "a shared operation binds foreign dependents")
        target = Path(operation["target"])
        covering = [
            record
            for record in shared_roots
            if _parts_relative(target, Path(record["path"])) is not None
        ]
        if len(covering) != 1:
            _fail("semantic-violation", "a shared operation leaves its roots")
        if operation["phase"] == "deploy":
            continue  # Checked as one complete producer-owned set below.
        change = operation["change"]
        ownership = operation["ownership"]
        if change.get("kind") == "ensure-file-block":
            if (
                operation["phase"] != "apply"
                or operation["owner_kind"] != "markdown"
                or operation["selector"] != "pause-legacy-routing"
                or target.name != "AGENTS.md"
            ):
                _fail("semantic-violation", "the routing pause shape was altered")
            if change["source_ref"] != pause_asset:
                _fail("semantic-violation", "the routing pause content was altered")
            pinned_state = {"type": "file", "checksum": pins["agents"]}
            if ownership["kind"] != "template-source" or ownership["reference"] != {
                "path": str(target),
                "state": pinned_state,
            }:
                _fail("semantic-violation", "the routing pause ownership was altered")
            if operation["before_requirement"] != _state_requirement(pinned_state):
                _fail("semantic-violation", "the routing pause before-state drifted")
        elif change == {"kind": "remove"}:
            if (
                operation["phase"] != "cleanup"
                or operation["owner_kind"] != "directory"
                or operation["selector"] != "whole-resource"
            ):
                _fail("semantic-violation", "a skill retirement shape was altered")
            if (
                ownership["kind"] != "skill-identity"
                or ownership["name"] not in pins["skills"]
            ):
                _fail("semantic-violation", "an unknown shared skill was added")
            # Logical scope proof: the sealed shared roots, never the ambient
            # environment, bind the retirement target. Re-resolving the live
            # skills dir here would misjudge a sealed plan whenever the plan
            # and this validation run under different environments, and the
            # recorded original (or its retained backup) already pins the
            # exact tree. A dedicated skills root has path authority itself;
            # when the Skills root is absorbed into a broader sealed home
            # root, the covering record must carry the sealed logical
            # ``skills_root`` location. Without that metadata there is no
            # exact binding left — a basename match under a broad home root
            # would prove nothing — so validation fails closed instead of
            # inferring a customary path.
            covering_root = covering[0]
            if covering_root["kind"] == "skills":
                logical_root = Path(covering_root["path"])
            else:
                sealed_logical = covering_root.get("skills_root")
                if sealed_logical is None:
                    _fail(
                        "semantic-violation",
                        "a skill retirement target was altered",
                    )
                logical_root = Path(sealed_logical)
            if target != logical_root / ownership["name"]:
                _fail("semantic-violation", "a skill retirement target was altered")
            requirement = operation["before_requirement"]
            if (
                requirement["kind"] != "state"
                or requirement["state"]["type"] != "directory"
            ):
                _fail("semantic-violation", "a skill retirement before-state drifted")
            if ownership["reference"] != {
                "path": str(target),
                "state": requirement["state"],
            }:
                _fail("semantic-violation", "a skill retirement ownership was altered")
            _check_skill_identity(operation, resolve_original)
        elif (
            change.get("kind") == "copy-file"
            and operation["selector"] == _ROUTING_SELECTOR
            and operation["phase"] == "apply"
            and operation["owner_kind"] == "markdown"
            and Path(operation["target"]).name == "AGENTS.md"
            and ownership.get("kind") == "approved-candidate"
            and ownership.get("reference") == change.get("source_ref")
        ):
            continue
        else:
            _fail("semantic-violation", "an unknown shared operation was added")
    pause_targets = {
        operation["target"]
        for operation in payload["shared_operations"]
        if operation["selector"] == "pause-legacy-routing"
    }
    replacement_targets = {
        operation["target"]
        for operation in payload["shared_operations"]
        if operation["selector"] == _ROUTING_SELECTOR
    }
    if pause_targets & replacement_targets:
        _fail(
            "approval-conflict",
            "an approved routing replacement cannot also append the pause block",
        )


# ---------------------------------------------------------------------------
# Plan-time inventory, freshness and ownership verification
# ---------------------------------------------------------------------------


def _check_item_freshness(root: Path, item: Mapping[str, Any], vault: Path) -> None:
    for reference in item["sources"]:
        state = reference["state"]
        if state["type"] != "file":
            _fail(
                "approval-conflict",
                "publication approval binds exact source files",
            )
        _check_reference_current(reference, "approval-conflict")
    candidate = item["candidate_ref"]
    if candidate is not None:
        candidate_path = Path(candidate["path"])
        if not candidate_path.is_relative_to(vault):
            _fail(
                "private-scope",
                "an approved candidate lives outside the private vault",
            )
        _check_reference_current(candidate, "approval-conflict")
    target = item["target_path"]
    if target is not None:
        target_path = Path(target)
        if _parts_relative(target_path, root) is None:
            _fail("scope-conflict", "a publication target leaves its project")
        if snapshot(target_path) != _ABSENT:
            _fail(
                "target-conflict",
                "a publication target already exists and is preserved for "
                "manual reconciliation",
            )
        _check_target_lineage(target_path, root)


def _load_publication_items(
    publication_path: Any, vault: Path
) -> list[Mapping[str, Any]]:
    if publication_path is None:
        return []
    if not isinstance(publication_path, (str, os.PathLike)):
        _fail("invalid-argument", "the publication decisions path must be a path")
    path = Path(publication_path)
    if ".." in path.parts or not path.is_absolute():
        _fail("invalid-argument", "the publication decisions path is not canonical")
    if not path.is_relative_to(vault):
        _fail(
            "private-scope",
            "publication decisions must live inside the private vault",
        )
    require_private_directory(path.parent)
    decisions = contracts.load_document(read_file(path), "publication_decisions")
    return decisions["items"]


def _parse_legacy_version(raw: bytes) -> str:
    try:
        version = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        _fail("unsupported-version", "the legacy tool version cannot be proven")
    if version not in _LEGACY_VERSIONS:
        _fail(
            "unsupported-version",
            "the legacy tool version is not the characterized one",
        )
    return version


def _check_legacy_version(root: Path) -> str:
    path = root / _LEGACY_DIR / _VERSION_FILE
    state = snapshot(path)
    if state["type"] != "file":
        _fail("unsupported-version", "the legacy tool version cannot be proven")
    return _parse_legacy_version(read_file(path, state))


def _inventory_version(
    entries: Sequence[Mapping[str, Any]], inventory_root: Path
) -> str:
    """Prove the data version of a sealed legacy inventory (live or backup)."""
    entry = next(
        (entry for entry in entries if entry["path"] == _VERSION_FILE), None
    )
    if entry is None or entry["type"] != "file":
        _fail("unsupported-version", "the legacy tool version cannot be proven")
    return _parse_legacy_version(
        read_file(
            inventory_root / _VERSION_FILE,
            {"type": "file", "checksum": entry["checksum"]},
        )
    )


def _template_hashes(root: Path, version: str) -> tuple[dict[str, str], dict[str, Any]]:
    path = root / _LEGACY_DIR / _TEMPLATE_HASHES
    reference = _present_file_reference(path, "the legacy ownership metadata")
    document = _json_object(
        read_file(path, reference["state"]), "the legacy ownership metadata"
    )
    return _parse_template_hashes(document, version), reference


def _parse_template_hashes(document: Any, version: str) -> dict[str, str]:
    """Validate legacy ownership metadata against the installed ownership pins.

    A v0.6.15 record may also claim lessons, runtime context or junk paths.
    Those digests prove recorded bytes only, never generated ownership, so
    they are validated for shape and left out of the generated hashes: user
    data keeps its publication, approval and fail-closed unknown-path rules.
    """
    if version not in _LEGACY_VERSIONS:
        _fail(
            "unsupported-version", "the legacy tool version is not the characterized one"
        )
    if (
        not isinstance(document, dict)
        or document.get("__version") != 2
        or not isinstance(document.get("hashes"), dict)
    ):
        _fail("invalid-config", "the legacy ownership metadata is malformed")
    hashes: dict[str, str] = {}
    configuration_pins = _ownership_pins()["project_configs"]
    for relative, digest in document["hashes"].items():
        parts = _check_safe_relative(relative, "a legacy ownership path")
        if parts[0] == _LEGACY_DIR and (
            len(parts) < 2 or parts[1] not in _GENERATED_LEGACY_TOP
        ):
            if (
                version != "0.6.15"
                or len(parts) < 2
                or parts[1] not in _LEGACY_CLAIMED_USER_DATA
            ):
                _fail(
                    "invalid-config",
                    "ownership metadata cannot claim legacy user data",
                )
            if not isinstance(digest, str) or _HEX64.fullmatch(digest) is None:
                _fail("invalid-config", "the legacy ownership metadata is malformed")
            continue
        if not isinstance(digest, str) or _HEX64.fullmatch(digest) is None:
            _fail("invalid-config", "the legacy ownership metadata is malformed")
        # A mutable legacy hash proves recorded bytes, not sole ownership
        # of a shared configuration. Mixed entries need reconciliation.
        if (
            len(parts) == 2
            and parts[1] in _SHARED_CONFIG_NAMES
            and digest not in configuration_pins.get(relative, ())
        ):
            _fail("ownership-conflict", "shared configuration ownership is unproven")
        hashes[PurePosixPath(*parts).as_posix()] = digest
    return hashes


def _normalized_text_digest(raw: bytes) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        _fail(
            "ownership-conflict",
            "a recorded generated file is not inspectable text",
        )
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def _official_alternative_digests(
    official: Mapping[str, tuple[str, ...]],
    relative: str,
    parts: tuple[str, ...],
) -> tuple[str, ...]:
    """Exact official digests authorized for one recorded path, if any.

    Shared host configuration and root-owned mixed documents keep their
    existing ownership rules; no official payload digest ever authorizes
    them.  Every other digest binds to this exact recorded path only.
    """
    if len(parts) == 2 and parts[1] in _SHARED_CONFIG_NAMES:
        return ()
    if len(parts) == 1 and parts[0] in _ROOT_OWNED_FILES:
        return ()
    return official.get(relative, ())


def _check_marker_block(text: str) -> None:
    start = f"<!-- {_TRELLIS_MARKER}:START -->"
    end = f"<!-- {_TRELLIS_MARKER}:END -->"
    if text.count(start) != 1 or text.count(end) != 1:
        _fail("ownership-conflict", "a managed marker is absent or ambiguous")
    left = text.index(start)
    try:
        text.index(end, left + len(start))
    except ValueError:
        _fail("ownership-conflict", "a managed marker is absent or ambiguous")


def _operation(
    phase: str,
    owner_kind: str,
    target: Path,
    selector: str,
    change: dict[str, Any],
    ownership: dict[str, Any],
    before: dict[str, Any],
    dependents: Sequence[str],
) -> dict[str, Any]:
    resource = contracts.resource_id(owner_kind, str(target))
    return {
        "operation_id": contracts.operation_id(phase, resource, selector),
        "phase": phase,
        "resource_id": resource,
        "owner_kind": owner_kind,
        "target": str(target),
        "selector": selector,
        "change": change,
        "ownership": ownership,
        "before_requirement": before,
        "dependent_projects": sorted(dependents),
    }


def _state_requirement(state: Mapping[str, Any]) -> dict[str, Any]:
    return {"kind": "state", "state": dict(state)}


def _require_no_host_roots(root: Path) -> None:
    """Prove absence without inspecting an unowned host directory's contents."""
    _canonical(root)
    for prefix in (*_PLATFORM_PREFIX, *_UNSELECTED_PLATFORM_PREFIX):
        if _lstat(root / prefix) is not None:
            _fail(
                "unknown-platform",
                "no configured platform could be proven from the ownership metadata",
            )


def _read_current(reference: Mapping[str, Any]) -> bytes:
    """Read a live input, pinned to its sealed state."""
    return read_file(Path(reference["path"]), reference["state"])


def _agents_no_touch(
    root: Path,
    hashes: Mapping[str, str],
    read_original: ReadOriginal,
    *,
    target_state: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Re-derive the sealed proof for an already-aligned root AGENTS.md.

    Recognition is exact and local: the legacy ownership metadata must record
    the project-root AGENTS.md, the original bytes must equal the bundled
    project template byte for byte, and those bytes must carry no legacy marker. A
    drifted or customized file returns None and keeps its signed-replacement
    or refusal rules; a trusted template that itself carries a marker fails
    closed instead of freezing legacy content in place.
    """
    if "AGENTS.md" not in hashes:
        return None
    target = root / "AGENTS.md"
    state = dict(target_state) if target_state is not None else snapshot(target)
    if state["type"] != "file":
        return None
    template = _present_file_reference(_PROJECT_AGENTS_TEMPLATE, "the project template")
    raw = read_original({"path": str(target), "state": state})
    if raw != read_original(template):
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if (
        f"<!-- {_TRELLIS_MARKER}:START -->" in text
        or f"<!-- {_TRELLIS_MARKER}:END -->" in text
    ):
        _fail(
            "ownership-conflict",
            "an aligned root document still carries a legacy marker",
        )
    return {
        "target": {"path": str(target), "state": state},
        "template": template,
    }


def _check_agents_no_touch_untouched(project: Mapping[str, Any]) -> None:
    """Re-prove the exact installed template binding and forbid all writes.

    Later batches must not trust a predecessor's re-sealed proof merely
    because its two references point to the same custom project document.
    """
    proof = project.get("agents_no_touch")
    if proof is None:
        return
    target = str(Path(project["root"]) / "AGENTS.md")
    if (
        proof["target"]["path"] != target
        or proof["template"]["path"] != str(_PROJECT_AGENTS_TEMPLATE)
    ):
        _fail(
            "semantic-violation",
            "the untouched AGENTS proof is not bound to the installed project template",
        )
    template = _present_file_reference(_PROJECT_AGENTS_TEMPLATE, "the project template")
    if (
        proof["template"] != template
        or proof["target"]["state"] != template["state"]
        or snapshot(Path(target)) != proof["target"]["state"]
    ):
        _fail(
            "semantic-violation",
            "the untouched AGENTS evidence no longer matches the installed template",
        )
    raw = _read_current(proof["target"])
    if raw != _read_current(template):
        _fail(
            "semantic-violation",
            "the untouched AGENTS bytes differ from the installed template",
        )
    if (
        f"<!-- {_TRELLIS_MARKER}:START -->".encode() in raw
        or f"<!-- {_TRELLIS_MARKER}:END -->".encode() in raw
    ):
        _fail(
            "ownership-conflict",
            "an aligned root document still carries a legacy marker",
        )
    for operation in project["private_operations"]:
        if operation["target"] == target:
            _fail(
                "semantic-violation",
                "an operation targets the proven untouched AGENTS",
            )


def _platform_operations(
    root: Path,
    hashes: Mapping[str, str],
    hashes_reference: Mapping[str, Any],
    approved_targets: Collection[Path] = (),
) -> tuple[list[str], list[dict[str, Any]], dict[str, Any] | None]:
    official = _ownership_pins()["official_payloads"]
    platforms: set[str] = set()
    operations: list[dict[str, Any]] = []
    agents_target = root / "AGENTS.md"
    no_touch = None
    if agents_target not in approved_targets:
        # An approved routing replacement takes precedence over recognition;
        # otherwise an already-aligned file is sealed as untouched proof.
        no_touch = _agents_no_touch(root, hashes, _read_current)
    legacy_rels = [
        PurePosixPath(*PurePosixPath(relative).parts[1:]).as_posix()
        for relative in hashes
        if PurePosixPath(relative).parts[:1] == (_LEGACY_DIR,)
        and len(PurePosixPath(relative).parts) > 1
    ]
    ignored, _tracked = _legacy_index(root, legacy_rels)
    pending_unknown: list[str] = []
    for relative in sorted(hashes):
        parts = PurePosixPath(relative).parts
        legacy_rel = (
            PurePosixPath(*parts[1:]).as_posix()
            if parts[:1] == (_LEGACY_DIR,) and len(parts) > 1
            else None
        )
        target = root.joinpath(*parts)
        if (
            len(parts) == 1
            and parts[0] in _ROOT_OWNED_FILES
            and target in approved_targets
        ):
            # An approved routing replacement owns this root document; the
            # recorded whole-file template digest must not gate it.
            continue
        if no_touch is not None and len(parts) == 1 and parts[0] in _ROOT_OWNED_FILES:
            # Already aligned with the bundled template: no operation, and
            # the sealed proof revalidates at every lifecycle stage instead.
            continue
        state = snapshot(target)
        if state["type"] != "file":
            _fail(
                "ownership-conflict",
                "a recorded generated file is unavailable",
            )
        raw = read_file(target, state)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            if legacy_rel is not None and legacy_rel in ignored:
                continue
            if legacy_rel is not None:
                pending_unknown.append(legacy_rel)
                continue
            _fail(
                "ownership-conflict",
                "a recorded generated file is not inspectable text",
            )
        digest = hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()
        if digest != hashes[relative] and digest not in _official_alternative_digests(
            official, relative, parts
        ):
            _fail(
                "ownership-conflict",
                "generated content drifted; removal is not authorized",
            )
        if parts[0] == _LEGACY_DIR:
            # Generated scripts/config stay in the byte-preserved legacy tree
            # until the separately gated cleanup; never remove them during apply.
            continue
        if parts[0] in _UNSELECTED_PLATFORM_PREFIX:
            _fail(
                "scope-conflict",
                "unselected legacy host routing requires reconciliation",
            )
        if len(parts) > 1 and parts[0] in _PLATFORM_PREFIX:
            platforms.add(_PLATFORM_PREFIX[parts[0]])
            operations.append(
                _operation(
                    "apply",
                    "file",
                    target,
                    "whole-resource",
                    {"kind": "remove"},
                    {"kind": "template-source", "reference": dict(hashes_reference)},
                    _state_requirement(state),
                    [str(root)],
                )
            )
        elif len(parts) == 1 and parts[0] in _ROOT_OWNED_FILES:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                _fail(
                    "ownership-conflict",
                    "a managed root document is not inspectable text",
                )
            _check_marker_block(text)
            operations.append(
                _operation(
                    "apply",
                    "markdown",
                    target,
                    "trellis-block",
                    {"kind": "remove"},
                    {
                        "kind": "managed-marker",
                        "reference": {"path": str(target), "state": state},
                        "marker": _TRELLIS_MARKER,
                    },
                    _state_requirement(state),
                    [str(root)],
                )
            )
        else:
            _fail(
                "unknown-content",
                "a recorded generated path cannot be classified",
            )
    if pending_unknown:
        _fail_unknown(root, pending_unknown)
    if not platforms:
        _require_no_host_roots(root)
    return sorted(platforms), operations, no_touch


def _private_task_skips(
    optional: Sequence[Mapping[str, Any]], root: Path
) -> dict[str, set[str]]:
    """Map a task folder to the members bound by one private-only skip."""
    skipped: dict[str, set[str]] = {}
    legacy = root / _LEGACY_DIR
    for item in optional:
        if item["decision"] != "private-only" or item["target_path"] is not None:
            continue
        rels = []
        for reference in item["sources"]:
            rel = _parts_relative(Path(reference["path"]), legacy)
            if rel is None:
                continue
            rels.append(rel)
        task_rels = [rel for rel in rels if rel[-1] == _TASK_JSON]
        if len(task_rels) != 1 or not task_rels[0] or task_rels[0][0] != "tasks":
            continue
        folder_parts = task_rels[0][:-1]
        folder = PurePosixPath(*folder_parts).as_posix()
        members = {PurePosixPath(*rel[len(folder_parts) :]).as_posix() for rel in rels}
        if folder in skipped:
            _fail("approval-conflict", "a legacy task has more than one private skip")
        skipped[folder] = members
    return skipped


# ---------------------------------------------------------------------------
# Successor deployment batch (binds one completed deployment-less batch)
# ---------------------------------------------------------------------------


def _load_successor_predecessor(
    manifest_path: Any, apply_path: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load and fully bind the completed predecessor batch. Read-only."""
    from sbtd_migration import _private_document

    if manifest_path is None or apply_path is None:
        _fail(
            "invalid-argument",
            "successor manifest and apply receipt must be supplied as a pair",
        )
    # The manifest directory and the backup vault are separate private areas:
    # receipts live beside the manifest while approvals/candidates live in the
    # vault. Privacy comes from _private_document, not vault containment.
    for value, message in (
        (manifest_path, "the successor manifest path is not canonical"),
        (apply_path, "the successor apply receipt path is not canonical"),
    ):
        if not isinstance(value, (str, os.PathLike)):
            _fail("invalid-argument", message)
        candidate = Path(value)
        if ".." in candidate.parts or not candidate.is_absolute():
            _fail("invalid-argument", message)
    prev_manifest, manifest_raw = _private_document(Path(manifest_path), "manifest")
    prev_receipt, apply_raw = _private_document(Path(apply_path), "apply_receipt")
    contracts.validate_declared_bindings(
        prev_manifest,
        {"apply_receipt": prev_receipt},
        {"manifest": manifest_raw, "apply_receipt": apply_raw},
    )
    contracts._bind_success_gate(prev_receipt, {"applied", "already-complete"})
    prev_payload = prev_manifest["payload"]
    if prev_payload["deployment"] is not None:
        _fail(
            "successor-conflict",
            "the completed batch already declares its deployment",
        )
    if prev_payload.get("successor") is not None:
        _fail(
            "successor-conflict",
            "a successor batch cannot follow another successor batch",
        )
    return prev_manifest, prev_receipt


def _plan_successor(
    roots: Sequence[Path],
    vault: Path,
    custodian: str,
    tool_versions: Mapping[str, Any],
    deployment_mode: str,
    hooks_authorized: bool,
    deployment_platform: str,
    prev_manifest: Mapping[str, Any],
    prev_receipt: Mapping[str, Any],
    successor_manifest_path: Path,
    successor_apply_path: Path,
) -> dict[str, Any]:
    """Seal a successor batch bound to one completed deployment-less batch.

    The predecessor's verified after-states are this batch's pre-states, so
    the apply-inventory gates (pinned generated files, publication freshness)
    are not re-run; every completed outcome and every carried cleanup target
    is re-measured instead. Read-only.
    """
    from sbtd_migration import _project_revision, _result_index

    prev_payload = prev_manifest["payload"]
    prev_projects = prev_payload["projects"]
    if {project["root"] for project in prev_projects} != {
        str(root) for root in roots
    }:
        _fail(
            "scope-conflict",
            "a successor batch must exactly match the completed batch roots",
        )
    if Path(prev_payload["backup_root"]) != vault:
        _fail(
            "scope-conflict",
            "a successor batch stays in the completed batch vault",
        )
    if prev_payload["custodian"] != custodian:
        _fail(
            "approval-conflict",
            "a successor batch keeps the recorded custodian",
        )
    results = _result_index(prev_receipt)
    prev_operations: dict[str, Mapping[str, Any]] = {}
    for project in prev_projects:
        for operation in project["private_operations"]:
            prev_operations[operation["resource_id"]] = operation
    for operation in prev_payload["shared_operations"]:
        prev_operations[operation["resource_id"]] = operation
    for operation in prev_operations.values():
        if operation["phase"] != "apply":
            continue
        result = results.get(operation["resource_id"])
        if (
            result is None
            or result["status"] != "succeeded"
            or result["after"] is None
        ):
            _fail(
                "successor-conflict",
                "the completed receipt does not prove every declared apply resource",
            )
        if snapshot(Path(operation["target"])) != result["after"]:
            _fail(
                "state-conflict",
                "a completed batch outcome no longer matches the current state",
            )

    def carry_cleanup(operation: Mapping[str, Any]) -> dict[str, Any]:
        requirement = operation["before_requirement"]
        if requirement["kind"] != "state":
            _fail(
                "semantic-violation",
                "a carried cleanup operation needs a concrete before-state",
            )
        if snapshot(Path(operation["target"])) != requirement["state"]:
            _fail(
                "state-conflict",
                "a pending cleanup target drifted from the completed batch",
            )
        return copy.deepcopy(dict(operation))

    carried_shared: list[dict[str, Any]] = []
    for operation in prev_payload["shared_operations"]:
        if operation["phase"] == "apply":
            continue
        if operation["phase"] != "cleanup":
            _fail(
                "successor-conflict",
                "the completed batch declares an unsupported later phase",
            )
        carried_shared.append(carry_cleanup(operation))
    # Every shared apply operation owns a global routing file, whether it
    # appended the pause block or copied an approved candidate; both are the
    # legitimate pre-state for the successor's installation templates.
    successor_pauses = {
        operation["target"]: operation["resource_id"]
        for operation in prev_payload["shared_operations"]
        if operation["phase"] == "apply"
    }
    projects: list[dict[str, Any]] = []
    for prev_project in prev_projects:
        root = Path(prev_project["root"])
        source_ref, head = _project_revision(root)
        sources = copy.deepcopy(prev_project["sources"])
        for reference in sources:
            if snapshot(Path(reference["path"])) != reference["state"]:
                _fail(
                    "state-conflict",
                    "a project legacy source drifted from the completed batch",
                )
        carried_private: list[dict[str, Any]] = []
        for operation in prev_project["private_operations"]:
            if operation["phase"] == "apply":
                continue
            if operation["phase"] != "cleanup":
                _fail(
                    "successor-conflict",
                    "the completed batch declares an unsupported later phase",
                )
            carried_private.append(carry_cleanup(operation))
        project_payload: dict[str, Any] = {
            "root": prev_project["root"],
            "source_ref": source_ref,
            "head": head,
            "platforms": list(prev_project["platforms"]),
            "sources": sources,
            "private_operations": carried_private,
            "shared_operation_ids": [],
        }
        proof = prev_project.get("agents_no_touch")
        if proof is not None:
            # The completed batch's untouched-AGENTS proof carries forward
            # only while the live file still matches it exactly.
            if snapshot(Path(proof["target"]["path"])) != proof["target"]["state"]:
                _fail(
                    "state-conflict",
                    "the proven untouched AGENTS drifted from the completed batch",
                )
            _check_agents_no_touch_untouched(prev_project)
            project_payload["agents_no_touch"] = copy.deepcopy(proof)
        projects.append(project_payload)
    embedded = [
        copy.deepcopy(result)
        for project in prev_receipt["payload"]["projects"]
        for result in project["private_results"]
    ] + copy.deepcopy(list(prev_receipt["payload"]["shared_results"]))
    if not embedded:
        _fail(
            "successor-conflict",
            "the completed receipt records no apply resources",
        )
    payload = {
        "projects": projects,
        "shared_roots": copy.deepcopy(list(prev_payload["shared_roots"])),
        "shared_operations": carried_shared,
        "publication_decisions": {"schema_version": 1, "items": []},
        "routing_approvals": None,
        "custodian": custodian,
        "backup_root": str(vault),
        "created_at": datetime.now().astimezone().isoformat(timespec="microseconds"),
        "retention": copy.deepcopy(prev_payload["retention"]),
        "tool_versions": dict(tool_versions),
        "deployment": None,
        "successor": {
            "manifest_id": prev_manifest["manifest_id"],
            "apply_id": prev_receipt["apply_id"],
            "manifest_ref": {
                "path": str(successor_manifest_path),
                "state": snapshot(successor_manifest_path),
            },
            "apply_receipt_ref": {
                "path": str(successor_apply_path),
                "state": snapshot(successor_apply_path),
            },
            "apply_results": embedded,
        },
    }
    from sbtd_graft_deployment import attach_deployment

    attach_deployment(
        payload,
        project_only=deployment_mode == "init-projects",
        hooks_authorized=hooks_authorized,
        platform=deployment_platform,
        successor_pauses=successor_pauses,
    )
    for project in payload["projects"]:
        if any(
            operation["phase"] == "apply"
            for operation in project["private_operations"]
        ):
            _fail(
                "successor-conflict",
                "the completed batch left required ignore protection unapplied; "
                "reconcile it before planning a successor batch",
            )
    _check_physical_aliases(
        [
            operation
            for project in projects
            for operation in project["private_operations"]
        ]
        + payload["shared_operations"]
    )
    _bind_approved_routing(payload, roots, bind_live=True)
    return contracts.seal_document("manifest", payload)

def _load_followup_predecessor(
    manifest_path: Any,
    apply_path: Any,
    deployment_path: Any,
    verification_path: Any,
    cleanup_path: Any,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    list[tuple[Mapping[str, Any], Mapping[str, Any]]],
]:
    """Load and fully bind the completed Codex predecessor chain. Read-only."""
    from sbtd_migration import _private_document

    values = (manifest_path, apply_path, deployment_path, verification_path, cleanup_path)
    if any(value is None for value in values):
        _fail(
            "invalid-argument",
            "followup predecessor documents must be supplied as a complete set",
        )
    # As with the successor pair: receipts live beside the manifest while the
    # vault holds approvals/candidates. Privacy comes from _private_document.
    for value, message in (
        (manifest_path, "the followup manifest path is not canonical"),
        (apply_path, "the followup apply receipt path is not canonical"),
        (deployment_path, "the followup deployment evidence path is not canonical"),
        (verification_path, "the followup verification path is not canonical"),
        (cleanup_path, "the followup cleanup receipt path is not canonical"),
    ):
        if not isinstance(value, (str, os.PathLike)):
            _fail("invalid-argument", message)
        candidate = Path(value)
        if ".." in candidate.parts or not candidate.is_absolute():
            _fail("invalid-argument", message)
    prev_manifest, manifest_raw = _private_document(Path(manifest_path), "manifest")
    prev_apply, apply_raw = _private_document(Path(apply_path), "apply_receipt")
    prev_deployment, deployment_raw = _private_document(
        Path(deployment_path), "deployment_evidence"
    )
    prev_verification, verification_raw = _private_document(
        Path(verification_path), "verification"
    )
    prev_cleanup, cleanup_raw = _private_document(Path(cleanup_path), "cleanup_receipt")
    ancestors = _bind_followup_predecessor(
        prev_manifest,
        prev_apply,
        prev_deployment,
        prev_verification,
        prev_cleanup,
        {
            "manifest": manifest_raw,
            "apply_receipt": apply_raw,
            "deployment_evidence": deployment_raw,
            "verification": verification_raw,
            "cleanup_receipt": cleanup_raw,
        },
    )
    return (
        prev_manifest,
        prev_apply,
        prev_deployment,
        prev_verification,
        prev_cleanup,
        ancestors,
    )


def _plan_followup(
    roots: Sequence[Path],
    vault: Path,
    custodian: str,
    tool_versions: Mapping[str, Any],
    prev_manifest: Mapping[str, Any],
    prev_apply: Mapping[str, Any],
    prev_deployment: Mapping[str, Any],
    prev_verification: Mapping[str, Any],
    prev_cleanup: Mapping[str, Any],
    ancestors: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
    followup_manifest_path: Path,
    followup_apply_path: Path,
    followup_deployment_path: Path,
    followup_verification_path: Path,
    followup_cleanup_path: Path,
) -> dict[str, Any]:
    """Seal a followup batch bound to one fully completed Codex batch.

    The predecessor's proven after-states are this batch's concrete
    pre-states, so the retired legacy closure is never re-derived; every
    completed outcome is re-measured instead. Read-only.
    """
    from sbtd_migration import (
        _project_revision,
        _require_reconciliation_provenance,
        _result_index,
    )

    prev_payload = prev_manifest["payload"]
    prev_projects = prev_payload["projects"]
    if {project["root"] for project in prev_projects} != {
        str(root) for root in roots
    }:
        _fail(
            "scope-conflict",
            "a followup batch must exactly match the completed batch roots",
        )
    if Path(prev_payload["backup_root"]) != vault:
        _fail(
            "scope-conflict",
            "a followup batch stays in the completed batch vault",
        )
    if prev_payload["custodian"] != custodian:
        _fail(
            "approval-conflict",
            "a followup batch keeps the recorded custodian",
        )
    _check_followup_predecessor_outcomes(
        _followup_outcome_chain(
            prev_manifest, prev_apply, prev_deployment, prev_cleanup, ancestors
        ),
        overwritten=(),
    )
    followup_deployed = {
        result["resource_id"]: result["after"]
        for result in _result_index(prev_deployment).values()
        if result["status"] == "succeeded" and result["after"] is not None
    }
    projects: list[dict[str, Any]] = []
    for prev_project in prev_projects:
        root = Path(prev_project["root"])
        source_ref, head = _project_revision(root)
        project_payload: dict[str, Any] = {
            "root": prev_project["root"],
            "source_ref": source_ref,
            "head": head,
            "platforms": list(prev_project["platforms"]),
            "sources": [],
            "private_operations": [],
            "shared_operation_ids": [],
        }
        proof = prev_project.get("agents_no_touch")
        if proof is not None:
            # The completed chain's untouched-AGENTS proof carries forward
            # only while the live file still matches it exactly.
            if snapshot(Path(proof["target"]["path"])) != proof["target"]["state"]:
                _fail(
                    "state-conflict",
                    "the proven untouched AGENTS drifted from the completed batch",
                )
            _check_agents_no_touch_untouched(prev_project)
            project_payload["agents_no_touch"] = copy.deepcopy(proof)
        projects.append(project_payload)
    payload = {
        "projects": projects,
        "shared_roots": [],
        "shared_operations": [],
        "publication_decisions": {"schema_version": 1, "items": []},
        "routing_approvals": None,
        "custodian": custodian,
        "backup_root": str(vault),
        "created_at": datetime.now().astimezone().isoformat(timespec="microseconds"),
        "retention": copy.deepcopy(prev_payload["retention"]),
        "tool_versions": dict(tool_versions),
        "deployment": None,
        "followup": {
            "manifest_id": prev_manifest["manifest_id"],
            "apply_id": prev_apply["apply_id"],
            "deployment_id": prev_deployment["deployment_id"],
            "verification_id": prev_verification["verification_id"],
            "cleanup_id": prev_cleanup["cleanup_id"],
            "manifest_ref": {
                "path": str(followup_manifest_path),
                "state": snapshot(followup_manifest_path),
            },
            "apply_receipt_ref": {
                "path": str(followup_apply_path),
                "state": snapshot(followup_apply_path),
            },
            "deployment_evidence_ref": {
                "path": str(followup_deployment_path),
                "state": snapshot(followup_deployment_path),
            },
            "verification_ref": {
                "path": str(followup_verification_path),
                "state": snapshot(followup_verification_path),
            },
            "cleanup_receipt_ref": {
                "path": str(followup_cleanup_path),
                "state": snapshot(followup_cleanup_path),
            },
        },
    }
    from sbtd_graft_deployment import attach_deployment

    attach_deployment(
        payload,
        project_only=False,
        hooks_authorized=False,
        platform="omp",
        followup_deployed=followup_deployed,
    )
    for project in payload["projects"]:
        if any(
            operation["phase"] == "apply"
            for operation in project["private_operations"]
        ):
            _fail(
                "followup-conflict",
                "the completed batch left required ignore protection unapplied; "
                "reconcile it before planning a followup batch",
            )
    _check_physical_aliases(
        [
            operation
            for project in projects
            for operation in project["private_operations"]
        ]
        + payload["shared_operations"]
    )
    _bind_approved_routing(payload, roots, bind_live=True)
    manifest = contracts.seal_document("manifest", payload)
    _require_reconciliation_provenance(prev_manifest, prev_deployment)
    return manifest



def _session_targets_complete_skip(
    relative: tuple[str, ...] | None,
    entries: Sequence[Mapping[str, Any]],
    items: Sequence[Mapping[str, Any]],
    root: Path,
) -> bool:
    """True only when a session names one fully private-only task folder."""
    if (
        not relative
        or ".." in relative
        or len(relative) < 3
        or relative[0] != _LEGACY_DIR
        or relative[1] != "tasks"
    ):
        return False
    folder = PurePosixPath(*relative[1:]).as_posix()
    bound = _private_task_skips(items, root).get(folder)
    if not bound or _TASK_JSON not in bound:
        return False
    prefix = folder + "/"
    actual = {
        entry["path"][len(prefix) :]
        for entry in entries
        if entry["type"] == "file" and str(entry["path"]).startswith(prefix)
    }
    return bound == actual


def _git_bytes(
    root: Path,
    args: Sequence[str],
    stdin: bytes | None = None,
    *,
    environment: Mapping[str, str] | None = None,
) -> bytes | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            input=stdin,
            capture_output=True,
            check=False,
            env=environment,
        )
    except OSError:
        return None
    if completed.returncode == 128:
        return None
    if args[0] == "check-ignore" and completed.returncode not in (0, 1):
        return None
    if args[0] != "check-ignore" and completed.returncode != 0:
        return None
    return completed.stdout


def _legacy_index(
    root: Path,
    relative_paths: Sequence[str],
    *,
    inventory_root: Path | None = None,
    entries: Sequence[Mapping[str, Any]] = (),
) -> tuple[set[str], set[str]]:
    """Return (ignored, tracked) paths relative to ``.trellis``.

    Ignored follows index-aware ``git check-ignore``: a tracked file is not
    ignored. If git cannot answer, nothing is treated as ignored.
    """
    prefix = f"{_LEGACY_DIR}/"
    listed = _git_bytes(root, ["ls-files", "-z", "--", _LEGACY_DIR])
    if listed is None:
        return set(), set()
    tracked = {
        path.decode()[len(prefix) :]
        for path in listed.split(b"\0")
        if path.startswith(prefix.encode())
    }
    repo_paths = [f"{prefix}{rel}" for rel in relative_paths]
    if not repo_paths:
        return set(), tracked
    if inventory_root is not None and inventory_root != root / _LEGACY_DIR:
        ignored = _retained_legacy_ignored(root, inventory_root, entries, relative_paths)
        return ignored - tracked, tracked
    checked = _git_bytes(
        root,
        ["check-ignore", "-z", "--stdin"],
        b"\0".join(path.encode() for path in repo_paths) + b"\0",
    )
    ignored = {
        path.decode()[len(prefix) :]
        for path in (checked or b"").split(b"\0")
        if path.startswith(prefix.encode())
    }
    return ignored - tracked, tracked


def _retained_legacy_ignored(
    root: Path,
    inventory_root: Path,
    entries: Sequence[Mapping[str, Any]],
    relative_paths: Sequence[str],
) -> set[str]:
    """Ask Git about the original rule hierarchy, not a re-rooted approximation.

    Only ignore files enter a private temporary tree. No payload, repository,
    index or worktree registration is copied or changed.
    """
    import tempfile

    git_dir = _git_bytes(root, ["rev-parse", "--absolute-git-dir"])
    git_top = _git_bytes(root, ["rev-parse", "--show-toplevel"])
    if git_dir is None or git_top is None:
        return set()
    directory = Path(os.fsdecode(git_dir.rstrip(b"\n")))
    top = Path(os.fsdecode(git_top.rstrip(b"\n")))
    if (
        not directory.is_absolute()
        or not directory.is_dir()
        or not top.is_absolute()
        or not root.is_relative_to(top)
    ):
        return set()
    project_relative = root.relative_to(top)
    ancestors = [root]
    while ancestors[-1] != top:
        ancestors.append(ancestors[-1].parent)
    directories = {entry["path"] for entry in entries if entry["type"] == "directory"}
    files_by_directory: dict[str, list[Mapping[str, Any]]] = {}
    for entry in entries:
        if entry["type"] == "file":
            parent = PurePosixPath(entry["path"]).parent.as_posix()
            files_by_directory.setdefault(parent, []).append(entry)
    queries = {
        f"{_LEGACY_DIR}/{relative}" + ("/" if relative in directories else ""): relative
        for relative in relative_paths
    }
    with tempfile.TemporaryDirectory(prefix="sbtd-retained-ignore-") as temporary:
        sandbox = require_private_directory(
            Path(temporary).resolve() / "rules", create=True
        )
        project = sandbox / project_relative
        legacy = project / _LEGACY_DIR
        legacy.mkdir(parents=True, exist_ok=True)
        directory_ids: set[tuple[int, int]] = set()
        for relative in sorted(directories, key=lambda path: (path.count("/"), path)):
            target = legacy / relative
            target.mkdir(parents=True, exist_ok=True)
            info = target.stat()
            identity = (info.st_dev, info.st_ino)
            if identity in directory_ids:
                _fail("ownership-conflict", "retained directory aliases cannot be reproduced")
            directory_ids.add(identity)
        for entry in entries:
            if entry["type"] == "file" and (legacy / entry["path"]).is_dir():
                _fail("ownership-conflict", "retained file and directory aliases conflict")
        for ancestor in reversed(ancestors):
            source = ancestor / ".gitignore"
            state = snapshot(source)
            if state["type"] == "absent":
                continue
            content = read_file(source, state)
            target = sandbox / ancestor.relative_to(top) / ".gitignore"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        for parent, siblings in files_by_directory.items():
            relative = PurePosixPath(parent) / ".gitignore"
            source = inventory_root.joinpath(*relative.parts)
            state = snapshot(source)
            if state["type"] == "absent":
                continue
            # Git uses the filesystem lookup, not a case-sensitive basename
            # filter. Bind any effective alias back to the proven inventory.
            entry = next(
                (item for item in siblings if item["path"] == relative.as_posix()),
                None,
            )
            if entry is None:
                matches = [
                    item
                    for item in siblings
                    if source.samefile(inventory_root / item["path"])
                ]
                if len(matches) != 1:
                    _fail("ownership-conflict", "retained ignore alias cannot be proven")
                entry = matches[0]
            content = read_file(
                source, {"type": "file", "checksum": entry["checksum"]}
            )
            target = legacy / relative
            target.write_bytes(content)
        checked = _git_bytes(
            project,
            ["check-ignore", "--no-index", "-z", "--stdin"],
            b"\0".join(os.fsencode(path) for path in queries) + b"\0",
            environment={
                **os.environ,
                "GIT_DIR": str(directory),
                "GIT_WORK_TREE": str(sandbox),
                "GIT_OPTIONAL_LOCKS": "0",
            },
        )
    if checked is None:
        return set()
    return {
        queries[path]
        for raw in checked.split(b"\0")
        if (path := os.fsdecode(raw)) in queries
    }


def _fail_unknown(root: Path, relative_paths: Sequence[str]) -> NoReturn:
    _ignored, tracked = _legacy_index(root, relative_paths)
    _fail(
        "unknown-content",
        "tracked or unignored unknown legacy files need an explicit decision",
        details={
            "paths": list(relative_paths),
            "tracked": [path for path in relative_paths if path in tracked],
            "recommendation": (
                "Do not delete a tracked file from this list. If it is local "
                "noise, stop tracking it and ignore it, then re-run plan. If "
                "it is real legacy data, approve it explicitly before planning "
                "again."
            ),
        },
    )


def _partition_legacy_entries(
    root: Path,
    entries: Sequence[Mapping[str, Any]],
    *,
    inventory_root: Path | None = None,
) -> tuple[list[Mapping[str, Any]], list[str]]:
    """Drop only gitignored paths outside the known layout.

    ``tasks``, ``spec`` and ``lessons`` stay even when gitignore matches them,
    so an ignored ``task.json`` still requires its approval.
    """
    ignored, _tracked = _legacy_index(
        root,
        [entry["path"] for entry in entries],
        inventory_root=inventory_root,
        entries=entries,
    )
    classified: list[Mapping[str, Any]] = []
    unknown: list[str] = []
    for entry in entries:
        relative = entry["path"]
        top = relative.split("/", 1)[0]
        if top not in _KNOWN_LEGACY_TOP:
            if relative in ignored:
                continue
            unknown.append(relative)
            continue
        classified.append(entry)
    return classified, unknown


def _check_generated_legacy_bytes(
    root: Path,
    inventory_root: Path,
    entries: Sequence[Mapping[str, Any]],
    hashes: Mapping[str, str],
) -> None:
    """Re-prove recorded generated legacy payloads from the sealed inventory.

    The directory snapshot binds the whole tree, but a coherently re-sealed
    manifest could swap one generated payload's bytes.  Bind every recorded
    generated file to its recorded digest - or to a pinned exact official
    payload - before its ownership claim is honored.  Bytes come from the
    proven inventory root (live or retained backup), checksum-bound to the
    sealed snapshot; binary and gitignore handling mirrors the plan gate.
    """
    official = _ownership_pins()["official_payloads"]
    recorded = [
        relative
        for relative in sorted(hashes)
        if PurePosixPath(relative).parts[:1] == (_LEGACY_DIR,)
        and len(PurePosixPath(relative).parts) > 1
    ]
    if not recorded:
        return
    proven = {entry["path"]: entry for entry in entries if entry["type"] == "file"}
    ignored: set[str] | None = None
    for relative in recorded:
        parts = PurePosixPath(relative).parts
        legacy_rel = PurePosixPath(*parts[1:]).as_posix()
        entry = proven.get(legacy_rel)
        if entry is None:
            _fail(
                "ownership-conflict",
                "a recorded generated file is unavailable",
            )
        raw = read_file(
            inventory_root.joinpath(*parts[1:]),
            {"type": "file", "checksum": entry["checksum"]},
        )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            if ignored is None:
                ignored, _tracked = _legacy_index(
                    root,
                    [
                        PurePosixPath(*PurePosixPath(item).parts[1:]).as_posix()
                        for item in recorded
                    ],
                    inventory_root=inventory_root,
                    entries=entries,
                )
            if legacy_rel in ignored:
                continue
            _fail_unknown(root, [legacy_rel])
        digest = hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()
        if digest != hashes[relative] and digest not in _official_alternative_digests(
            official, relative, parts
        ):
            _fail(
                "ownership-conflict",
                "generated content drifted; removal is not authorized",
            )


def _inventory_coverage(
    entries: Sequence[Mapping[str, Any]],
    closures: Mapping[
        tuple[str, ...], Sequence[tuple[Mapping[str, Any], list[tuple[str, ...]]]]
    ],
    forms: Mapping[tuple[str, ...], str],
    documents: Sequence[tuple[str, Mapping[str, Any], list[tuple[str, ...]]]],
    optional: Sequence[Mapping[str, Any]],
    root: Path,
    hashes: Mapping[str, str],
    *,
    inventory_root: Path | None = None,
) -> None:
    """Exact bijection between classified legacy files and approvals.

    Gitignored entries stay in the directory snapshot and are omitted here.
    """
    classified, unknown = _partition_legacy_entries(
        root, entries, inventory_root=inventory_root
    )
    if unknown:
        _fail_unknown(root, unknown)
    entries = classified
    empty_task_placeholder = False
    for entry in entries:
        if entry["path"].split("/", 1)[0] not in _KNOWN_LEGACY_TOP:
            _fail("unknown-content", "the legacy directory holds unclassified content")
        if entry["path"] == "tasks/.gitkeep":
            empty_task_placeholder = (
                entry["type"] == "file"
                and entry["checksum"] == hashlib.sha256(b"").hexdigest()
            )
    files = sorted(entry["path"] for entry in entries if entry["type"] == "file")
    folder_names: set[str] = set()
    for name in files:
        parts = PurePosixPath(name).parts
        if len(parts) >= 3 and parts[0] == "tasks" and parts[-1] == _TASK_JSON:
            folder_names.add(PurePosixPath(*parts[:-1]).as_posix())
    folder_members: dict[str, list[str]] = {folder: [] for folder in folder_names}
    history_files: list[str] = []
    for name in files:
        if not name.startswith("tasks/"):
            continue
        if name == "tasks/.gitkeep" and empty_task_placeholder:
            continue
        matches = [folder for folder in folder_names if name.startswith(folder + "/")]
        if not matches:
            # No ancestor task.json claims this file: it is task history and
            # only an approved verbatim document may cover it, exactly once.
            history_files.append(name)
            continue
        folder = max(matches, key=len)
        folder_members[folder].append(name[len(folder) + 1 :])
    coverage: dict[str, int] = {}

    def cover(key: str) -> None:
        coverage[key] = coverage.get(key, 0) + 1

    for folder, records in closures.items():
        folder_prefix = PurePosixPath(*folder[1:]).as_posix()
        for _item, rels in records:
            for rel in rels:
                cover(folder_prefix + "/" + PurePosixPath(*rel).as_posix())
    for category, _item, rels in documents:
        for rel in rels:
            cover(category + "/" + PurePosixPath(*rel).as_posix())
    for item in optional:
        if item["target_path"] is not None:
            # Handoffs may bind the same private journals for several tasks;
            # this is provenance, not duplicate publication of the originals.
            continue
        for reference in item["sources"]:
            rel = _parts_relative(Path(reference["path"]), root / _LEGACY_DIR)
            if rel is not None:
                cover(PurePosixPath(*rel).as_posix())
    for folder, records in closures.items():
        folder_name = PurePosixPath(*folder[1:]).as_posix()
        if folder_name not in folder_members:
            _fail(
                "approval-conflict",
                "an approved task projection has no legacy source",
            )
        form = forms[folder]
        for member in folder_members[folder_name]:
            # File-form closures bind task.json exactly twice (task.md
            # projection plus sidecar); every other legacy member — including
            # existing prd/design/implement attachments — binds exactly once,
            # as does every member of a whole-tree directory approval.
            expected = 1
            if member == _TASK_JSON and form == "file":
                expected = 2
            if coverage.get(folder_name + "/" + member, 0) != expected:
                _fail(
                    "approval-required",
                    "legacy task data is not covered exactly by its approved "
                    "projections",
                )
    skipped = _private_task_skips(optional, root)
    for folder, members in folder_members.items():
        folder_tuple = (_LEGACY_DIR, *PurePosixPath(folder).parts)
        if folder_tuple in closures:
            continue
        if skipped.get(folder) != set(members):
            _fail("approval-required", "a legacy task has no approved projections")
        for member in members:
            if coverage.get(f"{folder}/{member}", 0) != 1:
                _fail(
                    "approval-required",
                    "legacy task data is not covered exactly by its approved "
                    "projections",
                )
    for name in history_files:
        count = coverage.get(name, 0)
        if count == 0:
            _fail(
                "approval-required",
                "a historical task document needs its approved projection",
            )
        if count > 1:
            _fail(
                "approval-conflict",
                "a historical task document is approved at most once",
            )
    unowned = [
        name
        for name in files
        if name.split("/", 1)[0] in _GENERATED_LEGACY_TOP
        and f"{_LEGACY_DIR}/{name}" not in hashes
        and coverage.get(name, 0) != 1
    ]
    if unowned:
        ignored, _tracked = _legacy_index(
            root, unowned, inventory_root=inventory_root, entries=entries
        )
        asked = [name for name in unowned if name not in ignored]
        if asked:
            _fail_unknown(root, asked)
    for name in files:
        top = name.split("/", 1)[0]
        if top in _GENERATED_LEGACY_TOP and (
            f"{_LEGACY_DIR}/{name}" not in hashes and coverage.get(name, 0) != 1
        ):
            continue
        if top == "tasks":
            continue
        if top in _MANDATORY_TOP:
            if coverage.get(name, 0) != 1:
                _fail(
                    "approval-required",
                    "legacy documents are not covered exactly once",
                )
        elif coverage.get(name, 0) > 1:
            _fail("approval-conflict", "optional legacy data is approved at most once")


# ---------------------------------------------------------------------------
# Identity, protection and legacy-tree operations
# ---------------------------------------------------------------------------


def _deferred_recovery_instruction(
    task_branch: str | None, checkout: str | None
) -> str:
    """Canonical resume instruction for a handoff on a historic task branch.

    The migrated task keeps its legacy branch verbatim while the planning
    checkout records the actual current project HEAD. When the two differ,
    the approved handoff must carry this exact instruction (as its whole
    next action or as its first line) so any later write goes through the
    existing TaskStore rebind/branch gate instead of silently resuming.
    """
    task = task_branch if task_branch is not None else "no Git binding"
    seen = checkout if checkout is not None else "no Git binding"
    return (
        "Deferred branch recovery: the task stays bound to branch "
        + json.dumps(task, ensure_ascii=False)
        + " while the planning checkout is "
        + json.dumps(seen, ensure_ascii=False)
        + "; resume on the task branch or explicitly rebind the task through "
        "recovery before any task write."
    )


def _check_context_handoffs(
    root: Path,
    entries: Sequence[Mapping[str, Any]],
    closures: Mapping[tuple[str, ...], Any],
    projections: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
    read_source: ReadOriginal,
    source_ref: str | None,
    head: str | None,
) -> None:
    """Bind private continuation summaries to the entire original context.

    Trellis 0.6.17 stores current_task in .runtime/sessions/*.json, not
    .current-task. Journals have no machine-readable task ownership: when
    present, explicitly approved summaries must cover every unfinished task.
    Nothing here selects an active task or manufactures a summary.
    """
    from sbtd_handoff import _REDACTION_DECLARATION, HandoffStore
    from sbtd_task_state import TaskStateError, TaskStore

    context: dict[str, Mapping[str, Any]] = {}
    active_folders: set[tuple[str, ...]] = set()
    has_journal = False
    for entry in entries:
        if entry["type"] != "file":
            continue
        parts = PurePosixPath(entry["path"]).parts
        reference = {
            "path": str(root / _LEGACY_DIR / entry["path"]),
            "state": {"type": "file", "checksum": entry["checksum"]},
        }
        if parts == (".current-task",):
            if read_source(reference).strip():
                _fail(
                    "invalid-config",
                    "legacy path-line pointers need explicit reconciliation",
                )
            continue
        session = len(parts) == 3 and parts[:2] == (".runtime", "sessions")
        if parts[0] != "workspace" and not session:
            if parts[0] == ".runtime":
                approved = any(
                    item["decision"] == "private-only" and reference in item["sources"]
                    for item in items
                )
                if not approved:
                    _fail(
                        "approval-required",
                        "unknown runtime context needs private approval",
                    )
            continue
        raw = read_source(reference)
        if parts[-1] == ".gitkeep" and not raw:
            continue
        context[reference["path"]] = reference
        if not session:
            has_journal = True
            continue
        if not parts[-1].endswith(".json"):
            _fail("invalid-config", "legacy session records must be JSON")
        record = _json_object(raw, "the legacy session")
        metadata = {
            "platform",
            "last_seen_at",
            "current_task",
            "current_run",
            "session_id",
            "sessionId",
            "sessionID",
            "conversation_id",
            "conversationId",
            "conversationID",
            "transcript_path",
            "transcriptPath",
            "transcript",
        }
        if not isinstance(record, dict) or set(record) - metadata:
            _fail("invalid-config", "legacy session has an unknown structure")
        task_ref = record.get("current_task")
        if task_ref is None:
            if record.get("current_run") is not None:
                _fail("graph-conflict", "a legacy run has no associated task")
            continue
        if not isinstance(task_ref, str) or not task_ref.strip():
            _fail("invalid-config", "legacy current_task must be a nonblank reference")
        task_path = Path(task_ref)
        if task_path.is_absolute():
            relative = _parts_relative(task_path, root)
        else:
            normalized = task_ref.replace("\\", "/")
            while normalized.startswith("./"):
                normalized = normalized[2:]
            relative = PurePosixPath(normalized).parts
            if relative and relative[0] == "tasks":
                relative = (_LEGACY_DIR, *relative)
            elif relative and relative[0] != _LEGACY_DIR:
                relative = (_LEGACY_DIR, "tasks", *relative)
        if relative is None or ".." in relative or (
            relative not in closures
            and not _session_targets_complete_skip(relative, entries, items, root)
        ):
            _fail(
                "graph-conflict",
                "legacy session task has no unique approved projection",
            )
        if relative in closures:
            active_folders.add(relative)

    needed = {
        projection.legacy_id
        for projection in projections.values()
        if projection.document.frontmatter["status"] not in TERMINAL_STATUSES
        and (
            has_journal
            or any(
                folder[-1] in projection.aliases or folder[-1] == projection.legacy_id
                for folder in active_folders
            )
        )
    }
    handoff_items = [
        item
        for item in items
        if item["target_path"] is not None
        and Path(item["target_path"]).parent == root / "docs" / "handoffs"
    ]
    if not needed and not handoff_items:
        return
    if not context or not needed:
        _fail(
            "approval-conflict",
            "a handoff requires identified unfinished legacy context",
        )
    store = HandoffStore(TaskStore(root, read_only=True))
    covered: set[str] = set()
    for item in handoff_items:
        if item["decision"] != "redact" or not item["required"]:
            _fail(
                "approval-required",
                "a continuation handoff needs required redact approval",
            )
        if {ref["path"]: ref for ref in item["sources"]} != context:
            _fail(
                "approval-conflict",
                "handoff approval must bind the complete private context",
            )
        candidate = item["candidate_ref"]
        if candidate["state"]["type"] != "file":
            _fail("candidate-conflict", "a handoff candidate must be a Markdown file")
        try:
            text = _candidate_bytes(candidate, None).decode("utf-8")
            handoff = store._parse_text(text)
        except (UnicodeError, TaskStateError):
            _fail("candidate-conflict", "the handoff snapshot is invalid")
        task_id = handoff["task_id"]
        if task_id not in needed or task_id in covered:
            _fail("graph-conflict", "handoff task identity is unexpected or duplicated")
        fields = projections[task_id].document.frontmatter
        expected = {
            "task_id": task_id,
            "task_path": f"ai/tasks/{task_id}/task.md",
            "project_root": str(root),
            "branch": fields["branch"],
            "head": head,
            "task_status": fields["status"],
            "workflow_mode": fields["workflow_mode"],
            "mode_source": fields["mode_source"],
            "mode_note": fields["mode_note"],
            "redaction": _REDACTION_DECLARATION,
        }
        if any(handoff[key] != value for key, value in expected.items()):
            _fail(
                "candidate-conflict",
                "handoff identity, revision or task state does not match",
            )
        content = handoff["content"]
        if (
            not content["goal"].strip()
            or not content["next_action"].strip()
            or not any(value.strip() for value in content["remaining"])
        ):
            _fail(
                "candidate-conflict",
                "handoff must state its goal, remaining work and next action",
            )
        instruction = _deferred_recovery_instruction(fields["branch"], source_ref)
        next_action = content["next_action"]
        mismatched = fields["branch"] != source_ref
        carries = next_action == instruction or next_action.startswith(
            instruction + "\n"
        )
        if mismatched != carries:
            _fail(
                "candidate-conflict",
                "a handoff on a historic branch must carry its exact deferred "
                "recovery instruction, and a same-branch handoff must not",
            )
        target = Path(item["target_path"])
        date = datetime.fromisoformat(handoff["created_at"].replace("Z", "+00:00"))
        expected_name = f"{date:%Y_%m_%d}-{store._task_key(task_id)}.md"
        if target.name != expected_name:
            _fail(
                "target-conflict",
                "handoff filename must bind its task and snapshot date",
            )
        snapshot_fields = {
            key: value for key, value in handoff.items() if key != "summary"
        }
        if store._render(snapshot_fields) != text:
            _fail("candidate-conflict", "handoff body must match its approved snapshot")
        covered.add(task_id)
    if covered != needed:
        _fail(
            "approval-required",
            "unfinished workspace context requires approved handoffs",
        )
    tracked = store.tasks._git("ls-files", "-z", "--", "docs/handoffs")
    if head is not None and tracked.returncode:
        _fail("private-scope", "handoff tracked state cannot be verified")
    if tracked.returncode == 0 and tracked.stdout:
        _fail("private-scope", "handoff storage must not be tracked")
    _check_handoff_ignore(root, [Path(item["target_path"]) for item in handoff_items])


def _check_handoff_ignore(root: Path, targets: Sequence[Path]) -> None:
    """Evaluate planned ignore bytes without changing the selected project."""
    import tempfile

    from onboard import gitignore_verdicts
    from sbtd_migration import _append_blocks
    from sbtd_task_state import TaskStore

    ignore_path = root / ".gitignore"
    state = snapshot(ignore_path)
    current = b"" if state["type"] == "absent" else read_file(ignore_path, state)
    operation = _ignore_operation(root)
    planned = _append_blocks(current, [operation]) if operation is not None else current
    with tempfile.TemporaryDirectory(prefix="sbtd-handoff-ignore-") as directory:
        sandbox = Path(directory)
        git = TaskStore(sandbox)
        initialized = git._git("init", "--quiet")
        if initialized.returncode:
            _fail("private-scope", "handoff ignore protection cannot be verified")
        (sandbox / ".gitignore").write_bytes(planned)
        for relative in ("docs/.gitignore", "docs/handoffs/.gitignore"):
            source = root / relative
            source_state = snapshot(source)
            if source_state["type"] == "absent":
                continue
            content = read_file(source, source_state)
            target = sandbox / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        probes = (
            "docs/handoffs/",
            *(path.relative_to(root).as_posix() for path in targets),
        )
        verdicts = gitignore_verdicts(sandbox, probes, env=git._git_environment())
        if isinstance(verdicts, str) or not all(
            verdict.ignored for verdict in verdicts.values()
        ):
            _fail(
                "private-scope",
                "planned ignore rules do not protect every private handoff",
            )


def _identity_operation(root: Path) -> dict[str, Any] | None:
    legacy_path = root / _LEGACY_DIR / _DEVELOPER_NAME
    legacy_state = snapshot(legacy_path)
    store = DeveloperStore(root, read_only=True)
    resolved = store.resolve()
    if resolved.status == "ready":
        return None
    if resolved.status != "needs-name" or not resolved.first_write_eligible:
        _fail(
            "identity-conflict",
            "the current developer identity state cannot host a migration",
        )
    legacy_name: str | None = None
    if legacy_state["type"] == "file":
        legacy_name = read_legacy_identity(read_file(legacy_path, legacy_state))
    elif legacy_state["type"] != "absent":
        _fail("identity-conflict", "the legacy identity path is not a normal file")
    if legacy_name is None:
        # No old or new identity: the runtime asks on first use; a migration
        # never invents or guesses a name.
        return None
    planned = store.plan(legacy_name)
    if planned.status != "planned":
        _fail("identity-conflict", "the legacy identity cannot be migrated safely")
    target = root / ".sbtd" / "developer"
    if snapshot(target) != _ABSENT:
        _fail("identity-conflict", "the current identity target is not missing")
    _check_target_lineage(target, root)
    source = {"path": str(legacy_path), "state": legacy_state}
    return _operation(
        "apply",
        "file",
        target,
        "name",
        {"kind": "migrate-developer", "source_ref": source, "name": legacy_name},
        {"kind": "config-entry", "reference": dict(source), "key_path": ["name"]},
        _state_requirement(_ABSENT),
        [str(root)],
    )


def _ignore_operation(root: Path) -> dict[str, Any] | None:
    from onboard import missing_file_lines

    asset = _present_file_reference(_IGNORE_ASSET, "the local ignore asset")
    gitignore = root / ".gitignore"
    before = snapshot(gitignore)
    if before["type"] == "directory":
        _fail("target-conflict", "the ignore path is not a writable file")
    current = b"" if before["type"] == "absent" else read_file(gitignore, before)
    try:
        asset_text = read_file(Path(asset["path"]), asset["state"]).decode("utf-8")
        current_text = current.decode("utf-8")
    except UnicodeDecodeError:
        _fail("invalid-config", "managed ignore content is not UTF-8 text")
    if not missing_file_lines(asset_text, current_text):
        return None
    if before["type"] == "absent":
        _check_target_lineage(gitignore, root)
    return _operation(
        "apply",
        "gitignore",
        gitignore,
        "local-ignore",
        {"kind": "ensure-file-block", "source_ref": asset},
        {"kind": "template-source", "reference": dict(asset)},
        _state_requirement(before),
        [str(root)],
    )


def _publication_operation(root: Path, item: Mapping[str, Any]) -> dict[str, Any]:
    candidate = item["candidate_ref"]
    target = Path(item["target_path"])
    directory = candidate["state"]["type"] == "directory"
    owner_kind = (
        "directory" if directory else "markdown" if target.suffix == ".md" else "file"
    )
    return _operation(
        "apply",
        owner_kind,
        target,
        "whole-resource",
        {
            "kind": "copy-directory" if directory else "copy-file",
            "source_ref": copy.deepcopy(candidate),
        },
        {"kind": "template-source", "reference": copy.deepcopy(candidate)},
        _state_requirement(_ABSENT),
        [str(root)],
    )


def _legacy_cleanup_operation(
    root: Path, legacy_reference: Mapping[str, Any]
) -> dict[str, Any]:
    target = root / _LEGACY_DIR
    return _operation(
        "cleanup",
        "directory",
        target,
        "whole-resource",
        {"kind": "remove"},
        {"kind": "template-source", "reference": dict(legacy_reference)},
        _state_requirement(legacy_reference["state"]),
        [str(root)],
    )


# ---------------------------------------------------------------------------
# Shared HOME/config resources (owned once, full dependent closure)
# ---------------------------------------------------------------------------


def _shared_operations(
    roots: Sequence[Path],
    approved_targets: Collection[Path] = (),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Pause the exact pinned v1.0.15 global routing, retire proven old Skills.

    Foreign global content is preserved untouched. Customized legacy routing
    blocks instead of silently remaining active; only byte-exact known ownership
    authorizes a pause. Retired Skills are recognized by identity (a regular
    directory whose SKILL.md frontmatter names the retired Skill), never by a
    version checksum, so every 1.0.x line qualifies while a same-named foreign
    directory is preserved. Cleanup stays gated on later verification; no new
    wiring is deployed here.
    """
    from onboard import (
        default_codex_home,
        omp_global_agents_path,
        resolve_global_skills_dir,
        user_home,
    )

    dependents = sorted(str(root) for root in roots)
    pins = _ownership_pins()
    operations: list[dict[str, Any]] = []
    needed_roots: dict[str, str] = {}
    codex_home = default_codex_home()
    routing_targets = [("codex-home", codex_home, codex_home / "AGENTS.md")]
    omp_home = user_home() / ".omp"
    # Existence only. Every path component is checked nofollow; children are
    # not walked. Unrelated links inside the directory are not routing targets.
    omp_presence = _omp_root_presence(omp_home)
    if omp_presence == "directory":
        routing_targets.append(("omp-home", omp_home, omp_global_agents_path(omp_home)))
    elif omp_presence == "file":
        _fail("ownership-conflict", "the existing OMP root is not a safe directory")
    pause = _present_file_reference(_PAUSE_ASSET, "the maintenance asset")
    current_routing = read_file(_PACKAGE / "templates" / "agents" / "AGENTS.global.md")
    seen_targets: set[Path] = set()
    for root_kind, shared_root, agents in routing_targets:
        if agents in seen_targets:
            continue
        seen_targets.add(agents)
        if agents in approved_targets:
            continue
        agents_state = snapshot(agents)
        if agents_state == {"type": "file", "checksum": pins["agents"]}:
            operations.append(
                _operation(
                    "apply",
                    "markdown",
                    agents,
                    "pause-legacy-routing",
                    {"kind": "ensure-file-block", "source_ref": pause},
                    {
                        "kind": "template-source",
                        "reference": {"path": str(agents), "state": agents_state},
                    },
                    _state_requirement(agents_state),
                    dependents,
                )
            )
            needed_roots[str(shared_root)] = root_kind
        elif agents_state["type"] == "file":
            raw = read_file(agents, agents_state)
            if raw != current_routing and re.search(
                rb"\btrellis\b", raw, re.IGNORECASE
            ):
                _fail(
                    "ownership-conflict",
                    "customized legacy global routing requires explicit reconciliation",
                )
    skills_root, _source = resolve_global_skills_dir()
    if _lineage_probe(skills_root) == "directory":
        _physical_root(skills_root)
        from sbtd_cleanup_targets import skill_identity_error

        for name in sorted(pins["skills"]):
            target = skills_root / name
            if skill_identity_error(target, name) is not None:
                continue  # absent, drifted or foreign content is never retired
            state = snapshot(target)
            if state["type"] != "directory":
                continue
            operations.append(
                _operation(
                    "cleanup",
                    "directory",
                    target,
                    "whole-resource",
                    {"kind": "remove"},
                    {
                        "kind": "skill-identity",
                        "reference": {"path": str(target), "state": state},
                        "name": name,
                    },
                    _state_requirement(state),
                    dependents,
                )
            )
            needed_roots[str(skills_root)] = "skills"
    shared_roots: list[dict[str, Any]] = [
        {"kind": kind, "path": path, "dependent_projects": dependents}
        for path, kind in sorted(needed_roots.items())
    ]
    kept_roots = [
        record
        for record in shared_roots
        if not any(
            other["path"] != record["path"]
            and Path(record["path"]).is_relative_to(Path(other["path"]))
            for other in shared_roots
        )
    ]
    # A collapsed record leaves its exact binding on the surviving covering
    # root: an absorbed Skills root seals its logical location there. Without
    # it the retirement target would lose its exact sealed scope and later
    # validation fails closed.
    for record in shared_roots:
        if record["kind"] != "skills" or record in kept_roots:
            continue
        covering = [
            other
            for other in kept_roots
            if other["path"] != record["path"]
            and Path(record["path"]).is_relative_to(Path(other["path"]))
        ]
        if len(covering) == 1:
            covering[0]["skills_root"] = record["path"]
    return kept_roots, operations


# ---------------------------------------------------------------------------
# Physical alias guard (same rule as the apply-time context validation)
# ---------------------------------------------------------------------------


def _check_physical_aliases(operations: Sequence[Mapping[str, Any]]) -> None:
    seen: dict[tuple[int, int], str] = {}
    for operation in operations:
        target = Path(operation["target"])
        state = snapshot(target)
        if state["type"] == "absent":
            continue
        metadata = target.lstat()
        identity = metadata.st_dev, metadata.st_ino
        if (state["type"] == "file" and metadata.st_nlink > 1) or seen.setdefault(
            identity, str(target)
        ) != str(target):
            _fail(
                "physical-alias",
                "managed resources have ambiguous physical ownership",
            )


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def plan_migration(
    project_roots: Sequence[Any],
    backup_root: Any,
    custodian: Any,
    publication_path: Any,
    *,
    tool_versions: Mapping[str, Any],
    deployment_mode: str | None = None,
    hooks_authorized: bool = False,
    deployment_platform: str = "codex",
    routing_approvals: Any = None,
    routing_approval_key: Any = None,
    successor_manifest: Any = None,
    successor_apply_receipt: Any = None,
    followup_manifest: Any = None,
    followup_apply_receipt: Any = None,
    followup_deployment_evidence: Any = None,
    followup_verification: Any = None,
    followup_cleanup_receipt: Any = None,
) -> dict[str, Any]:
    """Verify the authorized preparation and seal a bound migration manifest.

    Read-only unless ``routing_approval_key`` is set. That path signs only the
    named approval file, and only after the key matches the installed public
    key. An existing verified-private ``backup_root``, exact publication
    decisions with existing candidates, current source and target states, the
    per-project Git binding, the pinned legacy ownership metadata and the
    identity chain are all validated; any conflict blocks the plan with zero
    writes instead of guessing.
    """
    if deployment_mode not in {None, "init", "init-projects"}:
        _fail("invalid-argument", "the deployment mode must be explicitly supported")
    if hooks_authorized and deployment_mode != "init":
        _fail(
            "scope-conflict",
            "global hooks require an explicitly planned full deployment",
        )
    if deployment_platform not in {"codex", "omp"}:
        _fail(
            "invalid-argument", "the deployment platform must be explicitly supported"
        )
    from sbtd_migration import _RETENTION, _project_revision

    if (
        isinstance(project_roots, (str, bytes))
        or not isinstance(project_roots, Sequence)
        or not project_roots
    ):
        _fail("invalid-argument", "at least one project root is required")
    if not isinstance(custodian, str) or not custodian.strip():
        _fail("invalid-argument", "a custodian is required")
    if (
        not isinstance(tool_versions, Mapping)
        or set(tool_versions)
        != {
            "onboard",
            "graft",
        }
        or any(
            not isinstance(value, str) or not value.strip()
            for value in tool_versions.values()
        )
    ):
        _fail(
            "invalid-argument",
            "tool versions must name the actual onboard and graft builds",
        )
    roots = [_physical_root(value) for value in project_roots]
    if len(set(roots)) != len(roots):
        _fail("scope-conflict", "duplicate project root in the selected batch")
    for index, root in enumerate(roots):
        for other in roots[index + 1 :]:
            if (
                root.samefile(other)
                or root.is_relative_to(other)
                or other.is_relative_to(root)
            ):
                _fail(
                    "scope-conflict", "selected project roots must not overlap or alias"
                )
    vault = _private_vault(backup_root)
    for root in roots:
        if vault.is_relative_to(root) or root.is_relative_to(vault):
            _fail(
                "private-scope",
                "the private backup root must stay outside the selected projects",
            )
    followup_values = (
        followup_manifest,
        followup_apply_receipt,
        followup_deployment_evidence,
        followup_verification,
        followup_cleanup_receipt,
    )
    if any(value is not None for value in followup_values):
        if successor_manifest is not None or successor_apply_receipt is not None:
            _fail(
                "invalid-argument",
                "a followup batch cannot also be a successor batch",
            )
        if publication_path is not None:
            _fail(
                "invalid-argument",
                "a followup batch does not consume publication decisions",
            )
        if routing_approvals is not None or routing_approval_key is not None:
            _fail(
                "invalid-argument",
                "a followup batch does not consume routing approvals",
            )
        if deployment_mode != "init":
            _fail(
                "invalid-argument",
                "a followup batch requires the full init deployment mode",
            )
        if deployment_platform != "omp":
            _fail(
                "invalid-argument",
                "a followup batch deploys only to the OMP platform",
            )
        if hooks_authorized:
            _fail(
                "scope-conflict",
                "a followup batch does not authorize hooks",
            )
        (
            prev_manifest,
            prev_apply,
            prev_deployment,
            prev_verification,
            prev_cleanup,
            ancestors,
        ) = _load_followup_predecessor(
            followup_manifest,
            followup_apply_receipt,
            followup_deployment_evidence,
            followup_verification,
            followup_cleanup_receipt,
        )
        return _plan_followup(
            roots,
            vault,
            custodian,
            tool_versions,
            prev_manifest,
            prev_apply,
            prev_deployment,
            prev_verification,
            prev_cleanup,
            ancestors,
            Path(followup_manifest),
            Path(followup_apply_receipt),
            Path(followup_deployment_evidence),
            Path(followup_verification),
            Path(followup_cleanup_receipt),
        )
    if successor_manifest is not None or successor_apply_receipt is not None:
        if publication_path is not None:
            _fail(
                "invalid-argument",
                "a successor batch does not consume publication decisions",
            )
        if routing_approvals is not None or routing_approval_key is not None:
            _fail(
                "invalid-argument",
                "a successor batch does not consume routing approvals",
            )
        if deployment_mode is None:
            _fail(
                "invalid-argument",
                "a successor batch requires an explicit deployment mode",
            )
        prev_manifest, prev_receipt = _load_successor_predecessor(
            successor_manifest, successor_apply_receipt
        )
        return _plan_successor(
            roots,
            vault,
            custodian,
            tool_versions,
            deployment_mode,
            hooks_authorized,
            deployment_platform,
            prev_manifest,
            prev_receipt,
            Path(successor_manifest),
            Path(successor_apply_receipt),
        )
    items = _load_publication_items(publication_path, vault)
    assigned = _assign_items(roots, items)
    private_strings = _private_strings(vault)
    if routing_approval_key is not None:
        if routing_approvals is None:
            _fail(
                "invalid-argument",
                "a routing approval key requires the routing approval file",
            )
        _sign_routing_approval(
            Path(routing_approvals), Path(routing_approval_key), vault, roots
        )
    routing_items = _load_routing_approvals(routing_approvals, vault)
    routing_path = Path(routing_approvals) if routing_approvals is not None else vault
    shared_replacements, private_replacements = (
        _approved_routing_operations(routing_items, roots, vault, routing_path)
        if routing_approvals is not None
        else ([], {})
    )
    approved_targets = {Path(item["target_path"]) for item in routing_items}

    read_current = _read_current

    projects: list[dict[str, Any]] = []
    for root in roots:
        project_items = assigned[root]
        for item in project_items:
            _check_item_freshness(root, item, vault)
        source_ref, head = _project_revision(root)
        legacy_path = root / _LEGACY_DIR
        legacy_state = snapshot(legacy_path)
        if legacy_state["type"] != "directory":
            _fail(
                "missing-legacy",
                "the selected project has no legacy Trellis data",
            )
        legacy_reference = {"path": str(legacy_path), "state": legacy_state}
        _state, entries = directory_snapshot(legacy_path)
        version = _check_legacy_version(root)
        hashes, hashes_reference = _template_hashes(root, version)
        platforms, platform_ops, agents_no_touch = _platform_operations(
            root, hashes, hashes_reference, approved_targets
        )
        closures, documents, optional = _classify_project_items(root, project_items)
        projections, forms = _validate_project_closures(
            root, closures, documents, read_current, private_strings
        )
        _inventory_coverage(
            entries,
            closures,
            forms,
            documents,
            optional,
            root,
            hashes,
            inventory_root=root / _LEGACY_DIR,
        )
        _check_context_handoffs(
            root,
            entries,
            closures,
            projections,
            project_items,
            read_current,
            source_ref,
            head,
        )
        identity_op = _identity_operation(root)
        publication_ops = [
            _publication_operation(root, item)
            for item in sorted(
                (item for item in project_items if item["decision"] != "private-only"),
                key=lambda item: item["target_path"],
            )
        ]
        private_ops: list[dict[str, Any]] = []
        if identity_op is not None or publication_ops:
            ignore_op = _ignore_operation(root)
            if ignore_op is not None:
                private_ops.append(ignore_op)
        if identity_op is not None:
            private_ops.append(identity_op)
        private_ops.extend(publication_ops)
        private_ops.extend(platform_ops)
        private_ops.extend(private_replacements.get(root, []))
        private_ops.append(_legacy_cleanup_operation(root, legacy_reference))
        project_payload: dict[str, Any] = {
            "root": str(root),
            "source_ref": source_ref,
            "head": head,
            "platforms": platforms,
            "sources": [legacy_reference],
            "private_operations": private_ops,
            "shared_operation_ids": [],
        }
        if agents_no_touch is not None:
            # Sealed proof that the root AGENTS.md already matches the
            # bundled template; revalidated exactly at validate/apply/retry/
            # recovery instead of touching the file.
            project_payload["agents_no_touch"] = agents_no_touch
        projects.append(project_payload)
    shared_roots, shared_ops = _shared_operations(roots, approved_targets)
    for operation in shared_replacements:
        target = Path(operation["target"])
        role = operation["ownership"]["role"]
        root_path = target.parent if role == "codex-global" else target.parent.parent
        kind = "codex-home" if role == "codex-global" else "omp-home"
        if not any(record["path"] == str(root_path) for record in shared_roots):
            shared_roots.append(
                {
                    "kind": kind,
                    "path": str(root_path),
                    "dependent_projects": sorted(str(root) for root in roots),
                }
            )
        shared_ops.append(operation)
    # A replacement-declared home root can cover a skills root that stood
    # alone before the merge; fold it into logical metadata exactly like the
    # producer-side collapse so the retirement target keeps one unambiguous
    # covering root with its sealed logical Skills location.
    for record in list(shared_roots):
        if record["kind"] != "skills":
            continue
        covering = [
            other
            for other in shared_roots
            if other is not record
            and other["path"] != record["path"]
            and other["dependent_projects"] == record["dependent_projects"]
            and Path(record["path"]).is_relative_to(Path(other["path"]))
        ]
        if len(covering) != 1:
            continue
        covering[0].setdefault("skills_root", record["path"])
        shared_roots.remove(record)
    shared_ids = sorted(operation["operation_id"] for operation in shared_ops)
    for project in projects:
        project["shared_operation_ids"] = list(shared_ids)
    payload = {
        "projects": projects,
        "shared_roots": shared_roots,
        "shared_operations": shared_ops,
        "publication_decisions": {"schema_version": 1, "items": copy.deepcopy(items)},
        "routing_approvals": (
            {"path": str(routing_path), "state": snapshot(routing_path)}
            if routing_approvals is not None
            else None
        ),
        "custodian": custodian,
        "backup_root": str(vault),
        "created_at": datetime.now().astimezone().isoformat(timespec="microseconds"),
        "retention": copy.deepcopy(_RETENTION),
        "tool_versions": dict(tool_versions),
        "deployment": None,
    }
    if deployment_mode is not None:
        from sbtd_graft_deployment import attach_deployment

        attach_deployment(
            payload,
            project_only=deployment_mode == "init-projects",
            hooks_authorized=hooks_authorized,
            platform=deployment_platform,
        )
    _check_physical_aliases(
        [
            operation
            for project in projects
            for operation in project["private_operations"]
        ]
        + shared_ops
    )
    _bind_approved_routing(payload, roots, bind_live=True)
    return contracts.seal_document("manifest", payload)
