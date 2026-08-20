#!/usr/bin/env python3
"""Analyze Playwright JSON reports and produce a repair plan."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def first_line(value: str) -> str:
    return next((line.strip() for line in value.splitlines() if line.strip()), "")


def error_message(result: dict[str, Any], test: dict[str, Any]) -> str:
    messages: list[str] = []
    for error in result.get("errors", []):
        if isinstance(error, dict):
            messages.append(str(error.get("message") or error.get("stack") or ""))
        else:
            messages.append(str(error))
    if result.get("error"):
        error = result["error"]
        if isinstance(error, dict):
            messages.append(str(error.get("message") or error.get("stack") or ""))
        else:
            messages.append(str(error))
    for error in test.get("errors", []):
        if isinstance(error, dict):
            messages.append(str(error.get("message") or error.get("stack") or ""))
        else:
            messages.append(str(error))
    return "\n".join(message for message in messages if message)


def categorize(message: str, status: str) -> str:
    lower = message.lower()
    if "timeout" in lower or "timed out" in lower or status == "timedOut":
        return "timeout"
    if "strict mode violation" in lower or "locator" in lower or "selector" in lower:
        return "selector"
    if "expect(" in lower or "tohave" in lower or "tobe" in lower or "assert" in lower:
        return "assertion"
    if "401" in lower or "403" in lower or "unauthorized" in lower or "permission" in lower or "login" in lower:
        return "auth"
    if "net::err" in lower or "navigation" in lower or "tohaveurl" in lower:
        return "navigation"
    if "500" in lower or "404" in lower or "api" in lower or "request failed" in lower or "route" in lower:
        return "api"
    if "duplicate" in lower or "already exists" in lower or "not found" in lower or "test data" in lower:
        return "test-data"
    return "unknown"


def suggestions(category: str) -> list[str]:
    mapping = {
        "selector": [
            "优先为目标元素补 data-testid/data-cy，并在 Page Object 中改用稳定选择器。",
            "如果是 strict mode violation，收窄 locator 范围或使用更明确的 role/name。",
            "避免依赖生成 CSS class 或不稳定层级选择器。",
        ],
        "timeout": [
            "确认页面是否需要登录态、测试数据或 dev server。",
            "用等待可观察状态替代 waitForTimeout，例如等待接口响应、按钮可用或加载态消失。",
            "检查接口 mock/真实后端是否返回了用例期望的数据。",
        ],
        "assertion": [
            "核对断言文本是否受 i18n、异步加载或空数据影响。",
            "把过强断言改成用户可观察的稳定结果，例如 toast、URL、表格行或状态标签。",
        ],
        "auth": [
            "补 storageState 或测试登录 fixture，避免每条用例重复手动登录。",
            "确认测试账号权限覆盖目标页面和操作。",
        ],
        "navigation": [
            "检查 baseURL、路由守卫、重定向和动态路由参数。",
            "跳转后等待目标页面 ready 状态，而不是只断言 URL。",
        ],
        "api": [
            "检查后端服务、API mock、请求参数和测试数据准备。",
            "为失败态用例明确 route.fulfill/route.abort，避免依赖不稳定环境。",
        ],
        "test-data": [
            "使用唯一测试数据并在 teardown 清理。",
            "把 create -> verify -> cleanup 封装成 fixture 或 API helper。",
        ],
        "unknown": [
            "打开 Playwright trace/screenshot 定位失败步骤。",
            "先把失败归因到选择器、数据、权限、接口、断言或环境中的一种，再修复。",
        ],
    }
    return mapping.get(category, mapping["unknown"])


def attachments(result: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for item in result.get("attachments", []):
        if isinstance(item, dict) and item.get("path"):
            values.append(str(item["path"]))
    return values


def walk_suites(suite: dict[str, Any], parents: list[str], failures: list[dict[str, Any]]) -> None:
    title = suite.get("title")
    next_parents = parents + ([title] if title else [])
    for spec in suite.get("specs", []):
        spec_title = spec.get("title", "")
        file = spec.get("file", "")
        line = spec.get("line")
        for test in spec.get("tests", []):
            test_title = " ".join(part for part in [*next_parents, spec_title] if part)
            for result in test.get("results", []):
                status = result.get("status", test.get("status", "unknown"))
                if status in {"passed", "skipped"}:
                    continue
                message = error_message(result, test)
                category = categorize(message, status)
                failures.append(
                    {
                        "title": test_title,
                        "file": file,
                        "line": line,
                        "status": status,
                        "durationMs": result.get("duration"),
                        "category": category,
                        "message": first_line(message),
                        "suggestedFixes": suggestions(category),
                        "artifacts": attachments(result),
                    }
                )
    for child in suite.get("suites", []):
        walk_suites(child, next_parents, failures)


def load_report(path: Path) -> dict[str, Any]:
    return json.loads(read_text(path))


def build_plan(report: dict[str, Any], run_command: str) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    for suite in report.get("suites", []):
        walk_suites(suite, [], failures)
    categories: dict[str, int] = {}
    for failure in failures:
        categories[failure["category"]] = categories.get(failure["category"], 0) + 1
    priority = sorted(categories.items(), key=lambda item: item[1], reverse=True)
    actions = [
        f"优先修复 {category} 类失败，共 {count} 条。"
        for category, count in priority[:5]
    ]
    if not actions:
        actions.append("未发现失败用例；保持现有测试并进入覆盖率检查。")
    return {
        "summary": {
            "failedTests": len(failures),
            "categories": categories,
            "status": "needs-repair" if failures else "passed",
        },
        "failures": failures,
        "nextIteration": {
            "priorityActions": actions,
            "rerunCommand": run_command,
            "recommendedLoop": [
                "修复最高频失败类别",
                "重跑失败 spec 或全量 e2e",
                "重新生成 ui-test-coverage.json",
                "更新最终报告",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Playwright JSON report failures.")
    parser.add_argument("--report", default="tests/e2e/reports/results.json", help="Playwright JSON report path.")
    parser.add_argument("--out", default="ui-test-repair-plan.json", help="Repair plan output path.")
    parser.add_argument("--rerun-command", default="npx playwright test", help="Command to rerun after fixes.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    report_path = Path(args.report)
    report = load_report(report_path)
    plan = build_plan(report, args.rerun_command)
    out = Path(args.out)
    out.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2 if args.pretty else None) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {out} ({plan['summary']['failedTests']} failed tests analyzed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

