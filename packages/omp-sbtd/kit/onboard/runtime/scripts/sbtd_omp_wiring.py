"""Pure OMP MCP configuration analysis for P1-05.

The module reads only bytes and already-normalized inherited-source records. It
never executes configured commands, probes a host, or writes a file. Deployment
callers own snapshots, filesystem authorization, and persistence.

The desired state is a single global ``sbtd-graft`` stdio definition: no fixed
``--root`` and no ``cwd``, so the spawned process working directory alone
selects the connection's project. Retired fixed-root ``sbtd-graft-<hash>``
entries conflict by default; explicit ``retire_legacy=True`` removes only
entries whose complete retired shape, hashed root and runtime ownership are
proven (batch runtime or an explicit observed ``legacy`` runtime contract).
Only user-wide inherited sources may suppress the managed write: a
project-scoped equivalent entry covers sessions from that one project only
and can never satisfy the global definition.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn

import onboard_contracts as contracts
from sbtd_project import _check_finite, _reject_json_constant, _reject_json_duplicates

__all__ = [
    "analyze_omp_configuration",
    "desired_omp_server",
    "omp_mcp_candidate",
    "verify_owned_omp_mcp_section",
]

_SERVER_PREFIX = "sbtd-graft"
_GLOBAL_NAME = _SERVER_PREFIX
_RUNTIME_KEYS = ("node", "cli", "python", "launcher")
_STARTUP_FLAGS = ("-E", "-s")
_TELEMETRY_ENV = {"DO_NOT_TRACK": "1", "DNT": "1"}


def _fail(code: str, message: str) -> NoReturn:
    raise contracts.ContractError(code, message)


def _server_name(root: str) -> str:
    return f"{_SERVER_PREFIX}-{hashlib.sha256(root.encode('utf-8')).hexdigest()[:16]}"


def _absolute_paths(mapping: Mapping[str, Any]) -> dict[str, str]:
    paths: dict[str, str] = {}
    for key in _RUNTIME_KEYS:
        value = mapping.get(key)
        if isinstance(value, os.PathLike):
            value = os.fspath(value)
        if not isinstance(value, str) or not value or not os.path.isabs(value):
            _fail(
                "invalid-argument",
                "binding paths must be non-empty absolute path strings",
            )
        paths[key] = value
    return paths


def _runtime_identity(paths: Mapping[str, str]) -> tuple[str, str, str, str]:
    return (paths["python"], paths["launcher"], paths["node"], paths["cli"])


def _bindings(
    bindings: Sequence[Mapping[str, Any]], *, require_root: bool = False
) -> list[dict[str, Any]]:
    if isinstance(bindings, (str, bytes, bytearray)) or not isinstance(
        bindings, Sequence
    ):
        _fail("invalid-argument", "bindings must be a sequence of mappings")
    resolved: list[dict[str, Any]] = []
    for binding in bindings:
        if not isinstance(binding, Mapping):
            _fail("invalid-argument", "each binding must be a mapping")
        paths: dict[str, Any] = _absolute_paths(binding)
        root = binding.get("root")
        if root is None and require_root:
            _fail("invalid-argument", "the binding requires an explicit root")
        if root is not None:
            if isinstance(root, os.PathLike):
                root = os.fspath(root)
            if not isinstance(root, str) or not root or not os.path.isabs(root):
                _fail(
                    "invalid-argument",
                    "binding paths must be non-empty absolute path strings",
                )
            paths["root"] = root
        legacy = binding.get("legacy")
        if legacy is not None:
            if "root" not in paths:
                _fail(
                    "invalid-argument",
                    "a legacy runtime contract requires the binding root",
                )
            if not isinstance(legacy, Mapping) or set(legacy) != set(_RUNTIME_KEYS):
                _fail(
                    "invalid-argument",
                    "a legacy runtime contract names exactly the runtime paths",
                )
            paths["legacy"] = _absolute_paths(legacy)
        resolved.append(paths)
    return resolved


def desired_omp_server(binding: Mapping[str, Any]) -> dict[str, Any]:
    """Return the native OMP stdio record of the single global definition.

    The record is rootless: no ``--root`` and no ``cwd`` — the spawned
    process working directory alone selects the connection's project. A
    ``root`` key in the binding is accepted but never rendered.
    """
    paths = _bindings([binding])[0]
    return {
        "type": "stdio",
        "command": paths["python"],
        "args": [
            *_STARTUP_FLAGS,
            paths["launcher"],
            "mcp",
            "--node",
            paths["node"],
            "--entry",
            paths["cli"],
        ],
        "env": dict(_TELEMETRY_ENV),
    }


def _strict_json(raw: bytes, label: str) -> Any:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        _fail("invalid-utf8", f"the {label} is not strict UTF-8")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_json_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (ValueError, RecursionError):
        _fail("invalid-json", f"the {label} is not strict JSON")
    if not _check_finite(value):
        _fail("invalid-json", f"the {label} contains a non-finite number")
    return value


def _reject_dynamic(value: Any) -> None:
    if isinstance(value, str):
        if re.search(r"\$\{[^}:]+(?::-[^}]*)?\}", value):
            _fail(
                "invalid-config",
                "OMP configuration contains unsupported dynamic values",
            )
        return
    if isinstance(value, list):
        for item in value:
            _reject_dynamic(item)
        return
    if isinstance(value, dict):
        for item in value.values():
            _reject_dynamic(item)


def _servers(document: Any, label: str) -> dict[str, Mapping[str, Any]]:
    if not isinstance(document, dict):
        _fail("invalid-config", f"the {label} must be a JSON object")
    servers = document.get("mcpServers", {})
    if not isinstance(servers, dict) or any(
        not isinstance(name, str) or not isinstance(server, Mapping)
        for name, server in servers.items()
    ):
        _fail("invalid-config", f"the {label} MCP server section is malformed")
    _reject_dynamic(servers)
    return servers


def _literal_env_keys(server: Mapping[str, Any]) -> list[str] | None:
    env = server.get("env", {})
    if not isinstance(env, Mapping):
        return None
    policy = server.get("envPolicy")
    if policy == "literal":
        return sorted(key for key in env if isinstance(key, str))
    if policy is not None:
        return None
    literal = server.get("envLiteralKeys", [])
    if not isinstance(literal, list) or any(
        not isinstance(key, str) for key in literal
    ):
        return None
    return sorted(literal)


def _equivalent(actual: Mapping[str, Any], desired: Mapping[str, Any]) -> bool:
    env = actual.get("env", {})
    actual_type = actual.get("type", "stdio")
    actual_literals = _literal_env_keys(actual)
    desired_literals = _literal_env_keys(desired)
    return (
        actual.get("auth") == desired.get("auth")
        and actual.get("oauth") == desired.get("oauth")
        and actual.get("requestIdFormat", "number")
        == desired.get("requestIdFormat", "number")
        and actual_type == desired["type"]
        and actual.get("command") == desired["command"]
        and actual.get("args") == desired["args"]
        and actual.get("cwd") == desired.get("cwd")
        and isinstance(env, Mapping)
        and dict(env) == desired["env"]
        and actual_literals is not None
        and actual_literals == desired_literals
    )

def _source_order(source: Mapping[str, Any]) -> int:
    provider = source["source"].split("-", 1)[0]
    try:
        return {"native": 0, "claude": 1, "codex": 2}[provider]
    except KeyError:
        _fail("invalid-argument", "inherited source providers are unsupported")


_USER_WIDE_SCOPES = ("user", "user-alternate", "user-json")


def _user_wide(source: Mapping[str, Any]) -> bool:
    """True only for sources that cover every project and no-project session.

    A project-scoped equivalent entry (``*-project``) proves wiring only for
    sessions started inside that one project; it can never satisfy the
    global rootless ``sbtd-graft`` definition for other projects or for a
    projectless session, so it must not suppress the managed write.
    Unknown future scopes are not user-wide: an unnecessary idempotent
    write is safe, a wrong suppression is not.
    """
    parts = source["source"].split("-", 1)
    return len(parts) == 2 and parts[1] in _USER_WIDE_SCOPES


def _string_set(value: Any, label: str) -> set[str]:
    if value is None:
        return set()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        _fail("invalid-config", f"the active OMP {label} list is malformed")
    return set(value)


def _entry_enabled(server: Mapping[str, Any]) -> bool:
    enabled = server.get("enabled")
    if isinstance(enabled, str):
        lowered = enabled.lower()
        if lowered in {"false", "0"}:
            return False
        if lowered in {"true", "1"}:
            return True
    if enabled is None:
        return True
    if isinstance(enabled, bool):
        return enabled
    _fail("invalid-config", "an active OMP MCP enabled flag is malformed")


def _legacy_record_shape(
    name: str, server: Any
) -> tuple[str, tuple[str, str, str, str]] | None:
    """Parse as the exact retired fixed-root managed record.

    Returns ``(root, runtime identity)`` only when the name hash, argv,
    ``cwd`` and environment match what the retired renderer provably
    produced; anything else is ``None`` and can never be claimed or deleted
    by prefix. Deletion is stricter than effective equivalence: the key set
    must be exactly the retired native shape, so a record carrying custom
    fields (``timeout``, ``description``, ``transport``, an added
    ``enabled`` flag, …) is unknown and blocks with bytes unchanged.
    """
    if not isinstance(server, Mapping) or set(server) != {
        "type",
        "command",
        "args",
        "cwd",
        "env",
    }:
        return None
    command = server.get("command")
    args = server.get("args")
    if (
        not isinstance(command, str)
        or not os.path.isabs(command)
        or not isinstance(args, list)
        or len(args) != 10
        or any(not isinstance(token, str) for token in args)
        or args[:2] != list(_STARTUP_FLAGS)
        or not _owned_launcher_name(args[2])
        or args[3] != "mcp"
        or args[4::2] != ["--root", "--node", "--entry"]
    ):
        return None
    root, node, cli = args[5], args[7], args[9]
    if (
        name != _server_name(root)
        or not os.path.isabs(node)
        or Path(cli).name != "cli.js"
    ):
        return None
    retired = {
        "type": "stdio",
        "command": command,
        "args": args,
        "cwd": root,
        "env": dict(_TELEMETRY_ENV),
    }
    if not _equivalent(server, retired):
        return None
    return root, (command, args[2], node, cli)


def analyze_omp_configuration(
    target: Path,
    bindings: Sequence[Mapping[str, Any]],
    inherited: Sequence[Mapping[str, Any]],
    *,
    disabled_extensions: Sequence[str] = (),
    retire_legacy: bool = False,
    active_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Analyze the active OMP target and explicit inherited records.

    ``inherited`` is the caller's observed source set, already honoring profile
    and provider gates. This function does not rediscover or execute it.
    ``active_bytes`` substitutes verified in-memory bytes for the active
    document instead of reading ``target`` from disk; every ownership,
    disabled-identity and inheritance gate applies unchanged, so a caller
    holding proven original bytes can derive the deterministic outcome
    without trusting live target content.
    """
    if not isinstance(target, Path) or not target.is_absolute():
        _fail("invalid-argument", "the OMP MCP target must be an absolute path")
    if isinstance(disabled_extensions, (str, bytes)) or any(
        not isinstance(item, str) for item in disabled_extensions
    ):
        _fail("invalid-argument", "disabled OMP extension identities are malformed")
    paths = _bindings(bindings)
    runtimes = {_runtime_identity(item) for item in paths}
    if len(runtimes) > 1:
        _fail(
            "invalid-argument",
            "a global graft MCP definition carries exactly one runtime",
        )
    runtime = runtimes.pop() if runtimes else None
    selected = {item["root"] for item in paths if "root" in item}
    contracts: dict[str, set[tuple[str, str, str, str]]] = {}
    for item in paths:
        if "root" in item and "legacy" in item:
            contracts.setdefault(item["root"], set()).add(
                _runtime_identity(item["legacy"])
            )
    desired = (
        {_GLOBAL_NAME: desired_omp_server(paths[0])} if paths else {}
    )
    sources = sorted(_normalized_inherited(inherited), key=_source_order)
    document: dict[str, Any] = {"mcpServers": {}}
    existing: dict[str, Mapping[str, Any]] = {}
    if active_bytes is not None:
        # Verified in-memory document: empty bytes mean no document (an
        # absent or never-written target), never a malformed one.
        if not isinstance(active_bytes, (bytes, bytearray)):
            _fail("invalid-argument", "the active OMP MCP document must be bytes")
        raw = bytes(active_bytes)
        if raw:
            document = _strict_json(raw, "active OMP MCP configuration")
            existing = _servers(document, "active OMP MCP configuration")
    elif target.exists():
        raw = target.read_bytes()
        document = _strict_json(raw, "active OMP MCP configuration")
        existing = _servers(document, "active OMP MCP configuration")
    disabled_servers = _string_set(document.get("disabledServers"), "disabledServers")
    forced_enabled = _string_set(document.get("enabledServers"), "enabledServers")
    blocked_extensions = set(disabled_extensions)

    def blocked_name(name: str) -> bool:
        return name in disabled_servers or f"mcp:{name}" in blocked_extensions

    blocked_names = {name for name in desired if blocked_name(name)}
    if blocked_names:
        _fail(
            "ownership-conflict",
            "the active OMP configuration disables a generated Graft identity",
        )
    removals: set[str] = set()
    for active_name, active in existing.items():
        enabled = _entry_enabled(active) or active_name in forced_enabled
        managed_shape = active_name == _GLOBAL_NAME or active_name.startswith(
            _SERVER_PREFIX + "-"
        )
        if blocked_name(active_name):
            if managed_shape:
                _fail(
                    "ownership-conflict",
                    "an active sbtd-graft OMP entry is explicitly disabled",
                )
            continue
        if not managed_shape:
            continue
        if active_name.startswith(_SERVER_PREFIX + "-"):
            shape = _legacy_record_shape(active_name, active)
            if shape is None:
                _fail(
                    "ownership-conflict",
                    "an unknown sbtd-graft OMP entry cannot be claimed",
                )
            root, old_runtime = shape
            if not enabled:
                _fail(
                    "ownership-conflict",
                    "an active sbtd-graft OMP entry differs or is disabled",
                )
            if not retire_legacy or root not in selected:
                _fail(
                    "ownership-conflict",
                    "a retired-shape graft OMP entry requires explicit "
                    "retirement authorization",
                )
            if old_runtime != runtime and old_runtime not in contracts.get(root, ()):
                _fail(
                    "ownership-conflict",
                    "a retired graft OMP runtime is not proven owned",
                )
            removals.add(active_name)
            continue
        equivalent_names = {
            desired_name
            for desired_name, desired_server in desired.items()
            if _equivalent(active, desired_server)
        }
        if not enabled or not equivalent_names:
            _fail(
                "ownership-conflict",
                "an active sbtd-graft OMP entry differs or is disabled",
            )
    matches: list[dict[str, str]] = []
    writes: list[dict[str, Any]] = []
    for source in sources:
        for name, server in source["servers"].items():
            server_enabled = source["enabled"] and (
                _entry_enabled(server) or name in forced_enabled
            )
            managed_shape = name == _SERVER_PREFIX or name.startswith(
                _SERVER_PREFIX + "-"
            )
            if blocked_name(name):
                if managed_shape:
                    _fail(
                        "ownership-conflict",
                        "an inherited sbtd-graft connection is explicitly disabled",
                    )
                continue
            equivalent_names = {
                desired_name
                for desired_name, desired_server in desired.items()
                if _equivalent(server, desired_server)
            }
            if managed_shape and (not server_enabled or not equivalent_names):
                _fail(
                    "ownership-conflict",
                    "an inherited sbtd-graft connection differs or is disabled",
                )
            if not server_enabled:
                continue
            if not _user_wide(source):
                # Project-scoped entries never satisfy the global
                # definition: their managed/legacy/conflict gates above
                # still fire, but they cannot suppress the managed write.
                continue
            for desired_name in equivalent_names:
                matches.append(
                    {
                        "source": source["source"],
                        "name": name,
                        "server": desired_name,
                    }
                )
    active_candidates = {
        name: server
        for name, server in existing.items()
        if not blocked_name(name) and (_entry_enabled(server) or name in forced_enabled)
    }
    for name, server in desired.items():
        if any(match["server"] == name for match in matches):
            continue
        current = active_candidates.get(name)
        if current is not None:
            if _equivalent(current, server):
                matches.append({"source": "active", "name": name, "server": name})
                continue
            _fail(
                "ownership-conflict",
                "an existing sbtd-graft OMP entry differs and cannot be claimed",
            )
        equivalent_active = [
            active_name
            for active_name, active in active_candidates.items()
            if _equivalent(active, server)
        ]
        if equivalent_active:
            matches.append(
                {"source": "active", "name": equivalent_active[0], "server": name}
            )
            continue
        writes.append({"name": name, "server": server})
    return {
        "target": str(target),
        "servers": existing,
        "writes": writes,
        "removals": sorted(removals),
        "inherited_matches": matches,
    }


def _normalized_inherited(
    inherited: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(inherited, (str, bytes, bytearray)) or not isinstance(
        inherited, Sequence
    ):
        _fail("invalid-argument", "inherited sources must be a sequence of mappings")
    normalized: list[dict[str, Any]] = []
    for record in inherited:
        if (
            not isinstance(record, Mapping)
            or not isinstance(record.get("source"), str)
            or not isinstance(record.get("enabled"), bool)
            or not isinstance(record.get("servers"), Mapping)
        ):
            _fail("invalid-argument", "inherited source records are malformed")
        servers = record["servers"]
        if any(
            not isinstance(name, str) or not isinstance(server, Mapping)
            for name, server in servers.items()
        ):
            _fail("invalid-argument", "inherited MCP server records are malformed")
        _reject_dynamic(servers)
        normalized.append(
            {
                "source": record["source"],
                "enabled": record["enabled"],
                "servers": dict(servers),
            }
        )
    return normalized


def omp_mcp_candidate(before: bytes, analysis: Mapping[str, Any]) -> bytes:
    """Render the active OMP config candidate, or ``before`` when complete."""
    if not isinstance(before, (bytes, bytearray)):
        _fail("invalid-argument", "input document must be bytes")
    raw = bytes(before)
    document = (
        _strict_json(raw, "active OMP MCP configuration") if raw else {"mcpServers": {}}
    )
    existing = _servers(document, "active OMP MCP configuration")
    if not isinstance(analysis, Mapping) or not isinstance(
        analysis.get("writes"), list
    ):
        _fail("invalid-argument", "the OMP configuration analysis is malformed")
    writes = analysis["writes"]
    removals = analysis.get("removals", [])
    if (
        any(not isinstance(item, Mapping) for item in writes)
        or not isinstance(removals, list)
        or any(not isinstance(name, str) for name in removals)
    ):
        _fail("invalid-argument", "the OMP configuration analysis is malformed")
    servers = dict(existing)
    disabled_servers = _string_set(document.get("disabledServers"), "disabledServers")
    for name in removals:
        managed_shape = name == _GLOBAL_NAME or name.startswith(_SERVER_PREFIX + "-")
        if not managed_shape or name not in servers or name in disabled_servers:
            _fail(
                "ownership-conflict",
                "a retired graft OMP entry no longer matches the active document",
            )
        del servers[name]
    for item in writes:
        name = item.get("name")
        server = item.get("server")
        if not isinstance(name, str) or not isinstance(server, Mapping):
            _fail("invalid-argument", "the OMP configuration analysis is malformed")
        if name in disabled_servers:
            _fail(
                "ownership-conflict",
                "the active OMP configuration disables a generated Graft identity",
            )
        if name in servers:
            _fail(
                "ownership-conflict",
                "an existing sbtd-graft OMP entry differs and cannot be claimed",
            )
        servers[name] = dict(server)
    if not writes and not removals:
        return raw
    document["mcpServers"] = servers
    try:
        return contracts.canonical_json_bytes(document)
    except (TypeError, ValueError, RecursionError):
        _fail("invalid-config", "the rendered OMP MCP candidate cannot be serialized")


# ---------------------------------------------------------------------------
# Managed graft section ownership gate (follow-up predecessor checks)
# ---------------------------------------------------------------------------
#
# The follow-up plan gates a completed configure-graft outcome by
# managed-section ownership, not whole-file equality: the host may append
# unrelated servers beside the graft-owned entries. The sealed chain never
# carries launch bindings, so expectations are the owned argv shapes —
# never recomputed bytes. Anything missing, malformed, duplicated or
# reshaped inside the managed section fails closed; drift outside it does
# not block.


def _owned_launcher_name(path: Any) -> bool:
    return isinstance(path, str) and Path(path).name == "sbtd_graft_entry.py"


def _verify_global_omp_entry(
    entry: Any, disabled: Collection[str], forced: Collection[str]
) -> None:
    """Fail closed unless the rootless ``sbtd-graft`` entry is intact."""
    if not isinstance(entry, Mapping):
        _fail("state-conflict", "a managed graft OMP MCP entry was reshaped")
    command = entry.get("command")
    args = entry.get("args")
    if (
        not isinstance(command, str)
        or not os.path.isabs(command)
        or not isinstance(args, list)
        or len(args) != 8
        or any(not isinstance(token, str) for token in args)
        or args[:2] != list(_STARTUP_FLAGS)
        or not os.path.isabs(args[2])
        or not _owned_launcher_name(args[2])
        or args[3] != "mcp"
        or args[4::2] != ["--node", "--entry"]
        or not os.path.isabs(args[5])
        or not os.path.isabs(args[7])
        or Path(args[7]).name != "cli.js"
    ):
        _fail("state-conflict", "a managed graft OMP MCP argv was reshaped")
    desired = {
        "type": "stdio",
        "command": command,
        "args": args,
        "env": dict(_TELEMETRY_ENV),
    }
    if not _equivalent(entry, desired):
        _fail("state-conflict", "a managed graft OMP MCP entry was reshaped")
    try:
        enabled = _entry_enabled(entry)
    except contracts.ContractError as error:
        if error.code != "invalid-config":
            raise
        # Inside this gate a malformed managed-section value is a
        # state-conflict, never a configuration-usage error.
        _fail("state-conflict", "a managed graft OMP MCP entry was reshaped")
    if _GLOBAL_NAME in disabled or (not enabled and _GLOBAL_NAME not in forced):
        _fail("state-conflict", "a managed graft OMP entry is explicitly disabled")


def verify_owned_omp_mcp_section(raw: bytes, roots: Sequence[str]) -> None:
    """Fail closed unless the managed graft OMP MCP section is intact.

    The current global definition — one rootless ``sbtd-graft`` entry — is
    validated whenever present; retired hash-keyed entries may not coexist
    with it. When it is absent, historical receipts sealed against the
    retired fixed-root shape are validated exactly as before: every batch
    root's hash-keyed entry must be intact, foreign ``sbtd-graft-*``
    entries owned by other batches stay exempt, a managed identity listed
    in ``disabledServers`` fails closed, and all managed entries must agree
    on the runtime. Unlike the Codex side, no launcher anchor exists here:
    the chain has no verified directory target provably containing the OMP
    launcher path, so the boundary stays shape plus cross-entry
    consistency.
    """
    if not isinstance(raw, (bytes, bytearray)):
        _fail("state-conflict", "the OMP MCP configuration is unavailable")
    try:
        text = bytes(raw).decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        _fail("state-conflict", "the OMP MCP configuration is not strict UTF-8")
    try:
        document = json.loads(
            text,
            object_pairs_hook=_reject_json_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (ValueError, RecursionError):
        _fail("state-conflict", "the OMP MCP configuration is not strict JSON")
    if not _check_finite(document) or not isinstance(document, dict):
        _fail("state-conflict", "the OMP MCP configuration root is malformed")
    servers = document.get("mcpServers")
    if not isinstance(servers, dict):
        _fail("state-conflict", "the managed graft OMP MCP section is missing")
    for label in ("disabledServers", "enabledServers"):
        value = document.get(label)
        if value is not None and (
            not isinstance(value, list)
            or any(not isinstance(item, str) for item in value)
        ):
            _fail("state-conflict", f"the OMP {label} list is malformed")
    disabled = set(document.get("disabledServers") or ())
    forced = set(document.get("enabledServers") or ())
    if _GLOBAL_NAME in servers:
        if any(name.startswith(_SERVER_PREFIX + "-") for name in servers):
            _fail(
                "state-conflict",
                "managed graft OMP MCP generations are mixed",
            )
        _verify_global_omp_entry(servers[_GLOBAL_NAME], disabled, forced)
        return
    batch = {str(root) for root in roots}
    expected = {_server_name(root) for root in batch}
    if not expected:
        _fail("state-conflict", "the managed graft OMP MCP section is missing")
    if not expected.issubset(servers):
        _fail("state-conflict", "the managed graft OMP MCP entries were changed")
    if expected & disabled:
        _fail("state-conflict", "a managed graft OMP entry is explicitly disabled")
    identities: set[tuple[str, str, str, str]] = set()
    for root in sorted(batch):
        name = _server_name(root)
        entry = servers[name]
        if not isinstance(entry, Mapping):
            _fail("state-conflict", "a managed graft OMP MCP entry was reshaped")
        command = entry.get("command")
        args = entry.get("args")
        if (
            not isinstance(command, str)
            or not os.path.isabs(command)
            or not isinstance(args, list)
            or len(args) != 10
            or any(not isinstance(token, str) for token in args)
            or args[:2] != list(_STARTUP_FLAGS)
            or not os.path.isabs(args[2])
            or not _owned_launcher_name(args[2])
            or args[3] != "mcp"
            or args[4::2] != ["--root", "--node", "--entry"]
            or args[5] != root
            or not os.path.isabs(args[7])
            or not os.path.isabs(args[9])
            or Path(args[9]).name != "cli.js"
        ):
            _fail("state-conflict", "a managed graft OMP MCP argv was reshaped")
        desired = {
            "type": "stdio",
            "command": command,
            "args": args,
            "cwd": root,
            "env": dict(_TELEMETRY_ENV),
        }
        if not _equivalent(entry, desired):
            _fail("state-conflict", "a managed graft OMP MCP entry was reshaped")
        try:
            enabled = _entry_enabled(entry)
        except contracts.ContractError as error:
            if error.code != "invalid-config":
                raise
            # Inside this gate a malformed managed-section value is a
            # state-conflict, never a configuration-usage error.
            _fail("state-conflict", "a managed graft OMP MCP entry was reshaped")
        if not enabled and name not in forced:
            _fail("state-conflict", "a managed graft OMP MCP entry was reshaped")
        identities.add((command, args[2], args[7], args[9]))
    if len(identities) > 1:
        _fail(
            "state-conflict", "managed graft OMP MCP entries disagree on the runtime"
        )
