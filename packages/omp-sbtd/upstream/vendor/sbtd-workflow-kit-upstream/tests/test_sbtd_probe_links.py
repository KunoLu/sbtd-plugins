"""Regression tests for precise linked Skill target authorization (isolated probe).

Covers the two-phase flow: ``upgrade --phase authorize-link`` prepares a
content-bound authorization artifact from an explicit operator-supplied
physical target, and ``verify --probe --yes --link-authorization`` revalidates
and materializes the linked Skill as a plain fixture directory. Default
refusal without authorization, every mismatch class, race drift before and
during the copy, and immutability of old artifacts are exercised here.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "sbtd-workflow-onboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import sbtd_probe_links as probe_links
import sbtd_upgrade
import sbtd_upgrade_cli
import sbtd_upgrade_hosts as hosts
from onboard_contracts import ContractError, canonical_json_bytes
from sbtd_migration_files import (
    directory_snapshot,
    require_private_directory,
    save_document,
)

CLI = SCRIPTS / "onboard.py"
SCHEMA = json.loads(
    (ROOT / "sbtd-workflow-onboard" / "upgrade.schema.json").read_text(encoding="utf-8")
)

# Fixed protocol fixture, deliberately independent of implementation constants.
PINNED_TOOLS = [
    "graft_check_freshness", "graft_file_api", "graft_find_all",
    "graft_find_code", "graft_repo_map", "graft_trace_calls",
]
GRAFT_VERSION = "0.22.0"
HOST_ID = "codex-account"


def _digest(value) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _write_skill(root: Path, name: str, *, frontmatter_name: str | None = None) -> Path:
    skill = root / name
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {frontmatter_name or name}\ndescription: probe link test\n---\n",
        encoding="utf-8",
    )
    (skill / "reference.txt").write_text(f"{name} payload\n", encoding="utf-8")
    return skill


def _runtime(base: Path) -> dict[str, str]:
    directory = base / "runtime"
    directory.mkdir(exist_ok=True)
    paths: dict[str, str] = {}
    for key, filename in (("python", "python"), ("node", "node"), ("cli", "cli.js")):
        target = directory / filename
        target.write_bytes(b"")
        paths[key] = str(target)
    return paths


def _package(base: Path) -> Path:
    root = base / "package"
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SCRIPTS / "sbtd_graft_entry.py", root / "scripts" / "sbtd_graft_entry.py")
    return root


def _codex_host(base: Path, runtime: dict[str, str], root: Path, project: Path) -> dict:
    account = base / "account"
    return {
        "id": HOST_ID,
        "platform": "codex",
        "config_home": str(account / ".codex"),
        "config": str(account / ".codex" / "config.toml"),
        "runtime": dict(runtime),
        "skills_roots": [str(root)],
        "project_roots": [str(project)],
    }


def _omp_host(base: Path, runtime: dict[str, str], root: Path, project: Path) -> dict:
    account = base / "omp-account"
    return {
        "id": "omp-account",
        "platform": "omp",
        "config_home": str(account / ".omp"),
        "config": str(account / ".omp" / "agent" / "mcp.json"),
        "runtime": dict(runtime),
        "skills_roots": [str(root)],
        "project_roots": [str(project)],
    }


def _sealed_plan(vault: Path, scope: dict, resources: list[dict]) -> dict:
    payload = {
        "plan_schema": "upgrade-plan",
        "status": "planned",
        "baseline": {
            "baseline_id": "probe-link-baseline",
            "source": {
                "path": str(Path(scope["skills_roots"][0]).parent),
                "state": {"type": "directory", "checksum": "0" * 64},
            },
        },
        "scope": scope,
        "backup_root": str(vault),
        "resources": resources,
        "domains": [],
        "blocked_resources": [],
    }
    return {"schema_version": 1, "plan_id": _digest(payload), "payload": payload}


def _skill_resource(root: Path, name: str) -> dict:
    target = root / name
    state = sbtd_upgrade._payload_state(target)
    return {
        "id": f"skill:{name}",
        "kind": "skill",
        "target": str(target),
        "source": str(target),
        "before": state,
        "desired": state,
        "classification": "current",
        "decision": "keep",
        "details": {},
    }


def _prepare(plan_id: str, root: Path, link: Path, physical: Path, host_id: str = HOST_ID) -> dict:
    return probe_links.prepare_link_authorization(
        plan_id=plan_id,
        hosts=[{"id": host_id, "skills_roots": [str(root)]}],
        host_id=host_id,
        skill_path=str(link),
        target_path=str(physical),
    )


def _entry(document: dict) -> dict:
    return {
        "authorization_id": document["authorization_id"],
        "payload": document["payload"],
    }


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


# ---------------------------------------------------------------------------
# Scripted probe doubles (never a real spawn; evidence stays observable)
# ---------------------------------------------------------------------------


class _Stdin:
    def __init__(self, proc: "_Proc") -> None:
        self._proc = proc

    def write(self, data: bytes) -> int:
        for line in data.splitlines():
            if line.strip():
                self._proc._feed(json.loads(line))
        return len(data)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self._proc._close()


class _Stdout:
    def __init__(self, proc: "_Proc") -> None:
        self._proc = proc

    def readline(self) -> bytes:
        return self._proc._next_line()

    def close(self) -> None:
        return None


class _Proc:
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


class _Rig:
    """Monkeypatches the hosts module probe seams with scripted doubles."""

    def __init__(self, testcase: unittest.TestCase, expected_skills: list[str]) -> None:
        self.testcase = testcase
        self.expected_skills = list(expected_skills)
        self.extra_roots: list[str] = []
        self.spawns: list[list[str]] = []

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
                    "serverInfo": {"name": "graft", "version": GRAFT_VERSION},
                },
            }
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": [{"name": name} for name in PINNED_TOOLS]},
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
            return {"jsonrpc": "2.0", "id": request_id, "result": {"thread": {"id": "t-1"}}}
        if method == "config/mcpServer/reload":
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        if method == "mcpServerStatus/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "data": [
                        {
                            "name": "sbtd-graft",
                            "runtimeStatus": "connected",
                            "tools": {name: {} for name in PINNED_TOOLS},
                            "serverInfo": {"name": "graft", "version": GRAFT_VERSION},
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
                    "enabled": True,
                }
                for name in self.expected_skills
            ]
            entry = {"cwd": request["params"]["cwds"][0], "skills": skills, "errors": []}
            return {"jsonrpc": "2.0", "id": request_id, "result": {"data": [entry]}}
        return None

    def _omp_handler(self, request: dict):
        rtype = request.get("type")
        request_id = request.get("id")
        if request_id is None:
            return None
        envelope = {
            "id": request_id,
            "type": "response",
            "command": rtype,
            "success": True,
        }
        if rtype == "negotiate_protocol":
            return {**envelope, "data": {}}
        if rtype == "get_state":
            return {
                **envelope,
                "data": {
                    "systemPrompt": ["probe fixture prompt"],
                    "dumpTools": [
                        {
                            "name": f"mcp__sbtd_graft_{name}",
                            "description": f"pinned graft tool {name}",
                            "parameters": {"type": "object", "properties": {}},
                        }
                        for name in PINNED_TOOLS
                    ],
                },
            }
        if rtype == "get_available_commands":
            return {
                **envelope,
                "data": [{"name": f"skill:{name}"} for name in self.expected_skills],
            }
        return None

    def _spawn(self, argv, *, env, cwd):
        self.spawns.append(list(argv))
        if "app-server" in argv:
            return _Proc(self._codex_handler)
        if "--mode" in argv:
            return _Proc(self._omp_handler)
        return _Proc(self._mcp_handler)

    def install(self) -> "_Rig":
        self.testcase.addCleanup(self._restore)
        self._saved = (
            hosts._spawn,
            hosts._which,
            hosts.validate_project,
            hosts.validate_runtime,
            hosts._HOST_TIMEOUT,
        )
        hosts._spawn = self._spawn
        hosts._which = lambda name: f"/fake/bin/{name}"
        hosts.validate_project = lambda root: {"root": str(root)}
        hosts.validate_runtime = lambda node, cli: {"node": str(node), "cli": str(cli)}
        hosts._HOST_TIMEOUT = 3.0
        return self

    def _restore(self) -> None:
        (
            hosts._spawn,
            hosts._which,
            hosts.validate_project,
            hosts.validate_runtime,
            hosts._HOST_TIMEOUT,
        ) = self._saved

    def host_spawns(self) -> list[list[str]]:
        return [argv for argv in self.spawns if "app-server" in argv or "--mode" in argv]


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


class _LinksCase(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        # Owned fixture roots resolve the platform temp alias; operator inputs
        # under test are never resolved by the implementation.
        self.base = Path(temporary.name).resolve()

    def linked_fixture(self, *, link_text: str | None = None):
        """(skills_root, link, physical target, plain sibling)."""
        root = self.base / "account" / "skills"
        alpha = _write_skill(root, "alpha")
        physical = _write_skill(self.base / "physical", "linked-skill")
        link = root / "linked-skill"
        link.symlink_to(link_text or str(physical), target_is_directory=True)
        return root, link, physical, alpha

    def prepare(self, plan_id: str, root: Path, link: Path, physical: Path) -> dict:
        return _prepare(plan_id, root, link, physical)


# ---------------------------------------------------------------------------
# Phase 1: prepare
# ---------------------------------------------------------------------------


class PrepareAuthorizationTests(_LinksCase):
    def test_artifact_binds_plan_host_link_target_identity_and_content(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        original_text = os.readlink(link)
        plan_id = "a" * 64
        document = self.prepare(plan_id, root, link, physical)
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["authorization_id"], _digest(document["payload"]))
        payload = document["payload"]
        self.assertEqual(
            payload["authorization_schema"], "upgrade-probe-link-authorization"
        )
        self.assertEqual(payload["plan_id"], plan_id)
        self.assertEqual(payload["host_id"], HOST_ID)
        self.assertEqual(payload["skill_name"], "linked-skill")
        self.assertEqual(payload["skill_path"], str(link))
        link_info = os.lstat(link)
        self.assertEqual(
            payload["link"],
            {
                "text": original_text,
                "device": link_info.st_dev,
                "inode": link_info.st_ino,
                "ctime_ns": link_info.st_ctime_ns,
            },
        )
        target_info = os.lstat(physical)
        self.assertEqual(
            payload["target"],
            {
                "path": str(physical),
                "device": target_info.st_dev,
                "inode": target_info.st_ino,
                "ctime_ns": target_info.st_ctime_ns,
            },
        )
        state, _entries = directory_snapshot(physical)
        self.assertEqual(payload["state"], state)
        # The original link and target stay untouched, and the artifact is schema-valid.
        self.assertTrue(link.is_symlink())
        import jsonschema

        jsonschema.validate(document, SCHEMA)

    def test_relative_parent_link_supported_when_ancestors_physical(self) -> None:
        root = self.base / "account" / "skills"
        _write_skill(root, "alpha")
        physical = _write_skill(self.base / "physical", "linked-skill")
        link = root / "linked-skill"
        link.symlink_to(os.path.join("..", "..", "physical", "linked-skill"),
                        target_is_directory=True)
        document = self.prepare("b" * 64, root, link, physical)
        self.assertEqual(
            document["payload"]["link"]["text"],
            os.path.join("..", "..", "physical", "linked-skill"),
        )
        self.assertEqual(document["payload"]["target"]["path"], str(physical))

    def test_relative_link_through_linked_ancestor_is_refused(self) -> None:
        root = self.base / "account" / "skills"
        _write_skill(root, "alpha")
        real = _write_skill(self.base / "real", "linked-skill")
        # An intermediate component of the link text path is itself a link.
        alias = self.base / "alias"
        alias.symlink_to(self.base / "real", target_is_directory=True)
        link = root / "linked-skill"
        link.symlink_to(os.path.join("..", "..", "alias", "..", "real", "linked-skill"),
                        target_is_directory=True)
        with self.assertRaises(ContractError) as caught:
            self.prepare("b" * 64, root, link, real)
        self.assertEqual(caught.exception.code, "unsafe-path")

    def test_absolute_link_with_parent_traversal_supported(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        intermediate = physical.parent / "intermediate"
        intermediate.mkdir()
        link.unlink()
        link.symlink_to(str(intermediate / ".." / physical.name), target_is_directory=True)
        original_text = os.readlink(link)
        document = self.prepare("b" * 64, root, link, physical)
        self.assertEqual(document["payload"]["link"]["text"], original_text)

    def test_windows_substitution_spelling_does_not_expand_device_authority(self) -> None:
        with mock.patch.object(probe_links.os, "name", "nt"):
            self.assertEqual(
                probe_links._target_comparison_key(r"\\?\C:\skills\example"),
                probe_links._target_comparison_key(r"C:\skills\example"),
            )
            self.assertEqual(
                probe_links._target_comparison_key(r"\\?\UNC\server\share\example"),
                probe_links._target_comparison_key(r"\\server\share\example"),
            )
            for unsafe in (
                r"\\?\GLOBALROOT\Device\HarddiskVolume1\example",
                r"\\.\C:\skills\example",
                "\\\\?\\C:\\skills\\example ",
                r"\\?\C:\skills\example.",
            ):
                with self.subTest(path=unsafe), self.assertRaises(ContractError):
                    probe_links._target_comparison_key(unsafe)

    def test_identity_removed_between_validation_and_snapshot_is_refused(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        original = probe_links._skill_identity

        def remove_after_identity(target, name):
            result = original(target, name)
            (target / "SKILL.md").unlink()
            return result

        with mock.patch.object(probe_links, "_skill_identity", side_effect=remove_after_identity):
            with self.assertRaises(ContractError):
                self.prepare("b" * 64, root, link, physical)

    def test_mismatched_target_is_refused_before_its_metadata_is_accessed(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        approved = _write_skill(self.base / "approved", "linked-skill")
        original = probe_links._lstat

        def guarded_metadata(path):
            if Path(path).is_relative_to(physical.parent):
                self.fail("unapproved target metadata was accessed")
            return original(path)

        with mock.patch.object(probe_links, "_lstat", side_effect=guarded_metadata):
            with self.assertRaises(ContractError) as caught:
                self.prepare("c" * 64, root, link, approved)
        self.assertEqual(caught.exception.code, "target-mismatch")

    def test_target_mismatch_refused_before_any_content_read(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        other = _write_skill(self.base / "other", "linked-skill")
        with self.assertRaises(ContractError) as caught:
            self.prepare("c" * 64, root, link, other)
        self.assertEqual(caught.exception.code, "target-mismatch")

    def test_supplied_path_crossing_a_link_is_refused(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        alias = self.base / "physical-alias"
        alias.symlink_to(self.base / "physical", target_is_directory=True)
        with self.assertRaises(ContractError) as caught:
            self.prepare("c" * 64, root, link, alias / "linked-skill")
        self.assertEqual(caught.exception.code, "unsafe-path")

    def test_unknown_host_is_refused(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        with self.assertRaises(ContractError) as caught:
            probe_links.prepare_link_authorization(
                plan_id="c" * 64,
                hosts=[{"id": HOST_ID, "skills_roots": [str(root)]}],
                host_id="other-host", skill_path=str(link), target_path=str(physical),
            )
        self.assertEqual(caught.exception.code, "authorization-mismatch")

    def test_skill_outside_bound_roots_is_refused(self) -> None:
        _root, link, physical, _alpha = self.linked_fixture()
        other_root = self.base / "unselected" / "skills"
        other_root.mkdir(parents=True)
        with self.assertRaises(ContractError) as caught:
            _prepare("c" * 64, other_root, link, physical)
        self.assertEqual(caught.exception.code, "scope-violation")

    def test_plain_directory_needs_no_authorization(self) -> None:
        root = self.base / "account" / "skills"
        plain = _write_skill(root, "alpha")
        with self.assertRaises(ContractError) as caught:
            self.prepare("c" * 64, root, plain, plain)
        self.assertEqual(caught.exception.code, "invalid-argument")

    def test_missing_link_is_refused(self) -> None:
        root = self.base / "account" / "skills"
        root.mkdir(parents=True)
        with self.assertRaises(ContractError) as caught:
            self.prepare("c" * 64, root, root / "ghost", self.base / "physical")
        self.assertEqual(caught.exception.code, "invalid-argument")

    def test_file_target_is_refused(self) -> None:
        root = self.base / "account" / "skills"
        root.mkdir(parents=True)
        target = self.base / "physical-file"
        target.write_text("not a directory\n", encoding="utf-8")
        link = root / "linked-skill"
        link.symlink_to(str(target), target_is_directory=True)
        with self.assertRaises(ContractError) as caught:
            self.prepare("c" * 64, root, link, target)
        self.assertEqual(caught.exception.code, "unsafe-path")

    def test_nested_link_target_is_refused(self) -> None:
        root = self.base / "account" / "skills"
        root.mkdir(parents=True)
        physical = _write_skill(self.base / "physical", "linked-skill")
        intermediate = self.base / "intermediate"
        intermediate.symlink_to(physical, target_is_directory=True)
        link = root / "linked-skill"
        link.symlink_to(intermediate, target_is_directory=True)
        original_text = os.readlink(link)
        for supplied in (physical, intermediate):
            with self.subTest(supplied=supplied), self.assertRaises(ContractError):
                self.prepare("c" * 64, root, link, supplied)
        self.assertEqual(os.readlink(link), original_text)

    def test_target_with_nested_link_inside_is_refused(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        (physical / "nested").symlink_to(self.base / "account", target_is_directory=True)
        with self.assertRaises(ContractError) as caught:
            self.prepare("c" * 64, root, link, physical)
        self.assertEqual(caught.exception.code, "unsafe-path")

    @unittest.skipIf(os.name == "nt", "POSIX fifo scenario")
    def test_target_with_special_file_inside_is_refused(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        os.mkfifo(physical / "fifo")
        with self.assertRaises(ContractError) as caught:
            self.prepare("c" * 64, root, link, physical)
        self.assertEqual(caught.exception.code, "unsafe-path")

    def test_wrong_skill_identity_is_rejected(self) -> None:
        root = self.base / "account" / "skills"
        root.mkdir(parents=True)
        physical = _write_skill(self.base / "physical", "linked-skill",
                                frontmatter_name="different-skill")
        link = root / "linked-skill"
        link.symlink_to(str(physical), target_is_directory=True)
        with self.assertRaises(ContractError) as caught:
            self.prepare("c" * 64, root, link, physical)
        self.assertEqual(caught.exception.code, "skill-identity-mismatch")

    def test_missing_skill_identity_is_rejected(self) -> None:
        root = self.base / "account" / "skills"
        root.mkdir(parents=True)
        physical = self.base / "physical" / "linked-skill"
        physical.mkdir(parents=True)
        (physical / "reference.txt").write_text("payload\n", encoding="utf-8")
        link = root / "linked-skill"
        link.symlink_to(str(physical), target_is_directory=True)
        with self.assertRaises(ContractError) as caught:
            self.prepare("c" * 64, root, link, physical)
        self.assertEqual(caught.exception.code, "skill-identity-unproven")

    def test_linked_skill_md_is_refused(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        (physical / "SKILL.md").unlink()
        (physical / "SKILL.md").symlink_to(self.base / "account" / "skills" / "alpha" / "SKILL.md")
        with self.assertRaises(ContractError) as caught:
            self.prepare("c" * 64, root, link, physical)
        self.assertEqual(caught.exception.code, "unsafe-path")

    def test_unprovable_identity_fails_closed(self) -> None:
        fake = types.SimpleNamespace(st_dev=0, st_ino=0)
        with self.assertRaises(ContractError) as caught:
            probe_links._object_identity(fake, "a probe object")
        self.assertEqual(caught.exception.code, "identity-unprovable")
        fake_non_int = types.SimpleNamespace(st_dev=1, st_ino=None)
        with self.assertRaises(ContractError) as caught:
            probe_links._object_identity(fake_non_int, "a probe object")
        self.assertEqual(caught.exception.code, "identity-unprovable")


# ---------------------------------------------------------------------------
# Document validation and binding
# ---------------------------------------------------------------------------


class ValidateAuthorizationTests(_LinksCase):
    def test_roundtrip_validation_returns_sealed_payload(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        document = self.prepare("d" * 64, root, link, physical)
        payload = probe_links.validate_link_authorization(
            document, plan_id="d" * 64,
            hosts=[{"id": HOST_ID, "skills_roots": [str(root)]}],
        )
        self.assertEqual(payload, document["payload"])
        self.assertIsNot(payload, document["payload"])

    def test_tampered_payload_breaks_digest_binding(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        document = self.prepare("d" * 64, root, link, physical)
        forged = json.loads(json.dumps(document))
        forged["payload"]["link"]["text"] = str(self.base / "elsewhere")
        with self.assertRaises(ContractError) as caught:
            probe_links.validate_link_authorization(
                forged, plan_id="d" * 64,
                hosts=[{"id": HOST_ID, "skills_roots": [str(root)]}],
            )
        self.assertEqual(caught.exception.code, "authorization-id-mismatch")

    def test_wrong_plan_binding_is_refused(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        document = self.prepare("d" * 64, root, link, physical)
        with self.assertRaises(ContractError) as caught:
            probe_links.validate_link_authorization(
                document, plan_id="e" * 64,
                hosts=[{"id": HOST_ID, "skills_roots": [str(root)]}],
            )
        self.assertEqual(caught.exception.code, "authorization-mismatch")

    def test_wrong_host_identity_is_refused(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        document = self.prepare("d" * 64, root, link, physical)
        with self.assertRaises(ContractError) as caught:
            probe_links.validate_link_authorization(
                document, plan_id="d" * 64,
                hosts=[{"id": "another-host", "skills_roots": [str(root)]}],
            )
        self.assertEqual(caught.exception.code, "authorization-mismatch")

    def test_path_outside_bound_roots_is_refused(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        document = self.prepare("d" * 64, root, link, physical)
        other_root = self.base / "other-root"
        other_root.mkdir()
        with self.assertRaises(ContractError) as caught:
            probe_links.validate_link_authorization(
                document, plan_id="d" * 64,
                hosts=[{"id": HOST_ID, "skills_roots": [str(other_root)]}],
            )
        self.assertEqual(caught.exception.code, "authorization-mismatch")

    def test_structural_rejections(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        document = self.prepare("d" * 64, root, link, physical)
        hosts_scope = [{"id": HOST_ID, "skills_roots": [str(root)]}]
        cases = []
        missing_key = json.loads(json.dumps(document))
        del missing_key["payload"]["link"]
        cases.append(missing_key)
        extra_key = json.loads(json.dumps(document))
        extra_key["payload"]["comment"] = "forgery"
        cases.append(extra_key)
        wrong_version = json.loads(json.dumps(document))
        wrong_version["schema_version"] = 2
        cases.append(wrong_version)
        wrong_schema = json.loads(json.dumps(document))
        wrong_schema["payload"]["authorization_schema"] = "upgrade-plan"
        cases.append(wrong_schema)
        unproven_inode = json.loads(json.dumps(document))
        unproven_inode["payload"]["target"]["inode"] = 0
        cases.append(unproven_inode)
        for index, case in enumerate(cases):
            with self.subTest(case=index):
                with self.assertRaises(ContractError) as caught:
                    probe_links.validate_link_authorization(
                        case, plan_id="d" * 64, hosts=hosts_scope
                    )
                self.assertEqual(caught.exception.code, "invalid-document")


# ---------------------------------------------------------------------------
# Phase 2: materialization (live revalidation + safe copy)
# ---------------------------------------------------------------------------


class MaterializeAuthorizationTests(_LinksCase):
    def _materialize(self, document: dict, destination: Path, private_root: Path):
        payload = probe_links.validate_link_authorization(
            document,
            plan_id=document["payload"]["plan_id"],
            hosts=[
                {
                    "id": HOST_ID,
                    "skills_roots": [document["payload"]["skill_path"].rsplit(os.sep, 1)[0]],
                }
            ],
        )
        return probe_links.materialize_authorized_skill(
            payload, destination=destination, private_root=private_root
        )

    def test_inconsistent_target_document_refuses_before_target_metadata_access(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        document = self.prepare("f" * 64, root, link, physical)
        approved = _write_skill(self.base / "approved", "linked-skill")
        document["payload"]["target"] = {
            "path": str(approved),
            **probe_links._object_identity(os.lstat(approved), "fixture target"),
        }
        document["payload"]["state"] = directory_snapshot(approved)[0]
        document["authorization_id"] = _digest(document["payload"])
        original = probe_links._lstat

        def guarded_metadata(path):
            if Path(path).is_relative_to(physical.parent):
                self.fail("unapproved target metadata was accessed")
            return original(path)

        private = require_private_directory(self.base / "fixture", create=True)
        with mock.patch.object(probe_links, "_lstat", side_effect=guarded_metadata):
            with self.assertRaises(ContractError) as caught:
                self._materialize(document, private / "linked-skill", private)
        self.assertEqual(caught.exception.code, "link-mismatch")
        self.assertFalse((private / "linked-skill").exists())

    def test_materializes_plain_directory_and_preserves_original(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        original_text = os.readlink(link)
        document = self.prepare("f" * 64, root, link, physical)
        private = require_private_directory(self.base / "fixture", create=True)
        result = self._materialize(document, private / "linked-skill", private)
        copied = private / "linked-skill"
        self.assertTrue(copied.is_dir())
        self.assertFalse(copied.is_symlink())
        self.assertEqual(_tree_bytes(copied), _tree_bytes(physical))
        self.assertEqual(result["state"], document["payload"]["state"])
        # The original link and target are never modified.
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), original_text)

    def test_content_drift_before_copy_is_refused(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        document = self.prepare("f" * 64, root, link, physical)
        (physical / "reference.txt").write_text("drifted\n", encoding="utf-8")
        private = require_private_directory(self.base / "fixture", create=True)
        with self.assertRaises(ContractError) as caught:
            self._materialize(document, private / "linked-skill", private)
        self.assertEqual(caught.exception.code, "state-conflict")
        self.assertFalse((private / "linked-skill").exists())

    def test_link_text_change_is_refused(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        document = self.prepare("f" * 64, root, link, physical)
        other = _write_skill(self.base / "other", "linked-skill")
        link.unlink()
        link.symlink_to(str(other), target_is_directory=True)
        private = require_private_directory(self.base / "fixture", create=True)
        # The link object itself was also replaced; identity rejection wins.
        with self.assertRaises(ContractError) as caught:
            self._materialize(document, private / "linked-skill", private)
        self.assertEqual(caught.exception.code, "identity-mismatch")
        self.assertFalse((private / "linked-skill").exists())

    def test_replaced_link_with_identical_text_is_refused(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        document = self.prepare("f" * 64, root, link, physical)
        text = os.readlink(link)
        link.unlink()
        link.symlink_to(text, target_is_directory=True)
        self.assertEqual(os.readlink(link), text)
        private = require_private_directory(self.base / "fixture", create=True)
        with self.assertRaises(ContractError) as caught:
            self._materialize(document, private / "linked-skill", private)
        self.assertEqual(caught.exception.code, "identity-mismatch")

    def test_same_inode_with_new_ctime_is_not_the_authorized_object(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        document = self.prepare("f" * 64, root, link, physical)
        original = probe_links._lstat
        observed = os.lstat(link)
        recycled = types.SimpleNamespace(
            st_mode=observed.st_mode, st_dev=observed.st_dev,
            st_ino=observed.st_ino, st_ctime_ns=observed.st_ctime_ns + 1,
        )

        def recycled_identity(path):
            return recycled if Path(path) == link else original(path)

        private = require_private_directory(self.base / "fixture", create=True)
        with mock.patch.object(probe_links, "_lstat", side_effect=recycled_identity):
            with self.assertRaises(ContractError) as caught:
                self._materialize(document, private / "linked-skill", private)
        self.assertEqual(caught.exception.code, "identity-mismatch")
        self.assertFalse((private / "linked-skill").exists())

    def test_replaced_target_with_identical_bytes_is_refused(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        document = self.prepare("f" * 64, root, link, physical)
        content = _tree_bytes(physical)
        replacement = self.base / "replacement"
        replacement.mkdir()
        for relative, data in content.items():
            target = replacement / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        # The original link object stays; only the target directory is swapped
        # for a byte-identical replacement (same absolute link text).
        physical.rename(self.base / "retired")
        replacement.rename(physical)
        state, _entries = directory_snapshot(physical)
        self.assertEqual(state, document["payload"]["state"])
        private = require_private_directory(self.base / "fixture", create=True)
        with self.assertRaises(ContractError) as caught:
            self._materialize(document, private / "linked-skill", private)
        self.assertEqual(caught.exception.code, "identity-mismatch")
        self.assertFalse((private / "linked-skill").exists())

    def test_target_ancestor_swapped_for_link_is_refused(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        document = self.prepare("f" * 64, root, link, physical)
        (self.base / "physical").rename(self.base / "physical-original")
        (self.base / "physical").symlink_to(self.base / "physical-original",
                                           target_is_directory=True)
        private = require_private_directory(self.base / "fixture", create=True)
        with self.assertRaises(ContractError) as caught:
            self._materialize(document, private / "linked-skill", private)
        self.assertEqual(caught.exception.code, "unsafe-path")

    def test_content_drift_during_copy_is_refused_after_copy(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        document = self.prepare("f" * 64, root, link, physical)
        before = _tree_bytes(physical)
        private = require_private_directory(self.base / "fixture", create=True)
        real_copy = probe_links.backup_reference

        def poisoned_copy(*args, **kwargs):
            result = real_copy(*args, **kwargs)
            # Attacker writes into the target after its bytes were copied.
            (physical / "injected.txt").write_text("drift during copy\n",
                                                   encoding="utf-8")
            return result

        with mock.patch.object(probe_links, "backup_reference", poisoned_copy):
            with self.assertRaises(ContractError):
                self._materialize(document, private / "linked-skill", private)
        # The materialized copy holds exactly the authorized bytes, never the drift.
        self.assertEqual(_tree_bytes(private / "linked-skill"), before)

    def test_link_swap_during_copy_is_refused_after_copy(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        document = self.prepare("f" * 64, root, link, physical)
        private = require_private_directory(self.base / "fixture", create=True)
        real_copy = probe_links.backup_reference
        text = os.readlink(link)

        def poisoned_copy(*args, **kwargs):
            result = real_copy(*args, **kwargs)
            # Attacker replaces the link object mid-copy, keeping its text.
            link.unlink()
            link.symlink_to(text, target_is_directory=True)
            return result

        with mock.patch.object(probe_links, "backup_reference", poisoned_copy):
            with self.assertRaises(ContractError) as caught:
                self._materialize(document, private / "linked-skill", private)
        self.assertEqual(caught.exception.code, "identity-mismatch")


# ---------------------------------------------------------------------------
# Probe fixture copy integration (hosts._copy_skill_roots)
# ---------------------------------------------------------------------------


class CopySkillRootsAuthorizationTests(_LinksCase):
    def _destinations(self) -> Path:
        parent = self.base / "fixture"
        parent.mkdir(exist_ok=True)
        return parent / "roots"

    def _sealed_entries(self, *documents: dict) -> list[dict]:
        entries = []
        for document in documents:
            payload = probe_links.validate_link_authorization(
                document,
                plan_id=document["payload"]["plan_id"],
                hosts=[
                    {
                        "id": HOST_ID,
                        "skills_roots": [
                            document["payload"]["skill_path"].rsplit(os.sep, 1)[0]
                        ],
                    }
                ],
            )
            entries.append({"authorization_id": document["authorization_id"],
                            "payload": payload})
        return entries

    def test_default_refusal_without_authorization_never_reads_target(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        if os.name != "nt":
            # An unreadable target proves the refusal happens before any access.
            physical.chmod(0o000)
            self.addCleanup(physical.chmod, 0o700)
        destinations = self._destinations()
        with self.assertRaises(ContractError) as caught:
            hosts._copy_skill_roots([str(root)], destinations)
        self.assertEqual(caught.exception.code, "unsafe-path")
        self.assertFalse((destinations / "0").exists())
        self.assertTrue(link.is_symlink())

    def test_authorized_link_materializes_plain_directory(self) -> None:
        root, link, physical, alpha = self.linked_fixture()
        document = self.prepare("0" * 64, root, link, physical)
        outcomes: list[dict] = []
        copies = hosts._copy_skill_roots(
            [str(root)],
            self._destinations(),
            link_authorizations=self._sealed_entries(document),
            outcomes=outcomes,
        )
        copied = Path(copies[0])
        materialized = copied / "linked-skill"
        self.assertTrue(materialized.is_dir())
        self.assertFalse(materialized.is_symlink())
        self.assertEqual(_tree_bytes(materialized), _tree_bytes(physical))
        self.assertEqual(_tree_bytes(copied / "alpha"), _tree_bytes(alpha))
        # No expected-skill reduction: the materialized Skill keeps its name.
        self.assertEqual(
            hosts._expected_skill_names(copies), ["alpha", "linked-skill"]
        )
        self.assertEqual(len(outcomes), 1)
        outcome = outcomes[0]
        self.assertEqual(outcome["authorization_id"], document["authorization_id"])
        self.assertEqual(outcome["status"], "materialized")
        self.assertEqual(outcome["skill_name"], "linked-skill")
        self.assertEqual(outcome["target"], document["payload"]["target"])
        self.assertEqual(
            outcome["state_checksum"], document["payload"]["state"]["checksum"]
        )
        self.assertTrue(link.is_symlink())

    def test_partial_authorization_coverage_is_refused(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        other = _write_skill(self.base / "other", "other-skill")
        second = root / "other-skill"
        second.symlink_to(str(other), target_is_directory=True)
        document = self.prepare("0" * 64, root, link, physical)
        with self.assertRaises(ContractError) as caught:
            hosts._copy_skill_roots(
                [str(root)],
                self._destinations(),
                link_authorizations=self._sealed_entries(document),
            )
        self.assertEqual(caught.exception.code, "unsafe-path")
        self.assertFalse((self._destinations() / "0").exists())

    def test_authorization_for_another_skill_does_not_cover(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        other_root = self.base / "second" / "skills"
        other_link_target = _write_skill(self.base / "other", "other-skill")
        other_root.mkdir(parents=True)
        other_link = other_root / "other-skill"
        other_link.symlink_to(str(other_link_target), target_is_directory=True)
        document = probe_links.prepare_link_authorization(
            plan_id="0" * 64,
            hosts=[{"id": HOST_ID, "skills_roots": [str(other_root)]}],
            host_id=HOST_ID,
            skill_path=str(other_link),
            target_path=str(other_link_target),
        )
        with self.assertRaises(ContractError) as caught:
            hosts._copy_skill_roots(
                [str(root)],
                self._destinations(),
                link_authorizations=self._sealed_entries(document),
            )
        self.assertEqual(caught.exception.code, "unsafe-path")

    def test_duplicate_authorizations_are_refused(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        document = self.prepare("0" * 64, root, link, physical)
        entries = self._sealed_entries(document, document)
        with self.assertRaises(ContractError) as caught:
            hosts._copy_skill_roots(
                [str(root)],
                self._destinations(),
                link_authorizations=entries,
            )
        self.assertEqual(caught.exception.code, "authorization-conflict")

    def test_root_child_added_during_copy_is_refused(self) -> None:
        root, link, physical, _alpha = self.linked_fixture()
        document = self.prepare("0" * 64, root, link, physical)
        real_copy = hosts.backup_reference
        injected = {"done": False}

        def poisoned_copy(*args, **kwargs):
            result = real_copy(*args, **kwargs)
            if not injected["done"]:
                injected["done"] = True
                _write_skill(root, "late-arrival")
            return result

        with mock.patch.object(hosts, "backup_reference", poisoned_copy):
            with self.assertRaises(ContractError) as caught:
                hosts._copy_skill_roots(
                    [str(root)],
                    self._destinations(),
                    link_authorizations=self._sealed_entries(document),
                )
        self.assertEqual(caught.exception.code, "state-conflict")

    def test_plain_child_drift_after_copy_is_refused(self) -> None:
        root, link, physical, alpha = self.linked_fixture()
        document = self.prepare("0" * 64, root, link, physical)
        real_copy = hosts.backup_reference

        def poisoned_copy(*args, **kwargs):
            result = real_copy(*args, **kwargs)
            (alpha / "reference.txt").write_text("drifted after copy\n",
                                                 encoding="utf-8")
            return result

        with mock.patch.object(hosts, "backup_reference", poisoned_copy):
            with self.assertRaises(ContractError) as caught:
                hosts._copy_skill_roots(
                    [str(root)],
                    self._destinations(),
                    link_authorizations=self._sealed_entries(document),
                )
        self.assertEqual(caught.exception.code, "state-conflict")

    def test_root_itself_a_link_keeps_default_refusal(self) -> None:
        _root, _link, physical, _alpha = self.linked_fixture()
        alias = self.base / "aliased-root"
        alias.symlink_to(self.base / "account" / "skills", target_is_directory=True)
        document = self.prepare("0" * 64, self.base / "account" / "skills",
                                self.base / "account" / "skills" / "linked-skill",
                                physical)
        with self.assertRaises(ContractError) as caught:
            hosts._copy_skill_roots(
                [str(alias)],
                self._destinations(),
                link_authorizations=self._sealed_entries(document),
            )
        self.assertEqual(caught.exception.code, "unsafe-path")


# ---------------------------------------------------------------------------
# verify_hosts probe integration with scripted host doubles
# ---------------------------------------------------------------------------


class VerifyHostsProbeLinkTests(_LinksCase):
    def _aligned_scope(self, platform: str = "codex"):
        runtime, package = _runtime(self.base), _package(self.base)
        root, link, physical, _alpha = self.linked_fixture()
        # The installed Onboard copy used for launcher bindings.
        onboard = root / "sbtd-workflow-onboard" / "scripts"
        onboard.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SCRIPTS / "sbtd_graft_entry.py", onboard / "sbtd_graft_entry.py")
        project = self.base / "project"
        project.mkdir()
        if platform == "codex":
            host = _codex_host(self.base, runtime, root, project)
        else:
            host = _omp_host(self.base, runtime, root, project)
        scope = {"hosts": [host], "skills_roots": [str(root)]}
        resource = hosts.build_host_resources(scope, package_root=package)[0]
        config = Path(host["config"])
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_bytes(hosts.render_resource(resource))
        return scope, package, root, link, physical, host

    def test_authorized_probe_passes_with_full_link_evidence(self) -> None:
        scope, package, root, link, physical, host = self._aligned_scope()
        document = self.prepare("1" * 64, root, link, physical)
        rig = _Rig(self, ["alpha", "linked-skill"]).install()
        result = hosts.verify_hosts(
            scope,
            package_root=package,
            probe=True,
            link_authorizations=[
                {
                    "authorization_id": document["authorization_id"],
                    "payload": probe_links.validate_link_authorization(
                        document, plan_id="1" * 64,
                        hosts=[{"id": HOST_ID, "skills_roots": [str(root)]}],
                    ),
                }
            ],
        )
        entry = result["hosts"][0]
        self.assertEqual(entry["status"], "pass", entry)
        skills = entry["host"]["checks"]["skills"]
        self.assertEqual(skills["status"], "verified", skills)
        self.assertEqual(skills["skills"], ["alpha", "linked-skill"])
        evidence = skills["link_authorizations"]
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["authorization_id"], document["authorization_id"])
        self.assertEqual(evidence[0]["status"], "materialized")
        self.assertEqual(evidence[0]["target"]["path"], str(physical))
        self.assertEqual(
            evidence[0]["state_checksum"], document["payload"]["state"]["checksum"]
        )
        self.assertTrue(rig.host_spawns(), "the isolated host probe never ran")
        self.assertTrue(link.is_symlink())

    def test_authorized_probe_passes_for_omp_host(self) -> None:
        scope, package, root, link, physical, host = self._aligned_scope("omp")
        document = probe_links.prepare_link_authorization(
            plan_id="1" * 64,
            hosts=[{"id": "omp-account", "skills_roots": [str(root)]}],
            host_id="omp-account",
            skill_path=str(link),
            target_path=str(physical),
        )
        rig = _Rig(self, ["alpha", "linked-skill"]).install()
        result = hosts.verify_hosts(
            scope,
            package_root=package,
            probe=True,
            link_authorizations=[
                {
                    "authorization_id": document["authorization_id"],
                    "payload": probe_links.validate_link_authorization(
                        document, plan_id="1" * 64,
                        hosts=[{"id": "omp-account", "skills_roots": [str(root)]}],
                    ),
                }
            ],
        )
        entry = result["hosts"][0]
        self.assertEqual(entry["status"], "pass", entry)
        skills = entry["host"]["checks"]["skills"]
        self.assertEqual(skills["status"], "verified", skills)
        self.assertEqual(skills["link_authorizations"][0]["status"], "materialized")

    def test_unauthorized_link_fails_before_any_host_spawn(self) -> None:
        scope, package, root, link, physical, _host = self._aligned_scope()
        rig = _Rig(self, ["alpha", "linked-skill"]).install()
        result = hosts.verify_hosts(scope, package_root=package, probe=True)
        entry = result["hosts"][0]
        self.assertEqual(entry["status"], "fail", entry)
        load = entry["host"]["checks"]["host_load"]
        self.assertEqual(load["status"], "failed")
        self.assertEqual(load["reason"], "unsafe-path")
        # The refused copy never lets the host process start.
        self.assertEqual(rig.host_spawns(), [])
        self.assertTrue(link.is_symlink())

    def test_authorization_bound_to_another_host_is_not_applied(self) -> None:
        scope, package, root, link, physical, _host = self._aligned_scope()
        document = _prepare("1" * 64, root, link, physical, host_id="other-host")
        rig = _Rig(self, ["alpha", "linked-skill"]).install()
        result = hosts.verify_hosts(
            scope,
            package_root=package,
            probe=True,
            link_authorizations=[
                {
                    "authorization_id": document["authorization_id"],
                    "payload": probe_links.validate_link_authorization(
                        document, plan_id="1" * 64,
                        hosts=[{"id": "other-host", "skills_roots": [str(root)]}],
                    ),
                }
            ],
        )
        load = result["hosts"][0]["host"]["checks"]["host_load"]
        self.assertEqual(load["status"], "failed")
        self.assertEqual(load["reason"], "unsafe-path")
        self.assertEqual(rig.host_spawns(), [])

    def test_replaced_link_with_plain_directory_invalidates_authorization(self) -> None:
        scope, package, root, link, physical, _host = self._aligned_scope()
        document = self.prepare("1" * 64, root, link, physical)
        # Operator replaced the link with a real directory after preparing.
        link.unlink()
        replacement = root / "linked-skill"
        replacement.mkdir()
        for relative, data in _tree_bytes(physical).items():
            target = replacement / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        rig = _Rig(self, ["alpha", "linked-skill"]).install()
        result = hosts.verify_hosts(
            scope,
            package_root=package,
            probe=True,
            link_authorizations=[
                {
                    "authorization_id": document["authorization_id"],
                    "payload": probe_links.validate_link_authorization(
                        document, plan_id="1" * 64,
                        hosts=[{"id": HOST_ID, "skills_roots": [str(root)]}],
                    ),
                }
            ],
        )
        load = result["hosts"][0]["host"]["checks"]["host_load"]
        self.assertEqual(load["status"], "failed", load)
        self.assertEqual(load["reason"], "link-mismatch")
        self.assertEqual(rig.host_spawns(), [])


# ---------------------------------------------------------------------------
# Engine integration (sbtd_upgrade)
# ---------------------------------------------------------------------------


class UpgradeEngineLinkTests(_LinksCase):
    def _engine_fixture(self):
        runtime, package = _runtime(self.base), _package(self.base)
        root, link, physical, alpha = self.linked_fixture()
        onboard = root / "sbtd-workflow-onboard" / "scripts"
        onboard.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SCRIPTS / "sbtd_graft_entry.py", onboard / "sbtd_graft_entry.py")
        project = self.base / "project"
        project.mkdir()
        host = _codex_host(self.base, runtime, root, project)
        scope = {
            "schema_version": 1,
            "skills_roots": [str(root)],
            "hosts": [host],
            "decisions": {},
        }
        vault = require_private_directory(self.base / "vault", create=True)
        plan = _sealed_plan(vault, scope, [_skill_resource(root, "alpha")])
        return plan, vault, scope, package, root, link, physical, host

    def test_prepare_via_engine_binds_the_sealed_plan(self) -> None:
        plan, _vault, _scope, _package_root, root, link, physical, _host = (
            self._engine_fixture()
        )
        document = sbtd_upgrade.prepare_probe_link_authorization(
            plan, host_id=HOST_ID, skill_path=str(link), target_path=str(physical)
        )
        self.assertEqual(document["payload"]["plan_id"], plan["plan_id"])
        self.assertEqual(document["payload"]["host_id"], HOST_ID)
        import jsonschema

        jsonschema.validate(document, SCHEMA)

    def test_prepare_via_engine_rejects_foreign_host(self) -> None:
        plan, _vault, _scope, _package_root, root, link, physical, _host = (
            self._engine_fixture()
        )
        with self.assertRaises(ContractError) as caught:
            sbtd_upgrade.prepare_probe_link_authorization(
                plan, host_id="stranger", skill_path=str(link), target_path=str(physical)
            )
        self.assertEqual(caught.exception.code, "authorization-mismatch")

    def test_verify_rejects_authorizations_without_probe(self) -> None:
        plan, vault, _scope, _package_root, root, link, physical, _host = (
            self._engine_fixture()
        )
        save_document(
            vault / f"upgrade-plan-{plan['plan_id']}.json", plan, private_root=vault
        )
        document = sbtd_upgrade.prepare_probe_link_authorization(
            plan, host_id=HOST_ID, skill_path=str(link), target_path=str(physical)
        )
        with self.assertRaises(ContractError) as caught:
            sbtd_upgrade.verify_upgrade(plan, probe=False, link_authorizations=[document])
        self.assertEqual(caught.exception.code, "invalid-argument")

    def test_verify_rejects_authorization_of_another_plan(self) -> None:
        plan, vault, _scope, _package_root, root, link, physical, _host = (
            self._engine_fixture()
        )
        save_document(
            vault / f"upgrade-plan-{plan['plan_id']}.json", plan, private_root=vault
        )
        foreign = _prepare("9" * 64, root, link, physical)
        with self.assertRaises(ContractError) as caught:
            sbtd_upgrade.verify_upgrade(plan, probe=True, link_authorizations=[foreign])
        self.assertEqual(caught.exception.code, "authorization-mismatch")

    def test_two_hosts_can_authorize_one_shared_link_without_cross_host_reuse(self) -> None:
        original, vault, scope, _package_root, root, link, physical, host = self._engine_fixture()
        shutil.copytree(
            SCRIPTS.parent, root / "sbtd-workflow-onboard", dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        second_home = self.base / "second-account" / ".codex"
        second_host = {
            **host, "id": "second-codex",
            "config_home": str(second_home), "config": str(second_home / "config.toml"),
        }
        scope = {**scope, "hosts": [host, second_host]}
        plan = _sealed_plan(vault, scope, original["payload"]["resources"])
        save_document(vault / f"upgrade-plan-{plan['plan_id']}.json", plan, private_root=vault)
        documents = [
            sbtd_upgrade.prepare_probe_link_authorization(
                plan, host_id=selected["id"], skill_path=str(link), target_path=str(physical)
            )
            for selected in scope["hosts"]
        ]
        for resource in hosts.build_host_resources(scope, package_root=SCRIPTS.parent):
            config = Path(resource["target"])
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_bytes(hosts.render_resource(resource))
        rig = _Rig(self, ["alpha", "linked-skill", "sbtd-workflow-onboard"]).install()
        result = sbtd_upgrade.verify_upgrade(plan, probe=True, link_authorizations=documents)
        self.assertEqual(result["status"], "aligned", result)
        self.assertEqual(len(rig.host_spawns()), 2)
        for report in result["payload"]["hosts"]["hosts"]:
            evidence = report["host"]["checks"]["skills"]["link_authorizations"]
            self.assertEqual([row["host_id"] for row in evidence], [report["id"]])

    def test_verify_rejects_duplicate_authorizations(self) -> None:
        plan, vault, _scope, _package_root, root, link, physical, _host = (
            self._engine_fixture()
        )
        save_document(
            vault / f"upgrade-plan-{plan['plan_id']}.json", plan, private_root=vault
        )
        document = sbtd_upgrade.prepare_probe_link_authorization(
            plan, host_id=HOST_ID, skill_path=str(link), target_path=str(physical)
        )
        with self.assertRaises(ContractError) as caught:
            sbtd_upgrade.verify_upgrade(
                plan, probe=True, link_authorizations=[document, document]
            )
        self.assertEqual(caught.exception.code, "authorization-conflict")

    def test_verify_probe_with_authorization_aligned_and_old_artifacts_untouched(
        self,
    ) -> None:
        plan, vault, scope, package, root, link, physical, host = self._engine_fixture()
        # Public verify derives its expected installed payload from the running
        # package; a launcher-only placeholder cannot satisfy that boundary.
        shutil.copytree(
            SCRIPTS.parent, root / "sbtd-workflow-onboard", dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        plan_path = vault / f"upgrade-plan-{plan['plan_id']}.json"
        save_document(plan_path, plan, private_root=vault)
        # Pre-existing evidence in the vault must survive verification untouched.
        legacy_receipt = vault / ("upgrade-receipt-" + "7" * 64 + ".json")
        legacy_receipt.write_text('{"historical": true}\n', encoding="utf-8")
        plan_bytes = plan_path.read_bytes()
        receipt_bytes = legacy_receipt.read_bytes()
        document = sbtd_upgrade.prepare_probe_link_authorization(
            plan, host_id=HOST_ID, skill_path=str(link), target_path=str(physical)
        )
        resource = hosts.build_host_resources(scope, package_root=SCRIPTS.parent)[0]
        config = Path(host["config"])
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_bytes(hosts.render_resource(resource))
        rig = _Rig(self, ["alpha", "linked-skill", "sbtd-workflow-onboard"]).install()
        result = sbtd_upgrade.verify_upgrade(
            plan, probe=True, link_authorizations=[document]
        )
        self.assertEqual(result["status"], "aligned", result["payload"]["hosts"])
        skills = result["payload"]["hosts"]["hosts"][0]["host"]["checks"]["skills"]
        self.assertEqual(skills["status"], "verified", skills)
        evidence = skills["link_authorizations"]
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["authorization_id"], document["authorization_id"])
        self.assertEqual(evidence[0]["status"], "materialized")
        self.assertEqual(evidence[0]["target"], document["payload"]["target"])
        self.assertTrue(rig.host_spawns())
        self.assertEqual(plan_path.read_bytes(), plan_bytes)
        self.assertEqual(legacy_receipt.read_bytes(), receipt_bytes)
        self.assertTrue(link.is_symlink())
        import jsonschema

        jsonschema.validate(result, SCHEMA)


# ---------------------------------------------------------------------------
# CLI integration (parsing + handler envelopes)
# ---------------------------------------------------------------------------


class UpgradeCliLinkTests(_LinksCase):
    def test_authorize_link_requires_its_explicit_inputs(self) -> None:
        commands = [
            ["upgrade", "--phase", "authorize-link", "--plan", "/plan"],
            ["upgrade", "--phase", "authorize-link", "--plan", "/plan",
             "--host", "h", "--skill-path", "/s", "--target-path", "/t", "--yes"],
            ["upgrade", "--phase", "verify", "--plan", "/plan",
             "--link-authorization", "/a.json"],
            ["upgrade", "--phase", "plan", "--scope", "/s", "--backup-root", "/b",
             "--link-authorization", "/a.json"],
            ["upgrade", "--phase", "apply", "--plan", "/p", "--host", "h"],
        ]
        for command in commands:
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, "-B", str(CLI), *command],
                    capture_output=True, text=True, timeout=30, check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("invalid arguments", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def _cli_fixture(self):
        root, link, physical, _alpha = self.linked_fixture()
        scope = {
            "schema_version": 1,
            "skills_roots": [str(root)],
            "hosts": [{"id": HOST_ID, "skills_roots": [str(root)]}],
            "decisions": {},
        }
        vault = require_private_directory(self.base / "vault", create=True)
        plan = _sealed_plan(vault, scope, [_skill_resource(root, "alpha")])
        plan_file = self.base / "plan.json"
        plan_file.write_text(json.dumps(plan), encoding="utf-8")
        return plan, plan_file, vault, root, link, physical

    def _args(self, **overrides):
        base = {
            "phase": "authorize-link",
            "scope": None,
            "backup_root": None,
            "output": None,
            "plan": None,
            "receipt": None,
            "confirm_plan": None,
            "host": None,
            "skill_path": None,
            "target_path": None,
            "link_authorization": None,
            "yes": False,
            "probe": False,
            "json": True,
        }
        base.update(overrides)
        return types.SimpleNamespace(**base)

    def _run(self, args) -> tuple[int, dict]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = sbtd_upgrade_cli.run_upgrade(args)
        return code, json.loads(buffer.getvalue())

    def test_authorize_link_cli_emits_and_saves_artifact(self) -> None:
        plan, plan_file, vault, root, link, physical = self._cli_fixture()
        output = vault / "link-authorization.json"
        code, envelope = self._run(
            self._args(
                plan=str(plan_file),
                host=HOST_ID,
                skill_path=str(link),
                target_path=str(physical),
                output=str(output),
            )
        )
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["mode"], "upgrade")
        self.assertEqual(envelope["phase"], "authorize-link")
        self.assertEqual(envelope["authorization_path"], str(output))
        document = envelope["authorization"]
        self.assertEqual(document["payload"]["plan_id"], plan["plan_id"])
        saved = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(saved, document)
        import jsonschema

        jsonschema.validate(document, SCHEMA)
        # The vault write is a new immutable document: a second write is refused.
        code, failure = self._run(
            self._args(
                plan=str(plan_file),
                host=HOST_ID,
                skill_path=str(link),
                target_path=str(physical),
                output=str(output),
            )
        )
        self.assertEqual(code, 2)
        self.assertEqual(failure["status"], "blocked")
        self.assertEqual(saved, json.loads(output.read_text(encoding="utf-8")))

    def test_authorize_link_cli_stdout_only_by_default(self) -> None:
        plan, plan_file, vault, root, link, physical = self._cli_fixture()
        code, envelope = self._run(
            self._args(
                plan=str(plan_file),
                host=HOST_ID,
                skill_path=str(link),
                target_path=str(physical),
            )
        )
        self.assertEqual(code, 0, envelope)
        self.assertIsNone(envelope["authorization_path"])
        self.assertEqual(
            os.listdir(vault), [], "stdout-only prepare must not touch the vault"
        )

    def test_authorize_link_cli_refusal_is_a_blocked_envelope(self) -> None:
        plan, plan_file, vault, root, link, physical = self._cli_fixture()
        other = _write_skill(self.base / "other", "linked-skill")
        code, failure = self._run(
            self._args(
                plan=str(plan_file),
                host=HOST_ID,
                skill_path=str(link),
                target_path=str(other),
            )
        )
        self.assertEqual(code, 2)
        self.assertEqual(failure["status"], "blocked")
        self.assertEqual(failure["reason"], "target-mismatch")
        import jsonschema

        jsonschema.validate(failure, SCHEMA)

    def test_verify_cli_probe_with_comma_separated_authorizations(self) -> None:
        runtime, package = _runtime(self.base), _package(self.base)
        root, link, physical, _alpha = self.linked_fixture()
        other = _write_skill(self.base / "other", "other-skill")
        second = root / "other-skill"
        second.symlink_to(str(other), target_is_directory=True)
        shutil.copytree(
            SCRIPTS.parent, root / "sbtd-workflow-onboard",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        project = self.base / "project"
        project.mkdir()
        host = _codex_host(self.base, runtime, root, project)
        scope = {
            "schema_version": 1,
            "skills_roots": [str(root)],
            "hosts": [host],
            "decisions": {},
        }
        vault = require_private_directory(self.base / "vault", create=True)
        plan = _sealed_plan(vault, scope, [_skill_resource(root, "alpha")])
        plan_path = vault / f"upgrade-plan-{plan['plan_id']}.json"
        save_document(plan_path, plan, private_root=vault)
        plan_file = self.base / "plan.json"
        plan_file.write_text(json.dumps(plan), encoding="utf-8")
        first = sbtd_upgrade.prepare_probe_link_authorization(
            plan, host_id=HOST_ID, skill_path=str(link), target_path=str(physical)
        )
        second_doc = sbtd_upgrade.prepare_probe_link_authorization(
            plan, host_id=HOST_ID, skill_path=str(second), target_path=str(other)
        )
        first_file = self.base / "auth-one.json"
        first_file.write_text(json.dumps(first), encoding="utf-8")
        second_file = self.base / "auth-two.json"
        second_file.write_text(json.dumps(second_doc), encoding="utf-8")
        resource = hosts.build_host_resources(scope, package_root=SCRIPTS.parent)[0]
        config = Path(host["config"])
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_bytes(hosts.render_resource(resource))
        rig = _Rig(
            self, ["alpha", "linked-skill", "other-skill", "sbtd-workflow-onboard"]
        ).install()
        code, result = self._run(
            self._args(
                phase="verify",
                plan=str(plan_file),
                probe=True,
                yes=True,
                link_authorization=f"{first_file},{second_file}",
            )
        )
        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "aligned")
        skills = result["payload"]["hosts"]["hosts"][0]["host"]["checks"]["skills"]
        self.assertEqual(skills["status"], "verified", skills)
        self.assertEqual(
            skills["skills"],
            ["alpha", "linked-skill", "other-skill", "sbtd-workflow-onboard"],
        )
        evidence = skills["link_authorizations"]
        self.assertEqual(
            [item["status"] for item in evidence], ["materialized", "materialized"]
        )
        self.assertEqual(
            {item["authorization_id"] for item in evidence},
            {first["authorization_id"], second_doc["authorization_id"]},
        )
        self.assertTrue(link.is_symlink() and second.is_symlink())

    def test_verify_cli_rejects_blank_authorization_path(self) -> None:
        plan, plan_file, vault, root, link, physical = self._cli_fixture()
        first = sbtd_upgrade.prepare_probe_link_authorization(
            plan, host_id=HOST_ID, skill_path=str(link), target_path=str(physical)
        )
        first_file = self.base / "auth-one.json"
        first_file.write_text(json.dumps(first), encoding="utf-8")
        code, failure = self._run(
            self._args(
                phase="verify",
                plan=str(plan_file),
                probe=True,
                yes=True,
                link_authorization=f"{first_file},",
            )
        )
        self.assertEqual(code, 2)
        self.assertEqual(failure["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
