from __future__ import annotations
# ruff: noqa: I001 -- local scripts require the explicit test path before import.

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard/scripts"
sys.path.insert(0, str(SCRIPTS))


from onboard_contracts import ContractError, canonical_json_bytes
from sbtd_graft_deployment import execute_migration_deployment, load_deployment_context
from sbtd_migration import apply_migration, runtime_versions
from sbtd_migration_files import save_document, snapshot
from sbtd_migration_plan import plan_migration, validate_legacy_inputs
from sbtd_migration_verify import verify_migration
from sbtd_recovery import apply_recovery, plan_recovery

from tests.test_sbtd_followup_batch import _graph_fixture, _synthetic_smoke
from tests.test_sbtd_migration_apply import file_contents, legacy_project
from tests.test_sbtd_migration_plan import _ownership_asset_context, _reader


class OmpDeploymentPlanTests(unittest.TestCase):
    def test_omp_migration_plan_binds_profile_sources_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = legacy_project(base, "project")
            home, vault = base / "home", base / "vault"
            agent = home / ".omp/profiles/work/agent"
            codex = home / ".codex"
            for path in (agent, codex, vault):
                path.mkdir(parents=True, mode=0o700)
            (agent / "config.yml").write_text(
                "enabledProviders: [codex]\n", encoding="utf-8"
            )
            (codex / "config.toml").write_text(
                '[mcp_servers.foreign]\ncommand = "/foreign/server"\n',
                encoding="utf-8",
            )
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "OMP_PROFILE": "work",
                "CODEX_HOME": str(home / "ignored-codex-home"),
                "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
            }
            before = file_contents(base)
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
                validate_legacy_inputs(manifest, _reader)
            self.assertEqual(file_contents(base), before)
            payload = manifest["payload"]
            self.assertEqual(payload["deployment"]["mode"], "init")
            self.assertEqual(payload["deployment"]["platform"], "omp")
            self.assertIn(
                str(codex / "config.toml"),
                {item["path"] for item in payload["deployment"]["inputs"]},
            )
            operations = [
                operation
                for operation in payload["shared_operations"]
                if operation["phase"] == "deploy"
            ]
            self.assertEqual(
                {
                    (operation["target"], operation["selector"])
                    for operation in operations
                    if operation["selector"] == "graft-omp-mcp"
                },
                {(str(agent / "mcp.json"), "graft-omp-mcp")},
            )
            self.assertFalse(
                any(
                    operation["selector"] in {"graft-mcp", "graft-hooks"}
                    for operation in operations
                )
            )

    def test_project_only_omp_plan_declares_no_global_config(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = legacy_project(base, "project")
            home, vault = base / "home", base / "vault"
            home.mkdir(mode=0o700)
            vault.mkdir(mode=0o700)
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(home / ".codex"),
                "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
            }
            before = file_contents(base)
            with mock.patch.dict(os.environ, environment):
                manifest = plan_migration(
                    [root],
                    vault,
                    "fixture",
                    None,
                    tool_versions=runtime_versions(),
                    deployment_mode="init-projects",
                    deployment_platform="omp",
                )
                validate_legacy_inputs(manifest, _reader)
            self.assertEqual(file_contents(base), before)
            payload = manifest["payload"]
            self.assertEqual(
                payload["deployment"],
                {"mode": "init-projects", "platform": "omp", "inputs": []},
            )
            self.assertFalse(
                any(
                    operation["phase"] == "deploy"
                    for operation in payload["shared_operations"]
                )
            )

    def test_inherited_source_drift_blocks_apply_before_any_write(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = legacy_project(base, "project")
            home, vault, evidence = (
                base / name for name in ("home", "vault", "evidence")
            )
            agent = home / ".omp/agent"
            codex = home / ".codex"
            for path in (agent, codex, vault, evidence):
                path.mkdir(parents=True, mode=0o700)
            (agent / "config.yml").write_text(
                "enabledProviders: [codex]\n", encoding="utf-8"
            )
            source = codex / "config.toml"
            source.write_text(
                '[mcp_servers.foreign]\ncommand = "/foreign/one"\n',
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
                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(manifest))
                source.write_text(
                    '[mcp_servers.foreign]\ncommand = "/foreign/two"\n',
                    encoding="utf-8",
                )
                before = file_contents(base)
                with self.assertRaises(ContractError):
                    apply_migration(manifest_path, confirmed=True)
            self.assertEqual(file_contents(base), before)

    def test_omp_render_uses_active_profile_sources_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = legacy_project(base, "project")
            agent = home / ".omp/profiles/work/agent"
            agent.mkdir(parents=True)
            target = agent / "mcp.json"
            binding = {
                "root": str(root),
                "node": "/fixture/node",
                "cli": "/fixture/graft/dist/cli.js",
                "python": "/fixture/python",
                "launcher": str(
                    Path(__file__).resolve().parents[1]
                    / "sbtd-workflow-onboard/scripts/sbtd_graft_entry.py"
                ),
            }
            operation = {
                "selector": "graft-omp-mcp",
                "target": str(target),
            }
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "OMP_PROFILE": "work",
                "CODEX_HOME": str(home / ".codex"),
            }
            before = file_contents(base)
            with mock.patch.dict(os.environ, environment):
                from sbtd_graft_deployment import render_configuration

                candidate = render_configuration(operation, b"", [binding])
            self.assertEqual(file_contents(base), before)
            servers = __import__("json").loads(candidate)["mcpServers"]
            self.assertEqual(len(servers), 1)
            server = next(iter(servers.values()))
            self.assertEqual(server["command"], binding["python"])
            self.assertNotIn("cwd", server)
            self.assertNotIn("--root", server["args"])
            self.assertEqual(server["env"], {"DO_NOT_TRACK": "1", "DNT": "1"})

    def test_omp_render_rejects_disabled_generated_extension_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = legacy_project(base, "project")
            agent = home / ".omp/agent"
            agent.mkdir(parents=True)
            target = agent / "mcp.json"
            binding = {
                "root": str(root),
                "node": "/fixture/node",
                "cli": "/fixture/graft/dist/cli.js",
                "python": "/fixture/python",
                "launcher": str(
                    Path(__file__).resolve().parents[1]
                    / "sbtd-workflow-onboard/scripts/sbtd_graft_entry.py"
                ),
            }
            name = "sbtd-graft"
            (agent / "config.yml").write_text(
                f"disabledExtensions: [mcp:{name}]\n", encoding="utf-8"
            )
            operation = {"selector": "graft-omp-mcp", "target": str(target)}
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(home / ".codex"),
            }
            with mock.patch.dict(os.environ, environment):
                from sbtd_graft_deployment import render_configuration

                with self.assertRaises(ContractError) as failure:
                    render_configuration(operation, b"", [binding])
            self.assertEqual(failure.exception.code, "ownership-conflict")
            self.assertFalse(target.exists())

    def test_inherited_equivalent_connection_leaves_absent_omp_config_unwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = legacy_project(base, "project")
            home = base / "home"
            agent = home / ".omp/agent"
            codex = home / ".codex"
            private = base / "private"
            for path in (agent, codex, private):
                path.mkdir(parents=True, mode=0o700)
            binding = {
                "root": str(root),
                "node": "/fixture/node",
                "cli": "/fixture/cli.js",
                "python": "/fixture/python",
                "launcher": str(
                    Path(__file__).resolve().parents[1]
                    / "sbtd-workflow-onboard/scripts/sbtd_graft_entry.py"
                ),
            }
            from sbtd_omp_wiring import desired_omp_server

            desired = desired_omp_server(binding)
            (agent / "config.yml").write_text(
                "enabledProviders: [codex]\n", encoding="utf-8"
            )
            (codex / "config.toml").write_text(
                "[mcp_servers.sbtd-graft]\n"
                f'command = "{desired["command"]}"\n'
                "args = "
                + json.dumps(desired["args"])
                + "\n"
                '[mcp_servers.sbtd-graft.env]\nDO_NOT_TRACK = "1"\nDNT = "1"\n',
                encoding="utf-8",
            )
            target = agent / "mcp.json"
            policy = (
                Path(__file__).resolve().parents[1]
                / "sbtd-workflow-onboard/assets/graft-build-policy.json"
            )
            operation = {
                "phase": "deploy",
                "resource_id": "fixture-resource",
                "operation_id": "fixture-operation",
                "selector": "graft-omp-mcp",
                "target": str(target),
                "change": {
                    "kind": "configure-graft",
                    "source_ref": {
                        "path": str(policy),
                        "state": {
                            "type": "file",
                            "checksum": __import__(
                                "onboard_contracts"
                            ).GRAFT_BUILD_POLICY_SHA256,
                        },
                    },
                },
                "dependent_projects": [str(root)],
            }
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(codex),
            }
            with mock.patch.dict(os.environ, environment):
                from sbtd_graft_deployment import execute_resource

                result = execute_resource(
                    operation,
                    expected={"type": "absent", "checksum": None},
                    root=agent,
                    private_root=private,
                    backup_path=private / "backup",
                    bindings=[binding],
                    runtime={},
                    launcher_state=snapshot(
                        Path(__file__).resolve().parents[1]
                        / "sbtd-workflow-onboard"
                    ),
                )
            self.assertEqual(result["status"], "succeeded", result)
            self.assertEqual(result["after"], {"type": "absent", "checksum": None})
            self.assertFalse(target.exists())


    def test_full_omp_deployment_writes_active_mcp_and_no_host_hooks(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = legacy_project(base, "project")
            home, vault, evidence = (
                base / name for name in ("home", "vault", "evidence")
            )
            for path in (home, vault, evidence):
                path.mkdir(mode=0o700)
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(home / ".codex"),
                "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
                "GIT_CONFIG_NOSYSTEM": "1",
            }
            for command in (
                ["git", "init", "-b", "main", str(root)],
                ["git", "-C", str(root), "config", "user.email", "fixture@test"],
                ["git", "-C", str(root), "config", "user.name", "fixture"],
                ["git", "-C", str(root), "add", "-A"],
                ["git", "-C", str(root), "commit", "-m", "legacy state"],
            ):
                subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    env={**os.environ, **environment},
                )
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
                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(manifest))
                applied, code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
                self.assertEqual(code, 0, applied)
                receipt = applied["migration"]["apply_receipt"]
                output = evidence / "deployment.json"
                context = load_deployment_context(
                    manifest_path,
                    evidence / ("apply-" + receipt["apply_id"] + ".json"),
                    output,
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

                def graph(project, _runtime):
                    (project / "graft").mkdir()
                    (project / "graft/fixture").write_bytes(b"synthetic native output")

                def smoke(project, smoke_runtime, evidence_dir):
                    source_ref, head = manifest["payload"]["projects"][0][
                        "source_ref"
                    ], manifest["payload"]["projects"][0]["head"]
                    moment = datetime.now(timezone.utc).isoformat()
                    report = evidence_dir / "api-report-omp-smoke.json"
                    summary = evidence_dir / "api-report-omp-smoke.md"
                    envelope_path = evidence_dir / "api-report-omp-smoke.evidence.json"
                    raw = {
                        "repositoryKey": hashlib.sha256(
                            str(project).encode()
                        ).hexdigest(),
                        "projectRoot": str(project),
                        "sourceRef": source_ref,
                        "sourceCommit": head,
                        "worktreeState": "dirty",
                        "sourceRevision": "dirty",
                        "evidenceSource": "developer-local",
                        "trigger": "manual",
                        "environmentAlignment": "verified",
                        "evidencePublication": "local-only",
                        "e2eMode": "smoke-only",
                        "mockStrategy": "none",
                        "startedAt": moment,
                        "finishedAt": moment,
                        "command": [
                            smoke_runtime["node"],
                            smoke_runtime["cli"],
                            "check",
                            ".",
                            "--json",
                        ],
                        "stdout": "synthetic native output",
                        "stderr": "",
                        "exitCode": 0,
                        "processExitCode": 0,
                        "timedOut": False,
                    }
                    report.write_text(json.dumps(raw), encoding="utf-8")
                    summary.write_text("合成 smoke 摘要。\n", encoding="utf-8")
                    envelope = {
                        "schemaVersion": 1,
                        "runId": "omp-smoke",
                        "createdAt": moment,
                        "evidenceSource": "developer-local",
                        "trigger": "manual",
                        "repository": {
                            "repositoryKey": raw["repositoryKey"],
                            "sourceRef": source_ref,
                            "sourceCommit": head,
                            "worktreeState": "dirty",
                        },
                        "sourceRevision": "dirty",
                        "environmentAlignment": "verified",
                        "e2eMode": "smoke-only",
                        "mockStrategy": "none",
                        "featureSources": [],
                        "reports": [
                            {
                                "testType": "api",
                                "path": str(report),
                                "summaryMd": str(summary),
                                "sha256": hashlib.sha256(
                                    report.read_bytes()
                                ).hexdigest(),
                                "status": "passed",
                                "mode": "smoke-only",
                            }
                        ],
                        "evidencePublication": "local-only",
                        "secretsRedacted": True,
                    }
                    envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
                    return [
                        {"path": str(path), "state": snapshot(path)}
                        for path in (report, envelope_path, summary)
                    ]

                with (
                    mock.patch(
                        "sbtd_graft_deployment.verified_runtime", return_value=runtime
                    ),
                    mock.patch(
                        "sbtd_graft_deployment.build_project_graph", side_effect=graph
                    ),
                    mock.patch(
                        "sbtd_graft_deployment.run_project_smoke", side_effect=smoke
                    ),
                ):
                    result, code = execute_migration_deployment(context)
                self.assertEqual(code, 0, result)
                self.assertEqual(result["status"], "succeeded")
                target = home / ".omp/agent/mcp.json"
                servers = json.loads(target.read_text(encoding="utf-8"))["mcpServers"]
                self.assertEqual(len(servers), 1)
                server = next(iter(servers.values()))
                self.assertEqual(server["command"], runtime["python"])
                self.assertEqual(
                    server["args"][2],
                    str(
                        home
                        / ".agent/skills/sbtd-workflow-onboard/scripts/sbtd_graft_entry.py"
                    ),
                )
                self.assertNotIn("cwd", server)
                self.assertNotIn("--root", server["args"])
                self.assertFalse((home / ".codex/hooks.json").exists())
                self.assertFalse((home / ".codex/config.toml").exists())
                saved = result["deploymentEvidence"]["evidence"]["payload"]
                self.assertEqual(saved["status"], "succeeded")
                self.assertTrue(output.is_file())


def _legacy_project_with_host_configs(base):
    """Legacy project carrying ownership-pinned generated host configs.

    Mirrors the production batch whose approved manifest removes the
    project's recorded ``.codex/config.toml`` and ``.claude/settings.json``
    during apply; both paths are sealed OMP deployment inputs.
    """
    root = legacy_project(base, "project")
    host_configs = {
        ".codex/config.toml": b'model = "recorded"\n',
        ".claude/settings.json": b'{"legacyRouting": true}\n',
    }
    (root / ".claude").mkdir()
    owned = {
        ".codex/agents/trellis-implement.toml": (
            root / ".codex/agents/trellis-implement.toml"
        ).read_bytes(),
        **host_configs,
    }
    for relative, raw in host_configs.items():
        (root / relative).write_bytes(raw)
    (root / ".trellis/.template-hashes.json").write_text(
        json.dumps(
            {
                "__version": 2,
                "hashes": {
                    name: hashlib.sha256(raw).hexdigest()
                    for name, raw in owned.items()
                },
            }
        )
    )
    return root, host_configs


def _proven_input_environment(home, host_configs, base):
    environment = {
        "HOME": str(home),
        "USERPROFILE": str(home),
        "CODEX_HOME": str(home / ".codex"),
        "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
    }
    asset = _ownership_asset_context(
        base,
        None,
        config_pins={
            relative: [hashlib.sha256(raw).hexdigest()]
            for relative, raw in host_configs.items()
        },
    )
    return environment, asset


class OmpDeploymentProvenInputTests(unittest.TestCase):
    """Bound-stage-proof recognition for sealed OMP configuration inputs.

    An approved apply removal changes a sealed deployment input between
    planning and deployment; revalidation must recognize exactly that
    proven change while every unapproved, unbound or mutated state keeps
    the drift rejection before any write.
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

    def _plan_and_apply(self, root, vault, evidence, asset, environment):
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
        apply_path = evidence / ("apply-" + receipt["apply_id"] + ".json")
        return manifest, manifest_path, apply_path, receipt

    def _deploy_context(self, manifest_path, apply_path, output, root):
        return load_deployment_context(
            manifest_path,
            apply_path,
            output,
            previous_path=None,
            mode="init",
            roots=[root],
            hooks_authorized=False,
        )

    def test_apply_proven_host_config_removal_deploys_and_verifies(self):
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
                sealed = {
                    item["path"]: item["state"]
                    for item in manifest["payload"]["deployment"]["inputs"]
                }
                for relative in host_configs:
                    self.assertEqual(sealed[str(root / relative)]["type"], "file")
                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(manifest))
                applied, code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
                self.assertEqual(code, 0, applied)
                for relative in host_configs:
                    self.assertFalse((root / relative).exists())
                receipt = applied["migration"]["apply_receipt"]
                operations = {
                    operation["resource_id"]: operation
                    for operation in manifest["payload"]["projects"][0][
                        "private_operations"
                    ]
                }
                proven_targets = {str(root / relative) for relative in host_configs}
                proven = [
                    result
                    for result in receipt["payload"]["projects"][0][
                        "private_results"
                    ]
                    if operations[result["resource_id"]]["target"] in proven_targets
                ]
                self.assertEqual(len(proven), len(host_configs))
                for result in proven:
                    self.assertEqual(result["status"], "succeeded")
                    self.assertEqual(
                        result["after"], {"type": "absent", "checksum": None}
                    )
                    self.assertTrue(Path(result["backup_ref"]["path"]).is_file())
                apply_path = evidence / ("apply-" + receipt["apply_id"] + ".json")

                # A bound retry receipt preserves the proven removals and
                # must pass the same revalidation.
                retried, retry_code = apply_migration(
                    manifest_path,
                    previous_receipt_path=apply_path,
                    confirmed=True,
                    no_routing_approvals=True,
                )
                self.assertEqual(retry_code, 0, retried)
                self.assertEqual(retried["status"], "already-complete")

                context = self._deploy_context(
                    manifest_path, apply_path, evidence / "deployment.json", root
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
                    result, code = execute_migration_deployment(context)
                self.assertEqual(code, 0, result)
                self.assertEqual(result["status"], "succeeded")
                verified, verify_code = verify_migration(
                    manifest_path, apply_path, evidence / "deployment.json"
                )
                self.assertEqual(verify_code, 0, verified)

    def test_unproven_input_removal_refuses_deploy_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = legacy_project(base, "project")
            home, vault, evidence = (
                base / name for name in ("home", "vault", "evidence")
            )
            agent = home / ".omp/agent"
            codex = home / ".codex"
            for path in (agent, codex, vault, evidence):
                path.mkdir(parents=True, mode=0o700)
            (agent / "config.yml").write_text(
                "enabledProviders: [codex]\n", encoding="utf-8"
            )
            source = codex / "config.toml"
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
                self.assertIn(
                    str(source),
                    {
                        item["path"]
                        for item in manifest["payload"]["deployment"]["inputs"]
                    },
                )
                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(manifest))
                applied, code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
                self.assertEqual(code, 0, applied)
                receipt = applied["migration"]["apply_receipt"]
                # Nobody approved or recorded touching this sealed input.
                source.unlink()
                with self.assertRaises(ContractError) as drift:
                    self._deploy_context(
                        manifest_path,
                        evidence / ("apply-" + receipt["apply_id"] + ".json"),
                        evidence / "deployment.json",
                        root,
                    )
            self.assertEqual(drift.exception.code, "state-conflict")
            self.assertIn("drifted", str(drift.exception))
            self.assertFalse((evidence / "deployment.json").exists())
            self.assertFalse((agent / "mcp.json").exists())

    def test_mutated_proven_input_refuses_deploy_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root, host_configs = _legacy_project_with_host_configs(base)
            home, vault, evidence = (
                base / name for name in ("home", "vault", "evidence")
            )
            for path in (home, vault, evidence):
                path.mkdir(mode=0o700)
            environment, asset = _proven_input_environment(home, host_configs, base)
            _manifest, manifest_path, apply_path, _receipt = self._plan_and_apply(
                root, vault, evidence, asset, environment
            )
            with mock.patch.dict(os.environ, environment), asset:
                # The proven outcome is absent; unapproved new bytes are
                # refused by the original-reference and input closures.
                (root / ".codex/config.toml").write_bytes(b'model = "unapproved"\n')
                with self.assertRaises(ContractError) as drift:
                    self._deploy_context(
                        manifest_path, apply_path, evidence / "deployment.json", root
                    )
            self.assertEqual(drift.exception.code, "state-conflict")
            self.assertFalse((evidence / "deployment.json").exists())
            self.assertFalse((home / ".omp/agent/mcp.json").exists())

    def test_mutated_retained_original_refuses_deploy_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root, host_configs = _legacy_project_with_host_configs(base)
            home, vault, evidence = (
                base / name for name in ("home", "vault", "evidence")
            )
            for path in (home, vault, evidence):
                path.mkdir(mode=0o700)
            environment, asset = _proven_input_environment(home, host_configs, base)
            manifest, manifest_path, apply_path, receipt = self._plan_and_apply(
                root, vault, evidence, asset, environment
            )
            operations = {
                operation["resource_id"]: operation
                for operation in manifest["payload"]["projects"][0][
                    "private_operations"
                ]
            }
            removal = next(
                result
                for result in receipt["payload"]["projects"][0]["private_results"]
                if operations[result["resource_id"]]["target"]
                == str(root / ".codex/config.toml")
            )
            with mock.patch.dict(os.environ, environment), asset:
                # A proven change requires its intact retained original.
                Path(removal["backup_ref"]["path"]).write_bytes(b"mutated\n")
                with self.assertRaises(ContractError) as drift:
                    self._deploy_context(
                        manifest_path, apply_path, evidence / "deployment.json", root
                    )
            self.assertEqual(drift.exception.code, "state-conflict")
            self.assertFalse((evidence / "deployment.json").exists())
            self.assertFalse((home / ".omp/agent/mcp.json").exists())

    def test_recovery_restores_proven_removed_host_configs(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root, host_configs = _legacy_project_with_host_configs(base)
            home, vault, evidence = (
                base / name for name in ("home", "vault", "evidence")
            )
            for path in (home, vault, evidence):
                path.mkdir(mode=0o700)
            environment, asset = _proven_input_environment(home, host_configs, base)
            _manifest, manifest_path, apply_path, _receipt = self._plan_and_apply(
                root, vault, evidence, asset, environment
            )
            with mock.patch.dict(os.environ, environment), asset:
                planned, plan_code = plan_recovery(
                    manifest_path, apply_receipt_path=apply_path
                )
                self.assertEqual(plan_code, 0, planned)
                plan = planned["recovery"]["plan"]
                plan_path = evidence / "recovery-plan.json"
                save_document(plan_path, plan, private_root=evidence)
                restored, recovery_code = apply_recovery(
                    plan_path, confirm_recovery=plan["plan_id"]
                )
                self.assertEqual(recovery_code, 0, restored)
                for relative, raw in host_configs.items():
                    self.assertEqual((root / relative).read_bytes(), raw)

if __name__ == "__main__":
    unittest.main()
