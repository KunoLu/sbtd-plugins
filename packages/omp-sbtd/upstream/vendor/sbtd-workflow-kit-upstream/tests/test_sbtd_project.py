from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "sbtd-workflow-onboard" / "scripts" / "sbtd_project.py"
sys.path.insert(0, str(MODULE_PATH.parent))

import sbtd_project

try:
    import yaml
except ImportError:  # pragma: no cover - requirements declare PyYAML
    yaml = None

VALIDATION_SCOPE = "selected-state-shape-and-containment"


def task_text(
    task_id: str = "example",
    *,
    schema_version: int = 1,
    status: str = "planned",
    workflow_mode: str = "default",
    mode_source: str = "default",
    created_at: str = "2026-09-18T10:00:00Z",
    completed_at: str = "null",
    extra_frontmatter: str = "",
) -> str:
    # Timestamps stay unquoted on purpose: a loader that converts them to
    # datetime objects would fail the schema, proving they remain strings.
    blocked = "blocked_reason: waiting on user\n" if status == "blocked" else ""
    return (
        "---\n"
        f"schema_version: {schema_version}\n"
        f"id: {task_id}\n"
        f"workflow_mode: {workflow_mode}\n"
        f"mode_source: {mode_source}\n"
        "mode_note: recorded explicitly\n"
        f"status: {status}\n"
        "branch: main\n"
        f"created_at: {created_at}\n"
        "updated_at: 2026-09-18T10:00:00Z\n"
        f"completed_at: {completed_at}\n"
        f"{blocked}{extra_frontmatter}"
        "---\n"
        "\n# Task body\n\nThe body is never parsed by the inspector.\n"
    )


def tree_snapshot(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        base = Path(dirpath)
        for name in sorted(dirnames):
            path = base / name
            rel = str(path.relative_to(root)) + "/"
            snapshot[rel] = (
                "symlink:" + os.readlink(path) if path.is_symlink() else "dir"
            )
        for name in sorted(filenames):
            path = base / name
            rel = str(path.relative_to(root))
            if path.is_symlink():
                snapshot[rel] = "symlink:" + os.readlink(path)
            else:
                snapshot[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


class ProjectStateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="sbtd-project-state-test-")
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.project = self.root / "project"
        self.project.mkdir()

    def inspect(self) -> sbtd_project.StateInspection:
        result = sbtd_project.inspect_project_state(self.project)
        json.dumps(result)  # stdout reporting requires one JSON document
        self.assertEqual(result["validationScope"], VALIDATION_SCOPE)
        for key in (
            "status",
            "reason",
            "nextStep",
            "activeTask",
            "bootstrapTask",
            "legacyPresent",
        ):
            self.assertIn(key, result)
        return result

    def write_task(self, relative: str, text: str | None = None, **kwargs) -> Path:
        target = self.project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            text if text is not None else task_text(**kwargs), encoding="utf-8"
        )
        return target

    def write_pointer(
        self,
        task_id: str = "example",
        task_path: str = ".sbtd/tasks/example/task.md",
        raw: str | None = None,
    ) -> Path:
        target = self.project / ".sbtd" / "active-task.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        if raw is None:
            raw = (
                json.dumps(
                    {
                        "schema_version": 1,
                        "task_id": task_id,
                        "task_path": task_path,
                    }
                )
                + "\n"
            )
        target.write_text(raw, encoding="utf-8")
        return target

    def write_bootstrap(self, text: str | None = None, **kwargs) -> Path:
        kwargs.setdefault("task_id", "00-bootstrap-guidelines")
        return self.write_task(
            "ai/tasks/00-bootstrap-guidelines/task.md", text, **kwargs
        )

    def assert_summary(
        self,
        summary: sbtd_project.TaskSummary | None,
        relative: str,
        task_id: str,
        status: str,
        mode: object,
    ) -> None:
        self.assertEqual(
            summary,
            {
                "relativePath": relative,
                "id": task_id,
                "status": status,
                "workflowMode": mode,
            },
        )


class AbsenceTests(ProjectStateTestCase):
    def test_empty_project_is_success_and_creates_nothing(self) -> None:
        before = tree_snapshot(self.project)

        result = self.inspect()

        self.assertEqual(result["status"], "success")
        self.assertIsNone(result["activeTask"])
        self.assertIsNone(result["bootstrapTask"])
        self.assertFalse(result["legacyPresent"])

        self.assertEqual(tree_snapshot(self.project), before)
        self.assertFalse(os.path.lexists(self.project / ".sbtd"))

    def test_state_containers_without_pointer_or_bootstrap_are_success(self) -> None:
        (self.project / ".sbtd" / "tasks").mkdir(parents=True)
        (self.project / "ai" / "tasks").mkdir(parents=True)

        result = self.inspect()

        self.assertEqual(result["status"], "success")
        self.assertIsNone(result["activeTask"])
        self.assertIsNone(result["bootstrapTask"])

    def test_missing_root_is_blocked(self) -> None:
        result = sbtd_project.inspect_project_state(self.root / "missing")

        self.assertEqual(result["status"], "blocked")

    def test_file_as_root_is_blocked(self) -> None:
        target = self.root / "file-root"
        target.write_text("not a directory", encoding="utf-8")

        result = sbtd_project.inspect_project_state(target)

        self.assertEqual(result["status"], "blocked")


class ActivePointerTests(ProjectStateTestCase):
    def test_valid_local_pointer_reports_summary(self) -> None:
        self.write_pointer()
        self.write_task(".sbtd/tasks/example/task.md", status="in-progress")

        result = self.inspect()

        self.assertEqual(result["status"], "success")
        self.assert_summary(
            result["activeTask"],
            ".sbtd/tasks/example/task.md",
            "example",
            "in-progress",
            "default",
        )
        self.assertIsNone(result["bootstrapTask"])

    def test_valid_shared_pointer_reports_summary(self) -> None:
        self.write_pointer(
            task_id="parent/child", task_path="ai/tasks/parent/child/task.md"
        )
        self.write_task("ai/tasks/parent/child/task.md", task_id="parent/child")

        result = self.inspect()

        self.assertEqual(result["status"], "success")
        self.assert_summary(
            result["activeTask"],
            "ai/tasks/parent/child/task.md",
            "parent/child",
            "planned",
            "default",
        )

    def test_archive_storage_path_need_not_match_id_spelling(self) -> None:
        self.write_pointer(
            task_id="example",
            task_path="ai/tasks/archive/2026-Q1/archived-copy/task.md",
        )
        self.write_task(
            "ai/tasks/archive/2026-Q1/archived-copy/task.md",
            task_id="example",
            status="done",
            completed_at="2026-09-17T11:00:00+08:00",
        )

        result = self.inspect()

        self.assertEqual(result["status"], "success")
        self.assert_summary(
            result["activeTask"],
            "ai/tasks/archive/2026-Q1/archived-copy/task.md",
            "example",
            "done",
            "default",
        )

    def test_task_extensions_are_preserved_and_not_serialized(self) -> None:
        self.write_pointer()
        task = self.write_task(
            ".sbtd/tasks/example/task.md",
            extra_frontmatter=(
                "custom_extension:\n  nested: [1, 2.5, true, null]\n  note: 中文备注\n"
            ),
        )
        before = task.read_bytes()

        result = self.inspect()

        self.assertEqual(result["status"], "success")
        self.assertEqual(task.read_bytes(), before)

    def test_pointer_malformed_json_is_blocked(self) -> None:
        self.write_pointer(raw='{"schema_version": 1, "task_id": }')

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

        self.assertIsNone(result["activeTask"])

    def test_pointer_duplicate_keys_are_blocked(self) -> None:
        self.write_pointer(
            raw=(
                '{"schema_version": 1, "schema_version": 1, '
                '"task_id": "example", "task_path": ".sbtd/tasks/example/task.md"}'
            )
        )

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_pointer_nonfinite_numbers_are_blocked(self) -> None:
        for version in ("NaN", "Infinity", "1e999"):
            with self.subTest(version=version):
                self.write_pointer(
                    raw=(
                        f'{{"schema_version": {version}, "task_id": "example", '
                        '"task_path": ".sbtd/tasks/example/task.md"}'
                    )
                )

                result = self.inspect()

                self.assertEqual(result["status"], "blocked")

    def test_pointer_schema_violations_are_blocked(self) -> None:
        for raw in (
            # task_path escapes the project lexically
            '{"schema_version": 1, "task_id": "example", "task_path": "../example/task.md"}',
            # unknown schema versions are not silently interpreted
            '{"schema_version": 2, "task_id": "example", "task_path": ".sbtd/tasks/example/task.md"}',
            # bookmark fields only; no mode/status duplication
            '{"schema_version": 1, "task_id": "example", "task_path": ".sbtd/tasks/example/task.md", "status": "done"}',
        ):
            with self.subTest(raw=raw):
                self.write_pointer(raw=raw)

                result = self.inspect()

                self.assertEqual(result["status"], "blocked")

    def test_pointer_to_missing_task_is_blocked(self) -> None:
        self.write_pointer()

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_pointer_id_must_match_task_frontmatter(self) -> None:
        self.write_pointer(task_id="example")
        self.write_task(".sbtd/tasks/example/task.md", task_id="someone-else")

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_task_id_must_match_non_archive_storage_path(self) -> None:
        # Pointer and frontmatter agree with each other but not with the path.
        self.write_pointer(task_id="someone-else")
        self.write_task(".sbtd/tasks/example/task.md", task_id="someone-else")

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_pointer_directory_is_blocked(self) -> None:
        (self.project / ".sbtd" / "active-task.json").mkdir(parents=True)

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_migration_unknown_mode_needs_user_choice(self) -> None:
        self.write_pointer()
        self.write_task(
            ".sbtd/tasks/example/task.md",
            workflow_mode="null",
            mode_source="migration-unknown",
        )

        result = self.inspect()

        self.assertEqual(result["status"], "needs-user")

        self.assert_summary(
            result["activeTask"],
            ".sbtd/tasks/example/task.md",
            "example",
            "planned",
            None,
        )


class TaskRecordTests(ProjectStateTestCase):
    def prepare(self, text: str | None = None, **kwargs) -> Path:
        self.write_pointer()
        return self.write_task(".sbtd/tasks/example/task.md", text, **kwargs)

    def test_invalid_yaml_syntax_is_blocked(self) -> None:
        self.prepare(task_text("example").replace("id: example", "id: [unclosed"))

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_duplicate_yaml_keys_are_blocked(self) -> None:
        text = task_text("example").replace(
            "status: planned", "status: planned\nstatus: done"
        )
        self.prepare(text)

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_unsafe_yaml_tags_are_blocked(self) -> None:
        self.prepare(
            task_text(
                "example",
                extra_frontmatter='exploit: !!python/object/apply:os.system ["id"]\n',
            )
        )

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_non_json_yaml_types_are_blocked(self) -> None:
        for extra in ("blob: !!binary aGk=\n", "tags: !!set {a, b}\n"):
            with self.subTest(extra=extra):
                self.prepare(task_text("example", extra_frontmatter=extra))

                result = self.inspect()

                self.assertEqual(result["status"], "blocked")

    def test_shared_alias_dag_is_checked_once_per_call(self) -> None:
        shared: list[object] = [1]
        for _ in range(10):
            shared = [shared, shared]
        data = {"first": shared, "second": shared}
        checker = sbtd_project.validate_json_compatible
        with mock.patch.object(
            sbtd_project, "validate_json_compatible", wraps=checker
        ) as checked:
            sbtd_project.validate_json_compatible(data, "task")
        self.assertLess(checked.call_count, 30)

        shared.append(object())
        with self.assertRaises(sbtd_project.TaskDataError):
            sbtd_project.validate_json_compatible(data, "task")

    def test_cyclic_yaml_aliases_are_blocked(self) -> None:
        self.prepare(task_text("example", extra_frontmatter="loop: &loop\n  - *loop\n"))

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_nonfinite_yaml_numbers_are_blocked(self) -> None:
        for literal in (".inf", ".nan"):
            with self.subTest(literal=literal):
                self.prepare(
                    task_text("example", extra_frontmatter=f"score: {literal}\n")
                )

                result = self.inspect()

                self.assertEqual(result["status"], "blocked")

    def test_missing_frontmatter_block_is_blocked(self) -> None:
        self.prepare("# just a markdown file\n")

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_unterminated_frontmatter_is_blocked(self) -> None:
        self.prepare("---\nschema_version: 1\nid: example\n")

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_empty_frontmatter_is_blocked(self) -> None:
        self.prepare("---\n---\n# empty\n")

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_wrong_schema_version_is_blocked(self) -> None:
        self.prepare(task_text("example", schema_version=2))

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_missing_required_field_is_blocked(self) -> None:
        self.prepare(task_text("example").replace("status: planned\n", ""))

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_impossible_calendar_date_is_blocked(self) -> None:
        self.prepare(task_text("example", created_at="2026-02-30T10:00:00Z"))

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_overflowing_timezone_offset_is_blocked(self) -> None:
        self.prepare(task_text("example", created_at="2026-09-18T10:00:00+08:60"))

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_invalid_utf8_task_is_blocked(self) -> None:
        self.write_pointer()
        target = self.project / ".sbtd" / "tasks" / "example" / "task.md"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"---\n\xff\xfe not utf-8\n---\n")

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_windows_reparse_metadata_is_rejected_for_selected_path_components(
        self,
    ) -> None:
        self.write_pointer()
        self.write_task(".sbtd/tasks/example/task.md")
        reparse = (self.project / ".sbtd" / "tasks").resolve()
        native_lstat = Path.lstat

        def lstat(path: Path):
            metadata = native_lstat(path)
            if path == reparse:
                return SimpleNamespace(
                    st_mode=metadata.st_mode,
                    st_file_attributes=0x400,
                )
            return metadata

        with (
            mock.patch.object(
                sbtd_project.stat,
                "FILE_ATTRIBUTE_REPARSE_POINT",
                0x400,
                create=True,
            ),
            mock.patch.object(Path, "lstat", new=lstat),
        ):
            result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_open_regular_file_rejects_reparse_ancestor_metadata(self) -> None:
        parent = self.project / "junction"
        parent.mkdir()
        target = parent / "task.md"
        target.write_text("safe content", encoding="utf-8")
        native_lstat = Path.lstat

        def lstat(path: Path):
            metadata = native_lstat(path)
            if path == parent:
                return SimpleNamespace(
                    st_mode=metadata.st_mode,
                    st_file_attributes=0x400,
                )
            return metadata

        with (
            mock.patch.object(
                sbtd_project.stat,
                "FILE_ATTRIBUTE_REPARSE_POINT",
                0x400,
                create=True,
            ),
            mock.patch.object(Path, "lstat", new=lstat),
            self.assertRaises(sbtd_project.TaskDataError),
            sbtd_project.open_regular_file(target, "task"),
        ):
            pass

    def test_errors_never_echo_body_or_private_extension_values(self) -> None:
        secret = "hunter2-private-token"
        text = task_text("example").replace("status: planned\n", "")
        text = text.replace(
            "completed_at: null\n",
            f"completed_at: null\nprivate_extension: {secret}\n",
        )
        text += f"\nBody leak candidate: {secret}\n"
        self.prepare(text)

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")
        self.assertNotIn(secret, json.dumps(result))


class ContainmentTests(ProjectStateTestCase):
    def write_outside_task(self) -> Path:
        outside = self.root / "outside" / "task.md"
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_text(task_text("example"), encoding="utf-8")
        return outside

    def test_task_symlink_escape_is_blocked(self) -> None:
        outside = self.write_outside_task()
        task_dir = self.project / ".sbtd" / "tasks" / "example"
        task_dir.mkdir(parents=True)
        (task_dir / "task.md").symlink_to(outside)
        self.write_pointer()

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_parent_symlink_escape_is_blocked(self) -> None:
        outside_root = self.root / "outside-tasks"
        (outside_root / "example").mkdir(parents=True)
        (outside_root / "example" / "task.md").write_text(
            task_text("example"), encoding="utf-8"
        )
        (self.project / ".sbtd").mkdir()
        (self.project / ".sbtd" / "tasks").symlink_to(
            outside_root, target_is_directory=True
        )
        self.write_pointer()

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_dangling_symlink_is_distinct_from_absence(self) -> None:
        task_dir = self.project / ".sbtd" / "tasks" / "example"
        task_dir.mkdir(parents=True)
        (task_dir / "task.md").symlink_to(self.project / ".sbtd" / "tasks" / "gone.md")
        self.write_pointer()

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_task_wrong_type_is_blocked(self) -> None:
        (self.project / ".sbtd" / "tasks" / "example" / "task.md").mkdir(parents=True)
        self.write_pointer()

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_pointer_symlink_escape_is_blocked(self) -> None:
        outside = self.root / "outside-pointer.json"
        outside.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "task_id": "example",
                    "task_path": ".sbtd/tasks/example/task.md",
                }
            ),
            encoding="utf-8",
        )
        (self.project / ".sbtd").mkdir()
        (self.project / ".sbtd" / "active-task.json").symlink_to(outside)

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_unreadable_task_file_is_blocked(self) -> None:
        self.write_pointer()
        task = self.write_task(".sbtd/tasks/example/task.md")
        task.chmod(0)
        self.addCleanup(task.chmod, 0o644)
        try:
            task.read_bytes()
        except PermissionError:
            pass
        else:
            self.skipTest("filesystem does not enforce permission bits here")

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")


class BootstrapTaskTests(ProjectStateTestCase):
    def test_unfinished_bootstrap_is_required(self) -> None:
        self.write_bootstrap(status="planned")
        result = self.inspect()
        self.assertEqual(result["status"], "bootstrap-required")
        assert result["bootstrapTask"] is not None
        self.assertEqual(result["bootstrapTask"]["status"], "planned")

    def test_done_bootstrap_record_is_success_not_acceptance_proof(self) -> None:
        self.write_bootstrap(status="done", completed_at="2026-09-17T11:00:00+08:00")

        result = self.inspect()

        self.assertEqual(result["status"], "success")
        self.assert_summary(
            result["bootstrapTask"],
            "ai/tasks/00-bootstrap-guidelines/task.md",
            "00-bootstrap-guidelines",
            "done",
            "default",
        )

    def test_cancelled_bootstrap_is_not_a_completed_bootstrap(self) -> None:
        self.write_bootstrap(status="cancelled")

        result = self.inspect()

        self.assertEqual(result["status"], "bootstrap-required")
        assert result["bootstrapTask"] is not None
        self.assertEqual(result["bootstrapTask"]["status"], "cancelled")

    def test_cancelled_active_task_is_a_readable_terminal_record(self) -> None:
        self.write_task(".sbtd/tasks/example/task.md", status="cancelled")
        self.write_pointer()

        result = self.inspect()

        self.assertEqual(result["status"], "success")
        self.assert_summary(
            result["activeTask"],
            ".sbtd/tasks/example/task.md",
            "example",
            "cancelled",
            "default",
        )

    def test_malformed_bootstrap_is_blocked(self) -> None:
        self.write_bootstrap("---\nid: [unclosed\n---\n")

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_bootstrap_id_must_match_fixed_path(self) -> None:
        self.write_bootstrap(task_id="renamed-bootstrap")

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")


class LegacyAndDependencyTests(ProjectStateTestCase):
    def test_legacy_trellis_is_preserved_and_needs_migration_decision(self) -> None:
        legacy = self.project / ".trellis" / "tasks" / "00-bootstrap-guidelines"
        legacy.mkdir(parents=True)
        marker = legacy / "task.md"
        marker.write_text("legacy trellis content", encoding="utf-8")
        self.write_pointer()
        self.write_task(".sbtd/tasks/example/task.md")
        before = tree_snapshot(self.project)

        result = self.inspect()

        self.assertEqual(result["status"], "needs-user")
        self.assertTrue(result["legacyPresent"])

        # Legacy presence short-circuits: v2 state is not trusted until the
        # explicit migration decision, and nothing is read or changed.
        self.assertIsNone(result["activeTask"])
        self.assertIsNone(result["bootstrapTask"])
        self.assertEqual(tree_snapshot(self.project), before)
        self.assertEqual(marker.read_text(encoding="utf-8"), "legacy trellis content")

    def test_uninspectable_legacy_presence_is_unknown_not_absent(self) -> None:
        self.project.chmod(0)
        try:
            try:
                (self.project / ".trellis").lstat()
            except PermissionError:
                pass
            except FileNotFoundError:
                self.skipTest("permission bits do not restrict this test user")
            result = self.inspect()
            self.assertEqual(result["status"], "blocked")
            self.assertIsNone(result["legacyPresent"])
        finally:
            self.project.chmod(0o700)

    def test_missing_pyyaml_is_reported_not_raised(self) -> None:
        self.write_pointer()
        self.write_task(".sbtd/tasks/example/task.md")

        with mock.patch.dict(sys.modules, {"yaml": None}):
            result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    def test_missing_jsonschema_is_reported_not_raised(self) -> None:
        self.write_pointer()
        self.write_task(".sbtd/tasks/example/task.md")

        with mock.patch.dict(sys.modules, {"jsonschema": None}):
            result = self.inspect()

        self.assertEqual(result["status"], "blocked")

    @unittest.skipIf(yaml is None, "PyYAML is not installed")
    def test_pyyaml_global_resolver_state_is_not_mutated(self) -> None:
        self.write_pointer()
        self.write_task(".sbtd/tasks/example/task.md")

        result = self.inspect()

        self.assertEqual(result["status"], "success")
        assert yaml is not None
        loaded = yaml.safe_load("when: 2026-09-18\n")
        self.assertIsInstance(loaded["when"], date)


class PriorityTests(ProjectStateTestCase):
    def test_invalid_state_blocks_even_when_bootstrap_is_pending(self) -> None:
        self.write_pointer(raw="{not json")
        self.write_bootstrap()

        result = self.inspect()

        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["activeTask"])
        self.assertIsNotNone(result["bootstrapTask"])

    def test_unresolved_mode_needs_user_before_bootstrap_required(self) -> None:
        self.write_pointer()
        self.write_task(
            ".sbtd/tasks/example/task.md",
            workflow_mode="null",
            mode_source="migration-unknown",
        )
        self.write_bootstrap()

        result = self.inspect()

        self.assertEqual(result["status"], "needs-user")

    def test_valid_active_state_and_pending_bootstrap_is_bootstrap_required(
        self,
    ) -> None:
        self.write_pointer()
        self.write_task(
            ".sbtd/tasks/example/task.md",
            status="done",
            completed_at="2026-09-17T11:00:00Z",
        )
        self.write_bootstrap(status="in-progress")

        result = self.inspect()

        self.assertEqual(result["status"], "bootstrap-required")
        self.assertIsNotNone(result["activeTask"])
        self.assertIsNotNone(result["bootstrapTask"])

    def test_populated_project_is_never_modified(self) -> None:
        self.write_pointer()
        self.write_task(".sbtd/tasks/example/task.md")
        self.write_bootstrap(status="done", completed_at="2026-09-17T11:00:00Z")
        docs = self.project / "docs" / "notes.md"
        docs.parent.mkdir(parents=True)
        docs.write_text("user content", encoding="utf-8")
        before = tree_snapshot(self.project)

        result = self.inspect()

        self.assertEqual(result["status"], "success")
        self.assertEqual(tree_snapshot(self.project), before)


    def test_unused_unresolvable_task_root_does_not_block_selected_state(self) -> None:
        self.write_pointer(task_path="ai/tasks/example/task.md")
        self.write_task(
            "ai/tasks/example/task.md", workflow_mode="lite", mode_source="user"
        )
        (self.project / ".sbtd" / "tasks").symlink_to("tasks")

        result = self.inspect()

        self.assertEqual(result["status"], "success")

    def test_uninspectable_root_marks_legacy_presence_unknown(self) -> None:
        with mock.patch.object(
            sbtd_project,
            "_checked_root",
            side_effect=sbtd_project.TaskDataError("root unavailable", "repair root"),
        ):
            result = self.inspect()

        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["legacyPresent"])

    def test_invalid_bundled_schema_directs_repair_to_the_bundle(self) -> None:
        self.write_pointer()
        self.write_task(".sbtd/tasks/example/task.md")
        invalid = self.root / "invalid-task-data.schema.json"

        for content in (b"\xff", b'{"type": 1}'):
            with self.subTest(content=content):
                invalid.write_bytes(content)
                with mock.patch.object(sbtd_project, "_SCHEMA_PATH", invalid):
                    result = self.inspect()
                self.assertEqual(result["status"], "blocked")
                self.assertIn("task-data.schema.json", result["nextStep"])

    def test_dangling_bundled_schema_reference_directs_repair_to_bundle(self) -> None:
        self.write_pointer()
        self.write_task(".sbtd/tasks/example/task.md")
        dangling = self.root / "dangling-task-data.schema.json"
        schema = json.loads(sbtd_project._SCHEMA_PATH.read_text(encoding="utf-8"))
        del schema["$defs"]["activeTask"]
        dangling.write_text(json.dumps(schema), encoding="utf-8")

        with mock.patch.object(sbtd_project, "_SCHEMA_PATH", dangling):
            result = self.inspect()

        self.assertEqual(result["status"], "blocked")
        self.assertIn("task-data.schema.json", result["nextStep"])


    def test_cross_root_task_symlink_remains_contained(self) -> None:
        target = self.write_task("ai/tasks/example/task.md")
        local = self.project / ".sbtd" / "tasks" / "example"
        local.mkdir(parents=True)
        (local / "task.md").symlink_to(target)
        self.write_pointer()

        result = self.inspect()

        self.assertEqual(result["status"], "success")
if __name__ == "__main__":
    unittest.main()
