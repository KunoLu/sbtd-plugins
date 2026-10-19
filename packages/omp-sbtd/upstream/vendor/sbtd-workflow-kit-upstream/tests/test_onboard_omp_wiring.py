from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

PACKAGE = (Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard").resolve()
sys.path.insert(0, str(PACKAGE / "scripts"))

from onboard_contracts import ContractError
from sbtd_graft_deployment import execute_normal_wiring, plan_normal_wiring

from tests.test_sbtd_migration_apply import file_contents, legacy_project


class OmpNormalWiringTests(unittest.TestCase):
    def test_unavailable_runtime_is_readonly_and_never_creates_omp_state(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = legacy_project(base, "project")
            home = base / "home"
            home.mkdir()
            args = Namespace(
                projects_root=str(root),
                platform="omp",
                graft_hooks=False,
                global_skills_dir=str(home / ".agent/skills"),
            )
            before = file_contents(base)
            with (
                mock.patch.dict(
                    os.environ,
                    {
                        "HOME": str(home),
                        "USERPROFILE": str(home),
                        "CODEX_HOME": str(home / ".codex"),
                    },
                ),
                mock.patch(
                    "sbtd_graft_deployment.verified_runtime",
                    side_effect=ContractError("runtime-unavailable", "missing"),
                ),
            ):
                plan = plan_normal_wiring("init", args)
            self.assertEqual(plan["status"], "not-available")
            self.assertEqual(file_contents(base), before)

    def test_normal_plan_uses_template_only_when_project_agents_will_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = legacy_project(base, "project")
            home = base / "home"
            home.mkdir()
            (root / "AGENTS.md").write_bytes(b"\xff<!-- graft:start -->broken")
            runtime = {
                "node": "/fixture/node",
                "cli": "/fixture/cli.js",
                "python": "/fixture/python",
            }
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(home / ".codex"),
                "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
            }

            def plan(skip_project_agents, mode="init"):
                args = Namespace(
                    projects_root=str(root),
                    platform="omp",
                    graft_hooks=False,
                    global_skills_dir=str(home / ".agent/skills"),
                    skip_project_agents=skip_project_agents,
                )
                with (
                    mock.patch.dict(os.environ, environment),
                    mock.patch(
                        "sbtd_graft_deployment.verified_runtime", return_value=runtime
                    ),
                ):
                    return plan_normal_wiring(mode, args)

            self.assertEqual(plan(False)["status"], "planned")
            self.assertEqual(plan(True)["status"], "blocked")
            self.assertEqual(plan(False, "check")["status"], "planned")
            self.assertEqual(plan(True, "check")["status"], "blocked")
            self.assertEqual((root / "AGENTS.md").read_bytes(), b"\xff<!-- graft:start -->broken")


    def test_planned_omp_wiring_writes_active_config_without_hooks(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = legacy_project(base, "project")
            home = base / "home"
            installed = home / ".agent/skills/sbtd-workflow-onboard"
            home.mkdir()
            shutil.copytree(PACKAGE, installed)
            args = Namespace(
                projects_root=str(root),
                platform="omp",
                graft_hooks=False,
                global_skills_dir=str(home / ".agent/skills"),
            )
            runtime = {
                "node": "/fixture/node",
                "cli": "/fixture/cli.js",
                "python": "/fixture/python",
            }
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(home / ".codex"),
                "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
            }
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch(
                    "sbtd_graft_deployment.verified_runtime", return_value=runtime
                ),
            ):
                plan = plan_normal_wiring("init", args)
            self.assertEqual(plan["status"], "planned", plan)
            self.assertIsNone(plan["codexHome"])
            self.assertEqual(plan["ompHome"], str(home / ".omp/agent"))
            self.assertFalse((home / ".omp").exists())

            def graph(project, _runtime):
                (project / "graft").mkdir()
                (project / "graft/fixture").write_bytes(b"synthetic native output")

            with (
                mock.patch.dict(os.environ, environment),
                mock.patch(
                    "sbtd_graft_deployment.build_project_graph", side_effect=graph
                ),
            ):
                result, code = execute_normal_wiring(plan, template_written=False)
            self.assertEqual(code, 0, result)
            self.assertEqual(result["status"], "success")
            target = home / ".omp/agent/mcp.json"
            servers = json.loads(target.read_text(encoding="utf-8"))["mcpServers"]
            self.assertEqual(len(servers), 1)
            server = next(iter(servers.values()))
            self.assertEqual(server["command"], runtime["python"])
            self.assertNotIn("cwd", server)
            self.assertNotIn("--root", server["args"])
            self.assertFalse((home / ".codex/hooks.json").exists())
            self.assertEqual(result["hooks"], "not-installed")

    def test_global_only_install_preserves_foreign_config_and_repeats_without_changes(self):
        """GM-01/06: no project is required to install the shared connection."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            installed = home / ".agent/skills/sbtd-workflow-onboard"
            shutil.copytree(PACKAGE, installed)
            target = home / ".omp/agent/mcp.json"
            target.parent.mkdir(parents=True)
            foreign = {"command": "/foreign/server", "args": ["keep"]}
            target.write_text(json.dumps({"mcpServers": {"foreign": foreign}}))
            args = Namespace(
                projects_root=None,
                platform="omp",
                graft_hooks=False,
                global_skills_dir=str(installed.parent),
            )
            runtime = {
                "node": "/fixture/node",
                "cli": "/fixture/cli.js",
                "python": "/fixture/python",
            }
            with (
                mock.patch.dict(os.environ, {
                    "HOME": str(home),
                    "USERPROFILE": str(home),
                    "CODEX_HOME": str(home / ".codex"),
                    "AGENT_SKILLS_DIR": str(installed.parent),
                }),
                mock.patch("sbtd_graft_deployment.verified_runtime", return_value=runtime),
            ):
                plan = plan_normal_wiring("init", args)
                self.assertEqual(plan["status"], "planned", plan)
                self.assertEqual(plan["privateOperations"], {})
                result, code = execute_normal_wiring(plan, template_written=False)
                self.assertEqual(code, 0, result)
                self.assertEqual(result["projects"], [])
                servers = json.loads(target.read_bytes())["mcpServers"]
                self.assertEqual(set(servers), {"foreign", "sbtd-graft"})
                self.assertEqual(servers["foreign"], foreign)
                self.assertNotIn("cwd", servers["sbtd-graft"])
                self.assertNotIn("--root", servers["sbtd-graft"]["args"])
                before = target.read_bytes()
                second = plan_normal_wiring("init", args)
                result, code = execute_normal_wiring(second, template_written=False)
                self.assertEqual(code, 0, result)
                self.assertEqual(target.read_bytes(), before)
                self.assertFalse((home / "graft").exists())

    def test_global_only_failed_write_does_not_report_empty_project_success(self):
        """GM-01/07: a shared-resource failure is failure even with zero roots."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            installed = base / ".agent/skills/sbtd-workflow-onboard"
            shutil.copytree(PACKAGE, installed)
            args = Namespace(
                projects_root=None, platform="codex", graft_hooks=False,
                global_skills_dir=str(installed.parent),
            )
            runtime = {
                "node": "/fixture/node", "cli": "/fixture/cli.js",
                "python": "/fixture/python",
            }
            with (
                mock.patch.dict(os.environ, {
                    "HOME": str(base), "USERPROFILE": str(base),
                    "CODEX_HOME": str(base / ".codex"),
                }),
                mock.patch("sbtd_graft_deployment.verified_runtime", return_value=runtime),
            ):
                plan = plan_normal_wiring("init", args)
                self.assertEqual(plan["status"], "planned", plan)
                with mock.patch("sbtd_graft_deployment.write_file", side_effect=OSError("full disk")):
                    result, code = execute_normal_wiring(plan, template_written=False)
                self.assertEqual(code, 5, result)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["operationResults"][0]["status"], "failed")
                self.assertFalse((base / ".codex/config.toml").exists())

    def test_explicit_old_runtime_contract_preserves_original_and_rejects_drift(self):
        """GM-07/08: observed old paths authorize only a bounded config cutover."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            project = legacy_project(base, "project")
            installed = home / ".agent/skills/sbtd-workflow-onboard"
            shutil.copytree(PACKAGE, installed)
            target = home / ".omp/agent/mcp.json"
            target.parent.mkdir(parents=True)
            old = {
                "root": str(project), "python": str(base / "old/python"),
                "node": str(base / "old/node"), "cli": str(base / "old/dist/cli.js"),
                "launcher": str(base / "old/scripts/sbtd_graft_entry.py"),
            }
            name = "sbtd-graft-" + hashlib.sha256(str(project).encode()).hexdigest()[:16]
            foreign = {"command": "/foreign/server", "args": ["keep"]}
            target.write_text(json.dumps({"mcpServers": {
                name: {
                    "type": "stdio", "command": old["python"],
                    "args": ["-E", "-s", old["launcher"], "mcp", "--root", str(project),
                             "--node", old["node"], "--entry", old["cli"]],
                    "cwd": str(project), "env": {"DO_NOT_TRACK": "1", "DNT": "1"},
                },
                "foreign": foreign,
            }}))
            original = target.read_bytes()
            contract_dir = base / "private"
            contract_dir.mkdir(mode=0o700)
            contract = contract_dir / "old-bindings.json"
            contract.write_text(json.dumps({"schema_version": 1, "bindings": [old]}))
            args = Namespace(
                projects_root=str(project), platform="omp", graft_hooks=False,
                global_skills_dir=str(installed.parent), skip_project_agents=True,
                graft_retire_legacy=True, graft_legacy_bindings=None,
            )
            runtime = {
                "node": "/fixture/node", "cli": "/fixture/cli.js",
                "python": "/fixture/python",
            }
            with (
                mock.patch.dict(os.environ, {
                    "HOME": str(home), "USERPROFILE": str(home),
                    "CODEX_HOME": str(home / ".codex"),
                    "AGENT_SKILLS_DIR": str(installed.parent),
                }),
                mock.patch("sbtd_graft_deployment.verified_runtime", return_value=runtime),
            ):
                self.assertEqual(plan_normal_wiring("init", args)["status"], "blocked")
                self.assertEqual(target.read_bytes(), original)
                args.graft_legacy_bindings = str(contract)
                plan = plan_normal_wiring("init", args)
                self.assertEqual(plan["status"], "planned", plan)
                saved_contract = contract.read_bytes()
                contract.write_bytes(saved_contract + b"\n")
                before = file_contents(base)
                result, code = execute_normal_wiring(plan, template_written=False)
                self.assertEqual(code, 2, result)
                self.assertEqual(result["operationResults"], [])
                self.assertEqual(file_contents(base), before)
                contract.write_bytes(saved_contract)
                def graph(root, _runtime):
                    (root / "graft").mkdir()
                with mock.patch("sbtd_graft_deployment.build_project_graph", side_effect=graph):
                    result, code = execute_normal_wiring(plan, template_written=False)
                self.assertEqual(code, 0, result)
                servers = json.loads(target.read_bytes())["mcpServers"]
                self.assertEqual(set(servers), {"foreign", "sbtd-graft"})
                self.assertEqual(servers["foreign"], foreign)
                backup = result["operationResults"][-1]["backup_ref"]
                self.assertEqual(Path(backup["path"]).read_bytes(), original)
                # Scoped restore is possible without touching unrelated resources.
                from sbtd_migration_files import snapshot, write_file
                write_file(target, Path(backup["path"]).read_bytes(), snapshot(target), scope=target.parent)
                self.assertEqual(target.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
