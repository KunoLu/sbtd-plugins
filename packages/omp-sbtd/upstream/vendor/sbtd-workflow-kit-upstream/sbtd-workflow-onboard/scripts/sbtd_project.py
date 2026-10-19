"""Read-only minimal project state inspection for SBTD onboarding.

Scope: inspect only the optional known state containers of one project:

- the ``.sbtd/active-task.json`` pointer and the task record it selects,
- the fixed explicit bootstrap record ``ai/tasks/00-bootstrap-guidelines/task.md``,
- the presence of legacy ``.trellis`` state (never read within it).

Every result carries ``validationScope="selected-state-shape-and-containment"``:
this module proves only selected-state shape and physical containment. It is
not task recovery, branch rebinding, full parent/event history validation or
workflow acceptance evidence; those belong to the dedicated migration and
recovery work. It never writes, never runs subprocesses and never prints.
Missing optional state is reported as success and is not treated as evidence
of initialization; malformed selected state is reported, never rebuilt or
overwritten. Error strings are fixed and sanitized: task bodies and private
extension values are never echoed.
"""

from __future__ import annotations

import json
import math
import os
import stat
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, TypedDict

__all__ = [
    "StateInspection",
    "TaskDataError",
    "TaskSummary",
    "inspect_project_state",
    "open_regular_file",
    "parse_active_pointer",
    "parse_task_frontmatter",
    "require_dependency",
    "validate_json_compatible",
    "validate_task_data",
    "validate_task_timestamps",
]


class TaskSummary(TypedDict):
    relativePath: str
    id: str
    status: str
    workflowMode: str | None


class StateInspection(TypedDict):
    status: str
    reason: str
    nextStep: str
    validationScope: str
    activeTask: TaskSummary | None
    bootstrapTask: TaskSummary | None
    legacyPresent: bool | None


VALIDATION_SCOPE = "selected-state-shape-and-containment"

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "templates"
    / "skills"
    / "sbtd-task"
    / "references"
    / "task-data.schema.json"
)
_POINTER_PATH = ".sbtd/active-task.json"
_BOOTSTRAP_PATH = "ai/tasks/00-bootstrap-guidelines/task.md"
_LEGACY_PATH = ".trellis"
_TASK_ROOTS = (".sbtd/tasks", "ai/tasks")
_ARCHIVE_PREFIXES = tuple(root + "/archive/" for root in _TASK_ROOTS)
_TASK_MD_SUFFIX = "/task.md"
_TIMESTAMP_FIELDS = ("created_at", "updated_at", "completed_at")

_ROOT_NEXT = "verify the selected project path before running onboarding checks"
_REPAIR_NEXT = (
    "preserve the original record and resolve its malformed state explicitly; "
    "onboarding never rebuilds or overwrites task data"
)
_CONTAINMENT_NEXT = (
    "replace the link with real in-project state or fix the recorded path; "
    "onboarding never follows links that escape the project task roots"
)
_MISSING_TARGET_NEXT = (
    "select an existing task or clear the stale pointer explicitly; "
    "onboarding never recreates recorded task files"
)
_DEPENDENCY_NEXT = (
    "install the declared sbtd-workflow-onboard requirements "
    "(PyYAML>=6.0.3,<7, jsonschema>=4.20,<5) before running project state checks"
)
_SCHEMA_REPAIR_NEXT = (
    "restore sbtd-workflow-onboard/templates/skills/sbtd-task/references/task-data.schema.json"
)



class TaskDataError(Exception):
    """A fixed, sanitized inspection failure; never carries file content."""

    def __init__(self, reason: str, next_step: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.next_step = next_step


def _result(
    status: str,
    reason: str,
    next_step: str,
    active_task: TaskSummary | None = None,
    bootstrap_task: TaskSummary | None = None,
    legacy_present: bool | None = False,
) -> StateInspection:
    return {
        "status": status,
        "reason": reason,
        "nextStep": next_step,
        "validationScope": VALIDATION_SCOPE,
        "activeTask": active_task,
        "bootstrapTask": bootstrap_task,
        "legacyPresent": legacy_present,
    }


def require_dependency(module_name: str, package: str) -> Any:
    """Import a declared dependency lazily and report its absence."""
    try:
        return __import__(module_name)
    except ImportError:
        raise TaskDataError(
            f"required dependency {package} is not installed in the onboarding environment",
            _DEPENDENCY_NEXT,
        ) from None


def _bundled_schema() -> dict[str, Any]:
    try:
        raw = _SCHEMA_PATH.read_bytes()
    except OSError:
        raise TaskDataError(
            "the bundled task-data schema is missing or unreadable",
            _SCHEMA_REPAIR_NEXT,
        ) from None
    try:
        loaded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise TaskDataError(
            "the bundled task-data schema is invalid", _SCHEMA_REPAIR_NEXT
        ) from None
    if not isinstance(loaded, dict):
        raise TaskDataError(
            "the bundled task-data schema is invalid", _SCHEMA_REPAIR_NEXT
        )
    return loaded



def validate_task_data(data: object, definition: str, label: str) -> dict[str, Any]:
    jsonschema = require_dependency("jsonschema", "jsonschema")
    from referencing.exceptions import Unresolvable
    schema = {**_bundled_schema(), "$ref": f"#/$defs/{definition}"}
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
        valid = isinstance(data, dict) and validator.is_valid(data)
    except (jsonschema.exceptions.SchemaError, Unresolvable):
        raise TaskDataError(
            "the bundled task-data schema is invalid", _SCHEMA_REPAIR_NEXT
        ) from None
    if not valid:
        raise TaskDataError(
            f"{label} fails the bundled {definition} schema",
            _REPAIR_NEXT,
        )
    return data



def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _is_windows_reparse_point(metadata: object) -> bool:
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(flag and getattr(metadata, "st_file_attributes", 0) & flag)


def _reject_windows_reparse_points(path: Path, label: str) -> None:
    current = path
    while True:
        if _is_windows_reparse_point(current.lstat()):
            raise TaskDataError(
                f"{label} contains a Windows reparse point", _CONTAINMENT_NEXT
            )
        if current.parent == current:
            return
        current = current.parent


def _resolve_contained_file(
    root_real: Path,
    relative: str,
    label: str,
    allowed_roots: tuple[Path, ...] | None,
    missing_reason: str | None,
) -> Path | None:
    """Resolve ``relative`` proving physical containment before any read.

    Every component is checked, parent symlinks must stay inside the project
    and the final regular file must resolve under the allowed local/shared
    task roots when given. Returns ``None`` only when a component is simply
    absent and ``missing_reason`` is ``None``; a dangling link, escape, wrong
    type or permission failure is always a problem, never an absence.
    """
    current = root_real
    for part in PurePosixPath(relative).parts:
        candidate = current / part
        try:
            metadata = candidate.lstat()
            mode = metadata.st_mode
        except FileNotFoundError:
            if missing_reason is None:
                return None
            raise TaskDataError(missing_reason, _MISSING_TARGET_NEXT) from None
        except PermissionError:
            raise TaskDataError(
                f"{label} cannot be inspected (permission denied)", _REPAIR_NEXT
            ) from None
        except OSError:
            raise TaskDataError(f"{label} cannot be inspected", _REPAIR_NEXT) from None
        if _is_windows_reparse_point(metadata):
            raise TaskDataError(
                f"{label} contains a Windows reparse point", _CONTAINMENT_NEXT
            )
        if stat.S_ISLNK(mode):
            try:
                resolved = candidate.resolve(strict=True)
            except FileNotFoundError:
                raise TaskDataError(
                    f"{label} is a dangling symlink", _CONTAINMENT_NEXT
                ) from None
            except RuntimeError:
                raise TaskDataError(
                    f"{label} is a symlink loop", _CONTAINMENT_NEXT
                ) from None
            except OSError:
                raise TaskDataError(
                    f"{label} cannot be inspected", _REPAIR_NEXT
                ) from None
            if not _is_within(resolved, root_real):
                raise TaskDataError(
                    f"{label} is a symlink that escapes the project root",
                    _CONTAINMENT_NEXT,
                )
            current = resolved
        else:
            current = candidate
    try:
        final = current.resolve(strict=True)
        final_metadata = final.lstat()
        final_mode = final_metadata.st_mode
    except FileNotFoundError:
        if missing_reason is None:
            return None
        raise TaskDataError(missing_reason, _MISSING_TARGET_NEXT) from None
    except OSError:
        raise TaskDataError(f"{label} cannot be inspected", _REPAIR_NEXT) from None
    if _is_windows_reparse_point(final_metadata):
        raise TaskDataError(
            f"{label} contains a Windows reparse point", _CONTAINMENT_NEXT
        )
    if not _is_within(final, root_real):
        raise TaskDataError(f"{label} escapes the project root", _CONTAINMENT_NEXT)
    if not stat.S_ISREG(final_mode):
        raise TaskDataError(f"{label} is not a regular file", _REPAIR_NEXT)
    if allowed_roots is not None and not any(
        _is_within(final, allowed) for allowed in allowed_roots
    ):
        raise TaskDataError(
            f"{label} resolves outside the allowed task roots (.sbtd/tasks or ai/tasks)",
            _CONTAINMENT_NEXT,
        )
    return final


@contextmanager
def open_regular_file(path: Path, label: str) -> Iterator[BinaryIO]:
    """Read only a regular file; special files never block the task writer."""
    try:
        _reject_windows_reparse_points(path, label)
        if not stat.S_ISREG(path.lstat().st_mode):
            raise TaskDataError(f"{label} is not a regular file", _REPAIR_NEXT)
        flags = (
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        )
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise TaskDataError(
                    f"{label} changed to a non-regular file", _REPAIR_NEXT
                )
            yield handle
    except PermissionError:
        raise TaskDataError(
            f"{label} cannot be read (permission denied)", _REPAIR_NEXT
        ) from None
    except OSError:
        raise TaskDataError(f"{label} cannot be read", _REPAIR_NEXT) from None


def _read_utf8(path: Path, label: str) -> str:
    with open_regular_file(path, label) as handle:
        raw = handle.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise TaskDataError(f"{label} is not valid UTF-8", _REPAIR_NEXT) from None


def _reject_json_constant(name: str) -> None:
    raise ValueError(f"non-finite literal {name}")


def _reject_json_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key!r}")
        result[key] = value
    return result


def _check_finite(value: object) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_check_finite(item) for item in value)
    if isinstance(value, dict):
        return all(_check_finite(item) for item in value.values())
    return True


def parse_active_pointer(text: str) -> dict[str, Any]:
    """Parse the active pointer as strict JSON, then validate its schema."""
    label = "active pointer"
    try:
        data = json.loads(
            text,
            object_pairs_hook=_reject_json_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (ValueError, RecursionError):
        raise TaskDataError(
            f"{label} is not valid strict JSON "
            "(duplicate keys and nonfinite numbers are rejected)",
            _REPAIR_NEXT,
        ) from None
    if not _check_finite(data):
        raise TaskDataError(
            f"{label} is not valid strict JSON "
            "(duplicate keys and nonfinite numbers are rejected)",
            _REPAIR_NEXT,
        )
    return validate_task_data(data, "activeTask", label)


def _build_safe_loader(yaml: Any) -> type:
    """Build a SafeLoader subclass for task frontmatter.

    The timestamp implicit resolver is removed on the subclass copy only, so
    timestamps stay strings for real calendar/timezone validation and global
    PyYAML resolver state is never mutated. Duplicate keys are rejected.
    """

    class TaskSafeLoader(yaml.SafeLoader):
        pass

    TaskSafeLoader.yaml_implicit_resolvers = {
        key: [
            (tag, regexp)
            for tag, regexp in resolvers
            if tag != "tag:yaml.org,2002:timestamp"
        ]
        for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }

    def construct_mapping(loader: Any, node: Any, deep: bool = False) -> dict:
        loader.flatten_mapping(node)
        mapping = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=True)
            try:
                hash(key)
            except TypeError:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found unhashable key",
                    key_node.start_mark,
                ) from None
            if key in mapping:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found a duplicate key",
                    key_node.start_mark,
                ) from None
            # deep=True also rejects cyclic aliases during construction.
            mapping[key] = loader.construct_object(value_node, deep=True)
        return mapping

    TaskSafeLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping
    )
    return TaskSafeLoader


def validate_json_compatible(
    value: object,
    label: str,
    active: set[int] | None = None,
    seen: set[int] | None = None,
) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TaskDataError(
                f"{label} frontmatter contains a nonfinite number", _REPAIR_NEXT
            )
        return
    if isinstance(value, (list, dict)):
        active = set() if active is None else active
        seen = set() if seen is None else seen
        marker = id(value)
        if marker in active:
            raise TaskDataError(
                f"{label} frontmatter contains a cyclic structure", _REPAIR_NEXT
            )
        if marker in seen:
            return
        active.add(marker)
        try:
            children = value.values() if isinstance(value, dict) else value
            if isinstance(value, dict):
                for key in value:
                    if not isinstance(key, str):
                        raise TaskDataError(
                            f"{label} frontmatter contains a value that is not "
                            "JSON-compatible (bytes, sets, objects and "
                            "non-string keys are rejected)",
                            _REPAIR_NEXT,
                        )
            for child in children:
                validate_json_compatible(child, label, active, seen)
        finally:
            active.discard(marker)
        seen.add(marker)
        return
    raise TaskDataError(
        f"{label} frontmatter contains a value that is not JSON-compatible "
        "(bytes, sets, objects and non-string keys are rejected)",
        _REPAIR_NEXT,
    )



def _load_safe_yaml(text: str, label: str) -> Any:
    yaml = require_dependency("yaml", "PyYAML")
    try:
        data = yaml.load(text, Loader=_build_safe_loader(yaml))
    except (yaml.YAMLError, RecursionError):
        raise TaskDataError(
            f"{label} frontmatter is not parseable as safe YAML "
            "(duplicate keys and unsafe tags are rejected)",
            _REPAIR_NEXT,
        ) from None
    validate_json_compatible(data, label)
    return data


def parse_task_frontmatter(text: str, label: str) -> dict[str, Any]:
    """Parse frontmatter without interpreting or rewriting the Markdown body."""
    text = text.removeprefix("\ufeff")
    lines = text.split("\n")
    if lines[0].rstrip("\r") != "---":
        raise TaskDataError(f"{label} has no YAML frontmatter block", _REPAIR_NEXT)
    end = None
    for index in range(1, len(lines)):
        if lines[index].rstrip("\r") == "---":
            end = index
            break
    if end is None:
        raise TaskDataError(
            f"{label} frontmatter block is not terminated", _REPAIR_NEXT
        )
    data = _load_safe_yaml("\n".join(lines[1:end]), label)
    if not isinstance(data, dict):
        raise TaskDataError(f"{label} frontmatter is not a mapping", _REPAIR_NEXT)
    return data


def validate_task_timestamps(record: dict[str, Any], label: str) -> None:
    """Validate real calendar/timezone values; the schema pattern is not enough."""
    for field in _TIMESTAMP_FIELDS:
        value = record.get(field)
        if value is None:
            continue
        text = value if isinstance(value, str) else ""
        candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            datetime.fromisoformat(candidate)
        except ValueError:
            raise TaskDataError(
                f"{label} timestamp field {field} is not a real "
                "calendar/timezone value",
                _REPAIR_NEXT,
            ) from None
        # fromisoformat normalizes overflowing offset minutes (e.g. +08:60);
        # the schema pattern pins the shape, so reject them lexically.
        if not text.endswith("Z") and int(text[-2:]) > 59:
            raise TaskDataError(
                f"{label} timestamp field {field} is not a real "
                "calendar/timezone value",
                _REPAIR_NEXT,
            )


def _read_task_record(
    root_real: Path,
    relative: str,
    label: str,
    missing_reason: str | None,
) -> dict[str, Any] | None:
    task_file = _resolve_contained_file(
        root_real, relative, label, None, missing_reason
    )
    if task_file is None:
        return None
    allowed_roots = []
    for root in _TASK_ROOTS:
        try:
            allowed_roots.append((root_real / root).resolve(strict=True))
        except (OSError, RuntimeError):
            continue
    if not any(_is_within(task_file, allowed) for allowed in allowed_roots):
        raise TaskDataError(
            f"{label} resolves outside the allowed task roots (.sbtd/tasks or ai/tasks)",
            _CONTAINMENT_NEXT,
        )
    record = parse_task_frontmatter(_read_utf8(task_file, label), label)
    validate_task_data(record, "taskFrontmatter", label)
    validate_task_timestamps(record, label)
    return record



def _derived_id(relative: str) -> str | None:
    """Logical ID implied by a non-archive storage path, if it is one."""
    for root in _TASK_ROOTS:
        prefix = root + "/"
        if relative.startswith(prefix) and relative.endswith(_TASK_MD_SUFFIX):
            return relative[len(prefix) : -len(_TASK_MD_SUFFIX)]
    return None


def _summary(relative: str, record: dict[str, Any]) -> TaskSummary:
    return {
        "relativePath": relative,
        "id": record["id"],
        "status": record["status"],
        "workflowMode": record["workflow_mode"],
    }


def _inspect_active_task(
    root_real: Path,
) -> tuple[TaskSummary | None, str | None]:
    pointer_file = _resolve_contained_file(
        root_real, _POINTER_PATH, "active pointer", None, None
    )
    if pointer_file is None:
        return None, None
    pointer = parse_active_pointer(_read_utf8(pointer_file, "active pointer"))
    task_relative = str(pointer["task_path"])
    task_id = str(pointer["task_id"])
    record = _read_task_record(
        root_real,
        task_relative,
        "selected task",
        "active pointer records a task file that is missing",
    )
    assert record is not None  # missing_reason guarantees a problem, not None
    if record["id"] != task_id:
        raise TaskDataError(
            "selected task id does not match the active pointer task_id",
            _REPAIR_NEXT,
        )
    # Archive storage paths need not match the ID spelling; ordinary paths must.
    if (
        not task_relative.startswith(_ARCHIVE_PREFIXES)
        and _derived_id(task_relative) != record["id"]
    ):
        raise TaskDataError(
            "selected task id does not match its storage path", _REPAIR_NEXT
        )
    summary = _summary(task_relative, record)
    if record["mode_source"] == "migration-unknown":
        return summary, "needs-user"
    return summary, "ok"


def _inspect_bootstrap_task(
    root_real: Path,
) -> tuple[TaskSummary | None, str | None]:
    record = _read_task_record(root_real, _BOOTSTRAP_PATH, "bootstrap task", None)
    if record is None:
        return None, None
    if record["id"] != _derived_id(_BOOTSTRAP_PATH):
        raise TaskDataError(
            "bootstrap task id does not match its fixed storage path", _REPAIR_NEXT
        )
    summary = _summary(_BOOTSTRAP_PATH, record)
    if record["mode_source"] == "migration-unknown":
        return summary, "needs-user"
    return summary, "done" if record["status"] == "done" else "pending"


def _checked_root(root: Path) -> Path:
    try:
        mode = root.stat().st_mode
    except FileNotFoundError:
        raise TaskDataError("project root does not exist", _ROOT_NEXT) from None
    except OSError:
        raise TaskDataError("project root cannot be inspected", _ROOT_NEXT) from None
    if not stat.S_ISDIR(mode):
        raise TaskDataError("project root is not a directory", _ROOT_NEXT)
    try:
        return root.resolve(strict=True)
    except OSError:
        raise TaskDataError("project root cannot be inspected", _ROOT_NEXT) from None


def _guard(
    inspection: Callable[[Path], tuple[TaskSummary | None, str | None]],
    root_real: Path,
) -> tuple[TaskSummary | None, str | None]:
    """Run one inspection, converting every failure into a sanitized problem."""

    try:
        return inspection(root_real)
    except TaskDataError:
        raise
    except Exception as exc:  # noqa: BLE001 - the result contract always returns.
        raise TaskDataError(
            f"the state inspection failed unexpectedly ({type(exc).__name__}); "
            "no state was modified",
            _REPAIR_NEXT,
        ) from None


def inspect_project_state(project_root: Path) -> StateInspection:
    """Inspect one project's optional SBTD state without modifying anything.

    Always returns a dict with ``status`` (success, blocked, needs-user or
    bootstrap-required), ``reason``, ``nextStep``, ``validationScope``,
    ``activeTask``, ``bootstrapTask`` and ``legacyPresent``. Summaries carry
    only ``relativePath``, ``id``, ``status`` and ``workflowMode``.
    """
    try:
        root_real = _checked_root(Path(project_root))
    except TaskDataError as exc:
        return _result(
            "blocked", exc.reason, exc.next_step, legacy_present=None
        )
    try:
        (root_real / _LEGACY_PATH).lstat()
    except FileNotFoundError:
        legacy_present = False
    except OSError:
        return _result(
            "blocked",
            "legacy state presence could not be inspected",
            _REPAIR_NEXT,
            legacy_present=None,
        )
    else:
        legacy_present = True
    if legacy_present:
        return _result(
            "needs-user",
            "legacy .trellis state is present and was retained without being read",
            "run the explicit v1 -> v2 migration path; onboarding never invokes "
            "the legacy runtime and never modifies retained state",
            legacy_present=True,
        )

    problems: list[TaskDataError] = []
    active_task: TaskSummary | None = None
    bootstrap_task: TaskSummary | None = None
    needs_user = False
    bootstrap_pending = False
    for inspection in (_inspect_active_task, _inspect_bootstrap_task):
        try:
            summary, outcome = _guard(inspection, root_real)
        except TaskDataError as exc:
            problems.append(exc)
            continue
        if inspection is _inspect_active_task:
            active_task = summary
        else:
            bootstrap_task = summary
        needs_user = needs_user or outcome == "needs-user"
        bootstrap_pending = bootstrap_pending or outcome == "pending"

    if problems:
        first = problems[0]
        return _result(
            "blocked", first.reason, first.next_step, active_task, bootstrap_task
        )
    if needs_user:
        return _result(
            "needs-user",
            "a task workflow mode is unresolved (mode_source=migration-unknown)",
            "ask the user to choose the workflow mode explicitly; onboarding "
            "never assumes a legacy mode",
            active_task,
            bootstrap_task,
        )
    if bootstrap_pending:
        return _result(
            "bootstrap-required",
            "the explicit bootstrap task exists and is not recorded as done",
            "complete the explicitly requested bootstrap or resolve its record "
            "before retrying onboarding; unrelated safe work does not require onboarding",
            active_task,
            bootstrap_task,
        )
    if active_task is None and bootstrap_task is None:
        return _result(
            "success",
            "no active task pointer, bootstrap record or legacy state exists; "
            "missing optional state is not evidence of initialization",
            "run onboarding only when installation is explicitly requested; "
            "ordinary tasks do not require prior initialization",
        )
    return _result(
        "success",
        "selected state passed shape and containment checks only; recorded "
        "state is not task recovery, branch rebinding or workflow acceptance proof",
        "proceed with the recorded task state; history, recovery and acceptance "
        "validation stay outside this inspection scope",
        active_task,
        bootstrap_task,
    )
