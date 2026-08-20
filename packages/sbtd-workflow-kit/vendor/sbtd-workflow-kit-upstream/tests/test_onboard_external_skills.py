from __future__ import annotations

import argparse
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
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


class ExternalSkillInstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="sbtd-external-skills-test-")
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.skills_dir = self.root / "skills"
        self.fake_repo = self.root / "upstream"
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.git_log = self.root / "git.log"
        self.env = os.environ.copy()
        self.env["HOME"] = str(self.home)
        self.env["FAKE_EXTERNAL_REPO"] = str(self.fake_repo)
        self.env["FAKE_GIT_LOG"] = str(self.git_log)
        self.env["PATH"] = os.pathsep.join((str(self.bin_dir), "/usr/bin", "/bin"))
        self.module_counter = 0

    def write_executable(self, name: str, body: str) -> Path:
        target = self.bin_dir / name
        target.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IXUSR)
        return target

    def write_fake_git(self, *, clone_succeeds: bool) -> None:
        status = "0" if clone_succeeds else "1"
        self.write_executable(
            "git",
            f"""
            #!/bin/sh
            printf '%s\n' "$*" >> "$FAKE_GIT_LOG"
            if [ "$1" = "clone" ]; then
              destination=""
              for argument in "$@"; do destination="$argument"; done
              if [ "{status}" -ne 0 ]; then
                printf 'simulated clone failure\n' >&2
                exit {status}
              fi
              mkdir -p "$destination"
              cp -R "$FAKE_EXTERNAL_REPO"/. "$destination"/
              exit 0
            fi
            if [ "$1" = "-C" ] && [ "$3" = "rev-parse" ]; then
              printf '1111111111111111111111111111111111111111\n'
              exit 0
            fi
            exit 0
            """,
        )

    def write_upstream_skill(self, name: str, marker: str) -> None:
        target = self.fake_repo / "skills" / "engineering" / name
        target.mkdir(parents=True, exist_ok=True)
        (target / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: fixture\n---\n\n{marker}\n",
            encoding="utf-8",
        )

    def write_existing_skill(self, name: str, marker: str) -> None:
        target = self.skills_dir / name
        target.mkdir(parents=True, exist_ok=True)
        (target / "SKILL.md").write_text(marker, encoding="utf-8")

    def write_valid_skill(self, root: Path, name: str, marker: str = "fixture") -> Path:
        root.mkdir(parents=True, exist_ok=True)
        (root / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: fixture\n---\n\n{marker}\n",
            encoding="utf-8",
        )
        return root

    def load_onboard_module(self):
        self.module_counter += 1
        module_name = f"onboard_external_test_{id(self)}_{self.module_counter}"
        spec = importlib.util.spec_from_file_location(module_name, ONBOARD)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load onboard module from {ONBOARD}")
        loader = cast(importlib.machinery.SourceFileLoader, spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        self.addCleanup(sys.modules.pop, module_name, None)
        loader.exec_module(module)
        return module

    def run_onboard(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (sys.executable, str(ONBOARD), *args),
            check=False,
            capture_output=True,
            text=True,
            env=self.env,
            timeout=30,
        )

    def install(self, skills: str, source: str) -> subprocess.CompletedProcess[str]:
        return self.run_onboard(
            "install-external-skills",
            "--skills",
            skills,
            "--source",
            source,
            "--global-skills-dir",
            str(self.skills_dir),
            "--yes",
            "--json",
        )

    def test_upstream_uses_repository_when_the_contract_is_valid(self) -> None:
        self.write_fake_git(clone_succeeds=True)
        self.write_upstream_skill("diagnosing-bugs", "upstream marker")

        completed = self.install("diagnosing-bugs", "upstream")

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        payload = json.loads(completed.stdout)
        result = next(
            item for item in payload["results"] if item.get("name") == "diagnosing-bugs"
        )
        self.assertEqual(result["sourceUsed"], "upstream")
        self.assertEqual(
            result["sourceRevision"], "1111111111111111111111111111111111111111"
        )
        self.assertIn(
            "upstream marker",
            (self.skills_dir / "diagnosing-bugs" / "SKILL.md").read_text(),
        )

    def test_auto_uses_vendored_stable_without_accessing_upstream(self) -> None:
        self.write_fake_git(clone_succeeds=True)
        self.write_upstream_skill("diagnosing-bugs", "upstream marker")

        completed = self.install("diagnosing-bugs", "auto")

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        payload = json.loads(completed.stdout)
        result = next(
            item for item in payload["results"] if item.get("name") == "diagnosing-bugs"
        )
        self.assertEqual(result["sourceUsed"], "stable")
        self.assertIsNone(result["fallbackReason"])
        self.assertTrue(result["stableSet"])
        self.assertFalse(self.git_log.exists())
        self.assertNotIn(
            "upstream marker",
            (self.skills_dir / "diagnosing-bugs" / "SKILL.md").read_text(),
        )

    def test_stable_mode_does_not_invoke_git(self) -> None:
        self.write_fake_git(clone_succeeds=False)

        completed = self.install("diagnosing-bugs", "stable")

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        payload = json.loads(completed.stdout)
        result = next(
            item for item in payload["results"] if item.get("name") == "diagnosing-bugs"
        )
        self.assertEqual(result["sourceUsed"], "stable")
        self.assertFalse(self.git_log.exists())

    def test_strict_upstream_failure_leaves_every_existing_target_unchanged(
        self,
    ) -> None:
        self.write_fake_git(clone_succeeds=True)
        self.write_upstream_skill("diagnosing-bugs", "new diagnosing-bugs")
        self.write_existing_skill("diagnosing-bugs", "old diagnosing-bugs")
        self.write_existing_skill("tdd", "old tdd")

        completed = self.install("diagnosing-bugs,tdd", "upstream")

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(
            (self.skills_dir / "diagnosing-bugs" / "SKILL.md").read_text(),
            "old diagnosing-bugs",
        )
        self.assertEqual((self.skills_dir / "tdd" / "SKILL.md").read_text(), "old tdd")

    def test_auto_uses_one_stable_set_for_the_whole_repository_group(self) -> None:
        self.write_fake_git(clone_succeeds=True)

        completed = self.install("diagnosing-bugs,tdd", "auto")

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        payload = json.loads(completed.stdout)
        installed = {
            item["name"]: item
            for item in payload["results"]
            if item.get("name") in {"diagnosing-bugs", "tdd"}
        }
        self.assertEqual(
            {item["sourceUsed"] for item in installed.values()}, {"stable"}
        )
        self.assertEqual(
            len({item["stableSet"] for item in installed.values()}), 1
        )
        self.assertFalse(self.git_log.exists())

    def test_stable_promotion_requires_explicit_confirmation(self) -> None:
        completed = self.run_onboard(
            "promote-external-skills-stable",
            "--repository",
            "mattpocock-skills",
            "--revision",
            "2" * 40,
            "--stable-set",
            "2099-01-01.1",
            "--json",
        )

        self.assertEqual(completed.returncode, 2)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["repository"], "mattpocock-skills")
        self.assertEqual(payload["revision"], "2" * 40)

    def test_complete_vendored_stable_set_installs_without_network(self) -> None:
        self.write_fake_git(clone_succeeds=False)

        completed = self.run_onboard(
            "install-external-skills",
            "--all",
            "--source",
            "stable",
            "--global-skills-dir",
            str(self.skills_dir),
            "--yes",
            "--json",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        payload = json.loads(completed.stdout)
        installed = [
            item for item in payload["results"] if item.get("phase") == "commit"
        ]
        catalog = json.loads(
            (ROOT / "sbtd-workflow-onboard" / "catalog.json").read_text(
                encoding="utf-8"
            )
        )
        expected_count = sum(
            entry["kind"] == "external-skill" for entry in catalog["entries"]
        )
        self.assertEqual(len(installed), expected_count)
        self.assertEqual({item["sourceUsed"] for item in installed}, {"stable"})
        self.assertTrue(
            all(
                (self.skills_dir / item["name"] / "SKILL.md").is_file()
                for item in installed
            )
        )
        self.assertFalse(self.git_log.exists())

    def test_stable_reset_install_replaces_retired_writing_skill(self) -> None:
        self.write_valid_skill(
            self.skills_dir / "writing-great-skills",
            "writing-great-skills",
            "retired canonical",
        )
        self.write_valid_skill(
            self.skills_dir / "write-a-skill",
            "write-a-skill",
            "older legacy alias",
        )

        completed = self.run_onboard(
            "install-external-skills",
            "--all",
            "--source",
            "stable",
            "--global-skills-dir",
            str(self.skills_dir),
            "--yes",
            "--json",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        payload = json.loads(completed.stdout)
        self.assertTrue(
            (self.skills_dir / "writing-for-agents" / "SKILL.md").is_file()
        )
        self.assertFalse((self.skills_dir / "writing-great-skills").exists())
        self.assertFalse((self.skills_dir / "write-a-skill").exists())
        self.assertTrue(
            any(
                item.get("name") == "writing-great-skills"
                and item.get("replacement") == "writing-for-agents"
                and item.get("status") == "removed"
                for item in payload["results"]
            )
        )

    def test_migrate_external_skills_installs_replacements_for_all_legacy_aliases(
        self,
    ) -> None:
        legacy_names = (
            "diagnose",
            "write-a-skill",
            "writing-great-skills",
            "to-prd",
            "to-issues",
            "zoom-out",
        )
        for name in legacy_names:
            self.write_valid_skill(self.skills_dir / name, name, "legacy")

        completed = self.run_onboard(
            "migrate-external-skills",
            "--source",
            "stable",
            "--global-skills-dir",
            str(self.skills_dir),
            "--yes",
            "--json",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "migrated")
        self.assertEqual(
            {
                item["name"]
                for item in payload["results"]
                if item.get("status") == "removed"
            },
            set(legacy_names),
        )
        for name in legacy_names:
            self.assertFalse((self.skills_dir / name).exists(), name)
        for name in (
            "diagnosing-bugs",
            "writing-for-agents",
            "to-spec",
            "to-tickets",
        ):
            self.assertTrue((self.skills_dir / name / "SKILL.md").is_file(), name)

    def test_migrate_external_skills_aborts_before_installing_on_identity_conflict(
        self,
    ) -> None:
        self.write_valid_skill(self.skills_dir / "diagnose", "diagnose", "legacy")
        self.write_valid_skill(
            self.skills_dir / "to-prd",
            "user-owned-to-prd",
            "must not be replaced",
        )

        completed = self.run_onboard(
            "migrate-external-skills",
            "--source",
            "stable",
            "--global-skills-dir",
            str(self.skills_dir),
            "--yes",
            "--json",
        )

        self.assertNotEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertTrue((self.skills_dir / "diagnose").exists())
        self.assertTrue((self.skills_dir / "to-prd").exists())
        self.assertFalse((self.skills_dir / "diagnosing-bugs").exists())
        self.assertTrue(
            any(
                item.get("name") == "to-prd"
                and item.get("status") == "failed"
                and item.get("phase") == "preflight-legacy-identity"
                for item in payload["results"]
            )
        )

    def test_migrate_external_skills_requires_confirmation_before_writes(
        self,
    ) -> None:
        self.write_valid_skill(self.skills_dir / "to-prd", "to-prd", "legacy")

        completed = self.run_onboard(
            "migrate-external-skills",
            "--source",
            "stable",
            "--global-skills-dir",
            str(self.skills_dir),
            "--json",
        )

        self.assertEqual(completed.returncode, 2, completed.stderr or completed.stdout)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "needs-confirmation")
        self.assertTrue((self.skills_dir / "to-prd").exists())
        self.assertFalse((self.skills_dir / "to-spec").exists())

    def test_stable_install_preserves_identity_conflicting_legacy_skill(self) -> None:
        self.write_valid_skill(
            self.skills_dir / "writing-great-skills",
            "user-owned-writing-skill",
            "must not be deleted",
        )

        completed = self.run_onboard(
            "install-external-skills",
            "--all",
            "--source",
            "stable",
            "--global-skills-dir",
            str(self.skills_dir),
            "--yes",
            "--json",
        )

        self.assertNotEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertFalse((self.skills_dir / "writing-for-agents").exists())
        self.assertTrue((self.skills_dir / "writing-great-skills").exists())
        self.assertTrue(
            any(
                item.get("name") == "writing-great-skills"
                and item.get("status") == "failed"
                and item.get("phase") == "preflight-legacy-identity"
                for item in payload["results"]
            )
        )
        self.assertEqual(list(self.skills_dir.glob(".sbtd-external-staging-*")), [])

    def test_reset_migration_removes_retired_writing_skill_when_replacement_exists(
        self,
    ) -> None:
        onboard = self.load_onboard_module()
        self.write_valid_skill(
            self.skills_dir / "writing-for-agents",
            "writing-for-agents",
            "replacement",
        )
        self.write_valid_skill(
            self.skills_dir / "writing-great-skills",
            "writing-great-skills",
            "retired canonical",
        )
        self.write_valid_skill(
            self.skills_dir / "write-a-skill",
            "write-a-skill",
            "older legacy alias",
        )

        plan = onboard.build_external_migration_plan(
            argparse.Namespace(global_skills_dir=str(self.skills_dir))
        )
        results = onboard.run_external_migration(plan)

        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["requiredCanonical"], ["writing-for-agents"])
        self.assertFalse((self.skills_dir / "writing-great-skills").exists())
        self.assertFalse((self.skills_dir / "write-a-skill").exists())
        self.assertEqual(
            {
                item["name"]
                for item in results
                if item.get("status") == "removed"
            },
            {"writing-great-skills", "write-a-skill"},
        )

    def test_reset_migration_preserves_identity_conflicting_legacy_skill(
        self,
    ) -> None:
        onboard = self.load_onboard_module()
        self.write_valid_skill(
            self.skills_dir / "writing-for-agents",
            "writing-for-agents",
            "replacement",
        )
        self.write_valid_skill(
            self.skills_dir / "writing-great-skills",
            "user-owned-writing-skill",
            "must not be deleted",
        )

        plan = onboard.build_external_migration_plan(
            argparse.Namespace(global_skills_dir=str(self.skills_dir))
        )
        results = onboard.run_external_migration(plan)

        self.assertTrue((self.skills_dir / "writing-great-skills").exists())
        self.assertTrue(
            any(
                item.get("name") == "writing-great-skills"
                and item.get("status") == "failed"
                and item.get("phase") == "preflight-legacy-identity"
                for item in results
            )
        )

    def test_reset_migration_rejects_dangling_legacy_symlink(self) -> None:
        onboard = self.load_onboard_module()
        self.write_valid_skill(
            self.skills_dir / "writing-for-agents",
            "writing-for-agents",
            "replacement",
        )
        legacy = self.skills_dir / "writing-great-skills"
        legacy.symlink_to(self.root / "missing-user-owned-skill")

        plan = onboard.build_external_migration_plan(
            argparse.Namespace(global_skills_dir=str(self.skills_dir))
        )
        results = onboard.run_external_migration(plan)

        self.assertEqual(plan["status"], "planned")
        self.assertTrue(legacy.is_symlink())
        self.assertTrue(
            any(
                item.get("name") == "writing-great-skills"
                and item.get("status") == "failed"
                and item.get("phase") == "preflight-legacy-identity"
                for item in results
            )
        )

    def test_rollback_failure_retains_the_only_backup_copy(self) -> None:
        onboard = self.load_onboard_module()
        self.write_valid_skill(
            self.skills_dir / "diagnosing-bugs", "diagnosing-bugs", "old"
        )
        staging = self.root / "staging"
        self.write_valid_skill(staging / "diagnosing-bugs", "diagnosing-bugs", "new")
        resolved = {
            "diagnosing-bugs": {
                "repo": "fixture",
                "sourceUsed": "upstream",
                "sourceRevision": "1" * 40,
                "stableSet": None,
                "fallbackReason": None,
            }
        }
        real_move = shutil.move
        move_count = 0

        def failing_move(source, destination):
            nonlocal move_count
            move_count += 1
            if move_count in {2, 3}:
                raise OSError("simulated commit/restore failure")
            return real_move(source, destination)

        with mock.patch.object(onboard.shutil, "move", side_effect=failing_move):
            _, transaction = onboard.commit_external_skill_transaction(
                ["diagnosing-bugs"], resolved, self.skills_dir, staging
            )

        self.assertEqual(transaction["status"], "rollback-failed")
        rollback_path = Path(transaction["rollbackPath"])
        self.assertTrue((rollback_path / "diagnosing-bugs" / "SKILL.md").is_file())
        self.assertIn(
            "old", (rollback_path / "diagnosing-bugs" / "SKILL.md").read_text()
        )

    def test_stable_manifest_paths_cannot_escape_the_declared_root(self) -> None:
        onboard = self.load_onboard_module()
        stable_root = self.root / "stable"
        stable_root.mkdir()
        outside = self.write_valid_skill(self.root / "outside", "diagnosing-bugs")
        manifest = {
            "stableSet": "fixture",
            "repositories": {
                "mattpocock-skills": {
                    "url": onboard.EXTERNAL_SKILL_SOURCES["diagnosing-bugs"]["repo"],
                    "revision": "1" * 40,
                }
            },
            "skills": {
                "diagnosing-bugs": {
                    "repository": "mattpocock-skills",
                    "stablePath": "../outside",
                    "treeSha256": onboard.external_tree_sha256(outside),
                }
            },
        }

        with self.assertRaisesRegex(RuntimeError, "relative path|declared root"):
            onboard.stable_external_skill_source(
                manifest, "diagnosing-bugs", stable_root
            )

        outside_license = self.root / "LICENSE"
        outside_license.write_text("fixture", encoding="utf-8")
        metadata = {
            "repositories": {
                "fixture": {
                    "revision": "1" * 40,
                    "licenseFiles": [{"source": "LICENSE", "stablePath": "../LICENSE"}],
                }
            }
        }
        with self.assertRaisesRegex(RuntimeError, "relative path|declared root"):
            onboard.validate_external_stable_metadata(metadata, stable_root)

    def test_promotion_rejects_source_subpath_outside_the_cloned_repository(
        self,
    ) -> None:
        onboard = self.load_onboard_module()
        stable_root = self.root / "stable"
        shutil.copytree(onboard.EXTERNAL_STABLE_ROOT, stable_root)
        manifest_path = stable_root / "MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        original_stable_set = manifest["stableSet"]
        outside = self.root / "outside-ui-ux-pro-max"
        shutil.copytree(
            onboard.EXTERNAL_STABLE_ROOT / "skills" / "ui-ux-pro-max",
            outside,
        )
        manifest["skills"]["ui-ux-pro-max"]["sourceSubpath"] = str(outside)
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        fake_repo = self.root / "promotion-repo"
        fake_repo.mkdir()
        shutil.copy2(
            onboard.EXTERNAL_STABLE_ROOT
            / "licenses"
            / "ui-ux-pro-max-skill-LICENSE",
            fake_repo / "LICENSE",
        )

        def fake_clone(_repo, _revision, destination):
            shutil.copytree(fake_repo, destination, dirs_exist_ok=True)
            return True, ""

        args = argparse.Namespace(
            repository="ui-ux-pro-max-skill",
            revision="2" * 40,
            stable_set="fixture",
            yes=True,
            json=True,
        )
        with (
            mock.patch.object(onboard, "EXTERNAL_STABLE_ROOT", stable_root),
            mock.patch.object(onboard, "EXTERNAL_STABLE_MANIFEST", manifest_path),
            mock.patch.object(
                onboard, "clone_repo_at_revision", side_effect=fake_clone
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            status = onboard.promote_external_skills_stable(args)

        self.assertNotEqual(status, 0)
        self.assertEqual(
            json.loads(manifest_path.read_text(encoding="utf-8"))["stableSet"],
            original_stable_set,
        )

    def test_promotion_prunes_retired_stable_skill_directory(self) -> None:
        onboard = self.load_onboard_module()
        stable_root = self.root / "stable"
        shutil.copytree(onboard.EXTERNAL_STABLE_ROOT, stable_root)
        manifest_path = stable_root / "MANIFEST.json"
        self.write_valid_skill(
            stable_root / "skills" / "writing-great-skills",
            "writing-great-skills",
            "retired stable content",
        )
        fake_repo = self.root / "promotion-repo"
        shutil.copytree(
            onboard.EXTERNAL_STABLE_ROOT / "skills" / "ui-ux-pro-max",
            fake_repo / ".claude" / "skills" / "ui-ux-pro-max",
        )
        shutil.copy2(
            onboard.EXTERNAL_STABLE_ROOT
            / "licenses"
            / "ui-ux-pro-max-skill-LICENSE",
            fake_repo / "LICENSE",
        )

        def fake_clone(_repo, _revision, destination):
            shutil.copytree(fake_repo, destination, dirs_exist_ok=True)
            return True, ""

        args = argparse.Namespace(
            repository="ui-ux-pro-max-skill",
            revision="2" * 40,
            stable_set="fixture",
            yes=True,
            json=True,
        )
        with (
            mock.patch.object(onboard, "EXTERNAL_STABLE_ROOT", stable_root),
            mock.patch.object(onboard, "EXTERNAL_STABLE_MANIFEST", manifest_path),
            mock.patch.object(
                onboard, "clone_repo_at_revision", side_effect=fake_clone
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            status = onboard.promote_external_skills_stable(args)

        self.assertEqual(status, 0)
        self.assertFalse((stable_root / "skills" / "writing-great-skills").exists())

    def test_prune_rejects_symlinked_stable_skills_root(self) -> None:
        onboard = self.load_onboard_module()
        stable_root = self.root / "stable"
        stable_root.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (stable_root / "skills").symlink_to(outside, target_is_directory=True)

        with self.assertRaisesRegex(RuntimeError, "skills directory is invalid"):
            onboard.prune_unmanaged_stable_skill_directories(
                {"skills": {}}, stable_root
            )

    def test_bundled_migration_reports_legacy_deletion_failure(self) -> None:
        onboard = self.load_onboard_module()
        canonical = self.write_valid_skill(
            self.skills_dir / "sbtd-workflow-onboard",
            "sbtd-workflow-onboard",
        )
        legacy = self.write_valid_skill(
            self.skills_dir / "kuno-workflow-onboard-skills",
            "kuno-workflow-onboard-skills",
        )
        plan = {
            "status": "required",
            "migrations": [
                {
                    "canonicalName": "sbtd-workflow-onboard",
                    "canonicalTarget": str(canonical),
                    "legacyTargets": [str(legacy)],
                }
            ],
        }

        with mock.patch.object(
            onboard,
            "remove_existing_target",
            side_effect=OSError("simulated deletion failure"),
        ):
            results = onboard.run_bundled_skill_migration(plan)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "failed")
        self.assertEqual(results[0]["target"], str(legacy))
        self.assertIn("simulated deletion failure", results[0]["error"])

    def test_invalid_canonical_skill_is_reinstalled_before_legacy_removal(self) -> None:
        onboard = self.load_onboard_module()
        self.write_valid_skill(self.skills_dir / "diagnose", "diagnose", "legacy")
        self.write_valid_skill(
            self.skills_dir / "diagnosing-bugs", "wrong-name", "invalid canonical"
        )
        args = argparse.Namespace(global_skills_dir=str(self.skills_dir))

        missing = onboard.missing_required_external_skills(args)

        self.assertIn("diagnosing-bugs", missing)
        plan = {
            "status": "planned",
            "targetDir": str(self.skills_dir),
            "removeLegacy": ["diagnose"],
        }
        results = onboard.run_external_migration(plan)
        self.assertTrue((self.skills_dir / "diagnose" / "SKILL.md").is_file())
        self.assertTrue(any(item.get("phase") == "preflight" for item in results))

    def test_auto_requires_the_stable_manifest_without_cloning_upstream(self) -> None:
        onboard = self.load_onboard_module()
        clone = mock.Mock(side_effect=AssertionError("upstream must not be cloned"))

        with (
            mock.patch.object(
                onboard, "EXTERNAL_STABLE_MANIFEST", self.root / "missing.json"
            ),
            mock.patch.object(onboard, "clone_repo", clone),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "cannot read stable External Skills manifest"
            ):
                onboard.resolve_external_install_sources(
                    ["diagnosing-bugs"], "auto", self.root / "workspace"
                )

        clone.assert_not_called()

    def test_upstream_does_not_mask_unexpected_internal_errors_with_stable(self) -> None:
        onboard = self.load_onboard_module()
        stable_loader = mock.Mock(side_effect=RuntimeError("stable should not load"))

        with (
            mock.patch.object(onboard, "clone_repo", return_value=(True, "")),
            mock.patch.object(onboard, "cloned_repo_revision", return_value="1" * 40),
            mock.patch.object(
                onboard,
                "source_dir_for_external_skill",
                side_effect=AssertionError("unexpected internal error"),
            ),
            mock.patch.object(onboard, "load_external_stable_manifest", stable_loader),
        ):
            with self.assertRaisesRegex(AssertionError, "unexpected internal error"):
                onboard.resolve_external_install_sources(
                    ["diagnosing-bugs"], "upstream", self.root / "workspace"
                )

        stable_loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
