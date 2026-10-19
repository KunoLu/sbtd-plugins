"""Follow-up predecessor gates: configure-graft section ownership.

A completed batch's configure-graft outcomes (Codex config.toml, hooks.json,
OMP mcp.json, project AGENTS.md fences) are gated by managed-section
ownership, not whole-file equality: the host runtime may append sections
beside the graft-owned entries. Chains seal the deployed bytes first, then
the host content mutates, so a passing case proves the gate relaxed. Every
case builds its own temporary predecessor chain; nothing reads private
deployment evidence.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from onboard_contracts import ContractError
from sbtd_codex_wiring import (
    codex_hooks_candidate,
    codex_mcp_candidate,
    project_agents_candidate,
)
from sbtd_migration_files import snapshot
from sbtd_migration_plan import _check_followup_predecessor_outcomes
from sbtd_omp_wiring import desired_omp_server


def _bindings(root, package):
    return {
        "root": str(root),
        "node": "/fixture/node",
        "cli": "/fixture/cli.js",
        "python": "/fixture/python",
        "launcher": str(package / "scripts/sbtd_graft_entry.py"),
    }


def _legacy_server_key(root):
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()
    return f"sbtd-graft-{digest[:16]}"


def _legacy_omp_record(root, package):
    """The exact retired fixed-root OMP record, for historical receipts."""
    bindings = _bindings(root, package)
    return {
        "type": "stdio",
        "command": bindings["python"],
        "args": [
            "-E", "-s", bindings["launcher"], "mcp", "--root", bindings["root"],
            "--node", bindings["node"], "--entry", bindings["cli"],
        ],
        "cwd": bindings["root"],
        "env": {"DO_NOT_TRACK": "1", "DNT": "1"},
    }


def _legacy_codex_toml(root, package):
    """The exact retired fixed-root config.toml entry, for old receipts."""
    bindings = _bindings(root, package)
    args = [
        "-E", "-s", bindings["launcher"], "mcp", "--root", bindings["root"],
        "--node", bindings["node"], "--entry", bindings["cli"],
    ]
    return (
        f"[mcp_servers.{_legacy_server_key(root)}]\n"
        f'command = "{bindings["python"]}"\n'
        f"args = {json.dumps(args)}\n"
        f'cwd = "{bindings["root"]}"\n'
        f"[mcp_servers.{_legacy_server_key(root)}.env]\n"
        'DO_NOT_TRACK = "1"\nDNT = "1"\n'
    )


def _seal(target, selector, roots, *, kind="configure-graft", owner="markdown",
          anchors=()):
    """Seal one predecessor chain against the CURRENT target bytes."""
    operations = [
        {
            "phase": "deploy",
            "resource_id": "resource-1",
            "target": str(target),
            "selector": selector,
            "owner_kind": owner,
            "change": {"kind": kind, "source_ref": "policy"},
            "dependent_projects": sorted(str(root) for root in roots),
        }
    ]
    results = {
        "deploy": {
            "resource-1": {"status": "succeeded", "after": snapshot(Path(target))}
        }
    }
    for index, anchor in enumerate(anchors):
        operations.append(
            {
                "phase": "deploy",
                "resource_id": f"anchor-{index}",
                "target": str(anchor),
                "selector": "whole-resource",
                "owner_kind": "directory",
                "change": {"kind": "build-graft", "source_ref": "policy"},
                "dependent_projects": sorted(str(root) for root in roots),
            }
        )
        results["deploy"][f"anchor-{index}"] = {
            "status": "succeeded",
            "after": snapshot(Path(anchor)),
        }
    manifest = {"payload": {"projects": [], "shared_operations": operations}}
    return [(manifest, results)]


def _check(chain):
    return _check_followup_predecessor_outcomes(chain, overwritten=())


class FollowupSectionGateTests(unittest.TestCase):
    def assert_conflict(self, chain, code="state-conflict"):
        with self.assertRaises(ContractError) as error:
            _check(chain)
        self.assertEqual(error.exception.code, code)

    def _package(self, base, name="pkg"):
        package = base / name
        (package / "scripts").mkdir(parents=True)
        return package

    def _codex_config(self, base, roots, package):
        target = base / "config.toml"
        target.write_bytes(
            codex_mcp_candidate(b"", [_bindings(root, package) for root in roots])
        )
        return target

    def test_toml_host_appended_sections_do_not_block(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            package = self._package(base)
            target = self._codex_config(base, [root], package)
            chain = _seal(target, "graft-mcp", [root], owner="toml",
                          anchors=[package])
            target.write_bytes(
                target.read_bytes()
                + b'\n[hooks.state.persist]\nenabled = true\n'
                + b'[projects."/other"]\ntrust_level = "trusted"\n'
                + b"[desktop]\nnotifications = false\n"
            )
            outcome = _check(chain)
            self.assertEqual(outcome[str(target)], snapshot(target))

    def test_toml_global_receipt_without_projects_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            package = self._package(base)
            target = self._codex_config(base, [base / "project"], package)
            chain = _seal(target, "graft-mcp", [], owner="toml",
                          anchors=[package])
            outcome = _check(chain)
            self.assertIn(str(target), outcome)

    def test_toml_historical_fixed_root_receipt_still_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            package = self._package(base)
            target = base / "config.toml"
            target.write_text(_legacy_codex_toml(root, package), encoding="utf-8")
            chain = _seal(target, "graft-mcp", [root], owner="toml",
                          anchors=[package])
            outcome = _check(chain)
            self.assertIn(str(target), outcome)
            changed = target.read_bytes().replace(
                b"/fixture/cli.js", b"/fixture/other.js"
            )
            target.write_bytes(changed)
            self.assert_conflict(chain)

    def test_toml_legacy_entry_beside_global_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            package = self._package(base)
            target = self._codex_config(base, [root], package)
            chain = _seal(target, "graft-mcp", [root], owner="toml",
                          anchors=[package])
            # A retired fixed-root entry beside the global definition mixes
            # managed generations; the gate cannot prove which is drift.
            target.write_bytes(
                target.read_bytes()
                + b"\n"
                + _legacy_codex_toml(root, package).encode()
            )
            self.assert_conflict(chain)

    def test_toml_managed_entry_tampering_still_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            package = self._package(base)

            target = self._codex_config(base, [root], package)
            chain = _seal(target, "graft-mcp", [root], owner="toml",
                          anchors=[package])
            changed = target.read_bytes().replace(
                b"/fixture/cli.js", b"/fixture/other.js"
            )
            self.assertNotEqual(changed, target.read_bytes())
            target.write_bytes(changed)
            self.assert_conflict(chain)

            target = self._codex_config(base, [root], package)
            chain = _seal(target, "graft-mcp", [root], owner="toml",
                          anchors=[package])
            text = target.read_text(encoding="utf-8")
            target.write_text(text[: text.index("[mcp_servers.")],
                              encoding="utf-8")
            self.assert_conflict(chain)

            target = self._codex_config(base, [root], package)
            chain = _seal(target, "graft-mcp", [root], owner="toml",
                          anchors=[package])
            changed = target.read_bytes().replace(b'DNT = "1"', b'DNT = "0"')
            self.assertNotEqual(changed, target.read_bytes())
            target.write_bytes(changed)
            self.assert_conflict(chain)

            chain = _seal(target, "graft-mcp", [root], owner="toml",
                          anchors=[package])
            target.unlink()
            self.assert_conflict(chain)

    def test_toml_historical_receipt_with_global_entry_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            package = self._package(base)
            target = base / "config.toml"
            target.write_text(_legacy_codex_toml(root, package), encoding="utf-8")
            chain = _seal(target, "graft-mcp", [root], owner="toml",
                          anchors=[package])
            # The global definition beside a historical fixed-root receipt
            # is the same mixed-generation ambiguity, in the other order.
            target.write_bytes(
                target.read_bytes()
                + b"\n"
                + codex_mcp_candidate(b"", [_bindings(root, package)])
            )
            self.assert_conflict(chain)

    def test_toml_launcher_outside_deployment_tree_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            package = self._package(base)
            elsewhere = self._package(base, "elsewhere")
            target = base / "config.toml"
            target.write_bytes(
                codex_mcp_candidate(b"", [_bindings(root, elsewhere)])
            )
            chain = _seal(target, "graft-mcp", [root], owner="toml",
                          anchors=[package])
            self.assert_conflict(chain)

    def test_cleanup_directory_is_not_a_launcher_anchor(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            retired = base / ".trellis"
            # The launcher sits under a tree the predecessor RETIRED: a
            # cleanup outcome (after=absent) must never anchor it.
            bindings = _bindings(root, retired)
            target = base / "config.toml"
            target.write_bytes(codex_mcp_candidate(b"", [bindings]))
            operations = [
                {
                    "phase": "deploy",
                    "resource_id": "resource-1",
                    "target": str(target),
                    "selector": "graft-mcp",
                    "owner_kind": "toml",
                    "change": {"kind": "configure-graft", "source_ref": "policy"},
                    "dependent_projects": [str(root)],
                },
                {
                    "phase": "cleanup",
                    "resource_id": "resource-2",
                    "target": str(retired),
                    "selector": "whole-resource",
                    "owner_kind": "directory",
                    "change": {"kind": "remove", "source_ref": "policy"},
                    "dependent_projects": [str(root)],
                },
            ]
            results = {
                "deploy": {
                    "resource-1": {
                        "status": "succeeded",
                        "after": snapshot(target),
                    }
                },
                "cleanup": {
                    "resource-2": {
                        "status": "succeeded",
                        "after": {"type": "absent", "checksum": None},
                    }
                },
            }
            chain = [
                ({"payload": {"projects": [], "shared_operations": operations}},
                 results)
            ]
            self.assert_conflict(chain)

    def test_omp_host_appended_server_does_not_block(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            target = base / "mcp.json"
            document = {
                "mcpServers": {
                    "sbtd-graft": desired_omp_server(_bindings(root, base))
                }
            }
            target.write_text(json.dumps(document), encoding="utf-8")
            chain = _seal(target, "graft-omp-mcp", [root], owner="json")
            document["mcpServers"]["unrelated"] = {
                "type": "stdio",
                "command": "/usr/bin/true",
                "args": [],
            }
            target.write_text(json.dumps(document), encoding="utf-8")
            outcome = _check(chain)
            self.assertIn(str(target), outcome)

    def test_omp_global_receipt_without_projects_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            target = base / "mcp.json"
            document = {
                "mcpServers": {
                    "sbtd-graft": desired_omp_server(_bindings(base, base))
                }
            }
            target.write_text(json.dumps(document), encoding="utf-8")
            chain = _seal(target, "graft-omp-mcp", [], owner="json")
            outcome = _check(chain)
            self.assertIn(str(target), outcome)

    def test_omp_global_receipt_rejects_relative_runtime_paths(self):
        """R2: matching basenames cannot substitute for absolute ownership."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            target = base / "mcp.json"
            binding = {
                "python": str(base / "python"),
                "node": str(base / "node"),
                "cli": str(base / "runtime/cli.js"),
                "launcher": str(base / "installed/scripts/sbtd_graft_entry.py"),
            }
            original = json.dumps({
                "mcpServers": {"sbtd-graft": desired_omp_server(binding)}
            }).encode()
            target.write_bytes(original)
            chain = _seal(target, "graft-omp-mcp", [], owner="json")
            self.assertIn(str(target), _check(chain))
            for index in (2, 7):
                with self.subTest(argument=index):
                    document = json.loads(original)
                    args = document["mcpServers"]["sbtd-graft"]["args"]
                    args[index] = Path(args[index]).name
                    target.write_text(json.dumps(document), encoding="utf-8")
                    before = target.read_bytes()
                    self.assert_conflict(chain)
                    self.assertEqual(target.read_bytes(), before)

    def test_omp_historical_receipt_rejects_relative_runtime_paths(self):
        """The same absolute-path invariant also protects historical readers."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            target = base / "mcp.json"
            name = _legacy_server_key(root)
            original = json.dumps({
                "mcpServers": {name: _legacy_omp_record(root, base)}
            }).encode()
            target.write_bytes(original)
            chain = _seal(target, "graft-omp-mcp", [root], owner="json")
            self.assertIn(str(target), _check(chain))
            for index in (2, 9):
                with self.subTest(argument=index):
                    document = json.loads(original)
                    args = document["mcpServers"][name]["args"]
                    args[index] = Path(args[index]).name
                    target.write_text(json.dumps(document), encoding="utf-8")
                    before = target.read_bytes()
                    self.assert_conflict(chain)
                    self.assertEqual(target.read_bytes(), before)

    def test_omp_historical_fixed_root_receipt_still_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            target = base / "mcp.json"
            document = {
                "mcpServers": {
                    _legacy_server_key(root): _legacy_omp_record(root, base)
                }
            }
            target.write_text(json.dumps(document), encoding="utf-8")
            chain = _seal(target, "graft-omp-mcp", [root], owner="json")
            outcome = _check(chain)
            self.assertIn(str(target), outcome)
            document["mcpServers"][_legacy_server_key(root)]["args"][-1] = (
                "/fixture/other.js"
            )
            target.write_text(json.dumps(document), encoding="utf-8")
            self.assert_conflict(chain)

    def test_omp_managed_entry_tampering_still_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            target = base / "mcp.json"
            document = {
                "mcpServers": {
                    "sbtd-graft": desired_omp_server(_bindings(root, base))
                }
            }
            target.write_text(json.dumps(document), encoding="utf-8")
            chain = _seal(target, "graft-omp-mcp", [root], owner="json")
            document["mcpServers"]["sbtd-graft"]["args"][-1] = (
                "/fixture/other.js"
            )
            target.write_text(json.dumps(document), encoding="utf-8")
            self.assert_conflict(chain)

    def test_omp_disabled_managed_identity_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            target = base / "mcp.json"
            document = {
                "mcpServers": {
                    "sbtd-graft": desired_omp_server(_bindings(root, base))
                }
            }
            target.write_text(json.dumps(document), encoding="utf-8")
            chain = _seal(target, "graft-omp-mcp", [root], owner="json")
            document["disabledServers"] = ["sbtd-graft"]
            target.write_text(json.dumps(document), encoding="utf-8")
            self.assert_conflict(chain)

    def test_omp_malformed_enabled_flag_is_state_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            target = base / "mcp.json"
            document = {
                "mcpServers": {
                    "sbtd-graft": desired_omp_server(_bindings(root, base))
                }
            }
            target.write_text(json.dumps(document), encoding="utf-8")
            chain = _seal(target, "graft-omp-mcp", [root], owner="json")
            # A non-str/bool enabled flag is gate drift, not a usage error.
            document["mcpServers"]["sbtd-graft"]["enabled"] = 1
            target.write_text(json.dumps(document), encoding="utf-8")
            self.assert_conflict(chain)

    def test_omp_mixed_generations_block(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            target = base / "mcp.json"
            document = {
                "mcpServers": {
                    "sbtd-graft": desired_omp_server(_bindings(root, base))
                }
            }
            target.write_text(json.dumps(document), encoding="utf-8")
            chain = _seal(target, "graft-omp-mcp", [root], owner="json")
            # A retired fixed-root entry beside the global definition mixes
            # managed generations; the gate cannot prove which is drift.
            document["mcpServers"][_legacy_server_key(root)] = (
                _legacy_omp_record(root, base)
            )
            target.write_text(json.dumps(document), encoding="utf-8")
            self.assert_conflict(chain)

    def test_agents_user_text_outside_fence_does_not_block(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            target = base / "AGENTS.md"
            target.write_bytes(project_agents_candidate(b"# Project\n"))
            chain = _seal(target, "graft-agents", [root])
            target.write_bytes(
                target.read_bytes() + b"\nUser notes outside the fence.\n"
            )
            outcome = _check(chain)
            self.assertEqual(outcome[str(target)], snapshot(target))

    def test_agents_fence_tampering_still_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            target = base / "AGENTS.md"
            original = project_agents_candidate(b"# Project\n")

            target.write_bytes(original)
            chain = _seal(target, "graft-agents", [root])
            target.write_bytes(
                original.replace(
                    b"\n<!-- graft:end -->", b"\nedited\n<!-- graft:end -->"
                )
            )
            self.assert_conflict(chain)

            target.write_bytes(b"# Project with no fence at all\n")
            self.assert_conflict(chain)

            target.write_bytes(original + original)
            self.assert_conflict(chain)

    def _hooks(self, base, roots, package):
        target = base / "hooks.json"
        target.write_bytes(
            codex_hooks_candidate(
                b"",
                [_bindings(root, package) for root in roots],
                authorized=True,
            )
        )
        return target

    def test_hooks_unrelated_hook_does_not_block(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            package = self._package(base)
            target = self._hooks(base, [root], package)
            chain = _seal(target, "graft-hooks", [root], owner="json",
                          anchors=[package])
            document = json.loads(target.read_bytes())
            document["hooks"]["SessionStart"].append(
                {
                    "matcher": "startup",
                    "hooks": [
                        {"type": "command", "command": "/usr/bin/true", "timeout": 5}
                    ],
                }
            )
            # A managed-shaped hook for a root outside this batch is foreign.
            foreign = json.loads(
                codex_hooks_candidate(
                    b"", [_bindings(base / "other", package)], authorized=True
                )
            )
            document["hooks"]["SessionStart"].extend(
                foreign["hooks"]["SessionStart"]
            )
            target.write_text(json.dumps(document), encoding="utf-8")
            outcome = _check(chain)
            self.assertIn(str(target), outcome)

    def test_hooks_managed_command_tampering_still_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            package = self._package(base)
            target = self._hooks(base, [root], package)
            chain = _seal(target, "graft-hooks", [root], owner="json",
                          anchors=[package])
            changed = target.read_bytes().replace(
                b"/fixture/cli.js", b"/fixture/other.js", 1
            )
            self.assertNotEqual(changed, target.read_bytes())
            target.write_bytes(changed)
            self.assert_conflict(chain)

    def test_hooks_event_swap_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            package = self._package(base)
            target = self._hooks(base, [root], package)
            chain = _seal(target, "graft-hooks", [root], owner="json",
                          anchors=[package])
            document = json.loads(target.read_bytes())
            start = document["hooks"]["SessionStart"][0]["hooks"][0]["command"]
            prompt = document["hooks"]["UserPromptSubmit"][0]["hooks"][0][
                "command"
            ]
            document["hooks"]["SessionStart"][0]["hooks"][0]["command"] = prompt
            document["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"] = start
            target.write_text(json.dumps(document), encoding="utf-8")
            self.assert_conflict(chain)

    def test_hooks_noncanonical_quoting_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            package = self._package(base)
            target = self._hooks(base, [root], package)
            chain = _seal(target, "graft-hooks", [root], owner="json",
                          anchors=[package])
            # Same shlex.split argv, but not the canonical render: a shell
            # metachar payload could hide behind non-canonical quoting.
            changed = target.read_bytes().replace(
                b"/fixture/python -E -s", b"'/fixture/python' -E -s", 1
            )
            self.assertNotEqual(changed, target.read_bytes())
            target.write_bytes(changed)
            self.assert_conflict(chain)

    def test_hooks_managed_group_append_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            package = self._package(base)
            target = self._hooks(base, [root], package)
            chain = _seal(target, "graft-hooks", [root], owner="json",
                          anchors=[package])
            document = json.loads(target.read_bytes())
            document["hooks"]["Stop"][0]["hooks"].append(
                {"type": "command", "command": "/usr/bin/true", "timeout": 5}
            )
            target.write_text(json.dumps(document), encoding="utf-8")
            self.assert_conflict(chain)

    def test_non_configure_graft_drift_still_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            target = base / "notes.txt"
            target.write_bytes(b"original\n")
            chain = _seal(
                target, "whole-resource", [root],
                kind="ensure-file-block", owner="file",
            )
            outcome = _check(chain)
            self.assertIn(str(target), outcome)
            target.write_bytes(b"drifted\n")
            self.assert_conflict(chain)

    def test_unknown_configure_graft_selector_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            target = base / "config.toml"
            target.write_bytes(b"# anything\n")
            chain = _seal(target, "graft-unknown", [root], owner="toml")
            self.assert_conflict(chain)

    def test_renamed_python_interpreter_does_not_block(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            package = self._package(base)
            # The producer accepts any absolute interpreter; a pypy3-style
            # name must stay green after the seal-then-append sequence.
            bindings = _bindings(root, package)
            bindings["python"] = "/fixture/bin/pypy3"
            target = base / "config.toml"
            target.write_bytes(codex_mcp_candidate(b"", [bindings]))
            chain = _seal(target, "graft-mcp", [root], owner="toml",
                          anchors=[package])
            target.write_bytes(
                target.read_bytes() + b'\n[desktop]\nnotifications = false\n'
            )
            outcome = _check(chain)
            self.assertEqual(outcome[str(target)], snapshot(target))

    def test_overwritten_anchor_tree_still_anchors_launcher(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "project"
            package = self._package(base)
            target = self._codex_config(base, [root], package)
            chain = _seal(target, "graft-mcp", [root], owner="toml",
                          anchors=[package])
            # The apply-time path overwrites the anchor tree (shared skills
            # dir); containment must not depend on the overwrite exemption.
            outcome = _check_followup_predecessor_outcomes(
                chain, overwritten={str(package)}
            )
            self.assertEqual(outcome[str(target)], snapshot(target))


if __name__ == "__main__":
    unittest.main()
