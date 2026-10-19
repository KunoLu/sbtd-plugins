#!/usr/bin/env python3
"""P1 knowledge ingest, evidence decision, revision set, and smoke orchestration."""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - JSON remains supported without PyYAML.
    yaml = None
try:
    import jsonschema  # type: ignore
except (
    ImportError
):  # pragma: no cover - reported when persisted contracts are validated.
    jsonschema = None


SCHEMA_VERSION = 1
PARSER_VERSION = "2.0.0"
ALLOWED_TARGETS = {"pull-request", "knowledge-base"}
ALLOWED_TRIGGERS = {
    "local",
    "pre-pr",
    "pull-request",
    "merge",
    "schedule",
    "release",
    "manual",
}
ALLOWED_PROFILES = {"developer-local", "ci", "knowledge-server"}
SMOKE_PROFILES = {"ci", "knowledge-server"}
ALLOWED_MODES = {
    "full-stack",
    "contract-backed",
    "mock-backed",
    "app-mocked",
    "smoke-only",
    "backend-only",
    "blocked",
    "not-needed",
}
TEXT_TEST_SUFFIXES = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".py",
    ".java",
    ".kt",
    ".yml",
    ".yaml",
    ".feature",
}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"Authorization\s*:\s*Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?:password|passwd|token|secret)\s*[:=]\s*[^\s]{8,}", re.IGNORECASE),
)

LANGUAGE_KEYWORDS = {
    "en": {
        "feature": ("Feature",),
        "rule": ("Rule",),
        "background": ("Background",),
        "scenario": ("Scenario",),
        "outline": ("Scenario Outline", "Scenario Template"),
        "examples": ("Examples", "Scenarios"),
        "given": ("Given",),
        "when": ("When",),
        "then": ("Then",),
        "and": ("And",),
        "but": ("But",),
    },
    "zh-CN": {
        "feature": ("功能",),
        "rule": ("规则",),
        "background": ("背景",),
        "scenario": ("场景", "剧本"),
        "outline": ("场景大纲", "剧本大纲"),
        "examples": ("例子", "示例"),
        "given": ("假如", "假设", "假定"),
        "when": ("当",),
        "then": ("那么",),
        "and": ("而且", "并且", "同时"),
        "but": ("但是",),
    },
    "ja": {
        "feature": ("フィーチャ", "機能"),
        "rule": ("ルール",),
        "background": ("背景",),
        "scenario": ("シナリオ",),
        "outline": ("シナリオアウトライン", "シナリオテンプレート"),
        "examples": ("例",),
        "given": ("前提", "もし"),
        "when": ("もし",),
        "then": ("ならば",),
        "and": ("かつ",),
        "but": ("しかし",),
    },
}
SKILL_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = SKILL_ROOT / "references"
VALIDATION_EVIDENCE_SCHEMA = (
    SKILL_ROOT.parent
    / "project-validation"
    / "references"
    / "validation-evidence.schema.json"
)


class P1Error(RuntimeError):
    pass


class ConfigurationError(P1Error):
    pass


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def write_metrics(
    output: Path,
    run_id: str,
    kind: str,
    started_ns: int,
    counters: dict[str, int],
    dimensions: dict[str, str | int | bool],
) -> dict[str, Any]:
    finished_ns = time.time_ns()
    metrics = {
        "schema_version": 1,
        "run_id": run_id,
        "kind": kind,
        "started_at": dt.datetime.fromtimestamp(
            started_ns / 1_000_000_000, tz=dt.timezone.utc
        )
        .isoformat()
        .replace("+00:00", "Z"),
        "finished_at": now_iso(),
        "duration_ms": max(0, (finished_ns - started_ns) // 1_000_000),
        "counters": counters,
        "dimensions": dimensions,
    }
    validate_schema(metrics, REFERENCE_ROOT / "metrics.schema.json", "P1 metrics")
    write_json(output / "metrics.json", metrics)
    return metrics


def load_data(path: Path | str) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise ConfigurationError(f"Configuration file does not exist: {source}")
    text = source.read_text(encoding="utf-8")
    if source.suffix.lower() == ".json":
        value = json.loads(text)
    else:
        if yaml is None:
            raise ConfigurationError(
                "YAML configuration requires PyYAML; use JSON or install PyYAML."
            )
        value = yaml.safe_load(text)
    if not isinstance(value, dict):
        raise ConfigurationError(f"Configuration root must be an object: {source}")
    return value


def validate_schema(value: Any, schema_path: Path, label: str) -> None:
    if jsonschema is None:
        raise ConfigurationError(
            "P1 contract validation requires jsonschema; install requirements.txt."
        )
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(value)
    except (OSError, json.JSONDecodeError, jsonschema.ValidationError) as error:
        raise ConfigurationError(
            f"{label} failed Schema validation: {error}"
        ) from error


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{label} must be a non-empty string")
    return value.strip()


def safe_relative(value: Any, label: str) -> str:
    path = PurePosixPath(require_string(value, label))
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationError(f"{label} must be a contained relative path")
    return path.as_posix()


def validate_product_config(product: dict[str, Any]) -> dict[str, Any]:
    if product.get("schema_version") != SCHEMA_VERSION:
        raise ConfigurationError("product schema_version must be 1")
    require_string(product.get("product_key"), "product_key")
    repositories = product.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise ConfigurationError("repositories must be a non-empty array")
    seen: set[str] = set()
    for index, repository in enumerate(repositories):
        if not isinstance(repository, dict):
            raise ConfigurationError(f"repositories[{index}] must be an object")
        key = require_string(repository.get("key"), f"repositories[{index}].key")
        if key in seen:
            raise ConfigurationError(f"duplicate repository key: {key}")
        seen.add(key)
        require_string(repository.get("remote"), f"repositories[{index}].remote")
        require_string(repository.get("role"), f"repositories[{index}].role")
        require_string(
            repository.get("target_ref"), f"repositories[{index}].target_ref"
        )
        roots = repository.get("feature_roots")
        if not isinstance(roots, list) or not roots:
            raise ConfigurationError(
                f"repositories[{index}].feature_roots must be non-empty"
            )
        repository["feature_roots"] = [
            safe_relative(root, "feature_root") for root in roots
        ]
        if "test_roots" in repository:
            if not isinstance(repository["test_roots"], list):
                raise ConfigurationError(
                    f"repositories[{index}].test_roots must be an array"
                )
            repository["test_roots"] = [
                safe_relative(root, "test_root") for root in repository["test_roots"]
            ]
        if "binding_manifests" in repository:
            if not isinstance(repository["binding_manifests"], list):
                raise ConfigurationError(
                    f"repositories[{index}].binding_manifests must be an array"
                )
            repository["binding_manifests"] = [
                safe_relative(path, "binding_manifest")
                for path in repository["binding_manifests"]
            ]
    validate_evidence_policy(product.get("evidence_policy", {}), "evidence_policy")
    for repository in repositories:
        validate_evidence_policy(
            repository.get("evidence_policy", {}),
            f"repositories.{repository['key']}.evidence_policy",
        )
    validate_smoke_config(product.get("smoke", {}), seen)
    return product


def validate_smoke_config(smoke: Any, repository_keys: set[str]) -> None:
    if smoke in (None, {}):
        return
    if not isinstance(smoke, dict):
        raise ConfigurationError("smoke must be an object")
    retry_policy = smoke.get("retry_policy", {})
    if (
        not isinstance(retry_policy, dict)
        or not isinstance(retry_policy.get("infrastructure", 0), int)
        or retry_policy.get("infrastructure", 0) < 0
    ):
        raise ConfigurationError(
            "smoke.retry_policy.infrastructure must be a non-negative integer"
        )
    command_map = smoke.get("commands", {})
    if not isinstance(command_map, dict):
        raise ConfigurationError("smoke.commands must be an object")
    for repository_key, commands in command_map.items():
        if repository_key not in repository_keys:
            raise ConfigurationError(
                f"smoke command references unknown repository: {repository_key}"
            )
        if not isinstance(commands, list):
            raise ConfigurationError(
                f"smoke.commands.{repository_key} must be an array"
            )
        seen_commands: set[str] = set()
        for index, raw in enumerate(commands):
            spec = raw if isinstance(raw, dict) else {"command": raw}
            normalize_command(spec.get("command"))
            key = str(spec.get("key", f"command-{index + 1}"))
            if key in seen_commands:
                raise ConfigurationError(
                    f"duplicate smoke command key for {repository_key}: {key}"
                )
            seen_commands.add(key)
            if spec.get("stage", "test") not in {
                "preflight",
                "prepare",
                "test",
                "cleanup",
            }:
                raise ConfigurationError(
                    f"unsupported smoke command stage: {spec.get('stage')}"
                )
            labels = spec.get("required_runner_labels", [])
            if not isinstance(labels, list) or any(
                not isinstance(label, str) or not label for label in labels
            ):
                raise ConfigurationError(
                    f"smoke command {key} has invalid required_runner_labels"
                )
            if "timeout_seconds" in spec and (
                not isinstance(spec["timeout_seconds"], int)
                or spec["timeout_seconds"] < 1
            ):
                raise ConfigurationError(
                    f"smoke command {key} timeout_seconds must be a positive integer"
                )
            if any(
                not isinstance(code, int)
                for code in spec.get("infrastructure_exit_codes", [])
            ):
                raise ConfigurationError(
                    f"smoke command {key} infrastructure_exit_codes must be integers"
                )
            command_retry = spec.get("retry_policy", {})
            if (
                not isinstance(command_retry, dict)
                or not isinstance(command_retry.get("infrastructure", 0), int)
                or command_retry.get("infrastructure", 0) < 0
            ):
                raise ConfigurationError(f"smoke command {key} retry policy is invalid")
            reports = spec.get("reports", [])
            if not isinstance(reports, list):
                raise ConfigurationError(
                    f"smoke command {key} reports must be an array"
                )
            for report in reports:
                if not isinstance(report, dict):
                    raise ConfigurationError(
                        f"smoke command {key} report must be an object"
                    )
                safe_relative(report.get("path"), "report.path")
                safe_relative(report.get("summary_md"), "report.summary_md")
                if (
                    report.get("mode", spec.get("mode", "smoke-only"))
                    not in ALLOWED_MODES
                ):
                    raise ConfigurationError(
                        f"smoke command {key} report mode is invalid"
                    )


def validate_workspace_config(
    workspace: dict[str, Any], product: dict[str, Any]
) -> dict[str, Any]:
    if workspace.get("schema_version") != SCHEMA_VERSION:
        raise ConfigurationError("workspace schema_version must be 1")
    if workspace.get("product_key") != product.get("product_key"):
        raise ConfigurationError("workspace product_key must match product registry")
    product_root = Path(
        require_string(workspace.get("product_root"), "product_root")
    ).expanduser()
    runtime_root = Path(
        require_string(workspace.get("runtime_root"), "runtime_root")
    ).expanduser()
    if not product_root.is_absolute() or not runtime_root.is_absolute():
        raise ConfigurationError("product_root and runtime_root must be absolute paths")
    paths = workspace.get("paths")
    if not isinstance(paths, dict):
        raise ConfigurationError("workspace paths must be an object")
    for repository in product["repositories"]:
        key = repository["key"]
        if key not in paths:
            if repository.get("optional", False):
                continue
            raise ConfigurationError(f"workspace path missing for repository: {key}")
        paths[key] = safe_relative(paths[key], f"paths.{key}")
    trust = workspace.get("trust")
    if isinstance(trust, dict):
        for root in trust.get("deployment_metadata_roots", []):
            if not Path(root).expanduser().is_absolute():
                raise ConfigurationError(
                    "deployment metadata trust roots must be absolute"
                )
    for key, runner in workspace.get("runners", {}).items():
        command = runner.get("command", []) if isinstance(runner, dict) else []
        joined = "\0".join(command)
        for placeholder in ("{job_manifest}", "{result_manifest}", "{artifact_dir}"):
            if placeholder not in joined:
                raise ConfigurationError(
                    f"runner {key} command must include {placeholder}"
                )
    return workspace


def validate_evidence_policy(policy: Any, label: str) -> None:
    if policy in (None, {}):
        return
    if not isinstance(policy, dict):
        raise ConfigurationError(f"{label} must be an object")
    rules = policy.get("defaults", policy)
    if not isinstance(rules, dict):
        raise ConfigurationError(f"{label}.defaults must be an object")
    for key, rule in rules.items():
        if not isinstance(rule, dict):
            raise ConfigurationError(f"{label}.{key} must be an object")
        if "required" in rule and not isinstance(rule["required"], bool):
            raise ConfigurationError(f"{label}.{key}.required must be boolean")
        targets = rule.get("targets", [])
        if not isinstance(targets, list) or any(
            target not in ALLOWED_TARGETS for target in targets
        ):
            raise ConfigurationError(
                f"{label}.{key}.targets contains an unsupported target"
            )


def load_configs(
    product_path: Path | str, workspace_path: Path | str | None = None
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    product = validate_product_config(load_data(product_path))
    validate_schema(product, REFERENCE_ROOT / "product.schema.json", "product registry")
    workspace = (
        validate_workspace_config(load_data(workspace_path), product)
        if workspace_path
        else None
    )
    if workspace is not None:
        validate_schema(
            workspace, REFERENCE_ROOT / "workspace.schema.json", "workspace mapping"
        )
    return product, workspace


def repository_by_key(product: dict[str, Any], key: str) -> dict[str, Any]:
    for repository in product["repositories"]:
        if repository["key"] == key:
            return repository
    raise ConfigurationError(f"unknown repository key: {key}")


def policy_keys(trigger: str, profile: str) -> list[str]:
    profile_key = {
        "developer-local": "developer_local",
        "ci": "ci",
        "knowledge-server": "knowledge_server",
    }[profile]
    keys = [profile_key]
    trigger_key = {"pull-request": "pull_request", "schedule": "scheduled_smoke"}.get(
        trigger
    )
    if trigger_key and trigger_key not in keys:
        keys.append(trigger_key)
    return keys


def resolve_evidence_decision(
    product: dict[str, Any],
    repository_key: str,
    trigger: str,
    execution_profile: str,
    explicit_targets: Iterable[str] = (),
    central_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_product_config(product)
    repository = repository_by_key(product, repository_key)
    if trigger not in ALLOWED_TRIGGERS:
        raise ConfigurationError(f"unsupported trigger: {trigger}")
    if execution_profile not in ALLOWED_PROFILES:
        raise ConfigurationError(f"unsupported execution profile: {execution_profile}")
    targets = set(explicit_targets)
    if not targets <= ALLOWED_TARGETS:
        raise ConfigurationError("explicit target is unsupported")
    requirements = {
        "clean_worktree": False,
        "exact_head_sha": False,
        "revision_set": False,
        "environment_alignment": False,
    }
    applied: list[dict[str, str]] = []
    required = bool(targets)
    sources = (
        ("central-policy", central_policy or {}),
        ("product-policy", product.get("evidence_policy", {})),
        ("repository-policy", repository.get("evidence_policy", {})),
    )
    for level, policy in sources:
        rules = policy.get("defaults", policy) if isinstance(policy, dict) else {}
        for key in policy_keys(trigger, execution_profile):
            rule = rules.get(key, {}) if isinstance(rules, dict) else {}
            if not isinstance(rule, dict):
                continue
            if rule.get("required"):
                required = True
                applied.append({"level": level, "rule": f"{key}.required"})
            targets.update(rule.get("targets", []))
            for config_name, decision_name in (
                ("require_clean_worktree", "clean_worktree"),
                ("require_exact_head_sha", "exact_head_sha"),
                ("require_revision_set", "revision_set"),
                ("require_environment_alignment", "environment_alignment"),
            ):
                if rule.get(config_name):
                    requirements[decision_name] = True
    if explicit_targets:
        applied.append({"level": "explicit-target", "rule": "explicit-target"})
    blocked = required and not targets
    contract = "blocked" if blocked else "required" if required else "not-required"
    ordered_targets = sorted(targets)
    if ordered_targets == ["pull-request"]:
        intent = "pull-request"
    elif ordered_targets == ["knowledge-base"]:
        intent = "knowledge-base"
    elif len(ordered_targets) == 2:
        intent = "pull-request-and-knowledge-base"
    else:
        intent = "blocked" if blocked else "not-needed"
    priority = {
        "central-policy": 0,
        "product-policy": 1,
        "repository-policy": 2,
        "explicit-target": 3,
    }
    source = (
        min(applied, key=lambda item: priority[item["level"]])
        if applied
        else {"level": "default", "rule": "not-required"}
    )
    base = {
        "schema_version": SCHEMA_VERSION,
        "policy_version": int(product.get("evidence_policy", {}).get("version", 1)),
        "product_key": product["product_key"],
        "repository_key": repository_key,
        "trigger": trigger,
        "execution_profile": execution_profile,
        "evidence_contract": contract,
        "evidence_intent": intent,
        "evidence_targets": ordered_targets,
        "decision_source": source,
        "decision_reason": "-".join((source["level"], source["rule"], contract)),
        "requirements": requirements,
        "applied_rules": applied,
    }
    digest = canonical_digest(base)
    decision = {
        **base,
        "decision_id": f"evd-decision-{product['product_key']}-{digest[-12:]}",
        "decision_digest": digest,
    }
    validate_schema(
        decision, REFERENCE_ROOT / "evidence-decision.schema.json", "evidence decision"
    )
    return decision


def run_git(
    repo: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ("git", "-C", str(repo), *args),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and completed.returncode != 0:
        raise P1Error(
            (completed.stderr or completed.stdout).strip()
            or f"git {' '.join(args)} failed"
        )
    return completed


def resolve_ref(repo_path: Path, repository: dict[str, Any], fetch: bool) -> str:
    if (
        not (repo_path / ".git").exists()
        and run_git(repo_path, "rev-parse", "--git-dir", check=False).returncode != 0
    ):
        raise P1Error(f"not a Git repository: {repo_path}")
    target_ref = repository["target_ref"]
    candidates = [target_ref]
    if fetch:
        fetched = run_git(
            repo_path,
            "fetch",
            "--no-tags",
            repository["remote"],
            target_ref,
            check=False,
        )
        if fetched.returncode == 0:
            candidates.insert(0, "FETCH_HEAD")
    if target_ref.startswith("refs/heads/"):
        candidates.append(
            "refs/remotes/origin/" + target_ref.removeprefix("refs/heads/")
        )
    for candidate in candidates:
        resolved = run_git(
            repo_path, "rev-parse", "--verify", f"{candidate}^{{commit}}", check=False
        )
        if resolved.returncode == 0 and re.fullmatch(
            r"[0-9a-fA-F]{40,64}", resolved.stdout.strip()
        ):
            return resolved.stdout.strip().lower()
    raise P1Error(f"target ref cannot be resolved without fallback: {target_ref}")


def create_revision_set(
    product: dict[str, Any], workspace: dict[str, Any], fetch: bool = True
) -> dict[str, Any]:
    root = Path(workspace["product_root"])
    entries: list[dict[str, Any]] = []
    required_failure = False
    optional_failure = False
    for repository in product["repositories"]:
        key = repository["key"]
        if key not in workspace["paths"]:
            entries.append(
                {
                    "repository_key": key,
                    "requested_ref": repository["target_ref"],
                    "status": "unavailable",
                    "error": "workspace path not configured",
                }
            )
            optional_failure = True
            continue
        repo_path = (root / workspace["paths"][key]).resolve()
        try:
            commit = resolve_ref(repo_path, repository, fetch)
            entries.append(
                {
                    "repository_key": key,
                    "requested_ref": repository["target_ref"],
                    "resolved_commit": commit,
                    "status": "resolved",
                }
            )
        except P1Error as error:
            entries.append(
                {
                    "repository_key": key,
                    "requested_ref": repository["target_ref"],
                    "status": "blocked",
                    "error": str(error),
                }
            )
            if repository.get("optional", False):
                optional_failure = True
            else:
                required_failure = True
    status = (
        "blocked" if required_failure else "partial" if optional_failure else "ready"
    )
    base = {
        "schema_version": 1,
        "product_key": product["product_key"],
        "repositories": entries,
    }
    digest = canonical_digest(base)
    revision_set = {
        **base,
        "revision_set_id": f"revset-{product['product_key']}-{digest[-12:]}",
        "created_at": now_iso(),
        "status": status,
        "digest": digest,
    }
    validate_schema(
        revision_set, REFERENCE_ROOT / "revision-set.schema.json", "revision set"
    )
    return revision_set


def git_paths(
    repo: Path, commit: str, roots: Iterable[str], suffixes: set[str] | None = None
) -> list[str]:
    completed = run_git(repo, "ls-tree", "-r", "--name-only", commit, "--", *roots)
    paths = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if suffixes is not None:
        paths = [path for path in paths if Path(path).suffix.lower() in suffixes]
    return paths


def git_text(repo: Path, commit: str, path: str) -> str:
    completed = run_git(repo, "show", f"{commit}:{path}")
    return completed.stdout


def match_heading(line: str, words: Iterable[str]) -> str | None:
    for word in sorted(words, key=len, reverse=True):
        match = re.match(rf"^\s*{re.escape(word)}\s*[:：]\s*(.+?)\s*$", line)
        if match:
            return match.group(1)
    return None


def parse_gherkin(
    text: str, source: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    language_match = re.search(r"^\s*#\s*language\s*:\s*([^\s]+)", text, re.MULTILINE)
    language = language_match.group(1) if language_match else "en"
    gaps: list[str] = []
    keywords = LANGUAGE_KEYWORDS.get(language)
    if keywords is None:
        keywords = LANGUAGE_KEYWORDS["en"]
        gaps.append(f"unsupported Gherkin language: {language}")
    features: list[dict[str, Any]] = []
    scenarios: list[dict[str, Any]] = []
    pending_tags: list[str] = []
    feature: dict[str, Any] | None = None
    rule: str | None = None
    background: dict[str, Any] | None = None
    scenario: dict[str, Any] | None = None
    current_steps: list[dict[str, Any]] | None = None
    current_step: dict[str, Any] | None = None
    current_examples: dict[str, Any] | None = None
    doc_string: dict[str, Any] | None = None
    doc_delimiter: str | None = None
    step_kinds = ("given", "when", "then", "and", "but")
    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if doc_string is not None:
            if stripped.startswith(doc_delimiter or "\0"):
                doc_string["end_line"] = number
                doc_string["content"] = "\n".join(doc_string.pop("content_lines"))
                doc_string = None
                doc_delimiter = None
            else:
                doc_string["content_lines"].append(stripped)
            continue
        if current_step is not None and (
            stripped.startswith('"""') or stripped.startswith("```")
        ):
            doc_delimiter = stripped[:3]
            media_type = stripped[3:].strip() or None
            doc_string = {
                "delimiter": doc_delimiter,
                "media_type": media_type,
                "start_line": number,
                "content_lines": [],
            }
            current_step["doc_string"] = doc_string
            continue
        if stripped.startswith("@"):
            pending_tags.extend(
                part for part in stripped.split() if part.startswith("@")
            )
            continue
        name = match_heading(raw, keywords["feature"])
        if name is not None:
            feature = {
                **source,
                "name": name,
                "language": language,
                "line": number,
                "tags": pending_tags,
                "backgrounds": [],
            }
            features.append(feature)
            pending_tags = []
            rule = None
            background = None
            scenario = None
            current_steps = None
            current_step = None
            continue
        name = match_heading(raw, keywords["rule"])
        if name is not None:
            rule = name
            pending_tags = []
            background = None
            scenario = None
            current_steps = None
            current_step = None
            continue
        name = match_heading(raw, keywords["background"])
        if name is not None:
            if feature is None:
                gaps.append(f"background before Feature at line {number}")
                continue
            background = {
                "name": name,
                "rule": rule,
                "line": number,
                "tags": pending_tags,
                "steps": [],
            }
            feature["backgrounds"].append(background)
            pending_tags = []
            scenario = None
            current_steps = background["steps"]
            current_step = None
            current_examples = None
            continue
        outline = match_heading(raw, keywords["outline"])
        name = (
            outline if outline is not None else match_heading(raw, keywords["scenario"])
        )
        if name is not None:
            if feature is None:
                gaps.append(f"scenario before Feature at line {number}")
                continue
            scenario = {
                **source,
                "feature": feature["name"],
                "rule": rule,
                "name": name,
                "kind": "Scenario Outline" if outline is not None else "Scenario",
                "language": language,
                "line": number,
                "tags": pending_tags,
                "steps": [],
                "examples": [],
            }
            matching_backgrounds = [
                item for item in feature["backgrounds"] if item.get("rule") == rule
            ]
            if not matching_backgrounds and rule is not None:
                matching_backgrounds = [
                    item for item in feature["backgrounds"] if item.get("rule") is None
                ]
            scenario["background"] = (
                matching_backgrounds[-1]["name"] if matching_backgrounds else None
            )
            scenarios.append(scenario)
            pending_tags = []
            background = None
            current_steps = scenario["steps"]
            current_step = None
            current_examples = None
            continue
        examples_name = match_heading(raw, keywords["examples"])
        if examples_name is not None and scenario is not None:
            current_examples = {
                "name": examples_name,
                "line": number,
                "tags": pending_tags,
                "rows": [],
            }
            scenario["examples"].append(current_examples)
            pending_tags = []
            current_step = None
            continue
        if (
            current_examples is not None
            and stripped.startswith("|")
            and stripped.endswith("|")
        ):
            current_examples["rows"].append(
                [cell.strip() for cell in stripped.strip("|").split("|")]
            )
            continue
        if (
            current_step is not None
            and stripped.startswith("|")
            and stripped.endswith("|")
        ):
            current_step.setdefault("data_table", []).append(
                [cell.strip() for cell in stripped.strip("|").split("|")]
            )
            continue
        if current_steps is not None:
            for kind in step_kinds:
                for word in keywords[kind]:
                    match = re.match(rf"^\s*{re.escape(word)}\s+(.+?)\s*$", raw)
                    if match:
                        current_examples = None
                        current_step = {
                            "keyword": word,
                            "kind": kind,
                            "text": match.group(1),
                            "line": number,
                        }
                        current_steps.append(current_step)
                        break
                else:
                    continue
                break
    if doc_string is not None:
        gaps.append(f"unterminated doc string at line {doc_string['start_line']}")
        doc_string["content"] = "\n".join(doc_string.pop("content_lines"))
    for item in scenarios:
        rows = [example["rows"] for example in item["examples"]]
        item["examples_fingerprint"] = canonical_digest(rows) if rows else None
    return features, scenarios, gaps


def locator_for(scenario: dict[str, Any]) -> dict[str, Any]:
    return {
        "repository_key": scenario["repository_key"],
        "source_ref": scenario["source_ref"],
        "source_commit": scenario["source_commit"],
        "path": scenario["path"],
        "feature": scenario["feature"],
        "rule": scenario.get("rule"),
        "scenario": scenario["name"],
        "examples_fingerprint": scenario.get("examples_fingerprint"),
        "line": scenario["line"],
    }


def normalized_behavior(scenario: dict[str, Any]) -> str:
    text = " ".join([scenario["name"], *(step["text"] for step in scenario["steps"])])
    return re.sub(r"[\W_]+", "", text.casefold())


def build_conflict_candidates(
    scenarios: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    overlaps: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for index, left in enumerate(scenarios):
        for right in scenarios[index + 1 :]:
            if left["repository_key"] == right["repository_key"]:
                continue
            similarity = difflib.SequenceMatcher(
                None, normalized_behavior(left), normalized_behavior(right)
            ).ratio()
            same_name = re.sub(r"\W+", "", left["name"].casefold()) == re.sub(
                r"\W+", "", right["name"].casefold()
            )
            evidence = {
                "algorithm": "normalized-sequence-v1",
                "confidence": round(similarity, 4),
            }
            sources = [locator_for(left), locator_for(right)]
            if similarity >= 0.82 or same_name:
                overlaps.append(
                    {
                        "kind": "semantic-overlap-candidate",
                        "sources": sources,
                        "evidence": evidence,
                    }
                )
            left_then = [
                step["text"] for step in left["steps"] if step["kind"] == "then"
            ]
            right_then = [
                step["text"] for step in right["steps"] if step["kind"] == "then"
            ]
            if same_name and left_then != right_then:
                conflicts.append(
                    {
                        "kind": "expected-outcome-conflict-candidate",
                        "sources": sources,
                        "evidence": {
                            **evidence,
                            "left_then": left_then,
                            "right_then": right_then,
                        },
                    }
                )
    return overlaps, conflicts


def manifest_nodes(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from manifest_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from manifest_nodes(child)


def scan_bindings(
    repo: Path, commit: str, repository: dict[str, Any], scenarios: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    roots = repository.get("test_roots", [])
    bindings: list[dict[str, Any]] = []
    if roots:
        for path in git_paths(repo, commit, roots, TEXT_TEST_SUFFIXES):
            content = git_text(repo, commit, path)
            for scenario in scenarios:
                if (
                    scenario["repository_key"] == repository["key"]
                    and scenario["name"] in content
                ):
                    bindings.append(
                        {
                            "source": locator_for(scenario),
                            "test_path": path,
                            "method": "scenario-name-static-scan",
                        }
                    )
    for manifest_path in repository.get("binding_manifests", []):
        try:
            content = git_text(repo, commit, manifest_path)
            if manifest_path.endswith(".json"):
                manifest = json.loads(content)
            else:
                if yaml is None:
                    raise ConfigurationError("YAML binding manifest requires PyYAML")
                manifest = yaml.safe_load(content)
        except (
            P1Error,
            json.JSONDecodeError,
            yaml.YAMLError if yaml is not None else ValueError,
        ) as error:
            raise P1Error(
                f"binding manifest cannot be read: {manifest_path}: {error}"
            ) from error
        for node in manifest_nodes(manifest):
            scenario_name = next(
                (
                    node.get(key)
                    for key in ("scenario", "scenarioName", "bddScenario")
                    if node.get(key)
                ),
                None,
            )
            feature_path = next(
                (
                    node.get(key)
                    for key in ("featurePath", "feature_path", "sourceFeature")
                    if node.get(key)
                ),
                None,
            )
            test_path = next(
                (
                    node.get(key)
                    for key in ("testPath", "test_path", "path")
                    if node.get(key)
                ),
                None,
            )
            if not isinstance(scenario_name, str) or not isinstance(test_path, str):
                continue
            for scenario in scenarios:
                if scenario["name"] != scenario_name:
                    continue
                if isinstance(feature_path, str) and feature_path != scenario["path"]:
                    continue
                bindings.append(
                    {
                        "source": locator_for(scenario),
                        "test_path": test_path,
                        "manifest_path": manifest_path,
                        "method": "manifest",
                    }
                )
    unique: dict[str, dict[str, Any]] = {}
    for binding in bindings:
        key = canonical_digest(binding)
        unique[key] = binding
    return list(unique.values())


def idempotency_key(kind: str, value: dict[str, Any]) -> str:
    return canonical_digest({"kind": kind, **value})


def idempotency_record(runtime: Path, kind: str, key: str) -> Path:
    return runtime / "idempotency" / kind / f"{key.removeprefix('sha256:')}.json"


def load_idempotent_result(runtime: Path, kind: str, key: str) -> dict[str, Any] | None:
    record_path = idempotency_record(runtime, kind, key)
    if not record_path.is_file():
        return None
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
        summary_path = Path(record["summary_path"])
        result = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, KeyError, json.JSONDecodeError):
        return None
    if result.get("idempotency_key") != key:
        return None
    return {
        **result,
        "reused": True,
        "original_run_id": result.get("run_id"),
        "artifact_root": str(summary_path.parent),
    }


def store_idempotent_result(
    runtime: Path, kind: str, key: str, summary_path: Path
) -> None:
    write_json(
        idempotency_record(runtime, kind, key),
        {
            "schema_version": 1,
            "kind": kind,
            "idempotency_key": key,
            "summary_path": str(summary_path.resolve()),
            "recorded_at": now_iso(),
        },
    )


def run_ingest(
    product_path: Path | str,
    workspace_path: Path | str,
    output_dir: Path | str,
    fetch: bool = True,
    run_id: str | None = None,
) -> dict[str, Any]:
    started_ns = time.time_ns()
    product, workspace = load_configs(product_path, workspace_path)
    assert workspace is not None
    runtime = Path(workspace["runtime_root"])
    revision_set = create_revision_set(product, workspace, fetch=fetch)
    ingest_key = idempotency_key(
        "ingest",
        {
            "product_key": product["product_key"],
            "revision_set_id": revision_set["revision_set_id"],
            "parser_version": PARSER_VERSION,
        },
    )
    reused = load_idempotent_result(runtime, "ingest", ingest_key)
    if reused is not None:
        return reused
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    existing_summary = output / "ingest-summary.json"
    if existing_summary.is_file():
        existing = json.loads(existing_summary.read_text(encoding="utf-8"))
        if existing.get("idempotency_key") == ingest_key:
            return existing
        raise P1Error("ingest output already contains a different logical run")
    write_json(output / "revision-set.json", revision_set)
    all_features: list[dict[str, Any]] = []
    all_scenarios: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    gaps: list[dict[str, str]] = []
    repository_results: list[dict[str, Any]] = []
    root = Path(workspace["product_root"])
    revisions = {
        entry["repository_key"]: entry for entry in revision_set["repositories"]
    }
    for repository in product["repositories"]:
        key = repository["key"]
        revision = revisions[key]
        if revision["status"] != "resolved":
            repository_results.append(
                {
                    "repository_key": key,
                    "status": "blocked",
                    "error": revision.get("error"),
                }
            )
            continue
        repo = (root / workspace["paths"][key]).resolve()
        commit = revision["resolved_commit"]
        feature_paths = git_paths(
            repo, commit, repository["feature_roots"], {".feature"}
        )
        repo_scenarios: list[dict[str, Any]] = []
        for path in feature_paths:
            source = {
                "repository_key": key,
                "source_ref": repository["target_ref"],
                "source_commit": commit,
                "path": path,
            }
            features, scenarios, parser_gaps = parse_gherkin(
                git_text(repo, commit, path), source
            )
            all_features.extend(features)
            all_scenarios.extend(scenarios)
            repo_scenarios.extend(scenarios)
            gaps.extend(
                {"repository_key": key, "path": path, "message": gap}
                for gap in parser_gaps
            )
        bindings.extend(scan_bindings(repo, commit, repository, repo_scenarios))
        repository_results.append(
            {
                "repository_key": key,
                "requested_ref": repository["target_ref"],
                "resolved_commit": commit,
                "status": "run",
                "feature_count": len(feature_paths),
                "scenario_count": len(repo_scenarios),
            }
        )
    overlaps, conflicts = build_conflict_candidates(all_scenarios)
    locators = [locator_for(scenario) for scenario in all_scenarios]
    write_json(output / "features.json", all_features)
    write_json(output / "scenarios.json", all_scenarios)
    write_json(output / "source-locators.json", locators)
    write_json(output / "bindings.json", bindings)
    write_json(output / "overlaps.json", overlaps)
    write_json(output / "conflicts.json", conflicts)
    status = (
        "blocked"
        if revision_set["status"] == "blocked"
        else "partial"
        if revision_set["status"] == "partial" or gaps
        else "run"
    )
    summary = {
        "schema_version": 1,
        "run_id": run_id or f"ingest-{ingest_key[-12:]}",
        "product_key": product["product_key"],
        "parser_version": PARSER_VERSION,
        "idempotency_key": ingest_key,
        "reused": False,
        "output_dir": str(output.resolve()),
        "status": status,
        "mutation": "none",
        "revision_set_id": revision_set["revision_set_id"],
        "repositories": repository_results,
        "feature_count": len(all_features),
        "scenario_count": len(all_scenarios),
        "binding_count": len(bindings),
        "overlap_count": len(overlaps),
        "conflict_count": len(conflicts),
        "parser_gaps": gaps,
    }
    write_json(output / "ingest-summary.json", summary)
    write_metrics(
        output,
        summary["run_id"],
        "ingest",
        started_ns,
        {
            "repositories": len(repository_results),
            "features": len(all_features),
            "scenarios": len(all_scenarios),
            "bindings": len(bindings),
            "overlaps": len(overlaps),
            "conflicts": len(conflicts),
            "parser_gaps": len(gaps),
        },
        {
            "product_key": product["product_key"],
            "revision_set_id": revision_set["revision_set_id"],
            "parser_version": PARSER_VERSION,
        },
    )
    store_idempotent_result(
        runtime, "ingest", ingest_key, output / "ingest-summary.json"
    )
    return summary


def normalize_command(value: Any) -> list[str]:
    if (
        isinstance(value, list)
        and value
        and all(isinstance(item, str) and item for item in value)
    ):
        return value
    if isinstance(value, str) and value.strip():
        return shlex.split(value)
    raise ConfigurationError(
        "smoke command must be a non-empty argv array or shell-free command string"
    )


def copy_report(source: Path, destination: Path) -> Path:
    if not source.is_file() or source.is_symlink():
        raise P1Error(f"report is missing or unsafe: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def resolve_report_pair(
    worktree: Path, report_spec: dict[str, Any], not_before_ns: int
) -> tuple[Path, Path]:
    report_pattern = safe_relative(report_spec.get("path"), "report.path")
    summary_pattern = safe_relative(report_spec.get("summary_md"), "report.summary_md")
    report_matches = [
        path.resolve()
        for path in worktree.glob(report_pattern)
        if path.is_file()
        and not path.is_symlink()
        and path.stat().st_mtime_ns >= not_before_ns
    ]
    summary_matches = [
        path.resolve()
        for path in worktree.glob(summary_pattern)
        if path.is_file()
        and not path.is_symlink()
        and path.stat().st_mtime_ns >= not_before_ns
    ]
    if not report_matches:
        raise P1Error(
            f"report was not produced by the current command: {report_pattern}"
        )
    report_source = max(report_matches, key=lambda path: path.stat().st_mtime_ns)
    same_stem = [path for path in summary_matches if path.stem == report_source.stem]
    if not same_stem:
        raise P1Error(
            f"same-stem Chinese Markdown summary is missing for: {report_source.name}"
        )
    summary_source = max(same_stem, key=lambda path: path.stat().st_mtime_ns)
    if (
        worktree.resolve() not in report_source.parents
        or worktree.resolve() not in summary_source.parents
    ):
        raise P1Error("report path escaped isolated worktree")
    summary_text = summary_source.read_text(encoding="utf-8", errors="ignore")
    if re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", summary_text) is None:
        raise P1Error(
            f"same-stem Markdown summary is not Chinese: {summary_source.name}"
        )
    return report_source, summary_source


def artifact_record(path: Path, output: Path, kind: str) -> dict[str, Any]:
    stat = path.stat()
    return {
        "kind": kind,
        "path": path.relative_to(output).as_posix(),
        "sha256": file_sha256(path),
        "size": stat.st_size,
        "modified_at": dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
    }


def write_checksums(
    output: Path,
    repository_key: str,
    artifacts: list[dict[str, Any]],
    manifest_path: Path,
) -> Path:
    checksums_path = output / f"checksums-{repository_key}.sha256"
    lines = [f"{item['sha256']}  {item['path']}" for item in artifacts]
    lines.append(
        f"{file_sha256(manifest_path)}  {manifest_path.relative_to(output).as_posix()}"
    )
    checksums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksums_path


def contains_secret(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")[:2_000_000]
    except OSError:
        return True
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def resolve_environment_alignment(
    revision_set: dict[str, Any],
    deployment_manifest_path: Path | str | None,
    fallback: str,
    workspace: dict[str, Any],
) -> dict[str, Any]:
    if deployment_manifest_path is None:
        return {
            "status": fallback,
            "reason": "deployment-manifest-not-provided",
            "runners": {},
        }
    manifest = load_data(deployment_manifest_path)
    validate_schema(
        manifest,
        REFERENCE_ROOT / "deployment-manifest.schema.json",
        "deployment manifest",
    )
    deployed = manifest["repositories"]
    expected = {
        item["repository_key"]: item["resolved_commit"]
        for item in revision_set["repositories"]
        if item["status"] == "resolved"
    }
    if not expected or not all(
        deployed.get(key) == commit for key, commit in expected.items()
    ):
        return {
            "status": "mismatch",
            "reason": "deployment-revision-mismatch",
            "runners": manifest["runners"],
        }
    trust = workspace.get("trust")
    if not isinstance(trust, dict):
        return {
            "status": "unverified",
            "reason": "workspace-trust-not-configured",
            "runners": manifest["runners"],
        }
    source = Path(deployment_manifest_path).expanduser().resolve()
    trusted_roots = [
        Path(root).expanduser().resolve()
        for root in trust.get("deployment_metadata_roots", [])
    ]
    if not any(source == root or root in source.parents for root in trusted_roots):
        return {
            "status": "unverified",
            "reason": "deployment-manifest-outside-trusted-root",
            "runners": manifest["runners"],
        }
    attestation = manifest["attestation"]
    if attestation["issuer"] not in set(trust.get("allowed_issuers", [])):
        return {
            "status": "unverified",
            "reason": "deployment-issuer-not-allowed",
            "runners": manifest["runners"],
        }
    unsigned = json.loads(json.dumps(manifest))
    unsigned["attestation"].pop("manifest_digest", None)
    if canonical_digest(unsigned) != attestation["manifest_digest"]:
        return {
            "status": "unverified",
            "reason": "deployment-manifest-digest-invalid",
            "runners": manifest["runners"],
        }
    return {
        "status": "verified",
        "reason": "trusted-deployment-manifest",
        "manifest_digest": attestation["manifest_digest"],
        "issuer": attestation["issuer"],
        "runners": manifest["runners"],
    }


def runner_attestation_matches(
    expected: dict[str, Any], actual: dict[str, Any]
) -> bool:
    return (
        expected.get("id") == actual.get("id")
        and expected.get("version") == actual.get("version")
        and expected.get("image_digest") == actual.get("image_digest")
        and set(expected.get("labels", [])) == set(actual.get("labels", []))
        and expected.get("tools", {}) == actual.get("tools", {})
    )


def render_adapter_command(
    command: list[str], replacements: dict[str, Path]
) -> list[str]:
    rendered: list[str] = []
    for item in command:
        value = item
        for token, path in replacements.items():
            value = value.replace("{" + token + "}", str(path))
        rendered.append(value)
    return rendered


def execute_local_once(
    argv: list[str],
    worktree: Path,
    report_specs: list[dict[str, Any]],
    runner: dict[str, Any],
    timeout_seconds: int | None,
) -> dict[str, Any]:
    started_ns = time.time_ns()
    try:
        completed = subprocess.run(
            argv,
            cwd=worktree,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            "status": "blocked",
            "failure_class": "infrastructure",
            "error": str(error),
            "stdout": "",
            "stderr": str(error),
            "report_root": worktree,
            "report_specs": report_specs,
            "started_ns": started_ns,
            "runner": runner,
            "queue_latency_ms": 0,
        }
    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "failure_class": "none" if completed.returncode == 0 else "assertion",
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "report_root": worktree,
        "report_specs": report_specs,
        "started_ns": started_ns,
        "runner": runner,
        "queue_latency_ms": 0,
    }


def execute_command_runner_once(
    runner_key: str,
    runner_config: dict[str, Any],
    spec: dict[str, Any],
    argv: list[str],
    output: Path,
    product: dict[str, Any],
    repository: dict[str, Any],
    revision: dict[str, Any],
    revision_set: dict[str, Any],
    run_id: str,
    suite_key: str,
    run_attempt: int,
    execution_attempt: int,
    timeout_seconds: int | None,
) -> dict[str, Any]:
    job_root = (
        output
        / "jobs"
        / repository["key"]
        / str(spec["key"])
        / f"attempt-{execution_attempt}"
    )
    artifact_dir = job_root / "artifacts"
    result_path = job_root / "result.json"
    job_path = job_root / "job.json"
    job = {
        "schema_version": 1,
        "run_id": run_id,
        "suite_key": suite_key,
        "attempt": run_attempt,
        "command_key": str(spec["key"]),
        "repository": {
            "key": repository["key"],
            "remote": repository["remote"],
            "requested_ref": repository["target_ref"],
            "resolved_commit": revision["resolved_commit"],
        },
        "revision_set": revision_set,
        "command": argv,
        "required_runner_labels": spec.get("required_runner_labels", []),
        "artifact_dir": str(artifact_dir.resolve()),
    }
    validate_schema(job, REFERENCE_ROOT / "runner-job.schema.json", "runner job")
    write_json(job_path, job)
    adapter_argv = render_adapter_command(
        runner_config["command"],
        {
            "job_manifest": job_path.resolve(),
            "result_manifest": result_path.resolve(),
            "artifact_dir": artifact_dir.resolve(),
        },
    )
    started_ns = time.time_ns()
    try:
        completed = subprocess.run(
            adapter_argv,
            cwd=job_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            "status": "blocked",
            "failure_class": "infrastructure",
            "error": str(error),
            "stdout": "",
            "stderr": str(error),
            "report_root": job_root,
            "report_specs": [],
            "started_ns": started_ns,
            "runner": None,
            "queue_latency_ms": 0,
        }
    if completed.returncode != 0 or not result_path.is_file():
        return {
            "status": "blocked",
            "failure_class": "infrastructure",
            "exit_code": completed.returncode,
            "error": "runner adapter did not produce a valid result manifest",
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "report_root": job_root,
            "report_specs": [],
            "started_ns": started_ns,
            "runner": None,
            "queue_latency_ms": 0,
        }
    result = load_data(result_path)
    validate_schema(
        result, REFERENCE_ROOT / "runner-result.schema.json", "runner result"
    )
    if not set(spec.get("required_runner_labels", [])) <= set(
        result["runner"]["labels"]
    ):
        return {
            "status": "blocked",
            "failure_class": "infrastructure",
            "error": "runner result does not attest required labels",
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "report_root": job_root,
            "report_specs": [],
            "started_ns": started_ns,
            "runner": result["runner"],
            "queue_latency_ms": result.get("queue_latency_ms", 0),
        }
    return {
        **result,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "report_root": job_root,
        "report_specs": result["reports"],
        "started_ns": started_ns,
        "runner_key": runner_key,
    }


def add_worktree(repo: Path, destination: Path, commit: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    completed = run_git(
        repo, "worktree", "add", "--detach", str(destination), commit, check=False
    )
    if completed.returncode != 0:
        raise P1Error((completed.stderr or completed.stdout).strip())


def remove_worktree(repo: Path, destination: Path) -> None:
    run_git(repo, "worktree", "remove", "--force", str(destination), check=False)
    if destination.exists():
        shutil.rmtree(destination, ignore_errors=True)


def process_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def acquire_run_lock(
    lock: Path,
    worktree_root: Path,
    product: dict[str, Any],
    workspace: dict[str, Any],
) -> None:
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock.mkdir()
    except FileExistsError as error:
        owner_path = lock / "owner.json"
        try:
            owner = json.loads(owner_path.read_text(encoding="utf-8"))
            owner_pid = int(owner["pid"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise P1Error(
                f"run lock exists without verifiable owner: {lock.name}"
            ) from error
        if process_is_alive(owner_pid):
            raise P1Error(
                f"run is already locked by live process {owner_pid}: {lock.name}"
            ) from error
        root = Path(workspace["product_root"])
        for repository in product["repositories"]:
            key = repository["key"]
            if key not in workspace["paths"]:
                continue
            source_repo = (root / workspace["paths"][key]).resolve()
            remove_worktree(source_repo, worktree_root / key)
        shutil.rmtree(worktree_root, ignore_errors=True)
        shutil.rmtree(lock, ignore_errors=True)
        lock.mkdir()
    write_json(
        lock / "owner.json",
        {"schema_version": 1, "pid": os.getpid(), "created_at": now_iso()},
    )


def run_smoke(
    product_path: Path | str,
    workspace_path: Path | str,
    output_dir: Path | str,
    trigger: str,
    execution_profile: str = "knowledge-server",
    fetch: bool = True,
    run_id: str | None = None,
    explicit_targets: Iterable[str] = (),
    environment_alignment: str = "unverified",
    central_policy: dict[str, Any] | None = None,
    deployment_manifest_path: Path | str | None = None,
    runner_labels: Iterable[str] = (),
    suite_key: str = "smoke",
    attempt: int = 1,
) -> dict[str, Any]:
    started_ns = time.time_ns()
    product, workspace = load_configs(product_path, workspace_path)
    assert workspace is not None
    if execution_profile not in SMOKE_PROFILES:
        raise ConfigurationError(
            "smoke execution profile must be ci or knowledge-server"
        )
    if environment_alignment not in {
        "verified",
        "unverified",
        "mismatch",
        "not-needed",
    }:
        raise ConfigurationError("unsupported environment alignment")
    if attempt < 1:
        raise ConfigurationError("smoke attempt must be at least 1")
    suite_key = require_string(suite_key, "suite_key")
    revision_set = create_revision_set(product, workspace, fetch=fetch)
    smoke_key = idempotency_key(
        "smoke",
        {
            "revision_set_id": revision_set["revision_set_id"],
            "suite_key": suite_key,
            "environment_profile": execution_profile,
            "attempt": attempt,
        },
    )
    runtime = Path(workspace["runtime_root"])
    reused = load_idempotent_result(runtime, "smoke", smoke_key)
    if reused is not None:
        return reused
    run_id = run_id or f"smoke-{product['product_key']}-{smoke_key[-12:]}-a{attempt}"
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    existing_summary = output / "smoke-summary.json"
    if existing_summary.is_file():
        existing = json.loads(existing_summary.read_text(encoding="utf-8"))
        if existing.get("idempotency_key") == smoke_key:
            return existing
        raise P1Error("smoke output already contains a different logical run")
    environment_details = resolve_environment_alignment(
        revision_set, deployment_manifest_path, environment_alignment, workspace
    )
    write_json(output / "revision-set.json", revision_set)
    if revision_set["status"] == "blocked":
        result = {
            "schema_version": 1,
            "run_id": run_id,
            "suite_key": suite_key,
            "attempt": attempt,
            "idempotency_key": smoke_key,
            "reused": False,
            "output_dir": str(output.resolve()),
            "status": "blocked",
            "revision_set": revision_set,
            "runs": [],
        }
        write_json(output / "smoke-summary.json", result)
        write_metrics(
            output,
            run_id,
            "smoke",
            started_ns,
            {"repositories": 0, "commands": 0, "reports": 0, "blocked": 1},
            {
                "product_key": product["product_key"],
                "revision_set_id": revision_set["revision_set_id"],
                "suite_key": suite_key,
                "environment_profile": execution_profile,
                "attempt": attempt,
            },
        )
        store_idempotent_result(
            runtime, "smoke", smoke_key, output / "smoke-summary.json"
        )
        return result
    root = Path(workspace["product_root"])
    worktree_root = runtime / "worktrees" / run_id
    lock = runtime / "locks" / run_id
    acquire_run_lock(lock, worktree_root, product, workspace)
    revision_map = {
        item["repository_key"]: item for item in revision_set["repositories"]
    }
    command_map = product.get("smoke", {}).get("commands", {})
    results: list[dict[str, Any]] = []
    overall = "passed"
    try:
        for repository_key, command_values in command_map.items():
            if not isinstance(command_values, list):
                raise ConfigurationError(
                    f"smoke.commands.{repository_key} must be an array"
                )
            repository = repository_by_key(product, repository_key)
            revision = revision_map.get(repository_key, {})
            if revision.get("status") != "resolved":
                results.append(
                    {
                        "repository_key": repository_key,
                        "status": "blocked",
                        "reason": "revision unavailable",
                    }
                )
                overall = "blocked"
                continue
            source_repo = (root / workspace["paths"][repository_key]).resolve()
            worktree = worktree_root / repository_key
            add_worktree(source_repo, worktree, revision["resolved_commit"])
            reports: list[dict[str, Any]] = []
            artifacts: list[dict[str, Any]] = []
            command_results: list[dict[str, Any]] = []
            repository_errors: list[str] = []
            runner_attestations: dict[str, dict[str, Any]] = {}
            repository_environment_alignment = environment_details["status"]
            decision = resolve_evidence_decision(
                product,
                repository_key,
                trigger,
                execution_profile,
                explicit_targets,
                central_policy,
            )
            try:
                stage_priority = {"preflight": 0, "prepare": 1, "test": 2, "cleanup": 3}
                staged_commands: list[tuple[int, dict[str, Any]]] = []
                for index, raw_command in enumerate(command_values):
                    candidate = (
                        raw_command
                        if isinstance(raw_command, dict)
                        else {"command": raw_command}
                    )
                    stage = candidate.get("stage", "test")
                    if stage not in stage_priority:
                        raise ConfigurationError(
                            f"unsupported smoke command stage: {stage}"
                        )
                    staged_commands.append(
                        (
                            index,
                            {
                                **candidate,
                                "stage": stage,
                                "key": candidate.get("key", f"command-{index + 1}"),
                            },
                        )
                    )
                staged_commands.sort(
                    key=lambda item: (stage_priority[item[1]["stage"]], item[0])
                )
                pipeline_blocked = False
                for index, spec in staged_commands:
                    key = spec["key"]
                    stage = spec["stage"]
                    argv = normalize_command(spec.get("command"))
                    runner_key = spec.get("runner", "local")
                    if pipeline_blocked and stage != "cleanup":
                        command_results.append(
                            {
                                "key": key,
                                "stage": stage,
                                "argv": argv,
                                "runner": runner_key,
                                "status": "skipped",
                                "reason": "earlier preflight or prepare stage was blocked",
                                "attempts": [],
                                "queue_latency_ms": 0,
                            }
                        )
                        continue
                    if runner_key == "local":
                        local_runner = workspace.get("local_runner") or {
                            "id": "local-unattested",
                            "version": "unverified",
                            "image_digest": "sha256:" + "0" * 64,
                            "labels": sorted(set(runner_labels)),
                            "tools": {},
                        }
                        available_labels = set(local_runner.get("labels", [])) | set(
                            runner_labels
                        )
                        runner_config = None
                    else:
                        runner_config = workspace.get("runners", {}).get(runner_key)
                        if not isinstance(runner_config, dict):
                            command_results.append(
                                {
                                    "key": key,
                                    "stage": stage,
                                    "argv": argv,
                                    "runner": runner_key,
                                    "status": "blocked",
                                    "error": f"runner adapter is not configured: {runner_key}",
                                }
                            )
                            repository_errors.append(
                                f"{key}: runner adapter is not configured: {runner_key}"
                            )
                            overall = "blocked"
                            if stage in {"preflight", "prepare"}:
                                pipeline_blocked = True
                            continue
                        available_labels = set(runner_config.get("labels", []))
                    missing_labels = sorted(
                        set(spec.get("required_runner_labels", [])) - available_labels
                    )
                    if missing_labels:
                        command_results.append(
                            {
                                "key": key,
                                "stage": stage,
                                "argv": argv,
                                "runner": runner_key,
                                "status": "blocked",
                                "error": f"missing runner labels: {', '.join(missing_labels)}",
                            }
                        )
                        repository_errors.append(
                            f"{key}: missing runner labels: {', '.join(missing_labels)}"
                        )
                        overall = "blocked"
                        if stage in {"preflight", "prepare"}:
                            pipeline_blocked = True
                        continue
                    log_dir = output / "logs" / repository_key
                    log_dir.mkdir(parents=True, exist_ok=True)
                    retry_policy = product.get("smoke", {}).get("retry_policy", {})
                    retry_policy = {**retry_policy, **spec.get("retry_policy", {})}
                    infrastructure_retries = int(retry_policy.get("infrastructure", 0))
                    infrastructure_exit_codes = set(
                        spec.get("infrastructure_exit_codes", [])
                    )
                    attempts: list[dict[str, Any]] = []
                    command_status = "blocked"
                    execution: dict[str, Any] = {}
                    for execution_attempt in range(1, infrastructure_retries + 2):
                        started_at = now_iso()
                        if runner_key == "local":
                            execution = execute_local_once(
                                argv,
                                worktree,
                                spec.get("reports", []),
                                local_runner,
                                spec.get("timeout_seconds"),
                            )
                            if execution.get("exit_code") in infrastructure_exit_codes:
                                execution["failure_class"] = "infrastructure"
                                execution["status"] = "blocked"
                        else:
                            execution = execute_command_runner_once(
                                runner_key,
                                runner_config,
                                spec,
                                argv,
                                output,
                                product,
                                repository,
                                revision,
                                revision_set,
                                run_id,
                                suite_key,
                                attempt,
                                execution_attempt,
                                spec.get("timeout_seconds"),
                            )
                        failure_class = execution["failure_class"]
                        command_status = execution["status"]
                        attempt_result = {
                            "attempt": execution_attempt,
                            "started_at": started_at,
                            "finished_at": now_iso(),
                            "status": command_status,
                            "failure_class": failure_class,
                        }
                        if "exit_code" in execution:
                            attempt_result["exit_code"] = execution["exit_code"]
                        if execution.get("error"):
                            attempt_result["error"] = execution["error"]
                        (
                            log_dir / f"{key}.attempt-{execution_attempt}.stdout.txt"
                        ).write_text(execution.get("stdout", ""), encoding="utf-8")
                        (
                            log_dir / f"{key}.attempt-{execution_attempt}.stderr.txt"
                        ).write_text(execution.get("stderr", ""), encoding="utf-8")
                        attempts.append(attempt_result)
                        if (
                            failure_class != "infrastructure"
                            or execution_attempt > infrastructure_retries
                        ):
                            break
                    command_results.append(
                        {
                            "key": key,
                            "stage": stage,
                            "argv": argv,
                            "runner": runner_key,
                            "status": command_status,
                            "attempts": attempts,
                            "queue_latency_ms": execution.get("queue_latency_ms", 0),
                        }
                    )
                    actual_runner = execution.get("runner")
                    if isinstance(actual_runner, dict):
                        runner_attestations[canonical_digest(actual_runner)] = (
                            actual_runner
                        )
                        if environment_details["status"] == "verified":
                            expected_runner = environment_details["runners"].get(
                                runner_key
                            )
                            if expected_runner is None:
                                repository_environment_alignment = "unverified"
                            elif not runner_attestation_matches(
                                expected_runner, actual_runner
                            ):
                                repository_environment_alignment = "mismatch"
                    if command_status == "blocked":
                        overall = "blocked"
                    elif command_status == "failed" and overall != "blocked":
                        overall = "failed"
                    if stage in {"preflight", "prepare"} and command_status != "passed":
                        pipeline_blocked = True
                    for report_spec in execution.get("report_specs", []):
                        try:
                            report_source, summary_source = resolve_report_pair(
                                execution["report_root"],
                                report_spec,
                                execution["started_ns"],
                            )
                            target_dir = output / "reports" / repository_key / str(key)
                            report_target = copy_report(
                                report_source, target_dir / report_source.name
                            )
                            summary_target = copy_report(
                                summary_source, target_dir / summary_source.name
                            )
                            if contains_secret(report_target) or contains_secret(
                                summary_target
                            ):
                                report_target.unlink(missing_ok=True)
                                summary_target.unlink(missing_ok=True)
                                raise P1Error(
                                    "report pair failed sensitive information scan"
                                )
                            artifacts.extend(
                                (
                                    artifact_record(
                                        report_target, output, "native-report"
                                    ),
                                    artifact_record(
                                        summary_target, output, "markdown-summary"
                                    ),
                                )
                            )
                            reports.append(
                                {
                                    "testType": report_spec.get(
                                        "test_type", spec.get("test_type", "api")
                                    ),
                                    "path": report_target.relative_to(
                                        output
                                    ).as_posix(),
                                    "summaryMd": summary_target.relative_to(
                                        output
                                    ).as_posix(),
                                    "sha256": file_sha256(report_target),
                                    "status": command_status,
                                    "mode": report_spec.get(
                                        "mode", spec.get("mode", "smoke-only")
                                    ),
                                }
                            )
                        except P1Error as error:
                            command_status = "blocked"
                            command_results[-1]["status"] = "blocked"
                            command_results[-1]["error"] = str(error)
                            repository_errors.append(f"{key}: {error}")
                            overall = "blocked"
                            if stage in {"preflight", "prepare"}:
                                pipeline_blocked = True
                            break
                alignment_blocked = (
                    decision["requirements"]["environment_alignment"]
                    and repository_environment_alignment != "verified"
                )
                if decision["evidence_contract"] == "required" and (
                    not reports or alignment_blocked
                ):
                    overall = "blocked"
                    repository_status = "blocked"
                elif any(item["status"] == "blocked" for item in command_results):
                    repository_status = "blocked"
                else:
                    repository_status = (
                        "failed"
                        if any(item["status"] == "failed" for item in command_results)
                        else "passed"
                    )
                if reports:
                    manifest_base = {
                        "schema_version": 1,
                        "run_id": run_id,
                        "repository_key": repository_key,
                        "revision_set_id": revision_set["revision_set_id"],
                        "created_at": now_iso(),
                        "artifacts": artifacts,
                    }
                    artifact_manifest = {
                        **manifest_base,
                        "manifest_digest": canonical_digest(manifest_base),
                    }
                    validate_schema(
                        artifact_manifest,
                        REFERENCE_ROOT / "artifact-manifest.schema.json",
                        "artifact manifest",
                    )
                    manifest_path = output / f"artifact-manifest-{repository_key}.json"
                    write_json(manifest_path, artifact_manifest)
                    checksums_path = write_checksums(
                        output, repository_key, artifacts, manifest_path
                    )
                    modes = {item["mode"] for item in reports}
                    envelope_mode = modes.pop() if len(modes) == 1 else "smoke-only"
                    revision_array = [
                        {
                            "repositoryKey": item["repository_key"],
                            "sourceRef": item["requested_ref"],
                            "sourceCommit": item["resolved_commit"],
                            "worktreeState": "clean",
                        }
                        for item in revision_set["repositories"]
                        if item["status"] == "resolved"
                    ]
                    envelope = {
                        "schemaVersion": 1,
                        "runId": run_id,
                        "createdAt": now_iso(),
                        "evidenceSource": execution_profile,
                        "trigger": trigger,
                        "repository": {
                            "repositoryKey": repository_key,
                            "sourceRef": repository["target_ref"],
                            "sourceCommit": revision["resolved_commit"],
                            "worktreeState": "clean",
                        },
                        "sourceRevision": "exact",
                        "environmentAlignment": repository_environment_alignment,
                        "e2eMode": envelope_mode,
                        "mockStrategy": "none",
                        "featureSources": [],
                        "reports": reports,
                        "revisionSet": revision_array,
                        "revisionSetId": revision_set["revision_set_id"],
                        "decisionId": decision["decision_id"],
                        "decisionDigest": decision["decision_digest"],
                        "evidenceTargets": decision["evidence_targets"],
                        "artifactManifest": manifest_path.relative_to(
                            output
                        ).as_posix(),
                        "artifactManifestDigest": artifact_manifest["manifest_digest"],
                        "checksumsFile": checksums_path.relative_to(output).as_posix(),
                        "runnerAttestations": list(runner_attestations.values()),
                        "evidencePublication": "not-configured",
                        "secretsRedacted": True,
                    }
                    validate_schema(
                        envelope, VALIDATION_EVIDENCE_SCHEMA, "validation evidence"
                    )
                    write_json(output / f"evidence-{repository_key}.json", envelope)
                repository_result = {
                    "repository_key": repository_key,
                    "status": repository_status,
                    "decision": decision,
                    "commands": command_results,
                    "report_count": len(reports),
                    "environment_alignment": repository_environment_alignment,
                }
                if repository_errors:
                    repository_result["reason"] = "; ".join(repository_errors)
                results.append(repository_result)
            except (P1Error, ConfigurationError) as error:
                overall = "blocked"
                results.append(
                    {
                        "repository_key": repository_key,
                        "status": "blocked",
                        "decision": decision,
                        "commands": command_results,
                        "report_count": len(reports),
                        "reason": str(error),
                    }
                )
            finally:
                remove_worktree(source_repo, worktree)
    finally:
        shutil.rmtree(worktree_root, ignore_errors=True)
        shutil.rmtree(lock, ignore_errors=True)
    result = {
        "schema_version": 1,
        "run_id": run_id,
        "suite_key": suite_key,
        "attempt": attempt,
        "idempotency_key": smoke_key,
        "reused": False,
        "output_dir": str(output.resolve()),
        "status": overall,
        "revision_set": revision_set,
        "runs": results,
    }
    write_json(output / "smoke-summary.json", result)
    flattened_commands = [
        command for run in results for command in run.get("commands", [])
    ]
    write_metrics(
        output,
        run_id,
        "smoke",
        started_ns,
        {
            "repositories": len(results),
            "commands": len(flattened_commands),
            "local_runner_commands": sum(
                command.get("runner") == "local" for command in flattened_commands
            ),
            "remote_runner_commands": sum(
                command.get("runner") not in {None, "local"}
                for command in flattened_commands
            ),
            "execution_retries": sum(
                max(0, len(command.get("attempts", [])) - 1)
                for command in flattened_commands
            ),
            "reports": sum(run.get("report_count", 0) for run in results),
            "blocked": sum(run.get("status") == "blocked" for run in results),
            "failed": sum(run.get("status") == "failed" for run in results),
            "passed": sum(run.get("status") == "passed" for run in results),
            "queue_latency_ms": sum(
                command.get("queue_latency_ms", 0) for command in flattened_commands
            ),
        },
        {
            "product_key": product["product_key"],
            "revision_set_id": revision_set["revision_set_id"],
            "suite_key": suite_key,
            "environment_profile": execution_profile,
            "attempt": attempt,
        },
    )
    store_idempotent_result(runtime, "smoke", smoke_key, output / "smoke-summary.json")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SBTD knowledge-base P1 runtime")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-config")
    validate.add_argument("--product", required=True)
    validate.add_argument("--workspace")
    decision = sub.add_parser("decision")
    decision.add_argument("--product", required=True)
    decision.add_argument("--repository", required=True)
    decision.add_argument("--trigger", required=True, choices=sorted(ALLOWED_TRIGGERS))
    decision.add_argument(
        "--execution-profile", required=True, choices=sorted(ALLOWED_PROFILES)
    )
    decision.add_argument("--target", action="append", default=[])
    decision.add_argument("--central-policy")
    decision.add_argument("--output")
    ingest = sub.add_parser("ingest")
    ingest.add_argument("--product", required=True)
    ingest.add_argument("--workspace", required=True)
    ingest.add_argument("--output", required=True)
    ingest.add_argument("--run-id")
    ingest.add_argument("--no-fetch", action="store_true")
    smoke = sub.add_parser("smoke")
    smoke.add_argument("--product", required=True)
    smoke.add_argument("--workspace", required=True)
    smoke.add_argument("--output", required=True)
    smoke.add_argument(
        "--trigger", default="schedule", choices=sorted(ALLOWED_TRIGGERS)
    )
    smoke.add_argument(
        "--execution-profile",
        default="knowledge-server",
        choices=sorted(SMOKE_PROFILES),
    )
    smoke.add_argument("--target", action="append", default=[])
    smoke.add_argument("--central-policy")
    smoke.add_argument("--deployment-manifest")
    smoke.add_argument("--runner-label", action="append", default=[])
    smoke.add_argument(
        "--environment-alignment",
        default="unverified",
        choices=("verified", "unverified", "mismatch", "not-needed"),
    )
    smoke.add_argument("--suite-key", default="smoke")
    smoke.add_argument("--attempt", type=int, default=1)
    smoke.add_argument("--run-id")
    smoke.add_argument("--no-fetch", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-config":
            product, workspace = load_configs(args.product, args.workspace)
            result = {
                "status": "valid",
                "product_key": product["product_key"],
                "repository_count": len(product["repositories"]),
                "workspace": workspace is not None,
            }
        elif args.command == "decision":
            product, _ = load_configs(args.product)
            central = load_data(args.central_policy) if args.central_policy else None
            result = resolve_evidence_decision(
                product,
                args.repository,
                args.trigger,
                args.execution_profile,
                args.target,
                central,
            )
            if args.output:
                write_json(Path(args.output), result)
        elif args.command == "ingest":
            result = run_ingest(
                args.product,
                args.workspace,
                args.output,
                fetch=not args.no_fetch,
                run_id=args.run_id,
            )
        else:
            central = load_data(args.central_policy) if args.central_policy else None
            result = run_smoke(
                args.product,
                args.workspace,
                args.output,
                trigger=args.trigger,
                execution_profile=args.execution_profile,
                fetch=not args.no_fetch,
                run_id=args.run_id,
                explicit_targets=args.target,
                environment_alignment=args.environment_alignment,
                central_policy=central,
                deployment_manifest_path=args.deployment_manifest,
                runner_labels=args.runner_label,
                suite_key=args.suite_key,
                attempt=args.attempt,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        status = result.get("status") or result.get("evidence_contract")
        return 3 if status == "blocked" else 2 if status == "partial" else 0
    except (P1Error, ConfigurationError, json.JSONDecodeError) as error:
        print(
            json.dumps(
                {"status": "blocked", "error": str(error)}, ensure_ascii=False, indent=2
            ),
            file=sys.stderr,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
