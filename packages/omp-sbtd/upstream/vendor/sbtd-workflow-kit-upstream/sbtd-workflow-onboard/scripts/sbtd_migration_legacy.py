"""Legacy Trellis identity/task projection validation; pure bytes, no I/O.

Grounded in Trellis v0.6.17 commit 833a5846d18ad7a5ccd8c41c876d89cc936f5fd9:

- ``common/developer.py`` writes ``name=<name>\\ninitialized_at=<datetime>\\n``.
  ``read_legacy_identity`` extracts exactly one unmodified, currently valid
  name; it never normalizes and never relaxes ``DeveloperStore`` parsing.
- ``common/task_store.py`` task.json carries id/name (the bare slug),
  title/description/status, createdAt/completedAt written by
  ``strftime("%Y-%m-%d")`` (date granularity only), branch/base_branch,
  parent/children/subtasks storing full ``MM-DD-slug`` directory names, and
  meta plus other keys. ``subtasks`` is the legacy spelling of ``children``.
- Archive writes status=completed before moving a task under
  ``tasks/archive/<YYYY-MM>/``; position or the archive action alone never
  proves completion, and an ``archived`` status value is not a success proof.
- Older observed task.json records also carry the blocked/cancelled status
  literals, preserved verbatim. cancelled is a native terminal cancellation:
  ``completed_at`` stays null (no fake completedAt), its history is exactly
  one ``unknown -> cancelled`` event timed by a provable cancelledAt (missing
  or date-only stays unknown), and an archived cancelled record buckets only
  by a fully proven (RFC3339) cancellation quarter, else ``undated`` — never
  the directory name.
  blocked keeps its truthful reason (a supplied blocked_reason or an
  unambiguous ``meta.suspension.reason``; otherwise the canonical missing-
  evidence text), one ``unknown -> blocked`` event timed by a provable
  ``meta.suspension.since``, and no fabricated recovery phase.

The caller (Main) reads and binds the actual bytes; this module only parses
and validates. Publication approval, secret scanning and plan/apply/verify
orchestration live outside; nothing here proves them. Every failure is a
sanitized ``ContractError`` that names the fixed rule, never a rejected value.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from onboard_arguments import validate_developer_name
from onboard_contracts import ContractError
from sbtd_project import TaskDataError
from sbtd_task_document import TaskDocument, _frontmatter_bounds

# ---------------------------------------------------------------------------
# Fixed legacy vocabulary (pinned Trellis source + main PRD section 11.2/11.3)
# ---------------------------------------------------------------------------

# v0.6.17 writes planning -> in_progress -> completed; the PRD mapping table
# additionally names the pending/in-progress/checking/review/done spellings.
# Older observed records also carry the blocked/cancelled literals; both are
# preserved verbatim (blocked stays unfinished, cancelled is a native
# terminal cancellation, never a success). "archived" is deliberately
# absent: it never proves completion by itself, and no alias spellings
# (e.g. "canceled") are accepted.
_STATUS_MAP = {
    "planning": "planned",
    "pending": "planned",
    "in_progress": "in-progress",
    "in-progress": "in-progress",
    "checking": "checking",
    "review": "checking",
    "completed": "done",
    "done": "done",
    "blocked": "blocked",
    "cancelled": "cancelled",
}

_SIDECAR_KEYS = frozenset(
    {
        "schema_version",
        "source_path",
        "source_sha256",
        "original",
        "redacted_paths",
        "parse_status",
    }
)
_DECISIONS = frozenset({"share", "redact"})

# Legacy task.json keys that have no authoritative current frontmatter
# meaning. They live only inside the sidecar original snapshot; a migrated
# frontmatter must not silently absorb them as extension data. (id, status,
# parent and branch are owned current fields and are checked for equality.)
_LEGACY_ONLY_KEYS = frozenset(
    {
        "name",
        "title",
        "description",
        "createdAt",
        "completedAt",
        "cancelledAt",
        "base_branch",
        "subtasks",
        "children",
        "meta",
        "dev_type",
        "scope",
        "package",
        "priority",
        "creator",
        "assignee",
        "worktree_path",
        "commit",
        "pr_url",
        "relatedFiles",
        "notes",
    }
)

_CURRENT_FRONTMATTER_FIELDS = frozenset(
    {
        "schema_version",
        "id",
        "workflow_mode",
        "mode_source",
        "mode_note",
        "status",
        "parent",
        "branch",
        "created_at",
        "updated_at",
        "completed_at",
        "blocked_reason",
    }
)


_IDENTITY_KEY = re.compile(r"^[a-z][a-z0-9_]*=")
_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ARCHIVE_SEGMENT = "archive"
_TASK_JSON_NAME = "task.json"

# Canonical uncertainty wording when a legacy blocked record carries no
# reason; it describes the missing evidence, never a guessed cause.
_BLOCKED_REASON_MISSING = "legacy task.json status=blocked; reason not recorded"
_BLOCKED_REASON_REDACTED = "legacy task.json status=blocked; reason redacted"

__all__ = [
    "TaskProjection",
    "read_legacy_identity",
    "validate_projection_graph",
    "validate_task_projection",
]


# ---------------------------------------------------------------------------
# Strict, lossless legacy JSON decoding (floats preserved, finite only)
# ---------------------------------------------------------------------------


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(
                "duplicate-key", "legacy JSON object has a duplicate key"
            )
        result[key] = value
    return result


def _reject_constant(_text: str) -> Any:
    raise ContractError("non-finite-number", "legacy JSON literal is not finite")


def _parse_float(text: str) -> Decimal:
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ContractError(
            "invalid-number", "legacy JSON number cannot be represented losslessly"
        ) from None
    if not value.is_finite():
        raise ContractError("non-finite-number", "legacy JSON number is not finite")
    return value


def _decode_legacy(raw: bytes, label: str) -> Any:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ContractError("invalid-utf8", f"{label} is not strict UTF-8") from None
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=_parse_float,
            parse_constant=_reject_constant,
        )
    except ContractError:
        raise
    except (ValueError, RecursionError):
        raise ContractError(
            "invalid-json", f"{label} is not well-formed JSON"
        ) from None


def _typed_equal(left: Any, right: Any) -> bool:
    """Exact JSON value/type equality, with non-integral numbers kept decimal."""
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, int) or isinstance(right, int):
        return (
            isinstance(left, int)
            and not isinstance(left, bool)
            and isinstance(right, int)
            and not isinstance(right, bool)
            and left == right
        )
    if isinstance(left, Decimal) or isinstance(right, Decimal):
        return (
            isinstance(left, Decimal) and isinstance(right, Decimal) and left == right
        )
    if isinstance(left, str) or isinstance(right, str):
        return isinstance(left, str) and isinstance(right, str) and left == right
    if isinstance(left, list) or isinstance(right, list):
        return (
            isinstance(left, list)
            and isinstance(right, list)
            and len(left) == len(right)
            and all(_typed_equal(a, b) for a, b in zip(left, right))
        )
    if isinstance(left, dict) or isinstance(right, dict):
        return (
            isinstance(left, dict)
            and isinstance(right, dict)
            and left.keys() == right.keys()
            and all(_typed_equal(left[key], right[key]) for key in left)
        )
    return False


# ---------------------------------------------------------------------------
# Legacy developer identity
# ---------------------------------------------------------------------------


def read_legacy_identity(raw: bytes) -> str:
    """Extract the one original name from a legacy ``.trellis/.developer``.

    Other fixed-format ``key=value`` metadata (e.g. ``initialized_at``) is
    accepted and left to the private original; the name is returned
    unmodified and must satisfy the shared ``validate_developer_name``.
    Duplicate keys, an invalid name or unparseable lines are rejected.
    """
    try:
        text = raw.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise ContractError(
            "invalid-legacy-identity", "legacy identity is not strict UTF-8"
        ) from None
    declarations = [
        line for line in text.splitlines() if line and not line.startswith("#")
    ]
    seen: set[str] = set()
    names: list[str] = []
    for line in declarations:
        if not _IDENTITY_KEY.match(line):
            raise ContractError(
                "invalid-legacy-identity",
                "legacy identity metadata is not in fixed key=value form",
            )
        key, _, value = line.partition("=")
        if key in seen:
            raise ContractError(
                "invalid-legacy-identity", "legacy identity repeats a metadata key"
            )
        seen.add(key)
        if key == "name":
            names.append(value)
    if not names:
        raise ContractError(
            "invalid-legacy-identity", "legacy identity has no name= declaration"
        )
    try:
        return validate_developer_name(names[0])
    except (argparse.ArgumentTypeError, TypeError):
        raise ContractError(
            "invalid-legacy-identity",
            "legacy identity name does not satisfy the current name rule",
        ) from None


# ---------------------------------------------------------------------------
# Safe project-relative source paths and JSON Pointers
# ---------------------------------------------------------------------------


def _check_safe_relative_path(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value:
        raise ContractError("invalid-source-path", f"{label} is not a path string")
    if value.startswith(("/", "~")) or re.match(r"^[A-Za-z]:", value):
        raise ContractError(
            "invalid-source-path", f"{label} must be a project-relative path"
        )
    if "\\" in value or value.endswith("/"):
        raise ContractError(
            "invalid-source-path", f"{label} must use normalized posix separators"
        )
    parts = tuple(value.split("/"))
    for part in parts:
        if part in ("", ".", "..") or any(
            ord(char) < 0x20 or 0x7F <= ord(char) <= 0x9F for char in part
        ):
            raise ContractError(
                "invalid-source-path", f"{label} contains an unsafe path segment"
            )
    return parts


def _check_source_path(source_path: Any) -> tuple[str, ...]:
    parts = _check_safe_relative_path(source_path, "legacy source path")
    if len(parts) < 2 or parts[-1] != _TASK_JSON_NAME:
        raise ContractError(
            "invalid-source-path",
            "legacy source path must be a task.json inside its task directory",
        )
    return parts


def _unescape_pointer_segment(segment: str) -> str:
    index = 0
    out: list[str] = []
    while index < len(segment):
        char = segment[index]
        if char == "~":
            if segment[index : index + 2] == "~0":
                out.append("~")
                index += 2
                continue
            if segment[index : index + 2] == "~1":
                out.append("/")
                index += 2
                continue
            raise ContractError(
                "invalid-redaction", "redacted_paths entry is not a valid JSON Pointer"
            )
        out.append(char)
        index += 1
    return "".join(out)


def _pointer_segments(pointer: Any) -> tuple[str, ...]:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ContractError(
            "invalid-redaction", "redacted_paths entry is not a valid JSON Pointer"
        )
    return tuple(_unescape_pointer_segment(part) for part in pointer[1:].split("/"))


def _resolve_list_index(segment: str, length: int) -> int:
    if not re.fullmatch(r"0|[1-9][0-9]*", segment):
        raise ContractError(
            "invalid-redaction", "redacted_paths array index is not canonical"
        )
    index = int(segment)
    if index >= length:
        raise ContractError(
            "invalid-redaction", "redacted_paths entry does not resolve in the source"
        )
    return index


def _null_at(root: Any, segments: tuple[str, ...]) -> None:
    current = root
    for segment in segments[:-1]:
        if isinstance(current, dict):
            if segment not in current:
                break
            current = current[segment]
        elif isinstance(current, list):
            current = current[_resolve_list_index(segment, len(current))]
        else:
            break
    else:
        last = segments[-1]
        if isinstance(current, dict):
            if last not in current:
                raise ContractError(
                    "invalid-redaction",
                    "redacted_paths entry does not resolve in the source",
                )
            current[last] = None
            return
        if isinstance(current, list):
            current[_resolve_list_index(last, len(current))] = None
            return
    raise ContractError(
        "invalid-redaction", "redacted_paths entry does not resolve in the source"
    )


def _apply_redactions(source: Any, redacted_paths: list[Any]) -> Any:
    import copy

    redacted = copy.deepcopy(source)
    segments = [_pointer_segments(pointer) for pointer in redacted_paths]
    canonical = sorted(segments)
    for earlier, later in itertools.pairwise(canonical):
        if earlier == later:
            raise ContractError(
                "invalid-redaction", "redacted_paths contains a duplicate pointer"
            )
        if len(later) > len(earlier) and later[: len(earlier)] == earlier:
            raise ContractError(
                "invalid-redaction", "redacted_paths contains overlapping pointers"
            )
    for path in segments:
        _null_at(redacted, path)
    return redacted


# ---------------------------------------------------------------------------
# Legacy field semantics
# ---------------------------------------------------------------------------


def _legacy_id(source: dict[str, Any]) -> str:
    identity = source.get("id")
    if not isinstance(identity, str) or not identity:
        raise ContractError(
            "invalid-legacy-task", "legacy task has no unambiguous string id"
        )
    name = source.get("name", identity)
    if not isinstance(name, str) or name != identity:
        raise ContractError("invalid-legacy-task", "legacy task id and name disagree")
    return identity


def _legacy_status(source: dict[str, Any]) -> str:
    status = source.get("status")
    if not isinstance(status, str) or status not in _STATUS_MAP:
        raise ContractError(
            "invalid-legacy-task", "legacy task status is not migratable truthfully"
        )
    return _STATUS_MAP[status]


def _legacy_timestamp(source: dict[str, Any], field: str) -> str | None:
    """Map one legacy time field to a provable RFC3339 value or None.

    Date-only values keep their day granularity: they never become fabricated
    timezone-aware moments, so the current field must stay null. Anything
    that is neither a real calendar date nor a real timezone-aware timestamp
    is an unknown time fact and blocks the projection.
    """
    value = source.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ContractError(
            "invalid-legacy-task", f"legacy task {field} is not a string or null"
        )
    if _DATE_ONLY.fullmatch(value):
        try:
            date.fromisoformat(value)
        except ValueError:
            raise ContractError(
                "invalid-legacy-task", f"legacy task {field} is not a real date"
            ) from None
        return None
    if _RFC3339.fullmatch(value):
        candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            datetime.fromisoformat(candidate)
        except ValueError:
            raise ContractError(
                "invalid-legacy-task",
                f"legacy task {field} is not a real calendar/timezone value",
            ) from None
        return value
    raise ContractError(
        "invalid-legacy-task", f"legacy task {field} has unknown time semantics"
    )


# Terminal statuses with a provable legacy terminal time. A date-only
# completedAt still proves its calendar quarter for done (characterized
# legacy behavior); cancelled uses its validated publishable event, so an
# imported record re-archives to the same bucket that event implies.
# Redacted or unproven cancellation times are undated. The old archive
# directory name is never a time proof.
_ARCHIVE_TIME_FIELDS = {"done": "completedAt", "cancelled": "cancelledAt"}


def _archive_bucket(
    source: dict[str, Any], status: str, document: TaskDocument
) -> str | None:
    field = _ARCHIVE_TIME_FIELDS.get(status)
    if field is None:
        return None
    if status == "cancelled":
        event_at = document.events[0]["at"]
        timestamp = None if event_at == "unknown" else event_at
    else:
        value = source.get(field)
        timestamp = (
            value
            if isinstance(value, str) and _DATE_ONLY.fullmatch(value)
            else _legacy_timestamp(source, field)
        )
    if timestamp is None:
        return "undated"
    month = int(timestamp[5:7])
    return f"{timestamp[:4]}-Q{(month - 1) // 3 + 1}"


def _legacy_parent(source: dict[str, Any]) -> str | None:
    parent = source.get("parent")
    if parent is None:
        return None
    if not isinstance(parent, str) or not parent:
        raise ContractError(
            "invalid-legacy-task", "legacy task parent is not a reference string"
        )
    return parent


def _legacy_children(source: dict[str, Any]) -> tuple[str, ...]:
    # ``subtasks`` is the legacy spelling of ``children``; both are lists of
    # directory-name references and a repaired null reads as an empty list.
    combined: list[str] = []
    for field in ("children", "subtasks"):
        values = source.get(field)
        if values is None:
            continue
        if not isinstance(values, list):
            raise ContractError(
                "invalid-legacy-task", f"legacy task {field} is not a reference list"
            )
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, str) or not value:
                raise ContractError(
                    "invalid-legacy-task",
                    f"legacy task {field} entry is not a reference string",
                )
            if value in seen:
                raise ContractError(
                    "invalid-legacy-task",
                    f"legacy task {field} repeats a child reference",
                )
            seen.add(value)
            if value not in combined:
                combined.append(value)
    return tuple(combined)


def _legacy_branch(source: dict[str, Any]) -> str | None:
    branch = source.get("branch")
    if branch is None:
        return None
    if not isinstance(branch, str) or not branch:
        raise ContractError(
            "invalid-legacy-task", "legacy task branch is not a string or null"
        )
    return branch


def _blocked_suspension(source: dict[str, Any]) -> dict[str, Any] | None:
    """Return the recorded ``meta.suspension`` object of a legacy blocked task.

    The old observed shape carries state/reason/since/resumeWhen; only the
    reason string and the since time are provable current facts, so
    state/resumeWhen stay sidecar/private truth and are never read here.
    A present but non-object suspension is malformed metadata, not evidence.
    """
    meta = source.get("meta")
    if not isinstance(meta, dict):
        return None
    suspension = meta.get("suspension")
    if suspension is None:
        return None
    if not isinstance(suspension, dict):
        raise ContractError(
            "invalid-legacy-task", "legacy suspension metadata is malformed"
        )
    return suspension


def _blocked_reason(source: dict[str, Any]) -> str:
    """Derive the one truthful blocked reason from recorded legacy evidence.

    A supplied top-level ``blocked_reason`` and ``meta.suspension.reason``
    must each be non-blank strings and must agree; contradictory or
    malformed supplied reasons block the projection. When no reason was
    recorded, the canonical uncertainty text describes the missing evidence
    instead of guessing a cause.
    """
    supplied: list[str] = []
    containers: tuple[dict[str, Any], ...] = (source,)
    suspension = _blocked_suspension(source)
    if suspension is not None:
        containers = (source, suspension)
    for container, field in zip(containers, ("blocked_reason", "reason")):
        value = container.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise ContractError(
                "invalid-legacy-task",
                "a supplied legacy blocked reason is malformed",
            )
        if value not in supplied:
            supplied.append(value)
    if len(supplied) > 1:
        raise ContractError(
            "invalid-legacy-task", "recorded legacy blocked reasons contradict"
        )
    return supplied[0] if supplied else _BLOCKED_REASON_MISSING


def _blocked_since(source: dict[str, Any]) -> str | None:
    """Provable suspension start from ``meta.suspension.since`` or None.

    Shares the legacy time rule: an RFC3339 value is provable, a date-only
    or missing value is unknown, anything else is malformed. The recovery
    phase stays unknown; no resume history is ever derived here.
    """
    suspension = _blocked_suspension(source)
    if suspension is None:
        return None
    return _legacy_timestamp(suspension, "since")


def _redacts_field(
    sidecar: dict[str, Any], decision: str, path: tuple[str, ...]
) -> bool:
    """A validated redaction also covers newly derived optional task details."""
    if decision != "redact":
        return False
    for pointer in sidecar["redacted_paths"]:
        if pointer == "":
            return True
        segments = _pointer_segments(pointer)
        if path[: len(segments)] == segments:
            return True
    return False


def _projected_blocked_reason(
    source: dict[str, Any], sidecar: dict[str, Any], decision: str
) -> str:
    reason = _blocked_reason(source)
    if source.get("blocked_reason") is not None and _redacts_field(
        sidecar, decision, ("blocked_reason",)
    ):
        return _BLOCKED_REASON_REDACTED
    suspension = _blocked_suspension(source)
    if (
        suspension is not None
        and suspension.get("reason") is not None
        and _redacts_field(sidecar, decision, ("meta", "suspension", "reason"))
    ):
        return _BLOCKED_REASON_REDACTED
    return reason


# ---------------------------------------------------------------------------
# Sidecar (legacy-task.json) privacy and preservation checks
# ---------------------------------------------------------------------------


def _check_sidecar_shape(sidecar: Any) -> dict[str, Any]:
    if not isinstance(sidecar, dict) or set(sidecar.keys()) != _SIDECAR_KEYS:
        raise ContractError(
            "invalid-sidecar", "legacy-task.json must carry exactly the six fixed keys"
        )
    version = sidecar["schema_version"]
    if type(version) is not int or version != 1:
        raise ContractError(
            "invalid-sidecar", "legacy-task.json schema_version must be 1"
        )
    if sidecar["parse_status"] != "valid":
        raise ContractError(
            "invalid-sidecar",
            "legacy-task.json marks the original invalid; the task cannot "
            "migrate as a normal task",
        )
    digest = sidecar["source_sha256"]
    if digest is not None and (
        not isinstance(digest, str) or not _SHA256.fullmatch(digest)
    ):
        raise ContractError(
            "invalid-sidecar", "legacy-task.json source_sha256 is not lowercase hex"
        )
    if not isinstance(sidecar["redacted_paths"], list) or not all(
        isinstance(pointer, str) for pointer in sidecar["redacted_paths"]
    ):
        raise ContractError(
            "invalid-sidecar", "legacy-task.json redacted_paths must be pointer strings"
        )
    return sidecar


def _check_snapshot(
    sidecar: dict[str, Any],
    source: dict[str, Any],
    source_raw: bytes,
    source_path: str,
    decision: str,
) -> None:
    declared_path = sidecar["source_path"]
    if declared_path is not None:
        if not isinstance(declared_path, str) or declared_path != source_path:
            raise ContractError(
                "invalid-sidecar",
                "legacy-task.json source_path does not match the actual source",
            )
        _check_safe_relative_path(declared_path, "legacy-task.json source_path")
    redacted_paths = sidecar["redacted_paths"]
    original = sidecar["original"]
    if decision == "share":
        if redacted_paths:
            raise ContractError(
                "privacy-violation", "a share decision cannot declare redactions"
            )
        if not _typed_equal(source, original):
            raise ContractError(
                "preservation-failure",
                "shared snapshot does not preserve the original exactly",
                exit_code=3,
            )
        if declared_path is None:
            if sidecar["source_sha256"] is not None:
                raise ContractError(
                    "privacy-violation",
                    "a private source path forbids publishing the raw hash",
                )
        elif sidecar["source_sha256"] != hashlib.sha256(source_raw).hexdigest():
            raise ContractError(
                "preservation-failure",
                "shared raw hash does not match the original bytes",
                exit_code=3,
            )
        return
    # redact: the raw hash is never published under any redaction form.
    if sidecar["source_sha256"] is not None:
        raise ContractError(
            "privacy-violation", "a redact decision forbids publishing the raw hash"
        )
    if "" in redacted_paths:
        if redacted_paths != [""] or original is not None:
            raise ContractError(
                "invalid-redaction",
                'root-private form is exactly redacted_paths [""] with null original',
            )
        return
    if original is None:
        raise ContractError(
            "invalid-redaction", "a null original requires the root-private form"
        )
    expected = _apply_redactions(source, redacted_paths)
    if not _typed_equal(expected, original):
        raise ContractError(
            "preservation-failure",
            "redacted snapshot differs from the original beyond the declared "
            "null positions",
            exit_code=3,
        )


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TaskProjection:
    """One verified legacy task bound to its migrated task document.

    ``legacy_id`` is the original logical id (the bare slug). ``parent`` and
    ``children`` carry the *original* legacy references (full directory
    names), never inferred from path nesting; ``validate_projection_graph``
    resolves them through ``aliases`` (the actual source folder name when it
    differs from ``legacy_id``) and checks the document's frontmatter parent
    against the resolved parent's logical id. ``document`` is the validated
    current TaskDocument; it is not a second state source.
    """

    legacy_id: str
    parent: str | None
    children: tuple[str, ...]
    document: TaskDocument
    aliases: tuple[str, ...] = ()
    archive_bucket: str | None = None


def _check_time_provenance(document: TaskDocument) -> None:
    from markdown_it import MarkdownIt

    _, _, body_start = _frontmatter_bounds(document.text)
    blocks = [
        token.content
        for token in MarkdownIt("commonmark").parse(document.text[body_start:])
        if token.type == "fence"
        and token.level == 0
        and token.info.strip() == "sbtd-legacy-time-provenance"
    ]
    sources = {
        "created_at": "legacy task.json: createdAt (sidecar or private original)",
        "updated_at": "legacy task.json: no recorded update time",
        "completed_at": "legacy task.json: completedAt (sidecar or private original)",
    }
    expected = {
        field: {"source": source, "status": "unproven"}
        for field, source in sources.items()
        if document.frontmatter[field] is None
    }
    if (
        len(blocks) != 1
        or _decode_legacy(blocks[0].encode("utf-8"), "legacy timestamp provenance")
        != expected
    ):
        raise ContractError(
            "invalid-task-document",
            "unproven legacy times need the source-bound timestamp provenance block",
        )


def _check_document(
    document: TaskDocument,
    source: dict[str, Any],
    identity: str,
    status: str,
    parent: str | None,
    branch: str | None,
    *,
    sidecar: dict[str, Any],
    decision: str,
) -> None:
    frontmatter = document.frontmatter
    if _LEGACY_ONLY_KEYS & frontmatter.keys():
        raise ContractError(
            "invalid-task-document",
            "migrated frontmatter must not carry legacy-only field spellings",
        )
    if (source.keys() & frontmatter.keys()) - _CURRENT_FRONTMATTER_FIELDS:
        raise ContractError(
            "invalid-task-document",
            "migrated frontmatter must not absorb unmapped legacy source fields",
        )
    if frontmatter["id"] != identity:
        raise ContractError(
            "invalid-task-document", "migrated task id does not match the legacy id"
        )
    if frontmatter["status"] != status:
        raise ContractError(
            "invalid-task-document",
            "migrated task status does not match the mapped legacy status",
        )
    if (
        frontmatter["workflow_mode"] is not None
        or frontmatter["mode_source"] != "migration-unknown"
        or frontmatter["mode_note"] != "legacy Trellis task without mode proof"
    ):
        raise ContractError(
            "invalid-task-document",
            "a legacy task without mode proof requires null mode, "
            "migration-unknown source and the canonical migration mode note",
        )
    declared_parent = frontmatter.get("parent")
    if parent is None:
        if declared_parent is not None:
            raise ContractError(
                "invalid-task-document",
                "migrated parent must not be inferred without legacy metadata",
            )
    elif not isinstance(declared_parent, str):
        raise ContractError(
            "invalid-task-document",
            "migrated parent must name the resolved legacy parent",
        )
    if frontmatter["branch"] != branch:
        raise ContractError(
            "invalid-task-document", "migrated branch does not match the legacy branch"
        )
    created_at = _legacy_timestamp(source, "createdAt")
    completed_at = _legacy_timestamp(source, "completedAt")
    if status != "done" and source.get("completedAt") is not None:
        raise ContractError(
            "invalid-legacy-task",
            "an unfinished legacy task cannot carry a completion time",
        )
    if frontmatter["created_at"] != created_at:
        raise ContractError(
            "invalid-task-document",
            "migrated created_at does not match the provable legacy time",
        )
    if frontmatter["completed_at"] != completed_at:
        raise ContractError(
            "invalid-task-document",
            "migrated completed_at does not match the provable legacy time",
        )
    if frontmatter["updated_at"] is not None:
        raise ContractError(
            "invalid-task-document",
            "legacy tasks have no provable update time; updated_at stays null",
        )
    _check_time_provenance(document)
    events = document.events
    if status == "blocked":
        expected_reason = _projected_blocked_reason(source, sidecar, decision)
        if frontmatter.get("blocked_reason") != expected_reason:
            raise ContractError(
                "invalid-task-document",
                "migrated blocked_reason does not match its publishable legacy value",
            )
    # Each proven terminal/blocked status carries exactly one canonical
    # historical fact event; other statuses have no provable history at all.
    fact: tuple[str, str | None, str, str, str] | None = None
    if status == "done":
        fact = (
            "done", completed_at, "legacy completion fact", "completed", "completion"
        )
    elif status == "cancelled":
        # completed_at stays null; a provable cancelledAt timestamps the
        # cancellation event, a missing/date-only one stays unknown.
        fact = (
            "cancelled",
            _legacy_timestamp(source, "cancelledAt"),
            "legacy cancellation fact",
            "cancelled",
            "cancellation",
        )
    elif status == "blocked":
        fact = (
            "blocked",
            _blocked_since(source),
            "legacy blocked fact",
            "blocked",
            "blocked",
        )
    if fact is None:
        if events:
            raise ContractError(
                "invalid-task-document",
                "an unfinished legacy task has no provable state history",
            )
        return
    to, proven_at, reason, adjective, noun = fact
    if status in ("cancelled", "blocked"):
        if (
            created_at is not None
            and proven_at is not None
            and datetime.fromisoformat(proven_at.replace("Z", "+00:00"))
            < datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        ):
            raise ContractError(
                "invalid-legacy-task", "legacy status time precedes its creation"
            )
        creation_day = source.get("createdAt")
        if (
            created_at is None
            and isinstance(creation_day, str)
            and _DATE_ONLY.fullmatch(creation_day)
            and proven_at is not None
            and proven_at[:10] < creation_day
        ):
            raise ContractError(
                "invalid-legacy-task", "legacy status day precedes its creation day"
            )
        time_path = (
            ("cancelledAt",)
            if status == "cancelled"
            else ("meta", "suspension", "since")
        )
        if _redacts_field(sidecar, decision, time_path):
            proven_at = None
    if len(events) != 1:
        raise ContractError(
            "invalid-task-document",
            f"a {adjective} legacy task needs exactly its {noun} record event",
        )
    event = events[0]
    if event["from"] != "unknown" or event["to"] != to:
        raise ContractError(
            "invalid-task-document",
            f"legacy {noun} history is only recorded as unknown -> {to}",
        )
    if event["at"] != (proven_at if proven_at is not None else "unknown"):
        raise ContractError(
            "invalid-task-document",
            f"legacy {noun} event time must be the provable time or unknown",
        )
    if event["reason"] != reason or event["evidence"] != "legacy task.json status":
        raise ContractError(
            "invalid-task-document",
            f"legacy {noun} history must cite the source {noun} fact",
        )


def validate_task_projection(
    source_raw: bytes,
    task_raw: bytes,
    sidecar_raw: bytes,
    *,
    source_path: str,
    decision: str,
) -> TaskProjection:
    """Validate one legacy task.json, its migrated task.md and sidecar.

    ``source_raw`` is the private truth: parse status, field semantics and
    history are always verified against it. The six-key legacy-task.json
    sidecar must bind the actual source path, keep the raw hash invisible
    under any redaction/private path/unparseable source, and prove the
    shared ``original`` snapshot loses nothing beyond the declared JSON
    Pointer null redactions (or the root-private form). The migrated
    TaskDocument must carry the mapped identity/status/mode/parent/branch/
    time semantics and no fabricated history.
    """
    if decision not in _DECISIONS:
        raise ContractError("invalid-argument", "decision must be share or redact")
    parts = _check_source_path(source_path)
    source = _decode_legacy(source_raw, "legacy task")
    if not isinstance(source, dict):
        raise ContractError("invalid-legacy-task", "legacy task.json is not an object")
    sidecar = _check_sidecar_shape(_decode_legacy(sidecar_raw, "legacy-task.json"))
    _check_snapshot(sidecar, source, source_raw, source_path, decision)
    try:
        text = task_raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ContractError(
            "invalid-task-document", "migrated task document is not strict UTF-8"
        ) from None
    try:
        document = TaskDocument.parse(text)
    except TaskDataError as error:
        raise ContractError("invalid-task-document", error.reason) from None
    identity = _legacy_id(source)
    status = _legacy_status(source)
    if status not in ("done", "cancelled") and _ARCHIVE_SEGMENT in parts[:-1]:
        raise ContractError(
            "invalid-legacy-task",
            "an archived-position task without a proven terminal state is blocked",
        )
    parent = _legacy_parent(source)
    children = _legacy_children(source)
    branch = _legacy_branch(source)
    _check_document(
        document, source, identity, status, parent, branch,
        sidecar=sidecar, decision=decision,
    )
    folder = parts[-2]
    relative_folder = "/".join(parts[2:-1])
    aliases = tuple(
        dict.fromkeys(
            name for name in (folder, relative_folder) if name and name != identity
        )
    )
    bucket = (
        _archive_bucket(source, status, document)
        if _ARCHIVE_SEGMENT in parts[2:-1] else None
    )
    return TaskProjection(identity, parent, children, document, aliases, bucket)


# ---------------------------------------------------------------------------
# Batch relationship graph
# ---------------------------------------------------------------------------


def _resolve(
    reference: str, names: Mapping[str, TaskProjection], rule: str
) -> TaskProjection:
    projection = names.get(reference)
    if projection is None:
        raise ContractError("graph-conflict", rule)
    return projection


def validate_projection_graph(projections: Mapping[str, TaskProjection]) -> None:
    """Validate one batch of projections against the actual old relationships.

    Logical identity is unique, every parent/children reference resolves
    through real legacy names (directory nesting is never a substitute),
    both sides of each link agree, and the parent graph is acyclic.
    """
    names: dict[str, TaskProjection] = {}
    for key, projection in projections.items():
        if key != projection.legacy_id:
            raise ContractError(
                "graph-conflict", "projection mapping key must be the legacy id"
            )
        for name in (projection.legacy_id, *projection.aliases):
            owner = names.get(name)
            if owner is not None and owner is not projection:
                raise ContractError(
                    "graph-conflict", "two legacy tasks claim the same name"
                )
            names[name] = projection
    parents: dict[str, TaskProjection | None] = {}
    for projection in projections.values():
        reference = projection.parent
        if reference is None:
            parents[projection.legacy_id] = None
            continue
        parent = _resolve(
            reference, names, "legacy task parent reference cannot be resolved"
        )
        if parent is projection:
            raise ContractError("graph-conflict", "legacy task is its own parent")
        declared = projection.document.frontmatter.get("parent")
        if declared != parent.legacy_id:
            raise ContractError(
                "graph-conflict",
                "migrated parent does not match the resolved legacy parent",
            )
        parents[projection.legacy_id] = parent
    for projection in projections.values():
        resolved_children: set[str] = set()
        for reference in projection.children:
            child = _resolve(
                reference, names, "legacy task child reference cannot be resolved"
            )
            if child.legacy_id in resolved_children:
                raise ContractError(
                    "graph-conflict", "legacy task repeats a resolved child"
                )
            resolved_children.add(child.legacy_id)
            if parents.get(child.legacy_id) is not projection:
                raise ContractError(
                    "graph-conflict",
                    "legacy parent/children references disagree between tasks",
                )
        for other in projections.values():
            if (
                parents.get(other.legacy_id) is projection
                and other.legacy_id not in resolved_children
            ):
                raise ContractError(
                    "graph-conflict",
                    "legacy parent/children references disagree between tasks",
                )
    # Cycle check over the resolved parent edges.
    for projection in projections.values():
        seen: set[str] = set()
        current = parents.get(projection.legacy_id)
        while current is not None:
            if current.legacy_id in seen:
                raise ContractError(
                    "graph-conflict", "legacy parent relationships contain a cycle"
                )
            seen.add(current.legacy_id)
            current = parents.get(current.legacy_id)
