from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1] / "sbtd-workflow-onboard/scripts/onboard.py"
)


class MigrationCliTests(unittest.TestCase):
    def test_missing_site_packages_does_not_break_the_blocked_json_response(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            environment = os.environ.copy()
            environment.update(
                HOME=str(home),
                USERPROFILE=str(home),
                CODEX_HOME=str(home / ".codex"),
                PYTHONDONTWRITEBYTECODE="1",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-S",
                    "-B",
                    str(SCRIPT),
                    "migration",
                    "--phase",
                    "apply",
                    "--manifest",
                    str(home / "manifest.json"),
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=30,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            response = json.loads(result.stdout)
            self.assertEqual(response["status"], "blocked")
            self.assertEqual(response["migration"], {})
            self.assertEqual(list(home.iterdir()), [])

    def test_live_migration_parser_does_not_echo_unknown_private_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
            environment = os.environ.copy()
            environment.update(
                HOME=str(home),
                USERPROFILE=str(home),
                CODEX_HOME=str(home / ".codex"),
                PYTHONDONTWRITEBYTECODE="1",
            )
            help_result = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "migration", "--help"],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=30,
            )
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            private_token = "SYNTHETIC_PRIVATE_ARGUMENT"
            rejected = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPT),
                    "migration",
                    "--phase",
                    "apply",
                    "--manifest",
                    str(home / "manifest.json"),
                    "--unknown",
                    private_token,
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
                timeout=30,
            )
            self.assertEqual(rejected.returncode, 2)
            self.assertEqual(rejected.stdout, "")
            self.assertNotIn(private_token, rejected.stderr)
            self.assertEqual(list(home.iterdir()), [])



if __name__ == "__main__":
    unittest.main()
