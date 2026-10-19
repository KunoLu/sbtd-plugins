from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ONBOARD = ROOT / "sbtd-workflow-onboard" / "scripts" / "onboard.py"
sys.path.insert(0, str(ONBOARD.parent))


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
        self.env["USERPROFILE"] = str(self.home)
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

    def run_onboard(
        self, *args: str, timeout: int = 120
    ) -> subprocess.CompletedProcess[str]:

        return subprocess.run(
            (sys.executable, str(ONBOARD), *args),
            check=False,
            capture_output=True,
            text=True,
            env=self.env,
            timeout=timeout,
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
            "skill:sbtd-task",
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
            "skill:sbtd-task",
            "source",
            "templates/skills/gherkin-bdd",
        )

        completed = self.run_onboard_script(script, "plan", "--json")

        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        self.assertIn("frontmatter name", completed.stderr)

    def test_plan_rejects_absolute_local_catalog_source(self) -> None:
        script = self.copy_onboard()
        absolute_source = (
            script.parents[1] / "templates" / "skills" / "sbtd-task"
        ).resolve()
        self.rewrite_catalog_entry(
            script,
            "skill:sbtd-task",
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
            ("kind-id-mismatch", "id", "agent:sbtd-task", "does not match kind"),
            ("role-mismatch", "targetRole", "project-agents", "target role"),
        )

        for name, field, value, message in cases:
            with self.subTest(field=field, value=value):
                script = self.copy_onboard(name)
                self.rewrite_catalog_entry(
                    script,
                    "skill:sbtd-task",
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
            str(self.codex_home.resolve() / "skills" / "sbtd-task"),
            targets,
        )
        self.assertNotIn(
            str(self.project_one.resolve() / ".agent" / "skills" / "sbtd-task"),
            targets,
        )
        self.assertNotIn(
            str(self.project_two.resolve() / ".agent" / "skills" / "sbtd-task"),
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
            "# project-specific\nnode_modules/\n.trellis/*\n.gitnexus/\ncustom-private/\n",
            encoding="utf-8",
        )
        args = (
            "init-projects",
            "--projects-root",
            str(self.project_one),
            "--skip-project-agents",
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
        self.assertEqual(first_content.count("custom-private/\n"), 1)
        for local_rule in ("/.sbtd", "/docs/handoffs", "/graft", "/.graft"):
            self.assertEqual(first_content.splitlines().count(local_rule), 1)
        template_lines = {
            line
            for line in (
                ROOT / "sbtd-workflow-onboard" / "templates" / "project" / ".gitignore"
            )
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        }
        self.assertTrue(template_lines.issubset(set(first_content.splitlines())))
        self.assertEqual(second_content, first_content)

    def init_project_one_gitignore(self) -> subprocess.CompletedProcess[str]:
        return self.run_onboard(
            "init-projects",
            "--projects-root",
            str(self.project_one),
            "--skip-project-agents",
            "--yes",
        )

    def git_init_project_one(self) -> None:
        subprocess.run(
            ("git", "init", "--quiet"),
            cwd=self.project_one,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_init_projects_reports_broad_shared_path_conflicts(self) -> None:
        self.git_init_project_one()
        gitignore = self.project_one / ".gitignore"
        for pattern in ("ai/", "docs/", "tests/"):
            with self.subTest(pattern=pattern):
                gitignore.write_text("# local\n" + pattern + "\n", encoding="utf-8")
                result = self.init_project_one_gitignore()
                output = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn(
                    f".gitignore:2:{pattern} ignores paths that must stay trackable:",
                    output,
                )
                self.assertIn(
                    pattern, gitignore.read_text(encoding="utf-8").splitlines()
                )

    def test_init_projects_reports_supported_shared_branch_conflicts(self) -> None:
        self.git_init_project_one()
        gitignore = self.project_one / ".gitignore"
        for pattern, hidden in (
            ("/docs/lessons.md", "docs/lessons.md"),
            ("docs/contexts/*/adr/", "docs/contexts/example/adr/example.md"),
            ("ai/tasks/archive/undated/", "ai/tasks/archive/undated/example/task.md"),
            ("maestro/flow/ios/", "maestro/flow/ios/smoke.yml"),
            ("maestro/flow/android/", "maestro/flow/android/smoke.yml"),
            (".agents/skills/react-bits-pro/", ".agents/skills/react-bits-pro/SKILL.md"),
            ("/.gitignore", ".gitignore"),
            ("/.gitattributes", ".gitattributes"),
            ("ai/tasks/*/legacy-task.json", "ai/tasks/example/legacy-task.json"),
            ("ai/tasks/*/prd.md", "ai/tasks/example/prd.md"),
            ("ai/tasks/*/design.md", "ai/tasks/example/design.md"),
            ("ai/tasks/*/implement.md", "ai/tasks/example/implement.md"),
            ("ai/tasks/00-bootstrap-guidelines/", "ai/tasks/00-bootstrap-guidelines/task.md"),
            ("/docs/PRODUCT.md", "docs/PRODUCT.md"),
            ("/docs/DESIGN.md", "docs/DESIGN.md"),
            ("tests/unit/", "tests/unit/test_example.py"),
            ("tests/api/", "tests/api/test_example.py"),
            ("tests/e2e/*.spec.ts", "tests/e2e/example.spec.ts"),
        ):
            with self.subTest(pattern=pattern):
                gitignore.write_text("# local\n" + pattern + "\n", encoding="utf-8")
                result = self.init_project_one_gitignore()
                output = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn(
                    f".gitignore:2:{pattern} ignores paths that must stay trackable:",
                    output,
                )
                self.assertIn(hidden, output)
                self.assertIn(
                    pattern, gitignore.read_text(encoding="utf-8").splitlines()
                )

    def test_init_projects_accepts_gitignore_in_clean_git_repo(self) -> None:
        self.git_init_project_one()

        result = self.init_project_one_gitignore()
        output = result.stdout + result.stderr

        self.assertEqual(result.returncode, 0, output)
        self.assertNotIn("must stay trackable", output)

    def test_init_projects_protects_sbtd_local_state_and_shared_artifacts(self) -> None:
        self.git_init_project_one()
        installed = self.init_project_one_gitignore()
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)

        ignored = (
            ".sbtd/developer",
            ".sbtd/active-task.json",
            ".sbtd/tasks/local/task.md",
            "docs/handoffs/session.md",
            "graft/index.json",
            ".graft/state.json",
            "ai/tasks/example/reports/raw.json",
            "ai/tasks/parent/child/reports/raw.txt",
            "ai/tasks/archive/2026-Q1/example/reports/raw.json",
            "ai/tasks/archive/undated/example/reports/summary.md",
        )
        trackable = (
            "AGENTS.md",
            "ai/tasks/shared/task.md",
            "ai/tasks/parent/child/task.md",
            "ai/tasks/archive/2026-Q1/shared/task.md",
            "ai/tasks/archive/undated/shared/task.md",
            "ai/tasks/shared/reports.md",
            "src/reports/template.ts",
            "docs/spec/lessons.md",
            "docs/lessons/index.md",
            "docs/CONTEXT.md",
            "docs/adr/decision.md",
            "features/example.feature",
            "maestro/flow/smoke.yml",
            "tests/e2e/manifest/ui-test-manifest.json",
            "tests/e2e/manifest/ui-selector-audit.json",
            "tests/e2e/manifest/ui-test-coverage.json",
            "packages/graft/index.ts",
            "packages/.graft/model.json",
            "packages/.sbtd/model.md",
            "packages/docs/handoffs/guide.md",
        )
        for paths, expected in ((ignored, 0), (trackable, 1)):
            for path in paths:
                with self.subTest(path=path):
                    verdict = subprocess.run(
                        ["git", "check-ignore", "--no-index", "--quiet", path],
                        cwd=self.project_one,
                        env=self.env,
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(
                        verdict.returncode, expected, path + verdict.stderr
                    )

    def test_init_projects_skips_gitignore_probe_without_git_repo(self) -> None:
        """Outside a work tree the git-backed probe must degrade to a no-op
        rather than block onboarding."""
        result = self.init_project_one_gitignore()
        output = result.stdout + result.stderr

        self.assertEqual(result.returncode, 0, output)
        self.assertFalse((self.project_one / ".git").exists())
        self.assertIn("verification skipped", output)

    def test_init_projects_rejects_task_report_reinclusion(self) -> None:
        self.git_init_project_one()
        first = self.init_project_one_gitignore()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        gitignore = self.project_one / ".gitignore"
        protected = gitignore.read_text(encoding="utf-8")
        for report_dir in (
            "ai/tasks/example/reports",
            "ai/tasks/parent/child/reports",
            "ai/tasks/archive/2026-Q1/example/reports",
            "ai/tasks/archive/undated/example/reports",
        ):
            with self.subTest(report_dir=report_dir):
                report = self.project_one / report_dir / "raw.json"
                report.parent.mkdir(parents=True, exist_ok=True)
                report.write_bytes(b'{"private": "fixture"}\n')
                pattern = f"!/{report_dir}"
                gitignore.write_text(protected + pattern + "\n", encoding="utf-8")
                result = self.init_project_one_gitignore()
                output = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn("must stay ignored", output)
                self.assertIn(pattern, output)
                self.assertIn(report_dir, output)
                self.assertEqual(report.read_bytes(), b'{"private": "fixture"}\n')

    def test_init_projects_rejects_reinclusion_that_exposes_env_secrets(self) -> None:
        """A pre-existing `!.env*` outlives the appended `.env` rule because the
        template is appended before it in match order only when the user file is
        shorter; either way the merged file must not leave secrets trackable,
        and the report must name the deciding line."""
        self.git_init_project_one()
        gitignore = self.project_one / ".gitignore"
        gitignore.write_text("# local\n.env\n", encoding="utf-8")

        first = self.init_project_one_gitignore()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)

        gitignore.write_text(
            gitignore.read_text(encoding="utf-8") + "!.env*\n", encoding="utf-8"
        )
        result = self.init_project_one_gitignore()
        output = result.stdout + result.stderr

        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("must stay ignored", output)
        self.assertIn("!.env*", output)
        self.assertIn(".env", output)

    def test_init_projects_detects_reinclusion_whose_pattern_contains_a_colon(
        self,
    ) -> None:
        """`!.en[v:]` re-includes `.env` just as plainly as `!.env*`, and the
        verdict must not depend on the pattern being colon-free.

        git reports the deciding pattern as `source:linenum:pattern`, so reading
        the pattern by splitting that text truncates `!.en[v:]` to `]`. The lost
        `!` flips the verdict to "ignored" and onboarding signs off on a merged
        file that leaves secrets trackable -- the precise failure this probe
        exists to catch."""
        self.git_init_project_one()
        gitignore = self.project_one / ".gitignore"
        gitignore.write_text("# local\n.env\n", encoding="utf-8")

        merged = self.init_project_one_gitignore()
        self.assertEqual(merged.returncode, 0, merged.stdout + merged.stderr)

        gitignore.write_text(
            gitignore.read_text(encoding="utf-8") + "!.en[v:]\n", encoding="utf-8"
        )
        result = self.init_project_one_gitignore()
        output = result.stdout + result.stderr

        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("must stay ignored", output)
        self.assertIn("!.en[v:]", output)

    def test_init_projects_json_success_output_is_a_single_document(self) -> None:
        """`--json` promises a machine-readable stdout, which means exactly one
        document -- and the success path is where that promise was broken.

        A write mode used to print the plan document and then a second document
        for the project report, so `json.loads` raised `Extra data` on every
        successful run. Only `plan` and `check` were parsed by tests, so the
        break stayed invisible. Parsing stdout here also pins the prose out of
        the payload, and pins `mode` at the root so a consumer reads it the same
        way for every mode."""
        self.git_init_project_one()

        result = self.run_onboard(
            "init-projects",
            "--projects-root",
            str(self.project_one),
            "--skip-project-agents",
            "--yes",
            "--json",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["mode"], "init-projects")
        self.assertIn("operations", payload)
        self.assertIn("backups", payload)
        self.assertEqual(payload["sbtdProjectSetup"]["status"], "success")
        self.assertIn("unverifiedChecks", payload)
        self.assertNotIn("Verification passed", result.stdout)
        self.assertNotIn("Backups:", result.stdout)

    def test_init_projects_probes_every_sbtd_local_root(self) -> None:
        self.git_init_project_one()
        gitignore = self.project_one / ".gitignore"
        merged = self.init_project_one_gitignore()
        self.assertEqual(merged.returncode, 0, merged.stdout + merged.stderr)
        baseline = gitignore.read_text(encoding="utf-8")
        for root, leaked in (
            (".sbtd", ".sbtd/developer"),
            ("docs/handoffs", "docs/handoffs/session.md"),
            ("graft", "graft/index.json"),
            (".graft", ".graft/state.json"),
        ):
            with self.subTest(root=root):
                gitignore.write_text(
                    baseline + f"!/{root}\n!/{root}/**\n", encoding="utf-8"
                )
                result = self.init_project_one_gitignore()
                output = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn("must stay ignored", output)
                self.assertIn(leaked, output)

    def test_init_projects_fails_when_git_cannot_evaluate_gitignore(self) -> None:
        """A git that errors out is not a licence to pass: an unverified
        .gitignore must block instead of reporting success."""
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git)
        self.write_executable(
            "git",
            "#!/bin/sh\n"
            'if [ "$1" = "check-ignore" ]; then\n'
            '  echo "fatal: simulated check-ignore failure" >&2\n'
            "  exit 2\n"
            "fi\n"
            f'exec {real_git} "$@"\n',
        )
        self.git_init_project_one()

        result = self.init_project_one_gitignore()
        output = result.stdout + result.stderr

        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("could not evaluate", output)

    def test_init_projects_reports_gitignore_check_as_unverified_without_git(
        self,
    ) -> None:
        """No git means no ignore semantics to query, which is a skipped check
        rather than a failure -- but the run must not sign off with a bare
        "Verification passed" that reads as "the merged rules were verified"."""
        self.write_executable(
            "git",
            '#!/bin/sh\necho "fatal: not a git repository" >&2\nexit 128\n',
        )

        result = self.init_project_one_gitignore()
        output = result.stdout + result.stderr

        self.assertEqual(result.returncode, 0, output)
        self.assertIn("verification skipped", output)
        self.assertIn(
            "Verification passed, except for checks that could not be evaluated:",
            result.stdout,
        )
        self.assertNotIn("Verification passed.", result.stdout)

    def test_init_projects_reports_gitignore_check_as_unverified_without_any_git(
        self,
    ) -> None:
        """`git` missing from PATH must degrade the same way as `git` refusing.

        `gitignore_verdicts` folds two different failures into one verdict:
        `run_project_command` returns `None` when the executable cannot be
        spawned at all, and returns exit 128 when git runs but rejects the
        directory. A stub that exits 128 only exercises the second, so the
        `None` branch -- the one taken on a machine without git -- would keep
        passing if it started raising or silently reporting success."""
        empty_bin = self.root / "empty-bin"
        empty_bin.mkdir()
        self.env["PATH"] = str(empty_bin)
        self.assertIsNone(shutil.which("git", path=str(empty_bin)))

        result = self.init_project_one_gitignore()
        output = result.stdout + result.stderr

        self.assertEqual(result.returncode, 0, output)
        self.assertIn("verification skipped", output)
        self.assertIn(
            "Verification passed, except for checks that could not be evaluated:",
            result.stdout,
        )
        self.assertNotIn("Verification passed.", result.stdout)

    def test_init_projects_fails_when_git_answers_only_some_probes(self) -> None:
        """A truncated `check-ignore` answer must not be read as a pass for the
        probes git never mentioned: an unanswered probe is unverified, and every
        probe it covers is safety-bearing.

        The stub answers in the `-z` wire format -- four NUL-terminated fields
        for a single probe -- so the run fails because the other probes went
        unanswered. A textual answer would instead be rejected as malformed
        output, passing this test for the wrong reason and leaving the
        short-answer path untested."""
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git)
        self.write_executable(
            "git",
            "#!/bin/sh\n"
            'if [ "$1" = "check-ignore" ]; then\n'
            "  printf '.gitignore\\0001\\000.env\\000.env\\000'\n"
            "  exit 0\n"
            "fi\n"
            f'exec {real_git} "$@"\n',
        )
        self.git_init_project_one()

        result = self.init_project_one_gitignore()
        output = result.stdout + result.stderr

        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("could not evaluate", output)

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
            ROOT / "sbtd-workflow-onboard" / "templates" / "project" / ".gitignore"
        ).read_text(encoding="utf-8")
        initial_bytes = b"\xef\xbb\xbf" + template.encode("utf-8")
        gitignore.write_bytes(initial_bytes)
        args = (
            "init-projects",
            "--projects-root",
            str(self.project_one),
            "--skip-project-agents",
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

        self.assertEqual(completed.returncode, 2)

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
            "--yes",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertTrue((global_skills / "sbtd-task" / "SKILL.md").is_file())
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

    def write_task(
        self, project: Path, relative_path: str, task_id: str, status: str
    ) -> Path:
        target = project / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        metadata = {
            "schema_version": 1,
            "id": task_id,
            "workflow_mode": "default",
            "mode_source": "default",
            "mode_note": "Synthetic lifecycle fixture.",
            "status": status,
            "branch": None,
            "created_at": "2026-09-18T00:00:00Z",
            "updated_at": "2026-09-18T00:00:00Z",
            "completed_at": "2026-09-18T00:00:00Z" if status == "done" else None,
        }
        target.write_text(
            "---\n" + json.dumps(metadata) + "\n---\n\nPreserve this body.\n",
            encoding="utf-8",
        )
        return target

    def test_init_projects_creates_only_install_assets_without_trellis(self) -> None:
        log = self.root / "unexpected-trellis-call"
        self.env["TRELIS_ARGS_LOG"] = str(log)
        self.write_executable(
            "trellis", '#!/bin/sh\nprintf invoked > "$TRELIS_ARGS_LOG"\nexit 99\n'
        )
        completed = self.run_onboard(
            "init-projects", "--projects-root", self.projects_csv, "--yes", "--json"
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["sbtdProjectSetup"]["status"], "success")
        for project in (self.project_one, self.project_two):
            self.assertEqual(
                {path.name for path in project.iterdir()}, {"AGENTS.md", ".gitignore"}
            )
        self.assertFalse(log.exists())
        self.assertEqual(list(self.home.iterdir()), [])

    def test_legacy_state_blocks_batch_before_any_project_write(self) -> None:
        legacy = self.project_two / ".trellis" / "tasks" / "historical.json"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b'{"unrecognized": "preserve exact bytes"}\n')
        before = legacy.read_bytes()
        completed = self.run_onboard(
            "init-projects", "--projects-root", self.projects_csv, "--yes", "--json"
        )
        self.assertEqual(completed.returncode, 2, completed.stderr)
        projects = json.loads(completed.stdout)["sbtdProjectSetup"]["projects"]
        self.assertEqual(
            [project["status"] for project in projects], ["success", "needs-user"]
        )
        for project in (self.project_one, self.project_two):
            self.assertFalse((project / "AGENTS.md").exists())
            self.assertFalse((project / ".gitignore").exists())
        self.assertEqual(legacy.read_bytes(), before)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_explicit_bootstrap_reports_recorded_status_without_changing_it(
        self,
    ) -> None:
        relative = "ai/tasks/00-bootstrap-guidelines/task.md"
        task = self.write_task(
            self.project_one, relative, "00-bootstrap-guidelines", "planned"
        )
        before = task.read_bytes()
        completed = self.run_onboard(
            "init-projects", "--projects-root", str(self.project_one), "--yes", "--json"
        )
        self.assertEqual(completed.returncode, 6, completed.stderr)
        report = json.loads(completed.stdout)["sbtdProjectSetup"]
        self.assertEqual(report["status"], "bootstrap-required")
        self.assertEqual(task.read_bytes(), before)
        self.assertFalse((self.project_one / "AGENTS.md").exists())
        self.write_task(self.project_one, relative, "00-bootstrap-guidelines", "done")
        done_bytes = task.read_bytes()
        completed = self.run_onboard(
            "init-projects", "--projects-root", str(self.project_one), "--yes", "--json"
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(task.read_bytes(), done_bytes)
        self.assertFalse((self.project_one / ".sbtd").exists())

    def test_invalid_active_pointer_blocks_before_global_install(self) -> None:
        pointer = self.project_one / ".sbtd" / "active-task.json"
        pointer.parent.mkdir()
        pointer.write_bytes(b'{"schema_version": 1,')
        skills = self.root / "global-skills"
        agents = self.root / "global-AGENTS.md"
        completed = self.run_onboard(
            "init",
            "--projects-root",
            str(self.project_one),
            "--global-skills-dir",
            str(skills),
            "--global-agents-path",
            str(agents),
            "--yes",
            "--json",
        )
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout)["sbtdProjectSetup"]["status"], "blocked"
        )
        self.assertEqual(pointer.read_bytes(), b'{"schema_version": 1,')
        self.assertFalse(skills.exists())
        self.assertFalse(agents.exists())
        self.assertFalse((self.project_one / "AGENTS.md").exists())

    def test_check_and_plan_accept_uninitialized_project_without_writes(self) -> None:
        for mode in ("check-projects", "plan"):
            with self.subTest(mode=mode):
                completed = self.run_onboard(
                    mode, "--projects-root", str(self.project_one), "--json"
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                payload = json.loads(completed.stdout)
                report = (
                    payload["projects"][0]["sbtd"]
                    if mode == "check-projects"
                    else payload["sbtdInit"]
                )
                self.assertEqual(report["status"], "success")
                self.assertEqual(list(self.project_one.iterdir()), [])
                self.assertEqual(list(self.home.iterdir()), [])

    def test_new_ignore_protection_does_not_hide_existing_reserved_data(self) -> None:
        private = self.project_one / "graft" / "user-content.txt"
        private.parent.mkdir()
        private.write_bytes(b"user-owned, not a graph\n")
        completed = self.run_onboard(
            "init-projects", "--projects-root", str(self.project_one), "--yes", "--json"
        )
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout)["sbtdProjectSetup"]["status"], "needs-user"
        )
        self.assertEqual(private.read_bytes(), b"user-owned, not a graph\n")
        self.assertFalse((self.project_one / ".gitignore").exists())
        self.assertFalse((self.project_one / "AGENTS.md").exists())

    def test_ignore_symlink_cannot_modify_an_external_file(self) -> None:
        external = self.root / "external-ignore"
        external.write_bytes(b"private-pattern\n")
        (self.project_one / ".gitignore").symlink_to(external)
        completed = self.run_onboard(
            "init-projects", "--projects-root", str(self.project_one), "--yes", "--json"
        )
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertEqual(external.read_bytes(), b"private-pattern\n")
        self.assertTrue((self.project_one / ".gitignore").is_symlink())
        self.assertFalse((self.project_one / "AGENTS.md").exists())

    def test_project_check_respects_explicitly_skipped_agents_target(self) -> None:
        external = self.root / "user-agents"
        external.write_bytes(b"preserve external instructions\n")
        agents = self.project_one / "AGENTS.md"
        agents.symlink_to(external)
        rejected = self.run_onboard(
            "check-projects", "--projects-root", str(self.project_one), "--json"
        )
        self.assertEqual(rejected.returncode, 2, rejected.stderr)
        allowed = self.run_onboard(
            "check-projects",
            "--projects-root",
            str(self.project_one),
            "--skip-project-agents",
            "--json",
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        self.assertEqual(
            json.loads(allowed.stdout)["projects"][0]["sbtd"]["status"], "success"
        )
        self.assertTrue(agents.is_symlink())
        self.assertEqual(external.read_bytes(), b"preserve external instructions\n")
        self.assertFalse((self.project_one / ".gitignore").exists())

    def test_reset_preserves_existing_project_data_bytes(self) -> None:
        initial = self.run_onboard(
            "init-projects", "--projects-root", str(self.project_one), "--yes", "--json"
        )
        self.assertEqual(initial.returncode, 0, initial.stderr)
        contents = {
            ".sbtd/developer": b"name=fixture\n",
            ".sbtd/tasks/history/task.md": b"unselected historical task\n",
            "ai/tasks/history/task.md": b"shared history\n",
            "docs/spec/project.md": b"existing conventions\n",
            "docs/lessons/topics/history.md": b"existing lessons\n",
            "docs/handoffs/session.md": b"existing handoff\n",
        }
        for relative, content in contents.items():
            target = self.project_one / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        completed = self.run_onboard(
            "reset",
            "--projects-root",
            str(self.project_one),
            "--global-skills-dir",
            str(self.root / "global-skills"),
            "--global-agents-path",
            str(self.root / "global-AGENTS.md"),
            "--yes",
            "--json",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        for relative, content in contents.items():
            self.assertEqual((self.project_one / relative).read_bytes(), content)
        self.assertFalse((self.project_one / ".sbtd" / "active-task.json").exists())
        self.assertFalse(
            (self.project_one / "ai/tasks/00-bootstrap-guidelines").exists()
        )

    def _required_external_skill_names(self) -> list[str]:
        catalog = json.loads(
            (ROOT / "sbtd-workflow-onboard" / "catalog.json").read_text(
                encoding="utf-8"
            )
        )
        return [
            entry["id"].removeprefix("skill:")
            for entry in catalog["entries"]
            if entry["kind"] == "external-skill"
        ]

    def _seed_required_external_skills(self, global_skills: Path) -> None:
        for name in self._required_external_skill_names():
            target = global_skills / name
            target.mkdir(parents=True, exist_ok=True)
            (target / "SKILL.md").write_text(
                f"---\nname: {name}\n---\n",
                encoding="utf-8",
            )

    def test_plan_reports_skill_write_actions_for_valid_shells(self) -> None:
        global_skills = self.root / "global-skills"
        bundled = global_skills / "sbtd-task"
        bundled.mkdir(parents=True)
        (bundled / "SKILL.md").write_text(
            "---\nname: sbtd-task\n---\n",
            encoding="utf-8",
        )
        completed = self.run_onboard(
            "plan",
            "--projects-root",
            str(self.project_one),
            "--global-skills-dir",
            str(global_skills),
            "--json",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(
            payload["skillWritePolicy"],
            {"init": "skip-valid-shells", "reset": "overwrite-all"},
        )
        entry = next(
            item
            for item in payload["operations"]
            if item["label"] == "global skill sbtd-task"
        )
        self.assertTrue(entry["targetValid"])
        self.assertEqual(entry["plannedActionOnInit"], "skipped-already-valid")
        self.assertEqual(entry["plannedActionOnReset"], "overwritten-without-backup")

    def test_init_skips_valid_bundled_and_external_skill_shells(self) -> None:
        global_skills = self.root / "global-skills"
        self._seed_required_external_skills(global_skills)
        bundled = global_skills / "sbtd-task"
        bundled.mkdir(parents=True)
        valid_bundled = "---\nname: sbtd-task\n---\nstale-but-valid-bundled\n"
        (bundled / "SKILL.md").write_text(valid_bundled, encoding="utf-8")
        (bundled / "keep-init.txt").write_text("keep-bundled\n", encoding="utf-8")
        invalid_bundled = global_skills / "gherkin-bdd"
        invalid_bundled.mkdir(parents=True)
        (invalid_bundled / "SKILL.md").write_text(
            "---\nname: not-gherkin-bdd\n---\n",
            encoding="utf-8",
        )
        (invalid_bundled / "drop-invalid-bundled.txt").write_text(
            "stale-invalid-bundled\n",
            encoding="utf-8",
        )
        ponytail = global_skills / "ponytail"
        valid_ponytail = "---\nname: ponytail\n---\nstale-but-valid-external\n"
        (ponytail / "SKILL.md").write_text(valid_ponytail, encoding="utf-8")
        (ponytail / "keep-init.txt").write_text("keep-external\n", encoding="utf-8")
        dep = global_skills / "codebase-design"
        valid_dep = "---\nname: codebase-design\n---\nstale-but-valid-dep\n"
        (dep / "SKILL.md").write_text(valid_dep, encoding="utf-8")
        (dep / "keep-dep.txt").write_text("keep-dep\n", encoding="utf-8")
        tdd = global_skills / "tdd"
        (tdd / "SKILL.md").write_text("---\nname: not-tdd\n---\n", encoding="utf-8")
        (tdd / "drop-invalid-tdd.txt").write_text(
            "stale-invalid-tdd\n", encoding="utf-8"
        )

        completed = self.run_onboard(
            "init",
            "--projects-root",
            str(self.project_one),
            "--global-skills-dir",
            str(global_skills),
            "--global-agents-path",
            str(self.root / "global-AGENTS.md"),
            "--yes",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertEqual(
            (bundled / "SKILL.md").read_text(encoding="utf-8"), valid_bundled
        )
        self.assertEqual(
            (bundled / "keep-init.txt").read_text(encoding="utf-8"),
            "keep-bundled\n",
        )
        self.assertEqual(
            (ponytail / "SKILL.md").read_text(encoding="utf-8"), valid_ponytail
        )
        self.assertEqual(
            (ponytail / "keep-init.txt").read_text(encoding="utf-8"),
            "keep-external\n",
        )
        self.assertEqual((dep / "SKILL.md").read_text(encoding="utf-8"), valid_dep)
        self.assertEqual(
            (dep / "keep-dep.txt").read_text(encoding="utf-8"), "keep-dep\n"
        )
        self.assertFalse((invalid_bundled / "drop-invalid-bundled.txt").exists())
        self.assertIn(
            "name: gherkin-bdd",
            (invalid_bundled / "SKILL.md").read_text(encoding="utf-8"),
        )
        self.assertFalse((tdd / "drop-invalid-tdd.txt").exists())
        self.assertIn("name: tdd", (tdd / "SKILL.md").read_text(encoding="utf-8"))
        self.assertTrue((self.root / "global-AGENTS.md").is_file())

    def test_reset_overwrites_valid_bundled_and_external_skills(self) -> None:
        global_skills = self.root / "global-skills"
        self._seed_required_external_skills(global_skills)
        bundled = global_skills / "sbtd-task"
        bundled.mkdir(parents=True)
        (bundled / "SKILL.md").write_text(
            "---\nname: sbtd-task\n---\n",
            encoding="utf-8",
        )
        (bundled / "drop-reset.txt").write_text("stale-bundled\n", encoding="utf-8")
        for name in self._required_external_skill_names():
            (global_skills / name / "drop-reset.txt").write_text(
                f"stale-{name}\n",
                encoding="utf-8",
            )

        completed = self.run_onboard(
            "reset",
            "--projects-root",
            str(self.project_one),
            "--global-skills-dir",
            str(global_skills),
            "--global-agents-path",
            str(self.root / "global-AGENTS.md"),
            "--yes",
            timeout=120,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertFalse((bundled / "drop-reset.txt").exists())
        bundled_template = (
            ROOT
            / "sbtd-workflow-onboard"
            / "templates"
            / "skills"
            / "sbtd-task"
            / "SKILL.md"
        )
        self.assertEqual(
            (bundled / "SKILL.md").read_text(encoding="utf-8"),
            bundled_template.read_text(encoding="utf-8"),
        )
        stable_root = (
            ROOT
            / "sbtd-workflow-onboard"
            / "assets"
            / "external-skills"
            / "stable"
            / "skills"
        )
        for name in self._required_external_skill_names():
            target = global_skills / name
            self.assertFalse((target / "drop-reset.txt").exists(), name)
            self.assertEqual(
                (target / "SKILL.md").read_text(encoding="utf-8"),
                (stable_root / name / "SKILL.md").read_text(encoding="utf-8"),
                name,
            )

    def test_init_installs_complete_sbtd_task_bundle_without_retired_skills(
        self,
    ) -> None:
        """Package-layer proof for the catalog cutover: a fresh isolated init
        must install sbtd-task as the full canonical directory -- entry,
        references, schema and licenses, byte-identical to the declared source
        -- while the retired trellis-workflow/trellis-channel Skills are gone
        from the catalog, the package templates and every installed copy."""
        global_skills = self.root / "global-skills"
        self._seed_required_external_skills(global_skills)
        global_agents = self.root / "global-AGENTS.md"
        args = (
            "--projects-root",
            str(self.project_one),
            "--global-skills-dir",
            str(global_skills),
            "--global-agents-path",
            str(global_agents),
        )

        planned = self.run_onboard("plan", *args, "--json")
        self.assertEqual(planned.returncode, 0, planned.stderr)
        contained_roots = (global_skills.resolve(), self.project_one.resolve())
        for operation in json.loads(planned.stdout)["operations"]:
            target = Path(operation["target"]).resolve()
            self.assertTrue(
                target == global_agents.resolve()
                or any(target.is_relative_to(root) for root in contained_roots),
                operation["target"],
            )

        completed = self.run_onboard("init", *args, "--yes")
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

        catalog = json.loads(
            (ROOT / "sbtd-workflow-onboard" / "catalog.json").read_text(
                encoding="utf-8"
            )
        )
        bundled_entries = [
            entry for entry in catalog["entries"] if entry["kind"] == "bundled-skill"
        ]
        external_entries = [
            entry for entry in catalog["entries"] if entry["kind"] == "external-skill"
        ]
        self.assertEqual(len(bundled_entries), 14)
        self.assertEqual(len(external_entries), 19)
        entry_ids = {entry["id"] for entry in catalog["entries"]}
        self.assertNotIn("skill:trellis-workflow", entry_ids)
        self.assertNotIn("skill:trellis-channel", entry_ids)
        sbtd_task_entry = next(
            entry for entry in bundled_entries if entry["id"] == "skill:sbtd-task"
        )
        self.assertEqual(sbtd_task_entry["source"], "templates/skills/sbtd-task")
        self.assertEqual(sbtd_task_entry["targetRole"], "skill")

        canonical = (
            ROOT / "sbtd-workflow-onboard" / "templates" / "skills" / "sbtd-task"
        )
        canonical_files = sorted(
            path.relative_to(canonical)
            for path in canonical.rglob("*")
            if path.is_file()
        )
        for required in (
            Path("SKILL.md"),
            Path("LICENSE"),
            Path("NOTICE"),
            Path("references") / "task-data.schema.json",
            Path("references") / "strict.md",
            Path("references") / "state.md",
            Path("references") / "handoff.md",
            Path("references") / "methods.md",
            Path("references") / "tooling.md",
            Path("references") / "presentation.md",
        ):
            self.assertIn(required, canonical_files)
        installed = global_skills / "sbtd-task"
        installed_files = sorted(
            path.relative_to(installed)
            for path in installed.rglob("*")
            if path.is_file()
        )
        self.assertEqual(installed_files, canonical_files)
        for relative in canonical_files:
            self.assertEqual(
                (installed / relative).read_bytes(),
                (canonical / relative).read_bytes(),
                str(relative),
            )

        installed_onboard_templates = (
            global_skills / "sbtd-workflow-onboard" / "templates" / "skills"
        )
        for retired in ("trellis-workflow", "trellis-channel"):
            self.assertFalse(
                (
                    ROOT / "sbtd-workflow-onboard" / "templates" / "skills" / retired
                ).exists(),
                retired,
            )
            self.assertFalse((global_skills / retired).exists(), retired)
            self.assertFalse((installed_onboard_templates / retired).exists(), retired)

    def test_plan_skips_omp_global_agents_when_omp_root_absent(self) -> None:
        completed = self.run_onboard(
            "plan",
            "--projects-root",
            str(self.project_one),
            "--json",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        labels = [item["label"] for item in json.loads(completed.stdout)["operations"]]
        self.assertIn("codex global AGENTS.md", labels)
        self.assertNotIn("omp global AGENTS.md", labels)

    def test_plan_includes_omp_global_agents_when_omp_root_exists(self) -> None:
        omp_root = self.home / ".omp"
        omp_root.mkdir()
        completed = self.run_onboard(
            "plan",
            "--projects-root",
            str(self.project_one),
            "--global-agents-path",
            str(self.root / "custom-global-AGENTS.md"),
            "--json",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        operations = json.loads(completed.stdout)["operations"]
        omp_op = next(
            item for item in operations if item["label"] == "omp global AGENTS.md"
        )
        self.assertEqual(
            omp_op["target"],
            str((omp_root / "agent" / "AGENTS.md").resolve()),
        )
        self.assertTrue(
            any(
                item["label"] == "codex global AGENTS.md"
                and item["target"]
                == str((self.root / "custom-global-AGENTS.md").resolve())
                for item in operations
            )
        )

    def test_plan_dedupes_omp_op_when_global_agents_path_is_omp_target(self) -> None:
        omp_agents = self.home / ".omp" / "agent" / "AGENTS.md"
        omp_agents.parent.mkdir(parents=True)
        completed = self.run_onboard(
            "plan",
            "--projects-root",
            str(self.project_one),
            "--global-agents-path",
            str(omp_agents),
            "--json",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        operations = json.loads(completed.stdout)["operations"]
        labels = [item["label"] for item in operations]
        self.assertIn("codex global AGENTS.md", labels)
        self.assertNotIn("omp global AGENTS.md", labels)
        self.assertEqual(
            sum(
                1 for item in operations if item["target"] == str(omp_agents.resolve())
            ),
            1,
        )

    def test_init_same_global_agents_path_as_omp_target_overwrites_once(self) -> None:
        global_skills = self.root / "global-skills"
        self._seed_required_external_skills(global_skills)
        omp_agents = self.home / ".omp" / "agent" / "AGENTS.md"
        omp_agents.parent.mkdir(parents=True)
        omp_agents.write_text("stale omp agents\n", encoding="utf-8")
        template = (
            ROOT / "sbtd-workflow-onboard" / "templates" / "agents" / "AGENTS.global.md"
        ).read_text(encoding="utf-8")

        completed = self.run_onboard(
            "init",
            "--projects-root",
            str(self.project_one),
            "--global-skills-dir",
            str(global_skills),
            "--global-agents-path",
            str(omp_agents),
            "--yes",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertEqual(omp_agents.read_text(encoding="utf-8"), template)
        backups = [
            path
            for path in omp_agents.parent.iterdir()
            if path.name.startswith("AGENTS.md.") and path != omp_agents
        ]
        self.assertEqual(len(backups), 1)

    def test_init_dedupes_project_agents_when_root_is_omp_agent_dir(self) -> None:
        global_skills = self.root / "global-skills"
        self._seed_required_external_skills(global_skills)
        omp_root = self.home / ".omp"
        project_root = omp_root / "agent"
        project_root.mkdir(parents=True)
        omp_agents = project_root / "AGENTS.md"
        omp_agents.write_text("stale omp agents\n", encoding="utf-8")
        template = (
            ROOT / "sbtd-workflow-onboard" / "templates" / "agents" / "AGENTS.global.md"
        ).read_text(encoding="utf-8")

        planned = self.run_onboard(
            "plan",
            "--projects-root",
            str(project_root),
            "--json",
        )
        self.assertEqual(planned.returncode, 0, planned.stderr)
        operations = json.loads(planned.stdout)["operations"]
        matching = [
            item
            for item in operations
            if item["kind"] == "file"
            and Path(item["target"]).resolve() == omp_agents.resolve()
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["label"], "omp global AGENTS.md")

        completed = self.run_onboard(
            "init",
            "--projects-root",
            str(project_root),
            "--global-skills-dir",
            str(global_skills),
            "--yes",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertEqual(omp_agents.read_text(encoding="utf-8"), template)
        backups = [
            path
            for path in project_root.iterdir()
            if path.name.startswith("AGENTS.md.") and path != omp_agents
        ]
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "stale omp agents\n")

    def test_init_overwrites_existing_omp_global_agents(self) -> None:
        global_skills = self.root / "global-skills"
        self._seed_required_external_skills(global_skills)
        omp_agents = self.home / ".omp" / "agent" / "AGENTS.md"
        omp_agents.parent.mkdir(parents=True)
        omp_agents.write_text("stale omp agents\n", encoding="utf-8")
        template = (
            ROOT / "sbtd-workflow-onboard" / "templates" / "agents" / "AGENTS.global.md"
        ).read_text(encoding="utf-8")

        completed = self.run_onboard(
            "init",
            "--projects-root",
            str(self.project_one),
            "--global-skills-dir",
            str(global_skills),
            "--global-agents-path",
            str(self.root / "global-AGENTS.md"),
            "--yes",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertEqual(omp_agents.read_text(encoding="utf-8"), template)
        self.assertEqual(
            (self.root / "global-AGENTS.md").read_text(encoding="utf-8"),
            template,
        )

    def test_init_projects_does_not_write_omp_global_agents(self) -> None:
        omp_root = self.home / ".omp"
        omp_root.mkdir()
        completed = self.run_onboard(
            "init-projects",
            "--projects-root",
            str(self.project_one),
            "--yes",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertFalse((omp_root / "agent" / "AGENTS.md").exists())

    def test_check_json_reports_omp_paths(self) -> None:
        absent = self.run_onboard("check", "--json")
        self.assertEqual(absent.returncode, 0, absent.stderr)
        absent_paths = json.loads(absent.stdout)["paths"]
        self.assertIsNone(absent_paths["ompRoot"])
        self.assertIsNone(absent_paths["ompGlobalAgents"])

        omp_root = self.home / ".omp"
        omp_root.mkdir()
        present = self.run_onboard("check", "--json")
        self.assertEqual(present.returncode, 0, present.stderr)
        present_paths = json.loads(present.stdout)["paths"]
        self.assertEqual(present_paths["ompRoot"], str(omp_root.resolve()))
        self.assertEqual(
            present_paths["ompGlobalAgents"],
            str((omp_root / "agent" / "AGENTS.md").resolve()),
        )


class OmpHomePathTests(unittest.TestCase):
    def test_user_home_prefers_windows_userprofile(self) -> None:
        import importlib.util
        import sys
        from types import SimpleNamespace

        spec = importlib.util.spec_from_file_location("sbtd_onboard", ONBOARD)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        original_os = module.os
        try:
            module.os = SimpleNamespace(
                name="nt",
                environ={"USERPROFILE": r"C:\Users\omp-user"},
            )
            self.assertEqual(module.user_home(), Path(r"C:\Users\omp-user"))
        finally:
            module.os = original_os
            sys.modules.pop(spec.name, None)


if __name__ == "__main__":
    unittest.main()
