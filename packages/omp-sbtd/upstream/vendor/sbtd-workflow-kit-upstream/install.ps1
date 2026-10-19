[CmdletBinding()]
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
  [switch]$GraftRetireLegacy,
  [string]$GraftLegacyBindings = "",
  [switch]$NoMcp,
  [switch]$DryRun,
  [switch]$Yes,
  [switch]$NoColor,
  [switch]$Help,
  [ValidateSet("", "migration", "recovery", "cleanup-legacy", "upgrade")]
  [string]$WorkflowMode = "",
  [Parameter(ValueFromRemainingArguments=$true)]
  [string[]]$WorkflowArgs = @()
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
if ($script:ProjectsOnly -and $GraftRetireLegacy) {
  throw "-InitProjects cannot retire global Graft MCP entries."
}
if ($GraftLegacyBindings -and -not $GraftRetireLegacy) {
  throw "-GraftLegacyBindings requires -GraftRetireLegacy."
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
      The installer may verify this CLI read-only immediately. Missing-CLI
      repair and npm bootstrap wait for complete selected-project preflight.
  -SourceRoot <path>
      Path to the sbtd-workflow-onboard directory.
      Defaults to ./sbtd-workflow-onboard.
  -ProjectsRoot <abs-path[,abs-path...]>
      One or more absolute project root paths separated by English commas.
      When omitted, ask interactively unless -Yes selects global-only setup.
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
  -GraftRetireLegacy
      Explicitly retire exact owned fixed-project Graft MCP entries for the
      selected roots after preview, preserving originals; not TEMP cleanup.
  -GraftLegacyBindings <path>
      Private old-runtime contract for an explicitly authorized MCP cutover.
  -NoMcp
      Skip MCP configuration.
  -DryRun
      Print commands and MCP writes without making changes.
  -Yes
      Answer yes to yes/no prompts within the selected scope.
      Normal init/reset without -ProjectsRoot is global-only; cwd is not
      implicitly selected as a project.
  -NoColor
      Disable ANSI color.
  -Help
      Show this help.
  -WorkflowMode <migration|recovery|cleanup-legacy|upgrade>
      Forward directly to scripts/onboard.py without onboarding. Remaining
      arguments are passed through unchanged, except --source-root.
      PowerShell-bound --yes and --help are forwarded explicitly; the `--`
      end-of-options marker is not supported on this forwarding path.
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
    "scripts/sbtd_project.py",
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

function Invoke-WorkflowMode {
  $source = $SourceRoot
  $forwarded = @()
  $explicitYes = $Yes.IsPresent
  for ($index = 0; $index -lt $WorkflowArgs.Count; $index++) {
    $arg = $WorkflowArgs[$index]
    if ($arg -eq "--source-root") {
      if (($index + 1) -ge $WorkflowArgs.Count) {
        Stop-WithMessage "--source-root requires a value"
      }
      $source = $WorkflowArgs[$index + 1]
      $index++
      continue
    }
    if ($arg -like "--source-root=*") {
      $source = $arg.Substring("--source-root=".Length)
      $next = if (($index + 1) -lt $WorkflowArgs.Count) { $WorkflowArgs[$index + 1] } else { $null }
      if ($null -ne $next -and $next.StartsWith('\') -and $source -match '^[A-Za-z]:?$') {
        if ($source.Length -eq 1) { $source += ':' }
        $source += $next
        $index++
      }
      continue
    }
    if ($arg -ieq '--yes:$true') {
      $explicitYes = $true
      continue
    }
    if ($arg -ieq '--yes:$false') {
      $explicitYes = $false
      continue
    }
    $forwarded += $arg
  }
  if ($WorkflowMode -eq "cleanup-legacy" -and $GlobalSkillsDir) {
    $forwarded += @("--global-skills-dir", $GlobalSkillsDir)
  }
  if ($explicitYes) {
    $forwarded += "--yes"
  }
  if ($Help) {
    $forwarded += "--help"
  }
  if ($WorkflowMode -cne $WorkflowMode.ToLowerInvariant()) {
    Stop-WithMessage "WorkflowMode must be lowercase: migration, recovery, cleanup-legacy or upgrade"
  }
  Validate-SourceRoot $source
  Find-Python
  $arguments = $PythonPrefix + @((Get-OnboardPy), $WorkflowMode) + $forwarded
  & $PythonExe @arguments
  exit $LASTEXITCODE
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
  if ($GraftRetireLegacy) { $args += "--graft-retire-legacy" }
  if ($GraftLegacyBindings) { $args += @("--graft-legacy-bindings", $GraftLegacyBindings) }
  if ($NoMcp) { $args += "--no-mcp" }
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
    $script:ProjectsRoot = $InitProjects
  }
  else {
    Update-AgentCliCheck
    if (-not $Action) {
      $script:Action = Select-One "Onboard action:" @("init", "reset")
    }
  }

  if ($ProjectsRoot) {
    Resolve-ProjectsRoot $ProjectsRoot
  }
  elseif ($Yes) {
    $script:SkipProjectAgents = $true
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

# Graft is optional: the read-only `install-graft --json` probe (no --yes,
# zero writes) is the single source of the real plan — frozen package, actual
# npm prefix, telemetry target/changes. Only needs-confirmation leads to a
# prompt and the confirmed `install-graft --yes`; blocked/operational states
# degrade to a warning and onboarding continues without Graft. A confirmed
# install failure still aborts the installer via Invoke-External.
function Ensure-GraftCli {
  Write-Host ""
  Write-Colored "Graft CLI (optional)" Cyan

  $probeArguments = $PythonPrefix + @((Get-OnboardPy), "install-graft", "--json")
  Write-Host ("+ " + (@($PythonExe) + $probeArguments -join " "))
  $probeOutput = & $PythonExe @probeArguments
  $probeExit = $LASTEXITCODE
  $probe = $null
  try {
    $probe = ($probeOutput -join "`n") | ConvertFrom-Json
  }
  catch {
    $probe = $null
  }
  if ($null -eq $probe) {
    Write-Warn "Graft CLI probe did not return a readable plan (exit $probeExit); skipping the optional Graft CLI."
    return
  }

  $status = [string]$probe.status
  $reason = [string]$probe.reason
  if ($status -eq "already-installed") {
    Write-Host "Graft CLI is already installed and usable; skipping."
    return
  }
  if ($status -eq "blocked") {
    if (-not $reason) { $reason = "unknown reason" }
    Write-Warn "Graft CLI is blocked: $reason. Skipping the optional Graft CLI; existing GitNexus/Graft configuration and data are left untouched."
    return
  }
  if ($status -ne "needs-confirmation") {
    if (-not $reason) { $reason = "no reason given" }
    Write-Warn "Graft CLI probe returned status '$status' (exit $probeExit): $reason. Skipping the optional Graft CLI."
    return
  }

  $plan = $probe.plan
  $package = "@nanonets/graft@0.22.0"
  if ($plan -and $plan.PSObject.Properties["package"] -and $plan.package) {
    $package = [string]$plan.package
  }
  $prefix = "<unresolved>"
  if ($plan -and $plan.PSObject.Properties["prefix"] -and $plan.prefix) {
    $prefix = [string]$plan.prefix
  }
  $telemetryPath = "<unknown>"
  $changeText = "none"
  if ($plan -and $plan.PSObject.Properties["telemetry"] -and $plan.telemetry) {
    if ($plan.telemetry.PSObject.Properties["path"] -and $plan.telemetry.path) {
      $telemetryPath = [string]$plan.telemetry.path
    }
    if ($plan.telemetry.PSObject.Properties["changes"] -and $plan.telemetry.changes) {
      $pairs = @()
      foreach ($property in $plan.telemetry.changes.PSObject.Properties) {
        $pairs += ("{0}={1}" -f $property.Name, $property.Value)
      }
      if ($pairs.Count -gt 0) { $changeText = $pairs -join ", " }
    }
  }
  $telemetryOnly = $probe.PSObject.Properties["before"] -and $probe.before -and $probe.before.PSObject.Properties["installed"] -and $probe.before.installed
  $prompt = "Install the optional Graft CLI now?"
  if ($telemetryOnly) {
    Write-Host "Graft telemetry opt-out plan:"
    Write-Host "  Existing CLI: verified; only persist telemetry opt-out (no package install)"
    $prompt = "Persist telemetry opt-out for the existing Graft CLI now?"
  }
  else {
    Write-Host "Graft CLI install plan:"
    Write-Host "  Package: $package (frozen pin; never latest)"
    Write-Host "  Target: npm global prefix $prefix"
    Write-Host "  Requires: Node.js >= 20 and npm native lifecycle scripts for the pinned allow list"
  }
  Write-Host "  Telemetry: set $changeText in $telemetryPath (unknown keys preserved)"
  if (-not (Prompt-YesNo $prompt "n")) {
    Write-Host "Graft optional changes declined; continuing without changes."
    return
  }
  if ($telemetryOnly) {
    Invoke-Onboard "install-graft" @("--telemetry-only", "--yes")
  }
  else {
    Invoke-Onboard "install-graft" @("--yes")
  }
  Update-Check
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

  Ensure-GraftCli

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
  if ($SkipProjectAgents) { $arguments += "--skip-project-agents" }
  $json = & $PythonExe @arguments
  $checkExit = $LASTEXITCODE
  if ($checkExit -ne 0) {
    Write-Host ($json -join "`n")
    Write-Host "Project checks failed with exit code $checkExit."
    exit $checkExit
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
  Write-Host "  4) Custom stdio MCP server"
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
  $onboardMode = if ($script:ProjectsOnly) { "init-projects" } else { $Action }
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
  Write-Host "Action: $onboardMode"
  Write-Host ("Project roots: " + ($(if ($ProjectsRoot) { $ProjectsRoot } else { "<none>" })))
  Write-Host ("Project AGENTS: " + ($(if ($SkipProjectAgents) { "skip" } else { "install" })))
  Write-Host ("Bundled and external Skills: " + ($(if ($script:ProjectsOnly) { "not touched" } else { "required global" })))
  Write-Host ("External Skill source: " + ($(if ($script:ProjectsOnly) { "not touched" } else { "auto (vendored stable; upstream is explicit opt-in)" })))
  Write-Host ("MCP: " + ($(if ($script:ProjectsOnly -or $NoMcp) { "skip" } else { "configure interactively" })))

  if (-not $Yes) {
    if (-not (Prompt-YesNo "Proceed with onboard $onboardMode?" "n")) {
      Stop-WithMessage "Installation cancelled."
    }
  }

  if ($DryRun) {
    Write-Host ""
    Write-Host "Dry run: skipped onboard $onboardMode writes."
  }
  else {
    Invoke-Onboard $onboardMode ($common + @("--yes"))
  }
}

function Final-Checks {
  Write-Host ""
  Write-Colored "Final check" Cyan
  if ($script:ProjectsOnly) {
    $projectArguments = @("--projects-root", $ProjectsRoot)
    if ($SkipProjectAgents) { $projectArguments += "--skip-project-agents" }
    Invoke-Onboard "check-projects" $projectArguments
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

if ($WorkflowMode) {
  Invoke-WorkflowMode
}
if ($WorkflowArgs.Count -gt 0) {
  Stop-WithMessage "Unknown option: $($WorkflowArgs[0])"
}
if ($Help) {
  Show-Usage
  exit 0
}

Validate-SourceRoot $SourceRoot
Find-Python
Show-Logo
Resolve-InteractiveInputs
Update-ProjectsCheck
if (-not $script:ProjectsOnly) {
  Ensure-TargetAgentCli
  Install-MissingRuntimeAndSkills
  Select-AndConfigureMcp
}
else {
  Write-Host ""
  Write-Host "Project-only mode: skipped all global tool, Skill, Agent CLI, and MCP checks/installations."
}
Configure-ProjectOptionalItems
Show-PlanAndExecute
Final-Checks
