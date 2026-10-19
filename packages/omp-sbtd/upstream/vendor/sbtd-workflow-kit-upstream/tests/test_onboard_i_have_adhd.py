from __future__ import annotations

import argparse
import hashlib
import importlib.machinery
import importlib.util
import json
import shlex
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
CATALOG = ROOT / "sbtd-workflow-onboard" / "catalog.json"
STABLE = ROOT / "sbtd-workflow-onboard" / "assets" / "external-skills" / "stable"

I_HAVE_ADHD_REVISION = "4092de07ce3ed88389d77c0d623b7af89b40ac0e"
I_HAVE_ADHD_REVIEWED_SHA256 = (
    "3170b16ace00aecb0dd7feb54c0b5aa642e7502acda06ecd24fd89a11c7127e9"
)

I_HAVE_ADHD_LICENSE_SHA256 = (
    "8acbb618089b738404f76ac60fca1aaa995d9a87995eddf95f0b777acd7f7d2c"
)

class IHaveAdhdStableContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module_counter = 0

    def load_onboard_module(self):
        self.module_counter += 1
        module_name = f"onboard_i_have_adhd_test_{id(self)}_{self.module_counter}"
        spec = importlib.util.spec_from_file_location(module_name, ONBOARD)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load onboard module from {ONBOARD}")
        loader = cast(importlib.machinery.SourceFileLoader, spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        self.addCleanup(sys.modules.pop, module_name, None)
        loader.exec_module(module)
        return module

    def test_catalog_registers_i_have_adhd_external_skill(self) -> None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        entries = {
            entry["id"]: entry
            for entry in catalog["entries"]
            if entry["kind"] == "external-skill"
        }
        entry = entries["skill:i-have-adhd"]
        self.assertEqual(
            entry["source"],
            {
                "repo": "https://github.com/ayghri/i-have-adhd.git",
                "subpath": "skills/i-have-adhd",
                "aliases": ["i-have-adhd"],
            },
        )
        self.assertEqual(entry["targetRole"], "external-skill")
        self.assertEqual(len(entries), 19)

    def test_stable_manifest_repository_entry(self) -> None:
        manifest = json.loads((STABLE / "MANIFEST.json").read_text(encoding="utf-8"))
        repository = manifest["repositories"]["i-have-adhd"]
        self.assertEqual(repository["url"], "https://github.com/ayghri/i-have-adhd.git")
        self.assertEqual(repository["revision"], I_HAVE_ADHD_REVISION)
        self.assertEqual(repository["license"], "MIT")
        self.assertEqual(
            repository["licenseFiles"],
            [{"source": "LICENSE", "stablePath": "licenses/i-have-adhd-LICENSE"}],
        )

    def test_stable_manifest_skill_entry(self) -> None:
        manifest = json.loads((STABLE / "MANIFEST.json").read_text(encoding="utf-8"))
        skill = manifest["skills"]["i-have-adhd"]
        self.assertEqual(skill["repository"], "i-have-adhd")
        self.assertEqual(skill["sourceSubpath"], "skills/i-have-adhd")
        self.assertEqual(skill["stablePath"], "skills/i-have-adhd")
        self.assertRegex(skill["treeSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(len(manifest["skills"]), 19)

    def test_snapshot_matches_reviewed_baseline(self) -> None:
        snapshot = (STABLE / "skills" / "i-have-adhd" / "SKILL.md").read_bytes()
        self.assertEqual(
            hashlib.sha256(snapshot).hexdigest(), I_HAVE_ADHD_REVIEWED_SHA256
        )
        license_file = STABLE / "licenses" / "i-have-adhd-LICENSE"
        self.assertEqual(
            hashlib.sha256(license_file.read_bytes()).hexdigest(),
            I_HAVE_ADHD_LICENSE_SHA256,
        )

    def test_referenced_membership_and_check_classification(self) -> None:
        module = self.load_onboard_module()
        self.assertIn("i-have-adhd", module.REFERENCED_SKILLS)
        self.assertIn("caveman", module.INTERACTION_SKILLS)
        self.assertNotIn("i-have-adhd", module.INTERACTION_SKILLS)
        source = module.EXTERNAL_SKILL_SOURCES["i-have-adhd"]
        self.assertEqual(source["repo"], "https://github.com/ayghri/i-have-adhd.git")
        self.assertEqual(source["subpath"], "skills/i-have-adhd")
        with tempfile.TemporaryDirectory(prefix="sbtd-i-have-adhd-missing-") as tmp:
            skills_dir = Path(tmp) / "skills"
            item = module.check_skill("i-have-adhd", "referenced", skills_dir, None)
        self.assertEqual(item["group"], "referenced")
        self.assertEqual(
            item["sourceRepo"], "https://github.com/ayghri/i-have-adhd.git"
        )
        self.assertFalse(item["installed"])

    def test_no_install_subcommand_or_pin_constants_remain(self) -> None:
        module = self.load_onboard_module()
        self.assertNotIn("install-i-have-adhd", module.build_parser().format_help())
        advice = module.skill_next_step(
            {
                "name": "i-have-adhd",
                "sourceRepo": "https://github.com/ayghri/i-have-adhd.git",
            }
        )
        self.assertIn("install-external-skills", advice)
        self.assertNotIn("install-i-have-adhd", advice)

    def test_repair_hints_use_installed_script_path_not_cwd_relative(self) -> None:
        module = self.load_onboard_module()
        script = module.ONBOARD_SCRIPT_PATH
        self.assertTrue(script.is_absolute())
        self.assertEqual(script, ONBOARD.absolute())
        external = module.skill_next_step(
            {"name": "i-have-adhd", "sourceRepo": "https://example.invalid/repo.git"}
        )
        caveman = module.skill_next_step({"name": "caveman"})
        expected_prefix = module.render_shell_command(["python", str(script)])
        if expected_prefix.startswith("& "):
            expected_prefix = expected_prefix[2:]
        for advice in (external, caveman):
            self.assertIn(expected_prefix + " ", advice)
            self.assertNotIn("python scripts/onboard.py", advice)
        self.assertIn(
            module.render_shell_command(
                ["--skills", "i-have-adhd", "--scope", "global", "--source", "auto", "--yes"]
            ).removeprefix("& "),
            external,
        )

    def test_posix_hints_keep_metacharacters_literal(self) -> None:
        module = self.load_onboard_module()
        hostile = [
            "/tmp/with space/onboard.py",
            "/tmp/$HOME-ish/onboard.py",
            "/tmp/`whoami`/onboard.py",
            "/tmp/glob*[x]{a,b}~#?/onboard.py",
            "/tmp/it's/onboard.py",
        ]
        with mock.patch.object(module.os, "name", "posix"):
            self.assertEqual(module.shell_prefix(), "")
            self.assertEqual(
                module.shell_quote_path(Path("/tmp/plain/onboard.py")), "/tmp/plain/onboard.py"
            )
            for text in hostile:
                quoted = module.shell_quote_path(Path(text))
                # A sh word-splitter must recover the exact path, so nothing is
                # left for the shell to expand or glob.
                self.assertEqual(shlex.split(quoted), [text], quoted)
            argv = ["python", "/tmp/it's a $dir/onboard.py", "check", "--json"]
            self.assertEqual(shlex.split(module.render_shell_command(argv)), argv)
            command = module.onboard_command("check", "--json")
            self.assertEqual(
                shlex.split(command),
                ["python", str(module.ONBOARD_SCRIPT_PATH), "check", "--json"],
            )
            hint = module.skill_next_step({"name": "caveman"})
            self.assertFalse(hint.startswith("Run in PowerShell"), hint)

    def test_windows_hints_render_runnable_powershell(self) -> None:
        module = self.load_onboard_module()
        hostile = [
            r"C:\Users\it's me\onboard.py",
            r"C:\Users\%USERNAME%\onboard.py",
            r"C:\Users\!DELAYED!\onboard.py",
            r"C:\Users\$env\onboard.py",
        ]
        with mock.patch.object(module.os, "name", "nt"):
            self.assertEqual(module.shell_prefix(), "Run in PowerShell: ")
            for text in hostile:
                quoted = module.shell_quote_path(Path(text))
                self.assertTrue(quoted.startswith("'") and quoted.endswith("'"), quoted)
                # PowerShell single-quoted literal: only `'` is escaped (doubled);
                # `%VAR%`, `!VAR!` and `$env` survive byte-for-byte.
                self.assertEqual(quoted[1:-1].replace("''", "'"), text)
            # Whitelisted tokens stay bare: no quoting, no call operator.
            self.assertEqual(
                module.render_shell_command(
                    ["python", r"C:\Users\me\onboard.py", "check", "--json"]
                ),
                r"python C:\Users\me\onboard.py check --json",
            )
            rendered = module.render_shell_command(["python", r"C:\x y\onboard.py", "check"])
            self.assertEqual(rendered, "python 'C:\\x y\\onboard.py' check")
            command = module.onboard_command("check", "--json")
            self.assertTrue(command.startswith("python "), command)
            self.assertTrue(command.endswith(" check --json"), command)
            # The call operator only appears when argv[0] itself needs quoting.
            spaced = module.render_shell_command(
                [r"C:\Program Files\Python\python.exe", "check"]
            )
            self.assertEqual(spaced, "& 'C:\\Program Files\\Python\\python.exe' check")
            hint = module.skill_next_step(
                {"name": "i-have-adhd", "sourceRepo": "https://example.invalid/repo.git"}
            )
            self.assertTrue(hint.startswith("Run in PowerShell: "), hint)
            self.assertIn("PowerShell", hint)

    def seed_valid_required_skills(self, module, skills_dir: Path) -> None:
        # Seed every required skill except i-have-adhd so the real missing
        # selector must choose i-have-adhd on its own.
        skills_dir.mkdir(parents=True, exist_ok=True)
        for name in module.EXTERNAL_SKILL_SOURCES:
            if name == "i-have-adhd":
                continue
            shutil.copytree(STABLE / "skills" / name, skills_dir / name)

    def test_required_install_reinstalls_missing_i_have_adhd(self) -> None:
        # Covers the init/reset required-install flow from an empty skills root;
        # the real missing selector, not a mock, must pick i-have-adhd.
        module = self.load_onboard_module()
        with tempfile.TemporaryDirectory(
            prefix="sbtd-i-have-adhd-install-"
        ) as tmp:
            skills_dir = Path(tmp) / "skills"
            self.seed_valid_required_skills(module, skills_dir)
            args = argparse.Namespace(global_skills_dir=str(skills_dir), json=True)
            self.assertEqual(
                module.missing_required_external_skills(args), ["i-have-adhd"]
            )
            payload = module.install_required_external_skills(
                args, overwrite=False
            )
            transaction = cast(dict[str, object], payload["transaction"])
            self.assertEqual(transaction["status"], "committed")
            self.assertEqual(
                (skills_dir / "i-have-adhd" / "SKILL.md").read_bytes(),
                (STABLE / "skills" / "i-have-adhd" / "SKILL.md").read_bytes(),
            )

    def test_required_install_replaces_partial_i_have_adhd(self) -> None:
        # A partial installation (directory without a valid SKILL.md) must be
        # selected as missing and replaced by the vendored payload.
        module = self.load_onboard_module()
        with tempfile.TemporaryDirectory(
            prefix="sbtd-i-have-adhd-partial-"
        ) as tmp:
            skills_dir = Path(tmp) / "skills"
            self.seed_valid_required_skills(module, skills_dir)
            partial = skills_dir / "i-have-adhd"
            partial.mkdir(parents=True)
            (partial / "README.md").write_text("partial", encoding="utf-8")
            args = argparse.Namespace(global_skills_dir=str(skills_dir), json=True)
            self.assertEqual(
                module.missing_required_external_skills(args), ["i-have-adhd"]
            )
            payload = module.install_required_external_skills(
                args, overwrite=False
            )
            transaction = cast(dict[str, object], payload["transaction"])
            self.assertEqual(transaction["status"], "committed")
            self.assertEqual(
                (skills_dir / "i-have-adhd" / "SKILL.md").read_bytes(),
                (STABLE / "skills" / "i-have-adhd" / "SKILL.md").read_bytes(),
            )

    def test_corrupted_stable_mirror_is_rejected_without_mutation(self) -> None:
        # A corrupted vendored i-have-adhd tree must fail checksum validation
        # before any target is changed. The install path is driven for real;
        # only the stable root location is redirected to a corrupted copy,
        # keeping the genuine checksum validator in the loop.
        module = self.load_onboard_module()
        with tempfile.TemporaryDirectory(
            prefix="sbtd-i-have-adhd-corrupt-"
        ) as tmp:
            corrupted_root = Path(tmp) / "stable"
            shutil.copytree(STABLE, corrupted_root)
            (corrupted_root / "skills" / "i-have-adhd" / "SKILL.md").write_bytes(
                b"---\nname: i-have-adhd\ndescription: tampered\n---\n\ntampered body\n"
            )
            skills_dir = Path(tmp) / "skills"
            self.seed_valid_required_skills(module, skills_dir)
            args = argparse.Namespace(global_skills_dir=str(skills_dir), json=True)
            self.assertEqual(
                module.missing_required_external_skills(args), ["i-have-adhd"]
            )
            corrupted_manifest = json.loads(
                (corrupted_root / "MANIFEST.json").read_text(encoding="utf-8")
            )
            real_stable_source = module.stable_external_skill_source
            with (
                mock.patch.object(
                    module,
                    "load_external_stable_manifest",
                    return_value=corrupted_manifest,
                ),
                mock.patch.object(
                    module,
                    "stable_external_skill_source",
                    lambda manifest, name: real_stable_source(
                        manifest, name, corrupted_root
                    ),
                ),
            ):
                payload = module.install_required_external_skills(
                    args, overwrite=False
                )
            transaction = cast(dict[str, object], payload["transaction"])
            self.assertEqual(transaction["status"], "aborted-before-commit")
            results = cast(list[dict[str, object]], payload["results"])
            self.assertEqual(len(results), 1)
            self.assertIn("checksum mismatch", str(results[0]["error"]))
            self.assertFalse(
                (skills_dir / "i-have-adhd" / "SKILL.md").exists()
            )



if __name__ == "__main__":
    unittest.main()
