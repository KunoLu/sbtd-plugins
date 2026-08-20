#!/usr/bin/env python3
"""Audit frontend source files for UI selector stability.

The output helps generated Playwright tests prefer stable selectors and records
where adding data-testid/data-cy/accessible names would reduce flakiness.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


FRONTEND_EXTS = {".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte"}
IGNORE_DIRS = {
    ".git",
    ".next",
    ".nuxt",
    ".output",
    ".turbo",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "playwright-report",
    "test-results",
    "vendor",
}
INTERACTIVE_TAGS = (
    "Button",
    "button",
    "Input",
    "input",
    "Select",
    "select",
    "textarea",
    "a",
    "Link",
    "Table",
    "Modal",
    "Dialog",
    "Drawer",
    "Form.Item",
    "Upload",
    "DatePicker",
    "Checkbox",
    "Radio",
    "Switch",
    "Tabs",
)
STABLE_ATTR_RE = re.compile(
    r"(data-testid|data-test|data-cy|aria-label|aria-labelledby|role|id)\s*=",
    re.IGNORECASE,
)
LABEL_RE = re.compile(r"(?:label|title|placeholder|name)\s*=\s*['\"]([^'\"]+)['\"]")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def iter_frontend_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in FRONTEND_EXTS:
            continue
        if set(path.parts) & IGNORE_DIRS:
            continue
        files.append(path)
    return sorted(files)


def kebab(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", value)
    value = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value.lower() or "element"


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def element_name(tag: str, attrs: str, body: str | None, index: int) -> str:
    label = LABEL_RE.search(attrs)
    if label:
        return label.group(1).strip()
    if body:
        body = re.sub(r"\s+", " ", body).strip()
        if 0 < len(body) <= 40:
            return body
    return f"{tag}-{index}"


def tag_role(tag: str) -> str:
    lower = tag.lower().replace(".", "-")
    if "button" in lower:
        return "button"
    if "input" in lower or "select" in lower or "textarea" in lower or "datepicker" in lower:
        return "field"
    if lower in {"a", "link"}:
        return "link"
    if "table" in lower:
        return "table"
    if "modal" in lower or "dialog" in lower or "drawer" in lower:
        return "dialog"
    return lower


def audit_file(root: Path, path: Path) -> dict[str, Any]:
    text = read_text(path)
    rel = path.relative_to(root).as_posix()
    tag_pattern = "|".join(re.escape(tag) for tag in INTERACTIVE_TAGS)
    pattern = re.compile(
        rf"<(?P<tag>{tag_pattern})\b(?P<attrs>[^>]*)>(?P<body>[^<]{{0,80}})?",
        re.IGNORECASE,
    )

    elements: list[dict[str, Any]] = []
    stable = 0
    missing: list[dict[str, Any]] = []
    for index, match in enumerate(pattern.finditer(text), start=1):
        tag = match.group("tag")
        attrs = match.group("attrs") or ""
        body = match.group("body") or ""
        is_stable = bool(STABLE_ATTR_RE.search(attrs)) or (
            tag.lower() == "form.item" and bool(re.search(r"label\s*=", attrs))
        )
        name = element_name(tag, attrs, body, index)
        role = tag_role(tag)
        test_id = f"{kebab(Path(rel).stem)}-{kebab(name)}-{role}"
        element = {
            "tag": tag,
            "name": name,
            "line": line_number(text, match.start()),
            "stable": is_stable,
            "suggestedTestId": test_id,
        }
        elements.append(element)
        if is_stable:
            stable += 1
        else:
            missing.append(
                {
                    "file": rel,
                    "line": element["line"],
                    "element": name,
                    "tag": tag,
                    "suggestedTestId": test_id,
                    "reason": "缺少 data-testid/data-cy/aria-label/role/id 等稳定定位信息",
                }
            )

    return {
        "file": rel,
        "interactiveElements": len(elements),
        "stableElements": stable,
        "missingStableSelectors": missing,
    }


def score(stable: int, total: int) -> int:
    if total == 0:
        return 100
    return round(stable * 100 / total)


def stability_level(value: int) -> str:
    if value >= 85:
        return "high"
    if value >= 60:
        return "medium"
    return "low"


def build_report(root: Path) -> dict[str, Any]:
    files = [audit_file(root, path) for path in iter_frontend_files(root)]
    files = [item for item in files if item["interactiveElements"] > 0]
    total = sum(item["interactiveElements"] for item in files)
    stable = sum(item["stableElements"] for item in files)
    missing = [missing for item in files for missing in item["missingStableSelectors"]]
    selector_score = score(stable, total)
    return {
        "summary": {
            "filesScanned": len(files),
            "interactiveElements": total,
            "stableElements": stable,
            "missingStableSelectors": len(missing),
            "selectorStabilityScore": selector_score,
            "selectorStabilityLevel": stability_level(selector_score),
        },
        "files": files,
        "recommendations": missing[:200],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit frontend selector stability.")
    parser.add_argument("--root", default=".", help="Project root.")
    parser.add_argument("--out", default="ui-selector-audit.json", help="Selector audit output path.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    report = build_report(root)
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None) + "\n",
        encoding="utf-8",
    )
    summary = report["summary"]
    print(
        "Wrote "
        f"{out} ({summary['selectorStabilityScore']} selector stability, "
        f"{summary['missingStableSelectors']} missing stable selectors)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

