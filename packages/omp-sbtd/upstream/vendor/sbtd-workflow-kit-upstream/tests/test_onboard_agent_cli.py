from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ONBOARD = ROOT / "sbtd-workflow-onboard" / "scripts" / "onboard.py"


class AgentCliCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="sbtd-agent-cli-test-")
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.home = self.root / "home"
        self.home.mkdir()
        self.env = os.environ.copy()
        self.env["HOME"] = str(self.home)
        self.env["PATH"] = str(self.bin_dir)

    def write_executable(self, name: str, body: str) -> Path:
        target = self.bin_dir / name
        target.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IXUSR)
        return target

    def run_onboard(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (sys.executable, str(ONBOARD), *args),
            check=False,
            capture_output=True,
            text=True,
            env=self.env,
            timeout=30,
        )

    def test_check_agent_cli_reports_supported_platform_mappings(self) -> None:
        expected = {
            "codex": ("codex", "@openai/codex"),
            "claude": ("claude", "@anthropic-ai/claude-code"),
            "kimi": ("kimi", "@moonshot-ai/kimi-code"),
            "omp": ("omp", "@oh-my-pi/pi-coding-agent"),
        }

        for platform_name, (command, npm_package) in expected.items():
            with self.subTest(platform=platform_name):
                self.write_executable(
                    command,
                    f"""
                    #!/bin/sh
                    echo "{command} 1.2.3"
                    """,
                )
                completed = self.run_onboard(
                    "check-agent-cli",
                    "--platform",
                    platform_name,
                    "--json",
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                payload = json.loads(completed.stdout)
                self.assertTrue(payload["installed"])
                self.assertEqual(payload["command"], command)
                self.assertEqual(payload["npmPackage"], npm_package)
                self.assertEqual(
                    payload["installCommand"], f"npm install -g {npm_package}@latest"
                )
                (self.bin_dir / command).unlink()

    def test_check_prefers_bundled_playwright_mcp_when_available(self) -> None:
        self.write_executable(
            "npm",
            """
            #!/bin/sh
            echo "12.0.1"
            """,
        )

        completed = self.run_onboard("check", "--json")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        playwright_mcp = next(
            check
            for check in payload["manualChecks"]
            if check["name"] == "Playwright MCP"
        )
        self.assertIn(
            "bundled `npx playwright mcp` entrypoint",
            playwright_mcp["steps"][0],
        )
        self.assertIn(
            "compatible dedicated Playwright MCP server",
            playwright_mcp["steps"][0],
        )

    def test_install_agent_cli_requires_npm_when_command_is_missing(self) -> None:
        completed = self.run_onboard(
            "install-agent-cli",
            "--platform",
            "codex",
            "--yes",
            "--json",
        )

        self.assertEqual(completed.returncode, 2, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "npm-required")
        self.assertFalse(payload["runtime"]["npm"]["installed"])

    def test_install_agent_cli_uses_latest_global_npm_package_and_verifies_command(
        self,
    ) -> None:
        npm_log = self.root / "npm.log"
        self.env["FAKE_BIN_DIR"] = str(self.bin_dir)
        self.env["FAKE_NPM_LOG"] = str(npm_log)
        self.env["FAKE_AGENT_COMMAND"] = "kimi"
        self.write_executable(
            "node",
            """
            #!/bin/sh
            echo "v24.15.0"
            """,
        )
        self.write_executable(
            "npm",
            """
            #!/bin/sh
            if [ "$1" = "--version" ]; then
              echo "10.9.2"
              exit 0
            fi
            printf '%s\n' "$*" > "$FAKE_NPM_LOG"
            printf '#!/bin/sh\necho "%s 9.9.9"\n' "$FAKE_AGENT_COMMAND" > "$FAKE_BIN_DIR/$FAKE_AGENT_COMMAND"
            /bin/chmod +x "$FAKE_BIN_DIR/$FAKE_AGENT_COMMAND"
            """,
        )

        completed = self.run_onboard(
            "install-agent-cli",
            "--platform",
            "kimi",
            "--yes",
            "--json",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "installed")
        self.assertTrue(payload["after"]["installed"])
        self.assertEqual(
            npm_log.read_text(encoding="utf-8").strip(),
            "install -g @moonshot-ai/kimi-code@latest",
        )

    def test_install_agent_cli_skips_npm_when_target_command_already_passes(
        self,
    ) -> None:
        npm_log = self.root / "npm.log"
        self.env["FAKE_NPM_LOG"] = str(npm_log)
        self.write_executable(
            "codex",
            """
            #!/bin/sh
            echo "codex 1.2.3"
            """,
        )
        self.write_executable(
            "node",
            """
            #!/bin/sh
            echo "v24.15.0"
            """,
        )
        self.write_executable(
            "npm",
            """
            #!/bin/sh
            if [ "$1" = "--version" ]; then
              echo "10.9.2"
              exit 0
            fi
            printf '%s\n' "$*" > "$FAKE_NPM_LOG"
            """,
        )

        completed = self.run_onboard(
            "install-agent-cli",
            "--platform",
            "codex",
            "--yes",
            "--json",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "already-installed")
        self.assertFalse(npm_log.exists())


if __name__ == "__main__":
    unittest.main()
