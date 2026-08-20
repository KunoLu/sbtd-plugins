#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import filecmp
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import cast


SKILL_DIR = Path(__file__).resolve().parents[1]
SKILL_ENTRY_DIR = Path(__file__).absolute().parents[1]
CATALOG_PATH = SKILL_DIR / "catalog.json"
EXTERNAL_STABLE_ROOT = SKILL_DIR / "assets" / "external-skills" / "stable"
EXTERNAL_STABLE_MANIFEST = EXTERNAL_STABLE_ROOT / "MANIFEST.json"


def read_skill_frontmatter_name(skill_md: Path) -> str | None:
    try:
        lines = skill_md.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        lines = skill_md.read_text(errors="ignore").splitlines()
    except OSError:
        return None

    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:80]:
        stripped = line.strip()
        if stripped == "---":
            return None
        if stripped.startswith("name:"):
            return stripped.split(":", 1)[1].strip().strip("'\"")
    return None


def validate_relative_catalog_path(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{field} must be a non-empty relative path")
    if (
        Path(value).is_absolute()
        or re.match(r"^(?:[A-Za-z]:[\\/]|[\\/])", value)
        or re.search(r"(^|[\\/])\.\.([\\/]|$)", value)
    ):
        raise RuntimeError(
            f"{field} must be a relative path contained by its root: {value}"
        )
    return value


def resolve_local_catalog_source(value: object, entry_id: str) -> Path:
    relative = validate_relative_catalog_path(
        value, f"SBTD Onboard catalog source for {entry_id}"
    )
    source = (SKILL_DIR / relative).resolve()
    try:
        source.relative_to(SKILL_DIR)
    except ValueError as exc:
        raise RuntimeError(
            f"SBTD Onboard catalog source escapes the Skill root: {relative}"
        ) from exc
    if not source.exists():
        raise RuntimeError(
            f"SBTD Onboard catalog source is missing for {entry_id}: {source}"
        )
    return source


def valid_https_repository_url(value: object) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(r"https://[^/?#\s]+/(?:[^/?#\s]+/)*[^/?#\s]+/?", value)
        is not None
    )


CATALOG_KIND_CONTRACTS: dict[str, tuple[str, frozenset[str]]] = {
    "agent-template": (
        "agent:",
        frozenset({"codex-global-agents", "project-agents"}),
    ),
    "project-template": ("project:", frozenset({"project-gitignore"})),
    "bundled-skill": (
        "skill:",
        frozenset({"skill", "skill:sbtd-workflow-onboard"}),
    ),
    "external-skill": ("skill:", frozenset({"external-skill"})),
}


def load_catalog() -> dict[str, object]:
    try:
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read SBTD Onboard catalog: {exc}") from exc
    if (
        catalog.get("schemaVersion") != 1
        or catalog.get("name") != "sbtd-workflow-onboard"
    ):
        raise RuntimeError("SBTD Onboard catalog identity or schema version is invalid")
    entries = catalog.get("entries")
    if not isinstance(entries, list) or not entries:
        raise RuntimeError("SBTD Onboard catalog must contain entries")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise RuntimeError("SBTD Onboard catalog entries must be objects")
        if set(entry) != {"id", "kind", "source", "targetRole"}:
            raise RuntimeError("SBTD Onboard catalog entries have invalid fields")
        entry_id = entry.get("id")
        entry_kind = entry.get("kind")
        source_value = entry.get("source")
        target_role = entry.get("targetRole")
        if (
            not isinstance(entry_id, str)
            or re.fullmatch(r"(agent|project|skill):[a-z0-9][a-z0-9-]*", entry_id)
            is None
            or entry_id in seen
        ):
            raise RuntimeError(
                f"SBTD Onboard catalog entry id is invalid or duplicated: {entry_id}"
            )
        contract = CATALOG_KIND_CONTRACTS.get(str(entry_kind))
        if contract is None:
            raise RuntimeError(f"SBTD Onboard catalog kind is invalid for {entry_id}")
        expected_prefix, allowed_roles = contract
        if not entry_id.startswith(expected_prefix):
            raise RuntimeError(
                f"SBTD Onboard catalog id does not match kind {entry_kind}: {entry_id}"
            )
        if not isinstance(target_role, str) or target_role not in allowed_roles:
            raise RuntimeError(
                f"SBTD Onboard catalog target role is invalid for {entry_id}: {target_role}"
            )
        if entry_kind == "external-skill":
            if not isinstance(source_value, dict) or set(source_value) != {
                "repo",
                "subpath",
                "aliases",
            }:
                raise RuntimeError(
                    f"SBTD Onboard external source is invalid for {entry_id}"
                )
            repo = source_value.get("repo")
            subpath = source_value.get("subpath")
            aliases = source_value.get("aliases")
            if not valid_https_repository_url(repo):
                raise RuntimeError(
                    f"SBTD Onboard external source repo must be a valid HTTPS "
                    f"repository URL for {entry_id}"
                )
            validate_relative_catalog_path(
                subpath, f"SBTD Onboard external source subpath for {entry_id}"
            )
            if (
                not isinstance(aliases, list)
                or not aliases
                or any(not isinstance(alias, str) or not alias for alias in aliases)
                or len(aliases) != len(set(aliases))
            ):
                raise RuntimeError(
                    f"SBTD Onboard external source is invalid for {entry_id}"
                )
        else:
            source = resolve_local_catalog_source(source_value, entry_id)
            if entry_kind in {"agent-template", "project-template"}:
                if not source.is_file():
                    raise RuntimeError(
                        f"SBTD Onboard {entry_kind} source must be a regular file "
                        f"for {entry_id}: {source}"
                    )
            else:
                if not source.is_dir():
                    raise RuntimeError(
                        f"SBTD Onboard bundled-skill source must be a directory "
                        f"for {entry_id}: {source}"
                    )
                expected_name = entry_id.removeprefix("skill:")
                actual_name = read_skill_frontmatter_name(source / "SKILL.md")
                if actual_name != expected_name:
                    raise RuntimeError(
                        f"SBTD Onboard bundled-skill frontmatter name must match "
                        f"{entry_id}: expected {expected_name}, got "
                        f"{actual_name or '<missing>'}"
                    )
        seen.add(entry_id)
    return cast(dict[str, object], catalog)


def catalog_source(catalog: dict[str, object], entry_id: str) -> Path:
    entries = cast(list[dict[str, object]], catalog["entries"])
    for entry in entries:
        if entry["id"] == entry_id:
            return (SKILL_DIR / str(entry["source"])).resolve()
    raise RuntimeError(f"SBTD Onboard catalog entry is missing: {entry_id}")


def catalog_external_skill_sources(
    catalog: dict[str, object],
) -> dict[str, dict[str, object]]:
    sources: dict[str, dict[str, object]] = {}
    for entry in cast(list[dict[str, object]], catalog["entries"]):
        if entry.get("kind") != "external-skill":
            continue
        source = cast(dict[str, object], entry["source"])
        sources[str(entry["id"]).removeprefix("skill:")] = {
            "repo": str(source["repo"]),
            "subpath": str(source["subpath"]),
            "aliases": tuple(cast(list[str], source["aliases"])),
        }
    return sources


CATALOG = load_catalog()
GLOBAL_AGENTS_TEMPLATE = catalog_source(CATALOG, "agent:codex-global")
PROJECT_AGENTS_TEMPLATE = catalog_source(CATALOG, "agent:project")
PROJECT_GITIGNORE_TEMPLATE = catalog_source(CATALOG, "project:gitignore")
SKILL_SOURCES = {
    str(entry["id"]).removeprefix("skill:"): (
        SKILL_DIR / str(entry["source"])
    ).resolve()
    for entry in cast(list[dict[str, object]], CATALOG["entries"])
    if entry.get("kind") == "bundled-skill"
}
EXTERNAL_SKILL_SOURCES = catalog_external_skill_sources(CATALOG)
NVM_INSTALL_URL = "https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.5/install.sh"
RTK_INSTALL_URL = (
    "https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh"
)
TEMURIN21_RELEASES_URL = "https://github.com/adoptium/temurin21-binaries/releases"
TEMURIN_RELEASES_API_TEMPLATE = (
    "https://api.github.com/repos/adoptium/temurin{major}-binaries/releases/latest"
)
MAESTRO_INSTALL_URL = "https://get.maestro.mobile.dev"
CAVEMAN_INSTALL_SPEC = "JuliusBrussee/caveman"
CAVEMAN_INSTALL_SH_URL = (
    "https://raw.githubusercontent.com/JuliusBrussee/caveman/main/install.sh"
)
CAVEMAN_INSTALL_PS1_URL = (
    "https://raw.githubusercontent.com/JuliusBrussee/caveman/main/install.ps1"
)
JAVA_MIN_MAJOR = 17
BUNDLED_SKILL_LEGACY_NAMES = {
    "sbtd-workflow-onboard": ("kuno-workflow-onboard-skills",),
}
CLI_TOOLS = (
    {
        "name": "rtk",
        "versionArgs": ("--version",),
        "globalInstall": "curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh",
        "projectInstall": None,
        "advice": "Install RTK from rtk-ai/rtk and verify with `rtk gain`; do not treat the unrelated Rust Type Kit package as valid.",
    },
    {
        "name": "trellis",
        "versionArgs": ("--version",),
        "globalInstall": "npm install -g @mindfoldhq/trellis@latest",
        "projectInstall": None,
        "advice": "Install Trellis globally so one verified CLI can initialize every selected project root.",
    },
    {
        "name": "gitnexus",
        "versionArgs": ("--version",),
        "globalInstall": "npm install -g gitnexus@latest",
        "projectInstall": None,
        "advice": "Install GitNexus globally; each project keeps its own index while sharing the verified CLI and MCP command.",
    },
)
AGENT_CLI_SPECS = {
    "codex": {
        "label": "Codex",
        "command": "codex",
        "npmPackage": "@openai/codex",
        "versionArgs": ("--version",),
        "advice": "Install the latest Codex CLI globally from the official @openai/codex npm package.",
    },
    "claude": {
        "label": "Claude Code",
        "command": "claude",
        "npmPackage": "@anthropic-ai/claude-code",
        "versionArgs": ("--version",),
        "advice": "Install the latest Claude Code CLI globally from the official @anthropic-ai/claude-code npm package.",
    },
    "kimi": {
        "label": "Kimi Code",
        "command": "kimi",
        "npmPackage": "@moonshot-ai/kimi-code",
        "versionArgs": ("--version",),
        "advice": "Install the latest Kimi Code CLI globally from the official @moonshot-ai/kimi-code npm package. The npm distribution requires a supported Node.js runtime.",
    },
    "oh-my-pi": {
        "label": "Oh My Pi",
        "command": "omp",
        "npmPackage": "@oh-my-pi/pi-coding-agent",
        "versionArgs": ("--version",),
        "advice": "Install the latest Oh My Pi CLI globally from @oh-my-pi/pi-coding-agent and verify the omp command. Upstream recommends its native or Bun installer, so npm installation must pass the command verification gate.",
    },
}
AGENT_PLATFORM_ALIASES = {
    "codex": "codex",
    "claude": "claude",
    "claude-code": "claude",
    "claudecode": "claude",
    "kimi": "kimi",
    "kimi-code": "kimi",
    "kimicode": "kimi",
    "oh-my-pi": "oh-my-pi",
    "ohmypi": "oh-my-pi",
    "omp": "oh-my-pi",
}
TRELLIS_INIT_PLATFORMS = (
    "cursor",
    "claude",
    "opencode",
    "codex",
    "kilo",
    "kiro",
    "gemini",
    "antigravity",
    "devin",
    "windsurf",
    "qoder",
    "codebuddy",
    "copilot",
    "droid",
    "omp",
    "pi",
    "reasonix",
    "zcode",
    "trae",
)
TRELLIS_BOOTSTRAP_TASK_CANDIDATES = (".trellis/tasks/00-bootstrap-guidelines",)
BUNDLED_SKILLS = tuple(SKILL_SOURCES.keys())
MATTPOCOCK_CANONICAL_SKILLS = (
    "diagnosing-bugs",
    "tdd",
    "grill-me",
    "grill-with-docs",
    "grilling",
    "domain-modeling",
    "codebase-design",
    "handoff",
    "writing-for-agents",
    "to-spec",
    "to-tickets",
)
MATTPOCOCK_LEGACY_RENAMES = {
    "diagnose": "diagnosing-bugs",
    "write-a-skill": "writing-for-agents",
    "writing-great-skills": "writing-for-agents",
    "to-prd": "to-spec",
    "to-issues": "to-tickets",
}
MATTPOCOCK_REMOVED_SKILLS = {
    "zoom-out": "Removed upstream; use repo exploration, GitNexus exploring, codebase-design, or book-refactoring-pass instead.",
}
MATTPOCOCK_REQUIRED_DEPENDENCIES = {
    "tdd": ("codebase-design",),
    "grill-me": ("grilling",),
    "grill-with-docs": ("grilling", "domain-modeling"),
}
REFERENCED_SKILLS = (
    *MATTPOCOCK_CANONICAL_SKILLS,
    "ui-ux-pro-max",
    "impeccable",
    "shadcn",
)
INTERACTION_SKILLS = ("caveman",)
if set(EXTERNAL_SKILL_SOURCES) != set(REFERENCED_SKILLS):
    raise RuntimeError(
        "SBTD Onboard catalog external Skills do not match the referenced Skill contract"
    )
MATTPOCOCK_REPO = str(EXTERNAL_SKILL_SOURCES["diagnosing-bugs"]["repo"])
MATTPOCOCK_SKILL_SUBPATHS = {
    name: str(EXTERNAL_SKILL_SOURCES[name]["subpath"])
    for name in MATTPOCOCK_CANONICAL_SKILLS
}
if any(
    EXTERNAL_SKILL_SOURCES[name]["repo"] != MATTPOCOCK_REPO
    for name in MATTPOCOCK_CANONICAL_SKILLS
):
    raise RuntimeError(
        "SBTD Onboard catalog mattpocock Skills must share one repository"
    )
EXTERNAL_REPO_TO_SKILLS: dict[str, tuple[str, ...]] = {}
for _skill_name, _source_spec in EXTERNAL_SKILL_SOURCES.items():
    _repo = str(_source_spec["repo"])
    EXTERNAL_REPO_TO_SKILLS[_repo] = (
        *EXTERNAL_REPO_TO_SKILLS.get(_repo, ()),
        _skill_name,
    )
BASE_MANUAL_CHECKS = (
    {
        "name": "Chrome DevTools MCP",
        "category": "mcp",
        "advice": "Confirm the active Agent or IDE exposes Chrome DevTools MCP tools before relying on it for Web runtime diagnostics.",
        "steps": (
            "Configure or enable the Chrome DevTools MCP server in the active Agent or IDE MCP settings.",
            "Confirm Google Chrome or Chrome for Testing is available when the MCP server requires it.",
            "Restart or reload the Agent environment so the MCP server is discovered.",
            "Confirm Chrome DevTools MCP tools are visible before relying on it for console, network, screenshot, or performance diagnostics.",
            "Treat Chrome DevTools MCP output as diagnostic evidence, not as a replacement for project tests or Playwright E2E.",
        ),
    },
    {
        "name": "Playwright MCP",
        "category": "mcp",
        "advice": "Confirm Playwright MCP tools are visible before relying on them for page exploration, accessibility snapshots, or locator assistance.",
        "steps": (
            "When the selected Playwright distribution exposes it, prefer its bundled `npx playwright mcp` entrypoint; otherwise configure a compatible dedicated Playwright MCP server.",
            "Restart or reload the Agent environment so the MCP server is discovered.",
            "Confirm Playwright MCP tools are visible to the Agent.",
            "Use Playwright MCP for exploration and locator assistance only; do not treat it as a substitute for project-level Playwright CLI.",
        ),
    },
)


@dataclass(frozen=True)
class Operation:
    label: str
    source: Path
    target: Path
    kind: str
    same_location: bool = False


def expand_path(value: str | None) -> Path | None:
    if not value:
        return None
    return Path(value).expanduser().resolve()


def default_codex_home() -> Path:
    env_value = os.environ.get("CODEX_HOME")
    if env_value:
        return Path(env_value).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def known_global_skills_dirs() -> tuple[Path, ...]:
    home = Path.home()
    return tuple(
        path.resolve()
        for path in (
            home / ".agents" / "skills",
            home / ".agent" / "skills",
            home / ".codex" / "skills",
            home / ".claude" / "skills",
            home / ".pi" / "agent" / "skills",
            default_codex_home() / "skills",
        )
    )


def installed_global_skills_dir() -> Path | None:
    known_roots = set(known_global_skills_dirs())
    for skill_dir in (SKILL_ENTRY_DIR, SKILL_DIR):
        if skill_dir.name != "sbtd-workflow-onboard":
            continue
        parent = skill_dir.parent.resolve()
        if parent in known_roots and (skill_dir / "SKILL.md").is_file():
            return parent
    return None


def resolve_global_skills_dir(value: str | None = None) -> tuple[Path, str]:
    explicit = expand_path(value)
    if explicit:
        return explicit, "argument"

    environment = os.environ.get("AGENT_SKILLS_DIR")
    if environment:
        return Path(environment).expanduser().resolve(), "environment"

    installed = installed_global_skills_dir()
    if installed:
        return installed, "installed-skill-parent"

    return (default_codex_home() / "skills").resolve(), "platform-default"


def default_global_skills_dir() -> Path:
    return resolve_global_skills_dir()[0]


def resolve_project_root(
    args: argparse.Namespace, required: bool = False
) -> Path | None:
    """Resolve the single-project interface used by project-only tool installers."""
    project_root = expand_path(getattr(args, "project_root", None))
    if project_root and not project_root.is_dir():
        raise SystemExit(
            f"--project-root must be an existing directory: {project_root}"
        )
    if required and not project_root:
        raise SystemExit(
            "--project-root is required unless --skip-project-agents is used"
        )
    return project_root


def resolve_project_roots(
    args: argparse.Namespace, required: bool = False
) -> list[Path]:
    raw = (getattr(args, "projects_root", None) or "").strip()
    if not raw:
        if required:
            raise SystemExit("--projects-root is required")
        return []

    roots: list[Path] = []
    for value in raw.split(","):
        candidate_text = value.strip()
        if not candidate_text:
            continue
        candidate = Path(candidate_text).expanduser()
        if not candidate.is_absolute():
            raise SystemExit(
                f"--projects-root only accepts absolute paths: {candidate_text}"
            )
        candidate = candidate.resolve()
        if not candidate.is_dir():
            raise SystemExit(f"Project root does not exist: {candidate}")
        if candidate not in roots:
            roots.append(candidate)

    if required and not roots:
        raise SystemExit("--projects-root must contain at least one absolute path")
    return roots


def run_command(
    command: tuple[str, ...], timeout: int = 30, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def shell_result(
    script: str, timeout: int = 300
) -> subprocess.CompletedProcess[str] | None:
    shell = shutil.which("bash") or shutil.which("sh")
    if not shell:
        return None
    return run_command((shell, "-lc", script), timeout=timeout)


def command_output(
    command: tuple[str, ...], timeout: int = 10, env: dict[str, str] | None = None
) -> tuple[int | None, str]:
    completed = run_command(command, timeout=timeout, env=env)
    if completed is None:
        return None, ""
    output = (completed.stdout or completed.stderr).strip()
    return completed.returncode, output


def command_version(command: str, version_args: tuple[str, ...]) -> str | None:
    _, output = command_output((command, *version_args), timeout=5)
    return output.splitlines()[0] if output else None


def nvm_dir_shell_expr() -> str:
    return '${NVM_DIR:-$([ -z "${XDG_CONFIG_HOME-}" ] && printf %s "$HOME/.nvm" || printf %s "$XDG_CONFIG_HOME/nvm")}'


def nvm_load_script() -> str:
    nvm_dir = nvm_dir_shell_expr()
    return (
        f'export NVM_DIR="{nvm_dir}"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"'
    )


def check_nvm() -> dict[str, object]:
    system = platform.system() or sys.platform
    if system == "Windows":
        path = shutil.which("nvm")
        version = command_version("nvm", ("version",)) if path else None
        return {
            "name": "nvm",
            "installed": bool(path),
            "path": path,
            "version": version,
            "installableByScript": False,
            "advice": "Native Windows should use nvm-windows, nvs, or WSL; the nvm-sh installer is for POSIX shells.",
        }

    completed = shell_result(
        f"{nvm_load_script()}; command -v nvm; nvm --version", timeout=10
    )
    installed = bool(completed and completed.returncode == 0)
    lines = (completed.stdout if completed else "").strip().splitlines()
    return {
        "name": "nvm",
        "installed": installed,
        "path": lines[0] if lines else None,
        "version": lines[-1] if len(lines) > 1 else None,
        "installableByScript": system in {"Darwin", "Linux"},
        "advice": "Install nvm first, then use `nvm install --lts`, `nvm alias default 'lts/*'`, and `nvm use --lts`.",
    }


def activate_nvm_node_path() -> str | None:
    if platform.system() == "Windows":
        return None
    completed = shell_result(
        f"{nvm_load_script()}; "
        "(nvm use --lts >/dev/null 2>&1 || nvm use default >/dev/null 2>&1 || true); "
        "command -v npm",
        timeout=20,
    )
    if not completed or completed.returncode != 0:
        return None
    npm_path = (
        completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    )
    if not npm_path:
        return None
    npm_bin = str(Path(npm_path).parent)
    current = os.environ.get("PATH", "")
    if npm_bin not in current.split(os.pathsep):
        os.environ["PATH"] = f"{npm_bin}{os.pathsep}{current}"
    return npm_bin


def check_npm_runtime() -> dict[str, object]:
    if not shutil.which("npm"):
        activate_nvm_node_path()
    npm_path = shutil.which("npm")
    node_path = shutil.which("node")
    npm_version = command_version("npm", ("--version",)) if npm_path else None
    node_version = command_version("node", ("--version",)) if node_path else None
    nvm = check_nvm()
    return {
        "platform": platform.system() or sys.platform,
        "npm": {
            "installed": bool(npm_path and npm_version),
            "path": npm_path,
            "version": npm_version,
        },
        "node": {
            "installed": bool(node_path and node_version),
            "path": node_path,
            "version": node_version,
        },
        "nvm": nvm,
        "requiredBeforeCliChecks": True,
        "advice": "CLI tool checks run only after npm is usable. If npm is missing, run `python scripts/onboard.py ensure-npm --yes` after user confirmation.",
    }


def check_cli_tool(spec: dict[str, str | tuple[str, ...]]) -> dict[str, object]:
    name = str(spec["name"])
    path = shutil.which(name)
    version = command_version(name, spec["versionArgs"]) if path else None
    installed = bool(path and version)
    result = {
        "name": name,
        "category": "cli",
        "installed": installed,
        "path": path,
        "version": version,
        "globalInstall": spec["globalInstall"],
        "projectInstall": spec["projectInstall"],
        "advice": spec["advice"],
    }
    if name == "rtk" and path:
        code, output = command_output(("rtk", "gain"), timeout=10)
        correct = code == 0
        version_looks_correct = bool(version and version.lower().startswith("rtk "))
        result["installed"] = correct
        result["rtkGainVerified"] = correct
        result["wrongPackageSuspected"] = not correct and not version_looks_correct
        result["verificationFailed"] = not correct and version_looks_correct
        result["verifyCommand"] = "rtk gain"
        result["verifyOutput"] = output.splitlines()[0] if output else None
        if result["wrongPackageSuspected"]:
            result["advice"] = (
                "An `rtk` command exists but `rtk gain` failed, so this may be the wrong rtk package. Confirm before uninstalling or replacing it."
            )
        elif result["verificationFailed"]:
            result["advice"] = (
                "The rtk binary looks like rtk-ai/rtk, but `rtk gain` failed. Troubleshoot RTK data directory permissions or reinstall after user confirmation."
            )
    elif name == "rtk":
        result["rtkGainVerified"] = False
        result["wrongPackageSuspected"] = False
        result["verificationFailed"] = False
        result["verifyCommand"] = "rtk gain"
    return result


def normalize_agent_platform(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    platform_name = AGENT_PLATFORM_ALIASES.get(normalized)
    if not platform_name:
        allowed = ", ".join(("codex", "claude", "kimi", "oh-my-pi", "omp"))
        raise SystemExit(
            f"Unsupported Agent platform: {value}. Allowed values: {allowed}"
        )
    return platform_name


def check_agent_cli(platform_value: str) -> dict[str, object]:
    platform_name = normalize_agent_platform(platform_value)
    spec = AGENT_CLI_SPECS[platform_name]
    command = str(spec["command"])
    version_args = tuple(str(item) for item in spec["versionArgs"])
    path = shutil.which(command)
    code, output = (
        command_output((command, *version_args), timeout=10) if path else (None, "")
    )
    version = output.splitlines()[0] if code == 0 and output else None
    npm_package = str(spec["npmPackage"])
    result: dict[str, object] = {
        "mode": "check-agent-cli",
        "platform": platform_name,
        "label": spec["label"],
        "command": command,
        "path": path,
        "version": version,
        "installed": bool(path and version),
        "npmPackage": npm_package,
        "installCommand": f"npm install -g {npm_package}@latest",
        "verifyCommand": command_display((command, *version_args)),
        "advice": spec["advice"],
        "runtime": check_npm_runtime(),
    }
    if path and not version:
        result["verificationFailed"] = True
        result["verifyOutput"] = output.splitlines()[0] if output else None
    return result


def print_agent_cli_check(result: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    status = "installed" if result["installed"] else "missing"
    if result.get("verificationFailed"):
        status = "verification-failed"
    print(f"Target Agent CLI: {result['label']}")
    print(f"- status: {status}")
    print(f"- command: {result['command']}")
    if result.get("path"):
        print(f"- path: {result['path']}")
    if result.get("version"):
        print(f"- version: {result['version']}")
    if not result["installed"]:
        print(f"- install: {result['installCommand']}")
        print(f"- advice: {result['advice']}")


def parse_java_major(output: str | None) -> int | None:
    if not output:
        return None
    match = re.search(
        r'(?:openjdk|java)?\s*version\s+"?(\d+)(?:\.(\d+))?', output, re.IGNORECASE
    )
    if not match:
        match = re.search(r"\b(\d+)(?:\.(\d+))?\.\d+", output)
    if not match:
        return None
    first = int(match.group(1))
    second = match.group(2)
    if first == 1 and second:
        return int(second)
    return first


def java_version_output() -> tuple[str | None, str | None]:
    code, output = command_output(("java", "--version"), timeout=5)
    if code == 0 and output:
        return output.splitlines()[0], "java --version"
    code, output = command_output(("java", "-version"), timeout=5)
    if code == 0 and output:
        return output.splitlines()[0], "java -version"
    return None, "java --version"


def usable_java_home(candidate: str | Path | None) -> Path | None:
    if not candidate:
        return None
    path = Path(candidate).expanduser()
    if (path / "bin" / "java").is_file():
        return path.resolve()
    return None


def java_binary_version(java_binary: Path) -> tuple[str | None, str | None]:
    code, output = command_output((str(java_binary), "--version"), timeout=5)
    if code == 0 and output:
        return output.splitlines()[0], f"{java_binary} --version"
    code, output = command_output((str(java_binary), "-version"), timeout=5)
    if code == 0 and output:
        return output.splitlines()[0], f"{java_binary} -version"
    return None, f"{java_binary} --version"


def java_home_major(java_home: Path) -> int | None:
    version, _ = java_binary_version(java_home / "bin" / "java")
    return parse_java_major(version)


def macos_java_home(major: int | None = None) -> Path | None:
    if platform.system() != "Darwin":
        return None
    helper = Path("/usr/libexec/java_home")
    if not helper.is_file():
        return None
    command = (str(helper), "-v", str(major)) if major else (str(helper),)
    code, output = command_output(command, timeout=5)
    if code != 0 or not output:
        return None
    return usable_java_home(output.splitlines()[0].strip())


def infer_java_home_from_path(java_path: str | None) -> Path | None:
    if java_path:
        java_bin = Path(java_path).expanduser().resolve()
        if platform.system() == "Darwin" and java_bin == Path("/usr/bin/java"):
            return None
        if java_bin.name == "java" and java_bin.parent.name == "bin":
            inferred = usable_java_home(java_bin.parent.parent)
            if inferred:
                return inferred
    return None


def java_home_candidates(java_path: str | None) -> list[Path]:
    candidates: list[Path] = []

    def add(candidate: str | Path | None) -> None:
        java_home = usable_java_home(candidate)
        if java_home and java_home not in candidates:
            candidates.append(java_home)

    add(infer_java_home_from_path(java_path))
    add(os.environ.get("JAVA_HOME"))
    add(macos_java_home())
    add(macos_java_home(JAVA_MIN_MAJOR))

    patterns = (
        Path.home() / "JDK" / "*" / "Contents" / "Home",
        Path.home() / "JDK" / "*",
        Path.home()
        / "Library"
        / "Java"
        / "JavaVirtualMachines"
        / "*"
        / "Contents"
        / "Home",
        Path("/Library/Java/JavaVirtualMachines") / "*" / "Contents" / "Home",
        Path("/usr/lib/jvm") / "*",
    )
    for pattern in patterns:
        for candidate in pattern.parent.glob(pattern.name):
            add(candidate)

    return candidates


def select_java_home(
    java_path: str | None,
) -> tuple[Path | None, int | None, str | None]:
    candidates = java_home_candidates(java_path)
    candidate_info: list[tuple[Path, int | None]] = [
        (candidate, java_home_major(candidate)) for candidate in candidates
    ]
    if (
        candidate_info
        and candidate_info[0][1]
        and candidate_info[0][1] >= JAVA_MIN_MAJOR
    ):
        return candidate_info[0][0], candidate_info[0][1], "current-java-home"
    for candidate, major in candidate_info[1:] if candidate_info else []:
        if major and major >= JAVA_MIN_MAJOR:
            return candidate, major, "alternate-installed-jdk"
    return None, None, None


def unique_path_entries(entries: list[str | None]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if not entry or entry in seen:
            continue
        seen.add(entry)
        result.append(entry)
    return result


def maestro_bin_dir(maestro_path: str | None) -> str:
    if maestro_path:
        return str(Path(maestro_path).expanduser().parent)
    return str(Path.home() / ".maestro" / "bin")


def mcp_path_value(java_home: str | None, maestro_path: str | None) -> str:
    java_bin = f"{java_home}/bin" if java_home else "<JAVA_HOME>/bin"
    return os.pathsep.join(
        unique_path_entries(
            [
                maestro_bin_dir(maestro_path),
                java_bin,
                "/usr/local/bin",
                "/opt/homebrew/bin",
                "/usr/bin",
                "/bin",
                "/usr/sbin",
                "/sbin",
            ]
        )
    )


def toml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def gitnexus_mcp_server_config(
    gitnexus_check: dict[str, object],
) -> dict[str, object] | None:
    command = gitnexus_check.get("path")
    if not gitnexus_check.get("installed") or not command:
        return None
    return {
        "command": str(command),
        "args": ["mcp"],
        "env": {},
    }


def gitnexus_mcp_toml_example(gitnexus_check: dict[str, object]) -> str | None:
    config = gitnexus_mcp_server_config(gitnexus_check)
    if not config:
        return None
    return "\n".join(
        [
            "[mcp_servers.gitnexus]",
            f'command = "{toml_string(str(config["command"]))}"',
            'args = ["mcp"]',
        ]
    )


def gitnexus_mcp_json_example(gitnexus_check: dict[str, object]) -> str | None:
    config = gitnexus_mcp_server_config(gitnexus_check)
    if not config:
        return None
    return json.dumps(
        {"mcpServers": {"gitnexus": config}},
        indent=2,
        ensure_ascii=False,
    )


def gitnexus_mcp_config_examples(gitnexus_check: dict[str, object]) -> dict[str, str]:
    generic_json = gitnexus_mcp_json_example(gitnexus_check)
    toml = gitnexus_mcp_toml_example(gitnexus_check)
    if not generic_json or not toml:
        return {}
    return {
        "genericJson": generic_json,
        "toml": toml,
    }


def build_gitnexus_mcp_manual_check(
    gitnexus_check: dict[str, object],
) -> dict[str, object]:
    server_config = gitnexus_mcp_server_config(gitnexus_check)
    config_examples = gitnexus_mcp_config_examples(gitnexus_check)
    readiness = (
        "Use the generated MCP server config with the detected local GitNexus CLI path and `args = [mcp]`; for Codex this maps to `codex mcp add gitnexus -- <detected-gitnexus-path> mcp`."
        if server_config
        else "Install or repair the GitNexus CLI first, then rerun `check` so the workflow can detect the local executable path before configuring GitNexus MCP."
    )
    item: dict[str, object] = {
        "name": "GitNexus MCP",
        "category": "mcp",
        "advice": "After GitNexus CLI is installed, use the detected local GitNexus executable path for stdio MCP config, then confirm the current Agent environment exposes GitNexus MCP tools and that the target project has an index before relying on GitNexus analysis.",
        "steps": (
            "Confirm the GitNexus CLI works, for example with `gitnexus --version` and `gitnexus status` in the target project.",
            readiness,
            "Configure or enable the GitNexus MCP server in the active Agent or IDE MCP settings using stdio command + args from the generated config. Use other transports only when the user explicitly selected a transport-specific setup.",
            "Restart or reload the Agent environment so the MCP server is discovered.",
            "Confirm GitNexus MCP tools or resources are visible to the Agent, then check the target project index.",
            "If the project is not indexed yet, run GitNexus analysis from the project root and re-check MCP visibility.",
        ),
    }
    if server_config:
        item["mcpServerConfig"] = server_config
        item["configExample"] = config_examples["genericJson"]
        item["configExamples"] = config_examples
    return item


def maestro_mcp_environment(
    java_check: dict[str, object], maestro_check: dict[str, object]
) -> dict[str, str]:
    java_home = str(java_check.get("javaHome") or "<JAVA_HOME>")
    path_value = mcp_path_value(
        str(java_check.get("javaHome")) if java_check.get("javaHome") else None,
        str(maestro_check.get("path")) if maestro_check.get("path") else None,
    )
    return {"JAVA_HOME": java_home, "PATH": path_value}


def maestro_mcp_server_config(
    java_check: dict[str, object], maestro_check: dict[str, object]
) -> dict[str, object]:
    return {
        "command": "maestro",
        "args": ["mcp"],
        "env": maestro_mcp_environment(java_check, maestro_check),
    }


def maestro_mcp_toml_example(
    java_check: dict[str, object], maestro_check: dict[str, object]
) -> str:
    env = maestro_mcp_environment(java_check, maestro_check)
    return "\n".join(
        [
            "[mcp_servers.maestro]",
            'command = "maestro"',
            'args = ["mcp"]',
            "",
            "[mcp_servers.maestro.env]",
            f'JAVA_HOME = "{toml_string(env["JAVA_HOME"])}"',
            f'PATH = "{toml_string(env["PATH"])}"',
        ]
    )


def maestro_mcp_json_example(
    java_check: dict[str, object], maestro_check: dict[str, object]
) -> str:
    return json.dumps(
        {
            "mcpServers": {
                "maestro": maestro_mcp_server_config(java_check, maestro_check)
            }
        },
        indent=2,
        ensure_ascii=False,
    )


def maestro_mcp_config_examples(
    java_check: dict[str, object], maestro_check: dict[str, object]
) -> dict[str, str]:
    return {
        "genericJson": maestro_mcp_json_example(java_check, maestro_check),
        "toml": maestro_mcp_toml_example(java_check, maestro_check),
    }


def maestro_cli_env(java_check: dict[str, object]) -> dict[str, str] | None:
    java_home = java_check.get("javaHome")
    if not java_home:
        return None
    env = os.environ.copy()
    env["JAVA_HOME"] = str(java_home)
    env["PATH"] = os.pathsep.join(
        unique_path_entries([f"{java_home}/bin", os.environ.get("PATH")])
    )
    return env


def build_maestro_mcp_manual_check(
    java_check: dict[str, object],
    maestro_check: dict[str, object],
) -> dict[str, object]:
    java_home = java_check.get("javaHome")
    maestro_ready = bool(maestro_check.get("installed"))
    server_config = maestro_mcp_server_config(java_check, maestro_check)
    config_examples = maestro_mcp_config_examples(java_check, maestro_check)
    readiness = (
        "Detected Java 17+ and Maestro CLI; adapt the generated command, args, and env values to the active Agent or IDE MCP configuration format."
        if java_home and maestro_ready
        else "Complete Java 17+ and Maestro CLI setup first, then replace any placeholder values before enabling Maestro MCP in the active Agent or IDE."
    )
    return {
        "name": "Maestro MCP",
        "category": "mcp",
        "advice": "Maestro MCP depends on Java 17+, a working Maestro CLI, and explicit MCP environment variables for JAVA_HOME and PATH.",
        "mcpServerConfig": server_config,
        "environment": server_config["env"],
        "configExample": config_examples["genericJson"],
        "configExamples": config_examples,
        "steps": (
            "Confirm Java 17+ is available with `java --version` or `java -version`; prefer the JDK currently used by the local machine when it is 17+, otherwise choose an installed JDK that is 17 or higher before installing a new JDK.",
            "Confirm the Maestro CLI works, for example with `maestro --help` and `maestro test --help`; ensure the MCP PATH includes the directory that contains the `maestro` binary.",
            readiness,
            "Configure the active Agent or IDE MCP settings with `command = maestro`, `args = [mcp]`, and the generated env values. Do not configure only command and args; include `JAVA_HOME` and `PATH` so `maestro mcp` can find Java and Maestro in the MCP server process environment.",
            "Restart or reload the Agent environment so the MCP server is discovered.",
            "Confirm Maestro MCP tools are visible before relying on device inspection, view hierarchy, screenshots, or flow assistance.",
            "If Maestro MCP is unavailable but Maestro CLI works, continue deterministic flow execution through `maestro test` and report MCP separately.",
        ),
    }


REACT_PROJECT_DEPENDENCY_MARKERS = (
    "react",
    "react-dom",
    "next",
    "@vitejs/plugin-react",
    "@vitejs/plugin-react-swc",
    "@remix-run/react",
    "@tanstack/react-router",
    "@tanstack/react-start",
)


def project_dependencies(package_data: dict[str, object] | None) -> dict[str, object]:
    dependencies: dict[str, object] = {}
    if not package_data:
        return dependencies
    for key in (
        "dependencies",
        "devDependencies",
        "optionalDependencies",
        "peerDependencies",
    ):
        value = package_data.get(key)
        if isinstance(value, dict):
            dependencies.update(value)
    return dependencies


def is_react_project(project_root: Path | None) -> bool:
    dependencies = project_dependencies(project_package_json(project_root))
    return any(marker in dependencies for marker in REACT_PROJECT_DEPENDENCY_MARKERS)


def has_shadcn_components_config(project_root: Path | None) -> bool:
    return bool(project_root and (project_root / "components.json").is_file())


def should_check_react_bits_tier(project_root: Path | None) -> bool:
    return bool(
        project_root
        and is_react_project(project_root)
        and has_shadcn_components_config(project_root)
    )


def build_react_bits_tier_manual_check(project_root: Path) -> dict[str, object]:
    components_json = project_root / "components.json"
    return {
        "name": "React Bits tier selection",
        "category": "conditional-project-skill",
        "advice": "A React + shadcn/ui project was detected. Keep the default as shadcn/ui only; ask before adding React Bits Free, Starter, Pro, or Ultimate. Do not print or store any React Bits license key.",
        "detected": {
            "projectRoot": str(project_root),
            "componentsJson": str(components_json),
            "reactProject": True,
        },
        "steps": (
            "Tell the user that shadcn/ui covers normal application components, while React Bits Free or paid tiers are optional sources for more expressive animated components, blocks, or landing sections.",
            "Ask whether this project should stay with shadcn/ui only, add React Bits Free, or use an existing paid Starter / Pro / Ultimate entitlement.",
            "For React Bits Free, install only after the user confirms and a free source or registry has been explicitly configured for this workflow.",
            "For paid tiers, require explicit user confirmation and verify the current environment can read `REACTBITS_LICENSE_KEY` without printing it.",
            "When paid prerequisites are met and the user selects a paid tier, run `npx shadcn@latest add @reactbits-starter/skill --path .agents/skills/react-bits-pro --overwrite --yes` from the project root even when the target Skill already exists, then confirm `.agents/skills/react-bits-pro/SKILL.md` exists before using it.",
            "During reset, preserve the detected React Bits tier and registry; do not replace Free, Starter, Pro, or Ultimate with a different default tier without confirmation.",
        ),
    }


def build_manual_checks(
    java_check: dict[str, object],
    maestro_check: dict[str, object],
    project_root: Path | None,
    gitnexus_check: dict[str, object],
) -> tuple[dict[str, object], ...]:
    checks = [build_gitnexus_mcp_manual_check(gitnexus_check), *BASE_MANUAL_CHECKS]
    checks.insert(3, build_maestro_mcp_manual_check(java_check, maestro_check))
    if project_root and should_check_react_bits_tier(project_root):
        checks.append(build_react_bits_tier_manual_check(project_root))
    return tuple(checks)


def check_java_for_maestro() -> dict[str, object]:
    path = shutil.which("java")
    current_version, current_version_command = (
        java_version_output() if path else (None, "java --version")
    )
    current_major = parse_java_major(current_version)
    java_home, java_home_major_value, java_home_source = select_java_home(path)
    if java_home:
        selected_version, selected_version_command = java_binary_version(
            java_home / "bin" / "java"
        )
        selected_major = parse_java_major(selected_version) or java_home_major_value
    else:
        selected_version, selected_version_command, selected_major = (
            current_version,
            current_version_command,
            current_major,
        )
    installed = bool(java_home and selected_major and selected_major >= JAVA_MIN_MAJOR)
    result: dict[str, object] = {
        "name": "java",
        "category": "runtime",
        "installed": installed,
        "path": str(java_home / "bin" / "java") if installed and java_home else path,
        "currentPath": path,
        "currentVersion": current_version,
        "currentVersionMajor": current_major,
        "currentVersionCommand": current_version_command,
        "javaHome": str(java_home) if java_home else None,
        "javaHomeSource": java_home_source,
        "version": selected_version,
        "versionMajor": selected_major,
        "versionCommand": selected_version_command,
        "globalInstall": f"Install the latest OpenJDK Temurin 21 JDK from {TEMURIN21_RELEASES_URL}",
        "projectInstall": None,
        "advice": "Maestro requires Java 17+. Prefer the local machine's current JDK when it is 17+; if it is missing or lower than 17, use another installed JDK that is 17+ before asking to install a new JDK. Default new installs to the latest OpenJDK Temurin 21 JDK; user-selected versions must be 17 or higher.",
    }
    if not installed and path and current_major and current_major < JAVA_MIN_MAJOR:
        result["incompatibleVersion"] = True
    if (
        installed
        and current_major
        and current_major < JAVA_MIN_MAJOR
        and java_home_source == "alternate-installed-jdk"
    ):
        result["reason"] = (
            "The current `java` is lower than 17, but another installed JDK satisfies Maestro's Java prerequisite."
        )
    return result


def check_maestro_cli(java_check: dict[str, object]) -> dict[str, object]:
    if not java_check.get("installed"):
        return {
            "name": "maestro",
            "category": "cli",
            "installed": False,
            "path": None,
            "version": None,
            "notChecked": True,
            "reason": "Java 17+ is required before Maestro CLI can be checked.",
            "globalInstall": "Install Java 17+ first, then install Maestro CLI with the official Maestro instructions.",
            "projectInstall": None,
            "advice": "Resolve the Java 17+ prerequisite first. Maestro MCP is unavailable until Maestro CLI works.",
        }
    path = shutil.which("maestro")
    env = maestro_cli_env(java_check)
    code, output = (
        command_output(("maestro", "--version"), timeout=10, env=env)
        if path
        else (None, "")
    )
    first_line = output.splitlines()[0] if output else None
    version = (
        first_line
        if code == 0 and first_line and not first_line.lower().startswith("exception")
        else None
    )
    result: dict[str, object] = {
        "name": "maestro",
        "category": "cli",
        "installed": bool(path and version),
        "path": path,
        "binDir": maestro_bin_dir(path),
        "version": version,
        "globalInstall": "Install Maestro CLI with the official Maestro installer or Homebrew tap after user confirmation.",
        "projectInstall": None,
        "advice": "Install Maestro CLI into the local development environment or CI runner after Java 17+ is available. Then configure Maestro MCP separately if needed.",
    }
    if path and not version:
        result["verificationFailed"] = True
        result["verifyCommand"] = "maestro --version"
        result["verifyOutput"] = first_line
    return result


def project_package_json(project_root: Path | None) -> dict[str, object] | None:
    if not project_root:
        return None
    package_json = project_root / "package.json"
    if not package_json.is_file():
        return None
    try:
        return json.loads(package_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def check_playwright_project(project_root: Path | None) -> dict[str, object]:
    package_data = project_package_json(project_root)
    config_paths: list[str] = []
    e2e_paths: list[str] = []
    if project_root:
        for name in (
            "playwright.config.ts",
            "playwright.config.js",
            "playwright.config.mts",
            "playwright.config.cts",
        ):
            candidate = project_root / name
            if candidate.is_file():
                config_paths.append(str(candidate))
        for name in ("tests/e2e", "e2e", "playwright-report", "test-results"):
            candidate = project_root / name
            if candidate.exists():
                e2e_paths.append(str(candidate))

    dependencies: dict[str, object] = {}
    scripts: dict[str, object] = {}
    if package_data:
        for key in ("dependencies", "devDependencies", "optionalDependencies"):
            value = package_data.get(key)
            if isinstance(value, dict):
                dependencies.update(value)
        value = package_data.get("scripts")
        if isinstance(value, dict):
            scripts = value

    has_dependency = "@playwright/test" in dependencies or "playwright" in dependencies
    playwright_scripts = {
        key: value
        for key, value in scripts.items()
        if isinstance(value, str) and "playwright" in value
    }
    installed = bool(has_dependency or config_paths or playwright_scripts)
    has_project_markers = bool(
        has_dependency or config_paths or e2e_paths or playwright_scripts
    )
    not_checked = project_root is None or not has_project_markers
    reason = None
    if project_root is None:
        reason = "No project root was provided, so project-level Playwright readiness was not checked."
    elif not has_project_markers:
        reason = "No package.json, Playwright config, or E2E directory was detected under the target project root."
    return {
        "name": "Playwright CLI",
        "category": "project-cli",
        "installed": installed,
        "applicable": not not_checked,
        "path": str(project_root) if project_root else None,
        "version": dependencies.get("@playwright/test")
        or dependencies.get("playwright"),
        "notChecked": not_checked,
        "reason": reason,
        "configPaths": config_paths,
        "e2ePaths": e2e_paths,
        "scripts": playwright_scripts,
        "globalInstall": "Do not install Playwright globally by default.",
        "projectInstall": "npm init playwright@latest or npm install -D @playwright/test, then npx playwright install",
        "advice": "Playwright CLI is a project-level Web E2E dependency. If Web regression or web-ui-autotest-generator needs it and it is missing, ask the user before installing it into the target project.",
    }


def check_react_bits_project(project_root: Path) -> dict[str, object]:
    applicable = should_check_react_bits_tier(project_root)
    result: dict[str, object] = {
        "applicable": applicable,
        "projectRoot": str(project_root),
        "componentsJson": str(project_root / "components.json") if applicable else None,
        "selectionRequired": applicable,
    }
    if applicable:
        result["manualCheck"] = build_react_bits_tier_manual_check(project_root)
    else:
        result["reason"] = (
            "React Bits applies only when the project is React-based and has "
            "shadcn/ui initialized through components.json."
        )
    return result


def build_project_check(project_root: Path) -> dict[str, object]:
    bootstrap_task, relative_path = find_trellis_bootstrap_task(project_root)
    return {
        "projectRoot": str(project_root),
        "playwright": check_playwright_project(project_root),
        "reactBits": check_react_bits_project(project_root),
        "trellis": {
            "initialized": (project_root / ".trellis").is_dir(),
            "path": str(project_root / ".trellis"),
            "bootstrapRequired": bootstrap_task is not None,
            "bootstrapTask": str(bootstrap_task) if bootstrap_task else None,
            "bootstrapRelativePath": relative_path,
        },
    }


def build_projects_check_results(args: argparse.Namespace) -> dict[str, object]:
    project_roots = resolve_project_roots(args, required=True)
    return {
        "mode": "check-projects",
        "projects": [
            build_project_check(project_root) for project_root in project_roots
        ],
    }


def print_projects_check_results(results: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return
    print("Project checks:")
    for item in results["projects"]:
        print(f"- project root: {item['projectRoot']}")
        playwright = item["playwright"]
        print(
            "  Playwright CLI: "
            + (
                "installed"
                if playwright["installed"]
                else "missing"
                if playwright["applicable"]
                else "not-needed"
            )
        )
        react_bits = item["reactBits"]
        print(
            "  React Bits tier selection: "
            + ("required" if react_bits["applicable"] else "not-needed")
        )
        trellis = item["trellis"]
        print(
            "  Trellis: "
            + ("initialized" if trellis["initialized"] else "not-initialized")
        )
        print(
            "  Bootstrap guidelines: "
            + ("required" if trellis["bootstrapRequired"] else "not-found")
        )


def check_skill(
    name: str, group: str, global_dir: Path, project_dir: Path | None
) -> dict[str, object]:
    locations: list[dict[str, str]] = []
    global_candidate = global_dir / name / "SKILL.md"
    global_valid = (
        external_skill_target_is_valid(global_dir, name)
        if group == "referenced"
        else global_candidate.is_file()
    )
    if global_valid:
        locations.append({"scope": "global", "path": str(global_candidate)})
    if project_dir:
        project_candidate = project_dir / name / "SKILL.md"
        project_valid = (
            external_skill_target_is_valid(project_dir, name)
            if group == "referenced"
            else project_candidate.is_file()
        )
        if project_valid:
            locations.append({"scope": "project", "path": str(project_candidate)})

    return {
        "name": name,
        "category": "skill",
        "group": group,
        "installed": bool(locations),
        "locations": locations,
        "globalTarget": str(global_dir / name / "SKILL.md"),
        "projectTarget": str(project_dir / name / "SKILL.md") if project_dir else None,
        "sourceRepo": EXTERNAL_SKILL_SOURCES.get(name, {}).get("repo")
        if group == "referenced"
        else None,
    }


def report_entry(
    name: str,
    status: str,
    *,
    path: str | None = None,
    version: str | None = None,
    scope: str | None = None,
    reason: str | None = None,
    next_step: str | None = None,
    source_repo: str | None = None,
) -> dict[str, object]:
    entry: dict[str, object] = {"name": name, "status": status}
    optional = {
        "path": path,
        "version": version,
        "scope": scope,
        "reason": reason,
        "nextStep": next_step,
        "sourceRepo": source_repo,
    }
    for key, value in optional.items():
        if value:
            entry[key] = value
    return entry


def cli_failure_reason(item: dict[str, object]) -> str:
    name = str(item["name"])
    if item.get("category") == "project-cli":
        reason = f"No project-level Playwright dependency, config, script, or E2E directory was detected under {item.get('path') or 'the target project root'}."
    elif item.get("incompatibleVersion"):
        reason = f"`{name}` exists at {item.get('path')}, but version {item.get('version')} is lower than the required Java {JAVA_MIN_MAJOR}+ for Maestro."
    elif item.get("notChecked") and item.get("reason"):
        reason = str(item["reason"])
    elif item.get("wrongPackageSuspected"):
        reason = f"`{name}` exists at {item.get('path')}, but `{item.get('verifyCommand')}` failed; it may be a different same-name package."
    elif item.get("verificationFailed"):
        reason = f"`{name}` exists at {item.get('path')}, but `{item.get('verifyCommand')}` failed."
    elif not item.get("path"):
        reason = f"`{name}` command was not found in PATH."
    elif not item.get("version"):
        reason = f"`{name}` exists at {item.get('path')}, but the version command returned no usable output."
    else:
        reason = f"`{name}` did not pass the installer verification checks."

    verify_output = item.get("verifyOutput")
    if verify_output:
        reason += f" First verification output: {verify_output}"
    return reason


def cli_next_step(item: dict[str, object]) -> str:
    if item.get("notChecked") and item.get("advice"):
        return str(item["advice"])
    return (
        "Install or repair the required global tool, then rerun the check. "
        f"Suggested command: {item['globalInstall']}"
    )


def skill_failure_reason(item: dict[str, object]) -> str:
    if item["name"] == "caveman":
        return (
            "No `caveman/SKILL.md` was found in the checked global skills directory: "
            + str(item["globalTarget"])
        )
    targets = [str(item["globalTarget"])]
    if item.get("projectTarget"):
        targets.append(str(item["projectTarget"]))
    return "No `SKILL.md` was found at the checked target path(s): " + ", ".join(
        targets
    )


def skill_next_step(item: dict[str, object]) -> str:
    name = str(item["name"])
    if name == "caveman":
        return "After user confirmation, install the Codex skill with `python scripts/onboard.py install-caveman --yes`, then rerun `check`."
    if item.get("sourceRepo"):
        return (
            "Install the required global Skill from the configured repository with "
            f"`python scripts/onboard.py install-external-skills --skills {name} --scope global --source auto --yes`."
        )
    return "Run `init` or `reset` to install the required global bundled Skills, then rerun `check`."


def skipped_already_installed_entry(
    entry: dict[str, object],
    reason: str,
    next_step: str,
) -> dict[str, object]:
    skipped = dict(entry)
    skipped["status"] = "skipped-already-installed"
    skipped["reason"] = reason
    skipped["nextStep"] = next_step
    return skipped


def build_installation_report(results: dict[str, object]) -> dict[str, object]:
    runtime = results["runtime"]
    installed: dict[str, list[dict[str, object]]] = {
        "runtime": [],
        "tools": [],
        "skills": [],
    }
    skipped_already_installed: dict[str, list[dict[str, object]]] = {
        "runtime": [],
        "tools": [],
        "skills": [],
    }
    failed_or_missing: dict[str, list[dict[str, object]]] = {
        "runtime": [],
        "tools": [],
        "skills": [],
    }
    not_checked: dict[str, list[dict[str, object]]] = {"tools": []}

    for name in ("npm", "node"):
        item = runtime[name]
        entry = report_entry(
            name,
            "installed" if item["installed"] else "missing",
            path=item.get("path"),
            version=item.get("version"),
        )
        if item["installed"]:
            installed["runtime"].append(entry)
            skipped_already_installed["runtime"].append(
                skipped_already_installed_entry(
                    entry,
                    f"`{name}` is already available in PATH.",
                    "Skip bootstrap installation unless the user explicitly requests a reinstall or version change.",
                )
            )
        else:
            entry["reason"] = f"`{name}` is not available in PATH."
            entry["nextStep"] = (
                runtime["advice"]
                if name == "npm"
                else "Install Node.js through nvm or the platform package manager, then rerun `check`."
            )
            failed_or_missing["runtime"].append(entry)

    nvm = runtime["nvm"]
    nvm_entry = report_entry(
        "nvm",
        "installed" if nvm["installed"] else "missing",
        path=nvm.get("path"),
        version=nvm.get("version"),
    )
    if nvm["installed"]:
        installed["runtime"].append(nvm_entry)
        skipped_already_installed["runtime"].append(
            skipped_already_installed_entry(
                nvm_entry,
                "`nvm` is already available.",
                "Skip nvm bootstrap unless the user explicitly requests a reinstall or version manager change.",
            )
        )
    elif not runtime["npm"]["installed"]:
        nvm_entry["reason"] = "npm is missing and nvm is not available for bootstrap."
        nvm_entry["nextStep"] = nvm["advice"]
        failed_or_missing["runtime"].append(nvm_entry)

    if results["cliChecksSkipped"]:
        for spec in CLI_TOOLS:
            not_checked["tools"].append(
                report_entry(
                    str(spec["name"]),
                    "not-checked",
                    reason="npm is not usable yet, so CLI verification was skipped.",
                    next_step="Run `python scripts/onboard.py ensure-npm --yes` after user confirmation, then rerun `check`.",
                )
            )
    for item in results["tools"]:
        if item.get("notChecked"):
            not_checked["tools"].append(
                report_entry(
                    str(item["name"]),
                    "not-checked",
                    reason=str(
                        item.get("reason") or "Prerequisites are not satisfied yet."
                    ),
                    next_step=cli_next_step(item),
                )
            )
            continue
        entry = report_entry(
            str(item["name"]),
            "installed" if item["installed"] else "missing",
            path=item.get("path"),
            version=item.get("version"),
        )
        if item["installed"]:
            installed["tools"].append(entry)
            skipped_already_installed["tools"].append(
                skipped_already_installed_entry(
                    entry,
                    f"`{item['name']}` is already installed and passed the current verification checks.",
                    "Skip CLI installation unless the user explicitly requests reinstall, upgrade, replacement, or project-local installation.",
                )
            )
        else:
            if item.get("incompatibleVersion"):
                entry["status"] = "incompatible"
            elif item.get("wrongPackageSuspected"):
                entry["status"] = "wrong-package-suspected"
            elif item.get("verificationFailed"):
                entry["status"] = "verification-failed"
            entry["reason"] = cli_failure_reason(item)
            entry["nextStep"] = cli_next_step(item)
            failed_or_missing["tools"].append(entry)

    for item in results["skills"]:
        locations = item["locations"]
        if item["installed"]:
            for location in locations:
                installed["skills"].append(
                    report_entry(
                        str(item["name"]),
                        "installed",
                        path=location["path"],
                        scope=location["scope"],
                        source_repo=item.get("sourceRepo"),
                    )
                )
            continue

        failed_or_missing["skills"].append(
            report_entry(
                str(item["name"]),
                "missing",
                reason=skill_failure_reason(item),
                next_step=skill_next_step(item),
                source_repo=item.get("sourceRepo"),
            )
        )

    manual_configuration = []
    for item in results["manualChecks"]:
        manual_item = {
            "name": item["name"],
            "category": item["category"],
            "status": "manual-required",
            "reason": "This item cannot be proven or completed safely by the installer alone.",
            "advice": item["advice"],
            "steps": item["steps"],
        }
        for key in (
            "mcpServerConfig",
            "environment",
            "configExample",
            "configExamples",
        ):
            if item.get(key):
                manual_item[key] = item[key]
        manual_configuration.append(manual_item)

    installed_count = sum(len(items) for items in installed.values())
    skipped_count = sum(len(items) for items in skipped_already_installed.values())
    failed_count = sum(len(items) for items in failed_or_missing.values())
    not_checked_count = sum(len(items) for items in not_checked.values())
    return {
        "summary": {
            "installed": installed_count,
            "skippedAlreadyInstalled": skipped_count,
            "failedOrMissing": failed_count,
            "notChecked": not_checked_count,
            "manualConfiguration": len(manual_configuration),
        },
        "installed": installed,
        "skippedAlreadyInstalled": skipped_already_installed,
        "failedOrMissing": failed_or_missing,
        "notChecked": not_checked,
        "manualConfiguration": manual_configuration,
    }


def build_check_results(args: argparse.Namespace) -> dict[str, object]:
    project_roots = resolve_project_roots(args)
    global_skills_dir, global_skills_dir_source = resolve_global_skills_dir(
        getattr(args, "global_skills_dir", None)
    )
    runtime = check_npm_runtime()
    skills = [
        check_skill(name, "bundled", global_skills_dir, None) for name in BUNDLED_SKILLS
    ]
    skills.extend(
        check_skill(name, "referenced", global_skills_dir, None)
        for name in REFERENCED_SKILLS
    )
    skills.extend(
        check_skill(name, "interaction", global_skills_dir, None)
        for name in INTERACTION_SKILLS
    )

    cli_checks_skipped = not runtime["npm"]["installed"]
    tools = [] if cli_checks_skipped else [check_cli_tool(spec) for spec in CLI_TOOLS]
    gitnexus_check = next(
        (item for item in tools if item.get("name") == "gitnexus"),
        {},
    )
    java_check = check_java_for_maestro()
    maestro_check = check_maestro_cli(java_check)
    tools.append(java_check)
    tools.append(maestro_check)
    manual_checks = build_manual_checks(java_check, maestro_check, None, gitnexus_check)
    project_checks = [
        build_project_check(project_root) for project_root in project_roots
    ]
    missing = {
        "runtime": [] if runtime["npm"]["installed"] else ["npm"],
        "tools": [
            item["name"]
            for item in tools
            if not item["installed"] and not item.get("notChecked")
        ],
        "skills": [item["name"] for item in skills if not item["installed"]],
    }

    results = {
        "mode": "check",
        "platform": platform.system() or sys.platform,
        "paths": {
            "globalSkillsDir": str(global_skills_dir),
            "globalSkillsDirSource": global_skills_dir_source,
            "projectRoots": [str(project_root) for project_root in project_roots],
        },
        "runtime": runtime,
        "cliChecksSkipped": cli_checks_skipped,
        "tools": tools,
        "skills": skills,
        "manualChecks": manual_checks,
        "projectChecks": project_checks,
        "missing": missing,
    }
    results["installationReport"] = build_installation_report(results)
    return results


def print_report_entries(
    entries: list[dict[str, object]], empty_message: str = "- none"
) -> None:
    if not entries:
        print(empty_message)
        return
    for item in entries:
        detail = []
        if item.get("scope"):
            detail.append(f"scope={item['scope']}")
        if item.get("path"):
            detail.append(f"path={item['path']}")
        if item.get("version"):
            detail.append(f"version={item['version']}")
        suffix = f" ({', '.join(detail)})" if detail else ""
        print(f"- {item['name']}: {item['status']}{suffix}")
        if item.get("sourceRepo"):
            print(f"  source repo: {item['sourceRepo']}")
        if item.get("reason"):
            print(f"  reason: {item['reason']}")
        if item.get("nextStep"):
            print(f"  next: {item['nextStep']}")


def print_indented_block(value: object, indent: int = 4) -> None:
    prefix = " " * indent
    for line in str(value).splitlines():
        print(f"{prefix}{line}")


def print_config_examples(item: dict[str, object]) -> None:
    examples = item.get("configExamples")
    if isinstance(examples, dict) and examples:
        print("  config examples:")
        for name, example in examples.items():
            label = "generic MCP JSON" if name == "genericJson" else name
            print(f"  {label}:")
            print_indented_block(example)
        return
    if item.get("configExample"):
        print("  config example:")
        print_indented_block(item["configExample"])


def print_installation_report(
    report: dict[str, object], heading: str = "Installation report"
) -> None:
    print(f"\n{heading}:")
    summary = report["summary"]
    print(
        "Summary: "
        f"installed={summary['installed']}, "
        f"skipped_already_installed={summary['skippedAlreadyInstalled']}, "
        f"failed_or_missing={summary['failedOrMissing']}, "
        f"not_checked={summary['notChecked']}, "
        f"manual_configuration={summary['manualConfiguration']}"
    )

    print("\nInstalled runtime:")
    print_report_entries(report["installed"]["runtime"])
    print("\nInstalled CLI tools:")
    print_report_entries(report["installed"]["tools"])
    print("\nInstalled skills:")
    print_report_entries(report["installed"]["skills"])

    print("\nSkipped because already installed - runtime:")
    print_report_entries(report["skippedAlreadyInstalled"]["runtime"])
    print("\nSkipped because already installed - CLI tools:")
    print_report_entries(report["skippedAlreadyInstalled"]["tools"])

    print("\nFailed or missing runtime:")
    print_report_entries(report["failedOrMissing"]["runtime"])
    print("\nFailed or missing CLI tools:")
    print_report_entries(report["failedOrMissing"]["tools"])
    print("\nFailed or missing skills:")
    print_report_entries(report["failedOrMissing"]["skills"])

    print("\nNot checked:")
    print_report_entries(report["notChecked"]["tools"])

    print("\nManual configuration required:")
    manual_items = report["manualConfiguration"]
    if not manual_items:
        print("- none")
    for item in manual_items:
        print(f"- {item['name']} [{item['category']}]: {item['status']}")
        print(f"  reason: {item['reason']}")
        print(f"  advice: {item['advice']}")
        print_config_examples(item)
        print("  steps:")
        for index, step in enumerate(item["steps"], start=1):
            print(f"  {index}. {step}")


def print_check_results(results: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    print("Preflight check")
    print(f"Platform: {results['platform']}")
    paths = results["paths"]
    print(f"Global skills: {paths['globalSkillsDir']}")
    for project_root in paths["projectRoots"]:
        print(f"Project root: {project_root}")

    runtime = results["runtime"]
    print("\nRuntime preflight:")
    npm = runtime["npm"]
    node = runtime["node"]
    nvm = runtime["nvm"]
    npm_status = "installed" if npm["installed"] else "missing"
    node_status = "installed" if node["installed"] else "missing"
    nvm_status = "installed" if nvm["installed"] else "missing"
    print(
        f"- npm: {npm_status}"
        + (f" at {npm['path']} ({npm['version']})" if npm.get("path") else "")
    )
    print(
        f"- node: {node_status}"
        + (f" at {node['path']} ({node['version']})" if node.get("path") else "")
    )
    print(
        f"- nvm: {nvm_status}" + (f" ({nvm['version']})" if nvm.get("version") else "")
    )
    if not npm["installed"]:
        print(
            "  action: ask the user to install npm via nvm, then run `python scripts/onboard.py ensure-npm --yes`."
        )

    print("\nCLI tools:")
    if results["cliChecksSkipped"]:
        print(
            "- npm-backed tools skipped: npm is not usable yet, so rtk / trellis / gitnexus checks have not run."
        )
    for item in results["tools"]:
        status = "installed" if item["installed"] else "missing"
        if item.get("notChecked"):
            status = "not-checked"
        elif item.get("incompatibleVersion"):
            status = "incompatible"
        elif item.get("wrongPackageSuspected"):
            status = "wrong-package-suspected"
        elif item.get("verificationFailed"):
            status = "verification-failed"
        detail = f" ({item['version']})" if item.get("version") else ""
        path = f" at {item['path']}" if item.get("path") else ""
        print(f"- {item['name']}: {status}{path}{detail}")
        if item.get("verifyCommand"):
            verified = "passed" if item.get("rtkGainVerified") else "not passed"
            print(f"  verify: {item['verifyCommand']} ({verified})")
        if item.get("reason"):
            print(f"  reason: {item['reason']}")
        if not item["installed"]:
            print(f"  global: {item['globalInstall']}")
            if item.get("projectInstall"):
                print(f"  project: {item['projectInstall']}")
            print(f"  advice: {item['advice']}")

    print("\nSkills:")
    for item in results["skills"]:
        status = "installed" if item["installed"] else "missing"
        print(f"- {item['name']} [{item['group']}]: {status}")
        for location in item["locations"]:
            print(f"  {location['scope']}: {location['path']}")
        if not item["installed"]:
            print(f"  global target: {item['globalTarget']}")
            if item["projectTarget"]:
                print(f"  project target: {item['projectTarget']}")
            if item.get("sourceRepo"):
                print(f"  source repo: {item['sourceRepo']}")

    print("\nManual checks:")
    for item in results["manualChecks"]:
        print(f"- {item['name']} [{item['category']}]: {item['advice']}")
        print_config_examples(item)

    if results["projectChecks"]:
        print("")
        print_projects_check_results(
            {"mode": "check-projects", "projects": results["projectChecks"]},
            False,
        )

    missing = results["missing"]
    if missing["runtime"] or missing["tools"] or missing["skills"]:
        print("\nMissing summary:")
        if missing["runtime"]:
            print("- runtime: " + ", ".join(missing["runtime"]))
        if missing["tools"]:
            print("- tools: " + ", ".join(missing["tools"]))
        if missing["skills"]:
            print("- skills: " + ", ".join(missing["skills"]))
        print(
            "Install required global items before init/reset; project-only items remain conditional per project root."
        )
    else:
        print("\nMissing summary: none")

    print_installation_report(results["installationReport"])


def backup_path(target: Path) -> Path:
    today = dt.date.today().isoformat()
    index = 1
    while True:
        candidate = target.with_name(f"{target.name}.{today}-{index}")
        if not candidate.exists():
            return candidate
        index += 1


def remove_existing_target(target: Path) -> None:
    if target.is_dir() and not target.is_symlink():
        shutil.rmtree(target)
    else:
        target.unlink()


def compare_tree(
    source: Path, target: Path, ignored_names: set[str] | None = None
) -> list[str]:
    failures: list[str] = []
    ignored = ignored_names or set()
    for item in source.rglob("*"):
        rel = item.relative_to(source)
        if any(part in ignored for part in rel.parts):
            continue
        if item.name.endswith(".pyc"):
            continue
        other = target / rel
        if item.is_dir():
            if not other.is_dir():
                failures.append(str(rel))
            continue
        if not other.is_file() or not filecmp.cmp(item, other, shallow=False):
            failures.append(str(rel))
    return failures


def missing_file_lines(source_text: str, target_text: str) -> list[str]:
    target_lines = target_text.splitlines()
    if target_lines:
        target_lines[0] = target_lines[0].removeprefix("\ufeff")
    existing_lines = set(target_lines)
    missing_lines: list[str] = []
    pending_separator = False

    for line in source_text.splitlines():
        if not line:
            pending_separator = bool(missing_lines)
            continue
        if line in existing_lines:
            continue
        if pending_separator and missing_lines[-1] != "":
            missing_lines.append("")
        missing_lines.append(line)
        existing_lines.add(line)
        pending_separator = False

    return missing_lines


def ensure_file_contains(source: Path, target: Path) -> str:
    source_text = source.read_text(encoding="utf-8")

    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        if not source_text.endswith("\n"):
            source_text += "\n"
        target.write_text(source_text, encoding="utf-8")
        return "created"

    existing = target.read_text(encoding="utf-8")
    missing_lines = missing_file_lines(source_text, existing)
    if not missing_lines:
        return "skipped-already-present"

    prefix = "" if not existing or existing.endswith("\n") else "\n"
    separator = "\n" if existing.strip() else ""
    addition = "\n".join(missing_lines) + "\n"
    target.write_text(
        f"{existing}{prefix}{separator}{addition}",
        encoding="utf-8",
    )
    return "updated"


def copy_operation(operation: Operation) -> str:
    if operation.same_location:
        return "skipped-same-location"
    operation.target.parent.mkdir(parents=True, exist_ok=True)
    if operation.kind == "ensure-file-block":
        return ensure_file_contains(operation.source, operation.target)
    if operation.kind == "file":
        shutil.copy2(operation.source, operation.target)
        return "copied"
    if operation.target.exists():
        remove_existing_target(operation.target)
        action = "overwritten-without-backup"
    else:
        action = "copied"
    shutil.copytree(operation.source, operation.target)
    return action


def verify_operation(operation: Operation) -> list[str]:
    if operation.same_location:
        return []
    if operation.kind == "ensure-file-block":
        if not operation.target.is_file():
            return [operation.label]
        source_text = operation.source.read_text(encoding="utf-8")
        target_text = operation.target.read_text(encoding="utf-8")
        if not missing_file_lines(source_text, target_text):
            return []
        return [operation.label]
    if operation.kind == "file":
        if operation.target.is_file() and filecmp.cmp(
            operation.source, operation.target, shallow=False
        ):
            return []
        return [operation.label]
    return compare_tree(operation.source, operation.target)


def canonical_external_skill_name(name: str) -> str:
    return MATTPOCOCK_LEGACY_RENAMES.get(name, name)


def legacy_external_skill_names_for(canonical_name: str) -> list[str]:
    return [
        legacy_name
        for legacy_name, replacement_name in MATTPOCOCK_LEGACY_RENAMES.items()
        if replacement_name == canonical_name
    ]

def filesystem_entry_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()

def legacy_external_skill_identity_error(target: Path, legacy_name: str) -> str | None:
    if not target.is_dir() or target.is_symlink():
        return f"legacy target is not a regular Skill directory: {target}"
    skill_md = target / "SKILL.md"
    if not skill_md.is_file() or skill_md.is_symlink():
        return f"legacy target has no regular SKILL.md: {target}"
    actual_name = read_skill_frontmatter_name(skill_md)
    if actual_name != legacy_name:
        return (
            f"legacy Skill identity conflict: expected {legacy_name}, "
            f"found {actual_name or '<missing>'}"
        )
    return None


def external_skill_dependency_closure(skill_names: list[str]) -> list[str]:
    selected: list[str] = []

    def add(name: str) -> None:
        if name in selected:
            return
        selected.append(name)
        for dependency in MATTPOCOCK_REQUIRED_DEPENDENCIES.get(name, ()):
            add(dependency)

    for skill_name in skill_names:
        add(skill_name)
    return selected


def parse_skill_names(args: argparse.Namespace) -> list[str]:
    if getattr(args, "all", False):
        return external_skill_dependency_closure(list(EXTERNAL_SKILL_SOURCES.keys()))

    raw = getattr(args, "skills", None)
    if not raw:
        raise SystemExit("--skills or --all is required")

    requested = [item.strip() for item in raw.split(",") if item.strip()]
    if "all" in requested:
        return external_skill_dependency_closure(list(EXTERNAL_SKILL_SOURCES.keys()))

    removed = [name for name in requested if name in MATTPOCOCK_REMOVED_SKILLS]
    if removed:
        details = "; ".join(
            f"{name}: {MATTPOCOCK_REMOVED_SKILLS[name]}" for name in removed
        )
        raise SystemExit(f"Removed external skill(s): {details}")

    canonical_requested = [canonical_external_skill_name(name) for name in requested]

    unknown = [
        name for name in canonical_requested if name not in EXTERNAL_SKILL_SOURCES
    ]
    if unknown:
        known = ", ".join(EXTERNAL_SKILL_SOURCES.keys())
        raise SystemExit(
            f"Unknown external skill(s): {', '.join(unknown)}. Known: {known}"
        )

    unique: list[str] = []
    for name in external_skill_dependency_closure(canonical_requested):
        if name not in unique:
            unique.append(name)
    return unique


def resolve_install_skills_dir(args: argparse.Namespace) -> Path:
    return resolve_global_skills_dir(args.global_skills_dir)[0]


def external_install_plan(
    args: argparse.Namespace, selected: list[str], target_dir: Path
) -> dict[str, object]:
    legacy_targets = [
        {
            "name": legacy_name,
            "replacement": name,
            "target": str(target_dir / legacy_name),
            "targetExists": (target_dir / legacy_name).exists(),
        }
        for name in selected
        for legacy_name in legacy_external_skill_names_for(name)
        if (target_dir / legacy_name).exists()
    ]
    return {
        "mode": "install-external-skills",
        "scope": args.scope,
        "requestedSource": args.source,
        "targetDir": str(target_dir),
        "forceOverwriteExisting": True,
        "backupExistingTargets": "temporary-rollback",
        "transactionalInstall": True,
        "replaceFlagProvided": bool(args.replace),
        "removeLegacyAfterCanonicalCommit": legacy_targets,
        "skills": [
            {
                "name": name,
                "repo": EXTERNAL_SKILL_SOURCES[name]["repo"],
                "target": str(target_dir / name),
                "targetExists": (target_dir / name).exists(),
            }
            for name in selected
        ],
    }


def print_external_install_plan(plan: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return

    print("External skill install plan")
    print(f"Scope: {plan['scope']}")
    print(f"Requested source: {plan['requestedSource']}")
    print(f"Target skills dir: {plan['targetDir']}")
    print(
        "Transactional install: yes, existing targets use a temporary rollback backup"
    )
    legacy_items = plan.get("removeLegacyAfterCanonicalCommit")
    if isinstance(legacy_items, list) and legacy_items:
        print("Legacy targets removed after canonical commit:")
        for item in legacy_items:
            if not isinstance(item, dict):
                raise RuntimeError(
                    "external install legacy plan entry must be an object"
                )
            entry = cast(dict[str, object], item)
            status = "exists" if entry["targetExists"] else "missing"
            print(
                f"- {entry['name']} -> {entry['replacement']}: "
                f"{entry['target']} ({status})"
            )
    skill_items = plan.get("skills")
    if not isinstance(skill_items, list):
        raise RuntimeError("external install plan skills must be a list")
    for item in skill_items:
        if not isinstance(item, dict):
            raise RuntimeError("external install skill plan entry must be an object")
        entry = cast(dict[str, object], item)
        status = "exists" if entry["targetExists"] else "missing"
        print(f"- {entry['name']}: {entry['target']} ({status})")
        print(f"  source: {entry['repo']}")


def discover_skill_dirs(repo_root: Path) -> list[Path]:
    dirs: list[Path] = []
    for skill_md in repo_root.rglob("SKILL.md"):
        try:
            rel = skill_md.relative_to(repo_root)
        except ValueError:
            continue
        if ".git" in rel.parts:
            continue
        dirs.append(skill_md.parent)
    return dirs


def resolve_contained_relative_path(root: Path, value: object, field: str) -> Path:
    raw = str(value or "")
    relative = Path(raw)
    if not raw or relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError(
            f"{field} must be a non-empty relative path without '..': {raw or '<missing>'}"
        )
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise RuntimeError(
            f"{field} must stay within its declared root: {raw}"
        ) from exc
    return candidate


def source_dir_for_external_skill(repo_root: Path, skill_name: str) -> Path:
    spec = EXTERNAL_SKILL_SOURCES[skill_name]
    configured_subpath = spec.get("subpath")
    if configured_subpath:
        candidate = resolve_contained_relative_path(
            repo_root, configured_subpath, f"configured subpath for {skill_name}"
        )
        if (candidate / "SKILL.md").is_file():
            return candidate
        raise RuntimeError(
            f"configured subpath for {skill_name} does not contain SKILL.md: {configured_subpath}"
        )

    subpath = MATTPOCOCK_SKILL_SUBPATHS.get(skill_name)
    if subpath:
        candidate = resolve_contained_relative_path(
            repo_root, subpath, f"fallback subpath for {skill_name}"
        )
        if (candidate / "SKILL.md").is_file():
            return candidate

    aliases = {str(alias) for alias in spec["aliases"]}
    candidates = discover_skill_dirs(repo_root)
    if not candidates:
        raise RuntimeError("no SKILL.md files found in cloned repository")

    by_dir_name = [candidate for candidate in candidates if candidate.name in aliases]
    if len(by_dir_name) == 1:
        return by_dir_name[0]

    by_frontmatter = [
        candidate
        for candidate in candidates
        if read_skill_frontmatter_name(candidate / "SKILL.md") in aliases
    ]
    if len(by_frontmatter) == 1:
        return by_frontmatter[0]

    repo = str(spec["repo"])
    if len(EXTERNAL_REPO_TO_SKILLS[repo]) == 1 and len(candidates) == 1:
        return candidates[0]

    rel_candidates = ", ".join(
        str(candidate.relative_to(repo_root)) for candidate in candidates[:20]
    )
    if len(candidates) > 20:
        rel_candidates += ", ..."
    raise RuntimeError(
        f"could not uniquely locate {skill_name}; candidates: {rel_candidates}"
    )


def external_tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        candidate for candidate in root.rglob("*") if candidate.is_file()
    ):
        if path.is_symlink():
            raise RuntimeError(
                f"external Skill contains an unsupported symlink: {path.relative_to(root)}"
            )
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()

def prune_unmanaged_stable_skill_directories(
    manifest: dict[str, object], stable_root: Path
) -> list[str]:
    skills = manifest.get("skills")
    if not isinstance(skills, dict):
        raise RuntimeError("stable External Skills manifest skills must be an object")

    unresolved_skills_root = stable_root / "skills"
    if (
        not unresolved_skills_root.is_dir()
        or unresolved_skills_root.is_symlink()
    ):
        raise RuntimeError("stable External Skills skills directory is invalid")
    skills_root = unresolved_skills_root.resolve()

    expected: set[str] = set()
    for skill_name, entry in skills.items():
        if not isinstance(skill_name, str) or not isinstance(entry, dict):
            raise RuntimeError("stable External Skills manifest contains invalid skill metadata")
        target = resolve_contained_relative_path(
            stable_root,
            entry.get("stablePath"),
            f"stablePath for {skill_name}",
        ).resolve()
        try:
            relative = target.relative_to(skills_root)
        except ValueError as exc:
            raise RuntimeError(
                f"stablePath for {skill_name} must be under skills/"
            ) from exc
        if len(relative.parts) != 1:
            raise RuntimeError(
                f"stablePath for {skill_name} must be a direct child of skills/"
            )
        expected.add(relative.name)

    pruned: list[str] = []
    for candidate in unresolved_skills_root.iterdir():
        if candidate.name in expected:
            continue
        remove_existing_target(candidate)
        pruned.append(candidate.name)
    return sorted(pruned)


def validate_external_skill_source(skill_name: str, source: Path) -> None:
    if not source.is_dir() or source.is_symlink():
        raise RuntimeError(
            f"external Skill source is not a regular directory: {source}"
        )
    skill_md = source / "SKILL.md"
    if not skill_md.is_file() or skill_md.is_symlink():
        raise RuntimeError(
            f"external Skill {skill_name} does not contain a regular SKILL.md"
        )
    frontmatter_name = read_skill_frontmatter_name(skill_md)
    if frontmatter_name != skill_name:
        raise RuntimeError(
            f"external Skill {skill_name} frontmatter name is {frontmatter_name or '<missing>'}"
        )
    for path in source.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(
                f"external Skill {skill_name} contains an unsupported symlink: {path.relative_to(source)}"
            )


def external_skill_target_is_valid(skills_root: Path, skill_name: str) -> bool:
    try:
        validate_external_skill_source(skill_name, skills_root / skill_name)
    except (OSError, RuntimeError):
        return False
    return True


def load_external_stable_manifest() -> dict[str, object]:
    try:
        manifest = json.loads(EXTERNAL_STABLE_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"cannot read stable External Skills manifest: {exc}"
        ) from exc
    if manifest.get("schemaVersion") != 1:
        raise RuntimeError("stable External Skills manifest schemaVersion must be 1")
    repositories = manifest.get("repositories")
    skills = manifest.get("skills")
    if not isinstance(repositories, dict) or not isinstance(skills, dict):
        raise RuntimeError(
            "stable External Skills manifest must contain repositories and skills objects"
        )
    if set(skills) != set(EXTERNAL_SKILL_SOURCES):
        missing = sorted(set(EXTERNAL_SKILL_SOURCES) - set(skills))
        extra = sorted(set(skills) - set(EXTERNAL_SKILL_SOURCES))
        raise RuntimeError(
            "stable External Skills manifest does not match the canonical set; "
            f"missing={missing}, extra={extra}"
        )
    validate_external_stable_metadata(manifest, EXTERNAL_STABLE_ROOT)
    return manifest


def validate_external_stable_metadata(
    manifest: dict[str, object], stable_root: Path
) -> None:
    repositories = manifest.get("repositories")
    if not isinstance(repositories, dict):
        raise RuntimeError(
            "stable External Skills manifest repositories must be an object"
        )
    for repository_id, repository in repositories.items():
        if not isinstance(repository, dict):
            raise RuntimeError(
                f"stable repository metadata is invalid: {repository_id}"
            )
        revision = str(repository.get("revision") or "")
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise RuntimeError(
                f"stable repository revision is invalid: {repository_id}"
            )
        license_files = repository.get("licenseFiles")
        if not isinstance(license_files, list) or not license_files:
            raise RuntimeError(
                f"stable repository has no licenseFiles: {repository_id}"
            )
        for license_entry in license_files:
            if not isinstance(license_entry, dict):
                raise RuntimeError(
                    f"stable repository has an invalid license entry: {repository_id}"
                )
            source = str(license_entry.get("source") or "")
            stable_path = str(license_entry.get("stablePath") or "")
            if not source or not stable_path:
                raise RuntimeError(
                    f"stable repository license file is missing or invalid: {repository_id}/{stable_path}"
                )
            license_path = resolve_contained_relative_path(
                stable_root,
                stable_path,
                f"license stablePath for {repository_id}",
            )
            if not license_path.is_file():
                raise RuntimeError(
                    f"stable repository license file is missing or invalid: {repository_id}/{stable_path}"
                )


def stable_external_skill_source(
    manifest: dict[str, object],
    skill_name: str,
    stable_root: Path = EXTERNAL_STABLE_ROOT,
) -> tuple[Path, str, str]:
    skills = manifest["skills"]
    repositories = manifest["repositories"]
    assert isinstance(skills, dict)
    assert isinstance(repositories, dict)
    skill = skills.get(skill_name)
    if not isinstance(skill, dict):
        raise RuntimeError(f"stable manifest has no entry for {skill_name}")
    repository_id = skill.get("repository")
    repository = repositories.get(repository_id)
    if not isinstance(repository_id, str) or not isinstance(repository, dict):
        raise RuntimeError(f"stable manifest repository is invalid for {skill_name}")
    source = resolve_contained_relative_path(
        stable_root,
        skill.get("stablePath"),
        f"stablePath for {skill_name}",
    )
    validate_external_skill_source(skill_name, source)
    expected_digest = str(skill.get("treeSha256") or "")
    actual_digest = external_tree_sha256(source)
    if not expected_digest or actual_digest != expected_digest:
        raise RuntimeError(
            f"stable External Skill checksum mismatch for {skill_name}: "
            f"expected {expected_digest or '<missing>'}, got {actual_digest}"
        )
    revision = str(repository.get("revision") or "")
    repo = str(repository.get("url") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise RuntimeError(
            f"stable External Skill revision is invalid for {skill_name}"
        )
    if repo != str(EXTERNAL_SKILL_SOURCES[skill_name]["repo"]):
        raise RuntimeError(
            f"stable External Skill repository does not match configured source for {skill_name}"
        )
    return source, revision, str(manifest.get("stableSet") or "")


def clone_repo(repo: str, destination: Path) -> tuple[bool, str]:
    if not shutil.which("git"):
        return False, "git command not found"

    try:
        completed = subprocess.run(
            ("git", "clone", "--depth", "1", repo, str(destination)),
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        return False, "git clone timed out after 180 seconds"
    except OSError as exc:
        return False, str(exc)
    if completed.returncode == 0:
        return True, ""
    message = (completed.stderr or completed.stdout).strip()
    return False, message or f"git clone exited with {completed.returncode}"


def cloned_repo_revision(repo_root: Path) -> str:
    try:
        completed = subprocess.run(
            ("git", "-C", str(repo_root), "rev-parse", "HEAD"),
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise RuntimeError(
            f"cannot determine cloned repository revision: {exc}"
        ) from exc
    revision = completed.stdout.strip()
    if completed.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", revision):
        message = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(
            message or "cloned repository did not return a full commit revision"
        )
    return revision


def clone_repo_at_revision(
    repo: str, revision: str, destination: Path
) -> tuple[bool, str]:
    if not shutil.which("git"):
        return False, "git command not found"
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        return False, "revision must be a full 40-character lowercase commit SHA"
    commands = (
        ("git", "init", str(destination)),
        ("git", "-C", str(destination), "remote", "add", "origin", repo),
        ("git", "-C", str(destination), "fetch", "--depth", "1", "origin", revision),
        ("git", "-C", str(destination), "checkout", "--detach", "FETCH_HEAD"),
    )
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired:
            return False, f"command timed out after 180 seconds: {shlex.join(command)}"
        except OSError as exc:
            return False, str(exc)
        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout).strip()
            return False, message or f"command failed: {shlex.join(command)}"
    return True, ""


def copy_external_skill(source: Path, target: Path) -> tuple[str, bool, str | None]:
    replaced_existing = target.exists()
    if target.exists():
        remove_existing_target(target)

    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(
            source,
            target,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
        )
    except OSError as exc:
        return "failed", replaced_existing, str(exc)

    failures = compare_tree(source, target, {".git", "__pycache__"})
    if failures:
        return (
            "failed",
            replaced_existing,
            "verification failed: " + ", ".join(failures[:20]),
        )
    return ("replaced" if replaced_existing else "installed"), replaced_existing, None


def resolve_external_install_sources(
    selected: list[str], requested_source: str, workspace: Path
) -> dict[str, dict[str, object]]:
    manifest = (
        load_external_stable_manifest()
        if requested_source in {"auto", "stable"}
        else None
    )
    repo_groups: dict[str, list[str]] = {}
    for name in selected:
        repo = str(EXTERNAL_SKILL_SOURCES[name]["repo"])
        repo_groups.setdefault(repo, []).append(name)

    resolved: dict[str, dict[str, object]] = {}
    for index, (repo, names) in enumerate(repo_groups.items(), start=1):
        if requested_source == "upstream":
            try:
                repo_root = workspace / f"repo-{index}"
                ok, clone_error = clone_repo(repo, repo_root)
                if not ok:
                    raise RuntimeError(clone_error)
                revision = cloned_repo_revision(repo_root)
                upstream_sources: dict[str, Path] = {}
                for name in names:
                    source = source_dir_for_external_skill(repo_root, name)
                    validate_external_skill_source(name, source)
                    upstream_sources[name] = source
                for name, source in upstream_sources.items():
                    resolved[name] = {
                        "source": source,
                        "repo": repo,
                        "sourceUsed": "upstream",
                        "sourceRevision": revision,
                        "stableSet": None,
                        "fallbackReason": None,
                    }
                continue
            except (OSError, RuntimeError) as exc:
                raise RuntimeError(
                    f"upstream External Skill group failed for {repo}: {exc}"
                ) from exc

        assert manifest is not None
        stable_group: dict[str, tuple[Path, str, str]] = {}
        for name in names:
            stable_group[name] = stable_external_skill_source(manifest, name)
        for name, (source, revision, stable_set) in stable_group.items():
            resolved[name] = {
                "source": source,
                "repo": repo,
                "sourceUsed": "stable",
                "sourceRevision": revision,
                "stableSet": stable_set,
                "fallbackReason": None,
            }
    return resolved


def stage_external_skills(
    selected: list[str], resolved: dict[str, dict[str, object]], target_dir: Path
) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".sbtd-external-staging-", dir=target_dir))
    try:
        for name in selected:
            source = Path(str(resolved[name]["source"]))
            destination = staging / name
            shutil.copytree(
                source,
                destination,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            validate_external_skill_source(name, destination)
            failures = compare_tree(source, destination, {".git", "__pycache__"})
            if failures:
                raise RuntimeError(
                    f"staging verification failed for {name}: "
                    + ", ".join(failures[:20])
                )
        return staging
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def commit_external_skill_transaction(
    selected: list[str],
    resolved: dict[str, dict[str, object]],
    target_dir: Path,
    staging: Path,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    legacy_names: list[str] = []
    for name in selected:
        for legacy_name in legacy_external_skill_names_for(name):
            if legacy_name not in legacy_names:
                legacy_names.append(legacy_name)
    identity_conflicts = [
        {
            "name": legacy_name,
            "replacement": canonical_external_skill_name(legacy_name),
            "target": str(target_dir / legacy_name),
            "status": "failed",
            "phase": "preflight-legacy-identity",
            "error": identity_error,
        }
        for legacy_name in legacy_names
        if filesystem_entry_exists(target_dir / legacy_name)
        if (
            identity_error := legacy_external_skill_identity_error(
                target_dir / legacy_name, legacy_name
            )
        )
        is not None
    ]
    if identity_conflicts:
        shutil.rmtree(staging, ignore_errors=True)
        return identity_conflicts, {
            "status": "aborted-before-commit",
            "rolledBack": False,
            "rollbackErrors": [],
            "rollbackPath": None,
        }

    rollback = Path(
        tempfile.mkdtemp(prefix=".sbtd-external-rollback-", dir=target_dir)
    )

    existed = {name: filesystem_entry_exists(target_dir / name) for name in selected}
    moved: list[tuple[Path, Path]] = []
    committed: list[Path] = []
    results: list[dict[str, object]] = []
    rollback_errors: list[str] = []
    retain_rollback = False
    try:
        for name in (*selected, *legacy_names):
            target = target_dir / name
            if not filesystem_entry_exists(target):
                continue
            backup = rollback / name
            shutil.move(str(target), str(backup))
            moved.append((target, backup))

        for name in selected:
            target = target_dir / name
            shutil.move(str(staging / name), str(target))
            committed.append(target)
            source_info = resolved[name]
            result = {
                "name": name,
                "repo": source_info["repo"],
                "target": str(target),
                "status": "replaced" if existed[name] else "installed",
                "phase": "commit",
                "replacedExisting": existed[name],
                "sourceUsed": source_info["sourceUsed"],
                "sourceRevision": source_info["sourceRevision"],
                "stableSet": source_info.get("stableSet"),
                "fallbackReason": source_info.get("fallbackReason"),
            }
            results.append(result)

        for legacy_name in legacy_names:
            if (rollback / legacy_name).exists():
                results.append(
                    {
                        "name": legacy_name,
                        "replacement": canonical_external_skill_name(legacy_name),
                        "target": str(target_dir / legacy_name),
                        "status": "removed",
                        "phase": "remove-legacy-after-commit",
                    }
                )
        transaction = {
            "status": "committed",
            "rolledBack": False,
            "rollbackErrors": [],
            "rollbackPath": None,
        }
        return results, transaction
    except Exception as exc:  # noqa: BLE001 - rollback must cover every local commit failure.
        for target in reversed(committed):
            try:
                remove_existing_target(target)
            except Exception as rollback_exc:  # noqa: BLE001 - aggregate rollback failures.
                rollback_errors.append(f"remove {target}: {rollback_exc}")
        for target, backup in reversed(moved):
            try:
                if target.exists():
                    remove_existing_target(target)
                shutil.move(str(backup), str(target))
            except Exception as rollback_exc:  # noqa: BLE001 - aggregate rollback failures.
                rollback_errors.append(f"restore {target}: {rollback_exc}")
        results = [
            {
                "name": name,
                "repo": resolved[name]["repo"],
                "target": str(target_dir / name),
                "status": "failed",
                "phase": "commit",
                "sourceUsed": resolved[name]["sourceUsed"],
                "sourceRevision": resolved[name]["sourceRevision"],
                "stableSet": resolved[name].get("stableSet"),
                "fallbackReason": resolved[name].get("fallbackReason"),
                "error": str(exc),
            }
            for name in selected
        ]
        retain_rollback = bool(rollback_errors)
        return results, {
            "status": "rollback-failed" if rollback_errors else "rolled-back",
            "rolledBack": True,
            "rollbackErrors": rollback_errors,
            "rollbackPath": str(rollback) if retain_rollback else None,
        }
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        if not retain_rollback:
            shutil.rmtree(rollback, ignore_errors=True)


def remove_legacy_external_targets(
    target_dir: Path,
    selected: list[str],
    extra_legacy_names: list[str] | None = None,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    legacy_names: list[str] = []
    for name in selected:
        for legacy_name in legacy_external_skill_names_for(name):
            if legacy_name not in legacy_names:
                legacy_names.append(legacy_name)
    for legacy_name in extra_legacy_names or []:
        if legacy_name not in legacy_names:
            legacy_names.append(legacy_name)

    for legacy_name in legacy_names:
        target = target_dir / legacy_name
        if not filesystem_entry_exists(target):
            continue
        identity_error = legacy_external_skill_identity_error(target, legacy_name)
        if identity_error is not None:
            results.append(
                {
                    "name": legacy_name,
                    "replacement": canonical_external_skill_name(legacy_name),
                    "target": str(target),
                    "status": "failed",
                    "phase": "preflight-legacy-identity",
                    "error": identity_error,
                }
            )
            continue
        try:
            remove_existing_target(target)
            results.append(
                {
                    "name": legacy_name,
                    "replacement": canonical_external_skill_name(legacy_name),
                    "target": str(target),
                    "status": "removed",
                    "phase": "remove-legacy",
                }
            )
        except Exception as exc:  # noqa: BLE001 - keep cleanup report per target.
            results.append(
                {
                    "name": legacy_name,
                    "replacement": canonical_external_skill_name(legacy_name),
                    "target": str(target),
                    "status": "failed",
                    "phase": "remove-legacy",
                    "error": str(exc),
                }
            )
    return results


def scoped_skills_root(args: argparse.Namespace) -> Path:
    return resolve_global_skills_dir(args.global_skills_dir)[0]


def external_migration_timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def external_migration_backup_root(skills_root: Path) -> Path:
    return skills_root.with_name(f"{skills_root.name}-backups")


def detected_mattpocock_skill_names(skills_root: Path) -> list[str]:
    candidates = (
        *MATTPOCOCK_CANONICAL_SKILLS,
        *MATTPOCOCK_LEGACY_RENAMES.keys(),
        *MATTPOCOCK_REMOVED_SKILLS.keys(),
    )
    detected: list[str] = []
    for name in candidates:
        target = skills_root / name
        if filesystem_entry_exists(target):
            detected.append(name)
    return detected


def canonical_migration_targets(detected: list[str]) -> list[str]:
    selected: list[str] = []
    for name in detected:
        if name in MATTPOCOCK_REMOVED_SKILLS:
            continue
        selected.append(canonical_external_skill_name(name))
    return external_skill_dependency_closure(selected)


def build_external_migration_plan(args: argparse.Namespace) -> dict[str, object]:
    skills_root = scoped_skills_root(args)

    detected = detected_mattpocock_skill_names(skills_root)
    legacy = [
        name
        for name in detected
        if name in MATTPOCOCK_LEGACY_RENAMES or name in MATTPOCOCK_REMOVED_SKILLS
    ]
    selected = canonical_migration_targets(legacy)
    canonical = [name for name in detected if name in MATTPOCOCK_CANONICAL_SKILLS]
    return {
        "mode": "mattpocock-external-migration",
        "status": "planned" if legacy else "skipped",
        "reason": None
        if legacy
        else "no legacy mattpocock skills detected in global skills root",
        "targetDir": str(skills_root),
        "detectedLegacy": legacy,
        "detectedCanonical": canonical,
        "requiredCanonical": selected,
        "removeLegacy": legacy,
        "backupRoot": str(external_migration_backup_root(skills_root)),
        "autoMode": "legacy-only",
    }


def backup_skill_target(target: Path, backup_dir: Path) -> str | None:
    if not target.exists():
        return None
    destination = backup_dir / target.name
    if destination.exists():
        remove_existing_target(destination)
    backup_dir.mkdir(parents=True, exist_ok=True)
    if target.is_dir() and not target.is_symlink():
        shutil.copytree(
            target, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )
    else:
        shutil.copy2(target, destination)
    return str(destination)


def run_external_migration(plan: dict[str, object]) -> list[dict[str, object]]:
    if plan["status"] != "planned":
        return [
            {
                "status": "skipped",
                "reason": plan.get("reason"),
            }
        ]

    target_dir = Path(str(plan["targetDir"]))
    remove_legacy = plan.get("removeLegacy")
    if not isinstance(remove_legacy, list):
        raise RuntimeError("external migration removeLegacy must be a list")
    legacy = [
        str(name)
        for name in remove_legacy
        if filesystem_entry_exists(target_dir / str(name))
    ]
    if not legacy:
        return [
            {
                "status": "skipped",
                "reason": "legacy targets were already handled by canonical installation",
            }
        ]
    backup_dir = (
        external_migration_backup_root(target_dir)
        / f"mattpocock-1.0-migration-{external_migration_timestamp()}"
    )

    results: list[dict[str, object]] = []
    for name in legacy:
        identity_error = legacy_external_skill_identity_error(target_dir / name, name)
        if identity_error is not None:
            results.append(
                {
                    "name": name,
                    "replacement": canonical_external_skill_name(name),
                    "target": str(target_dir / name),
                    "status": "failed",
                    "phase": "preflight-legacy-identity",
                    "error": identity_error,
                }
            )
            continue
        if name in MATTPOCOCK_LEGACY_RENAMES:
            replacement = canonical_external_skill_name(name)
            if not external_skill_target_is_valid(target_dir, replacement):
                results.append(
                    {
                        "name": name,
                        "status": "failed",
                        "phase": "preflight",
                        "error": f"canonical replacement is missing: {replacement}",
                    }
                )
    if results:
        return results

    for name in legacy:
        try:
            backup = backup_skill_target(target_dir / name, backup_dir)
            results.append({"name": name, "status": "backed-up", "backup": backup})
        except Exception as exc:  # noqa: BLE001 - keep migration report per target.
            results.append(
                {"name": name, "status": "failed", "phase": "backup", "error": str(exc)}
            )

    if any(item["status"] == "failed" for item in results):
        return results

    legacy_removals = remove_legacy_external_targets(target_dir, [], legacy)
    results.extend(legacy_removals)
    return results


def execute_external_skill_install(
    args: argparse.Namespace, selected: list[str], target_dir: Path
) -> tuple[list[dict[str, object]], dict[str, object]]:
    try:
        with tempfile.TemporaryDirectory(
            prefix="sbtd-onboard-external-sources-"
        ) as tmp:
            resolved = resolve_external_install_sources(
                selected, args.source, Path(tmp)
            )
            staging = stage_external_skills(selected, resolved, target_dir)
            return commit_external_skill_transaction(
                selected, resolved, target_dir, staging
            )
    except Exception as exc:  # noqa: BLE001 - no target is changed before the transaction begins.
        return (
            [
                {
                    "name": name,
                    "repo": EXTERNAL_SKILL_SOURCES[name]["repo"],
                    "target": str(target_dir / name),
                    "status": "failed",
                    "phase": "prepare",
                    "error": str(exc),
                }
                for name in selected
            ],
            {
                "status": "aborted-before-commit",
                "rolledBack": False,
                "rollbackErrors": [],
                "rollbackPath": None,
            },
        )


def external_migration_identity_failures(
    plan: dict[str, object]
) -> list[dict[str, object]]:
    target_dir = Path(str(plan["targetDir"]))
    remove_legacy = plan.get("removeLegacy")
    if not isinstance(remove_legacy, list):
        raise TypeError("external migration removeLegacy must be a list")
    return [
        {
            "name": name,
            "replacement": canonical_external_skill_name(name),
            "target": str(target_dir / name),
            "status": "failed",
            "phase": "preflight-legacy-identity",
            "error": identity_error,
        }
        for name in (str(name) for name in remove_legacy)
        if filesystem_entry_exists(target_dir / name)
        if (
            identity_error := legacy_external_skill_identity_error(
                target_dir / name, name
            )
        )
        is not None
    ]


def migrate_external_skills(args: argparse.Namespace) -> int:
    plan = build_external_migration_plan(args)
    payload: dict[str, object] = {
        "mode": "migrate-external-skills",
        "scope": args.scope,
        "requestedSource": args.source,
        "targetDir": plan["targetDir"],
        "plan": plan,
        "installationResults": [],
        "transaction": {
            "status": "not-required",
            "rolledBack": False,
            "rollbackErrors": [],
            "rollbackPath": None,
        },
        "results": [],
    }
    if plan["status"] == "skipped":
        payload["status"] = "skipped"
        payload["results"] = [
            {"status": "skipped", "reason": plan.get("reason")}
        ]
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print_external_migration_report(cast(list[dict[str, object]], payload["results"]))
        return 0

    identity_failures = external_migration_identity_failures(plan)
    if identity_failures:
        payload["status"] = "failed"
        payload["results"] = identity_failures
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print_external_migration_report(identity_failures)
        return 1

    if not args.yes:
        payload["status"] = "needs-confirmation"
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print_external_migration_report(
                [{"status": "needs-confirmation", "reason": "rerun with --yes"}]
            )
        return 2

    required_canonical = plan["requiredCanonical"]
    if not isinstance(required_canonical, list):
        raise TypeError("external migration requiredCanonical must be a list")
    selected = [str(name) for name in required_canonical]
    installation_results: list[dict[str, object]] = []
    if selected:
        target_dir = Path(str(plan["targetDir"]))
        installation_results, transaction = execute_external_skill_install(
            args, selected, target_dir
        )
        payload["installationResults"] = installation_results
        payload["transaction"] = transaction
        if transaction["status"] != "committed":
            payload["status"] = "failed"
            payload["results"] = installation_results
            if args.json:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                print_external_migration_report(installation_results)
            return 1

    migration_results = run_external_migration(build_external_migration_plan(args))
    results = [*installation_results, *migration_results]
    payload["results"] = results
    failed = [item for item in results if item["status"] == "failed"]
    payload["status"] = "failed" if failed else "migrated"
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print_external_migration_report(results)
    return 1 if failed else 0


def install_external_skills(args: argparse.Namespace) -> int:
    selected = parse_skill_names(args)
    target_dir = resolve_install_skills_dir(args)
    plan = external_install_plan(args, selected, target_dir)

    if not args.yes:
        print_external_install_plan(plan, args.json)
        print(
            "Refusing to install external skills without --yes. Confirm with the user, then rerun with --yes.",
            file=sys.stderr,
        )
        return 2
    if not args.json:
        print_external_install_plan(plan, False)

    results: list[dict[str, object]] = []
    transaction: dict[str, object] = {
        "status": "not-started",
        "rolledBack": False,
        "rollbackErrors": [],
        "rollbackPath": None,
    }
    results, transaction = execute_external_skill_install(args, selected, target_dir)

    payload = {
        "mode": "install-external-skills",
        "scope": args.scope,
        "requestedSource": args.source,
        "targetDir": str(target_dir),
        "forceOverwriteExisting": True,
        "backupExistingTargets": "temporary-rollback",
        "replaceFlagProvided": bool(args.replace),
        "plan": plan,
        "results": results,
        "transaction": transaction,
    }
    post_check = build_check_results(args)
    payload["postCheck"] = post_check
    payload["installationReport"] = post_check["installationReport"]
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("\nExternal skill install results")
        for item in results:
            print(f"- {item['name']}: {item['status']}")
            if item.get("target"):
                print(f"  target: {item['target']}")
            if item.get("sourceUsed"):
                print(f"  source: {item['sourceUsed']} ({item.get('sourceRevision')})")
            if item.get("fallbackReason"):
                print(f"  fallback: {item['fallbackReason']}")
            if item.get("error"):
                print(f"  note: {item['error']}")
        print(f"Transaction: {transaction['status']}")
        if transaction.get("rollbackPath"):
            print(f"Rollback backup retained at: {transaction['rollbackPath']}")
        rollback_errors = transaction.get("rollbackErrors")
        if isinstance(rollback_errors, list):
            for rollback_error in rollback_errors:
                print(f"  rollback error: {rollback_error}")
        print_installation_report(
            cast(dict[str, object], payload["installationReport"]),
            "Final installation report",
        )

    return 1 if transaction["status"] != "committed" else 0


def promote_external_skills_stable(args: argparse.Namespace) -> int:
    manifest = load_external_stable_manifest()
    repositories = cast(dict[str, object], manifest["repositories"])
    skills = cast(dict[str, object], manifest["skills"])
    repository = repositories.get(args.repository)
    if not isinstance(repository, dict):
        known = ", ".join(sorted(repositories))
        raise SystemExit(
            f"Unknown stable repository: {args.repository}. Known: {known}"
        )
    selected = [
        name
        for name, entry in skills.items()
        if isinstance(entry, dict) and entry.get("repository") == args.repository
    ]
    plan = {
        "mode": "promote-external-skills-stable",
        "repository": args.repository,
        "repo": repository.get("url"),
        "revision": args.revision,
        "stableSet": args.stable_set,
        "skills": selected,
        "target": str(EXTERNAL_STABLE_ROOT),
    }
    if not args.yes:
        if args.json:
            print(json.dumps(plan, indent=2, ensure_ascii=False))
        else:
            print("Stable External Skills promotion plan")
            for key, value in plan.items():
                print(f"- {key}: {value}")
            print("Refusing to promote without --yes.", file=sys.stderr)
        return 2

    payload: dict[str, object] = {**plan, "status": "failed"}
    with tempfile.TemporaryDirectory(prefix="sbtd-external-promotion-source-") as tmp:
        repo_root = Path(tmp) / "repository"
        ok, error = clone_repo_at_revision(
            str(repository.get("url") or ""), args.revision, repo_root
        )
        if not ok:
            payload["error"] = error
            print(
                json.dumps(payload, indent=2, ensure_ascii=False)
                if args.json
                else error
            )
            return 1

        candidate_container = Path(
            tempfile.mkdtemp(
                prefix=".sbtd-stable-promotion-", dir=EXTERNAL_STABLE_ROOT.parent
            )
        )
        candidate_root = candidate_container / "stable"
        previous_root = candidate_container / "previous"
        retain_candidate_container = False
        try:
            shutil.copytree(EXTERNAL_STABLE_ROOT, candidate_root)
            candidate_manifest = json.loads(json.dumps(manifest))
            candidate_repositories = cast(
                dict[str, object], candidate_manifest["repositories"]
            )
            candidate_skills = cast(dict[str, object], candidate_manifest["skills"])

            for name in selected:
                entry = candidate_skills[name]
                if not isinstance(entry, dict):
                    raise RuntimeError(f"stable Skill metadata is invalid: {name}")
                entry = cast(dict[str, object], entry)
                source = resolve_contained_relative_path(
                    repo_root,
                    entry.get("sourceSubpath"),
                    f"sourceSubpath for {name}",
                )
                validate_external_skill_source(name, source)
                destination = resolve_contained_relative_path(
                    candidate_root,
                    entry.get("stablePath"),
                    f"stablePath for {name}",
                )
                if destination.exists():
                    remove_existing_target(destination)
                shutil.copytree(
                    source,
                    destination,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
                )
                validate_external_skill_source(name, destination)
                entry["treeSha256"] = external_tree_sha256(destination)

            payload["prunedStableSkills"] = prune_unmanaged_stable_skill_directories(
                candidate_manifest, candidate_root
            )

            license_files = repository.get("licenseFiles")
            if not isinstance(license_files, list):
                raise RuntimeError(
                    f"stable repository {args.repository} has no licenseFiles list"
                )
            for license_entry in license_files:
                if not isinstance(license_entry, dict):
                    raise RuntimeError(
                        f"stable repository {args.repository} has an invalid license entry"
                    )
                source = resolve_contained_relative_path(
                    repo_root,
                    license_entry.get("source"),
                    f"license source for {args.repository}",
                )
                destination = resolve_contained_relative_path(
                    candidate_root,
                    license_entry.get("stablePath"),
                    f"license stablePath for {args.repository}",
                )
                if not source.is_file():
                    raise RuntimeError(
                        f"required upstream license file is missing: {source}"
                    )
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

            candidate_repository = candidate_repositories[args.repository]
            if not isinstance(candidate_repository, dict):
                raise RuntimeError(
                    f"stable repository metadata is invalid: {args.repository}"
                )
            candidate_repository = cast(dict[str, object], candidate_repository)
            candidate_repository["revision"] = args.revision
            candidate_manifest["stableSet"] = args.stable_set
            candidate_manifest["promotedAt"] = dt.date.today().isoformat()
            (candidate_root / "MANIFEST.json").write_text(
                json.dumps(candidate_manifest, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            validate_external_stable_metadata(candidate_manifest, candidate_root)
            for name in EXTERNAL_SKILL_SOURCES:
                stable_external_skill_source(candidate_manifest, name, candidate_root)

            shutil.move(str(EXTERNAL_STABLE_ROOT), str(previous_root))
            try:
                shutil.move(str(candidate_root), str(EXTERNAL_STABLE_ROOT))
            except Exception as commit_exc:
                try:
                    shutil.move(str(previous_root), str(EXTERNAL_STABLE_ROOT))
                except Exception as restore_exc:
                    retain_candidate_container = True
                    raise RuntimeError(
                        "stable promotion commit and rollback failed; previous stable set retained at "
                        f"{previous_root}: commit={commit_exc}; rollback={restore_exc}"
                    ) from restore_exc
                raise
            payload["status"] = "promoted"
            payload["promotedSkills"] = selected
        except Exception as exc:  # noqa: BLE001 - promotion keeps the prior stable set on every failure.
            payload["error"] = str(exc)
        finally:
            if not retain_candidate_container:
                shutil.rmtree(candidate_container, ignore_errors=True)

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"Stable External Skills promotion: {payload['status']}")
        if payload.get("error"):
            print(f"- error: {payload['error']}")
        elif payload.get("promotedSkills"):
            print("- promoted: " + ", ".join(selected))
    return 0 if payload["status"] == "promoted" else 1


def missing_required_external_skills(args: argparse.Namespace) -> list[str]:
    global_skills_dir = resolve_global_skills_dir(
        getattr(args, "global_skills_dir", None)
    )[0]
    return [
        name
        for name in EXTERNAL_SKILL_SOURCES
        if not external_skill_target_is_valid(global_skills_dir, name)
    ]


def install_required_external_skills(args: argparse.Namespace) -> int:
    missing = missing_required_external_skills(args)
    if not missing:
        return 0
    print(
        "Required global external Skills are missing and will be installed: "
        + ", ".join(missing)
    )
    install_args = argparse.Namespace(
        all=False,
        skills=",".join(missing),
        scope="global",
        source="auto",
        global_skills_dir=getattr(args, "global_skills_dir", None),
        replace=False,
        yes=True,
        json=False,
    )
    return install_external_skills(install_args)


def default_shell_profile() -> Path:
    shell_name = Path(os.environ.get("SHELL", "")).name
    if shell_name == "zsh":
        return Path.home() / ".zshrc"
    if shell_name == "bash" and platform.system() == "Darwin":
        return Path.home() / ".bash_profile"
    if shell_name == "bash":
        return Path.home() / ".bashrc"
    return Path.home() / ".profile"


def ensure_profile_line(profile: Path, line: str, marker: str) -> bool:
    profile.parent.mkdir(parents=True, exist_ok=True)
    existing = profile.read_text(encoding="utf-8") if profile.exists() else ""
    if line in existing:
        return False
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    with profile.open("a", encoding="utf-8") as handle:
        handle.write(f"{prefix}# {marker}\n{line}\n")
    return True


def ensure_npm(args: argparse.Namespace) -> int:
    before = check_npm_runtime()
    payload: dict[str, object] = {
        "mode": "ensure-npm",
        "platform": before["platform"],
        "before": before,
        "actions": [],
    }

    if before["npm"]["installed"]:
        payload["status"] = "already-installed"
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("npm is already available.")
            print(f"npm: {before['npm']['path']} ({before['npm']['version']})")
            print(f"node: {before['node']['path']} ({before['node']['version']})")
        return 0

    system = platform.system() or sys.platform
    if system == "Windows":
        payload["status"] = "unsupported-platform"
        payload["advice"] = (
            "Native Windows is not supported by the nvm-sh installer. Use WSL with nvm-sh, "
            "or install a Windows Node version manager such as nvm-windows/nvs, then rerun check."
        )
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(
                "npm is missing, but native Windows cannot be fully configured by this nvm-sh installer."
            )
            print(payload["advice"])
        return 1

    install_actions = payload["actions"]
    install_actions.append(f"install or update nvm with {NVM_INSTALL_URL}")
    install_actions.append("install latest Node.js LTS with nvm")
    install_actions.append("set nvm default alias to lts/*")
    install_actions.append("switch current shell to Node.js LTS")

    if not args.yes:
        payload["status"] = "needs-confirmation"
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("npm is missing.")
            print(f"Platform: {system}")
            for action in install_actions:
                print(f"- {action}")
            print("Rerun with --yes after user confirmation.")
        return 2

    installer_tool = (
        "curl" if shutil.which("curl") else "wget" if shutil.which("wget") else None
    )
    if not installer_tool:
        payload["status"] = "failed"
        payload["error"] = (
            "Neither curl nor wget is available to download the nvm installer."
        )
        print(
            json.dumps(payload, indent=2, ensure_ascii=False)
            if args.json
            else payload["error"]
        )
        return 1

    if installer_tool == "curl":
        install_script = f"curl -o- {NVM_INSTALL_URL} | bash"
    else:
        install_script = f"wget -qO- {NVM_INSTALL_URL} | bash"

    install_result = shell_result(install_script, timeout=300)
    if not install_result or install_result.returncode != 0:
        payload["status"] = "failed"
        payload["error"] = (
            (install_result.stderr or install_result.stdout).strip()
            if install_result
            else "Unable to execute shell installer."
        )
        print(
            json.dumps(payload, indent=2, ensure_ascii=False)
            if args.json
            else payload["error"]
        )
        return 1

    node_script = (
        f"{nvm_load_script()}; "
        "nvm install --lts; "
        "nvm alias default 'lts/*'; "
        "nvm use --lts; "
        "node --version; "
        "npm --version"
    )
    node_result = shell_result(node_script, timeout=600)
    if not node_result or node_result.returncode != 0:
        payload["status"] = "failed"
        payload["error"] = (
            (node_result.stderr or node_result.stdout).strip()
            if node_result
            else "Unable to run nvm after installation."
        )
        print(
            json.dumps(payload, indent=2, ensure_ascii=False)
            if args.json
            else payload["error"]
        )
        return 1

    after = check_npm_runtime()
    payload["after"] = after
    payload["status"] = "installed" if after["npm"]["installed"] else "failed"
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"ensure-npm status: {payload['status']}")
        if after["npm"]["installed"]:
            print(f"npm: {after['npm']['path']} ({after['npm']['version']})")
            print(f"node: {after['node']['path']} ({after['node']['version']})")
        else:
            print(
                "npm still is not available in PATH. Restart the shell or source the profile file, then rerun check."
            )
    return 0 if after["npm"]["installed"] else 1


def install_agent_cli(args: argparse.Namespace) -> int:
    before = check_agent_cli(args.platform)
    payload: dict[str, object] = {
        "mode": "install-agent-cli",
        "platform": before["platform"],
        "label": before["label"],
        "command": before["command"],
        "npmPackage": before["npmPackage"],
        "installCommand": before["installCommand"],
        "verifyCommand": before["verifyCommand"],
        "runtime": before["runtime"],
        "before": before,
    }

    if before["installed"]:
        payload["status"] = "already-installed"
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"{before['label']} CLI is already installed and verified.")
            print(f"{before['command']}: {before['path']} ({before['version']})")
        return 0

    runtime = before["runtime"]
    if not runtime["npm"]["installed"]:
        payload["status"] = "npm-required"
        payload["advice"] = (
            "Install npm first with `python scripts/onboard.py ensure-npm --yes` after user confirmation, "
            "then rerun install-agent-cli."
        )
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"{before['label']} CLI is missing and npm is not usable.")
            print(payload["advice"])
        return 2

    if not args.yes:
        payload["status"] = "needs-confirmation"
        payload["actions"] = [
            f"run `{before['installCommand']}`",
            f"verify `{before['verifyCommand']}`",
        ]
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"{before['label']} CLI is missing or failed verification.")
            for action in payload["actions"]:
                print(f"- {action}")
            print("Rerun with --yes after user confirmation.")
        return 2

    npm_package = f"{before['npmPackage']}@latest"
    install_result = run_command(("npm", "install", "-g", npm_package), timeout=900)
    payload["installOutput"] = command_excerpt(install_result)
    if not install_result or install_result.returncode != 0:
        payload["status"] = "failed"
        payload["error"] = (
            command_excerpt(install_result) or "npm global install failed."
        )
        print(
            json.dumps(payload, indent=2, ensure_ascii=False)
            if args.json
            else payload["error"]
        )
        return 1

    after = check_agent_cli(str(before["platform"]))
    payload["after"] = after
    payload["status"] = "installed" if after["installed"] else "verification-failed"
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"install-agent-cli status: {payload['status']}")
        if after["installed"]:
            print(f"{after['command']}: {after['path']} ({after['version']})")
        else:
            print(
                f"npm completed, but `{after['verifyCommand']}` did not pass. "
                "Check the npm global bin PATH and the package runtime prerequisites."
            )
            if after.get("verifyOutput"):
                print(f"First verification output: {after['verifyOutput']}")
    return 0 if after["installed"] else 1


def install_rtk(args: argparse.Namespace) -> int:
    before = check_cli_tool(CLI_TOOLS[0])
    local_bin = Path.home() / ".local" / "bin"
    profile = expand_path(args.profile) or default_shell_profile()
    payload: dict[str, object] = {
        "mode": "install-rtk",
        "platform": platform.system() or sys.platform,
        "before": before,
        "installUrl": RTK_INSTALL_URL,
        "targetDir": str(local_bin),
        "profile": str(profile),
    }

    if before["installed"]:
        payload["status"] = "already-installed"
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("rtk is already installed and verified with `rtk gain`.")
            print(f"rtk: {before['path']} ({before['version']})")
        return 0

    if before.get("wrongPackageSuspected") and not args.replace_wrong:
        payload["status"] = "wrong-package-suspected"
        payload["advice"] = (
            "An `rtk` command exists but `rtk gain` failed. Confirm whether to remove or replace it before installing rtk-ai/rtk."
        )
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(payload["advice"])
            print(
                "Rerun with --replace-wrong after user confirmation if replacement is intended."
            )
        return 2
    if before.get("verificationFailed") and not args.reinstall:
        payload["status"] = "verification-failed"
        payload["advice"] = (
            "`rtk --version` looks like rtk-ai/rtk, but `rtk gain` failed. "
            "Check RTK data directory permissions first, or rerun with --reinstall after user confirmation."
        )
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(payload["advice"])
        return 2

    system = platform.system() or sys.platform
    if system == "Windows":
        payload["status"] = "manual-required"
        payload["advice"] = (
            "Download the Windows release zip from rtk-ai/rtk, extract rtk.exe into a directory on PATH "
            "such as %USERPROFILE%\\.local\\bin, then verify with `rtk --version` and `rtk gain`."
        )
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(payload["advice"])
        return 1

    if not args.yes:
        payload["status"] = "needs-confirmation"
        payload["actions"] = [
            f"run {RTK_INSTALL_URL}",
            f"ensure {local_bin} is in PATH via {profile}",
            "verify `rtk --version` and `rtk gain`",
        ]
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("rtk is missing or not verified.")
            for action in payload["actions"]:
                print(f"- {action}")
            print("Rerun with --yes after user confirmation.")
        return 2

    if (
        before.get("wrongPackageSuspected")
        and args.replace_wrong
        and shutil.which("cargo")
    ):
        run_command(("cargo", "uninstall", "rtk"), timeout=120)

    if not shutil.which("curl"):
        payload["status"] = "failed"
        payload["error"] = "curl is required for the rtk-ai/rtk quick install script."
        print(
            json.dumps(payload, indent=2, ensure_ascii=False)
            if args.json
            else payload["error"]
        )
        return 1

    install_result = shell_result(f"curl -fsSL {RTK_INSTALL_URL} | sh", timeout=300)
    if not install_result or install_result.returncode != 0:
        payload["status"] = "failed"
        payload["error"] = (
            (install_result.stderr or install_result.stdout).strip()
            if install_result
            else "Unable to run rtk installer."
        )
        print(
            json.dumps(payload, indent=2, ensure_ascii=False)
            if args.json
            else payload["error"]
        )
        return 1

    os.environ["PATH"] = f"{local_bin}{os.pathsep}{os.environ.get('PATH', '')}"
    profile_updated = ensure_profile_line(
        profile,
        'export PATH="$HOME/.local/bin:$PATH"',
        "Added by sbtd-workflow-onboard for rtk",
    )
    after = check_cli_tool(CLI_TOOLS[0])
    payload["after"] = after
    payload["profileUpdated"] = profile_updated
    payload["status"] = "installed" if after["installed"] else "failed"
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"install-rtk status: {payload['status']}")
        if profile_updated:
            print(f"Updated PATH in {profile}")
        if after["installed"]:
            print(f"rtk: {after['path']} ({after['version']})")
            print("Verification passed: rtk gain")
        else:
            print(
                "rtk was installed but did not pass `rtk gain`. Check PATH, release download, and name-collision risk."
            )
    return 0 if after["installed"] else 1


def caveman_platform_install_command() -> tuple[
    str, tuple[str, ...] | None, str | None
]:
    system = platform.system() or sys.platform
    if system == "Windows":
        display = f"irm {CAVEMAN_INSTALL_PS1_URL} | iex"
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if not powershell:
            return (
                display,
                None,
                "PowerShell is required to run the caveman Windows installer.",
            )
        return (
            display,
            (
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                display,
            ),
            None,
        )

    if system in {"Darwin", "Linux"}:
        display = f"curl -fsSL {CAVEMAN_INSTALL_SH_URL} | bash"
        if not shutil.which("curl"):
            return (
                display,
                None,
                "curl is required to download the caveman macOS/Linux installer.",
            )
        bash = shutil.which("bash")
        if not bash:
            return (
                display,
                None,
                "bash is required to run the caveman macOS/Linux installer.",
            )
        return display, (bash, "-lc", display), None

    return (
        f"curl -fsSL {CAVEMAN_INSTALL_SH_URL} | bash",
        None,
        f"Automatic caveman installation is not configured for platform: {system}.",
    )


def install_caveman(args: argparse.Namespace) -> int:
    global_skills_dir = resolve_global_skills_dir(args.global_skills_dir)[0]
    before = check_skill("caveman", "interaction", global_skills_dir, None)
    display_command, install_command, unavailable_reason = (
        caveman_platform_install_command()
    )
    payload: dict[str, object] = {
        "mode": "install-caveman",
        "agent": args.agent,
        "platform": platform.system() or sys.platform,
        "before": before,
        "installSpec": CAVEMAN_INSTALL_SPEC,
        "installCommand": display_command,
        "installCommands": {
            "macosLinux": f"curl -fsSL {CAVEMAN_INSTALL_SH_URL} | bash",
            "windows": f"irm {CAVEMAN_INSTALL_PS1_URL} | iex",
        },
        "globalSkillsDir": str(global_skills_dir),
    }

    if before["installed"]:
        payload["status"] = "already-installed"
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("caveman is already installed as a global interaction skill.")
            for location in before["locations"]:
                print(f"{location['scope']}: {location['path']}")
        return 0

    if unavailable_reason or install_command is None:
        payload["status"] = "manual-required"
        payload["advice"] = (
            unavailable_reason
            or "Run the platform-specific caveman installer manually, then rerun check."
        )
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(
                "caveman is missing, but automatic installation is not available on this platform."
            )
            print(payload["advice"])
            print(f"Suggested command: {display_command}")
        return 1

    if not args.yes:
        payload["status"] = "needs-confirmation"
        payload["actions"] = [
            "install the caveman Codex skill into the user-level Agent/Codex skill environment",
            f"run `{display_command}`",
            "rerun `python scripts/onboard.py check` and confirm `caveman/SKILL.md` is visible",
        ]
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("caveman is missing.")
            print(
                "caveman compresses Agent replies for lower token use; it does not change code, tests, validation, or workflow decisions."
            )
            for action in payload["actions"]:
                print(f"- {action}")
            print("Rerun with --yes after user confirmation.")
        return 2

    install_env = os.environ.copy()
    install_env["AGENT_SKILLS_DIR"] = str(global_skills_dir)
    install_result = run_command(install_command, timeout=600, env=install_env)
    payload["installOutput"] = command_excerpt(install_result)
    if not install_result or install_result.returncode != 0:
        payload["status"] = "failed"
        payload["error"] = (
            command_excerpt(install_result)
            or "Unable to run the caveman skill installer."
        )
        print(
            json.dumps(payload, indent=2, ensure_ascii=False)
            if args.json
            else payload["error"]
        )
        return 1

    after = check_skill("caveman", "interaction", global_skills_dir, None)
    payload["after"] = after
    payload["status"] = "installed" if after["installed"] else "failed"
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"install-caveman status: {payload['status']}")
        if after["installed"]:
            for location in after["locations"]:
                print(f"{location['scope']}: {location['path']}")
            print(
                "Verification passed: caveman/SKILL.md is visible in the checked global skills directory."
            )
        else:
            print(
                "The caveman installer completed, but `caveman/SKILL.md` was not found in the checked global skills directory."
            )
            print(
                "If you use a custom skills root, set AGENT_SKILLS_DIR or rerun check with --global-skills-dir."
            )
    return 0 if after["installed"] else 1


def command_excerpt(
    completed: subprocess.CompletedProcess[str] | None, limit: int = 20
) -> str | None:
    if completed is None:
        return None
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    lines = output.strip().splitlines()
    if not lines:
        return None
    return "\n".join(lines[-limit:])


def github_json(url: str, timeout: int = 30) -> dict[str, object]:
    request = urllib.request.Request(
        url, headers={"User-Agent": "sbtd-workflow-onboard"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def download_url(url: str, destination: Path, timeout: int = 900) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "sbtd-workflow-onboard"}
    )
    with (
        urllib.request.urlopen(request, timeout=timeout) as response,
        destination.open("wb") as handle,
    ):
        shutil.copyfileobj(response, handle)


def temurin_platform_ids() -> tuple[str | None, str | None, str | None]:
    system = platform.system() or sys.platform
    machine = platform.machine().lower()
    if system == "Darwin":
        os_id = "mac"
    elif system == "Linux":
        os_id = "linux"
    else:
        return (
            None,
            None,
            f"Temurin tarball auto-install is only supported on macOS and Linux; current platform is {system}.",
        )

    if machine in {"x86_64", "amd64"}:
        arch_id = "x64"
    elif machine in {"arm64", "aarch64"}:
        arch_id = "aarch64"
    else:
        return (
            None,
            None,
            f"Unsupported CPU architecture for Temurin auto-install: {machine}.",
        )
    return os_id, arch_id, None


def select_temurin_asset(major: int) -> dict[str, object]:
    os_id, arch_id, reason = temurin_platform_ids()
    if reason:
        raise RuntimeError(reason)

    release = github_json(TEMURIN_RELEASES_API_TEMPLATE.format(major=major))
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise RuntimeError("GitHub release payload did not include assets.")

    prefix = f"OpenJDK{major}U-jdk_{arch_id}_{os_id}_hotspot_"
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        url = str(asset.get("browser_download_url") or "")
        if (
            name.startswith(prefix)
            and name.endswith(".tar.gz")
            and "debugimage" not in name
            and "testimage" not in name
            and "static-libs" not in name
            and url
        ):
            return {
                "release": release.get("tag_name"),
                "name": name,
                "url": url,
            }
    raise RuntimeError(
        f"No matching Temurin {major} JDK tar.gz asset found for {arch_id}/{os_id}."
    )


def safe_extract_tar(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            target = (destination / member.name).resolve()
            if target != destination_root and destination_root not in target.parents:
                raise RuntimeError(f"Unsafe path in archive: {member.name}")
        tar.extractall(destination)


def find_java_home(root: Path) -> Path:
    candidates = sorted(root.rglob("bin/java"))
    for java_bin in candidates:
        if java_bin.is_file():
            return java_bin.parent.parent
    raise RuntimeError("Extracted JDK archive did not contain bin/java.")


def activate_java_home(java_home: Path) -> None:
    os.environ["JAVA_HOME"] = str(java_home)
    os.environ["PATH"] = f"{java_home / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"


def install_java(args: argparse.Namespace) -> int:
    major = int(args.major)
    if major < JAVA_MIN_MAJOR:
        raise SystemExit(
            f"Refusing to install Java {major}. Maestro requires Java {JAVA_MIN_MAJOR}+."
        )

    before = check_java_for_maestro()
    install_root = expand_path(args.install_root) or (
        Path.home() / ".local" / "share" / "sbtd-workflow" / "jdks"
    )
    target_home = install_root / f"temurin-{major}"
    profile = expand_path(args.profile) or default_shell_profile()
    payload: dict[str, object] = {
        "mode": "install-java",
        "platform": platform.system() or sys.platform,
        "before": before,
        "major": major,
        "minimumMajor": JAVA_MIN_MAJOR,
        "releaseSource": TEMURIN21_RELEASES_URL,
        "targetJavaHome": str(target_home),
        "profile": str(profile),
    }

    if before["installed"] and not args.force:
        payload["status"] = "already-installed"
        payload["advice"] = (
            "An installed JDK already satisfies Maestro's Java 17+ prerequisite. Use --force only after confirming a version replacement is intended."
        )
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("An installed JDK already satisfies Maestro's Java 17+ prerequisite.")
            print(f"java: {before['path']} ({before['version']})")
            if before.get("javaHome"):
                print(f"JAVA_HOME: {before['javaHome']}")
            print(payload["advice"])
        return 0

    os_id, arch_id, platform_reason = temurin_platform_ids()
    if platform_reason:
        payload["status"] = "manual-required"
        payload["reason"] = platform_reason
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(platform_reason)
            print(
                f"Download a Java {major}+ JDK manually from {TEMURIN21_RELEASES_URL}."
            )
        return 1
    payload["targetPlatform"] = {"os": os_id, "arch": arch_id}

    payload["actions"] = [
        f"fetch the latest Temurin {major} JDK release asset from {TEMURIN21_RELEASES_URL}",
        f"extract it into {target_home}",
        f"write JAVA_HOME and PATH exports into {profile}",
        "verify `java --version` reports Java 17 or higher",
    ]
    if not args.yes:
        payload["status"] = "needs-confirmation"
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(
                f"Java {JAVA_MIN_MAJOR}+ is missing or a Java {major} install was explicitly requested."
            )
            for action in payload["actions"]:
                print(f"- {action}")
            print("Rerun with --yes after user confirmation.")
        return 2

    try:
        asset = select_temurin_asset(major)
        payload["selectedAsset"] = asset
        with tempfile.TemporaryDirectory(prefix="sbtd-temurin-") as temp_dir:
            archive = Path(temp_dir) / str(asset["name"])
            extracted = Path(temp_dir) / "extracted"
            download_url(str(asset["url"]), archive)
            safe_extract_tar(archive, extracted)
            extracted_java_home = find_java_home(extracted)
            target_home.parent.mkdir(parents=True, exist_ok=True)
            if target_home.exists():
                backup = backup_path(target_home)
                shutil.move(str(target_home), str(backup))
                payload["backup"] = str(backup)
            shutil.move(str(extracted_java_home), str(target_home))
    except (OSError, RuntimeError, urllib.error.URLError, json.JSONDecodeError) as exc:
        payload["status"] = "failed"
        payload["error"] = str(exc)
        print(
            json.dumps(payload, indent=2, ensure_ascii=False)
            if args.json
            else payload["error"]
        )
        return 1

    activate_java_home(target_home)
    profile_updated = ensure_profile_line(
        profile,
        f'export JAVA_HOME="{target_home}"; export PATH="$JAVA_HOME/bin:$PATH"',
        f"Added by sbtd-workflow-onboard for Temurin {major}",
    )
    after = check_java_for_maestro()
    payload["after"] = after
    payload["profileUpdated"] = profile_updated
    payload["status"] = "installed" if after["installed"] else "failed"
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"install-java status: {payload['status']}")
        if profile_updated:
            print(f"Updated JAVA_HOME/PATH in {profile}")
        if after["installed"]:
            print(f"java: {after['path']} ({after['version']})")
        else:
            print(
                "Java was installed but did not pass the Java 17+ verification. Check JAVA_HOME and PATH."
            )
    return 0 if after["installed"] else 1


def install_maestro(args: argparse.Namespace) -> int:
    java_before = check_java_for_maestro()
    before = check_maestro_cli(java_before)
    profile = expand_path(args.profile) or default_shell_profile()
    maestro_bin = Path.home() / ".maestro" / "bin"
    payload: dict[str, object] = {
        "mode": "install-maestro",
        "platform": platform.system() or sys.platform,
        "before": before,
        "java": java_before,
        "installUrl": MAESTRO_INSTALL_URL,
        "profile": str(profile),
        "maestroMcpConfig": maestro_mcp_server_config(java_before, before),
        "maestroMcpConfigExamples": maestro_mcp_config_examples(java_before, before),
    }

    if before["installed"] and not args.reinstall:
        payload["status"] = "already-installed"
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("Maestro CLI is already installed and verified.")
            print(f"maestro: {before['path']} ({before['version']})")
            print("Maestro MCP configuration:")
            print_config_examples(
                {"configExamples": payload["maestroMcpConfigExamples"]}
            )
        return 0

    if not java_before["installed"]:
        payload["status"] = "java-required"
        payload["advice"] = (
            f"Install Java {JAVA_MIN_MAJOR}+ first. Default command: "
            "`python scripts/onboard.py install-java --major 21 --yes` after user confirmation."
        )
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"Maestro CLI requires Java {JAVA_MIN_MAJOR}+ before installation.")
            print(payload["advice"])
        return 2

    system = platform.system() or sys.platform
    if system == "Windows":
        payload["status"] = "manual-required"
        payload["advice"] = (
            "Use WSL with the official install script, or follow Maestro's regular Windows installation guide manually."
        )
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(payload["advice"])
        return 1

    if before.get("verificationFailed") and not args.reinstall:
        payload["status"] = "verification-failed"
        payload["advice"] = (
            "A maestro command exists but failed verification. Rerun with --reinstall only after confirming replacement is intended."
        )
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(payload["advice"])
        return 2

    payload["actions"] = [
        f'run the official Maestro installer: curl -fsSL "{MAESTRO_INSTALL_URL}" | bash',
        f"ensure {maestro_bin} is in PATH via {profile}",
        "verify `maestro --version` and `maestro test --help`",
    ]
    if not args.yes:
        payload["status"] = "needs-confirmation"
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("Maestro CLI is missing or not verified.")
            for action in payload["actions"]:
                print(f"- {action}")
            print("Maestro MCP configuration after CLI installation:")
            print_config_examples(
                {"configExamples": payload["maestroMcpConfigExamples"]}
            )
            print("Rerun with --yes after user confirmation.")
        return 2

    if not shutil.which("curl"):
        payload["status"] = "failed"
        payload["error"] = "curl is required for the official Maestro install script."
        print(
            json.dumps(payload, indent=2, ensure_ascii=False)
            if args.json
            else payload["error"]
        )
        return 1

    install_result = shell_result(
        f'curl -fsSL "{MAESTRO_INSTALL_URL}" | bash', timeout=600
    )
    if not install_result or install_result.returncode != 0:
        payload["status"] = "failed"
        payload["error"] = (
            command_excerpt(install_result) or "Unable to run the Maestro installer."
        )
        print(
            json.dumps(payload, indent=2, ensure_ascii=False)
            if args.json
            else payload["error"]
        )
        return 1

    os.environ["PATH"] = f"{maestro_bin}{os.pathsep}{os.environ.get('PATH', '')}"
    profile_updated = ensure_profile_line(
        profile,
        'export PATH="$HOME/.maestro/bin:$PATH"',
        "Added by sbtd-workflow-onboard for Maestro CLI",
    )
    java_after = check_java_for_maestro()
    after = check_maestro_cli(java_after)
    payload["after"] = after
    payload["maestroMcpConfig"] = maestro_mcp_server_config(java_after, after)
    payload["maestroMcpConfigExamples"] = maestro_mcp_config_examples(java_after, after)
    payload["profileUpdated"] = profile_updated
    payload["status"] = "installed" if after["installed"] else "failed"
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"install-maestro status: {payload['status']}")
        if profile_updated:
            print(f"Updated PATH in {profile}")
        if after["installed"]:
            print(f"maestro: {after['path']} ({after['version']})")
            print("Maestro MCP configuration:")
            print_config_examples(
                {"configExamples": payload["maestroMcpConfigExamples"]}
            )
        else:
            print(
                "Maestro installer completed but `maestro --version` did not pass. Check PATH, Java, and installer output."
            )
    return 0 if after["installed"] else 1


def run_project_command(
    command: tuple[str, ...], cwd: Path, timeout: int = 900
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def parse_trellis_platforms(args: argparse.Namespace) -> list[str]:
    raw_values = getattr(args, "trellis_platform", None) or []
    platforms: list[str] = []
    invalid: list[str] = []
    for raw_value in raw_values:
        for part in re.split(r"[\s,]+", raw_value):
            platform_name = part.strip().lower().removeprefix("--")
            if not platform_name:
                continue
            if platform_name not in TRELLIS_INIT_PLATFORMS:
                invalid.append(platform_name)
                continue
            if platform_name not in platforms:
                platforms.append(platform_name)
    if invalid:
        allowed = ", ".join(TRELLIS_INIT_PLATFORMS)
        raise SystemExit(
            f"Unsupported Trellis platform(s): {', '.join(invalid)}. Allowed values: {allowed}"
        )
    return platforms


def trellis_init_command(username: str, platforms: list[str]) -> tuple[str, ...]:
    platform_flags = tuple(f"--{platform_name}" for platform_name in platforms)
    return (
        "trellis",
        "init",
        "-u",
        username,
        *platform_flags,
        "--yes",
        "--skip-existing",
    )


def command_display(command: tuple[str, ...]) -> str:
    return shlex.join(command)


def find_trellis_bootstrap_task(project_root: Path) -> tuple[Path | None, str | None]:
    for relative_path in TRELLIS_BOOTSTRAP_TASK_CANDIDATES:
        candidate = project_root / relative_path
        if candidate.exists():
            return candidate, relative_path
    return None, None


def run_trellis_project_setup_for_root(
    mode: str,
    args: argparse.Namespace,
    project_root: Path,
    trellis_check: dict[str, object],
) -> dict[str, object]:
    report: dict[str, object] = {
        "mode": mode,
        "status": "skipped",
        "projectRoot": str(project_root),
    }
    if mode not in {"init", "reset", "init-projects"}:
        report["reason"] = (
            "Trellis project setup only runs after init/reset/init-projects."
        )
        return report
    if getattr(args, "skip_trellis_init", False):
        report["status"] = "skipped"
        report["reason"] = "--skip-trellis-init was provided."
        return report

    report["cli"] = {
        "installed": trellis_check.get("installed"),
        "path": trellis_check.get("path"),
        "version": trellis_check.get("version"),
    }
    if not trellis_check.get("installed"):
        report["status"] = "blocked"
        report["init"] = {
            "status": "blocked-missing-cli",
            "reason": "trellis CLI must be installed and pass version verification before project initialization.",
            "nextStep": "Install or repair the required global Trellis CLI, then rerun the project initialization command.",
        }
        return report

    trellis_dir = project_root / ".trellis"
    platforms = parse_trellis_platforms(args)
    username = (getattr(args, "trellis_user", None) or "").strip()
    if trellis_dir.exists():
        report["init"] = {
            "status": "skipped-existing",
            "path": str(trellis_dir),
            "reason": "Target project already has .trellis/.",
        }
    elif not username:
        example = trellis_init_command("your-name", platforms)
        report["status"] = "needs-user"
        report["init"] = {
            "status": "needs-user",
            "reason": "Target project does not have .trellis/ and --trellis-user was not provided.",
            "nextStep": "Ask for the Trellis developer username and optional platform flags, then rerun with --projects-root, --trellis-user, and --trellis-platform.",
            "exampleCommand": command_display(example),
        }
        return report
    else:
        command = trellis_init_command(username, platforms)
        init_result = run_project_command(command, project_root, timeout=300)
        init_succeeded = bool(
            init_result and init_result.returncode == 0 and trellis_dir.exists()
        )
        report["init"] = {
            "status": "success" if init_succeeded else "failed",
            "command": command_display(command),
            "stdout": command_excerpt(init_result, limit=12),
        }
        if not init_succeeded:
            report["status"] = "failed"
            report["init"]["stderr"] = command_excerpt(init_result, limit=12)
            report["init"]["reason"] = (
                "trellis init did not complete successfully or did not create .trellis/."
            )
            return report

    if getattr(args, "skip_trellis_bootstrap", False):
        report["status"] = "success"
        report["bootstrapTask"] = {
            "status": "skipped",
            "reason": "--skip-trellis-bootstrap was provided.",
        }
        return report

    bootstrap_task, relative_path = find_trellis_bootstrap_task(project_root)
    if not bootstrap_task:
        report["status"] = "success"
        report["bootstrapTask"] = {
            "status": "not-found",
            "reason": "No bootstrap task was found at the canonical path.",
            "checkedPaths": list(TRELLIS_BOOTSTRAP_TASK_CANDIDATES),
        }
        return report

    report["status"] = "bootstrap-required"
    report["bootstrapTask"] = {
        "status": "found",
        "path": str(bootstrap_task),
        "relativePath": relative_path,
        "requiredAction": (
            "Use the trellis-workflow Skill to execute this task: read .trellis/workflow.md and task artifacts, "
            "run $trellis-before-dev, complete the bootstrap guideline work, run $trellis-check, and only then run $trellis-finish-work."
        ),
    }
    return report


def aggregate_trellis_status(projects: list[dict[str, object]]) -> str:
    statuses = {str(item.get("status")) for item in projects}
    for status in ("failed", "blocked", "needs-user", "bootstrap-required"):
        if status in statuses:
            return status
    if "success" in statuses:
        return "success"
    return "skipped"


def run_trellis_project_setup(mode: str, args: argparse.Namespace) -> dict[str, object]:
    project_roots = resolve_project_roots(args)
    if mode not in {"init", "reset", "init-projects"}:
        return {
            "mode": mode,
            "status": "skipped",
            "projects": [],
            "reason": "Trellis project setup only runs after init/reset/init-projects.",
        }
    if not project_roots:
        return {
            "mode": mode,
            "status": "skipped",
            "projects": [],
            "reason": "--projects-root was not provided.",
        }

    trellis_check = check_cli_tool(CLI_TOOLS[1])
    projects = [
        run_trellis_project_setup_for_root(mode, args, project_root, trellis_check)
        for project_root in project_roots
    ]
    return {
        "mode": mode,
        "status": aggregate_trellis_status(projects),
        "projects": projects,
    }


def print_trellis_project_setup_report(report: dict[str, object]) -> None:
    print("\nTrellis project setup:")
    print(f"- status: {report.get('status')}")
    if report.get("reason"):
        print(f"  reason: {report['reason']}")
    for project in report.get("projects", []):
        print(f"- project root: {project['projectRoot']}")
        print(f"  status: {project.get('status')}")
        cli = project.get("cli")
        if isinstance(cli, dict):
            print(f"  cli: {'installed' if cli.get('installed') else 'missing'}")
            if cli.get("path"):
                print(f"  cli path: {cli['path']}")
            if cli.get("version"):
                print(f"  cli version: {cli['version']}")
        init = project.get("init")
        if isinstance(init, dict):
            print(f"  init: {init.get('status')}")
            if init.get("path"):
                print(f"  init path: {init['path']}")
            if init.get("command"):
                print(f"  init command: {init['command']}")
            if init.get("reason"):
                print(f"  init reason: {init['reason']}")
            if init.get("nextStep"):
                print(f"  init next step: {init['nextStep']}")
            if init.get("exampleCommand"):
                print(f"  example: {init['exampleCommand']}")
        bootstrap = project.get("bootstrapTask")
        if isinstance(bootstrap, dict):
            print(f"  bootstrap task: {bootstrap.get('status')}")
            if bootstrap.get("path"):
                print(f"  bootstrap path: {bootstrap['path']}")
            if bootstrap.get("reason"):
                print(f"  bootstrap reason: {bootstrap['reason']}")
            if bootstrap.get("requiredAction"):
                print(f"  required action: {bootstrap['requiredAction']}")


def install_playwright_cli(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args, required=True)
    runtime = check_npm_runtime()
    before = check_playwright_project(project_root)
    package_json = project_root / "package.json"
    payload: dict[str, object] = {
        "mode": "install-playwright-cli",
        "projectRoot": str(project_root),
        "before": before,
        "runtime": runtime,
    }

    if before["installed"] and not args.reinstall:
        payload["status"] = "already-installed"
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("Project-level Playwright CLI is already present.")
            if before.get("version"):
                print(f"Playwright dependency: {before['version']}")
        return 0

    if not runtime["npm"]["installed"]:
        payload["status"] = "npm-required"
        payload["advice"] = (
            "Install npm first, for example with `python scripts/onboard.py ensure-npm --yes` after user confirmation."
        )
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(
                "Playwright CLI is project-level Node tooling, but npm is not usable."
            )
            print(payload["advice"])
        return 2

    if not package_json.is_file():
        payload["status"] = "not-applicable"
        payload["reason"] = (
            "No package.json exists at the project root; do not create a Node test stack automatically."
        )
        payload["fallback"] = (
            "Use Playwright MCP or Chrome DevTools MCP for exploratory Web diagnostics, and add Playwright CLI only after the project accepts a Node test dependency."
        )
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(payload["reason"])
            print(payload["fallback"])
        return 2

    payload["actions"] = [
        "install project dependency: npm install -D @playwright/test",
        "install Playwright browser binaries: npx playwright install",
    ]
    if args.skip_browsers:
        payload["actions"][-1] = (
            "skip browser binary installation because --skip-browsers was provided"
        )
    if not args.yes:
        payload["status"] = "needs-confirmation"
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("Project-level Playwright CLI is missing.")
            for action in payload["actions"]:
                print(f"- {action}")
            print("Rerun with --yes after user confirmation.")
        return 2

    install_result = run_project_command(
        ("npm", "install", "-D", "@playwright/test"), project_root, timeout=900
    )
    payload["npmInstallOutput"] = command_excerpt(install_result)
    if not install_result or install_result.returncode != 0:
        payload["status"] = "failed"
        payload["error"] = command_excerpt(install_result) or "npm install failed."
        print(
            json.dumps(payload, indent=2, ensure_ascii=False)
            if args.json
            else payload["error"]
        )
        return 1

    if not args.skip_browsers:
        browsers_result = run_project_command(
            ("npx", "playwright", "install"), project_root, timeout=1200
        )
        payload["browserInstallOutput"] = command_excerpt(browsers_result)
        if not browsers_result or browsers_result.returncode != 0:
            payload["status"] = "browser-install-failed"
            payload["error"] = (
                command_excerpt(browsers_result) or "npx playwright install failed."
            )
            print(
                json.dumps(payload, indent=2, ensure_ascii=False)
                if args.json
                else payload["error"]
            )
            return 1

    after = check_playwright_project(project_root)
    payload["after"] = after
    payload["status"] = "installed" if after["installed"] else "failed"
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"install-playwright-cli status: {payload['status']}")
        if after["installed"]:
            print(
                "Project-level Playwright CLI dependency/config marker is now present."
            )
        else:
            print(
                "Playwright install completed but no dependency/config/script marker was detected."
            )
    return 0 if after["installed"] else 1


def build_operations(mode: str, args: argparse.Namespace) -> list[Operation]:
    project_roots = resolve_project_roots(args)
    operations: list[Operation] = []

    if mode != "init-projects":
        global_agents = expand_path(args.global_agents_path) or (
            default_codex_home() / "AGENTS.md"
        )
        operations.append(
            Operation(
                "codex global AGENTS.md",
                GLOBAL_AGENTS_TEMPLATE,
                global_agents,
                "file",
            )
        )
        skills_root = scoped_skills_root(args)
        for name, source in SKILL_SOURCES.items():
            target = skills_root / name
            operations.append(
                Operation(
                    f"global skill {name}",
                    source,
                    target,
                    "dir",
                    source.resolve() == target.resolve(),
                )
            )

    for project_root in project_roots:
        if not args.skip_project_agents:
            operations.append(
                Operation(
                    f"project AGENTS.md [{project_root}]",
                    PROJECT_AGENTS_TEMPLATE,
                    project_root / "AGENTS.md",
                    "file",
                )
            )
        operations.append(
            Operation(
                f"project .gitignore [{project_root}]",
                PROJECT_GITIGNORE_TEMPLATE,
                project_root / ".gitignore",
                "ensure-file-block",
            )
        )

    return operations


def build_bundled_skill_migration_plan(
    mode: str, args: argparse.Namespace
) -> dict[str, object]:
    if mode == "init-projects":
        return {
            "mode": "bundled-skill-rename",
            "status": "skipped",
            "reason": "init-projects does not inspect or modify global skills.",
        }

    skills_root = scoped_skills_root(args)
    migrations: list[dict[str, object]] = []
    conflicts: list[dict[str, object]] = []
    for canonical_name, legacy_names in BUNDLED_SKILL_LEGACY_NAMES.items():
        canonical_target = skills_root / canonical_name
        legacy_targets: list[Path] = []
        for legacy_name in legacy_names:
            legacy_target = skills_root / legacy_name
            if not legacy_target.exists():
                continue
            actual_name = (
                read_skill_frontmatter_name(legacy_target / "SKILL.md")
                if legacy_target.is_dir()
                else None
            )
            if actual_name != legacy_name:
                conflicts.append(
                    {
                        "path": str(legacy_target),
                        "expectedName": legacy_name,
                        "actualName": actual_name,
                    }
                )
                continue
            legacy_targets.append(legacy_target)
        migrations.append(
            {
                "canonicalName": canonical_name,
                "canonicalTarget": str(canonical_target),
                "legacyTargets": [str(path) for path in legacy_targets],
            }
        )
    return {
        "mode": "bundled-skill-rename",
        "status": (
            "blocked"
            if conflicts
            else "required"
            if any(item["legacyTargets"] for item in migrations)
            else "not-needed"
        ),
        "reason": (
            "A legacy path exists but its Skill identity does not match the "
            "legacy name; no files were changed."
            if conflicts
            else None
        ),
        "targetDir": str(skills_root),
        "migrations": migrations,
        "conflicts": conflicts,
    }


def run_bundled_skill_migration(plan: dict[str, object]) -> list[dict[str, object]]:
    if plan.get("status") == "skipped":
        return []

    results: list[dict[str, object]] = []
    for raw_item in cast(list[dict[str, object]], plan.get("migrations") or []):
        canonical_name = str(raw_item["canonicalName"])
        canonical_target = Path(str(raw_item["canonicalTarget"]))
        legacy_targets = [
            Path(str(path)) for path in raw_item.get("legacyTargets") or []
        ]
        if read_skill_frontmatter_name(canonical_target / "SKILL.md") != canonical_name:
            results.append(
                {
                    "name": canonical_name,
                    "status": "failed",
                    "target": str(canonical_target),
                    "error": "canonical bundled Skill is missing or has invalid frontmatter",
                }
            )
            continue

        for legacy_target in legacy_targets:
            try:
                remove_existing_target(legacy_target)
            except OSError as exc:
                results.append(
                    {
                        "name": legacy_target.name,
                        "status": "failed",
                        "target": str(legacy_target),
                        "canonicalTarget": str(canonical_target),
                        "error": str(exc),
                    }
                )
                continue
            results.append(
                {
                    "name": legacy_target.name,
                    "status": "removed",
                    "target": str(legacy_target),
                    "canonicalTarget": str(canonical_target),
                }
            )
    return results


def print_bundled_skill_migration_report(results: list[dict[str, object]]) -> None:
    print("\nBundled Skill rename migration report:")
    if not results:
        print("- none")
        return
    for item in results:
        print(f"- {item['name']}: {item['status']}")
        print(f"  target: {item['target']}")
        if item.get("canonicalTarget"):
            print(f"  canonical target: {item['canonicalTarget']}")
        if item.get("error"):
            print(f"  error: {item['error']}")


def print_plan(
    mode: str,
    operations: list[Operation],
    as_json: bool,
    bundled_migration_plan: dict[str, object] | None = None,
    external_migration_plan: dict[str, object] | None = None,
    global_skills_dir: Path | None = None,
    global_skills_dir_source: str | None = None,
) -> None:
    payload = {
        "mode": mode,
        "platform": platform.system() or sys.platform,
        "skillDir": str(SKILL_DIR),
        "globalSkillsDir": str(global_skills_dir) if global_skills_dir else None,
        "globalSkillsDirSource": global_skills_dir_source,
        "operations": [
            {
                "label": op.label,
                "source": str(op.source),
                "target": str(op.target),
                "kind": op.kind,
                "targetExists": op.target.exists(),
                "sameLocation": op.same_location,
            }
            for op in operations
        ],
    }
    if bundled_migration_plan:
        payload["bundledMigration"] = bundled_migration_plan
    if external_migration_plan:
        payload["externalMigration"] = external_migration_plan
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print(f"Mode: {mode}")
    print(f"Platform: {payload['platform']}")
    for item in payload["operations"]:
        if item["sameLocation"]:
            exists = "same source and target"
        else:
            exists = "exists" if item["targetExists"] else "missing"
        print(f"- {item['label']}: {item['target']} ({exists})")
    if bundled_migration_plan:
        print("\nBundled Skill rename migration:")
        print(f"- status: {bundled_migration_plan['status']}")
        if bundled_migration_plan.get("targetDir"):
            print(f"- target skills dir: {bundled_migration_plan['targetDir']}")
        if bundled_migration_plan.get("reason"):
            print(f"- reason: {bundled_migration_plan['reason']}")
        for item in bundled_migration_plan.get("migrations") or []:
            if item.get("legacyTargets"):
                print(
                    "- remove legacy: "
                    + ", ".join(str(path) for path in item["legacyTargets"])
                )
        for item in bundled_migration_plan.get("conflicts") or []:
            print(
                "- legacy identity conflict: "
                f"{item['path']} (expected {item['expectedName']}, "
                f"got {item.get('actualName') or '<missing>'})"
            )
    if external_migration_plan:
        print("\nExternal mattpocock migration:")
        print(f"- status: {external_migration_plan['status']}")
        if external_migration_plan.get("targetDir"):
            print(f"- target skills dir: {external_migration_plan['targetDir']}")
        if external_migration_plan.get("reason"):
            print(f"- reason: {external_migration_plan['reason']}")
        if external_migration_plan.get("detectedLegacy"):
            print(
                "- detected legacy: "
                + ", ".join(
                    str(name) for name in external_migration_plan["detectedLegacy"]
                )
            )
        if external_migration_plan.get("detectedCanonical"):
            print(
                "- detected canonical: "
                + ", ".join(
                    str(name) for name in external_migration_plan["detectedCanonical"]
                )
            )
        if external_migration_plan.get("requiredCanonical"):
            print(
                "- required canonical: "
                + ", ".join(
                    str(name) for name in external_migration_plan["requiredCanonical"]
                )
            )
        if external_migration_plan.get("removeLegacy"):
            print(
                "- remove legacy: "
                + ", ".join(
                    str(name) for name in external_migration_plan["removeLegacy"]
                )
            )


def operation_allows_existing_target(operation: Operation) -> bool:
    return operation.kind == "ensure-file-block"


def operation_result(
    operation: Operation,
    status: str,
    action: str,
    *,
    backup: Path | None = None,
    reason: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "label": operation.label,
        "target": str(operation.target),
        "kind": operation.kind,
        "status": status,
        "action": action,
    }
    if backup:
        result["backup"] = str(backup)
    if reason:
        result["reason"] = reason
    return result


def print_operation_report(
    results: list[dict[str, object]], heading: str = "Operation report"
) -> None:
    print(f"\n{heading}:")
    if not results:
        print("- none")
        return
    for item in results:
        print(f"- {item['label']}: {item['status']}")
        print(f"  target: {item['target']}")
        print(f"  action: {item['action']}")
        if item.get("backup"):
            print(f"  backup: {item['backup']}")
        if item.get("reason"):
            print(f"  reason: {item['reason']}")


def print_external_migration_report(results: list[dict[str, object]]) -> None:
    print("\nExternal mattpocock migration report:")
    if not results:
        print("- none")
        return
    for item in results:
        label = item.get("name") or item.get("repo") or "migration"
        print(f"- {label}: {item['status']}")
        if item.get("phase"):
            print(f"  phase: {item['phase']}")
        if item.get("target"):
            print(f"  target: {item['target']}")
        if item.get("backup"):
            print(f"  backup: {item['backup']}")
        if item.get("error"):
            print(f"  error: {item['error']}")
        if item.get("reason"):
            print(f"  reason: {item['reason']}")


def ensure_confirmed(args: argparse.Namespace, mode: str) -> None:
    if mode == "plan":
        return
    if not args.yes:
        raise SystemExit(
            "Refusing to change files without --yes. Run plan first, then rerun with --yes."
        )


def run(mode: str, args: argparse.Namespace) -> int:
    if mode == "check":
        print_check_results(build_check_results(args), args.json)
        return 0
    if mode == "check-projects":
        print_projects_check_results(build_projects_check_results(args), args.json)
        return 0
    if mode == "check-agent-cli":
        print_agent_cli_check(check_agent_cli(args.platform), args.json)
        return 0
    if mode == "ensure-npm":
        return ensure_npm(args)
    if mode == "install-agent-cli":
        return install_agent_cli(args)
    if mode == "install-rtk":
        return install_rtk(args)
    if mode == "install-caveman":
        return install_caveman(args)
    if mode == "install-java":
        return install_java(args)
    if mode == "install-maestro":
        return install_maestro(args)
    if mode == "install-playwright-cli":
        return install_playwright_cli(args)
    if mode == "install-external-skills":
        return install_external_skills(args)
    if mode == "migrate-external-skills":
        return migrate_external_skills(args)
    if mode == "promote-external-skills-stable":
        return promote_external_skills_stable(args)

    if mode in {"init", "reset"} and not args.json:
        print_check_results(build_check_results(args), False)
        print("")

    global_skills_dir, global_skills_dir_source = resolve_global_skills_dir(
        getattr(args, "global_skills_dir", None)
    )
    operations = build_operations(mode, args)
    bundled_migration_plan = build_bundled_skill_migration_plan(mode, args)
    external_migration_plan = (
        {
            "mode": "mattpocock-external-migration",
            "status": "skipped",
            "reason": "init-projects does not inspect or modify global skills.",
        }
        if mode == "init-projects"
        else build_external_migration_plan(args)
    )
    print_plan(
        mode,
        operations,
        args.json,
        bundled_migration_plan,
        external_migration_plan,
        global_skills_dir,
        global_skills_dir_source,
    )
    if mode == "plan":
        return 0

    ensure_confirmed(args, mode)
    if bundled_migration_plan.get("status") == "blocked":
        print(
            "Bundled Skill rename migration blocked: legacy Skill identity "
            "does not match the configured legacy name.",
            file=sys.stderr,
        )
        return 4

    external_identity_failures = (
        external_migration_identity_failures(external_migration_plan)
        if external_migration_plan.get("status") == "planned"
        else []
    )
    if external_identity_failures:
        print(
            "External mattpocock migration blocked: legacy Skill identity "
            "does not match the configured legacy name.",
            file=sys.stderr,
        )
        for item in external_identity_failures:
            label = item.get("name") or item.get("repo") or "migration"
            print(f"- {label}: {item.get('error', 'unknown failure')}", file=sys.stderr)
        return 4

    if mode in {"init", "reset"}:
        external_install_status = install_required_external_skills(args)
        if external_install_status != 0:
            print(
                "Required global external Skill installation failed.", file=sys.stderr
            )
            return 4

    active_operations = [op for op in operations if not op.same_location]
    conflicts = [
        op
        for op in active_operations
        if op.target.exists() and not operation_allows_existing_target(op)
    ]

    backups: list[tuple[Path, Path]] = []
    backup_by_target: dict[Path, Path] = {}
    for op in conflicts:
        if op.kind != "file":
            continue
        backup = backup_path(op.target)
        op.target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(op.target), str(backup))
        backups.append((op.target, backup))
        backup_by_target[op.target] = backup

    operation_results: list[dict[str, object]] = []
    for op in active_operations:
        try:
            action = copy_operation(op)
            failures = verify_operation(op)
            if failures:
                operation_results.append(
                    operation_result(
                        op,
                        "failed",
                        action,
                        backup=backup_by_target.get(op.target),
                        reason="verification failed: " + ", ".join(failures[:20]),
                    )
                )
                continue

            status = "skipped" if action.startswith("skipped") else "success"
            operation_results.append(
                operation_result(
                    op,
                    status,
                    action,
                    backup=backup_by_target.get(op.target),
                )
            )
        except Exception as exc:  # noqa: BLE001 - report each file operation failure with context.
            operation_results.append(
                operation_result(
                    op,
                    "failed",
                    "error",
                    backup=backup_by_target.get(op.target),
                    reason=str(exc),
                )
            )

    failed_operations = [
        item for item in operation_results if item["status"] == "failed"
    ]

    if backups:
        print("Backups:")
        for original, backup in backups:
            print(f"- {original} -> {backup}")

    if not args.json:
        print_operation_report(operation_results)

    if failed_operations:
        print("Verification failed:", file=sys.stderr)
        for item in failed_operations:
            print(
                f"- {item['label']}: {item.get('reason', 'unknown failure')}",
                file=sys.stderr,
            )
        return 3

    bundled_migration_results = run_bundled_skill_migration(bundled_migration_plan)
    failed_bundled_migrations = [
        item for item in bundled_migration_results if item["status"] == "failed"
    ]
    if not args.json:
        print_bundled_skill_migration_report(bundled_migration_results)
    if failed_bundled_migrations:
        print("Bundled Skill rename migration failed:", file=sys.stderr)
        for item in failed_bundled_migrations:
            print(
                f"- {item['name']}: {item.get('error', 'unknown failure')}",
                file=sys.stderr,
            )
        return 4

    migration_results = run_external_migration(external_migration_plan)
    failed_migrations = [
        item for item in migration_results if item["status"] == "failed"
    ]
    if not args.json:
        print_external_migration_report(migration_results)
    if failed_migrations:
        print("External mattpocock migration failed:", file=sys.stderr)
        for item in failed_migrations:
            label = item.get("name") or item.get("repo") or "migration"
            print(f"- {label}: {item.get('error', 'unknown failure')}", file=sys.stderr)
        return 4

    trellis_report = run_trellis_project_setup(mode, args)
    if args.json:
        print(
            json.dumps(
                {"trellisProjectSetup": trellis_report}, indent=2, ensure_ascii=False
            )
        )
    else:
        print_trellis_project_setup_report(trellis_report)
    if trellis_report.get("status") in {"blocked", "needs-user"}:
        return 2
    if trellis_report.get("status") == "failed":
        return 5
    if trellis_report.get("status") == "bootstrap-required":
        return 6

    print("Verification passed.")
    if not args.json:
        if mode == "init-projects":
            print_projects_check_results(build_projects_check_results(args), False)
        else:
            final_check = build_check_results(args)
            print_installation_report(
                final_check["installationReport"], "Final installation report"
            )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install or reset SBTD workflow AGENTS and skills."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    for mode in ("check", "plan", "init", "reset", "init-projects"):
        sub = subparsers.add_parser(mode)
        sub.add_argument(
            "--projects-root",
            required=mode == "init-projects",
            help="Comma-separated absolute project root paths.",
        )
        sub.add_argument(
            "--skip-project-agents",
            action="store_true",
            help="Do not install project AGENTS.md.",
        )
        sub.add_argument(
            "--global-agents-path", help="Override Codex global AGENTS.md path."
        )
        sub.add_argument(
            "--global-skills-dir", help="Override global skills directory."
        )
        sub.add_argument(
            "--yes", action="store_true", help="Allow init/reset to write files."
        )
        sub.add_argument(
            "--json", action="store_true", help="Print machine-readable plan."
        )
        sub.add_argument(
            "--trellis-user",
            help="Developer username for `trellis init -u` when the target project has no .trellis/.",
        )
        sub.add_argument(
            "--trellis-platform",
            action="append",
            default=[],
            help=(
                "Trellis init platform flag without leading dashes, repeatable or comma-separated "
                f"(supported: {', '.join(TRELLIS_INIT_PLATFORMS)})."
            ),
        )
        sub.add_argument(
            "--skip-trellis-init",
            action="store_true",
            help="Do not run the post-install Trellis init check for init/reset.",
        )
        sub.add_argument(
            "--skip-trellis-bootstrap",
            action="store_true",
            help="Do not report the post-install Trellis bootstrap task handoff for init/reset.",
        )

    project_check = subparsers.add_parser("check-projects")
    project_check.add_argument(
        "--projects-root",
        required=True,
        help="Comma-separated absolute project root paths.",
    )
    project_check.add_argument(
        "--json", action="store_true", help="Print machine-readable project checks."
    )

    install = subparsers.add_parser("install-external-skills")
    install.add_argument(
        "--skills",
        help="Comma-separated external skill names to install. Use 'all' for every known external skill.",
    )
    install.add_argument(
        "--all",
        action="store_true",
        help="Install every known external referenced skill.",
    )
    install.add_argument(
        "--scope",
        choices=("global",),
        default="global",
        help="Install into the global skills directory.",
    )
    install.add_argument(
        "--source",
        choices=("auto", "upstream", "stable"),
        default="auto",
        help=(
            "External Skill source policy: auto and stable use the vendored stable set; "
            "upstream is an explicit opt-in with no fallback."
        ),
    )
    install.add_argument(
        "--global-skills-dir", help="Override global skills directory."
    )
    install.add_argument(
        "--replace",
        action="store_true",
        help="Compatibility flag; replacement now uses a temporary transactional rollback backup.",
    )
    install.add_argument(
        "--yes", action="store_true", help="Allow external skill installation."
    )
    install.add_argument(
        "--json", action="store_true", help="Print machine-readable plan and results."
    )

    migrate = subparsers.add_parser("migrate-external-skills")
    migrate.add_argument(
        "--scope",
        choices=("global",),
        default="global",
        help="Migrate legacy external Skills in the global skills directory.",
    )
    migrate.add_argument(
        "--source",
        choices=("auto", "upstream", "stable"),
        default="auto",
        help=(
            "Canonical replacement source: auto and stable use the vendored stable "
            "set; upstream is an explicit opt-in with no fallback."
        ),
    )
    migrate.add_argument(
        "--global-skills-dir", help="Override global skills directory."
    )
    migrate.add_argument(
        "--yes", action="store_true", help="Allow external Skill migration."
    )
    migrate.add_argument(
        "--json", action="store_true", help="Print machine-readable migration results."
    )

    promote = subparsers.add_parser("promote-external-skills-stable")
    promote.add_argument(
        "--repository",
        required=True,
        help="Repository id from the stable External Skills manifest.",
    )
    promote.add_argument(
        "--revision",
        required=True,
        help="Full 40-character lowercase upstream commit SHA to promote.",
    )
    promote.add_argument(
        "--stable-set",
        required=True,
        help="New Onboard stable set identifier, for example 2026-07-11.2.",
    )
    promote.add_argument(
        "--yes", action="store_true", help="Allow stable snapshot replacement."
    )
    promote.add_argument(
        "--json", action="store_true", help="Print machine-readable plan and results."
    )

    npm = subparsers.add_parser("ensure-npm")
    npm.add_argument(
        "--yes",
        action="store_true",
        help="Install nvm and Node.js LTS when npm is missing.",
    )
    npm.add_argument(
        "--json", action="store_true", help="Print machine-readable results."
    )

    agent_check = subparsers.add_parser("check-agent-cli")
    agent_check.add_argument(
        "--platform",
        required=True,
        help="Target Agent platform: codex, claude, kimi, oh-my-pi, or omp.",
    )
    agent_check.add_argument(
        "--json", action="store_true", help="Print machine-readable results."
    )

    agent_install = subparsers.add_parser("install-agent-cli")
    agent_install.add_argument(
        "--platform",
        required=True,
        help="Target Agent platform: codex, claude, kimi, oh-my-pi, or omp.",
    )
    agent_install.add_argument(
        "--yes",
        action="store_true",
        help="Install the target Agent CLI globally from its official npm package after user confirmation.",
    )
    agent_install.add_argument(
        "--json", action="store_true", help="Print machine-readable results."
    )

    rtk = subparsers.add_parser("install-rtk")
    rtk.add_argument(
        "--yes", action="store_true", help="Install rtk-ai/rtk when missing."
    )
    rtk.add_argument(
        "--replace-wrong",
        action="store_true",
        help="If an existing rtk command fails `rtk gain`, allow replacing it after user confirmation.",
    )
    rtk.add_argument(
        "--reinstall",
        action="store_true",
        help="Reinstall when rtk exists but `rtk gain` verification fails.",
    )
    rtk.add_argument(
        "--profile", help="Shell profile file to update with ~/.local/bin PATH."
    )
    rtk.add_argument(
        "--json", action="store_true", help="Print machine-readable results."
    )

    caveman = subparsers.add_parser("install-caveman")
    caveman.add_argument(
        "--agent",
        default="codex",
        help="Retained for compatibility; the official caveman installer selects the platform-specific install path.",
    )
    caveman.add_argument(
        "--global-skills-dir",
        help="Override global skills directory used for post-install verification.",
    )
    caveman.add_argument(
        "--yes",
        action="store_true",
        help="Install the caveman Codex skill after user confirmation.",
    )
    caveman.add_argument(
        "--json", action="store_true", help="Print machine-readable results."
    )

    java = subparsers.add_parser("install-java")
    java.add_argument(
        "--major",
        type=int,
        default=21,
        help="Temurin JDK major version to install. Must be 17 or higher; defaults to 21.",
    )
    java.add_argument(
        "--install-root",
        help="Directory that should contain the extracted Temurin JDK.",
    )
    java.add_argument(
        "--profile", help="Shell profile file to update with JAVA_HOME and PATH."
    )
    java.add_argument(
        "--force",
        action="store_true",
        help="Install even when an existing Java 17+ runtime is already available.",
    )
    java.add_argument(
        "--yes",
        action="store_true",
        help="Download and install the selected Temurin JDK after user confirmation.",
    )
    java.add_argument(
        "--json", action="store_true", help="Print machine-readable results."
    )

    maestro = subparsers.add_parser("install-maestro")
    maestro.add_argument(
        "--profile", help="Shell profile file to update with ~/.maestro/bin PATH."
    )
    maestro.add_argument(
        "--reinstall",
        action="store_true",
        help="Run the official installer even when a maestro command already exists but fails verification.",
    )
    maestro.add_argument(
        "--yes",
        action="store_true",
        help="Run the official Maestro installer after user confirmation.",
    )
    maestro.add_argument(
        "--json", action="store_true", help="Print machine-readable results."
    )

    playwright = subparsers.add_parser("install-playwright-cli")
    playwright.add_argument(
        "--project-root",
        required=True,
        help="Target project root where package.json exists.",
    )
    playwright.add_argument(
        "--reinstall",
        action="store_true",
        help="Run npm install even when Playwright project markers already exist.",
    )
    playwright.add_argument(
        "--skip-browsers",
        action="store_true",
        help="Install @playwright/test but skip `npx playwright install`.",
    )
    playwright.add_argument(
        "--yes",
        action="store_true",
        help="Install Playwright into the target project after user confirmation.",
    )
    playwright.add_argument(
        "--json", action="store_true", help="Print machine-readable results."
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return run(args.mode, args)


if __name__ == "__main__":
    raise SystemExit(main())
