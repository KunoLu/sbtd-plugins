"""Explicit single-writer task operations for host-native Python callers.

No CLI, automatic discovery across projects, identity creation or background work.
The task document owns state; the active JSON is only a bookmark.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from itertools import chain
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

from onboard import gitignore_verdicts
from sbtd_project import (
    TaskDataError,
    open_regular_file,
    parse_active_pointer,
    require_dependency,
    validate_task_data,
)
from sbtd_task_document import TaskDocument

# Terminal states finish a task without success semantics; cancelled never
# counts as done and never carries a completion time.
TERMINAL_STATUSES = frozenset(("done", "cancelled"))


class TaskStateError(TaskDataError):
    def __init__(
        self,
        reason: str,
        next_step: str = "preserve existing task data and resolve the reported conflict",
        *,
        completed_steps: tuple[str, ...] = (),
    ) -> None:
        super().__init__(reason, next_step)
        self.completed_steps = completed_steps


@dataclass(frozen=True)
class TaskSnapshot:
    task_path: str
    document: TaskDocument


@dataclass(frozen=True)
class TaskTransfer:
    status: str
    task: TaskSnapshot
    source_path: str
    target_path: str
    files: tuple[str, ...]
    retained_original: str | None = None
    completed_steps: tuple[str, ...] = ()


class TaskStore:
    def __init__(self, root: Path, *, read_only: bool = False) -> None:
        try:
            self.root = root.resolve(strict=True)
        except (OSError, RuntimeError):
            raise TaskStateError("project root cannot be resolved") from None
        if not self.root.is_dir():
            raise TaskStateError("project root is not a directory")
        self.read_only = read_only

    def _path(self, relative: str) -> Path:
        parts = PurePosixPath(relative).parts
        if not parts or relative.startswith("/") or "\\" in relative or ".." in parts:
            raise TaskStateError("task path is outside the selected project")
        current = self.root
        for index, part in enumerate(parts):
            current = current / part
            try:
                mode = current.lstat().st_mode
            except FileNotFoundError:
                continue
            except OSError:
                raise TaskStateError("task path cannot be inspected") from None
            if stat.S_ISLNK(mode):
                raise TaskStateError(
                    "task writes and reads do not follow symbolic links"
                )
            if index < len(parts) - 1 and not stat.S_ISDIR(mode):
                raise TaskStateError("task parent path is not a directory")
        return current

    @staticmethod
    def _git_environment() -> dict[str, str]:
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GIT_")
        }
        environment.update(
            LC_ALL="C", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull
        )
        return environment

    def _git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ["git", "-C", str(self.root), *arguments],
                env=self._git_environment(),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise TaskStateError("Git binding cannot be inspected safely") from None

    def current_binding(self) -> str | None:
        top = self._git("rev-parse", "--show-toplevel")
        if top.returncode:
            if "not a git repository" in top.stderr:
                return None
            raise TaskStateError("Git repository binding cannot be inspected")
        if Path(top.stdout.removesuffix("\n")).resolve() != self.root:
            raise TaskStateError(
                "selected project is not the actual Git repository root"
            )
        branch = self._git("symbolic-ref", "--quiet", "--short", "HEAD")
        if branch.returncode == 0:
            return branch.stdout.strip()
        head = self._git("rev-parse", "--verify", "HEAD")
        if head.returncode or len(head.stdout.strip()) not in (40, 64):
            raise TaskStateError("detached Git identity cannot be proven")
        return "detached:" + head.stdout.strip()

    def _authorize(self, confirmed: bool) -> None:
        if self.read_only:
            raise TaskStateError("read-only work cannot persist task state")
        if not confirmed:
            raise TaskStateError("task persistence requires explicit confirmation")

    def _require_untracked_local_state(self, binding: str | None) -> None:
        if binding is not None:
            tracked = self._git("ls-files", "-z", "--", ".sbtd")
            if tracked.returncode or tracked.stdout:
                raise TaskStateError(
                    "local task state is tracked or its tracked status is unknown"
                )

    def _local_protected(self, binding: str | None, paths: tuple[str, ...]) -> bool:
        if binding is None:
            target = self._path(".gitignore")
            if not target.exists():
                return False
            if not target.is_file():
                raise TaskStateError("local protection target is not a regular file")
            try:
                lines = [
                    line
                    for line in target.read_text(encoding="utf-8-sig").splitlines()
                    if line.strip() and not line.lstrip().startswith("#")
                ]
            except (OSError, UnicodeError):
                raise TaskStateError("local protection cannot be inspected") from None
            # No Git repository exists, so no tracked-state claim is made.
            # A final explicit root rule is a conservative future-Git safeguard.
            return bool(lines) and lines[-1] in ("/.sbtd", "/.sbtd/")
        verdicts = gitignore_verdicts(self.root, paths, env=self._git_environment())
        if isinstance(verdicts, str):
            raise TaskStateError("local protection cannot be verified by Git")
        return all(verdicts[relative].ignored for relative in paths)

    def _require_local_protection(self, binding: str | None, task_path: str) -> None:
        self._require_untracked_local_state(binding)
        protected_paths = [".sbtd/", ".sbtd/active-task.json"]
        if task_path.startswith(".sbtd/"):
            protected_paths.append(task_path)
        if not self._local_protected(binding, tuple(protected_paths)):
            raise TaskStateError(
                "local task state is not protected by ignore rules",
                "authorize only the required root-anchored local protection; do not initialize the whole project",
            )

    def protect_local_state(self, *, confirmed: bool = False) -> bool:
        self._authorize(confirmed)
        binding = self.current_binding()
        self._require_untracked_local_state(binding)
        if self._local_protected(binding, (".sbtd/",)):
            return False
        reserved = self._path(".sbtd")
        if reserved.exists() and (not reserved.is_dir() or any(reserved.iterdir())):
            raise TaskStateError("narrow protection would hide existing reserved data")
        target = self._path(".gitignore")
        try:
            if target.exists():
                if not target.is_file() or target.stat().st_nlink != 1:
                    raise TaskStateError(
                        "local protection target has unsafe ownership or type"
                    )
                with open_regular_file(target, "local protection target") as handle:
                    original = handle.read()
                original.decode("utf-8-sig")
            else:
                original = None
        except (OSError, UnicodeError):
            raise TaskStateError(
                "local protection target cannot be safely read"
            ) from None
        content = original or b""
        if content and not content.endswith(b"\n"):
            content += b"\n"
        content += b"/.sbtd/\n"
        self._write(".gitignore", content, original)
        try:
            protected = self._local_protected(binding, (".sbtd/",))
        except TaskStateError as error:
            raise TaskStateError(
                error.reason,
                error.next_step,
                completed_steps=tuple(dict.fromkeys((".gitignore", *error.completed_steps))),
            ) from None
        if not protected:
            raise TaskStateError(
                "local protection was written but could not be verified",
                completed_steps=(".gitignore",),
            )
        return True

    def _read(self, relative: str) -> TaskDocument:
        path = self._path(relative)
        try:
            with open_regular_file(path, "selected task") as handle:
                text = handle.read().decode("utf-8")
            return TaskDocument.parse(text)
        except TaskDataError as exc:
            raise TaskStateError(exc.reason, exc.next_step) from None
        except (OSError, UnicodeDecodeError):
            raise TaskStateError("selected task cannot be read as UTF-8") from None

    def _records(self) -> Iterator[TaskSnapshot]:
        for relative in (".sbtd/tasks", "ai/tasks"):
            base = self._path(relative)
            if not base.exists():
                continue
            if not base.is_dir():
                raise TaskStateError("task storage root is not a directory")
            def unreadable(error: OSError) -> None:
                raise TaskStateError("task storage cannot be fully inspected") from error

            for directory, _, files in os.walk(
                base, followlinks=False, onerror=unreadable
            ):
                if "task.md" not in files:
                    continue
                relative_path = (
                    (Path(directory) / "task.md").relative_to(self.root).as_posix()
                )
                document = self._read(relative_path)
                yield TaskSnapshot(relative_path, document)

    def _catalog(self) -> dict[str, TaskSnapshot]:
        records: dict[str, TaskSnapshot] = {}
        for snapshot in self._records():
            task_id = snapshot.document.frontmatter["id"]
            if task_id in records:
                raise TaskStateError("multiple task records have the same logical ID")
            records[task_id] = snapshot
        self._validate_parents(records)
        return records

    @staticmethod
    def _validate_parents(records: dict[str, TaskSnapshot]) -> None:
        for task_id in records:
            seen: set[str] = set()
            current: str | None = task_id
            while current is not None:
                if current in seen:
                    raise TaskStateError("task parent relationships contain a cycle")
                seen.add(current)
                if current not in records:
                    raise TaskStateError("task parent cannot be resolved")
                current = records[current].document.frontmatter.get("parent")

    @staticmethod
    def _unfinished_descendants(task_id: str, records: dict[str, TaskSnapshot]) -> bool:
        children: dict[str, list[str]] = {}
        for child_id, snapshot in records.items():
            parent = snapshot.document.frontmatter.get("parent")
            if parent is not None:
                children.setdefault(parent, []).append(child_id)
        pending = list(children.get(task_id, ()))
        while pending:
            child_id = pending.pop()
            if (
                records[child_id].document.frontmatter["status"]
                not in TERMINAL_STATUSES
            ):
                return True
            pending.extend(children.get(child_id, ()))
        return False

    def _pointer(self) -> tuple[dict[str, Any] | None, bytes | None]:
        path = self._path(".sbtd/active-task.json")
        if not path.exists():
            return None, None
        try:
            with open_regular_file(path, "active task pointer") as handle:
                raw = handle.read()
            pointer = parse_active_pointer(raw.decode("utf-8"))
        except TaskDataError as exc:
            raise TaskStateError(exc.reason, exc.next_step) from None
        except (OSError, ValueError, TypeError):
            raise TaskStateError(
                "active task pointer is malformed or unreadable"
            ) from None
        return pointer, raw

    def inspect(self, task_id: str | None = None) -> TaskSnapshot:
        records = self._catalog()
        if task_id is not None:
            if task_id not in records:
                raise TaskStateError("selected task cannot be found")
            return records[task_id]
        pointer, _ = self._pointer()
        if pointer is None:
            raise TaskStateError("there is no active task")
        selected = records.get(pointer["task_id"])
        if selected is None or selected.task_path != pointer["task_path"]:
            raise TaskStateError(
                "active task pointer does not match its logical record"
            )
        return selected

    def _write(self, relative: str, content: bytes, expected: bytes | None) -> None:
        path = self._path(relative)
        temporary: str | None = None
        try:
            actual = None
            if path.exists():
                with open_regular_file(path, "task write target") as handle:
                    actual = handle.read()
            if actual != expected:
                raise TaskStateError("task data changed before writing")
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(
                prefix=".sbtd-write-", dir=path.parent
            )
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            if expected is not None:
                os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
            self._path(relative)
            actual = None
            if path.exists():
                with open_regular_file(path, "task write target") as handle:
                    actual = handle.read()
            if actual != expected:
                raise TaskStateError("task data changed while preparing the write")
            if expected is None:
                os.link(temporary, path)
            else:
                os.replace(temporary, path)
                temporary = None
        except OSError:
            raise TaskStateError(
                "task state write failed; existing data was not force-overwritten"
            ) from None
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass

    def create(
        self,
        task_id: str,
        *,
        body: str,
        mode: str | None = None,
        mode_note: str | None = None,
        parent: str | None = None,
        shared: bool = False,
        confirmed: bool = False,
    ) -> TaskSnapshot:
        self._authorize(confirmed)
        binding = self.current_binding()
        records = self._catalog()
        previous_pointer, old_pointer = self._pointer()
        selected_mode = mode if mode is not None else "default"
        moment = datetime.now().astimezone().isoformat()
        metadata = {
            "schema_version": 1,
            "id": task_id,
            "workflow_mode": selected_mode,
            "mode_source": "user" if mode is not None else "default",
            "mode_note": mode_note
            or (
                "user selected the task mode"
                if mode is not None
                else "implicit default for a new task"
            ),
            "status": "planned",
            "branch": binding,
            "created_at": moment,
            "updated_at": moment,
            "completed_at": None,
        }
        if parent is not None:
            metadata["parent"] = parent
        existing = records.get(task_id)
        if existing is not None:
            self._now(existing.document)
            metadata["created_at"] = existing.document.frontmatter["created_at"]
            metadata["updated_at"] = existing.document.frontmatter["updated_at"]
        validate_task_data(metadata, "taskFrontmatter", "new task")
        yaml = require_dependency("yaml", "PyYAML")

        document = TaskDocument.parse(
            "---\n"
            + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
            + "---\n"
            + body
        )
        if not self._history(document)[1]:
            raise TaskStateError("new task event history conflicts with its planned state")
        storage = (
            "ai/tasks"
            if shared or selected_mode in ("lite", "strict")
            else ".sbtd/tasks"
        )
        relative = f"{storage}/{task_id}/task.md"
        if relative.casefold().startswith("ai/tasks/index.md/"):
            raise TaskStateError("task storage conflicts with the shared index")
        self._require_local_protection(binding, relative)
        pointer = {"schema_version": 1, "task_id": task_id, "task_path": relative}
        validate_task_data(pointer, "activeTask", "new active task pointer")
        if existing is not None and (
            existing.task_path != relative or existing.document.text != document.text
        ):
            raise TaskStateError(
                "task logical ID already has different content; preserve it"
            )
        candidate = existing or TaskSnapshot(relative, document)
        desired = {**records, task_id: candidate}
        self._validate_parents(desired)
        if existing is None and parent is not None:
            current = parent
            while current is not None:
                if (
                    records[current].document.frontmatter["status"]
                    in TERMINAL_STATUSES
                ):
                    raise TaskStateError(
                        "new child requires its terminal ancestor to be explicitly reopened"
                    )
                current = records[current].document.frontmatter.get("parent")
        index_before: bytes | None = None
        index_after: bytes | None = None
        if relative.startswith("ai/tasks/"):
            index_before, index_after = self._index_candidate(desired, records)
        written: list[str] = []
        try:
            if existing is None:
                self._write(relative, document.text.encode("utf-8"), None)
                written.append(relative)
            if index_after is not None and index_after != index_before:
                self._write("ai/tasks/index.md", index_after, index_before)
                written.append("ai/tasks/index.md")
            if previous_pointer != pointer:
                self._write(
                    ".sbtd/active-task.json",
                    (json.dumps(pointer, ensure_ascii=False, indent=2) + "\n").encode(
                        "utf-8"
                    ),
                    old_pointer,
                )
        except TaskDataError as exc:
            raise TaskStateError(
                exc.reason, exc.next_step, completed_steps=tuple(written)
            ) from None
        return candidate

    def _selected_for_write(self, task_id: str, confirmed: bool) -> TaskSnapshot:
        self._authorize(confirmed)
        selected = self.inspect(task_id)
        binding = self.current_binding()
        if selected.document.frontmatter["branch"] != binding:
            raise TaskStateError(
                "task belongs to a different branch or repository binding",
                "choose the correct worktree, explicitly rebind through recovery, or inspect read-only",
            )
        if selected.task_path.startswith(".sbtd/"):
            self._require_local_protection(binding, selected.task_path)
        return selected

    @staticmethod
    def _require_known_mode(document: TaskDocument) -> None:
        if document.frontmatter["workflow_mode"] is None:
            raise TaskStateError(
                "historical task mode is unresolved",
                "ask the user to choose default, lite or strict and persist that explicit choice first",
            )

    @staticmethod
    def _history(document: TaskDocument) -> tuple[str | None, bool]:
        phase: str | None = None
        previous: str | None = None
        previous_at: datetime | None = None
        consistent = True
        phases = ("planned", "in-progress", "checking")
        for event in document.events:
            source, target = event["from"], event["to"]
            if previous is not None and source != previous:
                consistent = False
            if event["at"] != "unknown":
                at = datetime.fromisoformat(event["at"].replace("Z", "+00:00"))
                if previous_at is not None and at < previous_at:
                    consistent = False
                previous_at = at
            if source == "unknown" and target == "blocked" and previous is None:
                # A first historical unknown->blocked record is a consistent
                # snapshot whose recovery phase stays unknown; it never
                # proves a real blocked ingress or invents one.
                pass
            elif source != "blocked" and target == "blocked":
                if phase is not None or source not in phases:
                    consistent = False
                phase = source
            elif source == "blocked" and target in phases:
                explicit_recovery = event["reason"].startswith(
                    "User-selected recovery after unknown/conflicting history: "
                )
                if explicit_recovery:
                    # Preserve the unresolved prefix, but the recorded user
                    # choice establishes the starting point for later events.
                    consistent = True
                elif phase is None or phase != target:
                    consistent = False
                phase = None
            elif source == "blocked" and target == "cancelled":
                phase = None
            previous = target
        if previous is not None and previous != document.frontmatter["status"]:
            consistent = False
        updated = document.frontmatter["updated_at"]
        if (
            previous_at is not None
            and updated is not None
            and previous_at > datetime.fromisoformat(updated.replace("Z", "+00:00"))
        ):
            consistent = False
        return phase if consistent else None, consistent

    @staticmethod
    def _now(document: TaskDocument) -> str:
        now = datetime.now().astimezone()
        timestamps = [
            value
            for field in ("created_at", "updated_at", "completed_at")
            if (value := document.frontmatter[field]) is not None
        ]
        timestamps.extend(event["at"] for event in document.events if event["at"] != "unknown")
        if any(
            datetime.fromisoformat(value.replace("Z", "+00:00")) > now
            for value in timestamps
        ):
            raise TaskStateError("task timestamps are ahead of the observed clock")
        return now.isoformat()

    def _save(self, selected: TaskSnapshot, candidate: TaskDocument) -> TaskSnapshot:
        self._write(
            selected.task_path,
            candidate.text.encode("utf-8"),
            selected.document.text.encode("utf-8"),
        )
        return TaskSnapshot(selected.task_path, candidate)

    def transition(
        self,
        task_id: str,
        status: str,
        *,
        reason: str,
        evidence: str,
        confirmed: bool = False,
    ) -> TaskSnapshot:
        selected = self._selected_for_write(task_id, confirmed)
        document = selected.document
        self._require_known_mode(document)
        previous = document.frontmatter["status"]
        if status == previous:
            if status != "blocked" or reason == document.frontmatter["blocked_reason"]:
                return selected
            candidate = document.updated(
                {"blocked_reason": reason, "updated_at": self._now(document)}
            )
            return self._save(selected, candidate)
        if previous == "blocked" and status != "cancelled":
            raise TaskStateError("blocked tasks require history-aware recovery")
        _, consistent = self._history(document)
        if not consistent:
            raise TaskStateError("task event history conflicts with its current state")
        allowed = {
            "planned": ("in-progress", "blocked", "cancelled"),
            "in-progress": ("checking", "blocked", "cancelled"),
            "checking": ("in-progress", "done", "blocked", "cancelled"),
            "blocked": ("cancelled",),
            "done": (),
            "cancelled": (),
        }
        if status not in allowed[previous]:
            raise TaskStateError("requested task status change is not permitted")
        if (
            status == "checking" or status in TERMINAL_STATUSES
        ) and self._unfinished_descendants(task_id, self._catalog()):
            raise TaskStateError(
                "terminal parent transitions require all descendant tasks to be finished"
            )
        moment = self._now(document)
        event = {
            "at": moment,
            "from": previous,
            "to": status,
            "reason": reason,
            "evidence": evidence,
        }
        if status == "blocked":
            validate_task_data(event, "blockEntryEvent", "new blocked event")
        fields: dict[str, Any] = {
            "status": status,
            "updated_at": moment,
            "completed_at": moment if status == "done" else None,
        }
        if status == "blocked":
            fields["blocked_reason"] = reason
        elif previous == "blocked":
            fields["blocked_reason"] = None
        candidate = document.updated(fields, event=event)
        if not self._history(candidate)[1]:
            raise TaskStateError("requested transition would create inconsistent history")
        return self._save(selected, candidate)

    def set_mode(
        self,
        task_id: str,
        mode: str,
        *,
        note: str,
        confirmed: bool = False,
    ) -> TaskSnapshot:
        selected = self._selected_for_write(task_id, confirmed)
        frontmatter = selected.document.frontmatter
        if (
            frontmatter["workflow_mode"] == mode
            and frontmatter["mode_source"] == "user"
            and frontmatter["mode_note"] == note
        ):
            return selected
        candidate = selected.document.updated(
            {
                "workflow_mode": mode,
                "mode_source": "user",
                "mode_note": note,
                "updated_at": self._now(selected.document),
            }
        )
        return self._save(selected, candidate)

    def resume(
        self,
        task_id: str,
        *,
        reason: str,
        evidence: str,
        target: str | None = None,
        confirmed: bool = False,
    ) -> TaskSnapshot:
        selected = self._selected_for_write(task_id, confirmed)
        if not reason.strip() or not evidence.strip():
            raise TaskStateError("recovery requires a nonempty reason and evidence")
        document = selected.document
        self._require_known_mode(document)
        status = document.frontmatter["status"]
        if status != "blocked":
            if (
                status in ("planned", "in-progress", "checking")
                and document.events
                and document.events[-1]["from"] == "blocked"
                and document.events[-1]["to"] == status
            ):
                return selected
            raise TaskStateError("selected task is not blocked")
        previous_phase, _ = self._history(document)
        if previous_phase is None:
            if target not in ("planned", "in-progress", "checking"):
                raise TaskStateError(
                    "blocked history cannot prove the previous phase",
                    "ask the user to select planned, in-progress or checking; preserve existing history",
                )
            reason = (
                "User-selected recovery after unknown/conflicting history: " + reason
            )
        elif target is not None and target != previous_phase:
            raise TaskStateError(
                "recovery target contradicts the recorded blocked ingress"
            )
        else:
            target = previous_phase
        moment = self._now(document)
        candidate = document.updated(
            {
                "status": target,
                "blocked_reason": None,
                "updated_at": moment,
            },
            event={
                "at": moment,
                "from": "blocked",
                "to": target,
                "reason": reason,
                "evidence": evidence,
            },
        )
        return self._save(selected, candidate)

    def reopen(
        self,
        task_id: str,
        *,
        reason: str,
        evidence: str,
        confirmed: bool = False,
    ) -> TaskSnapshot:
        selected = self._selected_for_write(task_id, confirmed)
        document = selected.document
        self._require_known_mode(document)
        terminal = document.frontmatter["status"]
        if terminal not in TERMINAL_STATUSES:
            if (
                terminal == "planned"
                and document.events
                and document.events[-1]["from"] in TERMINAL_STATUSES
                and document.events[-1]["to"] == "planned"
            ):
                return selected
            raise TaskStateError("only a finished task can be reopened")
        records = self._catalog()
        if records[task_id].document.text != document.text:
            raise TaskStateError("task changed while preparing ancestor reopening")
        lineage: list[TaskSnapshot] = []
        current: str | None = task_id
        while current is not None:
            ancestor = records[current]
            lineage.append(ancestor)
            current = ancestor.document.frontmatter.get("parent")
        binding = self.current_binding()
        candidates: list[tuple[TaskSnapshot, TaskDocument]] = []
        for ancestor in reversed(lineage):
            previous = ancestor.document
            terminal = previous.frontmatter["status"]
            if terminal not in TERMINAL_STATUSES:
                continue
            self._require_known_mode(previous)
            if previous.frontmatter["branch"] != binding:
                raise TaskStateError("terminal ancestor belongs to a different branch")
            if ancestor.task_path.startswith(".sbtd/"):
                self._require_local_protection(binding, ancestor.task_path)
            _, consistent = self._history(previous)
            if not consistent:
                raise TaskStateError("finished task history is inconsistent")
            ingress = [
                event
                for event in previous.events
                if event["to"] == terminal and event["from"] != terminal
            ]
            prepared = previous
            if not ingress:
                if terminal == "done":
                    preserved_at = previous.frontmatter["completed_at"] or "unknown"
                    preserved_reason = "Preserved historical completion from existing task frontmatter"
                    preserved_evidence = "existing task.md status/completed_at; earlier evidence not-recorded"
                else:
                    preserved_at = "unknown"
                    preserved_reason = "Preserved historical cancellation from existing task frontmatter"
                    preserved_evidence = "existing task.md status; earlier evidence not-recorded"
                prepared = previous.updated(
                    {},
                    event={
                        "at": preserved_at,
                        "from": "unknown",
                        "to": terminal,
                        "reason": preserved_reason,
                        "evidence": preserved_evidence,
                    },
                    prepend_event=True,
                )
            elif (
                terminal == "done"
                and previous.frontmatter["completed_at"] is not None
            ):
                recorded = ingress[-1]["at"]
                if recorded == "unknown" or (
                    datetime.fromisoformat(recorded.replace("Z", "+00:00"))
                    != datetime.fromisoformat(
                        previous.frontmatter["completed_at"].replace("Z", "+00:00")
                    )
                ):
                    raise TaskStateError(
                        "completion time conflicts with the preserved event"
                    )
            moment = self._now(previous)
            candidate = prepared.updated(
                {
                    "status": "planned",
                    "completed_at": None,
                    "updated_at": moment,
                },
                event={
                    "at": moment,
                    "from": terminal,
                    "to": "planned",
                    "reason": reason,
                    "evidence": evidence,
                },
            )
            if not self._history(candidate)[1]:
                raise TaskStateError(
                    "historical terminal record cannot be reconciled without changing existing events"
                )
            candidates.append((ancestor, candidate))
        written: list[str] = []
        for ancestor, candidate in candidates:
            try:
                self._save(ancestor, candidate)
            except TaskDataError as exc:
                raise TaskStateError(
                    exc.reason, exc.next_step, completed_steps=tuple(written)
                ) from None
            written.append(ancestor.task_path)
        return self.inspect(task_id)

    def _tree_manifest(self, relative: str) -> dict[str, tuple[int, int, str | None]]:
        root = self._path(relative)
        if not root.is_dir():
            raise TaskStateError("task directory is missing or is not a directory")
        entries: dict[str, tuple[int, int, str | None]] = {}
        for directory, directories, files in os.walk(root, followlinks=False):
            directory_path = Path(directory)
            for entry_name in chain((".",), directories, files):
                path = directory_path / entry_name
                metadata = path.lstat()
                name = path.relative_to(root).as_posix()
                if stat.S_ISLNK(metadata.st_mode):
                    raise TaskStateError(
                        "task transfer does not follow or publish symbolic links"
                    )
                if stat.S_ISDIR(metadata.st_mode):
                    digest = None
                elif stat.S_ISREG(metadata.st_mode):
                    checksum = hashlib.sha256()
                    with open_regular_file(path, "task transfer attachment") as handle:
                        while chunk := handle.read(131072):
                            checksum.update(chunk)
                    digest = checksum.hexdigest()
                else:
                    raise TaskStateError(
                        "task transfer contains a non-regular attachment"
                    )
                entries[name] = (metadata.st_mode, metadata.st_mtime_ns, digest)
        return entries

    @staticmethod
    def _index_rows(records: dict[str, TaskSnapshot]) -> list[str]:
        rows: list[str] = []
        for task_id, snapshot in sorted(records.items()):
            if not snapshot.task_path.startswith("ai/tasks/"):
                continue
            label = task_id.replace("[", "\\[").replace("]", "\\]")
            target = quote(snapshot.task_path.removeprefix("ai/tasks/"), safe="/")
            rows.append(f"- [{label}]({target})")
        return rows

    def _index_candidate(
        self,
        records: dict[str, TaskSnapshot],
        previous: dict[str, TaskSnapshot],
    ) -> tuple[bytes | None, bytes]:
        path = self._path("ai/tasks/index.md")
        if path.exists() and not path.is_file():
            raise TaskStateError("shared task index is not a regular file")
        try:
            original = None
            if path.exists():
                with open_regular_file(path, "shared task index") as handle:
                    original = handle.read()
            text = (
                original.decode("utf-8") if original is not None else "# Shared tasks\n"
            )
        except (OSError, UnicodeError):
            raise TaskStateError("shared task index cannot be safely read") from None
        begin, end = "<!-- sbtd-task-index:start -->", "<!-- sbtd-task-index:end -->"
        rows = self._index_rows(records)
        block = begin + "\n" + "\n".join(rows) + "\n" + end
        if begin not in text and end not in text:
            separator = "\n" if text.endswith("\n") else "\n\n"
            return original, (text + separator + block + "\n").encode("utf-8")
        if (
            text.count(begin) != 1
            or text.count(end) != 1
            or text.index(begin) >= text.index(end)
        ):
            raise TaskStateError("shared task index has conflicting ownership markers")
        start, finish = text.index(begin), text.index(end)
        allowed = set(rows + self._index_rows(previous))
        existing = [
            line
            for line in text[start + len(begin) : finish].splitlines()
            if line.strip()
        ]
        if any(line not in allowed for line in existing) or len(existing) != len(
            set(existing)
        ):
            raise TaskStateError(
                "shared task index contains unknown or conflicting managed content"
            )
        return original, (text[:start] + block + text[finish + len(end) :]).encode(
            "utf-8"
        )

    def _publish_tree(
        self,
        source: str,
        target: str,
        expected: dict[str, tuple[int, int, str | None]],
        binding: str | None,
        updates: dict[str, TaskDocument] | None = None,
    ) -> None:
        temporary = f".sbtd/task-transfer-candidates/{uuid.uuid4().hex}"
        self._require_local_protection(binding, temporary + "/task/task.md")
        candidate_root = self._path(temporary)
        candidate_root.mkdir(mode=0o700, parents=True)
        published = False
        try:
            shutil.copytree(self._path(source), candidate_root / "task", symlinks=True)
            if (
                self._tree_manifest(source) != expected
                or self._tree_manifest(temporary + "/task") != expected
            ):
                raise TaskStateError(
                    "task contents changed while preparing the transfer"
                )
            for relative, document in (updates or {}).items():
                prepared = temporary + "/task/" + relative
                with open_regular_file(self._path(prepared), "prepared task") as handle:
                    original = handle.read()
                self._write(prepared, document.text.encode("utf-8"), original)
            if self._tree_manifest(source) != expected:
                raise TaskStateError(
                    "task contents changed before publishing the transfer"
                )
            destination = self._path(target)
            if destination.exists():
                raise TaskStateError(
                    "task transfer target appeared while preparing the copy"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.rename(candidate_root / "task", destination)
            published = True
        finally:
            try:
                shutil.rmtree(candidate_root)
            except OSError:
                if published:
                    raise TaskStateError(
                        "task transfer published but candidate cleanup failed",
                        completed_steps=(target,),
                    ) from None
                raise

    def _terminal_time(self, document: TaskDocument) -> str | None:
        terminal = document.frontmatter["status"]
        if terminal not in TERMINAL_STATUSES:
            raise TaskStateError("only finished tasks can be archived")
        _, consistent = self._history(document)
        if not consistent:
            raise TaskStateError("terminal history is inconsistent")
        ingress = [
            event
            for event in document.events
            if event["to"] == terminal and event["from"] != terminal
        ]
        field = document.frontmatter["completed_at"] if terminal == "done" else None
        event_at = ingress[-1]["at"] if ingress else None
        if event_at == "unknown":
            event_at = None
        if (
            field is not None
            and event_at is not None
            and datetime.fromisoformat(field.replace("Z", "+00:00"))
            != datetime.fromisoformat(event_at.replace("Z", "+00:00"))
        ):
            raise TaskStateError("completion time conflicts with its preserved event")
        value = field or event_at
        if value is not None:
            finished = datetime.fromisoformat(value.replace("Z", "+00:00"))
            created = document.frontmatter["created_at"]
            if finished > datetime.now().astimezone() or (
                created is not None
                and finished < datetime.fromisoformat(created.replace("Z", "+00:00"))
            ):
                raise TaskStateError(
                    "terminal time is outside the task's observed history"
                )
        return value

    def _archive_target(self, snapshot: TaskSnapshot) -> str:
        finished_at = self._terminal_time(snapshot.document)
        period = "undated"
        if finished_at is not None:
            finished = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
            period = f"{finished.year:04d}-Q{(finished.month - 1) // 3 + 1}"
        storage = (
            ".sbtd/tasks"
            if snapshot.task_path.startswith(".sbtd/tasks/")
            else "ai/tasks"
        )
        return (
            f"{storage}/archive/{period}/{snapshot.document.frontmatter['id']}/task.md"
        )

    def _archive_document(
        self,
        source: TaskSnapshot,
        target: str,
        reason: str,
        evidence: str,
        existing: TaskSnapshot | None,
    ) -> TaskDocument:
        self._terminal_time(source.document)
        terminal = source.document.frontmatter["status"]
        message = f"Archived task from {source.task_path} to {target}: {reason}"
        now = self._now(source.document)
        moment = now
        if existing is not None:
            if not existing.document.events:
                raise TaskStateError("archive candidate has no operation event")
            event = existing.document.events[-1]
            if (
                event["from"] != terminal
                or event["to"] != terminal
                or event["reason"] != message
                or event["evidence"] != evidence
                or event["at"] == "unknown"
                or existing.document.frontmatter["updated_at"] != event["at"]
                or datetime.fromisoformat(event["at"].replace("Z", "+00:00"))
                > datetime.fromisoformat(now)
            ):
                raise TaskStateError(
                    "archive candidate does not match this approved operation"
                )
            moment = event["at"]
        candidate = source.document.updated(
            {"updated_at": moment},
            event={
                "at": moment,
                "from": terminal,
                "to": terminal,
                "reason": message,
                "evidence": evidence,
            },
        )
        if existing is not None and existing.document.text != candidate.text:
            raise TaskStateError(
                "archive candidate contains changes not present in the original"
            )
        return candidate

    def _verify_transfer_tree(
        self,
        source: str,
        target: str,
        expected: dict[str, tuple[int, int, str | None]],
        updates: dict[str, TaskDocument],
    ) -> None:
        if self._tree_manifest(source) != expected:
            raise TaskStateError("original task contents changed during the transfer")
        actual = self._tree_manifest(target)
        if actual.keys() != expected.keys():
            raise TaskStateError(
                "task transfer target has missing or additional content"
            )
        for relative, entry in expected.items():
            target_entry = actual[relative]
            if relative in updates:
                digest = hashlib.sha256(
                    updates[relative].text.encode("utf-8")
                ).hexdigest()
                matches = target_entry[0] == entry[0] and target_entry[2] == digest
            elif entry[2] is None and updates:
                matches = target_entry[0] == entry[0] and target_entry[2] is None
            else:
                matches = target_entry == entry
            if not matches:
                raise TaskStateError(
                    "task transfer target differs from the approved candidate"
                )

    def _transfer(
        self,
        task_id: str,
        *,
        operation: str,
        reason: str = "",
        evidence: str = "",
        confirmed: bool = False,
        retire_source: bool = False,
        include_tasks: tuple[str, ...] = (),
    ) -> TaskTransfer:
        physical = list(self._records())
        matches = [
            snapshot
            for snapshot in physical
            if snapshot.document.frontmatter["id"] == task_id
        ]
        if operation == "promote":
            originals = [
                snapshot
                for snapshot in matches
                if snapshot.task_path.startswith(".sbtd/tasks/")
            ]
            already_status = "already-shared"
        else:
            if not reason.strip() or not evidence.strip():
                raise TaskStateError("archive requires a nonempty reason and evidence")
            originals = [
                snapshot
                for snapshot in matches
                if snapshot.task_path != self._archive_target(snapshot)
            ]
            already_status = "already-archived"
        if not originals:
            if len(matches) != 1:
                raise TaskStateError("transfer cannot resolve a unique task")
            selected = matches[0]
            directory = PurePosixPath(selected.task_path).parent.as_posix()
            available = {
                item.document.frontmatter["id"]
                for item in physical
                if item.task_path.startswith(directory + "/")
            }
            if not set(include_tasks).issubset(available):
                raise TaskStateError(
                    "explicit transfer scope is not present in the target storage"
                )
            return TaskTransfer(
                already_status, selected, selected.task_path, selected.task_path, ()
            )
        if len(originals) != 1:
            raise TaskStateError("transfer has conflicting original records")
        selected = originals[0]
        source_file = selected.task_path
        target_file = (
            "ai/tasks/" + source_file.removeprefix(".sbtd/tasks/")
            if operation == "promote"
            else self._archive_target(selected)
        )
        source_dir = PurePosixPath(source_file).parent.as_posix()
        target_dir = PurePosixPath(target_file).parent.as_posix()
        declared = (task_id, *include_tasks)
        owned = {
            item.document.frontmatter["id"]
            for item in physical
            if item.task_path.startswith(source_dir + "/")
        }
        if len(declared) != len(set(declared)) or owned != set(declared):
            raise TaskStateError(
                "task directory contains records outside the explicit promotion scope",
                "review the separate logical tasks and explicitly include each authorized task; path nesting is not ownership",
            )
        source_key = source_dir.casefold()
        target_key = target_dir.casefold()
        if target_key == "ai/tasks/index.md" or target_key.startswith(
            "ai/tasks/index.md/"
        ):
            raise TaskStateError("task storage conflicts with the shared index")
        if target_key.startswith(source_key + "/") or source_key.startswith(
            target_key + "/"
        ):
            raise TaskStateError("task transfer source and target directories overlap")
        source_manifest = self._tree_manifest(source_dir)
        target = self._path(target_dir)
        if retire_source and not target.exists():
            raise TaskStateError(
                "original retirement requires an already prepared target",
                "prepare and verify the target first, then obtain a separate retirement confirmation",
            )
        by_path = {snapshot.task_path: snapshot for snapshot in physical}
        updates: dict[str, TaskDocument] = {}
        if operation == "archive":
            for snapshot in physical:
                if snapshot.task_path.startswith(source_dir + "/"):
                    destination = target_dir + snapshot.task_path[len(source_dir) :]
                    relative = snapshot.task_path[len(source_dir) + 1 :]
                    updates[relative] = self._archive_document(
                        snapshot,
                        destination,
                        reason,
                        evidence,
                        by_path.get(destination),
                    )
        if target.exists():
            self._verify_transfer_tree(source_dir, target_dir, source_manifest, updates)
        records: dict[str, TaskSnapshot] = {}
        moved: dict[str, TaskSnapshot] = {}
        for snapshot in physical:
            relative = snapshot.task_path
            record_id = snapshot.document.frontmatter["id"]
            if relative.startswith(target_dir + "/"):
                counterpart = source_dir + relative[len(target_dir) :]
                original = by_path.get(counterpart)
                expected_document = updates.get(relative[len(target_dir) + 1 :])
                if original is None or snapshot.document.text != (
                    expected_document.text
                    if expected_document is not None
                    else original.document.text
                ):
                    raise TaskStateError(
                        "transfer target has no matching original record"
                    )
                continue
            if record_id in records:
                raise TaskStateError(
                    "promotion cannot choose between duplicate logical IDs"
                )
            records[record_id] = snapshot
            if relative.startswith(source_dir + "/"):
                destination = target_dir + relative[len(source_dir) :]
                moved[record_id] = TaskSnapshot(
                    destination,
                    updates.get(relative[len(source_dir) + 1 :], snapshot.document),
                )
        self._validate_parents(records)
        if operation == "archive" and self._unfinished_descendants(task_id, records):
            raise TaskStateError("archive requires all descendant tasks to be finished")
        desired = {**records, **moved}
        self._validate_parents(desired)
        index_before: bytes | None = None
        index_after: bytes | None = None
        if target_file.startswith("ai/tasks/"):
            index_before, index_after = self._index_candidate(desired, records)
        pointer, pointer_before = self._pointer()
        if pointer is not None and not any(
            item.task_path == pointer["task_path"]
            and item.document.frontmatter["id"] == pointer["task_id"]
            for item in physical
        ):
            raise TaskStateError("active pointer is not a valid transfer reference")
        pointer_after = pointer
        if pointer is None:
            pointer_after = {
                "schema_version": 1,
                "task_id": task_id,
                "task_path": target_file,
            }
        elif pointer["task_path"].startswith(source_dir + "/"):
            pointer_after = {
                **pointer,
                "task_path": target_dir + pointer["task_path"][len(source_dir) :],
            }
        files = tuple(
            name for name, entry in source_manifest.items() if entry[2] is not None
        )
        if not confirmed:
            return TaskTransfer(
                "needs-confirmation", selected, source_file, target_file, files
            )
        self._authorize(confirmed)
        binding = self.current_binding()
        if any(
            snapshot.document.frontmatter["branch"] != binding
            for snapshot in moved.values()
        ):
            raise TaskStateError("transfer contains a task from another branch")
        self._require_local_protection(binding, source_file)
        written: list[str] = []
        retained: str | None = None
        try:
            if not target.exists():
                self._publish_tree(
                    source_dir, target_dir, source_manifest, binding, updates
                )
                written.append(target_dir)
            self._verify_transfer_tree(source_dir, target_dir, source_manifest, updates)
            if index_after is not None and index_after != index_before:
                self._write("ai/tasks/index.md", index_after, index_before)
                written.append("ai/tasks/index.md")
            if pointer_after != pointer:
                self._write(
                    ".sbtd/active-task.json",
                    (
                        json.dumps(pointer_after, ensure_ascii=False, indent=2) + "\n"
                    ).encode("utf-8"),
                    pointer_before,
                )
                written.append(".sbtd/active-task.json")
            if retire_source:
                retained = f".sbtd/task-originals/{uuid.uuid4().hex}/task"
                self._require_local_protection(binding, retained + "/task.md")
                self._verify_transfer_tree(
                    source_dir, target_dir, source_manifest, updates
                )
                destination = self._path(retained)
                destination.parent.mkdir(mode=0o700, parents=True)
                os.rename(self._path(source_dir), destination)
                written.append(retained)
        except TaskDataError as exc:
            completed = tuple(
                dict.fromkeys((*written, *getattr(exc, "completed_steps", ())))
            )
            raise TaskStateError(
                exc.reason, exc.next_step, completed_steps=completed
            ) from None
        except OSError:
            raise TaskStateError(
                "task transfer stopped after an I/O failure; originals were not recursively deleted",
                completed_steps=tuple(written),
            ) from None
        return TaskTransfer(
            ("promoted" if operation == "promote" else "archived")
            if retire_source
            else "retirement-required",
            moved[task_id],
            source_file,
            target_file,
            files,
            retained,
            tuple(written),
        )

    def promote(
        self,
        task_id: str,
        *,
        confirmed: bool = False,
        retire_source: bool = False,
        include_tasks: tuple[str, ...] = (),
    ) -> TaskTransfer:
        return self._transfer(
            task_id,
            operation="promote",
            confirmed=confirmed,
            retire_source=retire_source,
            include_tasks=include_tasks,
        )

    def archive(
        self,
        task_id: str,
        *,
        reason: str,
        evidence: str,
        confirmed: bool = False,
        retire_source: bool = False,
        include_tasks: tuple[str, ...] = (),
    ) -> TaskTransfer:
        return self._transfer(
            task_id,
            operation="archive",
            reason=reason,
            evidence=evidence,
            confirmed=confirmed,
            retire_source=retire_source,
            include_tasks=include_tasks,
        )

    def select(self, task_id: str, *, confirmed: bool = False) -> TaskSnapshot:
        selected = self._selected_for_write(task_id, confirmed)
        if self._unfinished_descendants(task_id, self._catalog()):
            raise TaskStateError("select an unfinished child before parent integration")
        binding = self.current_binding()
        if selected.document.frontmatter["branch"] != binding:
            raise TaskStateError("task branch changed before bookmark selection")
        self._require_local_protection(binding, ".sbtd/active-task.json")
        pointer, original = self._pointer()
        candidate = {
            "schema_version": 1,
            "task_id": task_id,
            "task_path": selected.task_path,
        }
        if pointer == candidate:
            return selected
        if self._read(selected.task_path).text != selected.document.text:
            raise TaskStateError("selected task changed before bookmark persistence")
        self._write(
            ".sbtd/active-task.json",
            (json.dumps(candidate, ensure_ascii=False, indent=2) + "\n").encode(
                "utf-8"
            ),
            original,
        )
        return selected

    def rebind(
        self,
        task_id: str,
        *,
        expected_branch: str | None,
        reason: str,
        evidence: str,
        confirmed: bool = False,
    ) -> TaskSnapshot:
        self._authorize(confirmed)
        if not reason.strip() or not evidence.strip():
            raise TaskStateError(
                "branch rebinding requires its explicit reason and evidence"
            )
        selected = self.inspect(task_id)
        document = selected.document
        observed = self.current_binding()
        previous = document.frontmatter["branch"]
        if previous == observed:
            return selected
        if previous != expected_branch:
            raise TaskStateError("task branch changed since the rebinding decision")
        if selected.task_path.startswith(".sbtd/"):
            self._require_local_protection(observed, selected.task_path)
        _, consistent = self._history(document)
        if not consistent:
            raise TaskStateError(
                "resolve the task history before changing its branch binding"
            )
        phase = document.frontmatter["status"]
        moment = self._now(document)
        candidate = document.updated(
            {"branch": observed, "updated_at": moment},
            event={
                "at": moment,
                "from": phase,
                "to": phase,
                "reason": (
                    "Explicit branch rebinding from "
                    + json.dumps(previous, ensure_ascii=False)
                    + " to "
                    + json.dumps(observed, ensure_ascii=False)
                    + ": "
                    + reason
                ),
                "evidence": evidence,
            },
        )
        if self.current_binding() != observed:
            raise TaskStateError("checkout changed while preparing the rebinding")
        return self._save(selected, candidate)

    def recovery_candidates(
        self, task_id: str | None = None
    ) -> tuple[TaskSnapshot, ...]:
        if task_id is not None:
            return (self.inspect(task_id),)
        pointer, _ = self._pointer()
        if pointer is not None:
            return (self.inspect(),)
        records = self._catalog()
        return tuple(records[task_id] for task_id in sorted(records))
