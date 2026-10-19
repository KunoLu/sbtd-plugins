from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard/scripts"
sys.path.insert(0, str(SCRIPTS))


class CodexCandidateTests(unittest.TestCase):
    def binding(self, base):
        return {
            name: str(base / value)
            for name, value in {
                "root": "project",
                "node": "runtime/node",
                "cli": "package/dist/cli.js",
                "python": "runtime/python",
                "launcher": "installed/scripts/sbtd_graft_entry.py",
            }.items()
        }

    def test_hooks_require_authorization_and_preserve_every_foreign_handler(self):
        from sbtd_codex_wiring import codex_hooks_candidate

        with tempfile.TemporaryDirectory() as directory:
            binding = self.binding(Path(directory).resolve())
            original = b'{"description":"user-owned","hooks":{"UserPromptSubmit":[{"hooks":[{"type":"command","command":"echo keep-prompt","timeout":5}]}],"Stop":[{"hooks":[{"type":"command","command":"echo keep-stop","timeout":5}]}]}}\n'
            self.assertEqual(
                codex_hooks_candidate(original, [binding], authorized=False), original
            )
            rendered = codex_hooks_candidate(original, [binding], authorized=True)
            parsed = json.loads(rendered)
            self.assertEqual(parsed["description"], "user-owned")
            for event, command in (
                ("UserPromptSubmit", "echo keep-prompt"),
                ("Stop", "echo keep-stop"),
            ):
                commands = [
                    handler["command"]
                    for group in parsed["hooks"][event]
                    for handler in group["hooks"]
                ]
                self.assertEqual(commands.count(command), 1)
            self.assertEqual(
                codex_hooks_candidate(rendered, [binding], authorized=True), rendered
            )
            self.assertNotIn("trusted_hash", rendered.decode())

    def test_malformed_foreign_hook_containers_block_without_rewriting(self):
        from onboard_contracts import ContractError
        from sbtd_codex_wiring import codex_hooks_candidate

        with tempfile.TemporaryDirectory() as directory:
            binding = self.binding(Path(directory).resolve())
            for malformed in (
                b'{"hooks":{"Stop":[null]}}',
                b'{"hooks":{"Stop":[{"hooks":null}]}}',
                b'{"hooks":{"Stop":[{"hooks":[null]}]}}',
            ):
                with self.subTest(malformed=malformed), self.assertRaises(
                    ContractError
                ) as failure:
                    codex_hooks_candidate(malformed, [binding], authorized=True)
                self.assertEqual(failure.exception.code, "invalid-config")

    def test_foreign_hook_group_may_omit_empty_hooks(self):
        from sbtd_codex_wiring import codex_hooks_candidate

        with tempfile.TemporaryDirectory() as directory:
            binding = self.binding(Path(directory).resolve())
            rendered = json.loads(
                codex_hooks_candidate(
                    b'{"hooks":{"Stop":[{"matcher":"foreign"}]}}',
                    [binding],
                    authorized=True,
                )
            )
            self.assertEqual(rendered["hooks"]["Stop"][0], {"matcher": "foreign"})


    def test_session_start_includes_pinned_clear_event(self):
        from sbtd_codex_wiring import codex_hooks_candidate

        with tempfile.TemporaryDirectory() as directory:
            binding = self.binding(Path(directory).resolve())
            rendered = json.loads(
                codex_hooks_candidate(b"", [binding], authorized=True)
            )
            self.assertEqual(
                rendered["hooks"]["SessionStart"][0]["matcher"],
                "startup|resume|clear|compact",
            )

    def test_session_start_matcher_updates_singleton_group_in_place(self):
        from sbtd_codex_wiring import codex_hooks_candidate

        with tempfile.TemporaryDirectory() as directory:
            binding = self.binding(Path(directory).resolve())
            document = json.loads(
                codex_hooks_candidate(b"", [binding], authorized=True)
            )
            groups = document["hooks"]["SessionStart"]
            groups[0]["matcher"] = "startup|resume|compact"
            foreign = {"matcher": "foreign", "hooks": []}
            groups.append(foreign)
            rendered = json.loads(
                codex_hooks_candidate(
                    json.dumps(document).encode(), [binding], authorized=True
                )
            )
            self.assertEqual(
                rendered["hooks"]["SessionStart"][0]["matcher"],
                "startup|resume|clear|compact",
            )
            self.assertEqual(rendered["hooks"]["SessionStart"][1], foreign)


    def test_modified_managed_executable_paths_are_not_silently_replaced(self):
        import sbtd_codex_wiring as wiring
        from onboard_contracts import ContractError

        with tempfile.TemporaryDirectory() as directory:
            binding = self.binding(Path(directory).resolve())
            # POSIX dialect, pinned so the shlex round-trip below is truthful
            # on any host; the Windows dialect has its own variant.
            with mock.patch.object(wiring, "_WINDOWS", False):
                original = wiring.codex_hooks_candidate(b"", [binding], authorized=True)
                for boundary in ("python", "--node", "--entry"):
                    document = json.loads(original)
                    handler = document["hooks"]["UserPromptSubmit"][0]["hooks"][0]
                    arguments = shlex.split(handler["command"])
                    position = (
                        0 if boundary == "python" else arguments.index(boundary) + 1
                    )
                    arguments[position] = str(
                        Path(directory) / "user-modified-executable"
                    )
                    handler["command"] = shlex.join(arguments)
                    changed = json.dumps(document).encode()
                    with (
                        self.subTest(boundary=boundary),
                        self.assertRaises(ContractError),
                    ):
                        wiring.codex_hooks_candidate(
                            changed, [binding], authorized=True
                        )

    def test_pre_hardening_owned_hook_is_not_preserved_as_foreign(self):
        import sbtd_codex_wiring as wiring
        from onboard_contracts import ContractError

        with tempfile.TemporaryDirectory() as directory:
            binding = self.binding(Path(directory).resolve())
            with mock.patch.object(wiring, "_WINDOWS", False):
                original = wiring.codex_hooks_candidate(b"", [binding], authorized=True)
                document = json.loads(original)
                handler = document["hooks"]["SessionStart"][0]["hooks"][0]
                arguments = shlex.split(handler["command"])
                del arguments[1:3]
                handler["command"] = shlex.join(arguments)
                previous = json.dumps(document).encode()
                self.assertEqual(
                    wiring.codex_hooks_candidate(previous, [binding], authorized=False),
                    previous,
                )
                with self.assertRaises(ContractError) as failure:
                    wiring.codex_hooks_candidate(previous, [binding], authorized=True)
                self.assertEqual(failure.exception.code, "ownership-conflict")

    def test_mixed_managed_hook_group_requires_explicit_reconciliation(self):
        from onboard_contracts import ContractError
        from sbtd_codex_wiring import codex_hooks_candidate

        with tempfile.TemporaryDirectory() as directory:
            binding = self.binding(Path(directory).resolve())
            document = json.loads(
                codex_hooks_candidate(b"", [binding], authorized=True)
            )
            document["hooks"]["SessionStart"][0]["hooks"].append(
                {"type": "command", "command": "echo foreign", "timeout": 5}
            )
            with self.assertRaises(ContractError) as failure:
                codex_hooks_candidate(
                    json.dumps(document).encode(), [binding], authorized=True
                )
            self.assertEqual(failure.exception.code, "ownership-conflict")

    def test_duplicate_managed_hook_requires_explicit_reconciliation(self):
        from onboard_contracts import ContractError
        from sbtd_codex_wiring import codex_hooks_candidate

        with tempfile.TemporaryDirectory() as directory:
            binding = self.binding(Path(directory).resolve())
            document = json.loads(
                codex_hooks_candidate(b"", [binding], authorized=True)
            )
            document["hooks"]["SessionStart"].append(
                document["hooks"]["SessionStart"][0].copy()
            )
            with self.assertRaises(ContractError) as failure:
                codex_hooks_candidate(
                    json.dumps(document).encode(), [binding], authorized=True
                )
            self.assertEqual(failure.exception.code, "ownership-conflict")


    def test_agents_fence_update_preserves_non_owned_bytes(self):
        from onboard_contracts import ContractError
        from sbtd_codex_wiring import project_agents_candidate

        original = b"# User instructions\r\nKeep this spacing.  \r\n<!-- graft:start -->\nOld instructions.\n<!-- graft:end -->\r\n\nUser suffix.\n"
        candidate = project_agents_candidate(original)
        self.assertTrue(
            candidate.startswith(b"# User instructions\r\nKeep this spacing.  \r\n")
        )
        self.assertTrue(candidate.endswith(b"\r\n\nUser suffix.\n"))
        self.assertNotIn(b"Old instructions.", candidate)
        self.assertEqual(project_agents_candidate(candidate), candidate)
        with self.assertRaises(ContractError):
            project_agents_candidate(original + b"<!-- graft:start -->broken")

    def test_authorized_template_replaces_malformed_agents_before_fencing(self):
        from sbtd_graft_deployment import render_configuration

        candidate = render_configuration(
            {"selector": "graft-agents"},
            b"\xff<!-- graft:start -->obsolete",
            [],
            install_template=True,
        )
        self.assertNotIn(b"\xff", candidate)
        self.assertEqual(candidate.count(b"<!-- graft:start -->"), 1)


    @staticmethod
    def _legacy_toml(root, runtime):
        import hashlib

        key = "sbtd-graft-" + hashlib.sha256(
            root.encode("utf-8")
        ).hexdigest()[:16]
        args = [
            "-E", "-s", runtime["launcher"], "mcp", "--root", root,
            "--node", runtime["node"], "--entry", runtime["cli"],
        ]
        return (
            f"[mcp_servers.{key}]\n"
            f'command = {json.dumps(runtime["python"])}\n'
            f"args = {json.dumps(args)}\n"
            f'cwd = {json.dumps(root)}\n'
            f"[mcp_servers.{key}.env]\n"
            'DO_NOT_TRACK = "1"\nDNT = "1"\n'
        )

    def test_mcp_global_definition_is_single_rootless_and_preserves_foreign_toml(
        self,
    ):
        import tomlkit
        from sbtd_codex_wiring import codex_mcp_candidate

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            first = self.binding(base)
            second = {**first, "root": str(base / "two")}
            original = b'# User comment\nmodel = "user-model"\n\n[mcp_servers.foreign]\ncommand = "keep-me" # preserve this comment\n'
            candidate = codex_mcp_candidate(original, [first, second])
            parsed = tomlkit.parse(candidate.decode())
            self.assertEqual(parsed["model"], "user-model")
            self.assertEqual(parsed["mcp_servers"]["foreign"]["command"], "keep-me")
            self.assertIn(b"# User comment", candidate)
            self.assertIn(b"# preserve this comment", candidate)
            self.assertEqual(set(parsed["mcp_servers"]), {"foreign", "sbtd-graft"})
            server = parsed["mcp_servers"]["sbtd-graft"]
            self.assertEqual(server["command"], first["python"])
            self.assertEqual(
                list(server["args"]),
                [
                    "-E", "-s", first["launcher"], "mcp",
                    "--node", first["node"], "--entry", first["cli"],
                ],
            )
            self.assertNotIn("cwd", server)
            self.assertEqual(dict(server["env"]), {"DO_NOT_TRACK": "1", "DNT": "1"})
            # One runtime carries every project: batch and later append
            # render the identical single definition, never a second entry.
            self.assertEqual(codex_mcp_candidate(original, [first]), candidate)
            self.assertEqual(
                codex_mcp_candidate(candidate, [first, second]), candidate
            )

    def test_mcp_rootless_binding_renders_and_empty_batch_keeps_bytes(self):
        import tomlkit
        from sbtd_codex_wiring import codex_mcp_candidate

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            binding = self.binding(base)
            rootless = {
                key: value for key, value in binding.items() if key != "root"
            }
            original = b'model = "user-model"\n'
            rendered = codex_mcp_candidate(original, [rootless])
            server = tomlkit.parse(rendered.decode())["mcp_servers"]["sbtd-graft"]
            self.assertEqual(server["command"], binding["python"])
            self.assertNotIn("cwd", server)
            self.assertEqual(codex_mcp_candidate(original, []), original)

    def test_mcp_batch_with_two_runtimes_is_refused(self):
        from onboard_contracts import ContractError
        from sbtd_codex_wiring import codex_mcp_candidate

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            with self.assertRaises(ContractError) as failure:
                codex_mcp_candidate(
                    b"", [self.binding(base / "one"), self.binding(base / "two")]
                )
            self.assertEqual(failure.exception.code, "invalid-argument")

    def test_retired_fixed_root_entry_conflicts_without_explicit_retirement(self):
        from onboard_contracts import ContractError
        from sbtd_codex_wiring import codex_mcp_candidate

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            binding = self.binding(base)
            document = self._legacy_toml(binding["root"], binding).encode()
            with self.assertRaises(ContractError) as failure:
                codex_mcp_candidate(document, [binding])
            self.assertEqual(failure.exception.code, "ownership-conflict")
            # Authorization scoped to a different root cannot claim it.
            other = {**binding, "root": str(base / "other")}
            with self.assertRaises(ContractError) as failure:
                codex_mcp_candidate(document, [other], retire_legacy=True)
            self.assertEqual(failure.exception.code, "ownership-conflict")

    def test_authorized_retirement_replaces_only_the_proven_entry(self):
        import tomlkit
        from sbtd_codex_wiring import codex_mcp_candidate

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            binding = self.binding(base)
            original = b'# User comment\n[mcp_servers.foreign]\ncommand = "keep-me" # note\n'
            document = (
                original.decode() + "\n" + self._legacy_toml(binding["root"], binding)
            ).encode()
            switched = codex_mcp_candidate(document, [binding], retire_legacy=True)
            parsed = tomlkit.parse(switched.decode())
            self.assertEqual(set(parsed["mcp_servers"]), {"foreign", "sbtd-graft"})
            server = parsed["mcp_servers"]["sbtd-graft"]
            self.assertEqual(server["command"], binding["python"])
            self.assertNotIn("cwd", server)
            self.assertIn(b"# User comment", switched)
            self.assertIn(b"# note", switched)
            self.assertEqual(parsed["mcp_servers"]["foreign"]["command"], "keep-me")
            self.assertEqual(
                codex_mcp_candidate(switched, [binding], retire_legacy=True),
                switched,
            )

    def test_discontiguous_tables_retire_only_owned_server_and_preserve_comments(self):
        import tomlkit
        from sbtd_codex_wiring import codex_mcp_candidate

        with tempfile.TemporaryDirectory() as directory:
            binding = self.binding(Path(directory).resolve())
            legacy_head, legacy_env = self._legacy_toml(
                binding["root"], binding
            ).split("\n[mcp_servers.", 1)
            foreign = '# Foreign server\n[mcp_servers.foreign]\ncommand = "keep-me" # keep note\n'
            features = '\n[features]\nshell_tool = false # user choice\n'
            provider = '\n[model_providers.local]\nname = "local-provider" # retain provider\n'
            second = '\n[mcp_servers.second]\ncommand = "another-tool"\n'
            original = (
                foreign + legacy_head + features
                + "\n[mcp_servers." + legacy_env + provider + second
            ).encode()

            candidate = codex_mcp_candidate(
                original, [binding], retire_legacy=True
            )
            parsed = tomlkit.parse(candidate.decode()).unwrap()
            self.assertEqual(
                set(parsed["mcp_servers"]), {"foreign", "second", "sbtd-graft"}
            )
            self.assertEqual(parsed["mcp_servers"]["foreign"], {"command": "keep-me"})
            self.assertEqual(parsed["mcp_servers"]["second"], {"command": "another-tool"})
            self.assertEqual(parsed["features"], {"shell_tool": False})
            self.assertEqual(parsed["model_providers"]["local"], {"name": "local-provider"})
            for block in (foreign, features, provider, second):
                self.assertIn(block.encode(), candidate)
            self.assertNotIn("cwd", parsed["mcp_servers"]["sbtd-graft"])
            self.assertEqual(
                codex_mcp_candidate(candidate, [binding], retire_legacy=True),
                candidate,
            )

    def test_discontiguous_existing_global_server_is_byte_idempotent(self):
        from sbtd_codex_wiring import codex_mcp_candidate

        with tempfile.TemporaryDirectory() as directory:
            binding = self.binding(Path(directory).resolve())
            args = [
                "-E", "-s", binding["launcher"], "mcp",
                "--node", binding["node"], "--entry", binding["cli"],
            ]
            original = (
                "[mcp_servers.sbtd-graft]\n"
                f'command = {json.dumps(binding["python"])}\n'
                f"args = {json.dumps(args)}\n"
                '\n[features]\nshell_tool = false # preserve\n'
                '\n[mcp_servers.sbtd-graft.env]\nDNT = "1"\nDO_NOT_TRACK = "1"\n'
                '\n[mcp_servers.foreign]\ncommand = "keep-me"\n'
            ).encode()
            self.assertEqual(codex_mcp_candidate(original, [binding]), original)

    def test_discontiguous_tables_keep_retirement_ownership_checks(self):
        from onboard_contracts import ContractError
        from sbtd_codex_wiring import codex_mcp_candidate

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            binding = self.binding(base)
            legacy_head, legacy_env = self._legacy_toml(
                binding["root"], binding
            ).split("\n[mcp_servers.", 1)
            middle = '\n[features]\nshell_tool = false\n'
            ending = "\n[mcp_servers." + legacy_env
            original = (legacy_head + middle + ending).encode()
            customized = (legacy_head + "\ntimeout = 60" + middle + ending).encode()
            cases = (
                ("no authorization", original, binding, False, "ownership-conflict"),
                ("different root", original, {**binding, "root": str(base / "other")}, True, "ownership-conflict"),
                ("different runtime", original, {**binding, "node": str(base / "other/node")}, True, "ownership-conflict"),
                ("custom old entry", customized, binding, True, "ownership-conflict"),
                ("inline root", b'mcp_servers = { foreign = { command = "keep-me" } }\n', binding, True, "invalid-config"),
            )
            for label, content, selected, authorized, expected in cases:
                with self.subTest(label=label), self.assertRaises(ContractError) as failure:
                    codex_mcp_candidate(
                        content, [selected], retire_legacy=authorized
                    )
                self.assertEqual(failure.exception.code, expected)

    def test_authorized_retirement_of_an_observed_legacy_runtime_contract(self):
        import tomlkit
        from onboard_contracts import ContractError
        from sbtd_codex_wiring import codex_mcp_candidate

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            binding = self.binding(base)
            legacy_runtime = {
                "node": str(base / "old-runtime/node"),
                "cli": str(base / "old-package/dist/cli.js"),
                "python": str(base / "old-runtime/python"),
                "launcher": str(base / "old-deploy/scripts/sbtd_graft_entry.py"),
            }
            document = self._legacy_toml(binding["root"], legacy_runtime).encode()
            # A different old runtime without the observed contract: refused.
            with self.assertRaises(ContractError) as failure:
                codex_mcp_candidate(document, [binding], retire_legacy=True)
            self.assertEqual(failure.exception.code, "ownership-conflict")
            # A contract that does not match the observed old runtime: refused.
            wrong = {
                **binding,
                "legacy": {**legacy_runtime, "node": str(base / "other/node")},
            }
            with self.assertRaises(ContractError) as failure:
                codex_mcp_candidate(document, [wrong], retire_legacy=True)
            self.assertEqual(failure.exception.code, "ownership-conflict")
            # The exact observed contract retires the entry onto the new
            # runtime: the TEMP-runtime migration path.
            contracted = {**binding, "legacy": legacy_runtime}
            switched = codex_mcp_candidate(
                document, [contracted], retire_legacy=True
            )
            parsed = tomlkit.parse(switched.decode())
            self.assertEqual(set(parsed["mcp_servers"]), {"sbtd-graft"})
            server = parsed["mcp_servers"]["sbtd-graft"]
            self.assertEqual(server["command"], binding["python"])
            self.assertEqual(server["args"][2], binding["launcher"])

    def test_unknown_graft_prefixed_entry_is_never_retired_by_prefix(self):
        from onboard_contracts import ContractError
        from sbtd_codex_wiring import codex_mcp_candidate

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            binding = self.binding(base)
            unknown = b'[mcp_servers.sbtd-graft-mine]\ncommand = "/usr/bin/true"\n'
            with self.assertRaises(ContractError) as failure:
                codex_mcp_candidate(unknown, [binding], retire_legacy=True)
            self.assertEqual(failure.exception.code, "ownership-conflict")
            # A hash-keyed entry missing the managed env is likewise unknown.
            import hashlib

            key = "sbtd-graft-" + hashlib.sha256(
                binding["root"].encode("utf-8")
            ).hexdigest()[:16]
            reshaped = (
                f"[mcp_servers.{key}]\n"
                f'command = "{binding["python"]}"\n'
                f'args = {json.dumps(["-E", "-s", binding["launcher"], "mcp", "--root", binding["root"], "--node", binding["node"], "--entry", binding["cli"]])}\n'
                f'cwd = "{binding["root"]}"\n'
            ).encode()
            with self.assertRaises(ContractError) as failure:
                codex_mcp_candidate(reshaped, [binding], retire_legacy=True)
            self.assertEqual(failure.exception.code, "ownership-conflict")

    def test_existing_different_global_entry_is_not_overwritten(self):
        from onboard_contracts import ContractError
        from sbtd_codex_wiring import codex_mcp_candidate

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            document = codex_mcp_candidate(b"", [self.binding(base / "elsewhere")])
            with self.assertRaises(ContractError) as failure:
                codex_mcp_candidate(document, [self.binding(base)])
            self.assertEqual(failure.exception.code, "ownership-conflict")

    def test_stop_hook_timeout_outlasts_the_native_sync_cap(self):
        from sbtd_codex_wiring import codex_hooks_candidate

        with tempfile.TemporaryDirectory() as directory:
            binding = self.binding(Path(directory).resolve())
            parsed = json.loads(codex_hooks_candidate(b"", [binding], authorized=True))
            # Native sync may consume its full 120-second cap; the host must
            # leave time for the managed launcher to observe and clean it up.
            self.assertGreater(parsed["hooks"]["Stop"][0]["hooks"][0]["timeout"], 120)

    def test_windows_hook_command_round_trips_argv_and_stays_idempotent(self):
        import sbtd_codex_wiring as wiring

        with tempfile.TemporaryDirectory() as directory:
            binding = self.binding(Path(directory).resolve() / "root with spaces")
            original = (
                b'{"description":"user-owned","hooks":{"Stop":[{"hooks":'
                b'[{"type":"command","command":"echo keep & echo both","timeout":5}]}]}}\n'
            )
            with mock.patch.object(wiring, "_WINDOWS", True):
                rendered = wiring.codex_hooks_candidate(
                    original, [binding], authorized=True
                )
                parsed = json.loads(rendered)
                groups = parsed["hooks"]["Stop"]
                owned = [
                    handler["command"]
                    for group in groups
                    for handler in group["hooks"]
                    if handler["command"] != "echo keep & echo both"
                ]
                self.assertEqual(len(owned), 1)
                self.assertNotIn("'", owned[0])
                self.assertIn('"', owned[0])
                # The foreign handler — metacharacters and all — is preserved.
                self.assertEqual(
                    [h["command"] for g in groups for h in g["hooks"]].count(
                        "echo keep & echo both"
                    ),
                    1,
                )
                self.assertEqual(parsed["description"], "user-owned")
                self.assertEqual(
                    wiring.codex_hooks_candidate(rendered, [binding], authorized=True),
                    rendered,
                )

    def test_windows_foreign_owned_shaped_command_is_never_claimed_or_refused(self):
        import sbtd_codex_wiring as wiring

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            binding = self.binding(base)
            foreign_argv = [
                binding["python"],
                "-E",
                "-s",
                binding["launcher"],
                "hook",
                "--root",
                str(base / "foreign&%!root project"),
                "--node",
                binding["node"],
                "--entry",
                binding["cli"],
                "--event",
                "stop",
            ]
            foreign_command = subprocess.list2cmdline(foreign_argv)
            original = json.dumps(
                {
                    "hooks": {
                        "Stop": [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": foreign_command,
                                        "timeout": 5,
                                    }
                                ]
                            }
                        ]
                    }
                }
            ).encode()
            with mock.patch.object(wiring, "_WINDOWS", True):
                rendered = wiring.codex_hooks_candidate(
                    original, [binding], authorized=True
                )
                commands = [
                    handler["command"]
                    for group in json.loads(rendered)["hooks"]["Stop"]
                    for handler in group["hooks"]
                ]
                # Same launcher shape but a different root: strictly foreign —
                # preserved verbatim, never refused for its metacharacters and
                # never reconciled into the managed entry.
                self.assertEqual(commands.count(foreign_command), 1)
                self.assertEqual(len(commands), 2)

    def test_windows_paths_with_live_cmd_operators_are_refused(self):
        import sbtd_codex_wiring as wiring
        from onboard_contracts import ContractError

        unsafe = {
            "root": "unsafe&command",
            "python": "%COMSPEC%",
            "launcher": "unsafe!expanded!",
            "node": "unsafe|command",
            "cli": "unsafe\ncommand",
        }
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            for key, value in unsafe.items():
                binding = self.binding(base)
                binding[key] = str(base / value)
                with self.subTest(key=key), mock.patch.object(wiring, "_WINDOWS", True):
                    with self.assertRaises(ContractError) as failure:
                        wiring.codex_hooks_candidate(b"", [binding], authorized=True)
                    self.assertEqual(failure.exception.code, "invalid-argument")
            # POSIX rendering is unchanged: the same path is safely quoted,
            # not refused (dialect pinned so this is truthful on any host).
            binding = self.binding(base)
            binding["root"] = str(base / "unsafe&segment")
            with mock.patch.object(wiring, "_WINDOWS", False):
                rendered = wiring.codex_hooks_candidate(b"", [binding], authorized=True)
            command = json.loads(rendered)["hooks"]["Stop"][0]["hooks"][0]["command"]
            self.assertIn("'", command)
            arguments = shlex.split(command)
            self.assertEqual(arguments[arguments.index("--root") + 1], binding["root"])

    def test_windows_modified_managed_executable_paths_are_not_silently_replaced(self):
        import sbtd_codex_wiring as wiring
        from onboard_contracts import ContractError

        with tempfile.TemporaryDirectory() as directory:
            binding = self.binding(Path(directory).resolve())
            with mock.patch.object(wiring, "_WINDOWS", True):
                original = wiring.codex_hooks_candidate(b"", [binding], authorized=True)
                for boundary in ("python", "--node", "--entry"):
                    document = json.loads(original)
                    handler = document["hooks"]["UserPromptSubmit"][0]["hooks"][0]
                    arguments = wiring._split_hook_command(handler["command"])
                    position = (
                        0 if boundary == "python" else arguments.index(boundary) + 1
                    )
                    arguments[position] = str(
                        Path(directory) / "user-modified-executable"
                    )
                    handler["command"] = subprocess.list2cmdline(arguments)
                    changed = json.dumps(document).encode()
                    with (
                        self.subTest(boundary=boundary),
                        self.assertRaises(ContractError),
                    ):
                        wiring.codex_hooks_candidate(
                            changed, [binding], authorized=True
                        )

    def test_rendered_commands_ignore_caller_python_startup_environment(self):
        import sbtd_codex_wiring as wiring
        import tomlkit

        if os.name == "nt":
            self.skipTest("POSIX host-shell execution probe")
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            hostile = base / "hostile-pythonpath"
            hostile.mkdir()
            sentinels = base / "sentinels"
            sentinels.mkdir()
            # Caller-controlled startup injection: the json.py shadow would
            # execute on the guard's own stdlib imports, the sitecustomize
            # hook at interpreter startup — but only if PYTHONPATH were
            # honored.
            for name in ("json.py", "sitecustomize.py"):
                (hostile / name).write_text(
                    "import os\n"
                    "open(os.path.join(os.environ['P104_SENTINELS'], "
                    + repr(name)
                    + "), 'w').write('ran')\n",
                    encoding="utf-8",
                )
            trusted = base / "trusted"
            trusted.mkdir()
            (trusted / "trusted_sibling.py").write_text(
                "MARKER = 'sibling-import-ok'\n", encoding="utf-8"
            )
            # Startup-boundary double only: it records how the interpreter
            # launched it. It is not the real guard launcher and proves
            # nothing about native Graft.
            (trusted / "fake_launcher.py").write_text(
                "import json, os, sys\n"
                "import trusted_sibling\n"
                "json.dump("
                "{'argv': sys.argv[1:], 'json_module': json.__file__, "
                "'cwd': os.getcwd(), 'sibling': trusted_sibling.MARKER}, "
                "open(os.environ['P104_RESULT'], 'w'))\n",
                encoding="utf-8",
            )
            binding = self.binding(base)
            binding["python"] = sys.executable
            binding["launcher"] = str(trusted / "fake_launcher.py")
            result = base / "result.json"
            env = {
                "PYTHONPATH": str(hostile),
                "PYTHONHOME": str(base / "not-a-python-home"),
                "P104_RESULT": str(result),
                "P104_SENTINELS": str(sentinels),
            }

            def observe():
                observed = json.loads(result.read_text(encoding="utf-8"))
                # The launcher's script directory stays importable under
                # -E -s (unlike -I), so trusted siblings still load…
                self.assertEqual(observed["sibling"], "sibling-import-ok")
                # …while the PYTHONPATH shadow never became json.
                self.assertNotIn(str(hostile), observed["json_module"])
                self.assertEqual(list(sentinels.iterdir()), [])
                return observed["argv"]
            # MCP form: exactly the argv Codex spawns — command plus args.
            # The global definition carries no --root; the host-selected
            # process cwd alone binds the connection's project.
            (base / "project").mkdir()
            mcp_candidate = wiring.codex_mcp_candidate(b"", [binding])
            servers = tomlkit.parse(mcp_candidate.decode())["mcp_servers"]
            server = next(iter(servers.values()))
            completed = subprocess.run(
                [server["command"], *server["args"]],
                env=env,
                cwd=binding["root"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                observe(),
                [
                    "mcp",
                    "--node",
                    binding["node"],
                    "--entry",
                    binding["cli"],
                ],
            )
            observed = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(Path(observed["cwd"]), Path(binding["root"]))

            # Hook form: Codex 0.154 runs hook commands through the host
            # shell ($SHELL -lc); /bin/sh -c exercises the same rendered
            # POSIX quoting dialect without login-profile noise.
            hooks = json.loads(
                wiring.codex_hooks_candidate(b"", [binding], authorized=True)
            )
            command = hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"]
            result.unlink()
            completed = subprocess.run(
                ["/bin/sh", "-c", command],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                observe(),
                [
                    "hook",
                    "--root",
                    binding["root"],
                    "--node",
                    binding["node"],
                    "--entry",
                    binding["cli"],
                    "--event",
                    "session-start",
                ],
            )


if __name__ == "__main__":
    unittest.main()
