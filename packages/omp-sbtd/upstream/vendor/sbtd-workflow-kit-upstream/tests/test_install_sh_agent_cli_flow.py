from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = ROOT / "install.sh"
INSTALL_PS1 = ROOT / "install.ps1"
SOURCE_ROOT = ROOT / "sbtd-workflow-onboard"


class BashInstallerAgentCliFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="sbtd-install-sh-test-")
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.state_dir = self.root / "state"
        self.state_dir.mkdir()
        self.project_root = self.root / "project"
        self.project_root.mkdir()
        self.project_root_two = self.root / "project-two"
        self.project_root_two.mkdir()
        self.log_path = self.root / "onboard-modes.log"
        self.args_log_path = self.root / "onboard-args.log"
        self.env = os.environ.copy()
        self.env["PATH"] = os.pathsep.join(
            (str(self.bin_dir), os.environ.get("PATH", ""))
        )
        self.env["REAL_PYTHON"] = sys.executable
        self.env["FAKE_STATE_DIR"] = str(self.state_dir)
        self.env["FAKE_ONBOARD_LOG"] = str(self.log_path)
        self.env["FAKE_ONBOARD_ARGS_LOG"] = str(self.args_log_path)
        self.env["FAKE_PROJECT_ROOT"] = str(self.project_root)
        self.write_fake_python()

    def write_executable(self, path: Path, body: str) -> None:
        path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        if os.name != "nt":
            return
        bash = shutil.which("bash")
        if bash is None:
            return
        path.with_name(f"{path.name}.cmd").write_text(
            f'@echo off\r\n"{bash}" "{path}" %*\r\n',
            encoding="ascii",
        )

    def fake_onboard_python_body(self) -> str:
        return """
            #!/bin/sh
            if [ "$1" = "-" ]; then
              exec "$REAL_PYTHON" "$@"
            fi

            mode="$2"
            printf '%s\n' "$mode" >> "$FAKE_ONBOARD_LOG"
            printf '%s\n' "$*" >> "$FAKE_ONBOARD_ARGS_LOG"
            npm_installed=false
            agent_installed=false
            external_installed=true
            graft_installed=false
            graft_status=not-available
            graft_reason='Graft CLI is not installed.'
            graft_next='Confirm the installer plan to install @nanonets/graft@0.18.0.'
            [ -f "$FAKE_STATE_DIR/npm" ] && npm_installed=true
            [ -f "$FAKE_STATE_DIR/agent" ] && agent_installed=true
            [ -f "$FAKE_STATE_DIR/external-missing" ] && external_installed=false
            if [ -f "$FAKE_STATE_DIR/graft" ]; then
              graft_installed=true
              graft_status=available
              graft_reason=''
              graft_next=''
            elif [ -f "$FAKE_STATE_DIR/graft-blocked" ]; then
              graft_status=blocked
              graft_reason='A conflicting executable already provides this command.'
              graft_next='Remove the conflicting executable, then rerun the installer.'
            fi

            case "$mode" in
              check-agent-cli)
                printf '{"mode":"check-agent-cli","platform":"codex","label":"Codex","command":"codex","installed":%s,"npmPackage":"@openai/codex","installCommand":"npm install -g @openai/codex@latest","runtime":{"npm":{"installed":%s}}}\n' "$agent_installed" "$npm_installed"
                ;;
              ensure-npm)
                : > "$FAKE_STATE_DIR/npm"
                printf '{"status":"installed"}\n'
                ;;
              install-agent-cli)
                if [ ! -f "$FAKE_STATE_DIR/npm" ]; then
                  printf '{"status":"npm-required"}\n'
                  exit 2
                fi
                : > "$FAKE_STATE_DIR/agent"
                printf '{"status":"installed"}\n'
                ;;
              install-graft)
                confirmed=false
                telemetry_only=false
                for arg in "$@"; do
                  [ "$arg" = "--yes" ] && confirmed=true
                  [ "$arg" = "--telemetry-only" ] && telemetry_only=true
                done
                  if [ "$confirmed" = false ] && [ -f "$FAKE_STATE_DIR/graft-telemetry-only" ]; then
                    printf '{"mode":"install-graft","status":"needs-confirmation","reason":"persist telemetry opt-out only","plan":{"telemetry":{"path":"/tmp/fake-home/.graft/telemetry.json","changes":{"enabled":false}}},"before":{"installed":true}}\n'
                    exit 2
                  fi
                if [ "$confirmed" = false ]; then
                  if [ -f "$FAKE_STATE_DIR/graft" ]; then
                    printf '{"mode":"install-graft","status":"already-installed","reason":"pinned Graft CLI already verified usable","plan":{},"before":{"installed":true}}\n'
                    exit 0
                  fi
                  if [ -f "$FAKE_STATE_DIR/graft-blocked" ]; then
                    printf '{"mode":"install-graft","status":"blocked","stage":"conflict","reason":"an unrecognized graft executable already occupies PATH","plan":{},"before":{}}\n'
                    exit 2
                  fi
                  if [ ! -f "$FAKE_STATE_DIR/npm" ]; then
                    printf '{"mode":"install-graft","status":"blocked","stage":"npm","reason":"npm is required for the global install but was not found","plan":{},"before":{}}\n'
                    exit 2
                  fi
                  printf '{"mode":"install-graft","status":"needs-confirmation","reason":"explicit confirmation is required before any download, install, or telemetry write; no changes were made","plan":{"package":"@nanonets/graft@0.18.0","prefix":"/tmp/fake-prefix","telemetry":{"path":"/tmp/fake-home/.graft/telemetry.json","changes":{"enabled":false}}},"before":{"installed":false}}\n'
                  exit 2
                fi
                if [ "$telemetry_only" = true ]; then
                  : > "$FAKE_STATE_DIR/telemetry-disabled"
                  printf '{"mode":"install-graft","status":"already-installed"}\n'
                  exit 0
                fi
                if [ -f "$FAKE_STATE_DIR/graft-fails" ]; then
                  printf '{"mode":"install-graft","status":"failed","stage":"npm-install","reason":"npm exited 1"}\n'
                  exit 1
                fi
                : > "$FAKE_STATE_DIR/graft"
                printf '{"mode":"install-graft","status":"installed"}\n'
                ;;
              check)
                json=false
                for arg in "$@"; do
                  [ "$arg" = "--json" ] && json=true
                done
                if [ "$json" = true ]; then
                  if [ -f "$FAKE_STATE_DIR/ponytail-conflict" ]; then
                    printf '{"runtime":{"npm":{"installed":true}},"tools":[],"skills":[],"manualChecks":[],"ponytailProvider":{"provider":"conflict"}}\\n'
                    exit 4
                  fi
                  printf '{"runtime":{"npm":{"installed":%s}},"tools":[{"name":"rtk","installed":true},{"name":"trellis","installed":true},{"name":"graft","category":"cli","installed":%s,"version":"0.18.0","pinnedVersion":"0.18.0","status":"%s","reason":"%s","nextStep":"%s"},{"name":"java","installed":true},{"name":"maestro","installed":true}],"skills":[{"name":"caveman","installed":true},{"name":"diagnosing-bugs","group":"referenced","installed":%s}],"manualChecks":[]}\n' "$npm_installed" "$graft_installed" "$graft_status" "$graft_reason" "$graft_next" "$external_installed"
                else
                  printf 'preflight check\n'
                fi
                ;;
              install-external-skills)
                rm -f "$FAKE_STATE_DIR/external-missing"
                printf 'external skills installed\n'
                ;;
              install-playwright-cli)
                printf 'playwright installed\n'
                ;;
              check-projects)
                if [ -f "$FAKE_STATE_DIR/react-bits-applicable" ]; then
                  printf '{"mode":"check-projects","projects":[{"projectRoot":"%s","playwright":{"applicable":false,"installed":false},"reactBits":{"applicable":true}}]}\n' "$FAKE_PROJECT_ROOT"
                elif [ -f "$FAKE_STATE_DIR/playwright-applicable" ]; then
                  printf '{"mode":"check-projects","projects":[{"projectRoot":"%s","playwright":{"applicable":true,"installed":false},"reactBits":{"applicable":false}}]}\n' "$FAKE_PROJECT_ROOT"
                else
                  printf '{"mode":"check-projects","projects":[]}\n'
                fi
                ;;
              plan)
                printf 'plan\n'
                ;;
              init|reset|init-projects)
                printf '%s complete\n' "$mode"
                ;;
              migration|recovery)
                printf '{"mode":"%s","status":"forwarded"}\n' "$mode"
                if [ -n "${FAKE_FORWARD_RC:-}" ]; then
                  exit "$FAKE_FORWARD_RC"
                fi
                ;;
              *)
                printf 'unexpected fake mode: %s\n' "$mode" >&2
                exit 1
                ;;
            esac
            """

    def write_fake_python(self) -> None:
        self.write_executable(
            self.bin_dir / "python3",
            self.fake_onboard_python_body(),
        )

    def run_installer(
        self,
        user_input: str = "",
        action: str = "init",
        projects_only: bool = False,
        platform: str = "codex",
        yes: bool = True,
        no_mcp: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        project_args = (
            ("--init-projects", str(self.project_root))
            if projects_only
            else (
                "--projects-root",
                str(self.project_root),
                "--action",
                action,
            )
        )
        optional_args = []
        if yes:
            optional_args.append("--yes")
        if no_mcp:
            optional_args.append("--no-mcp")
        return subprocess.run(
            (
                "/bin/bash",
                str(INSTALL_SH),
                "--platform",
                platform,
                "--source-root",
                str(SOURCE_ROOT),
                *project_args,
                "--skip-project-agents",
                *optional_args,
                "--no-color",
            ),
            input=user_input,
            check=False,
            capture_output=True,
            text=True,
            env=self.env,
            timeout=30,
        )

    def modes(self) -> list[str]:
        return self.log_path.read_text(encoding="utf-8").splitlines()

    def invocation_args(self) -> list[str]:
        return self.args_log_path.read_text(encoding="utf-8").splitlines()

    def run_workflow_mode(
        self, mode: str, *args: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (
                "/bin/bash",
                str(INSTALL_SH),
                mode,
                "--source-root",
                str(SOURCE_ROOT),
                *args,
            ),
            check=False,
            capture_output=True,
            text=True,
            env=self.env,
            timeout=30,
        )

    def test_migration_and_recovery_forward_without_installer_side_effects(
        self,
    ) -> None:
        for mode in ("migration", "recovery"):
            with self.subTest(mode=mode):
                self.log_path.write_text("", encoding="utf-8")
                self.args_log_path.write_text("", encoding="utf-8")
                completed = self.run_workflow_mode(
                    mode,
                    "--phase",
                    "plan" if mode == "recovery" else "cleanup",
                    "--confirm-recovery" if mode == "recovery" else "--confirm-cleanup",
                    "abc123",
                    "--json",
                )

                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(completed.stderr, "")
                self.assertEqual(
                    completed.stdout,
                    '{"mode":"' + mode + '","status":"forwarded"}\n',
                )
                self.assertEqual(self.modes(), [mode])
                forwarded = self.invocation_args()[-1]
                self.assertIn(f"onboard.py {mode}", forwarded)
                self.assertIn("--json", forwarded)
                self.assertNotIn("--source-root", forwarded)

    def test_workflow_forwarding_supports_equals_source_root_and_exit_code(
        self,
    ) -> None:
        self.env["FAKE_FORWARD_RC"] = "3"
        completed = subprocess.run(
            (
                "/bin/bash",
                str(INSTALL_SH),
                "migration",
                f"--source-root={SOURCE_ROOT}",
                "--phase",
                "plan",
                "--json",
            ),
            check=False,
            capture_output=True,
            text=True,
            env=self.env,
            timeout=30,
        )

        self.assertEqual(completed.returncode, 3, completed.stderr)
        self.assertEqual(
            completed.stdout, '{"mode":"migration","status":"forwarded"}\n'
        )
        forwarded = self.invocation_args()[-1]
        self.assertIn("onboard.py migration", forwarded)
        self.assertNotIn("--source-root", forwarded)

    def test_bash_workflow_mode_requires_lowercase(self) -> None:
        completed = self.run_workflow_mode("MIGRATION", "--phase", "plan")

        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(self.log_path.exists())

    def test_startup_banner_displays_kuno_welcome_panel_after_blank_line(self) -> None:
        completed = self.run_installer(projects_only=True)

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        left_width = 42
        right_width = 46
        title = "─── SBTD Workflow Installer "
        logos = (
            "██╗  ██╗██╗   ██╗███╗   ██╗ ██████╗",
            "██║ ██╔╝██║   ██║████╗  ██║██╔═══██╗",
            "█████╔╝ ██║   ██║██╔██╗ ██║██║   ██║",
            "██╔═██╗ ██║   ██║██║╚██╗██║██║   ██║",
            "██║  ██╗╚██████╔╝██║ ╚████║╚██████╔╝",
            "╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝",
        )
        tips = (
            "Tips",
            "--platform <agent>       Target Agent",
            "--projects-root <paths>  Set project roots",
            "--init-projects <paths>  Project-only mode",
            "--action <init|reset>    Select workflow",
            "--dry-run                Preview changes",
        )
        expected_panel = "\n" + "\n".join(
            (
                "╭" + title + "─" * (left_width + 1 + right_width - len(title)) + "╮",
                *(
                    "│"
                    + logo.center(left_width)
                    + "│"
                    + ("  " + tip).ljust(right_width)
                    + "│"
                    for logo, tip in zip(logos, tips)
                ),
                "╰" + "─" * left_width + "┴" + "─" * right_width + "╯",
            )
        )

        self.assertTrue(completed.stdout.startswith(expected_panel + "\n"))
        self.assertEqual(
            {len(line) for line in expected_panel.splitlines()[1:]},
            {91},
        )

    def test_color_detection_does_not_shadow_no_color_environment(self) -> None:
        source = INSTALL_SH.read_text(encoding="utf-8")

        self.assertIn("NO_COLOR_REQUESTED=0", source)
        self.assertIn('"$NO_COLOR_REQUESTED" -eq 0', source)
        self.assertIn('-z "${NO_COLOR:-}"', source)
        self.assertNotIn("\nNO_COLOR=0\n", source)

    def test_closed_stdin_supports_help_and_noninteractive_project_mode(self) -> None:
        invocations = (
            ("/bin/bash", str(INSTALL_SH), "--help"),
            (
                "/bin/bash",
                str(INSTALL_SH),
                "--platform",
                "codex",
                "--source-root",
                str(SOURCE_ROOT),
                "--init-projects",
                str(self.project_root),
                "--no-mcp",
                "--yes",
                "--no-color",
            ),
        )

        for invocation in invocations:
            with self.subTest(invocation=invocation):
                completed = subprocess.run(
                    (
                        "/bin/bash",
                        "-c",
                        'exec 0<&-; exec "$@"',
                        "_",
                        *invocation,
                    ),
                    check=False,
                    capture_output=True,
                    text=True,
                    env=self.env,
                    timeout=30,
                )

                self.assertEqual(
                    completed.returncode,
                    0,
                    completed.stderr or completed.stdout,
                )
                self.assertNotIn("Bad file descriptor", completed.stderr)
        self.assertNotIn("--skip-project-agents", self.invocation_args())

    def test_existing_target_cli_is_checked_before_general_preflight(self) -> None:
        (self.state_dir / "npm").touch()
        (self.state_dir / "agent").touch()

        completed = self.run_installer()

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        modes = self.modes()
        self.assertEqual(modes[0], "check-agent-cli")
        self.assertLess(modes.index("check-agent-cli"), modes.index("check"))
        self.assertNotIn("ensure-npm", modes)
        self.assertNotIn("install-agent-cli", modes)

    def test_reset_uses_the_same_early_target_agent_gate(self) -> None:
        (self.state_dir / "npm").touch()
        (self.state_dir / "agent").touch()

        completed = self.run_installer(action="reset")

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        modes = self.modes()
        self.assertEqual(modes[0], "check-agent-cli")
        self.assertLess(modes.index("check-agent-cli"), modes.index("check"))
        self.assertIn("reset", modes)

    def test_agent_platform_is_forwarded_to_onboarding_operations(
        self,
    ) -> None:
        (self.state_dir / "npm").touch()
        (self.state_dir / "agent").touch()

        completed = self.run_installer(platform="claude")

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        init_invocation = next(
            arguments
            for arguments in self.invocation_args()
            if arguments.split()[1] == "init"
        )
        args = init_invocation.split()
        self.assertIn("--platform", args)
        self.assertEqual(args[args.index("--platform") + 1], "claude")

    def test_init_projects_skips_all_global_checks_and_installers(self) -> None:
        completed = self.run_installer(projects_only=True)

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        modes = self.modes()
        self.assertIn("check-projects", modes)
        self.assertIn("init-projects", modes)
        self.assertNotIn("check-agent-cli", modes)
        self.assertNotIn("check", modes)
        self.assertNotIn("ensure-npm", modes)
        self.assertNotIn("install-agent-cli", modes)
        self.assertNotIn("install-external-skills", modes)
        self.assertNotIn("install-graft", modes)

    def test_yes_without_projects_root_is_global_only(self) -> None:
        home = self.root / "global-only-home"
        home.mkdir()
        environment = {**self.env, "HOME": str(home), "USERPROFILE": str(home)}
        completed = subprocess.run(
            [
                "/bin/bash", str(INSTALL_SH),
                "--platform", "codex", "--source-root", str(SOURCE_ROOT),
                "--yes", "--action", "init", "--no-mcp", "--no-color",
            ],
            cwd=self.project_root,
            input="",
            capture_output=True,
            text=True,
            env=environment,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertIn("Project roots: <none>", completed.stdout)
        self.assertIn("Project AGENTS: skip", completed.stdout)
        self.assertNotIn("check-projects", self.modes())
        self.assertTrue(all("--projects-root" not in args for args in self.invocation_args()))
        self.assertFalse((self.project_root / "AGENTS.md").exists())
        self.assertFalse((self.project_root / ".gitignore").exists())

    def test_yes_installs_optional_project_tool_without_prompting(self) -> None:
        (self.state_dir / "playwright-applicable").touch()

        completed = self.run_installer(projects_only=True)

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertIn("install-playwright-cli", self.modes())

    def test_init_projects_react_bits_choice_reads_original_user_input(self) -> None:
        (self.state_dir / "react-bits-applicable").touch()

        completed = subprocess.run(
            (
                "/bin/bash",
                str(INSTALL_SH),
                "--source-root",
                str(SOURCE_ROOT),
                "--init-projects",
                str(self.project_root),
                "--no-mcp",
                "--yes",
                "--no-color",
            ),
            input="1\n1\n",
            check=False,
            capture_output=True,
            text=True,
            env=self.env,
            timeout=3,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertIn("React Bits decision", completed.stderr)
        self.assertNotIn("Invalid choice.", completed.stderr)

    def test_paid_react_bits_skill_is_moved_to_project_agent_skills(self) -> None:
        (self.state_dir / "react-bits-applicable").touch()
        self.env["REACTBITS_LICENSE_KEY"] = "test-license-key"
        self.write_executable(
            self.bin_dir / "npx",
            """
            #!/bin/sh
            target="."
            while [ "$#" -gt 0 ]; do
              if [ "$1" = "--path" ]; then
                target="$2"
                shift 2
                continue
              fi
              shift
            done
            mkdir -p "$target"
            printf '%s\n' 'new react bits skill' > "$target/SKILL.md"
            """,
        )
        target = (
            self.project_root / ".agents" / "skills" / "react-bits-pro" / "SKILL.md"
        )
        target.parent.mkdir(parents=True)
        target.write_text("old react bits skill\n", encoding="utf-8")

        completed = subprocess.run(
            (
                "/bin/bash",
                str(INSTALL_SH),
                "--source-root",
                str(SOURCE_ROOT),
                "--init-projects",
                str(self.project_root),
                "--no-mcp",
                "--yes",
                "--no-color",
            ),
            input="1\ny\n3\n",
            check=False,
            capture_output=True,
            text=True,
            env=self.env,
            timeout=3,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertEqual(target.read_text(encoding="utf-8"), "new react bits skill\n")
        self.assertFalse((self.project_root / "SKILL.md").exists())
        self.assertEqual(list(target.parent.glob("SKILL.md.*")), [])

    def test_omitted_projects_root_prompts_for_and_forwards_multiple_absolute_paths(
        self,
    ) -> None:
        (self.state_dir / "npm").touch()
        (self.state_dir / "agent").touch()
        projects_csv = f"{self.project_root},{self.project_root_two}"
        canonical_projects_csv = (
            f"{self.project_root.resolve()},{self.project_root_two.resolve()}"
        )

        completed = subprocess.run(
            (
                "/bin/bash",
                str(INSTALL_SH),
                "--platform",
                "codex",
                "--source-root",
                str(SOURCE_ROOT),
                "--action",
                "init",
                "--skip-project-agents",
                "--no-mcp",
                "--no-color",
            ),
            input=f"n\n{projects_csv}\nn\ny\n",
            check=False,
            capture_output=True,
            text=True,
            env=self.env,
            timeout=30,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        init_invocation = next(
            line for line in self.invocation_args() if line.split()[1:2] == ["init"]
        )
        self.assertIn(f"--projects-root {canonical_projects_csv}", init_invocation)

    def test_bash_public_flags_use_plural_projects_contract(self) -> None:
        completed = subprocess.run(
            ("/bin/bash", str(INSTALL_SH), "--help"),
            check=False,
            capture_output=True,
            text=True,
            env=self.env,
            timeout=30,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--projects-root", completed.stdout)
        self.assertIn("--init-projects", completed.stdout)
        self.assertNotIn("--project-root", completed.stdout)
        self.assertNotIn("--skills-scope", completed.stdout)
        self.assertNotIn("--project-skills-dir", completed.stdout)
        self.assertNotIn("--trellis", completed.stdout)

    def powershell_environment(self) -> tuple[str, dict[str, str]]:
        runtime = os.environ.get("SBTD_TEST_PWSH") or shutil.which("pwsh")
        if runtime is None:
            self.skipTest("PowerShell runtime is not available")
        home = self.root / "powershell-home"
        home.mkdir()
        environment = {
            **self.env,
            "HOME": str(home),
            "USERPROFILE": str(home),
            "XDG_CONFIG_HOME": str(home / "config"),
            "XDG_CACHE_HOME": str(home / "cache"),
            "XDG_DATA_HOME": str(home / "data"),
            "DOTNET_CLI_HOME": str(home),
            "POWERSHELL_TELEMETRY_OPTOUT": "1",
            "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
        return runtime, environment

    def test_powershell_rejects_unknown_parameters_before_help(self) -> None:
        runtime, environment = self.powershell_environment()
        command = [
            runtime,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(INSTALL_PS1),
            "-Help",
        ]
        valid = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            timeout=30,
            check=False,
        )
        self.assertEqual(valid.returncode, 0, valid.stderr)
        rejected = subprocess.run(
            [*command, "-TrellisUser", "synthetic"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            timeout=30,
            check=False,
        )
        self.assertNotEqual(
            rejected.returncode, 0, "Retired parameter was silently accepted"
        )

    def test_powershell_project_only_installs_assets_without_global_commands(
        self,
    ) -> None:
        runtime, environment = self.powershell_environment()
        for name in ("python", "python3"):
            self.write_executable(
                self.bin_dir / name,
                '#!/bin/sh\nexec "$REAL_PYTHON" "$@"\n',
            )
        forbidden = self.root / "forbidden-global-commands"
        environment["FORBIDDEN_COMMANDS"] = str(forbidden)
        for name in (
            "npm",
            "npx",
            "codex",
            "omp",
            "trellis",
            "gitnexus",
            "rtk",
            "maestro",
        ):
            body = '#!/bin/sh\nprintf invoked >> "$FORBIDDEN_COMMANDS"\nexit 99\n'
            if name == "npm":
                body = (
                    "#!/bin/sh\n"
                    'if [ "$1" = "root" ] && [ "$2" = "-g" ]; then\n'
                    '  mkdir -p "$FAKE_STATE_DIR/npm-global"\n'
                    '  printf "%s\\n" "$FAKE_STATE_DIR/npm-global"\n'
                    "  exit 0\n"
                    "fi\n"
                    'printf invoked >> "$FORBIDDEN_COMMANDS"\n'
                    "exit 99\n"
                )
            self.write_executable(self.bin_dir / name, body)
        completed = subprocess.run(
            [
                runtime,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(INSTALL_PS1),
                "-SourceRoot",
                str(SOURCE_ROOT),
                "-Platform",
                "codex",
                "-InitProjects",
                str(self.project_root),
                "-NoMcp",
                "-NoColor",
                "-Yes",
            ],
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertFalse(forbidden.exists())
        self.assertFalse((Path(environment["HOME"]) / ".codex").exists())
        self.assertFalse((Path(environment["HOME"]) / ".omp").exists())

    def scaffold_conflict_environment(self) -> dict[str, str]:
        home = self.root / "preflight-home"
        home.mkdir()
        external = self.root / "preserved-ignore"
        external.write_text("preserve\n", encoding="utf-8")
        (self.project_root / ".gitignore").symlink_to(external)
        (self.project_root / "package.json").write_text(
            '{"dependencies":{"react":"18.3.1"}}', encoding="utf-8"
        )
        (self.project_root / "components.json").write_text("{}", encoding="utf-8")
        environment = {
            **self.env,
            "HOME": str(home),
            "USERPROFILE": str(home),
            "CODEX_HOME": str(home / ".codex"),
            "XDG_CONFIG_HOME": str(home / "config"),
            "XDG_CACHE_HOME": str(home / "cache"),
            "XDG_DATA_HOME": str(home / "data"),
            "DOTNET_CLI_HOME": str(home),
            "POWERSHELL_TELEMETRY_OPTOUT": "1",
            "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
            "MUTATION_LOG": str(self.root / "unexpected-mutation"),
        }
        for name in ("python", "python3"):
            self.write_executable(
                self.bin_dir / name,
                """
                #!/bin/sh
                if [ "$1" = "-" ]; then exec "$REAL_PYTHON" "$@"; fi
                case "$2" in
                  check|check-projects|check-agent-cli|plan) exec "$REAL_PYTHON" "$@" ;;
                  *) : > "$MUTATION_LOG"; exit 99 ;;
                esac
                """,
            )
        for name in (
            "node",
            "npm",
            "codex",
            "omp",
            "npx",
            "rtk",
            "gitnexus",
            "maestro",
            "git",
        ):
            self.write_executable(
                self.bin_dir / name,
                """
                #!/bin/sh
                if [ "$1" = "--version" ] || [ "$1" = "-v" ]; then printf '22.0.0\\n'; exit 0; fi
                printf '%s\\n' "$0 $*" > "$MUTATION_LOG"
                exit 99
                """,
            )
        return environment

    def test_bash_full_preflight_precedes_global_and_optional_mutations(self) -> None:
        environment = self.scaffold_conflict_environment()
        for mode in ("normal", "project-only"):
            with self.subTest(mode=mode):
                scope = (
                    ["--projects-root", str(self.project_root), "--action", "init"]
                    if mode == "normal"
                    else ["--init-projects", str(self.project_root)]
                )
                completed = subprocess.run(
                    [
                        "/bin/bash",
                        str(INSTALL_SH),
                        "--source-root",
                        str(SOURCE_ROOT),
                        "--platform",
                        "codex",
                        "--no-mcp",
                        "--no-color",
                        "--yes",
                        *scope,
                    ],
                    input="2\nfixture-registry/button\n",
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                self.assertEqual(completed.returncode, 2, completed.stderr)
                mutation_log = Path(environment["MUTATION_LOG"])
                self.assertFalse(
                    mutation_log.exists(),
                    mutation_log.read_text(encoding="utf-8")
                    if mutation_log.exists()
                    else "",
                )
                self.assertTrue((self.project_root / ".gitignore").is_symlink())
                self.assertFalse((self.project_root / "AGENTS.md").exists())
                self.assertEqual(
                    (self.root / "preserved-ignore").read_text(), "preserve\n"
                )

    def test_powershell_full_preflight_precedes_global_and_optional_mutations(
        self,
    ) -> None:
        runtime = os.environ.get("SBTD_TEST_PWSH") or shutil.which("pwsh")
        if runtime is None:
            self.skipTest("PowerShell runtime is not available")
        environment = self.scaffold_conflict_environment()
        for mode in ("normal", "project-only"):
            with self.subTest(mode=mode):
                scope = (
                    ["-ProjectsRoot", str(self.project_root), "-Action", "init"]
                    if mode == "normal"
                    else ["-InitProjects", str(self.project_root)]
                )
                completed = subprocess.run(
                    [
                        runtime,
                        "-NoProfile",
                        "-NonInteractive",
                        "-File",
                        str(INSTALL_PS1),
                        "-SourceRoot",
                        str(SOURCE_ROOT),
                        "-Platform",
                        "codex",
                        "-NoMcp",
                        "-NoColor",
                        "-Yes",
                        *scope,
                    ],
                    env=environment,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                    check=False,
                )
                self.assertEqual(completed.returncode, 2, completed.stderr)
                mutation_log = Path(environment["MUTATION_LOG"])
                self.assertFalse(
                    mutation_log.exists(),
                    mutation_log.read_text(encoding="utf-8")
                    if mutation_log.exists()
                    else "",
                )
                self.assertTrue((self.project_root / ".gitignore").is_symlink())
                self.assertFalse((self.project_root / "AGENTS.md").exists())
                self.assertEqual(
                    (self.root / "preserved-ignore").read_text(), "preserve\n"
                )

    def test_root_installers_delegate_external_source_selection_to_onboard(
        self,
    ) -> None:
        bash_source = INSTALL_SH.read_text(encoding="utf-8")
        powershell_source = INSTALL_PS1.read_text(encoding="utf-8")

        self.assertNotIn("EXTERNAL_SKILLS=(", bash_source)
        self.assertNotIn("$ExternalSkills = @(", powershell_source)
        self.assertIn("--source auto", bash_source)
        self.assertIn('"--source", "auto"', powershell_source)

    def test_bash_installs_missing_referenced_skills_with_auto_source(self) -> None:
        (self.state_dir / "npm").touch()
        (self.state_dir / "agent").touch()
        (self.state_dir / "external-missing").touch()

        completed = self.run_installer()

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        invocation = next(
            line
            for line in self.invocation_args()
            if line.split()[1:2] == ["install-external-skills"]
        )
        self.assertIn("--skills diagnosing-bugs", invocation)
        self.assertIn("--scope global --source auto --yes", invocation)

    def test_working_target_cli_skips_npm_bootstrap_and_optional_graft(
        self,
    ) -> None:
        (self.state_dir / "agent").touch()

        completed = self.run_installer()

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        modes = self.modes()
        self.assertEqual(modes[0], "check-agent-cli")
        self.assertNotIn("ensure-npm", modes)
        self.assertEqual(modes.count("install-graft"), 1)  # read-only probe only
        self.assertIn("Graft CLI is blocked", completed.stderr)

    def test_graft_install_shows_plan_and_delegates_to_onboard(self) -> None:
        (self.state_dir / "npm").touch()
        (self.state_dir / "agent").touch()
        npm_log = self.root / "npm.log"
        self.env["FAKE_NPM_LOG"] = str(npm_log)
        self.write_executable(
            self.bin_dir / "npm",
            """
            #!/bin/sh
            printf '%s\n' "$*" >> "$FAKE_NPM_LOG"
            if [ "$1" = "config" ]; then printf '/tmp/fake-prefix\n'; fi
            exit 0
            """,
        )

        completed = self.run_installer()

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertIn("@nanonets/graft@0.18.0", completed.stdout)
        self.assertIn("npm global prefix /tmp/fake-prefix", completed.stdout)
        self.assertIn("/tmp/fake-home/.graft/telemetry.json", completed.stdout)
        self.assertEqual(self.modes().count("install-graft"), 2)  # probe + confirmed
        self.assertTrue((self.state_dir / "graft").exists())
        self.assertFalse(
            npm_log.exists(),
            "wrapper must not run npm directly; the Python probe owns the plan",
        )

    def test_graft_existing_cli_requests_only_telemetry_consent(self) -> None:
        (self.state_dir / "npm").touch()
        (self.state_dir / "agent").touch()
        (self.state_dir / "graft-telemetry-only").touch()
        completed = self.run_installer()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("telemetry opt-out plan", completed.stdout)
        self.assertIn("no package install", completed.stdout)
        self.assertNotIn("Graft CLI install plan:", completed.stdout)
        self.assertTrue((self.state_dir / "telemetry-disabled").exists())
        self.assertFalse((self.state_dir / "graft").exists())

    def test_powershell_existing_graft_requests_only_telemetry_consent(self) -> None:
        runtime, environment = self.powershell_fake_onboard_environment()
        (self.state_dir / "npm").touch()
        (self.state_dir / "agent").touch()
        (self.state_dir / "graft-telemetry-only").touch()
        completed = self.run_powershell_installer(runtime, environment)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("telemetry opt-out plan", completed.stdout)
        self.assertIn("no package install", completed.stdout)
        self.assertNotIn("Graft CLI install plan:", completed.stdout)
        self.assertTrue((self.state_dir / "telemetry-disabled").exists())
        self.assertFalse((self.state_dir / "graft").exists())

    def test_graft_decline_continues_onboarding_without_install(self) -> None:
        (self.state_dir / "npm").touch()
        (self.state_dir / "agent").touch()

        completed = self.run_installer(user_input="n\ny\n", yes=False)

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        modes = self.modes()
        self.assertEqual(modes.count("install-graft"), 1)  # read-only probe only
        self.assertIn("init", modes)
        self.assertFalse((self.state_dir / "graft").exists())
        self.assertIn("declined", completed.stdout)

    def test_graft_confirmed_failure_aborts_with_nonzero_exit(self) -> None:
        (self.state_dir / "npm").touch()
        (self.state_dir / "agent").touch()
        (self.state_dir / "graft-fails").touch()

        completed = self.run_installer()

        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        modes = self.modes()
        self.assertEqual(modes.count("install-graft"), 2)  # probe + confirmed
        self.assertNotIn("init", modes)
        self.assertFalse((self.state_dir / "graft").exists())

    def test_graft_blocked_conflict_is_reported_without_overwrite(self) -> None:
        (self.state_dir / "npm").touch()
        (self.state_dir / "agent").touch()
        (self.state_dir / "graft-blocked").touch()

        completed = self.run_installer()

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertIn("Graft CLI is blocked", completed.stderr)
        self.assertIn("left untouched", completed.stderr)
        self.assertEqual(self.modes().count("install-graft"), 1)  # probe only
        self.assertFalse((self.state_dir / "graft").exists())

    def test_graft_already_installed_skips_reinstall(self) -> None:
        (self.state_dir / "npm").touch()
        (self.state_dir / "agent").touch()
        (self.state_dir / "graft").touch()

        completed = self.run_installer()

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertIn("already installed and usable", completed.stdout)
        self.assertEqual(self.modes().count("install-graft"), 1)  # read-only probe only

    def test_retired_gitnexus_menu_option_now_selects_custom_stdio(self) -> None:
        (self.state_dir / "npm").touch()
        (self.state_dir / "agent").touch()
        codex_log = self.root / "codex.log"
        self.env["FAKE_CODEX_LOG"] = str(codex_log)
        self.write_executable(
            self.bin_dir / "codex",
            """
            #!/bin/sh
            printf '%s\n' "$*" >> "$FAKE_CODEX_LOG"
            exit 0
            """,
        )
        answers = "n\n\n4\ncustom-echo\necho\n\n\ny\n"

        completed = self.run_installer(user_input=answers, yes=False, no_mcp=False)

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertIn("4) Custom stdio MCP server", completed.stdout)
        self.assertNotIn("GitNexus MCP", completed.stdout)
        codex_invocations = codex_log.read_text(encoding="utf-8").splitlines()
        self.assertTrue(
            any("mcp add custom-echo" in line for line in codex_invocations)
        )
        self.assertFalse(any("gitnexus" in line for line in codex_invocations))

    def powershell_fake_onboard_environment(self) -> tuple[str, dict[str, str]]:
        runtime, environment = self.powershell_environment()
        self.write_executable(
            self.bin_dir / "python",
            self.fake_onboard_python_body(),
        )
        return runtime, environment

    def test_powershell_yes_without_projects_root_is_global_only(self) -> None:
        runtime, environment = self.powershell_fake_onboard_environment()
        completed = subprocess.run(
            [
                runtime, "-NoProfile", "-NonInteractive", "-File", str(INSTALL_PS1),
                "-Platform", "codex", "-SourceRoot", str(SOURCE_ROOT),
                "-Yes", "-Action", "init", "-NoMcp", "-NoColor",
            ],
            cwd=self.project_root,
            input="",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertIn("Project roots: <none>", completed.stdout)
        self.assertIn("Project AGENTS: skip", completed.stdout)
        self.assertNotIn("check-projects", self.modes())
        self.assertTrue(all("--projects-root" not in args for args in self.invocation_args()))
        self.assertFalse((self.project_root / "AGENTS.md").exists())
        self.assertFalse((self.project_root / ".gitignore").exists())

    def test_powershell_workflow_mode_forwards_without_onboarding(self) -> None:
        runtime, environment = self.powershell_fake_onboard_environment()
        completed = subprocess.run(
            [
                runtime,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(INSTALL_PS1),
                "-WorkflowMode",
                "migration",
                "--source-root",
                str(SOURCE_ROOT),
                "--phase",
                "cleanup",
                "--confirm-cleanup",
                "abc123",
                "--json",
            ],
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "")
        self.assertEqual(
            completed.stdout, '{"mode":"migration","status":"forwarded"}\n'
        )
        self.assertEqual(self.modes(), ["migration"])
        forwarded = self.invocation_args()[-1]
        self.assertIn("onboard.py migration", forwarded)
        self.assertIn("--json", forwarded)
        self.assertNotIn("--source-root", forwarded)

    def test_powershell_workflow_forwarding_preserves_yes_and_exit_code(self) -> None:
        runtime, environment = self.powershell_fake_onboard_environment()
        environment["FAKE_FORWARD_RC"] = "7"
        completed = subprocess.run(
            [
                runtime,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(INSTALL_PS1),
                "-WorkflowMode",
                "migration",
                f"--source-root={SOURCE_ROOT}",
                "--phase",
                "apply",
                "--manifest",
                str(self.root / "manifest.json"),
                "--yes",
                "--json",
            ],
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )

        self.assertEqual(completed.returncode, 7, completed.stderr)
        self.assertEqual(
            completed.stdout, '{"mode":"migration","status":"forwarded"}\n'
        )
        forwarded = self.invocation_args()[-1]
        self.assertIn("onboard.py migration", forwarded)
        self.assertIn("--yes", forwarded)
        self.assertIn("--json", forwarded)
        self.assertNotIn("--source-root", forwarded)

    def test_powershell_workflow_forwarding_respects_explicit_yes_values(self) -> None:
        runtime, environment = self.powershell_fake_onboard_environment()
        for value, confirmed in (("true", True), ("false", False)):
            with self.subTest(value=value):
                self.log_path.write_text("", encoding="utf-8")
                self.args_log_path.write_text("", encoding="utf-8")
                completed = subprocess.run(
                    [
                        runtime,
                        "-NoProfile",
                        "-NonInteractive",
                        "-File",
                        str(INSTALL_PS1),
                        "-WorkflowMode",
                        "migration",
                        "--source-root",
                        str(SOURCE_ROOT),
                        "--phase",
                        "plan",
                        f"--yes:${value}",
                        "--json",
                    ],
                    env=environment,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                    check=False,
                )

                self.assertEqual(completed.returncode, 0, completed.stderr)
                forwarded = self.invocation_args()[-1].split()
                self.assertEqual("--yes" in forwarded, confirmed)
                self.assertNotIn(f"--yes:${value}", forwarded)

    def test_powershell_workflow_mode_requires_lowercase(self) -> None:
        runtime, environment = self.powershell_fake_onboard_environment()
        completed = subprocess.run(
            [
                runtime,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(INSTALL_PS1),
                "-WorkflowMode",
                "MIGRATION",
                "--source-root",
                str(SOURCE_ROOT),
                "--phase",
                "plan",
            ],
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(self.log_path.exists())

    def run_powershell_installer(
        self, runtime: str, environment: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                runtime,
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(INSTALL_PS1),
                "-SourceRoot",
                str(SOURCE_ROOT),
                "-Platform",
                "codex",
                "-ProjectsRoot",
                str(self.project_root),
                "-Action",
                "init",
                "-SkipProjectAgents",
                "-NoMcp",
                "-NoColor",
                "-Yes",
            ],
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )

    def test_powershell_blocks_on_ponytail_provider_conflict(self) -> None:
        runtime, environment = self.powershell_fake_onboard_environment()
        for state in ("npm", "agent", "graft", "ponytail-conflict"):
            (self.state_dir / state).touch()
        completed = self.run_powershell_installer(runtime, environment)
        self.assertNotEqual(completed.returncode, 0)
        modes = self.modes()
        self.assertIn("check", modes)
        for forbidden in ("install-external-skills", "init", "reset"):
            self.assertNotIn(forbidden, modes)
        self.assertEqual(list(self.project_root.iterdir()), [])

    def test_powershell_graft_install_delegates_to_onboard_handler(self) -> None:
        runtime, environment = self.powershell_fake_onboard_environment()
        (self.state_dir / "npm").touch()
        (self.state_dir / "agent").touch()
        npm_log = self.root / "npm-pwsh.log"
        environment["FAKE_NPM_LOG"] = str(npm_log)
        self.write_executable(
            self.bin_dir / "npm",
            '#!/bin/sh\nprintf \'%s\\n\' "$*" >> "$FAKE_NPM_LOG"\n'
            'if [ "$1" = "config" ]; then printf \'/tmp/fake-prefix\\n\'; fi\n'
            "exit 0\n",
        )

        completed = self.run_powershell_installer(runtime, environment)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("@nanonets/graft@0.18.0", completed.stdout)
        self.assertIn("npm global prefix /tmp/fake-prefix", completed.stdout)
        self.assertEqual(self.modes().count("install-graft"), 2)  # probe + confirmed
        self.assertTrue((self.state_dir / "graft").exists())
        self.assertFalse(
            npm_log.exists(),
            "wrapper must not run npm directly; the Python probe owns the plan",
        )

    def test_powershell_graft_confirmed_failure_is_nonzero(self) -> None:
        runtime, environment = self.powershell_fake_onboard_environment()
        (self.state_dir / "npm").touch()
        (self.state_dir / "agent").touch()
        (self.state_dir / "graft-fails").touch()

        completed = self.run_powershell_installer(runtime, environment)

        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        modes = self.modes()
        self.assertEqual(modes.count("install-graft"), 2)  # probe + confirmed
        self.assertNotIn("init", modes)
        self.assertFalse((self.state_dir / "graft").exists())


class PowerShellInstallerAgentCliFlowTests(unittest.TestCase):
    def test_powershell_startup_banner_matches_kuno_welcome_panel(self) -> None:
        source = INSTALL_PS1.read_text(encoding="utf-8")
        logo = source.split("function Show-Logo", 1)[1].split(
            "function Normalize-Platform",
            1,
        )[0]

        self.assertIn(
            'function Show-Logo {\n  Write-Host ""\n'
            '  Write-Colored "╭─── SBTD Workflow Installer ',
            source,
        )
        self.assertIn(
            "│  --platform <agent>       Target Agent       │",
            logo,
        )
        self.assertIn(
            "│  --init-projects <paths>  Project-only mode  │",
            logo,
        )
        self.assertIn(
            "│  --dry-run                Preview changes    │",
            logo,
        )
        self.assertIn("╰──────────────────────────────────────────┴", logo)
        self.assertEqual(logo.count("SBTD Workflow Installer"), 1)

    def test_powershell_script_has_utf8_bom_for_windows_powershell(self) -> None:
        self.assertTrue(INSTALL_PS1.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_powershell_installs_paid_react_bits_skill_at_agent_path(self) -> None:
        source = INSTALL_PS1.read_text(encoding="utf-8")

        self.assertIn(
            '$reactBitsSkillDirectory = ".agents/skills/react-bits-pro"',
            source,
        )
        self.assertIn('"--path"', source)
        self.assertIn('"--overwrite"', source)
        self.assertIn('"--yes"', source)
        self.assertIn(
            "Test-Path -LiteralPath $reactBitsSkill -PathType Leaf",
            source,
        )


if __name__ == "__main__":
    unittest.main()
