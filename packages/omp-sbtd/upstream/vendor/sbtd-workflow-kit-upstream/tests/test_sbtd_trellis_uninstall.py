from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import onboard_contracts as contracts
import sbtd_trellis_uninstall as adapter
from sbtd_migration_files import directory_snapshot, snapshot
from sbtd_trellis_uninstall import (
    SUPPORTED_TRELLIS_VERSIONS,
    execute_trellis_uninstall,
    prepare_trellis_uninstall,
)

AGENTS_RAW = (
    b"# mine\n\n<!-- TRELLIS:START -->\nmanaged\n<!-- TRELLIS:END -->\n\n"
    b"<!-- graft:start -->\nfence\n<!-- graft:end -->\n"
)
AGENTS_SCRUBBED = "# mine\n\n\n\n<!-- graft:start -->\nfence\n<!-- graft:end -->\n"
SUPPORTED_VERSION = SUPPORTED_TRELLIS_VERSIONS[0]


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _plan_payload(**overrides):
    """Planner replay shape mirroring the vendor's pure modules."""
    payload = {
        "status": "ok",
        "pruned_keys": [],
        "platforms": ["claude-code"],
        "deletions": [
            {"path": ".claude/settings.json", "missing": False},
            {"path": ".trellis/workflow.md", "missing": False},
        ],
        "modifications": [
            {
                "path": "AGENTS.md",
                "reason": "Strip Trellis managed block; preserve user instructions",
                "content": AGENTS_SCRUBBED,
            }
        ],
        "remove_trellis_dir": True,
        "pruned_dirs": [".claude"],
    }
    payload.update(overrides)
    return payload


def _dry_run_text(plan) -> str:
    deleted = sum(1 for item in plan["deletions"] if not item["missing"]) + 1
    modified = len(plan["modifications"])
    missing = sum(1 for item in plan["deletions"] if item["missing"])
    lines = [
        "",
        "Trellis uninstall plan",
        "",
        f"Will be deleted ({deleted} entries):",
        "  - .claude/settings.json",
        "  - .trellis/  (entire directory)",
        "",
    ]
    if modified:
        lines += [
            f"Will be modified ({modified} files):",
            "  ~ AGENTS.md",
        ]
    if missing:
        lines.append(f"({missing} manifest entries already missing on disk — skipped.)")
    lines.append("Dry run — no files were modified.")
    return "\n".join(lines) + "\n"


class FakeRunner:
    """Boundary fake for the node planner replay and the vendor CLI."""

    def __init__(self, plans, *, dry_run_exit=0, dry_run_text=None, uninstall=None):
        self.plans = plans if isinstance(plans, list) else [plans]
        self.dry_run_exit = dry_run_exit
        self.dry_run_text = dry_run_text
        self.uninstall = uninstall
        self.calls: list[tuple[list[str], dict]] = []
        self.current_plan = None

    def __call__(self, command, **kwargs):
        self.calls.append((list(command), kwargs))
        if Path(command[0]).name == "node":
            self.current_plan = (
                self.plans[0] if len(self.plans) == 1 else self.plans.pop(0)
            )
            return SimpleNamespace(
                returncode=0, stdout=json.dumps(self.current_plan), stderr=""
            )
        if command[1:] == ["uninstall", "--dry-run"]:
            text = (
                self.dry_run_text
                if self.dry_run_text is not None
                else _dry_run_text(self.current_plan)
            )
            return SimpleNamespace(returncode=self.dry_run_exit, stdout=text, stderr="")
        if command[1:] == ["uninstall", "-y"]:
            if self.uninstall is None:
                raise AssertionError("the vendor uninstaller must not run in this test")
            return self.uninstall(command, **kwargs)
        raise AssertionError(f"unexpected command: {command}")

    def uninstall_calls(self):
        return [c for c, _ in self.calls if c[1:] == ["uninstall", "-y"]]


def _apply_plan(root: Path, plan):
    """Perform exactly the mutations the sealed plan describes, like the vendor."""

    def run(command, **kwargs):
        for deletion in plan["deletions"]:
            if not deletion["missing"]:
                (root / deletion["path"]).unlink()
        for modification in plan["modifications"]:
            (root / modification["path"]).write_text(modification["content"])
        shutil.rmtree(root / ".trellis")
        for relative in plan.get("pruned_dirs", []):
            target = root / relative
            if target.is_dir() and not any(target.iterdir()):
                target.rmdir()
        return SimpleNamespace(
            returncode=0,
            stdout="\x1b[32mUninstalled trellis: 2 files deleted, 1 files modified, "
            "2 directories removed.\x1b[0m",
            stderr="",
        )

    return run


class AdapterFixture:
    def __init__(self, base: Path) -> None:
        base = base.resolve()
        self.base = base
        self.project = base / "project"
        self.home = base / "home"
        self.home.mkdir()
        self.vault = base / "vault"
        self.vault.mkdir(mode=0o700)
        package = base / "fakepkg"
        (package / "bin").mkdir(parents=True)
        (package / "dist/commands").mkdir(parents=True)
        (package / "dist/utils").mkdir(parents=True)
        (package / "dist/configurators").mkdir(parents=True)
        cli = package / "bin/trellis.js"
        cli.write_text("#!/usr/bin/env node\n")
        cli.chmod(0o755)
        (package / "package.json").write_text(
            json.dumps({"name": "@mindfoldhq/trellis", "version": SUPPORTED_VERSION})
        )
        for relative in (
            "dist/commands/uninstall.js",
            "dist/configurators/index.js",
            "dist/utils/managed-removal.js",
            "dist/utils/manifest-prune.js",
            "dist/utils/template-hash.js",
        ):
            (package / relative).write_text("// planner module stub\n")
        binary = base / "fakebin"
        binary.mkdir()
        (binary / "tl").symlink_to(cli)
        node = binary / "node"
        node.write_text("#!/bin/sh\n")
        node.chmod(0o755)
        self.package = package
        self.binary = binary
        self.cli = cli
        trellis = self.project / ".trellis"
        (trellis / "workspace/dev01").mkdir(parents=True)
        (trellis / ".template-hashes.json").write_text(
            '{"__version": 2, "hashes": {".claude/settings.json": "abc", "AGENTS.md": "def"}}'
        )
        (trellis / "workflow.md").write_text("guide\n")
        (trellis / "workspace/dev01/notes.md").write_text("journal\n")
        claude = self.project / ".claude"
        claude.mkdir(parents=True)
        (claude / "settings.json").write_text('{"hooks": {}}')
        (self.project / "AGENTS.md").write_bytes(AGENTS_RAW)
        self.environ = {
            "HOME": str(self.home),
            "USERPROFILE": str(self.home),
            "PATH": str(binary),
        }

    def which(self, name: str):
        candidate = self.binary / name
        return str(candidate) if candidate.exists() else None

    def prepare(self, plan=None, **runner_kwargs):
        runner = FakeRunner(
            plan if plan is not None else _plan_payload(), **runner_kwargs
        )
        prepared = prepare_trellis_uninstall(
            self.project, environ=self.environ, which=self.which, runner=runner
        )
        return prepared, runner


class PrepareTests(unittest.TestCase):
    def test_prepare_seals_exact_footprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, _ = fixture.prepare()
            payload = prepared["payload"]
            self.assertEqual(prepared["schema_version"], 1)
            self.assertEqual(prepared["kind"], "trellis-uninstall-prepare")
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["root"], str(fixture.project))
            tool = payload["tool"]
            self.assertEqual(tool["requested"], "tl")
            self.assertEqual(tool["path"], str(fixture.cli))
            self.assertEqual(tool["package_root"], str(fixture.package))
            self.assertEqual(tool["package_name"], "@mindfoldhq/trellis")
            self.assertEqual(tool["package_version"], SUPPORTED_VERSION)
            self.assertEqual(tool["node"], str(fixture.binary / "node"))
            self.assertEqual(
                tool["package_files"]["bin/trellis.js"], snapshot(fixture.cli)
            )
            self.assertEqual(
                tool["package_files"]["dist/utils/managed-removal.js"],
                snapshot(fixture.package / "dist/utils/managed-removal.js"),
            )
            self.assertEqual(
                payload["planner"],
                {"source": "node-import", "strict_paths": True, "prune_persist": False},
            )
            evidence = payload["evidence"]["dry_run"]
            self.assertEqual(evidence["exit"], 0)
            self.assertEqual(evidence["deleted_entries"], 3)
            self.assertEqual(evidence["modified_files"], 1)
            self.assertTrue(evidence["matches_planner"])
            resources = payload["resources"]
            self.assertEqual(
                [(r["kind"], r["relative"]) for r in resources],
                [
                    ("vendor-delete", ".claude/settings.json"),
                    ("vendor-scrub", "AGENTS.md"),
                    ("vendor-trellis-dir", ".trellis"),
                    ("vendor-prune-dir", ".claude"),
                ],
                "the whole .trellis tree must be exactly one resource entry",
            )
            delete, scrub, tree, prune = resources
            self.assertEqual(
                delete["before"],
                {"type": "file", "checksum": _sha256(b'{"hooks": {}}')},
            )
            self.assertEqual(
                delete["expected_after"], {"type": "absent", "checksum": None}
            )
            self.assertEqual(scrub["before"]["checksum"], _sha256(AGENTS_RAW))
            self.assertEqual(
                scrub["expected_after"],
                {"type": "file", "checksum": _sha256(AGENTS_SCRUBBED.encode())},
            )
            self.assertEqual(
                scrub["reason"],
                "Strip Trellis managed block; preserve user instructions",
            )
            self.assertEqual(tree["before"], snapshot(fixture.project / ".trellis"))
            self.assertEqual(
                tree["expected_after"], {"type": "absent", "checksum": None}
            )
            self.assertEqual(prune["before"], snapshot(fixture.project / ".claude"))
            self.assertEqual(
                prune["expected_after"], {"type": "absent", "checksum": None}
            )
            for resource in resources:
                self.assertTrue(resource["path"].startswith(str(fixture.project)))
            expected_id = hashlib.sha256(
                contracts.canonical_json_bytes(payload)
            ).hexdigest()
            self.assertEqual(prepared["prepared_id"], expected_id)
            json.dumps(prepared)

    def test_prepare_records_missing_manifest_entries_as_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            plan = _plan_payload(
                deletions=[
                    {"path": ".claude/settings.json", "missing": False},
                    {"path": ".codex/hooks.json", "missing": True},
                ]
            )
            prepared, _ = fixture.prepare(plan)
            payload = prepared["payload"]
            self.assertEqual(payload["skipped_missing"], [".codex/hooks.json"])
            self.assertEqual(
                [r["relative"] for r in payload["resources"]],
                [".claude/settings.json", "AGENTS.md", ".trellis", ".claude"],
            )
            self.assertEqual(payload["evidence"]["dry_run"]["missing_entries"], 1)

    def test_prepare_accepts_dry_run_without_modified_section_when_none_expected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, _ = fixture.prepare(_plan_payload(modifications=[]))
            payload = prepared["payload"]
            self.assertEqual(payload["status"], "ready")
            evidence = payload["evidence"]["dry_run"]
            self.assertEqual(evidence["modified_files"], 0)
            self.assertTrue(evidence["matches_planner"])
            self.assertEqual(
                [r["relative"] for r in payload["resources"]],
                [".claude/settings.json", ".trellis", ".claude"],
            )

    def test_prepare_rejects_missing_modified_section_when_modifications_expected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            text_without_modified = _dry_run_text(_plan_payload(modifications=[]))
            with self.assertRaises(contracts.ContractError) as caught:
                fixture.prepare(dry_run_text=text_without_modified)
            self.assertEqual(caught.exception.code, "plan-evidence-mismatch")

    def test_prepare_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            before, _ = directory_snapshot(fixture.project)
            fixture.prepare()
            after, _ = directory_snapshot(fixture.project)
            self.assertEqual(before, after)
            self.assertEqual(list(fixture.vault.iterdir()), [])

    def test_prepare_without_trellis_returns_absent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            shutil.rmtree(fixture.project / ".trellis")

            def no_runner(command, **kwargs):
                raise AssertionError("no vendor probe may run when .trellis is absent")

            prepared = prepare_trellis_uninstall(
                fixture.project,
                environ=fixture.environ,
                which=fixture.which,
                runner=no_runner,
            )
            payload = prepared["payload"]
            self.assertEqual(payload["status"], "absent")
            self.assertEqual(payload["resources"], [])
            self.assertIsNone(payload["tool"])
            json.dumps(prepared)

    def test_prepare_missing_tool_returns_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared = prepare_trellis_uninstall(
                fixture.project,
                environ=fixture.environ,
                which=lambda name: None,
                runner=FakeRunner(_plan_payload()),
            )
            payload = prepared["payload"]
            self.assertEqual(payload["status"], "unavailable")
            self.assertEqual(payload["unavailable_code"], "tool-unavailable")
            self.assertIsNone(payload["tool"])
            self.assertEqual(payload["resources"], [])

    def test_prepare_discovery_uses_the_given_environ_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared = prepare_trellis_uninstall(
                fixture.project,
                environ=fixture.environ,
                runner=FakeRunner(_plan_payload()),
            )
            tool = prepared["payload"]["tool"]
            self.assertEqual(tool["path"], str(fixture.cli))
            isolated = dict(fixture.environ, PATH="/nonexistent")
            prepared = prepare_trellis_uninstall(
                fixture.project,
                environ=isolated,
                runner=FakeRunner(_plan_payload()),
            )
            self.assertEqual(prepared["payload"]["status"], "unavailable")
            self.assertEqual(
                prepared["payload"]["unavailable_code"], "tool-unavailable"
            )
            no_path = {"HOME": str(fixture.home), "USERPROFILE": str(fixture.home)}
            prepared = prepare_trellis_uninstall(
                fixture.project,
                environ=no_path,
                runner=FakeRunner(_plan_payload()),
            )
            self.assertEqual(prepared["payload"]["status"], "unavailable")
            self.assertEqual(
                prepared["payload"]["unavailable_code"], "tool-unavailable"
            )

    def test_prepare_unsupported_planner_version_returns_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            (fixture.package / "package.json").write_text(
                json.dumps({"name": "@mindfoldhq/trellis", "version": "0.7.0"})
            )
            prepared, _ = fixture.prepare()
            payload = prepared["payload"]
            self.assertEqual(payload["status"], "unavailable")
            self.assertEqual(payload["unavailable_code"], "tool-version-unsupported")
            self.assertEqual(payload["tool"]["package_version"], "0.7.0")
            self.assertEqual(payload["resources"], [])

    def test_prepare_missing_manifest_returns_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, _ = fixture.prepare({"status": "no-manifest"})
            payload = prepared["payload"]
            self.assertEqual(payload["status"], "unavailable")
            self.assertEqual(payload["unavailable_code"], "manifest-missing")
            self.assertEqual(payload["tool"]["path"], str(fixture.cli))

    def test_prepare_untrustworthy_binding_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            (fixture.binary / "tl").unlink()
            stray = fixture.base / "stray-tl"
            stray.write_text("#!/bin/sh\n")
            (fixture.binary / "tl").symlink_to(stray)
            with self.assertRaises(contracts.ContractError) as caught:
                fixture.prepare()
            self.assertEqual(caught.exception.code, "tool-binding")

    def test_prepare_rejects_home_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            environ = dict(fixture.environ, HOME=str(fixture.project))
            with self.assertRaises(contracts.ContractError) as caught:
                prepare_trellis_uninstall(
                    fixture.project,
                    environ=environ,
                    which=fixture.which,
                    runner=FakeRunner(_plan_payload()),
                )
            self.assertEqual(caught.exception.code, "home-root-refused")

    def test_prepare_rejects_symlink_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            link = fixture.base / "link"
            link.symlink_to(fixture.project)
            with self.assertRaises(contracts.ContractError) as caught:
                prepare_trellis_uninstall(
                    link,
                    environ=fixture.environ,
                    which=fixture.which,
                    runner=FakeRunner(_plan_payload()),
                )
            self.assertEqual(caught.exception.code, "invalid-root")

    def test_prepare_rejects_noncanonical_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            for bad in ("relative/project", str(fixture.project / ".."), "/"):
                with self.assertRaises(contracts.ContractError) as caught:
                    prepare_trellis_uninstall(
                        bad,
                        environ=fixture.environ,
                        which=fixture.which,
                        runner=FakeRunner(_plan_payload()),
                    )
                self.assertIn(caught.exception.code, {"unsafe-path", "invalid-root"})

    def test_prepare_planner_parent_escape_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            plan = _plan_payload(
                deletions=[{"path": "../outside.txt", "missing": False}]
            )
            with self.assertRaises(contracts.ContractError) as caught:
                fixture.prepare(plan)
            self.assertEqual(caught.exception.code, "plan-unsafe")
            self.assertTrue((fixture.project / ".trellis").is_dir())

    def test_prepare_rejects_control_characters_in_managed_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            plan = _plan_payload(
                deletions=[{"path": ".claude/\nspoofed-header", "missing": False}]
            )
            with self.assertRaises(contracts.ContractError) as caught:
                fixture.prepare(plan)
            self.assertEqual(caught.exception.code, "plan-unsafe")

    def test_prepare_planner_duplicate_path_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            plan = _plan_payload(
                deletions=[
                    {"path": ".claude/settings.json", "missing": False},
                    {"path": ".claude/settings.json", "missing": False},
                ]
            )
            with self.assertRaises(contracts.ContractError) as caught:
                fixture.prepare(plan)
            self.assertEqual(caught.exception.code, "plan-unsafe")

    def test_prepare_planner_rejection_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            with self.assertRaises(contracts.ContractError) as caught:
                fixture.prepare({"status": "plan-error", "message": "vendor detail"})
            self.assertEqual(caught.exception.code, "plan-unsafe")

    def test_prepare_dry_run_disagreement_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            with self.assertRaises(contracts.ContractError) as caught:
                fixture.prepare(dry_run_text="Will be deleted (9 entries):\n")
            self.assertEqual(caught.exception.code, "plan-evidence-mismatch")

    def test_prepare_dry_run_refusal_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            with self.assertRaises(contracts.ContractError) as caught:
                fixture.prepare(dry_run_exit=1)
            self.assertEqual(caught.exception.code, "vendor-dry-run-failed")

    def test_prepare_symlinked_managed_file_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            target = fixture.project / ".claude/settings.json"
            target.unlink()
            target.symlink_to(fixture.project / "AGENTS.md")
            with self.assertRaises(contracts.ContractError) as caught:
                fixture.prepare()
            self.assertEqual(caught.exception.code, "unsafe-path")


class ExecuteTests(unittest.TestCase):
    def _prepared(self, fixture: AdapterFixture, plan=None):
        plan = plan if plan is not None else _plan_payload()
        prepared, _ = fixture.prepare(plan)
        return prepared, plan

    def _execute(self, fixture, prepared, runner):
        return execute_trellis_uninstall(
            fixture.project,
            prepared,
            fixture.vault,
            environ=fixture.environ,
            runner=runner,
        )

    def test_caller_guard_rejects_evidence_drift_during_backup_before_vendor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)
            proof = fixture.vault / "proof.json"
            proof.write_bytes(b"original evidence")
            expected = snapshot(proof)
            original_tree = snapshot(fixture.project)
            original_backup = adapter.backup_reference
            runner = FakeRunner(plan, uninstall=_apply_plan(fixture.project, plan))

            def backup_then_drift(*args, **kwargs):
                ref = original_backup(*args, **kwargs)
                proof.write_bytes(b"concurrent change")
                return ref

            def guard():
                if snapshot(proof) != expected:
                    raise contracts.ContractError("evidence-mismatch", "evidence changed")

            with (
                mock.patch.object(adapter, "backup_reference", side_effect=backup_then_drift),
                self.assertRaises(contracts.ContractError) as failure,
            ):
                execute_trellis_uninstall(
                    fixture.project, prepared, fixture.vault,
                    environ=fixture.environ, runner=runner, before_execute=guard,
                )
            self.assertEqual(failure.exception.code, "evidence-mismatch")
            self.assertEqual(runner.uninstall_calls(), [])
            self.assertEqual(snapshot(fixture.project), original_tree)

    def test_execute_runs_vendor_and_records_everything(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)
            environ = dict(
                fixture.environ,
                TRELLIS_ALLOW_DIRTY_UNINSTALL="1",
                TRELLIS_ALLOW_HOMEDIR="1",
                NODE_OPTIONS="--require=/private/evil-preload.js",
                NODE_PATH=str(fixture.base / "evil-modules"),
            )
            runner = FakeRunner(plan, uninstall=_apply_plan(fixture.project, plan))
            outcome = execute_trellis_uninstall(
                fixture.project, prepared, fixture.vault, environ=environ, runner=runner
            )
            self.assertEqual(outcome["status"], "removed")
            self.assertEqual(outcome["exit"], 0)
            self.assertEqual(outcome["errors"], [])
            self.assertEqual(outcome["command"], [str(fixture.cli), "uninstall", "-y"])
            self.assertEqual(len(runner.uninstall_calls()), 1)
            call_kwargs = next(
                kwargs
                for command, kwargs in runner.calls
                if command[1:] == ["uninstall", "-y"]
            )
            self.assertEqual(call_kwargs["cwd"], str(fixture.project))
            self.assertNotIn("TRELLIS_ALLOW_DIRTY_UNINSTALL", call_kwargs["env"])
            self.assertNotIn("TRELLIS_ALLOW_HOMEDIR", call_kwargs["env"])
            self.assertNotIn("NODE_OPTIONS", call_kwargs["env"])
            self.assertNotIn("NODE_PATH", call_kwargs["env"])
            self.assertEqual(
                Path(shutil.which("node", path=call_kwargs["env"]["PATH"])).resolve(),
                fixture.binary / "node",
            )
            self.assertEqual(call_kwargs["env"]["HOME"], str(fixture.home))
            statuses = [record["status"] for record in outcome["results"]]
            self.assertEqual(statuses, ["removed", "scrubbed", "removed", "removed"])
            for record, resource in zip(
                outcome["results"], prepared["payload"]["resources"]
            ):
                self.assertEqual(record["path"], resource["path"])
                self.assertEqual(record["before"], resource["before"])
                self.assertEqual(record["after"], resource["expected_after"])
                self.assertEqual(record["backup_ref"]["state"], resource["before"])
            backup_root = Path(outcome["backups"]["root"])
            self.assertEqual(backup_root.parent, fixture.vault)
            self.assertEqual(backup_root.name, prepared["prepared_id"])
            agents_backup = Path(outcome["results"][1]["backup_ref"]["path"])
            self.assertEqual(agents_backup.read_bytes(), AGENTS_RAW)
            tree_backup = Path(outcome["results"][2]["backup_ref"]["path"])
            self.assertEqual(
                snapshot(tree_backup), prepared["payload"]["resources"][2]["before"]
            )
            self.assertTrue((tree_backup / "workspace/dev01/notes.md").is_file())
            self.assertFalse((fixture.project / ".trellis").exists())
            self.assertFalse((fixture.project / ".claude").exists())
            self.assertEqual(
                (fixture.project / "AGENTS.md").read_text(), AGENTS_SCRUBBED
            )
            evidence = Path(outcome["evidence_ref"]["path"])
            document = json.loads(evidence.read_text())
            self.assertEqual(document["kind"], "trellis-uninstall-outcome")
            self.assertEqual(document["exit"], 0)
            self.assertIn("Uninstalled trellis", document["stdout"])
            self.assertNotIn("\x1b", document["stdout"])
            json.dumps(outcome)

    def test_vendor_dry_run_and_execute_bind_sealed_node(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            evil_bin = fixture.base / "evilbin"
            evil_bin.mkdir()
            evil_node = evil_bin / "node"
            evil_node.write_text("#!/bin/sh\n")
            evil_node.chmod(0o755)
            environ = dict(
                fixture.environ,
                PATH=str(evil_bin),
                NODE_OPTIONS="--require=/private/evil-preload.js",
                NODE_PATH=str(fixture.base / "evil-modules"),
            )
            plan = _plan_payload()
            prepare_runner = FakeRunner(plan)
            prepared = prepare_trellis_uninstall(
                fixture.project,
                environ=environ,
                which=fixture.which,
                runner=prepare_runner,
            )
            dry_run_env = next(
                kwargs["env"]
                for command, kwargs in prepare_runner.calls
                if command[1:] == ["uninstall", "--dry-run"]
            )
            planner_env = next(
                kwargs["env"]
                for command, kwargs in prepare_runner.calls
                if Path(command[0]).name == "node"
            )
            self.assertNotIn("NODE_OPTIONS", planner_env)
            self.assertNotIn("NODE_PATH", planner_env)
            self.assertNotIn("NODE_OPTIONS", dry_run_env)
            self.assertNotIn("NODE_PATH", dry_run_env)
            self.assertEqual(
                Path(shutil.which("node", path=dry_run_env["PATH"])).resolve(),
                fixture.binary / "node",
            )
            execute_runner = FakeRunner(
                plan, uninstall=_apply_plan(fixture.project, plan)
            )
            outcome = execute_trellis_uninstall(
                fixture.project,
                prepared,
                fixture.vault,
                environ=environ,
                runner=execute_runner,
            )
            self.assertEqual(outcome["status"], "removed")
            execute_env = next(
                kwargs["env"]
                for command, kwargs in execute_runner.calls
                if command[1:] == ["uninstall", "-y"]
            )
            self.assertEqual(
                Path(shutil.which("node", path=execute_env["PATH"])).resolve(),
                fixture.binary / "node",
            )
            self.assertNotIn("NODE_OPTIONS", execute_env)
            self.assertNotIn("NODE_PATH", execute_env)

    def test_execute_evidence_write_failure_keeps_measured_partial_outcome(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)
            runner = FakeRunner(plan, uninstall=_apply_plan(fixture.project, plan))
            failure = contracts.ContractError(
                "write-failed", "private evidence sink unavailable", exit_code=3
            )
            with mock.patch.object(adapter, "save_document", side_effect=failure):
                outcome = self._execute(fixture, prepared, runner)
            self.assertEqual(outcome["status"], "partial")
            self.assertIsNone(outcome["evidence_ref"])
            self.assertTrue(outcome["errors"][-1].startswith("evidence-failed:"))
            self.assertTrue(
                all(r["status"] in ("removed", "scrubbed") for r in outcome["results"])
            )
            self.assertFalse((fixture.project / ".trellis").exists())

    def test_execute_backs_up_before_vendor_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)
            observed = {}

            def uninstall(command, **kwargs):
                backup_dir = fixture.vault / prepared["prepared_id"] / "resources"
                observed["agents_backup"] = (backup_dir / "001").read_bytes()
                observed["settings_present"] = (
                    fixture.project / ".claude/settings.json"
                ).is_file()
                return _apply_plan(fixture.project, plan)(command, **kwargs)

            runner = FakeRunner(plan, uninstall=uninstall)
            outcome = self._execute(fixture, prepared, runner)
            self.assertEqual(outcome["status"], "removed")
            self.assertEqual(observed["agents_backup"], AGENTS_RAW)
            self.assertTrue(observed["settings_present"])

    def test_execute_rechecks_after_backups_before_vendor_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)
            original_backup = adapter.backup_reference

            def concurrent_edit(source_ref, destination, *, private_root):
                result = original_backup(
                    source_ref, destination, private_root=private_root
                )
                if source_ref["path"] == str(fixture.project / ".claude"):
                    with open(fixture.project / "AGENTS.md", "ab") as handle:
                        handle.write(b"concurrent user edit\n")
                return result

            with (
                mock.patch.object(
                    adapter, "backup_reference", side_effect=concurrent_edit
                ),
                self.assertRaises(contracts.ContractError) as caught,
            ):
                self._execute(fixture, prepared, FakeRunner(plan))
            self.assertEqual(caught.exception.code, "state-conflict")
            self.assertTrue((fixture.project / ".trellis").is_dir())
            self.assertTrue(
                (fixture.vault / prepared["prepared_id"] / "resources").is_dir()
            )

    def test_execute_uninstalls_when_missing_manifest_entry_stays_missing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            codex = fixture.project / ".codex"
            codex.mkdir()
            (codex / "notes.txt").write_text("unrelated user file\n")
            plan = _plan_payload(
                deletions=[
                    {"path": ".claude/settings.json", "missing": False},
                    {"path": ".codex/hooks.json", "missing": True},
                ]
            )
            prepared, _ = self._prepared(fixture, plan)
            self.assertEqual(
                prepared["payload"]["skipped_missing"], [".codex/hooks.json"]
            )
            runner = FakeRunner(plan, uninstall=_apply_plan(fixture.project, plan))
            outcome = self._execute(fixture, prepared, runner)
            self.assertEqual(outcome["status"], "removed")
            self.assertEqual(len(runner.uninstall_calls()), 1)
            self.assertEqual(
                [r["state"] for r in outcome["backups"]["refs"]],
                [r["before"] for r in prepared["payload"]["resources"]],
            )
            for reference in outcome["backups"]["refs"]:
                self.assertTrue(Path(reference["path"]).exists())
            self.assertEqual((codex / "notes.txt").read_text(), "unrelated user file\n")
            self.assertFalse((codex / "hooks.json").exists())

    def test_execute_rejects_skipped_missing_path_reappearing_during_backup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            codex = fixture.project / ".codex"
            codex.mkdir()
            (codex / "notes.txt").write_text("unrelated user file\n")
            plan = _plan_payload(
                deletions=[
                    {"path": ".claude/settings.json", "missing": False},
                    {"path": ".codex/hooks.json", "missing": True},
                ]
            )
            prepared, _ = self._prepared(fixture, plan)
            original_backup = adapter.backup_reference

            def concurrent_create(source_ref, destination, *, private_root):
                result = original_backup(
                    source_ref, destination, private_root=private_root
                )
                (codex / "hooks.json").write_text("created mid-backup\n")
                return result

            runner = FakeRunner(plan)
            with (
                mock.patch.object(
                    adapter, "backup_reference", side_effect=concurrent_create
                ),
                self.assertRaises(contracts.ContractError) as caught,
            ):
                self._execute(fixture, prepared, runner)
            self.assertEqual(caught.exception.code, "state-conflict")
            self.assertEqual(runner.uninstall_calls(), [])
            self.assertEqual((codex / "hooks.json").read_text(), "created mid-backup\n")
            self.assertEqual((codex / "notes.txt").read_text(), "unrelated user file\n")
            self.assertTrue(
                (fixture.vault / prepared["prepared_id"] / "resources").is_dir()
            )

    def test_execute_spawn_failure_is_measured_and_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)

            def uninstall(command, **kwargs):
                raise OSError("boom sensitive-marker")

            outcome = self._execute(
                fixture, prepared, FakeRunner(plan, uninstall=uninstall)
            )
            self.assertEqual(outcome["status"], "failed")
            self.assertIsNone(outcome["exit"])
            self.assertTrue(
                all(record["status"] == "unchanged" for record in outcome["results"])
            )
            self.assertEqual(len(outcome["errors"]), 1)
            self.assertTrue(outcome["errors"][0].startswith("vendor-run-failed:"))
            self.assertNotIn("sensitive-marker", json.dumps(outcome))
            self.assertTrue((fixture.project / ".trellis").is_dir())
            self.assertTrue(Path(outcome["backups"]["refs"][0]["path"]).is_file())
            self.assertIsNotNone(outcome["evidence_ref"])

    def test_execute_timeout_is_a_measured_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)

            def uninstall(command, **kwargs):
                raise subprocess.TimeoutExpired(command, 120)

            outcome = self._execute(
                fixture, prepared, FakeRunner(plan, uninstall=uninstall)
            )
            self.assertEqual(outcome["status"], "failed")
            self.assertTrue((fixture.project / ".trellis").is_dir())

    def test_execute_vendor_refusal_is_reported_without_claiming_intact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)

            def uninstall(command, **kwargs):
                return SimpleNamespace(
                    returncode=1,
                    stdout="",
                    stderr="Refusing: uncommitted user data sensitive-marker",
                )

            outcome = self._execute(
                fixture, prepared, FakeRunner(plan, uninstall=uninstall)
            )
            self.assertEqual(outcome["status"], "failed")
            self.assertTrue(
                outcome["errors"][0].startswith(
                    "vendor-refused: the vendor uninstall exited 1"
                )
            )
            for record in outcome["results"]:
                self.assertEqual(record["status"], "unchanged")
                self.assertEqual(record["after"], record["before"])
            self.assertNotIn("sensitive-marker", json.dumps(outcome))
            evidence = json.loads(Path(outcome["evidence_ref"]["path"]).read_text())
            self.assertIn("sensitive-marker", evidence["stderr"])
            self.assertTrue((fixture.project / ".trellis").is_dir())

    def test_execute_partial_mutation_is_measured_not_narrated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)

            def uninstall(command, **kwargs):
                shutil.rmtree(fixture.project / ".trellis")
                (fixture.project / ".claude/settings.json").unlink()
                return SimpleNamespace(returncode=1, stdout="", stderr="")

            outcome = self._execute(
                fixture, prepared, FakeRunner(plan, uninstall=uninstall)
            )
            self.assertEqual(outcome["status"], "partial")
            by_relative = {r["relative"]: r for r in outcome["results"]}
            self.assertEqual(by_relative[".claude/settings.json"]["status"], "removed")
            self.assertEqual(by_relative[".trellis"]["status"], "removed")
            self.assertEqual(by_relative["AGENTS.md"]["status"], "unchanged")
            self.assertEqual(by_relative[".claude"]["status"], "unexpected")
            self.assertFalse((fixture.project / ".trellis").exists())
            self.assertEqual((fixture.project / "AGENTS.md").read_bytes(), AGENTS_RAW)

    def test_execute_vendor_success_without_mutation_fails_and_never_deletes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)

            def uninstall(command, **kwargs):
                return SimpleNamespace(returncode=0, stdout="done", stderr="")

            outcome = self._execute(
                fixture, prepared, FakeRunner(plan, uninstall=uninstall)
            )
            self.assertEqual(outcome["status"], "failed")
            self.assertTrue(outcome["errors"][0].startswith("vendor-verification:"))
            self.assertTrue(
                (fixture.project / ".trellis").is_dir(),
                "the adapter must never delete .trellis itself",
            )

    def test_execute_retried_refusal_keeps_distinct_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)

            def uninstall(command, **kwargs):
                return SimpleNamespace(returncode=1, stdout="", stderr="refused")

            runner = FakeRunner(plan, uninstall=uninstall)
            first = self._execute(fixture, prepared, runner)
            second = self._execute(fixture, prepared, runner)
            self.assertEqual(first["status"], "failed")
            self.assertEqual(second["status"], "failed")
            self.assertFalse(any("evidence-failed" in e for e in second["errors"]))
            evidence_files = list(
                (fixture.vault / prepared["prepared_id"]).glob("outcome-*.json")
            )
            self.assertEqual(len(evidence_files), 2)

    def test_execute_rejects_tampered_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)
            tampered = json.loads(json.dumps(prepared))
            tampered["payload"]["resources"][0]["before"] = {
                "type": "file",
                "checksum": "0" * 64,
            }
            with self.assertRaises(contracts.ContractError) as caught:
                self._execute(fixture, tampered, FakeRunner(plan))
            self.assertEqual(caught.exception.code, "binding-violation")
            self.assertTrue((fixture.project / ".trellis").is_dir())
            self.assertEqual(list(fixture.vault.iterdir()), [])

    def test_execute_rejects_resealed_resource_path_substitution(self) -> None:
        for location in ("inside-project", "outside-project"):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as directory:
                fixture = AdapterFixture(Path(directory))
                prepared, plan = self._prepared(fixture)
                parent = fixture.project if location == "inside-project" else fixture.base
                decoy = parent / "decoy.md"
                decoy.write_text(AGENTS_SCRUBBED)
                resource = next(
                    item for item in prepared["payload"]["resources"]
                    if item["relative"] == "AGENTS.md"
                )
                resource["path"] = str(decoy)
                resource["before"] = snapshot(decoy)
                prepared["prepared_id"] = hashlib.sha256(
                    contracts.canonical_json_bytes(prepared["payload"])
                ).hexdigest()
                before, _ = directory_snapshot(fixture.project)
                runner = FakeRunner(plan, uninstall=_apply_plan(fixture.project, plan))

                with self.assertRaises(contracts.ContractError) as caught:
                    self._execute(fixture, prepared, runner)

                self.assertEqual(caught.exception.code, "invalid-document")
                self.assertEqual(runner.uninstall_calls(), [])
                self.assertEqual(directory_snapshot(fixture.project)[0], before)
                self.assertEqual(decoy.read_text(), AGENTS_SCRUBBED)
                self.assertEqual(list(fixture.vault.iterdir()), [])

    def test_execute_rejects_resealed_unsafe_relative_paths(self) -> None:
        for relative in ("../AGENTS.md", "/AGENTS.md", "./AGENTS.md"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                fixture = AdapterFixture(Path(directory))
                prepared, plan = self._prepared(fixture)
                payload = prepared["payload"]
                resource = payload["resources"][1]
                resource["relative"] = relative
                resource["path"] = str(fixture.project / relative)
                payload["scope"]["resources"][1]["relative"] = relative
                prepared["prepared_id"] = hashlib.sha256(
                    contracts.canonical_json_bytes(payload)
                ).hexdigest()
                before, _ = directory_snapshot(fixture.project)
                runner = FakeRunner(plan, uninstall=_apply_plan(fixture.project, plan))

                with self.assertRaises(contracts.ContractError) as caught:
                    self._execute(fixture, prepared, runner)

                self.assertEqual(caught.exception.code, "plan-unsafe")
                self.assertEqual(runner.uninstall_calls(), [])
                self.assertEqual(directory_snapshot(fixture.project)[0], before)
                self.assertEqual(list(fixture.vault.iterdir()), [])

    def test_execute_rejects_state_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)
            with open(fixture.project / "AGENTS.md", "ab") as handle:
                handle.write(b"user edit\n")
            with self.assertRaises(contracts.ContractError) as caught:
                self._execute(fixture, prepared, FakeRunner(plan))
            self.assertEqual(caught.exception.code, "state-conflict")
            self.assertTrue((fixture.project / ".trellis").is_dir())
            self.assertEqual(list(fixture.vault.iterdir()), [])

    def test_execute_rejects_scope_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, _plan = self._prepared(fixture)
            (fixture.project / ".codex").mkdir()
            (fixture.project / ".codex/config.toml").write_text("[x]\n")
            drifted = _plan_payload(
                deletions=[
                    {"path": ".claude/settings.json", "missing": False},
                    {"path": ".codex/config.toml", "missing": False},
                ]
            )
            with self.assertRaises(contracts.ContractError) as caught:
                self._execute(fixture, prepared, FakeRunner(drifted))
            self.assertEqual(caught.exception.code, "scope-conflict")
            self.assertTrue((fixture.project / ".trellis").is_dir())

    def test_execute_rejects_tool_version_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)
            (fixture.package / "package.json").write_text(
                json.dumps({"name": "@mindfoldhq/trellis", "version": "0.6.18"})
            )
            with self.assertRaises(contracts.ContractError) as caught:
                self._execute(fixture, prepared, FakeRunner(plan))
            self.assertEqual(caught.exception.code, "tool-version-unsupported")
            self.assertTrue((fixture.project / ".trellis").is_dir())

    def test_execute_rejects_in_place_planner_module_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)
            (fixture.package / "dist/utils/managed-removal.js").write_text(
                "// replaced after preparation\n"
            )
            with self.assertRaises(contracts.ContractError) as caught:
                self._execute(fixture, prepared, FakeRunner(plan))
            self.assertEqual(caught.exception.code, "scope-conflict")
            self.assertTrue((fixture.project / ".trellis").is_dir())

    def test_execute_rejects_cli_losing_executable_bit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)
            fixture.cli.chmod(0o644)
            with self.assertRaises(contracts.ContractError) as caught:
                self._execute(fixture, prepared, FakeRunner(plan))
            self.assertEqual(caught.exception.code, "tool-binding")
            self.assertTrue((fixture.project / ".trellis").is_dir())

    def test_execute_rejects_root_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            (fixture.base / "other").mkdir()
            other = AdapterFixture(fixture.base / "other")
            prepared, plan = self._prepared(fixture)
            with self.assertRaises(contracts.ContractError) as caught:
                execute_trellis_uninstall(
                    other.project,
                    prepared,
                    fixture.vault,
                    environ=fixture.environ,
                    runner=FakeRunner(plan),
                )
            self.assertEqual(caught.exception.code, "scope-conflict")

    def test_execute_requires_private_backup_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)
            fixture.vault.chmod(0o755)
            try:
                with self.assertRaises(contracts.ContractError) as caught:
                    self._execute(fixture, prepared, FakeRunner(plan))
                self.assertEqual(caught.exception.code, "privacy-unproven")
            finally:
                fixture.vault.chmod(0o700)
            self.assertTrue((fixture.project / ".trellis").is_dir())

    def test_execute_rejects_backup_root_inside_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)
            inside = fixture.project / ".private-vault"
            inside.mkdir(mode=0o700)
            with self.assertRaises(contracts.ContractError) as caught:
                execute_trellis_uninstall(
                    fixture.project,
                    prepared,
                    inside,
                    environ=fixture.environ,
                    runner=FakeRunner(plan),
                )
            self.assertEqual(caught.exception.code, "scope-violation")
            self.assertTrue((fixture.project / ".trellis").is_dir())

    def test_execute_rejects_symlink_backup_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared, plan = self._prepared(fixture)
            link = fixture.base / "vault-link"
            link.symlink_to(fixture.vault)
            with self.assertRaises(contracts.ContractError) as caught:
                execute_trellis_uninstall(
                    fixture.project,
                    prepared,
                    link,
                    environ=fixture.environ,
                    runner=FakeRunner(plan),
                )
            self.assertEqual(caught.exception.code, "unsafe-path")

    def test_execute_unavailable_is_refused_before_anything_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            prepared = prepare_trellis_uninstall(
                fixture.project,
                environ=fixture.environ,
                which=lambda name: None,
                runner=FakeRunner(_plan_payload()),
            )
            self.assertEqual(prepared["payload"]["status"], "unavailable")
            with self.assertRaises(contracts.ContractError) as caught:
                self._execute(fixture, prepared, FakeRunner(_plan_payload()))
            self.assertEqual(caught.exception.code, "vendor-unavailable")
            self.assertTrue((fixture.project / ".trellis").is_dir())
            self.assertEqual(list(fixture.vault.iterdir()), [])

    def test_execute_absent_is_a_verified_noop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            shutil.rmtree(fixture.project / ".trellis")
            prepared = prepare_trellis_uninstall(
                fixture.project,
                environ=fixture.environ,
                which=fixture.which,
                runner=FakeRunner(_plan_payload()),
            )

            def no_runner(command, **kwargs):
                raise AssertionError("no vendor run for an absent uninstall")

            outcome = execute_trellis_uninstall(
                fixture.project,
                prepared,
                fixture.vault,
                environ=fixture.environ,
                runner=no_runner,
            )
            self.assertEqual(outcome["status"], "removed")
            self.assertEqual(outcome["results"], [])
            self.assertEqual(outcome["backups"], {"root": None, "refs": []})
            self.assertEqual(list(fixture.vault.iterdir()), [])

    def test_execute_absent_rejects_reappearing_trellis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = AdapterFixture(Path(directory))
            shutil.rmtree(fixture.project / ".trellis")
            absent = prepare_trellis_uninstall(
                fixture.project,
                environ=fixture.environ,
                which=fixture.which,
                runner=FakeRunner(_plan_payload()),
            )
            self.assertEqual(absent["payload"]["status"], "absent")
            (fixture.project / ".trellis").mkdir()
            with self.assertRaises(contracts.ContractError) as caught:
                self._execute(fixture, absent, FakeRunner(_plan_payload()))
            self.assertEqual(caught.exception.code, "state-conflict")


REAL_TL = shutil.which("tl")
REAL_NODE = shutil.which("node")


@unittest.skipUnless(REAL_TL and REAL_NODE, "the vendor Trellis CLI is not installed")
class RealVendorTests(unittest.TestCase):
    """Isolated smoke against the actually installed tl in a disposable project."""

    def _fixture(
        self, base: Path, *, orphan_hook: bool, managed_agents: bool = True
    ) -> Path:
        base = base.resolve()
        project = base / "project"
        trellis = project / ".trellis"
        (trellis / "workspace/dev01").mkdir(parents=True)
        manifest = {
            "__version": 2,
            "hashes": {
                ".claude/settings.json": "aa",
                ".trellis/workflow.md": "cc",
            },
        }
        if managed_agents:
            manifest["hashes"]["AGENTS.md"] = "bb"
        if orphan_hook:
            manifest["hashes"][".claude/hooks/x.py"] = "dd"
        (trellis / ".template-hashes.json").write_text(json.dumps(manifest))
        (trellis / "workflow.md").write_text("guide\n")
        (trellis / "workspace/dev01/notes.md").write_text("journal\n")
        claude = project / ".claude"
        claude.mkdir(parents=True)
        (claude / "settings.json").write_text('{"hooks": {}}')
        if orphan_hook:
            (claude / "hooks").mkdir()
            (claude / "hooks/x.py").write_text("user owned\n")
        agents = "# mine\n<!-- graft:start -->\nfence\n<!-- graft:end -->\n"
        if managed_agents:
            agents = (
                "# mine\n<!-- TRELLIS:START -->\nmanaged\n<!-- TRELLIS:END -->\n"
                "<!-- graft:start -->\nfence\n<!-- graft:end -->\n"
            )
        (project / "AGENTS.md").write_text(agents)
        vault = base / "vault"
        vault.mkdir(mode=0o700)
        return project

    def _prepare(self, project: Path):
        try:
            return prepare_trellis_uninstall(project)
        except contracts.ContractError as error:
            if error.code in (
                "tool-unavailable",
                "tool-binding",
                "tool-version-unsupported",
            ):
                self.skipTest(f"installed vendor tool is not usable here: {error.code}")
            raise

    def test_real_vendor_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = self._fixture(base, orphan_hook=True)
            vault = base / "vault"
            prepared = self._prepare(project)
            payload = prepared["payload"]
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["tool"]["package_version"], SUPPORTED_VERSION)
            self.assertTrue(payload["evidence"]["dry_run"]["matches_planner"])
            self.assertEqual(
                [(r["kind"], r["relative"]) for r in payload["resources"]],
                [
                    ("vendor-delete", ".claude/settings.json"),
                    ("vendor-scrub", "AGENTS.md"),
                    ("vendor-trellis-dir", ".trellis"),
                ],
            )
            self.assertEqual(payload["pruned_keys"], [".claude/hooks/x.py"])
            outcome = execute_trellis_uninstall(project, prepared, vault)
            self.assertEqual(outcome["status"], "removed")
            self.assertEqual(outcome["exit"], 0)
            self.assertEqual(
                outcome["command"], [payload["tool"]["path"], "uninstall", "-y"]
            )
            self.assertFalse(Path(payload["tool"]["path"]).is_symlink())
            self.assertFalse((project / ".trellis").exists())
            self.assertFalse((project / ".claude/settings.json").exists())
            self.assertEqual(
                (project / "AGENTS.md").read_text(),
                "# mine\n\n<!-- graft:start -->\nfence\n<!-- graft:end -->\n",
            )
            self.assertTrue(
                (project / ".claude/hooks/x.py").is_file(),
                "orphan user hook must survive the vendor uninstall",
            )
            tree_backup = Path(outcome["results"][2]["backup_ref"]["path"])
            self.assertTrue((tree_backup / "workspace/dev01/notes.md").is_file())
            evidence = json.loads(Path(outcome["evidence_ref"]["path"]).read_text())
            self.assertEqual(evidence["exit"], 0)
            self.assertIn("Uninstalled trellis", evidence["stdout"])

    def test_real_vendor_prunes_empty_managed_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = self._fixture(base, orphan_hook=False)
            vault = base / "vault"
            prepared = self._prepare(project)
            payload = prepared["payload"]
            kinds = [(r["kind"], r["relative"]) for r in payload["resources"]]
            self.assertIn(("vendor-prune-dir", ".claude"), kinds)
            outcome = execute_trellis_uninstall(project, prepared, vault)
            self.assertEqual(outcome["status"], "removed")
            self.assertFalse((project / ".claude").exists())

    def test_real_vendor_dry_run_omits_empty_modified_section(self) -> None:
        """tl 0.6.17 prints no "Will be modified" section when nothing is scrubbed."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = self._fixture(base, orphan_hook=False, managed_agents=False)
            vault = base / "vault"
            prepared = self._prepare(project)
            payload = prepared["payload"]
            self.assertEqual(payload["status"], "ready")
            evidence = payload["evidence"]["dry_run"]
            self.assertEqual(evidence["modified_files"], 0)
            self.assertTrue(evidence["matches_planner"])
            self.assertNotIn(
                "vendor-scrub",
                [r["kind"] for r in payload["resources"]],
            )
            outcome = execute_trellis_uninstall(project, prepared, vault)
            self.assertEqual(outcome["status"], "removed")
            self.assertFalse((project / ".trellis").exists())
            self.assertEqual(
                (project / "AGENTS.md").read_text(),
                "# mine\n<!-- graft:start -->\nfence\n<!-- graft:end -->\n",
            )

    def test_real_prepare_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = self._fixture(base, orphan_hook=True)
            before, _ = directory_snapshot(project)
            prepared = self._prepare(project)
            after, _ = directory_snapshot(project)
            self.assertEqual(before, after, "prepare must not persist manifest pruning")
            self.assertEqual(prepared["payload"]["status"], "ready")


if __name__ == "__main__":
    unittest.main()
