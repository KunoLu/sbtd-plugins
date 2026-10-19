"""Read-only OMP 18.2.5 MCP source discovery for SBTD deployment.

This module mirrors the pinned host's configuration selection without importing
or launching it. It parses declared files only; environment expansion,
provider commands, and every write stay out of this layer.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn

import onboard_contracts as contracts
from sbtd_migration_files import read_file, snapshot
from sbtd_omp_wiring import _servers, _strict_json, analyze_omp_configuration
from sbtd_project import (
    TaskDataError,
    _build_safe_loader,
    require_dependency,
    validate_json_compatible,
)

__all__ = ["active_omp_paths", "analyze_omp_sources", "discover_omp_sources"]

_PROFILE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_RESERVED_PROFILE = re.compile(
    r"^(?:CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\..*)?$", re.IGNORECASE
)


def _fail(code: str, message: str) -> NoReturn:
    raise contracts.ContractError(code, message)


def _profile(environ: Mapping[str, str]) -> str | None:
    raw = (
        environ.get("OMP_PROFILE")
        if "OMP_PROFILE" in environ
        else environ.get("PI_PROFILE")
    )
    value = (raw or "").strip()
    if not value or value == "default":
        return None
    if (
        value in {".", ".."}
        or value.endswith(".")
        or not _PROFILE_NAME.fullmatch(value)
        or _RESERVED_PROFILE.fullmatch(value)
    ):
        _fail("invalid-config", "the active OMP profile name is invalid")
    return value


def active_omp_paths(
    *, home: Path, environ: Mapping[str, str]
) -> dict[str, Path | str | None]:
    """Resolve the active OMP user MCP target without creating directories."""
    if not home.is_absolute():
        _fail("invalid-argument", "the user home must be absolute")
    profile = _profile(environ)
    config_name = environ.get("PI_CONFIG_DIR") or ".omp"
    if (
        not config_name
        or Path(config_name).is_absolute()
        or ".." in Path(config_name).parts
    ):
        _fail("invalid-config", "the OMP config directory override is invalid")
    config_root = home / config_name
    if profile is not None:
        config_root = config_root / "profiles" / profile
        agent = config_root / "agent"
    else:
        override = environ.get("PI_CODING_AGENT_DIR", "")
        derived = config_root / "profiles" / (environ.get("PI_PROFILE") or "") / "agent"
        agent = (
            Path(override).expanduser().resolve()
            if override.strip() and Path(override).expanduser().resolve() != derived
            else config_root / "agent"
        )
    return {
        "config_root": config_root,
        "agent_dir": agent,
        "target": agent / "mcp.json",
        "profile": profile,
    }


def _read_snapshot(path: Path, inputs: dict[str, dict[str, Any]]) -> bytes | None:
    state = snapshot(path)
    if state["type"] == "directory":
        _fail("invalid-config", "an OMP configuration source is a directory")
    key = str(path)
    previous = inputs.get(key)
    if previous is not None and previous["state"] != state:
        _fail("state-conflict", "one OMP configuration source has conflicting states")
    inputs[key] = {"path": key, "state": state}
    if state["type"] != "file":
        return None
    return read_file(path, state)


def _yaml_settings(raw: bytes) -> dict[str, Any]:
    try:
        yaml = require_dependency("yaml", "PyYAML")
    except TaskDataError:
        _fail(
            "validator-unavailable",
            "install the declared YAML dependency before OMP analysis",
        )
    try:
        value = yaml.load(
            raw.decode("utf-8", errors="strict"), Loader=_build_safe_loader(yaml)
        )
        validate_json_compatible(value, "OMP settings")
    except (UnicodeDecodeError, RecursionError, TaskDataError, yaml.YAMLError):
        _fail("invalid-config", "the active OMP settings are not strict YAML")
    if value is None:
        return {}
    if not isinstance(value, dict):
        _fail("invalid-config", "the active OMP settings must be an object")
    return value


def _provider_settings(
    agent: Path, inputs: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    yml = agent / "config.yml"
    yaml_path = agent / "config.yaml"
    yml_raw = _read_snapshot(yml, inputs)
    yaml_raw = _read_snapshot(yaml_path, inputs)
    selected_raw = yml_raw if yml_raw is not None else yaml_raw
    settings = _yaml_settings(selected_raw) if selected_raw is not None else {}
    result: dict[str, Any] = {
        "enabled": set(),
        "disabled": set(),
        "disabled_extensions": set(),
    }
    for source, target in (
        ("enabledProviders", "enabled"),
        ("disabledProviders", "disabled"),
        ("disabledExtensions", "disabled_extensions"),
    ):
        value = settings.get(source, [])
        if not isinstance(value, list) or any(
            not isinstance(item, str) for item in value
        ):
            _fail("invalid-config", "OMP provider settings are malformed")
        result[target] = set(value)
    if "native" in result["disabled"]:
        _fail("invalid-config", "the active OMP native provider is disabled")
    return result


def _guard_dynamic_sources(
    roots: Sequence[Path],
    agent: Path,
    inputs: dict[str, dict[str, Any]],
    environ: Mapping[str, str],
    *,
    claude_user_settings: Path | None,
) -> None:
    if environ.get("PI_CONFIG_FILES", "").strip():
        _fail("invalid-config", "OMP configuration overlays cannot be safely analyzed")
    if _read_snapshot(agent / ".env", inputs) is not None:
        _fail("invalid-config", "the active OMP agent environment is dynamic")
    if _read_snapshot(agent / "settings.json", inputs) is not None:
        _fail("invalid-config", "legacy OMP settings cannot be safely analyzed")
    if claude_user_settings is not None:
        raw = _read_snapshot(claude_user_settings, inputs)
        if raw is not None:
            settings = _strict_json(raw, "Claude user settings")
            if not isinstance(settings, dict):
                _fail("invalid-config", "Claude user settings must be an object")
            if "disabledExtensions" in settings:
                _fail(
                    "invalid-config",
                    "Claude user extension settings cannot be safely analyzed",
                )
    for root in roots:
        for path, parser in (
            (root / ".omp/config.yml", "yaml"),
            (root / ".omp/config.yaml", "yaml"),
            (root / ".omp/settings.json", "json"),
            (root / ".claude/settings.json", "json"),
        ):
            raw = _read_snapshot(path, inputs)
            if raw is None:
                continue
            settings = (
                _yaml_settings(raw)
                if parser == "yaml"
                else _strict_json(raw, "OMP project settings")
            )
            if not isinstance(settings, dict):
                _fail("invalid-config", "OMP project settings must be an object")
            if {
                "enabledProviders",
                "disabledProviders",
                "disabledExtensions",
            } & settings.keys():
                _fail(
                    "invalid-config",
                    "OMP project provider settings cannot be safely analyzed",
                )


def _user_enabled(
    provider: str, settings: Mapping[str, set[str]], environ: Mapping[str, str]
) -> bool:
    if provider in settings["disabled"]:
        return False
    if provider == "claude" and environ.get("CLAUDE_CONFIG_DIR", "").strip():
        return True
    return bool(settings["enabled"] & {provider, "*", "all"})


def _json_servers(raw: bytes, label: str) -> dict[str, Mapping[str, Any]]:
    document = _strict_json(raw, label)
    servers = _servers(document, label)
    result: dict[str, Mapping[str, Any]] = {}
    for name, server in servers.items():
        enabled = server.get("enabled")
        if isinstance(enabled, str):
            lowered = enabled.lower()
            if lowered in {"false", "0"}:
                enabled = False
            elif lowered in {"true", "1"}:
                enabled = True
        if enabled is not None and not isinstance(enabled, bool):
            _fail("invalid-config", f"the {label} MCP enabled flag is malformed")
        converted = dict(server)
        result[name] = {**converted, "enabled": enabled is not False}
    return result


def _toml_servers(raw: bytes, path: Path) -> dict[str, Mapping[str, Any]]:
    try:
        import tomlkit
        from tomlkit.exceptions import TOMLKitError
    except ImportError:
        _fail(
            "validator-unavailable",
            "install the declared TOML dependency before OMP analysis",
        )
    try:
        document = tomlkit.parse(raw.decode("utf-8", errors="strict")).unwrap()
    except (ValueError, RecursionError, TOMLKitError, UnicodeDecodeError):
        _fail("invalid-toml", "an inherited Codex MCP configuration is malformed")
    servers = document.get("mcp_servers", {})
    if not isinstance(servers, dict):
        _fail("invalid-config", "an inherited Codex MCP section is malformed")
    result: dict[str, Mapping[str, Any]] = {}
    for name, server in servers.items():
        if not isinstance(name, str) or not isinstance(server, dict):
            _fail("invalid-config", "an inherited Codex MCP server is malformed")
        if any(
            key in server
            for key in ("env_vars", "env_http_headers", "bearer_token_env_var")
        ):
            _fail(
                "invalid-config",
                "an inherited Codex MCP server uses dynamic environment input",
            )
        cwd = server.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            _fail("invalid-config", "an inherited Codex MCP cwd is malformed")
        resolved_cwd = (
            str((path.parent / cwd).resolve())
            if isinstance(cwd, str) and cwd and not os.path.isabs(cwd)
            else cwd
        )
        command = server.get("command")
        if command is not None and not isinstance(command, str):
            _fail("invalid-config", "an inherited Codex MCP command is malformed")
        if isinstance(command, str) and command and not os.path.isabs(command):
            base = Path(resolved_cwd) if isinstance(resolved_cwd, str) else path.parent
            command = str((base / command).resolve())
        args = server.get("args", [])
        env = server.get("env", {})
        if (
            not isinstance(args, list)
            or any(not isinstance(item, str) for item in args)
            or not isinstance(env, dict)
            or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in env.items()
            )
        ):
            _fail("invalid-config", "an inherited Codex MCP server is malformed")
        enabled = server.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            _fail("invalid-config", "an inherited Codex MCP enabled flag is malformed")
        result[name] = {
            "type": "http" if server.get("url") else "stdio",
            "command": command,
            "args": args,
            "cwd": resolved_cwd,
            "env": env,
            "enabled": enabled is not False,
        }
    return result


def _append_source(
    sources: list[dict[str, Any]],
    *,
    name: str,
    path: Path,
    enabled: bool,
    raw: bytes | None,
    parser: str,
) -> None:
    if raw is None:
        return
    servers = _json_servers(raw, name) if parser == "json" else _toml_servers(raw, path)
    if servers:
        sources.append(
            {"source": name, "path": str(path), "enabled": enabled, "servers": servers}
        )


def _guard_claude_plugin_sources(
    roots: Sequence[Path],
    home: Path,
    environ: Mapping[str, str],
    paths: Mapping[str, Path | str | None],
    inputs: dict[str, dict[str, Any]],
) -> None:
    # Pinned OMP discovers project and OMP-origin plugins without a user
    # provider opt-in. Until manifests are modeled, a registry is a conflict.
    config_name = environ.get("PI_CONFIG_DIR") or ".omp"
    override = environ.get("CLAUDE_CONFIG_DIR", "").strip()
    claude_root = (
        Path(override).expanduser().resolve() if override else home / ".claude"
    )
    config_root = paths["config_root"]
    assert isinstance(config_root, Path)
    registries = {
        claude_root / "plugins/installed_plugins.json",
        home / config_name / "plugins/installed_plugins.json",
        config_root / "plugins/installed_plugins.json",
    }
    xdg = environ.get("XDG_DATA_HOME", "")
    if xdg:
        xdg_root = Path(xdg).expanduser().resolve() / "omp"
        profile = paths["profile"]
        if isinstance(profile, str):
            xdg_root = xdg_root / "profiles" / profile
        registries.add(xdg_root / "plugins/installed_plugins.json")
    for root in roots:
        ancestry = (root, *root.parents)
        anchor = next(
            (path for path in ancestry if (path / config_name).is_dir()), None
        )
        if anchor is None:
            anchor = next((path for path in ancestry if (path / ".git").exists()), None)
        if anchor is not None:
            registries.add(anchor / config_name / "plugins/installed_plugins.json")
    for path in sorted(registries):
        if _read_snapshot(path, inputs) is not None:
            _fail("invalid-config", "Plugin MCP sources cannot be safely analyzed")


def discover_omp_sources(
    roots: Sequence[Path],
    *,
    home: Path,
    environ: Mapping[str, str],
) -> dict[str, Any]:
    """Return active target metadata and every source snapshot without writes."""
    paths = active_omp_paths(home=home, environ=environ)
    inputs: dict[str, dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    agent = paths["agent_dir"]
    assert isinstance(agent, Path)
    target = paths["target"]
    assert isinstance(target, Path)
    settings = _provider_settings(agent, inputs)
    _guard_claude_plugin_sources(roots, home, environ, paths, inputs)
    claude_override = environ.get("CLAUDE_CONFIG_DIR", "").strip()
    claude_dir = (
        Path(claude_override).expanduser().resolve()
        if claude_override
        else home / ".claude"
    )
    claude_json = (
        claude_dir / ".claude.json" if claude_override else home / ".claude.json"
    )
    claude_enabled = _user_enabled("claude", settings, environ)
    _guard_dynamic_sources(
        roots,
        agent,
        inputs,
        environ,
        claude_user_settings=claude_dir / "settings.json" if claude_enabled else None,
    )

    codex_project_enabled = "codex" not in settings["disabled"]
    claude_project_enabled = "claude" not in settings["disabled"]
    codex_user = home / ".codex/config.toml"
    codex_raw = None
    if _user_enabled("codex", settings, environ):
        codex_raw = _read_snapshot(codex_user, inputs)
    _append_source(
        sources,
        name="codex-user",
        path=codex_user,
        enabled=True,
        raw=codex_raw,
        parser="toml",
    )
    claude_raw: dict[Path, bytes | None] = {}
    if claude_enabled:
        claude_raw = {
            path: _read_snapshot(path, inputs)
            for path in (claude_json, claude_dir / "mcp.json")
        }
    user_alternate_raw = _read_snapshot(agent / ".mcp.json", inputs)
    if user_alternate_raw is not None:
        _append_source(
            sources,
            name="native-user-alternate",
            path=agent / ".mcp.json",
            enabled=True,
            raw=user_alternate_raw,
            parser="json",
        )
    for name, path in (
        ("claude-user-json", claude_json),
        ("claude-user", claude_dir / "mcp.json"),
    ):
        raw = claude_raw.get(path)
        added = len(sources)
        _append_source(
            sources, name=name, path=path, enabled=True, raw=raw, parser="json"
        )
        if len(sources) != added:
            break

    for root in roots:
        root = root.resolve(strict=True)
        codex_project = root / ".codex/config.toml"
        _append_source(
            sources,
            name="codex-project",
            path=codex_project,
            enabled=codex_project_enabled,
            raw=_read_snapshot(codex_project, inputs),
            parser="toml",
        )
        claude_project = (root / ".claude/.mcp.json", root / ".claude/mcp.json")
        project_raw = [(path, _read_snapshot(path, inputs)) for path in claude_project]
        for path, raw in project_raw:
            added = len(sources)
            _append_source(
                sources,
                name="claude-project",
                path=path,
                enabled=claude_project_enabled,
                raw=raw,
                parser="json",
            )
            if len(sources) != added:
                break
        for name, path in (
            ("native-project", root / ".omp/mcp.json"),
            ("native-project", root / ".omp/.mcp.json"),
        ):
            _append_source(
                sources,
                name=name,
                path=path,
                enabled=True,
                raw=_read_snapshot(path, inputs),
                parser="json",
            )
    return {
        "target": str(target),
        "profile": paths["profile"],
        "config_root": str(paths["config_root"]),
        "agent_dir": str(agent),
        "inputs": [inputs[key] for key in sorted(inputs)],
        "sources": sources,
        "disabled_extensions": sorted(settings["disabled_extensions"]),
    }


def analyze_omp_sources(
    roots: Sequence[Path],
    bindings: Sequence[Mapping[str, Any]],
    *,
    home: Path,
    environ: Mapping[str, str],
) -> dict[str, Any]:
    """Return source discovery plus the desired-binding target analysis."""
    discovered = discover_omp_sources(roots, home=home, environ=environ)
    discovered["analysis"] = analyze_omp_configuration(
        Path(discovered["target"]),
        bindings,
        discovered["sources"],
        disabled_extensions=discovered["disabled_extensions"],
    )
    return discovered
