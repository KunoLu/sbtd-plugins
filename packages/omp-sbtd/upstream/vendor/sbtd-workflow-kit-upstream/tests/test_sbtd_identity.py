from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sbtd-workflow-onboard" / "scripts"))

from sbtd_identity import DeveloperStore


class DeveloperIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="sbtd-identity-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "project"
        self.root.mkdir()
        self.env = {
            **os.environ,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
        }
        subprocess.run(
            ["git", "init", "-b", "trunk", str(self.root)],
            env=self.env,
            capture_output=True,
            check=True,
        )
        (self.root / ".gitignore").write_text("/.sbtd/\n")

    def test_valid_local_identity_wins_without_git_or_legacy_reads(self) -> None:
        identity = self.root / ".sbtd/developer"
        identity.parent.mkdir()
        identity.write_bytes(b"name=dev01\n")
        legacy = self.root / ".trellis"
        legacy.mkdir()
        (legacy / ".developer").write_bytes(b"name=Legacy_Invalid\n")
        before = identity.read_bytes()
        with mock.patch.dict(os.environ, {"PATH": "", "TRELLIS_DEVELOPER": "ignored"}):
            resolved = DeveloperStore(self.root).resolve()
        self.assertEqual(resolved.status, "ready")
        self.assertEqual(resolved.name, "dev01")
        self.assertEqual(resolved.source, "local")
        self.assertFalse(resolved.first_write_eligible)
        self.assertEqual(identity.read_bytes(), before)
        self.assertEqual((legacy / ".developer").read_bytes(), b"name=Legacy_Invalid\n")

    def linked_checkout(self) -> Path:
        subprocess.run(
            ["git", "-C", str(self.root), "add", ".gitignore"],
            env=self.env,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "-c",
                "user.name=Synthetic Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-m",
                "fixture",
            ],
            env=self.env,
            capture_output=True,
            check=True,
        )
        linked = self.root.parent / "linked checkout"
        subprocess.run(
            ["git", "-C", str(self.root), "worktree", "add", "-b", "main", str(linked)],
            env=self.env,
            capture_output=True,
            check=True,
        )
        return linked

    def test_linked_checkout_reads_real_main_identity_without_copying_it(self) -> None:
        linked = self.linked_checkout()
        identity = self.root / ".sbtd/developer"
        identity.parent.mkdir()
        identity.write_bytes(b"name=main01\n")
        resolved = DeveloperStore(linked).resolve()
        self.assertEqual(resolved.status, "ready", resolved)
        self.assertEqual(resolved.name, "main01")
        self.assertEqual(resolved.source, "main-worktree")
        self.assertEqual(resolved.topology, "linked")
        self.assertFalse((linked / ".sbtd").exists())
        self.assertEqual(identity.read_bytes(), b"name=main01\n")

    def test_invalid_local_identity_never_falls_through_to_valid_main(self) -> None:
        linked = self.linked_checkout()
        main = self.root / ".sbtd/developer"
        main.parent.mkdir()
        main.write_bytes(b"name=main01\n")
        local = linked / ".sbtd/developer"
        local.parent.mkdir()
        local.write_bytes(b"name=Invalid_Name\n")
        resolved = DeveloperStore(linked).resolve()
        self.assertEqual(resolved.status, "conflict")
        self.assertIsNone(resolved.name)
        self.assertFalse(resolved.first_write_eligible)
        self.assertEqual(local.read_bytes(), b"name=Invalid_Name\n")

    def test_missing_git_is_unknown_not_permission_to_create_identity(self) -> None:
        with mock.patch.dict(os.environ, {"PATH": ""}):
            resolved = DeveloperStore(self.root).resolve()
        self.assertEqual(resolved.status, "blocked")
        self.assertEqual(resolved.topology, "unknown")
        self.assertFalse(resolved.first_write_eligible)
        self.assertFalse((self.root / ".sbtd").exists())

    def test_first_identity_requires_explicit_name_and_narrow_protection_permission(
        self,
    ) -> None:
        (self.root / ".gitignore").unlink()
        store = DeveloperStore(self.root)
        resolved = store.resolve()
        self.assertEqual(resolved.status, "needs-name")
        self.assertTrue(resolved.first_write_eligible)
        planned = store.plan("dev01")
        self.assertEqual(planned.status, "planned")
        self.assertTrue(planned.needs_protection)
        self.assertFalse((self.root / ".sbtd").exists())
        self.assertFalse((self.root / ".gitignore").exists())
        unconfirmed = store.ensure("dev01")
        self.assertEqual(unconfirmed.status, "needs-confirmation")
        protected = store.ensure("dev01", confirmed=True)
        self.assertEqual(protected.status, "needs-protection")
        self.assertFalse((self.root / ".gitignore").exists())
        created = store.ensure("dev01", confirmed=True, protect=True)
        self.assertEqual(created.status, "created")
        self.assertEqual(created.name, "dev01")
        self.assertEqual(created.source, "local")
        self.assertEqual((self.root / ".sbtd/developer").read_bytes(), b"name=dev01\n")
        self.assertEqual((self.root / ".gitignore").read_bytes(), b"/.sbtd/\n")
        self.assertEqual(
            {path.name for path in (self.root / ".sbtd").iterdir()}, {"developer"}
        )
        self.assertEqual(store.ensure("dev01", confirmed=True).status, "unchanged")
        self.assertEqual(store.ensure("other01", confirmed=True).status, "conflict")
        self.assertEqual((self.root / ".sbtd/developer").read_bytes(), b"name=dev01\n")

    def test_main_conflict_blocks_legacy_and_local_creation(self) -> None:
        linked = self.linked_checkout()
        main = self.root / ".sbtd/developer"
        main.parent.mkdir()
        main.write_bytes(b"name=main01\nname=second02\n")
        legacy = linked / ".trellis"
        legacy.mkdir()
        (legacy / ".developer").write_bytes(b"name=legacy01\n")
        result = DeveloperStore(linked).ensure("new01", confirmed=True, protect=True)
        self.assertEqual(result.status, "conflict")
        self.assertFalse(result.first_write_eligible)
        self.assertFalse((linked / ".sbtd").exists())
        self.assertEqual(main.read_bytes(), b"name=main01\nname=second02\n")
        self.assertEqual((legacy / ".developer").read_bytes(), b"name=legacy01\n")

    def test_verified_missing_main_allows_local_creation_without_backfilling_main(
        self,
    ) -> None:
        linked = self.linked_checkout()
        store = DeveloperStore(linked)
        missing = store.resolve()
        self.assertEqual(missing.status, "needs-name")
        self.assertEqual(missing.topology, "linked")
        self.assertTrue(missing.first_write_eligible)
        created = store.ensure("local01", confirmed=True)
        self.assertEqual(created.status, "created", created)
        self.assertEqual((linked / ".sbtd/developer").read_bytes(), b"name=local01\n")
        self.assertFalse((self.root / ".sbtd").exists())

    def test_inherited_identity_is_used_in_place_not_copied_or_overridden(self) -> None:
        linked = self.linked_checkout()
        identity = self.root / ".sbtd/developer"
        identity.parent.mkdir()
        identity.write_bytes(b"name=main01\n")
        store = DeveloperStore(linked)
        repeated = store.ensure("main01", confirmed=True, protect=True)
        self.assertEqual(repeated.status, "unchanged")
        self.assertEqual(repeated.source, "main-worktree")
        conflict = store.ensure("different02", confirmed=True, protect=True)
        self.assertEqual(conflict.status, "conflict")
        self.assertFalse((linked / ".sbtd").exists())
        self.assertEqual(identity.read_bytes(), b"name=main01\n")

    def test_symlink_identity_is_a_conflict_and_preserves_the_external_target(
        self,
    ) -> None:
        outside = self.root.parent / "outside-identity"
        outside.write_bytes(b"name=outside01\n")
        identity = self.root / ".sbtd/developer"
        identity.parent.mkdir()
        identity.symlink_to(outside)
        resolved = DeveloperStore(self.root).resolve()
        self.assertEqual(resolved.status, "conflict")
        self.assertIsNone(resolved.name)
        self.assertFalse(resolved.first_write_eligible)
        self.assertEqual(
            DeveloperStore(self.root).ensure("new01", confirmed=True).status, "conflict"
        )
        self.assertTrue(identity.is_symlink())
        self.assertEqual(outside.read_bytes(), b"name=outside01\n")

    def test_unknown_reserved_content_is_not_hidden_to_establish_identity(self) -> None:
        (self.root / ".gitignore").unlink()
        reserved = self.root / ".sbtd"
        reserved.mkdir()
        user_file = reserved / "user-notes"
        user_file.write_bytes(b"Preserve user business content.\n")
        result = DeveloperStore(self.root).ensure("dev01", confirmed=True, protect=True)
        self.assertEqual(result.status, "conflict")
        self.assertEqual(user_file.read_bytes(), b"Preserve user business content.\n")
        self.assertFalse((self.root / ".gitignore").exists())
        self.assertFalse((reserved / "developer").exists())

    def test_readonly_scope_refuses_first_identity_and_ignore_writes(self) -> None:
        (self.root / ".gitignore").unlink()
        result = DeveloperStore(self.root, read_only=True).ensure(
            "dev01", confirmed=True, protect=True
        )
        self.assertEqual(result.status, "blocked")
        self.assertFalse((self.root / ".gitignore").exists())
        self.assertFalse((self.root / ".sbtd").exists())

    def test_concurrent_identity_winner_is_never_overwritten(self) -> None:
        store = DeveloperStore(self.root)
        target = self.root / ".sbtd/developer"
        real_link = os.link

        def create_winner(source, destination, *args, **kwargs):
            if Path(destination) == target:
                target.write_bytes(b"name=winner01\n")
            return real_link(source, destination, *args, **kwargs)

        with mock.patch("sbtd_task_state.os.link", side_effect=create_winner):
            result = store.ensure("requested01", confirmed=True)
        self.assertEqual(result.status, "failed")
        self.assertEqual(target.read_bytes(), b"name=winner01\n")
        self.assertEqual(store.resolve().name, "winner01")

    def test_broken_git_marker_is_unknown_not_a_verified_non_git_project(self) -> None:
        retained = self.root.parent / "retained-git-metadata"
        (self.root / ".git").rename(retained)
        (self.root / ".git").mkdir()
        result = DeveloperStore(self.root).ensure("dev01", confirmed=True, protect=True)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.topology, "unknown")
        self.assertFalse(result.first_write_eligible)
        self.assertFalse((self.root / ".sbtd").exists())

    def test_valid_identity_wins_even_when_git_metadata_is_broken(self) -> None:
        retained = self.root.parent / "retained-git-metadata"
        (self.root / ".git").rename(retained)
        (self.root / ".git").mkdir()
        identity = self.root / ".sbtd/developer"
        identity.parent.mkdir()
        identity.write_bytes(b"name=local01\n")
        result = DeveloperStore(self.root).resolve()
        self.assertEqual(result.status, "ready")
        self.assertEqual(result.source, "local")
        self.assertEqual(result.name, "local01")

    def test_tracked_local_payload_blocks_identity_creation_without_untracking(
        self,
    ) -> None:
        payload = self.root / ".sbtd/user-data"
        payload.parent.mkdir()
        payload.write_bytes(b"tracked synthetic data\n")
        subprocess.run(
            ["git", "-C", str(self.root), "add", "-f", ".sbtd/user-data"],
            env=self.env,
            capture_output=True,
            check=True,
        )
        before = payload.read_bytes()
        result = DeveloperStore(self.root).ensure("dev01", confirmed=True, protect=True)
        self.assertEqual(result.status, "blocked")
        self.assertFalse((self.root / ".sbtd/developer").exists())
        self.assertEqual(payload.read_bytes(), before)
        tracked = subprocess.check_output(
            ["git", "-C", str(self.root), "ls-files", "--", ".sbtd/user-data"],
            env=self.env,
            text=True,
        )
        self.assertEqual(tracked.strip(), ".sbtd/user-data")

    def test_invalid_requested_name_is_not_normalized_or_persisted(self) -> None:
        result = DeveloperStore(self.root).ensure(
            " Dev01 ", confirmed=True, protect=True
        )
        self.assertEqual(result.status, "conflict")
        self.assertIsNone(result.name)
        assert result.reason is not None
        self.assertNotIn(" Dev01 ", result.reason)
        self.assertFalse((self.root / ".sbtd").exists())


    def test_protection_write_verification_failure_reports_gitignore_completion(
        self,
    ) -> None:
        from sbtd_task_state import TaskStateError

        (self.root / ".gitignore").unlink()
        store = DeveloperStore(self.root)
        verification_failure = TaskStateError(
            "local protection cannot be verified by Git"
        )
        with mock.patch.object(
            store.tasks,
            "_local_protected",
            side_effect=[False, False, verification_failure],
        ):
            result = store.ensure("dev01", confirmed=True, protect=True)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.completed_steps, (".gitignore",))
        self.assertEqual((self.root / ".gitignore").read_bytes(), b"/.sbtd/\n")
        self.assertFalse((self.root / ".sbtd/developer").exists())


if __name__ == "__main__":
    unittest.main()
