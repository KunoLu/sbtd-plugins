from __future__ import annotations

import argparse
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from typing import cast
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
ONBOARD = ROOT / "sbtd-workflow-onboard" / "scripts" / "onboard.py"
SKILL_DIR = ROOT / "sbtd-workflow-onboard"
STABLE_ROOT = SKILL_DIR / "assets" / "external-skills" / "stable"
TEMPLATES_DIR = SKILL_DIR / "templates"

PONYTAIL_SKILLS = ("ponytail", "ponytail-review", "ponytail-audit", "ponytail-debt")
PONYTAIL_REPO = "https://github.com/DietrichGebert/ponytail.git"
PONYTAIL_REVISION = "2ed6c52c9d7e5e56942508591085fd45dea277d3"
PONYTAIL_STABLE_SET = "2026-08-27.1"


class PonytailModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module_counter = 0

    def load_onboard_module(self):
        self.module_counter += 1
        module_name = f"onboard_ponytail_test_{id(self)}_{self.module_counter}"
        spec = importlib.util.spec_from_file_location(module_name, ONBOARD)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load onboard module from {ONBOARD}")
        loader = cast(importlib.machinery.SourceFileLoader, spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        self.addCleanup(sys.modules.pop, module_name, None)
        loader.exec_module(module)
        return module


class PonytailCatalogTests(PonytailModuleTests):
    def test_catalog_registers_four_required_ponytail_external_skills(self) -> None:
        onboard = self.load_onboard_module()

        self.assertEqual(len(onboard.EXTERNAL_SKILL_SOURCES), 18)
        for name in PONYTAIL_SKILLS:
            source = onboard.EXTERNAL_SKILL_SOURCES[name]
            self.assertEqual(source["repo"], PONYTAIL_REPO)
            self.assertEqual(source["subpath"], f"skills/{name}")
        for name in PONYTAIL_SKILLS:
            self.assertIn(name, onboard.REFERENCED_SKILLS)
        self.assertEqual(
            set(onboard.EXTERNAL_SKILL_SOURCES), set(onboard.REFERENCED_SKILLS)
        )

    def test_stable_manifest_contains_ponytail_snapshot(self) -> None:
        manifest = json.loads(
            (STABLE_ROOT / "MANIFEST.json").read_text(encoding="utf-8")
        )

        self.assertEqual(manifest["stableSet"], PONYTAIL_STABLE_SET)
        repository = manifest["repositories"]["ponytail"]
        self.assertEqual(repository["url"], PONYTAIL_REPO)
        self.assertEqual(repository["revision"], PONYTAIL_REVISION)
        self.assertEqual(repository["license"], "MIT")
        self.assertEqual(
            repository["licenseFiles"],
            [{"source": "LICENSE", "stablePath": "licenses/ponytail-LICENSE"}],
        )
        self.assertEqual(len(manifest["repositories"]), 5)
        self.assertEqual(len(manifest["skills"]), 18)
        for name in PONYTAIL_SKILLS:
            entry = manifest["skills"][name]
            self.assertEqual(entry["repository"], "ponytail")
            self.assertEqual(entry["sourceSubpath"], f"skills/{name}")
            self.assertEqual(entry["stablePath"], f"skills/{name}")
            self.assertRegex(entry["treeSha256"], r"^[0-9a-f]{64}$")
            skill_md = STABLE_ROOT / "skills" / name / "SKILL.md"
            self.assertTrue(skill_md.is_file(), f"missing stable Skill: {name}")
        self.assertTrue(
            (STABLE_ROOT / "licenses" / "ponytail-LICENSE").is_file(),
            "missing vendored Ponytail MIT license",
        )
        notices = (STABLE_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("DietrichGebert/ponytail", notices)
        self.assertIn("licenses/ponytail-LICENSE", notices)


class PonytailPromotionSeamTests(PonytailModuleTests):
    def setUp(self) -> None:
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory(prefix="sbtd-ponytail-promotion-")
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def write_stable_root_without_ponytail(self) -> tuple[Path, Path]:
        stable_root = self.root / "stable"
        shutil.copytree(STABLE_ROOT, stable_root)
        for name in PONYTAIL_SKILLS:
            shutil.rmtree(stable_root / "skills" / name, ignore_errors=True)
        manifest_path = stable_root / "MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["repositories"].pop("ponytail", None)
        for name in PONYTAIL_SKILLS:
            manifest["skills"].pop(name, None)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        # A true pre-Ponytail baseline has neither the vendored license nor the
        # attribution row, so the test proves promotion recreates both.
        (stable_root / "licenses" / "ponytail-LICENSE").unlink(missing_ok=True)
        notice_path = stable_root / "THIRD_PARTY_NOTICES.md"
        notice_lines = notice_path.read_text(encoding="utf-8").splitlines()
        notice_path.write_text(
            "\n".join(
                line
                for line in notice_lines
                if not line.startswith("| `DietrichGebert/ponytail` |")
            )
            + "\n",
            encoding="utf-8",
        )
        return stable_root, manifest_path

    def write_fake_ponytail_repo(self) -> Path:
        repo = self.root / "ponytail-upstream"
        for name in PONYTAIL_SKILLS:
            skill_dir = repo / "skills" / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: fixture\n---\n\nfixture\n",
                encoding="utf-8",
            )
        (repo / "LICENSE").write_text("MIT License fixture\n", encoding="utf-8")
        return repo

    def fake_clone(self, repo: Path):
        def clone(_url, _revision, destination):
            shutil.copytree(repo, destination, dirs_exist_ok=True)
            return True, ""

        return clone

    def promotion_args(self, **overrides) -> argparse.Namespace:
        values = {
            "repository": "ponytail",
            "repo": PONYTAIL_REPO,
            "revision": PONYTAIL_REVISION,
            "stable_set": PONYTAIL_STABLE_SET,
            "license": "MIT",
            "license_files": ["LICENSE=licenses/ponytail-LICENSE"],
            "yes": True,
            "json": True,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def run_promotion(self, onboard, stable_root: Path, manifest_path: Path,
                      repo: Path, args: argparse.Namespace) -> tuple[int, dict]:
        stdout = io.StringIO()
        with (
            mock.patch.object(onboard, "EXTERNAL_STABLE_ROOT", stable_root),
            mock.patch.object(onboard, "EXTERNAL_STABLE_MANIFEST", manifest_path),
            mock.patch.object(
                onboard, "clone_repo_at_revision", side_effect=self.fake_clone(repo)
            ),
            contextlib.redirect_stdout(stdout),
        ):
            try:
                status = onboard.promote_external_skills_stable(args)
            except SystemExit:
                return 2, {}
        output = stdout.getvalue().strip()
        payload = json.loads(output) if output.startswith("{") else {}
        return status, payload

    def test_promotion_registers_new_repository_from_catalog(self) -> None:
        onboard = self.load_onboard_module()
        stable_root, manifest_path = self.write_stable_root_without_ponytail()
        repo = self.write_fake_ponytail_repo()

        status, payload = self.run_promotion(
            onboard, stable_root, manifest_path, repo, self.promotion_args()
        )

        self.assertEqual(status, 0, payload.get("error"))
        self.assertEqual(payload["status"], "promoted")
        self.assertEqual(sorted(payload["promotedSkills"]), sorted(PONYTAIL_SKILLS))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        repository = manifest["repositories"]["ponytail"]
        self.assertEqual(repository["url"], PONYTAIL_REPO)
        self.assertEqual(repository["revision"], PONYTAIL_REVISION)
        self.assertEqual(repository["license"], "MIT")
        self.assertEqual(
            repository["licenseFiles"],
            [{"source": "LICENSE", "stablePath": "licenses/ponytail-LICENSE"}],
        )
        self.assertEqual(len(manifest["skills"]), 18)
        for name in PONYTAIL_SKILLS:
            entry = manifest["skills"][name]
            self.assertEqual(entry["sourceSubpath"], f"skills/{name}")
            self.assertEqual(entry["stablePath"], f"skills/{name}")
            self.assertTrue((stable_root / "skills" / name / "SKILL.md").is_file())
        self.assertTrue(
            (stable_root / "licenses" / "ponytail-LICENSE").is_file()
        )
        notice_text = (stable_root / "THIRD_PARTY_NOTICES.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "| `DietrichGebert/ponytail` | MIT | `licenses/ponytail-LICENSE` |",
            notice_text,
        )
        self.assertEqual(manifest["stableSet"], PONYTAIL_STABLE_SET)

    def test_promotion_rejects_stale_extra_manifest_skill(self) -> None:
        onboard = self.load_onboard_module()
        stable_root = self.root / "stable"
        shutil.copytree(STABLE_ROOT, stable_root)
        manifest_path = stable_root / "MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        original_stable_set = manifest["stableSet"]
        stale_dir = stable_root / "skills" / "stale-retired-skill"
        stale_dir.mkdir(parents=True)
        (stale_dir / "SKILL.md").write_text(
            "---\nname: stale-retired-skill\ndescription: fixture\n---\n\nfixture\n",
            encoding="utf-8",
        )
        manifest["skills"]["stale-retired-skill"] = {
            "repository": "mattpocock-skills",
            "sourceSubpath": "skills/engineering/tdd",
            "stablePath": "skills/stale-retired-skill",
            "treeSha256": "0" * 64,
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        fake_repo = self.root / "promotion-repo"
        shutil.copytree(
            STABLE_ROOT / "skills" / "ui-ux-pro-max",
            fake_repo / ".claude" / "skills" / "ui-ux-pro-max",
        )
        shutil.copy2(
            STABLE_ROOT / "licenses" / "ui-ux-pro-max-skill-LICENSE",
            fake_repo / "LICENSE",
        )

        def fake_clone(_url, _revision, destination):
            shutil.copytree(fake_repo, destination, dirs_exist_ok=True)
            return True, ""

        args = self.promotion_args(
            repository="ui-ux-pro-max-skill",
            repo=None,
            license=None,
            license_files=None,
            stable_set="2026-08-26.2",
        )
        stdout = io.StringIO()
        with (
            mock.patch.object(onboard, "EXTERNAL_STABLE_ROOT", stable_root),
            mock.patch.object(onboard, "EXTERNAL_STABLE_MANIFEST", manifest_path),
            mock.patch.object(
                onboard, "clone_repo_at_revision", side_effect=fake_clone
            ),
            contextlib.redirect_stdout(stdout),
        ):
            status = onboard.promote_external_skills_stable(args)

        self.assertNotEqual(status, 0)
        payload = json.loads(stdout.getvalue())
        self.assertIn("extra=['stale-retired-skill']", payload["error"])
        self.assertEqual(
            json.loads(manifest_path.read_text(encoding="utf-8"))["stableSet"],
            original_stable_set,
        )
        self.assertIn("stale-retired-skill", manifest["skills"])

    def test_promotion_new_repository_requires_registration_metadata(self) -> None:
        onboard = self.load_onboard_module()
        stable_root, manifest_path = self.write_stable_root_without_ponytail()
        repo = self.write_fake_ponytail_repo()
        before = manifest_path.read_text(encoding="utf-8")

        for overrides in (
            {"repo": None},
            {"license": None},
            {"license_files": None},
            {"license_files": []},
        ):
            with self.subTest(overrides=overrides):
                status, _payload = self.run_promotion(
                    onboard,
                    stable_root,
                    manifest_path,
                    repo,
                    self.promotion_args(**overrides),
                )
                self.assertNotEqual(status, 0)
                self.assertEqual(manifest_path.read_text(encoding="utf-8"), before)
                for name in PONYTAIL_SKILLS:
                    self.assertFalse((stable_root / "skills" / name).exists())

    def test_promotion_rejects_malformed_license_file_mapping(self) -> None:
        onboard = self.load_onboard_module()
        stable_root, manifest_path = self.write_stable_root_without_ponytail()
        repo = self.write_fake_ponytail_repo()
        before = manifest_path.read_text(encoding="utf-8")

        status, _payload = self.run_promotion(
            onboard,
            stable_root,
            manifest_path,
            repo,
            self.promotion_args(license_files=["LICENSE"]),
        )

        self.assertNotEqual(status, 0)
        self.assertEqual(manifest_path.read_text(encoding="utf-8"), before)

    def test_promotion_existing_repository_rejects_mismatched_repo_url(self) -> None:
        onboard = self.load_onboard_module()
        stable_root, manifest_path = self.write_stable_root_without_ponytail()
        repo = self.write_fake_ponytail_repo()
        before = manifest_path.read_text(encoding="utf-8")

        status, _payload = self.run_promotion(
            onboard,
            stable_root,
            manifest_path,
            repo,
            self.promotion_args(
                repository="mattpocock-skills",
                repo="https://github.com/example/other.git",
                license=None,
                license_files=None,
            ),
        )

        self.assertNotEqual(status, 0)
        self.assertEqual(manifest_path.read_text(encoding="utf-8"), before)

    def test_promotion_existing_repository_rejects_license_override(self) -> None:
        onboard = self.load_onboard_module()
        stable_root, manifest_path = self.write_stable_root_without_ponytail()
        repo = self.write_fake_ponytail_repo()
        before = manifest_path.read_text(encoding="utf-8")

        status, _payload = self.run_promotion(
            onboard,
            stable_root,
            manifest_path,
            repo,
            self.promotion_args(
                repository="mattpocock-skills",
                repo=None,
                license="Apache-2.0",
                license_files=None,
            ),
        )

        self.assertNotEqual(status, 0)
        self.assertEqual(manifest_path.read_text(encoding="utf-8"), before)


class PonytailProviderHelperTests(PonytailModuleTests):
    def test_repo_identity_normalization_variants(self) -> None:
        onboard = self.load_onboard_module()
        expected = "github.com/dietrichgebert/ponytail"
        variants = [
            "https://github.com/DietrichGebert/ponytail.git",
            "https://github.com/DietrichGebert/ponytail",
            "http://github.com/DietrichGebert/ponytail.git",
            "ssh://git@github.com/DietrichGebert/ponytail.git",
            "git+ssh://git@github.com/DietrichGebert/ponytail.git",
            "git@github.com:DietrichGebert/ponytail.git",
            "git:github.com/DietrichGebert/ponytail",
            "github.com/DietrichGebert/ponytail.git/",
            "GitHub.com/DietrichGebert/Ponytail.git",
        ]
        for value in variants:
            with self.subTest(value=value):
                self.assertEqual(
                    onboard.normalized_ponytail_repo_identity(value), expected
                )

    def test_list_platform_plugins_handles_timeout_nonzero_and_malformed(self) -> None:
        onboard = self.load_onboard_module()
        with (
            mock.patch.object(onboard.shutil, "which", return_value="/fake/codex"),
            mock.patch.object(
                onboard.subprocess,
                "run",
                side_effect=onboard.subprocess.TimeoutExpired("codex", 10),
            ),
        ):
            self.assertEqual(onboard.list_platform_plugins("codex"), ("cli-unavailable", []))

        nonzero = subprocess.CompletedProcess(
            ["codex"], 1, stdout='[{"name": "ponytail"}]', stderr=""
        )
        with (
            mock.patch.object(onboard.shutil, "which", return_value="/fake/codex"),
            mock.patch.object(onboard.subprocess, "run", return_value=nonzero),
        ):
            self.assertEqual(onboard.list_platform_plugins("codex"), ("cli-unavailable", []))

        malformed = subprocess.CompletedProcess(["codex"], 0, stdout="not json", stderr="")
        with (
            mock.patch.object(onboard.shutil, "which", return_value="/fake/codex"),
            mock.patch.object(onboard.subprocess, "run", return_value=malformed),
        ):
            self.assertEqual(onboard.list_platform_plugins("codex"), ("cli-unavailable", []))

    def test_list_platform_plugins_preserves_map_identities(self) -> None:
        onboard = self.load_onboard_module()
        payload = subprocess.CompletedProcess(
            ["codex"], 0, stdout='{"ponytail@ponytail": {"enabled": true}}', stderr=""
        )
        with (
            mock.patch.object(onboard.shutil, "which", return_value="/fake/codex"),
            mock.patch.object(onboard.subprocess, "run", return_value=payload),
        ):
            status, records = onboard.list_platform_plugins("codex")
        self.assertEqual(status, "ok")
        self.assertEqual(records[0]["id"], "ponytail@ponytail")
        self.assertTrue(onboard.is_official_ponytail_plugin("codex", records[0]))

        wrapped = subprocess.CompletedProcess(
            ["codex"],
            0,
            stdout='{"plugins": {"ponytail@ponytail": {"enabled": true}}}',
            stderr="",
        )
        with (
            mock.patch.object(onboard.shutil, "which", return_value="/fake/codex"),
            mock.patch.object(onboard.subprocess, "run", return_value=wrapped),
        ):
            status, records = onboard.list_platform_plugins("codex")
        self.assertEqual(status, "ok")
        self.assertTrue(onboard.is_official_ponytail_plugin("codex", records[0]))

    def test_conflict_takes_precedence_over_unavailable_cli(self) -> None:
        onboard = self.load_onboard_module()

        def fake_list(platform_name: str):
            if platform_name == "codex":
                return "ok", [{"id": "ponytail@ponytail", "enabled": True}]
            return "cli-unavailable", []

        with mock.patch.object(
            onboard, "list_platform_plugins", side_effect=fake_list
        ):
            provider = onboard.detect_ponytail_provider(Path("/nonexistent-skills"))
        self.assertEqual(provider["provider"], "conflict")
        self.assertEqual(provider["pluginStatus"], "installed-enabled")


class PonytailProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="sbtd-ponytail-provider-")
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.skills_dir = self.root / "skills"
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.env = os.environ.copy()
        self.env["HOME"] = str(self.home)
        self.env["PATH"] = os.pathsep.join((str(self.bin_dir), "/usr/bin", "/bin"))
        # A fake npm keeps check_npm_runtime from prepending the machine's nvm
        # bin directory (and its real codex/omp binaries) to PATH.
        self.write_executable(
            "npm",
            """
            #!/bin/sh
            if [ "$1" = "--version" ]; then
              printf '10.9.0\\n'
            fi
            exit 0
            """,
        )

    def write_executable(self, name: str, body: str) -> Path:
        target = self.bin_dir / name
        target.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IXUSR)
        return target

    def write_fake_plugin_cli(self, name: str, payload: str, exit_code: int = 0) -> None:
        if name == "omp":
            (self.home / ".omp").mkdir(exist_ok=True)
        self.write_executable(
            name,
            f"""
            #!/bin/sh
            if [ "$1" = "plugin" ] && [ "$2" = "list" ]; then
              printf '%s\n' '{payload}'
              exit {exit_code}
            fi
            exit 64
            """,
        )

    def run_onboard(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (sys.executable, str(ONBOARD), *args),
            check=False,
            capture_output=True,
            text=True,
            env=self.env,
            timeout=60,
        )

    def run_check(self) -> tuple[int, dict]:
        completed = self.run_onboard(
            "check",
            "--global-skills-dir",
            str(self.skills_dir),
            "--json",
        )
        return completed.returncode, json.loads(completed.stdout)

    def test_check_fails_with_conflict_when_codex_plugin_enabled(self) -> None:
        self.write_fake_plugin_cli(
            "codex", '[{"id": "ponytail@ponytail", "enabled": true}]'
        )

        returncode, payload = self.run_check()

        self.assertEqual(returncode, 4)
        provider = payload["ponytailProvider"]
        self.assertEqual(provider["provider"], "conflict")
        self.assertEqual(provider["pluginStatus"], "installed-enabled")
        self.assertEqual(provider["nextStep"], "disable-or-remove-plugin")
        self.assertEqual(provider["requiredSkills"], list(PONYTAIL_SKILLS))

    def test_check_fails_with_conflict_when_omp_plugin_enabled(self) -> None:
        self.write_fake_plugin_cli(
            "omp",
            '[{"name": "ponytail", "source": "git:github.com/DietrichGebert/ponytail",'
            ' "enabled": true}]',
        )

        returncode, payload = self.run_check()

        self.assertEqual(returncode, 4)
        provider = payload["ponytailProvider"]
        self.assertEqual(provider["provider"], "conflict")
        self.assertEqual(provider["pluginStatus"], "installed-enabled")

    def test_check_reports_stable_provider_when_plugin_disabled(self) -> None:
        self.write_fake_plugin_cli(
            "codex", '[{"id": "ponytail@ponytail", "enabled": false}]'
        )
        self.write_fake_plugin_cli("omp", "[]")

        returncode, payload = self.run_check()

        self.assertEqual(returncode, 0)
        provider = payload["ponytailProvider"]
        self.assertEqual(provider["provider"], "onboard-stable")
        self.assertEqual(provider["pluginStatus"], "installed-disabled")
        self.assertEqual(provider["skillStatus"], "missing")
        self.assertEqual(provider["nextStep"], "install-required")

    def test_check_never_invokes_omp_cli_when_omp_root_absent(self) -> None:
        """`check` must stay read-only on a machine that never configured OMP.

        `omp plugin list --json` creates `~/.omp` as a side effect, so a probe
        that runs before checking the directory silently converts "OMP is not
        installed" into "OMP is installed but empty" -- and leaves state behind
        in the user's home directory.
        """
        marker = self.root / "omp-invoked"
        self.write_executable(
            "omp",
            f"""
            #!/bin/sh
            : > '{marker}'
            mkdir -p '{self.home}/.omp'
            printf '%s\n' '[]'
            exit 0
            """,
        )
        self.assertFalse((self.home / ".omp").exists())

        returncode, payload = self.run_check()

        self.assertEqual(returncode, 0)
        self.assertFalse(marker.exists(), "check invoked the OMP CLI")
        self.assertFalse((self.home / ".omp").exists(), "check created ~/.omp")
        self.assertEqual(
            payload["ponytailProvider"]["platforms"]["omp"]["status"],
            "not-configured",
        )

    def test_check_reports_unknown_when_plugin_cli_unavailable(self) -> None:
        returncode, payload = self.run_check()

        self.assertEqual(returncode, 0)
        provider = payload["ponytailProvider"]
        self.assertEqual(provider["provider"], "unknown")
        self.assertEqual(provider["pluginStatus"], "cli-unavailable")

    def test_check_ignores_unofficial_ponytail_named_plugins(self) -> None:
        self.write_fake_plugin_cli(
            "codex",
            '[{"id": "ponytail@other-marketplace", "enabled": true},'
            ' {"name": "ponytail-extra", "marketplace": "ponytail", "enabled": true}]',
        )
        self.write_fake_plugin_cli(
            "omp",
            '[{"name": "ponytail", "source": "github.com/example/ponytail-fork",'
            ' "enabled": true}]',
        )

        returncode, payload = self.run_check()

        self.assertEqual(returncode, 0)
        provider = payload["ponytailProvider"]
        self.assertEqual(provider["provider"], "onboard-stable")
        self.assertEqual(provider["pluginStatus"], "missing")

    def test_init_blocks_before_writing_stable_copies_on_conflict(self) -> None:
        self.write_fake_plugin_cli(
            "codex", '[{"id": "ponytail@ponytail", "enabled": true}]'
        )

        completed = self.run_onboard(
            "init",
            "--global-skills-dir",
            str(self.skills_dir),
            "--yes",
            "--json",
        )

        self.assertEqual(completed.returncode, 4)
        self.assertIn("conflict", completed.stderr.lower())
        for name in PONYTAIL_SKILLS:
            self.assertFalse((self.skills_dir / name).exists())

    def test_reset_blocks_before_writing_stable_copies_on_conflict(self) -> None:
        self.write_fake_plugin_cli(
            "codex", '[{"id": "ponytail@ponytail", "enabled": true}]'
        )

        completed = self.run_onboard(
            "reset",
            "--global-skills-dir",
            str(self.skills_dir),
            "--yes",
            "--json",
        )

        self.assertEqual(completed.returncode, 4)
        self.assertIn("conflict", completed.stderr.lower())
        for name in PONYTAIL_SKILLS:
            self.assertFalse((self.skills_dir / name).exists())

    def test_check_flags_codex_map_payload_with_enabled_plugin(self) -> None:
        self.write_fake_plugin_cli(
            "codex", '{"ponytail@ponytail": {"enabled": true}}'
        )

        returncode, payload = self.run_check()

        self.assertEqual(returncode, 4)
        self.assertEqual(payload["ponytailProvider"]["provider"], "conflict")

    def test_check_flags_wrapped_map_payload_with_enabled_plugin(self) -> None:
        self.write_fake_plugin_cli(
            "codex", '{"plugins": {"ponytail@ponytail": {"enabled": true}}}'
        )

        returncode, payload = self.run_check()

        self.assertEqual(returncode, 4)
        self.assertEqual(payload["ponytailProvider"]["provider"], "conflict")

    def test_check_flags_omp_ssh_install_spec_with_enabled_plugin(self) -> None:
        self.write_fake_plugin_cli(
            "omp",
            '[{"name": "ponytail",'
            ' "installSpec": "ssh://git@github.com/DietrichGebert/ponytail.git",'
            ' "enabled": true}]',
        )

        returncode, payload = self.run_check()

        self.assertEqual(returncode, 4)
        self.assertEqual(payload["ponytailProvider"]["provider"], "conflict")

    def write_valid_ponytail_skill(self, name: str) -> None:
        target = self.skills_dir / name
        target.mkdir(parents=True, exist_ok=True)
        (target / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: fixture\n---\n\nfixture\n",
            encoding="utf-8",
        )

    def test_check_reports_partial_skill_state(self) -> None:
        self.write_fake_plugin_cli("codex", "[]")
        self.write_fake_plugin_cli("omp", "[]")
        self.write_valid_ponytail_skill("ponytail")
        self.write_valid_ponytail_skill("ponytail-review")

        returncode, payload = self.run_check()

        self.assertEqual(returncode, 0)
        provider = payload["ponytailProvider"]
        self.assertEqual(provider["skillStatus"], "partial")
        self.assertEqual(provider["nextStep"], "repair-required")

    def test_check_reports_invalid_skill_state(self) -> None:
        self.write_fake_plugin_cli("codex", "[]")
        self.write_fake_plugin_cli("omp", "[]")
        broken = self.skills_dir / "ponytail"
        broken.mkdir(parents=True)
        (broken / "SKILL.md").write_text("garbage\n", encoding="utf-8")

        returncode, payload = self.run_check()

        self.assertEqual(returncode, 0)
        provider = payload["ponytailProvider"]
        self.assertEqual(provider["skillStatus"], "invalid")
        self.assertEqual(provider["nextStep"], "repair-required")

    def test_check_reports_dangling_symlink_as_invalid(self) -> None:
        self.write_fake_plugin_cli("codex", "[]")
        self.write_fake_plugin_cli("omp", "[]")
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        (self.skills_dir / "ponytail").symlink_to(
            self.skills_dir / "missing-target"
        )

        returncode, payload = self.run_check()

        self.assertEqual(returncode, 0)
        provider = payload["ponytailProvider"]
        self.assertEqual(provider["skillStatus"], "invalid")
        self.assertEqual(provider["nextStep"], "repair-required")


class PonytailWorkflowContractTests(unittest.TestCase):
    def test_global_agents_contains_code_readability_and_ponytail_routing(self) -> None:
        content = (TEMPLATES_DIR / "agents" / "AGENTS.global.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("## 代码可读性", content)
        self.assertIn("可读性与可维护性优先于减少源码行数", content)
        self.assertIn("浅层包装（shallow wrappers）", content)
        self.assertIn("假想的端口（ports）", content)
        self.assertIn("`ponytail`", content)
        self.assertIn("`ponytail-review`", content)
        self.assertIn("`ponytail-audit`", content)
        self.assertIn("`ponytail-debt`", content)

    def test_project_agents_contains_minimal_readability_fallback(self) -> None:
        content = (TEMPLATES_DIR / "agents" / "AGENTS.project.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("代码可读性", content)
        self.assertIn("浅层包装（shallow wrappers）", content)
        self.assertIn("ponytail", content)

    def test_trellis_workflow_contains_ponytail_review_sequence(self) -> None:
        content = (TEMPLATES_DIR / "skills" / "trellis-workflow" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("ponytail", content)
        self.assertIn("ponytail-review", content)
        self.assertIn("Code Readability Review", content)

    def test_project_validation_does_not_carry_readability_rules(self) -> None:
        content = (
            TEMPLATES_DIR / "skills" / "project-validation" / "SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertNotIn("Code Readability", content)


if __name__ == "__main__":
    unittest.main()
