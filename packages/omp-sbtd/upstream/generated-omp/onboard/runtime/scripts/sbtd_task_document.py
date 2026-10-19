"""Task Markdown parsing and candidate updates; no filesystem writes."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Any

from sbtd_project import (
    TaskDataError,
    parse_task_frontmatter,
    validate_task_data,
    validate_task_timestamps,
)

_EVENT_COLUMNS = ("at", "from", "to", "reason", "evidence")
_REPAIR = "preserve the task and resolve its document conflict before writing"


def _frontmatter_bounds(text: str) -> tuple[int, int, int]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].removeprefix("\ufeff").rstrip("\r\n") != "---":
        raise TaskDataError("task has no YAML frontmatter block", _REPAIR)
    offset = len(lines[0])
    start = offset
    for line in lines[1:]:
        if line.rstrip("\r\n") == "---":
            return start, offset, offset + len(line)
        offset += len(line)
    raise TaskDataError("task frontmatter block is not terminated", _REPAIR)


def _cells(line: str) -> list[str]:
    line = line.strip()
    line = line.removeprefix("|")
    if line.endswith("|"):
        tail = line[:-1]
        escapes = len(tail) - len(tail.rstrip("\\"))
        if escapes % 2 == 0:
            line = tail
    cells: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(line):
        character = line[index]
        if character == "\\" and index + 1 < len(line) and line[index + 1] in "\\|":
            index += 1
            current.append(line[index])
        elif character == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
        index += 1
    cells.append("".join(current).strip())
    return cells


def _event_table(
    text: str, body_start: int, *, prepend: bool = False
) -> tuple[list[dict[str, str]], int | None]:
    try:
        from markdown_it import MarkdownIt
    except ImportError:
        raise TaskDataError(
            "required dependency markdown-it-py is not installed",
            "install the declared sbtd-workflow-onboard requirements before task writes",
        ) from None
    body = text[body_start:]
    # Token maps count CommonMark line endings, not Unicode text separators.
    lines = re.split(r"(?<=\n)|(?<=\r)(?!\n)", body)
    tokens = MarkdownIt("commonmark").enable("table").parse(body)
    headings = [
        index
        for index, token in enumerate(tokens)
        if token.type == "heading_open"
        and token.tag == "h2"
        and token.level == 0
        and index + 1 < len(tokens)
        and tokens[index + 1].content == "状态事件"
    ]
    if not headings:
        return [], None
    if len(headings) != 1:
        raise TaskDataError("task has multiple state event sections", _REPAIR)
    table_index = headings[0] + 3
    table = tokens[table_index] if table_index < len(tokens) else None
    if (
        table is None
        or table.type != "table_open"
        or table.level != 0
        or table.map is None
    ):
        raise TaskDataError("task state event section has no top-level table", _REPAIR)
    for following in tokens[table_index + 1 :]:
        if (
            following.type == "heading_open"
            and following.level == 0
            and following.tag in ("h1", "h2")
        ):
            break
        if following.type == "table_open" and following.level == 0:
            raise TaskDataError(
                "task state event section contains multiple tables", _REPAIR
            )
    first, last = table.map
    if tuple(_cells(lines[first])) != _EVENT_COLUMNS:
        raise TaskDataError("task state event table has invalid columns", _REPAIR)
    separators = _cells(lines[first + 1])
    if len(separators) != 5 or not all(
        re.fullmatch(r":?-{3,}:?", cell) for cell in separators
    ):
        raise TaskDataError("task state event table has an invalid separator", _REPAIR)
    events: list[dict[str, str]] = []
    for line in lines[first + 2 : last]:
        values = _cells(line)
        if len(values) != 5:
            raise TaskDataError("task state event table has a malformed row", _REPAIR)
        event = dict(
            zip(
                _EVENT_COLUMNS,
                (html.unescape(cell.replace("<br>", "\n")) for cell in values),
            )
        )
        validate_task_data(event, "stateEvent", "task state event")
        if event["at"] != "unknown":
            validate_task_timestamps({"updated_at": event["at"]}, "task state event")
        events.append(event)
    boundary = first + 2 if prepend else last
    return events, body_start + sum(len(line) for line in lines[:boundary])


def _event_cell(value: str) -> str:
    """Escape one cell without losing whitespace removed by Markdown table parsing."""
    leading = len(value) - len(value.lstrip())
    if leading == len(value):
        return "".join(f"&#{ord(character)};" for character in value)
    trailing = len(value.rstrip())

    def escape(text: str) -> str:
        return (
            html.escape(text, quote=False)
            .replace("\\", "&#92;")
            .replace("|", "&#124;")
            .replace("\r", "&#13;")
            .replace("\n", "<br>")
        )

    return (
        "".join(f"&#{ord(character)};" for character in value[:leading])
        + escape(value[leading:trailing])
        + "".join(f"&#{ord(character)};" for character in value[trailing:])
    )


def _event_row(event: dict[str, str], newline: str) -> str:
    validate_task_data(event, "stateEvent", "task state event")
    if event["at"] != "unknown":
        validate_task_timestamps({"updated_at": event["at"]}, "task state event")
    cells = [_event_cell(event[key]) for key in _EVENT_COLUMNS]
    return "| " + " | ".join(cells) + " |" + newline


@dataclass(frozen=True)
class TaskDocument:
    text: str
    frontmatter: dict[str, Any]
    events: tuple[dict[str, str], ...]

    @classmethod
    def parse(cls, text: str) -> TaskDocument:
        frontmatter = parse_task_frontmatter(text, "task")
        validate_task_data(frontmatter, "taskFrontmatter", "task")
        validate_task_timestamps(frontmatter, "task")
        _, _, body_start = _frontmatter_bounds(text)
        events, _ = _event_table(text, body_start)
        return cls(text, frontmatter, tuple(events))

    def updated(
        self,
        fields: dict[str, Any],
        *,
        event: dict[str, str] | None = None,
        prepend_event: bool = False,
    ) -> TaskDocument:
        # Compose only for source spans after the shared safe parser has accepted
        # the data. Replacing owned values preserves all unrelated YAML/body bytes.
        import yaml

        start, end, _ = _frontmatter_bounds(self.text)
        node = yaml.compose(self.text[start:end], Loader=yaml.BaseLoader)
        if not isinstance(node, yaml.MappingNode):
            raise TaskDataError("task frontmatter is not a mapping", _REPAIR)
        spans = {key.value: value for key, value in node.value}
        newline = "\r\n" if "\r\n" in self.text else "\n"
        additions: list[str] = []
        replacements: list[tuple[int, int, str]] = []
        for key, value in fields.items():
            try:
                encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
            except (TypeError, ValueError):
                raise TaskDataError(
                    "task update is not JSON-compatible", _REPAIR
                ) from None
            if key not in spans:
                additions.append(json.dumps(key, ensure_ascii=False) + ": " + encoded)
                continue
            scalar = spans[key]
            first = start + scalar.start_mark.index
            last = start + scalar.end_mark.index
            scalar_text = self.text[first:last]
            header = scalar_text.splitlines()[0] if scalar_text else ""
            if scalar.style in ("|", ">") and "#" in header:
                encoded += " " + header[header.index("#") :]
            if scalar_text.endswith(newline):
                encoded += newline
            replacements.append((first, last, encoded))
        if additions:
            if node.flow_style:
                insertion = start + node.end_mark.index - 1
                if node.value:
                    last_value = node.value[-1][1]
                    trailing = self.text[
                        start + last_value.end_mark.index : insertion
                    ]
                    prefix = " " if trailing.lstrip().startswith(",") else ", "
                else:
                    prefix = " "
                appended = prefix + ", ".join(additions)
            else:
                insertion = end
                indent = " " * node.start_mark.column
                appended = "".join(indent + field + newline for field in additions)
            replacements.append((insertion, insertion, appended))
        candidate = self.text
        for first, last, encoded in sorted(replacements, reverse=True):
            candidate = candidate[:first] + encoded + candidate[last:]
        if event is not None:
            _, _, body_start = _frontmatter_bounds(candidate)
            _, insertion = _event_table(candidate, body_start, prepend=prepend_event)
            row = _event_row(event, newline)
            if insertion is None:
                separator = newline if candidate.endswith(newline) else newline * 2
                candidate += separator + "## 状态事件" + newline * 2
                candidate += "| at | from | to | reason | evidence |" + newline
                candidate += "|---|---|---|---|---|" + newline + row
            else:
                prefix = (
                    newline
                    if insertion and candidate[insertion - 1] not in "\r\n"
                    else ""
                )
                candidate = candidate[:insertion] + prefix + row + candidate[insertion:]
        parsed = self.parse(candidate)
        added = (event,) if event is not None else ()
        expected_events = added + self.events if prepend_event else self.events + added
        if parsed.events != expected_events:
            raise TaskDataError(
                "task candidate cannot preserve the complete visible state-event history",
                _REPAIR,
            )
        return parsed
