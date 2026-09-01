from __future__ import annotations

import os
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
        self.env["PATH"] = os.pathsep.join((str(self.bin_dir), "/usr/bin", "/bin"))
        self.env["REAL_PYTHON"] = sys.executable
        self.env["FAKE_STATE_DIR"] = str(self.state_dir)
        self.env["FAKE_ONBOARD_LOG"] = str(self.log_path)
        self.env["FAKE_ONBOARD_ARGS_LOG"] = str(self.args_log_path)
        self.env["FAKE_PROJECT_ROOT"] = str(self.project_root)
        self.write_fake_python()

    def write_executable(self, path: Path, body: str) -> None:
        path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def write_fake_python(self) -> None:
        self.write_executable(
            self.bin_dir / "python3",
            """
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
            [ -f "$FAKE_STATE_DIR/npm" ] && npm_installed=true
            [ -f "$FAKE_STATE_DIR/agent" ] && agent_installed=true
            [ -f "$FAKE_STATE_DIR/external-missing" ] && external_installed=false

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
              check)
                json=false
                for arg in "$@"; do
                  [ "$arg" = "--json" ] && json=true
                done
                if [ "$json" = true ]; then
                  printf '{"runtime":{"npm":{"installed":%s}},"tools":[{"name":"rtk","installed":true},{"name":"trellis","installed":true},{"name":"gitnexus","installed":true},{"name":"java","installed":true},{"name":"maestro","installed":true}],"skills":[{"name":"caveman","installed":true},{"name":"diagnosing-bugs","group":"referenced","installed":%s}],"manualChecks":[]}\n' "$npm_installed" "$external_installed"
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
              *)
                printf 'unexpected fake mode: %s\n' "$mode" >&2
                exit 1
                ;;
            esac
            """,
        )

    def run_installer(
        self,
        user_input: str = "",
        action: str = "init",
        projects_only: bool = False,
        platform: str = "codex",
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
                "--skip-trellis-init",
                "--no-mcp",
                "--yes",
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
                "╭"
                + title
                + "─" * (left_width + 1 + right_width - len(title))
                + "╮",
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
                "--skip-trellis-init",
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
                "--skip-trellis-init",
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
            self.project_root
            / ".agents"
            / "skills"
            / "react-bits-pro"
            / "SKILL.md"
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
                "--skip-trellis-init",
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
                "--skip-trellis-init",
                "--no-mcp",
                "--no-color",
            ),
            input=f"n\n{projects_csv}\ny\n",
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

    def test_bash_enforces_global_tools_skills_and_mcp_scope_policy(self) -> None:
        source = INSTALL_SH.read_text(encoding="utf-8")
        global_stage = source.split("install_missing_runtime_and_skills() {", 1)[
            1
        ].split("prompt_env_pairs() {", 1)[0]
        self.assertIn("npm install -g @mindfoldhq/trellis@latest", global_stage)
        self.assertIn("npm install -g gitnexus@latest", global_stage)
        self.assertIn("--scope global --source auto --yes", global_stage)
        self.assertNotIn("External skills install decision", global_stage)
        self.assertNotIn("Install @mindfoldhq/trellis globally?", global_stage)
        self.assertNotIn("Install gitnexus globally?", global_stage)
        self.assertIn("claude mcp add --transport stdio --scope user", source)
        self.assertIn('local target="$HOME/.omp/agent/mcp.json"', source)
        self.assertNotIn("$PROJECT_ROOT/.omp/mcp.json", source)

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

    def test_missing_target_cli_bootstraps_npm_then_installs_agent_before_preflight(
        self,
    ) -> None:
        completed = self.run_installer()

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        modes = self.modes()
        first_check = modes.index("check")
        self.assertEqual(
            modes[:first_check],
            [
                "check-agent-cli",
                "ensure-npm",
                "check-agent-cli",
                "install-agent-cli",
                "check-agent-cli",
            ],
        )

    def test_existing_target_cli_bootstraps_required_npm_once_without_legacy_stage(
        self,
    ) -> None:
        (self.state_dir / "agent").touch()

        completed = self.run_installer()

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        modes = self.modes()
        self.assertEqual(modes[0], "check-agent-cli")
        self.assertEqual(modes.count("ensure-npm"), 1)
        source = INSTALL_SH.read_text(encoding="utf-8")
        legacy_stage = source.split("install_missing_runtime_and_skills() {", 1)[
            1
        ].split("prompt_env_pairs() {", 1)[0]
        self.assertNotIn("run_onboard ensure-npm", legacy_stage)


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
            '│  --platform <agent>       Target Agent       │',
            logo,
        )
        self.assertIn(
            '│  --init-projects <paths>  Project-only mode  │',
            logo,
        )
        self.assertIn(
            '│  --dry-run                Preview changes    │',
            logo,
        )
        self.assertIn("╰──────────────────────────────────────────┴", logo)
        self.assertEqual(logo.count("SBTD Workflow Installer"), 1)

    def test_powershell_script_has_utf8_bom_for_windows_powershell(self) -> None:
        self.assertTrue(INSTALL_PS1.read_bytes().startswith(b"\xef\xbb\xbf"))


    def test_powershell_checks_target_agent_before_action_and_removes_legacy_npm_stage(
        self,
    ) -> None:
        source = INSTALL_PS1.read_text(encoding="utf-8")
        self.assertIn("function Ensure-TargetAgentCli", source)
        interactive = source.split("function Resolve-InteractiveInputs", 1)[1].split(
            "function Install-MissingRuntimeAndSkills",
            1,
        )[0]
        self.assertLess(
            interactive.index("Ensure-TargetAgentCli"),
            interactive.index("if (-not $Action)"),
        )
        legacy_stage = source.split("function Install-MissingRuntimeAndSkills", 1)[
            1
        ].split("function Split-TrellisPlatforms", 1)[0]
        self.assertNotIn('Invoke-Onboard "ensure-npm"', legacy_stage)

    def test_powershell_uses_plural_projects_and_fixed_mcp_scopes(self) -> None:
        source = INSTALL_PS1.read_text(encoding="utf-8")
        parameter_block = source.split(")\n\n$ErrorActionPreference", 1)[0]
        self.assertIn("$ProjectsRoot", parameter_block)
        self.assertIn("$InitProjects", parameter_block)
        self.assertNotIn("$ProjectRoot", parameter_block)
        self.assertNotIn("$SkillsScope", parameter_block)
        self.assertIn('"--scope", "user"', source)
        self.assertIn('Join-Path $HOME ".omp/agent/mcp.json"', source)
        self.assertNotIn('Join-Path $ProjectRoot ".omp/mcp.json"', source)

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
            'Test-Path -LiteralPath $reactBitsSkill -PathType Leaf',
            source,
        )

    def test_powershell_yes_confirms_yes_no_prompts(self) -> None:
        source = INSTALL_PS1.read_text(encoding="utf-8")
        usage = source.split("function Show-Usage", 1)[1].split(
            "function Stop-WithMessage",
            1,
        )[0]
        prompt = source.split("function Prompt-YesNo", 1)[1].split(
            "function Select-One",
            1,
        )[0]

        self.assertIn("Answer yes to every yes/no prompt.", usage)
        self.assertIn("if ($Yes)", prompt)
        self.assertIn("return $true", prompt)

    def test_powershell_blocks_on_ponytail_provider_conflict(self) -> None:
        source = INSTALL_PS1.read_text(encoding="utf-8")

        assert_fn = source.split("function Assert-PonytailProviderClear", 1)[1].split(
            "function Install-MissingRuntimeAndSkills",
            1,
        )[0]
        self.assertIn("$script:Check.ponytailProvider.provider", assert_fn)
        self.assertIn('$provider -eq "conflict"', assert_fn)
        self.assertIn("Ponytail provider conflict", assert_fn)

        preflight = source.split("function Install-MissingRuntimeAndSkills", 1)[1]
        self.assertLess(preflight.index("Update-Check"), preflight.index("Assert-PonytailProviderClear"))
        self.assertLess(
            preflight.index("Assert-PonytailProviderClear"),
            preflight.index("install-external-skills"),
        )

        invoke_onboard = source.split("function Invoke-Onboard", 1)[1].split(
            "function Update-Check",
            1,
        )[0]
        self.assertIn("[switch]$AllowProviderConflict", invoke_onboard)
        self.assertIn(
            '$tolerated = $AllowProviderConflict -and $Mode -eq "check" -and $LASTEXITCODE -eq 4',
            invoke_onboard,
        )
        show_check = source.split("function Show-Check", 1)[1].split(
            "function Get-OnboardPy",
            1,
        )[0] if "function Show-Check" in source else ""
        preflight = source.split("function Install-MissingRuntimeAndSkills", 1)[1]
        self.assertIn("Show-Check -AllowProviderConflict", preflight)

        # The edited regions must keep balanced braces/parens/brackets.
        for region_name, region in (
            ("Assert-PonytailProviderClear", assert_fn),
            ("Invoke-Onboard", invoke_onboard),
        ):
            with self.subTest(region=region_name):
                for opener, closer in (("{", "}"), ("(", ")"), ("[", "]")):
                    self.assertEqual(region.count(opener), region.count(closer))



if __name__ == "__main__":
    unittest.main()
