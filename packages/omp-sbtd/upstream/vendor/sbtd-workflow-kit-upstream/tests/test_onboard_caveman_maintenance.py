from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
ONBOARD = ROOT / "sbtd-workflow-onboard" / "scripts" / "onboard.py"
sys.path.insert(0, str(ONBOARD.parent))

# Declared fixture snapshots. Expected family identities are digested from
# THESE bytes only -- never from the payload under test, which would bless
# whatever local customization happened to be on disk.
CURRENT_SKILL = b"---\nname: caveman\n---\n\ncurrent payload\n"
OLDER_SKILL = b"---\nname: caveman\n---\n\nolder payload\n"
UNKNOWN_SKILL = b"---\nname: caveman\n---\n\nunknown payload\n"
CURRENT_HASH = hashlib.sha256(CURRENT_SKILL).hexdigest()
OLDER_HASH = hashlib.sha256(OLDER_SKILL).hexdigest()

CURRENT_HELP = b"---\nname: caveman-help\n---\n\ncurrent companion\n"
OLDER_HELP = b"---\nname: caveman-help\n---\n\nolder companion\n"
CUSTOM_HELP = b"---\nname: caveman-help\n---\n\ncustom\n"
CURRENT_CAVECREW = b"---\nname: cavecrew\n---\n\ncurrent companion\n"
OLDER_CAVECREW = b"---\nname: cavecrew\n---\n\nolder companion\n"
CURRENT_CAVECREW_HELPER = b"---\nname: cavecrew-helper\n---\n\ncurrent companion\n"
OLDER_CAVECREW_HELPER = b"---\nname: cavecrew-helper\n---\n\nolder companion\n"

# Reviewed upstream full-family identities (JuliusBrussee/caveman), digested
# with external_tree_sha256 per family directory.
REVIEWED_FAMILY_V260 = {
    "cavecrew": "673643f8c42f06f0904eb975a56923583c2cd47ce4bf5a5ac1e5e49b8e4b2c66",
    "caveman": "26b5e133a79a0251dad5e57acaa22ef601731fe59fb4637f9f150d7dfc250bad",
    "caveman-commit": "68fce6cc3c50050e8ede6df99d4f478582d9b5952782c441acf2477b16d706db",
    "caveman-compress": "3d618a06313658b3f108bf82c2f97591643e7fee83cb5990c30e5a044e9a0587",
    "caveman-discover": "0a52f133aef4d3b81e9554cc43132bcf1accedb1154f6ac8e75df24f5f58f537",
    "caveman-evidence-review": "fc5959727ef2f822d756c7e837abea51be91c32e0ca87758c1b77f68c98d5552",
    "caveman-explore": "81c49c489e8d94ffb4cf47e05632235a88d125c4a05e6d2cf64bc0535aa87895",
    "caveman-help": "63b42410962891586b7a5317391e39b8b0a90370144be4d7281e43c68b140947",
    "caveman-learn": "9c1442a0b61945e1bc37240d9a494be4658768e56e61b76943fb0cbc18d805cd",
    "caveman-manage": "e6ad788986936cbe49bdf12cf122fa966dd9e20c0ea7716397e0049d9f833d5a",
    "caveman-optimize": "35dd36fa4b6fe800e9c1db8818b5e79ee18448372f33bd48ee593516d131a947",
    "caveman-review": "d50a54e5b5a5bae7fcac1a4472cfd34ce47c9a8183d1357928eac4c2bd8322db",
    "caveman-setup": "546eb697be5b87cec06117c4eb6d3e9eac55331cb860d2743c2d7b6f45c261b4",
    "caveman-stats": "652eaffb8f6c635431ed238fa7ae2126e138ad7b1d26fae7390f8edc1af17bb0",
}
REVIEWED_FAMILY_V250 = {
    **REVIEWED_FAMILY_V260,
    "caveman": "cfe5ad82c6b43421624d20dd30dc83100bb9516f889b0b2a8bb2cdd0dbd2a6be",
}


def core_only_known_families() -> dict[str, dict[str, dict[str, bytes]]]:
    """Default fixture identity: each known ref ships the caveman core only."""
    return {
        "v2.6.0": {"caveman": {"SKILL.md": CURRENT_SKILL}},
        "v2.5.0": {"caveman": {"SKILL.md": OLDER_SKILL}},
    }


class CavemanMaintenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="sbtd-caveman-test-")
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.skills_dir = self.root / "skills"
        self.module_counter = 0
        self.snapshot_counter = 0

    def load_onboard_module(self):
        self.module_counter += 1
        module_name = f"onboard_caveman_test_{id(self)}_{self.module_counter}"
        spec = importlib.util.spec_from_file_location(module_name, ONBOARD)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load onboard module from {ONBOARD}")
        loader = cast(importlib.machinery.SourceFileLoader, spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        self.addCleanup(sys.modules.pop, module_name, None)
        loader.exec_module(module)
        return module

    def snapshot_digest(self, module, files: dict[str, bytes]) -> str:
        """Digest a separately declared fixture snapshot via the production hasher."""
        self.snapshot_counter += 1
        snapshot_dir = self.root / "fixture-snapshots" / str(self.snapshot_counter)
        for relative, content in files.items():
            path = snapshot_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return module.external_tree_sha256(snapshot_dir)

    def baseline_context(self, module, families=None):
        """Patch known caveman identities derived from declared fixture snapshots.

        ``families`` maps ref -> family directory name -> {relative path: bytes}
        and fully replaces the default core-only identity. Expected digests are
        computed from these declared snapshots, never from the payload under
        test, so a customized target can never bless itself.
        """
        declared = core_only_known_families() if families is None else families
        known = {
            ref: {
                name: self.snapshot_digest(module, files)
                for name, files in members.items()
            }
            for ref, members in declared.items()
        }
        stack = contextlib.ExitStack()
        stack.enter_context(
            mock.patch.object(module, "CAVEMAN_CORE_SKILL_SHA256", CURRENT_HASH)
        )
        stack.enter_context(
            mock.patch.object(
                module,
                "CAVEMAN_KNOWN_CORE_SKILL_SHA256",
                {"v2.6.0": CURRENT_HASH, "v2.5.0": OLDER_HASH},
            )
        )
        stack.enter_context(
            mock.patch.object(module, "CAVEMAN_KNOWN_FAMILY_SHA256", known)
        )
        return stack

    def write_skill(self, name: str, content: bytes) -> Path:
        return self.write_skill_in(self.skills_dir.parent, name, content)

    def write_skill_in(self, root: Path, name: str, content: bytes) -> Path:
        target = root / "skills" / name / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target

    def skill_path(self, name: str) -> Path:
        return self.skills_dir / name / "SKILL.md"

    def fake_clone_from(self, source_repo: Path):
        def clone(_repo: str, _revision: str, destination: Path):
            shutil.copytree(source_repo, destination, dirs_exist_ok=True)
            return True, ""

        return clone

    def test_classifier_distinguishes_states(self) -> None:
        module = self.load_onboard_module()
        with self.baseline_context(module):
            self.assertEqual(module.classify_caveman_state(self.skills_dir), "missing")
            self.write_skill("caveman", CURRENT_SKILL)
            self.assertEqual(module.classify_caveman_state(self.skills_dir), "current")
            self.write_skill("caveman", OLDER_SKILL)
            self.assertEqual(module.classify_caveman_state(self.skills_dir), "outdated")
            self.write_skill("caveman", UNKNOWN_SKILL)
            self.assertEqual(
                module.classify_caveman_state(self.skills_dir), "unknown-drift"
            )
            self.write_skill("caveman", b"---\nname: wrong\n---\n")
            self.assertEqual(module.classify_caveman_state(self.skills_dir), "abnormal")

    def test_dangling_caveman_symlink_is_abnormal(self) -> None:
        self.skills_dir.mkdir(parents=True)
        (self.skills_dir / "caveman").symlink_to(
            self.root / "missing", target_is_directory=True
        )
        module = self.load_onboard_module()
        self.assertEqual(module.classify_caveman_state(self.skills_dir), "abnormal")

    def test_pin_constants_match_reviewed_baseline(self) -> None:
        module = self.load_onboard_module()
        self.assertEqual(
            module.CAVEMAN_SOURCE_REPO, "https://github.com/JuliusBrussee/caveman.git"
        )
        self.assertEqual(module.CAVEMAN_PINNED_REF, "v2.6.0")
        self.assertEqual(
            module.CAVEMAN_PINNED_REVISION,
            "b82c0ad42c2bedc1f2cd78e414dadfaffbaaeec3",
        )
        self.assertEqual(
            module.CAVEMAN_CORE_SKILL_SHA256,
            "c4d7354b4b063d54601fcdd5097a5b1713d1a1a2e386ac39efa438aa1ffef8ce",
        )
        self.assertEqual(
            module.CAVEMAN_KNOWN_CORE_SKILL_SHA256["v2.5.0"],
            "fec5718a391dd9d8c89746d39e0cc0fa7aa5b50447669a15e44c3244167828c0",
        )
        self.assertEqual(
            module.CAVEMAN_KNOWN_FAMILY_SHA256["v2.6.0"], REVIEWED_FAMILY_V260
        )
        self.assertEqual(
            module.CAVEMAN_KNOWN_FAMILY_SHA256["v2.5.0"], REVIEWED_FAMILY_V250
        )

    def test_sibling_symlink_is_abnormal_and_fail_closed(self) -> None:
        module = self.load_onboard_module()
        core = self.write_skill("caveman", CURRENT_SKILL)
        external = self.root / "elsewhere"
        external.mkdir()
        external_bytes = b"---\nname: caveman-help\n---\n"
        (external / "SKILL.md").write_bytes(external_bytes)
        sibling_link = self.skills_dir / "caveman-help"
        sibling_link.symlink_to(external, target_is_directory=True)
        original_link_target = sibling_link.readlink()
        with self.baseline_context(module):
            self.assertEqual(module.classify_caveman_state(self.skills_dir), "abnormal")
            source_repo = self.root / "upstream-sibling"
            self.write_skill_in(source_repo, "caveman", CURRENT_SKILL)
            with mock.patch.object(
                module,
                "clone_repo_at_revision",
                side_effect=self.fake_clone_from(source_repo),
            ):
                result = module.maintain_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "failed")
        self.assertIn("symlink", str(result["error"]))
        self.assertEqual(core.read_bytes(), CURRENT_SKILL)
        self.assertTrue(sibling_link.is_symlink())
        self.assertEqual(sibling_link.readlink(), original_link_target)
        self.assertEqual((external / "SKILL.md").read_bytes(), external_bytes)

    def test_regular_file_caveman_is_repaired(self) -> None:
        module = self.load_onboard_module()
        self.skills_dir.mkdir(parents=True)
        (self.skills_dir / "caveman").write_bytes(OLDER_SKILL)
        self.assertEqual(module.classify_caveman_state(self.skills_dir), "abnormal")
        source_repo = self.root / "upstream-file-repair"
        self.write_skill_in(source_repo, "caveman", CURRENT_SKILL)
        with (
            self.baseline_context(module),
            mock.patch.object(
                module,
                "clone_repo_at_revision",
                side_effect=self.fake_clone_from(source_repo),
            ),
        ):
            result = module.maintain_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "success")
        self.assertEqual(self.skill_path("caveman").read_bytes(), CURRENT_SKILL)
        backup = Path(str(result["backup"]))
        self.assertEqual((backup / "caveman").read_bytes(), OLDER_SKILL)

    def test_payload_sync_backups_only_caveman_family(self) -> None:
        module = self.load_onboard_module()
        families = {
            "v2.6.0": {
                "caveman": {"SKILL.md": CURRENT_SKILL},
                "cavecrew": {"SKILL.md": CURRENT_CAVECREW},
                "cavecrew-helper": {"SKILL.md": CURRENT_CAVECREW_HELPER},
            },
            "v2.5.0": {
                "caveman": {"SKILL.md": OLDER_SKILL},
                "cavecrew": {"SKILL.md": OLDER_CAVECREW},
                "cavecrew-helper": {"SKILL.md": OLDER_CAVECREW_HELPER},
            },
        }
        self.write_skill("caveman", OLDER_SKILL)
        self.write_skill("cavecrew", OLDER_CAVECREW)
        self.write_skill("cavecrew-helper", OLDER_CAVECREW_HELPER)
        self.write_skill("unrelated", b"---\nname: unrelated\n---\nkeep\n")
        source_repo = self.root / "upstream"
        self.write_skill_in(source_repo, "caveman", CURRENT_SKILL)
        self.write_skill_in(source_repo, "cavecrew", CURRENT_CAVECREW)
        self.write_skill_in(source_repo, "cavecrew-helper", CURRENT_CAVECREW_HELPER)
        self.write_skill_in(
            source_repo,
            "investigate-first",
            b"---\nname: investigate-first\n---\nskip\n",
        )

        with (
            self.baseline_context(module, families),
            mock.patch.object(
                module,
                "clone_repo_at_revision",
                side_effect=self.fake_clone_from(source_repo),
            ),
        ):
            result = module.install_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "success")
        self.assertEqual(self.skill_path("caveman").read_bytes(), CURRENT_SKILL)
        self.assertEqual(
            self.skill_path("cavecrew-helper").read_bytes(),
            CURRENT_CAVECREW_HELPER,
        )
        self.assertEqual(
            self.skill_path("cavecrew").read_bytes(),
            CURRENT_CAVECREW,
        )
        self.assertEqual(
            self.skill_path("unrelated").read_bytes(),
            b"---\nname: unrelated\n---\nkeep\n",
        )
        self.assertFalse((self.skills_dir / "investigate-first").exists())
        backup = Path(str(result["backup"]))
        self.assertEqual((backup / "caveman" / "SKILL.md").read_bytes(), OLDER_SKILL)
        self.assertEqual(
            (backup / "cavecrew-helper" / "SKILL.md").read_bytes(),
            OLDER_CAVECREW_HELPER,
        )
        self.assertEqual(
            (backup / "cavecrew" / "SKILL.md").read_bytes(),
            OLDER_CAVECREW,
        )
        self.assertNotIn("unrelated", [entry.name for entry in backup.iterdir()])

    def test_backup_failure_keeps_all_live_family_entries(self) -> None:
        module = self.load_onboard_module()
        families = {
            "v2.6.0": {
                "caveman": {"SKILL.md": CURRENT_SKILL},
                "cavecrew-helper": {"SKILL.md": CURRENT_CAVECREW_HELPER},
            },
            "v2.5.0": {
                "caveman": {"SKILL.md": OLDER_SKILL},
                "cavecrew-helper": {"SKILL.md": OLDER_CAVECREW_HELPER},
            },
        }
        self.write_skill("caveman", OLDER_SKILL)
        self.write_skill("cavecrew-helper", OLDER_CAVECREW_HELPER)
        source_repo = self.root / "upstream-backup-failure"
        self.write_skill_in(source_repo, "caveman", CURRENT_SKILL)
        self.write_skill_in(source_repo, "cavecrew-helper", CURRENT_CAVECREW_HELPER)

        real_copytree = module.shutil.copytree
        calls = {"count": 0}

        def fail_second_backup(source: Path, destination: Path, *args, **kwargs):
            if str(destination).startswith(str(self.skills_dir.parent)):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise OSError("disk full")
            return real_copytree(source, destination, *args, **kwargs)

        def fake_clone(_repo: str, _revision: str, destination: Path):
            destination.mkdir(parents=True)
            for skill_dir in (source_repo / "skills").iterdir():
                target = destination / "skills" / skill_dir.name
                target.mkdir(parents=True)
                (target / "SKILL.md").write_bytes((skill_dir / "SKILL.md").read_bytes())
            return True, ""

        with (
            self.baseline_context(module, families),
            mock.patch.object(module, "clone_repo_at_revision", side_effect=fake_clone),
            mock.patch.object(
                module.shutil, "copytree", side_effect=fail_second_backup
            ),
        ):
            result = module.install_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(calls["count"], 2)
        self.assertEqual(self.skill_path("caveman").read_bytes(), OLDER_SKILL)
        self.assertEqual(
            self.skill_path("cavecrew-helper").read_bytes(),
            OLDER_CAVECREW_HELPER,
        )

    def test_nested_symlink_payload_is_never_replaced_or_traversed(self) -> None:
        # A nested symlink makes the family identity unverifiable, so the
        # payload is unknown drift: never replaced, never traversed.
        module = self.load_onboard_module()
        skill = self.write_skill("caveman", OLDER_SKILL)
        external_secret = self.root / "outside"
        external_secret.mkdir()
        secret_bytes = b"---\nname: outside\n---\nsecret\n"
        (external_secret / "SKILL.md").write_bytes(secret_bytes)
        link = skill.parent / "nested-link"
        link.symlink_to(external_secret, target_is_directory=True)
        original_link_target = link.readlink()
        source_repo = self.root / "upstream-nested"
        self.write_skill_in(source_repo, "caveman", CURRENT_SKILL)

        with self.baseline_context(module):
            self.assertEqual(
                module.classify_caveman_state(self.skills_dir), "unknown-drift"
            )
            with mock.patch.object(
                module,
                "clone_repo_at_revision",
                side_effect=self.fake_clone_from(source_repo),
            ) as clone:
                result = module.install_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "attention-required")
        clone.assert_not_called()
        self.assertEqual(skill.read_bytes(), OLDER_SKILL)
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.readlink(), original_link_target)
        self.assertEqual((external_secret / "SKILL.md").read_bytes(), secret_bytes)

    def test_restore_preserves_nested_symlink_without_traversal(self) -> None:
        module = self.load_onboard_module()
        backup_dir = self.root / "backup"
        backup_caveman = backup_dir / "caveman"
        backup_caveman.mkdir(parents=True)
        (backup_caveman / "SKILL.md").write_bytes(OLDER_SKILL)
        external = self.root / "external"
        external.mkdir()
        (external / "SKILL.md").write_bytes(b"---\nname: external\n---\n")
        (backup_caveman / "nested-link").symlink_to(external, target_is_directory=True)

        self.write_skill("caveman", CURRENT_SKILL)
        restore_error = module.restore_caveman_family(self.skills_dir, backup_dir)
        self.assertIsNone(restore_error)
        restored_link = self.skills_dir / "caveman" / "nested-link"
        self.assertTrue(restored_link.is_symlink())
        self.assertEqual(
            restored_link.readlink(),
            (backup_caveman / "nested-link").readlink(),
        )

    def test_unknown_drift_never_mutates_payload(self) -> None:
        module = self.load_onboard_module()
        target = self.write_skill("caveman", UNKNOWN_SKILL)
        sibling = self.write_skill("caveman-help", CUSTOM_HELP)
        with self.baseline_context(module):
            result = module.maintain_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "attention-required")
        self.assertEqual(target.read_bytes(), UNKNOWN_SKILL)
        self.assertEqual(sibling.read_bytes(), CUSTOM_HELP)

    def test_known_core_does_not_authorize_customized_sibling_replacement(self) -> None:
        module = self.load_onboard_module()
        families = {
            "v2.6.0": {
                "caveman": {"SKILL.md": CURRENT_SKILL},
                "caveman-help": {"SKILL.md": CURRENT_HELP},
            },
            "v2.5.0": {
                "caveman": {"SKILL.md": OLDER_SKILL},
                "caveman-help": {"SKILL.md": OLDER_HELP},
            },
        }
        core = self.write_skill("caveman", OLDER_SKILL)
        customized = b"---\nname: caveman-help\n---\nlocal workflow\n"
        sibling = self.write_skill("caveman-help", customized)
        source_repo = self.root / "upstream-custom-sibling"
        self.write_skill_in(source_repo, "caveman", CURRENT_SKILL)
        self.write_skill_in(source_repo, "caveman-help", CURRENT_HELP)

        with (
            self.baseline_context(module, families=families),
            mock.patch.object(
                module,
                "clone_repo_at_revision",
                side_effect=self.fake_clone_from(source_repo),
            ),
        ):
            result = module.maintain_caveman_payload(self.skills_dir)

        self.assertEqual(result["status"], "attention-required")
        self.assertEqual(core.read_bytes(), OLDER_SKILL)
        self.assertEqual(sibling.read_bytes(), customized)

    def test_changed_file_inside_core_is_unknown_drift(self) -> None:
        # A known core SKILL.md does not authorize replacing a core directory
        # whose other files were changed locally.
        module = self.load_onboard_module()
        core = self.write_skill("caveman", CURRENT_SKILL)
        notes = core.parent / "notes.md"
        notes.write_bytes(b"local notes\n")
        with self.baseline_context(module):
            self.assertEqual(
                module.classify_caveman_state(self.skills_dir), "unknown-drift"
            )
            result = module.maintain_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "attention-required")
        self.assertEqual(core.read_bytes(), CURRENT_SKILL)
        self.assertEqual(notes.read_bytes(), b"local notes\n")

    def symlinked_core_fixture(self) -> tuple[Path, Path]:
        external = self.root / "elsewhere"
        external.mkdir()
        external_core = external / "SKILL.md"
        external_core.write_bytes(OLDER_SKILL)
        skill_dir = self.skills_dir / "caveman"
        skill_dir.mkdir(parents=True)
        core_link = skill_dir / "SKILL.md"
        core_link.symlink_to(external_core)
        return core_link, external_core

    def test_text_install_on_symlinked_core_shows_refusal_reason(self) -> None:
        module = self.load_onboard_module()
        core_link, external_core = self.symlinked_core_fixture()
        args = argparse.Namespace(
            agent="codex",
            global_skills_dir=str(self.skills_dir),
            yes=True,
            json=False,
        )
        stdout = io.StringIO()
        with self.baseline_context(module), contextlib.redirect_stdout(stdout):
            code = module.install_caveman(args)
        text = stdout.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("symlink", text)
        self.assertIn("SKILL.md", text)
        self.assertTrue(core_link.is_symlink())
        self.assertEqual(external_core.read_bytes(), OLDER_SKILL)

    def test_text_plan_on_symlinked_core_shows_refusal_reason(self) -> None:
        module = self.load_onboard_module()
        core_link, external_core = self.symlinked_core_fixture()
        stdout = io.StringIO()
        with self.baseline_context(module), contextlib.redirect_stdout(stdout):
            payload = module.build_plan_payload(
                "plan", [], global_skills_dir=self.skills_dir
            )
            module.print_plan(payload)
        text = stdout.getvalue()
        self.assertIn("symlink", text)
        self.assertIn("SKILL.md", text)
        self.assertTrue(core_link.is_symlink())
        self.assertEqual(external_core.read_bytes(), OLDER_SKILL)

    def test_text_install_upgrade_shows_real_backup_path(self) -> None:
        module = self.load_onboard_module()
        self.write_skill("caveman", OLDER_SKILL)
        source_repo = self.root / "upstream-text-upgrade"
        self.write_skill_in(source_repo, "caveman", CURRENT_SKILL)
        args = argparse.Namespace(
            agent="codex",
            global_skills_dir=str(self.skills_dir),
            yes=True,
            json=False,
        )
        stdout = io.StringIO()
        with (
            self.baseline_context(module),
            mock.patch.object(
                module,
                "clone_repo_at_revision",
                side_effect=self.fake_clone_from(source_repo),
            ),
            contextlib.redirect_stdout(stdout),
        ):
            code = module.install_caveman(args)
        text = stdout.getvalue()
        self.assertEqual(code, 0)
        self.assertEqual(self.skill_path("caveman").read_bytes(), CURRENT_SKILL)
        backups = [
            entry
            for entry in self.root.iterdir()
            if entry.name.startswith(f"{self.skills_dir.name}.caveman.bak-")
        ]
        self.assertEqual(len(backups), 1)
        self.assertIn(str(backups[0]), text)
        self.assertEqual(
            (backups[0] / "caveman" / "SKILL.md").read_bytes(), OLDER_SKILL
        )

    def test_missing_core_with_unknown_sibling_is_preserved(self) -> None:
        module = self.load_onboard_module()
        sibling = self.write_skill("caveman-help", CUSTOM_HELP)
        with self.baseline_context(module):
            self.assertEqual(
                module.classify_caveman_state(self.skills_dir), "unknown-drift"
            )
            result = module.maintain_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "attention-required")
        self.assertEqual(sibling.read_bytes(), CUSTOM_HELP)
        self.assertFalse((self.skills_dir / "caveman").exists())

    def test_missing_core_with_known_companions_is_unknown_drift(self) -> None:
        # A partial family (known companions without the core) must be reported
        # as drift, never as an ordinary missing install: the whole-family
        # identity check, not the missing core alone, gates replacement.
        module = self.load_onboard_module()
        families = {
            "v2.6.0": {
                "caveman": {"SKILL.md": CURRENT_SKILL},
                "caveman-help": {"SKILL.md": CURRENT_HELP},
            },
            "v2.5.0": {
                "caveman": {"SKILL.md": OLDER_SKILL},
                "caveman-help": {"SKILL.md": OLDER_HELP},
            },
        }
        sibling = self.write_skill("caveman-help", CURRENT_HELP)
        with self.baseline_context(module, families=families):
            self.assertEqual(
                module.classify_caveman_state(self.skills_dir), "unknown-drift"
            )
            result = module.maintain_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "attention-required")
        self.assertEqual(sibling.read_bytes(), CURRENT_HELP)
        self.assertFalse((self.skills_dir / "caveman").exists())

    def test_install_rechecks_target_drift_after_clone(self) -> None:
        # A customization landing while the pinned source stages must be
        # caught by the post-clone recheck before any mutation.
        module = self.load_onboard_module()
        core = self.write_skill("caveman", OLDER_SKILL)
        source_repo = self.root / "upstream-recheck"
        self.write_skill_in(source_repo, "caveman", CURRENT_SKILL)

        def mutating_clone(repo: str, revision: str, destination: Path):
            self.write_skill("caveman-help", CUSTOM_HELP)
            return self.fake_clone_from(source_repo)(repo, revision, destination)

        with (
            self.baseline_context(module),
            mock.patch.object(
                module, "clone_repo_at_revision", side_effect=mutating_clone
            ),
        ):
            result = module.install_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "attention-required")
        self.assertEqual(core.read_bytes(), OLDER_SKILL)
        self.assertEqual(self.skill_path("caveman-help").read_bytes(), CUSTOM_HELP)

    def test_nested_symlink_with_abnormal_core_fails_closed(self) -> None:
        # An abnormal core containing a nested symlink must fail closed:
        # never repaired, never traversed.
        module = self.load_onboard_module()
        caveman_dir = self.skills_dir / "caveman"
        caveman_dir.mkdir(parents=True)
        external_secret = self.root / "outside-abnormal"
        external_secret.mkdir()
        secret_bytes = b"---\nname: outside\n---\nsecret\n"
        (external_secret / "SKILL.md").write_bytes(secret_bytes)
        link = caveman_dir / "nested-link"
        link.symlink_to(external_secret, target_is_directory=True)

        with self.baseline_context(module):
            self.assertEqual(
                module.classify_caveman_state(self.skills_dir), "abnormal"
            )
            with mock.patch.object(
                module, "clone_repo_at_revision"
            ) as clone:
                result = module.maintain_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "failed")
        self.assertIn("nested symlink", str(result["error"]))
        clone.assert_not_called()
        self.assertTrue(link.is_symlink())
        self.assertEqual((external_secret / "SKILL.md").read_bytes(), secret_bytes)

    def test_install_caveman_payload_refuses_nested_symlink_abnormal_core(
        self,
    ) -> None:
        # Direct installs must honor the plan's blocked action before staging.
        module = self.load_onboard_module()
        caveman_dir = self.skills_dir / "caveman"
        caveman_dir.mkdir(parents=True)
        external_secret = self.root / "outside-direct"
        external_secret.mkdir()
        secret_bytes = b"---\nname: outside\n---\nsecret\n"
        (external_secret / "SKILL.md").write_bytes(secret_bytes)
        link = caveman_dir / "nested-link"
        link.symlink_to(external_secret, target_is_directory=True)

        with self.baseline_context(module):
            with mock.patch.object(
                module, "clone_repo_at_revision"
            ) as clone:
                result = module.install_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "failed")
        self.assertIn("nested symlink", str(result["error"]))
        clone.assert_not_called()
        self.assertTrue(link.is_symlink())

    def test_unreadable_descendant_fails_closed_without_clone(self) -> None:
        # os.walk suppresses traversal errors without onerror; the collected
        # error must still fail the guard closed, never repaired or traversed.
        module = self.load_onboard_module()
        caveman_dir = self.skills_dir / "caveman"
        caveman_dir.mkdir(parents=True)

        def failing_walk(root, **kwargs):
            onerror = kwargs.get("onerror")
            if onerror is not None:
                onerror(OSError("simulated permission denied"))
            return
            yield

        with self.baseline_context(module):
            self.assertEqual(
                module.classify_caveman_state(self.skills_dir), "abnormal"
            )
            with (
                mock.patch.object(module.os, "walk", side_effect=failing_walk),
                mock.patch.object(
                    module, "clone_repo_at_revision"
                ) as clone,
            ):
                result = module.maintain_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "failed")
        self.assertIn("nested symlink", str(result["error"]))
        clone.assert_not_called()

    def test_install_backs_up_family_appearing_during_clone(self) -> None:
        # Starting from an empty directory must not skip the backup: a known
        # family appearing while staging must still be backed up.
        module = self.load_onboard_module()
        source_repo = self.root / "upstream-appearing-family"
        self.write_skill_in(source_repo, "caveman", CURRENT_SKILL)

        def appearing_clone(repo: str, revision: str, destination: Path):
            self.write_skill("caveman", OLDER_SKILL)
            return self.fake_clone_from(source_repo)(repo, revision, destination)

        with (
            self.baseline_context(module),
            mock.patch.object(
                module, "clone_repo_at_revision", side_effect=appearing_clone
            ),
        ):
            result = module.install_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "success")
        self.assertEqual(self.skill_path("caveman").read_bytes(), CURRENT_SKILL)
        self.assertIn("backup", result)
        backups = [
            entry
            for entry in self.root.iterdir()
            if entry.name.startswith(f"{self.skills_dir.name}.caveman.bak-")
        ]
        self.assertEqual(len(backups), 1)
        self.assertEqual(
            (backups[0] / "caveman" / "SKILL.md").read_bytes(), OLDER_SKILL
        )

    def test_abnormal_core_with_unknown_companion_is_attention_required(
        self,
    ) -> None:
        # A repairable abnormal core never authorizes replacing an
        # unrecognized companion; the combination must stop at report-only.
        module = self.load_onboard_module()
        wrong_core_bytes = b"---\nname: not-caveman\n---\n\nwrong\n"
        caveman_dir = self.skills_dir / "caveman"
        caveman_dir.mkdir(parents=True)
        (caveman_dir / "SKILL.md").write_bytes(wrong_core_bytes)
        sibling = self.write_skill("caveman-help", CUSTOM_HELP)

        with self.baseline_context(module):
            with mock.patch.object(
                module, "clone_repo_at_revision"
            ) as clone:
                result = module.maintain_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "attention-required")
        clone.assert_not_called()
        self.assertEqual(
            (caveman_dir / "SKILL.md").read_bytes(), wrong_core_bytes
        )
        self.assertEqual(sibling.read_bytes(), CUSTOM_HELP)

    def test_maintain_upgrades_known_older_payload_with_backup(self) -> None:
        # Covers the maintenance entry point used by run(init/reset).
        module = self.load_onboard_module()
        self.write_skill("caveman", OLDER_SKILL)
        source_repo = self.root / "upstream-maintain-upgrade"
        self.write_skill_in(source_repo, "caveman", CURRENT_SKILL)
        with (
            self.baseline_context(module),
            mock.patch.object(
                module,
                "clone_repo_at_revision",
                side_effect=self.fake_clone_from(source_repo),
            ),
        ):
            result = module.maintain_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["state"], "outdated")
        self.assertEqual(result["plannedAction"], "upgrade")
        self.assertEqual(self.skill_path("caveman").read_bytes(), CURRENT_SKILL)
        backups = [
            entry
            for entry in self.root.iterdir()
            if entry.name.startswith(f"{self.skills_dir.name}.caveman.bak-")
        ]
        self.assertEqual(len(backups), 1)
        self.assertEqual(
            (backups[0] / "caveman" / "SKILL.md").read_bytes(), OLDER_SKILL
        )

    def test_run_init_json_upgrades_older_caveman_and_keeps_backup(self) -> None:
        # The audited write-mode dispatch: run(init) must reach caveman
        # maintenance and fold the result into the single --json document.
        module = self.load_onboard_module()
        self.write_skill("caveman", OLDER_SKILL)
        source_repo = self.root / "upstream-run-init"
        self.write_skill_in(source_repo, "caveman", CURRENT_SKILL)
        args = argparse.Namespace(
            agent="codex", global_skills_dir=str(self.skills_dir), json=True
        )
        stdout = io.StringIO()
        with (
            self.baseline_context(module),
            mock.patch.object(
                module,
                "resolve_global_skills_dir",
                return_value=(self.skills_dir, "explicit"),
            ),
            mock.patch.object(module, "build_operations", return_value=[]),
            mock.patch.object(
                module,
                "build_bundled_skill_migration_plan",
                return_value={"status": "skipped"},
            ),
            mock.patch.object(
                module,
                "build_external_migration_plan",
                return_value={"status": "skipped"},
            ),
            mock.patch.object(module, "ensure_confirmed"),
            mock.patch.object(
                module,
                "detect_ponytail_provider",
                return_value={"provider": "none"},
            ),
            mock.patch.object(
                module, "install_required_external_skills", return_value=None
            ),
            mock.patch.object(module, "run_bundled_skill_migration", return_value=[]),
            mock.patch.object(module, "run_external_migration", return_value=[]),
            mock.patch.object(
                module,
                "clone_repo_at_revision",
                side_effect=self.fake_clone_from(source_repo),
            ),
            contextlib.redirect_stdout(stdout),
        ):
            code = module.run("init", args)
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        maintenance = payload["cavemanMaintenance"]
        self.assertEqual(maintenance["status"], "success")
        self.assertEqual(maintenance["state"], "outdated")
        self.assertEqual(maintenance["plannedAction"], "upgrade")
        self.assertIn("backup", maintenance)
        self.assertEqual(self.skill_path("caveman").read_bytes(), CURRENT_SKILL)
        backups = [
            entry
            for entry in self.root.iterdir()
            if entry.name.startswith(f"{self.skills_dir.name}.caveman.bak-")
        ]
        self.assertEqual(len(backups), 1)
        self.assertEqual(
            (backups[0] / "caveman" / "SKILL.md").read_bytes(), OLDER_SKILL
        )

    def test_install_caveman_from_missing_backs_up_appearing_family(self) -> None:
        # The CLI wrapper starts from an empty directory before cloning; the
        # post-clone mutation-time decision must still back the family up.
        module = self.load_onboard_module()
        source_repo = self.root / "upstream-cli-appearing"
        self.write_skill_in(source_repo, "caveman", CURRENT_SKILL)

        def appearing_clone(repo: str, revision: str, destination: Path):
            self.write_skill("caveman", OLDER_SKILL)
            return self.fake_clone_from(source_repo)(repo, revision, destination)

        args = argparse.Namespace(
            agent="codex",
            global_skills_dir=str(self.skills_dir),
            yes=True,
            json=True,
        )
        stdout = io.StringIO()
        with (
            self.baseline_context(module),
            mock.patch.object(
                module, "clone_repo_at_revision", side_effect=appearing_clone
            ),
            contextlib.redirect_stdout(stdout),
        ):
            code = module.install_caveman(args)
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        maintenance = payload["maintenance"]
        self.assertEqual(maintenance["status"], "success")
        self.assertIn("backup", maintenance)
        self.assertEqual(self.skill_path("caveman").read_bytes(), CURRENT_SKILL)
        backups = [
            entry
            for entry in self.root.iterdir()
            if entry.name.startswith(f"{self.skills_dir.name}.caveman.bak-")
        ]
        self.assertEqual(len(backups), 1)
        self.assertEqual(
            (backups[0] / "caveman" / "SKILL.md").read_bytes(), OLDER_SKILL
        )


    def test_install_blocks_when_staged_source_family_mismatches_pin(self) -> None:
        module = self.load_onboard_module()
        core = self.write_skill("caveman", OLDER_SKILL)
        source_repo = self.root / "upstream-tampered"
        self.write_skill_in(source_repo, "caveman", CURRENT_SKILL)
        self.write_skill_in(source_repo, "caveman-help", CUSTOM_HELP)
        with (
            self.baseline_context(module),
            mock.patch.object(
                module,
                "clone_repo_at_revision",
                side_effect=self.fake_clone_from(source_repo),
            ),
        ):
            result = module.install_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(core.read_bytes(), OLDER_SKILL)
        self.assertFalse((self.skills_dir / "caveman-help").exists())

    def test_explicit_install_preserves_unknown_drift(self) -> None:
        module = self.load_onboard_module()
        target = self.write_skill("caveman", UNKNOWN_SKILL)
        sibling = self.write_skill("caveman-help", CUSTOM_HELP)
        args = argparse.Namespace(
            agent="codex",
            global_skills_dir=str(self.skills_dir),
            yes=True,
            json=True,
        )
        stdout = io.StringIO()
        with self.baseline_context(module), contextlib.redirect_stdout(stdout):
            code = module.install_caveman(args)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "attention-required")
        self.assertEqual(target.read_bytes(), UNKNOWN_SKILL)
        self.assertEqual(sibling.read_bytes(), CUSTOM_HELP)

    def test_explicit_install_stages_payload_into_global_skills_dir(self) -> None:
        module = self.load_onboard_module()
        families = {
            "v2.6.0": {
                "caveman": {"SKILL.md": CURRENT_SKILL},
                "caveman-help": {"SKILL.md": CURRENT_HELP},
            },
        }
        source_repo = self.root / "upstream"
        self.write_skill_in(source_repo, "caveman", CURRENT_SKILL)
        self.write_skill_in(source_repo, "caveman-help", CURRENT_HELP)
        args = argparse.Namespace(
            agent="codex",
            global_skills_dir=str(self.skills_dir),
            yes=True,
            json=True,
        )
        stdout = io.StringIO()
        clone_calls: list[tuple[str, str]] = []

        def recording_clone(repo: str, revision: str, destination: Path):
            clone_calls.append((repo, revision))
            return self.fake_clone_from(source_repo)(repo, revision, destination)

        with (
            self.baseline_context(module, families),
            mock.patch.object(
                module, "clone_repo_at_revision", side_effect=recording_clone
            ),
            contextlib.redirect_stdout(stdout),
        ):
            code = module.install_caveman(args)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "installed")
        self.assertEqual(
            clone_calls,
            [(module.CAVEMAN_SOURCE_REPO, module.CAVEMAN_PINNED_REVISION)],
        )
        self.assertEqual(self.skill_path("caveman").read_bytes(), CURRENT_SKILL)
        self.assertEqual(self.skill_path("caveman-help").read_bytes(), CURRENT_HELP)

    def test_explicit_install_failure_stays_in_json_contract(self) -> None:
        module = self.load_onboard_module()
        args = argparse.Namespace(
            agent="codex",
            global_skills_dir=str(self.skills_dir),
            yes=True,
            json=True,
        )
        stdout = io.StringIO()
        with (
            mock.patch.object(
                module,
                "install_caveman_payload",
                side_effect=OSError("stage write failed"),
            ),
            contextlib.redirect_stdout(stdout),
        ):
            code = module.install_caveman(args)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(payload["status"], "failed")
        self.assertIn("stage write failed", payload["maintenance"]["error"])

    def test_check_reports_maintenance_state_without_mutation(self) -> None:
        module = self.load_onboard_module()
        self.write_skill("caveman", OLDER_SKILL)
        args = argparse.Namespace(
            projects_root=None, global_skills_dir=str(self.skills_dir)
        )
        isolated_env = {
            "HOME": str(self.root / "home"),
            "PATH": str(self.root / "bin"),
        }
        with (
            self.baseline_context(module),
            mock.patch.dict(module.os.environ, isolated_env, clear=True),
        ):
            results = module.build_check_results(args)
        caveman = next(item for item in results["skills"] if item["name"] == "caveman")
        self.assertEqual(caveman["maintenanceState"], "outdated")
        self.assertEqual(caveman["pinnedRef"], module.CAVEMAN_PINNED_REF)
        self.assertEqual(caveman["maintenanceScope"], "workflow-skill-payload-only")
        self.assertEqual(self.skill_path("caveman").read_bytes(), OLDER_SKILL)

    def test_symlinked_core_file_is_never_replaced(self) -> None:
        module = self.load_onboard_module()
        core_link, external_core = self.symlinked_core_fixture()
        skill_dir = self.skills_dir / "caveman"
        source_repo = self.root / "source"
        self.write_skill_in(source_repo, "caveman", CURRENT_SKILL)
        with self.baseline_context(module):
            self.assertEqual(module.classify_caveman_state(self.skills_dir), "abnormal")
            plan = module.caveman_maintenance_plan(self.skills_dir)
            self.assertEqual(plan["plannedAction"], "blocked")
            self.assertIn("SKILL.md", str(plan["blockedReason"]))
            with mock.patch.object(
                module,
                "clone_repo_at_revision",
                side_effect=self.fake_clone_from(source_repo),
            ) as clone:
                result = module.maintain_caveman_payload(self.skills_dir)
                explicit = module.install_caveman_payload(self.skills_dir)
        clone.assert_not_called()
        self.assertEqual(result["status"], "failed")
        self.assertIn("symlink", str(result["error"]))
        self.assertEqual(explicit["status"], "failed")
        self.assertIn("symlink", str(explicit["error"]))
        self.assertTrue(core_link.is_symlink())
        self.assertEqual(core_link.readlink(), external_core)
        self.assertEqual(external_core.read_bytes(), OLDER_SKILL)
        self.assertFalse(skill_dir.is_symlink())
        self.assertEqual(
            [entry.name for entry in self.skills_dir.iterdir()], ["caveman"]
        )

    def test_sibling_symlink_without_core_is_abnormal_not_missing(self) -> None:
        module = self.load_onboard_module()
        self.skills_dir.mkdir(parents=True)
        dangling = self.skills_dir / "cavecrew-helper"
        dangling.symlink_to(self.root / "nowhere", target_is_directory=True)
        with self.baseline_context(module):
            self.assertEqual(module.classify_caveman_state(self.skills_dir), "abnormal")
            plan = module.caveman_maintenance_plan(self.skills_dir)
            self.assertEqual(plan["plannedAction"], "blocked")
            result = module.maintain_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "failed")
        self.assertIn("symlink", str(result["error"]))
        self.assertTrue(dangling.is_symlink())
        self.assertFalse((self.skills_dir / "caveman").exists())

    def test_prefix_named_sibling_symlink_blocks_but_is_never_mutated(self) -> None:
        # `caveman.local` sits outside the narrow `caveman-*` mutation matcher but
        # must still trip the documented `caveman*` fail-closed symlink guard.
        module = self.load_onboard_module()
        self.write_skill("caveman", UNKNOWN_SKILL)
        external = self.root / "external-local"
        external.mkdir()
        odd_link = self.skills_dir / "caveman.local"
        odd_link.symlink_to(external, target_is_directory=True)
        self.assertFalse(module.is_caveman_family_name("caveman.local"))
        self.assertTrue(module.is_caveman_family_prefix_name("caveman.local"))
        self.assertTrue(module.is_caveman_family_prefix_name("cavecrewX"))
        self.assertFalse(module.is_caveman_family_prefix_name("cave"))
        self.assertNotIn(
            odd_link,
            module.caveman_family_dirs(self.skills_dir),
            "mutation scope must stay narrow",
        )
        with self.baseline_context(module):
            self.assertEqual(module.classify_caveman_state(self.skills_dir), "abnormal")
            plan = module.caveman_maintenance_plan(self.skills_dir)
            self.assertEqual(plan["plannedAction"], "blocked")
            self.assertIn("symlink", str(plan["blockedReason"]))
            result = module.install_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(odd_link.is_symlink())
        self.assertEqual(odd_link.readlink(), external)
        self.assertEqual(self.skill_path("caveman").read_bytes(), UNKNOWN_SKILL)

    def test_staging_filesystem_error_returns_structured_failure(self) -> None:
        module = self.load_onboard_module()
        self.write_skill("caveman", OLDER_SKILL)
        with (
            self.baseline_context(module),
            mock.patch.object(
                module.tempfile,
                "TemporaryDirectory",
                side_effect=OSError("no tmp space"),
            ),
        ):
            result = module.install_caveman_payload(self.skills_dir)
        self.assertEqual(result["status"], "failed")
        self.assertIn("no tmp space", str(result["error"]))
        self.assertEqual(self.skill_path("caveman").read_bytes(), OLDER_SKILL)

    def test_human_check_output_renders_maintenance_state(self) -> None:
        module = self.load_onboard_module()
        self.write_skill("caveman", UNKNOWN_SKILL)
        args = argparse.Namespace(
            projects_root=None, global_skills_dir=str(self.skills_dir)
        )
        isolated_env = {
            "HOME": str(self.root / "home"),
            "PATH": str(self.root / "bin"),
        }
        stdout = io.StringIO()
        with (
            self.baseline_context(module),
            mock.patch.dict(module.os.environ, isolated_env, clear=True),
        ):
            results = module.build_check_results(args)
            with contextlib.redirect_stdout(stdout):
                module.print_check_results(results, False)
        text = stdout.getvalue()
        self.assertIn("- caveman [interaction]: installed", text)
        self.assertIn("maintenance: unknown-drift", text)
        self.assertIn(f"pinned {module.CAVEMAN_PINNED_REF}", text)
        self.assertIn("planned action: none", text)
        self.assertEqual(self.skill_path("caveman").read_bytes(), UNKNOWN_SKILL)

    def test_plan_reports_upgrade_for_known_older_payload(self) -> None:
        module = self.load_onboard_module()
        self.write_skill("caveman", OLDER_SKILL)
        with self.baseline_context(module):
            plan = module.build_plan_payload(
                "plan", [], global_skills_dir=self.skills_dir
            )
        self.assertEqual(plan["cavemanMaintenance"]["state"], "outdated")
        self.assertEqual(plan["cavemanMaintenance"]["plannedAction"], "upgrade")


if __name__ == "__main__":
    unittest.main()
