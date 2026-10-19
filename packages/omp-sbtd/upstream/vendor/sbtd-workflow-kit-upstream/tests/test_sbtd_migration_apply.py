from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard/scripts"
sys.path.insert(0, str(SCRIPTS))

import sbtd_migration_plan
from onboard_contracts import ContractError, canonical_json_bytes
from sbtd_migration import apply_migration, runtime_versions
from sbtd_migration_plan import plan_migration


def legacy_project(base: Path, name: str) -> Path:
    root = base / name
    (root / ".trellis/workspace/dev01").mkdir(parents=True)
    (root / ".codex/agents").mkdir(parents=True)
    (root / ".trellis/.developer").write_bytes(
        b"name=dev01\ninitialized_at=2026-09-01T12:00:00\n"
    )
    (root / ".trellis/.version").write_text("0.6.17\n")
    (root / ".trellis/workspace/dev01/journal-1.md").write_text(
        "Synthetic private legacy journal.\n"
    )
    (root / ".trellis/workspace/dev01/untracked.bin").write_bytes(
        b"\x00retained-private-fixture\xff"
    )
    (root / ".gitignore").write_text(".trellis/\n.gitnexus/\n")
    (root / "AGENTS.md").write_bytes(
        b"Foreign project rule.\n<!-- TRELLIS:START -->\nLegacy route.\n<!-- TRELLIS:END -->\n"
    )
    owned = {
        ".codex/agents/trellis-implement.toml": b'name = "trellis-implement"\n',
    }
    for relative_name, raw in owned.items():
        (root / relative_name).write_bytes(raw)
    (root / ".trellis/.template-hashes.json").write_text(
        json.dumps(
            {
                "__version": 2,
                "hashes": {
                    name: hashlib.sha256(raw).hexdigest() for name, raw in owned.items()
                },
            }
        )
    )
    return root


def file_contents(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


class MigrationApplyTests(unittest.TestCase):
    def test_resource_preservation_failure_keeps_exit_three(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = legacy_project(base, "project")
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
            }
            with mock.patch.dict(os.environ, environment):
                manifest = plan_migration(
                    [project], vault, "fixture", None, tool_versions=runtime_versions()
                )
                path = evidence / "manifest.json"
                path.write_bytes(canonical_json_bytes(manifest))
                before = (project / ".gitignore").read_bytes()
                with mock.patch(
                    "sbtd_migration.write_file",
                    side_effect=ContractError(
                        "checksum-mismatch", "synthetic readback failure", exit_code=3
                    ),
                ):
                    response, code = apply_migration(
                        path, confirmed=True, no_routing_approvals=True
                    )
            self.assertEqual(code, 3, response)
            self.assertEqual(response["status"], "failed")
            self.assertEqual((project / ".gitignore").read_bytes(), before)

    def test_batch_preflight_rejects_drift_before_any_project_write(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            roots = [legacy_project(base, name) for name in ("alpha", "beta")]
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
            }
            with mock.patch.dict(os.environ, environment):
                manifest = plan_migration(
                    roots, vault, "fixture", None, tool_versions=runtime_versions()
                )
                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(manifest))
                (roots[1] / "AGENTS.md").write_bytes(b"user changed the second project")
                before = file_contents(base)
                with self.assertRaises(ContractError):
                    apply_migration(manifest_path, confirmed=True)
                self.assertEqual(file_contents(base), before)
                self.assertEqual(list(vault.iterdir()), [])
                self.assertFalse((roots[0] / ".sbtd").exists())

    def test_partial_batch_retains_success_and_retries_only_unfinished_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            roots = [legacy_project(base, name) for name in ("alpha", "beta")]
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
            }
            with mock.patch.dict(os.environ, environment):
                manifest = plan_migration(
                    roots, vault, "fixture", None, tool_versions=runtime_versions()
                )
                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(manifest))
                link = os.link

                def fail_second_identity(source, destination, *args, **kwargs):
                    if Path(destination) == roots[1] / ".sbtd/developer":
                        raise OSError("synthetic second-project write failure")
                    return link(source, destination, *args, **kwargs)

                with mock.patch(
                    "sbtd_migration_files.os.link", side_effect=fail_second_identity
                ):
                    failed, code = apply_migration(
                        manifest_path, confirmed=True, no_routing_approvals=True
                    )
                self.assertEqual(code, 5, failed)
                receipt = failed["migration"]["apply_receipt"]
                statuses = {
                    project["root"]: project["status"]
                    for project in receipt["payload"]["projects"]
                }
                self.assertEqual(
                    statuses, {str(roots[0]): "applied", str(roots[1]): "failed"}
                )
                self.assertEqual(
                    (roots[0] / ".sbtd/developer").read_bytes(), b"name=dev01\n"
                )
                self.assertFalse((roots[1] / ".sbtd/developer").exists())
                saved = next(
                    path
                    for path in evidence.glob("*.json")
                    if json.loads(path.read_text()).get("apply_id")
                    == receipt["apply_id"]
                )
                first_tree = file_contents(roots[0])
                first_results = receipt["payload"]["projects"][0]["private_results"]
                retried, retry_code = apply_migration(
                    manifest_path,
                    previous_receipt_path=saved,
                    confirmed=True,
                    no_routing_approvals=True,
                )
                self.assertEqual(retry_code, 0, retried)
                final = retried["migration"]["apply_receipt"]
                self.assertEqual(
                    final["payload"]["previous_receipt_id"], receipt["apply_id"]
                )
                self.assertEqual(file_contents(roots[0]), first_tree)
                self.assertEqual(
                    final["payload"]["projects"][0]["private_results"], first_results
                )
                self.assertEqual(
                    (roots[1] / ".sbtd/developer").read_bytes(), b"name=dev01\n"
                )

    def test_unapproved_global_pause_is_refused_before_write(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = legacy_project(base, "project")
            omp_agent = root / ".omp/agents/trellis-implement.md"
            omp_agent.parent.mkdir(parents=True)
            omp_agent.write_bytes(b"# Legacy OMP agent\n")
            metadata_path = root / ".trellis/.template-hashes.json"
            metadata = json.loads(metadata_path.read_text())
            metadata["hashes"][".omp/agents/trellis-implement.md"] = hashlib.sha256(
                omp_agent.read_bytes()
            ).hexdigest()
            metadata_path.write_text(json.dumps(metadata))
            home, vault, evidence = (
                base / name for name in ("home", "vault", "evidence")
            )
            for path in (home, vault, evidence):
                path.mkdir(mode=0o700)
            router = home / ".omp/agent/AGENTS.md"
            router.parent.mkdir(parents=True)
            legacy_global = (
                b"# Legacy global routing\nUse trellis-workflow for every task.\n"
            )
            router.write_bytes(legacy_global)
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(home / ".codex"),
                "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
            }
            fixture_pins = sbtd_migration_plan._ownership_pins()
            fixture_pins["agents"] = hashlib.sha256(legacy_global).hexdigest()
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch.object(
                    sbtd_migration_plan, "_ownership_pins", return_value=fixture_pins
                ),
            ):
                before_plan = file_contents(base)
                manifest = plan_migration(
                    [root], vault, "fixture", None, tool_versions=runtime_versions()
                )
                self.assertEqual(file_contents(base), before_plan)
                shared = manifest["payload"]["shared_operations"]
                self.assertEqual(
                    [operation["target"] for operation in shared], [str(router)]
                )
                self.assertEqual(
                    manifest["payload"]["shared_roots"],
                    [
                        {
                            "kind": "omp-home",
                            "path": str(home / ".omp"),
                            "dependent_projects": [str(root)],
                        }
                    ],
                )
                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(manifest))
                with (
                    mock.patch(
                        "sbtd_migration._render_resource",
                        side_effect=AssertionError("render"),
                    ),
                    self.assertRaises(ContractError) as error,
                ):
                    apply_migration(
                        manifest_path, confirmed=True, no_routing_approvals=True
                    )
                self.assertEqual(error.exception.code, "approval-conflict")
                self.assertEqual(router.read_bytes(), legacy_global)

    def test_private_failure_saves_retryable_partial_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            roots = [legacy_project(base, name) for name in ("alpha", "beta")]
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
            }
            with mock.patch.dict(os.environ, environment):
                manifest = plan_migration(
                    roots, vault, "fixture", None, tool_versions=runtime_versions()
                )
                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(manifest))
                link = os.link

                def fail_beta_identity(source, destination, *args, **kwargs):
                    if Path(destination) == roots[1] / ".sbtd/developer":
                        raise OSError(
                            "synthetic private write failure before the shared pause"
                        )
                    return link(source, destination, *args, **kwargs)

                with mock.patch(
                    "sbtd_migration_files.os.link", side_effect=fail_beta_identity
                ):
                    failed, code = apply_migration(
                        manifest_path, confirmed=True, no_routing_approvals=True
                    )
                self.assertEqual(code, 5, failed)
                receipt = failed["migration"]["apply_receipt"]
                statuses = {
                    project["root"]: project["status"]
                    for project in receipt["payload"]["projects"]
                }
                self.assertEqual(
                    statuses, {str(roots[0]): "applied", str(roots[1]): "failed"}
                )
                self.assertEqual(receipt["payload"]["shared_results"], [])
                for project in receipt["payload"]["projects"]:
                    self.assertEqual(project["shared_operation_ids"], [])

                self.assertEqual(
                    (roots[0] / ".sbtd/developer").read_bytes(), b"name=dev01\n"
                )
                self.assertFalse(
                    (roots[1] / ".codex/agents/trellis-implement.toml").exists()
                )
                self.assertFalse((roots[1] / ".sbtd/developer").exists())
                saved = next(
                    path
                    for path in evidence.glob("*.json")
                    if json.loads(path.read_text()).get("apply_id")
                    == receipt["apply_id"]
                )
                self.assertEqual(json.loads(saved.read_text()), receipt)
                first_tree = file_contents(roots[0])
                first_results = receipt["payload"]["projects"][0]["private_results"]
                retried, retry_code = apply_migration(
                    manifest_path,
                    previous_receipt_path=saved,
                    confirmed=True,
                    no_routing_approvals=True,
                )
                self.assertEqual(retry_code, 0, retried)
                self.assertEqual(retried["status"], "applied")
                final = retried["migration"]["apply_receipt"]
                self.assertEqual(
                    final["payload"]["previous_receipt_id"], receipt["apply_id"]
                )
                self.assertEqual(file_contents(roots[0]), first_tree)
                self.assertEqual(
                    final["payload"]["projects"][0]["private_results"], first_results
                )
                self.assertEqual(
                    {
                        project["root"]: project["status"]
                        for project in final["payload"]["projects"]
                    },
                    {
                        str(roots[0]): "already-complete",
                        str(roots[1]): "applied",
                    },
                )
                self.assertEqual(
                    (roots[1] / ".sbtd/developer").read_bytes(), b"name=dev01\n"
                )

    def test_first_apply_preserves_originals_and_retry_uses_the_saved_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = legacy_project(base, "project")
            home = base / "home"
            home.mkdir(mode=0o700)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            evidence = base / "evidence"
            evidence.mkdir(mode=0o700)
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(home / ".codex"),
                "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
            }
            old_tree = file_contents(root / ".trellis")
            with mock.patch.dict(os.environ, environment):
                manifest = plan_migration(
                    [root],
                    vault,
                    "fixture-custodian",
                    None,
                    tool_versions=runtime_versions(),
                )
                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(manifest))
                applied, code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
                self.assertEqual(code, 0, applied)
                self.assertEqual(applied["status"], "applied")
                self.assertEqual(
                    (root / ".sbtd/developer").read_bytes(), b"name=dev01\n"
                )
                self.assertEqual(file_contents(root / ".trellis"), old_tree)
                agents = (root / "AGENTS.md").read_text()
                self.assertIn("Foreign project rule.", agents)
                self.assertIn("Legacy route.", agents)
                self.assertTrue(
                    any(
                        path.read_bytes() == b"\x00retained-private-fixture\xff"
                        for path in vault.rglob("untracked.bin")
                    )
                )
                receipt = applied["migration"]["apply_receipt"]
                saved = [
                    path
                    for path in evidence.glob("*.json")
                    if json.loads(path.read_text()).get("apply_id")
                    == receipt["apply_id"]
                ]
                self.assertEqual(len(saved), 1)
                self.assertEqual(json.loads(saved[0].read_text()), receipt)
                before_retry = file_contents(root)
                retried, retry_code = apply_migration(
                    manifest_path,
                    previous_receipt_path=saved[0],
                    confirmed=True,
                    no_routing_approvals=True,
                )
                self.assertEqual(retry_code, 0, retried)
                self.assertEqual(retried["status"], "already-complete")
                self.assertEqual(file_contents(root), before_retry)
            self.assertEqual(list(home.iterdir()), [])

    def test_retry_preserves_original_unavailable_exit_code(self):
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
            }
            with mock.patch.dict(os.environ, environment):
                manifest = plan_migration(
                    [root], vault, "fixture", None, tool_versions=runtime_versions()
                )
                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(manifest))
                first, first_code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
                self.assertEqual(first_code, 0, first)
                receipt_path = next(
                    path
                    for path in evidence.glob("apply-*.json")
                    if json.loads(path.read_text()).get("apply_id")
                    == first["migration"]["apply_receipt"]["apply_id"]
                )
                backup = next(vault.rglob("journal-1.md"))
                backup.unlink()
                retried, code = apply_migration(
                    manifest_path,
                    previous_receipt_path=receipt_path,
                    confirmed=True,
                    no_routing_approvals=True,
                )
            self.assertEqual(code, 3, retried)
            self.assertEqual(retried["status"], "failed")

    def test_unlisted_successor_is_rejected_even_with_a_matching_receipt(self):
        from onboard_contracts import ContractError
        from sbtd_migration import _require_runtime_lineage, _verified_runtime_pair
        from sbtd_migration_files import snapshot

        predecessor, _successor = _verified_runtime_pair()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            target = base / "live.txt"
            target.write_bytes(b"after\n")
            backup = base / "backup.txt"
            backup.write_bytes(b"before\n")
            manifest = {
                "manifest_id": "m1",
                "payload": {
                    "tool_versions": {"onboard": predecessor, "graft": "0.18.0"},
                    "projects": [
                        {
                            "private_operations": [
                                {
                                    "phase": "apply",
                                    "resource_id": "r1",
                                    "target": str(target),
                                }
                            ]
                        }
                    ],
                    "shared_operations": [],
                },
            }
            receipt = {
                "apply_id": "a1",
                "payload": {
                    "manifest_id": "m1",
                    "status": "applied",
                    "projects": [
                        {
                            "private_results": [
                                {
                                    "resource_id": "r1",
                                    "status": "succeeded",
                                    "after": snapshot(target),
                                    "backup_ref": {
                                        "path": str(backup),
                                        "state": snapshot(backup),
                                    },
                                }
                            ]
                        }
                    ],
                    "shared_results": [],
                },
            }
            with self.assertRaises(ContractError) as unlisted:
                _require_runtime_lineage(
                    manifest,
                    receipt,
                    manifest["payload"]["tool_versions"],
                    {
                        "onboard": "runtime-sha256:unlisted-successor",
                        "graft": "0.18.0",
                    },
                )
            self.assertEqual(unlisted.exception.code, "version-conflict")
            self.assertEqual(target.read_bytes(), b"after\n")

    def test_runtime_lineage_stays_closed_without_complete_evidence(self):
        from onboard_contracts import ContractError
        from sbtd_migration import _require_runtime_lineage
        from sbtd_migration_files import snapshot

        predecessor = (
            "runtime-sha256:27e74bf511e8b62ad6dac07188933811bd429a84b38b8f01ae025e997fdd7750"
        )
        current = {"onboard": "runtime-sha256:successor", "graft": "0.18.0"}
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            target = base / "live.txt"
            target.write_bytes(b"after\n")
            backup = base / "backup.txt"
            backup.write_bytes(b"before\n")
            after = snapshot(target)
            before = snapshot(backup)
            manifest = {
                "manifest_id": "m1",
                "payload": {
                    "tool_versions": {"onboard": predecessor, "graft": "0.18.0"},
                    "projects": [
                        {
                            "private_operations": [
                                {
                                    "phase": "apply",
                                    "resource_id": "r1",
                                    "target": str(target),
                                }
                            ]
                        }
                    ],
                    "shared_operations": [],
                },
            }
            receipt = {
                "apply_id": "a1",
                "payload": {
                    "manifest_id": "m1",
                    "status": "applied",
                    "projects": [
                        {
                            "private_results": [
                                {
                                    "resource_id": "r1",
                                    "status": "succeeded",
                                    "after": after,
                                    "backup_ref": {
                                        "path": str(backup),
                                        "state": before,
                                    },
                                }
                            ]
                        }
                    ],
                    "shared_results": [],
                },
            }
            sealed = manifest["payload"]["tool_versions"]
            with mock.patch(
                "sbtd_migration._verified_runtime_pair",
                return_value=(predecessor, current["onboard"]),
            ):
                _require_runtime_lineage(manifest, receipt, sealed, current)
                with self.assertRaises(ContractError) as unlisted:
                    _require_runtime_lineage(
                        manifest,
                        receipt,
                        {"onboard": "runtime-sha256:other", "graft": "0.18.0"},
                        current,
                    )
                self.assertEqual(unlisted.exception.code, "version-conflict")
                with self.assertRaises(ContractError) as missing:
                    _require_runtime_lineage(manifest, None, sealed, current)
                self.assertEqual(missing.exception.code, "version-conflict")
                partial = json.loads(json.dumps(receipt))
                partial["payload"]["status"] = "failed"
                with self.assertRaises(ContractError) as incomplete:
                    _require_runtime_lineage(manifest, partial, sealed, current)
                self.assertEqual(incomplete.exception.code, "lineage-conflict")
                backup.write_bytes(b"changed\n")
                with self.assertRaises(ContractError) as drifted:
                    _require_runtime_lineage(manifest, receipt, sealed, current)
                self.assertEqual(drifted.exception.code, "lineage-conflict")

    def test_recovery_receipt_replaces_only_completed_inverse_states(self):
        from onboard_contracts import ContractError
        from sbtd_migration import _require_runtime_lineage
        from sbtd_migration_files import snapshot

        predecessor = (
            "runtime-sha256:27e74bf511e8b62ad6dac07188933811bd429a84b38b8f01ae025e997fdd7750"
        )
        current = {"onboard": "runtime-sha256:successor", "graft": "0.18.0"}
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            restored = base / "restored.txt"
            untouched = base / "untouched.txt"
            restored.write_bytes(b"applied\n")
            applied_restored = snapshot(restored)
            restored.write_bytes(b"pre-apply\n")
            untouched.write_bytes(b"applied\n")
            backup = base / "backup.txt"
            backup.write_bytes(b"original\n")
            restored_after = snapshot(restored)
            applied_after = snapshot(untouched)
            backup_state = snapshot(backup)
            manifest = {
                "manifest_id": "m1",
                "payload": {
                    "tool_versions": {"onboard": predecessor, "graft": "0.18.0"},
                    "projects": [
                        {
                            "private_operations": [
                                {
                                    "phase": "apply",
                                    "resource_id": "restored",
                                    "target": str(restored),
                                },
                                {
                                    "phase": "apply",
                                    "resource_id": "untouched",
                                    "target": str(untouched),
                                },
                            ]
                        }
                    ],
                    "shared_operations": [],
                },
            }
            receipt = {
                "apply_id": "a1",
                "payload": {
                    "manifest_id": "m1",
                    "status": "applied",
                    "projects": [
                        {
                            "private_results": [
                                {
                                    "resource_id": "restored",
                                    "status": "succeeded",
                                    "after": applied_restored,
                                    "backup_ref": {
                                        "path": str(backup),
                                        "state": backup_state,
                                    },
                                },
                                {
                                    "resource_id": "untouched",
                                    "status": "succeeded",
                                    "after": applied_after,
                                    "backup_ref": None,
                                },
                            ]
                        }
                    ],
                    "shared_results": [],
                },
            }
            recovery = {
                "payload": {
                    "manifest_id": "m1",
                    "results": [
                        {
                            "resource_id": "restored",
                            "phase": "cleanup",
                            "status": "succeeded",
                            "after": {"type": "absent", "checksum": None},
                        },
                        {
                            "resource_id": "restored",
                            "phase": "apply",
                            "status": "succeeded",
                            "after": restored_after,
                        },
                        {
                            "resource_id": "untouched",
                            "status": "failed",
                            "after": applied_after,
                        },
                    ],
                }
            }
            sealed = manifest["payload"]["tool_versions"]
            with mock.patch(
                "sbtd_migration._verified_runtime_pair",
                return_value=(predecessor, current["onboard"]),
            ):
                _require_runtime_lineage(
                    manifest, receipt, sealed, current, recovery
                )
                untouched.write_bytes(b"drifted\n")
                with self.assertRaises(ContractError) as untouched_drift:
                    _require_runtime_lineage(
                        manifest, receipt, sealed, current, recovery
                    )
                self.assertEqual(untouched_drift.exception.code, "lineage-conflict")
                untouched.write_bytes(b"applied\n")
                restored.write_bytes(b"also-drifted\n")
                with self.assertRaises(ContractError) as restored_drift:
                    _require_runtime_lineage(
                        manifest, receipt, sealed, current, recovery
                    )
                self.assertEqual(restored_drift.exception.code, "lineage-conflict")
                restored.write_bytes(b"pre-apply\n")
                with self.assertRaises(ContractError) as unlisted:
                    _require_runtime_lineage(
                        manifest,
                        receipt,
                        sealed,
                        {
                            "onboard": "runtime-sha256:unlisted-successor",
                            "graft": "0.18.0",
                        },
                        recovery,
                    )
                self.assertEqual(unlisted.exception.code, "version-conflict")
                partial = json.loads(json.dumps(receipt))
                partial["payload"]["status"] = "failed"
                with self.assertRaises(ContractError) as incomplete:
                    _require_runtime_lineage(
                        manifest, partial, sealed, current, recovery
                    )
                self.assertEqual(incomplete.exception.code, "lineage-conflict")


    def test_tampered_lineage_document_is_version_conflict(self):
        import sbtd_migration
        from onboard_contracts import ContractError
        from sbtd_migration import _LINEAGE_DOCUMENT

        official = _LINEAGE_DOCUMENT.read_bytes()
        document = json.loads(official)
        with tempfile.TemporaryDirectory() as directory:
            tampered = Path(directory).resolve() / "runtime-lineage.json"
            cases = {
                "successor": {
                    **document,
                    "successor": "runtime-sha256:" + "ab" * 32,
                },
                "signature": {
                    **document,
                    "signature": "A" * len(document["signature"]),
                },
            }
            for name, payload in cases.items():
                with self.subTest(name=name):
                    tampered.write_text(
                        json.dumps(payload), encoding="utf-8"
                    )
                    with (
                        mock.patch.object(
                            sbtd_migration, "_LINEAGE_DOCUMENT", tampered
                        ),
                        self.assertRaises(ContractError) as error,
                    ):
                        sbtd_migration._verified_runtime_pair()
                    self.assertEqual(error.exception.code, "version-conflict")
        self.assertEqual(_LINEAGE_DOCUMENT.read_bytes(), official)



if __name__ == "__main__":
    unittest.main()
