from __future__ import annotations

import hashlib
import copy
import json
import re
import shutil
import tempfile
import unittest
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "sbtd-workflow-onboard" / "templates" / "skills"


class WorkflowContractTests(unittest.TestCase):
    def test_repository_gitignore_keeps_canonical_generated_paths(self) -> None:
        entries = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

        self.assertEqual(
            entries,
            [".DS_Store", ".gitnexus/", ".trellis/", "__pycache__/", "AGENTS.md"],
        )

    def test_project_template_ignores_trellis_workspace(self) -> None:
        template = (
            ROOT / "sbtd-workflow-onboard" / "templates" / "project" / ".gitignore"
        )
        entries = template.read_text(encoding="utf-8").splitlines()

        # Coverage comes from the parent wildcard alone. A separate
        # `.trellis/workspace` entry is a direct child of `.trellis/*` and so
        # changes no verdict; keeping it contradicts the adjacent comment that
        # forbids re-listing direct children.
        self.assertIn(".trellis/*", entries)
        self.assertNotIn(".trellis/workspace", entries)
        self.assertNotIn("!.trellis/workspace/", entries)
        self.assertNotIn("!.trellis/workspace/**", entries)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme_html = (ROOT / "README.html").read_text(encoding="utf-8")
        self.assertIn("无尾随斜杠的 `.trellis/*`", readme)
        self.assertIn(
            "无尾随斜杠的 <code>.trellis/*</code>",
            readme_html,
        )
        self.assertIn("有意不同于上游 Trellis 默认会 stage workspace 内容", readme)
        self.assertIn(
            "有意不同于上游 Trellis 默认会 stage workspace 内容",
            readme_html,
        )
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

            workspace = project / ".trellis" / "workspace" / "developer"
            ignored_files = (
                project / ".trellis" / "workspace" / "index.md",
                workspace / "journal-1.md",
                workspace / "index.md",
                workspace / "trace" / "session.json",
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
                self.assertEqual(result.returncode, 0)

    def test_project_template_ignores_trellis_workspace_symlink(self) -> None:
        template = (
            ROOT / "sbtd-workflow-onboard" / "templates" / "project" / ".gitignore"
        )

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

            workspace = project / ".trellis" / "workspace"
            workspace.parent.mkdir()
            external_workspace = project / "external-workspace"
            external_workspace.mkdir()
            try:
                workspace.symlink_to(external_workspace, target_is_directory=True)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"workspace symlinks unavailable: {error}")

            ignored_symlink = subprocess.run(
                ["git", "check-ignore", "--quiet", str(workspace.relative_to(project))],
                cwd=project,
            )
            self.assertEqual(ignored_symlink.returncode, 0)

    def assert_template_ignore_state(
        self,
        ignored: tuple[str, ...],
        trackable: tuple[str, ...],
    ) -> None:
        template = (
            ROOT / "sbtd-workflow-onboard" / "templates" / "project" / ".gitignore"
        )
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

            for relative_path in ignored:
                result = subprocess.run(
                    ["git", "check-ignore", "--no-index", "--quiet", relative_path],
                    cwd=project,
                )
                self.assertEqual(
                    result.returncode, 0, f"{relative_path} must be ignored"
                )
            for relative_path in trackable:
                result = subprocess.run(
                    ["git", "check-ignore", "--no-index", "--quiet", relative_path],
                    cwd=project,
                )
                self.assertEqual(
                    result.returncode, 1, f"{relative_path} must stay trackable"
                )

    def test_project_template_trellis_star_covers_runtime_children(self) -> None:
        """`.trellis/*` alone covers every runtime child, so the template never
        needs to re-list `.backup-*`, `worktrees`, `.runtime`, `.cache`,
        `channels`, or `.template-hashes.json`."""
        self.assert_template_ignore_state(
            ignored=(
                ".trellis/.backup-20260101/spec.md",
                ".trellis/worktrees/feature/file.md",
                ".trellis/.runtime/state.json",
                ".trellis/.cache/index.bin",
                ".trellis/channels/main.jsonl",
                ".trellis/.template-hashes.json",
            ),
            trackable=(
                ".trellis/workflow.md",
                ".trellis/spec/spec.md",
                ".trellis/agents/agent.md",
                ".trellis/lessons/lessons.md",
                ".trellis/tasks/sample/prd.md",
            ),
        )

    def test_project_template_ignores_env_secrets_but_keeps_example(self) -> None:
        """A bare `.env` holds real credentials and must never be committable,
        while `.env.example` stays tracked as the checked-in template."""
        self.assert_template_ignore_state(
            ignored=(".env", ".env.local", ".env.production.local"),
            trackable=(".env.example",),
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

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme_html = (ROOT / "README.html").read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        for document in (readme, readme_html, changelog):
            self.assertIn("旧模板已经写入", document)
            self.assertIn("reset", document)
            self.assertIn("不会自动删除", document)

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

    def test_platform_option_and_automation_scope_are_explicit(self) -> None:
        bash_installer = (ROOT / "install.sh").read_text(encoding="utf-8")
        powershell_installer = (ROOT / "install.ps1").read_text(encoding="utf-8")
        onboard_skill = (ROOT / "sbtd-workflow-onboard" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        onboard_reference = (
            ROOT / "sbtd-workflow-onboard" / "REFERENCE.md"
        ).read_text(encoding="utf-8")
        prompt = (
            ROOT
            / "prompts"
            / "automations"
            / "sbtd-workflow-tools-version-check.md"
        ).read_text(encoding="utf-8")

        for installer in (bash_installer, powershell_installer):
            self.assertIn("Target Agent CLI and MCP platform.", installer)
            self.assertIn(
                "does not change the Codex global AGENTS.md target",
                installer,
            )
        for document in (onboard_skill, onboard_reference):
            self.assertIn(
                "The Agent platform selects the CLI and MCP adapter",
                document,
            )
            self.assertIn(
                "does not select the global AGENTS target",
                document,
            )
            self.assertIn("~/.omp/agent/AGENTS.md", document)
            self.assertIn("does not create `.omp`", document)
            self.assertIn("single file write", document)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme_html = (ROOT / "README.html").read_text(encoding="utf-8")
        self.assertIn("~/.omp/agent/AGENTS.md", readme)
        self.assertIn("~/.omp/agent/AGENTS.md", readme_html)
        self.assertIn("不存在则跳过且不创建 `.omp`", readme)
        self.assertIn("不存在则跳过且不创建 <code>.omp</code>", readme_html)
        init_asset = (
            ROOT / "docs" / "assets" / "onboard-skill-init.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("不写 `~/.omp/agent/AGENTS.md`", init_asset)
        self.assertIn("~/.omp/agent/AGENTS.md", init_asset)

        for path in (
            "`install.sh`",
            "`install.ps1`",
            "`sbtd-workflow-onboard/templates/project/.gitignore`",
            "`tests/**`",
        ):
            self.assertIn(path, prompt)
        self.assertIn("不依赖根 `AGENTS.md` 是否存在", prompt)
        self.assertIn("不得创建缺失的 `.omp`", prompt)

        self.assertIn("无人值守自动化", prompt)
        self.assertIn("用户在交互会话中明确要求", prompt)

        self.assertIn("无人值守自动化仅可创建或修改", prompt)
        self.assertIn(
            "`install.sh`、`install.ps1`、`sbtd-workflow-onboard/scripts/onboard.py`、"
            "`sbtd-workflow-onboard/catalog.json`、"
            "`sbtd-workflow-onboard/catalog.schema.json`、"
            "`sbtd-workflow-onboard/templates/project/.gitignore` 与 `tests/**` "
            "只能读取、评估或验证，不得由无人值守自动化修改。",
            prompt,
        )

    def test_grill_status_does_not_force_redundant_questions(self) -> None:
        global_agents = (
            ROOT
            / "sbtd-workflow-onboard"
            / "templates"
            / "agents"
            / "AGENTS.global.md"
        ).read_text(encoding="utf-8")
        workflow = (
            ROOT
            / "sbtd-workflow-onboard"
            / "templates"
            / "skills"
            / "trellis-workflow"
            / "SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertNotIn("必须主动询问用户是否需要先用", global_agents)
        self.assertIn(
            "只有调用与跳过之间存在会实质改变需求、领域边界或实现决策的权衡时，才询问用户",
            global_agents,
        )
        self.assertNotIn(
            "ask whether the user wants to use that Skill first and then reassess",
            workflow,
        )
        self.assertIn(
            "Ask only when using versus skipping the Skill presents a material trade-off",
            workflow,
        )

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
            hashlib.sha256(license_path.read_bytes()).hexdigest(),
            "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
        )
        license_entries = {
            "README.md": "`sbtd-workflow-onboard/LICENSE` / `NOTICE`",
            "README.html": (
                "<code>sbtd-workflow-onboard/LICENSE</code> / <code>NOTICE</code>"
            ),
        }
        for document, license_entry in license_entries.items():
            content = (ROOT / document).read_text(encoding="utf-8")
            self.assertIn("Apache License 2.0", content)
            self.assertIn("web-ui-autotest-generator/LICENSE", content)
            self.assertIn("seo-geo/LICENSE", content)
            self.assertIn("ReScienceLab/opc-skills", content)
            self.assertIn(license_entry, content)
            self.assertIn("Copyright 2026 KunoLu", content)

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
            "trellis-channel",
            "trellis-workflow",
        )

        for skill_name in skill_names:
            with self.subTest(skill=skill_name):
                content = (SKILLS / skill_name / "SKILL.md").read_text(
                    encoding="utf-8"
                )
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
        self.assertEqual(
            entry["source"], "templates/skills/web-ui-autotest-generator"
        )
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
            [len(line) - len(line.lstrip("#")) for line in chinese.splitlines() if line.startswith("#")],
            [len(line) - len(line.lstrip("#")) for line in english.splitlines() if line.startswith("#")],
        )
        self.assertEqual(chinese.count("```"), english.count("```"))
        for code_span in re.findall(r"`([^`\n]+)`", chinese):
            with self.subTest(code_span=code_span):
                self.assertIn(f"`{code_span}`", english)
        self.assertNotIn("web-ui-autotest", stable_manifest["repositories"])
        self.assertNotIn(
            "web-ui-autotest-generator", stable_manifest["skills"]
        )
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

    def test_changelog_orders_tags_newest_first(self) -> None:
        changelog_path = ROOT / "CHANGELOG.md"

        self.assertTrue(changelog_path.is_file())
        changelog = changelog_path.read_text(encoding="utf-8")
        self.assertTrue(changelog.startswith("# CHANGELOG\n"))

        def heading_index(version: str) -> int:
            match = re.search(
                rf"^## {re.escape(version)}（",
                changelog,
                re.MULTILINE,
            )
            self.assertIsNotNone(match, version)
            return int(match.start())

        self.assertLess(heading_index("v1.0.4"), heading_index("v1.0.3"))
        self.assertLess(heading_index("v1.0.3"), heading_index("v1.0.2"))
        self.assertLess(heading_index("v1.0.2"), heading_index("v1.0.1"))
        self.assertLess(heading_index("v1.0.1"), heading_index("v1.0.0"))
        self.assertIn("## v1.0.4（2026-07-19）", changelog)
        self.assertIn("## v1.0.3（2026-07-19）", changelog)
        self.assertIn("## v1.0.2（2026-07-18）", changelog)
        self.assertIn("## v1.0.1（2026-07-18）", changelog)
        self.assertNotIn("## v1.0.2（未发布）", changelog)
        self.assertNotIn("## v1.0.4（未发布）", changelog)
        self.assertRegex(changelog, r"[\u4e00-\u9fff]")

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
        self.assertEqual(
            [
                entry["id"]
                for entry in catalog["entries"]
                if entry["kind"] == "bundled-skill"
            ],
            [
                "skill:sbtd-workflow-onboard",
                "skill:trellis-workflow",
                "skill:trellis-channel",
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
            ],
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
            ("skill:trellis-workflow", "source", "../outside"),
            ("skill:trellis-workflow", "source", "/tmp/outside"),
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
            ("skill:trellis-workflow", "id", "agent:trellis-workflow"),
            ("skill:trellis-workflow", "targetRole", "project-agents"),
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
        gherkin = (SKILLS / "gherkin-bdd" / "SKILL.md").read_text(encoding="utf-8")
        project_agents = (
            ROOT
            / "sbtd-workflow-onboard"
            / "templates"
            / "agents"
            / "AGENTS.project.md"
        ).read_text(encoding="utf-8")

        for document in (gherkin, project_agents):
            self.assertIn("explicit read-only intent", document)
            self.assertIn("add / change / update / delete", document)
            self.assertIn("写入 / 新增 / 修改 / 更新 / 删除", document)

    def test_trellis_requires_post_commit_pr_head_evidence_refresh(self) -> None:
        trellis = (SKILLS / "trellis-workflow" / "SKILL.md").read_text(encoding="utf-8")
        contract = (
            SKILLS
            / "project-validation"
            / "references"
            / "validation-evidence-contract.md"
        ).read_text(encoding="utf-8")

        self.assertIn("post-commit evidence refresh", trellis)
        self.assertIn("final PR head SHA", trellis)
        self.assertIn("sidecar / envelope", trellis)
        self.assertIn("After the commit", contract)
        self.assertIn("final PR head SHA", contract)
        self.assertIn("sidecar or aggregate envelope", contract)

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

    def test_readme_uses_repository_root_script_path(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme_html = (ROOT / "README.html").read_text(encoding="utf-8")
        repository_script = (
            "sbtd-workflow-onboard/templates/skills/"
            "knowledge-base-integration/scripts/knowledge_base_p1.py"
        )
        self.assertIn(repository_script, readme)
        self.assertIn(repository_script, readme_html)

        parser = HTMLParser()
        parser.feed(readme_html)
        parser.close()

    def test_version_check_prompt_is_versioned_and_documented(self) -> None:
        prompt_path = (
            ROOT / "prompts" / "automations" / "sbtd-workflow-tools-version-check.md"
        )
        prompt = prompt_path.read_text(encoding="utf-8")

        self.assertIn("SBTD Workflow Tools Version Check", prompt)
        self.assertIn("sbtd-workflow-onboard/catalog.json", prompt)
        self.assertIn("catalog.schema.json", prompt)
        self.assertIn("`__pycache__/`", prompt)
        self.assertIn("不要修改 `ENTRYPOINT.md`", prompt)
        self.assertIn("内容严格为五行", prompt)
        self.assertIn(
            "- `prompts/automations/sbtd-workflow-tools-version-check.md`",
            prompt,
        )
        self.assertIn(
            "`## <工具名> <起始版本> -> <目标版本>`",
            prompt,
        )
        self.assertIn("每个 bundled Skill local source", prompt)
        self.assertIn("每个 external Skill source", prompt)
        self.assertNotRegex(prompt, r"\d+ 个 bundled Skill local source")
        self.assertNotRegex(prompt, r"\d+ 个 external Skill source")
        read_allowlist = next(
            line
            for line in prompt.splitlines()
            if "当前可读取、评估或验证的本仓库版本化规则" in line
        )
        write_allowlist = next(
            line
            for line in prompt.splitlines()
            if "无人值守自动化仅可创建或修改" in line
        )
        self.assertIn("`ENTRYPOINT.md`", read_allowlist)
        self.assertIn("`UPDATE.md`", read_allowlist)
        for writable_path in (
            "`sbtd-workflow-onboard/SKILL.md`",
            "`sbtd-workflow-onboard/REFERENCE.md`",
        ):
            with self.subTest(writable_path=writable_path):
                self.assertIn(writable_path, write_allowlist)
        for read_only_path in (
            "`install.sh`",
            "`install.ps1`",
            "`sbtd-workflow-onboard/scripts/onboard.py`",
            "`sbtd-workflow-onboard/templates/project/.gitignore`",
            "`tests/**`",
        ):
            with self.subTest(read_only_path=read_only_path):
                self.assertNotIn(read_only_path, write_allowlist)
        for document_path in (
            ROOT / "README.md",
            ROOT / "README.html",
        ):
            with self.subTest(document=document_path.name):
                self.assertIn(
                    "prompts/automations/sbtd-workflow-tools-version-check.md",
                    document_path.read_text(encoding="utf-8"),
                )

    def test_external_skill_policy_is_stable_first_across_user_surfaces(
        self,
    ) -> None:
        documents = {
            path: (ROOT / path).read_text(encoding="utf-8")
            for path in (
                "ENTRYPOINT.md",
                "README.md",
                "README.html",
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
        archive_names = [
            path.name for path in (ROOT / "archive").glob("UPDATED-*.md")
        ]

        self.assertTrue(archive_names)
        for archive_name in archive_names:
            with self.subTest(archive_name=archive_name):
                self.assertRegex(
                    archive_name,
                    r"^UPDATED-\d{4}-\d{2}-\d{2}-[1-9]\d*\.md$",
                )

    def test_tracked_controls_and_onboard_usage_are_documented(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme_html = (ROOT / "README.html").read_text(encoding="utf-8")
        prompt = (
            ROOT / "prompts" / "automations" / "sbtd-workflow-tools-version-check.md"
        ).read_text(encoding="utf-8")

        self.assertLess(
            readme.index("## 安装及使用说明"),
            readme.index("## 仓库定位"),
        )
        bootstrap_command = (
            "npx --yes skills@latest add \\\n"
            "  KunoLu/640-skills@sbtd-workflow-onboard \\\n"
            "  --global \\\n"
            "  --agent codex \\\n"
            "  --yes \\\n"
            "  --copy"
        )
        pinned_bootstrap_command = (
            "npx --yes skills@latest add \\\n"
            "  'KunoLu/640-skills#v1.0.0@sbtd-workflow-onboard' \\\n"
            "  --global \\\n"
            "  --agent codex \\\n"
            "  --yes \\\n"
            "  --copy"
        )
        plan_command = (
            'python "$SBTD_ONBOARD_DIR/scripts/onboard.py" plan \\\n'
            "  --platform codex \\\n"
            "  --projects-root /abs/project-one,/abs/project-two \\\n"
            "  --json"
        )
        self.assertIn(
            "KunoLu/640-skills#<tag>@sbtd-workflow-onboard",
            readme,
        )
        self.assertIn(
            "KunoLu/640-skills#&lt;tag&gt;@sbtd-workflow-onboard",
            readme_html,
        )
        self.assertNotIn(
            "KunoLu/640-skills#<tag>@sbtd-workflow-onboard",
            readme_html,
        )
        for document in (readme, readme_html):
            self.assertIn(bootstrap_command, document)
            self.assertIn(pinned_bootstrap_command, document)
            self.assertNotIn(
                "  https://github.com/KunoLu/640-skills \\\n",
                document,
            )
            self.assertNotIn("  --skill sbtd-workflow-onboard \\\n", document)
            self.assertIn("默认分支", document)
            self.assertIn("最新 commit", document)
            self.assertIn("最新 tag", document)
            self.assertIn(plan_command, document)
            self.assertIn("sbtd-workflow-onboard Skill", document)
            self.assertIn("AGENTS.md", document)
            self.assertIn("ENTRYPOINT.md", document)
            self.assertIn("SBTD Workflow Tools Version Check", document)
            self.assertIn("英语逗号", document)
            self.assertIn("--init-projects", document)
            self.assertIn("install.sh", document)
            self.assertIn("install.ps1", document)

        self.assertIn("非交互执行必须二选一", readme)
        self.assertIn(
            "project-only 模式只记录平台上下文，不执行任何全局检测或安装",
            readme_html,
        )
        self.assertIn("只有用户明确执行 `sync` / `同步` 时", prompt)
        self.assertIn("`update` / `更新` 与二者无关", prompt)
        self.assertIn("版本检查自动化不直接读取或写入 Orca live automation", prompt)
        self.assertNotIn("git check-ignore", prompt)
        self.assertNotIn("修改后必须同步更新同名 live automation", prompt)
        self.assertIn(
            "`CHANGELOG.md`、`README.md`、`README.html` 和本 prompt",
            prompt,
        )
        self.assertIn("包含 `web-ui-autotest-generator`", prompt)
        self.assertIn("`AGENTS.project.md` 不在普通 sync 范围内", prompt)
        self.assertIn(
            "install-external-skills --skills ponytail,ponytail-review,ponytail-audit,ponytail-debt",
            prompt,
        )
        self.assertIn("不得把 Ponytail stable 路径列为 cp/rsync 目标", prompt)
        self.assertNotIn(
            "templates/skills/ponytail",
            prompt,
        )

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

        for document in (readme, readme_html):
            self.assertIn("web-ui-autotest-generator", document)
            self.assertIn(
                "/Users/lusonglin/.agent/skills/web-ui-autotest-generator/",
                document,
            )
            self.assertIn(
                "install-external-skills --skills ponytail,ponytail-review,ponytail-audit,ponytail-debt",
                document,
            )
            self.assertIn("不得作为同步表", document)
            self.assertIn("本机可选", document)
            self.assertIn("不进入远程", document)
        entrypoint = entrypoint_path.read_text(encoding="utf-8")
        self.assertIn("## 0. 版本监控配置", entrypoint)
        self.assertIn("本机若存在根 `AGENTS.md` 则一并扫描", entrypoint)

    def test_readme_knowledge_cli_example_is_shell_executable(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme_html = (ROOT / "README.html").read_text(encoding="utf-8")
        invalid_pipeline = "knowledge_base_p1.py " + "|".join(
            ("validate-config", "decision", "ingest", "smoke")
        )
        executable_prefix = (
            "python sbtd-workflow-onboard/templates/skills/"
            "knowledge-base-integration/scripts/knowledge_base_p1.py "
            "validate-config"
        )

        for document in (readme, readme_html):
            self.assertNotIn(invalid_pipeline, document)
            self.assertIn(executable_prefix, document)
            self.assertIn("--product", document)
            self.assertIn("--workspace", document)

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
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        design = (
            ROOT / "docs" / "prd" / "knowledge-base-integration-prd.md"
        ).read_text(encoding="utf-8")
        for document in (readme, design):
            self.assertIn("sync / 同步", document)
            self.assertIn("read / 读取", document)
        self.assertIn("P1.1", readme)
        self.assertIn("Runner Adapter", design)

    def test_caveman_auto_lite_has_monotonic_task_state(self) -> None:
        agents_root = ROOT / "sbtd-workflow-onboard" / "templates" / "agents"
        global_agents = (agents_root / "AGENTS.global.md").read_text(encoding="utf-8")
        project_agents = (agents_root / "AGENTS.project.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme_html = (ROOT / "README.html").read_text(encoding="utf-8")
        reference = (ROOT / "sbtd-workflow-onboard" / "REFERENCE.md").read_text(
            encoding="utf-8"
        )

        required_global_phrases = (
            "自动生命周期由本全局规则负责",
            "外部 `caveman` Skill 只负责手动模式的表达风格、强度和手动退出",
            "没有暴露配置或配置缺失时按 `auto` 处理",
            "`progressUpdateCount`",
            "`toolResultCount`",
            "`autoLiteEligible`",
            "`autoLiteActive`",
            "`taskAutoExit`",
            "`sessionAutoExit`",
            "`autoLiteEligible=true` 后",
            "下一条非保护区、非阻塞且无需用户决定的重复中间状态更新必须进入",
            "保护区只覆盖当前回复的表达风格",
            "不得清除计数器、`autoLiteEligible` 或 `autoLiteActive`",
            "不重新计数",
            "新的主要目标",
            "`继续`、`确认`、授权、状态询问、故障恢复",
            "context compaction",
            "handoff",
            "首次自动进入时的一次性提示是外部 Skill“不宣布模式”规则的唯一例外",
            "不得停止或跳过必须的中间状态更新",
        )
        for phrase in required_global_phrases:
            with self.subTest(global_rule=phrase):
                self.assertIn(phrase, global_agents)

        for obsolete_phrase in (
            "已知配置不是 `off`",
            "且后续仍需要继续探索、读取、验证或修复",
            "且后续输出主要是重复状态或验证摘要",
            "再次满足自动模式资格",
            "新的用户请求到来时",
        ):
            with self.subTest(obsolete_global_rule=obsolete_phrase):
                self.assertNotIn(obsolete_phrase, global_agents)

        self.assertIn("只引用全局状态机事实源", project_agents)
        self.assertIn("保护区只覆盖当前回复", project_agents)
        self.assertNotIn("`progressUpdateCount`", project_agents)
        self.assertNotIn("`toolResultCount`", project_agents)

        for document in (readme, readme_html):
            self.assertIn("autoLiteEligible", document)
            self.assertIn("新的主要目标", document)
            self.assertIn("保护区只覆盖当前回复", document)
            self.assertIn("配置缺失时按 auto 处理", document)

        self.assertIn("monotonic eligibility latch", reference)
        self.assertIn("new primary goal", reference)
        self.assertIn("protected replies preserve automatic state", reference)

    def test_every_completed_grill_requires_visible_ddd_boundary_review(
        self,
    ) -> None:
        agents_root = ROOT / "sbtd-workflow-onboard" / "templates" / "agents"
        global_agents = (agents_root / "AGENTS.global.md").read_text(encoding="utf-8")
        project_agents = (agents_root / "AGENTS.project.md").read_text(encoding="utf-8")
        trellis = (
            ROOT
            / "sbtd-workflow-onboard"
            / "templates"
            / "skills"
            / "trellis-workflow"
            / "SKILL.md"
        ).read_text(encoding="utf-8")
        ddd_review = (
            ROOT
            / "sbtd-workflow-onboard"
            / "templates"
            / "skills"
            / "book-ddd-distilled-modeling"
            / "SKILL.md"
        ).read_text(encoding="utf-8")
        onboard_skill = (
            ROOT / "sbtd-workflow-onboard" / "SKILL.md"
        ).read_text(encoding="utf-8")
        reference = (
            ROOT / "sbtd-workflow-onboard" / "REFERENCE.md"
        ).read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme_html = (ROOT / "README.html").read_text(encoding="utf-8")

        for phrase in (
            "无论是 Agent 自发调用还是用户主动调用",
            "每次完整执行 `grill-with-docs` 结束后",
            "`grill-with-docs` 内嵌的 external `domain-modeling` dependency 已运行也不得替代",
            "必须立即调用 `book-ddd-distilled-modeling`",
            "`DDD Boundary Review`",
            "审核状态枚举、输出字段、重跑回路和 stop condition 以 `book-ddd-distilled-modeling/SKILL.md` 为唯一事实源",
            "审核未达到该 Skill 定义的通过状态前，不得进入需求确认、PRD、design、Trellis task 或实现",
        ):
            with self.subTest(global_rule=phrase):
                self.assertIn(phrase, global_agents)

        # The status enum belongs to the owning reviewer Skill. The global rules
        # fix only this gate's timing, so they must not restate the vocabulary.
        self.assertNotIn(
            "`confirmed` / `needs-clarification` / `blocked`", global_agents
        )

        # The project template delegates the enum and the cross-reviewer order
        # to the global rules, so it must still bind the gate without restating
        # the vocabulary.
        self.assertIn("强制 post-grill DDD 二次审核", project_agents)
        self.assertIn(
            "并输出 `DDD Boundary Review` 后才能进入需求确认 / PRD",
            project_agents,
        )
        self.assertIn(
            "`book-ddd-distilled-modeling` 不可用时记为 `blocked`",
            project_agents,
        )

        for phrase in (
            "Every completed `grill-with-docs` session",
            "regardless of whether the Agent or the user initiated it",
            "must be followed immediately by `book-ddd-distilled-modeling`",
            "`domain-modeling` inside `grill-with-docs` does not satisfy",
            "`DDD Boundary Review`",
            "must not advance to requirement confirmation, PRD, design, task creation, or implementation",
        ):
            with self.subTest(trellis_rule=phrase):
                self.assertIn(phrase.lower(), trellis.lower())

        self.assertIn(
            "Always run after every completed grill-with-docs session",
            ddd_review,
        )
        self.assertIn("## Mandatory Post-grill Review", ddd_review)
        self.assertIn("DDD Boundary Review", ddd_review)
        self.assertIn("Status: confirmed | needs-clarification | blocked", ddd_review)
        self.assertIn("Corrections to the grill-with-docs result", ddd_review)

        self.assertIn(
            "Every completed external `grill-with-docs` session",
            onboard_skill,
        )
        self.assertIn("Every completed external `grill-with-docs` session", reference)

        for document in (readme, readme_html):
            self.assertIn("DDD Boundary Review", document)
            self.assertIn("每次完整执行", document)
            self.assertIn("grill-with-docs", document)
            self.assertIn("external", document)
            self.assertIn("domain-modeling", document)
            self.assertIn("不能替代", document)
            self.assertIn("未达到", document)
            self.assertIn("confirmed", document)

    def test_other_book_skills_have_mandatory_development_gates(
        self,
    ) -> None:
        onboard_root = ROOT / "sbtd-workflow-onboard"
        agents_root = onboard_root / "templates" / "agents"
        skills_root = onboard_root / "templates" / "skills"
        global_agents = (agents_root / "AGENTS.global.md").read_text(encoding="utf-8")
        project_agents = (agents_root / "AGENTS.project.md").read_text(encoding="utf-8")
        trellis = (skills_root / "trellis-workflow" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        skill_contracts = {
            name: (skills_root / name / "SKILL.md").read_text(encoding="utf-8")
            for name in (
                "book-refactoring-pass",
                "book-legacy-change-safety",
                "book-ddia-data-design",
                "book-release-readiness",
            )
        }
        onboard_skill = (onboard_root / "SKILL.md").read_text(encoding="utf-8")
        reference = (onboard_root / "REFERENCE.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme_html = (ROOT / "README.html").read_text(encoding="utf-8")

        for phrase in (
            "`Book Gate Plan`",
            "下方 Skill 路由表是客观触发条件的唯一常驻事实源",
            "各 `book-*/SKILL.md` 独占 reviewer 状态、输出 schema、修正回路和 stop condition",
            "命中触发条件后不得主观降级",
            "未命中时保持 on-demand",
            "`seam-required` 的受控例外以两份 reviewer Skill 为准",
            "强制门禁命中但 Skill 缺失、不可读取或证据不足时，Gate state 为 `blocked`",
        ):
            with self.subTest(global_rule=phrase):
                self.assertIn(phrase, global_agents)

        # Reviewer display names and status enums are owned by the matched
        # book-*/SKILL.md, asserted below. The global rules route to them and
        # must not carry a second copy that could drift.
        for review_name, status_enum in (
            (
                "`DDIA Data Design Review`",
                "`confirmed` / `needs-design-change` / `blocked`",
            ),
            (
                "`Legacy Change Safety Review`",
                "`characterized` / `needs-safety-net` / `seam-required` / `blocked`",
            ),
            ("`Refactoring Review`", "`proceed` / `refactor-first` / `blocked`"),
            ("`Release Readiness Review`", "`ready` / `needs-mitigation` / `blocked`"),
        ):
            with self.subTest(global_delegates=review_name):
                self.assertNotIn(review_name, global_agents)
                self.assertNotIn(status_enum, global_agents)

        # AGENTS.project.md is the project-only fallback. It routes objective
        # trigger predicates to the owning Skill instead of restating reviewer
        # labels, and leaves cross-reviewer ordering to the global rules.
        for phrase in (
            "修改既有生产代码 -> 行为保持型重构检查（`book-refactoring-pass`）",
            "高回归风险任一命中 -> 遗留代码安全修改检查（`book-legacy-change-safety`）",
            "上下文边界或模型歧义 -> 领域边界审核（`book-ddd-distilled-modeling`）",
            "API 所有权",
            "-> 数据设计风险检查（`book-ddia-data-design`）",
            "rollout / migration / runtime 运维行为变更任一命中",
            "-> 发布就绪检查（`book-release-readiness`）",
            "对应 bundled Skill 不存在时该项为 `blocked`，不得记为 `passed` 或静默跳过",
            "若当前会话的全局规则已把某 reviewer 标为强制门禁，则缺 Skill 必须 `blocked`",
        ):
            with self.subTest(project_rule=phrase):
                self.assertIn(phrase, project_agents)

        for phrase in (
            "`Book Gate Plan`",
            "unmatched scenarios remain on-demand",
            "matched mandatory gates cannot be downgraded",
            "Use the global Skill routing table as the objective-trigger source.",
            "Load the matched `book-*/SKILL.md` before the gate runs",
            "that reviewer Skill is the sole source for its output schema, pass status, correction loop, and stop condition",
            "Do not duplicate reviewer-specific status vocabularies in Trellis artifacts.",
        ):
            with self.subTest(trellis_rule=phrase):
                self.assertIn(phrase.lower(), trellis.lower())

        required_skill_phrases = {
            "book-ddia-data-design": (
                "## Mandatory Development Gate",
                "DDIA Data Design Review",
                "Status: confirmed | needs-design-change | blocked",
                "before design artifacts become stable or implementation begins",
            ),
            "book-legacy-change-safety": (
                "## Mandatory Development Gate",
                "Legacy Change Safety Review",
                "Status: characterized | needs-safety-net | seam-required | blocked",
                "before the first behavior-changing edit",
            ),
            "book-refactoring-pass": (
                "## Mandatory Development Gate",
                "Refactoring Review",
                "Status: proceed | refactor-first | blocked",
                "before the first implementation edit to existing production code",
            ),
            "book-release-readiness": (
                "## Mandatory Development Gate",
                "Release Readiness Review",
                "Status: ready | needs-mitigation | blocked",
                "after all applicable testing-tool gates and project validation",
            ),
        }
        for skill_name, phrases in required_skill_phrases.items():
            for phrase in phrases:
                with self.subTest(skill=skill_name, contract=phrase):
                    self.assertIn(phrase, skill_contracts[skill_name])

        self.assertIn("normal `init` / `reset`", onboard_skill)
        self.assertIn("objective predicates", reference)
        for document in (readme, readme_html):
            self.assertIn("Book Gate Plan", document)
            self.assertIn("DDIA Data Design Review", document)
            self.assertIn("Legacy Change Safety Review", document)
            self.assertIn("Refactoring Review", document)
            self.assertIn("Release Readiness Review", document)
            self.assertIn("其他场景仍按需调用", document)

    def test_book_gate_lifecycle_resolves_review_findings(self) -> None:
        """Every gate-lifecycle claim is checked independently so one drifted
        document cannot mask the rest of the surfaces in the same run."""
        onboard_root = ROOT / "sbtd-workflow-onboard"
        agents_root = onboard_root / "templates" / "agents"
        skills_root = onboard_root / "templates" / "skills"

        def agents(name: str) -> str:
            return (agents_root / name).read_text(encoding="utf-8")

        def skill(name: str) -> str:
            return (skills_root / name / "SKILL.md").read_text(encoding="utf-8")

        global_agents = agents("AGENTS.global.md")
        project_agents = agents("AGENTS.project.md")
        trellis = skill("trellis-workflow")
        legacy = skill("book-legacy-change-safety")
        refactoring = skill("book-refactoring-pass")
        ddia = skill("book-ddia-data-design")
        release = skill("book-release-readiness")
        onboard_skill = (onboard_root / "SKILL.md").read_text(encoding="utf-8")
        reference = (onboard_root / "REFERENCE.md").read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme_html = (ROOT / "README.html").read_text(encoding="utf-8")

        def present(label: str, document: str, needle: str, topic: str) -> None:
            with self.subTest(topic=topic, document=label, expect="present"):
                self.assertIn(needle, document)

        def absent(label: str, document: str, needle: str, topic: str) -> None:
            with self.subTest(topic=topic, document=label, expect="absent"):
                self.assertNotIn(needle, document)

        lifecycle = "`planned` → `running` → `passed` / `blocked`"
        gate_states = "`planned` / `running` / `passed` / `blocked` / `not-required`"

        # AGENTS.global.md owns the Gate state enum and README mirrors it for
        # users. trellis-workflow/SKILL.md maintains the plan but delegates the
        # vocabulary, so it must name the plan without restating the states.
        for label, document in (
            ("AGENTS.global.md", global_agents),
            ("README.md", readme),
        ):
            present(label, document, "Book Gate Plan", "gate plan")
            present(label, document, gate_states, "gate state enum")
            present(label, document, lifecycle, "gate lifecycle")
        present("trellis-workflow", trellis, "Book Gate Plan", "gate plan")
        present(
            "trellis-workflow",
            trellis,
            "Do not duplicate reviewer-specific status vocabularies in Trellis artifacts.",
            "vocabulary delegation",
        )
        absent("trellis-workflow", trellis, gate_states, "gate state enum")
        # AGENTS.project.md names the plan but delegates the enum; the
        # delegation itself is held by
        # test_reviewer_status_vocabularies_stay_in_their_owning_skill.
        present("AGENTS.project.md", project_agents, "Book Gate Plan", "gate plan")
        present("README.html", readme_html, "Book Gate Plan", "gate plan")
        for state in ("planned", "running", "passed", "blocked", "not-required"):
            with self.subTest(topic="gate state enum", document="README.html", state=state):
                self.assertIn(f"<code>{state}</code>", readme_html)
        present(
            "README.html",
            readme_html,
            "<code>planned</code> → <code>running</code>",
            "gate lifecycle",
        )

        present(
            "AGENTS.global.md",
            global_agents,
            "已命中强制门禁：不得直接跳过",
            "no-skip rule",
        )
        unavailable_section = global_agents.split("### Skill 不可用时", 1)[1]
        present(
            "AGENTS.global.md#unavailable",
            unavailable_section,
            "book-derived 开发阶段强制门禁",
            "skill-unavailable fallback",
        )
        present(
            "AGENTS.global.md#unavailable",
            unavailable_section,
            "`blocked`",
            "skill-unavailable fallback",
        )
        absent(
            "AGENTS.global.md#unavailable",
            unavailable_section,
            "- 直接跳过。\n- 不要阻塞任务。",
            "skill-unavailable fallback",
        )

        # `seam-required` is owned by the two reviewer Skills. The global rules
        # pin only its controlled exception; Trellis must not restate it.
        for label, document in (
            ("AGENTS.global.md", global_agents),
            ("book-legacy-change-safety", legacy),
            ("book-refactoring-pass", refactoring),
        ):
            present(label, document, "`seam-required`", "seam-required ownership")
        present(
            "AGENTS.global.md",
            global_agents,
            "`seam-required` 的受控例外以两份 reviewer Skill 为准",
            "seam-required exception",
        )
        absent("trellis-workflow", trellis, "`seam-required`", "seam-required ownership")
        for label, document in (
            ("book-legacy-change-safety", legacy),
            ("book-refactoring-pass", refactoring),
        ):
            present(label, document, "safety-seam-only", "safety-seam-only ownership")

        release_order = "after all applicable testing-tool gates and project validation"
        for label, document in (
            ("book-release-readiness", release),
            ("sbtd-workflow-onboard/SKILL.md", onboard_skill),
            ("REFERENCE.md", reference),
        ):
            present(label, document, release_order, "release gate ordering")
        # Trellis states the same ordering in its own phase vocabulary.
        arrows = trellis.replace("\u2192", "->")
        present(
            "trellis-workflow",
            trellis,
            "after all testing-tool gates and `project-validation`",
            "release gate ordering",
        )
        present(
            "trellis-workflow",
            arrows,
            "-> project-validation final validation",
            "release phase order",
        )
        present(
            "trellis-workflow",
            arrows,
            "-> book-release-readiness (when applicable)",
            "release phase order",
        )
        for needle in ("required validation", "optional check", "accountable owner"):
            present("book-release-readiness", release, needle, "release evidence roles")

        cache_trigger = "shared, persistent, cross-request, or cross-process caches"
        present("book-ddia-data-design", ddia, cache_trigger, "cache trigger")
        absent("book-ddia-data-design", ddia, "- Caches, queues", "cache trigger")
        for label, document in (
            ("AGENTS.global.md", global_agents),
            ("AGENTS.project.md", project_agents),
            ("trellis-workflow", trellis),
            ("README.md", readme),
            ("README.html", readme_html),
        ):
            present(
                label,
                document,
                "shared / persistent / cross-request / cross-process cache",
                "cache trigger",
            )

        for label, document in (
            ("sbtd-workflow-onboard/SKILL.md", onboard_skill),
            ("REFERENCE.md", reference),
        ):
            present(label, document, "normal `init` / `reset`", "gate activation scope")
            present(
                label,
                document,
                "bootstrap and `init-projects` do not activate",
                "gate activation scope",
            )
        present(
            "sbtd-workflow-onboard/SKILL.md",
            onboard_skill,
            "`Book Gate Plan`",
            "gate plan",
        )

        present(
            "CHANGELOG.md",
            changelog,
            "external `domain-modeling` dependency",
            "domain-modeling provenance",
        )
        absent(
            "CHANGELOG.md",
            changelog,
            "内部 `domain-modeling`",
            "domain-modeling provenance",
        )

        # The caveman auto-lite rule is restated in several README sections.
        # The floor is 2 rather than the current 3 so adding or removing one
        # restatement stays legal; it only catches the rule collapsing to a
        # single mention. README.html carries its own wording, so this is a
        # within-README consistency check, not a cross-file parity check.
        for phrase in (
            "5 个独立工具结果",
            "`autoLiteEligible` 单调锁存",
            "只有新的主要目标重置",
        ):
            with self.subTest(topic="caveman rule restatement", phrase=phrase):
                self.assertGreaterEqual(readme.count(phrase), 2)

        present(
            "README.html",
            readme_html,
            "事务边界、读写路径、backfill / replay / rollback / recovery",
            "ddia trigger prose",
        )

    def test_reviewer_status_vocabularies_stay_in_their_owning_skill(self) -> None:
        """A status enum copied into a second document drifts out of step with
        its owner without anything failing, so the delegating template must
        point at the owner rather than restate the members."""
        agents_root = ROOT / "sbtd-workflow-onboard" / "templates" / "agents"
        global_agents = (agents_root / "AGENTS.global.md").read_text(encoding="utf-8")
        project_agents = (agents_root / "AGENTS.project.md").read_text(encoding="utf-8")

        gate_states = "`planned` / `running` / `passed` / `blocked` / `not-required`"
        # Exact membership, not a subset: a member added to or dropped from the
        # rendering below stops matching the owning document.
        self.assertEqual(
            {part.strip().strip("`") for part in gate_states.split("/")},
            {"planned", "running", "passed", "blocked", "not-required"},
        )
        self.assertEqual(global_agents.count(gate_states), 1)

        self.assertIn("本文件不复制 reviewer 状态词表", project_agents)
        self.assertNotIn(gate_states, project_agents)
        # `blocked` stays reachable in the delegating template because the
        # fallback needs it; the states that only ever appear inside the enum
        # must not.
        for state in ("planned", "running", "not-required"):
            with self.subTest(delegated_state=state):
                self.assertNotIn(f"`{state}`", project_agents)
        self.assertIn("`blocked`", project_agents)

        for owned in ("`seam-required`", "`safety-seam-only`"):
            with self.subTest(reviewer_status=owned):
                self.assertNotIn(owned, project_agents)

    def test_book_gate_rows_cover_every_canonical_trigger(self) -> None:
        """Each gate's trigger predicate is restated in three standalone rule
        sources. A trigger widened in the canonical Skill but missed in a
        restatement silently narrows the gate wherever it was missed. Every
        trigger token is asserted inside the single routing row that owns it,
        so a short token such as `API` cannot be satisfied by an unrelated
        mention elsewhere in the file."""
        onboard_root = ROOT / "sbtd-workflow-onboard"
        agents_root = onboard_root / "templates" / "agents"
        skills_root = onboard_root / "templates" / "skills"
        global_agents = (agents_root / "AGENTS.global.md").read_text(encoding="utf-8")
        project_agents = (agents_root / "AGENTS.project.md").read_text(encoding="utf-8")
        trellis = (skills_root / "trellis-workflow" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        def gate_bullets(skill: str) -> list[str]:
            section = skill.split("## Mandatory Development Gate", 1)[1]
            section = section.split("Emit a separate visible review", 1)[0]
            return [
                line[2:].strip()
                for line in section.splitlines()
                if line.startswith("- ")
            ]

        def normalize(text: str) -> str:
            """Fold hyphen/space differences so `data-pipeline` in the English
            restatement matches the canonical `data pipeline`."""
            return re.sub(r"[-\s]+", " ", text).lower()

        # canonical bullet -> (Chinese trigger tokens, English trigger tokens)
        coverage: dict[str, dict[str, tuple[tuple[str, ...], tuple[str, ...]]]] = {
            "book-ddia-data-design": {
                "Persisted or shared data, databases, schemas, or migrations.": (
                    ("持久化 / 共享数据", "schema / migration"),
                    ("persisted / shared data", "schema / migration"),
                ),
                "shared, persistent, cross-request, or cross-process caches; queues, events, streams, jobs, ETL, or analytics pipelines.": (
                    (
                        "cross-request / cross-process cache",
                        "queue / event / stream / job",
                        "ETL / analytics",
                    ),
                    (
                        "cross-request / cross-process cache",
                        "queue / event / stream / job",
                        "ETL / analytics",
                    ),
                ),
                "Cross-service data flow or API ownership.": (
                    ("跨服务数据流", "API 所有权"),
                    ("cross-service data flow", "API ownership"),
                ),
                "Data ownership, source of truth, transaction boundaries, or read / write paths.": (
                    ("数据所有权", "source of truth", "事务边界", "读写路径"),
                    (
                        "data ownership",
                        "source of truth",
                        "transaction boundaries",
                        "read / write paths",
                    ),
                ),
                "Backfill, replay, rollback, or recovery behavior.": (
                    ("backfill / replay / rollback / recovery",),
                    ("backfill / replay / rollback / recovery",),
                ),
            },
            "book-release-readiness": {
                "Service, API, auth, billing, or notification behavior.": (
                    ("service", "API", "auth", "billing", "notification"),
                    ("service", "API", "auth", "billing", "notification"),
                ),
                "Background job, queue, scheduler, or data pipeline.": (
                    ("background job", "queue", "scheduler", "data pipeline"),
                    ("background job", "queue", "scheduler", "data pipeline"),
                ),
                "External integration.": (("外部集成",), ("external integration",)),
                "Deployment, rollout, migration, or runtime operational behavior.": (
                    ("deployment", "rollout", "migration", "runtime 运维行为"),
                    (
                        "deployment",
                        "rollout",
                        "migration",
                        "runtime operational behavior",
                    ),
                ),
            },
        }

        for skill_name, mapping in coverage.items():
            canonical = (skills_root / skill_name / "SKILL.md").read_text(
                encoding="utf-8"
            )
            bullets = gate_bullets(canonical)
            self.assertTrue(bullets, f"{skill_name} declares no gate triggers")
            # Every canonical trigger must be mapped, so a new bullet cannot be
            # added to the Skill without also being restated in the rule files.
            self.assertEqual(
                sorted(bullets),
                sorted(mapping),
                f"{skill_name} gate triggers are not all covered below",
            )

            # The routing row is the only place a trigger token counts, so
            # locate exactly one row per source before asserting tokens.
            rows = {
                "AGENTS.global.md": [
                    line
                    for line in global_agents.splitlines()
                    if line.startswith(f"| `{skill_name}` |")
                ],
                "AGENTS.project.md": [
                    line
                    for line in project_agents.splitlines()
                    if f"`{skill_name}`" in line and "任一命中" in line
                ],
                "trellis-workflow": [
                    line
                    for line in trellis.splitlines()
                    if line.startswith(f"- `{skill_name}`:")
                ],
            }
            for label, matched in rows.items():
                with self.subTest(skill=skill_name, source=label, check="one row"):
                    self.assertEqual(
                        len(matched),
                        1,
                        f"{label} must carry exactly one {skill_name} routing row",
                    )

            for bullet, (chinese, english) in mapping.items():
                for label, tokens in (
                    ("AGENTS.global.md", chinese),
                    ("AGENTS.project.md", chinese),
                    ("trellis-workflow", english),
                ):
                    row = normalize(rows[label][0])
                    for token in tokens:
                        with self.subTest(
                            skill=skill_name,
                            trigger=bullet,
                            source=label,
                            token=token,
                        ):
                            self.assertIn(
                                normalize(token),
                                row,
                                f"{label} {skill_name} row drops trigger {token!r}",
                            )

    def test_book_gate_fallbacks_match_across_both_self_contained_sources(
        self,
    ) -> None:
        """Either AGENTS file may be the only one loaded, so both must resolve
        an unavailable Skill the same way: a mandatory gate degrades to
        `blocked`, and only a non-mandatory Skill may be skipped."""
        agents_root = ROOT / "sbtd-workflow-onboard" / "templates" / "agents"
        global_agents = (agents_root / "AGENTS.global.md").read_text(encoding="utf-8")
        project_agents = (agents_root / "AGENTS.project.md").read_text(encoding="utf-8")

        for document, label in (
            (global_agents, "AGENTS.global.md"),
            (project_agents, "AGENTS.project.md"),
        ):
            with self.subTest(source=label):
                self.assertIn("不可用", document)
                self.assertIn("`blocked`", document)
                self.assertIn("不阻塞任务", document)
                # The pre-gate wording let any missing Skill be skipped.
                self.assertNotIn("- 直接跳过。\n- 不要阻塞任务。", document)

        unavailable = global_agents.split("### Skill 不可用时", 1)[1]
        self.assertIn("已命中强制门禁：不得直接跳过", unavailable)
        self.assertIn("`blocked`", unavailable)
        self.assertIn("未命中强制门禁的普通按需 Skill", unavailable)

        self.assertIn(
            "`book-ddd-distilled-modeling` 不可用时记为 `blocked`", project_agents
        )
        self.assertIn("不冒充 Skill 审核", project_agents)

    def test_trellis_dispatch_layers_remain_distinct(self) -> None:
        onboard_root = ROOT / "sbtd-workflow-onboard"
        agents_root = onboard_root / "templates" / "agents"
        skills_root = onboard_root / "templates" / "skills"
        global_agents = (agents_root / "AGENTS.global.md").read_text(encoding="utf-8")
        project_agents = (agents_root / "AGENTS.project.md").read_text(
            encoding="utf-8"
        )
        workflow = (skills_root / "trellis-workflow" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        channel = (skills_root / "trellis-channel" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        _, codex_multi_agent = channel.split("## Codex Multi-Agent", 1)
        codex_multi_agent = codex_multi_agent.split("\n---", 1)[0]
        entrypoint = (ROOT / "ENTRYPOINT.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme_html = (ROOT / "README.html").read_text(encoding="utf-8")
        automation = (
            ROOT
            / "prompts"
            / "automations"
            / "sbtd-workflow-tools-version-check.md"
        ).read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

        self.assertIn("只定义共享 workflow gate，不标识运行平台", global_agents)
        self.assertIn("当前 host 为 Codex 且 `.codex/**` 集成可用", global_agents)
        self.assertIn("由主会话协调 phase", global_agents)
        self.assertIn("非法显式 Codex dispatch 值也会 fail-closed", global_agents)
        self.assertIn("当前 host 为 OMP 且 `.omp/**` 集成可用", global_agents)
        self.assertIn("OMP 自己的 `task` worker", global_agents)
        self.assertIn("不得读取、写入或推断 `codex.dispatch_mode`", global_agents)
        self.assertIn("同一变更职责只能有一个写入执行者", global_agents)
        self.assertIn("独立只读 review / cross-validation 可并行进行", global_agents)
        # AGENTS.project.md is the minimal fallback: it states the platform
        # boundary in condensed form and leaves the per-host dispatch detail to
        # the global rules asserted above.
        self.assertIn(
            "`.trellis/**` 只定义共享 workflow gate，不标识 host", project_agents
        )
        self.assertIn(
            "Codex 只解释 `.codex/**` 和有效 `codex.dispatch_mode`", project_agents
        )
        self.assertIn("OMP 只解释 `.omp/**` 与生成 worker", project_agents)
        self.assertIn("两者不得互相套用", project_agents)
        self.assertIn(
            "每项变更只有一个 writer，每个验证环境只有一个 controller", project_agents
        )
        self.assertIn(
            "显式 `codex.dispatch_mode` 取值非法时 fail-closed 到 Inline",
            project_agents,
        )
        self.assertIn("Shared `.trellis/config.yaml`, `.trellis/workflow.md`, and task artifacts define workflow gates, not platform identity.", workflow)
        self.assertIn("**Codex only, when the current host is Codex", workflow)
        self.assertIn("**OMP, when the current host is OMP", workflow)
        self.assertIn("Do not apply or infer `codex.dispatch_mode`", workflow)
        self.assertIn("obey its workflow planning gate instead", workflow)
        self.assertIn(
            "User-requested independent read-only review and cross-validation may run in parallel",
            workflow,
        )
        self.assertIn(
            "A Trellis-managed platform role sub-agent alone is not a Channel trigger.",
            channel,
        )
        self.assertIn(
            "User-requested independent read-only review and cross-validation workers may run in parallel",
            channel,
        )
        self.assertNotIn(
            "Use the Codex inline main session for ordinary Trellis tasks.",
            codex_multi_agent,
        )
        self.assertIn(
            "In a current Codex host with `.codex/**` integration",
            codex_multi_agent,
        )
        self.assertIn("Codex phase dispatch", entrypoint)
        self.assertIn("OMP phase dispatch", entrypoint)
        self.assertIn("Platform identity", entrypoint)
        self.assertIn("当前 host 与其 `.codex/**` / `.omp/**` 生成资产决定本次执行", entrypoint)
        self.assertIn("当前 host 与其专属生成资产决定本次执行", readme)
        self.assertIn("当前 host 与其 <code>.codex/**</code> 或 <code>.omp/**</code> 生成资产决定本次执行", readme_html)
        self.assertIn("Platform identity comes from the current host and its generated integration", channel)
        self.assertIn("OMP `task` worker", readme)
        self.assertIn("OMP <code>task</code> worker", readme_html)
        self.assertIn(
            "仅当前 Codex host 且 <code>.codex/**</code> 集成可用时",
            readme_html,
        )
        self.assertIn(
            "仅当前 OMP host 且 <code>.omp/**</code> 集成可用时",
            readme_html,
        )
        self.assertIn(
            "GitHub release body 缺失、为空或明显不足以判断变更",
            automation,
        )
        self.assertIn(
            "目标 stable tag 的有效配置、workflow 模板和 migration manifest",
            automation,
        )
        self.assertIn(
            "缺少任一项时不得形成或更新平台调度规则",
            automation,
        )
        self.assertIn("区分“已配置平台目录”与“当前 host”", automation)
        self.assertIn(
            "release notes 或其他官方 tagged evidence",
            automation,
        )
        self.assertIn("Trellis 的平台调度边界", changelog)

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
        self.assertIn("恢复为 `.DS_Store`、`.gitnexus/`、`.trellis/`、`__pycache__/` 四行", repository_lesson)
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


if __name__ == "__main__":
    unittest.main()
