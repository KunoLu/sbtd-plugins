#!/usr/bin/env python3
"""Check generated UI test coverage against ui-test-manifest.json."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


IGNORE_DIRS = {"node_modules", ".git", "playwright-report", "test-results", "dist", "build"}
SPEC_SUFFIXES = (".spec.ts", ".test.ts", ".spec.js", ".test.js", ".cy.ts", ".cy.js")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def iter_specs(root: Path, tests_dir: str) -> list[Path]:
    base = root / tests_dir
    if not base.exists():
        base = root
    specs: list[Path] = []
    for path in base.rglob("*"):
        if not path.is_file() or not path.name.endswith(SPEC_SUFFIXES):
            continue
        if set(path.parts) & IGNORE_DIRS:
            continue
        specs.append(path)
    return sorted(specs)


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def contains_any(text: str, values: list[str]) -> bool:
    haystack = normalize(text)
    for value in values:
        if value and normalize(value) in haystack:
            return True
    return False


def page_matching_specs(page: dict[str, Any], spec_texts: dict[Path, str]) -> list[Path]:
    route = page.get("route", "")
    name = page.get("name", "")
    page_id = page.get("id", "")
    needles = [route, name, page_id]
    matched = [path for path, text in spec_texts.items() if contains_any(text, needles)]
    if matched:
        return matched
    source_stems = [Path(source).stem for source in page.get("sourceFiles", [])]
    return [path for path, text in spec_texts.items() if contains_any(text, source_stems)]


def infer_covered_items(page: dict[str, Any], texts: list[str]) -> list[str]:
    combined = "\n".join(texts)
    covered: list[str] = []
    if page_matching_text(page, combined):
        covered.append("page-load")
    buttons = page.get("uiElements", {}).get("buttons", [])
    if contains_any(combined, [button for button in buttons if button in ("查询", "搜索", "Search")]):
        covered.append("search")
    if contains_any(combined, [button for button in buttons if button in ("重置", "Reset")]):
        covered.append("reset")
    if contains_any(combined, [button for button in buttons if button in ("新增", "创建", "添加", "Create", "Add")]):
        covered.append("create")
    if contains_any(combined, [button for button in buttons if button in ("编辑", "修改", "Edit")]):
        covered.append("edit")
    if contains_any(combined, [button for button in buttons if button in ("删除", "移除", "Delete")]):
        covered.append("delete")
    if re.search(r"required|校验|validation|invalid|error", combined, flags=re.IGNORECASE):
        covered.append("form-validation")
    if re.search(r"empty|no data|暂无|空", combined, flags=re.IGNORECASE):
        covered.append("empty-state")
    if re.search(r"pagination|分页|next page|上一页|下一页", combined, flags=re.IGNORECASE):
        covered.append("pagination")
    if re.search(r"dialog|modal|drawer|弹窗|抽屉", combined, flags=re.IGNORECASE):
        covered.append("dialog")
    if re.search(r"401|403|permission|unauthorized|未登录|无权限", combined, flags=re.IGNORECASE):
        covered.append("permission")
    if re.search(r"route\.fulfill|route\.abort|500|network error|接口失败|请求失败", combined, flags=re.IGNORECASE):
        covered.append("api-error")
    if page.get("uiElements", {}).get("links") and re.search(r"toHaveURL|goto|click", combined):
        covered.append("navigation")
    return sorted(set(covered))


def page_matching_text(page: dict[str, Any], text: str) -> bool:
    return contains_any(text, [page.get("route", ""), page.get("name", ""), page.get("id", "")])


def expected_items(page: dict[str, Any]) -> list[tuple[str, str]]:
    items = [("page-load", "每个路由至少需要页面加载/核心渲染测试")]
    ui = page.get("uiElements", {})
    buttons = " ".join(ui.get("buttons", []))
    if any(word in buttons for word in ("查询", "搜索", "Search")):
        items.append(("search", "发现查询/搜索按钮但没有对应测试"))
    if any(word in buttons for word in ("重置", "Reset")):
        items.append(("reset", "发现重置按钮但没有对应测试"))
    if any(word in buttons for word in ("新增", "创建", "添加", "Create", "Add")):
        items.append(("create", "发现新增/创建入口但没有对应测试"))
    if any(word in buttons for word in ("编辑", "修改", "Edit")):
        items.append(("edit", "发现编辑入口但没有对应测试"))
    if any(word in buttons for word in ("删除", "移除", "Delete")):
        items.append(("delete", "发现删除入口但没有确认/结果测试"))
    if ui.get("forms"):
        items.append(("form-validation", "发现表单但没有校验测试"))
    if ui.get("tables"):
        items.append(("empty-state", "发现列表/表格但没有空态测试"))
        items.append(("pagination", "发现列表/表格，建议覆盖分页或说明无需分页"))
    if ui.get("dialogs"):
        items.append(("dialog", "发现弹窗/抽屉但没有打开关闭/提交测试"))
    if ui.get("links"):
        items.append(("navigation", "发现页面链接但没有跳转测试"))
    if page.get("apiDependencies"):
        items.append(("api-error", "发现 API 依赖但没有失败态测试"))
    if page.get("authRequired"):
        items.append(("permission", "页面需要鉴权但没有权限/未登录测试"))
    return items


def coverage_level(covered: list[str], missing: list[dict[str, str]]) -> str:
    if not covered:
        return "missing"
    if covered == ["page-load"] and missing:
        return "smoke"
    if missing:
        return "partial"
    return "full"


def count_tests(spec_texts: dict[Path, str]) -> int:
    test_case_pattern = re.compile(r"\btest(?:\.(?:only|skip|fixme))?\s*\(")
    return sum(len(test_case_pattern.findall(text)) for text in spec_texts.values())


def percent(part: int, total: int) -> int:
    if total == 0:
        return 100
    return round(part * 100 / total)


def api_dependency_covered(api: dict[str, Any], texts: list[str]) -> bool:
    combined = "\n".join(texts).lower()
    method = str(api.get("method", "")).lower()
    path = str(api.get("path", "")).lower()
    if not path:
        return False
    return path in combined or f"{method} {path}" in combined or path.replace("{", ":").replace("}", "") in combined


def weighted_score(values: list[tuple[int, int, bool]]) -> int:
    active = [(score, weight) for score, weight, enabled in values if enabled]
    total_weight = sum(weight for _, weight in active)
    if total_weight == 0:
        return 100
    return round(sum(score * weight for score, weight in active) / total_weight)


def load_selector_audit(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError:
        return None


def build_report(
    manifest: dict[str, Any],
    root: Path,
    tests_dir: str,
    selector_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    specs = iter_specs(root, tests_dir)
    spec_texts = {path: read_text(path) for path in specs}
    pages = []
    expected_total = 0
    covered_total = 0
    api_total = 0
    api_covered_total = 0
    for page in manifest.get("pages", []):
        matching = page_matching_specs(page, spec_texts)
        texts = [spec_texts[path] for path in matching]
        covered = infer_covered_items(page, texts)
        expected = expected_items(page)
        api_dependencies = page.get("apiDependencies", [])
        api_covered = sum(1 for api in api_dependencies if api_dependency_covered(api, texts))
        expected_total += len(expected)
        covered_total += sum(1 for item, _ in expected if item in covered)
        api_total += len(api_dependencies)
        api_covered_total += api_covered
        missing = [
            {
                "item": item,
                "reason": reason,
                "suggestedTest": suggested_test_name(page, item),
            }
            for item, reason in expected
            if item not in covered
        ]
        pages.append(
            {
                "route": page.get("route", ""),
                "coverageLevel": coverage_level(covered, missing),
                "score": {
                    "expectedItems": len(expected),
                    "coveredItems": sum(1 for item, _ in expected if item in covered),
                    "coveragePercent": percent(sum(1 for item, _ in expected if item in covered), len(expected)),
                    "apiDependencies": len(api_dependencies),
                    "apiDependenciesCovered": api_covered,
                    "apiCoveragePercent": percent(api_covered, len(api_dependencies)),
                },
                "covered": covered,
                "missing": missing,
                "testFiles": [path.relative_to(root).as_posix() for path in matching],
            }
        )

    routes_covered = sum(1 for page in pages if page["coverageLevel"] != "missing")
    cross_page_flows = infer_cross_page_flows(manifest, spec_texts, root)
    cross_total = len(cross_page_flows)
    cross_covered = sum(1 for flow in cross_page_flows if flow["covered"])
    has_pages = bool(manifest.get("pages"))
    route_coverage = percent(routes_covered, len(manifest.get("pages", []))) if has_pages else 0
    feature_coverage = percent(covered_total, expected_total) if has_pages else 0
    api_coverage = percent(api_covered_total, api_total)
    cross_flow_coverage = percent(cross_covered, cross_total)
    selector_summary = selector_audit.get("summary", {}) if selector_audit else {}
    selector_score = selector_summary.get("selectorStabilityScore")
    overall_score = 0 if not has_pages else weighted_score(
        [
            (route_coverage, 25, bool(manifest.get("pages"))),
            (feature_coverage, 40, expected_total > 0),
            (api_coverage, 15, api_total > 0),
            (cross_flow_coverage, 10, cross_total > 0),
            (int(selector_score), 10, isinstance(selector_score, int)),
        ]
    )
    levels = {page["coverageLevel"] for page in pages}
    overall = "full"
    if not has_pages:
        overall = "missing"
    elif "missing" in levels:
        overall = "partial" if routes_covered else "missing"
    elif "partial" in levels:
        overall = "partial"
    elif "smoke" in levels:
        overall = "smoke"

    return {
        "summary": {
            "routesDiscovered": len(manifest.get("pages", [])),
            "routesCovered": routes_covered,
            "testsGenerated": count_tests(spec_texts),
            "coverageLevel": overall,
            "scores": {
                "overallScore": overall_score,
                "pageCoveragePercent": route_coverage,
                "featureCoveragePercent": feature_coverage,
                "apiCoveragePercent": api_coverage,
                "crossPageFlowCoveragePercent": cross_flow_coverage,
                "selectorStabilityScore": selector_score,
            },
            "totals": {
                "expectedFeatureItems": expected_total,
                "coveredFeatureItems": covered_total,
                "apiDependenciesDiscovered": api_total,
                "apiDependenciesCovered": api_covered_total,
                "crossPageFlowsDiscovered": cross_total,
                "crossPageFlowsCovered": cross_covered,
            },
        },
        "pages": pages,
        "selectorAudit": selector_summary,
        "crossPageFlows": cross_page_flows,
    }


def suggested_test_name(page: dict[str, Any], item: str) -> str:
    route = page.get("route", "page")
    names = {
        "page-load": f"{route} 页面正常加载",
        "search": f"{route} 查询功能",
        "reset": f"{route} 重置查询条件",
        "create": f"{route} 新增成功",
        "edit": f"{route} 编辑成功",
        "delete": f"{route} 删除确认",
        "form-validation": f"{route} 表单必填校验",
        "empty-state": f"{route} 空数据状态",
        "pagination": f"{route} 分页切换",
        "dialog": f"{route} 弹窗打开关闭",
        "navigation": f"{route} 页面跳转",
        "api-error": f"{route} 接口失败提示",
        "permission": f"{route} 无权限或未登录访问",
    }
    return names.get(item, f"{route} {item}")


def infer_cross_page_flows(manifest: dict[str, Any], spec_texts: dict[Path, str], root: Path) -> list[dict[str, Any]]:
    flows = []
    all_text_by_path = {path: normalize(text) for path, text in spec_texts.items()}
    for page in manifest.get("pages", []):
        for flow in page.get("flows", []):
            name = flow.get("name", "")
            steps = flow.get("steps", [])
            matched_path = None
            for path, text in all_text_by_path.items():
                if contains_any(text, [name]) or sum(1 for step in steps if normalize(step) in text) >= 2:
                    matched_path = path
                    break
            flows.append(
                {
                    "name": name,
                    "covered": matched_path is not None,
                    "testFile": matched_path.relative_to(root).as_posix() if matched_path else None,
                    "missingReason": None if matched_path else "未发现覆盖该跨页面/业务流程的场景用例",
                }
            )
    return flows


def main() -> int:
    parser = argparse.ArgumentParser(description="Check UI test coverage from manifest and specs.")
    parser.add_argument("--root", default=".", help="Project root.")
    parser.add_argument("--manifest", default="ui-test-manifest.json", help="Input manifest path.")
    parser.add_argument("--tests-dir", default="tests/e2e", help="Directory containing generated UI tests.")
    parser.add_argument("--selector-audit", default="ui-selector-audit.json", help="Optional selector audit JSON path.")
    parser.add_argument("--out", default="ui-test-coverage.json", help="Coverage output path.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path
    manifest = json.loads(read_text(manifest_path))
    selector_audit_path = Path(args.selector_audit)
    if not selector_audit_path.is_absolute():
        selector_audit_path = root / selector_audit_path
    selector_audit = load_selector_audit(selector_audit_path)
    report = build_report(manifest, root, args.tests_dir, selector_audit)

    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None) + "\n",
        encoding="utf-8",
    )
    print(
        "Wrote "
        f"{out} ({report['summary']['routesCovered']}/"
        f"{report['summary']['routesDiscovered']} routes covered, "
        f"{report['summary']['testsGenerated']} tests found, "
        f"score {report['summary']['scores']['overallScore']})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
