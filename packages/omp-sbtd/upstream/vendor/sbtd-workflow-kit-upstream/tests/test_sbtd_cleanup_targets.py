from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from sbtd_cleanup_targets import (
    GITNEXUS_SKILL_NAMES,
    RETIRED_SKILL_NAMES,
    TRELLIS_SKILL_NAMES,
    detect_marker_blocks,
    detect_mcp_targets,
    detect_project_targets,
    detect_skill_targets,
    remove_json_server_key,
    remove_marker_blocks,
    remove_toml_server_table,
    skill_identity_error,
)

AGENTS_WITH_BOTH_BLOCKS = (
    b"<!-- TRELLIS:START -->\n"
    b"# Trellis Instructions\n"
    b"\n"
    b"Managed by Trellis.\n"
    b"<!-- TRELLIS:END -->\n"
    b"\n"
    b"<!-- gitnexus:start -->\n"
    b"# GitNexus\n"
    b"Use the GitNexus MCP tools.\n"
    b"<!-- gitnexus:end -->\n"
    b"\n"
    b"---\n"
    b"\n"
    b"# Codex project rules\n"
    b"\n"
    b"<!-- graft:start -->\n"
    b"Graft fence body.\n"
    b"<!-- graft:end -->\n"
)


class MarkerBlockTests(unittest.TestCase):
    def test_both_blocks_are_removable(self) -> None:
        result = detect_marker_blocks(AGENTS_WITH_BOTH_BLOCKS)
        self.assertEqual(result["status"], "removable")
        self.assertEqual(result["removals"], 2)

    def test_removal_preserves_everything_outside_blocks(self) -> None:
        cleaned = remove_marker_blocks(AGENTS_WITH_BOTH_BLOCKS)
        self.assertNotIn(b"TRELLIS:START", cleaned)
        self.assertNotIn(b"gitnexus:start", cleaned)
        self.assertNotIn(b"Trellis Instructions", cleaned)
        self.assertNotIn(b"GitNexus MCP tools", cleaned)
        self.assertEqual(
            cleaned,
            b"\n\n---\n\n# Codex project rules\n\n"
            b"<!-- graft:start -->\nGraft fence body.\n<!-- graft:end -->\n",
        )
        self.assertIn(b"<!-- graft:start -->", cleaned)
        self.assertIn(b"<!-- graft:end -->", cleaned)
        self.assertIn(b"# Codex project rules", cleaned)

    def test_no_markers_is_none(self) -> None:
        self.assertEqual(
            detect_marker_blocks(b"plain project rules\n"), {"status": "none"}
        )

    def test_unmatched_end_is_malformed(self) -> None:
        result = detect_marker_blocks(b"text\n<!-- TRELLIS:END -->\n")
        self.assertEqual(result["status"], "malformed")

    def test_duplicated_start_is_malformed(self) -> None:
        raw = (
            b"<!-- TRELLIS:START -->\na\n<!-- TRELLIS:END -->\n"
            b"<!-- TRELLIS:START -->\nb\n<!-- TRELLIS:END -->\n"
        )
        self.assertEqual(detect_marker_blocks(raw)["status"], "malformed")

    def test_interleaved_pairs_are_malformed(self) -> None:
        raw = (
            b"<!-- TRELLIS:START -->\n"
            b"<!-- gitnexus:start -->\n"
            b"<!-- TRELLIS:END -->\n"
            b"<!-- gitnexus:end -->\n"
        )
        self.assertEqual(detect_marker_blocks(raw)["status"], "malformed")

    def test_inline_example_is_not_a_managed_marker(self) -> None:
        raw = (
            b"An example: <!-- TRELLIS:START -->\n"
            b"sample\n<!-- TRELLIS:END --> in prose\n"
        )
        self.assertEqual(detect_marker_blocks(raw), {"status": "none"})
        self.assertEqual(remove_marker_blocks(raw), raw)

    def test_fenced_marker_example_is_preserved(self) -> None:
        raw = (
            b"```markdown\n<!-- TRELLIS:START -->\nexample\n<!-- TRELLIS:END -->\n```\n"
        )
        self.assertEqual(detect_marker_blocks(raw), {"status": "none"})
        self.assertEqual(remove_marker_blocks(raw), raw)

    def test_removal_refuses_malformed_input(self) -> None:
        with self.assertRaises(ValueError):
            remove_marker_blocks(b"<!-- TRELLIS:START -->\nnever closed\n")


class SkillIdentityTests(unittest.TestCase):
    def _skill_dir(self, base: Path, name: str, frontmatter_name: str) -> Path:
        target = base / name
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text(
            f"---\nname: {frontmatter_name}\ndescription: drifted 1.0.x content\n---\nbody\n"
        )
        (target / "extra.txt").write_text("user drift from any 1.0.x version\n")
        return target

    def test_drifted_content_with_matching_frontmatter_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            target = self._skill_dir(base, "trellis-workflow", "trellis-workflow")
            self.assertIsNone(skill_identity_error(target, "trellis-workflow"))

    def test_mismatched_frontmatter_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            target = self._skill_dir(base, "trellis-workflow", "user-own-skill")
            self.assertIsNotNone(skill_identity_error(target, "trellis-workflow"))

    def test_missing_skill_md_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "trellis-channel"
            target.mkdir()
            self.assertIsNotNone(skill_identity_error(target, "trellis-channel"))

    def test_symlink_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            real = self._skill_dir(base, "real", "trellis-workflow")
            link = base / "trellis-workflow"
            os.symlink(real, link)
            self.assertIsNotNone(skill_identity_error(link, "trellis-workflow"))

    def test_detect_skill_targets_lists_only_proven_identities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            self._skill_dir(base, "trellis-workflow", "trellis-workflow")
            self._skill_dir(base, "trellis-channel", "something-else")
            result = detect_skill_targets(base)
            kinds = [item["name"] for item in result["candidates"]]
            blocked = [item["name"] for item in result["blocked"]]
            self.assertEqual(kinds, ["trellis-workflow"])
            self.assertEqual(blocked, ["trellis-channel"])

class GitNexusRetiredSkillTests(unittest.TestCase):
    EXPECTED_GITNEXUS = (
        "gitnexus-cli",
        "gitnexus-debugging",
        "gitnexus-exploring",
        "gitnexus-guide",
        "gitnexus-impact-analysis",
        "gitnexus-pdg-query",
        "gitnexus-pr-review",
        "gitnexus-refactoring",
        "gitnexus-taint-analysis",
    )

    def _skill_dir(self, base: Path, name: str, frontmatter_name: str) -> Path:
        target = base / name
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text(
            f"---\nname: {frontmatter_name}\ndescription: retired gitnexus skill\n---\nbody\n"
        )
        return target

    def test_closed_set_is_exact_and_wildcard_free(self) -> None:
        self.assertEqual(GITNEXUS_SKILL_NAMES, self.EXPECTED_GITNEXUS)
        self.assertEqual(len(set(GITNEXUS_SKILL_NAMES)), 9)
        for name in GITNEXUS_SKILL_NAMES:
            self.assertNotIn("*", name)
            self.assertNotIn("/", name)
            self.assertNotIn("\\", name)
        self.assertEqual(
            RETIRED_SKILL_NAMES, TRELLIS_SKILL_NAMES + GITNEXUS_SKILL_NAMES
        )

    def test_default_detection_stays_trellis_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            for name in self.EXPECTED_GITNEXUS:
                self._skill_dir(base, name, name)
            self._skill_dir(base, "trellis-workflow", "trellis-workflow")
            result = detect_skill_targets(base)
            self.assertEqual(
                [item["name"] for item in result["candidates"]],
                ["trellis-workflow"],
            )
            self.assertEqual(result["blocked"], [])

    def test_explicit_opt_in_detects_all_eleven_exact_identities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            for name in RETIRED_SKILL_NAMES:
                self._skill_dir(base, name, name)
            result = detect_skill_targets(base, retired=RETIRED_SKILL_NAMES)
            self.assertEqual(
                [item["name"] for item in result["candidates"]],
                sorted(RETIRED_SKILL_NAMES),
            )
            self.assertEqual(result["blocked"], [])

    def test_similar_directory_names_are_never_matched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            # A directory outside the closed set is ignored even when its
            # frontmatter claims a retired identity (never a prefix match).
            self._skill_dir(base, "gitnexus-cli-extra", "gitnexus-cli")
            self._skill_dir(base, "gitnexus", "gitnexus")
            self._skill_dir(base, "gitnexus-pr", "gitnexus-pr-review")
            result = detect_skill_targets(base, retired=RETIRED_SKILL_NAMES)
            self.assertEqual(result["candidates"], [])
            self.assertEqual(result["blocked"], [])

    def test_identity_conflict_is_blocked_not_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            self._skill_dir(base, "gitnexus-cli", "user-own-skill")
            result = detect_skill_targets(base, retired=RETIRED_SKILL_NAMES)
            self.assertEqual(result["candidates"], [])
            self.assertEqual(
                [item["name"] for item in result["blocked"]], ["gitnexus-cli"]
            )

    def test_drifted_content_with_matching_frontmatter_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            target = self._skill_dir(base, "gitnexus-taint-analysis", "gitnexus-taint-analysis")
            (target / "extra.txt").write_text("user drift from any version\n")
            self.assertIsNone(
                skill_identity_error(target, "gitnexus-taint-analysis")
            )
            result = detect_skill_targets(base, retired=RETIRED_SKILL_NAMES)
            self.assertEqual(
                [item["name"] for item in result["candidates"]],
                ["gitnexus-taint-analysis"],
            )

    def test_symlink_directory_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            real = self._skill_dir(base, "real", "gitnexus-guide")
            os.symlink(real, base / "gitnexus-guide")
            result = detect_skill_targets(base, retired=RETIRED_SKILL_NAMES)
            self.assertEqual(result["candidates"], [])
            self.assertEqual(
                [item["name"] for item in result["blocked"]], ["gitnexus-guide"]
            )

    def test_retired_names_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            with self.assertRaises(ValueError):
                detect_skill_targets(base, retired=["gitnexus/evil"])
            with self.assertRaises(ValueError):
                detect_skill_targets(base, retired=[".."])
            with self.assertRaises(ValueError):
                detect_skill_targets(base, retired=[""])
            with self.assertRaises(TypeError):
                detect_skill_targets(base, retired="gitnexus-cli")
            with self.assertRaises(ValueError):
                detect_skill_targets(base, retired=[123])


class ProjectTargetTests(unittest.TestCase):
    def _project(self, base: Path, *, malformed_agents: bool = False) -> Path:
        root = base / "project"
        (root / ".trellis/workspace/dev01").mkdir(parents=True)
        (root / ".gitnexus/index").mkdir(parents=True)
        (root / ".gitnexus/index/db.bin").write_bytes(b"\x00index\xff")
        agents = (
            b"<!-- TRELLIS:START -->\nopen\n"
            if malformed_agents
            else AGENTS_WITH_BOTH_BLOCKS
        )
        (root / "AGENTS.md").write_bytes(agents)
        return root

    def test_detects_trellis_gitnexus_and_marker_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._project(Path(directory))
            result = detect_project_targets(root)
            kinds = sorted(item["kind"] for item in result["candidates"])
            self.assertEqual(
                kinds, ["directory-remove", "marker-blocks", "trellis-uninstall"]
            )
            self.assertEqual(result["blocked"], [])

    def test_malformed_agents_is_blocked_not_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._project(Path(directory), malformed_agents=True)
            result = detect_project_targets(root)
            kinds = [item["kind"] for item in result["candidates"]]
            self.assertNotIn("marker-blocks", kinds)
            self.assertEqual(len(result["blocked"]), 1)
            self.assertEqual(result["blocked"][0]["kind"], "marker-blocks")

    def test_clean_project_has_no_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            (root / "AGENTS.md").write_text("# rules\n")
            result = detect_project_targets(root)
            self.assertEqual(result["candidates"], [])
            self.assertEqual(result["blocked"], [])


class McpTargetTests(unittest.TestCase):
    def _home(self, base: Path) -> Path:
        home = base / "home"
        (home / ".codex").mkdir(parents=True)
        (home / ".kimi-code").mkdir(parents=True)
        (home / ".omp/agent").mkdir(parents=True)
        (home / ".codex/config.toml").write_text(
            '# user comment\n[mcp_servers.gitnexus]\ncommand = "/usr/local/bin/gitnexus"\n'
            'args = ["mcp"]\n\n[mcp_servers.context7]\ncommand = "npx"\n'
        )
        (home / ".claude.json").write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "gitnexus": {"command": "gitnexus", "args": ["mcp"]},
                        "playwright": {"command": "npx"},
                    }
                }
            )
        )
        (home / ".kimi-code/mcp.json").write_text(
            json.dumps({"mcpServers": {"gitnexus": {"command": "gitnexus"}}})
        )
        (home / ".omp/agent/mcp.json").write_text(
            json.dumps({"mcpServers": {"playwright": {"command": "npx"}}})
        )
        return home

    def test_detects_gitnexus_entries_per_host(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self._home(Path(directory).resolve())
            environ = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(home / ".codex"),
            }
            result = detect_mcp_targets(environ=environ)
            by_host = {item["host"]: item for item in result["candidates"]}
            self.assertEqual(sorted(by_host), ["claude", "codex", "kimi"])
            self.assertEqual(by_host["codex"]["format"], "toml")
            self.assertEqual(by_host["claude"]["format"], "json")
            self.assertEqual(result["blocked"], [])

    def test_missing_configs_are_not_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve() / "home"
            home.mkdir()
            environ = {"HOME": str(home), "USERPROFILE": str(home)}
            result = detect_mcp_targets(environ=environ)
            self.assertEqual(result["candidates"], [])

    def test_malformed_existing_host_config_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self._home(Path(directory).resolve())
            (home / ".kimi-code/mcp.json").write_text("{invalid")
            result = detect_mcp_targets(environ={"HOME": str(home)})
            self.assertEqual(len(result["blocked"]), 1)
            self.assertEqual(result["blocked"][0]["host"], "kimi")

    def test_duplicate_json_mcp_key_is_rejected(self) -> None:
        raw = b'{"mcpServers":{"gitnexus":{},"gitnexus":{"command":"other"}}}'
        with self.assertRaises(ValueError):
            remove_json_server_key(raw, "gitnexus")

    def test_nonfinite_number_is_blocked_during_detection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self._home(Path(directory).resolve())
            (home / ".kimi-code/mcp.json").write_text(
                '{"mcpServers":{"gitnexus":{"command":"gitnexus"}},"number":1e999}'
            )
            result = detect_mcp_targets(environ={"HOME": str(home)})
            self.assertEqual(result["blocked"][0]["host"], "kimi")
            self.assertFalse(
                any(item["host"] == "kimi" for item in result["candidates"])
            )

    def test_unencodable_json_neighbor_is_blocked_during_detection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self._home(Path(directory).resolve())
            (home / ".kimi-code/mcp.json").write_bytes(
                b'{"mcpServers":{"gitnexus":{}},"neighbor":"\\ud800"}'
            )
            result = detect_mcp_targets(environ={"HOME": str(home)})
            self.assertEqual(result["blocked"][0]["host"], "kimi")

    def test_runtime_options_do_not_hide_gitnexus_servers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self._home(Path(directory).resolve())
            (home / ".kimi-code/mcp.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "package-long": {
                                "command": "npx",
                                "args": ["--package=gitnexus", "gitnexus", "mcp"],
                            },
                            "package-short": {
                                "command": "npx",
                                "args": ["-p", "gitnexus", "gitnexus-mcp"],
                            },
                            "terminator": {
                                "command": "npx",
                                "args": ["--", "gitnexus", "mcp"],
                            },
                            "node-flags": {
                                "command": "node",
                                "args": [
                                    "--no-warnings",
                                    "/opt/node_modules/gitnexus/dist/cli/index.js",
                                    "mcp",
                                ],
                            },
                            "other": {
                                "command": "npx",
                                "args": ["--package=gitnexus", "other-mcp"],
                            },
                        }
                    }
                )
            )
            result = detect_mcp_targets(environ={"HOME": str(home)})
            kimi = next(item for item in result["candidates"] if item["host"] == "kimi")
            self.assertEqual(
                kimi["keys"],
                ["node-flags", "package-long", "package-short", "terminator"],
            )

    def test_other_servers_gitnexus_argument_is_not_an_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self._home(Path(directory).resolve())
            (home / ".kimi-code/mcp.json").write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "other": {
                                "command": "npx",
                                "args": ["-y", "other-mcp", "gitnexus"],
                            },
                            "node-other": {
                                "command": "node",
                                "args": [
                                    "/opt/other.js",
                                    "/opt/node_modules/gitnexus/bin.js",
                                ],
                            },
                        }
                    }
                )
            )
            result = detect_mcp_targets(environ={"HOME": str(home)})
            self.assertFalse(
                any(item["host"] == "kimi" for item in result["candidates"])
            )

    def _custom_omp_home(self, base: Path) -> Path:
        home = self._home(base)
        (home / "custom-omp/agent").mkdir(parents=True)
        (home / "custom-omp/agent/mcp.json").write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "gitnexus": {"command": "gitnexus", "args": ["mcp"]},
                        "playwright": {"command": "npx"},
                    }
                }
            )
        )
        return home

    def test_effective_custom_omp_config_dir_target_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self._custom_omp_home(Path(directory).resolve())
            environ = {"HOME": str(home), "PI_CONFIG_DIR": "custom-omp"}
            result = detect_mcp_targets(environ=environ)
            self.assertEqual(result["blocked"], [])
            omp = [item for item in result["candidates"] if item["host"] == "omp"]
            self.assertEqual(
                [item["path"] for item in omp],
                [str(home / "custom-omp/agent/mcp.json")],
            )
            self.assertEqual(omp[0]["keys"], ["gitnexus"])

    def test_effective_omp_profile_target_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self._custom_omp_home(Path(directory).resolve())
            profile = home / "custom-omp/profiles/work/agent"
            profile.mkdir(parents=True)
            (profile / "mcp.json").write_text(
                json.dumps({"mcpServers": {"gitnexus": {"command": "gitnexus"}}})
            )
            environ = {
                "HOME": str(home),
                "PI_CONFIG_DIR": "custom-omp",
                "OMP_PROFILE": "work",
            }
            result = detect_mcp_targets(environ=environ)
            self.assertEqual(result["blocked"], [])
            omp = [item for item in result["candidates"] if item["host"] == "omp"]
            self.assertEqual(
                [item["path"] for item in omp], [str(profile / "mcp.json")]
            )

    def test_pi_profile_fallback_and_omp_profile_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self._custom_omp_home(Path(directory).resolve())
            for name in ("work", "other"):
                agent = home / "custom-omp/profiles" / name / "agent"
                agent.mkdir(parents=True)
                (agent / "mcp.json").write_text(
                    json.dumps({"mcpServers": {"gitnexus": {"command": "gitnexus"}}})
                )
            base = {"HOME": str(home), "PI_CONFIG_DIR": "custom-omp"}
            fallback = detect_mcp_targets(environ={**base, "PI_PROFILE": "other"})
            fallback_omp = [
                item for item in fallback["candidates"] if item["host"] == "omp"
            ]
            self.assertEqual(
                [item["path"] for item in fallback_omp],
                [str(home / "custom-omp/profiles/other/agent/mcp.json")],
            )
            override = detect_mcp_targets(
                environ={**base, "PI_PROFILE": "other", "OMP_PROFILE": "work"}
            )
            override_omp = [
                item for item in override["candidates"] if item["host"] == "omp"
            ]
            self.assertEqual(
                [item["path"] for item in override_omp],
                [str(home / "custom-omp/profiles/work/agent/mcp.json")],
            )

    def test_resolved_default_omp_target_is_not_duplicated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self._home(Path(directory).resolve())
            (home / ".omp/agent/mcp.json").write_text(
                json.dumps({"mcpServers": {"gitnexus": {"command": "gitnexus"}}})
            )
            result = detect_mcp_targets(environ={"HOME": str(home)})
            omp = [
                item
                for item in result["candidates"]
                if item["path"] == str(home / ".omp/agent/mcp.json")
            ]
            self.assertEqual(len(omp), 1)

    def test_invalid_omp_resolver_input_fails_closed(self) -> None:
        from onboard_contracts import ContractError

        with tempfile.TemporaryDirectory() as directory:
            home = self._custom_omp_home(Path(directory).resolve())
            for override in ("/absolute/path", "../escape"):
                with self.assertRaises(ContractError):
                    detect_mcp_targets(
                        environ={"HOME": str(home), "PI_CONFIG_DIR": override}
                    )
            with self.assertRaises(ContractError):
                detect_mcp_targets(
                    environ={"HOME": str(home), "OMP_PROFILE": "Bad_Name!"}
                )

    def test_json_key_removal_preserves_neighbor_servers(self) -> None:
        raw = json.dumps(
            {
                "mcpServers": {
                    "gitnexus": {"command": "gitnexus", "args": ["mcp"]},
                    "playwright": {"command": "npx", "args": ["-y", "@playwright/mcp"]},
                },
                "other": True,
            }
        ).encode()
        cleaned = remove_json_server_key(raw, "gitnexus")
        document = json.loads(cleaned)
        self.assertNotIn("gitnexus", document["mcpServers"])
        self.assertEqual(
            document["mcpServers"]["playwright"],
            {"command": "npx", "args": ["-y", "@playwright/mcp"]},
        )
        self.assertTrue(document["other"])

    def test_json_key_removal_without_the_key_is_a_noop(self) -> None:
        raw = json.dumps({"mcpServers": {"playwright": {"command": "npx"}}}).encode()
        self.assertEqual(
            json.loads(remove_json_server_key(raw, "gitnexus")), json.loads(raw)
        )

    def test_toml_table_removal_preserves_comments_and_neighbors(self) -> None:
        raw = (
            b"# user comment\n[mcp_servers.gitnexus]\n"
            b'command = "/usr/local/bin/gitnexus"\nargs = ["mcp"]\n\n'
            b'[mcp_servers.context7]\ncommand = "npx"\n'
        )
        cleaned = remove_toml_server_table(raw, "gitnexus")
        text = cleaned.decode()
        self.assertIn("# user comment", text)
        self.assertNotIn("mcp_servers.gitnexus", text)
        self.assertIn("[mcp_servers.context7]", text)
        self.assertIn('command = "npx"', text)


if __name__ == "__main__":
    unittest.main()
