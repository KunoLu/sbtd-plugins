# SBTD Workflow Onboard Reference

## Bundled Templates

- `templates/agents/AGENTS.global.md` -> global Codex `AGENTS.md`, and `~/.omp/agent/AGENTS.md` when `~/.omp` already exists
- `templates/agents/AGENTS.project.md` → each selected project root `AGENTS.md`
- `templates/project/.gitignore` → each selected project root `.gitignore`
- `templates/skills/**` → required global bundled Skills

`catalog.json` is the runtime source of truth for these paths, all bundled Skill ids, and every external Skill repository/subpath/alias. `catalog.schema.json` defines its Draft 2020-12 contract; `examples/catalog.minimal.json` is the minimal valid shape. The root installers require both catalog files, and `scripts/onboard.py` rejects duplicate ids, absolute or escaping paths, malformed HTTPS repository URLs, invalid kind/id/target-role combinations, wrong local source types, missing sources, and bundled Skill frontmatter identity mismatches before processing a command.

> **v2 delivery boundaries:** canonical payload is 14 bundled / 19 external Skills. Project setup uses SBTD checks without Trellis initialization. Graft detection/installation, explicit Codex/OMP project wiring, task libraries, developer identity, migration plan/apply/verify/reconcile, cleanup/recovery and root-installer forwarding have separate implementation and acceptance records. Published tags and their evidence establish release and platform status; a source checkout or installed copy alone does not. Existing legacy data is preserved.

The P1-01 argument/codec modules and `onboard-contracts.schema.json` provide the exchange contracts. P1-12 exposes migration plan/apply/verify; P1-04/P1-05 supply Codex/OMP wiring and the migration-context deployment producer below; cleanup and recovery are implemented by their owning tasks. Contract validation checks declared structures and relationships; filesystem safety, authorization and actual operations remain stage-owned.

For validation, install the declared dependency with the interpreter that will load the installed Skill: `python -m pip install -r /path/to/installed/sbtd-workflow-onboard/requirements.txt`. A Skill directory copy does not perform this step. Imports remain lazy, missing dependencies fail closed, and availability must be checked from the installed copy rather than inferred from source-tree CI.

AGENTS files are backed up before overwrite. On `reset`, bundled Skill targets are overwritten without backup after their catalog sources pass the startup checks above. On `init`, a bundled Skill target that is already a valid Skill shell is skipped; missing or invalid shells are copied. After the canonical `sbtd-workflow-onboard` target validates, the legacy `kuno-workflow-onboard-skills` directory is removed without leaving an alias only when its own `SKILL.md` frontmatter confirms the legacy identity. An unrelated or mismatched legacy path blocks `init` / `reset` before target changes and remains untouched; deletion errors are returned as migration failures. Project `.gitignore` is updated in place by ensuring that the bundled block exists.


## Official Skills CLI Bootstrap

Install only the self-contained Onboard Skill from the public repository:

```bash
npx --yes skills@latest add \
  https://github.com/KunoLu/640-skills \
  --skill sbtd-workflow-onboard \
  --global \
  --agent codex \
  --yes \
  --copy
```

Use an authenticated `git+ssh://` source for a private repository. The source must expose `sbtd-workflow-onboard/SKILL.md`; the official CLI recursively discovers that Skill and copies the complete directory, including `REFERENCE.md`, `catalog.json`, `catalog.schema.json`, `scripts/`, `templates/`, and `assets/`.

The official CLI is a package bootstrap only. It does not run Onboard, install the catalog's bundled/external Skills, write AGENTS files, install Trellis/GitNexus, or initialize projects. After bootstrap, invoke the installed Skill and use its `scripts/onboard.py` interface. The repository root `install.sh` and `install.ps1` remain the complete interactive installation interfaces for a cloned checkout.

Installed `scripts/onboard.py` resolves its global Skills root in this order: explicit `--global-skills-dir`, `$AGENT_SKILLS_DIR`, the installed `sbtd-workflow-onboard` directory's parent when it is under a recognized global Agent Skills root, then the existing platform default. JSON `plan` and `check` output includes `globalSkillsDirSource` so this decision is auditable.

## Public Interfaces

### Bash

```bash
bash install.sh [options]
```

Important arguments:

- `--platform <codex|claude|kimi|oh-my-pi|omp>`
- `--projects-root <abs-path[,abs-path...]>`
- `--init-projects <abs-path[,abs-path...]>`
- `--action <init|reset>`
- `--source-root <path>`
- `--skip-project-agents`
- `--global-agents-path <path>`
- `--global-skills-dir <path>`
- `--no-mcp`, `--dry-run`, `--yes`, `--no-color`

The Agent platform selects the CLI and MCP adapter; it does not select the global AGENTS target. Normal onboarding keeps the Codex global AGENTS default shown under [Paths](#paths) unless `--global-agents-path` / `-GlobalAgentsPath` explicitly overrides it. If the user-home `.omp` directory already exists (POSIX `~/.omp`, Windows `%USERPROFILE%\.omp`), `init` / `reset` also backup-then-overwrite the same template to `~/.omp/agent/AGENTS.md`. Missing `.omp` is skipped; Onboard does not create `.omp`. `--global-agents-path` overrides only the Codex target. Project-only mode never writes global AGENTS.

### PowerShell

```powershell
.\install.ps1 [options]
```

PowerShell uses `-Platform`, `-ProjectsRoot`, `-InitProjects`, `-Action`, `-SourceRoot`, `-SkipProjectAgents`, `-GlobalAgentsPath`, `-GlobalSkillsDir`, `-NoMcp`, `-DryRun`, `-Yes`, and `-NoColor`. Trellis username/platform/skip options are removed in both installers and Python, without aliases.

`--yes` / `-Yes` answers yes/no prompts and skips final execution confirmation. It does not invent platform, action or React Bits text/selection answers, authorize migration, or override project-state conflicts.

`--project-root`, `-ProjectRoot`, `--skills-scope`, `-SkillsScope`, `--project-skills-dir`, and `-ProjectSkillsDir` are no longer public root-installer arguments.

## Project Root Contract

`--projects-root` / `-ProjectsRoot` accepts one or more existing absolute directories separated by English commas. `--init-projects` / `-InitProjects` accepts the same format and activates project-only mode.

Rules:

1. Relative paths are rejected.
2. Empty CSV elements are ignored.
3. Paths are resolved to canonical absolute paths.
4. Duplicates are processed once.
5. `projects-root` and `init-projects` are mutually exclusive.
6. `init-projects` cannot be combined with `action`.
7. Without `--yes` / `-Yes`, a normal root-installer run that receives neither project argument asks whether cwd is a project root, explains the absolute CSV format, and otherwise prompts for the list.
8. A blank interactive project list means global-only onboarding.
9. With `--yes` / `-Yes`, normal `init` / `reset` without `projects-root` is global-only. It does not ask the cwd question or implicitly select cwd; project AGENTS/ignore/graph assets are not installed. Explicit `projects-root` and `init-projects` selections are unchanged.

When the Onboard Skill receives multiple repository paths without an explicit statement that they should be initialized, it must ask the user to confirm that those paths are the intended project initialization roots.

## Two Execution Modes

### Normal init/reset

Normal onboarding:

1. Resolves the target Agent platform.
2. May inspect the target Agent CLI read-only before collecting the remaining inputs.
3. Resolves all project roots and AGENTS scope, then runs complete `check-projects` before any installation or configuration write.
4. Repairs the selected Agent/npm only after project preflight passes, then runs the global preflight.
5. Offers Graft's pinned global installation after showing its plan; refusal does not install npm/Graft or block unrelated safe work.
6. Preserves the existing optional RTK, caveman, Java, and Maestro decisions.
7. For `init`, installs only missing or invalid required external Skills globally. For `reset`, force-reinstalls every required external Skill from the current stable snapshot.
8. Optionally configures selected user/global MCP servers.
9. Checks project-only Playwright and React Bits conditions for every root.
10. Writes global AGENTS with backup-then-overwrite. For `init`, copies missing or invalid bundled Skills and skips valid Skill shells. For `reset`, overwrites every bundled Skill without backup.
11. Inspects every selected project's minimal SBTD state and scaffold destinations before Python installation writes; conflicts stop the batch.
12. Writes project AGENTS and `.gitignore`, preserving optional task/identity/spec/lessons data, then reports SBTD checks again.


### Project-only init-projects

Project-only mode:


1. Resolves the selected Agent platform for the existing adapter context.
2. Skips target Agent CLI detection and installation.
3. Skips global installation and user configuration. Explicit Python Codex/OMP project setup may detect the already-installed fixed Graft/Node locally; it never installs them or writes HOME telemetry.
4. Runs complete read-only `check-projects` with the actual `--skip-project-agents` scope before any optional project install.
5. Offers only applicable project-local Playwright or React Bits decisions.
6. Writes project AGENTS and `.gitignore`.
7. Requires no Trellis CLI, developer name or pre-existing task state.
8. Reports an explicitly present unfinished SBTD bootstrap task without creating one.
9. For explicit Codex or OMP projects with fixed Graft available, maintains the project fence and graph; otherwise reports not-available and continues unrelated setup. No HOME, user-level MCP or hook writes.

The project AGENTS provides the existing minimum routing/safety fallback; project-only mode does not install or claim activation of global Skills. Missing optional tools do not freeze unrelated safe default/lite work, and no missing reviewer may be reported as passed.

## Target Agent CLI Gate

| Platform | Command | Required global npm package |
|---|---|---|
| `codex` | `codex --version` | `@openai/codex@latest` |
| `claude` | `claude --version` | `@anthropic-ai/claude-code@latest` |
| `kimi` | `kimi --version` | `@moonshot-ai/kimi-code@latest` |
| `oh-my-pi` / `omp` | `omp --version` | `@oh-my-pi/pi-coding-agent@latest` |

Shared commands:

```bash
python scripts/onboard.py check-agent-cli --platform codex
python scripts/onboard.py install-agent-cli --platform codex --yes
```

Normal onboarding may probe the target CLI read-only first, but collects the action, project list and AGENTS scope and passes complete project preflight before any CLI installation or repair. Oh My Pi follows the requested npm path and is accepted only when `omp --version` succeeds.

## Required Global Tools

Graft is an explicitly confirmed auxiliary CLI, pinned to `@nanonets/graft@0.22.0` with Node >=20. Existing local availability is checked independently of npm or latest-version reachability. No automatic upgrade, install loop or offline-mirror product is provided.

```bash
python scripts/onboard.py install-graft --json
python scripts/onboard.py install-graft --yes --json
```

Without confirmation the handler only reports its package/prefix/telemetry plan. The confirmed path verifies frozen tarball integrity, enables the required native lifecycle scripts and verifies the installed pinned CLI. Telemetry persistence is create-only: an absent `~/.graft/telemetry.json` is atomically published without replacing a concurrent creator; an existing `enabled=false` file is read-only. Any existing file requiring an update blocks without mutation. Graft does not share a conditional-write protocol, so read/compare/replace cannot safely preserve concurrent updates. Resolve existing enabled state externally under exclusive control before retrying; the installer never invokes Graft's telemetry command or silently overwrites foreign fields.

When only telemetry opt-out is selected, use `install-graft --telemetry-only --yes --json`. The handler rechecks the verified pinned CLI and blocks if it disappeared or changed; it never falls through to npm/package installation under telemetry-only consent. Both root wrappers preserve this action boundary after showing the probe plan.

All managed Graft children receive `DO_NOT_TRACK=1`, an empty dotenv input, `DOTENV_CONFIG_QUIET=true`, and no inherited dotenv-debug or LLM/cloud activation settings. The installation child also uses `CI=1` to avoid this pin's detached postinstall path; runtime DNT is separately exercised without relying on CI. These child settings do not edit the user's global environment.

`graft --version` is local-only; `graft version` invokes npm metadata and can return an offline/unreachable message. Check/plan never run the latter. A cached npm answer is not proof of connectivity; offline verification uses a real network control and empty per-case caches.

Managed discovery accepts the package-owned npm entry `dist/bin/graft.js` and the internal `dist/cli.js`; generated MCP/hook bindings retain `dist/cli.js` so existing ownership verification remains compatible. Managed children discard inherited `TRAIL_*` settings, force `TRAIL_INVOKED_AS=graft`, and set `TRAIL_NO_FETCH=1` and `GRAFT_NO_TRAIL_SWITCH=1`; installing Trail elsewhere must not rename managed tools or trigger upstream wiring migration. Note lookup must stay within the selected root: ancestor checkouts outside it are rejected; non-Git roots include the upstream-discovered immediate child checkouts. Each effective checkout's `.trail` and `.claude/skills` trees must have contained real directories and single-link regular files, revalidated before each MCP request.

### Graft pin acceptance scenarios

This source repository keeps scenarios in documentation, not `.feature` files. Chinese scenario text uses English Gherkin keywords; test references describe behavioral coverage, not a separate Gherkin runner.

- **Scenario: 官方 npm 入口可用** — Given 固定版本包的 npm 命令链接到 `dist/bin/graft.js`，When 检查本地可用性，Then 返回该固定版本可用；包外 shim 仍拒绝且不执行。覆盖：`test_check_accepts_official_npm_bin`、`test_check_rejects_package_name_in_unowned_shim_without_execution`。
- **Scenario: 安装不扩展为接线切换** — Given 已展示目标前缀与遥测计划，When 明确确认安装，Then 校验固定包完整性及可运行版本并保持遥测关闭，And 不修改 MCP、PATH 或项目 stamp。覆盖：`test_install_without_confirmation_makes_zero_writes` 及独立前缀真实安装 smoke。
- **Scenario: 新包沿用接线合同** — Given 官方 npm 入口已验证可用，When 生成受管 MCP/hook 配置，Then 使用同包 `dist/cli.js` 且通过既有 ownership 校验。覆盖：真实运行时的配置生成／消费 smoke。
- **Scenario: 宿主环境不能触发 Trail 迁移** — Given 父进程设置 Trail 品牌且 PATH 存在 Trail，And 项目保留 Graft helper，When 受管 MCP 或 hook 启动，Then 工具仍为 `graft_*`，And 不自动迁移或改写项目接线。覆盖：真实固定包的品牌、upkeep、MCP 与 hook smoke。
- **Scenario: 旧运行时或 stamp 不自动修复** — Given 包版本或 stamp 仍为 `0.21.1`，When 新守门入口启动，Then 拒绝执行且不改现场。覆盖：`test_missing_or_old_stamp_never_repairs_itself` 及旧版真实运行时／stamp smoke。
- **Scenario: 新增笔记与技能读取不越界** — Given 笔记有效 checkout 位于选定根之外，或其 `.trail`／`.claude/skills` 包含链接、hardlink 或特殊文件，When 构图、hook、分析或 MCP 请求开始，Then 在读取正文前拒绝且保留现场。普通非 Git 根及范围内普通笔记仍可用。覆盖：`test_trail_notes_cannot_read_linked_or_special_files`、`test_regular_project_trail_notes_are_valid_without_a_graph`、`test_ancestor_note_checkout_is_outside_selected_scope`、`test_single_child_note_checkout_is_validated`、`test_session_start_skill_inputs_are_bounded`，以及 MCP 请求间笔记篡改 smoke。


GitNexus installation and dedicated MCP suggestions are removed. Existing user GitNexus assets are removed only through the confirmed cleanup path (see [Cleanup runtime](#cleanup-runtime)); the npm package, the GitNexus CLI and `~/.gitnexus` global data always remain untouched. Explicit Codex/OMP graph/MCP wiring is described below.

RTK remains optional and retains its confirmation flow. Onboard verifies the binary with an isolated `gain` probe, because running it in an empty user HOME creates a history database. `verificationScope=isolated-probe` means actual user-history directory permissions and contents were not verified. Do not interpret probe success as a repair of the user's data directory.

## npm and nvm

Installing a missing selected Agent or an explicitly accepted npm-backed tool requires npm. A working local Graft/Agent is not blocked just because npm/latest lookup is absent. On macOS and Linux, prerequisite installation remains explicit:

Plain `check` is an inventory, not a selected npm install. Missing npm/Node/nvm are listed under `installationReport.conditionalRuntime` with `status=conditional`, not under its failure buckets or `missing.runtime`. Actual install handlers still validate their required runtimes and reject missing prerequisites before writes.

```bash
python scripts/onboard.py ensure-npm --yes
```

The command installs/loads nvm, installs the latest Node.js LTS, sets the default alias, switches to LTS, and verifies Node/npm.

Native Windows remains manual-required because the POSIX nvm-sh installer is not compatible. Use WSL, nvm-windows, nvs, or another approved Node.js installation, then rerun the installer.

Project-only mode never bootstraps npm. If a user chooses a project-local Playwright or React Bits action and npm/npx is unavailable, report that project action as blocked.

## Required Global Skills

The 14 bundled Skills are always global during normal init/reset:

1. `sbtd-workflow-onboard`
2. `sbtd-task`
3. `project-validation`
4. `web-ui-autotest-generator`
5. `gherkin-bdd`
6. `knowledge-base-integration`
7. `maestro-mobile-e2e`
8. `lessons-record`
9. `book-refactoring-pass`
10. `book-legacy-change-safety`
11. `book-ddd-distilled-modeling`
12. `book-ddia-data-design`
13. `book-release-readiness`
14. `seo-geo`

The retired `trellis-workflow` and `trellis-channel` bundled Skills were removed from the catalog and the template tree in the same atomic change that added `sbtd-task` (source `templates/skills/sbtd-task`); no alias or compatibility copy is installed. User-global copies of the retired directories are deliberately left untouched by this change — their retirement cleanup is owned by the confirmed legacy cleanup path (see [Cleanup runtime](#cleanup-runtime)).

The Onboard rename is a bundled migration: normal `plan` reports any detected legacy target, and normal `init` / `reset` removes it only after the canonical `sbtd-workflow-onboard/SKILL.md` exists with matching frontmatter. Project-only `init-projects` never inspects or modifies global Skill directories.

All 19 referenced external Skills are also required globally:

| Skill | Repository |
|---|---|
| `diagnosing-bugs`, `tdd`, `grill-me`, `grill-with-docs`, `grilling`, `domain-modeling`, `codebase-design`, `handoff`, `writing-for-agents`, `to-spec`, `to-tickets` | `https://github.com/mattpocock/skills.git` |
| `impeccable` | `https://github.com/pbakaus/impeccable.git` |
| `ui-ux-pro-max` | `https://github.com/nextlevelbuilder/ui-ux-pro-max-skill.git` |
| `shadcn` | `https://github.com/shadcn-ui/ui.git`, subpath `skills/shadcn` |
| `ponytail`, `ponytail-review`, `ponytail-audit`, `ponytail-debt` | `https://github.com/DietrichGebert/ponytail.git`, subpaths `skills/<name>` |
| `i-have-adhd` | `https://github.com/ayghri/i-have-adhd.git`, subpath `skills/i-have-adhd` |

### Ponytail Provider Boundary

The four Ponytail Skills are ordinary required external Skills: no install confirmation, no optional group, and a missing or invalid copy is installed or repaired from the vendored stable set with the same transaction semantics as every other required Skill. Onboard is the stable skill-only provider and never installs, enables, disables, trusts, or removes the official Ponytail plugin; `ponytail-gain` and `ponytail-help` belong only to that plugin and are never Onboard-managed.

`check --json` reports `ponytailProvider` with `provider` (`onboard-stable` / `conflict` / `unknown`), `skillStatus` (`complete` / `partial` / `missing` / `invalid`), `pluginStatus` (`installed-enabled` / `installed-disabled` / `missing` / `cli-unavailable`), per-platform detail, and `nextStep`. Detection is read-only: Codex uses `codex plugin list --json`; OMP uses `omp plugin list --json` only when `~/.omp` already exists, because merely starting an unconfigured OMP CLI may create that directory. A missing `~/.omp` reports OMP as `not-configured` without invoking the CLI. Codex matches only canonical `ponytail@ponytail` (or name `ponytail` with marketplace `ponytail`); OMP matches name `ponytail` only when its source / install spec normalizes to the official `github.com/DietrichGebert/ponytail` repository. Same-named third-party packages never count.

An enabled official plugin is `provider=conflict`: `check` exits non-zero and `init` / `reset` block before writing stable copies; the root installers stop with the same guidance. The remedy is manual — disable or remove the plugin with the platform's own CLI, then rerun. An installed-but-disabled plugin is reported without blocking. When any platform CLI cannot be queried or its output cannot be parsed (and no enabled plugin was proven on the other platform), `provider=unknown`: Onboard neither fabricates a clean state nor blocks on unproven conflict.

The runtime gate contracts become active only after normal `init` / `reset` successfully writes the global rules and installs the required bundled / external Skills. The public Skills CLI bootstrap and `init-projects` do not activate these runtime gates by themselves. Installed global `AGENTS.md`, project rules, bundled `sbtd-task`, and bundled reviewer Skills jointly own the execution contract.

The `Book Gate Plan` uses objective predicates and explicit lifecycle states and is produced up front by `strict` tasks. `default` / `lite` tasks select methods by actual risk and explicit deliverables and never fake a chosen method's evidence; project requirements remain binding. Every completed external `grill-with-docs` session invokes bundled `book-ddd-distilled-modeling` in all modes. For strict tasks, persisted/shared data, shared / persistent / cross-request / cross-process caches, async/cross-service flows, ownership, migrations, or recovery invoke `book-ddia-data-design`; existing-behavior bugs or uncertain existing code invoke `book-legacy-change-safety`; any existing-production-code edit invokes `book-refactoring-pass`; production-path runtime/deployment changes invoke `book-release-readiness` after all applicable testing-tool gates and project validation. Matched strict gates emit blocking visible statuses until passed; unmatched scenarios remain on demand.

Install every missing external Skill:

```bash
python scripts/onboard.py install-external-skills --all --scope global --source auto --yes
```

`--scope project` is rejected. Direct normal `init` and `reset` ensure every external Skill exists globally before template writes; the root installers perform the same guarantee before invoking the final mode.

Migrate all recognized legacy mattpocock directories in a specific global Skill root:

```bash
python scripts/onboard.py migrate-external-skills \
  --scope global \
  --source auto \
  --global-skills-dir /path/to/global/skills \
  --yes
```

Source policies:

- `auto` (default): require and validate the reviewed vendored stable manifest, checksum, frontmatter, and complete Skill tree without accessing Git or the network.
- `upstream`: explicitly opt into cloning and validating the current upstream repository group; any acquisition or validation failure is fatal and does not fall back.
- `stable`: use the same deterministic vendored source as `auto`, while recording explicit stable-source intent in `requestedSource`.

Preparation and commit are separate phases. Every selected Skill is resolved, copied into target-filesystem staging, and verified before any canonical or legacy target changes. Manifest paths, configured upstream subpaths, and license paths must remain relative to and contained by their declared roots; absolute paths, `..` traversal, and symlink escapes are rejected. Commit moves existing targets into a temporary rollback directory, installs every staged canonical target, and only then removes legacy aliases.

No automatic source fallback occurs. Stable manifest, containment, checksum, license, or snapshot validation failures are fatal for `auto` and `stable`; upstream acquisition or validation failures are fatal for `upstream`. Target-side staging, permission, disk, commit, and rollback failures are always fatal. A local commit failure attempts to restore all prior targets; if any restore step fails, the transaction reports and retains the rollback directory path instead of deleting the only remaining backup copy.

`init` / `reset --json` embed the required installation report under `requiredExternalInstall` in the single root document, including when installation fails before template writes. Per-Skill source metadata and `transaction` recovery fields remain available; the field is `null` when no required installation ran. Existing root plan fields and exit-code semantics are unchanged.

The vendored stable set lives at `assets/external-skills/stable/`. Its `MANIFEST.json` is the single source of truth for stable-set id, upstream repository, full commit SHA, upstream subpath, local stable path, tree SHA-256, and license/NOTICE files. The snapshots are upstream content copied unchanged. Do not hand-edit them.

Promote a reviewed repository revision explicitly:

```bash
python scripts/onboard.py promote-external-skills-stable \
  --repository <manifest-repository-id> \
  --revision <full-40-character-commit-sha> \
  --stable-set <yyyy-mm-dd.index> \
  --yes
```

Promotion updates every managed Skill from that repository as one group, refreshes its license files and digests, validates the entire candidate stable set, and then swaps the stable directory transactionally. It never runs during normal `init`, `reset`, or external installation.
If upstream changed canonical names, repository layout, or license paths, first review and update the manifest/configured source contract in the same repository change; promotion intentionally refuses to guess a new subpath.

First-time registration of a repository that is not yet in the manifest uses catalog-driven selection:

```bash
python scripts/onboard.py promote-external-skills-stable \
  --repository <new-repository-id> \
  --repo <upstream-https-url> \
  --revision <full-40-character-commit-sha> \
  --stable-set <yyyy-mm-dd.index> \
  --license <spdx-license-id> \
  --license-file "LICENSE=licenses/<new-repository-id>-LICENSE" \
  --yes
```

`--repo` must be a valid HTTPS URL and selects every catalog external entry whose `source.repo` matches it exactly; an empty selection is rejected. `--license` takes an SPDX id, and `--license-file` is repeatable with `SOURCE=STABLE_PATH` mappings. The current manifest is read in relaxed mode for this bootstrap, and catalog equality is enforced only after the candidate tree is fully assembled and validated. For an existing repository, `--repo` may only repeat the recorded URL and `--license` / `--license-file` are rejected, so promotion never silently rewrites repository metadata. Any validation failure leaves the live stable tree unchanged; if commit and rollback both fail, the single recovery directory is retained and reported.

Legacy aliases remain recognized for migration: `diagnose` → `diagnosing-bugs`, `write-a-skill` and `writing-great-skills` → `writing-for-agents`, `to-prd` → `to-spec`, and `to-issues` → `to-tickets`; removed `zoom-out` has no replacement. `migrate-external-skills` first validates every detected legacy target's directory and `SKILL.md` frontmatter identity. If any identity conflicts, it fail-closes before any canonical install, backup, or deletion. It then installs every required canonical replacement using the chosen source policy and shared transaction. When that transaction commits, its legacy predecessors and temporary rollback directory are deleted; the rollback directory is retained only for an incomplete restore. A legacy-only cleanup that needs no canonical install—because the canonical target is already valid or because the legacy target is `zoom-out`—copies the verified legacy directory into a persistent migration backup before removal. Normal `init` / `reset` retain legacy-only automatic migration so already canonical external Skills are not cloned twice during every run.

## Skills That Keep Their Existing Scope

- `caveman`: user-level global and still requires its existing explicit installation decision when missing. Replacement and backup cover only `caveman`, `caveman-*`, `cavecrew`, and `cavecrew-*`; broader `caveman*` / `cavecrew*` prefix matching is detection-only for the fail-closed symlink guard, which also covers nested symlinks at any depth inside an abnormal core. A known version requires the complete mutable family directory set and payload fingerprints to match a reviewed snapshot, using the existing generated-cache exclusions. Matching the core alone never authorizes replacement: partial, mixed, or customized payloads are reported as unknown drift, and an abnormal core cannot authorize replacing unrecognized companions. The staged source must match the pinned full family, and the live target is rechecked before replacement. Known older payloads are backed up before upgrade; replaceable non-symlink abnormal cores may be repaired when no unknown companion exists. Human `plan`, `install-caveman`, `init`, and `reset` reports include refusal reasons, retained backup paths, and restore errors. Caveman maintenance remains optional and does not turn a successful required installation into failure. Hooks, statusline, plugins, and extensions remain user-managed. Monitoring only reports drift; changing the maintenance baseline requires reviewing the complete family and installer / hook behavior and updating ref, revision, core hash, family fingerprints, and tests together. The external Skill owns manual style and intensity; the global AGENTS template owns automatic lifecycle with a monotonic eligibility latch. Only a new primary goal resets it, and protected replies preserve automatic state.
- React Bits Free/Starter/Pro/Ultimate: project-only and conditional.
- Project Playwright CLI / `@playwright/test`: project-only and conditional.

Java 17+ and Maestro CLI remain local development environment prerequisites, not project dependencies. They keep their existing conditional confirmation flow.

## Project Checks

Project-only status is available without global inspection:

```bash
python scripts/onboard.py check-projects \
  --projects-root /abs/project-one,/abs/project-two \
  --json
```

The result contains one entry per root:

- `projectRoot`
- `playwright`
- `reactBits`
- `sbtd`: the selected-state inspection with `status`, `reason`, `nextStep`, `validationScope`, `activeTask`, `bootstrapTask` and `legacyPresent`; a present bootstrap record appears under `sbtd.bootstrapTask.relativePath`

Removed `trellis.*` setup fields have no aliases.

Normal `check` includes the same entries under `projectChecks` while global runtime/tools/Skills remain at the top level.

### Playwright

Playwright is applicable when the project already contains a Playwright dependency, config, script, or E2E directory. A generic `package.json` by itself is not enough to install Playwright automatically.

After confirmation:

```bash
python scripts/onboard.py install-playwright-cli \
  --project-root /one/project \
  --yes
```

This single-project argument belongs only to the project-local Playwright installer; the public root installer still uses plural `projects-root`.

### React Bits

React Bits tier selection is shown only when the root is a React project and contains `components.json`.

- Default: keep shadcn/ui only.
- Free: require an explicitly configured free registry item before running `npx shadcn@latest add <registry-item>` in that project.
- Paid: require an existing entitlement and readable `REACTBITS_LICENSE_KEY`; never print or persist it. When prerequisites pass, add `@reactbits-starter/skill` from the project root with `--path .agents/skills/react-bits-pro --overwrite --yes`, then require `.agents/skills/react-bits-pro/SKILL.md` to exist. An existing target is overwritten without a backup.
- Reset: preserve the detected tier and registry.

## Multi-Project SBTD Setup

`check` / `check-projects` inspect selected state and scaffold conflicts read-only; `plan` exposes the same result in `sbtdInit`. `check-projects --skip-project-agents` excludes that unselected write target without skipping ignore/state checks. Missing optional state is valid and does not prove installation or create files.

The inspector validates the current active pointer and its selected task, plus `ai/tasks/00-bootstrap-guidelines/task.md` when explicitly present. It uses the bundled task v1 schema, safe JSON-compatible YAML, duplicate/cycle/nonfinite rejection, real timestamp parsing, filesystem containment and pointer/record logical-ID agreement. It does not scan history, infer a newest task, modify state, validate full parent/event history, or authorize branch recovery.

An unfinished bootstrap record reports `bootstrap-required`; no bootstrap is created by installation. A done record reports recorded completion only. Legacy `.trellis` yields `needs-user` for explicit migration and stays untouched. Malformed state is `blocked`. Every root retains `status`, `reason` and `nextStep`.

Both root installers gate all global/optional project mutations on the complete selected-project preflight; Python repeats it before its own installation writes. Reject blocking state, nonregular selected AGENTS/ignore targets, a multiply-linked ignore file, or new rules hiding existing unconfirmed reserved data. All roots retain results and a conflict stops the batch; reset preserves optional data. Read-only Agent detection may precede this gate, but installation/MCP writes may not.

Aggregate priority is `failed > blocked > needs-user > bootstrap-required > success > skipped`; exit codes remain 5, 2, 2, 6, 0, 0 respectively. A read-only plan may successfully report a blocked proposed operation without executing it.

## Task State Library (P1-17)

`scripts/sbtd_task_document.py` and `scripts/sbtd_task_state.py` are a host-native Python library shipped with the installed Onboard Skill. They are not `onboard.py` subcommands and do not register a new global CLI, daemon, journal, or background service. Markdown structure recognition uses the declared dependency markdown-it-py>=4,<5 (CommonMark tokens, parse-only, no rendering, no network; Python >=3.10). When the installed helper copy or its declared dependencies (PyYAML, jsonschema, markdown-it-py) are missing, parsing and task-state writes stop explicitly; callers must report that persistence did not run rather than claiming it.

The task document owns mode, status, timestamps and the single `## 状态事件` table; `.sbtd/active-task.json` is only a bookmark. `TaskDocument.parse` / `updated` preserve frontmatter extensions, body and attachments that do not belong to the current operation.

`TaskStore(root, read_only=False)` public operations:

- `inspect(task_id=None)` — read-only; without an id it resolves the active bookmark and checks it against the logical record.
- `create(task_id, body=..., mode=None, mode_note=None, parent=None, shared=False, confirmed=False)`
- `select(task_id, confirmed=False)`
- `transition(task_id, status, reason=..., evidence=..., confirmed=False)`
- `set_mode(task_id, mode, note=..., confirmed=False)`
- `resume(task_id, reason=..., evidence=..., target=None, confirmed=False)`
- `reopen(task_id, reason=..., evidence=..., confirmed=False)`
- `protect_local_state(confirmed=False)` — first-time narrow protection appends only `/.sbtd/` to the project `.gitignore`.
- `promote(task_id, confirmed=False, retire_source=False, include_tasks=())`
- `archive(task_id, reason=..., evidence=..., confirmed=False, retire_source=False, include_tasks=())`
- `current_binding()` — read-only; the actual branch, `detached:<full-sha>`, or `None` for a proven non-Git root.
- `recovery_candidates(task_id=None)` — read-only; the explicit task, the valid active bookmark, or every recorded candidate, never an mtime pick.
- `rebind(task_id, expected_branch=..., reason=..., evidence=..., confirmed=False)` — the only write path that changes a branch binding; records a same-phase event with the old and new binding and never checks out, stashes, or resets blocked recovery history.

Unconfirmed `promote` / `archive` calls return read-only transfer previews. Other mutating calls, including `rebind` and `protect_local_state`, raise `TaskStateError` when confirmation is missing; they do not write. `promote` / `archive` return `TaskTransfer(status, task, source_path, target_path, files, retained_original, completed_steps)`. `protect_local_state` returns a boolean indicating whether protection was added. Failures report `reason`, `next_step` and actual `completed_steps`. Engineering boundaries:

- New tasks default to local `.sbtd/tasks/<id>/task.md`; lite/strict or explicit sharing uses `ai/tasks/<id>/task.md`. Mode and storage are orthogonal. Git projects bind the actual branch or `detached:<full-sha>`; non-Git projects record `branch=null`.
- `cancelled` is terminal but not a successful completion: `completed_at` remains null. Confirmed `transition(..., "cancelled", ...)` accepts planned/in-progress/checking/blocked, refuses a still-unfinished descendant and never cancels children implicitly; done must be explicitly reopened first. `reopen` preserves done/cancelled history, and `archive` accepts either terminal state. Cancelled archive periods use the latest proven cancellation event or `undated`; cancellation is never bootstrap success or an unfinished-work handoff reminder. The task runtime, schema and references must be updated together; an older reader rejecting the new status is not permission to relabel it done.
- Promotion/archive are two-phase: the first confirmed call prepares and verifies the complete target candidate, the effective active reference and the necessary shared index; `retire_source=True` requires an already prepared target plus a separate confirmation, then atomically moves the original directory into `.sbtd/task-originals/<generated>/task`. Originals are retained, never recursively deleted.
- Candidate copies live only in the protected `.sbtd/task-transfer-candidates/` area owned by the current operation and are cleaned up afterwards; they are not a second valid task record, and no journal service exists beside the task document.
- Other logical `task.md` records inside a task directory must each be authorized via `include_tasks`; path nesting is not ownership.
- Unknown or conflicting blocked history requires an explicit user phase choice; no ingress is fabricated and a blocked task never returns directly to done.
- Retries reconcile against recorded state and events instead of appending duplicate completion or release events.
- Windows support, host routing and legacy migration remain later stages; on-demand identity creation is covered by the P1-19 section below. Full validation, real-host proof and release are not claimed here.

## Routing and Handoff Helpers (P1-18)

`scripts/sbtd_task_routing.py` and `scripts/sbtd_handoff.py` extend the same host-native library; they register no global CLI, daemon, journal, scheduler, or `onboard.py` subcommand and reuse the `TaskStore` parsing, protection checks and atomic writes instead of duplicating them.

`TaskRouter(store).route(RouteRequest(...))` maps only facts the host already made explicit to a deterministic `RouteDecision(status, mode, persisted, task, reason, candidates)`:

- `RouteRequest` carries `intent` (`new` / `continue` / `question`), optional `task_id`, `explicit_mode`, `read_only`, `confirmed`, `body`, `mode_note`, an optional `ModeRecommendation(mode, reason, risk_id)`, its `recommendation_response` (`accept` / `keep`) and the `refusal_reason`. The router never classifies natural language or infers intent.
- `continue` resolves exactly one task via `recovery_candidates` before any mode decision: multiple or missing candidates return `needs-task-choice` with the candidate IDs; an unresolved recorded mode returns `needs-mode-choice`; a branch mismatch returns `needs-branch-choice` (correct worktree, explicit `rebind`, or read-only). A task's valid record outranks any old handoff.
- A recommendation for a different mode first returns `needs-mode-decision` without writing or executing; `accept` applies the recommended mode, `keep` requires the user's refusal reason and records the refusal in a structured `mode_note` deduplicated by risk identity, so an unchanged risk is not re-prompted.
- Read-only requests, read-only stores and pure `question` intent return `ready` with the session-only choice and write nothing. A confirmed save that fails returns `persistence-failed`: the session choice stands, the old mode is not restored, and recovery is not claimed reliable. Without confirmation a changed choice returns `needs-persistence-confirmation`.
- A writable `new` request without a task ID returns `needs-task-choice` before asking to persist. Accepted recommendations retain their reason and risk identity in `mode_note`; ordinary free-text notes remain valid. Repeating an already persisted `(mode, user source, note)` choice returns `ready` without reconfirming or rewriting.

`HandoffStore(tasks)` persists continuation snapshots under the protected `docs/handoffs/` only:

- `HandoffPolicy(task_opt_out=False, session_opt_out=False)` carries two independently latched opt-outs; session opt-out is reported first and manual save bypasses neither read-only nor confirmation/redaction checks. `save(task_id, content=..., trigger=..., policy=..., confirmed=False, redaction_confirmed=False)` returns `HandoffResult(status, persisted, path=None, snapshot=None, reason=None)`. Statuses remain `suppressed`, `conversation-only`, `branch-conflict`, `unprotected`, `unchanged`, `pending-confirmation`, `needs-redaction` and `saved`; their full conditions are in `templates/skills/sbtd-task/references/handoff.md`. Deduplication compares only the latest snapshot for the task, excluding `created_at`; older matching history does not suppress a new context.
- `protect(confirmed=False)` returns True when it appends the root-anchored `/docs/handoffs/` rule and False when already protected; missing confirmation, read-only scope, tracked state, or hiding unknown existing data raises `TaskStateError`. Non-Git rules retain literal leading spaces and use the last exact relevant positive/negative rule; uncertain patterns do not prove protection. The helper never initializes Git or overwrites foreign files.
- New file names are `docs/handoffs/{YYYY_mm_dd}-<sha256>.md`, with a fixed-length lowercase SHA-256 digest of the UTF-8 full task ID. Existing reversible full-ID hex names stay readable without renaming. Filename ownership is checked against the full `task_id`; the filename alone is never authority. Snapshot fields remain `schema_version`, `task_id`, `task_path`, `task_status`, `workflow_mode`, `mode_source`, `mode_note`, `project_root`, `branch`, `head` (null for unborn HEAD / non-Git), `created_at`, `content`, `policy`, and `redaction`. Content requires `goal` / `next_action` / `limitations` strings and `decisions` / `completed` / `remaining` / `changed_files` / `verification` / `do_not_repeat` string lists, plus optional JSON-compatible `presentation`; unknown keys are rejected.
- `load(relative_path)` requires the closed schema version 1, a filename key matching the task ID's SHA-256 or legacy reversible hex, and the current `project_root`. Malformed, unowned or foreign files raise `TaskStateError`. Snapshots of any age can be explicitly loaded without changing the task. `reminders(now=None)` returns snapshots at most seven days old, latest per task, for matching root/branch and unfinished tasks; malformed or foreign files are skipped and each returned dict adds its `path`. No automatic session-start capability is claimed.

Whether the Agent truly recommends first and pauses, invokes grill/DDD, or executes a mode's full method remains owned by the Skill rules and real-host proof, not by these return values. Platform, host-wiring and migration acceptance require their own selected-version evidence. The library alone does not prove automatic session-start restoration.

## Developer Identity (P1-19)

`scripts/sbtd_identity.py` implements the lessons identity chain as a host-native library; it registers no global CLI, daemon, initializer, or identity database, and reuses `TaskStore` containment, protection and atomic writes instead of duplicating them.

`DeveloperStore(root, read_only=False)` operations, each returning a frozen `IdentityResult(status, name, source, path, first_write_eligible, topology, reason, needs_protection, completed_steps)` (exportable via `dataclasses.asdict`):

- `resolve()` — read-only. A valid local `.sbtd/developer` (UTF-8, one unambiguous `name=` line whose value matches `^[a-z0-9]+$` verbatim) returns `ready` with `source="local"` and no Git call. Only when the local file is genuinely absent does it verify the real Git toplevel, the absolute git-dir/common-dir and the NUL-separated worktree registry; a verified linked worktree then reads the same-repo main checkout's current identity in place (`source="main-worktree"`), never copying it. Present-but-abnormal local or main files (duplicate declarations, invalid name, wrong type, symlink, unreadable, unsafe parents) return `conflict`, never missing; unknown or unavailable Git metadata returns `blocked`, never assumed non-linked. A verified absent chain returns `needs-name` with `first_write_eligible=True`.
- `plan(name)` — read-only. The same existing identity returns `unchanged`; a different existing identity returns `conflict`; a verified missing target returns `planned`, with `needs_protection` reporting whether the narrow `/.sbtd/` ignore rule is still missing. It downloads nothing, writes nothing and creates no task or spec.
- `ensure(name, confirmed=False, protect=False)` — writes only from a `planned` result: without confirmation it returns `needs-confirmation`; when the required ignore rule is missing and `protect` was not explicitly allowed it returns `needs-protection` (the presence of a name never implies protection authorization). Creation rechecks the chain, writes only `name=<name>\n` non-overwriting, and re-reads before reporting `created`; a concurrent winner is preserved, a same-name retry is `unchanged`, and any failure returns `failed` with the honest `completed_steps`.

`onboard.py` consumes identity only through an explicit `--developer <name>` (validated by the same `validate_developer_name`, accepted at most once):

- `check` / `plan --developer` stay read-only and add a `developerPlan` object to the single JSON document: `requestedName`, aggregate `status`, `reason`, and a `projects` list whose entries carry `projectRoot`, `requestedName`, `status`, `name`, `source` (`local` / `main-worktree` / null), `target` (the `.sbtd/developer` path), `topology`, `needsProtection`, `reason` and `completedSteps`. A conflict, blocked or needs-* aggregate, or an empty project scope, exits 2 — the name is never defaulted to cwd or HOME.
- `init` / `reset` / `init-projects` apply the name only to the explicitly listed projects together with `--yes`; the full-batch identity plan is checked before any global or project mutation, so an existing conflict is refused before side effects rather than after another project was written. A `planned` entry that still needs protection goes through the existing confirmed scaffold ignore flow first, then `ensure(confirmed=True)` re-verifies; identity ensure never replaces the whole initialization flow nor rewrites `TaskStore` protection. A post-write identity failure exits nonzero with the single JSON document preserving partial results. A same-name inherited main identity is `unchanged` with no local copy.
  Only an original plan entry with `needsProtection=true` forwards protection authorization to `ensure(protect=True)` after the user confirms that listed initialization scope. This lets a verified non-Git project complete the existing narrow final-root-rule safeguard; an unplanned new protection need remains unauthorized. The helper never initializes Git or broadens the project list.
- Once identity initialization follows completed scaffold writes, JSON retains their actual `operationResults`. Identity failure also reports post-write `sbtdProjectSetup`, `developerPlan`, backups and unverified checks in that same document; it does not imply rollback. A project root becoming unavailable is a per-project `blocked` preflight or `failed` write result, preserving earlier projects' completed results instead of aborting with a traceback.
- Text-mode writes print the final developer result as well as preflight. Identity outcomes `conflict`, `blocked`, and `needs-*` exit 2; actual `failed` outcomes exit 5. Completed writes remain reported for either category.
- Without `--developer` nothing changes: no command creates, repairs or requires an identity, and `reset` preserves any existing file.

Ordinary resolve/plan/check/global installation never reads `.trellis/.developer`; authorized legacy identity migration remains separately gated and is not performed by this helper alone. The root installers forward the implemented public flags without adding a developer-specific option. Use the selected version's native-platform, integration and release evidence rather than inferring acceptance from the identity API.

## Migration Runtime

The installed Onboard script exposes `migration --phase plan`, `apply`, `verify`, `reconcile` and `cleanup`, plus the separate `recovery --phase plan|apply` mode and the fresh-detection `cleanup-legacy --phase plan|apply` mode. This is not a second CLI, and there is no positional `migration plan` alias. Batch cleanup consumes the bound verification record and an explicitly confirmed `verification_id`; recovery consumes the manifest-scoped evidence chain and an explicitly confirmed `plan_id`; `cleanup-legacy` consumes a freshly sealed cleanup plan and an explicitly confirmed `plan_id`. Before a real-project cutover, verify the selected version's integration and applicable native-platform evidence, then obtain the separate exact-scope deployment authorization. A release tag does not grant that authorization.

### Authorized preparation and plan

- Resolve the actual selected project roots, whole shared HOME/host batch, custodian and private storage explicitly. Never infer authorization from a valid checksum or a sample label.
- Prepare an existing owner-private vault outside every selected project. Publication decisions and approved candidates must already exist inside that vault; plan never creates them. POSIX owner/mode and Windows ACL checks are separate; unproven privacy, links, aliases or unknown types block.
- `routing-approvals` is a separate private record for an already approved AGENTS.md candidate. The record must include an Ed25519 signature over its canonical `schema_version` and `items`. Apply and plan verify that signature with `assets/routing-approval.pub` from the installed package, resolved from the installed script path. The public key is not read from the manifest or from a caller path. Plan may sign an existing approval file only when given `--routing-approval-key`; that key must stay outside the vault and selected projects, its path is not sealed, and a key that does not match the installed public key is rejected before the signature is written. Apply does not read a private key. The caller must still pass `--routing-approvals`; its SHA must match the sealed record, and the operation set is rebuilt from that file. A caller who points that path at an attacker file fails signature verification before write. Without that file, apply requires explicit `--no-routing-approvals` and refuses pause-block append or management-block deletion on `AGENTS.md`. Omitting both is not "no approval".
- Characterized legacy **data** versions are Trellis `0.6.15` and `0.6.17`; unknown or unproven versions still reject, without editing the original stamp. This does not widen the separately pinned vendor-uninstall CLI version. Generated runtime files remain in the private-preserved legacy tree until later cleanup. Unknown ownership or customized/mixed shared configuration blocks for reconciliation; a mutable legacy hash alone cannot authorize deleting foreign entries. Old configuration pins are compatibility facts, not a latest-version update target.
- Gitignored paths under `.trellis` that sit outside the known layout are incidental. Plan does not require approval for them, but the directory snapshot still contains them, so later cleanup removes them together with the rest of `.trellis` through the vendor uninstall. `tasks`, `spec` and `lessons` stay in the approval closure even when gitignore matches them. A path outside that layout that git does not ignore stops the plan and is listed for an explicit decision; plan does not delete it.
- For the characterized 0.6.15 metadata shape only, hash entries under `.trellis/lessons/`, `.trellis/.runtime/` or `.trellis/.DS_Store` are recorded-byte claims, **not generated ownership**. Their original metadata and full inventory remain bound; they neither authorize individual removals nor exempt user content from publication/private-preservation approval. The existing 0.6.17 metadata restrictions, safe-path checks, generated-file drift checks and shared-configuration pins remain unchanged. A revalidation resolves version and metadata from the sealed inventory, including retained originals after legacy retirement.
- A stale generated-file digest may additionally match a reviewed official-template pin in the installed `assets/migration-legacy-ownership.json`, for that exact relative path and normalized content only. Each pin records its package version, source member/rendering and release integrity; it does not authorize a different path, extra user content or shared-config ownership. Runtime validation is offline, preserves the original `.version` / `.template-hashes.json`, and rechecks the same content policy against sealed/retained originals. Template release versions are distinct from the accepted legacy data layouts and vendor-uninstall CLI pin.
- Mixed project `AGENTS.md` is never included in that generated-file recognition. Only the existing signature-verified routing replacement, bound to the actual file before-state and exact private candidate, can supersede its stale whole-file template digest. Missing/invalid approval or drift still rejects. Preserve applicable project rules in the reviewed candidate; replacing retired tool routing is not permission to overwrite unrelated rules.
  Migration deployment must preserve the exact project-rule body from that verified approval. Remove only the exact native maintenance-pause prefix and its separator, then use the existing managed Graft-fence renderer; do not replace the approved body with the generic project template. Provenance, preflight, retries, verification and recovery must agree. Merely starting with the pause text is not approval. Ordinary explicitly template-installing init and projects without an approved replacement retain their existing behavior; no-touch AGENTS remain untouched.
- Retained-original validation also preserves Git's ignore boundary: checksum-bound retained `.gitignore` rules cover recorded binary caches, unrecorded generated caches and ignored incidental paths; tracked files and required task/spec/lesson publication stay protected. An excluded ancestor directory cannot be re-included by a descendant negation, while a genuinely effective negation still rejects unapproved content. Missing Git/rule proof does not authorize a live-only ignore fallback, and coherently re-sealing a manifest does not prove foreign generated bytes.
  To preserve the entire Git hierarchy, retained checks may build an automatically removed owner-private temporary tree containing only ignore rules, using the real repository's Git metadata in read-only mode. They do not copy task payloads, initialize/register a Git repository/worktree, write the real index, or change the project or vault.
- A project with no proven legacy host may seal `platforms: []` only when the known project host roots are genuinely absent. Presence/type probes do not read an unowned host directory's contents. A newly appearing host root before apply rejects rather than reusing the old absence assumption. Empty platforms do not waive recorded root-marker operations, identity/protection operations or their approval gates; dropping a required marker operation from a re-sealed manifest still rejects. No platform files or registrations are synthesized.
- An already aligned root `AGENTS.md` may be retained without a replacement or signature only when it is byte-identical to the executing package's project template and is bound as unchanged evidence in the manifest. No AGENTS removal/copy operation is created. Every later phase revalidates that proof; a customized or drifted document is not covered by this exception, and old ownership metadata is never rewritten.
  This zero-write requirement also applies to declared deployment and successor/followup batches: preserve and re-prove the same target/current-template evidence, omit only the AGENTS configuration operation, and retain the independent graph build. It does not append a Graft fence to that file or exempt a later custom edit.
- Legacy files below `tasks/` that have no owning ancestor `task.json` are historical documents, not inferred tasks. Explicit file publications map them to `docs/legacy-archive/tasks/<the exact suffix below legacy tasks>`, preserving names as opaque history rather than claiming dates/status/identity. Every file needs exact source/candidate coverage and the existing privacy/link checks; actual task attachments cannot be diverted through this route.

#### Legacy compatibility acceptance

本仓库不生成 `.feature`；以下中文场景配合既有公开 API／CLI unittest 作为兼容性行为规格。`cancelled` 是取消终止，不是成功完成；只读 plan、真实确认、完整私有原件与当前状态绑定的门不因兼容输入扩大而省略。

| 场景 | Given / When / Then | 验证边界 |
|---|---|---|
| 取消不冒充完成 | Given 未终止任务及明确取消理由；When 用户确认取消；Then 状态为 cancelled、completed_at 为 null，取消事件只追加一次 | TaskStore lifecycle |
| 终止仍保护子任务 | Given 父任务有未终止子任务；When 取消或归档父任务；Then 拒绝，不静默取消子任务；已取消子任务不作为未完成工作 | TaskStore parent/child |
| 取消历史可归档与重开 | Given 已取消任务；When 显式归档或重开；Then 保留取消事件，重开回 planned；归档只用已证明取消时间或 undated，不借 completed_at 或目录名制造时间 | TaskStore archive/reopen |
| 导入真实状态 | Given 旧 cancelled 或 blocked 状态及其原件；When 校验投影；Then 保留原状态、未知模式和时间，不改成 done、不损失 sidecar／私有真值 | Legacy task projection |
| 未知阻塞历史不能自动恢复 | Given 旧记录仅证明当前 blocked；When 续作恢复；Then 必须明确选择恢复阶段，不发明进入 blocked 前的阶段；矛盾理由／时间仍拒绝 | Legacy projection + TaskStore |
| 无宿主不是未知宿主 | Given 已知旧数据但没有已配置平台，且相关宿主路径确实不存在；When 计划迁移；Then platforms 为空、不生成虚构宿主操作；存在未认领或异常宿主路径时仍拒绝 | Migration plan |
| 旧元数据不能认领用户内容 | Given 受支持旧版本的元数据提及 lessons／runtime／杂项；When 计划与复验；Then 原元数据保留，用户内容不变成受管生成文件，必要发布／保全覆盖仍需审批；逃逸路径、未知版本及不明共享配置拒绝 | Migration plan and operation validation |
| 兼容不等于授权 | Given 格式兼容但批准缺失、候选漂移或源改变；When plan/apply/recovery；Then 非零拒绝并保留原件，不用重试或版本兼容绕过 | Native CLI / migration lifecycle |
| 脱敏不能由派生字段反向泄露 | Given 理由或取消／暂停时间已按 JSON pointer 脱敏；When 校验 task.md；Then 理由使用固定脱敏说明、事件时间为 unknown、取消归档为 undated，拒绝原值回填；原件只留私有保全 | Legacy projection privacy regressions |
| 新一轮阻塞不继承已取消阶段 | Given blocked→cancelled→reopen；When 再进入工作阶段并阻塞／恢复；Then 恢复到本轮真实阶段，不复用上一轮 ingress | TaskStore repeated block lifecycle |
| 取消不能冒充恢复重试 | Given 最后事件是 blocked→cancelled；When 调用 resume；Then 拒绝且原件字节不变；只有 blocked→当前 planned/in-progress/checking 的真实恢复事件可幂等返回 | TaskStore resume |
| 已知时间矛盾不能被脱敏掩盖 | Given 已证明的取消／暂停时间早于已证明的创建时间；When 校验旧任务；Then 拒绝投影，不通过脱敏或改成 unknown 修复原始矛盾 | Legacy projection chronology |
| 精确官方模板不依赖过期登记 | Given 登记 hash 过期但实际内容命中同路径已审核发行钉；When plan 与原件复验；Then 接受识别且不改旧元数据；额外改字节、换路径或未知模板拒绝 | Public migration plan / revalidation |
| 混合规则只能明确批准替换 | Given AGENTS 含项目规则且登记 hash 过期；When 用户提交已有签名机制批准的精确前态和候选；Then 按批准替换识别，不把整份文档认领为生成资产；缺签名或任一漂移仍拒绝 | Signed routing approval / apply / recovery |
| 已对齐规则保持不动 | Given 项目 AGENTS 与执行包的项目模板逐字相同；When 计划与后续复验；Then 封存并验证 unchanged 证据，不签名、不覆盖；自定义或漂移内容仍拒绝 | Native plan / apply / replay |
| 仅文档历史不伪造任务 | Given 历史目录只有文档、无所属 task.json；When 明确批准逐文件归档；Then 保留源相对结构及完整内容，不补 task 身份／状态／日期，遗漏、重复或伪装真实任务附件仍拒绝 | Native publication / inventory |
| 历史分支交接不改现场 | Given 历史任务分支不同于迁移 checkout；When 导入真实交接；Then 保留旧分支、标明当前 HEAD 的迁移取证语义与后续明确恢复要求，不 checkout、不自动 rebind/select | Migration handoff / TaskStore |
| 批准正文跨部署保真 | Given 已验签的项目规则候选含项目专属约束；When apply后部署、重试或恢复；Then 正文除精确维护前缀外保留，只更新受管Graft段；未批准文字不能借暂停前缀获得此例外 | Native migration deployment / retry / recovery |

#### Canonical legacy task candidates

The v2 candidate validator binds mapped state to the preserved `task.json`, rather than accepting prose as machine evidence. Unknown old fields stay in `legacy-task.json` (or the private original); they must not become current frontmatter extensions. Independently validated current fields are regenerated, not copied from coincidentally named old fields.

- Unproven mode is `workflow_mode: null`, `mode_source: migration-unknown`, and `mode_note: legacy Trellis task without mode proof`.
- A proven completed legacy task has one `unknown -> done` event. Its reason is exactly `legacy completion fact`, evidence exactly `legacy task.json status`, and time is the provable completion timestamp or `unknown`. Extra narrative belongs outside that authoritative event.
- A cancelled legacy task stays `cancelled`, keeps `completed_at: null`, and records exactly one `unknown -> cancelled` fact with reason `legacy cancellation fact` and evidence `legacy task.json status`. Only a valid full RFC3339 `cancelledAt` supplies an event time and archive quarter; a missing/date-only value gives an `unknown` event and `undated` archive, retaining the original day privately/in the sidecar. Do not derive a date from the archive folder or add a fabricated completion.
- A blocked legacy task stays `blocked`. Its `blocked_reason` comes from a nonblank source `blocked_reason` or `meta.suspension.reason`; conflicting or malformed declarations reject the projection. When neither was recorded, the canonical text is `legacy task.json status=blocked; reason not recorded`, describing missing evidence rather than inventing a cause. Exactly one `unknown -> blocked` fact uses reason `legacy blocked fact`, evidence `legacy task.json status` and the proven full `meta.suspension.since` timestamp or `unknown`. This first historical fact is not a normal blocked ingress; recovery still requires the user's explicit prior-phase choice. Archived blocked records remain rejected.
- Publication redaction applies to these newly derived optional details too: if a supplied blocker reason is covered by a redacted JSON pointer (including an ancestor or root-private snapshot), `blocked_reason` must be `legacy task.json status=blocked; reason redacted`, not the private value. Redacted `cancelledAt` / `meta.suspension.since` yields an `unknown` fact time; cancelled archive placement follows that published fact, hence `undated`. This does not relax source validation: malformed/conflicting reasons or a proven cancellation/suspension timestamp before proven creation still reject, even when hidden. Existing core identity/status/frontmatter provenance rules remain unchanged.
- A date-only `createdAt` remains an unknown instant, but is a recorded calendar-day boundary: a cancellation/suspension timestamp with an earlier recorded date is rejected for reconciliation. The same recorded day remains allowed; no midnight, timezone or creation instant is invented.
- The task body has exactly one top-level `sbtd-legacy-time-provenance` fenced JSON block. Include exactly the timestamp fields whose current frontmatter value is null, using the following fixed source/status values; omit a field when its timestamp is provable. These labels refer to preserved source facts, not public JSON pointers: they remain truthful when the shared sidecar is redacted or root-private.

```sbtd-legacy-time-provenance
{
  "created_at": {"source": "legacy task.json: createdAt (sidecar or private original)", "status": "unproven"},
  "updated_at": {"source": "legacy task.json: no recorded update time", "status": "unproven"},
  "completed_at": {"source": "legacy task.json: completedAt (sidecar or private original)", "status": "unproven"}
}
```

Candidates prepared under the earlier permissive grammar must be regenerated in the private preparation area and reapproved; do not rewrite an already sealed manifest or its approved bytes. Historical archive positions map to the proven quarter or `undated`; an ordinary completed task is not automatically archived. Local Markdown links/images must resolve to approved publication targets; escaping paths, local file URLs and unsafe schemes are rejected.

**Link-policy boundary:** reject any Windows drive prefix (`C:secret.md`, `C:/secret.md`, or `C:\secret.md`, including percent-encoded spellings) before treating a URI scheme as external. Ordinary project-relative links still need an approved target. Other protocols keep the existing markdown-it safety policy: this is not HTTPS-only and does not ban every data URI; HTTP, mailto and parser-approved image data URIs remain supported, while unsafe destinations remain rejected. Validation never fetches the link.

**Exit-policy boundary:** a rejected link remains a pre-publication `target-conflict` (the CLI reports blocked/2). This repair does not change execution-phase status aggregation, preservation failures or partial-receipt semantics. Any broader 2/3/5 reclassification must separately define preflight refusals versus failures after writes and update the matching status/retry contracts; it is not bundled with this path fix.

**Private continuation handoffs (PLAN-008):** the fixed legacy format is `.trellis/.runtime/sessions/*.json` with `current_task`; nonempty old `.current-task` path lines and unknown session shapes require reconciliation. Workspace journals remain complete private originals. If journals exist, every unfinished migrated task needs its own explicitly approved handoff; session-only context requires the referenced unfinished tasks. Multiple tasks are preserved separately, never auto-selected.

Prepare each reviewed, redacted summary in the private vault using the existing `HandoffStore` Markdown snapshot format. Its publication item uses `decision: redact`, `required: true`, binds every original journal/session file in `sources`, and targets `docs/handoffs/{YYYY_mm_dd}-<sha256-of-task-id>.md`. Match the migrated task's identity/path/state/mode/branch and the planned HEAD; supply a nonblank goal, remaining work and next action. Approval covers the exact candidate bytes and source snapshots. The planner generates neither summaries nor approvals. Raw journals, private hashes and session metadata remain in the private backup rather than shared task records.

Historical branch bindings may differ from the migration checkout only with explicit deferred-recovery provenance in the handoff. Preserve the source task's branch verbatim and bind the observed migration HEAD without claiming it is the old branch's HEAD. The handoff must make the mismatch and need for a later explicit recovery/rebinding decision clear; import does not check out a branch, activate a task, or relax normal TaskStore/HandoffStore write gates.

Plan is read-only. Apply uses existing ignore protection and copy operations; retry, verify, cleanup and recovery retain their bound-original and candidate checks. Missing approval, stale/foreign task references, unknown runtime content without a private-only decision, changed candidates or tracked handoff storage block. An explicit private-only item can skip one whole legacy task folder or preserve spec files without publication or a handoff; lessons still need a share/redact projection, and a missing or partial skip still blocks. A session pointer to that complete skip is allowed. Unknown, external, or partial-skip pointers still block. A handoff can be loaded through `HandoffStore` after apply, but does not set active-task or choose a mode for an unproven legacy task.

Command shapes below require actual authorized values in place of angle-bracket arguments:

```text
python <installed-onboard.py> migration --phase plan --projects-root <comma-separated-absolute-roots> --backup-root <external-private-vault> --custodian <actual-label> [--publication-decisions <private-file>] [--routing-approvals <private-file>] [--routing-approval-key <private-key-outside-vault>] [--successor-manifest <private-manifest-file> --successor-apply-receipt <complete-private-receipt> --deployment-mode init|init-projects] --json
python <installed-onboard.py> migration --phase apply --manifest <private-manifest-file> [--apply-receipt <prior-private-receipt>] (--routing-approvals <private-file> | --no-routing-approvals) --yes --json
python <installed-onboard.py> migration --phase verify --manifest <private-manifest-file> --apply-receipt <complete-private-receipt> --deployment-evidence <private-deployment-file> --json
python <installed-onboard.py> migration --phase reconcile --manifest <private-manifest-file> --apply-receipt <complete-private-receipt> --missing-deployment-evidence <absent-private-path> --deployment-evidence-out <new-private-path> --yes --json
python <installed-onboard.py> migration --phase cleanup --manifest <private-manifest-file> --apply-receipt <complete-private-receipt> --deployment-evidence <private-deployment-file> --verification <private-verification-file> [--cleanup-receipt <prior-private-cleanup-receipt>] --confirm-cleanup <current-verification-id> --json
python <installed-onboard.py> recovery --phase plan --manifest <private-manifest-file> [--apply-receipt <partial-apply-receipt>] [--deployment-evidence <partial-deployment-evidence>] [--cleanup-receipt <partial-cleanup-receipt>] [--projects-root <comma-separated-absolute-roots>] --json
python <installed-onboard.py> recovery --phase apply --plan <private-recovery-plan-file> [--recovery-receipt <prior-private-recovery-receipt>] --confirm-recovery <current-plan-id> --json
python <installed-onboard.py> cleanup-legacy --phase plan --projects-root <comma-separated-absolute-roots> --backup-root <existing-private-directory> [--global-skills-dir <skills-root>] --json
python <installed-onboard.py> cleanup-legacy --phase apply --plan <private-cleanup-plan-file> [--cleanup-receipt <prior-private-cleanup-receipt>] --confirm-cleanup <current-plan-id> --json
```

Each command returns one envelope. Subsequent file arguments require the corresponding bare subobject: `response.migration.manifest`, `response.migration.apply_receipt`, `response.migration.verification`, `response.migration.cleanup_receipt`, `response.recovery.plan`, `response.recovery.receipt`, or `response.cleanup_legacy.plan` / `response.cleanup_legacy.receipt`; reconcile returns the bare `response.migration.deployment_evidence` document plus its absolute `deployment_evidence_path`; the whole response envelope is not a manifest/receipt/plan. Store output only in the authorized private location. Explicit caller-side saving does not make plan/verify writable.

A successor deployment batch repairs a completed batch whose sealed plan carries no deployment declaration: pass `--successor-manifest` and `--successor-apply-receipt` as a pair (no directory discovery; each stays in its own private directory — the manifest directory and the backup vault are separate private areas) together with an explicit `--deployment-mode`. The predecessor must have `deployment: null`, no successor binding of its own, and a fully successful apply receipt. The planner re-verifies the bound documents, the exact root set, vault and custodian, and re-measures every completed apply outcome and every carried cleanup target; any drift blocks instead of relaxing the pre-state. The sealed successor manifest carries only the pending legacy/skill retirements plus the deployment closure, inherits the predecessor retention verbatim, embeds the predecessor's succeeded apply results under `payload.successor` alongside `manifest_ref`/`apply_receipt_ref` content-hash references to the real predecessor files — those two files must not be moved or rewritten for the lifetime of the successor chain — and lets deployment `before_requirement` reference them across manifests. Every consumer (apply/deploy/verify/cleanup) re-loads the referenced predecessor documents and rejects altered embedded results, a reduced carried cleanup set, or drifted completed outcomes. Apply, verify, cleanup and recovery consume the chain through the ordinary bound documents with no new flags. Successor inputs are mutually exclusive with `--publication-decisions` and the routing-approval options.

### OMP follow-up deployment

Use a followup batch only after a Codex predecessor has completed apply, deployment, verified verification and cleanup. This is a separate path from a successor batch; successor-of-successor stays rejected. The predecessor may be an original or successor batch, not another followup. All five files must be supplied together; do not discover them by scanning directories:

```text
python <installed-onboard.py> migration --phase plan --projects-root <same-absolute-roots> --backup-root <same-private-vault> --custodian <same-label> --followup-manifest <predecessor-manifest> --followup-apply-receipt <predecessor-apply> --followup-deployment-evidence <predecessor-deployment> --followup-verification <predecessor-verified-record> --followup-cleanup-receipt <predecessor-cleanup> --deployment-mode init --deployment-platform omp --json
```

Followup inputs are plan-only, mutually exclusive with successor/publication/routing approval inputs, and reject hooks. The manifest seals five immutable file references and their IDs under `payload.followup`; preserve those files in their private locations for the entire followup lifetime. Every consumer rechecks their bindings, success states, retained backups and non-overwritten outcomes. Project roots, platforms, vault, custodian and retention are inherited; Git revision is observed again. Missing ignore protection blocks instead of adding a data-migration operation.

Review the complete plan before authorizing deployment: it includes project AGENTS/graphs, canonical global rules/Skills and OMP MCP, not just one MCP file. An older managed installation can be replaced only when its target and current state are proven by the predecessor's successful results. Unknown customizations remain conflicts. The new batch uses concrete before-states, empty project sources and no apply/legacy-cleanup operations; it does not relax old successor rules or the current batch's runtime/source checks. Historical predecessor source files need not equal the new release's templates.

Predecessor-owned overwrite targets bind differently by ownership: configure-graft section targets (Codex config.toml, hooks.json, OMP mcp.json, project AGENTS.md fences) prove their managed section and seal the current live snapshot, so fence-exterior host or user text carries over; directories and other whole-resource targets still pin the recorded historical after-state, and resealing a followup cannot adopt later user changes. For section targets the interpreter, node and cli paths are checked by argv shape and cross-entry consistency only — a same-shape path swap still passes. Codex launchers must sit inside a live directory deployment target from the same gate run — retired cleanup targets never anchor — and managed hook commands must match the canonical render for their event; OMP launchers stay shape plus cross-entry consistency because that chain has no verified directory containing them. Directory upgrades pass their verified retained backup to the existing replacement primitive so recovery can restore the older installation. Deployment evidence output cannot overlap predecessor/ancestor documents, source or stage backups, publication candidates, report artifacts or other sealed inputs; a new file inside a protected directory is also an overlap. A disjoint sibling evidence directory within the private vault remains allowed.

After saving the bare manifest privately, use the ordinary confirmed apply with `--no-routing-approvals`, then the existing `init` migration deployment context and ordinary verify inputs for this new batch. No new flags are needed by later phases: the manifest carries predecessor references. Empty cleanup does not authorize deletion. Recovery restores only this followup's proven writes to its own before-state; it does not undo predecessor cleanup, reactivate Trellis or remove any predecessor/followup backups. Actual HOME deployment, OMP session restart and `initialize` / `tools/list` / root-bound query proof remain separately authorized operational work.

### Apply, retry and verification

Apply first checks the complete batch and current runtime/input bindings, retains full original bytes and empty directories, then installs only approved projections and required local protection. Legacy identity is explicitly extracted into a genuinely missing current identity; ordinary identity lookup is unchanged. Proven owned Codex and existing OMP global routers receive the maintenance pause, with one shared result and full declared dependent-project closure. An absent OMP root is not created. The existence check classifies only that root and does not walk its children. Every path component, including parents, is checked without following links. A link, file, or special entry on that path is rejected. Unrelated links inside the directory are not an existence failure and are not modified.

Successful or handled partial applies atomically save a new `apply-<apply_id>.json` beside the manifest before returning its copy. Retry must explicitly supply that receipt; completed unchanged resources and their original backups are preserved, only legal unfinished work resumes, and unattempted shared operations cannot be reported as observed. There is no implicit receipt discovery, cross-resource transaction, guessed rollback, or deletion of old data. If receipt persistence or preservation fails, stop and retain all private artifacts; do not retry from guessed state.

Verify requires complete successful apply plus bound deployment evidence and actual native report files; it never invokes deployment or smoke. When the bound deployment evidence carries the current-state reconciliation marker produced by `migration --phase reconcile`, a successful verify still returns `verified` and exposes `verification.payload.acceptance_basis = "current-state"`; the marker is bound to that exact evidence, ordinary executed evidence verifies without the field and remains valid, and a fabricated or mismatched marker rejects. It rechecks source/revision/runtime, originals/backups, approved publications, report digests and scope, actual retained resources and future cleanup candidates. A route whose latest bound successful operation proves `after=absent` is not a retained present asset; missing publications or an unproven disappearance still fail.

Native report schemas remain unchanged. Outer migration `source_ref` stays null for a detached or non-Git project. Native report `sourceRef` is the explicit label `HEAD` for detached Git with the exact OID, or `non-git` with null commit and unknown source revision outside Git; these labels are not invented branch names. Ordinary named refs remain exact. First-deployment report times must lie inside that deployment attempt. A cumulative retry may retain successful report bytes only within the same bound apply epoch, from the supplied apply receipt's `finished_at` through the latest deployment finish. Reports still require exact root/ref/OID, verified environment, non-mock smoke mode, command, captured stdout/stderr and clean exit; an optional `processExitCode`, when present, must also be integer zero.

Declared non-API auxiliary reports require native evidence v2 and a supported `junit-xml-v1` or `playwright-json-v1` report, with a uniquely matched passing case carrying the source-locator digest. Every linked locator must match the enclosing repository key, source ref and commit. Unsupported/untyped auxiliary reports fail closed. Auxiliary report mode does not trigger the API genuine-mode gate, and an auxiliary report never replaces the required genuine API smoke. A state-consistent batch report may be referenced by multiple projects; conflicting states or strict ancestor/descendant report paths remain invalid.

`tool_versions` binds installed migration source/assets, declared dependency versions and Python, plus the selected Graft target pin; it is not proof that Graft or a host was executed. A consumer may accept one predecessor runtime only when its signed pairing verifies with `assets/runtime-lineage.pub`, the current `onboard` hash equals that successor, and the caller supplies the manifest's complete successful apply receipt. After callers validate the full evidence bindings, known deploy and cleanup outcomes supersede apply outcomes in that order; a bound recovery receipt then supplies the latest succeeded inverse state. Current targets must match that latest proven state and retained backups must still match. Unknown forward states are rejected, not replaced by an older apply state. A failed stage can have a known changed outcome: recognizing it does not permit ordinary partial-write retry; explicit recovery still requires its valid before backup and confirmed plan. An ordinary apply retry receives no later-stage evidence and still requires its own apply outcome.

The pairing file stays outside the runtime fingerprint; the public key and verification code stay inside it. An unlisted successor, bad signature, incomplete apply receipt or evidence mismatch remains fail-closed. This exception neither waives fresh-plan checks nor authorizes a new write. Consumer fixtures prove their stated boundaries, not real host deployment; Windows ACL execution and host deployment require their own environment proof. No valid hash or task status waives a missing required check.

### Current-state reconciliation of missing deployment evidence

Reconcile is the narrow repair for exactly one gap: apply completed successfully and the declared deployment resources were actually produced, but the cumulative deployment evidence was never saved (for example, the process was interrupted before its final evidence write). It never backfills or forges the missing historical receipt: it freshly observes the current state and saves one new, explicitly typed evidence document at a new path. If the historical evidence file exists, if the apply receipt is not complete and successful, or if any sealed input has drifted, reconcile rejects and the ordinary deploy/retry path remains the only route.

```text
python <installed-onboard.py> migration --phase reconcile --manifest <private-manifest-file> --apply-receipt <complete-private-receipt> --missing-deployment-evidence <absent-private-path> --deployment-evidence-out <new-private-path> --yes --json
```

- Consent is explicit: without `--yes`, reconcile blocks before any write or smoke run. Both evidence paths must be absolute, physical and inside the original manifest's private directory; the missing path must genuinely not exist, and the output path must be new, non-overwriting and distinct from the missing path, the manifest, the apply receipt and every declared or protected resource. The missing historical path is never written.
- New evidence names also reserve case- and Unicode-equivalent spellings conservatively, even on case-sensitive filesystems; this publication guard does not change managed-resource identity. Originally absent backup slots must remain absent through the fresh checks and publication, and retry publication rechecks that the cited historical receipt has not appeared.
- Reconcile revalidates the exact original manifest and apply bytes (hash-bound), the sealed root/revision and closed declared resources, the installed policy and the signed runtime lineage, then re-derives every sealed deploy operation and re-measures current state. Every non-absent before-state must still match the deterministic original backup in the private vault; drift fails closed. Fresh report files come from real smoke runs inside the new observation window; caller-supplied old reports or resource results are never accepted. Approved project-rule bodies, no-touch AGENTS and all apply/source backups keep their existing protections.
- Writes are limited to the fresh private report files and the single new evidence document. Reconcile never runs deployment execution, apply, cleanup or recovery paths and never changes task state; sealed manifest bytes, versions and runtime pins are never resealed or rewritten.
- The new document is ordinary `deployment_evidence` plus an explicit `payload.reconciliation` marker: `kind: current-state`, `historical_execution: unknown`, hash-bound references to the exact original manifest and apply bytes, the proven-absent missing-evidence path and the actual runtime versions. Its `started_at` / `finished_at` describe this observation window only — no historical exit code, success claim or old timestamp is invented. Each result's `before` is the sealed phase requirement proven by the retained original (or its planned absence); `after` is freshly measured current state. With the marker present, `succeeded` means the current postconditions were accepted, **not** that the original deployment process was observed to exit cleanly and **not** that any new target write occurred: current-state evidence is not prior process completion.
- Actual consumers recheck both cited source objects as safe files with matching digests; the pure JSON binder still reads no filesystem. The observer must match the manifest runtime or its signature-approved forward successor. New cross-runtime observations preserve the original signed object in `observer_lineage`, verified against the installed trusted public key even after the current pair file rotates. The evidence carries no trust key. Older records without this field retain only same-runtime or matching-current-pair acceptance; missing old authority is never reconstructed.
- The success envelope reports `phase=reconcile`, `status=reconciled`, a null `verification_id`, per-project reconciled status, and `migration.deployment_evidence` (bare document) with its absolute `deployment_evidence_path`; failure uses the existing sanitized blocked/failed envelope with an empty migration object. Reconciliation provenance is immutable through later cumulative retries — a retry cannot launder it back into executed origin — and later cleanup/recovery planning consumes genuine reconciled evidence coherently without re-demanding the old live after-states.
- Later verify, deployment retry, cleanup and recovery context checks also require the cited historical-evidence path to remain absent. If that file or any other object reappears there, the current-state proof is ambiguous and the consumer blocks; it never silently switches evidence or overwrites the reappeared object.
- Accepted plan/evidence outputs recheck direct and followup-ancestor provenance after processing; ordinary current receipts do not bypass a reconciled predecessor's source gate. Cleanup and recovery also recheck after preflight before resource writes. Late cleanup/recovery drift retains measured outcomes, completed recovery steps and protection references in non-success cumulative receipts. Deployment publication refusal retains `operationResults` and explicitly reports no usable receipt. Superseded historical target states are not replayed, and these checks do not promise a cross-process atomic snapshot.
- Current-state acceptance runs semantic/lineage checks before the final snapshot-only pass. Provenance validation supplies pinned references for a final refresh without re-parsing the ancestor chain; observed targets, originals, reports and source references are refreshed after expensive validation. Verify retains absent observations too and does not change previously failed/blocked outcomes into acceptance.
- Reconcile grants no installation, deployment-retry, cleanup or live-cutover authorization: the standard `verify` described above consumes the new document next, and every later phase keeps its own gates. The regular deploy, retry and recovery paths with their runtime-lineage, signature and install gates are unchanged.

### Cleanup runtime

Cleanup has two entry points over one detection and execution engine. The batch entry `migration --phase cleanup` consumes the bound verified verification record and an explicitly confirmed `verification_id`; its sealed candidate set, cumulative receipt and retry semantics are unchanged, and immutable batch manifests never gain the new target kinds — project `.gitnexus/`, gitnexus MCP entries and AGENTS marker blocks are always handled by a fresh plan, never by hidden batch scope expansion. The fresh entry `cleanup-legacy --phase plan|apply` re-detects every supported target live and binds the confirmation to a freshly sealed plan. Neither id is authentication or ownership proof; each only binds one explicit confirmation to the candidate set that was displayed and sealed.

Batch cleanup does not redeploy. It may retain changed or absent deployment-discovery inputs only when a closed dependency check proves they do not influence cleanup: project-root identity, actual vendor footprints, all declared operation targets, ownership/source references and the backup scope remain protected. Both observations must be ordinary files or absent; new discovery paths, profile/tool binding changes, symlinks, unknown kinds and unproven dependencies still reject. Receipt-proven input changes keep their existing rules. Accepted unrelated observations are recorded as `deployment_only_inputs`, not as fresh deployment acceptance. Apply, deploy, reconcile, verify and recovery do not inherit this exception. Retained assets and root/branch/HEAD are rechecked at the last mutation gate and before acceptance publication.

After a verification whose `status` is `verified`, the Agent proactively offers cleanup: it displays the batch-sealed candidates from the verification's per-project `cleanup_candidates` and `shared_cleanup_candidates`, and runs `cleanup-legacy --phase plan` so the actual fresh candidate list is displayed as well — the combined confirmation happens only after both lists are shown, and items that were not detected are not listed. A user who declines is told that `sbtd cleanup`, `清理工作流` or the same explicit intent re-triggers the flow later. The trigger authorizes read-only detection and planning only; the explicit yes after the displayed scope authorizes execution, and one confirmation covers the displayed combined scope of batch-sealed and freshly planned candidates. Run the batch cleanup first; if it changed originals sealed by the fresh plan, regenerate that plan and display the remaining work. During the same confirmed cleanup run, the original consent also covers a plan that only removes overlap targets proven completed by the bound batch receipt, provided the remaining targets and effects are unchanged. This ordinary reduction needs no second yes; added targets or changed effects require renewed consent. Unexplained disappearance, user edits and conflicting/failed evidence still stop the flow for reconciliation. Use the current plan's id even when consent carries forward. The Agent reads `verification_id` / `plan_id` from the CLI JSON output itself; the user never pastes a hash. Normal `init` / `reset` never performs this cleanup. Entry selection is batch evidence first: only missing batch evidence falls back to a fresh plan for the retired `.trellis` / Skill targets as well, while stale, conflicting or failed batch evidence is preserved and resolved first — never used as a fallback reason to bypass a gate.

Detected candidate kinds:

- `trellis-uninstall` — a project `.trellis` directory. Removal actually runs the vendor `tl uninstall` with the project root as the working directory, driven by a dedicated adapter: plan-time preparation computes the complete vendor footprint, and before execution the footprint — `.trellis` plus the platform configuration and AGENTS entries the vendor uninstall may modify — is privately backed up. A missing CLI or a failed preparation blocks the target without executing; there is no engine direct-delete fallback and no `rm -rf`. An incomplete uninstall fails the resource and the receipt records per-resource measured after-states, so partial mutations are reported as measured evidence and must be reconciled before any retry — never claimed untouched. Batch cleanup removes its sealed `.trellis` targets through the same adapter and full-footprint backup with the existing before/after checks unchanged. A symlinked `.trellis` is blocked, not a candidate.
  Each prepared resource path must exactly match the checked project root joined with its strictly validated relative path, and execution compares the bound paths with the fresh planner replay. Resealing the descriptor does not authorize a decoy path: a mismatch is rejected as `invalid-document` before adapter backups or vendor execution. Backup, state rechecks and outcome measurement consume only bound paths. The persisted scope fingerprint shape and digest algorithm remain unchanged for valid existing plans.
- `skill-directory` — a global `trellis-workflow` or `trellis-channel` directory under the resolved global Skills root, proven by identity: a non-symlink directory whose regular `SKILL.md` frontmatter `name` exactly matches. Content drift across 1.0.x versions does not matter; there is no fixed checksum pin. A symlink, a missing or unreadable `SKILL.md`, or a mismatched `name` is blocked and preserved.
  A physical shared HOME root does not authorize every same-named directory beneath it. A standalone `shared_root` of kind `skills` binds its own `path`; when that root is absorbed into a broader record, the manifest retains its exact logical directory as `shared_root.skills_root`. Producers preserve this annotation through root merging, and consumers require the retired Skill to be its direct child. Missing logical scope for an absorbed retirement fails closed; it is not reconstructed from the current environment or from the target's basename.
  Fresh `cleanup-legacy` additionally recognizes the nine exact GitNexus Skill identities listed in [Upgrade Alignment](#upgrade-alignment). This does not widen immutable migration manifests or authorize prefix-based removal; the same direct-child, identity, backup and separate-confirmation checks apply.
- `directory-remove` — a project `.gitnexus/` directory; a symlink is blocked. This is project-local data only: the GitNexus npm package, its CLI and `~/.gitnexus` global data are never cleanup targets, and no CLI/npm uninstall is performed.
- `mcp-server-remove` — gitnexus server entries in an already existing host global configuration file. Only existing files are probed and nothing is created; the user home resolves from `HOME` or `USERPROFILE`:

  | host | probed existing paths | format |
  |---|---|---|
  | codex | `$CODEX_HOME/config.toml` and `~/.codex/config.toml` | TOML |
  | claude | `~/.claude.json`; `~/.claude/mcp.json`; `$CLAUDE_CONFIG_DIR/mcp.json` when set | JSON |
  | kimi | `~/.kimi-code/mcp.json`; `~/.kimi-code/config.toml`; `~/.kimi/mcp.json` | JSON / TOML |
  | omp | `~/.omp/agent/mcp.json`; `$PI_CODING_AGENT_DIR/mcp.json` when set; each existing `~/.omp/profiles/<profile>/agent/mcp.json`; the effective configuration resolved by the existing `active_omp_paths` resolver — relative `$PI_CONFIG_DIR` override with `OMP_PROFILE` taking precedence over `PI_PROFILE` | JSON |

  An entry identifies as gitnexus when its key is `gitnexus` / `gitnexus-mcp`, its command is a gitnexus binary, or its npx/node arguments name the gitnexus package. Removal deletes every detected gitnexus entry from `mcpServers` (JSON) or `[mcp_servers]` (TOML) and nothing else. JSON files are parsed strictly (duplicate keys rejected) and rewritten under the existing MCP write convention (normalized layout, UTF-8, trailing newline); TOML files go through a format-preserving tomlkit round-trip. Neighboring servers and all other content are preserved. An unparseable, symlinked or non-regular configuration is blocked and preserved. Spelling aliases of the same directory entry are probed once; distinct hardlink entries remain separate targets because atomic replacement changes only one entry. These files are shared by every project on the host: the displayed scope discloses that impact and the confirmation covers it.
- `marker-blocks` — a project `AGENTS.md` containing exactly one ordered pair of `<!-- TRELLIS:START -->` / `<!-- TRELLIS:END -->` (uppercase) and/or one ordered pair of `<!-- gitnexus:start -->` / `<!-- gitnexus:end -->` (lowercase), each recognized only as a top-level HTML comment block — a marker-looking line inside a code fence or inline context is ordinary content, not a marker. Removal deletes the paired blocks with their contents; every byte outside the spans, including `<!-- graft:start -->` / `<!-- graft:end -->` fences and project-owned content, is preserved. Zero pairs is not a candidate; duplicated, interleaved, nested or unmatched markers are blocked and listed for manual resolution — the file is never guess-edited.

Fresh path contract:

```text
python <installed-onboard.py> cleanup-legacy --phase plan --projects-root <comma-separated-absolute-roots> --backup-root <existing-private-directory> [--global-skills-dir <skills-root>] --json
python <installed-onboard.py> cleanup-legacy --phase apply --plan <private-cleanup-plan-file> [--cleanup-receipt <prior-private-cleanup-receipt>] --confirm-cleanup <current-plan-id> --json
```

`plan` does not mutate cleanup targets: it detects every candidate kind above for the selected roots, the resolved global Skills root and the existing host MCP files, snapshots each before-state, seals the private backup root / home / Skills root and the prepared vendor-uninstall descriptor for each `.trellis` candidate, and saves `cleanup-legacy-plan-<plan_id>.json` inside the verified private backup root; the JSON envelope carries `cleanup_legacy.plan` and its private `plan_path`. The plan-time global Skills root follows the existing resolver precedence — explicit `--global-skills-dir`, then `$AGENT_SKILLS_DIR`, then the trusted installed Onboard parent directory, then the platform default — and is sealed into the plan; `apply` consumes only that sealed root, accepts no Skills-root option of its own, and is not redirected by a changed environment. This override exists only on `cleanup-legacy --phase plan`: migration phase arguments and `cleanup-legacy --phase apply` are unchanged. Both phases reject, before any target write, candidate paths that are equal to or nested inside one another — for example a selected project `.gitnexus` containing a selected retired Skill directory — leaving every original untouched rather than relying on execution order. A target whose vendor preparation fails is recorded as blocked, and any blocked item makes the plan result `blocked` (exit 2); with no candidates the result is `nothing-to-clean` (exit 0). `apply` requires `--confirm-cleanup` equal to the current sealed `plan_id` and the plan file still in its declared private backup root; a plan whose content no longer matches its `plan_id` is a binding violation and stays blocked. Apply refuses while any blocked item remains and re-validates the whole scope before writing: the home and selected Skill root must match the plan and every remaining candidate must retain its authorized identity and intended effect. A first execution requires the sealed before-state; a receipt retry may instead use an exactly matching after-state from a proven successful vendor transition bound to that plan's prepared resources. Original backups are immutable and reused for those transitioned candidates; remaining marker edits are rendered from the original bytes, not from the partly scrubbed file. Unexpected drift or unproven state still blocks. When a successful batch has changed fresh-plan originals, regenerate the fresh plan and use its new plan_id; this token refresh does not itself require a second user yes. Within the same confirmed flow, unchanged targets/effects or a receipt-proven completed-only reduction retain the original consent; added targets or changed effects require renewed consent, and unexplained changes require reconciliation. Every candidate original is privately backed up before execution begins, then each resource executes fail-stop and its after-state is verified against the intended goal: absent for removals, exact rendered bytes for file edits. A cumulative `cleanup-legacy-receipt-<receipt_id>.json` is saved atomically beside the plan; if saving fails after writes, the run reports failure and the private backup directory must be preserved. An explicit retry passes the prior `--cleanup-receipt` of the same plan; proven successes are not replayed. Failed/partial vendor work, forged transition evidence, user edits, or an unsuccessful resource's unexplained after-state block retry until reconciled. Exit codes: plan 0 planned / nothing-to-clean, 2 blocked; apply 0 cleaned, 2 blocked, 3 failed. Non-JSON output prints only the status; detailed references stay private.

The `recovery` CLI consumes migration-batch evidence only; it does not accept cleanup-legacy plans or receipts. Fresh-path backups are retained private files with no automated restore command; restoration from them is a manual custodian operation under the retention and destruction rules below.

#### Upgrade-backed batch cleanup

Ordinary `upgrade` does not require a local lineage signature. For a completed, verified **original** migration batch whose canonical Onboard package was subsequently replaced once, cleanup accepts the optional pair `--upgrade-plan` / `--upgrade-receipt`. This narrow continuation uses the native replacement proof rather than inventing a new signature:

```text
python <installed-onboard.py> migration --phase cleanup --manifest <manifest> --apply-receipt <apply> --deployment-evidence <deployment> --verification <verified-record> --confirm-cleanup <verification_id> --upgrade-plan <private-vault>/upgrade-plan-<plan_id>.json --upgrade-receipt <private-vault>/upgrade-receipt-<receipt_id>.json --json
```

- Both inputs are required together and only on migration cleanup. Use the canonical, digest-named files saved by the native upgrade engine, with their exact canonical bytes; reformatting, partial receipts, wrong targets, wrong baselines and unbound originals reject.
- The approved, operator-controlled private vault must prove a complete isolated native upgrade with exactly one write: replacing the canonical installed Onboard package. Other resources must remain keep/preserve. The installed payload must still equal the recorded after-state; the original package must match both its full backup and payload before-state.
- Only the bound original package supplies the historical public key and existing pairing/observer proof. Its known file/interpreter/dependency fingerprint must reproduce the accepted historical runtime; unavailable or different environment evidence blocks. No arbitrary trust-key option, new private key or execution/import of backup code is permitted.
- The cleanup receipt records immutable `upgrade_context` provenance. Retry requires the same explicit upgrade evidence; new source drift fails before a write, and post-write drift produces a non-success receipt retaining measured outcomes. Sealed provenance validation does not resolve newly changed live aliases; runtime consumers recheck physical paths.
- This is one direct hop and cleanup-only, not a general migration compatibility mechanism. It cannot continue partial apply/deploy, authorize a successor/followup batch, or be consumed as an ordinary migration recovery authorization. Preserve old and upgraded packages plus all receipts for any separately planned restoration; there is no automatic recovery promise for unsupported consumers.
- Private-vault control is the historical trust assumption, as in upgrade recovery; hashes do not resist a writer who can forge the whole vault. No stale/failed batch fallback, source resealing or signature bypass is introduced.


### Backup retention and manual destruction

Backups are retained independently of migration cleanup, Graft uninstall, task completion and recovery success. No phase in this Onboard runtime deletes original backups, approved candidates, manifests, stage receipts or registered copies, and no new disposal CLI, lifecycle file, journal, lock, scheduler or evidence index is added. A manifest records the non-sensitive custodian, the explicit external private `backup_root`, the managed backup inventory and the minimum retention requirement; the normal release path keeps backups through the P3 two-week observation and at least 14 days after formal release, whichever ends later, unless the project explicitly extends it or a stricter privacy/legal requirement forces a different preservation plan before migration proceeds.

Recovery is available only while the bound manifest, stage/recovery receipts, actual backups and registered copies still prove ownership, exact scope and current state. A legal partial apply/deploy/cleanup may be recovered only for the proven writes; missing, incomplete or conflicting evidence, unknown files, symlink escape, changed targets or resources in use are evidence-insufficient and stay blocked with zero deletion and no done claim. Recovery success restores only the bound managed data and configuration comparison state; it never invokes, reinstalls, or resumes the retired Trellis runtime, and restored files never imply that runtime is executable or writable — its `runtime_readiness` stays not-verified and must not be inferred from recovery success. Recovery success never authorizes backup destruction and does not end the maintenance window: maintenance does not end automatically before the bound deployment acceptance. A same-runtime partial receipt retry only resumes that batch's unfinished writes; it is distinct from the predecessor-acceptance path above, which separately requires the signed predecessor-successor pairing and the manifest's complete successful apply receipt. Live receipts prove only the actual live state they observed; fault injection, partial retry, and recovery resume must each be proven by fresh isolated tests, and neither kind of evidence substitutes for the other.

Manual destruction is a custodian operation outside cleanup. Both the normal-release branch and the explicit migration-abandonment / release-cancellation branch require unresolved migration/recovery issues to be closed, no operation using the backups, no audit retention requirement, and a separate destruction authorization. The normal branch also requires the completed release readiness decision and the retention window to have ended; the termination branch requires the recorded termination decision, accepted necessary recovery and an explicit custodian close-out of remaining rollback needs. If P2-01 has not completed and no manifest exists, the termination branch may only process preparation artifacts whose ownership is proven by private publication-decision candidates and preparation authorization or an existing migration report.

Before any deletion, the custodian or an explicitly authorized Agent must save and reread, in an existing private preparation record or migration report outside the deletion scope, the non-sensitive custodian label, candidate ownership, exact destruction scope, this independent authorization and the actual confirmation time. The record location must first be verified private, writable and able to retain the note in its existing format; closed publication-decision schemas are not extended arbitrarily. Any missing item, including confirmation time, or any save/reread failure is blocked, deletes nothing and is not done. Destruction then rechecks each unchanged listed object in the same controlled window, deletes only listed objects, records actual deleted/failed/remaining results in the same record, and leaves unresolved paths privately retained for review. Interruption or failure preserves real results; retry rechecks the remaining list and obtains confirmation again, never treating a later same-name file as the old backup.

## Codex and OMP Wiring and Deployment

Explicit `--platform codex|omp` selects Graft host wiring in Python `init`/`reset`, even with no project roots. `--projects-root <absolute-roots>` additionally selects local graph preparation; `init-projects` remains project-only. Setup never installs or upgrades Graft/Node implicitly. Missing pinned runtime reports `graftWiring.status=not-available` for optional normal setup; explicitly authorized hooks, legacy cutover and sealed migration remain blocked. Ownership/configuration/scope failures are never downgraded. Project templates precede the fence; `--skip-project-agents` preserves surrounding instructions. Global-only success means the definition was installed, not that a project graph was queried.

`graftWiring` in `check` and `plan` is read-only installation feasibility for the selected scope, not a health certificate for the currently installed project instructions. When project AGENTS replacement is selected, pre-render the canonical template that would be backed up/applied by the later confirmed install; `--skip-project-agents` instead validates the current file. `status=planned` never authorizes a write or claims the current bytes were repaired. Root installers use the same preflight before installation.

OMP plugin MCP manifests are not modeled by this installer. The preflight conservatively rejects any discovered installed-plugin registry, including Claude configuration overrides, OMP base/profile/XDG data roots and the nearest selected-project registry. This guard does not depend only on an explicit `claude-plugins` user opt-in: the pinned host can load OMP-origin and project plugin roots by default. No registry is rewritten or plugin executed.

Full setup merges one stable global `sbtd-graft` server into the effective host configuration domain, with absolute installed runtime/launcher arguments and neither a fixed `cwd` nor a project `--root`. Repeating setup or adding another project does not add another server. Foreign configuration is preserved and conflicting managed definitions block. Project-only setup writes no HOME, global Skill or MCP/hook configuration. Existing AGENTS mirror policy remains separate from OMP MCP wiring; sealed migration lists its shared writes before confirmation.

For `--platform omp`, full `init` writes only the active OMP user MCP target: default `~/.omp/agent/mcp.json`, named-profile `~/.omp/profiles/<profile>/agent/mcp.json`, or default-profile `PI_CODING_AGENT_DIR`. It never writes hooks. Plan/execute snapshots every static OMP, Codex and Claude source it reads; inherited equivalence follows OMP's complete connection identity, not just command shape. Existing enabled equivalent connections leave an absent OMP target absent, while disabled managed entries, conflicting definitions, server/extension denylists, dynamic overlays, agent `.env`, legacy settings and provider-setting project files block rather than infer an effective host state. Migration plan selects this producer with `--deployment-platform omp`; `init-projects` declares only project fence/graph resources and has no shared MCP operation.

After migration apply, a sealed OMP discovery input may legitimately differ because a declared operation changed it. Revalidation accepts that difference only when the caller's bound successful stage results chain from the sealed state to the current state and the retained originals still match. The discovered input-path set remains exact; unrecorded changes, partial results, broken chains and changed backups still block before writes. Plan-time discovery remains strict. A source fix changes the runtime fingerprint: this input-state proof does not replace the separately signed predecessor/successor pairing or installation/deployment authorization.
Discovery still inspects the current effective provider configuration; receipt proof neither fabricates historical settings nor reintroduces retired inputs into that discovery.

Batch setup rejects nested or mutually containing selected roots before any runtime probe. Each selected root receives its own graph; batch and incremental setup use the same project operation. At MCP startup the launcher finds the nearest real Git repository/worktree from the actual process cwd and locks it for the connection. Root proof uses an external Git executable from absolute PATH entries, excludes project-local/relative entries, scrubs inherited `GIT_*` and disables system/global Git config. HOME, no repository, malformed boundaries, uninitialized nested repositories, missing/old stamps and unsafe graphs fail closed without borrowing a demo, parent or sibling graph. Hook/analyze commands retain their explicit root; MCP rejects `--root`. Changing shell cwd does not retarget an existing connection.

On Windows the root proof selects `git.exe` by its fully qualified path in each external PATH directory and requires its resolved target to remain an `.exe` outside the project. It never searches cwd implicitly or executes `.cmd`/`.bat` wrappers through PATHEXT. Global OMP ownership checks require absolute launcher and CLI paths as well as their managed filenames; matching basenames alone do not certify a record.

The Windows Git root proof decodes output as UTF-8 independently of Python's default code page, so Unicode checkout paths do not depend on UTF-8 mode. POSIX retains its existing locale decoding. Undecodable proof output is a controlled `root-unsafe` refusal before downstream launch, never a reason to weaken root equality or borrow another graph.

Full installation binds MCP/hooks to the canonical installed Onboard Skill, not a disposable bootstrap checkout. That package is installed and verified before dependent host configuration is published. If ordinary init would retain a merely-valid but different older Skill shell, wiring preflight requests an explicitly confirmed reset instead of running the old guard. Project-only uses its existing executing package because it installs no global Skill.

Hooks are absent from the default write set. `--graft-hooks` is separate consent to install the managed definitions, not host trust or execution proof. The host must support and enable hooks and trust the exact configured hashes; Onboard never edits trust state or bypasses it. Preserve all foreign handlers. Host-event acceptance is a separate real-host check. The root installers forward this option through the implemented deployment flags.

The generated Python commands use `-E -s` before the installed script: caller `PYTHONHOME`/`PYTHONPATH` and user-site startup cannot run ahead of the guard, while trusted sibling modules remain importable. The launcher uses pinned native code, an ephemeral HOME, DNT and dotenv/LLM/cloud environment isolation. It validates current graph state before every MCP request; native automatic refresh stays disabled. A graph replaced by Stop or explicit deployment is rechecked before the running MCP receives another request. Invalid state returns a sanitized protocol error and stops that session rather than forwarding the request. Missing/old/incomplete stamps are never automatically reconciled. This is a single-controller adapter, not an OS sandbox or arbitrary concurrent-writer isolation.

An unrelated hook event is ignored before requiring the bound repository to exist; a deleted binding therefore does not break other projects. Relevant events still require valid runtime/root/graph state. Existing exact pre-hardening managed hook commands without startup isolation block authorized reconciliation instead of being preserved as foreign beside new commands; ownership conflicts require explicit resolution. Normal hook trust is never bypassed.

Normal wiring exposes `backupRoots` in the plan and retains existing resource originals in a private `<scope>/.sbtd/installation-originals/<run>/` directory. Existing installer template backups keep their original policy. Migration deployment instead uses the manifest's external private `backup_root`; its deployment evidence and native raw/Chinese-summary/envelope reports are new files within the manifest's private directory.

Codex MCP tables may be split across unrelated TOML sections, including a managed server's environment subtable. Candidate rendering preserves these valid table fragments, foreign values and comments without requiring a live-file normalization pass. This layout compatibility does not admit a top-level inline `mcp_servers` table or relax legacy runtime/root ownership and explicit-retirement checks. TOMLKit must be at least 0.13.2: [that release fixes incomplete deletion of split table fragments](https://github.com/python-poetry/tomlkit/blob/0.13.2/CHANGELOG.md). Retirement also reparses the serialized candidate and refuses any residual managed legacy entry; update the installed-copy dependencies rather than weakening this check.

Old `sbtd-graft-<root-hash>` entries are migration inputs, never newly generated. Normal setup refuses them. `--graft-retire-legacy` requires exact selected old roots and complete old command/argv/cwd/env/hash ownership. Across different runtime paths, additionally supply `--graft-legacy-bindings <private-json>` with `{"schema_version":1,"bindings":[{"root":"/selected/root","python":"/old/python","node":"/old/node","cli":"/old/dist/cli.js","launcher":"/old/scripts/sbtd_graft_entry.py"}]}`. The operator must inspect actual configuration/retained evidence before approving this contract. Its private parent, closed fields, selected roots, uniqueness, absolute paths and unchanged input snapshot are checked; it must stay outside deployment targets. Preview the plan before confirmed init; preserve its JSON result and original backups for scoped restore. Root wrappers forward these flags (`-GraftRetireLegacy` / `-GraftLegacyBindings` in PowerShell).

Project-only and sealed historical deployment contexts reject cutover options. Inherited old OMP sources cannot be deleted from another configuration domain. Historical receipts remain immutable and their old owned-section shapes are still verifiable; mixed old/new generations conflict. Configuration cutover does not stop existing host processes or delete TEMP runtimes/backups. Live replacement, reload and dependency proof precede P3-05 retirement; P3-04 separately governs backup disposal.

For a migration, include the deployment choice in the original read-only plan:

```text
python <installed-onboard.py> migration --phase plan --projects-root <absolute-roots> --backup-root <external-private-vault> --custodian <actual-label> --deployment-mode init --deployment-platform codex|omp [--graft-hooks] --json
python <installed-onboard.py> init --platform codex|omp --projects-root <same-roots> --migration-manifest <manifest-file> --migration-apply-receipt <successful-apply-file> --deployment-evidence-out <new-private-file> [--graft-hooks] --yes --json
```

Use `--deployment-mode init-projects` and the `init-projects` entry only for a batch without shared-HOME operations; it cannot install global hooks. The plan seals canonical template sources plus narrowly typed `build-graft` / `configure-graft` operations bound to the installed fixed policy. Unrecognized customized global installation targets block; the current lower-severity limitation concerning unrelated existing Skill-root consumers is recorded in the repository findings ledger, not bypassed here.

Deployment validates the entire manifest/apply/runtime/scope and output path before ordinary installation side effects, then executes only declared resources. It does not run unrelated external installers, migration apply/cleanup or sync. Actual native `graft check` is `smoke-only`, not host-event, full-stack or business-behavior proof.

On retry, explicitly pass `--previous-deployment-evidence <previous-file>` and a new `--deployment-evidence-out`; completed resources retain original before/backup references and are not rewritten. Drift or unknown partial writes stop automatic continuation. The single JSON response contains `deploymentEvidence: {path, evidence}` only for this context; an unsaved/invalid result is null and nonzero, with observed writes retained. The bare saved evidence file is the input to migration verify. Ordinary init has no `deploymentEvidence` field.

## MCP Setup

MCP configuration remains optional and interactive in normal mode. Project-only mode skips it.

Built-in choices:

- Chrome DevTools MCP: `npx -y chrome-devtools-mcp@latest`
- Playwright MCP: when the selected Playwright distribution exposes it, use its bundled `npx playwright mcp` entrypoint; otherwise configure a compatible dedicated Playwright MCP server.
- Maestro MCP: `maestro mcp` with `JAVA_HOME` and `PATH`
- Custom stdio MCP: user-provided command/args/env

The generic MCP menu is separate from the Codex Graft producer described above. The producer binds the verified installed launcher and selected root directly; installation alone does not prove host trust or event execution.

Fixed platform scopes for the generic MCP menu:

- Codex: user-level `codex mcp add` behavior.
- Claude Code: `claude mcp add --transport stdio --scope user ...`.
- Kimi Code: `kimi mcp add --transport stdio ...` with its default scope behavior.
- Oh My Pi: merge into `~/.omp/agent/mcp.json` only.

Do not write project-level Claude MCP entries or `<project-root>/.omp/mcp.json`. Do not expose secrets in logs or reports.

Maestro MCP is not a separate package. Java 17+ and Maestro CLI must pass first. Native Windows Java/Maestro automatic installation remains unavailable.

## Paths

Global AGENTS:

1. `--global-agents-path`
2. `$CODEX_HOME/AGENTS.md`
3. `~/.codex/AGENTS.md`

Additional OMP global AGENTS, only when the user-home `.omp` directory already exists:

- POSIX: `~/.omp/agent/AGENTS.md`
- Windows: `%USERPROFILE%\.omp\agent\AGENTS.md`

Existing OMP `AGENTS.md` is backed up then overwritten. Missing `.omp` is skipped; Onboard does not create `.omp`. `--global-agents-path` does not disable this extra write. If `--global-agents-path` or a project `AGENTS.md` resolves to the same file as the OMP or Codex global target, `init` / `reset` keep a single file write and a single backup.



Global Skills:

1. `--global-skills-dir`
2. `$AGENT_SKILLS_DIR`
3. Parent directory of an installed `sbtd-workflow-onboard` under `~/.agents/skills`, `~/.agent/skills`, `~/.codex/skills`, `~/.claude/skills`, `~/.pi/agent/skills`, or `$CODEX_HOME/skills`
4. `$CODEX_HOME/skills`
5. `~/.codex/skills`

Project paths, repeated for every selected root:

- `<project-root>/AGENTS.md`
- `<project-root>/.gitignore`
- optional `.sbtd/active-task.json` and its selected task (read-only)
- optional `ai/tasks/00-bootstrap-guidelines/task.md` (read-only)
- conditional project Playwright dependencies/configuration
- conditional React Bits Skill/registry

Generic bundled/external workflow Skills are never installed under `<project-root>/.agent/skills` by this onboard flow.

## Shared Python Commands

```bash
python scripts/onboard.py check --projects-root /abs/one,/abs/two
python scripts/onboard.py check-projects --projects-root /abs/one,/abs/two
python scripts/onboard.py plan --platform codex --projects-root /abs/one,/abs/two --json
python scripts/onboard.py init --platform codex --projects-root /abs/one,/abs/two --yes
python scripts/onboard.py reset --platform codex --projects-root /abs/one,/abs/two --yes
python scripts/onboard.py init-projects --platform codex --projects-root /abs/one,/abs/two --yes
```

`--json` emits one stdout JSON document; diagnostics use stderr. Write modes merge plan and results, including `sbtdInit`, `sbtdProjectSetup`, `backups` and `unverifiedChecks` as applicable. Project checks expose `sbtd`, not `trellis`. Removed setup fields have no aliases. Bootstrap/invalid-state results are nonzero; argparse syntax errors retain stderr and exit 2.

Global-only onboarding is still supported by omitting `--projects-root` and explicitly skipping project AGENTS when using the Python command directly:

```bash
python scripts/onboard.py init --platform codex --skip-project-agents --yes
```

## Verification

After writes:

1. Verify every copied AGENTS file against its source template.
2. Verify every bundled global Skill directory recursively.
3. Verify the project `.gitignore` block exists in every selected root.
4. Report per-root SBTD state/bootstrap results without claiming task recovery or acceptance proof.
5. Report per-root Playwright and React Bits decisions without claiming optional installation succeeded unless the command and post-check pass.
6. Rerun the target Agent CLI and global preflight after normal onboarding.
7. Rerun only `check-projects` after project-only onboarding.

Network, permissions, missing dependencies, unsupported platform execution, malformed state, legacy migration requirements and bootstrap-required results remain explicit; no skipped check is a pass.

## Upgrade Alignment

跨平台基线按原始文件字节与相对 POSIX 字符串顺序计算。仓库根 `.gitattributes` 对整个 `sbtd-workflow-onboard/**` 禁用 checkout 文本转换，既保留二进制，也保留上游合法 CRLF；运行时不归一化内容来制造 pin 匹配。Stable promotion 必须从保留上游提交原始字节的 checkout 取证，不能把本地自动换行转换后的内容当作上游原样镜像。

`upgrade` 对显式范围进行内容对齐，不改变 `init` 跳过合法 Skill 壳、`reset` 重装和 `migration` 迁移数据的既有含义。基线来自执行中的完整 Onboard 包：catalog、模板、固定 stable 内容及来源；绝对安装路径或文件时间不是版本。不能证明历史版本时报告 `unknown-drift`，不凭名称或版本字符串猜测。

### 范围与授权

准备 version-1 scope JSON。下例只选择 Skills 与全局规则；路径须替换为真实、明确授权的绝对路径：

```json
{
  "schema_version": 1,
  "skills_roots": ["/abs/selected/skills"],
  "agents_targets": ["/abs/selected/config/AGENTS.md"],
  "hosts": [],
  "shell_profiles": [],
  "decisions": {}
}
```

一个宿主域以 `id`、`platform`、`config_home`、`config`、`skills_roots`、`runtime`（绝对 `python`／`node`／`cli`）和 `project_roots` 描述。宿主 Skills 根也必须在顶层选择。普通 Codex 与 Orca 账户使用各自的配置域，不自动扫描账号或认证目录。Codex／OMP 复用现有受管 Graft 候选生成器；其他平台不擅自新增 Graft 接线。选中已有项目用于验证，不等于初始化项目或构建图授权。

`oh-my-pi` 在计划封存前统一为 `omp`，后续应用／验证使用同一平台标识。Codex 的 `config` 必须是所选 `config_home` 下的 `config.toml`；不能对宿主不加载的其他 TOML 文件报告对齐。

同一物理 Skills 根的路径拼写别名只产生一个写入集合；目标与决定键同步绑定到选定拼写。不把大小写敏感卷上的真实不同目录合并，也不通过再次跟随 symlink／junction 来归一化用户路径。

可选 `executable` 是实际宿主 CLI 的绝对路径。`onboard_root` 表示宿主要加载的**已安装 Onboard 包目录**，不是 Skills 根：仅有一个宿主 Skills 根时派生为该根的 `sbtd-workflow-onboard`；多个根必须明确选定其中一个包目录。host-only 范围需显式选定已有且受信的包目录。最终 MCP launcher 指向这个安装目标，不能指向仓库源码或升级暂存执行器。OMP 计划同时核对所选项目的有效继承来源；相同继承连接可复用，来源变化或被禁用／冲突的受管连接不能冒充对齐。

若 OMP 的有效继承来源同时属于本批将改写的 provider 配置，计划／应用以 `inherited-dependency-conflict` 在目标写入前拒绝。先对齐 provider 配置域，再以其实际新状态重新规划 consumer；不把上一份计划中的旧继承快照用作新状态，也不在同一批中先写一半再因自身写入失败。

可选 shell profile 以 `path`、`shell`（`bash`／`zsh`／`powershell`）与绝对 `bin` 描述。仅修改该文件中的受管 PATH 块，保留其他内容；MCP 使用固定绝对运行时，不依赖 PATH。执行 profile 会运行其中用户代码，因此只读计划不启动 shell。

带 UTF-16 LE／BE BOM 的 profile 在生成候选前明确拒绝，保持原件字节，不混写 UTF-8，也不自动转码。不能表示为单个 PATH 项的目录同样写前拒绝：POSIX 的 `:`、Windows PowerShell 的 `;`，以及驱动器转换后仍含 `:` 的 Windows POSIX-shell 路径。

Windows Git Bash／zsh 的受管 PATH 使用 `/c/...` 驱动器别名（UNC 使用 `//server/share/...`），避免把 `C:` 的冒号误作 PATH 分隔符。探测只转换路径拼写，仍绑定所选 shell 实际使用的可执行文件；并存的 `graft.ps1`、`graft.exe` 不能仅因同名被判为同一目标。PowerShell 使用原生路径。

显式 shell probe 在隔离 HOME 中以交互条件加载 Bash／zsh profile；PowerShell 检查实际优先级最高的命令，alias／function 遮蔽不能被筛掉后报通过。受支持的 npm shim 按已识别的包装器结构绑定其字面相对 CLI 目标，不能把普通 `.cmd`／`.ps1` 文件的物理路径当作 `cli.js`。这证明命令解析及 CLI 文件指向，不执行包装器，也不证明其 Node 选择或实际运行成功；固定 Node 的协议能力由独立 host/runtime 检查证明。未知或具有动态路径展开的包装器不冒报匹配。

新增 Bash／zsh PATH 块使用 LF，原有 CRLF 内容不转码，避免 CR 附着于原 PATH 最后一项。旧 PATH 检测同时识别所选目录的原生／POSIX 拼写及 zsh 数组项，按完整目录边界匹配，不把同前缀目录或子目录算作已选 bin。BOMless 非 ASCII npm PS1 shim 仅在实际 PowerShell 引擎使用 UTF-8（新版引擎或 UTF-8 默认代码页）时可按 UTF-8 字面目标证明，否则报告编码未证明；不执行 wrapper。

`decisions` 以计划中的绝对目标路径为键，值为 `replace` 或 `preserve`。缺失受管资产进入安装；当前内容跳过；未知内容必须选择后重新计划，先展示额外文件及替换影响。身份不符、不安全路径或候选重叠不能靠 `replace` 放行。保留差异属于例外，不是完全对齐。个人 Skills、Caveman 未知定制、插件、hooks、账号与凭据不在默认升级范围。

对已选但缺失的 host MCP／shell profile，`preserve` 不表示“保持不存在”：仍按缺失资源安装契约处理。不需要安装时应从 scope 移除该目标；对已经存在的差异才使用 `preserve` 保留例外。

### 计划、应用与分层验收

备份根必须是已有私有目录，与安装包及所有目标互不嵌套。默认计划仅 stdout；`--output` 只创建指定私有 vault 内的新计划，不覆盖现存文件。

POSIX 使用当前用户所有权及私有权限证明；Windows 必须有可验证的私有 DACL，`chmod(0700)` 不等于 Windows 隐私证明。已有 vault 只校验、不自动修权限；执行器仅对本次新建的子目录使用既有跨平台私有目录初始化器。准备根目录时须由操作人确认，不能把 plan 变成隐式 ACL 修复。

```bash
python scripts/onboard.py upgrade --phase plan \
  --scope /abs/scope.json --backup-root /abs/private/vault \
  --output /abs/private/vault/upgrade-plan.json --json
```

展示完整计划并确认后，从返回的 `plan.plan_id` 读取 ID（不要让用户手抄 hash）。修改 scope 决策或目标后必须重新生成计划并重新展示。

```bash
python scripts/onboard.py upgrade --phase apply \
  --plan /abs/private/vault/upgrade-plan.json \
  --confirm-plan <plan_id> --yes --json

python scripts/onboard.py upgrade --phase verify \
  --plan /abs/private/vault/upgrade-plan.json \
  --receipt /abs/private/vault/upgrade-receipt-<id>.json --json
```

apply 重新推导范围并校验源、完整前态与私有备份路径，先保存原件，再逐资源写入和测量；写入意图与累计回执供中断后调和。重试必须传入对应 `--receipt`；用户新增或未知后态停止，不通过重新规划丢弃失败事实。Onboard 自身更新由校验后的独立包副本执行，不在被覆盖目录中混合导入新旧模块。跨资源不承诺原子提交；失败报告与原件均保留。

只读 verify 实测当前磁盘，不启动宿主、不构建图、不自动修复。明确批准后可添加 `--probe --yes` 进行运行时与宿主探测。报告分开：

| 层级 | 通过所需证据 | 不可替代的边界 |
|---|---|---|
| disk | 实际完整载荷或受管配置语义匹配固定基线 | 合法 Skill 壳或旧回执不够 |
| runtime | 实际绑定命令及协议能力 | shell 版本号不代表 GUI 使用相同路径 |
| host | 真实 Codex／OMP 进程加载所选受管配置的隔离投影，标记 `isolated-host/selected-projection` | 不是原配置域、GUI 或既有会话重载证明；`live_reload` 保持 unverified |
| legacy | 实际旧入口检测与独立清理结果 | 升级成功不授权删除旧资产 |

`aligned` 仅表示内容对齐；host 未验证必须继续显示未验证。`preserve` 导致 `exceptions`，必需资源不同导致 `drift`；两者非零退出。缺依赖、身份冲突、缺确认或不安全路径为 blocked，执行失败和部分失败保留实际结果。不能把该阶段退出 0 改写成“整机已经与全新安装完全一致”。

聚合状态保留 `blocked` 高于 `drift` 的优先级，并保留逐域结果。合法配置仅包含无关 MCP 时，legacy 为 `none`；非法配置仍为 `unknown`，不把两者混为一谈。

OMP 的 legacy 还计入已启用继承来源中的 `sbtd-graft-*` 入口，不把未选 provider 或 YAML 设置文件当作 MCP 源。存在但非文件的配置不能证明无旧入口，报告 unknown。host RPC 已证明 unsupported 时，host 与域汇总保持该状态，不降为 unverified。host-home 别名只绑定配置目标，不改写已精确选中的其他决定键。

OMP 来源发现／分析未完成且没有旧入口证据时，legacy 为 `unknown`／`source-discovery-incomplete`，不能由缺失 active 文件推出无继承旧项。直接 MCP 回复必须带 `jsonrpc: "2.0"`；RPC 数字 ID 不接受 Boolean 代替，合法 Number 表示仍匹配，Codex 不回显版本的独立约定保持。

写后发生回执持久化或隔离执行器失败时，CLI 返回 `status=failed`、exit 3，并携带绑定本批的 `batch`：计划／恢复 ID、`backup_root`、可取得的最后持久 `checkpoint`（或 `null`）及实测／`unknown` 的 `mutation`。旧 checkpoint 不是本次成功证明；证据再次读取失败也不得把已有写入改报为普通写前 blocked。保留这些恢复入口和原件，先核对实际状态，再按同一批次的续作／恢复规则处理。

当前 `--probe` 的宿主测试不读取认证或发起模型请求，使用临时 HOME 和所选受管配置投影。它证明真实宿主能加载该投影，不证明所有原宿主继承配置或已有连接已切换。原配置域／既有会话是否重载必须另有实际证据；普通 `check` 的 `contentAlignment.scope=skills-only` 只检查所选 Skills 根，不包括全局 AGENTS 或 MCP。

升级／恢复的计划与执行使用当前 `sys.executable -I -B` 和净化环境检查声明 Python 依赖。依赖仅在父进程 user-site 可见时，在目标及 vault 写入前以 `isolated-dependencies-unavailable` 受控拒绝；执行入口先校验封存ID确认，再检查当前解释器，不能沿用计划时另一环境的证明。须由操作人准备隔离可用的解释器依赖，不注入 user-site、取消隔离或自动安装。

OMP 隔离宿主探测保持 **user-wide** 投影边界；它不创建私有项目图，也不证明仅由项目级配置提供的连接已加载。项目级路由没有用户级等价连接时，不得把该探测报告成通过；用户级路由通过也不构成项目级路由已验证的证据。

OMP 加载判据使用 `get_state.dumpTools` 的结构化工具名与参数 schema；prompt 中提到工具 URI 不构成注册或可调用证据。隔离配置显式关闭 xdev 延迟入口，以核对实际注册的目标工具。RPC 请求写入与响应共用期限，宿主不消费 stdin 也不能无限阻塞；探测结束负责回收自有进程及管道。

<a id="probe-skill-link-authorization"></a>
#### 隔离 probe 的精确 Skill 链接授权

默认继续拒绝 Skills 根内的符号链接，不读取未批准的链接目标。授权只适用于本次隔离宿主投影：原链接保留，明确批准的物理目录复制为临时环境中的普通目录；安装、迁移、清理与通用 nofollow 策略不变。授权不允许缩减 expected Skills，不替代真实宿主 Skill／MCP 注册检查，也不证明 `live_reload`。

只在已展示并批准的宿主与 Skills 根范围内，为具体链接准备授权。下列 `--target-path` 是**允许读取该物理目录内容**的明确输入；不是安装或宿主启动授权。目录必须使用不经过链接／reparse point 的物理绝对路径，不能用通用 `resolve()` 放宽用户路径。

```bash
python scripts/onboard.py upgrade --phase authorize-link \
  --plan /abs/private/vault/upgrade-plan.json \
  --host omp-default \
  --skill-path /abs/skills/example-skill \
  --target-path /abs/physical/example-skill \
  --output /abs/private/vault/example-skill-authorization.json --json
```

本阶段不启动宿主、不修改原链接；默认只向 stdout 返回授权，`--output` 仅在原计划的私有 vault 中新建文件，拒绝覆盖。`--host` 必须是计划封存的宿主 ID，`--skill-path` 必须是其所选 Skills 根的直接子链接；目标 `SKILL.md` 的身份须匹配该 Skill。原始链接文本、链接对象身份、目标目录身份与完整内容摘要共同绑定到原 `plan_id`；授权摘要不是签名，不要求普通用户创建密钥对，授权文件必须由操作者控制。

准备授权时先比较链接文本的纯路径拼写与明确批准的物理目标；不匹配即拒绝，不先探查原链接目标的元数据，避免未经批准的 UNC／网络路径访问。拼写相同只是预检，不产生权限证明；随后仍沿原始文本逐组件执行 nofollow 检查，保留 `..` 前的隐藏链接拒绝。

读取并确认授权记录后，在原 verify 命令上追加 `--probe --yes --link-authorization`。多个授权路径使用逗号分隔；参数仅用于 probe，缺少 probe 或不匹配原计划／宿主均拒绝：

```bash
python scripts/onboard.py upgrade --phase verify \
  --plan /abs/private/vault/upgrade-plan.json \
  --receipt /abs/private/vault/upgrade-receipt.json \
  --probe --yes \
  --link-authorization /abs/private/vault/example-skill-authorization.json --json
```

授权只在当前对象和摘要仍匹配时有效；链接即使以相同文本重新创建，或目录以相同内容替换，也必须重新审查。无法证明对象身份、嵌套链接、特殊文件、错误 Skill 身份及复制漂移均停止。过期记录不自动刷新；重新批准时使用新的输出文件，旧证据保持不变。磁盘、runtime、host 与 `live_reload` 继续分别报告，物化成功本身不等于宿主加载成功。

对象绑定包含 `device`、`inode` 和纳秒级 `ctime_ns`，不把被文件系统复用的 inode 号码独自当作原对象证明。授权文档应原样消费，不经会截断大整数精度的工具重写。

多个宿主可以共享同一 Skills 根，但每个宿主须各自准备授权并在同次 verify 中提供；仅拒绝同一宿主与逻辑路径的重复授权，不把一个宿主的授权借给另一个宿主。相对链接中的 `..` 逐级按 nofollow 证明；Windows 普通盘符／UNC 与对应 `\\?\` 拼写只用于等价比较，仍保留原始链接文本和对象身份。未知设备命名空间、尾点／尾空格歧义保持拒绝。

`SKILL.md` 身份与封存快照中的同一文件摘要绑定，私有副本再次验证身份，已授权 Skill 不能从 expected 集合静默消失。上述检查使用既有基于路径的快照／复制原语，不是跨进程原子文件系统事务，也不保证其他进程在检查完成后不再修改对象；操作者须控制授权文件和输入目录。

持久行为规格沿用本仓 Markdown 约定，中文场景与 English Given／When／Then；自动化映射为 `tests/test_sbtd_probe_links.py` 及既有 `tests/test_sbtd_upgrade_hosts.py`：

| 场景 | Given / When / Then |
|---|---|
| 未授权目标不访问 | Given 所选根含链接且未提供对应授权；When 请求隔离 probe；Then 拒绝该投影，不跟随链接读取目标，不改原链接 |
| 精确批准只物化投影 | Given 批准绑定原计划、宿主、逻辑路径、原始链接文本、物理目录及身份／摘要；When 所有绑定仍匹配；Then 在隔离目录复制普通 Skill 目录，并完整核对宿主实际加载 |
| 共享根按宿主授权 | Given 两个宿主共享同一个链接 Skill；When 分别提供绑定各宿主的有效授权；Then 两个宿主均可验证，授权不跨宿主借用，同宿主重复仍拒绝 |
| 授权与现场不符 | Given 授权属于其他计划／宿主或链接／目标已替换；When 消费授权；Then 拒绝，不自动刷新批准或改写旧计划／回执 |
| 不安全嵌套仍拒绝 | Given 批准的目录含嵌套链接、特殊文件或不安全路径；When 准备或消费授权；Then 拒绝，不递归扩大访问范围 |
| 身份与封存内容一致 | Given Skill 身份已检查；When SKILL.md 在封存前删除或替换；Then 不签发与该身份不符的授权，私有副本也不能省略已授权 Skill |
| Windows 原生链接文本 | Given readlink 返回合法扩展盘符或 UNC 拼写；When 批准相同物理目录；Then 在 nofollow 和对象身份均匹配后接受，原始文本不改；未知设备路径仍拒绝 |
| 复制漂移不接受 | Given 复制前后链接、目标身份或内容出现变化；When 完成投影检查；Then 不启动宿主或不发布成功结果，保留原链接与原件 |

Bash 入口为 `bash install.sh upgrade ...`，PowerShell 为 `./install.ps1 -WorkflowMode upgrade ...`；工作流参数直接转发，不运行普通 onboarding。恢复也由两入口转发。

### 独立恢复与旧资产退出

```bash
python scripts/onboard.py recovery --phase plan \
  --upgrade-plan /abs/private/vault/upgrade-plan.json \
  --upgrade-receipt /abs/private/vault/upgrade-receipt-<id>.json \
  --output /abs/private/vault/recovery-plan.json --json

python scripts/onboard.py recovery --phase apply \
  --upgrade-recovery-plan /abs/private/vault/recovery-plan.json \
  --confirm-recovery <recovery_id> --json
```

恢复只针对本批实际写过的资源，绑定当前实测后态及原件。展示恢复清单后另行确认；后态漂移时保留用户内容并阻断。不自动删除备份，也不承诺恢复旧运行时可用。恢复重试使用返回的累计 `--recovery-receipt`。升级恢复参数不能与 migration 恢复参数混用。

已确认的 restore 意图之后，目标 `absent` 是既有恢复续作窗口，不要求额外“删除完成”checkpoint；这不是覆盖未知非空内容的授权。当前内容与可接受续作状态不符时仍停止，保留备份和冲突内容。

**历史信任边界：** 操作人明确选择且独占管理的已有私有 vault 是受信历史来源。摘要和相互引用验证一致性，不是签名认证；不能防御有 vault 写权限的人整组一致伪造计划、回执、意图与 checkpoint。不得从未知来源接收整套 vault 并据此自动删除文件。来源或控制权存疑时停止恢复，人工核对原件及操作记录。本流程不创建独立签名密钥或后台信任服务。

执行始终绑定当前受信 Onboard 包；包内容在独立升级后变化时，旧计划可能返回 `source-stale`，不会自动信任并执行 vault 内历史代码。保留旧失败证据，使用可信原包核对或重新规划。生成缓存不改变载荷对齐，但恢复仍保护完整当前内容；新增缓存不自动归本批所有。恢复资源后保留空父目录，避免把并发创建的用户目录误删。

源包与安装目标具有包含关系本身不构成全面禁令，仍按内容、目标冲突与分阶段执行边界判断。嵌套安装后，原 bootstrap 可能因自身树内容改变而变成 `source-stale`；应从本次安装的**同基线规范 Onboard 副本**继续重试／恢复，而不是据此执行 vault 内历史代码或放宽基线校验。

九个退役 GitNexus Skills 纳入现有独立 `cleanup-legacy` 身份检测：`gitnexus-cli`、`gitnexus-debugging`、`gitnexus-exploring`、`gitnexus-guide`、`gitnexus-impact-analysis`、`gitnexus-pdg-query`、`gitnexus-pr-review`、`gitnexus-refactoring`、`gitnexus-taint-analysis`。仅在所选根的直接子目录且自身 `SKILL.md` 名称相符时成为候选。没有前缀删除，不卸载 CLI，不删除 `~/.gitnexus`、未选项目索引、历史运行时或备份；清理计划、独立确认和完整原件保护沿用 Cleanup Runtime。

### 升级行为验收场景

本仓库以 Markdown 场景映射现有 unittest，不生成 `.feature`。场景正文中文，结构关键词英文。

| Scenario | Given / When / Then |
|---|---|
| U01 只读完整盘点 | Given 空选定目录；When plan；Then 返回完整 catalog 载荷与摘要，目标和 vault 无新增 |
| U02 合法旧壳不冒充当前 | Given 名称合法但正文或辅助文件不同；When plan；Then 报告缺失、不同、额外文件和未知漂移 |
| U03 升级收敛 | Given 明确替换差异；When apply 后 verify；Then 受管载荷与同基线全新安装等价，原件保留 |
| U04 定制保留 | Given preserve 决定；When verify；Then 报告例外而非完全对齐 |
| U05 多域隔离 | Given 多域与共享根；When apply；Then 共享资源只写一次，未选域不变 |
| U06 前态变化拒绝 | Given 计划后源或目标改变；When apply；Then 不覆盖并报告冲突 |
| U07 重复执行 | Given 上次已完成且后态未变；When 重试或重新计划；Then 不重复改写与制造备份 |
| U08 故障恢复 | Given 部分失败或写后中断；When 续作或确认恢复；Then 记录真实后态且保护原件和用户新增 |
| U09 自升级隔离 | Given 当前包属于更新集合；When apply；Then 独立已校验包执行，载荷不混版 |
| U10 混合配置保护 | Given 其他 MCP 与注释；When 接线；Then 保留无关内容，未知受管所有权拒绝 |
| U11 分层验收 | Given 文件对齐但未有真实宿主证据；When verify；Then disk 与 host 分开，host 不冒报通过 |
| U12 退役身份 | Given 精确旧名及同名异身份目录；When cleanup；Then 仅获批且身份通过者可退出，冲突保留 |
| U13 PATH 与 MCP 分离 | Given 所选 profile；When 确认应用；Then 受管块幂等，MCP 不依赖 shell PATH |
| U14 路径安全 | Given 中文/空格路径或 symlink/junction/重叠目标；When plan/apply；Then 合法路径正确处理，越界拒绝 |
| U15 脱敏输出 | Given 配置含私密字段；When 计划、验证或错误；Then 不打印原始配置或凭据 |
| U16 输入与编码拒绝 | Given UTF-16 profile、不可表达的 PATH 项或非规范 Codex 配置名；When plan／render；Then 写前拒绝，原字节与未选配置不变 |
| U17 真实探测证据 | Given 交互守卫、命令遮蔽、npm shim 或 OMP 工具文本；When 显式 probe；Then 真实优先级与受限 CLI 指向可验证，只有有效 RPC 注册表可证明 OMP 加载，写入／响应均受期限约束 |
| U18 物理路径边界 | Given 物理路径别名、大小写敏感目录或父目录中的无关链接；When plan／apply；Then 同一资源只绑定一次，不合并不同目录，不递归读取无关兄弟，根路径包含判断正确 |
| U19 状态与失败入口 | Given 写后证据失败、平台别名或混合域状态；When CLI 返回／verify；Then 保留绑定批次的 checkpoint 与实测／unknown，平台统一，blocked 不被 drift 掩盖，合法无关 MCP 与非法配置区分 |
| U20 冲突目标别名 | Given 同一既有定制 AGENTS 的不同大小写物理别名分别声明 replace／preserve；When plan／apply；Then 写入前拒绝重叠，原文件及 vault 不变 |
| U21 决定与依赖别名 | Given 已选配置／profile／Onboard 子目录的真实别名或继承输入别名；When 绑定决定／预检；Then 合法决定绑定封存目标，依赖写入冲突在任意目标修改前拒绝 |
| U22 协议边界 | Given data-only method 回复、缺失／不支持 MCP 协商版本或异常关闭；When probe；Then 不报告 verified；支持的协商版本可正常使用，缺失宿主方法脱敏报告 unsupported |
| U23 Profile 兼容性 | Given 首行 UTF-8 BOM、Unicode PowerShell PATH 或登录守卫；When render／probe；Then 保留既有 BOM，新 PowerShell profile 兼容 5.1，登录 profile 在隔离登录模式检验 |
| U24 受控 CLI 拒绝 | Given 未授权 probe 或无法展开的用户目录；When CLI；Then 返回满足 failureDocument 的脱敏拒绝，前者不读取 plan |
| U25 写入归属保护 | Given intent 后明确记录未写入且用户内容恰等于 desired；When retry／用旧 checkpoint recovery；Then 不认领或删除用户内容；有 intent 的未知现场阻断恢复，不静默空恢复成功 |
| U26 宿主配置隔离 | Given 真实项目存在未选 Codex MCP／配置；When 授权隔离 probe；Then 不加载该项目配置，仍验证所选受管连接与 Skills |
| U27 缺失 Unicode 别名 | Given APFS 下缺失目标的 NFC／NFD 等价拼写及 preserve；When plan／apply；Then 目标写入前拒绝重叠，不改变 preserve 现场 |
| U28 Shell 命令依赖 | Given 受管 shell 命令位于同批被替换的 Skill 内；When apply；Then 先拒绝依赖冲突，目标均不写入 |
| U29 既有 Profile 与路径编码 | Given 非空 BOMless PowerShell profile、Unicode 路径或 npm shim 字面标点；When render／probe；Then 无关字节保持，5.1正确解释PATH、stdout正确解码、路径内部Unicode分隔符不被截断、动态shim仍拒绝 |
| U30 有效域与状态汇总 | Given OMP有效继承旧入口、非文件配置或不支持的host RPC；When verify；Then legacy按有效选定来源报告，非文件unknown，unsupported不降为unverified |
| U31 封存范围稳定 | Given 缺失Skills根与AGENTS路径是大小写／规范化别名；When plan；Then 写前拒绝范围重叠，合法范围在创建目录后仍可重试／恢复 |
| U32 隔离依赖一致 | Given 仅父解释器user-site可见的依赖或执行解释器不同于计划时；When plan／apply；Then 在目标和vault写入前确认当前隔离解释器可用性，否则受控拒绝并引导准备依赖 |
| U33 POSIX换行保全 | Given 带CRLF注释的Bash/zsh profile；When加入PATH块并加载；Then 保留原字节，原PATH最后目录仍能解析命令 |
| U34 原生shim编码证明 | Given PowerShell5.1与BOMless非ASCII npm shim；When probe；Then 按实际解码证明CLI指向或拒绝matched，不执行wrapper |
| U35 RPC类型与版本 | Given Boolean ID或MCP缺失／错误jsonrpc版本；When probe；Then 不获得verified，合法Number ID与Codex兼容保持 |
| U36 未发现不等于不存在 | Given OMP接线前置条件不满足或Windows Bash旧PATH为POSIX拼写；When verify；Then 未完成来源发现为unknown，已选旧PATH仍报告，同前缀或子目录不计 |
