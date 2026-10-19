# ruff: noqa: I001 -- local scripts require the explicit test path before import.
from __future__ import annotations
import json

import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "sbtd-workflow-onboard/scripts"
sys.path.insert(0, str(SCRIPTS))

from onboard_contracts import ContractError
from sbtd_graft_deployment import (
    _validate_selected_root_batch,
    execute_normal_wiring,
    plan_normal_wiring,
)
from sbtd_migration_files import snapshot

PACKAGE = (ROOT / "sbtd-workflow-onboard").resolve()


def _git_env(home: Path) -> dict[str, str]:
    return {
        **os.environ,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
    }


def _git(root: Path, *args: str, home: Path) -> None:
    # Fixture commits must not leave detached maintenance writers racing the
    # subsequent whole-tree no-mutation assertions.
    subprocess.run(
        ["git", "-c", "maintenance.auto=false", "-C", str(root), *args],
        check=True,
        capture_output=True,
        env=_git_env(home),
        text=True,
    )


def _git_repo(path: Path, branch: str, home: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(
        ["git", "-c", "maintenance.auto=false", "init", "-b", branch, str(path)],
        check=True,
        capture_output=True,
        env=_git_env(home),
        text=True,
    )
    _git(path, "config", "user.email", "fixture@test", home=home)
    _git(path, "config", "user.name", "fixture", home=home)
    (path / "app.py").write_text(f"VALUE = {branch!r}\n", encoding="utf-8")
    _git(path, "add", "app.py", home=home)
    _git(path, "commit", "-m", f"initial {branch}", home=home)
    return path


def _args(roots: list[Path], skills: Path) -> Namespace:
    return Namespace(
        projects_root=",".join(str(root) for root in roots),
        platform="codex",
        graft_hooks=False,
        global_skills_dir=str(skills),
    )


class GraftIsolationTests(unittest.TestCase):
    def test_same_physical_root_aliases_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            first, alias = base / "first", base / "alias"
            first.mkdir()
            alias.symlink_to(first, target_is_directory=True)
            with self.assertRaises(ContractError) as failure:
                _validate_selected_root_batch([first, alias])
            self.assertEqual(failure.exception.code, "scope-conflict")

    def test_nested_selected_repository_roots_block_before_runtime_wiring(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            parent = _git_repo(base / "parent", "main", home)
            child = _git_repo(parent / "child", "child", home)
            before = snapshot(base)
            args = _args([parent, child], home / ".agent/skills")
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(home / ".codex"),
            }
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch(
                    "sbtd_graft_deployment.verified_runtime",
                    side_effect=AssertionError("runtime probe must not run first"),
                ),
            ):
                plan = plan_normal_wiring("init", args)
            self.assertEqual(plan["status"], "blocked")
            self.assertIn("overlap", plan["reason"])
            self.assertEqual(snapshot(base), before)

    def test_two_roots_build_only_selected_repos_and_leave_sibling_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            workspace = base / "workspace"
            alpha = _git_repo(workspace / "alpha", "main", home)
            beta = _git_repo(workspace / "beta", "feature-beta", home)
            sibling = _git_repo(workspace / "sibling", "sibling", home)
            skills = home / ".agent/skills"
            installed = skills / "sbtd-workflow-onboard"
            home.mkdir(exist_ok=True)
            shutil.copytree(PACKAGE, installed)
            args = _args([alpha, beta], skills)
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(home / ".codex"),
                "AGENT_SKILLS_DIR": str(skills),
            }
            runtime = {
                "node": "/fixture/node",
                "cli": "/fixture/cli.js",
                "python": "/fixture/python",
            }
            built: list[Path] = []

            def build(root: Path, _runtime):
                built.append(root)
                (root / "graft").mkdir(exist_ok=True)
                (root / "graft/marker.txt").write_text(
                    root.name + "\n", encoding="utf-8"
                )

            before_workspace = snapshot(workspace)
            before_sibling = snapshot(sibling)
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch(
                    "sbtd_graft_deployment.verified_runtime", return_value=runtime
                ),
            ):
                plan = plan_normal_wiring("init", args)
            self.assertEqual(plan["status"], "planned", plan)
            self.assertEqual(snapshot(workspace), before_workspace)
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch(
                    "sbtd_graft_deployment.build_project_graph", side_effect=build
                ),
            ):
                result, code = execute_normal_wiring(plan, template_written=False)
            self.assertEqual(code, 0, result)
            self.assertEqual(built, [alpha, beta])
            self.assertEqual(snapshot(sibling), before_sibling)
            self.assertFalse((workspace / "graft").exists())
            self.assertFalse((workspace / ".graft").exists())
            config = tomllib.loads(
                (home / ".codex/config.toml").read_text(encoding="utf-8")
            )
            servers = config["mcp_servers"]
            self.assertEqual(set(servers), {"sbtd-graft"})
            self.assertNotIn("cwd", servers["sbtd-graft"])
            self.assertNotIn("--root", servers["sbtd-graft"]["args"])

    def test_linked_worktrees_on_different_branches_are_distinct_selected_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            main = _git_repo(base / "main", "main", home)
            linked = base / "linked"
            subprocess.run(
                ["git", "-C", str(main), "worktree", "add", "-b", "feature", str(linked)],
                check=True,
                capture_output=True,
                env=_git_env(home),
                text=True,
            )
            (linked / "app.py").write_text("VALUE = 'feature'\n", encoding="utf-8")
            _git(linked, "add", "app.py", home=home)
            _git(linked, "commit", "-m", "feature worktree", home=home)
            branches = {
                subprocess.run(
                    ["git", "-C", str(path), "branch", "--show-current"],
                    check=True,
                    capture_output=True,
                    env=_git_env(home),
                    text=True,
                ).stdout.strip()
                for path in (main, linked)
            }
            self.assertEqual(branches, {"main", "feature"})
            skills = home / ".agent/skills"
            installed = skills / "sbtd-workflow-onboard"
            shutil.copytree(PACKAGE, installed)
            args = _args([main, linked], skills)
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(home / ".codex"),
                "AGENT_SKILLS_DIR": str(skills),
            }
            runtime = {
                "node": "/fixture/node",
                "cli": "/fixture/cli.js",
                "python": "/fixture/python",
            }
            built: list[Path] = []

            def build(root: Path, _runtime):
                built.append(root)
                (root / "graft").mkdir(exist_ok=True)

            with (
                mock.patch.dict(os.environ, environment),
                mock.patch(
                    "sbtd_graft_deployment.verified_runtime", return_value=runtime
                ),
            ):
                plan = plan_normal_wiring("init", args)
            self.assertEqual(plan["status"], "planned", plan)
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch(
                    "sbtd_graft_deployment.build_project_graph", side_effect=build
                ),
            ):
                result, code = execute_normal_wiring(plan, template_written=False)
            self.assertEqual(code, 0, result)
            self.assertEqual(built, [main, linked])
            config = tomllib.loads(
                (home / ".codex/config.toml").read_text(encoding="utf-8")
            )
            self.assertEqual(set(config["mcp_servers"]), {"sbtd-graft"})
            self.assertNotIn("cwd", config["mcp_servers"]["sbtd-graft"])
            self.assertNotIn("--root", config["mcp_servers"]["sbtd-graft"]["args"])

    def test_omp_two_roots_share_one_session_scoped_definition(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            workspace = base / "workspace"
            alpha = _git_repo(workspace / "alpha", "main", home)
            beta = _git_repo(workspace / "beta", "feature-beta", home)
            skills = home / ".agent/skills"
            installed = skills / "sbtd-workflow-onboard"
            home.mkdir(exist_ok=True)
            shutil.copytree(PACKAGE, installed)
            args = _args([alpha, beta], skills)
            args.platform = "omp"
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(home / ".codex"),
                "AGENT_SKILLS_DIR": str(skills),
            }
            runtime = {
                "node": "/fixture/node",
                "cli": "/fixture/cli.js",
                "python": "/fixture/python",
            }

            def build(root: Path, _runtime):
                (root / "graft").mkdir(exist_ok=True)

            with (
                mock.patch.dict(os.environ, environment),
                mock.patch(
                    "sbtd_graft_deployment.verified_runtime", return_value=runtime
                ),
            ):
                plan = plan_normal_wiring("init", args)
            self.assertEqual(plan["status"], "planned", plan)
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch(
                    "sbtd_graft_deployment.build_project_graph", side_effect=build
                ),
            ):
                result, code = execute_normal_wiring(plan, template_written=False)
            self.assertEqual(code, 0, result)
            target = home / ".omp/agent/mcp.json"
            servers = json.loads(target.read_text(encoding="utf-8"))["mcpServers"]
            self.assertEqual(set(servers), {"sbtd-graft"})
            self.assertNotIn("cwd", servers["sbtd-graft"])
            self.assertNotIn("--root", servers["sbtd-graft"]["args"])


if __name__ == "__main__":
    unittest.main()
