param(
  [string]$Platform = "",
  [string]$SourceRoot = "./sbtd-workflow-onboard",
  [string]$ProjectsRoot = "",
  [string]$InitProjects = "",
  [ValidateSet("", "init", "reset")]
  [string]$Action = "",
  [switch]$SkipProjectAgents,
  [string]$GlobalAgentsPath = "",
  [string]$GlobalSkillsDir = "",
  [string]$TrellisUser = "",
  [string[]]$TrellisPlatform = @(),
  [switch]$SkipTrellisInit,
  [switch]$SkipTrellisBootstrap,
  [switch]$NoMcp,
  [switch]$DryRun,
  [switch]$Yes,
  [switch]$NoColor,
  [switch]$Help
)

$ErrorActionPreference = "Stop"
$script:ProjectRoots = @()
$script:ProjectsOnly = -not [string]::IsNullOrWhiteSpace($InitProjects)

if ($ProjectsRoot -and $InitProjects) {
  throw "Use either -ProjectsRoot or -InitProjects, not both."
}
if ($script:ProjectsOnly -and $Action) {
  throw "-InitProjects is a standalone mode and cannot be combined with -Action."
}

function Show-Usage {
  @"
SBTD workflow installer

Usage:
  .\install.ps1 [options]

Options:
  -Platform <codex|claude|kimi|oh-my-pi|omp>
      Target Agent CLI and MCP platform. "omp" is an alias for "oh-my-pi".
      This option does not change the Codex global AGENTS.md target; override
      that separately with -GlobalAgentsPath. If ~/.omp already exists,
      init/reset also overwrite ~/.omp/agent/AGENTS.md.
      The installer verifies this CLI immediately, bootstraps npm when needed,
      and installs the official npm package globally at @latest when missing.
  -SourceRoot <path>
      Path to the sbtd-workflow-onboard directory.
      Defaults to ./sbtd-workflow-onboard.
  -ProjectsRoot <abs-path[,abs-path...]>
      One or more absolute project root paths separated by English commas.
      When omitted, the installer asks interactively for the project roots.
  -InitProjects <abs-path[,abs-path...]>
      Run only per-project checks and initialization. Global tools, Skills,
      Agent CLI, and MCP are not checked, installed, or configured.
  -Action <init|reset>
      Onboard operation to run.
  -SkipProjectAgents
      Do not install project AGENTS.md.
  -GlobalAgentsPath <path>
      Override the global AGENTS.md target.
  -GlobalSkillsDir <path>
      Override global skills directory.
  -TrellisUser <name>
      Developer username for trellis init -u when the project has no .trellis/.
  -TrellisPlatform <name[,name...]>
      Trellis init platform flag without leading dashes. May be repeated.
      Examples: codex, claude, kimi, cursor, omp, pi. Replaces the Agent
      platform default. OMP and Pi are separate flags.
  -SkipTrellisInit
      Skip post-install trellis init for project roots without .trellis/.
  -SkipTrellisBootstrap
      Skip post-install bootstrap task detection.
  -NoMcp
      Skip MCP configuration.
  -DryRun
      Print commands and MCP writes without making changes.
  -Yes
      Answer yes to every yes/no prompt.
  -NoColor
      Disable ANSI color.
  -Help
      Show this help.
"@
}

function Stop-WithMessage {
  param([string]$Message)
  Write-Error $Message
  exit 1
}

function Write-Warn {
  param([string]$Message)
  Write-Warning $Message
}

function Use-Color {
  return (-not $NoColor.IsPresent) -and (-not $env:NO_COLOR) -and ($Host.UI.RawUI -ne $null)
}

function Write-Colored {
  param(
    [string]$Text,
    [ConsoleColor]$Color = [ConsoleColor]::Magenta
  )
  if (Use-Color) {
    Write-Host $Text -ForegroundColor $Color
  }
  else {
    Write-Host $Text
  }
}

function Show-Logo {
  Write-Host ""
  Write-Colored "╭─── SBTD Workflow Installer ─────────────────────────────────────────────────────────────╮" DarkMagenta
  Write-Colored "│   ██╗  ██╗██╗   ██╗███╗   ██╗ ██████╗    │  Tips                                        │" DarkMagenta
  Write-Colored "│   ██║ ██╔╝██║   ██║████╗  ██║██╔═══██╗   │  --platform <agent>       Target Agent       │" DarkMagenta
  Write-Colored "│   █████╔╝ ██║   ██║██╔██╗ ██║██║   ██║   │  --projects-root <paths>  Set project roots  │" Magenta
  Write-Colored "│   ██╔═██╗ ██║   ██║██║╚██╗██║██║   ██║   │  --init-projects <paths>  Project-only mode  │" Magenta
  Write-Colored "│   ██║  ██╗╚██████╔╝██║ ╚████║╚██████╔╝   │  --action <init|reset>    Select workflow    │" Magenta
  Write-Colored "│   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝    │  --dry-run                Preview changes    │" Magenta
  Write-Colored "╰──────────────────────────────────────────┴──────────────────────────────────────────────╯" Magenta
  Write-Host ""
}

function Normalize-Platform {
  param([string]$Value)
  $normalized = $Value.ToLowerInvariant().Replace("_", "-")
  switch ($normalized) {
    "codex" { return "codex" }
    "claude" { return "claude" }
    "claude-code" { return "claude" }
    "claudecode" { return "claude" }
    "kimi" { return "kimi" }
    "kimi-code" { return "kimi" }
    "kimicode" { return "kimi" }
    "oh-my-pi" { return "oh-my-pi" }
    "ohmypi" { return "oh-my-pi" }
    "omp" { return "oh-my-pi" }
    default { Stop-WithMessage "Unsupported platform: $Value" }
  }
}

function Platform-Label {
  param([string]$Value)
  switch ($Value) {
    "codex" { return "Codex" }
    "claude" { return "Claude Code" }
    "kimi" { return "Kimi Code" }
    "oh-my-pi" { return "Oh My Pi" }
    default { return $Value }
  }
}

function Prompt-Text {
  param(
    [string]$Prompt,
    [string]$Default = ""
  )
  if ($Default) {
    $value = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value
  }
  return (Read-Host $Prompt)
}

function Prompt-YesNo {
  param(
    [string]$Prompt,
    [string]$Default = "n"
  )
  if ($Yes) {
    return $true
  }
  $suffix = if ($Default -eq "y") { "[Y/n]" } else { "[y/N]" }
  while ($true) {
    $value = Read-Host "$Prompt $suffix"
    if ([string]::IsNullOrWhiteSpace($value)) { $value = $Default }
    switch ($value.ToLowerInvariant()) {
      "y" { return $true }
      "yes" { return $true }
      "n" { return $false }
      "no" { return $false }
      default { Write-Host "Please answer y or n." }
    }
  }
}

function Select-One {
  param(
    [string]$Prompt,
    [string[]]$Options
  )
  Write-Host $Prompt
  for ($i = 0; $i -lt $Options.Count; $i++) {
    Write-Host ("  {0}) {1}" -f ($i + 1), $Options[$i])
  }
  while ($true) {
    $choice = Read-Host "Select one"
    $number = 0
    if ([int]::TryParse($choice, [ref]$number) -and $number -ge 1 -and $number -le $Options.Count) {
      return $Options[$number - 1]
    }
    Write-Host "Invalid choice."
  }
}

function Validate-SourceRoot {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
    Write-Error @"
SBTD Onboard skill was not found.

Expected:
  $Path

This installer requires -SourceRoot to point directly to the
sbtd-workflow-onboard directory.
"@
    exit 1
  }

  $resolved = (Resolve-Path -LiteralPath $Path).Path
  $required = @(
    "SKILL.md",
    "REFERENCE.md",
    "catalog.json",
    "catalog.schema.json",
    "scripts/onboard.py",
    "templates/agents/AGENTS.global.md",
    "templates/agents/AGENTS.project.md",
    "templates/skills",
    "assets/external-skills/stable/MANIFEST.json"
  )
  $missing = @()
  foreach ($item in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $resolved $item))) {
      $missing += $item
    }
  }
  if ($missing.Count -gt 0) {
    Write-Error @"
SBTD Onboard skill was not found or is incomplete.

Provided:
  $resolved

Missing:
  $($missing -join "`n  ")

Please pass a valid sbtd-workflow-onboard directory.
"@
    exit 1
  }
  $script:SourceRoot = $resolved
}

function Find-Python {
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) {
    $script:PythonExe = $python.Source
    $script:PythonPrefix = @()
    return
  }
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) {
    $script:PythonExe = $py.Source
    $script:PythonPrefix = @("-3")
    return
  }
  Stop-WithMessage "python or py is required to run $SourceRoot\scripts\onboard.py"
}

function Invoke-External {
  param(
    [string]$FilePath,
    [string[]]$Arguments
  )
  $line = @($FilePath) + $Arguments
  Write-Host ("+ " + ($line -join " "))
  if ($DryRun) { return }
  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed with exit code $LASTEXITCODE`: $($line -join ' ')"
  }
}

function Get-OnboardPy {
  return (Join-Path $SourceRoot "scripts/onboard.py")
}

function Get-CommonArgs {
  $args = @()
  if ($Platform) { $args += @("--platform", $Platform) }
  if ($ProjectsRoot) { $args += @("--projects-root", $ProjectsRoot) }
  if ($SkipProjectAgents) { $args += "--skip-project-agents" }
  if ($GlobalAgentsPath) { $args += @("--global-agents-path", $GlobalAgentsPath) }
  if ($GlobalSkillsDir) { $args += @("--global-skills-dir", $GlobalSkillsDir) }
  if ($TrellisUser) { $args += @("--trellis-user", $TrellisUser) }
  foreach ($platformName in $TrellisPlatform) {
    if ($platformName) { $args += @("--trellis-platform", $platformName) }
  }
  if ($SkipTrellisInit) { $args += "--skip-trellis-init" }
  if ($SkipTrellisBootstrap) { $args += "--skip-trellis-bootstrap" }
  return $args
}

function Invoke-Onboard {
  param(
    [string]$Mode,
    [string[]]$Extra = @(),
    [switch]$AllowProviderConflict
  )
  $arguments = $PythonPrefix + @((Get-OnboardPy), $Mode) + $Extra
  if ($Mode -eq "check" -or $Mode -eq "check-projects" -or $Mode -eq "check-agent-cli" -or $Mode -eq "plan") {
    Write-Host ("+ " + (@($PythonExe) + $arguments -join " "))
    & $PythonExe @arguments
    # Exit 4 from check means a Ponytail provider conflict; only the preflight
    # path tolerates it because Assert-PonytailProviderClear runs immediately
    # after and reports the conflict with guidance. Every other check path
    # (including the final verification) must treat exit 4 as a failure.
    $tolerated = $AllowProviderConflict -and $Mode -eq "check" -and $LASTEXITCODE -eq 4
    if ($LASTEXITCODE -ne 0 -and -not $tolerated) {
      throw "Command failed with exit code $LASTEXITCODE`: $($arguments -join ' ')"
    }
  }
  else {
    Invoke-External $PythonExe $arguments
  }
}

function Update-Check {
  $script:CheckJsonPath = [System.IO.Path]::GetTempFileName()
  $arguments = $PythonPrefix + @((Get-OnboardPy), "check") + (Get-CommonArgs) + @("--json")
  if ($DryRun) {
    Write-Host ("+ " + (@($PythonExe) + $arguments -join " "))
  }
  & $PythonExe @arguments | Set-Content -LiteralPath $CheckJsonPath -Encoding UTF8
  $script:Check = Get-Content -LiteralPath $CheckJsonPath -Raw | ConvertFrom-Json
}

function Update-AgentCliCheck {
  $arguments = $PythonPrefix + @(
    (Get-OnboardPy),
    "check-agent-cli",
    "--platform",
    $Platform,
    "--json"
  )
  $json = & $PythonExe @arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Target Agent CLI check failed with exit code $LASTEXITCODE."
  }
  $script:AgentCliCheck = $json | ConvertFrom-Json
}

function Ensure-TargetAgentCli {
  Update-AgentCliCheck
  $label = [string]$script:AgentCliCheck.label
  $command = [string]$script:AgentCliCheck.command
  $installCommand = [string]$script:AgentCliCheck.installCommand
  $npmInstalled = [bool]$script:AgentCliCheck.runtime.npm.installed

  Write-Host ""
  Write-Colored "Target Agent CLI check" Cyan
  if ($script:AgentCliCheck.installed) {
    Write-Host "$label CLI passed verification: $command"
    if (-not $npmInstalled) {
      Write-Host "npm is required for the mandatory global Trellis and GitNexus CLIs; bootstrapping Node.js LTS + npm."
      Invoke-Onboard "ensure-npm" @("--yes")
      if (-not $DryRun) {
        Update-AgentCliCheck
        if (-not $script:AgentCliCheck.runtime.npm.installed) {
          Stop-WithMessage "npm bootstrap completed but npm is still unavailable; required global tools cannot be installed."
        }
      }
    }
    return
  }

  Write-Host "$label CLI is missing or failed verification."
  if ($installCommand) {
    Write-Host "Required install: $installCommand"
  }
  if (-not $npmInstalled) {
    if (-not (Prompt-YesNo "npm is required to install the selected $label CLI. Bootstrap Node.js LTS + npm now?" "n")) {
      Stop-WithMessage "$label CLI is required before collecting the remaining onboard inputs."
    }
    Invoke-Onboard "ensure-npm" @("--yes")
    if (-not $DryRun) {
      Update-AgentCliCheck
      if (-not $script:AgentCliCheck.runtime.npm.installed) {
        Stop-WithMessage "npm bootstrap did not make npm available; cannot install $label CLI."
      }
    }
  }

  if (-not (Prompt-YesNo "Install the latest $label CLI globally with npm now?" "n")) {
    Stop-WithMessage "$label CLI is required before collecting the remaining onboard inputs."
  }
  Invoke-Onboard "install-agent-cli" @("--platform", $Platform, "--yes")
  if ($DryRun) {
    Write-Host "Dry run: skipped $label CLI installation verification."
    return
  }

  Update-AgentCliCheck
  if (-not $script:AgentCliCheck.installed) {
    Stop-WithMessage "$label CLI installation completed but command verification failed."
  }
  Write-Host "$label CLI installation and command verification passed."
}

function Show-Check {
  param([switch]$AllowProviderConflict)
  Invoke-Onboard "check" (Get-CommonArgs) -AllowProviderConflict:$AllowProviderConflict
}

function Tool-ByName {
  param([string]$Name)
  return @($script:Check.tools | Where-Object { $_.name -eq $Name } | Select-Object -First 1)[0]
}

function Skill-ByName {
  param([string]$Name)
  return @($script:Check.skills | Where-Object { $_.name -eq $Name } | Select-Object -First 1)[0]
}

function Runtime-Installed {
  param([string]$Name)
  $item = $script:Check.runtime.$Name
  return [bool]$item.installed
}

function Tool-Installed {
  param([string]$Name)
  $item = Tool-ByName $Name
  return [bool]($item -and $item.installed)
}

function Skill-Installed {
  param([string]$Name)
  $item = Skill-ByName $Name
  return [bool]($item -and $item.installed)
}

function Resolve-ProjectsRoot {
  param([string]$Value)
  $resolved = @()
  foreach ($item in ($Value -split ",")) {
    $path = $item.Trim()
    if (-not $path) { continue }
    if (-not [System.IO.Path]::IsPathRooted($path)) {
      Stop-WithMessage "Project roots must be absolute paths: $path"
    }
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
      Stop-WithMessage "Project root does not exist: $path"
    }
    $canonical = (Resolve-Path -LiteralPath $path).Path
    if ($resolved -notcontains $canonical) { $resolved += $canonical }
  }
  if ($resolved.Count -eq 0) {
    Stop-WithMessage "At least one absolute project root is required."
  }
  $script:ProjectRoots = $resolved
  $script:ProjectsRoot = $resolved -join ","
}

function Resolve-InteractiveInputs {
  if ($Platform) {
    $script:Platform = Normalize-Platform $Platform
  }
  else {
    $selected = Select-One "Target coding agent tool:" @("Codex", "Claude Code", "Kimi Code", "Oh My Pi")
    switch ($selected) {
      "Codex" { $script:Platform = "codex" }
      "Claude Code" { $script:Platform = "claude" }
      "Kimi Code" { $script:Platform = "kimi" }
      "Oh My Pi" { $script:Platform = "oh-my-pi" }
    }
  }

  if ($script:ProjectsOnly) {
    $script:Action = "init-projects"
    $script:ProjectsRoot = $InitProjects
  }
  else {
    Ensure-TargetAgentCli
    if (-not $Action) {
      $script:Action = Select-One "Onboard action:" @("init", "reset")
    }
  }

  if ($ProjectsRoot) {
    Resolve-ProjectsRoot $ProjectsRoot
  }
  else {
    $cwd = (Get-Location).Path
    if (Prompt-YesNo "Use $cwd as the project root? You may also provide multiple absolute paths separated by English commas." "y") {
      Resolve-ProjectsRoot $cwd
    }
    else {
      $provided = Prompt-Text "Enter one or more absolute project root paths separated by English commas, or leave blank for global-only onboarding"
      if ($provided) {
        Resolve-ProjectsRoot $provided
      }
      else {
        $script:SkipProjectAgents = $true
      }
    }
  }

  if ($script:ProjectRoots.Count -gt 0 -and -not $SkipProjectAgents) {
    if (-not (Prompt-YesNo "Install project AGENTS.md into every selected project root?" "y")) {
      $script:SkipProjectAgents = $true
    }
  }
  if ($script:ProjectRoots.Count -eq 0) {
    $script:SkipProjectAgents = $true
  }
}

function Assert-PonytailProviderClear {
  $provider = ""
  if ($script:Check -and $script:Check.ponytailProvider) {
    $provider = [string]$script:Check.ponytailProvider.provider
  }
  if ($provider -eq "conflict") {
    throw "Ponytail provider conflict: the official Ponytail plugin is enabled. Disable or remove that plugin, then rerun the installer; Onboard installs and manages the vendored stable Ponytail Skills."
  }
}

function Install-MissingRuntimeAndSkills {
  Write-Host ""
  Write-Colored "Preflight check" Cyan
  Show-Check -AllowProviderConflict
  Update-Check
  Assert-PonytailProviderClear

  if (-not (Tool-Installed "rtk")) {
    $rtk = Tool-ByName "rtk"
    if ($rtk -and $rtk.wrongPackageSuspected) {
      if (Prompt-YesNo "rtk exists but may be the wrong package. Replace with rtk-ai/rtk?" "n") {
        Invoke-Onboard "install-rtk" @("--replace-wrong", "--yes")
      }
    }
    elseif ($rtk -and $rtk.verificationFailed) {
      if (Prompt-YesNo "rtk verification failed. Reinstall rtk-ai/rtk?" "n") {
        Invoke-Onboard "install-rtk" @("--reinstall", "--yes")
      }
    }
    elseif (Prompt-YesNo "rtk is missing. Install rtk-ai/rtk?" "n") {
      Invoke-Onboard "install-rtk" @("--yes")
    }
    Update-Check
  }

  if (-not (Tool-Installed "trellis") -and (Runtime-Installed "npm")) {
    Write-Host "Trellis CLI is required globally; installing @mindfoldhq/trellis@latest."
    Invoke-External "npm" @("install", "-g", "@mindfoldhq/trellis@latest")
    Update-Check
  }

  if (-not (Tool-Installed "gitnexus") -and (Runtime-Installed "npm")) {
    Write-Host "GitNexus CLI is required globally; installing gitnexus@latest."
    Invoke-External "npm" @("install", "-g", "gitnexus@latest")
    Update-Check
  }

  if (-not (Skill-Installed "caveman")) {
    if (Prompt-YesNo "caveman skill is missing. Install it as a user-level global skill?" "n") {
      Invoke-Onboard "install-caveman" @("--yes")
      Update-Check
    }
  }

  $missingExternal = @($script:Check.skills | Where-Object {
    ($_.group -eq "referenced") -and (-not $_.installed)
  } | ForEach-Object { $_.name })
  if ($missingExternal.Count -gt 0) {
    Write-Host ""
    Write-Host ("Required global external skills are missing: " + ($missingExternal -join ","))
    $args = @("--skills", ($missingExternal -join ","), "--scope", "global", "--source", "auto", "--yes")
    if ($GlobalSkillsDir) { $args += @("--global-skills-dir", $GlobalSkillsDir) }
    Invoke-Onboard "install-external-skills" $args
    Update-Check
  }
}

function Split-TrellisPlatforms {
  param([string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) { return @() }
  return @($Value -replace "\s", "" -split "," | Where-Object { $_ } | ForEach-Object { $_.TrimStart("-") })
}

function Resolve-TrellisProjectSetupInputs {
  if ($SkipTrellisInit) { return }
  if ($script:ProjectRoots.Count -eq 0) { return }
  $needsInit = @($script:ProjectRoots | Where-Object {
    -not (Test-Path -LiteralPath (Join-Path $_ ".trellis"))
  })
  if ($needsInit.Count -eq 0) { return }

  if (-not (Get-Command trellis -ErrorAction SilentlyContinue)) {
    Write-Warn "The required global Trellis CLI is unavailable; project initialization will be reported as blocked."
    return
  }

  while ([string]::IsNullOrWhiteSpace($script:TrellisUser)) {
    $script:TrellisUser = Prompt-Text "Trellis developer username for trellis init -u"
    if ([string]::IsNullOrWhiteSpace($script:TrellisUser)) {
      if (Prompt-YesNo "Skip trellis init for all selected projects that do not have .trellis/?" "n") {
        $script:SkipTrellisInit = $true
        return
      }
    }
  }

  if ($script:TrellisPlatform.Count -eq 0) {
    $rawPlatforms = Prompt-Text "Trellis platform flags, comma-separated without --. Blank uses the Agent platform default for codex, claude, or kimi; Oh My Pi requires omp and/or pi"
    $script:TrellisPlatform = @(Split-TrellisPlatforms $rawPlatforms)
  }
}

function Update-ProjectsCheck {
  if (-not $ProjectsRoot) {
    $script:ProjectsCheck = [pscustomobject]@{ mode = "check-projects"; projects = @() }
    return
  }
  $arguments = $PythonPrefix + @(
    (Get-OnboardPy),
    "check-projects",
    "--projects-root",
    $ProjectsRoot,
    "--json"
  )
  $json = & $PythonExe @arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Project checks failed with exit code $LASTEXITCODE."
  }
  $script:ProjectsCheck = $json | ConvertFrom-Json
}

function Invoke-InProject {
  param(
    [string]$ProjectRoot,
    [string]$FilePath,
    [string[]]$Arguments
  )
  Write-Host "+ cd $ProjectRoot; $FilePath $($Arguments -join ' ')"
  if ($DryRun) { return }
  Push-Location $ProjectRoot
  try {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
      throw "Command failed with exit code $LASTEXITCODE`: $FilePath $($Arguments -join ' ')"
    }
  }
  finally {
    Pop-Location
  }
}

function Configure-ProjectOptionalItems {
  if (-not $ProjectsRoot) { return }
  Update-ProjectsCheck
  foreach ($project in @($script:ProjectsCheck.projects)) {
    $projectRoot = [string]$project.projectRoot
    if ($project.playwright.applicable -and -not $project.playwright.installed) {
      if (Prompt-YesNo "Playwright project tooling is applicable but missing in $projectRoot. Install @playwright/test in this project?" "n") {
        Invoke-Onboard "install-playwright-cli" @("--project-root", $projectRoot, "--yes")
      }
    }

    if ($project.reactBits.applicable) {
      $decision = Select-One "React Bits decision for $projectRoot`:" @(
        "keep shadcn/ui only",
        "configure React Bits Free from an existing registry item",
        "configure an existing paid React Bits entitlement"
      )
      if ($decision -eq "configure React Bits Free from an existing registry item") {
        $registryItem = Prompt-Text "Configured free React Bits shadcn registry item, or blank to skip"
        if ($registryItem) {
          Invoke-InProject $projectRoot "npx" @("shadcn@latest", "add", $registryItem)
        }
        else {
          Write-Warn "React Bits Free was not installed for $projectRoot because no configured registry item was provided."
        }
      }
      elseif ($decision -eq "configure an existing paid React Bits entitlement") {
        if (-not $env:REACTBITS_LICENSE_KEY) {
          Write-Warn "REACTBITS_LICENSE_KEY is unavailable; skipped paid React Bits setup for $projectRoot."
        }
        else {
          $reactBitsSkillDirectory = ".agents/skills/react-bits-pro"
          Invoke-InProject $projectRoot "npx" @(
            "shadcn@latest",
            "add",
            "@reactbits-starter/skill",
            "--path",
            $reactBitsSkillDirectory,
            "--overwrite",
            "--yes"
          )
          $reactBitsSkill = Join-Path $projectRoot "$reactBitsSkillDirectory/SKILL.md"
          if (-not $DryRun -and -not (Test-Path -LiteralPath $reactBitsSkill -PathType Leaf)) {
            throw "React Bits setup did not create $reactBitsSkill"
          }
        }
      }
    }
  }
}

function Prompt-EnvPairs {
  $pairs = @{}
  while ($true) {
    $key = Prompt-Text "Env key for this MCP server, or blank to finish"
    if (-not $key) { break }
    if ($key -match "TOKEN|PASSWORD|SECRET|KEY") {
      $secure = Read-Host "Value for $key" -AsSecureString
      $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
      try {
        $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
      }
      finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
      }
    }
    else {
      $value = Prompt-Text "Value for $key"
    }
    $pairs[$key] = $value
  }
  return $pairs
}

function Ensure-MaestroReady {
  Update-Check
  if (-not (Tool-Installed "java")) {
    Write-Warn "Maestro MCP requires Java 17+. Native Windows auto-install is not enabled by this installer."
    Write-Warn "Install Java 17+ manually, then rerun this script."
    return $false
  }

  if (-not (Tool-Installed "maestro")) {
    Write-Warn "Maestro CLI is missing or not verified. Native Windows Maestro install is manual-required."
    Write-Warn "Install Maestro CLI or use WSL, then rerun this script."
    return $false
  }
  return $true
}

function Get-MaestroEnv {
  $config = Get-ManualMcpConfig "Maestro MCP"
  if ($config -and $config.env) {
    return $config.env
  }
  return @{}
}

function Get-ManualMcpConfig {
  param([string]$Name)
  foreach ($item in $script:Check.manualChecks) {
    if ($item.name -eq $Name -and $item.PSObject.Properties["mcpServerConfig"]) {
      return $item.mcpServerConfig
    }
  }
  return $null
}

function Convert-EnvObjectToHash {
  param($EnvObject)
  $envHash = @{}
  if ($null -eq $EnvObject) {
    return $envHash
  }
  foreach ($property in $EnvObject.PSObject.Properties) {
    $envHash[$property.Name] = [string]$property.Value
  }
  return $envHash
}

function Configure-StdioMcp {
  param(
    [string]$Name,
    [string]$Command,
    [string[]]$Args,
    [hashtable]$ServerEnv = @{}
  )

  switch ($Platform) {
    "codex" {
      if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
        Write-Warn "codex CLI not found; skipped MCP server $Name."
        return
      }
      $cmdArgs = @("mcp", "add", $Name)
      foreach ($key in $ServerEnv.Keys) {
        $cmdArgs += @("--env", "$key=$($ServerEnv[$key])")
      }
      $cmdArgs += @("--", $Command) + $Args
      Invoke-External "codex" $cmdArgs
    }
    "claude" {
      if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
        Write-Warn "claude CLI not found; skipped MCP server $Name."
        return
      }
      $cmdArgs = @("mcp", "add", "--transport", "stdio", "--scope", "user")
      foreach ($key in $ServerEnv.Keys) {
        $cmdArgs += @("--env", "$key=$($ServerEnv[$key])")
      }
      $cmdArgs += @($Name, "--", $Command) + $Args
      Invoke-External "claude" $cmdArgs
    }
    "kimi" {
      if (-not (Get-Command kimi -ErrorAction SilentlyContinue)) {
        Write-Warn "kimi CLI not found; skipped MCP server $Name."
        return
      }
      $cmdArgs = @("mcp", "add", "--transport", "stdio")
      foreach ($key in $ServerEnv.Keys) {
        $cmdArgs += @("--env", "$key=$($ServerEnv[$key])")
      }
      $cmdArgs += @($Name, "--", $Command) + $Args
      Invoke-External "kimi" $cmdArgs
    }
    "oh-my-pi" {
      Configure-OmpStdio $Name $Command $Args $ServerEnv
    }
  }
}

function Configure-OmpStdio {
  param(
    [string]$Name,
    [string]$Command,
    [string[]]$Args,
    [hashtable]$ServerEnv = @{}
  )
  $target = Join-Path $HOME ".omp/agent/mcp.json"

  if ($DryRun) {
    Write-Host "+ write Oh My Pi MCP server $Name to $target"
    return
  }

  if (Test-Path -LiteralPath $target) {
    $config = Get-Content -LiteralPath $target -Raw | ConvertFrom-Json
  }
  else {
    $config = [pscustomobject]@{}
  }
  if (-not $config.PSObject.Properties["mcpServers"]) {
    $config | Add-Member -MemberType NoteProperty -Name "mcpServers" -Value ([pscustomobject]@{})
  }
  $server = [ordered]@{
    type = "stdio"
    command = $Command
    args = $Args
    env = $ServerEnv
  }
  $config.mcpServers | Add-Member -MemberType NoteProperty -Name $Name -Value $server -Force
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
  $config | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $target -Encoding UTF8
  Write-Host "wrote $Name MCP server to $target"
}

function Select-AndConfigureMcp {
  if ($NoMcp) {
    Write-Host ""
    Write-Host "MCP configuration skipped by -NoMcp."
    return
  }
  if (-not (Prompt-YesNo "Configure MCP servers for $(Platform-Label $Platform) now?" "y")) {
    Write-Host "MCP configuration skipped by user."
    return
  }

  Write-Host ""
  Write-Host "Available MCP options:"
  Write-Host "  1) Chrome DevTools MCP"
  Write-Host "  2) Playwright MCP"
  Write-Host "  3) Maestro MCP"
  Write-Host "  4) GitNexus MCP (auto from gitnexus CLI)"
  Write-Host "  5) Custom stdio MCP server"
  $raw = Read-Host "Select comma-separated options, or blank for none"
  if (-not $raw) { return }
  $items = $raw -replace "\s", "" -split ","
  foreach ($item in $items) {
    switch ($item) {
      "1" {
        Configure-StdioMcp "chrome-devtools" "npx" @("-y", "chrome-devtools-mcp@latest") @{}
      }
      "2" {
        Configure-StdioMcp "playwright" "npx" @("-y", "@playwright/mcp@latest") @{}
      }
      "3" {
        if (Ensure-MaestroReady) {
          $envObject = Get-MaestroEnv
          $envHash = Convert-EnvObjectToHash $envObject
          Configure-StdioMcp "maestro" "maestro" @("mcp") $envHash
        }
      }
      "4" {
        $config = Get-ManualMcpConfig "GitNexus MCP"
        if ($config -and $config.command) {
          $serverArgs = @()
          if ($config.args) {
            foreach ($arg in $config.args) {
              $serverArgs += [string]$arg
            }
          }
          $envHash = Convert-EnvObjectToHash $config.env
          Configure-StdioMcp "gitnexus" ([string]$config.command) $serverArgs $envHash
        }
        else {
          Write-Warn "GitNexus CLI path was not detected; falling back to manual MCP command input."
          $command = Prompt-Text "GitNexus MCP command, or blank to skip"
          if (-not $command) {
            Write-Warn "Skipped GitNexus MCP: command is required."
            continue
          }
          $argsLine = Prompt-Text "GitNexus MCP args as a simple space-separated list"
          $serverArgs = if ($argsLine) { $argsLine -split "\s+" } else { @() }
          $envHash = Prompt-EnvPairs
          Configure-StdioMcp "gitnexus" $command $serverArgs $envHash
        }
      }
      "5" {
        $name = Prompt-Text "MCP server name"
        $command = Prompt-Text "MCP command"
        if (-not $name -or -not $command) {
          Write-Warn "Skipped custom MCP: name and command are required."
          continue
        }
        $argsLine = Prompt-Text "MCP args as a simple space-separated list"
        $serverArgs = if ($argsLine) { $argsLine -split "\s+" } else { @() }
        $envHash = Prompt-EnvPairs
        Configure-StdioMcp $name $command $serverArgs $envHash
      }
      default {
        Write-Warn "Invalid MCP selection ignored: $item"
      }
    }
  }
}

function Show-PlanAndExecute {
  $common = Get-CommonArgs
  Write-Host ""
  Write-Colored "Final plan" Cyan
  if (-not $script:ProjectsOnly) {
    Invoke-Onboard "plan" $common
  }
  else {
    Write-Host "Project-only mode will run init-projects without global writes."
  }

  Write-Host ""
  Write-Host ("Target platform: " + (Platform-Label $Platform))
  Write-Host "Source root: $SourceRoot"
  Write-Host "Action: $Action"
  Write-Host ("Project roots: " + ($(if ($ProjectsRoot) { $ProjectsRoot } else { "<none>" })))
  Write-Host ("Project AGENTS: " + ($(if ($SkipProjectAgents) { "skip" } else { "install" })))
  Write-Host ("Bundled and external Skills: " + ($(if ($script:ProjectsOnly) { "not touched" } else { "required global" })))
  Write-Host ("External Skill source: " + ($(if ($script:ProjectsOnly) { "not touched" } else { "auto (vendored stable; upstream is explicit opt-in)" })))
  Write-Host ("MCP: " + ($(if ($script:ProjectsOnly -or $NoMcp) { "skip" } else { "configure interactively" })))

  if (-not $Yes) {
    if (-not (Prompt-YesNo "Proceed with onboard $Action?" "n")) {
      Stop-WithMessage "Installation cancelled."
    }
  }

  if ($DryRun) {
    Write-Host ""
    Write-Host "Dry run: skipped onboard $Action writes."
  }
  else {
    Invoke-Onboard $Action ($common + @("--yes"))
  }
}

function Final-Checks {
  Write-Host ""
  Write-Colored "Final check" Cyan
  if ($script:ProjectsOnly) {
    Invoke-Onboard "check-projects" @("--projects-root", $ProjectsRoot)
    return
  }
  Invoke-Onboard "check-agent-cli" @("--platform", $Platform)
  Invoke-Onboard "check" (Get-CommonArgs)

  switch ($Platform) {
    "codex" {
      if (Get-Command codex -ErrorAction SilentlyContinue) {
        Invoke-External "codex" @("mcp", "list")
      }
      else { Write-Warn "codex CLI not found; MCP list skipped." }
    }
    "claude" {
      if (Get-Command claude -ErrorAction SilentlyContinue) {
        Invoke-External "claude" @("mcp", "list")
      }
      else { Write-Warn "claude CLI not found; MCP list skipped." }
    }
    "kimi" {
      if (Get-Command kimi -ErrorAction SilentlyContinue) {
        Invoke-External "kimi" @("mcp", "list")
      }
      else { Write-Warn "kimi CLI not found; MCP list skipped." }
    }
    "oh-my-pi" {
      Write-Host "Oh My Pi MCP config: $(Join-Path $HOME '.omp/agent/mcp.json')"
    }
  }
}

if ($Help) {
  Show-Usage
  exit 0
}

Validate-SourceRoot $SourceRoot
Find-Python
Show-Logo
Resolve-InteractiveInputs
if (-not $script:ProjectsOnly) {
  Install-MissingRuntimeAndSkills
  Select-AndConfigureMcp
}
else {
  Write-Host ""
  Write-Host "Project-only mode: skipped all global tool, Skill, Agent CLI, and MCP checks/installations."
}
Configure-ProjectOptionalItems
Resolve-TrellisProjectSetupInputs
Show-PlanAndExecute
Final-Checks
