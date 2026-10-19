"""OMP current-state reconciliation lifecycle; native boundaries are fixtures.

Normal cases build one genuine OMP batch (plan/apply/deploy) in an isolated HOME;
its historical deployment receipt is then lost and reconciliation observes
the current state. Covers the two truthful OMP configure outcomes — a real
absent-to-desired mcp.json write and the inherited user-wide equivalent
no-op that intentionally leaves the target absent — plus refusal guards.
The native graph/smoke doubles are contract-backed fixtures, not real host
proof (合成夹具；不证明真实 host 部署。).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import onboard_contracts as contracts
from sbtd_graft_deployment import execute_migration_deployment, load_deployment_context
from sbtd_migration import apply_migration, runtime_versions
from sbtd_migration_files import snapshot
from sbtd_migration_plan import plan_migration
from sbtd_migration_verify import verify_migration
from sbtd_omp_wiring import desired_omp_server
from sbtd_reconciliation import reconcile_deployment

from tests.test_sbtd_followup_batch import _graph_fixture, _synthetic_smoke
from tests.test_sbtd_migration_apply import legacy_project
from tests.test_sbtd_migration_verify import _tree_bytes
from tests.test_sbtd_reconciliation import (
    _apply_only_operation,
    _drift_target,
    _stage_results,
)

_RUNTIME = {"node": "/fixture/node", "cli": "/fixture/cli.js", "python": "/fixture/python"}
_ABSENT = {"type": "absent", "checksum": None}


class _OmpBatch:
    """One genuinely deployed OMP batch whose historical receipt is then lost.

    With ``inherited_equivalent`` the Codex user configuration already carries
    an equivalent user-wide sbtd-graft entry, so the genuine deployment
    intentionally leaves the active mcp.json absent. With
    ``manifest_in_agent_dir`` the manifest private directory IS the active OMP
    agent directory, so sealed OMP configuration inputs sit beside the
    evidence paths.

    The present-empty negative case stops after genuine plan/apply and
    supplies current post-state separately, without claiming native deploy
    success; reconciliation must still validate the retained original type.
    """

    def __init__(
        self, case, *, inherited_equivalent=False, manifest_in_agent_dir=False,
        present_empty_original=False, no_touch=False,
    ):
        directory = tempfile.TemporaryDirectory()
        case.addCleanup(directory.cleanup)
        base = Path(directory.name).resolve()
        self.base = base
        self.root = legacy_project(base, "project")
        if no_touch:
            from onboard import PROJECT_AGENTS_TEMPLATE

            (self.root / "AGENTS.md").write_bytes(PROJECT_AGENTS_TEMPLATE.read_bytes())
            hashes_path = self.root / ".trellis/.template-hashes.json"
            hashes = json.loads(hashes_path.read_bytes())
            hashes["hashes"]["AGENTS.md"] = hashlib.sha256(b"old owned rules").hexdigest()
            hashes_path.write_text(json.dumps(hashes), encoding="utf-8")
        self.home = base / "home"
        self.agent = self.home / ".omp/agent"
        self.codex = self.home / ".codex"
        self.vault = base / "vault"
        self.evidence = base / "evidence"
        for path in (self.agent, self.codex, self.vault, self.evidence):
            path.mkdir(parents=True, mode=0o700)
        self.environment = {
            "HOME": str(self.home),
            "USERPROFILE": str(self.home),
            "CODEX_HOME": str(self.codex),
            "AGENT_SKILLS_DIR": str(self.home / ".agent/skills"),
            "PI_CODING_AGENT_DIR": str(self.agent),
            "PI_CONFIG_DIR": ".omp",
            "OMP_PROFILE": "default",
            "PI_PROFILE": "default",
            "PI_CONFIG_FILES": "",
            "CLAUDE_CONFIG_DIR": str(self.home / ".claude"),
            "XDG_DATA_HOME": str(self.home / ".local/share"),
        }
        if inherited_equivalent:
            launcher = (
                self.home
                / ".agent/skills/sbtd-workflow-onboard/scripts/sbtd_graft_entry.py"
            )
            desired = desired_omp_server({**_RUNTIME, "launcher": str(launcher)})
            (self.agent / "config.yml").write_text(
                "enabledProviders: [codex]\n", encoding="utf-8"
            )
            (self.codex / "config.toml").write_text(
                "[mcp_servers.sbtd-graft]\n"
                f'command = "{desired["command"]}"\n'
                "args = "
                + json.dumps(desired["args"])
                + "\n"
                '[mcp_servers.sbtd-graft.env]\nDO_NOT_TRACK = "1"\nDNT = "1"\n',
                encoding="utf-8",
            )
        if present_empty_original:
            (self.agent / "mcp.json").write_bytes(b"")
        manifest_dir = self.agent if manifest_in_agent_dir else self.evidence
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
            case.assertEqual(self.omp_operation()["target"], str(self.agent / "mcp.json"))
            self.manifest_path = manifest_dir / "manifest.json"
            self.manifest_path.write_bytes(
                contracts.canonical_json_bytes(self.manifest)
            )
            applied, code = apply_migration(
                self.manifest_path, confirmed=True, no_routing_approvals=True
            )
            if code != 0:
                raise AssertionError(f"fixture apply failed: {applied}")
            receipt = applied["migration"]["apply_receipt"]
            self.apply_path = manifest_dir / ("apply-" + receipt["apply_id"] + ".json")
            self.missing_path = manifest_dir / "interrupted-deployment.json"
            if present_empty_original:
                # This case supplies current state later; it deliberately
                # makes no claim that normal deployment accepted empty JSON.
                self.target = self.agent / "mcp.json"
                return
            context = load_deployment_context(
                self.manifest_path,
                self.apply_path,
                self.missing_path,
                previous_path=None,
                mode="init",
                roots=[self.root],
                hooks_authorized=False,
            )
            with (
                mock.patch(
                    "sbtd_graft_deployment.verified_runtime",
                    return_value=dict(_RUNTIME),
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
                raise AssertionError(f"fixture deployment failed: {deployed}")
            self.missing_path.unlink()
        self.target = self.agent / "mcp.json"

    def omp_operation(self):
        return next(
            operation
            for operation in self.manifest["payload"]["shared_operations"]
            if operation["selector"] == "graft-omp-mcp"
        )


def _reconcile(batch, output_path, *, smoke=None):
    """Reconcile under the same contract-backed native doubles as the Codex suite."""
    with (
        mock.patch.dict(os.environ, batch.environment),
        mock.patch(
            "sbtd_graft_deployment.verified_runtime",
            return_value=dict(_RUNTIME),
        ),
        mock.patch(
            "sbtd_graft_deployment.run_project_smoke",
            side_effect=_synthetic_smoke(batch.manifest) if smoke is None else smoke,
        ),
        mock.patch(
            "sbtd_graft_deployment.build_project_graph",
            side_effect=AssertionError("reconciliation must not rebuild"),
        ),
        mock.patch(
            "sbtd_graft_deployment.execute_resource",
            side_effect=AssertionError("reconciliation must not deploy"),
        ),
    ):
        return reconcile_deployment(
            batch.manifest_path,
            batch.apply_path,
            batch.missing_path,
            output_path,
            confirmed=True,
        )


def _observed_omp_result(batch, evidence):
    return {
        result["resource_id"]: result
        for result in evidence["payload"]["shared_results"]
    }[batch.omp_operation()["resource_id"]]


class OmpCurrentStateReconciliationLifecycleTests(unittest.TestCase):
    def test_no_touch_inputs_rechecked_after_provenance(self):
        import sbtd_graft_deployment as deployment
        import sbtd_migration as migration

        for consumer in ("reconcile", "retry"):
            with self.subTest(consumer=consumer):
                batch = _OmpBatch(self, no_touch=True)
                proof = batch.manifest["payload"]["projects"][0]["agents_no_touch"]
                agents = Path(proof["target"]["path"])
                output = batch.evidence / "current-state.json"
                if consumer == "retry":
                    _reconcile(batch, output)
                    previous = output
                    output = batch.evidence / "retry.json"
                    with mock.patch.dict(os.environ, batch.environment):
                        context = load_deployment_context(
                            batch.manifest_path, batch.apply_path, output,
                            previous_path=previous, mode="init", roots=[batch.root],
                            hooks_authorized=False,
                        )
                real_result = contracts.validate_deployment_result
                real_provenance = migration._require_reconciliation_provenance
                stage = {"ready": False}
                damaged = agents.read_bytes() + b"\nconcurrent no-touch drift\n"

                def after_result(*args, stage=stage, real_result=real_result, **kwargs):
                    result = real_result(*args, **kwargs)
                    stage["ready"] = True
                    return result

                def after_provenance(
                    *args, stage=stage, real_provenance=real_provenance,
                    agents=agents, damaged=damaged, **kwargs,
                ):
                    refs = real_provenance(*args, **kwargs)
                    if stage["ready"]:
                        agents.write_bytes(damaged)
                    return refs

                with (
                    mock.patch.object(contracts, "validate_deployment_result", side_effect=after_result),
                    mock.patch.object(migration, "_require_reconciliation_provenance", side_effect=after_provenance),
                ):
                    if consumer == "reconcile":
                        with self.assertRaises(contracts.ContractError):
                            _reconcile(batch, output)
                    else:
                        with (
                            mock.patch.dict(os.environ, batch.environment),
                            mock.patch.object(deployment, "verified_runtime", return_value=dict(_RUNTIME)),
                            mock.patch.object(deployment, "run_project_smoke", side_effect=_synthetic_smoke(batch.manifest)),
                            mock.patch.object(deployment, "build_project_graph", side_effect=AssertionError("no rebuild")),
                        ):
                            result, code = execute_migration_deployment(context)
                        self.assertEqual(code, 5, result)
                        self.assertIsNone(result["deploymentEvidence"])
                self.assertFalse(output.exists())
                self.assertEqual(agents.read_bytes(), damaged)

    def test_present_empty_omp_original_fails_closed(self):
        import sbtd_graft_deployment as deployment
        from sbtd_migration_files import backup_reference

        batch = _OmpBatch(self, present_empty_original=True)
        package = batch.home / ".agent/skills/sbtd-workflow-onboard"
        shutil.copytree(deployment._PACKAGE, package)
        bindings = deployment.launch_bindings(
            [batch.root], _RUNTIME, package_root=package
        )
        resolution = contracts.resolution_stage_results(
            batch.manifest["payload"], {"apply": _stage_results(batch.apply_path)}
        )
        operations = [
            operation
            for project in batch.manifest["payload"]["projects"]
            for operation in project["private_operations"]
            if operation["phase"] == "deploy"
        ] + [
            operation for operation in batch.manifest["payload"]["shared_operations"]
            if operation["phase"] == "deploy"
        ]
        with (
            mock.patch.dict(os.environ, batch.environment),
            mock.patch("sbtd_graft_deployment.build_project_graph", side_effect=_graph_fixture),
        ):
            for operation in operations:
                expected = contracts._expected_before(operation["before_requirement"], resolution)
                backup = batch.vault / batch.manifest["manifest_id"] / "deploy" / operation["resource_id"]
                if operation["selector"] == "graft-omp-mcp":
                    # Preserve the actual sealed empty file, then supply a
                    # plausible nonempty post-state. History remains unknown;
                    # validation must derive from the original, not live size.
                    deployment._prepare_target_parents(backup, batch.vault)
                    backup_reference(
                        {"path": str(batch.target), "state": expected},
                        backup, private_root=batch.vault,
                    )
                    batch.target.write_bytes(b"{}")
                    batch.target.write_bytes(deployment.render_configuration(operation, b"", bindings))
                else:
                    target = Path(operation["target"])
                    if target == package:
                        # The canonical runtime was copied above so bindings
                        # can be constructed; its planned original was absent.
                        self.assertEqual(expected, _ABSENT)
                        self.assertEqual(snapshot(package), operation["change"]["source_ref"]["state"])
                        continue
                    result = deployment.execute_resource(
                        operation, expected=expected,
                        root=batch.root if target.is_relative_to(batch.root) else batch.home,
                        private_root=batch.vault, backup_path=backup, bindings=bindings,
                        runtime=_RUNTIME, launcher_state=snapshot(deployment._PACKAGE),
                        install_template=True,
                    )
                    self.assertEqual(result["status"], "succeeded", (operation, result))
        output_path = batch.evidence / "current-state-evidence.json"
        original_state = snapshot(batch.vault)
        current_state = snapshot(batch.target)
        with self.assertRaises(contracts.ContractError) as failure:
            _reconcile(batch, output_path)
        self.assertEqual(failure.exception.code, "invalid-json")
        self.assertFalse(output_path.exists())
        self.assertFalse(batch.missing_path.exists())
        self.assertEqual(snapshot(batch.vault), original_state)
        self.assertEqual(snapshot(batch.target), current_state)

    def test_changed_omp_target_reconciles_and_verifies(self):
        batch = _OmpBatch(self)
        # The genuine deployment wrote the desired rootless sbtd-graft entry:
        # the target really changed absent -> desired file.
        self.assertTrue(batch.target.is_file())
        deployed_bytes = batch.target.read_bytes()
        servers = json.loads(deployed_bytes)["mcpServers"]
        self.assertEqual(set(servers), {"sbtd-graft"})
        project_before = _tree_bytes(batch.root)
        home_before = _tree_bytes(batch.home)
        originals_before = _tree_bytes(batch.vault)
        manifest_before = batch.manifest_path.read_bytes()
        apply_before = batch.apply_path.read_bytes()
        output_path = batch.evidence / "current-state-evidence.json"

        result = _reconcile(batch, output_path)
        evidence = result["evidence"]
        self.assertEqual(
            evidence["payload"]["reconciliation"]["kind"], "current-state"
        )
        observed = _observed_omp_result(batch, evidence)
        # The derived result proves the sealed absent before-state and the
        # freshly measured deployed file — never a caller-supplied echo.
        self.assertEqual(observed["status"], "succeeded")
        self.assertEqual(observed["before"], _ABSENT)
        self.assertEqual(observed["after"], snapshot(batch.target))
        self.assertIsNone(observed["backup_ref"])

        with mock.patch.dict(os.environ, batch.environment):
            verified, verify_code = verify_migration(
                batch.manifest_path, batch.apply_path, output_path
            )
        self.assertEqual(verify_code, 0, verified)
        self.assertEqual(
            verified["migration"]["verification"]["payload"]["acceptance_basis"],
            "current-state",
        )
        # Zero target/history/input mutation: only new evidence appeared.
        self.assertEqual(batch.target.read_bytes(), deployed_bytes)
        self.assertFalse(batch.missing_path.exists())
        self.assertEqual(_tree_bytes(batch.root), project_before)
        self.assertEqual(_tree_bytes(batch.home), home_before)
        self.assertEqual(_tree_bytes(batch.vault), originals_before)
        self.assertEqual(batch.manifest_path.read_bytes(), manifest_before)
        self.assertEqual(batch.apply_path.read_bytes(), apply_before)

    def test_inherited_equivalent_absent_noop_reconciles(self):
        batch = _OmpBatch(self, inherited_equivalent=True)
        # The inherited user-wide equivalent intentionally kept the genuine
        # deployment from writing: the declared outcome is absence itself.
        self.assertFalse(batch.target.exists())
        output_path = batch.evidence / "current-state-evidence.json"

        result = _reconcile(batch, output_path)
        observed = _observed_omp_result(batch, result["evidence"])
        self.assertEqual(observed["status"], "succeeded")
        self.assertEqual(observed["before"], _ABSENT)
        self.assertEqual(observed["after"], _ABSENT)
        self.assertIsNone(observed["backup_ref"])

        with mock.patch.dict(os.environ, batch.environment):
            verified, verify_code = verify_migration(
                batch.manifest_path, batch.apply_path, output_path
            )
        self.assertEqual(verify_code, 0, verified)
        self.assertEqual(
            verified["migration"]["verification"]["payload"]["acceptance_basis"],
            "current-state",
        )
        self.assertFalse(batch.target.exists())
        self.assertFalse(batch.missing_path.exists())


class OmpCurrentStateReconciliationRefusalTests(unittest.TestCase):
    def test_tampered_omp_target_fails_closed_without_repairs(self):
        batch = _OmpBatch(self)
        raw = json.loads(batch.target.read_bytes())
        raw["mcpServers"]["sbtd-graft"]["args"] = ["/tampered/launcher"]
        batch.target.write_text(json.dumps(raw), encoding="utf-8")
        tampered = batch.target.read_bytes()
        evidence_before = _tree_bytes(batch.evidence)
        output_path = batch.evidence / "current-state-evidence.json"

        with self.assertRaises(contracts.ContractError) as failure:
            _reconcile(batch, output_path)
        self.assertEqual(failure.exception.code, "state-conflict")
        self.assertFalse(output_path.exists())
        self.assertFalse(batch.missing_path.exists())
        self.assertEqual(batch.target.read_bytes(), tampered)
        self.assertEqual(_tree_bytes(batch.evidence), evidence_before)

    def test_appearing_target_breaks_inherited_noop(self):
        # The inherited no-op declares absence; a target that appears later is
        # drift, not an equivalent outcome.
        batch = _OmpBatch(self, inherited_equivalent=True)
        batch.target.write_bytes(b'{"mcpServers": {}}\n')
        appeared = batch.target.read_bytes()
        output_path = batch.evidence / "current-state-evidence.json"

        with self.assertRaises(contracts.ContractError) as failure:
            _reconcile(batch, output_path)
        self.assertEqual(failure.exception.code, "state-conflict")
        self.assertFalse(output_path.exists())
        self.assertFalse(batch.missing_path.exists())
        self.assertEqual(batch.target.read_bytes(), appeared)

    def test_evidence_paths_reserved_from_sealed_omp_inputs(self):
        # The manifest private directory is the active OMP agent directory:
        # every sealed deployment input — present or absent — is reserved, so
        # evidence paths can never mutate a sealed configuration input.
        batch = _OmpBatch(self, inherited_equivalent=True, manifest_in_agent_dir=True)
        inputs = {
            reference["path"]: reference["state"]
            for reference in contracts._manifest_input_references(
                batch.manifest["payload"]
            )
        }
        absent_input = batch.agent / "settings.json"
        alternate_input = batch.agent / ".env"
        present_input = batch.agent / "config.yml"
        self.assertEqual(inputs[str(absent_input)], _ABSENT)
        self.assertEqual(inputs[str(alternate_input)], _ABSENT)
        self.assertEqual(inputs[str(present_input)]["type"], "file")
        output_path = batch.agent / "current-state-evidence.json"

        cases = {
            "output equals sealed absent input": (batch.missing_path, absent_input),
            "missing equals sealed absent input": (alternate_input, output_path),
            "output equals sealed present input": (
                batch.missing_path,
                present_input,
            ),
        }
        for name, (missing, output) in cases.items():
            with self.subTest(case=name):
                agent_before = _tree_bytes(batch.agent)
                with (
                    self.assertRaises(contracts.ContractError) as failure,
                    mock.patch.dict(os.environ, batch.environment),
                ):
                    reconcile_deployment(
                        batch.manifest_path,
                        batch.apply_path,
                        missing,
                        output,
                        confirmed=True,
                    )
                self.assertEqual(failure.exception.code, "private-scope")
                # Refusal precedes smoke and writes: the agent directory is
                # byte-identical and every reserved input keeps its state.
                self.assertEqual(_tree_bytes(batch.agent), agent_before)
                self.assertFalse(output_path.exists())
                self.assertFalse(absent_input.exists())
                self.assertFalse(alternate_input.exists())

    def test_apply_only_target_drift_fails_before_any_smoke(self):
        batch = _OmpBatch(self)
        operation = _apply_only_operation(batch.manifest)
        target = Path(operation["target"])
        after = _stage_results(batch.apply_path)[operation["resource_id"]]["after"]
        self.assertEqual(snapshot(target), after)
        _drift_target(target, after)
        drifted = snapshot(target)
        evidence_before = _tree_bytes(batch.evidence)
        output_path = batch.evidence / "current-state-evidence.json"

        with self.assertRaises(contracts.ContractError) as failure:
            _reconcile(batch, output_path)
        self.assertEqual(failure.exception.code, "state-conflict")
        self.assertFalse(output_path.exists())
        self.assertFalse(batch.missing_path.exists())
        self.assertEqual(_tree_bytes(batch.evidence), evidence_before)
        self.assertEqual(snapshot(target), drifted)


if __name__ == "__main__":
    unittest.main()
