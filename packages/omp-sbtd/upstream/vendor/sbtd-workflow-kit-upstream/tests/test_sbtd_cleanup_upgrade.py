"""Behavior tests for the cleanup upgrade-hop trust continuation adapter.

Covers ``sbtd_cleanup_upgrade.validate_cleanup_upgrade`` and context
revalidation against real native upgrade operations: every hop is produced
by the actual ``sbtd_upgrade`` engine (sealed plan, guarded apply, complete
receipt, original backup) executed on real temporary directories, with the
inventory provider replaced by a fixture double driven by
``upgrade_fixture.json`` inside a synthetic package — the same seam the
engine's own tests use, so the staged isolated subprocess runs the
identical code path. Positive cases exercise the complete direct-hop
replacement of the canonical Onboard package; negative cases cover wrong
package/root/receipt/hash, drifted current state, tampered or missing
backups, symlinked evidence paths, partial/failed receipts, unrelated
writes and non-native executor evidence.
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
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

import sbtd_cleanup_upgrade
import sbtd_upgrade
from onboard_contracts import ContractError, canonical_json_bytes
from sbtd_migration_files import require_private_directory, snapshot

ONBOARD_ID = "skill:sbtd-workflow-onboard"

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
    return snapshot(Path(path))


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
        if before["type"] == "absent":
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
        "catalog": {"sha256": "0" * 64},
        "stable": {"stable_set": "fixture"},
        "runtime": {"requirements_sha256": "0" * 64},
        "source": {"path": str(root), "state": payload_directory_state(root)},
    }
    return {"baseline": baseline, "resources": resources, "domains": spec.get("domains", [])}
'''

ENGINE_COPY = (
    "sbtd_upgrade.py",
    "sbtd_upgrade_paths.py",
    "onboard_contracts.py",
    "sbtd_migration_files.py",
    "sbtd_cleanup_targets.py",
    "sbtd_project.py",
)

OLD_PACKAGE_FILES = {
    "scripts/sbtd_upgrade.py": "# historical package C\n",
    "scripts/sbtd_migration.py": "# historical migration runtime C\n",
    "VERSION": "1\n",
    "catalog.json": '{"entries": []}\n',
}


class CleanupUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.base, True)
        previous = sys.modules.get("sbtd_upgrade_inventory")

        def restore_provider():
            if previous is None:
                sys.modules.pop("sbtd_upgrade_inventory", None)
            else:
                sys.modules["sbtd_upgrade_inventory"] = previous

        self.addCleanup(restore_provider)

    # -- fixture helpers ----------------------------------------------------

    def _vault(self, name: str = "vault") -> Path:
        return require_private_directory(self.base / name, create=True)

    def _package(self, *, fixture: dict, files: dict[str, str], name: str) -> Path:
        package = self.base / name
        scripts = package / "scripts"
        scripts.mkdir(parents=True)
        for module_name in ENGINE_COPY:
            shutil.copy(SCRIPTS / module_name, scripts / module_name)
        (scripts / "sbtd_upgrade_inventory.py").write_text(
            FIXTURE_INVENTORY, encoding="utf-8"
        )
        (package / "upgrade_fixture.json").write_text(
            json.dumps(fixture), encoding="utf-8"
        )
        for relative, content in files.items():
            path = package / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return package

    def _register(self, package: Path) -> None:
        path = package / "scripts" / "sbtd_upgrade_inventory.py"
        module = types.ModuleType("sbtd_upgrade_inventory")
        module.__file__ = str(path)
        sys.modules["sbtd_upgrade_inventory"] = module
        exec(  # noqa: S102 -- test-owned provider source
            compile(path.read_text(encoding="utf-8"), str(path), "exec"),
            module.__dict__,
        )
        patcher = mock.patch.object(
            sbtd_upgrade, "_trusted_package_root", return_value=package
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _skills_root(self, name: str) -> Path:
        root = self.base / name
        root.mkdir(exist_ok=True)
        return root

    @staticmethod
    def _onboard_entry(target: Path, **flags) -> dict:
        entry = {
            "id": f"{ONBOARD_ID}@{target}",
            "kind": "skill",
            "source": ".",
            "target": str(target),
            "known_old": True,
        }
        entry.update(flags)
        return entry

    def _install_old_package(self, target: Path) -> None:
        for relative, content in OLD_PACKAGE_FILES.items():
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def _hop(
        self,
        *,
        label: str = "hop",
        extra_resources: list[dict] | None = None,
        extra_files: dict[str, str] | None = None,
        extra_decisions: dict[str, str] | None = None,
        isolated: bool = True,
    ):
        """One real native upgrade replacing the installed old package."""
        skills = self._skills_root(f"skills-{label}")
        target = skills / "sbtd-workflow-onboard"
        self._install_old_package(target)
        resources = [self._onboard_entry(target)]
        resources.extend(extra_resources or [])
        files = {"VERSION": "2\n", "FIXNOTE.md": "rc4 cleanup upgrade hop\n"}
        files.update(extra_files or {})
        package = self._package(
            fixture={"baseline_id": f"baseline-{label}", "resources": resources},
            files=files,
            name=f"pkg-{label}",
        )
        self._register(package)
        vault = self._vault(f"vault-{label}")
        decisions = {str(target): "replace"}
        decisions.update(extra_decisions or {})
        scope = {
            "schema_version": 1,
            "skills_roots": [str(skills)],
            "decisions": decisions,
        }
        plan = sbtd_upgrade.plan_upgrade(scope, vault, package_root=package)
        if isolated:
            receipt = sbtd_upgrade.apply_upgrade(plan, confirmed=plan["plan_id"])
        else:
            receipt = sbtd_upgrade._apply_upgrade_local(
                plan, confirmed=plan["plan_id"], receipt=None, package_root=package
            )
        return types.SimpleNamespace(
            skills=skills,
            target=target,
            package=package,
            vault=vault,
            plan=plan,
            receipt=receipt,
            plan_path=vault / f"upgrade-plan-{plan['plan_id']}.json",
            receipt_path=vault / f"upgrade-receipt-{receipt['receipt_id']}.json",
        )

    @staticmethod
    def _resign(document: dict, id_key: str, mutate) -> dict:
        """Structurally valid re-digested document with mutated payload."""
        payload = copy.deepcopy(document["payload"])
        mutate(payload)
        digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        return {"schema_version": 1, id_key: digest, "payload": payload}

    def _save_document(self, vault: Path, name: str, document: dict) -> Path:
        path = vault / name
        path.write_bytes(canonical_json_bytes(document))
        return path

    def _replacement_row(self, hop) -> dict:
        (row,) = [
            row
            for row in hop.receipt["payload"]["resources"]
            if row["id"].startswith(f"{ONBOARD_ID}@")
        ]
        return row

    # -- positive direct-hop behavior ---------------------------------------

    def test_complete_direct_hop_binds_previous_package(self):
        hop = self._hop()
        self.assertEqual(hop.receipt["payload"]["status"], "complete")
        self.assertTrue(hop.receipt["payload"]["executor"]["isolated"])
        self.assertEqual(
            (hop.target / "VERSION").read_text(encoding="utf-8"), "2\n"
        )

        context = sbtd_cleanup_upgrade.validate_cleanup_upgrade(
            hop.plan_path, hop.receipt_path, current_package=hop.target
        )

        row = self._replacement_row(hop)
        expected_backup = (
            hop.vault
            / "originals"
            / hop.plan["plan_id"][:16]
            / hashlib.sha256(row["id"].encode("utf-8")).hexdigest()[:32]
        )
        self.assertEqual(context.previous_package, expected_backup)
        self.assertEqual(context.current_package, hop.target)
        self.assertEqual(context.backup_root, hop.vault)
        self.assertEqual(context.plan_id, hop.plan["plan_id"])
        self.assertEqual(context.receipt_id, hop.receipt["receipt_id"])
        self.assertEqual(
            context.baseline_id, hop.plan["payload"]["baseline"]["baseline_id"]
        )
        self.assertEqual(context.resource_id, row["id"])
        # The complete original package survives in the private backup.
        self.assertEqual(
            (context.previous_package / "VERSION").read_text(encoding="utf-8"),
            "1\n",
        )
        self.assertEqual(
            (
                context.previous_package / "scripts" / "sbtd_migration.py"
            ).read_text(encoding="utf-8"),
            "# historical migration runtime C\n",
        )

        provenance = context.provenance
        self.assertEqual(provenance["schema"], "cleanup-upgrade-provenance")
        self.assertEqual(provenance["schema_version"], 1)
        self.assertEqual(provenance["plan_id"], hop.plan["plan_id"])
        self.assertEqual(provenance["receipt_id"], hop.receipt["receipt_id"])
        self.assertEqual(provenance["backup_root"], str(hop.vault))
        self.assertEqual(provenance["plan_ref"]["path"], str(hop.plan_path))
        self.assertEqual(
            provenance["plan_ref"]["state"], snapshot(hop.plan_path)
        )
        self.assertEqual(provenance["receipt_ref"]["path"], str(hop.receipt_path))
        self.assertEqual(
            provenance["receipt_ref"]["state"], snapshot(hop.receipt_path)
        )
        self.assertEqual(
            provenance["current_package"],
            {"path": str(hop.target), "state": row["after"]},
        )
        self.assertEqual(
            provenance["previous_package"],
            {"path": str(expected_backup), "state": row["backup_ref"]["state"]},
        )
        self.assertEqual(
            provenance["previous_payload_state"], row["before"]
        )
        self.assertEqual(
            row["before"], hop.plan["payload"]["resources"][0]["before"]
        )
        self.assertEqual(row["backup_ref"]["state"], row["mechanical_before"])
        # Provenance is JSON-safe for cleanup receipt citation.
        json.dumps(provenance)

        # Immutable context and working late revalidation.
        with self.assertRaises(dataclasses.FrozenInstanceError):
            context.plan_id = "0" * 64  # type: ignore[misc]
        refreshed = context.revalidate()
        self.assertEqual(refreshed, context)
        again = sbtd_cleanup_upgrade.revalidate_cleanup_upgrade(context)
        self.assertEqual(again.provenance, context.provenance)

    def test_retry_receipt_of_same_hop_remains_valid(self):
        hop = self._hop(label="retry")
        second = sbtd_upgrade.apply_upgrade(
            hop.plan, confirmed=hop.plan["plan_id"], receipt=hop.receipt
        )
        self.assertEqual(second["payload"]["status"], "complete")
        self.assertEqual(second["payload"]["sequence"], 1)
        self.assertEqual(
            second["payload"]["previous_receipt_id"], hop.receipt["receipt_id"]
        )
        second_path = hop.vault / f"upgrade-receipt-{second['receipt_id']}.json"
        context = sbtd_cleanup_upgrade.validate_cleanup_upgrade(
            hop.plan_path, second_path, current_package=hop.target
        )
        self.assertEqual(context.receipt_id, second["receipt_id"])
        self.assertEqual(context.previous_package.parent.parent, hop.vault / "originals")
        context.revalidate()

    def test_kept_neighbor_resources_are_accepted(self):
        skills = self._skills_root("skills-neighbors")
        target = skills / "sbtd-workflow-onboard"
        self._install_old_package(target)
        neighbors = []
        files = {"VERSION": "2\n"}
        decisions = {str(target): "replace"}
        for index in range(3):
            neighbor = skills / f"skill-{index}"
            source = f"payload/skill-{index}"
            neighbor.mkdir()
            (neighbor / "SKILL.md").write_text(f"current {index}\n", encoding="utf-8")
            files[f"{source}/SKILL.md"] = f"current {index}\n"
            neighbors.append(
                {
                    "id": f"skill:skill-{index}@{neighbor}",
                    "kind": "skill",
                    "source": source,
                    "target": str(neighbor),
                }
            )
        package = self._package(
            fixture={
                "baseline_id": "baseline-neighbors",
                "resources": [self._onboard_entry(target), *neighbors],
            },
            files=files,
            name="pkg-neighbors",
        )
        self._register(package)
        vault = self._vault("vault-neighbors")
        plan = sbtd_upgrade.plan_upgrade(
            {
                "schema_version": 1,
                "skills_roots": [str(skills)],
                "decisions": decisions,
            },
            vault,
            package_root=package,
        )
        decisions_set = {
            resource["id"]: resource["decision"]
            for resource in plan["payload"]["resources"]
        }
        self.assertEqual(
            decisions_set[f"{ONBOARD_ID}@{target}"], "replace"
        )
        self.assertEqual(
            sum(1 for decision in decisions_set.values() if decision == "keep"), 3
        )
        receipt = sbtd_upgrade.apply_upgrade(plan, confirmed=plan["plan_id"])
        self.assertEqual(receipt["payload"]["status"], "complete")
        context = sbtd_cleanup_upgrade.validate_cleanup_upgrade(
            vault / f"upgrade-plan-{plan['plan_id']}.json",
            vault / f"upgrade-receipt-{receipt['receipt_id']}.json",
            current_package=target,
        )
        self.assertEqual(context.current_package, target)
        self.assertTrue(
            str(context.previous_package).startswith(str(vault / "originals"))
        )

    # -- wrong evidence: package, root, receipt, hashes ---------------------

    def test_rejects_current_package_that_is_not_the_sealed_target(self):
        hop = self._hop()
        clone = self.base / "clone"
        shutil.copytree(hop.target, clone)
        for wrong in (hop.skills, clone, hop.package):
            with self.subTest(wrong=wrong):
                with self.assertRaises(ContractError) as raised:
                    sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                        hop.plan_path, hop.receipt_path, current_package=wrong
                    )
                self.assertEqual(raised.exception.code, "upgrade-hop-binding")

    def test_rejects_receipt_of_a_different_plan(self):
        first = self._hop(label="first")
        second = self._hop(label="second")
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                first.plan_path, second.receipt_path, current_package=first.target
            )
        self.assertEqual(raised.exception.code, "upgrade-hop-binding")

    def test_rejects_tampered_document_hashes(self):
        hop = self._hop()
        for path in (hop.plan_path, hop.receipt_path):
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(original + b" ")
                try:
                    with self.assertRaises(ContractError) as raised:
                        sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                            hop.plan_path, hop.receipt_path, current_package=hop.target
                        )
                    self.assertIn(
                        raised.exception.code,
                        {"plan-id-mismatch", "receipt-id-mismatch", "invalid-json"},
                    )
                finally:
                    path.write_bytes(original)

    def test_rejects_documents_outside_the_canonical_vault_names(self):
        hop = self._hop()
        elsewhere = self.base / "copies"
        elsewhere.mkdir()
        copied_plan = elsewhere / hop.plan_path.name
        copied_receipt = elsewhere / hop.receipt_path.name
        shutil.copy(hop.plan_path, copied_plan)
        shutil.copy(hop.receipt_path, copied_receipt)
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                copied_plan, hop.receipt_path, current_package=hop.target
            )
        self.assertEqual(raised.exception.code, "upgrade-hop-binding")
        renamed_receipt = hop.vault / "receipt-copy.json"
        shutil.copy(hop.receipt_path, renamed_receipt)
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                hop.plan_path, renamed_receipt, current_package=hop.target
            )
        self.assertEqual(raised.exception.code, "upgrade-hop-binding")

    def test_rejects_document_mutation_during_validation(self):
        # Mutation between the pinned read and the final recheck: the pin
        # must never be silently re-accepted as new evidence.
        hop = self._hop()
        original = hop.plan_path.read_bytes()
        real_read = sbtd_cleanup_upgrade.read_file

        def mutating_read(path, expected=None):
            content = real_read(path, expected)
            if Path(path) == hop.plan_path:
                hop.plan_path.write_bytes(content + b" ")
            return content

        try:
            with mock.patch.object(
                sbtd_cleanup_upgrade, "read_file", mutating_read
            ):
                with self.assertRaises(ContractError) as raised:
                    sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                        hop.plan_path, hop.receipt_path, current_package=hop.target
                    )
            self.assertEqual(raised.exception.code, "evidence-mismatch")
        finally:
            hop.plan_path.write_bytes(original)

        # Mutation between the state pin and the bound read: the parsed
        # bytes can never diverge from the pinned state.
        hop2 = self._hop(label="mutated-mid-read")
        original2 = hop2.plan_path.read_bytes()
        real_snapshot = sbtd_cleanup_upgrade.snapshot
        mutated = {"done": False}

        def mutating_snapshot(path):
            state = real_snapshot(path)
            if not mutated["done"] and Path(path) == hop2.plan_path:
                mutated["done"] = True
                hop2.plan_path.write_bytes(original2 + b" ")
            return state

        try:
            with mock.patch.object(
                sbtd_cleanup_upgrade, "snapshot", mutating_snapshot
            ):
                with self.assertRaises(ContractError) as raised:
                    sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                        hop2.plan_path,
                        hop2.receipt_path,
                        current_package=hop2.target,
                    )
            self.assertEqual(raised.exception.code, "state-conflict")
        finally:
            hop2.plan_path.write_bytes(original2)

    def test_rejects_receipt_with_foreign_baseline(self):
        hop = self._hop()
        forged = self._resign(
            hop.receipt,
            "receipt_id",
            lambda payload: payload.update(baseline_id="sha256:" + "0" * 64),
        )
        forged_path = self._save_document(
            hop.vault, f"upgrade-receipt-{forged['receipt_id']}.json", forged
        )
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                hop.plan_path, forged_path, current_package=hop.target
            )
        self.assertEqual(raised.exception.code, "upgrade-hop-binding")

    def test_rejects_inert_result_that_contradicts_sealed_decision(self):
        neighbor = self.base / "skills-flip" / "skill-0"
        neighbor.mkdir(parents=True)
        (neighbor / "SKILL.md").write_text("current 0\n", encoding="utf-8")
        hop = self._hop(
            label="flip",
            extra_resources=[
                {
                    "id": f"skill:skill-0@{neighbor}",
                    "kind": "skill",
                    "source": "payload/skill-0",
                    "target": str(neighbor),
                }
            ],
            extra_files={"payload/skill-0/SKILL.md": "current 0\n"},
        )
        neighbor_row = next(
            row
            for row in hop.receipt["payload"]["resources"]
            if row["id"].startswith("skill:skill-0@")
        )
        self.assertEqual(neighbor_row["result"], "kept")

        def flip(payload):
            for row in payload["resources"]:
                if row["id"].startswith("skill:skill-0@"):
                    row["result"] = "preserved"

        forged = self._resign(hop.receipt, "receipt_id", flip)
        forged_path = self._save_document(
            hop.vault, f"upgrade-receipt-{forged['receipt_id']}.json", forged
        )
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                hop.plan_path, forged_path, current_package=hop.target
            )
        self.assertEqual(raised.exception.code, "upgrade-hop-scope")

    def test_rejects_forged_plan_and_receipt_pair(self):
        hop = self._hop()
        bogus_before = {"type": "directory", "checksum": "0" * 64}
        forged_plan = self._resign(
            hop.plan,
            "plan_id",
            lambda payload: payload["resources"][0].update(before=bogus_before),
        )

        def forge_receipt(payload):
            payload["plan_id"] = forged_plan["plan_id"]
            payload["resources"][0]["before"] = bogus_before

        forged_receipt = self._resign(hop.receipt, "receipt_id", forge_receipt)
        forged_plan_path = self._save_document(
            hop.vault, f"upgrade-plan-{forged_plan['plan_id']}.json", forged_plan
        )
        forged_receipt_path = self._save_document(
            hop.vault,
            f"upgrade-receipt-{forged_receipt['receipt_id']}.json",
            forged_receipt,
        )
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                forged_plan_path, forged_receipt_path, current_package=hop.target
            )
        self.assertEqual(raised.exception.code, "upgrade-hop-binding")

    def test_rejects_forged_receipt_row_against_real_plan(self):
        hop = self._hop()
        forged_receipt = self._resign(
            hop.receipt,
            "receipt_id",
            lambda payload: payload["resources"][0].update(
                before={"type": "directory", "checksum": "0" * 64}
            ),
        )
        forged_path = self._save_document(
            hop.vault,
            f"upgrade-receipt-{forged_receipt['receipt_id']}.json",
            forged_receipt,
        )
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                hop.plan_path, forged_path, current_package=hop.target
            )
        self.assertEqual(raised.exception.code, "upgrade-hop-binding")

    # -- drifted current state and backups ----------------------------------

    def test_rejects_drifted_current_package_and_failed_revalidation(self):
        hop = self._hop()
        context = sbtd_cleanup_upgrade.validate_cleanup_upgrade(
            hop.plan_path, hop.receipt_path, current_package=hop.target
        )
        (hop.target / "LATE-DRIFT.md").write_text("drift\n", encoding="utf-8")
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                hop.plan_path, hop.receipt_path, current_package=hop.target
            )
        self.assertEqual(raised.exception.code, "upgrade-hop-drift")
        with self.assertRaises(ContractError) as reraised:
            context.revalidate()
        self.assertEqual(reraised.exception.code, "upgrade-hop-drift")

    def test_rejects_tampered_original_backup(self):
        hop = self._hop()
        context = sbtd_cleanup_upgrade.validate_cleanup_upgrade(
            hop.plan_path, hop.receipt_path, current_package=hop.target
        )
        (context.previous_package / "VERSION").write_text(
            "tampered\n", encoding="utf-8"
        )
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                hop.plan_path, hop.receipt_path, current_package=hop.target
            )
        self.assertEqual(raised.exception.code, "preservation-failed")
        self.assertEqual(raised.exception.exit_code, 3)
        with self.assertRaises(ContractError) as reraised:
            context.revalidate()
        self.assertEqual(reraised.exception.code, "preservation-failed")

    def test_rejects_missing_original_backup(self):
        hop = self._hop()
        context = sbtd_cleanup_upgrade.validate_cleanup_upgrade(
            hop.plan_path, hop.receipt_path, current_package=hop.target
        )
        shutil.rmtree(context.previous_package)
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                hop.plan_path, hop.receipt_path, current_package=hop.target
            )
        self.assertEqual(raised.exception.code, "preservation-failed")

    def test_rejects_backup_replaced_by_a_link(self):
        hop = self._hop()
        context = sbtd_cleanup_upgrade.validate_cleanup_upgrade(
            hop.plan_path, hop.receipt_path, current_package=hop.target
        )
        shutil.rmtree(context.previous_package)
        context.previous_package.symlink_to(hop.package)
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                hop.plan_path, hop.receipt_path, current_package=hop.target
            )
        self.assertEqual(raised.exception.code, "unsafe-path")

    # -- symlinked or private-path violations --------------------------------

    def test_rejects_symlinked_evidence_and_current_paths(self):
        hop = self._hop()
        linked_plan = self.base / "linked-plan.json"
        linked_plan.symlink_to(hop.plan_path)
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                linked_plan, hop.receipt_path, current_package=hop.target
            )
        self.assertEqual(raised.exception.code, "unsafe-path")

        alias = self.base / "alias"
        alias.symlink_to(hop.skills)
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                hop.plan_path,
                hop.receipt_path,
                current_package=alias / hop.target.name,
            )
        self.assertEqual(raised.exception.code, "unsafe-path")

    @unittest.skipUnless(os.name == "posix", "POSIX privacy proof")
    def test_rejects_vault_that_lost_privacy(self):
        hop = self._hop()
        context = sbtd_cleanup_upgrade.validate_cleanup_upgrade(
            hop.plan_path, hop.receipt_path, current_package=hop.target
        )
        os.chmod(hop.vault, 0o755)
        self.addCleanup(os.chmod, hop.vault, 0o700)
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                hop.plan_path, hop.receipt_path, current_package=hop.target
            )
        self.assertEqual(raised.exception.code, "privacy-unproven")
        with self.assertRaises(ContractError) as reraised:
            context.revalidate()
        self.assertEqual(reraised.exception.code, "privacy-unproven")

    def test_rejects_rewritten_evidence_document_on_revalidation(self):
        hop = self._hop()
        context = sbtd_cleanup_upgrade.validate_cleanup_upgrade(
            hop.plan_path, hop.receipt_path, current_package=hop.target
        )
        # Byte-different rewrite of identical content is still drift.
        document = json.loads(hop.plan_path.read_text(encoding="utf-8"))
        hop.plan_path.write_text(
            json.dumps(document, indent=2), encoding="utf-8"
        )
        with self.assertRaises(ContractError) as raised:
            context.revalidate()
        self.assertEqual(raised.exception.code, "evidence-mismatch")

    # -- incomplete, partial or off-scope batches ----------------------------

    def test_rejects_partial_and_failed_receipts(self):
        hop = self._hop()
        for status, failure in (("partial", None), ("failed", {"resource_id": "x", "code": "y"})):
            with self.subTest(status=status):

                def mutate(payload, status=status, failure=failure):
                    payload["status"] = status
                    payload["failure"] = failure

                forged = self._resign(hop.receipt, "receipt_id", mutate)
                forged_path = self._save_document(
                    hop.vault, f"upgrade-receipt-{forged['receipt_id']}.json", forged
                )
                with self.assertRaises(ContractError) as raised:
                    sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                        hop.plan_path, forged_path, current_package=hop.target
                    )
                self.assertEqual(raised.exception.code, "upgrade-hop-incomplete")

    def test_rejects_receipt_missing_a_resource_row(self):
        hop = self._hop()
        forged = self._resign(
            hop.receipt,
            "receipt_id",
            lambda payload: payload["resources"].pop(),
        )
        forged_path = self._save_document(
            hop.vault, f"upgrade-receipt-{forged['receipt_id']}.json", forged
        )
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                hop.plan_path, forged_path, current_package=hop.target
            )
        self.assertEqual(raised.exception.code, "upgrade-hop-incomplete")

    def test_rejects_batch_with_unrelated_writes(self):
        other = self.base / "skills-multi" / "skill-other"
        hop = self._hop(
            label="multi",
            extra_resources=[
                {
                    "id": f"skill:skill-other@{other}",
                    "kind": "skill",
                    "source": "payload/skill-other",
                    "target": str(other),
                }
            ],
            extra_files={"payload/skill-other/SKILL.md": "other\n"},
        )
        # The unrelated install really happened; the hop is still rejected.
        self.assertEqual(
            (other / "SKILL.md").read_text(encoding="utf-8"), "other\n"
        )
        self.assertEqual(hop.receipt["payload"]["status"], "complete")
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                hop.plan_path, hop.receipt_path, current_package=hop.target
            )
        self.assertEqual(raised.exception.code, "upgrade-hop-scope")

    def test_rejects_non_onboard_replacement(self):
        skills = self._skills_root("skills-alien")
        target = skills / "skill-other"
        target.mkdir()
        (target / "SKILL.md").write_text("old other\n", encoding="utf-8")
        package = self._package(
            fixture={
                "baseline_id": "baseline-alien",
                "resources": [
                    {
                        "id": f"skill:skill-other@{target}",
                        "kind": "skill",
                        "source": "payload/skill-other",
                        "target": str(target),
                        "known_old": True,
                    }
                ],
            },
            files={"payload/skill-other/SKILL.md": "new other\n"},
            name="pkg-alien",
        )
        self._register(package)
        vault = self._vault("vault-alien")
        plan = sbtd_upgrade.plan_upgrade(
            {
                "schema_version": 1,
                "skills_roots": [str(skills)],
                "decisions": {str(target): "replace"},
            },
            vault,
            package_root=package,
        )
        receipt = sbtd_upgrade.apply_upgrade(plan, confirmed=plan["plan_id"])
        self.assertEqual(receipt["payload"]["status"], "complete")
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                vault / f"upgrade-plan-{plan['plan_id']}.json",
                vault / f"upgrade-receipt-{receipt['receipt_id']}.json",
                current_package=target,
            )
        self.assertEqual(raised.exception.code, "upgrade-hop-scope")

    def test_rejects_plan_without_replacement_hop(self):
        skills = self._skills_root("skills-keep")
        target = skills / "sbtd-workflow-onboard"
        package = self._package(
            fixture={
                "baseline_id": "baseline-keep",
                "resources": [self._onboard_entry(target)],
            },
            files={"VERSION": "2\n"},
            name="pkg-keep",
        )
        # The installed copy is already current: nothing to replace.
        shutil.copytree(package, target)
        self._register(package)
        vault = self._vault("vault-keep")
        plan = sbtd_upgrade.plan_upgrade(
            {"schema_version": 1, "skills_roots": [str(skills)]},
            vault,
            package_root=package,
        )
        (resource,) = plan["payload"]["resources"]
        self.assertEqual(resource["decision"], "keep")
        receipt = sbtd_upgrade.apply_upgrade(plan, confirmed=plan["plan_id"])
        self.assertEqual(receipt["payload"]["status"], "complete")
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                vault / f"upgrade-plan-{plan['plan_id']}.json",
                vault / f"upgrade-receipt-{receipt['receipt_id']}.json",
                current_package=target,
            )
        self.assertEqual(raised.exception.code, "upgrade-hop-scope")

    def test_rejects_non_isolated_executor_evidence(self):
        hop = self._hop(label="local", isolated=False)
        self.assertFalse(hop.receipt["payload"]["executor"]["isolated"])
        self.assertEqual(hop.receipt["payload"]["status"], "complete")
        with self.assertRaises(ContractError) as raised:
            sbtd_cleanup_upgrade.validate_cleanup_upgrade(
                hop.plan_path, hop.receipt_path, current_package=hop.target
            )
        self.assertEqual(raised.exception.code, "upgrade-hop-binding")


if __name__ == "__main__":
    unittest.main()
