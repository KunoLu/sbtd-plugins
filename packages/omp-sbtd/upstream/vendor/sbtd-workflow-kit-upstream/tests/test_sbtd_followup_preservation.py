"""Regression tests for the followup preservation security findings.

P123-ANCESTOR-OUTPUT-OVERLAP (FollowupSecurity finding 1): the deployment
evidence output must never land inside an immutable ancestor original or a
stage backup object, and the rejection must happen before any deployment
target changes; a disjoint sibling directory under the inherited vault
stays permitted.

P123-DIRECTORY-UPGRADE-BACKUP (FollowupSecurity finding 2): a legitimate
predecessor-owned installation directory built from an older canonical
source is explicitly allowed to differ from the current template; the
upgrade must install, retry, and recover its exact prior bytes.

Everything runs inside an isolated TemporaryDirectory HOME through the
imported FollowupMigration fixture (composition only, no subclassing) with
the labeled smoke-only native doubles (合成夹具；不证明真实 host 部署。). No
write ever reaches the live HOME, the demo assets, or the production
template tree: the older-source catalog swap points at an isolated copy
under the temporary base, and the test proves the real template source is
byte-identical before and after.
"""
from __future__ import annotations

import dataclasses
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

import sbtd_graft_deployment
from onboard_contracts import ContractError, canonical_json_bytes
from sbtd_migration import apply_migration
from sbtd_migration_files import save_document, snapshot
from sbtd_recovery import apply_recovery, plan_recovery

from tests.test_sbtd_followup_batch import FollowupMigration
from tests.test_sbtd_migration_legacy import (
    _json_bytes,
    _legacy_source,
    _sidecar,
    _task_md,
)
from tests.test_sbtd_migration_plan import _decisions, _item, _ref, _write


def _protected_originals_dirs(fixture):
    """Intact private originals directories of every batch in the ancestry."""
    protected = []
    for manifest_path in (fixture.original_manifest_path, fixture.manifest_path):
        if manifest_path is None or not manifest_path.is_file():
            continue
        manifest_id = json.loads(manifest_path.read_bytes())["manifest_id"]
        originals = fixture.vault / manifest_id / "originals"
        if originals.is_dir():
            protected.extend(
                sorted(path for path in originals.iterdir() if path.is_dir())
            )
    return protected


def _stage_backup_dir(fixture):
    """One real directory backup object from a predecessor stage."""
    return min(
        path
        for path in fixture.vault.rglob("*")
        if path.is_dir() and path.parent.name in {"apply", "deploy", "cleanup"}
    )


class FollowupAncestorOutputTests(unittest.TestCase):
    """Finding 1: evidence output must not corrupt immutable ancestry."""

    def _apply_at_vault_root(self, fixture, followup):
        # A followup manifest stored at the inherited private vault root
        # places every ancestor backup object inside the permitted output
        # scope; the stage itself is legitimate and must succeed.
        manifest_path = fixture.vault / "followup-manifest.json"
        manifest_path.write_bytes(canonical_json_bytes(followup))
        with mock.patch.dict(os.environ, fixture.environment):
            applied, code = apply_migration(
                manifest_path, confirmed=True, no_routing_approvals=True
            )
        self.assertEqual(code, 0, applied)
        receipt = applied["migration"]["apply_receipt"]
        apply_path = fixture.vault / ("apply-" + receipt["apply_id"] + ".json")
        self.assertTrue(apply_path.is_file())
        return manifest_path, apply_path

    def test_output_descendant_of_protected_backups_is_rejected_before_any_write(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            # Preinstall one canonical directory so the predecessor actually
            # creates a directory backup, rather than assuming a fresh install
            # has one (its directory targets would all be absent).
            with mock.patch.dict(os.environ, fixture.environment):
                existing = next(
                    item
                    for item in sbtd_graft_deployment._installation_templates(
                        [str(fixture.root)]
                    )
                    if item.target.name == "sbtd-task"
                )
            shutil.copytree(existing.source, existing.target)
            fixture.build()
            protected = _protected_originals_dirs(fixture)
            self.assertTrue(protected)
            protected.append(_stage_backup_dir(fixture))
            # Exercise the ancestry-overlap gate, not the earlier POSIX
            # privacy check. Directory digests cover content, not mode bits.
            if os.name == "posix":
                for container in protected:
                    container.chmod(0o700)
            followup = fixture.plan_followup()
            manifest_path, apply_path = self._apply_at_vault_root(fixture, followup)
            home_before = snapshot(fixture.home)
            root_before = snapshot(fixture.root)
            proof = fixture.predecessor_proof()
            for container in protected:
                with self.subTest(container=str(container)):
                    output_path = container / "deployment.json"
                    with self.assertRaises(ContractError) as error:
                        fixture.execute_deployment(
                            manifest_path, apply_path, output_path
                        )
                    self.assertEqual(error.exception.code, "private-scope")
                    self.assertFalse(output_path.exists())
            # The rejection happened before any deployment target changed,
            # and every ancestor backup kept its exact bytes.
            self.assertEqual(snapshot(fixture.home), home_before)
            self.assertEqual(snapshot(fixture.root), root_before)
            for path, raw in proof.items():
                self.assertEqual(Path(path).read_bytes(), raw, path)

    def test_output_in_disjoint_sibling_vault_directory_is_permitted(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            followup = fixture.plan_followup()
            manifest_path, apply_path = self._apply_at_vault_root(fixture, followup)
            sibling = fixture.vault / "sibling-evidence"
            sibling.mkdir(mode=0o700)
            ancestor_bytes = {
                str(path): snapshot(path)
                for path in _protected_originals_dirs(fixture)
            }
            result, code = fixture.execute_deployment(
                manifest_path, apply_path, sibling / "deployment.json"
            )
            self.assertEqual(code, 0, result)
            self.assertTrue((sibling / "deployment.json").is_file())
            self.assertTrue((fixture.home / ".omp/agent/mcp.json").is_file())
            for path, state in ancestor_bytes.items():
                self.assertEqual(snapshot(Path(path)), state, path)

    def test_output_descendant_of_published_directory_candidate_is_rejected(
        self,
    ):
        # Security rereview: the protected closure must also cover directory
        # publication candidates enumerated from the manifest input closure.
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            fixture = FollowupMigration(base, via_successor=False)
            # This publication scenario has no session continuation data.
            # Remove the helper's unrelated synthetic workspace before any
            # approval or source snapshot is sealed.
            shutil.rmtree(fixture.root / ".trellis/workspace")
            # Mirror MigrationPlanClosureTests._tree_closure_fixture (helper
            # composition, no subclassing): a legacy task folder plus an
            # approved DIRECTORY candidate stored inside the inherited vault.
            folder = fixture.root / ".trellis/tasks/09-01-alpha"
            source_raw = _json_bytes(_legacy_source())
            _write(folder / "task.json", source_raw)
            _write(folder / "prd.md", b"# legacy prd\n")
            candidate = fixture.vault / "cand-tree"
            _write(candidate / "task.md", _task_md())
            _write(candidate / "legacy-task.json", _sidecar(source_raw))
            _write(candidate / "prd.md", b"# legacy prd\n")
            fixture.publication_decisions = _decisions(
                fixture.vault,
                [
                    _item(
                        "09-01-alpha-tree",
                        [
                            _ref(folder / "task.json"),
                            _ref(folder / "prd.md"),
                        ],
                        fixture.root / "ai/tasks/alpha",
                        "share",
                        candidate,
                    )
                ],
            )
            fixture.build()
            # The completed predecessor really published the candidate tree.
            published = fixture.root / "ai/tasks/alpha"
            self.assertTrue((published / "task.md").is_file())
            self.assertTrue((published / "legacy-task.json").is_file())
            candidate_before = snapshot(candidate)
            followup = fixture.plan_followup()
            manifest_path, apply_path = self._apply_at_vault_root(fixture, followup)
            home_before = snapshot(fixture.home)
            root_before = snapshot(fixture.root)
            proof = fixture.predecessor_proof()
            # Exercise the ancestry-overlap gate, not the earlier POSIX
            # privacy check. Directory digests cover content, not mode bits.
            if os.name == "posix":
                candidate.chmod(0o700)
            output_path = candidate / "deployment.json"
            with self.assertRaises(ContractError) as error:
                fixture.execute_deployment(
                    manifest_path, apply_path, output_path
                )
            self.assertEqual(error.exception.code, "private-scope")
            # Rejected before any write: no target changed, the candidate is
            # byte-identical, and every predecessor backup is intact.
            self.assertFalse(output_path.exists())
            self.assertEqual(snapshot(fixture.home), home_before)
            self.assertEqual(snapshot(fixture.root), root_before)
            self.assertEqual(snapshot(candidate), candidate_before)
            for path, raw in proof.items():
                self.assertEqual(Path(path).read_bytes(), raw, path)


class FollowupDirectoryUpgradeTests(unittest.TestCase):
    """Finding 2: predecessor-owned older directory upgrades cleanly."""

    def test_older_owned_directory_upgrades_retries_and_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            fixture = FollowupMigration(base)
            skills_dir = Path(fixture.environment["AGENT_SKILLS_DIR"])
            with mock.patch.dict(os.environ, fixture.environment):
                catalog = sbtd_graft_deployment._installation_templates(
                    [str(fixture.root)]
                )
            operation = next(
                op
                for op in catalog
                if op.target.parent == skills_dir
                and op.target.name != "sbtd-workflow-onboard"
            )
            real_source = operation.source
            production_before = snapshot(real_source)
            older_source = base / "older-source" / operation.target.name
            shutil.copytree(real_source, older_source)
            (older_source / "OLDER-RUNTIME.txt").write_bytes(b"older runtime\n")
            installed = operation.target
            real_catalog = sbtd_graft_deployment._installation_templates

            def older_catalog(roots, *, omp_agents_target=None):
                return [
                    dataclasses.replace(op, source=older_source)
                    if op.target == operation.target
                    else op
                    for op in real_catalog(
                        roots, omp_agents_target=omp_agents_target
                    )
                ]

            # The whole predecessor chain resolves the isolated older copy;
            # the production template tree is never written.
            with mock.patch(
                "sbtd_graft_deployment._installation_templates",
                new=older_catalog,
            ):
                fixture.build()
            self.assertEqual(snapshot(installed), snapshot(older_source))
            self.assertNotEqual(snapshot(older_source), snapshot(real_source))
            self.assertEqual(snapshot(real_source), production_before)

            # The followup plan re-declares the directory from the current
            # source and carries the exact predecessor outcome as its
            # required before-state.
            followup = fixture.plan_followup()
            declared = next(
                op
                for op in followup["payload"]["shared_operations"]
                if op["target"] == str(installed)
            )
            self.assertEqual(
                declared["change"]["source_ref"]["state"], snapshot(real_source)
            )
            self.assertEqual(
                declared["before_requirement"],
                {"kind": "state", "state": snapshot(installed)},
            )

            applied, code, manifest_path = fixture.apply_followup(followup)
            self.assertEqual(code, 0, applied)
            receipt = applied["migration"]["apply_receipt"]
            apply_path = fixture.followup_evidence / (
                "apply-" + receipt["apply_id"] + ".json"
            )
            result, code, deployment_path = fixture.deploy_followup(
                manifest_path, apply_path
            )
            self.assertEqual(code, 0, result)
            # The older directory upgraded to the current template, and the
            # exact prior bytes were preserved in a private backup.
            self.assertEqual(snapshot(installed), snapshot(real_source))
            payload = result["deploymentEvidence"]["evidence"]["payload"]
            upgraded = next(
                entry
                for entry in payload["shared_results"]
                if entry["resource_id"] == declared["resource_id"]
            )
            self.assertEqual(upgraded["status"], "succeeded")
            self.assertIsNotNone(upgraded["backup_ref"])
            self.assertTrue(Path(upgraded["backup_ref"]["path"]).is_dir())
            proof = fixture.predecessor_proof()

            # A retry deploy stays cumulative and keeps the upgrade.
            retry, code, _retry_path = fixture.deploy_followup(
                manifest_path,
                apply_path,
                previous_path=deployment_path,
                output_name="deployment-retry.json",
            )
            self.assertEqual(code, 0, retry)
            self.assertEqual(snapshot(installed), snapshot(real_source))

            verification_path = fixture.followup_evidence / "verification.json"
            verified, code = fixture.verify(
                manifest_path, apply_path, deployment_path, verification_path
            )
            self.assertEqual(code, 0, verified)
            cleaned, code = fixture.cleanup(
                manifest_path, apply_path, deployment_path, verification_path
            )
            self.assertEqual(code, 0, cleaned)
            cleanup_receipt = cleaned["migration"]["cleanup_receipt"]
            cleanup_path = fixture.followup_evidence / (
                "cleanup-" + cleanup_receipt["cleanup_id"] + ".json"
            )

            # Recovery restores the exact prior (older) directory bytes.
            with mock.patch.dict(os.environ, fixture.environment):
                envelope, code = plan_recovery(
                    manifest_path,
                    apply_receipt_path=apply_path,
                    deployment_evidence_path=deployment_path,
                    cleanup_receipt_path=cleanup_path,
                )
            self.assertEqual(code, 0, envelope)
            plan = envelope["recovery"]["plan"]
            plan_path = fixture.followup_evidence / "recovery-plan.json"
            save_document(
                plan_path, plan, private_root=fixture.followup_evidence
            )
            with mock.patch.dict(os.environ, fixture.environment):
                restored, code = apply_recovery(
                    plan_path, confirm_recovery=plan["plan_id"]
                )
            self.assertEqual(code, 0, restored)
            self.assertEqual(restored["status"], "restored")
            self.assertEqual(snapshot(installed), snapshot(older_source))
            # The production template tree was never touched, and the
            # predecessor evidence and backups kept their exact bytes.
            self.assertEqual(snapshot(real_source), production_before)
            for path, raw in proof.items():
                self.assertEqual(Path(path).read_bytes(), raw, path)

    def test_older_launcher_package_upgrades_through_the_activation_gate(self):
        # The launcher package is a distinct gate: the installed
        # sbtd-workflow-onboard directory must byte-match the canonical
        # package (sbtd_graft_deployment._PACKAGE) when the MCP wiring is
        # activated. A real followup after P1-23 script changes necessarily
        # upgrades it; the predecessor is aged with an isolated, labeled
        # older template variant (marker file only, scripts byte-identical -
        # no old-runtime claims) and _PACKAGE pinned to the same copy.
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            fixture = FollowupMigration(base)
            with mock.patch.dict(os.environ, fixture.environment):
                catalog = sbtd_graft_deployment._installation_templates(
                    [str(fixture.root)]
                )
            operation = next(
                op
                for op in catalog
                if op.target.name == "sbtd-workflow-onboard"
            )
            real_source = operation.source
            production_before = snapshot(real_source)
            older_source = base / "older-launcher" / operation.target.name
            shutil.copytree(real_source, older_source)
            (older_source / "OLDER-LAUNCHER.txt").write_bytes(
                b"isolated older launcher template variant\n"
            )
            installed = operation.target
            real_catalog = sbtd_graft_deployment._installation_templates

            def older_catalog(roots, *, omp_agents_target=None):
                return [
                    dataclasses.replace(op, source=older_source)
                    if op.target == operation.target
                    else op
                    for op in real_catalog(
                        roots, omp_agents_target=omp_agents_target
                    )
                ]

            # Predecessor lifecycle only: template catalog AND the canonical
            # package pin both resolve the isolated older copy.
            with (
                mock.patch(
                    "sbtd_graft_deployment._installation_templates",
                    new=older_catalog,
                ),
                mock.patch("sbtd_graft_deployment._PACKAGE", new=older_source),
            ):
                fixture.build()
            self.assertEqual(snapshot(installed), snapshot(older_source))
            self.assertNotEqual(snapshot(older_source), snapshot(real_source))
            self.assertEqual(snapshot(real_source), production_before)

            followup = fixture.plan_followup()
            declared = next(
                op
                for op in followup["payload"]["shared_operations"]
                if op["target"] == str(installed)
            )
            self.assertEqual(
                declared["change"]["source_ref"]["state"], snapshot(real_source)
            )
            self.assertEqual(
                declared["before_requirement"],
                {"kind": "state", "state": snapshot(installed)},
            )

            applied, code, manifest_path = fixture.apply_followup(followup)
            self.assertEqual(code, 0, applied)
            receipt = applied["migration"]["apply_receipt"]
            apply_path = fixture.followup_evidence / (
                "apply-" + receipt["apply_id"] + ".json"
            )
            result, code, deployment_path = fixture.deploy_followup(
                manifest_path, apply_path
            )
            self.assertEqual(code, 0, result)
            # The new package installed and its checksum passed the MCP
            # activation gate: the OMP wiring exists and launches the
            # installed entry point.
            self.assertEqual(snapshot(installed), snapshot(real_source))
            servers = json.loads(
                (fixture.home / ".omp/agent/mcp.json").read_text(
                    encoding="utf-8"
                )
            )["mcpServers"]
            self.assertEqual(len(servers), 1)
            server = next(iter(servers.values()))
            self.assertEqual(
                server["args"][2],
                str(
                    fixture.home
                    / ".agent/skills/sbtd-workflow-onboard/scripts/sbtd_graft_entry.py"
                ),
            )
            payload = result["deploymentEvidence"]["evidence"]["payload"]
            upgraded = next(
                entry
                for entry in payload["shared_results"]
                if entry["resource_id"] == declared["resource_id"]
            )
            self.assertEqual(upgraded["status"], "succeeded")
            self.assertIsNotNone(upgraded["backup_ref"])
            proof = fixture.predecessor_proof()

            # A retry deploy stays cumulative and keeps the new package.
            retry, code, _retry_path = fixture.deploy_followup(
                manifest_path,
                apply_path,
                previous_path=deployment_path,
                output_name="deployment-retry.json",
            )
            self.assertEqual(code, 0, retry)
            self.assertEqual(snapshot(installed), snapshot(real_source))

            verification_path = fixture.followup_evidence / "verification.json"
            verified, code = fixture.verify(
                manifest_path, apply_path, deployment_path, verification_path
            )
            self.assertEqual(code, 0, verified)
            cleaned, code = fixture.cleanup(
                manifest_path, apply_path, deployment_path, verification_path
            )
            self.assertEqual(code, 0, cleaned)
            cleanup_receipt = cleaned["migration"]["cleanup_receipt"]
            cleanup_path = fixture.followup_evidence / (
                "cleanup-" + cleanup_receipt["cleanup_id"] + ".json"
            )

            # Recovery restores the older launcher package bytes.
            with mock.patch.dict(os.environ, fixture.environment):
                envelope, code = plan_recovery(
                    manifest_path,
                    apply_receipt_path=apply_path,
                    deployment_evidence_path=deployment_path,
                    cleanup_receipt_path=cleanup_path,
                )
            self.assertEqual(code, 0, envelope)
            plan = envelope["recovery"]["plan"]
            plan_path = fixture.followup_evidence / "recovery-plan.json"
            save_document(
                plan_path, plan, private_root=fixture.followup_evidence
            )
            with mock.patch.dict(os.environ, fixture.environment):
                restored, code = apply_recovery(
                    plan_path, confirm_recovery=plan["plan_id"]
                )
            self.assertEqual(code, 0, restored)
            self.assertEqual(restored["status"], "restored")
            self.assertEqual(snapshot(installed), snapshot(older_source))
            self.assertEqual(snapshot(real_source), production_before)
            for path, raw in proof.items():
                self.assertEqual(Path(path).read_bytes(), raw, path)


if __name__ == "__main__":
    unittest.main()
