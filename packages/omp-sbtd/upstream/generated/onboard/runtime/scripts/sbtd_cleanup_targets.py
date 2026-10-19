"""Detection and execution for post-migration legacy cleanup targets.

This module is the single implementation of the expanded legacy cleanup
scope: the project ``.trellis`` directory (removed through the vendor
``tl uninstall`` command, never a manual recursive delete), the retired
global ``trellis-workflow`` / ``trellis-channel`` Skills (identity-proven
directory removal, not a v1.0.15 checksum pin), the project ``.gitnexus``
directory, ``gitnexus`` MCP server entries in the Codex / Claude / Kimi /
OMP user-level configurations, and the legacy ``TRELLIS`` / ``gitnexus``
marker blocks inside a project ``AGENTS.md``. The retired-Skill detector's
default closed set stays trellis-only; the nine retired GitNexus Skills in
``GITNEXUS_SKILL_NAMES`` (exact identities, never wildcard) are detected
only when a caller explicitly opts into ``RETIRED_SKILL_NAMES``.

Every detection returns JSON-safe dictionaries so both the sealed
migration batch path and the fresh ``cleanup-legacy`` path can seal and
display the same candidates. Deletions always happen after the caller has
preserved a private backup; this module never deletes without being told
to execute, and never touches the GitNexus npm package or the global
``~/.gitnexus`` data directory.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

TRELLIS_SKILL_NAMES = ("trellis-channel", "trellis-workflow")

# Retired GitNexus Skills: exact directory identities, never a prefix or
# wildcard match. The default detection closed set stays trellis-only so
# sealed migration batches and historical plans keep their exact semantics;
# the fresh cleanup-legacy path opts into the combined set explicitly.
GITNEXUS_SKILL_NAMES = (
    "gitnexus-cli",
    "gitnexus-debugging",
    "gitnexus-exploring",
    "gitnexus-guide",
    "gitnexus-impact-analysis",
    "gitnexus-pdg-query",
    "gitnexus-pr-review",
    "gitnexus-refactoring",
    "gitnexus-taint-analysis",
)
RETIRED_SKILL_NAMES = TRELLIS_SKILL_NAMES + GITNEXUS_SKILL_NAMES

_MARKER_PAIRS = (
    ("<!-- TRELLIS:START -->", "<!-- TRELLIS:END -->"),
    ("<!-- gitnexus:start -->", "<!-- gitnexus:end -->"),
)


# ---------------------------------------------------------------------------
# AGENTS.md legacy marker blocks
# ---------------------------------------------------------------------------


def _marker_events(raw: bytes) -> list[tuple[int, str, str]]:
    from markdown_it import MarkdownIt

    tokens = MarkdownIt("commonmark").parse(raw.decode("utf-8"))
    comment_lines = {
        token.map[0] for token in tokens if token.type == "html_block" and token.map
    }
    events: list[tuple[int, str, str]] = []
    position = 0
    for number, line in enumerate(raw.splitlines(keepends=True)):
        content = line.rstrip(b"\r\n")
        if number in comment_lines:
            for start, end in _MARKER_PAIRS:
                if content == start.encode():
                    events.append((position, "start", start))
                elif content == end.encode():
                    events.append((position, "end", end))
        position += len(line)
    return events


def _marker_spans(raw: bytes) -> list[tuple[int, int, tuple[str, str]]]:
    """Return disjoint unique marker spans, rejecting ambiguous ownership."""
    events = _marker_events(raw)
    if not events:
        return []
    spans: list[tuple[int, int, tuple[str, str]]] = []
    open_stack: list[tuple[int, tuple[str, str]]] = []
    for position, kind, token in events:
        pair = next(pair for pair in _MARKER_PAIRS if token in pair)
        if kind == "start":
            if open_stack:
                raise ValueError(f"nested or duplicated marker {pair[0]}")
            open_stack.append((position, pair))
            continue
        if not open_stack:
            raise ValueError(f"unmatched marker {pair[1]}")
        open_position, open_pair = open_stack[-1]
        if open_pair != pair:
            raise ValueError(f"interleaved markers {open_pair[0]} and {pair[1]}")
        open_stack.pop()
        spans.append((open_position, position + len(pair[1].encode()), pair))
    if open_stack:
        raise ValueError(f"unmatched marker {open_stack[-1][1][0]}")
    seen_pairs: set[tuple[str, str]] = set()
    for _, _, pair in spans:
        if pair in seen_pairs:
            raise ValueError(f"duplicated marker pair {pair[0]}")
        seen_pairs.add(pair)
    spans.sort()
    return spans


def detect_marker_blocks(raw: bytes) -> dict[str, Any]:
    try:
        spans = _marker_spans(raw)
    except ValueError as error:
        return {"status": "malformed", "reason": str(error)}
    if not spans:
        return {"status": "none"}
    return {"status": "removable", "removals": len(spans)}


def remove_marker_blocks(raw: bytes) -> bytes:
    spans = _marker_spans(raw)
    result = raw
    for start, end, _pair in reversed(spans):
        stop = end
        if result[stop : stop + 2] == b"\r\n":
            stop += 2
        elif result[stop : stop + 1] == b"\n":
            stop += 1
        result = result[:start] + result[stop:]
    return result


# ---------------------------------------------------------------------------
# Retired Trellis Skill identity
# ---------------------------------------------------------------------------


def _frontmatter_name(content: bytes) -> str | None:
    from sbtd_project import TaskDataError, _load_safe_yaml

    try:
        lines = content.decode("utf-8").splitlines()
        if not lines or lines[0] != "---":
            return None
        end = lines.index("---", 1)
        metadata = _load_safe_yaml("\n".join(lines[1:end]), "legacy Skill identity")
        return metadata.get("name") if isinstance(metadata, dict) else None
    except (UnicodeDecodeError, ValueError, TaskDataError):
        return None


def skill_identity_error(target: Path, name: str) -> str | None:
    """Prove a retired Skill identity without any version checksum pin."""
    if (
        any(path.is_symlink() for path in (target, *target.parents))
        or not target.is_dir()
    ):
        return f"legacy target is not a regular Skill directory: {target}"
    skill_md = target / "SKILL.md"
    if skill_md.is_symlink() or not skill_md.is_file():
        return f"legacy target has no regular SKILL.md: {target}"
    try:
        actual = _frontmatter_name(skill_md.read_bytes())
    except OSError:
        return f"legacy target SKILL.md cannot be read: {target}"
    if actual != name:
        return (
            f"legacy Skill identity conflict: expected {name}, "
            f"got {actual or '<missing>'}: {target}"
        )
    return None


def _retired_names(retired: Iterable[str]) -> list[str]:
    if isinstance(retired, (str, bytes)):
        raise TypeError("retired Skill identities must be an iterable of names")
    names = set(retired)
    if any(
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        for name in names
    ):
        raise ValueError("retired Skill identities must be plain directory names")
    return sorted(names)


def detect_skill_targets(
    skills_root: Path, *, retired: Iterable[str] = TRELLIS_SKILL_NAMES
) -> dict[str, Any]:
    """Detect identity-proven retired Skills; the default closed set is trellis-only."""
    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for name in _retired_names(retired):
        target = skills_root / name
        if not target.exists() and not target.is_symlink():
            continue
        error = skill_identity_error(target, name)
        if error is None:
            candidates.append(
                {"kind": "skill-directory", "name": name, "path": str(target)}
            )
        else:
            blocked.append(
                {
                    "kind": "skill-directory",
                    "name": name,
                    "path": str(target),
                    "reason": error,
                }
            )
    return {"candidates": candidates, "blocked": blocked}


# ---------------------------------------------------------------------------
# Project targets
# ---------------------------------------------------------------------------


def detect_project_targets(root: Path) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    trellis = root / ".trellis"
    if trellis.is_symlink():
        blocked.append(
            {
                "kind": "trellis-uninstall",
                "path": str(trellis),
                "reason": ".trellis is a symlink",
            }
        )
    elif trellis.is_dir():
        candidates.append(
            {"kind": "trellis-uninstall", "path": str(trellis), "root": str(root)}
        )
    elif trellis.exists():
        blocked.append(
            {
                "kind": "trellis-uninstall",
                "path": str(trellis),
                "reason": "not a directory",
            }
        )
    gitnexus = root / ".gitnexus"
    if gitnexus.is_symlink():
        blocked.append(
            {
                "kind": "directory-remove",
                "path": str(gitnexus),
                "reason": ".gitnexus is a symlink",
            }
        )
    elif gitnexus.is_dir():
        candidates.append(
            {"kind": "directory-remove", "path": str(gitnexus), "name": ".gitnexus"}
        )
    elif gitnexus.exists():
        blocked.append(
            {
                "kind": "directory-remove",
                "path": str(gitnexus),
                "reason": "not a directory",
            }
        )
    agents = root / "AGENTS.md"
    if agents.is_symlink() or (agents.exists() and not agents.is_file()):
        blocked.append(
            {
                "kind": "marker-blocks",
                "path": str(agents),
                "reason": "not a regular file",
            }
        )
    if agents.is_file() and not agents.is_symlink():
        try:
            raw = agents.read_bytes()
        except OSError:
            blocked.append(
                {
                    "kind": "marker-blocks",
                    "path": str(agents),
                    "reason": "unreadable file",
                }
            )
            raw = None
        if raw is not None:
            markers = detect_marker_blocks(raw)
            if markers["status"] == "removable":
                candidates.append(
                    {
                        "kind": "marker-blocks",
                        "path": str(agents),
                        "removals": markers["removals"],
                    }
                )
            elif markers["status"] == "malformed":
                blocked.append(
                    {
                        "kind": "marker-blocks",
                        "path": str(agents),
                        "reason": markers["reason"],
                    }
                )
    return {"candidates": candidates, "blocked": blocked}


# ---------------------------------------------------------------------------
# gitnexus MCP server entries
# ---------------------------------------------------------------------------


def _home(environ: Mapping[str, str]) -> Path:
    return Path(environ.get("HOME") or environ.get("USERPROFILE") or str(Path.home()))


def strict_json_object(raw: bytes) -> dict[str, Any]:
    def unique(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError("duplicate JSON key")
            result[name] = value
        return result

    def invalid_constant(_value):
        raise ValueError("non-finite JSON value")

    def finite_float(value):
        import math

        number = float(value)
        if not math.isfinite(number):
            raise ValueError("non-finite JSON number")
        return number

    try:
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=invalid_constant,
            parse_float=finite_float,
        )
    except RecursionError as error:
        raise ValueError("JSON nesting exceeds the supported parser depth") from error
    if not isinstance(document, dict):
        raise TypeError("configuration must be a JSON object")
    try:
        # Prove renderability before any preceding cleanup can execute.
        json.dumps(document, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as error:
        raise ValueError("configuration cannot be safely serialized") from error
    return document


def _command_operand(args: list[str], *, node: bool) -> str:
    values = (
        {"-r", "--require", "--import", "--loader", "--inspect-port"}
        if node
        else {"-p", "--package"}
    )
    flags = (
        {
            "--no-warnings",
            "--no-deprecation",
            "--enable-source-maps",
            "--inspect",
            "--inspect-brk",
        }
        if node
        else {"-y", "--yes", "--no-install", "--offline", "--quiet"}
    )
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            return args[index + 1] if index + 1 < len(args) else ""
        if not arg.startswith("-"):
            return arg
        option = arg.split("=", 1)[0]
        if option in values:
            index += 1 if "=" in arg else 2
        elif option in flags:
            index += 1
        else:
            return ""  # Unknown option arity is not a deletion identity.
    return ""


def _gitnexus_names(servers: dict[str, Any], key: str) -> list[str]:
    names = []
    for name, server in servers.items():
        if not isinstance(server, dict):
            raise TypeError("MCP server must be an object")
        command = str(server.get("command", "")).replace("\\", "/").rsplit("/", 1)[-1]
        args = server.get("args", [])
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise ValueError("MCP args must be a string array")
        known_command = command in {
            "gitnexus",
            "gitnexus-mcp",
            "gitnexus.cmd",
            "gitnexus-mcp.cmd",
        }
        if command in {"npx", "npx.cmd"}:
            package = _command_operand(args, node=False)
            package_argument = package in {
                "gitnexus",
                "gitnexus-mcp",
            } or package.startswith(("gitnexus@", "gitnexus-mcp@"))
        else:
            script = _command_operand(args, node=True).replace("\\", "/")
            package_argument = (
                command in {"node", "node.exe"} and "/node_modules/gitnexus/" in script
            )
        if name in {key, "gitnexus-mcp"} or known_command or package_argument:
            names.append(name)
    return sorted(names)


def _json_server_present(path: Path, key: str) -> list[str]:
    document = strict_json_object(path.read_bytes())
    servers = document.get("mcpServers", {})
    if not isinstance(servers, dict):
        raise TypeError("mcpServers must be an object")
    return _gitnexus_names(servers, key)


def _toml_server_present(path: Path, key: str) -> list[str]:
    import tomlkit

    document = tomlkit.parse(path.read_text(encoding="utf-8"))
    servers = document.unwrap().get("mcp_servers", {})
    if not isinstance(servers, dict):
        raise TypeError("mcp_servers must be a table")
    return _gitnexus_names(servers, key)


def detect_mcp_targets(
    *, environ: Mapping[str, str], key: str = "gitnexus"
) -> dict[str, Any]:
    from sbtd_omp_sources import active_omp_paths

    home = _home(environ)
    codex_home = Path(environ.get("CODEX_HOME") or (home / ".codex"))
    probes: list[tuple[str, Path, str, Callable[[Path, str], list[str]]]] = [
        ("codex", codex_home / "config.toml", "toml", _toml_server_present),
        ("codex", home / ".codex" / "config.toml", "toml", _toml_server_present),
        ("claude", home / ".claude.json", "json", _json_server_present),
        ("claude", home / ".claude" / "mcp.json", "json", _json_server_present),
        ("kimi", home / ".kimi-code" / "mcp.json", "json", _json_server_present),
        ("kimi", home / ".kimi-code" / "config.toml", "toml", _toml_server_present),
        ("kimi", home / ".kimi" / "mcp.json", "json", _json_server_present),
        ("omp", home / ".omp" / "agent" / "mcp.json", "json", _json_server_present),
    ]
    # Include the active root/profile using the same resolver as deployment.
    omp_target = active_omp_paths(home=home, environ=environ)["target"]
    assert isinstance(omp_target, Path)
    probes.append(("omp", omp_target, "json", _json_server_present))
    if environ.get("PI_CODING_AGENT_DIR"):
        probes.append(
            (
                "omp",
                Path(environ["PI_CODING_AGENT_DIR"]) / "mcp.json",
                "json",
                _json_server_present,
            )
        )
    if environ.get("CLAUDE_CONFIG_DIR"):
        probes.append(
            (
                "claude",
                Path(environ["CLAUDE_CONFIG_DIR"]) / "mcp.json",
                "json",
                _json_server_present,
            )
        )
    profiles = home / ".omp" / "profiles"
    if profiles.is_symlink():
        raise ValueError("OMP profiles directory is a symlink")
    if profiles.is_dir():
        for profile in sorted(profiles.iterdir()):
            probes.append(
                ("omp", profile / "agent" / "mcp.json", "json", _json_server_present)
            )
    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_locations: set[tuple[int, int, str]] = set()
    for host, path, fmt, probe in probes:
        identity = str(path)
        if identity in seen:
            continue
        seen.add(identity)
        if not path.exists() and not path.is_symlink():
            continue
        try:
            if any(parent.is_symlink() for parent in (path, *path.parents)):
                raise ValueError("configuration path contains a symlink")
            if not path.is_file():
                raise ValueError("configuration is not a regular file")
            # Directory aliases share a namespace; distinct hardlink entries do not.
            parent = path.parent.stat()
            location = (parent.st_dev, parent.st_ino, path.name)
            if location in seen_locations:
                continue
            seen_locations.add(location)
            present = probe(path, key)
        except (OSError, ValueError, TypeError, ImportError):
            blocked.append(
                {
                    "kind": "mcp-server-remove",
                    "host": host,
                    "path": str(path),
                    "reason": "configuration cannot be safely parsed; preserve it",
                }
            )
            continue
        if not present:
            continue
        candidates.append(
            {
                "kind": "mcp-server-remove",
                "host": host,
                "path": str(path),
                "format": fmt,
                "keys": present,
            }
        )
    return {"candidates": candidates, "blocked": blocked}


def remove_json_server_key(raw: bytes, key: str) -> bytes:
    document = strict_json_object(raw)
    servers = document.get("mcpServers")
    if not isinstance(servers, dict) or key not in servers:
        return raw
    del servers[key]
    rendered = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False)
    return (rendered + "\n").encode("utf-8")


def remove_toml_server_table(raw: bytes, key: str) -> bytes:
    import tomlkit

    document = tomlkit.parse(raw.decode("utf-8"))
    servers = document.get("mcp_servers")
    if servers is None or key not in servers:
        return raw
    del servers[key]
    return tomlkit.dumps(document).encode("utf-8")
