from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "sbtd-workflow-onboard" / "templates" / "skills"


class WorkflowContractTests(unittest.TestCase):
    def test_task_reports_stay_local_without_hiding_shared_documents(self) -> None:
        for source in (
            ROOT / ".gitignore",
            ROOT / "sbtd-workflow-onboard" / "templates" / "project" / ".gitignore",
        ):
            with self.subTest(source=source):
                self.assert_template_ignore_state(
                    source=source,
                    ignored=(
                        "ai/tasks/example/reports/raw.json",
                        "ai/tasks/example/reports/review-round4/summary.md",
                        "ai/tasks/parent/child/reports/raw.txt",
                        "ai/tasks/archive/2026-Q1/example/reports/raw.json",
                        "ai/tasks/archive/undated/example/reports/summary.md",
                    ),
                    trackable=(
                        "ai/tasks/index.md",
                        "ai/tasks/example/task.md",
                        "ai/tasks/example/prd.md",
                        "ai/tasks/example/design.md",
                        "ai/tasks/example/implement.md",
                        "ai/tasks/example/reports.md",
                        "ai/tasks/parent/child/task.md",
                        "ai/tasks/archive/2026-Q1/example/task.md",
                        "ai/tasks/archive/undated/example/task.md",
                        "src/reports/template.ts",
                        "reports/public.md",
                        "packages/demo/ai/tasks/example/reports/public.md",
                    ),
                )

    def test_project_template_protects_local_state_without_hiding_shared_paths(
        self,
    ) -> None:
        self.assert_template_ignore_state(
            ignored=(
                ".sbtd/developer",
                ".sbtd/active-task.json",
                ".sbtd/tasks/local/task.md",
                "docs/handoffs/session.md",
                "graft/index.json",
                ".graft/state.json",
            ),
            trackable=(
                "ai/tasks/parent/child/task.md",
                "ai/tasks/archive/2026-Q1/task/task.md",
                "docs/spec/lessons.md",
                "docs/lessons/topics/example.md",
                "packages/graft/index.ts",
                "packages/.graft/model.json",
                "packages/.sbtd/module.md",
                "packages/docs/handoffs/guide.md",
            ),
        )

    def test_project_template_ignores_reserved_symlink_paths(self) -> None:
        template = (
            ROOT / "sbtd-workflow-onboard" / "templates" / "project" / ".gitignore"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            self._run_git(project, "init", "--quiet")
            shutil.copyfile(template, project / ".gitignore")
            external = root / "external"
            external.mkdir()
            for relative in (
                ".sbtd", "docs/handoffs", "graft", ".graft",
                "ai/tasks/example/reports",
            ):
                with self.subTest(path=relative):
                    target = project / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        target.symlink_to(external, target_is_directory=True)
                    except (NotImplementedError, OSError) as error:
                        self.skipTest(f"directory symlinks unavailable: {error}")
                    result = self._run_git(
                        project,
                        "check-ignore",
                        "--no-index",
                        "--quiet",
                        relative,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, relative)

    def assert_template_ignore_state(
        self,
        ignored: tuple[str, ...],
        trackable: tuple[str, ...],
        source: Path | None = None,
    ) -> None:
        template = source or (
            ROOT / "sbtd-workflow-onboard" / "templates" / "project" / ".gitignore"
        )
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            self._run_git(project, "init", "--quiet")
            shutil.copyfile(template, project / ".gitignore")
            for paths, expected in ((ignored, 0), (trackable, 1)):
                for relative in paths:
                    with self.subTest(path=relative):
                        result = self._run_git(
                            project,
                            "check-ignore",
                            "--no-index",
                            "--quiet",
                            relative,
                            check=False,
                        )
                        self.assertEqual(result.returncode, expected, relative)

    def test_project_template_ignores_reserved_regular_files(self) -> None:
        template = (
            ROOT / "sbtd-workflow-onboard" / "templates" / "project" / ".gitignore"
        )
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            self._run_git(project, "init", "--quiet")
            shutil.copyfile(template, project / ".gitignore")
            for relative in (
                ".sbtd", "docs/handoffs", "graft", ".graft",
                "ai/tasks/example/reports",
            ):
                with self.subTest(path=relative):
                    target = project / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("fixture-local-state\n", encoding="utf-8")
                    result = self._run_git(
                        project,
                        "check-ignore",
                        "--no-index",
                        "--quiet",
                        relative,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, relative)

    def test_project_template_ignores_env_secrets_but_keeps_example(self) -> None:
        """A bare `.env` holds real credentials and must never be committable,
        while `.env.example` stays tracked as the checked-in template."""
        self.assert_template_ignore_state(
            ignored=(".env", ".env.local", ".env.production.local"),
            trackable=(".env.example",),
        )

    def test_project_template_ignores_impeccable_local_config_only(self) -> None:
        self.assert_template_ignore_state(
            ignored=(".impeccable/config.local.json",),
            trackable=(
                ".impeccable/config.json",
                ".impeccable/design.json",
            ),
        )

    def test_project_template_output_ignore_is_root_anchored(self) -> None:
        """`output/` is a Playwright artifact directory at the repository root;
        unanchored it would also swallow nested source directories."""
        self.assert_template_ignore_state(
            ignored=("output/report.json",),
            trackable=("src/output/index.ts", "docs/output/guide.md"),
        )

    def test_project_template_tracks_managed_agent_controls(self) -> None:
        template = (
            ROOT / "sbtd-workflow-onboard" / "templates" / "project" / ".gitignore"
        )
        entries = template.read_text(encoding="utf-8").splitlines()

        for tracked_path in (".claude/", "CLAUDE.md", ".agents/", "/AGENTS.md"):
            self.assertNotIn(tracked_path, entries)
        self.assertIn("/AGENTS.md.*", entries)
        for local_runtime in (
            ".claude/projects/",
            ".claude/worktrees/",
            ".claude/settings.local.json",
        ):
            self.assertIn(local_runtime, entries)

        for local_artifact in (
            "node_modules/",
            "dist/",
            "build/",
            ".next/",
            "out/",
            ".env.local",
            ".env.*.local",
        ):
            self.assertIn(local_artifact, entries)

        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            subprocess.run(
                ["git", "init", "--quiet"],
                cwd=project,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            shutil.copyfile(template, project / ".gitignore")

            tracked_files = (
                project / "AGENTS.md",
                project / "CLAUDE.md",
                project / ".agents" / "skills" / "trellis-start" / "SKILL.md",
                project / ".claude" / "agents" / "trellis-implement.md",
                project / ".claude" / "commands" / "trellis" / "start.md",
                project / ".claude" / "hooks" / "session-start.py",
                project / ".claude" / "settings.json",
            )
            for tracked_file in tracked_files:
                tracked_file.parent.mkdir(parents=True, exist_ok=True)
                tracked_file.touch()
                result = subprocess.run(
                    [
                        "git",
                        "check-ignore",
                        "--quiet",
                        str(tracked_file.relative_to(project)),
                    ],
                    cwd=project,
                )
                self.assertEqual(result.returncode, 1, tracked_file)

            ignored_files = (
                project / "AGENTS.md.2026-09-11-1",
                project / ".claude" / "projects" / "local-state.json",
                project / ".claude" / "worktrees" / "local-checkout" / "HEAD",
                project / ".claude" / "settings.local.json",
                project / "node_modules" / "package.json",
                project / "dist" / "index.html",
                project / "build" / "asset.js",
                project / ".next" / "build-manifest.json",
                project / "out" / "index.html",
                project / ".env.local",
                project / ".env.development.local",
            )
            for ignored_file in ignored_files:
                ignored_file.parent.mkdir(parents=True, exist_ok=True)
                ignored_file.touch()
                result = subprocess.run(
                    [
                        "git",
                        "check-ignore",
                        "--quiet",
                        str(ignored_file.relative_to(project)),
                    ],
                    cwd=project,
                )
                self.assertEqual(result.returncode, 0, ignored_file)

    def test_bundled_templates_do_not_route_to_retired_workflows(self) -> None:
        allowed = {
            SKILLS / "lessons-record" / "references" / "identity-migration.md",
        }
        retired = re.compile(
            r"\$trellis|trellis[-_ ]?(?:workflow|channel|check)|Trellis|"
            r"git[-_ ]?nexus|channel[-_ ]preflight|\.trellis",
            re.IGNORECASE,
        )
        offenders = []
        for path in (ROOT / "sbtd-workflow-onboard" / "templates").rglob("*"):
            if not path.is_file() or path in allowed:
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for number, line in enumerate(lines, 1):
                if retired.search(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{number}:{line.strip()}")
        self.assertEqual(offenders, [])

    def test_bundled_method_gates_are_layered_by_mode(self) -> None:
        gated = {
            "book-ddia-data-design",
            "book-legacy-change-safety",
            "book-refactoring-pass",
            "book-release-readiness",
        }
        for name in sorted(gated):
            with self.subTest(skill=name):
                document = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn("## Strict Development Gate", document)
                self.assertIn("default/lite", document)
                self.assertNotIn("## Mandatory Development Gate", document)
        bdd = (SKILLS / "gherkin-bdd" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("In strict tasks", bdd)
        self.assertIn("default/lite", bdd)
        self.assertNotIn("default hard rule", bdd)

    def test_repository_does_not_track_generated_agent_skill_aliases(self) -> None:
        alias = ROOT / ".claude" / "skills" / "sbtd-workflow-onboard"
        canonical = ROOT / "sbtd-workflow-onboard" / "SKILL.md"

        self.assertFalse(alias.is_symlink())
        self.assertFalse(alias.exists())
        self.assertTrue(canonical.is_file())

    def test_repository_uses_canonical_apache_2_license(self) -> None:
        license_path = ROOT / "LICENSE"

        self.assertTrue(license_path.is_file())
        self.assertEqual(
            hashlib.sha256(
                license_path.read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest(),
            "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
        )

    def test_onboard_and_eligible_bundled_skills_share_kunolu_license(self) -> None:
        canonical_license = (ROOT / "LICENSE").read_bytes()
        notice = (
            "Copyright 2026 KunoLu\n\n"
            "The original content in this Skill is licensed under the Apache "
            'License, Version 2.0 (the "License");\n'
            "you may not use this work except in compliance with the License.\n"
            "You may obtain a copy of the License at\n\n"
            "    https://www.apache.org/licenses/LICENSE-2.0\n\n"
            "Unless required by applicable law or agreed to in writing, software\n"
            'distributed under the License is distributed on an "AS IS" BASIS,\n'
            "WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n"
            "See the License for the specific language governing permissions and\n"
            "limitations under the License.\n\n"
            "Third-party components and source-derived material, where present, "
            "retain their own licenses, notices, and attribution requirements.\n"
        )
        excluded = {"seo-geo"}
        eligible_skill_roots = sorted(
            path
            for path in SKILLS.iterdir()
            if path.is_dir() and path.name not in excluded
        )
        licensed_roots = [ROOT / "sbtd-workflow-onboard", *eligible_skill_roots]
        tracked_files = set(
            subprocess.run(
                ["git", "ls-files"],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            ).stdout.splitlines()
        )

        for skill_root in licensed_roots:
            with self.subTest(skill=skill_root.name):
                self.assertEqual(
                    (skill_root / "LICENSE").read_bytes(),
                    canonical_license,
                )
                self.assertEqual(
                    (skill_root / "NOTICE").read_text(encoding="utf-8"),
                    notice,
                )
                self.assertIn(
                    (skill_root / "LICENSE").relative_to(ROOT).as_posix(),
                    tracked_files,
                )
                self.assertIn(
                    (skill_root / "NOTICE").relative_to(ROOT).as_posix(),
                    tracked_files,
                )

    def test_seo_geo_preserves_upstream_provenance_and_scopes_local_modifications(
        self,
    ) -> None:
        skill_root = SKILLS / "seo-geo"
        self.assertEqual(
            (skill_root / "LICENSE").read_bytes(),
            (ROOT / "LICENSE").read_bytes(),
        )

        notice = (skill_root / "NOTICE").read_text(encoding="utf-8")
        for expected in (
            "ReScienceLab/opc-skills",
            "https://github.com/ReScienceLab/opc-skills",
            "ab75cf514281af371962c3a8449cb2a3761fd2b9",
            ".agents/skills/seo-geo",
            "Apache License, Version 2.0",
            "Local modifications Copyright 2026 KunoLu",
            "Adapted the SKILL.md frontmatter",
            "Removed trailing whitespace",
            "Bundled the Skill into sbtd-workflow-onboard",
            "KunoLu claims copyright only in these local modifications",
        ):
            with self.subTest(notice_fragment=expected):
                self.assertIn(expected, notice)

        frontmatter_notice = (
            "# Modified by KunoLu in 2026: adapted upstream frontmatter "
            "for model-invoked discovery; see NOTICE."
        )
        self.assertIn(
            frontmatter_notice,
            (skill_root / "SKILL.md").read_text(encoding="utf-8"),
        )

        whitespace_notice = (
            "Modified by KunoLu in 2026: removed upstream trailing whitespace; "
            "see ../NOTICE."
        )
        whitespace_modified_files = (
            "examples/opc-skills-case-study.md",
            "references/geo-research.md",
            "scripts/autocomplete_ideas.py",
            "scripts/backlinks.py",
            "scripts/competitor_gap.py",
            "scripts/dataforseo_api.py",
            "scripts/domain_overview.py",
            "scripts/keyword_research.py",
            "scripts/related_keywords.py",
            "scripts/seo_audit.py",
            "scripts/serp_analysis.py",
        )
        for relative_path in whitespace_modified_files:
            with self.subTest(modified_file=relative_path):
                self.assertIn(
                    whitespace_notice,
                    (skill_root / relative_path).read_text(encoding="utf-8"),
                )

        tracked_files = set(
            subprocess.run(
                ["git", "ls-files"],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            ).stdout.splitlines()
        )
        for required_file in ("LICENSE", "NOTICE"):
            self.assertIn(
                (skill_root / required_file).relative_to(ROOT).as_posix(),
                tracked_files,
            )

    def test_selected_bundled_skill_descriptions_are_english(self) -> None:
        skill_names = (
            "lessons-record",
            "project-validation",
            "sbtd-task",
        )

        for skill_name in skill_names:
            with self.subTest(skill=skill_name):
                content = (SKILLS / skill_name / "SKILL.md").read_text(encoding="utf-8")
                frontmatter = content.split("---", 2)[1]
                description = next(
                    line
                    for line in frontmatter.splitlines()
                    if line.startswith("description:")
                )
                self.assertNotRegex(description, r"[\u3400-\u9fff]")

    def test_web_ui_skill_is_bundled_with_bilingual_readmes(self) -> None:
        skill_root = SKILLS / "web-ui-autotest-generator"
        english = (skill_root / "README.md").read_text(encoding="utf-8")
        chinese = (skill_root / "README.zh-CN.md").read_text(encoding="utf-8")
        catalog = json.loads(
            (ROOT / "sbtd-workflow-onboard" / "catalog.json").read_text(
                encoding="utf-8"
            )
        )
        entry = next(
            item
            for item in catalog["entries"]
            if item["id"] == "skill:web-ui-autotest-generator"
        )
        stable_manifest = json.loads(
            (
                ROOT
                / "sbtd-workflow-onboard"
                / "assets"
                / "external-skills"
                / "stable"
                / "MANIFEST.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(entry["kind"], "bundled-skill")
        self.assertEqual(entry["source"], "templates/skills/web-ui-autotest-generator")
        self.assertTrue((skill_root / "SKILL.md").is_file())
        skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        description = yaml.safe_load(skill.split("---", 2)[1])["description"]
        self.assertRegex(description, r"[\u3400-\u9fff]")
        for keyword in (
            "frontend",
            "backend",
            "pages",
            "routes",
            "components",
            "APIs",
            "user flows",
            "Playwright UI tests",
            "Chinese test reports",
            "page features",
            "cross-page logic",
            "independent test assets",
        ):
            with self.subTest(description_keyword=keyword):
                self.assertIn(keyword, description)
        bundled_license = skill_root / "LICENSE"
        self.assertTrue(bundled_license.is_file())
        self.assertEqual(
            hashlib.sha256(bundled_license.read_bytes()).hexdigest(),
            hashlib.sha256((ROOT / "LICENSE").read_bytes()).hexdigest(),
        )
        license_text = bundled_license.read_text(encoding="utf-8")
        self.assertIn("Apache License", license_text)
        self.assertNotIn("MIT License", license_text)
        self.assertNotIn("tangyajun", license_text)
        self.assertIn(
            "licensed under the Apache License 2.0",
            english,
        )
        self.assertIn("采用 Apache License 2.0", chinese)
        source_prefix = skill_root.relative_to(ROOT).as_posix() + "/"
        tracked_sources = set(
            subprocess.run(
                ["git", "ls-files", "--", source_prefix],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            ).stdout.splitlines()
        )
        source_files = {
            path.relative_to(ROOT).as_posix()
            for path in skill_root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(source_files, tracked_sources)
        self.assertRegex(chinese, r"[\u3400-\u9fff]")
        self.assertNotRegex(english, r"[\u3400-\u9fff]")
        self.assertEqual(
            [
                len(line) - len(line.lstrip("#"))
                for line in chinese.splitlines()
                if line.startswith("#")
            ],
            [
                len(line) - len(line.lstrip("#"))
                for line in english.splitlines()
                if line.startswith("#")
            ],
        )
        self.assertEqual(chinese.count("```"), english.count("```"))
        for code_span in re.findall(r"`([^`\n]+)`", chinese):
            with self.subTest(code_span=code_span):
                self.assertIn(f"`{code_span}`", english)
        self.assertNotIn("web-ui-autotest", stable_manifest["repositories"])
        self.assertNotIn("web-ui-autotest-generator", stable_manifest["skills"])
        notices = (
            ROOT
            / "sbtd-workflow-onboard"
            / "assets"
            / "external-skills"
            / "stable"
            / "THIRD_PARTY_NOTICES.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Cheryl-station/web-ui-autotest", notices)
        self.assertFalse(
            (
                ROOT
                / "sbtd-workflow-onboard"
                / "assets"
                / "external-skills"
                / "stable"
                / "licenses"
                / "web-ui-autotest-LICENSE"
            ).exists()
        )


    def test_onboard_skill_is_discoverable_and_documents_npx_install(self) -> None:
        skill_path = ROOT / "sbtd-workflow-onboard" / "SKILL.md"
        skill = skill_path.read_text(encoding="utf-8")

        self.assertTrue(skill_path.is_file())
        self.assertIn("name: sbtd-workflow-onboard", skill)
        self.assertIn("npx skills add", skill)
        self.assertIn("--skill sbtd-workflow-onboard", skill)
        self.assertIn("--global", skill)

    def test_onboard_catalog_is_schema_valid_and_sources_exist(self) -> None:
        schema = json.loads(
            (ROOT / "sbtd-workflow-onboard" / "catalog.schema.json").read_text(
                encoding="utf-8"
            )
        )
        catalog = json.loads(
            (ROOT / "sbtd-workflow-onboard" / "catalog.json").read_text(
                encoding="utf-8"
            )
        )
        example = json.loads(
            (
                ROOT / "sbtd-workflow-onboard" / "examples" / "catalog.minimal.json"
            ).read_text(encoding="utf-8")
        )

        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(catalog)
        jsonschema.Draft202012Validator(schema).validate(example)
        ids = [entry["id"] for entry in catalog["entries"]]
        self.assertEqual(len(ids), len(set(ids)))
        # Set-based on purpose: entry order in catalog.json carries no consumer
        # contract, so a reorder must not fail this inventory check. Uniqueness
        # is asserted above.
        self.assertEqual(
            {
                entry["id"]
                for entry in catalog["entries"]
                if entry["kind"] == "bundled-skill"
            },
            {
                "skill:sbtd-workflow-onboard",
                "skill:sbtd-task",
                "skill:project-validation",
                "skill:web-ui-autotest-generator",
                "skill:gherkin-bdd",
                "skill:knowledge-base-integration",
                "skill:maestro-mobile-e2e",
                "skill:lessons-record",
                "skill:book-refactoring-pass",
                "skill:book-legacy-change-safety",
                "skill:book-ddd-distilled-modeling",
                "skill:book-ddia-data-design",
                "skill:book-release-readiness",
                "skill:seo-geo",
            },
        )
        self.assertEqual(
            [
                entry["id"]
                for entry in catalog["entries"]
                if entry["kind"] == "external-skill"
            ],
            [
                "skill:diagnosing-bugs",
                "skill:tdd",
                "skill:grill-me",
                "skill:grill-with-docs",
                "skill:grilling",
                "skill:domain-modeling",
                "skill:codebase-design",
                "skill:handoff",
                "skill:writing-for-agents",
                "skill:to-spec",
                "skill:to-tickets",
                "skill:ui-ux-pro-max",
                "skill:impeccable",
                "skill:shadcn",
                "skill:ponytail",
                "skill:ponytail-review",
                "skill:ponytail-audit",
                "skill:ponytail-debt",
                "skill:i-have-adhd",
            ],
        )
        onboard_root = ROOT / "sbtd-workflow-onboard"
        for entry in catalog["entries"]:
            with self.subTest(entry=entry["id"]):
                if entry["kind"] == "external-skill":
                    self.assertTrue(entry["source"]["repo"].startswith("https://"))
                    self.assertTrue(entry["source"]["subpath"])
                    self.assertIn(
                        entry["id"].removeprefix("skill:"),
                        entry["source"]["aliases"],
                    )
                    continue
                source = (onboard_root / entry["source"]).resolve()
                self.assertTrue(source.is_relative_to(onboard_root.resolve()))
                self.assertTrue(source.exists())

    def test_catalog_schema_rejects_escaping_source_paths(self) -> None:
        schema = json.loads(
            (ROOT / "sbtd-workflow-onboard" / "catalog.schema.json").read_text(
                encoding="utf-8"
            )
        )
        catalog = json.loads(
            (ROOT / "sbtd-workflow-onboard" / "catalog.json").read_text(
                encoding="utf-8"
            )
        )
        validator = jsonschema.Draft202012Validator(schema)
        cases = (
            ("skill:sbtd-task", "source", "../outside"),
            ("skill:sbtd-task", "source", "/tmp/outside"),
            ("skill:diagnosing-bugs", "subpath", "../outside"),
            ("skill:diagnosing-bugs", "subpath", "/tmp/outside"),
        )

        for entry_id, field, value in cases:
            with self.subTest(entry_id=entry_id, field=field, value=value):
                invalid = copy.deepcopy(catalog)
                entry = next(
                    item for item in invalid["entries"] if item["id"] == entry_id
                )
                if field == "subpath":
                    entry["source"][field] = value
                else:
                    entry[field] = value
                with self.assertRaises(jsonschema.ValidationError):
                    validator.validate(invalid)

    def test_catalog_schema_rejects_kind_identity_and_role_mismatches(self) -> None:
        schema = json.loads(
            (ROOT / "sbtd-workflow-onboard" / "catalog.schema.json").read_text(
                encoding="utf-8"
            )
        )
        catalog = json.loads(
            (ROOT / "sbtd-workflow-onboard" / "catalog.json").read_text(
                encoding="utf-8"
            )
        )
        validator = jsonschema.Draft202012Validator(schema)
        cases = (
            ("skill:sbtd-task", "id", "agent:sbtd-task"),
            ("skill:sbtd-task", "targetRole", "project-agents"),
            ("agent:codex-global", "id", "skill:codex-global"),
            ("agent:codex-global", "targetRole", "skill"),
        )

        for entry_id, field, value in cases:
            with self.subTest(entry_id=entry_id, field=field, value=value):
                invalid = copy.deepcopy(catalog)
                entry = next(
                    item for item in invalid["entries"] if item["id"] == entry_id
                )
                entry[field] = value
                with self.assertRaises(jsonschema.ValidationError):
                    validator.validate(invalid)

    def test_catalog_schema_rejects_malformed_https_repository_url(self) -> None:
        schema = json.loads(
            (ROOT / "sbtd-workflow-onboard" / "catalog.schema.json").read_text(
                encoding="utf-8"
            )
        )
        catalog = json.loads(
            (ROOT / "sbtd-workflow-onboard" / "catalog.json").read_text(
                encoding="utf-8"
            )
        )
        validator = jsonschema.Draft202012Validator(schema)
        invalid = copy.deepcopy(catalog)
        external = next(
            item for item in invalid["entries"] if item["kind"] == "external-skill"
        )
        external["source"]["repo"] = "https://"

        with self.assertRaises(jsonschema.ValidationError):
            validator.validate(invalid)

    def test_knowledge_integration_schemas_are_valid_draft_2020_12(self) -> None:
        schema_paths = list(
            (SKILLS / "knowledge-base-integration" / "references").glob("*.schema.json")
        )
        schema_paths.append(
            SKILLS
            / "project-validation"
            / "references"
            / "validation-evidence.schema.json"
        )

        self.assertGreater(len(schema_paths), 1)
        for schema_path in schema_paths:
            with self.subTest(schema=schema_path.name):
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                jsonschema.Draft202012Validator.check_schema(schema)

    def test_knowledge_ingest_requires_explicit_read_only_intent(self) -> None:
        """Preserve the published ingest contract, not an LLM execution claim."""
        gherkin = (SKILLS / "gherkin-bdd" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("explicit read-only intent", gherkin)
        self.assertIn("add / change / update / delete", gherkin)
        self.assertIn("写入 / 新增 / 修改 / 更新 / 删除", gherkin)

    def test_ci_evidence_envelope_is_schema_valid(self) -> None:
        schema_path = (
            SKILLS
            / "project-validation"
            / "references"
            / "validation-evidence.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        envelope = {
            "schemaVersion": 1,
            "runId": "ci-smart-web-pr-123",
            "createdAt": "2026-07-17T00:00:00Z",
            "evidenceSource": "ci",
            "trigger": "pull-request",
            "repository": {
                "repositoryKey": "smart-web",
                "sourceRef": "refs/pull/123/head",
                "sourceCommit": "a" * 40,
                "worktreeState": "clean",
            },
            "sourceRevision": "exact",
            "environmentAlignment": "verified",
            "e2eMode": "full-stack",
            "mockStrategy": "none",
            "featureSources": [],
            "reports": [
                {
                    "testType": "web",
                    "path": "reports/web.html",
                    "summaryMd": "reports/web.md",
                    "sha256": "b" * 64,
                    "status": "passed",
                    "mode": "full-stack",
                }
            ],
            "evidencePublication": "published",
            "secretsRedacted": True,
        }

        jsonschema.Draft202012Validator(schema).validate(envelope)

        invalid_publication = {**envelope, "evidencePublication": "local-only"}
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(schema).validate(invalid_publication)

        invalid_checkout = {
            **envelope,
            "repository": {**envelope["repository"], "worktreeState": "dirty"},
        }
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(schema).validate(invalid_checkout)

    def test_external_skill_policy_is_stable_first_across_user_surfaces(
        self,
    ) -> None:
        documents = {
            path: (ROOT / path).read_text(encoding="utf-8")
            for path in (
                "ENTRYPOINT.md",
                "README.md",
                "install.sh",
                "install.ps1",
                "prompts/automations/sbtd-workflow-tools-version-check.md",
                "sbtd-workflow-onboard/SKILL.md",
                "sbtd-workflow-onboard/REFERENCE.md",
                "sbtd-workflow-onboard/scripts/onboard.py",
                "sbtd-workflow-onboard/templates/agents/AGENTS.global.md",
            )
        }
        combined = "\n".join(documents.values())

        for obsolete in (
            "validated upstream -> vendored stable fallback",
            "auto prefers validated upstream",
            "default `auto` policy validates every selected Skill from one upstream",
            "`auto` (default): clone and validate",
            "默认先验证上游",
            "默认 `auto` 先整组验证上游",
            "External Skill 默认使用 `--source auto`：按上游仓库整组 clone",
        ):
            with self.subTest(obsolete=obsolete):
                self.assertNotIn(obsolete, combined)

        self.assertIn(
            "auto and stable use the vendored stable set",
            documents["sbtd-workflow-onboard/scripts/onboard.py"],
        )
        self.assertIn(
            "auto (vendored stable; upstream is explicit opt-in)",
            documents["install.sh"],
        )
        self.assertIn(
            "auto (vendored stable; upstream is explicit opt-in)",
            documents["install.ps1"],
        )

    def test_update_archive_names_use_positive_numeric_sequences(self) -> None:
        archive_names = [path.name for path in (ROOT / "archive").glob("UPDATED-*.md")]

        self.assertTrue(archive_names)
        for archive_name in archive_names:
            with self.subTest(archive_name=archive_name):
                self.assertRegex(
                    archive_name,
                    r"^UPDATED-\d{4}-\d{2}-\d{2}-[1-9]\d*\.md$",
                )

    def test_repository_controls_are_tracked_or_ignored_as_intended(self) -> None:
        entrypoint_path = ROOT / "ENTRYPOINT.md"
        self.assertTrue(entrypoint_path.is_file())
        tracked = subprocess.run(
            ["git", "ls-files", "--", "AGENTS.md", "ENTRYPOINT.md"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        self.assertEqual(set(tracked), {"ENTRYPOINT.md"})
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "--", "AGENTS.md"],
            cwd=ROOT,
        )
        self.assertEqual(ignored.returncode, 0)

    def test_omp_version_monitoring_contract(self) -> None:
        def markdown_table(text: str, heading: str) -> list[dict[str, str]]:
            section = text.split(heading, 1)[1]
            section = section.split("\n## ", 1)[0]
            header: list[str] | None = None
            rows: list[dict[str, str]] = []
            for line in section.splitlines():
                if not line.startswith("|"):
                    continue
                cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
                if header is None:
                    header = cells
                    continue
                if all(set(cell) <= set("-:") for cell in cells):
                    continue
                rows.append(dict(zip(header, cells, strict=True)))
            return rows

        entrypoint = (ROOT / "ENTRYPOINT.md").read_text(encoding="utf-8")
        omp_rows = [
            row
            for row in markdown_table(entrypoint, "## 0. 版本监控配置")
            if row["工具"] == "OMP"
        ]
        self.assertEqual(len(omp_rows), 1)
        omp = omp_rows[0]
        self.assertEqual(omp["GitHub 仓库"], "can1357/oh-my-pi")
        self.assertEqual(omp["版本通道策略"], "stable-only")
        self.assertEqual(omp["是否启用监控"], "是")
        self.assertRegex(omp["当前使用版本"], r"^v\d+\.\d+\.\d+$")
        self.assertNotIn("omp/", omp["当前使用版本"])
        self.assertIn("@oh-my-pi/pi-coding-agent", omp["备注"])

        summary_omp = [
            row
            for row in markdown_table(entrypoint, "## 10. 当前版本汇总")
            if row["工具"] == "OMP"
        ]
        self.assertEqual(len(summary_omp), 1)
        self.assertEqual(summary_omp[0]["当前版本记录"], omp["当前使用版本"])


    def test_p1_1_runtime_contract_and_runner_examples_are_complete(self) -> None:
        references = SKILLS / "knowledge-base-integration" / "references"
        runtime_contract = (references / "runtime-contract.md").read_text(
            encoding="utf-8"
        )
        workspace = yaml.safe_load(
            (references / "workspace.local.example.yaml").read_text(encoding="utf-8")
        )

        self.assertIn("P1.1 Runtime Contract", runtime_contract)
        self.assertIn("Schema compatibility", runtime_contract)
        self.assertIn("current and previous major", runtime_contract)
        command = workspace["runners"]["android-maestro"]["command"]
        self.assertIn("{job_manifest}", command)
        self.assertIn("{result_manifest}", command)
        self.assertIn("{artifact_dir}", command)

        for example_name, schema_name in (
            ("product.example.yaml", "product.schema.json"),
            ("workspace.local.example.yaml", "workspace.schema.json"),
            ("deployment-manifest.example.yaml", "deployment-manifest.schema.json"),
        ):
            with self.subTest(example=example_name):
                example = yaml.safe_load(
                    (references / example_name).read_text(encoding="utf-8")
                )
                schema = json.loads(
                    (references / schema_name).read_text(encoding="utf-8")
                )
                jsonschema.Draft202012Validator(schema).validate(example)

    def test_deployment_manifest_example_has_valid_canonical_digest(self) -> None:
        path = (
            SKILLS
            / "knowledge-base-integration"
            / "references"
            / "deployment-manifest.example.yaml"
        )
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
        expected = manifest["attestation"].pop("manifest_digest")
        canonical = json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        actual = "sha256:" + hashlib.sha256(canonical).hexdigest()
        self.assertEqual(expected, actual)

    def test_p1_1_documentation_keeps_sync_and_read_separate(self) -> None:
        design = (
            ROOT / "docs" / "prd" / "knowledge-base-integration-prd.md"
        ).read_text(encoding="utf-8")
        self.assertIn("sync / 同步", design)
        self.assertIn("read / 读取", design)
        self.assertIn("Runner Adapter", design)

    def test_caveman_auto_lite_has_monotonic_task_state(self) -> None:
        """Public documentation remains a contract after the rule relocation."""
        reference = (ROOT / "sbtd-workflow-onboard" / "REFERENCE.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("monotonic eligibility latch", reference)
        self.assertIn("new primary goal", reference)
        self.assertIn("protected replies preserve automatic state", reference)

    def test_i_have_adhd_required_external_contract(self) -> None:
        """Keep the surviving public install/activation documentation contract."""
        reference = (ROOT / "sbtd-workflow-onboard" / "REFERENCE.md").read_text(
            encoding="utf-8"
        )
        onboard_skill = (ROOT / "sbtd-workflow-onboard" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        entrypoint = (ROOT / "ENTRYPOINT.md").read_text(encoding="utf-8")

        self.assertIn("All 19 referenced external Skills", reference)
        self.assertIn("ayghri/i-have-adhd", reference)
        self.assertIn("- `i-have-adhd`", onboard_skill)
        self.assertIn(
            "`i-have-adhd` 同为 required external Skill 由 Onboard stable set 统一安装和管理",
            entrypoint,
        )
        self.assertNotIn("| i-have-adhd | ayghri/i-have-adhd |", entrypoint)

    def test_every_completed_grill_requires_visible_ddd_boundary_review(self) -> None:
        """Verify the published gate contract without claiming host compliance."""
        ddd_review = (SKILLS / "book-ddd-distilled-modeling" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        onboard_skill = (ROOT / "sbtd-workflow-onboard" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        reference = (ROOT / "sbtd-workflow-onboard" / "REFERENCE.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "Always run after every completed grill-with-docs session", ddd_review
        )
        self.assertIn("## Mandatory Post-grill Review", ddd_review)
        self.assertIn("DDD Boundary Review", ddd_review)
        self.assertIn("Status: confirmed | needs-clarification | blocked", ddd_review)
        self.assertIn("Corrections to the grill-with-docs result", ddd_review)
        for document in (onboard_skill, reference):
            self.assertIn(
                "Every completed external `grill-with-docs` session", document
            )

    def test_other_book_skills_have_strict_development_gates(self) -> None:
        """Check the unchanged public reviewer result contracts with mode layering."""
        required_skill_phrases = {
            "book-ddia-data-design": (
                "## Strict Development Gate",
                "DDIA Data Design Review",
                "Status: confirmed | needs-design-change | blocked",
                "before design artifacts become stable or implementation begins",
            ),
            "book-legacy-change-safety": (
                "## Strict Development Gate",
                "Legacy Change Safety Review",
                "Status: characterized | needs-safety-net | seam-required | blocked",
                "before the first behavior-changing edit",
            ),
            "book-refactoring-pass": (
                "## Strict Development Gate",
                "Refactoring Review",
                "Status: proceed | refactor-first | blocked",
                "before the first implementation edit to existing production code",
            ),
            "book-release-readiness": (
                "## Strict Development Gate",
                "Release Readiness Review",
                "Status: ready | needs-mitigation | blocked",
                "after all applicable testing-tool gates and project validation",
            ),
        }
        for name, phrases in required_skill_phrases.items():
            document = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(skill=name, contract=phrase):
                    self.assertIn(phrase, document)
        onboard_skill = (ROOT / "sbtd-workflow-onboard" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        reference = (ROOT / "sbtd-workflow-onboard" / "REFERENCE.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("normal `init` / `reset`", onboard_skill)
        self.assertIn("objective predicates", reference)

    def test_lessons_split_name_charset_keeps_ids_collision_free(self) -> None:
        """Exercise the declared public name format without pinning its prose."""
        skill = (SKILLS / "lessons-record" / "SKILL.md").read_text(encoding="utf-8")
        declared_patterns = [
            value
            for value in re.findall(r"`([^`\n]+)`", skill)
            if value.startswith("^") and value.endswith("$")
        ]
        self.assertEqual(len(declared_patterns), 1)
        pattern = re.compile(declared_patterns[0])
        for name in ("alice", "bob2", "640"):
            with self.subTest(accepted=name):
                self.assertIsNotNone(pattern.fullmatch(name))
        for name in ("Alice", "a_b", "alice.wang", "a-b", "中文", "", "alice\n"):
            with self.subTest(rejected=name):
                self.assertIsNone(pattern.fullmatch(name))

    def test_gitignore_lessons_preserve_history_and_add_dated_status(self) -> None:
        repository_lesson = (
            ROOT / "docs" / "lessons" / "topics" / "repository-workflow.md"
        ).read_text(encoding="utf-8")
        validation_lesson = (
            ROOT / "docs" / "lessons" / "topics" / "validation-scripts.md"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "违反本仓库 `.gitignore` 必须严格三行的规则",
            repository_lesson,
        )
        self.assertIn(
            "删除 `.pi/` 并保留 `.DS_Store`、`.gitnexus/`、`.trellis/` 三行",
            repository_lesson,
        )
        self.assertIn(
            "都要运行 `.gitignore` 精确三行检查",
            repository_lesson,
        )
        self.assertIn("状态更新（2026-07-16）", repository_lesson)
        self.assertIn(
            "并保留 `.gitignore` 三行校验，确认 `.DS_Store` 仍被忽略",
            validation_lesson,
        )
        self.assertIn("状态更新（2026-07-16）", validation_lesson)
        self.assertIn("状态更新（2026-07-18）", repository_lesson)
        self.assertIn("状态更新（2026-07-18）", validation_lesson)
        self.assertIn(
            "恢复为 `.DS_Store`、`.gitnexus/`、`.trellis/`、`__pycache__/` 四行",
            repository_lesson,
        )
        self.assertIn(
            "LESSON-20260718-required-controls-tracked-source",
            repository_lesson,
        )
        self.assertIn(
            "LESSON-20260718-automation-sync-trigger-separation",
            repository_lesson,
        )
        self.assertIn("状态更新（2026-08-20）", repository_lesson)
        self.assertIn("状态更新（2026-08-20）", validation_lesson)
        self.assertIn("LESSON-20260820-root-agents-local-only", repository_lesson)
        self.assertIn(
            "`.DS_Store`、`.gitnexus/`、`.trellis/`、`__pycache__/`、`AGENTS.md` 五行",
            repository_lesson,
        )

    def _run_git(
        self,
        repo: Path,
        *args: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        empty_excludes = repo.parent / "empty-excludes"
        if not empty_excludes.exists():
            empty_excludes.write_bytes(b"")
        result = subprocess.run(
            [
                "git",
                "-c",
                "user.name=Lessons Test",
                "-c",
                "user.email=lessons@example.com",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "init.defaultBranch=main",
                "-c",
                f"core.excludesFile={empty_excludes}",
                *args,
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        if check:
            self.assertEqual(
                0,
                result.returncode,
                f"git {' '.join(args)} failed: {result.stdout}{result.stderr}",
            )
        return result

    def _merge_two_appends(
        self,
        repo: Path,
        base: str,
        ours: str,
        theirs: str,
        gitattributes: str | None = None,
    ) -> tuple[int, list[str], str]:
        """Diverge one lessons file two ways, merge, and report the outcome."""
        target = repo / "topics" / "workflow.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        self._run_git(repo, "init", "-q", ".")
        if gitattributes is not None:
            (repo / ".gitattributes").write_text(gitattributes, encoding="utf-8")
        target.write_text(base, encoding="utf-8")
        self._run_git(repo, "add", "-A")
        self._run_git(repo, "commit", "-qm", "base")
        self._run_git(repo, "switch", "-qc", "theirs")
        target.write_text(theirs, encoding="utf-8")
        self._run_git(repo, "commit", "-qam", "theirs")
        self._run_git(repo, "switch", "-q", "main")
        self._run_git(repo, "switch", "-qc", "ours")
        target.write_text(ours, encoding="utf-8")
        self._run_git(repo, "commit", "-qam", "ours")

        merge = self._run_git(repo, "merge", "--no-edit", "theirs", check=False)
        conflicts = self._run_git(
            repo, "diff", "--name-only", "--diff-filter=U"
        ).stdout.split()
        return merge.returncode, conflicts, target.read_text(encoding="utf-8")

    @staticmethod
    def _lessons_block(name: str, *items: str) -> str:
        body = "".join(f"- {item}\n" for item in items)
        return f"<!-- lessons:{name}:start -->\n{body}<!-- lessons:{name}:end -->\n"

    def _assert_blocks_own_their_content(
        self, merged: str, expected: dict[str, list[str]]
    ) -> None:
        """Assert every lesson sits inside its own owner's start-to-end region.

        Counting markers is not enough. A layout that emits `start`, then `end`,
        then the body balances every count and keeps each start marker unique
        while leaving all content outside the block that is supposed to own it.
        """
        regions = re.findall(
            r"<!-- lessons:([a-z0-9]+):start -->\n(.*?)<!-- lessons:\1:end -->",
            merged,
            flags=re.DOTALL,
        )
        owners = [owner for owner, _ in regions]
        self.assertEqual(
            sorted(expected), sorted(owners), f"block owners in {merged!r}"
        )
        self.assertEqual(len(owners), len(set(owners)), f"duplicate blocks: {owners}")

        for owner, body in regions:
            for line in expected[owner]:
                self.assertIn(line, body, f"{owner}'s block must hold {line!r}")
            for other, other_lines in expected.items():
                if other == owner:
                    continue
                for line in other_lines:
                    self.assertNotIn(
                        line, body, f"{owner}'s block must not hold {other}'s {line!r}"
                    )

        # Strip every region: no lesson line may survive outside a block.
        outside = re.sub(
            r"<!-- lessons:[a-z0-9]+:start -->\n.*?<!-- lessons:[a-z0-9]+:end -->",
            "",
            merged,
            flags=re.DOTALL,
        )
        for owner, owner_lines in expected.items():
            for line in owner_lines:
                self.assertNotIn(
                    line, outside, f"{line!r} must not sit outside {owner}'s block"
                )

    # The split-name rule took effect on this date. Records dated before it keep
    # their pre-split IDs and stay outside blocks; every write dated on or after
    # it must sit inside its owner's block.
    LESSONS_SPLIT_NAME_CUTOVER = "20260907"

    @staticmethod
    def _lessons_block_owner(
        regions: list[tuple[int, int, str]], position: int
    ) -> str | None:
        for body_start, body_end, owner in regions:
            if body_start < position < body_end:
                return owner
        return None

    def test_repository_own_lessons_obey_the_block_and_id_rules(self) -> None:
        """This repository routes its own `docs/lessons` through the
        `lessons-record` structure it ships, so every write dated on or after
        the cutover must sit inside its owner's marker block and name that
        owner in its ID. Inspecting only the content already inside a block
        would admit a lesson or status line appended at a file tail, which is
        the concurrent-append path the blocks exist to close.
        """
        cutover = self.LESSONS_SPLIT_NAME_CUTOVER
        start = re.compile(r"<!-- lessons:([a-z0-9]+):start -->")
        end = re.compile(r"<!-- lessons:([a-z0-9]+):end -->")
        # Every write carrying its own date: lesson headings, index rows, and
        # the dated status bullets appended to existing lessons.
        identifiers = re.compile(
            r"^(?:#{2,3} |\| *)(LESSON-(\d{8})-[a-z0-9-]+)", re.MULTILINE
        )
        statuses = re.compile(r"^- 状态更新（(\d{4})-(\d{2})-(\d{2})）", re.MULTILINE)
        blocks = 0
        checked = 0
        unblocked: set[str] = set()

        for path in sorted((ROOT / "docs" / "lessons").rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(ROOT)
            opens = [(m.end(), m.group(1)) for m in start.finditer(text)]
            closes = [(m.start(), m.group(1)) for m in end.finditer(text)]
            self.assertEqual(
                len(opens), len(closes), f"{rel}: unbalanced lessons markers"
            )

            regions: list[tuple[int, int, str]] = []
            for (body_start, owner), (body_end, closing_owner) in zip(
                opens, closes, strict=True
            ):
                blocks += 1
                # A block that closes before it opens, or closes under another
                # owner's marker, is not a block. Both would leave content
                # outside its own region while the markers still look present.
                self.assertEqual(owner, closing_owner, f"{rel}: crossed markers")
                self.assertLess(
                    body_start, body_end, f"{rel}: {owner} block is inverted"
                )
                regions.append((body_start, body_end, owner))

            for match in identifiers.finditer(text):
                lesson_id, date = match.group(1), match.group(2)
                owner = self._lessons_block_owner(regions, match.start(1))
                if date < cutover:
                    if owner is None:
                        unblocked.add(lesson_id)
                    continue
                checked += 1
                self.assertIsNotNone(
                    owner,
                    f"{rel}: {lesson_id} is dated on or after the {cutover} "
                    f"split-name cutover but sits outside every marker block",
                )
                fields = lesson_id.split("-")
                self.assertEqual(
                    owner,
                    fields[2],
                    f"{rel}: {lesson_id} sits in {owner}'s block but names "
                    f"{fields[2]!r} as its split name",
                )
                self.assertTrue(fields[3:], f"{rel}: {lesson_id} has an empty slug")

            for match in statuses.finditer(text):
                date = "".join(match.group(1, 2, 3))
                if date < cutover:
                    continue
                checked += 1
                self.assertIsNotNone(
                    self._lessons_block_owner(regions, match.start()),
                    f"{rel}: the status line dated {date} sits outside every "
                    f"marker block",
                )

        self.assertTrue(blocks, "this repository must carry lessons marker blocks")
        self.assertTrue(
            checked,
            f"no lessons write is dated on or after {cutover}, so the "
            f"post-cutover rule went unexercised",
        )
        # Every ID outside a block predates the rule. Freezing that count closes
        # the one path the date filter cannot see: a new record that skips its
        # block and backdates its ID below the cutover. Archiving a lesson moves
        # its heading without changing this set. Do not raise the number to let
        # an unmarked write pass; put the write in its owner's block instead.
        self.assertEqual(
            73,
            len(unblocked),
            "the set of lesson IDs outside every marker block changed; records "
            "predating the split-name rule are the only ones allowed there",
        )

    def test_lessons_marker_blocks_remove_concurrent_append_conflicts(self) -> None:
        shared = "# Workflow Lessons\n\nShared reading protocol.\n"
        alice = self._lessons_block("alice", "alice L1")
        bob = self._lessons_block("bob", "bob L1")
        alice_grown = self._lessons_block("alice", "alice L1", "alice L2")
        bob_grown = self._lessons_block("bob", "bob L1", "bob L2")

        # The mechanism: both blocks already exist, so two developers appending
        # in their own block land in separate hunks and merge cleanly.
        with tempfile.TemporaryDirectory() as temp_dir:
            code, conflicts, merged = self._merge_two_appends(
                Path(temp_dir),
                base=f"{shared}\n{alice}\n{bob}",
                ours=f"{shared}\n{alice_grown}\n{bob}",
                theirs=f"{shared}\n{alice}\n{bob_grown}",
            )
            self.assertEqual(0, code, f"expected a clean merge, conflicts={conflicts}")
            self.assertEqual([], conflicts)
            self._assert_blocks_own_their_content(
                merged,
                {
                    "alice": ["- alice L1", "- alice L2"],
                    "bob": ["- bob L1", "- bob L2"],
                },
            )
            self.assertNotIn("<<<<<<<", merged)

        # The problem being solved: without blocks, the same two appends collide.
        # If this ever merges cleanly, the feature's premise no longer holds.
        with tempfile.TemporaryDirectory() as temp_dir:
            code, conflicts, _ = self._merge_two_appends(
                Path(temp_dir),
                base=f"{shared}\n- old lesson\n",
                ours=f"{shared}\n- old lesson\n- alice L2\n",
                theirs=f"{shared}\n- old lesson\n- bob L2\n",
            )
            self.assertNotEqual(0, code)
            self.assertEqual(["topics/workflow.md"], conflicts)

        # The disclosed residual: creating the first two blocks still collides
        # once, because both insertions land at the same end-of-file position.
        with tempfile.TemporaryDirectory() as temp_dir:
            code, conflicts, _ = self._merge_two_appends(
                Path(temp_dir),
                base=shared,
                ours=f"{shared}\n{alice}",
                theirs=f"{shared}\n{bob}",
            )
            self.assertNotEqual(0, code)
            self.assertEqual(["topics/workflow.md"], conflicts)

        # The documented opt-in resolves that residual and keeps both blocks
        # intact, which is what makes it safe to offer for append-only files.
        with tempfile.TemporaryDirectory() as temp_dir:
            code, conflicts, merged = self._merge_two_appends(
                Path(temp_dir),
                base=shared,
                ours=f"{shared}\n{alice}",
                theirs=f"{shared}\n{bob}",
                gitattributes="topics/*.md merge=union\n",
            )
            self.assertEqual(0, code, f"expected union merge, conflicts={conflicts}")
            self.assertEqual([], conflicts)
            self._assert_blocks_own_their_content(
                merged, {"alice": ["- alice L1"], "bob": ["- bob L1"]}
            )


if __name__ == "__main__":
    unittest.main()
