"""Public CLI scenarios U01/U03/U06: read-only planning and guarded upgrade."""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "sbtd-workflow-onboard/scripts/onboard.py"
sys.path.insert(0, str(CLI.parent))

from sbtd_migration_files import require_private_directory


class UpgradeCliTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "isolated POSIX user-site fixture")
    def test_plan_rejects_dependencies_unavailable_to_isolated_executor(self):
        """U32: parent-only imports cannot authorize plan or apply."""
        import sysconfig
        import venv

        import tomlkit

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            environment = base / "python"
            venv.EnvBuilder(with_pip=False).create(environment)
            binary = environment / "bin/python"
            env = {**os.environ, "PYTHONUSERBASE": str(base / "user"), "HOME": str(base)}
            layout = subprocess.run(
                [str(binary), "-B", "-c",
                 "import json,site,sysconfig; print(json.dumps([sysconfig.get_path('purelib'),site.getusersitepackages()]))"],
                env=env, capture_output=True, text=True, check=True, timeout=30,
            )
            site_dir, user_site = map(Path, json.loads(layout.stdout))
            user_site.mkdir(parents=True)
            for item in Path(sysconfig.get_path("purelib")).iterdir():
                if item.name.startswith("tomlkit") or item.name.endswith(".pth") or item.name == "__pycache__":
                    continue
                (site_dir / item.name).symlink_to(item, target_is_directory=item.is_dir())
            (user_site / "tomlkit").symlink_to(Path(tomlkit.__file__).parent, target_is_directory=True)
            # Enable the test-owned user site only in the non-isolated interpreter.
            (site_dir / "fixture-user-site.pth").write_text(
                "import site,sys; site.ENABLE_USER_SITE = not sys.flags.isolated; "
                "site.addusersitepackages(set()) if site.ENABLE_USER_SITE else None\n",
                encoding="utf-8",
            )
            visibility = "import importlib.util; print(importlib.util.find_spec('tomlkit') is not None)"
            for flags, expected in (([], "True"), (["-I"], "False")):
                result = subprocess.run([str(binary), *flags, "-B", "-c", visibility],
                                        env=env, capture_output=True, text=True, check=True)
                self.assertEqual(result.stdout.strip(), expected)
            vault = base / "vault"
            require_private_directory(vault, create=True)
            config = base / "codex/config.toml"
            runtime = {}
            for key, name in (("python", "python-bin"), ("node", "node"), ("cli", "cli.js")):
                path = base / name
                path.write_bytes(b"")
                runtime[key] = str(path)
            scope = base / "scope.json"
            scope.write_text(json.dumps({
                "schema_version": 1,
                "hosts": [{"id": "codex", "platform": "codex", "config": str(config),
                           "config_home": str(config.parent), "onboard_root": str(CLI.parents[1]),
                           "skills_roots": [], "project_roots": [], "runtime": runtime}],
            }), encoding="utf-8")
            result = subprocess.run(
                [str(binary), "-B", str(CLI), "upgrade", "--phase", "plan",
                 "--scope", str(scope), "--backup-root", str(vault), "--json"],
                env=env, capture_output=True, text=True, timeout=120, check=False,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)["reason"], "isolated-dependencies-unavailable")
            self.assertFalse(config.exists())
            self.assertEqual(list(vault.iterdir()), [])
            (site_dir / "tomlkit").symlink_to(Path(tomlkit.__file__).parent, target_is_directory=True)
            positive = subprocess.run(result.args, env=env, capture_output=True, text=True,
                                      timeout=120, check=False)
            self.assertEqual(positive.returncode, 0, positive.stderr)
            self.assertEqual(json.loads(positive.stdout)["plan"]["payload"]["status"], "planned")
            self.assertFalse(config.exists())
            self.assertEqual(list(vault.iterdir()), [])
            plan = json.loads(positive.stdout)["plan"]
            plan_path = base / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            (site_dir / "tomlkit").unlink()
            applied = subprocess.run(
                [str(binary), "-B", str(CLI), "upgrade", "--phase", "apply",
                 "--plan", str(plan_path), "--confirm-plan", plan["plan_id"], "--yes", "--json"],
                env=env, capture_output=True, text=True, timeout=120, check=False,
            )
            self.assertEqual(applied.returncode, 2, applied.stderr)
            self.assertEqual(json.loads(applied.stdout)["reason"], "isolated-dependencies-unavailable")
            self.assertFalse(config.exists())
            self.assertEqual(list(vault.iterdir()), [])
            # Recovery may also be invoked from a different interpreter environment.
            from sbtd_migration_files import snapshot

            (site_dir / "tomlkit").symlink_to(Path(tomlkit.__file__).parent, target_is_directory=True)
            installed = subprocess.run(applied.args, env=env, capture_output=True, text=True,
                                       timeout=120, check=False)
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            recovery_path = vault / "recovery.json"
            recovery = subprocess.run(
                [str(binary), "-B", str(CLI), "recovery", "--phase", "plan",
                 "--upgrade-plan", str(plan_path), "--upgrade-receipt", json.loads(installed.stdout)["receipt_path"],
                 "--output", str(recovery_path), "--json"],
                env=env, capture_output=True, text=True, timeout=120, check=False,
            )
            self.assertEqual(recovery.returncode, 0, recovery.stdout + recovery.stderr)
            recovery_plan = json.loads(recovery.stdout)["plan"]
            vault_before, config_before = snapshot(vault), config.read_bytes()
            (site_dir / "tomlkit").unlink()
            restored = subprocess.run(
                [str(binary), "-B", str(CLI), "recovery", "--phase", "apply",
                 "--upgrade-recovery-plan", str(recovery_path),
                 "--confirm-recovery", recovery_plan["recovery_id"], "--json"],
                env=env, capture_output=True, text=True, timeout=120, check=False,
            )
            self.assertEqual(restored.returncode, 2, restored.stderr)
            self.assertEqual(json.loads(restored.stdout)["reason"], "isolated-dependencies-unavailable")
            self.assertEqual(snapshot(vault), vault_before)
            self.assertEqual(config.read_bytes(), config_before)

    def test_shell_command_dependency_refuses_before_skill_replacement(self):
        """U28: replacing a command's containing Skill must not partially commit."""
        import sbtd_upgrade
        from onboard_contracts import ContractError

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            skills, vault = base / "skills", base / "vault"
            target = skills / "sbtd-task"
            (target / "bin").mkdir(parents=True)
            original = b"---\nname: sbtd-task\n---\nold custom body\n"
            (target / "SKILL.md").write_bytes(original)
            command = target / "bin/graft"
            command.write_bytes(b"#!/bin/sh\nexit 0\n")
            command.chmod(0o755)
            require_private_directory(vault, create=True)
            scope = {"schema_version": 1, "skills_roots": [str(skills)]}
            initial = sbtd_upgrade.plan_upgrade(scope, vault)
            scope["decisions"] = {
                row["target"]: "replace" if row["target"] == str(target) else "preserve"
                for row in initial["payload"]["resources"]
            }
            profile = base / ".bashrc"
            scope["shell_profiles"] = [{"path": str(profile), "shell": "bash", "bin": str(command.parent)}]
            plan = sbtd_upgrade.plan_upgrade(scope, vault)
            with self.assertRaises(ContractError) as caught:
                sbtd_upgrade.apply_upgrade(plan, confirmed=plan["plan_id"])
            self.assertEqual(caught.exception.code, "shell-dependency-conflict")
            self.assertEqual((target / "SKILL.md").read_bytes(), original)
            self.assertEqual(command.read_bytes(), b"#!/bin/sh\nexit 0\n")
            self.assertFalse(profile.exists())

    def _user_created_desired_after_intent(self):
        import sbtd_upgrade

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name).resolve()
        target = base / "AGENTS.md"
        vault = base / "vault"
        require_private_directory(vault, create=True)
        plan = sbtd_upgrade.plan_upgrade(
            {"schema_version": 1, "agents_targets": [str(target)]}, vault,
        )
        desired = (CLI.parents[1] / "templates/agents/AGENTS.global.md").read_bytes()
        real_write = sbtd_upgrade._write_resource

        def user_write(*args, **kwargs):
            target.write_bytes(desired)
            return real_write(*args, **kwargs)

        def in_process(_runner, _argv):
            return sbtd_upgrade._apply_upgrade_local(
                plan, confirmed=plan["plan_id"], receipt=None, package_root=CLI.parents[1],
            )

        with (
            mock.patch.object(sbtd_upgrade, "_run_isolated", in_process),
            mock.patch.object(sbtd_upgrade, "_write_resource", user_write),
        ):
            failed = sbtd_upgrade.apply_upgrade(plan, confirmed=plan["plan_id"])
        self.assertEqual(failed["payload"]["resources"][0]["mutated"], False)
        checkpoints = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in vault.glob("upgrade-receipt-*.json")
        ]
        pending = next(row for row in checkpoints if row["payload"]["resources"][0]["result"] == "pending")
        return plan, failed, pending, target, desired

    def test_retry_does_not_claim_a_proven_unwritten_user_file(self):
        """U25: matching bytes do not override a known no-write result."""
        import sbtd_upgrade
        from onboard_contracts import ContractError

        plan, failed, _pending, target, desired = self._user_created_desired_after_intent()
        with self.assertRaises(ContractError) as caught:
            sbtd_upgrade.apply_upgrade(plan, confirmed=plan["plan_id"], receipt=failed)
        self.assertEqual(caught.exception.code, "state-conflict")
        self.assertEqual(target.read_bytes(), desired)

    def test_old_pending_checkpoint_respects_later_no_write_evidence(self):
        """U25: old checkpoints cannot turn a user file into a recovery deletion."""
        import sbtd_upgrade

        plan, _failed, pending, target, desired = self._user_created_desired_after_intent()
        recovery = sbtd_upgrade.plan_recovery(plan, pending)
        self.assertEqual(recovery["payload"]["steps"], [])
        result = sbtd_upgrade.apply_recovery(recovery, confirmed=recovery["recovery_id"])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(target.read_bytes(), desired)

    def test_pending_written_skill_with_cache_blocks_recovery(self):
        """U25: unknown intent-backed outcomes cannot disappear from recovery."""
        import sbtd_upgrade
        from onboard_contracts import ContractError

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            skills, vault = base / "skills", base / "vault"
            require_private_directory(vault, create=True)
            scope = {"schema_version": 1, "skills_roots": [str(skills)]}
            initial = sbtd_upgrade.plan_upgrade(scope, vault)
            target = skills / "sbtd-task"
            scope["decisions"] = {
                row["target"]: "preserve" for row in initial["payload"]["resources"]
                if row["target"] != str(target)
            }
            plan = sbtd_upgrade.plan_upgrade(scope, vault)
            save = sbtd_upgrade._save_once

            def fail_after_write(path, document, private_root):
                if Path(path).name.startswith("upgrade-receipt-") and any(
                    row["result"] == "succeeded" for row in document["payload"]["resources"]
                ):
                    raise OSError("receipt interruption")
                return save(path, document, private_root)

            with mock.patch.object(sbtd_upgrade, "_save_once", fail_after_write), self.assertRaises(ContractError):
                sbtd_upgrade._apply_upgrade_local(
                    plan, confirmed=plan["plan_id"], receipt=None, package_root=CLI.parents[1],
                )
            pending = json.loads(next(vault.glob("upgrade-receipt-*.json")).read_text(encoding="utf-8"))
            cache = target / "__pycache__/generated.pyc"
            cache.parent.mkdir()
            cache.write_bytes(b"user generated cache")
            recovery = sbtd_upgrade.plan_recovery(plan, pending)
            self.assertEqual(recovery["payload"]["status"], "blocked")
            self.assertEqual(recovery["payload"]["steps"][0]["reason"], "unattributed-outcome")
            with self.assertRaises(ContractError):
                sbtd_upgrade.apply_recovery(recovery, confirmed=recovery["recovery_id"])
            self.assertEqual(cache.read_bytes(), b"user generated cache")
            self.assertTrue((target / "SKILL.md").is_file())

    @unittest.skipUnless(os.name == "posix", "POSIX unknown-user expansion")
    def test_unresolved_home_paths_return_controlled_json(self):
        """U24: input, output and vault expansion failures are metadata-only."""
        import uuid

        unknown = f"~sbtd-missing-{uuid.uuid4().hex}/private-input.json"
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            vault = base / "vault"
            require_private_directory(vault, create=True)
            scope = base / "scope.json"
            scope.write_text(json.dumps({
                "schema_version": 1, "agents_targets": [str(base / "AGENTS.md")],
            }), encoding="utf-8")
            commands = [
                ["upgrade", "--phase", "plan", "--scope", unknown, "--backup-root", str(vault)],
                ["upgrade", "--phase", "plan", "--scope", str(scope), "--backup-root", unknown],
                ["upgrade", "--phase", "plan", "--scope", str(scope), "--backup-root", str(vault), "--output", unknown],
                ["recovery", "--phase", "plan", "--upgrade-plan", unknown, "--upgrade-receipt", unknown],
            ]
            for command in commands:
                with self.subTest(command=command):
                    result = subprocess.run(
                        [sys.executable, "-B", str(CLI), *command, "--json"],
                        capture_output=True, text=True, timeout=120, check=False,
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    document = json.loads(result.stdout)
                    self.assertEqual(document["reason"], "invalid-input")
                    self.assertEqual(document["status"], "blocked")
                    self.assertNotIn(unknown, result.stdout + result.stderr)
            self.assertEqual(list(vault.iterdir()), [])
            self.assertFalse((base / "AGENTS.md").exists())

    def test_undecided_profile_stays_blocked_even_after_disk_alignment(self):
        """U19: sealed consent cannot be supplied by later matching bytes."""
        import sbtd_upgrade
        import sbtd_upgrade_hosts

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            profile = base / ".bashrc"
            profile.write_bytes(b"# user profile\n")
            vault = base / "vault"
            require_private_directory(vault, create=True)
            scope = {
                "schema_version": 1,
                "shell_profiles": [{"path": str(profile), "shell": "bash", "bin": str(base / "bin")}],
            }
            plan = sbtd_upgrade.plan_upgrade(scope, vault)
            self.assertEqual(plan["payload"]["status"], "blocked")
            self.assertEqual(sbtd_upgrade.verify_upgrade(plan)["status"], "blocked")
            resource = sbtd_upgrade_hosts.build_host_resources({
                **scope, "decisions": {str(profile): "replace"},
            })[0]
            profile.write_bytes(sbtd_upgrade_hosts.render_resource(resource))
            self.assertEqual(sbtd_upgrade.verify_upgrade(plan)["status"], "blocked")

    def test_inherited_provider_alias_refuses_before_any_target_write(self):
        """U21: existing foreign-only Codex config aliases an OMP dependency."""
        from tests.test_sbtd_upgrade_inventory import case_variant

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            home = base / "account"
            provider_home = home / ".CODEX"
            provider_home.mkdir(parents=True)
            if case_variant(provider_home) is None:
                self.skipTest("requires a case-insensitive directory")
            provider = provider_home / "config.toml"
            original = b'[mcp_servers.foreign]\ncommand = "unrelated"\n'
            provider.write_bytes(original)
            omp_home = home / ".omp"
            (omp_home / "agent").mkdir(parents=True)
            (omp_home / "agent/config.yml").write_bytes(b'enabledProviders: ["codex"]\n')
            consumer = omp_home / "agent/mcp.json"
            runtime = {}
            for key, filename in (("python", "python"), ("node", "node"), ("cli", "cli.js")):
                path = base / filename
                path.write_bytes(b"")
                runtime[key] = str(path)
            hosts = [
                {
                    "id": name, "platform": name, "config_home": str(config_home),
                    "config": str(config), "onboard_root": str(CLI.parents[1]),
                    "skills_roots": [], "project_roots": [], "runtime": runtime,
                }
                for name, config_home, config in (
                    ("codex", provider_home, provider), ("omp", omp_home, consumer)
                )
            ]
            scope = base / "scope.json"
            scope.write_text(json.dumps({
                "schema_version": 1, "hosts": hosts,
                "decisions": {str(provider): "replace"},
            }), encoding="utf-8")
            vault = base / "vault"
            require_private_directory(vault, create=True)
            plan_path = vault / "plan.json"
            planned = subprocess.run(
                [sys.executable, "-B", str(CLI), "upgrade", "--phase", "plan",
                 "--scope", str(scope), "--backup-root", str(vault),
                 "--output", str(plan_path), "--json"],
                capture_output=True, text=True, timeout=120, check=False,
            )
            self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)
            plan = json.loads(planned.stdout)["plan"]
            applied = subprocess.run(
                [sys.executable, "-B", str(CLI), "upgrade", "--phase", "apply",
                 "--plan", str(plan_path), "--confirm-plan", plan["plan_id"], "--yes", "--json"],
                capture_output=True, text=True, timeout=120, check=False,
            )
            self.assertEqual(
                json.loads(applied.stdout).get("reason"), "inherited-dependency-conflict",
                applied.stdout + applied.stderr,
            )
            self.assertEqual(provider.read_bytes(), original)
            self.assertFalse(consumer.exists())

    def test_canonical_license_checkout_keeps_lf_bytes(self):
        """U14: autocrlf cannot change the canonical license versus its payload."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            environment = {
                key: value for key, value in os.environ.items()
                if not key.startswith("GIT_")
            }
            environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
            subprocess.run(
                ["git", "init", "-q", str(root)], env=environment,
                check=True, capture_output=True,
            )
            (root / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
            expected = (CLI.parents[1] / "LICENSE").read_bytes()
            root_license = root / "LICENSE"
            root_license.write_bytes((ROOT / "LICENSE").read_bytes())
            bundled_license = root / "sbtd-workflow-onboard/LICENSE"
            bundled_license.parent.mkdir()
            bundled_license.write_bytes(expected)
            subprocess.run(
                ["git", "-C", str(root), "-c", "core.autocrlf=true", "add", "."],
                env=environment, check=True, capture_output=True,
            )
            root_license.unlink()
            bundled_license.unlink()
            subprocess.run(
                ["git", "-C", str(root), "-c", "core.autocrlf=true", "checkout-index", "-a", "-f"],
                env=environment, check=True, capture_output=True,
            )
            self.assertEqual(root_license.read_bytes(), expected)
            self.assertEqual(bundled_license.read_bytes(), expected)

    def test_plan_describes_missing_payload_without_writing_targets(self):
        """U01: a real plan inventories payload, but never initializes the target."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            vault = root / "vault"
            require_private_directory(vault, create=True)
            target = root / "skills"
            scope = root / "scope.json"
            scope.write_text(json.dumps({"schema_version": 1, "skills_roots": [str(target)]}), encoding="utf-8")
            environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            result = subprocess.run(
                [sys.executable, "-B", str(CLI), "upgrade", "--phase", "plan",
                 "--scope", str(scope), "--backup-root", str(vault), "--json"],
                capture_output=True, text=True, env=environment, timeout=120, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            document = json.loads(result.stdout)
            plan = document.get("plan", document)
            payload = plan.get("payload", plan)
            resources = {Path(row["target"]).name: row for row in payload["resources"]}
            self.assertEqual(resources["sbtd-task"]["classification"], "missing")
            self.assertEqual(resources["diagnosing-bugs"]["decision"], "install")
            self.assertFalse(target.exists())
            self.assertEqual(list(vault.iterdir()), [])

    def test_upgrade_rejects_cross_phase_or_legacy_recovery_arguments(self):
        """U06: consent for one phase cannot widen another phase's scope."""
        commands = [
            ["upgrade", "--phase", "plan", "--scope", "/scope", "--backup-root", "/vault", "--yes"],
            ["upgrade", "--phase", "apply", "--plan", "/plan", "--scope", "/scope"],
            ["upgrade", "--phase", "verify", "--plan", "/plan", "--yes"],
            ["recovery", "--phase", "plan", "--upgrade-plan", "/plan",
             "--upgrade-receipt", "/receipt", "--manifest", "/legacy"],
            ["recovery", "--phase", "apply", "--upgrade-recovery-plan", "/plan",
             "--upgrade-plan", "/another-plan"],
        ]
        for command in commands:
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, "-B", str(CLI), *command],
                    capture_output=True, text=True, timeout=30, check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("invalid arguments", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_missing_probe_consent_does_not_read_plan_or_launch_host(self):
        """U11: probe permission is independent from the readonly verify phase."""
        result = subprocess.run(
            [sys.executable, "-B", str(CLI), "upgrade", "--phase", "verify",
             "--plan", "/nonexistent-upgrade-plan.json", "--probe", "--json"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["reason"], "probe-confirmation-required")
        import jsonschema

        schema = json.loads((CLI.parents[1] / "upgrade.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(json.loads(result.stdout), schema)

    def test_cli_post_mutation_failure_emits_one_redacted_batch_json(self):
        """R02: a real post-mutation persistence halt surfaces one redacted
        batch JSON; a real pre-write refusal stays blocked without batch."""
        import jsonschema
        import sbtd_upgrade
        import sbtd_upgrade_cli

        schema = json.loads(
            (ROOT / "sbtd-workflow-onboard" / "upgrade.schema.json").read_text(
                encoding="utf-8"
            )
        )

        # Both injection phases share one frozen read-only bootstrap copy;
        # production never writes the package, so the second identical
        # 9MB copytree was redundant.
        package_temporary = tempfile.TemporaryDirectory()
        self.addCleanup(package_temporary.cleanup)
        package = Path(package_temporary.name).resolve() / "bootstrap"
        shutil.copytree(
            CLI.parents[1], package,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

        def real_batch_phase(inject):
            """Drive the public handler over a real plan/vault; only the
            isolated process boundary runs in-process so the persistence
            fault injection can reach it."""
            temporary = tempfile.TemporaryDirectory()
            self.addCleanup(temporary.cleanup)
            root = Path(temporary.name).resolve()
            skills = root / "skills"
            old = skills / "sbtd-workflow-onboard"
            old.mkdir(parents=True)
            original = (
                b"---\nname: sbtd-workflow-onboard\n---\nold installed payload\n"
            )
            (old / "SKILL.md").write_bytes(original)
            vault = root / "vault"
            require_private_directory(vault, create=True)
            scope = {
                "schema_version": 1, "skills_roots": [str(skills)],
                "decisions": {str(old): "replace"},
            }
            plan = sbtd_upgrade.plan_upgrade(scope, str(vault), package_root=str(package))
            plan_file = root / "plan.json"
            plan_file.write_text(json.dumps(plan), encoding="utf-8")
            args = types.SimpleNamespace(
                phase="apply", plan=str(plan_file), receipt=None,
                confirm_plan=plan["plan_id"], yes=True, json=True, probe=False,
                scope=None, backup_root=None, output=None,
            )

            def in_process(runner, argv):
                return sbtd_upgrade._apply_upgrade_local(
                    plan, confirmed=plan["plan_id"], receipt=None,
                    package_root=package,
                )

            buffer = io.StringIO()
            with (
                mock.patch.object(sbtd_upgrade, "_run_isolated", in_process),
                inject(old, plan),
                contextlib.redirect_stdout(buffer),
            ):
                code = sbtd_upgrade_cli.run_upgrade(args)
            return code, json.loads(buffer.getvalue()), buffer.getvalue(), plan, vault, old, original

        def halt_injection(old, plan):
            real_save = sbtd_upgrade._save_once

            def fail_succeeded_receipt(path, document, vault_arg):
                if Path(path).name.startswith("upgrade-receipt-") and any(
                    row.get("result") == "succeeded"
                    for row in document["payload"]["resources"]
                ):
                    raise OSError("injected receipt persistence failure")
                return real_save(path, document, vault_arg)

            return mock.patch.object(sbtd_upgrade, "_save_once", fail_succeeded_receipt)

        code, document, raw, plan, vault, old, original = real_batch_phase(halt_injection)
        self.assertEqual(code, 3)
        self.assertEqual(document["status"], "failed")
        self.assertEqual(document["reason"], "write-failed")
        self.assertEqual(len(raw.strip().splitlines()), 1)
        self.assertNotIn("Traceback", raw)
        batch = document["batch"]
        self.assertEqual(batch["plan_id"], plan["plan_id"])
        self.assertEqual(batch["backup_root"], str(vault))
        persisted = list(vault.glob("upgrade-receipt-*.json"))
        self.assertEqual(len(persisted), 1)
        self.assertEqual(batch["checkpoint"]["path"], str(persisted[0]))
        self.assertNotEqual(batch["checkpoint"]["status"], "complete")
        self.assertEqual(batch["mutation"]["state"], "measured")
        sealed = {
            row["id"]: row for row in plan["payload"]["resources"]
            if row["kind"] == "skill"
        }
        measured = {row["id"]: row for row in batch["mutation"]["resources"]}
        self.assertTrue(measured)
        # The fault fires on the first succeeded receipt: prove the mutation
        # for the resource the batch evidence actually bound, independently
        # of any assumed plan ordering.
        for resource_id, row in measured.items():
            self.assertEqual(row["after"], sealed[resource_id]["desired"])
            source = Path(sealed[resource_id]["source"]["path"])
            target_path = Path(row["target"])
            for payload_file in source.rglob("*"):
                if payload_file.is_file():
                    relative = payload_file.relative_to(source)
                    self.assertEqual(
                        (target_path / relative).read_bytes(),
                        payload_file.read_bytes(),
                    )
        if str(old) not in {row["target"] for row in measured.values()}:
            # The halt stopped the batch before the old Onboard was attempted.
            self.assertEqual((old / "SKILL.md").read_bytes(), original)
        jsonschema.validate(document, schema)

        def prewrite_injection(old, plan):
            (old / "SKILL.md").write_bytes(b"tampered after planning\n")
            return contextlib.nullcontext()

        code, document, raw, plan, vault, old, original = real_batch_phase(prewrite_injection)
        self.assertEqual(code, 2)
        self.assertEqual(document["status"], "blocked")
        self.assertNotIn("batch", document)
        self.assertNotIn("Traceback", raw)
        jsonschema.validate(document, schema)

    def test_empty_upgrade_recovery_paths_return_redacted_json_not_legacy_traceback(self):
        """U06/U15: an empty upgrade path cannot route into legacy recovery."""
        result = subprocess.run(
            [sys.executable, "-B", str(CLI), "recovery", "--phase", "plan",
             "--upgrade-plan", "", "--upgrade-receipt", "", "--json"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "blocked")
        self.assertNotIn("Traceback", result.stderr)

    def test_blank_vault_or_supplied_receipt_never_defaults_to_cwd_or_absence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            vault = root / "vault"
            require_private_directory(vault, create=True)
            scope = root / "scope.json"
            scope.write_text(json.dumps({
                "schema_version": 1, "agents_targets": [str(root / "AGENTS.md")],
            }), encoding="utf-8")
            command = [sys.executable, "-B", str(CLI)]
            blank_vault = subprocess.run(
                [*command, "upgrade", "--phase", "plan", "--scope", str(scope),
                 "--backup-root", "", "--json"], cwd=vault,
                capture_output=True, text=True, timeout=60, check=False,
            )
            self.assertEqual(blank_vault.returncode, 2)
            self.assertEqual(json.loads(blank_vault.stdout)["reason"], "invalid-input")
            self.assertEqual(list(vault.iterdir()), [])
            plan_file = vault / "plan.json"
            plan = subprocess.run(
                [*command, "upgrade", "--phase", "plan", "--scope", str(scope),
                 "--backup-root", str(vault), "--output", str(plan_file), "--json"],
                capture_output=True, text=True, timeout=60, check=False,
            )
            self.assertEqual(plan.returncode, 0, plan.stderr + plan.stdout)
            verify = subprocess.run(
                [*command, "upgrade", "--phase", "verify", "--plan", str(plan_file),
                 "--receipt", "", "--json"], capture_output=True, text=True, timeout=60, check=False,
            )
            self.assertEqual(verify.returncode, 2)
            self.assertEqual(json.loads(verify.stdout)["reason"], "invalid-input")
            self.assertFalse((root / "AGENTS.md").exists())

    def test_installed_copy_retries_and_recovers_without_original_source(self):
        """U03/U07/U09: a real installed package owns the public lifecycle."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "bootstrap"
            shutil.copytree(CLI.parents[1], source, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            skills = root / "skills"
            old = skills / "sbtd-workflow-onboard"
            old.mkdir(parents=True)
            original = b"---\nname: sbtd-workflow-onboard\n---\nold installed payload\n"
            (old / "SKILL.md").write_bytes(original)
            vault = root / "vault"
            require_private_directory(vault, create=True)
            config_home = root / "codex"
            config = config_home / "config.toml"
            profile = root / ".bashrc"
            cli_entry = root / "cli.js"
            cli_entry.write_text("// Not executed: configuration-only runtime fixture.\n", encoding="utf-8")
            runtime = {"python": sys.executable, "node": sys.executable, "cli": str(cli_entry)}
            scope = root / "scope.json"
            scope.write_text(json.dumps({
                "schema_version": 1, "skills_roots": [str(skills)],
                "decisions": {str(old): "replace"},
                "hosts": [{
                    "id": "selected-codex", "platform": "codex",
                    "config_home": str(config_home), "config": str(config),
                    "skills_roots": [str(skills)], "runtime": runtime, "project_roots": [],
                }],
                "shell_profiles": [{"path": str(profile), "shell": "bash", "bin": str(root / "bin")}],
            }), encoding="utf-8")
            plan_path = vault / "plan.json"

            def invoke(package, *arguments):
                result = subprocess.run(
                    [sys.executable, "-B", str(package / "scripts/onboard.py"), *arguments, "--json"],
                    capture_output=True, text=True, timeout=900, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                return json.loads(result.stdout)

            plan = invoke(source, "upgrade", "--phase", "plan", "--scope", str(scope),
                          "--backup-root", str(vault), "--output", str(plan_path))["plan"]
            installed = invoke(source, "upgrade", "--phase", "apply", "--plan", str(plan_path),
                               "--confirm-plan", plan["plan_id"], "--yes")
            self.assertEqual(installed["status"], "complete")
            configured = config.read_text(encoding="utf-8")
            self.assertIn(str(old / "scripts/sbtd_graft_entry.py").replace("\\", "\\\\"), configured)
            self.assertNotIn(str(source), configured)
            shutil.rmtree(source)  # Only the test-owned bootstrap, never user source.
            retry = invoke(old, "upgrade", "--phase", "apply", "--plan", str(plan_path),
                           "--confirm-plan", plan["plan_id"], "--yes",
                           "--receipt", installed["receipt_path"])
            self.assertEqual(retry["status"], "complete")
            recovery_path = vault / "recovery.json"
            recovery = invoke(old, "recovery", "--phase", "plan", "--upgrade-plan", str(plan_path),
                              "--upgrade-receipt", retry["receipt_path"],
                              "--output", str(recovery_path))["plan"]
            restored = invoke(old, "recovery", "--phase", "apply",
                              "--upgrade-recovery-plan", str(recovery_path),
                              "--confirm-recovery", recovery["recovery_id"])
            self.assertEqual(restored["status"], "complete")
            self.assertEqual((old / "SKILL.md").read_bytes(), original)
            self.assertFalse((skills / "sbtd-task").exists())
            self.assertFalse((old / "scripts").exists())
            self.assertFalse(config.exists())
            self.assertFalse(profile.exists())
            self.assertTrue(Path(installed["receipt_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
