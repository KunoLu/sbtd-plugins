from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CodexDeploymentCliTests(unittest.TestCase):
    def test_invalid_deployment_context_is_rejected_before_normal_init_side_effects(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            home, project, evidence = (
                base / name for name in ("home", "project", "evidence")
            )
            for path in (home, project, evidence):
                path.mkdir(mode=0o700)
            (project / "user.txt").write_bytes(b"user content remains\n")
            (evidence / "manifest.json").write_text("{}")
            (evidence / "apply.json").write_text("{}")
            before = {
                str(path.relative_to(base)): path.read_bytes()
                for path in base.rglob("*")
                if path.is_file()
            }
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "sbtd-workflow-onboard/scripts/onboard.py"),
                    "init",
                    "--platform",
                    "codex",
                    "--projects-root",
                    str(project),
                    "--migration-manifest",
                    str(evidence / "manifest.json"),
                    "--migration-apply-receipt",
                    str(evidence / "apply.json"),
                    "--deployment-evidence-out",
                    str(evidence / "new-deployment.json"),
                    "--yes",
                    "--json",
                ],
                env={
                    **os.environ,
                    "HOME": str(home),
                    "USERPROFILE": str(home),
                    "CODEX_HOME": str(home / ".codex"),
                    "AGENT_SKILLS_DIR": str(home / ".agent/skills"),
                },
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(completed.returncode, 2, completed.stderr)
            response = json.loads(completed.stdout)
            self.assertEqual(response["mode"], "init")
            self.assertEqual(response["status"], "blocked")
            self.assertIsNone(response["deploymentEvidence"])
            self.assertEqual(
                {
                    str(path.relative_to(base)): path.read_bytes()
                    for path in base.rglob("*")
                    if path.is_file()
                },
                before,
            )
            self.assertEqual(list(home.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
