from __future__ import annotations

import json
import unittest
from datetime import datetime
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    ROOT
    / "sbtd-workflow-onboard"
    / "templates"
    / "skills"
    / "sbtd-task"
    / "references"
    / "task-data.schema.json"
)


class TaskDataSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(cls.schema)
        cls.format_checker = jsonschema.FormatChecker()

        @cls.format_checker.checks("date-time", raises=ValueError)
        def is_timestamp(value: object) -> bool:
            if not isinstance(value, str):
                return True
            return (
                datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
            )

    def validate(self, definition: str, record: dict) -> None:
        schema = {**self.schema, "$ref": f"#/$defs/{definition}"}
        jsonschema.Draft202012Validator(
            schema, format_checker=self.format_checker
        ).validate(record)

    def task(self, **changes: object) -> dict:
        record = {
            "schema_version": 1,
            "id": "import/customer-records",
            "workflow_mode": "lite",
            "mode_source": "user",
            "mode_note": "用户选择短清单",
            "status": "planned",
            "parent": "import",
            "branch": "feature/customer-import",
            "created_at": "2026-09-17T10:00:00+08:00",
            "updated_at": "2026-09-17T10:00:00+08:00",
            "completed_at": None,
        }
        record.update(changes)
        return record

    def test_unknown_mode_is_reserved_for_unresolved_migration(self) -> None:
        self.validate(
            "taskFrontmatter",
            self.task(workflow_mode=None, mode_source="migration-unknown"),
        )
        with self.assertRaises(jsonschema.ValidationError):
            self.validate("taskFrontmatter", self.task(workflow_mode=None))
        with self.assertRaises(jsonschema.ValidationError):
            self.validate("taskFrontmatter", self.task(mode_source="migration-unknown"))

    def test_implicit_source_cannot_select_a_nondefault_mode(self) -> None:
        self.validate(
            "taskFrontmatter", self.task(workflow_mode="default", mode_source="default")
        )
        with self.assertRaises(jsonschema.ValidationError):
            self.validate("taskFrontmatter", self.task(mode_source="default"))

    def test_blocked_reason_is_present_only_while_blocked(self) -> None:
        self.validate(
            "taskFrontmatter",
            self.task(status="blocked", blocked_reason="等待明确的迁移授权"),
        )
        for record in (
            self.task(status="blocked"),
            self.task(status="blocked", blocked_reason="   "),
            self.task(blocked_reason="已经解除的阻塞"),
            self.task(blocked_from="checking"),
        ):
            with (
                self.subTest(record=record),
                self.assertRaises(jsonschema.ValidationError),
            ):
                self.validate("taskFrontmatter", record)

    def test_reopened_task_cannot_keep_current_completion_time(self) -> None:
        completed_at = "2026-09-17T11:00:00+08:00"
        self.validate(
            "taskFrontmatter", self.task(status="done", completed_at=completed_at)
        )
        self.validate("taskFrontmatter", self.task(status="done", completed_at=None))
        with self.assertRaises(jsonschema.ValidationError):
            self.validate(
                "taskFrontmatter",
                self.task(status="planned", completed_at=completed_at),
            )

    def test_unblocking_cannot_skip_directly_to_completion(self) -> None:
        event = {
            "at": "2026-09-17T11:00:00+08:00",
            "from": "blocked",
            "to": "checking",
            "reason": "依赖恢复，回到之前的验证阶段",
            "evidence": "reports/recovery.md",
        }
        self.validate("stateEvent", event)
        with self.assertRaises(jsonschema.ValidationError):
            self.validate("stateEvent", {**event, "to": "done"})

    def test_continuing_block_is_not_a_new_block_entry(self) -> None:
        event = {
            "at": "2026-09-17T11:00:00+08:00",
            "from": "checking",
            "to": "blocked",
            "reason": "等待独立验证环境",
            "evidence": "reports/check.md",
        }
        self.validate("blockEntryEvent", event)
        continued = {**event, "from": "blocked"}
        with self.assertRaises(jsonschema.ValidationError):
            self.validate("blockEntryEvent", continued)
        with self.assertRaises(jsonschema.ValidationError):
            self.validate("blockEntryEvent", {**event, "at": "unknown"})
        self.validate(
            "stateEvent",
            {**continued, "reason": "用户明确重绑定分支，状态仍为 blocked"},
        )

    def test_active_pointer_cannot_escape_or_duplicate_task_state(self) -> None:
        pointer = {
            "schema_version": 1,
            "task_id": "import/customer-records",
            "task_path": ".sbtd/tasks/import/customer-records/task.md",
        }
        self.validate("activeTask", pointer)
        self.validate(
            "activeTask",
            {
                **pointer,
                "task_path": "ai/tasks/archive/2026-Q3/import/customer-records/task.md",
            },
        )
        for path in (
            "/ai/tasks/import/customer-records/task.md",
            ".sbtd/tasks/import/../customer-records/task.md",
            ".sbtd/tasks/import/customer-records/notes.md",
            "ai\\tasks\\import\\customer-records\\task.md",
            "other-project/tasks/import/customer-records/task.md",
            "ai/tasks/import/customer-records/task.md\n",
            ".sbtd/tasks/import/customer\u007frecords/task.md",
            ".sbtd/tasks/import/customer\u0085records/task.md",
        ):
            with self.subTest(path=path), self.assertRaises(jsonschema.ValidationError):
                self.validate("activeTask", {**pointer, "task_path": path})
        with self.assertRaises(jsonschema.ValidationError):
            self.validate("activeTask", {**pointer, "workflow_mode": "strict"})

    def test_schema_version_is_not_boolean_or_future_version(self) -> None:
        for version in (True, 2):
            with (
                self.subTest(version=version),
                self.assertRaises(jsonschema.ValidationError),
            ):
                self.validate("taskFrontmatter", self.task(schema_version=version))

    def test_unknown_history_does_not_authorize_naive_timestamps(self) -> None:
        self.validate(
            "taskFrontmatter",
            self.task(
                workflow_mode=None,
                mode_source="migration-unknown",
                created_at=None,
                updated_at=None,
            ),
        )
        for timestamp in ("2026-09-17T10:00:00", "2026-02-31T10:00:00+08:00"):
            with (
                self.subTest(timestamp=timestamp),
                self.assertRaises(jsonschema.ValidationError),
            ):
                self.validate("taskFrontmatter", self.task(created_at=timestamp))
        historical = {
            "at": "unknown",
            "from": "unknown",
            "to": "done",
            "reason": "旧记录已完成，缺原始完成时间",
            "evidence": "not-recorded",
        }
        self.validate("stateEvent", historical)
        with self.assertRaises(jsonschema.ValidationError):
            self.validate("stateEvent", {**historical, "to": "planned"})

    def test_cancelled_status_never_carries_completion_or_block_reason(self) -> None:
        self.validate("taskFrontmatter", self.task(status="cancelled"))
        self.validate(
            "taskFrontmatter", self.task(status="cancelled", blocked_reason=None)
        )
        with self.assertRaises(jsonschema.ValidationError):
            self.validate(
                "taskFrontmatter",
                self.task(
                    status="cancelled", completed_at="2026-09-17T11:00:00+08:00"
                ),
            )
        with self.assertRaises(jsonschema.ValidationError):
            self.validate(
                "taskFrontmatter",
                self.task(status="cancelled", blocked_reason="取消前记录的阻塞"),
            )

    def test_cancellation_events_follow_terminal_and_reopen_rules(self) -> None:
        event = {
            "at": "2026-09-17T11:00:00+08:00",
            "from": "planned",
            "to": "cancelled",
            "reason": "范围被上游决定取消",
            "evidence": "reports/cancellation.md",
        }
        for source in ("planned", "in-progress", "checking", "blocked", "cancelled"):
            with self.subTest(source=source):
                self.validate("stateEvent", {**event, "from": source})
        self.validate("stateEvent", {**event, "from": "cancelled", "to": "planned"})
        for transition in (
            {"from": "done", "to": "cancelled"},
            {"from": "cancelled", "to": "in-progress"},
            {"from": "cancelled", "to": "checking"},
            {"from": "cancelled", "to": "done"},
            {"from": "cancelled", "to": "blocked"},
        ):
            with (
                self.subTest(transition=transition),
                self.assertRaises(jsonschema.ValidationError),
            ):
                self.validate("stateEvent", {**event, **transition})

    def test_historical_terminal_facts_are_not_real_ingress(self) -> None:
        for target in ("cancelled", "blocked"):
            with self.subTest(target=target):
                self.validate(
                    "stateEvent",
                    {
                        "at": "unknown",
                        "from": "unknown",
                        "to": target,
                        "reason": "旧记录中的终态事实，缺原始时间",
                        "evidence": "not-recorded",
                    },
                )
        blocked_fact = {
            "at": "2026-09-17T11:00:00+08:00",
            "from": "unknown",
            "to": "blocked",
            "reason": "旧记录中的阻塞事实",
            "evidence": "not-recorded",
        }
        self.validate("stateEvent", blocked_fact)
        with self.assertRaises(jsonschema.ValidationError):
            self.validate("blockEntryEvent", blocked_fact)


if __name__ == "__main__":
    unittest.main()
