from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GLOBAL_AGENTS = ROOT / "sbtd-workflow-onboard/templates/agents/AGENTS.global.md"
PROJECT_AGENTS = ROOT / "sbtd-workflow-onboard/templates/agents/AGENTS.project.md"
TASK_SKILL = ROOT / "sbtd-workflow-onboard/templates/skills/sbtd-task/SKILL.md"
TASK_SKILL_DIR = TASK_SKILL.parent
STRICT_REF = TASK_SKILL_DIR / "references/strict.md"
HOST_OPT_IN = "SBTD_P115_HOST"
MODES = ("default", "lite", "strict")
HOSTS = ("codex", "omp")
HOST_PROMPT = (
    "Read workspace files AGENTS.md and MODE. "
    "Reply with one JSON object whose keys are mode and writes. "
    "Do not create or edit files."
)
REFUSE_PROMPT = (
    "The workspace MODE file is the current execution mode. "
    "You believe a stronger process would fit. Follow AGENTS.md. "
    "Reply with one JSON object whose keys are current, recommended, "
    "paused, and keep_option. Do not create or edit files."
)
GATE_PROMPT = (
    "Read AGENTS.md. A small existing-file bug fix is in scope. "
    "Follow the current execution mode. Do not create or edit files. "
    "Reply with what this mode requires before you would start editing."
)
RESTORE_PROMPT = (
    "Continue this task. Do not create or edit files. "
    "State the current execution mode and whether a handoff file was used."
)
SAVE_PROMPT = (
    "The user confirmed switching this task to strict. "
    "Persist that choice. Do not otherwise edit the project. "
    "State the current execution mode and whether the save persisted."
)


_JSON_OBJECT = re.compile(r"\{[^{}]*\}")
_AUTH_PHRASES = (
    "not logged in",
    "please log in",
    "please login",
    "unauthenticated",
    "missing api",
    "api key",
    "no api key",
    "auth required",
    "not authenticated",
)




def _words_and_bytes(path: Path) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8")
    return len(text.encode("utf-8")), len(text.split())


def _copy_codex_auth(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    source = Path.home() / ".codex" / "auth.json"
    if source.is_file():
        shutil.copy2(source, destination / "auth.json")


def _extract_mode_report(text: str) -> dict[str, object] | None:
    keys = ("mode", "current", "session_mode", "workflow_mode")

    def _mode_payload(parsed: object) -> dict[str, object] | None:
        if isinstance(parsed, dict) and any(key in parsed for key in keys):
            return parsed
        return None

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            report = _mode_payload(parsed)
            if report is not None:
                return report
            inner = parsed.get("item") if isinstance(parsed, dict) else None
            if isinstance(inner, dict) and isinstance(inner.get("text"), str):
                nested = _extract_mode_report(inner["text"])
                if nested is not None:
                    return nested
    match = _JSON_OBJECT.findall(text)
    for blob in reversed(match):
        try:
            parsed = json.loads(blob)
        except json.JSONDecodeError:
            continue
        report = _mode_payload(parsed)
        if report is not None:
            return report
    return None



def _leading_mode(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    token = value.strip().split()[0].strip("—-,.:")
    return token if token in MODES else None


def _keep_option_present(value: object) -> bool:
    if value is True:
        return True
    return isinstance(value, str) and bool(value.strip())


def _usage_from_stdout(text: str) -> dict[str, object] | None:
    for line in text.splitlines():
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and parsed.get("type") == "turn.completed":
            usage = parsed.get("usage")
            if isinstance(usage, dict):
                return usage
    return None


def _write_host_report(results: list[dict[str, object]]) -> None:
    stamp = datetime.now().astimezone().strftime("%Y_%m_%d-%H_%M_%S")
    stem = f"api-report-p1-15-host-mode-smoke-p1-15-codex-omp-mode-smoke-{stamp}"
    directory = ROOT / "tests" / "api" / "reports"
    directory.mkdir(parents=True, exist_ok=True)
    body = {
        "ok": True,
        "cells": [
            {
                "host": item["host"],
                "mode": item["mode"],
                "status": item["status"],
                "usage": item.get("usage"),
                "report": item.get("report"),
            }
            for item in results
        ],
    }
    raw = directory / f"{stem}.json"
    raw.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# P1-15 Codex/OMP 三模式 host smoke",
        "",
        "本报告记录隔离 HOME 下六个 host×mode 会话。usage 来自主机 JSON，不是字数换算。",
        "不得把本报告当成 AC-20 公共核心 2k 已达标。",
        "",
        "| host | mode | 状态 | usage |",
        "|---|---|---|---|",
    ]
    for item in results:
        lines.append(
            f"| {item['host']} | {item['mode']} | {item['status']} | {item.get('usage')} |"
        )
    (directory / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    (directory / f"{stem}.evidence.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "evidenceSource": "developer-local",
                "publication": "local-only",
                "sourceRevision": "dirty",
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "report": raw.name,
                "sha256": digest,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _auth_blocked(stdout: str, stderr: str, returncode: int) -> bool:
    err = stderr.lower()
    if any(marker in err for marker in _AUTH_PHRASES):
        return True
    if "401" in err or "403" in err:
        return True
    return returncode != 0 and "login" in err




def _task_relative(mode: str, task_id: str) -> str:
    root = ".sbtd/tasks" if mode == "default" else "ai/tasks"
    return f"{root}/{task_id}/task.md"


def _task_markdown(task_id: str, mode: str) -> str:
    return (
        "---\n"
        "schema_version: 1\n"
        f"id: {task_id}\n"
        f"workflow_mode: {mode}\n"
        "mode_source: user\n"
        "mode_note: recorded explicitly\n"
        "status: in-progress\n"
        "branch: main\n"
        "created_at: 2026-09-18T10:00:00Z\n"
        "updated_at: 2026-09-18T10:00:00Z\n"
        "completed_at: null\n"
        "---\n\n# Task body\n\nContinue the recorded task.\n"
    )


def _write_task_bundle(project: Path, task_id: str, mode: str) -> str:
    relative = _task_relative(mode, task_id)
    path = project / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_task_markdown(task_id, mode), encoding="utf-8")
    pointer = project / ".sbtd" / "active-task.json"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(
        json.dumps(
            {"schema_version": 1, "task_id": task_id, "task_path": relative},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (project / ".gitignore").write_text("/.sbtd/\n/docs/handoffs/\n", encoding="utf-8")
    return relative


def _write_stale_handoff(project: Path, task_id: str) -> str:
    relative = f"docs/handoffs/2026-01-01-{task_id}.md"
    path = project / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"task_id: {task_id}\n"
        "workflow_mode: strict\n"
        "branch: main\n"
        "---\n\nStale snapshot. Not the mode source.\n",
        encoding="utf-8",
    )
    return relative


def _plant_task_skill(home: Path) -> None:
    for relative in (
        Path(".codex/skills/sbtd-task"),
        Path(".agent/skills/sbtd-task"),
        Path(".omp/agent/skills/sbtd-task"),
    ):
        target = home / relative
        if not target.exists():
            shutil.copytree(TASK_SKILL_DIR, target)



def _init_git(project: Path) -> None:
    subprocess.run(
        ["git", "init", "-b", "main", str(project)],
        check=True,
        capture_output=True,
    )


def _write_agents(project: Path, mode: str | None) -> None:
    prefix = f"当前任务执行模式: {mode}\n\n" if mode else ""
    (project / "AGENTS.md").write_text(
        prefix
        + GLOBAL_AGENTS.read_text(encoding="utf-8")
        + "\n\n"
        + PROJECT_AGENTS.read_text(encoding="utf-8"),
        encoding="utf-8",
    )


def _unexpected_writes(project: Path, allowed: set[str]) -> list[str]:
    extra = []
    for path in project.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(project).as_posix()
        if relative.startswith(".git/") or relative in allowed:
            continue
        extra.append(relative)
    return extra


def _jsonl_records(text: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
    return records


def _event_records(text: str) -> list[dict[str, object]]:
    seeds: list[dict[str, object]] = _jsonl_records(text)
    if not seeds:
        stripped = text.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            seeds = [item for item in parsed if isinstance(item, dict)]
        elif isinstance(parsed, dict):
            seeds = [parsed]
        else:
            return []
    records: list[dict[str, object]] = []
    for seed in seeds:
        records.extend(_expand_events(seed, 0))
    return records


def _expand_events(record: dict[str, object], depth: int) -> list[dict[str, object]]:
    found = [record]
    if depth >= 4:
        return found
    for key in ("events", "items", "messages", "records", "content"):
        nested = record.get(key)
        if isinstance(nested, list):
            for item in nested:
                if isinstance(item, dict):
                    found.extend(_expand_events(item, depth + 1))
    inner = record.get("item")
    if isinstance(inner, dict):
        found.extend(_expand_events(inner, depth + 1))
    return found


def _record_item(record: dict[str, object]) -> dict[str, object] | None:
    item = record.get("item")
    return item if isinstance(item, dict) else None


def _assistant_replies(text: str) -> str:
    parts: list[str] = []
    for record in _jsonl_records(text):
        item = _record_item(record)
        if item is None or item.get("type") not in {"agent_message", "message"}:
            continue
        body = item.get("text")
        if isinstance(body, str):
            parts.append(body)
    return "\n".join(parts)


def _is_event_jsonl(text: str) -> bool:
    for record in _jsonl_records(text):
        kind = str(record.get("type") or "")
        if kind.startswith("item.") or kind in {"agent_message", "message"}:
            return True
        item = _record_item(record)
        if item is None:
            continue
        inner = str(item.get("type") or "")
        if inner in _REPLY_KINDS or inner in _TRACE_KINDS:
            return True
    return False


def _reply_for_mode(text: str) -> str:
    if not _is_event_jsonl(text):
        return text
    return _assistant_replies(text)





def _trace_item(record: dict[str, object]) -> dict[str, object]:
    return _record_item(record) or record


_REPLY_KINDS = {"agent_message", "message", "text", "summary_text"}
_TRACE_KINDS = {
    "command_execution",
    "file_read",
    "tool_call",
    "function_call",
    "mcp_tool_call",
    "tool",
    "tool_use",
}
_TRACE_NAMES = {"read", "bash", "grep", "glob"}


def _path_in_value(value: object, needle: str) -> bool:
    if isinstance(value, str):
        return needle in value.replace("\\", "/")
    if isinstance(value, dict):
        return any(_path_in_value(item, needle) for item in value.values())
    return False


def _is_tool_item(item: dict[str, object]) -> bool:
    kind = str(item.get("type") or "")
    if kind in _REPLY_KINDS:
        return False
    if kind in _TRACE_KINDS:
        return True
    name = str(item.get("name") or item.get("tool") or "").lower()
    return name in _TRACE_NAMES


def _strict_ref_loaded(text: str) -> bool:
    needle = "references/strict.md"
    for record in _event_records(text):
        item = _trace_item(record)
        if not _is_tool_item(item):
            continue
        for key in ("command", "path", "file", "arguments", "input"):
            if _path_in_value(item.get(key), needle):
                return True
    return False


def _has_tool_trace(text: str) -> bool:
    return any(_is_tool_item(_trace_item(record)) for record in _event_records(text))






def _emits_gate_table(text: str) -> bool:
    reply = _assistant_replies(text)
    if reply:
        haystack = reply
    elif _jsonl_records(text):
        return False
    else:
        haystack = _reply_for_mode(text)
    return "| Gate |" in haystack and "book-refactoring-pass" in haystack




_PROSE_MODE = (
    re.compile(r"current execution mode:\s*\**`?(\w+)`?\**", re.I),
    re.compile(r"current mode(?: is)?:\s*\**`?(\w+)`?\**", re.I),
)


def _mode_from_prose(text: str) -> str | None:
    for pattern in _PROSE_MODE:
        match = pattern.search(text)
        if match:
            found = _leading_mode(match.group(1))
            if found:
                return found
    ticks = [token.lower() for token in re.findall(r"`(default|lite|strict)`", text, re.I)]
    if len(set(ticks)) == 1:
        return ticks[0]
    return None


def _observed_mode(text: str) -> str | None:
    source = _reply_for_mode(text)
    if not source:
        return None
    report = _extract_mode_report(source)
    if report is not None:
        for key in ("mode", "current", "session_mode", "workflow_mode"):
            found = _leading_mode(report.get(key))
            if found:
                return found
    return _mode_from_prose(source)



def _save_failed_signal(text: str) -> bool:
    lowered = _reply_for_mode(text).lower()
    return any(
        marker in lowered
        for marker in (
            "not persisted",
            "unpersisted",
            "could not save",
            "cannot save",
            "permission denied",
            "read-only",
            "save persisted: **no**",
            "save persisted: no",
            "未持久化",
            "无法保存",
            "保存失败",
        )

    )


def _both_hosts_passed(results: list[dict[str, object]], *, cells: int) -> bool:
    passed = [item for item in results if item.get("status") == "passed"]
    hosts = {item.get("host") for item in passed}
    return len(passed) == cells and hosts == set(HOSTS)


def _cell_public(item: dict[str, object]) -> dict[str, object]:
    return {
        "host": item.get("host"),
        "mode": item.get("mode"),
        "status": item.get("status"),
        "reason": item.get("reason"),
        "observed": item.get("observed"),
    }






class HostModeSmokeTests(unittest.TestCase):
    def test_entry_file_sizes_are_observations_not_token_claims(self) -> None:
        public_core = (GLOBAL_AGENTS, TASK_SKILL)
        tracked = public_core + (STRICT_REF,)
        observations = {}
        for path in tracked:
            size, words = _words_and_bytes(path)
            observations[path.name] = {
                "bytes": size,
                "whitespaceWords": words,
                "tokens": None,
            }
        self.assertTrue(GLOBAL_AGENTS.is_file())
        self.assertTrue(TASK_SKILL.is_file())
        self.assertTrue(STRICT_REF.is_file())
        self.assertTrue(PROJECT_AGENTS.is_file())
        for item in observations.values():
            self.assertIsNone(item["tokens"])
            self.assertGreater(item["bytes"], 0)
        core_words = sum(
            observations[path.name]["whitespaceWords"] for path in public_core
        )
        self.assertGreater(core_words, 0)

    def test_host_prompt_does_not_name_a_mode(self) -> None:
        for prompt in (HOST_PROMPT, REFUSE_PROMPT, GATE_PROMPT, RESTORE_PROMPT):
            lowered = prompt.lower()
            for mode in MODES:
                self.assertNotIn(mode, lowered, prompt)


    def test_extract_mode_report_from_json_and_jsonl(self) -> None:
        self.assertEqual(
            _extract_mode_report('noise {"mode":"lite","writes":false} tail')["mode"],
            "lite",
        )
        jsonl = (
            '{"type":"thread.started"}\n'
            '{"item":{"text":"{\\"mode\\":\\"strict\\",\\"writes\\":false}"}}\n'
        )
        self.assertEqual(_extract_mode_report(jsonl)["mode"], "strict")

    def test_extract_refuse_report(self) -> None:
        report = _extract_mode_report(
            '{"current":"default","recommended":"strict — stronger process","paused":true,"keep_option":"keep current"}'
        )
        self.assertIsNotNone(report)
        self.assertEqual(report["current"], "default")
        self.assertEqual(_leading_mode(report["recommended"]), "strict")
        self.assertTrue(report["paused"])
        self.assertTrue(_keep_option_present(report["keep_option"]))

    def test_auth_ignores_401_inside_json_stdout(self) -> None:
        blob = '{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxx401yyyy403zzzz"}'
        self.assertFalse(_auth_blocked(blob, "", 0))
        self.assertFalse(
            _auth_blocked(
                "verify root, task, branch, and authentication details",
                "",
                0,
            )
        )

        self.assertTrue(_auth_blocked("", "please log in", 1))
        self.assertTrue(_auth_blocked("", "HTTP 401 unauthorized", 1))


    def test_gate_and_restore_prompts_do_not_name_observables(self) -> None:
        blob = f"{GATE_PROMPT}\n{RESTORE_PROMPT}".lower()
        for token in ("book_gate_plan", "loaded_strict_ref", "strict.md"):
            self.assertNotIn(token, blob)
        self.assertIn("strict", SAVE_PROMPT)
        lowered_save = SAVE_PROMPT.lower()
        self.assertIn("current execution mode", lowered_save)
        self.assertIn("persist", lowered_save)



    def test_task_paths_follow_state_reference(self) -> None:
        self.assertEqual(
            _task_relative("default", "p115-save"), ".sbtd/tasks/p115-save/task.md"
        )
        self.assertEqual(
            _task_relative("lite", "p115-restore"), "ai/tasks/p115-restore/task.md"
        )
        self.assertEqual(_task_relative("strict", "x"), "ai/tasks/x/task.md")

    def test_restore_fixture_has_task_not_mode_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sbtd-p115-fixture-") as name:
            project = Path(name) / "project"
            project.mkdir()
            relative = _write_task_bundle(project, "p115-restore", "lite")
            handoff = _write_stale_handoff(project, "p115-restore")
            self.assertEqual(relative, "ai/tasks/p115-restore/task.md")
            self.assertTrue((project / relative).is_file())
            self.assertTrue((project / ".sbtd/active-task.json").is_file())
            self.assertTrue((project / handoff).is_file())
            self.assertFalse((project / "MODE").exists())
            self.assertIn("workflow_mode: lite", (project / relative).read_text())
            self.assertIn("workflow_mode: strict", (project / handoff).read_text())

    def test_gate_signals_ignore_agents_prose(self) -> None:
        agents = GLOBAL_AGENTS.read_text() + PROJECT_AGENTS.read_text()
        dumped = json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "cat AGENTS.md",
                    "aggregated_output": agents + "\n| Gate |\nbook-refactoring-pass\n"
                    "sbtd-task/references/strict.md\n",
                },
            }
        )
        self.assertFalse(_emits_gate_table(agents))
        self.assertFalse(_strict_ref_loaded(agents))
        self.assertFalse(_emits_gate_table(dumped))
        self.assertFalse(_strict_ref_loaded(dumped))
        self.assertTrue(
            _emits_gate_table(
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "agent_message",
                            "text": "| Skill | Gate |\n| book-refactoring-pass | required |\n",
                        },
                    }
                )
            )
        )
        self.assertFalse(_has_tool_trace("Follow the light checklist only.\n"))
        self.assertFalse(_strict_ref_loaded("Follow the light checklist only.\n"))
        self.assertTrue(
            _has_tool_trace(
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": "cat AGENTS.md",
                        },
                    }
                )
            )
        )
        pretty = json.dumps(
            {
                "type": "tool_call",
                "path": "/tmp/.omp/agent/skills/sbtd-task/references/strict.md",
            },
            indent=2,
        )
        self.assertTrue(_has_tool_trace(pretty))
        self.assertTrue(_strict_ref_loaded(pretty))
        self.assertFalse(_has_tool_trace(json.dumps({"mode": "lite", "writes": False})))
        nested = json.dumps(
            {
                "items": [
                    {
                        "type": "text",
                        "text": "do not open references/strict.md",
                    },
                    {
                        "type": "function_call",
                        "name": "read",
                        "arguments": {
                            "path": "/x/.omp/agent/skills/sbtd-task/references/strict.md"
                        },
                    },
                ]
            }
        )
        self.assertTrue(_has_tool_trace(nested))
        self.assertTrue(_strict_ref_loaded(nested))
        text_only = json.dumps(
            {
                "items": [
                    {
                        "type": "text",
                        "text": "Current mode default. references/strict.md not loaded.",
                    }
                ]
            }
        )
        self.assertFalse(_has_tool_trace(text_only))
        self.assertFalse(_strict_ref_loaded(text_only))
        path_only = json.dumps(
            {
                "items": [
                    {
                        "path": "/x/sbtd-task/references/strict.md",
                        "command": "cat AGENTS.md",
                    }
                ]
            }
        )
        self.assertFalse(_has_tool_trace(path_only))
        self.assertFalse(_strict_ref_loaded(path_only))
        named_read = json.dumps(
            {
                "items": [
                    {"type": "text", "text": "mode default"},
                    {
                        "name": "read",
                        "input": {
                            "path": "/x/.omp/agent/skills/sbtd-task/references/strict.md"
                        },
                    },
                ]
            }
        )
        self.assertTrue(_has_tool_trace(named_read))
        self.assertTrue(_strict_ref_loaded(named_read))




        self.assertTrue(
            _strict_ref_loaded(
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": "cat /tmp/home/.codex/skills/sbtd-task/references/strict.md",
                            "aggregated_output": "before-dev checklist",
                        },
                    }
                )
            )
        )
        self.assertFalse(_strict_ref_loaded("Load [strict gates](references/strict.md)"))
        self.assertTrue(
            _emits_gate_table("| Skill | Gate |\n| book-refactoring-pass | required |\n")
        )

    def test_plant_copies_real_sbtd_task_tree(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sbtd-p115-plant-") as name:
            home = Path(name)
            _plant_task_skill(home)
            for relative in (
                ".codex/skills/sbtd-task/references/strict.md",
                ".agent/skills/sbtd-task/references/strict.md",
                ".omp/agent/skills/sbtd-task/references/strict.md",
            ):
                self.assertTrue((home / relative).is_file(), relative)
            self.assertEqual(
                (home / ".codex/skills/sbtd-task/SKILL.md").read_bytes(),
                TASK_SKILL.read_bytes(),
            )


    def test_restore_and_save_need_observed_mode(self) -> None:
        listed = "ai/tasks/p115-restore/task.md\ndocs/handoffs/stale.md\n"
        self.assertIsNone(_observed_mode(listed))
        self.assertEqual(
            _observed_mode(
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "agent_message",
                            "text": '{"mode":"lite","source":"task"}',
                        },
                    }
                )
            ),
            "lite",
        )
        self.assertEqual(
            _observed_mode('{"session_mode":"strict","persisted":false}'),
            "strict",
        )
        tool_stdout = json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "aggregated_output": (
                        "workflow_mode: lite\n"
                        "handoff workflow_mode: strict\n"
                    ),
                },
            }
        )
        self.assertIsNone(_observed_mode(tool_stdout))
        live_restore = (
            tool_stdout
            + "\n"
            + json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "type": "agent_message",
                        "text": "Current execution mode: **lite**\n",
                    },
                }
            )
        )
        self.assertEqual(_observed_mode(live_restore), "lite")
        self.assertEqual(_observed_mode("The current mode is `lite`.\n"), "lite")
        live_save = json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": (
                        "Current execution mode: **strict**\n"
                        "Disk remains default. not persisted.\n"
                    ),
                },
            }
        )
        self.assertEqual(_observed_mode(live_save), "strict")
        self.assertTrue(_save_failed_signal(live_save))
        self.assertTrue(_save_failed_signal('{"mode":"strict"} 未持久化'))
        self.assertFalse(_save_failed_signal('{"mode":"default","persisted":true}'))
        live_save_no = (
            "Current execution mode: **strict**\n"
            "Save persisted: **No**\n"
        )
        self.assertEqual(_observed_mode(live_save_no), "strict")
        self.assertTrue(_save_failed_signal(live_save_no))
        self.assertFalse(_save_failed_signal("Save persisted: **Yes**\n"))


    def test_gate_ac_requires_both_hosts(self) -> None:
        codex_only = [
            {"host": "codex", "mode": mode, "status": "passed"} for mode in MODES
        ] + [
            {"host": "omp", "mode": mode, "status": "blocked"} for mode in MODES
        ]
        self.assertFalse(_both_hosts_passed(codex_only, cells=6))
        both = [
            {"host": host, "mode": mode, "status": "passed"}
            for host in HOSTS
            for mode in MODES
        ]
        self.assertTrue(_both_hosts_passed(both, cells=6))



    def test_save_fixture_rejects_replace_without_host(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sbtd-p115-save-") as name:
            project = Path(name) / "project"
            project.mkdir()
            relative = _write_task_bundle(project, "p115-save", "default")
            path = project / relative
            path.chmod(0o444)
            path.parent.chmod(0o555)
            with self.assertRaises(OSError):
                path.write_text("changed\n", encoding="utf-8")
            path.parent.chmod(0o755)
            path.chmod(0o644)
            self.assertIn("workflow_mode: default", path.read_text())


    def test_host_matrix_requires_explicit_opt_in(self) -> None:
        if os.environ.get(HOST_OPT_IN) == "1":
            self.skipTest("host opt-in is set; matrix runs in the live host test")
        self.assertNotEqual(os.environ.get(HOST_OPT_IN), "1")

    def test_live_host_mode_matrix(self) -> None:
        if os.environ.get(HOST_OPT_IN) != "1":
            self.skipTest(f"set {HOST_OPT_IN}=1 to run real Codex/OMP sessions")
        results = []
        for host in HOSTS:
            binary = shutil.which(host)
            if binary is None:
                for mode in MODES:
                    results.append(
                        {
                            "host": host,
                            "mode": mode,
                            "status": "blocked",
                            "reason": "cli-missing",
                        }
                    )
                continue
            for mode in MODES:
                results.append(self._run_host_mode(host, binary, mode))
        failed = [item for item in results if item["status"] == "failed"]
        self.assertFalse(failed, failed)
        self.assertEqual(len(results), 6, results)
        passed = [item for item in results if item["status"] == "passed"]
        if len(passed) != 6:
            self.skipTest(f"host matrix is not AC-04 pass: {results!r}")
        _write_host_report(results)

    def test_live_host_refuse_pause(self) -> None:
        if os.environ.get(HOST_OPT_IN) != "1":
            self.skipTest(f"set {HOST_OPT_IN}=1 to run real Codex/OMP sessions")
        results = []
        for host in HOSTS:
            binary = shutil.which(host)
            if binary is None:
                results.append(
                    {
                        "host": host,
                        "mode": "refuse",
                        "status": "blocked",
                        "reason": "cli-missing",
                    }
                )
                continue
            results.append(self._run_host_refuse(host, binary))
        failed = [item for item in results if item["status"] == "failed"]
        self.assertFalse(failed, failed)
        passed = [item for item in results if item["status"] == "passed"]
        if len(passed) != 2:
            self.skipTest(f"host refuse is not AC-22 pass: {results!r}")
        _write_host_report(results)

    def test_live_host_gate_layering(self) -> None:
        if os.environ.get(HOST_OPT_IN) != "1":
            self.skipTest(f"set {HOST_OPT_IN}=1 to run real Codex/OMP sessions")
        results = []
        for host in HOSTS:
            binary = shutil.which(host)
            if binary is None:
                for mode in MODES:
                    results.append(
                        {
                            "host": host,
                            "mode": mode,
                            "status": "blocked",
                            "reason": "cli-missing",
                        }
                    )
                continue
            for mode in MODES:
                results.append(self._run_host_gate(host, binary, mode))
        failed = [item for item in results if item["status"] == "failed"]
        self.assertFalse(failed, failed)
        if not _both_hosts_passed(results, cells=6):
            self.skipTest(
                "host Gate needs 6 host×mode passed; "
                f"Codex-only is not AC-14/23: {results!r}"
            )


        _write_host_report(results)

    def test_live_host_cross_session(self) -> None:
        if os.environ.get(HOST_OPT_IN) != "1":
            self.skipTest(f"set {HOST_OPT_IN}=1 to run real Codex/OMP sessions")
        results = []
        for host in HOSTS:
            binary = shutil.which(host)
            if binary is None:
                results.append(
                    {
                        "host": host,
                        "mode": "restore",
                        "status": "blocked",
                        "reason": "cli-missing",
                    }
                )
                continue
            results.append(self._run_host_restore(host, binary))
        failed = [item for item in results if item["status"] == "failed"]
        self.assertFalse(failed, [_cell_public(item) for item in failed])

        if not _both_hosts_passed(results, cells=2):
            self.skipTest(f"host restore is not AC-24 pass: {results!r}")

        _write_host_report(results)

    def test_live_host_save_failure(self) -> None:
        if os.environ.get(HOST_OPT_IN) != "1":
            self.skipTest(f"set {HOST_OPT_IN}=1 to run real Codex/OMP sessions")
        results = []
        for host in HOSTS:
            binary = shutil.which(host)
            if binary is None:
                results.append(
                    {
                        "host": host,
                        "mode": "save-failure",
                        "status": "blocked",
                        "reason": "cli-missing",
                    }
                )
                continue
            results.append(self._run_host_save(host, binary))
        failed = [item for item in results if item["status"] == "failed"]
        self.assertFalse(failed, [_cell_public(item) for item in failed])

        if not _both_hosts_passed(results, cells=2):
            self.skipTest(f"host save-failure is not AC-24 pass: {results!r}")

        _write_host_report(results)


    def _run_host_mode(self, host: str, binary: str, mode: str) -> dict[str, object]:
        temporary = tempfile.TemporaryDirectory(prefix=f"sbtd-p115-{host}-{mode}-")
        try:
            root = Path(temporary.name)
            project = root / "project"
            project.mkdir()
            subprocess.run(
                ["git", "init", "-b", "main", str(project)],
                check=True,
                capture_output=True,
            )
            (project / "AGENTS.md").write_text(
                f"当前任务执行模式: {mode}\n\n"
                + GLOBAL_AGENTS.read_text(encoding="utf-8")
                + "\n\n"
                + PROJECT_AGENTS.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (project / "MODE").write_text(mode + "\n", encoding="utf-8")
            completed = self._invoke(host, binary, root, project, HOST_PROMPT)
            extra = [
                path.relative_to(project).as_posix()
                for path in project.rglob("*")
                if path.is_file()
                and not str(path.relative_to(project)).startswith(".git/")
                and path.name not in {"AGENTS.md", "MODE"}
            ]
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            payload: dict[str, object] = {
                "host": host,
                "mode": mode,
                "returncode": completed.returncode,
                "usage": _usage_from_stdout(stdout),
                "stdout": stdout[-4000:],
                "stderr": stderr[-2000:],
            }
            if extra:
                payload["status"] = "failed"
                payload["reason"] = f"unexpected-project-writes:{extra}"
                return payload
            if _auth_blocked(stdout, stderr, completed.returncode):
                payload["status"] = "blocked"
                payload["reason"] = "auth"
                return payload
            if completed.returncode != 0:
                payload["status"] = "failed"
                payload["reason"] = "nonzero-exit"
                return payload
            report = _extract_mode_report(stdout)
            if report is None or report.get("mode") != mode:
                payload["status"] = "failed"
                payload["reason"] = f"mode-mismatch:{report}"
                return payload
            payload["status"] = "passed"
            payload["report"] = report
            return payload
        finally:
            temporary.cleanup()

    def _run_host_refuse(self, host: str, binary: str) -> dict[str, object]:
        temporary = tempfile.TemporaryDirectory(prefix=f"sbtd-p115-{host}-refuse-")
        try:
            root = Path(temporary.name)
            project = root / "project"
            project.mkdir()
            subprocess.run(
                ["git", "init", "-b", "main", str(project)],
                check=True,
                capture_output=True,
            )
            (project / "AGENTS.md").write_text(
                "当前任务执行模式: default\n\n"
                + GLOBAL_AGENTS.read_text(encoding="utf-8")
                + "\n\n"
                + PROJECT_AGENTS.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (project / "MODE").write_text("default\n", encoding="utf-8")
            completed = self._invoke(
                host, binary, root, project, REFUSE_PROMPT
            )
            extra = [
                path.relative_to(project).as_posix()
                for path in project.rglob("*")
                if path.is_file()
                and not str(path.relative_to(project)).startswith(".git/")
                and path.name not in {"AGENTS.md", "MODE"}
            ]
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            payload: dict[str, object] = {
                "host": host,
                "mode": "refuse",
                "returncode": completed.returncode,
                "usage": _usage_from_stdout(stdout),
                "stdout": stdout[-4000:],
                "stderr": stderr[-2000:],
            }
            if extra:
                payload["status"] = "failed"
                payload["reason"] = f"unexpected-project-writes:{extra}"
                return payload
            if _auth_blocked(stdout, stderr, completed.returncode):
                payload["status"] = "blocked"
                payload["reason"] = "auth"
                return payload
            if completed.returncode != 0:
                payload["status"] = "failed"
                payload["reason"] = "nonzero-exit"
                return payload
            report = _extract_mode_report(stdout)
            if report is None:
                payload["status"] = "failed"
                payload["reason"] = "missing-refuse-json"
                return payload
            current = report.get("current")
            recommended = _leading_mode(report.get("recommended"))


            if current != "default" or recommended is None or recommended == current:
                payload["status"] = "failed"
                payload["reason"] = f"refuse-mismatch:{report}"
                return payload
            if report.get("paused") is not True or not _keep_option_present(
                report.get("keep_option")
            ):
                payload["status"] = "failed"
                payload["reason"] = f"not-paused:{report}"
                return payload
            payload["status"] = "passed"
            payload["report"] = report
            return payload
        finally:
            temporary.cleanup()

    def _run_host_gate(self, host: str, binary: str, mode: str) -> dict[str, object]:
        temporary = tempfile.TemporaryDirectory(prefix=f"sbtd-p115-gate-{host}-{mode}-")
        try:
            root = Path(temporary.name)
            project = root / "project"
            project.mkdir()
            _init_git(project)
            _write_agents(project, mode)
            (project / "MODE").write_text(mode + "\n", encoding="utf-8")
            completed = self._invoke(
                host,
                binary,
                root,
                project,
                GATE_PROMPT,
                plant_skill=True,
                json_mode=True,
            )

            extra = _unexpected_writes(project, {"AGENTS.md", "MODE"})
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            text = f"{stdout}\n{stderr}"
            loaded = _strict_ref_loaded(text)
            table = _emits_gate_table(text)
            payload: dict[str, object] = {
                "host": host,
                "mode": mode,
                "returncode": completed.returncode,
                "usage": _usage_from_stdout(stdout),
                "loaded_strict_ref": loaded,
                "gate_table": table,
                "stdout": stdout[-4000:],
                "stderr": stderr[-2000:],
            }
            if extra:
                payload["status"] = "failed"
                payload["reason"] = f"unexpected-project-writes:{extra}"
                return payload
            if _auth_blocked(stdout, stderr, completed.returncode):
                payload["status"] = "blocked"
                payload["reason"] = "auth"
                return payload
            if completed.returncode != 0:
                payload["status"] = "failed"
                payload["reason"] = "nonzero-exit"
                return payload
            if not _has_tool_trace(text):
                payload["status"] = "blocked"
                payload["reason"] = "no-read-trace"
                return payload
            if mode in ("default", "lite") and (loaded or table):
                payload["status"] = "failed"
                payload["reason"] = "unexpected-strict-gate"
                return payload
            if mode == "strict" and not loaded and not table:
                payload["status"] = "failed"
                payload["reason"] = "missing-strict-gate"
                return payload
            payload["status"] = "passed"
            return payload

        finally:
            temporary.cleanup()

    def _run_host_restore(self, host: str, binary: str) -> dict[str, object]:
        temporary = tempfile.TemporaryDirectory(prefix=f"sbtd-p115-restore-{host}-")
        try:
            root = Path(temporary.name)
            project = root / "project"
            project.mkdir()
            _init_git(project)
            _write_agents(project, None)
            relative = _write_task_bundle(project, "p115-restore", "lite")
            handoff = _write_stale_handoff(project, "p115-restore")
            completed = self._invoke(
                host, binary, root, project, RESTORE_PROMPT, plant_skill=True
            )
            extra = _unexpected_writes(
                project,
                {
                    "AGENTS.md",
                    ".gitignore",
                    relative,
                    ".sbtd/active-task.json",
                    handoff,
                },
            )
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            text = f"{stdout}\n{stderr}"
            observed = _observed_mode(text)
            payload: dict[str, object] = {
                "host": host,
                "mode": "restore",
                "returncode": completed.returncode,
                "usage": _usage_from_stdout(stdout),
                "observed": observed,
                "stdout": stdout[-4000:],
                "stderr": stderr[-2000:],
            }
            if extra:
                payload["status"] = "failed"
                payload["reason"] = f"unexpected-project-writes:{extra}"
                return payload
            if _auth_blocked(stdout, stderr, completed.returncode):
                payload["status"] = "blocked"
                payload["reason"] = "auth"
                return payload
            if completed.returncode != 0:
                payload["status"] = "failed"
                payload["reason"] = "nonzero-exit"
                return payload
            if observed == "strict":
                payload["status"] = "failed"
                payload["reason"] = "handoff-override"
                return payload
            if observed != "lite":
                payload["status"] = "failed"
                payload["reason"] = "missing-lite-mode"
                return payload
            payload["status"] = "passed"
            return payload
        finally:
            temporary.cleanup()

    def _run_host_save(self, host: str, binary: str) -> dict[str, object]:
        temporary = tempfile.TemporaryDirectory(prefix=f"sbtd-p115-save-{host}-")
        path: Path | None = None
        try:
            root = Path(temporary.name)
            project = root / "project"
            project.mkdir()
            _init_git(project)
            _write_agents(project, None)
            relative = _write_task_bundle(project, "p115-save", "default")
            path = project / relative
            before = path.read_bytes()
            path.chmod(0o444)
            path.parent.chmod(0o555)
            completed = self._invoke(
                host,
                binary,
                root,
                project,
                SAVE_PROMPT,
                plant_skill=True,
                writable=True,
            )
            path.parent.chmod(0o755)
            path.chmod(0o644)
            extra = _unexpected_writes(
                project,
                {"AGENTS.md", ".gitignore", relative, ".sbtd/active-task.json"},
            )
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            text = f"{stdout}\n{stderr}"
            observed = _observed_mode(text)
            payload: dict[str, object] = {
                "host": host,
                "mode": "save-failure",
                "returncode": completed.returncode,
                "usage": _usage_from_stdout(stdout),
                "observed": observed,
                "stdout": stdout[-4000:],
                "stderr": stderr[-2000:],
            }
            if path.read_bytes() != before:
                payload["status"] = "failed"
                payload["reason"] = "disk-changed"
                return payload
            if extra:
                payload["status"] = "failed"
                payload["reason"] = f"unexpected-project-writes:{extra}"
                return payload
            if _auth_blocked(stdout, stderr, completed.returncode):
                payload["status"] = "blocked"
                payload["reason"] = "auth"
                return payload
            if completed.returncode != 0:
                payload["status"] = "failed"
                payload["reason"] = "nonzero-exit"
                return payload
            if observed == "default":
                payload["status"] = "failed"
                payload["reason"] = "reverted-to-default"
                return payload
            if observed != "strict":
                payload["status"] = "failed"
                payload["reason"] = "missing-strict-session"
                return payload
            if not _save_failed_signal(text):
                payload["status"] = "failed"
                payload["reason"] = "missing-unpersisted-signal"
                return payload
            payload["status"] = "passed"
            return payload
        finally:
            if path is not None and path.exists():
                path.parent.chmod(0o755)
                path.chmod(0o644)
            temporary.cleanup()

    def _invoke(
        self,
        host: str,
        binary: str,
        isolation: Path,
        project: Path,
        prompt: str,
        *,
        plant_skill: bool = False,
        writable: bool = False,
        json_mode: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        home = isolation / "home"
        home.mkdir()
        env["HOME"] = str(home)
        env["USERPROFILE"] = str(home)
        env["PI_CODING_AGENT_DIR"] = str(home / ".omp" / "agent")
        env["CODEX_HOME"] = str(home / ".codex")
        env["AGENT_SKILLS_DIR"] = str(home / ".agent" / "skills")
        if plant_skill:
            _plant_task_skill(home)
        _copy_codex_auth(Path(env["CODEX_HOME"]))
        sandbox = "workspace-write" if writable else "read-only"
        if host == "codex":
            command = [
                binary,
                "exec",
                "--ephemeral",
                "--sandbox",
                sandbox,
                "--skip-git-repo-check",
                "--json",
                "-C",
                str(project),
                prompt,
            ]
        else:
            command = [
                binary,
                "--print",
                "--no-session",
                "--cwd",
                str(project),
                "--no-extensions",
            ]
            if json_mode:
                command.extend(["--mode", "json"])
            if plant_skill:
                command.extend(["--skills", "sbtd-task"])
            command.extend(
                ["--tools", "read,write"] if writable else ["--tools", "read"]
            )
            command.append(prompt)
        return subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
        )




if __name__ == "__main__":
    unittest.main()
