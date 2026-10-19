from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard/scripts"
sys.path.insert(0, str(SCRIPTS))

from onboard_contracts import ContractError
from sbtd_omp_sources import analyze_omp_sources
from sbtd_omp_wiring import (
    analyze_omp_configuration,
    desired_omp_server,
    omp_mcp_candidate,
)

BINDING = {
    "root": "/private/project",
    "node": "/private/node",
    "cli": "/private/graft/dist/cli.js",
    "python": "/private/python",
    "launcher": "/private/onboard/scripts/sbtd_graft_entry.py",
}


class OmpMcpCandidateTests(unittest.TestCase):
    def test_inherited_equivalent_connection_is_idempotent_without_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            desired = {
                "type": "stdio",
                "command": BINDING["python"],
                "args": [
                    "-E",
                    "-s",
                    BINDING["launcher"],
                    "mcp",
                    "--node",
                    BINDING["node"],
                    "--entry",
                    BINDING["cli"],
                ],
                "env": {"DO_NOT_TRACK": "1", "DNT": "1"},
            }
            inherited = base / ".codex/config.toml"
            inherited.parent.mkdir(parents=True)
            inherited.write_text(
                "[mcp_servers.sbtd-graft]\n"
                f'command = "{desired["command"]}"\n'
                "args = " + json.dumps(desired["args"]) + "\n"
                '[mcp_servers.sbtd-graft.env]\nDO_NOT_TRACK = "1"\nDNT = "1"\n',
                encoding="utf-8",
            )
            target = base / ".omp/mcp.json"
            target.parent.mkdir(parents=True)
            target.write_text('{"mcpServers": {}}\n', encoding="utf-8")
            analysis = analyze_omp_configuration(
                target,
                [BINDING],
                [
                    {
                        "source": "codex-user",
                        "enabled": True,
                        "servers": {"sbtd-graft": desired},
                    }
                ],
            )
            candidate = omp_mcp_candidate(target.read_bytes(), analysis)
            self.assertEqual(candidate, target.read_bytes())
            self.assertEqual(analysis["writes"], [])
            self.assertEqual(len(analysis["inherited_matches"]), 1)

    def test_project_disabled_source_blocks_without_rewriting_target(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            target = base / ".omp/mcp.json"
            before = b'{"mcpServers": {}}\n'
            target.parent.mkdir(parents=True)
            target.write_bytes(before)
            with self.assertRaises(ContractError) as failure:
                analyze_omp_configuration(
                    target,
                    [BINDING],
                    [
                        {
                            "source": "codex-project",
                            "enabled": False,
                            "servers": {"sbtd-graft": {"command": "/foreign"}},
                        }
                    ],
                )
            self.assertEqual(failure.exception.code, "ownership-conflict")
            self.assertEqual(target.read_bytes(), before)

    def test_malformed_or_dynamic_configuration_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            for index, raw in enumerate(
                (
                    b'{"mcpServers":}',
                    b'{"mcpServers": {"sbtd-graft": "not-object"}}',
                    b'{"mcpServers": {"sbtd-graft": {"command": "${SBTD_LAUNCHER}"}}}',
                    b'{"mcpServers": {"sbtd-graft": {"command": "prefix-${HOME}/launcher"}}}',
                    b'{"mcpServers": {"foreign": "not-object"}}',
                )
            ):
                target = base / str(index) / ".omp/mcp.json"
                target.parent.mkdir(parents=True)
                target.write_bytes(raw)
                before = {
                    str(path.relative_to(base)): path.read_bytes()
                    for path in base.rglob("*")
                    if path.is_file()
                }
                with self.subTest(index=index), self.assertRaises(ContractError):
                    analyze_omp_configuration(target, [BINDING], [])
                after = {
                    str(path.relative_to(base)): path.read_bytes()
                    for path in base.rglob("*")
                    if path.is_file()
                }
                self.assertEqual(after, before)

    def test_candidate_rechecks_the_active_disabled_server_denylist(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "mcp.json"
            analysis = analyze_omp_configuration(target, [BINDING], [])
            name = analysis["writes"][0]["name"]
            before = json.dumps({"mcpServers": {}, "disabledServers": [name]}).encode(
                "utf-8"
            )
            with self.assertRaises(ContractError) as failure:
                omp_mcp_candidate(before, analysis)
            self.assertEqual(failure.exception.code, "ownership-conflict")

    @staticmethod
    def _legacy_record(root, runtime):
        return {
            "type": "stdio",
            "command": runtime["python"],
            "args": [
                "-E", "-s", runtime["launcher"], "mcp", "--root", root,
                "--node", runtime["node"], "--entry", runtime["cli"],
            ],
            "cwd": root,
            "env": {"DO_NOT_TRACK": "1", "DNT": "1"},
        }

    @staticmethod
    def _legacy_name(root):
        import hashlib

        return "sbtd-graft-" + hashlib.sha256(
            root.encode("utf-8")
        ).hexdigest()[:16]

    def test_global_definition_is_single_rootless_and_batch_equals_append(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "mcp.json"
            rootless = {key: value for key, value in BINDING.items() if key != "root"}
            analysis = analyze_omp_configuration(target, [rootless], [])
            self.assertEqual(analysis["removals"], [])
            self.assertEqual(len(analysis["writes"]), 1)
            write = analysis["writes"][0]
            self.assertEqual(write["name"], "sbtd-graft")
            server = write["server"]
            self.assertEqual(server["command"], BINDING["python"])
            self.assertEqual(
                server["args"],
                [
                    "-E", "-s", BINDING["launcher"], "mcp",
                    "--node", BINDING["node"], "--entry", BINDING["cli"],
                ],
            )
            self.assertNotIn("cwd", server)
            # Same runtime, more project selections: one identical write.
            second = {**BINDING, "root": "/private/other"}
            batch = analyze_omp_configuration(target, [BINDING, second], [])
            self.assertEqual(batch["writes"], analysis["writes"])
            rendered = omp_mcp_candidate(b"", analysis)
            document = json.loads(rendered)
            self.assertEqual(set(document["mcpServers"]), {"sbtd-graft"})

    def test_batch_with_two_runtimes_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "mcp.json"
            other = {
                "root": "/private/other",
                "node": "/elsewhere/node",
                "cli": "/elsewhere/dist/cli.js",
                "python": "/elsewhere/python",
                "launcher": "/elsewhere/scripts/sbtd_graft_entry.py",
            }
            with self.assertRaises(ContractError) as failure:
                analyze_omp_configuration(target, [BINDING, other], [])
            self.assertEqual(failure.exception.code, "invalid-argument")

    def test_retired_fixed_root_entry_conflicts_without_explicit_retirement(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "mcp.json"
            target.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            self._legacy_name(BINDING["root"]):
                                self._legacy_record(BINDING["root"], BINDING),
                        }
                    }
                ),
                encoding="utf-8",
            )
            before = target.read_bytes()
            with self.assertRaises(ContractError) as failure:
                analyze_omp_configuration(target, [BINDING], [])
            self.assertEqual(failure.exception.code, "ownership-conflict")
            # Authorization scoped to a different root cannot claim it.
            other = {**BINDING, "root": "/private/other"}
            with self.assertRaises(ContractError) as failure:
                analyze_omp_configuration(target, [other], [], retire_legacy=True)
            self.assertEqual(failure.exception.code, "ownership-conflict")
            self.assertEqual(target.read_bytes(), before)

    def test_authorized_retirement_removes_only_the_proven_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "mcp.json"
            legacy_name = self._legacy_name(BINDING["root"])
            target.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            legacy_name: self._legacy_record(
                                BINDING["root"], BINDING
                            ),
                            "unrelated": {
                                "type": "stdio",
                                "command": "/usr/bin/true",
                                "args": [],
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            analysis = analyze_omp_configuration(
                target, [BINDING], [], retire_legacy=True
            )
            self.assertEqual(analysis["removals"], [legacy_name])
            candidate = json.loads(
                omp_mcp_candidate(target.read_bytes(), analysis)
            )
            self.assertEqual(
                set(candidate["mcpServers"]), {"sbtd-graft", "unrelated"}
            )
            self.assertEqual(
                candidate["mcpServers"]["unrelated"]["command"], "/usr/bin/true"
            )
            self.assertNotIn("cwd", candidate["mcpServers"]["sbtd-graft"])

    def test_authorized_retirement_of_an_observed_legacy_runtime_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "mcp.json"
            legacy_runtime = {
                "node": "/temp/old-runtime/node",
                "cli": "/temp/old-package/dist/cli.js",
                "python": "/temp/old-runtime/python",
                "launcher": "/temp/old-deploy/scripts/sbtd_graft_entry.py",
            }
            legacy_name = self._legacy_name(BINDING["root"])
            target.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            legacy_name: self._legacy_record(
                                BINDING["root"], legacy_runtime
                            )
                        }
                    }
                ),
                encoding="utf-8",
            )
            # A different old runtime without the observed contract: refused.
            with self.assertRaises(ContractError) as failure:
                analyze_omp_configuration(target, [BINDING], [], retire_legacy=True)
            self.assertEqual(failure.exception.code, "ownership-conflict")
            # A contract that does not match the observed old runtime: refused.
            wrong = {
                **BINDING,
                "legacy": {**legacy_runtime, "node": "/temp/other/node"},
            }
            with self.assertRaises(ContractError) as failure:
                analyze_omp_configuration(target, [wrong], [], retire_legacy=True)
            self.assertEqual(failure.exception.code, "ownership-conflict")
            # The exact observed contract retires the entry onto the new
            # runtime: the TEMP-runtime migration path.
            contracted = {**BINDING, "legacy": legacy_runtime}
            analysis = analyze_omp_configuration(
                target, [contracted], [], retire_legacy=True
            )
            self.assertEqual(analysis["removals"], [legacy_name])
            candidate = json.loads(
                omp_mcp_candidate(target.read_bytes(), analysis)
            )
            self.assertEqual(set(candidate["mcpServers"]), {"sbtd-graft"})
            self.assertEqual(
                candidate["mcpServers"]["sbtd-graft"]["command"], BINDING["python"]
            )

    def test_unknown_graft_prefixed_entry_is_never_retired_by_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "mcp.json"
            target.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "sbtd-graft-mine": {
                                "type": "stdio",
                                "command": "/usr/bin/true",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            before = target.read_bytes()
            with self.assertRaises(ContractError) as failure:
                analyze_omp_configuration(target, [BINDING], [], retire_legacy=True)
            self.assertEqual(failure.exception.code, "ownership-conflict")
            self.assertEqual(target.read_bytes(), before)

    def test_inherited_retired_shape_entry_conflicts_despite_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "mcp.json"
            with self.assertRaises(ContractError) as failure:
                analyze_omp_configuration(
                    target,
                    [BINDING],
                    [
                        {
                            "source": "codex-user",
                            "enabled": True,
                            "servers": {
                                self._legacy_name(BINDING["root"]):
                                    self._legacy_record(BINDING["root"], BINDING),
                            },
                        },
                    ],
                    retire_legacy=True,
                )
            self.assertEqual(failure.exception.code, "ownership-conflict")

    def test_retired_record_with_custom_fields_is_never_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "mcp.json"
            legacy_name = self._legacy_name(BINDING["root"])
            for extra in (
                {"timeout": 30},
                {"description": "user note"},
                {"enabled": True},
                {"transport": "http"},
            ):
                with self.subTest(extra=extra):
                    record = self._legacy_record(BINDING["root"], BINDING)
                    record.update(extra)
                    target.write_text(
                        json.dumps({"mcpServers": {legacy_name: record}}),
                        encoding="utf-8",
                    )
                    before = target.read_bytes()
                    with self.assertRaises(ContractError) as failure:
                        analyze_omp_configuration(
                            target, [BINDING], [], retire_legacy=True
                        )
                    self.assertEqual(
                        failure.exception.code, "ownership-conflict"
                    )
                    self.assertEqual(target.read_bytes(), before)

    def test_project_scoped_equivalent_does_not_suppress_global_write(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "mcp.json"
            analysis = analyze_omp_configuration(
                target,
                [BINDING],
                [
                    {
                        "source": "codex-project",
                        "enabled": True,
                        "servers": {"sbtd-graft": desired_omp_server(BINDING)},
                    }
                ],
            )
            # One project's equivalent entry covers only sessions started in
            # that project; the global definition is still written.
            self.assertEqual(len(analysis["writes"]), 1)
            self.assertEqual(analysis["writes"][0]["name"], "sbtd-graft")
            self.assertEqual(analysis["removals"], [])
            self.assertEqual(analysis["inherited_matches"], [])

    def test_project_scoped_equivalent_does_not_suppress_retirement_write(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "mcp.json"
            legacy_name = self._legacy_name(BINDING["root"])
            target.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            legacy_name: self._legacy_record(
                                BINDING["root"], BINDING
                            )
                        }
                    }
                ),
                encoding="utf-8",
            )
            analysis = analyze_omp_configuration(
                target,
                [BINDING],
                [
                    {
                        "source": "claude-project",
                        "enabled": True,
                        "servers": {"sbtd-graft": desired_omp_server(BINDING)},
                    }
                ],
                retire_legacy=True,
            )
            self.assertEqual(analysis["removals"], [legacy_name])
            self.assertEqual(len(analysis["writes"]), 1)
            self.assertEqual(analysis["writes"][0]["name"], "sbtd-graft")
            self.assertEqual(analysis["inherited_matches"], [])


class OmpSourceAnalysisTests(unittest.TestCase):
    def test_named_profile_ignores_agent_override_and_keeps_reads_readonly(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = base / "project"
            home.mkdir()
            root.mkdir()
            before = {
                str(path.relative_to(base)): path.read_bytes()
                for path in base.rglob("*")
                if path.is_file()
            }
            result = analyze_omp_sources(
                [root],
                [BINDING],
                home=home,
                environ={
                    "OMP_PROFILE": "work",
                    "PI_CODING_AGENT_DIR": str(base / "ignored-agent"),
                },
            )
            self.assertEqual(
                Path(result["target"]),
                home / ".omp/profiles/work/agent/mcp.json",
            )
            self.assertEqual(result["analysis"]["writes"][0]["server"]["type"], "stdio")
            after = {
                str(path.relative_to(base)): path.read_bytes()
                for path in base.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, before)

    def test_default_profile_honors_agent_override_and_codex_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = base / "project"
            agent = base / "custom-agent"
            codex = home / ".codex"
            for path in (agent, codex, root):
                path.mkdir(parents=True)
            desired = desired_omp_server(BINDING)
            (agent / "config.yml").write_text(
                "enabledProviders: [codex]\n", encoding="utf-8"
            )
            (codex / "config.toml").write_text(
                "[mcp_servers.sbtd-graft]\n"
                f'command = "{desired["command"]}"\n'
                "args = " + json.dumps(desired["args"]) + "\n"
                '[mcp_servers.sbtd-graft.env]\nDO_NOT_TRACK = "1"\nDNT = "1"\n',
                encoding="utf-8",
            )
            result = analyze_omp_sources(
                [root],
                [BINDING],
                home=home,
                environ={"PI_CODING_AGENT_DIR": str(agent)},
            )
            self.assertEqual(Path(result["target"]), agent / "mcp.json")
            self.assertEqual(result["analysis"]["writes"], [])
            self.assertEqual(
                [match["source"] for match in result["analysis"]["inherited_matches"]],
                ["codex-user"],
            )
            self.assertIn(
                {"path": str(codex / "config.toml"), "state": "file"},
                [
                    {"path": item["path"], "state": item["state"]["type"]}
                    for item in result["inputs"]
                ],
            )

    def test_project_disabled_codex_source_blocks_without_executing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = base / "project"
            config = root / ".codex/config.toml"
            config.parent.mkdir(parents=True)
            home.mkdir()
            config.write_text(
                "[mcp_servers.sbtd-graft]\n"
                'enabled = false\ncommand = "/definitely/not/executed"\n',
                encoding="utf-8",
            )
            before = config.read_bytes()
            with self.assertRaises(ContractError) as failure:
                analyze_omp_sources([root], [BINDING], home=home, environ={})
            self.assertEqual(failure.exception.code, "ownership-conflict")
            self.assertEqual(config.read_bytes(), before)

    def test_dynamic_overlay_or_project_provider_settings_block_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = base / "project"
            home.mkdir()
            (root / ".omp").mkdir(parents=True)
            (root / ".omp/config.yml").write_text(
                "enabledProviders: [codex]\n", encoding="utf-8"
            )
            before = {
                str(path.relative_to(base)): path.read_bytes()
                for path in base.rglob("*")
                if path.is_file()
            }
            with self.assertRaises(ContractError) as project_failure:
                analyze_omp_sources([root], [BINDING], home=home, environ={})
            self.assertEqual(project_failure.exception.code, "invalid-config")
            with self.assertRaises(ContractError) as overlay_failure:
                analyze_omp_sources(
                    [root],
                    [BINDING],
                    home=home,
                    environ={"PI_CONFIG_FILES": "/private/unknown-overlay.yml"},
                )
            self.assertEqual(overlay_failure.exception.code, "invalid-config")
            after = {
                str(path.relative_to(base)): path.read_bytes()
                for path in base.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, before)

    def test_legacy_agent_settings_are_not_silently_reinterpreted(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = base / "project"
            agent = home / ".omp/agent"
            agent.mkdir(parents=True)
            root.mkdir()
            legacy = agent / "settings.json"
            legacy.write_text('{"enabledProviders":["codex"]}', encoding="utf-8")
            before = legacy.read_bytes()
            with self.assertRaises(ContractError) as failure:
                analyze_omp_sources([root], [BINDING], home=home, environ={})
            self.assertEqual(failure.exception.code, "invalid-config")
            self.assertEqual(legacy.read_bytes(), before)

    def test_native_provider_disabled_blocks_deployment(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = base / "project"
            agent = home / ".omp/agent"
            agent.mkdir(parents=True)
            root.mkdir()
            (agent / "config.yml").write_text(
                "disabledProviders: [native]\n", encoding="utf-8"
            )
            with self.assertRaises(ContractError) as failure:
                analyze_omp_sources([root], [BINDING], home=home, environ={})
            self.assertEqual(failure.exception.code, "invalid-config")

    def test_project_claude_fallback_reads_second_file_after_empty_first(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = base / "project"
            home.mkdir()
            claude = root / ".claude"
            claude.mkdir(parents=True)
            desired = desired_omp_server(BINDING)
            (claude / ".mcp.json").write_text('{"other": true}', encoding="utf-8")
            (claude / "mcp.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "sbtd-graft": {
                                "command": desired["command"],
                                "args": ["stale"],
                                "env": desired["env"],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            # Only reading the fallback file surfaces this managed
            # non-equivalent entry; an equivalent entry here would no
            # longer be observable because project sources never suppress
            # the global write.
            with self.assertRaises(ContractError) as failure:
                analyze_omp_sources([root], [BINDING], home=home, environ={})
            self.assertEqual(failure.exception.code, "ownership-conflict")

    def test_claude_enabled_override_does_not_suppress_global_write(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = base / "project"
            agent = home / ".omp/agent"
            claude = root / ".claude"
            for path in (agent, claude):
                path.mkdir(parents=True)
            desired = desired_omp_server(BINDING)
            (agent / "mcp.json").write_text(
                json.dumps({"mcpServers": {}, "enabledServers": ["foreign"]}),
                encoding="utf-8",
            )
            (claude / "mcp.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "foreign": {**desired, "enabled": False},
                        }
                    }
                ),
                encoding="utf-8",
            )
            result = analyze_omp_sources([root], [BINDING], home=home, environ={})
            # The forced-enabled project entry is equivalent and harmless,
            # but a project scope can never satisfy the global definition.
            self.assertEqual(len(result["analysis"]["writes"]), 1)
            self.assertEqual(
                result["analysis"]["writes"][0]["name"], "sbtd-graft"
            )
            self.assertEqual(result["analysis"]["inherited_matches"], [])

    def test_enabled_non_equivalent_managed_inherited_entry_conflicts(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = base / "project"
            agent = home / ".omp/agent"
            codex = home / ".codex"
            agent.mkdir(parents=True)
            codex.mkdir(parents=True)
            root.mkdir()
            (agent / "config.yml").write_text(
                "enabledProviders: [codex]\n", encoding="utf-8"
            )
            (codex / "config.toml").write_text(
                '[mcp_servers.sbtd-graft]\ncommand = "/unproven/launcher"\n',
                encoding="utf-8",
            )
            with self.assertRaises(ContractError) as failure:
                analyze_omp_sources([root], [BINDING], home=home, environ={})
            self.assertEqual(failure.exception.code, "ownership-conflict")

    def test_alternate_active_user_config_suppresses_write(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = base / "project"
            agent = home / ".omp/agent"
            agent.mkdir(parents=True)
            root.mkdir()
            desired = desired_omp_server(BINDING)
            (agent / ".mcp.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "sbtd-graft": {
                                "command": desired["command"],
                                "args": desired["args"],
                                "env": desired["env"],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            target = agent / "mcp.json"
            result = analyze_omp_sources([root], [BINDING], home=home, environ={})
            self.assertEqual(result["analysis"]["writes"], [])
            self.assertFalse(target.exists())

    def test_inherited_non_equivalent_environment_does_not_suppress_native_write(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = base / "project"
            agent = home / ".omp/agent"
            codex = home / ".codex"
            agent.mkdir(parents=True)
            codex.mkdir(parents=True)
            root.mkdir()
            desired = desired_omp_server(BINDING)
            (agent / "config.yml").write_text(
                "enabledProviders: [codex]\n", encoding="utf-8"
            )
            (codex / "config.toml").write_text(
                "[mcp_servers.other]\n"
                f'command = "{desired["command"]}"\n'
                "args = " + json.dumps(desired["args"]) + "\n"
                '[mcp_servers.other.env]\nDO_NOT_TRACK = "1"\nDNT = "1"\nEXTRA = "x"\n',
                encoding="utf-8",
            )
            result = analyze_omp_sources([root], [BINDING], home=home, environ={})
            self.assertEqual(len(result["analysis"]["writes"]), 1)

    def test_inherited_transport_key_is_ignored_by_pinned_omp(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = base / "project"
            home.mkdir()
            (root / ".omp").mkdir(parents=True)
            desired = desired_omp_server(BINDING)
            (root / ".omp/mcp.json").write_text(
                json.dumps(
                    {"mcpServers": {"sbtd-graft": {**desired, "transport": "http"}}}
                ),
                encoding="utf-8",
            )
            result = analyze_omp_sources([root], [BINDING], home=home, environ={})
            # ``transport`` stays ignored for equivalence, so no conflict,
            # but the project-scoped entry cannot suppress the global write.
            self.assertEqual(len(result["analysis"]["writes"]), 1)
            self.assertEqual(
                result["analysis"]["writes"][0]["name"], "sbtd-graft"
            )

    def test_project_equivalent_for_one_root_does_not_satisfy_global_install(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root_a = base / "a"
            root_b = base / "b"
            home.mkdir()
            claude = root_a / ".claude"
            claude.mkdir(parents=True)
            root_b.mkdir()
            (claude / "mcp.json").write_text(
                json.dumps(
                    {"mcpServers": {"sbtd-graft": desired_omp_server(BINDING)}}
                ),
                encoding="utf-8",
            )
            binding_b = {**BINDING, "root": str(root_b)}
            result = analyze_omp_sources(
                [root_a, root_b], [BINDING, binding_b], home=home, environ={}
            )
            # Project A's equivalent entry covers neither project B nor a
            # projectless session: the global write still happens.
            self.assertEqual(len(result["analysis"]["writes"]), 1)
            self.assertEqual(
                result["analysis"]["writes"][0]["name"], "sbtd-graft"
            )
            self.assertEqual(result["analysis"]["inherited_matches"], [])

    def test_active_disabled_or_stale_managed_entry_conflicts_despite_inheritance(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = base / "project"
            agent = home / ".omp/agent"
            agent.mkdir(parents=True)
            root.mkdir()
            desired = desired_omp_server(BINDING)
            legacy = OmpMcpCandidateTests._legacy_record(BINDING["root"], BINDING)
            name = OmpMcpCandidateTests._legacy_name(BINDING["root"])
            (agent / "mcp.json").write_text(
                json.dumps({"mcpServers": {name: {"enabled": False, **legacy}}}),
                encoding="utf-8",
            )
            (root / ".omp").mkdir()
            (root / ".omp/mcp.json").write_text(
                json.dumps({"mcpServers": {"sbtd-graft": desired}}),
                encoding="utf-8",
            )
            with self.assertRaises(ContractError) as failure:
                analyze_omp_sources([root], [BINDING], home=home, environ={})
            self.assertEqual(failure.exception.code, "ownership-conflict")

    def test_disabled_server_and_extension_lists_block_generated_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            name = "sbtd-graft"
            for label, settings, config in (
                (
                    "server",
                    "",
                    {"mcpServers": {}, "disabledServers": [name]},
                ),
                (
                    "extension",
                    f"disabledExtensions: [mcp:{name}]\n",
                    {"mcpServers": {}},
                ),
            ):
                with self.subTest(kind=label):
                    root = base / label / "project"
                    home = base / label / "home"
                    agent = home / ".omp/agent"
                    agent.mkdir(parents=True)
                    root.mkdir()
                    if settings:
                        (agent / "config.yml").write_text(settings, encoding="utf-8")
                    (agent / "mcp.json").write_text(
                        json.dumps(config), encoding="utf-8"
                    )
                    with self.assertRaises(ContractError) as failure:
                        analyze_omp_sources([root], [BINDING], home=home, environ={})
                    self.assertEqual(failure.exception.code, "ownership-conflict")

    def test_claude_source_wins_over_codex_for_same_enabled_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = base / "project"
            agent = home / ".omp/agent"
            codex = home / ".codex"
            for path in (agent, codex, root):
                path.mkdir(parents=True)
            desired = desired_omp_server(BINDING)
            (agent / "config.yml").write_text(
                "enabledProviders: [codex, claude]\n", encoding="utf-8"
            )

            (codex / "config.toml").write_text(
                "[mcp_servers.sbtd-graft]\n"
                f'command = "{desired["command"]}"\n'
                "args = " + json.dumps(desired["args"]) + "\n"
                '[mcp_servers.sbtd-graft.env]\nDO_NOT_TRACK = "1"\nDNT = "1"\n',
                encoding="utf-8",
            )
            (home / ".claude.json").write_text(
                json.dumps({"mcpServers": {"sbtd-graft": desired}}),
                encoding="utf-8",
            )
            result = analyze_omp_sources([root], [BINDING], home=home, environ={})
            self.assertEqual(
                result["analysis"]["inherited_matches"][0]["source"],
                "claude-user-json",
            )

    def test_denylisted_equivalent_foreign_sources_do_not_suppress_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = base / "project"
            agent = home / ".omp/agent"
            agent.mkdir(parents=True)
            root.mkdir()
            desired = desired_omp_server(BINDING)
            target = agent / "mcp.json"
            target.write_text(
                json.dumps(
                    {
                        "mcpServers": {"other": desired},
                        "disabledServers": ["other"],
                    }
                ),
                encoding="utf-8",
            )
            result = analyze_omp_sources([root], [BINDING], home=home, environ={})
            self.assertEqual(len(result["analysis"]["writes"]), 1)

    def test_extension_denylisted_inherited_source_does_not_suppress_write(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = base / "project"
            agent = home / ".omp/agent"
            agent.mkdir(parents=True)
            (root / ".omp").mkdir(parents=True)
            desired = desired_omp_server(BINDING)
            (agent / "config.yml").write_text(
                "disabledExtensions: [mcp:other]\n", encoding="utf-8"
            )
            (root / ".omp/mcp.json").write_text(
                json.dumps({"mcpServers": {"other": desired}}),
                encoding="utf-8",
            )
            result = analyze_omp_sources([root], [BINDING], home=home, environ={})
            self.assertEqual(len(result["analysis"]["writes"]), 1)

    def test_project_and_claude_disabled_extensions_block_analysis(self):
        cases = (
            (".omp/config.yml", "disabledExtensions: [mcp:sbtd-graft]\n"),
            (".omp/settings.json", '{"disabledExtensions":["mcp:sbtd-graft"]}'),
            (".claude/settings.json", '{"disabledExtensions":["mcp:sbtd-graft"]}'),
        )
        for index, (relative, content) in enumerate(cases):
            with (
                self.subTest(relative=relative),
                tempfile.TemporaryDirectory() as directory,
            ):
                base = Path(directory).resolve()
                home = base / "home"
                root = base / "project"
                home.mkdir()
                target = root / relative
                target.parent.mkdir(parents=True)
                target.write_text(content, encoding="utf-8")
                with self.assertRaises(ContractError) as failure:
                    analyze_omp_sources([root], [BINDING], home=home, environ={})
                self.assertEqual(failure.exception.code, "invalid-config")

    def test_enabled_claude_user_disabled_extensions_block_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home = base / "home"
            root = base / "project"
            agent = home / ".omp/agent"
            claude = home / ".claude"
            agent.mkdir(parents=True)
            claude.mkdir(parents=True)
            root.mkdir()
            (agent / "config.yml").write_text(
                "enabledProviders: [claude]\n", encoding="utf-8"
            )
            (claude / "settings.json").write_text(
                '{"disabledExtensions":["mcp:sbtd-graft"]}', encoding="utf-8"
            )
            with self.assertRaises(ContractError) as failure:
                analyze_omp_sources([root], [BINDING], home=home, environ={})
            self.assertEqual(failure.exception.code, "invalid-config")

    def test_enabled_claude_plugin_sources_block_without_rewriting_them(self):
        for provider in ("claude", "omp"):
            with (
                self.subTest(provider=provider),
                tempfile.TemporaryDirectory() as directory,
            ):
                base = Path(directory).resolve()
                home = base / "home"
                root = base / "project"
                agent = home / ".omp/agent"
                plugins = (
                    home / ".claude/plugins/installed_plugins.json"
                    if provider == "claude"
                    else home / ".omp/plugins/installed_plugins.json"
                )
                agent.mkdir(parents=True)
                root.mkdir()
                (agent / "config.yml").write_text(
                    "enabledProviders: [claude-plugins]\n", encoding="utf-8"
                )
                plugins.parent.mkdir(parents=True)
                original = b'{"plugins": {"fixture": []}}\n'
                plugins.write_bytes(original)
                with self.assertRaises(ContractError) as failure:
                    analyze_omp_sources([root], [BINDING], home=home, environ={})
                self.assertEqual(failure.exception.code, "invalid-config")
                self.assertEqual(plugins.read_bytes(), original)

    def test_plugin_discovery_covers_default_override_xdg_and_project_registries(self):
        for source in (
            "default",
            "claude",
            "override",
            "xdg",
            "profile",
            "project",
            "ancestor",
        ):
            with (
                self.subTest(source=source),
                tempfile.TemporaryDirectory() as directory,
            ):
                base = Path(directory).resolve()
                home = base / "home"
                root = base / "project"
                agent = home / ".omp/agent"
                agent.mkdir(parents=True)
                root.mkdir()
                environment = {}
                plugins = home / ".omp/plugins/installed_plugins.json"
                if source == "claude":
                    (agent / "config.yml").write_text("enabledProviders: [claude]\n")
                    plugins = home / ".claude/plugins/installed_plugins.json"
                elif source == "override":
                    environment["CLAUDE_CONFIG_DIR"] = str(base / "claude-home")
                    plugins = base / "claude-home/plugins/installed_plugins.json"
                elif source == "xdg":
                    environment["XDG_DATA_HOME"] = str(base / "xdg")
                    plugins = base / "xdg/omp/plugins/installed_plugins.json"
                elif source == "profile":
                    environment["OMP_PROFILE"] = "work"
                    plugins = home / ".omp/profiles/work/plugins/installed_plugins.json"
                elif source == "project":
                    plugins = root / ".omp/plugins/installed_plugins.json"
                elif source == "ancestor":
                    plugins = base / ".omp/plugins/installed_plugins.json"
                plugins.parent.mkdir(parents=True)
                original = b'{"plugins":{"fixture@marketplace":[{"installPath":"/synthetic/plugin"}]}}'
                plugins.write_bytes(original)
                with self.assertRaises(ContractError) as failure:
                    analyze_omp_sources(
                        [root], [BINDING], home=home, environ=environment
                    )
                self.assertEqual(failure.exception.code, "invalid-config")
                self.assertEqual(plugins.read_bytes(), original)
                self.assertFalse((agent / "mcp.json").exists())


if __name__ == "__main__":
    unittest.main()
