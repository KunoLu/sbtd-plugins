from __future__ import annotations
# ruff: noqa: I001 -- local scripts require the explicit test path before import.

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard/scripts"
sys.path.insert(0, str(SCRIPTS))

import onboard_contracts as contracts
from onboard_contracts import ContractError, canonical_json_bytes
from sbtd_graft_deployment import (
    execute_migration_deployment,
    load_deployment_context,
    validate_deployment_declarations,
)
from sbtd_migration import apply_migration, cleanup_migration, runtime_versions
from sbtd_migration_files import save_document, snapshot
from sbtd_migration_plan import plan_migration, validate_legacy_inputs
from sbtd_migration_verify import verify_migration

from tests.test_sbtd_followup_batch import (
    FollowupMigration,
    _focused_installation_templates,
    _graph_fixture,
    _synthetic_smoke,
)
from tests.test_sbtd_migration_apply import legacy_project
from tests.test_sbtd_migration_cleanup import (
    _fake_prepare_trellis_uninstall,
    _fake_vendor_adapter,
)
from tests.test_sbtd_migration_plan import _reader
from tests.test_sbtd_omp_deployment import (
    _legacy_project_with_host_configs,
    _proven_input_environment,
)


class _OmpBatch:
    """Real plan/apply/deploy/verify chain with an OMP init deployment."""

    def __init__(
        self, base: Path, project_files: dict[str, bytes] | None = None
    ) -> None:
        self.base = base
        self.root = legacy_project(base, "project")
        for relative, raw in (project_files or {}).items():
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        self.home = base / "home"
        self.vault = base / "vault"
        self.evidence = base / "evidence"
        self.agent = self.home / ".omp/agent"
        self.codex = self.home / ".codex"
        for path in (self.agent, self.codex, self.vault, self.evidence):
            path.mkdir(parents=True, mode=0o700)
        (self.agent / "config.yml").write_text(
            "enabledProviders: [codex]\n", encoding="utf-8"
        )
        (self.codex / "config.toml").write_text(
            '[mcp_servers.foreign]\ncommand = "/foreign/server"\n',
            encoding="utf-8",
        )
        self.environment = {
            "HOME": str(self.home),
            "USERPROFILE": str(self.home),
            "CODEX_HOME": str(self.codex),
            "AGENT_SKILLS_DIR": str(self.home / ".agent/skills"),
        }
        self.manifest_path = self.evidence / "manifest.json"
        self.deployment_path = self.evidence / "deployment.json"
        self.verification_path = self.evidence / "verification.json"

    def build(self) -> "_OmpBatch":
        with mock.patch.dict(os.environ, self.environment):
            self.manifest = plan_migration(
                [self.root],
                self.vault,
                "fixture",
                None,
                tool_versions=runtime_versions(),
                deployment_mode="init",
                deployment_platform="omp",
            )
            self.manifest_path.write_bytes(canonical_json_bytes(self.manifest))
            applied, code = apply_migration(
                self.manifest_path, confirmed=True, no_routing_approvals=True
            )
            if code != 0:
                raise AssertionError(f"apply failed: {applied}")
            self.apply_receipt = applied["migration"]["apply_receipt"]
            self.apply_path = (
                self.evidence / f"apply-{self.apply_receipt['apply_id']}.json"
            )
            context = load_deployment_context(
                self.manifest_path,
                self.apply_path,
                self.deployment_path,
                previous_path=None,
                mode="init",
                roots=[self.root],
                hooks_authorized=False,
            )
            runtime = {
                "node": "/fixture/node",
                "cli": "/fixture/cli.js",
                "python": "/fixture/python",
            }
            with (
                mock.patch(
                    "sbtd_graft_deployment.verified_runtime",
                    return_value=runtime,
                ),
                mock.patch(
                    "sbtd_graft_deployment.build_project_graph",
                    side_effect=_graph_fixture,
                ),
                mock.patch(
                    "sbtd_graft_deployment.run_project_smoke",
                    side_effect=_synthetic_smoke(self.manifest),
                ),
            ):
                deployed, code = execute_migration_deployment(context)
            if code != 0:
                raise AssertionError(f"deploy failed: {deployed}")
            verified, code = verify_migration(
                self.manifest_path, self.apply_path, self.deployment_path
            )
            if code != 0:
                raise AssertionError(f"verify failed: {verified}")
            self.verification = verified["migration"]["verification"]
            save_document(
                self.verification_path,
                self.verification,
                private_root=self.evidence,
            )
        return self

    def cleanup(self, vendor_prepare=None, vendor_execute=None, **kwargs):
        with (
            mock.patch.dict(os.environ, self.environment),
            _fake_vendor_adapter(prepare=vendor_prepare, execute=vendor_execute),
        ):
            return cleanup_migration(
                self.manifest_path,
                self.apply_path,
                self.deployment_path,
                self.verification_path,
                **kwargs,
            )


class CleanupOnlyDeploymentDriftTests(unittest.TestCase):
    """Phase-aware cleanup dependency validation for sealed OMP inputs.

    A verified OMP migration batch whose deployment-only configuration
    inputs drifted after verification must not be blocked from retiring its
    legacy trees, while the identical drift keeps rejecting every
    deployment-phase consumer and any influencing, managed or unknown drift
    keeps rejecting cleanup itself before the first write.
    """

    def setUp(self):
        overrides = mock.patch.dict(
            os.environ,
            {
                name: ""
                for name in (
                    "OMP_PROFILE",
                    "PI_PROFILE",
                    "PI_CONFIG_DIR",
                    "PI_CODING_AGENT_DIR",
                    "CLAUDE_CONFIG_DIR",
                    "XDG_DATA_HOME",
                )
            },
        )
        overrides.start()
        self.addCleanup(overrides.stop)

    def test_cleanup_without_drift_retires_legacy_tree_with_omp_deployment(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = _OmpBatch(Path(directory).resolve()).build()
            result, code = batch.cleanup(
                confirm_cleanup=batch.verification["verification_id"]
            )
            self.assertEqual(code, 0, result)
            self.assertEqual(result["status"], "cleaned")
            self.assertFalse((batch.root / ".trellis").exists())

    def test_unrelated_config_drift_is_accepted_only_for_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = _OmpBatch(Path(directory).resolve()).build()
            config = batch.agent / "config.yml"
            drifted = b"enabledProviders: [codex]\n# operator note\n"
            self.assertNotEqual(config.read_bytes(), drifted)
            config.write_bytes(drifted)
            codex_raw = (batch.codex / "config.toml").read_bytes()
            mcp_raw = (batch.agent / "mcp.json").read_bytes()
            result, code = batch.cleanup(
                confirm_cleanup=batch.verification["verification_id"]
            )
            self.assertEqual(code, 0, result)
            self.assertEqual(result["status"], "cleaned")
            self.assertFalse((batch.root / ".trellis").exists())
            # The drifted configuration is preserved byte for byte: cleanup
            # neither restores nor edits deployment-only inputs.
            self.assertEqual(config.read_bytes(), drifted)
            self.assertEqual((batch.codex / "config.toml").read_bytes(), codex_raw)
            self.assertEqual((batch.agent / "mcp.json").read_bytes(), mcp_raw)

    def test_the_same_drift_still_rejects_deploy_verify_and_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = _OmpBatch(Path(directory).resolve()).build()
            (batch.agent / "config.yml").write_bytes(
                b"enabledProviders: [codex]\n# operator note\n"
            )
            with mock.patch.dict(os.environ, batch.environment):
                with self.assertRaises(ContractError) as deploy_drift:
                    load_deployment_context(
                        batch.manifest_path,
                        batch.apply_path,
                        batch.evidence / "deployment-2.json",
                        previous_path=batch.deployment_path,
                        mode="init",
                        roots=[batch.root],
                        hooks_authorized=False,
                    )
                self.assertEqual(deploy_drift.exception.code, "state-conflict")
                self.assertIn("drifted", str(deploy_drift.exception))
                with self.assertRaises(ContractError) as verify_drift:
                    verify_migration(
                        batch.manifest_path, batch.apply_path, batch.deployment_path
                    )
                self.assertEqual(verify_drift.exception.code, "state-conflict")
                with self.assertRaises(ContractError) as apply_drift:
                    apply_migration(
                        batch.manifest_path,
                        previous_receipt_path=batch.apply_path,
                        confirmed=True,
                        no_routing_approvals=True,
                    )
                self.assertEqual(apply_drift.exception.code, "state-conflict")
            self.assertFalse((batch.evidence / "deployment-2.json").exists())
            self.assertTrue((batch.root / ".trellis").is_dir())

    def test_cleanup_only_validation_reports_ignored_input_identities(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = legacy_project(base, "project")
            home, vault = base / "home", base / "vault"
            agent = home / ".omp/agent"
            codex = home / ".codex"
            for path in (agent, codex, vault):
                path.mkdir(parents=True, mode=0o700)
            config = agent / "config.yml"
            source = codex / "config.toml"
            config.write_text("enabledProviders: [codex]\n", encoding="utf-8")
            source.write_text(
                '[mcp_servers.foreign]\ncommand = "/foreign/server"\n',
                encoding="utf-8",
            )
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(codex),
                "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
            }
            with mock.patch.dict(os.environ, environment):
                manifest = plan_migration(
                    [root],
                    vault,
                    "fixture",
                    None,
                    tool_versions=runtime_versions(),
                    deployment_mode="init",
                    deployment_platform="omp",
                )
                self.assertIsNone(validate_legacy_inputs(manifest, _reader))
                self.assertEqual(
                    validate_legacy_inputs(manifest, _reader, cleanup_only=True), []
                )
                self.assertIsNone(
                    validate_deployment_declarations(manifest["payload"])
                )
                self.assertEqual(
                    validate_deployment_declarations(
                        manifest["payload"], cleanup_only=True
                    ),
                    [],
                )
                sealed = {
                    str(config): snapshot(config),
                    str(source): snapshot(source),
                }
                config.write_bytes(b"enabledProviders: [codex]\n# note\n")
                source.write_bytes(
                    b'[mcp_servers.foreign]\ncommand = "/foreign/other"\n'
                )
                with _fake_vendor_adapter():
                    with self.assertRaises(ContractError) as default_drift:
                        validate_legacy_inputs(manifest, _reader)
                    self.assertEqual(default_drift.exception.code, "state-conflict")
                    with self.assertRaises(ContractError):
                        validate_deployment_declarations(manifest["payload"])
                    ignored = validate_legacy_inputs(
                        manifest, _reader, cleanup_only=True
                    )
                    direct = validate_deployment_declarations(
                        manifest["payload"], cleanup_only=True
                    )
                self.assertIsInstance(ignored, list)
                self.assertEqual(
                    [entry["path"] for entry in ignored],
                    sorted(sealed),
                    ignored,
                )
                for entry in ignored:
                    self.assertEqual(entry["sealed_state"], sealed[entry["path"]])
                    self.assertEqual(
                        entry["live_state"], snapshot(Path(entry["path"]))
                    )
                    self.assertEqual(entry["sealed_state"]["type"], "file")
                    self.assertEqual(entry["live_state"]["type"], "file")
                    self.assertNotEqual(
                        entry["sealed_state"]["checksum"],
                        entry["live_state"]["checksum"],
                    )
                self.assertEqual(direct, ignored)

    def test_managed_target_drift_remains_rejected_for_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root, host_configs = _legacy_project_with_host_configs(base)
            home, vault, evidence = (
                base / name for name in ("home", "vault", "evidence")
            )
            for path in (home, vault, evidence):
                path.mkdir(mode=0o700)
            environment, asset = _proven_input_environment(home, host_configs, base)
            with mock.patch.dict(os.environ, environment), asset:
                manifest = plan_migration(
                    [root],
                    vault,
                    "fixture",
                    None,
                    tool_versions=runtime_versions(),
                    deployment_mode="init",
                    deployment_platform="omp",
                )
                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(manifest))
                applied, code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
                self.assertEqual(code, 0, applied)
                receipt = applied["migration"]["apply_receipt"]
                apply_path = evidence / f"apply-{receipt['apply_id']}.json"
                context = load_deployment_context(
                    manifest_path,
                    apply_path,
                    evidence / "deployment.json",
                    previous_path=None,
                    mode="init",
                    roots=[root],
                    hooks_authorized=False,
                )
                runtime = {
                    "node": "/fixture/node",
                    "cli": "/fixture/cli.js",
                    "python": "/fixture/python",
                }
                with (
                    mock.patch(
                        "sbtd_graft_deployment.verified_runtime",
                        return_value=runtime,
                    ),
                    mock.patch(
                        "sbtd_graft_deployment.build_project_graph",
                        side_effect=_graph_fixture,
                    ),
                    mock.patch(
                        "sbtd_graft_deployment.run_project_smoke",
                        side_effect=_synthetic_smoke(manifest),
                    ),
                ):
                    deployed, code = execute_migration_deployment(context)
                self.assertEqual(code, 0, deployed)
                verified, code = verify_migration(
                    manifest_path, apply_path, evidence / "deployment.json"
                )
                self.assertEqual(code, 0, verified)
                verification = verified["migration"]["verification"]
                verification_path = evidence / "verification.json"
                save_document(
                    verification_path, verification, private_root=evidence
                )
                # An approved apply removal proved this sealed input absent;
                # unapproved new bytes on the managed target keep the
                # historical drift rejection on the cleanup path as well.
                (root / ".codex/config.toml").write_bytes(
                    b'model = "unapproved"\n'
                )
                with _fake_vendor_adapter():
                    with self.assertRaises(ContractError) as drift:
                        cleanup_migration(
                            manifest_path,
                            apply_path,
                            evidence / "deployment.json",
                            verification_path,
                            confirm_cleanup=verification["verification_id"],
                        )
                self.assertEqual(drift.exception.code, "state-conflict")
                self.assertIn("drifted", str(drift.exception))
                self.assertTrue((root / ".trellis").is_dir())
                self.assertEqual(list(evidence.glob("cleanup-*.json")), [])

    def test_scope_influencing_config_drift_remains_rejected_for_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = _OmpBatch(Path(directory).resolve()).build()
            # Selecting different providers changes the discovered source
            # set itself, so this configuration drift is never cleanup-safe.
            (batch.agent / "config.yml").write_bytes(
                b"enabledProviders: [claude]\n"
            )
            with self.assertRaises(ContractError) as drift:
                batch.cleanup(
                    confirm_cleanup=batch.verification["verification_id"]
                )
            self.assertEqual(drift.exception.code, "state-conflict")
            self.assertIn("drifted", str(drift.exception))
            self.assertTrue((batch.root / ".trellis").is_dir())
            self.assertEqual(list(batch.evidence.glob("cleanup-*.json")), [])

    def test_irrelevant_project_source_appearing_is_accepted_for_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = _OmpBatch(Path(directory).resolve()).build()
            # A previously absent project-level source appears below the
            # selected root, but outside the actual vendor footprint (the
            # .trellis tree here) and outside every operation, ownership,
            # source and backup dependency, so cleanup may proceed.
            (batch.root / ".claude").mkdir()
            appeared = batch.root / ".claude/mcp.json"
            raw = b'{"mcpServers": {"foreign": {"command": "/foreign/server"}}}'
            appeared.write_bytes(raw)
            result, code = batch.cleanup(
                confirm_cleanup=batch.verification["verification_id"]
            )
            self.assertEqual(code, 0, result)
            self.assertEqual(result["status"], "cleaned")
            self.assertFalse((batch.root / ".trellis").exists())
            self.assertEqual(appeared.read_bytes(), raw)

    def test_absent_home_input_appearing_is_accepted_for_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = _OmpBatch(Path(directory).resolve()).build()
            # The alternate native source was sealed absent; appearing below
            # the agent directory is an absent-to-file transition disjoint
            # from every cleanup dependency, so it no longer blocks.
            appeared = batch.agent / ".mcp.json"
            raw = b'{"mcpServers": {}}'
            appeared.write_bytes(raw)
            result, code = batch.cleanup(
                confirm_cleanup=batch.verification["verification_id"]
            )
            self.assertEqual(code, 0, result)
            self.assertEqual(result["status"], "cleaned")
            self.assertFalse((batch.root / ".trellis").exists())
            self.assertEqual(appeared.read_bytes(), raw)

    def test_project_settings_file_drift_is_accepted_for_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = _OmpBatch(
                Path(directory).resolve(),
                project_files={
                    ".claude/settings.json": b'{"legacyRouting": true}\n',
                    ".codex/config.toml": (
                        b'[mcp_servers.foreign]\ncommand = "/foreign/one"\n'
                    ),
                },
            ).build()
            settings_raw = b'{"legacyRouting": false}\n'
            config_raw = b'[mcp_servers.foreign]\ncommand = "/foreign/two"\n'
            (batch.root / ".claude/settings.json").write_bytes(settings_raw)
            (batch.root / ".codex/config.toml").write_bytes(config_raw)
            result, code = batch.cleanup(
                confirm_cleanup=batch.verification["verification_id"]
            )
            self.assertEqual(code, 0, result)
            self.assertEqual(result["status"], "cleaned")
            self.assertFalse((batch.root / ".trellis").exists())
            self.assertEqual(
                (batch.root / ".claude/settings.json").read_bytes(), settings_raw
            )
            self.assertEqual(
                (batch.root / ".codex/config.toml").read_bytes(), config_raw
            )

    def test_project_settings_file_removal_is_accepted_for_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = _OmpBatch(
                Path(directory).resolve(),
                project_files={
                    ".claude/settings.json": b'{"legacyRouting": true}\n',
                    ".codex/config.toml": (
                        b'[mcp_servers.foreign]\ncommand = "/foreign/one"\n'
                    ),
                },
            ).build()
            (batch.root / ".claude/settings.json").unlink()
            (batch.root / ".codex/config.toml").unlink()
            result, code = batch.cleanup(
                confirm_cleanup=batch.verification["verification_id"]
            )
            self.assertEqual(code, 0, result)
            self.assertEqual(result["status"], "cleaned")
            self.assertFalse((batch.root / ".trellis").exists())
            self.assertFalse((batch.root / ".claude/settings.json").exists())
            self.assertFalse((batch.root / ".codex/config.toml").exists())

    def test_write_target_drift_remains_rejected_for_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = _OmpBatch(Path(directory).resolve()).build()
            # The deployed MCP resource is an explicit deployment write
            # target and a retained asset; any late change keeps cleanup
            # rejected before the first write.
            target = batch.agent / "mcp.json"
            drifted = target.read_bytes() + b"\n"
            target.write_bytes(drifted)
            with self.assertRaises(ContractError) as drift:
                batch.cleanup(
                    confirm_cleanup=batch.verification["verification_id"]
                )
            self.assertEqual(drift.exception.code, "state-conflict")
            self.assertIn("retained asset", str(drift.exception))
            self.assertTrue((batch.root / ".trellis").is_dir())
            self.assertEqual(target.read_bytes(), drifted)
            self.assertEqual(list(batch.evidence.glob("cleanup-*.json")), [])

    def test_retry_with_drift_skips_proven_cleaned_footprint(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = _OmpBatch(Path(directory).resolve()).build()
            result, code = batch.cleanup(
                confirm_cleanup=batch.verification["verification_id"]
            )
            self.assertEqual(code, 0, result)
            receipt = result["migration"]["cleanup_receipt"]
            receipt_path = batch.evidence / f"cleanup-{receipt['cleanup_id']}.json"
            self.assertTrue(receipt_path.is_file())
            (batch.agent / "config.yml").write_bytes(
                b"enabledProviders: [codex]\n# operator note\n"
            )

            def exploding_prepare(_root):
                raise AssertionError(
                    "the vendor planner must not run for a proven cleaned tree"
                )

            retried, retry_code = batch.cleanup(
                vendor_prepare=exploding_prepare,
                previous_receipt_path=receipt_path,
                confirm_cleanup=batch.verification["verification_id"],
            )
            self.assertEqual(retry_code, 0, retried)
            self.assertEqual(retried["status"], "already-complete")

    def test_input_becoming_vendor_effect_remains_rejected_for_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = _OmpBatch(Path(directory).resolve()).build()
            # The vendor's actual current footprint, not the project root,
            # decides participation: once the planner carries a path, a
            # late-appearing input there becomes a vendor effect and its
            # drift keeps the historical rejection.
            effect = batch.root / ".codex/config.toml"
            effect.write_text(
                '[mcp_servers.foreign]\ncommand = "/foreign/server"\n',
                encoding="utf-8",
            )

            def prepare_with_config_effect(root):
                prepared = _fake_prepare_trellis_uninstall(root)
                prepared["payload"]["resources"].append(
                    {
                        "kind": "vendor-delete",
                        "path": str(root / ".codex/config.toml"),
                        "before": snapshot(root / ".codex/config.toml"),
                        "expected_after": {"type": "absent", "checksum": None},
                    }
                )
                return prepared

            with self.assertRaises(ContractError) as drift:
                batch.cleanup(
                    vendor_prepare=prepare_with_config_effect,
                    confirm_cleanup=batch.verification["verification_id"],
                )
            self.assertEqual(drift.exception.code, "state-conflict")
            self.assertIn("drifted", str(drift.exception))
            self.assertTrue((batch.root / ".trellis").is_dir())
            self.assertTrue(effect.is_file())
            self.assertEqual(list(batch.evidence.glob("cleanup-*.json")), [])

    def test_unknown_cleanup_target_kind_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = _OmpBatch(Path(directory).resolve()).build()
            payload = copy.deepcopy(batch.manifest["payload"])
            retirement = next(
                operation
                for project in payload["projects"]
                for operation in project["private_operations"]
                if operation["phase"] == "cleanup"
            )
            retirement["selector"] = "trellis-block"
            (batch.agent / "config.yml").write_bytes(
                b"enabledProviders: [codex]\n# operator note\n"
            )
            with mock.patch.dict(os.environ, batch.environment):
                with self.assertRaises(ContractError) as drift:
                    validate_deployment_declarations(payload, cleanup_only=True)
            self.assertEqual(drift.exception.code, "scope-conflict")
            self.assertIn("unknown target kind", str(drift.exception))

    def test_forged_non_file_sealed_state_is_no_waiver(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = _OmpBatch(Path(directory).resolve()).build()
            payload = copy.deepcopy(batch.manifest["payload"])
            config = str(batch.agent / "config.yml")
            entry = next(
                item
                for item in payload["deployment"]["inputs"]
                if item["path"] == config
            )
            entry["state"] = {"type": "directory", "checksum": "0" * 64}
            (batch.agent / "config.yml").write_bytes(
                b"enabledProviders: [codex]\n# operator note\n"
            )
            with mock.patch.dict(os.environ, batch.environment):
                with _fake_vendor_adapter():
                    with self.assertRaises(ContractError) as drift:
                        validate_deployment_declarations(payload, cleanup_only=True)
            self.assertEqual(drift.exception.code, "state-conflict")
            self.assertIn("drifted", str(drift.exception))

    def test_symlinked_config_input_never_becomes_a_waiver(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = _OmpBatch(Path(directory).resolve()).build()
            config = batch.agent / "config.yml"
            raw = config.read_bytes()
            substitute = batch.agent / "substitute.yml"
            substitute.write_bytes(raw)
            config.unlink()
            os.symlink("substitute.yml", config)
            with self.assertRaises(ContractError) as drift:
                batch.cleanup(
                    confirm_cleanup=batch.verification["verification_id"]
                )
            self.assertEqual(drift.exception.code, "unsafe-path")
            self.assertTrue((batch.root / ".trellis").is_dir())
            self.assertTrue(config.is_symlink())
            self.assertEqual(list(batch.evidence.glob("cleanup-*.json")), [])


class FollowupUpgradeProvenanceGateTests(unittest.TestCase):
    """Upgrade-backed cleanup provenance never crosses a followup binding.

    The native upgrade receipt trust is restricted to the exact cleanup
    invocation that consumed its bound upgrade evidence; the shared
    followup predecessor binder re-proves nothing of it, so an
    upgrade-backed predecessor cleanup fails closed both when planning a
    new followup and when an already sealed followup is consumed.
    """

    def setUp(self):
        # Binding invariants never depend on the full skill catalog.
        _focused_installation_templates(self)

    def test_followup_rejects_upgrade_backed_predecessor_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            digest = "0" * 64
            provenance = {
                "schema": "cleanup-upgrade-provenance",
                "schema_version": 1,
                "plan_id": digest,
                "receipt_id": digest,
                "baseline_id": "sha256:" + digest,
                "resource_id": "skill:sbtd-workflow-onboard@2.0.0-rc.3",
                "backup_root": str(fixture.vault),
                "plan_ref": {
                    "path": str(fixture.evidence / "upgrade-plan.json"),
                    "state": {"type": "file", "checksum": digest},
                },
                "receipt_ref": {
                    "path": str(fixture.evidence / "upgrade-receipt.json"),
                    "state": {"type": "file", "checksum": digest},
                },
                "current_package": {
                    "path": str(fixture.evidence / "current-package"),
                    "state": {"type": "directory", "checksum": digest},
                },
                "previous_package": {
                    "path": str(fixture.evidence / "previous-package"),
                    "state": {"type": "directory", "checksum": digest},
                },
                "previous_payload_state": {
                    "type": "directory",
                    "checksum": digest,
                },
            }
            receipt = json.loads(fixture.cleanup_path.read_bytes())
            receipt["payload"]["upgrade_context"] = provenance
            upgraded = contracts.seal_document("cleanup_receipt", receipt["payload"])
            upgraded_path = fixture.evidence / "cleanup-upgrade-backed.json"
            upgraded_path.write_bytes(canonical_json_bytes(upgraded))

            # Planning a new followup over the upgrade-backed chain fails.
            with self.assertRaises(ContractError) as planning:
                fixture.plan_followup(followup_cleanup_receipt=upgraded_path)
            self.assertEqual(planning.exception.code, "upgrade-lineage-conflict")

            # An already sealed ordinary followup binding the original
            # receipt keeps its consumption rejection once the referenced
            # cleanup carries upgrade provenance.
            followup = fixture.plan_followup()
            tampered = json.loads(canonical_json_bytes(followup))
            tampered["payload"]["followup"]["cleanup_id"] = upgraded["cleanup_id"]
            tampered["payload"]["followup"]["cleanup_receipt_ref"] = {
                "path": str(upgraded_path),
                "state": snapshot(upgraded_path),
            }
            with (
                mock.patch.dict(os.environ, fixture.environment),
                self.assertRaises(ContractError) as consumption,
            ):
                validate_legacy_inputs(
                    contracts.seal_document("manifest", tampered["payload"]),
                    _reader,
                )
            self.assertEqual(consumption.exception.code, "upgrade-lineage-conflict")


if __name__ == "__main__":
    unittest.main()
