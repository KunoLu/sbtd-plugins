from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import onboard_contracts as contracts
import sbtd_migration_plan
from onboard_contracts import ContractError
from sbtd_migration_files import read_file, snapshot
from sbtd_migration_plan import plan_migration, validate_legacy_inputs

from tests.test_sbtd_migration_apply import legacy_project
from tests.test_sbtd_migration_legacy import (
    BLOCKED_EVENT,
    CANCELLED_EVENT,
    NO_RECORDED_REASON,
    _json_bytes,
    _legacy_source,
    _sidecar,
    _task_md,
)

_TEST_APPROVAL_KEY = None
_APPROVAL_KEY_PATCH = None


def setUpModule():
    global _TEST_APPROVAL_KEY, _APPROVAL_KEY_PATCH
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    _TEST_APPROVAL_KEY = Ed25519PrivateKey.generate()
    _APPROVAL_KEY_PATCH = mock.patch(
        "sbtd_migration_plan._routing_approval_public_key",
        return_value=_TEST_APPROVAL_KEY.public_key(),
    )
    _APPROVAL_KEY_PATCH.start()


def tearDownModule():
    if _APPROVAL_KEY_PATCH is not None:
        _APPROVAL_KEY_PATCH.stop()


def _sign_existing_approval(path, private_key=None):
    document = json.loads(path.read_bytes())
    payload = contracts.canonical_json_bytes(
        {"schema_version": document["schema_version"], "items": document["items"]}
    )
    signer = _TEST_APPROVAL_KEY if private_key is None else private_key
    document["signature"] = base64.b64encode(signer.sign(payload)).decode("ascii")
    path.write_bytes(json.dumps(document).encode("utf-8"))
    return path



class MigrationPlanTests(unittest.TestCase):
    def test_omp_home_child_link_does_not_block_the_existence_check(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            omp = home / ".omp"
            (omp / "agent").mkdir(parents=True)
            target = base / "elsewhere"
            target.write_text("unrelated")
            link = omp / "unrelated"
            link.symlink_to(target)
            project = base / "project"
            project.mkdir()
            with (
                _home_env(home),
                mock.patch("onboard.user_home", return_value=home),
            ):
                roots, operations = sbtd_migration_plan._shared_operations([project])
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.read_text(), "unrelated")
            self.assertFalse(any(record["kind"] == "omp-home" for record in roots))
            self.assertFalse(
                any("pause-legacy-routing" == op["selector"] for op in operations)
            )

    def test_omp_home_symlink_root_is_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            real = base / "real"
            (real / "agent").mkdir(parents=True)
            (real / "agent" / "AGENTS.md").write_text("trellis pin must not be read")
            home = base / "home"
            home.mkdir()
            (home / ".omp").symlink_to(real, target_is_directory=True)
            project = base / "project"
            project.mkdir()
            with (
                _home_env(home),
                mock.patch("onboard.user_home", return_value=home),
                self.assertRaises(ContractError) as caught,
            ):
                sbtd_migration_plan._shared_operations([project])
            self.assertEqual(
                caught.exception.message,
                "migration paths do not follow symbolic or reparse links",
            )
            self.assertEqual(
                (real / "agent" / "AGENTS.md").read_text(),
                "trellis pin must not be read",
            )

    def test_omp_root_presence_rejects_a_symlink_parent_without_following(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            physical = base / "physical"
            (physical / ".omp" / "agent").mkdir(parents=True)
            agents = physical / ".omp" / "agent" / "AGENTS.md"
            agents.write_text("trellis behind a parent link")
            home = base / "home"
            home.symlink_to(physical, target_is_directory=True)
            with self.assertRaises(ContractError) as caught:
                sbtd_migration_plan._omp_root_presence(home / ".omp")
            self.assertEqual(
                caught.exception.message,
                "migration paths do not follow symbolic or reparse links",
            )
            self.assertEqual(agents.read_text(), "trellis behind a parent link")
            self.assertTrue(home.is_symlink())


    def test_omp_home_file_root_is_not_a_safe_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            home.mkdir()
            (home / ".omp").write_text("not a directory")
            project = base / "project"
            project.mkdir()
            with (
                _home_env(home),
                mock.patch("onboard.user_home", return_value=home),
                self.assertRaises(ContractError) as caught,
            ):
                sbtd_migration_plan._shared_operations([project])
            self.assertEqual(
                caught.exception.message,
                "the existing OMP root is not a safe directory",
            )

    def test_planning_legacy_identity_is_read_only_and_has_no_global_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = base / "project"
            (project / ".trellis").mkdir(parents=True)
            (project / ".codex/agents").mkdir(parents=True)
            legacy = b"name=dev01\ninitialized_at=2026-09-01T12:00:00\n"
            (project / ".trellis/.developer").write_bytes(legacy)
            owned = b'name = "trellis-implement"\n'
            relative = ".codex/agents/trellis-implement.toml"
            (project / relative).write_bytes(owned)
            (project / ".trellis/.template-hashes.json").write_text(
                json.dumps(
                    {
                        "__version": 2,
                        "hashes": {relative: hashlib.sha256(owned).hexdigest()},
                    }
                )
            )
            (project / ".trellis/.version").write_text("0.6.17\n")
            home = base / "home"
            home.mkdir(mode=0o700)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            before = {
                str(path.relative_to(base)): path.read_bytes()
                for path in base.rglob("*")
                if path.is_file()
            }
            with mock.patch.dict(
                os.environ,
                {
                    "HOME": str(home),
                    "USERPROFILE": str(home),
                    "CODEX_HOME": str(home / ".codex"),
                    "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
                },
            ):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    None,
                    tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                )
                with self.assertRaises(ContractError):
                    plan_migration(
                        [project],
                        base / "missing-vault",
                        "fixture-custodian",
                        None,
                        tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                    )
            operations = manifest["payload"]["projects"][0]["private_operations"]
            identities = [
                operation
                for operation in operations
                if operation["change"]["kind"] == "migrate-developer"
            ]
            self.assertEqual(
                [operation["target"] for operation in identities],
                [str(project / ".sbtd/developer")],
            )
            self.assertEqual(
                {
                    str(path.relative_to(base)): path.read_bytes()
                    for path in base.rglob("*")
                    if path.is_file()
                },
                before,
            )
            self.assertFalse((project / ".sbtd").exists())
            self.assertEqual(list(vault.iterdir()), [])
            self.assertFalse((base / "missing-vault").exists())
            self.assertEqual(list(home.iterdir()), [])


LEGACY_IDENTITY = b"name=dev01\ninitialized_at=2026-09-01T12:00:00\n"
PLATFORM_TOML = b'name = "trellis-implement"\n'
PLATFORM_REL = ".codex/agents/trellis-implement.toml"
LESSON_BODY = (
    b"<!-- lessons:index -->\nlesson body references LESSON-20260901-a1b2-topic\n"
)
SPEC_BODY = b"# spec\n\napproved spec content\n"


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _ref(path):
    return {"path": str(path), "state": snapshot(path)}


def _home_env(home):
    return mock.patch.dict(
        os.environ,
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "CODEX_HOME": str(home / ".codex"),
            "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
        },
    )


def _base_tree(base, *, identity=True, version=b"0.6.17\n"):
    project = base / "project"
    _write(project / PLATFORM_REL, PLATFORM_TOML)
    _write(
        project / ".trellis/.template-hashes.json",
        _json_bytes(
            {
                "__version": 2,
                "hashes": {PLATFORM_REL: hashlib.sha256(PLATFORM_TOML).hexdigest()},
            }
        ),
    )
    if version is not None:
        _write(project / ".trellis/.version", version)
    if identity:
        _write(project / ".trellis/.developer", LEGACY_IDENTITY)
    return project

def _no_host_tree(base, *, version=b"0.6.17\n", with_marker=True):
    """Legacy project whose ownership metadata claims no host platform file."""
    project = base / "project"
    agents_md = b"Foreign project rule.\n"
    if with_marker:
        agents_md += b"<!-- TRELLIS:START -->\nLegacy route.\n<!-- TRELLIS:END -->\n"
    _write(project / "AGENTS.md", agents_md)
    hashes = {}
    if with_marker:
        hashes["AGENTS.md"] = hashlib.sha256(agents_md).hexdigest()
    generated = {
        ".trellis/workflow.md": b"# generated workflow\n",
        ".trellis/config.yaml": b"workflow: native\n",
        ".trellis/scripts/task.py": b"# generated legacy entrypoint\n",
        ".trellis/agents/implement.md": b"# generated agent\n",
    }
    for relative, raw in generated.items():
        _write(project / relative, raw)
        hashes[relative] = hashlib.sha256(raw).hexdigest()
    _write(
        project / ".trellis/.template-hashes.json",
        _json_bytes({"__version": 2, "hashes": hashes}),
    )
    _write(project / ".trellis/.version", version)
    _write(project / ".trellis/.developer", LEGACY_IDENTITY)
    return project


def _item(item_id, sources, target_path, decision, candidate_path, *, required=True):
    candidate = _ref(candidate_path) if candidate_path is not None else None
    scope = {
        "sources": [dict(reference) for reference in sources],
        "target_path": str(target_path) if target_path is not None else None,
        "decision": decision,
        "candidate_ref": candidate,
    }
    return {
        "item_id": item_id,
        "sources": [dict(reference) for reference in sources],
        "target_path": scope["target_path"],
        "required": required,
        "decision": decision,
        "candidate_ref": candidate,
        "approval": {"basis": "fixture custodian approval", "scope": scope},
    }


def _decisions(vault, items):
    path = vault / "decisions.json"
    path.write_bytes(json.dumps({"schema_version": 1, "items": items}).encode("utf-8"))
    return path


def _add_task(
    project,
    vault,
    items,
    *,
    task_id="alpha",
    folder="09-01-alpha",
    decision="share",
    source_overrides=None,
    task_md_kwargs=None,
    sidecar_kwargs=None,
    with_attachment=False,
):
    source = _legacy_source(id=task_id, name=task_id, **(source_overrides or {}))
    source["id"] = task_id
    source["name"] = task_id
    source_raw = _json_bytes(source)
    folder_path = project / ".trellis/tasks" / folder
    _write(folder_path / "task.json", source_raw)
    source_rel = f".trellis/tasks/{folder}/task.json"
    candidate = vault / f"cand-{folder}"
    target_dir = project / "ai/tasks" / task_id
    document_kwargs = {"identity": task_id}
    document_kwargs.update(task_md_kwargs or {})
    _write(candidate / "task.md", _task_md(**document_kwargs))
    sidecar_options = {"source_path": source_rel}
    sidecar_options.update(sidecar_kwargs or {})
    _write(candidate / "legacy-task.json", _sidecar(source_raw, **sidecar_options))
    source_reference = _ref(folder_path / "task.json")
    items.append(
        _item(
            folder + "-document",
            [source_reference],
            target_dir / "task.md",
            decision,
            candidate / "task.md",
        )
    )
    items.append(
        _item(
            folder + "-sidecar",
            [source_reference],
            target_dir / "legacy-task.json",
            decision,
            candidate / "legacy-task.json",
        )
    )
    if with_attachment:
        _write(folder_path / "prd.md", b"# legacy prd\n")
        _write(candidate / "prd.md", b"# legacy prd\n")
        items.append(
            _item(
                folder + "-prd",
                [_ref(folder_path / "prd.md")],
                target_dir / "prd.md",
                decision,
                candidate / "prd.md",
            )
        )
    return source_raw


def _add_spec(project, vault, items, *, body=SPEC_BODY, candidate_body=None):
    _write(project / ".trellis/spec/auth.md", body)
    _write(
        vault / "cand-spec/auth.md", body if candidate_body is None else candidate_body
    )
    items.append(
        _item(
            "spec-auth",
            [_ref(project / ".trellis/spec/auth.md")],
            project / "docs/spec/auth.md",
            "share",
            vault / "cand-spec/auth.md",
        )
    )


def _add_lessons_tree(project, vault, items, *, candidate_body=None):
    nested = b"topic note\n"
    _write(project / ".trellis/lessons/index.md", LESSON_BODY)
    _write(project / ".trellis/lessons/topics/x.md", nested)
    _write(
        vault / "cand-lessons/index.md",
        LESSON_BODY if candidate_body is None else candidate_body,
    )
    _write(vault / "cand-lessons/topics/x.md", nested)
    items.append(
        _item(
            "lessons-tree",
            [
                _ref(project / ".trellis/lessons/index.md"),
                _ref(project / ".trellis/lessons/topics/x.md"),
            ],
            project / "docs/lessons",
            "share",
            vault / "cand-lessons",
        )
    )


def _full_fixture(base, *, version=b"0.6.17\n"):
    """Approved project with task closure (file form), spec and lessons tree."""
    project = _base_tree(base, version=version)
    vault = base / "vault"
    vault.mkdir(mode=0o700)
    home = base / "home"
    home.mkdir(mode=0o700)
    items = []
    _add_task(project, vault, items, with_attachment=True)
    _add_spec(project, vault, items)
    _add_lessons_tree(project, vault, items)
    decisions = _decisions(vault, items)
    return project, vault, home, decisions


def _tree_bytes(base):
    return {
        str(path.relative_to(base)): path.read_bytes()
        for path in base.rglob("*")
        if path.is_file()
    }


def _plan(project, vault, decisions, home, roots=None):
    with _home_env(home):
        return plan_migration(
            roots or [project],
            vault,
            "fixture-custodian",
            decisions,
            tool_versions={"onboard": "fixture", "graft": "0.18.0"},
        )


def _reader(reference):
    return Path(reference["path"]).read_bytes()


class MigrationPlanReviewRegressions(unittest.TestCase):
    def test_generated_legacy_tree_is_preserved_until_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            home = base / "home"
            home.mkdir(mode=0o700)
            hashes_path = project / ".trellis/.template-hashes.json"
            metadata = json.loads(hashes_path.read_text())
            generated = {
                ".trellis/config.yaml": b"workflow: native\n",
                ".trellis/scripts/task.py": b"# generated legacy entrypoint\n",
                ".trellis/agents/implement.md": b"# generated agent\n",
                ".agents/skills/start/SKILL.md": b"# generated Codex skill\n",
            }
            for relative, raw in generated.items():
                _write(project / relative, raw)
                metadata["hashes"][relative] = hashlib.sha256(raw).hexdigest()
            hashes_path.write_bytes(_json_bytes(metadata))
            _write(project / ".trellis/.gitignore", b"workspace/\n")
            _write(project / ".trellis/.current-task", b"")
            _write(project / ".trellis/tasks/.gitkeep", b"")
            before = _tree_bytes(base)
            manifest = _plan(project, vault, None, home)
            with _home_env(home):
                validate_legacy_inputs(manifest, _reader)
            apply_targets = {
                operation["target"]
                for operation in manifest["payload"]["projects"][0][
                    "private_operations"
                ]
                if operation["phase"] == "apply"
            }
            self.assertIn(str(project / ".agents/skills/start/SKILL.md"), apply_targets)
            self.assertFalse(
                any(
                    Path(target).is_relative_to(project / ".trellis")
                    for target in apply_targets
                )
            )
            self.assertEqual(_tree_bytes(base), before)

    def test_share_cannot_rewrite_directly_copied_members(self):
        for member, item_id in (
            ("cand-spec/auth.md", "spec-auth"),
            ("cand-lessons/topics/x.md", "lessons-tree"),
            ("cand-09-01-alpha/prd.md", "09-01-alpha-prd"),
        ):
            with (
                self.subTest(member=member),
                tempfile.TemporaryDirectory() as directory,
            ):
                base = Path(directory).resolve()
                project, vault, home, decisions = _full_fixture(base)
                (vault / member).write_bytes(b"unapproved replacement\n")
                items = json.loads(decisions.read_text())["items"]
                item = next(item for item in items if item["item_id"] == item_id)
                item["candidate_ref"] = _ref(Path(item["candidate_ref"]["path"]))
                item["approval"]["scope"]["candidate_ref"] = item["candidate_ref"]
                _decisions(vault, items)
                before = _tree_bytes(base)
                with self.assertRaises(ContractError):
                    _plan(project, vault, decisions, home)
                self.assertEqual(_tree_bytes(base), before)

    def test_customized_legacy_global_routing_blocks_without_touching_foreign_text(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            home = base / "home"
            home.mkdir(mode=0o700)
            _write(
                home / ".codex/AGENTS.md",
                b"Use trellis-workflow for every task.\n\n# Foreign user rules\nKeep these.\n",
            )
            before = _tree_bytes(base)
            with self.assertRaises(ContractError):
                _plan(project, vault, None, home)
            self.assertEqual(_tree_bytes(base), before)

    def test_recorded_hash_cannot_claim_foreign_shared_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            home = base / "home"
            home.mkdir(mode=0o700)
            relative = ".codex/config.toml"
            foreign = b'model = "user-choice"\n\n[agents]\nmax_depth = 1\n'
            _write(project / relative, foreign)
            metadata_path = project / ".trellis/.template-hashes.json"
            metadata = json.loads(metadata_path.read_text())
            metadata["hashes"][relative] = hashlib.sha256(foreign).hexdigest()
            metadata_path.write_bytes(_json_bytes(metadata))
            before = _tree_bytes(base)
            with self.assertRaises(ContractError):
                _plan(project, vault, None, home)
            self.assertEqual(_tree_bytes(base), before)


class MigrationWorkflowOwnershipTests(unittest.TestCase):
    def test_unowned_workflow_requires_explicit_private_only_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            project, vault, home, decisions = _full_fixture(Path(directory).resolve())
            workflow = project / ".trellis/workflow.md"
            workflow.write_bytes(b"# Custom workflow\nPreserve this user policy.\n")
            before = _tree_bytes(project)
            with self.assertRaises(ContractError):
                _plan(project, vault, decisions, home)
            self.assertEqual(_tree_bytes(project), before)
            items = json.loads(decisions.read_text())["items"]
            items.append(
                _item(
                    "custom-workflow",
                    [_ref(workflow)],
                    None,
                    "private-only",
                    None,
                    required=False,
                )
            )
            _decisions(vault, items)
            manifest = _plan(project, vault, decisions, home)
            with _home_env(home):
                validate_legacy_inputs(manifest, _reader)
            self.assertEqual(_tree_bytes(project), before)
            self.assertEqual(
                manifest["payload"]["projects"][0]["sources"][0]["state"],
                snapshot(project / ".trellis"),
            )

    def test_resealed_manifest_cannot_drop_custom_workflow_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            project, vault, home, decisions = _full_fixture(Path(directory).resolve())
            workflow = project / ".trellis/workflow.md"
            workflow.write_bytes(b"# Custom workflow\nPreserve this user policy.\n")
            items = json.loads(decisions.read_text())["items"]
            items.append(
                _item(
                    "custom-workflow",
                    [_ref(workflow)],
                    None,
                    "private-only",
                    None,
                    required=False,
                )
            )
            _decisions(vault, items)
            manifest = _plan(project, vault, decisions, home)
            payload = json.loads(json.dumps(manifest["payload"]))
            payload["publication_decisions"]["items"] = [
                item
                for item in payload["publication_decisions"]["items"]
                if item["item_id"] != "custom-workflow"
            ]
            changed = contracts.seal_document("manifest", payload)
            before = _tree_bytes(project)
            with _home_env(home), self.assertRaises(ContractError):
                validate_legacy_inputs(changed, _reader)
            self.assertEqual(_tree_bytes(project), before)

    def test_original_inventory_uses_only_an_exact_private_backup(self):
        from sbtd_migration import _backup_sources, _source_backup_paths

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)
            source_root = project / ".trellis"
            workflow = source_root / "workflow.md"
            workflow.write_bytes(b"# Custom workflow\nPreserve this user policy.\n")
            (source_root / "tasks/.gitkeep").write_bytes(b"")
            items = json.loads(decisions.read_text())["items"]
            items.append(
                _item(
                    "custom-workflow",
                    [_ref(workflow)],
                    None,
                    "private-only",
                    None,
                    required=False,
                )
            )
            _decisions(vault, items)
            manifest = _plan(project, vault, decisions, home)
            backup = _source_backup_paths(manifest)[str(source_root)]
            with _home_env(home):
                _backup_sources(manifest)
                source_root.rename(base / "retired-source")

                def original(reference):
                    path = Path(reference["path"])
                    if path.is_relative_to(source_root):
                        path = backup / path.relative_to(source_root)
                    return read_file(path, reference["state"])

                before = snapshot(base)
                validate_legacy_inputs(manifest, original)
                self.assertEqual(snapshot(base), before)
                (backup / "workflow.md").write_bytes(b"changed private original\n")
                with self.assertRaises(ContractError):
                    validate_legacy_inputs(manifest, original)
                self.assertEqual(
                    (base / "retired-source/workflow.md").read_bytes(),
                    b"# Custom workflow\nPreserve this user policy.\n",
                )


class MigrationPlanLegacyCompatibilityTests(unittest.TestCase):
    """v2 legacy compatibility through public plan/validate consumer seams."""

    def test_root_without_host_platform_plans_empty_platforms(self):
        from sbtd_migration import _backup_sources, _source_backup_paths

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _no_host_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            source_root = project / ".trellis"
            before = _tree_bytes(base)
            manifest = _plan(project, vault, None, home)
            self.assertEqual(_tree_bytes(base), before)
            record = manifest["payload"]["projects"][0]
            self.assertEqual(record["platforms"], [])
            operations = record["private_operations"]
            self.assertFalse(
                any(
                    Path(operation["target"]).is_relative_to(project / prefix)
                    for operation in operations
                    for prefix in (".codex", ".claude", ".kimi", ".omp")
                )
            )
            markers = [
                operation
                for operation in operations
                if operation["ownership"]["kind"] == "managed-marker"
            ]
            self.assertEqual(
                [
                    (operation["target"], operation["change"]["kind"])
                    for operation in markers
                ],
                [(str(project / "AGENTS.md"), "remove")],
            )
            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, _reader))
                backup = _source_backup_paths(manifest)[str(source_root)]
                _backup_sources(manifest)
                source_root.rename(base / "retired-source")

                def original(reference):
                    path = Path(reference["path"])
                    if path.is_relative_to(source_root):
                        path = backup / path.relative_to(source_root)
                    return read_file(path, reference["state"])

                unchanged = snapshot(base)
                self.assertIsNone(validate_legacy_inputs(manifest, original))
                self.assertEqual(snapshot(base), unchanged)

    def test_empty_platform_cannot_hide_missing_marker_retirement(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _no_host_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            manifest = _plan(project, vault, None, home)
            payload = json.loads(json.dumps(manifest["payload"]))
            record = payload["projects"][0]
            record["private_operations"] = [
                operation for operation in record["private_operations"]
                if operation["selector"] != "trellis-block"
            ]
            altered = contracts.seal_document("manifest", payload)
            before = _tree_bytes(base)
            with _home_env(home), self.assertRaises(ContractError) as caught:
                validate_legacy_inputs(altered, _reader)
            self.assertEqual(caught.exception.code, "semantic-violation")
            self.assertEqual(_tree_bytes(base), before)

    def test_host_root_appearing_after_empty_platform_plan_blocks_apply(self):
        from sbtd_migration import apply_migration, runtime_versions

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _no_host_tree(base, with_marker=False)
            vault, home, evidence = base / "vault", base / "home", base / "evidence"
            for path in (vault, home, evidence):
                path.mkdir(mode=0o700)
            with _home_env(home):
                manifest = plan_migration(
                    [project], vault, "fixture-custodian", None,
                    tool_versions=runtime_versions(),
                )
                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(contracts.canonical_json_bytes(manifest))
                _write(project / ".omp/extensions/foreign.ts", b"// user extension\n")
                before = _tree_bytes(base)
                with self.assertRaises(ContractError) as caught:
                    apply_migration(
                        manifest_path, confirmed=True, no_routing_approvals=True
                    )
            self.assertEqual(
                caught.exception.code, "unknown-platform", str(caught.exception)
            )
            self.assertEqual(_tree_bytes(base), before)

    def test_empty_platform_manifest_survives_apply_rederivation(self):
        from sbtd_migration import apply_migration, runtime_versions

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _no_host_tree(base, with_marker=False)
            vault, home, evidence = base / "vault", base / "home", base / "evidence"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            evidence.mkdir(mode=0o700)
            with _home_env(home):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    None,
                    tool_versions=runtime_versions(),
                )
                record = manifest["payload"]["projects"][0]
                self.assertEqual(record["platforms"], [])
                targets = {
                    operation["target"]
                    for operation in record["private_operations"]
                }
                self.assertNotIn(str(project / "AGENTS.md"), targets)
                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(contracts.canonical_json_bytes(manifest))
                applied, code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
                self.assertEqual(code, 0, applied)
                self.assertEqual(applied["status"], "applied")
                saved = (
                    evidence
                    / f"apply-{applied['migration']['apply_receipt']['apply_id']}.json"
                )
                before_retry = (
                    _tree_bytes(project), _tree_bytes(vault), saved.read_bytes()
                )
                repeated, code = apply_migration(
                    manifest_path,
                    previous_receipt_path=saved,
                    confirmed=True,
                    no_routing_approvals=True,
                )
                self.assertEqual(code, 0, repeated)
                self.assertEqual(repeated["status"], "already-complete")
                self.assertEqual(
                    (_tree_bytes(project), _tree_bytes(vault), saved.read_bytes()),
                    before_retry,
                )
            self.assertEqual((project / "AGENTS.md").read_bytes(), b"Foreign project rule.\n")
            self.assertTrue((project / ".trellis").is_dir())

    def test_unclaimed_host_root_is_not_absence(self):
        for host_file in (
            ".claude/commands/trellis/continue.md",
            ".cursor/rules/trellis.mdc",
        ):
            with (
                self.subTest(host_file=host_file),
                tempfile.TemporaryDirectory() as directory,
            ):
                base = Path(directory).resolve()
                project = _no_host_tree(base)
                _write(project / host_file, b"# unclaimed host integration\n")
                vault, home = base / "vault", base / "home"
                vault.mkdir(mode=0o700)
                home.mkdir(mode=0o700)
                before = _tree_bytes(base)
                with self.assertRaises(ContractError) as caught:
                    _plan(project, vault, None, home)
                self.assertEqual(caught.exception.code, "unknown-platform")
                self.assertEqual(_tree_bytes(base), before)

    def test_unclaimed_host_root_is_rejected_without_reading_its_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _no_host_tree(base)
            host_root = project / ".claude"
            host_root.mkdir()
            outside = base / "unselected.txt"
            outside.write_bytes(b"unselected fixture content\n")
            try:
                (host_root / "foreign-link").symlink_to(outside)
            except OSError:
                self.skipTest("symlinks unavailable")
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            with self.assertRaises(ContractError) as caught:
                _plan(project, vault, None, home)
            self.assertEqual(caught.exception.code, "unknown-platform")
            self.assertEqual(outside.read_bytes(), b"unselected fixture content\n")

    def test_legacy_0_6_15_shape_plans_and_revalidates_after_retirement(self):
        from sbtd_migration import _backup_sources, _source_backup_paths

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base, version=b"0.6.15\n")
            metadata_path = project / ".trellis/.template-hashes.json"
            metadata = json.loads(metadata_path.read_text())
            generated = {
                ".trellis/workflow.md": b"# generated workflow\n",
                ".trellis/config.yaml": b"workflow: native\n",
                ".trellis/scripts/task.py": b"# generated legacy entrypoint\n",
                ".trellis/agents/implement.md": b"# generated agent\n",
            }
            for relative, raw in generated.items():
                _write(project / relative, raw)
                metadata["hashes"][relative] = hashlib.sha256(raw).hexdigest()
            marker = project / ".trellis/.runtime/update-check-fixture.marker"
            _write(marker, b"update probe junk\n")
            metadata["hashes"][".trellis/lessons/index.md"] = hashlib.sha256(
                LESSON_BODY
            ).hexdigest()
            metadata["hashes"][".trellis/lessons/topics/x.md"] = hashlib.sha256(
                b"topic note\n"
            ).hexdigest()
            metadata["hashes"][
                ".trellis/.runtime/update-check-fixture.marker"
            ] = hashlib.sha256(b"update probe junk\n").hexdigest()
            metadata["hashes"][".trellis/.DS_Store"] = hashlib.sha256(
                b"\x00binary junk\xff"
            ).hexdigest()
            metadata_path.write_bytes(_json_bytes(metadata))
            metadata_raw = metadata_path.read_bytes()
            items = json.loads(decisions.read_text())["items"]
            items.append(
                _item(
                    "runtime-marker",
                    [_ref(marker)],
                    None,
                    "private-only",
                    None,
                    required=False,
                )
            )
            decisions = _decisions(vault, items)
            source_root = project / ".trellis"
            before = _tree_bytes(base)
            manifest = _plan(project, vault, decisions, home)
            self.assertEqual(_tree_bytes(base), before)
            record = manifest["payload"]["projects"][0]
            self.assertEqual(record["platforms"], ["codex"])
            targets = {
                operation["target"] for operation in record["private_operations"]
            }
            self.assertTrue(
                {
                    str(marker),
                    str(project / ".trellis/lessons/index.md"),
                    str(project / ".trellis/lessons/topics/x.md"),
                }.isdisjoint(targets)
            )
            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, _reader))
                backup = _source_backup_paths(manifest)[str(source_root)]
                _backup_sources(manifest)
                source_root.rename(base / "retired-source")

                def original(reference):
                    path = Path(reference["path"])
                    if path.is_relative_to(source_root):
                        path = backup / path.relative_to(source_root)
                    return read_file(path, reference["state"])

                unchanged = snapshot(base)
                self.assertIsNone(validate_legacy_inputs(manifest, original))
                self.assertEqual(snapshot(base), unchanged)
            self.assertEqual(
                (base / "retired-source/.template-hashes.json").read_bytes(),
                metadata_raw,
            )

    def test_unknown_or_missing_legacy_version_still_rejects(self):
        for version in (b"0.6.16\n", b"0.6.15-dirty\n", None):
            with (
                self.subTest(version=version),
                tempfile.TemporaryDirectory() as directory,
            ):
                base = Path(directory).resolve()
                project = _base_tree(base, version=version)
                vault, home = base / "vault", base / "home"
                vault.mkdir(mode=0o700)
                home.mkdir(mode=0o700)
                before = _tree_bytes(base)
                with self.assertRaises(ContractError) as caught:
                    _plan(project, vault, None, home)
                self.assertEqual(caught.exception.code, "unsupported-version")
                self.assertEqual(_tree_bytes(base), before)

    def test_legacy_0_6_15_metadata_claims_do_not_authorize_or_exempt(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base, version=b"0.6.15\n")
            metadata_path = project / ".trellis/.template-hashes.json"
            metadata = json.loads(metadata_path.read_text())
            stale = hashlib.sha256(b"stale recorded bytes\n").hexdigest()
            marker = project / ".trellis/.runtime/update-check-fixture.marker"
            _write(marker, b"update probe junk\n")
            for relative in (
                ".trellis/lessons/index.md",
                ".trellis/lessons/topics/x.md",
                ".trellis/.runtime/update-check-fixture.marker",
                ".trellis/.DS_Store",
            ):
                metadata["hashes"][relative] = stale
            metadata_path.write_bytes(_json_bytes(metadata))
            items = json.loads(decisions.read_text())["items"]
            items.append(
                _item(
                    "runtime-marker",
                    [_ref(marker)],
                    None,
                    "private-only",
                    None,
                    required=False,
                )
            )
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            manifest = _plan(project, vault, decisions, home)
            record = manifest["payload"]["projects"][0]
            operations = record["private_operations"]
            targets = {operation["target"] for operation in operations}
            self.assertTrue(
                {
                    str(project / ".trellis/lessons/index.md"),
                    str(project / ".trellis/lessons/topics/x.md"),
                    str(marker),
                }.isdisjoint(targets)
            )
            apply_removals = {
                operation["target"]
                for operation in operations
                if operation["phase"] == "apply"
                and operation["change"]["kind"] == "remove"
            }
            self.assertEqual(apply_removals, {str(project / PLATFORM_REL)})
            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, _reader))
            self.assertEqual(_tree_bytes(base), before)
            # A recorded claim never exempts the lessons publication closure.
            skipped = [item for item in items if item["item_id"] != "lessons-tree"]
            project_before = _tree_bytes(project)
            with self.assertRaises(ContractError) as caught:
                _plan(project, vault, _decisions(vault, skipped), home)
            self.assertEqual(caught.exception.code, "approval-required")
            self.assertEqual(_tree_bytes(project), project_before)

    def test_legacy_0_6_15_runtime_context_still_needs_private_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base, version=b"0.6.15\n")
            metadata_path = project / ".trellis/.template-hashes.json"
            metadata = json.loads(metadata_path.read_text())
            marker = project / ".trellis/.runtime/update-check-fixture.marker"
            _write(marker, b"update probe junk\n")
            metadata["hashes"][
                ".trellis/.runtime/update-check-fixture.marker"
            ] = hashlib.sha256(b"update probe junk\n").hexdigest()
            metadata_path.write_bytes(_json_bytes(metadata))
            before = _tree_bytes(base)
            with self.assertRaises(ContractError) as caught:
                _plan(project, vault, decisions, home)
            self.assertEqual(caught.exception.code, "approval-required")
            self.assertEqual(_tree_bytes(base), before)

    def test_legacy_0_6_15_generated_drift_still_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base, version=b"0.6.15\n")
            _write(project / ".trellis/config.yaml", b"workflow: native\n")
            metadata_path = project / ".trellis/.template-hashes.json"
            metadata = json.loads(metadata_path.read_text())
            metadata["hashes"][".trellis/config.yaml"] = hashlib.sha256(
                b"workflow: older\n"
            ).hexdigest()
            metadata_path.write_bytes(_json_bytes(metadata))
            before = _tree_bytes(base)
            with self.assertRaises(ContractError) as caught:
                _plan(project, vault, decisions, home)
            self.assertEqual(caught.exception.code, "ownership-conflict")
            self.assertEqual(_tree_bytes(base), before)

    def test_legacy_0_6_17_metadata_contract_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)
            metadata_path = project / ".trellis/.template-hashes.json"
            metadata = json.loads(metadata_path.read_text())
            index = project / ".trellis/lessons/index.md"
            metadata["hashes"][".trellis/lessons/index.md"] = hashlib.sha256(
                index.read_bytes()
            ).hexdigest()
            metadata_path.write_bytes(_json_bytes(metadata))
            before = _tree_bytes(base)
            with self.assertRaises(ContractError) as caught:
                _plan(project, vault, decisions, home)
            self.assertEqual(caught.exception.code, "invalid-config")
            self.assertEqual(_tree_bytes(base), before)

    def test_legacy_0_6_15_malicious_claims_and_shared_config_still_reject(self):
        cases = (
            (".trellis/spec/auth.md", "invalid-config"),
            (".trellis/tasks/09-01-alpha/task.json", "invalid-config"),
            (".trellis/workspace/journal.md", "invalid-config"),
            (".trellis/.developer", "invalid-config"),
            ("../outside.md", "invalid-config"),
            (".claude/settings.json", "ownership-conflict"),
        )
        for relative, code in cases:
            with (
                self.subTest(relative=relative),
                tempfile.TemporaryDirectory() as directory,
            ):
                base = Path(directory).resolve()
                project = _base_tree(base, version=b"0.6.15\n")
                vault, home = base / "vault", base / "home"
                vault.mkdir(mode=0o700)
                home.mkdir(mode=0o700)
                metadata_path = project / ".trellis/.template-hashes.json"
                metadata = json.loads(metadata_path.read_text())
                metadata["hashes"][relative] = hashlib.sha256(
                    b"claimed bytes\n"
                ).hexdigest()
                metadata_path.write_bytes(_json_bytes(metadata))
                before = _tree_bytes(base)
                with self.assertRaises(ContractError) as caught:
                    _plan(project, vault, None, home)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(_tree_bytes(base), before)

    def test_cancelled_terminal_task_never_demands_a_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            items = []
            _add_task(
                project,
                vault,
                items,
                source_overrides={
                    "status": "cancelled",
                    "createdAt": "2026-01-01",
                    "cancelledAt": "2026-02-10T15:30:00Z",
                },
                task_md_kwargs={
                    "status": "cancelled",
                    "events": [dict(CANCELLED_EVENT, at="2026-02-10T15:30:00Z")],
                },
            )
            _write(
                project / ".trellis/workspace/dev01/journal-1.md",
                b"# Work remaining\nFinish alpha validation.\n",
            )
            _write(
                project / ".trellis/.runtime/sessions/codex_fixture.json",
                _json_bytes(
                    {
                        "platform": "codex",
                        "last_seen_at": "2026-09-21T10:00:00Z",
                        "current_task": ".trellis/tasks/09-01-alpha",
                        "current_run": None,
                    }
                ),
            )
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            manifest = _plan(project, vault, decisions, home)
            targets = {
                operation["target"]
                for operation in manifest["payload"]["projects"][0][
                    "private_operations"
                ]
            }
            self.assertIn(str(project / "ai/tasks/alpha/task.md"), targets)
            self.assertFalse(any("/docs/handoffs/" in target for target in targets))
            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, _reader))
            self.assertEqual(_tree_bytes(base), before)

    def test_blocked_unfinished_task_still_demands_a_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            items = []
            _add_task(
                project,
                vault,
                items,
                source_overrides={"status": "blocked"},
                task_md_kwargs={
                    "status": "blocked",
                    "blocked_reason": NO_RECORDED_REASON,
                    "events": [dict(BLOCKED_EVENT, at="unknown")],
                },
            )
            _write(
                project / ".trellis/workspace/dev01/journal-1.md",
                b"# Work remaining\nFinish alpha validation.\n",
            )
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            with self.assertRaises(ContractError) as caught:
                _plan(project, vault, decisions, home)
            self.assertEqual(caught.exception.code, "approval-required")
            self.assertEqual(_tree_bytes(base), before)


_OWNERSHIP_ASSET_PATH = (
    SCRIPTS.parents[0] / "assets" / "migration-legacy-ownership.json"
)
_STALE_DIGEST = hashlib.sha256(b"stale recorded bytes\n").hexdigest()
_OFFICIAL_WORKFLOW = b"# official generated workflow\n"


def _ownership_asset_context(base, official_field, *, config_pins=None):
    """Patch the installed ownership asset to a fixture carrying evidence.

    ``official_field`` is the raw ``official_template_payloads`` value; pass
    ``None`` to omit the field entirely (no fallback recognition).
    """
    document = json.loads(_OWNERSHIP_ASSET_PATH.read_bytes())
    if config_pins is not None:
        document["project_config_templates"] = config_pins
    if official_field is not None:
        document["official_template_payloads"] = official_field
    else:
        document.pop("official_template_payloads", None)
    asset = base / "fixture-ownership-asset.json"
    asset.write_bytes(_json_bytes(document))
    return mock.patch.object(sbtd_migration_plan, "_OWNERSHIP_ASSET", asset)


def _official_evidence(files, *, releases=None):
    return {
        "package": "@mindfoldhq/trellis",
        "normalization": "UTF-8, CRLF to LF only",
        "releases": releases
        or {
            "9.9.9": {
                "tarball": "https://registry.example.invalid/trellis-9.9.9.tgz",
                "integrity": "sha512-fixture",
            }
        },
        "files": files,
    }


def _official_record(digest, *, version="9.9.9"):
    return {
        "sha256": digest,
        "version": version,
        "member": "package/dist/templates/fixture-payload",
        "rendering": "verbatim",
    }


def _stale_platform_metadata(project, relatives):
    metadata_path = project / ".trellis/.template-hashes.json"
    metadata = json.loads(metadata_path.read_text())
    for relative in relatives:
        metadata["hashes"][relative] = _STALE_DIGEST
    metadata_path.write_bytes(_json_bytes(metadata))
    return metadata_path


def _receipt_reader(manifest, receipt):
    """Original bytes through a receipt's retained backups, as apply does."""
    from sbtd_migration import _original_reference

    def resolve(reference):
        found = _original_reference(reference, manifest, receipt)
        return read_file(Path(found["path"]), found["state"])

    return resolve


class MigrationPlanOfficialTemplateRecognitionTests(unittest.TestCase):
    """Exact official payloads pinned in the installed ownership asset."""

    def test_stale_recorded_digest_accepts_exact_official_alternative(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            _write(project / ".trellis/workflow.md", _OFFICIAL_WORKFLOW)
            metadata_path = _stale_platform_metadata(
                project, [PLATFORM_REL, ".trellis/workflow.md"]
            )
            metadata_raw = metadata_path.read_bytes()
            official = hashlib.sha256(PLATFORM_TOML).hexdigest()
            asset = _ownership_asset_context(
                base,
                _official_evidence(
                    {
                        PLATFORM_REL: [_official_record(official)],
                        ".trellis/workflow.md": [
                            _official_record(
                                hashlib.sha256(_OFFICIAL_WORKFLOW).hexdigest()
                            )
                        ],
                    }
                ),
            )
            before = _tree_bytes(base)
            with asset:
                manifest = _plan(project, vault, None, home)
            # Recognition never rewrites the recorded legacy metadata.
            self.assertEqual(metadata_path.read_bytes(), metadata_raw)
            self.assertEqual(_tree_bytes(base), before)
            operations = manifest["payload"]["projects"][0]["private_operations"]
            removals = [
                operation
                for operation in operations
                if operation["change"] == {"kind": "remove"}
                and operation["phase"] == "apply"
            ]
            self.assertEqual(
                [operation["target"] for operation in removals],
                [str(project / PLATFORM_REL)],
            )
            self.assertEqual(
                [operation["ownership"]["kind"] for operation in removals],
                ["template-source"],
            )
            with _home_env(home), asset:
                self.assertIsNone(validate_legacy_inputs(manifest, _reader))

    def test_changed_or_unpinned_content_is_still_rejected(self):
        official = hashlib.sha256(PLATFORM_TOML).hexdigest()
        cases = (
            (
                "changed",
                b'name = "trellis-implement"\n# user edit\n',
                _official_evidence({PLATFORM_REL: [_official_record(official)]}),
            ),
            (
                "unpinned-digest",
                PLATFORM_TOML,
                _official_evidence(
                    {
                        PLATFORM_REL: [
                            _official_record(hashlib.sha256(b"other\n").hexdigest())
                        ]
                    }
                ),
            ),
            ("no-evidence-field", PLATFORM_TOML, None),
        )
        for label, live, field in cases:
            with (
                self.subTest(label=label),
                tempfile.TemporaryDirectory() as directory,
            ):
                base = Path(directory).resolve()
                project = _base_tree(base)
                if live != PLATFORM_TOML:
                    _write(project / PLATFORM_REL, live)
                vault, home = base / "vault", base / "home"
                vault.mkdir(mode=0o700)
                home.mkdir(mode=0o700)
                _stale_platform_metadata(project, [PLATFORM_REL])
                asset = _ownership_asset_context(base, field)
                before = _tree_bytes(base)
                with asset, self.assertRaises(ContractError) as caught:
                    _plan(project, vault, None, home)
                self.assertEqual(caught.exception.code, "ownership-conflict")
                self.assertEqual(_tree_bytes(base), before)

    def test_official_digest_is_not_transferable_to_another_path(self):
        check_rel = ".codex/agents/trellis-check.toml"
        check_toml = b'name = "trellis-check"\n'
        for transferred in (True, False):
            with (
                self.subTest(transfer_blocked=transferred),
                tempfile.TemporaryDirectory() as directory,
            ):
                base = Path(directory).resolve()
                project = _base_tree(base)
                _write(project / check_rel, check_toml)
                vault, home = base / "vault", base / "home"
                vault.mkdir(mode=0o700)
                home.mkdir(mode=0o700)
                _stale_platform_metadata(project, [PLATFORM_REL, check_rel])
                files = {
                    PLATFORM_REL: [
                        _official_record(hashlib.sha256(PLATFORM_TOML).hexdigest()),
                        _official_record(hashlib.sha256(check_toml).hexdigest()),
                    ]
                }
                if not transferred:
                    files[check_rel] = [
                        _official_record(hashlib.sha256(check_toml).hexdigest())
                    ]
                asset = _ownership_asset_context(base, _official_evidence(files))
                before = _tree_bytes(base)
                if transferred:
                    # The check.toml bytes carry a digest pinned only for the
                    # implement path: recognized content never moves files.
                    with asset, self.assertRaises(ContractError) as caught:
                        _plan(project, vault, None, home)
                    self.assertEqual(caught.exception.code, "ownership-conflict")
                    self.assertEqual(_tree_bytes(base), before)
                else:
                    with asset:
                        manifest = _plan(project, vault, None, home)
                    removals = {
                        operation["target"]
                        for operation in manifest["payload"]["projects"][0][
                            "private_operations"
                        ]
                        if operation["change"] == {"kind": "remove"}
                        and operation["phase"] == "apply"
                    }
                    self.assertEqual(
                        removals,
                        {str(project / PLATFORM_REL), str(project / check_rel)},
                    )
                    self.assertEqual(_tree_bytes(base), before)

    def test_shared_configuration_never_uses_the_official_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            config_rel = ".codex/config.toml"
            recorded_config = b'model = "recorded"\n'
            live_config = b'model = "official-rendered"\n'
            _write(project / config_rel, live_config)
            metadata_path = project / ".trellis/.template-hashes.json"
            metadata = json.loads(metadata_path.read_text())
            metadata["hashes"][config_rel] = hashlib.sha256(
                recorded_config
            ).hexdigest()
            metadata_path.write_bytes(_json_bytes(metadata))
            asset = _ownership_asset_context(
                base,
                _official_evidence(
                    {
                        config_rel: [
                            _official_record(hashlib.sha256(live_config).hexdigest())
                        ]
                    }
                ),
                config_pins={
                    config_rel: [hashlib.sha256(recorded_config).hexdigest()]
                },
            )
            before = _tree_bytes(base)
            with asset, self.assertRaises(ContractError) as caught:
                _plan(project, vault, None, home)
            self.assertEqual(caught.exception.code, "ownership-conflict")
            self.assertEqual(_tree_bytes(base), before)

    def test_root_agents_never_uses_the_official_fallback(self):
        """A same-path official digest never replaces signed mixed-root approval."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, _home, vault, _evidence, _pause, environment = _routing_batch(
                base
            )
            live = project / "AGENTS.md"
            body = (
                b"keep-mine\n<!-- TRELLIS:START -->\ncustom routing\n"
                b"<!-- TRELLIS:END -->\n"
            )
            live.write_bytes(body)
            hashes_path = project / ".trellis/.template-hashes.json"
            recorded = json.loads(hashes_path.read_text())
            recorded["hashes"]["AGENTS.md"] = hashlib.sha256(
                b"recorded old template\n"
            ).hexdigest()
            hashes_path.write_bytes(_json_bytes(recorded))
            asset = _ownership_asset_context(
                base,
                _official_evidence(
                    {
                        "AGENTS.md": [
                            _official_record(hashlib.sha256(body).hexdigest())
                        ]
                    }
                ),
            )
            before = _tree_bytes(base)
            with (
                mock.patch.dict(os.environ, environment),
                asset,
                self.assertRaises(ContractError) as caught,
            ):
                plan_migration(
                    [project],
                    vault,
                    "fixture",
                    None,
                    tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                )
            self.assertEqual(caught.exception.code, "ownership-conflict")
            self.assertEqual(_tree_bytes(base), before)

    def test_malformed_official_evidence_fails_closed(self):
        official = hashlib.sha256(PLATFORM_TOML).hexdigest()
        sound = _official_evidence({PLATFORM_REL: [_official_record(official)]})

        def mutate(**overrides):
            return {**sound, **overrides}

        cases = (
            ("field-not-a-mapping", ["not", "a", "mapping"]),
            (
                "missing-package",
                {key: value for key, value in sound.items() if key != "package"},
            ),
            ("empty-releases", mutate(releases={})),
            (
                "release-without-integrity",
                mutate(
                    releases={
                        "9.9.9": {
                            "tarball": "https://registry.example.invalid/t.tgz"
                        }
                    }
                ),
            ),
            ("empty-files", mutate(files={})),
            (
                "records-not-a-list",
                mutate(files={PLATFORM_REL: _official_record(official)}),
            ),
            (
                "record-missing-member",
                mutate(
                    files={
                        PLATFORM_REL: [
                            {
                                "sha256": official,
                                "version": "9.9.9",
                                "rendering": "verbatim",
                            }
                        ]
                    }
                ),
            ),
            (
                "record-unpublished-version",
                mutate(
                    files={PLATFORM_REL: [_official_record(official, version="0.0.0")]}
                ),
            ),
            (
                "record-bad-digest",
                mutate(files={PLATFORM_REL: [_official_record("0" * 63 + "z")]}),
            ),
            (
                "unsafe-member",
                mutate(
                    files={
                        PLATFORM_REL: [
                            {**_official_record(official), "member": "../escape.toml"}
                        ]
                    }
                ),
            ),
            (
                "unsafe-path",
                mutate(files={"../escape.md": [_official_record(official)]}),
            ),
        )
        for label, field in cases:
            with (
                self.subTest(label=label),
                tempfile.TemporaryDirectory() as directory,
            ):
                base = Path(directory).resolve()
                _base_tree(base)
                vault, home = base / "vault", base / "home"
                vault.mkdir(mode=0o700)
                home.mkdir(mode=0o700)
                asset = _ownership_asset_context(base, field)
                before = _tree_bytes(base)
                with asset, self.assertRaises(ContractError) as caught:
                    _plan(base / "project", vault, None, home)
                self.assertEqual(caught.exception.code, "invalid-config")
                self.assertEqual(_tree_bytes(base), before)

    def test_signed_project_agents_replacement_bypasses_stale_whole_file_digest(
        self,
    ):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, _home, vault, evidence, pause, environment = _routing_batch(
                base
            )
            live = project / "AGENTS.md"
            live.write_bytes(
                b"keep-mine\n<!-- TRELLIS:START -->\ncustom routing\n"
                b"<!-- TRELLIS:END -->\n"
            )
            hashes_path = project / ".trellis/.template-hashes.json"
            recorded = json.loads(hashes_path.read_text())
            recorded["hashes"]["AGENTS.md"] = hashlib.sha256(
                b"recorded old template\n"
            ).hexdigest()
            hashes_path.write_bytes(_json_bytes(recorded))
            candidate = vault / "routing-candidate.md"
            candidate.write_bytes(pause + b"\napproved demo replacement\n")
            approval = vault / "routing-approvals.json"
            _routing_approval(approval, "demo-project", live, candidate)
            with mock.patch.dict(os.environ, environment):
                # No approval: the stale whole-file digest still blocks.
                with self.assertRaises(ContractError) as blocked:
                    plan_migration(
                        [project],
                        vault,
                        "fixture",
                        None,
                        tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                    )
                self.assertEqual(blocked.exception.code, "ownership-conflict")
                # An approval signed by a foreign key is no approval.
                _sign_existing_approval(
                    approval, private_key=Ed25519PrivateKey.generate()
                )
                with self.assertRaises(ContractError) as invalid:
                    _plan_routing(project, vault, approval, environment)
                self.assertEqual(invalid.exception.code, "approval-conflict")
                _sign_existing_approval(approval)
                manifest = _plan_routing(project, vault, approval, environment)
                private = manifest["payload"]["projects"][0]["private_operations"]
                replacements = [
                    operation
                    for operation in private
                    if operation["selector"] == "approved-routing-replacement"
                ]
                self.assertEqual(len(replacements), 1)
                self.assertEqual(replacements[0]["change"]["kind"], "copy-file")
                self.assertEqual(
                    replacements[0]["ownership"]["kind"], "approved-candidate"
                )
                self.assertEqual(replacements[0]["target"], str(live))
                # Foreign mixed content never becomes generated ownership: no
                # marker removal and no template-source removal for the file.
                self.assertFalse(
                    any(
                        operation["target"] == str(live)
                        and operation["selector"] == "trellis-block"
                        for operation in private
                    )
                )
                self.assertFalse(
                    any(
                        operation["target"] == str(live)
                        and operation["ownership"].get("kind") == "template-source"
                        for operation in private
                    )
                )
                self.assertTrue(
                    any(
                        operation["target"] == str(project / PLATFORM_REL)
                        and operation["change"] == {"kind": "remove"}
                        for operation in private
                    )
                )
                validate_legacy_inputs(manifest, _reader)
                from onboard_contracts import canonical_json_bytes
                from sbtd_migration import apply_migration

                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(manifest))
                with mock.patch(
                    "sbtd_migration.runtime_versions",
                    return_value={"onboard": "fixture", "graft": "0.18.0"},
                ):
                    response, code = apply_migration(
                        manifest_path,
                        confirmed=True,
                        routing_approvals=approval,
                    )
                self.assertEqual(code, 0, response)
                self.assertEqual(live.read_bytes(), candidate.read_bytes())
                self.assertFalse((project / PLATFORM_REL).exists())
                validate_legacy_inputs(
                    manifest,
                    _receipt_reader(
                        manifest, response["migration"]["apply_receipt"]
                    ),
                )

    def test_resealed_forged_platform_before_state_is_rejected(self):
        from sbtd_migration import apply_migration

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault, home, evidence = (
                base / "vault",
                base / "home",
                base / "evidence",
            )
            for path in (vault, home, evidence):
                path.mkdir(mode=0o700)
            manifest = _plan(project, vault, None, home)
            foreign = b'name = "trellis-implement"\n# foreign rewrite\n'
            _write(project / PLATFORM_REL, foreign)

            def forge(payload):
                operation = next(
                    item
                    for item in payload["projects"][0]["private_operations"]
                    if item["change"] == {"kind": "remove"}
                    and item["phase"] == "apply"
                )
                operation["before_requirement"]["state"] = snapshot(
                    project / PLATFORM_REL
                )

            tampered = _reseal(manifest, forge)
            with _home_env(home), self.assertRaises(ContractError) as caught:
                validate_legacy_inputs(tampered, _strict_reader)
            self.assertEqual(caught.exception.code, "ownership-conflict")
            manifest_path = evidence / "manifest.json"
            manifest_path.write_bytes(contracts.canonical_json_bytes(tampered))
            with (
                _home_env(home),
                mock.patch(
                    "sbtd_migration.runtime_versions",
                    return_value={"onboard": "fixture", "graft": "0.18.0"},
                ),
                self.assertRaises(ContractError) as apply_error,
            ):
                apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
            self.assertEqual(apply_error.exception.code, "ownership-conflict")
            self.assertEqual((project / PLATFORM_REL).read_bytes(), foreign)

    def test_resealed_forged_marker_before_state_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _no_host_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            manifest = _plan(project, vault, None, home)
            foreign = (
                b"foreign rules\n<!-- TRELLIS:START -->\nforged managed text\n"
                b"<!-- TRELLIS:END -->\n"
            )
            _write(project / "AGENTS.md", foreign)

            def forge(payload):
                operation = next(
                    item
                    for item in payload["projects"][0]["private_operations"]
                    if item["selector"] == "trellis-block"
                )
                forged = snapshot(project / "AGENTS.md")
                operation["before_requirement"]["state"] = forged
                operation["ownership"]["reference"]["state"] = forged

            tampered = _reseal(manifest, forge)
            with _home_env(home), self.assertRaises(ContractError) as caught:
                validate_legacy_inputs(tampered, _strict_reader)
            self.assertEqual(caught.exception.code, "ownership-conflict")
            self.assertEqual((project / "AGENTS.md").read_bytes(), foreign)

    def test_resealed_foreign_legacy_workflow_body_is_rejected(self):
        """A coherently re-sealed foreign .trellis payload inherits nothing."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _no_host_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            manifest = _plan(project, vault, None, home)
            legacy_path = project / ".trellis"
            foreign = b"# foreign workflow\nattacker controlled\n"
            _write(legacy_path / "workflow.md", foreign)

            def forge(payload):
                forged = snapshot(legacy_path)
                project_payload = payload["projects"][0]
                project_payload["sources"][0]["state"] = forged
                for operation in project_payload["private_operations"]:
                    reference = operation["ownership"].get("reference")
                    if (
                        isinstance(reference, dict)
                        and reference.get("path") == str(legacy_path)
                    ):
                        reference["state"] = forged
                    requirement = operation["before_requirement"]
                    if (
                        operation["target"] == str(legacy_path)
                        and requirement.get("kind") == "state"
                    ):
                        requirement["state"] = forged

            tampered = _reseal(manifest, forge)
            with _home_env(home), self.assertRaises(ContractError) as caught:
                validate_legacy_inputs(tampered, _strict_reader)
            self.assertEqual(caught.exception.code, "ownership-conflict")
            self.assertEqual((legacy_path / "workflow.md").read_bytes(), foreign)

    def test_ignored_binary_survives_retained_original_replay(self):
        """An ignored binary cache stays valid after the legacy tree retires."""
        from sbtd_migration import _backup_sources, _source_backup_paths

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _no_host_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            subprocess.run(
                ["git", "init"], cwd=project, check=True, capture_output=True
            )
            subprocess.run(
                [
                    "git",
                    "-c", "user.name=fixture",
                    "-c", "user.email=fixture@test",
                    "-c", "commit.gpgsign=false",
                    "commit", "--allow-empty", "-m", "fixture revision",
                ],
                cwd=project,
                check=True,
                capture_output=True,
            )
            source_root = project / ".trellis"
            _write(source_root / ".gitignore", b"__pycache__/\n")
            blob = b"\x00compiled\xff"
            cache = source_root / "scripts" / "common" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "io.cpython-313.pyc").write_bytes(blob)
            metadata_path = source_root / ".template-hashes.json"
            metadata = json.loads(metadata_path.read_text())
            metadata["hashes"][
                ".trellis/scripts/common/__pycache__/io.cpython-313.pyc"
            ] = hashlib.sha256(blob).hexdigest()
            metadata_path.write_bytes(_json_bytes(metadata))
            manifest = _plan(project, vault, None, home)
            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, _reader))
                backup = _source_backup_paths(manifest)[str(source_root)]
                _backup_sources(manifest)
                source_root.rename(base / "retired-source")

                def original(reference):
                    path = Path(reference["path"])
                    if path.is_relative_to(source_root):
                        path = backup / path.relative_to(source_root)
                    return read_file(path, reference["state"])

                self.assertIsNone(validate_legacy_inputs(manifest, original))
            self.assertEqual(
                (backup / "scripts/common/__pycache__/io.cpython-313.pyc").read_bytes(),
                blob,
            )

    def test_resealed_unignored_binary_workflow_is_rejected_after_retirement(self):
        from sbtd_migration import _backup_sources, _source_backup_paths

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _no_host_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            subprocess.run(
                ["git", "init"], cwd=project, check=True, capture_output=True
            )
            subprocess.run(
                [
                    "git",
                    "-c", "user.name=fixture",
                    "-c", "user.email=fixture@test",
                    "-c", "commit.gpgsign=false",
                    "commit", "--allow-empty", "-m", "fixture revision",
                ],
                cwd=project,
                check=True,
                capture_output=True,
            )
            source_root = project / ".trellis"
            _write(source_root / ".gitignore", b"__pycache__/\n")
            manifest = _plan(project, vault, None, home)
            foreign = b"\x00foreign workflow\xff"
            _write(source_root / "workflow.md", foreign)

            def forge(payload):
                state = snapshot(source_root)
                project_payload = payload["projects"][0]
                project_payload["sources"][0]["state"] = state
                for operation in project_payload["private_operations"]:
                    if operation["target"] == str(source_root):
                        operation["before_requirement"]["state"] = state
                        operation["ownership"]["reference"]["state"] = state

            tampered = _reseal(manifest, forge)
            with _home_env(home):
                backup = _source_backup_paths(tampered)[str(source_root)]
                _backup_sources(tampered)
                source_root.rename(base / "retired-source")

                def original(reference):
                    path = Path(reference["path"])
                    if path.is_relative_to(source_root):
                        path = backup / path.relative_to(source_root)
                    return read_file(path, reference["state"])

                with self.assertRaises(ContractError) as caught:
                    validate_legacy_inputs(tampered, original)
            self.assertEqual(caught.exception.code, "unknown-content")
            self.assertEqual((backup / "workflow.md").read_bytes(), foreign)

    def test_retained_unrecorded_ignored_cache_survives_replay(self):
        """An ignored incidental cache does not become unknown after retirement."""
        from sbtd_migration import _backup_sources, _source_backup_paths

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _no_host_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            subprocess.run(
                ["git", "init"], cwd=project, check=True, capture_output=True
            )
            subprocess.run(
                [
                    "git",
                    "-c", "user.name=fixture",
                    "-c", "user.email=fixture@test",
                    "-c", "commit.gpgsign=false",
                    "commit", "--allow-empty", "-m", "fixture revision",
                ],
                cwd=project,
                check=True,
                capture_output=True,
            )
            source_root = project / ".trellis"
            _write(source_root / ".gitignore", b"__pycache__/\n")
            blob = b"\x00compiled\xff"
            cache = source_root / "scripts" / "common" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "io.cpython-313.pyc").write_bytes(blob)
            manifest = _plan(project, vault, None, home)
            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, _reader))
                backup = _source_backup_paths(manifest)[str(source_root)]
                _backup_sources(manifest)
                source_root.rename(base / "retired-source")

                def original(reference):
                    path = Path(reference["path"])
                    if path.is_relative_to(source_root):
                        path = backup / path.relative_to(source_root)
                    return read_file(path, reference["state"])

                self.assertIsNone(validate_legacy_inputs(manifest, original))
            self.assertEqual(
                (backup / "scripts/common/__pycache__/io.cpython-313.pyc").read_bytes(),
                blob,
            )

    def test_retained_unknown_outside_known_layout_stays_ignored_replay(self):
        """Retained rules cover incidental unknown files after retirement."""
        from sbtd_migration import _backup_sources, _source_backup_paths

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _no_host_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            subprocess.run(
                ["git", "init"], cwd=project, check=True, capture_output=True
            )
            subprocess.run(
                [
                    "git",
                    "-c", "user.name=fixture",
                    "-c", "user.email=fixture@test",
                    "-c", "commit.gpgsign=false",
                    "commit", "--allow-empty", "-m", "fixture revision",
                ],
                cwd=project,
                check=True,
                capture_output=True,
            )
            source_root = project / ".trellis"
            _write(source_root / ".gitignore", b"cache/\n")
            blob = b"cache scratch\n"
            scratch = source_root / "cache"
            scratch.mkdir()
            (scratch / "notes.bin").write_bytes(blob)
            manifest = _plan(project, vault, None, home)
            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, _reader))
                backup = _source_backup_paths(manifest)[str(source_root)]
                _backup_sources(manifest)
                source_root.rename(base / "retired-source")

                def original(reference):
                    path = Path(reference["path"])
                    if path.is_relative_to(source_root):
                        path = backup / path.relative_to(source_root)
                    return read_file(path, reference["state"])

                self.assertIsNone(validate_legacy_inputs(manifest, original))
            self.assertEqual((backup / "cache" / "notes.bin").read_bytes(), blob)

    def test_retained_negation_preserves_ancestor_exclusion_replay(self):
        """A retained negation cannot reinclude below an excluded parent."""
        from sbtd_migration import _backup_sources, _source_backup_paths

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _no_host_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            subprocess.run(
                ["git", "init"], cwd=project, check=True, capture_output=True
            )
            subprocess.run(
                [
                    "git",
                    "-c", "user.name=fixture",
                    "-c", "user.email=fixture@test",
                    "-c", "commit.gpgsign=false",
                    "commit", "--allow-empty", "-m", "fixture revision",
                ],
                cwd=project,
                check=True,
                capture_output=True,
            )
            _write(project / ".gitignore", b"/.trellis/\n")
            source_root = project / ".trellis"
            _write(source_root / ".gitignore", b"!scripts/cache.bin\n")
            blob = b"\x00cached\xff"
            scripts = source_root / "scripts"
            (scripts / "cache.bin").write_bytes(blob)
            metadata_path = source_root / ".template-hashes.json"
            metadata = json.loads(metadata_path.read_text())
            metadata["hashes"][".trellis/scripts/cache.bin"] = hashlib.sha256(
                blob
            ).hexdigest()
            metadata_path.write_bytes(_json_bytes(metadata))
            manifest = _plan(project, vault, None, home)
            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, _reader))
                backup = _source_backup_paths(manifest)[str(source_root)]
                _backup_sources(manifest)
                source_root.rename(base / "retired-source")

                def original(reference):
                    path = Path(reference["path"])
                    if path.is_relative_to(source_root):
                        path = backup / path.relative_to(source_root)
                    return read_file(path, reference["state"])

                self.assertIsNone(validate_legacy_inputs(manifest, original))
            self.assertEqual((backup / "scripts" / "cache.bin").read_bytes(), blob)

    def test_retained_negation_allows_named_binary_replay(self):
        """A genuine retained negation survives post-retirement replay."""
        from sbtd_migration import _backup_sources, _source_backup_paths

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _no_host_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            subprocess.run(
                ["git", "init"], cwd=project, check=True, capture_output=True
            )
            subprocess.run(
                [
                    "git",
                    "-c", "user.name=fixture",
                    "-c", "user.email=fixture@test",
                    "-c", "commit.gpgsign=false",
                    "commit", "--allow-empty", "-m", "fixture revision",
                ],
                cwd=project,
                check=True,
                capture_output=True,
            )
            _write(project / ".gitignore", b".trellis/scripts/cache.bin\n")
            source_root = project / ".trellis"
            blob = b"\x00cached\xff"
            scripts = source_root / "scripts"
            (scripts / "cache.bin").write_bytes(blob)
            metadata_path = source_root / ".template-hashes.json"
            metadata = json.loads(metadata_path.read_text())
            metadata["hashes"][".trellis/scripts/cache.bin"] = hashlib.sha256(
                blob
            ).hexdigest()
            metadata_path.write_bytes(_json_bytes(metadata))
            manifest = _plan(project, vault, None, home)
            _write(source_root / ".gitignore", b"!scripts/cache.bin\n")

            def forge(payload):
                state = snapshot(source_root)
                project_payload = payload["projects"][0]
                project_payload["sources"][0]["state"] = state
                for operation in project_payload["private_operations"]:
                    if operation["target"] == str(source_root):
                        operation["before_requirement"]["state"] = state
                        operation["ownership"]["reference"]["state"] = state

            tampered = _reseal(manifest, forge)
            with _home_env(home):
                with self.assertRaises(ContractError) as caught:
                    validate_legacy_inputs(tampered, _reader)
                self.assertEqual(caught.exception.code, "unknown-content")
                backup = _source_backup_paths(tampered)[str(source_root)]
                _backup_sources(tampered)
                source_root.rename(base / "retired-source")

                def original(reference):
                    path = Path(reference["path"])
                    if path.is_relative_to(source_root):
                        path = backup / path.relative_to(source_root)
                    return read_file(path, reference["state"])

                with self.assertRaises(ContractError) as caught:
                    validate_legacy_inputs(tampered, original)
                native_git = sbtd_migration_plan._git_bytes

                def unavailable_retained_git(root, args, stdin=None, **kwargs):
                    if (kwargs.get("environment") or {}).get("GIT_WORK_TREE"):
                        return None
                    return native_git(root, args, stdin, **kwargs)

                with mock.patch.object(
                    sbtd_migration_plan,
                    "_git_bytes",
                    side_effect=unavailable_retained_git,
                ), self.assertRaises(ContractError) as unavailable:
                    validate_legacy_inputs(tampered, original)
                self.assertEqual(unavailable.exception.code, "unknown-content")
            self.assertEqual(caught.exception.code, "unknown-content")
            self.assertEqual((backup / "scripts" / "cache.bin").read_bytes(), blob)

    def test_retained_nested_ancestor_and_reinclusion_precedence(self):
        from sbtd_migration import _backup_sources, _source_backup_paths

        cases = (
            (b"/.trellis/scripts/\n", b"!scripts/deeper/cache.bin\n", False, ".gitignore"),
            (
                b"/.trellis/scripts/deeper/\n",
                b"!scripts/deeper/cache.bin\n", False, ".gitignore",
            ),
            (
                b"/.trellis/scripts/\n",
                b"!scripts/\n!scripts/deeper/cache.bin\n", True, ".gitignore",
            ),
            (
                b".trellis/scripts/deeper/cache.bin\n.trellis/scripts/.GITIGNORE\n",
                b"!deeper/cache.bin\n", True, "scripts/.GITIGNORE",
            ),
        )
        for root_rule, retained_rules, rejected, ignore_file in cases:
            with (
                self.subTest(root_rule=root_rule, rules=retained_rules, file=ignore_file),
                tempfile.TemporaryDirectory() as directory,
            ):
                base = Path(directory).resolve()
                project = _no_host_tree(base)
                vault, home = base / "vault", base / "home"
                vault.mkdir(mode=0o700)
                home.mkdir(mode=0o700)
                subprocess.run(
                    ["git", "init"], cwd=project, check=True, capture_output=True
                )
                subprocess.run(
                    [
                        "git", "-c", "user.name=fixture",
                        "-c", "user.email=fixture@test",
                        "-c", "commit.gpgsign=false",
                        "-c", f"core.hooksPath={os.devnull}",
                        "commit", "--allow-empty", "-m", "fixture revision",
                    ],
                    cwd=project, check=True, capture_output=True,
                )
                _write(project / ".gitignore", root_rule)
                source_root = project / ".trellis"
                relative = "scripts/deeper/cache.bin"
                blob = b"\x00cached\xff"
                _write(source_root / relative, blob)
                metadata_path = source_root / ".template-hashes.json"
                metadata = json.loads(metadata_path.read_text())
                metadata["hashes"][f".trellis/{relative}"] = hashlib.sha256(
                    blob
                ).hexdigest()
                metadata_path.write_bytes(_json_bytes(metadata))
                manifest = _plan(project, vault, None, home)
                _write(source_root / ignore_file, retained_rules)
                if ignore_file != ".gitignore" and not (
                    source_root / ignore_file.lower()
                ).exists():
                    self.skipTest("requires case-insensitive ignore-file lookup")

                def forge(payload, source_root=source_root):
                    state = snapshot(source_root)
                    selected = payload["projects"][0]
                    selected["sources"][0]["state"] = state
                    for operation in selected["private_operations"]:
                        if operation["target"] == str(source_root):
                            operation["before_requirement"]["state"] = state
                            operation["ownership"]["reference"]["state"] = state

                resealed = _reseal(manifest, forge)
                with _home_env(home):
                    if rejected:
                        with self.assertRaises(ContractError) as live:
                            validate_legacy_inputs(resealed, _reader)
                        self.assertEqual(live.exception.code, "unknown-content")
                    else:
                        self.assertIsNone(validate_legacy_inputs(resealed, _reader))
                    backup = _source_backup_paths(resealed)[str(source_root)]
                    _backup_sources(resealed)
                    source_root.rename(base / "retired-source")

                    def original(reference, source_root=source_root, backup=backup):
                        path = Path(reference["path"])
                        if path.is_relative_to(source_root):
                            path = backup / path.relative_to(source_root)
                        return read_file(path, reference["state"])

                    if rejected:
                        with self.assertRaises(ContractError) as caught:
                            validate_legacy_inputs(resealed, original)
                        self.assertEqual(caught.exception.code, "unknown-content")
                    else:
                        self.assertIsNone(validate_legacy_inputs(resealed, original))
                self.assertEqual((backup / relative).read_bytes(), blob)

    def test_official_alternative_apply_retry_and_retained_original_revalidation(
        self,
    ):
        from sbtd_migration import apply_migration, runtime_versions

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault, home, evidence = (
                base / "vault",
                base / "home",
                base / "evidence",
            )
            for path in (vault, home, evidence):
                path.mkdir(mode=0o700)
            _write(project / ".trellis/workflow.md", _OFFICIAL_WORKFLOW)
            metadata_path = _stale_platform_metadata(
                project, [PLATFORM_REL, ".trellis/workflow.md"]
            )
            metadata_raw = metadata_path.read_bytes()
            official = hashlib.sha256(PLATFORM_TOML).hexdigest()
            asset = _ownership_asset_context(
                base,
                _official_evidence(
                    {
                        PLATFORM_REL: [_official_record(official)],
                        ".trellis/workflow.md": [
                            _official_record(
                                hashlib.sha256(_OFFICIAL_WORKFLOW).hexdigest()
                            )
                        ],
                    }
                ),
            )
            with _home_env(home), asset:
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    None,
                    tool_versions=runtime_versions(),
                )
                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(contracts.canonical_json_bytes(manifest))
                applied, code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
                self.assertEqual(code, 0, applied)
                self.assertEqual(applied["status"], "applied")
            # The stale recorded metadata is preserved, never rewritten.
            self.assertEqual(metadata_path.read_bytes(), metadata_raw)
            self.assertFalse((project / PLATFORM_REL).exists())
            self.assertTrue((project / ".trellis").is_dir())
            self.assertEqual(
                (project / ".trellis/workflow.md").read_bytes(), _OFFICIAL_WORKFLOW
            )
            receipt = applied["migration"]["apply_receipt"]
            saved = evidence / f"apply-{receipt['apply_id']}.json"
            with _home_env(home), asset:
                repeated, code = apply_migration(
                    manifest_path,
                    previous_receipt_path=saved,
                    confirmed=True,
                    no_routing_approvals=True,
                )
                self.assertEqual(code, 0, repeated)
                self.assertEqual(repeated["status"], "already-complete")
                # Removed before-state bytes re-prove from the retained backup.
                self.assertIsNone(
                    validate_legacy_inputs(
                        manifest, _receipt_reader(manifest, receipt)
                    )
                )
                resource = contracts.resource_id("file", str(project / PLATFORM_REL))
                result = next(
                    item
                    for item in receipt["payload"]["projects"][0]["private_results"]
                    if item["resource_id"] == resource
                )
                backup = result["backup_ref"]
                self.assertIsNotNone(backup)
                Path(backup["path"]).write_bytes(b"tampered retained original\n")
                with self.assertRaises(ContractError) as caught:
                    validate_legacy_inputs(
                        manifest, _receipt_reader(manifest, receipt)
                    )
            self.assertEqual(caught.exception.code, "state-conflict")


class MigrationPlanBatchTests(unittest.TestCase):
    def test_full_batch_plan_and_repeatable_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)
            before = _tree_bytes(base)
            manifest = _plan(project, vault, decisions, home)
            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, _reader))
            payload = manifest["payload"]
            self.assertEqual(manifest["schema_version"], 1)
            self.assertRegex(manifest["manifest_id"], r"^[0-9a-f]{64}$")
            self.assertEqual(payload["backup_root"], str(vault))
            self.assertEqual(payload["shared_operations"], [])
            record = payload["projects"][0]
            self.assertEqual(record["root"], str(project))
            self.assertEqual(record["platforms"], ["codex"])
            self.assertIsNone(record["source_ref"])
            self.assertIsNone(record["head"])
            self.assertEqual(
                [source["path"] for source in record["sources"]],
                [str(project / ".trellis")],
            )
            operations = record["private_operations"]
            phases = {op["phase"] for op in operations}
            self.assertEqual(phases, {"apply", "cleanup"})
            cleanup = [op for op in operations if op["phase"] == "cleanup"]
            self.assertEqual(
                [(op["target"], op["change"]["kind"]) for op in cleanup],
                [(str(project / ".trellis"), "remove")],
            )
            by_kind = {}
            for operation in operations:
                by_kind.setdefault(operation["change"]["kind"], []).append(operation)
            self.assertEqual(
                [op["target"] for op in by_kind["migrate-developer"]],
                [str(project / ".sbtd/developer")],
            )
            removed = {op["target"] for op in by_kind["remove"]}
            self.assertEqual(
                removed, {str(project / PLATFORM_REL), str(project / ".trellis")}
            )
            blocks = by_kind["ensure-file-block"]
            self.assertEqual(
                [op["target"] for op in blocks], [str(project / ".gitignore")]
            )
            self.assertEqual(blocks[0]["owner_kind"], "gitignore")
            copies = {op["target"] for op in by_kind["copy-file"]}
            self.assertEqual(
                copies,
                {
                    str(project / "ai/tasks/alpha/task.md"),
                    str(project / "ai/tasks/alpha/legacy-task.json"),
                    str(project / "ai/tasks/alpha/prd.md"),
                    str(project / "docs/spec/auth.md"),
                },
            )
            directories = by_kind["copy-directory"]
            self.assertEqual(
                [op["target"] for op in directories], [str(project / "docs/lessons")]
            )
            self.assertEqual(
                payload["publication_decisions"]["items"],
                json.loads(decisions.read_text())["items"],
            )
            roundtrip = contracts.load_document(
                contracts.canonical_json_bytes(manifest), "manifest"
            )
            self.assertEqual(roundtrip, manifest)
            # Read-only: nothing changed anywhere, including the vault.
            self.assertEqual(_tree_bytes(base), before)

    def test_git_revision_and_head_are_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)
            env = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "GIT_CONFIG_NOSYSTEM": "1",
            }
            for command in (
                ["git", "init", "-b", "main", str(project)],
                ["git", "-C", str(project), "config", "user.email", "fixture@test"],
                ["git", "-C", str(project), "config", "user.name", "fixture"],
                ["git", "-C", str(project), "add", "-A"],
                ["git", "-C", str(project), "commit", "-m", "legacy state"],
            ):
                subprocess.run(
                    command, check=True, capture_output=True, env={**os.environ, **env}
                )
            head = subprocess.run(
                ["git", "-C", str(project), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                env={**os.environ, **env},
            ).stdout.strip()
            manifest = _plan(project, vault, decisions, home)
            record = manifest["payload"]["projects"][0]
            self.assertEqual(record["source_ref"], "main")
            self.assertEqual(record["head"], head)

    def test_validate_rejects_tampered_originals_and_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)
            manifest = _plan(project, vault, decisions, home)

            def tampered_source(reference):
                data = _reader(reference)
                if reference["path"].endswith("task.json"):
                    return data + b" "
                return data

            with _home_env(home), self.assertRaises(ContractError):
                validate_legacy_inputs(manifest, tampered_source)

            def tampered_identity(reference):
                data = _reader(reference)
                if reference["path"].endswith(".developer"):
                    return b"name=other9\n"
                return data

            with _home_env(home), self.assertRaises(ContractError):
                validate_legacy_inputs(manifest, tampered_identity)
            # A candidate mutated after approval breaks the recorded state.
            target = vault / "cand-spec/auth.md"
            target.write_bytes(b"changed after approval\n")
            with _home_env(home), self.assertRaises(ContractError):
                validate_legacy_inputs(manifest, _reader)


class MigrationPlanVaultTests(unittest.TestCase):
    def test_vault_must_exist_be_private_and_outside_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            home = base / "home"
            home.mkdir(mode=0o700)
            with _home_env(home):
                with self.assertRaises(ContractError):
                    plan_migration(
                        [project],
                        base / "missing",
                        "c",
                        None,
                        tool_versions={"onboard": "f", "graft": "0.18.0"},
                    )
                self.assertFalse((base / "missing").exists())
                loose = base / "loose"
                loose.mkdir(mode=0o755)
                with self.assertRaises(ContractError):
                    plan_migration(
                        [project],
                        loose,
                        "c",
                        None,
                        tool_versions={"onboard": "f", "graft": "0.18.0"},
                    )
                link = base / "link"
                real = base / "real"
                real.mkdir(mode=0o700)
                link.symlink_to(real)
                with self.assertRaises(ContractError):
                    plan_migration(
                        [project],
                        link,
                        "c",
                        None,
                        tool_versions={"onboard": "f", "graft": "0.18.0"},
                    )
                inside = project / ".vault"
                inside.mkdir(mode=0o700)
                with self.assertRaises(ContractError):
                    plan_migration(
                        [project],
                        inside,
                        "c",
                        None,
                        tool_versions={"onboard": "f", "graft": "0.18.0"},
                    )
            self.assertEqual(_tree_bytes(project), _tree_bytes(project))

    def test_overlapping_or_aliased_roots_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            home = base / "home"
            home.mkdir(mode=0o700)
            with _home_env(home):
                with self.assertRaises(ContractError):
                    plan_migration(
                        [project, project / ".trellis"],
                        vault,
                        "c",
                        None,
                        tool_versions={"onboard": "f", "graft": "0.18.0"},
                    )
                with self.assertRaises(ContractError):
                    plan_migration(
                        [project / ".codex" / ".."],
                        vault,
                        "c",
                        None,
                        tool_versions={"onboard": "f", "graft": "0.18.0"},
                    )

    def test_decisions_document_must_live_inside_the_vault(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            home = base / "home"
            home.mkdir(mode=0o700)
            outside = base / "decisions.json"
            outside.write_bytes(b'{"schema_version": 1, "items": []}')
            with _home_env(home), self.assertRaises(ContractError):
                plan_migration(
                    [project],
                    vault,
                    "c",
                    outside,
                    tool_versions={"onboard": "f", "graft": "0.18.0"},
                )
            self.assertEqual(
                _tree_bytes(base)[str(outside.relative_to(base))],
                b'{"schema_version": 1, "items": []}',
            )


class MigrationPlanClosureTests(unittest.TestCase):
    def _tree_closure_fixture(self, base):
        project = _base_tree(base)
        vault = base / "vault"
        vault.mkdir(mode=0o700)
        home = base / "home"
        home.mkdir(mode=0o700)
        folder_path = project / ".trellis/tasks/09-01-alpha"
        source_raw = _json_bytes(_legacy_source())
        _write(folder_path / "task.json", source_raw)
        _write(folder_path / "prd.md", b"# legacy prd\n")
        candidate = vault / "cand-tree"
        _write(candidate / "task.md", _task_md())
        _write(candidate / "legacy-task.json", _sidecar(source_raw))
        _write(candidate / "prd.md", b"# legacy prd\n")
        item = _item(
            "09-01-alpha-tree",
            [_ref(folder_path / "task.json"), _ref(folder_path / "prd.md")],
            project / "ai/tasks/alpha",
            "share",
            candidate,
        )
        return project, vault, home, candidate, item

    def test_whole_tree_task_closure_is_one_directory_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, _candidate, item = self._tree_closure_fixture(base)
            decisions = _decisions(vault, [item])
            before = _tree_bytes(base)
            manifest = _plan(project, vault, decisions, home)
            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, _reader))
            operations = manifest["payload"]["projects"][0]["private_operations"]
            copies = [
                (op["change"]["kind"], op["target"])
                for op in operations
                if op["change"]["kind"] in {"copy-file", "copy-directory"}
            ]
            self.assertEqual(
                copies, [("copy-directory", str(project / "ai/tasks/alpha"))]
            )
            self.assertEqual(_tree_bytes(base), before)

    def test_tree_candidate_member_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, candidate, item = self._tree_closure_fixture(base)
            # The approved tree silently drops the existing prd attachment.
            (candidate / "prd.md").unlink()
            item = _item(
                item["item_id"],
                item["sources"],
                item["target_path"],
                item["decision"],
                candidate,
            )
            decisions = _decisions(vault, [item])
            with _home_env(home), self.assertRaises(ContractError):
                plan_migration(
                    [project],
                    vault,
                    "c",
                    decisions,
                    tool_versions={"onboard": "f", "graft": "0.18.0"},
                )
            # An unknown extra member is just as unacceptable.
            _write(candidate / "prd.md", b"# migrated prd\n")
            _write(candidate / "smuggled.md", b"extra\n")
            item = _item(
                item["item_id"],
                item["sources"],
                item["target_path"],
                item["decision"],
                candidate,
            )
            decisions = _decisions(vault, [item])
            with _home_env(home), self.assertRaises(ContractError):
                plan_migration(
                    [project],
                    vault,
                    "c",
                    decisions,
                    tool_versions={"onboard": "f", "graft": "0.18.0"},
                )

    def test_missing_approval_never_substitutes_scan_results(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, _decisions_path = _full_fixture(base)
            with _home_env(home):
                # Tasks/spec/lessons exist but no approval document was given.
                with self.assertRaises(ContractError):
                    plan_migration(
                        [project],
                        vault,
                        "c",
                        None,
                        tool_versions={"onboard": "f", "graft": "0.18.0"},
                    )
                # An approval that covers only the task is still incomplete.
                items = []
                _add_task(project, base / "vault2", items)
            vault2 = base / "vault2"
            vault2.mkdir(mode=0o700, exist_ok=True)
            partial = _decisions(vault2, items)
            with _home_env(home), self.assertRaises(ContractError):
                plan_migration(
                    [project],
                    vault2,
                    "c",
                    partial,
                    tool_versions={"onboard": "f", "graft": "0.18.0"},
                )

    def test_private_only_cannot_cover_mandatory_projections(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            home = base / "home"
            home.mkdir(mode=0o700)
            folder_path = project / ".trellis/tasks/09-01-alpha"
            _write(folder_path / "task.json", _json_bytes(_legacy_source()))
            items = [
                _item(
                    "hidden-task",
                    [_ref(folder_path / "task.json")],
                    None,
                    "private-only",
                    None,
                )
            ]
            decisions = _decisions(vault, items)
            with _home_env(home), self.assertRaises(ContractError):
                plan_migration(
                    [project],
                    vault,
                    "c",
                    decisions,
                    tool_versions={"onboard": "f", "graft": "0.18.0"},
                )

    def test_malformed_scope_and_duplicate_candidates_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)
            document = json.loads(decisions.read_text())
            # Approval scope no longer matches the declared item fields.
            document["items"][0]["approval"]["scope"]["decision"] = "redact"
            decisions.write_bytes(json.dumps(document).encode("utf-8"))
            with _home_env(home), self.assertRaises(ContractError):
                plan_migration(
                    [project],
                    vault,
                    "c",
                    decisions,
                    tool_versions={"onboard": "f", "graft": "0.18.0"},
                )
            document = json.loads(
                _decisions(
                    vault,
                    json.loads((base / "vault/decisions.json").read_text())["items"],
                ).read_text()
            )
            document["items"][1]["candidate_ref"] = document["items"][0][
                "candidate_ref"
            ]
            decisions.write_bytes(json.dumps(document).encode("utf-8"))
            with _home_env(home), self.assertRaises(ContractError):
                plan_migration(
                    [project],
                    vault,
                    "c",
                    decisions,
                    tool_versions={"onboard": "f", "graft": "0.18.0"},
                )

    def test_unknown_legacy_content_and_platform_drift_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)
            _write(project / ".trellis/mystery.txt", b"unknown\n")
            with _home_env(home), self.assertRaises(ContractError):
                plan_migration(
                    [project],
                    vault,
                    "c",
                    decisions,
                    tool_versions={"onboard": "f", "graft": "0.18.0"},
                )
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)
            # An unrecorded platform file is foreign user data: it is neither
            # removed nor allowed to block planning.
            _write(project / ".codex/agents/rogue.toml", b'name = "rogue"\n')
            manifest = _plan(project, vault, decisions, home)
            removed = {
                op["target"]
                for op in manifest["payload"]["projects"][0]["private_operations"]
                if op["change"]["kind"] == "remove"
            }
            self.assertNotIn(str(project / ".codex/agents/rogue.toml"), removed)
            self.assertEqual(
                (project / ".codex/agents/rogue.toml").read_bytes(),
                b'name = "rogue"\n',
            )
            # Drifted managed content never authorizes removal either.
            (project / PLATFORM_REL).unlink()
            drifted = b'name = "trellis-implement"\n# drifted\n'
            _write(project / PLATFORM_REL, drifted)
            with _home_env(home), self.assertRaises(ContractError):
                plan_migration(
                    [project],
                    vault,
                    "c",
                    decisions,
                    tool_versions={"onboard": "f", "graft": "0.18.0"},
                )

    def test_graph_conflicts_and_stale_targets_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            home = base / "home"
            home.mkdir(mode=0o700)
            items = []
            _add_task(project, vault, items)
            _add_task(
                project,
                vault,
                items,
                task_id="beta",
                folder="09-02-beta",
                source_overrides={"parent": "09-99-ghost"},
                task_md_kwargs={"parent": None},
            )
            decisions = _decisions(vault, items)
            with _home_env(home), self.assertRaises(ContractError):
                plan_migration(
                    [project],
                    vault,
                    "c",
                    decisions,
                    tool_versions={"onboard": "f", "graft": "0.18.0"},
                )
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)
            # An approved target already exists: apply could not prove safety.
            _write(project / "ai/tasks/alpha/task.md", b"occupied\n")
            with _home_env(home), self.assertRaises(ContractError):
                plan_migration(
                    [project],
                    vault,
                    "c",
                    decisions,
                    tool_versions={"onboard": "f", "graft": "0.18.0"},
                )

    def test_existing_current_identity_precedes_legacy_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)
            _write(project / ".sbtd/developer", b"name=other9\n")
            manifest = _plan(project, vault, decisions, home)
            self.assertFalse(
                any(
                    op["change"]["kind"] == "migrate-developer"
                    for op in manifest["payload"]["projects"][0]["private_operations"]
                )
            )
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)
            (project / ".trellis/.developer").write_bytes(b"name=a\nname=b\n")
            with _home_env(home), self.assertRaises(ContractError):
                plan_migration(
                    [project],
                    vault,
                    "c",
                    decisions,
                    tool_versions={"onboard": "f", "graft": "0.18.0"},
                )


class MigrationPlanPrivacyTests(unittest.TestCase):
    def test_redact_projection_and_private_hash_safety(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            home = base / "home"
            home.mkdir(mode=0o700)
            source = _legacy_source()
            redacted_original = json.loads(_json_bytes(source).decode("utf-8"))
            redacted_original["meta"] = None
            items = []
            _add_task(
                project,
                vault,
                items,
                decision="redact",
                sidecar_kwargs={
                    "sha": None,
                    "redacted": ["/meta"],
                    "original": redacted_original,
                },
            )
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            manifest = _plan(project, vault, decisions, home)
            self.assertEqual(
                [
                    item["decision"]
                    for item in manifest["payload"]["publication_decisions"]["items"]
                ],
                ["redact", "redact"],
            )
            self.assertEqual(_tree_bytes(base), before)

    def test_redact_sidecar_never_pins_private_source_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            home = base / "home"
            home.mkdir(mode=0o700)
            items = []
            _add_task(
                project,
                vault,
                items,
                decision="redact",
                sidecar_kwargs={"redacted": ["/meta"]},
            )
            decisions = _decisions(vault, items)
            with _home_env(home), self.assertRaises(ContractError):
                plan_migration(
                    [project],
                    vault,
                    "c",
                    decisions,
                    tool_versions={"onboard": "f", "graft": "0.18.0"},
                )

    def test_shared_projection_never_embeds_private_digest_or_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            home = base / "home"
            home.mkdir(mode=0o700)
            folder_path = project / ".trellis/tasks/09-01-alpha"
            source_raw = _json_bytes(_legacy_source())
            _write(folder_path / "task.json", source_raw)
            digest = hashlib.sha256(source_raw).hexdigest()
            candidate = vault / "cand-09-01-alpha"
            _write(candidate / "task.md", _task_md() + digest.encode("utf-8") + b"\n")
            _write(candidate / "legacy-task.json", _sidecar(source_raw))
            source_reference = _ref(folder_path / "task.json")
            items = [
                _item(
                    "09-01-alpha-document",
                    [source_reference],
                    project / "ai/tasks/alpha/task.md",
                    "share",
                    candidate / "task.md",
                ),
                _item(
                    "09-01-alpha-sidecar",
                    [source_reference],
                    project / "ai/tasks/alpha/legacy-task.json",
                    "share",
                    candidate / "legacy-task.json",
                ),
            ]
            decisions = _decisions(vault, items)
            with _home_env(home), self.assertRaises(ContractError):
                plan_migration(
                    [project],
                    vault,
                    "c",
                    decisions,
                    tool_versions={"onboard": "f", "graft": "0.18.0"},
                )
            # A candidate still pointing at the retired layout is not a safe
            # rewritten link either.
            _write(candidate / "task.md", _task_md() + b"see .trellis/tasks\n")
            items[0] = _item(
                "09-01-alpha-document",
                [source_reference],
                project / "ai/tasks/alpha/task.md",
                "share",
                candidate / "task.md",
            )
            decisions = _decisions(vault, items)
            with _home_env(home), self.assertRaises(ContractError):
                plan_migration(
                    [project],
                    vault,
                    "c",
                    decisions,
                    tool_versions={"onboard": "f", "graft": "0.18.0"},
                )

    def test_lessons_marker_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)
            # Dropping the lesson marker from the approved copy is caught even
            # though the candidate checksum is honestly recomputed.
            _write(vault / "cand-lessons/index.md", b"lesson body without markers\n")
            items = json.loads(decisions.read_text())["items"]
            for item in items:
                if item["item_id"] == "lessons-tree":
                    item["candidate_ref"] = _ref(vault / "cand-lessons")
                    item["approval"]["scope"]["candidate_ref"] = item["candidate_ref"]
                    item["decision"] = "redact"
                    item["approval"]["scope"]["decision"] = "redact"
            decisions = _decisions(vault, items)
            with _home_env(home), self.assertRaises(ContractError):
                plan_migration(
                    [project],
                    vault,
                    "c",
                    decisions,
                    tool_versions={"onboard": "f", "graft": "0.18.0"},
                )


class MigrationPlanCurrentFindingsTests(unittest.TestCase):
    def test_archived_tasks_require_the_derived_archive_target(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            items = []
            _add_task(
                project,
                vault,
                items,
                folder="archive/2026-09/09-01-alpha",
                source_overrides={"status": "completed", "completedAt": "2026-09-05"},
                task_md_kwargs={
                    "status": "done",
                    "events": [
                        {
                            "at": "unknown",
                            "from": "unknown",
                            "to": "done",
                            "reason": "legacy completion fact",
                            "evidence": "legacy task.json status",
                        }
                    ],
                },
            )
            decisions = _decisions(vault, items)
            with _home_env(home), self.assertRaises(ContractError):
                plan_migration(
                    [project],
                    vault,
                    "c",
                    decisions,
                    tool_versions={"onboard": "f", "graft": "0.18.0"},
                )
            archive = project / "ai/tasks/archive/2026-Q3/alpha"
            for item in items:
                item["target_path"] = str(archive / Path(item["target_path"]).name)
                item["approval"]["scope"]["target_path"] = item["target_path"]
            decisions = _decisions(vault, items)
            manifest = _plan(project, vault, decisions, home)
            copies = [
                operation["target"]
                for operation in manifest["payload"]["projects"][0][
                    "private_operations"
                ]
                if operation["change"]["kind"].startswith("copy-")
            ]
            self.assertEqual(
                copies, [str(archive / "legacy-task.json"), str(archive / "task.md")]
            )

    def test_unknown_completion_time_requires_the_undated_archive_target(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            items = []
            _add_task(
                project,
                vault,
                items,
                folder="archive/unknown/09-01-alpha",
                source_overrides={"status": "completed"},
                task_md_kwargs={
                    "status": "done",
                    "events": [
                        {
                            "at": "unknown",
                            "from": "unknown",
                            "to": "done",
                            "reason": "legacy completion fact",
                            "evidence": "legacy task.json status",
                        }
                    ],
                },
            )
            archive = project / "ai/tasks/archive/undated/alpha"
            for item in items:
                item["target_path"] = str(archive / Path(item["target_path"]).name)
                item["approval"]["scope"]["target_path"] = item["target_path"]
            manifest = _plan(project, vault, _decisions(vault, items), home)
            self.assertIn(
                str(archive / "task.md"),
                [
                    op["target"]
                    for op in manifest["payload"]["projects"][0]["private_operations"]
                ],
            )

    def test_completed_active_task_is_not_implicitly_archived(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            items = []
            _add_task(
                project,
                vault,
                items,
                source_overrides={"status": "completed"},
                task_md_kwargs={
                    "status": "done",
                    "events": [
                        {
                            "at": "unknown",
                            "from": "unknown",
                            "to": "done",
                            "reason": "legacy completion fact",
                            "evidence": "legacy task.json status",
                        }
                    ],
                },
            )
            manifest = _plan(project, vault, _decisions(vault, items), home)
            targets = [
                op["target"]
                for op in manifest["payload"]["projects"][0]["private_operations"]
                if op["change"]["kind"].startswith("copy-")
            ]
            self.assertIn(str(project / "ai/tasks/alpha/task.md"), targets)
            self.assertFalse(any("/ai/tasks/archive/" in target for target in targets))

    def test_duplicate_logical_legacy_ids_block_before_projection_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            items = []
            _add_task(project, vault, items, folder="09-01-alpha")
            _add_task(
                project,
                vault,
                items,
                folder="archive/unknown/09-02-alpha",
                source_overrides={"status": "completed"},
                task_md_kwargs={
                    "status": "done",
                    "events": [
                        {
                            "at": "unknown",
                            "from": "unknown",
                            "to": "done",
                            "reason": "legacy completion fact",
                            "evidence": "legacy task.json status",
                        }
                    ],
                },
            )
            for item in items[2:]:
                item["target_path"] = str(
                    project
                    / "ai/tasks/archive/undated/alpha"
                    / Path(item["target_path"]).name
                )
                item["approval"]["scope"]["target_path"] = item["target_path"]
            with _home_env(home), self.assertRaises(ContractError) as caught:
                plan_migration(
                    [project],
                    vault,
                    "c",
                    _decisions(vault, items),
                    tool_versions={"onboard": "f", "graft": "0.18.0"},
                )
            self.assertEqual(caught.exception.code, "graph-conflict")

    def test_nested_task_files_belong_to_the_deepest_task_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            items = []
            _add_task(
                project,
                vault,
                items,
                task_id="parent",
                folder="09-parent",
                source_overrides={"children": ["09-parent/10-child"]},
            )
            _add_task(
                project,
                vault,
                items,
                task_id="child",
                folder="09-parent/10-child",
                source_overrides={"parent": "09-parent"},
                task_md_kwargs={"parent": "parent"},
            )
            manifest = _plan(project, vault, _decisions(vault, items), home)
            self.assertEqual(
                len(manifest["payload"]["publication_decisions"]["items"]), 4
            )

    def test_optional_private_task_attachment_is_covered_without_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)
            items = json.loads(decisions.read_text())["items"]
            attachment = next(
                item for item in items if item["item_id"].endswith("-prd")
            )
            attachment.update(
                required=False,
                decision="private-only",
                target_path=None,
                candidate_ref=None,
            )
            attachment["approval"]["scope"].update(
                decision="private-only", target_path=None, candidate_ref=None
            )
            manifest = _plan(project, vault, _decisions(vault, items), home)
            copied = {
                operation["target"]
                for operation in manifest["payload"]["projects"][0][
                    "private_operations"
                ]
                if operation["change"]["kind"].startswith("copy-")
            }
            self.assertNotIn(str(project / "ai/tasks/alpha/prd.md"), copied)


    def test_private_task_skip_and_spec_preservation_publish_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)
            items = json.loads(decisions.read_text())["items"]
            spec = next(item for item in items if item["item_id"] == "spec-auth")
            spec.update(
                required=False,
                decision="private-only",
                target_path=None,
                candidate_ref=None,
            )
            spec["approval"]["scope"].update(
                decision="private-only", target_path=None, candidate_ref=None
            )
            folder = project / ".trellis/tasks/00-bootstrap-guidelines"
            source = _legacy_source(
                id="bootstrap", name="bootstrap", status="in_progress"
            )
            _write(folder / "task.json", _json_bytes(source))
            _write(folder / "prd.md", b"private bootstrap notes\n")
            items.append(
                _item(
                    "skip-bootstrap",
                    [_ref(folder / "task.json"), _ref(folder / "prd.md")],
                    None,
                    "private-only",
                    None,
                    required=False,
                )
            )
            manifest = _plan(project, vault, _decisions(vault, items), home)
            targets = {
                operation["target"]
                for project_record in manifest["payload"]["projects"]
                for operation in project_record["private_operations"]
            }
            self.assertNotIn(str(project / "ai/tasks/bootstrap"), targets)
            self.assertNotIn(str(project / "ai/tasks/bootstrap/task.md"), targets)
            self.assertNotIn(str(project / "docs/spec/auth.md"), targets)
            self.assertFalse(any("handoffs" in target for target in targets))

    def test_skipped_unfinished_task_does_not_require_a_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            folder = project / ".trellis/tasks/00-bootstrap-guidelines"
            _write(
                folder / "task.json",
                _json_bytes(
                    _legacy_source(id="bootstrap", name="bootstrap", status="in_progress")
                ),
            )
            _write(folder / "prd.md", b"private bootstrap notes\n")
            _write(project / ".trellis/spec/auth.md", b"private spec\n")
            _write(project / ".trellis/workspace/journal.md", b"private journal\n")
            items = [
                _item(
                    "skip-bootstrap",
                    [_ref(folder / "task.json"), _ref(folder / "prd.md")],
                    None,
                    "private-only",
                    None,
                    required=False,
                ),
                _item(
                    "private-spec",
                    [_ref(project / ".trellis/spec/auth.md")],
                    None,
                    "private-only",
                    None,
                    required=False,
                ),
                _item(
                    "private-journal",
                    [_ref(project / ".trellis/workspace/journal.md")],
                    None,
                    "private-only",
                    None,
                    required=False,
                ),
            ]
            manifest = _plan(project, vault, _decisions(vault, items), home)
            targets = {
                operation["target"]
                for operation in manifest["payload"]["projects"][0]["private_operations"]
            }
            self.assertFalse(any("handoffs" in target or "bootstrap" in target for target in targets))

    def test_session_may_name_only_a_complete_private_skip(self):
        def build(base, current_task, *, partial=False):
            project = _base_tree(base)
            vault, home = base / "vault", base / "home"
            vault.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            folder = project / ".trellis/tasks/00-bootstrap-guidelines"
            _write(
                folder / "task.json",
                _json_bytes(
                    _legacy_source(id="bootstrap", name="bootstrap", status="in_progress")
                ),
            )
            _write(folder / "prd.md", b"private bootstrap notes\n")
            _write(project / ".trellis/spec/auth.md", b"private spec\n")
            _write(project / ".trellis/workspace/journal.md", b"private journal\n")
            session = project / ".trellis/.runtime/sessions/codex.json"
            _write(session, _json_bytes({"current_task": current_task, "current_run": None}))
            sources = [_ref(folder / "task.json")]
            if not partial:
                sources.append(_ref(folder / "prd.md"))
            items = [
                _item("skip-bootstrap", sources, None, "private-only", None, required=False),
                _item(
                    "private-spec",
                    [_ref(project / ".trellis/spec/auth.md")],
                    None,
                    "private-only",
                    None,
                    required=False,
                ),
                _item(
                    "private-journal",
                    [_ref(project / ".trellis/workspace/journal.md")],
                    None,
                    "private-only",
                    None,
                    required=False,
                ),
                _item(
                    "private-session",
                    [_ref(session)],
                    None,
                    "private-only",
                    None,
                    required=False,
                ),
            ]
            return project, vault, home, items

        with tempfile.TemporaryDirectory() as directory:
            project, vault, home, items = build(
                Path(directory).resolve(), ".trellis/tasks/00-bootstrap-guidelines"
            )
            manifest = _plan(project, vault, _decisions(vault, items), home)
            targets = {
                operation["target"]
                for operation in manifest["payload"]["projects"][0]["private_operations"]
            }
            self.assertFalse(any("handoffs" in target or "bootstrap" in target for target in targets))
        for current_task in ("../../outside", "/tmp/not-a-project-task", ".trellis/tasks/missing"):
            with self.subTest(current_task=current_task), tempfile.TemporaryDirectory() as directory:
                project, vault, home, items = build(Path(directory).resolve(), current_task)
                with self.assertRaises(ContractError) as caught:
                    _plan(project, vault, _decisions(vault, items), home)
                self.assertEqual(caught.exception.code, "graph-conflict")
        with tempfile.TemporaryDirectory() as directory:
            project, vault, home, items = build(
                Path(directory).resolve(),
                ".trellis/tasks/00-bootstrap-guidelines",
                partial=True,
            )
            with self.assertRaises(ContractError) as caught:
                _plan(project, vault, _decisions(vault, items), home)
            self.assertEqual(caught.exception.code, "approval-required")



    def test_partial_private_task_skip_still_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)
            items = json.loads(decisions.read_text())["items"]
            folder = project / ".trellis/tasks/00-keep-private"
            _write(
                folder / "task.json",
                _json_bytes(_legacy_source(id="kept", name="kept")),
            )
            _write(folder / "prd.md", b"still private\n")
            items.append(
                _item(
                    "partial-skip",
                    [_ref(folder / "task.json")],
                    None,
                    "private-only",
                    None,
                    required=False,
                )
            )
            with self.assertRaises(ContractError) as caught:
                _plan(project, vault, _decisions(vault, items), home)
            self.assertEqual(caught.exception.code, "approval-required")

    def test_private_only_lessons_still_require_a_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)
            items = json.loads(decisions.read_text())["items"]
            lessons = next(item for item in items if item["item_id"] == "lessons-tree")
            lessons.update(
                required=False,
                decision="private-only",
                target_path=None,
                candidate_ref=None,
            )
            lessons["approval"]["scope"].update(
                decision="private-only", target_path=None, candidate_ref=None
            )
            with self.assertRaises(ContractError) as caught:
                _plan(project, vault, _decisions(vault, items), home)
            self.assertEqual(caught.exception.code, "approval-required")

    def test_shared_markdown_links_need_a_planned_local_target(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)

            def update_spec(body):
                source = project / ".trellis/spec/auth.md"
                candidate = vault / "cand-spec/auth.md"
                _write(source, body)
                _write(candidate, body)
                items = json.loads(decisions.read_text())["items"]
                index = next(
                    i for i, item in enumerate(items) if item["item_id"] == "spec-auth"
                )
                items[index] = _item(
                    "spec-auth",
                    [_ref(source)],
                    project / "docs/spec/auth.md",
                    "share",
                    candidate,
                )
                return _decisions(vault, items)

            manifest = _plan(
                project,
                vault,
                update_spec(
                    b"[lesson](../lessons/index.md) [web](https://example.test)\n"
                    b"[http](http://example.test/x) [mail](mailto:dev@example.test)\n"
                    b"![inline](data:image/png;base64,AAAA)\n"
                ),
                home,
            )
            self.assertEqual(manifest["payload"]["projects"][0]["root"], str(project))
            for body in (
                b"[missing](missing.md)\n",
                b"[escape](../../outside.md)\n",
                b"[file](file:///outside.md)\n",
                b"[unsafe](javascript:alert%281%29)\n",
                b"[unsafe-data](data:text/html,test)\n",
                b"![missing](missing.png)\n",
                b"[drive](C:/outside.md)\n",
                b"[encoded-drive](C%3A%2Foutside.md)\n",
                b"[drive-relative](C:secret.md)\n",
                b"![drive-relative](c:secret.png)\n",
                b"![encoded-drive-relative](c%3Asecret.png)\n",
            ):
                with self.subTest(body=body):
                    with _home_env(home), self.assertRaises(ContractError) as caught:
                        plan_migration(
                            [project],
                            vault,
                            "c",
                            update_spec(body),
                            tool_versions={"onboard": "f", "graft": "0.18.0"},
                        )
                    self.assertEqual(caught.exception.code, "target-conflict")
                    self.assertEqual(caught.exception.exit_code, 2)

    def test_current_identity_precedes_malformed_legacy_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)
            _write(project / ".sbtd/developer", b"name=current9\n")
            _write(project / ".trellis/.developer", b"name=broken\nname=broken\n")
            manifest = _plan(project, vault, decisions, home)
            self.assertFalse(
                any(
                    op["change"]["kind"] == "migrate-developer"
                    for op in manifest["payload"]["projects"][0]["private_operations"]
                )
            )

    def test_existing_complete_ignore_protection_needs_no_duplicate_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, decisions = _full_fixture(base)
            _write(
                project / ".gitignore", sbtd_migration_plan._IGNORE_ASSET.read_bytes()
            )
            manifest = _plan(project, vault, decisions, home)
            project_record = manifest["payload"]["projects"][0]
            self.assertFalse(
                any(
                    operation["target"] == str(project / ".gitignore")
                    for operation in project_record["private_operations"]
                )
            )
            with _home_env(home):
                validate_legacy_inputs(manifest, _strict_reader)


class MigrationPlanSharedTests(unittest.TestCase):
    def test_drifted_shared_resources_are_preserved_without_operations(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            home = base / "home"
            home.mkdir(mode=0o700)
            _write(home / ".codex/AGENTS.md", b"# locally customized agents\n")
            _write(home / ".agent/skills/trellis-workflow/SKILL.md", b"custom\n")
            before = _tree_bytes(base)
            manifest = _plan(project, vault, None, home)
            self.assertEqual(manifest["payload"]["shared_operations"], [])
            self.assertEqual(_tree_bytes(base), before)

    def test_unrelated_shared_skills_are_preserved_without_blocking_retirement(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            home = base / "home"
            home.mkdir(mode=0o700)
            unrelated = home / ".agent/skills/unknown-skill/SKILL.md"
            _write(unrelated, b"name: other\n")
            outside = base / "unrelated-target"
            outside.mkdir()
            (home / ".agent/skills/unrelated-link").symlink_to(
                outside, target_is_directory=True
            )
            manifest = _plan(project, vault, None, home)
            self.assertEqual(manifest["payload"]["shared_operations"], [])
            self.assertEqual(unrelated.read_bytes(), b"name: other\n")

    def test_other_1_0_x_skill_bytes_are_retired_by_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            home = base / "home"
            home.mkdir(mode=0o700)
            skills_root = home / ".agent/skills"
            names = ("trellis-channel", "trellis-workflow")
            for name in names:
                _write(
                    skills_root / name / "SKILL.md",
                    f"---\nname: {name}\n---\n# different 1.0.x release\n".encode(),
                )
                _write(skills_root / name / "release.txt", b"not v1.0.15\n")
            pins = sbtd_migration_plan._ownership_pins()["skills"]
            for name in names:
                self.assertNotEqual(snapshot(skills_root / name), pins[name])
            manifest = _plan(project, vault, None, home)
            retired = [
                operation
                for operation in manifest["payload"]["shared_operations"]
                if operation["phase"] == "cleanup"
            ]
            self.assertEqual(
                [operation["ownership"]["name"] for operation in retired],
                list(names),
            )
            for operation in retired:
                state = snapshot(Path(operation["target"]))
                self.assertEqual(operation["before_requirement"]["state"], state)
                self.assertEqual(operation["ownership"]["reference"]["state"], state)
            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, _strict_reader))

    def test_same_named_foreign_skill_identity_is_not_retired(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            home = base / "home"
            home.mkdir(mode=0o700)
            impostor = home / ".agent/skills/trellis-channel/SKILL.md"
            _write(impostor, b"---\nname: user-owned-channel\n---\n# keep\n")
            manifest = _plan(project, vault, None, home)
            self.assertEqual(manifest["payload"]["shared_operations"], [])
            self.assertEqual(
                impostor.read_bytes(),
                b"---\nname: user-owned-channel\n---\n# keep\n",
            )



def _absorbed_skills_fixture(base):
    """Retired Skill below the platform-default skills root inside Codex HOME."""
    project = legacy_project(base, "project")
    vault = base / "vault"
    vault.mkdir(mode=0o700)
    home = base / "home"
    home.mkdir(mode=0o700)
    codex_home = home / ".codex"
    skill = codex_home / "skills" / "trellis-workflow"
    _write(skill / "SKILL.md", b"---\nname: trellis-workflow\n---\nlegacy skill\n")
    environment = {
        "HOME": str(home),
        "USERPROFILE": str(home),
        "CODEX_HOME": str(codex_home),
    }
    return project, vault, codex_home, skill, environment


def _plan_absorbed(project, vault, environment):
    with mock.patch.dict(os.environ, environment):
        os.environ.pop("AGENT_SKILLS_DIR", None)
        return plan_migration(
            [project],
            vault,
            "fixture-custodian",
            None,
            tool_versions={"onboard": "fixture", "graft": "0.18.0"},
            deployment_mode="init",
        )


def _validate_absorbed(manifest, environment, resolve_original=None):
    with mock.patch.dict(os.environ, environment):
        os.environ.pop("AGENT_SKILLS_DIR", None)
        return validate_legacy_inputs(manifest, _strict_reader, resolve_original)


class MigrationPlanAbsorbedSkillsRootTests(unittest.TestCase):
    def test_absorbed_skills_root_seals_its_logical_location(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, codex_home, skill, environment = _absorbed_skills_fixture(
                base
            )
            manifest = _plan_absorbed(project, vault, environment)
            payload = manifest["payload"]
            self.assertEqual(
                payload["shared_roots"],
                [
                    {
                        "kind": "codex-home",
                        "path": str(codex_home),
                        "skills_root": str(codex_home / "skills"),
                        "dependent_projects": [str(project)],
                    }
                ],
            )
            retired = [
                operation
                for operation in payload["shared_operations"]
                if operation["phase"] == "cleanup"
            ]
            self.assertEqual([operation["target"] for operation in retired], [str(skill)])
            self.assertIsNone(_validate_absorbed(manifest, environment))

    def test_resealed_same_named_target_under_home_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, codex_home, _skill, environment = _absorbed_skills_fixture(
                base
            )
            manifest = _plan_absorbed(project, vault, environment)
            decoy = codex_home / "user" / "trellis-workflow"
            _write(decoy / "SKILL.md", b"---\nname: trellis-workflow\n---\nuser copy\n")

            def mutate(payload):
                operation = next(
                    op
                    for op in payload["shared_operations"]
                    if op["phase"] == "cleanup"
                )
                target = str(decoy)
                state = snapshot(decoy)
                resource = contracts.resource_id("directory", target)
                operation["target"] = target
                operation["resource_id"] = resource
                operation["operation_id"] = contracts.operation_id(
                    "cleanup", resource, "whole-resource"
                )
                operation["ownership"]["reference"] = {"path": target, "state": state}
                operation["before_requirement"] = {"kind": "state", "state": state}
                payload["projects"][0]["shared_operation_ids"] = sorted(
                    op["operation_id"] for op in payload["shared_operations"]
                )

            tampered = _reseal(manifest, mutate)
            with (
                mock.patch.dict(os.environ, environment),
                self.assertRaises(ContractError) as caught,
            ):
                validate_legacy_inputs(tampered, _strict_reader)
            self.assertEqual(caught.exception.code, "semantic-violation")
            self.assertEqual(
                caught.exception.message, "a skill retirement target was altered"
            )

    def test_absorbed_retirement_revalidates_from_the_preserved_original(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, _codex_home, skill, environment = _absorbed_skills_fixture(
                base
            )
            manifest = _plan_absorbed(project, vault, environment)
            self.assertIsNone(_validate_absorbed(manifest, environment))
            preserved = base / "preserved" / "trellis-workflow"
            shutil.copytree(skill, preserved)
            shutil.rmtree(skill)

            def resolve_original(reference):
                return {"path": str(preserved), "state": reference["state"]}

            self.assertIsNone(
                _validate_absorbed(manifest, environment, resolve_original)
            )

    def test_absorbed_retirement_without_sealed_location_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, _codex_home, _skill, environment = _absorbed_skills_fixture(
                base
            )
            manifest = _plan_absorbed(project, vault, environment)

            def mutate(payload):
                for record in payload["shared_roots"]:
                    record.pop("skills_root", None)

            tampered = _reseal(manifest, mutate)
            with (
                mock.patch.dict(os.environ, environment),
                self.assertRaises(ContractError) as caught,
            ):
                validate_legacy_inputs(tampered, _strict_reader)
            self.assertEqual(caught.exception.code, "semantic-violation")
            self.assertEqual(
                caught.exception.message, "a skill retirement target was altered"
            )

    def test_merged_skills_root_still_requires_the_selected_direct_child(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _base_tree(base)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            home = base / "home"
            home.mkdir(mode=0o700)
            codex_home = home / ".codex"
            _write(codex_home / "AGENTS.md", b"pinned-global-agents\n")
            skill = codex_home / "skills" / "trellis-workflow"
            _write(skill / "SKILL.md", b"---\nname: trellis-workflow\n---\nlegacy skill\n")
            pins = sbtd_migration_plan._ownership_pins()
            pins["agents"] = hashlib.sha256(b"pinned-global-agents\n").hexdigest()
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(codex_home),
                "AGENT_SKILLS_DIR": str(codex_home / "skills"),
            }
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch.object(
                    sbtd_migration_plan, "_ownership_pins", return_value=pins
                ),
                mock.patch("onboard.user_home", return_value=home),
            ):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    None,
                    tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                )
            payload = manifest["payload"]
            self.assertEqual(
                payload["shared_roots"],
                [
                    {
                        "kind": "codex-home",
                        "path": str(codex_home),
                        "skills_root": str(codex_home / "skills"),
                        "dependent_projects": [str(project)],
                    }
                ],
            )
            # The sealed merged root binds validation: no deployment and no
            # ambient skills dir are needed to re-prove it.
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch.object(
                    sbtd_migration_plan, "_ownership_pins", return_value=pins
                ),
                mock.patch("onboard.user_home", return_value=home),
            ):
                os.environ.pop("AGENT_SKILLS_DIR", None)
                self.assertIsNone(
                    sbtd_migration_plan._validate_shared_operations(
                        payload, [str(project)]
                    )
                )
            decoy = codex_home / "user" / "trellis-workflow"
            _write(decoy / "SKILL.md", b"---\nname: trellis-workflow\n---\nuser copy\n")

            def mutate(payload):
                operation = next(
                    op
                    for op in payload["shared_operations"]
                    if op["phase"] == "cleanup"
                )
                target = str(decoy)
                state = snapshot(decoy)
                resource = contracts.resource_id("directory", target)
                operation["target"] = target
                operation["resource_id"] = resource
                operation["operation_id"] = contracts.operation_id(
                    "cleanup", resource, "whole-resource"
                )
                operation["ownership"]["reference"] = {"path": target, "state": state}
                operation["before_requirement"] = {"kind": "state", "state": state}
                payload["projects"][0]["shared_operation_ids"] = sorted(
                    op["operation_id"] for op in payload["shared_operations"]
                )

            tampered = _reseal(manifest, mutate)
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch.object(
                    sbtd_migration_plan, "_ownership_pins", return_value=pins
                ),
                mock.patch("onboard.user_home", return_value=home),
                self.assertRaises(ContractError) as caught,
            ):
                validate_legacy_inputs(tampered, _strict_reader)
            self.assertEqual(caught.exception.code, "semantic-violation")
            self.assertEqual(
                caught.exception.message, "a skill retirement target was altered"
            )



def _strict_reader(reference):
    from sbtd_migration_files import read_file

    return read_file(Path(reference["path"]), reference["state"])


def _reseal(manifest, mutate):
    payload = json.loads(json.dumps(manifest["payload"]))
    mutate(payload)
    return contracts.seal_document("manifest", payload)


class MigrationPlanOperationGateTests(unittest.TestCase):
    """Re-sealed manifests with altered operation sets must not validate."""

    def _planned(self, base):
        project, vault, home, decisions = _full_fixture(base)
        manifest = _plan(project, vault, decisions, home)
        with _home_env(home):
            self.assertIsNone(validate_legacy_inputs(manifest, _strict_reader))
        return project, vault, home, manifest

    def test_resealed_redundant_ignore_operation_is_rejected_from_original_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, _vault, home, manifest = self._planned(base)
            _write(
                project / ".gitignore", sbtd_migration_plan._IGNORE_ASSET.read_bytes()
            )

            def make_redundant(payload):
                operation = next(
                    op
                    for op in payload["projects"][0]["private_operations"]
                    if op["owner_kind"] == "gitignore"
                )
                operation["before_requirement"]["state"] = snapshot(
                    project / ".gitignore"
                )

            tampered = _reseal(manifest, make_redundant)
            with _home_env(home), self.assertRaises(ContractError) as caught:
                validate_legacy_inputs(tampered, _strict_reader)
            self.assertEqual(caught.exception.code, "semantic-violation")

    def test_invented_private_operation_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            _project, _vault, home, manifest = self._planned(base)
            hashes_ref = None
            for op in manifest["payload"]["projects"][0]["private_operations"]:
                if (
                    op["ownership"]["kind"] == "template-source"
                    and op["change"] == {"kind": "remove"}
                    and op["phase"] == "apply"
                ):
                    hashes_ref = op["ownership"]["reference"]
            self.assertIsNotNone(hashes_ref)

            def mutate(payload):
                target = str(Path(payload["projects"][0]["root"]) / "app.py")
                resource = contracts.resource_id("file", target)
                payload["projects"][0]["private_operations"].append(
                    {
                        "operation_id": contracts.operation_id(
                            "apply", resource, "whole-resource"
                        ),
                        "phase": "apply",
                        "resource_id": resource,
                        "owner_kind": "file",
                        "target": target,
                        "selector": "whole-resource",
                        "change": {"kind": "remove"},
                        "ownership": {
                            "kind": "template-source",
                            "reference": hashes_ref,
                        },
                        "before_requirement": {
                            "kind": "state",
                            "state": {"type": "file", "checksum": "ab" * 32},
                        },
                        "dependent_projects": [payload["projects"][0]["root"]],
                    }
                )

            tampered = _reseal(manifest, mutate)
            with _home_env(home), self.assertRaises(ContractError):
                validate_legacy_inputs(tampered, _strict_reader)

    def test_missing_protection_or_output_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            _project, _vault, home, manifest = self._planned(base)

            def drop_protection(payload):
                ops = payload["projects"][0]["private_operations"]
                payload["projects"][0]["private_operations"] = [
                    op for op in ops if op["owner_kind"] != "gitignore"
                ]

            tampered = _reseal(manifest, drop_protection)
            with _home_env(home), self.assertRaises(ContractError):
                validate_legacy_inputs(tampered, _strict_reader)

            def drop_output(payload):
                ops = payload["projects"][0]["private_operations"]
                payload["projects"][0]["private_operations"] = [
                    op for op in ops if op["change"]["kind"] != "copy-directory"
                ]

            with self.assertRaises(ContractError):
                # The codec itself already refuses an unmatched approval.
                _reseal(manifest, drop_output)

    def test_altered_identity_or_platform_ownership_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            _project, _vault, home, manifest = self._planned(base)

            def rename_identity(payload):
                for op in payload["projects"][0]["private_operations"]:
                    if op["change"].get("kind") == "migrate-developer":
                        op["change"]["name"] = "other9"

            tampered = _reseal(manifest, rename_identity)
            with _home_env(home), self.assertRaises(ContractError):
                validate_legacy_inputs(tampered, _strict_reader)

            def fake_platform_state(payload):
                for op in payload["projects"][0]["private_operations"]:
                    if op["change"] == {"kind": "remove"} and op["phase"] == "apply":
                        op["ownership"]["reference"]["state"] = {
                            "type": "file",
                            "checksum": "cd" * 32,
                        }

            tampered = _reseal(manifest, fake_platform_state)
            with _home_env(home), self.assertRaises(ContractError):
                validate_legacy_inputs(tampered, _strict_reader)

    def test_invented_shared_operation_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            _project, _vault, home, manifest = self._planned(base)

            def mutate(payload):
                root = payload["projects"][0]["root"]
                shared_root = str(Path(root).parent)
                target = str(Path(shared_root) / "AGENTS.md")
                resource = contracts.resource_id("markdown", target)
                operation_id = contracts.operation_id(
                    "apply", resource, "pause-legacy-routing"
                )
                payload["shared_roots"].append(
                    {
                        "kind": "codex-home",
                        "path": shared_root,
                        "dependent_projects": [payload["projects"][0]["root"]],
                    }
                )
                payload["shared_operations"].append(
                    {
                        "operation_id": operation_id,
                        "phase": "apply",
                        "resource_id": resource,
                        "owner_kind": "markdown",
                        "target": target,
                        "selector": "pause-legacy-routing",
                        "change": {
                            "kind": "ensure-file-block",
                            "source_ref": {
                                "path": target,
                                "state": {"type": "file", "checksum": "ef" * 32},
                            },
                        },
                        "ownership": {
                            "kind": "template-source",
                            "reference": {
                                "path": target,
                                "state": {"type": "file", "checksum": "ef" * 32},
                            },
                        },
                        "before_requirement": {
                            "kind": "state",
                            "state": {"type": "file", "checksum": "ef" * 32},
                        },
                        "dependent_projects": [payload["projects"][0]["root"]],
                    }
                )
                payload["projects"][0]["shared_operation_ids"] = [operation_id]

            tampered = _reseal(manifest, mutate)
            with _home_env(home), self.assertRaises(ContractError):
                validate_legacy_inputs(tampered, _strict_reader)


class MigrationContextHandoffTests(unittest.TestCase):
    def fixture(self, base):
        project = _base_tree(base)
        vault = base / "vault"
        vault.mkdir(mode=0o700)
        home = base / "home"
        home.mkdir(mode=0o700)
        items = []
        _add_task(project, vault, items)
        journal = project / ".trellis/workspace/dev01/journal-1.md"
        session = project / ".trellis/.runtime/sessions/codex_fixture.json"
        _write(journal, b"# Work remaining\nFinish alpha validation.\n")
        _write(
            session,
            _json_bytes(
                {
                    "platform": "codex",
                    "last_seen_at": "2026-09-21T10:00:00Z",
                    "current_task": ".trellis/tasks/09-01-alpha",
                    "current_run": None,
                }
            ),
        )
        return project, vault, home, items, [journal, session]

    def approve(self, project, vault, items, sources, *, task_id="alpha"):
        from sbtd_handoff import _REDACTION_DECLARATION, HandoffStore
        from sbtd_task_state import TaskStore

        handoff = {
            "schema_version": 1,
            "task_id": task_id,
            "task_path": f"ai/tasks/{task_id}/task.md",
            "task_status": "planned",
            "workflow_mode": None,
            "mode_source": "migration-unknown",
            "mode_note": "legacy Trellis task without mode proof",
            "project_root": str(project),
            "branch": None,
            "head": None,
            "created_at": "2026-09-21T10:00:00+00:00",
            "content": {
                "goal": "Complete the migrated task",
                "decisions": ["Keep migration approval separate from continuation"],
                "completed": ["Implementation"],
                "remaining": ["Run validation"],
                "changed_files": [],
                "verification": [],
                "do_not_repeat": ["Do not restore retired routing"],
                "next_action": "Inspect the task and run its validation",
                "limitations": "Legacy mode is unproven",
            },
            "policy": {"task_opt_out": False, "session_opt_out": False},
            "redaction": _REDACTION_DECLARATION,
        }
        store = HandoffStore(TaskStore(project, read_only=True))
        name = "2026_09_21-" + hashlib.sha256(task_id.encode()).hexdigest() + ".md"
        candidate = vault / f"handoff-{task_id}.md"
        candidate.write_text(store._render(handoff), encoding="utf-8")
        target = project / "docs/handoffs" / name
        items.append(
            _item(
                f"handoff-{task_id}",
                [_ref(path) for path in sources],
                target,
                "redact",
                candidate,
            )
        )
        return target, candidate

    def test_negated_handoff_protection_blocks_plan_without_writes(self):
        for nested in (False, True):
            with (
                self.subTest(nested=nested),
                tempfile.TemporaryDirectory() as directory,
            ):
                base = Path(directory).resolve()
                project, vault, home, items, sources = self.fixture(base)
                (project / ".gitignore").write_text("/docs/handoffs\n")
                if nested:
                    _write(project / "docs/.gitignore", b"!handoffs/\n")
                else:
                    (project / ".gitignore").write_text(
                        "/docs/handoffs\n!/docs/handoffs\n"
                    )
                self.approve(project, vault, items, sources)
                decisions = _decisions(vault, items)
                before = _tree_bytes(base)
                with self.assertRaises(ContractError) as error:
                    _plan(project, vault, decisions, home)
                self.assertEqual(error.exception.code, "private-scope")
                self.assertEqual(_tree_bytes(base), before)

    def test_unfinished_context_requires_approved_handoff_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items, _ = self.fixture(base)
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            with self.assertRaises(ContractError) as error:
                _plan(project, vault, decisions, home)
            self.assertEqual(error.exception.code, "approval-required")
            self.assertEqual(_tree_bytes(base), before)

    def test_approved_handoff_is_readable_after_apply_and_originals_are_recoverable(
        self,
    ):
        from sbtd_handoff import HandoffStore
        from sbtd_migration import apply_migration, runtime_versions
        from sbtd_task_state import TaskStore

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items, sources = self.fixture(base)
            originals = {path: path.read_bytes() for path in sources}
            target, candidate = self.approve(project, vault, items, sources)
            decisions = _decisions(vault, items)
            with _home_env(home):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    decisions,
                    tool_versions=runtime_versions(),
                )
                manifest_path = vault / "manifest.json"
                manifest_path.write_bytes(contracts.canonical_json_bytes(manifest))
                receipt, code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
                self.assertEqual(code, 0, receipt)
                receipt_path = vault / "apply.json"
                receipt_path.write_bytes(
                    contracts.canonical_json_bytes(
                        receipt["migration"]["apply_receipt"]
                    )
                )
                repeated, code = apply_migration(
                    manifest_path,
                    previous_receipt_path=receipt_path,
                    confirmed=True,
                    no_routing_approvals=True,
                )
                self.assertEqual(code, 0, repeated)
                loaded = HandoffStore(TaskStore(project, read_only=True)).load(
                    target.relative_to(project).as_posix()
                )
            self.assertEqual(loaded["content"]["remaining"], ["Run validation"])
            self.assertEqual(target.read_bytes(), candidate.read_bytes())
            self.assertFalse((project / ".sbtd/active-task.json").exists())
            self.assertIn("/docs/handoffs", (project / ".gitignore").read_text())
            from sbtd_migration import _source_backup_paths

            backup = _source_backup_paths(manifest)[str(project / ".trellis")]
            for path, raw in originals.items():
                self.assertEqual(path.read_bytes(), raw)
                self.assertEqual(
                    (backup / path.relative_to(project / ".trellis")).read_bytes(), raw
                )

    def test_handoff_approval_must_cover_every_original_context_file(self):
        with tempfile.TemporaryDirectory() as directory:
            project, vault, home, items, sources = self.fixture(
                Path(directory).resolve()
            )
            self.approve(project, vault, items, sources[:1])
            with self.assertRaises(ContractError) as error:
                _plan(project, vault, _decisions(vault, items), home)
            self.assertEqual(error.exception.code, "approval-conflict")

    def test_invalid_session_reference_is_not_guessed_from_journal(self):
        for reference in ("../../outside", ".trellis/tasks/missing"):
            with (
                self.subTest(reference=reference),
                tempfile.TemporaryDirectory() as directory,
            ):
                project, vault, home, items, sources = self.fixture(
                    Path(directory).resolve()
                )
                sources[1].write_bytes(_json_bytes({"current_task": reference}))
                self.approve(project, vault, items, sources)
                with self.assertRaises(ContractError) as error:
                    _plan(project, vault, _decisions(vault, items), home)
                self.assertEqual(error.exception.code, "graph-conflict")

    def test_session_only_context_requires_its_task_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            project, vault, home, items, sources = self.fixture(
                Path(directory).resolve()
            )
            sources[0].unlink()
            with self.assertRaises(ContractError) as error:
                _plan(project, vault, _decisions(vault, items), home)
            self.assertEqual(error.exception.code, "approval-required")
            self.approve(project, vault, items, sources[1:])
            manifest = _plan(project, vault, _decisions(vault, items), home)
            self.assertTrue(
                any(
                    "/docs/handoffs/" in operation["target"]
                    for operation in manifest["payload"]["projects"][0][
                        "private_operations"
                    ]
                )
            )

    def test_journals_require_each_unfinished_task_without_selecting_one(self):
        with tempfile.TemporaryDirectory() as directory:
            project, vault, home, items, sources = self.fixture(
                Path(directory).resolve()
            )
            _add_task(project, vault, items, task_id="beta", folder="09-02-beta")
            self.approve(project, vault, items, sources)
            with self.assertRaises(ContractError) as error:
                _plan(project, vault, _decisions(vault, items), home)
            self.assertEqual(error.exception.code, "approval-required")
            self.approve(project, vault, items, sources, task_id="beta")
            _plan(project, vault, _decisions(vault, items), home)
            self.assertFalse((project / ".sbtd/active-task.json").exists())

    def test_unknown_session_structure_and_legacy_path_line_fail_closed(self):
        for path_line in (False, True):
            with (
                self.subTest(path_line=path_line),
                tempfile.TemporaryDirectory() as directory,
            ):
                project, vault, home, items, sources = self.fixture(
                    Path(directory).resolve()
                )
                if path_line:
                    _write(
                        project / ".trellis/.current-task",
                        b".trellis/tasks/09-01-alpha\n",
                    )
                else:
                    sources[1].write_bytes(
                        _json_bytes({"future_task_pointer": "alpha"})
                    )
                self.approve(project, vault, items, sources)
                with self.assertRaises(ContractError) as error:
                    _plan(project, vault, _decisions(vault, items), home)
                self.assertEqual(error.exception.code, "invalid-config")

def _routing_batch(base):
    project = base / "project"
    (project / ".trellis").mkdir(parents=True)
    (project / ".codex/agents").mkdir(parents=True)
    (project / ".trellis/.developer").write_bytes(LEGACY_IDENTITY)
    owned = b'name = "trellis-implement"\n'
    relative = ".codex/agents/trellis-implement.toml"
    (project / relative).write_bytes(owned)
    (project / ".trellis/.template-hashes.json").write_text(
        json.dumps(
            {
                "__version": 2,
                "hashes": {relative: hashlib.sha256(owned).hexdigest()},
            }
        )
    )
    (project / ".trellis/.version").write_text("0.6.17\n")
    home = base / "home"
    vault = base / "vault"
    evidence = base / "evidence"
    for path in (home, vault, evidence):
        path.mkdir(mode=0o700)
    pause = (SCRIPTS.parents[0] / "assets" / "migration-paused-agents.txt").read_bytes()
    environment = {
        "HOME": str(home),
        "USERPROFILE": str(home),
        "CODEX_HOME": str(home / ".codex"),
        "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
    }
    return project, home, vault, evidence, pause, environment


def _routing_approval(path, role, target, candidate):
    path.write_bytes(
        json.dumps(
            {
                "schema_version": 1,
                "items": [
                    {
                        "role": role,
                        "target_path": str(target),
                        "before": snapshot(target),
                        "candidate_ref": {
                            "path": str(candidate),
                            "state": snapshot(candidate),
                        },
                        "basis": "fixture custodian approval",
                    }
                ],
            }
        ).encode("utf-8")
    )
    return _sign_existing_approval(path)


def _plan_routing(project, vault, approval, environment):
    with mock.patch.dict(os.environ, environment):
        return plan_migration(
            [project],
            vault,
            "fixture",
            None,
            tool_versions={"onboard": "fixture", "graft": "0.18.0"},
            routing_approvals=approval,
        )


class ApprovedRoutingReplacementTests(unittest.TestCase):
    def test_approved_candidate_is_copied_and_reopened(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = base / "project"
            (project / ".trellis").mkdir(parents=True)
            (project / ".codex/agents").mkdir(parents=True)
            (project / ".trellis/.developer").write_bytes(LEGACY_IDENTITY)
            owned = b'name = "trellis-implement"\n'
            relative = ".codex/agents/trellis-implement.toml"
            (project / relative).write_bytes(owned)
            (project / ".trellis/.template-hashes.json").write_text(
                json.dumps(
                    {
                        "__version": 2,
                        "hashes": {relative: hashlib.sha256(owned).hexdigest()},
                    }
                )
            )
            (project / ".trellis/.version").write_text("0.6.17\n")
            home = base / "home"
            vault = base / "vault"
            evidence = base / "evidence"
            for path in (home, vault, evidence):
                path.mkdir(mode=0o700)
            live = home / ".codex" / "AGENTS.md"
            live.parent.mkdir(parents=True)
            live.write_bytes(b"custom trellis routing\n")
            pause = (
                SCRIPTS.parents[0] / "assets" / "migration-paused-agents.txt"
            ).read_bytes()
            candidate = vault / "routing-candidate.md"
            candidate.write_bytes(pause + b"\napproved replacement\n")
            approval = vault / "routing-approvals.json"
            approval.write_bytes(
                json.dumps(
                    {
                        "schema_version": 1,
                        "items": [
                            {
                                "role": "codex-global",
                                "target_path": str(live),
                                "before": snapshot(live),
                                "candidate_ref": {
                                    "path": str(candidate),
                                    "state": snapshot(candidate),
                                },
                                "basis": "fixture custodian approval",
                            }
                        ],
                    }
                ).encode("utf-8")
            )
            _sign_existing_approval(approval)
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(home / ".codex"),
                "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
            }
            with mock.patch.dict(os.environ, environment):
                with self.assertRaises(ContractError) as blocked:
                    plan_migration(
                        [project],
                        vault,
                        "fixture",
                        None,
                        tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                    )
                self.assertIn(blocked.exception.code, {"ownership-conflict", "semantic-violation"})
                before_plan = live.read_bytes()
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture",
                    None,
                    tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                    routing_approvals=approval,
                )
                self.assertEqual(live.read_bytes(), before_plan)
                replacements = [
                    operation
                    for operation in manifest["payload"]["shared_operations"]
                    if operation["selector"] == "approved-routing-replacement"
                ]
                self.assertEqual(len(replacements), 1)
                operation = replacements[0]
                self.assertEqual(operation["change"]["kind"], "copy-file")
                self.assertEqual(operation["ownership"]["kind"], "approved-candidate")
                self.assertFalse(
                    any(
                        item["target"] == str(live)
                        and item["selector"] == "pause-legacy-routing"
                        for item in manifest["payload"]["shared_operations"]
                    )
                )
                validate_legacy_inputs(manifest, _reader)
                from onboard_contracts import canonical_json_bytes
                from sbtd_migration import apply_migration

                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(manifest))
                with mock.patch(
                    "sbtd_migration.runtime_versions",
                    return_value={"onboard": "fixture", "graft": "0.18.0"},
                ):
                    response, code = apply_migration(
                        manifest_path,
                        confirmed=True,
                        routing_approvals=approval,
                    )
                self.assertEqual(code, 0, response)
                self.assertEqual(live.read_bytes(), candidate.read_bytes())
                validate_legacy_inputs(
                    manifest,
                    _receipt_reader(
                        manifest, response["migration"]["apply_receipt"]
                    ),
                )
                candidate.write_bytes(pause + b"\nchanged after approval\n")
                from sbtd_migration_verify import _check_approved_routing

                with self.assertRaises(ContractError) as drifted:
                    _check_approved_routing(manifest)
                self.assertEqual(drifted.exception.code, "approved-routing-drift")


    def test_receipt_retry_skips_an_applied_routing_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, home, vault, evidence, pause, environment = _routing_batch(base)
            live = home / ".codex" / "AGENTS.md"
            live.parent.mkdir(parents=True)
            live.write_bytes(b"custom trellis routing\n")
            candidate = vault / "routing-candidate.md"
            candidate.write_bytes(pause + b"\napproved replacement\n")
            approval = _routing_approval(
                vault / "routing-approvals.json", "codex-global", live, candidate
            )
            manifest = _plan_routing(project, vault, approval, environment)
            from onboard_contracts import canonical_json_bytes
            from sbtd_migration import apply_migration

            manifest_path = evidence / "manifest.json"
            manifest_path.write_bytes(canonical_json_bytes(manifest))
            versions = {"onboard": "fixture", "graft": "0.18.0"}
            with mock.patch.dict(os.environ, environment), mock.patch(
                "sbtd_migration.runtime_versions", return_value=versions
            ):
                response, code = apply_migration(
                    manifest_path, confirmed=True, routing_approvals=approval
                )
                self.assertEqual(code, 0, response)
                applied = live.read_bytes()
                self.assertEqual(applied, candidate.read_bytes())
                receipt = response["migration"]["apply_receipt"]
                saved = evidence / f"apply-{receipt['apply_id']}.json"
                retried, retry_code = apply_migration(
                    manifest_path,
                    previous_receipt_path=saved,
                    confirmed=True,
                    routing_approvals=approval,
                )
                self.assertEqual(retry_code, 0, retried)
                self.assertEqual(retried["status"], "already-complete")
                self.assertEqual(live.read_bytes(), applied)
                live.write_bytes(applied + b"tampered\n")
                with self.assertRaises(ContractError) as conflict:
                    apply_migration(
                        manifest_path,
                        previous_receipt_path=saved,
                        confirmed=True,
                        routing_approvals=approval,
                    )
            self.assertEqual(conflict.exception.code, "retry-conflict")
            self.assertEqual(live.read_bytes(), applied + b"tampered\n")

    def test_listed_predecessor_retry_requires_a_matching_receipt(self):
        predecessor = (
            "runtime-sha256:27e74bf511e8b62ad6dac07188933811bd429a84b38b8f01ae025e997fdd7750"
        )
        sealed = {"onboard": predecessor, "graft": "0.18.0"}
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, home, vault, evidence, pause, environment = _routing_batch(base)
            live = home / ".codex" / "AGENTS.md"
            live.parent.mkdir(parents=True)
            live.write_bytes(b"custom trellis routing\n")
            candidate = vault / "routing-candidate.md"
            candidate.write_bytes(pause + b"\napproved replacement\n")
            approval = _routing_approval(
                vault / "routing-approvals.json", "codex-global", live, candidate
            )
            with mock.patch.dict(os.environ, environment):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture",
                    None,
                    tool_versions=sealed,
                    routing_approvals=approval,
                )
            from onboard_contracts import canonical_json_bytes
            from sbtd_migration import apply_migration

            manifest_path = evidence / "manifest.json"
            manifest_path.write_bytes(canonical_json_bytes(manifest))
            with mock.patch.dict(os.environ, environment), mock.patch(
                "sbtd_migration.runtime_versions", return_value=sealed
            ):
                response, code = apply_migration(
                    manifest_path, confirmed=True, routing_approvals=approval
                )
            self.assertEqual(code, 0, response)
            applied = live.read_bytes()
            receipt = response["migration"]["apply_receipt"]
            saved = evidence / f"apply-{receipt['apply_id']}.json"
            unlisted = {"onboard": "runtime-sha256:unlisted-successor", "graft": "0.18.0"}
            with mock.patch.dict(os.environ, environment), mock.patch(
                "sbtd_migration.runtime_versions", return_value=unlisted
            ):
                with self.assertRaises(ContractError) as rejected:
                    apply_migration(
                        manifest_path,
                        previous_receipt_path=saved,
                        confirmed=True,
                        routing_approvals=approval,
                    )
            self.assertEqual(rejected.exception.code, "version-conflict")
            self.assertEqual(live.read_bytes(), applied)
            from sbtd_migration import _verified_runtime_pair

            _predecessor, paired = _verified_runtime_pair()
            successor = {"onboard": paired, "graft": "0.18.0"}
            with mock.patch.dict(os.environ, environment), mock.patch(
                "sbtd_migration.runtime_versions", return_value=successor
            ):
                with self.assertRaises(ContractError) as missing:
                    apply_migration(
                        manifest_path, confirmed=True, routing_approvals=approval
                    )
                self.assertEqual(missing.exception.code, "version-conflict")
                self.assertEqual(live.read_bytes(), applied)
                retried, retry_code = apply_migration(
                    manifest_path,
                    previous_receipt_path=saved,
                    confirmed=True,
                    routing_approvals=approval,
                )
                self.assertEqual(retry_code, 0, retried)
                self.assertEqual(retried["status"], "already-complete")
                self.assertEqual(live.read_bytes(), applied)
                live.write_bytes(applied + b"tampered\n")
                with self.assertRaises(ContractError) as drifted:
                    apply_migration(
                        manifest_path,
                        previous_receipt_path=saved,
                        confirmed=True,
                        routing_approvals=approval,
                    )
            self.assertEqual(drifted.exception.code, "lineage-conflict")
            self.assertEqual(live.read_bytes(), applied + b"tampered\n")




    def test_candidate_without_the_pause_prefix_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            vault = base / "vault"
            project = base / "project"
            for path in (home, vault, project / ".trellis"):
                path.mkdir(parents=True, mode=0o700)
            live = home / ".codex" / "AGENTS.md"
            live.parent.mkdir(parents=True)
            live.write_bytes(b"custom trellis routing\n")
            candidate = vault / "routing-candidate.md"
            candidate.write_bytes(b"approved replacement without pause\n")
            approval = vault / "routing-approvals.json"
            approval.write_bytes(
                json.dumps(
                    {
                        "schema_version": 1,
                        "items": [
                            {
                                "role": "codex-global",
                                "target_path": str(live),
                                "before": snapshot(live),
                                "candidate_ref": {
                                    "path": str(candidate),
                                    "state": snapshot(candidate),
                                },
                                "basis": "fixture custodian approval",
                            }
                        ],
                    }
                ).encode("utf-8")
            )
            _sign_existing_approval(approval)
            with mock.patch.dict(
                os.environ,
                {
                    "HOME": str(home),
                    "USERPROFILE": str(home),
                    "CODEX_HOME": str(home / ".codex"),
                    "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
                },
            ), self.assertRaises(ContractError) as error:
                plan_migration(
                    [project],
                    vault,
                    "fixture",
                    None,
                    tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                    routing_approvals=approval,
                )
            self.assertEqual(error.exception.code, "candidate-conflict")

    def test_retry_block_refuses_a_partial_write(self):
        from sbtd_migration import _retry_block

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "AGENTS.md"
            target.write_bytes(b"partial\n")
            self.assertEqual(
                _retry_block(
                    {
                        "after": snapshot(target),
                        "before": {"type": "absent", "checksum": None},
                        "status": "failed",
                        "error": "post-state-conflict",
                    },
                    target,
                ),
                "unsafe-retry",
            )

    def test_resealed_routing_operation_must_match_the_approval_record(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = base / "project"
            (project / ".trellis").mkdir(parents=True)
            (project / ".codex/agents").mkdir(parents=True)
            (project / ".trellis/.developer").write_bytes(LEGACY_IDENTITY)
            owned = b'name = "trellis-implement"\n'
            relative = ".codex/agents/trellis-implement.toml"
            (project / relative).write_bytes(owned)
            (project / ".trellis/.template-hashes.json").write_text(
                json.dumps(
                    {
                        "__version": 2,
                        "hashes": {relative: hashlib.sha256(owned).hexdigest()},
                    }
                )
            )
            (project / ".trellis/.version").write_text("0.6.17\n")
            home = base / "home"
            vault = base / "vault"
            evidence = base / "evidence"
            for path in (home, vault, evidence):
                path.mkdir(mode=0o700)
            live = home / ".codex" / "AGENTS.md"
            live.parent.mkdir(parents=True)
            before_live = b"custom trellis routing\n"
            live.write_bytes(before_live)
            pause = (
                SCRIPTS.parents[0] / "assets" / "migration-paused-agents.txt"
            ).read_bytes()
            candidate = vault / "routing-candidate.md"
            candidate.write_bytes(pause + b"\napproved replacement\n")
            approval = vault / "routing-approvals.json"
            approval.write_bytes(
                json.dumps(
                    {
                        "schema_version": 1,
                        "items": [
                            {
                                "role": "codex-global",
                                "target_path": str(live),
                                "before": snapshot(live),
                                "candidate_ref": {
                                    "path": str(candidate),
                                    "state": snapshot(candidate),
                                },
                                "basis": "fixture custodian approval",
                            }
                        ],
                    }
                ).encode("utf-8")
            )
            _sign_existing_approval(approval)
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(home / ".codex"),
                "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
            }
            with mock.patch.dict(os.environ, environment):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture",
                    None,
                    tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                    routing_approvals=approval,
                )
                from sbtd_migration import _all_input_references, _original_reference

                approval_refs = [
                    reference
                    for reference in _all_input_references(manifest)
                    if reference["path"] == str(approval)
                ]
                self.assertEqual(
                    approval_refs,
                    [{"path": str(approval), "state": snapshot(approval)}],
                )


                def change_role(payload):
                    operation = next(
                        item
                        for item in payload["shared_operations"]
                        if item["selector"] == "approved-routing-replacement"
                    )
                    operation["ownership"]["role"] = "omp-global"

                with self.assertRaises(ContractError) as role_error:
                    validate_legacy_inputs(_reseal(manifest, change_role), _reader)
                self.assertEqual(role_error.exception.code, "approval-conflict")
                outside = base / "outside-candidate.md"
                outside.write_bytes(candidate.read_bytes())

                def point_outside(payload):
                    operation = next(
                        item
                        for item in payload["shared_operations"]
                        if item["selector"] == "approved-routing-replacement"
                    )
                    forged = {"path": str(outside), "state": snapshot(outside)}
                    operation["change"]["source_ref"] = forged
                    operation["ownership"]["reference"] = forged

                tampered = _reseal(manifest, point_outside)
                with self.assertRaises(ContractError) as scope_error:
                    validate_legacy_inputs(tampered, _reader)
                self.assertEqual(scope_error.exception.code, "private-scope")
                from onboard_contracts import canonical_json_bytes
                from sbtd_migration import apply_migration

                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(tampered))
                with mock.patch(
                    "sbtd_migration.runtime_versions",
                    return_value={"onboard": "fixture", "graft": "0.18.0"},
                ), self.assertRaises(ContractError):
                    apply_migration(manifest_path, confirmed=True)
                self.assertEqual(live.read_bytes(), before_live)
                approval.write_bytes(approval.read_bytes() + b"\n")
                with self.assertRaises(ContractError) as drifted:
                    _original_reference(approval_refs[0], manifest)
                self.assertEqual(drifted.exception.code, "state-conflict")
                with self.assertRaises(ContractError) as rebound:
                    validate_legacy_inputs(manifest, _reader)
                self.assertEqual(rebound.exception.code, "state-conflict")

    def test_omp_global_candidate_is_copied_and_a_wrong_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, home, vault, evidence, pause, environment = _routing_batch(base)
            live = home / ".omp" / "agent" / "AGENTS.md"
            candidate = vault / "routing-candidate.md"
            candidate.write_bytes(pause + b"\napproved omp replacement\n")
            approval = vault / "routing-approvals.json"
            approval.write_bytes(
                json.dumps(
                    {
                        "schema_version": 1,
                        "items": [
                            {
                                "role": "omp-global",
                                "target_path": str(live),
                                "before": {"type": "absent", "checksum": None},
                                "candidate_ref": {
                                    "path": str(candidate),
                                    "state": snapshot(candidate),
                                },
                                "basis": "fixture custodian approval",
                            }
                        ],
                    }
                ).encode("utf-8")
            )
            _sign_existing_approval(approval)
            with (
                mock.patch.dict(os.environ, environment),
                self.assertRaises(ContractError) as missing,
            ):
                plan_migration(
                    [project],
                    vault,
                    "fixture",
                    None,
                    tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                    routing_approvals=approval,
                )
            self.assertEqual(missing.exception.code, "ownership-conflict")
            live.parent.mkdir(parents=True)
            live.write_bytes(b"custom trellis omp routing\n")
            wrong = home / ".omp" / "AGENTS.md"
            wrong.write_bytes(b"custom trellis omp routing\n")
            _routing_approval(approval, "omp-global", wrong, candidate)
            with (
                mock.patch.dict(os.environ, environment),
                self.assertRaises(ContractError) as wrong_path,
            ):
                plan_migration(
                    [project],
                    vault,
                    "fixture",
                    None,
                    tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                    routing_approvals=approval,
                )
            self.assertEqual(wrong_path.exception.code, "approval-conflict")
            with (
                mock.patch.dict(os.environ, environment),
                self.assertRaises(ContractError) as blocked,
            ):
                plan_migration(
                    [project],
                    vault,
                    "fixture",
                    None,
                    tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                )
            self.assertEqual(blocked.exception.code, "ownership-conflict")
            _routing_approval(approval, "omp-global", live, candidate)
            with mock.patch.dict(os.environ, environment):
                manifest = _plan_routing(project, vault, approval, environment)
                replacements = [
                    operation
                    for operation in manifest["payload"]["shared_operations"]
                    if operation["selector"] == "approved-routing-replacement"
                ]
                self.assertEqual(
                    [
                        (
                            operation["change"]["kind"],
                            operation["ownership"]["role"],
                            operation["target"],
                        )
                        for operation in replacements
                    ],
                    [("copy-file", "omp-global", str(live))],
                )
                self.assertFalse(
                    any(
                        operation["target"] == str(live)
                        and operation["selector"] == "pause-legacy-routing"
                        for operation in manifest["payload"]["shared_operations"]
                    )
                )
                self.assertTrue(
                    any(
                        record["kind"] == "omp-home"
                        and record["path"] == str(home / ".omp")
                        for record in manifest["payload"]["shared_roots"]
                    )
                )
                validate_legacy_inputs(manifest, _reader)
                from onboard_contracts import canonical_json_bytes
                from sbtd_migration import apply_migration

                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(manifest))
                with mock.patch(
                    "sbtd_migration.runtime_versions",
                    return_value={"onboard": "fixture", "graft": "0.18.0"},
                ):
                    response, code = apply_migration(
                        manifest_path,
                        confirmed=True,
                        routing_approvals=approval,
                    )
                self.assertEqual(code, 0, response)
                self.assertEqual(live.read_bytes(), candidate.read_bytes())

                def change_role(payload):
                    operation = next(
                        item
                        for item in payload["shared_operations"]
                        if item["selector"] == "approved-routing-replacement"
                    )
                    operation["ownership"]["role"] = "demo-project"

                tampered = _reseal(manifest, change_role)
                with self.assertRaises(ContractError) as rebound:
                    validate_legacy_inputs(
                        tampered,
                        _receipt_reader(
                            tampered, response["migration"]["apply_receipt"]
                        ),
                    )
                self.assertEqual(rebound.exception.code, "approval-conflict")
                candidate.write_bytes(pause + b"\nchanged after approval\n")
                from sbtd_migration_verify import _check_approved_routing

                with self.assertRaises(ContractError) as drifted:
                    _check_approved_routing(manifest)
                self.assertEqual(drifted.exception.code, "approved-routing-drift")

    def test_demo_project_candidate_replaces_marker_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, _home, vault, evidence, pause, environment = _routing_batch(base)
            live = project / "AGENTS.md"
            body = b"custom trellis project routing\n"
            live.write_bytes(body)
            hashes_path = project / ".trellis/.template-hashes.json"
            recorded = json.loads(hashes_path.read_text())
            recorded["hashes"]["AGENTS.md"] = hashlib.sha256(body).hexdigest()
            hashes_path.write_text(json.dumps(recorded))
            candidate = vault / "routing-candidate.md"
            candidate.write_bytes(pause + b"\napproved demo replacement\n")
            approval = vault / "routing-approvals.json"
            other = base / "other" / "AGENTS.md"
            other.parent.mkdir()
            other.write_bytes(body)
            _routing_approval(approval, "demo-project", other, candidate)
            with (
                mock.patch.dict(os.environ, environment),
                self.assertRaises(ContractError) as outside,
            ):
                plan_migration(
                    [project],
                    vault,
                    "fixture",
                    None,
                    tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                    routing_approvals=approval,
                )
            self.assertEqual(outside.exception.code, "approval-conflict")
            with (
                mock.patch.dict(os.environ, environment),
                self.assertRaises(ContractError) as blocked,
            ):
                plan_migration(
                    [project],
                    vault,
                    "fixture",
                    None,
                    tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                )
            self.assertEqual(blocked.exception.code, "ownership-conflict")
            _routing_approval(approval, "demo-project", live, candidate)
            before_live = live.read_bytes()
            with mock.patch.dict(os.environ, environment):
                manifest = _plan_routing(project, vault, approval, environment)
                private = manifest["payload"]["projects"][0]["private_operations"]
                replacements = [
                    operation
                    for operation in private
                    if operation["selector"] == "approved-routing-replacement"
                ]
                self.assertEqual(
                    [
                        (
                            operation["change"]["kind"],
                            operation["ownership"]["role"],
                            operation["target"],
                            operation["dependent_projects"],
                        )
                        for operation in replacements
                    ],
                    [("copy-file", "demo-project", str(live), [str(project)])],
                )
                self.assertFalse(
                    any(
                        operation["target"] == str(live)
                        and operation["selector"] == "trellis-block"
                        for operation in private
                    )
                )
                self.assertFalse(
                    any(
                        operation["selector"] == "approved-routing-replacement"
                        for operation in manifest["payload"]["shared_operations"]
                    )
                )
                validate_legacy_inputs(manifest, _reader)
                from onboard_contracts import canonical_json_bytes
                from sbtd_migration import apply_migration

                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(canonical_json_bytes(manifest))
                with mock.patch(
                    "sbtd_migration.runtime_versions",
                    return_value={"onboard": "fixture", "graft": "0.18.0"},
                ):
                    response, code = apply_migration(
                        manifest_path,
                        confirmed=True,
                        routing_approvals=approval,
                    )
                self.assertEqual(code, 0, response)
                self.assertEqual(live.read_bytes(), candidate.read_bytes())
                outside_candidate = base / "outside-candidate.md"
                outside_candidate.write_bytes(candidate.read_bytes())

                def point_outside(payload):
                    operation = next(
                        item
                        for item in payload["projects"][0]["private_operations"]
                        if item["selector"] == "approved-routing-replacement"
                    )
                    forged = {
                        "path": str(outside_candidate),
                        "state": snapshot(outside_candidate),
                    }
                    operation["change"]["source_ref"] = forged
                    operation["ownership"]["reference"] = forged

                tampered = _reseal(manifest, point_outside)
                with self.assertRaises(ContractError) as scope_error:
                    validate_legacy_inputs(
                        tampered,
                        _receipt_reader(
                            tampered, response["migration"]["apply_receipt"]
                        ),
                    )
                self.assertEqual(scope_error.exception.code, "private-scope")
                manifest_path.write_bytes(canonical_json_bytes(tampered))
                with (
                    mock.patch(
                        "sbtd_migration.runtime_versions",
                        return_value={"onboard": "fixture", "graft": "0.18.0"},
                    ),
                    self.assertRaises(ContractError),
                ):
                    apply_migration(manifest_path, confirmed=True)
                self.assertEqual(live.read_bytes(), candidate.read_bytes())
                self.assertNotEqual(live.read_bytes(), before_live)
                candidate.write_bytes(pause + b"\nchanged after approval\n")
                from sbtd_migration_verify import _check_approved_routing

                with self.assertRaises(ContractError) as drifted:
                    _check_approved_routing(manifest)
                self.assertEqual(drifted.exception.code, "approved-routing-drift")




    def test_dropped_or_substituted_routing_is_rejected_before_write(self):
        from onboard_contracts import canonical_json_bytes, operation_id, resource_id
        from sbtd_migration import apply_migration

        def reject(manifest, environment, evidence, live, before, name):
            with mock.patch.dict(os.environ, environment):
                with self.assertRaises(ContractError) as error:
                    validate_legacy_inputs(manifest, _reader)
                self.assertEqual(error.exception.code, "approval-conflict")
            path = evidence / f"{name}.json"
            path.write_bytes(canonical_json_bytes(manifest))
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch(
                    "sbtd_migration.runtime_versions",
                    return_value={"onboard": "fixture", "graft": "0.18.0"},
                ),
                self.assertRaises(ContractError),
            ):
                apply_migration(path, confirmed=True)
            self.assertEqual(live.read_bytes(), before)

        def drop_routing(payload):
            removed = {
                operation["operation_id"]
                for operation in payload["shared_operations"]
                if operation["selector"] == "approved-routing-replacement"
            }
            for project_record in payload["projects"]:
                removed.update(
                    operation["operation_id"]
                    for operation in project_record["private_operations"]
                    if operation["selector"] == "approved-routing-replacement"
                )
                project_record["private_operations"] = [
                    operation
                    for operation in project_record["private_operations"]
                    if operation["operation_id"] not in removed
                ]
                project_record["shared_operation_ids"] = [
                    item
                    for item in project_record["shared_operation_ids"]
                    if item not in removed
                ]
            payload["shared_operations"] = [
                operation
                for operation in payload["shared_operations"]
                if operation["operation_id"] not in removed
            ]

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, home, vault, evidence, pause, environment = _routing_batch(base)
            live = home / ".codex" / "AGENTS.md"
            live.parent.mkdir(parents=True)
            before = b"custom trellis routing\n"
            live.write_bytes(before)
            candidate = vault / "routing-candidate.md"
            candidate.write_bytes(pause + b"\napproved replacement\n")
            approval = _routing_approval(
                vault / "routing-approvals.json", "codex-global", live, candidate
            )
            manifest = _plan_routing(project, vault, approval, environment)
            self.assertEqual(
                manifest["payload"]["routing_approvals"]["path"], str(approval)
            )
            reject(
                _reseal(manifest, drop_routing),
                environment,
                evidence,
                live,
                before,
                "codex-drop",
            )

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, home, vault, evidence, pause, environment = _routing_batch(base)
            live = home / ".omp" / "agent" / "AGENTS.md"
            live.parent.mkdir(parents=True)
            before = b"custom trellis omp routing\n"
            live.write_bytes(before)
            candidate = vault / "routing-candidate.md"
            candidate.write_bytes(pause + b"\napproved omp replacement\n")
            approval = _routing_approval(
                vault / "routing-approvals.json", "omp-global", live, candidate
            )
            manifest = _plan_routing(project, vault, approval, environment)
            reject(
                _reseal(manifest, drop_routing),
                environment,
                evidence,
                live,
                before,
                "omp-drop",
            )

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, home, vault, evidence, pause, environment = _routing_batch(base)
            live = project / "AGENTS.md"
            before = (
                b"keep-me\n<!-- TRELLIS:START -->\nmanaged\n<!-- TRELLIS:END -->\n"
                b"keep-tail\n"
            )
            live.write_bytes(before)
            hashes_path = project / ".trellis/.template-hashes.json"
            recorded = json.loads(hashes_path.read_text())
            recorded["hashes"]["AGENTS.md"] = hashlib.sha256(before).hexdigest()
            hashes_path.write_text(json.dumps(recorded))
            candidate = vault / "routing-candidate.md"
            candidate.write_bytes(pause + b"\napproved demo replacement\n")
            approval = _routing_approval(
                vault / "routing-approvals.json", "demo-project", live, candidate
            )
            manifest = _plan_routing(project, vault, approval, environment)

            def swap_for_marker_delete(payload):
                operations = payload["projects"][0]["private_operations"]
                replacement = next(
                    operation
                    for operation in operations
                    if operation["selector"] == "approved-routing-replacement"
                )
                operations.remove(replacement)
                resource = resource_id("markdown", str(live))
                operations.append(
                    {
                        "operation_id": operation_id(
                            "apply", resource, "trellis-block"
                        ),
                        "phase": "apply",
                        "resource_id": resource,
                        "owner_kind": "markdown",
                        "target": str(live),
                        "selector": "trellis-block",
                        "change": {"kind": "remove"},
                        "ownership": {
                            "kind": "managed-marker",
                            "reference": {"path": str(live), "state": snapshot(live)},
                            "marker": "TRELLIS",
                        },
                        "before_requirement": {
                            "kind": "state",
                            "state": snapshot(live),
                        },
                        "dependent_projects": [str(project)],
                    }
                )

            reject(
                _reseal(manifest, swap_for_marker_delete),
                environment,
                evidence,
                live,
                before,
                "demo-swap",
            )



    def test_approval_inside_evidence_apply_root_is_rejected_before_write(self):
        from onboard_contracts import canonical_json_bytes
        from sbtd_migration import apply_migration

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, home, vault, evidence, pause, environment = _routing_batch(base)
            live = project / "AGENTS.md"
            before = (
                b"keep-me\n<!-- TRELLIS:START -->\nmanaged\n"
                b"<!-- TRELLIS:END -->\nkeep-tail\n"
            )
            live.write_bytes(before)
            hashes_path = project / ".trellis/.template-hashes.json"
            recorded = json.loads(hashes_path.read_text())
            recorded["hashes"]["AGENTS.md"] = hashlib.sha256(before).hexdigest()
            hashes_path.write_text(json.dumps(recorded))
            candidate = vault / "routing-candidate.md"
            candidate.write_bytes(pause + b"\napproved demo replacement\n")
            approval = _routing_approval(
                vault / "routing-approvals.json", "demo-project", live, candidate
            )
            manifest = _plan_routing(project, vault, approval, environment)
            attacker = base / "attacker-vault"
            attacker.mkdir(mode=0o700)
            forged_candidate = attacker / "forged.md"
            forged_candidate.write_bytes(pause + b"\nattacker replacement\n")
            forged_approval = attacker / "routing-approvals.json"
            forged_approval.write_bytes(
                json.dumps(
                    {
                        "schema_version": 1,
                        "items": [
                            {
                                "role": "demo-project",
                                "target_path": str(live),
                                "before": snapshot(live),
                                "candidate_ref": {
                                    "path": str(forged_candidate),
                                    "state": snapshot(forged_candidate),
                                },
                                "basis": "forged",
                            }
                        ],
                    }
                ).encode()
            )
            nested = attacker / "evidence"
            nested.mkdir(mode=0o700)

            def retarget(payload):
                payload["backup_root"] = str(attacker)
                payload["routing_approvals"] = {
                    "path": str(forged_approval),
                    "state": snapshot(forged_approval),
                }
                for project_record in payload["projects"]:
                    for operation in project_record["private_operations"]:
                        if operation["selector"] != "approved-routing-replacement":
                            continue
                        forged = {
                            "path": str(forged_candidate),
                            "state": snapshot(forged_candidate),
                        }
                        operation["change"]["source_ref"] = forged
                        operation["ownership"]["reference"] = forged
                        operation["ownership"]["approval_ref"] = payload[
                            "routing_approvals"
                        ]

            tampered = _reseal(manifest, retarget)
            path = nested / "manifest.json"
            path.write_bytes(canonical_json_bytes(tampered))
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch(
                    "sbtd_migration.runtime_versions",
                    return_value={"onboard": "fixture", "graft": "0.18.0"},
                ),
                self.assertRaises(ContractError) as error,
            ):
                apply_migration(path, confirmed=True)
            self.assertEqual(error.exception.code, "private-scope")
            self.assertEqual(live.read_bytes(), before)

            honest = evidence / "manifest.json"
            honest.write_bytes(canonical_json_bytes(manifest))
            approval.write_bytes(approval.read_bytes() + b"\n")
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch(
                    "sbtd_migration.runtime_versions",
                    return_value={"onboard": "fixture", "graft": "0.18.0"},
                ),
                self.assertRaises(ContractError) as drifted,
            ):
                apply_migration(honest, confirmed=True)
            self.assertEqual(drifted.exception.code, "state-conflict")
            self.assertEqual(live.read_bytes(), before)

    def test_caller_anchor_rejects_retargeted_vault_before_render(self):
        from onboard_contracts import canonical_json_bytes
        from sbtd_migration import apply_migration

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, home, vault, evidence, pause, environment = _routing_batch(base)
            live = project / "AGENTS.md"
            before = (
                b"keep-me\n<!-- TRELLIS:START -->\nmanaged\n"
                b"<!-- TRELLIS:END -->\nkeep-tail\n"
            )
            live.write_bytes(before)
            hashes_path = project / ".trellis/.template-hashes.json"
            recorded = json.loads(hashes_path.read_text())
            recorded["hashes"]["AGENTS.md"] = hashlib.sha256(before).hexdigest()
            hashes_path.write_text(json.dumps(recorded))
            candidate = vault / "routing-candidate.md"
            candidate.write_bytes(pause + b"\napproved demo replacement\n")
            approval = _routing_approval(
                vault / "routing-approvals.json", "demo-project", live, candidate
            )
            manifest = _plan_routing(project, vault, approval, environment)
            attacker = base / "attacker-vault"
            attacker.mkdir(mode=0o700)
            forged_candidate = attacker / "forged.md"
            forged_candidate.write_bytes(pause + b"\nattacker replacement\n")
            forged_approval = attacker / "routing-approvals.json"
            forged_approval.write_bytes(
                json.dumps(
                    {
                        "schema_version": 1,
                        "items": [
                            {
                                "role": "demo-project",
                                "target_path": str(live),
                                "before": snapshot(live),
                                "candidate_ref": {
                                    "path": str(forged_candidate),
                                    "state": snapshot(forged_candidate),
                                },
                                "basis": "forged",
                            }
                        ],
                    }
                ).encode()
            )

            def retarget(payload):
                payload["backup_root"] = str(attacker)
                payload["routing_approvals"] = {
                    "path": str(forged_approval),
                    "state": snapshot(forged_approval),
                }
                for project_record in payload["projects"]:
                    for operation in project_record["private_operations"]:
                        if operation["selector"] != "approved-routing-replacement":
                            continue
                        forged = {
                            "path": str(forged_candidate),
                            "state": snapshot(forged_candidate),
                        }
                        operation["change"]["source_ref"] = forged
                        operation["ownership"]["reference"] = forged
                        operation["ownership"]["approval_ref"] = payload[
                            "routing_approvals"
                        ]

            tampered = _reseal(manifest, retarget)
            path = evidence / "retarget.json"
            path.write_bytes(canonical_json_bytes(tampered))
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch(
                    "sbtd_migration.runtime_versions",
                    return_value={"onboard": "fixture", "graft": "0.18.0"},
                ),
                mock.patch(
                    "sbtd_migration._render_resource",
                    side_effect=AssertionError("render"),
                ),
                self.assertRaises(ContractError) as error,
            ):
                apply_migration(
                    path, confirmed=True, routing_approvals=approval
                )
            self.assertEqual(error.exception.code, "invalid-config")
            self.assertEqual(live.read_bytes(), before)

    def test_null_approval_marker_delete_is_rejected_before_render(self):
        from onboard_contracts import canonical_json_bytes, operation_id, resource_id
        from sbtd_migration import apply_migration

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, home, vault, evidence, pause, environment = _routing_batch(base)
            live = project / "AGENTS.md"
            before = (
                b"keep-me\n<!-- TRELLIS:START -->\nmanaged\n"
                b"<!-- TRELLIS:END -->\nkeep-tail\n"
            )
            live.write_bytes(before)
            hashes_path = project / ".trellis/.template-hashes.json"
            recorded = json.loads(hashes_path.read_text())
            recorded["hashes"]["AGENTS.md"] = hashlib.sha256(before).hexdigest()
            hashes_path.write_text(json.dumps(recorded))
            candidate = vault / "routing-candidate.md"
            candidate.write_bytes(pause + b"\napproved demo replacement\n")
            approval = _routing_approval(
                vault / "routing-approvals.json", "demo-project", live, candidate
            )
            manifest = _plan_routing(project, vault, approval, environment)

            def null_and_delete(payload):
                payload["routing_approvals"] = None
                operations = payload["projects"][0]["private_operations"]
                replacement = next(
                    operation
                    for operation in operations
                    if operation["selector"] == "approved-routing-replacement"
                )
                operations.remove(replacement)
                resource = resource_id("markdown", str(live))
                operations.append(
                    {
                        "operation_id": operation_id(
                            "apply", resource, "trellis-block"
                        ),
                        "phase": "apply",
                        "resource_id": resource,
                        "owner_kind": "markdown",
                        "target": str(live),
                        "selector": "trellis-block",
                        "change": {"kind": "remove"},
                        "ownership": {
                            "kind": "managed-marker",
                            "reference": {"path": str(live), "state": snapshot(live)},
                            "marker": "TRELLIS",
                        },
                        "before_requirement": {
                            "kind": "state",
                            "state": snapshot(live),
                        },
                        "dependent_projects": [str(project)],
                    }
                )

            tampered = _reseal(manifest, null_and_delete)
            path = evidence / "null-delete.json"
            path.write_bytes(canonical_json_bytes(tampered))
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch(
                    "sbtd_migration.runtime_versions",
                    return_value={"onboard": "fixture", "graft": "0.18.0"},
                ),
                mock.patch(
                    "sbtd_migration._render_resource",
                    side_effect=AssertionError("render"),
                ),
                self.assertRaises(ContractError) as error,
            ):
                apply_migration(path, confirmed=True, no_routing_approvals=True)
            self.assertEqual(error.exception.code, "approval-conflict")
            self.assertEqual(live.read_bytes(), before)

    def test_caller_attacker_file_is_rejected_before_render(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )
        from onboard_contracts import canonical_json_bytes
        from sbtd_migration import apply_migration

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, home, vault, evidence, pause, environment = _routing_batch(base)
            live = project / "AGENTS.md"
            before = (
                b"keep-me\n<!-- TRELLIS:START -->\nmanaged\n"
                b"<!-- TRELLIS:END -->\nkeep-tail\n"
            )
            live.write_bytes(before)
            hashes_path = project / ".trellis/.template-hashes.json"
            recorded = json.loads(hashes_path.read_text())
            recorded["hashes"]["AGENTS.md"] = hashlib.sha256(before).hexdigest()
            hashes_path.write_text(json.dumps(recorded))
            candidate = vault / "routing-candidate.md"
            candidate.write_bytes(pause + b"\napproved demo replacement\n")
            approval = _routing_approval(
                vault / "routing-approvals.json", "demo-project", live, candidate
            )
            manifest = _plan_routing(project, vault, approval, environment)
            attacker = base / "attacker-vault"
            attacker.mkdir(mode=0o700)
            forged_candidate = attacker / "forged.md"
            forged_candidate.write_bytes(pause + b"\nattacker replacement\n")
            forged_approval = attacker / "routing-approvals.json"
            forged_approval.write_bytes(
                json.dumps(
                    {
                        "schema_version": 1,
                        "items": [
                            {
                                "role": "demo-project",
                                "target_path": str(live),
                                "before": snapshot(live),
                                "candidate_ref": {
                                    "path": str(forged_candidate),
                                    "state": snapshot(forged_candidate),
                                },
                                "basis": "forged",
                            }
                        ],
                    }
                ).encode()
            )
            _sign_existing_approval(forged_approval, Ed25519PrivateKey.generate())

            def retarget(payload):
                payload["backup_root"] = str(attacker)
                payload["routing_approvals"] = {
                    "path": str(forged_approval),
                    "state": snapshot(forged_approval),
                }
                for project_record in payload["projects"]:
                    for operation in project_record["private_operations"]:
                        if operation["selector"] != "approved-routing-replacement":
                            continue
                        forged = {
                            "path": str(forged_candidate),
                            "state": snapshot(forged_candidate),
                        }
                        operation["change"]["source_ref"] = forged
                        operation["ownership"]["reference"] = forged
                        operation["ownership"]["approval_ref"] = payload[
                            "routing_approvals"
                        ]

            tampered = _reseal(manifest, retarget)
            path = evidence / "attacker-file.json"
            path.write_bytes(canonical_json_bytes(tampered))
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch(
                    "sbtd_migration.runtime_versions",
                    return_value={"onboard": "fixture", "graft": "0.18.0"},
                ),
                mock.patch(
                    "sbtd_migration._render_resource",
                    side_effect=AssertionError("render"),
                ),
                self.assertRaises(ContractError) as error,
            ):
                apply_migration(
                    path, confirmed=True, routing_approvals=forged_approval
                )
            self.assertEqual(error.exception.code, "approval-conflict")
            self.assertEqual(live.read_bytes(), before)

    def test_plan_signs_only_the_approval_file_with_the_installed_key(self):
        from cryptography.hazmat.primitives import serialization

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, home, vault, evidence, pause, environment = _routing_batch(base)
            live = home / ".codex" / "AGENTS.md"
            live.parent.mkdir(parents=True)
            live.write_bytes(b"custom trellis routing\n")
            candidate = vault / "routing-candidate.md"
            candidate.write_bytes(pause + b"\napproved replacement\n")
            approval = vault / "routing-approvals.json"
            approval.write_bytes(
                json.dumps(
                    {
                        "schema_version": 1,
                        "items": [
                            {
                                "role": "codex-global",
                                "target_path": str(live),
                                "before": snapshot(live),
                                "candidate_ref": {
                                    "path": str(candidate),
                                    "state": snapshot(candidate),
                                },
                                "basis": "fixture custodian approval",
                            }
                        ],
                    }
                ).encode("utf-8")
            )
            before = approval.read_bytes()
            key_path = base / "operator.key"
            key_path.write_bytes(
                _TEST_APPROVAL_KEY.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                )
            )
            with mock.patch.dict(os.environ, environment):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture",
                    None,
                    tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                    routing_approvals=approval,
                    routing_approval_key=key_path,
                )
            self.assertNotEqual(approval.read_bytes(), before)
            self.assertIn(b"signature", approval.read_bytes())
            self.assertEqual(
                manifest["payload"]["routing_approvals"]["path"], str(approval)
            )
            self.assertNotIn("operator.key", json.dumps(manifest))


class IgnoredLegacyNoiseTests(unittest.TestCase):
    def test_gitignore_hides_incidental_files_but_not_task_json(self):
        from sbtd_migration_files import directory_snapshot

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            (root / ".gitignore").write_text(
                ".DS_Store\n*.pyc\n__pycache__/\n.trellis/.backup-*\n"
                ".trellis/tasks/*/task.json\n"
            )
            trellis = root / ".trellis"
            task = trellis / "tasks" / "00-bootstrap"
            task.mkdir(parents=True)
            (task / "task.json").write_text("{}\n")
            backup = trellis / ".backup-local"
            backup.mkdir()
            (backup / "old.txt").write_text("old\n")
            (trellis / ".DS_Store").write_bytes(b"\x00store")
            cache = trellis / "scripts" / "common" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "io.cpython-313.pyc").write_bytes(b"\x00pyc")
            (trellis / "notes.txt").write_text("tracked unknown\n")
            subprocess.run(
                ["git", "add", "--", ".gitignore", ".trellis/notes.txt"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            _state, entries = directory_snapshot(trellis)
            present = {entry["path"] for entry in entries}
            self.assertIn(".backup-local/old.txt", present)
            self.assertIn(".DS_Store", present)
            self.assertIn("scripts/common/__pycache__/io.cpython-313.pyc", present)
            classified, unknown = sbtd_migration_plan._partition_legacy_entries(
                root, entries
            )
            kept = {entry["path"] for entry in classified}
            self.assertIn("tasks/00-bootstrap/task.json", kept)
            self.assertNotIn(".backup-local/old.txt", kept)
            self.assertNotIn(".DS_Store", kept)
            self.assertIn("scripts/common/__pycache__/io.cpython-313.pyc", kept)
            self.assertEqual(unknown, ["notes.txt"])
            with self.assertRaises(ContractError) as caught:
                sbtd_migration_plan._fail_unknown(root, unknown)
            self.assertEqual(caught.exception.details["tracked"], ["notes.txt"])
            self.assertIn("Do not delete a tracked file", caught.exception.details["recommendation"])



def _add_history_document(
    project,
    vault,
    items,
    *,
    folder="archive/2026-09/09-02-legacy-notes",
    name="prd.md",
    body=b"# legacy prd\n",
    decision="share",
    candidate_body=None,
    target=None,
    item_id=None,
):
    """Approve one orphan legacy tasks file as a historical document."""
    source = project / ".trellis/tasks" / folder / name
    _write(source, body)
    candidate = vault / ("cand-history-" + folder.replace("/", "-") + "-" + name)
    _write(candidate, body if candidate_body is None else candidate_body)
    if target is None:
        target = project / "docs/legacy-archive/tasks" / folder / name
    items.append(
        _item(
            item_id or ("history-" + folder.replace("/", "-") + "-" + name),
            [_ref(source)],
            target,
            decision,
            candidate,
        )
    )
    return source, candidate, target


def _no_touch_tree(base, *, version=b"0.6.17\n", template=None):
    """Legacy project whose root AGENTS.md already equals the bundled template."""
    project = base / "project"
    if template is None:
        template = (
            SCRIPTS.parents[0] / "templates" / "agents" / "AGENTS.project.md"
        ).read_bytes()
    _write(project / "AGENTS.md", template)
    _write(project / PLATFORM_REL, PLATFORM_TOML)
    _write(
        project / ".trellis/.template-hashes.json",
        _json_bytes(
            {
                "__version": 2,
                "hashes": {
                    PLATFORM_REL: hashlib.sha256(PLATFORM_TOML).hexdigest(),
                    "AGENTS.md": hashlib.sha256(
                        b"legacy trellis routing marker\n"
                    ).hexdigest(),
                },
            }
        ),
    )
    _write(project / ".trellis/.version", version)
    _write(project / ".trellis/.developer", LEGACY_IDENTITY)
    return project


class MigrationHistoryDocumentTests(unittest.TestCase):
    """Legacy tasks files without any ancestor task.json archive as documents."""

    def fixture(self, base):
        project = _base_tree(base)
        vault = base / "vault"
        vault.mkdir(mode=0o700)
        home = base / "home"
        home.mkdir(mode=0o700)
        return project, vault, home, []

    def test_orphan_task_history_plans_to_canonical_legacy_archive_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items = self.fixture(base)
            expected = []
            for folder, name in (
                ("archive/2026-09/09-02-legacy-notes", "prd.md"),
                ("archive/2026-09/09-02-legacy-notes", "design.md"),
                ("archive/2026-09/09-03-review-notes", "FOLLOWUPS.md"),
            ):
                _source, _candidate, target = _add_history_document(
                    project, vault, items, folder=folder, name=name
                )
                expected.append(str(target))
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            manifest = _plan(project, vault, decisions, home)
            self.assertEqual(_tree_bytes(base), before)
            operations = manifest["payload"]["projects"][0]["private_operations"]
            publications = {
                operation["target"]
                for operation in operations
                if operation["change"]["kind"] == "copy-file"
            }
            self.assertEqual(publications, set(expected))
            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, _reader))
            self.assertEqual(_tree_bytes(base), before)

    def test_history_documents_apply_retry_and_retained_original_replay(self):
        from sbtd_migration import (
            _backup_sources,
            _source_backup_paths,
            apply_migration,
            runtime_versions,
        )

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items = self.fixture(base)
            bodies = {}
            for name, body in (
                ("prd.md", b"# legacy prd\n"),
                ("design.md", b"# legacy design\n"),
            ):
                _source, _candidate, target = _add_history_document(
                    project, vault, items, name=name, body=body
                )
                bodies[target] = body
            with _home_env(home):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    _decisions(vault, items),
                    tool_versions=runtime_versions(),
                )
                manifest_path = vault / "manifest.json"
                manifest_path.write_bytes(contracts.canonical_json_bytes(manifest))
                receipt, code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
                self.assertEqual(code, 0, receipt)
                receipt_path = vault / "apply.json"
                receipt_path.write_bytes(
                    contracts.canonical_json_bytes(
                        receipt["migration"]["apply_receipt"]
                    )
                )
                repeated, code = apply_migration(
                    manifest_path,
                    previous_receipt_path=receipt_path,
                    confirmed=True,
                    no_routing_approvals=True,
                )
                self.assertEqual(code, 0, repeated)
            for target, body in bodies.items():
                self.assertEqual(target.read_bytes(), body)
            source_root = project / ".trellis"
            originals = {
                path.relative_to(source_root): path.read_bytes()
                for path in source_root.rglob("*")
                if path.is_file()
            }
            backup = _source_backup_paths(manifest)[str(source_root)]
            _backup_sources(manifest)
            source_root.rename(base / "retired-source")
            resolve_receipt = _receipt_reader(
                manifest, receipt["migration"]["apply_receipt"]
            )

            def original(reference):
                path = Path(reference["path"])
                if path.is_relative_to(source_root):
                    return read_file(
                        backup / path.relative_to(source_root), reference["state"]
                    )
                # Retired platform files resolve through the receipt's retained
                # backups, exactly as apply-time revalidation resolves them.
                return resolve_receipt(reference)

            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, original))
            for relative, raw in originals.items():
                self.assertEqual((backup / relative).read_bytes(), raw)

    def test_recovery_plan_revalidates_history_document_closure(self):
        from sbtd_migration import apply_migration, runtime_versions
        from sbtd_recovery import plan_recovery

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items = self.fixture(base)
            _add_history_document(project, vault, items)
            with _home_env(home):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    _decisions(vault, items),
                    tool_versions=runtime_versions(),
                )
                manifest_path = vault / "manifest.json"
                manifest_path.write_bytes(contracts.canonical_json_bytes(manifest))
                receipt, code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
                self.assertEqual(code, 0, receipt)
                receipt_path = vault / "apply.json"
                receipt_path.write_bytes(
                    contracts.canonical_json_bytes(
                        receipt["migration"]["apply_receipt"]
                    )
                )
                envelope, code = plan_recovery(
                    manifest_path, apply_receipt_path=receipt_path
                )
            self.assertIn(code, (0, 2), envelope)
            self.assertEqual(
                envelope["recovery"]["plan"]["payload"]["manifest_id"],
                manifest["manifest_id"],
            )

    def test_unapproved_orphan_task_files_require_history_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items = self.fixture(base)
            _write(
                project / ".trellis/tasks/archive/2026-09/09-02-legacy-notes/prd.md",
                b"# legacy prd\n",
            )
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            with self.assertRaises(ContractError) as error:
                _plan(project, vault, decisions, home)
            self.assertEqual(error.exception.code, "approval-required")
            self.assertEqual(_tree_bytes(base), before)

    def test_history_document_target_must_keep_exact_legacy_relative_path(self):
        for wrong in (
            lambda project: project
            / "docs/legacy-archive/tasks/archive/2026-09/09-02-legacy-notes/renamed.md",
            lambda project: project / "docs/legacy-archive/tasks/archive/2026-09/prd.md",
            lambda project: project / "docs/legacy-archive/prd.md",
            lambda project: project / "ai/tasks/legacy-notes/prd.md",
            lambda project: project / "docs/spec/prd.md",
        ):
            with self.subTest(target=wrong), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                project, vault, home, items = self.fixture(base)
                _add_history_document(
                    project, vault, items, target=wrong(project)
                )
                decisions = _decisions(vault, items)
                before = _tree_bytes(base)
                with self.assertRaises(ContractError) as error:
                    _plan(project, vault, decisions, home)
                self.assertEqual(error.exception.code, "target-conflict")
                self.assertEqual(_tree_bytes(base), before)

    def test_history_document_cannot_shadow_an_unapproved_real_task(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items = self.fixture(base)
            folder_path = project / ".trellis/tasks/09-01-alpha"
            _write(folder_path / "task.json", _json_bytes(_legacy_source()))
            _write(folder_path / "prd.md", b"# legacy prd\n")
            candidate = vault / "cand-shadow"
            _write(candidate, b"# legacy prd\n")
            items.append(
                _item(
                    "shadow-prd",
                    [_ref(folder_path / "prd.md")],
                    project / "docs/legacy-archive/tasks/09-01-alpha/prd.md",
                    "share",
                    candidate,
                )
            )
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            with self.assertRaises(ContractError) as error:
                _plan(project, vault, decisions, home)
            self.assertEqual(error.exception.code, "approval-required")
            self.assertEqual(_tree_bytes(base), before)

    def test_history_document_cannot_double_bind_an_approved_task_file(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items = self.fixture(base)
            _add_task(project, vault, items, with_attachment=True)
            candidate = vault / "cand-double"
            _write(candidate, b"# legacy prd\n")
            items.append(
                _item(
                    "double-prd",
                    [_ref(project / ".trellis/tasks/09-01-alpha/prd.md")],
                    project / "docs/legacy-archive/tasks/09-01-alpha/prd.md",
                    "share",
                    candidate,
                )
            )
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            with self.assertRaises(ContractError) as error:
                _plan(project, vault, decisions, home)
            self.assertEqual(error.exception.code, "target-conflict")
            self.assertEqual(_tree_bytes(base), before)

    def test_history_document_binds_one_source_file_with_a_file_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items = self.fixture(base)
            first = project / ".trellis/tasks/archive/2026-09/09-02-legacy-notes/prd.md"
            second = (
                project / ".trellis/tasks/archive/2026-09/09-02-legacy-notes/design.md"
            )
            _write(first, b"# legacy prd\n")
            _write(second, b"# legacy design\n")
            candidate = vault / "cand-history-multi"
            _write(candidate, b"# combined\n")
            items.append(
                _item(
                    "history-multi",
                    [_ref(first), _ref(second)],
                    project / "docs/legacy-archive/tasks/archive/2026-09/09-02-legacy-notes",
                    "share",
                    candidate,
                )
            )
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            with self.assertRaises(ContractError) as error:
                _plan(project, vault, decisions, home)
            self.assertEqual(error.exception.code, "approval-conflict")
            self.assertEqual(_tree_bytes(base), before)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items = self.fixture(base)
            source = (
                project / ".trellis/tasks/archive/2026-09/09-02-legacy-notes/prd.md"
            )
            _write(source, b"# legacy prd\n")
            tree = vault / "cand-history-tree"
            _write(tree / "prd.md", b"# legacy prd\n")
            items.append(
                _item(
                    "history-tree",
                    [_ref(source)],
                    project
                    / "docs/legacy-archive/tasks/archive/2026-09/09-02-legacy-notes",
                    "share",
                    tree,
                )
            )
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            with self.assertRaises(ContractError) as error:
                _plan(project, vault, decisions, home)
            self.assertEqual(error.exception.code, "approval-conflict")
            self.assertEqual(_tree_bytes(base), before)

    def test_history_document_private_only_blanket_skip_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items = self.fixture(base)
            source = (
                project / ".trellis/tasks/archive/2026-09/09-02-legacy-notes/prd.md"
            )
            _write(source, b"# legacy prd\n")
            items.append(
                _item("history-skip", [_ref(source)], None, "private-only", None, required=False)
            )
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            with self.assertRaises(ContractError) as error:
                _plan(project, vault, decisions, home)
            self.assertEqual(error.exception.code, "approval-conflict")
            self.assertEqual(_tree_bytes(base), before)

    def test_history_document_share_drift_secret_leak_and_bad_link_still_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items = self.fixture(base)
            _add_history_document(
                project, vault, items, candidate_body=b"# altered prd\n"
            )
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            with self.assertRaises(ContractError) as error:
                _plan(project, vault, decisions, home)
            self.assertEqual(error.exception.code, "candidate-conflict")
            self.assertEqual(_tree_bytes(base), before)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items = self.fixture(base)
            _add_history_document(
                project,
                vault,
                items,
                body=b"# prd\nvault: " + str(vault).encode("utf-8") + b"\n",
            )
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            with self.assertRaises(ContractError) as error:
                _plan(project, vault, decisions, home)
            self.assertEqual(error.exception.code, "privacy-violation")
            self.assertEqual(_tree_bytes(base), before)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items = self.fixture(base)
            _add_history_document(
                project,
                vault,
                items,
                body=b"# prd\n\nSee [notes](../secret.md) for context.\n",
            )
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            with self.assertRaises(ContractError) as error:
                _plan(project, vault, decisions, home)
            self.assertEqual(error.exception.code, "target-conflict")
            self.assertEqual(_tree_bytes(base), before)

    def test_history_document_duplicate_approval_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items = self.fixture(base)
            source, _candidate, target = _add_history_document(project, vault, items)
            duplicate = vault / "cand-history-duplicate"
            _write(duplicate, b"# legacy prd\n")
            items.append(
                _item("history-duplicate", [_ref(source)], target, "share", duplicate)
            )
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            # The duplicate binding is refused as invalid input; which
            # coherence layer fires first (decisions binding, publication
            # link, approved-target or coverage) is an internal detail.
            with self.assertRaises(ContractError):
                _plan(project, vault, decisions, home)
            self.assertEqual(_tree_bytes(base), before)

    def test_resealed_manifest_with_altered_history_closure_is_rejected(self):
        import copy

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items = self.fixture(base)
            _add_history_document(project, vault, items)
            decisions = _decisions(vault, items)
            manifest = _plan(project, vault, decisions, home)
            payload = copy.deepcopy(manifest["payload"])
            operations = payload["projects"][0]["private_operations"]
            payload["projects"][0]["private_operations"] = [
                operation
                for operation in operations
                if "/docs/legacy-archive/" not in operation["target"]
            ]
            before = _tree_bytes(base)
            # Dropping the publication operation while its approved item
            # remains is incoherent: the manifest binding layer itself
            # refuses to seal the altered shape.
            with self.assertRaises(ContractError):
                contracts.seal_document("manifest", payload)
            self.assertEqual(_tree_bytes(base), before)


class MigrationAgentsNoTouchTests(unittest.TestCase):
    """A project AGENTS.md already equal to the bundled template is untouched."""

    def fixture(self, base, **kwargs):
        project = _no_touch_tree(base, **kwargs)
        vault = base / "vault"
        vault.mkdir(mode=0o700)
        home = base / "home"
        home.mkdir(mode=0o700)
        return project, vault, home

    def test_template_aligned_agents_plans_zero_operations_with_sealed_proof(self):
        for version in (b"0.6.15\n", b"0.6.17\n"):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                project, vault, home = self.fixture(base, version=version)
                aligned = (project / "AGENTS.md").read_bytes()
                before = _tree_bytes(base)
                manifest = _plan(project, vault, None, home)
                self.assertEqual(_tree_bytes(base), before)
                payload_project = manifest["payload"]["projects"][0]
                agents_ops = [
                    operation
                    for operation in payload_project["private_operations"]
                    if operation["target"] == str(project / "AGENTS.md")
                ]
                self.assertEqual(agents_ops, [])
                proof = payload_project.get("agents_no_touch")
                self.assertIsNotNone(proof)
                self.assertEqual(proof["target"]["path"], str(project / "AGENTS.md"))
                self.assertEqual(
                    proof["target"]["state"], snapshot(project / "AGENTS.md")
                )
                self.assertEqual(
                    proof["template"]["path"],
                    str(
                        SCRIPTS.parents[0]
                        / "templates"
                        / "agents"
                        / "AGENTS.project.md"
                    ),
                )
                self.assertEqual(proof["template"]["state"]["type"], "file")
                with _home_env(home):
                    self.assertIsNone(validate_legacy_inputs(manifest, _reader))
                self.assertEqual((project / "AGENTS.md").read_bytes(), aligned)
                self.assertEqual(_tree_bytes(base), before)

    def test_no_touch_agents_apply_retry_and_retained_replay_keep_bytes(self):
        from sbtd_migration import (
            _backup_sources,
            _source_backup_paths,
            apply_migration,
            runtime_versions,
        )

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home = self.fixture(base)
            aligned = (project / "AGENTS.md").read_bytes()
            with _home_env(home):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    None,
                    tool_versions=runtime_versions(),
                )
                manifest_path = vault / "manifest.json"
                manifest_path.write_bytes(contracts.canonical_json_bytes(manifest))
                receipt, code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
                self.assertEqual(code, 0, receipt)
                receipt_path = vault / "apply.json"
                receipt_path.write_bytes(
                    contracts.canonical_json_bytes(
                        receipt["migration"]["apply_receipt"]
                    )
                )
                repeated, code = apply_migration(
                    manifest_path,
                    previous_receipt_path=receipt_path,
                    confirmed=True,
                    no_routing_approvals=True,
                )
                self.assertEqual(code, 0, repeated)
            self.assertEqual((project / "AGENTS.md").read_bytes(), aligned)
            source_root = project / ".trellis"
            backup = _source_backup_paths(manifest)[str(source_root)]
            _backup_sources(manifest)
            source_root.rename(base / "retired-source")
            resolve_receipt = _receipt_reader(
                manifest, receipt["migration"]["apply_receipt"]
            )

            def original(reference):
                path = Path(reference["path"])
                if path.is_relative_to(source_root):
                    return read_file(
                        backup / path.relative_to(source_root), reference["state"]
                    )
                # Retired platform files resolve through the receipt's retained
                # backups, exactly as apply-time revalidation resolves them.
                return resolve_receipt(reference)

            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, original))
            self.assertEqual((project / "AGENTS.md").read_bytes(), aligned)

    def test_recovery_plan_revalidates_no_touch_agents_proof(self):
        from sbtd_migration import apply_migration, runtime_versions
        from sbtd_recovery import plan_recovery

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home = self.fixture(base)
            with _home_env(home):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    None,
                    tool_versions=runtime_versions(),
                )
                manifest_path = vault / "manifest.json"
                manifest_path.write_bytes(contracts.canonical_json_bytes(manifest))
                receipt, code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
                self.assertEqual(code, 0, receipt)
                receipt_path = vault / "apply.json"
                receipt_path.write_bytes(
                    contracts.canonical_json_bytes(
                        receipt["migration"]["apply_receipt"]
                    )
                )
                envelope, code = plan_recovery(
                    manifest_path, apply_receipt_path=receipt_path
                )
            self.assertIn(code, (0, 2), envelope)
            self.assertEqual(
                envelope["recovery"]["plan"]["payload"]["manifest_id"],
                manifest["manifest_id"],
            )
            self.assertEqual(
                (project / "AGENTS.md").read_bytes(),
                (
                    SCRIPTS.parents[0] / "templates" / "agents" / "AGENTS.project.md"
                ).read_bytes(),
            )

    def test_drifted_or_custom_agents_still_refused_without_signed_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home = self.fixture(
                base, template=b"Custom project rules.\n"
            )
            before = _tree_bytes(base)
            with self.assertRaises(ContractError) as error:
                _plan(project, vault, None, home)
            self.assertEqual(error.exception.code, "ownership-conflict")
            self.assertEqual(_tree_bytes(base), before)

    def test_marker_bearing_agents_keeps_marker_removal_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _no_host_tree(base)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            home = base / "home"
            home.mkdir(mode=0o700)
            before = _tree_bytes(base)
            manifest = _plan(project, vault, None, home)
            payload_project = manifest["payload"]["projects"][0]
            markers = [
                operation
                for operation in payload_project["private_operations"]
                if operation["selector"] == "trellis-block"
            ]
            self.assertEqual(
                [operation["target"] for operation in markers],
                [str(project / "AGENTS.md")],
            )
            self.assertIsNone(payload_project.get("agents_no_touch"))
            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, _reader))
            self.assertEqual(_tree_bytes(base), before)

    def test_resealed_or_tampered_no_touch_proof_is_rejected(self):
        import copy

        template_path = (
            SCRIPTS.parents[0] / "templates" / "agents" / "AGENTS.project.md"
        )
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home = self.fixture(base)
            manifest = _plan(project, vault, None, home)
            payload = copy.deepcopy(manifest["payload"])
            payload["projects"][0]["agents_no_touch"]["target"]["state"] = {
                "type": "file",
                "checksum": hashlib.sha256(b"forged\n").hexdigest(),
            }
            tampered = contracts.seal_document("manifest", payload)
            before = _tree_bytes(base)
            with _home_env(home), self.assertRaises(ContractError) as error:
                validate_legacy_inputs(tampered, _reader)
            self.assertEqual(error.exception.code, "semantic-violation")
            self.assertEqual(_tree_bytes(base), before)
            dropped = copy.deepcopy(manifest["payload"])
            del dropped["projects"][0]["agents_no_touch"]
            resealed = contracts.seal_document("manifest", dropped)
            with _home_env(home), self.assertRaises(ContractError) as error:
                validate_legacy_inputs(resealed, _reader)
            self.assertEqual(error.exception.code, "semantic-violation")
            self.assertEqual(_tree_bytes(base), before)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _no_host_tree(base)
            vault = base / "vault"
            vault.mkdir(mode=0o700)
            home = base / "home"
            home.mkdir(mode=0o700)
            manifest = _plan(project, vault, None, home)
            payload = copy.deepcopy(manifest["payload"])
            payload["projects"][0]["agents_no_touch"] = {
                "target": {
                    "path": str(project / "AGENTS.md"),
                    "state": snapshot(project / "AGENTS.md"),
                },
                "template": {
                    "path": str(template_path),
                    "state": snapshot(template_path),
                },
            }
            injected = contracts.seal_document("manifest", payload)
            before = _tree_bytes(base)
            with _home_env(home), self.assertRaises(ContractError) as error:
                validate_legacy_inputs(injected, _reader)
            self.assertEqual(error.exception.code, "semantic-violation")
            self.assertEqual(_tree_bytes(base), before)

    def test_no_touch_agents_drift_after_planning_blocks_validate_and_apply(self):
        from sbtd_migration import apply_migration, runtime_versions

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home = self.fixture(base)
            with _home_env(home):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    None,
                    tool_versions=runtime_versions(),
                )
                manifest_path = vault / "manifest.json"
                manifest_path.write_bytes(contracts.canonical_json_bytes(manifest))
            _write(project / "AGENTS.md", b"Customized after planning.\n")
            with _home_env(home), self.assertRaises(ContractError) as error:
                validate_legacy_inputs(manifest, _reader)
            self.assertEqual(error.exception.code, "semantic-violation")
            with _home_env(home), self.assertRaises(ContractError) as error:
                apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
            self.assertEqual(error.exception.code, "state-conflict")
            self.assertEqual(
                (project / "AGENTS.md").read_bytes(), b"Customized after planning.\n"
            )

    def test_template_carrying_legacy_marker_fails_closed(self):
        marker_template = (
            b"Project rules.\n"
            b"<!-- TRELLIS:START -->\nLegacy route.\n<!-- TRELLIS:END -->\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home = self.fixture(base, template=marker_template)
            fixture_template = base / "fixture-AGENTS.project.md"
            fixture_template.write_bytes(marker_template)
            before = _tree_bytes(base)
            with (
                mock.patch.object(
                    sbtd_migration_plan, "_PROJECT_AGENTS_TEMPLATE", fixture_template
                ),
                _home_env(home),
                self.assertRaises(ContractError) as error,
            ):
                plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    None,
                    tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                )
            self.assertEqual(error.exception.code, "ownership-conflict")
            self.assertEqual(_tree_bytes(base), before)


    def test_no_touch_project_deployment_declares_graph_build_only(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home = self.fixture(base)
            before = _tree_bytes(base)
            with _home_env(home):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    None,
                    tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                    deployment_mode="init-projects",
                )
            self.assertEqual(_tree_bytes(base), before)
            payload = manifest["payload"]
            self.assertEqual(payload["deployment"]["mode"], "init-projects")
            payload_project = payload["projects"][0]
            self.assertIsNotNone(payload_project.get("agents_no_touch"))
            deploy = [
                operation
                for operation in payload_project["private_operations"]
                if operation["phase"] == "deploy"
            ]
            self.assertEqual(
                [
                    (operation["target"], operation["change"]["kind"])
                    for operation in deploy
                ],
                [(str(project / "graft"), "build-graft")],
            )
            self.assertTrue(
                all(
                    operation["target"] != str(project / "AGENTS.md")
                    for operation in payload_project["private_operations"]
                )
            )
            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, _reader))
            self.assertEqual(_tree_bytes(base), before)

    def test_no_touch_successor_batch_carries_proof_and_omits_agents_write(self):
        from sbtd_migration import apply_migration, runtime_versions

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home = self.fixture(base)
            aligned = (project / "AGENTS.md").read_bytes()
            with _home_env(home):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    None,
                    tool_versions=runtime_versions(),
                )
                manifest_path = vault / "manifest.json"
                manifest_path.write_bytes(contracts.canonical_json_bytes(manifest))
                applied, code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
                self.assertEqual(code, 0, applied)
                receipt_path = vault / "apply.json"
                receipt_path.write_bytes(
                    contracts.canonical_json_bytes(
                        applied["migration"]["apply_receipt"]
                    )
                )
                successor = plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    None,
                    tool_versions=runtime_versions(),
                    deployment_mode="init-projects",
                    successor_manifest=manifest_path,
                    successor_apply_receipt=receipt_path,
                )
            payload_project = successor["payload"]["projects"][0]
            self.assertEqual(
                payload_project.get("agents_no_touch"),
                manifest["payload"]["projects"][0].get("agents_no_touch"),
            )
            self.assertIsNotNone(payload_project.get("agents_no_touch"))
            deploy = [
                operation
                for operation in payload_project["private_operations"]
                if operation["phase"] == "deploy"
            ]
            self.assertEqual(
                [operation["change"]["kind"] for operation in deploy],
                ["build-graft"],
            )
            self.assertTrue(
                all(
                    operation["target"] != str(project / "AGENTS.md")
                    for operation in payload_project["private_operations"]
                )
            )
            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(successor, _reader))
            self.assertEqual((project / "AGENTS.md").read_bytes(), aligned)

    def test_successor_plan_rejects_resealed_predecessor_with_self_bound_agents_template(self):
        import copy

        from sbtd_migration import apply_migration, runtime_versions

        for custom_agents in (False, True):
            with self.subTest(custom_agents=custom_agents), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                project, vault, home = self.fixture(base)
                with _home_env(home):
                    manifest = plan_migration(
                        [project], vault, "fixture-custodian", None,
                        tool_versions=runtime_versions(),
                    )
                    manifest_path = vault / "manifest.json"
                    manifest_path.write_bytes(contracts.canonical_json_bytes(manifest))
                    applied, code = apply_migration(
                        manifest_path, confirmed=True, no_routing_approvals=True
                    )
                    self.assertEqual(code, 0, applied)
                    if custom_agents:
                        _write(project / "AGENTS.md", b"Custom project rules.\n")
                    payload = copy.deepcopy(manifest["payload"])
                    proof = payload["projects"][0]["agents_no_touch"]
                    proof["target"]["state"] = snapshot(project / "AGENTS.md")
                    # Coherent file references, but a project file is not the
                    # installed template, even when its bytes happen to match.
                    proof["template"] = copy.deepcopy(proof["target"])
                    forged = contracts.seal_document("manifest", payload)
                    receipt_payload = copy.deepcopy(
                        applied["migration"]["apply_receipt"]["payload"]
                    )
                    receipt_payload["manifest_id"] = forged["manifest_id"]
                    receipt = contracts.seal_document("apply_receipt", receipt_payload)
                    contracts.validate_declared_bindings(
                        forged, {"apply_receipt": receipt}
                    )
                    manifest_path.write_bytes(contracts.canonical_json_bytes(forged))
                    receipt_path = vault / "apply.json"
                    receipt_path.write_bytes(contracts.canonical_json_bytes(receipt))
                    before = _tree_bytes(base)
                    with self.assertRaises(ContractError) as error:
                        plan_migration(
                            [project], vault, "fixture-custodian", None,
                            tool_versions=runtime_versions(),
                            deployment_mode="init-projects",
                            successor_manifest=manifest_path,
                            successor_apply_receipt=receipt_path,
                        )
                    self.assertEqual(error.exception.code, "semantic-violation")
                    self.assertEqual(_tree_bytes(base), before)

    def test_successor_plan_refuses_drifted_no_touch_proof(self):
        from sbtd_migration import apply_migration, runtime_versions

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home = self.fixture(base)
            with _home_env(home):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    None,
                    tool_versions=runtime_versions(),
                )
                manifest_path = vault / "manifest.json"
                manifest_path.write_bytes(contracts.canonical_json_bytes(manifest))
                applied, code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
                self.assertEqual(code, 0, applied)
                receipt_path = vault / "apply.json"
                receipt_path.write_bytes(
                    contracts.canonical_json_bytes(
                        applied["migration"]["apply_receipt"]
                    )
                )
            _write(project / "AGENTS.md", b"Customized after the batch.\n")
            before = _tree_bytes(base)
            with (
                _home_env(home),
                self.assertRaises(ContractError) as error,
            ):
                plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    None,
                    tool_versions=runtime_versions(),
                    deployment_mode="init-projects",
                    successor_manifest=manifest_path,
                    successor_apply_receipt=receipt_path,
                )
            self.assertEqual(error.exception.code, "state-conflict")
            self.assertEqual(_tree_bytes(base), before)

    def test_injected_deployment_agents_op_with_no_touch_proof_is_rejected(self):
        import copy

        from sbtd_graft_deployment import deployment_operations

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home = self.fixture(base)
            before = _tree_bytes(base)
            with _home_env(home):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    None,
                    tool_versions={"onboard": "fixture", "graft": "0.18.0"},
                    deployment_mode="init-projects",
                )
            payload = copy.deepcopy(manifest["payload"])
            produced, _shared = deployment_operations(
                [{"root": str(project), "private_operations": []}],
                platform="codex",
            )
            agents_op = next(
                operation
                for operation in produced[str(project)]
                if operation["selector"] == "graft-agents"
            )
            # Normalize: the crafted injection replaces any same-target deploy
            # operation so the resealed shape stays seal-coherent regardless
            # of what the producer legitimately declared.
            payload["projects"][0]["private_operations"] = [
                operation
                for operation in payload["projects"][0]["private_operations"]
                if operation["target"] != agents_op["target"]
            ]
            payload["projects"][0]["private_operations"].append(agents_op)
            tampered = contracts.seal_document("manifest", payload)
            with _home_env(home), self.assertRaises(ContractError) as error:
                validate_legacy_inputs(tampered, _reader)
            self.assertEqual(error.exception.code, "semantic-violation")
            self.assertEqual(_tree_bytes(base), before)

    def test_marker_removal_converging_to_template_retries_already_complete(self):
        """Recorded AGENTS.md = bundled template + one removable TRELLIS block.

        Plan declares the block removal and seals no agents_no_touch proof;
        apply converges the file to the exact template; a receipt-backed
        retry must stay already-complete, and the retained-original replay
        must still validate with the converged bytes in place.
        """
        from sbtd_migration import (
            _backup_sources,
            _source_backup_paths,
            apply_migration,
            runtime_versions,
        )

        template = (
            SCRIPTS.parents[0] / "templates" / "agents" / "AGENTS.project.md"
        ).read_bytes()
        block = (
            b"<!-- TRELLIS:START -->\nlegacy trellis routing\n<!-- TRELLIS:END -->"
        )
        recorded = template + block
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project = _no_touch_tree(base, template=recorded)
            _write(
                project / ".trellis/.template-hashes.json",
                _json_bytes(
                    {
                        "__version": 2,
                        "hashes": {
                            PLATFORM_REL: hashlib.sha256(PLATFORM_TOML).hexdigest(),
                            "AGENTS.md": hashlib.sha256(recorded).hexdigest(),
                        },
                    }
                ),
            )
            vault = base / "vault"
            evidence = base / "evidence"
            home = base / "home"
            for path in (vault, evidence, home):
                path.mkdir(mode=0o700)
            # A marker-removal apply requires the caller routing approval
            # file; an empty signed record seals the anchor without any
            # approved replacement.
            approval = vault / "routing-approvals.json"
            approval.write_bytes(
                json.dumps({"schema_version": 1, "items": []}).encode("utf-8")
            )
            _sign_existing_approval(approval)
            with _home_env(home):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    None,
                    tool_versions=runtime_versions(),
                    routing_approvals=approval,
                )
            payload_project = manifest["payload"]["projects"][0]
            markers = [
                operation
                for operation in payload_project["private_operations"]
                if operation["selector"] == "trellis-block"
            ]
            self.assertEqual(
                [operation["target"] for operation in markers],
                [str(project / "AGENTS.md")],
            )
            self.assertEqual(markers[0]["change"], {"kind": "remove"})
            self.assertIsNone(payload_project.get("agents_no_touch"))
            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, _reader))
                manifest_path = evidence / "manifest.json"
                manifest_path.write_bytes(contracts.canonical_json_bytes(manifest))
                applied, code = apply_migration(
                    manifest_path, confirmed=True, routing_approvals=approval
                )
                self.assertEqual(code, 0, applied)
                self.assertEqual(applied["status"], "applied")
            self.assertEqual((project / "AGENTS.md").read_bytes(), template)
            receipt_path = vault / "apply.json"
            receipt_path.write_bytes(
                contracts.canonical_json_bytes(
                    applied["migration"]["apply_receipt"]
                )
            )
            with _home_env(home):
                repeated, code = apply_migration(
                    manifest_path,
                    previous_receipt_path=receipt_path,
                    confirmed=True,
                    routing_approvals=approval,
                )
                self.assertEqual(code, 0, repeated)
                self.assertEqual(repeated["status"], "already-complete")
            self.assertEqual((project / "AGENTS.md").read_bytes(), template)
            source_root = project / ".trellis"
            backup = _source_backup_paths(manifest)[str(source_root)]
            _backup_sources(manifest)
            source_root.rename(base / "retired-source")
            resolve_receipt = _receipt_reader(
                manifest, applied["migration"]["apply_receipt"]
            )

            def original(reference):
                path = Path(reference["path"])
                if path.is_relative_to(source_root):
                    return read_file(
                        backup / path.relative_to(source_root), reference["state"]
                    )
                # Retired platform files resolve through the receipt's retained
                # backups, exactly as apply-time revalidation resolves them.
                return resolve_receipt(reference)

            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, original))
            self.assertEqual((project / "AGENTS.md").read_bytes(), template)


class MigrationHistoricBranchHandoffTests(unittest.TestCase):
    """A legacy task branch differing from the planning checkout defers recovery."""

    def fixture(self, base, *, task_branch="feature/legacy-program", checkout="staging"):
        project = _base_tree(base)
        subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
        subprocess.run(
            ["git", "checkout", "-b", checkout],
            cwd=project,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "-c", "user.name=fixture",
                "-c", "user.email=fixture@test",
                "-c", "commit.gpgsign=false",
                "commit", "--allow-empty", "-m", "fixture revision",
            ],
            cwd=project,
            check=True,
            capture_output=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=project, check=True, capture_output=True
        ).stdout.decode("utf-8").strip()
        vault = base / "vault"
        vault.mkdir(mode=0o700)
        home = base / "home"
        home.mkdir(mode=0o700)
        items = []
        _add_task(
            project,
            vault,
            items,
            source_overrides={"branch": task_branch},
            task_md_kwargs={"branch": task_branch},
        )
        journal = project / ".trellis/workspace/dev01/journal-1.md"
        session = project / ".trellis/.runtime/sessions/codex_fixture.json"
        _write(journal, b"# Work remaining\nFinish alpha validation.\n")
        _write(
            session,
            _json_bytes(
                {
                    "platform": "codex",
                    "last_seen_at": "2026-09-21T10:00:00Z",
                    "current_task": ".trellis/tasks/09-01-alpha",
                    "current_run": None,
                }
            ),
        )
        return project, vault, home, items, [journal, session], head

    def approve(
        self,
        project,
        vault,
        items,
        sources,
        head,
        *,
        task_id="alpha",
        branch="feature/legacy-program",
        checkout="staging",
        instruction="deferred",
    ):
        from sbtd_handoff import _REDACTION_DECLARATION, HandoffStore
        from sbtd_task_state import TaskStore

        next_action = "Inspect the task and run its validation"
        if instruction in ("deferred", "foreign"):
            from sbtd_migration_plan import _deferred_recovery_instruction

            seen = checkout if instruction == "deferred" else "origin/elsewhere"
            next_action = (
                _deferred_recovery_instruction(branch, seen) + "\n" + next_action
            )
        handoff = {
            "schema_version": 1,
            "task_id": task_id,
            "task_path": f"ai/tasks/{task_id}/task.md",
            "task_status": "planned",
            "workflow_mode": None,
            "mode_source": "migration-unknown",
            "mode_note": "legacy Trellis task without mode proof",
            "project_root": str(project),
            "branch": branch,
            "head": head,
            "created_at": "2026-09-21T10:00:00+00:00",
            "content": {
                "goal": "Complete the migrated task",
                "decisions": ["Keep migration approval separate from continuation"],
                "completed": ["Implementation"],
                "remaining": ["Run validation"],
                "changed_files": [],
                "verification": [],
                "do_not_repeat": ["Do not restore retired routing"],
                "next_action": next_action,
                "limitations": "Legacy mode is unproven",
            },
            "policy": {"task_opt_out": False, "session_opt_out": False},
            "redaction": _REDACTION_DECLARATION,
        }
        store = HandoffStore(TaskStore(project, read_only=True))
        name = "2026_09_21-" + hashlib.sha256(task_id.encode()).hexdigest() + ".md"
        candidate = vault / f"handoff-{task_id}.md"
        candidate.write_text(store._render(handoff), encoding="utf-8")
        target = project / "docs/handoffs" / name
        items.append(
            _item(
                f"handoff-{task_id}",
                [_ref(path) for path in sources],
                target,
                "redact",
                candidate,
            )
        )
        return target, candidate

    def test_historic_branch_handoff_accepted_with_deferred_recovery_instruction(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items, sources, head = self.fixture(base)
            target, _candidate = self.approve(project, vault, items, sources, head)
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            manifest = _plan(project, vault, decisions, home)
            self.assertEqual(_tree_bytes(base), before)
            payload_project = manifest["payload"]["projects"][0]
            self.assertEqual(payload_project["source_ref"], "staging")
            self.assertEqual(payload_project["head"], head)
            operations = payload_project["private_operations"]
            self.assertIn(str(target), {op["target"] for op in operations})
            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, _reader))
            self.assertFalse((project / ".sbtd/active-task.json").exists())
            self.assertEqual(_tree_bytes(base), before)

    def test_historic_branch_handoff_applies_and_task_store_gate_still_blocks_writes(
        self,
    ):
        from sbtd_handoff import HandoffPolicy, HandoffStore
        from sbtd_migration import apply_migration, runtime_versions
        from sbtd_task_state import TaskStore

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items, sources, head = self.fixture(base)
            target, candidate = self.approve(project, vault, items, sources, head)
            with _home_env(home):
                manifest = plan_migration(
                    [project],
                    vault,
                    "fixture-custodian",
                    _decisions(vault, items),
                    tool_versions=runtime_versions(),
                )
                manifest_path = vault / "manifest.json"
                manifest_path.write_bytes(contracts.canonical_json_bytes(manifest))
                receipt, code = apply_migration(
                    manifest_path, confirmed=True, no_routing_approvals=True
                )
                self.assertEqual(code, 0, receipt)
                receipt_path = vault / "apply.json"
                receipt_path.write_bytes(
                    contracts.canonical_json_bytes(
                        receipt["migration"]["apply_receipt"]
                    )
                )
                repeated, code = apply_migration(
                    manifest_path,
                    previous_receipt_path=receipt_path,
                    confirmed=True,
                    no_routing_approvals=True,
                )
                self.assertEqual(code, 0, repeated)
            self.assertEqual(target.read_bytes(), candidate.read_bytes())
            document = TaskStore(project, read_only=True).inspect("alpha").document
            self.assertEqual(
                document.frontmatter["branch"], "feature/legacy-program"
            )
            handoffs = HandoffStore(TaskStore(project))
            blocked = handoffs.save(
                "alpha",
                content={
                    "goal": "Continue the migrated task",
                    "decisions": [],
                    "completed": [],
                    "remaining": ["Run validation"],
                    "changed_files": [],
                    "verification": [],
                    "do_not_repeat": [],
                    "next_action": "Run validation",
                    "limitations": "none",
                },
                trigger="manual",
                policy=HandoffPolicy(),
                confirmed=True,
                redaction_confirmed=True,
            )
            self.assertEqual(blocked.status, "branch-conflict")
            self.assertFalse(blocked.persisted)

    def test_branch_mismatch_handoff_without_resume_instruction_is_refused(self):
        for instruction in ("absent", "foreign"):
            with self.subTest(instruction=instruction), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                project, vault, home, items, sources, head = self.fixture(base)
                self.approve(
                    project, vault, items, sources, head, instruction=instruction
                )
                decisions = _decisions(vault, items)
                before = _tree_bytes(base)
                with self.assertRaises(ContractError) as error:
                    _plan(project, vault, decisions, home)
                self.assertEqual(error.exception.code, "candidate-conflict")
                self.assertEqual(_tree_bytes(base), before)

    def test_handoff_branch_rewritten_to_checkout_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items, sources, head = self.fixture(base)
            self.approve(
                project,
                vault,
                items,
                sources,
                head,
                branch="staging",
                instruction="absent",
            )
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            with self.assertRaises(ContractError) as error:
                _plan(project, vault, decisions, home)
            self.assertEqual(error.exception.code, "candidate-conflict")
            self.assertEqual(_tree_bytes(base), before)

    def test_handoff_head_that_is_not_planning_head_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items, sources, _head = self.fixture(base)
            self.approve(
                project, vault, items, sources, "0" * 40, instruction="absent"
            )
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            with self.assertRaises(ContractError) as error:
                _plan(project, vault, decisions, home)
            self.assertEqual(error.exception.code, "candidate-conflict")
            self.assertEqual(_tree_bytes(base), before)

    def test_resume_instruction_without_branch_mismatch_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items, sources, head = self.fixture(
                base, task_branch="staging"
            )
            self.approve(
                project,
                vault,
                items,
                sources,
                head,
                branch="staging",
                instruction="deferred",
            )
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            with self.assertRaises(ContractError) as error:
                _plan(project, vault, decisions, home)
            self.assertEqual(error.exception.code, "candidate-conflict")
            self.assertEqual(_tree_bytes(base), before)

    def test_same_branch_handoff_needs_no_recovery_instruction(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            project, vault, home, items, sources, head = self.fixture(
                base, task_branch="staging"
            )
            target, _candidate = self.approve(
                project,
                vault,
                items,
                sources,
                head,
                branch="staging",
                instruction="absent",
            )
            decisions = _decisions(vault, items)
            before = _tree_bytes(base)
            manifest = _plan(project, vault, decisions, home)
            self.assertEqual(_tree_bytes(base), before)
            operations = manifest["payload"]["projects"][0]["private_operations"]
            self.assertIn(str(target), {op["target"] for op in operations})
            with _home_env(home):
                self.assertIsNone(validate_legacy_inputs(manifest, _reader))
            self.assertEqual(_tree_bytes(base), before)

if __name__ == "__main__":
    unittest.main()
