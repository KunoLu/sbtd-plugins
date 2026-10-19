from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
ONBOARD = ROOT / "sbtd-workflow-onboard/scripts/onboard.py"


class OnboardDeveloperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="sbtd-developer-cli-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.project = self.root / "project"
        self.project.mkdir()
        self.home = self.root / "home"
        self.home.mkdir()
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "USERPROFILE": str(self.home),
            "CODEX_HOME": str(self.home / ".codex"),
            "XDG_CONFIG_HOME": str(self.home / "config"),
            "XDG_CACHE_HOME": str(self.home / "cache"),
            "XDG_DATA_HOME": str(self.home / "data"),
            "XDG_STATE_HOME": str(self.home / "state"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
        }
        subprocess.run(
            ["git", "init", "-b", "trunk", str(self.project)],
            env=self.env,
            capture_output=True,
            check=True,
        )

    def run_onboard(self, *arguments, cwd=None):
        return subprocess.run(
            [sys.executable, "-B", str(ONBOARD), *arguments],
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
            cwd=cwd,
        )

    def make_git_repo(self, name: str) -> Path:
        repo = self.root / name
        repo.mkdir()
        subprocess.run(
            ["git", "init", "-b", "trunk", str(repo)],
            env=self.env,
            capture_output=True,
            check=True,
        )
        return repo

    def git(self, repo: Path, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(repo), *arguments],
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
        )

    def write_identity(self, repo: Path, content: bytes) -> Path:
        sbtd = repo / ".sbtd"
        sbtd.mkdir(exist_ok=True)
        identity = sbtd / "developer"
        identity.write_bytes(content)
        return identity

    def initialize(self, repo: Path, name: str = "dev01") -> dict:
        result = self.run_onboard(
            "init-projects",
            "--projects-root",
            str(repo),
            "--developer",
            name,
            "--skip-project-agents",
            "--yes",
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_text_initialization_reports_created_identity_not_only_plan(self) -> None:
        completed = self.run_onboard(
            "init-projects",
            "--projects-root", str(self.project),
            "--developer", "dev01",
            "--skip-project-agents", "--yes",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            (self.project / ".sbtd/developer").read_text(encoding="utf-8"),
            "name=dev01\n",
        )
        final_identity = completed.stdout.rsplit("Developer identity:", 1)[-1]
        self.assertIn("status: created", final_identity)

    def test_explicit_project_initialization_creates_only_the_confirmed_name(
        self,
    ) -> None:
        planned = self.run_onboard(
            "plan",
            "--projects-root",
            str(self.project),
            "--developer",
            "dev01",
            "--json",
        )
        self.assertEqual(planned.returncode, 0, planned.stderr)
        json.loads(planned.stdout)
        self.assertFalse((self.project / ".sbtd").exists())
        initialized = self.run_onboard(
            "init-projects",
            "--projects-root",
            str(self.project),
            "--developer",
            "dev01",
            "--skip-project-agents",
            "--yes",
            "--json",
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        json.loads(initialized.stdout)
        self.assertEqual(
            (self.project / ".sbtd/developer").read_bytes(), b"name=dev01\n"
        )
        self.assertEqual(
            {path.name for path in (self.project / ".sbtd").iterdir()}, {"developer"}
        )
        self.assertEqual(list(self.home.rglob("developer")), [])

    def test_plan_lists_every_requested_project_and_writes_nothing(self) -> None:
        second = self.make_git_repo("second")
        planned = self.run_onboard(
            "plan",
            "--projects-root",
            f"{self.project},{second}",
            "--developer",
            "dev01",
            "--json",
        )
        self.assertEqual(planned.returncode, 0, planned.stderr)
        payload = json.loads(planned.stdout)
        plan = payload["developerPlan"]
        self.assertEqual(plan["requestedName"], "dev01")
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(
            [entry["projectRoot"] for entry in plan["projects"]],
            [str(self.project), str(second)],
        )
        for entry, repo in zip(plan["projects"], (self.project, second)):
            self.assertEqual(entry["status"], "planned")
            self.assertEqual(entry["requestedName"], "dev01")
            self.assertEqual(entry["target"], str(repo / ".sbtd" / "developer"))
            self.assertTrue(entry["needsProtection"])
            self.assertFalse((repo / ".sbtd").exists())
            self.assertFalse((repo / ".gitignore").exists())

    def test_check_with_developer_is_read_only(self) -> None:
        checked = self.run_onboard(
            "check",
            "--projects-root",
            str(self.project),
            "--developer",
            "dev01",
            "--json",
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)
        plan = json.loads(checked.stdout)["developerPlan"]
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["projects"][0]["projectRoot"], str(self.project))
        self.assertFalse((self.project / ".sbtd").exists())
        self.assertEqual(list(self.home.rglob("developer")), [])

    def test_developer_without_projects_root_is_rejected(self) -> None:
        for mode in ("check", "plan"):
            with self.subTest(mode=mode):
                result = self.run_onboard(
                    mode, "--developer", "dev01", "--json", cwd=self.project
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                plan = json.loads(result.stdout)["developerPlan"]
                self.assertEqual(plan["status"], "blocked")
                self.assertEqual(plan["projects"], [])
        initialized = self.run_onboard(
            "init", "--developer", "dev01", "--yes", "--json", cwd=self.project
        )
        self.assertEqual(initialized.returncode, 2, initialized.stderr)
        plan = json.loads(initialized.stdout)["developerPlan"]
        self.assertEqual(plan["status"], "blocked")
        # The rejected run must not fall back to the cwd or HOME.
        self.assertFalse((self.project / ".sbtd").exists())
        self.assertFalse((self.home / ".codex" / "AGENTS.md").exists())
        self.assertEqual(list(self.home.rglob("developer")), [])

    def test_invalid_or_repeated_developer_name_is_rejected_by_parser(self) -> None:
        invalid = self.run_onboard(
            "plan",
            "--projects-root",
            str(self.project),
            "--developer",
            "Dev-01",
            "--json",
        )
        self.assertEqual(invalid.returncode, 2)
        self.assertEqual(invalid.stdout, "")
        repeated = self.run_onboard(
            "plan",
            "--projects-root",
            str(self.project),
            "--developer",
            "dev01",
            "--developer",
            "dev02",
            "--json",
        )
        self.assertEqual(repeated.returncode, 2)
        self.assertEqual(repeated.stdout, "")
        self.assertFalse((self.project / ".sbtd").exists())

    def test_conflicting_identity_blocks_before_any_write(self) -> None:
        identity = self.write_identity(self.project, b"name=other\n")
        result = self.run_onboard(
            "init-projects",
            "--projects-root",
            str(self.project),
            "--developer",
            "dev01",
            "--skip-project-agents",
            "--yes",
            "--json",
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        plan = json.loads(result.stdout)["developerPlan"]
        self.assertEqual(plan["status"], "conflict")
        self.assertEqual(plan["projects"][0]["status"], "conflict")
        self.assertEqual(identity.read_bytes(), b"name=other\n")
        self.assertFalse((self.project / ".gitignore").exists())
        self.assertEqual(
            {path.name for path in (self.project / ".sbtd").iterdir()}, {"developer"}
        )

    def test_batch_preflight_blocks_all_projects_before_first_write(self) -> None:
        second = self.make_git_repo("second")
        identity = self.write_identity(second, b"name=other\n")
        result = self.run_onboard(
            "init-projects",
            "--projects-root",
            f"{self.project},{second}",
            "--developer",
            "dev01",
            "--skip-project-agents",
            "--yes",
            "--json",
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        plan = json.loads(result.stdout)["developerPlan"]
        self.assertEqual(plan["status"], "conflict")
        self.assertEqual(
            [entry["status"] for entry in plan["projects"]], ["planned", "conflict"]
        )
        # The clean first project must not be scaffolded before the conflict
        # in the second project is reported.
        self.assertFalse((self.project / ".gitignore").exists())
        self.assertFalse((self.project / ".sbtd").exists())
        self.assertEqual(identity.read_bytes(), b"name=other\n")

    def test_same_name_initialization_is_idempotent(self) -> None:
        first = self.initialize(self.project)
        self.assertEqual(first["developerPlan"]["projects"][0]["status"], "created")
        again = self.initialize(self.project)
        entry = again["developerPlan"]["projects"][0]
        self.assertEqual(entry["status"], "unchanged")
        self.assertEqual(entry["source"], "local")
        self.assertEqual(
            (self.project / ".sbtd/developer").read_bytes(), b"name=dev01\n"
        )

    def test_linked_worktree_inherits_main_identity_without_local_copy(self) -> None:
        main = self.make_git_repo("mainrepo")
        self.git(
            main,
            "-c",
            "user.name=test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "--allow-empty",
            "-m",
            "init",
        )
        self.initialize(main)
        linked = self.root / "linked"
        self.git(main, "worktree", "add", "-b", "linked", str(linked))

        planned = self.run_onboard(
            "plan", "--projects-root", str(linked), "--developer", "dev01", "--json"
        )
        self.assertEqual(planned.returncode, 0, planned.stderr)
        entry = json.loads(planned.stdout)["developerPlan"]["projects"][0]
        self.assertEqual(entry["status"], "unchanged")
        self.assertEqual(entry["source"], "main-worktree")
        self.assertEqual(entry["name"], "dev01")
        self.assertEqual(
            Path(entry["target"]).resolve(), (main / ".sbtd" / "developer").resolve()
        )

        initialized = self.run_onboard(
            "init-projects",
            "--projects-root",
            str(linked),
            "--developer",
            "dev01",
            "--skip-project-agents",
            "--yes",
            "--json",
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        entry = json.loads(initialized.stdout)["developerPlan"]["projects"][0]
        self.assertEqual(entry["status"], "unchanged")
        self.assertFalse((linked / ".sbtd").exists())
        self.assertEqual((main / ".sbtd/developer").read_bytes(), b"name=dev01\n")

    def test_reset_preserves_identity_and_rejects_conflicting_name(self) -> None:
        self.initialize(self.project)
        identity = self.project / ".sbtd/developer"
        global_scope = (
            "--global-skills-dir",
            str(self.root / "global-skills"),
            "--global-agents-path",
            str(self.root / "global-AGENTS.md"),
        )

        plain = self.run_onboard(
            "reset",
            "--projects-root",
            str(self.project),
            "--skip-project-agents",
            *global_scope,
            "--yes",
            "--json",
        )
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertNotIn("developerPlan", json.loads(plain.stdout))
        self.assertEqual(identity.read_bytes(), b"name=dev01\n")
        self.assertEqual(
            {path.name for path in (self.project / ".sbtd").iterdir()}, {"developer"}
        )

        same = self.run_onboard(
            "reset",
            "--projects-root",
            str(self.project),
            "--developer",
            "dev01",
            "--skip-project-agents",
            *global_scope,
            "--yes",
            "--json",
        )
        self.assertEqual(same.returncode, 0, same.stderr)
        self.assertEqual(
            json.loads(same.stdout)["developerPlan"]["projects"][0]["status"],
            "unchanged",
        )
        self.assertEqual(identity.read_bytes(), b"name=dev01\n")

        conflicted = self.run_onboard(
            "reset",
            "--projects-root",
            str(self.project),
            "--developer",
            "other",
            "--skip-project-agents",
            *global_scope,
            "--yes",
            "--json",
        )
        self.assertEqual(conflicted.returncode, 2, conflicted.stderr)
        self.assertEqual(
            json.loads(conflicted.stdout)["developerPlan"]["status"], "conflict"
        )
        self.assertEqual(identity.read_bytes(), b"name=dev01\n")

    def test_malformed_or_symlinked_identity_is_a_conflict(self) -> None:
        identity = self.write_identity(self.project, b"name=Not-A-Name!\n")
        malformed = self.run_onboard(
            "plan",
            "--projects-root",
            str(self.project),
            "--developer",
            "dev01",
            "--json",
        )
        self.assertEqual(malformed.returncode, 2, malformed.stderr)
        self.assertEqual(
            json.loads(malformed.stdout)["developerPlan"]["status"], "conflict"
        )

        identity.unlink()
        identity.symlink_to(self.root / "elsewhere")
        linked = self.run_onboard(
            "plan",
            "--projects-root",
            str(self.project),
            "--developer",
            "dev01",
            "--json",
        )
        self.assertEqual(linked.returncode, 2, linked.stderr)
        self.assertEqual(
            json.loads(linked.stdout)["developerPlan"]["status"], "conflict"
        )
        self.assertTrue(identity.is_symlink())

    def test_non_git_initialization_uses_only_the_planned_protection_authorization(
        self,
    ) -> None:
        plain = self.root / "plain"
        plain.mkdir()
        planned = self.run_onboard(
            "plan", "--projects-root", str(plain), "--developer", "dev01", "--json"
        )
        self.assertEqual(planned.returncode, 0, planned.stderr)
        entry = json.loads(planned.stdout)["developerPlan"]["projects"][0]
        self.assertEqual(entry["status"], "planned")
        self.assertEqual(entry["topology"], "non-git")
        self.assertTrue(entry["needsProtection"])
        self.assertFalse((plain / ".gitignore").exists())
        self.assertFalse((plain / ".sbtd").exists())

        initialized = self.run_onboard(
            "init-projects",
            "--projects-root",
            str(plain),
            "--developer",
            "dev01",
            "--skip-project-agents",
            "--yes",
            "--json",
        )
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        plan = json.loads(initialized.stdout)["developerPlan"]
        self.assertEqual(plan["status"], "created")
        self.assertEqual((plain / ".sbtd/developer").read_bytes(), b"name=dev01\n")
        self.assertIn("/.sbtd/", (plain / ".gitignore").read_text().splitlines())
        self.assertFalse((plain / ".git").exists())

    def test_new_protection_need_after_plan_is_not_silently_authorized(self) -> None:
        sys.path.insert(0, str(ONBOARD.parent))
        import onboard

        ignore = self.project / ".gitignore"
        ignore.write_bytes(b"/.sbtd/\n")
        args = onboard.build_parser().parse_args(
            ["plan", "--projects-root", str(self.project), "--developer", "dev01"]
        )
        planned = onboard.build_developer_plan(args)
        assert planned is not None
        projects = planned["projects"]
        assert isinstance(projects, list)
        self.assertFalse(projects[0]["needsProtection"])
        ignore.write_bytes(b"# User changed protection after planning.\n")
        result = onboard.ensure_developer_identities(planned)
        self.assertEqual(result["status"], "needs-protection")
        self.assertEqual(
            ignore.read_bytes(), b"# User changed protection after planning.\n"
        )
        self.assertFalse((self.project / ".sbtd").exists())

    def test_failed_identity_write_reports_the_completed_scaffold_in_one_json(
        self,
    ) -> None:
        sys.path.insert(0, str(ONBOARD.parent))
        import onboard

        args = onboard.build_parser().parse_args(
            [
                "init-projects",
                "--projects-root",
                str(self.project),
                "--developer",
                "dev01",
                "--yes",
                "--json",
            ]
        )
        stdout, stderr = io.StringIO(), io.StringIO()
        real_link = os.link

        def refuse_identity(source, target, *positional, **keywords):
            if Path(target) == self.project / ".sbtd/developer":
                raise PermissionError("synthetic identity write failure")
            return real_link(source, target, *positional, **keywords)

        with (
            mock.patch.dict(os.environ, self.env),
            mock.patch("sbtd_task_state.os.link", side_effect=refuse_identity),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            exit_code = onboard.run(args.mode, args)
        self.assertEqual(exit_code, 5, stderr.getvalue())
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["developerPlan"]["status"], "failed")
        self.assertTrue((self.project / "AGENTS.md").is_file())
        self.assertTrue((self.project / ".gitignore").is_file())
        self.assertFalse((self.project / ".sbtd/developer").exists())
        results = {entry["target"]: entry for entry in payload["operationResults"]}
        for target in ("AGENTS.md", ".gitignore"):
            self.assertNotEqual(results[str(self.project / target)]["status"], "failed")
        self.assertEqual(
            payload["sbtdProjectSetup"]["projects"][0]["projectRoot"], str(self.project)
        )

    def test_root_disappearance_during_preflight_returns_a_blocked_entry(self) -> None:
        sys.path.insert(0, str(ONBOARD.parent))
        import onboard

        args = onboard.build_parser().parse_args(
            ["plan", "--projects-root", str(self.project), "--developer", "dev01"]
        )
        real_resolve = Path.resolve
        retained = self.root / "retained-project"

        def disappear_before_strict_resolution(path, *positional, **keywords):
            if (
                path == self.project
                and keywords.get("strict") is True
                and path.exists()
            ):
                path.rename(retained)
            return real_resolve(path, *positional, **keywords)

        with mock.patch.object(
            Path,
            "resolve",
            autospec=True,
            side_effect=disappear_before_strict_resolution,
        ):
            result = onboard.build_developer_plan(args)
        assert result is not None
        self.assertEqual(result["status"], "blocked")
        self.assertFalse((retained / ".sbtd").exists())

    def test_post_plan_missing_root_keeps_prior_success_in_the_batch_result(
        self,
    ) -> None:
        sys.path.insert(0, str(ONBOARD.parent))
        import onboard

        second = self.root / "second-project"
        second.mkdir()
        subprocess.run(
            ["git", "init", "-b", "topic", str(second)],
            env=self.env,
            capture_output=True,
            check=True,
        )
        for root in (self.project, second):
            (root / ".gitignore").write_bytes(b"/.sbtd/\n")
        args = onboard.build_parser().parse_args(
            [
                "plan",
                "--projects-root",
                f"{self.project},{second}",
                "--developer",
                "dev01",
            ]
        )
        planned = onboard.build_developer_plan(args)
        assert planned is not None
        second.rename(self.root / "retained-second")
        result = onboard.ensure_developer_identities(planned)
        self.assertEqual(result["status"], "failed")
        projects = result["projects"]
        assert isinstance(projects, list)
        self.assertEqual([item["status"] for item in projects], ["created", "failed"])
        self.assertEqual(
            (self.project / ".sbtd/developer").read_bytes(), b"name=dev01\n"
        )
        self.assertFalse((self.root / "retained-second/.sbtd").exists())


if __name__ == "__main__":
    unittest.main()
