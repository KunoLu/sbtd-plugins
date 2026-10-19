"""Guarded native Graft MCP/hook launch seam (P1-04).

This is the only path that may start the pinned ``@nanonets/graft@0.22.0``
native MCP server or its native hook module for a selected project. It exists
because every upstream entry point (``graft mcp``, the SessionStart hook) runs
``runUpkeep`` → ``reconcileWiring`` at boot, and upstream self-maintenance is
unsafe to run unverified:

- a missing wiring stamp replays ``DEFAULT_WIRING_OPTS`` (global/mcp/hooks/
  statusline all true) onto the developer's machine-wide Codex/Gemini config;
- an older stamp replays whatever hosts/flags it recorded;
- the upstream installed hook shim dynamically searches for the highest-
  version install (baked dir, repo node_modules, ``npm root -g``) and silently
  no-ops on failure.

So this launcher gates ALL native startup, then replaces the shim:

1. ``validate_runtime`` proves the exact pinned package identity from
   metadata only (no execution): node and the CLI are nofollow ordinary
   files and the CLI resolves to ``dist/cli.js`` or ``dist/bin/graft.js`` of a
   real ``@nanonets/graft`` package whose ``package.json`` version is 0.22.0.
2. ``validate_build_scope`` proves the selected root is safe for ANY native
   launch or build, even before a graph exists (the explicit-build case):
   no graft workspace index and no workspace-parent shape the pinned
   package would federate into or migrate (its workspace build deletes the
   parent's whole ``graft/`` tree); no project ``.graft`` brain link or
   unsafe build config; a generated ``graft/`` tree of only real
   directories and ordinary single-link files (a native build writes
   ``INDEX.md``/cards/``.graph`` through whatever sits there); and no
   graph/cache/concept path value the pinned query layer joins onto the
   root that is absolute, traverses, or rides a link/hardlink. Missing
   graph, stamp and source files are valid here — native freshness handles
   absence; unsafe presence never passes. Nothing is written or repaired.
3. ``validate_project`` routes through ``validate_build_scope`` and then
   requires a complete CURRENT native wiring state: an actual built wiring
   graph (``graft/.graph/wiring.json``) and the native stamp
   (``graft/.cache/wiring-stamp.json``) whose version is exactly 0.22.0,
   whose hosts are exactly ``["agents"]``, and whose four wiring opts are
   all false. With that stamp in place the native boot-time reconcile is
   a proven no-op. A missing, unreadable, stale or foreign stamp is never
   repaired here: this path writes nothing and fails closed.
4. ``managed_environment`` builds the only environment a native child may
   see: the P1-03 scrubbed env (no GRAFT_/LLM/API credentials, no Node
   preloads, DNT on, dotenv from /dev/null), HOME/USERPROFILE/XDG roots
   pointed at a provided private temporary HOME, ``GRAFT_DIR`` pinned to the
   selected root's ``graft/`` dir, and ``CLAUDE_PROJECT_DIR`` forced to the
   validated root (native hooks consult it before the payload cwd).

CLI (internal; wired only by the managed wiring candidates, never by
check/plan)::

    sbtd_graft_entry.py mcp --node ABS --entry ABS
    sbtd_graft_entry.py hook --root ABS --node ABS --entry ABS \
        --event {session-start,prompt,post-edit,stop}
    sbtd_graft_entry.py analyze --root ABS --node ABS --entry ABS \
        {ask,map,skeleton,callers,check,grep,blast} [VALUE]

``mcp`` takes no root argument: the launch process's own working directory
selects exactly one project for the connection's entire life, resolved by
``_resolve_session_root`` to the nearest proven Git repository or linked
worktree root. A legacy ``--root`` is an argparse usage error before any
validation, temporary HOME creation or native launch. Resolution never
descends into child directories (a neutral common parent of several
projects finds no project), never adopts the user's home directory as a
project or climbs above it, and never skips an unsafe ``.git`` marker
(link, reparse point, special or ambiguous gitdir file) to borrow an outer
repository's graph. A safe-shaped marker is only a candidate: the launch
cwd's own Git context must then prove it is a real work tree whose real
top-level is exactly the boundary directory, via the only Git invocation
this launcher ever makes — a sanitized read-only ``git rev-parse
--show-toplevel --is-inside-git-dir`` probe of the launch cwd with no
inherited GIT_* variable, no system/global config and no prompting, run
from an executable resolved only through canonical absolute PATH entries
outside the boundary candidate (a relative or empty entry, a project bin/
directory, or a symlink alias reaching into the repository can never
supply it; no usable installation fails closed). An empty or hand-made
marker, a gitdir pointer to a missing or unrelated gitdir, a cwd inside a
bare repository's data tree or a checkout's ``.git`` administrative tree,
a context Git itself refuses, or a top-level that resolves anywhere else
all fail closed; no parent or outer graph is ever borrowed.
``hook``/``analyze`` keep the explicit absolute ``--root``
binding above.
``mcp`` spawns exactly ``[node, cli, "mcp", root]`` with cwd=root behind
scoped stdio forwarding. ``analyze`` admits only the seven pinned read-only
commands above, always selects the selected root as the positional project,
forces JSON and no-refresh where native offers those flags, and has no option
surface for workspace-wide ``--dir``, LLM naming, deep builds, exports or
arbitrary native argv. The pinned native server speaks newline-delimited
JSON-RPC 2.0 on stdout only, and every host request line is gated through a
FRESH ``validate_project`` before native receives it: startup validation
alone cannot cover the graph the running child reloads when an explicit
build or the Stop hook's detached sync build replaces it on disk
(``GRAFT_NO_REFRESH`` suppresses only the child's own rebuild, not its
mtime-keyed reload of the file). A request that fails the fresh guard is
never forwarded — the host receives one fixed sanitized JSON-RPC error for
that request id, the native child is closed and terminated, and the
launcher exits 2. Native replies, notifications and request ids pass
through untouched, forwarded lines and refusal lines never share a partial
line on stdout, and host EOF, a dead child or a closed host pipe end the
session without orphaning the child or dropping a completed reply. ``hook``
reads the event payload once, and when the payload's ``cwd`` is provably
outside the declared absolute binding it exits 0 without demanding the
bound root, validating or launching anything — the single explicit no-op,
required because global hook entries fire in every project the host opens,
even after the bound project was deleted (an existing payload cwd can never
physically sit inside a missing bound root). A potentially related event
keeps the strict canonical/existing root, runtime and project proofs. Any
other payload problem is a fixed failure, never a fallback. A matching
event is forwarded as the original stdin bytes to the owned bridge
(``assets/graft-hook-entry.mjs``), which imports only the exact validated
``dist/claude/hooks.js`` and calls ``main(event)``.

Every validation failure prints one fixed sanitized line to stderr and exits
2 (argparse usage errors likewise). Before any launch, the scoped temporary
HOME's ``.graft/update-check.json`` is seeded ``{latest: null, checkedAt:
now}`` — an honest "answer unknown, checked just now" stamp that suppresses
the native detached npm updater only while that stamp stays younger than the
native 24h TTL. A native server outliving the window can still spawn the
updater, and detached grandchildren (the Stop hook's sync build) can outlive
the removed HOME and recreate the temp path; the seed is a suppression
hint, not a lifetime guarantee. The scoped temporary HOME is removed in
``finally`` whether the child exits, is signaled, or the wait is
interrupted; SIGINT/SIGTERM/SIGHUP received while waiting are forwarded to
the child and its own exit status is propagated (128+n when it dies by a
signal). There is no daemon, no retry, no auth copy and no persistent HOME
write.

Public helpers are import-safe and side-effect free (pure reads); only the
CLI creates the temporary HOME and launches children.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

if __name__ == "__main__":
    sys.dont_write_bytecode = True

import graft_runtime
from graft_runtime import GRAFT_PINNED_VERSION
from onboard_contracts import ContractError
from sbtd_project import TaskDataError, open_regular_file

__all__ = [
    "HOOK_EVENTS",
    "managed_environment",
    "validate_build_scope",
    "validate_project",
    "validate_runtime",
]

# The exact native sub-commands the pinned dist/claude/hooks.js main()
# dispatches; the Codex event → sub-command mapping is rendered by the
# wiring candidates, which must use these names verbatim.
HOOK_EVENTS = ("session-start", "prompt", "post-edit", "stop")

_PACKAGE = Path(__file__).resolve().parents[1]
_BRIDGE = _PACKAGE / "assets" / "graft-hook-entry.mjs"

_GRAPH_PARTS = ("graft", ".graph", "wiring.json")
_STAMP_PARTS = ("graft", ".cache", "wiring-stamp.json")
_BUILD_CONFIG_PARTS = (".graft", "config.json")
_UPDATE_CACHE_PARTS = (".graft", "update-check.json")

_WORKSPACE_PARTS = ("graft", "workspace.json")
_MANIFEST_PARTS = ("graft", "manifest.json")

# Exact directory names the pinned discoverWorkspaceChildren() skips when
# auto-detecting a workspace parent (ingest/fs.js SKIP_DIRS; dot-prefixed
# names are skipped separately, and .graft/config.json includeDirs is
# already forced empty by the build-config guard).
_SKIP_CHILD_DIRS = frozenset(
    {
        "node_modules",
        "dist",
        "build",
        "_build",
        "out",
        "target",
        "vendor",
        "coverage",
        "__pycache__",
        "venv",
    }
)

# The only span grammar the pinned extractors mint (`L<from>-L<to>`), and
# the exact pointer grammar the pinned ask.js parseSpan() matches before
# reading the captured path. JS `$` end-anchor semantics (`\Z`).
_SPAN_SHAPE_RE = re.compile(r"L\d+-L\d+")
_SPAN_POINTER_RE = re.compile(r"(.*):L\d+-L\d+")
# Windows drive-absolute form (`C:/…`); POSIX-absolute and UNC forms are
# covered by the leading-slash and backslash rules.
_DRIVE_ABS_RE = re.compile(r"[A-Za-z]:[\\/]")
# `.cache/` sidecar names the pinned readExtractCache() can consume
# (`extract.<stamp>.json`); never the ask index, whose doc.path fields are
# token bags, not paths.
_EXTRACT_CACHE_RE = re.compile(r"extract\..+\.json")


# Exact shape written by the pinned package's writeStamp(): nothing more is
# complete, nothing less is current.
_STAMP_KEYS = frozenset({"version", "hosts", "opts", "at"})
_STAMP_OPT_KEYS = frozenset({"global", "mcp", "hooks", "statusline"})
# Keys the pinned package may persist in .graft/config.json that this
# launcher recognizes. Trail ``pendingSignup`` is intentionally absent:
# any extra key, including that signup claim, fail-closes as unmanaged.
_BUILD_CONFIG_KEYS = frozenset(
    {"includeDirs", "followSubmodules", "followNestedRepos", "brain"}
)

# API tokens the native brain-push path reads; never inherited by a managed
# child even though the brain link itself is already rejected.
_API_SECRET_VARS = ("GH_TOKEN", "GITHUB_TOKEN")
# Host config override that would make the native hook read the developer's
# real Claude settings; dropped so it falls back to the private HOME.
_HOST_CONFIG_VARS = ("CLAUDE_CONFIG_DIR",)

_TEMP_HOME_PREFIX = "sbtd-graft-home-"


# ---------------------------------------------------------------------------
# Path and file proofs (pure reads; fixed sanitized failures)
# ---------------------------------------------------------------------------


def _canonical_root(root: Path) -> Path:
    """Canonical absolute selected root, or a fixed failure."""
    candidate = Path(root)
    if not candidate.is_absolute():
        raise ContractError(
            "invalid-argument", "the selected project root must be an absolute path"
        )
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError:
        raise ContractError(
            "root-missing", "the selected project root does not exist"
        ) from None
    except RuntimeError:
        raise ContractError(
            "root-unsafe", "the selected project root cannot be resolved safely"
        ) from None
    except OSError:
        raise ContractError(
            "root-unsafe", "the selected project root cannot be inspected"
        ) from None
    if resolved != candidate:
        raise ContractError(
            "root-unsafe", "the selected project root must already be canonical"
        )
    if not resolved.is_dir():
        raise ContractError(
            "root-not-directory", "the selected project root is not a directory"
        )
    return resolved


def _contained(
    root_real: Path, parts: tuple[str, ...], *, code: str, message: str
) -> Path:
    """Resolve a path below the canonical root, proving physical containment."""
    candidate = root_real.joinpath(*parts)
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError:
        raise ContractError(code, message) from None
    except RuntimeError:
        raise ContractError(
            "root-unsafe", "a managed Graft path cannot be resolved safely"
        ) from None
    except OSError:
        raise ContractError(
            "root-unsafe", "a managed Graft path cannot be inspected"
        ) from None
    if resolved != candidate or not graft_runtime._is_within(resolved, root_real):
        raise ContractError(
            "root-unsafe", "a managed Graft path escapes the selected project root"
        )
    return resolved


def _require_regular_file(path: Path, *, code: str, message: str) -> None:
    """Nofollow ordinary-file proof (symlinks and special files rejected)."""
    try:
        mode = path.lstat().st_mode
    except OSError:
        raise ContractError(code, message) from None
    if not stat.S_ISREG(mode):
        raise ContractError(code, message)


def _read_regular(path: Path, *, code: str, message: str) -> bytes:
    """Nofollow read of a proven regular file (shared P0 convention)."""
    try:
        with open_regular_file(path, "managed Graft state") as handle:
            return handle.read()
    except TaskDataError:
        raise ContractError(code, message) from None


def _reject_constant(_text: str) -> None:
    raise ValueError("non-finite JSON literal")


def _strict_json(raw: bytes, *, code: str, message: str) -> Any:
    """Strict UTF-8 JSON of any shape: duplicate keys and non-finite fail."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ContractError(code, message) from None
    try:
        return json.loads(
            text,
            object_pairs_hook=graft_runtime._reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (ValueError, RecursionError):
        raise ContractError(code, message) from None


def _strict_json_object(raw: bytes, *, code: str, message: str) -> dict[str, Any]:
    """Strict UTF-8 JSON object: duplicate keys and non-finite literals fail."""
    data = _strict_json(raw, code=code, message=message)
    if not isinstance(data, dict):
        raise ContractError(code, message)
    return data


def _is_reparse(info: os.stat_result) -> bool:
    """Reject Windows reparse attributes on every supported Python version."""
    return bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _prove_source_rel(
    root_real: Path,
    raw: str,
    memo: set[str],
    *,
    code: str,
    message: str,
) -> None:
    """Prove one declared repo-relative source path cannot escape the root.

    String rules mirror the posix-relative shape the pinned package itself
    mints (util/paths.js relPosix): no empty value or NUL, no backslash (a
    separator on Windows), no POSIX-absolute, drive-absolute or UNC form,
    and no empty/``.``/``..`` segment. Then a nofollow lstat walk of the
    existing prefix: every component must be a real directory or, at the
    end, a real regular file — symlinks, junctions/reparse points, special
    files and hardlinked files (``st_nlink > 1``) are rejected, inside the
    root just as across it. A missing component ends the walk proven: the
    native read then fails in place, which is exactly the freshness case a
    rebuilt graph expects. No file content is read or hashed.
    """
    if (
        not raw
        or "\x00" in raw
        or "\\" in raw
        or raw.startswith("/")
        or _DRIVE_ABS_RE.match(raw) is not None
    ):
        raise ContractError(code, message)
    segments = raw.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        raise ContractError(code, message)
    probe = root_real
    for segment in segments:
        probe = probe / segment
        key = str(probe)
        if key in memo:
            continue
        try:
            info = probe.lstat()
        except (FileNotFoundError, NotADirectoryError):
            return
        except OSError:
            raise ContractError(code, message) from None
        mode = info.st_mode
        if stat.S_ISLNK(mode) or _is_reparse(info):
            raise ContractError(code, message)
        if stat.S_ISDIR(mode):
            memo.add(key)
            continue
        if stat.S_ISREG(mode) and info.st_nlink == 1:
            return
        raise ContractError(code, message)


def _prove_span_pointer(
    root_real: Path,
    pointer: str,
    memo: set[str],
    *,
    code: str,
    message: str,
) -> None:
    """Prove the path half of a `path:Lx-Ly` pointer when it has that shape.

    The pinned ask.js parseSpan() matches ``^(.*):L\\d+-L\\d+$`` greedily
    and reads the captured path under the root; a pointer without the span
    suffix never reaches the filesystem and stays unproven by design.
    """
    match = _SPAN_POINTER_RE.fullmatch(pointer)
    if match is not None:
        _prove_source_rel(root_real, match.group(1), memo, code=code, message=message)


def _reject_workspace_scope(root_real: Path) -> None:
    """Fail closed on any native workspace shape before launch or build.

    The pinned package treats the root as a workspace parent — federating
    queries into children named by ``graft/workspace.json`` (joined
    verbatim, so a ``../sibling`` child refreshes outside the root) and, on
    build, DELETING the parent's whole ``graft/`` tree — whenever the index
    parses, or the root has no ``.git`` of its own and at least two
    immediate git children. A managed selected root is never a workspace:
    reject both shapes exactly where the pinned package would act on them.
    ``.git`` probes match native existsSync semantics (links followed).
    """
    if os.path.lexists(root_real.joinpath(*_WORKSPACE_PARTS)):
        raise ContractError(
            "workspace-index",
            "the selected project root holds a graft workspace index; "
            "managed native launch/build serves single roots only",
        )
    if os.path.exists(root_real / ".git"):
        return
    try:
        with os.scandir(root_real) as entries:
            children = sum(
                1
                for entry in entries
                if not entry.name.startswith(".")
                and entry.name not in _SKIP_CHILD_DIRS
                and entry.is_dir(follow_symlinks=False)
                and os.path.exists(root_real / entry.name / ".git")
            )
    except OSError:
        raise ContractError(
            "root-unsafe", "the selected project root cannot be inspected"
        ) from None
    if children >= 2:
        raise ContractError(
            "workspace-parent",
            "the selected project root looks like a workspace parent (no own "
            ".git, several git children); native build would delete its graft/ tree",
        )


def _reject_unsafe_tree(graft_dir: Path) -> None:
    """Nofollow walk of a native input tree: real dirs and single-link files.

    A native build writes ``INDEX.md``, cards and ``.graph``/``.cache``
    files through whatever already sits inside ``graft/`` — a symlink or
    hardlink turns that write into a clobber of the linked victim, and a
    special file (fifo/socket/device/reparse point) can block or redirect
    native reads. Reject all of them; content is never read or hashed.
    """
    pending = [graft_dir]
    while pending:
        current = pending.pop()
        try:
            with os.scandir(current) as entries:
                # DirEntry.stat() reports st_nlink=0 on Windows. Query the
                # actual entry without following links; never relax the
                # single-link ownership requirement to accept that sentinel.
                listing = [
                    (entry, os.stat(entry.path, follow_symlinks=False))
                    for entry in entries
                ]
        except OSError:
            raise ContractError(
                "tree-unsafe", "the native input tree cannot be inspected safely"
            ) from None
        for entry, info in listing:
            mode = info.st_mode
            if stat.S_ISLNK(mode) or _is_reparse(info):
                raise ContractError(
                    "tree-unsafe",
                    "the native input tree holds a link or reparse entry",
                )
            if stat.S_ISDIR(mode):
                pending.append(Path(entry.path))
                continue
            if stat.S_ISREG(mode) and info.st_nlink == 1:
                continue
            raise ContractError(
                "tree-unsafe",
                "the native input tree holds a hardlinked or special entry",
            )


def _validate_graph_data(root_real: Path, memo: set[str]) -> None:
    """Prove the built wiring graph's path data stays inside the root.

    Bounded to the exact pinned consumers: every ``nodes[].path`` is read
    by grep (and becomes a card write target, which must stay inside
    ``graft/``), every ``nodes[].span`` is concatenated into `path:span`
    pointers the greedy span parser re-reads, and any ``edges[].source``/
    ``target`` endpoint matching the span grammar (an unresolved one is
    read verbatim as a source snippet). A missing graph is valid (explicit
    build); an absent ``nodes``/``edges`` array carries no paths to prove.
    """
    if not os.path.lexists(root_real.joinpath(*_GRAPH_PARTS)):
        return
    graph_path = _contained(
        root_real,
        _GRAPH_PARTS,
        code="graph-unsafe",
        message="the built wiring graph cannot be resolved safely",
    )
    data = _strict_json(
        _read_regular(
            graph_path,
            code="graph-unsafe",
            message="the built wiring graph cannot be read safely",
        ),
        code="graph-unsafe",
        message="the built wiring graph is not strict unambiguous JSON",
    )
    if not isinstance(data, dict):
        raise ContractError(
            "graph-unsafe", "the built wiring graph is not a JSON object"
        )
    nodes = data.get("nodes")
    if nodes is not None:
        if not isinstance(nodes, list):
            raise ContractError(
                "graph-unsafe", "the built wiring graph nodes are not an array"
            )
        for node in nodes:
            if not isinstance(node, dict):
                raise ContractError(
                    "graph-unsafe", "a wiring graph node is not an object"
                )
            path = node.get("path")
            span = node.get("span")
            if not isinstance(path, str) or not isinstance(span, str):
                raise ContractError(
                    "graph-unsafe", "a wiring graph node has no provable path/span"
                )
            _prove_source_rel(
                root_real,
                path,
                memo,
                code="graph-unsafe",
                message="a wiring graph node path escapes the selected root",
            )
            if _SPAN_SHAPE_RE.fullmatch(span) is None:
                raise ContractError(
                    "graph-unsafe", "a wiring graph node span is not the pinned grammar"
                )
    edges = data.get("edges")
    if edges is not None:
        if not isinstance(edges, list):
            raise ContractError(
                "graph-unsafe", "the built wiring graph edges are not an array"
            )
        for edge in edges:
            if not isinstance(edge, dict):
                raise ContractError(
                    "graph-unsafe", "a wiring graph edge is not an object"
                )
            for endpoint in (edge.get("source"), edge.get("target")):
                if not isinstance(endpoint, str):
                    raise ContractError(
                        "graph-unsafe", "a wiring graph edge endpoint is not a string"
                    )
                _prove_span_pointer(
                    root_real,
                    endpoint,
                    memo,
                    code="graph-unsafe",
                    message="a wiring graph edge endpoint escapes the selected root",
                )


def _validate_cache_data(root_real: Path, graft_dir: Path, memo: set[str]) -> None:
    """Prove consumable cache/manifest path data stays inside the root.

    ``.cache/extract.<stamp>.json`` entries feed the next in-process build:
    cached ``nodes[].path`` must equal their ``files`` source key (the key a
    real on-disk file was parsed from) and pass the same path/span proofs,
    and cached rawEdge fields the resolver can copy verbatim into an edge
    endpoint (``source``/``targetId``/``specifier``/``name``) must not be
    span-shaped escapes. ``graft/manifest.json`` ``files[].path`` is an
    existence probe under the root, so it gets the same proof. Anything the
    pinned reader itself treats as absent (foreign shape, unknown layout)
    is left to it.
    """
    cache_dir = graft_dir / ".cache"
    if cache_dir.is_dir():
        try:
            names = os.listdir(cache_dir)
        except OSError:
            raise ContractError(
                "cache-unsafe", "the graft cache cannot be inspected safely"
            ) from None
        for name in names:
            if _EXTRACT_CACHE_RE.fullmatch(name) is None:
                continue
            data = _strict_json(
                _read_regular(
                    cache_dir / name,
                    code="cache-unsafe",
                    message="an extract cache cannot be read safely",
                ),
                code="cache-unsafe",
                message="an extract cache is not strict unambiguous JSON",
            )
            if not isinstance(data, dict):
                continue  # the pinned reader discards non-object caches
            files = data.get("files")
            if not isinstance(files, dict):
                continue  # absent or foreign: the pinned reader replays nothing
            for source, entry in files.items():
                if not isinstance(entry, dict):
                    continue
                nodes = entry.get("nodes")
                if nodes is not None:
                    if not isinstance(nodes, list):
                        raise ContractError(
                            "cache-unsafe",
                            "an extract cache entry nodes is not an array",
                        )
                    for node in nodes:
                        if not isinstance(node, dict):
                            raise ContractError(
                                "cache-unsafe", "an extract cache node is not an object"
                            )
                        path = node.get("path")
                        span = node.get("span")
                        if not isinstance(path, str) or not isinstance(span, str):
                            raise ContractError(
                                "cache-unsafe",
                                "an extract cache node has no provable path/span",
                            )
                        if path != source:
                            raise ContractError(
                                "cache-unsafe",
                                "an extract cache node path disagrees with its source key",
                            )
                        _prove_source_rel(
                            root_real,
                            path,
                            memo,
                            code="cache-unsafe",
                            message="an extract cache source path escapes the selected root",
                        )
                        if _SPAN_SHAPE_RE.fullmatch(span) is None:
                            raise ContractError(
                                "cache-unsafe",
                                "an extract cache node span is not the pinned grammar",
                            )
                raw_edges = entry.get("rawEdges")
                if raw_edges is not None:
                    if not isinstance(raw_edges, list):
                        raise ContractError(
                            "cache-unsafe",
                            "an extract cache entry rawEdges is not an array",
                        )
                    for raw in raw_edges:
                        if not isinstance(raw, dict):
                            raise ContractError(
                                "cache-unsafe",
                                "an extract cache raw edge is not an object",
                            )
                        for field in ("source", "targetId", "specifier", "name"):
                            value = raw.get(field)
                            if isinstance(value, str):
                                _prove_span_pointer(
                                    root_real,
                                    value,
                                    memo,
                                    code="cache-unsafe",
                                    message="an extract cache edge field escapes the selected root",
                                )
    if not os.path.lexists(root_real.joinpath(*_MANIFEST_PARTS)):
        return
    manifest_path = _contained(
        root_real,
        _MANIFEST_PARTS,
        code="cache-unsafe",
        message="the graft manifest cannot be resolved safely",
    )
    manifest = _strict_json(
        _read_regular(
            manifest_path,
            code="cache-unsafe",
            message="the graft manifest cannot be read safely",
        ),
        code="cache-unsafe",
        message="the graft manifest is not strict unambiguous JSON",
    )
    if not isinstance(manifest, dict):
        return  # the pinned reader discards a non-object manifest
    files = manifest.get("files")
    if files is None:
        return
    if not isinstance(files, list):
        raise ContractError("cache-unsafe", "the graft manifest files are not an array")
    for ref in files:
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
            raise ContractError(
                "cache-unsafe", "a graft manifest file entry has no provable path"
            )
        _prove_source_rel(
            root_real,
            ref["path"],
            memo,
            code="cache-unsafe",
            message="a graft manifest path escapes the selected root",
        )


def _concept_frontmatter(text: str, *, code: str, message: str) -> dict[str, Any]:
    """Parse one top-level concept file's frontmatter like gray-matter 4.0.3.

    Mirrors the pinned parser: BOM stripped; the file must open with `---`
    (not `----`); an optional language tag on the delimiter line selects
    the engine (`yaml`/`yml` via PyYAML, `json` via strict JSON — anything
    else, including the eval-backed `javascript` engine, is rejected); the
    block ends at the next `\\n---` or EOF; a blank/comment-only block is
    empty data. A non-mapping result has no `sources`/`slug` to prove.
    """
    text = text.removeprefix("\ufeff")
    if not text.startswith("---") or text.startswith("----"):
        return {}
    rest = text[3:]
    newline = re.search(r"\r?\n", rest)
    first_line = rest[: newline.start()] if newline is not None else rest
    language = first_line.strip().lower()
    block_start = newline.end() if newline is not None and language else 0
    body = rest[block_start:]
    close = body.find("\n---")
    block = body if close == -1 else body[:close]
    if re.sub(r"^\s*#[^\n]+", "", block, flags=re.MULTILINE).strip() == "":
        return {}
    if language in ("", "yaml", "yml"):
        try:
            import yaml
        except ImportError:
            raise ContractError(code, message) from None
        try:
            data = yaml.safe_load(block)
        except yaml.YAMLError:
            raise ContractError(code, message) from None
    elif language == "json":
        data = _strict_json(block.encode("utf-8"), code=code, message=message)
    else:
        # The pinned install's other engines eval or throw; neither is a
        # state a managed launch may accept.
        raise ContractError(code, message)
    return data if isinstance(data, dict) else {}


def _validate_concept_data(root_real: Path, graft_dir: Path, memo: set[str]) -> None:
    """Prove top-level concept frontmatter pointers stay inside the root.

    The pinned ask/cards layer parses every top-level ``graft/*.md`` except
    ``INDEX.md``: every string ``sources[].path`` joins the concept's
    comma-joined pointer, whose greedy span capture spans ALL entries, so
    each one must be provably in-root; a span-shaped ``slug`` (or any other
    span-shaped source string) is read as a source snippet. Card subdirs
    are never frontmatter-parsed natively and stay out of scope here.
    """
    try:
        names = os.listdir(graft_dir)
    except OSError:
        raise ContractError(
            "concept-unsafe", "the generated graft tree cannot be inspected safely"
        ) from None
    for name in names:
        if not name.endswith(".md") or name == "INDEX.md":
            continue
        raw = _read_regular(
            graft_dir / name,
            code="concept-unsafe",
            message="a generated concept file cannot be read safely",
        )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise ContractError(
                "concept-unsafe", "a generated concept file is not UTF-8 text"
            ) from None
        frontmatter = _concept_frontmatter(
            text,
            code="concept-unsafe",
            message="a generated concept file frontmatter cannot be proven safe",
        )
        code = "concept-unsafe"
        sources = frontmatter.get("sources")
        if sources is not None and not isinstance(sources, list):
            raise ContractError(
                code, "a concept source collection cannot be proven safe"
            )
        source_strings: list[str] = []
        for item in sources or ():
            if not isinstance(item, dict):
                raise ContractError(code, "a concept source cannot be proven safe")
            path = item.get("path")
            if path is None:
                path = ""
            if not isinstance(path, str):
                raise ContractError(code, "a concept source path cannot be proven safe")
            if path:
                _prove_source_rel(
                    root_real,
                    path,
                    memo,
                    code=code,
                    message="a concept source path escapes the selected root",
                )
                _prove_span_pointer(
                    root_real,
                    path,
                    memo,
                    code=code,
                    message="a concept source pointer escapes the selected root",
                )
            source_strings.append(path)
        joined = ", ".join(source_strings)
        if joined:
            _prove_span_pointer(
                root_real,
                joined,
                memo,
                code=code,
                message="the effective concept source pointer escapes the selected root",
            )
        slug = frontmatter.get("slug")
        if slug is None:
            slug = name[:-3]
        elif not isinstance(slug, str):
            raise ContractError(code, "a concept slug cannot be proven safe")
        _prove_span_pointer(
            root_real,
            slug,
            memo,
            code=code,
            message="a concept slug escapes the selected root",
        )


# Public validation helpers
# ---------------------------------------------------------------------------


def _validate_note_scope(root: Path) -> None:
    """Bound 0.22.0 note/skill reads to the selected root, without reading content."""
    checkout = next((path for path in (root, *root.parents) if (path / ".git").exists()), None)
    if checkout is not None and checkout != root:
        raise ContractError(
            "notes-scope-unsafe", "native notes would read an ancestor outside the selected root"
        )
    note_roots = [root]
    if checkout is None:
        try:
            with os.scandir(root) as entries:
                names = sorted(
                    entry.name for entry in entries
                    if not entry.name.startswith(".") and entry.is_dir(follow_symlinks=False)
                )
            # Match upstream childCheckouts; its note lookup has no build skip list.
            note_roots.extend(
                [root / name for name in names if (root / name / ".git").exists()][:64]
            )
        except OSError:
            raise ContractError(
                "notes-scope-unsafe", "native note checkouts cannot be inspected safely"
            ) from None
    for note_root in note_roots:
        for parts in ((".trail",), (".claude", "skills")):
            relative = (*note_root.relative_to(root).parts, *parts)
            if not os.path.lexists(root.joinpath(*relative)):
                continue
            tree = _contained(
                root, relative, code="tree-unsafe",
                message="the native notes or skills tree cannot be resolved safely",
            )
            if not tree.is_dir():
                raise ContractError("tree-unsafe", "the native notes or skills path is not a directory")
            _reject_unsafe_tree(tree)


def validate_build_scope(root: Path) -> None:
    """Prove the selected root is safe for ANY native launch or build.

    Import-safe and side-effect free (pure reads; no writes, no repairs),
    and usable before any explicit native build even when the wiring graph
    and stamp do not exist yet. In order: the canonical-root proof; the
    project ``.graft`` build-config rejection (brain link, out-of-root
    follows, unmanaged keys); the workspace scope rejection (any
    ``graft/workspace.json`` index, or a parent shape the pinned package
    would auto-detect — no own ``.git`` plus two or more immediate git
    children — whose build deletes the parent's ``graft/`` tree); a
    nofollow walk of the generated ``graft/`` tree rejecting links,
    reparse entries, hardlinks and special files; and the bounded data
    proofs over the built graph, extract caches, manifest and top-level
    concept frontmatter. Missing graph, stamp, caches and source files are
    valid: native freshness handles absence. Any failure is a fixed
    sanitized ContractError.
    """
    root_real = _canonical_root(root)
    _reject_unsafe_build_config(root_real)
    _reject_workspace_scope(root_real)
    _validate_note_scope(root_real)
    if not os.path.lexists(root_real / "graft"):
        return  # explicit build: nothing generated yet, nothing more to prove
    graft_dir = _contained(
        root_real,
        ("graft",),
        code="tree-unsafe",
        message="the generated graft tree cannot be resolved safely",
    )
    if not graft_dir.is_dir():
        raise ContractError(
            "tree-unsafe", "the generated graft path is not a real directory"
        )
    _reject_unsafe_tree(graft_dir)
    memo: set[str] = set()
    _validate_graph_data(root_real, memo)
    _validate_cache_data(root_real, graft_dir, memo)
    _validate_concept_data(root_real, graft_dir, memo)


def validate_runtime(node: Path, cli: Path) -> dict[str, str]:
    """Prove the exact pinned native runtime from metadata, without execution.

    Both paths must be absolute nofollow ordinary files. The CLI must resolve
    to the package-owned ``dist/cli.js`` or ``dist/bin/graft.js`` inside a real
    ``@nanonets/graft`` package whose ``package.json`` version is exactly the
    pinned release; unverified shell shims are not accepted. Returns the
    canonical node path, the proven package CLI path, the package directory
    and the pinned version.
    """
    node_path = Path(node)
    cli_path = Path(cli)
    if not node_path.is_absolute() or not cli_path.is_absolute():
        raise ContractError(
            "invalid-argument", "the node and Graft CLI paths must be absolute"
        )
    _require_regular_file(
        node_path,
        code="runtime-missing",
        message="the Node runtime is not an ordinary file",
    )
    _require_regular_file(
        cli_path,
        code="runtime-missing",
        message="the Graft CLI is not an ordinary file",
    )
    located = graft_runtime._locate_package(str(cli_path))
    if located is None:
        raise ContractError(
            "runtime-identity",
            "the Graft CLI does not resolve to the pinned @nanonets/graft package",
        )
    package_dir, version = located
    if version != GRAFT_PINNED_VERSION:
        raise ContractError(
            "runtime-version",
            "the installed Graft package is not the pinned "
            f"{GRAFT_PINNED_VERSION} release",
        )
    return {
        "node": os.path.realpath(node_path),
        "cli": os.path.realpath(cli_path),
        "package": str(package_dir),
        "version": version,
    }


def validate_project(root: Path) -> dict[str, Any]:
    """Prove the selected root holds a complete current native wiring state.

    Routes through ``validate_build_scope`` first (canonical root, build
    config, workspace scope, generated-tree and graph/cache/concept data
    proofs), then requires beneath the canonical root: an actual built
    wiring graph (``graft/.graph/wiring.json``, a non-empty ordinary file
    physically contained in the root) and the native wiring stamp
    (``graft/.cache/wiring-stamp.json``) as strict unambiguous JSON in
    exactly the pinned shape — version exactly 0.22.0, hosts exactly
    ``["agents"]``, all four wiring opts explicitly false. Anything
    missing, unreadable, stale, foreign or ambiguous fails closed; nothing
    is written or repaired, because a guessed stamp is precisely what makes
    native upkeep dangerous. Returns the canonical root and the parsed
    native stamp.
    """
    validate_build_scope(root)
    root_real = _canonical_root(root)
    graft_dir = _contained(
        root_real,
        ("graft",),
        code="graph-missing",
        message="the selected project root has no graft/ context directory",
    )
    if not graft_dir.is_dir():
        raise ContractError(
            "graph-missing",
            "the selected project root has no graft/ context directory",
        )
    graph = _contained(
        root_real,
        _GRAPH_PARTS,
        code="graph-missing",
        message="the selected project root has no built wiring graph",
    )
    _require_regular_file(
        graph,
        code="graph-missing",
        message="the wiring graph is not an ordinary file",
    )
    try:
        empty = graph.stat().st_size == 0
    except OSError:
        raise ContractError(
            "graph-missing", "the wiring graph cannot be inspected"
        ) from None
    if empty:
        raise ContractError("graph-missing", "the wiring graph is empty")
    stamp_path = _contained(
        root_real,
        _STAMP_PARTS,
        code="stamp-missing",
        message=(
            "the native wiring stamp is missing; the managed init flow must "
            "create it before any native launch"
        ),
    )
    stamp = _strict_json_object(
        _read_regular(
            stamp_path,
            code="stamp-invalid",
            message="the native wiring stamp cannot be read safely",
        ),
        code="stamp-invalid",
        message="the native wiring stamp is not strict unambiguous JSON",
    )
    if (
        set(stamp) != _STAMP_KEYS
        or not isinstance(stamp.get("at"), str)
        or not stamp["at"]
    ):
        raise ContractError(
            "stamp-invalid", "the native wiring stamp is not the complete pinned shape"
        )
    if stamp["version"] != GRAFT_PINNED_VERSION:
        raise ContractError(
            "stamp-version",
            "the native wiring stamp belongs to a different Graft release; "
            "re-run the managed init flow instead of allowing native upkeep",
        )
    hosts = stamp["hosts"]
    if not isinstance(hosts, list) or hosts != ["agents"]:
        raise ContractError(
            "stamp-hosts",
            "the native wiring stamp does not name exactly the AGENTS.md host",
        )
    opts = stamp["opts"]
    if (
        not isinstance(opts, dict)
        or set(opts) != _STAMP_OPT_KEYS
        or any(opts[key] is not False for key in _STAMP_OPT_KEYS)
    ):
        raise ContractError(
            "stamp-opts",
            "the native wiring stamp does not record global/mcp/hooks/statusline "
            "all declined",
        )
    return {"root": str(root_real), "stamp": stamp}


def managed_environment(root: Path, private_home: Path) -> dict[str, str]:
    """The only environment a managed native Graft child may see.

    Starts from the P1-03 scrubbed env (no GRAFT_*/LLM/cloud variables, no
    Node preloads, no CI, ``DO_NOT_TRACK``/``DNT`` on, dotenv fed from
    /dev/null), additionally drops inherited API tokens and the Claude config
    override, then re-roots every home-like variable at the provided private
    temporary HOME. ``GRAFT_DIR`` pins native sidecar state to the selected
    root's ``graft/`` directory and ``CLAUDE_PROJECT_DIR`` is forced to the
    validated root — native hooks consult it before the event payload cwd, so
    no caller override or payload subdirectory can redirect native state.

    Native MCP tools otherwise refresh/rebuild before answering. A managed
    startup guard cannot cover data derived by that post-launch build, so
    freshness-triggering queries must read only the already-proven graph.

    The project's ``.graft/config.json``, when present, must be strict JSON
    with no unmanaged keys, no brain link (cloud activation is forbidden), no
    submodule/nested-repo following (out-of-root walks) and no unmanaged
    include narrowing. The private HOME must be an existing absolute
    directory outside the selected root and must not be the user's real home.
    """
    root_real = _canonical_root(root)
    _reject_unsafe_build_config(root_real)
    home_real = _canonical_private_home(private_home, root_real)
    env = graft_runtime._managed_env(dict(os.environ), ci=False)
    for key in _API_SECRET_VARS + _HOST_CONFIG_VARS:
        env.pop(key, None)
    home = str(home_real)
    env["HOME"] = home
    env["USERPROFILE"] = home
    env["CODEX_HOME"] = os.path.join(home, ".codex")
    env["XDG_CONFIG_HOME"] = os.path.join(home, ".config")
    env["XDG_CACHE_HOME"] = os.path.join(home, ".cache")
    env["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
    env["XDG_STATE_HOME"] = os.path.join(home, ".local", "state")
    env["GRAFT_DIR"] = str(root_real / "graft")
    env["CLAUDE_PROJECT_DIR"] = str(root_real)
    env["GRAFT_NO_GITIGNORE"] = "1"
    env["GRAFT_NO_IGNORE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("NODE_COMPILE_CACHE", None)
    env["GRAFT_NO_REFRESH"] = "1"
    env["NODE_DISABLE_COMPILE_CACHE"] = "1"
    return env


def _reject_unsafe_build_config(root_real: Path) -> None:
    """Fail closed on a project .graft brain link or unsafe build config."""
    if not os.path.lexists(root_real.joinpath(*_BUILD_CONFIG_PARTS)):
        return
    config_path = _contained(
        root_real,
        _BUILD_CONFIG_PARTS,
        code="build-config-unsafe",
        message="the project .graft build configuration cannot be resolved safely",
    )
    config = _strict_json_object(
        _read_regular(
            config_path,
            code="build-config-unsafe",
            message="the project .graft build configuration cannot be read safely",
        ),
        code="build-config-unsafe",
        message="the project .graft build configuration is not strict unambiguous JSON",
    )
    if set(config) - _BUILD_CONFIG_KEYS:
        raise ContractError(
            "build-config-unsafe",
            "the project .graft build configuration carries unmanaged keys",
        )
    if "brain" in config:
        raise ContractError(
            "brain-link",
            "the project is linked to a remote Graft brain; cloud activation "
            "is forbidden",
        )
    for key in ("followSubmodules", "followNestedRepos"):
        value = config.get(key)
        if value is not None and value is not False:
            raise ContractError(
                "build-config-unsafe",
                "the project .graft build configuration follows repositories "
                "outside the selected root",
            )
    include_dirs = config.get("includeDirs")
    if include_dirs is not None and (
        not isinstance(include_dirs, list) or include_dirs
    ):
        raise ContractError(
            "build-config-unsafe",
            "the project .graft build configuration narrows the graph to "
            "unmanaged include directories",
        )


def _canonical_private_home(private_home: Path, root_real: Path) -> Path:
    """Existing canonical private HOME directory, disjoint from the project."""
    candidate = Path(private_home)
    if not candidate.is_absolute():
        raise ContractError(
            "invalid-argument", "the private temporary HOME must be an absolute path"
        )
    try:
        resolved = candidate.resolve(strict=True)
    except (FileNotFoundError, RuntimeError, OSError):
        raise ContractError(
            "home-invalid", "the private temporary HOME is unavailable"
        ) from None
    if not resolved.is_dir():
        raise ContractError(
            "home-invalid", "the private temporary HOME is not a directory"
        )
    if graft_runtime._is_within(resolved, root_real) or graft_runtime._is_within(
        root_real, resolved
    ):
        raise ContractError(
            "home-invalid",
            "the private temporary HOME overlaps the selected project root",
        )
    try:
        real_home = Path.home().resolve()
    except (RuntimeError, OSError):
        real_home = None
    if real_home is not None and resolved == real_home:
        raise ContractError(
            "home-invalid",
            "the private temporary HOME is the user's real home directory",
        )
    return resolved


# ---------------------------------------------------------------------------
# MCP session root resolution (process cwd, fixed for the connection)
# ---------------------------------------------------------------------------

# Exact gitdir pointer grammar a linked worktree or absorbed submodule
# ``.git`` file holds (worktree creation writes an absolute target, submodule
# absorption may write a relative one); the launcher never dereferences the
# target, the file is only a repository-boundary marker.
_GITDIR_POINTER_RE = re.compile(r"gitdir: [^\r\n\x00]+")
# A genuine pointer line is a few dozen bytes; anything larger is ambiguous.
_GITFILE_MAX_BYTES = 4096


def _git_boundary(marker: Path) -> bool:
    """Whether ``marker`` is a safe-shaped ``.git`` boundary candidate.

    Absence is the only False answer. A real directory or a nofollow regular
    gitdir pointer file is a boundary CANDIDATE; links, reparse points,
    special files and ambiguous pointer files fail closed, so an unsafe
    marker is never silently skipped and its project attributed to an outer
    repository. The shape alone never selects a project: the launch cwd's
    Git context must additionally pass ``_prove_checkout_context``.
    """
    try:
        info = marker.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        raise ContractError(
            "root-unsafe", "a .git marker cannot be inspected safely"
        ) from None
    if stat.S_ISLNK(info.st_mode) or _is_reparse(info) or not (
        stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)
    ):
        raise ContractError(
            "root-unsafe", "a .git marker must be a real directory or file"
        )
    if stat.S_ISDIR(info.st_mode):
        return True
    if not 0 < info.st_size <= _GITFILE_MAX_BYTES:
        raise ContractError(
            "root-unsafe", "a .git worktree pointer file is not the pinned shape"
        )
    try:
        text = _read_regular(
            marker,
            code="root-unsafe",
            message="a .git worktree pointer file cannot be read safely",
        ).decode("utf-8")
    except UnicodeDecodeError:
        raise ContractError(
            "root-unsafe", "a .git worktree pointer file is not the pinned shape"
        ) from None
    body = text.removesuffix("\n")
    if "\n" in body or _GITDIR_POINTER_RE.fullmatch(body) is None:
        raise ContractError(
            "root-unsafe", "a .git worktree pointer file is not the pinned shape"
        )
    return True


def _trusted_git(candidate: Path) -> str:
    """Canonical absolute Git executable from PATH, outside the candidate.

    The checkout proof child must never run project-owned code: only PATH
    entries that are absolute AND whose canonical directory lies outside
    the boundary candidate are consulted, so a relative entry, an empty
    entry or a project ``bin/`` directory (including one reaching the
    repository through a symlink alias) can never supply the executable.
    The found executable's own canonical path must likewise resolve
    outside the candidate. Windows accepts only an explicitly selected
    native git.exe, never a PATHEXT batch wrapper or implicit cwd lookup.
    Any entry that cannot be proven is skipped; no usable installation
    fails closed rather than falling back to an unqualified name.
    """
    executable_name = "git.exe" if os.name == "nt" else "git"
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry or not os.path.isabs(entry):
            continue
        try:
            real_dir = Path(entry).resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if graft_runtime._is_within(real_dir, candidate):
            continue
        try:
            resolved = (real_dir / executable_name).resolve(strict=True)
            if not resolved.is_file() or not os.access(resolved, os.X_OK):
                continue
        except (OSError, RuntimeError):
            continue
        if graft_runtime._is_within(resolved, candidate):
            continue
        if os.name == "nt" and resolved.suffix.lower() != ".exe":
            continue
        return str(resolved)
    raise ContractError(
        "root-unsafe", "no trusted Git installation is available for the checkout proof"
    )


def _prove_checkout_context(cwd: Path, boundary: Path) -> None:
    """Prove the launch cwd's own Git context resolves to exactly boundary.

    The marker walk alone proves nothing about the actual launch cwd: a cwd
    inside a bare repository's data tree (``git init --bare`` has no
    ``.git`` marker of its own) or inside a checkout's ``.git``
    administrative tree would otherwise be silently attributed to the
    nearest marked ancestor. This is the only Git invocation this launcher
    ever makes — a read-only probe OF THE LAUNCH CWD with no inherited
    GIT_* variable, no system or global config and no prompting, run from a
    ``_trusted_git`` executable, so the environment, per-user overrides and
    project-owned PATH entries can never steer it (a context Git itself
    refuses, e.g. a bare repository or dubious ownership, fails closed).
    The probe must report a real work tree whose top-level realpath-matches
    the boundary exactly: an administrative-tree or bare cwd, an ambiguous
    answer, or a top-level anywhere else all fail closed, and no parent or
    outer graph is ever borrowed.
    """
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_")
    }
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["LC_ALL"] = "C"
    try:
        completed = subprocess.run(
            [
                _trusted_git(boundary),
                "--no-optional-locks",
                "-C",
                str(cwd),
                "rev-parse",
                "--show-toplevel",
                "--is-inside-git-dir",
            ],
            env=env,
            capture_output=True,
            text=True,
            # Git for Windows emits UTF-8 paths even when Python uses an ANSI locale.
            encoding="utf-8" if os.name == "nt" else None,
            timeout=15,
            check=False,
        )
    except UnicodeDecodeError:
        raise ContractError(
            "root-unsafe", "the Git checkout proof returned undecodable output"
        ) from None
    except (OSError, subprocess.SubprocessError):
        raise ContractError(
            "root-unsafe", "the Git checkout proof could not be executed"
        ) from None
    if completed.returncode != 0:
        raise ContractError(
            "no-project",
            "the process working directory is not inside a Git work tree",
        )
    lines = completed.stdout.split("\n")
    if len(lines) != 3 or lines[2] != "":
        raise ContractError(
            "root-unsafe", "the Git checkout proof returned an ambiguous answer"
        )
    top, inside_git_dir = lines[0], lines[1]
    if inside_git_dir != "false":
        raise ContractError(
            "no-project",
            "the process working directory is Git administrative data, not a work tree",
        )
    if (
        not top
        or not os.path.isabs(top)
        or os.path.normcase(os.path.realpath(top))
        != os.path.normcase(str(boundary))
    ):
        raise ContractError(
            "root-unsafe",
            "the launch cwd's Git checkout does not match the nearest .git boundary",
        )


def _resolve_session_root() -> Path:
    """Canonical nearest proven Git repository/worktree root for this cwd.

    The global MCP definition carries no fixed root: the launch process's
    own working directory selects exactly one project, and the connection
    keeps that root for its entire life (a later host ``cd`` or protocol
    roots change never re-targets it). The walk starts at the canonical cwd
    and ascends to the NEAREST safe-shaped ``.git`` boundary, so a nested
    repository always wins over any outer graph and a neutral common parent
    of several projects finds no project at all. The user's home directory
    is a hard stop: it is never a project and the walk never climbs above
    it. A boundary candidate is adopted only after
    ``_prove_checkout_context`` proves the LAUNCH CWD's own Git context is
    a real work tree whose top-level is exactly that boundary — a cwd
    inside a bare repository's data tree or a checkout's administrative
    ``.git`` tree is refused, never attributed to the marked ancestor.
    Marker shape, environment and config overrides can never substitute for
    that proof.
    """
    try:
        cwd = Path(os.getcwd()).resolve(strict=True)
    except (OSError, RuntimeError):
        raise ContractError(
            "root-unsafe",
            "the process working directory cannot be resolved safely",
        ) from None
    home = Path(os.path.realpath(os.path.expanduser("~")))
    for candidate in (cwd, *cwd.parents):
        if candidate == home:
            raise ContractError(
                "no-project",
                "the user home directory is not a selectable project root",
            )
        if _git_boundary(candidate / ".git"):
            _prove_checkout_context(cwd, candidate)
            return candidate
    raise ContractError(
        "no-project",
        "the process working directory does not belong to a Git repository",
    )


# ---------------------------------------------------------------------------
# Native launch (CLI only)
# ---------------------------------------------------------------------------


def _proven_hook_module(package_dir: Path) -> Path:
    """The pinned package's own dist/claude/hooks.js as a nofollow file."""
    module = package_dir / "dist" / "claude" / "hooks.js"
    _require_regular_file(
        module,
        code="runtime-identity",
        message="the pinned Graft package hook module is unavailable",
    )
    return module


def _proven_bridge() -> Path:
    """The installed owned bridge asset as a nofollow ordinary file."""
    _require_regular_file(
        _BRIDGE,
        code="runtime-unavailable",
        message="the installed Graft hook bridge asset is unavailable",
    )
    return _BRIDGE


def _payload_cwd(payload: bytes) -> Path:
    """Canonical project cwd declared by a hook event payload.

    Only the containment decision is taken from the payload; its bytes are
    otherwise forwarded untouched and never persisted. A payload that cannot
    prove its project is a fixed failure, never a fallback no-op.
    """
    data = _strict_json_object(
        payload,
        code="payload-invalid",
        message="the hook event payload is not a strict JSON object",
    )
    cwd = data.get("cwd")
    if not isinstance(cwd, str) or not cwd or not os.path.isabs(cwd):
        raise ContractError(
            "payload-invalid", "the hook event payload has no provable project cwd"
        )
    return Path(os.path.realpath(cwd))


def _wait_with_signal_forwarding(proc: subprocess.Popen[bytes]) -> int:
    """Wait for the child, forwarding termination signals to it.

    The host manages this launcher as the direct child, so a signal that
    reaches only us must still reach the native grandchild; a group-wide
    signal reaches both, and the extra forward is harmless.
    """
    if os.name != "posix":
        try:
            return proc.wait()
        except KeyboardInterrupt:
            try:
                proc.terminate()
            except OSError:
                pass
            return proc.wait()

    def _forward(signum: int, _frame: Any) -> None:
        try:
            os.killpg(proc.pid, signum)
        except (ProcessLookupError, OSError):
            pass

    previous: dict[int, Any] = {}
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        previous[signum] = signal.signal(signum, _forward)
    try:
        return proc.wait()
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def _serve_child(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    stdin_bytes: bytes | None,
) -> int:
    """Spawn the validated native child with inherited protocol stdio.

    stdin/stdout/stderr default to inheritance: stdout carries the hook's
    JSON output untouched, and a hook payload is written to the child's
    stdin exactly as received. The child's exit status
    is propagated (128+n when it dies by signal n); a spawn failure is a
    fixed launch error, never a retry.
    """
    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.PIPE if stdin_bytes is not None else None,
            start_new_session=os.name == "posix",
        )
    except OSError:
        raise ContractError(
            "launch-failed", "the validated native runtime could not be started"
        ) from None
    if stdin_bytes is not None:
        assert proc.stdin is not None
        try:
            proc.stdin.write(stdin_bytes)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            # The child already exited; its own status carries the truth.
            pass
    returncode = _wait_with_signal_forwarding(proc)
    if returncode < 0:
        return 128 + (-returncode)
    return returncode


# Native MCP stdio framing (pinned dist/mcp/server.js): newline-delimited
# JSON-RPC 2.0, one message per line in each direction, no Content-Length
# headers; native exits 0 on stdin EOF and answers unparseable lines itself
# with id null / -32700. These are the only protocol errors this wrapper
# ever emits on its own.
_MCP_RPC_PARSE_ERROR = -32700
_MCP_RPC_INVALID_REQUEST = -32600
_MCP_RPC_REFUSED = -32603
# Fixed sanitized refusal text: never echoes request bytes, config values or
# path detail; the failing rule name rides only on the stderr line.
_MCP_REFUSAL_MESSAGE = (
    "the managed Graft wiring state failed validation; the request was refused"
)


def _terminate_child(proc: subprocess.Popen[bytes]) -> None:
    """Best-effort SIGTERM of the native child and its own posix group.

    The group target mirrors _wait_with_signal_forwarding: the child was
    spawned in a new session, so the stop reaches the same processes a
    forwarded host signal would.
    """
    if os.name == "posix":
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            return
        except (ProcessLookupError, OSError):
            pass
    try:
        proc.terminate()
    except OSError:
        pass


def _mcp_error_line(request_id: Any, code: int, message: str) -> bytes:
    """One fixed sanitized JSON-RPC error line for a refused host request."""
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        },
        separators=(",", ":"),
    )
    return payload.encode("utf-8") + b"\n"


def _gate_host_line(
    line: bytes, root_real: Path
) -> tuple[int, str, Any, ContractError] | None:
    """Gate one host-native protocol line through a FRESH project validation.

    Returns None when the line may be forwarded verbatim. Only a request
    object (a strict JSON object with a string ``method`` and an ``id``) can
    make native dispatch a tool, so notifications, responses and blank lines
    pass ungated; every request is validated against the CURRENT on-disk
    wiring state, because the running child reloads a replaced graph on
    mtime even with ``GRAFT_NO_REFRESH`` set. Any other return value is a
    refusal — the JSON-RPC error code/message to answer with, the request id
    to address (None when the line never proved one) and the sanitized
    ContractError for the fixed stderr line — the line is never forwarded
    and the session stops. A line the guard cannot classify safely is
    refused rather than passed to the native parser, whose duplicate-key
    last-wins semantics could otherwise smuggle an unvalidated method past
    the gate.
    """
    if not line.strip():
        return None  # blank lines carry no request; native ignores them
    try:
        message = _strict_json(
            line,
            code="protocol-invalid",
            message="the host protocol line is not strict unambiguous JSON",
        )
    except ContractError as error:
        return (_MCP_RPC_PARSE_ERROR, "the host line is not strict JSON", None, error)
    if not isinstance(message, dict):
        return (
            _MCP_RPC_INVALID_REQUEST,
            "the host line is not a JSON-RPC request object",
            None,
            ContractError(
                "protocol-invalid",
                "the host protocol line is not a JSON-RPC request object",
            ),
        )
    if not isinstance(message.get("method"), str) or "id" not in message:
        return None  # notification or response: no tool dispatch, no answer
    try:
        validate_project(root_real)
    except ContractError as error:
        return (_MCP_RPC_REFUSED, _MCP_REFUSAL_MESSAGE, message["id"], error)
    return None


def _serve_mcp_child(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    root_real: Path,
) -> int:
    """Spawn the validated native MCP server behind the per-request guard.

    Two daemon pump threads forward the JSON-lines protocol in both
    directions; every stdout write (forwarded native reply or fixed refusal)
    is serialized under one lock so a line is never torn. Host EOF closes
    the child's stdin and native exits on its own; a refusal or a dead host
    terminates the child; a dead child ends the wait and any completed
    replies still in the pipe are drained before the exit status is decided
    — the fixed failure exit on refusal, otherwise the child's own status
    (128+n when it dies by signal n). The host remains the single lifetime
    controller: no retry, no scheduler, and signals received while waiting
    are still forwarded to the child group by the shared wait helper.
    """
    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            start_new_session=os.name == "posix",
        )
    except OSError:
        raise ContractError(
            "launch-failed", "the validated native runtime could not be started"
        ) from None
    assert proc.stdin is not None and proc.stdout is not None
    native_input, native_output = proc.stdin, proc.stdout
    write_lock = threading.Lock()
    stopping = threading.Event()
    refusal_exit: list[int] = []

    def _emit_host(line: bytes) -> None:
        with write_lock:
            remaining = memoryview(line)
            while remaining:
                written = os.write(sys.stdout.fileno(), remaining)
                remaining = remaining[written:]

    def _host_to_native() -> None:
        try:
            # A daemon may remain blocked when native exits first. Keep its
            # BufferedReader separate from sys.stdin: Python finalization
            # must never wait for the standard stream's buffered I/O lock.
            with os.fdopen(os.dup(sys.stdin.fileno()), "rb") as host_input:
                for line in host_input:
                    if stopping.is_set():
                        break
                    refusal = _gate_host_line(line, root_real)
                    if refusal is not None:
                        code, text, request_id, error = refusal
                        refusal_exit.append(error.exit_code)
                        stopping.set()
                        try:
                            _emit_host(_mcp_error_line(request_id, code, text))
                        except (BrokenPipeError, OSError):
                            pass
                        os.write(
                            sys.stderr.fileno(),
                            f"sbtd-graft-entry: {error.message}\n".encode(),
                        )
                        break
                    native_input.write(line)
                    native_input.flush()
        except BrokenPipeError:
            # The native child closed stdin; its exit status remains authoritative.
            pass
        except OSError as error:
            if error.errno == errno.EPIPE:
                pass
            else:
                refusal_exit.append(2)
                stopping.set()
        except (ValueError, ContractError):
            refusal_exit.append(2)
            stopping.set()
        finally:
            try:
                native_input.close()
            except (BrokenPipeError, OSError):
                pass
            if stopping.is_set():
                _terminate_child(proc)

    def _native_to_host() -> None:
        while True:
            line = native_output.readline()
            if not line:
                return  # child closed stdout: every completed reply is drained
            try:
                _emit_host(line)
            except (BrokenPipeError, OSError):
                stopping.set()
                _terminate_child(proc)  # the host is gone; the child is useless
                return

    stdin_pump = threading.Thread(
        target=_host_to_native, name="graft-host-in", daemon=True
    )
    stdout_pump = threading.Thread(
        target=_native_to_host, name="graft-native-out", daemon=True
    )
    stdout_pump.start()
    stdin_pump.start()
    returncode = _wait_with_signal_forwarding(proc)
    stopping.set()
    # Backpressure is not EOF: preserve pending native bytes until the host
    # reads or closes its pipe rather than truncating a response on a timer.
    stdout_pump.join()
    if refusal_exit:
        return refusal_exit[0]
    if returncode < 0:
        return 128 + (-returncode)
    return returncode


def _seed_update_cache(home: Path) -> None:
    """Seed the private HOME's graft update cache as freshly checked.

    Native CLI boots (and the MCP server's own upkeep) spawn a detached
    ``_update-check`` npm probe unless ``~/.graft/update-check.json`` holds a
    ``checkedAt`` younger than 24h. Seeding it suppresses that probe only
    while the stamp stays inside that window: a native server outliving 24h
    can still spawn the updater, and detached grandchildren (the Stop
    hook's sync build, the ``graft ask``/``check`` children hooks spawn)
    can outlive the removed HOME and recreate the temp path — the seed is a
    suppression hint, not a lifetime guarantee. ``latest: null`` records an
    unknown answer: no registry lookup happened and none is claimed;
    ``checkedAt`` is only a suppression stamp. Written before launch, so no
    concurrent reader exists and a plain write suffices.
    """
    cache_path = home.joinpath(*_UPDATE_CACHE_PARTS)
    payload = json.dumps(
        {"latest": None, "checkedAt": int(time.time() * 1000)},
        separators=(",", ":"),
    ).encode("utf-8")
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(payload)
    except OSError:
        raise ContractError(
            "launch-failed",
            "the scoped temporary HOME could not be prepared for native launch",
        ) from None


def _run_mcp(args: argparse.Namespace) -> int:
    runtime = validate_runtime(Path(args.node), Path(args.entry))
    project = validate_project(_resolve_session_root())
    root_real = Path(project["root"])
    home = Path(tempfile.mkdtemp(prefix=_TEMP_HOME_PREFIX))
    try:
        env = managed_environment(root_real, home)
        _seed_update_cache(home)
        argv = [runtime["node"], runtime["cli"], "mcp", project["root"]]
        return _serve_mcp_child(argv, cwd=root_real, env=env, root_real=root_real)
    finally:
        shutil.rmtree(home, ignore_errors=True)


def _run_hook(args: argparse.Namespace) -> int:
    payload = sys.stdin.buffer.read()
    cwd_real = _payload_cwd(payload)
    declared = Path(args.root)
    if not declared.is_absolute():
        raise ContractError(
            "invalid-argument", "the selected project root must be an absolute path"
        )
    bound = Path(os.path.realpath(declared))
    if not graft_runtime._is_within(cwd_real, bound):
        # Global hook entries run in every project the host opens; an event
        # belonging to another project is the single explicit no-op. The
        # comparison never demands the bound root: a deleted bound project
        # cannot contain an existing payload cwd, so the no-op stays safe
        # and unrelated projects are never disrupted by the missing root.
        return 0
    runtime = validate_runtime(Path(args.node), Path(args.entry))
    project = validate_project(Path(args.root))
    proven_root = Path(project["root"])
    hook_module = _proven_hook_module(Path(runtime["package"]))
    bridge = _proven_bridge()
    home = Path(tempfile.mkdtemp(prefix=_TEMP_HOME_PREFIX))
    try:
        env = managed_environment(proven_root, home)
        _seed_update_cache(home)
        argv = [
            runtime["node"],
            str(bridge),
            "--entry",
            str(hook_module),
            "--event",
            args.event,
        ]
        return _serve_child(argv, cwd=proven_root, env=env, stdin_bytes=payload)
    finally:
        shutil.rmtree(home, ignore_errors=True)

def _relative_analysis_path(value: str) -> str:
    candidate = Path(value)
    if (
        not value
        or candidate.is_absolute()
        or "\\" in value
        or ".." in candidate.parts
    ):
        raise ContractError(
            "invalid-argument",
            "analysis file arguments must stay inside the selected project",
        )
    return value


def _analysis_argv(args: argparse.Namespace) -> list[str]:
    command = args.analysis_command
    for value_name in ("query", "file", "symbol", "pattern"):
        value = getattr(args, value_name, None)
        if value is not None and value.startswith("-"):
            raise ContractError(
                "invalid-argument",
                "analysis values must not be parsed as native options",
            )
    if command == "ask":
        return ["ask", args.query, ".", "--json", "--no-refresh"]
    if command == "map":
        return ["map", ".", "--json", "--no-refresh"]
    if command == "skeleton":
        return [
            "skeleton",
            _relative_analysis_path(args.file),
            ".",
            "--json",
            "--no-refresh",
        ]
    if command == "callers":
        return ["callers", args.symbol, ".", "--json", "--no-refresh"]
    if command == "check":
        return ["check", ".", "--json"]
    if command == "grep":
        return ["grep", args.pattern, ".", "--fixed", "--json", "--no-refresh"]
    if command == "blast":
        return ["blast", ".", "--format", "json", "--no-refresh"]
    raise ContractError("invalid-argument", "unsupported analysis command")


def _run_analyze(args: argparse.Namespace) -> int:
    argv_tail = _analysis_argv(args)
    runtime = validate_runtime(Path(args.node), Path(args.entry))
    project = validate_project(Path(args.root))
    root_real = Path(project["root"])
    home = Path(tempfile.mkdtemp(prefix=_TEMP_HOME_PREFIX))
    try:
        env = managed_environment(root_real, home)
        _seed_update_cache(home)
        argv = [runtime["node"], runtime["cli"], *argv_tail]
        return _serve_child(argv, cwd=root_real, env=env, stdin_bytes=None)
    finally:
        shutil.rmtree(home, ignore_errors=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sbtd-graft-entry",
        description=(
            "Internal managed launcher for the pinned Graft native MCP server "
            "and Codex hook events. Validates the canonical selected root, the "
            "workspace scope, the generated tree, the graph/cache/concept "
            "path data, the pinned package identity, the complete current "
            "wiring stamp and the built graph before any native launch; "
            "never repairs, never writes outside its scoped temporary HOME."
        ),
    )
    modes = parser.add_subparsers(dest="mode", required=True)
    mcp = modes.add_parser(
        "mcp",
        help="serve the cwd-selected project root's graph over MCP stdio",
    )
    _bind_runtime_arguments(mcp)
    hook = modes.add_parser(
        "hook", help="forward one Codex hook event to the pinned native module"
    )
    _bind_launch_arguments(hook)
    hook.add_argument(
        "--event",
        required=True,
        choices=HOOK_EVENTS,
        help="native hook sub-command for this Codex event",
    )
    analyze = modes.add_parser(
        "analyze", help="run one closed read-only Graft analysis command"
    )
    _bind_launch_arguments(analyze)
    analyses = analyze.add_subparsers(dest="analysis_command", required=True)
    analyses.add_parser("ask").add_argument("query")
    analyses.add_parser("map")
    analyses.add_parser("skeleton").add_argument("file")
    analyses.add_parser("callers").add_argument("symbol")
    analyses.add_parser("check")
    analyses.add_parser("grep").add_argument("pattern")
    analyses.add_parser("blast")
    return parser


def _bind_launch_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", required=True, help="absolute selected project root")
    _bind_runtime_arguments(parser)


def _bind_runtime_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--node",
        required=True,
        help="absolute Node >=20 binary (ordinary file, not a shim or symlink)",
    )
    parser.add_argument(
        "--entry",
        required=True,
        help="absolute pinned @nanonets/graft dist/cli.js or dist/bin/graft.js",
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.mode == "mcp":
            return _run_mcp(args)
        if args.mode == "hook":
            return _run_hook(args)
        return _run_analyze(args)
    except ContractError as error:
        print(f"sbtd-graft-entry: {error.message}", file=sys.stderr)
        return error.exit_code


if __name__ == "__main__":
    sys.exit(main())
