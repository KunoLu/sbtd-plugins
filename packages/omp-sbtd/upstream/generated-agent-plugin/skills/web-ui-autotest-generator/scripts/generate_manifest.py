#!/usr/bin/env python3
"""Generate an initial Web UI test manifest from frontend/backend source files.

This script is intentionally heuristic and dependency-free. It gives reviewers a
stable first pass that can be refined before test generation.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FRONTEND_EXTS = {".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte"}
BACKEND_EXTS = {".js", ".ts", ".py", ".java", ".kt", ".go", ".cs"}
PAGE_DIR_MARKERS = {"/pages/", "/views/", "/routes/", "/app/"}
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

BUTTON_WORDS = (
    "新增",
    "创建",
    "添加",
    "编辑",
    "修改",
    "删除",
    "移除",
    "查询",
    "搜索",
    "重置",
    "保存",
    "提交",
    "确定",
    "取消",
    "导出",
    "下载",
    "上传",
    "详情",
    "查看",
    "登录",
    "注册",
    "启用",
    "禁用",
    "审核",
    "Create",
    "Add",
    "Edit",
    "Delete",
    "Search",
    "Reset",
    "Save",
    "Submit",
    "Cancel",
    "Export",
    "Download",
    "Upload",
    "Detail",
    "View",
    "Login",
)


@dataclass(frozen=True)
class SourceFile:
    path: Path
    rel: str
    text: str


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def iter_source_files(root: Path, exts: set[str]) -> list[SourceFile]:
    files: list[SourceFile] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in exts:
            continue
        parts = set(path.parts)
        if parts & IGNORE_DIRS:
            continue
        rel = path.relative_to(root).as_posix()
        files.append(SourceFile(path=path, rel=rel, text=read_text(path)))
    return files


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = re.sub(r"\s+", " ", value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def slug(value: str) -> str:
    value = value.replace("[", ":").replace("]", "")
    value = re.sub(r"[^a-zA-Z0-9_\-\u4e00-\u9fff]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value.lower() or "page"


def guess_project_name(root: Path) -> str:
    package_json = root / "package.json"
    if package_json.exists():
        try:
            data = json.loads(read_text(package_json))
            if data.get("name"):
                return str(data["name"])
        except json.JSONDecodeError:
            pass
    return root.name


def detect_frontend_framework(root: Path) -> str:
    package_json = root / "package.json"
    if not package_json.exists():
        return "unknown"
    try:
        data = json.loads(read_text(package_json))
    except json.JSONDecodeError:
        return "unknown"
    deps = {}
    deps.update(data.get("dependencies", {}))
    deps.update(data.get("devDependencies", {}))
    names = set(deps)
    if "next" in names:
        return "next"
    if "nuxt" in names:
        return "nuxt"
    if "@angular/core" in names:
        return "angular"
    if "vue" in names:
        return "vue"
    if "svelte" in names or "@sveltejs/kit" in names:
        return "svelte"
    if "react" in names:
        return "react"
    return "unknown"


def detect_backend_framework(root: Path, backend_files: list[SourceFile]) -> str | None:
    package_json = root / "package.json"
    if package_json.exists():
        try:
            data = json.loads(read_text(package_json))
            deps = {}
            deps.update(data.get("dependencies", {}))
            deps.update(data.get("devDependencies", {}))
            names = set(deps)
            if "@nestjs/core" in names:
                return "nestjs"
            if "express" in names:
                return "express"
            if "koa" in names:
                return "koa"
        except json.JSONDecodeError:
            pass
    all_text = "\n".join(file.text[:5000] for file in backend_files)
    if "@SpringBootApplication" in all_text or "@RestController" in all_text:
        return "spring-boot"
    if "FastAPI(" in all_text:
        return "fastapi"
    if "Flask(" in all_text:
        return "flask"
    if "django" in all_text.lower():
        return "django"
    return None


def route_from_page_path(rel: str) -> str:
    path = rel
    for marker in ("src/pages/", "src/views/", "src/routes/", "pages/", "views/", "routes/", "app/"):
        if marker in path:
            path = path.split(marker, 1)[1]
            break
    path = re.sub(r"\.(page|route|view|component)?\.(tsx|ts|jsx|js|vue|svelte)$", "", path)
    path = re.sub(r"\.(tsx|ts|jsx|js|vue|svelte)$", "", path)
    path = path.replace("/index", "")
    path = path.replace("/page", "")
    path = path.replace("[", ":").replace("]", "")
    path = re.sub(r"\([^)]+\)/", "", path)
    path = re.sub(r"^index$", "", path)
    return "/" + path.strip("/")


def is_page_file(file: SourceFile) -> bool:
    normalized = "/" + file.rel
    if any(marker in normalized for marker in PAGE_DIR_MARKERS):
        return True
    name = file.path.name
    if name in {"page.tsx", "page.jsx", "page.vue", "page.svelte"}:
        return True
    return bool(re.search(r"(Page|View)\.(tsx|jsx|vue|svelte)$", name))


def extract_route_paths(text: str) -> list[str]:
    paths: list[str] = []
    patterns = [
        r"path\s*:\s*['\"]([^'\"]+)['\"]",
        r"<Route[^>]+path\s*=\s*['\"]([^'\"]+)['\"]",
        r"router\.(?:get|post|put|patch|delete)\(\s*['\"]([^'\"]+)['\"]",
        r"app\.(?:get|post|put|patch|delete)\(\s*['\"]([^'\"]+)['\"]",
    ]
    for pattern in patterns:
        paths.extend(re.findall(pattern, text))
    return unique([path for path in paths if path.startswith("/")])


def extract_title(file: SourceFile) -> str:
    candidates: list[str] = []
    patterns = [
        r"title\s*[:=]\s*['\"]([^'\"]+)['\"]",
        r"name\s*[:=]\s*['\"]([^'\"]+)['\"]",
        r"<h1[^>]*>([^<]+)</h1>",
        r"<h2[^>]*>([^<]+)</h2>",
        r"<title[^>]*>([^<]+)</title>",
    ]
    for pattern in patterns:
        candidates.extend(re.findall(pattern, file.text, flags=re.IGNORECASE))
    if candidates:
        return unique(candidates)[0]
    stem = file.path.stem
    if stem in {"index", "page"}:
        parent = file.path.parent.name
        return parent.replace("-", " ").replace("_", " ").title()
    return stem.replace("-", " ").replace("_", " ").title()


def extract_buttons(text: str) -> list[str]:
    buttons: list[str] = []
    patterns = [
        r"<(?:Button|button|a|Link)[^>]*(?:aria-label|title)\s*=\s*['\"]([^'\"]+)['\"]",
        r"<(?:Button|button)[^>]*>\s*([^<>{}\n]{1,40})\s*</(?:Button|button)>",
        r"\b(?:text|label)\s*[:=]\s*['\"]([^'\"]{1,40})['\"]",
    ]
    for pattern in patterns:
        buttons.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    for word in BUTTON_WORDS:
        if word in text:
            buttons.append(word)
    return unique(buttons)


def extract_links(text: str) -> list[str]:
    links: list[str] = []
    patterns = [
        r"<(?:Link|a)[^>]*(?:href|to)\s*=\s*['\"]([^'\"]+)['\"]",
        r"(?:navigate|router\.push|history\.push)\(\s*['\"]([^'\"]+)['\"]",
    ]
    for pattern in patterns:
        links.extend(re.findall(pattern, text))
    return unique([link for link in links if link.startswith("/")])


def extract_fields(text: str) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    patterns = [
        r"<(?:Input|input|Select|textarea|DatePicker)[^>]*(?:name|id|placeholder|label)\s*=\s*['\"]([^'\"]+)['\"]",
        r"(?:name|field|dataIndex|label)\s*:\s*['\"]([^'\"]+)['\"]",
        r"<Form\.Item[^>]*label\s*=\s*['\"]([^'\"]+)['\"]",
    ]
    for pattern in patterns:
        for field in re.findall(pattern, text):
            fields.append(
                {
                    "name": field,
                    "type": guess_field_type(field, text),
                    "required": bool(re.search(rf"{re.escape(field)}[\s\S]{{0,160}}required\s*[:=]?\s*true", text)),
                }
            )
    deduped: dict[str, dict[str, Any]] = {}
    for field in fields:
        deduped.setdefault(field["name"], field)
        deduped[field["name"]]["required"] = deduped[field["name"]]["required"] or field["required"]
    return list(deduped.values())


def guess_field_type(field: str, text: str) -> str:
    lower = field.lower()
    if any(token in lower for token in ("date", "time", "日期", "时间")):
        return "date"
    if any(token in lower for token in ("email", "邮箱")):
        return "email"
    if any(token in lower for token in ("phone", "mobile", "tel", "手机号", "电话")):
        return "tel"
    if any(token in lower for token in ("password", "密码")):
        return "password"
    if re.search(rf"{re.escape(field)}[\s\S]{{0,120}}(?:Select|select)", text):
        return "select"
    return "text"


def extract_tables(text: str) -> list[dict[str, Any]]:
    if not re.search(r"<(?:Table|table)|columns\s*=", text):
        return []
    columns = unique(re.findall(r"(?:title|label|dataIndex)\s*:\s*['\"]([^'\"]+)['\"]", text))
    row_actions = [word for word in ("查看", "详情", "编辑", "删除", "启用", "禁用", "View", "Edit", "Delete") if word in text]
    return [{"name": "primary-table", "columns": columns[:30], "rowActions": unique(row_actions)}]


def extract_dialogs(text: str) -> list[str]:
    dialogs: list[str] = []
    for marker, name in (
        ("<Modal", "modal"),
        ("<Dialog", "dialog"),
        ("<Drawer", "drawer"),
        ("ElDialog", "dialog"),
        ("el-dialog", "dialog"),
    ):
        if marker in text:
            dialogs.append(name)
    titled = re.findall(r"(?:Modal|Dialog|Drawer)[^>\n]*(?:title|header)\s*=\s*['\"]([^'\"]+)['\"]", text)
    dialogs.extend(titled)
    return unique(dialogs)


def extract_api_dependencies(text: str) -> list[dict[str, str]]:
    dependencies: list[dict[str, str]] = []
    patterns = [
        r"(GET|POST|PUT|PATCH|DELETE)\s*,?\s*['\"]([^'\"]*/api/[^'\"]+)['\"]",
        r"(?:fetch|axios\.(get|post|put|patch|delete))\(\s*['\"]([^'\"]+)['\"]",
        r"request\(\s*\{[\s\S]{0,220}?url\s*:\s*['\"]([^'\"]+)['\"][\s\S]{0,220}?method\s*:\s*['\"]([^'\"]+)['\"]",
    ]
    for method, path in re.findall(patterns[0], text, flags=re.IGNORECASE):
        dependencies.append({"method": method.upper(), "path": path, "trigger": "user-action"})
    for method, path in re.findall(patterns[1], text, flags=re.IGNORECASE):
        if path.startswith("/") or "/api/" in path:
            dependencies.append({"method": (method or "GET").upper(), "path": path, "trigger": "user-action"})
    for path, method in re.findall(patterns[2], text, flags=re.IGNORECASE):
        dependencies.append({"method": method.upper(), "path": path, "trigger": "user-action"})
    deduped: dict[tuple[str, str], dict[str, str]] = {}
    for item in dependencies:
        deduped[(item["method"], item["path"])] = item
    return list(deduped.values())


def infer_tests(buttons: list[str], fields: list[dict[str, Any]], tables: list[dict[str, Any]], links: list[str], dialogs: list[str]) -> list[dict[str, str]]:
    tests = [
        {"id": "load", "name": "页面正常加载", "type": "load", "priority": "P0"},
        {"id": "render-core", "name": "核心控件可见", "type": "smoke", "priority": "P0"},
    ]
    text = " ".join(buttons)
    if any(word in text for word in ("查询", "搜索", "Search")):
        tests.append({"id": "search-reset", "name": "查询和重置", "type": "happy-path", "priority": "P0"})
    if any(word in text for word in ("新增", "创建", "添加", "Create", "Add")):
        tests.append({"id": "create-success", "name": "新增成功", "type": "happy-path", "priority": "P0"})
    if any(word in text for word in ("编辑", "修改", "Edit")):
        tests.append({"id": "edit-success", "name": "编辑成功", "type": "happy-path", "priority": "P1"})
    if any(word in text for word in ("删除", "移除", "Delete")):
        tests.append({"id": "delete-confirm", "name": "删除确认", "type": "happy-path", "priority": "P1"})
    if fields:
        tests.append({"id": "form-validation", "name": "表单必填校验", "type": "validation", "priority": "P0"})
    if tables:
        tests.append({"id": "table-empty-pagination", "name": "列表空态和分页", "type": "happy-path", "priority": "P1"})
    if links:
        tests.append({"id": "navigation", "name": "页面跳转", "type": "navigation", "priority": "P1"})
    if dialogs:
        tests.append({"id": "dialog-open-close", "name": "弹窗打开关闭", "type": "happy-path", "priority": "P1"})
    tests.append({"id": "api-error", "name": "接口失败提示", "type": "error-state", "priority": "P2"})
    return tests


def build_page(file: SourceFile, route_override: str | None = None) -> dict[str, Any]:
    route = route_override or route_from_page_path(file.rel)
    title = extract_title(file)
    buttons = extract_buttons(file.text)
    links = extract_links(file.text)
    fields = extract_fields(file.text)
    tables = extract_tables(file.text)
    dialogs = extract_dialogs(file.text)
    apis = extract_api_dependencies(file.text)
    return {
        "id": slug(route or title),
        "name": title,
        "route": route,
        "sourceFiles": [file.rel],
        "authRequired": bool(re.search(r"auth|login|permission|token|鉴权|权限", file.text, flags=re.IGNORECASE)),
        "permissions": unique(re.findall(r"(?:permission|auth|role)\s*[:=]\s*['\"]([^'\"]+)['\"]", file.text)),
        "uiElements": {
            "buttons": buttons,
            "links": links,
            "forms": [{"name": "primary-form", "fields": fields}] if fields else [],
            "tables": tables,
            "dialogs": dialogs,
        },
        "apiDependencies": apis,
        "flows": infer_flows(route, buttons, links),
        "proposedTests": infer_tests(buttons, fields, tables, links, dialogs),
    }


def infer_flows(route: str, buttons: list[str], links: list[str]) -> list[dict[str, Any]]:
    flows: list[dict[str, Any]] = []
    if any(word in buttons for word in ("新增", "创建", "添加", "Create", "Add")):
        flows.append(
            {
                "name": "创建后回到列表验证",
                "steps": [f"打开 {route}", "点击新增", "填写表单", "提交", "验证列表出现新数据"],
                "expectedResult": "新数据创建成功并可在列表中找到",
            }
        )
    if links:
        flows.append(
            {
                "name": "页面跳转验证",
                "steps": [f"打开 {route}", "点击目标链接", "验证目标页面加载"],
                "expectedResult": "页面跳转成功且目标页面核心内容可见",
            }
        )
    return flows


def merge_route_definitions(frontend_files: list[SourceFile], pages: list[dict[str, Any]]) -> None:
    routes_by_source: dict[str, list[str]] = {}
    for file in frontend_files:
        routes = extract_route_paths(file.text)
        if routes:
            routes_by_source[file.rel] = routes
    existing_routes = {page["route"] for page in pages}
    for source, routes in routes_by_source.items():
        for route in routes:
            if route in existing_routes:
                continue
            pages.append(
                {
                    "id": slug(route),
                    "name": route.strip("/") or "Home",
                    "route": route,
                    "sourceFiles": [source],
                    "authRequired": False,
                    "permissions": [],
                    "uiElements": {"buttons": [], "links": [], "forms": [], "tables": [], "dialogs": []},
                    "apiDependencies": [],
                    "flows": [],
                    "proposedTests": [
                        {"id": "load", "name": "页面正常加载", "type": "load", "priority": "P0"},
                        {"id": "render-core", "name": "核心控件可见", "type": "smoke", "priority": "P1"},
                    ],
                }
            )
            existing_routes.add(route)


def build_manifest(root: Path) -> dict[str, Any]:
    frontend_files = iter_source_files(root, FRONTEND_EXTS)
    backend_files = iter_source_files(root, BACKEND_EXTS)
    pages = [build_page(file) for file in frontend_files if is_page_file(file)]
    merge_route_definitions(frontend_files, pages)
    pages.sort(key=lambda page: page["route"])
    return {
        "project": {
            "name": guess_project_name(root),
            "frontendFramework": detect_frontend_framework(root),
            "backendFramework": detect_backend_framework(root, backend_files),
            "testFramework": "playwright",
        },
        "pages": pages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ui-test-manifest.json from source code.")
    parser.add_argument("--root", default=".", help="Project root to scan.")
    parser.add_argument("--out", default="ui-test-manifest.json", help="Manifest output path.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    manifest = build_manifest(root)
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    out.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2 if args.pretty else None) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {out} with {len(manifest['pages'])} discovered pages/routes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
