"""Explicit developer identity resolution; no guessed names or legacy fallback."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from pathlib import Path

from onboard_arguments import validate_developer_name
from sbtd_project import TaskDataError, open_regular_file
from sbtd_task_state import TaskStateError, TaskStore

_IDENTITY_PATH = ".sbtd/developer"


@dataclass(frozen=True)
class IdentityResult:
    status: str
    name: str | None = None
    source: str | None = None
    path: str | None = None
    first_write_eligible: bool = False
    topology: str = "not-inspected"
    reason: str | None = None
    needs_protection: bool = False
    completed_steps: tuple[str, ...] = ()


class DeveloperStore:
    def __init__(self, root: Path, *, read_only: bool = False) -> None:
        self.tasks = TaskStore(root, read_only=read_only)

    @staticmethod
    def _read_name(tasks: TaskStore) -> str | None:
        path = tasks._path(_IDENTITY_PATH)
        if not path.exists():
            return None
        try:
            with open_regular_file(path, "developer identity") as handle:
                text = handle.read().decode("utf-8-sig")
        except UnicodeError:
            raise TaskStateError("developer identity is not readable UTF-8") from None
        declarations = [
            line for line in text.splitlines() if line and not line.startswith("#")
        ]
        if len(declarations) != 1 or not declarations[0].startswith("name="):
            raise TaskStateError(
                "developer identity must have one unambiguous name= declaration"
            )
        try:
            return validate_developer_name(declarations[0][len("name=") :])
        except (argparse.ArgumentTypeError, TypeError):
            raise TaskStateError(
                "developer identity name must match lowercase letters and digits exactly"
            ) from None

    @staticmethod
    def _git_path(tasks: TaskStore, *arguments: str) -> Path:
        result = tasks._git("rev-parse", *arguments)
        if result.returncode != 0:
            raise TaskStateError("Git worktree ownership could not be verified")
        value = result.stdout.removesuffix("\n")
        path = Path(value)
        if not value or not path.is_absolute():
            raise TaskStateError("Git returned an ambiguous worktree ownership path")
        try:
            return path.resolve(strict=True)
        except (OSError, RuntimeError):
            raise TaskStateError("Git worktree ownership path is unavailable") from None

    def _topology(self) -> tuple[str, TaskStore | None]:
        tasks = self.tasks
        root = tasks._git("rev-parse", "--show-toplevel")
        if root.returncode:
            if "not a git repository" in root.stderr:
                for ancestor in (tasks.root, *tasks.root.parents):
                    try:
                        (ancestor / ".git").lstat()
                    except FileNotFoundError:
                        continue
                    except OSError:
                        raise TaskStateError(
                            "Git ancestry cannot be safely inspected"
                        ) from None
                    raise TaskStateError(
                        "a Git marker exists but its checkout ownership is not verified"
                    )
                return "non-git", None
            raise TaskStateError("Git checkout classification is unknown")
        if Path(root.stdout.removesuffix("\n")).resolve() != tasks.root:
            raise TaskStateError("selected identity root is not the Git checkout root")
        git_dir = self._git_path(tasks, "--absolute-git-dir")
        common = self._git_path(tasks, "--path-format=absolute", "--git-common-dir")
        if git_dir == common:
            return "non-linked", None
        listing = tasks._git("worktree", "list", "--porcelain", "-z")
        if listing.returncode != 0 or not listing.stdout.endswith("\0\0"):
            raise TaskStateError(
                "Git worktree registry could not be read unambiguously"
            )
        records: list[dict[str, str]] = []
        for block in listing.stdout.split("\0\0"):
            if not block:
                continue
            record: dict[str, str] = {}
            for field in block.split("\0"):
                label, _, value = field.partition(" ")
                if not label or label in record:
                    raise TaskStateError(
                        "Git worktree registry has duplicate or malformed attributes"
                    )
                record[label] = value
            if "worktree" not in record or not Path(record["worktree"]).is_absolute():
                raise TaskStateError(
                    "Git worktree registry has an invalid checkout path"
                )
            records.append(record)
        if not records or "bare" in records[0]:
            raise TaskStateError("a real main checkout could not be established")
        current = [
            record for record in records if Path(record["worktree"]) == tasks.root
        ]
        if len(current) != 1 or records[0] is current[0]:
            raise TaskStateError(
                "linked worktree registry does not match this checkout"
            )
        main = TaskStore(Path(records[0]["worktree"]), read_only=True)
        actual_main_root = self._git_path(main, "--show-toplevel")
        main_git_dir = self._git_path(main, "--absolute-git-dir")
        main_common = self._git_path(main, "--path-format=absolute", "--git-common-dir")
        if (
            actual_main_root != main.root
            or main_git_dir != common
            or main_common != common
        ):
            raise TaskStateError(
                "main checkout does not share this repository's verified metadata"
            )
        return "linked", main

    def resolve(self) -> IdentityResult:
        local_path = str(self.tasks.root / _IDENTITY_PATH)
        try:
            local = self._read_name(self.tasks)
        except (TaskDataError, OSError, RuntimeError):
            return IdentityResult(
                "conflict",
                path=local_path,
                reason="local developer identity or its parent path is malformed, unsafe or unreadable",
            )
        if local is not None:
            return IdentityResult("ready", local, "local", local_path)
        try:
            topology, main = self._topology()
        except (TaskDataError, OSError, RuntimeError):
            return IdentityResult(
                "blocked",
                path=local_path,
                topology="unknown",
                reason="checkout ownership is unknown; do not create identity or guess a main checkout",
            )
        if main is not None:
            main_path = str(main.root / _IDENTITY_PATH)
            try:
                inherited = self._read_name(main)
            except (TaskDataError, OSError, RuntimeError):
                return IdentityResult(
                    "conflict",
                    path=main_path,
                    topology=topology,
                    reason="main checkout identity or its parent path is malformed, unsafe or unreadable",
                )
            if inherited is not None:
                return IdentityResult(
                    "ready", inherited, "main-worktree", main_path, topology=topology
                )
        return IdentityResult(
            "needs-name",
            path=local_path,
            first_write_eligible=True,
            topology=topology,
            reason="ask for a valid developer name and narrow write/protection authorization only when identity is needed",
        )

    def plan(self, name: str) -> IdentityResult:
        try:
            validate_developer_name(name)
        except (argparse.ArgumentTypeError, TypeError):
            return IdentityResult(
                "conflict",
                reason="requested developer name must match lowercase letters and digits exactly",
            )
        resolved = self.resolve()
        if resolved.status == "ready":
            if resolved.name != name:
                return replace(
                    resolved,
                    status="conflict",
                    reason="the existing developer identity differs; preserve it and ask for an explicit identity policy",
                )
            return replace(
                resolved,
                status="unchanged",
                reason="the same verified identity is already available; do not rewrite or copy it",
            )
        if not resolved.first_write_eligible:
            return resolved
        try:
            binding = self.tasks.current_binding()
            self.tasks._require_untracked_local_state(binding)
            protected = self.tasks._local_protected(binding, (".sbtd/", _IDENTITY_PATH))
            reserved = self.tasks._path(".sbtd")
            if (
                not protected
                and reserved.exists()
                and (not reserved.is_dir() or any(reserved.iterdir()))
            ):
                return replace(
                    resolved,
                    status="conflict",
                    first_write_eligible=False,
                    reason="identity protection would hide existing reserved data; preserve it",
                )
        except (TaskDataError, OSError, RuntimeError):
            return replace(
                resolved,
                status="blocked",
                first_write_eligible=False,
                reason="identity target protection or tracked state cannot be safely established",
            )
        return replace(
            resolved,
            status="planned",
            name=name,
            reason="create only the verified missing identity after explicit confirmation",
            needs_protection=not protected,
        )

    def ensure(
        self, name: str, *, confirmed: bool = False, protect: bool = False
    ) -> IdentityResult:
        planned = self.plan(name)
        if planned.status != "planned":
            return planned
        if not confirmed:
            return replace(
                planned,
                status="needs-confirmation",
                reason="identity creation has not been authorized",
            )
        try:
            self.tasks._authorize(confirmed)
        except TaskDataError:
            return replace(
                planned,
                status="blocked",
                reason="read-only scope does not permit identity or protection writes",
            )
        if planned.needs_protection and not protect:
            return replace(
                planned,
                status="needs-protection",
                reason="authorize only the necessary local ignore protection before creating identity",
            )
        completed: list[str] = []
        try:
            if planned.needs_protection:
                try:
                    protected = self.tasks.protect_local_state(confirmed=True)
                except TaskStateError as error:
                    completed.extend(error.completed_steps)
                    raise
                if protected:
                    completed.append(".gitignore")
            current = self.resolve()
            if current.status == "ready":
                if current.name == name:
                    return replace(
                        current, status="unchanged", completed_steps=tuple(completed)
                    )
                return replace(
                    current,
                    status="conflict",
                    reason="identity changed before creation; preserve the existing winner",
                    completed_steps=tuple(completed),
                )
            if not current.first_write_eligible:
                return replace(current, completed_steps=tuple(completed))
            self.tasks._require_local_protection(
                self.tasks.current_binding(), _IDENTITY_PATH
            )
            self.tasks._write(_IDENTITY_PATH, f"name={name}\n".encode(), None)
            completed.append(_IDENTITY_PATH)
            verified = self.resolve()
            if (
                verified.status != "ready"
                or verified.source != "local"
                or verified.name != name
            ):
                return replace(
                    verified,
                    status="failed",
                    reason="identity creation could not be verified by readback",
                    completed_steps=tuple(completed),
                )
            return replace(
                verified,
                status="created",
                reason="identity was created without overwriting existing content and verified by readback",
                completed_steps=tuple(completed),
            )
        except (TaskDataError, OSError, RuntimeError):
            return replace(
                planned,
                status="failed",
                reason="identity initialization stopped; preserve any existing file and inspect the completed steps",
                completed_steps=tuple(completed),
            )
