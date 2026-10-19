from __future__ import annotations
# ruff: noqa: I001 -- local scripts require the explicit test path before import.

import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard/scripts"
sys.path.insert(0, str(SCRIPTS))

from onboard_contracts import ContractError, operation_id, resource_id, seal_document
from sbtd_migration_plan import plan_migration, validate_legacy_inputs

from tests.test_sbtd_migration_apply import file_contents, legacy_project
from tests.test_sbtd_migration_plan import _reader


class CodexDeploymentPlanTests(unittest.TestCase):
    def test_project_only_deploy_resources_are_frozen_before_apply(self):
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
                    tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                    deployment_mode="init-projects",
                )
                validate_legacy_inputs(manifest, _reader)
                self.assertEqual(file_contents(base), before)
                payload = manifest["payload"]
                self.assertEqual(
                    payload["deployment"],
                    {"mode": "init-projects", "platform": "codex", "inputs": []},
                )
                operations = payload["projects"][0]["private_operations"]
                self.assertEqual(
                    {
                        operation["target"]
                        for operation in operations
                        if operation["phase"] == "deploy"
                    },
                    {str(root / "AGENTS.md"), str(root / "graft")},
                )
                self.assertEqual(payload["shared_operations"], [])
                broken = copy.deepcopy(payload)
                broken["projects"][0]["private_operations"] = [
                    operation
                    for operation in broken["projects"][0]["private_operations"]
                    if operation["change"]["kind"] != "build-graft"
                ]
                with self.assertRaises(ContractError):
                    validate_legacy_inputs(seal_document("manifest", broken), _reader)
                self.assertEqual(file_contents(base), before)

    def test_resealed_shared_host_root_cannot_replace_the_active_codex_home(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = legacy_project(base, "project")
            home, vault = base / "home", base / "vault"
            home.mkdir(mode=0o700)
            vault.mkdir(mode=0o700)
            active = home / "active-codex"
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(active),
                "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
            }
            with mock.patch.dict(os.environ, environment):
                manifest = plan_migration(
                    [root],
                    vault,
                    "fixture",
                    None,
                    tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                    deployment_mode="init",
                )
                validate_legacy_inputs(manifest, _reader)
                payload = copy.deepcopy(manifest["payload"])
                forged = base / "unselected-host"
                for shared_root in payload["shared_roots"]:
                    if shared_root["kind"] == "codex-home":
                        shared_root["path"] = str(forged)
                for operation in payload["shared_operations"]:
                    if operation["selector"] == "graft-mcp":
                        operation["target"] = str(forged / "config.toml")
                        operation["resource_id"] = resource_id(
                            "toml", operation["target"]
                        )
                        operation["operation_id"] = operation_id(
                            "deploy", operation["resource_id"], "graft-mcp"
                        )
                payload["projects"][0]["shared_operation_ids"] = sorted(
                    operation["operation_id"]
                    for operation in payload["shared_operations"]
                )
                before = file_contents(base)
                with self.assertRaises(ContractError):
                    validate_legacy_inputs(seal_document("manifest", payload), _reader)
                mismatched = copy.deepcopy(manifest["payload"])
                mismatched["deployment"]["platform"] = "omp"
                with self.assertRaises(ContractError):
                    validate_legacy_inputs(
                        seal_document("manifest", mismatched), _reader
                    )
                self.assertEqual(file_contents(base), before)

    def test_codex_manifest_rejects_an_omp_deploy_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = legacy_project(base, "project")
            home, vault = base / "home", base / "vault"
            home.mkdir(mode=0o700)
            vault.mkdir(mode=0o700)
            active = home / "active-codex"
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(active),
                "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
            }
            with mock.patch.dict(os.environ, environment):
                manifest = plan_migration(
                    [root],
                    vault,
                    "fixture",
                    None,
                    tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                    deployment_mode="init",
                )
                payload = copy.deepcopy(manifest["payload"])
                policy = next(
                    operation["change"]["source_ref"]
                    for operation in payload["shared_operations"]
                    if operation["selector"] == "graft-mcp"
                )
                target = str(home / ".omp/agent/mcp.json")
                resource = resource_id("json", target)
                operation = {
                    "phase": "deploy",
                    "resource_id": resource,
                    "operation_id": operation_id("deploy", resource, "graft-omp-mcp"),
                    "owner_kind": "json",
                    "target": target,
                    "selector": "graft-omp-mcp",
                    "change": {"kind": "configure-graft", "source_ref": policy},
                    "ownership": {"kind": "template-source", "reference": policy},
                    "before_requirement": {
                        "kind": "state",
                        "state": {"type": "absent", "checksum": None},
                    },
                    "dependent_projects": [str(root)],
                }
                payload["shared_roots"].append(
                    {
                        "kind": "omp-home",
                        "path": str(home / ".omp"),
                        "dependent_projects": [str(root)],
                    }
                )
                payload["shared_operations"].append(operation)
                payload["projects"][0]["shared_operation_ids"].append(
                    operation["operation_id"]
                )
                before = file_contents(base)
                with self.assertRaises(ContractError):
                    validate_legacy_inputs(seal_document("manifest", payload), _reader)
                self.assertEqual(file_contents(base), before)


if __name__ == "__main__":
    unittest.main()
