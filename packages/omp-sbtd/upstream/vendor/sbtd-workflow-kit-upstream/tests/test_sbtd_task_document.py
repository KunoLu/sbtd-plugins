from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sbtd-workflow-onboard" / "scripts"))

from sbtd_task_document import TaskDocument


class TaskDocumentTests(unittest.TestCase):
    def test_status_and_event_update_preserves_unowned_yaml_and_body(self) -> None:
        original = """---
schema_version: 1
id: parent/child
workflow_mode: default
mode_source: default
mode_note: implicit new task
status: planned # retain this comment
branch: main
created_at: 2026-09-18T12:00:00+08:00
updated_at: 2026-09-18T12:00:00+08:00
completed_at: null
extension: # user-owned formatting
  quoted: 'leave this quoted'
  nested: [1, true, null]
---
# Task body

Keep this body **exactly**.

```markdown
## 状态事件
This is an example, not an event table.
```
"""
        document = TaskDocument.parse(original)
        event = {
            "at": "2026-09-18T12:01:00+08:00",
            "from": "planned",
            "to": "in-progress",
            "reason": "A | B\n<next> & literal &#124;",
            "evidence": "approved task scope",
        }
        changed = document.updated(
            {"status": "in-progress", "updated_at": event["at"]}, event=event
        )
        reread = TaskDocument.parse(changed.text)
        self.assertEqual(reread.frontmatter["status"], "in-progress")
        self.assertEqual(reread.events, (event,))
        self.assertEqual(
            reread.frontmatter["extension"], document.frontmatter["extension"]
        )
        self.assertIn(" # retain this comment\n", changed.text)
        self.assertIn(
            "extension: # user-owned formatting\n  quoted: 'leave this quoted'\n  nested: [1, true, null]",
            changed.text,
        )
        self.assertIn(original.split("---\n", 2)[2], changed.text)

    def test_block_reason_can_be_added_without_rewriting_flow_frontmatter(self) -> None:
        metadata = {
            "schema_version": 1,
            "id": "task",
            "workflow_mode": "default",
            "mode_source": "default",
            "mode_note": "new task",
            "status": "planned",
            "branch": None,
            "created_at": "2026-09-18T12:00:00Z",
            "updated_at": "2026-09-18T12:00:00Z",
            "completed_at": None,
            "extension": {"preserved": [True, "literal | content"]},
        }
        document = TaskDocument.parse("---\n" + json.dumps(metadata) + "\n---\nBody\n")
        event = {
            "at": "2026-09-18T12:01:00Z",
            "from": "planned",
            "to": "blocked",
            "reason": "waiting on permission",
            "evidence": "permission not granted",
        }
        blocked = document.updated(
            {
                "status": "blocked",
                "blocked_reason": event["reason"],
                "updated_at": event["at"],
            },
            event=event,
        )
        self.assertEqual(blocked.frontmatter["blocked_reason"], event["reason"])
        self.assertEqual(blocked.frontmatter["extension"], metadata["extension"])
        self.assertEqual(blocked.events, (event,))
        self.assertIn("\n---\nBody\n", blocked.text)


    def test_event_boundary_whitespace_round_trips(self) -> None:
        document = TaskDocument.parse(
            """---
schema_version: 1
id: task
workflow_mode: default
mode_source: default
mode_note: new task
status: planned
branch: null
created_at: 2026-09-18T12:00:00Z
updated_at: 2026-09-18T12:00:00Z
completed_at: null
---
Body
"""
        )
        event = {
            "at": "2026-09-18T12:01:00Z",
            "from": "planned",
            "to": "in-progress",
            "reason": " \tkeep boundary whitespace\t ",
            "evidence": "\tconfirmed by user\t",
        }
        changed = document.updated(
            {"status": "in-progress", "updated_at": event["at"]}, event=event
        )
        self.assertEqual(TaskDocument.parse(changed.text).events, (event,))

    def test_event_append_adds_separator_after_eof_table_row(self) -> None:
        document = TaskDocument.parse(
            """---
schema_version: 1
id: task
workflow_mode: default
mode_source: default
mode_note: new task
status: in-progress
branch: null
created_at: 2026-09-18T12:00:00Z
updated_at: 2026-09-18T12:01:00Z
completed_at: null
---
## 状态事件

| at | from | to | reason | evidence |
|---|---|---|---|---|
| 2026-09-18T12:01:00Z | planned | in-progress | started | approved |"""
        )
        event = {
            "at": "2026-09-18T12:02:00Z",
            "from": "in-progress",
            "to": "checking",
            "reason": "implemented",
            "evidence": "review requested",
        }
        changed = document.updated(
            {"status": "checking", "updated_at": event["at"]}, event=event
        )
        self.assertIn("approved |\n| 2026-09-18T12:02:00Z", changed.text)
        self.assertEqual(changed.events[-1], event)

    def test_flow_frontmatter_comment_after_trailing_comma_is_preserved(self) -> None:
        document = TaskDocument.parse(
            """---
{schema_version: 1, id: task, workflow_mode: default, mode_source: default, mode_note: new task, status: planned, branch: null, created_at: 2026-09-18T12:00:00Z, updated_at: 2026-09-18T12:00:00Z, completed_at: null, # retain this comment
}
---
Body
"""
        )
        changed = document.updated({"parent": None})
        self.assertIsNone(changed.frontmatter["parent"])
        self.assertIn("# retain this comment", changed.text)

    def test_block_scalar_header_comment_survives_value_replacement(self) -> None:
        document = TaskDocument.parse(
            """---
schema_version: 1
id: task
workflow_mode: default
mode_source: default
mode_note: |- # retain this annotation
  old task note
status: planned
branch: null
created_at: 2026-09-18T12:00:00Z
updated_at: 2026-09-18T12:00:00Z
completed_at: null
---
Body
"""
        )
        changed = document.updated({"mode_note": "new task note"})
        self.assertEqual(changed.frontmatter["mode_note"], "new task note")
        self.assertIn("# retain this annotation", changed.text)

    def test_crlf_block_scalar_comment_replacement_does_not_double_carriage_return(
        self,
    ) -> None:
        original = (
            "---\n"
            "schema_version: 1\n"
            "id: task\n"
            "workflow_mode: default\n"
            "mode_source: default\n"
            "mode_note: |- # retain this annotation\n"
            "  old task note\n"
            "status: planned\n"
            "branch: null\n"
            "created_at: 2026-09-18T12:00:00Z\n"
            "updated_at: 2026-09-18T12:00:00Z\n"
            "completed_at: null\n"
            "---\n"
            "Body\n"
        ).replace("\n", "\r\n")
        changed = TaskDocument.parse(original).updated({"mode_note": "new task note"})
        self.assertNotIn("\r\r\n", changed.text)
        self.assertIn("mode_note: \"new task note\" # retain this annotation\r\n", changed.text)


if __name__ == "__main__":
    unittest.main()
