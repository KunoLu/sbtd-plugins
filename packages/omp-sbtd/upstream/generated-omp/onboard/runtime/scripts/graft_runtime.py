"""Shared Graft CLI detection and installation runtime (P1-03).

This module is the single Python implementation behind the managed
``install-graft`` flow. It exports exactly two public functions and never
prints to stdout/stderr; callers own all presentation:

- ``check_graft()`` — read-only detection of the pinned Graft CLI. It
  distinguishes *package present* from *CLI verified usable*, never executes
  an unrecognized ``graft`` executable, and works even when npm or network
  access is unavailable (only the local ``graft --version`` probe is used,
  never the network-bound ``graft version`` command).
- ``install_graft(*, confirmed, telemetry_only=False)`` — plans (always
  read-only) and, only after explicit confirmation, installs the frozen
  ``@nanonets/graft@0.22.0`` tarball with integrity verification and
  conservative telemetry opt-out persistence.

Pinned facts (registry-verified, do not "upgrade" to latest automatically):
tarball integrity sha512-UQ6VTzNYwRehZ5GXB/RZI/gdY9vkinMlEO4JKuqfvFu+7WKKE7dtf8cWsLtKDlQG/5yGGm5oBe7wS2Av5nXe7g==,
registry repository ``trailhq/Trail-Code``, registry gitHead absent, Node >=20.

Managed subprocesses always run with telemetry/trackable activation
scrubbed: DO_NOT_TRACK=1, DNT=1, dotenv disabled via DOTENV_CONFIG_PATH and
forced quiet via DOTENV_CONFIG_QUIET=true, and
GRAFT_/OPENROUTER_/ORCAROUTER_/OPENAI_/ANTHROPIC_/NODE_OPTIONS/NODE_PATH
removed. Installation adds CI=1 so the pinned postinstall exits instead of
spawning its detached flush. The telemetry CLI is never invoked (it triggers
the preAction updater); opt-out is persisted by editing
``~/.graft/telemetry.json`` directly and conservatively.

Platform scope: POSIX (macOS/Linux) is primary; Windows shim layouts are
probed best-effort but are not a validated target of this change.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

GRAFT_PACKAGE = "@nanonets/graft"
GRAFT_PINNED_VERSION = "0.22.0"
GRAFT_SPEC = f"{GRAFT_PACKAGE}@{GRAFT_PINNED_VERSION}"
GRAFT_TARBALL_URL = "https://registry.npmjs.org/@nanonets/graft/-/graft-0.22.0.tgz"
GRAFT_TARBALL_INTEGRITY = (
    "sha512-UQ6VTzNYwRehZ5GXB/RZI/gdY9vkinMlEO4JKuqfvFu+7WKKE7dtf8cWsLtKDlQG/5yGGm5oBe7wS2Av5nXe7g=="
)
GRAFT_REGISTRY_GIT_HEAD = None
NODE_MIN_MAJOR = 20

# npm >= 12 blocks lifecycle scripts by default; the pinned package needs its
# own postinstall plus the tree-sitter native builds. This is the exact allow
# list proven during the P0 capability spike — pass it only when relevant.
NPM12_ALLOW_SCRIPTS = (
    "@nanonets/graft",
    "tree-sitter",
    "tree-sitter-go",
    "tree-sitter-java",
    "tree-sitter-php",
    "tree-sitter-swift",
    "tree-sitter-kotlin",
    "tree-sitter-python",
    "tree-sitter-javascript",
    "tree-sitter-typescript",
    "@davisvaughan/tree-sitter-r",
    "tree-sitter-cli",
    "fsevents",
    "esbuild",
)

VERSION_TIMEOUT = 10
NPM_QUERY_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 180
NPM_INSTALL_TIMEOUT = 900

_SCRUBBED_PREFIXES = (
    "GRAFT_",
    "TRAIL_",
    "OPENROUTER_",
    "ORCAROUTER_",
    "OPENAI_",
    "ANTHROPIC_",
)
_SCRUBBED_VARS = (
    "NODE_OPTIONS",
    "NODE_PATH",
    "DOTENV_CONFIG_DEBUG",
    "DOTENV_CONFIG_QUIET",
)

_ADVICE_MISSING = (
    "Install the pinned Graft CLI with the managed install-graft flow after "
    "explicit confirmation; it fetches the frozen @nanonets/graft@0.22.0 "
    "tarball, verifies its integrity, and disables anonymous telemetry."
)


class _TelemetryConflict(Exception):
    """Telemetry state changed under us or is not safe to touch."""


class _TelemetryPersistError(Exception):
    """Telemetry state could not be persisted truthfully."""


def _managed_env(base: dict[str, str], *, ci: bool) -> dict[str, str]:
    """Subprocess env for Graft/npm children: telemetry off, no LLM/cloud
    activation variables, no Node preloads, and a silent dotenv loader.

    Only the managed child sees this; the user's real environment is never
    mutated. ``ci=True`` is used for installation so the pinned postinstall
    takes its immediate-exit path instead of the detached flush.
    """
    env = dict(base)
    for key in list(env):
        if key in _SCRUBBED_VARS or key.startswith(_SCRUBBED_PREFIXES):
            del env[key]
    env.pop("CI", None)
    env["DO_NOT_TRACK"] = "1"
    env["DNT"] = "1"
    # 0.22.0 also ships Trail; managed Graft must never rename or rewire a repo.
    env["TRAIL_INVOKED_AS"] = "graft"
    env["TRAIL_NO_FETCH"] = "1"
    env["GRAFT_NO_TRAIL_SWITCH"] = "1"
    env["DOTENV_CONFIG_PATH"] = os.devnull
    env["DOTENV_CONFIG_QUIET"] = "true"
    if ci:
        env["CI"] = "1"
    return env


@contextlib.contextmanager
def _isolated_npm_probe_env(env: dict[str, str]):
    """Managed env for read-only npm queries with an isolated cache.

    Even local npm queries (`--version`, `config get prefix`, `root -g`) can
    emit error logs into the npm cache on failure. check/plan must leave the
    user's HOME and real npm cache byte-identical, so probes redirect the
    cache to a private temp dir (removed on exit) and disable notifier,
    funding, and audit chatter. HOME stays real so the user's npmrc prefix
    configuration is still honored.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="graft-npm-probe-"))
    try:
        probe = _managed_env(env, ci=False)
        probe["NPM_CONFIG_CACHE"] = str(temp_dir)
        probe["NPM_CONFIG_UPDATE_NOTIFIER"] = "false"
        probe["NPM_CONFIG_FUND"] = "false"
        probe["NPM_CONFIG_AUDIT"] = "false"
        yield probe
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _run(
    command: list[str] | tuple[str, ...],
    *,
    env: dict[str, str],
    timeout: int,
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _which(name: str, env: dict[str, str]) -> str | None:
    return shutil.which(name, path=env.get("PATH") or os.defpath)


def _tail(text: str | None, *, limit: int = 800) -> str | None:
    """Truncated output tail for failure reports. Never includes env data."""
    if not text:
        return None
    lines = text.strip().splitlines()
    tail = "\n".join(lines[-5:]).strip()
    return tail[-limit:] if tail else None


def _home_dir(env: dict[str, str]) -> Path:
    home = env.get("HOME") or (env.get("USERPROFILE") if os.name == "nt" else None)
    return Path(home) if home else Path.home()


def _parse_major(version: str | None) -> int | None:
    if not version:
        return None
    text = version.strip().lstrip("vV")
    major, _, _ = text.partition(".")
    try:
        return int(major)
    except ValueError:
        return None


def _first_line(output: str | None) -> str | None:
    if not output:
        return None
    for line in output.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _node_info(env: dict[str, str]) -> dict[str, object]:
    path = _which("node", env)
    version = None
    if path:
        completed = _run(
            [path, "--version"],
            env=_managed_env(env, ci=False),
            timeout=VERSION_TIMEOUT,
        )
        if completed is not None and completed.returncode == 0:
            version = _first_line(completed.stdout)
    major = _parse_major(version)
    return {
        "path": path,
        "version": version,
        "compatible": (major >= NODE_MIN_MAJOR) if major is not None else None,
    }


def _npm_version(probe_env: dict[str, str], npm_path: str) -> str | None:
    completed = _run(
        [npm_path, "--version"],
        env=probe_env,
        timeout=NPM_QUERY_TIMEOUT,
    )
    if completed is None or completed.returncode != 0:
        return None
    return _first_line(completed.stdout)


def _npm_configured_prefix(probe_env: dict[str, str], npm_path: str) -> str | None:
    completed = _run(
        [npm_path, "config", "get", "prefix"], env=probe_env, timeout=NPM_QUERY_TIMEOUT
    )
    candidate = (
        _first_line(completed.stdout)
        if completed is not None and completed.returncode == 0
        else None
    )
    if candidate and candidate != "undefined":
        return candidate
    completed = _run(
        [npm_path, "prefix", "-g"], env=probe_env, timeout=NPM_QUERY_TIMEOUT
    )
    if completed is not None and completed.returncode == 0:
        candidate = _first_line(completed.stdout)
        if candidate and candidate != "undefined":
            return candidate
    return None


def _npm_global_root(probe_env: dict[str, str]) -> Path | None:
    """Local, read-only npm global root probe; None when npm is unusable."""
    npm_path = _which("npm", probe_env)
    if not npm_path:
        return None
    completed = _run(
        [npm_path, "root", "-g"],
        env=probe_env,
        timeout=NPM_QUERY_TIMEOUT,
    )
    if completed is None or completed.returncode != 0:
        return None
    line = _first_line(completed.stdout)
    return Path(line) if line else None


def _package_identity(pkg_dir: Path) -> str | None:
    """Pinned-package version when pkg_dir is a real @nanonets/graft package."""
    package_json = pkg_dir / "package.json"
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("name") != GRAFT_PACKAGE:
        return None
    version = data.get("version")
    return version if isinstance(version, str) and version else ""


def _package_dir_from_path(path: Path) -> Path | None:
    parts = path.parts
    for index in range(len(parts) - 2):
        if (
            parts[index] == "node_modules"
            and parts[index + 1] == "@nanonets"
            and parts[index + 2] == "graft"
        ):
            return Path(*parts[: index + 3])
    return None


def _locate_package(executable: str) -> tuple[Path, str] | None:
    """Bind a command to the frozen package, not unverified shim text.

    Accept the package-owned ``dist/cli.js`` or the 0.22.0 npm bin
    ``dist/bin/graft.js``. Shell and Windows shims are still blocked without
    execution; their text or a nearby package does not prove identity.
    """
    real = Path(os.path.realpath(executable))
    pkg_dir = _package_dir_from_path(real)
    if pkg_dir is None:
        return None
    allowed = {pkg_dir / "dist" / "cli.js", pkg_dir / "dist" / "bin" / "graft.js"}
    if real not in allowed:
        return None
    version = _package_identity(pkg_dir)
    if version is None:
        return None
    return pkg_dir, version


def check_graft() -> dict[str, object]:
    """Read-only detection of the pinned Graft CLI.

    Returns the common CLI-tool fields plus Graft-specific status. ``installed``
    is true ONLY for a verified usable pinned CLI: the executable's identity
    must resolve to the @nanonets/graft package and a local ``--version``
    probe in a sanitized environment must print exactly the pinned version.
    Unknown-identity executables are reported as conflicts and never run.
    Performs no home/project writes and no network access.
    """
    return _check_graft(dict(os.environ))


def _check_graft(env: dict[str, str]) -> dict[str, object]:
    result: dict[str, object] = {
        "name": "graft",
        "category": "cli",
        "installed": False,
        "path": None,
        "version": None,
        "globalInstall": (
            f'python "{Path(__file__).with_name("onboard.py")}" install-graft --yes'
        ),
        "projectInstall": None,
        "optional": True,
        "advice": _ADVICE_MISSING,
        "packagePresent": False,
        "packageVersion": None,
        "identity": None,
        "status": "not-available",
        "reason": "no graft executable or package found",
        "nextStep": (
            "Ask for confirmation, then run the managed install-graft flow to "
            f"install the pinned {GRAFT_SPEC}."
        ),
        "pinnedVersion": GRAFT_PINNED_VERSION,
        "node": _node_info(env),
    }

    executable = _which("graft", env)
    located: tuple[Path, str] | None = None
    if executable:
        result["path"] = executable
        located = _locate_package(executable)
        if located is None:
            result["identity"] = "unknown"
            result["status"] = "blocked"
            result["reason"] = (
                "a `graft` executable exists but its identity does not resolve "
                "to the @nanonets/graft package; it was not executed"
            )
            result["advice"] = (
                "An unrecognized `graft` executable is on PATH. The managed "
                "tooling never runs or overwrites unverified binaries; resolve "
                "the conflict manually before installing."
            )
            result["nextStep"] = (
                "Manually remove or rename the unrecognized `graft` executable, "
                "then rerun check."
            )
            return result
        _, package_version = located
        result["identity"] = "nanonets-package"
        result["packagePresent"] = True
        result["packageVersion"] = package_version or None

        completed = _run(
            [executable, "--version"],
            env=_managed_env(env, ci=False),
            timeout=VERSION_TIMEOUT,
        )
        if completed is None or completed.returncode != 0:
            detail = (
                "probe timed out or could not start"
                if completed is None
                else f"exit code {completed.returncode}"
            )
            stderr_tail = _tail(completed.stderr) if completed else None
            result["status"] = "blocked"
            result["reason"] = (
                f"graft --version failed ({detail}); the CLI is present but "
                "not usable (native startup failure, e.g. missing tree-sitter "
                "build)"
            )
            if stderr_tail:
                result["probeStderr"] = stderr_tail
            result["advice"] = (
                "The pinned Graft package is installed but its CLI crashes at "
                "startup. Reinstall via the managed install-graft flow so "
                "native lifecycle scripts run with the npm>=12 allow list."
            )
            result["nextStep"] = (
                "Ask for confirmation, then repair with the managed install-graft flow."
            )
            return result

        version = _first_line(completed.stdout)
        result["version"] = version
        if version != GRAFT_PINNED_VERSION:
            result["status"] = "blocked"
            result["reason"] = (
                f"installed Graft version {version!r} is not the pinned "
                f"{GRAFT_PINNED_VERSION}; capabilities were only proven for "
                "the pinned release"
            )
            result["advice"] = (
                "A different Graft version is installed. The workflow pins "
                f"{GRAFT_SPEC}; replace it through the managed install-graft "
                "flow after confirmation."
            )
            result["nextStep"] = (
                "Ask for confirmation, then install the pinned release with "
                "the managed install-graft flow."
            )
            return result

        if result["node"]["compatible"] is False:
            result["status"] = "blocked"
            result["reason"] = (
                f"the pinned Graft CLI requires Node >= {NODE_MIN_MAJOR}; "
                "the detected Node version is incompatible"
            )
            result["advice"] = (
                "Install a compatible Node runtime before using the pinned Graft CLI."
            )
            result["nextStep"] = f"Install Node >= {NODE_MIN_MAJOR}, then rerun check."
            return result

        result["installed"] = True
        result["status"] = "available"
        result["reason"] = None
        result["nextStep"] = None
        result["advice"] = (
            "Pinned Graft CLI is installed and verified usable. Host/graph "
            "wiring is a separate, later step; this status does not imply "
            "graph or host availability."
        )
        return result

    # No executable on PATH: distinguish a broken/partial global install
    # (package present, bin missing) from a clean slate. npm may be absent;
    # detection must not depend on it.
    with _isolated_npm_probe_env(env) as probe_env:
        npm_root = _npm_global_root(probe_env)
    if npm_root is not None:
        version = _package_identity(npm_root / "@nanonets" / "graft")
        if version is not None:
            result["packagePresent"] = True
            result["packageVersion"] = version or None
            result["identity"] = "nanonets-package"
            result["status"] = "blocked"
            result["reason"] = (
                "the @nanonets/graft package exists in the npm global root but "
                "no usable `graft` executable is on PATH (broken or partial "
                "installation)"
            )
            result["advice"] = (
                "A partial Graft installation exists without a working CLI. "
                "Repair it with the managed install-graft flow after "
                "confirmation."
            )
            result["nextStep"] = (
                "Ask for confirmation, then repair with the managed install-graft flow."
            )
    return result


def _read_file_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_telemetry_json(raw: bytes) -> dict[str, object]:
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    if not isinstance(data, dict):
        raise TypeError("telemetry JSON root is not an object")
    return data


def _is_within(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _inspect_telemetry(home: Path) -> dict[str, object]:
    """Read-only safety inspection of ~/.graft/telemetry.json.

    Flags unsafe parent/file types, symlink escapes, malformed or duplicate
    JSON, and non-object roots. Anything unsafe is a conflict to report, not
    something to guess at, delete, or overwrite.
    """
    target = home / ".graft" / "telemetry.json"
    info: dict[str, object] = {
        "path": str(target),
        "exists": False,
        "enabled": None,
        "safe": True,
        "problem": None,
        "changes": {"enabled": False},
        "preservesUnknownKeys": True,
    }

    def unsafe(problem: str) -> dict[str, object]:
        info["safe"] = False
        info["problem"] = problem
        return info

    parent = target.parent
    if os.path.lexists(parent):
        try:
            parent_stat = os.lstat(parent)
        except OSError as exc:
            return unsafe(f"cannot inspect ~/.graft: {exc.strerror or exc}")
        if stat.S_ISLNK(parent_stat.st_mode):
            resolved = parent.resolve()
            if not _is_within(resolved, home.resolve()):
                return unsafe("~/.graft is a symlink escaping the home directory")
            if not resolved.is_dir():
                return unsafe("~/.graft symlink does not resolve to a directory")
        elif not stat.S_ISDIR(parent_stat.st_mode):
            return unsafe("~/.graft exists but is not a directory")

    if not os.path.lexists(target):
        return info

    info["exists"] = True
    try:
        target_stat = os.lstat(target)
    except OSError as exc:
        return unsafe(f"cannot inspect telemetry.json: {exc.strerror or exc}")
    if stat.S_ISLNK(target_stat.st_mode):
        resolved_target = target.resolve()
        if not _is_within(resolved_target, parent.resolve()):
            return unsafe("telemetry.json is a symlink escaping ~/.graft")
        if not resolved_target.is_file():
            return unsafe("telemetry.json symlink does not resolve to a file")
    elif not stat.S_ISREG(target_stat.st_mode):
        return unsafe("telemetry.json exists but is not a regular file")

    try:
        data = _parse_telemetry_json(target.read_bytes())
    except (TypeError, ValueError, UnicodeDecodeError) as exc:
        return unsafe(f"telemetry.json is not valid JSON: {exc}")
    except OSError as exc:
        return unsafe(f"telemetry.json is not readable: {exc.strerror or exc}")
    enabled = data.get("enabled")
    info["enabled"] = enabled if isinstance(enabled, bool) else None
    return info


def _persist_telemetry_disabled(home: Path) -> dict[str, object]:
    """Create ``enabled: false`` telemetry state without overwriting Graft.

    Graft's own ``patchState`` read-modify-write is explicitly uncoordinated
    across processes. An existing mutable state therefore belongs to Graft:
    changing it here could lose fields written after any Python-side read.
    A missing state is published with a same-directory hard link, whose
    no-clobber semantics safely reject a concurrent creator.
    """
    inspection = _inspect_telemetry(home)
    target = Path(str(inspection["path"]))
    if not inspection["safe"]:
        raise _TelemetryConflict(str(inspection["problem"]))
    if inspection["exists"] and inspection["enabled"] is False:
        return {
            "path": str(target),
            "changed": False,
            "enabled": False,
            "preservedKeys": [],
            "created": False,
        }
    if inspection["exists"]:
        raise _TelemetryConflict(
            "telemetry.json already exists and needs a Graft-owned update; "
            "refusing to overwrite it without a shared writer protocol"
        )

    parent = target.parent
    try:
        if not os.path.lexists(parent):
            parent.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise _TelemetryConflict(
            "~/.graft was created concurrently; refusing to overwrite Graft-owned state"
        ) from exc
    except OSError as exc:
        raise _TelemetryPersistError(
            f"cannot create ~/.graft: {exc.strerror or exc}"
        ) from exc

    new_bytes = b'{\n  "enabled": false\n}\n'
    temp_path: str | None = None
    try:
        fd, temp_path = tempfile.mkstemp(
            dir=str(parent), prefix=".telemetry-", suffix=".tmp"
        )
        with os.fdopen(fd, "wb") as handle:
            handle.write(new_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o600)
        os.link(temp_path, target)
        os.unlink(temp_path)
        temp_path = None
    except FileExistsError as exc:
        raise _TelemetryConflict(
            "telemetry.json was created or updated concurrently; refusing to "
            "overwrite the Graft-owned state"
        ) from exc
    except OSError as exc:
        raise _TelemetryPersistError(
            f"cannot create telemetry.json: {exc.strerror or exc}"
        ) from exc
    finally:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    return {
        "path": str(target),
        "changed": True,
        "enabled": False,
        "preservedKeys": [],
        "created": True,
    }


def _fetch_tarball(url: str, dest: Path, timeout: int) -> None:
    """Download the frozen tarball into private temp storage."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "sbtd-graft-runtime/1.0"}
    )
    with (
        urllib.request.urlopen(request, timeout=timeout) as response,
        open(dest, "wb") as handle,
    ):
        shutil.copyfileobj(response, handle, length=256 * 1024)
    os.chmod(dest, 0o600)


def _verify_integrity(path: Path) -> bool:
    digest = hashlib.sha512()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(256 * 1024), b""):
            digest.update(chunk)
    computed = "sha512-" + base64.b64encode(digest.digest()).decode("ascii")
    return computed == GRAFT_TARBALL_INTEGRITY


def _prefix_writable(prefix: Path) -> bool:
    for candidate in (prefix / "bin", prefix / "lib" / "node_modules", prefix):
        probe = candidate
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        if not os.access(probe, os.W_OK):
            return False
    return True


def _build_plan(env: dict[str, str], before: dict[str, object]) -> dict[str, object]:
    """Read-only installation plan: frozen package, actual target prefix,
    telemetry target/changes, native script policy. No writes, no downloads."""
    node = _node_info(env)
    with _isolated_npm_probe_env(env) as probe_env:
        npm_path = _which("npm", probe_env)
        npm_version = _npm_version(probe_env, npm_path) if npm_path else None
        npm_major = _parse_major(npm_version)
        allow_scripts = (
            list(NPM12_ALLOW_SCRIPTS)
            if npm_major is not None and npm_major >= 12
            else None
        )
        prefix = _npm_configured_prefix(probe_env, npm_path) if npm_path else None
    home = _home_dir(env)
    telemetry = _inspect_telemetry(home)
    command: list[str] = [
        npm_path or "npm",
        "install",
        "-g",
        "--prefix",
        prefix or "<npm-global-prefix>",
        "--ignore-scripts=false",
        "--foreground-scripts",
    ]
    if allow_scripts:
        command.append("--allow-scripts=" + ",".join(allow_scripts))
    command.append("<verified-tarball>")

    replaces = None
    if before.get("packagePresent") and before.get("packageVersion") not in (
        None,
        GRAFT_PINNED_VERSION,
    ):
        replaces = {"version": before.get("packageVersion")}

    return {
        "package": GRAFT_SPEC,
        "pinnedVersion": GRAFT_PINNED_VERSION,
        "tarballUrl": GRAFT_TARBALL_URL,
        "integrity": GRAFT_TARBALL_INTEGRITY,
        "registryGitHead": GRAFT_REGISTRY_GIT_HEAD,
        "prefix": prefix,
        "node": node,
        "npm": {
            "path": npm_path,
            "version": npm_version,
            "allowScripts": allow_scripts,
            "ignoreScripts": False,
        },
        "command": command,
        "telemetry": telemetry,
        "env": {
            "DO_NOT_TRACK": "1",
            "DNT": "1",
            "TRAIL_INVOKED_AS": "graft",
            "TRAIL_NO_FETCH": "1",
            "GRAFT_NO_TRAIL_SWITCH": "1",
            "CI": "1",
            "DOTENV_CONFIG_PATH": os.devnull,
            "DOTENV_CONFIG_QUIET": "true",
            "scrubbedPrefixes": list(_SCRUBBED_PREFIXES),
            "scrubbedVars": list(_SCRUBBED_VARS),
            "npmProbeCache": "isolated private temp dir, removed after probing",
        },
        "replaces": replaces,
    }


def _preflight_blocker(
    env: dict[str, str],
    before: dict[str, object],
    plan: dict[str, object],
) -> tuple[str, str] | None:
    """Prerequisite/conflict gate. Every blocker is a real, truthful stage."""
    node = plan["node"]
    assert isinstance(node, dict)
    if not node.get("path"):
        return (
            "node",
            (
                f"Node.js >={NODE_MIN_MAJOR} is required but no node executable "
                "was found; install or activate Node first (not done automatically)"
            ),
        )
    if node.get("compatible") is not True:
        version = node.get("version") or "unknown"
        return (
            "node",
            (
                f"Node.js {version} does not satisfy the pinned package's "
                f"node >={NODE_MIN_MAJOR} engine requirement"
            ),
        )
    npm = plan["npm"]
    assert isinstance(npm, dict)
    if not npm.get("path"):
        return (
            "npm",
            (
                "npm is required for the global install but was not found; "
                "install npm/Node first (not done automatically)"
            ),
        )
    if not npm.get("version"):
        return ("npm", "npm was found but `npm --version` failed")
    if not plan.get("prefix"):
        return (
            "prefix",
            "could not resolve the configured npm global prefix",
        )
    prefix = Path(str(plan["prefix"]))
    if not _prefix_writable(prefix):
        return (
            "permission",
            (
                f"npm global prefix {prefix} is not writable by this user; "
                "fix permissions or use a user-owned prefix"
            ),
        )
    if before.get("path") and before.get("identity") == "unknown":
        return (
            "conflict",
            (
                "an unrecognized `graft` executable already occupies PATH; not "
                "overwriting an unowned binary — resolve it manually first"
            ),
        )
    telemetry = plan["telemetry"]
    assert isinstance(telemetry, dict)
    if not telemetry.get("safe"):
        return (
            "telemetry",
            f"telemetry target is unsafe to modify: {telemetry.get('problem')}",
        )
    return None


def _verify_installation(
    env: dict[str, str], prefix: Path
) -> tuple[bool, str | None, bool]:
    """Post-install gate: actual installed metadata + runnable local version.

    Returns (ok, failure_detail, partial_installation). npm exit 0 or a mere
    directory's existence is never treated as success on its own.
    """
    pkg_candidates = (
        prefix / "lib" / "node_modules" / "@nanonets" / "graft",
        prefix / "node_modules" / "@nanonets" / "graft",
    )
    pkg_dir = next(
        (
            candidate
            for candidate in pkg_candidates
            if (candidate / "package.json").is_file()
        ),
        None,
    )
    if pkg_dir is None:
        return False, "installed package metadata not found under the npm prefix", False
    version = _package_identity(pkg_dir)
    if version is None:
        return (
            False,
            "installed package.json is not a valid @nanonets/graft package",
            True,
        )
    if version != GRAFT_PINNED_VERSION:
        return (
            False,
            (
                f"installed version {version!r} does not match pinned "
                f"{GRAFT_PINNED_VERSION}"
            ),
            True,
        )
    bin_candidates = (
        prefix / "bin" / "graft",
        prefix / "graft.cmd",
        prefix / "graft",
    )
    executable = next(
        (candidate for candidate in bin_candidates if candidate.exists()), None
    )
    if executable is None:
        return False, "graft executable was not created in the npm prefix", True
    if _locate_package(str(executable)) != (pkg_dir.resolve(), GRAFT_PINNED_VERSION):
        return (
            False,
            "installed command does not resolve to the package-owned CLI",
            True,
        )
    completed = _run(
        [str(executable), "--version"],
        env=_managed_env(env, ci=False),
        timeout=VERSION_TIMEOUT,
    )
    if completed is None or completed.returncode != 0:
        detail = (
            "probe timed out or could not start"
            if completed is None
            else f"exit code {completed.returncode}: {_tail(completed.stderr) or 'no stderr'}"
        )
        return False, f"installed graft --version is not runnable ({detail})", True
    reported = _first_line(completed.stdout)
    if reported != GRAFT_PINNED_VERSION:
        return (
            False,
            (
                f"installed CLI reports version {reported!r}, not pinned "
                f"{GRAFT_PINNED_VERSION}"
            ),
            True,
        )
    return True, None, True


def install_graft(
    *, confirmed: bool, telemetry_only: bool = False
) -> tuple[dict[str, object], int]:
    """Plan or perform the pinned Graft CLI installation.

    ``telemetry_only=True`` authorizes only telemetry persistence for a pinned
    CLI that remains verified at this invocation; it never falls through to
    package installation.

    Read-only status gates run before the confirmation gate, so an
    unconfirmed probe (``install-graft --json`` without ``--yes``) already
    returns ``already-installed`` (exit 0, only when the telemetry opt-out is
    also already persisted — fully read-only) or ``blocked`` (exit 2, real
    prerequisite/conflict stage) truthfully; wrappers only need to prompt
    when the probe returns ``needs-confirmation``. An unconfirmed probe makes
    zero writes: no downloads, no installs, no telemetry edits, and npm
    prefix/version queries run with an isolated throwaway cache so the user's
    HOME and real npm cache stay byte-identical.

    With ``confirmed=True``: downloads the frozen tarball into private temp
    storage, verifies the frozen SRI, installs via npm into the configured
    global prefix with native lifecycle scripts enabled (npm>=12 allow list)
    under DNT+CI, verifies actual installed metadata and a runnable local
    ``--version``, then persists telemetry opt-out. Failures report the real
    stage and any partial installation; nothing is auto-uninstalled or
    rolled back.

    Exit codes: 0 installed/already-installed, 2 confirmation needed or
    prerequisite/conflict blocked, 1 operational failure.
    """
    env = dict(os.environ)
    return _install_graft(env, confirmed=confirmed, telemetry_only=telemetry_only)


def _install_graft(
    env: dict[str, str], *, confirmed: bool, telemetry_only: bool = False
) -> tuple[dict[str, object], int]:
    home = _home_dir(env)
    before = _check_graft(env)
    if telemetry_only and not before.get("installed"):
        return {
            "mode": "install-graft",
            "before": before,
            "status": "blocked",
            "stage": "telemetry-only",
            "reason": (
                "the previously verified pinned Graft CLI is no longer installed; "
                "telemetry-only confirmation cannot install a package"
            ),
        }, 2
    plan = _build_plan(env, before)
    result: dict[str, object] = {
        "mode": "install-graft",
        "plan": plan,
        "before": before,
    }
    # Read-only status gates run BEFORE the confirmation gate so that an
    # unconfirmed probe (install-graft --json without --yes) already reports
    # already-installed/blocked truthfully; wrappers only prompt when the
    # status is needs-confirmation. None of these branches write anything.
    if before.get("installed"):
        # Idempotent path: the pinned CLI is already verified usable. The only
        # remaining managed action is telemetry opt-out persistence.
        telemetry_state = plan["telemetry"]
        assert isinstance(telemetry_state, dict)
        if not telemetry_state.get("safe"):
            result["status"] = "blocked"
            result["stage"] = "telemetry"
            result["reason"] = (
                "telemetry target is unsafe to modify: "
                f"{telemetry_state.get('problem')}"
            )
            return result, 2
        if telemetry_state.get("enabled") is False:
            result["status"] = "already-installed"
            result["telemetry"] = {
                "path": telemetry_state["path"],
                "changed": False,
                "enabled": False,
                "preservedKeys": [],
                "created": False,
            }
            result["after"] = before
            result["reason"] = (
                "pinned Graft CLI already verified usable and telemetry "
                "opt-out already persisted; no changes needed"
            )
            return result, 0
        if not confirmed:
            result["status"] = "needs-confirmation"
            result["reason"] = (
                "pinned Graft CLI already verified usable; persisting the "
                "telemetry opt-out (enabled=false) still requires explicit "
                "confirmation; no changes were made"
            )
            return result, 2
        result["status"] = "already-installed"
        try:
            telemetry = _persist_telemetry_disabled(home)
        except _TelemetryConflict as exc:
            result["status"] = "blocked"
            result["stage"] = "telemetry"
            result["reason"] = str(exc)
            return result, 2
        except _TelemetryPersistError as exc:
            result["status"] = "failed"
            result["stage"] = "telemetry-persist"
            result["reason"] = str(exc)
            return result, 1
        result["telemetry"] = telemetry
        result["after"] = _check_graft(env)
        result["reason"] = (
            "pinned Graft CLI already verified usable; telemetry opt-out persisted"
        )
        return result, 0

    blocker = _preflight_blocker(env, before, plan)
    if blocker is not None:
        stage, reason = blocker
        result["status"] = "blocked"
        result["stage"] = stage
        result["reason"] = reason
        return result, 2

    if not confirmed:
        result["status"] = "needs-confirmation"
        result["reason"] = (
            "explicit confirmation is required before any download, install, "
            "or telemetry write; no changes were made"
        )
        return result, 2

    prefix = Path(str(plan["prefix"]))
    install_env = _managed_env(env, ci=True)
    command = plan["command"]
    assert isinstance(command, list)

    temp_dir = Path(tempfile.mkdtemp(prefix="graft-runtime-"))
    os.chmod(temp_dir, 0o700)
    tarball = temp_dir / f"graft-{GRAFT_PINNED_VERSION}.tgz"
    try:
        try:
            _fetch_tarball(GRAFT_TARBALL_URL, tarball, DOWNLOAD_TIMEOUT)
        except (OSError, urllib.error.URLError) as exc:
            result["status"] = "failed"
            result["stage"] = "download"
            result["reason"] = (
                f"could not download the frozen tarball from {GRAFT_TARBALL_URL}: {exc}"
            )
            result["partialInstallation"] = False
            return result, 1

        if not _verify_integrity(tarball):
            result["status"] = "failed"
            result["stage"] = "verify-integrity"
            result["reason"] = (
                "downloaded tarball does not match the frozen integrity "
                f"{GRAFT_TARBALL_INTEGRITY}; refusing to install"
            )
            result["partialInstallation"] = False
            return result, 1

        argv = [
            str(tarball) if part == "<verified-tarball>" else part for part in command
        ]
        completed = _run(argv, env=install_env, timeout=NPM_INSTALL_TIMEOUT)
        result["npmInstall"] = {
            "argv": argv,
            "exitCode": completed.returncode if completed else None,
        }
        if completed is None:
            result["status"] = "failed"
            result["stage"] = "npm-install"
            result["reason"] = "npm install timed out or could not start"
        elif completed.returncode != 0:
            result["status"] = "failed"
            result["stage"] = "npm-install"
            detail = _tail(completed.stderr) or _tail(completed.stdout)
            result["reason"] = "npm install failed"
            if detail:
                result["npmStderr"] = detail
        if result.get("status") == "failed":
            result["partialInstallation"] = (
                _package_identity(
                    prefix / "lib" / "node_modules" / "@nanonets" / "graft"
                )
                is not None
            )
            return result, 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    ok, detail, partial = _verify_installation(env, prefix)
    if not ok:
        result["status"] = "failed"
        result["stage"] = "verify-install"
        result["reason"] = detail
        result["partialInstallation"] = partial
        return result, 1

    try:
        telemetry = _persist_telemetry_disabled(home)
    except _TelemetryConflict as exc:
        result["status"] = "blocked"
        result["stage"] = "telemetry-persist"
        result["reason"] = str(exc)
        result["partialInstallation"] = True
        return result, 2
    except _TelemetryPersistError as exc:
        result["status"] = "failed"
        result["stage"] = "telemetry-persist"
        result["reason"] = str(exc)
        result["partialInstallation"] = True
        return result, 1

    result["status"] = "installed"
    result["telemetry"] = telemetry
    result["partialInstallation"] = False
    result["after"] = _check_graft(env)
    result["reason"] = (
        f"pinned {GRAFT_SPEC} installed, verified runnable, and telemetry "
        "opt-out persisted"
    )
    return result, 0
