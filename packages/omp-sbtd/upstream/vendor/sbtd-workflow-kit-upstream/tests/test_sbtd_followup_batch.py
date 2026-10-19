"""Followup batch behavior: original -> successor codex deployment -> verified
cleanup -> OMP followup plan/apply/deploy/verify/cleanup/recovery.

Everything runs inside an isolated TemporaryDirectory HOME. The only native
boundaries (verified runtime, project graph build, project smoke) are
deterministic smoke-only doubles; they do not prove a real host deployment
(合成夹具；不证明真实 host 部署。). No write ever reaches the live HOME or demo
assets, and no test subclasses another test class, so no suite is duplicated.

Reusable smoke fixture (parent CLI smoke, runtime mocks explicitly labeled):

    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory).resolve()
        with FollowupMigration(base) as fixture:
            # fixture.root / fixture.environment / fixture.followup_kwargs()
            # fixture.manifest_path, apply_path, deployment_path,
            # fixture.verification_path, cleanup_path  (predecessor five docs)
            # plan/apply/verify/cleanup: run_migration(SimpleNamespace(...))
            # under mock.patch.dict(os.environ, fixture.environment);
            # deploy: fixture.execute_deployment(manifest_path, apply_path,
            # output_path) wraps load_deployment_context +
            # execute_migration_deployment inside fixture.deployment_mocks().
            ...
"""
from __future__ import annotations

import contextlib
import copy
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

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import onboard_contracts as contracts
import sbtd_graft_deployment
from onboard_contracts import ContractError, canonical_json_bytes
from sbtd_graft_deployment import execute_migration_deployment, load_deployment_context
from sbtd_migration import apply_migration, cleanup_migration, runtime_versions
from sbtd_migration_files import read_file, save_document, snapshot
from sbtd_migration_plan import plan_migration, validate_legacy_inputs
from sbtd_migration_verify import verify_migration
from sbtd_recovery import apply_recovery, plan_recovery

from tests.test_sbtd_migration_apply import legacy_project
from tests.test_sbtd_migration_cleanup import VerifiedMigration, _fake_vendor_adapter
from tests.test_sbtd_migration_verify import _tree_bytes

_RUNTIME = {"node": "/fixture/node", "cli": "/fixture/cli.js", "python": "/fixture/python"}


def _reader(reference):
    return read_file(Path(reference["path"]), reference["state"])


def _graph_fixture(project, _runtime):
    (project / "graft").mkdir(exist_ok=True)
    (project / "graft/fixture").write_bytes(b"synthetic native output")


def _synthetic_smoke(manifest):
    """Smoke-only native report double bound to one manifest's revisions.

    Writes synthetic validation-evidence files; does not prove a real host
    deployment (合成 smoke 夹具；不证明真实 host 部署。).
    """
    records = {project["root"]: project for project in manifest["payload"]["projects"]}

    def smoke(project, smoke_runtime, evidence_dir):
        record = records[str(project)]
        source_ref, head = record["source_ref"], record["head"]
        label = (
            source_ref
            if source_ref is not None
            else "HEAD" if head is not None else "non-git"
        )
        revision = "dirty" if head is not None else "unknown"
        moment = datetime.now(timezone.utc).isoformat()
        stem = (
            "api-report-graft-smoke-"
            + hashlib.sha256(str(project).encode()).hexdigest()[:16]
            + "-"
            + datetime.now(timezone.utc).strftime("%Y_%m_%d-%H_%M_%S-%f")
        )
        report_path = evidence_dir / (stem + ".json")
        summary_path = evidence_dir / (stem + ".md")
        envelope_path = evidence_dir / (stem + ".evidence.json")
        summary_path.write_text(
            "合成 smoke 摘要；不证明真实 host 部署。\n", encoding="utf-8"
        )
        raw = {
            "repositoryKey": hashlib.sha256(str(project).encode()).hexdigest(),
            "projectRoot": str(project),
            "sourceRef": label,
            "sourceCommit": head,
            "worktreeState": revision,
            "sourceRevision": revision,
            "evidenceSource": "developer-local",
            "trigger": "manual",
            "environmentAlignment": "verified",
            "evidencePublication": "local-only",
            "e2eMode": "smoke-only",
            "mockStrategy": "none",
            "startedAt": moment,
            "finishedAt": moment,
            "command": [smoke_runtime["node"], smoke_runtime["cli"], "check", "."],
            "stdout": "synthetic native output",
            "stderr": "",
            "exitCode": 0,
            "processExitCode": 0,
            "timedOut": False,
        }
        report_path.write_text(json.dumps(raw), encoding="utf-8")
        envelope = {
            "schemaVersion": 1,
            "runId": "followup-smoke",
            "createdAt": moment,
            "evidenceSource": "developer-local",
            "trigger": "manual",
            "repository": {
                "repositoryKey": raw["repositoryKey"],
                "sourceRef": label,
                "sourceCommit": head,
                "worktreeState": revision,
            },
            "sourceRevision": revision,
            "environmentAlignment": "verified",
            "e2eMode": "smoke-only",
            "mockStrategy": "none",
            "featureSources": [],
            "reports": [
                {
                    "testType": "api",
                    "path": str(report_path),
                    "summaryMd": str(summary_path),
                    "sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
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
            for path in (report_path, envelope_path, summary_path)
        ]

    return smoke


def _failed_copy(path, kind, destination):
    """Reseal one stage document with a truthful failed status shape."""
    document = json.loads(path.read_bytes())
    payload = document["payload"]
    payload["status"] = "failed"
    for project in payload["projects"]:
        project["status"] = "failed"
        project["reason"] = "synthetic failure"
        project["nextStep"] = "synthetic next step"
    failed = contracts.seal_document(kind, payload)
    destination.write_bytes(canonical_json_bytes(failed))
    return destination


# Keep the full launcher package and two ordinary sibling Skill directories.
_FOCUSED_SKILL_DIRECTORIES = frozenset(
    {"sbtd-workflow-onboard", "sbtd-task", "project-validation"}
)


def _focused_installation_templates(case):
    """Narrow the installation input for catalog-independent boundary tests.

    The wrapper always calls the genuine selection and only drops directory
    operations whose target is an unrelated sibling skill; every kept
    operation is the exact selected object (real sources, payload bytes and
    targets), including all non-directory operations. Classes whose
    invariants do not depend on the full catalog call this from ``setUp``.
    Normal test cleanup restores the unfiltered selection; nested catalog
    patches still compose through the same module attribute.
    """
    real_catalog = sbtd_graft_deployment._installation_templates

    def focused(roots, *, omp_agents_target=None):
        return [
            operation
            for operation in real_catalog(roots, omp_agents_target=omp_agents_target)
            if operation.kind != "dir"
            or operation.target.name in _FOCUSED_SKILL_DIRECTORIES
        ]

    patcher = mock.patch("sbtd_graft_deployment._installation_templates", new=focused)
    case.addCleanup(patcher.stop)
    patcher.start()


def assert_proof_intact(case, proof):
    """Every captured predecessor proof file still exists, byte-identical."""
    for name, raw in proof.items():
        path = Path(name)
        case.assertTrue(path.is_file(), f"predecessor proof missing: {name}")
        case.assertEqual(
            path.read_bytes(), raw, f"predecessor proof drifted: {name}"
        )


class FollowupMigration:
    """Isolated original -> codex deployment -> verified cleanup predecessor.

    Reusable context manager driving the real stage entry points against an
    isolated HOME; only the three native boundaries are labeled smoke-only
    doubles. ``build()`` leaves a complete codex predecessor whose five
    private documents feed plan_migration's followup kwargs. With
    ``via_successor`` the deployment chain runs on a successor batch
    (original stays deployment-less); otherwise the original batch deploys
    directly. Followup outputs live in the separate private
    ``followup_evidence`` directory so predecessor proof stays byte-identical.
    """

    def __init__(self, base, names=("project",), platform="codex", via_successor=True, git=False, publication_decisions=None):
        self.base = base
        self.platform = platform
        self.via_successor = via_successor
        self.roots = [legacy_project(base, name) for name in names]
        self.root = self.roots[0]
        self.home = base / "home"
        self.vault = base / "vault"
        self.evidence = base / "evidence"
        self.followup_evidence = base / "followup-evidence"
        for path in (self.home, self.vault, self.evidence, self.followup_evidence):
            path.mkdir(mode=0o700)
        self.environment = {
            "HOME": str(self.home),
            "USERPROFILE": str(self.home),
            "CODEX_HOME": str(self.home / ".codex"),
            "AGENT_SKILLS_DIR": str(self.home / ".agent/skills"),
            "PI_CODING_AGENT_DIR": str(self.home / ".omp/agent"),
            "PI_CONFIG_DIR": ".omp",
            "OMP_PROFILE": "default",
            "PI_PROFILE": "default",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        if git:
            self._git_init()
        self.original_manifest_path = self.evidence / "original-manifest.json"
        self.manifest_path = self.evidence / "manifest.json"
        self.apply_path = None
        self.deployment_path = self.evidence / "deployment.json"
        self.verification_path = self.evidence / "verification.json"
        self.cleanup_path = None
        self.manifest = None
        self.apply_receipt = None
        self.deployment = None
        self.verification = None
        self.cleanup_receipt = None
        # Optional decisions document for the original/direct plan only;
        # successor and followup plans always inherit (None preserves the
        # default deployment-less/publication-less fixture).
        self.publication_decisions = publication_decisions

    def __enter__(self):
        self.build()
        return self

    def __exit__(self, *exc):
        return False

    def _git(self, *arguments):
        result = subprocess.run(
            ["git", "-C", str(self.root), *arguments],
            check=True,
            capture_output=True,
            env={**os.environ, **self.environment},
        )
        return result.stdout.decode().strip()

    def _git_init(self):
        for command in (
            ["git", "init", "-b", "main", str(self.root)],
            ["git", "-C", str(self.root), "config", "user.email", "fixture@test"],
            ["git", "-C", str(self.root), "config", "user.name", "fixture"],
            ["git", "-C", str(self.root), "add", "-A"],
            ["git", "-C", str(self.root), "commit", "-m", "legacy state"],
        ):
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                env={**os.environ, **self.environment},
            )

    def deployment_mocks(self, manifest_document, *, rebuild_graph=True):
        """Smoke-only native boundary doubles (不证明真实 host 部署)."""
        graph = (
            _graph_fixture
            if rebuild_graph
            else AssertionError("completed graph must not be rebuilt")
        )
        stack = contextlib.ExitStack()
        stack.enter_context(
            mock.patch(
                "sbtd_graft_deployment.verified_runtime", return_value=dict(_RUNTIME)
            )
        )
        stack.enter_context(
            mock.patch(
                "sbtd_graft_deployment.build_project_graph", side_effect=graph
            )
        )
        stack.enter_context(
            mock.patch(
                "sbtd_graft_deployment.run_project_smoke",
                side_effect=_synthetic_smoke(manifest_document),
            )
        )
        return stack

    def execute_deployment(
        self, manifest_path, apply_path, output_path, *, previous_path=None,
        rebuild_graph=True,
    ):
        """Real load_deployment_context + execute_migration_deployment."""
        document = json.loads(manifest_path.read_bytes())
        with mock.patch.dict(os.environ, self.environment):
            context = load_deployment_context(
                manifest_path,
                apply_path,
                output_path,
                previous_path=previous_path,
                mode="init",
                roots=self.roots,
                hooks_authorized=False,
            )
            with self.deployment_mocks(document, rebuild_graph=rebuild_graph):
                return execute_migration_deployment(context)

    def build(self):
        with mock.patch.dict(os.environ, self.environment):
            if self.via_successor:
                original = plan_migration(
                    [self.root],
                    self.vault,
                    "fixture",
                    self.publication_decisions,
                    tool_versions=runtime_versions(),
                )
                self.original_manifest_path.write_bytes(canonical_json_bytes(original))
                applied, code = apply_migration(
                    self.original_manifest_path,
                    confirmed=True,
                    no_routing_approvals=True,
                )
                if code != 0:
                    raise AssertionError(f"original apply failed: {applied}")
                original_receipt = applied["migration"]["apply_receipt"]
                original_receipt_path = self.evidence / (
                    "apply-" + original_receipt["apply_id"] + ".json"
                )
                self.manifest = plan_migration(
                    [self.root],
                    self.vault,
                    "fixture",
                    None,
                    tool_versions=runtime_versions(),
                    deployment_mode="init",
                    deployment_platform=self.platform,
                    successor_manifest=self.original_manifest_path,
                    successor_apply_receipt=original_receipt_path,
                )
            else:
                self.manifest = plan_migration(
                    [self.root],
                    self.vault,
                    "fixture",
                    self.publication_decisions,
                    tool_versions=runtime_versions(),
                    deployment_mode="init",
                    deployment_platform=self.platform,
                )
            self.manifest_path.write_bytes(canonical_json_bytes(self.manifest))
            applied, code = apply_migration(
                self.manifest_path, confirmed=True, no_routing_approvals=True
            )
            if code != 0:
                raise AssertionError(f"predecessor apply failed: {applied}")
            self.apply_receipt = applied["migration"]["apply_receipt"]
            self.apply_path = self.evidence / (
                "apply-" + self.apply_receipt["apply_id"] + ".json"
            )
            result, code = self.execute_deployment(
                self.manifest_path, self.apply_path, self.deployment_path
            )
        if code != 0:
            raise AssertionError(f"predecessor deployment failed: {result}")
        self.deployment = result["deploymentEvidence"]["evidence"]
        with mock.patch.dict(os.environ, self.environment):
            verified, code = verify_migration(
                self.manifest_path, self.apply_path, self.deployment_path
            )
        if code != 0:
            raise AssertionError(f"predecessor verify failed: {verified}")
        self.verification = verified["migration"]["verification"]
        save_document(
            self.verification_path, self.verification, private_root=self.evidence
        )
        with mock.patch.dict(os.environ, self.environment), _fake_vendor_adapter():
            cleaned, code = cleanup_migration(
                self.manifest_path,
                self.apply_path,
                self.deployment_path,
                self.verification_path,
                confirm_cleanup=self.verification["verification_id"],
            )
        if code != 0:
            raise AssertionError(f"predecessor cleanup failed: {cleaned}")
        self.cleanup_receipt = cleaned["migration"]["cleanup_receipt"]
        self.cleanup_path = self.evidence / (
            "cleanup-" + self.cleanup_receipt["cleanup_id"] + ".json"
        )

    def predecessor_paths(self):
        return {
            "followup_manifest": self.manifest_path,
            "followup_apply_receipt": self.apply_path,
            "followup_deployment_evidence": self.deployment_path,
            "followup_verification": self.verification_path,
            "followup_cleanup_receipt": self.cleanup_path,
        }

    def followup_kwargs(self):
        return dict(self.predecessor_paths())

    def plan_followup(
        self, *, roots=None, vault=None, custodian="fixture", mode="init",
        platform="omp", hooks=False, publication=None, extra=None, **overrides
    ):
        arguments = self.followup_kwargs()
        arguments.update(overrides)
        if extra:
            arguments.update(extra)
        with mock.patch.dict(os.environ, self.environment):
            return plan_migration(
                roots if roots is not None else [self.root],
                vault if vault is not None else self.vault,
                custodian,
                publication,
                tool_versions=runtime_versions(),
                deployment_mode=mode,
                deployment_platform=platform,
                hooks_authorized=hooks,
                **arguments,
            )

    def apply_followup(self, manifest, *, name="manifest.json", previous_receipt_path=None):
        manifest_path = self.followup_evidence / name
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        with mock.patch.dict(os.environ, self.environment):
            applied, code = apply_migration(
                manifest_path,
                previous_receipt_path=previous_receipt_path,
                confirmed=True,
                no_routing_approvals=True,
            )
        return applied, code, manifest_path

    def deploy_followup(
        self, manifest_path, apply_path, *, previous_path=None,
        rebuild_graph=True, output_name="deployment.json",
    ):
        output_path = self.followup_evidence / output_name
        result, code = self.execute_deployment(
            manifest_path,
            apply_path,
            output_path,
            previous_path=previous_path,
            rebuild_graph=rebuild_graph,
        )
        return result, code, output_path

    def verify(self, manifest_path, apply_path, deployment_path, verification_path):
        with mock.patch.dict(os.environ, self.environment):
            verified, code = verify_migration(
                manifest_path, apply_path, deployment_path
            )
        if code == 0:
            save_document(
                verification_path,
                verified["migration"]["verification"],
                private_root=verification_path.parent,
            )
        return verified, code

    def cleanup(
        self, manifest_path, apply_path, deployment_path, verification_path,
        *, previous_receipt_path=None,
    ):
        verification = json.loads(verification_path.read_bytes())
        with mock.patch.dict(os.environ, self.environment), _fake_vendor_adapter():
            return cleanup_migration(
                manifest_path,
                apply_path,
                deployment_path,
                verification_path,
                previous_receipt_path=previous_receipt_path,
                confirm_cleanup=verification["verification_id"],
            )

    def predecessor_proof(self):
        """Byte map of predecessor evidence and every vault backup."""
        proof = {
            str(self.evidence / name): raw
            for name, raw in _tree_bytes(self.evidence).items()
        }
        for path in self.vault.rglob("*"):
            if path.is_file():
                proof[str(path)] = path.read_bytes()
        return proof

    def complete_followup(self, followup=None, *, name="manifest.json"):
        """Drive one full OMP followup chain; return every stage artifact."""
        if followup is None:
            followup = self.plan_followup()
        applied, code, manifest_path = self.apply_followup(followup, name=name)
        if code != 0:
            raise AssertionError(f"followup apply failed: {applied}")
        receipt = applied["migration"]["apply_receipt"]
        apply_path = self.followup_evidence / ("apply-" + receipt["apply_id"] + ".json")
        result, code, deployment_path = self.deploy_followup(manifest_path, apply_path)
        if code != 0:
            raise AssertionError(f"followup deployment failed: {result}")
        verification_path = self.followup_evidence / "verification.json"
        verified, code = self.verify(
            manifest_path, apply_path, deployment_path, verification_path
        )
        if code != 0:
            raise AssertionError(f"followup verify failed: {verified}")
        cleaned, code = self.cleanup(
            manifest_path, apply_path, deployment_path, verification_path
        )
        if code != 0:
            raise AssertionError(f"followup cleanup failed: {cleaned}")
        cleanup_receipt = cleaned["migration"]["cleanup_receipt"]
        return {
            "manifest": followup,
            "manifest_path": manifest_path,
            "receipt": receipt,
            "apply_path": apply_path,
            "deployment": result["deploymentEvidence"]["evidence"],
            "deployment_path": deployment_path,
            "verification": verified["migration"]["verification"],
            "verification_path": verification_path,
            "cleanup_receipt": cleanup_receipt,
            "cleanup_path": self.followup_evidence
            / ("cleanup-" + cleanup_receipt["cleanup_id"] + ".json"),
        }

class FollowupNoTouchAgentsTests(unittest.TestCase):
    """An already-aligned project AGENTS.md survives the whole batch chain."""

    def test_no_touch_chain_preserves_exact_agents_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            # Convert the legacy project to the exact-template shape before
            # any plan runs: live bytes equal the bundled project template
            # while the recorded legacy digest differs.
            template = (
                SCRIPTS.parents[0] / "templates" / "agents" / "AGENTS.project.md"
            ).read_bytes()
            (fixture.root / "AGENTS.md").write_bytes(template)
            hashes_path = fixture.root / ".trellis" / ".template-hashes.json"
            document = json.loads(hashes_path.read_text(encoding="utf-8"))
            document["hashes"]["AGENTS.md"] = hashlib.sha256(
                b"legacy trellis routing marker\n"
            ).hexdigest()
            hashes_path.write_text(json.dumps(document), encoding="utf-8")

            fixture.build()
            # The deployment chain ran on the successor batch.
            successor_project = fixture.manifest["payload"]["projects"][0]
            self.assertIsNotNone(successor_project.get("agents_no_touch"))
            self.assertTrue(
                all(
                    operation["target"] != str(fixture.root / "AGENTS.md")
                    for operation in successor_project["private_operations"]
                )
            )
            self.assertEqual(
                [
                    operation["change"]["kind"]
                    for operation in successor_project["private_operations"]
                    if operation["phase"] == "deploy"
                ],
                ["build-graft"],
            )
            self.assertEqual((fixture.root / "AGENTS.md").read_bytes(), template)

            chain = fixture.complete_followup()
            followup_project = chain["manifest"]["payload"]["projects"][0]
            self.assertEqual(
                followup_project.get("agents_no_touch"),
                successor_project.get("agents_no_touch"),
            )
            self.assertTrue(
                all(
                    operation["target"] != str(fixture.root / "AGENTS.md")
                    for operation in followup_project["private_operations"]
                )
            )
            self.assertEqual(
                [
                    operation["change"]["kind"]
                    for operation in followup_project["private_operations"]
                    if operation["phase"] == "deploy"
                ],
                ["build-graft"],
            )
            self.assertEqual((fixture.root / "AGENTS.md").read_bytes(), template)


class FollowupBatchTests(unittest.TestCase):
    def test_followup_full_chain_preserves_predecessor_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            # Actual predecessor transitions: legacy tree cleaned, codex
            # deployment present, no OMP wiring yet.
            self.assertFalse((fixture.root / ".trellis").exists())
            codex_config = fixture.home / ".codex/config.toml"
            self.assertTrue(codex_config.is_file())
            self.assertFalse((fixture.home / ".omp/agent/mcp.json").exists())
            retained = fixture.verification["payload"]["projects"][0][
                "retained_assets"
            ]
            self.assertTrue(retained)
            retained_snapshots = {
                asset["path"]: snapshot(Path(asset["path"])) for asset in retained
            }
            gitignore_bytes = (fixture.root / ".gitignore").read_bytes()
            proof = fixture.predecessor_proof()
            codex_config_bytes = codex_config.read_bytes()
            untouched = snapshot(fixture.base)

            followup = fixture.plan_followup()
            self.assertEqual(snapshot(fixture.base), untouched)
            payload = followup["payload"]
            binding = payload["followup"]
            self.assertEqual(binding["manifest_id"], fixture.manifest["manifest_id"])
            self.assertEqual(binding["apply_id"], fixture.apply_receipt["apply_id"])
            self.assertEqual(
                binding["deployment_id"], fixture.deployment["deployment_id"]
            )
            self.assertEqual(
                binding["verification_id"], fixture.verification["verification_id"]
            )
            self.assertEqual(
                binding["cleanup_id"], fixture.cleanup_receipt["cleanup_id"]
            )
            for key, path in (
                ("manifest_ref", fixture.manifest_path),
                ("apply_receipt_ref", fixture.apply_path),
                ("deployment_evidence_ref", fixture.deployment_path),
                ("verification_ref", fixture.verification_path),
                ("cleanup_receipt_ref", fixture.cleanup_path),
            ):
                self.assertEqual(binding[key]["path"], str(path))
                self.assertEqual(binding[key]["state"], snapshot(path))
            self.assertNotIn("apply_results", binding)
            self.assertIsNone(payload.get("successor"))
            self.assertEqual(payload["deployment"]["mode"], "init")
            self.assertEqual(payload["deployment"]["platform"], "omp")
            self.assertEqual(
                payload["publication_decisions"], {"schema_version": 1, "items": []}
            )
            self.assertIsNone(payload["routing_approvals"])
            self.assertEqual(payload["backup_root"], str(fixture.vault))
            self.assertEqual(
                payload["custodian"], fixture.manifest["payload"]["custodian"]
            )
            self.assertEqual(
                payload["retention"], fixture.manifest["payload"]["retention"]
            )
            self.assertEqual(len(payload["projects"]), 1)
            project = payload["projects"][0]
            predecessor_project = fixture.manifest["payload"]["projects"][0]
            self.assertEqual(project["root"], predecessor_project["root"])
            self.assertEqual(project["platforms"], predecessor_project["platforms"])
            self.assertIsNone(project["source_ref"])
            self.assertIsNone(project["head"])
            self.assertEqual(project["sources"], [])
            phases = {
                operation["phase"] for operation in project["private_operations"]
            } | {operation["phase"] for operation in payload["shared_operations"]}
            self.assertEqual(phases, {"deploy"})
            contracts.validate_document(
                json.loads(canonical_json_bytes(followup)), "manifest"
            )
            with mock.patch.dict(os.environ, fixture.environment):
                validate_legacy_inputs(followup, _reader)
            self.assertEqual(snapshot(fixture.base), untouched)

            chain = fixture.complete_followup(followup)
            self.assertIsNone(chain["receipt"]["payload"]["previous_receipt_id"])
            self.assertEqual(
                chain["deployment"]["payload"]["manifest_id"],
                followup["manifest_id"],
            )
            self.assertEqual(
                chain["deployment"]["payload"]["apply_id"],
                chain["receipt"]["apply_id"],
            )
            self.assertIsNone(chain["deployment"]["payload"]["previous_deployment_id"])
            # Actual followup transition: OMP wiring appeared.
            target = fixture.home / ".omp/agent/mcp.json"
            servers = json.loads(target.read_text(encoding="utf-8"))["mcpServers"]
            self.assertEqual(len(servers), 1)
            server = next(iter(servers.values()))
            self.assertEqual(server["command"], _RUNTIME["python"])
            self.assertEqual(
                server["args"][2],
                str(
                    fixture.home
                    / ".agent/skills/sbtd-workflow-onboard/scripts/sbtd_graft_entry.py"
                ),
            )
            self.assertNotIn("cwd", server)
            self.assertNotIn("--root", server["args"])
            self.assertFalse((fixture.home / ".codex/hooks.json").exists())
            self.assertEqual(chain["verification"]["payload"]["status"], "verified")
            self.assertEqual(chain["cleanup_receipt"]["payload"]["status"], "cleaned")
            # Non-overwritten predecessor resources keep their exact bytes.
            self.assertEqual(codex_config.read_bytes(), codex_config_bytes)
            self.assertIn(
                b"<!-- graft:start -->", (fixture.root / "AGENTS.md").read_bytes()
            )
            self.assertFalse((fixture.root / ".trellis").exists())
            # Original ancestor outcomes the followup never re-declares
            # (retained assets, ignore protection) keep their exact bytes.
            for path, state in retained_snapshots.items():
                self.assertEqual(snapshot(Path(path)), state, path)
            self.assertEqual(
                (fixture.root / ".gitignore").read_bytes(), gitignore_bytes
            )
            assert_proof_intact(self, proof)

    def test_followup_accepts_direct_codex_predecessor(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(
                Path(directory).resolve(), via_successor=False
            )
            fixture.build()
            followup = fixture.plan_followup()
            payload = followup["payload"]
            self.assertEqual(
                payload["followup"]["manifest_id"], fixture.manifest["manifest_id"]
            )
            self.assertIsNone(payload.get("successor"))
            with mock.patch.dict(os.environ, fixture.environment):
                validate_legacy_inputs(followup, _reader)
            applied, code, _manifest_path = fixture.apply_followup(followup)
            self.assertEqual(code, 0, applied)
            self.assertEqual(applied["status"], "applied")

    def test_followup_overlay_preserves_user_agents_text(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            agents = fixture.root / "AGENTS.md"
            agents.write_bytes(agents.read_bytes() + b"\nUser customization\n")
            # Plan AFTER the host-side append: the sealed before-state binds
            # the live managed-section outcome, so apply and deploy accept
            # the drifted file and the render keeps fence-outside text.
            followup = fixture.plan_followup()
            applied, code, manifest_path = fixture.apply_followup(followup)
            self.assertEqual(code, 0, applied)
            receipt = applied["migration"]["apply_receipt"]
            apply_path = fixture.followup_evidence / (
                "apply-" + receipt["apply_id"] + ".json"
            )
            result, code, _path = fixture.deploy_followup(manifest_path, apply_path)
            self.assertEqual(code, 0, result)
            self.assertIn(
                "User customization", agents.read_text(encoding="utf-8")
            )

    def test_sibling_followups_share_one_predecessor(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            proof = fixture.predecessor_proof()
            v2 = fixture.plan_followup()
            applied, code, _path = fixture.apply_followup(v2, name="manifest-v2.json")
            self.assertEqual(code, 0, applied)
            v3 = fixture.plan_followup()
            self.assertNotEqual(v2["manifest_id"], v3["manifest_id"])
            for key in (
                "manifest_id",
                "apply_id",
                "deployment_id",
                "verification_id",
                "cleanup_id",
            ):
                self.assertEqual(
                    v2["payload"]["followup"][key],
                    v3["payload"]["followup"][key],
                )
            with mock.patch.dict(os.environ, fixture.environment):
                validate_legacy_inputs(v3, _reader)
            applied, code, _path = fixture.apply_followup(v3, name="manifest-v3.json")
            self.assertEqual(code, 0, applied)
            self.assertEqual(applied["status"], "applied")
            assert_proof_intact(self, proof)

    def test_followup_refreshes_the_project_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve(), git=True)
            fixture.build()
            first_head = fixture.manifest["payload"]["projects"][0]["head"]
            self.assertEqual(first_head, fixture._git("rev-parse", "HEAD"))
            fixture._git("add", "-A")
            fixture._git("commit", "-m", "post migration state")
            refreshed = fixture._git("rev-parse", "HEAD")
            self.assertNotEqual(refreshed, first_head)
            followup = fixture.plan_followup()
            project = followup["payload"]["projects"][0]
            self.assertEqual(project["source_ref"], "main")
            self.assertEqual(project["head"], refreshed)
            chain = fixture.complete_followup(followup)
            self.assertEqual(
                chain["deployment"]["payload"]["projects"][0]["head"], refreshed
            )
            self.assertEqual(chain["verification"]["payload"]["status"], "verified")

    def test_followup_retry_chain_is_cumulative_and_preserves_predecessor(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            proof = fixture.predecessor_proof()
            followup = fixture.plan_followup()
            applied, code, manifest_path = fixture.apply_followup(followup)
            self.assertEqual(code, 0, applied)
            first_receipt = applied["migration"]["apply_receipt"]
            first_apply_path = fixture.followup_evidence / (
                "apply-" + first_receipt["apply_id"] + ".json"
            )
            retried, code, _ = fixture.apply_followup(
                followup, previous_receipt_path=first_apply_path
            )
            self.assertEqual(code, 0, retried)
            self.assertEqual(retried["status"], "already-complete")
            receipt = retried["migration"]["apply_receipt"]
            self.assertEqual(
                receipt["payload"]["previous_receipt_id"],
                first_receipt["apply_id"],
            )
            apply_path = fixture.followup_evidence / (
                "apply-" + receipt["apply_id"] + ".json"
            )
            result, code, deployment_path = fixture.deploy_followup(
                manifest_path, apply_path
            )
            self.assertEqual(code, 0, result)
            self.assertEqual(result["status"], "succeeded")
            first_deployment = result["deploymentEvidence"]["evidence"]
            retried, code, retry_path = fixture.deploy_followup(
                manifest_path,
                apply_path,
                previous_path=deployment_path,
                rebuild_graph=False,
                output_name="deployment-retry.json",
            )
            self.assertEqual(code, 0, retried)
            self.assertEqual(retried["status"], "succeeded")
            second = retried["deploymentEvidence"]["evidence"]["payload"]
            self.assertEqual(
                second["previous_deployment_id"],
                first_deployment["deployment_id"],
            )
            verification_path = fixture.followup_evidence / "verification.json"
            verified, code = fixture.verify(
                manifest_path, apply_path, retry_path, verification_path
            )
            self.assertEqual(code, 0, verified)
            cleaned, code = fixture.cleanup(
                manifest_path, apply_path, retry_path, verification_path
            )
            self.assertEqual(code, 0, cleaned)
            first_cleanup = cleaned["migration"]["cleanup_receipt"]
            first_cleanup_path = fixture.followup_evidence / (
                "cleanup-" + first_cleanup["cleanup_id"] + ".json"
            )
            again, code = fixture.cleanup(
                manifest_path,
                apply_path,
                retry_path,
                verification_path,
                previous_receipt_path=first_cleanup_path,
            )
            self.assertEqual(code, 0, again)
            self.assertEqual(again["status"], "already-complete")
            self.assertEqual(
                again["migration"]["cleanup_receipt"]["payload"]["previous_receipt_id"],
                first_cleanup["cleanup_id"],
            )
            self.assertTrue((fixture.home / ".omp/agent/mcp.json").is_file())
            assert_proof_intact(self, proof)

    def test_followup_recovery_restores_before_followup_state(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            proof = fixture.predecessor_proof()
            codex_config_bytes = (fixture.home / ".codex/config.toml").read_bytes()
            chain = fixture.complete_followup()
            target = fixture.home / ".omp/agent/mcp.json"
            self.assertTrue(target.is_file())
            with mock.patch.dict(os.environ, fixture.environment):
                envelope, code = plan_recovery(
                    chain["manifest_path"],
                    apply_receipt_path=chain["apply_path"],
                    deployment_evidence_path=chain["deployment_path"],
                    cleanup_receipt_path=chain["cleanup_path"],
                )
            self.assertEqual(code, 0, envelope)
            plan = envelope["recovery"]["plan"]
            self.assertEqual(plan["payload"]["target"], "pre-apply")
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
            receipt = restored["recovery"]["receipt"]
            self.assertEqual(receipt["payload"]["status"], "restored")
            self.assertEqual(receipt["payload"]["pending_step_ids"], [])
            # Recovery goes to before-followup: OMP wiring is gone again.
            self.assertFalse(target.exists())
            # The predecessor codex deployment is not rolled back.
            self.assertEqual(
                (fixture.home / ".codex/config.toml").read_bytes(),
                codex_config_bytes,
            )
            agents = (fixture.root / "AGENTS.md").read_bytes()
            self.assertIn(b"<!-- graft:start -->", agents)
            self.assertNotIn(b"TRELLIS:START", agents)
            # The cleaned legacy tree stays cleaned; recovery is not a
            # rollback to the original legacy tree.
            self.assertFalse((fixture.root / ".trellis").exists())
            # A completed recovery retries as already-complete even though
            # the followup-created OMP directory is absent again.
            receipt_path = fixture.followup_evidence / (
                "recovery-" + receipt["receipt_id"] + ".json"
            )
            self.assertTrue(receipt_path.is_file())
            with mock.patch.dict(os.environ, fixture.environment):
                continued, code = apply_recovery(
                    plan_path,
                    previous_receipt_path=receipt_path,
                    confirm_recovery=plan["plan_id"],
                )
            self.assertEqual(code, 0, continued)
            self.assertEqual(continued["status"], "already-complete")
            self.assertFalse(target.exists())
            assert_proof_intact(self, proof)


class FollowupPredecessorGateTests(unittest.TestCase):
    def setUp(self):
        # Gate/binding invariants never depend on the full skill catalog.
        _focused_installation_templates(self)

    def test_followup_rejects_a_missing_predecessor_document(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            missing = fixture.evidence / "missing.json"
            for key in (
                "followup_manifest",
                "followup_apply_receipt",
                "followup_deployment_evidence",
                "followup_verification",
                "followup_cleanup_receipt",
            ):
                with (
                    self.subTest(missing=key),
                    self.assertRaises(ContractError) as error,
                ):
                    fixture.plan_followup(**{key: missing})
                self.assertEqual(error.exception.code, "read-failed")

    def test_followup_requires_the_complete_document_set(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            keys = (
                "followup_manifest",
                "followup_apply_receipt",
                "followup_deployment_evidence",
                "followup_verification",
                "followup_cleanup_receipt",
            )
            for dropped in keys:
                overrides = {dropped: None}
                with (
                    self.subTest(dropped=dropped),
                    self.assertRaises(ContractError) as error,
                ):
                    fixture.plan_followup(**overrides)
                self.assertEqual(error.exception.code, "invalid-argument")
            for single in keys[:2]:
                with (
                    self.subTest(single=single),
                    self.assertRaises(ContractError) as error,
                ):
                    fixture.plan_followup(
                        **{key: None for key in keys if key != single}
                    )
                self.assertEqual(error.exception.code, "invalid-argument")

    def test_followup_rejects_failed_predecessor_stages(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            cases = (
                ("followup_apply_receipt", fixture.apply_path, "apply_receipt"),
                (
                    "followup_deployment_evidence",
                    fixture.deployment_path,
                    "deployment_evidence",
                ),
                ("followup_verification", fixture.verification_path, "verification"),
                (
                    "followup_cleanup_receipt",
                    fixture.cleanup_path,
                    "cleanup_receipt",
                ),
            )
            for key, source, kind in cases:
                failed = _failed_copy(
                    source, kind, fixture.evidence / ("failed-" + kind + ".json")
                )
                with (
                    self.subTest(stage=kind),
                    self.assertRaises(ContractError) as error,
                ):
                    fixture.plan_followup(**{key: failed})
                self.assertEqual(error.exception.code, "binding-violation")

    def test_followup_rejects_forged_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            followup = fixture.plan_followup()
            forged_id = json.loads(canonical_json_bytes(followup))
            forged_id["payload"]["followup"]["cleanup_id"] = "0" * 64
            with (
                mock.patch.dict(os.environ, fixture.environment),
                self.assertRaises(ContractError) as error,
            ):
                validate_legacy_inputs(
                    contracts.seal_document("manifest", forged_id["payload"]),
                    _reader,
                )
            self.assertEqual(error.exception.code, "binding-violation")

            forged_ref = json.loads(canonical_json_bytes(followup))
            forged_ref["payload"]["followup"]["cleanup_receipt_ref"]["state"] = {
                "type": "file",
                "checksum": "0" * 64,
            }
            with (
                mock.patch.dict(os.environ, fixture.environment),
                self.assertRaises(ContractError) as error,
            ):
                validate_legacy_inputs(
                    contracts.seal_document("manifest", forged_ref["payload"]),
                    _reader,
                )
            self.assertEqual(error.exception.code, "state-conflict")

            swapped = json.loads(canonical_json_bytes(followup))
            swapped["payload"]["followup"]["cleanup_receipt_ref"] = {
                "path": str(fixture.deployment_path),
                "state": snapshot(fixture.deployment_path),
            }
            with (
                mock.patch.dict(os.environ, fixture.environment),
                self.assertRaises(ContractError),
            ):
                validate_legacy_inputs(
                    contracts.seal_document("manifest", swapped["payload"]),
                    _reader,
                )

    def test_followup_rejects_drifted_original_ancestor_outcome(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            retained = fixture.verification["payload"]["projects"][0][
                "retained_assets"
            ]
            self.assertTrue(retained)
            preserved = Path(
                next(
                    asset["path"]
                    for asset in retained
                    if asset["state"]["type"] == "directory"
                    and ".agent/skills" in asset["path"]
                )
            )
            (preserved / "junk.txt").write_bytes(b"junk\n")
            with self.assertRaises(ContractError) as error:
                fixture.plan_followup()
            self.assertEqual(error.exception.code, "state-conflict")

        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            config = fixture.home / ".codex/config.toml"
            changed = config.read_bytes().replace(b'DNT = "1"', b'DNT = "0"', 1)
            assert changed != config.read_bytes()
            config.write_bytes(changed)
            with self.assertRaises(ContractError) as error:
                fixture.plan_followup()
            self.assertEqual(error.exception.code, "state-conflict")

        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            agents = fixture.root / "AGENTS.md"
            changed = agents.read_bytes().replace(
                b"<!-- graft:start -->\n", b"<!-- graft:start -->\nedited\n", 1
            )
            assert changed != agents.read_bytes()
            agents.write_bytes(changed)
            with self.assertRaises(ContractError) as error:
                fixture.plan_followup()
            self.assertEqual(error.exception.code, "state-conflict")

        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            followup = fixture.plan_followup()
            # A predecessor document rewritten after planning fails the
            # consumer's sealed-reference revalidation before any write.
            _failed_copy(
                fixture.cleanup_path, "cleanup_receipt", fixture.cleanup_path
            )
            with self.assertRaises(ContractError) as error:
                fixture.apply_followup(followup)
            self.assertEqual(error.exception.code, "state-conflict")
            self.assertFalse((fixture.home / ".omp/agent/mcp.json").exists())

    def test_followup_rejects_foreign_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            fixture = FollowupMigration(base)
            fixture.build()
            other_project = legacy_project(base, "other")
            other_vault = base / "other-vault"
            other_vault.mkdir(mode=0o700)
            cases = [
                ([fixture.root, other_project], fixture.vault, "fixture", "scope-conflict"),
                ([fixture.root], other_vault, "fixture", "scope-conflict"),
                ([fixture.root], fixture.vault, "intruder", "approval-conflict"),
            ]
            for roots, vault, custodian, code in cases:
                with (
                    self.subTest(custodian=custodian, vault=vault.name),
                    self.assertRaises(ContractError) as error,
                ):
                    fixture.plan_followup(
                        roots=roots, vault=vault, custodian=custodian
                    )
                self.assertEqual(error.exception.code, code)

    def test_followup_rejects_invalid_request_combinations(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            cases = [
                ("other platform", {"platform": "codex"}, "invalid-argument"),
                ("project-only mode", {"mode": "init-projects"}, "invalid-argument"),
                ("missing mode", {"mode": None}, "invalid-argument"),
                ("hooks", {"hooks": True}, "scope-conflict"),
                (
                    "successor arguments",
                    {
                        "extra": {
                            "successor_manifest": fixture.manifest_path,
                            "successor_apply_receipt": fixture.apply_path,
                        }
                    },
                    "invalid-argument",
                ),
                (
                    "publication decisions",
                    {"publication": fixture.manifest_path},
                    "invalid-argument",
                ),
                (
                    "routing approvals",
                    {"extra": {"routing_approvals": fixture.manifest_path}},
                    "invalid-argument",
                ),
            ]
            for name, overrides, code in cases:
                with (
                    self.subTest(combination=name),
                    self.assertRaises(ContractError) as error,
                ):
                    fixture.plan_followup(**overrides)
                self.assertEqual(error.exception.code, code)

    def test_followup_of_followup_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            chain = fixture.complete_followup()
            with (
                mock.patch.dict(os.environ, fixture.environment),
                self.assertRaises(ContractError) as error,
            ):
                plan_migration(
                    [fixture.root],
                    fixture.vault,
                    "fixture",
                    None,
                    tool_versions=runtime_versions(),
                    deployment_mode="init",
                    deployment_platform="omp",
                    followup_manifest=chain["manifest_path"],
                    followup_apply_receipt=chain["apply_path"],
                    followup_deployment_evidence=chain["deployment_path"],
                    followup_verification=chain["verification_path"],
                    followup_cleanup_receipt=chain["cleanup_path"],
                )
            self.assertEqual(error.exception.code, "followup-conflict")

    def test_followup_rejects_a_non_codex_predecessor(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve(), platform="omp")
            fixture.build()
            with self.assertRaises(ContractError) as error:
                fixture.plan_followup()
            self.assertEqual(error.exception.code, "followup-conflict")

    def test_followup_rejects_a_deployment_less_predecessor(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            legacy = VerifiedMigration(base)
            legacy.build()
            with mock.patch.dict(os.environ, legacy.environment):
                cleaned, code = legacy.cleanup(
                    confirm_cleanup=legacy.verification["verification_id"]
                )
            if code != 0:
                raise AssertionError(f"predecessor cleanup failed: {cleaned}")
            cleanup_receipt = cleaned["migration"]["cleanup_receipt"]
            cleanup_path = legacy.evidence / (
                "cleanup-" + cleanup_receipt["cleanup_id"] + ".json"
            )
            with (
                mock.patch.dict(os.environ, legacy.environment),
                self.assertRaises(ContractError) as error,
            ):
                plan_migration(
                    [legacy.root],
                    legacy.vault,
                    "fixture-custodian",
                    None,
                    tool_versions=runtime_versions(),
                    deployment_mode="init",
                    deployment_platform="omp",
                    followup_manifest=legacy.manifest_path,
                    followup_apply_receipt=legacy.apply_path,
                    followup_deployment_evidence=legacy.deployment_path,
                    followup_verification=legacy.verification_path,
                    followup_cleanup_receipt=cleanup_path,
                )
            self.assertEqual(error.exception.code, "followup-conflict")

    def test_followup_rejects_missing_predecessor_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            backup = next(
                result["backup_ref"]
                for project in fixture.deployment["payload"]["projects"]
                for result in project["private_results"]
                if result["backup_ref"] is not None
            )
            Path(backup["path"]).unlink()
            with self.assertRaises(ContractError) as error:
                fixture.plan_followup()
            self.assertEqual(error.exception.code, "original-unavailable")


class FollowupOperationTamperingTests(unittest.TestCase):
    def setUp(self):
        # Tamper invariants need one real copy operation, not the full catalog.
        _focused_installation_templates(self)

    def test_resealed_inherited_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            followup = fixture.plan_followup()
            variants = []
            altered_vault = json.loads(canonical_json_bytes(followup))
            altered_vault["payload"]["backup_root"] = str(fixture.followup_evidence)
            variants.append(altered_vault)
            altered_custodian = json.loads(canonical_json_bytes(followup))
            altered_custodian["payload"]["custodian"] = "intruder"
            variants.append(altered_custodian)
            altered_retention = json.loads(canonical_json_bytes(followup))
            altered_retention["payload"]["retention"] = copy.deepcopy(
                altered_retention["payload"]["retention"]
            )
            altered_retention["payload"]["retention"]["normal_observation_days"] = 30
            variants.append(altered_retention)
            agents = fixture.root / "AGENTS.md"
            injected_source = json.loads(canonical_json_bytes(followup))
            injected_source["payload"]["projects"][0]["sources"] = [
                {"path": str(agents), "state": snapshot(agents)}
            ]
            variants.append(injected_source)
            for index, variant in enumerate(variants):
                with (
                    self.subTest(variant=index),
                    mock.patch.dict(os.environ, fixture.environment),
                    self.assertRaises(ContractError) as error,
                ):
                    validate_legacy_inputs(
                        contracts.seal_document("manifest", variant["payload"]),
                        _reader,
                    )
                self.assertEqual(error.exception.code, "semantic-violation")
            altered_publication = json.loads(canonical_json_bytes(followup))
            altered_publication["payload"]["publication_decisions"] = {
                "schema_version": 1,
                "items": ["not-empty"],
            }
            with (
                mock.patch.dict(os.environ, fixture.environment),
                self.assertRaises(ContractError),
            ):
                validate_legacy_inputs(
                    contracts.seal_document(
                        "manifest", altered_publication["payload"]
                    ),
                    _reader,
                )

    def test_resealed_deployment_declaration_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            followup = fixture.plan_followup()

            def variant(mutate):
                document = json.loads(canonical_json_bytes(followup))
                mutate(document["payload"])
                return contracts.seal_document("manifest", document["payload"])

            def flip_platform(payload):
                payload["deployment"]["platform"] = "codex"

            def flip_mode(payload):
                payload["deployment"]["mode"] = "init-projects"

            def inject_hooks(payload):
                mcp = next(
                    operation
                    for operation in payload["shared_operations"]
                    if operation["selector"] == "graft-omp-mcp"
                )
                mcp["selector"] = "graft-hooks"
                mcp["operation_id"] = contracts.operation_id(
                    "deploy", mcp["resource_id"], "graft-hooks"
                )
                for project in payload["projects"]:
                    project["shared_operation_ids"] = sorted(
                        mcp["operation_id"]
                        if operation_id
                        == contracts.operation_id(
                            "deploy", mcp["resource_id"], "graft-omp-mcp"
                        )
                        else operation_id
                        for operation_id in project["shared_operation_ids"]
                    )

            def flip_requirement(payload):
                operation = next(
                    operation
                    for operation in payload["shared_operations"]
                    if operation["change"]["kind"] in {"copy-file", "copy-directory"}
                )
                operation["before_requirement"] = {
                    "kind": "phase-after",
                    "phase": "apply",
                    "resource_id": operation["resource_id"],
                }

            cases = [
                ("platform", flip_platform, "semantic-violation"),
                ("mode", flip_mode, "semantic-violation"),
                ("hooks", inject_hooks, "semantic-violation"),
                ("phase-after requirement", flip_requirement, "semantic-violation"),
            ]
            for name, mutate, code in cases:
                with (
                    self.subTest(resealed=name),
                    mock.patch.dict(os.environ, fixture.environment),
                    self.assertRaises(ContractError) as error,
                ):
                    validate_legacy_inputs(variant(mutate), _reader)
                self.assertEqual(error.exception.code, code)

        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            followup = fixture.plan_followup()
            document = json.loads(canonical_json_bytes(followup))
            document["payload"]["successor"] = {
                "manifest_id": fixture.manifest["manifest_id"],
                "apply_id": fixture.apply_receipt["apply_id"],
                "manifest_ref": {
                    "path": str(fixture.manifest_path),
                    "state": snapshot(fixture.manifest_path),
                },
                "apply_receipt_ref": {
                    "path": str(fixture.apply_path),
                    "state": snapshot(fixture.apply_path),
                },
                "apply_results": [],
            }
            with self.assertRaises(ContractError):
                contracts.validate_document(document, "manifest")

    def test_resealed_generated_prestate_cannot_adopt_user_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            followup = fixture.plan_followup()
            agents = fixture.root / "AGENTS.md"
            original_agents = agents.read_bytes()
            graph_extra = fixture.root / "graft" / "unowned.txt"
            # Fence-outside drift is lawful under section ownership: the
            # resealed before-state matches the live managed-section
            # outcome, so the closure revalidation accepts it.
            payload = copy.deepcopy(followup["payload"])
            operation = next(
                item
                for item in payload["projects"][0]["private_operations"]
                if item["change"]["kind"] == "configure-graft"
            )
            try:
                agents.write_bytes(original_agents + b"\nUser customization\n")
                operation["before_requirement"] = {
                    "kind": "state",
                    "state": snapshot(agents),
                }
                resealed = contracts.seal_document("manifest", payload)
                with mock.patch.dict(os.environ, fixture.environment):
                    validate_legacy_inputs(resealed, _reader)
            finally:
                agents.write_bytes(original_agents)
            # A whole-resource graft directory still rejects adopted drift.
            payload = copy.deepcopy(followup["payload"])
            operation = next(
                item
                for item in payload["projects"][0]["private_operations"]
                if item["change"]["kind"] == "build-graft"
            )
            target = Path(operation["target"])
            try:
                graph_extra.write_bytes(b"User graph data")
                customized = snapshot(target)
                operation["before_requirement"] = {
                    "kind": "state",
                    "state": customized,
                }
                resealed = contracts.seal_document("manifest", payload)
                with self.assertRaises(ContractError) as error:
                    fixture.apply_followup(resealed)
                self.assertEqual(error.exception.code, "ownership-conflict")
                self.assertEqual(snapshot(target), customized)
            finally:
                graph_extra.unlink(missing_ok=True)

    def test_dropped_deploy_operation_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            followup = fixture.plan_followup()
            shared = followup["payload"]["shared_operations"]
            self.assertTrue(shared)
            mcp = next(
                operation
                for operation in shared
                if operation["selector"] == "graft-omp-mcp"
            )
            template = next(
                operation
                for operation in shared
                if operation["change"]["kind"] in {"copy-file", "copy-directory"}
            )
            cases = [
                ("mcp resource", mcp, "semantic-violation"),
                ("installation template", template, "semantic-violation"),
            ]
            for name, dropped, code in cases:
                payload = json.loads(canonical_json_bytes(followup))["payload"]
                payload["shared_operations"] = [
                    operation
                    for operation in payload["shared_operations"]
                    if operation["operation_id"] != dropped["operation_id"]
                ]
                for project in payload["projects"]:
                    project["shared_operation_ids"] = sorted(
                        operation_id
                        for operation_id in project["shared_operation_ids"]
                        if operation_id != dropped["operation_id"]
                    )
                resealed = contracts.seal_document("manifest", payload)
                with (
                    self.subTest(dropped=name),
                    mock.patch.dict(os.environ, fixture.environment),
                    self.assertRaises(ContractError) as error,
                ):
                    validate_legacy_inputs(resealed, _reader)
                self.assertEqual(error.exception.code, code)

    def test_tampered_followup_manifest_fails_closed_at_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = FollowupMigration(Path(directory).resolve())
            fixture.build()
            followup = fixture.plan_followup()
            payload = followup["payload"]
            dropped = next(
                operation
                for operation in payload["shared_operations"]
                if operation["change"]["kind"] in {"copy-file", "copy-directory"}
            )
            payload["shared_operations"] = [
                operation
                for operation in payload["shared_operations"]
                if operation["operation_id"] != dropped["operation_id"]
            ]
            for project in payload["projects"]:
                project["shared_operation_ids"] = sorted(
                    operation_id
                    for operation_id in project["shared_operation_ids"]
                    if operation_id != dropped["operation_id"]
                )
            resealed = contracts.seal_document("manifest", payload)
            before = _tree_bytes(fixture.root)
            with self.assertRaises(ContractError) as error:
                fixture.apply_followup(resealed)
            self.assertEqual(error.exception.code, "semantic-violation")
            self.assertEqual(_tree_bytes(fixture.root), before)
            self.assertFalse((fixture.home / ".omp/agent/mcp.json").exists())


if __name__ == "__main__":
    unittest.main()
