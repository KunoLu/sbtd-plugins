"""Engine scenarios for the Onboard upgrade alignment core.

Covers the engine side of U01-U09: read-only planning, guarded apply,
forgery/drift rejection, idempotent retry, interruption and failure
recovery, host semantic verification, recovery plans, and the staged
isolated self-upgrade executor. Inventory and host providers are fixture
doubles driven by ``upgrade_fixture.json`` inside a synthetic package; the
same fixture files are copied into the staged package so the isolated
subprocess executes the identical code path. All filesystem effects use
real temporary directories and the real migration primitives.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "sbtd-workflow-onboard" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import sbtd_upgrade
from onboard_contracts import ContractError
from sbtd_migration_files import require_private_directory, snapshot

FIXTURE_INVENTORY = '''\
"""Fixture inventory provider driven by upgrade_fixture.json."""
from __future__ import annotations

import json
from pathlib import Path

from onboard_contracts import ContractError
from sbtd_migration_files import snapshot


def _root(package_root):
    if package_root is not None:
        return Path(package_root)
    return Path(__file__).resolve().parents[1]


def _spec(root):
    return json.loads((root / "upgrade_fixture.json").read_text(encoding="utf-8"))


def payload_directory_state(path):
    return snapshot(Path(path))


def payload_file_state(path):
    return snapshot(Path(path))

_PLATFORM_ALIASES = {"oh-my-pi": "omp"}


def normalize_host_platform(value):
    if not isinstance(value, str) or not value:
        raise ContractError("invalid-config", "host platform must be a non-empty string")
    return _PLATFORM_ALIASES.get(value, value)


def normalize_scope(scope):
    """Fixture canonicalization mirroring the inventory provider contract."""
    if not isinstance(scope, dict) or scope.get("schema_version") != 1:
        raise ContractError("invalid-config", "the upgrade scope must declare schema_version 1")
    normalized = json.loads(json.dumps(scope))
    for host in normalized.get("hosts", []):
        host["platform"] = normalize_host_platform(host.get("platform"))
    return normalized


def _state(path):
    probe = snapshot(Path(path))
    if probe["type"] == "directory":
        return payload_directory_state(Path(path))
    if probe["type"] == "file":
        return payload_file_state(Path(path))
    return probe


def _decision(classification, choice):
    if classification == "missing":
        return "preserve" if choice == "preserve" else "install"
    if classification == "current":
        return "keep"
    if classification == "identity-conflict":
        return "preserve" if choice == "preserve" else "blocked"
    if choice == "replace":
        return "replace"
    if choice == "preserve":
        return "preserve"
    return "blocked"


def build_inventory(scope, *, package_root=None):
    root = _root(package_root)
    spec = _spec(root)
    decisions = scope.get("decisions", {})
    resources = []
    for entry in spec["resources"]:
        source = root / entry["source"]
        target = Path(entry["target"])
        desired = _state(source)
        before = _state(target)
        if bool(entry.get("conflict")):
            classification = "identity-conflict"
        elif before["type"] == "absent":
            classification = "missing"
        elif before == desired:
            classification = "current"
        elif bool(entry.get("known_old")):
            classification = "known-old"
        else:
            classification = "unknown-drift"
        decision = _decision(classification, decisions.get(str(target)))
        resources.append(
            {
                "id": entry["id"],
                "kind": entry.get("kind", "skill"),
                "target": str(target),
                "source": {"path": str(source), "state": desired},
                "before": before,
                "desired": desired,
                "classification": classification,
                "decision": decision,
                "details": entry.get("details", {}),
            }
        )
    baseline = {
        "schema_version": 1,
        "baseline_id": spec["baseline_id"],
        "catalog": {"sha256": spec.get("catalog_sha256", "0" * 64)},
        "stable": {"stable_set": "fixture"},
        "runtime": {"requirements_sha256": "0" * 64},
        "source": {"path": str(root), "state": payload_directory_state(root)},
    }
    return {"baseline": baseline, "resources": resources, "domains": spec.get("domains", [])}
'''

FIXTURE_HOSTS = '''\
"""Fixture hosts provider driven by upgrade_fixture.json."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from onboard_contracts import ContractError
from sbtd_migration_files import snapshot


def _root(package_root):
    if package_root is not None:
        return Path(package_root)
    return Path(__file__).resolve().parents[1]


def _spec(root):
    return json.loads((root / "upgrade_fixture.json").read_text(encoding="utf-8"))


def _content(root, entry):
    return (root / entry["content"]).read_bytes()


def _rendered(entry, content):
    return {"type": "file", "checksum": hashlib.sha256(content).hexdigest()}


def build_host_resources(scope, *, package_root=None):
    root = _root(package_root)
    spec = _spec(root)
    decisions = scope.get("decisions", {})
    resources = []
    for entry in spec.get("host_resources", []):
        target = Path(entry["target"])
        rendered = _rendered(entry, _content(root, entry))
        before = snapshot(target)
        if bool(entry.get("conflict")):
            classification = "identity-conflict"
        elif before == rendered:
            classification = "current"
        elif before["type"] == "absent":
            classification = "missing"
        else:
            classification = "unknown-drift"
        choice = decisions.get(str(target))
        if classification == "missing":
            decision = "preserve" if choice == "preserve" else "install"
        elif classification == "current":
            decision = "keep"
        elif classification == "identity-conflict":
            decision = "preserve" if choice == "preserve" else "blocked"
        elif choice == "replace":
            decision = "replace"
        elif choice == "preserve":
            decision = "preserve"
        else:
            decision = "blocked"
        desired = rendered if decision in ("install", "replace", "keep") else None
        if entry["kind"] == "shell":
            bin_dir = next(
                (profile["bin"] for profile in scope.get("shell_profiles", []) if profile["path"] == str(target)),
                str(target.parent / "bin"),
            )
            descriptor = {
                "profile": {
                    "path": str(target),
                    "shell": entry.get("shell", "bash"),
                    "bin": bin_dir,
                }
            }
        else:
            descriptor = {
                "host": {
                    "id": entry.get("host", "fixture-host"),
                    "platform": "darwin",
                    "config_home": str(target.parent),
                    "config": target.name,
                }
            }
        resources.append(
            {
                "id": entry["id"],
                "kind": entry["kind"],
                "target": str(target),
                "source": bin_dir if entry["kind"] == "shell" else str(root / "scripts"),
                "before": before,
                "desired": desired,
                "classification": classification,
                "decision": decision,
                "details": {
                    "package_root": str(root),
                    "managed_digest": rendered["checksum"],
                    **({
                        "command_identity": {
                            "path": str(Path(bin_dir) / "graft"),
                            "resolved": None,
                            "link": None,
                            "state": snapshot(Path(bin_dir) / "graft"),
                        },
                    } if entry["kind"] == "shell" else {}),
                },
                **descriptor,
            }
        )
    return resources


def render_resource(resource, *, package_root=None):
    root = _root(package_root)
    if package_root is not None and str(root) != resource["details"]["package_root"]:
        raise ContractError("invalid-argument", "package_root mismatch")
    spec = _spec(root)
    for entry in spec.get("host_resources", []):
        if entry["id"] == resource["id"]:
            if snapshot(Path(entry["target"])) != resource["before"]:
                raise ContractError("state-conflict", "host target changed")
            return _content(root, entry)
    raise ContractError("invalid-argument", "unknown host resource")


def _disk(root, entry, target, decisions):
    measured = snapshot(target)
    if measured["type"] == "absent":
        return {"status": "missing", "decision": decisions.get(str(target))}
    try:
        live = target.read_bytes()
    except OSError:
        return {"status": "blocked", "decision": decisions.get(str(target))}
    # Semantic rule: managed content embedded in a larger user file stays
    # aligned; losing the managed bytes drifts.
    status = "aligned" if _content(root, entry) in live else "drifted"
    return {"status": status, "decision": decisions.get(str(target))}


def verify_hosts(scope, *, package_root=None, probe=False, link_authorizations=None):
    root = _root(package_root)
    spec = _spec(root)
    decisions = scope.get("decisions", {})
    hosts = []
    profiles = []
    for entry in spec.get("host_resources", []):
        target = Path(entry["target"])
        disk = _disk(root, entry, target, decisions)
        if entry["kind"] == "shell":
            profiles.append(
                {
                    "path": str(target),
                    "shell": entry.get("shell", "bash"),
                    "status": "unverified",
                    "disk": disk,
                    "host": "unverified",
                    "legacy": "none",
                }
            )
        else:
            hosts.append(
                {
                    "id": entry.get("host", "fixture-host"),
                    "platform": "darwin",
                    "applicability": "supported",
                    "status": "unverified",
                    "disk": disk,
                    "runtime": "verified" if probe else "unverified",
                    "host": "verified" if probe else "unverified",
                    "legacy": "none",
                }
            )
    return {"probe": probe, "hosts": hosts, "shell_profiles": profiles}
'''

ENGINE_COPY = (
    "sbtd_upgrade.py",
    "sbtd_upgrade_paths.py",
    "onboard_contracts.py",
    "sbtd_migration_files.py",
    "sbtd_cleanup_targets.py",
    "sbtd_project.py",
)


class UpgradeEngineTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.base, True)
        previous = {
            name: sys.modules.get(name)
            for name in ("sbtd_upgrade_inventory", "sbtd_upgrade_hosts")
        }

        def restore_providers():
            for name, module in previous.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

        self.addCleanup(restore_providers)

    # -- fixture helpers ----------------------------------------------------

    def _vault(self, name: str = "vault") -> Path:
        return require_private_directory(self.base / name, create=True)

    def _package(
        self,
        *,
        fixture: dict,
        files: dict[str, str],
        name: str = "pkg",
        with_scripts: bool = True,
    ) -> Path:
        package = self.base / name
        scripts = package / "scripts"
        scripts.mkdir(parents=True)
        if with_scripts:
            for module_name in ENGINE_COPY:
                shutil.copy(SCRIPTS / module_name, scripts / module_name)
        (scripts / "sbtd_upgrade_inventory.py").write_text(
            FIXTURE_INVENTORY, encoding="utf-8"
        )
        (scripts / "sbtd_upgrade_hosts.py").write_text(FIXTURE_HOSTS, encoding="utf-8")
        (package / "upgrade_fixture.json").write_text(
            json.dumps(fixture), encoding="utf-8"
        )
        for relative, content in files.items():
            path = package / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode("utf-8"))
        return package

    def _register(self, package: Path) -> None:
        for name in ("sbtd_upgrade_inventory", "sbtd_upgrade_hosts"):
            path = package / "scripts" / f"{name}.py"
            module = types.ModuleType(name)
            module.__file__ = str(path)
            sys.modules[name] = module
            exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)  # noqa: S102 -- test-owned provider source
        patcher = mock.patch.object(sbtd_upgrade, "_trusted_package_root", return_value=package)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _real_module(self, name: str):
        alias = f"_upgrade_engine_real_{name}"
        path = SCRIPTS / f"{name}.py"
        module = types.ModuleType(alias)
        module.__file__ = str(path)
        sys.modules[alias] = module
        self.addCleanup(sys.modules.pop, alias, None)
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)  # noqa: S102 -- repository-owned test import
        return module

    def _skills_root(self, name: str = "skills") -> Path:
        root = self.base / name
        root.mkdir()
        return root

    def _skill_fixture(self, target: Path, source: str, **flags) -> dict:
        entry = {
            "id": f"skill@{target}",
            "kind": "skill",
            "source": source,
            "target": str(target),
        }
        entry.update(flags)
        return entry

    def _plan(self, scope: dict, vault: Path, package: Path) -> dict:
        return sbtd_upgrade.plan_upgrade(scope, vault, package_root=package)

    def _apply_local(self, plan: dict, receipt: dict | None = None) -> dict:
        return sbtd_upgrade._apply_upgrade_local(
            plan,
            confirmed=plan["plan_id"],
            receipt=receipt,
            package_root=Path(plan["payload"]["baseline"]["source"]["path"]),
        )

    def _apply_recovery_local(
        self, recovery_plan: dict, receipt: dict | None = None
    ) -> dict:
        return sbtd_upgrade._apply_recovery_local(
            recovery_plan,
            confirmed=recovery_plan["recovery_id"],
            receipt=receipt,
            package_root=None,
        )

    def _receipt_rows(self, receipt: dict) -> dict[str, dict]:
        return {row["id"]: row for row in receipt["payload"]["resources"]}

    def _forge(self, plan: dict, mutate) -> dict:
        forged = copy.deepcopy(plan)
        mutate(forged["payload"])
        forged["plan_id"] = sbtd_upgrade._digest(forged["payload"])
        return forged

    # -- plan phase ---------------------------------------------------------

    def test_plan_is_read_only_and_deterministic(self):
        skills = self._skills_root()
        target = skills / "skill-a"
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [self._skill_fixture(target, "payload/skill-a")],
            },
            files={"payload/skill-a/SKILL.md": "---\nname: skill-a\n---\n"},
        )
        self._register(package)
        vault = self._vault()
        scope = {"schema_version": 1, "skills_roots": [str(skills)]}
        plan = self._plan(scope, vault, package)
        self.assertEqual(plan["schema_version"], 1)
        self.assertEqual(plan["payload"]["plan_schema"], "upgrade-plan")
        self.assertEqual(plan["payload"]["status"], "planned")
        self.assertEqual(plan["payload"]["backup_root"], str(vault))
        (resource,) = plan["payload"]["resources"]
        self.assertEqual(resource["classification"], "missing")
        self.assertEqual(resource["decision"], "install")
        self.assertEqual(resource["target"], str(target))
        again = self._plan(scope, vault, package)
        self.assertEqual(plan["plan_id"], again["plan_id"])
        self.assertFalse(target.exists())
        self.assertEqual(list(vault.iterdir()), [])

    def test_plan_requires_existing_private_vault(self):
        skills = self._skills_root()
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [
                    self._skill_fixture(skills / "skill-a", "payload/skill-a")
                ],
            },
            files={"payload/skill-a/SKILL.md": "x\n"},
        )
        self._register(package)
        scope = {"schema_version": 1, "skills_roots": [str(skills)]}
        with self.assertRaises(ContractError):
            self._plan(scope, self.base / "missing-vault", package)
        open_vault = self.base / "open-vault"
        open_vault.mkdir(mode=0o755)
        with self.assertRaises(ContractError):
            self._plan(scope, open_vault, package)

    def test_plan_rejects_vault_overlapping_target(self):
        skills = self._skills_root()
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [
                    self._skill_fixture(skills / "skill-a", "payload/skill-a")
                ],
            },
            files={"payload/skill-a/SKILL.md": "x\n"},
        )
        self._register(package)
        nested_vault = skills / "skill-a"
        require_private_directory(nested_vault, create=True)
        scope = {"schema_version": 1, "skills_roots": [str(skills)]}
        with self.assertRaises(ContractError) as caught:
            self._plan(scope, nested_vault, package)
        self.assertEqual(caught.exception.code, "backup-root-overlap")

    def test_plan_marks_undecided_drift_blocked_without_leaking_content(self):
        skills = self._skills_root()
        drifted = skills / "skill-a"
        drifted.mkdir()
        (drifted / "SKILL.md").write_text("user customized SECRET-TOKEN\n", encoding="utf-8")
        legacy = skills / "skill-b"
        legacy.mkdir()
        (legacy / "SKILL.md").write_text("old managed copy\n", encoding="utf-8")
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [
                    self._skill_fixture(drifted, "payload/skill-a"),
                    self._skill_fixture(legacy, "payload/skill-b", known_old=True),
                ],
            },
            files={
                "payload/skill-a/SKILL.md": "new\n",
                "payload/skill-b/SKILL.md": "newer\n",
            },
        )
        self._register(package)
        vault = self._vault()
        scope = {"schema_version": 1, "skills_roots": [str(skills)]}
        plan = self._plan(scope, vault, package)
        self.assertEqual(plan["payload"]["status"], "blocked")
        rows = {row["id"]: row for row in plan["payload"]["resources"]}
        self.assertEqual(rows[f"skill@{drifted}"]["classification"], "unknown-drift")
        self.assertEqual(rows[f"skill@{drifted}"]["decision"], "blocked")
        self.assertEqual(rows[f"skill@{legacy}"]["classification"], "known-old")
        self.assertEqual(rows[f"skill@{legacy}"]["decision"], "blocked")
        self.assertNotIn("SECRET-TOKEN", json.dumps(plan))
        self.assertEqual(list(vault.iterdir()), [])

    # -- apply phase --------------------------------------------------------

    def test_apply_install_lifecycle_and_verify_aligned(self):
        skills = self._skills_root()
        target = skills / "skill-a"
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [self._skill_fixture(target, "payload/skill-a")],
            },
            files={
                "payload/skill-a/SKILL.md": "---\nname: skill-a\n---\n",
                "payload/skill-a/helper.py": "print('a')\n",
            },
        )
        self._register(package)
        vault = self._vault()
        scope = {"schema_version": 1, "skills_roots": [str(skills)]}
        plan = self._plan(scope, vault, package)
        receipt = self._apply_local(plan)
        self.assertEqual(receipt["payload"]["status"], "complete")
        self.assertEqual(receipt["status"], "complete")
        self.assertEqual(receipt["payload"]["plan_id"], plan["plan_id"])
        self.assertIsNone(receipt["payload"]["previous_receipt_id"])
        self.assertEqual(receipt["payload"]["sequence"], 0)
        self.assertEqual(
            (target / "SKILL.md").read_text(encoding="utf-8"),
            "---\nname: skill-a\n---\n",
        )
        row = self._receipt_rows(receipt)[f"skill@{target}"]
        self.assertEqual(row["result"], "succeeded")
        self.assertEqual(row["after"], row["desired"])
        self.assertIsNone(row["backup_ref"])
        self.assertTrue(list(vault.glob("upgrade-receipt-*.json")))
        verification = sbtd_upgrade.verify_upgrade(plan, receipt=receipt)
        self.assertEqual(verification["payload"]["status"], "aligned")
        self.assertEqual(verification["status"], "aligned")
        (seen,) = verification["payload"]["resources"]
        self.assertEqual(seen["result"], "aligned")

    def test_apply_known_old_replace_preserves_original_backup(self):
        skills = self._skills_root()
        target = skills / "skill-a"
        target.mkdir()
        (target / "SKILL.md").write_text("original managed copy\n", encoding="utf-8")
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [
                    self._skill_fixture(target, "payload/skill-a", known_old=True)
                ],
            },
            files={"payload/skill-a/SKILL.md": "current baseline\n"},
        )
        self._register(package)
        vault = self._vault()
        scope = {
            "schema_version": 1,
            "skills_roots": [str(skills)],
            "decisions": {str(target): "replace"},
        }
        plan = self._plan(scope, vault, package)
        (resource,) = plan["payload"]["resources"]
        self.assertEqual(resource["classification"], "known-old")
        self.assertEqual(resource["decision"], "replace")
        original_state = snapshot(target)
        receipt = self._apply_local(plan)
        self.assertEqual(receipt["payload"]["status"], "complete")
        self.assertEqual(
            (target / "SKILL.md").read_text(encoding="utf-8"), "current baseline\n"
        )
        row = self._receipt_rows(receipt)[f"skill@{target}"]
        self.assertEqual(row["result"], "succeeded")
        self.assertIsNotNone(row["backup_ref"])
        backup = Path(row["backup_ref"]["path"])
        self.assertEqual(
            (backup / "SKILL.md").read_text(encoding="utf-8"),
            "original managed copy\n",
        )
        self.assertEqual(row["backup_ref"]["state"], original_state)
        verification = sbtd_upgrade.verify_upgrade(plan, receipt=receipt)
        self.assertEqual(verification["payload"]["status"], "aligned")

    def test_apply_requires_matching_confirmation(self):
        skills = self._skills_root()
        target = skills / "skill-a"
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [self._skill_fixture(target, "payload/skill-a")],
            },
            files={"payload/skill-a/SKILL.md": "x\n"},
        )
        self._register(package)
        vault = self._vault()
        scope = {"schema_version": 1, "skills_roots": [str(skills)]}
        plan = self._plan(scope, vault, package)
        with self.assertRaises(ContractError) as missing:
            sbtd_upgrade._apply_upgrade_local(
                plan, confirmed=None, receipt=None, package_root=package
            )
        self.assertEqual(missing.exception.code, "confirmation-required")
        with self.assertRaises(ContractError) as wrong:
            sbtd_upgrade._apply_upgrade_local(
                plan, confirmed="0" * 64, receipt=None, package_root=package
            )
        self.assertEqual(wrong.exception.code, "confirmation-mismatch")
        self.assertFalse(target.exists())

    def test_apply_rejects_forged_target_path(self):
        skills = self._skills_root()
        target = skills / "skill-a"
        attacker = self.base / "attacker" / "skill-a"
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [self._skill_fixture(target, "payload/skill-a")],
            },
            files={"payload/skill-a/SKILL.md": "x\n"},
        )
        self._register(package)
        vault = self._vault()
        scope = {"schema_version": 1, "skills_roots": [str(skills)]}
        plan = self._plan(scope, vault, package)

        def redirect(payload):
            payload["resources"][0]["target"] = str(attacker)

        forged = self._forge(plan, redirect)
        with self.assertRaises(ContractError) as caught:
            self._apply_local(forged)
        self.assertEqual(caught.exception.code, "plan-stale")
        self.assertFalse(attacker.exists())
        self.assertFalse(target.exists())

    def test_apply_rejects_forged_decision_flip(self):
        skills = self._skills_root()
        target = skills / "skill-a"
        target.mkdir()
        (target / "SKILL.md").write_text("user content\n", encoding="utf-8")
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [self._skill_fixture(target, "payload/skill-a")],
            },
            files={"payload/skill-a/SKILL.md": "baseline\n"},
        )
        self._register(package)
        vault = self._vault()
        scope = {
            "schema_version": 1,
            "skills_roots": [str(skills)],
            "decisions": {str(target): "preserve"},
        }
        plan = self._plan(scope, vault, package)
        self.assertEqual(plan["payload"]["resources"][0]["decision"], "preserve")

        def flip(payload):
            payload["resources"][0]["decision"] = "replace"

        forged = self._forge(plan, flip)
        with self.assertRaises(ContractError) as caught:
            self._apply_local(forged)
        self.assertEqual(caught.exception.code, "plan-inconsistent")
        self.assertEqual(
            (target / "SKILL.md").read_text(encoding="utf-8"), "user content\n"
        )

    def test_apply_rejects_source_drift_after_plan(self):
        skills = self._skills_root()
        target = skills / "skill-a"
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [self._skill_fixture(target, "payload/skill-a")],
            },
            files={"payload/skill-a/SKILL.md": "v1\n"},
        )
        self._register(package)
        vault = self._vault()
        scope = {"schema_version": 1, "skills_roots": [str(skills)]}
        plan = self._plan(scope, vault, package)
        (package / "payload/skill-a/SKILL.md").write_text("v2\n", encoding="utf-8")
        with self.assertRaises(ContractError) as caught:
            self._apply_local(plan)
        self.assertEqual(caught.exception.code, "plan-stale")
        self.assertFalse(target.exists())

    def test_apply_rejects_target_drift_after_plan(self):
        skills = self._skills_root()
        target = skills / "skill-a"
        target.mkdir()
        (target / "SKILL.md").write_text("custom v1\n", encoding="utf-8")
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [self._skill_fixture(target, "payload/skill-a")],
            },
            files={"payload/skill-a/SKILL.md": "baseline\n"},
        )
        self._register(package)
        vault = self._vault()
        scope = {
            "schema_version": 1,
            "skills_roots": [str(skills)],
            "decisions": {str(target): "replace"},
        }
        plan = self._plan(scope, vault, package)
        (target / "SKILL.md").write_text("custom v2\n", encoding="utf-8")
        with self.assertRaises(ContractError) as caught:
            self._apply_local(plan)
        self.assertEqual(caught.exception.code, "state-conflict")
        self.assertEqual(
            (target / "SKILL.md").read_text(encoding="utf-8"), "custom v2\n"
        )

    def test_apply_refuses_blocked_resources(self):
        skills = self._skills_root()
        target = skills / "skill-a"
        target.mkdir()
        (target / "SKILL.md").write_text("custom\n", encoding="utf-8")
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [self._skill_fixture(target, "payload/skill-a")],
            },
            files={"payload/skill-a/SKILL.md": "baseline\n"},
        )
        self._register(package)
        vault = self._vault()
        scope = {"schema_version": 1, "skills_roots": [str(skills)]}
        plan = self._plan(scope, vault, package)
        self.assertEqual(plan["payload"]["status"], "blocked")
        with self.assertRaises(ContractError) as caught:
            self._apply_local(plan)
        self.assertEqual(caught.exception.code, "blocked-resource")
        self.assertEqual(
            (target / "SKILL.md").read_text(encoding="utf-8"), "custom\n"
        )

    # -- retry, interruption and failure -------------------------------------

    def test_retry_after_completion_is_idempotent(self):
        skills = self._skills_root()
        target = skills / "skill-a"
        target.mkdir()
        (target / "SKILL.md").write_text("old\n", encoding="utf-8")
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [self._skill_fixture(target, "payload/skill-a")],
            },
            files={"payload/skill-a/SKILL.md": "new\n"},
        )
        self._register(package)
        vault = self._vault()
        scope = {
            "schema_version": 1,
            "skills_roots": [str(skills)],
            "decisions": {str(target): "replace"},
        }
        plan = self._plan(scope, vault, package)
        first = self._apply_local(plan)
        self.assertEqual(first["payload"]["status"], "complete")
        backups_after_first = sorted(vault.glob("originals/**/*"))
        mtime = (target / "SKILL.md").stat().st_mtime_ns
        second = self._apply_local(plan, receipt=first)
        self.assertEqual(second["payload"]["status"], "complete")
        self.assertEqual(second["payload"]["sequence"], 1)
        self.assertEqual(
            second["payload"]["previous_receipt_id"], first["receipt_id"]
        )
        row = self._receipt_rows(second)[f"skill@{target}"]
        self.assertEqual(row["result"], "skipped-complete")
        self.assertEqual((target / "SKILL.md").stat().st_mtime_ns, mtime)
        self.assertEqual(sorted(vault.glob("originals/**/*")), backups_after_first)

    def test_interrupted_write_reconciled_from_intent(self):
        skills = self._skills_root()
        target = skills / "skill-a"
        target.mkdir()
        (target / "SKILL.md").write_text("old\n", encoding="utf-8")
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [self._skill_fixture(target, "payload/skill-a")],
            },
            files={"payload/skill-a/SKILL.md": "new\n"},
        )
        self._register(package)
        vault = self._vault()
        scope = {
            "schema_version": 1,
            "skills_roots": [str(skills)],
            "decisions": {str(target): "replace"},
        }
        plan = self._plan(scope, vault, package)
        real_save = sbtd_upgrade.save_document
        injected = {"failed": False}

        def flaky_save(path, document, *, private_root):
            if (
                Path(path).name.startswith("upgrade-receipt-")
                and not injected["failed"]
                and any(row["result"] == "succeeded" for row in document["payload"]["resources"])
            ):
                injected["failed"] = True
                raise ContractError(
                    "write-failed", "injected interruption", exit_code=3
                )
            return real_save(path, document, private_root=private_root)

        with mock.patch.object(sbtd_upgrade, "save_document", flaky_save), self.assertRaises(ContractError):
            self._apply_local(plan)
        self.assertEqual(
            (target / "SKILL.md").read_text(encoding="utf-8"), "new\n"
        )
        initial_files = list(vault.glob("upgrade-receipt-*.json"))
        self.assertTrue(initial_files)
        initial = json.loads(initial_files[0].read_text(encoding="utf-8"))
        self.assertEqual(initial["status"], "partial")
        self.assertEqual(initial["payload"]["resources"][0]["result"], "pending")
        recovery = sbtd_upgrade.plan_recovery(plan, initial)
        self.assertEqual(recovery["payload"]["status"], "planned")
        self.assertEqual(len(recovery["payload"]["steps"]), 1)
        self.assertEqual(recovery["payload"]["steps"][0]["expected_current"], snapshot(target))
        self.assertTrue(list((vault / "intents").glob("intent-*.json")))
        mtime = (target / "SKILL.md").stat().st_mtime_ns
        retry = self._apply_local(plan)
        self.assertEqual(retry["payload"]["status"], "complete")
        row = self._receipt_rows(retry)[f"skill@{target}"]
        self.assertEqual(row["result"], "reconciled")
        self.assertIsNotNone(row["backup_ref"])
        self.assertEqual(
            (Path(row["backup_ref"]["path"]) / "SKILL.md").read_text(
                encoding="utf-8"
            ),
            "old\n",
        )
        self.assertEqual((target / "SKILL.md").stat().st_mtime_ns, mtime)

    def test_partial_failure_records_measured_state_then_retry_completes(self):
        skills = self._skills_root()
        target_a = skills / "skill-a"
        target_b = skills / "skill-b"
        for target, text in ((target_a, "old a\n"), (target_b, "old b\n")):
            target.mkdir()
            (target / "SKILL.md").write_text(text, encoding="utf-8")
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [
                    self._skill_fixture(target_a, "payload/skill-a"),
                    self._skill_fixture(target_b, "payload/skill-b"),
                ],
            },
            files={
                "payload/skill-a/SKILL.md": "new a\n",
                "payload/skill-b/SKILL.md": "new b\n",
            },
        )
        self._register(package)
        vault = self._vault()
        scope = {
            "schema_version": 1,
            "skills_roots": [str(skills)],
            "decisions": {str(target_a): "replace", str(target_b): "replace"},
        }
        plan = self._plan(scope, vault, package)
        real_install = sbtd_upgrade.install_reference

        def failing_install(source_ref, target, expected, *, scope, backup_ref=None):
            if Path(target).name == "skill-b":
                raise ContractError(
                    "write-failed", "injected write failure", exit_code=3
                )
            return real_install(
                source_ref, target, expected, scope=scope, backup_ref=backup_ref
            )

        with mock.patch.object(sbtd_upgrade, "install_reference", failing_install):
            receipt = self._apply_local(plan)
        self.assertEqual(receipt["payload"]["status"], "partial")
        rows = self._receipt_rows(receipt)
        self.assertEqual(rows[f"skill@{target_a}"]["result"], "succeeded")
        self.assertEqual(rows[f"skill@{target_b}"]["result"], "failed")
        self.assertEqual(rows[f"skill@{target_b}"]["reason"], "write-failed")
        self.assertEqual(
            rows[f"skill@{target_b}"]["after"],
            rows[f"skill@{target_b}"]["before"],
        )
        self.assertEqual(receipt["payload"]["failure"]["resource_id"], f"skill@{target_b}")
        self.assertEqual(
            (target_b / "SKILL.md").read_text(encoding="utf-8"), "old b\n"
        )
        # Both originals were taken before the first write and survive.
        self.assertIsNotNone(rows[f"skill@{target_b}"]["backup_ref"])
        backup_b = Path(rows[f"skill@{target_b}"]["backup_ref"]["path"])
        self.assertEqual(
            (backup_b / "SKILL.md").read_text(encoding="utf-8"), "old b\n"
        )
        retry = self._apply_local(plan, receipt=receipt)
        self.assertEqual(retry["payload"]["status"], "complete")
        retry_rows = self._receipt_rows(retry)
        self.assertEqual(retry_rows[f"skill@{target_a}"]["result"], "skipped-complete")
        self.assertEqual(retry_rows[f"skill@{target_b}"]["result"], "succeeded")
        self.assertEqual(
            (target_b / "SKILL.md").read_text(encoding="utf-8"), "new b\n"
        )
        self.assertEqual(
            (backup_b / "SKILL.md").read_text(encoding="utf-8"), "old b\n"
        )

    # -- keep / preserve and verification ------------------------------------

    def test_keep_and_preserve_semantics_and_verify_exceptions(self):
        skills = self._skills_root()
        current = skills / "skill-a"
        current.mkdir()
        (current / "SKILL.md").write_bytes(b"same\n")
        preserved = skills / "skill-b"
        preserved.mkdir()
        (preserved / "SKILL.md").write_text("user custom\n", encoding="utf-8")
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [
                    self._skill_fixture(current, "payload/skill-a"),
                    self._skill_fixture(preserved, "payload/skill-b"),
                ],
            },
            files={
                "payload/skill-a/SKILL.md": "same\n",
                "payload/skill-b/SKILL.md": "baseline\n",
            },
        )
        self._register(package)
        vault = self._vault()
        scope = {
            "schema_version": 1,
            "skills_roots": [str(skills)],
            "decisions": {str(preserved): "preserve"},
        }
        plan = self._plan(scope, vault, package)
        rows = {row["id"]: row for row in plan["payload"]["resources"]}
        self.assertEqual(rows[f"skill@{current}"]["decision"], "keep")
        self.assertEqual(rows[f"skill@{preserved}"]["decision"], "preserve")
        mtime = (current / "SKILL.md").stat().st_mtime_ns
        receipt = self._apply_local(plan)
        self.assertEqual(receipt["payload"]["status"], "complete")
        results = self._receipt_rows(receipt)
        self.assertEqual(results[f"skill@{current}"]["result"], "kept")
        self.assertEqual(results[f"skill@{preserved}"]["result"], "preserved")
        self.assertEqual((current / "SKILL.md").stat().st_mtime_ns, mtime)
        self.assertEqual(
            (preserved / "SKILL.md").read_text(encoding="utf-8"), "user custom\n"
        )
        verification = sbtd_upgrade.verify_upgrade(plan, receipt=receipt)
        self.assertEqual(verification["payload"]["status"], "exceptions")
        self.assertIn(f"skill@{preserved}", verification["payload"]["exceptions"])

    def test_verify_reports_missing_drift_and_receipt_divergence(self):
        skills = self._skills_root()
        target = skills / "skill-a"
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [self._skill_fixture(target, "payload/skill-a")],
            },
            files={"payload/skill-a/SKILL.md": "baseline\n"},
        )
        self._register(package)
        vault = self._vault()
        scope = {"schema_version": 1, "skills_roots": [str(skills)]}
        plan = self._plan(scope, vault, package)
        early = sbtd_upgrade.verify_upgrade(plan)
        self.assertEqual(early["payload"]["status"], "drift")
        self.assertEqual(early["payload"]["resources"][0]["result"], "missing")
        receipt = self._apply_local(plan)
        target.mkdir(exist_ok=True)
        (target / "SKILL.md").write_text("tampered\n", encoding="utf-8")
        late = sbtd_upgrade.verify_upgrade(plan, receipt=receipt)
        self.assertEqual(late["payload"]["status"], "drift")
        self.assertEqual(late["payload"]["resources"][0]["result"], "drift")
        self.assertEqual(
            late["payload"]["resources"][0]["reason"], "receipt-outcome-diverged"
        )

    # -- host resources --------------------------------------------------------

    def test_host_profile_lifecycle_and_semantic_verify(self):
        home = self.base / "home"
        home.mkdir()
        profile = home / ".bashrc"
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [],
                "host_resources": [
                    {
                        "id": f"shell@{profile}",
                        "kind": "shell",
                        "content": "managed/profile.sh",
                        "target": str(profile),
                        "shell": "bash",
                    }
                ],
            },
            files={"managed/profile.sh": "# sbtd-managed-bin\nexport PATH=\"$HOME/bin:$PATH\"\n"},
        )
        # The fixture inventory requires at least one skill resource; add a
        # current no-op skill so the combined set is valid.
        skills = self._skills_root()
        current = skills / "skill-a"
        current.mkdir()
        (current / "SKILL.md").write_bytes(b"same\n")
        (package / "payload/skill-a").mkdir(parents=True)
        (package / "payload/skill-a/SKILL.md").write_bytes(b"same\n")
        fixture = json.loads((package / "upgrade_fixture.json").read_text(encoding="utf-8"))
        fixture["resources"] = [self._skill_fixture(current, "payload/skill-a")]
        (package / "upgrade_fixture.json").write_text(json.dumps(fixture), encoding="utf-8")
        self._register(package)
        vault = self._vault()
        scope = {
            "schema_version": 1,
            "skills_roots": [str(skills)],
            "shell_profiles": [
                {"path": str(profile), "shell": "bash", "bin": str(self.base / "bin")}
            ],
        }
        plan = self._plan(scope, vault, package)
        rows = {row["id"]: row for row in plan["payload"]["resources"]}
        self.assertEqual(rows[f"shell@{profile}"]["decision"], "install")
        receipt = self._apply_local(plan)
        self.assertEqual(receipt["payload"]["status"], "complete")
        managed = (package / "managed/profile.sh").read_bytes()
        self.assertEqual(profile.read_bytes(), managed)
        verification = sbtd_upgrade.verify_upgrade(plan, receipt=receipt)
        self.assertEqual(verification["payload"]["status"], "aligned")
        self.assertEqual(verification["payload"]["hosts"]["probe"], False)
        (profile_row,) = verification["payload"]["hosts"]["shell_profiles"]
        self.assertEqual(profile_row["disk"]["status"], "aligned")
        self.assertEqual(profile_row["host"], "unverified")
        # Unrelated user additions keep managed alignment; ownership loss drifts.
        with profile.open("ab") as handle:
            handle.write(b"# user additions\n")
        still = sbtd_upgrade.verify_upgrade(plan, receipt=receipt)
        self.assertEqual(still["payload"]["hosts"]["shell_profiles"][0]["disk"]["status"], "aligned")
        self.assertEqual(still["payload"]["status"], "aligned")
        profile.write_text("# user-owned profile without the managed block\n", encoding="utf-8")
        drifted = sbtd_upgrade.verify_upgrade(plan, receipt=receipt)
        self.assertEqual(drifted["payload"]["status"], "drift")
        probed = sbtd_upgrade.verify_upgrade(plan, probe=True)
        self.assertEqual(probed["payload"]["probe"], True)
        self.assertEqual(
            probed["payload"]["hosts"]["shell_profiles"][0]["disk"]["status"],
            "drifted",
        )

    def test_host_resource_retries_after_original_source_is_removed(self):
        home = self.base / "home"
        home.mkdir()
        profile = home / ".bashrc"
        skills = self._skills_root()
        current = skills / "skill-a"
        current.mkdir()
        (current / "SKILL.md").write_bytes(b"same\n")
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [self._skill_fixture(current, "payload/skill-a")],
                "host_resources": [{
                    "id": f"shell@{profile}", "kind": "shell",
                    "content": "managed/profile.sh", "target": str(profile),
                    "shell": "bash",
                }],
            },
            files={
                "payload/skill-a/SKILL.md": "same\n",
                "managed/profile.sh": "# sbtd-managed-bin\n",
            },
        )
        self._register(package)
        vault = self._vault()
        scope = {
            "schema_version": 1, "skills_roots": [str(skills)],
            "shell_profiles": [{"path": str(profile), "shell": "bash", "bin": str(self.base / "bin")}],
        }
        plan = self._plan(scope, vault, package)
        receipt = sbtd_upgrade.apply_upgrade(plan, confirmed=plan["plan_id"])
        installed = self.base / "installed-onboard"
        shutil.copytree(package, installed)
        self._register(installed)
        shutil.rmtree(package)
        retry = sbtd_upgrade.apply_upgrade(plan, confirmed=plan["plan_id"], receipt=receipt)
        rows = self._receipt_rows(retry)
        self.assertEqual(rows[f"shell@{profile}"]["result"], "skipped-complete")
        self.assertEqual(profile.read_bytes(), b"# sbtd-managed-bin\n")


    def test_host_preserve_downgrades_to_exception_without_leaking_config(self):
        home = self.base / "home"
        home.mkdir()
        config = home / "config.json"
        config.write_text(
            json.dumps({"mcpServers": {"other": {"command": "secret-SECRET-cmd"}}}),
            encoding="utf-8",
        )
        skills = self._skills_root()
        current = skills / "skill-a"
        current.mkdir()
        (current / "SKILL.md").write_bytes(b"same\n")
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [self._skill_fixture(current, "payload/skill-a")],
                "host_resources": [
                    {
                        "id": f"mcp@{config}",
                        "kind": "mcp",
                        "content": "managed/mcp.json",
                        "target": str(config),
                        "host": "fixture-host",
                    }
                ],
            },
            files={
                "payload/skill-a/SKILL.md": "same\n",
                "managed/mcp.json": json.dumps({"mcpServers": {"graft": {"command": "run"}}}),
            },
        )
        self._register(package)
        vault = self._vault()
        scope = {
            "schema_version": 1,
            "skills_roots": [str(skills)],
            "hosts": [{
                "id": "fixture-host", "platform": "codex",
                "config_home": str(home), "config": str(config),
                "skills_roots": [str(skills)], "project_roots": [],
                "runtime": {"python": "/usr/bin/python3", "node": "/usr/bin/node", "cli": "/usr/bin/graft"},
            }],
            "decisions": {str(config): "preserve"},
        }
        plan = self._plan(scope, vault, package)
        rows = {row["id"]: row for row in plan["payload"]["resources"]}
        self.assertEqual(rows[f"mcp@{config}"]["decision"], "preserve")
        self.assertIsNone(rows[f"mcp@{config}"]["desired"])
        receipt = self._apply_local(plan)
        self.assertEqual(
            self._receipt_rows(receipt)[f"mcp@{config}"]["result"], "preserved"
        )
        verification = sbtd_upgrade.verify_upgrade(plan, receipt=receipt)
        self.assertEqual(verification["payload"]["status"], "exceptions")
        self.assertIn("fixture-host", verification["payload"]["exceptions"])
        self.assertNotIn("SECRET", json.dumps(verification))
        self.assertIn("secret-SECRET-cmd", config.read_text(encoding="utf-8"))

    # -- recovery --------------------------------------------------------------

    def _recovery_batch(self):
        skills = self._skills_root()
        replaced = skills / "skill-a"
        replaced.mkdir()
        (replaced / "SKILL.md").write_text("original bytes\n", encoding="utf-8")
        agents_file = self.base / "agents-home" / "AGENTS.md"
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [
                    self._skill_fixture(replaced, "payload/skill-a"),
                    {
                        "id": f"agents@{agents_file}",
                        "kind": "agents",
                        "source": "payload/AGENTS.global.md",
                        "target": str(agents_file),
                    },
                ],
            },
            files={
                "payload/skill-a/SKILL.md": "new bytes\n",
                "payload/AGENTS.global.md": "# global agents\n",
            },
        )
        self._register(package)
        vault = self._vault()
        scope = {
            "schema_version": 1,
            "skills_roots": [str(skills)],
            "agents_targets": [str(agents_file)],
            "decisions": {str(replaced): "replace"},
        }
        plan = self._plan(scope, vault, package)
        receipt = self._apply_local(plan)
        self.assertEqual(receipt["payload"]["status"], "complete")
        return plan, receipt, replaced, agents_file, vault

    def test_recovery_restores_originals_and_removes_installed(self):
        plan, receipt, replaced, agents_file, vault = self._recovery_batch()
        self.assertEqual(
            (replaced / "SKILL.md").read_text(encoding="utf-8"), "new bytes\n"
        )
        self.assertTrue(agents_file.is_file())
        recovery_plan = sbtd_upgrade.plan_recovery(plan, receipt)
        self.assertEqual(recovery_plan["payload"]["status"], "planned")
        steps = {
            step["resource_id"]: step for step in recovery_plan["payload"]["steps"]
        }
        self.assertEqual(steps[f"skill@{replaced}"]["action"], "restore")
        self.assertEqual(steps[f"agents@{agents_file}"]["action"], "remove")
        self.assertEqual(
            steps[f"agents@{agents_file}"]["created_parents"],
            [str(agents_file.parent)],
        )
        recovery_receipt = self._apply_recovery_local(recovery_plan)
        self.assertEqual(recovery_receipt["payload"]["status"], "complete")
        self.assertEqual(
            (replaced / "SKILL.md").read_text(encoding="utf-8"),
            "original bytes\n",
        )
        self.assertFalse(agents_file.exists())
        # Conservative rollback removes only the measured resource; an empty
        # parent created during apply is intentionally retained.
        self.assertTrue(agents_file.parent.is_dir())
        self.assertEqual(list(agents_file.parent.iterdir()), [])
        # Original backups are never destroyed by recovery.
        originals = list((vault / "originals").glob("**/SKILL.md"))
        self.assertTrue(originals)
        self.assertEqual(
            originals[0].read_text(encoding="utf-8"), "original bytes\n"
        )
        self.assertTrue(list(vault.glob("upgrade-recovery-receipt-*.json")))

    def test_recovery_refuses_live_drift(self):
        plan, receipt, replaced, agents_file, _vault = self._recovery_batch()
        with agents_file.open("a", encoding="utf-8") as handle:
            handle.write("user addition\n")
        recovery_plan = sbtd_upgrade.plan_recovery(plan, receipt)
        self.assertEqual(recovery_plan["payload"]["status"], "blocked")
        steps = {
            step["resource_id"]: step for step in recovery_plan["payload"]["steps"]
        }
        self.assertEqual(steps[f"agents@{agents_file}"]["status"], "blocked")
        self.assertEqual(steps[f"agents@{agents_file}"]["reason"], "live-drift")
        self.assertEqual(steps[f"skill@{replaced}"]["status"], "actionable")
        with self.assertRaises(ContractError) as caught:
            self._apply_recovery_local(recovery_plan)
        self.assertEqual(caught.exception.code, "blocked-recovery-step")
        self.assertIn("user addition", agents_file.read_text(encoding="utf-8"))

    def test_recovery_requires_separate_confirmation(self):
        plan, receipt, _replaced, _agents, _vault = self._recovery_batch()
        recovery_plan = sbtd_upgrade.plan_recovery(plan, receipt)
        with self.assertRaises(ContractError) as missing:
            sbtd_upgrade._apply_recovery_local(
                recovery_plan, confirmed=None, receipt=None, package_root=None
            )
        self.assertEqual(missing.exception.code, "confirmation-required")
        with self.assertRaises(ContractError) as wrong:
            sbtd_upgrade._apply_recovery_local(
                recovery_plan, confirmed="1" * 64, receipt=None, package_root=None
            )
        self.assertEqual(wrong.exception.code, "confirmation-mismatch")

    def test_recovery_retry_is_idempotent(self):
        plan, receipt, replaced, agents_file, _vault = self._recovery_batch()
        recovery_plan = sbtd_upgrade.plan_recovery(plan, receipt)
        first = self._apply_recovery_local(recovery_plan)
        self.assertEqual(first["payload"]["status"], "complete")
        second = self._apply_recovery_local(recovery_plan, receipt=first)
        self.assertEqual(second["payload"]["status"], "complete")
        self.assertEqual(second["payload"]["sequence"], 1)
        self.assertEqual(
            second["payload"]["previous_receipt_id"],
            first["recovery_receipt_id"],
        )
        for row in second["payload"]["steps"]:
            self.assertEqual(row["result"], "skipped-complete")
        self.assertEqual(
            (replaced / "SKILL.md").read_text(encoding="utf-8"),
            "original bytes\n",
        )
        self.assertFalse(agents_file.exists())

    # -- staged isolated execution (self-upgrade) ------------------------------

    def test_public_apply_uses_staged_isolated_executor(self):
        skills = self._skills_root()
        target = skills / "skill-a"
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [self._skill_fixture(target, "payload/skill-a")],
            },
            files={"payload/skill-a/SKILL.md": "isolated\n"},
        )
        self._register(package)
        vault = self._vault()
        scope = {"schema_version": 1, "skills_roots": [str(skills)]}
        plan = self._plan(scope, vault, package)
        with mock.patch.object(sbtd_upgrade, "_trusted_package_root", return_value=package):
            receipt = sbtd_upgrade.apply_upgrade(plan, confirmed=plan["plan_id"])
        self.assertEqual(receipt["payload"]["status"], "complete")
        executor = receipt["payload"]["executor"]
        self.assertTrue(executor["isolated"])
        self.assertTrue(str(executor["runner"]).startswith(str(vault / "self")))
        self.assertEqual(
            (target / "SKILL.md").read_text(encoding="utf-8"), "isolated\n"
        )
        self.assertTrue(list(vault.glob("upgrade-receipt-*.json")))

    def test_self_upgrade_replaces_running_package_from_staged_copy(self):
        skills = self._skills_root()
        marker = "# replacement package marker\n"
        package = self._package(
            fixture={"baseline_id": "b1", "resources": []},
            files={},
        )
        # Rebuild fixture with the self-targeting resource now that the
        # package path is known.
        fixture = {
            "baseline_id": "b1",
            "resources": [
                {
                    "id": f"self@{package}",
                    "kind": "skill",
                    "source": "payload/pkg-new",
                    "target": str(package),
                }
            ],
        }
        (package / "upgrade_fixture.json").write_text(
            json.dumps(fixture), encoding="utf-8"
        )
        new_root = package / "payload/pkg-new"
        (new_root / "scripts").mkdir(parents=True)
        (new_root / "scripts/sbtd_upgrade.py").write_text(marker, encoding="utf-8")
        (new_root / "VERSION").write_text("2\n", encoding="utf-8")
        self._register(package)
        vault = self._vault()
        scope = {
            "schema_version": 1,
            "skills_roots": [str(skills)],
            "decisions": {str(package): "replace"},
        }
        plan = self._plan(scope, vault, package)
        (resource,) = plan["payload"]["resources"]
        self.assertEqual(resource["classification"], "unknown-drift")
        self.assertEqual(resource["decision"], "replace")
        with mock.patch.object(sbtd_upgrade, "_trusted_package_root", return_value=package):
            receipt = sbtd_upgrade.apply_upgrade(plan, confirmed=plan["plan_id"])
        self.assertEqual(receipt["payload"]["status"], "complete")
        self.assertTrue(receipt["payload"]["executor"]["isolated"])
        self.assertEqual(
            (package / "scripts/sbtd_upgrade.py").read_text(encoding="utf-8"),
            marker,
        )
        self.assertEqual((package / "VERSION").read_text(encoding="utf-8"), "2\n")
        # The complete original package survives in the private backups.
        row = self._receipt_rows(receipt)[f"self@{package}"]
        backup = Path(row["backup_ref"]["path"])
        restored_runner = backup / "scripts/sbtd_upgrade.py"
        self.assertTrue(restored_runner.is_file())
        self.assertIn(
            "Onboard upgrade alignment engine",
            restored_runner.read_text(encoding="utf-8"),
        )
        with (
            mock.patch.object(sbtd_upgrade, "_trusted_package_root", return_value=package),
            self.assertRaises(ContractError) as changed_source,
        ):
            sbtd_upgrade.apply_upgrade(plan, confirmed=plan["plan_id"], receipt=receipt)
        self.assertEqual(changed_source.exception.code, "source-stale")

    # -- documents -------------------------------------------------------------

    def test_save_plan_persists_immutable_document(self):
        skills = self._skills_root()
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [
                    self._skill_fixture(skills / "skill-a", "payload/skill-a")
                ],
            },
            files={"payload/skill-a/SKILL.md": "x\n"},
        )
        self._register(package)
        vault = self._vault()
        scope = {"schema_version": 1, "skills_roots": [str(skills)]}
        plan = self._plan(scope, vault, package)
        destination = vault / "saved-plan.json"
        reference = sbtd_upgrade.save_plan(plan, destination)
        self.assertEqual(reference["state"]["type"], "file")
        loaded = json.loads(destination.read_text(encoding="utf-8"))
        self.assertEqual(loaded["plan_id"], plan["plan_id"])
        with self.assertRaises(ContractError):
            sbtd_upgrade.save_plan(plan, destination)

    def test_schema_file_validates_engine_documents(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed in this interpreter")
        schema = json.loads(
            (ROOT / "sbtd-workflow-onboard" / "upgrade.schema.json").read_text(
                encoding="utf-8"
            )
        )
        plan, receipt, _replaced, _agents_file, _vault = self._recovery_batch()
        jsonschema.validate(plan, schema)
        jsonschema.validate(receipt, schema)
        verification = sbtd_upgrade.verify_upgrade(plan, receipt=receipt)
        jsonschema.validate(verification, schema)
        recovery_plan = sbtd_upgrade.plan_recovery(plan, receipt)
        jsonschema.validate(recovery_plan, schema)
        recovery_receipt = self._apply_recovery_local(recovery_plan)
        jsonschema.validate(recovery_receipt, schema)
        jsonschema.validate(plan["payload"]["scope"], schema)

    def test_public_apply_rejects_untrusted_executor_source(self):
        plan, _receipt, _skill, _agents, vault = self._recovery_batch()
        forged = copy.deepcopy(plan)
        forged["payload"]["baseline"]["source"]["path"] = str(self.base / "attacker-package")
        forged["plan_id"] = sbtd_upgrade._digest(forged["payload"])
        with self.assertRaises(ContractError):
            sbtd_upgrade.apply_upgrade(forged, confirmed=forged["plan_id"])
        self.assertFalse((vault / "self").exists())

    def test_tampered_stage_never_executes(self):
        plan, _receipt, _skill, _agents, vault = self._recovery_batch()
        baseline = plan["payload"]["baseline"]
        stage = sbtd_upgrade._stage_self_package(baseline, vault)
        runner = Path(stage["runner"])
        runner.write_text("raise RuntimeError('untrusted')\n", encoding="utf-8")
        with self.assertRaises(ContractError) as caught:
            sbtd_upgrade._stage_self_package(baseline, vault)
        self.assertEqual(caught.exception.code, "self-stage-conflict")

    def test_rehashed_recovery_cannot_remove_an_unrelated_file(self):
        plan, receipt, _skill, agents, _vault = self._recovery_batch()
        unrelated = agents.parent / "UNRELATED.txt"
        unrelated.write_text("user-owned\n", encoding="utf-8")
        recovery = sbtd_upgrade.plan_recovery(plan, receipt)
        forged = copy.deepcopy(recovery)
        removal = next(step for step in forged["payload"]["steps"] if step["action"] == "remove")
        removal["target"] = str(unrelated)
        removal["expected_current"] = snapshot(unrelated)
        removal["expected_mechanical"] = snapshot(unrelated)
        forged["recovery_id"] = sbtd_upgrade._digest(forged["payload"])
        with self.assertRaises(ContractError) as caught:
            self._apply_recovery_local(forged)
        self.assertEqual(caught.exception.code, "plan-stale")
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "user-owned\n")
        self.assertTrue(agents.exists())

    def test_failed_but_changed_resource_is_recoverable(self):
        skills = self._skills_root()
        target = skills / "skill-a"
        target.mkdir()
        (target / "SKILL.md").write_text("original\n", encoding="utf-8")
        package = self._package(
            fixture={"baseline_id": "b1", "resources": [
                self._skill_fixture(target, "payload/skill-a"),
            ]},
            files={"payload/skill-a/SKILL.md": "replacement\n"},
        )
        self._register(package)
        vault = self._vault()
        plan = self._plan({
            "schema_version": 1, "skills_roots": [str(skills)],
            "decisions": {str(target): "replace"},
        }, vault, package)
        real_install = sbtd_upgrade.install_reference

        def fail_after_commit(*args, **kwargs):
            real_install(*args, **kwargs)
            raise ContractError("write-failed", "injected post-commit failure", exit_code=3)

        with mock.patch.object(sbtd_upgrade, "install_reference", fail_after_commit):
            receipt = self._apply_local(plan)
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), "replacement\n")
        recovery = sbtd_upgrade.plan_recovery(plan, receipt)
        self.assertEqual(len(recovery["payload"]["steps"]), 1)
        recovered = self._apply_recovery_local(recovery)
        self.assertEqual(recovered["status"], "complete")
        self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), "original\n")

    def test_recovery_resumes_after_remove_before_restore_copy(self):
        plan, receipt, target, agents, _vault = self._recovery_batch()
        recovery = sbtd_upgrade.plan_recovery(plan, receipt)
        with mock.patch.object(
            sbtd_upgrade, "install_reference",
            side_effect=ContractError("write-failed", "injected restore interruption", exit_code=3),
        ):
            failed = self._apply_recovery_local(recovery)
        self.assertEqual(failed["status"], "failed")
        self.assertFalse(target.exists())
        retried = self._apply_recovery_local(recovery, receipt=failed)
        self.assertEqual(retried["status"], "complete")
        self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), "original bytes\n")
        self.assertFalse(agents.exists())

    def test_joint_inherited_provider_write_is_refused_before_mutations(self):
        skills = self._skills_root()
        provider = skills / "provider"
        consumer = skills / "consumer"
        dependency = provider / "SKILL.md"
        package = self._package(
            fixture={"baseline_id": "b1", "resources": [
                self._skill_fixture(provider, "payload/provider"),
                self._skill_fixture(consumer, "payload/consumer", details={
                    "effective_inputs": [{"path": str(dependency), "state": snapshot(dependency)}],
                }),
            ]},
            files={"payload/provider/SKILL.md": "provider\n", "payload/consumer/SKILL.md": "consumer\n"},
        )
        self._register(package)
        vault = self._vault()
        plan = self._plan({"schema_version": 1, "skills_roots": [str(skills)]}, vault, package)
        with self.assertRaises(ContractError) as caught:
            self._apply_local(plan)
        self.assertEqual(caught.exception.code, "inherited-dependency-conflict")
        self.assertFalse(provider.exists())
        self.assertFalse(consumer.exists())
        self.assertFalse((vault / "originals").exists())

    def test_recovery_directly_uses_interrupted_intent(self):
        skills = self._skills_root()
        target = skills / "skill-a"
        target.mkdir()
        (target / "SKILL.md").write_text("original\n", encoding="utf-8")
        package = self._package(
            fixture={"baseline_id": "b1", "resources": [self._skill_fixture(target, "payload/skill-a")]},
            files={"payload/skill-a/SKILL.md": "replacement\n"},
        )
        self._register(package)
        vault = self._vault()
        plan = self._plan({
            "schema_version": 1, "skills_roots": [str(skills)],
            "decisions": {str(target): "replace"},
        }, vault, package)
        real_save = sbtd_upgrade.save_document

        def fail_after_write(path, document, *, private_root):
            if Path(path).name.startswith("upgrade-receipt-") and any(
                row["result"] == "succeeded" for row in document["payload"]["resources"]
            ):
                raise ContractError("write-failed", "injected receipt interruption", exit_code=3)
            return real_save(path, document, private_root=private_root)

        with mock.patch.object(sbtd_upgrade, "save_document", fail_after_write), self.assertRaises(ContractError):
            self._apply_local(plan)
        initial = json.loads(next(vault.glob("upgrade-receipt-*.json")).read_text(encoding="utf-8"))
        recovery = sbtd_upgrade.plan_recovery(plan, initial)
        recovered = self._apply_recovery_local(recovery)
        self.assertEqual(recovered["status"], "complete")
        self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), "original\n")
        retry = self._apply_recovery_local(recovery, receipt=recovered)
        self.assertEqual(retry["status"], "complete")
        self.assertEqual(retry["payload"]["steps"][0]["result"], "skipped-complete")

    def test_late_user_drift_is_not_attributed_as_an_engine_write(self):
        skills = self._skills_root()
        target = skills / "skill-a"
        target.mkdir()
        (target / "SKILL.md").write_text("original\n", encoding="utf-8")
        package = self._package(
            fixture={"baseline_id": "b1", "resources": [self._skill_fixture(target, "payload/skill-a")]},
            files={"payload/skill-a/SKILL.md": "replacement\n"},
        )
        self._register(package)
        vault = self._vault()
        plan = self._plan({
            "schema_version": 1, "skills_roots": [str(skills)],
            "decisions": {str(target): "replace"},
        }, vault, package)

        def concurrent_edit(*args, **kwargs):
            (target / "SKILL.md").write_text("late user edit\n", encoding="utf-8")
            raise ContractError("state-conflict", "injected pre-write drift")

        with mock.patch.object(sbtd_upgrade, "_write_resource", concurrent_edit):
            failed = self._apply_local(plan)
        row = self._receipt_rows(failed)[f"skill@{target}"]
        self.assertFalse(row["mutated"])
        recovery = sbtd_upgrade.plan_recovery(plan, failed)
        self.assertEqual(recovery["payload"]["steps"], [])
        self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), "late user edit\n")

    def test_unknown_partial_outcome_preserves_user_additions(self):
        skills = self._skills_root()
        target = skills / "skill-a"
        target.mkdir()
        (target / "SKILL.md").write_text("original\n", encoding="utf-8")
        package = self._package(
            fixture={"baseline_id": "b1", "resources": [self._skill_fixture(target, "payload/skill-a")]},
            files={"payload/skill-a/SKILL.md": "replacement\n"},
        )
        self._register(package)
        vault = self._vault()
        plan = self._plan({
            "schema_version": 1, "skills_roots": [str(skills)],
            "decisions": {str(target): "replace"},
        }, vault, package)
        real_install = sbtd_upgrade.install_reference

        def concurrent_post_commit(*args, **kwargs):
            real_install(*args, **kwargs)
            (target / "user-created.txt").write_text("do not lose\n", encoding="utf-8")
            raise ContractError("write-failed", "injected uncertain outcome", exit_code=3)

        with mock.patch.object(sbtd_upgrade, "install_reference", concurrent_post_commit):
            failed = self._apply_local(plan)
        row = self._receipt_rows(failed)[f"skill@{target}"]
        self.assertIsNone(row["mutated"])
        recovery = sbtd_upgrade.plan_recovery(plan, failed)
        self.assertEqual(recovery["payload"]["status"], "blocked")
        self.assertEqual(recovery["payload"]["steps"][0]["reason"], "unattributed-outcome")
        with self.assertRaises(ContractError):
            self._apply_recovery_local(recovery)
        self.assertEqual((target / "user-created.txt").read_text(encoding="utf-8"), "do not lose\n")
        forged = copy.deepcopy(recovery)
        forged["payload"]["status"] = "planned"
        for step in forged["payload"]["steps"]:
            step["status"] = "actionable"
        forged["recovery_id"] = sbtd_upgrade._digest(forged["payload"])
        with self.assertRaises(ContractError) as denied:
            self._apply_recovery_local(forged)
        self.assertEqual(denied.exception.code, "plan-stale")
        self.assertEqual((target / "user-created.txt").read_text(encoding="utf-8"), "do not lose\n")


    def test_recovery_rejects_a_separately_changed_trusted_package(self):
        plan, receipt, target, _agents, _vault = self._recovery_batch()
        source = Path(plan["payload"]["baseline"]["source"]["path"])
        (source / "payload/skill-a/SKILL.md").write_text("different package generation\n", encoding="utf-8")
        with self.assertRaises(ContractError) as stale:
            sbtd_upgrade.plan_recovery(plan, receipt)
        self.assertEqual(stale.exception.code, "source-stale")
        self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), "new bytes\n")

    def test_equivalent_installed_package_retries_and_recovers_relocated_plan(self):
        plan, receipt, replaced, agents_file, _vault = self._recovery_batch()
        original = Path(plan["payload"]["baseline"]["source"]["path"])
        installed = self.base / "installed-onboard"
        shutil.copytree(original, installed)
        self._register(installed)
        shutil.rmtree(original)
        self.assertFalse(original.exists())
        retry = sbtd_upgrade.apply_upgrade(
            plan, confirmed=plan["plan_id"], receipt=receipt
        )
        self.assertEqual(retry["payload"]["status"], "complete")
        rows = self._receipt_rows(retry)
        self.assertEqual(rows[f"skill@{replaced}"]["result"], "skipped-complete")
        self.assertEqual(rows[f"agents@{agents_file}"]["result"], "skipped-complete")
        recovery = sbtd_upgrade.plan_recovery(plan, retry)
        self.assertEqual(recovery["payload"]["status"], "planned")
        recovered = sbtd_upgrade.apply_recovery(
            recovery, confirmed=recovery["recovery_id"]
        )
        self.assertEqual(recovered["payload"]["status"], "complete")
        self.assertEqual(
            (replaced / "SKILL.md").read_text(encoding="utf-8"),
            "original bytes\n",
        )
        self.assertFalse(agents_file.exists())
        self.assertTrue(agents_file.parent.is_dir())


    def test_generated_cache_retry_skips_without_adopting_cache_ownership(self):
        skills = self._skills_root()
        target = skills / "skill-a"
        package = self._package(
            fixture={"baseline_id": "b1", "resources": [self._skill_fixture(target, "payload/skill-a")]},
            files={"payload/skill-a/SKILL.md": "baseline\n"},
        )
        self._register(package)
        real_inventory = self._real_module("sbtd_upgrade_inventory")
        inventory = sys.modules["sbtd_upgrade_inventory"]
        inventory.payload_directory_state = real_inventory.payload_directory_state
        inventory.payload_file_state = real_inventory.payload_file_state
        vault = self._vault()
        plan = self._plan({"schema_version": 1, "skills_roots": [str(skills)]}, vault, package)
        first = self._apply_local(plan)
        before = self._receipt_rows(first)[f"skill@{target}"]["mechanical_after"]
        cache = target / "__pycache__"
        cache.mkdir()
        (cache / "generated.pyc").write_bytes(b"generated cache")
        retried = self._apply_local(plan, receipt=first)
        row = self._receipt_rows(retried)[f"skill@{target}"]
        self.assertEqual(row["result"], "skipped-complete")
        self.assertEqual(row["mechanical_after"], before)
        self.assertNotEqual(snapshot(target), before)
        recovery = sbtd_upgrade.plan_recovery(plan, retried)
        self.assertEqual(recovery["payload"]["status"], "blocked")
        self.assertEqual(recovery["payload"]["steps"][0]["reason"], "live-drift")
        self.assertTrue((cache / "generated.pyc").exists())

    def test_concurrently_created_parent_is_never_retired(self):
        parent = self.base / "concurrent-home"
        target = parent / "AGENTS.md"
        package = self._package(
            fixture={"baseline_id": "b1", "resources": [{
                "id": f"agents@{target}", "kind": "agents", "source": "payload/AGENTS.md",
                "target": str(target),
            }]},
            files={"payload/AGENTS.md": "managed\n"},
        )
        self._register(package)
        vault = self._vault()
        plan = self._plan({"schema_version": 1, "agents_targets": [str(target)]}, vault, package)
        real_create = sbtd_upgrade._ensure_parent_directories

        def user_creates_first(path):
            parent.mkdir()
            return real_create(path)

        with mock.patch.object(sbtd_upgrade, "_ensure_parent_directories", user_creates_first):
            receipt = self._apply_local(plan)
        self.assertEqual(self._receipt_rows(receipt)[f"agents@{target}"]["created_parents"], [])
        recovery = sbtd_upgrade.plan_recovery(plan, receipt)
        self._apply_recovery_local(recovery)
        self.assertFalse(target.exists())
        self.assertTrue(parent.is_dir())

    def test_mcp_missing_or_stale_preserved_onboard_blocks_the_whole_write_set(self):
        for stale in (False, True):
            with self.subTest(stale=stale):
                skills = self._skills_root(f"skills-{stale}")
                onboard = skills / "sbtd-workflow-onboard"
                other = skills / "other"
                home = self.base / f"home-{stale}"
                home.mkdir()
                config = home / "config.json"
                if stale:
                    onboard.mkdir()
                    (onboard / "SKILL.md").write_text("customized\n", encoding="utf-8")
                package = self._package(
                    name=f"pkg-{stale}",
                    fixture={"baseline_id": "b1", "resources": [
                        self._skill_fixture(onboard, "payload/onboard"),
                        self._skill_fixture(other, "payload/other"),
                    ], "host_resources": [{
                        "id": f"mcp@{config}", "kind": "mcp", "host": "codex",
                        "target": str(config), "content": "managed/config.json",
                    }]},
                    files={
                        "payload/onboard/SKILL.md": "managed onboard\n",
                        "payload/onboard/scripts/sbtd_graft_entry.py": "entry\n",
                        "payload/other/SKILL.md": "other\n",
                        "managed/config.json": '{"managed":true}',
                    },
                )
                self._register(package)
                provider = sys.modules["sbtd_upgrade_hosts"]
                real_build = provider.build_host_resources

                def with_dependency(scope, *, package_root=None, real_build=real_build, package=package, onboard=onboard):
                    rows = real_build(scope, package_root=package_root)
                    for row in rows:
                        source = package / "payload/onboard"
                        row["host"]["onboard_root"] = str(onboard)
                        row["details"]["onboard_payload_digest"] = snapshot(source)["checksum"]
                        row["details"]["launcher"] = {
                            "path": str(onboard / "scripts/sbtd_graft_entry.py"),
                            "state": snapshot(onboard / "scripts/sbtd_graft_entry.py"),
                            "desired": snapshot(source / "scripts/sbtd_graft_entry.py"),
                        }
                    return rows

                scope = {
                    "schema_version": 1, "skills_roots": [str(skills)],
                    "decisions": {str(onboard): "preserve"},
                    "hosts": [{
                        "id": "codex", "platform": "codex", "config_home": str(home),
                        "config": str(config), "onboard_root": str(onboard),
                        "skills_roots": [str(skills)], "project_roots": [],
                        "runtime": {"python": "/usr/bin/python3", "node": "/usr/bin/node", "cli": "/usr/bin/graft"},
                    }],
                }
                vault = self._vault(f"vault-{stale}")
                with mock.patch.object(provider, "build_host_resources", with_dependency):
                    plan = self._plan(scope, vault, package)
                    with self.assertRaises(ContractError) as refused:
                        self._apply_local(plan)
                self.assertEqual(refused.exception.code, "launcher-dependency-conflict")
                self.assertFalse(other.exists())
                self.assertFalse(config.exists())
                self.assertFalse((vault / "originals").exists())

    def test_real_codex_current_config_cannot_be_forged_into_replace(self):
        skills = self._skills_root()
        current = skills / "skill-a"
        current.mkdir()
        (current / "SKILL.md").write_bytes(b"same\n")
        package = self._package(
            fixture={"baseline_id": "b1", "resources": [self._skill_fixture(current, "payload/skill-a")]},
            files={
                "payload/skill-a/SKILL.md": "same\n",
                "SKILL.md": "---\nname: sbtd-workflow-onboard\n---\n",
                "scripts/sbtd_graft_entry.py": (SCRIPTS / "sbtd_graft_entry.py").read_text(encoding="utf-8"),
            },
        )
        self._register(package)
        real_inventory = self._real_module("sbtd_upgrade_inventory")
        sys.modules["sbtd_upgrade_inventory"]._payload_scan = real_inventory._payload_scan
        real_hosts = self._real_module("sbtd_upgrade_hosts")
        sys.modules["sbtd_upgrade_hosts"] = real_hosts
        home = self.base / "codex-home"
        home.mkdir()
        config = home / "config.toml"
        runtime = self.base / "runtime"
        runtime.mkdir()
        for name in ("python", "node", "graft"):
            (runtime / name).write_text("fixture executable\n", encoding="utf-8")
        host = {
            "id": "codex", "platform": "codex", "config_home": str(home),
            "config": str(config), "onboard_root": str(package),
            "skills_roots": [], "project_roots": [],
            "runtime": {"python": str(runtime / "python"), "node": str(runtime / "node"), "cli": str(runtime / "graft")},
        }
        scope = {"schema_version": 1, "skills_roots": [str(skills)], "hosts": [host]}
        resource = real_hosts.build_host_resources(scope, package_root=package)[0]
        config.write_bytes(real_hosts.render_resource(resource, package_root=package))
        before = config.read_bytes()
        vault = self._vault()
        plan = self._plan(scope, vault, package)
        mcp = next(row for row in plan["payload"]["resources"] if row["kind"] == "mcp")
        self.assertEqual(mcp["classification"], "current")
        self.assertEqual(mcp["decision"], "keep")
        forged = self._forge(plan, lambda payload: next(
            row for row in payload["resources"] if row["kind"] == "mcp"
        ).update({"decision": "replace"}))
        with self.assertRaises(ContractError) as denied:
            self._apply_local(forged)
        self.assertEqual(denied.exception.code, "plan-inconsistent")
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual(list(vault.iterdir()), [])

    def test_nullable_host_runtime_scope_and_plan_match_schema(self):
        import jsonschema
        skills = self._skills_root()
        current = skills / "skill-a"
        current.mkdir()
        (current / "SKILL.md").write_bytes(b"same\n")
        home = self.base / "home"
        home.mkdir()
        package = self._package(
            fixture={"baseline_id": "b1", "resources": [self._skill_fixture(current, "payload/skill-a")]},
            files={"payload/skill-a/SKILL.md": "same\n"},
        )
        self._register(package)
        scope = {
            "schema_version": 1, "skills_roots": [str(skills)],
            "hosts": [{
                "id": "codex", "platform": "codex", "config_home": str(home),
                "config": str(home / "config.toml"), "onboard_root": str(package),
                "skills_roots": [], "project_roots": [],
                "runtime": {"python": None, "node": None, "cli": None},
            }],
        }
        schema = json.loads((ROOT / "sbtd-workflow-onboard/upgrade.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(scope, schema)
        plan = self._plan(scope, self._vault(), package)
        jsonschema.validate(plan, schema)

    def test_requested_probe_incomplete_evidence_cannot_pass(self):
        skills = self._skills_root()
        current = skills / "skill-a"
        current.mkdir()
        (current / "SKILL.md").write_bytes(b"same\n")
        home = self.base / "home"
        home.mkdir()
        package = self._package(
            fixture={"baseline_id": "b1", "resources": [self._skill_fixture(current, "payload/skill-a")]},
            files={"payload/skill-a/SKILL.md": "same\n"},
        )
        self._register(package)
        scope = {
            "schema_version": 1, "skills_roots": [str(skills)],
            "hosts": [{
                "id": "codex", "platform": "codex", "config_home": str(home),
                "config": str(home / "config.toml"), "onboard_root": str(package),
                "skills_roots": [], "project_roots": [],
                "runtime": {"python": None, "node": None, "cli": None},
            }],
        }
        plan = self._plan(scope, self._vault(), package)
        report = {
            "hosts": [{"id": "codex", "platform": "codex", "applicability": "supported",
                       "disk": {"status": "aligned", "decision": "keep"},
                       "runtime": {"status": "unavailable"},
                       "host": {"status": "unverified"}, "legacy": {"status": "none"}}],
            "shell_profiles": [],
        }
        provider = sys.modules["sbtd_upgrade_hosts"]
        with mock.patch.object(provider, "verify_hosts", return_value=report):
            self.assertEqual(sbtd_upgrade.verify_upgrade(plan, probe=False)["status"], "aligned")
            self.assertEqual(sbtd_upgrade.verify_upgrade(plan, probe=True)["status"], "blocked")
        absent = {"hosts": [], "shell_profiles": []}
        with mock.patch.object(provider, "verify_hosts", return_value=absent):
            self.assertEqual(sbtd_upgrade.verify_upgrade(plan, probe=True)["status"], "blocked")

    def test_probe_ignores_unrequested_live_reload_but_requires_skills_and_shell(self):
        verified = {"status": "verified"}
        report = {
            "hosts": [{
                "id": "codex", "applicability": "supported",
                "disk": {"status": "aligned"}, "runtime": verified,
                "host": {"status": "unverified", "live_reload": {"status": "unsupported"},
                         "checks": {key: dict(verified) for key in ("binding", "protocol", "host_load", "skills")}},
            }],
            "shell_profiles": [{
                "path": "/selected/profile", "applicability": "supported",
                "disk": {"status": "aligned"}, "runtime": {"status": "not-applicable"},
                "host": {"status": "verified", "checks": {"command_resolution": dict(verified)}},
            }],
        }
        self.assertIsNone(sbtd_upgrade._host_verdict(report, probe=True)[0])
        report["hosts"][0]["host"]["checks"]["skills"] = {"status": "unavailable"}
        self.assertEqual(sbtd_upgrade._host_verdict(report, probe=True)[0], "blocked")
        report["hosts"][0]["host"]["checks"]["skills"] = {"status": "failed"}
        self.assertEqual(sbtd_upgrade._host_verdict(report, probe=True)[0], "drift")
        report["hosts"][0]["host"]["checks"]["skills"] = dict(verified)
        report["shell_profiles"][0]["host"]["checks"]["command_resolution"] = {"status": "unavailable"}
        self.assertEqual(sbtd_upgrade._host_verdict(report, probe=True)[0], "blocked")
        unsupported = {"hosts": [{"id": "claude", "applicability": "unsupported",
                                  "disk": {"status": "not-applicable"}, "host": {"status": "not-applicable"}}]}
        self.assertIsNone(sbtd_upgrade._host_verdict(unsupported, probe=True)[0])

    # -- review regressions: R02/R03/R05/R16/R17 ------------------------------

    @unittest.skipIf(os.name == "nt", "POSIX symlink scenario")
    def test_parent_preflight_ignores_unselected_sibling_links(self):
        """R05: apply preflight lstats only parent components, never the tree."""
        skills = self._skills_root()
        target = skills / "AGENTS.md"
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        (skills / "unselected-link").symlink_to(elsewhere, target_is_directory=True)
        (skills / "dangling-link").symlink_to(self.base / "missing-target")
        nested = skills / "nested"
        nested.mkdir()
        (nested / "deep-link").symlink_to(elsewhere, target_is_directory=True)
        if hasattr(os, "mkfifo"):
            os.mkfifo(skills / "unselected-fifo")
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [{
                    "id": f"agents@{target}",
                    "kind": "agents",
                    "source": "payload/AGENTS.global.md",
                    "target": str(target),
                }],
            },
            files={"payload/AGENTS.global.md": "# agents\n"},
        )
        self._register(package)
        vault = self._vault()
        plan = self._plan({"schema_version": 1, "agents_targets": [str(target)]}, vault, package)
        receipt = self._apply_local(plan)
        self.assertEqual(receipt["payload"]["status"], "complete")
        self.assertEqual(target.read_text(encoding="utf-8"), "# agents\n")
        # Unselected siblings are never read or disturbed.
        self.assertTrue((skills / "unselected-link").is_symlink())
        self.assertTrue((skills / "dangling-link").is_symlink())
        self.assertTrue((nested / "deep-link").is_symlink())

    @unittest.skipIf(os.name == "nt", "POSIX symlink scenario")
    def test_parent_preflight_refuses_linked_parents(self):
        """R05: a linked parent component itself is still refused."""
        real = self.base / "real"
        real.mkdir()
        (real / "sub").mkdir()
        link = self.base / "link"
        link.symlink_to(real, target_is_directory=True)
        for target in (
            link / "AGENTS.md",
            link / "sub" / "AGENTS.md",
            link / "missing" / "AGENTS.md",
        ):
            with self.subTest(target=str(target)):
                with self.assertRaises(ContractError) as caught:
                    sbtd_upgrade._missing_parents(target)
                self.assertEqual(caught.exception.code, "unsafe-path")

    def test_parent_preflight_refuses_file_parent(self):
        """R05: an existing parent that is a regular file is refused."""
        blocker = self.base / "blocker"
        blocker.write_text("x\n", encoding="utf-8")
        with self.assertRaises(ContractError) as caught:
            sbtd_upgrade._missing_parents(blocker / "AGENTS.md")
        self.assertEqual(caught.exception.code, "unsafe-path")

    def test_host_verdict_blocked_outranks_drift(self):
        """R17: one blocked domain is never hidden by another domain's drift."""
        report = {
            "hosts": [
                {"id": "blocked-host", "disk": {"status": "blocked"}},
                {"id": "drift-host", "disk": {"status": "missing"}},
            ]
        }
        verdict, exceptions = sbtd_upgrade._host_verdict(report)
        self.assertEqual(verdict, "blocked")
        self.assertEqual(exceptions, [])
        profiles = {
            "shell_profiles": [
                {"path": "/p", "disk": {"status": "blocked"}},
                {"path": "/q", "disk": {"status": "drifted"}},
            ]
        }
        self.assertEqual(sbtd_upgrade._host_verdict(profiles)[0], "blocked")
        drift_only = {"hosts": [{"id": "d", "disk": {"status": "drifted"}}]}
        self.assertEqual(sbtd_upgrade._host_verdict(drift_only)[0], "drift")

    def test_verify_status_blocked_outranks_skill_drift(self):
        """R17: aggregate verify keeps blocked over drift with per-domain evidence."""
        skills = self._skills_root()
        target = skills / "skill-a"
        target.mkdir()
        (target / "SKILL.md").write_text("original\n", encoding="utf-8")
        package = self._package(
            fixture={"baseline_id": "b1", "resources": [
                self._skill_fixture(target, "payload/skill-a"),
            ]},
            files={"payload/skill-a/SKILL.md": "replacement\n"},
        )
        self._register(package)
        vault = self._vault()
        plan = self._plan({
            "schema_version": 1, "skills_roots": [str(skills)],
            "decisions": {str(target): "replace"},
        }, vault, package)
        receipt = self._apply_local(plan)
        (target / "SKILL.md").write_text("user drift\n", encoding="utf-8")
        report = {
            "hosts": [
                {"id": "blocked-host", "disk": {"status": "blocked"}},
                {"id": "drift-host", "disk": {"status": "missing"}},
            ],
            "shell_profiles": [],
        }
        provider = sys.modules["sbtd_upgrade_hosts"]
        with mock.patch.object(provider, "verify_hosts", return_value=report):
            verification = sbtd_upgrade.verify_upgrade(plan, receipt=receipt)
        self.assertEqual(verification["status"], "blocked")
        rows = {row["id"]: row for row in verification["payload"]["resources"]}
        self.assertEqual(rows[f"skill@{target}"]["result"], "drift")

    def test_plan_seals_canonical_platform_and_probe_requires_reported_host(self):
        """R16: the oh-my-pi alias is sealed as canonical omp for every layer."""
        skills = self._skills_root()
        current = skills / "skill-a"
        current.mkdir()
        (current / "SKILL.md").write_bytes(b"same\n")
        home = self.base / "home"
        home.mkdir()
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [self._skill_fixture(current, "payload/skill-a")],
            },
            files={"payload/skill-a/SKILL.md": "same\n"},
        )
        self._register(package)
        scope = {
            "schema_version": 1, "skills_roots": [str(skills)],
            "hosts": [{
                "id": "omp-box", "platform": "oh-my-pi", "config_home": str(home),
                "config": str(home / "omp.json"), "onboard_root": str(package),
                "skills_roots": [], "project_roots": [],
                "runtime": {"python": None, "node": None, "cli": None},
            }],
        }
        plan = self._plan(scope, self._vault(), package)
        self.assertEqual(plan["payload"]["scope"]["hosts"][0]["platform"], "omp")
        verified = {"status": "verified"}
        report = {
            "hosts": [{
                "id": "omp-box", "platform": "omp", "applicability": "supported",
                "disk": {"status": "aligned", "decision": "keep"},
                "runtime": verified,
                "host": {"status": "verified", "checks": {
                    key: dict(verified)
                    for key in ("binding", "protocol", "host_load", "skills")
                }},
                "legacy": {"status": "none"},
            }],
            "shell_profiles": [],
        }
        provider = sys.modules["sbtd_upgrade_hosts"]
        with mock.patch.object(provider, "verify_hosts", return_value=report):
            self.assertEqual(sbtd_upgrade.verify_upgrade(plan, probe=True)["status"], "aligned")
        with mock.patch.object(
            provider, "verify_hosts", return_value={"hosts": [], "shell_profiles": []}
        ):
            self.assertEqual(sbtd_upgrade.verify_upgrade(plan, probe=True)["status"], "blocked")


    def test_preserve_decision_missing_host_config_still_installs(self):
        """R03 retained contract: preserve on a missing selected host config
        cannot keep it absent — the plan stays install and apply creates the
        valid rendered config."""
        import tomllib
        skills = self._skills_root()
        current = skills / "skill-a"
        current.mkdir()
        (current / "SKILL.md").write_bytes(b"same\n")
        package = self._package(
            fixture={"baseline_id": "b1", "resources": [self._skill_fixture(current, "payload/skill-a")]},
            files={
                "payload/skill-a/SKILL.md": "same\n",
                "SKILL.md": "---\nname: sbtd-workflow-onboard\n---\n",
                "scripts/sbtd_graft_entry.py": (SCRIPTS / "sbtd_graft_entry.py").read_text(encoding="utf-8"),
            },
        )
        self._register(package)
        real_inventory = self._real_module("sbtd_upgrade_inventory")
        fixture_inventory = sys.modules["sbtd_upgrade_inventory"]
        fixture_inventory._payload_scan = real_inventory._payload_scan
        fixture_inventory.payload_directory_state = real_inventory.payload_directory_state
        fixture_inventory.payload_file_state = real_inventory.payload_file_state
        real_hosts = self._real_module("sbtd_upgrade_hosts")
        sys.modules["sbtd_upgrade_hosts"] = real_hosts
        home = self.base / "codex-home"
        home.mkdir()
        config = home / "config.toml"
        runtime = self.base / "runtime"
        runtime.mkdir()
        for name in ("python", "node", "graft"):
            (runtime / name).write_text("fixture executable\n", encoding="utf-8")
        host = {
            "id": "codex", "platform": "codex", "config_home": str(home),
            "config": str(config), "onboard_root": str(package),
            "skills_roots": [], "project_roots": [],
            "runtime": {"python": str(runtime / "python"), "node": str(runtime / "node"), "cli": str(runtime / "graft")},
        }
        scope = {
            "schema_version": 1, "skills_roots": [str(skills)], "hosts": [host],
            "decisions": {str(config): "preserve"},
        }
        expected = real_hosts.render_resource(
            real_hosts.build_host_resources(scope, package_root=package)[0],
            package_root=package,
        )
        vault = self._vault()
        plan = self._plan(scope, vault, package)
        mcp = next(row for row in plan["payload"]["resources"] if row["kind"] == "mcp")
        self.assertEqual(mcp["classification"], "missing")
        self.assertEqual(mcp["decision"], "install")
        receipt = self._apply_local(plan)
        rows = {row["id"]: row for row in receipt["payload"]["resources"]}
        self.assertEqual(rows[mcp["id"]]["result"], "succeeded")
        self.assertEqual(config.read_bytes(), expected)
        parsed = tomllib.loads(config.read_text(encoding="utf-8"))
        self.assertIn("sbtd-graft", json.dumps(parsed))

    def test_post_write_persistence_failure_binds_batch_checkpoint(self):
        """R02: a post-mutation persistence failure keeps batch recovery evidence."""
        skills = self._skills_root()
        target = skills / "skill-a"
        target.mkdir()
        (target / "SKILL.md").write_text("original\n", encoding="utf-8")
        package = self._package(
            fixture={"baseline_id": "b1", "resources": [
                self._skill_fixture(target, "payload/skill-a"),
            ]},
            files={"payload/skill-a/SKILL.md": "replacement\n"},
        )
        self._register(package)
        vault = self._vault()
        plan = self._plan({
            "schema_version": 1, "skills_roots": [str(skills)],
            "decisions": {str(target): "replace"},
        }, vault, package)
        desired = plan["payload"]["resources"][0]["desired"]
        real_save = sbtd_upgrade._save_once

        def fail_final_receipt(path, document, vault_arg):
            if Path(path).name.startswith("upgrade-receipt-") and any(
                row.get("result") == "succeeded"
                for row in document["payload"]["resources"]
            ):
                raise OSError("injected receipt persistence failure")
            return real_save(path, document, vault_arg)

        with (
            mock.patch.object(sbtd_upgrade, "_save_once", fail_final_receipt),
            self.assertRaises(ContractError) as caught,
        ):
            self._apply_local(plan)
        error = caught.exception
        self.assertEqual(error.code, "write-failed")
        self.assertEqual(error.exit_code, 3)
        batch = (error.details or {}).get("batch")
        self.assertIsNotNone(batch)
        self.assertEqual(batch["phase"], "upgrade")
        self.assertEqual(batch["plan_id"], plan["plan_id"])
        self.assertEqual(batch["backup_root"], str(vault))
        persisted = list(vault.glob("upgrade-receipt-*.json"))
        self.assertEqual(len(persisted), 1)
        checkpoint = batch["checkpoint"]
        self.assertEqual(checkpoint["path"], str(persisted[0]))
        # The bound checkpoint is evidence, never this attempt's success.
        self.assertNotEqual(checkpoint["status"], "complete")
        self.assertEqual(batch["mutation"]["state"], "measured")
        measured = {row["id"]: row for row in batch["mutation"]["resources"]}
        self.assertEqual(measured[f"skill@{target}"]["after"], desired)
        self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), "replacement\n")

    @unittest.skipIf(os.name == "nt", "POSIX symlink scenario")
    def test_post_write_persistence_failure_reports_unknown_mutation(self):
        """R02: an unmeasurable post-mutation state is reported as unknown."""
        skills = self._skills_root()
        target = skills / "skill-a"
        target.mkdir()
        (target / "SKILL.md").write_text("original\n", encoding="utf-8")
        package = self._package(
            fixture={"baseline_id": "b1", "resources": [
                self._skill_fixture(target, "payload/skill-a"),
            ]},
            files={"payload/skill-a/SKILL.md": "replacement\n"},
        )
        self._register(package)
        vault = self._vault()
        plan = self._plan({
            "schema_version": 1, "skills_roots": [str(skills)],
            "decisions": {str(target): "replace"},
        }, vault, package)
        real_save = sbtd_upgrade._save_once

        def fail_and_poison(path, document, vault_arg):
            if Path(path).name.startswith("upgrade-receipt-") and any(
                row.get("result") == "succeeded"
                for row in document["payload"]["resources"]
            ):
                (target / "unselected-link").symlink_to(skills)
                raise OSError("injected receipt persistence failure")
            return real_save(path, document, vault_arg)

        with (
            mock.patch.object(sbtd_upgrade, "_save_once", fail_and_poison),
            self.assertRaises(ContractError) as caught,
        ):
            self._apply_local(plan)
        batch = (caught.exception.details or {}).get("batch")
        self.assertIsNotNone(batch)
        self.assertEqual(batch["mutation"]["state"], "unknown")
        measured = {row["id"]: row for row in batch["mutation"]["resources"]}
        self.assertIsNone(measured[f"skill@{target}"]["after"])

    def test_isolated_crash_after_intent_binds_checkpoint_and_mutation(self):
        """R02: an executor crash after intents binds checkpoint plus mutation."""
        skills = self._skills_root()
        target_a = skills / "skill-a"
        target_b = skills / "skill-b"
        for target, text in ((target_a, "old a\n"), (target_b, "old b\n")):
            target.mkdir()
            (target / "SKILL.md").write_text(text, encoding="utf-8")
        package = self._package(
            fixture={
                "baseline_id": "b1",
                "resources": [
                    self._skill_fixture(target_a, "payload/skill-a"),
                    self._skill_fixture(target_b, "payload/skill-b"),
                ],
            },
            files={
                "payload/skill-a/SKILL.md": "new a\n",
                "payload/skill-b/SKILL.md": "new b\n",
            },
        )
        self._register(package)
        vault = self._vault()
        scope = {
            "schema_version": 1,
            "skills_roots": [str(skills)],
            "decisions": {str(target_a): "replace", str(target_b): "replace"},
        }
        plan = self._plan(scope, vault, package)
        sealed = {row["id"]: row for row in plan["payload"]["resources"]}
        real_install = sbtd_upgrade.install_reference

        def failing_install(source_ref, target, expected, *, scope, backup_ref=None):
            if Path(target).name == "skill-b":
                raise ContractError("write-failed", "injected write failure", exit_code=3)
            return real_install(source_ref, target, expected, scope=scope, backup_ref=backup_ref)

        with mock.patch.object(sbtd_upgrade, "install_reference", failing_install):
            receipt = self._apply_local(plan)
        self.assertEqual(receipt["payload"]["status"], "partial")
        crash = ContractError(
            "self-upgrade-failed",
            "the isolated upgrade executor failed without a contract error",
            exit_code=3,
        )
        with (
            mock.patch.object(sbtd_upgrade, "_run_isolated", side_effect=crash),
            self.assertRaises(ContractError) as caught,
        ):
            sbtd_upgrade.apply_upgrade(
                plan, confirmed=plan["plan_id"], receipt=receipt
            )
        error = caught.exception
        self.assertEqual(error.code, "self-upgrade-failed")
        self.assertEqual(error.exit_code, 3)
        batch = (error.details or {}).get("batch")
        self.assertIsNotNone(batch)
        self.assertEqual(batch["checkpoint"]["receipt_id"], receipt["receipt_id"])
        self.assertNotEqual(batch["checkpoint"]["status"], "complete")
        self.assertEqual(batch["mutation"]["state"], "measured")
        measured = {row["id"]: row for row in batch["mutation"]["resources"]}
        self.assertEqual(measured[f"skill@{target_a}"]["after"], sealed[f"skill@{target_a}"]["desired"])
        self.assertEqual(measured[f"skill@{target_b}"]["after"], sealed[f"skill@{target_b}"]["before"])

    def test_pre_write_validation_has_no_batch_evidence(self):
        """R02: pre-write validation stays a plain blocked contract error."""
        skills = self._skills_root()
        target = skills / "skill-a"
        target.mkdir()
        (target / "SKILL.md").write_text("original\n", encoding="utf-8")
        package = self._package(
            fixture={"baseline_id": "b1", "resources": [
                self._skill_fixture(target, "payload/skill-a"),
            ]},
            files={"payload/skill-a/SKILL.md": "replacement\n"},
        )
        self._register(package)
        vault = self._vault()
        plan = self._plan({
            "schema_version": 1, "skills_roots": [str(skills)],
            "decisions": {str(target): "replace"},
        }, vault, package)
        (target / "SKILL.md").write_text("tampered\n", encoding="utf-8")
        with self.assertRaises(ContractError) as caught:
            self._apply_local(plan)
        self.assertEqual(caught.exception.code, "state-conflict")
        self.assertIsNone(caught.exception.details)

    def test_recovery_post_step_persistence_failure_binds_recovery_evidence(self):
        """R02: recovery persistence failures bind the recovery identity too."""
        plan, receipt, target, _agents, vault = self._recovery_batch()
        recovery = sbtd_upgrade.plan_recovery(plan, receipt)
        real_save = sbtd_upgrade._save_once

        def fail_final_receipt(path, document, vault_arg):
            if Path(path).name.startswith("upgrade-recovery-receipt-") and any(
                row.get("result") == "succeeded" for row in document["payload"]["steps"]
            ):
                raise OSError("injected recovery receipt persistence failure")
            return real_save(path, document, vault_arg)

        with (
            mock.patch.object(sbtd_upgrade, "_save_once", fail_final_receipt),
            self.assertRaises(ContractError) as caught,
        ):
            self._apply_recovery_local(recovery)
        error = caught.exception
        self.assertEqual(error.code, "write-failed")
        self.assertEqual(error.exit_code, 3)
        batch = (error.details or {}).get("batch")
        self.assertIsNotNone(batch)
        self.assertEqual(batch["phase"], "recovery")
        self.assertEqual(batch["recovery_id"], recovery["recovery_id"])
        self.assertEqual(batch["plan_id"], plan["plan_id"])
        self.assertEqual(batch["backup_root"], str(vault))
        self.assertNotEqual(batch["checkpoint"]["status"], "complete")
        self.assertEqual(batch["mutation"]["state"], "measured")
        self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), "original bytes\n")

    def test_post_write_halt_survives_intent_scan_io_failure(self):
        """R02: an evidence-scan I/O failure degrades to unknown mutation and
        never drops the bound batch — the write halt must not be lost."""
        skills = self._skills_root()
        target = skills / "skill-a"
        target.mkdir()
        (target / "SKILL.md").write_text("original\n", encoding="utf-8")
        package = self._package(
            fixture={"baseline_id": "b1", "resources": [
                self._skill_fixture(target, "payload/skill-a"),
            ]},
            files={"payload/skill-a/SKILL.md": "replacement\n"},
        )
        self._register(package)
        vault = self._vault()
        plan = self._plan({
            "schema_version": 1, "skills_roots": [str(skills)],
            "decisions": {str(target): "replace"},
        }, vault, package)
        real_save = sbtd_upgrade._save_once
        real_scan = sbtd_upgrade._scan_intents

        def fail_final_receipt(path, document, vault_arg):
            if Path(path).name.startswith("upgrade-receipt-") and any(
                row.get("result") == "succeeded"
                for row in document["payload"]["resources"]
            ):
                raise OSError("injected receipt persistence failure")
            return real_save(path, document, vault_arg)

        scans: list[str] = []

        def broken_second_scan(vault_arg, prefix, id_field):
            scans.append(prefix)
            if len(scans) > 1:
                raise OSError("injected intent scan failure")
            return real_scan(vault_arg, prefix, id_field)

        with (
            mock.patch.object(sbtd_upgrade, "_save_once", fail_final_receipt),
            mock.patch.object(sbtd_upgrade, "_scan_intents", broken_second_scan),
            self.assertRaises(ContractError) as caught,
        ):
            self._apply_local(plan)
        error = caught.exception
        self.assertEqual(error.code, "write-failed")
        self.assertEqual(error.exit_code, 3)
        batch = (error.details or {}).get("batch")
        self.assertIsNotNone(batch)
        self.assertEqual(batch["plan_id"], plan["plan_id"])
        self.assertEqual(batch["backup_root"], str(vault))
        persisted = list(vault.glob("upgrade-receipt-*.json"))
        self.assertEqual(len(persisted), 1)
        self.assertEqual(batch["checkpoint"]["path"], str(persisted[0]))
        self.assertNotEqual(batch["checkpoint"]["status"], "complete")
        # The intent scan failed: mutation state is honestly unknown, but the
        # batch, checkpoint and write halt are never lost.
        self.assertEqual(batch["mutation"]["state"], "unknown")
        self.assertEqual(batch["mutation"]["resources"], [])


if __name__ == "__main__":
    unittest.main()
