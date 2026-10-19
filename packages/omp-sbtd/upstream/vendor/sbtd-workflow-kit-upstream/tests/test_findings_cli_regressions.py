from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "sbtd-workflow-onboard" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import onboard


class FindingsCliRegressionTests(unittest.TestCase):
    def test_missing_migration_module_returns_sanitized_blocked_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "skill"
            shutil.copytree(
                SCRIPTS.parent, skill, ignore=shutil.ignore_patterns("__pycache__")
            )
            scripts = skill / "scripts"
            (scripts / "sbtd_migration_files.py").unlink()
            home = root / "home"
            home.mkdir()
            environment = os.environ.copy()
            environment.update(
                HOME=str(home), USERPROFILE=str(home), CODEX_HOME=str(home / ".codex")
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(scripts / "onboard.py"),
                    "migration",
                    "--phase",
                    "apply",
                    "--manifest",
                    str(root / "manifest.json"),
                    "--json",
                ],
                capture_output=True,
                text=True,
                env=environment,
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 2, completed.stderr)
            response = json.loads(completed.stdout)
            self.assertEqual(response["status"], "blocked")
            self.assertEqual(response["migration"], {})
            self.assertIn("runtime", response["reason"])
            self.assertNotIn("Traceback", completed.stderr)
            self.assertEqual(list(home.iterdir()), [])

    def test_installers_reject_missing_state_module_before_invoking_python(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "incomplete"
            for relative in (
                "SKILL.md",
                "REFERENCE.md",
                "catalog.json",
                "catalog.schema.json",
                "templates/agents/AGENTS.global.md",
                "templates/agents/AGENTS.project.md",
                "assets/external-skills/stable/MANIFEST.json",
                "scripts/onboard.py",
            ):
                target = source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    'print("UNEXPECTED_CLI_EXECUTION")\n'
                    if relative.endswith("onboard.py")
                    else "fixture\n"
                )
            (source / "templates/skills").mkdir()
            runners = []
            bash = shutil.which("bash")
            if bash:
                runners.append(
                    [
                        bash,
                        str(ROOT / "install.sh"),
                        "migration",
                        "--source-root",
                        str(source),
                    ]
                )
            pwsh = shutil.which("pwsh")
            if pwsh:
                runners.append(
                    [
                        pwsh,
                        "-NoProfile",
                        "-File",
                        str(ROOT / "install.ps1"),
                        "-WorkflowMode",
                        "migration",
                        "-SourceRoot",
                        str(source),
                    ]
                )
            if not runners:
                self.skipTest("no supported installer interpreter")
            for command in runners:
                with self.subTest(interpreter=command[0]):
                    completed = subprocess.run(
                        command, capture_output=True, text=True, timeout=30, check=False
                    )
                    self.assertNotEqual(completed.returncode, 0)
                    combined = completed.stdout + completed.stderr
                    self.assertIn("scripts/sbtd_project.py", combined)
                    self.assertNotIn("UNEXPECTED_CLI_EXECUTION", combined)

    def test_text_plan_reports_wiring_blocker_and_remedy(self):
        payload = {
            "mode": "plan",
            "platform": "codex",
            "operations": [],
            "graftWiring": {
                "status": "blocked",
                "reason": "foreign configuration conflict",
                "nextStep": "preserve foreign configuration and resolve ownership",
            },
        }
        stream = io.StringIO()
        with redirect_stdout(stream):
            onboard.print_plan(payload)
        self.assertIn("blocked", stream.getvalue())
        self.assertIn("foreign configuration conflict", stream.getvalue())
        self.assertIn("preserve foreign configuration", stream.getvalue())

    def test_missing_optional_runtime_is_not_an_installation_failure(self):
        runtime = {
            name: {
                "installed": False,
                "path": None,
                "version": None,
                "advice": "prepare only when needed",
            }
            for name in ("npm", "node", "nvm")
        }
        runtime["advice"] = "prepare only when needed"
        report = onboard.build_installation_report(
            {
                "runtime": runtime,
                "tools": [],
                "skills": [],
                "manualChecks": [],
            }
        )
        self.assertEqual(report["failedOrMissing"]["runtime"], [])
        self.assertEqual(report["summary"]["failedOrMissing"], 0)
        self.assertEqual(
            {entry["name"] for entry in report["conditionalRuntime"]},
            {"npm", "node", "nvm"},
        )
        self.assertTrue(
            all(
                entry["status"] == "conditional"
                for entry in report["conditionalRuntime"]
            )
        )

    def test_late_wiring_conflict_keeps_blocked_exit_and_partial_setup_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            home = root / "home"
            home.mkdir()
            environment = {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "CODEX_HOME": str(home / ".codex"),
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
            }
            args = onboard.build_parser().parse_args(
                [
                    "init-projects",
                    "--projects-root",
                    str(project),
                    "--skip-project-agents",
                    "--yes",
                    "--json",
                ]
            )
            stream = io.StringIO()
            with (
                mock.patch.dict(os.environ, environment),
                mock.patch(
                    "sbtd_graft_deployment.plan_normal_wiring",
                    return_value={"status": "planned"},
                ),
                mock.patch(
                    "sbtd_graft_deployment.execute_normal_wiring",
                    return_value=(
                        {
                            "status": "blocked",
                            "reason": "configuration changed after planning",
                        },
                        2,
                    ),
                ),
                redirect_stdout(stream),
            ):
                code = onboard.run("init-projects", args)
            self.assertEqual(code, 2)
            report = json.loads(stream.getvalue())
            self.assertEqual(report["sbtdProjectSetup"]["status"], "blocked")
            self.assertTrue((project / ".gitignore").is_file())
            self.assertTrue(report["operationResults"])


if __name__ == "__main__":
    unittest.main()
