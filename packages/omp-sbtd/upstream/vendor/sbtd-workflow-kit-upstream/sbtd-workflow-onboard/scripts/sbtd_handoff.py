"""Protected handoff snapshots for real continuation events.

A handoff is a dated Markdown snapshot under ``docs/handoffs/``. The task
document stays the only source of mode/status; a snapshot records what the
task owned at save time and never overwrites a newer task choice on resume.
Snapshots are written only for genuine continuation events (``pause``,
``context-switch``, ``branch-switch``, ``context-pressure`` or an explicit
``manual`` request); call/status counts and entering checking are not
triggers. There is no automatic session-start reading here: callers read
explicitly through ``load``/``reminders``.

Physical paths, Git inspection and atomic writes are reused from the owning
:class:`~sbtd_task_state.TaskStore`; this module adds no second parser for
task state and no second fact source.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from onboard import gitignore_verdicts
from sbtd_project import (
    TaskDataError,
    open_regular_file,
    parse_task_frontmatter,
    validate_json_compatible,
)
from sbtd_task_state import TERMINAL_STATUSES, TaskSnapshot, TaskStateError, TaskStore

HANDOFFS_DIR = "docs/handoffs"
IGNORE_RULE = "/docs/handoffs/"

_AUTO_TRIGGERS = ("pause", "context-switch", "branch-switch", "context-pressure")
_SCHEMA_VERSION = 1
_REMINDER_WINDOW = timedelta(days=7)

_REDACTION_DECLARATION = (
    "the caller reviewed this summary and confirmed it contains no tokens, "
    "account identifiers, private payloads, raw graph contents or secrets"
)

_SNAPSHOT_FIELDS = frozenset(
    {
        "schema_version",
        "task_id",
        "task_path",
        "task_status",
        "workflow_mode",
        "mode_source",
        "mode_note",
        "project_root",
        "branch",
        "head",
        "created_at",
        "content",
        "policy",
        "redaction",
    }
)
_TEXT_CONTENT_FIELDS = ("goal", "next_action", "limitations")
_LIST_CONTENT_FIELDS = (
    "decisions",
    "completed",
    "remaining",
    "changed_files",
    "verification",
    "do_not_repeat",
)
_POLICY_FIELDS = frozenset({"task_opt_out", "session_opt_out"})

# New snapshots use a fixed SHA-256 key so valid logical IDs cannot exceed a
# filesystem component limit. Readers also accept the original reversible hex
# key, which remains the source of truth for existing snapshots.
_FILENAME = re.compile(r"^\d{4}_\d{2}_\d{2}-([0-9a-f]+)\.md$")
_PATH_SHAPE = re.compile(r"^docs/handoffs/[^/]+\.md$")


@dataclass
class HandoffPolicy:
    """Explicit auto-handoff opt-out latches; the store never mutates them."""

    task_opt_out: bool = False
    session_opt_out: bool = False


@dataclass(frozen=True)
class HandoffResult:
    status: str
    persisted: bool
    path: str | None = None
    snapshot: dict[str, Any] | None = None
    reason: str | None = None


def _validate_content(content: Any) -> dict[str, Any]:
    label = "handoff content"
    if not isinstance(content, dict):
        raise TaskStateError(f"{label} is not a mapping")
    required = set(_TEXT_CONTENT_FIELDS) | set(_LIST_CONTENT_FIELDS)
    unknown = set(content) - required - {"presentation"}
    missing = required - set(content)
    if unknown or missing:
        raise TaskStateError(
            f"{label} has an unexpected shape "
            f"(missing: {sorted(missing)}; unknown: {sorted(unknown)})"
        )
    normalized: dict[str, Any] = {}
    for field in _TEXT_CONTENT_FIELDS:
        if not isinstance(content[field], str):
            raise TaskStateError(f"{label} field {field} is not a string")
        normalized[field] = content[field]
    for field in _LIST_CONTENT_FIELDS:
        value = content[field]
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise TaskStateError(f"{label} field {field} is not a list of strings")
        normalized[field] = list(value)
    if "presentation" in content:
        try:
            validate_json_compatible(content["presentation"], label)
        except TaskDataError as exc:
            raise TaskStateError(exc.reason, exc.next_step) from None
        normalized["presentation"] = content["presentation"]
    # Keep a stable key order so rendered snapshots compare deterministically.
    ordered: dict[str, Any] = {"goal": normalized["goal"]}
    for field in _LIST_CONTENT_FIELDS:
        ordered[field] = normalized[field]
    ordered["next_action"] = normalized["next_action"]
    ordered["limitations"] = normalized["limitations"]
    if "presentation" in normalized:
        ordered["presentation"] = normalized["presentation"]
    return ordered


def _parse_moment(value: Any) -> datetime:
    text = value if isinstance(value, str) else ""
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        moment = datetime.fromisoformat(candidate)
    except ValueError:
        raise TaskStateError(
            "handoff snapshot timestamp is not a real calendar/timezone value"
        ) from None
    if moment.tzinfo is None:
        raise TaskStateError("handoff snapshot timestamp has no timezone")
    return moment


class HandoffStore:
    """Save, read and filter handoff snapshots for one authorized project."""

    def __init__(self, tasks: TaskStore) -> None:
        self.tasks = tasks

    # -- encoding and rendering -----------------------------------------

    @staticmethod
    def _task_key(task_id: str) -> str:
        return hashlib.sha256(task_id.encode("utf-8")).hexdigest()

    @staticmethod
    def _key_task_id(key: str) -> str:
        try:
            return bytes.fromhex(key).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            raise TaskStateError("handoff filename does not encode a task ID") from None

    @classmethod
    def _filename_belongs_to_task(cls, name: str, task_id: str) -> bool:
        match = _FILENAME.match(name)
        if match is None:
            return False
        key = match.group(1)
        if key == cls._task_key(task_id):
            return True
        try:
            return cls._key_task_id(key) == task_id
        except TaskStateError:
            return False

    @staticmethod
    def _render_section(title: str, lines: list[str]) -> str:
        body = "\n".join(f"- {line}" for line in lines) if lines else "- none recorded"
        return f"## {title}\n{body}\n"

    def _render(self, snapshot: dict[str, Any]) -> str:
        import yaml

        frontmatter = yaml.safe_dump(snapshot, allow_unicode=True, sort_keys=False)
        content = snapshot["content"]
        branch = snapshot["branch"] or "no Git binding"
        head = snapshot["head"] or "unknown"
        mode = snapshot["workflow_mode"]
        parts = [
            f"# Handoff: {snapshot['task_id']}\n",
            (
                f"- Task: `{snapshot['task_id']}` at `{snapshot['task_path']}` "
                f"(status: {snapshot['task_status']})\n"
                f"- Mode: {mode if mode is not None else 'unknown'} "
                f"({snapshot['mode_source']}) — {snapshot['mode_note']}\n"
                f"- Project: {snapshot['project_root']}\n"
                f"- Branch: {branch}\n"
                f"- HEAD: {head}\n"
            ),
            f"## Goal\n{content['goal']}\n",
            self._render_section("Decisions", content["decisions"]),
            self._render_section("Completed", content["completed"]),
            self._render_section("Remaining", content["remaining"]),
            self._render_section("Changed files", content["changed_files"]),
            self._render_section("Verification", content["verification"]),
            f"## Next action\n{content['next_action']}\n",
            self._render_section("Do not repeat", content["do_not_repeat"]),
            f"## Limitations\n{content['limitations']}\n",
            f"## Redaction\n{snapshot['redaction']}\n",
        ]
        return "---\n" + frontmatter + "---\n" + "\n".join(parts)

    # -- snapshot parsing and validation ---------------------------------

    def _parse_text(self, text: str) -> dict[str, Any]:
        label = "handoff snapshot"
        try:
            data = parse_task_frontmatter(text, label)
        except TaskDataError as exc:
            raise TaskStateError(exc.reason, exc.next_step) from None
        self._validate_snapshot(data)
        lines = text.removeprefix("\ufeff").split("\n")
        end = next(
            index
            for index in range(1, len(lines))
            if lines[index].rstrip("\r") == "---"
        )
        snapshot = dict(data)
        snapshot["summary"] = "\n".join(lines[end + 1 :])
        return snapshot

    @staticmethod
    def _validate_snapshot(data: dict[str, Any]) -> None:
        label = "handoff snapshot"
        if set(data) != _SNAPSHOT_FIELDS:
            raise TaskStateError(
                f"{label} has an unexpected shape "
                f"(missing: {sorted(_SNAPSHOT_FIELDS - set(data))}; "
                f"unknown: {sorted(set(data) - _SNAPSHOT_FIELDS)})"
            )
        version = data["schema_version"]
        if type(version) is not int or version != _SCHEMA_VERSION:
            raise TaskStateError(f"{label} has an unsupported schema version")
        for field in (
            "task_id",
            "task_path",
            "task_status",
            "mode_source",
            "mode_note",
            "project_root",
            "redaction",
        ):
            if not isinstance(data[field], str) or not data[field]:
                raise TaskStateError(f"{label} field {field} is not a string")
        for field in ("workflow_mode", "branch", "head"):
            if data[field] is not None and not isinstance(data[field], str):
                raise TaskStateError(f"{label} field {field} is not a string or null")
        _parse_moment(data["created_at"])
        policy = data["policy"]
        if not isinstance(policy, dict) or set(policy) != _POLICY_FIELDS:
            raise TaskStateError(f"{label} policy has an unexpected shape")
        for field in _POLICY_FIELDS:
            if type(policy[field]) is not bool:
                raise TaskStateError(f"{label} policy field {field} is not a boolean")
        _validate_content(data["content"])

    def _read_snapshot(self, relative: str) -> tuple[dict[str, Any], bytes]:
        path = self.tasks._path(relative)
        if not path.exists():
            raise TaskStateError("handoff snapshot does not exist")
        try:
            with open_regular_file(path, "handoff snapshot") as handle:
                original = handle.read()
                text = original.decode("utf-8")
        except TaskDataError as exc:
            raise TaskStateError(exc.reason, exc.next_step) from None
        except UnicodeDecodeError:
            raise TaskStateError("handoff snapshot cannot be read as UTF-8") from None
        snapshot = self._parse_text(text)
        if snapshot["project_root"] != str(self.tasks.root):
            raise TaskStateError("handoff snapshot belongs to another project root")
        if not self._filename_belongs_to_task(path.name, snapshot["task_id"]):
            raise TaskStateError("handoff filename does not match its recorded task ID")
        return snapshot, original

    def _scan(self) -> Iterator[tuple[str, dict[str, Any]]]:
        base = self.tasks._path(HANDOFFS_DIR)
        if not base.exists():
            return
        if not base.is_dir():
            raise TaskStateError("handoff storage root is not a directory")
        for entry in sorted(base.iterdir()):
            if _FILENAME.match(entry.name) is None:
                continue
            relative = f"{HANDOFFS_DIR}/{entry.name}"
            try:
                snapshot, _ = self._read_snapshot(relative)
            except TaskStateError:
                # Malformed, foreign-owned or tampered files are not usable
                # snapshots; explicit load() reports them loudly.
                continue
            yield relative, snapshot

    # -- protection --------------------------------------------------------

    def _protected(self, binding: str | None) -> bool:
        if binding is not None:
            tracked = self.tasks._git("ls-files", "-z", "--", HANDOFFS_DIR)
            if tracked.returncode or tracked.stdout:
                raise TaskStateError(
                    "handoff directory is tracked or its tracked status is unknown"
                )
            probes = (HANDOFFS_DIR + "/", HANDOFFS_DIR + "/handoff.md")
            verdicts = gitignore_verdicts(
                self.tasks.root, probes, env=self.tasks._git_environment()
            )
            if isinstance(verdicts, str):
                raise TaskStateError("handoff protection cannot be verified by Git")
            return all(verdicts[relative].ignored for relative in probes)
        # Without Git, only an exact root-anchored rule counts; the last
        # matching positive or negation decides whether it is still effective.
        target = self.tasks._path(".gitignore")
        if not target.exists():
            return False
        if not target.is_file():
            raise TaskStateError("handoff protection target is not a regular file")
        try:
            lines = target.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError):
            raise TaskStateError("handoff protection cannot be inspected") from None
        effective: bool | None = None
        for line in lines:
            if line in ("/docs/handoffs", IGNORE_RULE):
                effective = True
            elif line in ("!/docs/handoffs", "!" + IGNORE_RULE):
                effective = False
        return effective is True

    def protect(self, *, confirmed: bool = False) -> bool:
        """Add the narrow ``/docs/handoffs/`` ignore rule; never broader.

        Returns True when the rule was written, False when the directory was
        already protected. Existing data under ``docs/handoffs`` is a
        conflict, never something to hide behind a new rule.
        """
        self.tasks._authorize(confirmed)
        binding = self.tasks.current_binding()
        if self._protected(binding):
            return False
        reserved = self.tasks._path(HANDOFFS_DIR)
        if reserved.exists() and (not reserved.is_dir() or any(reserved.iterdir())):
            raise TaskStateError("narrow handoff protection would hide existing data")
        target = self.tasks._path(".gitignore")
        try:
            if target.exists():
                if not target.is_file() or target.stat().st_nlink != 1:
                    raise TaskStateError(
                        "handoff protection target has unsafe ownership or type"
                    )
                with open_regular_file(target, "handoff protection target") as handle:
                    original = handle.read()
                original.decode("utf-8-sig")
            else:
                original = None
        except (OSError, UnicodeError):
            raise TaskStateError(
                "handoff protection target cannot be safely read"
            ) from None
        except TaskDataError as exc:
            raise TaskStateError(exc.reason, exc.next_step) from None
        content = original or b""
        if content and not content.endswith(b"\n"):
            content += b"\n"
        rule = IGNORE_RULE.encode("ascii") + b"\n"
        lines = content.split(b"\n") if content else []
        tail = [line.strip() for line in lines if line.strip()]
        if binding is None and tail and tail[-1] in (b"/.sbtd", b"/.sbtd/"):
            # Without Git the final explicit root rule is the safeguard for
            # local task state too; insert before it so both stay effective.
            index = next(
                candidate
                for candidate in range(len(lines) - 1, -1, -1)
                if lines[candidate].strip()
            )
            lines.insert(index, IGNORE_RULE.encode("ascii"))
            content = b"\n".join(lines)
            if not content.endswith(b"\n"):
                content += b"\n"
        else:
            content += rule
        self.tasks._write(".gitignore", content, original)
        if not self._protected(binding):
            raise TaskStateError(
                "handoff protection was written but could not be verified"
            )
        return True

    # -- save --------------------------------------------------------------

    def _head(self, binding: str | None) -> str | None:
        if binding is None:
            return None
        result = self.tasks._git("rev-parse", "--verify", "HEAD")
        if result.returncode:
            # Unborn branch or otherwise unobservable: explicitly unknown.
            return None
        return result.stdout.strip()

    def _candidate(
        self,
        task: TaskSnapshot,
        content: dict[str, Any],
        policy: HandoffPolicy,
        moment: datetime,
        binding: str | None,
        head: str | None,
    ) -> dict[str, Any]:
        frontmatter = task.document.frontmatter
        return {
            "schema_version": _SCHEMA_VERSION,
            "task_id": frontmatter["id"],
            "task_path": task.task_path,
            "task_status": frontmatter["status"],
            "workflow_mode": frontmatter["workflow_mode"],
            "mode_source": frontmatter["mode_source"],
            "mode_note": frontmatter["mode_note"],
            "project_root": str(self.tasks.root),
            "branch": binding,
            "head": head,
            "created_at": moment.isoformat(),
            "content": _validate_content(content),
            "policy": {
                "task_opt_out": bool(policy.task_opt_out),
                "session_opt_out": bool(policy.session_opt_out),
            },
            "redaction": _REDACTION_DECLARATION,
        }

    @staticmethod
    def _meaningful(snapshot: dict[str, Any]) -> dict[str, Any]:
        # created_at is the only field whose change alone means nothing.
        return {key: value for key, value in snapshot.items() if key != "created_at"}

    def save(
        self,
        task_id: str,
        *,
        content: dict[str, Any],
        trigger: str,
        policy: HandoffPolicy,
        confirmed: bool = False,
        redaction_confirmed: bool = False,
    ) -> HandoffResult:
        if not isinstance(policy, HandoffPolicy):
            raise TaskStateError("handoff policy must be an explicit HandoffPolicy")
        if trigger != "manual":
            if trigger not in _AUTO_TRIGGERS:
                return HandoffResult(
                    "suppressed",
                    False,
                    reason=(
                        "not a real continuation event; call/status counts and "
                        "entering checking are not handoff triggers"
                    ),
                )
            if policy.session_opt_out:
                return HandoffResult(
                    "suppressed",
                    False,
                    reason="session-level auto-handoff opt-out is active",
                )
            if policy.task_opt_out:
                return HandoffResult(
                    "suppressed",
                    False,
                    reason="task-level auto-handoff opt-out is active",
                )
        if self.tasks.read_only:
            return HandoffResult(
                "conversation-only",
                False,
                reason=(
                    "read-only scope: the handoff stays in the conversation and "
                    "cross-session restoration was not persisted"
                ),
            )
        moment = datetime.now().astimezone()
        binding = self.tasks.current_binding()
        task = self.tasks.inspect(task_id)
        candidate = self._candidate(
            task, content, policy, moment, binding, self._head(binding)
        )
        text = self._render(candidate)
        # Parsing the rendered candidate proves the YAML round-trip and yields
        # the same shape (frontmatter + preserved body) that load() returns.
        snapshot = self._parse_text(text)
        record_branch = task.document.frontmatter["branch"]
        if record_branch != binding:
            return HandoffResult(
                "branch-conflict",
                False,
                snapshot=snapshot,
                reason=(
                    f"task is bound to {record_branch!r} but the current checkout "
                    f"is {binding!r}; use the correct worktree or an explicit "
                    "rebinding before writing a handoff"
                ),
            )
        if not self._protected(binding):
            return HandoffResult(
                "unprotected",
                False,
                snapshot=snapshot,
                reason=(
                    "docs/handoffs is not protected by ignore rules; narrow "
                    "authorization through protect(confirmed=True) is required"
                ),
            )
        meaningful = self._meaningful(snapshot)
        latest: tuple[str, dict[str, Any], datetime] | None = None
        for relative, existing in self._scan():
            if existing["task_id"] != task_id:
                continue
            created = _parse_moment(existing["created_at"])
            if latest is None or (created, relative) > (latest[2], latest[0]):
                latest = (relative, existing, created)
        if latest is not None and self._meaningful(latest[1]) == meaningful:
            return HandoffResult(
                "unchanged",
                True,
                path=latest[0],
                snapshot=latest[1],
                reason=(
                    "the latest snapshot is unchanged; crossing a day alone "
                    "does not require a new handoff"
                ),
            )
        if not confirmed:
            return HandoffResult(
                "pending-confirmation",
                False,
                snapshot=snapshot,
                reason="explicit confirmation is required; nothing was written",
            )
        if not redaction_confirmed:
            return HandoffResult(
                "needs-redaction",
                False,
                snapshot=snapshot,
                reason=(
                    "the caller must explicitly confirm the summary was reviewed "
                    "and redacted before it is written"
                ),
            )
        relative = (
            f"{HANDOFFS_DIR}/{moment.strftime('%Y_%m_%d')}-{self._task_key(task_id)}.md"
        )
        expected: bytes | None = None
        if self.tasks._path(relative).exists():
            existing, expected = self._read_snapshot(relative)
            if existing["task_id"] != task_id:
                raise TaskStateError(
                    "handoff path is owned by another task; refusing to overwrite"
                )
        self.tasks._write(relative, text.encode("utf-8"), expected)
        return HandoffResult("saved", True, path=relative, snapshot=snapshot)

    # -- read --------------------------------------------------------------

    def load(self, relative_path: str) -> dict[str, Any]:
        """Load one owned snapshot; older snapshots load but never change tasks."""
        if _PATH_SHAPE.match(relative_path) is None:
            raise TaskStateError("path is not a handoff snapshot")
        snapshot, _ = self._read_snapshot(relative_path)
        return snapshot

    def reminders(self, *, now: datetime | None = None) -> tuple[dict[str, Any], ...]:
        """Unfinished matching snapshots within seven days, latest per task.

        Matching means this project root, the current branch binding and a
        task that is not finished (done or cancelled). Older snapshots stay
        manually recoverable through ``load``; nothing here reads
        automatically at session start.
        """
        moment = now if now is not None else datetime.now().astimezone()
        if moment.tzinfo is None:
            moment = moment.astimezone()
        binding = self.tasks.current_binding()
        latest: dict[str, tuple[str, dict[str, Any], datetime]] = {}
        for relative, snapshot in self._scan():
            if snapshot["branch"] != binding:
                continue
            created = _parse_moment(snapshot["created_at"])
            if created > moment or moment - created > _REMINDER_WINDOW:
                continue
            previous = latest.get(snapshot["task_id"])
            if previous is None or created > previous[2]:
                latest[snapshot["task_id"]] = (relative, snapshot, created)
        results = []
        for task_id, (relative, snapshot, _) in latest.items():
            try:
                task = self.tasks.inspect(task_id)
            except TaskDataError:
                continue  # not provably unfinished
            if (
                task.document.frontmatter["status"] in TERMINAL_STATUSES
                or task.document.frontmatter["branch"] != binding
                or task.task_path != snapshot["task_path"]
            ):
                continue
            entry = dict(snapshot)
            entry["path"] = relative
            results.append(entry)
        results.sort(key=lambda entry: (entry["created_at"], entry["path"]))
        results.reverse()
        return tuple(results)
