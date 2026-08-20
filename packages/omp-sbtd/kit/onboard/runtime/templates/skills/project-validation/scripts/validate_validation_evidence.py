#!/usr/bin/env python3
"""Validate validation-evidence envelopes.

v1: JSON Schema shape only.
v2: schema plus referential integrity, report parsing, and locator binding.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

REFERENCE_ROOT = Path(__file__).resolve().parents[1] / "references"
V1_SCHEMA = REFERENCE_ROOT / "validation-evidence.schema.json"
V2_SCHEMA = REFERENCE_ROOT / "validation-evidence.v2.schema.json"
DIGEST_PROPERTY = "sbtd.sourceLocatorDigest"
HEX64 = r"^[0-9a-f]{64}$"

REASON_OK = "OK"


class EvidenceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def normalize_commit(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise EvidenceError("REVISION_MISMATCH", "sourceCommit is required")
    commit = value.strip().lower()
    if len(commit) < 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise EvidenceError("REVISION_MISMATCH", f"invalid sourceCommit {value!r}")
    return commit


def posix_relative(path: str) -> str:
    if not isinstance(path, str) or not path.strip():
        raise EvidenceError("UNSAFE_PATH", "path is empty")
    candidate = path.replace("\\", "/")
    if candidate.startswith("/") or candidate.startswith("~"):
        raise EvidenceError("UNSAFE_PATH", f"absolute path rejected: {path}")
    parts = [part for part in candidate.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise EvidenceError("UNSAFE_PATH", f"path escape rejected: {path}")
    return "/".join(parts)


def resolve_safe(root: Path, relative: str) -> Path:
    rel = posix_relative(relative)
    resolved_root = root.resolve()
    target = (resolved_root / rel).resolve()
    try:
        target.relative_to(resolved_root)
    except ValueError as exc:
        raise EvidenceError("UNSAFE_PATH", f"symlink or path escape: {relative}") from exc
    return target


def source_locator_payload(locator: dict[str, Any]) -> dict[str, Any]:
    return {
        "examplesFingerprint": locator.get("examplesFingerprint") or None,
        "feature": locator["feature"],
        "path": posix_relative(locator["path"]),
        "repositoryKey": locator["repositoryKey"],
        "rule": locator.get("rule") or None,
        "scenario": locator["scenario"],
        "sourceCommit": normalize_commit(locator["sourceCommit"]),
        "sourceRef": locator["sourceRef"],
    }


def source_locator_digest(locator: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json(source_locator_payload(locator)))


def load_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_schema(envelope: dict[str, Any], schema_path: Path) -> None:
    if jsonschema is None:
        raise EvidenceError(
            "VALIDATOR_UNAVAILABLE",
            "jsonschema is not installed; install project-validation/requirements.txt",
        )
    schema = load_schema(schema_path)
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(envelope), key=lambda item: list(item.path))
    if errors:
        first = errors[0]
        path = "/".join(str(part) for part in first.path)
        raise EvidenceError("SCHEMA_INVALID", f"{path}: {first.message}" if path else first.message)


def require_file(path: Path, relative: str) -> None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise EvidenceError("UNSAFE_PATH", f"not a regular file: {relative}")
    if relative.replace("\\", "/").endswith(".feature") and path.is_dir():
        raise EvidenceError("FEATURE_NOT_FILE", f"directory named as feature: {relative}")


def parse_junit(data: bytes) -> list[dict[str, Any]]:
    class RejectingTreeBuilder(ET.TreeBuilder):
        def doctype(self, name, pubid, system):  # type: ignore[no-untyped-def]
            raise EvidenceError("XXE_OR_MALFORMED", "JUnit XML DTD/entity is not allowed")

    parser = ET.XMLParser(target=RejectingTreeBuilder())
    expat = getattr(parser, "parser", None)
    if expat is not None:
        def reject(*_args: object, **_kwargs: object) -> None:
            raise EvidenceError("XXE_OR_MALFORMED", "JUnit XML DTD/entity is not allowed")

        if hasattr(expat, "EntityDeclHandler"):
            expat.EntityDeclHandler = reject
        if hasattr(expat, "UnparsedEntityDeclHandler"):
            expat.UnparsedEntityDeclHandler = reject
        if hasattr(expat, "ExternalEntityRefHandler"):
            expat.ExternalEntityRefHandler = lambda *_args, **_kwargs: 0
        if hasattr(expat, "SetParamEntityParsing"):
            expat.SetParamEntityParsing(0)
    try:
        root = ET.fromstring(data, parser=parser)
    except EvidenceError:
        raise
    except ET.ParseError as exc:
        raise EvidenceError("XXE_OR_MALFORMED", f"malformed JUnit XML: {exc}") from exc

    cases: list[dict[str, Any]] = []

    def walk(node: ET.Element, suites: list[str]) -> None:
        tag = node.tag.split("}", 1)[-1]
        if tag == "testsuite":
            name = node.attrib.get("name", "")
            next_suites = [*suites, name] if name else suites
            for child in list(node):
                walk(child, next_suites)
            return
        if tag == "testsuites":
            for child in list(node):
                walk(child, suites)
            return
        if tag != "testcase":
            return
        properties: list[str] = []
        failed = False
        skipped = False
        for child in list(node):
            child_tag = child.tag.split("}", 1)[-1]
            if child_tag in {"failure", "error"}:
                failed = True
            elif child_tag == "skipped":
                skipped = True
            elif child_tag == "properties":
                for prop in list(child):
                    if prop.tag.split("}", 1)[-1] != "property":
                        continue
                    if prop.attrib.get("name") == DIGEST_PROPERTY:
                        properties.append(prop.attrib.get("value", ""))
            elif child_tag == "property" and child.attrib.get("name") == DIGEST_PROPERTY:
                properties.append(child.attrib.get("value", ""))
        outcome = "failed" if failed else "skipped" if skipped else "passed"
        cases.append(
            {
                "suites": suites,
                "classname": node.attrib.get("classname", ""),
                "name": node.attrib.get("name", ""),
                "file": posix_relative(node.attrib["file"]) if node.attrib.get("file") else None,
                "outcome": outcome,
                "bindings": properties,
            }
        )

    walk(root, [])
    return cases


def _playwright_specs(node: dict[str, Any], inherited_file: str | None) -> list[dict[str, Any]]:
    file_name = node.get("file") or inherited_file
    inherited = (
        list(node["titlePath"])
        if "titlePath" in node
        else ([node["title"]] if node.get("title") else [])
    )
    found: list[dict[str, Any]] = []
    for spec in node.get("specs") or []:
        spec_file = spec.get("file") or file_name
        title = spec.get("title") or ""
        for test in spec.get("tests") or []:
            results = test.get("results") or []
            status = (results[-1].get("status") if results else test.get("status")) or "unknown"
            annotations = []
            for annotation in test.get("annotations") or []:
                if annotation.get("type") == DIGEST_PROPERTY:
                    annotations.append(annotation.get("description") or annotation.get("value") or "")
            found.append(
                {
                    "project": test.get("projectName") or (test.get("project") or {}).get("name") or "",
                    "file": posix_relative(spec_file) if spec_file else "",
                    "titlePath": [*inherited, title] if title else list(inherited),
                    "outcome": "passed" if status == "passed" else status,
                    "bindings": annotations,
                }
            )
    for child in node.get("suites") or []:
        child_titles = [*inherited, *([child["title"]] if child.get("title") else [])]
        child = {**child, "titlePath": [part for part in child_titles if part]}
        found.extend(_playwright_specs(child, file_name))
    return found


def parse_playwright(data: bytes) -> list[dict[str, Any]]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise EvidenceError("XXE_OR_MALFORMED", f"malformed Playwright JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvidenceError("UNSUPPORTED_FORMAT", "Playwright JSON must be an object")
    cases: list[dict[str, Any]] = []
    for suite in payload.get("suites") or []:
        root = {**suite}
        if suite.get("title") and suite.get("title") != suite.get("file"):
            root["titlePath"] = [suite["title"]]
        else:
            root["titlePath"] = []
        cases.extend(_playwright_specs(root, suite.get("file")))
    return cases


def match_junit(cases: list[dict[str, Any]], selector: dict[str, Any]) -> list[dict[str, Any]]:
    wanted_suites = list(selector.get("suites") or [])
    wanted_file = posix_relative(selector["file"]) if selector.get("file") else None
    matched = []
    for case in cases:
        if case["classname"] != selector.get("classname", ""):
            continue
        if case["name"] != selector.get("name"):
            continue
        if wanted_suites and case["suites"] != wanted_suites:
            continue
        if wanted_file is not None and case["file"] != wanted_file:
            continue
        matched.append(case)
    return matched


def match_playwright(cases: list[dict[str, Any]], selector: dict[str, Any]) -> list[dict[str, Any]]:
    wanted_file = posix_relative(selector["file"])
    wanted_titles = list(selector["titlePath"])
    matched = []
    for case in cases:
        if case["project"] != selector.get("project"):
            continue
        if case["file"] != wanted_file:
            continue
        if case["titlePath"] != wanted_titles:
            continue
        matched.append(case)
    return matched


def unique_binding(case: dict[str, Any]) -> str:
    bindings = [item.strip().lower() for item in case.get("bindings") or [] if item]
    if not bindings:
        raise EvidenceError("BINDING_MISSING", "matched case has no sourceLocatorDigest binding")
    unique = set(bindings)
    if len(unique) != 1:
        raise EvidenceError("BINDING_DUPLICATE", "matched case has conflicting locator bindings")
    digest = next(iter(unique))
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise EvidenceError("BINDING_MALFORMED", f"invalid case binding {digest!r}")
    return digest


def validate_v2(envelope: dict[str, Any], root: Path) -> None:
    validate_schema(envelope, V2_SCHEMA)
    locators = {item["sourceLocatorDigest"]: item for item in envelope["sourceLocators"]}
    if len(locators) != len(envelope["sourceLocators"]):
        raise EvidenceError("DUPLICATE_LINK", "duplicate sourceLocatorDigest")
    reports = {item["sha256"].lower(): item for item in envelope["reports"]}
    if len(reports) != len(envelope["reports"]):
        raise EvidenceError("DUPLICATE_LINK", "duplicate report sha256")

    repo = envelope["repository"]
    repo_commit = normalize_commit(repo["sourceCommit"]) if repo.get("sourceCommit") else None
    seen_links: set[tuple[str, str, str]] = set()

    for locator in envelope["sourceLocators"]:
        recomputed = source_locator_digest(locator)
        if locator["sourceLocatorDigest"] != recomputed:
            raise EvidenceError(
                "LOCATOR_DIGEST_MISMATCH",
                f"locator digest {locator['sourceLocatorDigest']} != {recomputed}",
            )
        if repo_commit and normalize_commit(locator["sourceCommit"]) != repo_commit:
            raise EvidenceError("REVISION_MISMATCH", "locator commit differs from envelope repository")
        feature_path = resolve_safe(root, locator["path"])
        if not feature_path.is_file() or feature_path.is_symlink():
            raise EvidenceError("FEATURE_NOT_FILE", f"feature path is not a file: {locator['path']}")

    for link in envelope["scenarioLinks"]:
        digest = link["sourceLocatorDigest"]
        report_sha = link["reportSha256"].lower()
        key = (digest, report_sha, json.dumps(link["testCaseSelector"], sort_keys=True))
        if key in seen_links:
            raise EvidenceError("DUPLICATE_LINK", "duplicate scenario link")
        seen_links.add(key)
        if digest not in locators:
            raise EvidenceError("DANGLING_LOCATOR", f"missing locator {digest}")
        report = reports.get(report_sha)
        if report is None:
            raise EvidenceError("DANGLING_REPORT", f"missing report {report_sha}")
        if report["status"] != "passed":
            raise EvidenceError("REPORT_NOT_PASSED", f"report {report['path']} is {report['status']}")
        if link["reportFormat"] != report.get("reportFormat"):
            raise EvidenceError("UNSUPPORTED_FORMAT", "link reportFormat does not match report")
        if report.get("reportFormat") not in {"junit-xml-v1", "playwright-json-v1"}:
            raise EvidenceError("UNSUPPORTED_FORMAT", f"unsupported reportFormat {report.get('reportFormat')}")

        report_path = resolve_safe(root, report["path"])
        require_file(report_path, report["path"])
        data = report_path.read_bytes()
        actual_sha = sha256_bytes(data)
        if actual_sha != report_sha:
            raise EvidenceError(
                "REPORT_HASH_MISMATCH",
                f"{report['path']} sha256 {actual_sha} != {report_sha}",
            )

        if report["reportFormat"] == "junit-xml-v1":
            cases = parse_junit(data)
            matched = match_junit(cases, link["testCaseSelector"])
        else:
            cases = parse_playwright(data)
            matched = match_playwright(cases, link["testCaseSelector"])
        if not matched:
            raise EvidenceError("SELECTOR_ZERO_MATCH", "selector matched no report test case")
        if len(matched) > 1:
            raise EvidenceError("SELECTOR_MULTI_MATCH", "selector matched multiple report test cases")
        case = matched[0]
        if case["outcome"] != "passed":
            raise EvidenceError("CASE_NOT_PASSED", f"matched case outcome is {case['outcome']}")
        binding = unique_binding(case)
        expected = source_locator_digest(locators[digest])
        if binding != expected:
            raise EvidenceError(
                "BINDING_MISMATCH",
                f"case binding {binding} != locator {expected}",
            )

    if envelope["evidenceSource"] == "ci" or envelope["evidencePublication"] == "published":
        attestations = envelope.get("runnerAttestations") or []
        if not attestations:
            raise EvidenceError("ATTESTATION_MISSING", "CI/published evidence requires runner attestation")
        attested_hashes = {
            (item.get("tools") or {}).get("reportSha256", "").lower()
            for item in attestations
        }
        attested_commits = {
            normalize_commit((item.get("tools") or {})["sourceCommit"])
            for item in attestations
            if (item.get("tools") or {}).get("sourceCommit")
        }
        for link in envelope["scenarioLinks"]:
            if link["reportSha256"].lower() not in attested_hashes:
                raise EvidenceError("ATTESTATION_MISMATCH", "attestation does not bind report hash")
        if repo_commit and repo_commit not in attested_commits:
            raise EvidenceError("ATTESTATION_MISMATCH", "attestation does not bind source revision")


def validate_v1(envelope: dict[str, Any]) -> None:
    validate_schema(envelope, V1_SCHEMA)


def load_envelope(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--envelope", required=True, type=Path)
    parser.add_argument("--root", type=Path, help="repository root used to resolve relative paths")
    parser.add_argument("--schema-version", type=int, choices=(1, 2))
    args = parser.parse_args(argv)
    try:
        envelope = load_envelope(args.envelope)
        version = args.schema_version or envelope.get("schemaVersion")
        if version == 1:
            validate_v1(envelope)
        elif version == 2:
            if args.root is None:
                raise EvidenceError("UNSAFE_PATH", "--root is required for v2 validation")
            validate_v2(envelope, args.root)
        else:
            raise EvidenceError("SCHEMA_INVALID", f"unsupported schemaVersion {version!r}")
    except EvidenceError as exc:
        print(json.dumps({"ok": False, "code": exc.code, "message": exc.message}, ensure_ascii=False))
        return 1
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "code": "SCHEMA_INVALID", "message": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "code": REASON_OK}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
