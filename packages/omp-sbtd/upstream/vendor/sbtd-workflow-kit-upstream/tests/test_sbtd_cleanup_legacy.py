from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from onboard_contracts import canonical_json_bytes
from sbtd_cleanup_legacy import apply_cleanup_legacy, plan_cleanup_legacy
from sbtd_migration_files import (
    backup_reference,
    remove_reference,
    require_private_directory,
    snapshot,
)

AGENTS_RAW = (
    b"<!-- TRELLIS:START -->\nlegacy route\n<!-- TRELLIS:END -->\n\n"
    b"<!-- gitnexus:start -->\nlegacy index notes\n<!-- gitnexus:end -->\n\n"
    b"# own rules\n\n<!-- graft:start -->\nfence\n<!-- graft:end -->\n"
)
AGENTS_CLEAN = b"\n\n# own rules\n\n<!-- graft:start -->\nfence\n<!-- graft:end -->\n"
AGENTS_LEGACY_ONLY = (
    b"<!-- TRELLIS:START -->\nlegacy route\n<!-- TRELLIS:END -->\n\n"
    b"<!-- gitnexus:start -->\nlegacy index notes\n<!-- gitnexus:end -->\n"
)
AGENTS_ONLY_SCRUBBED = (
    b"<!-- gitnexus:start -->\nlegacy index notes\n<!-- gitnexus:end -->\n"
)


def _vendor_scrub(raw: bytes) -> bytes:
    """Test-only vendor effect: drop the TRELLIS block and its blank line."""
    start = raw.index(b"<!-- TRELLIS:START -->")
    stop = raw.index(b"<!-- TRELLIS:END -->") + len(b"<!-- TRELLIS:END -->")
    if raw[stop : stop + 2] == b"\r\n":
        stop += 2
    elif raw[stop : stop + 1] == b"\n":
        stop += 1
    if raw[stop : stop + 1] == b"\n":
        stop += 1
    return raw[:start] + raw[stop:]


def _fake_vendor_prepare(root, *, environ=None):
    """Test-only vendor seam; production always uses the installed tl CLI."""
    root = Path(root)
    agents = root / "AGENTS.md"
    trellis = root / ".trellis"
    payload = {
        "root": str(root),
        "status": "ready",
        "resources": [
            {
                "resource_id": "trellis-000",
                "kind": "vendor-scrub",
                "path": str(agents),
                "relative": "AGENTS.md",
                "before": snapshot(agents),
                "expected_after": {
                    "type": "file",
                    "checksum": hashlib.sha256(
                        _vendor_scrub(agents.read_bytes())
                    ).hexdigest(),
                },
            },
            {
                "resource_id": "trellis-001",
                "kind": "vendor-trellis-dir",
                "path": str(trellis),
                "relative": ".trellis",
                "before": snapshot(trellis),
                "expected_after": {"type": "absent", "checksum": None},
            },
        ],
    }
    return {
        "schema_version": 1,
        "kind": "trellis-uninstall-prepare",
        "prepared_id": hashlib.sha256(canonical_json_bytes(payload)).hexdigest(),
        "payload": payload,
    }


def _fake_vendor_execute(root, prepared, backup_root, *, environ=None, partial=False):
    """Run test-double vendor effects with real private backups and measures."""
    vault = Path(backup_root)
    backup_dir = require_private_directory(vault / prepared["prepared_id"], create=True)
    resources_dir = require_private_directory(backup_dir / "resources", create=True)
    results = []
    for index, resource in enumerate(prepared["payload"]["resources"]):
        backup_ref = backup_reference(
            {"path": resource["path"], "state": resource["before"]},
            resources_dir / f"{index:03d}",
            private_root=vault,
        )
        path = Path(resource["path"])
        if resource["kind"] == "vendor-scrub":
            path.write_bytes(_vendor_scrub(path.read_bytes()))  # Test double only.
        elif not partial:
            shutil.rmtree(path)  # Test double only; production never deletes .trellis.
        after = snapshot(path)
        results.append(
            {
                "resource_id": resource["resource_id"],
                "kind": resource["kind"],
                "path": resource["path"],
                "relative": resource["relative"],
                "before": resource["before"],
                "backup_ref": backup_ref,
                "after": after,
                "status": (
                    ("scrubbed" if resource["kind"] == "vendor-scrub" else "removed")
                    if after == resource["expected_after"]
                    else "unchanged"
                ),
            }
        )
    return {
        "status": "partial" if partial else "removed",
        "root": str(root),
        "prepared_id": prepared["prepared_id"],
        "exit": 1 if partial else 0,
        "results": results,
        "errors": ["vendor-refused: simulated refusal"] if partial else [],
    }


@contextmanager
def _fake_vendor(*, execute=None):
    with (
        mock.patch(
            "sbtd_trellis_uninstall.prepare_trellis_uninstall",
            side_effect=_fake_vendor_prepare,
        ),
        mock.patch(
            "sbtd_trellis_uninstall.execute_trellis_uninstall",
            side_effect=execute or _fake_vendor_execute,
        ),
    ):
        yield


def _refuse_gitnexus_removal(path, expected, *, scope):
    if Path(path).name == ".gitnexus":
        raise OSError("simulated removal failure")
    return remove_reference(path, expected, scope=scope)


class CleanupLegacyFixture:
    def __init__(self, base: Path) -> None:
        self.base = base.resolve()
        self.home = self.base / "home"
        self.vault = self.base / "vault"
        self.skills = self.home / ".agent/skills"
        self.project = self.base / "project"
        self.home.mkdir(mode=0o700)
        self.vault.mkdir(mode=0o700)
        self.skills.mkdir(parents=True)
        (self.home / ".codex").mkdir()
        (self.home / ".codex/config.toml").write_text(
            '[mcp_servers.gitnexus]\ncommand = "gitnexus"\n\n'
            '[mcp_servers.context7]\ncommand = "npx"\n'
        )
        (self.home / ".claude.json").write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "gitnexus": {"command": "gitnexus"},
                        "playwright": {"command": "npx"},
                    }
                }
            )
        )
        for relative in (".kimi-code/mcp.json", ".omp/agent/mcp.json"):
            config = self.home / relative
            config.parent.mkdir(parents=True)
            config.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "gitnexus": {"command": "gitnexus"},
                            "custom-index": {
                                "command": "node",
                                "args": [
                                    "/opt/node_modules/gitnexus/dist/cli/index.js",
                                    "mcp",
                                ],
                            },
                            "browser": {"command": "npx", "args": ["@playwright/mcp"]},
                        }
                    }
                )
            )
        (self.project / ".gitnexus/index").mkdir(parents=True)
        (self.project / ".gitnexus/index/db.bin").write_bytes(b"\x00db\xff")
        (self.project / "AGENTS.md").write_bytes(AGENTS_RAW)
        skill = self.skills / "trellis-workflow"
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            "---\nname: trellis-workflow\n---\nOld 1.0.7 payload\n"
        )
        self.environ = {
            "HOME": str(self.home),
            "USERPROFILE": str(self.home),
            "CODEX_HOME": str(self.home / ".codex"),
            "AGENT_SKILLS_DIR": str(self.skills),
            "PATH": os.environ.get("PATH", ""),
        }

    def plan(self):
        envelope, code = plan_cleanup_legacy(
            [self.project], self.vault, skills_root=self.skills, environ=self.environ
        )
        return envelope, code

    def prepare(self):
        envelope, code = self.plan()
        if code:
            raise AssertionError(envelope)
        return Path(envelope["cleanup_legacy"]["plan_path"]), envelope["plan_id"]

    def apply(self, path, confirmation, receipt=None):
        return apply_cleanup_legacy(
            path,
            confirm_cleanup=confirmation,
            cleanup_receipt_path=receipt,
            environ=self.environ,
        )


class CleanupLegacyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.fixture = CleanupLegacyFixture(Path(self.temporary.name))

    def test_gitnexus_skill_retirement_requires_confirmation_and_preserves_original(self):
        """U12: fresh cleanup retires an exact old Skill, not a prefix neighbor."""
        fixture = self.fixture
        skill = fixture.skills / "gitnexus-cli"
        skill.mkdir()
        payload = b"---\nname: gitnexus-cli\n---\nUser-retained old tool instructions\n"
        (skill / "SKILL.md").write_bytes(payload)
        neighbor = fixture.skills / "gitnexus-cli-extra"
        neighbor.mkdir()
        (neighbor / "SKILL.md").write_bytes(payload)
        before = snapshot(skill)
        plan_path, plan_id = fixture.prepare()
        _rejected, code = fixture.apply(plan_path, "not-the-displayed-plan")
        self.assertNotEqual(code, 0)
        self.assertEqual(snapshot(skill), before)
        result, code = fixture.apply(plan_path, plan_id)
        self.assertEqual(code, 0, result)
        self.assertFalse(skill.exists())
        self.assertEqual((neighbor / "SKILL.md").read_bytes(), payload)
        rows = result["cleanup_legacy"]["receipt"]["payload"]["results"]
        retired = next(row for row in rows if row["path"] == str(skill))
        self.assertEqual(retired["status"], "succeeded")
        self.assertEqual(snapshot(Path(retired["backup_ref"]["path"])), before)

    def test_plan_preserves_targets_and_lists_actual_contents(self):
        fixture = self.fixture
        original = snapshot(fixture.project)
        envelope, code = fixture.plan()
        self.assertEqual(code, 0)
        self.assertEqual(envelope["status"], "planned")
        self.assertEqual(snapshot(fixture.project), original)
        payload = envelope["cleanup_legacy"]["plan"]["payload"]
        self.assertEqual(
            [p["kind"] for p in payload["projects"][0]["candidates"]],
            ["directory-remove", "marker-blocks"],
        )
        self.assertEqual(
            [p["host"] for p in payload["shared"]["mcp"]["candidates"]],
            ["codex", "claude", "kimi", "omp"],
        )

    def test_omp_directory_aliases_do_not_duplicate_cleanup_targets(self):
        fixture = self.fixture
        if not (fixture.home / ".OMP").is_dir():
            self.skipTest("requires case-insensitive directory aliases")
        fixture.environ["PI_CONFIG_DIR"] = ".OMP"
        envelope, code = fixture.plan()
        self.assertEqual((code, envelope["status"]), (0, "planned"))
        candidates = envelope["cleanup_legacy"]["plan"]["payload"]["shared"]["mcp"][
            "candidates"
        ]
        self.assertEqual(
            [row["path"] for row in candidates if row["host"] == "omp"],
            [str(fixture.home / ".omp/agent/mcp.json")],
        )
        cleaned, code = fixture.apply(
            Path(envelope["cleanup_legacy"]["plan_path"]), envelope["plan_id"]
        )
        self.assertEqual((code, cleaned["status"]), (0, "cleaned"))
        self.assertEqual(
            json.loads((fixture.home / ".omp/agent/mcp.json").read_bytes()),
            {
                "mcpServers": {
                    "browser": {"command": "npx", "args": ["@playwright/mcp"]}
                }
            },
        )

    def test_distinct_hardlinked_config_entries_are_both_cleaned(self):
        fixture = self.fixture
        claude = fixture.home / ".claude.json"
        omp = fixture.home / ".omp/agent/mcp.json"
        omp.unlink()
        omp.hardlink_to(claude)
        path, plan_id = fixture.prepare()
        envelope, code = fixture.apply(path, plan_id)
        self.assertEqual((code, envelope["status"]), (0, "cleaned"))
        expected = {"mcpServers": {"playwright": {"command": "npx"}}}
        self.assertEqual(json.loads(claude.read_bytes()), expected)
        self.assertEqual(json.loads(omp.read_bytes()), expected)

    def test_confirmation_is_required_before_every_target_write(self):
        fixture = self.fixture
        path, _plan_id = fixture.prepare()
        for confirmation in (None, "0" * 64):
            with self.subTest(confirmation=confirmation):
                before = snapshot(fixture.project)
                envelope, code = fixture.apply(path, confirmation)
                self.assertEqual((code, envelope["status"]), (2, "blocked"))
                self.assertEqual(snapshot(fixture.project), before)

    def test_confirmed_cleanup_preserves_neighbors_and_backups(self):
        fixture = self.fixture
        path, plan_id = fixture.prepare()
        envelope, code = fixture.apply(path, plan_id)
        self.assertEqual((code, envelope["status"]), (0, "cleaned"), envelope)
        self.assertFalse((fixture.project / ".gitnexus").exists())
        self.assertFalse((fixture.skills / "trellis-workflow").exists())
        self.assertEqual((fixture.project / "AGENTS.md").read_bytes(), AGENTS_CLEAN)
        self.assertEqual(
            json.loads((fixture.home / ".claude.json").read_text()),
            {"mcpServers": {"playwright": {"command": "npx"}}},
        )
        self.assertEqual(
            (fixture.home / ".codex/config.toml").read_text().strip(),
            '[mcp_servers.context7]\ncommand = "npx"',
        )
        for relative in (".kimi-code/mcp.json", ".omp/agent/mcp.json"):
            self.assertEqual(
                json.loads((fixture.home / relative).read_text()),
                {
                    "mcpServers": {
                        "browser": {"command": "npx", "args": ["@playwright/mcp"]}
                    }
                },
            )
        for row in envelope["cleanup_legacy"]["receipt"]["payload"]["results"]:
            self.assertEqual(row["status"], "succeeded")
            self.assertEqual(snapshot(Path(row["backup_ref"]["path"])), row["before"])
        rerun, code = fixture.apply(
            path, plan_id, Path(envelope["cleanup_legacy"]["receipt_path"])
        )
        self.assertEqual((code, rerun["status"]), (0, "cleaned"), rerun)
        self.assertEqual((fixture.project / "AGENTS.md").read_bytes(), AGENTS_CLEAN)

    def test_rehashed_plan_cannot_delete_unselected_directory(self):
        fixture = self.fixture
        path, _plan_id = fixture.prepare()
        unrelated = fixture.base / "unrelated"
        unrelated.mkdir()
        (unrelated / "keep.txt").write_text("user data")
        document = json.loads(path.read_text())
        candidate = document["payload"]["projects"][0]["candidates"][0]
        candidate["path"] = str(unrelated)
        candidate["before"] = snapshot(unrelated)
        document["plan_id"] = hashlib.sha256(
            canonical_json_bytes(document["payload"])
        ).hexdigest()
        path.write_text(json.dumps(document))
        envelope, code = fixture.apply(path, document["plan_id"])
        self.assertEqual((code, envelope["status"]), (2, "blocked"))
        self.assertEqual((unrelated / "keep.txt").read_text(), "user data")
        self.assertTrue((fixture.project / ".gitnexus").is_dir())

    def test_drift_after_plan_blocks_all_writes(self):
        fixture = self.fixture
        path, plan_id = fixture.prepare()
        (fixture.project / ".gitnexus/index/late.bin").write_bytes(b"drift")
        envelope, code = fixture.apply(path, plan_id)
        self.assertEqual((code, envelope["status"]), (2, "blocked"))
        self.assertEqual((fixture.project / "AGENTS.md").read_bytes(), AGENTS_RAW)

    def test_unavailable_vendor_is_blocked_not_an_executable_candidate(self):
        fixture = self.fixture
        (fixture.project / ".trellis").mkdir()
        fixture.environ["PATH"] = ""
        envelope, code = fixture.plan()
        self.assertEqual((code, envelope["status"]), (2, "blocked"))
        project = envelope["cleanup_legacy"]["plan"]["payload"]["projects"][0]
        self.assertFalse(
            any(item["kind"] == "trellis-uninstall" for item in project["candidates"])
        )
        self.assertEqual(project["blocked"][0]["kind"], "trellis-uninstall")
        self.assertTrue((fixture.project / ".trellis").is_dir())

    def test_malformed_global_config_is_not_reported_as_clean(self):
        fixture = self.fixture
        (fixture.home / ".claude.json").write_text("invalid")
        envelope, code = fixture.plan()
        self.assertEqual((code, envelope["status"]), (2, "blocked"))
        self.assertEqual(
            envelope["cleanup_legacy"]["plan"]["payload"]["shared"]["mcp"]["blocked"][
                0
            ]["host"],
            "claude",
        )

    def test_backup_directory_inside_project_is_rejected(self):
        from onboard_contracts import ContractError

        fixture = self.fixture
        vault = fixture.project / "vault"
        vault.mkdir(mode=0o700)
        with self.assertRaises(ContractError):
            plan_cleanup_legacy(
                [fixture.project],
                vault,
                skills_root=fixture.skills,
                environ=fixture.environ,
            )
        self.assertTrue((fixture.project / ".gitnexus").is_dir())

    def test_nested_cleanup_candidates_are_rejected_before_plan_writes(self):
        from onboard_contracts import ContractError

        for direction in ("skill-under-index", "index-under-skill"):
            with (
                self.subTest(direction=direction),
                tempfile.TemporaryDirectory() as temp,
            ):
                fixture = CleanupLegacyFixture(Path(temp))
                skill = fixture.skills / "trellis-workflow"
                if direction == "skill-under-index":
                    fixture.skills = fixture.project / ".gitnexus"
                    shutil.move(str(skill), str(fixture.skills / skill.name))
                    fixture.environ["AGENT_SKILLS_DIR"] = str(fixture.skills)
                else:
                    fixture.project = skill
                    (skill / ".gitnexus").mkdir()
                before = snapshot(fixture.base)
                with self.assertRaises(ContractError) as raised:
                    fixture.plan()
                self.assertEqual(raised.exception.code, "scope-conflict")
                self.assertEqual(snapshot(fixture.base), before)

    def test_old_overlapping_plan_is_rejected_before_any_deletion(self):
        fixture = self.fixture
        path, _plan_id = fixture.prepare()
        document = json.loads(path.read_text())
        skill = fixture.skills / "trellis-workflow"
        fixture.skills = fixture.project / ".gitnexus"
        nested = fixture.skills / skill.name
        shutil.move(str(skill), str(nested))
        fixture.environ["AGENT_SKILLS_DIR"] = str(fixture.skills)
        payload = document["payload"]
        payload["skills_root"] = str(fixture.skills)
        payload["shared"]["skills"]["candidates"][0]["path"] = str(nested)
        for candidate in payload["projects"][0]["candidates"]:
            if candidate["kind"] == "directory-remove":
                candidate["before"] = snapshot(fixture.skills)
        document["plan_id"] = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        path.write_text(json.dumps(document))
        before = snapshot(fixture.base)

        envelope, code = fixture.apply(path, document["plan_id"])

        self.assertEqual((code, envelope["status"]), (2, "blocked"))
        self.assertEqual(snapshot(fixture.base), before)

    def test_plan_symlink_is_rejected(self):
        fixture = self.fixture
        path, plan_id = fixture.prepare()
        link = fixture.vault / "link.json"
        link.symlink_to(path)
        envelope, code = fixture.apply(link, plan_id)
        self.assertEqual((code, envelope["status"]), (2, "blocked"))

    def test_write_failure_preserves_backup_and_records_partial_results(self):
        fixture = self.fixture
        path, plan_id = fixture.prepare()
        with mock.patch(
            "sbtd_cleanup_legacy.write_file", side_effect=OSError("write denied")
        ):
            envelope, code = fixture.apply(path, plan_id)
        self.assertEqual((code, envelope["status"]), (3, "failed"))
        rows = envelope["cleanup_legacy"]["receipt"]["payload"]["results"]
        self.assertEqual([r["status"] for r in rows], ["succeeded", "failed"])
        self.assertEqual((fixture.project / "AGENTS.md").read_bytes(), AGENTS_RAW)
        self.assertTrue((fixture.skills / "trellis-workflow").exists())

    def test_real_cli_plan_and_refusal_return_one_json_document(self):
        fixture = self.fixture
        env = dict(os.environ, **fixture.environ, PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "onboard.py"),
                "cleanup-legacy",
                "--phase",
                "plan",
                "--projects-root",
                str(fixture.project),
                "--backup-root",
                str(fixture.vault),
                "--json",
            ],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        rejected = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "onboard.py"),
                "cleanup-legacy",
                "--phase",
                "apply",
                "--plan",
                plan["cleanup_legacy"]["plan_path"],
                "--json",
            ],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(rejected.returncode, 2, rejected.stderr)
        self.assertEqual(json.loads(rejected.stdout)["status"], "blocked")
        self.assertEqual((fixture.project / "AGENTS.md").read_bytes(), AGENTS_RAW)

    def test_cli_explicit_skills_root_overrides_environment_and_stays_sealed(self):
        fixture = self.fixture
        custom = fixture.base / "custom-skills"
        selected = custom / "trellis-workflow"
        selected.mkdir(parents=True)
        original = b"---\nname: trellis-workflow\n---\ncustom installation\n"
        (selected / "SKILL.md").write_bytes(original)
        unselected = fixture.skills / "trellis-workflow"
        unselected_before = snapshot(unselected)
        env = dict(fixture.environ, PYTHONDONTWRITEBYTECODE="1")
        command = [sys.executable, "-B", str(SCRIPTS / "onboard.py"), "cleanup-legacy"]
        planned = subprocess.run(
            command
            + [
                "--phase",
                "plan",
                "--projects-root",
                str(fixture.project),
                "--backup-root",
                str(fixture.vault),
                "--global-skills-dir",
                str(custom),
                "--json",
            ],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(planned.returncode, 0, planned.stderr)
        plan = json.loads(planned.stdout)
        self.assertEqual(
            plan["cleanup_legacy"]["plan"]["payload"]["skills_root"], str(custom)
        )
        self.assertEqual((selected / "SKILL.md").read_bytes(), original)

        applied = subprocess.run(
            command
            + [
                "--phase",
                "apply",
                "--plan",
                plan["cleanup_legacy"]["plan_path"],
                "--confirm-cleanup",
                plan["plan_id"],
                "--json",
            ],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(applied.returncode, 0, applied.stderr)
        result = json.loads(applied.stdout)
        self.assertEqual(result["status"], "cleaned")
        self.assertFalse(selected.exists())
        self.assertEqual(snapshot(unselected), unselected_before)
        row = next(
            row
            for row in result["cleanup_legacy"]["receipt"]["payload"]["results"]
            if row["kind"] == "skill-directory"
        )
        self.assertEqual(
            (Path(row["backup_ref"]["path"]) / "SKILL.md").read_bytes(), original
        )

    def _vendor_failed_run(self):
        """Isolated first apply: vendor success, then unchanged .gitnexus failure."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        fixture = CleanupLegacyFixture(Path(temporary.name))
        (fixture.project / ".trellis").mkdir()
        (fixture.project / ".trellis/state.json").write_text("{}")
        with _fake_vendor():
            plan_path, plan_id = fixture.prepare()
            with mock.patch(
                "sbtd_cleanup_legacy.remove_reference",
                side_effect=_refuse_gitnexus_removal,
            ):
                envelope, code = fixture.apply(plan_path, plan_id)
        self.assertEqual((code, envelope["status"]), (3, "failed"), envelope)
        return (
            fixture,
            plan_path,
            plan_id,
            Path(envelope["cleanup_legacy"]["receipt_path"]),
        )

    def test_retry_uses_successful_vendor_after_states_for_remaining_candidates(self):
        fixture = self.fixture
        agents = fixture.project / "AGENTS.md"
        (fixture.project / ".trellis").mkdir()
        (fixture.project / ".trellis/state.json").write_text("{}")
        vendor_after = _vendor_scrub(AGENTS_RAW) + b"<!-- vendor-extra -->\n"

        def prepare_with_extra(root, *, environ=None):
            prepared = _fake_vendor_prepare(root, environ=environ)
            prepared["payload"]["resources"][0]["expected_after"] = {
                "type": "file",
                "checksum": hashlib.sha256(vendor_after).hexdigest(),
            }
            prepared["prepared_id"] = hashlib.sha256(
                canonical_json_bytes(prepared["payload"])
            ).hexdigest()
            return prepared

        def execute_with_extra(root, prepared, backup_root, *, environ=None):
            outcome = _fake_vendor_execute(root, prepared, backup_root, environ=environ)
            agents.write_bytes(vendor_after)
            outcome["results"][0]["after"] = snapshot(agents)
            outcome["results"][0]["status"] = "scrubbed"
            return outcome

        with (
            mock.patch(
                "sbtd_trellis_uninstall.prepare_trellis_uninstall",
                side_effect=prepare_with_extra,
            ),
            mock.patch(
                "sbtd_trellis_uninstall.execute_trellis_uninstall",
                side_effect=execute_with_extra,
            ),
        ):
            plan_path, plan_id = fixture.prepare()
            with mock.patch(
                "sbtd_cleanup_legacy.remove_reference",
                side_effect=_refuse_gitnexus_removal,
            ):
                first, code = fixture.apply(plan_path, plan_id)
        self.assertEqual((code, first["status"]), (3, "failed"), first)
        self.assertEqual(agents.read_bytes(), vendor_after)
        receipt_path = Path(first["cleanup_legacy"]["receipt_path"])
        retry, code = fixture.apply(plan_path, plan_id, receipt_path)
        self.assertEqual((code, retry["status"]), (0, "cleaned"), retry)
        self.assertEqual(agents.read_bytes(), AGENTS_CLEAN)
        marker_row = next(
            row
            for row in retry["cleanup_legacy"]["receipt"]["payload"]["results"]
            if row["kind"] == "marker-blocks"
        )
        self.assertEqual(
            Path(marker_row["backup_ref"]["path"]).read_bytes(), AGENTS_RAW
        )

    def test_vendor_scrub_then_unchanged_failure_retries_from_original_backup(self):
        fixture, plan_path, plan_id, receipt = self._vendor_failed_run()
        self.assertFalse((fixture.project / ".trellis").exists())
        self.assertEqual(
            (fixture.project / "AGENTS.md").read_bytes(), _vendor_scrub(AGENTS_RAW)
        )
        retry, code = fixture.apply(plan_path, plan_id, receipt)
        self.assertEqual((code, retry["status"]), (0, "cleaned"), retry)
        self.assertFalse((fixture.project / ".gitnexus").exists())
        # Both legacy blocks removed; graft fence and own rules byte-exact.
        self.assertEqual((fixture.project / "AGENTS.md").read_bytes(), AGENTS_CLEAN)
        rows = retry["cleanup_legacy"]["receipt"]["payload"]["results"]
        self.assertTrue(all(row["status"] == "succeeded" for row in rows))
        agents_row = next(row for row in rows if row["kind"] == "marker-blocks")
        self.assertEqual(
            agents_row["before"],
            {"type": "file", "checksum": hashlib.sha256(AGENTS_RAW).hexdigest()},
        )
        # The pending edit rendered from the reused immutable original backup.
        self.assertEqual(
            Path(agents_row["backup_ref"]["path"]).read_bytes(), AGENTS_RAW
        )
        again, code = fixture.apply(
            plan_path,
            plan_id,
            Path(retry["cleanup_legacy"]["receipt_path"]),
        )
        self.assertEqual((code, again["status"]), (0, "cleaned"), again)
        self.assertEqual((fixture.project / "AGENTS.md").read_bytes(), AGENTS_CLEAN)

    def test_vendor_leaving_only_legacy_block_writes_rendered_file_on_retry(self):
        fixture = self.fixture
        (fixture.project / "AGENTS.md").write_bytes(AGENTS_LEGACY_ONLY)
        (fixture.project / ".trellis").mkdir()
        (fixture.project / ".trellis/state.json").write_text("{}")
        with _fake_vendor():
            plan_path, plan_id = fixture.prepare()
            with mock.patch(
                "sbtd_cleanup_legacy.remove_reference",
                side_effect=_refuse_gitnexus_removal,
            ):
                envelope, code = fixture.apply(plan_path, plan_id)
            self.assertEqual((code, envelope["status"]), (3, "failed"), envelope)
            # The vendor left only the legacy gitnexus block behind.
            self.assertEqual(
                (fixture.project / "AGENTS.md").read_bytes(), AGENTS_ONLY_SCRUBBED
            )
            retry, code = fixture.apply(
                plan_path, plan_id, Path(envelope["cleanup_legacy"]["receipt_path"])
            )
            self.assertEqual((code, retry["status"]), (0, "cleaned"), retry)
        # Both blocks were the whole file: the planned outcome keeps the
        # original file with exactly the rendered block-free bytes (the one
        # newline that separated the two legacy blocks).
        self.assertEqual((fixture.project / "AGENTS.md").read_bytes(), b"\n")
        rows = retry["cleanup_legacy"]["receipt"]["payload"]["results"]
        agents_row = next(row for row in rows if row["kind"] == "marker-blocks")
        self.assertEqual(agents_row["status"], "succeeded")
        self.assertEqual(
            agents_row["after"],
            {"type": "file", "checksum": hashlib.sha256(b"\n").hexdigest()},
        )

    def test_retry_rejects_tampered_vendor_transition(self):
        def vendor_outcome(payload):
            row = next(
                r for r in payload["results"] if r["kind"] == "trellis-uninstall"
            )
            return row["vendor"]

        def vendor_results(payload):
            return vendor_outcome(payload)["results"]

        def scrub_result(payload):
            return next(
                r for r in vendor_results(payload) if r["kind"] == "vendor-scrub"
            )

        cases = {
            "after": lambda fixture, payload: scrub_result(payload).update(
                after={"type": "file", "checksum": "0" * 64}
            ),
            "backup-state": lambda fixture, payload: scrub_result(payload)[
                "backup_ref"
            ].update(state={"type": "file", "checksum": "0" * 64}),
            "backup-path": lambda fixture, payload: scrub_result(payload)[
                "backup_ref"
            ].update(path=str(fixture.project / "AGENTS.md")),
            "unlisted-path": lambda fixture, payload: vendor_results(payload).append(
                dict(scrub_result(payload), path=str(fixture.project / "OTHER.md"))
            ),
            "duplicate-path": lambda fixture, payload: vendor_results(payload).append(
                dict(scrub_result(payload))
            ),
            "exit": lambda fixture, payload: vendor_outcome(payload).update(exit=1),
            "exit-bool": lambda fixture, payload: vendor_outcome(payload).update(
                exit=False
            ),
            "resource-id": lambda fixture, payload: scrub_result(payload).update(
                resource_id="trellis-999"
            ),
            "kind": lambda fixture, payload: scrub_result(payload).update(
                kind="vendor-delete"
            ),
            "relative": lambda fixture, payload: scrub_result(payload).update(
                relative="OTHER.md"
            ),
            "status": lambda fixture, payload: scrub_result(payload).update(
                status="removed"
            ),
            "null-first-result": lambda fixture, payload: vendor_results(
                payload
            ).__setitem__(0, None),
            "failed-vendor-not-mapping": lambda fixture, payload: payload["results"][
                -1
            ].update(vendor=[]),
            "failed-vendor-null-results": lambda fixture, payload: payload["results"][
                -1
            ].update(vendor={"status": "failed", "results": None}),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                fixture, plan_path, plan_id, receipt = self._vendor_failed_run()
                document = json.loads(receipt.read_text())
                mutate(fixture, document["payload"])
                document["receipt_id"] = hashlib.sha256(
                    canonical_json_bytes(document["payload"])
                ).hexdigest()
                receipt.write_text(json.dumps(document))
                envelope, code = fixture.apply(plan_path, plan_id, receipt)
                self.assertEqual((code, envelope["status"]), (2, "blocked"), envelope)
                self.assertEqual(
                    (fixture.project / "AGENTS.md").read_bytes(),
                    _vendor_scrub(AGENTS_RAW),
                )
                self.assertTrue((fixture.project / ".gitnexus").is_dir())

    def test_retry_rejects_null_prepared_resource(self):
        fixture, plan_path, _plan_id, receipt = self._vendor_failed_run()
        plan = json.loads(plan_path.read_text())
        candidate = plan["payload"]["projects"][0]["candidates"][0]
        candidate["trellis"]["payload"]["resources"].append(None)
        candidate["trellis"]["prepared_id"] = hashlib.sha256(
            canonical_json_bytes(candidate["trellis"]["payload"])
        ).hexdigest()
        plan["plan_id"] = hashlib.sha256(
            canonical_json_bytes(plan["payload"])
        ).hexdigest()
        plan_path.write_text(json.dumps(plan))
        document = json.loads(receipt.read_text())
        document["payload"]["plan_id"] = plan["plan_id"]
        row = next(
            r
            for r in document["payload"]["results"]
            if r["kind"] == "trellis-uninstall"
        )
        row["vendor"]["prepared_id"] = candidate["trellis"]["prepared_id"]
        document["receipt_id"] = hashlib.sha256(
            canonical_json_bytes(document["payload"])
        ).hexdigest()
        receipt.write_text(json.dumps(document))
        envelope, code = fixture.apply(plan_path, plan["plan_id"], receipt)
        self.assertEqual((code, envelope["status"]), (2, "blocked"), envelope)
        self.assertEqual(
            (fixture.project / "AGENTS.md").read_bytes(), _vendor_scrub(AGENTS_RAW)
        )
        self.assertTrue((fixture.project / ".gitnexus").is_dir())

    def test_retry_rejects_agents_edit_after_vendor_scrub(self):
        fixture, plan_path, plan_id, receipt = self._vendor_failed_run()
        edited = _vendor_scrub(AGENTS_RAW) + b"\nuser note\n"
        (fixture.project / "AGENTS.md").write_bytes(edited)
        envelope, code = fixture.apply(plan_path, plan_id, receipt)
        self.assertEqual((code, envelope["status"]), (2, "blocked"), envelope)
        self.assertEqual((fixture.project / "AGENTS.md").read_bytes(), edited)
        self.assertTrue((fixture.project / ".gitnexus").is_dir())

    def test_partial_vendor_outcome_stays_blocked_on_retry(self):
        fixture = self.fixture
        (fixture.project / ".trellis").mkdir()
        (fixture.project / ".trellis/state.json").write_text("{}")
        partial_execute = lambda *args, **kwargs: _fake_vendor_execute(
            *args, partial=True, **kwargs
        )
        with _fake_vendor(execute=partial_execute):
            plan_path, plan_id = fixture.prepare()
            envelope, code = fixture.apply(plan_path, plan_id)
            self.assertEqual((code, envelope["status"]), (3, "failed"), envelope)
            # The partial vendor scrubbed AGENTS.md but kept .trellis.
            self.assertEqual(
                (fixture.project / "AGENTS.md").read_bytes(), _vendor_scrub(AGENTS_RAW)
            )
            self.assertTrue((fixture.project / ".trellis").is_dir())
            retry, code = fixture.apply(
                plan_path, plan_id, Path(envelope["cleanup_legacy"]["receipt_path"])
            )
        self.assertEqual((code, retry["status"]), (2, "blocked"), retry)
        self.assertEqual(
            (fixture.project / "AGENTS.md").read_bytes(), _vendor_scrub(AGENTS_RAW)
        )
        self.assertTrue((fixture.project / ".trellis").is_dir())
        self.assertTrue((fixture.project / ".gitnexus").is_dir())

    def test_retry_after_second_failure_at_pending_agents_write(self):
        fixture, plan_path, plan_id, receipt = self._vendor_failed_run()
        with mock.patch(
            "sbtd_cleanup_legacy.write_file", side_effect=OSError("write denied")
        ):
            second, code = fixture.apply(plan_path, plan_id, receipt)
        self.assertEqual((code, second["status"]), (3, "failed"), second)
        # .gitnexus completed; AGENTS.md is unchanged at the vendor state, not
        # a partial cleanup that would demand reconciliation.
        self.assertFalse((fixture.project / ".gitnexus").exists())
        self.assertEqual(
            (fixture.project / "AGENTS.md").read_bytes(), _vendor_scrub(AGENTS_RAW)
        )
        third, code = fixture.apply(
            plan_path, plan_id, Path(second["cleanup_legacy"]["receipt_path"])
        )
        self.assertEqual((code, third["status"]), (0, "cleaned"), third)
        self.assertEqual((fixture.project / "AGENTS.md").read_bytes(), AGENTS_CLEAN)


if __name__ == "__main__":
    unittest.main()
