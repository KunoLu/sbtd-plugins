from __future__ import annotations

import json
import os
import stat
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ONBOARD = ROOT / "sbtd-workflow-onboard" / "scripts" / "onboard.py"


class MultiProjectOnboardCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="sbtd-multi-project-test-")
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.codex_home = self.home / ".codex"
        self.project_one = self.root / "project-one"
        self.project_two = self.root / "project-two"
        self.project_one.mkdir()
        self.project_two.mkdir()
        self.projects_csv = f"{self.project_one},{self.project_two}"
        self.env = os.environ.copy()
        self.env["HOME"] = str(self.home)
        self.env["CODEX_HOME"] = str(self.codex_home)

    def write_executable(self, name: str, body: str) -> Path:
        bin_dir = self.root / "bin"
        bin_dir.mkdir(exist_ok=True)
        target = bin_dir / name
        target.write_text(body, encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IXUSR)
        self.env["PATH"] = os.pathsep.join(
            (str(bin_dir), self.env.get("PATH", "/usr/bin:/bin"))
        )
        return target

    def run_onboard(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (sys.executable, str(ONBOARD), *args),
            check=False,
            capture_output=True,
            text=True,
            env=self.env,
            timeout=30,
        )

    def copy_onboard(self, name: str = "onboard-copy") -> Path:
        target = self.root / name
        shutil.copytree(ROOT / "sbtd-workflow-onboard", target)
        return target / "scripts" / "onboard.py"

    def run_onboard_script(
        self, script: Path, *args: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (sys.executable, str(script), *args),
            check=False,
            capture_output=True,
            text=True,
            env=self.env,
            timeout=30,
        )

    def rewrite_catalog_entry(
        self, script: Path, entry_id: str, field: str, value: object
    ) -> None:
        catalog_path = script.parents[1] / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        entry = next(item for item in catalog["entries"] if item["id"] == entry_id)
        if field == "repo":
            entry["source"]["repo"] = value
        else:
            entry[field] = value
        catalog_path.write_text(
            json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def test_plan_uses_installed_skill_parent_as_global_skills_dir(self) -> None:
        global_skills = self.home / ".agents" / "skills"
        skill_root = global_skills / "sbtd-workflow-onboard"
        shutil.copytree(ROOT / "sbtd-workflow-onboard", skill_root)
        script = skill_root / "scripts" / "onboard.py"
        self.env.pop("AGENT_SKILLS_DIR", None)

        completed = self.run_onboard_script(script, "plan", "--json")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["globalSkillsDir"], str(global_skills.resolve()))
        self.assertEqual(
            payload["globalSkillsDirSource"],
            "installed-skill-parent",
        )

    def test_plan_prefers_explicit_global_skills_dir(self) -> None:
        explicit = self.root / "explicit-global-skills"
        self.env["AGENT_SKILLS_DIR"] = str(self.root / "environment-global-skills")

        completed = self.run_onboard(
            "plan",
            "--global-skills-dir",
            str(explicit),
            "--json",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["globalSkillsDir"], str(explicit.resolve()))
        self.assertEqual(payload["globalSkillsDirSource"], "argument")

    def test_plan_prefers_environment_global_skills_dir(self) -> None:
        environment = self.root / "environment-global-skills"
        self.env["AGENT_SKILLS_DIR"] = str(environment)

        completed = self.run_onboard("plan", "--json")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["globalSkillsDir"], str(environment.resolve()))
        self.assertEqual(payload["globalSkillsDirSource"], "environment")

    def test_plan_uses_platform_default_outside_installed_skill_root(self) -> None:
        self.env.pop("AGENT_SKILLS_DIR", None)

        completed = self.run_onboard("plan", "--json")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(
            payload["globalSkillsDir"],
            str((self.codex_home / "skills").resolve()),
        )
        self.assertEqual(payload["globalSkillsDirSource"], "platform-default")

    def test_plan_rejects_regular_file_as_bundled_skill_source(self) -> None:
        script = self.copy_onboard()
        self.rewrite_catalog_entry(
            script,
            "skill:trellis-workflow",
            "source",
            "templates/project/.gitignore",
        )

        completed = self.run_onboard_script(script, "plan", "--json")

        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        self.assertIn("bundled-skill source must be a directory", completed.stderr)

    def test_plan_rejects_bundled_skill_frontmatter_name_mismatch(self) -> None:
        script = self.copy_onboard()
        self.rewrite_catalog_entry(
            script,
            "skill:trellis-workflow",
            "source",
            "templates/skills/trellis-channel",
        )

        completed = self.run_onboard_script(script, "plan", "--json")

        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        self.assertIn("frontmatter name", completed.stderr)

    def test_plan_rejects_absolute_local_catalog_source(self) -> None:
        script = self.copy_onboard()
        absolute_source = (
            script.parents[1] / "templates" / "skills" / "trellis-workflow"
        ).resolve()
        self.rewrite_catalog_entry(
            script,
            "skill:trellis-workflow",
            "source",
            str(absolute_source),
        )

        completed = self.run_onboard_script(script, "plan", "--json")

        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        self.assertIn("relative path", completed.stderr)

    def test_plan_rejects_malformed_external_repository_url(self) -> None:
        script = self.copy_onboard()
        self.rewrite_catalog_entry(
            script,
            "skill:diagnosing-bugs",
            "repo",
            "https://",
        )

        completed = self.run_onboard_script(script, "plan", "--json")

        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        self.assertIn("valid HTTPS repository URL", completed.stderr)

    def test_plan_rejects_kind_identity_and_target_role_mismatches(self) -> None:
        cases = (
            ("kind-id-mismatch", "id", "agent:trellis-workflow", "does not match kind"),
            ("role-mismatch", "targetRole", "project-agents", "target role"),
        )

        for name, field, value, message in cases:
            with self.subTest(field=field, value=value):
                script = self.copy_onboard(name)
                self.rewrite_catalog_entry(
                    script,
                    "skill:trellis-workflow",
                    field,
                    value,
                )

                completed = self.run_onboard_script(script, "plan", "--json")

                self.assertNotEqual(completed.returncode, 0, completed.stdout)
                self.assertIn(message, completed.stderr)

    def test_check_projects_reports_each_root_without_global_install_checks(
        self,
    ) -> None:
        (self.project_one / "package.json").write_text(
            json.dumps({"dependencies": {"react": "latest"}}),
            encoding="utf-8",
        )
        (self.project_one / "components.json").write_text("{}\n", encoding="utf-8")
        (self.project_two / "tests" / "e2e").mkdir(parents=True)

        completed = self.run_onboard(
            "check-projects",
            "--projects-root",
            self.projects_csv,
            "--json",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["mode"], "check-projects")
        self.assertEqual(
            [item["projectRoot"] for item in payload["projects"]],
            [str(self.project_one.resolve()), str(self.project_two.resolve())],
        )
        self.assertTrue(payload["projects"][0]["reactBits"]["applicable"])
        self.assertTrue(payload["projects"][1]["playwright"]["applicable"])
        paid_steps = " ".join(
            payload["projects"][0]["reactBits"]["manualCheck"]["steps"]
        )
        self.assertIn("even when the target Skill already exists", paid_steps)
        self.assertNotIn("project Skill is missing", paid_steps)

        self.assertNotIn("runtime", payload)
        self.assertNotIn("tools", payload)
        self.assertNotIn("skills", payload)

    def test_projects_root_rejects_relative_paths(self) -> None:
        completed = self.run_onboard(
            "check-projects",
            "--projects-root",
            "relative-project",
            "--json",
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("absolute", completed.stderr)

    def test_plan_installs_global_bundle_once_and_project_files_for_every_root(
        self,
    ) -> None:
        completed = self.run_onboard(
            "plan",
            "--projects-root",
            self.projects_csv,
            "--json",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        targets = [item["target"] for item in payload["operations"]]
        self.assertIn(str(self.project_one.resolve() / "AGENTS.md"), targets)
        self.assertIn(str(self.project_two.resolve() / "AGENTS.md"), targets)
        self.assertIn(str(self.project_one.resolve() / ".gitignore"), targets)
        self.assertIn(str(self.project_two.resolve() / ".gitignore"), targets)
        self.assertIn(
            str(self.codex_home.resolve() / "skills" / "trellis-workflow"),
            targets,
        )
        self.assertNotIn(
            str(self.project_one.resolve() / ".agent" / "skills" / "trellis-workflow"),
            targets,
        )
        self.assertNotIn(
            str(self.project_two.resolve() / ".agent" / "skills" / "trellis-workflow"),
            targets,
        )
        self.assertEqual(payload["bundledMigration"]["status"], "not-needed")
        self.assertEqual(
            payload["bundledMigration"]["migrations"][0]["canonicalName"],
            "sbtd-workflow-onboard",
        )

    def test_plan_routes_global_agents_to_codex_default_or_explicit_override(
        self,
    ) -> None:
        default = self.run_onboard(
            "plan",
            "--projects-root",
            str(self.project_one),
            "--json",
        )
        override_path = self.root / "custom-global-AGENTS.md"
        overridden = self.run_onboard(
            "plan",
            "--projects-root",
            str(self.project_one),
            "--global-agents-path",
            str(override_path),
            "--json",
        )

        self.assertEqual(default.returncode, 0, default.stderr)
        self.assertEqual(overridden.returncode, 0, overridden.stderr)
        default_operations = json.loads(default.stdout)["operations"]
        overridden_operations = json.loads(overridden.stdout)["operations"]
        default_target = next(
            item["target"]
            for item in default_operations
            if item["label"] == "codex global AGENTS.md"
        )
        overridden_target = next(
            item["target"]
            for item in overridden_operations
            if item["label"] == "codex global AGENTS.md"
        )

        self.assertEqual(default_target, str((self.codex_home / "AGENTS.md").resolve()))
        self.assertEqual(overridden_target, str(override_path.resolve()))

    def test_plan_reports_legacy_onboard_target_without_mutating_it(self) -> None:
        global_skills = self.root / "global-skills"
        legacy_onboard = global_skills / "kuno-workflow-onboard-skills"
        legacy_onboard.mkdir(parents=True)
        (legacy_onboard / "SKILL.md").write_text(
            "---\nname: kuno-workflow-onboard-skills\n---\n",
            encoding="utf-8",
        )

        completed = self.run_onboard(
            "plan",
            "--global-skills-dir",
            str(global_skills),
            "--json",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        migration = json.loads(completed.stdout)["bundledMigration"]
        self.assertEqual(migration["status"], "required")
        self.assertEqual(
            migration["migrations"][0]["canonicalTarget"],
            str((global_skills / "sbtd-workflow-onboard").resolve()),
        )
        self.assertEqual(
            migration["migrations"][0]["legacyTargets"],
            [str(legacy_onboard.resolve())],
        )
        self.assertTrue(legacy_onboard.is_dir())

    def test_init_projects_writes_only_project_files(self) -> None:
        completed = self.run_onboard(
            "init-projects",
            "--projects-root",
            self.projects_csv,
            "--skip-trellis-init",
            "--yes",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertTrue((self.project_one / "AGENTS.md").is_file())
        self.assertTrue((self.project_two / "AGENTS.md").is_file())
        self.assertTrue((self.project_one / ".gitignore").is_file())
        self.assertTrue((self.project_two / ".gitignore").is_file())
        self.assertFalse((self.codex_home / "AGENTS.md").exists())
        self.assertFalse((self.codex_home / "skills").exists())

    def test_init_projects_appends_only_missing_gitignore_lines(self) -> None:
        gitignore = self.project_one / ".gitignore"
        gitignore.write_text(
            "# project-specific\nnode_modules/\n.trellis/*\n",
            encoding="utf-8",
        )
        args = (
            "init-projects",
            "--projects-root",
            str(self.project_one),
            "--skip-project-agents",
            "--skip-trellis-init",
            "--yes",
        )

        first = self.run_onboard(*args)
        first_content = gitignore.read_text(encoding="utf-8")
        second = self.run_onboard(*args)
        second_content = gitignore.read_text(encoding="utf-8")

        self.assertEqual(first.returncode, 0, first.stderr or first.stdout)
        self.assertEqual(second.returncode, 0, second.stderr or second.stdout)
        self.assertIn("# project-specific\n", first_content)
        self.assertEqual(first_content.count("node_modules/\n"), 1)
        self.assertEqual(first_content.count(".trellis/*\n"), 1)
        self.assertEqual(first_content.count(".gitnexus/\n"), 1)
        template_lines = {
            line
            for line in (
                ROOT
                / "sbtd-workflow-onboard"
                / "templates"
                / "project"
                / ".gitignore"
            )
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        }
        self.assertTrue(template_lines.issubset(set(first_content.splitlines())))
        self.assertEqual(second_content, first_content)

    def test_init_projects_preserves_legacy_agent_control_ignores(
        self,
    ) -> None:
        gitignore = self.project_one / ".gitignore"
        legacy_entries = (".claude/", "CLAUDE.md", ".agents/", "/AGENTS.md")
        gitignore.write_text(
            "# legacy agent controls\n" + "\n".join(legacy_entries) + "\n",
            encoding="utf-8",
        )

        completed = self.run_onboard(
            "init-projects",
            "--projects-root",
            str(self.project_one),
            "--skip-project-agents",
            "--skip-trellis-init",
            "--yes",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        entries = gitignore.read_text(encoding="utf-8").splitlines()
        for entry in legacy_entries:
            self.assertIn(entry, entries)

        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=self.project_one,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        legacy_control_files = (
            self.project_one / "AGENTS.md",
            self.project_one / "CLAUDE.md",
            self.project_one / ".agents" / "skills" / "trellis-start" / "SKILL.md",
            self.project_one / ".claude" / "agents" / "trellis-implement.md",
        )
        for control_file in legacy_control_files:
            control_file.parent.mkdir(parents=True, exist_ok=True)
            control_file.touch()
            ignored = subprocess.run(
                [
                    "git",
                    "check-ignore",
                    "--quiet",
                    str(control_file.relative_to(self.project_one)),
                ],
                cwd=self.project_one,
            )
            self.assertEqual(ignored.returncode, 0, control_file)

    def test_init_projects_preserves_complete_utf8_bom_gitignore(self) -> None:
        gitignore = self.project_one / ".gitignore"
        template = (
            ROOT
            / "sbtd-workflow-onboard"
            / "templates"
            / "project"
            / ".gitignore"
        ).read_text(encoding="utf-8")
        initial_bytes = b"\xef\xbb\xbf" + template.encode("utf-8")
        gitignore.write_bytes(initial_bytes)
        args = (
            "init-projects",
            "--projects-root",
            str(self.project_one),
            "--skip-project-agents",
            "--skip-trellis-init",
            "--yes",
        )

        first = self.run_onboard(*args)
        second = self.run_onboard(*args)

        self.assertEqual(first.returncode, 0, first.stderr or first.stdout)
        self.assertEqual(second.returncode, 0, second.stderr or second.stdout)
        self.assertEqual(gitignore.read_bytes(), initial_bytes)


    def test_external_skill_project_scope_is_rejected(self) -> None:
        completed = self.run_onboard(
            "install-external-skills",
            "--all",
            "--scope",
            "project",
            "--yes",
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("invalid choice", completed.stderr)

    def test_onboard_public_flags_remove_project_skill_scope(self) -> None:
        completed = self.run_onboard("plan", "--help")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--projects-root", completed.stdout)
        self.assertNotIn("--project-root", completed.stdout)
        self.assertNotIn("--skills-scope", completed.stdout)
        self.assertNotIn("--project-skills-dir", completed.stdout)

    def test_normal_init_keeps_all_skill_targets_global(self) -> None:
        global_skills = self.root / "global-skills"
        external_names = (
            "diagnosing-bugs",
            "tdd",
            "grill-me",
            "grill-with-docs",
            "grilling",
            "domain-modeling",
            "codebase-design",
            "handoff",
            "writing-for-agents",
            "to-spec",
            "to-tickets",
            "impeccable",
            "ui-ux-pro-max",
            "shadcn",
        )
        for name in external_names:
            target = global_skills / name
            target.mkdir(parents=True)
            (target / "SKILL.md").write_text(
                f"---\nname: {name}\n---\n",
                encoding="utf-8",
            )

        legacy_onboard = global_skills / "kuno-workflow-onboard-skills"
        legacy_onboard.mkdir(parents=True)
        (legacy_onboard / "SKILL.md").write_text(
            "---\nname: kuno-workflow-onboard-skills\n---\n",
            encoding="utf-8",
        )

        completed = self.run_onboard(
            "init",
            "--projects-root",
            self.projects_csv,
            "--global-skills-dir",
            str(global_skills),
            "--global-agents-path",
            str(self.root / "global-AGENTS.md"),
            "--skip-trellis-init",
            "--yes",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertTrue((global_skills / "trellis-workflow" / "SKILL.md").is_file())
        self.assertTrue(
            (global_skills / "sbtd-workflow-onboard" / "SKILL.md").is_file()
        )
        self.assertTrue(
            (global_skills / "web-ui-autotest-generator" / "SKILL.md").is_file()
        )
        self.assertFalse(legacy_onboard.exists())
        self.assertFalse((self.project_one / ".agent" / "skills").exists())
        self.assertFalse((self.project_two / ".agent" / "skills").exists())

    def test_init_preserves_unrelated_directory_at_legacy_onboard_path(self) -> None:
        global_skills = self.root / "global-skills"
        catalog = json.loads(
            (ROOT / "sbtd-workflow-onboard" / "catalog.json").read_text(
                encoding="utf-8"
            )
        )
        for entry in catalog["entries"]:
            if entry["kind"] != "external-skill":
                continue
            name = entry["id"].removeprefix("skill:")
            target = global_skills / name
            target.mkdir(parents=True)
            (target / "SKILL.md").write_text(
                f"---\nname: {name}\n---\n",
                encoding="utf-8",
            )

        legacy_onboard = global_skills / "kuno-workflow-onboard-skills"
        legacy_onboard.mkdir(parents=True)
        unrelated_marker = legacy_onboard / "user-data.txt"
        unrelated_marker.write_text("keep\n", encoding="utf-8")
        (legacy_onboard / "SKILL.md").write_text(
            "---\nname: unrelated-user-skill\n---\n",
            encoding="utf-8",
        )

        completed = self.run_onboard(
            "init",
            "--projects-root",
            self.projects_csv,
            "--global-skills-dir",
            str(global_skills),
            "--global-agents-path",
            str(self.root / "global-AGENTS.md"),
            "--skip-trellis-init",
            "--yes",
        )

        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        self.assertIn("legacy Skill identity", completed.stderr)
        self.assertTrue(unrelated_marker.is_file())
        self.assertEqual(unrelated_marker.read_text(encoding="utf-8"), "keep\n")

    def test_init_aborts_before_writes_on_legacy_external_identity_conflict(
        self,
    ) -> None:
        global_skills = self.root / "global-skills"
        catalog = json.loads(
            (ROOT / "sbtd-workflow-onboard" / "catalog.json").read_text(
                encoding="utf-8"
            )
        )
        for entry in catalog["entries"]:
            if entry["kind"] != "external-skill":
                continue
            name = entry["id"].removeprefix("skill:")
            if name == "writing-for-agents":
                continue
            target = global_skills / name
            target.mkdir(parents=True)
            (target / "SKILL.md").write_text(
                f"---\nname: {name}\n---\n",
                encoding="utf-8",
            )

        conflicting = global_skills / "writing-great-skills"
        conflicting.mkdir(parents=True)
        (conflicting / "SKILL.md").write_text(
            "---\nname: user-owned-writing-skill\n---\nkeep\n",
            encoding="utf-8",
        )
        global_agents = self.root / "global-AGENTS.md"
        project_agents = self.project_one / "AGENTS.md"

        completed = self.run_onboard(
            "init",
            "--projects-root",
            self.projects_csv,
            "--global-skills-dir",
            str(global_skills),
            "--global-agents-path",
            str(global_agents),
            "--skip-trellis-init",
            "--yes",
        )

        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        self.assertIn("legacy Skill identity", completed.stderr)
        self.assertTrue((conflicting / "SKILL.md").is_file())
        self.assertEqual(
            (conflicting / "SKILL.md").read_text(encoding="utf-8"),
            "---\nname: user-owned-writing-skill\n---\nkeep\n",
        )
        self.assertFalse((global_skills / "writing-for-agents").exists())
        self.assertFalse(global_agents.exists())
        self.assertFalse(project_agents.exists())
        self.assertFalse((global_skills / "sbtd-workflow-onboard").exists())


    def test_init_projects_checks_trellis_and_bootstrap_for_every_root(self) -> None:
        bootstrap = self.project_two / ".trellis" / "tasks" / "00-bootstrap-guidelines"
        bootstrap.mkdir(parents=True)
        self.write_executable(
            "trellis",
            """#!/bin/sh
if [ "$1" = "--version" ]; then
  echo "trellis 9.9.9"
  exit 0
fi
if [ "$1" = "init" ]; then
  mkdir -p .trellis
  exit 0
fi
exit 1
""",
        )

        completed = self.run_onboard(
            "init-projects",
            "--projects-root",
            self.projects_csv,
            "--trellis-user",
            "developer",
            "--yes",
        )

        self.assertEqual(completed.returncode, 6, completed.stderr or completed.stdout)
        self.assertTrue((self.project_one / ".trellis").is_dir())
        self.assertIn(str(bootstrap.resolve()), completed.stdout)

    def test_init_projects_forwards_distinct_omp_and_pi_flags(self) -> None:
        trellis_args_log = self.root / "trellis-args.log"
        self.env["TRELIS_ARGS_LOG"] = str(trellis_args_log)
        self.write_executable(
            "trellis",
            """#!/bin/sh
if [ "$1" = "--version" ]; then
  echo "trellis 9.9.9"
  exit 0
fi
if [ "$1" = "init" ]; then
  printf '%s\n' "$@" > "$TRELIS_ARGS_LOG"
  mkdir -p .trellis
  exit 0
fi
exit 1
""",
        )

        completed = self.run_onboard(
            "init-projects",
            "--projects-root",
            str(self.project_one),
            "--trellis-user",
            "developer",
            "--trellis-platform",
            "omp,pi,codex",
            "--skip-trellis-bootstrap",
            "--yes",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertEqual(
            trellis_args_log.read_text(encoding="utf-8").splitlines(),
            [
                "init",
                "-u",
                "developer",
                "--omp",
                "--pi",
                "--codex",
                "--yes",
                "--skip-existing",
            ],
        )

if __name__ == "__main__":
    unittest.main()
